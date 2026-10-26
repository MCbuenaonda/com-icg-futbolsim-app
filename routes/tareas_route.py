"""
Tareas que dispara Cloud Scheduler (no las usa ningún navegador). Sin sesión: se autentican con la cabecera
X-Pulso-Clave = PULSO_CLAVE (variable de entorno). Si PULSO_CLAVE no está definida, la ruta responde 503.
"""
import hmac
import logging

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from config.settings import PULSO_CLAVE
from services.pulso_service import pulsar

route = APIRouter(prefix="/tareas", tags=["Tareas programadas"])
tag = "Tareas"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# 'def' y no 'async def': cerrar un partido, arrancar el siguiente o recalcular probabilidades es I/O bloqueante
# (pymongo) y puede tardar; con async congelaría el servidor entero.
@route.post("/pulso")
def pulso(x_pulso_clave: str = Header(default=""), simulacro: bool = False):
    if not PULSO_CLAVE:
        return JSONResponse({"ok": False, "error": "El pulso no está configurado (falta PULSO_CLAVE)."}, status_code=503)
    if not hmac.compare_digest(x_pulso_clave or "", PULSO_CLAVE):
        return JSONResponse({"ok": False, "error": "Clave inválida."}, status_code=401)
    r = pulsar("scheduler", simulacro=simulacro)
    if r.get("accion") not in ("esperando", "en_curso", "apagado", "ocupado"):
        logger.info(f"[pulso] {r}")
    return {"ok": r.get("accion") != "error", **r}
