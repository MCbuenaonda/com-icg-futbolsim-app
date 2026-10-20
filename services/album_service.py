"""
Lógica de negocio del Álbum de Estampas: compra/apertura de sobres
(pack_purchases) y colección del usuario (user_albums).

Las estampas se muestrean con $sample de Mongo (aleatoriedad real en el
servidor, sin traer toda la colección a Python). Dentro de un mismo sobre, si
sale dos veces la misma estampa nueva, la segunda se detecta como duplicada
contra la primera (se refleja el album localmente a medida que se procesa
cada estampa del sobre, no solo contra el estado que había antes de abrirlo).
"""
import certifi
import random
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import IMAGENES_PAISES_URL, MONGODB_URI
from services.imagenes_pais_service import url_estadio

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

COSTO_SOBRE = 100
CANTIDAD_ESTAMPAS_POR_SOBRE = 5

TIPOS_ESTAMPA = ["JUGADOR", "CIUDAD", "PAIS", "ARBITRO"]

# Categorías de rareza (de la más común a la más rara): cada estampa del sobre sale de una categoría con
# esta probabilidad, y la repetida se "vende" sola por 'bonus_repetida'. Es la ÚNICA fuente de verdad: los
# pesos, los bonus, la XP por categoría (config/niveles.py) y los marcos del frontend salen de acá.
# Por sobre de 5: ~3,5 normales y 1 especial; una dorada cada ~3 sobres y una platino cada ~7.
CATEGORIAS_ESTAMPA = [
    {"codigo": "NORMAL",   "nombre": "Normal",   "tipo": "JUGADOR", "estampa": "Jugadores", "probabilidad": 0.70, "bonus_repetida": 10, "color": "#e2e8f0"},
    {"codigo": "ESPECIAL", "nombre": "Especial", "tipo": "CIUDAD",  "estampa": "Estadios",  "probabilidad": 0.20, "bonus_repetida": 15, "color": "#2dd4bf"},
    {"codigo": "DORADA",   "nombre": "Dorada",   "tipo": "ARBITRO", "estampa": "Árbitros",  "probabilidad": 0.07, "bonus_repetida": 30, "color": "#facc15"},
    {"codigo": "PLATINO",  "nombre": "Platino",  "tipo": "PAIS",    "estampa": "Escudos",   "probabilidad": 0.03, "bonus_repetida": 50, "color": "#cbd5e1"},
]
CATEGORIA_POR_TIPO = {c["tipo"]: c for c in CATEGORIAS_ESTAMPA}
PESOS_TIPO_ESTAMPA = {c["tipo"]: c["probabilidad"] for c in CATEGORIAS_ESTAMPA}
BONUS_DUPLICADA_POR_TIPO = {c["tipo"]: c["bonus_repetida"] for c in CATEGORIAS_ESTAMPA}
BONUS_ESTAMPA_DUPLICADA = BONUS_DUPLICADA_POR_TIPO["JUGADOR"]
# XP de niveles por estampa NUEVA según su categoría (reglas en config/niveles.py)
ACCION_XP_POR_TIPO = {"JUGADOR": "ESTAMPA_NUEVA", "CIUDAD": "ESTAMPA_ESPECIAL", "ARBITRO": "ESTAMPA_DORADA", "PAIS": "ESTAMPA_PLATINO"}
LOGRO_POR_TIPO = {"ARBITRO": "PRIMERA_DORADA", "PAIS": "PRIMERA_PLATINO"}

SIGLA_CONFEDERACION = {1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC", 7: "REPECHAJE", 8: "MUNDIAL"}

COLECCION_POR_TIPO = {"JUGADOR": "jugadores", "CIUDAD": "ciudades", "PAIS": "paises", "ARBITRO": "arbitros"}
CAMPO_ALBUM_POR_TIPO = {"JUGADOR": "owned_jugadores", "CIUDAD": "owned_ciudades", "PAIS": "owned_paises", "ARBITRO": "owned_arbitros"}

# Puestos de 'arbitros.puesto', en el orden de la página de árbitros, con su sigla para la estampa
PUESTOS_ARBITRO = [
    ("Arbitro central", "central", "Central", "C"),
    ("Arbitro de línea 1", "linea1", "Línea 1", "L1"),
    ("Arbitro de línea 2", "linea2", "Línea 2", "L2"),
    ("4to Arbitro", "cuarto", "4to árbitro", "4°"),
]
SIGLA_PUESTO_ARBITRO = {p[0]: p[3] for p in PUESTOS_ARBITRO}


def _elegir_tipo_estampa() -> str:
    tipos = list(PESOS_TIPO_ESTAMPA)
    return random.choices(tipos, weights=[PESOS_TIPO_ESTAMPA[t] for t in tipos])[0]


def _serializar_compra(compra: dict) -> dict:
    return {
        "id": str(compra["_id"]),
        "usuario_id": str(compra["user_id"]),
        "costo_pagado": compra["cost_paid"],
        "estampas_obtenidas": compra["stickers_obtained"],
        "fecha": compra["created_at"]
    }


# ==========================================
# Compra y apertura de sobre
# ==========================================
# Origen del sobre: comprado (100 pts) o regalado por las recompensas de nivel (services/niveles_service.py).
# El sobre PLATINO trae su primera estampa de árbitro garantizada.
ORIGENES_SOBRE = {"COMPRA": None, "GRATIS": "sobres_gratis", "PLATINO": "sobres_platino"}


def buy_and_open_pack(usuario_id: str, origen: str = "COMPRA") -> dict:
    """
    Cobra 100 pts (o descuenta un sobre gratis / Platino de las recompensas de nivel), genera 5
    estampas según las categorías de rareza (CATEGORIAS_ESTAMPA: Normal jugador 70%, Especial estadio 20%,
    Dorada árbitro 7%, Platino escudo 3%; el Sobre Platino trae un escudo garantizado) y actualiza el
    álbum del usuario. Las duplicadas no se agregan: se "venden" automáticamente por el bonus de su
    categoría (10/15/30/50 pts), que se acredita al saldo. Al final otorga la XP de niveles.
    """
    if origen not in ORIGENES_SOBRE:
        raise ValueError("Tipo de sobre inválido")
    usuario_oid = ObjectId(usuario_id)
    usuario = db['usuarios'].find_one({"_id": usuario_oid})
    if not usuario or not usuario.get("activo", True):
        raise ValueError("Usuario no encontrado o inactivo")

    campo_regalo = ORIGENES_SOBRE[origen]
    if campo_regalo:
        descuento = db['usuarios'].update_one({"_id": usuario_oid, campo_regalo: {"$gte": 1}}, {"$inc": {campo_regalo: -1}})
        if descuento.modified_count == 0:
            raise ValueError("No tenés sobres de regalo de ese tipo")
    else:
        if usuario.get("monto", 0) < COSTO_SOBRE:
            raise ValueError("Saldo insuficiente para comprar un sobre")
        descuento = db['usuarios'].update_one(
            {"_id": usuario_oid, "monto": {"$gte": COSTO_SOBRE}},
            {"$inc": {"monto": -COSTO_SOBRE}}
        )
        if descuento.modified_count == 0:
            raise ValueError("Saldo insuficiente para comprar un sobre")

    album = db['user_albums'].find_one({"user_id": usuario_oid})
    if not album:
        album = {"user_id": usuario_oid, "owned_jugadores": [], "owned_paises": [], "owned_ciudades": [], "owned_arbitros": []}
        db['user_albums'].insert_one(album)

    estampas_obtenidas = []
    bonus_total = 0

    for i in range(CANTIDAD_ESTAMPAS_POR_SOBRE):
        tipo = "PAIS" if (origen == "PLATINO" and i == 0) else _elegir_tipo_estampa()   # Sobre Platino: un escudo garantizado
        coleccion = COLECCION_POR_TIPO[tipo]
        campo_album = CAMPO_ALBUM_POR_TIPO[tipo]

        muestra = list(db[coleccion].aggregate([{"$match": {"id": {"$exists": True}}}, {"$sample": {"size": 1}}]))
        if not muestra:
            continue
        doc = muestra[0]
        estampa_id = doc["id"]

        ya_la_tiene = estampa_id in album.get(campo_album, [])

        if ya_la_tiene:
            bonus = BONUS_DUPLICADA_POR_TIPO.get(tipo, BONUS_ESTAMPA_DUPLICADA)
            bonus_total += bonus
            estampas_obtenidas.append({
                "tipo": tipo, "id": estampa_id, "nombre": doc.get("nombre"),
                "duplicado": True, "bonus_puntos": bonus
            })
        else:
            db['user_albums'].update_one(
                {"user_id": usuario_oid},
                {"$addToSet": {campo_album: estampa_id}}
            )
            album.setdefault(campo_album, []).append(estampa_id)  # refleja el cambio localmente (dupes dentro del mismo sobre)
            estampas_obtenidas.append({
                "tipo": tipo, "id": estampa_id, "nombre": doc.get("nombre"),
                "duplicado": False, "bonus_puntos": 0
            })

    if bonus_total > 0:
        db['usuarios'].update_one({"_id": usuario_oid}, {"$inc": {"monto": bonus_total}})

    compra = {
        "user_id": usuario_oid,
        "cost_paid": 0 if campo_regalo else COSTO_SOBRE,
        "origen": origen,
        "stickers_obtained": estampas_obtenidas,
        "created_at": datetime.now()
    }
    resultado = db['pack_purchases'].insert_one(compra)
    compra["_id"] = resultado.inserted_id

    _otorgar_xp_sobre(usuario_oid, compra, album)

    respuesta = _serializar_compra(compra)
    respuesta["estampas_obtenidas"] = _detallar_estampas(estampas_obtenidas)
    return respuesta


def _paginas_completas(album: dict, estampas_nuevas: List[dict]) -> List[str]:
    """Páginas del álbum (país, o 'arbitros') que la tanda de estampas nuevas dejó completas."""
    catalogo = _catalogo_album()
    owned = {tipo: set(album.get(campo, [])) for tipo, campo in CAMPO_ALBUM_POR_TIPO.items()}
    paises: set = set()
    revisar_arbitros = False
    for e in estampas_nuevas:
        if e["tipo"] == "ARBITRO":
            revisar_arbitros = True
        elif e["tipo"] == "PAIS":
            paises.add(e["id"])
        elif e["tipo"] == "JUGADOR":
            paises.add(catalogo["pais_de_jugador"].get(e["id"]))
        elif e["tipo"] == "CIUDAD":
            paises.add(catalogo["pais_de_ciudad"].get(e["id"]))
    completas = []
    for pais_id in paises - {None}:
        if (pais_id in owned["PAIS"]
                and all(j in owned["JUGADOR"] for j, p in catalogo["pais_de_jugador"].items() if p == pais_id)
                and all(c in owned["CIUDAD"] for c, p in catalogo["pais_de_ciudad"].items() if p == pais_id)):
            completas.append(str(pais_id))
    if revisar_arbitros and all(a["id"] in owned["ARBITRO"] for a in catalogo["arbitros"]):
        completas.append("arbitros")
    return completas


def _otorgar_xp_sobre(usuario_oid: ObjectId, compra: dict, album: dict) -> None:
    """XP de niveles por el sobre: abrirlo (solo si se compró), cada estampa nueva y cada página completada."""
    from services.niveles_service import otorgar_logro, otorgar_xp, ref_mundial
    try:
        if compra["origen"] == "COMPRA":
            otorgar_xp(usuario_oid, "SOBRE", compra["_id"])
        otorgar_logro(usuario_oid, "PRIMER_SOBRE")
        nuevas = [e for e in compra["stickers_obtained"] if not e["duplicado"]]
        mundial = ref_mundial()   # una sola consulta por sobre: las estampas y páginas se ganan una vez por Mundial
        for e in nuevas:
            otorgar_xp(usuario_oid, ACCION_XP_POR_TIPO[e["tipo"]], f"{mundial}:{e['tipo']}:{e['id']}")
            if e["tipo"] in LOGRO_POR_TIPO:
                otorgar_logro(usuario_oid, LOGRO_POR_TIPO[e["tipo"]])
        for pagina in _paginas_completas(album, nuevas):
            otorgar_xp(usuario_oid, "PAGINA_COMPLETA", f"{mundial}:{pagina}")
    except Exception as e:
        print(f"No se pudo otorgar la XP del sobre: {e}")


def _detallar_estampas(estampas: List[dict]) -> List[dict]:
    """
    Datos para dibujar cada estampa en la animación del sobre (templates/album_sobres.html): país,
    dorsal y posición del jugador, confederación del escudo, estadio de la ciudad. Solo viajan en
    la respuesta: lo que se guarda en 'pack_purchases' no cambia.
    """
    ids = {tipo: [e["id"] for e in estampas if e["tipo"] == tipo] for tipo in TIPOS_ESTAMPA}
    siglas_pos = {p["id"]: p.get("siglas", "") for p in db['posiciones'].find({}, {"id": 1, "siglas": 1})}
    jugadores = {j["id"]: j for j in db['jugadores'].find({"id": {"$in": ids["JUGADOR"]}}, {"id": 1, "pais_id": 1, "numero": 1, "posicion_id": 1, "overall": 1})}
    ciudades = {c["id"]: c for c in db['ciudades'].find({"id": {"$in": ids["CIUDAD"]}}, {"id": 1, "pais_id": 1, "pais": 1, "estadio": 1})}
    arbitros = {a["id"]: a for a in db['arbitros'].find({"id": {"$in": ids["ARBITRO"]}}, {"id": 1, "pais_id": 1, "puesto": 1, "genero": 1, "avatar_imagen": 1})}
    ids_paises = (set(ids["PAIS"]) | {j.get("pais_id") for j in jugadores.values()} | {c.get("pais_id") for c in ciudades.values()}
                  | {a.get("pais_id") for a in arbitros.values()})
    paises = {p["id"]: p for p in db['paises'].find({"id": {"$in": list(ids_paises)}}, {"id": 1, "nombre": 1, "confederacion_id": 1})}

    detalladas = []
    for e in estampas:
        extra = {}
        if e["tipo"] == "JUGADOR":
            j = jugadores.get(e["id"], {})
            extra = {"pais_id": j.get("pais_id"), "numero": j.get("numero"), "posicion": siglas_pos.get(j.get("posicion_id"), ""),
                     "overall": round(j.get("overall") or 0, 1)}
        elif e["tipo"] == "PAIS":
            extra = {"pais_id": e["id"]}
        elif e["tipo"] == "CIUDAD":
            c = ciudades.get(e["id"], {})
            extra = {"pais_id": c.get("pais_id"), "estadio": c.get("estadio"), "estadio_img": url_estadio(e["id"])}
        elif e["tipo"] == "ARBITRO":
            a = arbitros.get(e["id"], {})
            extra = {"pais_id": a.get("pais_id"), "puesto": a.get("puesto"), "puesto_corto": SIGLA_PUESTO_ARBITRO.get(a.get("puesto"), ""),
                     "genero": a.get("genero"), "avatar_url": _url_avatar_arbitro(a)}
        pais = paises.get(extra.get("pais_id"), {})
        extra["pais_nombre"] = pais.get("nombre")
        extra["confederacion"] = SIGLA_CONFEDERACION.get(pais.get("confederacion_id"), "")
        categoria = CATEGORIA_POR_TIPO[e["tipo"]]
        extra["categoria"] = categoria["codigo"].lower()
        extra["categoria_nombre"] = categoria["nombre"]
        detalladas.append({**e, **extra})
    return detalladas


def _url_avatar_arbitro(arbitro: dict) -> Optional[str]:
    imagen = arbitro.get("avatar_imagen")
    return f"{IMAGENES_PAISES_URL}/{imagen}" if imagen else None


# ==========================================
# Colección del usuario
# ==========================================
def _paises_con_regalia(usuario_oid: ObjectId, owned_paises: List[int]) -> set:
    """
    IDs de 'owned_paises' que ya le generaron algún pago atribuible a la estampa (no a la
    mera inversión): el dividendo/bono del dueño con la sinergia x1.5 aplicada
    ('album_synergy_applied': True) o la recompensa pasiva de +20 pts para quien no es
    dueño ('type': 'SINERGIA_ALBUM' -- ver services/ownership_service.py::_abonar_puntos_dueno,
    que solo inserta ese tipo para usuarios que sí tienen la estampa).
    """
    if not owned_paises:
        return set()
    docs = db['ownership_transactions'].find(
        {
            "user_id": usuario_oid,
            "pais_id": {"$in": owned_paises},
            "$or": [{"album_synergy_applied": True}, {"type": "SINERGIA_ALBUM"}]
        },
        {"pais_id": 1}
    )
    return {d["pais_id"] for d in docs}


def _ciudades_con_regalia(usuario_oid: ObjectId, ciudades_docs: List[dict]) -> set:
    """
    IDs de ciudad que ya le generaron algún pago atribuible a la estampa: el cobro del
    dueño con la sinergia x1.5 aplicada ('album_synergy_applied': True), o -- al no
    existir un 'type' equivalente a SINERGIA_ALBUM en 'city_revenue_history' -- cualquier
    cobro registrado mientras el usuario NO era el dueño de la sede (ese cobro solo se
    genera para quien tiene la estampa, ver services/venue_service.py::process_match_city_revenue).
    """
    if not ciudades_docs:
        return set()
    ids_ciudades = [c["id"] for c in ciudades_docs]
    dueno_por_ciudad = {c["id"]: str(c.get("owner_user_id", 0)) for c in ciudades_docs}
    usuario_id_str = str(usuario_oid)

    docs = db['city_revenue_history'].find(
        {"user_id": usuario_oid, "ciudad_id": {"$in": ids_ciudades}},
        {"ciudad_id": 1, "album_synergy_applied": 1}
    )
    con_regalia = set()
    for d in docs:
        ciudad_id = d["ciudad_id"]
        if d.get("album_synergy_applied") or dueno_por_ciudad.get(ciudad_id) != usuario_id_str:
            con_regalia.add(ciudad_id)
    return con_regalia


def _jugadores_con_regalia(usuario_oid: ObjectId, owned_jugadores: List[int]) -> set:
    """
    IDs de 'owned_jugadores' que ya le generaron algún pago atribuible a la estampa: la
    sinergia x1.5 del Once Ideal ('fantasy_points_history.sinergia_album_aplicada': True)
    o la recompensa pasiva sin lineup ('album_passive_rewards', ver
    services/fantasy_service.py::procesar_eventos_jugadores_partido, caso b).
    """
    if not owned_jugadores:
        return set()
    con_sinergia = db['fantasy_points_history'].find(
        {"user_id": usuario_oid, "jugador_id": {"$in": owned_jugadores}, "sinergia_album_aplicada": True},
        {"jugador_id": 1}
    )
    con_pasiva = db['album_passive_rewards'].find(
        {"user_id": usuario_oid, "tipo_estampa": "JUGADOR", "item_id": {"$in": owned_jugadores}},
        {"item_id": 1}
    )
    return {d["jugador_id"] for d in con_sinergia} | {d["item_id"] for d in con_pasiva}


def obtener_coleccion_usuario(usuario_id: str) -> dict:
    """
    Estampas poseídas por el usuario y el % de llenado de jugadores por país (estilo
    álbum Panini). Además del resumen numérico, arma el DETALLE navegable de cada tipo
    de estampa (qué países/ciudades exactos tenés, y qué jugadores exactos por país),
    para la vista de "Mi Colección" (templates/album_coleccion.html) -- incluyendo, por
    estampa, si ya le dio alguna regalía/sinergia al usuario (ver funciones
    _paises_con_regalia / _ciudades_con_regalia / _jugadores_con_regalia).
    """
    usuario_oid = ObjectId(usuario_id)
    album = db['user_albums'].find_one({"user_id": usuario_oid})
    owned_jugadores = album.get("owned_jugadores", []) if album else []
    owned_paises = album.get("owned_paises", []) if album else []
    owned_ciudades = album.get("owned_ciudades", []) if album else []
    owned_arbitros = album.get("owned_arbitros", []) if album else []

    totales_por_pais = {
        doc["_id"]: doc["total"]
        for doc in db['jugadores'].aggregate([
            {"$group": {"_id": "$pais_id", "total": {"$sum": 1}}}
        ])
    }

    jugadores_con_regalia = _jugadores_con_regalia(usuario_oid, owned_jugadores)

    poseidos_por_pais: Dict[int, int] = {}
    jugadores_por_pais: Dict[int, List[dict]] = {}
    if owned_jugadores:
        jugadores_poseidos_docs = list(db['jugadores'].find(
            {"id": {"$in": owned_jugadores}}, {"id": 1, "nombre": 1, "pais_id": 1}
        ))
        for j in jugadores_poseidos_docs:
            poseidos_por_pais[j["pais_id"]] = poseidos_por_pais.get(j["pais_id"], 0) + 1
            jugadores_por_pais.setdefault(j["pais_id"], []).append({
                "id": j["id"], "nombre": j.get("nombre", "?"), "tiene_regalia": j["id"] in jugadores_con_regalia
            })
        for lista in jugadores_por_pais.values():
            lista.sort(key=lambda j: j["nombre"])

    nombres_paises = {p["id"]: p.get("nombre", "?") for p in db['paises'].find({}, {"id": 1, "nombre": 1})}

    llenado_por_pais = []
    for pais_id, total in totales_por_pais.items():
        poseidos = poseidos_por_pais.get(pais_id, 0)
        llenado_por_pais.append({
            "pais_id": pais_id,
            "pais_nombre": nombres_paises.get(pais_id, "?"),
            "total_jugadores": total,
            "jugadores_poseidos": poseidos,
            "porcentaje": round((poseidos / total) * 100, 1) if total else 0.0,
            "jugadores": jugadores_por_pais.get(pais_id, [])
        })
    llenado_por_pais.sort(key=lambda x: (-x["porcentaje"], x["pais_nombre"]))

    paises_detalle = []
    if owned_paises:
        paises_con_regalia = _paises_con_regalia(usuario_oid, owned_paises)
        paises_detalle = [
            {
                "id": p["id"], "nombre": p.get("nombre", "?"), "bandera": p.get("bandera"),
                "tiene_regalia": p["id"] in paises_con_regalia
            }
            for p in db['paises'].find({"id": {"$in": owned_paises}}, {"id": 1, "nombre": 1, "bandera": 1})
        ]
        paises_detalle.sort(key=lambda p: p["nombre"])

    ciudades_detalle = []
    if owned_ciudades:
        ciudades_docs = list(db['ciudades'].find(
            {"id": {"$in": owned_ciudades}},
            {"id": 1, "nombre": 1, "estadio": 1, "pais": 1, "owner_user_id": 1}
        ))
        ciudades_con_regalia = _ciudades_con_regalia(usuario_oid, ciudades_docs)
        ciudades_detalle = [
            {
                "id": c["id"], "nombre": c.get("nombre", "?"), "estadio": c.get("estadio"),
                "pais_nombre": c.get("pais", "?"), "tiene_regalia": c["id"] in ciudades_con_regalia
            }
            for c in ciudades_docs
        ]
        ciudades_detalle.sort(key=lambda c: c["nombre"])

    return {
        "usuario_id": usuario_id,
        "jugadores": owned_jugadores,
        "paises": owned_paises,
        "ciudades": owned_ciudades,
        "arbitros": owned_arbitros,
        "total_jugadores": len(owned_jugadores),
        "total_paises": len(owned_paises),
        "total_ciudades": len(owned_ciudades),
        "total_arbitros": len(owned_arbitros),
        "llenado_por_pais": llenado_por_pais,
        "paises_detalle": paises_detalle,
        "ciudades_detalle": ciudades_detalle
    }


# ==========================================
# Vista "Mi Álbum": 211 páginas, una por país, + la página Platino de árbitros
# ==========================================
# Orden de las páginas: por confederación (como las secciones de un álbum de papel) y por nombre.
ORDEN_CONFEDERACIONES = [1, 2, 3, 4, 6, 5]  # UEFA, CONMEBOL, CONCACAF, CAF, AFC, OFC

# Catálogo fijo del álbum (países, y a qué país pertenece cada jugador/ciudad): se carga una vez,
# igual que los mapas de services/imagenes_pais_service.py (no cambia en runtime).
_catalogo: Optional[dict] = None


def _catalogo_album() -> dict:
    global _catalogo
    if _catalogo is None:
        paises = list(db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1, "siglas": 1, "confederacion_id": 1}))
        orden_conf = {c: i for i, c in enumerate(ORDEN_CONFEDERACIONES)}
        paises.sort(key=lambda p: (orden_conf.get(p.get("confederacion_id"), 99), p.get("nombre", "")))
        pais_de_jugador = {j["id"]: j["pais_id"] for j in db["jugadores"].find({}, {"id": 1, "pais_id": 1})}
        pais_de_ciudad = {c["id"]: c["pais_id"] for c in db["ciudades"].find({}, {"id": 1, "pais_id": 1})}
        total_jugadores: Dict[int, int] = {}
        for pais_id in pais_de_jugador.values():
            total_jugadores[pais_id] = total_jugadores.get(pais_id, 0) + 1
        total_ciudades: Dict[int, int] = {}
        for pais_id in pais_de_ciudad.values():
            total_ciudades[pais_id] = total_ciudades.get(pais_id, 0) + 1
        orden_puesto = {p[0]: i for i, p in enumerate(PUESTOS_ARBITRO)}
        arbitros = list(db["arbitros"].find({"id": {"$exists": True}}, {"_id": 0, "id": 1, "nombre": 1, "pais_id": 1, "puesto": 1, "genero": 1, "avatar_imagen": 1}))
        arbitros.sort(key=lambda a: (orden_puesto.get(a.get("puesto"), 99), a.get("nombre", "")))
        _catalogo = {
            "arbitros": arbitros,
            "paises": [{"pais_id": p["id"], "nombre": p.get("nombre", "?"), "bandera": p.get("bandera"), "siglas": p.get("siglas"),
                        "confederacion": SIGLA_CONFEDERACION.get(p.get("confederacion_id"), ""),
                        "total_jugadores": total_jugadores.get(p["id"], 0), "total_ciudades": total_ciudades.get(p["id"], 0)}
                       for p in paises],
            "pais_de_jugador": pais_de_jugador,
            "pais_de_ciudad": pais_de_ciudad,
        }
    return _catalogo


def _indice_album(owned_jugadores: set, owned_ciudades: set, owned_paises: set, owned_arbitros: set) -> List[dict]:
    """Las 212 páginas (211 países + árbitros) con el avance del usuario en cada una (índice y navegación)."""
    catalogo = _catalogo_album()
    jugadores_por_pais: Dict[int, int] = {}
    for jugador_id in owned_jugadores:
        pais_id = catalogo["pais_de_jugador"].get(jugador_id)
        jugadores_por_pais[pais_id] = jugadores_por_pais.get(pais_id, 0) + 1
    ciudades_por_pais: Dict[int, int] = {}
    for ciudad_id in owned_ciudades:
        pais_id = catalogo["pais_de_ciudad"].get(ciudad_id)
        ciudades_por_pais[pais_id] = ciudades_por_pais.get(pais_id, 0) + 1

    indice = []
    for numero, p in enumerate(catalogo["paises"], start=1):
        tiene_escudo = p["pais_id"] in owned_paises
        obtenidas = int(tiene_escudo) + jugadores_por_pais.get(p["pais_id"], 0) + ciudades_por_pais.get(p["pais_id"], 0)
        total = 1 + p["total_jugadores"] + p["total_ciudades"]
        indice.append({**p, "tipo": "pais", "numero": numero, "escudo": tiene_escudo, "jugadores": jugadores_por_pais.get(p["pais_id"], 0),
                       "ciudades": ciudades_por_pais.get(p["pais_id"], 0), "obtenidas": obtenidas, "total": total,
                       "porcentaje": round(obtenidas / total * 100, 1) if total else 0.0})

    # Página especial al final: árbitros (estampas Platino)
    ids_arbitros = {a["id"] for a in catalogo["arbitros"]}
    obtenidas = len(owned_arbitros & ids_arbitros)
    total = len(ids_arbitros)
    indice.append({"tipo": "arbitros", "pais_id": None, "nombre": "Árbitros", "bandera": None, "siglas": None,
                   "confederacion": "ESPECIALES", "numero": len(indice) + 1, "escudo": False, "obtenidas": obtenidas, "total": total,
                   "porcentaje": round(obtenidas / total * 100, 1) if total else 0.0})
    return indice


def _pagina_arbitros(owned_arbitros: set) -> List[dict]:
    """
    Los 840 árbitros agrupados por puesto (las pestañas de la página Platino), con lo que dirigieron
    en el torneo: los partidos guardan solo el NOMBRE del árbitro, así que se cuenta por nombre.
    """
    partidos: Dict[str, int] = {}
    como_central: Dict[str, int] = {}
    for j in db["juegos"].find({"estado": "finalizado", "resultado.arbitros": {"$exists": True}}, {"resultado.arbitros": 1}):
        roles = (j.get("resultado") or {}).get("arbitros") or {}
        for rol, nombre in roles.items():
            if isinstance(nombre, str):
                partidos[nombre] = partidos.get(nombre, 0) + 1
                if rol == "central":
                    como_central[nombre] = como_central.get(nombre, 0) + 1

    nombres_paises = {p["pais_id"]: p for p in _catalogo_album()["paises"]}
    grupos = {p[0]: {"codigo": p[1], "nombre": p[2], "sigla": p[3], "arbitros": []} for p in PUESTOS_ARBITRO}
    for a in _catalogo_album()["arbitros"]:
        grupo = grupos.get(a.get("puesto"))
        if not grupo:
            continue
        pais = nombres_paises.get(a.get("pais_id"), {})
        grupo["arbitros"].append({
            "id": a["id"], "nombre": a.get("nombre", "?"), "puesto": a.get("puesto"), "puesto_corto": grupo["sigla"], "puesto_nombre": grupo["nombre"],
            "genero": a.get("genero"), "avatar_url": _url_avatar_arbitro(a),
            "pais_id": a.get("pais_id"), "pais_nombre": pais.get("nombre"), "bandera": pais.get("bandera"), "confederacion": pais.get("confederacion"),
            "partidos": partidos.get(a.get("nombre"), 0), "como_central": como_central.get(a.get("nombre"), 0),
            "obtenida": a["id"] in owned_arbitros,
        })
    resultado = []
    for g in grupos.values():
        g["total"] = len(g["arbitros"])
        g["obtenidas"] = sum(1 for a in g["arbitros"] if a["obtenida"])
        resultado.append(g)
    return resultado


def numero_pagina_de_pais(pais_id: int) -> Optional[int]:
    """Número de página (1-211) de un país, para entrar al álbum directo en su página (?pais=)."""
    for numero, p in enumerate(_catalogo_album()["paises"], start=1):
        if p["pais_id"] == pais_id:
            return numero
    return None


def obtener_album_pagina(usuario_id: str, numero: int) -> dict:
    """
    Datos de la vista HTML del álbum (templates/album_coleccion.html y la página suelta
    templates/partials/album_pagina.html): el álbum tiene una página por país (211), y cada página
    trae TODOS sus casilleros, se tengan o no: el escudo de la selección, sus ciudades sede (con el
    estadio) y su plantel ordenado por dorsal. Las estampas que faltan se dibujan como casillero
    vacío con el nombre impreso. Se arma una sola página por pedido (son ~43 casilleros cada una).
    La última página (212) es la especial de árbitros: 840 estampas Platino en 4 pestañas por puesto.
    La API JSON (/album/collection) no cambia: sigue usando obtener_coleccion_usuario.
    """
    usuario_oid = ObjectId(usuario_id)
    album = db["user_albums"].find_one({"user_id": usuario_oid}) or {}
    owned_jugadores = set(album.get("owned_jugadores", []))
    owned_ciudades = set(album.get("owned_ciudades", []))
    owned_paises = set(album.get("owned_paises", []))
    owned_arbitros = set(album.get("owned_arbitros", []))

    indice = _indice_album(owned_jugadores, owned_ciudades, owned_paises, owned_arbitros)
    numero = min(max(int(numero), 1), len(indice))
    hoja = indice[numero - 1]
    navegacion = {"anterior": numero - 1 if numero > 1 else None, "siguiente": numero + 1 if numero < len(indice) else None}
    resultado = {"indice": indice, "total_paginas": len(indice), "categorias": CATEGORIAS_ESTAMPA,
                 "totales": _totales_album(indice, owned_jugadores, owned_ciudades, owned_paises, owned_arbitros)}

    if hoja["tipo"] == "arbitros":
        return {**resultado, "pagina": {**hoja, **navegacion, "puestos": _pagina_arbitros(owned_arbitros)}}

    pais_id = hoja["pais_id"]

    # Escudo de la selección
    p = db["paises"].find_one({"id": pais_id}, {"id": 1, "nombre": 1, "bandera": 1, "federacion": 1, "aficionados": 1,
                                                 "valor": 1, "estado": 1, "estadisticas.rankin": 1, "estadisticas.poder": 1}) or {}
    est = p.get("estadisticas") or {}
    escudo = {
        "id": pais_id, "nombre": hoja["nombre"], "bandera": hoja["bandera"], "confederacion": hoja["confederacion"],
        "federacion": p.get("federacion"), "aficionados": p.get("aficionados"), "valor": p.get("valor"),
        "ranking": est.get("rankin"), "poder": est.get("poder"), "estado": p.get("estado"),
        "obtenida": hoja["escudo"], "tiene_regalia": bool(hoja["escudo"] and _paises_con_regalia(usuario_oid, [pais_id])),
    }

    # Ciudades sede del país (con el estadio)
    ciudades_docs = list(db["ciudades"].find({"pais_id": pais_id}, {"id": 1, "nombre": 1, "estadio": 1, "pais": 1, "pais_id": 1, "owner_user_id": 1}))
    regalia_ciudades = _ciudades_con_regalia(usuario_oid, [c for c in ciudades_docs if c["id"] in owned_ciudades])
    partidos_por_ciudad = {d["_id"]: d["n"] for d in db["juegos"].aggregate([
        {"$match": {"estado": "finalizado", "ubicacion.id": {"$in": [c["id"] for c in ciudades_docs]}}},
        {"$group": {"_id": "$ubicacion.id", "n": {"$sum": 1}}}])}
    ciudades = []
    for c in ciudades_docs:
        dueno = c.get("owner_user_id")
        ciudades.append({
            "id": c["id"], "nombre": c.get("nombre", "?"), "estadio": c.get("estadio"), "pais_nombre": c.get("pais", "?"),
            "pais_id": pais_id, "partidos": partidos_por_ciudad.get(c["id"], 0),
            "con_dueno": dueno not in (0, "0", None), "es_mia": str(dueno) == str(usuario_id),
            "obtenida": c["id"] in owned_ciudades, "tiene_regalia": c["id"] in regalia_ciudades,
        })
    ciudades.sort(key=lambda c: c["nombre"])

    # Plantel completo, por dorsal
    posiciones = {pos["id"]: pos for pos in db["posiciones"].find({}, {"id": 1, "siglas": 1, "nombre": 1})}
    jugadores_docs = list(db["jugadores"].find({"pais_id": pais_id}, {
        "id": 1, "nombre": 1, "numero": 1, "posicion_id": 1, "overall": 1, "edad": 1,
        "pie_habil": 1, "goles": 1, "asistencias": 1, "juegos_jugados": 1, "forma_actual": 1}))
    regalia_jugadores = _jugadores_con_regalia(usuario_oid, [j["id"] for j in jugadores_docs if j["id"] in owned_jugadores])
    plantel = []
    for j in jugadores_docs:
        pos = posiciones.get(j.get("posicion_id"), {})
        plantel.append({
            "id": j["id"], "nombre": j.get("nombre", "?"), "numero": j.get("numero"),
            "posicion": pos.get("siglas", ""), "posicion_nombre": pos.get("nombre", ""),
            "overall": round(j.get("overall") or 0, 1), "edad": j.get("edad"), "pie_habil": j.get("pie_habil"),
            "goles": j.get("goles", 0), "asistencias": j.get("asistencias", 0), "partidos": j.get("juegos_jugados", 0),
            "forma": j.get("forma_actual"), "obtenida": j["id"] in owned_jugadores, "tiene_regalia": j["id"] in regalia_jugadores,
        })
    plantel.sort(key=lambda j: (j["numero"] if j["numero"] is not None else 99, j["nombre"]))

    return {**resultado, "pagina": {**hoja, **navegacion, "escudo_estampa": escudo, "ciudades_estampa": ciudades, "plantel": plantel}}


def _totales_album(indice: List[dict], owned_jugadores: set, owned_ciudades: set, owned_paises: set, owned_arbitros: set) -> dict:
    catalogo = _catalogo_album()
    total_casilleros = sum(h["total"] for h in indice)
    total_obtenidas = sum(h["obtenidas"] for h in indice)
    return {
        "paises": len(owned_paises), "paises_total": len(catalogo["paises"]),
        "ciudades": len(owned_ciudades), "ciudades_total": len(catalogo["pais_de_ciudad"]),
        "jugadores": len(owned_jugadores), "jugadores_total": len(catalogo["pais_de_jugador"]),
        "arbitros": len(owned_arbitros), "arbitros_total": len(catalogo["arbitros"]),
        "paginas_completas": sum(1 for h in indice if h["obtenidas"] == h["total"]),
        "paginas_empezadas": sum(1 for h in indice if h["obtenidas"]),
        "porcentaje": round(total_obtenidas / total_casilleros * 100, 1) if total_casilleros else 0.0,
    }
