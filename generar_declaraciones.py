"""Escribe las declaraciones (rueda de prensa) de los partidos ya jugados, en orden cronológico, con las reacciones de la prensa y su
efecto en la reputación mediática (los partidos nuevos las reciben solos al terminar: services/declaraciones_service.py).

    python generar_declaraciones.py --muestra [N]   # imprime ejemplos y estadísticas SIN escribir (default 12)
    python generar_declaraciones.py --aplicar        # escribe las que falten (idempotente: repetirlo no duplica ni infla la reputación)
    python generar_declaraciones.py --revertir       # borra las declaraciones y sus reacciones (no recalcula la reputación)
"""
import collections
import sys

from services import declaraciones_service as DS
from services import prensa_service as PS

db = DS.db


def _partidos():
    return list(db["juegos"].find({"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}}).sort([("fecha", 1), ("hora", 1)]))


def muestra(n: int) -> None:
    dec, tipos, cuenta = [], collections.Counter(), collections.Counter()
    for j in _partidos():
        ctx, lados = DS._contexto_lados(j)
        from services import declaraciones as D
        from services import prensa as P
        ds = D.declaraciones_del_partido(lados, P.semilla("declaraciones", str(j["_id"])))
        cuenta[len(ds)] += 1
        for d in ds:
            tipos[d["tipo"]] += 1
            dec.append((lados[d["lado"]]["eq"], d))
    print("declaraciones por partido:", dict(sorted(cuenta.items())), "| tipos:", dict(tipos))
    paso = max(1, len(dec) // n)
    for eq, d in dec[::paso][:n]:
        print(f"- {eq} · {d['hablante']['nombre']} ({d['tipo']}): «{d['cita']}»")


def aplicar() -> None:
    total = 0
    for j in _partidos():
        total += DS.asegurar_declaraciones(j)
    print(f"Declaraciones escritas o confirmadas: {total}")


def revertir() -> None:
    a = db["declaraciones"].delete_many({}).deleted_count
    b = db[PS.COL].delete_many({"tipo": "REACCION"}).deleted_count
    print(f"Borradas {a} declaraciones y {b} reacciones.")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "--muestra"
    if modo == "--muestra":
        muestra(int(sys.argv[2]) if len(sys.argv) > 2 else 12)
    elif modo == "--aplicar":
        aplicar()
    elif modo == "--revertir":
        revertir()
    else:
        print(__doc__)
