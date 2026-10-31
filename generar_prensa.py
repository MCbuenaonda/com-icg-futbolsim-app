"""
Publicaciones de prensa de los partidos YA jugados (colección 'prensa'; los nuevos se generan solos al terminar cada partido,
ver services/prensa_service.py). Idempotente: salta los partidos que ya tienen publicaciones.

    python generar_prensa.py --muestra [N]    # imprime la prensa de N partidos recientes, no escribe (por defecto 3)
    python generar_prensa.py --aplicar        # genera la de todos los partidos terminados que no la tienen
    python generar_prensa.py --forzar         # reescribe la de TODOS (si cambiaron textos o reglas)
    python generar_prensa.py --revertir       # borra la colección
"""
import sys

from services import prensa_service as S


def partidos():
    ids = [d["_id"] for d in S.db["juegos"].find({"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}}, {"_id": 1, "fecha": 1, "hora": 1})
           .sort([("fecha", 1), ("hora", 1)]).allow_disk_use(True)]
    for i in ids:   # de a uno: cada partido trae sus ~300 eventos
        yield S.db["juegos"].find_one({"_id": i})


def muestra(n):
    ids = [d["_id"] for d in S.db["juegos"].find({"estado": "finalizado"}, {"_id": 1}).sort("fecha", -1).allow_disk_use(True).limit(max(n * 8, 8))][::8][:n]
    for j in (S.db["juegos"].find_one({"_id": i}) for i in ids):
        r = j["resultado"]
        print(f"\n=== {j['equipo_local']['nombre']} {r['goles_local']}-{r['goles_visitante']} {j['equipo_visitante']['nombre']}")
        for p in S.generar(j):
            print(f"[{p['medio']['nombre']} · {p['medio']['linea']} · {p['rol_cobertura']}] {p['tipo']} {p['tono']:+.2f}: {p['texto']}")


def aplicar(forzar=False):
    n = total = 0
    for j in partidos():
        total += 1
        n += S.asegurar_prensa(j, forzar=forzar)
    S.db[S.COL].create_index("juego_id")
    S.db[S.COL].create_index([("fecha", -1), ("hora", -1)])
    S.db[S.COL].create_index("medio_id")
    print(f"{n} publicaciones nuevas en {total} partidos; la colección tiene {S.db[S.COL].count_documents({})}")
    medias = S.reconstruir_reputacion()   # la reputación se recalcula entera repasando las publicaciones en orden
    print("reputación mediática reconstruida; promedio por tipo:", medias, "(poner en prensa.REP_MEDIA)")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo == "--muestra":
        muestra(int(sys.argv[2]) if len(sys.argv) > 2 else 3)
    elif modo == "--aplicar":
        aplicar()
    elif modo == "--forzar":
        aplicar(True)
    elif modo == "--revertir":
        S.db[S.COL].drop()
        print("colección 'prensa' borrada")
    else:
        print(__doc__)
