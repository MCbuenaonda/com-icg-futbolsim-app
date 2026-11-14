"""Escándalos de marcas (lógica pura). Sin Mongo: services/escandalos_service.py arma los datos y guarda.
Solo marcas ficticias y sus dueños inventados; tono de «crisis de imagen», nunca acusaciones graves.
"""
import random
from typing import Dict, List, Optional

from config import escandalos as CE
from services import prensa as P

TITULARES = {
    1: ["{m} está en el ojo de la tormenta por su última campaña publicitaria.", "Críticas a {m}: su campaña no cayó bien en las redes.", "{m} pide disculpas tras una publicidad que molestó a su público."],
    2: ["{m} retira un producto del mercado tras una oleada de quejas.", "Mala semana para {m}: devoluciones y quejas por fallas de un producto.", "{m} anuncia una revisión de calidad después de las críticas."],
    3: ["Polémica en {m}: las declaraciones de {d}, su dueño, desatan una crisis de imagen.", "{d}, dueño de {m}, queda en el centro de la polémica por sus palabras.",
        "Crisis en {m}: las patrocinadoras toman distancia tras las declaraciones de {d}."],
}
CIERRE = {"sensacionalista": ["¿El principio del fin para {m}?", "Las redes arden."], "analitica": ["Habrá que medir el impacto real en su patrocinio deportivo.", "La reacción de sus patrocinados será clave."],
          "critica": ["Una marca así tiene que dar explicaciones.", "Mala gestión de crisis, otra vez."], "oficialista": ["Conviene esperar a que la marca aclare su posición.", "Hay que dar tiempo a la empresa."],
          "optimista": ["Las crisis también son oportunidades para corregir el rumbo.", "Seguro sale fortalecida."], "popular": ["La afición ya tomó partido.", "En la calle no se habla de otra cosa."]}


def elegir_severidad(rng: random.Random) -> int:
    return rng.choices(list(CE.SEVERIDAD_PESOS), list(CE.SEVERIDAD_PESOS.values()))[0]


def titular(severidad: int, marca: dict, rng: random.Random) -> str:
    dueno = (marca.get("dueno") or {}).get("nombre") or "su dueño"
    return rng.choice(TITULARES[severidad]).format(m=marca["nombre"], d=dueno)


def nota(severidad: int, marca: dict, medio: dict, periodista: dict, rng: random.Random) -> dict:
    """{tono, categoria_tono, titular, texto} de la nota de un medio sobre la crisis."""
    tono = P.tono(-(0.3 + 0.15 * severidad), medio, periodista, False)
    tit = titular(severidad, marca, rng)
    cierre = rng.choice(CIERRE.get(medio.get("linea"), CIERRE["analitica"])).format(m=marca["nombre"])
    return {"tono": tono, "categoria_tono": P.categoria_tono(tono), "titular": tit, "texto": f"{tit} {cierre}"}


def efecto(severidad: int, contagio: bool = False) -> Dict[str, float]:
    f = CE.CONTAGIO if contagio else 1.0
    return {"rebaja": round(CE.REBAJA[severidad] * f, 3), "riesgo_extra": int(round(CE.RIESGO_EXTRA[severidad] * f))}


def ajustar_pago(pago: int, efecto_crisis: Optional[dict], respaldado: bool) -> int:
    """Pago de la ronda con la rebaja de la crisis (la mitad si el CEO respaldó a la marca)."""
    if not efecto_crisis:
        return pago
    rebaja = efecto_crisis["rebaja"] * (CE.RESPALDO_RESIDUO if respaldado else 1.0)
    return max(1, int(round(pago * (1.0 - rebaja))))


def pesos_marcas(marcas: List[dict], activos_por_marca: Dict[int, int], en_crisis: set) -> List[float]:
    """Más patrocinios activos = más probabilidad de crisis (para que el efecto se sienta); las que ya están en crisis, no."""
    return [0.0 if m["id"] in en_crisis else 1.0 + 2.0 * activos_por_marca.get(m["id"], 0) for m in marcas]
