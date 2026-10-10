"""
Catálogo de secciones/permisos del sistema: la fuente única de qué puede ver o hacer cada rol.

Los roles (colección 'roles', ver configurar_roles.py y /admin/roles) guardan una lista de
códigos de este catálogo en 'permisos' ("*" = todos). services/auth_service.py resuelve los
permisos del usuario en cada request y main.py protege cada router con
requiere_permiso("<codigo>"); base.html oculta del navbar lo que el rol no puede ver.

Si agregás una vista nueva: sumá su código acá, protegé su router en main.py y su link en
base.html con tiene_permiso(...). "Mi cuenta" y "Cambiar contraseña" no son secciones: cualquier
usuario con sesión puede verlas.
"""

PERMISO_TODO = "*"

# (codigo, nombre, grupo, descripcion) -- el orden es el de la matriz en /admin/roles
SECCIONES = [
    # --- Torneo (consulta) ---
    ("inicio", "Inicio", "Torneo", "Dashboard del torneo"),
    ("partidos", "Partidos", "Torneo", "Partidos pendientes, calendario, detalle y resumen de partidos"),
    ("cuadro", "Cuadro de eliminación", "Torneo", "Llaves de eliminación directa del Mundial"),
    ("en_vivo", "Simulación en Vivo", "Torneo", "Transmisión en vivo de los partidos"),
    ("paises", "Países y Jugadores", "Torneo", "Selecciones, planteles, perfiles y confederaciones"),
    ("estadisticas", "Estadísticas", "Torneo", "Líderes, récords y tendencias del torneo"),
    ("cara_a_cara", "Cara a Cara", "Torneo", "Historial de enfrentamientos entre dos países"),
    ("palmares", "Palmarés", "Torneo", "Archivo histórico de Mundiales y campeones"),
    ("scouter", "Scouter Pre-partido", "Torneo", "Análisis y probabilidades antes de cada partido"),
    ("aficionados", "Popularidad", "Torneo", "Ranking de aficionados por selección"),
    ("arbitros", "Árbitros", "Torneo", "Directorio y perfil de árbitros con sus estadísticas"),
    # --- Mi Juego (meta-juego con saldo) ---
    ("juego_en_vivo", "Juego en Vivo", "Mi Juego", "Elegir país y jugar puntos durante la transmisión"),
    ("quinielas", "Quinielas", "Mi Juego", "Comprar y ver boletos de quiniela"),
    ("selecciones", "Mercado de Selecciones", "Mi Juego", "Comprar y vender selecciones"),
    ("sedes", "Sedes", "Mi Juego", "Patrocinar ciudades sede"),
    ("once_ideal", "Once Ideal (Fantasy)", "Mi Juego", "Armar el equipo fantasy por fase"),
    ("album", "Álbum de Estampas", "Mi Juego", "Comprar sobres y ver la colección"),
    ("misiones", "Misiones y Trivia", "Mi Juego", "Check-in diario, beca y trivia"),
    ("ranking_usuarios", "Ranking de usuarios", "Mi Juego", "Comparación de patrimonio y logros entre usuarios"),
    # --- Administración (acciones sensibles) ---
    ("simular_partidos", "Simular partidos", "Administración", "Simular partidos y avanzar el torneo (incluye la reproducción automática)"),
    ("reiniciar_torneo", "Reiniciar torneo", "Administración", "Borrar el torneo actual y empezar de cero"),
    ("gestion_usuarios", "Gestión de usuarios y roles", "Administración", "Crear usuarios, restablecer contraseñas y definir roles"),
]

CODIGOS_SECCIONES = [s[0] for s in SECCIONES]
NOMBRE_SECCION = {s[0]: s[1] for s in SECCIONES}


def secciones_por_grupo():
    """[(grupo, [ {codigo, nombre, descripcion}, ... ]), ...] en el orden del catálogo."""
    grupos = {}
    for codigo, nombre, grupo, descripcion in SECCIONES:
        grupos.setdefault(grupo, []).append({"codigo": codigo, "nombre": nombre, "descripcion": descripcion})
    return list(grupos.items())


# Roles que siembra configurar_roles.py ('admin' es de sistema: no se borra ni se recorta)
ROL_ADMIN = "admin"
_CONSULTA = ["inicio", "partidos", "cuadro", "en_vivo", "paises", "estadisticas", "cara_a_cara", "palmares", "scouter", "aficionados", "arbitros"]
_META_JUEGO = ["juego_en_vivo", "quinielas", "selecciones", "sedes", "once_ideal", "album", "misiones", "ranking_usuarios"]
ROLES_INICIALES = [
    {"codigo": ROL_ADMIN, "nombre": "Administrador", "descripcion": "Acceso total, incluida la gestión de usuarios", "permisos": [PERMISO_TODO], "es_sistema": True},
    {"codigo": "jugador", "nombre": "Jugador", "descripcion": "Consulta del torneo y todo el meta-juego, sin acciones de administración", "permisos": _CONSULTA + _META_JUEGO, "es_sistema": False},
    {"codigo": "espectador", "nombre": "Espectador", "descripcion": "Solo consulta del torneo, sin meta-juego", "permisos": list(_CONSULTA), "es_sistema": False},
]
ROL_POR_DEFECTO = "jugador"

# Página de cada sección de vista (para el redirect post-login a la primera sección permitida
# y el botón de 'sin_permiso.html'). Las de acción (simular, reiniciar...) no tienen página.
URL_SECCION = {
    "inicio": "/", "partidos": "/juegos/", "cuadro": "/cuadro/", "en_vivo": "/en-vivo/",
    "paises": "/paises/", "estadisticas": "/estadisticas/", "cara_a_cara": "/cara-a-cara/",
    "palmares": "/palmares/", "aficionados": "/aficionados/", "arbitros": "/arbitros/", "juego_en_vivo": "/en-vivo/",
    "ranking_usuarios": "/ranking/",
    "quinielas": "/quinielas/", "selecciones": "/selecciones/mercado", "sedes": "/sedes/directorio",
    "once_ideal": "/once-ideal/", "album": "/album-estampas/sobres", "misiones": "/misiones/",
    "gestion_usuarios": "/admin/usuarios",
}


def pagina_inicial(permisos) -> str:
    """Primera página del catálogo que el rol puede ver; si no puede ver ninguna, 'Mi cuenta'."""
    for codigo in CODIGOS_SECCIONES:
        if codigo in permisos and codigo in URL_SECCION:
            return URL_SECCION[codigo]
    return "/cuenta"
