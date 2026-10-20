from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from bson.errors import InvalidId
from schemas.album_schema import PackPurchaseOut, ColeccionOut
from services.album_service import buy_and_open_pack, obtener_coleccion_usuario, obtener_album_pagina, numero_pagina_de_pais, COSTO_SOBRE, CATEGORIAS_ESTAMPA
from services.auth_service import obtener_usuario_actual, context_usuario_actual, exigir_mismo_usuario_o_admin
from services.imagenes_pais_service import GLOBALES_JINJA
from services.juegos_service import formatear_numero_compacto
import logging

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.globals.update(GLOBALES_JINJA)
templates.env.filters["numero_compacto"] = formatear_numero_compacto  # reverso de las estampas de país

# API JSON (contrato tal cual se pidió: /album/open-pack, /album/collection/{user_id})
route = APIRouter(prefix="/album", tags=["Album"])

# Vistas HTML: abrir sobres / ver colección
route_vistas = APIRouter(prefix="/album-estampas", tags=["Album UI"])

tag = 'Album'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==========================================================================
# API JSON
# ==========================================================================
@route.post("/open-pack", response_model=PackPurchaseOut, status_code=201, name="album_open_pack")
async def open_pack(request: Request, origen: str = "COMPRA"):
    """
    Compra y abre un sobre (100 pts) para el usuario logueado (vía cookie de sesión). Con
    ?origen=GRATIS|PLATINO abre uno de los sobres de regalo de las recompensas de nivel.
    """
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión para abrir un sobre")

    try:
        return buy_and_open_pack(usuario["_id"], origen=origen.upper())
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID inválido")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al abrir sobre: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al abrir el sobre")


@route.get("/collection/{user_id}", response_model=ColeccionOut, name="album_collection")
async def collection(user_id: str, request: Request):
    """Estampas poseídas por el usuario y % de llenado de jugadores por país."""
    exigir_mismo_usuario_o_admin(request, user_id)
    try:
        return obtener_coleccion_usuario(user_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")


# ==========================================================================
# Vistas HTML (requieren sesión iniciada — ver services/auth_service.py)
# ==========================================================================
@route_vistas.get("/sobres", response_class=HTMLResponse, name="album_sobres_vista")
async def sobres_vista(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="album_sobres.html",
        context={"costo_sobre": COSTO_SOBRE, "categorias": CATEGORIAS_ESTAMPA, "sobres_gratis": int(usuario.get("sobres_gratis") or 0),
                 "sobres_platino": int(usuario.get("sobres_platino") or 0)}
    )


@route_vistas.get("/coleccion", response_class=HTMLResponse, name="album_coleccion_vista")
async def coleccion_vista(request: Request, pagina: int = 1, pais: Optional[int] = None):
    """Álbum de 211 páginas (una por país). ?pagina=N o ?pais=<id> abre directo en esa página."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    if pais is not None:
        pagina = numero_pagina_de_pais(pais) or pagina
    album = obtener_album_pagina(str(usuario["_id"]), pagina)

    return templates.TemplateResponse(
        request=request,
        name="album_coleccion.html",
        context={"album": album}
    )


@route_vistas.get("/coleccion/pagina/{numero}", response_class=HTMLResponse, name="album_pagina_vista")
async def pagina_vista(numero: int, request: Request):
    """Solo la hoja del álbum (HTML suelto): la usa el hojeo de album_coleccion.html sin recargar la página."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Sesión expirada")

    album = obtener_album_pagina(str(usuario["_id"]), numero)
    return templates.TemplateResponse(
        request=request,
        name="partials/album_pagina.html",
        context={"album": album}
    )
