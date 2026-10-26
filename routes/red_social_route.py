from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.auth_service import context_usuario_actual, obtener_usuario_actual
from services.imagenes_pais_service import GLOBALES_JINJA
from services.juegos_service import formatear_numero_compacto, ICONO_ESTADO_ANIMO
from services import red_social_service as RS
import logging

# Red social de la FIFAV: posts de los partidos (todos) + publicaciones de las marcas del universo del usuario
# (services/red_social_service.py). Mismo permiso que el inicio. Handlers `def`: consultas bloqueantes a Mongo.
templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.globals.update(GLOBALES_JINJA)
templates.env.filters["numero_compacto"] = formatear_numero_compacto
templates.env.globals["icono_estado_animo"] = ICONO_ESTADO_ANIMO
route = APIRouter(prefix="/red-social", tags=["Red social"])
tag = 'Red social'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@route.get("/", response_class=HTMLResponse, name="red_social")
def red_social(request: Request, q: str = "", filtro: str = "todo"):
    usuario = obtener_usuario_actual(request)
    RS.poner_al_dia_en_segundo_plano(str(usuario["_id"]) if usuario else None)
    datos = RS.publicaciones(usuario, q, filtro)
    return templates.TemplateResponse(request=request, name="red_social.html", context={
        **datos, "q": q, "filtro": filtro if filtro in RS.FILTROS else "todo", "filtros": RS.FILTROS,
        "lateral": RS.barra_lateral(usuario)})


@route.get("/mas", response_class=HTMLResponse, name="red_social_mas")
def red_social_mas(request: Request, antes: str, q: str = "", filtro: str = "todo"):
    """La página siguiente (HTML suelto para «Cargar más»)."""
    datos = RS.publicaciones(obtener_usuario_actual(request), q, filtro, antes)
    return templates.TemplateResponse(request=request, name="partials/red_social_lista.html", context={**datos, "q": q, "filtro": filtro},
                                      headers={"X-Siguiente": datos["siguiente"] or ""})
