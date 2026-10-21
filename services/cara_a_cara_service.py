"""
Cara a Cara: historial completo de enfrentamientos entre dos países, de todos los mundiales y
fases guardados en 'juegos' (eliminatorias incluidas). Lo usan /cara-a-cara/ y el bloque
"Historial entre ambos" del Scouter (routes/prematch_route.py).

El ganador de cada partido sale de 'resultado.ganador_id' (cubre los definidos por penales);
si no está, del marcador.
"""
import certifi
from collections import defaultdict
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import DESCENDING
from pymongo.mongo_client import MongoClient

from config.settings import MONGODB_URI
from services.fecha_service import formatear_fecha_es

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')


def listar_paises() -> List[dict]:
    """Países para los selectores (id, nombre, bandera), alfabético."""
    return [{"id": p["id"], "nombre": p.get("nombre", "?"), "bandera": p.get("bandera") or ""}
            for p in db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1}).sort("nombre", 1)]


def _ganador(juego: dict) -> Optional[int]:
    res = juego.get("resultado") or {}
    if res.get("ganador_id") is not None and res.get("ganador_lado") in ("L", "V"):
        return res["ganador_id"]
    gl, gv = res.get("goles_local", 0) or 0, res.get("goles_visitante", 0) or 0
    if gl == gv:
        return None
    return (juego.get("equipo_local") or {}).get("id") if gl > gv else (juego.get("equipo_visitante") or {}).get("id")


def obtener_cara_a_cara(pais_a: int, pais_b: int, limite_partidos: int = 20, excluir_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Resumen del historial entre 'pais_a' y 'pais_b' (desde la óptica de A). None si un país no existe.
    'excluir_id': el partido que se está mirando (el detalle recién simulado no debe contarse a sí mismo).
    """
    paises = {p["id"]: p for p in db["paises"].find({"id": {"$in": [pais_a, pais_b]}}, {"id": 1, "nombre": 1, "bandera": 1})}
    if pais_a not in paises or pais_b not in paises or pais_a == pais_b:
        return None

    nombres_fase = {f["id"]: f.get("nombre", "") for f in db["fases"].find({}, {"id": 1, "nombre": 1})}
    anios = {str(m["_id"]): m.get("anio") for m in db["mundiales"].find({}, {"anio": 1})}
    filtro = {"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}, "$or": [
        {"equipo_local.id": pais_a, "equipo_visitante.id": pais_b},
        {"equipo_local.id": pais_b, "equipo_visitante.id": pais_a},
    ]}
    if excluir_id and ObjectId.is_valid(str(excluir_id)):
        filtro["_id"] = {"$ne": ObjectId(str(excluir_id))}
    juegos = list(db["juegos"].find(
        filtro,
        {"equipo_local": 1, "equipo_visitante": 1, "fecha": 1, "tag": 1, "fase_id": 1, "mundial_id": 1, "resultado.goles_local": 1,
         "resultado.goles_visitante": 1, "resultado.penaltis_local": 1, "resultado.penaltis_visitante": 1,
         "resultado.ganador_id": 1, "resultado.ganador_lado": 1, "resultado.goleadores": 1}
    ).sort([("fecha", DESCENDING)]))

    ganados = {pais_a: 0, pais_b: 0}
    empates = 0
    goles = {pais_a: 0, pais_b: 0}
    goleadores = defaultdict(lambda: {"nombre": None, "equipo": None, "jugador_id": None, "pais_id": None, "goles": 0})
    mayor_goleada = None
    partidos = []
    for j in juegos:
        res = j.get("resultado") or {}
        local, visitante = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
        gl, gv = res.get("goles_local", 0) or 0, res.get("goles_visitante", 0) or 0
        goles[local.get("id")] = goles.get(local.get("id"), 0) + gl
        goles[visitante.get("id")] = goles.get(visitante.get("id"), 0) + gv
        ganador = _ganador(j)
        if ganador in ganados:
            ganados[ganador] += 1
        else:
            empates += 1
        if gl != gv and (mayor_goleada is None or abs(gl - gv) > mayor_goleada[0]):
            mayor_goleada = (abs(gl - gv), j)
        id_por_equipo = {local.get("nombre"): local.get("id"), visitante.get("nombre"): visitante.get("id")}
        for g in res.get("goleadores") or []:
            clave = g.get("jugador_id") or g.get("jugador_nombre")
            goleadores[clave].update({"nombre": g.get("jugador_nombre"), "equipo": g.get("equipo"), "jugador_id": g.get("jugador_id"),
                                      "pais_id": id_por_equipo.get(g.get("equipo"))})
            goleadores[clave]["goles"] += g.get("goles", 0) or 0
        pl, pv = res.get("penaltis_local") or 0, res.get("penaltis_visitante") or 0
        partidos.append({
            "id": str(j["_id"]), "fecha": formatear_fecha_es(j.get("fecha")) if j.get("fecha") else "",
            "fase": nombres_fase.get(j.get("fase_id"), ""), "anio_mundial": anios.get(j.get("mundial_id")), "tag": j.get("tag"),
            "local": {"id": local.get("id"), "nombre": local.get("nombre"), "bandera": local.get("bandera") or "", "goles": gl},
            "visitante": {"id": visitante.get("id"), "nombre": visitante.get("nombre"), "bandera": visitante.get("bandera") or "", "goles": gv},
            "penales": f"{pl}-{pv}" if (pl or pv) else None,
            "ganador_id": ganador,
        })

    def _lado(pid):
        p = paises[pid]
        return {"id": pid, "nombre": p.get("nombre"), "bandera": p.get("bandera") or "", "ganados": ganados[pid], "goles": goles.get(pid, 0)}

    total = len(juegos)
    # Racha vigente desde la óptica de A (partidos ordenados del más reciente al más viejo)
    racha = None
    for p in partidos:
        r = "G" if p["ganador_id"] == pais_a else ("P" if p["ganador_id"] == pais_b else "E")
        if racha is None:
            racha = {"tipo": r, "n": 1}
        elif r == racha["tipo"]:
            racha["n"] += 1
        else:
            break
    goleada = None
    if mayor_goleada:
        diferencia, j = mayor_goleada
        goleada = next(p for p in partidos if p["id"] == str(j["_id"]))
        goleada = {**goleada, "diferencia": diferencia}
    return {
        "a": _lado(pais_a), "b": _lado(pais_b), "empates": empates, "total": total,
        "pct_a": round(100 * ganados[pais_a] / total) if total else 0,
        "pct_empate": round(100 * empates / total) if total else 0,
        "pct_b": round(100 * ganados[pais_b] / total) if total else 0,
        "mayor_goleada": goleada, "racha": racha,
        "promedio_goles": round((goles.get(pais_a, 0) + goles.get(pais_b, 0)) / total, 2) if total else 0,
        "ultimo": partidos[0] if partidos else None,
        "goleadores": sorted(goleadores.values(), key=lambda g: g["goles"], reverse=True)[:5],
        "ultimos": partidos[:5],
        "partidos": partidos[:limite_partidos],
    }


def clasicos_destacados(limite: int = 8) -> List[dict]:
    """Los cruces más repetidos de todos los mundiales guardados (para la portada de /cara-a-cara/ sin selección)."""
    pares = defaultdict(lambda: {"partidos": 0, "goles": 0, "fecha": None})
    nombres = {}
    for j in db["juegos"].find({"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}},
                               {"equipo_local": 1, "equipo_visitante": 1, "fecha": 1, "resultado.goles_local": 1, "resultado.goles_visitante": 1}):
        l, v = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
        if l.get("id") is None or v.get("id") is None:
            continue
        clave = tuple(sorted((l["id"], v["id"])))
        nombres[l["id"]], nombres[v["id"]] = l, v
        res = j.get("resultado") or {}
        par = pares[clave]
        par["partidos"] += 1
        par["goles"] += (res.get("goles_local") or 0) + (res.get("goles_visitante") or 0)
        par["fecha"] = max(par["fecha"] or j.get("fecha"), j.get("fecha")) if j.get("fecha") else par["fecha"]
    mejores = sorted(pares.items(), key=lambda kv: (-kv[1]["partidos"], -kv[1]["goles"]))[:limite]
    salida = []
    for (a, b), datos in mejores:
        salida.append({"a": {"id": a, "nombre": nombres[a].get("nombre"), "bandera": nombres[a].get("bandera") or ""},
                       "b": {"id": b, "nombre": nombres[b].get("nombre"), "bandera": nombres[b].get("bandera") or ""},
                       "partidos": datos["partidos"], "goles": datos["goles"]})
    return salida
