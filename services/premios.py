"""Premios del Mundial (lógica pura): mérito de los candidatos y votación del jurado de periodistas. Sin Mongo; determinístico (semilla = Mundial + categoría + medio)."""
import random
import statistics
from typing import Dict, List, Optional

from config import premios as CP
from services import prensa as P


def z_scores(valores: List[float]) -> List[float]:
    if len(valores) < 2:
        return [0.0 for _ in valores]
    media, sd = statistics.mean(valores), statistics.pstdev(valores) or 1.0
    return [(v - media) / sd for v in valores]


def merito_jugador(c: dict) -> float:
    """Calificación media de la Copa + goles por partido (todos) ."""
    n = max(1, c["partidos"])
    return c["rating"] + 0.30 * c["goles"] / n


def merito_portero(c: dict) -> float:
    n = max(1, c["partidos"])
    return c["rating"] + 0.10 * c["atajadas"] / n + 0.45 * c["vallas"] / n


def merito_tecnico(c: dict) -> float:
    n = max(1, c["partidos"])
    return c["puntos"] / n + 0.45 * c["dif"] / n + 0.35 * max(0, c["fase_max"] - CP.FASE_COPA)


def merito_arbitro(c: dict) -> float:
    n = max(1, c["partidos"])
    return 3.0 + 0.10 * c["partidos"] - 1.2 * c["polemicas"] / n + 0.02 * (c.get("reputacion") or 0)


MERITO = {"jugador": merito_jugador, "portero": merito_portero, "joven": merito_jugador, "tecnico": merito_tecnico, "arbitro": merito_arbitro}


def candidatos(categoria: str, pool: List[dict]) -> List[dict]:
    """Los CP.BOLETA con más mérito (con el mínimo de partidos), cada uno con su `merito`."""
    minimo = CP.MIN_PARTIDOS[categoria]
    elegibles = [c for c in pool if c["partidos"] >= minimo] or [c for c in pool if c["partidos"] >= 1]
    for c in elegibles:
        c["merito"] = round(MERITO[categoria](c), 3)
    return sorted(elegibles, key=lambda c: -c["merito"])[:CP.BOLETA]


def votar(categoria: str, cands: List[dict], medios: List[dict], semilla: str) -> Dict:
    """Cada medio vota con UN periodista: top 3 con puntos 3-2-1. Devuelve {puntos, primeros, boletas, patriotas, ...}."""
    if not cands:
        return {"puntos": {}, "primeros": {}, "votantes": 0, "patriotas": 0, "boletas": []}
    zm = dict(zip([c["id"] for c in cands], z_scores([c["merito"] for c in cands])))
    zg = dict(zip([c["id"] for c in cands], z_scores([c.get("goles", 0) / max(1, c["partidos"]) for c in cands])))
    zr = dict(zip([c["id"] for c in cands], z_scores([c.get("rating", c["merito"]) for c in cands])))
    puntos: Dict[int, int] = {c["id"]: 0 for c in cands}
    primeros: Dict[int, int] = {c["id"]: 0 for c in cands}
    patriotas, boletas = 0, []
    for medio in medios:
        rng = random.Random(f"{semilla}:{categoria}:{medio['id']}")
        per = rng.choice(medio["equipo"]["periodistas"])
        util = {}
        for c in cands:
            u = zm[c["id"]] + rng.gauss(0, CP.RUIDO)
            propio = medio.get("pais_id") is not None and medio.get("pais_id") == c.get("pais_id")
            if propio:
                u += CP.SESGO_PATRIOTA if per.get("sesgo") == "patriota" else (CP.SESGO_CRITICO if per.get("sesgo") == "critico" else 0.0)
                if medio.get("linea") == "oficialista":
                    u += 0.2
            linea = medio.get("linea")
            if linea == "sensacionalista":
                u += CP.SESGO_LINEA * zg[c["id"]]
            elif linea == "analitica":
                u += CP.SESGO_LINEA * zr[c["id"]]
            util[c["id"]] = u
        orden = sorted(util, key=lambda i: -util[i])[:len(CP.PUNTOS_VOTO)]
        for pts, cid in zip(CP.PUNTOS_VOTO, orden):
            puntos[cid] += pts
        primeros[orden[0]] += 1
        if next(c for c in cands if c["id"] == orden[0]).get("pais_id") == medio.get("pais_id") and medio.get("pais_id") is not None:
            patriotas += 1
        boletas.append({"medio_id": medio["id"], "primero": orden[0]})
    return {"puntos": puntos, "primeros": primeros, "votantes": len(medios), "patriotas": patriotas, "boletas": boletas}


def resultado(categoria: str, cands: List[dict], votacion: Dict) -> Optional[dict]:
    if not cands:
        return None
    orden = sorted(cands, key=lambda c: (-votacion["puntos"].get(c["id"], 0), -c["merito"]))
    ganador = orden[0]
    curiosidades = []
    n = votacion["votantes"]
    if n and votacion["primeros"][ganador["id"]] / n >= 0.6:
        curiosidades.append(f"Ganó con holgura: {votacion['primeros'][ganador['id']]} de {n} medios lo pusieron primero.")
    elif n and len(orden) > 1 and votacion["puntos"][ganador["id"]] - votacion["puntos"][orden[1]["id"]] <= max(3, n // 25):
        curiosidades.append(f"Final cerrado: ganó por {votacion['puntos'][ganador['id']] - votacion['puntos'][orden[1]['id']]} puntos sobre {orden[1]['nombre']}.")
    mejor_merito = max(cands, key=lambda c: c["merito"])
    if mejor_merito["id"] != ganador["id"]:
        curiosidades.append(f"El jurado se apartó de los números: {mejor_merito['nombre']} tenía el mejor rendimiento.")
    if n and votacion["patriotas"]:
        curiosidades.append(f"{votacion['patriotas']} medios votaron primero por alguien de su país.")
    return {"categoria": categoria, "ganador": _pub(ganador, votacion), "finalistas": [_pub(c, votacion) for c in orden[1:3]], "votantes": n,
            "curiosidades": curiosidades}


def _pub(c: dict, votacion: Dict) -> dict:
    return {"id": c["id"], "nombre": c["nombre"], "pais_id": c.get("pais_id"), "puntos": votacion["puntos"].get(c["id"], 0),
            "primeros": votacion["primeros"].get(c["id"], 0), "merito": c["merito"], "partidos": c["partidos"]}
