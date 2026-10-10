from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request, Query, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from bson.errors import InvalidId
from schemas.venue_schema import SedeOut, CiudadDisponibleOut
from services.venue_service import (
    obtener_ciudades_disponibles, buscar_ciudades_directorio, contar_ciudades_directorio,
    buy_city_venue, sell_city_venue, obtener_portafolio_sedes
)
from services.auth_service import obtener_usuario_actual, context_usuario_actual, exigir_mismo_usuario_o_admin
import logging

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])

# API JSON (contrato tal cual se pidió: /venues/buy, /venues/sell, /venues/my-portfolio, /venues/available)
route = APIRouter(prefix="/venues", tags=["Venues"])

# Vistas HTML: Directorio de Sedes / Mi Portafolio de Estadios
route_vistas = APIRouter(prefix="/sedes", tags=["Venues UI"])

tag = 'Venues'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==========================================================================
# API JSON
# ==========================================================================
@route.get("/available/{pais_id}", response_model=List[CiudadDisponibleOut], name="venues_available")
async def available(pais_id: int):
    """Ciudades de un país que todavía no tienen dueño, listas para patrocinar."""
    return obtener_ciudades_disponibles(pais_id)


@route.post("/buy/{ciudad_id}", response_model=SedeOut, status_code=201, name="venues_buy")
async def buy(request: Request, ciudad_id: int):
    """Compra/patrocina la ciudad `ciudad_id` para el usuario logueado (vía cookie de sesión)."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión para comprar una sede")

    try:
        return buy_city_venue(usuario["_id"], ciudad_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID inválido")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al comprar la sede {ciudad_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al procesar la compra")


@route.post("/sell/{ciudad_id}", response_model=SedeOut, name="venues_sell")
async def sell(request: Request, ciudad_id: int):
    """Vende la sede `ciudad_id` del usuario logueado, reembolsando el 80% de su costo de compra."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión para vender una sede")

    try:
        return sell_city_venue(usuario["_id"], ciudad_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID inválido")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al vender la sede {ciudad_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al procesar la venta")


@route.get("/my-portfolio/{user_id}", response_model=List[SedeOut], name="venues_portfolio")
async def my_portfolio(user_id: str, request: Request):
    """Sedes activas del usuario, con partidos alojados y ganancias totales."""
    exigir_mismo_usuario_o_admin(request, user_id)
    try:
        return obtener_portafolio_sedes(user_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")


@route.get("/buscar", response_model=List[CiudadDisponibleOut], name="venues_buscar")
async def buscar(request: Request, response: Response, q: str = Query("", description="Texto a buscar por ciudad o país"),
                 limite: int = Query(50, le=200), estado: str = Query("", description="'', disponible, mias u ocupada"),
                 saltar: int = Query(0, ge=0, description="Cuántos resultados saltear (paginación)")):
    """
    Endpoint adicional (no pedido explícitamente) que alimenta el buscador de la
    vista de Directorio: con >4000 ciudades no es viable mandarlas todas al
    template de una sola vez, así que el filtrado por texto se resuelve acá
    (mismo patrón que /fantasy/jugadores/buscar).
    """
    usuario = obtener_usuario_actual(request)
    usuario_id = usuario["_id"] if usuario else None
    # Total de coincidencias en un header, para "Mostrando N de TOTAL" sin cambiar el contrato de la respuesta
    response.headers["X-Total-Count"] = str(contar_ciudades_directorio(q, usuario_id, estado))
    return buscar_ciudades_directorio(q, usuario_id, limite, estado, saltar)


# ==========================================================================
# Vistas HTML (requieren sesión iniciada — ver services/auth_service.py)
# ==========================================================================
@route_vistas.get("/directorio", response_class=HTMLResponse, name="venues_directorio_vista")
async def directorio_vista(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    ciudades = buscar_ciudades_directorio("", usuario["_id"], limite=50)
    total = contar_ciudades_directorio("", usuario["_id"])

    return templates.TemplateResponse(
        request=request,
        name="directorio_sedes.html",
        context={"ciudades": ciudades, "total_ciudades": total}
    )


@route_vistas.get("/portafolio", response_class=HTMLResponse, name="venues_portafolio_vista")
async def portafolio_vista(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    sedes = obtener_portafolio_sedes(usuario["_id"])

    return templates.TemplateResponse(
        request=request,
        name="mi_portafolio_sedes.html",
        context={"sedes": sedes}
    )
