"""
Esquemas Pydantic para el módulo de Inversión en Sedes / Estadios
(routes/venue_route.py). Igual que en los demás módulos JSON de esta app
(quinielas, ownership, fantasy, álbum), son solo el contrato de entrada/salida
de la API — la persistencia sigue siendo pymongo + dicts en services/venue_service.py.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

ESTADOS_INVERSION_SEDE = {"ACTIVO", "VENDIDO"}


# ==========================================
# Directorio / disponibilidad de sedes
# ==========================================
class CiudadDisponibleOut(BaseModel):
    ciudad_id: int
    nombre: str
    estadio: Optional[str] = None
    tipo: Optional[str] = None
    pais_id: int
    pais_nombre: Optional[str] = None
    costo: int
    tiene_dueno: bool
    es_mia: bool = False


# ==========================================
# Portafolio (city_ownerships, salida)
# ==========================================
class SedeOut(BaseModel):
    id: str
    user_id: str
    ciudad_id: int
    ciudad_nombre: Optional[str] = None
    estadio: Optional[str] = None
    pais_id: int
    pais_nombre: Optional[str] = None
    purchase_price: int
    total_revenue_earned: int
    matches_hosted_count: int
    purchased_at: datetime
    sold_at: Optional[datetime] = None
    sale_price: Optional[int] = None
    status: str


# ==========================================
# Historial de regalías (city_revenue_history, salida)
# ==========================================
class RegaliaSedeOut(BaseModel):
    id: str
    user_id: str
    ciudad_id: int
    match_id: str
    fase_id: Optional[int] = None
    total_earned: int
    album_synergy_applied: bool
    created_at: datetime
