"""Premios del Mundial (services/premios.py lógica pura + services/premios_service.py Mongo).

Al cerrar el Mundial (la Gran Final), un jurado de periodistas —uno por medio— vota las categorías de abajo entre los mejores candidatos de la Copa
(fase >= FASE_COPA). Antes del cierre se muestra «La carrera por los premios» con quién lidera cada una por mérito. Los votos pasan por el sesgo del
periodista (patriota / crítico) y la línea del medio (sensacionalista premia goles, analítica premia la calificación). Efecto: cada premio suma a la
reputación mediática del ganador. No toca el motor ni la economía.
"""
FASE_COPA = 7
BOLETA = 8                 # candidatos que entran a la votación (los de más mérito)
PUNTOS_VOTO = (3, 2, 1)    # primer, segundo y tercer lugar de cada boleta
MIN_PARTIDOS = {"jugador": 2, "portero": 2, "joven": 2, "tecnico": 2, "arbitro": 1}
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
}
