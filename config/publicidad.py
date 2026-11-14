"""Publicidad pagada en las transmisiones (services/publicidad.py lógica pura + corporativo_tv_service._publicidad).

Cada partido que transmite una cadena con contrato ACTIVO de una selección tuya lleva `ESPACIOS` espacios publicitarios que compran marcas del catálogo (globales a
cualquier cadena, continentales de su confederación, locales de su país). Cada espacio vale una parte de lo que la cadena paga en promedio por partido
(`R.tv_esperado`), multiplicada por la AUDIENCIA del partido y el nivel de la marca; el corporativo se queda con `PARTICIPACION` del total. El mercado publicitario es
cíclico (el clima económico lo mueve) y una marca en crisis no compra (sus rivales compran más).
"""
ESPACIOS = 3
PARTICIPACION = 0.20
AUDIENCIA_FASE = {"grupos": 1.0, "eliminacion": 1.35, "final": 1.8}
AUDIENCIA_CLASICO = 1.2
POPULARIDAD_RANGO = (0.8, 1.3)     # según los aficionados de las dos selecciones frente a la base (100.000)
AUDIENCIA_TOPE = (0.7, 2.5)
FACTOR_MARCA = {3: 1.2, 2: 1.0, 1: 0.8}        # por nivel de la marca (global, continental, local)
PESO_NIVEL_MARCA = {3: 3.0, 2: 2.0, 1: 1.0}    # probabilidad de comprar un espacio
BONO_RIVAL_DE_CRISIS = 1.5
FASE_ELIMINACION = 8
FASE_FINAL = 13
AFICIONADOS_BASE = 100_000
