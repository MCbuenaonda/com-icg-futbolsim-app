"""Disciplina (services/disciplina.py lógica pura + services/disciplina_service.py Mongo): suspensiones por tarjetas.

- Doble amarilla: `PARTIDOS_DOBLE_AMARILLA` de suspensión. Roja directa: `PARTIDOS_ROJA_DIRECTA`.
- Acumulación: `AMARILLAS_PARA_SUSPENDER` amarillas en partidos distintos suspenden `PARTIDOS_ACUMULACION` partido y el contador vuelve a 0.
  La amarilla de una doble amarilla o de una roja no cuenta para la acumulación.
- Amnistía: al llegar a la eliminación directa del Mundial (`FASE_AMNISTIA`) las amarillas acumuladas se borran.
Con los datos de 1.132 partidos: ~0,3 suspensiones por partido, casi todas por expulsión.
"""
PARTIDOS_DOBLE_AMARILLA = 1
PARTIDOS_ROJA_DIRECTA = 2
AMARILLAS_PARA_SUSPENDER = 4
PARTIDOS_ACUMULACION = 1
FASE_AMNISTIA = 8
