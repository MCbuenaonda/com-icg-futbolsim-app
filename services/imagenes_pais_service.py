"""
Imágenes de cada selección (bandera, jersey, ícono y escudo), servidas desde el bucket público de
Cloud Storage configurado en IMAGENES_PAISES_URL (config/settings.py):

    <IMAGENES_PAISES_URL>/<tipo>/<paises.nombre>.png      ej. .../bandera/Países Bajos.png

El archivo se llama EXACTAMENTE como 'paises.nombre' en Mongo: si se renombra un país en Mongo,
hay que renombrar sus 4 archivos en el bucket (gcloud storage mv).

Los documentos de partidos/países guardan la bandera como EMOJI (sin el id en muchos lugares), y
cada emoji es único por país, así que 'pais_id_por_bandera' resuelve el país a partir del emoji.
Con eso el macro 'bandera' de templates/partials/macros.html dibuja la imagen en cualquier vista
sin tocar los services. Se registra como globals de Jinja en cada router (GLOBALES_JINJA), y
base.html le pasa el mismo mapa al cliente (window.PAISES_IMG) para UI.bandera/UI.jersey.
"""
import json
import unicodedata
from typing import Optional
from urllib.parse import quote

import certifi
from pymongo.mongo_client import MongoClient

from config.settings import IMAGENES_PAISES_URL, MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

TIPOS_IMAGEN = ("bandera", "jersey", "icono", "escudo")

# {id: nombre} y {emoji: id} de 'paises' (se cargan una vez: nombres y banderas no cambian en runtime)
_nombre_por_id: Optional[dict] = None
_id_por_bandera: Optional[dict] = None


def _cargar_paises() -> None:
    global _nombre_por_id, _id_por_bandera
    if _nombre_por_id is None:
        paises = list(db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1}))
        _nombre_por_id = {p["id"]: unicodedata.normalize("NFC", p["nombre"]) for p in paises if p.get("nombre")}
        _id_por_bandera = {p["bandera"]: p["id"] for p in paises if p.get("bandera")}


def pais_id_por_bandera(bandera: Optional[str]) -> Optional[int]:
    """Id del país a partir de su emoji de bandera."""
    _cargar_paises()
    return _id_por_bandera.get(bandera) if bandera else None


def url_imagen_pais(pais_id, tipo: str = "bandera") -> Optional[str]:
    """URL de la imagen del país en el bucket, o None si el país/tipo no existe (el que llama cae al emoji)."""
    if tipo not in TIPOS_IMAGEN:
        return None
    try:
        pais_id = int(pais_id)
    except (TypeError, ValueError):
        return None
    _cargar_paises()
    nombre = _nombre_por_id.get(pais_id)
    return f"{IMAGENES_PAISES_URL}/{tipo}/{quote(nombre)}.png" if nombre else None


def mapa_banderas_json() -> str:
    """Datos para UI.bandera()/UI.jersey() en el cliente (base.html lo deja en window.PAISES_IMG)."""
    _cargar_paises()
    return json.dumps({
        "base": IMAGENES_PAISES_URL,
        "porBandera": _id_por_bandera,
        "porId": {str(i): n for i, n in _nombre_por_id.items()},
    }, ensure_ascii=False)


# Logos de confederación: <IMAGENES_PAISES_URL>/confederaciones/<sigla en minúsculas>.png.
# 'color' tiñe el fondo de su card en el inicio; 'claro' = el logo es oscuro (negro/azul marino) y se
# dibuja como silueta blanca para que no se pierda sobre el tema oscuro.
LOGOS_CONFEDERACION = {
    "CONMEBOL": {"color": "#1e88e5", "claro": False},
    "UEFA": {"color": "#3b5bdb", "claro": True},
    "CONCACAF": {"color": "#d4a72c", "claro": False},
    "CAF": {"color": "#2e9d4a", "claro": False},
    "AFC": {"color": "#c0392b", "claro": True},
    "OFC": {"color": "#7cb342", "claro": False},
}


def logo_confederacion(sigla: Optional[str]) -> Optional[dict]:
    """{'url', 'color', 'claro'} del logo de la confederación, o None si no hay logo para esa sigla."""
    datos = LOGOS_CONFEDERACION.get((sigla or "").upper())
    if not datos:
        return None
    return {**datos, "url": f"{IMAGENES_PAISES_URL}/confederaciones/{quote((sigla or '').lower())}.png"}


# {ciudad_id: "estadios/dNN-cMM.svg"} (ciudades.estadio_imagen, asignado una vez por generar_estadios.py)
_estadio_por_ciudad: Optional[dict] = None


def url_estadio(ciudad_id) -> Optional[str]:
    """Ilustración del estadio de una ciudad sede (bucket estadios/), o None si no tiene."""
    global _estadio_por_ciudad
    try:
        ciudad_id = int(ciudad_id)
    except (TypeError, ValueError):
        return None
    if _estadio_por_ciudad is None:
        _estadio_por_ciudad = {c["id"]: c["estadio_imagen"] for c in db["ciudades"].find(
            {"estadio_imagen": {"$exists": True}}, {"id": 1, "estadio_imagen": 1})}
    imagen = _estadio_por_ciudad.get(ciudad_id)
    return f"{IMAGENES_PAISES_URL}/{imagen}" if imagen else None


# ids de jugadores con avatar (jugadores.avatar_imagen, asignado una vez por generar_avatares.py)
_jugadores_con_avatar: Optional[set] = None


def url_avatar(jugador_id) -> Optional[str]:
    """Avatar ilustrado del jugador (bucket jugadores/<id>.svg, fondo transparente), o None si no tiene."""
    global _jugadores_con_avatar
    try:
        jugador_id = int(jugador_id)
    except (TypeError, ValueError):
        return None
    if _jugadores_con_avatar is None:
        _jugadores_con_avatar = {j["id"] for j in db["jugadores"].find({"avatar_imagen": {"$exists": True}}, {"id": 1})}
    return f"{IMAGENES_PAISES_URL}/jugadores/{jugador_id}.svg" if jugador_id in _jugadores_con_avatar else None


# nombre -> {"url", "pais_id"} de los árbitros (arbitros.avatar_imagen, asignado una vez por generar_avatares_arbitros.py).
# Los partidos guardan solo el NOMBRE del árbitro; con nombres repetidos gana el primero.
_arbitros_por_nombre: Optional[dict] = None


def datos_arbitro(nombre) -> dict:
    """{'url': avatar del árbitro (bucket arbitros/<_id>.svg) o None, 'pais_id': id del país o None}."""
    global _arbitros_por_nombre
    if _arbitros_por_nombre is None:
        _arbitros_por_nombre = {}
        for a in db["arbitros"].find({}, {"nombre": 1, "pais_id": 1, "avatar_imagen": 1}).sort("_id", 1):
            imagen = a.get("avatar_imagen")
            _arbitros_por_nombre.setdefault(a["nombre"], {"url": f"{IMAGENES_PAISES_URL}/{imagen}" if imagen else None,
                                                          "pais_id": a.get("pais_id")})
    return _arbitros_por_nombre.get(nombre) or {"url": None, "pais_id": None}


def imagen_inicio(nombre: str) -> str:
    """Imágenes de las tarjetas de resumen del inicio (partidos, goles, confederaciones): <bucket>/inicio/<nombre>.png."""
    return f"{IMAGENES_PAISES_URL}/inicio/{quote(nombre)}.png"


def imagen_perfil(nombre: str) -> str:
    """Imágenes de las tarjetas del perfil del jugador (bucket perfil/<nombre>.png): forma, moral,
    pie_derecho/izquierdo/ambidiestro, especialidad y animo_<estado>. Acepta tildes y mayúsculas
    ("animo_Eufórico" -> perfil/animo_euforico.png)."""
    import unicodedata
    limpio = unicodedata.normalize("NFKD", str(nombre or "")).encode("ascii", "ignore").decode().lower().replace(" ", "_")
    return f"{IMAGENES_PAISES_URL}/perfil/{quote(limpio)}.png"


GLOBALES_JINJA = {
    "img_pais": url_imagen_pais, "pais_id_por_bandera": pais_id_por_bandera,
    "mapa_banderas_json": mapa_banderas_json, "logo_confederacion": logo_confederacion,
    "imagen_inicio": imagen_inicio, "img_estadio": url_estadio, "img_avatar": url_avatar,
    "datos_arbitro": datos_arbitro, "imagen_perfil": imagen_perfil,
}
