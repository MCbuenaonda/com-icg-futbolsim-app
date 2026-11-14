"""
100 agentes (representantes) FICTICIOS: colección permanente `agentes` (config/agentes.py).

  {id 1..100, nombre, edad, pais_id, confederacion_id, rasgo, rasgo_nombre, rasgo_texto, calidad 0..1, comision, cupo, ficticio: true}

Reparto por confederación en `AGENTES_POR_CONFEDERACION`, un país distinto por agente, nombres y apellidos de jugadores de la MISMA
nacionalidad combinados de forma que no coincidan con nadie del sistema (mismo método que generar_equipo_tv.py). Determinístico:
semilla = id. Volver a correr --aplicar no cambia nada salvo que cambie el catálogo (idempotente por id; conserva el avatar).

    python generar_agentes.py --muestra     # imprime el reparto y ejemplos, no escribe
    python generar_agentes.py --aplicar     # escribe (upsert por id) y crea el índice único
    python generar_agentes.py --revertir    # borra la colección
"""
import random
import sys
from collections import Counter

from config import agentes as CA


def _db():
    from services.imagenes_pais_service import db
    return db


def armar(db) -> list:
    from generar_equipo_tv import _nombre, _pools, _prohibidos
    pools = _pools(db)
    usados = _prohibidos(db)
    paises = list(db["paises"].find({}, {"_id": 0, "id": 1, "nombre": 1, "confederacion_id": 1}).sort("id", 1))
    rng = random.Random(20260817)
    docs, n = [], 0
    for conf, cantidad in CA.AGENTES_POR_CONFEDERACION.items():
        candidatos = [p for p in paises if p.get("confederacion_id") == conf and p["id"] in pools]
        rng.shuffle(candidatos)
        elegidos = candidatos[:cantidad]
        if len(elegidos) < cantidad:   # confederación chica: repite países (otro agente de la misma nacionalidad)
            elegidos += [rng.choice(candidatos) for _ in range(cantidad - len(elegidos))]
        for p in elegidos:
            n += 1
            r = random.Random(n * 7919 + 17)
            rasgo = r.choices(list(CA.PESOS_RASGO), weights=list(CA.PESOS_RASGO.values()))[0]
            calidad = round(min(1.0, max(0.0, r.betavariate(2.2, 2.2))), 3)
            lo, hi = CA.RASGOS[rasgo]["comision"]
            docs.append({"id": n, "nombre": _nombre(r, pools[p["id"]], usados, set()), "edad": r.randint(36, 70), "pais_id": p["id"],
                         "pais_nombre": p["nombre"], "confederacion_id": conf, "rasgo": rasgo, "rasgo_nombre": CA.RASGOS[rasgo]["nombre"],
                         "rasgo_texto": CA.RASGOS[rasgo]["texto"], "calidad": calidad, "comision": round(lo + (hi - lo) * calidad, 4),
                         "cupo": CA.CUPO_POR_AGENTE, "ficticio": True})
    return docs


def muestra():
    docs = armar(_db())
    print(len(docs), "agentes ·", dict(Counter(d["confederacion_id"] for d in docs)), "· rasgos", dict(Counter(d["rasgo"] for d in docs)))
    print("nombres únicos:", len({d["nombre"] for d in docs}) == len(docs), "· países distintos:", len({d["pais_id"] for d in docs}))
    for d in docs[::9]:
        print(f"  {d['id']:>3} {d['nombre']:<28} {d['pais_nombre']:<18} {d['rasgo_nombre']:<13} calidad {d['calidad']:.2f} comisión {d['comision']:.1%}")


def aplicar():
    from pymongo import UpdateOne
    db = _db()
    docs = armar(db)
    db["agentes"].bulk_write([UpdateOne({"id": d["id"]}, {"$set": d}, upsert=True) for d in docs], ordered=False)
    db["agentes"].create_index("id", unique=True)
    print(f"{db['agentes'].count_documents({})} agentes en 'agentes'")


def revertir():
    _db()["agentes"].drop()
    print("colección 'agentes' borrada")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar, "--revertir": revertir}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
