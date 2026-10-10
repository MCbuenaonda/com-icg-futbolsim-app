"""
Vistas de consulta del torneo agregadas en la tanda de UX: Cara a Cara (/cara-a-cara),
Cuadro de eliminación (/cuadro) y Palmarés (/palmares). Cada router tiene su propio permiso
(config/secciones.py), aplicado en main.py.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from services.auth_service import context_usuario_actual
from services.cara_a_cara_service import listar_paises, obtener_cara_a_cara
from services.cuadro_service import obtener_cuadro
from services.palmares_service import obtener_palmares
from services.arbitros_service import listar_arbitros, perfil_arbitro
from services.ranking_usuarios_service import obtener_ranking_usuarios

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
route_cara_a_cara = APIRouter(prefix="/cara-a-cara", tags=["Cara a Cara UI"])
route_cuadro = APIRouter(prefix="/cuadro", tags=["Cuadro UI"])
route_palmares = APIRouter(prefix="/palmares", tags=["Palmarés UI"])
route_arbitros = APIRouter(prefix="/arbitros", tags=["Árbitros UI"])
route_ranking = APIRouter(prefix="/ranking", tags=["Ranking de usuarios UI"])
tag = 'Mundial'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@route_cara_a_cara.get("/", response_class=HTMLResponse, name="cara_a_cara")
async def cara_a_cara(request: Request, a: Optional[int] = None, b: Optional[int] = None):
    historial = obtener_cara_a_cara(a, b) if a is not None and b is not None else None
    return templates.TemplateResponse(
        request=request, name="cara_a_cara.html",
        context={"paises": listar_paises(), "a": a, "b": b, "h2h": historial}
    )


@route_cuadro.get("/", response_class=HTMLResponse, name="cuadro")
async def cuadro(request: Request):
    return templates.TemplateResponse(request=request, name="cuadro.html", context={"cuadro": obtener_cuadro()})


@route_palmares.get("/", response_class=HTMLResponse, name="palmares")
async def palmares(request: Request):
    return templates.TemplateResponse(request=request, name="palmares.html", context={"palmares": obtener_palmares()})


@route_arbitros.get("/", response_class=HTMLResponse, name="arbitros")
async def arbitros(request: Request):
    return templates.TemplateResponse(request=request, name="arbitros.html", context={"arbitros": listar_arbitros()})


@route_arbitros.get("/perfil", response_class=HTMLResponse, name="arbitro_perfil")
async def arbitro(request: Request, nombre: str):
    # Por query string: los nombres de árbitro tienen espacios y caracteres especiales
    return templates.TemplateResponse(request=request, name="arbitro.html", context={"arbitro": perfil_arbitro(nombre), "nombre": nombre})


@route_ranking.get("/", response_class=HTMLResponse, name="ranking_usuarios")
async def ranking(request: Request):
    return templates.TemplateResponse(request=request, name="ranking_usuarios.html", context={"filas": obtener_ranking_usuarios()})
