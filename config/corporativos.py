"""
Corporativos Deportivos: definición de los 10 corporativos y TODAS las reglas numéricas del módulo.

Cada usuario juega su propia carrera en su propio "universo" (1 corporativo dirigido por él + 9 de la IA).
El reloj del módulo son los partidos terminados (registro global `corp_registro_partidos`); cada
PARTIDOS_POR_CICLO partidos hay un cierre de ciclo (nómina, directorio, ofertas, IA, cotización).
Ver services/corporativo_*_service.py y el plan en CLAUDE.md ("Corporativos Deportivos").

⚠️ En este mundo los atributos de los jugadores son casi parejos (overall ~59-62) y el ranking de países sale
de los resultados del simulador (no de la "fama" real): por eso los valores de mercado son RELATIVOS
(percentil dentro de la población) y no una fórmula sobre el overall absoluto.
"""

# --- Los 10 corporativos -------------------------------------------------------------------------
# afinidad: confederaciones enteras y/o países sueltos (ids de `paises`). Los talentos de la región de
# afinidad aceptan con más gusto y pesan el doble al sembrar la cartera inicial.
# perfil (IA): conservador | marketing | chequera | cantera | equilibrado | volumen | oportunista
CORPORATIVOS = [
    {"sigla": "VESA", "nombre": "Vanguard European Sports Alliance", "tier": "A", "perfil": "conservador",
     "region": "Europa occidental", "colores": ("#1d4ed8", "#facc15"), "emblema": "escudo",
     "afinidad": {"confederaciones": [], "paises": [12, 13, 15, 17, 23, 24, 27, 29, 30, 31, 33, 36, 37, 38, 39, 40,
                                                     42, 46, 48, 50, 53, 54, 56, 60, 62, 63]}},
    {"sigla": "APEX", "nombre": "Apex North American Athletics Syndicate", "tier": "A", "perfil": "marketing",
     "region": "Norteamérica", "colores": ("#dc2626", "#e5e7eb"), "emblema": "cumbre",
     "afinidad": {"confederaciones": [], "paises": [73, 79, 90]}},
    {"sigla": "SGSH", "nombre": "Sovereign Gulf Sports Holdings", "tier": "A", "perfil": "chequera",
     "region": "Golfo y Asia del Sur", "colores": ("#047857", "#d4af37"), "emblema": "halcon",
     "afinidad": {"confederaciones": [], "paises": [156, 158, 159, 161, 163, 167, 171, 173, 174, 176, 178, 180,
                                                     183, 186, 187, 188, 189, 191, 192, 200]}},
    {"sigla": "CSLS", "nombre": "Corporación del Sol & Leyendas del Sur", "tier": "B", "perfil": "cantera",
     "region": "Sudamérica", "colores": ("#f59e0b", "#0ea5e9"), "emblema": "sol",
     "afinidad": {"confederaciones": [2], "paises": []}},
    {"sigla": "IEAC", "nombre": "Imperial Eurasian Athletics Corporation", "tier": "B", "perfil": "equilibrado",
     "region": "Europa oriental y Asia Central", "colores": ("#7c2d12", "#fbbf24"), "emblema": "corona",
     "afinidad": {"confederaciones": [], "paises": [11, 14, 16, 18, 19, 20, 21, 22, 25, 26, 28, 32, 34, 35, 41, 43,
                                                     44, 45, 47, 49, 51, 52, 55, 57, 58, 59, 61, 64, 65,
                                                     155, 177, 184, 195, 197, 198]}},
    {"sigla": "DPST", "nombre": "Dynasty Pacific Sports Trust", "tier": "B", "perfil": "volumen",
     "region": "Asia oriental", "colores": ("#b91c1c", "#fde047"), "emblema": "pagoda",
     "afinidad": {"confederaciones": [], "paises": [164, 165, 166, 170, 175, 181, 194]}},
    {"sigla": "ASSC", "nombre": "Atlas & Savannah Sports Consortium", "tier": "C", "perfil": "cantera",
     "region": "África", "colores": ("#15803d", "#f97316"), "emblema": "acacia",
     "afinidad": {"confederaciones": [4], "paises": []}},
    {"sigla": "PZSG", "nombre": "Pacific Zenith Sports Group", "tier": "C", "perfil": "oportunista",
     "region": "Oceanía y Sudeste Asiático", "colores": ("#0891b2", "#f0abfc"), "emblema": "ola",
     "afinidad": {"confederaciones": [5], "paises": [157, 160, 162, 168, 169, 172, 179, 182, 185, 190, 193, 196, 199]}},
    {"sigla": "CSPG", "nombre": "Caribbean Spirit & Performance Group", "tier": "C", "perfil": "oportunista",
     "region": "Caribe", "colores": ("#06b6d4", "#facc15"), "emblema": "palmera",
     "afinidad": {"confederaciones": [], "paises": [66, 67, 68, 69, 70, 72, 75, 76, 77, 80, 82, 83, 85, 86, 87, 88,
                                                     89, 91, 94, 95, 96, 97, 98, 99, 100]}},
    {"sigla": "UIDR", "nombre": "Unión Istmo Deporte & Rendimiento", "tier": "C", "perfil": "equilibrado",
     "region": "Centroamérica", "colores": ("#2563eb", "#22c55e"), "emblema": "volcan",
     "afinidad": {"confederaciones": [], "paises": [71, 74, 78, 81, 84, 92, 93]}},
]
CORPORATIVO_POR_SIGLA = {c["sigla"]: c for c in CORPORATIVOS}

# --- Tiers ---------------------------------------------------------------------------------------
# top20_selecciones: cuántas de las selecciones iniciales salen del top 20 del ranking al sembrar.
TIERS = {
    "A": {"capital": 60000, "fama_minima": 60, "sueldo_base": 190, "selecciones": (6, 8), "top20_selecciones": 2,
          "jugadores": 50, "percentil_jugadores": 0.70, "reputacion": 75},
    "B": {"capital": 40000, "fama_minima": 30, "sueldo_base": 130, "selecciones": (4, 6), "top20_selecciones": 1,
          "jugadores": 35, "percentil_jugadores": 0.45, "reputacion": 55},
    "C": {"capital": 25000, "fama_minima": 0, "sueldo_base": 90, "selecciones": (3, 4), "top20_selecciones": 0,
          "jugadores": 25, "percentil_jugadores": 0.0, "reputacion": 35},
}
ORDEN_TIER = {"C": 0, "B": 1, "A": 2}
PESO_AFINIDAD_SIEMBRA = 6.0       # la región de afinidad pesa x6 al sembrar (identidad regional; x2 quedaba casi al azar)
FRACCION_REGIONAL_SELECCIONES = 0.5   # mínimo de la cartera inicial que sale de la región de afinidad
FRACCION_REGIONAL_JUGADORES = 0.4
EDAD_MAXIMA_CANTERA = 23          # perfiles "cantera": siembran jugadores jóvenes

# --- Reloj ---------------------------------------------------------------------------------------
PARTIDOS_POR_CICLO = 20        # ~45 ciclos por Mundial (una selección juega cada ~105 partidos en eliminatorias)
PARTIDOS_PRIMERAS_OFERTAS = 3     # al activar el módulo, las primeras ofertas llegan a los 3 partidos (no esperar un ciclo entero)
CICLOS_MAXIMOS_POR_PEDIDO = 6     # poner_al_dia procesa a lo sumo esto por request; el resto en el siguiente
PARTIDOS_RESPUESTA_FICHAJE = 2    # una oferta de fichaje se responde 2 partidos después
CICLOS_VENTANA_TRASPASOS = 2      # tras cada cambio de fase, la ventana para fichar representados ajenos

# --- Valuaciones ---------------------------------------------------------------------------------
# Jugador: valor = VALOR_JUGADOR_MIN + (MAX - MIN) * percentil ** CURVA * factor_edad
# percentil sobre un puntaje de calidad = overall (z) + rendimiento (z) + fuerza de su selección (z).
VALOR_JUGADOR_MIN = 800
VALOR_JUGADOR_MAX = 12000
CURVA_VALOR_JUGADOR = 2.5
PESOS_CALIDAD_JUGADOR = {"overall": 0.45, "rendimiento": 0.35, "seleccion": 0.20}
FACTOR_EDAD = [(23, 1.3), (29, 1.0), (32, 0.7), (99, 0.4)]   # (edad máxima inclusive, factor)
# Leyendas (jugadores.leyenda, agregar_leyendas.py): escala propia, NO entran al percentil de los
# jugadores actuales (si entraran, 2.321 jugadores de 80 abaratarían a todos los demás). Su valor depende de
# su talla histórica ('fama', 0..1) y de la fuerza de su selección; la edad de plenitud no las castiga.
# valor = VALOR_LEYENDA_BASE * (fama_min + (fama_max - fama_min) * fama) * (1 - PESO/2 + PESO * percentil_poder)
VALOR_LEYENDA_BASE = 15000
RANGO_FAMA_LEYENDA = (0.8, 1.4)
PESO_SELECCION_LEYENDA = 0.2
# Selección: valor comercial = paises.valor * FACTOR + (aficionados - BASE) * FACTOR_AFICIONADOS
FACTOR_VALOR_SELECCION = 5
AFICIONADOS_BASE = 80000
FACTOR_AFICIONADOS = 0.05

# --- Resultado por partido (fracción del valor del representado) ---------------------------------
# Un representado juega poco (≈0,2 partidos por ciclo en eliminatorias, más en la fase final), así que la renta
# por partido es alta y el honorario por ciclo bajo: el promedio queda apenas positivo, gana el que elige bien.
RENTA_SELECCION = {"jugar": 0.025, "victoria": 0.080, "empate": 0.025, "derrota": -0.050,
                   "avance_fase": 0.15, "eliminacion": -0.08}
RENTA_JUGADOR = {"jugar": 0.030, "gol": 0.080, "asistencia": 0.050, "valla_invicta": 0.060, "roja": -0.080}
HONORARIO_POR_CICLO = {"seleccion": 0.005, "jugador": 0.004}   # (reglas viejas: costo fijo por ciclo; lo usa el simulador "antes")
POSICIONES_VALLA_INVICTA = {1, 2, 3, 4, 5}   # portero + defensas (posiciones granulares de `posiciones`)

# --- Economía v2: honorarios ligados a la actividad + patrocinios ---------------------------------
# Una selección juega ~1 vez cada 94 partidos (~4,7 ciclos): con el honorario fijo por ciclo, el 83% de los ciclos de
# un representado eran pérdida. Ahora casi todo el honorario se cobra cuando el representado JUEGA (junto con la
# renta) y queda un mantenimiento chico por ciclo; además cada contrato cobra un patrocinio por ciclo, juegue o no.
# Calibrado con simular_balance_corporativos.py (ver CLAUDE.md, "Corporativos Deportivos").
HONORARIO_MANTENIMIENTO = {"seleccion": 0.0010, "jugador": 0.0008}   # por ciclo, juegue o no
HONORARIO_POR_PARTIDO = {"seleccion": 0.0120, "jugador": 0.0100}     # por partido jugado (la selección / el jugador que entra)
PARTIDOS_ESPERADOS_POR_CICLO = 0.2                                     # para estimar el honorario "por ciclo" en vistas y rescisiones
PATROCINIO_POR_CICLO = {"seleccion": 0.0012, "jugador": 0.0010}      # x popularidad (0,6 a 1,6)
POPULARIDAD_RANGO = (0.6, 1.6)
AFICIONADOS_POPULARIDAD = (60000, 160000)     # selección: aficionados que dan la popularidad mínima / máxima
# Renovación: el representado ya es de la casa, la prima es menor que la de un fichaje (y menor aún si está contento)
PRIMA_RENOVACION = 0.60                        # x prima de referencia
DESCUENTO_RENOVACION_SATISFACCION = 0.25       # hasta -25% más con satisfacción 100 (lineal desde 60)
# Cotización: el sentimiento sigue el ROI medio de la ventana (no el de un ciclo suelto, muy irregular) y el precio
# suma la renta esperada de los partidos YA programados de la cartera en los próximos ciclos.
CICLOS_RENTA_ESPERADA = 2

# --- Contratos de representación -----------------------------------------------------------------
DURACION_CONTRATO = (4, 12)       # ciclos
SATISFACCION_INICIAL = 60
SATISFACCION_PIDE_SALIR = 30
SATISFACCION = {"victoria_seleccion": 3, "partido_jugado": 2, "tier_a": 1,
                "impago": -5, "ciclo_sin_jugar": -2, "ciclo_perdidas": -3, "salida_negada": -10}
RESCISION_FRACCION_RESTANTE = 0.5
CICLOS_AVISO_RENOVACION = 3        # el CEO puede renovar en los últimos 3 ciclos del contrato
SATISFACCION_RENOVACION = 10
CLAUSULA_RESCISION_MULTIPLO = 1.5  # cláusula = valor * esto

# --- Mercado -------------------------------------------------------------------------------------
PESOS_ATRACTIVO = {"reputacion": 0.30, "fama": 0.20, "oferta": 0.30, "afinidad": 0.10, "cartera": 0.10}
# La oferta de representación es una PRIMA DE FIRMA (pago único, se amortiza en la duración del contrato).
# Prima de referencia = 5% del valor: con el neto promedio (~0,6% del valor por ciclo) se recupera en ~8 ciclos;
# elegir bien (selecciones que ganan, jugadores titulares) la recupera mucho antes.
PRIMA_REFERENCIA = 0.05
OFERTA_IDEAL_MULTIPLO = 1.3       # ofrecer >= 1.3x la prima de referencia da puntaje_oferta 100
PROBABILIDAD_ACEPTA = (0.05, 0.95)
COSTO_SCOUTING = 500
COSTO_MARKETING = 1500
MARKETING_REPUTACION = 5
PROPUESTAS_ENTRANTES_POR_CICLO = (0, 2)

TOPE_OFERTAS_PENDIENTES = 5       # ofertas de fichaje abiertas a la vez por CEO
PRIMA_RANGO_OFERTA = (0.5, 2.0)    # la prima que puede ofrecer el CEO, en múltiplos de la de referencia
CLAUSULA_PAGO_AUTOMATICO = True   # pagar la cláusula completa obliga al rival a vender (el representado igual decide)
CONTRAOFERTA_UMBRAL = 0.85        # si el monto llega al 85% de lo que pide la IA, contraoferta en vez de rechazar
CICLOS_VENCE_PROPUESTA = 1        # propuestas de talentos, ofertas de la IA y pedidos de salida
PROPUESTA_PRIMA_RANGO = (0.8, 1.25)
PROB_OFERTA_IA_POR_ESTRELLA = 0.35  # por ciclo de ventana, que algún rival ofrezca por una de tus figuras
MULTIPLO_OFERTA_IA = (1.1, 1.6)
BONO_SATISFACCION_CAMBIO = 0.3    # un representado descontento acepta irse con más facilidad
SCOUTING_INFORMES = 3
EDAD_MAXIMA_SCOUTING = 23

# --- Acciones del CEO entre partidos (services/corporativo_acciones_service.py) --------------------
# Marketing: además de +reputación, multiplica los patrocinios de TODA la cartera durante unos ciclos.
MARKETING_BONO_PATROCINIO = 1.5
MARKETING_CICLOS = 3
# Acuerdo publicitario con un representado: adelanto + un pago por ciclo durante 3-5 ciclos. Monto = valor x tasa
# x popularidad x (0,7 + 0,6 x reputación/100). La marca puede cortar si al representado le va mal.
ACUERDO_ADELANTO = 0.010          # x valor
ACUERDO_PAGO_CICLO = 0.006        # x valor, por ciclo
ACUERDO_CICLOS = (3, 5)
ACUERDOS_MAX_ACTIVOS = 4          # por corporativo
ACUERDO_PROB_CORTE = {"roja": 0.35, "goleada": 0.25, "eliminada": 0.60}   # al cierre del ciclo en que pasó
MARCAS_ACUERDO = [   # sponsors ficticios (sin marcas reales): nombre, colores
    ("Volta Energy", "#f59e0b", "#1e293b"), ("Nórdica Air", "#38bdf8", "#0f172a"), ("Kubo Telecom", "#a855f7", "#f8fafc"),
    ("Sierra Motors", "#ef4444", "#111827"), ("Brisa Bebidas", "#22c55e", "#052e16"), ("Atlas Bank", "#eab308", "#1c1917"),
    ("Pixel Play", "#ec4899", "#1e1b4b"), ("Ruta Viajes", "#14b8a6", "#042f2e"), ("Faro Seguros", "#3b82f6", "#f1f5f9"),
    ("Cumbre Calzado", "#f97316", "#1c1917"),
]
# Gira de exhibición de una selección que no juega en los próximos ciclos: costo ahora, recaudación al cierre del
# ciclo siguiente según sus aficionados (con varianza). Las del USUARIO suman aficionados reales (+1% a +3%).
GIRA_CICLOS_SIN_PARTIDO = 2       # requisito: sin partido programado en los próximos 2 ciclos
GIRA_COSTO = 0.010                # x valor de la selección
GIRA_RECAUDACION = (0.010, 0.030) # x valor, según aficionados (popularidad) y azar
GIRA_SATISFACCION = 8
GIRA_ENFRIAMIENTO = 3             # ciclos entre giras de la misma selección (también tope GLOBAL de aficionados)
GIRA_AFICIONADOS_PCT = (0.01, 0.03)
# Gira de un jugador: ingreso por su popularidad y un aporte MÍNIMO de aficionados a su selección (0 a 10 por gira,
# según su forma y la de su selección). La IA también las hace (el aporte es ínfimo); tope por selección y ciclo.
GIRA_JUGADOR_COSTO = 0.004        # x valor del jugador
GIRA_COSTO_MINIMO = 60            # organizar una gira nunca es gratis (un jugador poco conocido no la recupera)
GIRA_JUGADOR_INGRESO = (0.006, 0.014)
GIRA_JUGADOR_ENFRIAMIENTO = 3
GIRA_JUGADOR_AFICIONADOS_MAX = 10
TOPE_AFICIONADOS_GIRAS_JUGADOR = 50   # por selección y ciclo, entre todas las giras de todos los universos
GIRAS_POR_CICLO = 1               # giras (de selección o de jugador) por corporativo y ciclo
IA_PROB_ACUERDO = 0.25            # (acuerdos viejos: la IA ya no firma; las marcas los reemplazaron)
IA_PROB_GIRA = 0.20               # por ciclo, que organice una gira

# --- Plan de saneamiento -------------------------------------------------------------------------
# Corporativo en rojo (capital < 70% del inicial, o 3 de los últimos 4 ciclos con pérdida): el directorio abre un
# plan de 4 ciclos con 3 objetivos; mientras dura hay TREGUA (sin ultimátum ni despido por ranking; la quiebra sigue).
SANEAMIENTO_CAPITAL = 0.70
SANEAMIENTO_CICLOS_ROJO = (3, 4)  # 3 de los últimos 4
SANEAMIENTO_DURACION = 4
SANEAMIENTO_OBJETIVOS = {
    "utilidad_2": "Cerrar 2 ciclos con utilidad positiva",
    "acuerdo_1": "Firmar 1 acuerdo publicitario o patrocinio de marca",   # planes viejos (ya no se sortea)
    "patrocinio_1": "Conseguir 1 patrocinio de marca para un representado",
    "gira_1": "Organizar 1 gira de exhibición",
    "honorarios": "Bajar los honorarios: soltar contratos que no juegan (rescindir o dejar vencer)",
    "satisfaccion_50": "Mantener la satisfacción media de la cartera por encima de 50",
}
SANEAMIENTO_NO_SORTEAR = {"acuerdo_1"}
SANEAMIENTO_SORTEADOS = 3
APORTE_SANEAMIENTO = 0.15          # x capital inicial, al cumplir el plan
SANEAMIENTO_CONFIANZA = 10
SANEAMIENTO_FAMA = 4
SANEAMIENTO_SENTIMIENTO = 0.05
SANEAMIENTO_ESPERA = 4             # ciclos sin plan nuevo después de terminar uno

# --- IA ------------------------------------------------------------------------------------------
# fichajes por ciclo, multiplo de la prima que paga, filtro de percentil (min, max), edad máxima, peso de selecciones
PERFILES_IA = {
    "conservador": {"fichajes": 1, "multiplo": 1.1, "percentil": (0.6, 1.0), "edad": 99, "prob_seleccion": 0.2},
    "marketing":   {"fichajes": 1, "multiplo": 1.2, "percentil": (0.4, 1.0), "edad": 99, "prob_seleccion": 0.5},
    "chequera":    {"fichajes": 1, "multiplo": 1.5, "percentil": (0.75, 1.0), "edad": 99, "prob_seleccion": 0.25},
    "cantera":     {"fichajes": 1, "multiplo": 1.0, "percentil": (0.2, 1.0), "edad": 23, "prob_seleccion": 0.1},
    "equilibrado": {"fichajes": 1, "multiplo": 1.1, "percentil": (0.3, 1.0), "edad": 99, "prob_seleccion": 0.25},
    "volumen":     {"fichajes": 2, "multiplo": 1.0, "percentil": (0.3, 0.75), "edad": 99, "prob_seleccion": 0.2},
    "oportunista": {"fichajes": 1, "multiplo": 0.9, "percentil": (0.0, 0.55), "edad": 99, "prob_seleccion": 0.2},
}
PESO_AFINIDAD_IA = 3.0
IA_PRESUPUESTO_FICHAJE = 0.15     # fracción del capital
MAX_LEYENDAS_IA_POR_CORP = 3      # leyendas con contrato activo que puede juntar un corporativo de la IA
PESO_LEYENDA_IA = 0.25            # peso de una leyenda en el sorteo de fichajes de la IA (para que no se lleven todas de una)
IA_MULTIPLO_VENTA = {"default": 1.2, "chequera": 1.5}
IA_CICLOS_SIN_JUGAR_RESCINDE = 3
IA_ROI_DIVIDENDO = 0.05

# --- Carrera del CEO -----------------------------------------------------------------------------
FAMA_INICIAL = 10
FAMA = {"ciclo_utilidad": 2, "objetivo": 5, "fichaje_top50": 2, "titulo_temporada": 10,
        "despido": -15, "rechazo_repetido": -1, "renuncia_temprana": -3,
        # fama por resultados de los representados (una vez por ciclo y motivo, con tope)
        "avance_fase": 3, "actuacion": 2, "renta_mayor_honorarios": 1}
FAMA_TOPE_RESULTADOS_CICLO = 6
RECHAZOS_SIN_PENALIDAD = 2
CICLOS_RENUNCIA_TEMPRANA = 3
OFERTAS_INICIALES = 2             # ofertas garantizadas (tier C) en el primer cierre de ciclo
PROB_OFERTA_BUSCANDO = (0.40, 1 / 200)    # base + fama * factor
MARGEN_FAMA_OFERTA = 10
CICLOS_VENCE_OFERTA = 2
CICLOS_VENCE_HEADHUNTING = 1
PROB_HEADHUNTING = (25, 1 / 250, 0.03)    # max(0, (fama - umbral) * factor) + base (solo te buscan los de tu tier o más grandes)
MEJORA_SUELDO_HEADHUNTING = (0.10, 0.40)
CONFIANZA_CONTRAOFERTA = 60
MEJORA_CONTRAOFERTA = 0.15
CICLOS_PREAVISO = 1
CICLOS_PAUSA = {"despido": 3, "renuncia": 1}
AJUSTE_SUELDO_FAMA = 0.20         # ±20% del sueldo base según la fama al firmar
BONO_PORCENTAJE = (0.05, 0.10)    # sobre la utilidad MEDIA de la ventana de ROI (no premia la suerte de un ciclo)
BONO_TOPE_MULTIPLO_SUELDO = 2
FRACCION_BONO_EN_ACCIONES = 0.25
CICLOS_CONSOLIDACION_ACCIONES = 3
MEJORA_RENOVACION = 0.20

# --- Directorio ----------------------------------------------------------------------------------
CONFIANZA_INICIAL = 60
# El directorio juzga en RELATIVO (como en la vida real: contra la competencia), con ROI de una ventana de
# varios ciclos (un representado juega poco: el ROI de un solo ciclo es muy irregular). Cada tier espera
# terminar el ciclo dentro de un puesto del ranking de los 10 corporativos del universo.
CICLOS_VENTANA_ROI = 4
POSICION_ESPERADA_TIER = {"A": 3, "B": 6, "C": 8}
CONFIANZA_POSICION = {"cumple": 3, "cerca": -1, "lejos": -4}   # cerca = hasta 2 puestos debajo de lo esperado
CONFIANZA_ROI_NEGATIVO = (-0.02, -3)    # ROI de la ventana menor a esto: castigo extra
CONFIANZA_VS_INDICE = 2
CONFIANZA_IMPAGO = -15
CONFIANZA_ULTIMATUM = 35
CONFIANZA_DESPIDO = 20
CAPITAL_MINIMO_FRACCION = 0.25
CONFIANZA_RENUEVA_SIN_OBJETIVOS = 50
OBJETIVOS_PARA_RENOVAR = 2
OBJETIVOS_POR_TIER = {
    "A": ["roi_15", "selecciones_grupos_3", "cotizacion_mas_10", "goleador_torneo"],
    "B": ["roi_10", "selecciones_grupos_2", "cotizacion_inicial", "jugadores_10_partidos"],
    "C": ["roi_5", "selecciones_grupos_1", "cotizacion_inicial", "capital_inicial"],
}
OBJETIVOS = {
    "roi_5": "ROI de la temporada de al menos 5%",
    "roi_10": "ROI de la temporada de al menos 10%",
    "roi_15": "ROI de la temporada de al menos 15%",
    "selecciones_grupos_1": "Al menos 1 selección representada en la fase de grupos del Mundial",
    "selecciones_grupos_2": "Al menos 2 selecciones representadas en la fase de grupos del Mundial",
    "selecciones_grupos_3": "Al menos 3 selecciones representadas en la fase de grupos del Mundial",
    "cotizacion_inicial": "Cerrar la temporada con la acción por encima de su precio inicial",
    "cotizacion_mas_10": "Cerrar la temporada con la acción 10% arriba de su precio inicial",
    "goleador_torneo": "Representar al goleador del Mundial",
    "jugadores_10_partidos": "Tener 10 representados con al menos 3 partidos jugados",
    "capital_inicial": "Cerrar la temporada con el capital inicial o más",
}
OBJETIVOS_SORTEADOS = 3

# --- Bolsa ---------------------------------------------------------------------------------------
ACCIONES_POR_CORPORATIVO = 100000
SENTIMIENTO_RANGO = (0.6, 1.6)
SENTIMIENTO_INICIAL = 1.0
RUIDO_COTIZACION = 0.03
BANDA_COTIZACION_CICLO = 0.20
COMISION_BOLSA = 0.01
TOPE_TENENCIA = 0.10
QUIEBRA_CAIDA_COTIZACION = 0.50
FRACCION_MAX_DIVIDENDO = 0.30
IA_FRACCION_DIVIDENDO = 0.20      # la IA reparte el 20% de la utilidad del ciclo si tuvo ROI >= 0,5% y capital sano
SENTIMIENTO_DIVIDENDO = 0.03      # repartir dividendo mejora el sentimiento del mercado


# --- Marcas y patrocinios (services/corporativo_marcas_service.py; catálogo en config/marcas.py) -----------------
# Reemplazan al acuerdo publicitario. Las marcas (ficticias, colección `marcas`) se acercan solas a los representados
# de cualquier corporativo del universo, el CEO puede PROMOVER a los suyos y las marcas cortan si les va mal.
# Pago por ciclo = valor x MARCA_PAGO_CICLO x factor del alcance x (0,7 + 0,6 x encaje/100) x (0,85 + 0,3 x reputación/100);
# firma = MARCA_FIRMA x pago. Del corporativo del usuario, MARCA_COMISION_CEO va a su nómina (con el sueldo).
MARCA_PAGO_CICLO = 0.0040
MARCA_FIRMA = 1.5
MARCA_FACTOR_NIVEL = {3: 1.3, 2: 1.0, 1: 0.75}        # global, continental, local
MARCA_CUPOS_NIVEL = {3: 2, 2: 1, 1: 1}                # patrocinios simultáneos por marca y universo
MARCA_CICLOS = (4, 8)
MARCAS_MAX_POR_REPRESENTADO = 3                       # y nunca dos del mismo rubro
MARCA_COMISION_CEO = 0.05
MARCA_ENCAJE_MINIMO = 45                              # debajo de esto la marca no se interesa
MARCA_PROB_ACERCARSE = 0.20                           # por ciclo, que una marca con cupo libre salga a buscar
MARCA_PROB_RUMOR = 0.30                               # antes de ofertar deja correr el rumor un ciclo (entre 3-4 candidatos)
MARCA_IA_ACEPTA = 0.85
MARCA_OFERTA_CICLOS = 1                               # la oferta al usuario vence al cierre del ciclo siguiente
MARCA_PROMOCIONES_POR_CICLO = 3                       # «Promover» del CEO, se responden al cierre del ciclo
MARCA_PROMOCION_BASE = 0.15                           # prob. = base + encaje + reputación + fama (corporativo_reglas.prob_promocion)
# Riesgo de corte (0..100) al cierre de cada ciclo: lo que pasó en el ciclo x (1,3 - fidelidad de la marca)
MARCA_RIESGO = {"roja": 30, "goleada": 22, "eliminada": 60, "sin_jugar": 12, "mala_forma": 14, "descontento": 8}
MARCA_RIESGO_AVISO = 30                               # aviso previo («está revisando el patrocinio»)
MARCA_RIESGO_CORTE = 55                               # corta (o corta si ya había aviso y el riesgo sigue >= aviso)
MARCA_PROB_RENUEVA = 0.55                             # al vencer, si quedó conforme (riesgo bajo)
MARCA_PROB_REACCION = 0.70                            # que la marca comente en la red social el partido de su patrocinado
MARCA_PROB_POST_IA = 0.50                             # firmas/renovaciones/despedidas de la IA que llegan a la red (las tuyas, siempre)
