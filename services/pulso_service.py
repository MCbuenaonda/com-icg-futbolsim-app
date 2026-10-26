"""
El pulso: el torneo avanza solo en el SERVIDOR, sin depender de que haya un navegador abierto.

Cloud Scheduler llama cada minuto a POST /tareas/pulso (routes/tareas_route.py, protegida con PULSO_CLAVE). En local,
con PULSO_LOCAL=1, la propia app da el pulso cada 30 s (iniciar_pulso_local). Y los navegadores de los admins también
lo dan como respaldo (POST /matches/pulso/tick) mientras están abiertos. Da igual quién lo dé: cada pulso hace lo mismo
y respeta el mismo horario, así que no hay partidos duplicados ni adelantados.

En cada pulso (pulsar):
  1. Cierra la transmisión que terminó (live_match_service.obtener_estado_live: aplica los efectos diferidos una vez).
  2. Si la reproducción automática está prendida, no hay partido en curso y ya llegó la hora, arranca el siguiente
     (live_match_service.iniciar_simulacion_automatica, el mismo camino que el botón).
  3. En Cloud Run y solo desde el Scheduler: recalcula las probabilidades si quedaron viejas (allí un proceso aparte
     se queda sin CPU entre pedidos; aquí se hace dentro del pedido, ~45 s).

Horario: los partidos arrancan en una grilla fija — el siguiente a la hora de inicio del anterior + el ritmo
(intervalo_min, 30 por defecto) —, nunca antes de que termine la transmisión anterior (+ MARGEN). Si la reproducción
estuvo apagada y la hora ya pasó, arranca en el próximo pulso y la grilla sigue desde ahí.

Mongo: colección 'pulso' con dos documentos: 'config' {activo, intervalo_min, actualizado_por, actualizado_en} y
'estado' {candado_hasta, candado_token, ultimo_pulso, fuente, accion, detalle, proximo_inicio, ultimo_error, ...}.
El candado evita que dos pulsos (Scheduler, hilo local, navegadores) trabajen a la vez. Es PERMANENTE.
"""
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from pymongo.errors import DuplicateKeyError

from config.settings import EN_CLOUD_RUN, PULSO_INTERVALO_MIN
from services.live_match_service import (DURACION_TRANSMISION_SEGUNDOS, TRANSMISION_EN_CURSO, db, iniciar_simulacion_automatica,
                                         obtener_estado_live)

COLECCION = "pulso"
MARGEN_SEGUNDOS = 30          # pausa mínima entre el fin de una transmisión y el arranque de la siguiente
CANDADO_SEGUNDOS = 240        # un pulso que se colgó libera el candado solo después de esto
INTERVALOS_PERMITIDOS = (30, 45, 60, 90, 120)   # con 25 min de transmisión, menos de 30 no deja pausa
SEGUNDOS_PULSO_LOCAL = 30


# --- Configuración -------------------------------------------------------------------------------------------------
def config() -> dict:
    c = db[COLECCION].find_one({"_id": "config"}) or {}
    return {"activo": bool(c.get("activo")), "intervalo_min": int(c.get("intervalo_min") or PULSO_INTERVALO_MIN),
            "actualizado_por": c.get("actualizado_por"), "actualizado_en": c.get("actualizado_en")}


def guardar_config(usuario: dict, activo: Optional[bool] = None, intervalo_min: Optional[int] = None) -> dict:
    cambios = {"actualizado_por": (usuario or {}).get("username") or "?", "actualizado_en": datetime.utcnow()}
    if activo is not None:
        cambios["activo"] = bool(activo)
    if intervalo_min is not None:
        if int(intervalo_min) not in INTERVALOS_PERMITIDOS:
            raise ValueError(f"El ritmo tiene que ser uno de {', '.join(map(str, INTERVALOS_PERMITIDOS))} minutos.")
        cambios["intervalo_min"] = int(intervalo_min)
    db[COLECCION].update_one({"_id": "config"}, {"$set": cambios}, upsert=True)
    return config()


# --- Horario ---------------------------------------------------------------------------------------------------------
def _ultima_transmision() -> Optional[dict]:
    return db["juegos"].find_one({"transmision.started_at": {"$exists": True}},
                                 {"transmision": 1, "equipo_local.nombre": 1, "equipo_visitante.nombre": 1, "tag": 1},
                                 sort=[("transmision.started_at", -1)])


def calcular_proximo_inicio(ultima: Optional[dict], intervalo_min: int, ahora: datetime) -> datetime:
    """Función pura: cuándo arranca el próximo partido según la última transmisión (UTC, sin zona)."""
    if not ultima:
        return ahora
    tx = ultima.get("transmision") or {}
    inicio = tx["started_at"]
    fin = inicio + timedelta(seconds=tx.get("duracion_segundos") or DURACION_TRANSMISION_SEGUNDOS)
    return max(inicio + timedelta(minutes=intervalo_min), fin + timedelta(seconds=MARGEN_SEGUNDOS))


def resumen_publico() -> dict:
    """Lo que puede ver cualquiera en /en-vivo: si el torneo avanza solo, a qué ritmo y cuándo arranca el próximo."""
    c = config()
    ultima = _ultima_transmision()
    en_curso = bool(ultima and (ultima.get("transmision") or {}).get("estado") == TRANSMISION_EN_CURSO)
    proximo = calcular_proximo_inicio(ultima, c["intervalo_min"], datetime.utcnow()) if c["activo"] else None
    return {"activo": c["activo"], "intervalo_min": c["intervalo_min"], "duracion_min": DURACION_TRANSMISION_SEGUNDOS // 60,
            "en_curso": en_curso, "proximo_inicio": (proximo.isoformat() + "Z") if proximo else None,
            "intervalos": list(INTERVALOS_PERMITIDOS)}


def resumen_admin() -> dict:
    e = db[COLECCION].find_one({"_id": "estado"}) or {}
    iso = lambda v: (v.isoformat() + "Z") if isinstance(v, datetime) else v
    c = config()
    return {**resumen_publico(), "actualizado_por": c["actualizado_por"], "actualizado_en": iso(c["actualizado_en"]),
            "ultimo_pulso": iso(e.get("ultimo_pulso")), "fuente": e.get("fuente"), "accion": e.get("accion"), "detalle": e.get("detalle"),
            "ultimo_error": e.get("ultimo_error"), "ultimo_error_en": iso(e.get("ultimo_error_en"))}


# --- Candado -------------------------------------------------------------------------------------------------------
def _tomar_candado() -> Optional[str]:
    ahora, token = datetime.utcnow(), uuid.uuid4().hex
    nuevo = {"$set": {"candado_hasta": ahora + timedelta(seconds=CANDADO_SEGUNDOS), "candado_token": token}}
    libre = {"_id": "estado", "$or": [{"candado_hasta": {"$lt": ahora}}, {"candado_hasta": {"$exists": False}}, {"candado_hasta": None}]}
    if db[COLECCION].find_one_and_update(libre, nuevo):
        return token
    try:   # primera vez: todavía no existe el documento
        db[COLECCION].insert_one({"_id": "estado", "candado_hasta": ahora + timedelta(seconds=CANDADO_SEGUNDOS), "candado_token": token})
        return token
    except DuplicateKeyError:
        return None   # otro pulso está trabajando


def _soltar_candado(token: str, registro: dict):
    db[COLECCION].update_one({"_id": "estado", "candado_token": token}, {"$set": {**registro, "candado_hasta": None, "candado_token": None}})


# --- El pulso ------------------------------------------------------------------------------------------------------
def pulsar(fuente: str = "scheduler", simulacro: bool = False) -> dict:
    """Un pulso. 'fuente': scheduler / local / navegador (solo para el registro y para decidir el trabajo pesado).
    'simulacro': decide qué haría sin cerrar ni arrancar nada (para probar)."""
    if simulacro:
        c = config()
        ultima = _ultima_transmision()
        en_curso = bool(ultima and (ultima.get("transmision") or {}).get("estado") == TRANSMISION_EN_CURSO)
        prox = calcular_proximo_inicio(ultima, c["intervalo_min"], datetime.utcnow())
        accion = "en_curso" if en_curso else ("apagado" if not c["activo"] else ("arrancaria" if prox <= datetime.utcnow() else "esperando"))
        return {"simulacro": True, "accion": accion, "proximo_inicio": prox.isoformat() + "Z", **c}

    token = _tomar_candado()
    if not token:
        return {"accion": "ocupado", "detalle": "Otro pulso está trabajando."}
    ahora = datetime.utcnow()
    registro = {"ultimo_pulso": ahora, "fuente": fuente}
    salida = {"accion": None, "detalle": None}
    try:
        # 1. Cerrar la transmisión que terminó (aplica los efectos diferidos exactamente una vez)
        vivo = obtener_estado_live()
        if vivo and vivo.get("finalizado"):
            salida["cerrado"] = f"{vivo['local']} {vivo['goles_local']}-{vivo['goles_visitante']} {vivo['visitante']}"

        # 2. Arrancar el siguiente si toca
        c = config()
        ultima = _ultima_transmision()
        en_curso = bool(ultima and (ultima.get("transmision") or {}).get("estado") == TRANSMISION_EN_CURSO)
        proximo = calcular_proximo_inicio(ultima, c["intervalo_min"], ahora)
        if en_curso:
            salida.update(accion="en_curso", detalle=f"{ultima['equipo_local']['nombre']} vs {ultima['equipo_visitante']['nombre']}")
        elif not c["activo"]:
            salida.update(accion="apagado", detalle="La reproducción automática está apagada.")
        elif proximo > ahora:
            salida.update(accion="esperando", detalle=f"Próximo partido a las {proximo.isoformat()}Z")
        else:
            r = iniciar_simulacion_automatica()
            if not r["encontrado"]:
                salida.update(accion="sin_partidos", detalle="No quedan partidos pendientes: el torneo terminó.")
            else:
                j = r["juego"]
                salida.update(accion="ya_en_curso" if r["ya_en_progreso"] else "inicio",
                              detalle=f"{j['equipo_local']['nombre']} vs {j['equipo_visitante']['nombre']}")
                proximo = calcular_proximo_inicio(_ultima_transmision(), c["intervalo_min"], ahora)
        salida["proximo_inicio"] = proximo.isoformat() + "Z" if c["activo"] else None

        # 3. Probabilidades en Cloud Run (solo el Scheduler: un pedido de ~45 s no debe colgar a un navegador)
        if EN_CLOUD_RUN and fuente == "scheduler" and salida["accion"] != "inicio":
            try:
                from services.probabilidades_service import recalcular
                t = time.time()
                if recalcular():
                    salida["probabilidades"] = f"recalculadas en {time.time() - t:.0f} s"
            except Exception as e:
                salida["probabilidades"] = f"error: {e}"
        registro.update(accion=salida["accion"], detalle=salida["detalle"], ultimo_error=None)
        return salida
    except Exception as e:
        registro.update(accion="error", ultimo_error=str(e)[:500], ultimo_error_en=ahora)
        salida.update(accion="error", detalle=str(e)[:300])
        print(f"[pulso] error: {e}")
        return salida
    finally:
        _soltar_candado(token, registro)


# --- Pulso local (desarrollo) ----------------------------------------------------------------------------------------
_hilo_local = {"hilo": None}


def iniciar_pulso_local():
    """Con PULSO_LOCAL=1, la app da el pulso por su cuenta cada SEGUNDOS_PULSO_LOCAL (hilo de fondo, nunca lanza)."""
    if _hilo_local["hilo"]:
        return

    def bucle():
        time.sleep(5)
        while True:
            try:
                pulsar("local")
            except Exception as e:
                print(f"[pulso local] {e}")
            time.sleep(SEGUNDOS_PULSO_LOCAL)

    _hilo_local["hilo"] = threading.Thread(target=bucle, name="pulso-local", daemon=True)
    _hilo_local["hilo"].start()
    print("[pulso] pulso local activo: cada", SEGUNDOS_PULSO_LOCAL, "s")
