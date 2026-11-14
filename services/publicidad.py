"""Publicidad en las transmisiones (lógica pura). Sin Mongo; corporativo_tv_service._publicidad arma los datos y cobra."""
import math
import random
from typing import Dict, List, Optional

from config import publicidad as CP


def audiencia(fase_id: Optional[int], clasico: bool, af_a: float, af_b: float) -> float:
    """Multiplicador de audiencia del partido (0,7 a 2,5): la fase, si es un Clásico y la popularidad de las dos selecciones."""
    fase = CP.AUDIENCIA_FASE["final"] if (fase_id or 0) >= CP.FASE_FINAL else (CP.AUDIENCIA_FASE["eliminacion"] if (fase_id or 0) >= CP.FASE_ELIMINACION else CP.AUDIENCIA_FASE["grupos"])
    pop = math.sqrt(max(1.0, af_a) * max(1.0, af_b)) / CP.AFICIONADOS_BASE
    pop = max(CP.POPULARIDAD_RANGO[0], min(CP.POPULARIDAD_RANGO[1], pop))
    a = fase * (CP.AUDIENCIA_CLASICO if clasico else 1.0) * pop
    return round(max(CP.AUDIENCIA_TOPE[0], min(CP.AUDIENCIA_TOPE[1], a)), 3)


def elegibles(marcas: List[dict], cadena_pais_id: int, cadena_confederacion_id: Optional[int]) -> List[dict]:
    """Marcas que pueden comprar espacio en esa cadena: globales, continentales de su confederación y locales de su país."""
    out = []
    for m in marcas:
        al = m.get("alcance")
        if al == "global" or (al == "continental" and m.get("confederacion_id") is not None and m.get("confederacion_id") == cadena_confederacion_id) \
                or (al == "local" and m.get("pais_id") == cadena_pais_id):
            out.append(m)
    return out


def elegir_anunciantes(marcas: List[dict], en_crisis: set, rivales_de_crisis: set, rng: random.Random) -> List[dict]:
    """Hasta ESPACIOS marcas distintas (y de rubros distintos); las que están en crisis no compran y las rivales de una en crisis compran más."""
    pool = [m for m in marcas if m["id"] not in en_crisis]
    elegidas: List[dict] = []
    rubros = set()
    while pool and len(elegidas) < CP.ESPACIOS:
        pesos = [CP.PESO_NIVEL_MARCA.get(m.get("nivel", 1), 1.0) * (CP.BONO_RIVAL_DE_CRISIS if m["id"] in rivales_de_crisis else 1.0) for m in pool]
        m = rng.choices(pool, weights=pesos)[0]
        pool.remove(m)
        if m["rubro"] in rubros:
            continue
        rubros.add(m["rubro"])
        elegidas.append(m)
    return elegidas


def precio_espacio(base: float, aud: float, marca: dict) -> int:
    """Lo que paga una marca por UN espacio: una parte de lo esperado por partido, por la audiencia y el nivel de la marca."""
    return int(round(base / CP.ESPACIOS * aud * CP.FACTOR_MARCA.get(marca.get("nivel", 1), 1.0)))


def cobro(anunciantes: List[dict], base: float, aud: float) -> Dict:
    """{anunciantes: [{marca_id, nombre, monto}], total, participacion} del partido."""
    filas = [{"marca_id": m["id"], "nombre": m["nombre"], "monto": precio_espacio(base, aud, m)} for m in anunciantes]
    total = sum(f["monto"] for f in filas)
    return {"anunciantes": filas, "total": total, "participacion": int(round(total * CP.PARTICIPACION))}
