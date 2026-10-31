"""
Medios de comunicación FICTICIOS: 2 por país (diario generalista + medio deportivo = 422) y 12 internacionales (6 globales y 1
por confederación), cada uno con director y periodistas (colección 'medios', PERMANENTE). Ver config/medios.py.

  medio = {id, pais_id, pais, confederacion_id, nombre, slug, papel, nivel, linea, linea_nombre, linea_texto, credibilidad,
           equipo: {director: {nombre, edad, rasgo, ...}, periodistas: [{nombre, edad, rol, estilo, estilo_nombre, sesgo}]}}

Los nombres salen de las raíces de cada idioma (config/televisoras.RAICES) con patrones de prensa y se validan contra medios y
cadenas reales; las personas, de nombres y apellidos de jugadores de la nacionalidad del medio (como generar_equipo_tv.py,
sin apellidos de leyendas ni repetir apellido dentro del medio). Determinístico: semilla fija. Los logos y avatares se hacen aparte.

    python generar_medios.py --muestra [--n 20] [--paises A,B]   # ejemplos, no escribe
    python generar_medios.py --aplicar                            # escribe los 434 medios (upsert por id)
    python generar_medios.py --revertir                           # borra la colección
"""
import argparse
import difflib
import random
import re
import unicodedata

from config import medios as M
from config import televisoras as T
from generar_equipo_tv import _db, _nombre, _norm, _pools, _prohibidos

SEMILLA = 2028


def _plano(t):
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn"))


_NEGRA = [_plano(n) for n in M.LISTA_NEGRA_PRENSA if len(_plano(n)) >= 3]
_GEN = {_plano(g) for g in M.GENERICAS}


def parecido_a_real(nombre):
    candidatos = {_plano(nombre)} | {_plano(p) for p in re.split(r"[\s\-']+", nombre) if len(_plano(p)) >= 4 and _plano(p) not in _GEN}
    for c in candidatos:
        for real in _NEGRA:
            if c == real or (len(real) >= 5 and len(c) >= 5 and difflib.SequenceMatcher(None, c, real).ratio() >= 0.86):
                return real
    return None


def _armar(patron, raiz):
    from generar_televisoras import _armar as armar_tv
    return armar_tv(patron, raiz, 0)


def _persona(rng, pool, usados, apellidos, edad, **extra):
    return {"nombre": _nombre(rng, pool, usados, apellidos), "edad": edad, **extra}


def armar(db):
    pools = _pools(db)
    todos_pool = max(pools.values(), key=lambda p: len(p[0]))
    usados = _prohibidos(db)
    for col, campo in (("televisoras", "equipo"), ("marcas", "dueno")):
        for d in db[col].find({campo: {"$exists": True}}, {campo: 1}):
            v = d[campo]
            for p in ([v["dueno"], *v["comentaristas"]] if col == "televisoras" else [v]):
                usados.add(_norm(p["nombre"]))
    rng = random.Random(SEMILLA)
    pools_raiz = {g: rng.sample(lista, len(lista)) for g, lista in T.RAICES.items()}
    paises = sorted(db["paises"].find({}, {"_id": 0, "id": 1, "nombre": 1, "iso": 1, "confederacion_id": 1}), key=lambda p: p["id"])
    por_conf = {}
    for p in paises:
        por_conf.setdefault(p.get("confederacion_id"), []).append(p["id"])
    # ningún medio se llama igual que una televisora o una marca (se confundirían en la red social)
    nombres = {_plano(x["nombre"]) for col in ("televisoras", "marcas") for x in db[col].find({}, {"nombre": 1})}
    medios, problemas = [], []
    for p in paises:
        grupo = T.GRUPO_POR_ISO.get((p.get("iso") or "").upper())
        if not grupo:
            problemas.append(f"sin idioma: {p['nombre']}")
            continue
        patrones = M.PATRONES[M.PATRONES_GRUPO.get(grupo, grupo)]
        propias = list(T.RAICES_PAIS.get(str(p["id"])) or T.RAICES_PAIS.get((p.get("iso") or "").upper()) or [])
        usadas_raices = set()
        for k, papel in enumerate(M.PAPELES):
            nombre = None
            opciones = patrones[papel][:]
            rng.shuffle(opciones)
            fuente = propias or pools_raiz.get(grupo, [])
            for intento in range(200):
                libres = [r for r in fuente if r not in usadas_raices] or fuente
                if not libres:
                    break
                raiz = libres[intento % len(libres)] if propias else libres[0]
                cand = _armar(opciones[intento % len(opciones)], raiz)
                if not cand or _plano(cand) in nombres or parecido_a_real(cand):
                    if not propias and intento % len(opciones) == len(opciones) - 1:
                        pools_raiz[grupo].append(pools_raiz[grupo].pop(0))
                    continue
                nombre = cand
                break
            if not nombre:
                problemas.append(f"sin nombre: {p['nombre']} / {papel}")
                continue
            if not propias and raiz in pools_raiz.get(grupo, []):
                pools_raiz[grupo].remove(raiz)
            usadas_raices.add(raiz)
            nombres.add(_plano(nombre))
            medios.append(_medio(rng, {"id": p["id"] * 10 + k + 1, "pais_id": p["id"], "pais": p["nombre"], "confederacion_id": p.get("confederacion_id"),
                                       "nombre": nombre, "papel": papel}, pools.get(p["id"]) or todos_pool, usados, 3))
    for mid, nombre, papel, conf in M.INTERNACIONALES:
        origen = rng.choice([x for x in (por_conf.get(conf) or [x["id"] for x in paises]) if x in pools] or list(pools))
        medios.append(_medio(rng, {"id": mid, "pais_id": None, "pais": None, "confederacion_id": conf, "nombre": nombre, "papel": papel}, pools[origen], usados, 4))
    return medios, problemas


def _medio(rng, m, pool, usados, n_periodistas):
    papel = m["papel"]
    linea = rng.choices(list(M.LINEAS_POR_PAPEL[papel]), list(M.LINEAS_POR_PAPEL[papel].values()))[0]
    ap = set()
    director = _persona(rng, pool, usados, ap, rng.randint(46, 72), linea=linea)
    roles = list(M.ROLES) + (["columnista"] if n_periodistas > 3 else [])
    periodistas = []
    for rol in roles:
        estilo = rng.choices(list(M.ESTILOS_POR_ROL[rol]), list(M.ESTILOS_POR_ROL[rol].values()))[0]
        sesgo = rng.choices(list(M.SESGOS), list(M.SESGOS.values()))[0] if m["pais_id"] else "neutral"
        periodistas.append(_persona(rng, pool, usados, ap, rng.randint(25, 62), rol=rol, estilo=estilo,
                                    estilo_nombre=M.ESTILOS[estilo][0], sesgo=sesgo, sesgo_nombre=M.SESGO_NOMBRE[sesgo]))
    nombre_linea, texto = M.LINEAS[linea]
    director.update(rasgo=linea, rasgo_nombre=nombre_linea, rasgo_texto=texto)
    return {**m, "slug": re.sub(r"[^a-z0-9]+", "-", _plano(m["nombre"]) and "".join(c for c in unicodedata.normalize("NFD", m["nombre"].lower()) if unicodedata.category(c) != "Mn")).strip("-"),
            "nivel": M.NIVEL_POR_PAPEL[papel], "linea": linea, "linea_nombre": nombre_linea, "linea_texto": texto,
            "credibilidad": round(rng.uniform(0.45, 0.8), 2), "equipo": {"director": director, "periodistas": periodistas}}


def muestra(n, paises):
    db = _db()
    todo, problemas = armar(db)
    if paises:
        elegidos = [m for m in todo if m["pais"] in paises]
    else:
        visto, elegidos = set(), []
        for m in todo[:: max(1, len(todo) // n)]:
            if m["pais"] not in visto:
                visto.add(m["pais"])
                elegidos.append(m)
        elegidos += [m for m in todo if m["pais_id"] is None][:4]
    for m in elegidos:
        d, ps = m["equipo"]["director"], m["equipo"]["periodistas"]
        print(f"{(m['pais'] or 'Internacional'):<20} {m['nombre']:<28} {m['papel']:<11} línea {m['linea_nombre']}")
        print(f"    director: {d['nombre']} ({d['edad']})")
        print("    periodistas: " + " · ".join(f"{p['nombre']} ({p['rol']}, {p['estilo_nombre']}, {p['sesgo']})" for p in ps))
    print(f"\n{len(todo)} medios, {len({m['nombre'] for m in todo})} nombres distintos, {len(problemas)} problemas {problemas[:5]}")


def aplicar():
    from pymongo import UpdateOne
    db = _db()
    todo, problemas = armar(db)
    if problemas:
        print("NO se aplica, hay problemas:", problemas[:10])
        return
    db["medios"].bulk_write([UpdateOne({"id": m["id"]}, {"$set": m}, upsert=True) for m in todo], ordered=False)
    db["medios"].create_index("id", unique=True)
    print(f"{db['medios'].count_documents({})} medios en 'medios'")


def revertir():
    _db()["medios"].drop()
    print("colección 'medios' borrada")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--muestra", action="store_true")
    ap.add_argument("--aplicar", action="store_true")
    ap.add_argument("--revertir", action="store_true")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--paises", default="")
    a = ap.parse_args()
    if a.muestra:
        muestra(a.n, [x.strip() for x in a.paises.split(",") if x.strip()])
    elif a.aplicar:
        aplicar()
    elif a.revertir:
        revertir()
    else:
        print(__doc__)
