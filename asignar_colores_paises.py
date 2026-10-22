"""
Guarda en paises.colores los colores REALES de cada bandera (de bandera_plana/<nombre>.png del bucket), ordenados por
área: [{"hex": "#aa151b", "area": 0.5}, ...] (hasta 4, incluye blanco/negro si son parte de la bandera). Lo usa el
motor de arte del Mundial (services/arte_mundial/paleta.py) para el póster y el uniforme de la mascota, así el
servidor no necesita Pillow. Campo PERMANENTE (restart_mundial no lo toca). Idempotente.

    python asignar_colores_paises.py --muestra     # imprime, no escribe
    python asignar_colores_paises.py --aplicar     # escribe paises.colores

Requiere Pillow (solo este script).
"""
import io
import ssl
import sys
import urllib.request
from urllib.parse import quote

import certifi


def colores_de(url: str, maximo: int = 4) -> list:
    from PIL import Image
    contexto = ssl.create_default_context(cafile=certifi.where())
    imagen = Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=20, context=contexto).read())).convert("RGB").resize((80, 60))
    paleta = imagen.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    rgb = paleta.getpalette()
    total = 80 * 60
    salida = []
    for cuenta, i in sorted(paleta.getcolors(), reverse=True):
        c = tuple(rgb[i * 3:i * 3 + 3])
        if cuenta / total < 0.03:
            continue
        # fusiona tonos casi iguales (antialias de los bordes)
        previo = next((s for s in salida if sum(abs(a - b) for a, b in zip(s["rgb"], c)) < 60), None)
        if previo:
            previo["area"] += cuenta / total
            continue
        salida.append({"rgb": c, "area": cuenta / total})
    salida.sort(key=lambda s: -s["area"])
    return [{"hex": "#{:02x}{:02x}{:02x}".format(*s["rgb"]), "area": round(s["area"], 3)} for s in salida[:maximo]]


def main(aplicar: bool) -> None:
    sys.path.insert(0, ".")
    from pymongo import UpdateOne
    from config.settings import IMAGENES_PAISES_URL
    from services.imagenes_pais_service import db
    ops = []
    for p in db["paises"].find({}, {"id": 1, "nombre": 1}).sort("id", 1):
        try:
            cols = colores_de(f"{IMAGENES_PAISES_URL}/bandera_plana/{quote(p['nombre'])}.png")
        except Exception as e:
            print(f"  ⚠️ {p['nombre']}: {e}")
            continue
        print(f"{p['nombre']:28s} " + "  ".join(f"{c['hex']} {c['area']:.0%}" for c in cols))
        ops.append(UpdateOne({"id": p["id"]}, {"$set": {"colores": cols}}))
    if aplicar and ops:
        r = db["paises"].bulk_write(ops, ordered=False)
        print(f"paises.colores: {r.modified_count} actualizados de {len(ops)}")


if __name__ == "__main__":
    main("--aplicar" in sys.argv)
