from typing import List
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from schemas.fanbase_schema import PaisFanbaseOut
from services.fanbase_service import obtener_ranking_aficionados
from services.auth_service import context_usuario_actual
import logging

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])

# API JSON (contrato tal cual se pidió: GET /countries/fanbase-ranking)
route = APIRouter(prefix="/countries", tags=["Fanbase"])

# Vista HTML: ranking de popularidad
route_vistas = APIRouter(prefix="/aficionados", tags=["Fanbase UI"])

tag = 'Fanbase'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==========================================================================
# API JSON
# ==========================================================================
@route.get("/fanbase-ranking", response_model=List[PaisFanbaseOut], name="fanbase_ranking")
async def fanbase_ranking():
    """Selecciones ordenadas de mayor a menor por cantidad de aficionados, independiente del ranking FIFA."""
    return obtener_ranking_aficionados()


# ==========================================================================
# Vista HTML
# ==========================================================================
@route_vistas.get("/", response_class=HTMLResponse, name="fanbase_ranking_view")
async def fanbase_ranking_view(request: Request):
    ranking = obtener_ranking_aficionados()
    return templates.TemplateResponse(
        request=request,
        name="aficionados.html",
        context={"ranking": ranking}
    )
