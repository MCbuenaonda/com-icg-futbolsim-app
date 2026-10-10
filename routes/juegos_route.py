from fastapi import APIRouter, HTTPException
from fastapi import Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from services.juegos_service import obtener_juegos_programados, obtener_juego_activo, obtener_juegos_calendario, resaltar_jugadores_en_descripcion
from services.auth_service import context_usuario_actual, obtener_usuario_actual, tiene_permiso
from services.juego_en_vivo_service import sesiones_pendientes_usuario
from config.settings import PREFIX_JUEGOS_PATH
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
import certifi
import logging
import uuid
import json
from urllib.parse import urlencode

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')
templates = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])
templates.env.filters["resaltar_jugadores"] = resaltar_jugadores_en_descripcion
route = APIRouter(prefix=PREFIX_JUEGOS_PATH, tags=["Juegos"])
tag='Mundial'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
process_uuid = uuid.uuid4()


JUEGOS_POR_PAGINA = 24


def _filtrar_juegos(juegos: list, q: str, confederacion: str, grupo: str, fecha: str, jornada: str) -> list:
    """Filtros de la grilla de partidos pendientes (antes se aplicaban en el navegador sobre las
    ~700 tarjetas renderizadas de una vez)."""
    texto = (q or "").strip().lower()
    def coincide(j):
        if texto and texto not in (j.get("equipo_local", {}).get("nombre", "").lower() + " " + j.get("equipo_visitante", {}).get("nombre", "").lower()):
            return False
        if confederacion and str(j.get("confederacion_id")) != confederacion:
            return False
        if grupo and j.get("grupo") != grupo:
            return False
        if fecha and j.get("fecha") != fecha:
            return False
        if jornada and j.get("jornada") != jornada:
            return False
        return True
    return [j for j in juegos if coincide(j)]


@route.get("/", response_class=HTMLResponse)
async def juegos(request: Request, q: str = "", confederacion: str = "", grupo: str = "", fecha: str = "",
                 jornada: str = "", pagina: int = 1):
    try:
        # 1. Obtener el mundial activo (opcional)
        mundial_activo = db["mundiales"].find_one({"activo": True})
        mundial_id = mundial_activo["_id"] if mundial_activo else None
        
        # 2. Obtener los juegos programados
        juegos = obtener_juegos_programados(db, mundial_id)
        
        # Opciones de los filtros: de TODOS los pendientes (no solo de la página actual)
        grupos = sorted(list({j["grupo"] for j in juegos if "grupo" in j}))
        fechas = sorted(list({j["fecha"] for j in juegos if "fecha" in j}))
        jornadas = sorted(list({j["jornada"] for j in juegos if "jornada" in j}))

        # Filtros + paginación en el servidor
        total_pendientes = len(juegos)
        filtrados = _filtrar_juegos(juegos, q, confederacion, grupo, fecha, jornada)
        total_paginas = max(1, -(-len(filtrados) // JUEGOS_POR_PAGINA))
        pagina = min(max(1, pagina), total_paginas)
        juegos = filtrados[(pagina - 1) * JUEGOS_POR_PAGINA: pagina * JUEGOS_POR_PAGINA]
        filtros = {"q": q, "confederacion": confederacion, "grupo": grupo, "fecha": fecha, "jornada": jornada}
            
        # Elecciones pendientes del Juego en Vivo del usuario (badge "Vas con X" en cada tarjeta)
        usuario = obtener_usuario_actual(request)
        sesiones_juego_en_vivo = sesiones_pendientes_usuario(usuario) if tiene_permiso(usuario, "juego_en_vivo") else {}

        return templates.TemplateResponse(
            request=request,
            name="juegos.html",
            context={
                "sesiones_juego_en_vivo": sesiones_juego_en_vivo,
                "juegos": juegos,
                "mundial": mundial_activo,
                "grupos": grupos,
                "fechas": fechas,
                "jornadas": jornadas,
                "filtros": filtros,
                "query_filtros": urlencode({k: v for k, v in filtros.items() if v}),
                "hay_filtros": any(filtros.values()),
                "pagina": pagina,
                "total_paginas": total_paginas,
                "total_filtrados": len(filtrados),
                "total_pendientes": total_pendientes,
            }
        )
        
    except FileNotFoundError:
        print(f"Error: No se encontró la coleccion de juegos")
    except json.JSONDecodeError:
        print("Error: El archivo no tiene un formato JSON válido.")


@route.get("/calendario", response_class=HTMLResponse)
async def calendario(request: Request):
    try:
        # 1. Obtener el mundial activo (opcional)
        mundial_activo = db["mundiales"].find_one({"activo": True})
        mundial_id = mundial_activo["_id"] if mundial_activo else None

        # 2. Obtener todos los juegos con fecha asignada (programados y finalizados)
        juegos = obtener_juegos_calendario(db, mundial_id)

        # 3. Armar los eventos para el calendario (FullCalendar)
        eventos = []
        for j in juegos:
            local = j.get("equipo_local") or {}
            visita = j.get("equipo_visitante") or {}
            # Un partido "en vivo" ya está simulado (estado == "finalizado") pero todavía se
            # está revelando -- tratarlo como pendiente acá para no mostrar el marcador final
            # antes de tiempo.
            en_vivo = (j.get("transmision") or {}).get("estado") == "in_progress"
            finalizado = j.get("estado") == "finalizado" and not en_vivo

            marcador = f"{local.get('goles', 0)} - {visita.get('goles', 0)}" if finalizado else "vs"
            titulo = f"{local.get('siglas', local.get('nombre', '?'))} {marcador} {visita.get('siglas', visita.get('nombre', '?'))}"

            eventos.append({
                "title": titulo,
                "start": f"{j.get('fecha')}T{j.get('hora', '00:00')}",
                "backgroundColor": "#10b981" if finalizado else "#3b82f6",
                "borderColor": "#10b981" if finalizado else "#3b82f6",
                "extendedProps": {
                    "id": j.get("_id"),
                    "id_local": local.get("id"),
                    "id_visita": visita.get("id"),
                    "tiempo_extra": j.get("tiempo_extra"),
                    "estado": j.get("estado"),
                    "tag": j.get("tag"),
                    "grupo": j.get("grupo"),
                    "jornada": j.get("jornada"),
                    "estadio": (j.get("ubicacion") or {}).get("estadio"),
                }
            })

        # 4. Determinar la fecha inicial a mostrar: la del próximo partido pendiente
        #    (los juegos ya vienen ordenados por fecha/hora ascendente); si no hay
        #    ninguno pendiente, se usa la fecha del primer partido disponible. Un partido "en
        #    vivo" (estado == "finalizado" pero todavía en transmisión) cuenta como pendiente acá.
        proximo_partido = next(
            (j for j in juegos if j.get("estado") != "finalizado" or (j.get("transmision") or {}).get("estado") == "in_progress"),
            None
        )
        fecha_inicial = (proximo_partido or (juegos[0] if juegos else {})).get("fecha")

        return templates.TemplateResponse(
            request=request,
            name="calendario.html",
            context={
                "mundial": mundial_activo,
                "eventos_json": json.dumps(eventos, ensure_ascii=False),
                "fecha_inicial_json": json.dumps(fecha_inicial),
                "total_juegos": len(juegos),
            }
        )

    except FileNotFoundError:
        print(f"Error: No se encontró la coleccion de juegos")
    except json.JSONDecodeError:
        print("Error: El archivo no tiene un formato JSON válido.")


@route.get("/{id}", response_class=HTMLResponse)
async def juego(request: Request, id: str):
    try:
        juego, _ = obtener_juego_activo(id)

        if juego and (juego.get("transmision") or {}).get("estado") == "in_progress":
            # El partido ya está simulado y persistido, pero todavía se está "revelando" en
            # vivo -- no mostrar el resultado crudo acá, mandar a la vista de transmisión.
            return RedirectResponse(url=request.url_for("live_match_view"), status_code=303)

        return templates.TemplateResponse(
            request=request,
            name="resumen.html",
            context={"partido": juego}
        )
    except FileNotFoundError:
        print(f"Error: No se encontró la coleccion de paises")
    except json.JSONDecodeError:
        print("Error: El archivo no tiene un formato JSON válido.")
