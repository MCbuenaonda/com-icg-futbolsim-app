from fastapi import APIRouter, HTTPException
from fastapi import Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from services.partidos_interes_service import destacados_de_pais
from services.paises_service import get_paises, get_pais, obtener_trayectoria_pais, obtener_partidos_pais, obtener_estadisticas_torneo, obtener_balance_pais
from services.probabilidades_service import probabilidades_pais
from services.tecnicos_service import tarjeta_pais
from services.jugadores_service import get_jugadores
from services.juegos_service import formatear_numero_compacto
from services.fanbase_service import obtener_historial_aficionados_pais, AFICIONADOS_INICIAL
from services.auth_service import context_usuario_actual
from services.imagenes_pais_service import GLOBALES_JINJA
from config.settings import PREFIX_PAISES_PATH
import logging
import uuid
import json

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.globals.update(GLOBALES_JINJA)
templates.env.filters["numero_compacto"] = formatear_numero_compacto
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
        partidos = obtener_partidos_pais(int(id)) if pais else {"ultimos": [], "proximo": None}
        balance = obtener_balance_pais(int(id)) if pais else []
        try:
            probabilidades = probabilidades_pais(int(id)) if pais else None
        except Exception as e:   # nunca rompe la ficha
            logger.error(f"Probabilidades del país {id}: {e}")
            probabilidades = None
        try:
            cuerpo_tecnico = tarjeta_pais(int(id)) if pais else None
        except Exception as e:   # nunca rompe la ficha
            logger.error(f"Cuerpo técnico del país {id}: {e}")
            cuerpo_tecnico = None
        try:   # en qué top 10 de /estadisticas aparece la selección y sus jugadores + sus líderes en el Mundial
            destacados = destacados_de_pais(int(id)) if pais else None
        except Exception as e:   # nunca rompe la ficha
            logger.error(f"Destacados del país {id}: {e}")
            destacados = None
        estadisticas = obtener_estadisticas_torneo(pais) if pais else {}
        # figuras de la plantilla: los 6 de mejor valoración (la plantilla completa está en /jugadores/pais/{id});
        # las leyendas (jugadores.leyenda, ~80) van en su propio bloque, si no se quedarían con las 6 figuras
        plantel = get_jugadores(id, logger) if pais else []
        figuras = sorted([j for j in plantel if not j.get("leyenda")], key=lambda j: -(j.get("overall") or 0))[:6]
        leyendas = sorted([j for j in plantel if j.get("leyenda")], key=lambda j: j.get("posicion_id") or 99)

        return templates.TemplateResponse(
            request=request,
            name="pais.html",
            context={"pais": pais, "historial_aficionados": historial_aficionados, "aficionados_base": AFICIONADOS_INICIAL,
                     "trayectoria": trayectoria, "partidos": partidos, "figuras": figuras, "leyendas": leyendas,
                     "estadisticas": estadisticas, "balance": balance,
                     "probabilidades": probabilidades, "cuerpo_tecnico": cuerpo_tecnico, "destacados": destacados,
                     "plantel_por_id": {j["id"]: j for j in plantel}}
        )
    except FileNotFoundError:
        print(f"Error: No se encontró la coleccion de paises")
    except json.JSONDecodeError:
        print("Error: El archivo no tiene un formato JSON válido.")
