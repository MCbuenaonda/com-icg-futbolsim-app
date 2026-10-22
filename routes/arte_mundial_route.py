"""
Póster y mascota de cada Mundial (services/arte_mundial_service.py):
  - route_imagenes  /mundial/arte/{anio}/poster.svg y /mascota.svg: sin permiso de sección (se usan como <img> en el
                    inicio, Palmarés, el álbum y En Vivo); caché del navegador, la URL lleva la versión del arte.
  - route_vistas    /mundial/arte (permiso 'palmares', es parte del archivo del torneo): póster grande, ficha de la
                    mascota y la galería de todos los Mundiales.
  - route_admin     /admin/arte-mundial (permiso 'gestion_usuarios'): 3 propuestas alternativas, elegir otra o pedir
                    otra tanda, solo antes de que se juegue el primer partido.
"""
import json
import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from services import arte_mundial_service as AS
from services.auth_service import context_usuario_actual
from services.imagenes_pais_service import GLOBALES_JINJA

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.globals.update(GLOBALES_JINJA)
route_imagenes = APIRouter(prefix="/mundial/arte", tags=["Arte del Mundial"])
route_vistas = APIRouter(prefix="/mundial", tags=["Arte del Mundial UI"])
route_admin = APIRouter(prefix="/admin/arte-mundial", tags=["Arte del Mundial (admin)"])
tag = "Mundial"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _svg(request: Request, svg):
    if not svg:
        raise HTTPException(status_code=404, detail="Ese Mundial todavía no tiene arte")
    etag = AS.etag(svg)
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=86400", "ETag": etag})


@route_imagenes.get("/{anio}/poster.svg", name="arte_poster")
def poster(request: Request, anio: int):
    return _svg(request, AS.svg_poster(anio))


@route_imagenes.get("/{anio}/mascota.svg", name="arte_mascota")
def mascota(request: Request, anio: int):
    return _svg(request, AS.svg_mascota(anio))


@route_vistas.get("/arte", response_class=HTMLResponse, name="arte_mundial")
def vista(request: Request, anio: int = None):
    actual = AS.arte_de(anio) if anio else AS.arte_activo()
    return templates.TemplateResponse(request=request, name="arte_mundial.html",
                                      context={"arte": actual, "historico": AS.historico()})


@route_admin.get("", response_class=HTMLResponse, name="admin_arte_mundial")
def admin(request: Request, tanda: int = 1, ok: str = "", error: str = ""):
    actual = AS.arte_activo()
    props = AS.propuestas(actual["anio"], tanda) if actual else []
    return templates.TemplateResponse(request=request, name="admin_arte_mundial.html", context={
        "arte": actual, "propuestas": props, "tanda": tanda, "puede_cambiar": bool(actual) and AS.puede_cambiar(actual["anio"]),
        "recetas_json": [json.dumps(p, ensure_ascii=False) for p in props], "ok": ok, "error": error})


@route_admin.get("/propuesta/{anio}/{tanda}/{indice}/{que}.svg", name="admin_arte_propuesta")
def propuesta_svg(request: Request, anio: int, tanda: int, indice: int, que: str):
    props = AS.propuestas(anio, tanda)
    if not (0 <= indice < len(props)) or que not in ("poster", "mascota"):
        raise HTTPException(status_code=404)
    return Response(AS.svg_de_receta(anio, props[indice], que), media_type="image/svg+xml",
                    headers={"Cache-Control": "private, max-age=3600"})


@route_admin.post("/elegir", name="admin_arte_elegir")
def elegir(anio: int = Form(...), tanda: int = Form(...), indice: int = Form(...)):
    props = AS.propuestas(anio, tanda)
    if not (0 <= indice < len(props)):
        return RedirectResponse(url="/admin/arte-mundial?error=Propuesta+inválida", status_code=303)
    try:
        AS.elegir(anio, props[indice])
    except ValueError as e:
        return RedirectResponse(url=f"/admin/arte-mundial?error={e}", status_code=303)
    return RedirectResponse(url="/admin/arte-mundial?ok=1", status_code=303)
