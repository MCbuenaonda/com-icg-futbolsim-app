from fastapi import APIRouter, HTTPException
from fastapi import Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.estadisticas_service import obtener_estadisticas_generales
from services.auth_service import context_usuario_actual
import logging
import uuid

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
route = APIRouter(prefix='/estadisticas')
tag='Mundial'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
process_uuid = uuid.uuid4()


@route.get("/", response_class=HTMLResponse, name="estadisticas")
async def inicio(request: Request):
    estadisticas = obtener_estadisticas_generales()
    return templates.TemplateResponse(
        request=request,
        name="estadisticas.html",
        context={
            "stats": estadisticas,
        }
    )