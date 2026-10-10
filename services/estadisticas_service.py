from bson.objectid import ObjectId
from collections import defaultdict
from pymongo.database import Database
from typing import Dict, Optional
import certifi
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

def obtener_estadisticas_generales():
    """Retorna un diccionario completo con todas las métricas históricas y del torneo."""
    # Una sola consulta (con proyección liviana) para los récords por partido y las tendencias
    # del torneo -- ver sección 4b.
    juegos_records = _juegos_finalizados_para_records()
    partidos = _get_stats_partidos()
    partidos.update(_obtener_records_primer_gol(juegos_records))
    partidos["sede_mas_goleadora"] = _obtener_sede_mas_goleadora(juegos_records)
    return {
        "jugadores": _get_stats_jugadores(),
        "porteros": _get_stats_porteros(),
        "arbitros": _get_stats_arbitros(),
        "arbitros_avanzado": _get_stats_arbitros_avanzado(juegos_records),
        "partidos": partidos,
        "tendencias": _get_stats_tendencias(juegos_records),
        "paises": _get_stats_paises(),
        "torneos": _get_stats_torneos(),
        "once_ideal": _get_11_ideal()
    }

# ==========================================
# 1. ESTADÍSTICAS DE JUGADORES Y RACHAS
# ==========================================
def _get_stats_jugadores():
    jugadores_coll = db["jugadores"]
    paises_coll = db["paises"]

    # Jugadores destacados directos de la colección 'jugadores'.
    # Proyectan 'pais_id' (el campo real) en vez de 'pais' (nunca existió en 'jugadores' —
    # el país se guarda como id numérico, resuelto más abajo con un solo lookup en batch).
    mas_partidos = jugadores_coll.find_one({}, {
            "_id": 0,
            "nombre": 1,
            "pais_id": 1,
            "juegos_jugados": 1
        }, sort=[("juegos_jugados", -1)])

    mas_goles = jugadores_coll.find_one({},{
            "_id": 0,
            "id": 1,
            "nombre": 1,
            "pais_id": 1,
            "goles": 1
        }, sort=[("goles", -1)])

    mas_amarillas = jugadores_coll.find_one({}, {
            "_id": 0,
            "nombre": 1,
            "pais_id": 1,
            "amarilla": 1
        }, sort=[("amarilla", -1)])

    mas_rojas = jugadores_coll.find_one({}, {
            "_id": 0,
            "nombre": 1,
            "pais_id": 1,
            "roja": 1
        }, sort=[("roja", -1)])

    mas_faltas = jugadores_coll.find_one({}, {
            "_id": 0,
            "nombre": 1,
            "pais_id": 1,
            "faltas": 1
        }, sort=[("faltas", -1)])

    # Jugador con mejor % de conversión de gol (goles / disparos totales)
    mejor_efectividad_gol = _obtener_mejor_efectividad_gol(jugadores_coll)

    # Jugador más infringido (víctima): el que más faltas RECIBIÓ, no el que más cometió
    mas_infringido = jugadores_coll.find_one({}, {
            "_id": 0,
            "nombre": 1,
            "pais_id": 1,
            "faltas_recibidas": 1
        }, sort=[("faltas_recibidas", -1)])

    # Resolución en batch de pais_id -> nombre (un solo find en vez de 7 lookups sueltos),
    # y se le agrega el campo 'pais' a cada líder para no romper el contrato con la vista.
    lideres = [mas_partidos, mas_goles, mas_amarillas, mas_rojas, mas_faltas, mejor_efectividad_gol, mas_infringido]
    ids_paises = {l["pais_id"] for l in lideres if l and l.get("pais_id") is not None}
    nombres_paises = {p["id"]: p.get("nombre", "?") for p in paises_coll.find({"id": {"$in": list(ids_paises)}}, {"id": 1, "nombre": 1})}
    for lider in lideres:
        if lider:
            lider["pais"] = nombres_paises.get(lider.get("pais_id"), "?")

    # Partidos donde el máximo goleador anotó, para el modal de "ver partidos" de esa tarjeta
    if mas_goles and mas_goles.get("id") is not None:
        mas_goles["partidos"] = _obtener_partidos_jugador_por_evento(mas_goles["id"], "goleadores")

    # Racha de partidos seguidos anotando (procesando 'juegos')
    racha_goles = _obtener_mayor_racha_goles()
    if racha_goles.get("jugador_id") is not None:
        racha_goles["partidos"] = _obtener_partidos_jugador_por_evento(racha_goles["jugador_id"], "goleadores")
        
    # Jugador con mas asistencias, se obtiene desde jugadores
    mas_asistencias = jugadores_coll.find_one({}, {
            "_id": 0,
            "nombre": 1,
            "pais_id": 1,
            "asistencias": 1,
            "pais": 1
        }, sort=[("asistencias", -1)])

    # Súper Sub: jugador con más goles anotados en partidos donde entró de cambio
    super_sub = _obtener_super_sub()
    
    # Obtener el jugador con mejor juego aereo
    mejor_juego_aereo = jugadores_coll.find_one({}, {
            "_id": 0,
            "nombre": 1,
            "pais_id": 1,
            "juego_aereo": 1,
            "pais": 1
        }, sort=[("juego_aereo", -1)])

    # Jugador con mas recuperaciones de balón, se obtiene desde jugadores
    mas_recuperaciones = jugadores_coll.find_one({}, {
            "_id": 0,
            "nombre": 1,
            "pais_id": 1,
            "recuperaciones": 1,
            "pais": 1
        }, sort=[("recuperaciones", -1)])

    # Especialista a Balón Parado: jugador con más goles de penal en tandas de definición
    # (único tipo de balón parado -- de tiro libre/penal/córner -- que existe en el motor)
    especialista_balon_parado = _obtener_especialista_balon_parado()

    return {
        "mas_partidos": mas_partidos,
        "mas_goles": mas_goles,
        "mas_amarillas": mas_amarillas,
        "mas_rojas": mas_rojas,
        "mas_faltas": mas_faltas,
        "mayor_racha_goles": racha_goles,
        "mas_asistencias": mas_asistencias,
        "super_sub": super_sub,
        "mejor_efectividad_gol": mejor_efectividad_gol,
        "especialista_aereo": mejor_juego_aereo,
        "mas_infringido": mas_infringido,
        "mas_recuperaciones": mas_recuperaciones,
        "especialista_balon_parado": especialista_balon_parado
    }

# Mínimo de disparos totales para calificar al ranking de efectividad de gol -- evita que un
# jugador con, por ejemplo, 1 disparo y 1 gol (100%) encabece el ranking sin ser representativo.
MINIMO_TIROS_EFECTIVIDAD_GOL = 5

def _obtener_mejor_efectividad_gol(jugadores_coll):
    """
    Jugador con mejor % de conversión de gol (goles / disparos totales) de todo el torneo.
    'disparos totales' = 'tiros_puerta' + 'tiros_desviados', contadores de carrera acumulados
    en 'jugadores' por services/jugadores_service.py::actualizar_jugadores_post_partido junto
    al resto de stats de partido -- antes de este cambio esos dos campos se calculaban por
    partido en el motor de simulación pero se descartaban ahí mismo, nunca se persistían (mismo
    caveat que 'entro_de_cambio' para Súper Sub: solo cuenta desde los próximos partidos
    simulados en adelante; los jugadores viejos no tienen estos campos hasta que vuelvan a jugar).
    """
    pipeline = [
        {
            "$project": {
                "nombre": 1,
                "pais_id": 1,
                "goles": 1,
                "tiros_totales": {
                    "$add": [{"$ifNull": ["$tiros_puerta", 0]}, {"$ifNull": ["$tiros_desviados", 0]}]
                }
            }
        },
        {"$match": {"tiros_totales": {"$gte": MINIMO_TIROS_EFECTIVIDAD_GOL}}},
        {"$addFields": {
            "efectividad_gol": {"$round": [{"$multiply": [{"$divide": ["$goles", "$tiros_totales"]}, 100]}, 1]}
        }},
        {"$sort": {"efectividad_gol": -1}},
        {"$limit": 1}
    ]
    resultados = list(jugadores_coll.aggregate(pipeline))
    if not resultados:
        return None

    top = resultados[0]
    return {
        "nombre": top.get("nombre"),
        "pais_id": top.get("pais_id"),
        "goles": top.get("goles", 0),
        "tiros_totales": top.get("tiros_totales", 0),
        "efectividad_gol": top.get("efectividad_gol", 0)
    }

def _obtener_super_sub():
    """
    Jugador con más goles anotados (sumando TODO el torneo) en partidos donde entró de cambio.
    Usa 'resultado.goleadores[].entro_de_cambio' -- flag agregado a la construcción de
    'goleadores' en services/juegos_service.py junto al resto de sus campos estructurados
    (mismo patrón que 'resultado.goleadores'/'resultado.participantes', ver
    _obtener_mayor_racha_goles). Los partidos simulados ANTES de agregar ese flag no lo tienen
    guardado y no participan en el conteo -- no hay forma de reconstruirlo retroactivamente.
    """
    juegos_coll = db["juegos"]
    juegos = juegos_coll.find(
        {"estado": "finalizado", "resultado.goleadores.entro_de_cambio": True},
        {"resultado.goleadores": 1}
    )

    goles_por_jugador = defaultdict(lambda: {"nombre": None, "equipo": None, "goles": 0})
    for juego in juegos:
        for g in (juego.get("resultado") or {}).get("goleadores") or []:
            if not g.get("entro_de_cambio"):
                continue
            registro = goles_por_jugador[g["jugador_id"]]
            registro["nombre"] = g.get("jugador_nombre", "?")
            registro["equipo"] = g.get("equipo", "?")
            registro["goles"] += g.get("goles", 0)

    if not goles_por_jugador:
        return None

    top_id, top = max(goles_por_jugador.items(), key=lambda kv: kv[1]["goles"])
    return {
        "nombre": top["nombre"],
        "pais": top["equipo"],
        "goles": top["goles"],
        "partidos": _obtener_partidos_super_sub(top_id)
    }


def _obtener_partidos_super_sub(jugador_id: int) -> list:
    """
    Partidos finalizados donde 'jugador_id' anotó habiendo entrado de cambio, para el modal de
    "ver partidos" de la tarjeta Súper Sub -- mismo patrón que
    _obtener_partidos_jugador_por_evento, pero exige que AMBAS condiciones (el jugador y el
    flag 'entro_de_cambio') valgan sobre el MISMO elemento del array 'goleadores' ($elemMatch),
    no sobre elementos distintos de la lista.
    """
    juegos_coll = db["juegos"]
    juegos = juegos_coll.find(
        {
            "estado": "finalizado",
            "resultado.goleadores": {"$elemMatch": {"jugador_id": jugador_id, "entro_de_cambio": True}}
        },
        {
            "equipo_local": 1, "equipo_visitante": 1, "tag": 1, "fecha": 1,
            "resultado.goles_local": 1, "resultado.goles_visitante": 1
        }
    ).sort("fecha", 1)
    return [
        _formatear_partido_resumen(
            j, (j.get("resultado") or {}).get("goles_local", 0) or 0, (j.get("resultado") or {}).get("goles_visitante", 0) or 0
        )
        for j in juegos
    ]


def _obtener_especialista_balon_parado():
    """
    Jugador con más goles de balón parado -- tiro libre + penal + córner sumados -- de TODO el
    torneo. Los tres son jugadas reales en el motor de simulación (ver
    services/simular_service.py::ejecutar_tiro_libre/ejecutar_penal/ejecutar_corner).

    Usa 'resultado.goleadores[].{goles_tiro_libre,goles_penal,goles_corner}' -- campos
    agregados junto al resto de campos estructurados de 'goleadores' en
    services/juegos_service.py (mismo patrón que 'entro_de_cambio' para Súper Sub, ver
    _obtener_super_sub). Los partidos simulados ANTES de agregar estos campos no los tienen
    guardados y no participan en el conteo -- no hay forma de reconstruirlo retroactivamente.
    """
    juegos_coll = db["juegos"]
    juegos = juegos_coll.find(
        {
            "estado": "finalizado",
            "$or": [
                {"resultado.goleadores.goles_tiro_libre": {"$gt": 0}},
                {"resultado.goleadores.goles_penal": {"$gt": 0}},
                {"resultado.goleadores.goles_corner": {"$gt": 0}}
            ]
        },
        {"resultado.goleadores": 1}
    )

    goles_por_jugador = defaultdict(lambda: {"nombre": None, "equipo": None, "goles": 0})
    for juego in juegos:
        for g in (juego.get("resultado") or {}).get("goleadores") or []:
            goles_balon_parado = g.get("goles_tiro_libre", 0) + g.get("goles_penal", 0) + g.get("goles_corner", 0)
            if not goles_balon_parado:
                continue
            registro = goles_por_jugador[g["jugador_id"]]
            registro["nombre"] = g.get("jugador_nombre", "?")
            registro["equipo"] = g.get("equipo", "?")
            registro["goles"] += goles_balon_parado

    if not goles_por_jugador:
        return None

    top_id, top = max(goles_por_jugador.items(), key=lambda kv: kv[1]["goles"])
    return {
        "nombre": top["nombre"],
        "pais": top["equipo"],
        "goles": top["goles"],
        "partidos": _obtener_partidos_especialista_balon_parado(top_id)
    }


def _obtener_partidos_especialista_balon_parado(jugador_id: int) -> list:
    """
    Partidos finalizados donde 'jugador_id' anotó al menos un gol de tiro libre, penal o
    córner, para el modal de "ver partidos" de la tarjeta Especialista a Balón Parado --
    mismo patrón que _obtener_partidos_super_sub ($elemMatch para exigir que el jugador y AL
    MENOS uno de los tres tipos de gol valgan sobre el MISMO elemento del array).
    """
    juegos_coll = db["juegos"]
    juegos = juegos_coll.find(
        {
            "estado": "finalizado",
            "resultado.goleadores": {
                "$elemMatch": {
                    "jugador_id": jugador_id,
                    "$or": [
                        {"goles_tiro_libre": {"$gt": 0}},
                        {"goles_penal": {"$gt": 0}},
                        {"goles_corner": {"$gt": 0}}
                    ]
                }
            }
        },
        {
            "equipo_local": 1, "equipo_visitante": 1, "tag": 1, "fecha": 1,
            "resultado.goles_local": 1, "resultado.goles_visitante": 1
        }
    ).sort("fecha", 1)
    return [
        _formatear_partido_resumen(
            j, (j.get("resultado") or {}).get("goles_local", 0) or 0, (j.get("resultado") or {}).get("goles_visitante", 0) or 0
        )
        for j in juegos
    ]

def _obtener_mayor_racha_goles():
    """
    Calcula la racha más larga de partidos consecutivos (JUGADOS) en los que un jugador
    anotó gol.

    Usa dos listas estructuradas que routes/simular_route.py arma desde 'stats_jugadores'
    y guarda en cada partido al finalizarlo (no se parsea texto de 'resultado.eventos'):
      - 'resultado.goleadores': quiénes anotaron.
      - 'resultado.participantes': TODOS los jugadores que jugaron ese partido (titulares +
        suplentes que entraron), estén o no en 'goleadores'.
    'participantes' es necesario para poder distinguir "jugó este partido pero no anotó"
    (corta la racha) de "no jugó este partido" (no participa) — sin esa lista, dos partidos
    en los que un jugador anotó pero que en el medio tuvo partidos sin anotar entre uno y
    otro se contaban igual que si hubiera anotado en partidos realmente consecutivos.

    NOTA: los partidos simulados ANTES de este fix no tienen 'participantes' guardado (ese
    campo no existía todavía), así que no participan en el cálculo — no hay forma de
    reconstruir retroactivamente quién jugó esos partidos.
    """
    juegos_coll = db["juegos"]

    juegos = list(juegos_coll.find(
        {"estado": "finalizado", "resultado.participantes": {"$exists": True, "$ne": []}},
        {"fecha": 1, "resultado.goleadores": 1, "resultado.participantes": 1}
    ).sort("fecha", 1))

    # Mapa: jugador_id -> {'nombre': str, 'racha_actual': x, 'max_racha': y}
    historial_jugadores = defaultdict(lambda: {"nombre": None, "racha_actual": 0, "max_racha": 0})

    for juego in juegos:
        resultado = juego.get("resultado", {})
        participantes = resultado.get("participantes", [])
        goleadores = resultado.get("goleadores", [])
        nombres_por_goleador = {g["jugador_id"]: g.get("jugador_nombre", "?") for g in goleadores if g.get("jugador_id") is not None}

        for jugador_id in participantes:
            registro = historial_jugadores[jugador_id]
            if jugador_id in nombres_por_goleador:
                registro["nombre"] = nombres_por_goleador[jugador_id]
                registro["racha_actual"] += 1
                if registro["racha_actual"] > registro["max_racha"]:
                    registro["max_racha"] = registro["racha_actual"]
            else:
                # Jugó este partido y no anotó: corta la racha
                registro["racha_actual"] = 0

    # Obtener el líder de la racha (jugador_id es la propia clave del dict, se necesita para
    # poder buscar después en qué partidos concretos anotó -- ver _obtener_partidos_jugador_por_evento)
    top_racha_id, top_racha = max(
        historial_jugadores.items(), key=lambda kv: kv[1]["max_racha"],
        default=(None, {"nombre": None, "max_racha": 0})
    )
    return {"jugador": top_racha["nombre"], "jugador_id": top_racha_id, "partidos_consecutivos": top_racha["max_racha"]}

# ==========================================
# 2. ESTADÍSTICAS DE PORTEROS (Vía 'eventos' y 'jugadores')
# ==========================================
def _get_stats_porteros():
    juegos_coll = db["juegos"]
    jugadores_coll = db["jugadores"]
    paises_coll = db["paises"]
    posiciones_coll = db["posiciones"]

    # Posiciones granulares reales cuyo 'sector' es Portero (colección 'posiciones' —
    # 'jugadores' no tiene un campo 'posicion'/'equipo' de texto, solo 'posicion_id'/'pais_id').
    ids_posicion_portero = [p["id"] for p in posiciones_coll.find({"sector": "Portero"}, {"id": 1})]

    # 1. Portero con más atajadas ACUMULADAS. Antes se armaba agrupando eventos de 'juegos'
    #    por 'resultado.eventos.jugador' — un campo que el motor de simulación nunca guarda
    #    (los eventos solo tienen minuto/equipo/tipo/descripcion) — así que el $ifNull caía
    #    siempre a la descripción completa de la jugada en vez de un nombre. Ahora se usa el
    #    contador acumulado real en 'jugadores.atajadas' (ver jugadores_service.py).
    portero_mas_atajadas = None
    if ids_posicion_portero:
        top_atajadas = jugadores_coll.find_one(
            {"posicion_id": {"$in": ids_posicion_portero}, "atajadas": {"$gt": 0}},
            {"id": 1, "nombre": 1, "pais_id": 1, "atajadas": 1},
            sort=[("atajadas", -1)]
        )
        if top_atajadas:
            pais_doc = paises_coll.find_one({"id": top_atajadas.get("pais_id")}, {"nombre": 1})
            portero_mas_atajadas = {
                "portero": top_atajadas.get("nombre"),
                "equipo": pais_doc.get("nombre", "?") if pais_doc else "?",
                "total_atajadas": top_atajadas.get("atajadas", 0),
                # Partidos donde este portero atajó, para el modal de "ver partidos" de la
                # tarjeta Guante de Oro (ver _obtener_partidos_jugador_por_evento)
                "partidos": _obtener_partidos_jugador_por_evento(top_atajadas["id"], "atajadores") if top_atajadas.get("id") is not None else []
            }

    # 2. Portero con más juegos sin recibir gol (Valla Invicta Individual), aproximado por
    #    país (no hay registro de qué portero puntual atajó cada partido). Antes filtraba
    #    'jugadores' por un campo 'posicion' (string) que no existe — solo existe
    #    'posicion_id' (numérico) — así que nunca encontraba porteros y siempre daba N/A.
    pipeline_clean_sheets = [
        {"$match": {"estado": "finalizado"}},
        {
            "$project": {
                "valla_invicta_local": {"$eq": ["$resultado.goles_visitante", 0]},
                "valla_invicta_visitante": {"$eq": ["$resultado.goles_local", 0]},
                "local_id": "$equipo_local.id",
                "visitante_id": "$equipo_visitante.id"
            }
        }
    ]

    vallas_por_pais: Dict[int, int] = defaultdict(int)
    for juego in juegos_coll.aggregate(pipeline_clean_sheets):
        if juego["valla_invicta_local"]:
            vallas_por_pais[juego["local_id"]] += 1
        if juego["valla_invicta_visitante"]:
            vallas_por_pais[juego["visitante_id"]] += 1

    top_portero_valla = {"portero": "N/A", "pais": "N/A", "partidos_sin_recibir_gol": 0}
    if ids_posicion_portero and vallas_por_pais:
        porteros = list(jugadores_coll.find(
            {"posicion_id": {"$in": ids_posicion_portero}, "pais_id": {"$in": list(vallas_por_pais.keys())}},
            {"nombre": 1, "pais_id": 1}
        ))
        if porteros:
            nombres_paises = {p["id"]: p.get("nombre", "?") for p in paises_coll.find({"id": {"$in": list(vallas_por_pais.keys())}}, {"id": 1, "nombre": 1})}
            mejor = max(porteros, key=lambda p: vallas_por_pais.get(p["pais_id"], 0))
            top_portero_valla = {
                "portero": mejor.get("nombre"),
                "pais": nombres_paises.get(mejor["pais_id"], "?"),
                "partidos_sin_recibir_gol": vallas_por_pais.get(mejor["pais_id"], 0)
            }

    # Portero con más penales atajados (contador 'atajadas_penales' de jugadores, que solo crece
    # en tandas de penales). Antes se ordenaba por 'penales_atajados' -- campo inexistente -- y
    # se devolvía 'nombre' en vez de las claves 'portero'/'total' que lee el template.
    portero_mas_penales = None
    top_penales = jugadores_coll.find_one(
        {"atajadas_penales": {"$gt": 0}}, {"nombre": 1, "pais_id": 1, "atajadas_penales": 1},
        sort=[("atajadas_penales", -1)]
    )
    if top_penales:
        pais_doc = paises_coll.find_one({"id": top_penales.get("pais_id")}, {"nombre": 1})
        portero_mas_penales = {
            "portero": top_penales.get("nombre"),
            "pais": pais_doc.get("nombre", "?") if pais_doc else "?",
            "total": top_penales.get("atajadas_penales", 0),
        }

    return {
        "atajapenales": portero_mas_penales,
        "portero_mas_atajadas": portero_mas_atajadas,
        "portero_mas_vallas_invictas": top_portero_valla
    }

# ==========================================
# 3. ÁRBITROS CON MÁS JUEGOS PITADOS
# ==========================================
def _get_stats_arbitros():
    def _top_arbitro(rol_field):
        juegos_coll = db["juegos"]
        pipeline = [
            {"$match": {"estado": "finalizado", f"resultado.arbitros.{rol_field}": {"$ne": None}}},
            {"$group": {"_id": f"$resultado.arbitros.{rol_field}", "juegos": {"$sum": 1}}},
            {"$sort": {"juegos": -1}},
            {"$limit": 1}
        ]
        res = list(juegos_coll.aggregate(pipeline))
        # Se renombra '_id' (nombre crudo del $group de Mongo) a 'nombre', para no filtrar
        # un detalle de implementación de la agregación hacia el template.
        return {"nombre": res[0]["_id"], "juegos": res[0]["juegos"]} if res else None

    return {
        "central": _top_arbitro("central"),
        "linea1": _top_arbitro("linea1"),
        "linea2": _top_arbitro("linea2"),
        "cuarto": _top_arbitro("cuarto")
    }

# ==========================================
# 4. PARTIDOS DESTACADOS Y ESTADIOS
# ==========================================
def _formatear_partido_resumen(juego: dict, goles_local: int, goles_visitante: int) -> dict:
    """
    Resumen liviano de un partido (id/tag/fecha/equipos+goles) para listar en los modales de
    "ver partidos" de las tarjetas de Estadio Más Frecuente / País Más Remontador. Recibe
    'goles_local'/'goles_visitante' ya calculados por el caller (en vez de leer
    juego['resultado'] de nuevo acá) porque en '_get_stats_partidos' la clave 'resultado'
    puede haber sido borrada del mismo dict 'juego' más arriba en el loop (ver nota sobre
    referencias compartidas ahí) — 'equipo_local'/'equipo_visitante'/'_id'/'tag'/'fecha' en
    cambio nunca se borran, así que esos sí se leen directo del documento.
    """
    equipo_local = juego.get("equipo_local") or {}
    equipo_visitante = juego.get("equipo_visitante") or {}
    return {
        "id": str(juego["_id"]),
        "tag": juego.get("tag"),
        "fecha": juego.get("fecha"),
        "equipo_local": {
            "nombre": equipo_local.get("nombre"),
            "bandera": equipo_local.get("bandera"),
            "goles": goles_local
        },
        "equipo_visitante": {
            "nombre": equipo_visitante.get("nombre"),
            "bandera": equipo_visitante.get("bandera"),
            "goles": goles_visitante
        }
    }


def _obtener_partidos_jugador_por_evento(jugador_id: int, campo: str) -> list:
    """
    Partidos finalizados donde 'jugador_id' aparece en 'resultado.<campo>' (lista de eventos
    estructurados por jugador -- 'goleadores' o 'atajadores', ver rutes/simular_route.py y
    services/juegos_service.registrar_resultado_juego), para los modales de "ver partidos" de
    las tarjetas de líderes individuales (Máximo Goleador, Guante de Oro, Mayor Racha Gol) en
    la sección 'Líderes Individuales' -- mismo patrón que estadio_mas_frecuente/pais_mas_remontador
    más abajo en este archivo.

    NOTA: al igual que 'participantes' (ver _obtener_mayor_racha_goles), estos campos solo
    existen en partidos simulados después de que se agregaron -- los partidos viejos no
    aparecen acá aunque el jugador haya anotado/atajado en ellos.
    """
    juegos_coll = db["juegos"]
    juegos = juegos_coll.find(
        {"estado": "finalizado", f"resultado.{campo}.jugador_id": jugador_id},
        {
            "equipo_local": 1, "equipo_visitante": 1, "tag": 1, "fecha": 1,
            "resultado.goles_local": 1, "resultado.goles_visitante": 1
        }
    ).sort("fecha", 1)
    return [
        _formatear_partido_resumen(
            j, (j.get("resultado") or {}).get("goles_local", 0) or 0, (j.get("resultado") or {}).get("goles_visitante", 0) or 0
        )
        for j in juegos
    ]


def _get_stats_partidos():
    juegos_coll = db["juegos"]

    # Partidos con más goles (Tiempo Regular vs Tiempo Extra vs Penales)
    juegos_finalizados = list(juegos_coll.find({"estado": "finalizado"}))

    mas_goles_regular = None
    mas_goles_extra = None
    mas_goles_penales = None

    max_reg = -1
    max_ext = -1
    max_pen = -1

    # Remontadas: lista global (todos los partidos con remontada) + agrupados por país ganador,
    # para poder mostrar en el modal justo los partidos del país que más remontó.
    partidos_remontada = []
    remontadas_por_pais = defaultdict(list)

    # Estadio con más partidos jugados, acumulado en el mismo loop que recorre 'juegos_finalizados'
    # de todas formas (antes era una segunda consulta con $group aparte) -- también deja armada
    # la lista de partidos de ese estadio para el modal de "ver partidos".
    #
    # OJO: se agrupa por CIUDAD ('ubicacion.id', el id real y único de la ciudad en la colección
    # 'ciudades'), NO por el nombre del estadio a secas -- varias ciudades/países distintos
    # pueden tener un estadio con el mismo nombre (ej. varios "Estadio Nacional"), y agrupar
    # solo por texto los mezclaba como si fuera un único estadio. Se guarda un fallback a
    # (estadio, país) por si algún documento viejo no tuviera 'ubicacion.id' persistido.
    partidos_por_estadio = defaultdict(lambda: {"estadio": None, "ciudad": None, "pais": None, "partidos": []})

    # Juego sucio / limpio
    juego_mas_sucio = None
    juego_mas_limpio = None
    max_tarjetas = -1
    min_tarjetas = 999

    # Partido con más aforo (asistencia real, ver juegos_service.calcular_asistencia). Solo
    # participan los partidos que ya tienen 'aforo' persistido (se genera recién al entrar al
    # simulador de ese partido, ver routes/simular_route.py) -- si ninguno lo tiene, queda None.
    partido_mayor_aforo = None
    max_aforo = -1

    for j in juegos_finalizados:
        res = j.get("resultado", {})
        gl = res.get("goles_local", 0) or 0
        gv = res.get("goles_visitante", 0) or 0
        pl = res.get("penaltis_local", 0) or 0
        pv = res.get("penaltis_visitante", 0) or 0

        # Se captura antes de que el bloque de "destacados" de más abajo pueda borrar la
        # clave 'ubicacion' de este mismo dict 'j' (ver nota sobre referencias compartidas).
        ubicacion = j.get("ubicacion") or {}
        nombre_estadio = ubicacion.get("estadio")
        if nombre_estadio:
            clave_estadio = ubicacion.get("id")
            if clave_estadio is None:
                clave_estadio = (nombre_estadio, ubicacion.get("pais"))
            grupo_estadio = partidos_por_estadio[clave_estadio]
            grupo_estadio["estadio"] = nombre_estadio
            grupo_estadio["ciudad"] = ubicacion.get("nombre")
            grupo_estadio["pais"] = ubicacion.get("pais")
            grupo_estadio["partidos"].append(_formatear_partido_resumen(j, gl, gv))

        # Se captura antes de que el bloque de "destacados" de más abajo pueda borrar
        # 'resultado' de este mismo dict 'j' (mismo motivo que 'ubicacion' arriba).
        aforo = j.get("aforo") or {}
        asistencia = aforo.get("asistencia", 0) or 0
        if aforo and asistencia > max_aforo:
            max_aforo = asistencia
            partido_mayor_aforo = j
            partido_mayor_aforo["_id"] = str(partido_mayor_aforo["_id"])
            if "resultado" in partido_mayor_aforo: del partido_mayor_aforo["resultado"]
            if "estadisticas" in partido_mayor_aforo: del partido_mayor_aforo["estadisticas"]
            if "ubicacion" in partido_mayor_aforo: del partido_mayor_aforo["ubicacion"]
            partido_mayor_aforo["goles_local"] = gl
            partido_mayor_aforo["goles_visitante"] = gv

        tot_regular = gl + gv
        tot_penales = tot_regular + pl + pv

        # Evaluaciones de goles.
        # OJO: un mismo partido "j" puede calificar para más de un "destacado" a la vez
        # (ej. ser a la vez el de más goles en tiempo normal Y en tiempo extra) — en ese
        # caso dos variables distintas terminan apuntando al MISMO dict, así que los "del"
        # van guardados con "in" (si el otro bloque ya borró la clave, no vuelve a intentarlo).
        if tot_regular > max_reg:
            max_reg = tot_regular
            mas_goles_regular = j
            mas_goles_regular["_id"] = str(mas_goles_regular["_id"])
            if "resultado" in mas_goles_regular: del mas_goles_regular["resultado"]
            if "estadisticas" in mas_goles_regular: del mas_goles_regular["estadisticas"]
            if "ubicacion" in mas_goles_regular: del mas_goles_regular["ubicacion"]

        if j.get("tiempo_extra") and tot_regular > max_ext:
            max_ext = tot_regular
            mas_goles_extra = j
            mas_goles_extra["_id"] = str(mas_goles_extra["_id"])
            if "resultado" in mas_goles_extra: del mas_goles_extra["resultado"]
            if "estadisticas" in mas_goles_extra: del mas_goles_extra["estadisticas"]
            if "ubicacion" in mas_goles_extra: del mas_goles_extra["ubicacion"]

        if (pl + pv) > 0 and tot_penales > max_pen:
            max_pen = tot_penales
            mas_goles_penales = j
            mas_goles_penales["_id"] = str(mas_goles_penales["_id"])
            # El marcador de penales vive solo dentro de 'resultado', que se borra abajo
            # (igual que en los otros "destacados") — se preserva aparte para el template.
            mas_goles_penales["penaltis_local"] = pl
            mas_goles_penales["penaltis_visitante"] = pv
            if "resultado" in mas_goles_penales: del mas_goles_penales["resultado"]
            if "estadisticas" in mas_goles_penales: del mas_goles_penales["estadisticas"]
            if "ubicacion" in mas_goles_penales: del mas_goles_penales["ubicacion"]

        # Detección de Remontadas mediante simulación de eventos
        eventos = res.get("eventos", [])
        marcador_l, marcador_v = 0, 0
        hubo_remontada = False
        ganador_final = j.get("equipo_local")["nombre"] if gl > gv else j.get("equipo_visitante")["nombre"]

        if gl != gv: # Solo si hubo ganador
            for ev in eventos:
                tipo_evento = ev.get("tipo", "").upper()
                # "ANULADO" excluye los goles anulados por VAR (su tipo también contiene
                # la palabra "GOL": "🖥️ VAR - GOL ANULADO") — si no se excluye, un gol que
                # nunca se contó en el marcador real infla el marcador reconstruido acá y
                # puede generar remontadas falsas.
                if "GOL" in tipo_evento and "ANULADO" not in tipo_evento:
                    if ev.get("equipo") == j["equipo_local"]["nombre"]:
                        marcador_l += 1
                    elif ev.get("equipo") == j["equipo_visitante"]["nombre"]:
                        marcador_v += 1
                    
                    # Si en algún punto el equipo que terminó perdiendo iba ganando por 1
                    if (ganador_final == j["equipo_local"]["nombre"] and marcador_v > marcador_l) or \
                        (ganador_final == j["equipo_visitante"]["nombre"] and marcador_l > marcador_v):
                        hubo_remontada = True

            if hubo_remontada:
                info_remontada = _formatear_partido_resumen(j, gl, gv)
                partidos_remontada.append(info_remontada)
                remontadas_por_pais[ganador_final].append(info_remontada)

        # Medición de juego sucio / limpio
        tarjetas_faltas = sum(1 for e in eventos if any(k in e.get("tipo", "").upper() for k in ["TARJETA", "FALTA", "ROJA", "AMARILLA"]))
        if tarjetas_faltas > max_tarjetas:
            max_tarjetas = tarjetas_faltas
            juego_mas_sucio = j
            
            if "_id" in juego_mas_sucio:
                juego_mas_sucio["_id"] = str(juego_mas_sucio["_id"])
            
            if "estadisticas" in juego_mas_sucio:
                del juego_mas_sucio["estadisticas"]
            
            if "resultado" in juego_mas_sucio:
                del juego_mas_sucio["resultado"]
            
            if "ubicacion" in juego_mas_sucio:
                del juego_mas_sucio["ubicacion"]
            
        if tarjetas_faltas < min_tarjetas:
            min_tarjetas = tarjetas_faltas
            juego_mas_limpio = j
            
            if "_id" in juego_mas_limpio:
                juego_mas_limpio["_id"] = str(juego_mas_limpio["_id"])
            
            if "estadisticas" in juego_mas_limpio:
                del juego_mas_limpio["estadisticas"]
            
            if "resultado" in juego_mas_limpio:
                del juego_mas_limpio["resultado"]
            
            if "ubicacion" in juego_mas_limpio:
                del juego_mas_limpio["ubicacion"]
            
    nombre_top_remontador, partidos_top_remontador = max(
        remontadas_por_pais.items(), key=lambda kv: len(kv[1]), default=("Ninguno", [])
    )

    estadio_mas_frecuente = None
    if partidos_por_estadio:
        grupo_top_estadio = max(partidos_por_estadio.values(), key=lambda g: len(g["partidos"]))
        estadio_mas_frecuente = {
            "estadio": grupo_top_estadio["estadio"],
            "ciudad": grupo_top_estadio["ciudad"],
            "pais": grupo_top_estadio["pais"],
            "total_juegos": len(grupo_top_estadio["partidos"]),
            "partidos": sorted(grupo_top_estadio["partidos"], key=lambda p: p.get("fecha") or "")
        }

    return {
        "estadio_mas_frecuente": estadio_mas_frecuente,
        "mas_goles_tiempo_normal": mas_goles_regular,
        "mas_goles_tiempo_extra": mas_goles_extra,
        "mas_goles_penales": mas_goles_penales,
        "juego_mas_sucio": juego_mas_sucio,
        "juego_mas_limpio": juego_mas_limpio,
        "partido_mayor_aforo": partido_mayor_aforo,
        "partidos_con_remontada": partidos_remontada,
        "total_remontadas": len(partidos_remontada),
        "pais_mas_remontador": {
            "pais": nombre_top_remontador,
            "remontadas": len(partidos_top_remontador),
            "partidos": partidos_top_remontador
        }
    }

# ==========================================
# 4b. RÉCORDS POR PARTIDO Y TENDENCIAS DEL TORNEO (árbitros, primer gol, sede más goleadora,
#     promedios, franjas de gol, hat-tricks) -- todo derivado de 'resultado.eventos'
# ==========================================
TIPOS_GOL_EN_JUEGO = {"⚽ GOL", "⚽ GOL DE TIRO LIBRE", "⚽ GOL DE CÓRNER"}  # "⚽ GOL DE PENAL" solo existe en tandas
TIPOS_TARJETA = {"🟨 TARJETA AMARILLA", "🖥️ VAR - TARJETA REVISADA", "🟥 TARJETA ROJA", "🟨🟥 DOBLE AMARILLA"}  # la revisada = roja rebajada a amarilla
TIPOS_EXPULSION = {"🟥 TARJETA ROJA", "🟨🟥 DOBLE AMARILLA"}
FRANJAS_GOL = [(0, 15, "0-15'"), (16, 30, "16-30'"), (31, 45, "31-45'"), (46, 60, "46-60'"),
               (61, 75, "61-75'"), (76, 90, "76-90'"), (91, 999, "Alargue")]


def _juegos_finalizados_para_records() -> list:
    """Partidos finalizados con solo los campos que usan los récords y las tendencias (evita
    traer 'estadisticas', posiciones del balón, descripciones, etc.). Solo del Mundial ACTIVO:
    'juegos' conserva los partidos de mundiales anteriores (clean_and_update no los borra) y sin
    este filtro los récords y tendencias mezclaban torneos."""
    filtro = {"estado": "finalizado", "resultado": {"$exists": True}}
    mundial = db["mundiales"].find_one({"activo": True}, {"_id": 1})
    if mundial:
        filtro["mundial_id"] = str(mundial["_id"])
    return list(db["juegos"].find(
        filtro,
        {
            "equipo_local": 1, "equipo_visitante": 1, "tag": 1, "fecha": 1, "ubicacion": 1,
            "resultado.goles_local": 1, "resultado.goles_visitante": 1, "resultado.arbitros": 1,
            "resultado.goleadores": 1, "resultado.eventos.tipo": 1, "resultado.eventos.minuto": 1,
            "resultado.eventos.segundos_acumulados": 1, "resultado.eventos.equipo": 1,
            "resultado.eventos.jugadores": 1,
        }
    ))


def _goles_partido(juego: dict):
    res = juego.get("resultado") or {}
    return res.get("goles_local", 0) or 0, res.get("goles_visitante", 0) or 0


def _resumen_partido(juego: dict) -> dict:
    return _formatear_partido_resumen(juego, *_goles_partido(juego))


def _contar_faltas_tarjetas(eventos: list):
    """(faltas, tarjetas, expulsiones) de un partido, contando eventos del motor."""
    faltas = tarjetas = expulsiones = 0
    for e in eventos:
        tipo = e.get("tipo", "")
        if tipo == "🛑 FALTA":
            faltas += 1
        elif tipo in TIPOS_TARJETA:
            tarjetas += 1
            if tipo in TIPOS_EXPULSION:
                expulsiones += 1
    return faltas, tarjetas, expulsiones


def _get_stats_arbitros_avanzado(juegos: list) -> dict:
    """
    Récords EN UN PARTIDO del árbitro central: más/menos faltas y más/menos tarjetas, con el
    partido en cuestión. No se usa un promedio por árbitro a propósito: cada central dirige 1 a
    4 partidos en todo el torneo, y un promedio con tan pocos partidos es ruido. Además, el
    acumulado de expulsiones por árbitro en el torneo.
    """
    filas = []
    expulsiones_por_arbitro = defaultdict(lambda: {"expulsiones": 0, "partidos": 0})
    for j in juegos:
        arbitro = ((j.get("resultado") or {}).get("arbitros") or {}).get("central")
        if not arbitro:
            continue
        faltas, tarjetas, expulsiones = _contar_faltas_tarjetas((j.get("resultado") or {}).get("eventos", []))
        filas.append((arbitro, faltas, tarjetas, j))
        expulsiones_por_arbitro[arbitro]["expulsiones"] += expulsiones
        expulsiones_por_arbitro[arbitro]["partidos"] += 1

    if not filas:
        return {}

    def _armar(fila):
        arbitro, faltas, tarjetas, juego = fila
        return {"nombre": arbitro, "faltas": faltas, "tarjetas": tarjetas, "partido": _resumen_partido(juego)}

    nombre_exp, datos_exp = max(expulsiones_por_arbitro.items(), key=lambda kv: (kv[1]["expulsiones"], -kv[1]["partidos"]))
    return {
        "mas_faltas": _armar(max(filas, key=lambda f: (f[1], f[2]))),
        "mas_tarjetas": _armar(max(filas, key=lambda f: (f[2], f[1]))),
        "menos_faltas": _armar(min(filas, key=lambda f: (f[1], f[2]))),
        "menos_tarjetas": _armar(min(filas, key=lambda f: (f[2], f[1]))),
        "mas_expulsiones": {"nombre": nombre_exp, "expulsiones": datos_exp["expulsiones"], "partidos_dirigidos": datos_exp["partidos"]}
        if datos_exp["expulsiones"] > 0 else None,
    }


def _primer_gol(juego: dict) -> Optional[dict]:
    """Primer gol en juego del partido (sin tanda), ordenado por segundos (o minuto si falta)."""
    goles = [e for e in (juego.get("resultado") or {}).get("eventos", []) if e.get("tipo") in TIPOS_GOL_EN_JUEGO]
    if not goles:
        return None
    return min(goles, key=lambda e: (e.get("segundos_acumulados", (e.get("minuto") or 0) * 60), e.get("minuto") or 0))


def _obtener_records_primer_gol(juegos: list) -> dict:
    """
    'gol_mas_rapido': el primer gol de un partido que cayó más temprano en todo el torneo.
    'gol_mas_tardio': el primer gol que más tarde llegó (el partido que más tardó en abrirse;
    puede caer en el alargue). Los partidos sin goles en juego no participan.
    """
    primeros = []
    for j in juegos:
        gol = _primer_gol(j)
        if gol:
            primeros.append((gol.get("segundos_acumulados", (gol.get("minuto") or 0) * 60), gol, j))
    if not primeros:
        return {"gol_mas_rapido": None, "gol_mas_tardio": None}

    def _armar(item):
        segundos, gol, juego = item
        jugadores = gol.get("jugadores") or []
        return {"jugador": jugadores[0] if jugadores else "?", "equipo": gol.get("equipo"),
                "minuto": gol.get("minuto"), "segundos": int(segundos), "partido": _resumen_partido(juego)}

    return {
        "gol_mas_rapido": _armar(min(primeros, key=lambda p: p[0])),
        "gol_mas_tardio": _armar(max(primeros, key=lambda p: p[0])),
    }


def _obtener_sede_mas_goleadora(juegos: list) -> Optional[dict]:
    """Estadio (agrupado por ciudad, 'ubicacion.id', igual que estadio_mas_frecuente) con más
    goles en total en los partidos que albergó; desempata el promedio por partido. Los goles de
    la tanda de penales no cuentan (resultado.goles_* no los incluye)."""
    sedes = defaultdict(lambda: {"estadio": None, "ciudad": None, "pais": None, "goles": 0, "partidos": []})
    for j in juegos:
        ubicacion = j.get("ubicacion") or {}
        if not ubicacion.get("estadio"):
            continue
        clave = ubicacion.get("id")
        if clave is None:
            clave = (ubicacion.get("estadio"), ubicacion.get("pais"))
        sede = sedes[clave]
        sede.update({"estadio": ubicacion.get("estadio"), "ciudad": ubicacion.get("nombre"), "pais": ubicacion.get("pais")})
        sede["goles"] += sum(_goles_partido(j))
        sede["partidos"].append(_resumen_partido(j))
    if not sedes:
        return None
    top = max(sedes.values(), key=lambda s: (s["goles"], s["goles"] / len(s["partidos"])))
    return {
        "estadio": top["estadio"], "ciudad": top["ciudad"], "pais": top["pais"],
        "total_goles": top["goles"], "total_juegos": len(top["partidos"]),
        "promedio_goles": round(top["goles"] / len(top["partidos"]), 1),
        "partidos": sorted(top["partidos"], key=lambda p: p.get("fecha") or ""),
    }


def _get_stats_tendencias(juegos: list) -> dict:
    """Tendencias generales del torneo: promedio de goles, ambos marcan, ventaja de local,
    mayor goleada, goles por franja de minutos y hat-tricks."""
    total = len(juegos)
    if not total:
        return {"total_partidos": 0}

    total_goles = ambos_marcan = gana_local = empates = gana_visitante = 0
    mayor_goleada = None
    franjas = [0] * len(FRANJAS_GOL)
    hat_tricks = defaultdict(lambda: {"nombre": None, "equipo": None, "partidos": []})
    partidos_hat_trick = []

    for j in juegos:
        gl, gv = _goles_partido(j)
        total_goles += gl + gv
        ambos_marcan += 1 if gl > 0 and gv > 0 else 0
        if gl > gv:
            gana_local += 1
        elif gv > gl:
            gana_visitante += 1
        else:
            empates += 1
        clave_goleada = (abs(gl - gv), gl + gv)
        if mayor_goleada is None or clave_goleada > mayor_goleada[0]:
            mayor_goleada = (clave_goleada, j)

        for e in (j.get("resultado") or {}).get("eventos", []):
            if e.get("tipo") in TIPOS_GOL_EN_JUEGO:
                minuto = e.get("minuto") or 0
                for i, (desde, hasta, _) in enumerate(FRANJAS_GOL):
                    if desde <= minuto <= hasta:
                        franjas[i] += 1
                        break

        for g in (j.get("resultado") or {}).get("goleadores", []) or []:
            if (g.get("goles") or 0) >= 3:
                h = hat_tricks[g.get("jugador_id") or g.get("jugador_nombre")]
                h["nombre"], h["equipo"] = g.get("jugador_nombre"), g.get("equipo")
                # 'nota' la muestra el modal de "ver partidos" (templates/estadisticas.html)
                partido = {**_resumen_partido(j), "nota": f"🎩 {g.get('jugador_nombre')} ({g.get('equipo')}): {g.get('goles')} goles"}
                h["partidos"].append(partido)
                partidos_hat_trick.append(partido)

    goles_en_franjas = sum(franjas) or 1
    # "Rey del hat-trick" solo si alguien tiene 2+ (con todos empatados en 1 sería arbitrario)
    rey_hat_trick = max(hat_tricks.values(), key=lambda h: len(h["partidos"]), default=None)
    if rey_hat_trick and len(rey_hat_trick["partidos"]) < 2:
        rey_hat_trick = None
    pct = lambda n: round(100 * n / total, 1)
    return {
        "total_partidos": total,
        "total_goles": total_goles,
        "promedio_goles": round(total_goles / total, 2),
        "pct_ambos_marcan": pct(ambos_marcan),
        "resultados": {"pct_local": pct(gana_local), "pct_empate": pct(empates), "pct_visitante": pct(gana_visitante)},
        "mayor_goleada": {"diferencia": mayor_goleada[0][0], "partido": _resumen_partido(mayor_goleada[1])} if mayor_goleada else None,
        "goles_por_franja": [
            {"franja": etiqueta, "goles": franjas[i], "pct": round(100 * franjas[i] / goles_en_franjas, 1)}
            for i, (_, _, etiqueta) in enumerate(FRANJAS_GOL)
        ],
        "hat_tricks": {
            "total": len(partidos_hat_trick),
            "partidos": sorted(partidos_hat_trick, key=lambda p: p.get("fecha") or ""),
            "rey": {"nombre": rey_hat_trick["nombre"], "equipo": rey_hat_trick["equipo"],
                    "cantidad": len(rey_hat_trick["partidos"]), "partidos": rey_hat_trick["partidos"]} if rey_hat_trick else None,
        },
    }


# ==========================================
# 5. ESTADÍSTICAS DE PAÍSES (Vía 'juegos', agregando todo el torneo)
# ==========================================
def _calcular_estadisticas_reales_paises() -> Dict[int, dict]:
    """
    Recalcula las estadísticas acumuladas REALES de cada país agregando directamente sobre
    'juegos' (única fuente que acumula de verdad a lo largo de TODO el torneo):
      - 'paises.estadisticas.goles_favor/p_ofensiva/p_defensiva/...' nunca se actualiza tras
        un partido (solo 'estadisticas.poder', ver paises_service.actualizar_poder_y_rankin),
        así que consultar 'paises' para esto devolvía siempre el valor congelado del último
        'restart_mundial()' (o el del seed inicial).
      - 'internacional' sí se actualiza partido a partido (ver
        paises_service.actualizar_estadisticas_pais), pero se resetea a 0 cada vez que un país
        entra a una fase nueva (ver international_service.poblar_paises_internacional), así
        que tampoco sirve para "mejor país de todo el torneo".
    """
    juegos_coll = db["juegos"]
    juegos = juegos_coll.find(
        {"estado": "finalizado"},
        {
            "equipo_local.id": 1, "equipo_local.nombre": 1, "equipo_local.bandera": 1,
            "equipo_visitante.id": 1, "equipo_visitante.nombre": 1, "equipo_visitante.bandera": 1,
            "resultado.goles_local": 1, "resultado.goles_visitante": 1,
            "estadisticas.local": 1, "estadisticas.visitante": 1
        }
    )

    acumulado = defaultdict(lambda: {
        "nombre": None, "bandera": None,
        "goles_favor": 0, "goles_contra": 0, "puntos": 0,
        "suma_p_ofensiva": 0.0, "suma_p_defensiva": 0.0, "suma_p_posesion": 0.0,
        "suma_efectividad_gol": 0.0, "suma_promedio_gol": 0.0,
        "partidos": 0,
        # Para la efectividad de gol REAL (goles/tiros acumulados de todo el torneo, no el
        # promedio de "suma_efectividad_gol" de arriba) -- ver nota en _sumar_lado.
        "goles_con_datos_tiro": 0, "tiros_totales": 0
    })

    def _sumar_lado(pais_id, nombre, bandera, goles_favor, goles_contra, metricas):
        reg = acumulado[pais_id]
        reg["nombre"] = nombre
        reg["bandera"] = bandera
        reg["goles_favor"] += goles_favor
        reg["goles_contra"] += goles_contra
        reg["puntos"] += 3 if goles_favor > goles_contra else (1 if goles_favor == goles_contra else 0)
        reg["suma_p_ofensiva"] += metricas.get("p_ofensiva", 0)
        reg["suma_p_defensiva"] += metricas.get("p_defensiva", 0)
        reg["suma_p_posesion"] += metricas.get("p_posesion", 0)
        reg["suma_efectividad_gol"] += metricas.get("efectividad_gol", 0)
        reg["suma_promedio_gol"] += metricas.get("promedio_gol", 0)
        reg["partidos"] += 1
        # 'tiros_totales' es un campo nuevo en 'estadisticas.local/visitante' (ver
        # simular_service.calcular_metricas_equipo) -- los partidos simulados ANTES de este
        # cambio no lo tienen. Se suman goles y tiros SOLO de los partidos que sí lo traen, para
        # no mezclar goles de partidos viejos (sin dato de tiros) con tiros de partidos nuevos,
        # lo que inflaría artificialmente el % de efectividad real.
        if metricas.get("tiros_totales") is not None:
            reg["goles_con_datos_tiro"] += goles_favor
            reg["tiros_totales"] += metricas["tiros_totales"]

    for juego in juegos:
        resultado = juego.get("resultado")
        equipo_local = juego.get("equipo_local") or {}
        equipo_visitante = juego.get("equipo_visitante") or {}
        metricas = juego.get("estadisticas") or {}
        if not resultado or not equipo_local.get("id") or not equipo_visitante.get("id"):
            continue

        gl = resultado.get("goles_local", 0) or 0
        gv = resultado.get("goles_visitante", 0) or 0

        _sumar_lado(equipo_local["id"], equipo_local.get("nombre"), equipo_local.get("bandera"), gl, gv, metricas.get("local", {}))
        _sumar_lado(equipo_visitante["id"], equipo_visitante.get("nombre"), equipo_visitante.get("bandera"), gv, gl, metricas.get("visitante", {}))

    estadisticas_por_pais = {}
    for pais_id, reg in acumulado.items():
        partidos = reg["partidos"] or 1
        estadisticas_por_pais[pais_id] = {
            "nombre": reg["nombre"],
            "bandera": reg["bandera"],
            "estadisticas": {
                "goles_favor": reg["goles_favor"],
                "goles_contra": reg["goles_contra"],
                "diferencia_goles": reg["goles_favor"] - reg["goles_contra"],
                "puntos": reg["puntos"],
                "p_ofensiva": round(reg["suma_p_ofensiva"] / partidos, 1),
                "p_defensiva": round(reg["suma_p_defensiva"] / partidos, 1),
                "p_posesion": round(reg["suma_p_posesion"] / partidos, 1),
                "efectividad_gol": round(reg["suma_efectividad_gol"] / partidos, 1),
                "promedio_gol": round(reg["suma_promedio_gol"] / partidos, 2),
                "tiros_totales": reg["tiros_totales"],
                "efectividad_gol_real": (
                    round(reg["goles_con_datos_tiro"] / reg["tiros_totales"] * 100, 1)
                    if reg["tiros_totales"] > 0 else None
                )
            }
        }
    return estadisticas_por_pais


# Mínimo de disparos acumulados en el torneo para que un país califique al ranking de
# efectividad de gol real -- mismo criterio que MINIMO_TIROS_EFECTIVIDAD_GOL para jugadores,
# pero más alto porque un país acumula los tiros de TODOS sus jugadores en TODOS sus partidos.
MINIMO_TIROS_EFECTIVIDAD_GOL_PAIS = 10


def _obtener_fair_play(estadisticas_por_pais: Dict[int, dict]) -> Optional[dict]:
    """
    País con menos tarjetas + faltas acumuladas en el torneo (menor total = juego más limpio).

    'juegos.estadisticas.local/visitante' (ver simular_service.calcular_metricas_equipo) NO
    persiste faltas/tarjetas a nivel de equipo, solo por jugador -- así que en vez de parsear
    'juegos.eventos[]' de todo el torneo, se suma directo sobre 'jugadores' (contador por-torneo,
    se resetea en cada restart_mundial, no arrastra mundiales viejos) agrupando por 'pais_id'.

    Solo participan países que ya jugaron al menos un partido (mismo universo de
    'estadisticas_por_pais' que usa el resto de _get_stats_paises).
    """
    jugadores_coll = db["jugadores"]
    disciplina_por_pais = {
        reg["_id"]: {
            "faltas": reg.get("faltas", 0) or 0,
            "amarillas": reg.get("amarillas", 0) or 0,
            "rojas": reg.get("rojas", 0) or 0
        }
        for reg in jugadores_coll.aggregate([
            {"$group": {
                "_id": "$pais_id",
                "faltas": {"$sum": "$faltas"},
                "amarillas": {"$sum": "$amarilla"},
                "rojas": {"$sum": "$roja"}
            }}
        ])
    }

    candidatos = []
    for pais_id, datos in estadisticas_por_pais.items():
        disciplina = disciplina_por_pais.get(pais_id, {"faltas": 0, "amarillas": 0, "rojas": 0})
        candidatos.append({
            "nombre": datos["nombre"],
            "bandera": datos["bandera"],
            "faltas": disciplina["faltas"],
            "amarillas": disciplina["amarillas"],
            "rojas": disciplina["rojas"],
            "total_infracciones": disciplina["faltas"] + disciplina["amarillas"] + disciplina["rojas"]
        })

    if not candidatos:
        return None
    return min(candidatos, key=lambda p: p["total_infracciones"])


def _get_stats_paises():
    estadisticas_por_pais = _calcular_estadisticas_reales_paises()

    if not estadisticas_por_pais:
        return {"pais_mas_goleador": None, "mejor_ofensiva": None, "mejor_defensiva": None, "mejor_efectividad_gol": None}

    paises_lista = list(estadisticas_por_pais.values())
    pais_goleador = max(paises_lista, key=lambda p: p["estadisticas"]["goles_favor"])
    mejor_ofensiva = max(paises_lista, key=lambda p: p["estadisticas"]["p_ofensiva"])
    mejor_defensiva = max(paises_lista, key=lambda p: p["estadisticas"]["p_defensiva"])

    # Efectividad de gol REAL (goles/tiros acumulados de todo el torneo, ver _sumar_lado más
    # arriba) -- solo participan países con al menos MINIMO_TIROS_EFECTIVIDAD_GOL_PAIS tiros
    # registrados, para que un país con pocos partidos con dato de tiros no encabece el ranking
    # sin ser representativo (mismo criterio que _obtener_mejor_efectividad_gol para jugadores).
    paises_calificados = [
        p for p in paises_lista
        if p["estadisticas"].get("efectividad_gol_real") is not None
        and p["estadisticas"]["tiros_totales"] >= MINIMO_TIROS_EFECTIVIDAD_GOL_PAIS
    ]
    mejor_efectividad_gol = (
        max(paises_calificados, key=lambda p: p["estadisticas"]["efectividad_gol_real"])
        if paises_calificados else None
    )
    
    # pais con menos tarjetas y faltas acumuladas en el torneo (juego limpio) -- solo participan países con al menos 1 partido jugado
    fair_play = _obtener_fair_play(estadisticas_por_pais)

    return {
        "pais_mas_goleador": pais_goleador,
        "mejor_ofensiva": mejor_ofensiva,
        "mejor_defensiva": mejor_defensiva,
        "mejor_efectividad_gol": mejor_efectividad_gol,
        "fair_play": fair_play
    }

# ==========================================
# 6. TORNEOS Y 11 IDEAL
# ==========================================
def _get_stats_torneos():
    mundiales_coll = db["mundiales"]
    
    total_mundiales = mundiales_coll.count_documents({})
    return {"total_mundiales": total_mundiales}

def _get_11_ideal():
    """Selecciona al mejor jugador de cada posición técnica en función del 'overall' y 'rendimiento'."""
    posiciones_coll = db["posiciones"]
    jugadores_coll = db["jugadores"]
    paises_coll = db["paises"]

    posiciones = list(posiciones_coll.find()) # Colección catálogo
    ids_posiciones = [pos["id"] for pos in posiciones]

    # Un solo aggregate para traer al mejor jugador de cada posición
    # (antes era un find_one por posición del catálogo)
    pipeline_mejores = [
        {"$match": {"posicion_id": {"$in": ids_posiciones}}},
        {"$sort": {"overall": -1, "rendimiento": -1}},
        {"$group": {"_id": "$posicion_id", "mejor_jugador": {"$first": "$$ROOT"}}}
    ]
    mejores_por_posicion = {doc["_id"]: doc["mejor_jugador"] for doc in jugadores_coll.aggregate(pipeline_mejores)}

    # 'jugadores' no tiene un campo 'pais' (string) — se resuelve el nombre real vía
    # 'pais_id' en un solo lookup en batch (mismo fix que en _get_stats_jugadores).
    ids_paises = {j.get("pais_id") for j in mejores_por_posicion.values() if j.get("pais_id") is not None}
    nombres_paises = {p["id"]: p.get("nombre", "?") for p in paises_coll.find({"id": {"$in": list(ids_paises)}}, {"id": 1, "nombre": 1})}

    once_ideal = []
    for pos in posiciones:
        mejor_jugador = mejores_por_posicion.get(pos["id"])
        if mejor_jugador:
            once_ideal.append({
                "posicion": pos["nombre"],
                "siglas": pos["siglas"],
                "jugador": mejor_jugador["nombre"],
                "pais": nombres_paises.get(mejor_jugador.get("pais_id"), "?"),
                "overall": mejor_jugador["overall"]
            })
    return once_ideal
