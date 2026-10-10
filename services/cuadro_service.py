"""
Cuadro de eliminación directa del Mundial activo (fases 8-13), para /cuadro/.

Cómo se reconstruye el árbol: cada ronda guarda sus partidos con 'fase_id' y 'grupo' ("Grupo A",
"Grupo B", ...), y services/grupos_service.py arma la ronda siguiente con pares de letras
consecutivas -- (A,B) -> A, (C,D) -> B, ... -- así que la llave i de una ronda la juegan los
ganadores de las llaves 2i y 2i+1 de la anterior. Con eso se dibuja el cuadro completo, incluidas
las llaves todavía sin definir ("Ganador 16vos A / B").
"""
import certifi
from typing import Any, Dict, List, Optional

from pymongo.mongo_client import MongoClient

from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

# (fase_id, nombre, nombre corto, cantidad de llaves) -- el 3er puesto (fase 12) va aparte
RONDAS = [
    (8, "16vos de Final", "16vos", 16),
    (9, "Octavos de Final", "8vos", 8),
    (10, "Cuartos de Final", "4tos", 4),
    (11, "Semifinales", "Semis", 2),
    (13, "Gran Final", "Final", 1),
]
FASE_TERCER_LUGAR = 12


def _letra(i: int) -> str:
    return chr(ord("A") + i)


def _resumen_llave(juego: dict) -> dict:
    res = juego.get("resultado") or {}
    local, visitante = juego.get("equipo_local") or {}, juego.get("equipo_visitante") or {}
    jugado = juego.get("estado") == "finalizado" and bool(res)
    pl, pv = res.get("penaltis_local") or 0, res.get("penaltis_visitante") or 0
    ganador = res.get("ganador_id") if jugado else None
    return {
        "id": str(juego["_id"]), "jugado": jugado, "fecha": juego.get("fecha"),
        "local": {"id": local.get("id"), "nombre": local.get("nombre"), "bandera": local.get("bandera") or "",
                  "goles": res.get("goles_local") if jugado else None},
        "visitante": {"id": visitante.get("id"), "nombre": visitante.get("nombre"), "bandera": visitante.get("bandera") or "",
                      "goles": res.get("goles_visitante") if jugado else None},
        "penales": f"{pl}-{pv}" if jugado and (pl or pv) else None,
        "ganador_id": ganador,
    }


def obtener_cuadro() -> Dict[str, Any]:
    mundial = db["mundiales"].find_one({"activo": True})
    if not mundial:
        return {"hay_datos": False, "rondas": [], "tercer_lugar": None, "campeon": None}

    juegos = list(db["juegos"].find(
        {"mundial_id": str(mundial["_id"]), "fase_id": {"$in": [r[0] for r in RONDAS] + [FASE_TERCER_LUGAR]}},
        {"equipo_local": 1, "equipo_visitante": 1, "fase_id": 1, "grupo": 1, "estado": 1, "fecha": 1,
         "resultado.goles_local": 1, "resultado.goles_visitante": 1, "resultado.penaltis_local": 1,
         "resultado.penaltis_visitante": 1, "resultado.ganador_id": 1}
    ))
    por_llave = {}
    for j in juegos:
        letra = (j.get("grupo") or "").replace("Grupo", "").strip()[:1]
        por_llave[(j.get("fase_id"), letra)] = _resumen_llave(j)

    rondas: List[dict] = []
    for idx, (fase_id, nombre, corto, cantidad) in enumerate(RONDAS):
        llaves = []
        for i in range(cantidad):
            llave = por_llave.get((fase_id, _letra(i)))
            if not llave:
                # Todavía sin definir: quiénes la juegan, según la ronda anterior
                if idx == 0:
                    pendiente = ("Clasificado de grupos", "Clasificado de grupos")
                else:
                    anterior = RONDAS[idx - 1][2]
                    pendiente = (f"Ganador {anterior} {_letra(2 * i)}", f"Ganador {anterior} {_letra(2 * i + 1)}")
                llave = {"id": None, "jugado": False, "pendiente": pendiente}
            llave["letra"] = _letra(i)
            llaves.append(llave)
        rondas.append({"fase_id": fase_id, "nombre": nombre, "llaves": llaves})

    final = por_llave.get((13, "A"))
    campeon = None
    if final and final["jugado"] and final["ganador_id"] is not None:
        campeon = final["local"] if final["local"]["id"] == final["ganador_id"] else final["visitante"]

    return {
        "hay_datos": bool(juegos),
        "anio": mundial.get("anio"),
        "rondas": rondas,
        "tercer_lugar": por_llave.get((FASE_TERCER_LUGAR, "A")),
        "campeon": campeon,
    }
