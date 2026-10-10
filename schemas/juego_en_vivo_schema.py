"""Esquemas Pydantic del Juego en Vivo (routes/juego_en_vivo_route.py). Las respuestas son los
dicts que arma services/juego_en_vivo_service.py; acá solo se validan las entradas."""
from typing import Optional
from pydantic import BaseModel


class CrearSesionIn(BaseModel):
    juego_id: str
    pais_id: int
    multiplicador: Optional[float] = None  # riesgo inicial; por defecto x1


class CambiarRiesgoIn(BaseModel):
    multiplicador: float
