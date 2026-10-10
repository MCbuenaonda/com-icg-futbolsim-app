from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from config.secciones import pagina_inicial
from config.settings import COOKIE_SECURE
from services.auth_service import (
    autenticar_usuario,
    crear_token_sesion,
    permisos_de_rol,
    RUTA_CAMBIAR_PASSWORD,
    obtener_usuario_actual,
    context_usuario_actual,
    SESION_COOKIE,
    SESION_DURACION_SEGUNDOS
)
from services.account_service import obtener_resumen_cuenta
from services.usuarios_service import GestionUsuariosError, cambiar_password_propia
import logging

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
route = APIRouter()
tag = 'Auth'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _set_cookie_sesion(respuesta: RedirectResponse, usuario: dict) -> RedirectResponse:
    token = crear_token_sesion(usuario)
    respuesta.set_cookie(
        key=SESION_COOKIE,
        value=token,
        max_age=SESION_DURACION_SEGUNDOS,
        httponly=True,
        samesite="lax",
        secure=COOKIE_SECURE,  # True en producción detrás de HTTPS (variable de entorno COOKIE_SECURE)
    )
    return respuesta


def _destino_post_login(usuario: dict) -> str:
    """Si el admin le restableció la contraseña, primero a cambiarla; si no, a la primera
    sección que su rol puede ver (no todos los roles ven el Inicio)."""
    if usuario.get("debe_cambiar_password"):
        return RUTA_CAMBIAR_PASSWORD
    permisos = usuario.get("permisos") or permisos_de_rol(usuario.get("rol"))
    return pagina_inicial(permisos)


@route.get("/login", response_class=HTMLResponse, name="login")
async def login_form(request: Request):
    usuario = obtener_usuario_actual(request)
    if usuario:
        return RedirectResponse(url=_destino_post_login(usuario), status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None}
    )


@route.post("/login", name="login_submit")
async def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    usuario = autenticar_usuario(username.strip(), password)

    if not usuario:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Usuario o contraseña incorrectos.", "username": username},
            status_code=401
        )

    respuesta = RedirectResponse(url=_destino_post_login(usuario), status_code=303)
    return _set_cookie_sesion(respuesta, usuario)


# El registro público se cerró: las cuentas las crea un administrador en /admin/usuarios.


@route.post("/logout", name="logout")
async def logout(request: Request):
    respuesta = RedirectResponse(url=request.url_for("login"), status_code=303)
    respuesta.delete_cookie(SESION_COOKIE)
    return respuesta


@route.get("/cuenta", response_class=HTMLResponse, name="cuenta")
async def cuenta(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    if usuario.get("debe_cambiar_password"):
        return RedirectResponse(url=RUTA_CAMBIAR_PASSWORD, status_code=303)

    try:
        resumen = obtener_resumen_cuenta(usuario["_id"])
    except Exception as e:
        logger.error(f"Error al armar el resumen de cuenta de {usuario['_id']}: {str(e)}")
        resumen = None

    return templates.TemplateResponse(
        request=request,
        name="cuenta.html",
        context={"resumen": resumen}
    )



@route.get(RUTA_CAMBIAR_PASSWORD, response_class=HTMLResponse, name="cambiar_password")
async def cambiar_password_form(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    return templates.TemplateResponse(
        request=request, name="cambiar_password.html",
        context={"error": None, "exito": False, "obligatorio": bool(usuario.get("debe_cambiar_password"))}
    )


@route.post(RUTA_CAMBIAR_PASSWORD, name="cambiar_password_submit")
async def cambiar_password_submit(
    request: Request,
    password_actual: str = Form(...),
    password_nueva: str = Form(...),
    password_confirmacion: str = Form(...)
):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)
    obligatorio = bool(usuario.get("debe_cambiar_password"))
    try:
        cambiar_password_propia(usuario["_id"], password_actual, password_nueva, password_confirmacion)
    except GestionUsuariosError as e:
        return templates.TemplateResponse(
            request=request, name="cambiar_password.html",
            context={"error": str(e), "exito": False, "obligatorio": obligatorio}, status_code=400
        )
    if obligatorio:
        # Ya puede entrar al sistema: a su primera sección permitida
        return RedirectResponse(url=pagina_inicial(usuario.get("permisos") or set()), status_code=303)
    return templates.TemplateResponse(
        request=request, name="cambiar_password.html", context={"error": None, "exito": True, "obligatorio": False}
    )


@route.get("/cuenta/saldo", name="cuenta_saldo")
async def cuenta_saldo(request: Request):
    """Saldo actual del usuario (lo usa static/js/ui.js para refrescar la pill del navbar
    después de comprar/vender/cobrar sin recargar la página)."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return JSONResponse({"detail": "Inicia sesión."}, status_code=401)
    return {"monto": usuario.get("monto", 0)}
