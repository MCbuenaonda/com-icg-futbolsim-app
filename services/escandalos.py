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


# --- Cadenas de TV y medios ---------------------------------------------------------------------------------------------------
TITULARES_TV = {
    1: ["{t} recibe críticas por el tono de su última transmisión.", "Polémica menor en {t}: el público no quedó conforme con su cobertura."],
    2: ["{t} pide disculpas tras un error al aire durante una transmisión.", "Fallas técnicas y quejas: mala semana para {t}."],
    3: ["Crisis en {t}: las palabras de {d}, su dueño, desatan una polémica.", "{d}, dueño de {t}, queda en el centro de la crítica y las anunciantes dudan."],
}
TITULARES_MEDIO = {
    1: ["{m} corrige una nota y recibe críticas por el error.", "Cuestionan un titular de {m}: dicen que fue exagerado."],
    2: ["{m} retira una nota tras los reclamos de varios protagonistas.", "Mala semana para {m}: rectificaciones y críticas de los lectores."],
    3: ["Cuestionan la credibilidad de {m} tras una nota que debió retirar.", "Crisis en {m}: {d}, su director, pide disculpas públicas."],
}


def titular_tv(severidad: int, tele: dict, rng: random.Random) -> str:
    dueno = ((tele.get("equipo") or {}).get("dueno") or {}).get("nombre") or "su dueño"
    return rng.choice(TITULARES_TV[severidad]).format(t=tele["nombre"], d=dueno)


def titular_medio(severidad: int, medio: dict, rng: random.Random) -> str:
    director = ((medio.get("equipo") or {}).get("director") or {}).get("nombre") or "su director"
    return rng.choice(TITULARES_MEDIO[severidad]).format(m=medio["nombre"], d=director)


def nota_otros(severidad: int, titular_texto: str, nombre: str, medio: dict, periodista: dict, rng: random.Random) -> dict:
    tono = P.tono(-(0.25 + 0.12 * severidad), medio, periodista, False)
    cierre = rng.choice(CIERRE.get(medio.get("linea"), CIERRE["analitica"])).format(m=nombre)
    return {"tono": tono, "categoria_tono": P.categoria_tono(tono), "titular": titular_texto, "texto": f"{titular_texto} {cierre}"}


def tv_efecto(severidad: int, rival: bool = False) -> dict:
    return {"rebaja": 0.0, "bono": CE.TV_BONO_RIVAL[severidad]} if rival else {"rebaja": CE.TV_REBAJA[severidad], "bono": 0.0}


def ajustar_tv(monto: int, efecto_tv: Optional[dict]) -> int:
    """Pago de una cadena con su rebaja (si está en crisis) o su bono (si es rival de una en crisis)."""
    if not efecto_tv:
        return monto
    return max(1, int(round(monto * (1.0 - efecto_tv["rebaja"] + efecto_tv["bono"]))))


# --- Crisis de imagen deportivas (jugadores, DTs y árbitros) ----------------------------------------------------------------
TITULARES_JUGADOR = {
    "roja": ["{j} ve la roja y {eq} paga caro la expulsión.", "Expulsión de {j}: {eq} se queda con diez y la jugada divide opiniones.",
             "{j} pide disculpas tras su expulsión ante {rival}."],
    "doble": ["Doble amarilla para {j}: {eq} se queda con diez.", "{j} se va expulsado por acumulación de amonestaciones y {eq} lo lamenta.",
              "{eq} lamenta la expulsión de {j} ante {rival}."],
    "frustrado": ["{j} no esconde su frustración tras la derrota de {eq}: las redes se dividen.", "Gesto de fastidio de {j} tras el partido ante {rival} genera debate.",
                  "{j} genera discusión por sus palabras después de caer ante {rival}."],
}
TITULARES_DT = {
    "goleada": ["Dudas en torno a {j}: la goleada ante {rival} reabre el debate en {eq}.", "{j} se enfrenta a la prensa tras la derrota ante {rival}.",
                "Críticas a {j} después del {gf}-{gc} de {eq}."],
    "presion": ["{j}, bajo presión: la afición de {eq} ya pide cambios.", "Se agota la paciencia con {j} en {eq}.", "Aprietan a {j}: {eq} necesita reaccionar."],
}
TITULARES_ARBITRO = {"reincidente": ["{j}, bajo la lupa: otra polémica y ya son {n} en el torneo.", "Cuestionan a {j} por su manejo de los partidos: {n} polémicas en el torneo.",
                                     "Vuelve la polémica con {j}: los equipos piden más cuidado."]}
TONO_DEPORTIVO_BASE = 0.35   # tono de una nota de escándalo deportivo: -(base + paso x severidad)
TONO_DEPORTIVO_PASO = 0.15


def titular_deportivo(tipo: str, motivo: str, c: dict, rng: random.Random) -> str:
    banco = {"jugador": TITULARES_JUGADOR, "dt": TITULARES_DT, "arbitro": TITULARES_ARBITRO}[tipo][motivo]
    ctx = c.get("ctx") or {}
    return rng.choice(banco).format(j=c["nombre"], eq=ctx.get("eq", ""), rival=ctx.get("rival", ""), gf=ctx.get("gf", ""), gc=ctx.get("gc", ""), n=ctx.get("n", ""))


def nota_deportiva(severidad: int, titular_texto: str, nombre: str, medio: dict, periodista: dict, es_propio: bool, rng: random.Random) -> dict:
    tono = P.tono(-(TONO_DEPORTIVO_BASE + TONO_DEPORTIVO_PASO * severidad), medio, periodista, es_propio)
    cierre = rng.choice(CIERRE.get(medio.get("linea"), CIERRE["analitica"])).format(m=nombre)
    return {"tono": tono, "categoria_tono": P.categoria_tono(tono), "titular": titular_texto, "texto": f"{titular_texto} {cierre}"}
