"""Homenajes a leyendas (services/homenajes.py lógica pura + services/homenajes_service.py Mongo).

En los partidos importantes —eliminación directa (fase >= FASE_HONOR) o un Clásico entre rivales (services/relaciones_service.py)— se rinde homenaje a UNA
leyenda de uno de los dos equipos (determinístico por partido, ponderada por su fama). Su selección suma aficionados (global, con historial): entre
PCT_MIN y PCT_MAX de los que ya tiene, según la fama de la leyenda comprimida con raíz cuadrada para no favorecer de más a las selecciones grandes, y con
un TOPE_POR_SELECCION de homenajes por Mundial. Las leyendas no «dicen» nada: muchas son personas reales retiradas y algunas ya fallecieron; el
homenaje funciona igual para todas.
"""
FASE_HONOR = 8
PCT_MIN = 0.004
PCT_MAX = 0.012
TOPE_POR_SELECCION = 5
