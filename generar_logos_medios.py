"""
Logos (cabeceras) SVG de los 434 medios de comunicación ('medios'), con logos/prensa.py: 4 arquetipos (periodico, bloque, deportivo,
sello), fuente según el tipo de medio (serifa para los generalistas, condensada o itálica para los deportivos) y la paleta de la
bandera del país (los internacionales, la de su línea editorial). Determinístico (semilla = id del medio). Archivos: medios/<slug>.svg.

    python generar_logos_medios.py --muestra [carpeta]   # 24 logos + muestra.html
    python generar_logos_medios.py --generar [carpeta]   # todos en <carpeta>/medios/
    python generar_logos_medios.py --subir [carpeta]     # a gs://com-icg-mundial/medios/
    python generar_logos_medios.py --asignar             # escribe medios.logo (ruta en el bucket)
"""
import os
import random
import sys

from logos import prensa as LP
from logos.texto import fuente
from generar_televisoras import _paleta_pais, _soporta, SOLO_MAYUS

FUENTES = {"generalista": ["playfair", "montserrat", "oswald", "archivo", "rubik", "cinzel"],
           "deportivo": ["anton", "teko", "kanit_italica", "russo", "exo_italica", "bungee", "oswald"],
           "global": ["playfair", "montserrat", "cinzel"], "continental": ["montserrat", "oswald", "playfair"]}
ARQ = {"generalista": ["periodico", "bloque", "sello"], "deportivo": ["deportivo", "bloque", "sello"], "global": ["periodico", "sello"], "continental": ["bloque", "periodico"]}
PESO = {"playfair": 800, "montserrat": 800, "oswald": 700, "rubik": 700, "teko": 600, "exo_italica": 800, "cinzel": 700}
LINEA_COLOR = {"sensacionalista": "#f43f5e", "analitica": "#38bdf8", "critica": "#f59e0b", "oficialista": "#a78bfa", "optimista": "#22c55e", "popular": "#fb923c"}


def _db():
    from services.imagenes_pais_service import db
    return db


def diseno(m, pais):
    rng = random.Random(m["id"] * 7919 + 13)
    paleta = _paleta_pais(pais) if pais else None
    paleta = tuple(paleta) if paleta else (LINEA_COLOR[m["linea"]], "#f8fafc")
    arq = rng.choice(ARQ[m["papel"]])
    caso = rng.choice(["mayus", "titulo", "titulo"])
    for f in rng.sample(FUENTES[m["papel"]], len(FUENTES[m["papel"]])) + ["montserrat", "rubik", "oswald"]:
        c = "mayus" if f in SOLO_MAYUS or f == "cinzel" else caso
        texto = m["nombre"].upper() if c == "mayus" else m["nombre"]
        if _soporta(f, texto + "0123456789"):
            return {"nombre": m["nombre"], "paleta": paleta, "arquetipo": arq if not (arq == "deportivo" and f in ("playfair", "cinzel")) else "bloque",
                    "fuente": f, "peso": PESO.get(f, 800), "caso": c, "espaciado": rng.choice([3, 5]) if c == "mayus" else rng.choice([0, 1])}
    raise RuntimeError(f"sin tipografía para {m['nombre']}")


def _todos():
    db = _db()
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "colores": 1})}
    for m in db["medios"].find({}, {"_id": 0, "id": 1, "slug": 1, "nombre": 1, "papel": 1, "linea": 1, "pais_id": 1}).sort("id", 1):
        yield m, LP.componer(diseno(m, paises.get(m.get("pais_id"))))


def muestra(carpeta):
    os.makedirs(carpeta, exist_ok=True)
    todos = list(_todos())
    sel = todos[:: max(1, len(todos) // 24)][:24]
    for m, svg in sel:
        open(os.path.join(carpeta, f"{m['slug']}.svg"), "w").write(svg)
    html = "".join(f'<figure style="margin:0;background:#111c2e;border-radius:10px;padding:10px"><img style="width:100%;height:70px;object-fit:contain" src="{m["slug"]}.svg"><figcaption style="color:#94a3b8;font:11px sans-serif">{m["papel"]} · {m["nombre"]}</figcaption></figure>' for m, _ in sel)
    open(os.path.join(carpeta, "muestra.html"), "w").write('<meta charset="utf-8"><body style="background:#0b1220;display:grid;grid-template-columns:repeat(4,1fr);gap:10px;padding:10px">' + html + "</body>")
    print(f"{len(sel)} logos en {carpeta}")


def generar(carpeta):
    destino = os.path.join(carpeta, "medios")
    os.makedirs(destino, exist_ok=True)
    n = 0
    for m, svg in _todos():
        open(os.path.join(destino, f"{m['slug']}.svg"), "w").write(svg)
        n += 1
    print(f"{n} logos en {destino}")


def subir(carpeta):
    import subprocess
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "medios", "*.svg"), "gs://com-icg-mundial/medios/", "--gzip-local-all",
                    "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def asignar():
    from pymongo import UpdateOne
    db = _db()
    r = db["medios"].bulk_write([UpdateOne({"id": m["id"]}, {"$set": {"logo": f"medios/{m['slug']}.svg"}}) for m in db["medios"].find({}, {"id": 1, "slug": 1})], ordered=False)
    print(f"Medios con logo: {r.modified_count}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "logos_medios_generados"
    {"--muestra": lambda: muestra(carpeta), "--generar": lambda: generar(carpeta), "--subir": lambda: subir(carpeta), "--asignar": asignar}.get(modo, lambda: print(__doc__))()
