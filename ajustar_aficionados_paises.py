"""
Script de migración para el módulo de Popularidad y Base de Aficionados
(services/fanbase_service.py): agrega el campo 'aficionados' (base UNIFORME,
AFICIONADOS_INICIAL = 100.000) a los documentos de 'paises' que todavía no lo tengan -- no es
un valor aleatorio, todos los países arrancan parejos.

Solo hace falta correrlo UNA VEZ contra los 211 países ya sembrados -- las selecciones nuevas
que se agreguen después ya arrancan con 'aficionados' vía mundial_service.restart_mundial(), y
un país que juegue su primer partido sin haber corrido esta migración igual se auto-inicializa
con el mismo valor (ver fanbase_service._aplicar_delta_aficionados, que usa AFICIONADOS_INICIAL
como fallback vía '$ifNull').

Correr localmente con: python3 ajustar_aficionados_paises.py
"""
import certifi
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
from services.fanbase_service import AFICIONADOS_INICIAL

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')


def ajustar_aficionados():
    paises_coll = db['paises']

    resultado = paises_coll.update_many(
        {"aficionados": {"$exists": False}},
        {"$set": {"aficionados": AFICIONADOS_INICIAL}}
    )

    print(f"✅ Se inicializó 'aficionados' en {AFICIONADOS_INICIAL:,} en {resultado.modified_count} "
          f"país(es) que todavía no lo tenían.")


if __name__ == "__main__":
    ajustar_aficionados()
