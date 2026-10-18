"""Esquemas Pydantic para el módulo Álbum de Estampas (routes/album_route.py)."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

TIPOS_ESTAMPA = {"JUGADOR", "CIUDAD", "PAIS", "ARBITRO"}


class StickerOut(BaseModel):
    tipo: str
    id: int
    nombre: str
    duplicado: bool
    bonus_puntos: int = 0
    # Detalle para dibujar la estampa al abrir el sobre (opcionales: no se guardan en pack_purchases)
    pais_id: Optional[int] = None
    pais_nombre: Optional[str] = None
    confederacion: Optional[str] = None
    numero: Optional[int] = None
    posicion: Optional[str] = None
    overall: Optional[float] = None
    estadio: Optional[str] = None
    estadio_img: Optional[str] = None
    puesto: Optional[str] = None        # árbitro (estampa Platino)
    puesto_corto: Optional[str] = None
    genero: Optional[str] = None
    avatar_url: Optional[str] = None


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
    arbitros: List[int] = []
    total_jugadores: int
    total_paises: int
    total_ciudades: int
    total_arbitros: int = 0
    llenado_por_pais: List[LlenadoPaisOut]
    paises_detalle: List[PaisEstampaOut] = []
    ciudades_detalle: List[CiudadEstampaOut] = []
