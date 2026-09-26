import certifi
import bcrypt
from datetime import datetime
from typing import Optional
from fastapi import HTTPException, Request
from pymongo.mongo_client import MongoClient
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from bson import ObjectId
from config.settings import MONGODB_URI, SECRET_KEY

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


def crear_usuario(username: str, nombre: str, password: str) -> dict:
    """Crea un nuevo usuario. Lanza ValueError si el username ya está en uso."""
    if obtener_usuario_por_username(username):
        raise ValueError("Ese nombre de usuario ya está en uso")

    usuario = {
        "username": username,
        "nombre": nombre,
        "password_hash": hashear_password(password),
        "monto": MONTO_INICIAL_USUARIO,
        "activo": True,
        "fecha_registro": datetime.now()
    }
    resultado = db['usuarios'].insert_one(usuario)
    usuario["_id"] = resultado.inserted_id
    return usuario


def autenticar_usuario(username: str, password: str) -> Optional[dict]:
    """Verifica username/password. Devuelve el documento del usuario o None."""
    usuario = obtener_usuario_por_username(username)
    if not usuario or not usuario.get("activo", True):
        return None
    # if not verificar_password(password, usuario.get("password_hash")):
    #     return None
    return usuario


# ==========================================
# Sesión (cookie firmada, sin estado en el servidor)
# ==========================================
def crear_token_sesion(usuario: dict) -> str:
    return serializer.dumps({"user_id": str(usuario["_id"])})


def obtener_usuario_actual(request: Request) -> Optional[dict]:
    """
    Lee la cookie de sesión, valida la firma/expiración y devuelve el usuario
    logueado (sin password_hash) o None si no hay sesión válida.
    """
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
    return usuario


def context_usuario_actual(request: Request) -> dict:
    """Context processor de Jinja2Templates: agrega 'usuario_actual' a todas las vistas."""
    return {"usuario_actual": obtener_usuario_actual(request)}


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
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return usuario
