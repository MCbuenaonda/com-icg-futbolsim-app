import os
from dotenv import dotenv_values

config_env = {
    **dotenv_values(".env"),  
    **os.environ, 

}

PREFIX_SIMULADOR_PATH = '/simulador'
PREFIX_HOME_PATH = '/home'
PREFIX_PAISES_PATH = '/paises'
PREFIX_JUGADORES_PATH = '/jugadores'
PREFIX_CONFEDERACIONES_PATH = '/confederacion'
PREFIX_JUEGOS_PATH = '/juegos'
PREFIX_LIVE_GAME_PATH = '/live-game'  # API del Juego en Vivo (routes/juego_en_vivo_route.py)
# Credenciales: SIEMPRE desde el entorno o el .env (nunca en el código; ver .env.example).
# En Cloud Run se pasan con --set-env-vars / --set-secrets al desplegar.
MONGODB_URI = config_env.get("MONGODB_URI")
if not MONGODB_URI:
    raise RuntimeError(
        "Falta la variable MONGODB_URI. Definila en el archivo .env (ver .env.example) o en el "
        "entorno del servicio (Cloud Run: gcloud run deploy ... --set-env-vars MONGODB_URI=...)."
    )

# Clave usada para firmar la cookie de sesión de usuarios (services/auth_service.py).
# En producción definir SECRET_KEY en el .env con un valor propio y secreto.
SECRET_KEY = config_env.get("SECRET_KEY") or "dev-secret-key-cambiar-en-produccion"
if SECRET_KEY == "dev-secret-key-cambiar-en-produccion":
    import warnings
    warnings.warn("SECRET_KEY no está definida: se usa una clave de desarrollo. Definila en el .env / entorno en producción.")

# Cookie de sesión solo por HTTPS: activar en producción (ej. GCP detrás de HTTPS) con
# COOKIE_SECURE=1 en el entorno o el .env. En local (http://) debe quedar desactivada.
COOKIE_SECURE = str(config_env.get("COOKIE_SECURE", "0")).lower() in ("1", "true", "si", "yes")
