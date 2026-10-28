"""
Ilustraciones de estadios v2: 50 conceptos de clase mundial (estadios/catalogo.py) dibujados en línea técnica 3/4 con la
paleta REAL de la bandera de cada país (paises.colores → estadios/color.py). Ver CLAUDE.md («Ilustraciones de estadios»).

Reglas de asignación (determinísticas, semilla = pais_id):
  - dentro de un país no se repite ningún diseño (con más de 50 ciudades —Yibuti— se usa una VARIANTE: vista espejada y
    paleta invertida, así tampoco se repite ninguna imagen);
  - los conceptos culturales tienen más probabilidad donde encajan (regiones de generar_avatares.REGION_POR_PAIS y países
    costeros/insulares); los demás, al azar.
Un SVG por ciudad: estadios_v2/p<pais_id>-<codigo>[-b].svg en el bucket.

Uso (en este orden):
    python generar_estadios.py --muestra [carpeta]   # los 50 con 5 paletas de ejemplo + muestra.html (solo lee Mongo)
    python generar_estadios.py --generar [carpeta]   # un SVG por ciudad en <carpeta>/estadios_v2/
    python generar_estadios.py --subir [carpeta]     # sube a gs://com-icg-mundial/estadios_v2/ (NO borra estadios/)
    python generar_estadios.py --asignar             # respalda y escribe ciudades.estadio_imagen
    python generar_estadios.py --verificar           # sin repetidos por país, todos con imagen, reparto
    python generar_estadios.py --revertir            # vuelve al respaldo más reciente (los SVG viejos siguen en estadios/)
"""
import glob
import hashlib
import json
import math
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime

from estadios import catalogo as C
from estadios import color as COL

CARPETA_BUCKET = "gs://com-icg-mundial/estadios_v2"
CARPETA_RESPALDOS = "respaldos"
MUESTRA_PAISES = ["México", "Brasil", "Japón", "Marruecos", "Países Bajos"]

# Preferencias: peso del concepto en el sorteo del país
PESO_REGION = 4.0          # concepto cultural en su región
PESO_FUERA_REGION = 0.5    # concepto cultural lejos de su región
PESO_COSTERO = 3.0         # concepto marino en un país costero o insular
COSTEROS_EXTRA = {"Portugal", "España", "Italia", "Grecia", "Noruega", "Japón", "Chile", "Perú", "Brasil", "Australia",
                  "Nueva Zelanda", "Islandia", "Islas Feroe", "Malta", "Chipre", "Irlanda", "Escocia", "Inglaterra", "Gales",
                  "Uruguay", "Ecuador", "Colombia", "Venezuela", "Panamá", "Costa Rica", "Senegal", "Cabo Verde",
                  "Mauricio", "Seychelles", "Madagascar", "Comoras", "Santo Tomé y Príncipe", "Sri Lanka", "Maldivas",
                  "Filipinas", "Indonesia", "Singapur", "Croacia", "Montenegro", "Dinamarca", "Países Bajos", "Bélgica"}


def _db():
    from services.imagenes_pais_service import db
    return db


def _region(nombre: str):
    try:
        from generar_avatares import REGION_POR_PAIS
        return REGION_POR_PAIS.get(nombre)
    except Exception:
        return None


def _costero(nombre: str, region) -> bool:
    return nombre in COSTEROS_EXTRA or region in ("caribe", "caribe_hispano", "pacifico", "asia_sudeste")


def orden_conceptos(pais_id: int, nombre: str) -> list:
    """Los 50 códigos en el orden del país: sorteo ponderado sin reposición (Efraimidis-Spirakis), semilla = pais_id."""
    rng = random.Random(f"estadios:{pais_id}")
    region = _region(nombre)
    costero = _costero(nombre, region)
    claves = []
    for c in C.CONCEPTOS:
        w = 1.0
        if c["regiones"]:
            w = PESO_REGION if region in c["regiones"] else PESO_FUERA_REGION
        if c["costero"]:
            w = max(w, PESO_COSTERO if costero else 0.7)
        claves.append((rng.random() ** (1.0 / w), c["codigo"]))
    return [cod for _, cod in sorted(claves, reverse=True)]


def nombre_archivo(pais_id: int, codigo: str, variante: int) -> str:
    return f"estadios_v2/p{pais_id}-{codigo}{'-b' if variante else ''}.svg"


def asignacion() -> dict:
    """{ciudad_id: {pais_id, codigo, variante, imagen}} para todas las ciudades (determinístico)."""
    db = _db()
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "colores": 1})}
    por_pais = defaultdict(list)
    for c in db["ciudades"].find({}, {"id": 1, "pais_id": 1}).sort("id", 1):
        por_pais[c["pais_id"]].append(c["id"])
    salida = {}
    for pais_id, ids in por_pais.items():
        orden = orden_conceptos(pais_id, (paises.get(pais_id) or {}).get("nombre", ""))
        for k, ciudad_id in enumerate(ids):
            codigo, variante = orden[k % len(orden)], k // len(orden)
            salida[ciudad_id] = {"pais_id": pais_id, "codigo": codigo, "variante": variante,
                                 "imagen": nombre_archivo(pais_id, codigo, variante)}
    return salida


def _semilla(pais_id, codigo, variante) -> int:
    return int(hashlib.md5(f"{pais_id}:{codigo}:{variante}".encode()).hexdigest()[:8], 16)


def dibujar(pais: dict, codigo: str, variante: int = 0) -> str:
    paleta = COL.paleta(pais.get("colores") or [])
    if variante:
        paleta = COL.invertir(paleta)
    return C.dibujar(C.POR_CODIGO[codigo], paleta, semilla=_semilla(pais.get("id"), codigo, variante), espejo=bool(variante))


# --------------------------------------------------------------------------------------------------- modos
def muestra(carpeta: str):
    db = _db()
    os.makedirs(carpeta, exist_ok=True)
    paises = [p for n in MUESTRA_PAISES for p in [db["paises"].find_one({"nombre": n}, {"id": 1, "nombre": 1, "colores": 1})] if p]
    for p in paises:
        sub = os.path.join(carpeta, str(p["id"]))
        os.makedirs(sub, exist_ok=True)
        for i, c in enumerate(C.CONCEPTOS):
            with open(os.path.join(sub, f"{i + 1:02d}.svg"), "w") as f:
                f.write(dibujar(p, c["codigo"]))
    botones = "".join(f'<button data-p="{p["id"]}">{p["nombre"]}</button>' for p in paises)
    figuras = "".join(f'<figure><img data-n="{i + 1:02d}" alt=""><figcaption><b>{i + 1}.</b> {c["nombre"]}<small>{C.GRUPOS[c["grupo"]]}</small></figcaption></figure>'
                      for i, c in enumerate(C.CONCEPTOS))
    html = f"""<!doctype html><html lang="es"><meta charset="utf-8"><title>Estadios: 50 conceptos</title>
<style>body{{background:#0b1220;color:#cbd5e1;font-family:system-ui,sans-serif;margin:0;padding:16px}}
h1{{font-size:20px;margin:0 0 8px}} .barra{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}}
button{{background:#111c2e;color:#e2e8f0;border:1px solid #334155;border-radius:999px;padding:6px 14px;cursor:pointer}}
button.on{{border-color:#22c55e;background:#14532d}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}}
figure{{margin:0;background:#111c2e;border-radius:10px;padding:6px}} img{{width:100%;display:block}}
figcaption{{font-size:13px;padding:4px}} small{{display:block;color:#64748b}}</style>
<h1>Estadios: 50 conceptos con la paleta de cada país</h1><div class="barra">{botones}</div><div class="grid">{figuras}</div>
<script>const bs=[...document.querySelectorAll('button')];function ver(p){{bs.forEach(b=>b.classList.toggle('on',b.dataset.p==p));
document.querySelectorAll('img').forEach(i=>i.src=p+'/'+i.dataset.n+'.svg')}}bs.forEach(b=>b.onclick=()=>ver(b.dataset.p));ver(bs[0].dataset.p);</script></html>"""
    with open(os.path.join(carpeta, "muestra.html"), "w") as f:
        f.write(html)
    print(f"{len(C.CONCEPTOS)} conceptos × {len(paises)} paletas en {carpeta}/ — abre {carpeta}/muestra.html")


def generar(carpeta: str):
    db = _db()
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "colores": 1})}
    os.makedirs(os.path.join(carpeta, "estadios_v2"), exist_ok=True)
    hechos, pesos = set(), []
    for a in asignacion().values():
        if a["imagen"] in hechos:
            continue
        svg = dibujar(paises.get(a["pais_id"], {"id": a["pais_id"]}), a["codigo"], a["variante"])
        with open(os.path.join(carpeta, a["imagen"]), "w") as f:
            f.write(svg)
        hechos.add(a["imagen"])
        pesos.append(len(svg))
    print(f"{len(hechos)} SVG en {carpeta}/estadios_v2/ · peso medio {sum(pesos) / len(pesos) / 1024:.1f} KB · máximo {max(pesos) / 1024:.1f} KB")


def subir(carpeta: str):
    import subprocess
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "estadios_v2", "*.svg"), f"{CARPETA_BUCKET}/",
                    "--gzip-local-all", "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def asignar():
    from pymongo import UpdateOne
    db = _db()
    os.makedirs(CARPETA_RESPALDOS, exist_ok=True)
    respaldo = {str(c["id"]): c.get("estadio_imagen") for c in db["ciudades"].find({}, {"id": 1, "estadio_imagen": 1})}
    ruta = os.path.join(CARPETA_RESPALDOS, f"estadios_imagen_{datetime.now():%Y%m%d_%H%M%S}.json")
    with open(ruta, "w") as f:
        json.dump(respaldo, f)
    ops = [UpdateOne({"id": cid}, {"$set": {"estadio_imagen": a["imagen"]}}) for cid, a in asignacion().items()]
    r = db["ciudades"].bulk_write(ops, ordered=False)
    print(f"{r.modified_count} ciudades actualizadas de {len(ops)} (respaldo en {ruta})")


def revertir():
    from pymongo import UpdateOne
    archivos = sorted(glob.glob(os.path.join(CARPETA_RESPALDOS, "estadios_imagen_*.json")))
    if not archivos:
        sys.exit("No hay respaldo")
    with open(archivos[-1]) as f:
        respaldo = json.load(f)
    ops = [UpdateOne({"id": int(cid)}, {"$set": {"estadio_imagen": img}} if img else {"$unset": {"estadio_imagen": ""}}) for cid, img in respaldo.items()]
    r = _db()["ciudades"].bulk_write(ops, ordered=False)
    print(f"Revertido desde {archivos[-1]}: {r.modified_count} ciudades")


def verificar():
    asig = asignacion()
    por_pais = defaultdict(list)
    for a in asig.values():
        por_pais[a["pais_id"]].append((a["codigo"], a["variante"]))
    repetidos = {p: [x for x, n in Counter(v).items() if n > 1] for p, v in por_pais.items()}
    repetidos = {p: v for p, v in repetidos.items() if v}
    sin_imagen = _db()["ciudades"].count_documents({"estadio_imagen": {"$exists": False}})
    uso = Counter(a["codigo"] for a in asig.values())
    print(f"ciudades {len(asig)} · países {len(por_pais)} · países con imagen repetida: {len(repetidos)} · ciudades sin imagen en Mongo: {sin_imagen}")
    print(f"variantes (más de 50 ciudades): {sum(1 for a in asig.values() if a['variante'])}")
    print(f"uso por concepto: mín {min(uso.values())} · máx {max(uso.values())}")
    db = _db()
    nombres = {p["id"]: p["nombre"] for p in db["paises"].find({}, {"id": 1, "nombre": 1})}
    for cod in ("carpa_nomada", "cuenco_prehispanico", "vela_barco", "abanico"):
        en_region = Counter(_region(nombres.get(a["pais_id"], "")) for a in asig.values() if a["codigo"] == cod)
        print(f"  {cod}: {dict(en_region.most_common(4))}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "estadios_generados"
    acciones = {"--muestra": lambda: muestra(carpeta), "--generar": lambda: generar(carpeta), "--subir": lambda: subir(carpeta),
                "--asignar": asignar, "--revertir": revertir, "--verificar": verificar}
    acciones.get(modo, lambda: print(__doc__))()
