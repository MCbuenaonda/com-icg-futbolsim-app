"""
Historial de cada DT por esquema (directores_tecnicos.esquemas + ultimo_esquema), reconstruido desde los partidos ya
jugados: para que la decisión «repetir lo que le funcionó» (tecnicos.elegir_esquema) arranque con datos.
NO toca partidos, eventos ni marcadores. Después, cada partido nuevo suma solo (tecnicos_service.registrar_partido).

Uso:
    python asignar_esquemas_tecnicos.py --muestra     # qué se escribiría (no toca nada)
    python asignar_esquemas_tecnicos.py --aplicar     # recalcula y escribe (respaldo en respaldos/)
    python asignar_esquemas_tecnicos.py --revertir    # vuelve al respaldo más reciente

Recalcular es idempotente: siempre cuenta todos los partidos jugados con DT (resultado.dt) y su esquema inicial
(resultado.tactica_local / tactica_visita).
"""
import glob
import json
import os
import sys
from collections import defaultdict
from datetime import datetime

import certifi
from pymongo import MongoClient, UpdateOne

from config.settings import MONGODB_URI

db = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())["mundial"]
CARPETA = "respaldos"


def calcular() -> dict:
    esquemas = defaultdict(lambda: defaultdict(lambda: {"pj": 0, "pts": 0, "gf": 0, "gc": 0}))
    ultimo = {}
    filtro = {"estado": "finalizado", "resultado.dt": {"$exists": True}}
    proy = {"fecha": 1, "hora": 1, "resultado.dt": 1, "resultado.tactica_local": 1, "resultado.tactica_visita": 1,
            "equipo_local.tactica": 1, "equipo_visitante.tactica": 1, "resultado.goles_local": 1, "resultado.goles_visitante": 1}
    for j in db["juegos"].find(filtro, proy).sort([("fecha", 1), ("hora", 1)]):
        r = j["resultado"]
        for lado, esq, gf, gc in (("local", r.get("tactica_local") or (j.get("equipo_local") or {}).get("tactica"), r.get("goles_local", 0), r.get("goles_visitante", 0)),
                                  ("visita", r.get("tactica_visita") or (j.get("equipo_visitante") or {}).get("tactica"), r.get("goles_visitante", 0), r.get("goles_local", 0))):
            dt = ((r.get("dt") or {}).get(lado) or {}).get("id")
            if not dt or not esq:
                continue
            e = esquemas[dt][esq]
            e["pj"] += 1
            e["pts"] += 3 if gf > gc else (1 if gf == gc else 0)
            e["gf"] += gf or 0
            e["gc"] += gc or 0
            ultimo[dt] = esq
    return {dt: {"esquemas": {k: dict(v) for k, v in d.items()}, "ultimo_esquema": ultimo.get(dt)} for dt, d in esquemas.items()}


def muestra() -> None:
    datos = calcular()
    print(f"{len(datos)} técnicos con partidos")
    for dt, d in list(datos.items())[:8]:
        nombre = (db["directores_tecnicos"].find_one({"id": dt}, {"nombre": 1}) or {}).get("nombre")
        print(f"  {nombre}: último {d['ultimo_esquema']} · " + ", ".join(f"{k} {v['pj']}pj {v['pts']}pts" for k, v in d["esquemas"].items()))


def aplicar() -> None:
    datos = calcular()
    os.makedirs(CARPETA, exist_ok=True)
    respaldo = {str(t["id"]): {"esquemas": t.get("esquemas"), "ultimo_esquema": t.get("ultimo_esquema")}
                for t in db["directores_tecnicos"].find({}, {"id": 1, "esquemas": 1, "ultimo_esquema": 1})}
    ruta = os.path.join(CARPETA, f"esquemas_tecnicos_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(respaldo, f)
    ops = [UpdateOne({"id": dt}, {"$set": d}) for dt, d in datos.items()]
    if ops:
        r = db["directores_tecnicos"].bulk_write(ops)
        print(f"{r.modified_count} técnicos actualizados (respaldo en {ruta})")


def revertir() -> None:
    archivos = sorted(glob.glob(os.path.join(CARPETA, "esquemas_tecnicos_*.json")))
    if not archivos:
        sys.exit("No hay respaldo")
    with open(archivos[-1], encoding="utf-8") as f:
        respaldo = json.load(f)
    ops = []
    for dt, d in respaldo.items():
        if d.get("esquemas") is None:
            ops.append(UpdateOne({"id": int(dt)}, {"$unset": {"esquemas": "", "ultimo_esquema": ""}}))
        else:
            ops.append(UpdateOne({"id": int(dt)}, {"$set": d}))
    r = db["directores_tecnicos"].bulk_write(ops)
    print(f"Revertido desde {archivos[-1]}: {r.modified_count} técnicos")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar, "--revertir": revertir}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
