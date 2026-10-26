"""
Lógica de negocio de "Daily Check-in" y "Beca de Emergencia" (rescate de
bancarrota). La generación/validación de trivia vive aparte, en
services/trivia_service.py, porque son dos dominios distintos aunque
compartan la misma colección de estado por usuario (user_daily_rewards).

Notas de diseño / decisiones sobre ambigüedades del pedido original:
- Fecha de check-in "UTC/Local": esta app no maneja zonas horarias en ningún
  otro lado (todos los demás módulos usan datetime.now() del servidor sin
  tz-awareness), así que 'last_checkin_date' usa date.today() del servidor
  para quedar consistente con ese criterio existente, guardado como string
  ISO ('YYYY-MM-DD') para poder comparar por fecha calendario sin líos de hora.
- "Racha de 5 días reinicia": se interpreta como reinicio a 0 (no a 1) al
  otorgar el bono especial, para que el check-in del día siguiente arranque
  una racha nueva de un solo día.
- "No tiene inversiones ni quinielas activas" (Beca de Emergencia): esta app
  tiene DOS módulos de inversión (selecciones en team_ownerships, sedes en
  city_ownerships), no solo uno. Se consideran ambos — un usuario con una
  sede activa pero sin selecciones tampoco puede reclamar la beca.
- "1 reclamo por fase del mundial": igual que en ownership_service.py, esta
  app no tiene una fase global única. Se usa la fase del PRÓXIMO partido
  pendiente (obtener_juego_activo, servicios/juegos_service.py) como proxy de
  "fase actual" — mismo criterio ya usado para "fase iniciada" en
  fantasy_service.py. Si no hay ningún partido pendiente (fase_id = None),
  la regla degrada a "1 reclamo en total" mientras dure ese estado: se
  distingue explícitamente "nunca reclamó" (campo ausente) de "reclamó con
  fase_id=None" para no bloquear el primer reclamo de un usuario nuevo.
"""
import certifi
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
from services import niveles_service

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

BONO_CHECKIN_DIARIO = 50
DIAS_RACHA_BONO_ESPECIAL = 5
BONO_RACHA_ESPECIAL = 150

MONTO_BECA_EMERGENCIA = 100

TIPO_TRANSACCION_CHECKIN = "CHECKIN"
TIPO_TRANSACCION_CHECKIN_ESPECIAL = "CHECKIN_ESPECIAL"
TIPO_TRANSACCION_BECA_EMERGENCIA = "BECA_EMERGENCIA"

_SIN_RECLAMO_PREVIO = "__NUNCA__"  # sentinel para distinguir "nunca reclamó" de "reclamó con fase_id=None"


def _obtener_usuario_activo(user_id: str) -> Dict[str, Any]:
    usuario_oid = ObjectId(user_id)
    usuario = db['usuarios'].find_one({"_id": usuario_oid})
    if not usuario or not usuario.get("activo", True):
        raise ValueError("Usuario no encontrado o inactivo")
    return usuario


def _fase_actual() -> Optional[int]:
    from services.juegos_service import obtener_juego_activo
    juego_activo, _ = obtener_juego_activo()
    return juego_activo.get("fase_id") if juego_activo else None


# ==========================================
# Daily Check-in
# ==========================================
def check_in(user_id: str) -> dict:
    """
    Reclama el bono diario de ingreso (+50 pts). Si el usuario completa 5 días
    consecutivos, otorga un bono especial de +150 pts adicionales y reinicia
    la racha a 0. Solo se puede reclamar una vez por fecha calendario.
    """
    usuario_oid = ObjectId(user_id)
    _obtener_usuario_activo(user_id)

    hoy = date.today()
    hoy_str = hoy.isoformat()
    ayer_str = (hoy - timedelta(days=1)).isoformat()

    registro = db['user_daily_rewards'].find_one({"user_id": usuario_oid}) or {}

    if registro.get("last_checkin_date") == hoy_str:
        raise ValueError("Ya reclamaste tu recompensa diaria de hoy")

    racha_previa = registro.get("consecutive_days", 0)
    nueva_racha = racha_previa + 1 if registro.get("last_checkin_date") == ayer_str else 1

    bono = BONO_CHECKIN_DIARIO
    bono_especial_otorgado = False
    if nueva_racha >= DIAS_RACHA_BONO_ESPECIAL:
        bono += BONO_RACHA_ESPECIAL
        bono_especial_otorgado = True
        nueva_racha = 0

    db['usuarios'].update_one({"_id": usuario_oid}, {"$inc": {"monto": bono}})
    db['user_daily_rewards'].update_one(
        {"user_id": usuario_oid},
        {
            "$set": {"last_checkin_date": hoy_str, "consecutive_days": nueva_racha},
            "$inc": {"total_checkins": 1}
        },
        upsert=True
    )
    db['reward_transactions'].insert_one({
        "user_id": usuario_oid,
        "type": TIPO_TRANSACCION_CHECKIN_ESPECIAL if bono_especial_otorgado else TIPO_TRANSACCION_CHECKIN,
        "amount_points": bono,
        "created_at": datetime.now()
    })

    total_checkins = registro.get("total_checkins", 0) + 1

    # XP de niveles (nunca lanza): el check-in del día y, si cerró la racha de 5, el bonus
    niveles_service.otorgar_xp(usuario_oid, "CHECKIN", hoy_str)
    if bono_especial_otorgado:
        niveles_service.otorgar_xp(usuario_oid, "CHECKIN_RACHA", hoy_str)

    return {
        "bono_otorgado": bono,
        "bono_especial_otorgado": bono_especial_otorgado,
        "racha_actual": nueva_racha,
        "total_checkins": total_checkins
    }


# ==========================================
# Beca de Emergencia (rescate de bancarrota)
# ==========================================
def claim_bankruptcy_rescue(user_id: str) -> dict:
    """
    Otorga +100 pts si el usuario está en saldo 0 y no tiene inversiones
    (selecciones ni sedes) ni quinielas activas. Limitado a 1 reclamo por
    fase del mundial (ver nota de diseño en el docstring del módulo).
    """
    usuario_oid = ObjectId(user_id)
    usuario = _obtener_usuario_activo(user_id)

    if usuario.get("monto", 0) != 0:
        raise ValueError("Solo puedes reclamar la Beca de Emergencia si tu saldo es 0")

    tiene_selecciones = db['team_ownerships'].count_documents({"user_id": usuario_oid, "status": "ACTIVO"}) > 0
    tiene_sedes = db['city_ownerships'].count_documents({"user_id": usuario_oid, "status": "ACTIVO"}) > 0
    tiene_quinielas = db['quiniela_usuario'].count_documents({"usuario_id": usuario_oid, "estado": "PENDIENTE"}) > 0

    if tiene_selecciones or tiene_sedes or tiene_quinielas:
        raise ValueError("No puedes reclamar la Beca de Emergencia mientras tengas inversiones o quinielas activas")

    fase_actual = _fase_actual()
    registro = db['user_daily_rewards'].find_one({"user_id": usuario_oid}) or {}

    if registro.get("last_bankruptcy_fase", _SIN_RECLAMO_PREVIO) == fase_actual:
        raise ValueError("Ya reclamaste la Beca de Emergencia en esta fase del mundial")

    db['usuarios'].update_one({"_id": usuario_oid}, {"$inc": {"monto": MONTO_BECA_EMERGENCIA}})
    db['user_daily_rewards'].update_one(
        {"user_id": usuario_oid},
        {"$set": {"last_bankruptcy_fase": fase_actual}},
        upsert=True
    )
    db['reward_transactions'].insert_one({
        "user_id": usuario_oid,
        "type": TIPO_TRANSACCION_BECA_EMERGENCIA,
        "amount_points": MONTO_BECA_EMERGENCIA,
        "created_at": datetime.now()
    })

    return {"monto_otorgado": MONTO_BECA_EMERGENCIA, "fase_id": fase_actual}


# ==========================================
# Estado diario (para pintar el modal/calendario de check-in y habilitar botones)
# ==========================================
def obtener_daily_status(user_id: str) -> dict:
    usuario_oid = ObjectId(user_id)
    usuario = _obtener_usuario_activo(user_id)

    hoy = date.today()
    hoy_str = hoy.isoformat()
    registro = db['user_daily_rewards'].find_one({"user_id": usuario_oid}) or {}

    ya_reclamo_checkin_hoy = registro.get("last_checkin_date") == hoy_str
    racha_actual = registro.get("consecutive_days", 0)
    dias_para_bono_especial = max(0, DIAS_RACHA_BONO_ESPECIAL - racha_actual)

    tiene_selecciones = db['team_ownerships'].count_documents({"user_id": usuario_oid, "status": "ACTIVO"}) > 0
    tiene_sedes = db['city_ownerships'].count_documents({"user_id": usuario_oid, "status": "ACTIVO"}) > 0
    tiene_quinielas = db['quiniela_usuario'].count_documents({"usuario_id": usuario_oid, "estado": "PENDIENTE"}) > 0
    fase_actual = _fase_actual()

    puede_reclamar_beca = (
        usuario.get("monto", 0) == 0
        and not (tiene_selecciones or tiene_sedes or tiene_quinielas)
        and registro.get("last_bankruptcy_fase", _SIN_RECLAMO_PREVIO) != fase_actual
    )

    from services.trivia_service import MAX_SESIONES_TRIVIA_DIA
    sesiones_trivia_hoy = db['trivia_history'].count_documents({"user_id": usuario_oid, "session_date": hoy_str})

    return {
        "ya_reclamo_checkin_hoy": ya_reclamo_checkin_hoy,
        "racha_actual": racha_actual,
        "dias_para_bono_especial": dias_para_bono_especial,
        "puede_reclamar_beca_emergencia": puede_reclamar_beca,
        "trivia_sesiones_hoy": sesiones_trivia_hoy,
        "trivia_sesiones_restantes": max(0, MAX_SESIONES_TRIVIA_DIA - sesiones_trivia_hoy),
        "puede_jugar_trivia": sesiones_trivia_hoy < MAX_SESIONES_TRIVIA_DIA
    }


# ==========================================
# Vista /misiones (encabezado, checklist del día, racha, trivia, beca e historial)
# ==========================================
# Misiones del día: acciones con XP que se pueden hacer a diario (reglas en config/niveles.py). 'meta' = cuántas
# veces cuenta por día para tildarla; 'url' a dónde se hace. Se muestran solo las del rol (permiso = REGLAS_XP.modulo).
MISIONES_DEL_DIA = [
    {"accion": "CHECKIN",    "titulo": "Hacer el check-in",          "meta": 1, "url": "#checkin"},
    {"accion": "TRIVIA",     "titulo": "Jugar las 3 trivias",        "meta": 3, "url": "#trivia"},
    {"accion": "QUINIELA",   "titulo": "Comprar un boleto de quiniela", "meta": 1, "url": "/quinielas/"},
    {"accion": "ONCE_IDEAL", "titulo": "Ajustar tu Once Ideal",      "meta": 1, "url": "/once-ideal/"},
    {"accion": "SOBRE",      "titulo": "Abrir un sobre",             "meta": 1, "url": "/album-estampas/sobres"},
    {"accion": "JUEGO_VIVO", "titulo": "Jugar un partido en vivo",   "meta": 1, "url": "/juegos/"},
    {"accion": "ASISTENTE",  "titulo": "Consultar al Profe",         "meta": 1, "url": "/asistente/"},
]


def obtener_misiones_vista(user_id: str, permisos: Optional[set] = None) -> Dict[str, Any]:
    from config.niveles import REGLAS_XP, XP_TRIVIA_BASE, XP_TRIVIA_POR_ACIERTO
    from services.trivia_service import MAX_SESIONES_TRIVIA_DIA, PREGUNTAS_POR_SESION, PUNTOS_POR_RESPUESTA_CORRECTA

    usuario_oid = ObjectId(user_id)
    estado = obtener_daily_status(user_id)
    usuario = db['usuarios'].find_one({"_id": usuario_oid}, {"monto": 1}) or {}
    hoy = date.today()
    hoy_str, ayer_str = hoy.isoformat(), (hoy - timedelta(days=1)).isoformat()
    registro = db['user_daily_rewards'].find_one({"user_id": usuario_oid}) or {}

    # Racha vigente: la guardada se "corta" si el último check-in no fue hoy ni ayer. Si hoy cerró la racha de 5,
    # el contador ya volvió a 0, pero hoy se muestra completa.
    ultimo = registro.get("last_checkin_date")
    racha = registro.get("consecutive_days", 0) if ultimo in (hoy_str, ayer_str) else 0
    cerro_hoy = ultimo == hoy_str and racha == 0 and registro.get("total_checkins", 0) > 0
    dias_marcados = DIAS_RACHA_BONO_ESPECIAL if cerro_hoy else racha
    proximo_dia = None if estado["ya_reclamo_checkin_hoy"] else racha + 1
    bono_hoy = BONO_CHECKIN_DIARIO + (BONO_RACHA_ESPECIAL if proximo_dia == DIAS_RACHA_BONO_ESPECIAL else 0)
    checkin = {
        "racha": racha, "dias_marcados": dias_marcados, "proximo_dia": proximo_dia, "cerro_hoy": cerro_hoy,
        "bono_hoy": bono_hoy, "total": registro.get("total_checkins", 0), "dias_bono": DIAS_RACHA_BONO_ESPECIAL,
        "bono_diario": BONO_CHECKIN_DIARIO, "bono_especial": BONO_RACHA_ESPECIAL,
        "dias": [{"n": d, "hecho": d <= dias_marcados, "hoy": d == proximo_dia or (estado["ya_reclamo_checkin_hoy"] and d == dias_marcados),
                  "premio": BONO_CHECKIN_DIARIO + (BONO_RACHA_ESPECIAL if d == DIAS_RACHA_BONO_ESPECIAL else 0)}
                 for d in range(1, DIAS_RACHA_BONO_ESPECIAL + 1)],
    }

    # Trivia: las sesiones de hoy (las abandonadas también gastan cupo) y el historial completo
    sesiones_hoy = [{"aciertos": s.get("correct_answers"), "puntos": s.get("points_rewarded", 0),
                     "completada": s.get("estado") == "COMPLETADA"}
                    for s in db['trivia_history'].find({"user_id": usuario_oid, "session_date": hoy_str},
                                                       {"correct_answers": 1, "points_rewarded": 1, "estado": 1}).sort("created_at", 1)]
    agg = list(db['trivia_history'].aggregate([
        {"$match": {"user_id": usuario_oid, "estado": "COMPLETADA"}},
        {"$group": {"_id": None, "sesiones": {"$sum": 1}, "aciertos": {"$sum": "$correct_answers"},
                    "preguntas": {"$sum": "$questions_asked"}, "puntos": {"$sum": "$points_rewarded"},
                    "perfectas": {"$sum": {"$cond": [{"$eq": ["$correct_answers", "$questions_asked"]}, 1, 0]}}}}]))
    t = agg[0] if agg else {"sesiones": 0, "aciertos": 0, "preguntas": 0, "puntos": 0, "perfectas": 0}
    trivia = {
        "slots": [sesiones_hoy[i] if i < len(sesiones_hoy) else None for i in range(MAX_SESIONES_TRIVIA_DIA)],
        "restantes": estado["trivia_sesiones_restantes"], "maximo": MAX_SESIONES_TRIVIA_DIA,
        "preguntas_por_sesion": PREGUNTAS_POR_SESION, "puntos_por_acierto": PUNTOS_POR_RESPUESTA_CORRECTA,
        "xp_base": XP_TRIVIA_BASE, "xp_por_acierto": XP_TRIVIA_POR_ACIERTO,
        "sesiones": t["sesiones"], "puntos": t["puntos"], "perfectas": t["perfectas"],
        "precision": round(t["aciertos"] * 100 / t["preguntas"]) if t["preguntas"] else None,
        "puntos_hoy": sum(s["puntos"] or 0 for s in sesiones_hoy),
    }

    # Beca: cada requisito por separado, para mostrar cuál falta
    fase_actual = _fase_actual()
    requisitos = [
        {"texto": "Saldo en 0", "ok": usuario.get("monto", 0) == 0},
        {"texto": "Sin selecciones ni sedes activas",
         "ok": not (db['team_ownerships'].count_documents({"user_id": usuario_oid, "status": "ACTIVO"}, limit=1)
                    or db['city_ownerships'].count_documents({"user_id": usuario_oid, "status": "ACTIVO"}, limit=1))},
        {"texto": "Sin quinielas pendientes",
         "ok": not db['quiniela_usuario'].count_documents({"usuario_id": usuario_oid, "estado": "PENDIENTE"}, limit=1)},
        {"texto": "No la pediste en esta fase", "ok": registro.get("last_bankruptcy_fase", _SIN_RECLAMO_PREVIO) != fase_actual},
    ]
    beca = {"monto": MONTO_BECA_EMERGENCIA, "requisitos": requisitos, "disponible": estado["puede_reclamar_beca_emergencia"]}

    # Misiones del día (XP de hoy por acción) — mismo conteo que niveles_service.obtener_progreso
    usos: Dict[str, int] = {}
    xp_hoy = 0
    for ev in db['xp_eventos'].find({"user_id": usuario_oid, "fecha": hoy_str}, {"accion": 1, "xp": 1}):
        usos[ev["accion"]] = usos.get(ev["accion"], 0) + 1
        xp_hoy += ev.get("xp", 0)
    misiones = []
    for m in MISIONES_DEL_DIA:
        regla = REGLAS_XP.get(m["accion"], {})
        if permisos is not None and regla.get("modulo") not in permisos:
            continue
        hechas = min(usos.get(m["accion"], 0), m["meta"])
        if m["accion"] == "TRIVIA":   # una sesión abandonada no da XP pero gasta el cupo: cuenta como jugada
            hechas = min(len(sesiones_hoy), m["meta"])
        xp = regla.get("xp")
        misiones.append({**m, "hechas": hechas, "completa": hechas >= m["meta"], "icono": regla.get("icono", "bi-star"),
                         "xp_texto": f"+{xp} XP" if xp else f"+{XP_TRIVIA_BASE}-{XP_TRIVIA_BASE + XP_TRIVIA_POR_ACIERTO * PREGUNTAS_POR_SESION} XP c/u"})

    # Últimos premios: check-ins, beca y trivias completadas
    premios = [{"fecha": r["created_at"], "monto": r.get("amount_points", 0),
                "texto": {"CHECKIN": "Check-in diario", "CHECKIN_ESPECIAL": "Check-in + bono de racha",
                          "BECA_EMERGENCIA": "Beca de emergencia"}.get(r.get("type"), r.get("type")),
                "tipo": (r.get("type") or "").lower()}
               for r in db['reward_transactions'].find({"user_id": usuario_oid}).sort("created_at", -1).limit(10)]
    premios += [{"fecha": s.get("completed_at") or s["created_at"], "monto": s.get("points_rewarded", 0), "tipo": "trivia",
                 "texto": f"Trivia: {s.get('correct_answers', 0)}/{s.get('questions_asked', PREGUNTAS_POR_SESION)} aciertos"}
                for s in db['trivia_history'].find({"user_id": usuario_oid, "estado": "COMPLETADA"}).sort("created_at", -1).limit(10)]
    premios.sort(key=lambda p: p["fecha"], reverse=True)

    puntos_hoy = sum(r.get("amount_points", 0) for r in db['reward_transactions'].find(
        {"user_id": usuario_oid, "created_at": {"$gte": datetime.combine(hoy, datetime.min.time())}}, {"amount_points": 1}))
    manana = datetime.combine(hoy + timedelta(days=1), datetime.min.time())
    return {
        "estado": estado, "checkin": checkin, "trivia": trivia, "beca": beca, "misiones": misiones,
        "completas": sum(1 for m in misiones if m["completa"]), "premios": premios[:10],
        "puntos_hoy": puntos_hoy + trivia["puntos_hoy"], "xp_hoy": xp_hoy,
        "segundos_reinicio": int((manana - datetime.now()).total_seconds()), "fecha": hoy,
    }
