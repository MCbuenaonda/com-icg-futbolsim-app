"""
Presidentes de federación (211) y líderes de la afición (211) FICTICIOS, uno de cada por selección: colecciones permanentes `presidentes` y `lideres`
(config/directiva.py). `id` = id del país.

  presidentes: {id, pais_id, pais_nombre, confederacion_id, nombre, edad, federacion, rasgo, rasgo_nombre, rasgo_texto, ficticio}
  lideres:     {id, pais_id, pais_nombre, confederacion_id, nombre, edad, rasgo, rasgo_nombre, rasgo_texto, estilo, estilo_nombre, ficticio}

Nombres y apellidos de jugadores de la MISMA nacionalidad combinados de forma que no coincidan con nadie del sistema (mismo método que generar_equipo_tv.py).
Determinístico (semilla = id del país). Volver a --aplicar no cambia nada (upsert por id; conserva los avatares ya asignados).

    python generar_directiva.py --muestra     # reparto y ejemplos, no escribe
    python generar_directiva.py --aplicar     # escribe y crea los índices únicos
    python generar_directiva.py --revertir    # borra ambas colecciones
"""
import random
import sys
from collections import Counter

from config import directiva as CD


def _db():
    from services.imagenes_pais_service import db
    return db


def armar(db) -> tuple:
    from generar_equipo_tv import _nombre, _pools, _prohibidos
    pools = _pools(db)
    base = max(pools.values(), key=lambda p: len(p[0]))
    usados = _prohibidos(db)
    presidentes, lideres = [], []
    for p in db["paises"].find({}, {"_id": 0, "id": 1, "nombre": 1, "confederacion_id": 1, "federacion": 1}).sort("id", 1):
        r = random.Random(p["id"] * 7919 + 211)
        pool = pools.get(p["id"]) or base
        rp = r.choices(list(CD.RASGOS_PRESIDENTE), weights=[v["peso"] for v in CD.RASGOS_PRESIDENTE.values()])[0]
        rl = r.choices(list(CD.RASGOS_LIDER), weights=[v["peso"] for v in CD.RASGOS_LIDER.values()])[0]
        el = r.choices(list(CD.ESTILOS_LIDER), weights=[v["peso"] for v in CD.ESTILOS_LIDER.values()])[0]
        comun = {"id": p["id"], "pais_id": p["id"], "pais_nombre": p["nombre"], "confederacion_id": p.get("confederacion_id"), "ficticio": True}
        presidentes.append({**comun, "nombre": _nombre(r, pool, usados, set()), "edad": r.randint(46, 76), "federacion": p.get("federacion") or f"Federación de {p['nombre']}",
                            "rasgo": rp, "rasgo_nombre": CD.RASGOS_PRESIDENTE[rp]["nombre"], "rasgo_texto": CD.RASGOS_PRESIDENTE[rp]["texto"]})
        lideres.append({**comun, "nombre": _nombre(r, pool, usados, set()), "edad": r.randint(18, 34), "rasgo": rl, "rasgo_nombre": CD.RASGOS_LIDER[rl]["nombre"],
                        "rasgo_texto": CD.RASGOS_LIDER[rl]["texto"], "estilo": el, "estilo_nombre": CD.ESTILOS_LIDER[el]["nombre"]})
    return presidentes, lideres


def muestra():
    pres, lid = armar(_db())
    print(len(pres), "presidentes ·", dict(Counter(x["rasgo"] for x in pres)))
    print(len(lid), "líderes ·", dict(Counter(x["rasgo"] for x in lid)), "·", dict(Counter(x["estilo"] for x in lid)))
    nombres = [x["nombre"] for x in pres + lid]
    print("nombres únicos:", len(set(nombres)) == len(nombres))
    for a, b in list(zip(pres, lid))[::40]:
        print(f"  {a['pais_nombre']:<14} presidente {a['nombre']:<26} ({a['edad']}, {a['rasgo_nombre']}) · líder {b['nombre']:<24} ({b['edad']}, {b['rasgo_nombre']}, {b['estilo_nombre']})")


def aplicar():
    from pymongo import UpdateOne
    db = _db()
    pres, lid = armar(db)
    for col, docs in (("presidentes", pres), ("lideres", lid)):
        db[col].bulk_write([UpdateOne({"id": d["id"]}, {"$set": d}, upsert=True) for d in docs], ordered=False)
        db[col].create_index("id", unique=True)
        print(f"{db[col].count_documents({})} en '{col}'")


def revertir():
    for col in ("presidentes", "lideres"):
        _db()[col].drop()
    print("colecciones 'presidentes' y 'lideres' borradas")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar, "--revertir": revertir}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
