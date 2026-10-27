from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from bson.errors import InvalidId
from schemas.fantasy_schema import LineupIn, OjeadorIn, FantasyTeamOut, JugadorBusquedaOut, HistorialPuntosOut
from services.fantasy_service import (
    set_fantasy_lineup, obtener_alineacion, buscar_jugadores, jornada_actual, obtener_escuadras, desbloquear_escuadra,
    estado_desbloqueo, escuadras_desbloqueadas, datos_usuario_fantasy, obtener_detalle_jugadores, obtener_catalogo_posiciones,
    obtener_catalogo_paises, obtener_catalogo_formaciones, obtener_historial_puntos_fantasy,
    CAMBIOS_GRATIS_POR_JORNADA, TOPE_CAMBIOS_GRATIS, COSTO_CAMBIO_EXTRA
)
from services import fantasy_rendimiento
from config import fantasy as CFF
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
        return set_fantasy_lineup(usuario["_id"], payload.lineup, payload.formacion, payload.escuadra)
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
    posicion_id: Optional[int] = Query(None, description="Filtrar por posición (id de la colección 'posiciones')"),
    leyendas: Optional[bool] = Query(None, description="true: solo leyendas; false: sin leyendas"),
    linea: Optional[str] = Query(None, description="PORTERO/DEFENSA/MEDIO/DELANTERO (si no se da posicion_id)")
):
    """
    Endpoint auxiliar (no pedido explícitamente, pero necesario para que la vista
    de armado del Once Ideal sea usable): busca jugadores por nombre/país/posición
    entre los >4000 disponibles, en vez de mandarlos todos de una al HTML.
    """
    return buscar_jugadores(q.strip(), pais_id=pais_id, posicion_id=posicion_id, leyendas=leyendas, linea=linea)


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


@route.post("/escuadras/desbloquear", name="fantasy_desbloquear")
def desbloquear(request: Request):
    """Desbloquea el siguiente equipo del Once Ideal (saldo + jornadas con el anterior; ver config/fantasy.py)."""
    usuario = obtener_usuario_actual(request)
    try:
        return desbloquear_escuadra(usuario["_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@route.get("/jugadores/{jugador_id}/ficha", name="fantasy_ficha_jugador")
def ficha_jugador(jugador_id: int, request: Request):
    """Ficha del jugador para la ventana del Once Ideal: forma, próximo partido, partido a partido y lo que te pagó."""
    usuario = obtener_usuario_actual(request)
    datos = fantasy_rendimiento.ficha(jugador_id, usuario["_id"])
    if not datos:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    return datos


@route.get("/jugadores/niveles", name="fantasy_niveles")
def niveles(ids: str = Query("", description="ids separados por coma")):
    """Nivel de forma de varios jugadores. Nunca espera: si todavía se calcula, responde calculando=true."""
    lista = [int(x) for x in ids.split(",") if x.strip().isdigit()][:60]
    datos = fantasy_rendimiento.niveles_de(lista)
    return {"calculando": not datos and bool(lista), "niveles": {str(k): v for k, v in datos.items()}}


@route.post("/ojeador", name="fantasy_ojeador")
def ojeador(payload: OjeadorIn, request: Request):
    """Sugerencias pagas del Ojeador para una posición (la misma consulta es gratis hasta el próximo partido)."""
    usuario = obtener_usuario_actual(request)
    try:
        return fantasy_rendimiento.consultar_ojeador(usuario["_id"], payload.posicion_id, payload.nivel, payload.escuadra)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================================================
# Vista HTML (requiere sesión iniciada — ver services/auth_service.py)
# ==========================================================================
@route_vistas.get("/", response_class=HTMLResponse, name="fantasy_home")
def fantasy_home(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    # Varios equipos por Mundial (uno por formación, se desbloquean de a uno); los cambios gratis se liberan por
    # jornada fantasy (cada N partidos jugados del Mundial), por equipo.
    escuadras = obtener_escuadras(usuario["_id"])
    ids = [j for e in escuadras for j in e["lineup"]]
    detalle = {j["id"]: j for j in obtener_detalle_jugadores(ids)}
    for e in escuadras:
        e["jugadores"] = [detalle[j] for j in e["lineup"] if j in detalle]
    eliminados = [j for j in detalle.values() if j["eliminado"]]
    usuario_db = datos_usuario_fantasy(usuario["_id"])
    desbloqueo = estado_desbloqueo(usuario_db, escuadras)
    config_js = {
        "escuadras": escuadras,
        "abiertas": escuadras_desbloqueadas(usuario_db),
        "maximo": CFF.ESCUADRAS_MAX,
        "desbloqueo": desbloqueo,
        "formaciones": obtener_catalogo_formaciones(),
        "lineaDePosicion": {str(k): v for k, v in CFF.LINEA_DE_POSICION.items()},
        "posiciones": obtener_catalogo_posiciones(),
        "ojeador": fantasy_rendimiento.niveles_ojeador(),
        "reglas": {"costoExtra": COSTO_CAMBIO_EXTRA, "maxPorPais": 2, "maxLeyendas": 1},
        "urls": {"guardar": str(request.url_for("fantasy_set_lineup")), "buscar": str(request.url_for("fantasy_buscar_jugadores")),
                 "desbloquear": str(request.url_for("fantasy_desbloquear")), "ojeador": str(request.url_for("fantasy_ojeador")),
                 "niveles": str(request.url_for("fantasy_niveles")), "ficha": "/fantasy/jugadores/{id}/ficha"},
    }
    return templates.TemplateResponse(
        request=request,
        name="fantasy_once_ideal.html",
        context={
            "escuadras": escuadras,
            "jornada": jornada_actual(),
            "reglas": {"cambios_por_jornada": CAMBIOS_GRATIS_POR_JORNADA, "tope": TOPE_CAMBIOS_GRATIS, "costo_extra": COSTO_CAMBIO_EXTRA,
                       "jornadas_desbloqueo": CFF.JORNADAS_PARA_DESBLOQUEAR, "pago": CFF.PAGO_POR_PARTIDO["MEDIO"]},
            "desbloqueo": desbloqueo,
            "total_puntos": sum(e["total_points_fase"] for e in escuadras),
            "total_ganado": sum(e["monto_ganado"] for e in escuadras),
            "eliminados_en_once": eliminados,
            "paises": obtener_catalogo_paises(),
            "posiciones": obtener_catalogo_posiciones(),
            "config_json": json.dumps(config_js, ensure_ascii=False, default=str).replace("</", "<\\/"),
            "historial_puntos": obtener_historial_puntos_fantasy(usuario["_id"]),
        }
    )
