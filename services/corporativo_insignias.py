"""
Corporativos Deportivos — insignia "Representado por …" en vistas del torneo (Scouter, detalle previo del partido,
perfil de país y de jugador). Cada usuario ve SU universo: se cargan de una vez sus contratos activos (con caché
corta por usuario) y el template consulta el mapa con el macro `m.insignia_corp`.
"""
import time
from typing import Optional

import certifi
from pymongo import MongoClient

from config.settings import MONGODB_URI
from services.imagenes_pais_service import url_logo_corporativo

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database("mundial")

SEGUNDOS_CACHE = 20
_cache: dict = {}


def representantes(usuario: Optional[dict]) -> dict:
    """{"seleccion": {pais_id: {sigla, logo, mio}}, "jugador": {jugador_id: {...}}} del universo del usuario ({} si no juega)."""
    if not usuario:
        return {}
    uid = str(usuario.get("_id"))
    ahora = time.time()
    if uid in _cache and _cache[uid][0] > ahora:
        return _cache[uid][1]
    universo = db["corp_universos"].find_one({"_id": uid}, {"cargo.sigla": 1, "estado": 1})
    datos = {}
    if universo:
        mia = (universo.get("cargo") or {}).get("sigla") if universo.get("estado") in ("EN_CARGO", "PREAVISO") else None
        datos = {"seleccion": {}, "jugador": {}}
        for c in db["corp_contratos"].find({"universo_id": uid, "activo": True}, {"tipo": 1, "ref_id": 1, "sigla": 1}):
            datos[c["tipo"]][c["ref_id"]] = {"sigla": c["sigla"], "logo": url_logo_corporativo(c["sigla"]), "mio": c["sigla"] == mia}
    _cache[uid] = (ahora + SEGUNDOS_CACHE, datos)
    if len(_cache) > 500:
        _cache.clear()
    return datos
