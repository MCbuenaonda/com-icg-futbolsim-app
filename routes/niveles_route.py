from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from services.auth_service import obtener_usuario_actual, context_usuario_actual
from services.imagenes_pais_service import GLOBALES_JINJA
from services.niveles_service import marcar_nivel_visto, obtener_progreso, reclamar_recompensa
import logging

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.globals.update(GLOBALES_JINJA)

# Niveles de Socio FIFAV: página "Mi Nivel" + reclamar recompensas (reglas en config/niveles.py)
route = APIRouter(prefix="/niveles", tags=["Niveles"])

tag = 'Niveles'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@route.get("/", response_class=HTMLResponse, name="niveles_vista")
async def niveles_vista(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    return templates.TemplateResponse(request=request, name="niveles.html",
                                      context={"progreso": obtener_progreso(usuario["_id"])})


@route.post("/reclamar/{nivel}", name="niveles_reclamar")
async def reclamar(nivel: int, request: Request):
    """Reclama la recompensa PENDIENTE de un nivel (siempre el usuario de la sesión)."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión")
    try:
        resultado = reclamar_recompensa(usuario["_id"], nivel)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al reclamar la recompensa del nivel {nivel}: {e}")
        raise HTTPException(status_code=500, detail="Error interno al reclamar la recompensa")
    return resultado


@route.post("/visto", name="niveles_visto")
async def visto(request: Request):
    """Cierra el aviso de "¡Subiste de nivel!" de base.html."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión")
    marcar_nivel_visto(usuario["_id"])
    return {"ok": True}
