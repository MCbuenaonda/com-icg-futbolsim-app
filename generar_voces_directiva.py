"""
Escribe las voces de la directiva y la tribuna (presidente de la federación y líder de la afición) de los partidos YA JUGADOS, en orden cronológico
(colección `directiva_voces`, services/directiva_service.py). Idempotente: usa el mismo `asegurar_voces` del gancho y no repite lo ya escrito. No cambia
aficionados, DTs ni nada más: los efectos suaves solo rigen desde los partidos nuevos.

    python generar_voces_directiva.py --muestra    # cuántos partidos y voces saldrían, sin escribir
    python generar_voces_directiva.py --aplicar    # escribe
    python generar_voces_directiva.py --revertir   # borra todas las voces
"""
import sys


def _partidos(db):
    return db["juegos"].find({"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}}).sort([("fecha", 1), ("hora", 1)])


def muestra():
    from services import directiva_service as S
    from services.imagenes_pais_service import db
    ya = set(db[S.COL].distinct("juego_id"))
    n = sum(1 for j in _partidos(db) if str(j["_id"]) not in ya)
    print(f"{n} partidos jugados sin voces (de {db['juegos'].count_documents({'estado': 'finalizado'})}); {len(ya)} ya tienen")


def aplicar():
    from services import directiva_service as S
    from services.imagenes_pais_service import db
    ya = set(db[S.COL].distinct("juego_id"))
    partidos = nuevas = 0
    for j in _partidos(db):
        if str(j["_id"]) in ya:
            continue
        nuevas += S.asegurar_voces(j)
        partidos += 1
    print(f"{nuevas} voces en {partidos} partidos; total en la colección: {db[S.COL].count_documents({})}")


def revertir():
    from services import directiva_service as S
    from services.imagenes_pais_service import db
    print(f"{db[S.COL].delete_many({}).deleted_count} voces borradas")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar, "--revertir": revertir}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
