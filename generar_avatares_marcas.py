"""
Avatares ilustrados (SVG plano, busto, fondo transparente) del dueño de cada marca patrocinadora ('marcas.dueno').

Mismo motor que generar_avatares_tv.py (complexión + aspecto). El aspecto sale del rasgo del dueño, los colores de su ropa
(corbata, chamarra, estampado) son los de la marca y los rasgos físicos siguen al país de donde salió su nombre
(generar_dueno_marcas.armar es determinístico: se recalcula el mismo país). Archivos: tv_equipo/m<id>.svg del bucket.

    python generar_avatares_marcas.py --muestra [carpeta]   # 18 dueños + muestra.html
    python generar_avatares_marcas.py --generar [carpeta]   # todos en <carpeta>/tv_equipo/
    python generar_avatares_marcas.py --subir [carpeta]     # a gs://com-icg-mundial/tv_equipo/
    python generar_avatares_marcas.py --asignar             # escribe marcas.dueno.avatar
"""
import os
import sys

import generar_avatares_tv as TV
from generar_avatares import _region
from generar_dueno_marcas import armar

TV.ASPECTO_DUENO.update({   # rasgos del dueño de una marca (los que ya existían, como 'tiburon', se comparten)
    "fundador": {"creativo": 5, "rebelde": 3, "intelectual": 2}, "heredero": {"elegante": 5, "ejecutivo": 4, "intelectual": 2},
    "futbolero": {"deportivo": 6, "relajado": 3, "rebelde": 1}, "austero": {"desaliñado": 4, "intelectual": 4, "ejecutivo": 3},
    "imagen": {"elegante": 5, "ejecutivo": 3, "creativo": 2}, "filantropo": {"relajado": 4, "elegante": 3, "intelectual": 3}})


def _datos():
    from services.imagenes_pais_service import db
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "confederacion_id": 1})}
    colores = {m["id"]: m["colores"] for m in db["marcas"].find({}, {"id": 1, "colores": 1})}
    filas = []
    for m, pais, d in armar(db):
        c = colores[m["id"]]
        filas.append((m, f"m{m['id']}.svg", TV.AvatarTV(900000 + m["id"], d["edad"], _region(paises[pais]), (c[0], c[1]), "dueno", d["rasgo"])))
    return db, filas


def muestra(carpeta):
    os.makedirs(carpeta, exist_ok=True)
    _, filas = _datos()
    celdas = []
    for m, archivo, av in filas[:: max(1, len(filas) // 18)][:18]:
        with open(os.path.join(carpeta, archivo), "w") as f:
            f.write(av.svg())
        celdas.append(f'<figure style="margin:0"><img style="width:100%;background:#1b2740;border-radius:10px" src="{archivo}"><figcaption>{m["nombre"]} · {m["rubro"]} · {av.aspecto} · {av.complexion}</figcaption></figure>')
    with open(os.path.join(carpeta, "muestra.html"), "w") as f:
        f.write('<meta charset="utf-8"><body style="background:#111c2e;color:#cbd5e1;font:12px sans-serif;display:grid;grid-template-columns:repeat(6,1fr);gap:8px;padding:8px">' + "".join(celdas) + "</body>")
    print(f"{len(celdas)} SVG + muestra.html en {carpeta}")


def generar(carpeta):
    destino = os.path.join(carpeta, "tv_equipo")
    os.makedirs(destino, exist_ok=True)
    db, filas = _datos()
    por_id = {m["id"]: m for m in db["marcas"].find({}, {"id": 1, "dueno.nombre": 1})}
    for m, archivo, av in filas:
        with open(os.path.join(destino, archivo), "w") as f:
            f.write(av.svg())
    print(f"{len(filas)} SVG en {destino}")


def subir(carpeta):
    import subprocess
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "tv_equipo", "m*.svg"), "gs://com-icg-mundial/tv_equipo/",
                    "--gzip-local-all", "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def asignar():
    from pymongo import UpdateOne
    from services.imagenes_pais_service import db
    r = db["marcas"].bulk_write([UpdateOne({"id": m["id"]}, {"$set": {"dueno.avatar": f"tv_equipo/m{m['id']}.svg"}}) for m, _, _ in _datos()[1]], ordered=False)
    print(f"Marcas con avatar del dueño: {r.modified_count}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "avatares_marcas_generados"
    {"--muestra": lambda: muestra(carpeta), "--generar": lambda: generar(carpeta), "--subir": lambda: subir(carpeta),
     "--asignar": asignar}.get(modo, lambda: print(__doc__))()
