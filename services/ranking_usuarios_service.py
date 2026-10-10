"""
Ranking entre usuarios (/ranking/): compara a todos los usuarios activos en el meta-juego.

Patrimonio = saldo (usuarios.monto) + valor actual de sus selecciones activas
(team_ownerships.current_value) + lo pagado por sus sedes activas (city_ownerships.purchase_price;
las sedes no tienen valor de mercado). Además: puntos fantasy acumulados, aciertos en quinielas y
neto del Juego en Vivo (monto acreditado - entrada de las partidas terminadas).
"""
import certifi
from collections import defaultdict
from typing import Any, Dict, List

from pymongo.mongo_client import MongoClient

from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')


def _sumar_por_usuario(coleccion: str, filtro: dict, campo: str, clave_usuario: str = "user_id") -> Dict[str, float]:
    return {str(d["_id"]): d["total"] for d in db[coleccion].aggregate([
        {"$match": filtro}, {"$group": {"_id": f"${clave_usuario}", "total": {"$sum": {"$ifNull": [f"${campo}", 0]}}}},
    ])}


def obtener_ranking_usuarios() -> List[Dict[str, Any]]:
    selecciones = _sumar_por_usuario("team_ownerships", {"status": "ACTIVO"}, "current_value")
    dividendos = _sumar_por_usuario("team_ownerships", {}, "total_dividends_earned")
    sedes = _sumar_por_usuario("city_ownerships", {"status": "ACTIVO"}, "purchase_price")
    regalias = _sumar_por_usuario("city_revenue_history", {}, "total_earned")
    fantasy = _sumar_por_usuario("fantasy_teams", {}, "total_points_fase")

    # Quinielas: % de selecciones acertadas (sobre las ya resueltas)
    quinielas = defaultdict(lambda: {"acertadas": 0, "resueltas": 0, "boletos": 0})
    for b in db["quiniela_usuario"].find({}, {"usuario_id": 1, "selecciones.estado": 1}):
        q = quinielas[str(b.get("usuario_id"))]
        q["boletos"] += 1
        for s in b.get("selecciones") or []:
            if s.get("estado") in ("ACERTADO", "FALLADO"):
                q["resueltas"] += 1
                q["acertadas"] += 1 if s["estado"] == "ACERTADO" else 0

    juego_en_vivo = {str(d["_id"]): d for d in db["match_live_sessions"].aggregate([
        {"$match": {"estado": "finalizada"}},
        {"$group": {"_id": "$usuario_id", "neto": {"$sum": {"$subtract": ["$monto_acreditado", "$entrada_monto"]}}, "partidas": {"$sum": 1}}},
    ])}

    filas = []
    for u in db["usuarios"].find({"activo": {"$ne": False}}, {"username": 1, "nombre": 1, "monto": 1}):
        uid = str(u["_id"])
        q = quinielas.get(uid, {"acertadas": 0, "resueltas": 0, "boletos": 0})
        jev = juego_en_vivo.get(uid, {"neto": 0, "partidas": 0})
        saldo = u.get("monto", 0) or 0
        filas.append({
            "usuario_id": uid, "username": u.get("username"), "nombre": u.get("nombre") or u.get("username"),
            "saldo": saldo,
            "valor_selecciones": int(selecciones.get(uid, 0)), "valor_sedes": int(sedes.get(uid, 0)),
            "patrimonio": int(saldo + selecciones.get(uid, 0) + sedes.get(uid, 0)),
            "ingresos_pasivos": int(dividendos.get(uid, 0) + regalias.get(uid, 0)),
            "fantasy": int(fantasy.get(uid, 0)),
            "quinielas_boletos": q["boletos"],
            "quinielas_pct": round(100 * q["acertadas"] / q["resueltas"]) if q["resueltas"] else None,
            "juego_en_vivo_neto": int(jev["neto"]), "juego_en_vivo_partidas": jev["partidas"],
        })
    filas.sort(key=lambda f: (-f["patrimonio"], (f["nombre"] or "").lower()))
    for f in filas:
        # Empatados comparten posición (1 + cuántos tienen estrictamente más patrimonio)
        f["posicion"] = 1 + sum(1 for g in filas if g["patrimonio"] > f["patrimonio"])
    return filas
