"""
Script de mantenimiento para asegurar que todos los países tengan los campos
que usa el módulo de "Dueño de Selecciones" (services/ownership_service.py):
'valor' (default 1000) y 'user_id' (default 0, sin dueño).

Solo toca los documentos a los que les falte el campo (update_many con
$exists: False), así que es seguro correrlo varias veces sin pisar valores
ya asignados.

Correr localmente con: python3 seed_paises_ownership_fields.py
"""
import certifi
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

VALOR_INICIAL_PAIS = 1000


def seed_campos_ownership():
    paises = db['paises']

    resultado_valor = paises.update_many(
        {"valor": {"$exists": False}},
        {"$set": {"valor": VALOR_INICIAL_PAIS}}
    )
    print(f"✅ 'valor' agregado a {resultado_valor.modified_count} países (default {VALOR_INICIAL_PAIS})")

    resultado_dueno = paises.update_many(
        {"user_id": {"$exists": False}},
        {"$set": {"user_id": 0}}
    )
    print(f"✅ 'user_id' agregado a {resultado_dueno.modified_count} países (default 0, sin dueño)")


if __name__ == "__main__":
    seed_campos_ownership()
