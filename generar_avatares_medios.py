"""
Avatares ilustrados (SVG plano, busto, fondo transparente) del director y los periodistas de cada medio ('medios.equipo'). Mismo motor
que los de televisoras y marcas (generar_avatares_tv.AvatarTV: complexión y aspecto):
  - director: el aspecto sale de su línea editorial (la crítica, desaliñado o intelectual; la oficialista, elegante o ejecutivo...),
  - periodistas: el aspecto sale de su estilo (el polemista, rebelde; el analista, intelectual; el entrevistador, elegante...),
con los colores de la línea editorial en la ropa y los rasgos físicos del país del medio. Archivos: medios_equipo/<id>-d.svg y -p1..-p4.svg.

    python generar_avatares_medios.py --muestra [carpeta]   # 24 personas + muestra.html
    python generar_avatares_medios.py --generar [carpeta]   # todas en <carpeta>/medios_equipo/
    python generar_avatares_medios.py --subir [carpeta]     # a gs://com-icg-mundial/medios_equipo/
    python generar_avatares_medios.py --asignar             # escribe equipo.director.avatar y equipo.periodistas[i].avatar
"""
import os
import sys

import generar_avatares_tv as TV
from generar_avatares import _region

LINEA_COLOR = {"sensacionalista": ("#f43f5e", "#fde68a"), "analitica": ("#38bdf8", "#e0f2fe"), "critica": ("#f59e0b", "#fef3c7"), "oficialista": ("#a78bfa", "#ede9fe"),
               "optimista": ("#22c55e", "#dcfce7"), "popular": ("#fb923c", "#ffedd5")}
TV.ASPECTO_DUENO.update({   # director según la línea de su medio (las claves no chocan con las de dueños de TV ni de marcas)
    "sensacionalista": {"rebelde": 4, "relajado": 3, "creativo": 2}, "analitica": {"intelectual": 6, "ejecutivo": 2, "creativo": 2},
    "critica": {"desaliñado": 4, "intelectual": 4, "rebelde": 2}, "oficialista": {"elegante": 5, "ejecutivo": 5}, "optimista": {"relajado": 4, "creativo": 4, "elegante": 2},
    "popular": {"deportivo": 4, "relajado": 4, "rebelde": 2}})
ASPECTO_POR_ESTILO = {"analista": {"intelectual": 5, "ejecutivo": 2, "creativo": 2}, "polemista": {"rebelde": 5, "desaliñado": 3, "relajado": 2},
                      "cronista": {"desaliñado": 3, "creativo": 4, "intelectual": 2}, "entrevistador": {"elegante": 4, "ejecutivo": 3, "relajado": 3},
                      "sensacionalista": {"relajado": 4, "rebelde": 3, "deportivo": 3}, "estadistico": {"intelectual": 5, "ejecutivo": 3, "desaliñado": 2}}
for estilo, pesos in ASPECTO_POR_ESTILO.items():   # reutiliza el sorteo de AvatarTV con una clave propia por estilo
    TV.ASPECTO_DUENO["estilo_" + estilo] = pesos


def _db():
    from services.imagenes_pais_service import db
    return db


def personas():
    db = _db()
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "confederacion_id": 1})}
    todos_paises = sorted(paises)
    for m in db["medios"].find({"equipo": {"$exists": True}}, {"_id": 0, "id": 1, "nombre": 1, "pais_id": 1, "linea": 1, "equipo": 1}).sort("id", 1):
        pais = paises.get(m.get("pais_id")) or paises[todos_paises[m["id"] % len(todos_paises)]]
        colores = LINEA_COLOR[m["linea"]]
        d = m["equipo"]["director"]
        yield m, f"{m['id']}-d.svg", TV.AvatarTV(m["id"] * 10 + 1, d["edad"], _region(pais), colores, "dueno", d["rasgo"])
        for i, p in enumerate(m["equipo"]["periodistas"], 1):
            yield m, f"{m['id']}-p{i}.svg", TV.AvatarTV(m["id"] * 10 + 1 + i, p["edad"], _region(pais), colores, "dueno", "estilo_" + p["estilo"])


def muestra(carpeta):
    os.makedirs(carpeta, exist_ok=True)
    todas = list(personas())
    sel = todas[:: max(1, len(todas) // 24)][:24]
    celdas = []
    for m, archivo, av in sel:
        open(os.path.join(carpeta, archivo), "w").write(av.svg())
        celdas.append(f'<figure style="margin:0"><img style="width:100%;background:#1b2740;border-radius:10px" src="{archivo}"><figcaption>{archivo} · {av.aspecto} · {av.complexion} · {m["linea"]}</figcaption></figure>')
    open(os.path.join(carpeta, "muestra.html"), "w").write('<meta charset="utf-8"><body style="background:#111c2e;color:#cbd5e1;font:12px sans-serif;display:grid;grid-template-columns:repeat(6,1fr);gap:8px;padding:8px">' + "".join(celdas) + "</body>")
    print(f"{len(sel)} SVG + muestra.html en {carpeta}")


def generar(carpeta):
    destino = os.path.join(carpeta, "medios_equipo")
    os.makedirs(destino, exist_ok=True)
    n = 0
    for _, archivo, av in personas():
        open(os.path.join(destino, archivo), "w").write(av.svg())
        n += 1
    print(f"{n} SVG en {destino}")


def subir(carpeta):
    import subprocess
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "medios_equipo", "*.svg"), "gs://com-icg-mundial/medios_equipo/", "--gzip-local-all",
                    "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def asignar():
    from pymongo import UpdateOne
    db = _db()
    ops = []
    for m in db["medios"].find({"equipo": {"$exists": True}}, {"id": 1, "equipo.periodistas": 1}):
        cambios = {"equipo.director.avatar": f"medios_equipo/{m['id']}-d.svg"}
        for i in range(len(m["equipo"]["periodistas"])):
            cambios[f"equipo.periodistas.{i}.avatar"] = f"medios_equipo/{m['id']}-p{i + 1}.svg"
        ops.append(UpdateOne({"id": m["id"]}, {"$set": cambios}))
    r = db["medios"].bulk_write(ops, ordered=False)
    print(f"Medios con avatares asignados: {r.modified_count}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "avatares_medios_generados"
    {"--muestra": lambda: muestra(carpeta), "--generar": lambda: generar(carpeta), "--subir": lambda: subir(carpeta), "--asignar": asignar}.get(modo, lambda: print(__doc__))()
