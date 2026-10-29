"""
Lesiones durante el partido: lógica pura (sin base de datos). La usa simular_service; el catálogo y las
probabilidades viven en config/lesiones.py y la persistencia (bajas para los partidos siguientes) en
services/lesiones_service.py.
"""
import random as _random

from config import lesiones as CL


def prob_por_falta(agresividad_infractor: float, roja: bool = False) -> float:
    """Probabilidad de que la víctima de una falta se lesione."""
    factor = max(0.5, float(agresividad_infractor or CL.AGRESIVIDAD_REFERENCIA) / CL.AGRESIVIDAD_REFERENCIA)
    return CL.PROB_LESION_FALTA * factor * (CL.FACTOR_ROJA_DIRECTA if roja else 1.0)


def prob_muscular(energia: float, edad, segundos: float) -> float:
    """Probabilidad de una lesión muscular en 'segundos' de juego con esa energía."""
    if energia >= CL.UMBRAL_MUSCULAR or segundos <= 0:
        return 0.0
    falta = (CL.UMBRAL_MUSCULAR - max(0.0, energia)) / CL.UMBRAL_MUSCULAR
    riesgo_edad = 1.0 + max(0, (int(edad or 0) - CL.EDAD_RIESGO)) * CL.RIESGO_POR_ANIO
    return CL.PROB_MUSCULAR_MINUTO * falta * riesgo_edad * segundos / 60.0


def sortear(origen: str, rng=_random) -> dict:
    """{codigo, nombre, gravedad, partidos} de una lesión nueva."""
    tipos = CL.TIPOS[origen]
    tipo = rng.choices(tipos, weights=[t["peso"] for t in tipos])[0]
    gravedades = list(tipo["gravedad"])
    gravedad = rng.choices(gravedades, weights=[tipo["gravedad"][g] for g in gravedades])[0]
    lo, hi = CL.GRAVEDADES[gravedad]["partidos"]
    return {"codigo": tipo["codigo"], "nombre": tipo["nombre"], "gravedad": gravedad, "partidos": rng.randint(lo, hi)}


def debe_salir(gravedad: str, rng=_random) -> bool:
    """Las moderadas y graves sacan al jugador; una leve, a veces."""
    return gravedad != "leve" or rng.random() < CL.PROB_SALE_LEVE


def texto_evento(nombre: str, lesion: dict, origen: str, sale: bool, con_cambio: bool, equipo: str,
                 es_portero: bool = False, rng=_random) -> str:
    base = rng.choice(CL.TEXTOS_MUSCULAR if origen == "muscular" else CL.TEXTOS_CONTACTO)
    texto = base.format(j=nombre, lesion=lesion["nombre"])
    if not sale:
        if con_cambio or lesion["gravedad"] == "leve":
            return texto + CL.TEXTO_SIGUE
        return texto + (CL.TEXTO_PORTERO_SIGUE if es_portero else CL.TEXTO_SIGUE_SIN_CAMBIO)
    return texto + (CL.TEXTO_SALE_CAMBIO if con_cambio else CL.TEXTO_SALE_SIN_CAMBIO.format(equipo=equipo))


def texto_sin_cambio(equipo: str) -> str:
    return CL.TEXTO_SALE_SIN_CAMBIO.format(equipo=equipo)


def baja_texto(partidos: int) -> str:
    if partidos <= 0:
        return "sin baja"
    return f"{partidos} partido{'s' if partidos != 1 else ''} de baja"


def vista(lesion: dict) -> dict:
    """Datos de una lesión para las plantillas (nombre, gravedad con su color e ícono, partidos que le faltan)."""
    if not lesion:
        return {}
    g = CL.GRAVEDADES.get(lesion.get("gravedad"), CL.GRAVEDADES["leve"])
    restantes = int(lesion.get("restantes") or 0)
    return {**lesion, "gravedad_nombre": g["nombre"], "icono": g["icono"], "color": g["color"], "restantes": restantes,
            "activa": restantes > 0, "baja_texto": baja_texto(restantes)}
