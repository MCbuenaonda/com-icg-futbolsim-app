"""
Servicio de "Simulación Automática en Vivo" (routes/live_match_route.py).

Diseño: NO existe ningún mecanismo de background/async en este proyecto (sin BackgroundTasks,
Celery, APScheduler ni threads) -- 'simular_partido_realista' ya es una función síncrona que
calcula el partido COMPLETO (90/120 minutos de eventos) en una sola llamada bloqueante. Por eso
la "transmisión en vivo" acá NO es un cómputo diferido real: el partido se simula y su resultado
se persiste por completo al instante (reutilizando
services.juegos_service.simular_y_registrar_resultado), y lo único que pasa con el correr del
tiempo real es que se van "revelando" progresivamente los eventos que ya están calculados.

Esto se apoya en un campo NUEVO y puramente aditivo, 'juegos.transmision', que convive sin
interferir con el campo 'juegos.estado' existente ("creado"/"finalizado", leído/escrito en 27
puntos distintos del código) -- ningún consumidor existente necesita cambios.

Los EFECTOS SECUNDARIOS del partido (país/'internacional', jugadores, rankings, aficionados,
quinielas, dividendos de Dueño de Selecciones, fantasy, sedes, avance de fase --
services.juegos_service.aplicar_efectos_secundarios) NO se aplican al arrancar la transmisión:
si se aplicaran al instante, la tabla de posiciones, los perfiles de jugadores y el dashboard de
estadísticas revelarían el resultado del partido antes de que termine la "transmisión en vivo".
En cambio quedan diferidos en el campo 'juegos.efectos_pendientes' (aditivo, se borra apenas se
aplican) y se disparan recién cuando la ventana de 5 minutos termina, vía
_disparar_efectos_pendientes -- reutilizando el mismo "auto-finalize-on-read" que ya hacía el
flip de 'transmision.estado' a 'finished' dentro de obtener_estado_live.
"""
import certifi
import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
from services.juegos_service import obtener_juego_activo, simular_y_registrar_resultado, aplicar_efectos_secundarios
from services.clasificacion_service import obtener_tabla_grupo_de_equipo
from services.fecha_service import formatear_fecha_es
from services.simular_service import FORMACIONES

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DURACION_TRANSMISION_SEGUNDOS = 600  # 5 minutos reales por partido "transmitido"

TRANSMISION_EN_CURSO = "in_progress"
TRANSMISION_FINALIZADA = "finished"


def _match_en_progreso() -> Optional[Dict[str, Any]]:
    """El juego con 'transmision.estado' == 'in_progress', si hay alguno (debería haber a lo sumo uno)."""
    return db["juegos"].find_one({"transmision.estado": TRANSMISION_EN_CURSO})


def iniciar_simulacion_automatica() -> Dict[str, Any]:
    """
    Orquesta POST /matches/simulate-next-auto:
      1. Si ya hay un partido en 'transmision.estado' == 'in_progress' -> no-op, se devuelve
         ese mismo partido (para que un poller pueda llamar este endpoint repetidas veces sin
         arrancar una simulación nueva encima de la que ya está en curso).
      2. Si no, busca el próximo partido 'creado' (obtener_juego_activo() sin id -- el mismo
         criterio que ya usa el flujo manual: el más próximo por fecha/hora) y, si existe, corre
         simular_y_registrar_resultado(...) -- el partido queda simulado y su resultado
         persistido, pero SIN aplicar los efectos secundarios todavía (ver docstring del
         módulo) -- y además persiste 'transmision' (hora de inicio, para la revelación
         progresiva) y 'efectos_pendientes' (los datos que va a necesitar
         _disparar_efectos_pendientes cuando la ventana termine).
      3. Si no queda ningún partido 'creado', lo señala explícitamente (torneo terminado).

    :return: {
        "encontrado": bool,
        "ya_en_progreso": bool,
        "juego": Optional[dict],   # el doc de 'juegos' ya con 'transmision' seteado
    }
    """
    en_progreso = _match_en_progreso()
    if en_progreso:
        return {"encontrado": True, "ya_en_progreso": True, "juego": en_progreso}

    primer_partido, _ = obtener_juego_activo()
    if not primer_partido:
        return {"encontrado": False, "ya_en_progreso": False, "juego": None}

    juego_id = str(primer_partido["_id"])
    id_local = primer_partido["equipo_local"]["id"]
    id_visita = primer_partido["equipo_visitante"]["id"]

    # A propósito NO se llama a ejecutar_simulacion_completa acá -- esa función también aplica
    # todos los efectos secundarios (país, jugadores, rankings, fantasy, quinielas, etc.) al
    # instante, lo que "spoilearía" el resultado en la tabla de posiciones/perfiles de jugadores
    # antes de que termine la revelación en vivo. Solo se simula y se persiste el resultado
    # (necesario para que GET /matches/live pueda ir revelando 'resultado.eventos'); los efectos
    # secundarios quedan diferidos hasta que la ventana de 5 minutos termine (ver
    # _disparar_efectos_pendientes, llamada desde obtener_estado_live).
    base = simular_y_registrar_resultado(juego_id, id_local, id_visita)

    if base["ya_finalizado"]:
        # Caso borde preexistente (doble-POST concurrente): el partido ya se finalizó por otro
        # camino antes de que este request llegara a registrar_resultado_juego. No hay nada
        # nuevo que transmitir -- se devuelve igual que "ya en progreso" sin pisar nada.
        en_progreso = _match_en_progreso()
        return {"encontrado": True, "ya_en_progreso": True, "juego": en_progreso or base["partido"]}

    stats_jugadores = base.get("stats_jugadores") or {}
    efectos_pendientes = {
        "stats_jugadores": [{"jugador_id": jid, "stats": stats} for jid, stats in stats_jugadores.items()]
    }

    transmision = {
        "estado": TRANSMISION_EN_CURSO,
        "started_at": datetime.utcnow(),
        "duracion_segundos": DURACION_TRANSMISION_SEGUNDOS,
    }
    db["juegos"].update_one(
        {"_id": ObjectId(juego_id)},
        {"$set": {"transmision": transmision, "efectos_pendientes": efectos_pendientes}}
    )

    juego_actualizado = db["juegos"].find_one({"_id": ObjectId(juego_id)})
    return {"encontrado": True, "ya_en_progreso": False, "juego": juego_actualizado}


def calcular_estado_transmision(
    eventos: List[Dict[str, Any]], started_at: datetime, now: datetime, duracion_segundos: int = DURACION_TRANSMISION_SEGUNDOS
) -> Dict[str, Any]:
    """
    Función PURA (sin acceso a Mongo): dado el tiempo real transcurrido desde 'started_at' hasta
    'now', determina qué subconjunto de 'eventos' (ya calculados por completo) corresponde
    mostrar en ese instante de la "transmisión".

    Algoritmo: se reparte la CANTIDAD de eventos (no el minuto de partido) de forma lineal sobre
    'duracion_segundos'. 'eventos' ya está en orden cronológico de generación, así que revelar
    por índice preserva el orden narrativo (ej. un evento de preparación/transición -- ver
    services/simular_service.py -- siempre queda visible antes que el evento real que precede)
    sin depender de 'minuto':

        num_visibles = ceil(total_eventos * elapsed_segundos / duracion_segundos)

    Antes se mapeaba por 'minuto' (0' hasta 90'/120'): varios eventos suelen compartir el mismo
    'minuto' entero (sobre todo ahora que existen los eventos de preparación/transición, que a
    propósito comparten minuto con el evento que preceden) y aparecían todos de golpe en el
    mismo tick en vez de uno o varios cada cierto tiempo real.
    """
    elapsed_segundos = max(0.0, min((now - started_at).total_seconds(), duracion_segundos))
    finalizado_por_tiempo = elapsed_segundos >= duracion_segundos

    total_eventos = len(eventos)
    proporcion = (elapsed_segundos / duracion_segundos) if duracion_segundos > 0 else 1.0
    num_visibles = min(total_eventos, math.ceil(total_eventos * proporcion))

    eventos_visibles = eventos[:num_visibles]
    # Reloj de la transmisión: el minuto del último evento ya revelado (0 si todavía no se
    # reveló ninguno) -- queda sincronizado con lo que el usuario realmente está viendo, en vez
    # de una proyección lineal del minuto máximo independiente de qué eventos se muestran.
    minuto_visible_hasta = eventos_visibles[-1]["minuto"] if eventos_visibles else 0

    return {
        "elapsed_segundos": elapsed_segundos,
        "segundos_restantes": max(0.0, duracion_segundos - elapsed_segundos),
        "minuto_visible_hasta": minuto_visible_hasta,
        "eventos_visibles": eventos_visibles,
        "finalizado_por_tiempo": finalizado_por_tiempo,
    }


def instante_revelacion_evento(
    indice: int, total_eventos: int, started_at: datetime, duracion_segundos: int = DURACION_TRANSMISION_SEGUNDOS
) -> datetime:
    """
    Instante real en que calcular_estado_transmision revela el evento 'indice' (0-based): queda
    visible cuando ceil(total * elapsed / duracion) >= indice + 1, es decir apenas
    elapsed > indice * duracion / total. Lo usa el Juego en Vivo
    (services/juego_en_vivo_service.py) para saber qué multiplicador de riesgo regía cuando
    "ocurrió" cada evento, sin depender de cuándo hizo polling el usuario.
    """
    if total_eventos <= 0:
        return started_at
    return started_at + timedelta(seconds=indice * duracion_segundos / total_eventos)


def _marcador_parcial(eventos_visibles: List[Dict[str, Any]], nombre_local: str, nombre_visitante: str) -> Dict[str, int]:
    """
    Marcador PARCIAL derivado de los eventos ya revelados (nunca de 'resultado.goles_local/
    visitante', que ya es el resultado FINAL y no debe filtrarse antes de tiempo). Se filtra por
    'tipo' empezando con el emoji "⚽" (cubre "⚽ GOL" y "⚽ GOL DE PENAL") en vez de un substring
    "GOL" -- ese substring también matchea "🖥️ VAR - GOL ANULADO" (un gol anulado no debe sumar).
    """
    goles_local = sum(1 for e in eventos_visibles if e["equipo"] == nombre_local and e["tipo"].startswith("⚽"))
    goles_visitante = sum(1 for e in eventos_visibles if e["equipo"] == nombre_visitante and e["tipo"].startswith("⚽"))
    return {"goles_local": goles_local, "goles_visitante": goles_visitante}


def _disparar_efectos_pendientes(juego: Dict[str, Any]) -> None:
    """
    Corre los efectos secundarios (país, jugadores, rankings, aficionados, quinielas,
    dividendos, fantasy, sedes, avance de fase) que quedaron diferidos desde
    iniciar_simulacion_automatica -- se llama solo desde obtener_estado_live, y solo por el
    caller que ganó la carrera atómica sobre 'transmision.estado' (ver más abajo), así que se
    dispara exactamente una vez por partido.

    Limitación aceptada: si OTRO partido evalúa el avance de fase de su confederación mientras
    estos efectos siguen pendientes (ventana <= 5 min), verá 'internacional' desactualizado para
    los equipos de ESTE partido. Aceptable dado el tamaño de la ventana.
    """
    juego_id = str(juego["_id"])
    resultado = juego.get("resultado") or {}
    if not resultado:
        return

    id_local = (juego.get("equipo_local") or {}).get("id")
    id_visita = (juego.get("equipo_visitante") or {}).get("id")
    pendientes = juego.get("efectos_pendientes") or {}
    stats_jugadores = {item["jugador_id"]: item["stats"] for item in pendientes.get("stats_jugadores", [])}
    resp = {"exito": True, "resultado": resultado}
    estadisticas = juego.get("estadisticas", {})

    try:
        aplicar_efectos_secundarios(juego_id, id_local, id_visita, resp, estadisticas, stats_jugadores, juego_doc=juego)
    except Exception as e:
        logger.error(f"Error al aplicar efectos secundarios diferidos del partido {juego_id}: {str(e)}")
    finally:
        db["juegos"].update_one({"_id": juego["_id"]}, {"$unset": {"efectos_pendientes": ""}})


def obtener_estado_live() -> Optional[Dict[str, Any]]:
    """
    Orquesta GET /matches/live:
      - Si no hay ningún partido 'in_progress': devuelve None (el caller responde 404).
      - Si la ventana de transmisión ya venció: hace el flip 'transmision.estado' -> 'finished'
        (auto-finalize-on-read, no hay scheduler que lo haga proactivamente) y, si este caller
        ganó la carrera atómica sobre ese flip, dispara los efectos secundarios diferidos
        (_disparar_efectos_pendientes) antes de devolver el partido completo.
      - Si sigue en curso: devuelve el marcador y los eventos parciales.
    """
    juego = _match_en_progreso()
    if not juego:
        return None

    resultado = juego.get("resultado") or {}
    eventos = resultado.get("eventos", [])
    transmision = juego.get("transmision", {})
    nombre_local = (juego.get("equipo_local") or {}).get("nombre", "?")
    nombre_visitante = (juego.get("equipo_visitante") or {}).get("nombre", "?")
    bandera_local = (juego.get("equipo_local") or {}).get("bandera", "") or ""
    bandera_visitante = (juego.get("equipo_visitante") or {}).get("bandera", "") or ""
    # 'siglas' (ej. "ARG"), mismo campo/fallback que ya usa juegos_route.py::calendario() para
    # el título de los eventos del calendario -- si no está, se cae al nombre completo.
    siglas_local = (juego.get("equipo_local") or {}).get("siglas") or nombre_local
    siglas_visitante = (juego.get("equipo_visitante") or {}).get("siglas") or nombre_visitante
    grupo = juego.get("grupo")
    estadio = (juego.get("ubicacion") or {}).get("estadio")
    id_local = (juego.get("equipo_local") or {}).get("id")
    id_visita = (juego.get("equipo_visitante") or {}).get("id")

    estado_transmision = calcular_estado_transmision(
        eventos, transmision["started_at"], datetime.utcnow(), transmision.get("duracion_segundos", DURACION_TRANSMISION_SEGUNDOS)
    )

    if estado_transmision["finalizado_por_tiempo"]:
        flip = db["juegos"].update_one(
            {"_id": juego["_id"], "transmision.estado": TRANSMISION_EN_CURSO},
            {"$set": {"transmision.estado": TRANSMISION_FINALIZADA}}
        )
        if flip.modified_count > 0:
            _disparar_efectos_pendientes(juego)

    marcador = _marcador_parcial(estado_transmision["eventos_visibles"], nombre_local, nombre_visitante)

    return {
        "match_id": str(juego["_id"]),
        "local": nombre_local,
        "visitante": nombre_visitante,
        "bandera_local": bandera_local,
        "bandera_visitante": bandera_visitante,
        "siglas_local": siglas_local,
        "siglas_visitante": siglas_visitante,
        "grupo": grupo,
        "estadio": estadio,
        "fecha": formatear_fecha_es(juego.get("fecha")) if juego.get("fecha") else None,
        "hora": juego.get("hora"),
        "aforo": juego.get("aforo"),
        "confederacion_id": juego.get("confederacion_id"),
        "fase_id": juego.get("fase_id"),
        "id_local": id_local,
        "id_visita": id_visita,
        "goles_local": marcador["goles_local"],
        "goles_visitante": marcador["goles_visitante"],
        "minuto_actual": int(round(estado_transmision["minuto_visible_hasta"])),
        "eventos": estado_transmision["eventos_visibles"],
        "segundos_transcurridos": estado_transmision["elapsed_segundos"],
        "segundos_restantes": estado_transmision["segundos_restantes"],
        "finalizado": estado_transmision["finalizado_por_tiempo"],
    }


def obtener_tabla_grupo_partido_en_vivo() -> Optional[Dict[str, Any]]:
    """
    Tabla de posiciones del grupo al que pertenece el partido actualmente en transmisión, para
    el panel lateral de /en-vivo/. Se apoya en clasificacion_service.obtener_tabla_grupo_de_equipo
    (ya ordenada por el criterio reglamentario) y enriquece cada equipo con 'siglas' -- ese campo
    no lo trae la función de clasificación porque no lo necesita para nada más.

    Devuelve None si no hay ningún partido en curso. Si el partido está en una fase sin tabla de
    grupos (eliminación directa), 'grupo' viaja en None y 'equipos' vacío -- el caller decide si
    ocultar el panel en ese caso.
    """
    juego = _match_en_progreso()
    if not juego:
        return None

    confederacion_id = juego.get("confederacion_id")
    fase_id = juego.get("fase_id")
    id_local = (juego.get("equipo_local") or {}).get("id")
    id_visita = (juego.get("equipo_visitante") or {}).get("id")

    grupo, equipos = obtener_tabla_grupo_de_equipo(db, fase_id, confederacion_id, id_local)

    if equipos:
        ids_paises = [equipo["pais_id"] for equipo in equipos]
        siglas_por_id = {
            p["id"]: p.get("siglas", "") for p in db["paises"].find({"id": {"$in": ids_paises}}, {"id": 1, "siglas": 1})
        }
        for equipo in equipos:
            equipo["siglas"] = siglas_por_id.get(equipo["pais_id"], "")

    return {
        "match_id": str(juego["_id"]),
        "grupo": grupo,
        "id_local": id_local,
        "id_visita": id_visita,
        "equipos": equipos,
    }


def obtener_posiciones_plantillas_en_vivo() -> Optional[Dict[str, Any]]:
    """
    Datos de plantilla de AMBOS equipos del partido en transmisión, pedidos UNA sola vez por
    partido (no en cada poll de 3s) por el frontend (Cancha en Vivo, templates/live_match.html):

    - 'jugadores': mapa nombre de jugador -> sigla de posición granular (colección 'posiciones',
      ej. "LD", "MC", "ED" -- esquema distinto al 1-4 simplificado que usa el motor de
      simulación internamente vía 'linea_partido', ver CLAUDE.md), de TODA la plantilla de
      ambos países (titulares + suplentes).
    - 'titulares_local' / 'titulares_visitante': nombres del 11 inicial de cada equipo (ver
      services/simular_service.py, persistidos en 'juego.resultado' por
      services/juegos_service.py::registrar_resultado_juego) -- para que el frontend sepa quién
      arranca en cancha y pueda ir actualizando esa lista en vivo a medida que se revelan
      sustituciones/expulsiones.

    Existe porque los eventos de 'resultado.eventos' solo llevan el NOMBRE del jugador
    (services/simular_service.py::construir_evento, campo 'jugadores': List[str]) -- a
    propósito así, para no romper resaltar_jugadores_en_descripcion (hace match de string
    exacto contra la descripción).

    Devuelve None si no hay ningún partido en curso.
    """
    juego = _match_en_progreso()
    if not juego:
        return None

    id_local = (juego.get("equipo_local") or {}).get("id")
    id_visita = (juego.get("equipo_visitante") or {}).get("id")

    posiciones_por_id = {
        p["id"]: p.get("siglas", "") for p in db["posiciones"].find({}, {"id": 1, "siglas": 1})
    }
    jugadores = list(db["jugadores"].find(
        {"pais_id": {"$in": [id_local, id_visita]}}, {"nombre": 1, "posicion_id": 1, "numero": 1}
    ))
    resultado = juego.get("resultado") or {}
    # Táctica persistida por registrar_resultado_juego; el 11 titular viene en el orden de
    # FORMACIONES[tactica] (ver seleccionar_plantilla_titular), así que la línea de cada titular
    # (1 POR, 2 DEF, 3 MED, 4 DEL) es la del mismo índice en esa formación.
    tactica_local = (juego.get("equipo_local") or {}).get("tactica") or "4-3-3"
    tactica_visitante = (juego.get("equipo_visitante") or {}).get("tactica") or "4-3-3"
    return {
        "jugadores": {j["nombre"]: posiciones_por_id.get(j.get("posicion_id"), "") for j in jugadores},
        "dorsales": {j["nombre"]: j.get("numero") for j in jugadores if j.get("numero") is not None},
        "titulares_local": resultado.get("titulares_local", []),
        "titulares_visitante": resultado.get("titulares_visitante", []),
        "tactica_local": tactica_local,
        "tactica_visitante": tactica_visitante,
        "lineas_local": FORMACIONES.get(tactica_local, FORMACIONES["4-3-3"]),
        "lineas_visitante": FORMACIONES.get(tactica_visitante, FORMACIONES["4-3-3"]),
    }
