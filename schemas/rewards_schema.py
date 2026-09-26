"""
Esquemas Pydantic para el módulo de Misiones Diarias / Daily Check-in / Trivia
(routes/rewards_route.py). Igual que en los demás módulos JSON de esta app,
son solo el contrato de entrada/salida de la API — la persistencia sigue
siendo pymongo + dicts en services/rewards_service.py y services/trivia_service.py.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


# ==========================================
# Daily Check-in
# ==========================================
class CheckInOut(BaseModel):
    bono_otorgado: int
    bono_especial_otorgado: bool
    racha_actual: int
    total_checkins: int


# ==========================================
# Beca de Emergencia (rescate de bancarrota)
# ==========================================
class BancarrotaRescueOut(BaseModel):
    monto_otorgado: int
    fase_id: Optional[int] = None


# ==========================================
# Estado diario (check-in + racha + beca + trivia)
# ==========================================
class DailyStatusOut(BaseModel):
    ya_reclamo_checkin_hoy: bool
    racha_actual: int
    dias_para_bono_especial: int
    puede_reclamar_beca_emergencia: bool
    trivia_sesiones_hoy: int
    trivia_sesiones_restantes: int
    puede_jugar_trivia: bool


# ==========================================
# Trivia — generación (sin exponer la respuesta correcta)
# ==========================================
class TriviaPreguntaOut(BaseModel):
    indice: int
    enunciado: str
    opciones: List[str]


class TriviaQuizOut(BaseModel):
    session_id: str
    preguntas: List[TriviaPreguntaOut]


# ==========================================
# Trivia — envío de respuestas
# ==========================================
class TriviaSubmitIn(BaseModel):
    session_id: str
    respuestas: List[Optional[int]]


class TriviaDetalleRespuesta(BaseModel):
    enunciado: str
    opciones: List[str]
    respuesta_usuario_idx: Optional[int] = None
    respuesta_correcta_idx: int
    es_correcta: bool


class TriviaResultadoOut(BaseModel):
    correct_answers: int
    total_questions: int
    points_rewarded: int
    detalle: List[TriviaDetalleRespuesta]
    completed_at: datetime
