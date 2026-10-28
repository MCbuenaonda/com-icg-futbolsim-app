"""
Evolución de las ESPECIALIDADES (reglas en config/especialidades.py, lógica pura en services/especialidades.py).

registrar_partido se llama al final de juegos_service.aplicar_efectos_secundarios (en la transmisión en vivo, al
terminar: no spoilea; nunca lanza). Por cada jugador que participó (salvo leyendas, que no evolucionan):
  1. agrega el resumen del partido a jugadores.esp_ventana (últimos VENTANA_GUARDADA; idempotente por juego_id);
  2. suma un partido a cada especialidad que tiene (jugadores.esp_partidos: período de gracia);
  3. evalúa pérdidas y ganancias POR SELECCIÓN con equilibrio, piso y techo (ES.evolucionar_equipo, con el total de
     especialidades de sus 22 actuales) y las escribe (especialidades + booleanos de penales/tiros libres) en un bulk_write;
  4. deja cada cambio en la colección PERMANENTE especialidades_historial.
Todo es permanente (la carrera del jugador): restart_mundial no lo toca.
"""
import certifi
from datetime import datetime
from typing import Dict, List, Optional

from pymongo import UpdateOne
from pymongo.mongo_client import MongoClient

from config import especialidades as CE
from config.fantasy import LINEA_DE_POSICION
from config.settings import MONGODB_URI
from services import especialidades as ES

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')


def _es_partido_grande(juego_doc: Optional[dict]) -> bool:
    """Eliminación directa del Mundial (fases 8-13) o partido de serie con alargue posible."""
    if not juego_doc:
        return False
    return (juego_doc.get("fase_id") or 0) >= 8 or bool(juego_doc.get("tiempo_extra"))


def registrar_partido(juego_id: str, stats_jugadores: Dict, goles_local: int, goles_visitante: int,
                      juego_doc: Optional[dict] = None) -> List[dict]:
    """Aplica la evolución del partido. Devuelve los cambios [{jugador_id, codigo, tipo, motivo}] (vacío si nada)."""
    try:
        if not stats_jugadores:
            return []
        juego_id = str(juego_id)
        grande = _es_partido_grande(juego_doc)
        ids = []
        for k in stats_jugadores:
            try:
                ids.append(int(k))
            except (TypeError, ValueError):
                pass
        docs = {j["id"]: j for j in db["jugadores"].find(
            {"id": {"$in": ids}}, {"id": 1, "nombre": 1, "pais_id": 1, "posicion_id": 1, "leyenda": 1, "especialidades": 1,
                                   "esp_ventana": 1, "esp_partidos": 1})}
        mundial = db["mundiales"].find_one({"activo": True}, {"_id": 1})
        # 1) Resumen del partido y partidos jugados con cada especialidad, por jugador (agrupados por selección)
        por_pais: Dict[int, list] = {}
        for k, st in stats_jugadores.items():
            try:
                jid = int(k)
            except (TypeError, ValueError):
                continue
            j = docs.get(jid)
            if not j or j.get("leyenda"):
                continue
            ventana = list(j.get("esp_ventana") or [])
            if any(p.get("j") == juego_id for p in ventana):
                continue   # ya registrado (idempotente)
            gc = goles_visitante if st.get("lado") == "L" else goles_local
            ventana = (ventana + [ES.resumen_partido(st, gc, grande, juego_id)])[-CE.VENTANA_GUARDADA:]
            esp = [c for c in (j.get("especialidades") or []) if c in CE.ESPECIALIDADES]
            partidos = dict(j.get("esp_partidos") or {})
            for c in esp:
                partidos[c] = partidos.get(c, 0) + 1
            por_pais.setdefault(j.get("pais_id"), []).append({
                "jid": jid, "nombre": j.get("nombre"), "pais_id": j.get("pais_id"), "linea": LINEA_DE_POSICION.get(j.get("posicion_id"), "MEDIO"),
                "especialidades": esp, "esp_ventana": ventana, "esp_partidos": partidos, "cal": st.get("rating")})
        # 2) Total de especialidades de los 22 actuales de cada selección (equilibrio, piso y techo)
        totales = {pid: 0 for pid in por_pais}
        for d in db["jugadores"].find({"pais_id": {"$in": list(por_pais)}, "leyenda": {"$ne": True}}, {"pais_id": 1, "especialidades": 1}):
            totales[d["pais_id"]] = totales.get(d["pais_id"], 0) + len(d.get("especialidades") or [])
        # 3) Evolución por selección (ES.evolucionar_equipo) y escritura
        ops, historial, cambios = [], [], []
        ahora = datetime.now()
        for pid, estados in por_pais.items():
            resultado = ES.evolucionar_equipo(estados, totales.get(pid, CE.BASE_SELECCION))
            for e in estados:
                esp, partidos = list(e["especialidades"]), dict(e["esp_partidos"])
                ganadas, perdidas = resultado.get(e["jid"], ([], []))
                for c, _ in perdidas:
                    esp.remove(c)
                    partidos.pop(c, None)
                for c, _ in ganadas:
                    esp.append(c)
                    partidos[c] = 0
                sets = {"esp_ventana": e["esp_ventana"], "esp_partidos": partidos}
                if ganadas or perdidas:
                    sets.update(especialidades=esp, especialista_penales="penales" in esp, especialista_tiros_libres="tiros_libres" in esp)
                    for tipo, lista in (("PERDIDA", perdidas), ("GANADA", ganadas)):
                        for c, motivo in lista:
                            doc = {"_id": f"{e['jid']}:{c}:{tipo}:{juego_id}", "jugador_id": e["jid"], "jugador_nombre": e["nombre"],
                                   "pais_id": pid, "codigo": c, "tipo": tipo, "motivo": motivo, "juego_id": juego_id,
                                   "mundial_id": str(mundial["_id"]) if mundial else None, "fecha": ahora}
                            historial.append(UpdateOne({"_id": doc["_id"]}, {"$setOnInsert": doc}, upsert=True))
                            cambios.append({"jugador_id": e["jid"], "codigo": c, "tipo": tipo, "motivo": motivo})
                ops.append(UpdateOne({"id": e["jid"]}, {"$set": sets}))
        if ops:
            db["jugadores"].bulk_write(ops, ordered=False)
        if historial:
            db["especialidades_historial"].bulk_write(historial, ordered=False)
        return cambios
    except Exception as e:
        print(f"[especialidades] no se pudo registrar el partido {juego_id}: {e}")
        return []


def cambios_del_partido(juego_id: str) -> List[dict]:
    """Para el resumen del partido: quién ganó o perdió una especialidad en él."""
    try:
        filas = list(db["especialidades_historial"].find({"juego_id": str(juego_id)}).sort([("tipo", -1), ("jugador_nombre", 1)]))
        return [{**f, "_id": str(f["_id"]), "especialidad": (ES.vista([f["codigo"]]) or [{}])[0]} for f in filas]
    except Exception:
        return []


def historial_de(jugador_id: int, limite: int = 12) -> List[dict]:
    """Ganadas y perdidas de un jugador (más recientes primero), con el rival del partido."""
    try:
        filas = list(db["especialidades_historial"].find({"jugador_id": int(jugador_id)}).sort("fecha", -1).limit(limite))
        from bson import ObjectId
        juegos = {str(x["_id"]): x for x in db["juegos"].find(
            {"_id": {"$in": [ObjectId(f["juego_id"]) for f in filas if ObjectId.is_valid(f.get("juego_id", ""))]}},
            {"equipo_local": 1, "equipo_visitante": 1, "fecha": 1})}
        salida = []
        for f in filas:
            g = juegos.get(f.get("juego_id")) or {}
            loc, vis = g.get("equipo_local") or {}, g.get("equipo_visitante") or {}
            rival = vis if loc.get("id") == f.get("pais_id") else loc
            salida.append({**f, "_id": str(f["_id"]), "especialidad": (ES.vista([f["codigo"]]) or [{}])[0],
                           "rival": rival.get("nombre"), "rival_bandera": rival.get("bandera"), "fecha_partido": g.get("fecha")})
        return salida
    except Exception:
        return []


def evolucion_jugador(jugador: dict) -> dict:
    """Bloque «Evolución» de la ficha: progreso hacia las más cercanas, en riesgo, historial y de dónde salió cada una."""
    if not jugador or jugador.get("leyenda"):
        return {"leyenda": bool(jugador and jugador.get("leyenda"))}
    estado = {"linea": LINEA_DE_POSICION.get(jugador.get("posicion_id"), "MEDIO"), "especialidades": jugador.get("especialidades") or [],
              "esp_ventana": jugador.get("esp_ventana") or []}
    hist = historial_de(jugador.get("id"))
    ganadas = {}
    for h in reversed(hist):
        if h["tipo"] == "GANADA":
            ganadas[h["codigo"]] = h
        else:
            ganadas.pop(h["codigo"], None)
    return {**ES.progreso(estado), "historial": hist, "ganadas": ganadas, "seleccion": estado_seleccion(jugador.get("pais_id"))}


def ganadas_de_pais(pais_id) -> Dict[int, set]:
    """{jugador_id: {codigos ganados que conserva}} de una selección (marca ↑ en la plantilla)."""
    try:
        vigentes: Dict[int, set] = {}
        for h in db["especialidades_historial"].find({"pais_id": int(pais_id)}, {"jugador_id": 1, "codigo": 1, "tipo": 1}).sort("fecha", 1):
            s = vigentes.setdefault(h["jugador_id"], set())
            (s.add if h["tipo"] == "GANADA" else s.discard)(h["codigo"])
        return vigentes
    except Exception:
        return {}


def estado_seleccion(pais_id) -> dict:
    """Total de especialidades de los 22 actuales de una selección contra la base, el piso y el techo."""
    try:
        total = sum(len(d.get("especialidades") or []) for d in db["jugadores"].find(
            {"pais_id": int(pais_id), "leyenda": {"$ne": True}}, {"especialidades": 1}))
    except Exception:
        total = CE.BASE_SELECCION
    rango = CE.TECHO_SELECCION - CE.PISO_SELECCION
    return {"total": total, "base": CE.BASE_SELECCION, "piso": CE.PISO_SELECCION, "techo": CE.TECHO_SELECCION,
            "en_techo": total >= CE.TECHO_SELECCION, "en_piso": total <= CE.PISO_SELECCION,
            "pct": round((total - CE.PISO_SELECCION) * 100 / rango), "pct_base": round((CE.BASE_SELECCION - CE.PISO_SELECCION) * 100 / rango)}
