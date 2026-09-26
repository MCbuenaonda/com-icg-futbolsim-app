"""
Script de mantenimiento para asegurar que todas las ciudades tengan el campo
que usa el módulo de "Inversión en Sedes / Estadios" (services/venue_service.py):
'owner_user_id' (default 0, sin dueño).

Solo toca los documentos a los que les falte el campo (update_many con
$exists: False), así que es seguro correrlo varias veces sin pisar valores
ya asignados.

Correr localmente con: python3 seed_ciudades_ownership_fields.py
"""
import certifi
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')


def seed_campos_ownership():
    ciudades = db['ciudades']

    resultado_dueno = ciudades.update_many(
        {"owner_user_id": {"$exists": False}},
        {"$set": {"owner_user_id": 0}}
    )
    print(f"✅ 'owner_user_id' agregado a {resultado_dueno.modified_count} ciudades (default 0, sin dueño)")


if __name__ == "__main__":
    seed_campos_ownership()
