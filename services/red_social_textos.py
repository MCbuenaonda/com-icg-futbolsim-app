"""
Textos de las publicaciones de las MARCAS en la red social (firmas de patrocinio, rumores, renovaciones, despedidas y
respuestas a los partidos de sus patrocinados). Lógica pura, sin base de datos.

Para que no se lean repetidos, cada texto se arma combinando piezas (apertura + cuerpo + cierre), con la voz del
rubro de la marca (sus productos, emojis y hashtags) y una semilla por publicación: la misma publicación siempre
dice lo mismo, pero dos firmas distintas casi nunca coinciden (miles de combinaciones por tipo).
Español de Latinoamérica con «tú» / «ustedes».
"""
import random
import re
import unicodedata
from typing import List, Optional

# Voz de cada rubro: cómo habla la marca de lo suyo
VOZ_RUBRO = {
    "indumentaria": {"producto": ["nuestra camiseta", "la nueva colección", "nuestra ropa de entrenamiento", "la línea de juego"],
                     "emoji": ["👕", "🔥", "⚡", "🧵"], "tag": ["#VisteLaCancha", "#HechoParaJugar", "#SegundaPiel"]},
    "calzado": {"producto": ["nuestros botines", "los nuevos tachones", "la nueva suela", "nuestros tenis"],
                "emoji": ["👟", "⚡", "💨", "🦶"], "tag": ["#CadaPasoCuenta", "#PisaFuerte", "#VelocidadPura"]},
    "bebidas": {"producto": ["nuestra bebida", "la edición de campeonato", "cada lata", "nuestro sabor"],
                "emoji": ["🥤", "🧊", "🍹", "💧"], "tag": ["#Refresca", "#SaborDeTribuna", "#BrindaPorElGol"]},
    "alimentos": {"producto": ["nuestros productos", "la energía de cada mañana", "nuestra receta", "el snack del hincha"],
                  "emoji": ["🍽️", "🌽", "🥐", "🍫"], "tag": ["#EnergíaReal", "#SaborDeCasa", "#AlimentaTuJuego"]},
    "tecnologia": {"producto": ["nuestra tecnología", "nuestros datos", "la nueva plataforma", "nuestros equipos"],
                   "emoji": ["💡", "🤖", "📊", "🛰️"], "tag": ["#FuturoEnJuego", "#DatosQueGanan", "#Innovación"]},
    "telefonia": {"producto": ["nuestra red", "la señal más rápida", "nuestros planes", "la app"],
                  "emoji": ["📱", "📶", "📲", "🔊"], "tag": ["#SiempreConectados", "#SeñalDeCampeón", "#MásCerca"]},
    "automotriz": {"producto": ["nuestros autos", "el nuevo modelo", "nuestra flotilla", "cada motor"],
                   "emoji": ["🚗", "🏁", "⚙️", "🛞"], "tag": ["#PotenciaEnRuta", "#LlegaPrimero", "#MotorDeCampeón"]},
    "banca": {"producto": ["nuestra banca", "nuestras tarjetas", "cada inversión", "nuestra app financiera"],
              "emoji": ["💳", "🏦", "📈", "🤝"], "tag": ["#SolidezDeCampeón", "#InvierteEnTuJuego", "#Confianza"]},
    "aerolineas": {"producto": ["nuestros vuelos", "cada destino", "nuestra tripulación", "la nueva ruta"],
                   "emoji": ["✈️", "🌍", "🧳", "🛫"], "tag": ["#VolamosContigo", "#DespegaConTuSelección", "#ElMundoEsLaCancha"]},
    "energia": {"producto": ["nuestra energía", "cada estación", "nuestro combustible", "la energía limpia"],
                "emoji": ["⚡", "🔋", "☀️", "🔥"], "tag": ["#EnergíaQueMueve", "#FuerzaQueNoSeApaga", "#PrendeElPartido"]},
    "seguros": {"producto": ["nuestra protección", "cada póliza", "nuestro respaldo", "la cobertura total"],
                "emoji": ["🛡️", "🤝", "🧱", "✅"], "tag": ["#LaMejorDefensa", "#CubrimosCadaJugada", "#Tranquilidad"]},
    "videojuegos": {"producto": ["nuestro juego", "la nueva temporada", "nuestro canal", "el modo carrera"],
                    "emoji": ["🎮", "🕹️", "👾", "🏆"], "tag": ["#PresionaStart", "#GameOn", "#TuPróximaJugada"]},
    "lujo": {"producto": ["nuestra colección", "cada pieza", "nuestros relojes", "la edición limitada"],
             "emoji": ["⌚", "💎", "✨", "🖤"], "tag": ["#ElTiempoDeLosGrandes", "#Precisión", "#Legado"]},
}

# --- FIRMA (anuncio de un patrocinio nuevo) ---------------------------------------------------------------
FIRMA_APERTURA = [
    "¡Es oficial! {e}", "Bienvenido a la familia {marca}. {e}", "Llegó el día que esperábamos. {e}", "Nuevo integrante del equipo {e}",
    "Lo anunciamos con orgullo: {e}", "Esto ya es una realidad {e}", "Primera noticia de la semana y es enorme {e}",
    "Un sí que suena fuerte {e}", "Atención, que esto se pone bueno {e}", "Teníamos ganas de contarlo {e}",
    "Firmado y sellado ✍️", "Hoy empieza algo grande {e}",
]
FIRMA_JUGADOR = [
    "{nombre} es nuestro nuevo embajador y va a jugar con {producto}.",
    "{nombre} se suma a {marca}: talento de {pais} con nuestra marca en cada partido.",
    "{nombre} ({pais}) firma con nosotros por {ciclos} ciclos.",
    "A partir de hoy, {nombre} representa a {marca} dentro y fuera de la cancha.",
    "{nombre} eligió {producto} para lo que viene con {pais}.",
    "La cara de nuestra próxima campaña ya tiene nombre: {nombre}.",
    "Sumamos a {nombre}, una pieza clave de {pais}, a nuestro equipo de embajadores.",
    "{nombre} y {marca}: una alianza pensada para hacer historia con {pais}.",
    "Confiamos en {nombre} y {nombre_corto} confía en {producto}. Así de simple.",
    "{nombre} ya es parte de {marca}. Lo que viene con {pais} lo vivimos juntos.",
]
FIRMA_SELECCION = [
    "Somos patrocinadores oficiales de la selección de {nombre}.",
    "{marca} acompaña a {nombre} en su camino al Mundial.",
    "La selección de {nombre} lleva {producto} en cada partido a partir de hoy.",
    "Firmamos con {nombre}: {ciclos} ciclos para vivir el fútbol juntos.",
    "Nos ponemos la camiseta de {nombre}, ahora de manera oficial.",
    "{nombre} y {marca}, una sola afición desde hoy.",
    "Toda la energía de {marca} detrás de la selección de {nombre}.",
    "Orgullosos de ser la marca que acompaña a {nombre} en cada partido.",
    "La afición de {nombre} ahora también es nuestra afición.",
]
FIRMA_CIERRE = [
    "{lema}.", "Vamos con todo 💪", "Esto apenas empieza.", "Bienvenido, {nombre_corto}.", "Nos vemos en la cancha.",
    "¡A romperla juntos!", "Gracias por la confianza.", "Que ruede el balón ⚽", "Lo mejor está por venir.",
    "¿Ya viste el anuncio completo? 👀", "Dale la bienvenida en los comentarios 👇", "",
]

# --- RUMOR (la marca busca embajador entre varios) --------------------------------------------------------
RUMOR_APERTURA = [
    "👀 Algo se está cocinando en {marca}…", "Estamos buscando a nuestro próximo embajador.", "Se viene una firma importante. 🤫",
    "Nuestra próxima campaña necesita una figura. ¿Quién será?", "Hay reuniones, hay llamadas… y hay una lista corta.",
    "Pista: juega al fútbol y es muy bueno 😏", "No podemos decir mucho todavía, pero…", "Rumores de pasillo en {marca} 🗣️",
    "Se dice, se comenta… 👂", "Nuestro equipo de marketing no duerme desde hace días 😅",
]
RUMOR_CUERPO = [
    "En la lista corta están {candidatos}.", "Los nombres que suenan: {candidatos}.", "¿{candidatos}? Pronto lo sabrás.",
    "Entre {candidatos} anda el juego.", "Tenemos los ojos puestos en {candidatos}.",
    "Las opciones sobre la mesa: {candidatos}.", "Tres palabras: {candidatos}. Bueno, son nombres 😄",
    "Si te decimos {candidatos}, ¿a quién eliges?", "Solo uno vestirá {producto}: {candidatos}.",
]
RUMOR_CIERRE = [
    "¿A quién elegirían ustedes? 👇", "Haz tu apuesta en los comentarios.", "Muy pronto, novedades.", "Stay tuned 📡",
    "Activa las notificaciones 🔔", "No digas que no te avisamos.", "{tag}", "La decisión, en el próximo ciclo.", "",
]

# --- RENOVACIÓN y DESPEDIDA --------------------------------------------------------------------------------
RENOVACION = [
    "Seguimos juntos {e} {marca} renueva con {nombre} por {ciclos} ciclos más.",
    "No había dudas: {nombre} sigue siendo parte de {marca}. {e}",
    "Renovamos la confianza en {nombre}. ¡Por más partidos juntos! {e}",
    "{nombre} y {marca}, capítulo dos. {e} Gracias por todo lo que viene.",
    "Lo bueno se renueva: {nombre} continúa con {producto}. {e}",
    "Otra vez juntos. {nombre} extiende su vínculo con {marca} {e}",
    "Seguimos escribiendo esta historia con {nombre}. {lema}. {e}",
    "{marca} + {nombre}: renovado hasta nuevo aviso {e}",
]
DESPEDIDA = [
    "Gracias, {nombre}, por los ciclos compartidos. Te deseamos lo mejor. {e}",
    "Cerramos una etapa con {nombre}. Siempre serás parte de la historia de {marca}.",
    "Nuestro vínculo con {nombre} llega a su fin. Gracias por cada partido.",
    "{marca} y {nombre} toman caminos distintos. Éxito en lo que viene.",
    "Fin de ciclo con {nombre}. Agradecemos el compromiso y te deseamos suerte.",
    "Después de un tiempo juntos, decidimos no continuar con {nombre}. Gracias por todo.",
    "Hasta aquí llegamos con {nombre}. Mucha suerte en la próxima etapa. 🙏",
]

# --- REACCIÓN a un partido (respuesta en el hilo del post del partido) -----------------------------------
REACCION = {
    "gol": ["¡GOOOL de {nombre}! {e} Con {producto}, nada es imposible.", "{nombre} la mandó a guardar {e} ¡Así se hace!",
            "Ese gol de {nombre} tiene nuestro sello {e}", "{nombre} apareció cuando más se necesitaba {e} ¡Golazo!",
            "Le pegaste perfecto, {nombre_corto} {e}", "Gol de nuestro embajador {e} {tag}",
            "¡Qué definición, {nombre_corto}! {e}", "{nombre} no perdona {e}"],
    "doblete": ["¡Doblete de {nombre}! {e}{e} Dos veces nos hizo gritar.", "Dos goles de {nombre} {e} Y la noche sigue.",
                "{nombre} se llevó la pelota… casi. ¡Doblete! {e}", "¡Doble ración de {nombre}! {e}"],
    "hattrick": ["¡HAT-TRICK de {nombre}! {e}{e}{e} Histórico.", "Tres goles. Tres. {nombre} está en otra dimensión {e}",
                 "La pelota se va a casa con {nombre} {e} ¡Hat-trick!", "Se acabaron los adjetivos para {nombre} {e}"],
    "asistencia": ["Qué pase de {nombre} {e} Eso también es jugar con {producto}.", "{nombre} la sirvió en bandeja {e}",
                   "Asistencia de lujo de {nombre} {e}", "El gol es de todos, pero el pase es de {nombre} {e}"],
    "valla": ["Valla invicta para {nombre} {e} {lema}.", "Cero goles en contra con {nombre} atrás {e}",
              "{nombre} cerró la puerta con candado {e}", "Nadie pasó por donde estaba {nombre} {e}"],
    "roja": ["Hoy no fue el día de {nombre}. Seguimos contigo.", "Una roja no define a nadie. Fuerza, {nombre_corto}.",
             "Partido difícil para {nombre}. El próximo será mejor.", "Toca aprender y volver más fuertes, {nombre_corto}."],
    "victoria": ["¡Ganó {pais}! {e} Orgullosos de {nombre}.", "Victoria con sello de {nombre} {e}",
                 "Así se juega: triunfo de {pais} con {nombre} en cancha {e}", "Tres puntos que saben a {producto} {e}",
                 "¡Vamos {pais}! {e} {tag}", "Otro triunfo para celebrar con {nombre} {e}",
                 "Ganar siempre se siente bien, y más con {nombre} {e}"],
    "goleada_favor": ["¡Qué paliza! {e} {pais} no tuvo piedad.", "Goleada con {nombre} en el campo {e} Así da gusto.",
                      "Partidazo de {pais} {e} ¡Fiesta total!", "{marcador} y a otra cosa. {e} {tag}",
                      "Noche perfecta para {pais} {e}"],
    "empate": ["Empate que deja ganas de más. Vamos, {nombre_corto} {e}", "Un punto y a seguir. {lema}.",
               "Partido cerrado para {pais}. El próximo se gana {e}", "Ni ganamos ni perdimos: seguimos sumando con {nombre}.",
               "Repartieron puntos. {nombre} dejó todo {e}", "Empate con sabor a revancha {e}"],
    "derrota": ["Hoy no se dio. Seguimos contigo, {nombre_corto} {e}", "Las derrotas también enseñan. Fuerza, {pais}.",
                "No fue el resultado esperado, pero el apoyo no cambia {e}", "A levantar la cabeza, {nombre_corto}. Viene otro partido.",
                "Día complicado para {pais}. Seguimos juntos {e}", "Perder duele, rendirse no es opción {e}"],
    "goleada_contra": ["Noche dura para {pais}. Estamos para las buenas y las malas.", "Golpe fuerte, pero esto sigue. Ánimo, {nombre_corto}.",
                       "Hay partidos para olvidar. Este es uno. A seguir.", "Toca dar vuelta la página, {pais} 💪"],
}
REACCION_CIERRE = ["", "", "{tag}", "{lema}.", "#Vamos{pais_tag}", "{e}"]


def _semilla(*partes) -> random.Random:
    return random.Random("|".join(str(p) for p in partes))


def _limpiar(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([.,!?])", r"\1", t)
    return t


def _tag_pais(pais: Optional[str]) -> str:
    plano = unicodedata.normalize("NFKD", pais or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]", "", plano)


def _corto(nombre: str) -> str:
    partes = (nombre or "").split()
    return partes[-1] if len(partes) > 1 and len(partes[-1]) > 3 else (nombre or "")


def handle_marca(nombre: str) -> str:
    plano = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return "@" + re.sub(r"[^A-Za-z0-9]", "", plano.replace("&", "y"))


def _ctx(marca: dict, rng: random.Random, **datos) -> dict:
    voz = VOZ_RUBRO.get(marca.get("rubro"), VOZ_RUBRO["indumentaria"])
    nombre = datos.get("nombre") or ""
    return {"marca": marca.get("nombre", ""), "lema": marca.get("lema", ""), "producto": rng.choice(voz["producto"]),
            "e": rng.choice(voz["emoji"]), "tag": rng.choice(voz["tag"]), "nombre_corto": _corto(nombre),
            "pais_tag": _tag_pais(datos.get("pais")), **datos}


def _armar(piezas: List[List[str]], ctx: dict, rng: random.Random) -> str:
    return _limpiar(" ".join(rng.choice(p).format(**ctx) for p in piezas))


def texto_firma(marca: dict, tipo: str, nombre: str, pais: str, ciclos: int, semilla) -> str:
    rng = _semilla("firma", semilla)
    ctx = _ctx(marca, rng, nombre=nombre, pais=pais, ciclos=ciclos)
    cuerpo = FIRMA_SELECCION if tipo == "seleccion" else FIRMA_JUGADOR
    return _armar([FIRMA_APERTURA, cuerpo, FIRMA_CIERRE], ctx, rng)


def texto_rumor(marca: dict, candidatos: List[str], semilla) -> str:
    rng = _semilla("rumor", semilla)
    if len(candidatos) > 1:
        lista = ", ".join(candidatos[:-1]) + " o " + candidatos[-1]
    else:
        lista = candidatos[0] if candidatos else "alguien muy especial"
    ctx = _ctx(marca, rng, candidatos=lista, nombre="")
    return _armar([RUMOR_APERTURA, RUMOR_CUERPO, RUMOR_CIERRE], ctx, rng)


def texto_renovacion(marca: dict, nombre: str, pais: str, ciclos: int, semilla) -> str:
    rng = _semilla("renov", semilla)
    return _limpiar(rng.choice(RENOVACION).format(**_ctx(marca, rng, nombre=nombre, pais=pais, ciclos=ciclos)))


def texto_despedida(marca: dict, nombre: str, pais: str, semilla) -> str:
    rng = _semilla("adios", semilla)
    return _limpiar(rng.choice(DESPEDIDA).format(**_ctx(marca, rng, nombre=nombre, pais=pais)))


def situacion_reaccion(tipo: str, resultado: str, diferencia: int, aporte_jugador: Optional[dict]) -> Optional[str]:
    """Qué comenta la marca: lo del jugador manda (hat-trick, doblete, gol, roja, asistencia, valla) y si no, el resultado."""
    if tipo == "jugador":
        if not aporte_jugador:
            return None   # no jugó: la marca no comenta
        goles = aporte_jugador.get("gol", 0)
        if goles >= 3:
            return "hattrick"
        if goles == 2:
            return "doblete"
        if goles == 1:
            return "gol"
        if aporte_jugador.get("roja"):
            return "roja"
        if aporte_jugador.get("asistencia"):
            return "asistencia"
        if aporte_jugador.get("valla_invicta"):
            return "valla"
    if resultado == "victoria":
        return "goleada_favor" if diferencia >= 3 else "victoria"
    if resultado == "derrota":
        return "goleada_contra" if diferencia <= -3 else "derrota"
    return "empate"


def texto_reaccion(marca: dict, situacion: str, nombre: str, pais: str, marcador: str, semilla, usadas: Optional[set] = None) -> str:
    """'usadas': plantillas ya usadas en el mismo hilo (dos marcas no responden con la misma frase al mismo partido)."""
    rng = _semilla("reac", semilla)
    ctx = _ctx(marca, rng, nombre=nombre, pais=pais, marcador=marcador)
    opciones = [t for t in REACCION[situacion] if t not in (usadas or set())] or REACCION[situacion]
    plantilla = rng.choice(opciones)
    if usadas is not None:
        usadas.add(plantilla)
    return _limpiar(plantilla.format(**ctx) + " " + rng.choice(REACCION_CIERRE).format(**ctx))
