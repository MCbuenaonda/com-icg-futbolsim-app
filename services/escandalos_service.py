"""Escándalos y gestión de crisis de las marcas: servicio con Mongo (lógica y textos en services/escandalos.py, reglas en config/escandalos.py).

Colección `escandalos` (contenido GLOBAL; `restart_mundial` la borra): {_id "<ronda>:<marca_id>", marca_id, severidad, titular, ronda, desde_seq, hasta_seq}.
El reloj es el de corporativos (`seq`, partidos registrados): la crisis rige entre `desde_seq` y `hasta_seq` para cualquier universo, vaya al día o atrasado.
Las notas de los medios son notas de `prensa` con tipo "ESCANDALO" ancladas al partido que cerró la ronda (sin valoraciones: no tocan la reputación).
Gancho: `evaluar_ronda(juego)` al final de aplicar_efectos_secundarios (cada PARTIDOS_RONDA partidos terminados; idempotente por ronda, nunca lanza).

Efectos (los aplica corporativo_marcas_service): `efecto_para(marca_id, seq)` -> rebaja del pago y riesgo extra de sus patrocinios (la mitad para las marcas
aliadas, según `relaciones`); `bonus_encaje(marca_id, seq)` -> encaje extra de las marcas rivales. El CEO responde con `responder_crisis` (respaldar | distancia).
"""
import logging
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import UpdateOne
from pymongo.errors import DuplicateKeyError

from config import escandalos as CE
from services import escandalos as E
from services import prensa as P
from services import prensa_service as PS

logger = logging.getLogger(__name__)
db = PS.db
COL = "escandalos"
RONDAS = "escandalos_rondas"
_cache: Dict[str, Any] = {"hasta": 0.0, "crisis": [], "rel": {}}


def _invalidar() -> None:
    _cache["hasta"] = 0.0


# --- Generación ---------------------------------------------------------------------------------------------------------
def _seq_reloj() -> int:
    from services.corporativo_universo_service import seq_actual
    return seq_actual()


def evaluar_ronda(juego: Optional[dict] = None, forzar_ronda: Optional[int] = None) -> dict:
    try:
        terminados = db["juegos"].count_documents({"estado": "finalizado"})
        ronda = forzar_ronda if forzar_ronda is not None else terminados // CE.PARTIDOS_RONDA
        if ronda <= 0:
            return {"hecho": False}
        try:
            db[RONDAS].insert_one({"_id": ronda})
        except DuplicateKeyError:
            return {"hecho": False}
        return {"hecho": True, "ronda": ronda, "nuevos": _generar(ronda, juego)}
    except Exception as e:
        logger.error(f"Escándalos: {e}")
        return {"hecho": False, "error": str(e)}


def _generar(ronda: int, juego: Optional[dict]) -> int:
    from services.corporativo_marcas_service import catalogo
    rng = random.Random(f"escandalos:{ronda}")
    seq = _seq_reloj()
    marcas = list(catalogo().values())
    activos_por_marca = {d["_id"]: d["n"] for d in db["corp_patrocinios"].aggregate([{"$match": {"estado": "ACTIVO"}}, {"$group": {"_id": "$marca_id", "n": {"$sum": 1}}}])}
    en_crisis = {c["marca_id"] for c in db[COL].find({"hasta_seq": {"$gt": seq}}, {"marca_id": 1})}
    nuevos = 0
    for _ in range(CE.MAX_POR_RONDA):
        if rng.random() > CE.PROB_POR_ESCANDALO:
            continue
        pesos = E.pesos_marcas(marcas, activos_por_marca, en_crisis)
        if sum(pesos) <= 0:
            break
        marca = rng.choices(marcas, weights=pesos)[0]
        en_crisis.add(marca["id"])
        sev = E.elegir_severidad(rng)
        tit = E.titular(sev, marca, random.Random(f"esc-titular:{ronda}:{marca['id']}"))
        doc = {"_id": f"{ronda}:{marca['id']}", "marca_id": marca["id"], "severidad": sev, "titular": tit, "ronda": ronda, "desde_seq": seq, "hasta_seq": seq + CE.DURACION_PARTIDOS,
               "creado_en": datetime.utcnow()}
        try:
            db[COL].insert_one(doc)
        except DuplicateKeyError:
            continue
        nuevos += 1
        _notas(doc, marca, juego)
    _invalidar()
    return nuevos


def _notas(doc: dict, marca: dict, juego: Optional[dict]) -> None:
    """2-3 medios publican sobre la crisis: internacionales y, si la marca es local, el medio deportivo de su país."""
    if not juego:
        return
    medios = PS.medios()
    rng = random.Random(f"esc-notas:{doc['_id']}")
    candidatos = [m for m in medios if m.get("pais_id") is None]
    if marca.get("alcance") == "local" and marca.get("pais_id") is not None:
        propios = [m for m in medios if m.get("pais_id") == marca["pais_id"]]
        candidatos = sorted(propios, key=lambda m: 0 if m.get("papel") == "deportivo" else 1)[:1] + candidatos
    elegidos = candidatos[:1] + rng.sample(candidatos[1:], min(CE.MAX_NOTAS - 1, max(0, len(candidatos) - 1))) if candidatos else []
    ahora, notas = datetime.utcnow(), []
    for medio in elegidos[:CE.MAX_NOTAS]:
        m = dict(medio, credibilidad=PS.credibilidad_actual(medio))
        nrng = random.Random(f"esc-nota:{doc['_id']}:{medio['id']}")
        per = nrng.choice(medio["equipo"]["periodistas"])
        r = E.nota(doc["severidad"], marca, m, per, nrng)
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
        crisis = list(db[COL].find({"hasta_seq": {"$gt": seq - CE.DURACION_PARTIDOS}}))   # las vigentes y las recientes (universos atrasados)
        rel: Dict[int, Dict[str, set]] = {}
        for d in db["relaciones"].find({"tipo": "marca"}, {"a": 1, "b": 1, "clase": 1}):
            clave = "rivales" if d["clase"] == "rivalidad" else "aliados"
            rel.setdefault(d["a"], {"rivales": set(), "aliados": set()})[clave].add(d["b"])
            rel.setdefault(d["b"], {"rivales": set(), "aliados": set()})[clave].add(d["a"])
        _cache.update(crisis=crisis, rel=rel, hasta=time.time() + 15)
    return _cache


def efecto_para(marca_id: int, seq: int) -> Optional[dict]:
    """Efecto de las crisis vigentes en `seq` sobre los patrocinios de esa marca (la más fuerte): {crisis_id, severidad, rebaja, riesgo_extra, propia, titular}."""
    d = _datos()
    mejor = None
    for c in d["crisis"]:
        if not (c["desde_seq"] <= seq < c["hasta_seq"]):
            continue
        propia = c["marca_id"] == marca_id
        if not propia and marca_id not in d["rel"].get(c["marca_id"], {}).get("aliados", ()):
            continue
        e = E.efecto(c["severidad"], contagio=not propia)
        if mejor is None or e["rebaja"] > mejor["rebaja"]:
            mejor = {"crisis_id": c["_id"], "severidad": c["severidad"], "propia": propia, "titular": c["titular"], "marca_en_crisis": c["marca_id"], "hasta_seq": c["hasta_seq"], **e}
    return mejor


def bonus_encaje(marca_id: int, seq: int) -> int:
    """Encaje extra de una marca por las crisis vigentes de sus rivales (la suma, con tope razonable)."""
    d = _datos()
    total = 0
    for c in d["crisis"]:
        if c["desde_seq"] <= seq < c["hasta_seq"] and marca_id in d["rel"].get(c["marca_id"], {}).get("rivales", ()):
            total += CE.ENCAJE_RIVAL[c["severidad"]]
    return min(total, 15)


# --- Decisiones del CEO ---------------------------------------------------------------------------------------------------------
def _afectados(user_id, sigla: str, seq: int) -> List[dict]:
    from services.corporativo_marcas_service import catalogo, _nombre
    cat = catalogo()
    out = []
    for p in db["corp_patrocinios"].find({"universo_id": user_id, "sigla": sigla, "estado": "ACTIVO"}):
        e = efecto_para(p["marca_id"], seq)
        if not e:
            continue
        m = cat.get(p["marca_id"]) or {}
        respaldado = p.get("crisis_respaldo") == e["crisis_id"]
        out.append({"id": str(p["_id"]), "marca": m.get("nombre", "?"), "nombre": _nombre(p["tipo"], p["ref_id"]), "severidad": e["severidad"], "propia": e["propia"],
                    "marca_en_crisis": (cat.get(e["marca_en_crisis"]) or {}).get("nombre", "?"), "titular": e["titular"], "respaldado": respaldado,
                    "rebaja_pct": round(100 * e["rebaja"] * (CE.RESPALDO_RESIDUO if respaldado else 1.0)),
                    "costo_respaldo": int(round(p.get("pago_ciclo", 0) * CE.RESPALDO_CICLOS)), "partidos_restantes": max(0, e["hasta_seq"] - seq), "pago_ciclo": p.get("pago_ciclo", 0)})
    return out


def vista_usuario(user_id, sigla: Optional[str], seq: int) -> List[dict]:
    return _afectados(user_id, sigla, seq) if sigla else []


def contar_pendientes(user_id, sigla: Optional[str]) -> int:
    """Patrocinios tuyos afectados por una crisis y sin respaldar (para el indicador del menú). Nunca lanza."""
    try:
        from services.corporativo_universo_service import obtener_universo
        if not sigla:
            return 0
        seq = (obtener_universo(user_id) or {}).get("cursor_seq") or _seq_reloj()
        return sum(1 for a in _afectados(user_id, sigla, seq) if not a["respaldado"])
    except Exception:
        return 0


def responder_crisis(user_id, pat_id: str, accion: str) -> dict:
    from services import corporativo_universo_service as U
    if accion not in ("respaldar", "distancia"):
        raise ValueError("Acción desconocida")
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo = U.obtener_universo(user_id) or {}
        sigla = (universo.get("cargo") or {}).get("sigla")
        seq = universo.get("cursor_seq") or _seq_reloj()
        p = db["corp_patrocinios"].find_one({"_id": pat_id, "universo_id": user_id, "sigla": sigla, "estado": "ACTIVO"}) if sigla else None
        if not p:
            raise ValueError("Ese patrocinio ya no está activo")
        e = efecto_para(p["marca_id"], seq)
        if not e:
            raise ValueError("Esa marca ya no está en crisis")
        from services.corporativo_marcas_service import catalogo, _nombre
        marca = catalogo().get(p["marca_id"]) or {}
        nombre = _nombre(p["tipo"], p["ref_id"])
        ciclo = U.ciclo_en_curso(universo)
        if accion == "distancia":
            db["corp_patrocinios"].update_one({"_id": pat_id}, {"$set": {"estado": "TERMINADO", "motivo": "Tomaste distancia por la crisis de la marca", "fin_ciclo": ciclo, "fin_seq": seq}})
            return {"ok": True, "mensaje": f"Tomaste distancia de {marca.get('nombre')}: terminó el patrocinio de {nombre} sin castigo y quedó libre el cupo."}
        if p.get("crisis_respaldo") == e["crisis_id"]:
            raise ValueError("Ya respaldaste a esta marca en esta crisis")
        costo = int(round(p.get("pago_ciclo", 0) * CE.RESPALDO_CICLOS))
        corp = db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": sigla}, {"capital": 1}) or {}
        if int(corp.get("capital") or 0) < costo:
            raise ValueError(f"No te alcanza el capital para la campaña de apoyo ({costo:,})")
        db["corp_corporativos"].update_one({"universo_id": user_id, "sigla": sigla}, {"$inc": {"capital": -costo, "ciclo_actual.gastos_extra": costo}})
        db["corp_movimientos"].insert_one({"universo_id": user_id, "sigla": sigla, "ciclo": ciclo, "tipo": "CRISIS_MARCA", "monto": -costo,
                                           "detalle": f"Campaña de apoyo a {marca.get('nombre')} en su crisis", "creado_en": datetime.utcnow()})
        db["corp_patrocinios"].update_one({"_id": pat_id}, {"$set": {"crisis_respaldo": e["crisis_id"]}})
        return {"ok": True, "mensaje": f"Respaldaste a {marca.get('nombre')} (campaña de apoyo: {costo:,}). Se quita el riesgo extra y la rebaja baja a la mitad."}


def limpiar() -> None:
    db[COL].delete_many({})
    db[RONDAS].delete_many({})
    _invalidar()
