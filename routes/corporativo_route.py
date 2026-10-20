from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from services.auth_service import obtener_usuario_actual, context_usuario_actual
from services.imagenes_pais_service import GLOBALES_JINJA
from typing import Optional
from pydantic import BaseModel
from services.corporativo_service import obtener_ranking_ceos, obtener_mercado, obtener_perfil_corporativo, obtener_vista_inicio, renovar_contrato, rescindir_contrato
from services import corporativo_fichajes_service as fichajes
from services import corporativo_bolsa_service as bolsa
from services.corporativo_universo_service import crear_universo
from services import corporativo_carrera_service as carrera
import logging

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.globals.update(GLOBALES_JINJA)

# Corporativos Deportivos: carrera del usuario como CEO de un corporativo (reglas en config/corporativos.py).
# API (acciones, siempre sobre el usuario de la sesión) bajo /corporativos; vistas bajo /corporativo.
route = APIRouter(prefix="/corporativos", tags=["Corporativos"])
route_vistas = APIRouter(prefix="/corporativo", tags=["Corporativos"])

tag = 'Corporativos'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _usuario_api(request: Request) -> dict:
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión")
    return usuario


def _accion(funcion, *args):
    try:
        return funcion(*args)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Corporativos: error en {funcion.__name__}: {e}")
        raise HTTPException(status_code=500, detail="Error interno, intentá de nuevo")


@route_vistas.get("/", response_class=HTMLResponse, name="corporativo_inicio")
async def corporativo_inicio(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo.html", context=obtener_vista_inicio(usuario["_id"]))


@route_vistas.get("/mercado", response_class=HTMLResponse, name="corporativo_mercado")
async def corporativo_mercado(request: Request, tipo: str = "jugador", vista: str = "libres", q: str = "", conf: Optional[int] = None,
                              region: bool = False, edad_max: Optional[int] = None, orden: str = "valor", pagina: int = 1):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    datos = obtener_mercado(usuario["_id"], tipo, vista, q, conf, region, edad_max, orden, pagina)
    if not datos:
        return RedirectResponse(url=request.url_for("corporativo_inicio"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo_mercado.html", context=datos)


@route_vistas.get("/bolsa", response_class=HTMLResponse, name="corporativo_bolsa")
async def corporativo_bolsa(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    datos = bolsa.obtener_bolsa(usuario["_id"])
    if not datos:
        return RedirectResponse(url=request.url_for("corporativo_inicio"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo_bolsa.html", context=datos)


@route_vistas.get("/ranking", response_class=HTMLResponse, name="corporativo_ranking")
async def corporativo_ranking(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo_ranking.html",
                                      context={"filas": obtener_ranking_ceos(usuario["_id"])})


@route_vistas.get("/{sigla}", response_class=HTMLResponse, name="corporativo_perfil")
async def corporativo_perfil(sigla: str, request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    datos = obtener_perfil_corporativo(usuario["_id"], sigla.upper())
    if not datos:
        return RedirectResponse(url=request.url_for("corporativo_inicio"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo_perfil.html", context=datos)


@route.post("/activar", name="corporativos_activar")
async def activar(request: Request):
    """Entra al módulo: crea el universo del usuario y lo pone a buscar empleo."""
    usuario = _usuario_api(request)
    _accion(crear_universo, usuario["_id"])
    return {"ok": True}


@route.post("/ofertas/{oferta_id}/aceptar", name="corporativos_aceptar")
async def aceptar(oferta_id: str, request: Request):
    return _accion(carrera.aceptar_oferta, _usuario_api(request)["_id"], oferta_id)


@route.post("/ofertas/{oferta_id}/rechazar", name="corporativos_rechazar")
async def rechazar(oferta_id: str, request: Request):
    return _accion(carrera.rechazar_oferta, _usuario_api(request)["_id"], oferta_id)


@route.post("/renunciar", name="corporativos_renunciar")
async def renunciar(request: Request):
    return _accion(carrera.renunciar, _usuario_api(request)["_id"])


@route.post("/contratos/{contrato_id}/renovar", name="corporativos_renovar")
async def renovar(contrato_id: str, request: Request):
    return _accion(renovar_contrato, _usuario_api(request)["_id"], contrato_id)


@route.post("/contratos/{contrato_id}/rescindir", name="corporativos_rescindir")
async def rescindir(contrato_id: str, request: Request):
    return _accion(rescindir_contrato, _usuario_api(request)["_id"], contrato_id)


class OfertaFichaje(BaseModel):
    tipo: str
    ref_id: int
    prima: int
    duracion: int
    monto: int = 0


@route.post("/fichajes", name="corporativos_ofertar")
async def ofertar(oferta: OfertaFichaje, request: Request):
    """Oferta del CEO por un libre o (en ventana de traspasos) por un representado de un rival."""
    return _accion(fichajes.ofertar, _usuario_api(request)["_id"], oferta.tipo, oferta.ref_id, oferta.prima, oferta.duracion, oferta.monto)


@route.post("/fichajes/{oferta_id}/cancelar", name="corporativos_cancelar_oferta")
async def cancelar(oferta_id: str, request: Request):
    return _accion(fichajes.cancelar_oferta, _usuario_api(request)["_id"], oferta_id)


@route.post("/propuestas/{oferta_id}/{respuesta}", name="corporativos_responder")
async def responder(oferta_id: str, respuesta: str, request: Request):
    if respuesta not in ("aceptar", "rechazar"):
        raise HTTPException(status_code=400, detail="Respuesta inválida")
    return _accion(fichajes.responder, _usuario_api(request)["_id"], oferta_id, respuesta == "aceptar")


@route.post("/scouting", name="corporativos_scouting")
async def scouting(request: Request):
    return _accion(fichajes.scouting, _usuario_api(request)["_id"])


@route.post("/marketing", name="corporativos_marketing")
async def marketing(request: Request):
    return _accion(fichajes.marketing, _usuario_api(request)["_id"])


class OperacionBolsa(BaseModel):
    sigla: str
    cantidad: float


@route.post("/bolsa/comprar", name="corporativos_comprar_acciones")
async def comprar_acciones(op: OperacionBolsa, request: Request):
    return _accion(bolsa.comprar, _usuario_api(request)["_id"], op.sigla, int(op.cantidad))


@route.post("/bolsa/vender", name="corporativos_vender_acciones")
async def vender_acciones(op: OperacionBolsa, request: Request):
    return _accion(bolsa.vender, _usuario_api(request)["_id"], op.sigla, op.cantidad)


class Dividendo(BaseModel):
    fraccion: float


@route.post("/dividendo", name="corporativos_dividendo")
async def dividendo(d: Dividendo, request: Request):
    """El CEO en funciones reparte un dividendo de su corporativo."""
    return _accion(bolsa.repartir_dividendo, _usuario_api(request)["_id"], d.fraccion)
