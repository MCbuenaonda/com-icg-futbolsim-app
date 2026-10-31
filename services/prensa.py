"""
Prensa (lógica pura): qué medios opinan de un partido y qué dicen. Determinístico (semilla = partido + medio): el mismo partido
da siempre las mismas publicaciones. Sin Mongo: services/prensa_service.py arma el contexto, llama aquí y guarda.

Cada publicación lleva su TONO (-1 a 1) hacia lo que comenta, que después alimentará la reputación mediática. El tono sale de:
  - el resultado (o la calificación, si habla de un jugador) y lo sorprendente que fue,
  - la LÍNEA editorial del medio (sensacionalista exagera, analítica modera, crítica es dura, oficialista y optimista suavizan,
    popular sigue a la afición),
  - el SESGO del periodista (patriota favorece a los suyos, crítico los castiga),
  - el estado de ánimo del jugador (llega eufórico o frustrado).
"""
import random
import zlib
from typing import Dict, List, Optional

MAX_PUBLICACIONES = 6
ANIMO = {"Eufórico": 0.12, "Motivado": 0.06, "Concentrado": 0.0, "Nervioso": -0.04, "Insatisfecho": -0.08, "Decepcionado": -0.12, "Frustrado": -0.14}


def semilla(*partes) -> random.Random:
    return random.Random(zlib.crc32("|".join(str(p) for p in partes).encode()))


def limitar(x: float, lo=-1.0, hi=1.0) -> float:
    return max(lo, min(hi, x))


def categoria_tono(t: float) -> str:
    return "elogio" if t > 0.3 else ("critica" if t < -0.3 else "neutral")


# --- Qué medios cubren el partido ------------------------------------------------------------------------------------
def relevancia(ctx: dict) -> float:
    """0..1: qué tan noticioso fue el partido (más relevancia = más medios «interesados» de otros países)."""
    r = 0.25
    r += min(0.3, abs(ctx["dif"]) * 0.08)
    r += 0.2 if ctx["eliminacion"] else 0
    r += 0.15 if ctx.get("historia") in {"remontada", "remontada_epica", "gol_agonico", "goleada", "paliza", "sorpresa", "hattrick", "rescate"} else 0
    r += 0.2 if ctx.get("sorpresa") else 0
    return min(1.0, r)


def elegir_medios(ctx: dict, medios: List[dict], rng: random.Random) -> List[dict]:
    """[(medio, rol)] rol: 'local'|'visita' (medio de uno de los países) o 'interesado'. A lo sumo MAX_PUBLICACIONES."""
    elegidos, usados = [], set()
    for lado in ("local", "visita"):
        propios = [m for m in medios if m.get("pais_id") == ctx[lado]["id"]]
        for m in propios:
            p = 0.95 if m["papel"] == "deportivo" else 0.6 + 0.3 * relevancia(ctx)
            if rng.random() < p:
                elegidos.append((m, lado))
                usados.add(m["id"])
    rel = relevancia(ctx)
    n_interesados = 1 + (1 if rel > 0.45 else 0) + (1 if rel > 0.7 else 0)
    conf = {ctx["local"].get("confederacion_id"), ctx["visita"].get("confederacion_id")}
    candidatos = [m for m in medios if m["id"] not in usados]
    pesos = [m["nivel"] * (2.5 if m.get("confederacion_id") in conf else 1.0) * (3.0 if m.get("pais_id") is None else 1.0) for m in candidatos]
    for _ in range(n_interesados):
        if not candidatos:
            break
        i = rng.choices(range(len(candidatos)), weights=pesos)[0]
        elegidos.append((candidatos.pop(i), "interesado"))
        pesos.pop(i)
    rng.shuffle(elegidos)
    return elegidos[:MAX_PUBLICACIONES]


# --- Tono -------------------------------------------------------------------------------------------------------------
def tono(base: float, medio: dict, periodista: dict, es_propio: bool, es_dt=False, animo: Optional[str] = None) -> float:
    t = base
    linea = medio.get("linea")
    if linea == "sensacionalista":
        t *= 1.3
    elif linea == "analitica":
        t *= 0.8
    elif linea == "critica":
        t -= 0.25
    elif linea == "oficialista":
        t = t * 0.6 if t < 0 else t
        t += 0.2 if es_dt else 0.05
    elif linea == "optimista":
        t += 0.25
    elif linea == "popular" and t > 0:
        t += 0.15
    sesgo = periodista.get("sesgo")
    if sesgo == "patriota":
        t += 0.3 if es_propio else -0.12
    elif sesgo == "critico" and es_propio:
        t -= 0.3
    if periodista.get("estilo") == "polemista":
        t *= 1.2
    if animo:
        t += ANIMO.get(animo, 0.0)
    return round(limitar(t), 2)


# --- Textos por piezas (apertura según tipo y tono + dato del estilo + cierre de la línea) -----------------------------
APERTURA = {
    ("PARTIDO", "elogio"): ["{eq} se llevó el {gl}-{gv} ante {rival} con autoridad.", "Noche redonda de {eq}: {gl}-{gv} sobre {rival}.",
                            "{eq} le ganó a {rival} ({gl}-{gv}) y dejó una gran impresión.", "Triunfo sin discusión de {eq} contra {rival}, {gl}-{gv}."],
    ("PARTIDO", "neutral"): ["{eq} y {rival} se repartieron lo que dejó el {gl}-{gv}.", "Partido de trámite parejo entre {eq} y {rival}: {gl}-{gv}.",
                             "El {gl}-{gv} entre {eq} y {rival} deja más preguntas que respuestas.", "{eq} y {rival} firmaron un {gl}-{gv} sin sobresaltos."],
    ("PARTIDO", "critica"): ["{eq} cayó {gl}-{gv} ante {rival} y las dudas crecen.", "Tropiezo de {eq}: {gl}-{gv} frente a {rival}.",
                             "{eq} no estuvo a la altura contra {rival} ({gl}-{gv}).", "Mala tarde de {eq}: {rival} lo superó por {gl}-{gv}."],
    ("PARTIDO", "elogio_corto"): ["{eq} sufrió pero se llevó el {gl}-{gv} ante {rival}.", "Por la mínima, {eq} le ganó a {rival} ({gl}-{gv}).",
                                  "{eq} ganó {gl}-{gv} a {rival} en un partido de detalles."],
    ("PARTIDO", "critica_corto"): ["{eq} cayó por la mínima ante {rival} ({gl}-{gv}).", "Detalles que le costaron caro a {eq}: {gl}-{gv} frente a {rival}.",
                                   "{eq} perdió {gl}-{gv} ante {rival} y se queda con la sensación de que pudo más."],
    ("OPINION", "elogio"): ["Hay que reconocerlo: {eq} está jugando mejor que casi todos.", "{eq} ya no sorprende: se ganó el respeto de todos con el {gl}-{gv} a {rival}.",
                            "Cuando {eq} juega así, el resto tiene que tomar nota."],
    ("OPINION", "neutral"): ["Con el {gl}-{gv} sobre {rival}, aún es pronto para saber de qué es capaz {eq}.", "{eq} tiene cosas buenas y cosas por corregir tras el {gl}-{gv}.",
                             "Ni para celebrar ni para alarmarse: así quedó {eq} después del {gl}-{gv}."],
    ("OPINION", "critica"): ["Se acabó la paciencia con {eq}: el {gl}-{gv} ante {rival} no tiene excusa.", "Algo no funciona en {eq} y el {gl}-{gv} lo deja a la vista.",
                             "Si {eq} quiere aspirar a algo, tiene que explicar lo del {gl}-{gv} ante {rival}."],
    ("JUGADOR", "elogio"): ["{fig} fue el mejor de la cancha en el {gl}-{gv} de {eq} ({rating}).", "{fig} está en otro nivel: {rating} de calificación ante {rival}.",
                            "Con {fig} así, {eq} sueña: {rating} en el {gl}-{gv} a {rival}."],
    ("JUGADOR", "neutral"): ["{fig} cumplió ante {rival}, sin más ({rating}).", "Discreto {fig} en el {gl}-{gv}: {rating} de calificación.",
                             "{fig} pasó por el partido sin dejar huella ({rating})."],
    ("JUGADOR", "critica"): ["{fig} estuvo irreconocible contra {rival} ({rating}).", "Noche para el olvido de {fig}: {rating} en el {gl}-{gv}.",
                             "{fig} no apareció y {eq} lo pagó ({rating})."],
    ("DT", "elogio"): ["{dt} acertó en todo en el {gl}-{gv} de {eq} ante {rival}.", "La mano de {dt} se nota: {eq} ganó con orden.", "{dt} le ganó la partida táctica a {rival}."],
    ("DT", "neutral"): ["{dt} sigue buscando la fórmula de {eq} tras el {gl}-{gv}.", "Sin brillo pero sin sustos: así quedó {dt} con {eq}.",
                        "{dt} dejó dudas y certezas en el {gl}-{gv} de {eq}."],
    ("DT", "critica"): ["¿Hasta cuándo {dt}? {eq} cayó {gl}-{gv} ante {rival}.", "{dt} se quedó sin respuestas contra {rival} ({gl}-{gv}).",
                        "El banco de {eq} falló: {dt} no leyó el partido ante {rival}."],
}
DATO = {   # lo que agrega cada estilo de periodista
    "analista": ["Los números lo explican: {tiros} tiros y {pos}% de posesión.", "Táctica pura: el partido se decidió en el medio campo.", "Hay un patrón: quien controla la pelota, manda."],
    "polemista": ["Y que nadie me venga con excusas.", "Se dirá lo que se quiera, pero así de claro fue.", "Quien no lo vea, no vio el partido."],
    "cronista": ["El estadio contuvo el aliento en cada llegada.", "Fue un partido de esos que se cuentan despacio.", "En la tribuna se vivió cada minuto como una final."],
    "entrevistador": ["Pedimos declaraciones al vestuario y nadie quiso hablar.", "Tras el pitazo, fuentes del equipo reconocieron el golpe.", "En zona mixta el ánimo lo decía todo."],
    "sensacionalista": ["¡INCREÍBLE lo que se vivió!", "¡Nadie lo vio venir!", "Un partido que se recordará por años (¿o por semanas?)."],
    "estadistico": ["{eq} suma {pts} puntos y {gf} goles a favor en el torneo.", "Es el {gl}-{gv} número {n} del torneo en este tipo de partidos.", "Con este resultado, la diferencia de gol queda en {dif:+d}."],
}
CIERRE = {   # lo que agrega la línea editorial del medio
    "sensacionalista": ["¿Escándalo a la vista?", "El vestuario es un volcán.", "Esto no termina aquí."],
    "analitica": ["Habrá que ver los próximos partidos para confirmar la tendencia.", "Los datos dicen que no fue casualidad.", "El contexto importa más que el marcador."],
    "critica": ["Exigimos más.", "Así no se llega lejos.", "Alguien tendrá que dar la cara."],
    "oficialista": ["Hay que darles confianza.", "El proyecto sigue su camino.", "La federación respalda el trabajo."],
    "optimista": ["Lo mejor está por venir.", "De esto se aprende y se sale adelante.", "Hay motivos para sonreír."],
    "popular": ["La afición lo vivió como suyo.", "Así se siente el fútbol en la calle.", "El pueblo ya tiene su tema de conversación."],
}


def redactar(tipo: str, tono_v: float, medio: dict, periodista: dict, c: dict, rng: random.Random) -> dict:
    cat = categoria_tono(tono_v)
    clave = cat + "_corto" if tipo == "PARTIDO" and cat != "neutral" and abs(c.get("dif", 2)) <= 1 else cat
    datos = dict(c, rating=c.get("rating", ""), n=rng.randint(2, 9))
    apertura = rng.choice(APERTURA[(tipo, clave)]).format(**datos)
    dato = rng.choice(DATO.get(periodista.get("estilo"), DATO["cronista"])).format(**datos)
    cierre = rng.choice(CIERRE.get(medio.get("linea"), CIERRE["analitica"]))
    return {"titular": apertura, "texto": f"{apertura} {dato} {cierre}", "categoria_tono": cat}


# --- Reputación mediática (puntaje -100..100 de un jugador, un DT o una selección) ----------------------------------------
# Cada partido, lo que dijeron los medios sobre alguien (promedio de sus tonos, cada medio pesa según su alcance y su credibilidad)
# se suma a su puntaje, que se desgasta con cada nueva nota: lo reciente pesa más. Los efectos usan el puntaje CENTRADO (menos la
# media de su tipo, porque en promedio la prensa elogia un poco) para no mover el equilibrio general.
REP_DECAY = 0.85
REP_K = 25.0
REP_MEDIA = {"pais": 6.2, "jugador": 12.8, "dt": 3.0}   # promedio observado de cada tipo (reconstruir_reputacion, 720 partidos)
EFECTO_RIESGO_MARCA = 0.10      # puntos de riesgo por punto de reputación centrada (±10 en los extremos)
EFECTO_ENCAJE_MARCA = 0.08      # puntos de encaje (±8)
EFECTO_PRESION_DT = 0.12        # presión por partido de un DT con -100 de reputación (+0,12)
PESO_NIVEL = {2: 1.0, 3: 1.2, 4: 1.4}


def peso_medio(medio: dict) -> float:
    return PESO_NIVEL.get(medio.get("nivel", 2), 1.0) * (medio.get("credibilidad", 0.6) / 0.6)


def nuevo_puntaje(actual: float, notas: List[float]) -> float:
    """notas = [tono × peso del medio] de las publicaciones de UN partido sobre esa persona o selección."""
    if not notas:
        return actual
    return round(limitar(REP_DECAY * actual + REP_K * (sum(notas) / len(notas)), -100, 100), 2)


def centrado(tipo: str, puntaje: float) -> float:
    return limitar(puntaje - REP_MEDIA.get(tipo, 0.0), -100, 100)


def etiqueta_reputacion(c: float) -> str:
    return "Muy buena" if c >= 25 else "Buena" if c >= 8 else "Normal" if c > -8 else "Mala" if c > -25 else "Pésima"


# --- Pronósticos (antes del partido) -----------------------------------------------------------------------------------
GAMMA_ESTILO = {"estadistico": 3.0, "analista": 2.0, "cronista": 1.5, "entrevistador": 1.5, "polemista": 0.8, "sensacionalista": 0.6}   # qué tanto se pega al favorito
MARCADORES = {"L": [(1, 0), (2, 0), (2, 1), (3, 1), (3, 0)], "E": [(1, 1), (0, 0), (2, 2), (1, 1)], "V": [(0, 1), (0, 2), (1, 2), (1, 3), (0, 3)]}


def pronostico(medio: dict, periodista: dict, probs, lado_propio: Optional[str], rng: random.Random) -> dict:
    """{pick 'L'|'E'|'V', marcador (gl, gv), confianza}. probs = (gana local, empate, gana visita) del modelo conservador."""
    gamma = GAMMA_ESTILO.get(periodista.get("estilo"), 1.5)
    pesos = {k: max(0.001, p) ** gamma for k, p in zip("LEV", probs)}
    sesgo = periodista.get("sesgo")
    if lado_propio and sesgo == "patriota":
        pesos["L" if lado_propio == "local" else "V"] *= 1.7
    elif lado_propio and sesgo == "critico":
        pesos["L" if lado_propio == "local" else "V"] *= 0.7
    if medio.get("linea") == "sensacionalista":
        pesos["E"] *= 0.6
    pick = rng.choices(list(pesos), list(pesos.values()))[0]
    return {"pick": pick, "marcador": list(rng.choice(MARCADORES[pick])), "confianza": round(dict(zip("LEV", probs))[pick], 2)}


FRASES_PRONOSTICO = {"L": ["{eq} se lleva el partido: {gl}-{gv}.", "Mi apuesta: {gl}-{gv} para {eq}.", "{eq} debería imponerse por {gl}-{gv}."],
                     "V": ["{eq} sale con los tres puntos: {gv}-{gl}.", "Mi apuesta: {gv}-{gl} para {eq}.", "{eq} debería imponerse por {gv}-{gl} de visita."],
                     "E": ["Veo un empate {gl}-{gv} entre {eq} y {rival}.", "Pocas diferencias: {gl}-{gv} y a repartir los puntos."]}


def texto_pronostico(pick: str, marcador, local: str, visita: str, rng: random.Random) -> str:
    eq, rival = (local, visita) if pick != "V" else (visita, local)
    return rng.choice(FRASES_PRONOSTICO[pick]).format(eq=eq, rival=rival, gl=marcador[0], gv=marcador[1])
