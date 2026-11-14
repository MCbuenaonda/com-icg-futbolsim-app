"""Clima económico (lógica pura): estado y multiplicador de cada ciclo de corporativos. Reglas y constantes en config/clima.py. Sin Mongo.

`estado(ciclo)` sale de una cadena de Markov con semilla por ciclo: es reproducible, igual para todos y no se guarda. El próximo ciclo ya se conoce
(aviso previo). `registrar` anota en el ciclo del corporativo lo que se habría ganado sin clima ni crisis y lo que se dejó de ganar (base del seguro).
"""
import random
from typing import Dict, List

from config import clima as CL

_cadena: List[str] = ["normal"]   # _cadena[i] = estado del ciclo i + 1


def estado(ciclo: int) -> str:
    ciclo = max(1, int(ciclo))
    while len(_cadena) < ciclo:
        n = len(_cadena) + 1
        tr = CL.TRANSICIONES[_cadena[-1]]
        _cadena.append(random.Random(f"clima:{n}").choices(list(tr), list(tr.values()))[0])
    return _cadena[ciclo - 1]


def factor(ciclo: int) -> float:
    return CL.FACTOR[estado(ciclo)]


def vista(ciclo: int, adelante: int = 3, atras: int = 5) -> Dict:
    """Para la tarjeta del inicio: estado actual, pronóstico y los últimos ciclos."""
    def fila(c: int) -> dict:
        e = estado(c)
        return {"ciclo": c, "estado": e, "nombre": CL.NOMBRE[e], "factor": CL.FACTOR[e], "pct": round((CL.FACTOR[e] - 1) * 100)}
    return {"actual": fila(ciclo), "pronostico": [fila(ciclo + i) for i in range(1, adelante + 1)],
            "historial": [fila(c) for c in range(max(1, ciclo - atras), ciclo)]}


def aplicar(corp: dict, referencia: float, ciclo: int) -> int:
    """Pago con el clima del ciclo aplicado; deja anotado en el ciclo del corporativo lo asegurable y lo que se dejó de ganar."""
    final = max(1, int(round(referencia * factor(ciclo)))) if referencia > 0 else int(round(referencia))
    registrar(corp, referencia, final)
    return final


def registrar(corp: dict, referencia: float, final: float) -> None:
    """Anota un ingreso para el seguro: `referencia` = lo que habría sido sin recesión ni crisis, `final` = lo realmente cobrado."""
    ca = corp.get("ciclo_actual")
    if ca is None or referencia <= 0:
        return
    ca["asegurable"] = ca.get("asegurable", 0) + referencia
    if final < referencia:
        ca["perdida_clima"] = ca.get("perdida_clima", 0) + (referencia - final)


def prima(asegurable: float) -> int:
    return int(round(asegurable * CL.SEGURO_PRIMA))


def indemnizacion(perdida: float) -> int:
    return int(round(perdida * CL.SEGURO_COBERTURA))
