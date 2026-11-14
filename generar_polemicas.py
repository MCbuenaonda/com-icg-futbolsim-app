"""Polémicas arbitrales de los partidos ya jugados (los nuevos se generan solos al terminar: services/polemicas_service.py).

    python generar_polemicas.py --muestra [N]   # cuenta y muestra ejemplos SIN escribir (default 10)
    python generar_polemicas.py --aplicar       # escribe las que falten (idempotente) y deja la reputación al día
    python generar_polemicas.py --revertir      # borra las polémicas y sus notas (la reputación de los árbitros se borra también)
    python generar_polemicas.py --designacion   # solo lectura: con la reputación actual, cómo cambiaría el sorteo del central en eliminación directa
"""
import collections
import statistics
import sys

from config import polemicas as CP
from services import polemicas as PO
from services import polemicas_service as PS_

db = PS_.db


def _partidos():
    return list(db["juegos"].find({"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}}).sort([("fecha", 1), ("hora", 1)]))


def muestra(n: int) -> None:
    por_codigo, con_nota, ejemplos = collections.Counter(), 0, []
    juegos = _partidos()
    for j in juegos:
        items = PO.detectar(PS_._analisis(j))
        if not items:
            continue
        for i in items:
            por_codigo[i["codigo"]] += 1
        if PO.total(items) >= CP.UMBRAL_NOTA:
            con_nota += 1
            h = PS_._analisis(j)
            ejemplos.append(PO.titular(max(items, key=lambda i: i["peso"]), h, __import__("random").Random(1)))
    print(f"{len(juegos)} partidos | jugadas polémicas: {dict(por_codigo)} | partidos con nota de prensa: {con_nota}")
    paso = max(1, len(ejemplos) // n)
    for t in ejemplos[::paso][:n]:
        print("-", t)


def aplicar() -> None:
    # con el número de orden del partido como referencia, la reputación se desgasta como si cada nota hubiera ocurrido en su momento
    hechos = sum(PS_.asegurar_polemicas(j, terminados_ref=i + 1) for i, j in enumerate(_partidos()))
    print(f"Polémicas escritas: {hechos}")


def revertir() -> None:
    a = db[PS_.COL].delete_many({}).deleted_count
    b = db[PS_.PS.COL].delete_many({"tipo": "POLEMICA"}).deleted_count
    c = db[PS_.PS.COL_REP].delete_many({"tipo": "arbitro"}).deleted_count
    print(f"Borradas {a} polémicas, {b} notas y {c} reputaciones de árbitros.")


def designacion() -> None:
    puntajes = PS_.puntajes_centrales()
    centrales = list(db["arbitros"].find({"puesto": "Arbitro central"}, {"id": 1, "rigor": 1, "nombre": 1}))
    sin = [c["rigor"] for c in centrales if c.get("rigor")]
    pesos = [PO.peso_designacion(puntajes.get(c["id"])) for c in centrales]
    pond = sum(c["rigor"] * w for c, w in zip(centrales, pesos) if c.get("rigor")) / sum(w for c, w in zip(centrales, pesos) if c.get("rigor"))
    apart = [c["nombre"] for c in centrales if PO.apartado(puntajes.get(c["id"]))]
    print(f"{len(centrales)} centrales | con reputación: {len(puntajes)} | apartados: {len(apart)} {apart[:5]}")
    print(f"rigor medio del pool: {statistics.mean(sin):.4f} | rigor medio ponderado por reputación: {pond:.4f} (diferencia {pond - statistics.mean(sin):+.4f})")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else "--muestra"
    {"--muestra": lambda: muestra(int(sys.argv[2]) if len(sys.argv) > 2 else 10), "--aplicar": aplicar, "--revertir": revertir, "--designacion": designacion}.get(modo, lambda: print(__doc__))()
