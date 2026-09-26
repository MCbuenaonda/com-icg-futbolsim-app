import certifi
import random
from fastapi import HTTPException, status
from typing import Any, Dict, List, Optional
from google.api_core.exceptions import GoogleAPIError
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

def get_jugadores(id_pais, logger):
    try:
        collection = db['jugadores']
        # Ejecutar la consulta
        jugadores = list(collection.find({"pais_id": int(id_pais)}))

        # Catálogo de posiciones cargado una sola vez (en vez de un find_one por jugador)
        posiciones = {p["id"]: p["nombre"] for p in db['posiciones'].find({})}

        for jugador in jugadores:
            jugador['posicion'] = posiciones.get(int(jugador['posicion_id']))

        return jugadores
    except GoogleAPIError as e:
        logger.error(f"Error de MongoBD: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error de MongoBD: {str(e)}")
    except Exception as e:
        logger.error(f"Error al obtener los jugadores: {str(e)}")
        raise HTTPException(status_code=409, detail=f"Error al obtener los jugadores: {str(e)}")

def get_jugador(id_jugador, logger):
    try:        
        collection = db['jugadores']
        # Ejecutar la consulta
        jugador = collection.find_one({"id": int(id_jugador)})
        return jugador
    except GoogleAPIError as e:
        logger.error(f"Error de MongoBD: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error de MongoBD: {str(e)}")
    except Exception as e:
        logger.error(f"Error al obtener el jugador: {str(e)}")
        raise HTTPException(status_code=409, detail=f"Error al obtener el jugador: {str(e)}")


# ==========================================
# Estado de ánimo del jugador (post-partido)
# ==========================================
ESTADOS_ANIMO = ["Concentrado", "Motivado", "Eufórico", "Frustrado", "Nervioso", "Decepcionado", "Insatisfecho"]
ESTADO_ANIMO_DEFAULT = "Concentrado"

# Diferencia de goles a partir de la cual el resultado se considera "goleada" para el ánimo
# (mismo criterio conceptual que fanbase_service.DIFERENCIA_GOLES_GOLEADA, pero deliberadamente
# independiente -- son dos sistemas distintos, no hace falta que compartan la constante).
DIFERENCIA_GOLEADA_ANIMO = 3
UMBRAL_RATING_ALTO_ANIMO = 8.0
UMBRAL_RATING_BAJO_ANIMO = 5.0


def calcular_estado_animo_jugador(stats: dict, goles_favor_equipo: int, goles_contra_equipo: int) -> str:
    """
    Determina el 'estado_animo' de un jugador a partir de su propio desempeño (rating, goles,
    asistencias, tarjetas, errores) y el resultado de SU equipo en el partido. Es una función
    PURA (sin acceso a Mongo) a propósito: se llama dos veces por partido -- una antes de
    registrar el resultado (para armar el texto narrativo / comentarios del post, ver
    juegos_service.generar_comentarios_jugadores) y otra dentro de
    actualizar_jugadores_post_partido (para persistir el campo en 'jugadores') -- al ser pura y
    determinística, ambas llamadas dan el mismo resultado sin duplicar lógica de negocio ni
    necesitar pasar el valor ya calculado de un lado a otro del flujo.

    No usa "penal fallado" como señal propia porque el motor de simulación
    (services/simular_service.py::ejecutar_penal) no guarda un contador dedicado de penales
    fallados por jugador en 'stats_jugadores' -- solo queda registrado como texto libre en el
    evento visible, y este proyecto evita parsear texto para calcular datos (ver notas en
    estadisticas_service.py sobre bugs pasados por ese mismo motivo).
    """
    goles = stats.get("goles", 0)
    asistencias = stats.get("asistencias", 0)
    rating = stats.get("rating", 6.0)
    rojas = stats.get("rojas", 0)
    amarillas = stats.get("amarillas", 0)
    errores_graves = stats.get("errores_graves", 0)

    diferencia = goles_favor_equipo - goles_contra_equipo
    gano = diferencia > 0
    empato = diferencia == 0
    goleada_favor = gano and diferencia >= DIFERENCIA_GOLEADA_ANIMO
    goleada_contra = (not gano and not empato) and abs(diferencia) >= DIFERENCIA_GOLEADA_ANIMO

    # Una expulsión pesa más que cualquier otra cosa: frustra sin importar el resultado del equipo.
    if rojas > 0:
        return "Frustrado"

    if gano:
        if goleada_favor or (goles > 0 and rating >= UMBRAL_RATING_ALTO_ANIMO):
            return "Eufórico"
        if goles > 0 or asistencias > 0 or rating >= UMBRAL_RATING_ALTO_ANIMO:
            return "Motivado"
        return "Concentrado"

    if empato:
        if errores_graves > 0 or amarillas > 0:
            return "Insatisfecho"
        if goles > 0 or asistencias > 0:
            return "Motivado"
        return "Nervioso" if rating < UMBRAL_RATING_BAJO_ANIMO else "Concentrado"

    # Derrota
    if goleada_contra:
        return "Decepcionado"
    if errores_graves > 0:
        return "Frustrado"
    if rating >= UMBRAL_RATING_ALTO_ANIMO or goles > 0:
        return "Insatisfecho"  # jugó bien, pero el equipo perdió igual
    return "Nervioso" if rating >= UMBRAL_RATING_BAJO_ANIMO else "Decepcionado"


# Atributos clave por SECTOR real de la posición (ver colección 'posiciones': 'sector' es uno de
# "Portero"/"Defensa"/"Medio"/"Delantero" para cada una de las 11 posiciones granulares -- ver
# CLAUDE.md). ⚠️ Antes esto estaba indexado 1-4 y se le pasaba directo 'jugadores.posicion_id',
# que es el esquema GRANULAR (1-11), no el simplificado -- por pura coincidencia numérica solo
# Portero (id 1) y Defensa izquierdo (id 2) caían en el bucket correcto; Defensa derecho (id 3)
# quedaba tratado como mediocampista, Lateral izquierdo (id 4) como delantero, y las otras 7
# posiciones (id 5-11: Lateral derecho, los 3 mediocampistas, los 3 delanteros) no caían en
# ningún bucket. Ahora se resuelve el sector real vía la colección 'posiciones' antes de indexar.
ATRIBUTOS_CLAVE_POR_SECTOR = {
    "Portero": ["agilidad", "anticipacion", "compostura", "concentracion", "forma_actual", "moral"],
    "Defensa": ["agresividad", "anticipacion", "compostura", "fuerza_fisica", "juego_aereo", "resistencia"],
    "Medio": ["control_balon", "precision_pase", "vision_juego", "resistencia", "agilidad", "velocidad"],
    "Delantero": ["precision_tiro", "fuerza_disparo", "regate", "velocidad", "compostura", "agilidad"]
}

# Cuánto de 'delta_base' (el crecimiento/decremento genérico ligado al rating del partido, ver
# actualizar_jugadores_post_partido) se aplica a un atributo que NO es favorito del sector del
# jugador -- sigue habiendo algo de desarrollo atlético general, pero mucho más chico que en sus
# atributos de verdad relevantes.
FACTOR_ATRIBUTO_NO_FAVORITO = 0.35

# Peso extra que se le da a los atributos favoritos del sector al recalcular el overall -- antes
# era un promedio plano de los 17 atributos sin distinguir posición.
PESO_ATRIBUTO_FAVORITO = 2.5


def _multiplicador_edad(edad: Optional[int], delta: float) -> float:
    """
    Los jugadores jóvenes desarrollan más rápido (y son más resilientes a un mal partido); los
    veteranos casi no mejoran y declinan más rápido -- ver 'edad' en 'jugadores' (rasgo
    permanente asignado una sola vez por asignar_edad_jugadores.py, no una edad cronológica que
    avance con los mundiales). Solo se aplica a 'delta_base' (la parte genérica ligada al
    rating), nunca a los bonos/penalizaciones de acciones concretas (goles, atajadas, tarjetas,
    etc.) -- esas ya son mérito real de lo que hizo el jugador ESE partido, sin importar la edad.
    Neutro (1.0) si el jugador todavía no tiene 'edad' asignada.
    """
    if edad is None or delta == 0:
        return 1.0
    if delta > 0:
        if edad <= 20: return 1.3
        if edad <= 28: return 1.0
        if edad <= 32: return 0.7
        return 0.4
    if edad <= 20: return 0.7
    if edad <= 28: return 1.0
    if edad <= 32: return 1.15
    return 1.4


def recalcular_overall(atributos_actualizados: dict, sector: str) -> float:
    """
    Recalcula el overall del jugador ponderando más los atributos favoritos de su sector (ver
    ATRIBUTOS_CLAVE_POR_SECTOR/PESO_ATRIBUTO_FAVORITO) en vez de un promedio plano de los 17 --
    antes el overall de un arquero se diluía con sus stats de tiro/regate, que nunca usa.
    """
    atributos_clave = [
        "agilidad", "agresividad", "anticipacion", "compostura", "concentracion",
        "control_balon", "forma_actual", "fuerza_disparo", "fuerza_fisica",
        "juego_aereo", "moral", "precision_pase", "precision_tiro",
        "regate", "resistencia", "velocidad", "vision_juego"
    ]
    favoritos = ATRIBUTOS_CLAVE_POR_SECTOR.get(sector, [])

    suma = 0.0
    peso_total = 0.0
    for attr in atributos_clave:
        peso = PESO_ATRIBUTO_FAVORITO if attr in favoritos else 1.0
        suma += atributos_actualizados.get(attr, 60.0) * peso
        peso_total += peso
    return round(suma / peso_total, 1)

# función para actualizar los atributos de los jugadores tras un partido
def actualizar_jugadores_post_partido(stats_jugadores: dict, goles_local: int = 0, goles_visitante: int = 0) -> Dict[int, str]:
    """
    Actualiza la BD MongoDB tras finalizar el encuentro con variaciones dinámicas por atributo,
    y recalcula el 'estado_animo' de cada jugador (ver calcular_estado_animo_jugador) según su
    desempeño individual y el resultado de su equipo.

    :return: {jugador_id: nuevo_estado_animo} -- aunque el estado de ánimo ya se calcula (y se
        puede recalcular igual, es una función pura) antes de este punto para armar el post del
        partido (ver routes/simular_route.py), se devuelve por si algún caller solo necesita
        persistir sin tener que recalcular él mismo.
    """
    collection = db['jugadores']
    estados_animo: Dict[int, str] = {}

    # Sector real (Portero/Defensa/Medio/Delantero) por posición granular -- una sola consulta,
    # no una por jugador (mismo criterio que ya usa
    # live_match_service.obtener_posiciones_plantillas_en_vivo para su mapa de siglas).
    sector_por_posicion_id = {
        p["id"]: p.get("sector") for p in db["posiciones"].find({}, {"id": 1, "sector": 1})
    }

    atributos_habilidad = [
        "agilidad", "agresividad", "anticipacion", "compostura", "concentracion",
        "control_balon", "forma_actual", "fuerza_disparo", "fuerza_fisica",
        "juego_aereo", "moral", "precision_pase", "precision_tiro",
        "regate", "resistencia", "velocidad", "vision_juego"
    ]

    for j_id, stats in stats_jugadores.items():
        jugador_db = collection.find_one({"id": j_id})
        if not jugador_db:
            continue

        rating = stats.get("rating", 6.0)
        sector = sector_por_posicion_id.get(jugador_db.get("posicion_id"), "Medio")
        atributos_favoritos = ATRIBUTOS_CLAVE_POR_SECTOR.get(sector, [])
        edad = jugador_db.get("edad")

        # Rango base de cambio según la actuación (Rating)
        if rating >= 8.5:
            delta_base = 0.4
        elif rating >= 7.0:
            delta_base = 0.2
        elif rating >= 5.5:
            delta_base = 0.0
        elif rating >= 4.0:
            delta_base = -0.2
        else:
            delta_base = -0.4

        # 2. Mapeo de impacto por acciones específicas del partido
        bonos_acciones = {}
        
        # --- Hitos positivos ---
        goles = stats.get("goles", 0)
        if goles > 0:
            bonos_acciones["precision_tiro"] = bonos_acciones.get("precision_tiro", 0) + (goles * 0.3)
            bonos_acciones["compostura"] = bonos_acciones.get("compostura", 0) + (goles * 0.2)
            bonos_acciones["moral"] = bonos_acciones.get("moral", 0) + (goles * 0.5)

        asistencias = stats.get("asistencias", 0)
        if asistencias > 0:
            bonos_acciones["vision_juego"] = bonos_acciones.get("vision_juego", 0) + (asistencias * 0.3)
            bonos_acciones["precision_pase"] = bonos_acciones.get("precision_pase", 0) + (asistencias * 0.2)
            bonos_acciones["moral"] = bonos_acciones.get("moral", 0) + (asistencias * 0.3)

        regates = stats.get("regates_exitosos", 0)
        if regates >= 3:
            bonos_acciones["regate"] = bonos_acciones.get("regate", 0) + 0.3
            bonos_acciones["agilidad"] = bonos_acciones.get("agilidad", 0) + 0.2

        pases = stats.get("pases_completados", 0)
        if pases >= 20:
            bonos_acciones["precision_pase"] = bonos_acciones.get("precision_pase", 0) + 0.3
            bonos_acciones["vision_juego"] = bonos_acciones.get("vision_juego", 0) + 0.2

        atajadas = stats.get("atajadas", 0)
        if atajadas > 0 and sector == "Portero":
            bonos_acciones["anticipacion"] = bonos_acciones.get("anticipacion", 0) + (atajadas * 0.15)
            bonos_acciones["concentracion"] = bonos_acciones.get("concentracion", 0) + (atajadas * 0.1)

        # --- Penalizaciones por errores directos ---
        errores_graves = stats.get("errores_graves", 0)
        if errores_graves > 0:
            bonos_acciones["compostura"] = bonos_acciones.get("compostura", 0) - (errores_graves * 0.4)
            bonos_acciones["concentracion"] = bonos_acciones.get("concentracion", 0) - (errores_graves * 0.4)
            bonos_acciones["moral"] = bonos_acciones.get("moral", 0) - (errores_graves * 0.5)

        rojas = stats.get("rojas", 0)
        if rojas > 0:
            bonos_acciones["agresividad"] = bonos_acciones.get("agresividad", 0) + 0.3 # Sube agresividad negativa
            bonos_acciones["moral"] = bonos_acciones.get("moral", 0) - 0.8

        goles_encajados = stats.get("goles_encajados", 0)
        if goles_encajados >= 3 and sector in ("Portero", "Defensa"):
            bonos_acciones["moral"] = bonos_acciones.get("moral", 0) - 0.4
            bonos_acciones["compostura"] = bonos_acciones.get("compostura", 0) - 0.2
                
        nuevos_atributos = {}

        for attr in atributos_habilidad:
            val_actual = float(jugador_db.get(attr, 60.0))

            # Crecimiento genérico ligado al rating: completo si el atributo es favorito del
            # sector del jugador, reducido si no (ver FACTOR_ATRIBUTO_NO_FAVORITO) -- y escalado
            # por edad (jóvenes desarrollan más rápido y resisten mejor un mal partido, veteranos
            # casi no mejoran y declinan más rápido, ver _multiplicador_edad).
            delta_base_attr = delta_base if attr in atributos_favoritos else delta_base * FACTOR_ATRIBUTO_NO_FAVORITO
            delta_base_attr *= _multiplicador_edad(edad, delta_base_attr)

            # Modificador por acciones concretas -- NO se escala por posición ni por edad: ya es
            # mérito real de lo que hizo el jugador ese partido (goles, asistencias, atajadas,
            # tarjetas, etc.), se acredita completo sin importar su rol o su edad.
            impacto_accion = bonos_acciones.get(attr, 0.0)

            # Pequeña variación aleatoria (-0.1, 0.0, 0.1)
            ruido = random.choice([-0.1, 0.0, 0.1])

            delta_final = delta_base_attr + impacto_accion + ruido
            
            # Aplicar límites estándar (min 1%, max 99%)
            nuevo_val = max(1.0, min(99.0, val_actual + delta_final))
            nuevos_atributos[attr] = round(nuevo_val, 1)

        # Rendimiento como promedio acumulado de toda la carrera (no el rating de un solo
        # partido): antes se pisaba 'rendimiento' con 'rating * 10' en cada partido, perdiendo
        # todo el historial -- esto rompía tanto el "Balón de Oro" (que ordena por
        # 'rendimiento' buscando consistencia, ver jugadores_service.obtener_destacados_torneo)
        # como el propio motor de simulación, que usa 'rendimiento' como atributo de habilidad
        # de porteros/delanteros (ver simular_service.py) y no debería saltar ±40 puntos de un
        # partido a otro como el resto de los atributos, que evolucionan gradualmente.
        juegos_jugados_previos = jugador_db.get("juegos_jugados", 0)
        rendimiento_previo = jugador_db.get("rendimiento", 60.0)
        rendimiento_partido = round(rating * 10, 1)
        nuevos_atributos["rendimiento"] = round(
            ((rendimiento_previo * juegos_jugados_previos) + rendimiento_partido) / (juegos_jugados_previos + 1), 1
        )

        # Recalcular el OVERALL general (ponderado por sector, ver recalcular_overall)
        nuevos_atributos["overall"] = recalcular_overall(nuevos_atributos, sector)

        # Estado de ánimo según el propio desempeño y el resultado de SU equipo (lado L/V)
        lado = stats.get("lado", "L")
        goles_favor_equipo = goles_local if lado == "L" else goles_visitante
        goles_contra_equipo = goles_visitante if lado == "L" else goles_local
        nuevo_estado_animo = calcular_estado_animo_jugador(stats, goles_favor_equipo, goles_contra_equipo)
        nuevos_atributos["estado_animo"] = nuevo_estado_animo
        estados_animo[j_id] = nuevo_estado_animo

        # Actualización en MongoDB
        collection.update_one(
            {"id": j_id},
            {
                "$inc": {
                    "goles": stats.get("goles", 0),
                    "asistencias": stats.get("asistencias", 0),
                    "atajadas": stats.get("atajadas", 0),
                    "faltas": stats.get("faltas", 0),
                    "amarilla": stats.get("amarillas", 0),
                    "roja": stats.get("rojas", 0),
                    # Disparos totales (a puerta + desviados), para poder calcular la
                    # efectividad de gol por jugador (ver
                    # estadisticas_service._obtener_mejor_efectividad_gol) -- antes se
                    # calculaban por partido en el motor de simulación pero se descartaban acá.
                    "tiros_puerta": stats.get("tiros_puerta", 0),
                    "tiros_desviados": stats.get("tiros_desviados", 0),
                    # Faltas RECIBIDAS (jugador víctima), para "Jugador Más Infringido" (ver
                    # estadisticas_service._get_stats_jugadores) -- distinto de 'faltas', que
                    # cuenta las cometidas por el infractor.
                    "faltas_recibidas": stats.get("faltas_recibidas", 0),
                    # Robos de balón (recuperaciones) y atajadas de penal específicamente
                    # (distinto de 'atajadas', que mezcla juego abierto y penales) -- ambos ya
                    # se calculaban por partido en el motor de simulación pero se descartaban acá.
                    "recuperaciones": stats.get("recuperaciones", 0),
                    "atajadas_penales": stats.get("atajadas_penales", 0),
                    "juegos_jugados": 1
                },
                "$set": nuevos_atributos
            }
        )

    return estados_animo

# funcion para obtener
def obtener_destacados_torneo() -> Dict[str, Optional[Dict[str, Any]]]:
    jugadores_coll = db["jugadores"]

    # 1. Máximo goleador (Bota de Oro)
    # Criterio principal: mayor número de goles.
    # Desempate: menos juegos jugados o mayor rendimiento promedio.
    max_goleador = jugadores_coll.find_one(
        {"goles": {"$gt": 0}},  # Filtrar solo jugadores que hayan anotado
        sort=[("goles", -1), ("juegos_jugados", 1), ("rendimiento", -1)],
    )

    # 2. Mejor desempeño del torneo (Balón de Oro)
    # Criterio principal: mayor rendimiento (o forma_actual / overall)
    # Criterio secundario: mínimo de partidos jugados para evitar sesgos con jugadores de 1 solo partido.
    MIN_JUEGOS = 2

    mejor_desempeno = jugadores_coll.find_one(
        {"juegos_jugados": {"$gte": MIN_JUEGOS}},
        sort=[("rendimiento", -1), ("goles", -1), ("overall", -1)],
    )

    # Fallback si ningún jugador cumple el mínimo de partidos jugados
    if not mejor_desempeno:
        mejor_desempeno = jugadores_coll.find_one(
            {}, sort=[("rendimiento", -1), ("goles", -1)]
        )

    return {"max_goleador": max_goleador, "mejor_desempeno": mejor_desempeno}


def obtener_top_goleadores(limite: int = 10) -> List[Dict[str, Any]]:
    """
    Top N jugadores por goles (Bota de Oro), para el modal de "Goleador del Torneo" en
    templates/home.html. Mismo patrón de resolución en batch de pais_id -> nombre/bandera que ya
    usa estadisticas_service._get_stats_jugadores (un solo find contra 'paises' en vez de N
    lookups sueltos) -- 'jugadores' no tiene un campo 'pais'/'bandera' propio, solo 'pais_id'.
    """
    jugadores_coll = db["jugadores"]
    paises_coll = db["paises"]

    top = list(
        jugadores_coll.find(
            {"goles": {"$gt": 0}},
            {"_id": 0, "nombre": 1, "pais_id": 1, "goles": 1}
        ).sort("goles", -1).limit(limite)
    )

    ids_paises = {j["pais_id"] for j in top if j.get("pais_id") is not None}
    paises_map = {
        p["id"]: p for p in paises_coll.find({"id": {"$in": list(ids_paises)}}, {"id": 1, "nombre": 1, "bandera": 1})
    }
    for jugador in top:
        pais = paises_map.get(jugador.get("pais_id"), {})
        jugador["pais"] = pais.get("nombre", "?")
        jugador["bandera"] = pais.get("bandera", "")

    return top