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
        raise ValueError("Solo podés reclamar la Beca de Emergencia si tu saldo es 0")

    tiene_selecciones = db['team_ownerships'].count_documents({"user_id": usuario_oid, "status": "ACTIVO"}) > 0
    tiene_sedes = db['city_ownerships'].count_documents({"user_id": usuario_oid, "status": "ACTIVO"}) > 0
    tiene_quinielas = db['quiniela_usuario'].count_documents({"usuario_id": usuario_oid, "estado": "PENDIENTE"}) > 0

    if tiene_selecciones or tiene_sedes or tiene_quinielas:
        raise ValueError("No podés reclamar la Beca de Emergencia mientras tengas inversiones o quinielas activas")

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
