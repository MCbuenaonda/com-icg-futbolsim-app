"""Escándalos y gestión de crisis de las MARCAS (services/escandalos.py lógica pura + services/escandalos_service.py Mongo).

Cada `PARTIDOS_RONDA` partidos terminados, hasta `MAX_POR_RONDA` marcas ficticias entran en crisis (con `PROB_POR_ESCANDALO` cada una; las marcas con más
patrocinios activos tienen más peso, para que se note). Durante `DURACION_PARTIDOS` partidos (del reloj de corporativos, `seq`) sus patrocinios pagan menos
(`REBAJA`) y suben el riesgo de corte (`RIESGO_EXTRA`: por sí solo nunca cruza el aviso, `MARCA_RIESGO_AVISO` = 30). Las marcas aliadas sufren la mitad
(`CONTAGIO`) y las rivales ganan encaje (`ENCAJE_RIVAL`) para acercarse. El CEO puede RESPALDAR (paga `RESPALDO_CICLOS` ciclos de lo que paga esa marca: quita el
riesgo extra y la rebaja baja a `RESPALDO_RESIDUO`) o TOMAR DISTANCIA (termina el patrocinio sin castigo). La IA sufre lo mismo.
"""
PARTIDOS_RONDA = 8
MAX_POR_RONDA = 3
PROB_POR_ESCANDALO = 0.65
SEVERIDAD_PESOS = {1: 0.6, 2: 0.3, 3: 0.1}
DURACION_PARTIDOS = 16

REBAJA = {1: 0.15, 2: 0.30, 3: 0.45}          # de lo que paga la marca por ronda de pago
RIESGO_EXTRA = {1: 8, 2: 16, 3: 24}
CONTAGIO = 0.5
ENCAJE_RIVAL = {1: 4, 2: 8, 3: 12}
RESPALDO_CICLOS = 0.33                       # antes 1,0: respaldar costaba un ciclo entero para ahorrar ~0,12 de ciclo de rebaja y casi nunca convenía
RESPALDO_RESIDUO = 0.5
MAX_NOTAS = 3

# --- Cadenas de TV y medios (services/escandalos_medios_service.py): crisis de imagen de las cadenas de televisión y de los medios de prensa ---
# Cada ronda, hasta MAX_TV_POR_RONDA cadenas y MAX_MEDIOS_POR_RONDA medios (ficticios) entran en crisis con la misma duración y severidades que las marcas.
# Una cadena en crisis paga menos por partido y por anuncios (TV_REBAJA) a todos los universos y sus cadenas rivales de país pagan algo más (TV_BONO_RIVAL);
# un medio en crisis pierde credibilidad (MEDIO_CREDIBILIDAD, resta a `credibilidad_actual`): sus notas pesan menos en la reputación mediática.
MAX_TV_POR_RONDA = 1
MAX_MEDIOS_POR_RONDA = 1
PROB_TV = 0.50
PROB_MEDIO = 0.50
TV_REBAJA = {1: 0.10, 2: 0.20, 3: 0.30}
TV_BONO_RIVAL = {1: 0.03, 2: 0.05, 3: 0.08}
MEDIO_CREDIBILIDAD = {1: 0.05, 2: 0.10, 3: 0.18}
# Decisión del CEO en la crisis de una CADENA de TV (solo se pregunta si tu selección va a jugar mientras dure: si no, la crisis no te toca)
TV_RESPALDO_PARTIDOS = 1        # respaldar cuesta el pago esperado de UN partido de esa selección con la cadena
TV_RESPALDO_RESIDUO = 0.5       # la rebaja baja a la mitad mientras dure la crisis
TV_RESPALDO_RENUEVA = 0.10      # la cadena agradecida renueva con +10 puntos de probabilidad al terminar el contrato
