"""
Niveles de Socio FIFAV: reglas de experiencia (XP) por actividad y recompensas por nivel.

Principios del diseño (ver services/niveles_service.py):
  - Se premia la PARTICIPACIÓN (hacer cosas), no la riqueza ni la suerte: ganar solo da un plus chico.
  - Variedad sobre repetición: cada acción tiene tope diario, así sube más rápido el que toca varios módulos.
  - Nada "farmeable": vender no da XP, comprar tiene tope, los abonos del admin no dan XP y los ingresos
    automáticos (dividendos, regalías) dan poca XP con tope.
  - Logros únicos ("primera vez en cada módulo") que empujan al nivel 2-3 el primer día.
  - Curva creciente: cada nivel pide 100 XP más que el anterior (xp_para_nivel).

Para agregar niveles: sumar filas a NIVELES (el umbral sale solo de xp_para_nivel). La XP sigue
acumulándose después del nivel máximo, así que los niveles nuevos se desbloquean solos.
"""


def xp_para_nivel(nivel: int) -> int:
    """XP total acumulada que pide el nivel: 0, 100, 300, 600, 1000, … (cada nivel pide 100 más que el anterior)."""
    return 50 * (nivel - 1) * nivel


# Acciones que dan XP. 'tope_diario' = cuántas veces por día calendario cuentan (None = sin tope).
# 'xp' None = el monto lo calcula quien la otorga (trivia: 5 + 5 por acierto).
REGLAS_XP = {
    "CHECKIN":             {"xp": 10,   "tope_diario": 1,    "titulo": "Check-in diario",                   "icono": "bi-calendar-check", "modulo": "misiones"},
    "CHECKIN_RACHA":       {"xp": 15,   "tope_diario": 1,    "titulo": "5.º día seguido de racha",          "icono": "bi-fire",           "modulo": "misiones"},
    "TRIVIA":              {"xp": None, "tope_diario": 3,    "titulo": "Completar una trivia (5 + 5 por acierto)", "icono": "bi-patch-question", "modulo": "misiones"},
    "SOBRE":               {"xp": 5,    "tope_diario": 5,    "titulo": "Abrir un sobre comprado",           "icono": "bi-gift",           "modulo": "album"},
    "ESTAMPA_NUEVA":       {"xp": 2,    "tope_diario": None, "titulo": "Pegar una estampa nueva",           "icono": "bi-person-square",  "modulo": "album"},
    "ESTAMPA_PLATINO":     {"xp": 15,   "tope_diario": None, "titulo": "Pegar una estampa Platino nueva",   "icono": "bi-star-fill",      "modulo": "album"},
    "PAGINA_COMPLETA":     {"xp": 100,  "tope_diario": None, "titulo": "Completar una página del álbum",    "icono": "bi-book-half",      "modulo": "album"},
    "QUINIELA":            {"xp": 10,   "tope_diario": 3,    "titulo": "Comprar un boleto de quiniela",     "icono": "bi-ticket-detailed", "modulo": "quinielas"},
    "QUINIELA_GANADA":     {"xp": 30,   "tope_diario": None, "titulo": "Ganar un boleto de quiniela",       "icono": "bi-trophy",         "modulo": "quinielas"},
    "JUEGO_VIVO":          {"xp": 20,   "tope_diario": 3,    "titulo": "Jugar un partido del Juego en Vivo", "icono": "bi-broadcast",     "modulo": "juego_en_vivo"},
    "JUEGO_VIVO_GANANCIA": {"xp": 15,   "tope_diario": None, "titulo": "Terminar el Juego en Vivo con ganancia", "icono": "bi-graph-up-arrow", "modulo": "juego_en_vivo"},
    "ONCE_IDEAL":          {"xp": 30,   "tope_diario": None, "titulo": "Armar el Once Ideal de una fase",   "icono": "bi-people-fill",    "modulo": "once_ideal"},
    "SELECCION_COMPRA":    {"xp": 20,   "tope_diario": 2,    "titulo": "Comprar una selección",             "icono": "bi-flag-fill",      "modulo": "selecciones"},
    "SELECCION_DIVIDENDO": {"xp": 5,    "tope_diario": 10,   "titulo": "Cobrar un dividendo o bono de fase", "icono": "bi-cash-coin",     "modulo": "selecciones"},
    "SEDE_COMPRA":         {"xp": 15,   "tope_diario": 2,    "titulo": "Comprar una sede",                  "icono": "bi-building",       "modulo": "sedes"},
    "SEDE_REGALIA":        {"xp": 3,    "tope_diario": 10,   "titulo": "Cobrar una regalía de sede",        "icono": "bi-coin",           "modulo": "sedes"},
}
XP_TRIVIA_BASE = 5
XP_TRIVIA_POR_ACIERTO = 5

# Logros únicos: una sola vez en la vida del usuario (sobreviven a los reinicios del Mundial).
XP_LOGRO = 50
LOGROS = {
    "PRIMER_SOBRE":       {"titulo": "Primer sobre",             "descripcion": "Abriste tu primer sobre de estampas",       "icono": "bi-gift"},
    "PRIMERA_TRIVIA":     {"titulo": "Mente futbolera",          "descripcion": "Completaste tu primera trivia",             "icono": "bi-patch-question"},
    "PRIMERA_QUINIELA":   {"titulo": "Pronosticador",            "descripcion": "Compraste tu primer boleto de quiniela",    "icono": "bi-ticket-detailed"},
    "PRIMER_JUEGO_VIVO":  {"titulo": "En la tribuna",            "descripcion": "Jugaste tu primer partido en vivo",         "icono": "bi-broadcast"},
    "PRIMER_ONCE_IDEAL":  {"titulo": "Director técnico",         "descripcion": "Armaste tu primer Once Ideal",              "icono": "bi-people-fill"},
    "PRIMERA_SELECCION":  {"titulo": "Dueño de una selección",   "descripcion": "Compraste tu primera selección",            "icono": "bi-flag-fill"},
    "PRIMERA_SEDE":       {"titulo": "Patrocinador",             "descripcion": "Compraste tu primera sede",                 "icono": "bi-building"},
    "PRIMERA_PLATINO":    {"titulo": "Edición Platino",          "descripcion": "Conseguiste tu primera estampa Platino",    "icono": "bi-star-fill"},
}

# Recompensas modestas a propósito: el plan es seguir sumando niveles. Total de los 10: 2.400 pts + 9 sobres.
# tipo PUNTOS -> usuarios.monto; SOBRES -> usuarios.sobres_gratis; 'platino' -> usuarios.sobres_platino
# (sobre con una estampa de árbitro garantizada).
NIVELES = [
    {"nivel": 1,  "titulo": "Aficionado",            "recompensas": []},
    {"nivel": 2,  "titulo": "Hincha",                "recompensas": [{"tipo": "PUNTOS", "cantidad": 150}]},
    {"nivel": 3,  "titulo": "Abonado",               "recompensas": [{"tipo": "SOBRES", "cantidad": 1}]},
    {"nivel": 4,  "titulo": "Socio",                 "recompensas": [{"tipo": "PUNTOS", "cantidad": 250}]},
    {"nivel": 5,  "titulo": "Socio Oro",             "recompensas": [{"tipo": "SOBRES", "cantidad": 2}]},
    {"nivel": 6,  "titulo": "Ultra",                 "recompensas": [{"tipo": "PUNTOS", "cantidad": 400}]},
    {"nivel": 7,  "titulo": "Capitán de la grada",   "recompensas": [{"tipo": "SOBRES", "cantidad": 2}]},
    {"nivel": 8,  "titulo": "Leyenda de la tribuna", "recompensas": [{"tipo": "PUNTOS", "cantidad": 600}]},
    {"nivel": 9,  "titulo": "Embajador FIFAV",       "recompensas": [{"tipo": "SOBRES", "cantidad": 3}]},
    {"nivel": 10, "titulo": "Inmortal FIFAV",        "recompensas": [{"tipo": "PUNTOS", "cantidad": 1000}, {"tipo": "PLATINO", "cantidad": 1}]},
]
NIVEL_MAXIMO = NIVELES[-1]["nivel"]


def nivel_para_xp(xp: int) -> int:
    """Nivel alcanzado con esa XP acumulada (tope: el último nivel definido)."""
    nivel = 1
    for fila in NIVELES:
        if xp >= xp_para_nivel(fila["nivel"]):
            nivel = fila["nivel"]
    return nivel


def datos_nivel(nivel: int) -> dict:
    return next((f for f in NIVELES if f["nivel"] == nivel), NIVELES[-1])
