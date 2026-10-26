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

# Base pública de las imágenes de cada selección (bucket de Cloud Storage). Dentro hay una carpeta
# por tipo (bandera/, escudo/, icono/, jersey/) con un archivo por país nombrado EXACTAMENTE como
# 'paises.nombre' en Mongo (ej. bandera/Países Bajos.png). Ver services/imagenes_pais_service.py.
IMAGENES_PAISES_URL = (config_env.get("IMAGENES_PAISES_URL") or "https://storage.googleapis.com/com-icg-mundial").rstrip("/")

# La foto del partido (services/foto_partido_service.py): Vertex AI (Imagen) + bucket. Las credenciales NO van aquí:
# en local, `gcloud auth application-default login`; en Cloud Run, la cuenta de servicio del servicio (roles
# "Vertex AI User" y "Storage Object User" sobre el bucket).
GCP_PROJECT = config_env.get("GCP_PROJECT") or config_env.get("GOOGLE_CLOUD_PROJECT") or "soy-radius-332400"
# Los modelos Gemini 3 de imagen solo se sirven desde "global" (en us-central1 dan 404; probado con count_tokens)
VERTEX_LOCATION = config_env.get("VERTEX_LOCATION") or "global"
# Los modelos 'imagen-*' ya no están disponibles en el proyecto (404): se usan los Gemini de imagen.
# Precios en Vertex (oct-2026): gemini-3.1-flash-image ~0,067 USD por foto de 1K (512: 0,045; 2K: 0,101);
# gemini-3-pro-image ~0,134 USD (mejor calidad). Verificar en https://cloud.google.com/vertex-ai/generative-ai/pricing
VERTEX_MODELO_IMAGEN = config_env.get("VERTEX_MODELO_IMAGEN") or "gemini-3.1-flash-image"
FOTOS_TAMANO = config_env.get("FOTOS_TAMANO") or "1K"   # 512 / 1K / 2K / 4K (más grande = más caro)
FOTOS_BUCKET = config_env.get("FOTOS_BUCKET") or "com-icg-mundial"
FOTOS_POR_DIA = int(config_env.get("FOTOS_POR_DIA") or 3)
FOTOS_ZONA_HORARIA = config_env.get("FOTOS_ZONA_HORARIA") or "America/Mexico_City"

# El pulso (services/pulso_service.py): el torneo avanza solo en el servidor. Cloud Scheduler llama cada minuto a
# POST /tareas/pulso con la cabecera X-Pulso-Clave = PULSO_CLAVE (si no está definida, esa ruta queda deshabilitada).
# PULSO_LOCAL=1: la app da el pulso por su cuenta (hilo cada 30 s), para desarrollo en la Mac.
PULSO_CLAVE = config_env.get("PULSO_CLAVE") or ""
PULSO_LOCAL = str(config_env.get("PULSO_LOCAL", "0")).lower() in ("1", "true", "si", "yes")
PULSO_INTERVALO_MIN = int(config_env.get("PULSO_INTERVALO_MIN") or 30)   # ritmo por defecto (se cambia desde /en-vivo)
# Cloud Run define K_SERVICE: ahí la CPU solo corre mientras se atiende un pedido, así que los procesos en segundo plano
# (recálculo de probabilidades) se hacen dentro del pulso en vez de en un proceso aparte.
EN_CLOUD_RUN = bool(os.environ.get("K_SERVICE"))
