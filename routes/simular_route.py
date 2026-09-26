from fastapi import APIRouter, HTTPException
from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pymongo.mongo_client import MongoClient
from config.settings import PREFIX_SIMULADOR_PATH, MONGODB_URI
from services.juegos_service import obtener_juego_activo, obtener_ultimo_partido, obtener_resultado_equipo, calcular_asistencia, generar_clima_partido, guardar_aforo_clima_juego, obtener_marcador_ida_grupo_dos_equipos, obtener_historial_enfrentamientos, ejecutar_simulacion_completa, resaltar_jugadores_en_descripcion
from services.international_service import get_pais_internacional
from services.auth_service import context_usuario_actual, obtener_usuario_actual
from services.quinielas_service import contar_selecciones_pendientes_usuario
from services.match_badges_service import obtener_marcas_partido
from services.fecha_service import formatear_fecha_es
import certifi
import logging
import uuid
import json

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')
templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.filters["resaltar_jugadores"] = resaltar_jugadores_en_descripcion
templates.env.filters["fecha_es"] = formatear_fecha_es
route = APIRouter(prefix=PREFIX_SIMULADOR_PATH)
tag='Mundial'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
process_uuid = uuid.uuid4()


@route.get("/", response_class=HTMLResponse)
async def inicio(request: Request, id: str, id_local: int, id_visita: int):
    pais_local = get_pais_internacional(db, id_local, logger)
    pais_visitante = get_pais_internacional(db, id_visita, logger)
    
    # 1. Validar y extraer los registros aleatorios
    local = pais_local["nombre"] if id_local else "LOCAL"
    visitante = pais_visitante["nombre"] if id_visita else "VISITANTE"
    
    ultimo_juego_local = obtener_ultimo_partido(id_local)
    resultado_local= obtener_resultado_equipo(ultimo_juego_local, id_local)
    ultimo_juego_visita = obtener_ultimo_partido(id_visita)
    resultado_visita= obtener_resultado_equipo(ultimo_juego_visita, id_visita)
    
    if ultimo_juego_local:
        del ultimo_juego_local["ubicacion"]
        del ultimo_juego_local["estadisticas"]
        del ultimo_juego_local["resultado"]
    if ultimo_juego_visita:
        del ultimo_juego_visita["ubicacion"]
        del ultimo_juego_visita["estadisticas"]
        del ultimo_juego_visita["resultado"]
    
    # validamos si es el juego activo
    partido_sel, juego_activo = obtener_juego_activo(id)

    # validar si el juego ya tiene aforo/clima calculados; si no, generarlos y persistirlos
    if juego_activo and ('aforo' not in partido_sel or 'clima' not in partido_sel):
        aforo = calcular_asistencia(partido_sel["fase_id"], partido_sel["equipo_local"]["rankin"], partido_sel["equipo_visitante"]["rankin"])
        clima = generar_clima_partido(partido_sel["ubicacion"], partido_sel.get("hora"))
        guardar_aforo_clima_juego(id, aforo, clima)
        partido_sel["aforo"] = aforo
        partido_sel["clima"] = clima
    else:
        aforo = partido_sel.get("aforo")
        clima = partido_sel.get("clima")

    # si es el partido de vuelta (jornada 2) de un grupo de 2 equipos, obtener el marcador
    # de la ida para poder mostrar/evaluar la eliminatoria por marcador global
    marcador_ida = obtener_marcador_ida_grupo_dos_equipos(db, id, id_local, id_visita)

    partido = {
        "_id": id,
        "local": local,
        "visitante": visitante,
        "id_local": id_local,
        "id_visita": id_visita,
        "activo": juego_activo,
        "ubicaion": partido_sel["ubicacion"],
        "fecha": partido_sel["fecha"],
        "hora": partido_sel["hora"],
        "tag": partido_sel["tag"],
        "grupo": partido_sel["grupo"],
        "jornada": partido_sel["jornada"],
        "tipo": partido_sel["tipo"],
        "fase_id": partido_sel["fase_id"],
        "bandera_local": partido_sel["equipo_local"]["bandera"],
        "bandera_visitante": partido_sel["equipo_visitante"]["bandera"],
        "stats_local": pais_local["estadisticas"],
        "stats_visita": pais_visitante["estadisticas"],
        "ultimo_juego_local": ultimo_juego_local,
        "ultimo_juego_visita": ultimo_juego_visita,
        "resultado_ultimo_juego_local": resultado_local,
        "resultado_ultimo_juego_visita": resultado_visita,
        "aforo": aforo,
        "clima": clima,
        "tactica_local": partido_sel["equipo_local"].get("tactica"),
        "tactica_visita": partido_sel["equipo_visitante"].get("tactica"),
        "marcador_ida": marcador_ida,
    }
    
    usuario_sesion = obtener_usuario_actual(request)
    partidos_restantes_quiniela = contar_selecciones_pendientes_usuario(usuario_sesion["_id"]) if usuario_sesion else None

    marcas_partido = None
    if usuario_sesion:
        try:
            marcas_partido = obtener_marcas_partido(
                usuario_sesion["_id"], id, id_local, id_visita,
                partido_sel.get("fase_id"), (partido_sel.get("ubicacion") or {}).get("id")
            )
        except Exception as e:
            logger.error(f"Error al calcular marcas del partido {id}: {str(e)}")

    historial_enfrentamientos = obtener_historial_enfrentamientos(id_local, id_visita, excluir_id=id)

    return templates.TemplateResponse(
        request=request,
        name="simulador.html",
        context={
            "partido": partido,
            "stats_jugadores": None,
            "prefix": PREFIX_SIMULADOR_PATH,
            "partidos_restantes_quiniela": partidos_restantes_quiniela,
            "marcas_partido": marcas_partido,
            "historial_enfrentamientos": historial_enfrentamientos
        }
    )

# endpoint para simular un partido de fútbol
@route.get("/simular", response_class=HTMLResponse)
async def simular(request: Request, id: str, id_local: int, id_visita: int, tiempo_extra: bool = False):
    # Todo el motor + los efectos secundarios (jugadores, país, aficionados, quinielas,
    # selecciones/ownership, fantasy, sedes, ranking, avance de fase) vive en
    # services.juegos_service.ejecutar_simulacion_completa -- la comparte con
    # routes/live_match_route.py para el modo automático, así ambos flujos corren EXACTAMENTE
    # la misma lógica sin duplicarla. Acá solo queda lo específico de esta vista HTML.
    resultado_simulacion = ejecutar_simulacion_completa(id, id_local, id_visita, tiempo_extra)

    juego_doc = resultado_simulacion["juego_doc"]

    usuario_sesion = obtener_usuario_actual(request)
    partidos_restantes_quiniela = contar_selecciones_pendientes_usuario(usuario_sesion["_id"]) if usuario_sesion else None

    marcas_partido = None
    if usuario_sesion:
        try:
            marcas_partido = obtener_marcas_partido(
                usuario_sesion["_id"], id, id_local, id_visita,
                (juego_doc or {}).get("fase_id"), ((juego_doc or {}).get("ubicacion") or {}).get("id")
            )
        except Exception as e:
            logger.error(f"Error al calcular marcas del partido {id}: {str(e)}")

    historial_enfrentamientos = obtener_historial_enfrentamientos(id_local, id_visita, excluir_id=id)

    if resultado_simulacion["ya_finalizado"]:
        partido_doc = resultado_simulacion["partido"]
        if (partido_doc.get("transmision") or {}).get("estado") == "in_progress":
            # El partido ya está simulado y persistido, pero todavía se está "revelando" en
            # vivo -- no mostrar el resultado crudo acá, mandar a la vista de transmisión.
            return RedirectResponse(url=request.url_for("live_match_view"), status_code=303)
        return templates.TemplateResponse(
            request=request,
            name="simulador.html",
            context={
                "partido": resultado_simulacion["partido"],
                "stats_jugadores": None,
                "prefix": PREFIX_SIMULADOR_PATH,
                "intensidad_json": None,
                "partidos_restantes_quiniela": partidos_restantes_quiniela,
                "marcas_partido": marcas_partido,
                "historial_enfrentamientos": historial_enfrentamientos
            }
        )

    return templates.TemplateResponse(
        request=request,
        name="simulador.html",
        context={
            "partido": resultado_simulacion["partido"],
            "stats_jugadores": resultado_simulacion["stats_jugadores"],
            "prefix": PREFIX_SIMULADOR_PATH,
            "intensidad_json": json.dumps(resultado_simulacion["intensidad"]),
            "partidos_restantes_quiniela": partidos_restantes_quiniela,
            "marcas_partido": marcas_partido,
            "delta_aficionados": resultado_simulacion["delta_aficionados"],
            "historial_enfrentamientos": historial_enfrentamientos
        }
    )
