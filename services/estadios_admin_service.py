"""
Administración de ciudades sede y estadios (routes/admin_route.py, /admin/estadios; permiso 'gestion_usuarios').

Listado paginado con filtros y edición del NOMBRE del estadio. Al renombrar se actualiza también la copia que
llevan los partidos (`juegos.ubicacion.estadio`) y se deja en null la crónica de los ya jugados (se reescribe sola
con el nombre nuevo, ver cronica_service.asegurar_cronica). Cada cambio queda en `estadios_historial` (permanente).
"""
import certifi
import re
from datetime import datetime
from typing import Optional

from pymongo.mongo_client import MongoClient

from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

POR_PAGINA = 50
LARGO_MIN, LARGO_MAX = 3, 80


class EstadioError(Exception):
    pass


def _filtro(q: str, pais_id: Optional[int], confederacion_id: Optional[int], tipo: str, dueno: str) -> dict:
    filtro: dict = {}
    if pais_id:
        filtro["pais_id"] = pais_id
    elif confederacion_id:
        ids = [p["id"] for p in db["paises"].find({"confederacion_id": confederacion_id}, {"id": 1})]
        filtro["pais_id"] = {"$in": ids}
    if tipo in ("Capital", "Ciudad"):
        filtro["tipo"] = tipo
    if dueno == "con":
        filtro["owner_user_id"] = {"$nin": [None, 0, "0", ""]}
    elif dueno == "libre":
        filtro["owner_user_id"] = {"$in": [None, 0, "0", ""]}
    if q:
        patron = {"$regex": re.escape(q.strip()), "$options": "i"}
        filtro["$or"] = [{"nombre": patron}, {"estadio": patron}, {"pais": patron}]
    return filtro


def opciones_filtros() -> dict:
    paises = list(db["paises"].find({}, {"_id": 0, "id": 1, "nombre": 1, "confederacion_id": 1}).sort("nombre", 1))
    confs = list(db["confederaciones"].find({}, {"_id": 0, "id": 1, "nombre": 1}).sort("id", 1))
    return {"paises": paises, "confederaciones": confs}


def listar(q: str = "", pais_id: Optional[int] = None, confederacion_id: Optional[int] = None, tipo: str = "",
           dueno: str = "", pagina: int = 1) -> dict:
    filtro = _filtro(q, pais_id, confederacion_id, tipo, dueno)
    total = db["ciudades"].count_documents(filtro)
    paginas = max(1, -(-total // POR_PAGINA))
    pagina = min(max(1, pagina), paginas)
    docs = list(db["ciudades"].find(filtro, {"_id": 0, "id": 1, "nombre": 1, "tipo": 1, "estadio": 1, "pais_id": 1, "pais": 1,
                                             "owner_user_id": 1})
                .sort([("pais", 1), ("id", 1)]).skip((pagina - 1) * POR_PAGINA).limit(POR_PAGINA))
    ids = [d["id"] for d in docs]
    partidos = {}
    if ids:
        for g in db["juegos"].aggregate([{"$match": {"ubicacion.id": {"$in": ids}}},
                                         {"$group": {"_id": {"c": "$ubicacion.id", "e": "$estado"}, "n": {"$sum": 1}}}]):
            fila = partidos.setdefault(g["_id"]["c"], {"jugados": 0, "programados": 0})
            fila["programados" if g["_id"]["e"] == "creado" else "jugados"] += g["n"]
    paises = {p["id"]: p for p in db["paises"].find({"id": {"$in": list({d["pais_id"] for d in docs})}},
                                                    {"id": 1, "bandera": 1, "confederacion_id": 1})}
    confs = {c["id"]: c["nombre"] for c in db["confederaciones"].find({}, {"id": 1, "nombre": 1})}
    for d in docs:
        p = paises.get(d["pais_id"], {})
        d["bandera"] = p.get("bandera")
        d["confederacion"] = confs.get(p.get("confederacion_id"), "—")
        d["con_dueno"] = d.get("owner_user_id") not in (None, 0, "0", "")
        d["partidos"] = partidos.get(d["id"], {"jugados": 0, "programados": 0})
    return {"ciudades": docs, "total": total, "pagina": pagina, "paginas": paginas, "por_pagina": POR_PAGINA}


def renombrar_estadio(ciudad_id: int, nombre: str, usuario: str = "") -> dict:
    nombre = " ".join((nombre or "").split())
    if not (LARGO_MIN <= len(nombre) <= LARGO_MAX):
        raise EstadioError(f"El nombre debe tener entre {LARGO_MIN} y {LARGO_MAX} caracteres.")
    ciudad = db["ciudades"].find_one({"id": ciudad_id}, {"id": 1, "estadio": 1, "pais_id": 1, "pais": 1, "nombre": 1})
    if not ciudad:
        raise EstadioError("La ciudad no existe.")
    anterior = ciudad.get("estadio")
    if anterior == nombre:
        return {"estadio": nombre, "cambio": False, "partidos": 0}
    repetido = db["ciudades"].find_one({"pais_id": ciudad["pais_id"], "id": {"$ne": ciudad_id},
                                        "estadio": {"$regex": f"^{re.escape(nombre)}$", "$options": "i"}}, {"nombre": 1})
    if repetido:
        raise EstadioError(f"Ya hay un estadio con ese nombre en {ciudad.get('pais')} ({repetido['nombre']}).")
    db["ciudades"].update_one({"id": ciudad_id}, {"$set": {"estadio": nombre}})
    r = db["juegos"].update_many({"ubicacion.id": ciudad_id}, {"$set": {"ubicacion.estadio": nombre}})
    # la crónica nombra el estadio: en los ya jugados se reescribe sola al abrirlos
    db["juegos"].update_many({"ubicacion.id": ciudad_id, "resultado": {"$type": "object"}}, {"$set": {"resultado.cronica": None}})
    db["estadios_historial"].insert_one({"ciudad_id": ciudad_id, "anterior": anterior, "nuevo": nombre, "usuario": usuario,
                                         "fecha": datetime.now()})
    return {"estadio": nombre, "cambio": True, "partidos": r.modified_count}
