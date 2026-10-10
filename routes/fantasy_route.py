from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from bson.errors import InvalidId
from schemas.fantasy_schema import LineupIn, FantasyTeamOut, JugadorBusquedaOut, HistorialPuntosOut
from services.fantasy_service import (
    set_fantasy_lineup, obtener_alineacion, buscar_jugadores, fase_ya_iniciada,
    obtener_detalle_jugadores, obtener_catalogo_posiciones, obtener_catalogo_paises,
    obtener_formaciones_granulares, obtener_historial_puntos_fantasy, obtener_desempeno_lineup,
    obtener_equipo_mas_reciente_anterior, FORMACION_DEFAULT
)
from services.juegos_service import obtener_juego_activo
from services.auth_service import obtener_usuario_actual, context_usuario_actual, exigir_mismo_usuario_o_admin
import logging
import json

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])

# API JSON (contrato tal cual se pidió: /fantasy/lineup, /fantasy/lineup/{user_id}/{fase_id})
route = APIRouter(prefix="/fantasy", tags=["Fantasy"])

# Vista HTML para armar el Once Ideal
route_vistas = APIRouter(prefix="/once-ideal", tags=["Fantasy UI"])

tag = 'Fantasy'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==========================================================================
# API JSON
# ==========================================================================
@route.post("/lineup", response_model=FantasyTeamOut, name="fantasy_set_lineup")
async def set_lineup(payload: LineupIn, request: Request):
    """Guarda el Once Ideal del usuario para una fase (cobra penalización si la fase ya empezó).
    Siempre para el usuario de la sesión: el 'usuario_id' del body se ignora (antes permitía
    armar/cobrar la alineación de otra cuenta)."""
    usuario = obtener_usuario_actual(request)
    try:
        return set_fantasy_lineup(usuario["_id"], payload.fase_id, payload.lineup, payload.formacion)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario o jugador inválido")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al guardar alineación fantasy: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al guardar la alineación")


@route.get("/lineup/{user_id}/{fase_id}", response_model=Optional[FantasyTeamOut], name="fantasy_get_lineup")
async def get_lineup(user_id: str, fase_id: int, request: Request):
    """Devuelve el Once Ideal del usuario para esa fase (null si todavía no armó ninguno)."""
    exigir_mismo_usuario_o_admin(request, user_id)
    try:
        return obtener_alineacion(user_id, fase_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")


@route.get("/jugadores/buscar", response_model=List[JugadorBusquedaOut], name="fantasy_buscar_jugadores")
async def buscar(
    q: str = Query("", description="Nombre (o parte) del jugador a buscar"),
    pais_id: Optional[int] = Query(None, description="Filtrar por país"),
    posicion_id: Optional[int] = Query(None, description="Filtrar por posición (id de la colección 'posiciones')")
):
    """
    Endpoint auxiliar (no pedido explícitamente, pero necesario para que la vista
    de armado del Once Ideal sea usable): busca jugadores por nombre/país/posición
    entre los >4000 disponibles, en vez de mandarlos todos de una al HTML.
    """
    return buscar_jugadores(q.strip(), pais_id=pais_id, posicion_id=posicion_id)


@route.get("/points-history/{user_id}/{fase_id}", response_model=List[HistorialPuntosOut], name="fantasy_points_history")
async def points_history(user_id: str, fase_id: int, request: Request):
    """
    Endpoint auxiliar (no pedido explícitamente, pero coherente con el resto de
    endpoints de solo lectura del módulo): historial de cómo se calcularon los
    puntos fantasy del usuario en esta fase, más reciente primero.
    """
    exigir_mismo_usuario_o_admin(request, user_id)
    try:
        return obtener_historial_puntos_fantasy(user_id, fase_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")


# ==========================================================================
# Vista HTML (requiere sesión iniciada — ver services/auth_service.py)
# ==========================================================================
@route_vistas.get("/", response_class=HTMLResponse, name="fantasy_home")
async def fantasy_home(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    # "Fase actual": la del próximo partido activo (esta app no tiene una única
    # fase global, cada confederación avanza por separado — ver fase_ya_iniciada
    # en fantasy_service.py para el mismo criterio aplicado del lado del backend)
    juego_activo, _ = obtener_juego_activo()
    fase_id = juego_activo.get("fase_id") if juego_activo else 1

    alineacion = obtener_alineacion(usuario["_id"], fase_id)

    # Carry-over: si el usuario todavía no armó equipo para esta fase "actual" (que puede haber
    # avanzado sin que el usuario cambiara nada, ver obtener_equipo_mas_reciente_anterior), se
    # precarga el builder con su equipo más reciente de una fase anterior en vez de mostrar una
    # alineación vacía. No se persiste nada todavía -- recién se crea un registro para esta fase
    # cuando el usuario aprieta "Guardar Alineación".
    equipo_heredado = None
    if not alineacion:
        equipo_heredado = obtener_equipo_mas_reciente_anterior(usuario["_id"], fase_id)

    lineup_para_builder = alineacion["lineup"] if alineacion else (equipo_heredado["lineup"] if equipo_heredado else [])
    formacion_inicial = alineacion["formacion"] if alineacion else (equipo_heredado["formacion"] if equipo_heredado else FORMACION_DEFAULT)

    jugadores_actuales = obtener_detalle_jugadores(lineup_para_builder) if lineup_para_builder else []
    historial_puntos = obtener_historial_puntos_fantasy(usuario["_id"], fase_id)
    desempeno_lineup = obtener_desempeno_lineup(usuario["_id"], fase_id, lineup_para_builder) if lineup_para_builder else {}

    return templates.TemplateResponse(
        request=request,
        name="fantasy_once_ideal.html",
        context={
            "fase_id": fase_id,
            "alineacion": alineacion,
            "equipo_heredado": equipo_heredado,
            "formacion_inicial": formacion_inicial,
            "jugadores_actuales_json": json.dumps(jugadores_actuales, ensure_ascii=False),
            "fase_iniciada": fase_ya_iniciada(fase_id),
            "paises": obtener_catalogo_paises(),
            "posiciones": obtener_catalogo_posiciones(),
            "formaciones_granulares_json": json.dumps(obtener_formaciones_granulares(), ensure_ascii=False),
            "historial_puntos": historial_puntos,
            # Claves como string ({{ ... | tojson }} las serializa así igual, pero json.dumps
            # con dict de claves int también las convierte a string) para que el JS las use
            # indexando por jugador.id (JS castea el número a string en el acceso [] igual).
            "desempeno_lineup_json": json.dumps(desempeno_lineup, ensure_ascii=False)
        }
    )
