"""Esquemas Pydantic para el módulo de Simulación Automática en Vivo (services/live_match_service.py)."""
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel


class EventoOut(BaseModel):
    minuto: float
    equipo: str
    tipo: str
    descripcion: str
    jugadores: List[str] = []
    # Campos del motor de segundos (services/simular_service.py::construir_evento) -- opcionales
    # para no romper partidos viejos simulados antes de este cambio, que no los traen.
    segundos_acumulados: Optional[int] = None
    zona: Optional[str] = None
    posicion_balon: Optional[Dict[str, float]] = None
    es_preparacion: Optional[bool] = None


class StartedMatchOut(BaseModel):
    match_id: str
    local: str
    visitante: str
    id_local: int
    id_visita: int
    fecha: Optional[str] = None
    hora: Optional[str] = None
    fase_id: Optional[int] = None
    grupo: Optional[str] = None
    started_at: datetime
    duracion_segundos: int


class StartAutoSimulationResponse(BaseModel):
    encontrado: bool
    ya_en_progreso: bool = False
    match: Optional[StartedMatchOut] = None
    mensaje: str


class AforoOut(BaseModel):
    asistencia: int
    capacidad_estadio: Optional[int] = None
    porcentaje_ocupacion: Optional[float] = None
    estado: Optional[str] = None
    publico_local: Optional[int] = None
    publico_visitante: Optional[int] = None
    porcentaje_publico_local: Optional[float] = None
    porcentaje_publico_visitante: Optional[float] = None
    escenario_publico: Optional[str] = None


class LiveMatchOut(BaseModel):
    match_id: str
    local: str
    visitante: str
    bandera_local: str = ""
    bandera_visitante: str = ""
    siglas_local: str = ""
    siglas_visitante: str = ""
    grupo: Optional[str] = None
    estadio: Optional[str] = None
    fecha: Optional[str] = None
    hora: Optional[str] = None
    aforo: Optional[AforoOut] = None
    confederacion_id: Optional[int] = None
    fase_id: Optional[int] = None
    id_local: Optional[int] = None
    id_visita: Optional[int] = None
    goles_local: int
    goles_visitante: int
    minuto_actual: int
    eventos: List[EventoOut]
    segundos_transcurridos: float
    segundos_restantes: float
    finalizado: bool


class EquipoTablaGrupoOut(BaseModel):
    pais_id: int
    nombre: str
    bandera: Optional[str] = None
    siglas: Optional[str] = None
    puntos: int
    diferencia_goles: int
    goles_favor: int
    goles_contra: int
    juegos_jugados: int
    poder: float


class TablaGrupoOut(BaseModel):
    match_id: str
    grupo: Optional[str] = None
    id_local: Optional[int] = None
    id_visita: Optional[int] = None
    equipos: List[EquipoTablaGrupoOut]


class PlantillasLiveOut(BaseModel):
    jugadores: Dict[str, str]  # nombre del jugador -> sigla de posición granular
    titulares_local: List[str] = []
    titulares_visitante: List[str] = []
    dorsales: Dict[str, int] = {}  # nombre del jugador -> número de camiseta
    tactica_local: Optional[str] = None
    tactica_visitante: Optional[str] = None
    # Línea (1 POR, 2 DEF, 3 MED, 4 DEL) de cada titular, alineada por índice con titulares_*
    lineas_local: List[int] = []
    lineas_visitante: List[int] = []
