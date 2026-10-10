"""
Lógica PURA del Juego en Vivo (sin acceso a Mongo): cuotas, reglas de puntos por evento,
multiplicador de riesgo vigente, tope de saldo en 0, cooldown y resumen final.

services/juego_en_vivo_service.py es el que lee/escribe Mongo y orquesta; todo lo que decide
"cuántos puntos vale qué" vive acá para poder probarlo aislado.
"""
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

from config import juego_en_vivo as cfg


# ==========================================
# Cuota inicial y riesgo
# ==========================================
def probabilidad_victoria(poder_propio: float, poder_rival: float) -> float:
    """
    Probabilidad (%) de que gane el primer equipo, con la fórmula de "expected score" de Elo
    sobre 'estadisticas.poder' (misma idea que prematch_service._probabilidad_victoria_elo, pero
    con ESCALA_PODER_PROBABILIDAD en vez de 400: ver config/juego_en_vivo.py). Acotada a 1-99%.
    """
    diferencia = (poder_rival or 0.0) - (poder_propio or 0.0)
    try:
        probabilidad = 1.0 / (1.0 + 10 ** (diferencia / cfg.ESCALA_PODER_PROBABILIDAD))
    except OverflowError:
        probabilidad = 0.01 if diferencia > 0 else 0.99
    return max(1.0, min(99.0, probabilidad * 100.0))


def categoria_y_cuota(probabilidad_pct: float) -> Tuple[str, int]:
    """Categoría (favorito/equilibrado/underdog) y cuota inicial según la probabilidad de
    victoria del país elegido."""
    if probabilidad_pct >= cfg.UMBRAL_FAVORITO_PCT:
        categoria = "favorito"
    elif probabilidad_pct <= cfg.UMBRAL_UNDERDOG_PCT:
        categoria = "underdog"
    else:
        categoria = "equilibrado"
    return categoria, cfg.CUOTAS_INICIALES[categoria]


def normalizar_multiplicador(valor: Any) -> float:
    """Devuelve el nivel de riesgo válido (1, 1.5, 2, 3) o lanza ValueError."""
    try:
        multiplicador = float(valor)
    except (TypeError, ValueError):
        raise ValueError("Multiplicador inválido.")
    if multiplicador not in cfg.NIVELES_RIESGO:
        raise ValueError(f"Multiplicador inválido. Valores permitidos: {', '.join(f'x{m:g}' for m in cfg.NIVELES_RIESGO)}.")
    return multiplicador


def multiplicador_vigente(historial: List[Dict[str, Any]], instante: datetime) -> float:
    """
    Multiplicador que regía en 'instante': el último cambio del historial cuyo 'efectivo_desde'
    ya había llegado. Como el instante de cada evento es su momento de REVELACIÓN (fijo, ver
    live_match_service.instante_revelacion_evento), un cambio pedido después de que el evento
    ocurrió nunca le aplica, y el resultado no depende de cuándo hace polling el usuario.
    """
    vigente = cfg.MULTIPLICADOR_INICIAL
    for cambio in sorted(historial, key=lambda c: c["efectivo_desde"]):
        if cambio["efectivo_desde"] <= instante:
            vigente = cambio["multiplicador"]
        else:
            break
    return vigente


def estado_cambio_riesgo(
    ultimo_cambio_en: Optional[datetime], eventos_visibles: List[Dict[str, Any]],
    instantes_eventos: List[datetime], ahora: datetime, en_transmision: bool
) -> Dict[str, Any]:
    """
    ¿Puede el usuario cambiar el riesgo ahora? Antes de la transmisión, siempre. Durante: una vez
    cada COOLDOWN_RIESGO_SEGUNDOS, o antes si después del último cambio se reveló un gol
    (TIPOS_EVENTO_LIBERAN_COOLDOWN) -- 'instantes_eventos[i]' es el instante de revelación de
    'eventos_visibles[i]'.
    """
    if not en_transmision or ultimo_cambio_en is None:
        return {"puede_cambiar": True, "segundos_restantes": 0, "liberado_por_gol": False}

    restantes = cfg.COOLDOWN_RIESGO_SEGUNDOS - (ahora - ultimo_cambio_en).total_seconds()
    if restantes <= 0:
        return {"puede_cambiar": True, "segundos_restantes": 0, "liberado_por_gol": False}

    hubo_gol = any(
        ev.get("tipo") in cfg.TIPOS_EVENTO_LIBERAN_COOLDOWN and instante > ultimo_cambio_en
        for ev, instante in zip(eventos_visibles, instantes_eventos)
    )
    if hubo_gol:
        return {"puede_cambiar": True, "segundos_restantes": 0, "liberado_por_gol": True}
    return {"puede_cambiar": False, "segundos_restantes": int(restantes + 0.999), "liberado_por_gol": False}


def nuevo_cambio_riesgo(multiplicador: float, ahora: datetime, en_transmision: bool) -> Dict[str, Any]:
    """Entrada del historial de multiplicadores. Durante la transmisión entra en vigor
    DEMORA_ACTIVACION_SEGUNDOS después (anti "ver la jugada y subir el riesgo")."""
    demora = cfg.DEMORA_ACTIVACION_SEGUNDOS if en_transmision else 0
    return {"multiplicador": multiplicador, "solicitado_en": ahora, "efectivo_desde": ahora + timedelta(seconds=demora)}


# ==========================================
# Reglas de puntos
# ==========================================
def evaluar_reglas_evento(
    evento: Dict[str, Any], pais_nombre: str, rival_nombre: str, pais_id: int,
    reglas: List[Dict[str, Any]], es_ultimo_evento: bool = False, resultado_para_mi: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Movimientos BASE (sin multiplicador) que dispara un evento para quien eligió 'pais_nombre'.
    'resultado_para_mi' ("victoria"/"empate"/"derrota") solo se usa con el último evento del
    partido (ver reglas "resultado" en config/juego_en_vivo.py). Un evento que no involucra al
    país elegido ni a su rival (árbitro, VAR de gol anulado, etc.) no devuelve nada.
    """
    tipo = evento.get("tipo", "")
    equipo = evento.get("equipo")
    jugadores = evento.get("jugadores") or []
    movimientos = []

    for regla in reglas:
        if not regla.get("activo", True):
            continue
        if regla.get("pais_id") not in (None, pais_id):
            continue

        aplica_a = regla["aplica_a"]
        condicion = regla.get("condicion")
        if aplica_a == "resultado":
            if not (es_ultimo_evento and resultado_para_mi and condicion == resultado_para_mi):
                continue
        else:
            if tipo not in regla.get("tipos_evento", []):
                continue
            if aplica_a == "propio" and equipo != pais_nombre:
                continue
            if aplica_a == "rival" and equipo != rival_nombre:
                continue
            # En "⚽ GOL" el motor arma jugadores = [goleador, arquero rival, asistente?]
            if condicion == "con_asistencia" and len(jugadores) < 3:
                continue

        movimientos.append({
            "regla_codigo": regla["codigo"],
            "descripcion": regla["descripcion"].format(pais=pais_nombre, rival=rival_nombre),
            "puntos_base": int(regla["puntos_base"]),
        })
    return movimientos


def procesar_eventos(
    eventos: List[Dict[str, Any]], desde_idx: int, hasta_idx: int, saldo_inicial: int,
    pais_nombre: str, rival_nombre: str, pais_id: int, reglas: List[Dict[str, Any]],
    multiplicador_para_idx: Callable[[int], float], total_eventos: int, resultado_para_mi: Optional[str]
) -> Dict[str, Any]:
    """
    Aplica en orden los eventos [desde_idx, hasta_idx) sobre 'saldo_inicial'. Cada regla que
    dispara es una transacción: neto = round(base * multiplicador), con el saldo topeado en 0
    (si un movimiento lo bajaría de 0, el neto real es solo lo que quedaba). Al tocar 0 la sesión
    queda eliminada: los eventos siguientes se marcan como procesados pero no mueven nada.
    """
    saldo = saldo_inicial
    transacciones = []
    eliminado = saldo <= 0
    for idx in range(desde_idx, hasta_idx):
        if eliminado:
            break
        evento = eventos[idx]
        movimientos = evaluar_reglas_evento(
            evento, pais_nombre, rival_nombre, pais_id, reglas,
            es_ultimo_evento=(idx == total_eventos - 1), resultado_para_mi=resultado_para_mi
        )
        if not movimientos:
            continue
        multiplicador = multiplicador_para_idx(idx)
        for mov in movimientos:
            neto_teorico = int(round(mov["puntos_base"] * multiplicador))
            nuevo_saldo = max(0, saldo + neto_teorico)
            transacciones.append({
                "evento_idx": idx,
                "evento_tipo": evento.get("tipo"),
                "minuto": evento.get("minuto"),
                "regla_codigo": mov["regla_codigo"],
                "descripcion": mov["descripcion"],
                "puntos_base": mov["puntos_base"],
                "multiplicador": multiplicador,
                "puntos_netos": nuevo_saldo - saldo,
                "saldo_resultante": nuevo_saldo,
            })
            saldo = nuevo_saldo
            if saldo <= 0:
                eliminado = True
                break
    return {"saldo": saldo, "transacciones": transacciones, "eliminado": eliminado}


def resultado_para_pais(ganador_lado: Optional[str], lado_elegido: str) -> Optional[str]:
    """'L'/'V'/'E' (resultado.ganador_lado) -> victoria/empate/derrota desde el lado elegido."""
    if ganador_lado not in ("L", "V", "E"):
        return None
    if ganador_lado == "E":
        return "empate"
    return "victoria" if ganador_lado == lado_elegido else "derrota"


# ==========================================
# Resumen final
# ==========================================
def resumen_final(sesion: Dict[str, Any], transacciones_evento: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Puntos iniciales/finales, neto, los 3 eventos de mayor impacto (por |puntos|) y el
    multiplicador máximo realmente usado (el más alto que llegó a aplicarse a un evento, o el
    máximo elegido si no hubo eventos con puntos)."""
    iniciales = sesion["puntos_iniciales"]
    finales = sesion["puntos_actuales"]
    top = sorted(transacciones_evento, key=lambda t: abs(t["puntos_netos"]), reverse=True)[:3]
    multiplicadores_usados = [t["multiplicador"] for t in transacciones_evento]
    return {
        "puntos_iniciales": iniciales,
        "puntos_finales": finales,
        "neto": finales - iniciales,
        "neto_vs_entrada": finales - sesion.get("entrada_monto", 0),
        "eventos_destacados": [
            {k: t[k] for k in ("minuto", "evento_tipo", "descripcion", "puntos_base", "multiplicador", "puntos_netos")}
            for t in top
        ],
        "multiplicador_maximo": max(multiplicadores_usados) if multiplicadores_usados else sesion.get("multiplicador_maximo", 1.0),
        "eliminado": finales <= 0,
    }
