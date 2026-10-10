"""
Juego en Vivo (routes/juego_en_vivo_route.py): el usuario elige una de las dos selecciones de un
partido pendiente, paga una entrada de usuarios.monto y recibe una cuota de puntos; durante la
"Simulación en Vivo" (services/live_match_service.py) cada evento revelado suma o resta puntos
según el país elegido y el multiplicador de riesgo, y al terminar los puntos finales vuelven a
usuarios.monto.

Cómo encaja con la transmisión: no hay WebSockets/SSE ni tareas en segundo plano, y los eventos
NO se escriben de a uno en Mongo (el partido entero ya está en juegos.resultado.eventos; solo se
"revelan" con el reloj) -- por eso tampoco sirven los Change Streams. Los puntos se procesan
"al leer": cada GET del estado (polling de /en-vivo/) procesa los eventos revelados desde el
último procesado. Como el instante de revelación de cada evento es fijo
(live_match_service.instante_revelacion_evento), el resultado es el mismo sin importar cuándo ni
cuántas veces se consulte.

Consistencia: cada lote de eventos se aplica en una transacción de Mongo (Atlas = replica set)
que actualiza la sesión con un compare-and-set sobre 'ultimo_evento_procesado' e inserta las
transacciones de puntos; el índice único (sesion_id, evento_idx, regla_codigo) de
'point_transactions' es la segunda barrera contra procesar un evento dos veces (ver
configurar_juego_en_vivo.py). La lógica de "cuántos puntos vale qué" está en
services/juego_en_vivo_puntos.py (pura, sin Mongo).

Colecciones: match_live_sessions, point_transactions, event_point_rules.
"""
import certifi
import copy
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError
from pymongo.mongo_client import MongoClient

from config import juego_en_vivo as cfg
from config.settings import MONGODB_URI
from services import juego_en_vivo_puntos as puntos
from services.juegos_service import obtener_juego_activo
from services.live_match_service import (
    DURACION_TRANSMISION_SEGUNDOS, TRANSMISION_EN_CURSO, _match_en_progreso,
    calcular_estado_transmision, instante_revelacion_evento,
)

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

COLECCION_SESIONES = "match_live_sessions"
COLECCION_TRANSACCIONES = "point_transactions"
COLECCION_REGLAS = "event_point_rules"

ESTADO_PENDIENTE = "pendiente"      # eligió país, el partido todavía no empezó
ESTADO_EN_CURSO = "en_curso"        # transmisión en curso
ESTADO_ELIMINADA = "eliminada"      # llegó a 0 puntos: sigue mirando, no suma ni resta
ESTADO_FINALIZADA = "finalizada"    # partido terminado, puntos acreditados a usuarios.monto
ESTADO_CANCELADA = "cancelada"      # el partido se simuló sin transmisión en vivo: se reembolsó

MOVIMIENTO_ENTRADA = "ENTRADA"
MOVIMIENTO_EVENTO = "EVENTO"
MOVIMIENTO_PAGO_FINAL = "PAGO_FINAL"
MOVIMIENTO_REEMBOLSO = "REEMBOLSO"


class JuegoEnVivoError(Exception):
    """Error de validación del juego; la ruta lo traduce a HTTP con 'status_code'."""
    def __init__(self, mensaje: str, status_code: int = 400):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status_code = status_code


class _LoteYaProcesado(Exception):
    """Otro request procesó este lote primero (falló el compare-and-set): se aborta la transacción."""


# ==========================================
# Helpers
# ==========================================
def _oid(valor: Any, que: str = "ID") -> ObjectId:
    try:
        return valor if isinstance(valor, ObjectId) else ObjectId(str(valor))
    except (InvalidId, TypeError):
        raise JuegoEnVivoError(f"{que} inválido.", 400)


def _multiplicador_valido(valor: Any) -> float:
    try:
        return puntos.normalizar_multiplicador(valor)
    except ValueError as e:
        raise JuegoEnVivoError(str(e), 400)


def _cargar_reglas() -> List[Dict[str, Any]]:
    """Reglas activas desde 'event_point_rules'; si la colección está vacía (no se corrió
    configurar_juego_en_vivo.py), los valores por defecto de config/juego_en_vivo.py."""
    reglas = list(db[COLECCION_REGLAS].find({}, {"_id": 0}))
    return reglas or copy.deepcopy(cfg.REGLAS_PUNTOS_DEFAULT)


def _poder_equipos(juego: dict, ids_paises: List[int]) -> Dict[int, float]:
    """'estadisticas.poder' de cada país en el Mundial del partido ('internacional'), con
    'paises' como respaldo -- la misma referencia de favoritismo que usa el scouter
    (prematch_service)."""
    poder = {}
    mundial_id = juego.get("mundial_id")
    for d in db["internacional"].find({"id": {"$in": ids_paises}, "mundial_id": mundial_id}, {"id": 1, "estadisticas.poder": 1}):
        poder[d["id"]] = (d.get("estadisticas") or {}).get("poder", 0.0) or 0.0
    faltantes = [i for i in ids_paises if i not in poder]
    if faltantes:
        for d in db["paises"].find({"id": {"$in": faltantes}}, {"id": 1, "estadisticas.poder": 1}):
            poder[d["id"]] = (d.get("estadisticas") or {}).get("poder", 0.0) or 0.0
    return poder


def _lado_y_nombres(juego: dict, pais_id: int) -> Dict[str, Any]:
    local = juego.get("equipo_local") or {}
    visitante = juego.get("equipo_visitante") or {}
    if pais_id == local.get("id"):
        return {"lado": "L", "pais": local, "rival": visitante}
    if pais_id == visitante.get("id"):
        return {"lado": "V", "pais": visitante, "rival": local}
    raise JuegoEnVivoError("El país elegido no juega este partido.", 400)


def _esta_disponible_para_elegir(juego: dict) -> bool:
    return juego.get("estado") == "creado" and not juego.get("transmision")


def _iso(valor: Any) -> Any:
    return valor.isoformat() + "Z" if isinstance(valor, datetime) else valor


def _ejecutar_en_transaccion(funcion) -> Any:
    with client.start_session() as sesion_mongo:
        return sesion_mongo.with_transaction(funcion)


# ==========================================
# Cuotas
# ==========================================
def calcular_cuotas(juego: dict) -> Dict[str, Any]:
    local = juego.get("equipo_local") or {}
    visitante = juego.get("equipo_visitante") or {}
    poder = _poder_equipos(juego, [local.get("id"), visitante.get("id")])
    prob_local = puntos.probabilidad_victoria(poder.get(local.get("id"), 0.0), poder.get(visitante.get("id"), 0.0))

    def _lado(equipo: dict, probabilidad: float) -> dict:
        categoria, cuota = puntos.categoria_y_cuota(probabilidad)
        return {
            "pais_id": equipo.get("id"), "nombre": equipo.get("nombre", "?"), "bandera": equipo.get("bandera") or "",
            "siglas": equipo.get("siglas") or "", "probabilidad_pct": round(probabilidad, 1),
            "categoria": categoria, "cuota": cuota, "poder": round(poder.get(equipo.get("id"), 0.0), 1),
        }

    return {"local": _lado(local, prob_local), "visitante": _lado(visitante, 100.0 - prob_local)}


def obtener_cuotas_partido(usuario: dict, juego_id: Optional[str] = None) -> Dict[str, Any]:
    """Cuotas de ambos lados + entrada + saldo del usuario + su sesión si ya eligió. Sin
    'juego_id': el próximo partido que va a tomar "Simular siguiente" (obtener_juego_activo)."""
    if juego_id:
        juego = db["juegos"].find_one({"_id": _oid(juego_id, "Partido")})
    else:
        juego, _ = obtener_juego_activo()
    if not juego:
        raise JuegoEnVivoError("No se encontró el partido.", 404)

    usuario_doc = db["usuarios"].find_one({"_id": _oid(usuario["_id"])}, {"monto": 1}) or {}
    sesion = db[COLECCION_SESIONES].find_one({"usuario_id": _oid(usuario["_id"]), "juego_id": juego["_id"]})
    return {
        "juego_id": str(juego["_id"]),
        "fecha": juego.get("fecha"), "hora": juego.get("hora"), "grupo": juego.get("grupo"),
        "disponible": _esta_disponible_para_elegir(juego),
        "entrada": cfg.ENTRADA_MONTO,
        "monto_usuario": usuario_doc.get("monto", 0),
        "niveles_riesgo": _niveles_riesgo(),
        "sesion": _serializar_sesion_resumida(sesion) if sesion else None,
        **calcular_cuotas(juego),
    }


def _niveles_riesgo() -> List[Dict[str, Any]]:
    return [{"multiplicador": m, "nombre": n} for m, n in cfg.NIVELES_RIESGO.items()]


# ==========================================
# Sesiones: elegir país, cancelar, cambiar riesgo
# ==========================================
def crear_sesion(usuario: dict, juego_id: str, pais_id: int, multiplicador: Any = None) -> Dict[str, Any]:
    """
    Elige país para un partido pendiente: descuenta la entrada de usuarios.monto (condicional,
    nunca deja saldo negativo), crea la sesión y registra la transacción ENTRADA, todo en una
    transacción de Mongo.
    """
    usuario_oid = _oid(usuario["_id"])
    juego = db["juegos"].find_one({"_id": _oid(juego_id, "Partido")})
    if not juego:
        raise JuegoEnVivoError("No se encontró el partido.", 404)
    if not _esta_disponible_para_elegir(juego):
        raise JuegoEnVivoError("Este partido ya empezó o ya se jugó: solo puedes verlo como espectador.", 409)
    try:
        pais_id = int(pais_id)
    except (TypeError, ValueError):
        raise JuegoEnVivoError("País inválido.", 400)
    lados = _lado_y_nombres(juego, pais_id)
    multiplicador = _multiplicador_valido(multiplicador if multiplicador is not None else cfg.MULTIPLICADOR_INICIAL)

    if db[COLECCION_SESIONES].find_one({"usuario_id": usuario_oid, "juego_id": juego["_id"]}):
        raise JuegoEnVivoError("Ya elegiste país para este partido. Cancélalo primero si quieres cambiarlo.", 409)

    cuotas = calcular_cuotas(juego)
    datos_lado = cuotas["local"] if lados["lado"] == "L" else cuotas["visitante"]
    ahora = datetime.utcnow()
    mundial = db["mundiales"].find_one({"activo": True}, {"_id": 1})
    sesion_doc = {
        "usuario_id": usuario_oid,
        "juego_id": juego["_id"],
        "mundial_id": juego.get("mundial_id") or (str(mundial["_id"]) if mundial else None),
        "pais_id": pais_id,
        "pais_nombre": lados["pais"].get("nombre"),
        "pais_bandera": lados["pais"].get("bandera") or "",
        "rival_id": lados["rival"].get("id"),
        "rival_nombre": lados["rival"].get("nombre"),
        "lado": lados["lado"],
        "probabilidad_pct": datos_lado["probabilidad_pct"],
        "categoria_cuota": datos_lado["categoria"],
        "entrada_monto": cfg.ENTRADA_MONTO,
        "puntos_iniciales": datos_lado["cuota"],
        "puntos_actuales": datos_lado["cuota"],
        "multiplicador_historial": [puntos.nuevo_cambio_riesgo(multiplicador, ahora, en_transmision=False)],
        "multiplicador_maximo": multiplicador,
        "ultimo_cambio_en": None,
        "ultimo_evento_procesado": -1,
        "estado": ESTADO_PENDIENTE,
        "monto_acreditado": None,
        "resumen": None,
        "creado_en": ahora,
        "actualizado_en": ahora,
    }

    def _tx(s):
        cobro = db["usuarios"].update_one(
            {"_id": usuario_oid, "monto": {"$gte": cfg.ENTRADA_MONTO}},
            {"$inc": {"monto": -cfg.ENTRADA_MONTO}}, session=s
        )
        if cobro.modified_count == 0:
            raise JuegoEnVivoError(f"Saldo insuficiente: la entrada cuesta {cfg.ENTRADA_MONTO} puntos.", 400)
        sesion_id = db[COLECCION_SESIONES].insert_one(sesion_doc, session=s).inserted_id
        db[COLECCION_TRANSACCIONES].insert_one(_transaccion_monto(
            sesion_id, usuario_oid, juego["_id"], MOVIMIENTO_ENTRADA, -cfg.ENTRADA_MONTO,
            f"Entrada Juego en Vivo: {lados['pais'].get('nombre')} vs {lados['rival'].get('nombre')}", ahora
        ), session=s)
        return sesion_id

    try:
        _ejecutar_en_transaccion(_tx)
    except DuplicateKeyError:
        raise JuegoEnVivoError("Ya elegiste país para este partido.", 409)
    return obtener_cuotas_partido(usuario, str(juego["_id"]))


def cancelar_sesion(usuario: dict, juego_id: str) -> Dict[str, Any]:
    """Antes de que empiece el partido: borra la sesión y reembolsa la entrada (las
    transacciones ENTRADA/REEMBOLSO quedan como historial). "Cambiar de país" = cancelar + elegir."""
    usuario_oid = _oid(usuario["_id"])
    juego_oid = _oid(juego_id, "Partido")
    sesion = db[COLECCION_SESIONES].find_one({"usuario_id": usuario_oid, "juego_id": juego_oid})
    if not sesion:
        raise JuegoEnVivoError("No tienes una elección para este partido.", 404)
    juego = db["juegos"].find_one({"_id": juego_oid}) or {}
    if sesion["estado"] != ESTADO_PENDIENTE or not _esta_disponible_para_elegir(juego):
        raise JuegoEnVivoError("El partido ya empezó: ya no se puede cancelar.", 409)
    _reembolsar(sesion, "Cancelación Juego en Vivo", borrar_sesion=True)
    return obtener_cuotas_partido(usuario, juego_id)


def _reembolsar(sesion: dict, descripcion: str, borrar_sesion: bool) -> bool:
    """Devuelve la entrada. Atómico: solo el request que gana el cambio de estado reembolsa."""
    ahora = datetime.utcnow()

    def _tx(s):
        filtro = {"_id": sesion["_id"], "estado": ESTADO_PENDIENTE}
        if borrar_sesion:
            hecho = db[COLECCION_SESIONES].delete_one(filtro, session=s).deleted_count
        else:
            hecho = db[COLECCION_SESIONES].update_one(
                filtro, {"$set": {"estado": ESTADO_CANCELADA, "monto_acreditado": sesion["entrada_monto"], "actualizado_en": ahora}}, session=s
            ).modified_count
        if not hecho:
            return False
        db["usuarios"].update_one({"_id": sesion["usuario_id"]}, {"$inc": {"monto": sesion["entrada_monto"]}}, session=s)
        db[COLECCION_TRANSACCIONES].insert_one(_transaccion_monto(
            sesion["_id"], sesion["usuario_id"], sesion["juego_id"], MOVIMIENTO_REEMBOLSO, sesion["entrada_monto"], descripcion, ahora
        ), session=s)
        return True

    return _ejecutar_en_transaccion(_tx)


def cambiar_multiplicador(usuario: dict, juego_id: str, multiplicador: Any) -> Dict[str, Any]:
    """
    Cambia el nivel de riesgo. Antes del partido: libre e inmediato. Durante la transmisión:
    sujeto al cooldown (ver juego_en_vivo_puntos.estado_cambio_riesgo) y con efecto recién
    DEMORA_ACTIVACION_SEGUNDOS después -- nunca aplica a eventos ya revelados.
    """
    multiplicador = _multiplicador_valido(multiplicador)
    usuario_oid = _oid(usuario["_id"])
    juego_oid = _oid(juego_id, "Partido")
    sesion = db[COLECCION_SESIONES].find_one({"usuario_id": usuario_oid, "juego_id": juego_oid})
    if not sesion:
        raise JuegoEnVivoError("No elegiste país para este partido (modo espectador).", 404)
    juego = db["juegos"].find_one({"_id": juego_oid})
    sesion = procesar_sesion(sesion, juego)  # deja el saldo/estado al día antes de validar
    if sesion["estado"] not in (ESTADO_PENDIENTE, ESTADO_EN_CURSO):
        raise JuegoEnVivoError("Tu partida ya terminó: no puedes cambiar el riesgo.", 409)

    ahora = datetime.utcnow()
    en_transmision = _en_transmision(juego, ahora)
    if not en_transmision and juego.get("transmision"):
        raise JuegoEnVivoError("El partido ya terminó.", 409)

    ultimo_pedido = sesion["multiplicador_historial"][-1]["multiplicador"] if sesion["multiplicador_historial"] else None
    if ultimo_pedido == multiplicador:
        raise JuegoEnVivoError(f"Tu riesgo ya es x{multiplicador:g}.", 400)

    if en_transmision:
        eventos_visibles, instantes = _eventos_visibles_con_instantes(juego, ahora)
        estado = puntos.estado_cambio_riesgo(sesion.get("ultimo_cambio_en"), eventos_visibles, instantes, ahora, True)
        if not estado["puede_cambiar"]:
            raise JuegoEnVivoError(f"Podrás cambiar el riesgo en {estado['segundos_restantes']} s (o después de un gol).", 429)
        cambio = puntos.nuevo_cambio_riesgo(multiplicador, ahora, en_transmision=True)
        # Compare-and-set sobre 'ultimo_cambio_en': dos clicks simultáneos no pasan los dos el cooldown.
        actualizado = db[COLECCION_SESIONES].update_one(
            {"_id": sesion["_id"], "ultimo_cambio_en": sesion.get("ultimo_cambio_en"), "estado": ESTADO_EN_CURSO},
            {"$push": {"multiplicador_historial": cambio},
             "$set": {"ultimo_cambio_en": ahora, "actualizado_en": ahora},
             "$max": {"multiplicador_maximo": multiplicador}}
        )
    else:
        # Antes del partido no hay eventos que proteger: el historial se reemplaza (efecto inmediato)
        actualizado = db[COLECCION_SESIONES].update_one(
            {"_id": sesion["_id"], "estado": ESTADO_PENDIENTE},
            {"$set": {"multiplicador_historial": [puntos.nuevo_cambio_riesgo(multiplicador, ahora, False)],
                      "multiplicador_maximo": multiplicador, "actualizado_en": ahora}}
        )
    if actualizado.modified_count == 0:
        raise JuegoEnVivoError("Tu partida cambió mientras tanto; vuelve a intentarlo.", 409)
    return obtener_estado_juego(usuario, juego_id)


# ==========================================
# Procesamiento de eventos ("al leer")
# ==========================================
def _en_transmision(juego: Optional[dict], ahora: datetime) -> bool:
    transmision = (juego or {}).get("transmision") or {}
    if transmision.get("estado") != TRANSMISION_EN_CURSO:
        return False
    duracion = transmision.get("duracion_segundos", DURACION_TRANSMISION_SEGUNDOS)
    return (ahora - transmision["started_at"]).total_seconds() < duracion


def _eventos_visibles_con_instantes(juego: dict, ahora: datetime):
    eventos = (juego.get("resultado") or {}).get("eventos", [])
    transmision = juego["transmision"]
    duracion = transmision.get("duracion_segundos", DURACION_TRANSMISION_SEGUNDOS)
    visibles = calcular_estado_transmision(eventos, transmision["started_at"], ahora, duracion)["eventos_visibles"]
    instantes = [instante_revelacion_evento(i, len(eventos), transmision["started_at"], duracion) for i in range(len(visibles))]
    return visibles, instantes


def procesar_sesion(sesion: dict, juego: Optional[dict], ahora: Optional[datetime] = None) -> dict:
    """
    Aplica a la sesión los eventos revelados desde el último procesado y, si la transmisión ya
    terminó, la finaliza (acredita los puntos a usuarios.monto). Idempotente y segura ante
    llamadas concurrentes: devuelve siempre la sesión vigente releída de Mongo.
    """
    ahora = ahora or datetime.utcnow()
    if sesion["estado"] in (ESTADO_FINALIZADA, ESTADO_CANCELADA) or not juego:
        return sesion

    transmision = juego.get("transmision")
    if not transmision:
        # Se jugó por el flujo manual (/simulador), sin transmisión en vivo: no hubo juego.
        if juego.get("estado") == "finalizado" and sesion["estado"] == ESTADO_PENDIENTE:
            _reembolsar(sesion, "Reembolso Juego en Vivo: el partido se simuló sin transmisión", borrar_sesion=False)
        return db[COLECCION_SESIONES].find_one({"_id": sesion["_id"]})

    resultado = juego.get("resultado") or {}
    eventos = resultado.get("eventos", [])
    total = len(eventos)
    duracion = transmision.get("duracion_segundos", DURACION_TRANSMISION_SEGUNDOS)
    estado_tx = calcular_estado_transmision(eventos, transmision["started_at"], ahora, duracion)
    visibles = len(estado_tx["eventos_visibles"])
    desde = sesion["ultimo_evento_procesado"] + 1

    if sesion["estado"] in (ESTADO_PENDIENTE, ESTADO_EN_CURSO) and visibles > desde:
        historial = sesion.get("multiplicador_historial") or []
        lote = puntos.procesar_eventos(
            eventos, desde, visibles, sesion["puntos_actuales"],
            sesion["pais_nombre"], sesion["rival_nombre"], sesion["pais_id"], _cargar_reglas(),
            # El multiplicador de cada evento es el que regía en su instante de REVELACIÓN
            lambda i: puntos.multiplicador_vigente(historial, instante_revelacion_evento(i, total, transmision["started_at"], duracion)),
            total, puntos.resultado_para_pais(resultado.get("ganador_lado"), sesion["lado"]),
        )
        nuevo_estado = ESTADO_ELIMINADA if lote["eliminado"] else ESTADO_EN_CURSO
        _guardar_lote(sesion, desde, visibles - 1, lote, nuevo_estado, ahora)
    elif sesion["estado"] == ESTADO_PENDIENTE:
        db[COLECCION_SESIONES].update_one(
            {"_id": sesion["_id"], "estado": ESTADO_PENDIENTE}, {"$set": {"estado": ESTADO_EN_CURSO, "actualizado_en": ahora}}
        )

    sesion = db[COLECCION_SESIONES].find_one({"_id": sesion["_id"]})
    termino = estado_tx["finalizado_por_tiempo"] or transmision.get("estado") != TRANSMISION_EN_CURSO
    procesado_todo = sesion["ultimo_evento_procesado"] >= total - 1 or sesion["estado"] == ESTADO_ELIMINADA
    if termino and procesado_todo and sesion["estado"] in (ESTADO_EN_CURSO, ESTADO_ELIMINADA, ESTADO_PENDIENTE):
        _finalizar(sesion, ahora)
        sesion = db[COLECCION_SESIONES].find_one({"_id": sesion["_id"]})
    return sesion


def _guardar_lote(sesion: dict, desde: int, hasta: int, lote: dict, nuevo_estado: str, ahora: datetime) -> None:
    """Sesión (compare-and-set sobre 'ultimo_evento_procesado') + transacciones, atómico."""
    docs = [{
        "sesion_id": sesion["_id"], "usuario_id": sesion["usuario_id"], "juego_id": sesion["juego_id"],
        "tipo_movimiento": MOVIMIENTO_EVENTO, **t, "creado_en": ahora,
    } for t in lote["transacciones"]]
    set_campos = {"puntos_actuales": lote["saldo"], "ultimo_evento_procesado": hasta, "estado": nuevo_estado, "actualizado_en": ahora}

    def _tx(s):
        actualizado = db[COLECCION_SESIONES].update_one(
            {"_id": sesion["_id"], "ultimo_evento_procesado": desde - 1, "estado": {"$in": [ESTADO_PENDIENTE, ESTADO_EN_CURSO]}},
            {"$set": set_campos}, session=s
        )
        if actualizado.modified_count == 0:
            raise _LoteYaProcesado()
        if docs:
            db[COLECCION_TRANSACCIONES].insert_many(docs, session=s)

    try:
        _ejecutar_en_transaccion(_tx)
    except (_LoteYaProcesado, DuplicateKeyError):
        pass  # otro poll concurrente ya lo procesó: la sesión se relee igual


def _finalizar(sesion: dict, ahora: datetime) -> None:
    """Una sola vez por sesión (flip atómico de 'estado'): resumen + pago de los puntos finales."""
    transacciones = list(db[COLECCION_TRANSACCIONES].find(
        {"sesion_id": sesion["_id"], "tipo_movimiento": MOVIMIENTO_EVENTO}, {"_id": 0}
    ))
    resumen = puntos.resumen_final(sesion, transacciones)
    pago = max(0, int(sesion["puntos_actuales"]))

    def _tx(s):
        flip = db[COLECCION_SESIONES].update_one(
            {"_id": sesion["_id"], "estado": {"$in": [ESTADO_PENDIENTE, ESTADO_EN_CURSO, ESTADO_ELIMINADA]}},
            {"$set": {"estado": ESTADO_FINALIZADA, "resumen": resumen, "monto_acreditado": pago, "finalizado_en": ahora, "actualizado_en": ahora}},
            session=s
        )
        if flip.modified_count == 0:
            return
        if pago > 0:
            db["usuarios"].update_one({"_id": sesion["usuario_id"]}, {"$inc": {"monto": pago}}, session=s)
        db[COLECCION_TRANSACCIONES].insert_one(_transaccion_monto(
            sesion["_id"], sesion["usuario_id"], sesion["juego_id"], MOVIMIENTO_PAGO_FINAL, pago,
            f"Pago Juego en Vivo: {sesion['pais_nombre']} vs {sesion['rival_nombre']}", ahora
        ), session=s)

    _ejecutar_en_transaccion(_tx)


def _transaccion_monto(sesion_id, usuario_id, juego_id, tipo: str, monto: int, descripcion: str, ahora: datetime) -> dict:
    """Movimiento de usuarios.monto (ENTRADA/PAGO_FINAL/REEMBOLSO). 'evento_idx' negativo y
    'regla_codigo' = tipo para que no choquen con el índice único de los eventos."""
    return {
        "sesion_id": sesion_id, "usuario_id": usuario_id, "juego_id": juego_id,
        "tipo_movimiento": tipo, "evento_idx": -1, "regla_codigo": tipo,
        "descripcion": descripcion, "puntos_netos": monto, "creado_en": ahora,
    }


# ==========================================
# Estado para el frontend, ranking
# ==========================================
def obtener_estado_juego(usuario: dict, juego_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Estado del juego para /en-vivo/ (se consulta en cada poll). Sin 'juego_id' usa el partido
    en transmisión. Procesa los eventos pendientes antes de responder.
    """
    if juego_id:
        juego = db["juegos"].find_one({"_id": _oid(juego_id, "Partido")})
    else:
        juego = _match_en_progreso()
    if not juego:
        return {"modo": "sin_partido"}

    sesion = db[COLECCION_SESIONES].find_one({"usuario_id": _oid(usuario["_id"]), "juego_id": juego["_id"]})
    if not sesion:
        return {"modo": "espectador", "juego_id": str(juego["_id"])}

    ahora = datetime.utcnow()
    sesion = procesar_sesion(sesion, juego, ahora)
    en_transmision = _en_transmision(juego, ahora)
    historial = sesion.get("multiplicador_historial") or []
    multiplicador_actual = puntos.multiplicador_vigente(historial, ahora)
    pendiente = next((c for c in reversed(historial) if c["efectivo_desde"] > ahora), None)

    if en_transmision:
        eventos_visibles, instantes = _eventos_visibles_con_instantes(juego, ahora)
        cambio = puntos.estado_cambio_riesgo(sesion.get("ultimo_cambio_en"), eventos_visibles, instantes, ahora, True)
    else:
        cambio = puntos.estado_cambio_riesgo(None, [], [], ahora, False)
    if sesion["estado"] not in (ESTADO_PENDIENTE, ESTADO_EN_CURSO):
        cambio = {"puede_cambiar": False, "segundos_restantes": 0, "liberado_por_gol": False}

    transacciones = list(db[COLECCION_TRANSACCIONES].find(
        {"sesion_id": sesion["_id"], "tipo_movimiento": MOVIMIENTO_EVENTO}, {"_id": 0, "sesion_id": 0, "usuario_id": 0, "juego_id": 0}
    ).sort([("evento_idx", 1), ("_id", 1)]))
    for t in transacciones:
        t["creado_en"] = _iso(t.get("creado_en"))

    respuesta = {
        "modo": "jugador",
        "juego_id": str(juego["_id"]),
        **_serializar_sesion_resumida(sesion),
        "en_transmision": en_transmision,
        "multiplicador_actual": multiplicador_actual,
        "multiplicador_pendiente": {
            "multiplicador": pendiente["multiplicador"],
            "segundos_para_activar": max(0, int((pendiente["efectivo_desde"] - ahora).total_seconds() + 0.999)),
        } if pendiente else None,
        "cooldown": cambio,
        "cooldown_total_segundos": cfg.COOLDOWN_RIESGO_SEGUNDOS,
        "niveles_riesgo": _niveles_riesgo(),
        "transacciones": transacciones,
        "resumen": None,
    }
    if sesion["estado"] == ESTADO_FINALIZADA:
        respuesta["resumen"] = {
            **(sesion.get("resumen") or {}),
            "monto_acreditado": sesion.get("monto_acreditado"),
            "ranking_partido": obtener_ranking(usuario, juego_id=str(juego["_id"])),
            "ranking_torneo": obtener_ranking(usuario, mundial_id=sesion.get("mundial_id")),
        }
    return respuesta


def _serializar_sesion_resumida(sesion: dict) -> Dict[str, Any]:
    historial = sesion.get("multiplicador_historial") or []
    return {
        "estado": sesion["estado"],
        "pais_id": sesion["pais_id"], "pais_nombre": sesion["pais_nombre"], "pais_bandera": sesion.get("pais_bandera", ""),
        "rival_nombre": sesion["rival_nombre"], "lado": sesion["lado"],
        "categoria_cuota": sesion["categoria_cuota"], "probabilidad_pct": sesion.get("probabilidad_pct"),
        "entrada_monto": sesion["entrada_monto"],
        "puntos_iniciales": sesion["puntos_iniciales"], "puntos_actuales": sesion["puntos_actuales"],
        "multiplicador_elegido": historial[-1]["multiplicador"] if historial else cfg.MULTIPLICADOR_INICIAL,
        "multiplicador_maximo": sesion.get("multiplicador_maximo", cfg.MULTIPLICADOR_INICIAL),
        "monto_acreditado": sesion.get("monto_acreditado"),
    }


def obtener_ranking(usuario: Optional[dict], juego_id: Optional[str] = None, mundial_id: Optional[str] = None, limite: int = 10) -> Dict[str, Any]:
    """
    Ranking de jugadores. Por partido: puntos finales (o actuales si sigue en curso). Por torneo
    (mundial_id): suma de (monto acreditado - entrada) de todas sus partidas finalizadas.
    """
    if juego_id:
        filas = [{
            "usuario_id": s["usuario_id"], "valor": s["puntos_actuales"], "pais_nombre": s["pais_nombre"],
        } for s in db[COLECCION_SESIONES].find(
            {"juego_id": _oid(juego_id, "Partido"), "estado": {"$in": [ESTADO_EN_CURSO, ESTADO_ELIMINADA, ESTADO_FINALIZADA]}},
            {"usuario_id": 1, "puntos_actuales": 1, "pais_nombre": 1}
        )]
        criterio = "puntos"
    else:
        filas = [{"usuario_id": d["_id"], "valor": d["neto"], "partidas": d["partidas"]} for d in db[COLECCION_SESIONES].aggregate([
            {"$match": {"mundial_id": mundial_id, "estado": ESTADO_FINALIZADA}},
            {"$group": {"_id": "$usuario_id", "neto": {"$sum": {"$subtract": ["$monto_acreditado", "$entrada_monto"]}}, "partidas": {"$sum": 1}}},
        ])]
        criterio = "neto"

    filas.sort(key=lambda f: f["valor"], reverse=True)
    nombres = {u["_id"]: u.get("username") or u.get("nombre") or "?" for u in db["usuarios"].find(
        {"_id": {"$in": [f["usuario_id"] for f in filas]}}, {"username": 1, "nombre": 1}
    )}
    usuario_oid = _oid(usuario["_id"]) if usuario else None
    posicion = None
    tabla = []
    for i, f in enumerate(filas):
        # Empates comparten posición (1 + cuántos tienen estrictamente más)
        pos = 1 + sum(1 for g in filas if g["valor"] > f["valor"])
        if f["usuario_id"] == usuario_oid:
            posicion = pos
        if i < limite:
            tabla.append({"posicion": pos, "usuario": nombres.get(f["usuario_id"], "?"), "valor": f["valor"],
                          "es_usuario_actual": f["usuario_id"] == usuario_oid,
                          **({"pais_nombre": f["pais_nombre"]} if "pais_nombre" in f else {"partidas": f["partidas"]})})
    return {"criterio": criterio, "posicion": posicion, "total": len(filas), "tabla": tabla}


def sesiones_pendientes_usuario(usuario: Optional[dict]) -> Dict[str, Dict[str, Any]]:
    """{juego_id: sesión resumida} de las elecciones pendientes del usuario (badges en /juegos)."""
    if not usuario:
        return {}
    return {
        str(s["juego_id"]): _serializar_sesion_resumida(s)
        for s in db[COLECCION_SESIONES].find({"usuario_id": _oid(usuario["_id"]), "estado": ESTADO_PENDIENTE})
    }
