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
# Los handlers son `def` (no `async def`) a propósito: hacen I/O bloqueante con pymongo (poner_al_dia puede procesar
# varios ciclos) y FastAPI los corre en su threadpool; con `async def` una espera larga congelaba el servidor entero.
route = APIRouter(prefix="/corporativos", tags=["Corporativos"])
route_vistas = APIRouter(prefix="/corporativo", tags=["Corporativos"])

tag = 'Corporativos'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _usuario_api(request: Request) -> dict:
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitas iniciar sesión")
    return usuario


def _accion(funcion, *args):
    try:
        return funcion(*args)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Corporativos: error en {funcion.__name__}: {e}")
        raise HTTPException(status_code=500, detail="Error interno, intenta de nuevo")


@route_vistas.get("/", response_class=HTMLResponse, name="corporativo_inicio")
def corporativo_inicio(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo.html", context=obtener_vista_inicio(usuario["_id"]))


def _entero(valor: Optional[str], defecto: Optional[int] = None) -> Optional[int]:
    """Los filtros llegan del formulario como texto: vacío o inválido = sin filtro (antes daba error 422)."""
    try:
        return int(str(valor).strip()) if valor not in (None, "") else defecto
    except (TypeError, ValueError):
        return defecto


def _bandera(valor: Optional[str]) -> bool:
    return str(valor or "").strip().lower() in ("1", "true", "on", "si", "sí", "yes")


@route_vistas.get("/mercado", response_class=HTMLResponse, name="corporativo_mercado")
def corporativo_mercado(request: Request, tipo: str = "jugador", vista: str = "libres", q: str = "", conf: Optional[str] = None,
                        region: Optional[str] = None, edad_max: Optional[str] = None, orden: str = "valor", pagina: Optional[str] = None,
                        leyendas: Optional[str] = None, pronto: Optional[str] = None):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    datos = obtener_mercado(usuario["_id"], tipo, vista, (q or "").strip(), _entero(conf), _bandera(region), _entero(edad_max),
                            orden or "valor", max(1, _entero(pagina, 1)), _bandera(leyendas), _bandera(pronto))
    if not datos:
        return RedirectResponse(url=request.url_for("corporativo_inicio"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo_mercado.html", context=datos)


@route_vistas.get("/bolsa", response_class=HTMLResponse, name="corporativo_bolsa")
def corporativo_bolsa(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    datos = bolsa.obtener_bolsa(usuario["_id"])
    if not datos:
        return RedirectResponse(url=request.url_for("corporativo_inicio"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo_bolsa.html", context=datos)


@route_vistas.get("/ranking", response_class=HTMLResponse, name="corporativo_ranking")
def corporativo_ranking(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo_ranking.html",
                                      context={"filas": obtener_ranking_ceos(usuario["_id"])})


@route_vistas.get("/marcas", response_class=HTMLResponse, name="corporativo_marcas")
def corporativo_marcas(request: Request):
    from services import corporativo_marcas_service as marcas
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    datos = marcas.vista_marcas(usuario["_id"])
    if not datos:
        return RedirectResponse(url=request.url_for("corporativo_inicio"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo_marcas.html", context=datos)


@route_vistas.get("/televisoras", response_class=HTMLResponse, name="corporativo_televisoras")
def corporativo_televisoras(request: Request):
    from services import corporativo_tv_service as tv
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    datos = tv.vista_televisoras(usuario["_id"])
    if not datos:
        return RedirectResponse(url=request.url_for("corporativo_inicio"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo_televisoras.html", context=datos)


@route_vistas.get("/{sigla}", response_class=HTMLResponse, name="corporativo_perfil")
def corporativo_perfil(sigla: str, request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    datos = obtener_perfil_corporativo(usuario["_id"], sigla.upper())
    if not datos:
        return RedirectResponse(url=request.url_for("corporativo_inicio"), status_code=303)
    return templates.TemplateResponse(request=request, name="corporativo_perfil.html", context=datos)


@route.post("/activar", name="corporativos_activar")
def activar(request: Request):
    """Entra al módulo: crea el universo del usuario y lo pone a buscar empleo."""
    usuario = _usuario_api(request)
    _accion(crear_universo, usuario["_id"])
    return {"ok": True}


@route.post("/ofertas/{oferta_id}/aceptar", name="corporativos_aceptar")
def aceptar(oferta_id: str, request: Request):
    return _accion(carrera.aceptar_oferta, _usuario_api(request)["_id"], oferta_id)


@route.post("/ofertas/{oferta_id}/rechazar", name="corporativos_rechazar")
def rechazar(oferta_id: str, request: Request):
    return _accion(carrera.rechazar_oferta, _usuario_api(request)["_id"], oferta_id)


@route.post("/renunciar", name="corporativos_renunciar")
def renunciar(request: Request):
    return _accion(carrera.renunciar, _usuario_api(request)["_id"])


@route.post("/contratos/{contrato_id}/renovar", name="corporativos_renovar")
def renovar(contrato_id: str, request: Request):
    return _accion(renovar_contrato, _usuario_api(request)["_id"], contrato_id)


@route.post("/contratos/{contrato_id}/rescindir", name="corporativos_rescindir")
def rescindir(contrato_id: str, request: Request):
    return _accion(rescindir_contrato, _usuario_api(request)["_id"], contrato_id)


class OfertaFichaje(BaseModel):
    tipo: str
    ref_id: int
    prima: int
    duracion: int
    monto: int = 0


@route.post("/fichajes", name="corporativos_ofertar")
def ofertar(oferta: OfertaFichaje, request: Request):
    """Oferta del CEO por un libre o (en ventana de traspasos) por un representado de un rival."""
    return _accion(fichajes.ofertar, _usuario_api(request)["_id"], oferta.tipo, oferta.ref_id, oferta.prima, oferta.duracion, oferta.monto)


@route.post("/fichajes/{oferta_id}/cancelar", name="corporativos_cancelar_oferta")
def cancelar(oferta_id: str, request: Request):
    return _accion(fichajes.cancelar_oferta, _usuario_api(request)["_id"], oferta_id)


@route.post("/propuestas/{oferta_id}/{respuesta}", name="corporativos_responder")
def responder(oferta_id: str, respuesta: str, request: Request):
    if respuesta not in ("aceptar", "rechazar"):
        raise HTTPException(status_code=400, detail="Respuesta inválida")
    return _accion(fichajes.responder, _usuario_api(request)["_id"], oferta_id, respuesta == "aceptar")


@route.post("/scouting", name="corporativos_scouting")
def scouting(request: Request):
    return _accion(fichajes.scouting, _usuario_api(request)["_id"])


# --- Marcas y patrocinios (services/corporativo_marcas_service.py; reemplazan al acuerdo publicitario) ---
class PromoverIn(BaseModel):
    marca_id: int


@route.get("/contratos/{contrato_id}/marcas", name="corporativos_marcas_interesadas")
def marcas_interesadas(contrato_id: str, request: Request):
    from services import corporativo_marcas_service as marcas
    return _accion(marcas.interesadas, _usuario_api(request)["_id"], contrato_id)


@route.post("/contratos/{contrato_id}/promover", name="corporativos_promover")
def promover(contrato_id: str, datos: PromoverIn, request: Request):
    from services import corporativo_marcas_service as marcas
    return _accion(marcas.promover, _usuario_api(request)["_id"], contrato_id, datos.marca_id)


@route.post("/patrocinios/{pat_id}/{respuesta}", name="corporativos_responder_patrocinio")
def responder_patrocinio(pat_id: str, respuesta: str, request: Request):
    from services import corporativo_marcas_service as marcas
    if respuesta not in ("aceptar", "rechazar"):
        raise HTTPException(status_code=400, detail="Respuesta inválida")
    return _accion(marcas.responder_oferta, _usuario_api(request)["_id"], pat_id, respuesta == "aceptar")


# --- Televisoras (services/corporativo_tv_service.py) ---
@route.get("/televisoras/{tele_id}", name="corporativos_televisora")
def televisora_ficha(tele_id: int, request: Request):
    from services import corporativo_tv_service as tv
    datos = _accion(tv.ficha, _usuario_api(request)["_id"], tele_id)
    if not datos:
        raise HTTPException(status_code=404, detail="Esa televisora no existe")
    return datos


@route.get("/tv-contrato/{tv_id}", name="corporativos_contrato_tv")
def contrato_tv(tv_id: str, request: Request):
    from services import corporativo_tv_service as tv
    datos = _accion(tv.detalle_contrato, _usuario_api(request)["_id"], tv_id)
    if not datos:
        raise HTTPException(status_code=404, detail="Ese contrato ya no está disponible")
    return datos


@route.post("/entrevistas/{entrevista_id}/{postura}", name="corporativos_entrevista")
def responder_entrevista(entrevista_id: str, postura: str, request: Request):
    from services import corporativo_prensa_service as prensa_corp
    return _accion(prensa_corp.responder, _usuario_api(request)["_id"], entrevista_id, postura)


@route.post("/tv/{tv_id}/{respuesta}", name="corporativos_responder_tv")
def responder_tv(tv_id: str, respuesta: str, request: Request):
    from services import corporativo_tv_service as tv
    if respuesta not in ("aceptar", "rechazar"):
        raise HTTPException(status_code=400, detail="Respuesta inválida")
    return _accion(tv.responder, _usuario_api(request)["_id"], tv_id, respuesta == "aceptar")


# --- Giras (services/corporativo_acciones_service.py) ---
class GiraIn(BaseModel):
    contratos: list[str]


@route.get("/giras/jugadores", name="corporativos_giras_jugadores")
def giras_jugadores(request: Request):
    from services import corporativo_acciones_service as acciones
    return _accion(acciones.giras_jugadores, _usuario_api(request)["_id"])


@route.post("/giras", name="corporativos_gira_jugadores")
def gira_jugadores(datos: GiraIn, request: Request):
    from services import corporativo_acciones_service as acciones
    return _accion(acciones.organizar_gira_jugadores, _usuario_api(request)["_id"], datos.contratos)


@route.get("/contratos/{contrato_id}/gira", name="corporativos_cotizar_gira")
def cotizar_gira(contrato_id: str, request: Request):
    from services import corporativo_acciones_service as acciones
    return _accion(acciones.cotizar_gira, _usuario_api(request)["_id"], contrato_id)


@route.post("/contratos/{contrato_id}/gira", name="corporativos_organizar_gira")
def organizar_gira(contrato_id: str, request: Request):
    from services import corporativo_acciones_service as acciones
    return _accion(acciones.organizar_gira, _usuario_api(request)["_id"], contrato_id)


@route.post("/marketing", name="corporativos_marketing")
def marketing(request: Request):
    return _accion(fichajes.marketing, _usuario_api(request)["_id"])


class OperacionBolsa(BaseModel):
    sigla: str
    cantidad: float


@route.post("/bolsa/comprar", name="corporativos_comprar_acciones")
def comprar_acciones(op: OperacionBolsa, request: Request):
    return _accion(bolsa.comprar, _usuario_api(request)["_id"], op.sigla, int(op.cantidad))


@route.post("/bolsa/vender", name="corporativos_vender_acciones")
def vender_acciones(op: OperacionBolsa, request: Request):
    return _accion(bolsa.vender, _usuario_api(request)["_id"], op.sigla, op.cantidad)


class Dividendo(BaseModel):
    fraccion: float


@route.post("/dividendo", name="corporativos_dividendo")
def dividendo(d: Dividendo, request: Request):
    """El CEO en funciones reparte un dividendo de su corporativo."""
    return _accion(bolsa.repartir_dividendo, _usuario_api(request)["_id"], d.fraccion)
