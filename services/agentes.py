"""Agentes: lógica pura (sin Mongo). Ver config/agentes.py."""
from typing import Optional

from config import agentes as CA


def calidad_escala(calidad: float) -> float:
    lo, hi = CA.ESCALA_CALIDAD
    return lo + (hi - lo) * max(0.0, min(1.0, calidad))


def efectos(agente: dict, confederacion_representado: Optional[int], comision: Optional[float] = None) -> dict:
    """Lo que el agente aporta a su representado: bono_pago (fracción), encaje (puntos), riesgo (puntos, negativo = baja) y comision."""
    r = CA.RASGOS[agente["rasgo"]]
    cal = calidad_escala(agente.get("calidad", 0.5))
    reg = 1.0 if (confederacion_representado is None or agente.get("confederacion_id") == confederacion_representado) else CA.ESCALA_REGION_AJENA
    riesgo = r["riesgo"] * (cal if r["riesgo"] < 0 else 1.0)
    return {"bono_pago": round(r["bono_pago"] * cal * reg, 4), "encaje": int(round(r["encaje"] * cal * reg)), "riesgo": int(round(riesgo)),
            "comision": float(comision if comision is not None else agente["comision"]), "conoce_region": reg == 1.0}


def comision_con_sinergia(comision: float, tiene_estampa: bool) -> float:
    return max(CA.MIN_COMISION, round(comision - CA.SINERGIA_ALBUM_COMISION, 4)) if tiene_estampa else comision


def aplicar_pago(monto: int, ef: dict) -> tuple:
    """(monto con el bono, comisión del agente) para un cobro de marcas."""
    con_bono = int(round(monto * (1 + ef["bono_pago"])))
    return con_bono, int(round(con_bono * ef["comision"]))


def neto(ef: dict) -> float:
    """Multiplicador neto sobre lo que pagan las marcas (1,00 = igual que sin agente), para mostrar y calibrar."""
    return round((1 + ef["bono_pago"]) * (1 - ef["comision"]), 4)
