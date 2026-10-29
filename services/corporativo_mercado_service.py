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
    from services.corporativo_universo_service import leer_reloj
    return R.ciclo_de_seq(int(leer_reloj().get("seq") or 0))


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
                                               "rendimiento": 1, "edad": 1, "leyenda": 1, "fama": 1}))
    poder = {k: (v.get("estadisticas") or {}).get("poder") or 0 for k, v in paises.items()}
    # Leyendas con escala propia: no mueven el percentil ni el valor de los jugadores actuales
    valores_j, percentil_j = R.valores_con_leyendas(jugadores, poder)
    datos = {
        "jugadores": valores_j,
        "selecciones": {pid: R.valor_seleccion(p) for pid, p in paises.items()},
        "percentil": percentil_j,
        "info_jugadores": {j["id"]: {"nombre": j.get("nombre"), "pais_id": j.get("pais_id"), "posicion_id": j.get("posicion_id"),
                                     "edad": j.get("edad"), "leyenda": bool(j.get("leyenda"))} for j in jugadores},
        "info_paises": {pid: {"nombre": p.get("nombre"), "bandera": p.get("bandera"), "confederacion_id": p.get("confederacion_id"),
                              "rankin": (p.get("estadisticas") or {}).get("rankin"), "aficionados": p.get("aficionados")}
                        for pid, p in paises.items()},
    }
    _cache_valores.update(clave=clave, datos=datos, hasta=ahora + 60)
    return datos


_cache_calendario = {"clave": None, "datos": None, "hasta": 0.0}


def calendario_paises() -> Dict[int, dict]:
    """
    Cuándo juega cada selección según los partidos YA programados (estado 'creado', en el orden en que se juegan:
    fecha y hora, el mismo de juegos_service.obtener_juego_activo). Igual para todos los universos; se cachea por
    (partidos registrados, pendientes).
    -> {pais_id: {"faltan": partidos hasta el suyo (0 = es el próximo), "ciclo": ciclo global estimado,
                  "rival_id", "local": bool, "juego_id", "posiciones": [índices de todos sus partidos pendientes]}}
    Una selección que no aparece no tiene partido programado (todavía no se sorteó su fase, o fue eliminada).
    """
    if _cache_calendario["datos"] is not None and time.time() < _cache_calendario["hasta"]:
        return _cache_calendario["datos"]
    from services.corporativo_universo_service import leer_reloj
    seq = int(leer_reloj().get("seq") or 0)
    pendientes = list(db["juegos"].find({"estado": "creado"}, {"equipo_local.id": 1, "equipo_visitante.id": 1, "fecha": 1, "hora": 1})
                      .sort([("fecha", 1), ("hora", 1)]))
    clave = (seq, len(pendientes))
    if _cache_calendario["clave"] == clave:
        _cache_calendario["hasta"] = time.time() + 30
        return _cache_calendario["datos"]
    datos: Dict[int, dict] = {}
    for i, j in enumerate(pendientes):
        loc, vis = (j.get("equipo_local") or {}).get("id"), (j.get("equipo_visitante") or {}).get("id")
        for pid, rival, local in ((loc, vis, True), (vis, loc, False)):
            if pid is None:
                continue
            d = datos.get(pid)
            if d is None:
                datos[pid] = {"faltan": i, "ciclo": R.ciclo_de_seq(seq + i + 1), "rival_id": rival, "local": local,
                              "juego_id": str(j["_id"]), "posiciones": [i]}
            else:
                d["posiciones"].append(i)
    _cache_calendario.update(clave=clave, datos=datos, hasta=time.time() + 30)
    return datos


def partidos_en_ciclos(pais_id: int, ciclos: int) -> int:
    """Cuántos partidos programados tiene la selección en los próximos 'ciclos' ciclos (contando el actual)."""
    d = calendario_paises().get(pais_id)
    if not d:
        return 0
    limite = ciclos * C.PARTIDOS_POR_CICLO - (_cache_calendario["clave"][0] % C.PARTIDOS_POR_CICLO)
    return sum(1 for i in d["posiciones"] if i < limite)


def afines(sigla: str) -> set:
    """Ids de las selecciones de la región de afinidad del corporativo."""
    a = C.CORPORATIVO_POR_SIGLA[sigla]["afinidad"]
    info = valores()["info_paises"]
    return {pid for pid, p in info.items() if pid in a["paises"] or p.get("confederacion_id") in a["confederaciones"]}


def valor_contrato(tipo: str, ref_id: int) -> int:
    v = valores()
    return int((v["selecciones"] if tipo == "seleccion" else v["jugadores"]).get(ref_id, 0))
