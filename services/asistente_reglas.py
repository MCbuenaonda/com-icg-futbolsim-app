"""
Lógica pura del asistente "El Profe" (sin Mongo): prioridad de cada consejo, corte por nivel, recorte del detalle
según lo que se pagó y las frases del Profe. Reglas en config/asistente.py.

Un consejo es un dict:
  {"clave", "modulo", "tipo": URGENTE|OPORTUNIDAD|GRATIS, "titulo", "texto", "porque": [str], "numeros": [str],
   "url", "cta", "valor": int|None (pts estimados), "confianza": alta|media|baja, "riesgo": bajo|medio|alto,
   "urgencia": 0-100, "nivel_minimo": VISTAZO|ANALISIS|PROFUNDO, "pais_id"?, "bandera"?, "jugador_id"?}
"""
from typing import Dict, List, Sequence, Tuple

from config.asistente import (BONO_URGENTE, EMPATE, ESCALA_PODER, FAVORITO_GANA, MODULOS_ASISTENTE, NIVELES_ASISTENTE,
                              ORDEN_NIVELES, PESO_CONFIANZA, PUNTOS_POR_URGENCIA)


# ==========================================
# Modelo de partido (conservador, ver config/asistente.py)
# ==========================================
def probabilidades_partido(poder_local: float, poder_visita: float) -> Tuple[float, float, float]:
    """(gana local, empate, gana visita) a partir del 'poder' de cada uno."""
    diferencia = (poder_visita or 0.0) - (poder_local or 0.0)
    try:
        p_local = 1.0 / (1.0 + 10 ** (diferencia / ESCALA_PODER))
    except OverflowError:
        p_local = 0.0 if diferencia > 0 else 1.0
    x = min(1.0, abs(p_local - 0.5) / 0.49)
    favorito = FAVORITO_GANA[0] + FAVORITO_GANA[1] * x
    empate = EMPATE[0] + EMPATE[1] * x
    otro = max(0.0, 1.0 - favorito - empate)
    return (favorito, empate, otro) if p_local >= 0.5 else (otro, empate, favorito)


def mejor_pronostico(probs: Tuple[float, float, float]) -> Tuple[str, float]:
    """El pronóstico de quiniela más probable: ('LOCAL'|'EMPATE'|'VISITA', probabilidad)."""
    return max(zip(("LOCAL", "EMPATE", "VISITA"), probs), key=lambda t: t[1])


def distribucion_aciertos(probs: Sequence[float]) -> List[float]:
    """P(exactamente k aciertos) para pronósticos independientes con probabilidad probs[i] cada uno."""
    dist = [1.0]
    for p in probs:
        nueva = [0.0] * (len(dist) + 1)
        for k, q in enumerate(dist):
            nueva[k] += q * (1 - p)
            nueva[k + 1] += q * p
        dist = nueva
    return dist


def valor_esperado_quiniela(probs: Sequence[float], costo: int, reglas_premio: List[dict]) -> Tuple[float, float]:
    """(valor esperado neto, probabilidad de cobrar algún premio) de un boleto."""
    dist = distribucion_aciertos(probs)
    premio = {r["aciertos_requeridos"]: r["premio_puntos"] for r in reglas_premio}
    esperado = sum(q * premio.get(k, 0) for k, q in enumerate(dist))
    cobra = sum(q for k, q in enumerate(dist) if premio.get(k))
    return esperado - costo, cobra


def confianza_por_prob(p: float) -> str:
    return "alta" if p >= 0.6 else ("media" if p >= 0.4 else "baja")


def orden_nivel(codigo: str) -> int:
    return ORDEN_NIVELES.index(codigo) if codigo in ORDEN_NIVELES else -1


def prioridad(consejo: dict) -> float:
    """valor esperado × confianza + urgencia; lo URGENTE siempre primero."""
    base = (consejo.get("valor") or 0) * PESO_CONFIANZA.get(consejo.get("confianza"), 0.5)
    base += (consejo.get("urgencia") or 0) * PUNTOS_POR_URGENCIA
    if consejo.get("tipo") == "URGENTE":
        base += BONO_URGENTE
    return round(base, 1)


def _recortar_detalle(consejo: dict, detalle: str) -> dict:
    """El Vistazo dice qué y por qué; los números (probabilidad, ganancia) se pagan desde el Análisis."""
    c = dict(consejo)
    if detalle == "basico":
        c["numeros"], c["valor"] = [], None
    if detalle != "completo":
        c.pop("riesgo", None)
    return c


def seleccionar(consejos: List[dict], nivel: str) -> dict:
    """
    Arma el informe de un nivel: lo GRATIS aparte (no ocupa cupo), los consejos visibles ordenados por prioridad y
    cortados en max_consejos, y lo que quedó afuera contado por nivel (para el "el Informe profundo encontró N más").
    """
    cfg = NIVELES_ASISTENTE[nivel]
    n = orden_nivel(nivel)
    for c in consejos:
        c["prioridad"] = prioridad(c)
    visibles = [c for c in consejos if orden_nivel(c.get("nivel_minimo", "VISTAZO")) <= n]
    gratis = sorted((c for c in visibles if c["tipo"] == "GRATIS"), key=lambda c: -c["prioridad"])
    pagos = sorted((c for c in visibles if c["tipo"] != "GRATIS"), key=lambda c: -c["prioridad"])
    elegidos, sobrantes = pagos[:cfg["max_consejos"]], pagos[cfg["max_consejos"]:]

    # Lo que vería subiendo de nivel: los de nivel superior + los que no entraron por cupo
    bloqueados: Dict[str, dict] = {}
    for c in consejos:
        nm = c.get("nivel_minimo", "VISTAZO")
        if c["tipo"] != "GRATIS" and orden_nivel(nm) > n:
            b = bloqueados.setdefault(nm, {"nivel": nm, "nombre": NIVELES_ASISTENTE[nm]["nombre"], "cantidad": 0, "modulos": []})
            b["cantidad"] += 1
            nombre_mod = MODULOS_ASISTENTE.get(c["modulo"], {}).get("nombre", c["modulo"])
            if nombre_mod not in b["modulos"]:
                b["modulos"].append(nombre_mod)
    if sobrantes and n < len(ORDEN_NIVELES) - 1:
        sig = ORDEN_NIVELES[n + 1]
        b = bloqueados.setdefault(sig, {"nivel": sig, "nombre": NIVELES_ASISTENTE[sig]["nombre"], "cantidad": 0, "modulos": []})
        b["cantidad"] += min(len(sobrantes), NIVELES_ASISTENTE[sig]["max_consejos"] - cfg["max_consejos"])

    detalle = cfg["detalle"]
    elegidos = [_recortar_detalle(c, detalle) for c in elegidos]
    gratis = [_recortar_detalle(c, detalle) for c in gratis]
    valor_total = sum(c.get("valor") or 0 for c in elegidos if c["tipo"] == "OPORTUNIDAD") if detalle != "basico" else None
    return {
        "nivel": nivel, "consejos": elegidos, "gratis": gratis,
        "bloqueados": [bloqueados[k] for k in ORDEN_NIVELES if k in bloqueados],
        "resumen": {"consejos": len(elegidos), "urgentes": sum(1 for c in elegidos if c["tipo"] == "URGENTE"),
                    "oportunidades": sum(1 for c in elegidos if c["tipo"] == "OPORTUNIDAD"), "gratis": len(gratis),
                    "valor_potencial": valor_total},
        "plan": plan_jornada(elegidos) if detalle == "completo" else [],
    }


def plan_jornada(consejos: List[dict]) -> List[str]:
    """Los primeros pasos en orden: lo urgente, después lo de mayor valor esperado."""
    return [c["titulo"] for c in consejos[:4]]


def frase_profe(resumen: dict, nombre: str = "") -> str:
    """El globo del Profe al terminar el escaneo."""
    u, o, g = resumen.get("urgentes", 0), resumen.get("oportunidades", 0), resumen.get("gratis", 0)
    quien = f"{nombre}, " if nombre else ""
    if not (u or o or g):
        return f"{quien}revisé todo y está en orden. No hay nada que convenga tocar ahora."
    partes = []
    if u:
        partes.append(f"{u} {'cosa urgente' if u == 1 else 'cosas urgentes'}")
    if o:
        partes.append(f"{o} {'oportunidad' if o == 1 else 'oportunidades'}")
    if g:
        partes.append(f"{g} {'regalo' if g == 1 else 'regalos'} sin cobrar")
    texto = ", ".join(partes[:-1]) + (" y " if len(partes) > 1 else "") + partes[-1]
    arranque = "Empieza por lo urgente." if u else ("Arranca por lo gratis." if g and not o else "Te dejo lo que yo haría.")
    return f"{quien}encontré {texto}. {arranque}"


def frase_bienvenida(vistazo_gratis: bool, nombre: str = "") -> str:
    quien = f"Hola {nombre}. " if nombre else "Hola. "
    if vistazo_gratis:
        return quien + "Hoy el Vistazo corre por mi cuenta: reviso tus carteras y te digo qué hacer."
    return quien + "Dime qué tan a fondo quieres que mire y me pongo a revisar."
