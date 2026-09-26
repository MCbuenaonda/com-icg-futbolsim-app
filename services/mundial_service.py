import certifi
import random
from services.international_service import poblar_paises_internacional
from services.grupos_service import asignar_grupos_fase, creacion_grupos_mundial, asignar_grupos_16vos, asignar_grupos_8vos, asignar_grupos_4tos, asignar_grupos_semis, asignar_grupos_3er_lugar, asignar_grupos_final
from services.juegos_service import generar_partidos_fase
from services.ciudades_service import asignar_ubicacion_partidos
from services.fecha_service import asignar_fechas_y_horas_fase1, asignar_fechas_y_horas_fase_siguiente
from services.jugadores_service import obtener_top_goleadores, ESTADO_ANIMO_DEFAULT
from services.clasificacion_service import validacion_equipo_anfitrion
from services.fanbase_service import AFICIONADOS_INICIAL
from bson.objectid import ObjectId
from typing import Optional, Dict, Any
from pymongo.mongo_client import MongoClient
from pymongo import UpdateOne
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

# Ordinales en español para el título del dashboard ("1er/2do/3er... Torneo Mundial de Fútbol
# de la FIFAV"). Del 1 al 10 se usan las formas coloquiales habituales; de ahí en adelante se
# usa el indicador ordinal "º" (ej. "23º"), que es siempre válido en español y evita formas
# irregulares/forzadas para números grandes (this app puede simular mundiales indefinidamente).
ORDINALES_TORNEO = {
    1: "1er", 2: "2do", 3: "3er", 4: "4to", 5: "5to",
    6: "6to", 7: "7mo", 8: "8vo", 9: "9no", 10: "10mo"
}


def formatear_ordinal_torneo(numero: int) -> str:
    """1 -> '1er', 2 -> '2do', 3 -> '3er', ..., 10 -> '10mo', 11+ -> '11º', '12º', ..."""
    return ORDINALES_TORNEO.get(numero, f"{numero}º")


def obtener_ordinal_mundial_actual() -> int:
    """
    Posición (1-based) del mundial activo dentro de todos los mundiales alguna vez creados
    (colección 'mundiales', ordenados por año) -- para el título del dashboard. Si no hay
    ningún mundial activo devuelve 1 (caso defensivo, no debería pasar en el flujo normal ya
    que home_route.inicio() siempre llama a crear_nuevo_mundial() antes).
    """
    mundiales_coll = db["mundiales"]
    mundial_activo = mundiales_coll.find_one({"activo": True}, sort=[("anio", -1)])
    if not mundial_activo:
        return 1
    return mundiales_coll.count_documents({"anio": {"$lte": mundial_activo["anio"]}})


def crear_nuevo_mundial() -> Dict[str, Any]:
    mundiales_coll = db["mundiales"]
    paises_coll = db["paises"]

    # 1. Verificar si ya existe un mundial activo
    mundial_activo = mundiales_coll.find_one({"activo": True})
    if mundial_activo:
        pais_sede = paises_coll.find_one({"id": mundial_activo["pais_id"]})
        
        resp_mundial = {
            "pais": pais_sede["nombre"],
            "anio": mundial_activo["anio"], 
            "_id": mundial_activo["_id"]
        }
        
        return {
            "exito": False,
            "mensaje": f"Ya existe un Mundial activo para el año {mundial_activo['anio']}.",
            "data": resp_mundial
        }

    # 2. Obtener el último mundial registrado (ordenado por año descendente)
    ultimo_mundial = mundiales_coll.find_one(sort=[("anio", -1)])

    if not ultimo_mundial:
        # Caso A: Primer mundial en el sistema
        anio_nuevo = 1900
        confederacion_objetivo = 1
    else:
        # Caso B: Ya existen registros previos, calculamos año y siguiente confederación
        anio_nuevo = ultimo_mundial["anio"] + 4
        
        # Buscar el país del último mundial para saber su confederación
        pais_ultimo = paises_coll.find_one({"id": ultimo_mundial["pais_id"]})
        confed_actual = pais_ultimo.get("confederacion_id", 1) if pais_ultimo else 1
        
        # Rotación de confederaciones (1 a 6)
        confederacion_objetivo = (confed_actual % 6) + 1

    # 3. Elegir un país aleatorio de la confederación correspondiente
    paises_candidatos = list(paises_coll.find({"confederacion_id": confederacion_objetivo}))
    
    if not paises_candidatos:
        raise ValueError(f"No hay países disponibles en la confederación_id = {confederacion_objetivo}")

    pais_sede = random.choice(paises_candidatos)

    # 4. Construir el objeto para la colección 'mundiales'
    nuevo_mundial_doc = {
        "pais_id": pais_sede["id"], # O pais_sede["_id"] según la estructura de tu colección paises
        "anio": anio_nuevo,
        "activo": True,
        "campeon": None,
        "botin": None,
        "por": None,
        "dfi": None,
        "dfd": None,
        "li": None,
        "ld": None,
        "mi": None,
        "mc": None,
        "md": None,
        "ei": None,
        "dc": None,
        "ed": None
    }

    # 5. Insertar en base de datos
    resultado = mundiales_coll.insert_one(nuevo_mundial_doc)
    nuevo_mundial_doc["_id"] = str(resultado.inserted_id)
    
    # 6. Poblar la colección 'internacional' con los países participantes
    poblar_paises_internacional(db, 1, nuevo_mundial_doc["_id"])
    
    # 7. Asignar grupos para la fase 1
    asignar_grupos_fase(db, 1, nuevo_mundial_doc["_id"])
    
    # 8. Crear partidos de la fase 1
    generar_partidos_fase(db, 0, 1,nuevo_mundial_doc["_id"])
    
    # 9. Asigna ubicaciones de cada partido según el país local del equipo
    asignar_ubicacion_partidos(db, nuevo_mundial_doc["_id"], 1)
    
    # 10. Asignar fechas y horas a los partidos de la fase 1
    asignar_fechas_y_horas_fase1(db, nuevo_mundial_doc["_id"])
    
    resp_mundial = {
        "pais": pais_sede["nombre"],
        "anio": nuevo_mundial_doc["anio"],
        "_id": nuevo_mundial_doc["_id"]
    }

    return {
        "exito": True,
        "mensaje": f"Mundial {anio_nuevo} creado exitosamente en {pais_sede.get('nombre', 'País sede')}.",
        "data": resp_mundial
    }
    
def restart_mundial():
    mundiales_coll = db["mundiales"]
    inter_coll = db["internacional"]
    juegos_coll = db["juegos"]
    paises_coll = db["paises"]
    jugadores_coll = db["jugadores"]
    historial_coll = db["historial"]
    user_albums = db["user_albums"]
    team_ownerships = db["team_ownerships"]
    quiniela_usuario = db["quiniela_usuario"]
    pack_purchases = db["pack_purchases"]
    ownership_transactions = db["ownership_transactions"]
    usuarios = db["usuarios"]
    trivia_history = db["trivia_history"]
    user_daily_rewards = db["user_daily_rewards"]
    fantasy_teams = db["fantasy_teams"]
    reward_transactions = db["reward_transactions"]
    city_ownerships = db["city_ownerships"]
    ciudades = db["ciudades"]
    fantasy_points_history = db["fantasy_points_history"]
    historial_aficionados = db["historial_aficionados"]
        
    resultado = paises_coll.update_many(
        {},  # Filtro vacío para seleccionar todos los documentos
        {
            "$set": {
                "estado": "DISPONIBLE",
                "user_id": 0,
                "valor": 1000,
                "estadisticas": {
                    "puntos": 0,
                    "juegos_jugados": 0,
                    "juegos_ganados": 0,
                    "juegos_empatados": 0,
                    "juegos_perdidos": 0,
                    "goles_favor": 0,
                    "goles_contra": 0,
                    "diferencia_goles": 0,
                    "efectividad_gol": 0,
                    "promedio_gol": 0,
                    "p_ofensiva": 50,
                    "p_defensiva": 50,
                    "p_posesion": 50,
                    "rankin": 1,
                    "poder": 0
                },
                # Módulo de Popularidad y Base de Aficionados (ver services/fanbase_service.py)
                # -- base UNIFORME: todos los países arrancan con el mismo valor exacto, vive
                # fuera de 'estadisticas' porque es independiente del ranking FIFA.
                "aficionados": AFICIONADOS_INICIAL
            }
        }
    )
    
    # NOTA: se removieron los campos '*_temp' (goles_temp, asistencias_temp, atajadas_temp,
    # faltas_temp, amarilla_temp, roja_temp) de este reset. Estaban documentados como un
    # posible "contador de la edición de mundial actual vs. acumulado histórico", pero
    # ninguna función del proyecto los incrementa ni los lee -- solo se reseteaban a 0 acá,
    # sin ningún efecto. Los campos reales que sí se usan ('goles', 'asistencias', etc., vía
    # jugadores_service.actualizar_jugadores_post_partido) siguen reseteándose normalmente.
    # También se eliminaron las claves duplicadas que había en este mismo dict
    # ('asistencias'/'asistencias_temp'/'atajadas'/'atajadas_temp' aparecían dos veces).
    resultado_jug = jugadores_coll.update_many(
        {},  # Filtro vacío para seleccionar todos los documentos
        {
            "$set": {
                "goles": 0,
                "asistencias": 0,
                "atajadas": 0,
                "botin": 0,
                "estrella": 0,
                "faltas": 0,
                "amarilla": 0,
                "roja": 0,
                "lesiones": 0,
                "titular": 0,
                "rendimiento": 60,
                "agilidad": 60,
                "agresividad": 60,
                "anticipacion": 60,
                "compostura": 60,
                "concentracion": 60,
                "control_balón": 60,
                # 'especialista_penales'/'especialista_tiros_libres' (rasgo técnico) y
                # 'pie_habil' (rasgo físico fijo) YA NO se resetean acá -- antes se reescribían
                # a False/"ambidiestro" para todos en cada mundial, lo que los volvía inútiles
                # (nada los diferenciaba entre jugadores y el motor nunca podía usarlos de
                # forma significativa). Se asignan UNA sola vez de forma realista con el script
                # asignar_rasgos_jugadores.py y se preservan para siempre entre mundiales,
                # igual que cualquier otro rasgo permanente del jugador. Ver
                # services/simular_service.py::bonus_pie_habil/ejecutar_penal/ejecutar_tiro_libre.
                # 'edad' (asignada una sola vez por asignar_edad_jugadores.py, ver
                # services/jugadores_service.py::_multiplicador_edad) tampoco se resetea acá por
                # el mismo motivo -- es un rasgo de referencia permanente, no una edad
                # cronológica que deba avanzar con cada mundial (no hay retiro/generación de
                # jugadores nuevos en este proyecto).
                "forma_actual": 60,
                "fuerza_disparo": 60,
                "fuerza_fisica": 60,
                "juego_aereo": 60,
                "moral": 60,
                "overall": 60,
                "precision_pase": 60,
                "precision_tiro": 60,
                "regate": 60,
                "resistencia": 60,
                "velocidad": 60,
                "vision_juego": 60,
                "bonificaciones": None,
                "juegos_jugados": 0,
                "control_balon": 60,
                # Estado de ánimo (ver services/jugadores_service.py) -- arranca "Concentrado"
                # para todos, se recalcula partido a partido en actualizar_jugadores_post_partido.
                "estado_animo": ESTADO_ANIMO_DEFAULT,
                "faltas_recibidas": 0,
                "recuperaciones": 0,
                "atajadas_penales": 0,
                # 'tiros_puerta'/'tiros_desviados' se acumulan por partido en
                # jugadores_service.actualizar_jugadores_post_partido (alimentan la efectividad
                # de gol por jugador, ver estadisticas_service._obtener_mejor_efectividad_gol)
                # pero faltaban acá -- sin este fix se colaban valores del mundial anterior.
                "tiros_puerta": 0,
                "tiros_desviados": 0,
                "goles_tiro_libre": 0,
                "goles_corner": 0,
            }
        }
    )
    
    resultado_usr = usuarios.update_many(
        {},  # Filtro vacío para seleccionar todos los documentos
        {            
            "$set": {
                "monto": 10000                
            }
        }
    )
    
    # Eliminar el campo 'owner_user_id' de todos los documentos en 'ciudades'
    resultado_ciudades = ciudades.update_many(
        {},  # Filtro vacío para aplicar a TODOS los documentos
        {"$unset": {"owner_user_id": ""}}  # $unset elimina el campo indicado
    )
    
    # Actualizar todos los documentos en la colección 'paises'
    mundiales_coll.delete_many({})
    inter_coll.delete_many({})
    juegos_coll.delete_many({})
    historial_coll.delete_many({})
    user_albums.delete_many({})
    team_ownerships.delete_many({})
    quiniela_usuario.delete_many({})
    pack_purchases.delete_many({})
    ownership_transactions.delete_many({})
    trivia_history.delete_many({})
    user_daily_rewards.delete_many({})
    fantasy_teams.delete_many({})
    reward_transactions.delete_many({})
    city_ownerships.delete_many({})
    fantasy_points_history.delete_many({})
    historial_aficionados.delete_many({})
    
    crear_nuevo_mundial()


# funcion para crear la siguiente fase de la confederación
def crear_siguiente_fase(fase_id: int, confederacion_id: int, mundial_id: str):    
    # 1. Actualizar el estado de los equipos clasificados y eliminados en la colección 'paises'
    query_clasificado = {"confederacion_id": confederacion_id, "estado": {"$regex": "CLASIFICADO"}}

    # Obtener los equipos clasificados y eliminados de la fase actual
    clasificados_fase = list(db["internacional"].find(query_clasificado))

    # Actualizar el estado de los equipos en la colección 'paises' en un solo bulk_write
    # (antes era un update_one por país clasificado)
    if fase_id < 8 and clasificados_fase:
        db["paises"].bulk_write([
            UpdateOne({"id": clasificado["id"]}, {"$set": {"estado": "DISPONIBLE"}})
            for clasificado in clasificados_fase
        ])

    # se eliminan de 'internacional' los registros de clasificados, eliminados, calificados
    # y de repechaje en un solo delete_many (antes eran 4 delete_many separados). Es seguro
    # combinarlos en un $regex con alternancia porque los 4 prefijos de estado son mutuamente
    # excluyentes entre sí (ningún estado real matchea más de uno de los 4 patrones).
    db["internacional"].delete_many({
        "confederacion_id": confederacion_id,
        "estado": {"$regex": "CLASIFICADO|ELIMINADO|CALIFICADO|REPECHAJE"}
    })
    
    exist_siguiente_fase = True
    
    if fase_id == 2 and confederacion_id == 2:
        exist_siguiente_fase = False
        
    if fase_id == 3 and confederacion_id == 1:
        exist_siguiente_fase = False
        
    if fase_id == 4 and confederacion_id in [3,4]:
        exist_siguiente_fase = False
    
    if fase_id == 5 and confederacion_id == 5:
        exist_siguiente_fase = False
    
    if fase_id == 6 and confederacion_id == 6:
        exist_siguiente_fase = False
        
    if fase_id == 7 and confederacion_id == 7:
        exist_siguiente_fase = False

    if fase_id == 14 and confederacion_id == 8:
        exist_siguiente_fase = False
    
    # obtener conteo de paisesd de la coleccion 'internacional'
    paises_en_coleccion = db["internacional"].count_documents({})
    
    if paises_en_coleccion == 0 and fase_id < 7 and not exist_siguiente_fase:
        confederacion_id = 7
        exist_siguiente_fase = True
    elif paises_en_coleccion == 0 and fase_id == 7 and not exist_siguiente_fase:
        confederacion_id = 8
        validacion_equipo_anfitrion(db, mundial_id)
        exist_siguiente_fase = True
                
    # proceso de creacion de siguiente fase
    if exist_siguiente_fase:    
        # 1. Poblar la colección 'internacional' con los países participantes
        response = poblar_paises_internacional(db, fase_id, mundial_id, confederacion_id)
        
        if fase_id == 7:
            # creacion de grupos             
            creacion_grupos_mundial(db, mundial_id)
        elif fase_id == 8:
            asignar_grupos_16vos(db, mundial_id)        
        elif fase_id == 9:
            asignar_grupos_8vos(db, mundial_id)
        elif fase_id == 10:
            asignar_grupos_4tos(db, mundial_id)
        elif fase_id == 11:
            asignar_grupos_semis(db, mundial_id)
        elif fase_id == 12:
            asignar_grupos_3er_lugar(db, mundial_id)
        elif fase_id == 13:            
            asignar_grupos_final(db, mundial_id)
        else:
            # 2. Asignar grupos para la fase
            asignar_grupos_fase(db, fase_id, mundial_id, confederacion_id)
        
        # 3. Crear partidos de la fase 
        generar_partidos_fase(db, confederacion_id, fase_id, mundial_id)
        
        # 4. Asigna ubicaciones de cada partido según el país local del equipo
        asignar_ubicacion_partidos(db, mundial_id, fase_id)
        
        # 5. Asignar fechas y horas a los partidos de la fase
        asignar_fechas_y_horas_fase_siguiente(db, mundial_id, fase_id)
        
    if fase_id == 14:
        # actualizar datos en la tabla mundiales (marca campeón y 'activo: False')
        mundial_cerrado = update_data_mundial(db, mundial_id)

        # Preparar el terreno para el PRÓXIMO mundial (no un reinicio total: 'jugadores',
        # 'juegos', 'historial' y todas las colecciones de meta-juego -- álbum, ownership,
        # fantasy, etc. -- quedan intactas a propósito, ver restart_mundial() para el wipe
        # completo). Solo corre si update_data_mundial() realmente cerró el mundial -- si no
        # encontró campeón (ver comentario ahí), todavía no terminó de verdad.
        # crear_nuevo_mundial() ya se llama automáticamente desde home_route.inicio() en cada
        # carga del dashboard cuando no hay ningún mundial 'activo': con este reset, la
        # próxima visita a "/" arranca solo la Fase 1 del siguiente mundial.
        if mundial_cerrado:
            clean_and_update()


# funcion para ajustar y limpiar datos
def clean_and_update():
    """
    Reset "liviano" entre un mundial y el siguiente (a diferencia de restart_mundial(), que
    borra todo). Deja a todos los países en condiciones de volver a arrancar la Fase 1:
    - Limpia 'internacional' (el snapshot de la fase/mundial que acaba de terminar).
    - Vuelve el 'estado' de TODOS los países a "DISPONIBLE" (sin este paso, poblar_paises_
      internacional no encuentra a nadie para la Fase 1 del próximo mundial -- todos quedaron
      con un estado terminal como GANADOR_COPA_MUNDIAL_X/ELIMINADO_*/etc.).

    A propósito NO toca 'paises.estadisticas' (puntos, goles_favor/contra, etc.): esos números
    son acumulados históricos entre mundiales, no un contador por-torneo (a diferencia de
    'internacional', que sí arranca en 0 en cada fase nueva).
    """
    inter_coll = db["internacional"]
    paises_coll = db["paises"]

    # elimina datos de la coleccion 'internacional'
    inter_coll.delete_many({})

    # poner estado de los paises en 'disponible'
    paises_coll.update_many(
        {},  # Filtro vacío para seleccionar todos los documentos
        {
            "$set": { "estado": "DISPONIBLE" }
        }
    )

# actualiza los datos en la tabla mundial
def update_data_mundial(db, mundial_id) -> bool:
    """
    Marca campeón y cierra el mundial ('activo': False) al terminar la Gran Final.

    :return: True si se encontró un campeón y se cerró el mundial, False si no (ver
        comentario abajo) -- crear_siguiente_fase() usa este valor para decidir si corresponde
        además preparar el terreno para el próximo mundial (clean_and_update()).
    """
    mundial_coll = db["mundiales"]
    internacional_coll = db["internacional"]

    campeon = internacional_coll.find_one({"estado": {"$regex": "GANADOR_COPA_MUNDIAL"}})
    if not campeon:
        # No debería pasar en el flujo normal (se llama justo después de que
        # procesar_clasificacion_fase marca al ganador de la Gran Final), pero si por lo que
        # sea 'internacional' ya no tiene esa entrada (ej. se limpió antes de tiempo, mismo
        # tipo de problema que dejó el torneo trabado en 8vos->Cuartos), evita el
        # TypeError: 'NoneType' object is not subscriptable y deja el mundial como estaba en
        # vez de reventar toda la simulación del último partido.
        print(f"⚠️ No se encontró país con estado GANADOR_COPA_MUNDIAL al cerrar el mundial {mundial_id} -- no se pudo asignar campeón.")
        return False

    # asignacion de datos
    data = {
        "campeon": campeon["id"],
        "activo": False
    }

    # actualizar datos en el registro de la coleccion 'mundiales'
    mundial_coll.update_one({"_id": ObjectId(mundial_id)}, {"$set": data})
    return True
            
# funcion para obtener las estadisticas del dashboard
def get_data_dashboard_stats(mundial):
    # 1-3. Partidos jugados y goles totales calculados en el servidor de Mongo (aggregate)
    # en vez de traer toda la colección 'juegos' a Python para sumarla ahí.
    pipeline = [
        {"$match": {"estado": "finalizado", "mundial_id": str(mundial["_id"])}},
        {"$group": {
            "_id": None,
            "partidos_jugados": {"$sum": 1},
            "goles_totales": {"$sum": {
                "$add": [
                    {"$ifNull": ["$resultado.goles_local", 0]},
                    {"$ifNull": ["$resultado.goles_visitante", 0]}
                ]
            }}
        }}
    ]
    resultado_agg = list(db["juegos"].aggregate(pipeline))
    partidos_jugados = resultado_agg[0]["partidos_jugados"] if resultado_agg else 0
    goles_totales = resultado_agg[0]["goles_totales"] if resultado_agg else 0

    # 4. Promedio de goles
    promedio_goles = (goles_totales / partidos_jugados) if partidos_jugados > 0 else 0.0
    
    # 5. Top 10 goleadores del torneo (colección 'jugadores') -- ya trae 'pais'/'bandera'
    # resueltos en batch contra 'paises' (ver jugadores_service.obtener_top_goleadores). El
    # primero de la lista es el goleador destacado que ya mostraba la tarjeta del dashboard.
    top_goleadores = obtener_top_goleadores(limite=10)

    goleador_nombre = "-"
    goleador_goles = 0
    goleador_pais = "-"

    if top_goleadores:
        goleador_nombre = top_goleadores[0].get("nombre", "N/A")
        goleador_goles = top_goleadores[0].get("goles", 0)
        goleador_pais = top_goleadores[0].get("pais", "N/A")

    stats = {
        "partidos_jugados": partidos_jugados,
        "goles_totales": goles_totales,
        "promedio_goles": promedio_goles,
        "clasificados_count": 0,
        "total_cupos": 48,
        "goleador_nombre": goleador_nombre,
        "goleador_goles": goleador_goles,
        "goleador_pais": goleador_pais,
        "top_goleadores": top_goleadores
    }

    return stats