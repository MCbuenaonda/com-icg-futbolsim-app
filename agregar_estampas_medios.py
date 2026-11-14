"""
Catálogo de las estampas de TELEVISIÓN Y MARCAS del álbum: colección 'album_medios' (PERMANENTE; 2.774 documentos).

  categoria LOGO       logo de cada televisora (633) y de cada marca (121)        -> rareza Especial
  categoria PERSONAJE  comentaristas de las televisoras (2 por cadena = 1.266)    -> rareza Normal
  categoria DUENO      dueños de las televisoras (633) y de las marcas (121)      -> rareza Dorada
                       y los 100 AGENTES (origen 'agente', ids 900000+id, página 'agentes') -> rareza Dorada
                       y los 211 PRESIDENTES de federación (origen 'presidente', ids 1000000+país, página 'federaciones') y los 211 LÍDERES de la afición
                       (origen 'lider', ids 1100000+país, página 'penas') -> rareza Dorada

Cada documento: {id, categoria, origen 'televisora'|'marca', ref_id, nombre, detalle, imagen, pais_id, rasgo?, edad?}.
Ids fijos y legibles: 100000+tv (logo tv), 200000+marca (logo marca), 300000+tv*10+n (comentarista n), 400000+tv (dueño tv),
500000+marca (dueño marca). Salen de lo que ya tienen 'televisoras' (equipo) y 'marcas' (dueno); si cambian nombres o
imágenes, volver a correr --aplicar (es idempotente, reemplaza por id).

    python agregar_estampas_medios.py --muestra     # cuenta y ejemplos, no escribe
    python agregar_estampas_medios.py --aplicar     # escribe (upsert por id) y crea el índice único
    python agregar_estampas_medios.py --revertir    # borra la colección
"""
import sys


def _db():
    from services.imagenes_pais_service import db
    return db


CONFEDERACIONES = {1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC"}


def armar(db):
    """Además de la estampa, cada documento lleva dónde va en el álbum: pagina ('tv-uefa'…'tv-afc' | 'marcas'), subgrupo (pestaña:
    confederación de la cadena o rubro de la marca), 'orden' (para ordenar la pestaña) y 'rol_orden' (logo, dueño, comentaristas)."""
    from config.marcas import RUBROS
    docs = _armar(db)
    tv = {t["id"]: t for t in db["televisoras"].find({}, {"_id": 0, "id": 1, "confederacion_id": 1, "pais_id": 1, "nombre": 1})}
    marcas = {m["id"]: m for m in db["marcas"].find({}, {"_id": 0, "id": 1, "rubro": 1, "nombre": 1})}
    nombres_pais = {p["id"]: p["nombre"] for p in db["paises"].find({}, {"id": 1, "nombre": 1})}
    rubros = list(RUBROS)
    for d in docs:
        if d["origen"] in ("medio", "agente", "presidente", "lider"):   # las de prensa y agentes ya traen su página y su orden
            continue
        rol = {"LOGO": 0, "DUENO": 1, "PERSONAJE": 2}[d["categoria"]]
        if d["origen"] == "televisora":
            t = tv[d["ref_id"]]
            conf = t.get("confederacion_id")
            pais = nombres_pais.get(t["pais_id"], "")   # una página por confederación; dentro, una sección por país
            d.update(pagina="tv-" + CONFEDERACIONES.get(conf, "otras").lower(), subgrupo=pais, orden=0,
                     cadena=t["nombre"], pais_nombre=pais, rol_orden=rol)
        else:
            m = marcas[d["ref_id"]]
            d.update(pagina="marcas", subgrupo=RUBROS[m["rubro"]]["nombre"], orden=(rubros.index(m["rubro"]) + 1) * 10 ** 6,
                     cadena=m["nombre"], pais_nombre="", rol_orden=rol)
    return docs


def _armar(db):
    paises = {p["id"]: p["nombre"] for p in db["paises"].find({}, {"id": 1, "nombre": 1})}
    docs = []
    for t in db["televisoras"].find({"equipo": {"$exists": True}}, {"_id": 0}).sort("id", 1):
        pais = paises.get(t["pais_id"])
        docs.append({"id": 100000 + t["id"], "categoria": "LOGO", "origen": "televisora", "ref_id": t["id"], "nombre": t["nombre"],
                     "detalle": f"Televisora · {pais}", "imagen": f"televisoras/{t['slug']}.svg", "pais_id": t["pais_id"]})
        eq = t["equipo"]
        for i, c in enumerate(eq.get("comentaristas") or [], 1):
            docs.append({"id": 300000 + t["id"] * 10 + i, "categoria": "PERSONAJE", "origen": "televisora", "ref_id": t["id"], "nombre": c["nombre"],
                         "detalle": f"Comentarista · {t['nombre']}", "imagen": c.get("avatar"), "pais_id": t["pais_id"], "edad": c.get("edad")})
        d = eq["dueno"]
        docs.append({"id": 400000 + t["id"], "categoria": "DUENO", "origen": "televisora", "ref_id": t["id"], "nombre": d["nombre"],
                     "detalle": f"Dueño · {t['nombre']}", "imagen": d.get("avatar"), "pais_id": t["pais_id"], "edad": d.get("edad"), "rasgo": d.get("rasgo_nombre")})
    for m in db["marcas"].find({}, {"_id": 0}).sort("id", 1):
        pais = m.get("pais_id")
        docs.append({"id": 200000 + m["id"], "categoria": "LOGO", "origen": "marca", "ref_id": m["id"], "nombre": m["nombre"],
                     "detalle": f"Marca · {m.get('rubro')}", "imagen": m.get("logo"), "pais_id": pais})
        d = m.get("dueno")
        if d:
            docs.append({"id": 500000 + m["id"], "categoria": "DUENO", "origen": "marca", "ref_id": m["id"], "nombre": d["nombre"],
                         "detalle": f"Dueño · {m['nombre']}", "imagen": d.get("avatar"), "pais_id": pais, "edad": d.get("edad"), "rasgo": d.get("rasgo_nombre")})
    docs += _armar_prensa(db, paises)
    docs += _armar_agentes(db)
    docs += _armar_directiva(db)
    return docs


def _armar_directiva(db):
    """Estampas de PRESIDENTES de federación y LÍDERES de la afición (Dorada): páginas «Federaciones» y «Peñas», una pestaña por confederación (generar_directiva.py)."""
    from config.directiva import ID_ESTAMPA_LIDER, ID_ESTAMPA_PRESIDENTE
    docs = []
    for col, base, origen, pagina, rol in (("presidentes", ID_ESTAMPA_PRESIDENTE, "presidente", "federaciones", "Presidente"), ("lideres", ID_ESTAMPA_LIDER, "lider", "penas", "Líder de la afición")):
        for x in db[col].find({}, {"_id": 0}).sort("id", 1):
            conf = CONFEDERACIONES.get(x["confederacion_id"], "Otras")
            docs.append({"id": base + x["id"], "categoria": "DUENO", "origen": origen, "ref_id": x["id"], "nombre": x["nombre"], "detalle": f"{rol} · {x['pais_nombre']}",
                         "imagen": x.get("avatar"), "pais_id": x["pais_id"], "edad": x.get("edad"), "rasgo": x.get("rasgo_nombre") + (f" · {x['estilo_nombre']}" if x.get("estilo_nombre") else ""),
                         "pagina": pagina, "subgrupo": conf, "orden": x["confederacion_id"] * 10 ** 6, "cadena": x["pais_nombre"], "pais_nombre": x["pais_nombre"], "rol_orden": 0})
    return docs


def _armar_agentes(db):
    """Estampas de AGENTES (Dorada): una página «Agentes» con una pestaña por confederación (generar_agentes.py)."""
    from config.agentes import ID_ESTAMPA_BASE
    docs = []
    for a in db["agentes"].find({}, {"_id": 0}).sort("id", 1):
        conf = CONFEDERACIONES.get(a["confederacion_id"], "Otras")
        docs.append({"id": ID_ESTAMPA_BASE + a["id"], "categoria": "DUENO", "origen": "agente", "ref_id": a["id"], "nombre": a["nombre"],
                     "detalle": f"Agente · {a['pais_nombre']}", "imagen": a.get("avatar"), "pais_id": a["pais_id"], "edad": a.get("edad"),
                     "rasgo": a.get("rasgo_nombre"), "pagina": "agentes", "subgrupo": conf, "orden": a["confederacion_id"] * 10 ** 6,
                     "cadena": a["nombre"], "pais_nombre": a["pais_nombre"], "rol_orden": 0})
    return docs


def _armar_prensa(db, paises):
    """Estampas de PRENSA: logo de cada medio (Especial), su director (Dorada) y sus periodistas (Normal), en páginas por confederación
    ('prensa-uefa'…; los internacionales, 'prensa-int') con una sección por país."""
    docs = []
    for m in db["medios"].find({"equipo": {"$exists": True}}, {"_id": 0}).sort("id", 1):
        conf = CONFEDERACIONES.get(m.get("confederacion_id")) if m.get("pais_id") else None
        pagina = "prensa-" + (conf.lower() if conf else "int")
        pais = paises.get(m.get("pais_id")) or ("Medios globales" if m["papel"] == "global" else "Medios continentales")
        comun = {"origen": "medio", "ref_id": m["id"], "pais_id": m.get("pais_id"), "pagina": pagina, "subgrupo": pais, "orden": 0, "cadena": m["nombre"], "pais_nombre": pais}
        docs.append({**comun, "id": 600000 + m["id"], "categoria": "LOGO", "nombre": m["nombre"], "detalle": f"Medio · {pais}", "imagen": m.get("logo"), "rol_orden": 0})
        d = m["equipo"]["director"]
        docs.append({**comun, "id": 700000 + m["id"], "categoria": "DUENO", "nombre": d["nombre"], "detalle": f"Director · {m['nombre']}", "imagen": d.get("avatar"),
                     "edad": d.get("edad"), "rasgo": d.get("rasgo_nombre"), "rol_orden": 1})
        for i, p in enumerate(m["equipo"]["periodistas"], 1):
            docs.append({**comun, "id": 800000 + m["id"] * 10 + i, "categoria": "PERSONAJE", "nombre": p["nombre"], "detalle": f"Periodista · {m['nombre']}",
                         "imagen": p.get("avatar"), "edad": p.get("edad"), "rasgo": p.get("estilo_nombre"), "rol_orden": 1 + i})
    return docs


def muestra():
    docs = armar(_db())
    from collections import Counter
    print(len(docs), "estampas", dict(Counter((d["categoria"], d["origen"]) for d in docs)))
    print("ids únicos:", len({d["id"] for d in docs}) == len(docs), "· sin imagen:", sum(1 for d in docs if not d.get("imagen")))
    for d in docs[:3] + docs[-2:]:
        print(" ", d)


def aplicar():
    from pymongo import UpdateOne
    db = _db()
    docs = armar(db)
    db["album_medios"].bulk_write([UpdateOne({"id": d["id"]}, {"$set": d}, upsert=True) for d in docs], ordered=False)
    db["album_medios"].create_index("id", unique=True)
    db["album_medios"].create_index("categoria")
    print(f"{db['album_medios'].count_documents({})} estampas en 'album_medios'")


def revertir():
    _db()["album_medios"].drop()
    print("colección 'album_medios' borrada")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar, "--revertir": revertir}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
