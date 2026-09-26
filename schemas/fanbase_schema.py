"""Esquemas Pydantic para el módulo de Popularidad y Base de Aficionados (services/fanbase_service.py)."""
from typing import Optional
from pydantic import BaseModel


class PaisFanbaseOut(BaseModel):
    pais_id: int
    nombre: str
    bandera: Optional[str] = None
    aficionados: int
    # Ranking FIFA solo como dato de referencia -- el orden del listado es por 'aficionados',
    # no por este campo (son métricas explícitamente independientes, ver fanbase_service.py).
    rankin_fifa: int = 0
