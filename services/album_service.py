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
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

COSTO_SOBRE = 100
CANTIDAD_ESTAMPAS_POR_SOBRE = 5
BONUS_ESTAMPA_DUPLICADA = 10

TIPOS_ESTAMPA = ["JUGADOR", "CIUDAD", "PAIS"]

COLECCION_POR_TIPO = {"JUGADOR": "jugadores", "CIUDAD": "ciudades", "PAIS": "paises"}
CAMPO_ALBUM_POR_TIPO = {"JUGADOR": "owned_jugadores", "CIUDAD": "owned_ciudades", "PAIS": "owned_paises"}


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
def buy_and_open_pack(usuario_id: str) -> dict:
    """
    Cobra 100 pts, genera 5 estampas aleatorias (JUGADOR/CIUDAD/PAIS) y
    actualiza el álbum del usuario. Las duplicadas no se agregan: se
    "venden" automáticamente por 10 pts que se acreditan al saldo.
    """
    usuario_oid = ObjectId(usuario_id)
    usuario = db['usuarios'].find_one({"_id": usuario_oid})
    if not usuario or not usuario.get("activo", True):
        raise ValueError("Usuario no encontrado o inactivo")

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
        album = {"user_id": usuario_oid, "owned_jugadores": [], "owned_paises": [], "owned_ciudades": []}
        db['user_albums'].insert_one(album)

    estampas_obtenidas = []
    bonus_total = 0

    for _ in range(CANTIDAD_ESTAMPAS_POR_SOBRE):
        tipo = random.choice(TIPOS_ESTAMPA)
        coleccion = COLECCION_POR_TIPO[tipo]
        campo_album = CAMPO_ALBUM_POR_TIPO[tipo]

        muestra = list(db[coleccion].aggregate([{"$sample": {"size": 1}}]))
        if not muestra:
            continue
        doc = muestra[0]
        estampa_id = doc["id"]

        ya_la_tiene = estampa_id in album.get(campo_album, [])

        if ya_la_tiene:
            bonus_total += BONUS_ESTAMPA_DUPLICADA
            estampas_obtenidas.append({
                "tipo": tipo, "id": estampa_id, "nombre": doc.get("nombre"),
                "duplicado": True, "bonus_puntos": BONUS_ESTAMPA_DUPLICADA
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
        "cost_paid": COSTO_SOBRE,
        "stickers_obtained": estampas_obtenidas,
        "created_at": datetime.now()
    }
    resultado = db['pack_purchases'].insert_one(compra)
    compra["_id"] = resultado.inserted_id

    return _serializar_compra(compra)


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
        "total_jugadores": len(owned_jugadores),
        "total_paises": len(owned_paises),
        "total_ciudades": len(owned_ciudades),
        "llenado_por_pais": llenado_por_pais,
        "paises_detalle": paises_detalle,
        "ciudades_detalle": ciudades_detalle
    }
