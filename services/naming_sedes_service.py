"""Derechos de nombre de estadios: una marca le ofrece al dueño de una sede ponerle su nombre al estadio.

Colección `sedes_naming` (una por oferta/contrato; `restart_mundial` la borra):
    {ciudad_id, marca_id, user_id (dueño al ofrecer), estado OFERTA|ACTIVO|RECHAZADA|VENCIDA|ROTO|TERMINADO|VENDIDO,
     nombre (el comercial), nombre_original, pago_partido, firma, creada_ronda, vence_ronda, partidos, cobrado, firmado_en}
Colección `sedes_naming_movimientos` (feed de Mi cuenta): {user_id, ciudad_id, monto (+/-), concepto, created_at}

Todo va al saldo (`usuarios.monto`) del dueño. Las ofertas se evalúan cada `PARTIDOS_RONDA` partidos terminados (gancho al
final de `juegos_service.aplicar_efectos_secundarios`, idempotente y sin lanzar). El nombre comercial lo ven TODOS (la sede
tiene un solo dueño global). Los partidos ya jugados conservan el nombre con el que se jugaron.
Castigos suaves (config/naming.py): romper el contrato, vender la sede con el contrato vigente o quedarse sin partidos
cuestan `PENALIZACION_FIRMA` de la firma; nunca más que la firma ni dejan el saldo bajo cero.
"""
import logging
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import certifi
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

from config import naming as N
from config.settings import MONGODB_URI

logger = logging.getLogger(__name__)
client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database("mundial")

COL = "sedes_naming"
MOV = "sedes_naming_movimientos"
ABIERTOS = ("OFERTA", "ACTIVO")
FASE_ALTA = 11            # semifinal, 3er lugar y final (igual que venue_service.FASE_ID_BONO_ALTO)
MULT_FASE_ALTA = 3

_cache: Dict[str, Any] = {"hasta": 0.0, "datos": {}}


# --------------------------------------------------------------------------------------------------------------------
# Lectura (caché corta: hay muy pocos contratos activos y se pregunta por el nombre en muchas vistas)
# --------------------------------------------------------------------------------------------------------------------
def _invalidar() -> None:
    _cache["hasta"] = 0.0


def _activos() -> Dict[int, dict]:
    if _cache["hasta"] < time.time():
        from services.corporativo_marcas_service import catalogo
        from services.imagenes_pais_service import url_logo_marca
        cat = catalogo()
        datos = {}
        for c in db[COL].find({"estado": "ACTIVO"}):
            m = cat.get(c["marca_id"]) or {}
            datos[c["ciudad_id"]] = {"nombre": c["nombre"], "marca": m.get("nombre"), "marca_id": c["marca_id"],
                                     "logo": url_logo_marca(m.get("slug")) if m else None, "color": (m.get("colores") or [None])[0]}
        _cache["datos"] = datos
        _cache["hasta"] = time.time() + 15
    return _cache["datos"]


def nombre_estadio(ciudad_id: Optional[int], original: Optional[str] = None) -> Optional[str]:
    """El nombre comercial del estadio si una marca lo tiene, si no `original`. Barato: úsalo en vistas y plantillas."""
    try:
        d = _activos().get(ciudad_id)
    except Exception:
        d = None
    return d["nombre"] if d else original


def naming_de(ciudad_id: Optional[int]) -> Optional[dict]:
    """{nombre, marca, logo, color} del contrato vigente de esa sede (None si no tiene)."""
    try:
        return _activos().get(ciudad_id)
    except Exception:
        return None


# --------------------------------------------------------------------------------------------------------------------
# Cálculos puros
# --------------------------------------------------------------------------------------------------------------------
def pago_por_partido(nivel: int, fase_id: Optional[int] = None) -> int:
    base = N.REGALIA_BASE * N.FACTOR_PAGO.get(nivel, N.FACTOR_PAGO[1])
    if fase_id is not None and fase_id >= FASE_ALTA:
        base *= MULT_FASE_ALTA
    return round(base)


def firma_de(nivel: int) -> int:
    return pago_por_partido(nivel) * N.FIRMA_EN_PARTIDOS


def penalizacion_de(firma: int) -> int:
    return round(firma * N.PENALIZACION_FIRMA)


def elegible(marca: dict, ciudad: dict, confederacion_id: Optional[int]) -> bool:
    alcance = marca.get("alcance")
    if alcance == "global":
        return True
    if alcance == "continental":
        return marca.get("confederacion_id") is not None and marca.get("confederacion_id") == confederacion_id
    if alcance == "local":
        return marca.get("pais_id") is not None and marca.get("pais_id") == ciudad.get("pais_id")
    return False


def nombre_comercial(marca_nombre: str, ciudad_id: int) -> str:
    formato = random.Random(f"naming:{ciudad_id}:{marca_nombre}").choice(N.FORMATOS_NOMBRE)
    return formato.format(m=marca_nombre)


# --------------------------------------------------------------------------------------------------------------------
# Dinero
# --------------------------------------------------------------------------------------------------------------------
def _abonar(user_id, ciudad_id: int, monto: int, concepto: str) -> None:
    uid = ObjectId(str(user_id))
    db["usuarios"].update_one({"_id": uid}, {"$inc": {"monto": monto}})
    db[MOV].insert_one({"user_id": uid, "ciudad_id": ciudad_id, "monto": monto, "concepto": concepto, "created_at": datetime.now()})


def _cobrar_penalizacion(user_id, ciudad_id: int, monto: int, concepto: str) -> int:
    """Descuenta hasta `monto` sin dejar el saldo bajo cero; devuelve lo que se descontó realmente."""
    if monto <= 0:
        return 0
    uid = ObjectId(str(user_id))
    u = db["usuarios"].find_one({"_id": uid}, {"monto": 1}) or {}
    cobrado = max(0, min(monto, int(u.get("monto") or 0)))
    if cobrado:
        _abonar(uid, ciudad_id, -cobrado, concepto)
    return cobrado


# --------------------------------------------------------------------------------------------------------------------
# Ofertas (cada PARTIDOS_RONDA partidos terminados)
# --------------------------------------------------------------------------------------------------------------------
def _ocupacion_marcas() -> Dict[int, int]:
    ocup: Dict[int, int] = {}
    for c in db[COL].find({"estado": {"$in": list(ABIERTOS)}}, {"marca_id": 1}):
        ocup[c["marca_id"]] = ocup.get(c["marca_id"], 0) + 1
    return ocup


def evaluar_ronda(forzar_ronda: Optional[int] = None) -> dict:
    """Gancho de fin de partido. Si se completó una ronda de `PARTIDOS_RONDA` partidos: vence ofertas viejas, cierra
    contratos de estadios sin partidos por jugar y manda ofertas nuevas. Idempotente por ronda. Nunca lanza."""
    try:
        terminados = db["juegos"].count_documents({"estado": "finalizado"})
        ronda = forzar_ronda if forzar_ronda is not None else terminados // N.PARTIDOS_RONDA
        if ronda <= 0:
            return {"ronda": ronda, "hecho": False}
        try:
            db["sedes_naming_rondas"].insert_one({"_id": ronda})
        except DuplicateKeyError:
            return {"ronda": ronda, "hecho": False}
        return {"ronda": ronda, "hecho": True, **_procesar_ronda(ronda)}
    except Exception as e:
        logger.error(f"Naming de sedes: {e}")
        return {"hecho": False, "error": str(e)}


def _procesar_ronda(ronda: int) -> dict:
    from services.corporativo_marcas_service import catalogo
    from services.venue_service import partidos_programados
    ahora = datetime.now()
    cat = catalogo()
    # 1) las ofertas sin respuesta vencen
    vencidas = db[COL].update_many({"estado": "OFERTA", "vence_ronda": {"$lte": ronda}}, {"$set": {"estado": "VENCIDA", "cerrado_en": ahora}}).modified_count
    # 2) contratos cuyo estadio ya no tiene partidos por jugar: terminan (si no alojó ninguno, la marca reclama parte de la firma)
    ciudades_con_dueno = {c["id"]: c for c in db["ciudades"].find({"owner_user_id": {"$nin": [0, "0", None]}},
                                                                 {"id": 1, "pais_id": 1, "owner_user_id": 1, "estadio": 1})}
    programados = partidos_programados(list(ciudades_con_dueno))
    terminados = 0
    for c in db[COL].find({"estado": "ACTIVO"}):
        if programados.get(c["ciudad_id"], {}).get("n", 0) == 0:
            _terminar(c, sin_partidos=(c.get("partidos", 0) == 0))
            terminados += 1
    # 3) ofertas nuevas
    paises = {p["id"]: p.get("confederacion_id") for p in db["paises"].find({}, {"id": 1, "confederacion_id": 1})}
    ocup = _ocupacion_marcas()
    ocupadas = {c["ciudad_id"] for c in db[COL].find({"estado": {"$in": list(ABIERTOS)}}, {"ciudad_id": 1})}
    ofendidas = {(c["ciudad_id"], c["marca_id"]) for c in db[COL].find({"estado": "ROTO"}, {"ciudad_id": 1, "marca_id": 1})}
    nuevas = 0
    for cid, ciudad in ciudades_con_dueno.items():
        if cid in ocupadas or programados.get(cid, {}).get("n", 0) == 0:
            continue
        rng = random.Random(f"naming-oferta:{cid}:{ronda}")
        if rng.random() > N.PROB_OFERTA_SEDE:
            continue
        conf = paises.get(ciudad.get("pais_id"))
        candidatas = [m for m in cat.values() if elegible(m, ciudad, conf) and (cid, m["id"]) not in ofendidas
                      and ocup.get(m["id"], 0) < N.CUPO_POR_MARCA.get(m.get("nivel", 1), 1)]
        if not candidatas:
            continue
        marca = rng.choices(candidatas, weights=[(m.get("nivel", 1) + 0.5) * (0.5 + m.get("fidelidad", 0.5)) for m in candidatas])[0]
        nivel = marca.get("nivel", 1)
        db[COL].insert_one({
            "ciudad_id": cid, "marca_id": marca["id"], "user_id": ObjectId(str(ciudad["owner_user_id"])), "estado": "OFERTA",
            "nombre": nombre_comercial(marca["nombre"], cid), "nombre_original": ciudad.get("estadio"),
            "pago_partido": pago_por_partido(nivel), "firma": firma_de(nivel), "creada_ronda": ronda,
            "vence_ronda": ronda + N.OFERTA_RONDAS, "partidos": 0, "cobrado": 0, "creada_en": ahora})
        ocup[marca["id"]] = ocup.get(marca["id"], 0) + 1
        nuevas += 1
    _invalidar()
    return {"vencidas": vencidas, "terminados": terminados, "nuevas": nuevas}


def _terminar(c: dict, sin_partidos: bool) -> None:
    estado = db[COL].find_one_and_update({"_id": c["_id"], "estado": "ACTIVO"}, {"$set": {"estado": "TERMINADO", "cerrado_en": datetime.now(), "sin_partidos": sin_partidos}})
    if not estado:
        return
    if sin_partidos:
        _cobrar_penalizacion(c["user_id"], c["ciudad_id"], penalizacion_de(c["firma"]),
                             f"La marca reclama parte de la firma: {c['nombre']} no alojó partidos")
    _invalidar()


# --------------------------------------------------------------------------------------------------------------------
# Acciones del dueño
# --------------------------------------------------------------------------------------------------------------------
def _dueno_de(user_id, ciudad_id: int) -> bool:
    c = db["ciudades"].find_one({"id": ciudad_id}, {"owner_user_id": 1}) or {}
    return str(c.get("owner_user_id")) == str(user_id)


def aceptar(user_id, naming_id: str) -> dict:
    c = db[COL].find_one({"_id": ObjectId(naming_id), "estado": "OFERTA"})
    if not c or str(c["user_id"]) != str(user_id) or not _dueno_de(user_id, c["ciudad_id"]):
        raise ValueError("Esta oferta ya no está disponible")
    if db[COL].find_one({"ciudad_id": c["ciudad_id"], "estado": "ACTIVO"}):
        raise ValueError("Esta sede ya tiene un contrato vigente")
    ok = db[COL].update_one({"_id": c["_id"], "estado": "OFERTA"}, {"$set": {"estado": "ACTIVO", "firmado_en": datetime.now()}})
    if not ok.modified_count:
        raise ValueError("Esta oferta ya no está disponible")
    _abonar(user_id, c["ciudad_id"], c["firma"], f"Firma de derechos de nombre: {c['nombre']}")
    _invalidar()
    try:
        from services import niveles_service
        niveles_service.otorgar_xp(ObjectId(str(user_id)), "SEDE_NAMING", str(c["_id"]))
    except Exception:
        pass
    return {"firma": c["firma"], "nombre": c["nombre"]}


def rechazar(user_id, naming_id: str) -> dict:
    r = db[COL].update_one({"_id": ObjectId(naming_id), "user_id": ObjectId(str(user_id)), "estado": "OFERTA"},
                           {"$set": {"estado": "RECHAZADA", "cerrado_en": datetime.now()}})
    if not r.modified_count:
        raise ValueError("Esta oferta ya no está disponible")
    _invalidar()
    return {"ok": True}


def romper(user_id, naming_id: str) -> dict:
    """El dueño rompe el contrato: paga PENALIZACION_FIRMA de la firma y la marca no vuelve a ofrecerle a esa sede."""
    c = db[COL].find_one_and_update({"_id": ObjectId(naming_id), "user_id": ObjectId(str(user_id)), "estado": "ACTIVO"},
                                    {"$set": {"estado": "ROTO", "cerrado_en": datetime.now()}})
    if not c:
        raise ValueError("Este contrato ya no está vigente")
    pagado = _cobrar_penalizacion(user_id, c["ciudad_id"], penalizacion_de(c["firma"]), f"Indemnización por romper el contrato: {c['nombre']}")
    _invalidar()
    return {"penalizacion": pagado}


def cerrar_por_venta(user_id, ciudad_id: int) -> int:
    """Se llama al vender la sede: el contrato vigente termina y devuelve la penalización (el que vende la paga del reembolso)."""
    c = db[COL].find_one_and_update({"ciudad_id": ciudad_id, "estado": "ACTIVO"}, {"$set": {"estado": "VENDIDO", "cerrado_en": datetime.now()}})
    db[COL].update_many({"ciudad_id": ciudad_id, "estado": "OFERTA"}, {"$set": {"estado": "VENCIDA", "cerrado_en": datetime.now()}})
    _invalidar()
    return penalizacion_de(c["firma"]) if c else 0


def penalizacion_por_venta(ciudad_id: int) -> int:
    c = db[COL].find_one({"ciudad_id": ciudad_id, "estado": "ACTIVO"}, {"firma": 1})
    return penalizacion_de(c["firma"]) if c else 0


# --------------------------------------------------------------------------------------------------------------------
# Cobro por partido alojado (lo llama venue_service.process_match_city_revenue)
# --------------------------------------------------------------------------------------------------------------------
def cobrar_partido(ciudad_id: int, fase_id: Optional[int], match_id: str) -> int:
    try:
        c = db[COL].find_one({"ciudad_id": ciudad_id, "estado": "ACTIVO"})
        if not c or not _dueno_de(c["user_id"], ciudad_id):
            return 0
        from services.corporativo_marcas_service import catalogo
        nivel = (catalogo().get(c["marca_id"]) or {}).get("nivel", 1)
        monto = pago_por_partido(nivel, fase_id)
        if db[MOV].find_one({"ciudad_id": ciudad_id, "match_id": match_id, "monto": {"$gt": 0}, "concepto": {"$regex": "^Derechos de nombre"}}):
            return 0
        db[COL].update_one({"_id": c["_id"]}, {"$inc": {"partidos": 1, "cobrado": monto}})
        try:   # el partido queda con el nombre comercial con el que se jugó (el resumen lo muestra)
            db["juegos"].update_one({"_id": ObjectId(match_id)}, {"$set": {"ubicacion.estadio_comercial": c["nombre"]}})
        except Exception:
            pass
        uid = ObjectId(str(c["user_id"]))
        db["usuarios"].update_one({"_id": uid}, {"$inc": {"monto": monto}})
        db[MOV].insert_one({"user_id": uid, "ciudad_id": ciudad_id, "match_id": match_id, "monto": monto,
                            "concepto": f"Derechos de nombre: {c['nombre']}", "created_at": datetime.now()})
        return monto
    except Exception as e:
        logger.error(f"Naming de sedes (cobro): {e}")
        return 0


# --------------------------------------------------------------------------------------------------------------------
# Vistas
# --------------------------------------------------------------------------------------------------------------------
def vista_usuario(user_id) -> Dict[str, Any]:
    """Ofertas abiertas y contratos vigentes de las sedes del usuario, listos para el portafolio."""
    from services.corporativo_marcas_service import catalogo
    from services.imagenes_pais_service import url_logo_marca
    cat = catalogo()
    uid = ObjectId(str(user_id))
    docs = list(db[COL].find({"user_id": uid, "estado": {"$in": list(ABIERTOS)}}).sort("creada_ronda", -1))
    ciudades = {c["id"]: c for c in db["ciudades"].find({"id": {"$in": [d["ciudad_id"] for d in docs]}}, {"id": 1, "nombre": 1, "estadio": 1})}
    from services.venue_service import partidos_programados
    prog = partidos_programados([d["ciudad_id"] for d in docs]) if docs else {}
    filas = []
    for d in docs:
        m = cat.get(d["marca_id"]) or {}
        filas.append({"id": str(d["_id"]), "estado": d["estado"], "ciudad_id": d["ciudad_id"], "ciudad": (ciudades.get(d["ciudad_id"]) or {}).get("nombre", "?"),
                      "estadio_original": d.get("nombre_original"), "nombre": d["nombre"], "marca": m.get("nombre", "?"), "logo": url_logo_marca(m.get("slug")),
                      "alcance": m.get("alcance"), "lema": m.get("lema"), "pago_partido": d["pago_partido"], "pago_partido_alto": pago_por_partido(m.get("nivel", 1), FASE_ALTA),
                      "firma": d["firma"], "penalizacion": penalizacion_de(d["firma"]), "partidos": d.get("partidos", 0), "cobrado": d.get("cobrado", 0),
                      "programados": prog.get(d["ciudad_id"], {}).get("n", 0)})
    return {"ofertas": [f for f in filas if f["estado"] == "OFERTA"], "contratos": [f for f in filas if f["estado"] == "ACTIVO"],
            "penalizacion_pct": round(N.PENALIZACION_FIRMA * 100)}


def contar_pendientes(user_id) -> int:
    """Ofertas de naming esperando respuesta del usuario (para el indicador del menú)."""
    try:
        return db[COL].count_documents({"user_id": ObjectId(str(user_id)), "estado": "OFERTA"})
    except Exception:
        return 0


def movimientos_usuario(user_id) -> List[dict]:
    return list(db[MOV].find({"user_id": ObjectId(str(user_id))}))
