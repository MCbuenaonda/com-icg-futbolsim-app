import certifi
from fastapi import HTTPException, status
from google.api_core.exceptions import GoogleAPIError
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

def get_confederacion(id_confederacion, logger):
    try:        
        mundial_collection = db["mundiales"]
        mundial = mundial_collection.find_one({"activo": True})
        mundial_id = str(mundial["_id"])
        
        collection = db['confederaciones']
        
        # Ejecutar la consulta
        confederacion = collection.find_one({"id": int(id_confederacion)})
        if not confederacion:
            raise HTTPException(status_code=404, detail="Confederación no encontrada")
        
        # 1. Obtener países de la fase actual
        collection_internacional = db['internacional']
        paises_actuales = list(collection_internacional.find({"confederacion_id": int(id_confederacion)}))
        
        # 2. Obtener países de fases anteriores
        historial_collection = db['historial']
        paises_fases_ant = list(historial_collection.find({
            "confederacion_id": int(id_confederacion),
            "mundial_id": mundial_id
        }))
        
        
        # 3. Unificar todos los registros de países
        todos_los_paises = paises_fases_ant + paises_actuales

        # IDs de fase presentes en 'internacional' (la fase vigente de esta confederación) --
        # cualquier otra fase que aparezca (siempre proveniente de 'historial') ya se jugó por
        # completo. Se usa en el punto 4 para marcar cada fase como jugada o no, y en la vista
        # (templates/confederacion.html) para plegar las fases ya jugadas y ahorrar espacio.
        fases_vigentes_ids = {p.get("fase_eliminatoria", 1) for p in paises_actuales}

        # 4. Agrupar por Fase y luego por Grupo
        # Estructura final: { fase_id: { "nombre": "Fase X", "jugada": bool, "grupos": { "A": [...], "B": [...] } } }
        fases = {}
        ids_en_grupo = {}  # (fase_id, grupo) -> set de ids ya agregados, para deduplicar en O(1)
        for pais in todos_los_paises:
            fase_id = pais.get("fase_eliminatoria", 1)
            nombre_fase = pais.get("fase_nombre", f"Fase {fase_id}")
            grupo = pais.get("grupo", "Sin Grupo")

            # Obtener el identificador único del país
            pais_id = str(pais.get("id") or pais.get("siglas"))

            if fase_id not in fases:
                fases[fase_id] = {
                    "nombre": nombre_fase,
                    "jugada": fase_id not in fases_vigentes_ids,
                    "grupos": {}
                }
            
            if grupo not in fases[fase_id]["grupos"]:
                fases[fase_id]["grupos"][grupo] = []
                ids_en_grupo[(fase_id, grupo)] = set()

            # VALIDACIÓN: Verificar si el país ya existe en este grupo de esta fase
            # (set de ids ya vistos por grupo, en vez de un any() recorriendo la lista completa)
            clave_grupo = (fase_id, grupo)
            if pais_id not in ids_en_grupo[clave_grupo]:
                fases[fase_id]["grupos"][grupo].append(pais)
                ids_en_grupo[clave_grupo].add(pais_id)

        # 5. Ordenar las fases por su ID (para renderizar de la Fase 1 en adelante) y, dentro de
        # cada fase, los grupos alfabéticamente (Grupo A, B, C...) -- Mongo los devuelve en el
        # orden en que aparecieron los países, no necesariamente ordenados.
        for datos_fase in fases.values():
            datos_fase["grupos"] = dict(sorted(datos_fase["grupos"].items()))
        confederacion['fases'] = dict(sorted(fases.items()))
        
        return confederacion
    except GoogleAPIError as e:
        logger.error(f"Error de MongoBD: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error de MongoBD: {str(e)}")
    except Exception as e:
        logger.error(f"Error al obtener el pais: {str(e)}")
        raise HTTPException(status_code=409, detail=f"Error al obtener el pais: {str(e)}")


def get_data_confederaciones_dashboard(mundial):
    juegos_coll = db["juegos"]
    internacional_coll = db["internacional"]

    ids_confederaciones = [1, 2, 3, 4, 5, 6]

    # Conteo de partidos finalizados por confederación en un solo aggregate
    # (antes eran 6 count_documents separados)
    pipeline_conteos = [
        {"$match": {"confederacion_id": {"$in": ids_confederaciones}, "estado": "finalizado", "mundial_id": str(mundial["_id"])}},
        {"$group": {"_id": "$confederacion_id", "total": {"$sum": 1}}}
    ]
    conteos_por_confederacion = {doc["_id"]: doc["total"] for doc in juegos_coll.aggregate(pipeline_conteos)}

    # País líder (más puntos) por confederación en un solo aggregate
    # (antes eran 6 find_one separados)
    pipeline_lideres = [
        {"$match": {"confederacion_id": {"$in": ids_confederaciones}, "mundial_id": str(mundial["_id"])}},
        {"$sort": {"estadisticas.puntos": -1}},
        {"$group": {"_id": "$confederacion_id", "top_pais": {"$first": "$$ROOT"}}}
    ]
    lideres_por_confederacion = {doc["_id"]: doc["top_pais"] for doc in internacional_coll.aggregate(pipeline_lideres)}

    # Una confederación que ya completó el 100% de su fase archiva sus países de 'internacional'
    # a 'historial' (mismo patrón que ya usa get_confederacion() más arriba en este archivo) --
    # sin este fallback, 'lideres_por_confederacion' queda sin entrada para esa confederación en
    # cuanto termina, y el dashboard revienta al armar 'confederaciones' más abajo.
    ids_sin_lider = [cid for cid in ids_confederaciones if cid not in lideres_por_confederacion]
    if ids_sin_lider:
        mundial_activo = db["mundiales"].find_one({"activo": True})
        mundial_id = str(mundial_activo["_id"]) if mundial_activo else None
        pipeline_lideres_historial = [
            {"$match": {"confederacion_id": {"$in": ids_sin_lider}, "mundial_id": mundial_id}},
            {"$sort": {"estadisticas.puntos": -1}},
            {"$group": {"_id": "$confederacion_id", "top_pais": {"$first": "$$ROOT"}}}
        ]
        for doc in db["historial"].aggregate(pipeline_lideres_historial):
            lideres_por_confederacion[doc["_id"]] = doc["top_pais"]

    # Cantidad de países miembros por confederación (para la tarjeta de resumen del dashboard),
    # en el mismo aggregate batcheado que el resto de estos conteos.
    pipeline_paises_miembros = [
        {"$match": {"confederacion_id": {"$in": ids_confederaciones}}},
        {"$group": {"_id": "$confederacion_id", "total": {"$sum": 1}}}
    ]
    paises_miembros_por_confederacion = {doc["_id"]: doc["total"] for doc in internacional_coll.aggregate(pipeline_paises_miembros)}

    num_juegos_finallizados_1 = conteos_por_confederacion.get(1, 0)
    num_juegos_finallizados_2 = conteos_por_confederacion.get(2, 0)
    num_juegos_finallizados_3 = conteos_por_confederacion.get(3, 0)
    num_juegos_finallizados_4 = conteos_por_confederacion.get(4, 0)
    num_juegos_finallizados_5 = conteos_por_confederacion.get(5, 0)
    num_juegos_finallizados_6 = conteos_por_confederacion.get(6, 0)
    num_juegos_finallizados_7 = conteos_por_confederacion.get(7, 0)

    top_pais_1 = lideres_por_confederacion.get(1)
    top_pais_2 = lideres_por_confederacion.get(2)
    top_pais_3 = lideres_por_confederacion.get(3)
    top_pais_4 = lideres_por_confederacion.get(4)
    top_pais_5 = lideres_por_confederacion.get(5)
    top_pais_6 = lideres_por_confederacion.get(6)
    top_pais_7 = lideres_por_confederacion.get(7)

    porc_1 = f'{((num_juegos_finallizados_1/248) * 100):.0f}'
    porc_2 = f'{((num_juegos_finallizados_2/90) * 100):.0f}'
    porc_3 = f'{((num_juegos_finallizados_3/190) * 100):.0f}'
    porc_4 = f'{((num_juegos_finallizados_4/276) * 100):.0f}'
    porc_5 = f'{((num_juegos_finallizados_5/42) * 100):.0f}'
    porc_6 = f'{((num_juegos_finallizados_6/232) * 100):.0f}'
    porc_7 = f'{((num_juegos_finallizados_7/12) * 100):.0f}'
        
    estado_1 = "Finalizado" if int(porc_1) >= 100 else "En Curso" if int(porc_1) > 0 and int(porc_1) < 100 else "Pendiente"
    estado_2 = "Finalizado" if int(porc_2) >= 100 else "En Curso" if int(porc_2) > 0 and int(porc_2) < 100 else "Pendiente"
    estado_3 = "Finalizado" if int(porc_3) >= 100 else "En Curso" if int(porc_3) > 0 and int(porc_3) < 100 else "Pendiente"
    estado_4 = "Finalizado" if int(porc_4) >= 100 else "En Curso" if int(porc_4) > 0 and int(porc_4) < 100 else "Pendiente"
    estado_5 = "Finalizado" if int(porc_5) >= 100 else "En Curso" if int(porc_5) > 0 and int(porc_5) < 100 else "Pendiente"
    estado_6 = "Finalizado" if int(porc_6) >= 100 else "En Curso" if int(porc_6) > 0 and int(porc_6) < 100 else "Pendiente"
    estado_7 = "Finalizado" if int(porc_7) >= 100 else "En Curso" if int(porc_7) > 0 and int(porc_7) < 100 else "Pendiente"
    
    confederaciones = [
        {"id": 2, "sigla": "CONMEBOL", "nombre": "Sudamérica", "cupos": 6.5, "progreso": porc_2, "lider": (top_pais_2["nombre"] if top_pais_2 else None), "estado": estado_2, "paises_miembros": paises_miembros_por_confederacion.get(2, 0), "partidos_jugados": num_juegos_finallizados_2, "partidos_totales": 90},
        {"id": 1, "sigla": "UEFA", "nombre": "Europa", "cupos": 16, "progreso": porc_1, "lider": (top_pais_1["nombre"] if top_pais_1 else None), "estado": estado_1, "paises_miembros": paises_miembros_por_confederacion.get(1, 0), "partidos_jugados": num_juegos_finallizados_1, "partidos_totales": 248},
        {"id": 3, "sigla": "CONCACAF", "nombre": "Norte, Centroamérica y Caribe", "cupos": 6, "progreso": porc_3, "lider": (top_pais_3["nombre"] if top_pais_3 else None), "estado": estado_3, "paises_miembros": paises_miembros_por_confederacion.get(3, 0), "partidos_jugados": num_juegos_finallizados_3, "partidos_totales": 190},
        {"id": 4, "sigla": "CAF", "nombre": "África", "cupos": 9.5, "progreso": porc_4, "lider": (top_pais_4["nombre"] if top_pais_4 else None), "estado": estado_4, "paises_miembros": paises_miembros_por_confederacion.get(4, 0), "partidos_jugados": num_juegos_finallizados_4, "partidos_totales": 276},
        {"id": 6, "sigla": "AFC", "nombre": "Asia", "cupos": 8.5, "progreso": porc_6, "lider": (top_pais_6["nombre"] if top_pais_6 else None), "estado": estado_6, "paises_miembros": paises_miembros_por_confederacion.get(6, 0), "partidos_jugados": num_juegos_finallizados_6, "partidos_totales": 232},
        {"id": 5, "sigla": "OFC", "nombre": "Oceanía", "cupos": 1.5, "progreso": porc_5, "lider": (top_pais_5["nombre"] if top_pais_5 else None), "estado": estado_5, "paises_miembros": paises_miembros_por_confederacion.get(5, 0), "partidos_jugados": num_juegos_finallizados_5, "partidos_totales": 42},
        {"id": 7, "sigla": "REPECHAJE", "nombre": "Internacional", "cupos": 2, "progreso": porc_7, "lider": (top_pais_7["nombre"] if top_pais_7 else None), "estado": estado_7, "paises_miembros": 6, "partidos_jugados": num_juegos_finallizados_7, "partidos_totales": 12},
        {"id": 8, "sigla": "MUNDIAL", "nombre": "Internacional", "cupos": 48, "progreso": 0, "lider": "", "estado": "Pendiente", "paises_miembros": 0, "partidos_jugados": 0, "partidos_totales": 0},
    ]

    for conf in confederaciones:
        conf["partidos_pendientes"] = max(conf["partidos_totales"] - conf["partidos_jugados"], 0)

    return confederaciones