from fastapi import HTTPException
from typing import Dict, Any, List, Optional
from pymongo.database import Database

# Matriz centralizada de reglas: REGLAS_POBLAR_PAISES[fase_id] = [ {regla}, ... ]
REGLAS_POBLAR_PAISES = {
    1: [
        {"confederacion_id": 1, "limite": 55, "ranking_bajo": False},
        {"confederacion_id": 2, "limite": 10, "ranking_bajo": False},
        {"confederacion_id": 3, "limite": 4, "ranking_bajo": True},
        {"confederacion_id": 4, "limite": 54, "ranking_bajo": False},
        {"confederacion_id": 5, "limite": 4, "ranking_bajo": True},
        {"confederacion_id": 6, "limite": 20, "ranking_bajo": True},
    ],
    2: [
        {"confederacion_id": 1, "limite": 16, "ranking_bajo": False},
        {"confederacion_id": 3, "limite": 33, "ranking_bajo": False},
        {"confederacion_id": 4, "limite": 4, "ranking_bajo": False},
        {"confederacion_id": 5, "limite": 9, "ranking_bajo": False},
        {"confederacion_id": 6, "limite": 36, "ranking_bajo": False},
    ],
    3: [
        {"confederacion_id": 3, "limite": 12, "ranking_bajo": False},
        {"confederacion_id": 4, "limite": 2, "ranking_bajo": False},
        {"confederacion_id": 5, "limite": 4, "ranking_bajo": False},
        {"confederacion_id": 6, "limite": 18, "ranking_bajo": False},
    ],
    4: [
        {"confederacion_id": 5, "limite": 2, "ranking_bajo": False},
        {"confederacion_id": 6, "limite": 6, "ranking_bajo": False},
    ],
    5: [{"confederacion_id": 6, "limite": 2, "ranking_bajo": False}],
    6: [{"confederacion_id": 7, "limite": 6, "ranking_bajo": False}],
    7: [{"confederacion_id": 8, "limite": 48, "ranking_bajo": False}],
    8: [{"confederacion_id": 8, "limite": 32, "ranking_bajo": False}],
    9: [{"confederacion_id": 8, "limite": 16, "ranking_bajo": False}],
    10: [{"confederacion_id": 8, "limite": 8, "ranking_bajo": False}],
    11: [{"confederacion_id": 8, "limite": 4, "ranking_bajo": False}],
    12: [{"confederacion_id": 8, "limite": 2, "ranking_bajo": False}],
    13: [{"confederacion_id": 8, "limite": 2, "ranking_bajo": False}],
}

def poblar_paises_internacional(db: Database, fase_id: int, mundial_id: Any, confederacion_id: Optional[int] = None) -> Dict[str, Any]:
    paises_coll = db["paises"]
    internacional_coll = db["internacional"]

    if fase_id == 1:
        # 1. Limpiar o reiniciar los países activos en la colección internacional
        internacional_coll.delete_many({})

    # 2. Obtener las reglas para la fase
    reglas = REGLAS_POBLAR_PAISES.get(fase_id, [])
    
    if not reglas:
        return {
            "exito": False,
            "mensaje": f"No hay reglas configuradas para la Fase {fase_id}.",
        }
        
    # 3. Filtrar reglas por confederación si fase_id > 1
    if fase_id > 1 and confederacion_id is not None:
        reglas_confederaciones = [
            r for r in reglas if r["confederacion_id"] == confederacion_id
        ]
        if not reglas_confederaciones:
            return {
                "exito": True,
                "total_paises": 0,
                "mensaje": f"La Confederación {confederacion_id} no requiere poblar países en la Fase {fase_id}.",
            }
    else:
        reglas_confederaciones = reglas

    paises_a_insertar = []


    for regla in reglas_confederaciones:
        conf_id = regla["confederacion_id"]
        limite = regla["limite"]
        es_ranking_bajo = regla["ranking_bajo"]

        query = {"confederacion_id": conf_id, "estado": "DISPONIBLE"}
        
        if fase_id == 6: # Repechaje internacional
            query = {"estado": "REPECHAJE_INTERNACIONAL"}
        elif fase_id == 7: # Mundial
            query = {"estado": {"$regex": "CALIFICADO"}}
        elif fase_id == 8: # 16VOS de Mundial
            query = {"estado": {"$regex": "CLASIFICADO_16VOS"}}
        elif fase_id == 9: # 8VOS de Mundial
            query = {"estado": {"$regex": "CLASIFICADO_8VOS"}}
        elif fase_id == 10: # 4TOS de Mundial
            query = {"estado": {"$regex": "CLASIFICADO_4TOS"}}
        elif fase_id == 11: # Semifinal de Mundial
            query = {"estado": {"$regex": "CLASIFICADO_SEMIS"}}
        elif fase_id == 12: # 3er Lugar de Mundial
            query = {"estado": {"$regex": "CLASIFICADO_3ER"}}
        elif fase_id == 13: # FINAL de Mundial
            query = {"estado": {"$regex": "CLASIFICADO_FINAL"}}



        if es_ranking_bajo:
            # Ordenar por ranking descendente (-1) para obtener los de ranking más bajo (p. ej. posición 150, 149...)
            # Si usas puntos FIFA, cambia ("ranking", -1) por ("puntos_ranking", 1)
            cursor = paises_coll.find(query).sort("estadisticas.rankin", -1).limit(limite)
        else:
            # Traer todos o hasta el límite indicado
            cursor = paises_coll.find(query).limit(limite)

        paises_seleccionados = list(cursor)

        # Preparar los documentos para copiar en la colección 'internacional'
        for pais in paises_seleccionados:
            pais.pop("_id", None)
            
            pais["fase_eliminatoria"] = fase_id            
            pais["eliminado"] = False
            pais["mundial_id"] = mundial_id
            pais["estadisticas"]["puntos"] = 0
            pais["estadisticas"]["juegos_jugados"] = 0
            pais["estadisticas"]["juegos_ganados"] = 0
            pais["estadisticas"]["juegos_empatados"] = 0
            pais["estadisticas"]["juegos_perdidos"] = 0
            pais["estadisticas"]["goles_favor"] = 0
            pais["estadisticas"]["goles_contra"] = 0
            pais["estadisticas"]["diferencia_goles"] = 0
                        
            if fase_id < 7:
                pais["estado"] = "ACTIVO"                
            
            # asignacion de confederacion 7 para los equipos de repechaje
            if fase_id == 6:
                pais["confederacion_id"] = 7
            elif fase_id >= 7:
                pais["conf_id"] = pais["confederacion_id"]
                pais["confederacion_id"] = 8
            
            paises_a_insertar.append(pais)

    # 2. Inserción masiva en la colección 'internacional'
    if paises_a_insertar:
        resultado = internacional_coll.insert_many(paises_a_insertar)
        total_insertados = len(resultado.inserted_ids)
        
        # Actualizar estado a "ACTIVO" en la colección origen 'paises'
        ids_paises = [pais["id"] for pais in paises_a_insertar if "id" in pais]
        if ids_paises:
            paises_coll.update_many({"id": {"$in": ids_paises}}, {"$set": {"estado": "ACTIVO"}})
    else:
        total_insertados = 0
        
    return {
        "exito": True,
        "total_paises": total_insertados,
        "mensaje": f"Se registraron {total_insertados} países en la colección 'internacional' para la Fase 1."
    }


def get_pais_internacional(db: Database, id_pais, logger):
    try:        
        collection = db['internacional']
        # Ejecutar la consulta
        pais = collection.find_one({"id": int(id_pais)})
        
        return pais
    except Exception as e:
        logger.error(f"Error al obtener el pais: {str(e)}")
        raise HTTPException(status_code=409, detail=f"Error al obtener el pais: {str(e)}")