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
MONGODB_URI = 'mongodb+srv://ingcarloscerati_db_user:C4rl056C@cluster0.yleznra.mongodb.net/'

# Clave usada para firmar la cookie de sesión de usuarios (services/auth_service.py).
# En producción definir SECRET_KEY en el .env con un valor propio y secreto.
SECRET_KEY = config_env.get("SECRET_KEY", "dev-secret-key-cambiar-en-produccion")