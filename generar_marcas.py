"""
Catálogo de marcas ficticias (config/marcas.py) para los patrocinios de Corporativos: diseña el logo de cada una,
lo valida y carga la colección `marcas`.

Uso (logos: requiere `pip install fonttools brotli`):
    python generar_marcas.py --muestra [carpeta]   # SVGs + hoja HTML de revisión por rubro (no toca nada)
    python generar_marcas.py --subir [carpeta]     # sube marcas/<slug>.svg al bucket
    python generar_marcas.py --aplicar             # carga/actualiza la colección `marcas` (upsert por id)
    python generar_marcas.py --revertir            # borra la colección `marcas`

Determinístico (semilla fija): volver a correrlo da los mismos logos. Cada rubro usa los 8 arquetipos de
logos/componer.py y nunca repite símbolo ni la combinación arquetipo+tipografía; en todo el catálogo no se repite
(arquetipo, símbolo, tipografía). Los nombres se validan contra LISTA_NEGRA (coincidencia y parecido).
Al subir logos nuevos, subir VERSION_IMAGENES['marca'] en services/imagenes_pais_service.py.
"""
import difflib
import os
import random
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict

from config.marcas import ALCANCES, CONFEDERACIONES, GENERICAS, LEMAS, LISTA_NEGRA, MARCAS, PERFILES_MARCA, RUBROS

CARPETA_BUCKET = "gs://com-icg-mundial/marcas"
SEMILLA = 2026
ORDEN_ARQUETIPOS = ["wordmark", "monograma", "lateral", "apilado", "emblema", "sello", "etiqueta", "movimiento"]
PESO_FUENTE = {"playfair": 800, "montserrat": 800, "oswald": 700, "rubik": 700, "teko": 600, "exo_italica": 800,
               "comfortaa": 700, "cinzel": 700}
RUBRO_CORTO = {"indumentaria": "Sportswear", "calzado": "Calzado", "bebidas": "Bebidas", "alimentos": "Alimentos",
               "tecnologia": "Tecnología", "telefonia": "Telecom", "automotriz": "Motors", "banca": "Finanzas",
               "aerolineas": "Viajes", "energia": "Energía", "seguros": "Seguros", "videojuegos": "Games", "lujo": "Atelier"}


def slug(nombre: str) -> str:
    t = unicodedata.normalize("NFKD", nombre.replace("&", " y ")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _plano(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower())


def validar_nombres():
    """Lista de problemas: nombre repetido, o igual/parecido a una marca real."""
    negra = [n for n in LISTA_NEGRA if len(n) >= 3]
    problemas = []
    vistos = Counter(_plano(m[0]) for m in MARCAS)
    problemas += [f"repetido: {n}" for n, c in vistos.items() if c > 1]
    for nombre, *_ in MARCAS:
        candidatos = {_plano(nombre)} | {_plano(p) for p in nombre.split() if len(_plano(p)) >= 4 and _plano(p) not in GENERICAS}
        for c in candidatos:
            for real in negra:
                if c == real or (len(real) >= 4 and difflib.SequenceMatcher(None, c, real).ratio() >= 0.84):
                    problemas.append(f"{nombre!r} se parece a la marca real {real!r}")
    return problemas


def disenar():
    """Lista de marcas con su diseño de logo y sus datos de catálogo (determinístico)."""
    rng = random.Random(SEMILLA)
    por_rubro = defaultdict(list)
    for i, m in enumerate(MARCAS):
        por_rubro[m[1]].append((i, m))
    usados_global = set()
    uso_simbolo = Counter()
    from logos import simbolos
    salida = []
    for rubro, lista in por_rubro.items():
        cfg = RUBROS[rubro]
        arqs = ORDEN_ARQUETIPOS[:]
        rng.shuffle(arqs)
        # los objetos (avión, taza, auto...) solo en el rubro al que pertenecen
        candidatos = [f.__name__ for fam in cfg["familias"] for f in simbolos.SIMBOLOS[fam]
                      if rubro in simbolos.OBJETOS_RUBRO.get(f.__name__, [rubro])]
        rng.shuffle(candidatos)
        simbolos_rubro, combos_rubro, variantes = set(), set(), set()
        uso_fuente = Counter()
        for k, (i, (nombre, _, alcance, region)) in enumerate(lista):
            arq = arqs[k % len(arqs)]
            # símbolo: no repetido en el rubro, el menos usado del catálogo
            libres = [s for s in candidatos if s not in simbolos_rubro] or candidatos
            simb = min(libres, key=lambda s: (uso_simbolo[s], candidatos.index(s)))
            # tipografía: la menos usada del rubro sin repetir arquetipo+tipografía ni la terna global
            fuentes = sorted(cfg["fuentes"], key=lambda f: (uso_fuente[f], rng.random()))
            fte = next((f for f in fuentes if (arq, f) not in combos_rubro and (arq, simb, f) not in usados_global), fuentes[0])
            variante = rng.randrange(12)
            while (arq, variante % 6) in variantes:
                variante += 1
            variantes.add((arq, variante % 6))
            simbolos_rubro.add(simb)
            combos_rubro.add((arq, fte))
            usados_global.add((arq, simb, fte))
            uso_simbolo[simb] += 1
            uso_fuente[fte] += 1
            paleta = cfg["paletas"][k % len(cfg["paletas"])]
            vuelta = k // len(cfg["paletas"])
            if vuelta:
                # otra vuelta por las paletas del rubro: misma familia de color, más clara u oscura (no cambia el matiz)
                from logos.color import mezclar
                paleta = (mezclar(paleta[0], "#ffffff" if k % 2 else "#000000", 0.22 * vuelta), paleta[1])
            caso = rng.choice(["mayus", "titulo", "minus"]) if fte not in ("cinzel", "bebas", "anton", "bungee", "michroma") else "mayus"
            if fte == "pacifico":
                caso = "titulo"
            perfiles = cfg["perfiles"]
            perfil = rng.choices(list(perfiles), weights=list(perfiles.values()))[0]
            salida.append({
                "id": i + 1, "nombre": nombre, "slug": slug(nombre), "rubro": rubro, "alcance": alcance,
                "nivel": ALCANCES[alcance]["nivel"],
                "confederacion_id": region if alcance == "continental" else None,
                "pais": region if alcance == "local" else None,
                "colores": list(paleta), "lema": rng.choice(LEMAS[rubro]), "perfil": perfil,
                "fidelidad": round(rng.uniform(0.3, 0.9), 2),
                "diseno": {"arquetipo": arq, "simbolo": simb, "fuente": fte, "variante": variante, "caso": caso,
                           "espaciado": rng.choice([4, 6, 8]) if caso == "mayus" else rng.choice([0, 1, 2])},
            })
    return sorted(salida, key=lambda m: m["id"])


def svg_de(m: dict) -> str:
    from logos.componer import componer
    dz = m["diseno"]
    d = {"nombre": m["nombre"], "slug": m["slug"], "paleta": tuple(m["colores"]), "arquetipo": dz["arquetipo"],
         "simbolo": dz["simbolo"], "fuente": dz["fuente"], "peso": PESO_FUENTE.get(dz["fuente"], 800),
         "variante": dz["variante"], "caso": dz["caso"], "espaciado": dz["espaciado"], "semilla": m["id"],
         "rubro_corto": RUBRO_CORTO[m["rubro"]]}
    return componer(d)


def muestra(carpeta: str) -> None:
    problemas = validar_nombres()
    for p in problemas:
        print("⚠️ ", p)
    marcas = disenar()
    destino = os.path.join(carpeta, "marcas")
    os.makedirs(destino, exist_ok=True)
    secciones = []
    pesos = []
    for rubro, cfg in RUBROS.items():
        tarjetas = []
        for m in (x for x in marcas if x["rubro"] == rubro):
            svg = svg_de(m)
            pesos.append(len(svg))
            with open(os.path.join(destino, f"{m['slug']}.svg"), "w", encoding="utf-8") as f:
                f.write(svg)
            src = f"marcas/{m['slug']}.svg"
            dz = m["diseno"]
            region = (CONFEDERACIONES.get(m["confederacion_id"]) if m["alcance"] == "continental"
                      else m["pais"] if m["alcance"] == "local" else "")
            tarjetas.append(
                f'<figure><div class="o"><img src="{src}"></div><div class="c"><img src="{src}"></div>'
                f'<div class="chicos"><img src="{src}" style="height:32px"><img src="{src}" style="height:16px"></div>'
                f'<figcaption><b>{m["nombre"]}</b><br><small>{ALCANCES[m["alcance"]]["nombre"]} {region} · '
                f'{dz["arquetipo"]} · {dz["simbolo"]} · {dz["fuente"]} · {len(svg) // 1024 + 1} KB<br>'
                f'«{m["lema"]}» · busca: {PERFILES_MARCA[m["perfil"]].lower()}</small></figcaption></figure>')
        secciones.append(f'<h2>{cfg["nombre"]}</h2><section>{"".join(tarjetas)}</section>')
    with open(os.path.join(carpeta, "marcas.html"), "w", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8"><title>Marcas</title><style>'
                'body{background:#0b1220;color:#e2e8f0;font-family:system-ui,Arial;margin:0;padding:20px}'
                'h2{margin:28px 0 10px;font-size:18px;color:#86efac}'
                'section{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}'
                'figure{margin:0;background:#111a2e;border-radius:12px;padding:10px;display:grid;gap:6px;min-width:0}'
                '.o,.c{height:110px;border-radius:8px;display:flex;align-items:center;justify-content:center;padding:10px;overflow:hidden;min-width:0}'
                '.o{background:#111c2e}.c{background:#e5e7eb}.o img,.c img{width:100%;height:100%;min-width:0;object-fit:contain}'
                '.chicos{display:flex;gap:12px;align-items:center;background:#0b1220;padding:6px;border-radius:6px;overflow:hidden;min-width:0}.chicos img{max-width:60%;object-fit:contain}'
                'small{color:#94a3b8;font-size:11px}</style>'
                f'<p>{len(marcas)} marcas · {len(problemas)} problemas de nombre · peso medio {sum(pesos) // len(pesos) // 1024 + 1} KB</p>'
                + "".join(secciones))
    print(f"{len(marcas)} logos en {destino} (hoja: {carpeta}/marcas.html); problemas de nombre: {len(problemas)}")


def subir(carpeta: str) -> None:
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "marcas", "*.svg"), CARPETA_BUCKET + "/",
                    "--cache-control=public, max-age=604800", "--content-type=image/svg+xml"], check=True)


def _db():
    import certifi
    from pymongo import MongoClient
    from config.settings import MONGODB_URI
    return MongoClient(MONGODB_URI, tlsCAFile=certifi.where())["mundial"]


def aplicar() -> None:
    problemas = validar_nombres()
    if problemas:
        sys.exit("Hay nombres con problemas, corregir config/marcas.py:\n" + "\n".join(problemas))
    from pymongo import ASCENDING, UpdateOne
    db = _db()
    paises = {unicodedata.normalize("NFC", p["nombre"]): p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "confederacion_id": 1})}
    ops = []
    for m in disenar():
        doc = {k: v for k, v in m.items() if k != "pais"}
        if m["alcance"] == "local":
            p = paises.get(unicodedata.normalize("NFC", m["pais"]))
            if not p:
                sys.exit(f"País no encontrado para {m['nombre']}: {m['pais']}")
            doc["pais_id"], doc["confederacion_id"] = p["id"], p.get("confederacion_id")
        else:
            doc["pais_id"] = None
        doc["logo"] = f"marcas/{m['slug']}.svg"
        doc["ficticia"] = True
        ops.append(UpdateOne({"id": m["id"]}, {"$set": doc}, upsert=True))
    r = db["marcas"].bulk_write(ops)
    db["marcas"].create_index([("id", ASCENDING)], unique=True)
    db["marcas"].create_index([("slug", ASCENDING)], unique=True)
    print(f"marcas: {r.upserted_count} nuevas, {r.modified_count} actualizadas ({len(ops)} en total)")


def revertir() -> None:
    db = _db()
    print("marcas borradas:", db["marcas"].delete_many({"ficticia": True}).deleted_count)


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "marcas_muestra"
    if modo == "--muestra":
        muestra(carpeta)
    elif modo == "--subir":
        subir(carpeta)
    elif modo == "--aplicar":
        aplicar()
    elif modo == "--revertir":
        revertir()
    else:
        print(__doc__)
