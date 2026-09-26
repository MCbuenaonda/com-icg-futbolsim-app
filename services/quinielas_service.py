"""
Lógica de negocio del módulo de Quinielas: catálogo (quiniela_config), compra
de boletos (quiniela_usuario) y liquidación automática al finalizar partidos.

Mapeo con el resto del dominio:
- Un "partido no jugado" es un doc de 'juegos' con estado == "creado".
- El resultado de un partido (LOCAL/EMPATE/VISITA) se deriva del mismo
  'ganador_lado' ("L"/"V"/"E") que ya arma registrar_resultado_juego en
  juegos_service.py — no se recalcula goles acá, se reutiliza ese valor.
"""
import certifi
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

MAPA_GANADOR_LADO = {"L": "LOCAL", "V": "VISITA", "E": "EMPATE"}

ESTADO_SELECCION_PENDIENTE = "PENDIENTE"
ESTADO_SELECCION_ACERTADO = "ACERTADO"
ESTADO_SELECCION_FALLADO = "FALLADO"

ESTADO_BOLETO_PENDIENTE = "PENDIENTE"
ESTADO_BOLETO_GANADA = "GANADA"
ESTADO_BOLETO_PERDIDA = "PERDIDA"


# ==========================================
# Helpers de serialización (ObjectId -> str)
# ==========================================
def _serializar_config(config: dict) -> dict:
    config = dict(config)
    config["id"] = str(config.pop("_id"))
    return config


def _serializar_boleto(boleto: dict) -> dict:
    boleto = dict(boleto)
    boleto["id"] = str(boleto.pop("_id"))
    boleto["usuario_id"] = str(boleto["usuario_id"])
    boleto["quiniela_config_id"] = str(boleto["quiniela_config_id"])
    boleto["selecciones"] = [
        {**s, "juego_id": str(s["juego_id"])} for s in boleto.get("selecciones", [])
    ]
    return boleto


# ==========================================
# Catálogo de quinielas
# ==========================================
def obtener_configs_activas() -> List[dict]:
    configs = db['quiniela_config'].find({"activa": True})
    return [_serializar_config(c) for c in configs]


def obtener_config_por_id(config_id: str) -> Optional[dict]:
    config = db['quiniela_config'].find_one({"_id": ObjectId(config_id)})
    return config  # se devuelve crudo (con ObjectId) para uso interno del servicio


# ==========================================
# Compra de boleto
# ==========================================
def crear_boleto_quiniela(usuario_id: str, quiniela_config_id: str, selecciones: List[Dict[str, str]]) -> dict:
    """
    Valida y registra la compra de un boleto de quiniela:
    - La configuración debe existir y estar activa.
    - La cantidad de selecciones debe coincidir con config.cantidad_partidos.
    - Cada partido seleccionado debe existir y no haberse jugado todavía (estado == "creado").
    - El usuario debe tener saldo (monto) suficiente para cubrir el costo.

    Lanza ValueError con un mensaje descriptivo si alguna validación falla.
    """
    config = obtener_config_por_id(quiniela_config_id)
    if not config or not config.get("activa", False):
        raise ValueError("La quiniela seleccionada no existe o no está activa")

    if len(selecciones) != config["cantidad_partidos"]:
        raise ValueError(
            f"Esta quiniela requiere exactamente {config['cantidad_partidos']} selecciones "
            f"(se recibieron {len(selecciones)})"
        )

    usuario_oid = ObjectId(usuario_id)
    usuario = db['usuarios'].find_one({"_id": usuario_oid})
    if not usuario or not usuario.get("activo", True):
        raise ValueError("Usuario no encontrado o inactivo")

    costo = config["costo_puntos"]
    if usuario.get("monto", 0) < costo:
        raise ValueError("Saldo insuficiente para comprar esta quiniela")

    # Validar que cada partido exista y no se haya jugado todavía, y armar las
    # selecciones ya en el formato que se persiste en 'quiniela_usuario'
    selecciones_doc = []
    for seleccion in selecciones:
        juego_oid = ObjectId(seleccion["juego_id"])
        juego = db['juegos'].find_one({"_id": juego_oid}, {"estado": 1})
        if not juego:
            raise ValueError(f"El partido {seleccion['juego_id']} no existe")
        if juego.get("estado") != "creado":
            raise ValueError(f"El partido {seleccion['juego_id']} ya se jugó o no está disponible para pronóstico")

        selecciones_doc.append({
            "juego_id": juego_oid,
            "pronostico": seleccion["pronostico"],
            "estado": ESTADO_SELECCION_PENDIENTE,
            "resultado_real": None
        })

    # Descuento atómico del saldo: solo aplica si en este mismo momento el usuario
    # sigue teniendo saldo suficiente (evita saldo negativo por compras concurrentes)
    descuento = db['usuarios'].update_one(
        {"_id": usuario_oid, "monto": {"$gte": costo}},
        {"$inc": {"monto": -costo}}
    )
    if descuento.modified_count == 0:
        raise ValueError("Saldo insuficiente para comprar esta quiniela")

    boleto = {
        "usuario_id": usuario_oid,
        "quiniela_config_id": config["_id"],
        "costo_pagado": costo,
        "estado": ESTADO_BOLETO_PENDIENTE,
        "aciertos": 0,
        "premio_ganado": 0,
        "selecciones": selecciones_doc,
        "fecha_creacion": datetime.now(),
        "fecha_resolucion": None
    }

    resultado = db['quiniela_usuario'].insert_one(boleto)
    boleto["_id"] = resultado.inserted_id

    return _serializar_boleto(boleto)


def obtener_boletos_usuario(usuario_id: str) -> List[dict]:
    boletos = db['quiniela_usuario'].find(
        {"usuario_id": ObjectId(usuario_id)}
    ).sort("fecha_creacion", -1)
    return [_serializar_boleto(b) for b in boletos]


def contar_selecciones_pendientes_usuario(usuario_id: str) -> int:
    """
    Cuenta cuántos partidos le quedan por resolverse al usuario en TODAS sus
    quinielas PENDIENTES combinadas (suma de selecciones aún PENDIENTES).
    Se usa en simulador.html para el contador de "partidos restantes de la
    quiniela" y para habilitar el botón de comprar una nueva.
    """
    resultado = list(db['quiniela_usuario'].aggregate([
        {"$match": {"usuario_id": ObjectId(usuario_id), "estado": ESTADO_BOLETO_PENDIENTE}},
        {"$unwind": "$selecciones"},
        {"$match": {"selecciones.estado": ESTADO_SELECCION_PENDIENTE}},
        {"$count": "total"}
    ]))
    return resultado[0]["total"] if resultado else 0


# ==========================================
# Actualización automática al finalizar un partido
# ==========================================
def procesar_resultado_partido(juego_id: str, ganador_lado: str) -> None:
    """
    Se llama cada vez que un partido termina de simularse (ver routes/simular_route.py).
    Busca todas las quinielas PENDIENTES que incluyan ese partido, marca la
    selección correspondiente como ACERTADO/FALLADO, y liquida (calcula premio
    y acredita saldo) cualquier boleto que ya haya quedado con todas sus
    selecciones resueltas.
    """
    resultado_partido = MAPA_GANADOR_LADO.get(ganador_lado)
    if not resultado_partido:
        return

    juego_oid = ObjectId(juego_id) if not isinstance(juego_id, ObjectId) else juego_id

    boletos_afectados = db['quiniela_usuario'].find({
        "estado": ESTADO_BOLETO_PENDIENTE,
        "selecciones.juego_id": juego_oid
    })

    for boleto in boletos_afectados:
        selecciones_actualizadas = []
        for seleccion in boleto["selecciones"]:
            if seleccion["juego_id"] == juego_oid and seleccion["estado"] == ESTADO_SELECCION_PENDIENTE:
                acierto = seleccion["pronostico"] == resultado_partido
                seleccion = {
                    **seleccion,
                    "estado": ESTADO_SELECCION_ACERTADO if acierto else ESTADO_SELECCION_FALLADO,
                    "resultado_real": resultado_partido
                }
            selecciones_actualizadas.append(seleccion)

        db['quiniela_usuario'].update_one(
            {"_id": boleto["_id"]},
            {"$set": {"selecciones": selecciones_actualizadas}}
        )

        # Si ya no queda ninguna selección pendiente, la quiniela está lista para liquidarse
        if all(s["estado"] != ESTADO_SELECCION_PENDIENTE for s in selecciones_actualizadas):
            _liquidar_boleto(boleto["_id"], selecciones_actualizadas)


def _liquidar_boleto(boleto_id: ObjectId, selecciones: List[dict]) -> None:
    """Calcula aciertos/premio de un boleto ya resuelto, actualiza su estado y acredita el saldo."""
    boleto = db['quiniela_usuario'].find_one({"_id": boleto_id})
    if not boleto or boleto["estado"] != ESTADO_BOLETO_PENDIENTE:
        return  # ya liquidado (protege contra procesamiento duplicado)

    config = db['quiniela_config'].find_one({"_id": boleto["quiniela_config_id"]})
    aciertos = sum(1 for s in selecciones if s["estado"] == ESTADO_SELECCION_ACERTADO)

    premio = 0
    if config:
        # Reglas ordenadas de mayor a menor exigencia: aplica la primera que se cumpla
        reglas_ordenadas = sorted(
            config.get("reglas_premio", []),
            key=lambda r: r["aciertos_requeridos"],
            reverse=True
        )
        for regla in reglas_ordenadas:
            if aciertos >= regla["aciertos_requeridos"]:
                premio = regla["premio_puntos"]
                break

    estado_final = ESTADO_BOLETO_GANADA if premio > 0 else ESTADO_BOLETO_PERDIDA

    db['quiniela_usuario'].update_one(
        {"_id": boleto_id},
        {"$set": {
            "aciertos": aciertos,
            "premio_ganado": premio,
            "estado": estado_final,
            "fecha_resolucion": datetime.now()
        }}
    )

    if premio > 0:
        db['usuarios'].update_one(
            {"_id": boleto["usuario_id"]},
            {"$inc": {"monto": premio}}
        )
