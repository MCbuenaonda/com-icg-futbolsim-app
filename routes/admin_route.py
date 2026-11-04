"""
Administración: gestión de usuarios y roles (services/usuarios_service.py). Todo el router exige
el permiso 'gestion_usuarios' (ver main.py). Formularios clásicos (POST + render), sin API JSON:
una contraseña generada se muestra UNA sola vez en la respuesta y no se guarda en claro.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services.auth_service import context_usuario_actual, obtener_usuario_actual
from services import estadios_admin_service as estadios_srv
from services.imagenes_pais_service import GLOBALES_JINJA
from services.usuarios_service import (
    GestionUsuariosError, abonar_puntos, actualizar_usuario, borrar_rol, crear_usuario, generar_password_temporal, guardar_rol,
    listar_ajustes_recientes, listar_roles, listar_usuarios, matriz_secciones, restablecer_password,
)

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.globals.update(GLOBALES_JINJA)
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
            "usuarios": listar_usuarios(), "roles": listar_roles(), "ajustes": listar_ajustes_recientes(),
            "error": error, "exito": exito, "password_mostrada": password_mostrada,
        }
    )


@route.get("/usuarios", response_class=HTMLResponse, name="admin_usuarios")
def usuarios(request: Request, exito: Optional[str] = None):
    return _pagina_usuarios(request, exito=exito)


@route.post("/usuarios", response_class=HTMLResponse, name="admin_crear_usuario")
def crear(request: Request, username: str = Form(...), nombre: str = Form(""), rol: str = Form(...),
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
def editar(request: Request, usuario_id: str, nombre: str = Form(""), rol: str = Form(...), activo: Optional[str] = Form(None)):
    try:
        actualizar_usuario(obtener_usuario_actual(request), usuario_id, nombre, rol, activo is not None)
    except GestionUsuariosError as e:
        return _pagina_usuarios(request, error=str(e), status_code=400)
    return RedirectResponse(url=request.url_for("admin_usuarios").include_query_params(exito="Usuario actualizado."), status_code=303)


@route.post("/usuarios/{usuario_id}/password", response_class=HTMLResponse, name="admin_reset_password")
def reset_password(request: Request, usuario_id: str, username: str = Form(""), password: str = Form("")):
    try:
        nueva = restablecer_password(usuario_id, password)
    except GestionUsuariosError as e:
        return _pagina_usuarios(request, error=str(e), status_code=400)
    return _pagina_usuarios(
        request, exito=f"Contraseña de '{username}' restablecida. Deberá cambiarla al ingresar.",
        password_mostrada={"username": username, "password": nueva},
    )


@route.post("/usuarios/{usuario_id}/abonar", response_class=HTMLResponse, name="admin_abonar_puntos")
def abonar(request: Request, usuario_id: str, monto: str = Form(...), motivo: str = Form("")):
    """Suma puntos al saldo del usuario (queda auditado en 'ajustes_saldo')."""
    try:
        r = abonar_puntos(obtener_usuario_actual(request), usuario_id, monto, motivo)
    except GestionUsuariosError as e:
        return _pagina_usuarios(request, error=str(e), status_code=400)
    return RedirectResponse(url=request.url_for("admin_usuarios").include_query_params(
        exito=f"Se abonaron {r['monto']:,} pts a '{r['username']}'. Saldo actual: {r['saldo']:,} pts."), status_code=303)


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
def roles(request: Request, editar: Optional[str] = None, exito: Optional[str] = None):
    return _pagina_roles(request, editar=editar, exito=exito)


@route.post("/roles", response_class=HTMLResponse, name="admin_guardar_rol")
def guardar(request: Request, nombre: str = Form(...), descripcion: str = Form(""), codigo: str = Form(""),
                  codigo_original: str = Form(""), permisos: List[str] = Form([])):
    try:
        guardar_rol(codigo, nombre, descripcion, permisos, codigo_original or None)
    except GestionUsuariosError as e:
        return _pagina_roles(request, error=str(e), editar=codigo_original or None, status_code=400)
    return RedirectResponse(url=request.url_for("admin_roles").include_query_params(exito=f"Rol '{nombre}' guardado."), status_code=303)


@route.post("/roles/{codigo}/borrar", response_class=HTMLResponse, name="admin_borrar_rol")
def borrar(request: Request, codigo: str):
    try:
        borrar_rol(codigo)
    except GestionUsuariosError as e:
        return _pagina_roles(request, error=str(e), status_code=400)
    return RedirectResponse(url=request.url_for("admin_roles").include_query_params(exito="Rol borrado."), status_code=303)


# ==========================================
# Ciudades y estadios
# ==========================================
def _entero(valor) -> Optional[int]:
    try:
        return int(valor) if valor not in (None, "") else None
    except (TypeError, ValueError):
        return None


@route.get("/estadios", response_class=HTMLResponse, name="admin_estadios")
def estadios(request: Request, q: str = "", pais: str = "", confederacion: str = "", tipo: str = "", dueno: str = "",
                   pagina: int = 1):
    datos = estadios_srv.listar(q, _entero(pais), _entero(confederacion), tipo, dueno, pagina)
    return templates.TemplateResponse(request=request, name="admin_estadios.html", context={
        **datos, **estadios_srv.opciones_filtros(),
        "filtros": {"q": q, "pais": _entero(pais), "confederacion": _entero(confederacion), "tipo": tipo, "dueno": dueno},
    })


@route.post("/estadios/{ciudad_id}", name="admin_renombrar_estadio")
def renombrar_estadio(request: Request, ciudad_id: int, nombre: str = Form(...)):
    usuario = obtener_usuario_actual(request) or {}
    try:
        res = estadios_srv.renombrar_estadio(ciudad_id, nombre, usuario.get("username", ""))
    except estadios_srv.EstadioError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    return {"ok": True, **res}
