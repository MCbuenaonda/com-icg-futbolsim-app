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
    diferencia = {local: gl - gv, visita: gv - gl}   # para las goleadas (corte de acuerdos publicitarios)
    jugadores = {}
    for jid, a in agregado_partido.items():
        m = a["metricas"]
        if not m.get("partidos"):
            continue
        valla = recibidos.get(a.get("pais_id")) == 0 and posicion_por_jugador.get(jid) in C.POSICIONES_VALLA_INVICTA
        jugadores[jid] = {"jugar": 1, "gol": m.get("goles", 0), "asistencia": m.get("asistencias", 0),
                          "valla_invicta": 1 if valla else 0, "roja": m.get("rojas", 0)}
    return {"selecciones": selecciones, "jugadores": jugadores, "diferencia": {k: v for k, v in diferencia.items() if k is not None}}


def renta_seleccion(valor: int, resultado: str) -> int:
    r = C.RENTA_SELECCION
    return int(round(valor * (r["jugar"] + r[resultado])))


def renta_fase(valor: int, avanzo: bool) -> int:
    return int(round(valor * C.RENTA_SELECCION["avance_fase" if avanzo else "eliminacion"]))


def renta_jugador(valor: int, aporte: dict) -> int:
    return int(round(valor * sum(C.RENTA_JUGADOR[k] * n for k, n in aporte.items())))


def honorario(tipo: str, valor: int) -> int:
    """Honorario ESPERADO por ciclo (mantenimiento + partidos esperados): para vistas, rescisiones y estimaciones."""
    return int(round(valor * (C.HONORARIO_MANTENIMIENTO[tipo] + C.HONORARIO_POR_PARTIDO[tipo] * C.PARTIDOS_ESPERADOS_POR_CICLO)))


def honorario_mantenimiento(tipo: str, valor: int) -> int:
    """Lo que se cobra cada ciclo, juegue o no."""
    return int(round(valor * C.HONORARIO_MANTENIMIENTO[tipo]))


def honorario_partido(tipo: str, valor: int) -> int:
    """Lo que se cobra por cada partido que el representado juega (junto con su renta)."""
    return int(round(valor * C.HONORARIO_POR_PARTIDO[tipo]))


def popularidad_seleccion(aficionados: float) -> float:
    lo, hi = C.AFICIONADOS_POPULARIDAD
    t = limitar(((aficionados or lo) - lo) / (hi - lo), 0, 1)
    return round(C.POPULARIDAD_RANGO[0] + t * (C.POPULARIDAD_RANGO[1] - C.POPULARIDAD_RANGO[0]), 3)


def popularidad_jugador(valor: float) -> float:
    """Por su valor de mercado (las leyendas, por encima del máximo de los actuales, tocan el techo)."""
    t = limitar((valor - C.VALOR_JUGADOR_MIN) / (C.VALOR_JUGADOR_MAX - C.VALOR_JUGADOR_MIN), 0, 1)
    return round(C.POPULARIDAD_RANGO[0] + t ** 0.6 * (C.POPULARIDAD_RANGO[1] - C.POPULARIDAD_RANGO[0]), 3)


def patrocinio(tipo: str, valor: int, popularidad: float, multiplicador: float = 1.0) -> int:
    """Ingreso fijo por ciclo de un contrato (juegue o no). 'multiplicador': campaña de marketing vigente."""
    return int(round(valor * C.PATROCINIO_POR_CICLO[tipo] * popularidad * multiplicador))


def prima_renovacion(valor: float, satisfaccion: float) -> int:
    descuento = C.DESCUENTO_RENOVACION_SATISFACCION * limitar((satisfaccion - 60) / 40, 0, 1)
    return int(round(prima_referencia(valor) * C.PRIMA_RENOVACION * (1 - descuento), -1))


def renta_esperada_partido(tipo: str, valor: int) -> int:
    """Renta media de UN partido jugado, neta del honorario por partido (para proyecciones; ~45% victorias, 25% empates)."""
    if tipo == "seleccion":
        r = C.RENTA_SELECCION
        bruto = r["jugar"] + 0.45 * r["victoria"] + 0.25 * r["empate"] + 0.30 * r["derrota"]
    else:
        r = C.RENTA_JUGADOR
        bruto = r["jugar"] + 0.12 * r["gol"] + 0.08 * r["asistencia"] + 0.08 * r["valla_invicta"] - 0.01 * abs(r["roja"])
    return int(round(valor * (bruto - C.HONORARIO_POR_PARTIDO[tipo])))


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


# --- Acciones del CEO entre partidos: acuerdos y giras ------------------------------------------
def acuerdo_montos(valor: float, popularidad: float, reputacion: float, rng: random.Random) -> dict:
    """Adelanto, pago por ciclo y duración de un acuerdo publicitario (determinístico con rng)."""
    factor = popularidad * (0.7 + 0.6 * limitar(reputacion, 0, 100) / 100)
    return {"adelanto": int(round(valor * C.ACUERDO_ADELANTO * factor, -1)),
            "pago_ciclo": int(round(valor * C.ACUERDO_PAGO_CICLO * factor, -1)),
            "ciclos": rng.randint(*C.ACUERDO_CICLOS)}


def gira_costo(valor: float) -> int:
    return max(C.GIRA_COSTO_MINIMO, int(round(valor * C.GIRA_COSTO, -1)))


def gira_recaudacion(valor: float, popularidad: float, rng: random.Random) -> int:
    lo, hi = C.GIRA_RECAUDACION
    return int(round(valor * rng.uniform(lo, hi) * popularidad / 1.1, -1))


def gira_aficionados(aficionados: float, popularidad: float, rng: random.Random) -> int:
    """Aficionados que suma una gira de selección del USUARIO: +1% a +3% (más si la selección ya es popular)."""
    lo, hi = C.GIRA_AFICIONADOS_PCT
    pct = lo + (hi - lo) * limitar((popularidad - C.POPULARIDAD_RANGO[0]) / (C.POPULARIDAD_RANGO[1] - C.POPULARIDAD_RANGO[0]) * 0.6
                                   + rng.random() * 0.4, 0, 1)
    return int(round((aficionados or C.AFICIONADOS_BASE) * pct))


def gira_jugador_costo(valor: float) -> int:
    return max(C.GIRA_COSTO_MINIMO, int(round(valor * C.GIRA_JUGADOR_COSTO, -1)))


def gira_jugador_ingreso(valor: float, popularidad: float, rng: random.Random) -> int:
    lo, hi = C.GIRA_JUGADOR_INGRESO
    return int(round(valor * rng.uniform(lo, hi) * popularidad / 1.1, -1))


def gira_jugador_costo_v2(valor: float) -> int:
    return max(C.GIRA_COSTO_MINIMO_JUGADOR, int(round(valor * C.GIRA_JUGADOR_COSTO_V2)))


def gira_jugador_retorno(popularidad: float, forma_seleccion: float, forma_jugador: float) -> float:
    """Multiplicador esperado sobre el costo (sin azar): mejor con un jugador popular, que juega y cuya selección viene bien."""
    lo, hi = C.GIRA_JUGADOR_RETORNO
    puntaje = (0.45 * _escala(popularidad, C.POPULARIDAD_RANGO[0], C.POPULARIDAD_RANGO[1])
               + 0.30 * limitar(forma_seleccion or 0, 0, 1) + 0.25 * limitar(forma_jugador or 0, 0, 1))
    return lo + (hi - lo) * puntaje


def gira_jugador_ingreso_v2(costo: int, popularidad: float, forma_seleccion: float, forma_jugador: float, rng: random.Random) -> int:
    """Ingreso total de la gira de un jugador (se cobra en partes iguales partido a partido): costo x retorno ±15%."""
    return int(round(costo * gira_jugador_retorno(popularidad, forma_seleccion, forma_jugador) * rng.uniform(0.85, 1.15)))


def aporte_aficionados_jugador(forma_seleccion: float, forma_jugador: float, rng: random.Random) -> int:
    """
    GIRA_JUGADOR_AFICIONADOS_MIN a _MAX (1 a 100) aficionados para su selección por una gira de un jugador.
    forma_seleccion: puntos de sus últimos 5 partidos / 15. forma_jugador: 0..1 (juega y aporta goles/asistencias).
    Con malos resultados (selección que no suma y jugador que no juega) aporta el mínimo.
    """
    base = 0.6 * limitar(forma_seleccion, 0, 1) + 0.4 * limitar(forma_jugador, 0, 1)
    valor = int(round(C.GIRA_JUGADOR_AFICIONADOS_MAX * limitar(base * rng.uniform(0.7, 1.15), 0, 1)))
    return max(C.GIRA_JUGADOR_AFICIONADOS_MIN, min(C.GIRA_JUGADOR_AFICIONADOS_MAX, valor))


# --- Señales de comprar / vender -----------------------------------------------------------------
def renta_esperada_ciclo(tipo: str, valor: float, partidos_2_ciclos: int, popularidad: float, titular: float = 1.0) -> int:
    """Renta neta esperada POR CICLO de un representado en los próximos 2 ciclos (partidos programados + patrocinio
    - mantenimiento). 'titular': fracción de partidos que juega (jugadores)."""
    por_partidos = partidos_2_ciclos * titular * renta_esperada_partido(tipo, int(valor)) / 2
    return int(por_partidos + patrocinio(tipo, int(valor), popularidad) - honorario_mantenimiento(tipo, int(valor)))


def _senal_cartera(datos: dict, pos: list, neg: list):
    """
    Cartera: la señal de VENDER solo sale cuando el representado rinde mal Y su contrato está en la ventana de
    renovación (los últimos CICLOS_AVISO_RENOVACION ciclos: "pide renovación"). Un representado que rinde bien no se
    marca para vender aunque su valor haya subido: es justamente el que más deja cuando juega.
    En la ventana, además, una recomendación de renovación:
      renovar     rinde bien (o recuperó lo que costó) y sigue jugando
      esperar     resultados mixtos y todavía juega partidos antes de que venza: conviene verlo jugar y decidir después
      no_renovar  rinde mal y ya no le quedan partidos antes del vencimiento (o su selección quedó eliminada)
    -> (senal, renovacion|None). Agrega sus motivos a pos/neg.
    """
    restantes = datos.get("ciclos_restantes") or 99
    en_ventana = restantes <= C.CICLOS_AVISO_RENOVACION
    renta, costos = datos.get("renta_total") or 0, datos.get("costos_total") or 0
    # forma mala, casi no juega o eliminada (motivos de arriba); «sin partido programado» no cuenta: en las
    # eliminatorias una selección pasa varios ciclos sin jugar y eso no habla de su rendimiento
    malos = sum(1 for t in neg if not t.startswith("Sin partido"))
    buenos = sum(1 for t in pos)           # juega pronto, forma buena, titular
    if costos:
        if renta >= costos:
            buenos += 1
            pos.append(f"Ya recuperó lo que costó: rindió {int(round(renta)):,} contra {int(round(costos)):,}")
        else:
            malos += 1
            neg.append(f"Rindió {int(round(renta)):,} y costó {int(round(costos)):,}")
    if (datos.get("ciclos_sin_jugar") or 0) >= 2:
        malos += 1
        neg.append(f"{datos['ciclos_sin_jugar']} ciclos sin jugar")
    if (datos.get("satisfaccion") or 100) < 40:
        neg.append(f"Está descontento (satisfacción {datos['satisfaccion']}): podría pedir irse sin dejarte nada")
    if datos.get("valor_firma") and (datos.get("valor") or 0) >= datos["valor_firma"] * 1.3:
        pos.append(f"Su valor subió {datos['valor'] / datos['valor_firma'] - 1:.0%} desde que lo firmaste")
    if not en_ventana:
        return (None, None)
    antes = datos.get("partidos_antes_vencer") or 0
    antes_ultimo = datos.get("partidos_antes_ultimo") or 0   # partidos antes del último ciclo: todavía se puede renovar después
    if datos.get("eliminada"):
        decision, texto = "no_renovar", "Su selección quedó eliminada: renovar no le deja más partidos."
    elif buenos >= 2 and malos <= 1:
        decision, texto = "renovar", ("Viene rindiendo bien: conviene renovarlo antes de que venza."
                                      + (f" Además juega {antes} partido{'s' if antes != 1 else ''} antes del vencimiento." if antes else ""))
    elif malos >= 2 and buenos == 0 and not antes_ultimo:
        decision, texto = "no_renovar", "Viene rindiendo mal y ya no juega antes de que venza: mejor dejarlo ir o venderlo."
    elif antes_ultimo and restantes >= 2:
        decision, texto = "esperar", (f"Resultados mixtos y todavía juega {antes_ultimo} partido{'s' if antes_ultimo != 1 else ''} "
                                      "antes de su último ciclo: espera a verlo jugar y decide después (puedes renovarlo hasta el último ciclo).")
    elif renta >= costos:
        decision, texto = "renovar", "Ya recuperó lo que costó: renovarlo es razonable."
    else:
        decision, texto = "no_renovar", "No recuperó lo que costó y no le quedan partidos para demostrar: mejor no renovarlo."
    neg.append(f"Pide renovación: su contrato vence en {restantes} ciclo{'s' if restantes != 1 else ''}")
    senal = "vender" if decision == "no_renovar" and malos >= 2 else None
    return (senal, {"decision": decision, "texto": texto, "partidos_antes": antes, "ciclos_restantes": restantes})


def senales(datos: dict) -> dict:
    """
    Señales de COMPRAR (mercado) o de VENDER (cartera) con su "¿por qué?". 'datos':
      tipo, valor, popularidad, partidos_2_ciclos, sin_partido (bool), eliminada (bool), forma (0..1, puntos/15 de los
      últimos 5 de su selección), titular (0..1 o None), y para contratos propios: prima, satisfaccion,
      ciclos_sin_jugar, renta_total, costos_total, valor_firma, ciclos_restantes.
    -> {"senal": "comprar"|"vender"|"mantener"|None, "motivos": [{"tono": "pos"|"neg", "texto"}], "renta_ciclo", "recupera_ciclos"}
    """
    tipo, valor = datos["tipo"], datos.get("valor") or 0
    titular = datos.get("titular")
    renta = renta_esperada_ciclo(tipo, valor, datos.get("partidos_2_ciclos") or 0, datos.get("popularidad") or 1.0,
                                 1.0 if titular is None else max(0.2, titular))
    pos, neg = [], []
    if datos.get("eliminada"):
        neg.append("Su selección fue eliminada: ya no juega partidos")
    elif datos.get("sin_partido"):
        neg.append("Sin partido programado todavía")
    elif datos.get("partidos_2_ciclos"):
        pos.append(f"Juega pronto: {datos['partidos_2_ciclos']} partido{'s' if datos['partidos_2_ciclos'] > 1 else ''} en los próximos 2 ciclos")
    forma = datos.get("forma")
    if forma is not None:
        if forma >= 0.6:
            pos.append(f"Su selección viene bien ({round(forma * 15)} de 15 puntos en sus últimos 5)")
        elif forma <= 0.25:
            neg.append(f"Su selección viene mal ({round(forma * 15)} de 15 puntos en sus últimos 5)")
    if titular is not None and tipo == "jugador":
        if titular >= 0.7:
            pos.append("Titular habitual")
        elif titular <= 0.3:
            neg.append("Casi no juega con su selección")
    salida = {"renta_ciclo": renta, "recupera_ciclos": None}
    if "prima" not in datos:   # mercado: ¿conviene comprar?
        prima = prima_referencia(valor)
        # recuperación: mitad corto plazo (partidos ya programados) y mitad ritmo normal (~0,2 partidos por ciclo)
        largo = renta_esperada_ciclo(tipo, valor, 2 * C.PARTIDOS_ESPERADOS_POR_CICLO, datos.get("popularidad") or 1.0,
                                     1.0 if titular is None else max(0.2, titular))
        mezcla = (renta + largo) / 2
        if mezcla > 0:
            salida["recupera_ciclos"] = round(prima / mezcla, 1)
            if prima / mezcla <= 6:
                pos.append(f"La prima ({prima:,}) se recupera en ~{prima / mezcla:.0f} ciclos")
        # exigente a propósito: si casi todos tuvieran señal, no serviría para elegir
        senal = "comprar" if len(pos) >= 3 and not neg else None
    else:                      # cartera: ¿conviene vender? ¿conviene renovar?
        senal, renovacion = _senal_cartera(datos, pos, neg)
        salida["renovacion"] = renovacion
    salida.update(senal=senal, motivos=[{"tono": "pos", "texto": t} for t in pos] + [{"tono": "neg", "texto": t} for t in neg])
    return salida


# --- Marcas y patrocinios -------------------------------------------------------------------------
def _escala(x, lo, hi):
    return limitar((x - lo) / (hi - lo), 0, 1) if hi > lo else 0.0


def encaje_marca(marca: dict, rep: dict) -> int:
    """
    0..100: qué tanto le interesa el representado a la marca (0 = fuera de su región). 'rep':
      tipo, pais_id, confederacion_id, percentil (0..1 por valor), popularidad, forma (0..1 o None), titular (0..1 o None),
      partidos_2, edad, leyenda, sector (Portero/Defensa/Medio/Delantero), goles (en el Mundial), eliminada
    """
    if marca["alcance"] == "continental" and rep.get("confederacion_id") != marca.get("confederacion_id"):
        return 0
    if marca["alcance"] == "local" and rep.get("pais_id") != marca.get("pais_id"):
        return 0
    pct = rep.get("percentil") or 0
    # las globales buscan estrellas; las locales se conforman con menos
    base = {3: 10 + 40 * pct, 2: 18 + 32 * pct, 1: 30 + 20 * pct}[marca.get("nivel", 2)]
    forma = rep.get("forma")
    forma = 0.4 if forma is None else forma
    titular = rep.get("titular")
    titular = 0.5 if titular is None else titular
    edad = rep.get("edad") or 26
    es_jug = rep["tipo"] == "jugador"
    perfil = marca.get("perfil")
    if perfil == "goleadores":
        extra = (min(30, (rep.get("goles") or 0) * 10) + (12 if rep.get("sector") == "Delantero" else 0)) if es_jug else 25 * forma
    elif perfil == "figuras_forma":
        extra = 26 * forma + (14 * titular if es_jug else 10)
    elif perfil == "promesas":
        extra = (40 if edad <= 21 else 28 if edad <= 23 else 12 if edad <= 25 else 0) if es_jug and not rep.get("leyenda") else 0
    elif perfil == "aficion":
        extra = 40 * _escala(rep.get("popularidad") or 1.0, C.POPULARIDAD_RANGO[0], C.POPULARIDAD_RANGO[1])
    elif perfil == "selecciones":
        extra = (22 + 18 * forma) if not es_jug else 4
    elif perfil == "veteranos":
        extra = ((32 if edad >= 31 else 18 if edad >= 28 else 0) + 8 * titular) if es_jug and not rep.get("leyenda") else 10
    elif perfil == "defensas":
        extra = (34 + 6 * titular if rep.get("sector") in ("Portero", "Defensa") else 0) if es_jug else 14
    elif perfil == "leyendas":
        extra = 42 if rep.get("leyenda") else 0
    else:
        extra = 10
    ajuste = (6 if rep.get("partidos_2") else 0) - (30 if rep.get("eliminada") else 0)
    return int(round(limitar(base + extra + ajuste, 0, 100)))


def monto_marca(valor: float, nivel: int, encaje: float, reputacion: float) -> dict:
    """Pago por ciclo y firma de un patrocinio."""
    pago = valor * C.MARCA_PAGO_CICLO * C.MARCA_FACTOR_NIVEL.get(nivel, 1.0) * (0.7 + 0.6 * limitar(encaje, 0, 100) / 100) \
        * (0.85 + 0.3 * limitar(reputacion, 0, 100) / 100)
    pago = max(10, int(round(pago, -1)))
    return {"pago_ciclo": pago, "firma": int(round(pago * C.MARCA_FIRMA, -1))}


def prob_promocion(encaje: float, reputacion: float, fama: float = 50) -> float:
    """Probabilidad de que una marca acepte la promoción del CEO (se resuelve al cierre del ciclo)."""
    return round(limitar(C.MARCA_PROMOCION_BASE + 0.55 * _escala(encaje, C.MARCA_ENCAJE_MINIMO - 10, 95)
                         + 0.15 * limitar(reputacion, 0, 100) / 100 + 0.10 * limitar(fama, 0, 100) / 100, 0.05, 0.92), 2)


def riesgo_marca(eventos: dict, fidelidad: float) -> int:
    """0..100: riesgo de que la marca corte, por lo que pasó en el ciclo (roja, goleada, eliminación, sin jugar, mala forma)."""
    bruto = sum(C.MARCA_RIESGO[k] for k, v in (eventos or {}).items() if v and k in C.MARCA_RIESGO)
    return int(round(limitar(bruto * (1.3 - limitar(fidelidad, 0, 1)), 0, 100)))


# --- Televisoras (config TV_*; services/corporativo_tv_service.py) -----------------------------------------------
def tv_tarifa(valor: int, popularidad: float, nivel: int, perfil: str, forma: float = 1.0) -> Dict[str, int]:
    """Pago por partido según el resultado + bono por partido del contrato (si cumple la exigencia)."""
    base = valor * C.TV_BASE * popularidad * C.TV_NIVEL.get(nivel, 1.0) * forma
    m = C.TV_PERFIL.get(perfil) or C.TV_PERFIL["generosa"]
    return {k: max(1, int(round(base * m[k]))) for k in ("victoria", "empate", "derrota", "bono")}


def tv_esperado(tarifa: Dict[str, int]) -> int:
    """Pago medio por partido (sin bono), para comparar ofertas y para que la IA elija."""
    return int(round(sum(tarifa[r] * p for r, p in C.TV_PROBABILIDAD_RESULTADO.items())))


def tv_pct(resultados: Iterable[str]) -> Optional[float]:
    """% de los puntos sacados (victoria 3, empate 1) en los partidos del contrato; None sin partidos."""
    resultados = list(resultados)
    if not resultados:
        return None
    return sum(3 if r == "victoria" else 1 if r == "empate" else 0 for r in resultados) / (3 * len(resultados))


def tv_forma(pct: Optional[float]) -> float:
    """Multiplicador de la tarifa del contrato SIGUIENTE según el % de puntos del anterior."""
    if pct is None:
        return 1.0
    lo, hi = C.TV_FORMA_RANGO
    return round(limitar(1 + C.TV_FORMA_PENDIENTE * (pct - C.TV_FORMA_REFERENCIA), lo, hi), 3)


def tv_bono(tarifa: Dict[str, int], partidos: int, pct: Optional[float], exigencia: float) -> int:
    return int(tarifa["bono"] * partidos) if pct is not None and pct >= exigencia else 0


def tv_prob_renueva(fidelidad: float, pct: Optional[float]) -> float:
    """La cadena actual ofrece seguir: más si es fiel y si el equipo rindió."""
    return limitar(fidelidad + 1.2 * ((pct if pct is not None else C.TV_FORMA_REFERENCIA) - C.TV_FORMA_REFERENCIA), 0.05, 0.97)


def tv_prob_compite(nivel: int, pct: Optional[float], popularidad: float) -> float:
    """Otra cadena del país oferta en la renovación: más con buenos resultados y una selección popular."""
    lo, hi = C.TV_PROB_COMPETENCIA
    base = 0.30 + 1.3 * ((pct if pct is not None else C.TV_FORMA_REFERENCIA) - C.TV_FORMA_REFERENCIA) + 0.4 * (popularidad - 1)
    return limitar(base - 0.05 * (nivel - 2), lo, hi)


def tv_peso_inicial(nivel: int, popularidad: float) -> float:
    """Qué cadena hace la primera oferta: las selecciones populares atraen a la líder de audiencia."""
    return max(0.05, {1: 1.3 - 0.6 * (popularidad - 1), 2: 1.0, 3: 0.6 + 1.2 * (popularidad - 1)}[nivel])


def tv_invitado_pago(valor: int, popularidad: float, nivel_cadena: int) -> int:
    """Lo que cobra el corporativo cuando su jugador va de invitado a una transmisión (según el nivel del jugador)."""
    return max(1, int(round(valor * C.TV_INVITADO_PAGO * popularidad * C.TV_NIVEL.get(nivel_cadena, 1.0))))


def tv_invitado_aficionados(rng: random.Random, popularidad: float) -> int:
    lo, hi = C.TV_INVITADO_AFICIONADOS
    return int(round(limitar(rng.uniform(lo, hi) * popularidad, lo, hi)))
