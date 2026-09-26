# Script suelto de una sola corrida (ver CLAUDE.md: mismo patrón que ajuste_pais_jugador.py /
# probar_calificaciones.py) -- asigna de forma realista tres rasgos del esquema de 'jugadores'
# que hasta ahora restart_mundial() reescribía siempre al mismo valor placeholder para TODOS
# los jugadores (False / "ambidiestro"), volviéndolos inútiles: nada los diferenciaba entre
# jugadores y el motor de simulación nunca podía usarlos de forma significativa.
#
# A partir de este cambio, restart_mundial() YA NO toca estos tres campos (ver
# services/mundial_service.py) -- son rasgos físicos/técnicos permanentes del jugador, no
# stats de torneo, así que se asignan UNA sola vez acá y se preservan para siempre entre
# mundiales.
#
# Uso: python asignar_rasgos_jugadores.py
import random
import certifi
from collections import defaultdict
from pymongo.mongo_client import MongoClient
from pymongo import UpdateOne
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')
jugadores_coll = db['jugadores']

# Distribución de pie hábil -- aproximación realista (la gran mayoría diestra, una minoría
# zurda, ser verdaderamente ambidiestro es poco común). Ajustable si hace falta afinarla.
PIE_HABIL_OPCIONES = ["derecho", "izquierdo", "ambidiestro"]
PIE_HABIL_PESOS = [0.78, 0.18, 0.04]

# Probabilidad de que el mejor cobrador de cada equipo (por precision_tiro + fuerza_disparo)
# quede marcado como especialista -- son rolls independientes, así que puede terminar siendo
# especialista de ambos roles, de uno solo, o de ninguno (queda el fallback ya existente en el
# motor: "el de mejor precisión/potencia disponible").
PROB_ESPECIALISTA_PENALES = 0.55
PROB_ESPECIALISTA_TIROS_LIBRES = 0.55


def main():
    jugadores = list(jugadores_coll.find({}, {
        "id": 1, "pais_id": 1, "posicion_id": 1, "precision_tiro": 1, "fuerza_disparo": 1
    }))
    print(f"Jugadores encontrados: {len(jugadores)}")

    por_pais = defaultdict(list)
    for j in jugadores:
        por_pais[j.get("pais_id")].append(j)

    operaciones = []
    total_especialistas_penal = 0
    total_especialistas_tl = 0
    conteo_pie = defaultdict(int)

    for jugador in jugadores:
        pie_habil = random.choices(PIE_HABIL_OPCIONES, weights=PIE_HABIL_PESOS, k=1)[0]
        conteo_pie[pie_habil] += 1
        operaciones.append(UpdateOne({"id": jugador["id"]}, {"$set": {"pie_habil": pie_habil}}))

    for pais_id, plantilla in por_pais.items():
        de_campo = [j for j in plantilla if j.get("posicion_id") != 1]
        if not de_campo:
            continue

        mejor_cobrador = max(
            de_campo,
            key=lambda j: (j.get("precision_tiro", 60) + j.get("fuerza_disparo", 60))
        )

        es_especialista_penal = random.random() < PROB_ESPECIALISTA_PENALES
        es_especialista_tl = random.random() < PROB_ESPECIALISTA_TIROS_LIBRES
        if es_especialista_penal:
            total_especialistas_penal += 1
        if es_especialista_tl:
            total_especialistas_tl += 1

        operaciones.append(UpdateOne(
            {"id": mejor_cobrador["id"]},
            {"$set": {
                "especialista_penales": es_especialista_penal,
                "especialista_tiros_libres": es_especialista_tl
            }}
        ))

    if operaciones:
        resultado = jugadores_coll.bulk_write(operaciones)
        print(f"Documentos modificados: {resultado.modified_count}")

    print("Distribución de pie_habil asignada:", dict(conteo_pie))
    print(f"Equipos con especialista_penales=True: {total_especialistas_penal} / {len(por_pais)}")
    print(f"Equipos con especialista_tiros_libres=True: {total_especialistas_tl} / {len(por_pais)}")


if __name__ == "__main__":
    main()
