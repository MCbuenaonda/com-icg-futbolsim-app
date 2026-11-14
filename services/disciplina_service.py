"""Disciplina: suspensiones por tarjetas (services/disciplina.py lógica pura; reglas en config/disciplina.py).

`jugadores.suspension` = {juego_id, codigo, motivo, partidos, restantes, minuto, rival, fecha, cumplidos[]} (como `jugadores.lesion`) y
`jugadores.disciplina` = {amarillas, fase, ultimo_juego} (contador POR TORNEO; `crear_nuevo_mundial` lo limpia). El motor no alinea ni
pone en el banco a nadie con `suspension.restantes` > 0 (simular_service._de_baja). Historial PERMANENTE en `sanciones_historial`.

`registrar_partido(juego)` es el gancho al final de juegos_service.aplicar_efectos_secundarios (diferido en vivo, idempotente por juego,
nunca lanza): 1) los suspendidos de las dos selecciones cumplen un partido; 2) se anotan las tarjetas de este partido y las sanciones nuevas.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import certifi
from pymongo import MongoClient

from config.settings import MONGODB_URI
from services import disciplina as DI

logger = logging.getLogger(__name__)
client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database("mundial")


def registrar_partido(juego: Optional[Dict[str, Any]]) -> None:
    try:
        if not juego or not juego.get("resultado"):
            return
        juego_id = str(juego["_id"])
        res = juego["resultado"]
        local, visita = juego.get("equipo_local") or {}, juego.get("equipo_visitante") or {}
        paises = [p for p in (local.get("id"), visita.get("id")) if p is not None]
        fase_id = juego.get("fase_id")

        # 1) Cumplen un partido de suspensión (los sancionados en este mismo partido no)
        if paises:
            db["jugadores"].update_many(
                {"pais_id": {"$in": paises}, "suspension.restantes": {"$gt": 0}, "suspension.juego_id": {"$ne": juego_id},
                 "suspension.cumplidos": {"$ne": juego_id}},
                {"$inc": {"suspension.restantes": -1}, "$push": {"suspension.cumplidos": juego_id}})

        # 2) Tarjetas de este partido -> contador y sanciones nuevas
        tarjetas = DI.tarjetas_del_partido(res.get("eventos") or [])
        if not tarjetas:
            return
        pais_de = {local.get("nombre"): local.get("id"), visita.get("nombre"): visita.get("id")}
        rival_de = {local.get("id"): visita.get("nombre"), visita.get("id"): local.get("nombre")}
        nombres = [n for (_, n) in tarjetas]
        docs = {(j["pais_id"], j["nombre"]): j for j in db["jugadores"].find(
            {"pais_id": {"$in": paises}, "nombre": {"$in": nombres}}, {"id": 1, "nombre": 1, "pais_id": 1, "disciplina": 1})}
        ahora = datetime.utcnow()
        for (equipo, nombre), t in tarjetas.items():
            pais_id = pais_de.get(equipo)
            j = docs.get((pais_id, nombre))
            if not j:
                continue
            estado, sancion = DI.aplicar_partido(j.get("disciplina"), t, fase_id)
            cambios: Dict[str, Any] = {"disciplina": {**estado, "ultimo_juego": juego_id}}
            if sancion:
                cambios["suspension"] = {"juego_id": juego_id, "codigo": sancion["codigo"], "motivo": sancion["motivo"], "partidos": sancion["partidos"],
                                         "restantes": sancion["partidos"], "minuto": t.get("minuto"), "rival": rival_de.get(pais_id), "fecha": juego.get("fecha"),
                                         "cumplidos": []}
            r = db["jugadores"].update_one({"id": j["id"], "disciplina.ultimo_juego": {"$ne": juego_id}}, {"$set": cambios})
            if sancion and r.modified_count:
                db["sanciones_historial"].update_one(
                    {"_id": f"{juego_id}:{j['id']}"},
                    {"$setOnInsert": {"juego_id": juego_id, "jugador_id": j["id"], "jugador": nombre, "pais_id": pais_id, "equipo": equipo,
                                      "codigo": sancion["codigo"], "motivo": sancion["motivo"], "partidos": sancion["partidos"], "minuto": t.get("minuto"),
                                      "rival": rival_de.get(pais_id), "fecha": juego.get("fecha"), "mundial_id": str(juego.get("mundial_id") or ""),
                                      "registrada_en": ahora}}, upsert=True)
    except Exception as e:
        print(f"No se pudieron registrar las sanciones del partido: {e}")


def limpiar_disciplina() -> None:
    """Todos sin sanciones ni amarillas (nuevo Mundial)."""
    db["jugadores"].update_many({"$or": [{"suspension": {"$ne": None}}, {"disciplina": {"$ne": None}}]}, {"$set": {"suspension": None, "disciplina": None}})


# --- Vistas -----------------------------------------------------------------------------------------------------------
def suspension_de(jugador: Dict[str, Any]) -> Dict[str, Any]:
    return DI.vista((jugador or {}).get("suspension"))


def suspendidos_de_pais(pais_id: int) -> Dict[int, Dict[str, Any]]:
    """{jugador_id: vista} de los suspendidos de una selección (plantilla)."""
    return {j["id"]: DI.vista(j["suspension"]) for j in db["jugadores"].find(
        {"pais_id": pais_id, "suspension.restantes": {"$gt": 0}}, {"id": 1, "suspension": 1})}


def suspendidos_ids(ids: List[int]) -> Dict[int, Dict[str, Any]]:
    if not ids:
        return {}
    return {j["id"]: DI.vista(j["suspension"]) for j in db["jugadores"].find(
        {"id": {"$in": list(ids)}, "suspension.restantes": {"$gt": 0}}, {"id": 1, "suspension": 1})}


def historial_de(jugador_id: int, limite: int = 10) -> List[Dict[str, Any]]:
    return [DI.vista({**h, "restantes": 0}) | {"jugador": h.get("jugador")} for h in db["sanciones_historial"].find({"jugador_id": jugador_id}).sort("registrada_en", -1).limit(limite)]


def sanciones_del_partido(juego: Dict[str, Any]) -> Dict[str, Any]:
    """Para el resumen: las sanciones que dejó este partido y los jugadores que no pudieron jugarlo por suspensión."""
    jid = str((juego or {}).get("_id"))
    nuevas = [{**DI.vista({**h, "restantes": 0}), "jugador": h.get("jugador"), "equipo": h.get("equipo"), "pais_id": h.get("pais_id"), "jugador_id": h.get("jugador_id")}
              for h in db["sanciones_historial"].find({"juego_id": jid}).sort("minuto", 1)]
    return {"nuevas": nuevas, "bajas": ((juego or {}).get("resultado") or {}).get("bajas_suspension") or []}


def bajas_previa(ids_paises: List[int]) -> Dict[int, List[dict]]:
    """{pais_id: [{jugador_id, nombre, tipo 'suspension'|'lesion', motivo, restantes}]} de los que NO podrían jugar el próximo partido."""
    salida: Dict[int, List[dict]] = {p: [] for p in ids_paises}
    for j in db["jugadores"].find({"pais_id": {"$in": ids_paises}, "$or": [{"suspension.restantes": {"$gt": 0}}, {"lesion.restantes": {"$gt": 0}}]},
                                  {"id": 1, "nombre": 1, "pais_id": 1, "suspension": 1, "lesion": 1}):
        s, l = j.get("suspension") or {}, j.get("lesion") or {}
        if int(s.get("restantes") or 0) > 0:
            salida[j["pais_id"]].append({"jugador_id": j["id"], "nombre": j["nombre"], "tipo": "suspension", "motivo": s.get("motivo"), "restantes": s["restantes"]})
        elif int(l.get("restantes") or 0) > 0:
            salida[j["pais_id"]].append({"jugador_id": j["id"], "nombre": j["nombre"], "tipo": "lesion", "motivo": l.get("nombre"), "restantes": l["restantes"]})
    return salida
