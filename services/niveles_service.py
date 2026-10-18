"""
Niveles de Socio FIFAV: experiencia (XP) por actividad y recompensas por nivel (reglas en config/niveles.py).

- Cada acción que da XP deja un documento en 'xp_eventos' con índice ÚNICO (user_id, accion, ref): la misma
  acción nunca suma dos veces (otorgar_xp es idempotente) y los topes diarios se cuentan por 'fecha'.
- usuarios.xp se suma con $inc atómico; el nivel se deriva de la XP que devolvió ese $inc, así que dos
  eventos simultáneos no pueden saltarse ni duplicar un nivel. Cada nivel alcanzado crea su documento en
  'recompensas_nivel' (único por usuario+nivel) en estado PENDIENTE, que el usuario reclama en /niveles.
- Todo es PERMANENTE: restart_mundial no toca 'xp_eventos', 'recompensas_nivel' ni los campos de nivel de
  'usuarios'. Las acciones que se repiten por torneo llevan el mundial_id en el 'ref' (ver ref_mundial).
- otorgar_xp/otorgar_logro NUNCA lanzan: los llaman los módulos al final de cada acción (album, quinielas,
  trivia, …) y un fallo de XP no debe romper la compra/jugada que ya se hizo.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import certifi
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from pymongo.mongo_client import MongoClient

from config.niveles import (LOGROS, NIVEL_MAXIMO, NIVELES, REGLAS_XP, XP_LOGRO, datos_nivel, nivel_para_xp,
                            xp_para_nivel)
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')
logger = logging.getLogger(__name__)

ACCION_LOGRO = "LOGRO"
ESTADO_PENDIENTE = "PENDIENTE"
ESTADO_RECLAMADA = "RECLAMADA"
CAMPO_POR_RECOMPENSA = {"PUNTOS": "monto", "SOBRES": "sobres_gratis", "PLATINO": "sobres_platino"}


def _oid(usuario_id) -> ObjectId:
    return usuario_id if isinstance(usuario_id, ObjectId) else ObjectId(str(usuario_id))


def ref_mundial(*partes) -> str:
    """'ref' de una acción que se puede repetir en cada Mundial (página completa, Once Ideal por fase, …)."""
    mundial = db["mundiales"].find_one({"activo": True}, {"_id": 1})
    return ":".join([str(mundial["_id"]) if mundial else "sin-mundial", *[str(p) for p in partes]])


# ==========================================
# Otorgar XP
# ==========================================
def _sumar_xp(usuario_oid: ObjectId, xp: int, fecha: datetime) -> Dict[str, Any]:
    """$inc de XP y, si cruzó umbrales, el nivel nuevo y una recompensa PENDIENTE por cada nivel alcanzado."""
    usuario = db["usuarios"].find_one_and_update({"_id": usuario_oid}, {"$inc": {"xp": xp}},
                                                 projection={"xp": 1}, return_document=ReturnDocument.AFTER)
    if not usuario:
        return {"xp": xp, "nivel": None, "subio": False}
    xp_total = usuario["xp"]
    nivel_antes, nivel_nuevo = nivel_para_xp(xp_total - xp), nivel_para_xp(xp_total)
    creadas = 0
    for nivel in range(nivel_antes + 1, nivel_nuevo + 1):
        recompensas = datos_nivel(nivel)["recompensas"]
        if not recompensas:
            continue
        try:
            db["recompensas_nivel"].insert_one({"user_id": usuario_oid, "nivel": nivel, "recompensas": recompensas,
                                                "estado": ESTADO_PENDIENTE, "desbloqueada_en": fecha, "reclamada_en": None})
            creadas += 1
        except DuplicateKeyError:
            pass
    if nivel_nuevo > nivel_antes or creadas:
        db["usuarios"].update_one({"_id": usuario_oid}, {"$max": {"nivel": nivel_nuevo}, "$inc": {"recompensas_pendientes": creadas}})
    return {"xp": xp, "xp_total": xp_total, "nivel": nivel_nuevo, "subio": nivel_nuevo > nivel_antes}


def otorgar_xp(usuario_id, accion: str, ref, xp: Optional[int] = None, fecha: Optional[datetime] = None,
               retroactivo: bool = False) -> Optional[Dict[str, Any]]:
    """
    Suma la XP de una acción (REGLAS_XP) una sola vez por (usuario, acción, ref), respetando el tope diario.
    Devuelve {xp, xp_total, nivel, subio} o None si no sumó (duplicado, tope alcanzado o error).
    """
    try:
        regla = REGLAS_XP.get(accion)
        if accion != ACCION_LOGRO and not regla:
            raise ValueError(f"Acción de XP desconocida: {accion}")
        puntos = int(xp if xp is not None else (regla or {}).get("xp") or 0)
        if puntos <= 0:
            return None
        usuario_oid = _oid(usuario_id)
        fecha = fecha or datetime.now()
        dia = fecha.date().isoformat()
        tope = (regla or {}).get("tope_diario")
        if tope and db["xp_eventos"].count_documents({"user_id": usuario_oid, "accion": accion, "fecha": dia}) >= tope:
            return None
        try:
            db["xp_eventos"].insert_one({"user_id": usuario_oid, "accion": accion, "ref": str(ref), "xp": puntos,
                                         "fecha": dia, "creado_en": fecha, "retroactivo": retroactivo})
        except DuplicateKeyError:
            return None
        return _sumar_xp(usuario_oid, puntos, fecha)
    except Exception as e:
        logger.error(f"No se pudo otorgar XP ({accion}, {ref}) al usuario {usuario_id}: {e}")
        return None


def otorgar_logro(usuario_id, codigo: str, fecha: Optional[datetime] = None, retroactivo: bool = False) -> Optional[Dict[str, Any]]:
    """Logro único (LOGROS): +XP_LOGRO la primera vez, nunca más."""
    if codigo not in LOGROS:
        logger.error(f"Logro desconocido: {codigo}")
        return None
    return otorgar_xp(usuario_id, ACCION_LOGRO, codigo, xp=XP_LOGRO, fecha=fecha, retroactivo=retroactivo)


# ==========================================
# Recompensas
# ==========================================
def reclamar_recompensa(usuario_id, nivel: int) -> Dict[str, Any]:
    """
    Pasa la recompensa del nivel de PENDIENTE a RECLAMADA (update condicional: un doble clic no cobra dos
    veces) y la acredita: puntos a 'monto', sobres a 'sobres_gratis' / 'sobres_platino'.
    """
    usuario_oid = _oid(usuario_id)
    doc = db["recompensas_nivel"].find_one_and_update(
        {"user_id": usuario_oid, "nivel": int(nivel), "estado": ESTADO_PENDIENTE},
        {"$set": {"estado": ESTADO_RECLAMADA, "reclamada_en": datetime.now()}},
        return_document=ReturnDocument.AFTER)
    if not doc:
        raise ValueError("Esa recompensa no está disponible para reclamar")
    incrementos: Dict[str, int] = {"recompensas_pendientes": -1}
    for r in doc["recompensas"]:
        campo = CAMPO_POR_RECOMPENSA[r["tipo"]]
        incrementos[campo] = incrementos.get(campo, 0) + int(r["cantidad"])
    db["usuarios"].update_one({"_id": usuario_oid}, {"$inc": incrementos})
    return {"nivel": doc["nivel"], "recompensas": doc["recompensas"]}


def marcar_nivel_visto(usuario_id) -> None:
    """El aviso de "¡Subiste de nivel!" de base.html se muestra hasta que el usuario lo cierra."""
    usuario = db["usuarios"].find_one({"_id": _oid(usuario_id)}, {"nivel": 1})
    if usuario:
        db["usuarios"].update_one({"_id": usuario["_id"]}, {"$set": {"nivel_visto": usuario.get("nivel", 1)}})


# ==========================================
# Lectura (navbar y página /niveles)
# ==========================================
def resumen_nivel(usuario: Optional[dict]) -> Optional[Dict[str, Any]]:
    """Datos del navbar a partir del documento del usuario de la sesión (sin consultas extra)."""
    if not usuario:
        return None
    xp = int(usuario.get("xp") or 0)
    nivel = nivel_para_xp(xp)
    base = xp_para_nivel(nivel)
    siguiente = xp_para_nivel(nivel + 1) if nivel < NIVEL_MAXIMO else None
    pct = round((xp - base) / (siguiente - base) * 100) if siguiente else 100
    return {
        "nivel": nivel, "titulo": datos_nivel(nivel)["titulo"], "xp": xp, "xp_base": base, "xp_siguiente": siguiente,
        "pct": max(0, min(100, pct)), "maximo": siguiente is None,
        "pendientes": max(0, int(usuario.get("recompensas_pendientes") or 0)),
        "sin_ver": nivel > int(usuario.get("nivel_visto") or 1),
        "sobres_gratis": int(usuario.get("sobres_gratis") or 0), "sobres_platino": int(usuario.get("sobres_platino") or 0),
    }


def obtener_progreso(usuario_id) -> Dict[str, Any]:
    """Todo lo de la página /niveles: nivel, escalera de recompensas, reglas con el avance de hoy, logros e historial."""
    usuario_oid = _oid(usuario_id)
    usuario = db["usuarios"].find_one({"_id": usuario_oid}, {"xp": 1, "nivel_visto": 1, "recompensas_pendientes": 1,
                                                             "sobres_gratis": 1, "sobres_platino": 1}) or {}
    resumen = resumen_nivel(usuario)

    estado_por_nivel = {r["nivel"]: r for r in db["recompensas_nivel"].find({"user_id": usuario_oid})}
    escalera = []
    for fila in NIVELES:
        r = estado_por_nivel.get(fila["nivel"])
        if r:
            estado = "reclamada" if r["estado"] == ESTADO_RECLAMADA else "pendiente"
        else:
            estado = "alcanzado" if fila["nivel"] <= resumen["nivel"] else "bloqueada"
        escalera.append({**fila, "xp_requerida": xp_para_nivel(fila["nivel"]), "estado": estado,
                         "reclamada_en": (r or {}).get("reclamada_en")})

    hoy = datetime.now().date().isoformat()
    usos_hoy: Dict[str, int] = {}
    xp_hoy = 0
    for ev in db["xp_eventos"].find({"user_id": usuario_oid, "fecha": hoy}, {"accion": 1, "xp": 1}):
        usos_hoy[ev["accion"]] = usos_hoy.get(ev["accion"], 0) + 1
        xp_hoy += ev["xp"]
    reglas = [{"codigo": codigo, **regla, "hoy": usos_hoy.get(codigo, 0)} for codigo, regla in REGLAS_XP.items()]

    logros_obtenidos = {ev["ref"]: ev["creado_en"] for ev in db["xp_eventos"].find(
        {"user_id": usuario_oid, "accion": ACCION_LOGRO}, {"ref": 1, "creado_en": 1})}
    logros = [{"codigo": codigo, **datos, "xp": XP_LOGRO, "obtenido_en": logros_obtenidos.get(codigo)} for codigo, datos in LOGROS.items()]

    historial = []
    for ev in db["xp_eventos"].find({"user_id": usuario_oid}).sort("creado_en", -1).limit(20):
        if ev["accion"] == ACCION_LOGRO:
            titulo, icono = f"Logro: {LOGROS.get(ev['ref'], {}).get('titulo', ev['ref'])}", "bi-award-fill"
        else:
            regla = REGLAS_XP.get(ev["accion"], {})
            titulo, icono = regla.get("titulo", ev["accion"]), regla.get("icono", "bi-star")
        historial.append({"titulo": titulo, "icono": icono, "xp": ev["xp"], "fecha": ev["creado_en"], "retroactivo": ev.get("retroactivo", False)})

    return {**resumen, "xp_hoy": xp_hoy, "escalera": escalera, "reglas": reglas, "logros": logros, "historial": historial,
            "logros_obtenidos": len(logros_obtenidos)}


def listar_recompensas_reclamadas(usuario_id) -> List[dict]:
    """Para el feed de Mi Cuenta (categoría "Nivel")."""
    return list(db["recompensas_nivel"].find({"user_id": _oid(usuario_id), "estado": ESTADO_RECLAMADA}))
