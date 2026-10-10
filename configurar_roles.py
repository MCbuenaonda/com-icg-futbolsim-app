"""
Script de configuración de roles (una corrida, idempotente). Ejecutar contra la base real:

    python configurar_roles.py                          # siembra roles y asigna roles faltantes
    python configurar_roles.py --password-admin         # además pide (oculta) una contraseña para 'dummy'

Qué hace:
  1. Índices: 'roles.codigo' único.
  2. Siembra los roles de config/secciones.py::ROLES_INICIALES (Administrador, Jugador,
     Espectador) con upsert por 'codigo'. A los roles ya existentes NO les pisa los permisos (se
     pudieron editar en /admin/roles); solo el rol de sistema 'admin' se fuerza a "*".
  3. 'dummy' -> rol admin. El resto de los usuarios SIN rol -> ROL_POR_DEFECTO (jugador).
  4. Avisa qué usuarios no tienen contraseña (password_hash): desde este cambio el login VALIDA la
     contraseña (antes estaba desactivado), así que esos usuarios no podrán entrar hasta que un
     admin se la restablezca en /admin/usuarios.

Mientras la colección 'roles' esté vacía la app mantiene el comportamiento anterior (todos ven
todo, ver auth_service.permisos_de_rol): correr este script es lo que activa los roles.
"""
import argparse
import certifi
import getpass
from datetime import datetime
from pymongo import ASCENDING
from pymongo.mongo_client import MongoClient

from config.secciones import PERMISO_TODO, ROL_ADMIN, ROL_POR_DEFECTO, ROLES_INICIALES
from config.settings import MONGODB_URI
from services.auth_service import hashear_password

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

USUARIO_ADMIN_INICIAL = "dummy"


def sembrar_roles():
    db["roles"].create_index([("codigo", ASCENDING)], unique=True, name="codigo_unico")
    ahora = datetime.now()
    for rol in ROLES_INICIALES:
        existente = db["roles"].find_one({"codigo": rol["codigo"]})
        if existente:
            if rol["codigo"] == ROL_ADMIN:
                db["roles"].update_one({"_id": existente["_id"]}, {"$set": {"permisos": [PERMISO_TODO], "es_sistema": True, "actualizado_en": ahora}})
            print(f"  rol '{rol['codigo']}': ya existía (permisos sin cambios)")
        else:
            db["roles"].insert_one({**rol, "creado_en": ahora, "actualizado_en": ahora})
            print(f"  rol '{rol['codigo']}': creado")


def asignar_roles(password_admin=None):
    admin = db["usuarios"].find_one({"username": USUARIO_ADMIN_INICIAL})
    if admin:
        cambios = {"rol": ROL_ADMIN, "activo": True}
        if password_admin:
            cambios.update({"password_hash": hashear_password(password_admin), "debe_cambiar_password": False})
        db["usuarios"].update_one({"_id": admin["_id"]}, {"$set": cambios})
        print(f"  '{USUARIO_ADMIN_INICIAL}' -> admin" + (" (contraseña actualizada)" if password_admin else ""))
    else:
        print(f"  ⚠️  No existe el usuario '{USUARIO_ADMIN_INICIAL}': asigná el rol admin a otro usuario a mano.")
    sin_rol = db["usuarios"].update_many({"rol": {"$exists": False}}, {"$set": {"rol": ROL_POR_DEFECTO}})
    print(f"  {sin_rol.modified_count} usuario(s) sin rol -> '{ROL_POR_DEFECTO}'")


def avisar_sin_password():
    sin_hash = [u["username"] for u in db["usuarios"].find({"$or": [{"password_hash": {"$exists": False}}, {"password_hash": None}, {"password_hash": ""}]}, {"username": 1})]
    if sin_hash:
        print(f"  ⚠️  Sin contraseña (no podrán ingresar hasta que un admin se la restablezca): {', '.join(sin_hash)}")
    else:
        print("  Todos los usuarios tienen contraseña.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configura roles y el administrador inicial.")
    parser.add_argument("--password-admin", action="store_true", help=f"Pide una contraseña nueva para '{USUARIO_ADMIN_INICIAL}'")
    args = parser.parse_args()
    password = None
    if args.password_admin:
        password = getpass.getpass(f"Contraseña nueva para '{USUARIO_ADMIN_INICIAL}' (mín. 6): ")
        if len(password) < 6 or password != getpass.getpass("Repetir: "):
            raise SystemExit("Contraseña inválida o no coincide.")
    print("Roles:"); sembrar_roles()
    print("Usuarios:"); asignar_roles(password)
    avisar_sin_password()
