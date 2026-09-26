import certifi
from fastapi import HTTPException, status
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
from collections import defaultdict
import random

TACTICAS = ["4-3-3", "4-4-2", "3-5-2"]

FORMACIONES = {
    "4-3-3": [1,  2, 2, 2, 2,  3, 3, 3,  4, 4, 4],
    "4-4-2": [1,  2, 2, 2, 2,  3, 3, 3, 3,  4, 4],
    "3-5-2": [1,  2, 2, 2,  3, 3, 3, 3, 3,  4, 4]
}

POSICIONES = {
    1: "PORTERO",
    2: "DEFENSA",
    3: "MEDIO",
    4: "DELANTERO"
}

# Fracción de faltas cometidas en el tercio de ataque que caen en posición de disparo directo
# y se resuelven como tiro libre (ver ejecutar_tiro_libre) -- el resto sigue el flujo normal
# de falta (la pelota queda con el equipo infringido, sin remate).
PROB_TIRO_LIBRE_PELIGROSO = 0.30

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

# ---------------------------------------------------------------------------
# RELOJ DE SEGUNDOS ACUMULADOS (Event-Driven Seconds Tick)
# ---------------------------------------------------------------------------
# El motor avanza por 'segundos_acumulados' en vez de un 'minuto' discreto -- cada acción
# consume un costo de tiempo realista (ver rangos abajo) en vez del genérico
# random.choice([0.5, 1.0]) que usaba el bucle anterior. El campo "minuto" persistido sigue
# existiendo como entero (minuto = segundos_acumulados // 60) para no romper a ningún
# consumidor existente (templates, calcular_intensidad_partido, badgeMinuto, etc.).
DURACION_TIEMPO_REGLAMENTARIO = 5400  # 90' = 2 x 2700s
DURACION_MEDIO_TIEMPO = 2700          # cierre cosmético del 1er tiempo, ver construir_evento
DURACION_TIEMPO_EXTRA = 7200          # 120' si hay alargue

RANGO_SEGUNDOS_TRANSICION = (4, 8)        # pase / pase_profundo / despeje / regate
RANGO_SEGUNDOS_ATAQUE_REMATE = (3, 7)     # build-up + tiro / córner / tiro libre (el remate en sí)
RANGO_SEGUNDOS_FALTA = (20, 40)           # falta simple / tarjeta amarilla (sin derivar en tiro libre)
RANGO_SEGUNDOS_OFFSIDE = (20, 30)         # fuera de lugar
RANGO_SEGUNDOS_VAR_ROJA_PENAL = (45, 90)  # revisión VAR, roja directa/doble amarilla, cobro de penal
RANGO_SEGUNDOS_SUSTITUCION = (30, 45)     # sustitución (solo en paradas de juego del 2º tiempo)

def _costo_segundos(rango: tuple) -> int:
    return random.randint(*rango)

# Traducción de la zona interna del motor ('defensa'/'medio'/'ataque', usada en ~40 puntos de
# este archivo) al nombre persistido en cada evento -- se traduce SOLO al armar el evento, la
# lógica interna no se toca para no arriesgar una comparación de string rota en algún lugar.
ZONA_A_ZONA_PERSISTIDA = {"defensa": "defensiva", "medio": "mediocampo", "ataque": "ataque"}

# Posición de balón sintética: no hay modelo real de posición de jugadores en este motor, así
# que se aproxima con un rango de X (cancha 0-100) según la zona y un Y uniforme en todo el
# ancho (0-68) -- suficiente para pintar un punto plausible en un minimapa, no una simulación
# posicional real.
RANGO_X_POR_ZONA = {"defensa": (0, 33), "medio": (33, 66), "ataque": (66, 100)}

# Para los tipos de evento en TIPOS_CERCA_DEL_ARCO (el balón llegó de verdad a la portería: gol,
# atajada, desvío a córner, penal fallado), en vez del rango genérico de "ataque" (66-100 x /
# 0-68 y, todo el tercio) se usa un rango acotado cerca del arco -- x pegado a la línea de meta
# e y dentro del ancho real de una portería (7.32m, centrada en el medio de la cancha, 34).
RANGO_X_CERCA_DEL_ARCO = (92, 100)
RANGO_Y_ANCHO_ARCO = (27, 41)
TIPOS_CERCA_DEL_ARCO = {
    "⚽ GOL", "⚽ GOL DE PENAL", "⚽ GOL DE TIRO LIBRE", "⚽ GOL DE CÓRNER",
    "🧤 ATAJADA ESPECTACULAR", "🖐️ DESVÍO A CÓRNER", "❌ PENAL FALLADO"
}

def _posicion_balon_sintetica(zona_balon: str, tipo: str = None) -> dict:
    if tipo in TIPOS_CERCA_DEL_ARCO:
        x_min, x_max = RANGO_X_CERCA_DEL_ARCO
        y_min, y_max = RANGO_Y_ANCHO_ARCO
    else:
        x_min, x_max = RANGO_X_POR_ZONA.get(zona_balon, (33, 66))
        y_min, y_max = (0, 68)
    return {"x": round(random.uniform(x_min, x_max), 1), "y": round(random.uniform(y_min, y_max), 1)}

def construir_evento(segundos_acumulados: float, equipo: str, tipo: str, descripcion: str,
                      jugadores: list, zona_balon: str, es_preparacion: bool = False) -> dict:
    """
    Arma un evento de 'eventos_visibles' con la forma completa (campos de siempre +
    'segundos_acumulados'/'zona'/'posicion_balon' nuevos). Reemplaza a los dict literales
    sueltos y a la vieja 'evento_preparacion' -- con 3 campos nuevos por evento que dependen de
    estado compartido (reloj, zona actual), centralizarlo acá evita repetir esa lógica en los
    ~40 sitios que arman eventos.
    """
    evento = {
        "minuto": int(segundos_acumulados // 60),
        "segundos_acumulados": int(segundos_acumulados),
        "equipo": equipo,
        "tipo": tipo,
        "descripcion": descripcion,
        "jugadores": jugadores,
        "zona": ZONA_A_ZONA_PERSISTIDA.get(zona_balon, zona_balon),
        "posicion_balon": _posicion_balon_sintetica(zona_balon, tipo),
    }
    if es_preparacion:
        evento["es_preparacion"] = True
    return evento

def hay_revision_var(prob: float = 0.05) -> bool:
    """Probabilidad de que una jugada polémica (gol, penal, posible roja directa) pase por
    revisión del VAR -- mismo 5% que ya usaba el chequeo de gol, generalizado para reusarlo
    también en penal y roja directa."""
    return random.random() < prob

# funcion para obtener un jugador oponente segun la zona del balon
def obtener_oponente_segun_zona(equipo_defensor: dict, zona_balon: str):
    plantilla = equipo_defensor["plantilla"]
    defensas = [j for j in plantilla if j["posicion_id"] == 2]
    medios = [j for j in plantilla if j["posicion_id"] == 3]
    delanteros = [j for j in plantilla if j["posicion_id"] == 4]
    todos_menos_portero = [j for j in plantilla if j["posicion_id"] != 1]

    if zona_balon == "ataque":
        candidatos = defensas if defensas else todos_menos_portero
    elif zona_balon == "medio":
        candidatos = medios if medios else todos_menos_portero
    else:
        candidatos = delanteros + medios if (delanteros or medios) else todos_menos_portero

    return random.choice(candidatos)

# funcion para resolver un duelo entre dos jugadores
def resolver_duelo(prob_base: float, attr_atacante: float, attr_defensor: float) -> bool:
    diferencia = (attr_atacante - attr_defensor) / 100.0
    prob_final = max(0.08, min(0.92, prob_base + (diferencia * 0.35)))
    return random.random() < prob_final

# Bonus de "pie hábil" y especialistas de balón parado -- ver asignar_rasgos_jugadores.py para
# cómo se asignan estos campos (una sola vez, se preservan entre mundiales, ver
# services/mundial_service.py::restart_mundial).
BONUS_PRECISION_AMBIDIESTRO = 4  # jugador menos previsible: remata bien con cualquier pierna
BONUS_PRECISION_ESPECIALISTA_PENAL = 8
BONUS_PRECISION_ESPECIALISTA_TIRO_LIBRE = 6

# Bonos de formación táctica -- hoy la táctica (elegida al azar por partido, ver TACTICAS) solo
# definía la alineación vía FORMACIONES; con el reloj de segundos se le suma un efecto real
# sobre las probabilidades de posesión/progresión/intercepción, aplicado como plus de atributo
# en los mismos resolver_duelo() ya existentes (mismo patrón que bonus_pie_habil).
BONUS_FORMACION_POSESION_3_5_2 = 6       # conservar el balón en MEDIOCAMPO
BONUS_FORMACION_PROGRESION_4_3_3 = 6     # pase profundo MEDIOCAMPO -> ATAQUE por bandas
BONUS_FORMACION_INTERCEPCION_4_4_2 = 6   # recuperar el balón en ZONA DEFENSIVA


def bonus_pie_habil(jugador: dict) -> float:
    """
    Plus de precisión de disparo para jugadores ambidiestros ('pie_habil'). Solo aplica a
    duelos que usan 'precision_tiro' (tiro, penal, tiro libre) -- nunca a los aéreos
    (córner, que usa 'juego_aereo'): ser ambidiestro no te hace mejor de cabeza.
    """
    return BONUS_PRECISION_AMBIDIESTRO if jugador.get("pie_habil") == "ambidiestro" else 0.0

# ---------------------------------------------------------------------------
# EVENTOS DE PREPARACIÓN / TRANSICIÓN ("build-up")
# ---------------------------------------------------------------------------
# Entradas puramente narrativas para eventos_visibles, insertadas justo antes del evento real
# que describen (transición de posesión, tiro/gol, falta/robo) para evitar los saltos abruptos
# de posesión en la línea de tiempo ("Equipo A tenía la pelota" -> "gol de Equipo B" sin
# explicación). NUNCA tocan stats_jugadores -- las estadísticas reales siguen viviendo
# exclusivamente en el evento principal que sigue, y NUNCA consumen su propio costo de tiempo:
# comparten el mismo cargo de segundos que la acción real que preceden (ver construir_evento).
#
# Varias frases por situación (random.choice) para no repetir siempre el mismo texto, mismo
# patrón que FRASES_NARRATIVA_* en services/juegos_service.py.

FRASES_TRANSICION_PASE = [
    "¡Anticipación de {defensor}! Lee el pase de {atacante} y sale jugando para {equipo}...",
    "{defensor} le quita el balón a {atacante} en la salida de {rival} y sale jugando para {equipo}...",
]
FRASES_TRANSICION_REGATE = [
    "{defensor} le saca el balón a {atacante} con un cierre limpio y {equipo} recupera el control...",
    "Buen cierre de {defensor}: le quita la pelota a {atacante} sin cometer falta y arranca la contra...",
]
FRASES_PRESION_FALTA_PASE = [
    "{defensor} acosa la salida de {atacante} y va al choque para disputar la esférica...",
    "{defensor} cierra el espacio de pase de {atacante} con una entrada fuerte...",
]
FRASES_PRESION_FALTA_REGATE = [
    "{defensor} no le da espacio a {atacante} y entra directo a cortar el avance...",
    "{defensor} se le viene encima a {atacante} para frenar el desborde a cualquier costo...",
]
FRASES_PRESION_ROBO = [
    "{defensor} presiona la salida de {rival} y busca robar en zona peligrosa...",
    "{defensor} achica los espacios y le pone el cuerpo a la salida de {rival}...",
]
FRASES_PREPARACION_ASISTIDA = [
    "{asistente} filtra un pase entre líneas para {atacante}, que encara solo hacia el arco...",
    "Gran habilitación de {asistente}: {atacante} recibe con espacio y mira al arco...",
]
FRASES_PREPARACION_SOLO = [
    "{atacante} se acomoda para su pierna hábil y desenfunda el remate...",
    "{atacante} pisa el área, levanta la vista y decide rematar...",
]
FRASES_PREPARACION_PENAL = [
    "{tirador} acomoda el balón en el punto penal y respira hondo bajo la presión de la tanda...",
    "{tirador} da unos pasos atrás y fija la mirada en el punto penal...",
]
FRASES_PREPARACION_TIRO_LIBRE = [
    "{cobrador} deja el balón quieto sobre el punto de tiro libre y mide los pasos de carrera...",
    "{cobrador} traza la carrera del disparo mientras el árbitro ordena la barrera...",
]
FRASES_PREPARACION_CORNER = [
    "El córner se mece al área y {rematador} se eleva para buscar el cabezazo, marcado de cerca por {defensor}...",
    "{rematador} toma posición en el área para el centro, vigilado de cerca por {defensor}...",
]

# funcion para seleccionar plantilla titular
def seleccionar_plantilla_titular(plantilla_db: list, esquema="4-3-3") -> list:
    formacion_objetivo = FORMACIONES.get(esquema, FORMACIONES["4-3-3"])
    titulares = []
    jugadores_disponibles = list(plantilla_db)

    i = 1
    for linea in formacion_objetivo:
        candidatos = [j for j in jugadores_disponibles if j.get("posicion_id") == i]
        if not candidatos:
            candidatos = jugadores_disponibles

        elegido = random.choice(candidatos)
        jugador_partido = elegido.copy()
        jugador_partido["linea_partido"] = linea
        titulares.append(jugador_partido)
        jugadores_disponibles.remove(elegido)
        i += 1

    return titulares


# -------------------------------------------------------------------------
# LÓGICA DE TANDA DE PENALTIS (Serie de 5 + Muerte Súbita)
# -------------------------------------------------------------------------
def simular_tanda_penaltis(equipo_local, equipo_visitante, portero_local, portero_visitante, stats_jugadores, eventos_visibles, segundos_acumulados: float, arbitros: dict):
    penaltis_local = 0
    penaltis_visitante = 0

    # Filtrar cobradores de campo (excluir portero primero si es posible)
    cobradores_local = [j for j in equipo_local["plantilla"] if j.get("linea_partido") != 1]
    cobradores_visita = [j for j in equipo_visitante["plantilla"] if j.get("linea_partido") != 1]

    # Ordenar: primero los especialistas de penal (van al frente de la cola de cobro), y dentro
    # de cada grupo por precisión + compostura -- mismo par de atributos que usa el duelo real
    # en ejecutar_penal, en vez de solo precisión de tiro.
    def _prioridad_cobrador(j: dict):
        return (
            0 if j.get("especialista_penales") else 1,
            -(j.get("precision_tiro", 70) + j.get("compostura", 60))
        )
    cobradores_local.sort(key=_prioridad_cobrador)
    cobradores_visita.sort(key=_prioridad_cobrador)

    eventos_visibles.append(construir_evento(
        segundos_acumulados, "Árbitro", "🥅 TANDA DE PENALTIS",
        "¡Finaliza el tiempo extra! El ganador se decidirá desde el punto penal.",
        [], "ataque"
    ))

    # --- SERIE DE 5 PENALTIS ---
    ronda = 0
    while ronda < 5:
        # Cobro Local
        tirador_l = cobradores_local[ronda % len(cobradores_local)]
        gol_l, segundos_acumulados = ejecutar_penal(tirador_l, portero_visitante, equipo_local["nombre"], equipo_visitante["nombre"], stats_jugadores, eventos_visibles, segundos_acumulados, arbitros)
        if gol_l: penaltis_local += 1

        # Verificación matemática temprana de victoria local
        if abs(penaltis_local - penaltis_visitante) > (5 - (ronda + 1)) and penaltis_local > penaltis_visitante:
            break

        # Cobro Visitante
        tirador_v = cobradores_visita[ronda % len(cobradores_visita)]
        gol_v, segundos_acumulados = ejecutar_penal(tirador_v, portero_local, equipo_visitante["nombre"], equipo_local["nombre"], stats_jugadores, eventos_visibles, segundos_acumulados, arbitros)
        if gol_v: penaltis_visitante += 1

        # Verificación matemática temprana de victoria visitante
        if abs(penaltis_local - penaltis_visitante) > (5 - (ronda + 1)) and penaltis_visitante > penaltis_local:
            break

        ronda += 1

    # --- MUERTE SÚBITA (Si continúan empatados) ---
    while penaltis_local == penaltis_visitante:
        tirador_l = cobradores_local[ronda % len(cobradores_local)]
        gol_l, segundos_acumulados = ejecutar_penal(tirador_l, portero_visitante, equipo_local["nombre"], equipo_visitante["nombre"], stats_jugadores, eventos_visibles, segundos_acumulados, arbitros)
        if gol_l: penaltis_local += 1

        tirador_v = cobradores_visita[ronda % len(cobradores_visita)]
        gol_v, segundos_acumulados = ejecutar_penal(tirador_v, portero_local, equipo_visitante["nombre"], equipo_local["nombre"], stats_jugadores, eventos_visibles, segundos_acumulados, arbitros)
        if gol_v: penaltis_visitante += 1

        ronda += 1

    return penaltis_local, penaltis_visitante

# funcion para ejecutar un penal individual
def ejecutar_penal(tirador, portero, nombre_equipo, nombre_equipo_rival, stats_jugadores, eventos_visibles, segundos_acumulados: float, arbitros: dict):
    """Ejecuta un penal individual y registra las estadísticas correspondientes.

    'nombre_equipo_rival' (el dueño de 'portero') solo se usa para atribuir correctamente el
    evento de penal fallado/atajado al equipo del propio arquero, no al del cobrador.

    :return: (gol: bool, segundos_acumulados: float) -- el cobro de un penal (con o sin
        revisión del VAR) siempre cae dentro del rango VAR/Roja/Penal (45-90s).
    """
    # Promedio de precisión y compostura (sangre fría para tirar el penal), con el plus de
    # pie hábil ambidiestro y el de especialista de penales si corresponde (ver
    # bonus_pie_habil/BONUS_PRECISION_ESPECIALISTA_PENAL).
    attr_tirador = (tirador.get("precision_tiro", 60) + bonus_pie_habil(tirador) + tirador.get("compostura", 60)) / 2
    if tirador.get("especialista_penales"):
        attr_tirador += BONUS_PRECISION_ESPECIALISTA_PENAL

    # Promedio de agilidad y rendimiento del portero
    attr_portero = (portero.get("agilidad", 60) + portero.get("rendimiento", 60)) / 2

    eventos_visibles.append(construir_evento(
        segundos_acumulados, nombre_equipo, "⏳ PREPARACIÓN",
        random.choice(FRASES_PREPARACION_PENAL).format(tirador=tirador["nombre"]),
        [tirador["nombre"]], "ataque", es_preparacion=True
    ))
    segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_VAR_ROJA_PENAL)

    # --- REVISIÓN DEL VAR (encroachment del arquero, doble toque, etc.) ---
    if hay_revision_var():
        if random.choice([True, False]):
            eventos_visibles.append(construir_evento(
                segundos_acumulados, nombre_equipo, "🖥️ VAR - PENAL ANULADO",
                f"El VAR revisa el cobro y {arbitros['central']} anula el penal de {tirador['nombre']}.",
                [tirador["nombre"]], "ataque"
            ))
            stats_jugadores[tirador["id"]]["tiros_puerta"] += 1
            return False, segundos_acumulados

    # En penaltis la efectividad del cobrador es alta (75% base)
    gol = resolver_duelo(0.75, attr_tirador, attr_portero)

    stats_jugadores[tirador["id"]]["tiros_puerta"] += 1

    if gol:
        stats_jugadores[tirador["id"]]["goles"] += 1
        # Contador separado de 'goles' para identificar específicamente los goles de penal de
        # tanda, análogo a 'goles_tiro_libre'/'goles_corner' (ver ejecutar_tiro_libre/
        # ejecutar_corner más abajo) -- juntos alimentan "Especialista a Balón Parado" en
        # estadisticas_service.py.
        stats_jugadores[tirador["id"]]["goles_penal"] += 1
        eventos_visibles.append(construir_evento(
            segundos_acumulados, nombre_equipo, "⚽ GOL DE PENAL",
            f"¡Gol de {tirador['nombre']} en la tanda de penaltis!",
            [tirador["nombre"]], "ataque"
        ))
        return True, segundos_acumulados
    else:
        # Si no fue gol, es atajada o cobro erróneo. 'atajadas_penales' es un contador
        # separado de 'atajadas' (que mezcla atajadas de juego abierto y de penal) para poder
        # identificar específicamente al mejor atajapenales (ver
        # estadisticas_service.py y jugadores_service.actualizar_jugadores_post_partido).
        stats_jugadores[portero["id"]]["atajadas"] += 1
        stats_jugadores[portero["id"]]["atajadas_penales"] += 1
        eventos_visibles.append(construir_evento(
            segundos_acumulados, nombre_equipo_rival, "❌ PENAL FALLADO",
            f"¡{portero['nombre']} detiene el disparo de {tirador['nombre']}!",
            [portero["nombre"], tirador["nombre"]], "ataque"
        ))
        return False, segundos_acumulados


def ejecutar_tiro_libre(equipo_atacante: dict, defensor_marcador: dict, portero_rival: dict, equipo_defensor: dict,
                         stats_jugadores: dict, eventos_visibles: list, segundos_acumulados: float, mod_precision: float = 0.0):
    """
    Ejecuta un tiro libre directo (falta en posición de disparo, ver PROB_TIRO_LIBRE_PELIGROSO
    y su enganche en las ramas de falta de simular_partido_realista). Tres sub-duelos
    secuenciales vía resolver_duelo: muro defensivo, a puerta o desviado, cobrador vs arquero.

    'equipo_defensor' (el dueño de 'portero_rival') solo se usa para atribuir correctamente el
    evento de atajada al equipo del propio arquero, no al del cobrador.

    :return: (resultado, cobrador, segundos_acumulados) donde resultado in
        {"gol", "desviado", "bloqueado", "atajado"}. El costo (Ataque/Remate, 3-7s) se suma acá
        -- es adicional al costo de Falta ya cargado por la infracción que originó el tiro libre.
    """
    candidatos = [j for j in equipo_atacante["plantilla"] if j.get("linea_partido") != 1]
    if not candidatos:
        candidatos = equipo_atacante["plantilla"]

    # Prioriza un especialista en cancha (campo ya existente en el esquema de 'jugadores' pero
    # sin usar hasta ahora); si no hay, el de mejor precisión + potencia de disparo -- mismo
    # criterio que ya usa simular_tanda_penaltis para ordenar cobradores de penal.
    especialistas = [j for j in candidatos if j.get("especialista_tiros_libres")]
    pool = especialistas if especialistas else candidatos
    cobrador = max(pool, key=lambda j: j.get("precision_tiro", 60) + j.get("fuerza_disparo", 60))

    nombre_equipo = equipo_atacante["nombre"]

    # Plus de precisión del cobrador: pie hábil ambidiestro + especialista de tiros libres (si
    # corresponde), aplicado de forma consistente en los tres sub-duelos de acá abajo.
    plus_cobrador = bonus_pie_habil(cobrador)
    if cobrador.get("especialista_tiros_libres"):
        plus_cobrador += BONUS_PRECISION_ESPECIALISTA_TIRO_LIBRE

    eventos_visibles.append(construir_evento(
        segundos_acumulados, nombre_equipo, "⏳ PREPARACIÓN",
        random.choice(FRASES_PREPARACION_TIRO_LIBRE).format(cobrador=cobrador["nombre"]),
        [cobrador["nombre"]], "ataque", es_preparacion=True
    ))
    segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_ATAQUE_REMATE)

    # 1) Muro defensivo
    attr_cobrador = (cobrador.get("precision_tiro", 60) + plus_cobrador + cobrador.get("fuerza_disparo", 60)) / 2
    attr_muro = (defensor_marcador.get("fuerza_fisica", 60) + defensor_marcador.get("anticipacion", 60)) / 2
    supera_muro = resolver_duelo(0.65, attr_cobrador, attr_muro)

    if not supera_muro:
        eventos_visibles.append(construir_evento(
            segundos_acumulados, nombre_equipo, "🧱 TIRO LIBRE BLOQUEADO",
            f"¡La barrera se interpone! El tiro libre de {cobrador['nombre']} muere en el muro defensivo.",
            [cobrador["nombre"]], "ataque"
        ))
        return "bloqueado", cobrador, segundos_acumulados

    # 2) A puerta o desviado
    attr_precision = (cobrador.get("precision_tiro", 60) + plus_cobrador) * (1 + mod_precision)
    va_a_puerta = resolver_duelo(0.55, attr_precision, defensor_marcador.get("anticipacion", 60))

    if not va_a_puerta:
        stats_jugadores[cobrador["id"]]["tiros_desviados"] += 1
        eventos_visibles.append(construir_evento(
            segundos_acumulados, nombre_equipo, "🎯 DISPARO DESVIADO",
            f"El tiro libre de {cobrador['nombre']} se va desviado, cerca del poste.",
            [cobrador["nombre"]], "ataque"
        ))
        return "desviado", cobrador, segundos_acumulados

    stats_jugadores[cobrador["id"]]["tiros_puerta"] += 1

    # 3) Cobrador vs arquero (base menor que el tiro normal/penal -- un libre directo es más difícil de convertir)
    potencia = (cobrador.get("fuerza_disparo", 60) + cobrador.get("precision_tiro", 60) + plus_cobrador) / 2 * (1 + mod_precision)
    reflejos_portero = (
        portero_rival.get("rendimiento", 60) + portero_rival.get("agilidad", 60) + portero_rival.get("concentracion", 60)
    ) / 3
    gol = resolver_duelo(0.28, potencia, reflejos_portero)

    if gol:
        stats_jugadores[cobrador["id"]]["goles"] += 1
        stats_jugadores[cobrador["id"]]["goles_tiro_libre"] += 1
        stats_jugadores[portero_rival["id"]]["goles_encajados"] += 1
        eventos_visibles.append(construir_evento(
            segundos_acumulados, nombre_equipo, "⚽ GOL DE TIRO LIBRE",
            f"¡Golazo de tiro libre de {cobrador['nombre']}! Un misil imposible de atajar para {portero_rival['nombre']}.",
            [cobrador["nombre"], portero_rival["nombre"]], "ataque"
        ))
        return "gol", cobrador, segundos_acumulados
    else:
        stats_jugadores[portero_rival["id"]]["atajadas"] += 1
        eventos_visibles.append(construir_evento(
            segundos_acumulados, equipo_defensor["nombre"], "🧤 ATAJADA ESPECTACULAR",
            f"¡{portero_rival['nombre']} vuela y saca el tiro libre de {cobrador['nombre']} bajo el travesaño!",
            [portero_rival["nombre"], cobrador["nombre"]], "ataque"
        ))
        return "atajado", cobrador, segundos_acumulados


def ejecutar_corner(equipo_atacante: dict, equipo_defensor: dict, portero_rival: dict,
                     stats_jugadores: dict, eventos_visibles: list, segundos_acumulados: float):
    """
    Ejecuta un córner (disparado desde la rama de "desvío a córner" de la resolución de un tiro
    a puerta en simular_partido_realista). Tres sub-duelos: disputa aérea, a puerta o desviado,
    rematador vs arquero.

    :return: (resultado, rematador, segundos_acumulados) donde resultado in
        {"gol", "desviado", "despejado", "atajado"}.
    """
    candidatos = [j for j in equipo_atacante["plantilla"] if j.get("linea_partido") != 1]
    if not candidatos:
        candidatos = equipo_atacante["plantilla"]

    # La mitad de las veces remata el mejor cabeceador del equipo, la otra mitad cualquiera que
    # llega al área -- evita que sea siempre el mismo jugador, sin perder realismo.
    if random.random() < 0.5:
        rematador = max(candidatos, key=lambda j: j.get("juego_aereo", 60))
    else:
        rematador = random.choice(candidatos)

    nombre_equipo = equipo_atacante["nombre"]
    defensor = obtener_oponente_segun_zona(equipo_defensor, "ataque")

    eventos_visibles.append(construir_evento(
        segundos_acumulados, nombre_equipo, "⏳ PREPARACIÓN",
        random.choice(FRASES_PREPARACION_CORNER).format(rematador=rematador["nombre"], defensor=defensor["nombre"]),
        [rematador["nombre"], defensor["nombre"]], "ataque", es_preparacion=True
    ))
    segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_ATAQUE_REMATE)

    # 1) Disputa aérea: ¿conecta el ataque o despeja la defensa?
    attr_rematador = rematador.get("juego_aereo", 60)
    attr_defensor = (defensor.get("juego_aereo", 60) + defensor.get("fuerza_fisica", 60)) / 2
    conecta = resolver_duelo(0.40, attr_rematador, attr_defensor)

    if not conecta:
        eventos_visibles.append(construir_evento(
            segundos_acumulados, equipo_defensor["nombre"], "🛡️ CÓRNER DESPEJADO",
            f"¡{defensor['nombre']} se impone en el área y despeja el córner de cabeza!",
            [defensor["nombre"]], "ataque"
        ))
        return "despejado", rematador, segundos_acumulados

    # 2) A puerta o desviado
    va_a_puerta = resolver_duelo(0.55, attr_rematador, defensor.get("anticipacion", 60))

    if not va_a_puerta:
        stats_jugadores[rematador["id"]]["tiros_desviados"] += 1
        eventos_visibles.append(construir_evento(
            segundos_acumulados, nombre_equipo, "🎯 DISPARO DESVIADO",
            f"{rematador['nombre']} conecta de cabeza el córner, pero el balón se va desviado.",
            [rematador["nombre"]], "ataque"
        ))
        return "desviado", rematador, segundos_acumulados

    stats_jugadores[rematador["id"]]["tiros_puerta"] += 1

    # 3) Rematador vs arquero
    reflejos_portero = (
        portero_rival.get("rendimiento", 60) + portero_rival.get("agilidad", 60) + portero_rival.get("concentracion", 60)
    ) / 3
    gol = resolver_duelo(0.30, attr_rematador, reflejos_portero)

    if gol:
        stats_jugadores[rematador["id"]]["goles"] += 1
        stats_jugadores[rematador["id"]]["goles_corner"] += 1
        stats_jugadores[portero_rival["id"]]["goles_encajados"] += 1
        eventos_visibles.append(construir_evento(
            segundos_acumulados, nombre_equipo, "⚽ GOL DE CÓRNER",
            f"¡Gol de {rematador['nombre']} de cabeza tras el córner! Imposible para {portero_rival['nombre']}.",
            [rematador["nombre"], portero_rival["nombre"]], "ataque"
        ))
        return "gol", rematador, segundos_acumulados
    else:
        stats_jugadores[portero_rival["id"]]["atajadas"] += 1
        eventos_visibles.append(construir_evento(
            segundos_acumulados, equipo_defensor["nombre"], "🧤 ATAJADA ESPECTACULAR",
            f"¡{portero_rival['nombre']} se estira y ataja el remate de cabeza de {rematador['nombre']}!",
            [portero_rival["nombre"], rematador["nombre"]], "ataque"
        ))
        return "atajado", rematador, segundos_acumulados

# funcion para obtener cuarteta arbitral
def obtener_cuarteta_arbitral():
    """Selecciona aleatoriamente una cuarteta de árbitros desde la BD."""
    collection_arbitros = db['arbitros']

    puestos = ["Arbitro central", "Arbitro de línea 1", "Arbitro de línea 2", "4to Arbitro"]

    # Una sola consulta con $in (en vez de un find() separado por cada uno de los 4 puestos)
    arbitros_por_puesto = defaultdict(list)
    for arbitro in collection_arbitros.find({"puesto": {"$in": puestos}}):
        arbitros_por_puesto[arbitro["puesto"]].append(arbitro)

    cuerpo_arbitral = {
        "central": random.choice(arbitros_por_puesto["Arbitro central"])["nombre"],
        "linea1": random.choice(arbitros_por_puesto["Arbitro de línea 1"])["nombre"],
        "linea2": random.choice(arbitros_por_puesto["Arbitro de línea 2"])["nombre"],
        "cuarto": random.choice(arbitros_por_puesto["4to Arbitro"])["nombre"]
    }

    return cuerpo_arbitral

# funcion para realizar sustituciones de jugadores
def realizar_sustitucion(equipo: dict, bancas: dict, sustituciones_realizadas: int, max_cambios: int, segundos_acumulados: float, stats_jugadores: dict, eventos_visibles: dict, arbitros: dict, zona_balon: str):
    """Procesa el cambio de un jugador titular por uno de la banca. Se invoca solo en paradas
    de juego del 2º tiempo -- ver el llamador en simular_partido_realista."""
    if sustituciones_realizadas >= max_cambios:
        return sustituciones_realizadas

    banca = bancas[equipo["nombre"]]
    if not banca:
        return sustituciones_realizadas

    # Seleccionar jugador a salir (priorizar los que tengan menor rating momentáneo o más desgaste)
    titulares = equipo["plantilla"]

    # ⚠️ FILTRO CRÍTICO: Excluir al portero Y a jugadores que hayan sido expulsados
    candidatos_salir = [
        j for j in titulares
        if j.get("linea_partido") != 1 and not stats_jugadores[j["id"]].get("expulsado", False) and not stats_jugadores[j["id"]].get("entro_de_cambio", False)
    ]

    if not candidatos_salir:
        return sustituciones_realizadas

    sale_jugador = random.choice(candidatos_salir) # Evitamos cambiar al portero normalmente y un expulsado

    # Buscar suplente de la misma posición si es posible
    linea_saliente = sale_jugador.get("linea_partido", 3)

    # 1. MARCAR AL JUGADOR QUE SALE EN LAS ESTADÍSTICAS
    stats_jugadores[sale_jugador["id"]]["salio_de_cambio"] = True

    # Buscar suplente
    candidatos_suplentes = [j for j in banca if j.get("posicion_id") == sale_jugador.get("posicion_id")]

    entra_jugador = random.choice(candidatos_suplentes) if candidatos_suplentes else random.choice(banca)

    # Actualizar listas de plantilla y banca
    titulares.remove(sale_jugador)
    banca.remove(entra_jugador)

    entra_jugador_copia = entra_jugador.copy()
    entra_jugador_copia["linea_partido"] = linea_saliente
    titulares.append(entra_jugador_copia)

    # Registrar stats iniciales para el jugador que entra
    stats_jugadores[entra_jugador["id"]] = {
        "id": entra_jugador["id"],
        "nombre": entra_jugador["nombre"],
        "posicion": POSICIONES.get(linea_saliente, "MEDIO"),
        "equipo": equipo["nombre"],
        "entro_de_cambio": True,
        "salio_de_cambio": False,
        "pases_completados": 0, "pases_fallados": 0,
        "regates_exitosos": 0, "pérdidas": 0, "recuperaciones": 0,
        "tiros_puerta": 0, "tiros_desviados": 0, "goles": 0,
        "goles_penal": 0, "goles_tiro_libre": 0, "goles_corner": 0, "asistencias": 0,
        "faltas": 0, "faltas_recibidas": 0, "amarillas": 0, "rojas": 0,
        # Por si el suplente que entra es un arquero (poco común, pero posible):
        # 'atajadas'/'atajadas_penales' no viven acá arriba como el resto de métricas de
        # portero (mismo criterio que ya tenía este dict antes), pero sí se pre-siembra
        # 'atajadas_penales' para que un penal atajado por un arquero suplente no falle con
        # KeyError -- 'atajadas' (la general) queda con el mismo comportamiento previo.
        "atajadas_penales": 0,
        "lado": stats_jugadores[sale_jugador["id"]]["lado"]
    }

    eventos_visibles.append(construir_evento(
        segundos_acumulados, equipo["nombre"], "🔄 SUSTITUCIÓN",
        f"Entra {entra_jugador['nombre']} sustituyendo a {sale_jugador['nombre']}. (Anunciado por el 4to Árbitro: {arbitros['cuarto']})",
        [entra_jugador["nombre"], sale_jugador["nombre"]], zona_balon
    ))

    return sustituciones_realizadas + 1

# funcion para generar opinion del partido
def generar_opinion_partido(resultado: dict, stats_jugadores: dict) -> str:
    goles_l = resultado["goles_local"]
    goles_v = resultado["goles_visitante"]
    total_goles = goles_l + goles_v
    local = resultado["local"]
    visitante = resultado["visitante"]
    penaltis_l = resultado.get("penaltis_local")
    penaltis_v = resultado.get("penaltis_visitante")

    # Contadores de métricas globales del partido
    total_rojas = sum(1 for e in resultado["eventos"] if "ROJA" in e["tipo"])
    total_var = sum(1 for e in resultado["eventos"] if "VAR" in e["tipo"])

    # 1. Calificación de la emoción / ritmo del juego
    if total_goles >= 5:
        ritmo = "¡Un festival ofensivo inolvidable! Ambas escuadras priorizaron el ataque y regalaron un espectáculo repleto de emociones."
    elif total_goles in [3, 4]:
        ritmo = "Un encuentro sumamente dinámico y entretenido, con buenas fases de fútbol y un ritmo constante de ida y vuelta."
    elif total_goles in [1, 2]:
        ritmo = "Un partido táctico y disputado en cada rincón del campo. Ninguno regaló espacios y las defensas prevalecieron."
    else:
        ritmo = "Un duelo trabado y carente de ideas en el último tercio. La falta de contundencia primó a lo largo de los 90 minutos."

    # 2. Análisis del resultado y desarrollo
    if penaltis_l is not None:
        ganador_p = local if penaltis_l > penaltis_v else visitante
        desarrollo = f"Tras una batalla extenuante de 120 minutos que terminó en tablas, la tensión se trasladó a los lanzamientos desde el punto penal, donde {ganador_p} mantuvo la sangre fría para sellar la victoria ({penaltis_l}-{penaltis_v})."
    elif goles_l == goles_v:
        desarrollo = f"El empate refleja la paridad vista en el terreno de juego. Tanto {local} como {visitante} tuvieron momentos de dominio, pero ninguno logró dar el golpe definitivo."
    else:
        ganador = local if goles_l > goles_v else visitante
        perdedor = visitante if goles_l > goles_v else local
        dif = abs(goles_l - goles_v)

        if dif >= 3:
            desarrollo = f"{ganador} pasó por encima de {perdedor} con una actuación categórica e inapelable, demostrando una clara superioridad colectiva."
        elif dif == 2:
            desarrollo = f"{ganador} supo golpear en los momentos clave del partido y manejar los tiempos para asegurar un triunfo muy solvente."
        else:
            desarrollo = f"Triunfo muy ajustado para {ganador}. {perdedor} luchó hasta el último suspiro, pero la efectividad inclinó la balanza por la mínima diferencia."

    # 3. Menciones especiales por incidentes clave
    incidentes = []
    if total_rojas > 0:
        incidentes.append("El encuentro se vio fuertemente condicionado por las expulsiones y el juego brusco.")
    if total_var > 0:
        incidentes.append("El VAR tuvo protagonismo e intervenciones decisivas que cambiaron el rumbo del marcador.")

    texto_incidentes = " " + " ".join(incidentes) if incidentes else ""

    # 4. Jugador destacado (MVP)
    mvp = max(stats_jugadores.values(), key=lambda j: j.get("rating", 0))
    mencion_mvp = f"La gran figura del encuentro fue {mvp['nombre']} ({mvp['equipo']}), quien firmó una actuación sobresaliente con una calificación de {mvp['rating']}."

    # Conclusión final
    opinion_final = f"{ritmo} {desarrollo}{texto_incidentes} {mencion_mvp}"
    return opinion_final

# funcion para calcular el rating de un jugador en un partido
def calcular_rating_partido(stats: dict) -> float:
    rating = 6.0
    posicion = stats.get("posicion", "MEDIO")

    # LÓGICA EXCLUSIVA PARA EL PORTERO
    if posicion == "PORTERO":
        # 1. Acciones Positivas
        rating += stats.get("atajadas", 0) * 0.60     # +0.6 por cada atajada determinante
        rating += stats.get("desvios", 0) * 0.35      # +0.35 por desvío/rechace
        rating += stats.get("goles", 0) * 3.0         # Si un portero anota un gol
        rating += stats.get("asistencias", 0) * 1.0   # Asistencia de portero (saque largo, etc.)

        # 2. Juego con los pies
        rating += stats["pases_completados"] * 0.04

        # 3. Acciones Negativas
        rating -= stats.get("goles_encajados", 0) * 0.40  # -0.40 por gol recibido
        rating -= stats.get("errores_graves", 0) * 1.20   # -1.20 por falla garrafal
        rating -= stats["pases_fallados"] * 0.08
        rating -= stats["amarillas"] * 0.60
        rating -= stats["rojas"] * 2.50

        return round(max(3.0, min(10.0, rating)), 1)

    # 1. GOLES Y ASISTENCIAS
    if posicion in ["DEFENSA"]:
        rating += stats["goles"] * 2.0
        rating += stats.get("asistencias", 0) * 1.2
    elif posicion == "MEDIO":
        rating += stats["goles"] * 1.6
        rating += stats.get("asistencias", 0) * 1.0
    else:
        rating += stats["goles"] * 1.3
        rating += stats.get("asistencias", 0) * 0.8

    # 2. IMPACTO OFENSIVO
    rating += stats["tiros_puerta"] * 0.40
    rating += stats["regates_exitosos"] * 0.35

    # 3. PASES (Jerarquía: MEDIOS > DEFENSA > DELANTERO)
    pases_totales = stats["pases_completados"] + stats["pases_fallados"]
    if posicion == "MEDIO":
        rating += stats["pases_completados"] * 0.15
    elif posicion == "DEFENSA":
        rating += stats["pases_completados"] * 0.10
    else:
        rating += stats["pases_completados"] * 0.08

    # Bono de efectividad en pases
    if pases_totales >= 3:
        precision_pases = stats["pases_completados"] / pases_totales
        if precision_pases >= 0.80:
            rating += 0.5
        elif precision_pases >= 0.65:
            rating += 0.2

    # 4. RECUPERACIONES Y TRABAJO DEFENSIVO
    if posicion == "DEFENSA":
        rating += stats["recuperaciones"] * 0.50
    elif posicion == "MEDIO":
        rating += stats["recuperaciones"] * 0.40
    else:
        rating += stats["recuperaciones"] * 0.25

    # 5. BONO DE PARTICIPACIÓN (Premia el volumen de juego)
    acciones_totales = pases_totales + stats["regates_exitosos"] + stats["recuperaciones"] + stats["tiros_puerta"]
    if acciones_totales >= 8:
        rating += 0.6
    elif acciones_totales >= 5:
        rating += 0.3

    # 5. PENALIZACIONES
    if posicion == "DEFENSA":
        rating -= stats["pérdidas"] * 0.35
        rating -= stats["pases_fallados"] * 0.12
    elif posicion == "MEDIO":
        rating -= stats["pérdidas"] * 0.25
        rating -= stats["pases_fallados"] * 0.08
    else:
        rating -= stats["pérdidas"] * 0.15
        rating -= stats["pases_fallados"] * 0.05

    rating -= stats["tiros_desviados"] * 0.10
    rating -= stats["faltas"] * 0.12
    rating -= stats["amarillas"] * 0.60
    rating -= stats["rojas"] * 2.50

    # ⚠️ CASTIGO Y TOPE POR TARJETA ROJA
    if stats.get("rojas", 0) > 0:
        rating -= 3.5
        # Garantiza que el rating máximo para un expulsado sea 4.5
        return round(max(3.0, min(4.5, rating)), 1)

    return round(max(3.0, min(10.0, rating)), 1)

# funcion para calcular métricas de equipo a partir de stats individuales
def calcular_metricas_equipo(stats_jugadores: dict, goles_local: int, goles_visitante: int) -> dict:
    # Agrupadores iniciales
    m = {
        "L": {"pases": 0, "tiros_puerta": 0, "tiros_desviados": 0, "regates": 0, "recuperaciones": 0, "faltas": 0},
        "V": {"pases": 0, "tiros_puerta": 0, "tiros_desviados": 0, "regates": 0, "recuperaciones": 0, "faltas": 0}
    }

    # Sumar stats individuales agrupadas por lado ('L' local, 'V' visitante)
    for s in stats_jugadores.values():
        lado = s.get("lado", "L")
        m[lado]["pases"] += (s.get("pases_completados", 0) + s.get("pases_fallados", 0))
        m[lado]["tiros_puerta"] += s.get("tiros_puerta", 0)
        m[lado]["tiros_desviados"] += s.get("tiros_desviados", 0)
        m[lado]["regates"] += s.get("regates_exitosos", 0)
        m[lado]["recuperaciones"] += s.get("recuperaciones", 0)
        m[lado]["faltas"] += s.get("faltas", 0)

    # Totales acumulados
    total_pases = m["L"]["pases"] + m["V"]["pases"] or 1

    total_tiros_l = m["L"]["tiros_puerta"] + m["L"]["tiros_desviados"]
    total_tiros_v = m["V"]["tiros_puerta"] + m["V"]["tiros_desviados"]

    acciones_ofensivas_l = total_tiros_l + m["L"]["regates"]
    acciones_ofensivas_v = total_tiros_v + m["V"]["regates"]
    total_ofensiva = acciones_ofensivas_l + acciones_ofensivas_v or 1

    acciones_defensivas_l = m["L"]["recuperaciones"] + m["L"]["faltas"]
    acciones_defensivas_v = m["V"]["recuperaciones"] + m["V"]["faltas"]
    total_defensiva = acciones_defensivas_l + acciones_defensivas_v or 1

    # Métricas calculadas
    # 'tiros_totales' (a puerta + desviados) se persiste además de 'efectividad_gol' para poder
    # calcular, a nivel torneo, una efectividad de gol REAL por país (goles totales / tiros
    # totales acumulados en TODOS los partidos) en vez de solo el promedio de este % partido a
    # partido -- ver estadisticas_service._calcular_estadisticas_reales_paises.
    return {
        "local": {
            "p_posesion": round((m["L"]["pases"] / total_pases) * 100, 1),
            "p_ofensiva": round((acciones_ofensivas_l / total_ofensiva) * 100, 1),
            "p_defensiva": round((acciones_defensivas_l / total_defensiva) * 100, 1),
            "efectividad_gol": round((goles_local / total_tiros_l * 100), 1) if total_tiros_l > 0 else 0.0,
            "promedio_gol": round(goles_local / total_tiros_l, 2) if total_tiros_l > 0 else 0.0,
            "tiros_totales": total_tiros_l
        },
        "visitante": {
            "p_posesion": round((m["V"]["pases"] / total_pases) * 100, 1),
            "p_ofensiva": round((acciones_ofensivas_v / total_ofensiva) * 100, 1),
            "p_defensiva": round((acciones_defensivas_v / total_defensiva) * 100, 1),
            "efectividad_gol": round((goles_visitante / total_tiros_v * 100), 1) if total_tiros_v > 0 else 0.0,
            "promedio_gol": round(goles_visitante / total_tiros_v, 2) if total_tiros_v > 0 else 0.0,
            "tiros_totales": total_tiros_v
        }
    }

# Función para procesar la expulsión de un jugador
def procesar_expulsion(jugador: dict, equipo: dict, stats_jugadores: dict, eventos_visibles: list, segundos_acumulados: float, zona_balon: str, es_doble_amarilla: bool = False):
    """Saca al jugador del campo en tiempo real y marca sus flags de suspensión."""
    j_id = jugador["id"]
    stats = stats_jugadores[j_id]

    # ⚠️ SE ASEGURA QUE SE REGISTRE LA ROJA EN LAS STATS
    stats["rojas"] += 1
    stats["expulsado"] = True
    stats["suspendido_siguiente_partido"] = True
    stats["motivo_sancion"] = "DOBLE_AMARILLA" if es_doble_amarilla else "ROJA_DIRECTA"

    # ❌ Retirar del terreno de juego inmediatamente
    if jugador in equipo["plantilla"]:
        equipo["plantilla"].remove(jugador)

    tipo_evt = "🟨🟥 DOBLE AMARILLA" if es_doble_amarilla else "🟥 TARJETA ROJA"
    desc_evt = (f"¡Segunda amarilla! {jugador['nombre']} se va expulsado."
                if es_doble_amarilla else
                f"¡Entrada desmedida! {jugador['nombre']} recibe roja directa.")

    eventos_visibles.append(construir_evento(
        segundos_acumulados, equipo["nombre"], tipo_evt, desc_evt, [jugador["nombre"]], zona_balon
    ))

# -------------------------------------------------------------------------
# SIMULACIÓN PRINCIPAL
# -------------------------------------------------------------------------
def simular_partido_realista(id_local: int, id_visitante: int, tiempo_extra: bool = False, clima: dict = None, marcador_ida: dict = None):
    goles_local = 0
    goles_visitante = 0

    # Modificadores del clima del encuentro (ver generar_clima_partido en juegos_service.py).
    # modificador_desgaste no se aplica: el simulador no lleva un mecanismo de fatiga por minutos.
    modificadores_clima = (clima or {}).get("modificadores", {})
    mod_precision = modificadores_clima.get("precision", 0.0)
    mod_faltas = modificadores_clima.get("faltas", 0.0)

    # Goles ya anotados en la ida (ver obtener_marcador_ida_grupo_dos_equipos en juegos_service.py),
    # reasignados a las posiciones local/visitante de ESTE partido (la vuelta). Se usan para decidir
    # tiempo extra/penales por marcador GLOBAL (ida + vuelta) en eliminatorias de grupos de 2 equipos.
    goles_ida_local = (marcador_ida or {}).get("goles_local", 0)
    goles_ida_visita = (marcador_ida or {}).get("goles_visita", 0)

    def hay_empate_global():
        return (goles_local + goles_ida_local) == (goles_visitante + goles_ida_visita)

    collection = db['jugadores']
    collection_paises = db['paises']

    pais_local = collection_paises.find_one({"id": id_local})
    pais_visitante = collection_paises.find_one({"id": id_visitante})

    # Cargar Árbitros
    arbitros = obtener_cuarteta_arbitral()

    plantilla_local_temp = list(collection.find({"pais_id": id_local}))
    plantilla_visitante_temp = list(collection.find({"pais_id": id_visitante}))

    tactica_elegida_local = random.choice(TACTICAS)
    tactica_elegida_visita = random.choice(TACTICAS)

    # 11 titulares
    plantilla_local = seleccionar_plantilla_titular(plantilla_local_temp, esquema=tactica_elegida_local)
    plantilla_visitante = seleccionar_plantilla_titular(plantilla_visitante_temp, esquema=tactica_elegida_visita)

    # Nombres del 11 inicial, capturados ANTES de que 'plantilla_local'/'plantilla_visitante'
    # empiecen a mutar con sustituciones/expulsiones (son la misma lista que queda referenciada
    # en 'equipo_local["plantilla"]"/"equipo_visitante["plantilla"]" más abajo) -- se persisten en
    # 'resultado' para que la Cancha en Vivo sepa quién arrancó de titular sin tener que adivinar.
    nombres_titulares_local = [j["nombre"] for j in plantilla_local]
    nombres_titulares_visitante = [j["nombre"] for j in plantilla_visitante]

    # Bancas de suplentes (resto de jugadores)
    ids_titulares_local = {j["id"] for j in plantilla_local}
    ids_titulares_visita = {j["id"] for j in plantilla_visitante}

    bancas = {
        pais_local["nombre"]: [j for j in plantilla_local_temp if j["id"] not in ids_titulares_local],
        pais_visitante["nombre"]: [j for j in plantilla_visitante_temp if j["id"] not in ids_titulares_visita]
    }

    # Control de Cambios
    cambios_realizados = {pais_local["nombre"]: 0, pais_visitante["nombre"]: 0}
    max_cambios = 5

    equipo_local = {"nombre": pais_local["nombre"], "plantilla": plantilla_local}
    equipo_visitante = {"nombre": pais_visitante["nombre"], "plantilla": plantilla_visitante}

    # Tácticas por equipo (referenciable por nombre) -- usadas por los bonos de formación, ver
    # BONUS_FORMACION_* más arriba.
    tactica_por_equipo = {
        equipo_local["nombre"]: tactica_elegida_local,
        equipo_visitante["nombre"]: tactica_elegida_visita
    }

    stats_jugadores = {
        j["id"]: {
            "id": j["id"],
            "nombre": j["nombre"],
            "posicion": POSICIONES.get(j["linea_partido"], "MEDIO"),
            "equipo": equipo_local["nombre"] if j in equipo_local["plantilla"] else equipo_visitante["nombre"],
            "entro_de_cambio": False,
            "salio_de_cambio": False,
            "pases_completados": 0,
            "pases_fallados": 0,
            "regates_exitosos": 0,
            "pérdidas": 0,
            "recuperaciones": 0,
            "tiros_puerta": 0,
            "tiros_desviados": 0,
            "goles": 0,
            "goles_penal": 0,
            "goles_tiro_libre": 0,
            "goles_corner": 0,
            "asistencias": 0,
            "faltas": 0,
            "faltas_recibidas": 0,
            # 🧤 MÉTRICAS EXCLUSIVAS DE PORTERO:
            "atajadas": 0,
            "atajadas_penales": 0,
            "desvios": 0,
            "goles_encajados": 0,
            "errores_graves": 0,
            "amarillas": 0,
            "rojas": 0,
            "lado": "L" if j in equipo_local["plantilla"] else "V"
        }
        for j in equipo_local["plantilla"] + equipo_visitante["plantilla"]
    }

    eventos_visibles = []
    segundos_acumulados = 0.0
    equipo_con_balon = equipo_local
    equipo_defensor = equipo_visitante

    # Registra quién hizo el último pase de campo (no despeje) recibido por el poseedor
    # actual del balón, para poder atribuirle la asistencia si ese poseedor anota.
    # Se limpia (None) en cualquier pérdida de posesión, ya que corta la jugada de gol.
    posible_asistente = None

    portero_local = next((j for j in equipo_local["plantilla"] if j.get("linea_partido") == 1), equipo_local["plantilla"][0])
    portero_visitante = next((j for j in equipo_visitante["plantilla"] if j.get("linea_partido") == 1), equipo_visitante["plantilla"][0])

    medios_iniciales = [j for j in equipo_local["plantilla"] if j.get("linea_partido") == 3]
    jugador_con_balon = random.choice(medios_iniciales if medios_iniciales else equipo_local["plantilla"])
    zona_balon = "medio"

    eventos_visibles.append(construir_evento(
        segundos_acumulados, "Árbitro Central", "👉 SILBATO INICIAL",
        f"¡Arranca el partido entre {equipo_local['nombre']} y {equipo_visitante['nombre']}!",
        [], zona_balon
    ))

    # Puesta en juego: el saque de centro lo toca un delantero hacia el mediocampista ya elegido
    # arriba como 'jugador_con_balon' -- no cambia ningún estado (zona/jugador ya están
    # calculados), solo narra el primer toque del partido, que antes quedaba sin evento (un pase
    # exitoso no genera evento visible) y el primer evento que se veía ya era un duelo/presión.
    delanteros_iniciales = [j for j in equipo_local["plantilla"] if j.get("linea_partido") == 4]
    sacador_inicial = random.choice(delanteros_iniciales if delanteros_iniciales else equipo_local["plantilla"])
    eventos_visibles.append(construir_evento(
        segundos_acumulados, equipo_local["nombre"], "🔵 SAQUE DE CENTRO",
        f"{equipo_local['nombre']} pone el balón en juego: {sacador_inicial['nombre']} toca corto para {jugador_con_balon['nombre']}.",
        [sacador_inicial["nombre"], jugador_con_balon["nombre"]], zona_balon
    ))

    # Duración objetivo: 90' reglamentarios, pasa a 120' si hay tiempo extra (ver evaluación más
    # abajo). El primer tiempo cierra de forma cosmética al cruzar DURACION_MEDIO_TIEMPO (2700s)
    # -- un solo bucle continuo, no dos sub-fases separadas (ver plan).
    duracion_objetivo = DURACION_TIEMPO_REGLAMENTARIO
    primer_tiempo_cerrado = False

    while segundos_acumulados < duracion_objetivo:
        portero_rival = portero_visitante if equipo_con_balon == equipo_local else portero_local
        defensor_marcador = obtener_oponente_segun_zona(equipo_defensor, zona_balon)
        posicion_jugador = jugador_con_balon.get("linea_partido", 3)

        # --- CIERRE COSMÉTICO DEL 1ER TIEMPO ---
        if not primer_tiempo_cerrado and segundos_acumulados >= DURACION_MEDIO_TIEMPO:
            primer_tiempo_cerrado = True
            eventos_visibles.append(construir_evento(
                segundos_acumulados, "Árbitro", "🚩 FINAL DEL PRIMER TIEMPO",
                f"El árbitro {arbitros['central']} pita el final de la primera mitad. {equipo_local['nombre']} {goles_local} - {goles_visitante} {equipo_visitante['nombre']}.",
                [], zona_balon
            ))

        # --- PROBABILIDAD DE REALIZAR SUSTITUCIÓN ---
        # Solo en paradas de juego reales (después de narrar falta/tarjeta/fuera de
        # juego/gol/corner/tiro libre, ver los 'continue'/puntos de parón de abajo) y solo en el
        # 2º tiempo -- antes se evaluaba en CUALQUIER iteración desde el minuto 55, sin
        # distinguir si el juego estaba detenido.
        def _intentar_sustitucion():
            nonlocal segundos_acumulados
            if segundos_acumulados < DURACION_MEDIO_TIEMPO:
                return
            if random.random() < 0.08:
                equipo_cambio = random.choice([equipo_local, equipo_visitante])
                nombre_eq = equipo_cambio["nombre"]
                cambios_realizados[nombre_eq] = realizar_sustitucion(
                    equipo_cambio, bancas, cambios_realizados[nombre_eq], max_cambios, segundos_acumulados,
                    stats_jugadores, eventos_visibles, arbitros, zona_balon
                )
                segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_SUSTITUCION)

        # --- EVENTO CASUAL: FUERA DE LUGAR (Marcado por Jueces de Línea) ---
        if zona_balon == "ataque" and random.random() < 0.05:
            linea_arbitro = random.choice([arbitros["linea1"], arbitros["linea2"]])
            eventos_visibles.append(construir_evento(
                segundos_acumulados, equipo_con_balon["nombre"], "🚩 FUERA DE LUGAR",
                f"El juez de línea ({linea_arbitro}) señala posición adelantada de {jugador_con_balon['nombre']}.",
                [jugador_con_balon["nombre"]], zona_balon
            ))
            segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_OFFSIDE)
            equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
            jugador_con_balon = portero_rival
            zona_balon = "defensa"
            posible_asistente = None
            _intentar_sustitucion()
            continue

        # --- OPCIONES SEGÚN POSICIÓN Y ZONA ---
        # Pesos de disparo bajados (65->10 / 45->5, resto redistribuido a pase/regate): con el
        # reloj de segundos, acciones baratas (pase/tiro cuestan pocos segundos) entran muchas
        # más veces en los 5400s de partido que con el viejo loop por minuto -- el mismo peso de
        # "tiro" de antes, a este volumen de acciones, disparaba marcadores de 10+ goles por
        # partido. Un primer recorte a 22/12 solo bajó el promedio de 17.2 a 7.1 goles/partido
        # (la relación no es lineal: al bajar el peso de tiro, el equipo pasa más tiempo
        # circulando DENTRO de la zona de ataque en vez de perderla, compensando parte del
        # recorte) -- se ajustó más agresivo hasta calibrar contra partidos reales medidos.
        if zona_balon == "ataque":
            if posicion_jugador == 4:
                opciones, pesos = ["tiro", "regate", "pase"], [7, 31, 62]
            else:
                opciones, pesos = ["tiro", "pase", "regate"], [3, 67, 30]

        elif zona_balon == "medio":
            opciones, pesos = ["pase_profundo", "pase", "regate"], [35, 45, 20]

        else:
            if posicion_jugador == 1:
                opciones, pesos = ["pase", "despeje"], [70, 30]
            else:
                opciones, pesos = ["pase", "regate"], [75, 25]

        accion = random.choices(opciones, weights=pesos)[0]

        # --- ACCIÓN: PASE / PASE PROFUNDO / DESPEJE ---
        if accion in ["pase", "pase_profundo", "despeje"]:
            # Ejemplo en acción PASE:
            efectividad_pase = (jugador_con_balon.get("precision_pase", 60) + jugador_con_balon.get("vision_juego", 60)) / 2

            # Bonos de formación (ver BONUS_FORMACION_* arriba): 3-5-2 conserva mejor el balón
            # en mediocampo, 4-3-3 progresa mejor de mediocampo a ataque por bandas.
            tactica_propia = tactica_por_equipo[equipo_con_balon["nombre"]]
            if zona_balon == "medio" and tactica_propia == "3-5-2":
                efectividad_pase += BONUS_FORMACION_POSESION_3_5_2
            if accion == "pase_profundo" and tactica_propia == "4-3-3":
                efectividad_pase += BONUS_FORMACION_PROGRESION_4_3_3

            efectividad_pase = max(0.0, efectividad_pase * (1 + mod_precision))
            defensa_rival = (defensor_marcador.get("anticipacion", 60) + defensor_marcador.get("concentracion", 60)) / 2

            # Bono de formación defensiva: 4-4-2 intercepta mejor en zona propia.
            tactica_rival = tactica_por_equipo[equipo_defensor["nombre"]]
            if zona_balon == "defensa" and tactica_rival == "4-4-2":
                defensa_rival += BONUS_FORMACION_INTERCEPCION_4_4_2

            exito = resolver_duelo(0.85, efectividad_pase, defensa_rival)
            segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_TRANSICION)

            if exito:
                stats_jugadores[jugador_con_balon["id"]]["pases_completados"] += 1
                if accion == "pase_profundo" and zona_balon == "medio":
                    zona_balon = "ataque"
                elif zona_balon == "defensa":
                    zona_balon = "medio"

                siguiente_linea = 4 if zona_balon == "ataque" else (3 if zona_balon == "medio" else 2)
                candidatos = [j for j in equipo_con_balon["plantilla"] if j.get("linea_partido") == siguiente_linea and j["id"] != jugador_con_balon["id"]]

                if not candidatos:
                    candidatos = [j for j in equipo_con_balon["plantilla"] if j.get("linea_partido") == 3 and j["id"] != jugador_con_balon["id"]]
                if not candidatos:
                    candidatos = [j for j in equipo_con_balon["plantilla"] if j["id"] != jugador_con_balon["id"]]

                candidatos.sort(key=lambda j: stats_jugadores[j["id"]]["pases_completados"] + stats_jugadores[j["id"]]["pases_fallados"])

                # Un despeje (salida de emergencia del portero) no cuenta como jugada de asistencia;
                # un pase de campo sí queda "en el aire" como posible asistencia del próximo goleador.
                if accion == "despeje":
                    posible_asistente = None
                else:
                    posible_asistente = {"id": jugador_con_balon["id"], "nombre": jugador_con_balon["nombre"]}

                jugador_con_balon = candidatos[0] if random.random() < 0.70 else random.choice(candidatos)

            else:
                stats_jugadores[jugador_con_balon["id"]]["pases_fallados"] += 1
                stats_jugadores[defensor_marcador["id"]]["recuperaciones"] += 1
                posible_asistente = None

                # La probabilidad de falta sube si el defensor es muy agresivo o tiene poca compostura
                agresividad_def = defensor_marcador.get("agresividad", 60)
                compostura_def = defensor_marcador.get("compostura", 60)

                # Un jugador con 90% agresividad sube la prob de falta; uno con 90% compostura la baja
                # (valores calibrados empíricamente -- ver diagnostico_tarjetas.py -- para que el
                # total de faltas/tarjetas por partido se acerque al promedio real de fútbol,
                # dado el volumen de iteraciones que corren ahora en el motor de segundos)
                prob_falta = 0.15 + ((agresividad_def - compostura_def) / 200.0) + mod_faltas
                prob_falta = max(0.06, min(0.32, prob_falta))  # Mantener dentro de rangos cuerdos

                if random.random() < prob_falta:
                    stats_jugadores[defensor_marcador["id"]]["faltas"] += 1
                    # 'jugador_con_balon' acá todavía es el atacante que sufrió la falta -- la
                    # reasignación a 'defensor_marcador' pasa más abajo, después de este bloque.
                    stats_jugadores[jugador_con_balon["id"]]["faltas_recibidas"] += 1

                    eventos_visibles.append(construir_evento(
                        segundos_acumulados, equipo_defensor["nombre"], "🔥 PRESIÓN DEFENSIVA",
                        random.choice(FRASES_PRESION_FALTA_PASE).format(
                            defensor=defensor_marcador["nombre"], atacante=jugador_con_balon["nombre"]
                        ),
                        [defensor_marcador["nombre"], jugador_con_balon["nombre"]], zona_balon, es_preparacion=True
                    ))
                    segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_FALTA)

                    # Si el jugador es agresivo, incrementa ligeramente la probabilidad de tarjeta dura
                    factor_agresivo = agresividad_def / 100.0
                    rand_tarjeta = random.random()

                    # 🟥 ROJA DIRECTA (calibrado -- ver diagnostico_tarjetas.py)
                    if rand_tarjeta < (0.006 * factor_agresivo):
                        # --- REVISIÓN DEL VAR sobre una posible roja directa ---
                        if hay_revision_var() and random.choice([True, False]):
                            # El VAR baja la sanción a amarilla
                            stats_jugadores[defensor_marcador["id"]]["amarillas"] += 1
                            eventos_visibles.append(construir_evento(
                                segundos_acumulados, equipo_defensor["nombre"], "🖥️ VAR - TARJETA REVISADA",
                                f"El VAR revisa la entrada de {defensor_marcador['nombre']} y {arbitros['central']} la baja a amarilla.",
                                [defensor_marcador["nombre"]], zona_balon
                            ))
                        else:
                            procesar_expulsion(defensor_marcador, equipo_defensor, stats_jugadores, eventos_visibles, segundos_acumulados, zona_balon, es_doble_amarilla=False)
                        segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_VAR_ROJA_PENAL)

                    # 🟨 TARJETA AMARILLA (calibrado -- ver diagnostico_tarjetas.py)
                    elif rand_tarjeta < (0.12 * factor_agresivo):
                        stats_jugadores[defensor_marcador["id"]]["amarillas"] += 1

                        # ⚠️ VALIDAR DOBLE AMARILLA
                        if stats_jugadores[defensor_marcador["id"]]["amarillas"] >= 2:
                            procesar_expulsion(defensor_marcador, equipo_defensor, stats_jugadores, eventos_visibles, segundos_acumulados, zona_balon, es_doble_amarilla=True)
                            segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_VAR_ROJA_PENAL)
                        else:
                            eventos_visibles.append(construir_evento(
                                segundos_acumulados, equipo_defensor["nombre"], "🟨 TARJETA AMARILLA",
                                f"Amonestación para {defensor_marcador['nombre']} por juego brusco.",
                                [defensor_marcador["nombre"]], zona_balon
                            ))
                    else:
                        eventos_visibles.append(construir_evento(
                            segundos_acumulados, equipo_defensor["nombre"], "🛑 FALTA",
                            f"Falta táctica de {defensor_marcador['nombre']}.",
                            [defensor_marcador["nombre"]], zona_balon
                        ))

                    # Falta en el tercio de ataque: probabilidad de que sea un tiro libre
                    # directo en posición de disparo (ver PROB_TIRO_LIBRE_PELIGROSO y
                    # ejecutar_tiro_libre), en vez de solo continuar el juego con la pelota.
                    # 'equipo_con_balon'/'jugador_con_balon' acá todavía son el equipo/atacante
                    # infringido -- el swap de posesión normal pasa recién más abajo. Se
                    # resuelve la posesión acá mismo y se salta ese hand-off con 'continue',
                    # mismo patrón que ya usan los cortes de VAR/offside en este archivo.
                    if zona_balon == "ataque" and random.random() < PROB_TIRO_LIBRE_PELIGROSO:
                        resultado_tl, _, segundos_acumulados = ejecutar_tiro_libre(
                            equipo_con_balon, defensor_marcador, portero_rival, equipo_defensor,
                            stats_jugadores, eventos_visibles, segundos_acumulados, mod_precision
                        )
                        if resultado_tl == "gol":
                            if equipo_con_balon == equipo_local:
                                goles_local += 1
                            else:
                                goles_visitante += 1
                            equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                            medios = [j for j in equipo_con_balon["plantilla"] if j.get("linea_partido") == 3]
                            jugador_con_balon = random.choice(medios if medios else equipo_con_balon["plantilla"])
                            zona_balon = "medio"
                        else:
                            equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                            jugador_con_balon = portero_rival
                            zona_balon = "defensa"
                        posible_asistente = None
                        _intentar_sustitucion()
                        continue

                    # Si no hubo tiro libre directo, el equipo ATACANTE (el que sufrió la falta)
                    # reanuda el juego con un tiro libre indirecto/rápido -- conserva la pelota.
                    # Antes esta rama caía en el mismo swap de posesión de más abajo que un robo
                    # de balón limpio, como si cometer la falta premiara al infractor con el
                    # balón (se veía como un cambio de posesión ilógico en la cronología).
                    _intentar_sustitucion()
                    continue

                elif zona_balon == "defensa" and random.random() < 0.35:
                    # Si el balón se pierde en zona defensiva, existe la probabilidad de un fallo del portero:
                    if random.random() < 0.03:
                        stats_jugadores[portero_rival["id"]]["errores_graves"] += 1
                        eventos_visibles.append(construir_evento(
                            segundos_acumulados, equipo_defensor["nombre"], "⚠️ ERROR DE PORTERÍA",
                            f"¡Error grave de {portero_rival['nombre']} en la salida que casi termina en gol!",
                            [portero_rival["nombre"]], zona_balon
                        ))

                    eventos_visibles.append(construir_evento(
                        segundos_acumulados, equipo_defensor["nombre"], "🔥 PRESIÓN DEFENSIVA",
                        random.choice(FRASES_PRESION_ROBO).format(
                            defensor=defensor_marcador["nombre"], rival=equipo_con_balon["nombre"]
                        ),
                        [defensor_marcador["nombre"]], zona_balon, es_preparacion=True
                    ))
                    eventos_visibles.append(construir_evento(
                        segundos_acumulados, equipo_defensor["nombre"], "🧠 ROBO DE BALÓN",
                        f"¡Gran presión de {defensor_marcador['nombre']}! Recupera el balón en zona peligrosa.",
                        [defensor_marcador["nombre"]], zona_balon
                    ))

                else:
                    # Turnover "silencioso": no hubo falta ni el robo en zona defensiva de
                    # arriba -- es la mayoría de las pérdidas de balón (todo pase fallido fuera
                    # de esos dos casos). Antes no generaba ningún evento, lo que se sentía como
                    # un salto abrupto de posesión en la línea de tiempo.
                    eventos_visibles.append(construir_evento(
                        segundos_acumulados, equipo_defensor["nombre"], "⚡ EN TRANSICIÓN",
                        random.choice(FRASES_TRANSICION_PASE).format(
                            defensor=defensor_marcador["nombre"], atacante=jugador_con_balon["nombre"],
                            equipo=equipo_defensor["nombre"], rival=equipo_con_balon["nombre"]
                        ),
                        [defensor_marcador["nombre"], jugador_con_balon["nombre"]], zona_balon, es_preparacion=True
                    ))

                equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                # Si 'defensor_marcador' fue expulsado arriba (roja directa o doble amarilla),
                # ya no está en el campo -- no puede quedarse con la pelota. La posesión pasa a
                # un compañero suyo (ya excluido de "plantilla" por procesar_expulsion).
                if stats_jugadores[defensor_marcador["id"]].get("expulsado"):
                    jugador_con_balon = random.choice(equipo_con_balon["plantilla"]) if equipo_con_balon["plantilla"] else defensor_marcador
                else:
                    jugador_con_balon = defensor_marcador
                zona_balon = "medio" if zona_balon == "ataque" else "defensa"

        # --- ACCIÓN: REGATE ---
        elif accion == "regate":
            # Ejemplo en acción REGATE:
            # Atacante: Regate + Agilidad + Velocidad
            attr_regateador = (
                jugador_con_balon.get("regate", 60) +
                jugador_con_balon.get("agilidad", 60) +
                jugador_con_balon.get("velocidad", 60)
            ) / 3.0

            # Defensor: Fuerza física + Agresividad + Anticipación
            attr_defensa_fisica = (
                defensor_marcador.get("fuerza_fisica", 60) +
                defensor_marcador.get("agresividad", 60) +
                defensor_marcador.get("anticipacion", 60)
            ) / 3.0

            # Bono de formación defensiva (4-4-2 intercepta mejor en zona propia), mismo
            # criterio que en la rama de pase.
            if zona_balon == "defensa" and tactica_por_equipo[equipo_defensor["nombre"]] == "4-4-2":
                attr_defensa_fisica += BONUS_FORMACION_INTERCEPCION_4_4_2

            # Base bajada de 0.60 a 0.54: el éxito de gambeta era más alto que el ~45-50% real,
            # contribuía a llegar a zona de ataque con más facilidad de la debida.
            exito = resolver_duelo(0.54, attr_regateador, attr_defensa_fisica)
            segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_TRANSICION)

            if exito:
                stats_jugadores[jugador_con_balon["id"]]["regates_exitosos"] += 1
                if zona_balon == "medio":
                    zona_balon = "ataque"
                if random.random() < 0.25:
                    eventos_visibles.append(construir_evento(
                        segundos_acumulados, equipo_con_balon["nombre"], "⚡ REGATE DESTACADO",
                        f"¡Gran maniobra individual de {jugador_con_balon['nombre']} dejando atrás a la defensa!",
                        [jugador_con_balon["nombre"]], zona_balon
                    ))
            else:
                stats_jugadores[jugador_con_balon["id"]]["pérdidas"] += 1
                stats_jugadores[defensor_marcador["id"]]["recuperaciones"] += 1
                posible_asistente = None

                # Calibrado empíricamente -- ver diagnostico_tarjetas.py -- mismo motivo que
                # 'prob_falta' en la rama de pase fallido.
                prob_falta_regate = max(0.07, min(0.42, 0.24 + mod_faltas))
                if random.random() < prob_falta_regate:
                    stats_jugadores[defensor_marcador["id"]]["faltas"] += 1
                    # Mismo caso que en la rama de "pase fallido": 'jugador_con_balon' todavía
                    # es el atacante derribado -- la reasignación pasa más abajo.
                    stats_jugadores[jugador_con_balon["id"]]["faltas_recibidas"] += 1

                    eventos_visibles.append(construir_evento(
                        segundos_acumulados, equipo_defensor["nombre"], "🔥 PRESIÓN DEFENSIVA",
                        random.choice(FRASES_PRESION_FALTA_REGATE).format(
                            defensor=defensor_marcador["nombre"], atacante=jugador_con_balon["nombre"]
                        ),
                        [defensor_marcador["nombre"], jugador_con_balon["nombre"]], zona_balon, es_preparacion=True
                    ))
                    segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_FALTA)

                    if random.random() < 0.11:
                        stats_jugadores[defensor_marcador["id"]]["amarillas"] += 1

                        # ⚠️ CORRECCIÓN: VALIDAR DOBLE AMARILLA EN REGATES
                        if stats_jugadores[defensor_marcador["id"]]["amarillas"] >= 2:
                            procesar_expulsion(defensor_marcador, equipo_defensor, stats_jugadores, eventos_visibles, segundos_acumulados, zona_balon, es_doble_amarilla=True)
                            segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_VAR_ROJA_PENAL)
                        else:
                            eventos_visibles.append(construir_evento(
                                segundos_acumulados, equipo_defensor["nombre"], "🟨 TARJETA AMARILLA",
                                f"Tarjeta amarilla para {defensor_marcador['nombre']} por derribar a {jugador_con_balon['nombre']}.",
                                [defensor_marcador["nombre"], jugador_con_balon["nombre"]], zona_balon
                            ))
                    else:
                        eventos_visibles.append(construir_evento(
                            segundos_acumulados, equipo_defensor["nombre"], "🛑 FALTA",
                            f"Falta de {defensor_marcador['nombre']} al intentar frenar a {jugador_con_balon['nombre']}.",
                            [defensor_marcador["nombre"], jugador_con_balon["nombre"]], zona_balon
                        ))

                    # Mismo caso que en la rama de "pase fallido": posibilidad de tiro libre
                    # directo si la falta fue en el tercio de ataque. Esta rama NO reasigna
                    # 'zona_balon' en el hand-off normal de más abajo, así que acá todavía vale
                    # el 'zona_balon' del momento de la falta.
                    if zona_balon == "ataque" and random.random() < PROB_TIRO_LIBRE_PELIGROSO:
                        resultado_tl, _, segundos_acumulados = ejecutar_tiro_libre(
                            equipo_con_balon, defensor_marcador, portero_rival, equipo_defensor,
                            stats_jugadores, eventos_visibles, segundos_acumulados, mod_precision
                        )
                        if resultado_tl == "gol":
                            if equipo_con_balon == equipo_local:
                                goles_local += 1
                            else:
                                goles_visitante += 1
                            equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                            medios = [j for j in equipo_con_balon["plantilla"] if j.get("linea_partido") == 3]
                            jugador_con_balon = random.choice(medios if medios else equipo_con_balon["plantilla"])
                            zona_balon = "medio"
                        else:
                            equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                            jugador_con_balon = portero_rival
                            zona_balon = "defensa"
                        posible_asistente = None
                        _intentar_sustitucion()
                        continue

                    # Mismo criterio que en la rama de "pase fallido": si no hubo tiro libre
                    # directo, el equipo ATACANTE (el que sufrió la falta) conserva la pelota y
                    # reanuda con un tiro libre indirecto/rápido -- no es un cambio de posesión.
                    _intentar_sustitucion()
                    continue

                else:
                    # Turnover "silencioso" tras un regate fallido sin falta -- a diferencia de
                    # la rama de pase, acá no existe ningún sub-caso con evento propio: el 100%
                    # de estos casos caía sin narración antes de este cambio.
                    eventos_visibles.append(construir_evento(
                        segundos_acumulados, equipo_defensor["nombre"], "⚡ EN TRANSICIÓN",
                        random.choice(FRASES_TRANSICION_REGATE).format(
                            defensor=defensor_marcador["nombre"], atacante=jugador_con_balon["nombre"],
                            equipo=equipo_defensor["nombre"]
                        ),
                        [defensor_marcador["nombre"], jugador_con_balon["nombre"]], zona_balon, es_preparacion=True
                    ))

                equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                # Mismo caso que en la rama de "pase fallido": si 'defensor_marcador' fue
                # expulsado (doble amarilla), ya no está en el campo -- la posesión pasa a un
                # compañero suyo en vez de a él.
                if stats_jugadores[defensor_marcador["id"]].get("expulsado"):
                    jugador_con_balon = random.choice(equipo_con_balon["plantilla"]) if equipo_con_balon["plantilla"] else defensor_marcador
                else:
                    jugador_con_balon = defensor_marcador

        # --- ACCIÓN: TIRO ---
        elif accion == "tiro":
            # Build-up de expectativa: se dispara ANTES de resolver el duelo, así que no
            # spoilea el desenlace (gol/atajada/desviado/córner) -- mismo criterio de asistencia
            # que usa el gol real más abajo (posible_asistente distinto del rematador).
            if posible_asistente and posible_asistente["id"] != jugador_con_balon["id"]:
                descripcion_prep = random.choice(FRASES_PREPARACION_ASISTIDA).format(
                    asistente=posible_asistente["nombre"], atacante=jugador_con_balon["nombre"]
                )
                jugadores_prep = [posible_asistente["nombre"], jugador_con_balon["nombre"]]
            else:
                descripcion_prep = random.choice(FRASES_PREPARACION_SOLO).format(atacante=jugador_con_balon["nombre"])
                jugadores_prep = [jugador_con_balon["nombre"]]
            eventos_visibles.append(construir_evento(
                segundos_acumulados, equipo_con_balon["nombre"], "⏳ PREPARACIÓN", descripcion_prep, jugadores_prep, zona_balon, es_preparacion=True
            ))
            segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_ATAQUE_REMATE)

            # 1. ¿Logra sacar un remate cómodo? (Precisión + Juego Aéreo)
            attr_remate = (
                jugador_con_balon.get("precision_tiro", 60) + bonus_pie_habil(jugador_con_balon)
                + jugador_con_balon.get("juego_aereo", 60)
            ) / 2.0
            attr_remate = max(0.0, attr_remate * (1 + mod_precision))
            attr_marca_defensa = (defensor_marcador.get("anticipacion", 60) + defensor_marcador.get("fuerza_fisica", 60)) / 2.0

            # Base bajada de 0.50 a 0.44 como margen extra (el ajuste principal de volumen de
            # marcadores está en los pesos de acción de la zona de ataque, más arriba).
            va_a_puerta = resolver_duelo(0.44, attr_remate, attr_marca_defensa)

            if va_a_puerta:
                stats_jugadores[jugador_con_balon["id"]]["tiros_puerta"] += 1

                # 2. Duelo Delantero vs Portero
                potencia_remate = (
                    jugador_con_balon.get("fuerza_disparo", 60)
                    + jugador_con_balon.get("precision_tiro", 60) + bonus_pie_habil(jugador_con_balon)
                ) / 2.0
                potencia_remate = max(0.0, potencia_remate * (1 + mod_precision))

                reflejos_portero = (
                    portero_rival.get("rendimiento", 60) +
                    portero_rival.get("agilidad", 60) +
                    portero_rival.get("concentracion", 60)
                ) / 3.0

                # Base bajada de 0.37 a 0.32: la conversión por intento ya estaba cerca de lo
                # real (~18% medido con atributos promedio), esta reducción es solo margen extra.
                gol = resolver_duelo(0.32, potencia_remate, reflejos_portero)

                if gol:
                    # --- INTERVENCIÓN DEL VAR (5% de prob de revisión) ---
                    if hay_revision_var():
                        gol_anulado = random.choice([True, False])
                        segundos_acumulados += _costo_segundos(RANGO_SEGUNDOS_VAR_ROJA_PENAL)
                        if gol_anulado:
                            eventos_visibles.append(construir_evento(
                                segundos_acumulados, "VAR", "🖥️ VAR - GOL ANULADO",
                                f"El VAR revisa la jugada y {arbitros['central']} anula el gol de {jugador_con_balon['nombre']} por mano previa.",
                                [jugador_con_balon["nombre"]], zona_balon
                            ))
                            equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                            jugador_con_balon = portero_rival
                            zona_balon = "defensa"
                            posible_asistente = None
                            _intentar_sustitucion()
                            continue

                    stats_jugadores[jugador_con_balon["id"]]["goles"] += 1
                    stats_jugadores[portero_rival["id"]]["goles_encajados"] += 1

                    if equipo_con_balon == equipo_local:
                        goles_local += 1
                    else:
                        goles_visitante += 1

                    # Atribuir la asistencia al último pase de campo recibido por el goleador,
                    # siempre que no se la esté asistiendo a sí mismo (ej. tras un regate propio).
                    asistente = None
                    if posible_asistente and posible_asistente["id"] != jugador_con_balon["id"]:
                        asistente = posible_asistente
                        stats_jugadores[asistente["id"]]["asistencias"] += 1

                    descripcion_gol = f"¡Golazo de {jugador_con_balon['nombre']}! Remate imparable para {portero_rival['nombre']}."
                    if asistente:
                        descripcion_gol += f" Asistencia de {asistente['nombre']}."

                    eventos_visibles.append(construir_evento(
                        segundos_acumulados, equipo_con_balon["nombre"], "⚽ GOL", descripcion_gol,
                        [jugador_con_balon["nombre"], portero_rival["nombre"]] + ([asistente["nombre"]] if asistente else []),
                        zona_balon
                    ))

                    equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                    medios = [j for j in equipo_con_balon["plantilla"] if j.get("linea_partido") == 3]
                    jugador_con_balon = random.choice(medios if medios else equipo_con_balon["plantilla"])
                    zona_balon = "medio"
                    posible_asistente = None

                else:
                    # Un tiro a puerta puede terminar en atajada limpia o desvío a tiro de esquina
                    if random.random() < 0.65:
                        stats_jugadores[portero_rival["id"]]["atajadas"] += 1
                        eventos_visibles.append(construir_evento(
                            segundos_acumulados, equipo_defensor["nombre"], "🧤 ATAJADA ESPECTACULAR",
                            f"¡Disparo peligroso! {portero_rival['nombre']} se luce con una atajada salvadora.",
                            [portero_rival["nombre"]], zona_balon
                        ))
                        equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                        jugador_con_balon = portero_rival
                        zona_balon = "defensa"
                        posible_asistente = None
                    else:
                        stats_jugadores[portero_rival["id"]]["desvios"] += 1
                        eventos_visibles.append(construir_evento(
                            segundos_acumulados, equipo_defensor["nombre"], "🖐️ DESVÍO A CÓRNER",
                            f"¡Remate potente! {portero_rival['nombre']} mete las manos y envía el balón al tiro de esquina.",
                            [portero_rival["nombre"]], zona_balon
                        ))
                        # A diferencia de una atajada limpia, acá el equipo atacante CONSERVA
                        # la pelota (el córner es suyo) -- no hay swap de posesión todavía, se
                        # resuelve dentro de ejecutar_corner.
                        resultado_corner, _, segundos_acumulados = ejecutar_corner(
                            equipo_con_balon, equipo_defensor, portero_rival,
                            stats_jugadores, eventos_visibles, segundos_acumulados
                        )
                        if resultado_corner == "gol":
                            if equipo_con_balon == equipo_local:
                                goles_local += 1
                            else:
                                goles_visitante += 1
                            equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                            medios = [j for j in equipo_con_balon["plantilla"] if j.get("linea_partido") == 3]
                            jugador_con_balon = random.choice(medios if medios else equipo_con_balon["plantilla"])
                            zona_balon = "medio"
                        else:
                            equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                            jugador_con_balon = portero_rival
                            zona_balon = "defensa"
                        posible_asistente = None
                        _intentar_sustitucion()
                        continue

            else:
                stats_jugadores[jugador_con_balon["id"]]["tiros_desviados"] += 1
                eventos_visibles.append(construir_evento(
                    segundos_acumulados, equipo_con_balon["nombre"], "🎯 DISPARO DESVIADO",
                    f"Remate peligroso de {jugador_con_balon['nombre']} que pasa muy cerca del poste.",
                    [jugador_con_balon["nombre"]], zona_balon
                ))
                equipo_con_balon, equipo_defensor = equipo_defensor, equipo_con_balon
                jugador_con_balon = portero_rival
                zona_balon = "defensa"
                posible_asistente = None

        _intentar_sustitucion()

        # ---------------------------------------------------------------------
        # EVALUACIÓN DE TIEMPO EXTRA (30 Minutos Reglamentarios: 90' al 120')
        # ---------------------------------------------------------------------
        if segundos_acumulados >= DURACION_TIEMPO_REGLAMENTARIO and duracion_objetivo == DURACION_TIEMPO_REGLAMENTARIO:
            if tiempo_extra and hay_empate_global():
                duracion_objetivo = DURACION_TIEMPO_EXTRA  # Extendemos el simulador a 120 minutos
                max_cambios = 6  # Habilitar sexto cambio para la prórroga
                if marcador_ida:
                    desc_tiempo_extra = (
                        f"¡Marcador global {goles_local + goles_ida_local}-{goles_visitante + goles_ida_visita} "
                        f"(ida {goles_ida_local}-{goles_ida_visita})! Nos vamos a 30 minutos de tiempo extra."
                    )
                else:
                    desc_tiempo_extra = f"¡Empate a {goles_local}! Nos vamos a 30 minutos de tiempo extra."
                eventos_visibles.append(construir_evento(
                    DURACION_TIEMPO_REGLAMENTARIO, "Árbitro", "⏱️ TIEMPO EXTRA", desc_tiempo_extra, [], zona_balon
                ))
            else:
                break  # Si no hay tiempo extra habilitado o el marcador global no está empatado, finaliza el bucle

    # Evento de fin del tiempo reglamentario / extra
    segundos_final = DURACION_TIEMPO_EXTRA if (tiempo_extra and duracion_objetivo == DURACION_TIEMPO_EXTRA) else DURACION_TIEMPO_REGLAMENTARIO
    if marcador_ida:
        descripcion_final = (
            f"¡Final del partido de vuelta! {equipo_local['nombre']} {goles_local} - {goles_visitante} {equipo_visitante['nombre']}. "
            f"Marcador global (ida {goles_ida_local}-{goles_ida_visita}): {goles_local + goles_ida_local} - {goles_visitante + goles_ida_visita}."
        )
    else:
        descripcion_final = f"¡Final del partido! {equipo_local['nombre']} {goles_local} - {goles_visitante} {equipo_visitante['nombre']}."
    eventos_visibles.append(construir_evento(
        segundos_final, "Árbitro", "🏁 PITIDO FINAL", descripcion_final, [], zona_balon
    ))

    # -------------------------------------------------------------------------
    # EVALUACIÓN DE TANDA DE PENALTIS
    # -------------------------------------------------------------------------
    penaltis_local = None
    penaltis_visitante = None

    if tiempo_extra and hay_empate_global():
        penaltis_local, penaltis_visitante = simular_tanda_penaltis(
            equipo_local, equipo_visitante,
            portero_local, portero_visitante,
            stats_jugadores, eventos_visibles, segundos_final, arbitros
        )

    # Cálculo de métricas avanzadas del partido
    metricas_partido = calcular_metricas_equipo(stats_jugadores, goles_local, goles_visitante)

    # Cálculo final de calificaciones (Ratings)
    for stat in stats_jugadores.values():
        stat["rating"] = calcular_rating_partido(stat)

    resultado = {
        "local": equipo_local['nombre'],
        "visitante": equipo_visitante['nombre'],
        "id_local": id_local,
        "id_visitante": id_visitante,
        "goles_local": goles_local,
        "goles_visitante": goles_visitante,
        "penaltis_local": penaltis_local,
        "penaltis_visitante": penaltis_visitante,
        "arbitros": arbitros,
        "opinion": None,
        "estadisticas": metricas_partido,
        "eventos": eventos_visibles,
        "tactica_local": tactica_elegida_local,
        "tactica_visita": tactica_elegida_visita,
        "marcador_ida": marcador_ida,
        "marcador_global_local": goles_local + goles_ida_local,
        "marcador_global_visita": goles_visitante + goles_ida_visita,
        "titulares_local": nombres_titulares_local,
        "titulares_visitante": nombres_titulares_visitante
    }

    # Generar la opinión periodística final
    resultado["opinion"] = generar_opinion_partido(resultado, stats_jugadores)

    # NOTA: la actualización de 'jugadores' (goles/asistencias/atajadas/rendimiento, etc.)
    # se hace desde routes/simular_route.py, DESPUÉS de confirmar que 'registrar_resultado_juego'
    # dejó el partido marcado como 'finalizado'. Antes se hacía acá mismo, lo que significaba
    # que si el flujo fallaba justo después de simular (antes de persistir el resultado del
    # partido), las estadísticas de los jugadores ya habían quedado incrementadas para un
    # partido que seguía figurando como "creado" -- un reintento volvía a simularlo y
    # duplicaba goles/asistencias/tarjetas/juegos_jugados de todos los que participaron.
    return resultado, stats_jugadores
