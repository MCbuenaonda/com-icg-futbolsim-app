"""Disciplina (lógica pura): qué tarjetas vio cada jugador en un partido y qué sanción le toca. Sin Mongo.

Los eventos traen el NOMBRE del jugador y del equipo (no el id): disciplina_service.py los resuelve contra `jugadores`.
"""
from typing import Dict, List, Optional, Tuple

from config import disciplina as CD

AMARILLA, DOBLE, ROJA = "TARJETA AMARILLA", "DOBLE AMARILLA", "TARJETA ROJA"
MOTIVO = {"roja_directa": "roja directa", "doble_amarilla": "doble amarilla", "acumulacion": "acumulación de amarillas"}


def tarjetas_del_partido(eventos: List[dict]) -> Dict[Tuple[str, str], dict]:
    """{(equipo, jugador): {'amarillas': n sencillas, 'doble': bool, 'roja': bool, 'minuto': m}} de los que vieron tarjeta."""
    salida: Dict[Tuple[str, str], dict] = {}
    for e in eventos or []:
        tipo = e.get("tipo") or ""
        jugadores = e.get("jugadores") or []
        if not jugadores or not e.get("equipo"):
            continue
        kind = DOBLE if DOBLE in tipo else (ROJA if ROJA in tipo else (AMARILLA if AMARILLA in tipo else None))
        if not kind:
            continue
        d = salida.setdefault((e["equipo"], jugadores[0]), {"amarillas": 0, "doble": False, "roja": False, "minuto": e.get("minuto")})
        if kind == AMARILLA:
            d["amarillas"] += 1
        elif kind == DOBLE:
            d["doble"], d["minuto"] = True, e.get("minuto")
        else:
            d["roja"], d["minuto"] = True, e.get("minuto")
    return salida


def aplicar_partido(estado: Optional[dict], t: dict, fase_id: Optional[int]) -> Tuple[dict, Optional[dict]]:
    """estado = {'amarillas': n, 'fase': última fase registrada}; t = tarjetas del jugador en el partido.
    Devuelve (nuevo estado, sanción {'partidos', 'codigo', 'motivo'} o None)."""
    amarillas = int((estado or {}).get("amarillas") or 0)
    ultima_fase = (estado or {}).get("fase") or 0
    if fase_id is not None and fase_id >= CD.FASE_AMNISTIA and ultima_fase < CD.FASE_AMNISTIA:
        amarillas = 0   # amnistía al empezar la eliminación directa
    sancion = None
    if t.get("roja"):
        sancion = {"partidos": CD.PARTIDOS_ROJA_DIRECTA, "codigo": "roja_directa"}
    elif t.get("doble"):
        sancion = {"partidos": CD.PARTIDOS_DOBLE_AMARILLA, "codigo": "doble_amarilla"}
    else:
        amarillas += int(t.get("amarillas") or 0)
        if amarillas >= CD.AMARILLAS_PARA_SUSPENDER:
            amarillas = 0
            sancion = {"partidos": CD.PARTIDOS_ACUMULACION, "codigo": "acumulacion"}
    if sancion:
        sancion["motivo"] = MOTIVO[sancion["codigo"]]
    return {"amarillas": amarillas, "fase": fase_id or ultima_fase}, sancion


def vista(s: Optional[dict]) -> Dict:
    """Una suspensión lista para dibujar."""
    s = s or {}
    return {"motivo": s.get("motivo"), "codigo": s.get("codigo"), "partidos": int(s.get("partidos") or 0), "restantes": int(s.get("restantes") or 0),
            "rival": s.get("rival"), "minuto": s.get("minuto"), "fecha": s.get("fecha")}
