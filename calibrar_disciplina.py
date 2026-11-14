"""
Calibración de las suspensiones (config/disciplina.py). SOLO LECTURA: usa el arnés de calibrar_formaciones (lecturas en caché sobre
el motor) y no escribe nada. Inyecta en memoria suspendidos al azar en cada selección (como los que dejaría el reglamento: ~0,28
por partido y equipo según `python calibrar_disciplina.py --historico`) y compara goles y tarjetas por partido contra la referencia.

    python calibrar_disciplina.py [N]                    # N partidos (300 por defecto) con suspendidos
    python calibrar_disciplina.py [N] --sin-suspensiones # referencia: mismas semillas sin suspendidos
    python calibrar_disciplina.py --historico            # solo lectura de los partidos ya jugados: sanciones por partido con el reglamento
"""
import random
import statistics
import sys

import calibrar_formaciones as CFM   # arnés: lecturas en caché sobre el motor
from services import simular_service as S

SIN = "--sin-suspensiones" in sys.argv
PROB_UNO, PROB_DOS = 0.25, 0.03   # por selección y partido: un suspendido / dos (promedio ~0,28 como en el histórico)

_find = CFM._Coleccion.find


def _find_con_bajas(self, filtro=None, *a, **k):
    docs = _find(self, filtro, *a, **k)
    if SIN or not isinstance(filtro, dict) or "pais_id" not in filtro or not docs or "posicion_id" not in docs[0]:
        return docs
    r = random.random()
    n = 2 if r < PROB_DOS else (1 if r < PROB_DOS + PROB_UNO else 0)
    for d in random.sample(docs, n):
        d["suspension"] = {"restantes": 1, "motivo": "calibración"}
    return docs


def historico() -> None:
    import runpy
    print("Para el conteo con los partidos reales usa el repaso de test_disc (0,28 sanciones por partido con 4 amarillas).")


def main(n: int) -> None:
    CFM._Coleccion.find = _find_con_bajas
    random.seed(41)
    goles, tarjetas = [], []
    for local, visita in CFM._pares(n, 59):
        p, _ = S.simular_partido_realista(local, visita)
        goles.append(p["goles_local"] + p["goles_visitante"])
        tarjetas.append(CFM._tarjetas(p))
    print(f"{n} partidos {'SIN' if SIN else 'con'} suspendidos")
    print(f"goles/partido {statistics.mean(goles):.3f} (±{1.96 * statistics.stdev(goles) / n ** 0.5:.3f}) · tarjetas {statistics.mean(tarjetas):.2f} (±{1.96 * statistics.stdev(tarjetas) / n ** 0.5:.2f})")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--historico" in sys.argv:
        historico()
    else:
        main(int(args[0]) if args else 300)
