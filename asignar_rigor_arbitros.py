"""
Asigna el RIGOR (personalidad) de cada árbitro central: campo permanente 'arbitros.rigor' (0.75 permisivo ..
1.30 estricto, promedio ~1.0) + 'rigor_etiqueta'. El motor (simular_service) multiplica por el rigor la
probabilidad de tarjeta y, en menor medida, la de cobrar falta (services/arbitraje.py). Determinístico: la semilla
es el nombre, así que volver a correrlo da lo mismo. restart_mundial no toca 'arbitros'.

    python asignar_rigor_arbitros.py --muestra    # distribución y ejemplos, sin escribir
    python asignar_rigor_arbitros.py --aplicar    # escribe arbitros.rigor / rigor_etiqueta en los centrales
"""
import random
import statistics
import sys
import zlib

from services import arbitraje

DESVIO = 0.14


def rigor_para(nombre: str) -> float:
    r = random.Random(zlib.crc32(f"rigor|{nombre}".encode()))
    return round(max(arbitraje.RIGOR_MIN, min(arbitraje.RIGOR_MAX, r.gauss(1.0, DESVIO))), 2)


def _centrales():
    from services.imagenes_pais_service import db
    return db, list(db["arbitros"].find({"puesto": arbitraje.PUESTOS["central"]}, {"nombre": 1}))


def muestra():
    _, centrales = _centrales()
    valores = [rigor_para(a["nombre"]) for a in centrales]
    etiquetas = [arbitraje.etiqueta_rigor(v) for v in valores]
    print(f"Centrales: {len(valores)} · promedio {statistics.mean(valores):.3f} · min {min(valores)} · max {max(valores)}")
    print({e: etiquetas.count(e) for e in ("permisivo", "normal", "estricto")})
    for a, v in list(zip(centrales, valores))[:8]:
        print(f"  {a['nombre']:<28} {v}  {arbitraje.etiqueta_rigor(v)}")


def aplicar():
    from pymongo import UpdateOne
    db, centrales = _centrales()
    ops = [UpdateOne({"_id": a["_id"]}, {"$set": {"rigor": rigor_para(a["nombre"]),
                                                  "rigor_etiqueta": arbitraje.etiqueta_rigor(rigor_para(a["nombre"]))}})
           for a in centrales]
    r = db["arbitros"].bulk_write(ops)
    print(f"Centrales con rigor: {r.matched_count} (modificados {r.modified_count})")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
