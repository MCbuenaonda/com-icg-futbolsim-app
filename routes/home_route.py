from fastapi import APIRouter, HTTPException
from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from config.settings import PREFIX_HOME_PATH
from services.mundial_service import crear_nuevo_mundial, restart_mundial, get_data_dashboard_stats, obtener_ordinal_mundial_actual, formatear_ordinal_torneo
from services.juegos_service import get_data_dashboard_last_games, get_data_fase_actual_dashboard, get_data_clasificados_mundial, formatear_numero_compacto, ICONO_ESTADO_ANIMO
from services.confederacion_service import get_data_confederaciones_dashboard
from services.auth_service import context_usuario_actual
import logging
import uuid

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.filters["numero_compacto"] = formatear_numero_compacto
templates.env.filters["ordinal_torneo"] = formatear_ordinal_torneo
# Diccionario estado_animo -> ícono, expuesto como global (no filtro) para poder usar
# '.get(clave, default)' directamente en la plantilla (ver templates/home.html)
templates.env.globals["icono_estado_animo"] = ICONO_ESTADO_ANIMO
route = APIRouter()
tag='Mundial'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
process_uuid = uuid.uuid4()


@route.get("/", response_class=HTMLResponse, name="home")
async def inicio(request: Request):
    resp_mundial = crear_nuevo_mundial()
    mundial = resp_mundial.get('data')
    ordinal_mundial = obtener_ordinal_mundial_actual()

    # Datos simulados para alimentar el Dashboard
    stats = get_data_dashboard_stats(mundial)
    ultimos_partidos = get_data_dashboard_last_games()
    fase_actual = get_data_fase_actual_dashboard()
    confederaciones = get_data_confederaciones_dashboard(mundial)

    # obtenemos los paises calificados al mundial
    clasificados = get_data_clasificados_mundial()
    
    stats["clasificados_count"] = len(clasificados)
    
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "mundial": mundial,
            "ordinal_mundial": ordinal_mundial,
            "stats": stats,
            "fase_actual": fase_actual,
            "confederaciones": confederaciones,
            "ultimos_partidos": ultimos_partidos,
            "clasificados": clasificados
        }
    )

@route.get("/restart", name="home_restart")
async def reinicio(request: Request):
    # limpieza de tablas
    restart_mundial()
    return RedirectResponse(url=request.url_for("home"), status_code=303)

