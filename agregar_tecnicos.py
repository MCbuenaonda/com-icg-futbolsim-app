"""
Agrega los DIRECTORES TÉCNICOS: 5 por selección, de su nacionalidad, en la colección nueva 'directores_tecnicos'
(permanente: restart_mundial no la toca). Cada selección tiene un DT en funciones (paises.dt_id) que la federación
mantiene o cambia según los resultados (ver services/tecnicos_service.py); los otros 4 esperan en el "banco".

    python agregar_tecnicos.py --cache <dir> --descargar [--paises A,B]   # baja y cachea de Wikidata (solo lectura)
    python agregar_tecnicos.py --cache <dir> --muestra [--paises A,B]     # informe por país, no escribe
    python agregar_tecnicos.py --cache <dir> --aplicar                    # inserta (respaldo en respaldos/)
    python agregar_tecnicos.py --revertir                                 # borra los técnicos y sus estampas

Fuente: Wikidata, una consulta por país: personas vivas con ocupación "entrenador de fútbol" (Q628099), hombres,
nacidas desde 1950, con ciudadanía (P27) o país deportivo (P1532) del país. Puntaje = cantidad de equipos que
dirigieron (P6087) + selecciones dirigidas + fama (log de Wikipedias con artículo).

Reglas:
  - No puede ser alguien que ya está en el sistema: ni jugador ni leyenda (por el QID de Wikidata de las leyendas y
    por nombre normalizado contra toda 'jugadores') ni árbitro (las vistas buscan árbitros por nombre).
  - Cada persona es técnico de UN solo país: con doble nacionalidad queda en el país con menos candidatos.
  - Edad 35..75.
  - Faltantes (selecciones chicas): técnicos INVENTADOS con nombre y apellido tomados de jugadores reales de esa
    selección (combinación que no coincide con nadie), `ficticio: true`.
  - Rasgos permanentes 0..100 (semilla = id): lectura y motivacion (con un plus para los de mejor currículum DENTRO
    de su país, así cada país tiene la misma distribución: paridad), temperamento y confianza_leyendas al azar;
    estilo ofensivo / equilibrado / defensivo.

Después de aplicar: generar_avatares_tecnicos.py --generar/--subir/--asignar y asignar_tecnicos_partidos.py.
"""
import argparse
import gzip
import json
import math
import os
import random
import re
import sys
import unicodedata
from datetime import date, datetime
from typing import Dict, List, Optional

import actualizar_jugadores_reales as AR
import agregar_leyendas as L

RAIZ = os.path.dirname(os.path.abspath(__file__))
POR_PAIS = 5
EDAD_MIN, EDAD_MAX = 35, 75
CANDIDATOS = 300
# Países que no son un Estado con código ISO propio en Wikidata (naciones del Reino Unido)
QID_SUBDIVISION = {"gb-eng": "Q21", "gb-sct": "Q22", "gb-wls": "Q25", "gb-nir": "Q26"}
ESTILOS = [("ofensivo", 0.30), ("equilibrado", 0.40), ("defensivo", 0.30)]


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def _consulta(iso: str) -> str:
    sujeto = f"wd:{QID_SUBDIVISION[iso]}" if iso in QID_SUBDIVISION else "?pais"
    filtro_pais = "" if iso in QID_SUBDIVISION else f'?pais wdt:P297 "{iso.upper()}" .'
    return f"""SELECT ?p (SAMPLE(?en) AS ?en) (SAMPLE(?es) AS ?es) (SAMPLE(?nac) AS ?nac) (SAMPLE(?sl) AS ?sl)
 (SAMPLE(?art) AS ?art) (COUNT(DISTINCT ?eq) AS ?eqs) (COUNT(DISTINCT ?sel) AS ?sels) WHERE {{
 {filtro_pais}
 {{ ?p wdt:P27 {sujeto} }} UNION {{ ?p wdt:P1532 {sujeto} }}
 ?p wdt:P106 wd:Q628099 ; wdt:P21 wd:Q6581097 ; wdt:P569 ?nac ; wikibase:sitelinks ?sl .
 FILTER NOT EXISTS {{ ?p wdt:P570 ?m }}
 FILTER(?nac > "1950-01-01"^^xsd:dateTime)
 OPTIONAL {{ ?p wdt:P6087 ?eq . OPTIONAL {{ ?eq wdt:P31 wd:Q6979593 . BIND(?eq AS ?sel) }} }}
 OPTIONAL {{ ?p rdfs:label ?en FILTER(lang(?en)="en") }} OPTIONAL {{ ?p rdfs:label ?es FILTER(lang(?es)="es") }}
 OPTIONAL {{ ?art schema:about ?p ; schema:isPartOf <https://en.wikipedia.org/> }}
}} GROUP BY ?p ORDER BY DESC(?eqs) DESC(?sl) LIMIT {CANDIDATOS}"""


def _paises(db, solo=None):
    ps = list(db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1, "confederacion_id": 1}).sort("id", 1))
    return [p for p in ps if not solo or p["nombre"] in solo]


# ---------------------------------------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------------------------------------
def descargar(cache: str, solo=None) -> None:
    os.makedirs(cache, exist_ok=True)
    archivo = os.path.join(cache, "tecnicos.json")
    datos = json.load(open(archivo)) if os.path.exists(archivo) else {}
    for p in _paises(AR._db(), solo):
        clave = str(p["id"])
        if clave in datos and not solo:
            continue
        iso = AR.codigo_iso(p.get("bandera") or "")
        filas = []
        if iso:
            for b in L._sparql(_consulta(iso))["results"]["bindings"]:
                f = L._fila(b)
                if not f["nombre"]:
                    continue
                f["equipos"] = int(b.get("eqs", {}).get("value", 0))
                f["selecciones"] = int(b.get("sels", {}).get("value", 0))
                filas.append({k: f[k] for k in ("qid", "nombre", "nombre_en", "nac", "fama", "enlace", "equipos", "selecciones")})
        datos[clave] = {"pais": p["nombre"], "iso": iso, "candidatos": filas}
        print(f"{p['nombre']:<28} {iso or '-':<7} {len(filas):>3} candidatos")
        json.dump(datos, open(archivo, "w"), ensure_ascii=False)
    print(f"Cache: {archivo}")


# ---------------------------------------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------------------------------------
def _puntaje(c: dict) -> float:
    return c.get("equipos", 0) + 4 * c.get("selecciones", 0) + 2 * math.log1p(c.get("fama", 0))


def _edad(nac, hoy: date) -> Optional[int]:
    if not nac:
        return None
    return hoy.year - nac[0] - ((hoy.month, hoy.day) < (nac[1], nac[2]))


def _excluidos(db):
    jugadores = list(db["jugadores"].find({}, {"nombre": 1, "wikidata": 1, "pais_id": 1, "leyenda": 1}))
    qids = {j["wikidata"] for j in jugadores if j.get("wikidata")}
    nombres = {_normalizar(j["nombre"]) for j in jugadores} | {_normalizar(a["nombre"]) for a in db["arbitros"].find({}, {"nombre": 1})}
    return qids, nombres, jugadores


def _inventados(rng: random.Random, pais_id: int, cantidad: int, jugadores: List[dict], prohibidos: set) -> List[dict]:
    """Nombre de un jugador real de la selección + apellido de otro (verosímil para el idioma local)."""
    propios = [j["nombre"].split() for j in jugadores if j.get("pais_id") == pais_id and len(j["nombre"].split()) >= 2]
    nombres = sorted({p[0] for p in propios})
    apellidos = sorted({" ".join(p[1:]) for p in propios})
    salida = []
    for _ in range(500):
        if len(salida) >= cantidad or not nombres:
            break
        completo = f"{rng.choice(nombres)} {rng.choice(apellidos)}"
        if _normalizar(completo) in prohibidos:
            continue
        prohibidos.add(_normalizar(completo))
        salida.append({"qid": None, "nombre": completo, "edad": rng.randint(38, 66), "fama": 0, "ficticio": True})
    return salida


def calcular(cache: str, solo=None, hoy: Optional[date] = None):
    hoy = hoy or date.today()
    db = AR._db()
    datos = json.load(open(os.path.join(cache, "tecnicos.json")))
    qids_sistema, prohibidos, jugadores = _excluidos(db)
    paises = {p["id"]: p for p in _paises(db)}

    # candidatos válidos por país
    validos: Dict[int, List[dict]] = {}
    descartes = {"jugador_o_leyenda": 0, "edad": 0}
    for clave, info in datos.items():
        lista = []
        for c in info["candidatos"]:
            edad = _edad(c.get("nac"), hoy)
            if c["qid"] in qids_sistema or _normalizar(c["nombre"]) in prohibidos:
                descartes["jugador_o_leyenda"] += 1
                continue
            if edad is None or not EDAD_MIN <= edad <= EDAD_MAX:
                descartes["edad"] += 1
                continue
            lista.append({**c, "edad": edad})
        lista.sort(key=lambda c: -_puntaje(c))
        validos[int(clave)] = lista

    # cada persona en un solo país: primero los países con menos candidatos
    usados, elegidos = set(), {}
    for pais_id in sorted(validos, key=lambda k: (len(validos[k]), k)):
        sel = []
        for c in validos[pais_id]:
            if len(sel) >= POR_PAIS:
                break
            if c["qid"] in usados or _normalizar(c["nombre"]) in {_normalizar(s["nombre"]) for s in sel}:
                continue
            usados.add(c["qid"])
            sel.append(c)
        elegidos[pais_id] = sel
    for c_sel in elegidos.values():
        for c in c_sel:
            prohibidos.add(_normalizar(c["nombre"]))

    resultado = []
    for pais_id, p in sorted(paises.items()):
        if solo and p["nombre"] not in solo:
            continue
        sel = list(elegidos.get(pais_id, []))
        if len(sel) < POR_PAIS:
            sel += _inventados(random.Random(f"dt|{pais_id}"), pais_id, POR_PAIS - len(sel), jugadores, prohibidos)
        resultado.append((pais_id, p["nombre"], sel))
    return resultado, descartes


def muestra(cache: str, solo=None) -> None:
    resultado, descartes = calcular(cache, solo)
    reales = sum(1 for _, _, s in resultado for c in s if not c.get("ficticio"))
    total = sum(len(s) for _, _, s in resultado)
    for pais_id, pais, sel in resultado:
        txt = " · ".join(f"{c['nombre']} ({c['edad']}){'*' if c.get('ficticio') else ''}" for c in sel)
        print(f"{pais:<26} {txt}")
    completos = sum(1 for _, _, s in resultado if all(not c.get("ficticio") for c in s))
    print(f"\nTotal {total} técnicos: {reales} reales y {total - reales} inventados (*). "
          f"Países con los 5 reales: {completos}/{len(resultado)}. Descartados: {descartes}")


# ---------------------------------------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------------------------------------
def _rasgo(rng: random.Random, plus: float = 0.0) -> int:
    return int(round(max(15, min(95, rng.gauss(55 + plus, 13)))))


def _documento(nuevo_id: int, pais_id: int, pais: str, rango: int, c: dict) -> dict:
    rng = random.Random(f"dt|{nuevo_id}")
    plus = (2 - rango) * 4   # el de mejor currículum de su país +8, el último -8 (misma escala en todos los países)
    return {
        "id": nuevo_id, "nombre": c["nombre"], "pais_id": pais_id, "pais": pais, "edad": c["edad"], "genero": "M",
        "fecha_nacimiento": "-".join(f"{x:02d}" for x in c["nac"]) if c.get("nac") else None,
        "wikidata": c.get("qid"), "wikis": c.get("fama") or 0, "enlace": c.get("enlace"),
        "equipos_dirigidos_real": c.get("equipos", 0),
        **({"ficticio": True} if c.get("ficticio") else {}),
        "estilo": rng.choices([e for e, _ in ESTILOS], weights=[w for _, w in ESTILOS])[0],
        "lectura": _rasgo(rng, plus), "motivacion": _rasgo(rng, plus),
        "temperamento": _rasgo(rng), "confianza_leyendas": _rasgo(rng),
        "avatar_imagen": None,
    }


def _indices(db, coleccion: str, indices) -> None:
    """Crea índices sin bloquear: en el cluster compartido de Atlas un createIndexes puede no confirmar nunca
    (ver CLAUDE.md, corporativos); la app funciona igual sin ellos."""
    for claves, unico in indices:
        try:
            db[coleccion].create_index(claves, unique=unico, maxTimeMS=15000)
        except Exception as e:
            print(f"  (índice {claves} de {coleccion} sin confirmar: {type(e).__name__})")


def aplicar(cache: str) -> None:
    db = AR._db()
    if db["directores_tecnicos"].count_documents({}):
        sys.exit("Ya hay técnicos cargados: --revertir primero si querés volver a generarlos.")
    resultado, _ = calcular(cache)
    docs, siguiente = [], 1
    for pais_id, pais, sel in resultado:
        for rango, c in enumerate(sel):
            docs.append(_documento(siguiente, pais_id, pais, rango, c))
            siguiente += 1
    os.makedirs(os.path.join(RAIZ, "respaldos"), exist_ok=True)
    archivo = os.path.join(RAIZ, "respaldos", f"tecnicos_{datetime.now():%Y%m%d_%H%M%S}.json.gz")
    with gzip.open(archivo, "wt", encoding="utf-8") as f:
        json.dump({"docs": docs}, f, ensure_ascii=False, default=str)
    db["directores_tecnicos"].insert_many(docs, ordered=False)
    _indices(db, "directores_tecnicos", [("id", True), ("pais_id", False)])
    print(f"Técnicos insertados: {len(docs)} · respaldo {archivo}")
    print("Ahora: generar_avatares_tecnicos.py --generar/--subir/--asignar y asignar_tecnicos_partidos.py --muestra.")


def revertir() -> None:
    db = AR._db()
    n = db["directores_tecnicos"].count_documents({})
    if not n:
        print("No hay técnicos cargados.")
        return
    albums = db["user_albums"].update_many({"owned_tecnicos": {"$exists": True}}, {"$unset": {"owned_tecnicos": ""}})
    db["paises"].update_many({}, {"$unset": {"dt_id": "", "federacion_paciencia": ""}})
    db["dt_cargos"].delete_many({})
    db["juegos"].update_many({"resultado.dt": {"$exists": True}}, {"$unset": {"resultado.dt": ""}})
    r = db["directores_tecnicos"].delete_many({})
    print(f"Técnicos borrados: {r.deleted_count} · estampas quitadas de {albums.modified_count} álbumes · cargos e historial borrados")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache")
    ap.add_argument("--paises", help="lista separada por comas (nombres de 'paises')")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--descargar", action="store_true")
    g.add_argument("--muestra", action="store_true")
    g.add_argument("--aplicar", action="store_true")
    g.add_argument("--revertir", action="store_true")
    a = ap.parse_args()
    solo = [x.strip() for x in a.paises.split(",")] if a.paises else None
    if a.revertir:
        revertir()
    elif not a.cache:
        sys.exit("--cache es obligatorio")
    elif a.descargar:
        descargar(a.cache, solo)
    elif a.muestra:
        muestra(a.cache, solo)
    else:
        aplicar(a.cache)
