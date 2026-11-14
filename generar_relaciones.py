"""Rivalidades y alianzas (services/relaciones_service.py).

    python generar_relaciones.py --muestra     # cuenta y muestra ejemplos SIN escribir
    python generar_relaciones.py --aplicar     # escribe las de marcas, medios y TV (permanentes) y las de selecciones desde lo jugado
    python generar_relaciones.py --revertir    # borra TODAS las relaciones
"""
import collections
import sys

from services import relaciones as R
from services import relaciones_service as RS

db = RS.db


def muestra() -> None:
    from services.corporativo_marcas_service import catalogo
    marcas = list(catalogo().values())
    nom = {m["id"]: m["nombre"] for m in marcas}
    rm = R.relaciones_marcas(marcas)
    print("marcas:", dict(collections.Counter(d["clase"] for d in rm)), "| ej. rivales:", [(nom[d["a"]], nom[d["b"]], d["intensidad"]) for d in sorted((x for x in rm if x["clase"] == "rivalidad"), key=lambda x: -x["intensidad"])[:3]])
    print("medios:", dict(collections.Counter(d["clase"] for d in R.relaciones_medios(list(db["medios"].find({}, {"_id": 0, "id": 1, "pais_id": 1, "linea": 1}))))))
    print("tv:", len(R.relaciones_tv(list(db["televisoras"].find({}, {"_id": 0, "id": 1, "pais_id": 1})))))
    conf = {p["id"]: p.get("confederacion_id") for p in db["paises"].find({}, {"id": 1, "confederacion_id": 1, "nombre": 1})}
    nombres = {p["id"]: p["nombre"] for p in db["paises"].find({}, {"id": 1, "nombre": 1})}
    parejas = set()
    for j in db["juegos"].find({"estado": "finalizado"}, {"equipo_local.id": 1, "equipo_visitante.id": 1}):
        parejas.add(R._par(j["equipo_local"]["id"], j["equipo_visitante"]["id"]))
    res = []
    for a, b in parejas:
        v, m = R.intensidad_seleccion(RS._encuentros(a, b), conf.get(a) is not None and conf.get(a) == conf.get(b))
        res.append((v, a, b, m))
    res.sort(reverse=True)
    clasicos = [r for r in res if r[0] >= 55]; rivalidades = [r for r in res if 35 <= r[0] < 55]
    print(f"selecciones: {len(parejas)} parejas con partidos | clásicos {len(clasicos)} | rivalidades {len(rivalidades)}")
    for v, a, b, m in (clasicos[:5] + rivalidades[:3]):
        print(f"  {nombres[a]} - {nombres[b]}: {v} ({', '.join(m)})")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "--muestra"
    if modo == "--muestra":
        muestra()
    elif modo == "--aplicar":
        print(RS.reconstruir_fijas(), RS.reconstruir_selecciones())
    elif modo == "--revertir":
        print("borradas:", db[RS.COL].delete_many({}).deleted_count)
    else:
        print(__doc__)
