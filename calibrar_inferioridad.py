"""
Calibración del realismo del partido. SOLO LECTURA: usa el arnés de calibrar_formaciones (lecturas en caché sobre
el motor) y no escribe nada.

    python calibrar_inferioridad.py [N]           # N partidos normales: goles, penales, reparto de goles por línea
    python calibrar_inferioridad.py [N] --diez    # el LOCAL juega todo el partido con 10 (efecto de la inferioridad)

Referencias del fútbol real: con 10 se recibe ~50% más goles y se anota ~30% menos; 0,28-0,36 penales por partido
(~76% convertidos); goles por línea ~50% delanteros, ~30% medios, ~15% defensas.
"""
import random
import statistics
import sys
from collections import Counter

import calibrar_formaciones as CFM   # arnés: lecturas en caché sobre el motor
from services import simular_service as S

DIEZ = "--diez" in sys.argv
if DIEZ:
    sys.argv.remove("--diez")
    _seleccionar = S.seleccionar_plantilla_titular
    _turno = {"n": 0}

    def _con_uno_menos(*a, **k):
        once = _seleccionar(*a, **k)
        _turno["n"] += 1
        if _turno["n"] % 2 == 1:   # la primera llamada de cada partido es la del local
            de_campo = [j for j in once if j.get("linea_partido") != 1]
            once.remove(random.choice(de_campo))
        return once

    S.seleccionar_plantilla_titular = _con_uno_menos

SECTOR = {p["id"]: p.get("sector") for p in CFM._db_real["posiciones"].find({}, {"id": 1, "sector": 1})}
SIGLAS = {p["id"]: p.get("siglas") for p in CFM._db_real["posiciones"].find({}, {"id": 1, "siglas": 1})}
POSICION = {j["id"]: j.get("posicion_id") for j in CFM._db_real["jugadores"].find({}, {"id": 1, "posicion_id": 1})}


def main(n: int) -> None:
    random.seed(91)
    goles, gf_local, gc_local, penales, goles_pen = [], [], [], [], 0
    por_linea, por_puesto, tl_por_linea = Counter(), Counter(), Counter()
    for local, visita in CFM._pares(n, 91):
        p, stats = S.simular_partido_realista(local, visita)
        goles.append(p["goles_local"] + p["goles_visitante"])
        gf_local.append(p["goles_local"])
        gc_local.append(p["goles_visitante"])
        penales.append(sum(1 for e in p["eventos"] if e["tipo"] == "🎯 PENAL"))
        goles_pen += sum(1 for e in p["eventos"] if e["tipo"] == "⚽ GOL" and e.get("de_penal"))
        for jid, st in stats.items():
            if st.get("goles"):
                pos = POSICION.get(jid)
                por_linea[SECTOR.get(pos)] += st["goles"]
                por_puesto[SIGLAS.get(pos)] += st["goles"]
                tl_por_linea[SECTOR.get(pos)] += st.get("goles_tiro_libre", 0)
    ic = 1.96 * statistics.stdev(goles) / n ** 0.5
    print(f"{n} partidos {'(local con 10)' if DIEZ else ''}")
    print(f"goles/partido {statistics.mean(goles):.3f} (±{ic:.3f}) · local anota {statistics.mean(gf_local):.3f} "
          f"(±{1.96 * statistics.stdev(gf_local) / n ** 0.5:.3f}) y recibe {statistics.mean(gc_local):.3f} (±{1.96 * statistics.stdev(gc_local) / n ** 0.5:.3f})")
    print(f"penales {statistics.mean(penales):.3f} por partido · convertidos {100 * goles_pen / max(1, sum(penales)):.0f}%")
    total = sum(por_linea.values()) or 1
    print("goles por línea:", {k: f"{100 * v / total:.0f}%" for k, v in por_linea.most_common()},
          "· de tiro libre:", dict(tl_por_linea))
    print("por puesto:", por_puesto.most_common())


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
