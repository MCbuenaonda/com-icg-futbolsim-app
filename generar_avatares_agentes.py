"""
Avatares ilustrados (SVG plano, busto, fondo transparente) de los 100 agentes (colección 'agentes', generar_agentes.py).

Mismo motor que los dueños de televisora (generar_avatares_tv.AvatarTV, rol 'dueno'): complexión y aspecto salen del rasgo del agente
(`look` en config/agentes.py), la región del país da los rasgos físicos y la ropa lleva los colores de su bandera.
Semilla = 100000 + id (determinístico). Archivos: agentes/<id>.svg.

    python generar_avatares_agentes.py --muestra [carpeta]   # 24 agentes + muestra.html para revisarlos
    python generar_avatares_agentes.py --generar [carpeta]   # todos en <carpeta>/agentes/
    python generar_avatares_agentes.py --subir [carpeta]     # a gs://com-icg-mundial/agentes/
    python generar_avatares_agentes.py --asignar             # escribe agentes.avatar = "agentes/<id>.svg"
"""
import os
import sys

from config import agentes as CA
from generar_avatares import _region
from generar_avatares_tv import AvatarTV


def _datos():
    from services.imagenes_pais_service import db
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "confederacion_id": 1, "colores": 1})}
    return db, paises, list(db["agentes"].find({}, {"_id": 0}).sort("id", 1))


def _colores(pais: dict) -> tuple:
    hexes = [c["hex"] for c in (pais.get("colores") or []) if c.get("hex")]
    hexes = (hexes + ["#1d4ed8", "#facc15"])[:2] if len(hexes) < 2 else hexes[:2]
    return hexes[0], hexes[1]


def avatar(a: dict, paises: dict) -> AvatarTV:
    p = paises[a["pais_id"]]
    return AvatarTV(100000 + a["id"], a["edad"], _region(p), _colores(p), "dueno", CA.RASGOS[a["rasgo"]]["look"])


def muestra(carpeta):
    os.makedirs(carpeta, exist_ok=True)
    _, paises, agentes = _datos()
    celdas = []
    for a in agentes[:: max(1, len(agentes) // 24)][:24]:
        av = avatar(a, paises)
        archivo = f"{a['id']}.svg"
        with open(os.path.join(carpeta, archivo), "w") as f:
            f.write(av.svg())
        celdas.append(f'<figure><img src="{archivo}"><figcaption>{a["nombre"]} · {a["rasgo_nombre"]} · {av.aspecto} · {av.complexion} · {a["edad"]}</figcaption></figure>')
    with open(os.path.join(carpeta, "muestra.html"), "w") as f:
        f.write('<meta charset="utf-8"><body style="background:#111c2e;color:#cbd5e1;font:12px sans-serif;display:grid;grid-template-columns:repeat(6,1fr);gap:8px;padding:8px">'
                + "".join(celdas).replace("<img", '<img style="width:100%;background:#1b2740;border-radius:10px"').replace("<figure>", '<figure style="margin:0">') + "</body>")
    print(f"{len(celdas)} SVG + muestra.html en {carpeta}")


def generar(carpeta):
    destino = os.path.join(carpeta, "agentes")
    os.makedirs(destino, exist_ok=True)
    _, paises, agentes = _datos()
    for a in agentes:
        with open(os.path.join(destino, f"{a['id']}.svg"), "w") as f:
            f.write(avatar(a, paises).svg())
    print(f"{len(agentes)} SVG en {destino}")


def subir(carpeta):
    import subprocess
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "agentes", "*.svg"), "gs://com-icg-mundial/agentes/",
                    "--gzip-local-all", "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def asignar():
    from pymongo import UpdateOne
    db, _, agentes = _datos()
    r = db["agentes"].bulk_write([UpdateOne({"id": a["id"]}, {"$set": {"avatar": f"agentes/{a['id']}.svg"}}) for a in agentes], ordered=False)
    print(f"Agentes con avatar asignado: {r.modified_count}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "avatares_agentes_generados"
    {"--muestra": lambda: muestra(carpeta), "--generar": lambda: generar(carpeta), "--subir": lambda: subir(carpeta),
     "--asignar": asignar}.get(modo, lambda: print(__doc__))()
