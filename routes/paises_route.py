from fastapi import APIRouter, HTTPException
from fastapi import Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.paises_service import get_paises, get_pais, obtener_trayectoria_pais
from services.fanbase_service import obtener_historial_aficionados_pais, AFICIONADOS_INICIAL
from services.auth_service import context_usuario_actual
from config.settings import PREFIX_PAISES_PATH
import logging
import uuid
import json

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
route = APIRouter(prefix=PREFIX_PAISES_PATH)
tag='Mundial'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
process_uuid = uuid.uuid4()


@route.get("/", response_class=HTMLResponse)
async def paises(request: Request):
    try:
        paises = get_paises(logger)
            
        return templates.TemplateResponse(
            request=request,
            name="paises.html",
            context={"paises": paises, "prefix": PREFIX_PAISES_PATH, "aficionados_base": AFICIONADOS_INICIAL}
        )
    except FileNotFoundError:
        print(f"Error: No se encontró la coleccion de paises")
    except json.JSONDecodeError:
        print("Error: El archivo no tiene un formato JSON válido.")


@route.get("/{id}", response_class=HTMLResponse)
async def pais(request: Request, id: str):
    try:
        pais = get_pais(id, logger)
        historial_aficionados = obtener_historial_aficionados_pais(int(id)) if pais else []
        trayectoria = obtener_trayectoria_pais(int(id)) if pais else []

        return templates.TemplateResponse(
            request=request,
            name="pais.html",
            context={"pais": pais, "historial_aficionados": historial_aficionados, "aficionados_base": AFICIONADOS_INICIAL,
                     "trayectoria": trayectoria}
        )
    except FileNotFoundError:
        print(f"Error: No se encontró la coleccion de paises")
    except json.JSONDecodeError:
        print("Error: El archivo no tiene un formato JSON válido.")
