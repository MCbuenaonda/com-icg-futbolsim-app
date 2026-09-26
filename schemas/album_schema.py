"""Esquemas Pydantic para el módulo Álbum de Estampas (routes/album_route.py)."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

TIPOS_ESTAMPA = {"JUGADOR", "CIUDAD", "PAIS"}


class StickerOut(BaseModel):
    tipo: str
    id: int
    nombre: str
    duplicado: bool
    bonus_puntos: int = 0


class PackPurchaseOut(BaseModel):
    id: str
    usuario_id: str
    costo_pagado: int
    estampas_obtenidas: List[StickerOut]
    fecha: datetime


class JugadorEstampaOut(BaseModel):
    id: int
    nombre: str


class PaisEstampaOut(BaseModel):
    id: int
    nombre: str
    bandera: Optional[str] = None


class CiudadEstampaOut(BaseModel):
    id: int
    nombre: str
    estadio: Optional[str] = None
    pais_nombre: str


class LlenadoPaisOut(BaseModel):
    pais_id: int
    pais_nombre: str
    total_jugadores: int
    jugadores_poseidos: int
    porcentaje: float
    jugadores: List[JugadorEstampaOut] = []


class ColeccionOut(BaseModel):
    usuario_id: str
    jugadores: List[int]
    paises: List[int]
    ciudades: List[int]
    total_jugadores: int
    total_paises: int
    total_ciudades: int
    llenado_por_pais: List[LlenadoPaisOut]
    paises_detalle: List[PaisEstampaOut] = []
    ciudades_detalle: List[CiudadEstampaOut] = []
