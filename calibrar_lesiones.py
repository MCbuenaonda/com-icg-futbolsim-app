"""
Calibración de las lesiones (config/lesiones.py). SOLO LECTURA: usa el arnés de calibrar_formaciones (lecturas en
caché sobre el motor) y no escribe nada.

    python calibrar_lesiones.py [N]                 # N partidos (300 por defecto)
    python calibrar_lesiones.py [N] --sin-lesiones  # referencia: mismas semillas sin lesiones (goles por partido)

Mide lesiones por partido (contacto / muscular), cuántas sacan al jugador, cuántas dejan a un equipo con uno menos,
el reparto por gravedad y los goles y tarjetas por partido.
"""
import random
import statistics
import sys
from collections import Counter

import calibrar_formaciones as CFM   # arnés: lecturas en caché sobre el motor
from config import lesiones as CL
from services import simular_service as S

SIN_LESIONES = "--sin-lesiones" in sys.argv
if SIN_LESIONES:
    sys.argv.remove("--sin-lesiones")
    CL.PROB_LESION_FALTA = 0.0
    CL.PROB_MUSCULAR_MINUTO = 0.0


def main(n: int) -> None:
    random.seed(31)
    goles, tarjetas, por_partido = [], [], []
    origen, gravedad, salidas, sin_cambio, minutos = Counter(), Counter(), 0, 0, []
    for local, visita in CFM._pares(n, 53):
        p, _ = S.simular_partido_realista(local, visita)
        goles.append(p["goles_local"] + p["goles_visitante"])
        tarjetas.append(CFM._tarjetas(p))
        les = p.get("lesiones") or []
        por_partido.append(len(les))
        for l in les:
            origen[l["origen"]] += 1
            gravedad[l["gravedad"]] += 1
            minutos.append(l["minuto"])
            salidas += 1 if l["salio"] else 0
        sin_cambio += sum(1 for e in p["eventos"] if e.get("tipo") == "🚑 LESIÓN" and e.get("sin_cambio"))
    total = sum(por_partido) or 1
    print(f"{n} partidos {'SIN lesiones' if SIN_LESIONES else 'con lesiones'}")
    print(f"goles/partido {statistics.mean(goles):.3f} (±{1.96 * statistics.stdev(goles) / n ** 0.5:.3f}) · tarjetas {statistics.mean(tarjetas):.2f}")
    if SIN_LESIONES:
        return
    print(f"lesiones/partido {statistics.mean(por_partido):.3f} · salen {salidas / n:.3f} · con uno menos {sin_cambio / n:.3f}")
    print("origen:", {k: f"{v / n:.3f}" for k, v in origen.items()})
    print("gravedad:", {k: f"{100 * v / total:.0f}%" for k, v in gravedad.items()})
    if minutos:
        print(f"minuto medio {statistics.mean(minutos):.0f} · antes del 45: {100 * sum(m < 45 for m in minutos) / len(minutos):.0f}%")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
