"""Esquemas Pydantic para el módulo Fantasy (routes/fantasy_route.py)."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class LineupIn(BaseModel):
    usuario_id: Optional[str] = None  # ignorado: se usa el usuario de la sesión (routes/fantasy_route.py)
    fase_id: Optional[int] = None  # ignorado: el Once Ideal es uno por Mundial (services/fantasy_service.py)
    lineup: List[int]  # ids de jugadores (colección 'jugadores')
    formacion: str = "4-3-3"  # solo agrupamiento visual (4-3-3/4-4-2/3-5-2), no afecta la validación


class FantasyTeamOut(BaseModel):
    id: str
    usuario_id: str
    mundial_id: Optional[str] = None
    fase_id: Optional[int] = None  # legado
    lineup: List[int]
    formacion: str
    is_locked: bool
    total_points_fase: int
    cambios_gratis_disponibles: int


class JugadorBusquedaOut(BaseModel):
    id: int
    nombre: str
    posicion_id: int
    posicion: str
    posicion_nombre: str
    posicion_siglas: str
    pais_id: int
    pais_nombre: str
    overall: float
    numero: Optional[int] = None
    eliminado: bool = False
    motivo_eliminado: Optional[str] = None


class DesgloseConceptoOut(BaseModel):
    concepto: str
    cantidad: int
    puntos_unitarios: int
    subtotal: int


class HistorialPuntosOut(BaseModel):
    id: str
    jugador_id: int
    jugador_nombre: str
    desglose: List[DesgloseConceptoOut]
    puntos_base: int
    sinergia_album_aplicada: bool
    multiplicador: float
    puntos_finales: int
    monto_otorgado: int
    created_at: Optional[datetime] = None
