from fastapi import APIRouter, HTTPException
from fastapi import Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from config.settings import PREFIX_CONFEDERACIONES_PATH
from services.confederacion_service import get_confederacion
from services.auth_service import context_usuario_actual
import logging
import uuid
import json

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
route = APIRouter(prefix=PREFIX_CONFEDERACIONES_PATH)
tag='Mundial'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
process_uuid = uuid.uuid4()


@route.get("/{id}", response_class=HTMLResponse)
async def pais(request: Request, id: str):
    try:
        confederacion = get_confederacion(id, logger)
        
        return templates.TemplateResponse(
            request=request,
            name="confederacion.html",
            context={"confederacion": confederacion}
        )
    except FileNotFoundError:
        print(f"Error: No se encontró la confederacion")
    except json.JSONDecodeError:
        print("Error: El archivo no tiene un formato JSON válido.")
