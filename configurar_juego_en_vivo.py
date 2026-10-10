"""
Script de configuración del Juego en Vivo (services/juego_en_vivo_service.py). Correr una vez
(python configurar_juego_en_vivo.py) contra la base real; es idempotente, se puede repetir:

  1. Crea los índices de las colecciones del juego:
     - match_live_sessions: único (usuario_id, juego_id) -> una elección por usuario y partido.
     - point_transactions: único (sesion_id, evento_idx, regla_codigo) -> un evento nunca se
       procesa dos veces (segunda barrera además del compare-and-set del servicio).
     - event_point_rules: único (codigo).
  2. Siembra/actualiza 'event_point_rules' desde REGLAS_PUNTOS_DEFAULT (config/juego_en_vivo.py),
     con upsert por 'codigo'. OJO: pisa los valores que se hayan editado a mano en Mongo para
     esos códigos; las reglas extra creadas a mano (otros códigos) no se tocan.

Sin este script el juego igual funciona (el servicio usa los valores por defecto si la colección
de reglas está vacía), pero sin los índices únicos.
"""
import certifi
from datetime import datetime
from pymongo import ASCENDING, UpdateOne
from pymongo.mongo_client import MongoClient

from config.settings import MONGODB_URI
from config.juego_en_vivo import REGLAS_PUNTOS_DEFAULT

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')


def crear_indices():
    db["match_live_sessions"].create_index([("usuario_id", ASCENDING), ("juego_id", ASCENDING)], unique=True, name="usuario_juego_unico")
    db["match_live_sessions"].create_index([("juego_id", ASCENDING), ("estado", ASCENDING)], name="juego_estado")
    db["match_live_sessions"].create_index([("mundial_id", ASCENDING), ("estado", ASCENDING)], name="mundial_estado")
    db["point_transactions"].create_index(
        [("sesion_id", ASCENDING), ("evento_idx", ASCENDING), ("regla_codigo", ASCENDING)], unique=True, name="sesion_evento_regla_unico"
    )
    db["point_transactions"].create_index([("usuario_id", ASCENDING), ("creado_en", ASCENDING)], name="usuario_fecha")
    db["event_point_rules"].create_index([("codigo", ASCENDING)], unique=True, name="codigo_unico")
    print("Índices creados/verificados.")


def sembrar_reglas():
    ahora = datetime.utcnow()
    operaciones = []
    for regla in REGLAS_PUNTOS_DEFAULT:
        doc = {
            **regla,
            "es_positivo": regla["puntos_base"] > 0,
            "pais_id": regla.get("pais_id"),  # None = aplica a cualquier país elegido
            "activo": regla.get("activo", True),
            "actualizado_en": ahora,
        }
        operaciones.append(UpdateOne({"codigo": regla["codigo"]}, {"$set": doc}, upsert=True))
    resultado = db["event_point_rules"].bulk_write(operaciones)
    print(f"Reglas: {resultado.upserted_count} creadas, {resultado.modified_count} actualizadas, {len(operaciones)} en total.")


if __name__ == "__main__":
    crear_indices()
    sembrar_reglas()
