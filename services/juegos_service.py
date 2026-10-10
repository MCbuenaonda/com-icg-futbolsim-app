import certifi
from markupsafe import Markup, escape
from bson import ObjectId
from bson.errors import InvalidId
from typing import Dict, Any, List, Optional, Tuple
from pymongo.database import Database
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
from pymongo import ASCENDING, DESCENDING
from services.simular_service import simular_partido_realista
from services.paises_service import actualizar_estadisticas_pais, actualizar_poder_y_rankin, recalcular_rankin
from services.fanbase_service import AFICIONADOS_INICIAL, actualizar_aficionados_post_partido
from services.jugadores_service import calcular_estado_animo_jugador, ESTADO_ANIMO_DEFAULT, actualizar_jugadores_post_partido
from services.fecha_service import formatear_fecha_es
from services.quinielas_service import procesar_resultado_partido
from services.ownership_service import procesar_valor_y_dividendos_partido
from services.fantasy_service import procesar_eventos_jugadores_partido, refrescar_cambios_gratis_fase
from services.venue_service import process_match_city_revenue
import random
import logging

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generar_partidos_fase(db: Database, confederacion_id: int, fase_id: int, mundial_id: Any) -> Dict[str, Any]:
    internacional_coll = db["internacional"]
    partidos_coll = db["juegos"]

    # 1. Traer todos los equipos del mundial activo en la Fase
    if fase_id == 1:
        equipos_internacional = list(internacional_coll.find({
            "mundial_id": mundial_id,
            "fase_eliminatoria": fase_id
        }))
    else:
        equipos_internacional = list(internacional_coll.find({
            "mundial_id": mundial_id,
            "confederacion_id": confederacion_id,
            "fase_eliminatoria": fase_id
        }))

    if not equipos_internacional:
        return {"exito": False, "mensaje": "No hay equipos cargados en la colección internacional para este mundial."}

    # 2. Agrupar los equipos por (confederacion_id, grupo)
    grupos_dict = {}
    for eq in equipos_internacional:
        key = (eq["confederacion_id"], eq["grupo"])
        if key not in grupos_dict:
            grupos_dict[key] = []
        grupos_dict[key].append(eq)

    partidos_a_insertar = []

    # 3. Recorrer cada grupo
    for (conf_id, grupo_nombre), equipos in grupos_dict.items():
        total_equipos = len(equipos)

        # Mapear los equipos por su idx_grupo - 1 para rápida consulta O(1)
        # Ejemplo: idx_grupo 1 -> índice 0 en nuestro diccionario
        mapa_posicion = {eq["idx_grupo"] - 1: eq for eq in equipos}

        # Nombre de la colección según el número de equipos (ej: 'fixture_5_equipos' o 'fixture_5')
        # Cambia el nombre según cómo tengas nombradas tus colecciones en Mongo:
        collection = "dos"
        if total_equipos == 3:
            collection = "tres"
        elif total_equipos == 4:
            collection = "cuatro"
        elif total_equipos == 5:
            collection = "cinco"
        elif total_equipos == 6:
            collection = "seis"
        elif total_equipos == 10:
            collection = "diez"

        nombre_coleccion_fixture = f"{collection}_equipos" 
        fixture_coll = db[nombre_coleccion_fixture]

        # Consultar las jornadas ordenadas ascendente
        jornadas_fixture = list(fixture_coll.find({}).sort("jornada_id", 1))

        if not jornadas_fixture:
            raise ValueError(f"No se encontró la plantilla de fixture para {total_equipos} equipos en la colección '{nombre_coleccion_fixture}'.")

        total_jornadas = len(jornadas_fixture)
        mitad_jornadas = total_jornadas // 2
        
        # Si es fase 7 o mayor y la plantilla tiene ida/vuelta, tomar solo la primera mitad de jornadas
        if fase_id >= 7:
            jornadas_fixture = jornadas_fixture[:mitad_jornadas]

        # 4. Procesar cada jornada del fixture
        for jornada_doc in jornadas_fixture:
            jornada_num = jornada_doc["jornada_id"]
            
            # Si es fase 7 o superior (ej. Mundial), siempre es "ida".
            # Si es una fase anterior (ej. eliminatorias previas), se calcula si es ida o vuelta.
            if fase_id >= 7:
                tipo_partido = "ida"
            else:
                tipo_partido = "ida" if jornada_num <= mitad_jornadas else "vuelta"
                        
            # Extraer los campos pos1, pos2, pos3... ordenados
            # Ejemplo: [("pos1", 0), ("pos2", 1), ("pos3", 2), ("pos4", 3)...]
            posiciones = sorted(
                [(k, v) for k, v in jornada_doc.items() if k.startswith("pos") and v is not None],
                key=lambda x: int(x[0].replace("pos", ""))
            )

            # Iterar de 2 en 2 para armar las parejas (pos1 vs pos2, pos3 vs pos4, etc.)
            for i in range(0, len(posiciones), 2):
                # Verificar que exista la pareja completa (para evitar IndexOutOfBounds si hay impar)
                if i + 1 >= len(posiciones):
                    # Si queda una posición suelta, ese equipo descansa esta jornada
                    continue

                idx_local = posiciones[i][1]
                idx_visitante = posiciones[i+1][1]

                # Si el índice mapea a un equipo real (aplica para grupos impares)
                if idx_local in mapa_posicion and idx_visitante in mapa_posicion:
                    pais_local = mapa_posicion[idx_local]
                    pais_visitante = mapa_posicion[idx_visitante]

                    # # Consultar los datos completos del país (ofensiva, defensiva, etc.)
                    # pais_local = internacional_coll.find_one({"id": doc_local["pais_id"]})
                    # pais_visitante = internacional_coll.find_one({"id": doc_visitante["pais_id"]})

                    # Formatear el objeto del equipo según el esquema requerido
                    equipo_local_data = construir_objeto_equipo(pais_local)
                    equipo_visitante_data = construir_objeto_equipo(pais_visitante)

                    # Crear el documento del partido
                    partido = {
                        "mundial_id": mundial_id,
                        "grupo": f"Grupo {grupo_nombre}",
                        "confederacion_id": conf_id,
                        "equipo_local": equipo_local_data,
                        "equipo_visitante": equipo_visitante_data,
                        "tipo": tipo_partido,
                        "estado": "creado",
                        "jornada": f"Jornada {jornada_num}",
                        "tag": f"#{equipo_local_data['siglas']}{equipo_visitante_data['siglas']}",
                        "fase_id": fase_id,
                        "tiempo_extra": False
                    }

                    partidos_a_insertar.append(partido)

    # 5. Guardar masivamente en la colección 'juegos'
    if partidos_a_insertar:
        resultado = partidos_coll.insert_many(partidos_a_insertar)
        total_creados = len(resultado.inserted_ids)
    else:
        total_creados = 0

    return {
        "exito": True,
        "total_partidos_creados": total_creados,
        "mensaje": f"Se han generado e insertado {total_creados} partidos exitosamente."
    }
    
    
def construir_objeto_equipo(pais_doc: dict) -> dict:
    """Helper para armar la estructura exacta del equipo embedded en el partido."""
    if not pais_doc:
        return {}
        
    return {
        "id": pais_doc.get("id"),
        "nombre": pais_doc.get("nombre"),
        "siglas": pais_doc.get("siglas", pais_doc.get("iso", "N/A")),
        "iso": pais_doc.get("iso"),
        "rankin": pais_doc.get("estadisticas", {}).get("rankin", 0),
        "confederacion_id": pais_doc.get("confederacion_id"),
        "bandera": pais_doc.get("bandera"),
        "goles": 0
    }


def obtener_juegos_programados(db: Database, mundial_id: Any = None) -> List[Dict[str, Any]]:    
    juegos_coll = db["juegos"]
    
    query = {"estado": "creado"}
    
    mundial_id = str(mundial_id)
    
    # Si se pasa un mundial_id específico, filtramos por él
    if mundial_id:
        query["mundial_id"] = mundial_id

    # Ordenamiento compuesto: Primero por fecha ASC, luego por hora ASC
    cursor = juegos_coll.find(query).sort([("fecha", 1), ("hora", 1)])
    
    juegos = list(cursor)
    
    # Convertimos el ObjectId a string para evitar problemas de serialización en la plantilla
    for juego in juegos:
        juego["_id"] = str(juego["_id"])
        
    return juegos

# funcion para obtener todos los juegos con fecha asignada (programados y finalizados) para la vista de calendario
def obtener_juegos_calendario(db: Database, mundial_id: Any = None) -> List[Dict[str, Any]]:
    juegos_coll = db["juegos"]

    query = {"fecha": {"$ne": None, "$exists": True}}

    if mundial_id:
        query["mundial_id"] = str(mundial_id)

    cursor = juegos_coll.find(query).sort([("fecha", 1), ("hora", 1)])

    juegos = list(cursor)

    for juego in juegos:
        juego["_id"] = str(juego["_id"])

    return juegos

# funcion para registrar el resultado de un juego
def registrar_resultado_juego(db: Database, juego_id: str, partido: dict, stats_extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    juegos_coll = db["juegos"]
    
    goles_local = partido.get("goles_local", 0)
    goles_visitante = partido.get("goles_visitante", 0)

    # 2. Determinar ganador o empate
    id_local = partido["id_local"]
    id_visita = partido["id_visitante"]

    if goles_local > goles_visitante:
        ganador_id = id_local
        empate = False
    elif goles_visitante > goles_local:
        ganador_id = id_visita
        empate = False
    else:
        ganador_id = None
        empate = True

    # 3. Construir el objeto de resultado
    objeto_resultado = {
        "local": partido['local'],
        "visitante": partido['visitante'],
        "id_local": id_local,
        "id_visitante": id_visita,
        "goles_local": goles_local,
        "goles_visitante": goles_visitante,
        "penaltis_local": partido.get("penaltis_local", 0),
        "penaltis_visitante": partido.get("penaltis_visitante", 0),
        "arbitros": partido.get("arbitros", []),
        "opinion": partido.get("opinion", ""),
        "eventos": partido.get("eventos", []),
        "goleadores": partido.get("goleadores", []),
        "atajadores": partido.get("atajadores", []),
        "participantes": partido.get("participantes", []),
        # Feed estilo X del dashboard (ver templates/home.html): texto narrativo del post y
        # comentarios de jugadores, generados en routes/simular_route.py antes de este llamado
        # (ver juegos_service.generar_texto_narrativo / generar_comentarios_jugadores).
        "texto_narrativo": partido.get("texto_narrativo", ""),
        "comentarios_jugadores": partido.get("comentarios_jugadores", []),
        # 11 inicial por equipo (ver services/simular_service.py) -- usado por la Cancha en Vivo
        # (services/live_match_service.py::obtener_posiciones_plantillas_en_vivo) para saber
        # quién arrancó de titular sin tener que persistir todo 'stats_jugadores'.
        "titulares_local": partido.get("titulares_local", []),
        "titulares_visitante": partido.get("titulares_visitante", []),
        "ganador_id": ganador_id,
        "ganador_lado": "L" if ganador_id == id_local else ("V" if ganador_id == id_visita else "E"),
        "empate": empate        
    }    

    # 4. Actualizar el registro en MongoDB
    update_data = {
        "$set": {
            "estado": "finalizado",
            "equipo_local.goles": goles_local,
            "equipo_local.tactica": partido.get("tactica_local"),
            "equipo_visitante.goles": goles_visitante,
            "equipo_visitante.tactica": partido.get("tactica_visita"),
            "resultado": objeto_resultado,
            "estadisticas": partido.get("estadisticas", {})  # Guardar estadísticas si existen
        }
    }

    resultado_op = juegos_coll.update_one({"_id": ObjectId(juego_id)}, update_data)

    if resultado_op.modified_count > 0:
        return {
            "exito": True,
            "mensaje": "Juego finalizado y registrado correctamente.",
            "resultado": objeto_resultado
        }
    
    return {"exito": False, "mensaje": "No se pudo actualizar el registro del juego."}


def simular_y_registrar_resultado(juego_id: str, id_local: int, id_visita: int, tiempo_extra: bool = False) -> Dict[str, Any]:
    """
    Corre el motor de simulación (simular_partido_realista) y persiste el resultado (estado,
    resultado.*, estadisticas) vía registrar_resultado_juego -- todo lo necesario para que el
    partido quede "jugado" y sus eventos disponibles para la revelación en vivo
    (routes/live_match_route.py). NO aplica los efectos secundarios (jugadores, país,
    aficionados, quinielas, ownership, fantasy, sedes, ranking, avance de fase) -- eso vive en
    aplicar_efectos_secundarios, separado a propósito para que la Simulación en Vivo pueda
    diferir ese bloque hasta que termine la ventana de revelación (ver
    services/live_match_service.py) sin que la tabla de posiciones, los perfiles de jugadores,
    etc. se actualicen antes de tiempo.

    Idempotente: si el partido ya está 'finalizado', no vuelve a simular -- devuelve el doc tal
    cual está guardado (mismo guard que tenía antes routes/simular_route.py:simular()).

    :return: {
        "exito": bool,
        "ya_finalizado": bool,        # True si no hizo falta simular (idempotencia)
        "partido": dict,              # el 'partido' enriquecido (mismo shape que antes)
        "stats_jugadores": Optional[dict],
        "resp_registro": Optional[dict],  # lo que devuelve registrar_resultado_juego
        "juego_doc": Optional[dict],  # doc de 'juegos' pre-simulación (fecha/hora/tag/fase_id/etc.)
    }
    """
    juego, activo = obtener_juego_activo(juego_id)

    if juego["estado"] == "finalizado":
        return {
            "exito": True,
            "ya_finalizado": True,
            "partido": juego,
            "stats_jugadores": None,
            "resp_registro": None,
            "juego_doc": juego,
        }

    print(f"Simulando partido: juego_id={juego_id}")

    # 1. Determinar si se debe forzar tiempo extra por empate en jornada 1 (Grupo de 2 equipos)
    if not tiempo_extra:
        tiempo_extra = evaluar_tiempo_extra_grupo_dos_equipos(db, juego_id, id_local, id_visita)

    # Recuperar el clima ya generado/persistido para este partido (endpoint "/") para que influya en la simulación
    juego_doc = db["juegos"].find_one({"_id": ObjectId(juego_id)})
    clima = juego_doc.get("clima") if juego_doc else None

    # Si es el partido de vuelta de un grupo de 2 equipos, obtener los goles de la ida para
    # que la simulación evalúe tiempo extra/penales por marcador GLOBAL (ida + vuelta)
    marcador_ida = obtener_marcador_ida_grupo_dos_equipos(db, juego_id, id_local, id_visita)

    # El motor de simulación
    partido, stats_jugadores = simular_partido_realista(id_local, id_visita, tiempo_extra, clima=clima, marcador_ida=marcador_ida)

    # Completar la ficha técnica (sede, clima, aforo, fecha/hora/grupo/jornada/tag/tipo) para
    # la vista de resultado -- el dict 'resultado' que devuelve simular_partido_realista solo
    # trae los datos calculados del PARTIDO EN SÍ (goles, eventos, tácticas, etc.), no estos
    # campos de calendario/torneo, que solo existen en 'juegos' (juego_doc).
    if juego_doc:
        partido["ubicacion"] = juego_doc.get("ubicacion")
        partido["aforo"] = juego_doc.get("aforo")
        partido["clima"] = clima
        partido["fecha"] = juego_doc.get("fecha")
        partido["hora"] = juego_doc.get("hora")
        partido["grupo"] = juego_doc.get("grupo")
        partido["jornada"] = juego_doc.get("jornada")
        partido["tag"] = juego_doc.get("tag")
        partido["tipo"] = juego_doc.get("tipo")

    # Goleadores estructurados (jugador_id + nombre), para no depender de parsear el texto
    # de los eventos al calcular estadísticas históricas (ver _obtener_mayor_racha_goles).
    # 'entro_de_cambio' y 'equipo' se agregan para la tarjeta "Súper Sub" (ver
    # estadisticas_service._obtener_super_sub); 'goles_penal'/'goles_tiro_libre'/
    # 'goles_corner' para "Especialista a Balón Parado" (ver
    # estadisticas_service._obtener_especialista_balon_parado) -- partidos simulados ANTES de
    # estos cambios no tienen estos campos en 'resultado.goleadores' y no participan en esos
    # cálculos (mismo caveat que 'participantes' más abajo).
    partido["goleadores"] = [
        {
            "jugador_id": jugador_id,
            "jugador_nombre": stats.get("nombre", "?"),
            "goles": stats["goles"],
            "entro_de_cambio": stats.get("entro_de_cambio", False),
            "equipo": stats.get("equipo", "?"),
            "goles_penal": stats.get("goles_penal", 0),
            "goles_tiro_libre": stats.get("goles_tiro_libre", 0),
            "goles_corner": stats.get("goles_corner", 0)
        }
        for jugador_id, stats in stats_jugadores.items()
        if stats.get("goles", 0) > 0
    ]

    # Atajadores estructurados (jugador_id + nombre + cantidad), mismo criterio que
    # 'goleadores' -- para el modal de "ver partidos" de la tarjeta Guante de Oro en
    # estadisticas_service._get_stats_porteros
    partido["atajadores"] = [
        {"jugador_id": jugador_id, "jugador_nombre": stats.get("nombre", "?"), "atajadas": stats["atajadas"]}
        for jugador_id, stats in stats_jugadores.items()
        if stats.get("atajadas", 0) > 0
    ]

    # Todos los jugadores que participaron (titulares + suplentes que entraron), para poder
    # distinguir "jugó pero no anotó" (corta la racha) de "no jugó este partido" (no aplica)
    # al calcular la racha de partidos consecutivos anotando (ver _obtener_mayor_racha_goles)
    partido["participantes"] = list(stats_jugadores.keys())

    # Feed estilo X del dashboard (ver templates/home.html), publicado por la cuenta de la
    # FIFAV: texto narrativo del post + hilo de respuestas con comentarios de 2-3 jugadores
    # (acorde a su estado de ánimo) y, en ocasiones, de la cuenta oficial de alguna selección.
    # Se generan ACÁ (antes de registrar el resultado) para que queden guardados en el mismo
    # 'objeto_resultado' del partido -- el estado de ánimo de cada jugador se recalcula después,
    # dentro de actualizar_jugadores_post_partido, con la misma función pura, así que ambos coinciden siempre.
    partido["texto_narrativo"] = generar_texto_narrativo(
        partido.get("local"), partido.get("visitante"),
        partido["goles_local"], partido["goles_visitante"],
        juego_doc.get("tag") if juego_doc else partido.get("tag")
    )
    partido["comentarios_jugadores"] = generar_comentarios_partido(
        stats_jugadores, partido.get("local"), (juego_doc.get("equipo_local") or {}).get("bandera", "") if juego_doc else "",
        partido.get("visitante"), (juego_doc.get("equipo_visitante") or {}).get("bandera", "") if juego_doc else "",
        partido["goles_local"], partido["goles_visitante"],
        partido.get("eventos", []), (partido.get("clima") or {}).get("condicion")
    )

    resp = registrar_resultado_juego(db, juego_id, partido)

    return {
        "exito": True,
        "ya_finalizado": False,
        "partido": partido,
        "stats_jugadores": stats_jugadores,
        "resp_registro": resp,
        "juego_doc": juego_doc,
    }


def aplicar_efectos_secundarios(
    juego_id: str, id_local: int, id_visita: int, resp: Dict[str, Any],
    estadisticas: Dict[str, Any], stats_jugadores: Dict[Any, Any], juego_doc: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Aplica TODOS los efectos secundarios post-partido: estadísticas de jugadores, estadísticas
    de país (colección 'internacional'), popularidad/aficionados, liquidación de quinielas,
    valor de mercado y dividendos de Dueño de Selecciones, puntos Fantasy, regalías de sedes,
    poder/ranking de ambos países, y avance de fase de la confederación.

    Separado de simular_y_registrar_resultado para que la Simulación en Vivo
    (services/live_match_service.py) pueda diferir este bloque entero hasta que termine la
    ventana de revelación -- el flujo manual (routes/simular_route.py, vía
    ejecutar_simulacion_completa) sigue llamando a ambas funciones juntas, en el mismo orden y
    con el mismo comportamiento de siempre.

    :param resp: lo que devuelve registrar_resultado_juego -- se usa "exito" y "resultado"
        (con "ganador_lado", "goles_local", "goles_visitante").
    :param estadisticas: el campo 'estadisticas' del partido (mismo valor ya persistido en 'juegos').
    :param stats_jugadores: dict {jugador_id: stats} del motor de simulación.
    :param juego_doc: doc de 'juegos' -- puede ser el snapshot pre-simulación o una relectura
        posterior, son equivalentes acá (ningún campo que se usa de este doc lo toca
        registrar_resultado_juego).
    """
    goles_local = resp["resultado"]["goles_local"]
    goles_visitante = resp["resultado"]["goles_visitante"]

    # Las estadísticas de 'jugadores' (goles/asistencias/atajadas/rendimiento, etc.) solo se
    # persisten una vez que el partido quedó confirmado como 'finalizado' en 'juegos'. Si el
    # flujo fallaba entre simular y registrar el resultado, el partido quedaba "creado"
    # (pendiente) pero las stats de los jugadores ya se habían incrementado, y un reintento las
    # duplicaba -- por eso este gate.
    if resp["exito"]:
        actualizar_jugadores_post_partido(stats_jugadores, goles_local, goles_visitante)

    actualizar_estadisticas_pais(id_local, id_visita, goles_local, goles_visitante, estadisticas)

    # Popularidad y Base de Aficionados: victoria/empate/derrota + "Efecto Estrella" + bono de
    # "sorpresa" (David vs Goliat). No debe frenar la simulación si falla -- no es parte del
    # flujo crítico del partido.
    delta_aficionados = {"local": {"delta": 0, "aficionados_totales": 0}, "visitante": {"delta": 0, "aficionados_totales": 0}}
    try:
        match_data_aficionados = {
            "fase_id": juego_doc.get("fase_id") if juego_doc else None,
            "id_local": id_local, "id_visitante": id_visita,
            "goles_local": goles_local, "goles_visitante": goles_visitante,
            "rankin_local": (juego_doc.get("equipo_local") or {}).get("rankin", 0) if juego_doc else 0,
            "rankin_visitante": (juego_doc.get("equipo_visitante") or {}).get("rankin", 0) if juego_doc else 0,
        }
        delta_aficionados = actualizar_aficionados_post_partido(match_data_aficionados, stats_jugadores, match_id=juego_id)
    except Exception as e:
        logger.error(f"Error al actualizar aficionados para el partido {juego_id}: {str(e)}")

    # Actualizar/liquidar las quinielas que tenían este partido pendiente de resultado, y
    # actualizar el valor de mercado + dividendos del módulo de Dueño de Selecciones. Ninguna
    # de las dos debe frenar la simulación si algo falla.
    try:
        procesar_resultado_partido(juego_id, resp["resultado"]["ganador_lado"])
    except Exception as e:
        logger.error(f"Error al procesar quinielas para el partido {juego_id}: {str(e)}")

    try:
        procesar_valor_y_dividendos_partido({
            "pais_id_local": id_local,
            "pais_id_visita": id_visita,
            "goles_local": goles_local,
            "goles_visitante": goles_visitante,
            "ganador_lado": resp["resultado"]["ganador_lado"]
        })
    except Exception as e:
        logger.error(f"Error al procesar valor/dividendos de selecciones para el partido {juego_id}: {str(e)}")

    # Reparto de puntos Fantasy (Once Ideal + sinergia con el Álbum de Estampas)
    try:
        procesar_eventos_jugadores_partido(
            juego_doc.get("fase_id") if juego_doc else None,
            stats_jugadores,
            goles_local,
            goles_visitante,
            match_id=juego_id
        )
    except Exception as e:
        logger.error(f"Error al procesar puntos fantasy para el partido {juego_id}: {str(e)}")

    # Cobro de regalías del módulo de Inversión en Sedes/Estadios (con sinergia del Álbum)
    try:
        process_match_city_revenue({
            "ciudad_id": (juego_doc.get("ubicacion") or {}).get("id") if juego_doc else None,
            "fase_id": juego_doc.get("fase_id") if juego_doc else None,
            "match_id": juego_id,
            "goles_totales": goles_local + goles_visitante
        })
    except Exception as e:
        logger.error(f"Error al procesar regalías de sede para el partido {juego_id}: {str(e)}")

    # Partido entre país local y visitante
    actualizar_poder_y_rankin("L", id_local, resp["resultado"], resp["resultado"])
    actualizar_poder_y_rankin("V", id_visita, resp["resultado"], resp["resultado"])

    # Imports diferidos: clasificacion_service y mundial_service YA importan de este mismo
    # módulo (juegos_service) a nivel de archivo -- importarlos acá arriba crearía un import
    # circular. Mismo patrón que ya usa ownership_service.sell_team para el mismo problema.
    from services.clasificacion_service import validar_fase_confederacion_completada
    from services.mundial_service import crear_siguiente_fase

    esta_completada = validar_fase_confederacion_completada(db, juego_id)

    if esta_completada:
        # Recalcular el ranking global
        recalcular_rankin()

        # validar si hay siguiente fase en la confederación y, si la hay, generarla
        data_juego = db["juegos"].find_one({"_id": ObjectId(juego_id)})
        mundial_id = data_juego["mundial_id"]
        fase_actual = data_juego["fase_id"]
        siguiente_fase = fase_actual + 1
        confederacion_id = data_juego["confederacion_id"]

        # Esta confederación acaba de completar 'fase_actual' por completo: se le refresca
        # (resetea a 5, no acumula) el crédito de cambios gratis del Once Ideal.
        try:
            refrescar_cambios_gratis_fase(fase_actual)
        except Exception as e:
            logger.error(f"Error al refrescar cambios gratis fantasy de la fase {fase_actual}: {str(e)}")

        crear_siguiente_fase(siguiente_fase, confederacion_id, mundial_id)

    return {"delta_aficionados": delta_aficionados}


def ejecutar_simulacion_completa(juego_id: str, id_local: int, id_visita: int, tiempo_extra: bool = False) -> Dict[str, Any]:
    """
    Corre la simulación completa de UN partido: simular_y_registrar_resultado (motor + persistir
    el resultado) y, si no era idempotente, aplicar_efectos_secundarios (jugadores, país,
    aficionados, quinielas, ownership, fantasy, sedes, ranking, avance de fase). Usado por el
    flujo manual (routes/simular_route.py), que necesita las dos cosas en un solo paso -- la
    Simulación en Vivo (routes/live_match_route.py / services/live_match_service.py) en cambio
    llama a ambas funciones por separado, para diferir la segunda hasta que termine la ventana
    de revelación.

    :return: {
        "exito": bool,
        "ya_finalizado": bool,        # True si no hizo falta simular (idempotencia)
        "partido": dict,              # el 'partido' enriquecido (mismo shape que antes)
        "stats_jugadores": Optional[dict],
        "resp_registro": Optional[dict],  # lo que devuelve registrar_resultado_juego
        "delta_aficionados": Optional[dict],
        "intensidad": Optional[dict],
        "juego_doc": Optional[dict],  # doc de 'juegos' pre-simulación (fecha/hora/tag/fase_id/etc.)
    }
    """
    base = simular_y_registrar_resultado(juego_id, id_local, id_visita, tiempo_extra)

    if base["ya_finalizado"]:
        return {**base, "delta_aficionados": None, "intensidad": None}

    partido = base["partido"]
    resp = base["resp_registro"]

    efectos = aplicar_efectos_secundarios(
        juego_id, id_local, id_visita, resp, partido["estadisticas"], base["stats_jugadores"], base["juego_doc"]
    )

    # Intensidad/momentum del partido por bloques de minutos, para graficar el ritmo del encuentro
    intensidad = calcular_intensidad_partido(partido.get("eventos", []), partido.get("local"), partido.get("visitante"))

    return {
        "exito": True,
        "ya_finalizado": False,
        "partido": partido,
        "stats_jugadores": base["stats_jugadores"],
        "resp_registro": resp,
        "delta_aficionados": efectos["delta_aficionados"],
        "intensidad": intensidad,
        "juego_doc": base["juego_doc"],
    }


# Función para evaluar si un juego de vuelta en un grupo de 2 equipos requiere tiempo extra/penales
def evaluar_tiempo_extra_grupo_dos_equipos(db, juego_id: str, id_local: int, id_visita: int) -> bool:
    """
    Verifica si el juego debe habilitar la posibilidad de tiempo extra/penales:
    - A partir de la fase 8 los partidos son knockout a partido único, siempre aplica.
    - En un grupo de 2 equipos (ida/vuelta), la eliminatoria se define por marcador GLOBAL
      (ida + vuelta), así que el partido de vuelta/jornada 2 siempre debe evaluar tiempo extra,
      sin importar si la ida terminó empatada o no: el global puede quedar empatado igual
      dependiendo del resultado de la vuelta (ver `obtener_marcador_ida_grupo_dos_equipos`,
      que es quien le da a `simular_partido_realista` los goles de la ida para comparar el
      marcador global real).
    """
    collection_juegos = db['juegos']

    # 1. Obtener la información del partido actual
    juego_actual = collection_juegos.find_one({"_id": ObjectId(juego_id)})
    if not juego_actual:
        return False

    # 1.1 A partir de la fase 8 los juegos son de knockout directo
    if juego_actual["fase_id"] >= 8:
        return True

    # Verificar cuántos equipos distintos participan en este grupo_id
    equipos_en_grupo = collection_juegos.distinct("equipo_local.id", {"confederacion_id": juego_actual["confederacion_id"], "grupo": juego_actual["grupo"], "fase_id": juego_actual["fase_id"]})

    # Si el grupo tiene más de 2 equipos, no aplica la regla de vuelta/eliminatoria directa
    if len(equipos_en_grupo) != 2:
        return False

    # 2. Verificar si es la jornada 2 (partido de vuelta) en un grupo de 2 equipos
    jornada = (juego_actual.get("jornada") or juego_actual.get("fecha") or "")

    return jornada.lower() == 'jornada 2'


# Función para obtener el marcador de la ida (jornada 1) de un grupo de 2 equipos,
# reasignando los goles a las posiciones local/visitante del partido de VUELTA actual
# (que pueden estar invertidas respecto a la ida), para poder calcular el marcador global.
def obtener_marcador_ida_grupo_dos_equipos(db, juego_id: str, id_local: int, id_visita: int) -> Optional[Dict[str, Any]]:
    collection_juegos = db['juegos']

    juego_actual = collection_juegos.find_one({"_id": ObjectId(juego_id)})
    if not juego_actual:
        return None

    # Solo aplica para partidos de vuelta (jornada 2) de un grupo de 2 equipos
    jornada = (juego_actual.get("jornada") or juego_actual.get("fecha") or "")
    if jornada.lower() != 'jornada 2':
        return None

    equipos_en_grupo = collection_juegos.distinct("equipo_local.id", {"confederacion_id": juego_actual["confederacion_id"], "grupo": juego_actual["grupo"], "fase_id": juego_actual["fase_id"]})
    if len(equipos_en_grupo) != 2:
        return None

    juego_ida = collection_juegos.find_one({
        "_id": {"$ne": ObjectId(juego_id)},
        "grupo": juego_actual["grupo"],
        "confederacion_id": juego_actual["confederacion_id"],
        "fase_id": juego_actual["fase_id"],
        "jornada": 'Jornada 1',
        "$or": [
            {"equipo_local.id": id_local, "equipo_visitante.id": id_visita},
            {"equipo_local.id": id_visita, "equipo_visitante.id": id_local}
        ]
    })

    if not juego_ida or not juego_ida.get("resultado"):
        return None

    resultado_ida = juego_ida["resultado"]

    # Reasignar los goles de la ida a las posiciones local/visitante del partido de vuelta actual
    if resultado_ida["id_local"] == id_local:
        goles_ida_local = resultado_ida["goles_local"]
        goles_ida_visita = resultado_ida["goles_visitante"]
    else:
        goles_ida_local = resultado_ida["goles_visitante"]
        goles_ida_visita = resultado_ida["goles_local"]

    return {
        "juego_ida_id": str(juego_ida["_id"]),
        "goles_local": goles_ida_local,
        "goles_visita": goles_ida_visita,
        "nombre_local": juego_ida["equipo_local"]["nombre"] if resultado_ida["id_local"] == id_local else juego_ida["equipo_visitante"]["nombre"],
        "nombre_visita": juego_ida["equipo_visitante"]["nombre"] if resultado_ida["id_visitante"] == id_visita else juego_ida["equipo_local"]["nombre"]
    }

# función para verificar si una fase y confederación ya completaron todos sus partidos
def es_fase_confederacion_completada(db, fase_id: int, confederacion_id: int) -> bool:
    """
    Verifica si ya NO existen partidos pendientes por jugar 
    en una fase y confederación específicas.
    """
    collection_juegos = db['juegos']
    
    # Busca partidos que pertenezcan a la fase y confederación, pero que no se hayan jugado
    # (Ajusta los campos según la estructura de tu colección 'juegos')
    partidos_pendientes = collection_juegos.count_documents({
        "fase_id": fase_id,
        "confederacion_id": confederacion_id,
        "$or": [
            {"estado": "creado"},
            {"resultado": {"$exists": False}}
        ]
    })
    
    return partidos_pendientes == 0

COMPETICIONES_POR_CONFEDERACION = {
    1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC"
}

# Íconos para el resumen de "viñetas" del post estilo X del dashboard (ver
# templates/home.html) -- mismo criterio de substring que
# ICONOS_EVENTOS_DESTACADOS/PESOS_INTENSIDAD_EVENTOS más arriba en este archivo, pero acotado
# a lo que tiene sentido resumir en un post corto: goles reales (excluyendo los anulados por
# VAR) y tarjetas.
ICONOS_RESUMEN_FEED = [
    ("ANULADO", None),   # gol anulado por VAR: no cuenta como gol real, no se muestra
    ("GOL", "⚽"),
    ("DOBLE AMARILLA", "🟥"),
    ("ROJA", "🟥"),
    ("TARJETA AMARILLA", "🟨"),
]
MAX_EVENTOS_RESUMEN_FEED = 5

# Métricas de interacción "flavor" del feed estilo X (no son de una red social real: se derivan
# de datos reales del partido -- aforo, goles, tarjetas -- para que se sientan proporcionales a
# la repercusión real del encuentro en vez de ser números arbitrarios).
MULTIPLICADOR_VISUALIZACIONES_POR_ASISTENTE = 12
RETWEETS_POR_GOL = 340
RETWEETS_POR_TARJETA = 40
COMENTARIOS_POR_GOL = 90
COMENTARIOS_POR_TARJETA = 60
ASISTENCIA_DEFAULT_SIN_AFORO = 20000


def formatear_numero_compacto(numero: Optional[int]) -> str:
    """1234 -> '1.2K', 1234567 -> '1.2M' -- formato compacto estilo X/Twitter para contadores
    grandes (likes/retweets/comentarios/visualizaciones), usado como filtro Jinja en home_route.py."""
    numero = numero or 0
    if numero >= 1_000_000:
        return f"{numero / 1_000_000:.1f}M"
    if numero >= 1_000:
        return f"{numero / 1_000:.1f}K"
    return str(numero)


def resaltar_jugadores_en_descripcion(descripcion: Optional[str], jugadores: Optional[list] = None) -> Markup:
    """Envuelve en <strong> cada nombre de jugador presente en 'jugadores' dentro del texto de
    'descripcion' de un evento de partido (ver simular_service.py, campo 'jugadores' de cada
    eventos_visibles.append). Escapa el texto a mano porque Jinja autoescape no aplica una vez
    que el resultado se marca como Markup/safe -- usado como filtro Jinja en simular_route.py y
    juegos_route.py (mismo patrón que formatear_numero_compacto en home_route.py)."""
    texto_escapado = str(escape(descripcion or ""))
    for nombre in jugadores or []:
        if not nombre:
            continue
        nombre_escapado = str(escape(nombre))
        texto_escapado = texto_escapado.replace(
            nombre_escapado, f'<strong class="evento-jugador">{nombre_escapado}</strong>'
        )
    return Markup(texto_escapado)


def _resumen_eventos_feed(eventos: list) -> List[str]:
    """Viñetas breves de goles/tarjetas (en orden cronológico) para el cuerpo del post."""
    resumen = []
    for evento in eventos:
        tipo = (evento.get("tipo") or "").upper()
        for clave, icono in ICONOS_RESUMEN_FEED:
            if clave in tipo:
                if icono:
                    resumen.append(f"{icono} {evento.get('minuto', '?')}' {evento.get('equipo', '')}")
                break
        if len(resumen) >= MAX_EVENTOS_RESUMEN_FEED:
            break
    return resumen


# ==========================================
# Texto narrativo del post (resumen del ambiente del partido)
# ==========================================
DIFERENCIA_GOLEADA_NARRATIVA = 3

# Varias variantes por categoría (se elige una al azar con random.choice) para que el feed no
# repita siempre la misma frase en partidos con un resultado parecido.

FRASES_NARRATIVA_GOLEADA = [
    "¡Victoria aplastante de {ganador} en un duelo electrizante! 🔥⚽ {tag}",
    "{ganador} no tuvo piedad y firmó una goleada para el recuerdo 💥 {tag}",
    "Recital de {ganador}, que dejó en el camino a su rival sin contemplaciones 🎯 {tag}",
    "¡Una aplanadora! {ganador} pasó por encima de su rival con un festival de goles 🚀⚽ {tag}",
    "Paliza histórica de {ganador}: dominio absoluto de principio a fin 🏆💥 {tag}",
    "{ganador} dio un auténtico paseo futbolístico y goleó sin atenuantes 🎪⚽ {tag}",
    "¡Noche mágica para {ganador}! Baile, contundencia y goleada categórica ✨⚽ {tag}",
    "Sin despeinarse: {ganador} aplastó a su rival con una actuación perfecta 💣 {tag}",
    "¡Que paren el partido! {ganador} firmó una paliza inolvidable 💪⚽ {tag}",
    "{ganador} desató un vendaval de goles y se lleva una victoria contundente 🌪️⚽ {tag}",
    "Demolición completa de {ganador}, que no dio espacio a la reacción 🛑⚡ {tag}",
]

FRASES_NARRATIVA_AJUSTADA = [
    "{ganador} se lleva un triunfo agónico sobre la hora ⏱️⚽ {tag}",
    "Partido de infarto: {ganador} se queda con los 3 puntos en el final 😱 {tag}",
    "Sufrido pero merecido: {ganador} logró un triunfo mínimo y valioso 🙏 {tag}",
    "¡En el último suspiro! {ganador} destrabó un partido dramático y se abraza a la victoria 😮‍💨⚽ {tag}",
    "Victoria de oro para {ganador} en un duelo tenso que se definió por detalles 🥇⚖️ {tag}",
    "{ganador} aguantó la presión, pegó en el momento justo y se lleva el partido 🛡️⚡ {tag}",
    "¡Qué final! {ganador} se queda con un triunfo apretado en un choque no apto para cardíacos 🫀⚽ {tag}",
    "Se luchó hasta el último segundo: {ganador} logra una victoria apretadísima 💪⏱️ {tag}",
    "Puso el corazón y la garra: {ganador} rescata tres puntos agónicos 🗡️⚽ {tag}",
    "Duelo cerrado que se resuelve por la mínima a favor de {ganador} 🧗‍♂️⚽ {tag}",
    "¡Final dramático! {ganador} saca petróleo de un partido durísimo ⛏️🔥 {tag}",
]

FRASES_NARRATIVA_CLARA = [
    "Gran partido de {ganador}, que se impuso con autoridad 💪⚽ {tag}",
    "{ganador} hizo respetar su nivel y sumó una victoria contundente 🙌 {tag}",
    "Triunfo sólido de {ganador} de punta a punta del encuentro ✅ {tag}",
    "Jerarquía pura: {ganador} manejó los tiempos y se lleva un triunfo justo 🧠⚽ {tag}",
    "Paso firme de {ganador}, que resolvió el trámite sin pasar sofocones 🟢🔝 {tag}",
    "{ganador} impuso condiciones desde el pitazo inicial y se queda con los tres puntos 🎯 {tag}",
    "Actuación redonda de {ganador}: oficio, buen fútbol y victoria asegurada 📐⚽ {tag}",
    "Sin sorpresas: {ganador} dominó el desarrollo y se lleva una victoria muy clara 📈 {tag}",
    "{ganador} mostró su mejor versión y liquida el partido con sobriedad 🎩⚽ {tag}",
    "Triunfo inapelable de {ganador}, que nunca vio en riesgo su ventaja 🔒 {tag}",
    "Trabajo impecable de {ganador} para asegurar el resultado con solvencia ✨ {tag}",
]

FRASES_NARRATIVA_EMPATE_GOLEADOR = [
    "¡Festival de goles! {local} y {visitante} no se sacaron ventaja en un partidazo ⚽🔥 {tag}",
    "Ida y vuelta sin parar entre {local} y {visitante}, un empate con mucho espectáculo 🍿 {tag}",
    "¡Lluvia de goles! {local} y {visitante} regalaron una exhibición de ataque 🌊⚽ {tag}",
    "Golpe por golpe: {local} y {visitante} empatan en un choque frenético 💥⚽ {tag}",
    "¡Partidazo total! {local} y {visitante} dividieron honores en un espectáculo lleno de emociones 🎭⚽ {tag}",
    "Sin tregua en las áreas: {local} y {visitante} firman una igualdad electrizante ⚡🍿 {tag}",
    "¡Ataques encendidos! {local} y {visitante} se reparten puntos en un duelo de ida y vuelta constante 🥊 {tag}",
    "Puro vértigo: {local} y {visitante} no dieron descanso a los arqueros en un empate vibrante 🧤⚽ {tag}",
    "¡Apenas para aplaudir! {local} y {visitante} nos regalaron una fiesta de goles 👏🔥 {tag}",
    "Duelo de poder a poder: {local} y {visitante} firman las tablas con un marcador abultado 📊 {tag}",
]

FRASES_NARRATIVA_EMPATE_CERRADO = [
    "Reparto de puntos entre {local} y {visitante} en un partido muy cerrado 🤝 {tag}",
    "{local} y {visitante} no lograron sacarse diferencias en un duelo parejo ⚖️ {tag}",
    "Tablas en el marcador: {local} y {visitante} se neutralizaron tácticamente 🧩⚽ {tag}",
    "Mucho estudio y pocas grietas: {local} y {visitante} firman un empate sin sobresaltos 🛑 {tag}",
    "Duelo táctico de ajedrez entre {local} y {visitante} que termina en tablas ♟️ {tag}",
    "Respeto mutuo y defensas sólidas: {local} y {visitante} no rompen la paridad 🧱⚽ {tag}",
    "Pocas luces y mucho combate: {local} y {visitante} dividen puntos en un juego trabado ⚙️ {tag}",
    "{local} y {visitante} cerraron sus líneas y el partido termina en un apretón de manos 🤝⚽ {tag}",
    "Partido de dientes apretados: {local} y {visitante} se quedan con un punto para cada uno 🪨 {tag}",
    "Sin espacio para el error: {local} y {visitante} igualan en un duelo sumamente disputado 🚦 {tag}",
]


def generar_texto_narrativo(nombre_local: str, nombre_visitante: str, goles_local: int, goles_visitante: int, tag: Optional[str] = None) -> str:
    """
    Texto breve y dinámico que resume el ambiente del partido según el resultado final
    (goleada / victoria ajustada / victoria clara / empate con muchos goles / empate cerrado).
    """
    tag_texto = tag or ""
    diferencia = abs(goles_local - goles_visitante)
    total_goles = goles_local + goles_visitante

    if goles_local == goles_visitante:
        plantillas = FRASES_NARRATIVA_EMPATE_GOLEADOR if total_goles >= 3 else FRASES_NARRATIVA_EMPATE_CERRADO
        return random.choice(plantillas).format(local=nombre_local, visitante=nombre_visitante, tag=tag_texto).strip()

    ganador = nombre_local if goles_local > goles_visitante else nombre_visitante
    if diferencia >= DIFERENCIA_GOLEADA_NARRATIVA:
        plantillas = FRASES_NARRATIVA_GOLEADA
    elif diferencia == 1:
        plantillas = FRASES_NARRATIVA_AJUSTADA
    else:
        plantillas = FRASES_NARRATIVA_CLARA
    return random.choice(plantillas).format(ganador=ganador, tag=tag_texto).strip()


# ==========================================
# Comentarios de jugadores (respuestas/hilo del post)
# ==========================================
CANTIDAD_COMENTARIOS_MIN = 2
CANTIDAD_COMENTARIOS_MAX = 3

# Un comentario por estado de ánimo (ver jugadores_service.calcular_estado_animo_jugador),
# varias variantes por estado para que no se repita siempre la misma frase. Además de la frase
# "base" de resultado, cada estado suma variantes de agradecimiento (afición/rival) en los
# ánimos positivos/neutros, y de disconformidad (arbitraje/clima) en los negativos -- así el
# catálogo no se limita solo a comentar el resultado en sí.
FRASES_POR_ESTADO_ANIMO = {
    "Eufórico": [
        "¡Qué grande este equipo! Feliz por el gol y por los 3 puntos 💪🔥",
        "Día soñado, no lo voy a olvidar nunca 🙌⚽",
        "¡Así se juega! Vamos por más 🏆",
        "Gracias a la gente que nos acompaña siempre, este triunfo es para ustedes 🙌❤️",
        "Un gusto compartir cancha con un rival que la peleó hasta el final 🤝",
        "¡Mamma mía, qué locura de partido! Orgulloso de defender esta camiseta 🚀🔥",
        "¡Noche inolvidable! Esto es el fruto del trabajo diario de todo el grupo 🌟⚽",
        "¡Explotó la cancha! Gracias a la hinchada por este marco increíble 🎉🏟️",
        "Partidazo tremendo. Un placer jugar noches así ante un rival tan digno 👏🔥",
        "¡En lo más alto! A disfrutar hoy porque mañana se vuelve a entrenar con todo 💥🚀",
        "Inexplicable la alegría que siento hoy. ¡Gracias Dios y gracias equipo! 🙏⚽",
    ],
    "Motivado": [
        "Contento con el resultado, seguimos sumando 💪",
        "Buen partido del equipo, a mantener este nivel 👏",
        "Cada punto cuenta, vamos paso a paso 🙌",
        "Gracias a la afición por bancarnos en cada partido 🙏",
        "Lindo desafío ante un gran rival, seguimos creciendo juntos",
        "Paso a paso construimos el objetivo. ¡A no aflojar ahora! 📈⚽",
        "Muy buenas sensaciones en lo personal y colectivo. ¡Vamos por más! 👊",
        "Impresionante cómo empuja la gente desde la tribuna, te da un plus enorme 🗣️⚡",
        "Suma muchísimo este resultado pensando en lo que se viene. ¡Enfocados! 🎯",
        "El esfuerzo no se negocia. Gran trabajo de todo el plantel hoy 🤝💪",
        "Respeto enorme para el rival de hoy, nos exigió al 100% y nos hace mejores ⚽✨",
    ],
    "Concentrado": [
        "Un partido más, ya pensando en el próximo rival 🎯",
        "Cumplimos el objetivo, ahora a descansar y seguir",
        "Con la cabeza fría, así se construyen los logros",
        "Gracias al cuerpo técnico y a la gente por el apoyo de siempre",
        "Rival duro el de hoy, nos vamos con más experiencia",
        "Trabajo serio y disciplina en la cancha. A recuperar piernas 🧊⚽",
        "El plan de juego salió tal cual lo preparamos en la semana 📋🧠",
        "Cero distracciones. El torneo es largo y hay que mantener la constancia ⚖️",
        "Agradecido con los hinchas que hicieron el viaje para alentarnos 🚌👏",
        "Duelo muy táctico. Analizaremos los detalles para seguir corrigiendo 📖🔍",
        "Mantener el perfil bajo y seguir trabajando en silencio. Ese es el camino 🤫🎯",
    ],
    "Nervioso": [
        "Partido complicado, nos costó encontrar el rumbo",
        "Quedan cosas para ajustar, vamos con todo al próximo 🙏",
        "Sensaciones mixtas hoy, hay que seguir trabajando",
        "Sinceramente no comparto algunas decisiones arbitrales de hoy, pero seguimos",
        "El clima complicó mucho el ritmo del partido para los dos equipos",
        "Se jugó con los dientes apretados. Mucha tensión en cada pelota 😬⚽",
        "No logramos estar cómodos en la cancha, hay que dar vuelta la página 🔄",
        "El viento y la lluvia hicieron muy difícil el control del balón hoy 🌧️⚽",
        "Hubo jugadas dudosas que cambiaron el ritmo del partido, pero a seguir 🤐",
        "Agradecer a la gente por aguantar el aliento hasta el último minuto 🙏🏟️",
        "Mucha incertidumbre en varios pasajes del juego, nos faltó serenidad 🧠⚠️",
    ],
    "Insatisfecho": [
        "Di lo que pude, pero el resultado no acompañó",
        "Personalmente conforme, pero el equipo necesita más",
        "El resultado no refleja lo que trabajamos en la semana",
        "Hubo jugadas donde el árbitro pudo revisar más, pero no busco excusas",
        "Las condiciones climáticas no ayudaron, pero no es motivo para el resultado",
        "Nos quedamos cortos. Sabíamos que podíamos dar mucho más hoy 📉",
        "Sabor amargo. Hicimos el desgaste pero nos volvemos sin lo que buscábamos 😕",
        "Criterios arbitrales muy distintos para ambos lados hoy, difícil jugar así 🛑",
        "El estado del campo de juego complicó nuestro estilo, aunque no hay excusas 🏟️🌧️",
        "Gracias a la afición que nunca dejó de cantar pese a la lluvia y el resultado ❤️🌧️",
        "Sensación de frustración porque teníamos el partido controlado y se nos escapa 📊",
    ],
    "Frustrado": [
        "No estuvimos a la altura hoy, a corregir errores...",
        "Fue un partido difícil, pido disculpas a la gente",
        "No es excusa, tenemos que ser más responsables",
        "No comparto varias decisiones arbitrales de hoy, aunque eso no quita que debimos hacer más",
        "El estado del clima no ayudó, aun así debimos manejarlo mejor",
        "Noche para olvidar rápido. Toca poner la cara y asumir las fallas 🤦‍♂️⚽",
        "Bronca enorme por cómo se dio el juego. No supimos reaccionar a tiempo 🛑",
        "Increíble las faltas que se cobraron en nuestra área y las que no del otro lado 🤷‍♂️😡",
        "Aceptamos las críticas de la afición, tienen todo el derecho a estar enojados 🙏",
        "Mucho por analizar. Tuvimos desaciertos individuales que costaron muy caro 📉",
        "El clima estuvo insoportable, pero el rival supo adaptarse y nosotros no 🌪️",
    ],
    "Decepcionado": [
        "Duro golpe, no era el resultado que buscábamos 💔",
        "Una noche para el olvido, pedimos disculpas a la afición",
        "Nos vamos con bronca, no jugamos a nuestro nivel",
        "Gracias a la gente que nos acompañó incluso en un día así 🙏",
        "Felicito al rival, hoy fueron mejores que nosotros 👏",
        "Día muy triste para todo el grupo. No encontramos respuestas en la cancha 😞⚽",
        "Le fallamos a la gente que llenó la cancha. Solo queda trabajar el doble 💔🏟️",
        "Nada para rescatar de hoy. Felicitar al rival por su planteo impecable 🤝",
        "Perdón a todos los que vinieron a bancar. Prometemos revertir esta situación 💪🙏",
        "Un trago amargo difícil de digerir. Toca levantar la cabeza entre todos 💔🧱",
        "Duelo aplastante. Es momento de hacer autocrítica puerta adentro 🚪🤐",
    ],
}

# Ícono representativo de cada estado de ánimo en el feed (ver templates/home.html) -- se
# antepone al propio texto del comentario ("😤 Frustrado, ...") en vez de mostrarse como un
# badge de color aparte.
ICONO_ESTADO_ANIMO = {
    "Eufórico": "🔥",
    "Motivado": "⚡",
    "Concentrado": "🎯",
    "Nervioso": "😰",
    "Insatisfecho": "😑",
    "Frustrado": "😤",
    "Decepcionado": "🥺",
}


def generar_comentarios_jugadores(
    stats_jugadores: dict, nombre_local: str, nombre_visitante: str, goles_local: int, goles_visitante: int
) -> List[dict]:
    """
    Elige entre 2 y 3 jugadores al azar de los que participaron del partido y genera un
    comentario breve para cada uno, acorde a su 'estado_animo' (ver
    jugadores_service.calcular_estado_animo_jugador -- misma función pura que usa
    actualizar_jugadores_post_partido para persistirlo, así el comentario del post siempre
    coincide con el estado que termina quedando guardado en 'jugadores').
    """
    if not stats_jugadores:
        return []

    cantidad = min(len(stats_jugadores), random.randint(CANTIDAD_COMENTARIOS_MIN, CANTIDAD_COMENTARIOS_MAX))
    elegidos_ids = random.sample(list(stats_jugadores.keys()), cantidad)

    comentarios = []
    for jugador_id in elegidos_ids:
        stats = stats_jugadores[jugador_id]
        lado = stats.get("lado", "L")
        goles_favor_equipo = goles_local if lado == "L" else goles_visitante
        goles_contra_equipo = goles_visitante if lado == "L" else goles_local
        estado = calcular_estado_animo_jugador(stats, goles_favor_equipo, goles_contra_equipo)
        frases = FRASES_POR_ESTADO_ANIMO.get(estado, FRASES_POR_ESTADO_ANIMO[ESTADO_ANIMO_DEFAULT])

        comentarios.append({
            "jugador_id": jugador_id,
            "nombre": stats.get("nombre", "?"),
            "equipo": nombre_local if lado == "L" else nombre_visitante,
            "estado_animo": estado,
            "es_seleccion": False,
            "comentario": random.choice(frases)
        })
    return comentarios


# ==========================================
# Comentarios de la cuenta oficial de cada selección (hilo del post, distintos de los
# comentarios de jugadores individuales -- ver generar_comentarios_jugadores más arriba)
# ==========================================
NOMBRE_CUENTA_FIFAV = "FIFAV"
HANDLE_CUENTA_FIFAV = "@FIFAV_Oficial"
AVATAR_CUENTA_FIFAV = "🏆"

PROBABILIDAD_COMENTARIO_SELECCION = 0.45  # se evalúa por separado para cada selección
TARJETAS_GRAVES_UMBRAL_QUEJA_ARBITRAJE = 2  # amarillas recibidas (o al menos 1 roja/doble amarilla)
CONDICIONES_CLIMA_ADVERSAS = {"Calor Extremo", "Lluvia Intensa", "Nieve / Frio Intenso"}

FRASES_SELECCION_VICTORIA = [
    "¡Vamos {equipo}! Un triunfo que se disfruta con toda nuestra gente 🏆🔥",
    "Gran trabajo del plantel hoy. ¡Nos llevamos los 3 puntos! ✈️",
    "Otra alegría más para la afición de {equipo} 🙌",
    "¡Orgullo nacional! Victoria contundente para seguir firmes en el objetivo 🇨🇱🇲🇽🇦🇷⚽",
    "¡Paso firme de {equipo}! Triunfo dedicado a todos los que confían en este proyecto 🚀🔝",
    "¡Alegría monumental! {equipo} se queda con una gran victoria en una jornada inolvidable 🌟⚽",
    "Compromiso, fútbol y corazón. {equipo} suma tres puntos claves 🎯💪",
    "¡Pega fuerte {equipo}! Un resultado que premia el esfuerzo de todo el plantel 🦁⚽",
    "Noche soñada para {equipo}. ¡A festejar hoy y mañana enfocarse en lo que viene! 🎉✨",
    "¡Ganó {equipo}! Gran exhibición de fútbol y jerarquía en la cancha 🎩⚽",
]

FRASES_SELECCION_DERROTA = [
    "No es el resultado que buscábamos, pero el grupo sigue unido 💪",
    "Día difícil para {equipo}. Ya pensamos en el próximo desafío 🙏",
    "Nos vamos con la cabeza en alto pese al resultado. Sigue el camino.",
    "Duro tropezón para {equipo}. Toca analizar los errores y levantarse más fuertes 🛡️",
    "El camino es largo y las pruebas nos fortalecen. ¡A seguir trabajando, {equipo}! 🧱⚽",
    "No fue la noche de {equipo}. Agradecemos el apoyo y nos enfocamos en corregir 📉",
    "Sabor amargo tras este traspié. Todo {equipo} redoblará esfuerzos para revertirlo 💔",
    "Hoy no se dio. La selección de {equipo} asume el resultado y ya prepara la revancha 🔄",
    "Un golpe del que nos levantaremos todos juntos como equipo 🤝❤️",
    "Cuestión de carácter: {equipo} aprenderá de este tropiezo para volver mejor 🧗‍♂️",
]

FRASES_SELECCION_EMPATE = [
    "Un punto que suma en el camino de {equipo}. A seguir trabajando 🤝",
    "Partido parejo ante {rival}. Vamos por más en el próximo compromiso",
    "Empate luchado por {equipo}. Valoramos el esfuerzo del equipo en la cancha ⚖️",
    "Reparto de unidades ante {rival}. El camino de {equipo} sigue adelante 📊",
    "Tablas en el marcador. {equipo} rescata un punto valioso tras un trámite exigente 🪨",
    "Intenso ida y vuelta contra {rival}. Nos llevamos aprendizajes y un punto para sumar 📈",
    "Paridad total frente a {rival}. {equipo} continúa enfocado en sus objetivos 🧭",
    "Ni para uno ni para otro: {equipo} iguala ante un duro contrincante 🛑",
    "Seguimos sumando en la tabla. Buen esfuerzo colectivo de {equipo} en un duelo trabado ⛓️",
]

FRASES_SELECCION_AGRADECIMIENTO_AFICION = [
    "Gracias a nuestra hinchada por el aliento de siempre, en casa y a la distancia 🙌❤️",
    "Sin ustedes esto no sería lo mismo. ¡Gracias, afición de {equipo}! 🙏🎽",
    "¡Incondicionales! El calor de la afición de {equipo} se sintió durante los 90 minutos 🗣️🔥",
    "Cada cantico en la tribuna nos empuja hacia adelante. ¡Gracias por estar, {equipo}! 🏟️❤️",
    "La camiseta de {equipo} se defiende por y para ustedes. ¡Infinitas gracias por el apoyo! 🎽✨",
    "Que los colores de {equipo} sigan uniendo a todo el país. ¡Gracias por la fiesta en las gradas! 🥳🎆",
    "Nuestra mayor fortaleza es su apoyo. ¡Gracias a la afición de {equipo} por el respaldo constante! 🛡️❤️",
    "A los miles que viajaron y a los que alentaron desde casa: este sentimiento por {equipo} es único 🌍✈️",
]

FRASES_SELECCION_AGRADECIMIENTO_RIVAL = [
    "Reconocemos el nivel de {rival}, un digno rival dentro de la cancha 🤝",
    "Felicitamos a {rival} por el profesionalismo durante todo el encuentro 👏",
    "Agradecemos a la delegación de {rival} por un partido jugado con espíritu deportivo 🕊️⚽",
    "Un gran choque ante {rival}. El fútbol siempre une a nuestras naciones dentro y fuera de la cancha 🌐🤝",
    "Reconocimiento total para {rival} por la exigencia propuesta en este compromiso 🤜🤛",
    "Saludamos el gran trabajo táctico y la deportividad mostrada por {rival} 👏✨",
    "Un honor compartir cancha con {rival} en esta competencia internacional 🏆",
]

FRASES_SELECCION_QUEJA_ARBITRAJE = [
    "Hay decisiones arbitrales de hoy que ameritan una revisión más profunda ⚖️",
    "No compartimos algunos fallos del árbitro, pero respetamos el resultado en cancha",
    "El VAR debería haber intervenido en más de una jugada del partido de hoy",
    "Sentimos que ciertas determinaciones arbitrales condicionaron el desarrollo del encuentro 🛑",
    "Monitorearemos con la federación las jugadas dudosas que afectaron a {equipo} hoy 📝",
    "Disconformidad total con el criterio disciplinario aplicado en pasajes clave del choque ⚠️",
    "Hubo faltas determinantes que no fueron sancionadas con la misma vara durante el partido 🚫",
    "Creemos en la transparencia del juego y solicitaremos revisión formal sobre las jugadas puntuales 📌",
]

FRASES_SELECCION_QUEJA_CLIMA = [
    "Las condiciones climáticas de hoy fueron extremas para ambos equipos, pero no es excusa",
    "Jugar con este clima no es fácil para nadie. Felicitamos al cuerpo técnico por la preparación",
    "El campo de juego y las condiciones meteorológicas alteraron la dinámica normal del fútbol 🌧️⚽",
    "Un desgaste físico superlativo del plantel de {equipo} bajo exigencias climáticas severas 🌡️❄️",
    "La intensa lluvia y el barro impidieron desplegar el juego fluido que acostumbra {equipo} 🌧️🏟️",
    "Soportamos condiciones de temperatura desfavorables, pero el equipo dio la cara hasta el final ☀️🥵",
    "El clima impuso un duelo más físico que técnico. Resaltamos la entrega de nuestros futbolistas 🦾🌪️",
]

def _tuvo_tarjetas_graves_en_contra(eventos: list, nombre_equipo: str) -> bool:
    """True si el equipo recibió una roja/doble amarilla, o al menos
    TARJETAS_GRAVES_UMBRAL_QUEJA_ARBITRAJE amarillas -- motivo plausible de queja institucional."""
    amarillas = 0
    for evento in eventos or []:
        if evento.get("equipo") != nombre_equipo:
            continue
        tipo = (evento.get("tipo") or "").upper()
        if "ROJA" in tipo or "DOBLE AMARILLA" in tipo:
            return True
        if "AMARILLA" in tipo:
            amarillas += 1
    return amarillas >= TARJETAS_GRAVES_UMBRAL_QUEJA_ARBITRAJE


def _elegir_comentario_seleccion(resultado_equipo: str, hubo_queja_arbitraje: bool, clima_condicion: Optional[str], equipo: str, rival: str) -> Tuple[str, str]:
    """Elige (con pesos) una categoría de comentario institucional disponible según el contexto
    real del partido (resultado + factores como tarjetas graves recibidas o clima adverso) y
    devuelve (tipo_comentario, frase_ya_formateada)."""
    candidatos = []  # (tipo, catalogo, peso)
    if resultado_equipo == "victoria":
        candidatos.append(("victoria", FRASES_SELECCION_VICTORIA, 3))
        candidatos.append(("agradecimiento_rival", FRASES_SELECCION_AGRADECIMIENTO_RIVAL, 1))
    elif resultado_equipo == "derrota":
        candidatos.append(("derrota", FRASES_SELECCION_DERROTA, 3))
    else:
        candidatos.append(("empate", FRASES_SELECCION_EMPATE, 3))
    candidatos.append(("agradecimiento_aficion", FRASES_SELECCION_AGRADECIMIENTO_AFICION, 2))
    if hubo_queja_arbitraje:
        candidatos.append(("queja_arbitraje", FRASES_SELECCION_QUEJA_ARBITRAJE, 2))
    if clima_condicion in CONDICIONES_CLIMA_ADVERSAS:
        candidatos.append(("queja_clima", FRASES_SELECCION_QUEJA_CLIMA, 2))

    tipos, catalogos, pesos = zip(*candidatos)
    idx = random.choices(range(len(candidatos)), weights=pesos)[0]
    tipo, catalogo = tipos[idx], catalogos[idx]
    frase = random.choice(catalogo).format(equipo=equipo, rival=rival)
    return tipo, frase


def generar_comentarios_seleccion(
    nombre_local: str, bandera_local: str, nombre_visitante: str, bandera_visitante: str,
    goles_local: int, goles_visitante: int, eventos: list, clima_condicion: Optional[str] = None
) -> List[dict]:
    """
    Comentarios "institucionales" de la cuenta oficial de cada selección (no de un jugador
    puntual) para el hilo de respuestas del post -- se evalúa por separado para cada equipo
    (con PROBABILIDAD_COMENTARIO_SELECCION) si suma un comentario, y de qué tipo (resultado,
    agradecimiento a la afición/rival, o disconformidad con el arbitraje/clima) según el
    contexto real del partido.
    """
    equipos = [
        (nombre_local, bandera_local, goles_local, goles_visitante, nombre_visitante),
        (nombre_visitante, bandera_visitante, goles_visitante, goles_local, nombre_local),
    ]
    comentarios = []
    for nombre_equipo, bandera_equipo, goles_favor, goles_contra, rival in equipos:
        if random.random() > PROBABILIDAD_COMENTARIO_SELECCION:
            continue
        resultado_equipo = "victoria" if goles_favor > goles_contra else ("derrota" if goles_favor < goles_contra else "empate")
        hubo_queja_arbitraje = _tuvo_tarjetas_graves_en_contra(eventos, nombre_equipo)
        tipo, frase = _elegir_comentario_seleccion(resultado_equipo, hubo_queja_arbitraje, clima_condicion, nombre_equipo, rival)

        comentarios.append({
            "jugador_id": None,
            "nombre": f"Selección {nombre_equipo}",
            "equipo": nombre_equipo,
            "bandera": bandera_equipo,
            "es_seleccion": True,
            "tipo_comentario": tipo,
            "comentario": frase
        })
    return comentarios


def generar_comentarios_partido(
    stats_jugadores: dict, nombre_local: str, bandera_local: str, nombre_visitante: str, bandera_visitante: str,
    goles_local: int, goles_visitante: int, eventos: list, clima_condicion: Optional[str] = None
) -> List[dict]:
    """
    Combina los comentarios de jugadores (generar_comentarios_jugadores) con los, en ocasiones,
    comentarios institucionales de la(s) selección(es) (generar_comentarios_seleccion) en un
    único hilo de respuestas para el post del feed, mezclado en orden aleatorio para que no
    siempre aparezcan los de jugador primero.
    """
    comentarios = generar_comentarios_jugadores(stats_jugadores, nombre_local, nombre_visitante, goles_local, goles_visitante)
    comentarios += generar_comentarios_seleccion(
        nombre_local, bandera_local, nombre_visitante, bandera_visitante, goles_local, goles_visitante, eventos, clima_condicion
    )
    random.shuffle(comentarios)
    return comentarios


# Funcion para obtener los ultimos 5 juegos finalizados, en formato de feed estilo X/Twitter
# (ver templates/home.html) -- cada partido se muestra como si lo hubiera "posteado" la cuenta
# oficial de la FIFAV (el organismo del torneo), no la del equipo local.
def get_data_dashboard_last_games():
    juegos_coll = db["juegos"]
    # OJO: encadenar dos .sort() en pymongo NO los combina -- el segundo pisa al primero. Con
    # una lista de tuplas se ordena por ambos campos en un solo sort real (fecha, y a igualdad
    # de fecha, hora), ambos descendente.
    # 'transmision.estado' != 'in_progress' excluye al partido de la Simulación en Vivo (ver
    # services/live_match_service.py): aunque ya está 100% simulado y persistido (estado =
    # 'finalizado'), la transmisión todavía lo está "revelando" en /en-vivo -- no debe aparecer
    # en el feed como si la FIFAV ya lo hubiera publicado.
    juegos = list(
        juegos_coll.find({"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}})
        .sort([("fecha", -1), ("hora", -1)]).limit(5)
    )

    if not juegos:
        return []

    # Fallback en batch (una sola consulta extra, no N+1) para partidos simulados ANTES de que
    # existiera el snapshot de aficionados embebido en 'juegos.equipo_local.aficionados' (ver
    # fanbase_service.actualizar_aficionados_post_partido) -- para esos casos se usa el valor
    # ACTUAL de 'paises' como mejor aproximación disponible.
    ids_paises_local = {j["equipo_local"]["id"] for j in juegos if j.get("equipo_local", {}).get("id") is not None}
    aficionados_actuales = {
        p["id"]: p.get("aficionados", AFICIONADOS_INICIAL)
        for p in db["paises"].find({"id": {"$in": list(ids_paises_local)}}, {"id": 1, "aficionados": 1})
    } if ids_paises_local else {}

    ultimos_partidos = []
    for juego in juegos:
        equipo_local = juego.get("equipo_local") or {}
        equipo_visitante = juego.get("equipo_visitante") or {}
        resultado = juego.get("resultado") or {}
        eventos = resultado.get("eventos", [])

        goles_local = resultado.get("goles_local", equipo_local.get("goles", 0))
        goles_visitante = resultado.get("goles_visitante", equipo_visitante.get("goles", 0))
        total_goles = goles_local + goles_visitante
        total_tarjetas = sum(
            1 for e in eventos if any(k in (e.get("tipo") or "").upper() for k in ["TARJETA", "ROJA", "AMARILLA"])
        )

        asistencia = (juego.get("aforo") or {}).get("asistencia") or ASISTENCIA_DEFAULT_SIN_AFORO
        likes = equipo_local.get("aficionados")
        if likes is None:
            likes = aficionados_actuales.get(equipo_local.get("id"), AFICIONADOS_INICIAL)

        # Partidos simulados ANTES de que existiera este campo no tienen 'texto_narrativo'
        # guardado -- se genera al vuelo como fallback (solo para mostrar, no se persiste), a
        # partir de datos que siempre están disponibles (nombres, marcador, tag). Los
        # 'comentarios_jugadores' en cambio NO se pueden reconstruir retroactivamente (hace
        # falta el 'stats_jugadores' de ESE partido, que no se guardó históricamente), así que
        # para partidos viejos simplemente no hay comentarios.
        texto_narrativo = resultado.get("texto_narrativo") or generar_texto_narrativo(
            equipo_local.get("nombre", "?"), equipo_visitante.get("nombre", "?"),
            goles_local, goles_visitante, juego.get("tag")
        )
        comentarios_jugadores = resultado.get("comentarios_jugadores", [])

        ultimos_partidos.append({
            "match_id": str(juego["_id"]),
            "tag": juego.get("tag", ""),
            "fecha": juego.get("fecha"),
            "hora": juego.get("hora"),
            "competicion": COMPETICIONES_POR_CONFEDERACION.get(juego.get("confederacion_id"), "Mundial"),
            "autor_nombre": NOMBRE_CUENTA_FIFAV,
            "autor_handle": HANDLE_CUENTA_FIFAV,
            "autor_avatar": AVATAR_CUENTA_FIFAV,
            "local": {"nombre": equipo_local.get("nombre", "?"), "bandera": equipo_local.get("bandera", "")},
            "visitante": {"nombre": equipo_visitante.get("nombre", "?"), "bandera": equipo_visitante.get("bandera", "")},
            "goles_local": goles_local,
            "goles_visitante": goles_visitante,
            "resumen_eventos": _resumen_eventos_feed(eventos),
            "texto_narrativo": texto_narrativo,
            "comentarios_jugadores": comentarios_jugadores,
            "likes": likes,
            "retweets": total_goles * RETWEETS_POR_GOL + total_tarjetas * RETWEETS_POR_TARJETA,
            "comentarios": total_goles * COMENTARIOS_POR_GOL + total_tarjetas * COMENTARIOS_POR_TARJETA,
            "visualizaciones": asistencia * MULTIPLICADOR_VISUALIZACIONES_POR_ASISTENTE
        })

    return ultimos_partidos

# funcion para obtener el juego activo
def obtener_juego_activo(id: str = None):
    partidos_coll = db["juegos"]
    juego_activo = True
    
    # Consulta el primer documento con estado 'creado', ordenado por fecha y hora ascendente
    primer_partido = partidos_coll.find_one(
        {"estado": "creado"},
        sort=[("fecha", ASCENDING), ("hora", ASCENDING)]
    )
    
    if id:
        consultar_partido = partidos_coll.find_one({"_id": ObjectId(id)})
        
        id_primer = str(primer_partido['_id'])
        id_actual = str(consultar_partido['_id'])
   
        if id_primer != id_actual:
            primer_partido = consultar_partido 
            juego_activo = False
    
    return primer_partido, juego_activo


# funcion para obtener datos para el dashboard
def get_data_fase_actual_dashboard():
    partidos_coll = db["juegos"]
    confederaciones_coll = db["confederaciones"]
    fases_coll = db["fases"]
    
    # Consulta el primer documento con estado 'creado', ordenado por fecha y hora ascendente
    primer_partido, juego_activo = obtener_juego_activo()
    
    partidos_jugados = partidos_coll.count_documents({"estado": "finalizado"})
    partidos_totales = 1194

    progreso = (partidos_jugados / partidos_totales) * 100 if partidos_totales > 0 else 0

    if not primer_partido:
        # No queda ningún partido 'estado: creado' -- todas las confederaciones ya jugaron
        # todos sus partidos programados. Mismo criterio "sin próximo partido" que ya manejan
        # el resto de los callers de obtener_juego_activo() (ver
        # live_match_service.iniciar_simulacion_automatica, fantasy_route.py, etc.).
        return {
            "nombre": "Clasificación Finalizada",
            "descripcion": "Todos los partidos programados ya fueron jugados.",
            "progreso": progreso
        }

    confederacion = confederaciones_coll.find_one({"id": primer_partido["confederacion_id"]})
    jornada = primer_partido["jornada"]
    fase = fases_coll.find_one({"id": primer_partido["fase_id"]})
    descripcion = fase["descripcion"]

    fase_actual = {
        "nombre": f"Eliminatorias de {confederacion['region']} - {jornada}",
        "descripcion": descripcion,
        "progreso": progreso
    }
    
    return fase_actual

# Obtener paises que se han clasificado al mundial
def get_data_clasificados_mundial():
    paises_coll = db["paises"]
    
    # Obtener países cuyo estado coincida con cualquiera de los patrones
    query = {
        "estado": {
            "$regex": "CALIFICADO|ELIMINADO_FASE_GRUPOS|ELIMINADO_16VOS|ELIMINADO_8VOS|ELIMINADO_4TOS|GANADOR_",
            "$options": "i",  # Opcional: 'i' para ignorar mayúsculas/minúsculas
        }
    }
    
    paises = list(paises_coll.find(query))
    
    return paises

# funcion para obtener el ultimo partido jugado de un equipo
def obtener_ultimo_partido(equipo_id):
    juegos_coll = db["juegos"]
    # Filtro: El equipo puede ser local o visitante
    filtro = {
        "estado": "finalizado",
        "$or": [
            {"equipo_local.id": equipo_id},
            {"equipo_visitante.id": equipo_id}
        ]
    }
    
    # Busca 1 documento, ordenado por fecha (y hora) en orden descendente
    ultimo_partido = juegos_coll.find_one(
        filtro,
        sort=[("fecha", DESCENDING), ("hora", DESCENDING)]
    )
    
    return ultimo_partido

# Funcion para retornar la etiqueta de un resultado de un pais en especifico
def obtener_resultado_equipo(partido, equipo_id):
    if partido is None:
        return "Sin Partidos Previos"

    resultado_info = partido["resultado"]
    
    # 1. Comprobar si fue empate
    if resultado_info["empate"]:
        return "Empate"
    
    # 2. Comprobar si el equipo es el ganador
    if resultado_info["ganador_id"] == equipo_id:
        return "Victoria"
    else:
        return "Derrota"


def obtener_historial_enfrentamientos(id_local: int, id_visita: int, excluir_id: Optional[str] = None, limite: int = 20) -> List[dict]:
    """
    Partidos FINALIZADOS anteriores entre estos dos mismos equipos (sin importar quién fue
    local/visitante en cada uno), más recientes primero -- para la sección "Historial de
    Enfrentamientos" de la ficha pre-partido (ver templates/simulador.html), que dispara un
    modal de SweetAlert2 si hay al menos uno.

    'excluir_id' es el propio partido que se está viendo/simulando -- necesario porque cuando
    ya está finalizado (ej. al refrescar la página después de simularlo) matchea su propio
    filtro de 'estado: finalizado' y aparecería duplicado en su propio historial.
    """
    juegos_coll = db["juegos"]
    filtro: Dict[str, Any] = {
        "estado": "finalizado",
        "$or": [
            {"equipo_local.id": id_local, "equipo_visitante.id": id_visita},
            {"equipo_local.id": id_visita, "equipo_visitante.id": id_local}
        ]
    }
    if excluir_id:
        try:
            filtro["_id"] = {"$ne": ObjectId(excluir_id)}
        except InvalidId:
            pass

    juegos = juegos_coll.find(
        filtro,
        {
            "equipo_local": 1, "equipo_visitante": 1, "tag": 1, "fecha": 1,
            "resultado.goles_local": 1, "resultado.goles_visitante": 1,
            "resultado.penaltis_local": 1, "resultado.penaltis_visitante": 1
        }
    ).sort([("fecha", DESCENDING)]).limit(limite)

    historial = []
    for j in juegos:
        equipo_local = j.get("equipo_local") or {}
        equipo_visitante = j.get("equipo_visitante") or {}
        resultado = j.get("resultado") or {}
        historial.append({
            "id": str(j["_id"]),
            "fecha": formatear_fecha_es(j.get("fecha")),
            "tag": j.get("tag"),
            "equipo_local": {
                "nombre": equipo_local.get("nombre"),
                "bandera": equipo_local.get("bandera"),
                "goles": resultado.get("goles_local", 0) or 0
            },
            "equipo_visitante": {
                "nombre": equipo_visitante.get("nombre"),
                "bandera": equipo_visitante.get("bandera"),
                "goles": resultado.get("goles_visitante", 0) or 0
            },
            "penaltis_local": resultado.get("penaltis_local"),
            "penaltis_visitante": resultado.get("penaltis_visitante")
        })
    return historial

# Funcion para calcular la asistencia al estadio
def calcular_asistencia(fase_id: int, rankin_local: int, rankin_visita: int):
    """
    Calcula la asistencia y genera un diagnóstico del aforo según la fase y el ranking.
    - fase_id: Int del 1 al 13.
    - ranking_promedio: Promedio del ranking FIFA de ambos equipos (ej. 1 al 200).
    """
    capacidad_estadio=85000
    ranking_promedio=random.randint(25, 75)

    if fase_id > 1:
        ranking_promedio= int((rankin_local + rankin_visita) / 2)
    
    # 1. Definición del multiplicador base según la fase del torneo (1 a 13)
    fases_multiplicador = {
        1: 0.50,  # Eliminatoria confederaciones (Jornadas iniciales)
        2: 0.55,
        3: 0.60,
        4: 0.65,
        5: 0.70,  # Cierre de eliminatorias
        6: 0.75,  # Repechaje internacional
        7: 0.70,  # Fase de grupos del Mundial
        8: 0.78,  # 16avos de final
        9: 0.83,  # 8vos de final
        10: 0.88, # 4tos de final
        11: 0.93, # Semifinal
        12: 0.85, # 3er lugar
        13: 0.98  # Gran Final
    }
    
    # Obtener base según la fase (por defecto 0.60 si está fuera de rango)
    base_fase = fases_multiplicador.get(fase_id, 0.60)
    
    # 2. Ajuste por Ranking (Equipos mejor clasificados atraen más público)
    # Si el promedio es < 20 (top mundial) suma hasta +0.08, si es > 100 resta hasta -0.10
    if ranking_promedio <= 20:
        ajuste_ranking = random.uniform(0.03, 0.08)
    elif ranking_promedio <= 60:
        ajuste_ranking = random.uniform(-0.02, 0.03)
    else:
        ajuste_ranking = random.uniform(-0.10, -0.02)
        
    # 3. Variación aleatoria del día (+/- 5%)
    variacion_dia = random.uniform(-0.05, 0.05)
    
    # 4. Cálculo del porcentaje final de ocupación (entre 10% y 100%)
    porcentaje_ocupacion = min(1.0, max(0.10, base_fase + ajuste_ranking + variacion_dia))
    
    # 5. Cantidad total de asistentes
    asistencia_total = int(capacidad_estadio * porcentaje_ocupacion)
    
    # 6. Determinación del estado / ambiente del estadio
    if porcentaje_ocupacion >= 0.98:
        estado_estadio = "Lleno total / Boletos agotados"
    elif porcentaje_ocupacion >= 0.85:
        estado_estadio = "Casi lleno / Gran ambiente"
    elif porcentaje_ocupacion >= 0.65:
        estado_estadio = "Buena asistencia"
    elif porcentaje_ocupacion >= 0.45:
        estado_estadio = "A la mitad de su capacidad"
    elif porcentaje_ocupacion >= 0.25:
        estado_estadio = "Entrada regular / Varios sectores vacíos"
    else:
        estado_estadio = "Estadio prácticamente vacío"

    # 7. Reparto del aforo entre afición local y visitante. La mayoría de los partidos
    # tiene mayoría de público local, pero en algunos casos (rivalidades, selecciones
    # con mucha afición viajera/diáspora) el reparto puede estar parejo o incluso
    # inclinarse a favor del visitante, igual que en la vida real.
    escenarios_publico = [
        {"tipo": "predominio_local", "rango": (0.60, 0.85)},
        {"tipo": "aforo_parejo", "rango": (0.45, 0.55)},
        {"tipo": "fuerte_afluencia_visitante", "rango": (0.15, 0.40)},
    ]
    pesos_escenario = [65, 22, 13]

    escenario_publico = random.choices(escenarios_publico, weights=pesos_escenario)[0]
    porcentaje_local_publico = round(random.uniform(*escenario_publico["rango"]) * 100, 1)
    porcentaje_visitante_publico = round(100 - porcentaje_local_publico, 1)

    asistentes_local = int(asistencia_total * porcentaje_local_publico / 100)
    asistentes_visitante = asistencia_total - asistentes_local

    return {
        "asistencia": asistencia_total,
        "capacidad_estadio": capacidad_estadio,
        "porcentaje_ocupacion": round(porcentaje_ocupacion * 100, 2),
        "estado": estado_estadio,
        "publico_local": asistentes_local,
        "publico_visitante": asistentes_visitante,
        "porcentaje_publico_local": porcentaje_local_publico,
        "porcentaje_publico_visitante": porcentaje_visitante_publico,
        "escenario_publico": escenario_publico["tipo"]
    }
    
# Pesos de intensidad por tipo de evento, para graficar el ritmo del partido
# (se compara por substring contra el "tipo" del evento; primer match gana)
PESOS_INTENSIDAD_EVENTOS = [
    ("GOL", 10),
    ("DOBLE AMARILLA", 9),
    ("ROJA", 9),
    ("PENAL FALLADO", 6),
    ("ATAJADA", 6),
    ("ERROR DE PORTERÍA", 5),
    ("VAR", 5),
    ("TARJETA AMARILLA", 5),
    ("DESVÍO A CÓRNER", 4),
    ("REGATE DESTACADO", 3),
    ("DISPARO DESVIADO", 3),
    ("ROBO DE BALÓN", 2),
    ("FALTA", 2),
    ("SUSTITUCIÓN", 1),
    ("FUERA DE LUGAR", 1),
    ("TIEMPO EXTRA", 0),
    ("PITIDO FINAL", 0),
    ("SILBATO INICIAL", 0),
]
INTENSIDAD_PESO_DEFAULT = 1

# Iconos destacados a marcar sobre la gráfica de intensidad (gol, tarjetas, cambio).
# Se compara por substring contra el "tipo" del evento; primer match gana.
ICONOS_EVENTOS_DESTACADOS = [
    ("ANULADO", ""),          # gol anulado por VAR: no cuenta como gol
    ("GOL", "⚽"),
    ("DOBLE AMARILLA", "🟥"),
    ("ROJA", "🟥"),
    ("TARJETA AMARILLA", "🟨"),
    ("SUSTITUCIÓN", "🔄"),
]


def calcular_intensidad_partido(eventos: list, nombre_local: str, nombre_visitante: str, tamano_bloque: int = 5) -> dict:
    """
    Agrupa los eventos del partido en bloques de minutos y calcula un puntaje de
    intensidad por bloque (positivo a favor del local, negativo a favor del visitante),
    ponderando más los eventos relevantes (goles, tarjetas, atajadas) que los menores
    (faltas, fuera de lugar), para graficar el ritmo/momentum del encuentro. También
    arma, por bloque, los iconos de los eventos destacados (gol/tarjeta/cambio) para
    marcarlos sobre la gráfica.
    """
    if not eventos:
        return {"labels": [], "valores": [], "iconos": []}

    minuto_max = max(int(e.get("minuto", 0)) for e in eventos) or tamano_bloque
    total_bloques = (minuto_max // tamano_bloque) + 1

    valores = [0] * total_bloques
    iconos_por_bloque = [[] for _ in range(total_bloques)]

    for evento in eventos:
        minuto = int(evento.get("minuto", 0))
        tipo = evento.get("tipo", "")
        equipo = evento.get("equipo", "")
        bloque = min(minuto // tamano_bloque, total_bloques - 1)

        peso = INTENSIDAD_PESO_DEFAULT
        for clave, valor_peso in PESOS_INTENSIDAD_EVENTOS:
            if clave in tipo:
                peso = valor_peso
                break

        if equipo == nombre_local:
            valores[bloque] += peso
        elif equipo == nombre_visitante:
            valores[bloque] -= peso
        # eventos neutrales (Árbitro, VAR, 4to Árbitro, etc.) no inclinan la intensidad hacia ningún equipo

        for clave, icono in ICONOS_EVENTOS_DESTACADOS:
            if clave in tipo:
                if icono:
                    iconos_por_bloque[bloque].append(icono)
                break

    labels = [f"{min((i + 1) * tamano_bloque, minuto_max)}'" for i in range(total_bloques)]
    iconos = ["".join(lista) for lista in iconos_por_bloque]

    return {"labels": labels, "valores": valores, "iconos": iconos}


def guardar_aforo_clima_juego(juego_id: str, aforo: dict, clima: dict):
    """Persiste el aforo y el clima generados para un partido en la colección de juegos."""
    db["juegos"].update_one(
        {"_id": ObjectId(juego_id)},
        {"$set": {"aforo": aforo, "clima": clima}}
    )

# Aproximación de zona climática por confederación del país sede (orden de pesos
# alineado con `condiciones`: Soleado, Calor Extremo, Lluvia Intensa, Nieve/Frío Intenso)
CLIMA_PESOS_POR_CONFEDERACION = {
    1: [45, 10, 25, 20],  # UEFA - Europa: templado/frío, lluvia y frío más frecuentes
    2: [55, 20, 20, 5],   # CONMEBOL - Sudamérica: templado a cálido
    3: [45, 30, 20, 5],   # CONCACAF: calor y humedad tropical
    4: [35, 40, 20, 5],   # CAF - África: calor extremo predominante
    5: [55, 15, 25, 5],   # OFC - Oceanía: templado marítimo
    6: [45, 25, 25, 5],   # AFC - Asia: variado, tendencia cálida/húmeda
}
CLIMA_PESOS_DEFAULT = [50, 20, 20, 10]

def _es_horario_nocturno(hora: str) -> bool:
    """Un partido se considera nocturno desde las 19:00 en adelante (o antes de las 7:00)."""
    if not hora:
        return False
    try:
        hora_num = int(hora.split(":")[0])
    except (ValueError, AttributeError):
        return False
    return hora_num >= 19 or hora_num < 7


def generar_clima_partido(ubicacion: dict, hora: str = None):
    """
    Genera el clima del encuentro según la sede real del partido (ciudad/país
    anfitrión), usando la confederación del país sede como aproximación de su
    zona climática, y la hora del partido para distinguir día/noche (de noche
    no puede salir "Soleado", y las temperaturas base son más frescas).
    """
    de_noche = _es_horario_nocturno(hora)

    condiciones = [
        {
            "condicion": "Despejado" if de_noche else "Soleado",
            "modificador_precision": 0.0,
            "modificador_desgaste": 1.0,
            "modificador_faltas": 0.0,
            "descripcion": "Noche despejada y templada." if de_noche else "Día soleado y despejado."
        },
        {
            "condicion": "Calor Extremo",
            "modificador_precision": -0.05,
            "modificador_desgaste": 1.25,
            "modificador_faltas": 0.05,
            "descripcion": "Noche calurosa y pesada." if de_noche else "Calor sofocante sobre la cancha."
        },
        {
            "condicion": "Lluvia Intensa",
            "modificador_precision": -0.12,
            "modificador_desgaste": 1.15,
            "modificador_faltas": 0.10,
            "descripcion": "Terreno mojado y resbaladizo por la lluvia."
        },
        {
            "condicion": "Nieve / Frio Intenso",
            "modificador_precision": -0.10,
            "modificador_desgaste": 1.10,
            "modificador_faltas": 0.05,
            "descripcion": "Bajas temperaturas que dificultan el control del balón."
        }
    ]

    # Elección ponderada según la zona climática del país sede (fallback a los
    # pesos por defecto si no se puede determinar la confederación de la sede)
    pais_sede = db["paises"].find_one({"id": ubicacion.get("pais_id")}) if ubicacion else None
    confederacion_id = pais_sede.get("confederacion_id") if pais_sede else None
    pesos = CLIMA_PESOS_POR_CONFEDERACION.get(confederacion_id, CLIMA_PESOS_DEFAULT)

    clima = random.choices(condiciones, weights=pesos)[0]

    if clima["condicion"] == "Calor Extremo":
        temperatura_c = random.randint(24, 32) if de_noche else random.randint(28, 38)
    else:
        temperatura_c = random.randint(2, 18) if de_noche else random.randint(5, 25)

    return {
        "condicion": clima["condicion"],
        "temperatura_c": temperatura_c,
        "humedad_porcentaje": random.randint(70, 95) if "Lluvia" in clima["condicion"] else random.randint(30, 60),
        "viento_kmh": random.randint(5, 35),
        "modificadores": {
            "precision": clima["modificador_precision"],
            "faltas": clima["modificador_faltas"],
            "desgaste": clima["modificador_desgaste"]
        }
    }