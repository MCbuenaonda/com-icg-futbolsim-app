from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from bson.errors import InvalidId
from schemas.rewards_schema import (
    CheckInOut, BancarrotaRescueOut, DailyStatusOut, TriviaQuizOut, TriviaSubmitIn, TriviaResultadoOut
)
from services.rewards_service import check_in, claim_bankruptcy_rescue, obtener_daily_status
from services.trivia_service import generate_dynamic_trivia, validate_trivia_answers
from services.auth_service import obtener_usuario_actual, context_usuario_actual
import logging

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])

# API JSON — Daily Check-in / Beca de Emergencia (contrato tal cual se pidió: /rewards/...)
route_rewards = APIRouter(prefix="/rewards", tags=["Rewards"])

# API JSON — Trivia Dinámica (contrato tal cual se pidió: /trivia/...)
route_trivia = APIRouter(prefix="/trivia", tags=["Trivia"])

# Vistas HTML: Recompensa Diaria + Trivia Express
route_vistas = APIRouter(prefix="/misiones", tags=["Rewards UI"])

tag = 'Rewards'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _requerir_sesion(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        raise HTTPException(status_code=401, detail="Necesitás iniciar sesión")
    return usuario


def _requerir_sesion_propia(request: Request, user_id: str):
    """
    Igual que _requerir_sesion, pero además valida que el user_id del path
    coincida con el de la sesión — a diferencia de otros endpoints de solo
    lectura tipo 'my-portfolio/{user_id}' de este sistema, acá el GET tiene
    efecto secundario (genera una sesión de trivia, consume un cupo diario),
    así que no alcanza con solo advertir el riesgo de IDOR: se bloquea.
    """
    usuario = _requerir_sesion(request)
    if str(usuario["_id"]) != str(user_id):
        raise HTTPException(status_code=403, detail="No podés operar sobre otro usuario")
    return usuario


# ==========================================================================
# API JSON — Rewards
# ==========================================================================
@route_rewards.post("/check-in", response_model=CheckInOut, name="rewards_check_in")
async def check_in_endpoint(request: Request):
    usuario = _requerir_sesion(request)
    try:
        return check_in(usuario["_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error en check-in: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al procesar el check-in")


@route_rewards.post("/claim-bankruptcy-rescue", response_model=BancarrotaRescueOut, name="rewards_claim_bankruptcy_rescue")
async def claim_bankruptcy_rescue_endpoint(request: Request):
    usuario = _requerir_sesion(request)
    try:
        return claim_bankruptcy_rescue(usuario["_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al reclamar la beca de emergencia: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al procesar el reclamo")


@route_rewards.get("/daily-status/{user_id}", response_model=DailyStatusOut, name="rewards_daily_status")
async def daily_status_endpoint(request: Request, user_id: str):
    _requerir_sesion_propia(request, user_id)
    try:
        return obtener_daily_status(user_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==========================================================================
# API JSON — Trivia
# ==========================================================================
@route_trivia.get("/daily-quiz/{user_id}", response_model=TriviaQuizOut, name="trivia_daily_quiz")
async def daily_quiz_endpoint(request: Request, user_id: str):
    _requerir_sesion_propia(request, user_id)
    try:
        return generate_dynamic_trivia(user_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de usuario inválido")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al generar la trivia para {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al generar la trivia")


@route_trivia.post("/submit", response_model=TriviaResultadoOut, name="trivia_submit")
async def submit_endpoint(request: Request, body: TriviaSubmitIn):
    usuario = _requerir_sesion(request)
    try:
        return validate_trivia_answers(usuario["_id"], body.session_id, body.respuestas)
    except InvalidId:
        raise HTTPException(status_code=400, detail="ID de sesión inválido")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error al validar la trivia: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al validar las respuestas")


# ==========================================================================
# Vistas HTML (requieren sesión iniciada — ver services/auth_service.py)
# ==========================================================================
@route_vistas.get("/", response_class=HTMLResponse, name="misiones_vista")
async def misiones_vista(request: Request):
    usuario = obtener_usuario_actual(request)
    if not usuario:
        return RedirectResponse(url=request.url_for("login"), status_code=303)

    try:
        estado = obtener_daily_status(usuario["_id"])
    except ValueError:
        estado = None

    return templates.TemplateResponse(
        request=request,
        name="misiones_diarias.html",
        context={"estado": estado}
    )
