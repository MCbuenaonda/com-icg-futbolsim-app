"""
Plantilla de siembra de los Corporativos Deportivos: qué selecciones y jugadores representa cada uno de los 10
corporativos al nacer un universo (config/corporativos.py). Se calcula UNA vez, es determinística (semilla fija)
y se copia en cada universo nuevo: todos los usuarios arrancan con el mismo mundo.

    python sembrar_corporativos.py --muestra    # muestra el reparto, no escribe
    python sembrar_corporativos.py --aplicar    # (re)escribe corp_plantilla_siembra (solo afecta universos nuevos)

Reglas: cada tier recibe su cantidad de selecciones (algunas del top 20 del ranking actual) y de jugadores
(los tiers altos, del percentil de valor alto); la región de afinidad pesa el doble; los perfiles "cantera"
prefieren jugadores jóvenes; nadie se repite. El resto queda LIBRE.
"""
import math
import sys
from datetime import datetime

import certifi
from pymongo import MongoClient

from config import corporativos as C
from config.settings import MONGODB_URI
from services import corporativo_reglas as R

db = MongoClient(MONGODB_URI, tlsCAFile=certifi.where()).get_database("mundial")
SEMILLA = "siembra-corporativos-v1"


def _muestra_ponderada(rng, candidatos: list, pesos: dict, k: int) -> list:
    """k elementos sin reemplazo, con probabilidad proporcional al peso (Efraimidis-Spirakis)."""
    claves = {c: rng.random() ** (1 / max(pesos.get(c, 1.0), 1e-6)) for c in candidatos}
    return sorted(candidatos, key=claves.get, reverse=True)[:k]


def _afines(corp: dict, paises: dict) -> set:
    a = corp["afinidad"]
    return {pid for pid, p in paises.items() if pid in a["paises"] or p["confederacion_id"] in a["confederaciones"]}


def calcular_plantilla() -> list:
    rng = R.semilla(SEMILLA)
    paises = {p["id"]: p for p in db["paises"].find({}, {"_id": 0, "id": 1, "nombre": 1, "confederacion_id": 1,
                                                          "valor": 1, "aficionados": 1, "estadisticas.rankin": 1,
                                                          "estadisticas.poder": 1})}
    rankin = {pid: (p.get("estadisticas") or {}).get("rankin") or 211 for pid, p in paises.items()}
    poder = {pid: (p.get("estadisticas") or {}).get("poder") or 0 for pid, p in paises.items()}
    jugadores = list(db["jugadores"].find({}, {"_id": 0, "id": 1, "pais_id": 1, "overall": 1, "rendimiento": 1, "edad": 1}))
    valores = R.valores_jugadores(jugadores, poder)
    pct = R.percentiles(valores)
    edad = {j["id"]: j.get("edad") for j in jugadores}
    pais_de = {j["id"]: j.get("pais_id") for j in jugadores}

    top20 = [pid for pid in paises if rankin[pid] <= 20]
    usados_paises, usados_jugadores = set(), set()
    plantilla = []
    # Los tiers altos eligen primero (como en la vida real, se quedan con lo mejor)
    for corp in sorted(C.CORPORATIVOS, key=lambda c: -C.ORDEN_TIER[c["tier"]]):
        tier = C.TIERS[corp["tier"]]
        afines = _afines(corp, paises)
        peso_afin = lambda pid: C.PESO_AFINIDAD_SIEMBRA if pid in afines else 1.0

        n_sel = rng.randint(*tier["selecciones"])
        libres_top = [p for p in top20 if p not in usados_paises]
        elegidas = _muestra_ponderada(rng, libres_top, {p: peso_afin(p) for p in libres_top}, tier["top20_selecciones"])
        sesgo = {"A": lambda r: 2 - r / 211, "B": lambda r: 1.0, "C": lambda r: 1 + r / 211}[corp["tier"]]
        # identidad regional garantizada: al menos la mitad de la cartera es de su región (si quedan disponibles)
        faltan_region = max(0, math.ceil(n_sel * C.FRACCION_REGIONAL_SELECCIONES) - len(set(elegidas) & afines))
        region = [p for p in afines if p not in usados_paises and p not in elegidas and p not in top20]
        elegidas += _muestra_ponderada(rng, region, {p: sesgo(rankin[p]) for p in region}, faltan_region)
        resto = [p for p in paises if p not in usados_paises and p not in elegidas and p not in top20]
        elegidas += _muestra_ponderada(rng, resto, {p: peso_afin(p) * sesgo(rankin[p]) for p in resto}, n_sel - len(elegidas))
        usados_paises.update(elegidas)

        cantera = corp["perfil"] == "cantera"
        candidatos = [j for j in valores if j not in usados_jugadores and pct[j] >= tier["percentil_jugadores"]]
        pesos = {j: peso_afin(pais_de[j]) * (3.0 if cantera and (edad[j] or 30) <= C.EDAD_MAXIMA_CANTERA else 1.0)
                 for j in candidatos}
        de_region = [j for j in candidatos if pais_de[j] in afines]
        jug = _muestra_ponderada(rng, de_region, pesos, math.ceil(tier["jugadores"] * C.FRACCION_REGIONAL_JUGADORES))
        resto_j = [j for j in candidatos if j not in set(jug)]
        jug += _muestra_ponderada(rng, resto_j, pesos, tier["jugadores"] - len(jug))
        usados_jugadores.update(jug)
        plantilla.append({"sigla": corp["sigla"], "selecciones": sorted(elegidas), "jugadores": sorted(jug)})

    # resumen para --muestra
    for fila in plantilla:
        fila["_resumen"] = {
            "selecciones": [(paises[p]["nombre"], rankin[p]) for p in sorted(fila["selecciones"], key=rankin.get)],
            "valor_selecciones": sum(R.valor_seleccion(paises[p]) for p in fila["selecciones"]),
            "valor_jugadores": sum(valores[j] for j in fila["jugadores"]),
            "afines": sum(1 for j in fila["jugadores"] if pais_de[j] in _afines(C.CORPORATIVO_POR_SIGLA[fila["sigla"]], paises)),
        }
    return plantilla


def main(aplicar: bool) -> None:
    plantilla = calcular_plantilla()
    total_sel = sum(len(f["selecciones"]) for f in plantilla)
    total_jug = sum(len(f["jugadores"]) for f in plantilla)
    for f in plantilla:
        r, corp = f["_resumen"], C.CORPORATIVO_POR_SIGLA[f["sigla"]]
        print(f"{f['sigla']} (tier {corp['tier']}, capital {C.TIERS[corp['tier']]['capital']:,})  "
              f"{len(f['selecciones'])} selecciones ({r['valor_selecciones']:,})  "
              f"{len(f['jugadores'])} jugadores ({r['valor_jugadores']:,}, {r['afines']} de su región)")
        print("     " + ", ".join(f"{n} (#{rk})" for n, rk in r["selecciones"]))
    print(f"\nTotal: {total_sel} selecciones de 211 ({total_sel / 211:.0%}), {total_jug} jugadores asignados")
    if aplicar:
        ahora = datetime.utcnow()
        db["corp_plantilla_siembra"].delete_many({})
        db["corp_plantilla_siembra"].insert_many([{k: v for k, v in f.items() if not k.startswith("_")} | {"generada_en": ahora}
                                                   for f in plantilla])
        print("Plantilla guardada en corp_plantilla_siembra")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo not in ("--muestra", "--aplicar"):
        print(__doc__)
    else:
        main(aplicar=modo == "--aplicar")
