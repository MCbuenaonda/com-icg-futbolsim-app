from fastapi import APIRouter, HTTPException
from fastapi import Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from typing import Optional
from services.jugadores_service import get_jugadores, get_jugador
from services.paises_service import get_pais
from services.jugador_analisis_service import buscar_jugadores, comparar_jugadores, obtener_bitacora_jugador
from services.especialidades_service import evolucion_jugador
from services.auth_service import context_usuario_actual
from services.imagenes_pais_service import GLOBALES_JINJA
from config.settings import PREFIX_JUGADORES_PATH
import logging
import uuid
import json

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.globals.update(GLOBALES_JINJA)
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
        pais = get_pais(id, logger)  # encabezado: nombre, escudo, confederación

        return templates.TemplateResponse(
            request=request,
            name="jugadores.html",
            context={"jugadores": jugadores, "pais": pais}
        )
    except FileNotFoundError:
        print(f"Error: No se encontró la coleccion de paises")
    except json.JSONDecodeError:
        print("Error: El archivo no tiene un formato JSON válido.")
        
# Estas dos rutas van ANTES de "/{id}" (si no, "/comparar" se interpretaría como un id)
@route.get("/comparar", response_class=HTMLResponse, name="comparar_jugadores")
def comparar(request: Request, a: Optional[int] = None, b: Optional[int] = None):
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
        evolucion = evolucion_jugador(jugador) if jugador else None   # especialidades: progreso, riesgo e historial
        parte_medico = None   # lesión vigente e historial (services/lesiones_service.py)
        if jugador:
            try:
                from services.lesiones_service import lesion_de, historial_de
                parte_medico = {"actual": lesion_de(jugador), "historial": historial_de(jugador.get("id"))}
            except Exception as e:
                print(f"No se pudo leer el parte médico: {e}")

        return templates.TemplateResponse(
            request=request,
            name="jugador.html",
            context={"jugador": jugador, "bitacora": bitacora, "evolucion": evolucion, "parte_medico": parte_medico}
        )
    except FileNotFoundError:
        print(f"Error: No se encontró la coleccion de paises")
    except json.JSONDecodeError:
        print("Error: El archivo no tiene un formato JSON válido.")
