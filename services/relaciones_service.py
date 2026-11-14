"""Rivalidades y alianzas: servicio con Mongo (lógica en services/relaciones.py, reglas en config/relaciones.py).

Colección `relaciones` (`_id` = "<tipo>:<a>:<b>", a < b). Las de SELECCIONES se recalculan al terminar cada partido entre ellas
(`registrar_partido`, gancho de aplicar_efectos_secundarios: idempotente porque recalcula desde lo jugado, nunca lanza); las de marcas, medios
y cadenas de TV las escribe `generar_relaciones.py` (permanentes). `restart_mundial` borra solo las de selecciones.
"""
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import certifi
from pymongo import MongoClient

from config import relaciones as CR
from config.settings import MONGODB_URI
from services import relaciones as R

logger = logging.getLogger(__name__)
client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database("mundial")
COL = "relaciones"
_cache: Dict[str, Any] = {"hasta": 0.0, "sel": {}}


def _clave(tipo: str, a: int, b: int) -> str:
    x, y = R._par(a, b)
    return f"{tipo}:{x}:{y}"


# --- Selecciones ------------------------------------------------------------------------------------------------------------
def _encuentros(a: int, b: int) -> List[dict]:
    """Los partidos terminados entre dos selecciones, con lo que importa para la rivalidad (calor = polémicas + expulsiones del partido)."""
    juegos = list(db["juegos"].find({"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"},
                                      "$or": [{"equipo_local.id": a, "equipo_visitante.id": b}, {"equipo_local.id": b, "equipo_visitante.id": a}]},
                                     {"fase_id": 1, "resultado.goles_local": 1, "resultado.goles_visitante": 1}))
    if not juegos:
        return []
    ids = [str(j["_id"]) for j in juegos]
    calor: Dict[str, int] = {}
    for p in db["polemicas"].find({"_id": {"$in": ids}}, {"items": 1}):
        calor[p["_id"]] = calor.get(p["_id"], 0) + len(p.get("items") or [])
    for s in db["sanciones_historial"].find({"juego_id": {"$in": ids}, "codigo": {"$in": ["roja_directa", "doble_amarilla"]}}, {"juego_id": 1}):
        calor[s["juego_id"]] = calor.get(s["juego_id"], 0) + 1
    out = []
    for j in juegos:
        r = j.get("resultado") or {}
        out.append({"fase_id": j.get("fase_id"), "dif": abs((r.get("goles_local") or 0) - (r.get("goles_visitante") or 0)), "calor": calor.get(str(j["_id"]), 0)})
    return out


def recalcular_pareja(a: int, b: int, confederaciones: Optional[Dict[int, Any]] = None) -> Optional[dict]:
    """Recalcula la rivalidad entre dos selecciones desde lo jugado y la guarda (o la borra si ya no llega al umbral)."""
    if confederaciones is None:
        confederaciones = {p["id"]: p.get("confederacion_id") for p in db["paises"].find({"id": {"$in": [a, b]}}, {"id": 1, "confederacion_id": 1})}
    valor, motivos = R.intensidad_seleccion(_encuentros(a, b), confederaciones.get(a) is not None and confederaciones.get(a) == confederaciones.get(b))
    x, y = R._par(a, b)
    _id = _clave("seleccion", x, y)
    if valor >= CR.UMBRAL_RIVALIDAD:
        doc = {"tipo": "seleccion", "clase": "rivalidad", "a": x, "b": y, "intensidad": valor, "etiqueta": R.etiqueta(valor), "motivos": motivos, "actualizado": datetime.utcnow()}
        db[COL].update_one({"_id": _id}, {"$set": doc}, upsert=True)
        _cache["hasta"] = 0.0
        return doc
    if db[COL].delete_one({"_id": _id}).deleted_count:
        _cache["hasta"] = 0.0
    return None


def registrar_partido(juego: Optional[Dict[str, Any]]) -> None:
    """Gancho de fin de partido: recalcula la rivalidad entre los dos equipos. Nunca lanza."""
    try:
        if not juego or not juego.get("resultado"):
            return
        a, b = (juego.get("equipo_local") or {}).get("id"), (juego.get("equipo_visitante") or {}).get("id")
        if a is not None and b is not None:
            recalcular_pareja(a, b)
    except Exception as e:
        print(f"No se pudo registrar la rivalidad del partido: {e}")


def reconstruir_selecciones() -> Dict[str, int]:
    """Recalcula TODAS las rivalidades de selecciones desde lo jugado (script). Devuelve {'parejas', 'rivalidades', 'clasicos'}."""
    conf = {p["id"]: p.get("confederacion_id") for p in db["paises"].find({}, {"id": 1, "confederacion_id": 1})}
    parejas = set()
    for j in db["juegos"].find({"estado": "finalizado"}, {"equipo_local.id": 1, "equipo_visitante.id": 1}):
        a, b = (j.get("equipo_local") or {}).get("id"), (j.get("equipo_visitante") or {}).get("id")
        if a is not None and b is not None:
            parejas.add(R._par(a, b))
    db[COL].delete_many({"tipo": "seleccion"})
    rivalidades = clasicos = 0
    for a, b in sorted(parejas):
        d = recalcular_pareja(a, b, conf)
        if d:
            rivalidades += 1
            clasicos += 1 if d["intensidad"] >= CR.UMBRAL_CLASICO else 0
    return {"parejas": len(parejas), "rivalidades": rivalidades, "clasicos": clasicos}


# --- Marcas, medios y cadenas de TV (permanentes) --------------------------------------------------------------------------
def reconstruir_fijas() -> Dict[str, int]:
    from services.corporativo_marcas_service import catalogo
    salida = {}
    for tipo, docs in (("marca", R.relaciones_marcas(list(catalogo().values()))),
                       ("medio", R.relaciones_medios(list(db["medios"].find({}, {"_id": 0, "id": 1, "pais_id": 1, "linea": 1})))),
                       ("tv", R.relaciones_tv(list(db["televisoras"].find({}, {"_id": 0, "id": 1, "pais_id": 1}))))):
        db[COL].delete_many({"tipo": tipo})
        for d in docs:
            _id = _clave(tipo, d["a"], d["b"]) + (":a" if d["clase"] == "alianza" else "")
            db[COL].update_one({"_id": _id}, {"$set": {"tipo": tipo, **d, "etiqueta": "Rivalidad" if d["clase"] == "rivalidad" else "Alianza", "actualizado": datetime.utcnow()}}, upsert=True)
        salida[tipo] = len(docs)
    _cache["hasta"] = 0.0
    return salida


# --- Lectura (caché de 30 s: son pocos cientos de documentos) ---------------------------------------------------------------
def _selecciones() -> Dict[tuple, dict]:
    if _cache["hasta"] < time.time():
        _cache["sel"] = {(d["a"], d["b"]): d for d in db[COL].find({"tipo": "seleccion"}, {"_id": 0})}
        _cache["hasta"] = time.time() + 30
    return _cache["sel"]


def de_partido(a: Optional[int], b: Optional[int]) -> Optional[dict]:
    """La rivalidad entre dos selecciones ({etiqueta, intensidad, motivos, clasico}) o None si no es rivalidad ni clásico."""
    if a is None or b is None:
        return None
    try:
        d = _selecciones().get(R._par(a, b))
    except Exception:
        return None
    if not d:
        return None
    return {"etiqueta": d["etiqueta"], "intensidad": d["intensidad"], "motivos": d["motivos"], "clasico": d["intensidad"] >= CR.UMBRAL_CLASICO}


def texto_motivos(d: dict) -> str:
    return ", ".join(d["motivos"][:3])


def de_ref(tipo: str, ref: int, limite: int = 8) -> Dict[str, List[dict]]:
    """{'rivales': [...], 'aliados': [...]} de una selección, marca, medio o cadena (cada uno con id del otro, intensidad, motivos), la más fuerte primero."""
    docs = list(db[COL].find({"tipo": tipo, "$or": [{"a": ref}, {"b": ref}]}, {"_id": 0}).sort("intensidad", -1))
    out: Dict[str, List[dict]] = {"rivales": [], "aliados": []}
    for d in docs:
        otro = d["b"] if d["a"] == ref else d["a"]
        out["rivales" if d["clase"] == "rivalidad" else "aliados"].append({"id": otro, "intensidad": d["intensidad"], "etiqueta": d.get("etiqueta"), "motivos": d["motivos"]})
    out = {k: v[:limite] for k, v in out.items()}
    nombres = _nombres(tipo, [x["id"] for v in out.values() for x in v])
    for v in out.values():
        for x in v:
            x.update(nombres.get(x["id"], {"nombre": f"#{x['id']}"}))
    return out


def todas(tipo: str, limite: int = 3) -> Dict[int, Dict[str, List[dict]]]:
    """{id: {'rivales': [...], 'aliados': [...]}} de TODAS las marcas/medios/cadenas en una consulta (catálogos); cada uno con nombre del otro lado."""
    docs = list(db[COL].find({"tipo": tipo}, {"_id": 0}).sort("intensidad", -1))
    out: Dict[int, Dict[str, List[dict]]] = {}
    for d in docs:
        for yo, otro in ((d["a"], d["b"]), (d["b"], d["a"])):
            lista = out.setdefault(yo, {"rivales": [], "aliados": []})["rivales" if d["clase"] == "rivalidad" else "aliados"]
            if len(lista) < limite:
                lista.append({"id": otro, "intensidad": d["intensidad"], "motivos": d["motivos"]})
    nombres = _nombres(tipo, list({x["id"] for r in out.values() for v in r.values() for x in v}))
    for r in out.values():
        for v in r.values():
            for x in v:
                x.update(nombres.get(x["id"], {"nombre": f"#{x['id']}"}))
    return out


def _nombres(tipo: str, ids: List[int]) -> Dict[int, dict]:
    """{id: {nombre, bandera?, pais_id?}} del otro lado de cada relación, según el tipo."""
    if not ids:
        return {}
    if tipo == "seleccion":
        return {p["id"]: {"nombre": p["nombre"], "bandera": p.get("bandera") or "", "pais_id": p["id"]} for p in db["paises"].find({"id": {"$in": ids}}, {"id": 1, "nombre": 1, "bandera": 1})}
    col = {"marca": "marcas", "medio": "medios", "tv": "televisoras"}[tipo]
    return {d["id"]: {"nombre": d["nombre"], "pais_id": d.get("pais_id")} for d in db[col].find({"id": {"$in": ids}}, {"id": 1, "nombre": 1, "pais_id": 1})}


def limpiar_selecciones() -> None:
    db[COL].delete_many({"tipo": "seleccion"})
    _cache["hasta"] = 0.0
