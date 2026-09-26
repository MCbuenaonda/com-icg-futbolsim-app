# Script suelto de una sola corrida (ver CLAUDE.md: mismo patrón que asignar_rasgos_jugadores.py)
# -- asigna una 'edad' realista y PERMANENTE a cada jugador del catálogo. No es una edad
# cronológica que deba avanzar con cada mundial: no hay sistema de retiro ni de generación de
# jugadores nuevos en este proyecto, así que se trata como un rasgo de referencia fijo (mismo
# criterio que 'pie_habil'), asignado una sola vez y preservado para siempre entre mundiales
# (ver services/mundial_service.py::restart_mundial, que explícitamente no la resetea).
#
# Se usa en services/jugadores_service.py::_multiplicador_edad para que el crecimiento/decremento
# de atributos post-partido sea más rápido en jugadores jóvenes y casi nulo (con declive más
# marcado) en veteranos.
#
# Uso: python asignar_edad_jugadores.py
import random
import certifi
from collections import Counter
from pymongo.mongo_client import MongoClient
from pymongo import UpdateOne
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')
jugadores_coll = db['jugadores']

# Distribución realista de edad de un plantel profesional -- más masa en la edad "pico"
# (24-29), menos en los extremos (debutantes muy jóvenes, veteranos que ya casi no juegan).
EDAD_BUCKETS = [(17, 20), (21, 23), (24, 29), (30, 32), (33, 38)]
EDAD_PESOS = [0.08, 0.17, 0.45, 0.20, 0.10]


def main():
    jugadores = list(jugadores_coll.find({}, {"id": 1}))
    print(f"Jugadores encontrados: {len(jugadores)}")

    operaciones = []
    conteo_bucket = Counter()

    for jugador in jugadores:
        bucket = random.choices(EDAD_BUCKETS, weights=EDAD_PESOS, k=1)[0]
        edad = random.randint(*bucket)
        conteo_bucket[bucket] += 1
        operaciones.append(UpdateOne({"id": jugador["id"]}, {"$set": {"edad": edad}}))

    if operaciones:
        resultado = jugadores_coll.bulk_write(operaciones)
        print(f"Documentos modificados: {resultado.modified_count}")

    print("Distribución por bucket de edad asignada:")
    for bucket in EDAD_BUCKETS:
        print(f"  {bucket[0]}-{bucket[1]}: {conteo_bucket.get(bucket, 0)}")


if __name__ == "__main__":
    main()
