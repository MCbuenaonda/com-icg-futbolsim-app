from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from bson.errors import InvalidId
from schemas.fantasy_schema import LineupIn, FantasyTeamOut, JugadorBusquedaOut, HistorialPuntosOut
from services.fantasy_service import (
    set_fantasy_lineup, obtener_alineacion, buscar_jugadores, jornada_actual,
    obtener_detalle_jugadores, obtener_catalogo_posiciones, obtener_catalogo_paises,
    obtener_formaciones_granulares, obtener_historial_puntos_fantasy, obtener_desempeno_lineup,
    FORMACION_DEFAULT, CAMBIOS_GRATIS_POR_JORNADA, TOPE_CAMBIOS_GRATIS, COSTO_CAMBIO_EXTRA
)
from services.auth_service import obtener_usuario_actual, context_usuario_actual, exigir_mismo_usuario_o_admin
from services.imagenes_pais_service import GLOBALES_JINJA
import logging
import json

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.globals.update(GLOBALES_JINJA)

# API JSON (contrato tal cual se pidió: /fantasy/lineup, /fantasy/lineup/{user_id}/{fase_id})
route = APIRouter(prefix="/fantasy", tags=["Fantasy"])

# Vista HTML para armar el Once Ideal
# (handlers `def`, no `async def`: hacen I/O bloqueante con pymongo y FastAPI los corre en su threadpool)
route_vistas = APIRouter(prefix="/once-ideal", tags=["Fantasy UI"])

tag = 'Fantasy'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==========================================================================
# API JSON
# ==========================================================================
@route.post("/lineup", name="fantasy_set_lineup")
def set_lineup(payload: LineupIn, request: Request):
    """Guarda el Once Ideal del usuario para el Mundial (uno solo, suma en todas las fases). Devuelve además el
    desglose de cambios: reemplazos gratis de eliminados, cambios gratis usados y extra cobrados.
    Siempre para el usuario de la sesión: el 'usuario_id' y el 'fase_id' del body se ignoran."""
    usuario = obtener_usuario_actual(request)
    try:
        return set_fantasy_lineup(usuario["_id"], payload.lineup, payload.formacion)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario o jugador inválido")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al guardar alineación fantasy: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al guardar la alineación")


@route.get("/lineup/{user_id}/{fase_id}", response_model=Optional[FantasyTeamOut], name="fantasy_get_lineup")
def get_lineup(user_id: str, fase_id: int, request: Request):
    """Devuelve el Once Ideal del usuario para el Mundial (null si todavía no armó ninguno). 'fase_id' se ignora (compatibilidad)."""
    exigir_mismo_usuario_o_admin(request, user_id)
    try:
        return obtener_alineacion(user_id, fase_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")


@route.get("/jugadores/buscar", response_model=List[JugadorBusquedaOut], name="fantasy_buscar_jugadores")
def buscar(
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
def points_history(user_id: str, fase_id: int, request: Request):
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
def fantasy_home(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    # Un solo Once Ideal por Mundial (ya no por fase: cada confederación avanza a su ritmo); los cambios
    # gratis se liberan por jornada fantasy (cada N partidos jugados del Mundial).
    alineacion = obtener_alineacion(usuario["_id"])
    lineup = alineacion["lineup"] if alineacion else []
    jugadores_actuales = obtener_detalle_jugadores(lineup) if lineup else []

    return templates.TemplateResponse(
        request=request,
        name="fantasy_once_ideal.html",
        context={
            "alineacion": alineacion,
            "jornada": jornada_actual(),
            "reglas": {"cambios_por_jornada": CAMBIOS_GRATIS_POR_JORNADA, "tope": TOPE_CAMBIOS_GRATIS, "costo_extra": COSTO_CAMBIO_EXTRA},
            "eliminados_en_once": [j for j in jugadores_actuales if j["eliminado"]],
            "formacion_inicial": alineacion["formacion"] if alineacion else FORMACION_DEFAULT,
            "jugadores_actuales_json": json.dumps(jugadores_actuales, ensure_ascii=False),
            "paises": obtener_catalogo_paises(),
            "posiciones": obtener_catalogo_posiciones(),
            "formaciones_granulares_json": json.dumps(obtener_formaciones_granulares(), ensure_ascii=False),
            "historial_puntos": obtener_historial_puntos_fantasy(usuario["_id"]),
            # Claves como string ({{ ... | tojson }} las serializa así igual, pero json.dumps
            # con dict de claves int también las convierte a string) para que el JS las use
            # indexando por jugador.id (JS castea el número a string en el acceso [] igual).
            "desempeno_lineup_json": json.dumps(obtener_desempeno_lineup(usuario["_id"], lineup) if lineup else {}, ensure_ascii=False)
        }
    )
