from typing import List
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
from schemas.quiniela_schema import QuinielaConfigOut, CrearBoletoIn, BoletoOut
from services.quinielas_service import (
    obtener_configs_activas,
    crear_boleto_quiniela,
    obtener_boletos_usuario,
    obtener_rendimiento_quinielas
)
from services.juegos_service import obtener_juegos_programados
from services.auth_service import obtener_usuario_actual, context_usuario_actual, exigir_mismo_usuario_o_admin
import certifi
import logging

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')
templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])

# API JSON (contrato tal cual se definió: /pools/configs, /pools/tickets, /pools/tickets/user/{user_id})
route = APIRouter(prefix="/pools", tags=["Quinielas"])

# Vistas HTML para que un usuario logueado gestione sus quinielas desde el navegador
route_vistas = APIRouter(prefix="/quinielas", tags=["Quinielas UI"])

tag = 'Quinielas'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@route.get("/configs", response_model=List[QuinielaConfigOut], name="quinielas_configs")
async def listar_configs():
    """Lista los formatos de quiniela activos (3, 5, 10 partidos, etc.)."""
    return obtener_configs_activas()


@route.post("/tickets", response_model=BoletoOut, status_code=201, name="quinielas_crear_boleto")
async def crear_boleto(payload: CrearBoletoIn, request: Request):
    """Compra/registra un boleto de quiniela: valida saldo, partidos y descuenta los puntos.
    El boleto es SIEMPRE del usuario de la sesión: el 'usuario_id' del body se ignora (antes se
    usaba tal cual y permitía gastar el saldo de otra cuenta)."""
    usuario = obtener_usuario_actual(request)
    try:
        return crear_boleto_quiniela(
            usuario_id=usuario["_id"],
            quiniela_config_id=payload.quiniela_config_id,
            selecciones=[s.model_dump() for s in payload.selecciones]
        )
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario, quiniela o partido inválido")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al crear boleto de quiniela: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al procesar la compra")


@route.get("/tickets/user/{user_id}", response_model=List[BoletoOut], name="quinielas_boletos_usuario")
async def boletos_usuario(user_id: str, request: Request):
    """Lista las quinielas de un usuario y su estado (PENDIENTE / GANADA / PERDIDA)."""
    exigir_mismo_usuario_o_admin(request, user_id)
    try:
        return obtener_boletos_usuario(user_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")


# ==========================================================================
# Vistas HTML (requieren sesión iniciada — ver services/auth_service.py)
# ==========================================================================
@route_vistas.get("/", response_class=HTMLResponse, name="quinielas_home")
async def quinielas_home(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    mundial_activo = db["mundiales"].find_one({"activo": True})
    mundial_id = mundial_activo["_id"] if mundial_activo else None

    configs = obtener_configs_activas()
    partidos_disponibles = obtener_juegos_programados(db, mundial_id)

    return templates.TemplateResponse(
        request=request,
        name="quinielas.html",
        context={
            "configs": configs,
            "partidos": partidos_disponibles
        }
    )


@route_vistas.get("/mis-quinielas", response_class=HTMLResponse, name="quinielas_mias")
async def quinielas_mias(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    boletos = obtener_boletos_usuario(usuario["_id"])

    # Enriquecer selecciones (equipos/fecha del partido) y boletos (nombre de la
    # config) para mostrarlos en la vista, con una consulta batch por colección
    # en vez de una por partido/config (N+1)
    ids_juegos = {
        ObjectId(seleccion["juego_id"])
        for boleto in boletos
        for seleccion in boleto["selecciones"]
    }
    partidos_por_id = {}
    if ids_juegos:
        cursor = db["juegos"].find(
            {"_id": {"$in": list(ids_juegos)}},
            {"equipo_local": 1, "equipo_visitante": 1, "fecha": 1}
        )
        partidos_por_id = {str(j["_id"]): j for j in cursor}

    ids_configs = {ObjectId(boleto["quiniela_config_id"]) for boleto in boletos}
    configs_por_id = {}
    if ids_configs:
        cursor = db["quiniela_config"].find(
            {"_id": {"$in": list(ids_configs)}},
            {"nombre": 1, "cantidad_partidos": 1}
        )
        configs_por_id = {str(c["_id"]): c for c in cursor}

    for boleto in boletos:
        for seleccion in boleto["selecciones"]:
            seleccion["partido"] = partidos_por_id.get(seleccion["juego_id"])
        boleto["config"] = configs_por_id.get(boleto["quiniela_config_id"])

    return templates.TemplateResponse(
        request=request,
        name="mis_quinielas.html",
        context={"boletos": boletos}
    )



@route_vistas.get("/rendimiento", response_class=HTMLResponse, name="quinielas_rendimiento")
async def quinielas_rendimiento(request: Request):
    """Rendimiento del usuario como pronosticador (services/quinielas_service.obtener_rendimiento_quinielas)."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    return templates.TemplateResponse(
        request=request, name="quinielas_rendimiento.html",
        context={"rendimiento": obtener_rendimiento_quinielas(usuario["_id"])}
    )
