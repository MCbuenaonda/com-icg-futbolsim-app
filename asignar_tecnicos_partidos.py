"""
Reconstruye la historia de los directores técnicos desde el PRIMER partido del Mundial en curso, como si hubieran
estado siempre: DT inicial de cada selección (sorteado entre sus 5) y, partido por partido en orden cronológico, la
misma decisión de la federación que se usa en el juego (services/tecnicos_service: sumar_partido / decidir_cese /
elegir_reemplazo, semilla = id del partido). Así hay ceses, reemplazos y regresos según los resultados reales.

Escribe:
  - resultado.dt.{local,visita} = {id, nombre} en cada partido jugado (sin eventos nuevos: no se inventan reclamos,
    expulsiones del DT ni ajustes tácticos en partidos que ya se vieron);
  - la colección dt_cargos (cada cargo con su récord real);
  - paises.dt_id (el DT de hoy) y paises.federacion_paciencia.
No toca marcadores, eventos ni estadísticas.

    python asignar_tecnicos_partidos.py --muestra     # informe, no escribe
    python asignar_tecnicos_partidos.py --aplicar     # escribe (respaldo en respaldos/)
    python asignar_tecnicos_partidos.py --revertir    # borra dt_cargos, resultado.dt y paises.dt_id
"""
import gzip
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

from pymongo import UpdateOne

from services import tecnicos_service as T

RAIZ = os.path.dirname(os.path.abspath(__file__))
db = T.db


def _eliminados() -> set:
    return {p["id"] for p in db["paises"].find({}, {"id": 1, "estado": 1}) if str(p.get("estado", "")).startswith("ELIMINADO")}


def calcular():
    bancos = defaultdict(list)
    for d in db["directores_tecnicos"].find({}, {"id": 1, "nombre": 1, "pais_id": 1, "wikis": 1}):
        bancos[d["pais_id"]].append(d)
    if not bancos:
        sys.exit("No hay técnicos: correr agregar_tecnicos.py --aplicar primero.")
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "aficionados": 1})}
    juegos = list(db["juegos"].find({"estado": "finalizado", "resultado": {"$exists": True}},
                                    {"fecha": 1, "hora": 1, "mundial_id": 1, "resultado.id_local": 1, "resultado.id_visitante": 1,
                                     "resultado.goles_local": 1, "resultado.goles_visitante": 1}))
    juegos.sort(key=lambda j: (j.get("fecha") or "", j.get("hora") or "", str(j["_id"])))
    mundial = juegos[0].get("mundial_id") if juegos else None
    eliminados = _eliminados()
    ultimo_partido = {}
    for j in juegos:
        for pid in (j["resultado"]["id_local"], j["resultado"]["id_visitante"]):
            ultimo_partido[pid] = str(j["_id"])

    paciencia = {pid: T.paciencia_para(pid) for pid in paises}
    cargos = defaultdict(list)          # pais_id -> [cargo...], el último es el vigente
    for pid, banco in bancos.items():
        dt = T.elegir_inicial(pid, banco)
        cargos[pid].append(T.nuevo_cargo(pid, dt, "INICIO", None, mundial))
    dt_por_juego = {}
    jugados = Counter()

    for j in juegos:
        res, jid = j["resultado"], str(j["_id"])
        lados = [(res["id_local"], res["id_visitante"], res["goles_local"], res["goles_visitante"], "local"),
                 (res["id_visitante"], res["id_local"], res["goles_visitante"], res["goles_local"], "visita")]
        dt_por_juego[jid] = {}
        for pid, rival, gf, gc, lado in lados:
            if pid not in cargos:
                continue
            cargo = cargos[pid][-1]
            dt_por_juego[jid][lado] = {"id": cargo["dt_id"], "nombre": cargo["dt_nombre"]}
            esperados = T.puntos_esperados(paises.get(pid, {}).get("aficionados"), paises.get(rival, {}).get("aficionados"))
            T.sumar_partido(cargo, gf, gc, esperados, False, jid)
            jugados[pid] += 1
            eliminado = pid in eliminados and ultimo_partido.get(pid) == jid
            if eliminado:
                cargo["evaluado_eliminado"] = True
            if T.decidir_cese(cargo, paciencia[pid], eliminado, jid, pid):
                cargo.update({"hasta_juego": jid, "motivo_fin": "CESE", "cerrado_en_partido": jugados[pid],
                              "cese_por_eliminacion": eliminado, "hasta_fecha_juego": j.get("fecha")})
                nuevo = T.elegir_reemplazo(pid, cargo["dt_id"], bancos[pid], cargos[pid], jugados[pid], jid)
                regreso = any(c["dt_id"] == nuevo["id"] for c in cargos[pid])
                cargos[pid].append({**T.nuevo_cargo(pid, nuevo, "REEMPLAZO", jid, mundial, jugados[pid], j.get("fecha")),
                                    "reemplaza_a": cargo["dt_id"], "regreso": regreso})
    return paises, cargos, dt_por_juego, paciencia, juegos


def muestra():
    paises, cargos, dt_por_juego, _, juegos = calcular()
    conf = {p["id"]: p.get("confederacion_id") for p in db["paises"].find({}, {"id": 1, "confederacion_id": 1})}
    ceses = [c for lista in cargos.values() for c in lista if c["motivo_fin"] == "CESE"]
    regresos = [c for lista in cargos.values() for c in lista if c.get("regreso")]
    por_conf = Counter(conf.get(c["pais_id"]) for c in ceses)
    print(f"Partidos recorridos: {len(juegos)} · selecciones con DT: {len(cargos)}")
    print(f"Ceses: {len(ceses)} ({len(ceses) / max(1, len(cargos)):.2f} por selección) · por eliminación: "
          f"{sum(1 for c in ceses if c.get('cese_por_eliminacion'))} · regresos: {len(regresos)}")
    nombres = {1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC"}
    print("Ceses por confederación:", {nombres.get(k, k): v for k, v in sorted(por_conf.items(), key=lambda x: str(x[0]))})
    sin_cambio = sum(1 for lista in cargos.values() if len(lista) == 1)
    print(f"Selecciones que nunca cambiaron de DT: {sin_cambio}")
    mas = sorted(cargos.items(), key=lambda kv: -len(kv[1]))[:8]
    for pid, lista in mas:
        print(f"  {paises[pid]['nombre']:<22} {len(lista)} técnicos: " + " → ".join(
            f"{c['dt_nombre']} ({c['ganados']}-{c['empatados']}-{c['perdidos']})" for c in lista))
    for c in regresos[:6]:
        print(f"  Regreso: {c['dt_nombre']} vuelve a {paises[c['pais_id']]['nombre']}")


def aplicar():
    if db["dt_cargos"].count_documents({}):
        sys.exit("Ya hay cargos de DT: --revertir primero si querés reconstruirlos.")
    paises, cargos, dt_por_juego, paciencia, _ = calcular()
    os.makedirs(os.path.join(RAIZ, "respaldos"), exist_ok=True)
    archivo = os.path.join(RAIZ, "respaldos", f"tecnicos_partidos_{datetime.now():%Y%m%d_%H%M%S}.json.gz")
    with gzip.open(archivo, "wt", encoding="utf-8") as f:
        json.dump({"juegos": list(dt_por_juego), "paises": list(cargos)}, f)
    docs = [c for lista in cargos.values() for c in lista]
    db["dt_cargos"].insert_many(docs)
    from agregar_tecnicos import _indices
    _indices(db, "dt_cargos", [([("pais_id", 1), ("hasta_juego", 1)], False), ("dt_id", False)])
    ops = [UpdateOne({"_id": __import__("bson").ObjectId(jid)}, {"$set": {"resultado.dt": dt}}) for jid, dt in dt_por_juego.items() if dt]
    for i in range(0, len(ops), 500):
        db["juegos"].bulk_write(ops[i:i + 500])
    db["paises"].bulk_write([UpdateOne({"id": pid}, {"$set": {"dt_id": lista[-1]["dt_id"], "federacion_paciencia": paciencia[pid]}})
                             for pid, lista in cargos.items()])
    print(f"Cargos: {len(docs)} · partidos con DT: {len(ops)} · selecciones: {len(cargos)} · respaldo {archivo}")


def revertir():
    r = db["dt_cargos"].delete_many({})
    j = db["juegos"].update_many({"resultado.dt": {"$exists": True}}, {"$unset": {"resultado.dt": ""}})
    p = db["paises"].update_many({}, {"$unset": {"dt_id": "", "federacion_paciencia": ""}})
    print(f"Cargos borrados: {r.deleted_count} · partidos sin DT: {j.modified_count} · países: {p.modified_count}")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar, "--revertir": revertir}.get(sys.argv[1] if len(sys.argv) > 1 else "",
                                                                            lambda: print(__doc__))()
