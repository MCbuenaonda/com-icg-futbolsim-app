"""Premios del Mundial (services/premios.py lógica pura + services/premios_service.py Mongo).

Al cerrar el Mundial (la Gran Final), un jurado de periodistas —uno por medio— vota las categorías de abajo entre los mejores candidatos de la Copa
(fase >= FASE_COPA). Antes del cierre se muestra «La carrera por los premios» con quién lidera cada una por mérito. Los votos pasan por el sesgo del
periodista (patriota / crítico) y la línea del medio (sensacionalista premia goles, analítica premia la calificación). Efecto: cada premio suma a la
reputación mediática del ganador. No toca el motor ni la economía.
"""
FASE_COPA = 7
BOLETA = 8                 # candidatos que entran a la votación (los de más mérito)
PUNTOS_VOTO = (3, 2, 1)    # primer, segundo y tercer lugar de cada boleta
MIN_PARTIDOS = {"jugador": 2, "portero": 2, "joven": 2, "tecnico": 2, "arbitro": 1, "goleador": 1, "juego_limpio": 3, "partido": 1}
EDAD_JOVEN = 21
RUIDO = 0.55               # incertidumbre del voto de cada periodista (en desviaciones del mérito)
SESGO_PATRIOTA = 0.60
SESGO_CRITICO = -0.40
SESGO_LINEA = 0.35         # cuánto pesa lo que le gusta a cada línea editorial
VALOR_REPUTACION = 0.85    # tono de la nota que suma a la reputación del ganador (peso 1,5)

CATEGORIAS = {
    "jugador": {"nombre": "Mejor jugador del Mundial", "icono": "bi-star-fill", "color": "#eab308", "tipo": "jugador"},
    "portero": {"nombre": "Mejor portero", "icono": "bi-hand-index-thumb-fill", "color": "#38bdf8", "tipo": "jugador"},
    "joven": {"nombre": "Mejor jugador joven", "icono": "bi-lightning-charge-fill", "color": "#22c55e", "tipo": "jugador"},
    "tecnico": {"nombre": "Mejor director técnico", "icono": "bi-clipboard2-check-fill", "color": "#a78bfa", "tipo": "dt"},
    "arbitro": {"nombre": "Mejor árbitro", "icono": "bi-flag-fill", "color": "#f97316", "tipo": "arbitro"},
    # Premios por los NÚMEROS (`directo`: sin jurado, los decide el marcador y las tarjetas; la nota de prensa solo lo reporta) y el del jurado por drama
    "goleador": {"nombre": "Bota de Oro (máximo goleador)", "icono": "bi-bullseye", "color": "#f59e0b", "tipo": "jugador", "directo": True},
    "juego_limpio": {"nombre": "Premio Juego Limpio", "icono": "bi-heart-fill", "color": "#10b981", "tipo": "pais", "directo": True},
    "partido": {"nombre": "Partido del Mundial", "icono": "bi-fire", "color": "#ef4444", "tipo": None},
}
# Juego limpio: puntos de sanción por partido (amarilla 1, doble amarilla 2, roja directa 3); gana la selección con menos por partido (desempata la que más partidos jugó).
PUNTOS_TARJETA = {"AMARILLA": 1, "DOBLE": 2, "ROJA": 3}
# Partido del Mundial: mérito = goles totales x PESO_GOLES + peso de su historia (cronica.historia, 0-1) x PESO_HISTORIA + PESO_ELIMINACION si fue eliminación directa
PESO_GOLES = 0.35
PESO_HISTORIA = 3.0
PESO_ELIMINACION = 0.6
HISTORIA_DRAMA = {"remontada_epica": (0.95, "remontada épica"), "tanda": (0.90, "definición por penales"), "agonico": (0.86, "gol agónico"), "paliza": (0.85, "paliza"),
                  "hat_trick": (0.82, "hat-trick"), "sorpresa": (0.82, "batacazo"), "var_decisivo": (0.78, "el VAR decidió"), "leyenda_decisiva": (0.78, "una leyenda decidió"),
                  "con_diez": (0.72, "ganó con diez"), "remontada": (0.70, "remontada"), "empate_agonico": (0.70, "empate agónico"), "rescate": (0.68, "rescate"),
                  "ajuste_decisivo": (0.66, "la pizarra del DT"), "goleada": (0.60, "goleada"), "empate_loco": (0.60, "empate loco")}
