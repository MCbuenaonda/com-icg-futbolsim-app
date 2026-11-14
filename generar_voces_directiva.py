"""
Escribe las voces de la directiva y la tribuna (presidente de la federación y líder de la afición) de los partidos YA JUGADOS, en orden cronológico
(colección `directiva_voces`, services/directiva_service.py). Idempotente: usa el mismo `asegurar_voces` del gancho y no repite lo ya escrito. No cambia
aficionados, DTs ni nada más: los efectos suaves solo rigen desde los partidos nuevos.

    python generar_voces_directiva.py --muestra     # cuántos partidos y voces saldrían, sin escribir
    python generar_voces_directiva.py --aplicar     # escribe las voces que faltan (y sus reacciones de la prensa)
    python generar_voces_directiva.py --reacciones  # escribe las reacciones de la prensa a las voces que ya existen y RECONSTRUYE la reputación mediática
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


def reacciones():
    """Las voces ya escritas todavía no tienen reacciones de la prensa: se escriben en orden cronológico SIN tocar la reputación y al final se reconstruye
    TODA la reputación mediática (como generar_prensa.py): aplicar partidos viejos de golpe sobre el puntaje de hoy lo desgastaría."""
    from services import directiva_service as S
    from services import prensa_service as PS
    from services.imagenes_pais_service import db
    antes = db[PS.COL].count_documents({"tipo": "REACCION", "voz_id": {"$exists": True}})
    for j in _partidos(db):
        S.asegurar_voces(j, reputacion=False)
    despues = db[PS.COL].count_documents({"tipo": "REACCION", "voz_id": {"$exists": True}})
    print(f"{despues - antes} reacciones nuevas ({despues} en total); reconstruyendo la reputación mediática…")
    print("promedio por tipo:", PS.reconstruir_reputacion())


def revertir():
    from services import directiva_service as S
    from services.imagenes_pais_service import db
    from services import prensa_service as PS
    print(f"{db[S.COL].delete_many({}).deleted_count} voces borradas y {db[PS.COL].delete_many({'voz_id': {'$exists': True}}).deleted_count} reacciones (reconstruye la reputación con --reacciones o generar_prensa.py)")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar, "--reacciones": reacciones, "--revertir": revertir}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
