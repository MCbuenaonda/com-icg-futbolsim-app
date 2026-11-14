"""Homenajes a leyendas: servicio con Mongo (lógica en services/homenajes.py, reglas en config/homenajes.py).

Colección `homenajes` (`_id` = juego; `restart_mundial` la borra): {juego_id, mundial_id, pais_id, jugador_id, nombre, fama, pct, delta, aplicado_en}.
`leyenda_de_honor(juego)` es lo que se anuncia en la previa (determinístico) y, una vez jugado el partido, el homenaje registrado.
Gancho: `registrar_partido(juego)` en aplicar_efectos_secundarios (diferido en vivo, idempotente por partido, nunca lanza): suma los aficionados a la selección
(`fanbase_service._aplicar_delta_aficionados`, con su historial) y publica una nota `HOMENAJE` en `prensa` anclada al partido.
"""
import logging
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo.errors import DuplicateKeyError

from config import homenajes as CH
from services import homenajes as H
from services import prensa_service as PS

logger = logging.getLogger(__name__)
db = PS.db
COL = "homenajes"


def _es_de_honor(juego: dict) -> bool:
    if (juego.get("fase_id") or 0) >= CH.FASE_HONOR:
        return True
    try:
        from services.relaciones_service import de_partido
        rel = de_partido((juego.get("equipo_local") or {}).get("id"), (juego.get("equipo_visitante") or {}).get("id"))
        return bool(rel and rel["clasico"])
    except Exception:
        return False


def _equipos(juego: dict) -> List[dict]:
    mid = str(juego.get("mundial_id") or "")
    ids = [(juego.get("equipo_local") or {}).get("id"), (juego.get("equipo_visitante") or {}).get("id")]
    nombres = {(juego.get("equipo_local") or {}).get("id"): (juego.get("equipo_local") or {}).get("nombre"), (juego.get("equipo_visitante") or {}).get("id"): (juego.get("equipo_visitante") or {}).get("nombre")}
    por_pais: Dict[int, List[dict]] = {i: [] for i in ids}
    for j in db["jugadores"].find({"pais_id": {"$in": [i for i in ids if i is not None]}, "leyenda": True}, {"id": 1, "nombre": 1, "fama": 1, "pais_id": 1}):
        por_pais[j["pais_id"]].append({"id": j["id"], "nombre": j["nombre"], "fama": j.get("fama") or 0})
    usados = {d["_id"]: d["n"] for d in db[COL].aggregate([{"$match": {"mundial_id": mid, "pais_id": {"$in": ids}}}, {"$group": {"_id": "$pais_id", "n": {"$sum": 1}}}])}
    return [{"pais_id": i, "nombre": nombres.get(i), "leyendas": por_pais.get(i, []), "tope": usados.get(i, 0) >= CH.TOPE_POR_SELECCION} for i in ids if i is not None]


def leyenda_de_honor(juego: Optional[dict]) -> Optional[dict]:
    """El homenaje del partido: el registrado si ya se jugó, o el previsto ({..., confirmado: False}) si es un partido de honor. None si no lo es."""
    try:
        if not juego:
            return None
        jid = str(juego["_id"])
        d = db[COL].find_one({"_id": jid})
        if d:
            return {"pais_id": d["pais_id"], "pais": d.get("pais"), "jugador_id": d["jugador_id"], "nombre": d["nombre"], "fama": d["fama"], "pct": d["pct"], "delta": d.get("delta"), "confirmado": True}
        if not _es_de_honor(juego):
            return None
        h = H.elegir(_equipos(juego), f"homenaje:{jid}")
        return {**h, "delta": None, "confirmado": False} if h else None
    except Exception as e:
        logger.error(f"Homenajes: {e}")
        return None


def registrar_partido(juego: Optional[dict]) -> None:
    """Gancho de fin de partido: si fue un partido de honor, suma los aficionados y publica la nota. Idempotente; nunca lanza."""
    try:
        if not juego or juego.get("estado") != "finalizado" or not juego.get("resultado"):
            return
        jid = str(juego["_id"])
        if db[COL].find_one({"_id": jid}, {"_id": 1}) or not _es_de_honor(juego):
            return
        h = H.elegir(_equipos(juego), f"homenaje:{jid}")
        if not h:
            return
        from services import fanbase_service as FB
        paises = db["paises"]
        actual = (paises.find_one({"id": h["pais_id"]}, {"aficionados": 1}) or {}).get("aficionados") or FB.AFICIONADOS_INICIAL
        delta = int(round(actual * h["pct"]))
        try:
            db[COL].insert_one({"_id": jid, "juego_id": jid, "mundial_id": str(juego.get("mundial_id") or ""), "pais_id": h["pais_id"], "pais": h["pais"], "jugador_id": h["jugador_id"],
                                "nombre": h["nombre"], "fama": h["fama"], "pct": h["pct"], "delta": delta, "aplicado_en": datetime.utcnow()})
        except DuplicateKeyError:
            return
        total = FB._aplicar_delta_aficionados(paises, h["pais_id"], delta)
        FB._registrar_historial_aficionados(h["pais_id"], jid, delta, total, f"Homenaje a la leyenda {h['nombre']}")
        _nota(juego, h, delta)
    except Exception as e:
        print(f"No se pudo registrar el homenaje del partido: {e}")


def _nota(juego: dict, h: dict, delta: int) -> None:
    medios = PS.medios()
    if not medios:
        return
    medio = next((x for x in medios if x.get("pais_id") == h["pais_id"] and x.get("papel") == "deportivo"), None) or next((x for x in medios if x.get("pais_id") is None), medios[0])
    rng = random.Random(f"homenaje-nota:{juego['_id']}")
    per = rng.choice(medio["equipo"]["periodistas"])
    local, visita = (juego.get("equipo_local") or {}).get("nombre", ""), (juego.get("equipo_visitante") or {}).get("nombre", "")
    texto = H.nota(h, delta, local, visita, rng)
    db[PS.COL].update_one({"_id": f"{juego['_id']}:homenaje"}, {"$setOnInsert": {
        "_id": f"{juego['_id']}:homenaje", "juego_id": str(juego["_id"]), "fecha": juego.get("fecha"), "hora": juego.get("hora"), "medio_id": medio["id"],
        "medio": {"nombre": medio["nombre"], "slug": medio["slug"], "papel": medio["papel"], "linea": medio["linea"], "pais_id": medio.get("pais_id")},
        "periodista": {"nombre": per["nombre"], "rol": per["rol"], "estilo": per["estilo"], "sesgo": per["sesgo"]},
        "tipo": "HOMENAJE", "tono": 0.7, "categoria_tono": "elogio", "titular": texto.split(" El cariño")[0], "texto": texto, "valoraciones": [], "peso": 1.0,
        "rol_cobertura": "interesado", "creado_en": datetime.utcnow()}}, upsert=True)


# --- Vistas -----------------------------------------------------------------------------------------------------------------
def leyenda_simbolo(pais_id: int) -> Optional[dict]:
    """La leyenda más famosa de una selección (su símbolo): {id, nombre, fama, homenajes}."""
    try:
        d = db["jugadores"].find_one({"pais_id": pais_id, "leyenda": True}, {"id": 1, "nombre": 1, "fama": 1}, sort=[("fama", -1)])
        if not d:
            return None
        return {"id": d["id"], "nombre": d["nombre"], "fama": round(d.get("fama") or 0, 2), "homenajes": db[COL].count_documents({"jugador_id": d["id"]})}
    except Exception:
        return None


def homenajes_de(jugador_id: int) -> int:
    try:
        return db[COL].count_documents({"jugador_id": jugador_id})
    except Exception:
        return 0


def limpiar() -> None:
    db[COL].delete_many({})
