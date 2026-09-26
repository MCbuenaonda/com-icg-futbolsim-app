"""Esquemas Pydantic para el módulo de Análisis Pre-Partido (Pre-Match Scouter, services/prematch_service.py)."""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class EstadoClasificacion(str, Enum):
    """Estado de clasificación matemática de un equipo dentro de su grupo (fases 1-7)."""
    MATHEMATICALLY_QUALIFIED = "MATHEMATICALLY_QUALIFIED"
    DEPENDS_ON_SELF = "DEPENDS_ON_SELF"
    NEEDS_OUTSIDE_RESULTS = "NEEDS_OUTSIDE_RESULTS"
    ELIMINATED = "ELIMINATED"
    # Fases de eliminación directa (partido único, fases 8-13): no hay tabla de grupo ni
    # "clasificación matemática" en el sentido de puntos — solo aplica el % de avanzar de ronda.
    KNOCKOUT_STAGE = "KNOCKOUT_STAGE"


class TeamAnalysisOut(BaseModel):
    pais_id: int
    nombre: str
    bandera: Optional[str] = None

    # Tabla de grupo (0 / N-A en fases de eliminación directa)
    puntos: int = 0
    posicion: int = 0
    partidos_jugados: int = 0
    partidos_restantes: int = 0
    puntos_maximos_alcanzables: int = 0
    estado_clasificacion: EstadoClasificacion
    puntos_para_calificar: Optional[int] = None

    # Comparativa H2H
    probabilidad_victoria_pct: float
    p_ofensiva: float = 0.0
    p_defensiva: float = 0.0
    p_posesion: float = 0.0
    poder: float = 0.0
    goles_favor: int = 0
    goles_contra: int = 0


class GroupStandingRowOut(BaseModel):
    posicion: int
    pais_id: int
    nombre: str
    bandera: Optional[str] = None
    puntos: int
    partidos_jugados: int
    diferencia_goles: int
    # "DIRECTO" | "POSIBILIDAD" | "ELIMINADO" — zona de la tabla, para resaltar en la vista.
    zona: str
    es_equipo_analizado: bool


class PreMatchAnalysisResponse(BaseModel):
    match_id: str
    fase_id: int
    grupo: Optional[str] = None
    confederacion_id: Optional[int] = None
    cantidad_equipos_grupo: int = 0
    jornada_actual: Optional[int] = None
    jornadas_totales: Optional[int] = None
    es_eliminacion_directa: bool

    home_team_analysis: TeamAnalysisOut
    away_team_analysis: TeamAnalysisOut
    group_standings_summary: List[GroupStandingRowOut] = []

    scouter_verdict: str
