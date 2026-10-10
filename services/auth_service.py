import certifi
import bcrypt
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, Request
from pymongo.mongo_client import MongoClient
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from bson import ObjectId
from config.settings import MONGODB_URI, SECRET_KEY
from config.secciones import CODIGOS_SECCIONES, PERMISO_TODO

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

serializer = URLSafeTimedSerializer(SECRET_KEY, salt="sesion-usuario")

SESION_COOKIE = "sesion_futbolsim"
SESION_DURACION_SEGUNDOS = 60 * 60 * 24 * 7  # 7 días

# Saldo inicial de un usuario recién registrado (mismo campo 'monto' que ya
# se usaba en 'usuarios' para el modo manager)
MONTO_INICIAL_USUARIO = 1000


# ==========================================
# Contraseñas
# (bcrypt directo, no passlib: la última versión de passlib -1.7.4- quedó sin
# mantenimiento desde 2020 y es incompatible con las versiones actuales de bcrypt)
# ==========================================
def hashear_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_password(password: str, password_hash: Optional[str]) -> bool:
    if not password_hash:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ==========================================
# Usuarios
# ==========================================
def obtener_usuario_por_username(username: str) -> Optional[dict]:
    return db['usuarios'].find_one({"username": username})


# Alta de usuarios: services/usuarios_service.py::crear_usuario (solo desde /admin/usuarios;
# el registro público se cerró).


def autenticar_usuario(username: str, password: str) -> Optional[dict]:
    """Verifica username/password. Devuelve el documento del usuario o None."""
    usuario = obtener_usuario_por_username(username)
    if not usuario or not usuario.get("activo", True):
        return None
    if not verificar_password(password, usuario.get("password_hash")):
        return None
    return usuario


# ==========================================
# Sesión (cookie firmada, sin estado en el servidor)
# ==========================================
def crear_token_sesion(usuario: dict) -> str:
    return serializer.dumps({"user_id": str(usuario["_id"])})


# ==========================================
# Roles y permisos (catálogo en config/secciones.py, roles en la colección 'roles')
# ==========================================
def permisos_de_rol(codigo_rol: Optional[str]) -> set:
    """
    Códigos de sección que habilita un rol ("*" se expande a todo el catálogo). Un rol
    inexistente no habilita nada. Mientras la colección 'roles' esté vacía (todavía no se corrió
    configurar_roles.py) se mantiene el comportamiento previo: todos ven todo.
    """
    if db['roles'].estimated_document_count() == 0:
        return set(CODIGOS_SECCIONES)
    rol = db['roles'].find_one({"codigo": codigo_rol}) if codigo_rol else None
    if not rol:
        return set()
    permisos = set(rol.get("permisos") or [])
    if PERMISO_TODO in permisos:
        return set(CODIGOS_SECCIONES)
    return permisos & set(CODIGOS_SECCIONES)


def tiene_permiso(usuario: Optional[dict], *codigos: str) -> bool:
    """True si el usuario tiene AL MENOS uno de los permisos indicados."""
    if not usuario:
        return False
    permisos = usuario.get("permisos") or set()
    return any(c in permisos for c in codigos)


def obtener_usuario_actual(request: Request) -> Optional[dict]:
    """
    Lee la cookie de sesión, valida la firma/expiración y devuelve el usuario
    logueado (sin password_hash, con 'permisos' resueltos de su rol) o None si no hay sesión
    válida. Se cachea en request.state: en una misma request la llaman la dependencia del
    router, el context processor de Jinja y la vista.
    """
    if hasattr(request.state, "usuario_actual"):
        return request.state.usuario_actual
    usuario = _leer_usuario_de_cookie(request)
    request.state.usuario_actual = usuario
    return usuario


def _leer_usuario_de_cookie(request: Request) -> Optional[dict]:
    token = request.cookies.get(SESION_COOKIE)
    if not token:
        return None

    try:
        datos = serializer.loads(token, max_age=SESION_DURACION_SEGUNDOS)
    except (BadSignature, SignatureExpired):
        return None

    usuario = db['usuarios'].find_one({"_id": ObjectId(datos["user_id"])})
    if not usuario or not usuario.get("activo", True):
        return None

    usuario.pop("password_hash", None)
    usuario["_id"] = str(usuario["_id"])
    usuario["permisos"] = permisos_de_rol(usuario.get("rol"))
    return usuario


def context_usuario_actual(request: Request) -> dict:
    """
    Context processor de Jinja2Templates (lo registran todas las rutas): agrega a todas las
    vistas 'usuario_actual', 'puede("codigo", ...)' para mostrar/ocultar por permiso (navbar,
    botones de simular, etc.) y 'nav_activo("/prefijo", ...)' para resaltar el ítem del menú de
    la página actual.
    """
    usuario = obtener_usuario_actual(request)
    ruta = request.url.path

    def nav_activo(*prefijos: str) -> bool:
        return any(ruta == p or (p != "/" and ruta.startswith(p)) for p in prefijos)

    return {
        "usuario_actual": usuario,
        "puede": lambda *codigos: tiene_permiso(usuario, *codigos),
        "nav_activo": nav_activo,
    }


def exigir_sesion_activa(request: Request) -> dict:
    """
    Dependencia de FastAPI para 'app.include_router(..., dependencies=[Depends(...)])' en
    main.py: si no hay sesión activa, corta la request ANTES de que la vista se renderice y
    redirige a /login (en vez de mostrar el dashboard/vistas del sistema sin loguearse). Se
    aplica a los routers de PÁGINA (núcleo del torneo + cada 'route_vistas' de meta-juego), no a
    los de API JSON -- varios de esos GETs están documentados como públicos a propósito (ej.
    /matches/live, que ya consume el badge flotante de esta misma base.html) y varias rutas de
    meta-juego ya hacen su propio chequeo de sesión en escritura.

    El truco de 'HTTPException' con status 303 + header 'Location' es el mecanismo estándar de
    FastAPI para que una DEPENDENCIA (no la vista en sí) fuerce una redirección: el manejador de
    excepciones default de Starlette preserva los headers de la excepción, así que el navegador
    sigue la redirección igual que con un RedirectResponse común.
    """
    return _usuario_validado(request)


# Rutas a las que puede entrar un usuario con 'debe_cambiar_password' (si no, queda encerrado)
RUTA_CAMBIAR_PASSWORD = "/cuenta/password"


def es_request_html(request: Request) -> bool:
    """Navegación de página (HTML) vs llamada fetch/API (JSON): decide redirección o 401/403."""
    return "text/html" in request.headers.get("accept", "")


def _usuario_validado(request: Request) -> dict:
    """Sesión obligatoria + cambio de contraseña obligatorio (si el admin la restableció)."""
    usuario = obtener_usuario_actual(request)
    if not usuario:
        if es_request_html(request):
            raise HTTPException(status_code=303, headers={"Location": "/login"})
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    if usuario.get("debe_cambiar_password") and request.url.path != RUTA_CAMBIAR_PASSWORD:
        if es_request_html(request):
            raise HTTPException(status_code=303, headers={"Location": RUTA_CAMBIAR_PASSWORD})
        raise HTTPException(status_code=403, detail="Debes cambiar tu contraseña antes de continuar.")
    return usuario


def requiere_permiso(*codigos: str):
    """
    Dependencia de FastAPI: sesión activa + al menos uno de los permisos 'codigos' (ver
    config/secciones.py). Uso: app.include_router(router, dependencies=[Depends(requiere_permiso("quinielas"))])
    o como parámetro de una ruta. Sin permiso: 403 (main.py lo muestra como página
    'sin_permiso.html' si es navegación HTML).
    """
    def _dependencia(request: Request) -> dict:
        usuario = _usuario_validado(request)
        if not tiene_permiso(usuario, *codigos):
            raise HTTPException(status_code=403, detail="No tienes permiso para acceder a esta sección.")
        return usuario
    return _dependencia


def exigir_mismo_usuario_o_admin(request: Request, user_id: str) -> dict:
    """
    Para los endpoints de lectura con '{user_id}' en la URL (portafolios, colección, boletos,
    alineación fantasy): solo el propio usuario -- o quien tenga 'gestion_usuarios' -- puede ver
    los datos de esa cuenta. Antes cualquiera podía consultar los de otro cambiando el id (IDOR).
    """
    usuario = _usuario_validado(request)
    if str(usuario["_id"]) != str(user_id) and not tiene_permiso(usuario, "gestion_usuarios"):
        raise HTTPException(status_code=403, detail="No puedes consultar los datos de otro usuario.")
    return usuario
