from typing import Optional
from pydantic import BaseModel


class EstadisticasPais(BaseModel):
    puntos: Optional[int]
    juegos_jugados: Optional[int]
    juegos_ganados: Optional[int]
    juegos_empatados: Optional[int]
    juegos_perdidos: Optional[int]
    goles_favor: Optional[int]
    goles_contra: Optional[int]
    diferencia_goles: Optional[int]
    efectividad_gol: Optional[int]
    promedio_gol: Optional[int]
    p_ofensiva: Optional[int]
    p_defensiva: Optional[int]
    p_posesion: Optional[int]
    rankin: Optional[int]
    poder: Optional[int]

class Pais(BaseModel):
    id: Optional[int]
    nombre: Optional[str]
    confederacion_id: Optional[int]
    bandera: Optional[str]
    user_id: Optional[int]
    estado: Optional[str]
    siglas: Optional[str]
    iso: Optional[str]
    federacion: Optional[str]
    valor: Optional[int]
    estadisticas: Optional[EstadisticasPais]
