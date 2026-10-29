"""
Lesiones fuera del partido: las bajas para los partidos siguientes (las lesiones en sí las decide el motor, ver
services/lesiones.py y config/lesiones.py).

- `registrar_partido(juego)` (gancho en juegos_service.aplicar_efectos_secundarios: corre al terminar el partido, en
  vivo después de la transmisión; idempotente por juego, nunca lanza):
    1) los lesionados de las dos selecciones que no se lesionaron en ESTE partido cumplen un partido de baja
       (`jugadores.lesion.restantes` -1; `lesion.cumplidos` guarda los juegos ya contados);
    2) cada lesión nueva de `resultado.lesiones` queda en `jugadores.lesion` (con `restantes` = partidos de baja), suma
       al contador `jugadores.lesiones` (por torneo) y se archiva en `lesiones_historial` (PERMANENTE).
  El motor no alinea a nadie con `lesion.restantes` > 0 (simular_service).
- `restart_mundial` y `crear_nuevo_mundial` limpian `jugadores.lesion` (`limpiar_lesiones`): cada Mundial empieza sano.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import certifi
from bson import ObjectId
from pymongo import MongoClient

from config.settings import MONGODB_URI
from services import lesiones as LS

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')


def registrar_partido(juego: Optional[Dict[str, Any]]) -> None:
    try:
        if not juego or not juego.get("resultado"):
            return
        juego_id = str(juego["_id"])
        resultado = juego["resultado"]
        id_local = (juego.get("equipo_local") or {}).get("id")
        id_visita = (juego.get("equipo_visitante") or {}).get("id")
        paises = [p for p in (id_local, id_visita) if p is not None]

        # 1) Cumplen un partido de baja (los que se lesionaron en este mismo partido no)
        if paises:
            db["jugadores"].update_many(
                {"pais_id": {"$in": paises}, "lesion.restantes": {"$gt": 0}, "lesion.juego_id": {"$ne": juego_id},
                 "lesion.cumplidos": {"$ne": juego_id}},
                {"$inc": {"lesion.restantes": -1}, "$push": {"lesion.cumplidos": juego_id}})

        # 2) Lesiones nuevas
        nombres = {id_local: (juego.get("equipo_local") or {}).get("nombre"),
                   id_visita: (juego.get("equipo_visitante") or {}).get("nombre")}
        for l in resultado.get("lesiones") or []:
            jid = l.get("jugador_id")
            pais_id = l.get("pais_id")
            rival_id = id_visita if pais_id == id_local else id_local
            lesion = {
                "juego_id": juego_id, "codigo": l.get("codigo"), "nombre": l.get("nombre"), "gravedad": l.get("gravedad"),
                "partidos": int(l.get("partidos") or 0), "restantes": int(l.get("partidos") or 0), "minuto": l.get("minuto"),
                "origen": l.get("origen"), "salio": bool(l.get("salio")), "rival_id": rival_id, "rival": nombres.get(rival_id),
                "fecha": juego.get("fecha"), "mundial_id": str(juego.get("mundial_id") or ""), "cumplidos": [],
            }
            res = db["jugadores"].update_one({"id": jid, "lesion.juego_id": {"$ne": juego_id}},
                                             {"$set": {"lesion": lesion}, "$inc": {"lesiones": 1}})
            if res.modified_count:
                db["lesiones_historial"].update_one(
                    {"_id": f"{juego_id}:{jid}"},
                    {"$setOnInsert": {**{k: v for k, v in lesion.items() if k != "cumplidos"}, "jugador_id": jid,
                                      "pais_id": pais_id, "registrada_en": datetime.utcnow()}},
                    upsert=True)
    except Exception as e:
        print(f"No se pudieron registrar las lesiones del partido: {e}")


def limpiar_lesiones() -> None:
    """Todos sanos (nuevo Mundial)."""
    db["jugadores"].update_many({"lesion": {"$ne": None}}, {"$set": {"lesion": None}})


def lesion_de(jugador: Dict[str, Any]) -> Dict[str, Any]:
    """Vista de la lesión vigente o de la última (para la ficha del jugador)."""
    return LS.vista(jugador.get("lesion")) if jugador else {}


def lesionados_de_pais(pais_id: int) -> Dict[int, Dict[str, Any]]:
    """{jugador_id: vista de su lesión} de los que están de baja en una selección (plantilla, ficha del país)."""
    return {j["id"]: LS.vista(j["lesion"]) for j in db["jugadores"].find(
        {"pais_id": pais_id, "lesion.restantes": {"$gt": 0}}, {"id": 1, "lesion": 1})}


def lesionados_ids(ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """Mismo dato para una lista de jugadores cualquiera (Once Ideal)."""
    if not ids:
        return {}
    return {j["id"]: LS.vista(j["lesion"]) for j in db["jugadores"].find(
        {"id": {"$in": list(ids)}, "lesion.restantes": {"$gt": 0}}, {"id": 1, "lesion": 1})}


def historial_de(jugador_id: int, limite: int = 10) -> List[Dict[str, Any]]:
    return [LS.vista({**h, "restantes": 0}) for h in db["lesiones_historial"].find(
        {"jugador_id": jugador_id}).sort("registrada_en", -1).limit(limite)]


def lesiones_del_partido(juego: Dict[str, Any]) -> Dict[str, Any]:
    """Para el resumen del partido: las lesiones que hubo y las bajas con que llegó cada selección."""
    res = (juego or {}).get("resultado") or {}
    return {"lesiones": [LS.vista({**l, "restantes": l.get("partidos", 0)}) for l in res.get("lesiones") or []],
            "bajas": res.get("bajas_lesion") or []}
