"""Crisis de imagen DEPORTIVAS de jugadores, DTs y árbitros (hermano de escandalos_service.py —marcas— y escandalos_medios_service.py —cadenas y medios—).
Reglas en config/escandalos.py, titulares en services/escandalos.py.

Colección `escandalos_deportivos` (contenido GLOBAL; `restart_mundial` la borra): {_id "<ronda>:<tipo>:<id>", tipo 'jugador'|'dt'|'arbitro', ref_id, nombre, pais_id, motivo,
severidad, titular, juego_id, desde_seq, hasta_seq}. Gancho: `evaluar_ronda(ronda, juego)` lo llama escandalos_service.evaluar_ronda (idempotente por ronda).
NO es azar puro: se mira lo que pasó en los últimos PARTIDOS_RONDA partidos (una expulsión, una goleada en contra, un DT con mucha presión, un árbitro con polémicas
repetidas) y de ahí se sortea (uno de cada tipo como máximo por ronda). Las leyendas no entran. Efectos, todos suaves:
  - 2-3 medios publican notas `ESCANDALO` CON `valoraciones` sobre la persona: bajan su reputación mediática (y de ahí el riesgo y el encaje de las marcas, la presión
    del DT, la designación del árbitro) y, si el jugador es de tu cartera, abren una ENTREVISTA (corporativo_prensa_service.solicitar).
  - `efecto_jugador`: riesgo de corte extra y menos encaje de las marcas de ese jugador mientras dure; `presion_dt`: presión extra por partido sobre ese DT.
"""
import logging
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import UpdateOne
from pymongo.errors import DuplicateKeyError

from config import escandalos as CE
from services import escandalos as E
from services import prensa as P
from services import prensa_service as PS

logger = logging.getLogger(__name__)
db = PS.db
COL = "escandalos_deportivos"
_cache: Dict[str, Any] = {"hasta": 0.0, "crisis": []}


def _seq_reloj() -> int:
    from services.corporativo_universo_service import seq_actual
    return seq_actual()


def _invalidar() -> None:
    _cache["hasta"] = 0.0


# --- Candidatos: lo que pasó en los últimos partidos -------------------------------------------------------------------------------
def _juegos_recientes(n: int) -> List[dict]:
    return list(db["juegos"].find({"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}},
                                  {"equipo_local.id": 1, "equipo_local.nombre": 1, "equipo_visitante.id": 1, "equipo_visitante.nombre": 1, "resultado.goles_local": 1,
                                   "resultado.goles_visitante": 1, "resultado.dt": 1, "resultado.eventos.tipo": 1, "resultado.eventos.equipo": 1, "resultado.eventos.jugadores": 1})
                          .sort([("fecha", -1), ("hora", -1)]).limit(n))


def candidatos(juegos: List[dict], ventana_ids: Optional[List[str]] = None, con_presion: bool = True) -> List[dict]:
    """[{tipo, ref_id, nombre, pais_id, motivo, peso, ctx}] de los hechos de `juegos`. Sin escribir nada. `ventana_ids` = los partidos donde se cuentan las polémicas repetidas
    de un árbitro (por defecto los últimos VENTANA_ARBITRO); `con_presion=False` omite los DT por presión (la calibración con partidos viejos no conoce la presión de entonces)."""
    salida: List[dict] = []
    jugadores_con_roja = set()
    for j in juegos:
        r = j.get("resultado") or {}
        gl, gv = r.get("goles_local") or 0, r.get("goles_visitante") or 0
        lados = (("local", j["equipo_local"], j["equipo_visitante"], gl, gv), ("visita", j["equipo_visitante"], j["equipo_local"], gv, gl))
        for lado, eq, rival, gf, gc in lados:
            ctx = {"eq": eq["nombre"], "rival": rival["nombre"], "gf": gf, "gc": gc}
            # expulsiones
            for e in r.get("eventos") or []:
                t = e.get("tipo") or ""
                if e.get("equipo") != eq["nombre"] or not e.get("jugadores"):
                    continue
                motivo = "doble" if "DOBLE AMARILLA" in t else ("roja" if "TARJETA ROJA" in t else None)
                if not motivo:
                    continue
                d = db["jugadores"].find_one({"pais_id": eq["id"], "nombre": e["jugadores"][0], "leyenda": {"$ne": True}}, {"id": 1, "nombre": 1})
                if d and d["id"] not in jugadores_con_roja:
                    jugadores_con_roja.add(d["id"])
                    salida.append({"tipo": "jugador", "ref_id": d["id"], "nombre": d["nombre"], "pais_id": eq["id"], "motivo": motivo, "peso": 1.0 if motivo == "roja" else 0.6, "ctx": ctx})
            if gc - gf >= 3:
                # el DT de una goleada en contra y los jugadores frustrados de ese equipo
                dt = ((r.get("dt") or {}).get(lado) or {})
                if dt.get("id") is not None:
                    salida.append({"tipo": "dt", "ref_id": dt["id"], "nombre": dt.get("nombre", "el técnico"), "pais_id": eq["id"], "motivo": "goleada", "peso": 0.7, "ctx": ctx})
                for d in db["jugadores"].find({"pais_id": eq["id"], "estado_animo": "Frustrado", "leyenda": {"$ne": True}}, {"id": 1, "nombre": 1}).sort("overall", -1).limit(2):
                    if d["id"] not in jugadores_con_roja:
                        salida.append({"tipo": "jugador", "ref_id": d["id"], "nombre": d["nombre"], "pais_id": eq["id"], "motivo": "frustrado", "peso": 0.5, "ctx": ctx})
    # DTs con mucha presión acumulada (aunque no haya habido goleada)
    for cargo in (db["dt_cargos"].find({"hasta_juego": None, "presion": {"$gte": CE.PRESION_DT_ALTA}}, {"dt_id": 1, "pais_id": 1, "presion": 1}).sort("presion", -1).limit(3) if con_presion else []):
        dt = db["directores_tecnicos"].find_one({"id": cargo["dt_id"]}, {"nombre": 1})
        pais = db["paises"].find_one({"id": cargo["pais_id"]}, {"nombre": 1}) or {}
        if dt:
            salida.append({"tipo": "dt", "ref_id": cargo["dt_id"], "nombre": dt["nombre"], "pais_id": cargo["pais_id"], "motivo": "presion", "peso": 0.5, "ctx": {"eq": pais.get("nombre", "su selección")}})
    # árbitros con polémicas repetidas (alguna en estos partidos)
    recientes = {str(j["_id"]) for j in juegos}
    ventana = ventana_ids if ventana_ids is not None else [str(j["_id"]) for j in _juegos_recientes(CE.VENTANA_ARBITRO)]
    cuenta: Dict[int, int] = {}
    en_recientes = set()
    nombres: Dict[int, str] = {}
    for pol in db["polemicas"].find({"_id": {"$in": ventana}}, {"items.arbitro_id": 1, "items.arbitro": 1}):
        for aid in {it["arbitro_id"] for it in pol.get("items") or [] if it.get("arbitro_id") is not None}:
            cuenta[aid] = cuenta.get(aid, 0) + 1
            nombres[aid] = next((it["arbitro"] for it in pol["items"] if it.get("arbitro_id") == aid), "el árbitro")
            if pol["_id"] in recientes:
                en_recientes.add(aid)
    for aid, n in cuenta.items():
        if n >= CE.MIN_POLEMICAS_ARBITRO and aid in en_recientes:
            a = db["arbitros"].find_one({"id": aid}, {"pais_id": 1}) or {}
            salida.append({"tipo": "arbitro", "ref_id": aid, "nombre": nombres[aid], "pais_id": a.get("pais_id"), "motivo": "reincidente", "peso": float(n), "ctx": {"n": n}})
    return salida


def elegir(cands: List[dict], en_crisis: set, rng: random.Random) -> List[dict]:
    """Como máximo uno de cada tipo: sortea (con PROB_DEPORTIVO) entre sus candidatos, ponderando por el peso del hecho."""
    elegidos = []
    for tipo in ("jugador", "dt", "arbitro"):
        lista = [c for c in cands if c["tipo"] == tipo and (tipo, c["ref_id"]) not in en_crisis]
        if lista and rng.random() < CE.PROB_DEPORTIVO[tipo]:
            elegidos.append(rng.choices(lista, weights=[c["peso"] for c in lista])[0])
    return elegidos


# --- Generación ----------------------------------------------------------------------------------------------------------------------
def evaluar_ronda(ronda: int, juego: Optional[dict]) -> int:
    """Genera las crisis deportivas de la ronda. Nunca lanza; la idempotencia la da escandalos_service (una vez por ronda)."""
    try:
        seq = _seq_reloj()
        en_crisis = {(c["tipo"], c["ref_id"]) for c in db[COL].find({"hasta_seq": {"$gt": seq}}, {"tipo": 1, "ref_id": 1})}
        rng = random.Random(f"esc-deportivos:{ronda}")
        nuevos = 0
        for c in elegir(candidatos(_juegos_recientes(CE.PARTIDOS_RONDA)), en_crisis, rng):
            nuevos += _registrar(c, ronda, seq, rng, juego)
        _invalidar()
        return nuevos
    except Exception as e:
        logger.error(f"Escándalos deportivos: {e}")
        return 0


def _registrar(c: dict, ronda: int, seq: int, rng: random.Random, juego: Optional[dict]) -> int:
    sev = E.elegir_severidad(rng)
    titular = E.titular_deportivo(c["tipo"], c["motivo"], c, random.Random(f"esc-dep-titular:{ronda}:{c['tipo']}:{c['ref_id']}"))
    doc = {"_id": f"{ronda}:{c['tipo']}:{c['ref_id']}", "tipo": c["tipo"], "ref_id": c["ref_id"], "nombre": c["nombre"], "pais_id": c.get("pais_id"), "motivo": c["motivo"],
           "severidad": sev, "titular": titular, "juego_id": str(juego["_id"]) if juego else None, "ronda": ronda, "desde_seq": seq, "hasta_seq": seq + CE.DURACION_PARTIDOS,
           "creado_en": datetime.utcnow()}
    try:
        db[COL].insert_one(doc)
    except DuplicateKeyError:
        return 0
    _notas(doc, juego)
    return 1


def _notas(doc: dict, juego: Optional[dict]) -> None:
    """Hasta MAX_NOTAS medios: el deportivo del país de la persona (si lo tiene) y los internacionales. Con `valoraciones`: bajan su reputación y, si es un jugador de tu
    cartera, abren una entrevista."""
    if not juego:
        return
    medios = PS.medios()
    rng = random.Random(f"esc-dep-notas:{doc['_id']}")
    internacionales = [m for m in medios if m.get("pais_id") is None]
    propios = sorted([m for m in medios if m.get("pais_id") is not None and m.get("pais_id") == doc.get("pais_id")], key=lambda m: 0 if m.get("papel") == "deportivo" else 1)[:1]
    candidatos_m = propios + internacionales
    elegidos = candidatos_m[:1] + rng.sample(candidatos_m[1:], min(CE.MAX_NOTAS - 1, max(0, len(candidatos_m) - 1))) if candidatos_m else []
    ahora, notas = datetime.utcnow(), []
    for medio in elegidos[:CE.MAX_NOTAS]:
        m = dict(medio, credibilidad=PS.credibilidad_actual(medio))
        nrng = random.Random(f"esc-dep-nota:{doc['_id']}:{medio['id']}")
        per = nrng.choice(medio["equipo"]["periodistas"])
        r = E.nota_deportiva(doc["severidad"], doc["titular"], doc["nombre"], m, per, medio.get("pais_id") == doc.get("pais_id"), nrng)
        notas.append({"_id": f"{doc['_id']}:{medio['id']}:esc", "juego_id": str(juego["_id"]), "fecha": juego.get("fecha"), "hora": juego.get("hora"), "medio_id": medio["id"],
                      "medio": {"nombre": medio["nombre"], "slug": medio["slug"], "papel": medio["papel"], "linea": medio["linea"], "pais_id": medio.get("pais_id")},
                      "periodista": {"nombre": per["nombre"], "rol": per["rol"], "estilo": per["estilo"], "sesgo": per["sesgo"]},
                      "tipo": "ESCANDALO", **r, "valoraciones": [{"tipo": doc["tipo"], "id": doc["ref_id"], "nombre": doc["nombre"], "valor": r["tono"]}],
                      "peso": P.peso_medio(m), "rol_cobertura": "interesado", "creado_en": ahora})
    if not notas:
        return
    res = db[PS.COL].bulk_write([UpdateOne({"_id": x["_id"]}, {"$setOnInsert": x}, upsert=True) for x in notas], ordered=False)
    ids_nuevos = set(res.upserted_ids.values())
    nuevas = [x for x in notas if x["_id"] in ids_nuevos]
    if nuevas:   # solo lo recién escrito suma a la reputación (repetir la llamada no la infla)
        PS.actualizar_reputacion(nuevas)
        if doc["tipo"] == "arbitro":   # marca cuándo fue su última nota para que su reputación se recupere con el tiempo (polemicas_service)
            from services.polemicas_service import _terminados
            db[PS.COL_REP].update_one({"_id": f"arbitro:{doc['ref_id']}"}, {"$set": {"terminados_ref": _terminados()}})


# --- Lectura de efectos ----------------------------------------------------------------------------------------------------------------
def _datos() -> Dict[str, Any]:
    if _cache["hasta"] < time.time():
        seq = _seq_reloj()
        _cache.update(crisis=list(db[COL].find({"hasta_seq": {"$gt": seq - CE.DURACION_PARTIDOS}})), hasta=time.time() + 15)   # vigentes y recientes (universos atrasados)
    return _cache


def _vigente(tipo: str, ref_id: int, seq: int) -> Optional[dict]:
    mejor = None
    for c in _datos()["crisis"]:
        if c["tipo"] == tipo and c["ref_id"] == ref_id and c["desde_seq"] <= seq < c["hasta_seq"]:
            if mejor is None or c["severidad"] > mejor["severidad"]:
                mejor = c
    return mejor


def efecto_jugador(ref_id: int, seq: int) -> Optional[dict]:
    """{crisis_id, severidad, riesgo_extra, encaje_menos, titular} de la crisis vigente de ese jugador en `seq`, o None."""
    c = _vigente("jugador", ref_id, seq)
    if not c:
        return None
    return {"crisis_id": c["_id"], "severidad": c["severidad"], "riesgo_extra": CE.RIESGO_EXTRA_JUGADOR[c["severidad"]], "encaje_menos": CE.ENCAJE_MENOS_JUGADOR[c["severidad"]],
            "titular": c["titular"], "hasta_seq": c["hasta_seq"]}


def presion_dt(dt_id: Optional[int]) -> float:
    """Presión extra por partido sobre ese DT mientras dure su crisis (0 si no está en crisis)."""
    try:
        c = _vigente("dt", dt_id, _seq_reloj()) if dt_id is not None else None
        return CE.PRESION_DT[c["severidad"]] if c else 0.0
    except Exception:
        return 0.0


def crisis_de(tipo: str, ref_id: int) -> Optional[dict]:
    """La crisis vigente de una persona para las fichas: {titular, severidad, partidos_restantes} o None."""
    try:
        seq = _seq_reloj()
        c = _vigente(tipo, ref_id, seq)
        return {"titular": c["titular"], "severidad": c["severidad"], "partidos_restantes": max(0, c["hasta_seq"] - seq)} if c else None
    except Exception:
        return None


def limpiar() -> None:
    db[COL].delete_many({})
    _invalidar()
