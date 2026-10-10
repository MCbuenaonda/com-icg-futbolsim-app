"""
Análisis de jugadores: bitácora de partidos (perfil /jugadores/{id}), buscador y comparador
(/jugadores/comparar).

La bitácora sale de 'juegos.resultado.participantes' (ids de los jugadores que jugaron cada
partido), con los goles de 'resultado.goleadores', las atajadas de 'resultado.atajadores' y las
tarjetas de 'resultado.eventos' (por nombre, porque los eventos no guardan el id del jugador).
No hay calificación por partido guardada: el rating solo existe en la simulación.
"""
import certifi
import re
from typing import Any, Dict, List, Optional

from pymongo import DESCENDING
from pymongo.mongo_client import MongoClient

from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

# Atributos del radar (mismos que el perfil de jugador)
ATRIBUTOS_RADAR = [
    ("velocidad", "Velocidad"), ("regate", "Regate"), ("precision_tiro", "Prec. Tiro"),
    ("precision_pase", "Prec. Pase"), ("fuerza_disparo", "Fza. Disparo"), ("resistencia", "Resistencia"),
    ("vision_juego", "Visión"), ("anticipacion", "Anticipación"), ("agresividad", "Agresividad"),
    ("compostura", "Compostura"),
]
# Contadores de carrera para el comparador: (campo, etiqueta, ¿más es mejor?)
CONTADORES_COMPARADOR = [
    ("juegos_jugados", "Partidos jugados", True), ("goles", "Goles", True), ("asistencias", "Asistencias", True),
    ("tiros_puerta", "Tiros al arco", True), ("recuperaciones", "Recuperaciones", True), ("atajadas", "Atajadas", True),
    ("faltas", "Faltas cometidas", False), ("amarilla", "Amarillas", False), ("roja", "Rojas", False),
]
TIPOS_AMARILLA = {"🟨 TARJETA AMARILLA", "🖥️ VAR - TARJETA REVISADA"}
TIPOS_ROJA = {"🟥 TARJETA ROJA", "🟨🟥 DOBLE AMARILLA"}


def obtener_bitacora_jugador(jugador: dict, limite: int = 60) -> Dict[str, Any]:
    """Partidos jugados por 'jugador' (más recientes primero) + totales de la bitácora."""
    jugador_id, nombre, pais_id = jugador.get("id"), jugador.get("nombre"), jugador.get("pais_id")
    nombres_fase = {f["id"]: f.get("nombre", "") for f in db["fases"].find({}, {"id": 1, "nombre": 1})}
    juegos = db["juegos"].find(
        {"estado": "finalizado", "resultado.participantes": jugador_id},
        {"equipo_local": 1, "equipo_visitante": 1, "fecha": 1, "fase_id": 1, "tag": 1,
         "resultado.goles_local": 1, "resultado.goles_visitante": 1, "resultado.ganador_id": 1,
         "resultado.ganador_lado": 1, "resultado.goleadores": 1, "resultado.atajadores": 1,
         "resultado.eventos.tipo": 1, "resultado.eventos.jugadores": 1}
    ).sort([("fecha", DESCENDING)])

    partidos, totales = [], {"partidos": 0, "goles": 0, "atajadas": 0, "amarillas": 0, "rojas": 0, "victorias": 0, "empates": 0, "derrotas": 0}
    for j in juegos:
        res = j.get("resultado") or {}
        local, visitante = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
        es_local = local.get("id") == pais_id
        propio, rival = (local, visitante) if es_local else (visitante, local)
        gf = res.get("goles_local", 0) if es_local else res.get("goles_visitante", 0)
        gc = res.get("goles_visitante", 0) if es_local else res.get("goles_local", 0)
        ganador = res.get("ganador_id") if res.get("ganador_lado") in ("L", "V") else None
        resultado = "V" if ganador == propio.get("id") else ("D" if ganador == rival.get("id") else ("V" if gf > gc else "D" if gf < gc else "E"))
        gol = next((g for g in res.get("goleadores") or [] if g.get("jugador_id") == jugador_id), None)
        ataj = next((a for a in res.get("atajadores") or [] if a.get("jugador_id") == jugador_id), None)
        amarillas = sum(1 for e in res.get("eventos") or [] if e.get("tipo") in TIPOS_AMARILLA and (e.get("jugadores") or [None])[0] == nombre)
        rojas = sum(1 for e in res.get("eventos") or [] if e.get("tipo") in TIPOS_ROJA and (e.get("jugadores") or [None])[0] == nombre)
        fila = {
            "id": str(j["_id"]), "fecha": j.get("fecha"), "fase": nombres_fase.get(j.get("fase_id"), ""),
            "rival": {"nombre": rival.get("nombre"), "bandera": rival.get("bandera") or ""}, "local": es_local,
            "marcador": f"{gf}-{gc}", "resultado": resultado,
            "goles": (gol or {}).get("goles", 0), "entro_de_cambio": bool((gol or {}).get("entro_de_cambio")),
            "detalle_goles": [t for t, c in (("penal", "goles_penal"), ("tiro libre", "goles_tiro_libre"), ("córner", "goles_corner")) if (gol or {}).get(c)],
            "atajadas": (ataj or {}).get("atajadas", 0), "amarillas": amarillas, "rojas": rojas,
        }
        totales["partidos"] += 1
        totales["goles"] += fila["goles"]
        totales["atajadas"] += fila["atajadas"]
        totales["amarillas"] += amarillas
        totales["rojas"] += rojas
        totales[{"V": "victorias", "E": "empates", "D": "derrotas"}[resultado]] += 1
        if len(partidos) < limite:
            partidos.append(fila)
    return {"partidos": partidos, "totales": totales}


def buscar_jugadores(texto: str, limite: int = 15) -> List[dict]:
    """Buscador del comparador: por nombre del jugador (texto escapado, es input del usuario)."""
    texto = (texto or "").strip()
    if len(texto) < 2:
        return []
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1})}
    resultado = []
    for j in db["jugadores"].find({"nombre": {"$regex": re.escape(texto), "$options": "i"}},
                                  {"id": 1, "nombre": 1, "pais_id": 1, "overall": 1}).limit(limite):
        pais = paises.get(j.get("pais_id"), {})
        resultado.append({"id": j["id"], "nombre": j.get("nombre"), "pais": pais.get("nombre", ""),
                          "bandera": pais.get("bandera") or "", "overall": round(j.get("overall") or 0, 1)})
    return resultado


def _ficha(jugador_id: int) -> Optional[dict]:
    j = db["jugadores"].find_one({"id": jugador_id})
    if not j:
        return None
    pais = db["paises"].find_one({"id": j.get("pais_id")}, {"nombre": 1, "bandera": 1}) or {}
    posicion = db["posiciones"].find_one({"id": j.get("posicion_id")}, {"nombre": 1}) or {}
    return {
        "id": j["id"], "nombre": j.get("nombre"), "pais": pais.get("nombre", ""), "bandera": pais.get("bandera") or "",
        "posicion": posicion.get("nombre", ""), "edad": j.get("edad"), "numero": j.get("numero"),
        "overall": round(j.get("overall") or 0, 1), "rendimiento": round(j.get("rendimiento") or 0, 1),
        "pie_habil": j.get("pie_habil"),
        "atributos": [round(j.get(campo) or 0, 1) for campo, _ in ATRIBUTOS_RADAR],
        "contadores": [j.get(campo) or 0 for campo, _, _ in CONTADORES_COMPARADOR],
    }


def comparar_jugadores(a: int, b: int) -> Optional[Dict[str, Any]]:
    ficha_a, ficha_b = _ficha(a), _ficha(b)
    if not ficha_a or not ficha_b:
        return None
    filas = []
    for i, (_, etiqueta, mas_es_mejor) in enumerate(CONTADORES_COMPARADOR):
        va, vb = ficha_a["contadores"][i], ficha_b["contadores"][i]
        mejor = None if va == vb else (("a" if va > vb else "b") if mas_es_mejor else ("a" if va < vb else "b"))
        filas.append({"etiqueta": etiqueta, "a": va, "b": vb, "mejor": mejor})
    return {"a": ficha_a, "b": ficha_b, "filas": filas, "etiquetas_radar": [e for _, e in ATRIBUTOS_RADAR]}
