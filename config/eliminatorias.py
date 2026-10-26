"""
Textos del encabezado del inicio (juegos_service.get_data_fase_actual_dashboard) para cada fase de
las eliminatorias SEGÚN la confederación: cada una tiene un formato propio (grupos, tabla única o
llaves a ida y vuelta) y una cantidad distinta de rondas. Reflejan las reglas de
services/clasificacion_service.py (procesar_clasificacion_fase_N): si cambia un formato allá,
actualizar el texto aquí. Si una combinación no está, se usa 'fases.descripcion' (texto genérico).

Claves: (confederacion_id, fase_id). Confederaciones: 1 UEFA, 2 CONMEBOL, 3 CONCACAF, 4 CAF, 5 OFC,
6 AFC, 7 REPECHAJE. Las fases del Mundial (confederación 8) usan la descripción de 'fases'.
"""

# Cuántas rondas de eliminatoria juega cada confederación (para el "Ronda X de N" del encabezado)
RONDAS_POR_CONFEDERACION = {1: 2, 2: 1, 3: 3, 4: 3, 5: 4, 6: 5}

DESCRIPCION_FASE_CONFEDERACION = {
    # --- UEFA ---
    (1, 1): "Primera ronda europea: 55 selecciones repartidas en 12 grupos, todos contra todos a ida y vuelta. "
            "Los 12 líderes viajan directo al Mundial; los 12 segundos y los 4 mejores terceros siguen vivos en la ronda final.",
    (1, 2): "Ronda final europea: los 16 sobrevivientes en 4 grupos de 4, a ida y vuelta. "
            "Solo el primero de cada grupo se queda con uno de los últimos 4 boletos de Europa.",
    # --- CONMEBOL ---
    (2, 1): "La eliminatoria más pareja del mundo: las 10 selecciones sudamericanas en una tabla única, todos contra todos "
            "a ida y vuelta durante 18 fechas. Del 1° al 6° clasifican directo al Mundial y el 7° va al Repechaje Intercontinental.",
    # --- CONCACAF ---
    (3, 1): "Ronda preliminar: las 4 selecciones de menor ranking se miden en 2 llaves a ida y vuelta. "
            "Los ganadores por gol global se suman a la segunda ronda.",
    (3, 2): "Segunda ronda: 6 grupos a ida y vuelta. El 1° y el 2° de cada grupo avanzan a la ronda final; el resto queda eliminado.",
    (3, 3): "Ronda final: 12 selecciones en 3 grupos de 4, a ida y vuelta. Los dos primeros de cada grupo clasifican al Mundial "
            "y los 2 mejores terceros van al Repechaje Intercontinental.",
    # --- CAF ---
    (4, 1): "Fase de grupos africana: 54 selecciones en 9 grupos de 6, a ida y vuelta. Cada líder de grupo clasifica directo "
            "al Mundial; los 4 mejores segundos pasan a los play-offs.",
    (4, 2): "Semifinales de los play-offs africanos: los 4 mejores segundos se cruzan en 2 llaves a ida y vuelta; "
            "avanzan los ganadores por gol global.",
    (4, 3): "Final de los play-offs africanos: una última llave a ida y vuelta. El ganador representa a África "
            "en el Repechaje Intercontinental.",
    # --- OFC ---
    (5, 1): "Ronda preliminar de Oceanía: las 4 selecciones de menor ranking juegan 2 llaves a ida y vuelta; "
            "los ganadores por gol global pasan a la fase de grupos.",
    (5, 2): "Fase de grupos de Oceanía: 2 grupos a ida y vuelta. El 1° y el 2° de cada grupo avanzan a las semifinales.",
    (5, 3): "Semifinales de Oceanía: los 4 mejores de la fase de grupos se cruzan en 2 llaves a ida y vuelta; "
            "los ganadores juegan la final.",
    (5, 4): "Final de Oceanía: una llave a ida y vuelta. El ganador se queda con el único boleto directo de la OFC "
            "y el perdedor va al Repechaje Intercontinental.",
    # --- AFC ---
    (6, 1): "Ronda preliminar asiática: las 20 selecciones de menor ranking se enfrentan en 10 llaves a ida y vuelta; "
            "los ganadores por gol global avanzan a la segunda ronda.",
    (6, 2): "Segunda ronda asiática: 36 selecciones en 9 grupos de 4, a ida y vuelta. El 1° y el 2° de cada grupo "
            "pasan a la tercera ronda.",
    (6, 3): "Tercera ronda asiática: 18 selecciones en 3 grupos de 6, a ida y vuelta. Los dos primeros de cada grupo "
            "clasifican al Mundial; el 3° y el 4° siguen en la cuarta ronda.",
    (6, 4): "Cuarta ronda asiática: 6 selecciones en 2 grupos de 3, a ida y vuelta. Cada líder clasifica al Mundial; "
            "los segundos se juegan la quinta ronda.",
    (6, 5): "Quinta ronda asiática: los dos segundos de la cuarta ronda definen en una llave a ida y vuelta quién "
            "representa a Asia en el Repechaje Intercontinental.",
    # --- Repechaje Intercontinental ---
    (7, 6): "Repechaje Intercontinental: 6 selecciones de CONMEBOL, CONCACAF, CAF, AFC y OFC en 2 grupos de 3. "
            "El primero de cada grupo gana uno de los 2 últimos boletos al Mundial.",
}
