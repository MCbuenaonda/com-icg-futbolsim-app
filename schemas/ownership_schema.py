"""
Esquemas Pydantic para el módulo de Dueño de Selecciones / Accionista
(routes/ownership_route.py). Igual que en quinielas, son solo el contrato de
entrada/salida de la API — la persistencia sigue siendo pymongo + dicts.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

TIPOS_TRANSACCION = {"COMPRA", "VENTA", "DIVIDENDO", "BONO_CLASIFICACION", "SINERGIA_ALBUM"}


# ==========================================
# Mercado (países disponibles para comprar)
# ==========================================
class SeleccionMercadoOut(BaseModel):
    pais_id: int
    nombre: str
    bandera: Optional[str] = None
    confederacion_id: int
    valor: int


# ==========================================
# Portafolio (team_ownerships, salida)
# ==========================================
class InversionOut(BaseModel):
    id: str
    user_id: str
    pais_id: int
    pais_nombre: Optional[str] = None
    pais_bandera: Optional[str] = None
    confederacion_id: int
    purchase_price: int
    current_value: int
    plusvalia: int  # current_value - purchase_price
    total_dividends_earned: int
    purchased_at: datetime
    sold_at: Optional[datetime] = None
    sale_price: Optional[int] = None
    status: str


# ==========================================
# Transacciones (ownership_transactions, salida)
# ==========================================
class TransaccionOut(BaseModel):
    id: str
    user_id: str
    pais_id: int
    type: str
    amount_points: int
    album_synergy_applied: bool = False
    created_at: datetime
