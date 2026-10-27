"""
El DIRECTOR TÉCNICO dentro del partido (lógica pura, sin base de datos; la usa simular_service).

Cada selección tiene un DT en funciones (paises.dt_id → 'directores_tecnicos', ver services/tecnicos_service.py).
Sus rasgos permanentes (0..100) mueven el partido así:
  - estilo              → la táctica que elige (ofensivo prefiere 4-3-3, defensivo 4-4-2, equilibrado 3-5-2).
  - confianza_leyendas  → cuántas leyendas pone de titulares (0 a 3).
  - motivacion          → plus/malus chico de todos los atributos de su equipo, más el EFECTO TÉCNICO NUEVO
                          (plus que se desvanece en sus primeros partidos en el cargo).
  - lectura             → el AJUSTE TÁCTICO en vivo: si pierde, manda al equipo al ataque; si gana por la mínima,
                          cierra el partido. Ganar algo de un lado cuesta del otro; con buena lectura lo hace antes
                          y gana más de lo que cede (con mala lectura, al revés).
  - temperamento        → los RECLAMOS: un medidor de enojo que sube con los goles en contra, las tarjetas a sus
                          jugadores, el VAR en contra... y baja con el tiempo. Reclama, el central (más con más
                          rigor) lo amonesta y a la segunda lo expulsa: el ayudante toma el mando, no hay más
                          ajustes y el equipo lo siente un poco el resto del partido.

Los efectos se aplican como un AJUSTE de atributos por jugador (jugador["_ajuste"] = {general, ataque, defensa}),
que services/desgaste.py suma después del cansancio: así todos los duelos del motor lo sienten sin tocar cada
fórmula. Calibrado con Monte Carlo: +4 puntos en todos los atributos de un equipo = +11 puntos de probabilidad de
ganar, así que el DT mueve menos de un punto: entre el mejor y el peor DT hay ~3-5 puntos de probabilidad de ganar,
y en promedio el torneo no cambia (los rasgos están centrados en REFERENCIA).
Sin DT (dt=None) todo se comporta como antes: táctica y leyendas al azar, sin ajustes ni reclamos.
"""
import random

from services import desgaste
from typing import List, Optional, Tuple

REFERENCIA = 55.0                 # rasgo "promedio" (agregar_tecnicos: gauss(55, 13)); centra los efectos en 0
ESCALA = 40.0                     # (rasgo - REFERENCIA) / ESCALA ≈ -1..+1

# Qué atributos son "de ataque" y "de defensa" para el ajuste: desgaste.ATRIBUTOS_ATAQUE_DT / ATRIBUTOS_DEFENSA_DT
# (agresividad no está: cambiaría las faltas y las tarjetas)

# --- Antes del partido ----------------------------------------------------------------------------------------
TACTICAS_POR_ESTILO = {
    "ofensivo": {"4-3-3": 55, "3-5-2": 25, "4-4-2": 20},
    "equilibrado": {"3-5-2": 40, "4-3-3": 30, "4-4-2": 30},
    "defensivo": {"4-4-2": 55, "3-5-2": 25, "4-3-3": 20},
}
MOTIVACION_MAX = 0.6              # puntos de atributo con motivación 95 (y -0.6 con 15)
EFECTO_TECNICO_NUEVO = [0.8, 0.5, 0.25]   # plus en sus 3 primeros partidos en el cargo

# --- Ajuste táctico en vivo -----------------------------------------------------------------------------------
AJUSTE_PUNTOS = 3.0               # lo que se gana de un lado y se cede del otro (DT promedio)
AJUSTE_VENTAJA_LECTURA = 0.4      # con lectura 95 gana 3*(1.4) y cede 3*(0.6)
MINUTO_AJUSTE = 70                # DT promedio; la lectura lo adelanta/atrasa hasta 12'
PROB_AJUSTE_POR_MINUTO = 0.18

# --- Reclamos -------------------------------------------------------------------------------------------------
ENOJO = {"gol_en_contra": 14, "gol_anulado_propio": 28, "penal_en_contra": 16,
         "amarilla_propia": 9, "roja_propia": 22, "falta_propia": 1.5, "fuera_de_lugar_propio": 2.5}
ENOJO_DECAE_POR_MINUTO = 1.2
UMBRAL_RECLAMO = 18
PROB_RECLAMO_MAX = 0.55
PROB_AMONESTACION = 0.36          # por reclamo, DT promedio y central promedio
FACTOR_REINCIDENCIA = 1.5         # cada reclamo después del primero
MALUS_EXPULSADO = 0.5

TIPOS_GOL = ("⚽ GOL", "⚽ GOL DE TIRO LIBRE", "⚽ GOL DE CÓRNER")


def q(dt: Optional[dict], rasgo: str) -> float:
    """Rasgo normalizado a -1..+1 (0 = DT promedio o sin DT)."""
    if not dt:
        return 0.0
    return max(-1.0, min(1.0, (float(dt.get(rasgo, REFERENCIA) or REFERENCIA) - REFERENCIA) / ESCALA))


# --- Formación: elección con contexto y cambio en vivo (catálogo en config/formaciones.py) ---------------------
def elegir_esquema(dt: Optional[dict], ctx: Optional[dict] = None, rng=random) -> dict:
    """
    El DT elige el esquema del partido: parte de las preferencias de su ESTILO y las mueve según el contexto:
      - la postura que pide el partido: favorito -> más ofensiva, inferior -> más defensiva; en la vuelta de una serie,
        ganando el global cierra y perdiendo ataca; de local, un poco más ofensiva;
      - la racha: con mala racha cambia el esquema que venía usando, con buena lo repite;
      - su historial: los esquemas con los que suma más puntos;
      - el esquema probable del rival: busca el que le gana el medio/las bandas; verlo depende de su LECTURA
        (con mala lectura a veces elige al revés).
    ctx: {fuerza (diferencia de gol esperada, + favorito), forma (0..1), local, serie: {"vuelta", "global"},
          eliminacion, historial {esquema: {pj, pts}}, ultimo, rival_probable}
    -> {"esquema", "postura", "etiqueta", "motivo"}
    """
    import math
    from config import formaciones as CF
    from services import formaciones as FS
    ctx = ctx or {}
    estilo = (dt or {}).get("estilo") or "equilibrado"
    pref = CF.PREFERENCIAS_ESTILO.get(estilo, CF.PREFERENCIAS_ESTILO["equilibrado"])
    fuerza = float(ctx.get("fuerza") or 0.0)
    objetivo = 0.6 * max(-1.0, min(1.0, fuerza)) + (0.15 if ctx.get("local") else -0.05)
    serie = ctx.get("serie") or {}
    if serie.get("vuelta"):
        if serie.get("global", 0) > 0:
            objetivo = min(objetivo, -0.6)
        elif serie.get("global", 0) < 0:
            objetivo = max(objetivo, 0.7)
    elif ctx.get("eliminacion") and fuerza < 0:
        objetivo -= 0.2
    objetivo = max(-1.0, min(1.0, objetivo))
    lectura = q(dt, "lectura")
    ultimo, forma, rival = ctx.get("ultimo"), ctx.get("forma"), ctx.get("rival_probable")
    pesos = {}
    for e in CF.ESQUEMAS:
        w = pref.get(e, 1) * math.exp(-((FS.postura(e) - objetivo) ** 2) / (2 * CF.ANCHO_POSTURA ** 2))
        if ultimo == e and forma is not None:
            w *= 0.35 if forma <= CF.MALA_RACHA else (2.0 if forma >= CF.BUENA_RACHA else 1.0)
        h = (ctx.get("historial") or {}).get(e) or {}
        if h.get("pj", 0) >= CF.MINIMO_HISTORIAL:
            w *= 0.6 + 0.4 * (h.get("pts", 0) / h["pj"]) / 1.5
        if rival:
            w *= math.exp(CF.PESO_VENTAJA_RIVAL * lectura * FS.ventaja(e, rival) / 5.0)
        pesos[e] = w
    esquema = rng.choices(list(pesos), weights=list(pesos.values()))[0]
    d = FS.datos(esquema)
    # el porqué (lo que más pesó)
    if serie.get("vuelta") and serie.get("global", 0) > 0 and d["postura"] < 0:
        motivo = f"Sale con {esquema} para cuidar la ventaja del global"
    elif serie.get("vuelta") and serie.get("global", 0) < 0 and d["postura"] > 0:
        motivo = f"Necesita remontar el global: apuesta por el {esquema}"
    elif ultimo and forma is not None and forma <= CF.MALA_RACHA and esquema != ultimo:
        motivo = f"Tras la mala racha cambia el {ultimo} por el {esquema}"
    elif ultimo and forma is not None and forma >= CF.BUENA_RACHA and esquema == ultimo:
        motivo = f"Repite el {esquema} que le viene dando resultados"
    elif rival and lectura > 0.2 and FS.ventaja(esquema, rival) > 1.5:
        motivo = f"Lee el {rival} del rival y busca ganarle el medio con el {esquema}"
    elif fuerza >= 0.4 and d["postura"] >= 0.3:
        motivo = f"Sale a dominar como favorito con el {esquema}"
    elif fuerza <= -0.4 and d["postura"] <= -0.3:
        motivo = f"Se protege ante un rival superior: {esquema} y contragolpe"
    else:
        motivo = f"Fiel a su estilo {estilo}, juega con el {esquema}"
    return {"esquema": esquema, "postura": d["postura"], "etiqueta": d["etiqueta"], "motivo": motivo}


def esquema_probable(dt: Optional[dict], ultimo: Optional[str] = None) -> str:
    """Lo que un DT rival "suele" usar (para que el otro lo lea): el último que usó o el favorito de su estilo."""
    from config import formaciones as CF
    if ultimo in CF.FORMACIONES:
        return ultimo
    pref = CF.PREFERENCIAS_ESTILO.get((dt or {}).get("estilo") or "equilibrado", CF.PREFERENCIAS_ESTILO["equilibrado"])
    return max(pref, key=pref.get)


def esquema_en_vivo(dt: Optional[dict], actual: str, inicial: str, ajuste: Optional[str]) -> str:
    """El ajuste táctico en vivo como cambio de esquema: «ataque» -> uno más ofensivo de su repertorio, «cerrar» -> uno
    más defensivo, None/«normal» -> vuelve al inicial. Elige, entre los que van en esa dirección, el que más le gusta."""
    from config import formaciones as CF
    from services import formaciones as FS
    if not ajuste or ajuste == "normal":
        return inicial
    p = FS.postura(actual)
    pref = CF.PREFERENCIAS_ESTILO.get((dt or {}).get("estilo") or "equilibrado", CF.PREFERENCIAS_ESTILO["equilibrado"])
    if ajuste == "ataque":
        candidatos = [e for e in CF.ESQUEMAS if p < FS.postura(e) <= p + 0.8]
    else:
        candidatos = [e for e in CF.ESQUEMAS if p - 0.8 <= FS.postura(e) < p]
    if not candidatos:
        return actual
    return max(candidatos, key=lambda e: (pref.get(e, 0), abs(FS.postura(e) - p)))


def elegir_tactica(dt: Optional[dict], tacticas: List[str], rng=random) -> str:
    if not dt:
        return rng.choice(tacticas)
    pesos = TACTICAS_POR_ESTILO.get(dt.get("estilo"), TACTICAS_POR_ESTILO["equilibrado"])
    return rng.choices(tacticas, weights=[pesos.get(t, 1) for t in tacticas])[0]


def pesos_cantidad_leyendas(dt: Optional[dict]) -> Optional[List[float]]:
    """Pesos para arrancar con 0, 1, 2 o 3 leyendas (sin DT: los cuatro iguales, como antes)."""
    if not dt:
        return None
    c = q(dt, "confianza_leyendas")      # -1 = no confía (casi siempre 0-1), +1 = las pone (2-3)
    return [max(0.15, 1 - 0.8 * c), max(0.15, 1 - 0.3 * c), max(0.15, 1 + 0.3 * c), max(0.15, 1 + 0.8 * c)]


def plus_inicial(dt: Optional[dict], partidos_en_cargo: int) -> float:
    if not dt:
        return 0.0
    nuevo = EFECTO_TECNICO_NUEVO[partidos_en_cargo] if 0 <= partidos_en_cargo < len(EFECTO_TECNICO_NUEVO) else 0.0
    return MOTIVACION_MAX * q(dt, "motivacion") + nuevo


# --- Estado del banco durante el partido ------------------------------------------------------------------------
class Banco:
    """Lo que el DT de un equipo hace en el partido. Se crea en simular_partido_realista, uno por equipo."""

    def __init__(self, dt: Optional[dict], equipo: str, partidos_en_cargo: int = 99):
        self.dt = dt
        self.equipo = equipo
        self.nombre = (dt or {}).get("nombre")
        self.plus = plus_inicial(dt, partidos_en_cargo)
        self.ajuste = None          # None / "ataque" / "cerrar"
        self.enojo = 0.0
        self.reclamos = 0
        self.amonestado = False
        self.expulsado = False
        self.ultimo_minuto = 0.0

    @property
    def activo(self) -> bool:
        return self.dt is not None

    def ajustes(self) -> dict:
        """Lo que se suma a los atributos de cada jugador del equipo (ver desgaste._refrescar)."""
        general = self.plus - (MALUS_EXPULSADO if self.expulsado else 0.0)
        ataque = defensa = 0.0
        if self.ajuste:
            v = q(self.dt, "lectura") * AJUSTE_VENTAJA_LECTURA
            gana, cede = AJUSTE_PUNTOS * (1 + v), AJUSTE_PUNTOS * (1 - v)
            ataque, defensa = (gana, -cede) if self.ajuste == "ataque" else (-cede, gana)
        return {"general": round(general, 3), "ataque": round(ataque, 3), "defensa": round(defensa, 3)}

    def aplicar(self, plantilla: list) -> None:
        aj = self.ajustes()
        for j in plantilla:
            j["_ajuste"] = aj
            desgaste.refrescar(j)

    # --- ajuste táctico ---
    def minuto_ajuste(self) -> float:
        return MINUTO_AJUSTE - 12 * q(self.dt, "lectura")

    def evaluar_ajuste(self, minuto: float, diferencia: int, rng=random) -> Optional[str]:
        """Una vez por minuto de juego. diferencia = goles propios - ajenos (global en ida y vuelta).
        Devuelve el ajuste nuevo si lo hubo."""
        if not self.activo or self.expulsado or minuto < self.minuto_ajuste():
            return None
        deseado = "ataque" if diferencia < 0 else ("cerrar" if diferencia == 1 and minuto >= self.minuto_ajuste() + 8 else self.ajuste)
        if diferencia == 0 and self.ajuste == "cerrar":
            deseado = None                 # le empataron: se deshace el cerrojo
        if deseado == self.ajuste or rng.random() > PROB_AJUSTE_POR_MINUTO:
            return None
        self.ajuste = deseado
        return deseado or "normal"

    # --- reclamos ---
    def pasar_tiempo(self, minuto: float) -> None:
        self.enojo = max(0.0, self.enojo - ENOJO_DECAE_POR_MINUTO * max(0.0, minuto - self.ultimo_minuto))
        self.ultimo_minuto = minuto

    def reaccionar(self, motivo: str, rigor: float, rng=random) -> Optional[str]:
        """Suma enojo por algo que le pasó a su equipo y decide si reclama.
        Devuelve None, "reclamo", "amonestado" o "expulsado"."""
        if not self.activo or self.expulsado:
            return None
        self.enojo += ENOJO.get(motivo, 0)
        if self.enojo < UMBRAL_RECLAMO:
            return None
        temperamento = 0.5 + float(self.dt.get("temperamento", REFERENCIA) or REFERENCIA) / 100.0   # 0.65..1.45
        if rng.random() > min(PROB_RECLAMO_MAX, (self.enojo - UMBRAL_RECLAMO + 6) / 60.0 * temperamento):
            return None
        self.reclamos += 1
        self.enojo *= 0.55
        prob = PROB_AMONESTACION * temperamento * (rigor or 1.0) * (FACTOR_REINCIDENCIA ** (self.reclamos - 1))
        if rng.random() > min(0.9, prob):
            return "reclamo"
        if self.amonestado:
            self.expulsado = True
            self.ajuste = None
            return "expulsado"
        self.amonestado = True
        return "amonestado"


def motivos_de_evento(evento: dict, ultimo_gol_equipo: Optional[str], local: str, visita: str) -> List[Tuple[str, str]]:
    """[(equipo cuyo DT se enoja, motivo)] por un evento recién narrado."""
    t, eq = evento.get("tipo"), evento.get("equipo")
    rival = {local: visita, visita: local}
    salida = []
    if t in TIPOS_GOL and eq in rival:
        salida.append((rival[eq], "gol_en_contra"))
    elif t == "🖥️ VAR - GOL ANULADO" and ultimo_gol_equipo in rival:
        salida.append((ultimo_gol_equipo, "gol_anulado_propio"))
    elif t == "🎯 PENAL" and eq in rival:
        salida.append((rival[eq], "penal_en_contra"))
    elif t == "🟨 TARJETA AMARILLA" and eq in rival:
        salida.append((eq, "amarilla_propia"))
    elif t in ("🟥 TARJETA ROJA", "🟨🟥 DOBLE AMARILLA", "🖥️ VAR - ROJA DIRECTA") and eq in rival:
        salida.append((eq, "roja_propia"))
    elif t == "🛑 FALTA" and eq in rival:
        salida.append((eq, "falta_propia"))
    elif t == "🚩 FUERA DE LUGAR" and eq in rival:
        salida.append((eq, "fuera_de_lugar_propio"))
    return salida


# --- Textos -------------------------------------------------------------------------------------------------
TEXTOS_AJUSTE = {
    "ataque": ["{dt} ({equipo}) manda a su equipo al ataque: adelanta las líneas y mete más gente en el área.",
               "Desde el banco, {dt} pide ir a buscarlo: {equipo} se para más arriba y asume riesgos.",
               "{dt} mueve el tablero: {equipo} pasa a jugar con tres arriba y los laterales bien abiertos."],
    "cerrar": ["{dt} ({equipo}) ordena cerrar el partido: líneas juntas, el bloque atrás y a cuidar la ventaja.",
               "{dt} pide calma y orden: {equipo} se repliega para defender el resultado.",
               "Desde el banco, {dt} manda a bajar el ritmo: {equipo} se cierra atrás y juega al contragolpe."],
    "normal": ["{dt} ({equipo}) vuelve al plan inicial: el equipo se reacomoda en su dibujo de siempre.",
               "Tras el empate, {dt} reordena a {equipo} y deshace el cerrojo."],
}
TEXTOS_RECLAMO = ["{dt}, DT de {equipo}, protesta airadamente al cuarto árbitro.",
                  "{dt} sale del área técnica a reclamar: no está de acuerdo con la decisión.",
                  "Fastidio en el banco de {equipo}: {dt} gesticula y le pide explicaciones al central."]
TEXTOS_AMONESTADO = ["{arbitro} se acerca al banco y le muestra la amarilla a {dt} ({equipo}) por sus protestas.",
                     "Amonestación para {dt}, DT de {equipo}: {arbitro} no le tolera más reclamos."]
TEXTOS_EXPULSADO = ["¡{arbitro} expulsa a {dt}! El DT de {equipo} vio la segunda amarilla por protestar y se va a la tribuna; su ayudante toma el mando.",
                    "{dt} se pasó de la raya: {arbitro} lo echa del banco y {equipo} se queda sin su técnico el resto del partido."]


def texto(plantillas: List[str], rng=random, **kw) -> str:
    return rng.choice(plantillas).format(**kw)
