"""
Asigna las ESPECIALIDADES de los jugadores (config/especialidades.py) al campo PERMANENTE jugadores.especialidades.
restart_mundial no lo toca (como pie_habil). NO toca partidos.

PARIDAD: todas las selecciones reciben el mismo cupo, con el mismo reparto por línea (CUPO_POR_LINEA entre sus 22
jugadores actuales, CUPO_LEYENDAS_POR_LINEA entre sus 11 leyendas): ninguna queda con más especialistas que otra.
Cada selección tiene exactamente un especialista de penales y uno de tiros libres entre los actuales (se respeta al
que ya lo era); los booleanos especialista_penales / especialista_tiros_libres quedan sincronizados (el motor los lee).
Dentro de la selección, cada especialidad va a quien mejor encaja (percentil de sus atributos en su línea) con un
sorteo ponderado y determinístico (semilla = país); máximo MAXIMO_POR_JUGADOR por jugador y nunca repetida.

Uso:
    python asignar_especialidades.py --muestra     # reparto y ejemplos (no toca nada)
    python asignar_especialidades.py --aplicar     # escribe (respaldo en respaldos/)
    python asignar_especialidades.py --revertir    # vuelve al respaldo más reciente
"""
import bisect
import glob
import json
import os
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime

import certifi
from pymongo import MongoClient, UpdateOne

from config import especialidades as CE
from config.fantasy import LINEA_DE_POSICION
from config.settings import MONGODB_URI

db = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())["mundial"]
CARPETA = "respaldos"
CAMPOS = {"id": 1, "nombre": 1, "pais_id": 1, "posicion_id": 1, "leyenda": 1, "especialista_penales": 1,
          "especialista_tiros_libres": 1, "especialidades": 1,
          **{a: 1 for e in CE.ESPECIALIDADES.values() for a in e["atributos"]}}
FIJAS = ("penales", "tiros_libres")   # se reparten aparte: exactamente una de cada por selección


def _puntaje(j: dict, codigo: str) -> float:
    return statistics.mean(float(j.get(a) or 60) for a in CE.ESPECIALIDADES[codigo]["atributos"])


def _percentiles(jugadores: list) -> dict:
    """{(id, codigo): percentil 0..1 del jugador en esa especialidad dentro de su línea (sin leyendas)}."""
    por_linea = defaultdict(list)
    for j in jugadores:
        if not j.get("leyenda"):
            por_linea[LINEA_DE_POSICION.get(j.get("posicion_id"), "MEDIO")].append(j)
    salida = {}
    for linea, js in por_linea.items():
        for codigo, esp in CE.ESPECIALIDADES.items():
            if linea not in esp["lineas"] and codigo not in FIJAS:
                continue
            valores = sorted(_puntaje(j, codigo) for j in js)
            for j in js:
                salida[(j["id"], codigo)] = bisect.bisect_left(valores, _puntaje(j, codigo)) / max(1, len(valores) - 1)
    return salida


def _peso(j: dict, codigo: str, pct: dict, asignadas: dict) -> float:
    ya = asignadas[j["id"]]
    if codigo in ya or len(ya) >= CE.MAXIMO_POR_JUGADOR:
        return 0.0
    p = pct.get((j["id"], codigo), 0.5)   # leyendas: atributos parejos, todas iguales
    return (0.15 + p ** 2) * CE.PESO_POR_CANTIDAD.get(len(ya), 0.05)


def _repartir(jugadores: list, cupos: dict, rng: random.Random, pct: dict, asignadas: dict) -> None:
    """Llena el cupo de cada línea con especialidades de esa línea (sin las fijas), variadas dentro del equipo."""
    usadas = Counter(c for v in asignadas.values() for c in v)
    for linea, cupo in cupos.items():
        del_linea = [j for j in jugadores if LINEA_DE_POSICION.get(j.get("posicion_id"), "MEDIO") == linea]
        ya_en_linea = sum(len(asignadas[j["id"]]) for j in del_linea)
        for _ in range(max(0, cupo - ya_en_linea)):
            posibles = [c for c, e in CE.ESPECIALIDADES.items() if linea in e["lineas"] and c not in FIJAS]
            intentos = 0
            while intentos < 20:
                intentos += 1
                codigo = rng.choices(posibles, weights=[CE.ESPECIALIDADES[c].get("peso", 1.0) / (1 + 2 * usadas[c]) for c in posibles])[0]
                pesos = [_peso(j, codigo, pct, asignadas) for j in del_linea]
                if sum(pesos) > 0:
                    j = rng.choices(del_linea, weights=pesos)[0]
                    asignadas[j["id"]].append(codigo)
                    usadas[codigo] += 1
                    break


def calcular() -> dict:
    """{jugador_id: {especialidades, especialista_penales, especialista_tiros_libres}} para todos los jugadores."""
    jugadores = list(db["jugadores"].find({}, CAMPOS))
    pct = _percentiles(jugadores)
    por_pais = defaultdict(list)
    for j in jugadores:
        por_pais[j.get("pais_id")].append(j)
    salida = {}
    for pais_id, js in sorted(por_pais.items(), key=lambda x: (x[0] is None, x[0] or 0)):
        rng = random.Random(f"especialidades:{pais_id}")
        actuales = [j for j in js if not j.get("leyenda")]
        leyendas = [j for j in js if j.get("leyenda")]
        asignadas = {j["id"]: [] for j in js}
        campo = [j for j in actuales if LINEA_DE_POSICION.get(j.get("posicion_id")) != "PORTERO"]
        # Exactamente un especialista de penales y uno de tiros libres entre los actuales (respeta al que ya lo era)
        for codigo in FIJAS:
            booleano = CE.ESPECIALIDADES[codigo]["booleano"]
            previos = [j for j in campo if j.get(booleano)]
            if previos:
                elegido = max(previos, key=lambda j: _puntaje(j, codigo))
            elif campo:
                elegido = rng.choices(campo, weights=[0.15 + pct.get((j["id"], codigo), 0.5) ** 2 for j in campo])[0]
            else:
                continue
            asignadas[elegido["id"]].append(codigo)
        _repartir(actuales, CE.CUPO_POR_LINEA, rng, pct, asignadas)
        _repartir(leyendas, CE.CUPO_LEYENDAS_POR_LINEA, rng, pct, asignadas)
        for j in js:
            esp = asignadas[j["id"]]
            salida[j["id"]] = {"especialidades": esp, "especialista_penales": "penales" in esp,
                               "especialista_tiros_libres": "tiros_libres" in esp}
    return salida


def muestra() -> None:
    datos = calcular()
    jugadores = {j["id"]: j for j in db["jugadores"].find({}, CAMPOS)}
    por_jugador = Counter(len(d["especialidades"]) for jid, d in datos.items() if not jugadores[jid].get("leyenda"))
    print("especialidades por jugador actual:", dict(sorted(por_jugador.items())))
    por_ley = Counter(len(d["especialidades"]) for jid, d in datos.items() if jugadores[jid].get("leyenda"))
    print("especialidades por leyenda:", dict(sorted(por_ley.items())))
    tot_pais, tot_linea = defaultdict(int), defaultdict(Counter)
    for jid, d in datos.items():
        j = jugadores[jid]
        if not j.get("leyenda"):
            tot_pais[j["pais_id"]] += len(d["especialidades"])
            tot_linea[j["pais_id"]][LINEA_DE_POSICION.get(j.get("posicion_id"))] += len(d["especialidades"])
    print("total por selección (actuales):", Counter(tot_pais.values()))
    distintos = [p for p, c in tot_linea.items() if any(c[l] != n for l, n in CE.CUPO_POR_LINEA.items())]
    print("selecciones con un reparto por línea distinto al cupo:", len(distintos), distintos[:5])
    print("por especialidad:", Counter(c for d in datos.values() for c in d["especialidades"]).most_common())
    # ¿se corresponden con los atributos?
    for codigo in ("definidor", "torre", "regateador", "reflejos"):
        con = [_puntaje(jugadores[jid], codigo) for jid, d in datos.items() if codigo in d["especialidades"] and not jugadores[jid].get("leyenda")]
        linea = CE.ESPECIALIDADES[codigo]["lineas"][0]
        sin = [_puntaje(j, codigo) for j in jugadores.values() if not j.get("leyenda") and LINEA_DE_POSICION.get(j.get("posicion_id")) == linea
               and codigo not in datos[j["id"]]["especialidades"]]
        print(f"  {codigo}: atributos medios {statistics.mean(con):.1f} con la especialidad vs {statistics.mean(sin):.1f} sin ({len(con)} jugadores)")
    previos = [j for j in jugadores.values() if j.get("especialista_penales")]
    print("penalistas de antes que la conservan:", sum(1 for j in previos if "penales" in datos[j["id"]]["especialidades"]), "de", len(previos))
    pais = db["paises"].find_one({"nombre": "México"}, {"id": 1})
    if pais:
        print("ejemplo México:")
        for j in sorted((j for j in jugadores.values() if j.get("pais_id") == pais["id"]), key=lambda j: (bool(j.get("leyenda")), j.get("posicion_id"))):
            if datos[j["id"]]["especialidades"]:
                print(f"   {'(L) ' if j.get('leyenda') else ''}{j['nombre']} [{LINEA_DE_POSICION.get(j.get('posicion_id'))}]: {', '.join(datos[j['id']]['especialidades'])}")


def aplicar() -> None:
    datos = calcular()
    os.makedirs(CARPETA, exist_ok=True)
    respaldo = {str(j["id"]): {"especialidades": j.get("especialidades"), "especialista_penales": j.get("especialista_penales"),
                               "especialista_tiros_libres": j.get("especialista_tiros_libres")}
                for j in db["jugadores"].find({}, {"id": 1, "especialidades": 1, "especialista_penales": 1, "especialista_tiros_libres": 1})}
    ruta = os.path.join(CARPETA, f"especialidades_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(respaldo, f)
    ops = [UpdateOne({"id": jid}, {"$set": d}) for jid, d in datos.items()]
    r = db["jugadores"].bulk_write(ops, ordered=False)
    print(f"{r.modified_count} jugadores actualizados (respaldo en {ruta})")


def revertir() -> None:
    archivos = sorted(glob.glob(os.path.join(CARPETA, "especialidades_*.json")))
    if not archivos:
        sys.exit("No hay respaldo")
    with open(archivos[-1], encoding="utf-8") as f:
        respaldo = json.load(f)
    ops = []
    for jid, d in respaldo.items():
        sets = {k: v for k, v in d.items() if v is not None}
        unset = {k: "" for k, v in d.items() if v is None}
        cambios = {}
        if sets:
            cambios["$set"] = sets
        if unset:
            cambios["$unset"] = unset
        ops.append(UpdateOne({"id": int(jid)}, cambios))
    r = db["jugadores"].bulk_write(ops, ordered=False)
    print(f"Revertido desde {archivos[-1]}: {r.modified_count} jugadores")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar, "--revertir": revertir}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
