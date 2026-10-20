from fastapi import APIRouter, HTTPException
from fastapi import Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.estadisticas_service import obtener_estadisticas_generales, obtener_detalle_estadistica
from services.auth_service import context_usuario_actual
from services.imagenes_pais_service import GLOBALES_JINJA
import logging
import uuid

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.globals.update(GLOBALES_JINJA)
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

@route.get("/api/detalle", name="estadisticas_detalle")
async def detalle(tipo: str, id: int, metrica: str):
    """
    Detalle de una tarjeta o de una fila de los top 10 (lo abre el modal de estadisticas.html):
    quién es, cuánto suma en la métrica y en qué partidos del Mundial en curso sumó.
    """
    if tipo not in ("jugador", "seleccion"):
        raise HTTPException(status_code=400, detail="Tipo inválido: jugador o seleccion")
    try:
        datos = obtener_detalle_estadistica(tipo, id, metrica)
    except Exception as e:
        logger.error(f"Error al armar el detalle de estadística ({tipo}, {id}, {metrica}): {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al armar el detalle")
    if not datos:
        raise HTTPException(status_code=404, detail="No hay datos de esa estadística en este Mundial")
    return datos
