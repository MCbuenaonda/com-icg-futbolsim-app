from fastapi import APIRouter, HTTPException
from fastapi import Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from services.jugadores_service import get_jugadores, get_jugador
from services.jugador_analisis_service import buscar_jugadores, comparar_jugadores, obtener_bitacora_jugador
from services.auth_service import context_usuario_actual
from config.settings import PREFIX_JUGADORES_PATH
import logging
import uuid
import json

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
route = APIRouter(prefix=PREFIX_JUGADORES_PATH)
tag='Mundial'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
process_uuid = uuid.uuid4()


# @route.get("/", response_class=HTMLResponse)
# async def paises(request: Request):
#     try:
#         paises = get_paises(logger)
            
#         return templates.TemplateResponse(
#             request=request,
#             name="paises.html",
#             context={"paises": paises, "prefix": PREFIX_PAISES_PATH}
#         )
#     except FileNotFoundError:
#         print(f"Error: No se encontró la coleccion de paises")
#     except json.JSONDecodeError:
#         print("Error: El archivo no tiene un formato JSON válido.")


@route.get("/pais/{id}", response_class=HTMLResponse)
async def jugadores(request: Request, id: str):
    try:
        jugadores = get_jugadores(id, logger)
            
        return templates.TemplateResponse(
            request=request,
            name="jugadores.html",
            context={"jugadores": jugadores}
        )
    except FileNotFoundError:
        print(f"Error: No se encontró la coleccion de paises")
    except json.JSONDecodeError:
        print("Error: El archivo no tiene un formato JSON válido.")
        
# Estas dos rutas van ANTES de "/{id}" (si no, "/comparar" se interpretaría como un id)
@route.get("/comparar", response_class=HTMLResponse, name="comparar_jugadores")
async def comparar(request: Request, a: Optional[int] = None, b: Optional[int] = None):
    comparacion = comparar_jugadores(a, b) if a and b else None
    return templates.TemplateResponse(request=request, name="comparar_jugadores.html",
                                      context={"comparacion": comparacion, "a": a, "b": b})


@route.get("/api/buscar", name="buscar_jugadores_api")
async def buscar(q: str = ""):
    """Buscador del comparador (JSON): por nombre, mínimo 2 letras."""
    return buscar_jugadores(q)


@route.get("/{id}", response_class=HTMLResponse)
async def jugador(request: Request, id: str):
    try:
        jugador = get_jugador(id, logger)
        bitacora = obtener_bitacora_jugador(jugador) if jugador else None

        return templates.TemplateResponse(
            request=request,
            name="jugador.html",
            context={"jugador": jugador, "bitacora": bitacora}
        )
    except FileNotFoundError:
        print(f"Error: No se encontró la coleccion de paises")
    except json.JSONDecodeError:
        print("Error: El archivo no tiene un formato JSON válido.")
