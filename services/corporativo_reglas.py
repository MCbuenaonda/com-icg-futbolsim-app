"""
Reglas PURAS de los Corporativos Deportivos (sin Mongo): valuaciones, renta por partido, honorarios,
probabilidades de mercado y de carrera, directorio, remuneración y cotización. Todas las constantes viven en
config/corporativos.py. Las usan los services corporativo_* y el script simular_balance_corporativos.py
(por eso no tocan la base: mismo patrón que services/juego_en_vivo_puntos.py).
"""
import math
import random
from statistics import mean, pstdev
from typing import Dict, Iterable, Optional

from config import corporativos as C


def semilla(*partes) -> random.Random:
    """Generador determinístico a partir de (universo, seq, …): reproducir un universo da el mismo resultado."""
    return random.Random("|".join(str(p) for p in partes))


def limitar(x: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, x))


# --- Valuaciones ---------------------------------------------------------------------------------
def factor_edad(edad: Optional[int]) -> float:
    for tope, factor in C.FACTOR_EDAD:
        if (edad or 27) <= tope:
            return factor
    return C.FACTOR_EDAD[-1][1]


def _z(valores: Dict[int, float]) -> Dict[int, float]:
    if not valores:
        return {}
    m, s = mean(valores.values()), pstdev(valores.values()) or 1.0
    return {k: (v - m) / s for k, v in valores.items()}


def valores_jugadores(jugadores: Iterable[dict], poder_por_pais: Dict[int, float]) -> Dict[int, int]:
    """
    {jugador_id: valor de mercado}. Los atributos de este mundo son casi parejos, así que el valor sale del
    PERCENTIL de un puntaje de calidad (overall, rendimiento y fuerza de la selección, en z-scores), con una
    curva que deja pocas estrellas caras, por la edad.
    """
    jugadores = list(jugadores)
    z_ovr = _z({j["id"]: float(j.get("overall") or 60) for j in jugadores})
    z_ren = _z({j["id"]: float(j.get("rendimiento") or 60) for j in jugadores})
    z_sel = _z({j["id"]: float(poder_por_pais.get(j.get("pais_id"), 0) or 0) for j in jugadores})
    p = C.PESOS_CALIDAD_JUGADOR
    calidad = {i: p["overall"] * z_ovr[i] + p["rendimiento"] * z_ren[i] + p["seleccion"] * z_sel[i] for i in z_ovr}
    orden = sorted(calidad, key=calidad.get)
    n = max(len(orden) - 1, 1)
    edades = {j["id"]: j.get("edad") for j in jugadores}
    valores = {}
    for pos, jid in enumerate(orden):
        pct = pos / n
        base = C.VALOR_JUGADOR_MIN + (C.VALOR_JUGADOR_MAX - C.VALOR_JUGADOR_MIN) * pct ** C.CURVA_VALOR_JUGADOR
        valores[jid] = int(round(base * factor_edad(edades.get(jid)), -1))
    return valores


def valor_leyenda(jugador: dict, percentil_poder: float) -> int:
    """Valor de mercado de una LEYENDA: escala propia (ver config/corporativos.py), por fama y selección."""
    fmin, fmax = C.RANGO_FAMA_LEYENDA
    fama = min(max(float(jugador.get("fama") or 0.5), 0.0), 1.0)
    peso = C.PESO_SELECCION_LEYENDA
    return int(round(C.VALOR_LEYENDA_BASE * (fmin + (fmax - fmin) * fama) * (1 - peso / 2 + peso * percentil_poder), -1))


def valores_con_leyendas(jugadores: Iterable[dict], poder_por_pais: Dict[int, float]) -> tuple:
    """
    (valores, percentil) de TODOS los jugadores: los actuales con valores_jugadores/percentiles de siempre,
    calculados SOLO entre ellos, y las leyendas con valor_leyenda y percentil 1.0 (están por encima de todos).
    """
    jugadores = list(jugadores)
    normales = [j for j in jugadores if not j.get("leyenda")]
    valores = valores_jugadores(normales, poder_por_pais)
    percentil = percentiles(valores)
    pct_poder = percentiles({p: float(v or 0) for p, v in poder_por_pais.items()})
    for j in jugadores:
        if j.get("leyenda"):
            valores[j["id"]] = valor_leyenda(j, pct_poder.get(j.get("pais_id"), 0.5))
            percentil[j["id"]] = 1.0
    return valores, percentil


def percentiles(valores: Dict[int, float]) -> Dict[int, float]:
    orden = sorted(valores, key=valores.get)
    n = max(len(orden) - 1, 1)
    return {k: i / n for i, k in enumerate(orden)}


def valor_seleccion(pais: dict) -> int:
    """Valor comercial: el valor de mercado de la selección (ya sigue sus resultados) más su hinchada."""
    v = (pais.get("valor") or 1000) * C.FACTOR_VALOR_SELECCION
    v += max(0, (pais.get("aficionados") or C.AFICIONADOS_BASE) - C.AFICIONADOS_BASE) * C.FACTOR_AFICIONADOS
    return int(round(v, -1))


# --- Aporte y renta por partido ------------------------------------------------------------------
def separar_por_partido(agregado: dict) -> Dict[str, dict]:
    """
    Parte el agregado de varios partidos (estadisticas_service._agregar_jugadores_mundial) en uno por partido:
    {juego_id: {jugador_id: {"pais_id", "metricas": {m: n}}}}. Así una sola carga sirve para procesar muchos partidos.
    """
    por_partido: Dict[str, dict] = {}
    for jid, a in agregado.items():
        for metrica, partidos in a["partidos_por"].items():
            for juego_id, n in partidos.items():
                fila = por_partido.setdefault(juego_id, {}).setdefault(jid, {"pais_id": a.get("pais_id"), "metricas": {}})
                fila["metricas"][metrica] = n
    return por_partido


def aporte_partido(juego: dict, agregado_partido: dict, posicion_por_jugador: Dict[int, int]) -> dict:
    """
    Qué hizo cada selección y cada jugador en UN partido. 'agregado_partido' es
    estadisticas_service._agregar_jugadores_mundial([juego]) (resuelve los nombres de los eventos a ids).
    -> {"selecciones": {pais_id: "victoria"|"empate"|"derrota"}, "jugadores": {id: {jugar, gol, asistencia, valla_invicta, roja}}}
    """
    res = juego.get("resultado") or {}
    local, visita = (juego.get("equipo_local") or {}).get("id"), (juego.get("equipo_visitante") or {}).get("id")
    gl, gv = res.get("goles_local", 0) or 0, res.get("goles_visitante", 0) or 0
    ganador = res.get("ganador_id")
    selecciones = {}
    for pid in (local, visita):
        if pid is None:
            continue
        if res.get("empate") or ganador is None:
            selecciones[pid] = "empate"
        else:
            selecciones[pid] = "victoria" if ganador == pid else "derrota"
    recibidos = {local: gv, visita: gl}
    jugadores = {}
    for jid, a in agregado_partido.items():
        m = a["metricas"]
        if not m.get("partidos"):
            continue
        valla = recibidos.get(a.get("pais_id")) == 0 and posicion_por_jugador.get(jid) in C.POSICIONES_VALLA_INVICTA
        jugadores[jid] = {"jugar": 1, "gol": m.get("goles", 0), "asistencia": m.get("asistencias", 0),
                          "valla_invicta": 1 if valla else 0, "roja": m.get("rojas", 0)}
    return {"selecciones": selecciones, "jugadores": jugadores}


def renta_seleccion(valor: int, resultado: str) -> int:
    r = C.RENTA_SELECCION
    return int(round(valor * (r["jugar"] + r[resultado])))


def renta_fase(valor: int, avanzo: bool) -> int:
    return int(round(valor * C.RENTA_SELECCION["avance_fase" if avanzo else "eliminacion"]))


def renta_jugador(valor: int, aporte: dict) -> int:
    return int(round(valor * sum(C.RENTA_JUGADOR[k] * n for k, n in aporte.items())))


def honorario(tipo: str, valor: int) -> int:
    return int(round(valor * C.HONORARIO_POR_CICLO[tipo]))


# --- Mercado -------------------------------------------------------------------------------------
def prima_referencia(valor: float) -> int:
    return int(round(valor * C.PRIMA_REFERENCIA, -1))


def puntaje_oferta(prima: float, valor: float) -> float:
    """100 si la prima ofrecida es >= 1,3x la de referencia (5% del valor)."""
    return limitar(100 * (prima / max(prima_referencia(valor), 1)) / C.OFERTA_IDEAL_MULTIPLO, 0, 100)


def probabilidad_acepta(reputacion: float, fama: float, prima: float, valor: float,
                        afinidad: bool, calidad_cartera: float) -> float:
    """calidad_cartera: 0-100 (percentil medio de los representados del corporativo)."""
    p = C.PESOS_ATRACTIVO
    atractivo = (p["reputacion"] * reputacion + p["fama"] * fama + p["oferta"] * puntaje_oferta(prima, valor)
                 + p["afinidad"] * (100 if afinidad else 0) + p["cartera"] * calidad_cartera)
    return limitar(atractivo / 100, *C.PROBABILIDAD_ACEPTA)


# --- Carrera del CEO -----------------------------------------------------------------------------
def probabilidad_oferta_empleo(fama: float) -> float:
    base, factor = C.PROB_OFERTA_BUSCANDO
    return limitar(base + fama * factor, 0, 0.95)


def probabilidad_headhunting(fama: float, supera_promedio: bool) -> float:
    if not supera_promedio:
        return 0.0
    umbral, factor, base = C.PROB_HEADHUNTING
    return limitar(max(0.0, (fama - umbral) * factor) + base, 0, 0.6)


def sueldo_base(tier: str, fama: float) -> int:
    """Sueldo base por ciclo: el del tier, ±20% según la fama (fama 50 = el del tier)."""
    ajuste = 1 + C.AJUSTE_SUELDO_FAMA * limitar((fama - 50) / 50, -1, 1)
    return int(round(C.TIERS[tier]["sueldo_base"] * ajuste))


def bono_ciclo(porcentaje: float, utilidad: float, sueldo: int) -> int:
    if utilidad <= 0:
        return 0
    return int(min(utilidad * porcentaje, sueldo * C.BONO_TOPE_MULTIPLO_SUELDO))


def cambio_confianza(tier: str, posicion: int, roi_ventana: float, cotizacion_vs_indice: float, hubo_impago: bool) -> int:
    """
    posicion: 1..10 en el ranking de ROI de la ventana entre los 10 corporativos del universo.
    cotizacion_vs_indice: variación de la acción en el ciclo menos la variación media del índice FIFAV 10.
    """
    esperada = C.POSICION_ESPERADA_TIER[tier]
    if posicion <= esperada:
        cambio = C.CONFIANZA_POSICION["cumple"]
    elif posicion <= esperada + 2:
        cambio = C.CONFIANZA_POSICION["cerca"]
    else:
        cambio = C.CONFIANZA_POSICION["lejos"]
    umbral, castigo = C.CONFIANZA_ROI_NEGATIVO
    if roi_ventana < umbral:
        cambio += castigo
    if cotizacion_vs_indice > 0:
        cambio += C.CONFIANZA_VS_INDICE
    elif cotizacion_vs_indice < 0:
        cambio -= C.CONFIANZA_VS_INDICE
    if hubo_impago:
        cambio += C.CONFIANZA_IMPAGO
    return cambio


# --- Bolsa ---------------------------------------------------------------------------------------
def precio_accion(capital: float, valor_cartera: float, sentimiento: float, acciones: int = C.ACCIONES_POR_CORPORATIVO) -> float:
    return round(max(capital + valor_cartera, 0) / acciones * sentimiento, 2)


def nuevo_sentimiento(sentimiento: float, roi: float, noticias: float, rng: random.Random) -> float:
    """
    roi: del ciclo. noticias: suma de impactos (+0.05 fichaje estrella, −0.1 despido, −0.15 impago…).
    Sesgo hacia 1.0 (el mercado olvida) + ruido acotado.
    """
    s = sentimiento + (1.0 - sentimiento) * 0.1 + roi * 2 + noticias + rng.uniform(-C.RUIDO_COTIZACION, C.RUIDO_COTIZACION)
    return round(limitar(s, *C.SENTIMIENTO_RANGO), 4)


def limitar_banda(precio_nuevo: float, precio_anterior: float) -> float:
    b = C.BANDA_COTIZACION_CICLO
    return round(limitar(precio_nuevo, precio_anterior * (1 - b), precio_anterior * (1 + b)), 2)


def ciclo_de_seq(seq: int) -> int:
    """Número de ciclo al que pertenece un partido del registro (seq desde 1)."""
    return math.ceil(seq / C.PARTIDOS_POR_CICLO)
