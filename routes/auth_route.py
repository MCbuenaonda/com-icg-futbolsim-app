from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from services.auth_service import (
    autenticar_usuario,
    crear_usuario,
    crear_token_sesion,
    obtener_usuario_actual,
    context_usuario_actual,
    SESION_COOKIE,
    SESION_DURACION_SEGUNDOS
)
from services.account_service import obtener_resumen_cuenta
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
        samesite="lax"
    )
    return respuesta


@route.get("/login", response_class=HTMLResponse, name="login")
async def login_form(request: Request):
    if obtener_usuario_actual(request):
        return RedirectResponse(url=request.url_for("home"), status_code=303)

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

    respuesta = RedirectResponse(url=request.url_for("home"), status_code=303)
    return _set_cookie_sesion(respuesta, usuario)


@route.get("/registro", response_class=HTMLResponse, name="registro")
async def registro_form(request: Request):
    if obtener_usuario_actual(request):
        return RedirectResponse(url=request.url_for("home"), status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="registro.html",
        context={"error": None}
    )


@route.post("/registro", name="registro_submit")
async def registro_submit(
    request: Request,
    username: str = Form(...),
    nombre: str = Form(...),
    password: str = Form(...),
    password_confirmacion: str = Form(...)
):
    username = username.strip()
    nombre = nombre.strip()

    if len(username) < 3:
        error = "El nombre de usuario debe tener al menos 3 caracteres."
    elif len(password) < 6:
        error = "La contraseña debe tener al menos 6 caracteres."
    elif password != password_confirmacion:
        error = "Las contraseñas no coinciden."
    else:
        error = None

    if error:
        return templates.TemplateResponse(
            request=request,
            name="registro.html",
            context={"error": error, "username": username, "nombre": nombre},
            status_code=400
        )

    try:
        usuario = crear_usuario(username, nombre, password)
    except ValueError as e:
        return templates.TemplateResponse(
            request=request,
            name="registro.html",
            context={"error": str(e), "username": username, "nombre": nombre},
            status_code=409
        )

    respuesta = RedirectResponse(url=request.url_for("home"), status_code=303)
    return _set_cookie_sesion(respuesta, usuario)


@route.post("/logout", name="logout")
async def logout(request: Request):
    respuesta = RedirectResponse(url=request.url_for("home"), status_code=303)
    respuesta.delete_cookie(SESION_COOKIE)
    return respuesta


@route.get("/cuenta", response_class=HTMLResponse, name="cuenta")
async def cuenta(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

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
