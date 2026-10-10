from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from schemas.prematch_schema import PreMatchAnalysisResponse
from services.prematch_service import analyze_pre_match_status
from services.auth_service import context_usuario_actual
from services.cara_a_cara_service import obtener_cara_a_cara
import logging

templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])

# API JSON (contrato tal cual se pidió: GET /matches/pre-match-analysis/{match_id})
route = APIRouter(prefix="/matches", tags=["Pre-Match Scouter"])

# Vista HTML: Tarjeta Pre-Partido tipo transmisión deportiva
route_vistas = APIRouter(prefix="/scouter", tags=["Pre-Match Scouter UI"])

tag = 'Pre-Match Scouter'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def _resolver_analisis(match_id: str) -> PreMatchAnalysisResponse:
    """Corre el análisis y lo valida contra el esquema de respuesta (compartido por ambos endpoints)."""
    try:
        datos = analyze_pre_match_status(match_id)
        return PreMatchAnalysisResponse(**datos)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error al calcular el análisis pre-partido de '{match_id}': {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno al calcular el análisis pre-partido")


# ==========================================================================
# API JSON
# ==========================================================================
@route.get("/pre-match-analysis/{match_id}", response_model=PreMatchAnalysisResponse, name="prematch_analysis")
async def pre_match_analysis(match_id: str):
    """
    Análisis matemático de clasificación (fases 1-7, según reglas de cada tamaño de grupo) o
    de probabilidad de avance de ronda (fases 8-13, knockout a partido único), más comparativa
    H2H de estadísticas, para el partido 'match_id'.
    """
    return _resolver_analisis(match_id)


# ==========================================================================
# Vista HTML (Tarjeta Pre-Partido)
# ==========================================================================
@route_vistas.get("/{match_id}", response_class=HTMLResponse, name="prematch_scouter_view")
async def scouter_view(request: Request, match_id: str):
    analisis = _resolver_analisis(match_id)
    # Bloque "Historial entre ambos" (mismo resumen que /cara-a-cara)
    try:
        h2h = obtener_cara_a_cara(analisis.home_team_analysis.pais_id, analisis.away_team_analysis.pais_id)
    except Exception as e:
        logger.error(f"Error al armar el historial entre ambos del partido '{match_id}': {str(e)}")
        h2h = None
    return templates.TemplateResponse(
        request=request,
        name="prematch_scouter.html",
        context={"analisis": analisis, "match_id": match_id, "h2h": h2h}
    )
