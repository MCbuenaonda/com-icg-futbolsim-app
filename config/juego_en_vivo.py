"""
Valores por defecto del "Juego en Vivo" (services/juego_en_vivo_service.py).

Todo lo ajustable del juego vive acá, no en la lógica: la entrada, las cuotas por favoritismo,
los niveles de riesgo, el cooldown y las reglas de puntos por evento. Las reglas además se
siembran en la colección 'event_point_rules' (ver configurar_juego_en_vivo.py) para poder
ajustarlas en Mongo sin tocar código; si esa colección está vacía, el servicio usa
REGLAS_PUNTOS_DEFAULT de este archivo.
"""

# Entrada que se descuenta de usuarios.monto al elegir país; al terminar el partido se acreditan
# los puntos finales 1 a 1 (0 si quedó eliminado).
ENTRADA_MONTO = 1000

# Cuota inicial de puntos según la probabilidad de victoria del país ELEGIDO. Se calcula con la
# fórmula de Elo sobre 'estadisticas.poder' de 'internacional' (la forma en el torneo, la misma
# referencia de favoritismo que usa el scouter) pero con una escala propia: el 'poder' va de
# ~-25 a ~+45, y con la escala clásica de 400 todo partido daría ~50%.
# Brecha moderada a propósito: medido con 240 partidos simulados, HOY el motor no hace ganar más
# al de mayor 'poder' ni al de mejor plantel (todos los atributos están en ~60), así que una
# brecha grande le regalaría puntos al que elige underdog. Si el motor empieza a distinguir
# equipos (atributos que crecen), conviene recalibrar ESCALA_PODER_PROBABILIDAD y las cuotas.
ESCALA_PODER_PROBABILIDAD = 100.0
UMBRAL_FAVORITO_PCT = 60.0
UMBRAL_UNDERDOG_PCT = 40.0
CUOTAS_INICIALES = {
    "favorito": 900,
    "equilibrado": 1000,
    "underdog": 1100,
}

# Niveles de riesgo: el multiplicador afecta por igual a los puntos positivos y negativos.
NIVELES_RIESGO = {
    1.0: "Conservador",
    1.5: "Moderado",
    2.0: "Arriesgado",
    3.0: "Extremo",
}
MULTIPLICADOR_INICIAL = 1.0

# Durante la transmisión el riesgo se puede cambiar una vez cada COOLDOWN_RIESGO_SEGUNDOS (reales),
# o antes si se revela un gol después del último cambio. El cambio entra en vigor
# DEMORA_ACTIVACION_SEGUNDOS después de pedirlo: un "⏳ PREPARACIÓN" de tiro se revela ~2s antes
# de su desenlace, y sin esta demora se podría subir el riesgo sabiendo que viene una jugada.
COOLDOWN_RIESGO_SEGUNDOS = 60
DEMORA_ACTIVACION_SEGUNDOS = 10
TIPOS_EVENTO_LIBERAN_COOLDOWN = ("⚽ GOL", "⚽ GOL DE TIRO LIBRE", "⚽ GOL DE CÓRNER", "⚽ GOL DE PENAL")

# Reglas de puntos por evento. Calibradas con Monte Carlo (240 partidos simulados) para que a x1
# el saldo final medio quede cerca de la entrada (~1060): casi todo es simétrico ("lo que suma un
# lado lo resta el otro"). Con los valores originales (gol en contra -200, tiro al arco rival -15,
# atajada +40, asistencia +80) la media daba ~1310 a x1 y ~1910 a x3 -- subir el riesgo siempre
# convenía y cada partido inflaba usuarios.monto. Con estos valores: x1 media ~1060 / 4% llega a 0;
# x3 media ~1430 pero mediana ~835 y 44% llega a 0 (más premio posible, mucho más riesgo). 'aplica_a' compara el 'equipo' del evento (tal cual lo arma
# services/simular_service.py) con el país elegido:
#   "propio" -> el evento es del país elegido; "rival" -> es del otro; "resultado" -> se evalúa
#   con el ÚLTIMO evento del partido contra resultado.ganador_lado (no con el "🏁 PITIDO FINAL":
#   en eliminación directa la tanda de penales se narra DESPUÉS del pitido, y dar el bono ahí
#   adelantaría quién gana la tanda). Por eso las reglas de resultado no llevan tipos_evento.
# OJO con la atribución del motor: en atajadas, desvíos y penales fallados el 'equipo' es el del
# ARQUERO; en faltas y tarjetas, el del infractor. Un mismo evento puede disparar varias reglas
# (ej. una atajada de mi arquero = "atajada_importante" + "tiro_al_arco_rival").
# 'descripcion' admite {pais} / {rival} (nombres reales del partido).
# 'condicion': None | "con_asistencia" (⚽ GOL con asistente) | "victoria" | "empate" | "derrota".
_GOLES_EN_JUGADA = ["⚽ GOL", "⚽ GOL DE TIRO LIBRE", "⚽ GOL DE CÓRNER"]
_ATAJADAS = ["🧤 ATAJADA ESPECTACULAR", "🖐️ DESVÍO A CÓRNER"]
_AMARILLAS = ["🟨 TARJETA AMARILLA", "🖥️ VAR - TARJETA REVISADA"]  # la revisada es una roja rebajada a amarilla
_ROJAS = ["🟥 TARJETA ROJA", "🟨🟥 DOBLE AMARILLA"]

REGLAS_PUNTOS_DEFAULT = [
    {"codigo": "gol_a_favor", "descripcion": "Gol de {pais}", "tipos_evento": _GOLES_EN_JUGADA, "aplica_a": "propio", "condicion": None, "puntos_base": 250},
    {"codigo": "gol_en_contra", "descripcion": "Gol de {rival}", "tipos_evento": _GOLES_EN_JUGADA, "aplica_a": "rival", "condicion": None, "puntos_base": -250},
    {"codigo": "asistencia", "descripcion": "Asistencia en el gol de {pais}", "tipos_evento": ["⚽ GOL"], "aplica_a": "propio", "condicion": "con_asistencia", "puntos_base": 50},
    {"codigo": "tiro_al_arco", "descripcion": "Tiro al arco de {pais}", "tipos_evento": _ATAJADAS, "aplica_a": "rival", "condicion": None, "puntos_base": 25},
    {"codigo": "tiro_al_arco_rival", "descripcion": "Tiro al arco de {rival}", "tipos_evento": _ATAJADAS, "aplica_a": "propio", "condicion": None, "puntos_base": -25},
    {"codigo": "atajada_importante", "descripcion": "Atajada importante del arquero de {pais}", "tipos_evento": ["🧤 ATAJADA ESPECTACULAR"], "aplica_a": "propio", "condicion": None, "puntos_base": 25},
    {"codigo": "corner_a_favor", "descripcion": "Córner a favor de {pais}", "tipos_evento": ["🖐️ DESVÍO A CÓRNER"], "aplica_a": "rival", "condicion": None, "puntos_base": 10},
    {"codigo": "corner_en_contra", "descripcion": "Córner a favor de {rival}", "tipos_evento": ["🖐️ DESVÍO A CÓRNER"], "aplica_a": "propio", "condicion": None, "puntos_base": -5},
    {"codigo": "falta_cometida", "descripcion": "Falta cometida por {pais}", "tipos_evento": ["🛑 FALTA"], "aplica_a": "propio", "condicion": None, "puntos_base": -10},
    {"codigo": "falta_recibida", "descripcion": "Falta recibida por {pais}", "tipos_evento": ["🛑 FALTA"], "aplica_a": "rival", "condicion": None, "puntos_base": 5},
    {"codigo": "amarilla", "descripcion": "Tarjeta amarilla para {pais}", "tipos_evento": _AMARILLAS, "aplica_a": "propio", "condicion": None, "puntos_base": -30},
    {"codigo": "amarilla_rival", "descripcion": "Tarjeta amarilla para {rival}", "tipos_evento": _AMARILLAS, "aplica_a": "rival", "condicion": None, "puntos_base": 15},
    {"codigo": "roja", "descripcion": "Tarjeta roja para {pais}", "tipos_evento": _ROJAS, "aplica_a": "propio", "condicion": None, "puntos_base": -120},
    {"codigo": "roja_rival", "descripcion": "Tarjeta roja para {rival}", "tipos_evento": _ROJAS, "aplica_a": "rival", "condicion": None, "puntos_base": 60},
    # El motor solo genera penales en la tanda (simular_tanda_penaltis), no durante el partido.
    {"codigo": "penal_a_favor", "descripcion": "Penal convertido por {pais}", "tipos_evento": ["⚽ GOL DE PENAL"], "aplica_a": "propio", "condicion": None, "puntos_base": 100},
    {"codigo": "penal_en_contra", "descripcion": "Penal convertido por {rival}", "tipos_evento": ["⚽ GOL DE PENAL"], "aplica_a": "rival", "condicion": None, "puntos_base": -150},
    {"codigo": "penal_atajado", "descripcion": "El arquero de {pais} ataja un penal", "tipos_evento": ["❌ PENAL FALLADO"], "aplica_a": "propio", "condicion": None, "puntos_base": 100},
    {"codigo": "penal_errado", "descripcion": "{pais} falla un penal", "tipos_evento": ["❌ PENAL FALLADO"], "aplica_a": "rival", "condicion": None, "puntos_base": -60},
    {"codigo": "resultado_victoria", "descripcion": "Victoria de {pais}", "tipos_evento": [], "aplica_a": "resultado", "condicion": "victoria", "puntos_base": 200},
    {"codigo": "resultado_empate", "descripcion": "Empate entre {pais} y {rival}", "tipos_evento": [], "aplica_a": "resultado", "condicion": "empate", "puntos_base": 0},
    {"codigo": "resultado_derrota", "descripcion": "Derrota de {pais}", "tipos_evento": [], "aplica_a": "resultado", "condicion": "derrota", "puntos_base": -200},
]
