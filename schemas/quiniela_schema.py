"""
Esquemas Pydantic para el módulo de Quinielas (routes/quinielas_route.py).
Solo se usan como contrato de entrada/salida de la API; la persistencia sigue
siendo con pymongo + diccionarios planos (mismo patrón que el resto del
proyecto), no hay una capa ODM real por debajo.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, field_validator

PRONOSTICOS_VALIDOS = {"LOCAL", "EMPATE", "VISITA"}


# ==========================================
# Catálogo de quinielas (quiniela_config)
# ==========================================
class ReglaPremio(BaseModel):
    aciertos_requeridos: int
    premio_puntos: int


class QuinielaConfigOut(BaseModel):
    id: str
    codigo: str
    nombre: str
    cantidad_partidos: int
    costo_puntos: int
    reglas_premio: List[ReglaPremio]
    activa: bool


# ==========================================
# Compra de boleto (entrada)
# ==========================================
class SeleccionIn(BaseModel):
    juego_id: str
    pronostico: str

    @field_validator("pronostico")
    @classmethod
    def validar_pronostico(cls, valor: str) -> str:
        valor = valor.strip().upper()
        if valor not in PRONOSTICOS_VALIDOS:
            raise ValueError(f"pronostico debe ser uno de {sorted(PRONOSTICOS_VALIDOS)}")
        return valor


class CrearBoletoIn(BaseModel):
    usuario_id: Optional[str] = None  # ignorado: se usa el usuario de la sesión (routes/quinielas_route.py)
    quiniela_config_id: str
    selecciones: List[SeleccionIn]


# ==========================================
# Boleto de quiniela (quiniela_usuario, salida)
# ==========================================
class SeleccionOut(BaseModel):
    juego_id: str
    pronostico: str
    estado: str
    resultado_real: Optional[str] = None


class BoletoOut(BaseModel):
    id: str
    usuario_id: str
    quiniela_config_id: str
    costo_pagado: int
    estado: str
    aciertos: int
    premio_ganado: int
    selecciones: List[SeleccionOut]
    fecha_creacion: datetime
    fecha_resolucion: Optional[datetime] = None
