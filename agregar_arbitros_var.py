"""
Agrega el 5to árbitro (VAR) a la colección 'arbitros': 210 árbitros nuevos, uno por país (el mismo
reparto de los otros 4 puestos: Islas Feroe no tiene árbitros), con nombres inventados por país en
arbitros_var.json. Revisa las jugadas que pide el 4to árbitro y decide si lo marcado en el campo es
bueno o no (ver services/arbitraje.py y simular_service.py).

Mismos campos que los existentes: nombre, pais, pais_id, puesto ("Arbitro VAR"), genero, id numérico
(sigue al máximo actual, como asignar_id_arbitros.py) y avatar_imagen ("arbitros/<_id>.svg", el SVG lo
generan y suben generar_avatares_arbitros.py --generar / --subir). Marca 'origen: "var_generado"' para
poder revertir.

    python agregar_arbitros_var.py --muestra     # valida (210 países distintos, nombres únicos) sin escribir
    python agregar_arbitros_var.py --aplicar     # inserta (idempotente: no duplica si ya están)
    python agregar_arbitros_var.py --revertir    # borra los insertados y sus estampas del álbum
"""
import json
import os
import sys

from services.imagenes_pais_service import db

RAIZ = os.path.dirname(os.path.abspath(__file__))
PUESTO = "Arbitro VAR"
ORIGEN = "var_generado"


def _cargar():
    with open(os.path.join(RAIZ, "arbitros_var.json"), encoding="utf-8") as f:
        return json.load(f)["arbitros"]


def _validar(filas):
    paises = {p["nombre"]: p["id"] for p in db["paises"].find({}, {"nombre": 1, "id": 1})}
    existentes = {a["nombre"] for a in db["arbitros"].find({"origen": {"$ne": ORIGEN}}, {"nombre": 1})}
    errores = []
    vistos_pais, vistos_nombre = set(), set()
    for a in filas:
        if a["pais"] not in paises:
            errores.append(f"País desconocido: {a['pais']}")
        if a["pais"] in vistos_pais:
            errores.append(f"País repetido: {a['pais']}")
        if a["nombre"] in existentes or a["nombre"] in vistos_nombre:
            errores.append(f"Nombre repetido: {a['nombre']}")
        if a.get("genero") not in ("F", "M"):
            errores.append(f"Género inválido: {a['nombre']}")
        vistos_pais.add(a["pais"])
        vistos_nombre.add(a["nombre"])
    sin_var = sorted(set(paises) - vistos_pais)
    return paises, errores, sin_var


def muestra():
    filas = _cargar()
    _, errores, sin_var = _validar(filas)
    print(f"Árbitros VAR: {len(filas)} ({sum(a['genero'] == 'F' for a in filas)} árbitras) · países sin VAR: {sin_var}")
    print("Errores:" if errores else "Sin errores.", *errores, sep="\n  ")
    ya = db["arbitros"].count_documents({"puesto": PUESTO})
    print(f"Ya insertados: {ya}")
    for a in filas[:12]:
        print(f"  {a['pais']:<24} {a['nombre']} ({a['genero']})")


def aplicar():
    filas = _cargar()
    paises, errores, _ = _validar(filas)
    if errores:
        sys.exit("No se aplica: " + "; ".join(errores))
    ya = {a["nombre"] for a in db["arbitros"].find({"puesto": PUESTO}, {"nombre": 1})}
    maximo = db["arbitros"].find_one({"id": {"$exists": True}}, sort=[("id", -1)])
    siguiente = (maximo["id"] if maximo else 0) + 1
    nuevos = []
    for a in filas:
        if a["nombre"] in ya:
            continue
        nuevos.append({"nombre": a["nombre"], "pais": a["pais"], "pais_id": paises[a["pais"]], "puesto": PUESTO,
                       "genero": a["genero"], "id": siguiente + len(nuevos), "origen": ORIGEN})
    if not nuevos:
        print("Los árbitros VAR ya estaban cargados.")
        return
    r = db["arbitros"].insert_many(nuevos)
    for _id in r.inserted_ids:
        db["arbitros"].update_one({"_id": _id}, {"$set": {"avatar_imagen": f"arbitros/{_id}.svg"}})
    print(f"Insertados {len(r.inserted_ids)} árbitros VAR (ids {nuevos[0]['id']}-{nuevos[-1]['id']}).")
    print("Siguiente paso: generar_avatares_arbitros.py --generar, --subir y --asignar.")


def revertir():
    ids = [a["id"] for a in db["arbitros"].find({"origen": ORIGEN}, {"id": 1})]
    if not ids:
        print("No hay árbitros VAR generados.")
        return
    r_album = db["user_albums"].update_many({"owned_arbitros": {"$in": ids}}, {"$pull": {"owned_arbitros": {"$in": ids}}})
    r = db["arbitros"].delete_many({"origen": ORIGEN})
    print(f"Borrados {r.deleted_count} árbitros VAR; álbumes ajustados: {r_album.modified_count}.")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar, "--revertir": revertir}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
