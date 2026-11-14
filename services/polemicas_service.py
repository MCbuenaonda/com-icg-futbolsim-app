"""Polémicas arbitrales: servicio con Mongo. La lógica y los textos están en services/polemicas.py; las reglas en config/polemicas.py.

Colección `polemicas` (contenido GLOBAL; `restart_mundial` la borra): {_id = juego_id, juego_id, fecha, hora, total, items [{codigo, peso, responsable,
arbitro, arbitro_id, lado 'L'|'V' perjudicado, equipo_perjudicado_id, jugador, minuto, titular}]}. Las NOTAS de los medios son notas normales de `prensa`
con tipo "POLEMICA" y `valoraciones` sobre el árbitro (tipo `arbitro`, id = `arbitros.id`), así la reputación mediática (`prensa_reputacion`),
las fichas y la red social las reconocen. Gancho: `asegurar_polemicas(juego)` en aplicar_efectos_secundarios, ANTES de las declaraciones (el DT
perjudicado lee de aquí si debe reclamar). Idempotente, nunca lanza, no toca partidos en transmisión.

La reputación se desgasta CON EL TIEMPO (RECUPERACION_POR_PARTIDO por partido terminado desde la última nota): `puntaje_actual(arbitro_id)`.
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from pymongo import UpdateOne

from config import polemicas as CP
from services import polemicas as PO
from services import prensa as P
from services import prensa_service as PS

logger = logging.getLogger(__name__)
db = PS.db
COL = "polemicas"
PUESTO = {"central": "Arbitro central", "var": "Arbitro VAR"}
_cache_terminados = {"hasta": 0.0, "n": 0}


def _terminados() -> int:
    import time
    if _cache_terminados["hasta"] < time.time():
        _cache_terminados.update(n=db["juegos"].count_documents({"estado": "finalizado"}), hasta=time.time() + 30)
    return _cache_terminados["n"]


def _id_arbitro(nombre: str, rol: str) -> Optional[int]:
    a = db["arbitros"].find_one({"nombre": nombre, "puesto": PUESTO.get(rol)}, {"id": 1})
    return a.get("id") if a else None


def _analisis(j: dict) -> dict:
    from services.cronica_service import analizar
    return analizar(j)


def asegurar_polemicas(j: Optional[dict], terminados_ref: Optional[int] = None) -> int:
    """Escribe las polémicas del partido y las notas de la prensa si faltan. Idempotente; nunca lanza."""
    try:
        if not j or j.get("estado") != "finalizado" or (j.get("transmision") or {}).get("estado") == "in_progress" or not PS.medios():
            return 0
        jid = str(j["_id"])
        if db[COL].find_one({"_id": jid}, {"_id": 1}):
            return 0
        h = _analisis(j)
        items = PO.detectar(h)
        if not items:
            return 0
        for i in items:
            i["arbitro_id"] = _id_arbitro(i["arbitro"], i["responsable"])
            i["equipo_perjudicado_id"] = (j["equipo_local"] if i["lado"] == "L" else j["equipo_visitante"]).get("id")
        total = PO.total(items)
        rng = P.semilla("polemicas", jid)
        for i in items:
            i["titular"] = PO.titular(i, h, P.semilla("polemica-titular", jid, i["codigo"], i.get("minuto")))
        doc = {"_id": jid, "juego_id": jid, "fecha": j.get("fecha"), "hora": j.get("hora"), "total": total, "items": items, "creado_en": datetime.utcnow()}
        db[COL].insert_one(doc)
        if total < CP.UMBRAL_NOTA:
            return 1
        # Notas de la prensa sobre el árbitro responsable de la jugada más pesada
        principal = max(items, key=lambda i: i["peso"])
        ctx = PS.contexto(j)
        elegidos = P.elegir_medios(ctx, PS.medios(), P.semilla("polemicas-medios", jid))
        perjudicado_id = principal["equipo_perjudicado_id"]
        elegidos.sort(key=lambda t: 0 if t[0].get("pais_id") == perjudicado_id else 1)   # primero la prensa del perjudicado
        ahora, notas = datetime.utcnow(), []
        for medio, rol in elegidos[:CP.MAX_NOTAS]:
            m = dict(medio, credibilidad=PS.credibilidad_actual(medio))
            nrng = P.semilla("polemica-nota", jid, medio["id"])
            per = nrng.choice(medio["equipo"]["periodistas"])
            r = PO.nota(principal, h, m, per, medio.get("pais_id") == perjudicado_id, nrng)
            val = {"tipo": "arbitro", "id": principal["arbitro_id"], "nombre": principal["arbitro"], "valor": r["tono"]}
            notas.append({"_id": f"{jid}:{medio['id']}:pol", "juego_id": jid, "fecha": j.get("fecha"), "hora": j.get("hora"), "medio_id": medio["id"],
                          "medio": {"nombre": medio["nombre"], "slug": medio["slug"], "papel": medio["papel"], "linea": medio["linea"], "pais_id": medio.get("pais_id")},
                          "periodista": {"nombre": per["nombre"], "rol": per["rol"], "estilo": per["estilo"], "sesgo": per["sesgo"]},
                          "tipo": "POLEMICA", **r, "valoraciones": [val] if principal["arbitro_id"] is not None else [], "peso": P.peso_medio(m),
                          "rol_cobertura": rol, "creado_en": ahora})
        if notas:
            res = db[PS.COL].bulk_write([UpdateOne({"_id": x["_id"]}, {"$setOnInsert": x}, upsert=True) for x in notas], ordered=False)
            ids_nuevos = set(res.upserted_ids.values())
            nuevas = [x for x in notas if x["_id"] in ids_nuevos and x["valoraciones"]]
            if nuevas:
                PS.actualizar_reputacion(nuevas)
                if principal["arbitro_id"] is not None:   # marca cuándo fue la última nota, para desgastar el puntaje con el tiempo
                    db[PS.COL_REP].update_one({"_id": f"arbitro:{principal['arbitro_id']}"}, {"$set": {"terminados_ref": terminados_ref if terminados_ref is not None else _terminados()}})
        return 1
    except Exception as e:
        print(f"[polemicas] no se pudieron generar: {e}")
        return 0


# --- Reputación con recuperación ----------------------------------------------------------------------------------------
def puntaje_actual(arbitro_id: Optional[int], terminados: Optional[int] = None) -> Optional[float]:
    """Puntaje de reputación del árbitro desgastado por los partidos terminados desde su última nota (None si nunca salió)."""
    if arbitro_id is None:
        return None
    d = db[PS.COL_REP].find_one({"_id": f"arbitro:{arbitro_id}"})
    return _desgastado(d, terminados)


def _desgastado(d: Optional[dict], terminados: Optional[int] = None) -> Optional[float]:
    if not d:
        return None
    n = _terminados() if terminados is None else terminados
    desde = max(0, n - int(d.get("terminados_ref") or n))
    return round(d["puntaje"] * (CP.RECUPERACION_POR_PARTIDO ** desde), 2)


_cache_puntajes = {"hasta": 0.0, "datos": {}}


def puntajes_centrales() -> Dict[int, float]:
    """{arbitro_id: puntaje ya desgastado} de todos los árbitros con reputación (la designación de los centrales). Caché de 15 s."""
    import time
    if _cache_puntajes["hasta"] < time.time():
        n = _terminados()
        _cache_puntajes.update(datos={d["id"]: _desgastado(d, n) for d in db[PS.COL_REP].find({"tipo": "arbitro"})}, hasta=time.time() + 15)
    return _cache_puntajes["datos"]


def reputacion_vista(arbitro_id: Optional[int]) -> Optional[dict]:
    p = puntaje_actual(arbitro_id)
    if p is None:
        return None
    return {"puntaje": round(p), "centrada": round(p), "etiqueta": P.etiqueta_reputacion(p),
            "color": "#4ade80" if p >= 8 else ("#f87171" if p <= -8 else "#94a3b8")}


# --- Vistas -----------------------------------------------------------------------------------------------------------------
def de_partido(juego_id: str) -> Optional[dict]:
    d = db[COL].find_one({"_id": str(juego_id)})
    if not d:
        return None
    return {"total": d["total"], "items": [{k: i.get(k) for k in ("codigo", "peso", "responsable", "arbitro", "arbitro_id", "jugador", "minuto", "titular")} for i in d["items"]],
            "con_nota": d["total"] >= CP.UMBRAL_NOTA}


def limpiar() -> None:
    db[COL].delete_many({})
