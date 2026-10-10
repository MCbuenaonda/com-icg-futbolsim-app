"""
Administración: gestión de usuarios y roles (services/usuarios_service.py). Todo el router exige
el permiso 'gestion_usuarios' (ver main.py). Formularios clásicos (POST + render), sin API JSON:
una contraseña generada se muestra UNA sola vez en la respuesta y no se guarda en claro.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services.auth_service import context_usuario_actual, obtener_usuario_actual
from services.usuarios_service import (
    GestionUsuariosError, actualizar_usuario, borrar_rol, crear_usuario, generar_password_temporal, guardar_rol,
    listar_roles, listar_usuarios, matriz_secciones, restablecer_password,
)

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
route = APIRouter(prefix="/admin", tags=["Administración"])
tag = 'Administración'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==========================================
# Usuarios
# ==========================================
def _pagina_usuarios(request: Request, error: Optional[str] = None, exito: Optional[str] = None,
                     password_mostrada: Optional[dict] = None, status_code: int = 200):
    return templates.TemplateResponse(
        request=request, name="admin_usuarios.html", status_code=status_code,
        context={
            "usuarios": listar_usuarios(), "roles": listar_roles(),
            "error": error, "exito": exito, "password_mostrada": password_mostrada,
        }
    )


@route.get("/usuarios", response_class=HTMLResponse, name="admin_usuarios")
async def usuarios(request: Request, exito: Optional[str] = None):
    return _pagina_usuarios(request, exito=exito)


@route.post("/usuarios", response_class=HTMLResponse, name="admin_crear_usuario")
async def crear(request: Request, username: str = Form(...), nombre: str = Form(""), rol: str = Form(...),
                password: str = Form(""), generar: Optional[str] = Form(None)):
    password = generar_password_temporal() if (generar or not password.strip()) else password
    try:
        usuario = crear_usuario(username, nombre, rol, password)
    except GestionUsuariosError as e:
        return _pagina_usuarios(request, error=str(e), status_code=400)
    return _pagina_usuarios(
        request, exito=f"Usuario '{usuario['username']}' creado. Deberá cambiar la contraseña en su primer ingreso.",
        password_mostrada={"username": usuario["username"], "password": password},
    )


@route.post("/usuarios/{usuario_id}", response_class=HTMLResponse, name="admin_editar_usuario")
async def editar(request: Request, usuario_id: str, nombre: str = Form(""), rol: str = Form(...), activo: Optional[str] = Form(None)):
    try:
        actualizar_usuario(obtener_usuario_actual(request), usuario_id, nombre, rol, activo is not None)
    except GestionUsuariosError as e:
        return _pagina_usuarios(request, error=str(e), status_code=400)
    return RedirectResponse(url=request.url_for("admin_usuarios").include_query_params(exito="Usuario actualizado."), status_code=303)


@route.post("/usuarios/{usuario_id}/password", response_class=HTMLResponse, name="admin_reset_password")
async def reset_password(request: Request, usuario_id: str, username: str = Form(""), password: str = Form("")):
    try:
        nueva = restablecer_password(usuario_id, password)
    except GestionUsuariosError as e:
        return _pagina_usuarios(request, error=str(e), status_code=400)
    return _pagina_usuarios(
        request, exito=f"Contraseña de '{username}' restablecida. Deberá cambiarla al ingresar.",
        password_mostrada={"username": username, "password": nueva},
    )


# ==========================================
# Roles
# ==========================================
def _pagina_roles(request: Request, error: Optional[str] = None, exito: Optional[str] = None,
                  editar: Optional[str] = None, status_code: int = 200):
    roles = listar_roles()
    rol_editado = next((r for r in roles if r["codigo"] == editar), None)
    return templates.TemplateResponse(
        request=request, name="admin_roles.html", status_code=status_code,
        context={"roles": roles, "grupos": matriz_secciones(), "rol_editado": rol_editado, "error": error, "exito": exito}
    )


@route.get("/roles", response_class=HTMLResponse, name="admin_roles")
async def roles(request: Request, editar: Optional[str] = None, exito: Optional[str] = None):
    return _pagina_roles(request, editar=editar, exito=exito)


@route.post("/roles", response_class=HTMLResponse, name="admin_guardar_rol")
async def guardar(request: Request, nombre: str = Form(...), descripcion: str = Form(""), codigo: str = Form(""),
                  codigo_original: str = Form(""), permisos: List[str] = Form([])):
    try:
        guardar_rol(codigo, nombre, descripcion, permisos, codigo_original or None)
    except GestionUsuariosError as e:
        return _pagina_roles(request, error=str(e), editar=codigo_original or None, status_code=400)
    return RedirectResponse(url=request.url_for("admin_roles").include_query_params(exito=f"Rol '{nombre}' guardado."), status_code=303)


@route.post("/roles/{codigo}/borrar", response_class=HTMLResponse, name="admin_borrar_rol")
async def borrar(request: Request, codigo: str):
    try:
        borrar_rol(codigo)
    except GestionUsuariosError as e:
        return _pagina_roles(request, error=str(e), status_code=400)
    return RedirectResponse(url=request.url_for("admin_roles").include_query_params(exito="Rol borrado."), status_code=303)
