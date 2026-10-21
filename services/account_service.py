"""
Resumen de cuenta del usuario (vista "Mi Cuenta"): agrega en un solo lugar la
actividad de todos los módulos de economía de puntos construidos en esta app
(Selecciones, Sedes, Quinielas, Fantasy, Álbum, Recompensas/Trivia).

Notas de diseño / decisiones sobre ambigüedades del pedido original:
- El pedido fue "un resumen de todas las transacciones, adquisiciones,
  inversiones y demás información asociada al usuario, con gráficas". No hay
  una única colección de auditoría transversal: cada módulo tiene la suya
  (o, en el caso de Sedes, ninguna dedicada a compra/venta). Este servicio
  arma un FEED unificado combinando:
    - ownership_transactions (selecciones: compra/venta/dividendo/bono/sinergia)
    - city_ownerships (sedes: compra/venta — sintetizado desde purchased_at/
      sold_at, porque a diferencia de selecciones este módulo nunca tuvo una
      colección de transacciones propia) + city_revenue_history (regalías)
    - quiniela_usuario (compra de boleto + premio si ganó)
    - pack_purchases (compra de sobre + bonus por estampas duplicadas)
    - trivia_history (sesiones COMPLETADA)
    - reward_transactions (check-in diario y Beca de Emergencia — colección
      NUEVA agregada junto con este resumen: services/rewards_service.py no
      registraba estos eventos individualmente, solo contadores acumulados
      en user_daily_rewards. Los check-ins/becas reclamados ANTES de este
      cambio no van a aparecer en el feed histórico, solo los de acá en más).
- "Evolución del balance" (gráfica de línea): es el NETO acumulado de los
  eventos que sí están en el feed, no el saldo histórico real de
  'usuarios.monto' (que arranca en 1000 y pudo moverse por otras vías, ej. el
  saldo inicial o ajustes manuales). Se etiquola explícitamente como "balance
  de actividad registrada" en la UI para no insinuar que es un historial
  contable exacto.
"""
import certifi
from typing import Any, Dict, List
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
from services.niveles_service import listar_recompensas_reclamadas

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

MAX_ITEMS_FEED = 100

ETIQUETAS_OWNERSHIP = {
    "COMPRA": "Compra de selección",
    "VENTA": "Venta de selección",
    "DIVIDENDO": "Dividendo por victoria",
    "BONO_CLASIFICACION": "Bono de clasificación",
    "SINERGIA_ALBUM": "Sinergia con el Álbum"
}

ETIQUETAS_REWARD = {
    "CHECKIN": "Check-in diario",
    "CHECKIN_ESPECIAL": "Check-in diario (racha de 5 días)",
    "BECA_EMERGENCIA": "Beca de Emergencia"
}


def obtener_resumen_cuenta(user_id: str) -> Dict[str, Any]:
    usuario_oid = ObjectId(user_id)

    # ---------------------------------------------------------------
    # Selecciones (Ownership)
    # ---------------------------------------------------------------
    selecciones = list(db['team_ownerships'].find({"user_id": usuario_oid}))
    transacciones_ownership = list(db['ownership_transactions'].find({"user_id": usuario_oid}))

    ids_paises = {s["pais_id"] for s in selecciones} | {t["pais_id"] for t in transacciones_ownership}
    nombres_paises = {p["id"]: p.get("nombre", "?") for p in db['paises'].find({"id": {"$in": list(ids_paises)}}, {"id": 1, "nombre": 1})}

    selecciones_activas = [s for s in selecciones if s.get("status") == "ACTIVO"]
    resumen_selecciones = {
        "cantidad_activas": len(selecciones_activas),
        "cantidad_total": len(selecciones),
        "total_invertido": sum(s.get("purchase_price", 0) for s in selecciones),
        "total_dividendos": sum(s.get("total_dividends_earned", 0) for s in selecciones_activas),
        "detalle": [
            {
                "pais_id": s["pais_id"],
                "pais_nombre": nombres_paises.get(s["pais_id"], "?"),
                "purchase_price": s.get("purchase_price", 0),
                "current_value": s.get("current_value", 0),
                "total_dividends_earned": s.get("total_dividends_earned", 0),
                "status": s.get("status")
            }
            for s in selecciones_activas
        ]
    }

    # ---------------------------------------------------------------
    # Sedes (Venues)
    # ---------------------------------------------------------------
    sedes = list(db['city_ownerships'].find({"user_id": usuario_oid}))
    regalias_sedes = list(db['city_revenue_history'].find({"user_id": usuario_oid}))

    ids_ciudades = {s["ciudad_id"] for s in sedes} | {r["ciudad_id"] for r in regalias_sedes}
    nombres_ciudades = {c["id"]: c.get("nombre", "?") for c in db['ciudades'].find({"id": {"$in": list(ids_ciudades)}}, {"id": 1, "nombre": 1})}

    sedes_activas = [s for s in sedes if s.get("status") == "ACTIVO"]
    resumen_sedes = {
        "cantidad_activas": len(sedes_activas),
        "cantidad_total": len(sedes),
        "total_invertido": sum(s.get("purchase_price", 0) for s in sedes),
        "total_regalias": sum(s.get("total_revenue_earned", 0) for s in sedes_activas),
        "partidos_alojados": sum(s.get("matches_hosted_count", 0) for s in sedes_activas),
        "detalle": [
            {
                "ciudad_id": s["ciudad_id"],
                "ciudad_nombre": nombres_ciudades.get(s["ciudad_id"], "?"),
                "purchase_price": s.get("purchase_price", 0),
                "total_revenue_earned": s.get("total_revenue_earned", 0),
                "matches_hosted_count": s.get("matches_hosted_count", 0),
                "status": s.get("status")
            }
            for s in sedes_activas
        ]
    }

    # ---------------------------------------------------------------
    # Quinielas
    # ---------------------------------------------------------------
    boletos = list(db['quiniela_usuario'].find({"usuario_id": usuario_oid}))
    resumen_quinielas = {
        "cantidad": len(boletos),
        "ganadas": sum(1 for b in boletos if b.get("estado") == "GANADA"),
        "perdidas": sum(1 for b in boletos if b.get("estado") == "PERDIDA"),
        "pendientes": sum(1 for b in boletos if b.get("estado") == "PENDIENTE"),
        "total_apostado": sum(b.get("costo_pagado", 0) for b in boletos),
        "total_ganado": sum(b.get("premio_ganado", 0) for b in boletos)
    }

    # ---------------------------------------------------------------
    # Fantasy (Once Ideal)
    # ---------------------------------------------------------------
    equipos_fantasy = list(db['fantasy_teams'].find({"user_id": usuario_oid}))
    resumen_fantasy = {
        "alineaciones_armadas": len(equipos_fantasy),
        "puntos_totales": sum(e.get("total_points_fase", 0) for e in equipos_fantasy)
    }

    # ---------------------------------------------------------------
    # Álbum de Estampas
    # ---------------------------------------------------------------
    album = db['user_albums'].find_one({"user_id": usuario_oid}) or {}
    sobres_comprados = list(db['pack_purchases'].find({"user_id": usuario_oid}))
    resumen_album = {
        "jugadores": len(album.get("owned_jugadores", [])),
        "paises": len(album.get("owned_paises", [])),
        "ciudades": len(album.get("owned_ciudades", [])),
        "arbitros": len(album.get("owned_arbitros", [])),
        "sobres_comprados": len(sobres_comprados),
        "total_gastado_sobres": sum(p.get("cost_paid", 0) for p in sobres_comprados)
    }

    # ---------------------------------------------------------------
    # Recompensas Diarias / Trivia
    # ---------------------------------------------------------------
    registro_rewards = db['user_daily_rewards'].find_one({"user_id": usuario_oid}) or {}
    sesiones_trivia_completadas = list(db['trivia_history'].find({"user_id": usuario_oid, "estado": "COMPLETADA"}))
    resumen_rewards = {
        "racha_actual": registro_rewards.get("consecutive_days", 0),
        "total_checkins": registro_rewards.get("total_checkins", 0),
        "trivia_sesiones_jugadas": len(sesiones_trivia_completadas),
        "trivia_puntos_totales": sum(s.get("points_rewarded", 0) for s in sesiones_trivia_completadas)
    }

    # ---------------------------------------------------------------
    # Feed unificado de transacciones (más reciente primero)
    # ---------------------------------------------------------------
    feed: List[Dict[str, Any]] = []

    for t in transacciones_ownership:
        feed.append({
            "fecha": t["created_at"],
            "categoria": "Selección",
            "descripcion": f"{ETIQUETAS_OWNERSHIP.get(t['type'], t['type'])} — {nombres_paises.get(t['pais_id'], '?')}",
            "monto": t.get("amount_points", 0)
        })

    for s in sedes:
        if s.get("purchased_at"):
            feed.append({
                "fecha": s["purchased_at"],
                "categoria": "Sede",
                "descripcion": f"Compra de sede — {nombres_ciudades.get(s['ciudad_id'], '?')}",
                "monto": -s.get("purchase_price", 0)
            })
        if s.get("status") == "VENDIDO" and s.get("sold_at"):
            feed.append({
                "fecha": s["sold_at"],
                "categoria": "Sede",
                "descripcion": f"Venta de sede — {nombres_ciudades.get(s['ciudad_id'], '?')}",
                "monto": s.get("sale_price", 0)
            })

    for r in regalias_sedes:
        feed.append({
            "fecha": r["created_at"],
            "categoria": "Sede",
            "descripcion": "Regalía de taquilla" + (" (sinergia Álbum)" if r.get("album_synergy_applied") else ""),
            "monto": r.get("total_earned", 0)
        })

    for b in boletos:
        if b.get("fecha_creacion"):
            feed.append({
                "fecha": b["fecha_creacion"],
                "categoria": "Quiniela",
                "descripcion": "Compra de quiniela",
                "monto": -b.get("costo_pagado", 0)
            })
        if b.get("estado") == "GANADA" and b.get("fecha_resolucion"):
            feed.append({
                "fecha": b["fecha_resolucion"],
                "categoria": "Quiniela",
                "descripcion": f"Premio de quiniela ({b.get('aciertos', 0)} aciertos)",
                "monto": b.get("premio_ganado", 0)
            })

    for p in sobres_comprados:
        if p.get("created_at"):
            regalo = p.get("origen") in ("GRATIS", "PLATINO")
            feed.append({
                "fecha": p["created_at"],
                "categoria": "Álbum",
                "descripcion": ("Sobre Platino de regalo (recompensa de nivel)" if p.get("origen") == "PLATINO"
                                else "Sobre gratis (recompensa de nivel)" if regalo else "Compra de sobre de estampas"),
                "monto": -p.get("cost_paid", 0)
            })
            bonus_total = sum(e.get("bonus_puntos", 0) for e in p.get("stickers_obtained", []))
            if bonus_total > 0:
                feed.append({
                    "fecha": p["created_at"],
                    "categoria": "Álbum",
                    "descripcion": "Estampas duplicadas (bonus)",
                    "monto": bonus_total
                })

    for s in sesiones_trivia_completadas:
        if s.get("completed_at"):
            feed.append({
                "fecha": s["completed_at"],
                "categoria": "Trivia",
                "descripcion": f"Trivia completada ({s.get('correct_answers', 0)}/{s.get('questions_asked', 3)} aciertos)",
                "monto": s.get("points_rewarded", 0)
            })

    # Abonos hechos por un administrador (services/usuarios_service.abonar_puntos)
    for aj in db['ajustes_saldo'].find({"user_id": usuario_oid}):
        feed.append({
            "fecha": aj["creado_en"],
            "categoria": "Ajuste",
            "descripcion": f"Abono del administrador: {aj.get('motivo', '')}",
            "monto": aj.get("monto", 0),
        })

    # Recompensas de nivel reclamadas (services/niveles_service.py): solo las de puntos mueven el saldo
    for rn in listar_recompensas_reclamadas(usuario_oid):
        for r in rn.get("recompensas", []):
            feed.append({
                "fecha": rn["reclamada_en"],
                "categoria": "Nivel",
                "descripcion": (f"Recompensa del nivel {rn['nivel']}" if r["tipo"] == "PUNTOS"
                                else f"Recompensa del nivel {rn['nivel']}: {r['cantidad']} sobre{'s' if r['cantidad'] != 1 else ''} {'Platino' if r['tipo'] == 'PLATINO' else 'gratis'}"),
                "monto": r["cantidad"] if r["tipo"] == "PUNTOS" else 0,
            })

    for rt in db['reward_transactions'].find({"user_id": usuario_oid}):
        feed.append({
            "fecha": rt["created_at"],
            "categoria": "Recompensas",
            "descripcion": ETIQUETAS_REWARD.get(rt["type"], rt["type"]),
            "monto": rt.get("amount_points", 0)
        })

    # Juego en Vivo (services/juego_en_vivo_service.py): solo los movimientos de usuarios.monto
    # (entrada, pago final, reembolso); los puntos por evento son internos de cada partida.
    for jt in db['point_transactions'].find({"usuario_id": usuario_oid, "tipo_movimiento": {"$in": ["ENTRADA", "PAGO_FINAL", "REEMBOLSO"]}}):
        feed.append({
            "fecha": jt["creado_en"],
            "categoria": "Juego en Vivo",
            "descripcion": jt.get("descripcion", jt["tipo_movimiento"]),
            "monto": jt.get("puntos_netos", 0)
        })

    # Corporativos Deportivos: sueldo + bono del CEO y operaciones de la bolsa (lo que mueve usuarios.monto).
    # universo_id = _id del usuario como string; los asientos de sueldo están en negativo para el corporativo.
    for mv in db['corp_movimientos'].find({"universo_id": str(user_id), "tipo": "SUELDO_CEO"}):
        feed.append({
            "fecha": mv["creado_en"],
            "categoria": "Corporativo",
            "descripcion": f"Sueldo de CEO en {mv['sigla']} (ciclo {mv['ciclo']})",
            "monto": -mv.get("monto", 0),
        })
    for op in db['corp_operaciones_bolsa'].find({"universo_id": str(user_id), "tipo": {"$in": ["COMPRA", "VENTA", "DIVIDENDO"]}}):
        if not op.get("monto"):
            continue
        feed.append({
            "fecha": op["creado_en"],
            "categoria": "Bolsa",
            "descripcion": {"COMPRA": "Compra", "VENTA": "Venta", "DIVIDENDO": "Dividendo"}[op["tipo"]]
                           + f" de acciones de {op['sigla']}" + (f" ({op['cantidad']:,.0f})" if op["tipo"] != "DIVIDENDO" else ""),
            "monto": op.get("monto", 0),
        })

    # Asistente "El Profe": lo cobrado (las devoluciones de la garantía quedan en 0 y no se listan)
    for c in db['asistente_consultas'].find({"user_id": usuario_oid, "cobrado": {"$gt": 0}}, {"fecha": 1, "nivel": 1, "cobrado": 1}):
        feed.append({
            "fecha": c["fecha"],
            "categoria": "Asistente",
            "descripcion": f"Consulta al Profe ({ {'VISTAZO': 'Vistazo', 'ANALISIS': 'Análisis', 'PROFUNDO': 'Informe profundo'}.get(c['nivel'], c['nivel']) })",
            "monto": -c["cobrado"],
        })

    feed.sort(key=lambda x: x["fecha"], reverse=True)

    # ---------------------------------------------------------------
    # Datos para gráficas (Chart.js, ver templates/cuenta.html)
    # ---------------------------------------------------------------
    gasto_por_categoria: Dict[str, int] = {}
    ingreso_por_categoria: Dict[str, int] = {}
    for item in feed:
        bucket = gasto_por_categoria if item["monto"] < 0 else ingreso_por_categoria
        bucket[item["categoria"]] = bucket.get(item["categoria"], 0) + abs(item["monto"])

    saldo_acumulado = 0
    evolucion_saldo = []
    for item in sorted(feed, key=lambda x: x["fecha"]):
        saldo_acumulado += item["monto"]
        evolucion_saldo.append({"fecha": item["fecha"].strftime("%Y-%m-%d"), "saldo_acumulado": saldo_acumulado})

    return {
        "selecciones": resumen_selecciones,
        "sedes": resumen_sedes,
        "quinielas": resumen_quinielas,
        "fantasy": resumen_fantasy,
        "album": resumen_album,
        "rewards": resumen_rewards,
        "feed": feed[:MAX_ITEMS_FEED],
        "graficas": {
            "gasto_por_categoria": gasto_por_categoria,
            "ingreso_por_categoria": ingreso_por_categoria,
            "evolucion_saldo": evolucion_saldo
        }
    }
