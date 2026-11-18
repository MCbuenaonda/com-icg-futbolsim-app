"""Esquemas Pydantic para el módulo de Simulación Automática en Vivo (services/live_match_service.py)."""
from datetime import datetime
from typing import Any, Dict, List, Optional
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
    # Reloj con tiempo añadido y cuerpo arbitral (services/arbitraje.py) -- opcionales, los partidos viejos no los traen
    periodo: Optional[int] = None
    adicional: Optional[int] = None
    arbitro: Optional[str] = None
    arbitro_rol: Optional[str] = None
    var_decision: Optional[str] = None
    de_penal: Optional[bool] = None
    minutos_anadidos: Optional[int] = None
    # Director técnico (services/tecnicos.py): reclamos, amonestación/expulsión del DT y ajustes tácticos
    dt_id: Optional[int] = None
    dt: Optional[str] = None
    ajuste: Optional[str] = None
    # Cambio de esquema en vivo (services/tecnicos.esquema_en_vivo): del y al
    esquema_de: Optional[str] = None
    esquema_a: Optional[str] = None
    especialidad: Optional[str] = None   # especialidad del jugador que decidió la jugada (config/especialidades.py)
    especialidad_nombre: Optional[str] = None
    # Lesión (services/lesiones.py): cuál, gravedad, si sale y si su equipo se queda con uno menos
    lesion: Optional[str] = None
    gravedad: Optional[str] = None
    sale_lesionado: Optional[bool] = None
    sin_cambio: Optional[bool] = None
    # Recorrido del balón (services/balon.py): origen, destino, trayectoria y toques sin narrar, en coordenadas absolutas
    balon: Optional[Dict[str, Any]] = None


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


class ClimaOut(BaseModel):
    condicion: Optional[str] = None
    temperatura_c: Optional[float] = None
    humedad_porcentaje: Optional[float] = None
    viento_kmh: Optional[float] = None


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
    estadio_img: Optional[str] = None  # ilustración del estadio (bucket estadios_v2/): marcador de TV y comercial de la transmisión
    fecha: Optional[str] = None
    hora: Optional[str] = None
    aforo: Optional[AforoOut] = None
    clima: Optional[ClimaOut] = None   # chip del clima junto al estadio
    confederacion_id: Optional[int] = None
    fase_id: Optional[int] = None
    id_local: Optional[int] = None
    id_visita: Optional[int] = None
    goles_local: int
    goles_visitante: int
    minuto_actual: int
    adicional_actual: int = 0
    eventos: List[EventoOut]
    segundos_transcurridos: float
    segundos_restantes: float
    finalizado: bool
    # Energía (0-100) de cada jugador al minuto que se está revelando: {"<jugador_id>": energía}
    energia: Dict[str, int] = {}
    # Cada cuánto se revela un evento (ms): la cancha reparte la animación de cada jugada en ese intervalo
    ms_por_evento: Optional[int] = None


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


class MesaTeleOut(BaseModel):
    id: int
    nombre: str
    logo: Optional[str] = None
    color: str
    color2: str
    lema: Optional[str] = None
    pais_id: Optional[int] = None  # selección cuyos derechos tiene la cadena en este partido
    pais: Optional[str] = None


class MesaComentaristaOut(BaseModel):
    nombre: Optional[str] = None
    avatar_url: Optional[str] = None
    rol: str  # narrador | analista


class MesaInvitadoOut(BaseModel):
    jugador_id: int
    nombre: str
    pais_id: Optional[int] = None


class MarcaDuenoOut(BaseModel):
    nombre: Optional[str] = None
    avatar_url: Optional[str] = None


class MarcaPatrocinadoraOut(BaseModel):
    """Una marca de tu universo que patrocina a una selección o a un jugador del partido (para el dato «presentado por»)."""
    id: int
    nombre: str
    logo: Optional[str] = None
    color: str
    color2: str
    lema: Optional[str] = None
    dueno: Optional[MarcaDuenoOut] = None


class MesaOut(BaseModel):
    tele: MesaTeleOut
    comentaristas: List[MesaComentaristaOut] = []
    invitado: Optional[MesaInvitadoOut] = None
    convenios: List[MarcaPatrocinadoraOut] = []   # marcas con convenio de presentación de la cadena


class PatrocinadoresOut(BaseModel):
    paises: Dict[str, List[MarcaPatrocinadoraOut]] = {}     # pais_id -> marcas de la selección
    jugadores: Dict[str, List[MarcaPatrocinadoraOut]] = {}  # jugador_id -> marcas del jugador


class VozOut(BaseModel):
    """Quien puede comentar el partido en la pleca (líder de la afición, presidente, periodista o jugador de otro país del grupo)."""
    tipo: str  # aficion | presidente | periodista | jugador
    nombre: str
    cargo: str
    avatar_url: Optional[str] = None
    jugador_id: Optional[int] = None
    pais_id: Optional[int] = None
    pais: Optional[str] = None
    lado: str  # local | visita | grupo | neutral
    rasgo: Optional[str] = None
    sesgo: Optional[str] = None
    medio: Optional[str] = None
    medio_logo: Optional[str] = None


class ContextoPartidoOut(BaseModel):
    """Dónde está el partido en el torneo (lista cerrada): lo usan los comentarios de la transmisión."""
    fase_id: Optional[int] = None
    jornada: Optional[int] = None
    jornadas_total: Optional[int] = None


class TransmisionLiveOut(BaseModel):
    """Quién narra el partido en transmisión PARA EL USUARIO de la sesión (lista cerrada: nada de pagos ni aficionados)."""
    match_id: str
    modo: str  # tv | radio
    mesas: List[MesaOut] = []
    patrocinadores: PatrocinadoresOut = PatrocinadoresOut()
    voces: List[VozOut] = []
    contexto: ContextoPartidoOut = ContextoPartidoOut()


class PlantillasLiveOut(BaseModel):
    jugadores: Dict[str, str]  # nombre del jugador -> sigla de posición granular
    titulares_local: List[str] = []
    titulares_visitante: List[str] = []
    dorsales: Dict[str, int] = {}  # nombre del jugador -> número de camiseta
    ids: Dict[str, int] = {}  # nombre del jugador -> id (para su avatar en "Jugadores en Cancha")
    paises: Dict[str, str] = {}  # nombre del jugador -> nombre de su selección (la narración de TV/radio lo menciona)
    tactica_local: Optional[str] = None
    tactica_visitante: Optional[str] = None
    # Línea (1 POR, 2 DEF, 3 MED, 4 DEL) de cada titular, alineada por índice con titulares_*
    lineas_local: List[int] = []
    lineas_visitante: List[int] = []
    leyendas: List[str] = []  # nombres de las leyendas (jugadores.leyenda) de los dos equipos
    # Mascota del Mundial (services/arte_mundial_service): festeja en la cancha los goles del anfitrión
    anfitrion: Optional[str] = None
    mascota_url: Optional[str] = None
    mascota_nombre: Optional[str] = None
    # DT de cada lado (live_match_service._dts_en_vivo): {local|visita: {id, nombre, estilo, arquetipo, avatar_url, partidos, record}}
    dt: Dict[str, Any] = {}
    # Formaciones (config/formaciones.py): líneas de cada esquema, para reacomodar la cancha si el DT cambia de esquema,
    # y el planteamiento inicial de cada lado {local|visita: {esquema, etiqueta, postura, motivo}} (sin los cambios: spoiler)
    formaciones: Dict[str, List[int]] = {}
    planteamiento: Dict[str, Any] = {}
    # Qué extremo jugó de segundo delantero en cada lado ({local|visita: bool}, services/formaciones.lineas)
    espejo_extremos: Dict[str, bool] = {}
    # Cuerpo arbitral del partido con su rostro ({rol: {nombre, url}}): la ventana de avisos de la cancha muestra quién marcó
    arbitros: Dict[str, Any] = {}


class EquipoPreviaOut(BaseModel):
    id: Optional[int] = None
    nombre: Optional[str] = None
    bandera: str = ""
    siglas: str = ""


class ClimaPreviaOut(BaseModel):
    condicion: Optional[str] = None
    temperatura_c: Optional[float] = None
    humedad_porcentaje: Optional[float] = None
    viento_kmh: Optional[float] = None


class AforoPreviaOut(BaseModel):
    asistencia: Optional[int] = None
    capacidad_estadio: Optional[int] = None
    porcentaje_ocupacion: Optional[float] = None
    estado: Optional[str] = None


class InvitadoPreviaOut(BaseModel):
    nombre: Optional[str] = None
    jugador_id: Optional[int] = None
    pais_id: Optional[int] = None
    pais: Optional[str] = None


class CadenaPreviaOut(BaseModel):
    id: Optional[int] = None
    nombre: str
    logo: Optional[str] = None
    color: Optional[str] = None
    pais: Optional[str] = None
    invitado: Optional[InvitadoPreviaOut] = None


class TransmisionPreviaOut(BaseModel):
    modo: str = "radio"   # "tv" con las cadenas de TU universo, o "radio"
    cadenas: List[CadenaPreviaOut] = []


class ProximoPartidoOut(BaseModel):
    """Previa del próximo partido de /en-vivo (sin transmisión): estadio, equipos, fecha, clima y aforo."""
    match_id: str
    local: EquipoPreviaOut
    visitante: EquipoPreviaOut
    estadio: Optional[str] = None
    estadio_img: Optional[str] = None
    ciudad: Optional[str] = None
    pais_sede: Optional[str] = None
    fecha: Optional[str] = None
    fecha_texto: Optional[str] = None
    hora: Optional[str] = None
    grupo: Optional[str] = None
    jornada: Optional[str] = None
    clima: Optional[ClimaPreviaOut] = None
    aforo: Optional[AforoPreviaOut] = None
    transmision: Optional[TransmisionPreviaOut] = None


class JugadorTorneoOut(BaseModel):
    """Números del torneo de un jugador, SIN el partido en transmisión (lista cerrada)."""
    id: int
    nombre: str
    goles: int = 0
    asistencias: int = 0
    partidos: int = 0
    amarillas: int = 0
    rojas: int = 0
    leyenda: bool = False
