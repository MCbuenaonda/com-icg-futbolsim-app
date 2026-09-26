"""
Script de mantenimiento para cargar/actualizar el catálogo de 'quiniela_config'
(los 3 formatos de quiniela: 3, 5 y 10 partidos).

Usa upsert por 'codigo', así que se puede volver a correr sin duplicar datos.

Correr localmente con: python3 seed_quinielas_config.py
"""
import certifi
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

CONFIGS = [
    {
        "codigo": "POOL_3",
        "nombre": "Quiniela de 3 Partidos",
        "cantidad_partidos": 3,
        "costo_puntos": 100,
        "reglas_premio": [
            {"aciertos_requeridos": 3, "premio_puntos": 500},
            {"aciertos_requeridos": 2, "premio_puntos": 150}
        ],
        "activa": True
    },
    {
        "codigo": "POOL_5",
        "nombre": "Quiniela de 5 Partidos",
        "cantidad_partidos": 5,
        "costo_puntos": 200,
        "reglas_premio": [
            {"aciertos_requeridos": 5, "premio_puntos": 2000},
            {"aciertos_requeridos": 4, "premio_puntos": 500}
        ],
        "activa": True
    },
    {
        "codigo": "POOL_10",
        "nombre": "Quiniela de 10 Partidos",
        "cantidad_partidos": 10,
        "costo_puntos": 500,
        "reglas_premio": [
            {"aciertos_requeridos": 10, "premio_puntos": 20000},
            {"aciertos_requeridos": 9, "premio_puntos": 5000},
            {"aciertos_requeridos": 8, "premio_puntos": 1000}
        ],
        "activa": True
    }
]


def seed_quinielas_config():
    coleccion = db['quiniela_config']
    for config in CONFIGS:
        coleccion.update_one(
            {"codigo": config["codigo"]},
            {"$set": config},
            upsert=True
        )
        print(f"✅ {config['codigo']} ({config['nombre']}) cargada/actualizada")


if __name__ == "__main__":
    seed_quinielas_config()
