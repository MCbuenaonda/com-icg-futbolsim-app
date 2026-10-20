"""
Corporativos Deportivos — mercado: valuaciones de selecciones y jugadores (reglas puras en
services/corporativo_reglas.py). Las valuaciones son las mismas para todos los universos (dependen del mundo
del torneo, no del usuario) y se cachean en memoria por ciclo del registro global: se recalculan solo cuando
cambia el ciclo (cada PARTIDOS_POR_CICLO partidos).
"""
import time
from typing import Dict

import certifi
from pymongo import MongoClient

from config import corporativos as C
from config.settings import MONGODB_URI
from services import corporativo_reglas as R

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database("mundial")

_cache_valores = {"clave": None, "datos": None, "hasta": 0.0}


def _ciclo_global() -> int:
    reloj = db["corp_reloj"].find_one({"_id": "partidos"}) or {}
    return R.ciclo_de_seq(int(reloj.get("seq") or 0))


def valores() -> Dict[str, dict]:
    """
    {"jugadores": {id: valor}, "selecciones": {id: valor}, "percentil": {jugador_id: 0..1},
     "info_jugadores": {id: {nombre, pais_id, posicion_id, edad}}, "info_paises": {id: {nombre, bandera, confederacion_id, rankin}}}
    """
    ahora = time.time()
    if _cache_valores["datos"] is not None and ahora < _cache_valores["hasta"]:
        return _cache_valores["datos"]
    clave = _ciclo_global()
    if _cache_valores["datos"] is not None and clave == _cache_valores["clave"]:
        _cache_valores["hasta"] = ahora + 60
        return _cache_valores["datos"]
    paises = {p["id"]: p for p in db["paises"].find({}, {"_id": 0, "id": 1, "nombre": 1, "bandera": 1, "confederacion_id": 1,
                                                          "valor": 1, "aficionados": 1, "estadisticas.rankin": 1,
                                                          "estadisticas.poder": 1})}
    jugadores = list(db["jugadores"].find({}, {"_id": 0, "id": 1, "nombre": 1, "pais_id": 1, "posicion_id": 1, "overall": 1,
                                               "rendimiento": 1, "edad": 1}))
    poder = {k: (v.get("estadisticas") or {}).get("poder") or 0 for k, v in paises.items()}
    valores_j = R.valores_jugadores(jugadores, poder)
    datos = {
        "jugadores": valores_j,
        "selecciones": {pid: R.valor_seleccion(p) for pid, p in paises.items()},
        "percentil": R.percentiles(valores_j),
        "info_jugadores": {j["id"]: {"nombre": j.get("nombre"), "pais_id": j.get("pais_id"), "posicion_id": j.get("posicion_id"),
                                     "edad": j.get("edad")} for j in jugadores},
        "info_paises": {pid: {"nombre": p.get("nombre"), "bandera": p.get("bandera"), "confederacion_id": p.get("confederacion_id"),
                              "rankin": (p.get("estadisticas") or {}).get("rankin")} for pid, p in paises.items()},
    }
    _cache_valores.update(clave=clave, datos=datos, hasta=ahora + 60)
    return datos


def afines(sigla: str) -> set:
    """Ids de las selecciones de la región de afinidad del corporativo."""
    a = C.CORPORATIVO_POR_SIGLA[sigla]["afinidad"]
    info = valores()["info_paises"]
    return {pid for pid, p in info.items() if pid in a["paises"] or p.get("confederacion_id") in a["confederaciones"]}


def valor_contrato(tipo: str, ref_id: int) -> int:
    v = valores()
    return int((v["selecciones"] if tipo == "seleccion" else v["jugadores"]).get(ref_id, 0))
