"""
Palmarés: archivo histórico de los Mundiales (/palmares/).

Fuentes: 'mundiales' (anio, pais_id = sede, campeon = id del país campeón, activo) más los
partidos de cada mundial en 'juegos' (por 'mundial_id'): la final (fase 13) da el finalista y el
marcador, el partido por el 3er puesto (fase 12) el tercero, 'resultado.goleadores' el goleador
del torneo. Ojo: restart_mundial borra todo esto; clean_and_update (fin normal de un Mundial) no.
"""
import certifi
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from pymongo.mongo_client import MongoClient

from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

FASE_FINAL = 13
FASE_TERCER_LUGAR = 12


def _ganador_y_perdedor(juego: Optional[dict]):
    if not juego:
        return None, None
    res = juego.get("resultado") or {}
    local, visitante = juego.get("equipo_local") or {}, juego.get("equipo_visitante") or {}
    ganador_id = res.get("ganador_id")
    if ganador_id is None:
        return None, None
    return (local, visitante) if local.get("id") == ganador_id else (visitante, local)


def _marcador(juego: Optional[dict]) -> Optional[str]:
    if not juego:
        return None
    res = juego.get("resultado") or {}
    texto = f"{res.get('goles_local', 0)}-{res.get('goles_visitante', 0)}"
    pl, pv = res.get("penaltis_local") or 0, res.get("penaltis_visitante") or 0
    return texto + (f" ({pl}-{pv} pen.)" if pl or pv else "")


def _goleador(mundial_id: str) -> Optional[dict]:
    res = list(db["juegos"].aggregate([
        {"$match": {"mundial_id": mundial_id, "estado": "finalizado"}},
        {"$unwind": "$resultado.goleadores"},
        {"$group": {"_id": {"id": "$resultado.goleadores.jugador_id", "nombre": "$resultado.goleadores.jugador_nombre",
                            "equipo": "$resultado.goleadores.equipo"}, "goles": {"$sum": "$resultado.goleadores.goles"}}},
        {"$sort": {"goles": -1}}, {"$limit": 1},
    ]))
    return {"nombre": res[0]["_id"].get("nombre"), "equipo": res[0]["_id"].get("equipo"), "goles": res[0]["goles"]} if res else None


def obtener_palmares() -> Dict[str, Any]:
    mundiales = list(db["mundiales"].find({}).sort("anio", -1))
    paises = {p["id"]: {"nombre": p.get("nombre", "?"), "bandera": p.get("bandera") or ""}
              for p in db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1})}
    nombres_fase = {f["id"]: f.get("nombre", "") for f in db["fases"].find({}, {"id": 1, "nombre": 1})}

    ediciones: List[dict] = []
    titulos = Counter()
    finales = Counter()
    for m in mundiales:
        mid = str(m["_id"])
        final = db["juegos"].find_one({"mundial_id": mid, "fase_id": FASE_FINAL, "estado": "finalizado"})
        tercero_juego = db["juegos"].find_one({"mundial_id": mid, "fase_id": FASE_TERCER_LUGAR, "estado": "finalizado"})
        _, finalista = _ganador_y_perdedor(final)
        tercero, _ = _ganador_y_perdedor(tercero_juego)
        stats = list(db["juegos"].aggregate([
            {"$match": {"mundial_id": mid, "estado": "finalizado"}},
            {"$group": {"_id": None, "partidos": {"$sum": 1},
                        "goles": {"$sum": {"$add": [{"$ifNull": ["$resultado.goles_local", 0]}, {"$ifNull": ["$resultado.goles_visitante", 0]}]}},
                        "fase_max": {"$max": "$fase_id"}}},
        ]))
        stats = stats[0] if stats else {"partidos": 0, "goles": 0, "fase_max": None}
        campeon = paises.get(m.get("campeon")) if m.get("campeon") is not None else None
        if campeon:
            titulos[m["campeon"]] += 1
            finales[m["campeon"]] += 1
        if finalista and finalista.get("id") is not None:
            finales[finalista["id"]] += 1
        ediciones.append({
            "anio": m.get("anio"), "activo": bool(m.get("activo")),
            "sede": paises.get(m.get("pais_id")),
            "campeon": campeon,
            "finalista": {"nombre": finalista.get("nombre"), "bandera": finalista.get("bandera") or ""} if finalista else None,
            "tercero": {"nombre": tercero.get("nombre"), "bandera": tercero.get("bandera") or ""} if tercero else None,
            "marcador_final": _marcador(final),
            "id_final": str(final["_id"]) if final else None,
            "goleador": _goleador(mid),
            "partidos": stats["partidos"], "goles": stats["goles"],
            "promedio_goles": round(stats["goles"] / stats["partidos"], 2) if stats["partidos"] else 0,
            "fase_actual": nombres_fase.get(stats.get("fase_max"), "") if m.get("activo") else None,
        })

    tabla_titulos = sorted(
        ({"pais_id": pid, **paises.get(pid, {"nombre": "?", "bandera": ""}), "titulos": titulos[pid], "finales": finales[pid]}
         for pid in set(titulos) | set(finales)),
        key=lambda f: (f["titulos"], f["finales"]), reverse=True
    )
    return {"ediciones": ediciones, "tabla_titulos": tabla_titulos, "total_ediciones": len(ediciones),
            "ediciones_terminadas": sum(1 for e in ediciones if e["campeon"])}
