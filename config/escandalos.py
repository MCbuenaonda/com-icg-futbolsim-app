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
RESPALDO_CICLOS = 1.0
RESPALDO_RESIDUO = 0.5
MAX_NOTAS = 3
