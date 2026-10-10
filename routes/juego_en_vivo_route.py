"""
API del Juego en Vivo (services/juego_en_vivo_service.py): elegir país antes del partido, cambiar
el riesgo durante la transmisión y consultar saldo/transacciones/ranking. Todas las rutas exigen
sesión iniciada (los puntos se cobran/acreditan en usuarios.monto); el cálculo de puntos es
100% del backend, el frontend solo muestra lo que devuelve 'state'.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from config.settings import PREFIX_LIVE_GAME_PATH
from schemas.juego_en_vivo_schema import CambiarRiesgoIn, CrearSesionIn
from services.auth_service import obtener_usuario_actual
from services.juego_en_vivo_service import (
    JuegoEnVivoError, cambiar_multiplicador, cancelar_sesion, crear_sesion,
    obtener_cuotas_partido, obtener_estado_juego, obtener_ranking,
)

route = APIRouter(prefix=PREFIX_LIVE_GAME_PATH, tags=["Juego en Vivo"])
tag = 'Juego en Vivo'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _usuario_o_401(request: Request) -> dict:
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Inicia sesión para jugar.")
    return usuario


def _ejecutar(funcion, *args, **kwargs):
    """Traduce los errores de validación del servicio a HTTP (400/404/409/429)."""
    try:
        return funcion(*args, **kwargs)
    except JuegoEnVivoError as e:
        raise HTTPException(status_code=e.status_code, detail=e.mensaje)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error en Juego en Vivo: {e}")
        raise HTTPException(status_code=500, detail="Error interno del Juego en Vivo.")


@route.get("/next", name="live_game_next")
async def proximo_partido(request: Request):
    """Cuotas del próximo partido que va a transmitirse ("Simular siguiente" en /en-vivo/)."""
    return _ejecutar(obtener_cuotas_partido, _usuario_o_401(request))


@route.get("/matches/{juego_id}/odds", name="live_game_odds")
async def cuotas_partido(juego_id: str, request: Request):
    """Probabilidad, categoría y cuota de cada selección + entrada, saldo y elección del usuario."""
    return _ejecutar(obtener_cuotas_partido, _usuario_o_401(request), juego_id)


@route.post("/sessions", status_code=201, name="live_game_crear_sesion")
async def elegir_pais(payload: CrearSesionIn, request: Request):
    """Elige país para un partido pendiente: cobra la entrada y asigna la cuota de puntos."""
    return _ejecutar(crear_sesion, _usuario_o_401(request), payload.juego_id, payload.pais_id, payload.multiplicador)


@route.delete("/sessions/{juego_id}", name="live_game_cancelar_sesion")
async def cancelar_eleccion(juego_id: str, request: Request):
    """Cancela la elección antes de que empiece el partido y reembolsa la entrada."""
    return _ejecutar(cancelar_sesion, _usuario_o_401(request), juego_id)


@route.put("/sessions/{juego_id}/risk", name="live_game_riesgo")
async def cambiar_riesgo(juego_id: str, payload: CambiarRiesgoIn, request: Request):
    """Cambia el multiplicador (x1/x1.5/x2/x3), sujeto a cooldown durante la transmisión."""
    return _ejecutar(cambiar_multiplicador, _usuario_o_401(request), juego_id, payload.multiplicador)


@route.get("/state", name="live_game_estado")
async def estado_juego(request: Request, juego_id: Optional[str] = None):
    """Estado del juego del usuario (procesa los eventos revelados). Sin 'juego_id': el partido
    en transmisión. Se consulta en cada poll de /en-vivo/."""
    return _ejecutar(obtener_estado_juego, _usuario_o_401(request), juego_id)


@route.get("/ranking", name="live_game_ranking")
async def ranking(request: Request, juego_id: Optional[str] = None, mundial_id: Optional[str] = None):
    """Ranking por partido (juego_id) o del torneo (mundial_id)."""
    if not juego_id and not mundial_id:
        raise HTTPException(status_code=400, detail="Indica juego_id o mundial_id.")
    return _ejecutar(obtener_ranking, _usuario_o_401(request), juego_id=juego_id, mundial_id=mundial_id)
