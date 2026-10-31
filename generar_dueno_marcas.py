"""
Dueño FICTICIO para cada marca patrocinadora (colección 'marcas', campo permanente 'dueno').

  dueno = {"nombre", "edad", "rasgo", "rasgo_nombre", "rasgo_texto"}

Mismo método que generar_equipo_tv.py: nombre y apellido de jugadores de una nacionalidad (la del país de la marca si es
local, un país de su confederación si es continental, cualquiera si es global), combinados para que no coincidan con nadie
del sistema (jugadores, árbitros, técnicos, dueños y comentaristas de televisoras) ni entre sí. El rasgo sigue el perfil
de la marca. Por ahora solo se muestra. Determinístico: semilla = id de la marca.

    python generar_dueno_marcas.py --muestra [--n 15]    # imprime ejemplos, no escribe
    python generar_dueno_marcas.py --aplicar             # escribe 'dueno' en las 121 marcas
    python generar_dueno_marcas.py --revertir            # quita el campo 'dueno'
"""
import argparse
import random

from generar_equipo_tv import _db, _nombre, _pools, _prohibidos

RASGOS = {
    "fundador": ("Fundador visionario", "Creó la marca de cero: apuesta por ideas nuevas y talentos jóvenes."),
    "tiburon": ("Tiburón comercial", "Negocia duro y busca el mayor retorno en cada patrocinio."),
    "heredero": ("Heredero tradicional", "Cuida el legado de la marca: prefiere lo seguro y las relaciones largas."),
    "futbolero": ("Fanático del fútbol", "Vive el fútbol: se encariña con sus patrocinados y los respalda en las malas."),
    "austero": ("Austero", "Mide cada gasto: paga justo y cortará rápido si no ve resultados."),
    "imagen": ("Obsesionado con la imagen", "Cuida la reputación por encima de todo: ante un escándalo corta sin dudar."),
    "filantropo": ("Filántropo", "Busca causas y comunidad: premia a quien da la cara por su afición."),
}
PERFIL_RASGOS = {
    "selecciones": ["heredero", "futbolero"], "aficion": ["futbolero", "filantropo"], "goleadores": ["tiburon", "futbolero"],
    "veteranos": ["heredero", "austero"], "figuras_forma": ["imagen", "tiburon", "fundador"], "defensas": ["austero", "heredero"],
    "leyendas": ["heredero", "filantropo"], "promesas": ["fundador", "futbolero"],
}


def armar(db):
    pools = _pools(db)
    usados = _prohibidos(db)
    for t in db["televisoras"].find({"equipo": {"$exists": True}}, {"equipo": 1}):
        usados |= {_n(p["nombre"]) for p in [t["equipo"]["dueno"], *t["equipo"]["comentaristas"]]}
    por_conf = {}
    for p in db["paises"].find({}, {"id": 1, "confederacion_id": 1}):
        por_conf.setdefault(p.get("confederacion_id"), []).append(p["id"])
    todos = [pid for pid in pools]
    salida = []
    for m in sorted(db["marcas"].find({}, {"_id": 0, "id": 1, "nombre": 1, "pais_id": 1, "confederacion_id": 1, "alcance": 1, "perfil": 1, "rubro": 1}), key=lambda x: x["id"]):
        rng = random.Random(m["id"] * 6151 + 17)
        if m.get("pais_id") in pools:
            pais = m["pais_id"]
        else:
            candidatos = [p for p in por_conf.get(m.get("confederacion_id"), []) if p in pools] or todos
            pais = rng.choice(sorted(candidatos))
        rasgo = rng.choice(PERFIL_RASGOS.get(m.get("perfil"), list(RASGOS)))
        d = {"nombre": _nombre(rng, pools[pais], usados, set()), "edad": rng.randint(45, 78), "rasgo": rasgo,
             "rasgo_nombre": RASGOS[rasgo][0], "rasgo_texto": RASGOS[rasgo][1]}
        salida.append((m, pais, d))
    return salida


def _n(texto):
    from generar_equipo_tv import _norm
    return _norm(texto)


def muestra(n: int) -> None:
    db = _db()
    nombres = {p["id"]: p["nombre"] for p in db["paises"].find({}, {"id": 1, "nombre": 1})}
    todo = armar(db)
    for m, pais, d in todo[:: max(1, len(todo) // n)][:n]:
        print(f"{m['nombre']:<22} {m['rubro']:<13} {m['alcance']:<11} ({m.get('perfil')})  →  {d['nombre']} ({d['edad']}), {d['rasgo_nombre']}  [nombre de {nombres.get(pais)}]")
    print(f"\n{len(todo)} marcas, {len({x[2]['nombre'] for x in todo})} dueños distintos")


def aplicar() -> None:
    from pymongo import UpdateOne
    db = _db()
    r = db["marcas"].bulk_write([UpdateOne({"id": m["id"]}, {"$set": {"dueno": d}}) for m, _, d in armar(db)], ordered=False)
    print(f"{r.modified_count} marcas con dueño")


def revertir() -> None:
    r = _db()["marcas"].update_many({}, {"$unset": {"dueno": ""}})
    print(f"campo 'dueno' quitado de {r.modified_count} marcas")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--muestra", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--revertir", action="store_true")
    ap.add_argument("--n", type=int, default=15)
    a = ap.parse_args()
    if a.muestra:
        muestra(a.n)
    elif a.aplicar:
        aplicar()
    elif a.revertir:
        revertir()
    else:
        print(__doc__)
