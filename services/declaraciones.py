"""
Declaraciones (lógica pura): lo que dicen los DTs y las figuras tras un partido y cómo reacciona la prensa. Determinístico
(semilla = partido + lado): el mismo partido da siempre las mismas declaraciones. Sin Mongo: services/declaraciones_service.py
arma el contexto, llama aquí y guarda.

Una declaración tiene un TIPO (elogia al equipo, pide calma, reclama al arbitraje...), elegido según el resultado, lo que pasó en
el partido y el TEMPERAMENTO del DT (el reclamón reclama más, el sereno asume). Cada declaración lleva un VALOR (-1 a 1) que dice
qué tan bien o mal cae en la prensa; las reacciones de los medios parten de ahí y pasan por su línea editorial y el sesgo del
periodista (services/prensa.py::tono), y alimentan la reputación mediática. Tono siempre deportivo y respetuoso.
No toca el motor del partido, el ánimo ni la moral de nadie.
"""
import random
from typing import Dict, List, Optional

from services import prensa as P

PROB_DT_NORMAL = 0.35           # partidos comunes: probabilidad de que un DT hable
PROB_JUGADOR = 0.40             # que hable la figura (o el expulsado) de un lado
RATING_FIGURA = 7.6             # calificación mínima para que la figura hable
MAX_DECLARACIONES = 3           # por partido
REACCIONES_POR_DECLARACION = 2
HISTORIAS_NOTICIOSAS = {"remontada", "remontada_epica", "gol_agonico", "goleada", "paliza", "sorpresa", "hattrick", "rescate", "var_decisivo"}

# valor de cada tipo ante la prensa (cómo cae lo que dijo, antes de pasar por la línea del medio)
VALOR = {"elogia_equipo": 0.35, "respeta_rival": 0.45, "dedica": 0.5, "mira_adelante": 0.2, "pide_calma": 0.15, "asume": 0.35,
         "autocritica": 0.25, "critica_equipo": -0.3, "reclama_arbitro": -0.35, "con_diez": 0.4, "disculpas": -0.05,
         "figura": 0.5, "expulsado": -0.2}

TITULO = {"elogia_equipo": "Elogia a su equipo", "respeta_rival": "Respeta al rival", "dedica": "Dedica el triunfo", "mira_adelante": "Mira al próximo partido",
          "pide_calma": "Pide calma", "asume": "Asume la responsabilidad", "autocritica": "Reconoce que pudo más", "critica_equipo": "Critica a su equipo",
          "reclama_arbitro": "Reclama al arbitraje", "con_diez": "Aplaude jugar con diez", "disculpas": "Pide disculpas", "figura": "Comparte el mérito",
          "expulsado": "Pide perdón"}

# lo que hizo, en pasado y tercera persona (lo usan las reacciones de la prensa)
ACCION = {"elogia_equipo": "elogió el trabajo de {eq}", "respeta_rival": "respetó a {rival}", "dedica": "dedicó el resultado a la afición",
          "mira_adelante": "ya piensa en el próximo partido", "pide_calma": "pidió calma tras el golpe", "asume": "asumió la responsabilidad",
          "autocritica": "reconoció que su equipo pudo dar más", "critica_equipo": "criticó la actitud de su equipo",
          "reclama_arbitro": "reclamó con dureza al arbitraje", "con_diez": "elogió a su equipo por jugar con diez",
          "disculpas": "pidió disculpas por su expulsión", "figura": "quiso compartir el mérito con todo el equipo",
          "expulsado": "pidió perdón al equipo por su expulsión"}

CITAS_DT = {
    "elogia_equipo": ["Estoy orgulloso de {eq}: hicieron lo que les pedimos de principio a fin.", "{eq} compitió como equipo y eso es lo que más me gusta.",
                      "Los muchachos lo dieron todo y el resultado ({gl}-{gv}) lo refleja."],
    "respeta_rival": ["{rival} es un rival muy serio; el {gl}-{gv} no cuenta toda la historia.", "Hay que respetar a {rival}: nos exigió hasta el último minuto.",
                      "Le tengo mucho respeto a {rival}, hicieron un gran partido."],
    "dedica": ["Esta victoria es para nuestra gente, que nunca deja de apoyarnos.", "Se la dedicamos a la afición de {eq}: sin ella nada de esto tendría sentido.",
               "Es un triunfo para todo un país; lo celebramos juntos."],
    "mira_adelante": ["Ya pasó, toca descansar y pensar en lo que viene.", "Disfrutamos esta noche, pero mañana ya estamos trabajando en el próximo partido.",
                      "Lo importante ahora es llegar bien al siguiente compromiso."],
    "pide_calma": ["Hay que tener calma: el torneo es largo y todavía hay mucho por jugar.", "No es momento de dramatizar; el {gl}-{gv} duele, pero seguimos en pie.",
                   "Pido tranquilidad a todos: vamos a corregir lo que haya que corregir."],
    "asume": ["La responsabilidad es mía; si el equipo falló, fallé yo primero.", "Asumo lo ocurrido ante {rival}: me toca encontrar las respuestas.",
              "Los jugadores dieron lo que tenían; el que tiene que dar explicaciones soy yo."],
    "autocritica": ["Sabemos que podíamos dar más y vamos a trabajar para lograrlo.", "Hubo cosas que no salieron y es justo reconocerlo.",
                    "No estuvimos a la altura de lo que podemos hacer; lo tenemos claro."],
    "critica_equipo": ["Me voy molesto: la actitud de mi equipo no fue la que habíamos hablado.", "No puede ser que se compita así; esperaba mucho más de {eq}.",
                       "Falta carácter, y lo vamos a trabajar desde mañana."],
    "reclama_arbitro": ["No estoy de acuerdo con varias decisiones del arbitraje y lo digo con respeto.", "Hubo jugadas que cambiaron el partido y no las vi como el árbitro.",
                        "Respeto la decisión, pero creo que merecíamos otra lectura de lo que pasó."],
    "con_diez": ["Jugar con diez y competir así habla de la grandeza de este grupo.", "Con un hombre menos, mis jugadores dejaron el alma en la cancha.",
                 "Quedarnos con diez nos complicó, pero la respuesta del equipo fue admirable."],
    "disculpas": ["Me dejé llevar en el momento y le pido disculpas al cuarto árbitro y a mi equipo.", "Me expulsaron por reclamar y no estuvo bien; me comprometo a controlarme.",
                  "Reconozco mi error: mi lugar es acompañar a los jugadores, y hoy no pude."],
}
CITAS_JUGADOR = {
    "figura": ["Estoy feliz por mi partido, pero lo importante es el equipo.", "Todo el mérito es de mis compañeros; yo solo hice mi trabajo.",
               "Me sentí cómodo, pero este triunfo es de todos."],
    "expulsado": ["Me equivoqué y el equipo lo pagó; les pido perdón a mis compañeros.", "Fue una acción mía y no debió pasar: asumo la sanción.",
                  "Dejé a mis compañeros con diez y me duele; voy a aprender de esto."],
}

REACCION = {   # {h} = quien habló, {accion} = lo que hizo
    "elogio": ["{h} {accion} y se ganó el aplauso.", "Gran gesto: {h} {accion}.", "{h} {accion}, con la seriedad que pide el momento."],
    "neutral": ["{h} {accion} tras el {gl}-{gv}.", "Tras el partido, {h} {accion}.", "En zona mixta, {h} {accion}."],
    "critica": ["{h} {accion} y las dudas siguen.", "No convenció: {h} {accion}.", "Poco para tanto ruido: {h} {accion}."],
}


# --- Qué dice cada uno --------------------------------------------------------------------------------------------------
def noticioso(c: dict) -> bool:
    """¿El partido (visto desde un lado) fue lo bastante noticioso como para que su DT hable siempre?"""
    return bool(c.get("polemica_contra") or c.get("eliminacion") or abs(c.get("dif", 0)) >= 3 or c.get("dt_expulsado") or c.get("historia") in HISTORIAS_NOTICIOSAS or c.get("sorpresa"))


def tipo_dt(c: dict, rng: random.Random) -> str:
    """c: contexto del lado (res 'V'|'E'|'D', temperamento 0-100, roja_propia, penal_contra, dt_expulsado...)."""
    temp = max(0.4, min(1.8, (c.get("temperamento") or 55) / 55))
    if c.get("dt_expulsado"):
        return rng.choices(["disculpas", "reclama_arbitro", "mira_adelante"], [6, 1.5 * temp, 1])[0]
    pesos: Dict[str, float] = {}
    if c["res"] == "V":
        pesos = {"elogia_equipo": 3, "respeta_rival": 2, "dedica": 1 + (2 if c.get("eliminacion") else 0), "mira_adelante": 2}
        if c.get("roja_propia"):
            pesos["con_diez"] = 5
    elif c["res"] == "E":
        pesos = {"respeta_rival": 2, "pide_calma": 2, "mira_adelante": 2, "autocritica": 1}
        if c.get("polemica_contra"):
            pesos["reclama_arbitro"] = 3 * temp
        if c.get("roja_propia"):
            pesos["con_diez"] = 4
    else:
        pesos = {"pide_calma": 3, "asume": 2.5 / temp, "mira_adelante": 1.5, "autocritica": 1.5}
        if temp >= 1.1:
            pesos["critica_equipo"] = 1.2 * temp
        pesos["reclama_arbitro"] = (6 if c.get("polemica_contra") else 4 if (c.get("roja_propia") or c.get("penal_contra")) else 0.5) * temp
    return rng.choices(list(pesos), list(pesos.values()))[0]


CITAS_CLASICO = {"respeta_rival": ["Un clásico siempre es especial: {rival} nos exige al máximo y eso se respeta.", "Contra {rival} nunca hay partidos fáciles; es un clásico y se juega distinto.",
                                    "Estos duelos con {rival} se sienten diferente, lo saben los dos equipos."],
                 "pide_calma": ["Es un clásico y duele, pero hay que mantener la calma: contra {rival} habrá revancha.", "No hay que dramatizar: así son los clásicos con {rival}."],
                 "elogia_equipo": ["Ganar un clásico ante {rival} tiene un valor especial para todos.", "Los muchachos entendieron lo que significa jugar contra {rival}."]}


def cita(tipo: str, c: dict, rng: random.Random) -> str:
    if c.get("clasico") and tipo in CITAS_CLASICO and rng.random() < 0.6:
        return rng.choice(CITAS_CLASICO[tipo]).format(eq=c["eq"], rival=c["rival"], gl=c["gl"], gv=c["gv"])
    fuente = CITAS_DT if tipo in CITAS_DT else CITAS_JUGADOR
    return rng.choice(fuente[tipo]).format(eq=c["eq"], rival=c["rival"], gl=c["gl"], gv=c["gv"])


def declaraciones_del_partido(lados: Dict[str, dict], rng: random.Random) -> List[dict]:
    """lados = {'local': c, 'visita': c}; devuelve [{lado, hablante:{tipo,id,nombre}, tipo, valor, cita}] (máx. MAX_DECLARACIONES)."""
    salida: List[dict] = []
    for lado in ("local", "visita"):
        c = lados[lado]
        if c.get("dt_id") and (noticioso(c) or rng.random() < PROB_DT_NORMAL):
            t = tipo_dt(c, rng)
            salida.append({"lado": lado, "hablante": {"tipo": "dt", "id": c["dt_id"], "nombre": c["dt"]}, "tipo": t, "valor": VALOR[t], "cita": cita(t, c, rng),
                           "peso_orden": 1 if noticioso(c) else 0})
        expulsado, figura = c.get("expulsado"), c.get("figura")
        if expulsado and rng.random() < PROB_JUGADOR:
            salida.append({"lado": lado, "hablante": {"tipo": "jugador", **expulsado}, "tipo": "expulsado", "valor": VALOR["expulsado"], "cita": cita("expulsado", c, rng), "peso_orden": 1})
        elif figura and figura["rating"] >= RATING_FIGURA and c["res"] != "D" and rng.random() < PROB_JUGADOR:
            salida.append({"lado": lado, "hablante": {"tipo": "jugador", "id": figura["id"], "nombre": figura["nombre"]}, "tipo": "figura", "valor": VALOR["figura"],
                           "cita": cita("figura", c, rng), "peso_orden": 0})
    salida.sort(key=lambda d: -d["peso_orden"])
    return salida[:MAX_DECLARACIONES]


# --- Cómo reacciona la prensa -----------------------------------------------------------------------------------------
def reaccion(decl: dict, c: dict, medio: dict, periodista: dict, es_propio: bool, rng: random.Random) -> dict:
    """{tono, categoria_tono, titular, texto}: la nota de un medio sobre lo que dijo `decl` (c = contexto del lado de quien habló)."""
    valor = P.tono(decl["valor"], medio, periodista, es_propio, es_dt=decl["hablante"]["tipo"] == "dt")
    cat = P.categoria_tono(valor)
    accion = ACCION[decl["tipo"]].format(eq=c["eq"], rival=c["rival"])
    titular = rng.choice(REACCION[cat]).format(h=decl["hablante"]["nombre"], accion=accion, gl=c["gl"], gv=c["gv"])
    cierre = rng.choice(P.CIERRE.get(medio.get("linea"), P.CIERRE["analitica"]))
    return {"tono": valor, "categoria_tono": cat, "titular": titular, "texto": f"{titular} {cierre}"}
