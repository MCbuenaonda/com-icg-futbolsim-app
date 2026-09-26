from typing import List, Optional
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from bson.errors import InvalidId
from schemas.ownership_schema import SeleccionMercadoOut, InversionOut
from services.ownership_service import obtener_mercado, buy_team, sell_team, obtener_portafolio
from services.auth_service import obtener_usuario_actual, context_usuario_actual
import logging

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])

# API JSON (contrato tal cual se pidió: /ownership/buy, /ownership/sell, /ownership/my-portfolio, /ownership/market)
route = APIRouter(prefix="/ownership", tags=["Ownership"])

# Vistas HTML: Mercado de Selecciones / Mi Portafolio
route_vistas = APIRouter(prefix="/selecciones", tags=["Ownership UI"])

tag = 'Ownership'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mismo catálogo ya usado en confederacion_service.get_data_confederaciones_dashboard,
# solo para poblar el filtro del mercado (no depende de esa función porque esa
# también agrega estadísticas de partidos que acá no hacen falta)
CONFEDERACIONES = [
    {"id": 1, "sigla": "UEFA", "nombre": "Europa"},
    {"id": 2, "sigla": "CONMEBOL", "nombre": "Sudamérica"},
    {"id": 3, "sigla": "CONCACAF", "nombre": "Norte, Centroamérica y Caribe"},
    {"id": 4, "sigla": "CAF", "nombre": "África"},
    {"id": 5, "sigla": "OFC", "nombre": "Oceanía"},
    {"id": 6, "sigla": "AFC", "nombre": "Asia"},
]


# ==========================================================================
# API JSON
# ==========================================================================
@route.get("/market", response_model=List[SeleccionMercadoOut], name="ownership_market")
async def market(confederacion_id: Optional[int] = Query(None, description="Filtrar por confederación")):
    """Lista las selecciones sin dueño disponibles para comprar, ordenadas por confederación y valor."""
    return obtener_mercado(confederacion_id)


@route.post("/buy/{pais_id}", response_model=InversionOut, status_code=201, name="ownership_buy")
async def buy(request: Request, pais_id: int):
    """Compra la selección `pais_id` para el usuario logueado (vía cookie de sesión)."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión para comprar una selección")

    try:
        return buy_team(usuario["_id"], pais_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID inválido")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al comprar la selección {pais_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al procesar la compra")


@route.post("/sell/{pais_id}", response_model=InversionOut, name="ownership_sell")
async def sell(request: Request, pais_id: int):
    """Vende la selección `pais_id` del usuario logueado al valor de mercado actual."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión para vender una selección")

    try:
        return sell_team(usuario["_id"], pais_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID inválido")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al vender la selección {pais_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al procesar la venta")


@route.get("/my-portfolio/{user_id}", response_model=List[InversionOut], name="ownership_portfolio")
async def my_portfolio(user_id: str):
    """Selecciones activas del usuario, con valor de compra, valor actual y plusvalía."""
    try:
        return obtener_portafolio(user_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")


# ==========================================================================
# Vistas HTML (requieren sesión iniciada — ver services/auth_service.py)
# ==========================================================================
@route_vistas.get("/mercado", response_class=HTMLResponse, name="ownership_mercado_vista")
async def mercado_vista(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    selecciones = obtener_mercado()

    return templates.TemplateResponse(
        request=request,
        name="mercado_selecciones.html",
        context={
            "selecciones": selecciones,
            "confederaciones": CONFEDERACIONES
        }
    )


@route_vistas.get("/portafolio", response_class=HTMLResponse, name="ownership_portafolio_vista")
async def portafolio_vista(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    inversiones = obtener_portafolio(usuario["_id"])

    return templates.TemplateResponse(
        request=request,
        name="mi_portafolio.html",
        context={"inversiones": inversiones}
    )
