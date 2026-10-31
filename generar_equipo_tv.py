"""
Dueño y dos comentaristas FICTICIOS para cada televisora (colección 'televisoras', campo permanente 'equipo').

  equipo = {"dueno": {"nombre", "edad", "rasgo", "rasgo_nombre", "rasgo_texto"},
            "comentaristas": [{"nombre", "edad"}, {"nombre", "edad"}]}

Los nombres salen de nombres y apellidos de los jugadores de la MISMA nacionalidad que la cadena (suenan al idioma local) y
se combinan de forma que no coincidan con nadie del sistema (jugadores, leyendas, árbitros, técnicos) ni entre sí.
El rasgo del dueño sigue el perfil de la cadena; por ahora solo se muestra (más adelante puede mover fidelidad/exigencia).
Determinístico: semilla = id de la cadena; volver a correrlo da lo mismo.

    python generar_equipo_tv.py --muestra [--n 20] [--paises A,B]   # imprime ejemplos, no escribe
    python generar_equipo_tv.py --aplicar                            # escribe 'equipo' en las 633 cadenas
    python generar_equipo_tv.py --revertir                           # quita el campo 'equipo'
"""
import argparse
import random
import unicodedata

PERFIL_RASGOS = {   # perfil de la cadena -> rasgos posibles del dueño
    "generosa": ["mecenas", "visionario", "estrella"],
    "resultadista": ["tiburon", "impaciente", "ahorrador"],
    "fiel": ["tradicional", "visionario", "ahorrador"],
}
RASGOS = {
    "mecenas": ("Mecenas", "Invierte sin mirar tanto el balance: renueva con facilidad y paga de buen grado."),
    "visionario": ("Visionario", "Apuesta por las selecciones en ascenso y por las figuras jóvenes."),
    "estrella": ("Amante de las estrellas", "Se muere por las grandes figuras: sus jugadores invitados lo convencen."),
    "tiburon": ("Tiburón de los negocios", "Negocia duro y no regala nada, pero cumple lo pactado."),
    "impaciente": ("Impaciente", "Pide resultados ya: si la selección no gana, corta sin pensarlo."),
    "ahorrador": ("Ahorrador", "Cuida cada centavo: paga justo y exige bastante a cambio."),
    "tradicional": ("Tradicional", "Es fiel a quien ya conoce: prefiere renovar antes que cambiar."),
}


def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn" and c.isalnum())


def _db():
    from services.imagenes_pais_service import db
    return db


def _prohibidos(db) -> set:
    nombres = set()
    for col in ("jugadores", "arbitros", "directores_tecnicos"):
        nombres |= {_norm(d["nombre"]) for d in db[col].find({}, {"nombre": 1}) if d.get("nombre")}
    return nombres


def _pools(db):
    """{pais_id: (nombres, apellidos)} de los jugadores de cada nacionalidad."""
    pools = {}
    for j in db["jugadores"].find({}, {"nombre": 1, "pais_id": 1, "leyenda": 1}):
        partes = [x for x in (j.get("nombre") or "").split() if x.rstrip(".").lower() not in ("jr", "sr", "ii", "iii")]
        if len(partes) >= 2:
            n, a = pools.setdefault(j["pais_id"], (set(), set()))
            n.add(partes[0])
            if not j.get("leyenda"):   # los apellidos de las leyendas son de figuras famosas: no se reutilizan
                a.add(" ".join(partes[1:]))
    return {k: (sorted(n), sorted(a)) for k, (n, a) in pools.items()}


def _nombre(rng, pool, usados: set, apellidos_cadena: set):
    nombres, apellidos = pool
    for _ in range(400):
        apellido = rng.choice(apellidos)
        completo = f"{rng.choice(nombres)} {apellido}"
        if _norm(completo) not in usados and apellido not in apellidos_cadena:
            apellidos_cadena.add(apellido)
            usados.add(_norm(completo))
            return completo
    raise RuntimeError("sin combinaciones libres")


def armar(db, solo=None):
    """[(cadena, equipo)] de todas (o de 'solo' ids de cadena), en orden de id."""
    pools = _pools(db)
    usados = _prohibidos(db)
    salida = []
    for t in sorted(db["televisoras"].find({}, {"_id": 0, "id": 1, "nombre": 1, "pais_id": 1, "perfil": 1}), key=lambda x: x["id"]):
        rng = random.Random(t["id"] * 7919 + 31)
        pool = pools.get(t["pais_id"]) or max(pools.values(), key=lambda p: len(p[0]))
        rasgo = rng.choice(PERFIL_RASGOS.get(t.get("perfil"), list(RASGOS)))
        ap = set()   # una misma cadena no repite apellido
        equipo = {"dueno": {"nombre": _nombre(rng, pool, usados, ap), "edad": rng.randint(48, 76), "rasgo": rasgo,
                            "rasgo_nombre": RASGOS[rasgo][0], "rasgo_texto": RASGOS[rasgo][1]},
                  "comentaristas": [{"nombre": _nombre(rng, pool, usados, ap), "edad": rng.randint(28, 62)} for _ in range(2)]}
        if solo is None or t["id"] in solo:
            salida.append((t, equipo))
    return salida


def muestra(n: int, paises) -> None:
    db = _db()
    nombres_pais = {p["id"]: p["nombre"] for p in db["paises"].find({}, {"id": 1, "nombre": 1})}
    todo = armar(db)
    if paises:
        elegidas = [x for x in todo if nombres_pais.get(x[0]["pais_id"]) in paises]
    else:
        visto, elegidas = set(), []
        for t, e in todo[:: max(1, len(todo) // n)]:
            if t["pais_id"] not in visto:
                visto.add(t["pais_id"])
                elegidas.append((t, e))
    for t, e in elegidas[: n if not paises else None]:
        d = e["dueno"]
        print(f"{nombres_pais.get(t['pais_id'], '?'):<22} {t['nombre']:<28} ({t.get('perfil')})")
        print(f"    dueño: {d['nombre']} ({d['edad']}) · {d['rasgo_nombre']}")
        print(f"    comentan: {e['comentaristas'][0]['nombre']} ({e['comentaristas'][0]['edad']}) y {e['comentaristas'][1]['nombre']} ({e['comentaristas'][1]['edad']})")
    print(f"\n{len(todo)} cadenas en total, {len({x[1]['dueno']['nombre'] for x in todo})} dueños distintos")


def aplicar() -> None:
    from pymongo import UpdateOne
    db = _db()
    ops = [UpdateOne({"id": t["id"]}, {"$set": {"equipo": e}}) for t, e in armar(db)]
    r = db["televisoras"].bulk_write(ops, ordered=False)
    print(f"{r.modified_count} cadenas con dueño y comentaristas")


def revertir() -> None:
    r = _db()["televisoras"].update_many({}, {"$unset": {"equipo": ""}})
    print(f"campo 'equipo' quitado de {r.modified_count} cadenas")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--muestra", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--revertir", action="store_true")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--paises", default="")
    a = ap.parse_args()
    if a.muestra:
        muestra(a.n, [p.strip() for p in a.paises.split(",") if p.strip()])
    elif a.aplicar:
        aplicar()
    elif a.revertir:
        revertir()
    else:
        print(__doc__)
