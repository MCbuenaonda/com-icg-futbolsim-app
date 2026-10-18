"""
Asigna un 'id' numérico PERMANENTE a cada árbitro (la colección solo tenía _id). Lo necesita el
álbum de estampas: los sobres guardan {tipo, id:int} y user_albums.owned_arbitros es una lista de ids.

Solo numera a los que todavía no tienen 'id' (continúa desde el máximo, ordenados por _id): se
puede volver a correr sin renumerar a nadie. restart_mundial no toca 'arbitros'.

    python asignar_id_arbitros.py --muestra    # dry run: cuántos faltan y los primeros ids que tocarían
    python asignar_id_arbitros.py --asignar    # escribe arbitros.id
"""
import sys
from pymongo import UpdateOne
from services.imagenes_pais_service import db


def _pendientes():
    maximo = db["arbitros"].find_one({"id": {"$exists": True}}, sort=[("id", -1)])
    siguiente = (maximo["id"] if maximo else 0) + 1
    sin_id = list(db["arbitros"].find({"id": {"$exists": False}}, {"_id": 1, "nombre": 1}).sort("_id", 1))
    return [(siguiente + i, a) for i, a in enumerate(sin_id)]


def muestra():
    pendientes = _pendientes()
    print(f"Árbitros sin id: {len(pendientes)}")
    for nuevo_id, a in pendientes[:10]:
        print(f"  {nuevo_id:>4}  {a['nombre']}")


def asignar():
    pendientes = _pendientes()
    if not pendientes:
        print("Todos los árbitros ya tienen id.")
        return
    r = db["arbitros"].bulk_write([UpdateOne({"_id": a["_id"], "id": {"$exists": False}}, {"$set": {"id": nuevo_id}})
                                   for nuevo_id, a in pendientes])
    print(f"Árbitros numerados: {r.modified_count} de {len(pendientes)}")


if __name__ == "__main__":
    {"--muestra": muestra, "--asignar": asignar}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
