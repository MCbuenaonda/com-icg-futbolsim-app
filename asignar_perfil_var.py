"""
Personalidad de cada árbitro VAR (5to árbitro): dos rasgos permanentes en 'arbitros' (solo puesto "Arbitro VAR").

  - var_intervencion: cuánto revisa. Multiplica la probabilidad de que una jugada pase a revisión
    (0.45 "deja correr" .. 1.8 "intervencionista", promedio ~1.0).
  - var_severidad: cuánto da por malo lo marcado en el campo. Multiplica la probabilidad de revertir una
    jugada revisada (0.6 "respeta al campo" .. 1.4 "implacable", promedio ~1.0).
Los dos se sortean por separado (independientes, promedio 1): el promedio de goles anulados del torneo no cambia,
solo se reparte distinto entre los VAR. El motor los usa en services/arbitraje.py (debe_revisar / revierte).
Determinístico (semilla = nombre); restart_mundial no toca 'arbitros'.

    python asignar_perfil_var.py --muestra    # distribución y ejemplos, sin escribir
    python asignar_perfil_var.py --aplicar    # escribe var_intervencion / var_severidad y sus etiquetas
"""
import math
import random
import statistics
import sys
import zlib

from services import arbitraje

SIGMA_INTERVENCION = 0.32
DESVIO_SEVERIDAD = 0.17


def perfil_para(nombre: str) -> dict:
    r = random.Random(zlib.crc32(f"var|{nombre}".encode()))
    # log-normal con media 1 (la mayoría cerca de 1, algunos muy intervencionistas)
    intervencion = math.exp(r.gauss(-SIGMA_INTERVENCION ** 2 / 2, SIGMA_INTERVENCION))
    intervencion = round(max(arbitraje.VAR_INTERVENCION_MIN, min(arbitraje.VAR_INTERVENCION_MAX, intervencion)), 2)
    severidad = round(max(arbitraje.VAR_SEVERIDAD_MIN, min(arbitraje.VAR_SEVERIDAD_MAX, r.gauss(1.0, DESVIO_SEVERIDAD))), 2)
    return {"var_intervencion": intervencion, "var_severidad": severidad,
            "var_intervencion_etiqueta": arbitraje.etiqueta_intervencion(intervencion),
            "var_severidad_etiqueta": arbitraje.etiqueta_severidad(severidad)}


def _vars():
    from services.imagenes_pais_service import db
    return db, list(db["arbitros"].find({"puesto": arbitraje.PUESTOS["var"]}, {"nombre": 1}))


def muestra():
    _, vars_ = _vars()
    perfiles = [perfil_para(a["nombre"]) for a in vars_]
    i = [p["var_intervencion"] for p in perfiles]
    s = [p["var_severidad"] for p in perfiles]
    print(f"VAR: {len(perfiles)} · intervención media {statistics.mean(i):.3f} ({min(i)}-{max(i)}) · severidad media {statistics.mean(s):.3f} ({min(s)}-{max(s)})")
    print(f"  producto medio (tasa de anulación relativa): {statistics.mean(a * b for a, b in zip(i, s)):.3f}")
    for clave in ("var_intervencion_etiqueta", "var_severidad_etiqueta"):
        etiquetas = [p[clave] for p in perfiles]
        print(" ", clave, {e: etiquetas.count(e) for e in sorted(set(etiquetas))})
    for a, p in list(zip(vars_, perfiles))[:8]:
        print(f"  {a['nombre']:<28} {p['var_intervencion']} {p['var_intervencion_etiqueta']:<18} {p['var_severidad']} {p['var_severidad_etiqueta']}")


def aplicar():
    from pymongo import UpdateOne
    db, vars_ = _vars()
    r = db["arbitros"].bulk_write([UpdateOne({"_id": a["_id"]}, {"$set": perfil_para(a["nombre"])}) for a in vars_])
    print(f"VAR con perfil: {r.matched_count} (modificados {r.modified_count})")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
