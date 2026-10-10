"""
Gestión de usuarios y roles (routes/admin_route.py, /admin/*; permiso 'gestion_usuarios') y
cambio de contraseña propio (/cuenta/password).

Salvaguardas: siempre queda al menos un administrador activo; un admin no puede desactivarse
ni quitarse el rol admin a sí mismo; el rol 'admin' (de sistema) no se borra ni se recorta; un
rol con usuarios asignados no se borra. Cada restablecimiento de contraseña hecho por el admin
deja 'debe_cambiar_password' = True, así el usuario la cambia en su próximo ingreso.
"""
import certifi
import secrets
import string
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.mongo_client import MongoClient

from config.secciones import CODIGOS_SECCIONES, PERMISO_TODO, ROL_ADMIN, secciones_por_grupo
from config.settings import MONGODB_URI
from services.auth_service import MONTO_INICIAL_USUARIO, hashear_password, verificar_password

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

LONGITUD_MINIMA_PASSWORD = 6
LONGITUD_MINIMA_USERNAME = 3


class GestionUsuariosError(Exception):
    """Error de validación; la ruta lo muestra como alerta en la página."""


def _oid(valor: Any) -> ObjectId:
    try:
        return ObjectId(str(valor))
    except (InvalidId, TypeError):
        raise GestionUsuariosError("Usuario inválido.")


def _validar_password(password: str) -> None:
    if len(password or "") < LONGITUD_MINIMA_PASSWORD:
        raise GestionUsuariosError(f"La contraseña debe tener al menos {LONGITUD_MINIMA_PASSWORD} caracteres.")


def generar_password_temporal(longitud: int = 10) -> str:
    """Contraseña aleatoria legible (sin caracteres ambiguos como 0/O, 1/l)."""
    alfabeto = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")
    return "".join(secrets.choice(alfabeto) for _ in range(longitud))


# ==========================================
# Roles
# ==========================================
def listar_roles() -> List[dict]:
    roles = list(db["roles"].find({}).sort([("es_sistema", -1), ("nombre", 1)]))
    conteo = {d["_id"]: d["n"] for d in db["usuarios"].aggregate([{"$group": {"_id": "$rol", "n": {"$sum": 1}}}])}
    for r in roles:
        r["_id"] = str(r["_id"])
        r["usuarios"] = conteo.get(r["codigo"], 0)
        r["todos"] = PERMISO_TODO in (r.get("permisos") or [])
    return roles


def _rol_existe(codigo: str) -> bool:
    return db["roles"].count_documents({"codigo": codigo}, limit=1) > 0


def guardar_rol(codigo: Optional[str], nombre: str, descripcion: str, permisos: List[str], codigo_original: Optional[str] = None) -> None:
    """Crea (codigo_original=None) o edita un rol. Los permisos se filtran contra el catálogo."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise GestionUsuariosError("El rol necesita un nombre.")
    permisos_validos = [p for p in permisos if p in CODIGOS_SECCIONES]
    ahora = datetime.now()

    if codigo_original:
        rol = db["roles"].find_one({"codigo": codigo_original})
        if not rol:
            raise GestionUsuariosError("El rol no existe.")
        cambios = {"nombre": nombre, "descripcion": (descripcion or "").strip(), "actualizado_en": ahora}
        if not rol.get("es_sistema"):  # el admin conserva siempre "*"
            cambios["permisos"] = permisos_validos
        db["roles"].update_one({"_id": rol["_id"]}, {"$set": cambios})
        return

    codigo = "".join(c for c in (codigo or nombre).lower().strip().replace(" ", "_") if c.isalnum() or c == "_")
    if not codigo:
        raise GestionUsuariosError("Código de rol inválido.")
    if _rol_existe(codigo):
        raise GestionUsuariosError(f"Ya existe un rol con el código '{codigo}'.")
    db["roles"].insert_one({
        "codigo": codigo, "nombre": nombre, "descripcion": (descripcion or "").strip(),
        "permisos": permisos_validos, "es_sistema": False, "creado_en": ahora, "actualizado_en": ahora,
    })


def borrar_rol(codigo: str) -> None:
    rol = db["roles"].find_one({"codigo": codigo})
    if not rol:
        raise GestionUsuariosError("El rol no existe.")
    if rol.get("es_sistema"):
        raise GestionUsuariosError("El rol de sistema no se puede borrar.")
    usuarios = db["usuarios"].count_documents({"rol": codigo})
    if usuarios:
        raise GestionUsuariosError(f"El rol tiene {usuarios} usuario(s) asignado(s): cámbiales el rol antes de borrarlo.")
    db["roles"].delete_one({"_id": rol["_id"]})


def matriz_secciones():
    return secciones_por_grupo()


# ==========================================
# Usuarios
# ==========================================
def listar_usuarios() -> List[dict]:
    nombres_rol = {r["codigo"]: r["nombre"] for r in db["roles"].find({}, {"codigo": 1, "nombre": 1})}
    usuarios = list(db["usuarios"].find({}, {"password_hash": 0}).sort("username", 1))
    for u in usuarios:
        u["_id"] = str(u["_id"])
        u["rol_nombre"] = nombres_rol.get(u.get("rol"), "Sin rol")
    return usuarios


def _admins_activos(excluir_id: Optional[ObjectId] = None) -> int:
    filtro = {"rol": ROL_ADMIN, "activo": {"$ne": False}}
    if excluir_id:
        filtro["_id"] = {"$ne": excluir_id}
    return db["usuarios"].count_documents(filtro)


def crear_usuario(username: str, nombre: str, rol: str, password: str) -> dict:
    """Alta hecha por el admin: queda activa y con 'debe_cambiar_password' (la inicial la eligió el admin)."""
    username = (username or "").strip()
    nombre = (nombre or "").strip() or username
    if len(username) < LONGITUD_MINIMA_USERNAME:
        raise GestionUsuariosError(f"El usuario debe tener al menos {LONGITUD_MINIMA_USERNAME} caracteres.")
    if db["usuarios"].count_documents({"username": username}, limit=1):
        raise GestionUsuariosError("Ese nombre de usuario ya está en uso.")
    if not _rol_existe(rol):
        raise GestionUsuariosError("Rol inválido.")
    _validar_password(password)
    usuario = {
        "username": username, "nombre": nombre, "password_hash": hashear_password(password),
        "monto": MONTO_INICIAL_USUARIO, "activo": True, "rol": rol, "debe_cambiar_password": True,
        "fecha_registro": datetime.now(),
    }
    usuario["_id"] = db["usuarios"].insert_one(usuario).inserted_id
    return usuario


def actualizar_usuario(admin_actual: dict, usuario_id: str, nombre: str, rol: str, activo: bool) -> None:
    oid = _oid(usuario_id)
    usuario = db["usuarios"].find_one({"_id": oid})
    if not usuario:
        raise GestionUsuariosError("El usuario no existe.")
    if not _rol_existe(rol):
        raise GestionUsuariosError("Rol inválido.")
    es_uno_mismo = str(oid) == str(admin_actual["_id"])
    if es_uno_mismo and not activo:
        raise GestionUsuariosError("No puedes desactivar tu propia cuenta.")
    if es_uno_mismo and rol != ROL_ADMIN and usuario.get("rol") == ROL_ADMIN:
        raise GestionUsuariosError("No puedes quitarte el rol de administrador a ti mismo.")
    deja_de_ser_admin_activo = usuario.get("rol") == ROL_ADMIN and (rol != ROL_ADMIN or not activo)
    if deja_de_ser_admin_activo and _admins_activos(excluir_id=oid) == 0:
        raise GestionUsuariosError("Debe quedar al menos un administrador activo.")
    db["usuarios"].update_one({"_id": oid}, {"$set": {
        "nombre": (nombre or "").strip() or usuario.get("nombre"), "rol": rol, "activo": bool(activo),
    }})


def restablecer_password(usuario_id: str, password: Optional[str] = None) -> str:
    """El admin fija una contraseña nueva (o se genera una aleatoria). Devuelve la contraseña
    en claro para mostrarla UNA vez; el usuario tendrá que cambiarla al entrar."""
    oid = _oid(usuario_id)
    if not db["usuarios"].count_documents({"_id": oid}, limit=1):
        raise GestionUsuariosError("El usuario no existe.")
    password = (password or "").strip() or generar_password_temporal()
    _validar_password(password)
    db["usuarios"].update_one({"_id": oid}, {"$set": {"password_hash": hashear_password(password), "debe_cambiar_password": True}})
    return password


def cambiar_password_propia(usuario_id: str, actual: str, nueva: str, confirmacion: str) -> None:
    usuario = db["usuarios"].find_one({"_id": _oid(usuario_id)})
    if not usuario or not verificar_password(actual or "", usuario.get("password_hash")):
        raise GestionUsuariosError("La contraseña actual no es correcta.")
    if nueva != confirmacion:
        raise GestionUsuariosError("Las contraseñas nuevas no coinciden.")
    _validar_password(nueva)
    if verificar_password(nueva, usuario.get("password_hash")):
        raise GestionUsuariosError("La contraseña nueva debe ser distinta de la actual.")
    db["usuarios"].update_one({"_id": usuario["_id"]}, {"$set": {"password_hash": hashear_password(nueva), "debe_cambiar_password": False}})
