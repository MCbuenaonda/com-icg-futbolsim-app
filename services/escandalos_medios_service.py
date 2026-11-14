"""Escándalos de CADENAS DE TV y MEDIOS DE PRENSA (hermano de services/escandalos_service.py, que cubre las marcas). Reglas en config/escandalos.py.

Colección `escandalos_otros` (contenido GLOBAL; `restart_mundial` la borra): {_id "<ronda>:<tv|medio>:<id>", tipo 'tv'|'medio', ref_id, severidad, titular, ronda, desde_seq, hasta_seq}.
Mismo reloj (`seq`) y mismo gancho que las marcas: `evaluar_ronda(juego, ronda)` lo llama escandalos_service.evaluar_ronda, así queda idempotente por ronda.
Efectos: una cadena en crisis paga menos (`efecto_tv`) y sus rivales de país algo más; un medio en crisis pierde credibilidad (`baja_credibilidad`, la resta
prensa_service.credibilidad_actual). Los medios rivales y los internacionales publican notas `ESCANDALO` (sin valoraciones: no tocan la reputación).
"""
import logging
import random
import time
from datetime import datetime
from typing import Any, Dict, Optional

from pymongo import UpdateOne
from pymongo.errors import DuplicateKeyError

from config import escandalos as CE
from services import escandalos as E
from services import prensa as P
from services import prensa_service as PS

logger = logging.getLogger(__name__)
db = PS.db
COL = "escandalos_otros"
_cache: Dict[str, Any] = {"hasta": 0.0, "crisis": [], "rel_tv": {}}


def _seq_reloj() -> int:
    from services.corporativo_universo_service import seq_actual
    return seq_actual()


def _invalidar() -> None:
    _cache["hasta"] = 0.0


def evaluar_ronda(ronda: int, juego: Optional[dict]) -> int:
    """Genera las crisis de cadenas y medios de la ronda. Nunca lanza; la idempotencia la da escandalos_service (una vez por ronda)."""
    try:
        return _generar(ronda, juego)
    except Exception as e:
        logger.error(f"Escándalos de TV y medios: {e}")
        return 0


def _generar(ronda: int, juego: Optional[dict]) -> int:
    from services.corporativo_tv_service import catalogo as catalogo_tv
    rng = random.Random(f"escandalos-otros:{ronda}")
    seq = _seq_reloj()
    en_crisis = {(c["tipo"], c["ref_id"]) for c in db[COL].find({"hasta_seq": {"$gt": seq}}, {"tipo": 1, "ref_id": 1})}
    nuevos = 0
    # Cadenas de TV: más contratos activos = más probabilidad (para que el efecto se sienta)
    cadenas = list(catalogo_tv().values())
    activos = {d["_id"]: d["n"] for d in db["corp_tv_contratos"].aggregate([{"$match": {"estado": "ACTIVO"}}, {"$group": {"_id": "$televisora_id", "n": {"$sum": 1}}}])}
    for _ in range(CE.MAX_TV_POR_RONDA):
        pesos = [0.0 if ("tv", t["id"]) in en_crisis else 1.0 + 2.0 * activos.get(t["id"], 0) for t in cadenas]
        if rng.random() > CE.PROB_TV or sum(pesos) <= 0:
            continue
        t = rng.choices(cadenas, weights=pesos)[0]
        nuevos += _registrar("tv", t, ronda, seq, rng, juego, en_crisis)
    # Medios de prensa: los de más peso (alcance y credibilidad) son más visibles
    medios = PS.medios()
    for _ in range(CE.MAX_MEDIOS_POR_RONDA):
        pesos = [0.0 if ("medio", m["id"]) in en_crisis else P.peso_medio(m) for m in medios]
        if rng.random() > CE.PROB_MEDIO or sum(pesos) <= 0:
            continue
        m = rng.choices(medios, weights=pesos)[0]
        nuevos += _registrar("medio", m, ronda, seq, rng, juego, en_crisis)
    _invalidar()
    return nuevos


def _registrar(tipo: str, ent: dict, ronda: int, seq: int, rng: random.Random, juego: Optional[dict], en_crisis: set) -> int:
    en_crisis.add((tipo, ent["id"]))
    sev = E.elegir_severidad(rng)
    trng = random.Random(f"esc-otros-titular:{ronda}:{tipo}:{ent['id']}")
    tit = E.titular_tv(sev, ent, trng) if tipo == "tv" else E.titular_medio(sev, ent, trng)
    doc = {"_id": f"{ronda}:{tipo}:{ent['id']}", "tipo": tipo, "ref_id": ent["id"], "severidad": sev, "titular": tit, "ronda": ronda, "desde_seq": seq,
           "hasta_seq": seq + CE.DURACION_PARTIDOS, "creado_en": datetime.utcnow()}
    try:
        db[COL].insert_one(doc)
    except DuplicateKeyError:
        return 0
    _notas(doc, ent, juego)
    return 1


def _notas(doc: dict, ent: dict, juego: Optional[dict]) -> None:
    """Hasta MAX_NOTAS medios publican: los rivales del mismo país (si el protagonista es un medio) y los internacionales; nunca el propio medio."""
    if not juego:
        return
    rng = random.Random(f"esc-otros-notas:{doc['_id']}")
    candidatos = [m for m in PS.medios() if m.get("pais_id") is None and not (doc["tipo"] == "medio" and m["id"] == ent["id"])]
    if doc["tipo"] == "medio":
        rivales = [m for m in PS.medios() if m.get("pais_id") is not None and m.get("pais_id") == ent.get("pais_id") and m["id"] != ent["id"]]
        candidatos = rivales[:1] + candidatos
    elegidos = candidatos[:1] + rng.sample(candidatos[1:], min(CE.MAX_NOTAS - 1, max(0, len(candidatos) - 1))) if candidatos else []
    ahora, notas = datetime.utcnow(), []
    for medio in elegidos[:CE.MAX_NOTAS]:
        m = dict(medio, credibilidad=PS.credibilidad_actual(medio))
        nrng = random.Random(f"esc-otros-nota:{doc['_id']}:{medio['id']}")
        per = nrng.choice(medio["equipo"]["periodistas"])
        r = E.nota_otros(doc["severidad"], doc["titular"], ent["nombre"], m, per, nrng)
        notas.append({"_id": f"{doc['_id']}:{medio['id']}:esc", "juego_id": str(juego["_id"]), "fecha": juego.get("fecha"), "hora": juego.get("hora"), "medio_id": medio["id"],
                      "medio": {"nombre": medio["nombre"], "slug": medio["slug"], "papel": medio["papel"], "linea": medio["linea"], "pais_id": medio.get("pais_id")},
                      "periodista": {"nombre": per["nombre"], "rol": per["rol"], "estilo": per["estilo"], "sesgo": per["sesgo"]},
                      "tipo": "ESCANDALO", **r, "valoraciones": [], "peso": P.peso_medio(m), "rol_cobertura": "interesado", "creado_en": ahora})
    if notas:
        db[PS.COL].bulk_write([UpdateOne({"_id": x["_id"]}, {"$setOnInsert": x}, upsert=True) for x in notas], ordered=False)


# --- Lectura de efectos -----------------------------------------------------------------------------------------------------
def _datos() -> Dict[str, Any]:
    if _cache["hasta"] < time.time():
        seq = _seq_reloj()
        crisis = list(db[COL].find({"hasta_seq": {"$gt": seq - CE.DURACION_PARTIDOS}}))   # vigentes y recientes (universos atrasados)
        rel: Dict[int, set] = {}
        for d in db["relaciones"].find({"tipo": "tv", "clase": "rivalidad"}, {"a": 1, "b": 1}):
            rel.setdefault(d["a"], set()).add(d["b"])
            rel.setdefault(d["b"], set()).add(d["a"])
        _cache.update(crisis=crisis, rel_tv=rel, hasta=time.time() + 15)
    return _cache


def efecto_tv(tele_id: int, seq: int) -> Optional[dict]:
    """Efecto sobre lo que paga esa cadena en `seq`: {rebaja, bono, crisis_id, severidad, propia, titular, hasta_seq} o None."""
    d = _datos()
    mejor = None
    for c in d["crisis"]:
        if c["tipo"] != "tv" or not (c["desde_seq"] <= seq < c["hasta_seq"]):
            continue
        propia = c["ref_id"] == tele_id
        if not propia and tele_id not in d["rel_tv"].get(c["ref_id"], ()):
            continue
        e = E.tv_efecto(c["severidad"], rival=not propia)
        fuerza = e["rebaja"] if propia else -e["bono"]
        if mejor is None or fuerza > mejor["_f"]:
            mejor = {**e, "_f": fuerza, "crisis_id": c["_id"], "severidad": c["severidad"], "propia": propia, "titular": c["titular"], "hasta_seq": c["hasta_seq"], "tele_en_crisis": c["ref_id"]}
    if mejor:
        mejor.pop("_f")
    return mejor


def baja_credibilidad(medio_id: int) -> float:
    """Cuánto resta a la credibilidad de un medio por su crisis vigente (0 si no está en crisis)."""
    try:
        seq = _seq_reloj()
        return max((CE.MEDIO_CREDIBILIDAD[c["severidad"]] for c in _datos()["crisis"]
                    if c["tipo"] == "medio" and c["ref_id"] == medio_id and c["desde_seq"] <= seq < c["hasta_seq"]), default=0.0)
    except Exception:
        return 0.0


def crisis_de(tipo: str, ref_id: int) -> Optional[dict]:
    """La crisis vigente propia de una cadena o un medio: {titular, severidad, partidos_restantes} o None (para las vistas)."""
    try:
        seq = _seq_reloj()
        for c in _datos()["crisis"]:
            if c["tipo"] == tipo and c["ref_id"] == ref_id and c["desde_seq"] <= seq < c["hasta_seq"]:
                return {"crisis_id": c["_id"], "titular": c["titular"], "severidad": c["severidad"], "partidos_restantes": max(0, c["hasta_seq"] - seq)}
    except Exception:
        pass
    return None
