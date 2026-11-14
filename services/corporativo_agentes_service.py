"""Agentes de tus representados (reglas en config/agentes.py, lógica pura en services/agentes.py).

Catálogo permanente `agentes` (100 ficticios, generar_agentes.py) y contratos POR UNIVERSO en `corp_agentes`:
    {_id: "<universo>:<contrato>:<ciclo>", universo_id, sigla, contrato_id, tipo, ref_id, agente_id, comision, sinergia_album,
     confederacion_id (del representado), desde_ciclo, hasta_ciclo, estado ACTIVO|TERMINADO|CANCELADO, motivo, bono_total, comision_total}
Solo trabajan para el corporativo del USUARIO (la IA no usa agentes en esta versión).
Efectos sobre las marcas (corporativo_marcas_service): bono sobre la firma y el pago por ciclo, comisión del agente (capital y
`gastos_extra`, movimiento AGENTE_COMISION), encaje extra al buscar candidatos y riesgo de corte del patrocinio.
"""
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId

from config import agentes as CA
from config import corporativos as C
from services import agentes as A
from services import corporativo_universo_service as U
from services.corporativo_mercado_service import valores

logger = logging.getLogger(__name__)
db = U.db
COL = "corp_agentes"
_cache = {"datos": None, "hasta": 0.0}


def catalogo() -> Dict[int, dict]:
    ahora = time.time()
    if _cache["datos"] is None or ahora > _cache["hasta"]:
        _cache["datos"] = {a["id"]: a for a in db["agentes"].find({}, {"_id": 0})}
        _cache["hasta"] = ahora + 300
    return _cache["datos"]


def _nombre(tipo: str, ref_id: int) -> str:
    v = valores()
    return (v["info_paises"] if tipo == "seleccion" else v["info_jugadores"]).get(ref_id, {}).get("nombre", "?")


def confederacion_de(tipo: str, ref_id: int) -> Optional[int]:
    v = valores()
    pais = ref_id if tipo == "seleccion" else v["info_jugadores"].get(ref_id, {}).get("pais_id")
    return v["info_paises"].get(pais, {}).get("confederacion_id")


def _efectos_pacto(p: dict) -> Optional[dict]:
    ag = catalogo().get(p["agente_id"])
    return A.efectos(ag, p.get("confederacion_id"), p["comision"]) if ag else None


# --- Enganches con el ciclo (corporativo_ciclo_service.Estado / corporativo_marcas_service) --------------------------
def cargar(estado) -> None:
    """Deja en cada contrato del usuario con agente `_agente` = {pacto_id, efectos}. No se guarda (no está en CAMPOS_CONTRATO)."""
    estado.agentes = {}
    pactos = list(db[COL].find({"universo_id": estado.uid, "estado": "ACTIVO"}))
    if not pactos:
        return
    por_contrato = {str(c["_id"]): c for c in estado.contratos}
    for p in pactos:
        c = por_contrato.get(p["contrato_id"])
        ef = _efectos_pacto(p)
        if c and ef:
            c["_agente"] = {"pacto_id": p["_id"], "ef": ef}
            estado.agentes[p["_id"]] = {**p, "_bono": 0, "_comision": 0}


def ajustar(estado, corp: dict, c: dict, monto: int, ciclo: int, concepto: str) -> int:
    """Bono del agente sobre un cobro de marcas y su comisión (a cargo del capital). Devuelve el monto ya con el bono."""
    info = c.get("_agente")
    if not info or not corp.get("es_del_usuario"):
        return monto
    con_bono, com = A.aplicar_pago(monto, info["ef"])
    corp["capital"] -= com
    corp["ciclo_actual"]["gastos_extra"] = corp["ciclo_actual"].get("gastos_extra", 0) + com
    estado.mover(corp["sigla"], ciclo, "AGENTE_COMISION", -com, f"Comisión de tu agente por {concepto}")
    acum = estado.agentes.get(info["pacto_id"])
    if acum is not None:
        acum["_bono"] += con_bono - monto
        acum["_comision"] += com
    return con_bono


def encaje_extra(c: dict) -> int:
    info = c.get("_agente")
    return int(info["ef"]["encaje"]) if info else 0


def riesgo_extra(c: dict) -> int:
    info = c.get("_agente")
    return int(info["ef"]["riesgo"]) if info else 0


def ajustar_directo(user_id, contrato_id: str, sigla: str, monto: int, ciclo: int, concepto: str) -> int:
    """Lo mismo que `ajustar` para una acción del usuario fuera de poner_al_dia (aceptar una oferta): escribe directo."""
    p = db[COL].find_one({"universo_id": user_id, "contrato_id": str(contrato_id), "estado": "ACTIVO"})
    ef = _efectos_pacto(p) if p else None
    if not ef:
        return monto
    con_bono, com = A.aplicar_pago(monto, ef)
    db["corp_corporativos"].update_one({"universo_id": user_id, "sigla": sigla}, {"$inc": {"capital": -com, "ciclo_actual.gastos_extra": com}})
    db["corp_movimientos"].insert_one({"universo_id": user_id, "sigla": sigla, "ciclo": ciclo, "tipo": "AGENTE_COMISION", "monto": -com,
                                       "detalle": f"Comisión de tu agente por {concepto}", "creado_en": datetime.utcnow()})
    db[COL].update_one({"_id": p["_id"]}, {"$inc": {"bono_total": con_bono - monto, "comision_total": com}})
    return con_bono


def cerrar_ciclo(estado, ciclo: int) -> None:
    """Guarda lo acumulado y termina los contratos vencidos o de representados que ya no están en la cartera."""
    for pid, p in list(getattr(estado, "agentes", {}).items()):
        total_com = int(p.get("comision_total", 0) + p["_comision"])
        cambios = {"$inc": {"bono_total": p["_bono"], "comision_total": p["_comision"]}} if (p["_bono"] or p["_comision"]) else {}
        p["_bono"] = p["_comision"] = 0
        c = next((x for x in estado.contratos if str(x["_id"]) == p["contrato_id"] and x["activo"]), None)
        motivo = None
        if not c:
            motivo = "Ya no representas a ese jugador o selección"
        elif ciclo >= p["hasta_ciclo"]:
            motivo = "Venció el contrato"
        if motivo:
            cambios.setdefault("$set", {}).update(estado="TERMINADO", motivo=motivo, fin_ciclo=ciclo)
            if c:
                c.pop("_agente", None)
            estado.agentes.pop(pid, None)
            ag = catalogo().get(p["agente_id"], {})
            U.avisar(estado.uid, ciclo, "AGENTE", f"Terminó tu contrato con {ag.get('nombre', 'tu agente')}",
                     f"{motivo}. Pagó de comisión {total_com:,} en total; si quieres seguir con él o con otro, "
                     "contrátalo de nuevo en Agentes.", "bi-briefcase-fill", clave=f"agente-fin:{pid}")
        if cambios:
            db[COL].update_one({"_id": pid}, cambios)


# --- Acciones del usuario -----------------------------------------------------------------------------------
def _universo_en_cargo(user_id) -> dict:
    universo = U.obtener_universo(user_id)
    if not universo or universo.get("estado") != "EN_CARGO" or not universo.get("cargo"):
        raise ValueError("Necesitas dirigir un corporativo para contratar agentes")
    return universo


def _contrato_libre(user_id, universo: dict, contrato_id: str) -> dict:
    try:
        c = db["corp_contratos"].find_one({"_id": ObjectId(contrato_id), "universo_id": user_id, "activo": True, "sigla": universo["cargo"]["sigla"]})
    except Exception:
        c = None
    if not c:
        raise ValueError("Ese representado no está en tu cartera")
    return c


def _tiene_estampa(user_id, agente_id: int) -> bool:
    try:
        return bool(db["user_albums"].find_one({"user_id": ObjectId(str(user_id)), "owned_duenos": CA.ID_ESTAMPA_BASE + agente_id}, {"_id": 1}))
    except Exception:
        return False


def cotizar(user_id, agente_id: int, contrato_id: str) -> dict:
    universo = _universo_en_cargo(user_id)
    ag = catalogo().get(agente_id)
    if not ag:
        raise ValueError("Ese agente no existe")
    c = _contrato_libre(user_id, universo, contrato_id)
    comision = A.comision_con_sinergia(ag["comision"], _tiene_estampa(user_id, agente_id))
    ef = A.efectos(ag, confederacion_de(c["tipo"], c["ref_id"]), comision)
    return {"agente": ag["nombre"], "representado": _nombre(c["tipo"], c["ref_id"]), "bono_pago": ef["bono_pago"], "comision": ef["comision"],
            "encaje": ef["encaje"], "riesgo": ef["riesgo"], "conoce_region": ef["conoce_region"], "neto": A.neto(ef),
            "sinergia_album": comision < ag["comision"]}


def contratar(user_id, agente_id: int, contrato_id: str) -> dict:
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo = _universo_en_cargo(user_id)
        ag = catalogo().get(agente_id)
        if not ag:
            raise ValueError("Ese agente no existe")
        c = _contrato_libre(user_id, universo, contrato_id)
        activos = list(db[COL].find({"universo_id": user_id, "estado": "ACTIVO"}, {"agente_id": 1, "contrato_id": 1}))
        if any(p["contrato_id"] == str(c["_id"]) for p in activos):
            raise ValueError("Ese representado ya tiene agente")
        if len(activos) >= CA.MAX_AGENTES_USUARIO:
            raise ValueError(f"Puedes tener hasta {CA.MAX_AGENTES_USUARIO} agentes a la vez")
        if sum(1 for p in activos if p["agente_id"] == agente_id) >= ag.get("cupo", CA.CUPO_POR_AGENTE):
            raise ValueError(f"{ag['nombre']} ya lleva a todos los representados que puede atender")
        ciclo = U.ciclo_en_curso(universo)
        sinergia = _tiene_estampa(user_id, agente_id)
        comision = A.comision_con_sinergia(ag["comision"], sinergia)
        pid = f"{user_id}:{c['_id']}:{ciclo}"
        db[COL].update_one({"_id": pid}, {"$set": {
            "universo_id": user_id, "sigla": c["sigla"], "contrato_id": str(c["_id"]), "tipo": c["tipo"], "ref_id": c["ref_id"], "agente_id": agente_id,
            "comision": comision, "sinergia_album": sinergia, "confederacion_id": confederacion_de(c["tipo"], c["ref_id"]),
            "desde_ciclo": ciclo, "hasta_ciclo": ciclo + CA.CICLOS_CONTRATO - 1, "estado": "ACTIVO", "motivo": None, "bono_total": 0,
            "comision_total": 0, "creado_en": datetime.utcnow()}}, upsert=True)
        nombre = _nombre(c["tipo"], c["ref_id"])
    U.dar_xp(user_id, "CORP_AGENTE", pid)
    return {"ok": True, "mensaje": f"{ag['nombre']} ahora representa los intereses de {nombre} ({CA.CICLOS_CONTRATO} ciclos, comisión {comision:.1%})."
                                   + (" Tu estampa del álbum le bajó la comisión." if sinergia else "")}


def _pago_ciclo_patrocinios(user_id, contrato_id: str) -> int:
    return sum(int(p.get("pago_ciclo", 0)) for p in db["corp_patrocinios"].find({"universo_id": user_id, "contrato_id": contrato_id, "estado": "ACTIVO"}, {"pago_ciclo": 1}))


def _penalizacion(user_id, p: dict) -> int:
    return int(round(_pago_ciclo_patrocinios(user_id, p["contrato_id"]) * (1 + (_efectos_pacto(p) or {"bono_pago": 0})["bono_pago"]) * p["comision"] * CA.PENALIZACION_CANCELAR))


def cancelar(user_id, pacto_id: str) -> dict:
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo = _universo_en_cargo(user_id)
        p = db[COL].find_one({"_id": pacto_id, "universo_id": user_id, "estado": "ACTIVO"})
        if not p:
            raise ValueError("Ese contrato ya no está vigente")
        ciclo = U.ciclo_en_curso(universo)
        costo = _penalizacion(user_id, p)
        if costo:
            corp = db["corp_corporativos"].find_one_and_update({"universo_id": user_id, "sigla": p["sigla"], "capital": {"$gte": costo}},
                                                               {"$inc": {"capital": -costo, "ciclo_actual.gastos_extra": costo}})
            if not corp:
                raise ValueError(f"No te alcanza el capital para cancelar ({costo:,})")
            db["corp_movimientos"].insert_one({"universo_id": user_id, "sigla": p["sigla"], "ciclo": ciclo, "tipo": "AGENTE_COMISION", "monto": -costo,
                                               "detalle": "Cancelar el contrato con tu agente antes de tiempo", "creado_en": datetime.utcnow()})
        db[COL].update_one({"_id": pacto_id}, {"$set": {"estado": "CANCELADO", "motivo": "Lo cancelaste", "fin_ciclo": ciclo}, "$inc": {"comision_total": costo}})
        ag = catalogo().get(p["agente_id"], {})
    return {"ok": True, "mensaje": f"Cancelaste a {ag.get('nombre', 'tu agente')}." + (f" Pagaste {costo:,} por romper antes de tiempo." if costo else "")}


# --- Vista -----------------------------------------------------------------------------------------------------
def _agente_vista(a: dict, ocupados: Dict[int, int]) -> dict:
    from services.imagenes_pais_service import url_imagen_medios
    r = CA.RASGOS[a["rasgo"]]
    v = valores()
    pais = v["info_paises"].get(a["pais_id"], {})
    return {"id": a["id"], "nombre": a["nombre"], "edad": a.get("edad"), "pais_id": a["pais_id"], "pais_nombre": a.get("pais_nombre") or pais.get("nombre"),
            "bandera": pais.get("bandera"), "confederacion_id": a["confederacion_id"], "rasgo": a["rasgo"], "rasgo_nombre": r["nombre"], "rasgo_icono": r["icono"],
            "rasgo_texto": r["texto"], "calidad": int(round(a["calidad"] * 100)), "comision": a["comision"], "comision_texto": f"{a['comision']:.1%}",
            "avatar": url_imagen_medios(a.get("avatar")), "cupo": a.get("cupo", CA.CUPO_POR_AGENTE), "ocupados": ocupados.get(a["id"], 0),
            "tiene_estampa_id": CA.ID_ESTAMPA_BASE + a["id"]}


def vista_agentes(user_id) -> Optional[dict]:
    universo = U.obtener_universo(user_id)
    if not universo:
        return None
    U.poner_al_dia(user_id)
    universo = U.obtener_universo(user_id)
    en_cargo = universo.get("estado") == "EN_CARGO" and bool(universo.get("cargo"))
    sigla = (universo.get("cargo") or {}).get("sigla")
    ciclo = U.ciclo_en_curso(universo)
    pactos = list(db[COL].find({"universo_id": user_id, "estado": "ACTIVO"}))
    ocupados: Dict[int, int] = {}
    for p in pactos:
        ocupados[p["agente_id"]] = ocupados.get(p["agente_id"], 0) + 1
    cat = catalogo()
    agentes = [_agente_vista(a, ocupados) for a in sorted(cat.values(), key=lambda x: x["id"])]
    por_id = {a["id"]: a for a in agentes}
    estampas: set = set()
    try:
        album = db["user_albums"].find_one({"user_id": ObjectId(str(user_id))}, {"owned_duenos": 1}) or {}
        estampas = set(album.get("owned_duenos") or [])
    except Exception:
        pass
    for a in agentes:
        a["con_estampa"] = a["tiene_estampa_id"] in estampas
    mis = []
    for p in sorted(pactos, key=lambda x: x["desde_ciclo"]):
        ef = _efectos_pacto(p)
        if not ef or p["agente_id"] not in por_id:
            continue
        mis.append({"id": p["_id"], "agente": por_id[p["agente_id"]], "representado": _nombre(p["tipo"], p["ref_id"]), "tipo": p["tipo"], "ref_id": p["ref_id"],
                    "ciclos_restantes": max(0, p["hasta_ciclo"] - ciclo + 1), "hasta_ciclo": p["hasta_ciclo"], "comision": p["comision"],
                    "bono_pago": ef["bono_pago"], "encaje": ef["encaje"], "riesgo": ef["riesgo"], "conoce_region": ef["conoce_region"], "neto": A.neto(ef),
                    "bono_total": int(p.get("bono_total", 0)), "comision_total": int(p.get("comision_total", 0)), "penalizacion": _penalizacion(user_id, p),
                    "sinergia_album": p.get("sinergia_album", False)})
    ocupados_contratos = {p["contrato_id"] for p in pactos}
    libres = []
    if en_cargo:
        for c in db["corp_contratos"].find({"universo_id": user_id, "activo": True, "sigla": sigla}):
            if str(c["_id"]) not in ocupados_contratos:
                libres.append({"contrato_id": str(c["_id"]), "nombre": _nombre(c["tipo"], c["ref_id"]), "tipo": c["tipo"],
                               "confederacion_id": confederacion_de(c["tipo"], c["ref_id"])})
        libres.sort(key=lambda x: (x["tipo"], x["nombre"]))
    from config.marcas import CONFEDERACIONES
    return {"universo": universo, "en_cargo": en_cargo, "sigla": sigla, "ciclo": ciclo, "agentes": agentes, "mis_contratos": mis, "libres": libres,
            "max_agentes": CA.MAX_AGENTES_USUARIO, "ciclos_contrato": CA.CICLOS_CONTRATO, "rasgos": [{"codigo": k, "nombre": v["nombre"], "icono": v["icono"], "texto": v["texto"]} for k, v in CA.RASGOS.items()],
            "confederaciones": CONFEDERACIONES, "penalizacion_pct": int(CA.PENALIZACION_CANCELAR * 100)}
