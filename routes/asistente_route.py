from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
from services.auth_service import obtener_usuario_actual, context_usuario_actual
from services.imagenes_pais_service import GLOBALES_JINJA
from services import asistente_service
import logging

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.globals.update(GLOBALES_JINJA)

# Asistente virtual "El Profe": escaneo pagado con consejos accionables (services/asistente_service.py).
# Handlers 'def' (no async): el escaneo hace varias consultas pymongo bloqueantes.
route = APIRouter(prefix="/asistente", tags=["Asistente"])

tag = 'Asistente'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class MarcaIn(BaseModel):
    clave: str
    accion: str   # listo | descartar | deshacer


class ConsultaIn(BaseModel):
    nivel: str
    precio_esperado: Optional[int] = None   # el precio que mostraba la página (ver asistente_service.consultar)


@route.get("/", response_class=HTMLResponse, name="asistente_vista")
def asistente_vista(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    return templates.TemplateResponse(request=request, name="asistente.html",
                                      context={"vista": asistente_service.obtener_vista(usuario)})


@route.post("/consultar", name="asistente_consultar")
def consultar(datos: ConsultaIn, request: Request):
    """Cobra (si corresponde) y devuelve el informe. Siempre el usuario de la sesión."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión")
    try:
        return asistente_service.consultar(usuario, datos.nivel, datos.precio_esperado)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error en la consulta al asistente: {e}")
        raise HTTPException(status_code=500, detail="El Profe no pudo terminar el escaneo. Probá de nuevo en un momento.")


@route.get("/informe/{consulta_id}", name="asistente_informe")
def informe(consulta_id: str, request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión")
    doc = asistente_service.obtener_informe(usuario, consulta_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No se encontró ese informe")
    return doc


@route.get("/informe/{consulta_id}/seguimiento", name="asistente_seguimiento")
def seguimiento(consulta_id: str, request: Request):
    """Qué consejos ya se hicieron (detectado solo) o ya no aplican. Puede re-escanear: por eso va aparte del informe."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión")
    try:
        datos = asistente_service.obtener_seguimiento(usuario, consulta_id)
    except Exception as e:
        logger.error(f"Error en el seguimiento del informe {consulta_id}: {e}")
        raise HTTPException(status_code=500, detail="No se pudo revisar el informe")
    if datos is None:
        raise HTTPException(status_code=404, detail="No se encontró ese informe")
    return datos


@route.post("/informe/{consulta_id}/consejo", name="asistente_marcar")
def marcar(consulta_id: str, datos: MarcaIn, request: Request):
    """El usuario marca un consejo como listo, lo descarta o deshace la marca. Siempre sobre un informe propio."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión")
    try:
        return asistente_service.marcar_consejo(usuario, consulta_id, datos.clave, datos.accion)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
