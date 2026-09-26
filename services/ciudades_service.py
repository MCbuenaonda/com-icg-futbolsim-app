import random
from typing import Dict, Any
from pymongo.database import Database
from pymongo import UpdateOne
from bson.objectid import ObjectId

def asignar_ubicacion_partidos(db: Database, mundial_id: Any, fase_id: int) -> Dict[str, Any]:
    partidos_coll = db["juegos"]  # O db["juegos"] según el nombre exacto en tu BD
    ciudades_coll = db["ciudades"]

    # 1. Obtener partidos que NO tengan el campo 'ubicacion' o sea nulo
    query_sin_ubicacion = {
        "$or": [
            {"ubicacion": {"$exists": False}},
            {"ubicacion": None}
        ]
    }
    
    partidos = list(partidos_coll.find(query_sin_ubicacion))

    if not partidos:
        return {
            "exito": True,
            "actualizados": 0,
            "mensaje": "No hay partidos pendientes de asignación de ubicación."
        }

    # Caché local de ciudades por país para no saturar la BD con consultas repetidas
    # Ejemplo: { 164: [lista_de_ciudades_rumania], 200: [...] }
    ciudades_por_pais = {}
    operaciones_actualizacion = []
    
    pais_id_mundial = None
    if fase_id >= 7:    
        # 1. Asegurar que mundial_id sea ObjectId si viene como string
        if isinstance(mundial_id, str):
            mundial_id = ObjectId(mundial_id)
        
        mundial = db["mundiales"].find_one({"_id": mundial_id})        
        if not mundial:
            return {"exito": False, "mensaje": "Mundial no encontrado."}
        
        pais_id_mundial = mundial.get("pais_id")
        
    # 2. Iterar sobre cada partido
    for partido in partidos:
        if fase_id >= 7:
            pais_id_local = pais_id_mundial
        else:
            equipo_local = partido.get("equipo_local", {})
            pais_id_local = equipo_local.get("id")

        if not pais_id_local:
            continue

        # 3. Buscar ciudades disponibles para el país local (usando caché)
        if pais_id_local not in ciudades_por_pais:
            ciudades = list(ciudades_coll.find({"pais_id": pais_id_local}))
            ciudades_por_pais[pais_id_local] = ciudades
        else:
            ciudades = ciudades_por_pais[pais_id_local]

        # Si el país local no tiene ciudades registradas en la BD
        if not ciudades:
            # Opcional: puedes definir un fallback/ciudad por defecto si aplica
            continue

        # 4. Elegir una ciudad al azar
        ciudad_seleccionada = random.choice(ciudades)

        # 5. Clonar la estructura de la ciudad excluyendo el '_id'
        ubicacion_data = {
            "id": ciudad_seleccionada.get("id"),
            "nombre": ciudad_seleccionada.get("nombre"),
            "tipo": ciudad_seleccionada.get("tipo"),
            "estadio": ciudad_seleccionada.get("estadio"),
            "pais_id": ciudad_seleccionada.get("pais_id"),
            "pais": ciudad_seleccionada.get("pais")
        }

        # 6. Preparar la operación de actualización masiva
        operaciones_actualizacion.append(
            UpdateOne(
                {"_id": ObjectId(partido["_id"])},
                {"$set": {"ubicacion": ubicacion_data}}
            )
        )

    # 7. Ejecutar actualizados en lote
    if operaciones_actualizacion:
        resultado = partidos_coll.bulk_write(operaciones_actualizacion)
        modificados = resultado.modified_count
    else:
        modificados = 0

    return {
        "exito": True,
        "actualizados": modificados,
        "mensaje": f"Se asignó ubicación exitosamente a {modificados} partidos."
    }