"""Polémicas arbitrales (services/polemicas.py lógica pura + services/polemicas_service.py Mongo).

Un partido es POLÉMICO si suma puntos de `PESOS` (jugadas que cambian o discuten el resultado); con `UMBRAL_NOTA` o más, 1 a 3 medios
publican una nota sobre el árbitro responsable (el VAR si decidió él, el central si fue una decisión de campo) y el DT perjudicado lo
reclama en su rueda de prensa. La reputación del árbitro (`prensa_reputacion`, tipo `arbitro`) se recupera con el tiempo y pesa en la
DESIGNACIÓN de los centrales de la eliminación directa (fase >= `FASE_DESIGNACION`): mejor imagen, más probabilidad de recibir los
partidos grandes; con reputación pésima queda apartado hasta recuperarse. No toca nada más del motor.
"""
PESOS = {"gol_anulado_decisivo": 1.0, "gol_anulado": 0.45, "penal_anulado": 0.6, "roja_por_var": 0.6, "penal_decisivo": 0.55}
# penal_decisivo (decisión del central): un penal convertido que le dio el empate o la victoria a quien lo recibió; es lo que más mueve la
# reputación de los CENTRALES, que son los que se sortean por reputación en la eliminación directa
UMBRAL_NOTA = 0.5
MAX_NOTAS = 3

FASE_DESIGNACION = 8            # eliminación directa
RECUPERACION_POR_PARTIDO = 0.985  # el puntaje se desgasta ×0,985 por cada partido terminado desde la última nota (~22% a los 100 partidos)
PESO_REPUTACION = 1.5           # peso de designación = max(PESO_MINIMO, 1 + PESO_REPUTACION × puntaje/100)
PESO_MINIMO = 0.15
UMBRAL_APARTADO = -35           # con este puntaje (ya desgastado) o peor, el central no recibe partidos de eliminación directa
