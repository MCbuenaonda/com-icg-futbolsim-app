"""Presidentes de federación y líderes de la afición: servicio con Mongo (lógica y citas en services/directiva.py, reglas en config/directiva.py).

Catálogo permanente: `presidentes` y `lideres` (211 cada uno, `id` = id del país; generar_directiva.py). Voces: colección `directiva_voces` (contenido GLOBAL,
`restart_mundial` la borra): {_id "<juego>:<lado>:<presidente|lider>", juego_id, fecha, hora, lado, pais_id, equipo, hablante, tipo, titulo, cita, creado_en}.
Gancho: `asegurar_voces(juego)` al final de aplicar_efectos_secundarios, después de las declaraciones (idempotente, nunca lanza, no toca partidos en transmisión).
Efectos suaves (los aplican otros servicios con las funciones de aquí): `factor_paciencia` (tecnicos_service), `ajustar_delta` (fanbase_service) y `presion_lider` (tecnicos_service).
"""
import logging
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import UpdateOne

from config import directiva as CD
from services import directiva as D
from services.prensa_service import db

logger = logging.getLogger(__name__)
COL = "directiva_voces"
_cache: Dict[str, Any] = {"hasta": 0.0, "presidentes": {}, "lideres": {}}


def _catalogo() -> Dict[str, Any]:
    if _cache["hasta"] < time.time():
        _cache["presidentes"] = {d["id"]: d for d in db["presidentes"].find({}, {"_id": 0})}
        _cache["lideres"] = {d["id"]: d for d in db["lideres"].find({}, {"_id": 0})}
        _cache["hasta"] = time.time() + 300
    return _cache


def presidente(pais_id: int) -> Optional[dict]:
    return _catalogo()["presidentes"].get(pais_id)


def lider(pais_id: int) -> Optional[dict]:
    return _catalogo()["lideres"].get(pais_id)


# --- Efectos suaves -------------------------------------------------------------------------------------------------------
def factor_paciencia(pais_id: int) -> float:
    try:
        p = presidente(pais_id)
        return D.factor_paciencia(p["rasgo"]) if p else 1.0
    except Exception:
        return 1.0


def ajustar_delta(pais_id: int, delta: int) -> tuple:
    """(delta con el ánimo de la barra, nombre del rasgo si lo cambió)."""
    try:
        l = lider(pais_id)
        if not l:
            return delta, None
        nuevo = D.ajustar_delta_aficionados(delta, l["rasgo"])
        return nuevo, (l["rasgo_nombre"] if nuevo != delta else None)
    except Exception:
        return delta, None


def presion_lider(pais_id: int, gf: int, gc: int) -> float:
    try:
        l = lider(pais_id)
        return D.presion_lider(l["rasgo"], gf, gc) if l else 0.0
    except Exception:
        return 0.0


# --- Voces tras el partido ------------------------------------------------------------------------------------------------
def _lados(j: dict) -> Dict[str, dict]:
    res = j.get("resultado") or {}
    gl, gv = res.get("goles_local") or 0, res.get("goles_visitante") or 0
    eliminacion = (j.get("fase_id") or 0) >= 8
    jid = str(j["_id"])
    out = {}
    for lado, eq, gf, gc in (("local", j["equipo_local"], gl, gv), ("visita", j["equipo_visitante"], gv, gl)):
        ganador_id = res.get("ganador_id")   # en eliminación directa empatada, quien ganó por penales
        gano = gf > gc or (gf == gc and ganador_id is not None and ganador_id == eq["id"])
        resultado = "V" if gano else ("E" if gf == gc and ganador_id is None else "D")
        cese = bool(db["dt_cargos"].find_one({"pais_id": eq["id"], "hasta_juego": jid}, {"_id": 1}))
        dt = ((res.get("dt") or {}).get(lado) or {}).get("nombre")
        out[lado] = {"pais_id": eq["id"], "eq": eq["nombre"], "dt": dt, "res": resultado, "dif": gf - gc, "eliminacion": eliminacion,
                     "eliminado": bool(eliminacion and resultado == "D"), "cese": cese}
    return out


def asegurar_voces(j: Optional[dict]) -> int:
    """Escribe las voces del partido si faltan. Idempotente; nunca lanza."""
    try:
        if not j or j.get("estado") != "finalizado" or (j.get("transmision") or {}).get("estado") == "in_progress":
            return 0
        cat = _catalogo()
        if not cat["presidentes"] and not cat["lideres"]:
            return 0
        jid = str(j["_id"])
        lados = _lados(j)
        voces = D.voces_del_partido(lados, cat["presidentes"], cat["lideres"], random.Random(f"directiva:{jid}"))
        if not voces:
            return 0
        ahora = datetime.utcnow()
        docs = [{"_id": f"{jid}:{v['lado']}:{v['hablante']['tipo']}", "juego_id": jid, "fecha": j.get("fecha"), "hora": j.get("hora"), "lado": v["lado"],
                 "pais_id": lados[v["lado"]]["pais_id"], "equipo": lados[v["lado"]]["eq"], "hablante": v["hablante"], "tipo": v["tipo"], "titulo": v["titulo"],
                 "cita": v["cita"], "creado_en": ahora} for v in voces]
        db[COL].bulk_write([UpdateOne({"_id": d["_id"]}, {"$setOnInsert": d}, upsert=True) for d in docs], ordered=False)
        return len(docs)
    except Exception as e:
        print(f"[directiva] no se pudieron generar las voces: {e}")
        return 0


# --- Vistas ---------------------------------------------------------------------------------------------------------------
def _persona(x: Optional[dict], tipo: str) -> Optional[dict]:
    if not x:
        return None
    from services.imagenes_pais_service import url_imagen_medios
    r = (CD.RASGOS_PRESIDENTE if tipo == "presidente" else CD.RASGOS_LIDER)[x["rasgo"]]
    return {"tipo": tipo, "id": x["id"], "nombre": x["nombre"], "edad": x.get("edad"), "rasgo": x["rasgo"], "rasgo_nombre": x["rasgo_nombre"], "rasgo_icono": r["icono"],
            "rasgo_texto": x["rasgo_texto"], "estilo_nombre": x.get("estilo_nombre"), "federacion": x.get("federacion"), "avatar": url_imagen_medios(x.get("avatar"))}


def _voz_vista(d: dict) -> dict:
    from services.tecnicos_service import fecha_corta
    return {"juego_id": d["juego_id"], "fecha_corta": fecha_corta(d.get("fecha")) or d.get("fecha"), "tipo": d["tipo"], "titulo": d["titulo"], "cita": d["cita"],
            "hablante": d["hablante"], "equipo": d.get("equipo"), "pais_id": d.get("pais_id")}


def de_partido(juego_id: str) -> List[dict]:
    try:
        cat = _catalogo()
        salida = []
        for d in db[COL].find({"juego_id": str(juego_id)}).sort([("lado", 1), ("hablante.tipo", 1)]):
            v = _voz_vista(d)
            v["persona"] = _persona((cat["presidentes"] if d["hablante"]["tipo"] == "presidente" else cat["lideres"]).get(d["pais_id"]), d["hablante"]["tipo"])
            salida.append(v)
        return salida
    except Exception as e:
        print(f"[directiva] de_partido: {e}")
        return []


def de_pais(pais_id: int, limite: int = 4) -> Optional[dict]:
    """{presidente, lider, voces: [últimas]} para la ficha de la selección; None si no hay catálogo."""
    try:
        p, l = _persona(presidente(pais_id), "presidente"), _persona(lider(pais_id), "lider")
        if not p and not l:
            return None
        voces = [_voz_vista(d) for d in db[COL].find({"pais_id": pais_id}).sort([("fecha", -1), ("hora", -1)]).limit(limite)]
        return {"presidente": p, "lider": l, "voces": voces}
    except Exception as e:
        print(f"[directiva] de_pais: {e}")
        return None


def limpiar() -> None:
    db[COL].delete_many({})
