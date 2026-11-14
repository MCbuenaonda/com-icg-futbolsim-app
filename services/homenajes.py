"""Homenajes a leyendas (lógica pura). Sin Mongo; services/homenajes_service.py arma los datos y guarda. Tono respetuoso: nunca se le atribuyen palabras a una leyenda."""
import math
import random
from typing import Dict, List, Optional

from config import homenajes as CH


def pct(fama: float) -> float:
    """Porcentaje de aficionados que suma el homenaje: entre PCT_MIN y PCT_MAX, con la fama comprimida (raíz cuadrada)."""
    f = max(0.0, min(1.0, float(fama or 0)))
    return CH.PCT_MIN + (CH.PCT_MAX - CH.PCT_MIN) * math.sqrt(f)


def elegir(equipos: List[dict], semilla: str) -> Optional[dict]:
    """equipos = [{pais_id, nombre, tope (bool: ya llegó al tope), leyendas: [{id, nombre, fama}]}] de los dos equipos.
    Elige primero el equipo (al azar entre los que no llegaron al tope) y luego la leyenda con peso fama² (las más famosas, más a menudo).
    Devuelve {pais_id, pais, jugador_id, nombre, fama, pct} o None si no hay a quién homenajear."""
    rng = random.Random(semilla)
    posibles = [e for e in equipos if not e.get("tope") and e.get("leyendas")]
    if not posibles:
        return None
    e = rng.choice(posibles)
    ley = rng.choices(e["leyendas"], weights=[0.05 + (l.get("fama") or 0) ** 2 for l in e["leyendas"]])[0]
    return {"pais_id": e["pais_id"], "pais": e["nombre"], "jugador_id": ley["id"], "nombre": ley["nombre"], "fama": round(ley.get("fama") or 0, 3), "pct": round(pct(ley.get("fama")), 4)}


TITULARES = ["Homenaje a {nombre}, leyenda de {pais}, en el {local}-{visita}.", "{pais} recordó a {nombre}: una leyenda que sigue viva en su afición.",
             "El estadio se rindió ante la memoria de {nombre}, símbolo de {pais}."]


def titular(h: dict, local: str, visita: str, rng: random.Random) -> str:
    return rng.choice(TITULARES).format(nombre=h["nombre"], pais=h["pais"], local=local, visita=visita)


def nota(h: dict, delta: int, local: str, visita: str, rng: random.Random) -> str:
    return f"{titular(h, local, visita, rng)} El cariño por su leyenda sumó {delta:,} aficionados a {h['pais']}."
