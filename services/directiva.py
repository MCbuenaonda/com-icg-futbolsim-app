"""Presidentes de federación y líderes de la afición: lógica pura (sin Mongo). Reglas en config/directiva.py."""
import random
from typing import Dict, Optional

from config import directiva as CD
from services import prensa as P


def factor_paciencia(rasgo: Optional[str]) -> float:
    return 1.0 + CD.RASGOS_PRESIDENTE.get(rasgo, {}).get("paciencia", 0.0)


def ajustar_delta_aficionados(delta: int, rasgo: Optional[str]) -> int:
    """Cambio de aficionados de un partido con el ánimo del líder (positivo o negativo)."""
    r = CD.RASGOS_LIDER.get(rasgo)
    if not r or not delta:
        return delta
    return int(round(delta * (r["pos"] if delta > 0 else r["neg"])))


def presion_lider(rasgo: Optional[str], gf: int, gc: int) -> float:
    """Presión que suma el líder sobre el DT tras un partido (derrota / victoria; el empate no suma)."""
    r = CD.RASGOS_LIDER.get(rasgo)
    if not r:
        return 0.0
    return r["presion_derrota"] if gf < gc else (r["presion_victoria"] if gf > gc else 0.0)


# --- Citas ---------------------------------------------------------------------------------------------------------------
PRESIDENTE = {
    "felicita": {"titulo": "Celebra el triunfo", "citas": ["Es un día de orgullo para todo el país: {eq} está haciendo historia.", "Gracias a los jugadores y al cuerpo técnico: ganar así es de todos.",
                                                            "Este resultado nos da la razón en el rumbo que llevamos."]},
    "respalda": {"titulo": "Respalda al técnico", "citas": ["Mi confianza en {dt} sigue intacta: el trabajo se ve en la cancha.", "Tenemos un proyecto y {dt} es parte de él.",
                                                              "El equipo va por buen camino; hay que seguir."]},
    "calma": {"titulo": "Pide calma", "citas": ["Un tropiezo no cambia nada: pido calma y respaldo para {eq}.", "No es momento de buscar culpables sino de trabajar.",
                                                  "Duele perder, pero vamos a levantarnos."]},
    "exige": {"titulo": "Exige explicaciones", "citas": ["Lo de hoy no estuvo a la altura de nuestra gente: vamos a evaluar todo, empezando por el cuerpo técnico.",
                                                         "Una derrota así no se puede repetir; esperamos respuestas.", "La paciencia tiene límite y la afición merece más."]},
    "cese": {"titulo": "Anuncia un cambio", "citas": ["La federación decidió un cambio en el banquillo: agradecemos a {dt} y confiamos en que el equipo reaccione.",
                                                     "Tomamos una decisión difícil pero necesaria: el ciclo de {dt} terminó.", "Es hora de un nuevo aire en {eq}; le deseamos lo mejor a {dt}."]},
    "eliminado": {"titulo": "Asume la eliminación", "citas": ["Queda el aprendizaje: hay que revisar el proceso con calma y volver más fuertes.", "Gracias a la afición por no soltarnos. Ahora toca reconstruir.",
                                                            "Nos duele la eliminación, pero {eq} seguirá creciendo."]},
}
REMATE_PRESIDENTE = {
    "institucional": ["Los procesos se respetan.", "Primero la institución."], "ambicioso": ["Vamos por más.", "Aquí se viene a ganar, siempre."],
    "austero": ["Y con los pies en la tierra.", "Sin gastos de más, con resultados."], "populista": ["Lo dice la gente, y la gente manda.", "Estoy con la afición."],
    "reformista": ["Hay que cambiar lo que haga falta.", "Este es solo el principio de la reforma."],
}
LIDER = {
    "fiesta": {"titulo": "Se desborda la tribuna", "citas": ["¡Qué fiesta! {eq} nos hizo felices a todos, a cantar hasta el amanecer.", "¡Se ganó! Nadie se va a casa temprano hoy.",
                                                         "La barra no para de cantar: ¡vamos {eq}!"]},
    "aguante": {"titulo": "Pide aguante", "citas": ["Un punto que se siente raro, pero la barra sigue firme con {eq}.", "No se ganó, pero tampoco se perdió: aguante, equipo.",
                                                    "Hay que seguir alentando, falta mucho."]},
    "reclamo": {"titulo": "Reclama en las gradas", "citas": ["Así no, {eq}: la afición merece que se deje todo en la cancha.", "Vinimos a alentar y nos vamos con rabia. Hay que mejorar ya.",
                                                          "Se perdió, pero la barra no se mueve de aquí."]},
    "furia": {"titulo": "Estalla la afición", "citas": ["¡Esto es una vergüenza! Queremos respuestas de jugadores y técnico.", "Una goleada así no la perdonamos: que den la cara.",
                                                       "La paciencia se acabó; la gente quiere cambios."]},
    "orgullo": {"titulo": "Orgullo de barra", "citas": ["¡Ganamos en grande! Esta camiseta se defiende así, con alma.", "Qué orgullo ver a {eq} pelear de esta manera.",
                                                       "Hoy la tribuna también jugó: ¡a seguir!"]},
}
REMATE_LIDER = {
    "festivo": ["¡Fiesta total!", "Que siga la fiesta."], "exigente": ["Pero hay que exigir más.", "Y no vamos a bajar la vara."],
    "ultra": ["¡Hasta la muerte con los colores!", "Aquí no se rinde nadie."], "humilde": ["Gracias por dejarnos estar.", "Con humildad y a seguir."],
    "carismatico": ["Que se sume más gente, hay lugar para todos.", "Súmate a la barra, ¡hay sitio para ti!"],
}


# --- Cómo reacciona la prensa ----------------------------------------------------------------------------------------------
VALOR_VOZ = {"felicita": 0.45, "respalda": 0.25, "calma": 0.15, "exige": -0.25, "cese": -0.15, "eliminado": 0.10,
             "fiesta": 0.40, "orgullo": 0.50, "aguante": 0.20, "reclamo": -0.20, "furia": -0.40}
ACCION_VOZ = {"felicita": "celebró el triunfo de {eq}", "respalda": "respaldó al cuerpo técnico", "calma": "pidió calma tras el tropiezo",
              "exige": "exigió explicaciones tras la derrota", "cese": "anunció el cambio de técnico", "eliminado": "asumió la eliminación de {eq}",
              "fiesta": "encendió la fiesta en la tribuna", "orgullo": "se mostró orgulloso de {eq}", "aguante": "pidió aguante a la afición",
              "reclamo": "reclamó desde la tribuna", "furia": "estalló contra jugadores y técnico"}
REACCION_VOZ = {   # {h} = quien habló (con su cargo), {accion} = lo que hizo
    "elogio": ["{h} {accion} y se llevó el aplauso.", "Gran gesto: {h} {accion}.", "{h} {accion}, con el ánimo que pide el momento."],
    "neutral": ["{h} {accion} tras el {gl}-{gv}.", "Después del partido, {h} {accion}.", "Se escuchó a {h}: {accion}."],
    "critica": ["{h} {accion} y las dudas siguen.", "No convenció: {h} {accion}.", "Mucho ruido: {h} {accion}."],
}
CARGO = {"presidente": "El presidente de la federación", "lider": "El líder de la barra"}


def reaccion(voz: dict, c: dict, medio: dict, periodista: dict, es_propio: bool, rng: random.Random) -> dict:
    """{tono, categoria_tono, titular, texto}: la nota de un medio sobre lo que dijo `voz` (c = contexto del lado)."""
    tono = P.tono(VALOR_VOZ[voz["tipo"]], medio, periodista, es_propio)
    cat = P.categoria_tono(tono)
    h = f"{CARGO[voz['hablante']['tipo']]} {voz['hablante']['nombre']}"
    titular = rng.choice(REACCION_VOZ[cat]).format(h=h, accion=ACCION_VOZ[voz["tipo"]].format(eq=c["eq"]), gl=c["gl"], gv=c["gv"])
    cierre = rng.choice(P.CIERRE.get(medio.get("linea"), P.CIERRE["analitica"]))
    return {"tono": tono, "categoria_tono": cat, "titular": titular, "texto": f"{titular} {cierre}"}


def _tipo_presidente(lado: dict, cese: bool) -> Optional[str]:
    if cese:
        return "cese"
    if lado.get("eliminado"):
        return "eliminado"
    res, dif = lado["res"], lado["dif"]
    if res == "V":
        return "felicita" if (lado.get("eliminacion") or dif >= 3) else "respalda"
    if res == "E":
        return "respalda"
    return "exige" if dif <= -3 else "calma"


def _tipo_lider(lado: dict) -> str:
    res, dif = lado["res"], lado["dif"]
    if res == "V":
        return "orgullo" if (lado.get("eliminacion") or dif >= 3) else "fiesta"
    if res == "E":
        return "aguante"
    return "furia" if dif <= -3 else "reclamo"


def voces_del_partido(lados: Dict[str, dict], presidentes: Dict[int, dict], lideres: Dict[int, dict], rng: random.Random) -> list:
    """lados = {'local'|'visita': {pais_id, eq, dt, res V|E|D, dif, eliminacion, eliminado, cese, goleada}}. -> [{lado, hablante {tipo,id,nombre,rasgo,rasgo_nombre}, tipo, titulo, cita}]."""
    salida = []
    for lado, d in lados.items():
        pres, lid = presidentes.get(d["pais_id"]), lideres.get(d["pais_id"])
        noticioso = bool(d.get("eliminacion") or d.get("cese") or abs(d["dif"]) >= 3 or d.get("eliminado"))
        if pres and (noticioso or rng.random() < CD.PROB_PRESIDENTE_NORMAL):
            t = _tipo_presidente(d, bool(d.get("cese")))
            cita = rng.choice(PRESIDENTE[t]["citas"]).format(eq=d["eq"], dt=d.get("dt") or "el técnico") + " " + rng.choice(REMATE_PRESIDENTE[pres["rasgo"]])
            salida.append({"lado": lado, "hablante": {"tipo": "presidente", "id": d["pais_id"], "nombre": pres["nombre"], "rasgo": pres["rasgo"], "rasgo_nombre": pres["rasgo_nombre"]},
                           "tipo": t, "titulo": PRESIDENTE[t]["titulo"], "cita": cita})
        if lid and rng.random() < CD.PROB_LIDER:
            t = _tipo_lider(d)
            cita = rng.choice(LIDER[t]["citas"]).format(eq=d["eq"]) + " " + rng.choice(REMATE_LIDER[lid["rasgo"]])
            salida.append({"lado": lado, "hablante": {"tipo": "lider", "id": d["pais_id"], "nombre": lid["nombre"], "rasgo": lid["rasgo"], "rasgo_nombre": lid["rasgo_nombre"]},
                           "tipo": t, "titulo": LIDER[t]["titulo"], "cita": cita})
    return salida
