"""
Script de migración para el campo 'estado_animo' de jugadores (ver services/jugadores_service.py):
agrega 'estado_animo: "Concentrado"' a los documentos de 'jugadores' que todavía no lo tengan.

Solo hace falta correrlo UNA VEZ contra los ~4600 jugadores ya sembrados -- a partir de ahí se
recalcula partido a partido en jugadores_service.actualizar_jugadores_post_partido, y
mundial_service.restart_mundial() ya lo resetea a "Concentrado" en cada reinicio de torneo.

Correr localmente con: python3 ajustar_estado_animo_jugadores.py
"""
import certifi
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
from services.jugadores_service import ESTADO_ANIMO_DEFAULT

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')


def ajustar_estado_animo():
    jugadores_coll = db['jugadores']

    resultado = jugadores_coll.update_many(
        {"estado_animo": {"$exists": False}},
        {"$set": {"estado_animo": ESTADO_ANIMO_DEFAULT}}
    )

    print(f"✅ Se inicializó 'estado_animo: {ESTADO_ANIMO_DEFAULT}' en {resultado.modified_count} "
          f"jugador(es) que todavía no lo tenían.")


if __name__ == "__main__":
    ajustar_estado_animo()
