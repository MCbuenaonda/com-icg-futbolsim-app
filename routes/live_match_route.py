from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from schemas.live_match_schema import StartAutoSimulationResponse, StartedMatchOut, LiveMatchOut, TablaGrupoOut, PlantillasLiveOut
from services.live_match_service import iniciar_simulacion_automatica, obtener_estado_live, obtener_tabla_grupo_partido_en_vivo, obtener_posiciones_plantillas_en_vivo
from services.auth_service import obtener_usuario_actual, context_usuario_actual, requiere_permiso
import logging

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])

# API JSON (comparte el prefijo /matches con routes/prematch_route.py -- FastAPI permite
# varios APIRouter bajo el mismo prefijo; se distinguen por 'tags' en /docs)
route = APIRouter(prefix="/matches", tags=["Live Auto-Simulation"])

# Vista HTML: panel de transmisión en vivo (botón para arrancar + polling de /matches/live)
route_vistas = APIRouter(prefix="/en-vivo", tags=["Live Auto-Simulation UI"])

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _serializar_started_match(juego: dict) -> StartedMatchOut:
    return StartedMatchOut(
        match_id=str(juego["_id"]),
        local=(juego.get("equipo_local") or {}).get("nombre", "?"),
        visitante=(juego.get("equipo_visitante") or {}).get("nombre", "?"),
        id_local=(juego.get("equipo_local") or {}).get("id"),
        id_visita=(juego.get("equipo_visitante") or {}).get("id"),
        fecha=juego.get("fecha"),
        hora=juego.get("hora"),
        fase_id=juego.get("fase_id"),
        grupo=juego.get("grupo"),
        started_at=juego["transmision"]["started_at"],
        duracion_segundos=juego["transmision"]["duracion_segundos"],
    )


@route.post("/simulate-next-auto", response_model=StartAutoSimulationResponse, name="matches_simulate_next_auto",
            dependencies=[Depends(requiere_permiso("simular_partidos"))])
async def simulate_next_auto(request: Request):
    """
    Busca el próximo partido pendiente ('creado'), lo simula y persiste el resultado (motor +
    services.juegos_service.simular_y_registrar_resultado), y arranca la ventana de "transmisión
    en vivo" de 5 minutos que consume GET /matches/live. Los efectos secundarios del partido
    (país, jugadores, rankings, aficionados, quinielas, fantasy, sedes, avance de fase) quedan
    diferidos hasta que esa ventana termine, para no revelar el resultado antes de tiempo en la
    tabla de posiciones/perfiles de jugadores. Requiere sesión iniciada.

    Es seguro llamarlo repetidas veces (ej. desde un poller): si ya hay un partido en curso, no
    arranca uno nuevo -- devuelve el que ya está en curso.
    """
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión para simular partidos automáticamente")

    try:
        resultado = iniciar_simulacion_automatica()
    except Exception as e:
        logger.error(f"Error al iniciar la simulación automática: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al iniciar la simulación automática")

    if not resultado["encontrado"]:
        return StartAutoSimulationResponse(
            encontrado=False,
            mensaje="No hay partidos pendientes por simular."
        )

    juego = resultado["juego"]
    match_out = _serializar_started_match(juego)

    if resultado["ya_en_progreso"]:
        return StartAutoSimulationResponse(
            encontrado=True,
            ya_en_progreso=True,
            match=match_out,
            mensaje="Ya hay una transmisión en curso; no se inició una nueva."
        )

    # A propósito NO se devuelve el marcador acá (ni el de arriba, "ya_en_progreso") -- eso
    # revelaría el resultado final en la misma respuesta del botón "Simular siguiente", antes de
    # que arranque la revelación en vivo. El marcador (parcial, gobernado por la ventana de 5
    # minutos) se consulta vía GET /matches/live.
    return StartAutoSimulationResponse(
        encontrado=True,
        ya_en_progreso=False,
        match=match_out,
        mensaje="Simulación iniciada, transmisión en curso."
    )


@route.get("/live", response_model=LiveMatchOut, name="matches_live")
async def get_live_match():
    """
    Estado actual de la transmisión en vivo: partido en curso, marcador parcial y solo el
    subconjunto de eventos ya "sucedidos" en la ventana de 5 minutos, más los segundos
    restantes. Solo lectura -- sin autenticación, igual que el resto de los GET del proyecto.
    """
    estado = obtener_estado_live()
    if not estado:
        raise HTTPException(status_code=404, detail="No hay ningún partido en transmisión en este momento.")

    return LiveMatchOut(**estado)


@route.get("/live/tabla-grupo", response_model=TablaGrupoOut, name="matches_live_tabla_grupo")
async def get_live_tabla_grupo():
    """
    Tabla de posiciones del grupo del partido en transmisión (para el panel lateral de
    /en-vivo/, junto a la cronología). Solo lectura, sin autenticación -- no expone nada que no
    esté ya público en /confederacion/{id}. 'equipos' viaja vacío si la fase no tiene tabla de
    grupos (eliminación directa); el frontend decide si ocultar el panel en ese caso.
    """
    tabla = obtener_tabla_grupo_partido_en_vivo()
    if not tabla:
        raise HTTPException(status_code=404, detail="No hay ningún partido en transmisión en este momento.")

    return TablaGrupoOut(**tabla)


@route.get("/live/plantillas", response_model=PlantillasLiveOut, name="matches_live_plantillas")
async def get_live_plantillas():
    """
    Mapa nombre de jugador -> sigla de posición granular (POR/LD/LI/MC/ED/etc.) y el 11 titular
    de ambos equipos del partido en transmisión, para enriquecer la etiqueta de "Cancha en Vivo"
    y las cards de "Jugadores en Cancha" en el frontend. Solo lectura, sin autenticación -- no
    expone nada que no esté ya público en /jugadores/{id}. Pensado para pedirse UNA vez por
    partido, no en cada poll.
    """
    plantillas = obtener_posiciones_plantillas_en_vivo()
    if not plantillas:
        raise HTTPException(status_code=404, detail="No hay ningún partido en transmisión en este momento.")

    return PlantillasLiveOut(**plantillas)


# ==========================================================================
# Vista HTML (Panel de Transmisión en Vivo)
# ==========================================================================
@route_vistas.get("/", response_class=HTMLResponse, name="live_match_view")
async def live_match_view(request: Request):
    """
    Panel client-side puro: no recibe datos del server, todo el estado (si hay un partido en
    curso, marcador parcial, eventos revelados) se consulta vía JS contra GET /matches/live
    (polling) y se arranca vía POST /matches/simulate-next-auto.
    """
    return templates.TemplateResponse(request=request, name="live_match.html", context={})
