"""Tareas pendientes del usuario para el indicador del menú (GET /cuenta/pendientes, pintado por base.html).

Solo CUENTA lo que ya está guardado (nunca pone al día un universo ni escribe), con una caché corta por usuario: el menú lo
pregunta cada minuto. Cada pendiente trae su sección (`seccion` = el código de config/secciones.py), a qué URL llevar y
cuánto vale en el contador. Si agregas un módulo con decisiones pendientes, súmalo en `_pendientes`.
"""
import logging
import time
from datetime import date
from typing import Dict, List

from bson import ObjectId

from services.auth_service import tiene_permiso

logger = logging.getLogger(__name__)
_cache: Dict[str, dict] = {}
SEGUNDOS_CACHE = 20


def _db():
    from services.rewards_service import db
    return db


def _item(clave: str, seccion: str, titulo: str, cuenta: int, url: str, icono: str) -> dict:
    return {"clave": clave, "seccion": seccion, "titulo": titulo, "cuenta": int(cuenta), "url": url, "icono": icono}


def _pendientes(usuario: dict) -> List[dict]:
    db = _db()
    uid = str(usuario["_id"])
    oid = ObjectId(uid)
    items: List[dict] = []

    # Misiones: el check-in diario sin reclamar
    if tiene_permiso(usuario, "misiones"):
        reg = db["user_daily_rewards"].find_one({"user_id": oid}, {"last_checkin_date": 1}) or {}
        if reg.get("last_checkin_date") != date.today().isoformat():
            items.append(_item("checkin", "misiones", "Check-in diario sin reclamar", 1, "/misiones/", "bi-calendar-check-fill"))

    # Niveles: recompensas de nivel por reclamar y sobres de regalo por abrir
    u = db["usuarios"].find_one({"_id": oid}, {"recompensas_pendientes": 1, "sobres_gratis": 1, "sobres_platino": 1}) or {}
    if tiene_permiso(usuario, "niveles") and int(u.get("recompensas_pendientes") or 0) > 0:
        n = int(u["recompensas_pendientes"])
        items.append(_item("recompensas", "niveles", f"{n} recompensa{'s' if n != 1 else ''} de nivel por reclamar", n, "/niveles/", "bi-trophy-fill"))
    sobres = int(u.get("sobres_gratis") or 0) + int(u.get("sobres_platino") or 0)
    if tiene_permiso(usuario, "album") and sobres > 0:
        items.append(_item("sobres", "album", f"{sobres} sobre{'s' if sobres != 1 else ''} gratis por abrir", sobres, "/album-estampas/sobres", "bi-gift-fill"))

    # Sedes: ofertas de derechos de nombre
    if tiene_permiso(usuario, "sedes"):
        from services.naming_sedes_service import contar_pendientes
        n = contar_pendientes(uid)
        if n:
            items.append(_item("naming", "sedes", f"{n} oferta{'s' if n != 1 else ''} de derechos de nombre", n, "/sedes/portafolio", "bi-megaphone-fill"))

    # Corporativos: lo que espera tu respuesta (ofertas de trabajo, de TV y de marcas, propuestas del mercado y entrevistas)
    if tiene_permiso(usuario, "corporativos"):
        universo = db["corp_universos"].find_one({"_id": uid}, {"cargo": 1, "estado": 1}) or {}
        sigla = (universo.get("cargo") or {}).get("sigla")
        filtro = {"universo_id": uid}
        partes = [("empleo", "Oferta de trabajo|Ofertas de trabajo", db["corp_ofertas_empleo"].count_documents({**filtro, "estado": "PENDIENTE"}), "/corporativo/#cpDecisiones")]
        if sigla and universo.get("estado") == "EN_CARGO":
            from services.corporativo_service import TIPOS_PROPUESTA
            partes += [
                ("tv", "Oferta de televisora|Ofertas de televisora", db["corp_tv_contratos"].count_documents({**filtro, "sigla": sigla, "estado": "OFERTA"}), "/corporativo/televisoras"),
                ("marcas", "Oferta de marca|Ofertas de marca", db["corp_patrocinios"].count_documents({**filtro, "sigla": sigla, "estado": "OFERTA"}), "/corporativo/marcas"),
                ("propuestas", "Propuesta del mercado|Propuestas del mercado", db["corp_ofertas"].count_documents({**filtro, "estado": "PENDIENTE", "tipo": {"$in": list(TIPOS_PROPUESTA)}}), "/corporativo/#cpDecisiones"),
                ("entrevistas", "Entrevista pendiente|Entrevistas pendientes", db["corp_entrevistas"].count_documents({**filtro, "estado": "PENDIENTE"}), "/corporativo/#cpDecisiones"),
            ]
        if sigla and universo.get("estado") == "EN_CARGO":
            from services.escandalos_service import contar_pendientes as crisis_pendientes
            partes.append(("crisis", "Marca en crisis|Marcas en crisis", crisis_pendientes(uid, sigla), "/corporativo/marcas"))
        total = sum(p[2] for p in partes)
        if total:
            detalle = ", ".join(f"{p[2]} {p[1].split('|')[0 if p[2] == 1 else 1].lower()}" for p in partes if p[2])
            items.append(_item("corporativos", "corporativos", f"Corporativo: {detalle}", total, "/corporativo/", "bi-buildings-fill"))
    return items


def obtener(usuario: dict) -> dict:
    """{total, secciones: {codigo: cuenta}, items: [...]}; caché de SEGUNDOS_CACHE por usuario. Nunca lanza."""
    uid = str(usuario["_id"])
    hit = _cache.get(uid)
    if hit and hit["hasta"] > time.time():
        return hit["datos"]
    try:
        items = _pendientes(usuario)
    except Exception as e:
        logger.error(f"Pendientes del usuario: {e}")
        items = []
    secciones: Dict[str, int] = {}
    for i in items:
        secciones[i["seccion"]] = secciones.get(i["seccion"], 0) + i["cuenta"]
    datos = {"total": sum(i["cuenta"] for i in items), "secciones": secciones, "items": items}
    _cache[uid] = {"hasta": time.time() + SEGUNDOS_CACHE, "datos": datos}
    return datos


def invalidar(usuario_id) -> None:
    _cache.pop(str(usuario_id), None)
