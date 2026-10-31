from bson.objectid import ObjectId
from collections import defaultdict
from pymongo.database import Database
from typing import Dict, Optional
import certifi
import time
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

_cache_mundial = {"id": None, "hasta": 0.0}


def _mundial_activo_id() -> Optional[str]:
    """Id del Mundial activo, cacheado 30 s (cada carga de la vista arma ~12 consultas con este filtro)."""
    ahora = time.monotonic()
    if ahora >= _cache_mundial["hasta"]:
        mundial = db["mundiales"].find_one({"activo": True}, {"_id": 1})
        _cache_mundial.update(id=str(mundial["_id"]) if mundial else None, hasta=ahora + 30)
    return _cache_mundial["id"]


def _filtro_finalizados() -> dict:
    """
    Filtro base de TODAS las consultas de partidos de esta vista: jugados, del Mundial activo
    ('juegos' conserva los de mundiales anteriores) y sin el que todavía se está transmitiendo en
    vivo (ya está simulado, pero su resultado no debe adelantarse aquí).
    """
    filtro = {"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}}
    mundial_id = _mundial_activo_id()
    if mundial_id:
        filtro["mundial_id"] = mundial_id
    return filtro


def _completar_ids_jugadores(stats: dict) -> None:
    """
    Agrega 'jugador_id' y 'pais_id' a cada récord de jugador de la vista de estadísticas (para el
    avatar, la bandera de fondo y el link a /jugadores/{id}). Varios récords solo traen el nombre
    del jugador y del país, así que se resuelven todos juntos en UNA consulta: por nombre, y si hay
    homónimos, por el país del récord.
    """
    jugadores, porteros, partidos = stats["jugadores"], stats["porteros"], stats["partidos"]
    # (registro, clave del nombre del jugador, clave del nombre del país)
    registros = [(jugadores.get(k), "nombre", "pais") for k in (
        "mas_goles", "mas_partidos", "mas_asistencias", "especialista_balon_parado", "super_sub", "mas_recuperaciones",
        "especialista_aereo", "mas_amarillas", "mas_rojas", "mas_faltas", "mas_infringido")]
    registros += [(jugadores.get("mayor_racha_goles"), "jugador", None),
                  (porteros.get("portero_mas_atajadas"), "portero", "equipo"),
                  (porteros.get("portero_mas_vallas_invictas"), "portero", "pais"),
                  (porteros.get("atajapenales"), "portero", "equipo"),
                  (partidos.get("gol_mas_rapido"), "jugador", "equipo"),
                  (partidos.get("gol_mas_tardio"), "jugador", "equipo")]
    registros += [(j, "jugador", "pais") for j in stats.get("once_ideal") or []]
    registros = [(r, kn, kp) for r, kn, kp in registros if isinstance(r, dict) and r.get(kn)]
    if not registros:
        return

    nombres = {r[kn] for r, kn, _ in registros}
    candidatos = defaultdict(list)
    for j in db["jugadores"].find({"nombre": {"$in": list(nombres)}}, {"_id": 0, "id": 1, "nombre": 1, "pais_id": 1}):
        candidatos[j["nombre"]].append(j)
    pais_por_nombre = {p["nombre"]: p["id"] for p in db["paises"].find({}, {"_id": 0, "id": 1, "nombre": 1})}

    for r, kn, kp in registros:
        opciones = candidatos.get(r[kn], [])
        if r.get("jugador_id") is not None:
            elegido = next((j for j in opciones if j["id"] == r["jugador_id"]), None)
        else:
            pais_id = r.get("pais_id") or pais_por_nombre.get(r.get(kp)) if kp else r.get("pais_id")
            elegido = next((j for j in opciones if j["pais_id"] == pais_id), None) or (opciones[0] if len(opciones) == 1 else None)
        if elegido:
            r.setdefault("jugador_id", elegido["id"])
            r.setdefault("pais_id", elegido["pais_id"])

# ==========================================
# 1. ESTADÍSTICAS DE JUGADORES Y RACHAS
# ==========================================
# Mínimo de disparos totales para calificar al ranking de efectividad de gol -- evita que un
# jugador con, por ejemplo, 1 disparo y 1 gol (100%) encabece el ranking sin ser representativo.
MINIMO_TIROS_EFECTIVIDAD_GOL = 5

# ==========================================
# 2. ESTADÍSTICAS DE PORTEROS (Vía 'eventos' y 'jugadores')
# ==========================================
# ==========================================
# 3. ÁRBITROS CON MÁS JUEGOS PITADOS
# ==========================================
def _get_stats_arbitros():
    def _top_arbitro(rol_field):
        juegos_coll = db["juegos"]
        pipeline = [
            {"$match": {**_filtro_finalizados(), f"resultado.arbitros.{rol_field}": {"$ne": None}}},
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
    juego['resultado'] de nuevo aquí) porque en '_get_stats_partidos' la clave 'resultado'
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


def _get_stats_partidos(juegos: Optional[list] = None):
    juegos_coll = db["juegos"]

    # Partidos con más goles (Tiempo Regular vs Tiempo Extra vs Penales). Con la lista compartida
    # de obtener_estadisticas_generales se trabaja sobre COPIAS: más abajo se borran campos
    # ('resultado', 'ubicacion'...) de los partidos récord, y eso no debe tocar la lista común.
    juegos_finalizados = [dict(j) for j in juegos] if juegos is not None else list(juegos_coll.find({**_filtro_finalizados()}))

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
            grupo_estadio["ciudad_id"] = ubicacion.get("id")
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
                # nunca se contó en el marcador real infla el marcador reconstruido aquí y
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
            "ciudad_id": grupo_top_estadio.get("ciudad_id"),
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
            "bandera": next((e.get("bandera") for pt_ in partidos_top_remontador for e in (pt_.get("equipo_local") or {}, pt_.get("equipo_visitante") or {})
                             if e.get("nombre") == nombre_top_remontador), None),
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
    filtro = {**_filtro_finalizados(), "resultado": {"$exists": True}}
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
        sede.update({"estadio": ubicacion.get("estadio"), "ciudad": ubicacion.get("nombre"), "pais": ubicacion.get("pais"), "ciudad_id": ubicacion.get("id")})
        sede["goles"] += sum(_goles_partido(j))
        sede["partidos"].append(_resumen_partido(j))
    if not sedes:
        return None
    top = max(sedes.values(), key=lambda s: (s["goles"], s["goles"] / len(s["partidos"])))
    return {
        "estadio": top["estadio"], "ciudad": top["ciudad"], "pais": top["pais"], "ciudad_id": top.get("ciudad_id"),
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
def _calcular_estadisticas_reales_paises(juegos_lista: Optional[list] = None) -> Dict[int, dict]:
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
    juegos = juegos_lista if juegos_lista is not None else juegos_coll.find(
        {**_filtro_finalizados()},
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


def _get_stats_paises(juegos: Optional[list] = None):
    estadisticas_por_pais = _calcular_estadisticas_reales_paises(juegos)

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
    
    # Fair play: lo calcula obtener_estadisticas_generales desde el agregado del Mundial (tarjetas y faltas por partido)
    fair_play = None

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

def _get_11_ideal(leyendas: bool = False):
    """
    Selecciona al mejor jugador de cada posición técnica en función del 'overall' y 'rendimiento'.
    Las leyendas (jugadores.leyenda, ~80) van en un once aparte (leyendas=True): si compitieran con
    el resto se quedarían con los 11 puestos.
    """
    posiciones_coll = db["posiciones"]
    jugadores_coll = db["jugadores"]
    paises_coll = db["paises"]

    posiciones = list(posiciones_coll.find()) # Colección catálogo
    ids_posiciones = [pos["id"] for pos in posiciones]

    # Un solo aggregate para traer al mejor jugador de cada posición
    # (antes era un find_one por posición del catálogo)
    pipeline_mejores = [
        {"$match": {"posicion_id": {"$in": ids_posiciones}, "leyenda": True if leyendas else {"$ne": True}}},
        # leyendas: todas arrancan en ~80, así que manda el rendimiento en el Mundial y, a igualdad, la fama
        {"$sort": {"rendimiento": -1, "wikis": -1, "fama": -1} if leyendas else {"overall": -1, "rendimiento": -1}},
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
                "jugador_id": mejor_jugador.get("id"),
                "pais_id": mejor_jugador.get("pais_id"),
                "pais": nombres_paises.get(mejor_jugador.get("pais_id"), "?"),
                "overall": mejor_jugador["overall"]
            })
    return once_ideal


# ==========================================
# 7. AGREGADO DEL MUNDIAL EN CURSO, TOP 10 Y DETALLE
# ==========================================
# Todo lo de esta sección sale de los partidos del Mundial activo (no de los contadores de
# 'jugadores', que NO se reinician entre mundiales: solo restart_mundial los pone en 0). Los
# eventos traen NOMBRES de jugadores; el rol de cada nombre según el tipo de evento sale del motor
# (simular_service.construir_evento):
#   ⚽ GOL*            -> [goleador, arquero rival, asistente?]   (equipo = el que anota)
#   🛑 FALTA / 🟨       -> [infractor, infractado?]               (equipo = el del infractor)
#   🟥 / 🟨🟥           -> [expulsado]
#   🧠 ROBO DE BALÓN   -> [quien recupera];  ⚡ REGATE DESTACADO -> [quien regatea]
#   🎯 / 🧱             -> [quien dispara];   🧤 ATAJADA -> [arquero, tirador?] (equipo = el del arquero)
#   ❌ PENAL FALLADO   -> [arquero, pateador] (equipo = el del arquero)

PROYECCION_JUEGOS_MUNDIAL = {
    "equipo_local": 1, "equipo_visitante": 1, "tag": 1, "fecha": 1, "hora": 1, "ubicacion": 1, "aforo": 1,
    "tiempo_extra": 1, "jornada": 1, "grupo": 1, "fase_id": 1, "estadisticas.local": 1, "estadisticas.visitante": 1,
    **{f"resultado.{k}": 1 for k in ("goles_local", "goles_visitante", "penaltis_local", "penaltis_visitante", "ganador_id",
                                     "empate", "arbitros", "goleadores", "atajadores", "participantes")},
    "resultado.eventos.tipo": 1, "resultado.eventos.minuto": 1, "resultado.eventos.segundos_acumulados": 1,
    "resultado.eventos.equipo": 1, "resultado.eventos.jugadores": 1,
}

METRICAS_JUGADOR = ("partidos", "goles", "goles_penal", "goles_tiro_libre", "goles_corner", "goles_suplente", "asistencias",
                    "atajadas", "penales_atajados", "disparos", "faltas", "faltas_recibidas", "amarillas", "rojas",
                    "recuperaciones", "regates")

# (código, título, ícono, sufijo, mínimo para entrar a la lista)
TOP_JUGADORES = [
    ("goles", "Goleadores", "bi-dribbble", "goles", 1),
    ("asistencias", "Asistidores", "bi-share-fill", "asist.", 1),
    ("contribucion", "Goles + asistencias", "bi-plus-circle-fill", "G+A", 1),
    ("atajadas", "Arqueros (atajadas)", "bi-hand-index-thumb-fill", "atajadas", 1),
    ("recuperaciones", "Recuperadores", "bi-shield-fill-check", "recup.", 1),
    ("regates", "Regateadores", "bi-lightning-charge-fill", "regates", 1),
    ("disparos", "Más disparos", "bi-bullseye", "disparos", 1),
    ("partidos", "Más presencias", "bi-person-check-fill", "PJ", 1),
    ("tarjetas", "Más amonestados", "bi-file-earmark-fill", "pts", 1),
    ("faltas_recibidas", "Más infractados", "bi-bandaid-fill", "faltas", 1),
    ("valoracion", "Mejor valoración", "bi-star-fill", "OVR", 0),
]
TOP_SELECCIONES = [
    ("puntos", "Puntos", "bi-trophy-fill", "pts"),
    ("victorias", "Victorias", "bi-check-circle-fill", "G"),
    ("goles_favor", "Goles a favor", "bi-dribbble", "GF"),
    ("defensa", "Mejor defensa", "bi-shield-fill", "GC/PJ"),
    ("diferencia", "Diferencia de gol", "bi-plus-slash-minus", "DG"),
    ("efectividad", "Efectividad de tiro", "bi-bullseye", "%"),
    ("posesion", "Posesión", "bi-pie-chart-fill", "%"),
    ("vallas", "Vallas invictas", "bi-lock-fill", "vallas"),
    ("fair_play", "Fair play", "bi-hand-thumbs-up-fill", "tarj./PJ"),
    ("aficionados", "Más aficionados", "bi-people-fill", "fans"),
]
MINIMO_PJ_RANKING_SELECCION = 3

_cache_vista = {"clave": None, "stats": None, "juegos": None, "agregado": None, "paises": None}


def _juegos_del_mundial() -> list:
    """Partidos jugados del Mundial activo, con la proyección que usan todas las secciones (una sola carga)."""
    return list(db["juegos"].find({**_filtro_finalizados()}, PROYECCION_JUEGOS_MUNDIAL).sort([("fecha", 1), ("hora", 1)]))


def _agregar_jugadores_mundial(juegos: list) -> dict:
    """
    {jugador_id: {nombre, pais_id, posicion_id, overall, metricas: {m: total}, partidos_por: {m: {juego_id: n}}}}
    recorriendo UNA vez los partidos. Los nombres de los eventos se resuelven a id con (país, nombre),
    así dos jugadores homónimos de selecciones distintas no se mezclan.
    """
    ids = {pid for j in juegos for pid in ((j.get("resultado") or {}).get("participantes") or [])}
    ids |= {g.get("jugador_id") for j in juegos for g in ((j.get("resultado") or {}).get("goleadores") or [])}
    info = {d["id"]: d for d in db["jugadores"].find({"id": {"$in": [i for i in ids if i is not None]}},
                                                     {"_id": 0, "id": 1, "nombre": 1, "pais_id": 1, "posicion_id": 1, "overall": 1})}
    por_clave = {(d.get("pais_id"), d.get("nombre")): d["id"] for d in info.values()}
    agregado: Dict[int, dict] = {}

    def sumar(jugador_id, metrica, juego_id, n=1):
        if jugador_id is None or not n:
            return
        a = agregado.get(jugador_id)
        if a is None:
            d = info.get(jugador_id, {})
            a = agregado[jugador_id] = {"id": jugador_id, "nombre": d.get("nombre", "?"), "pais_id": d.get("pais_id"),
                                        "posicion_id": d.get("posicion_id"), "overall": d.get("overall"),
                                        "metricas": defaultdict(int), "partidos_por": defaultdict(dict)}
        a["metricas"][metrica] += n
        a["partidos_por"][metrica][juego_id] = a["partidos_por"][metrica].get(juego_id, 0) + n

    for j in juegos:
        jid = str(j["_id"])
        res = j.get("resultado") or {}
        local, visita = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
        pais_de_equipo = {local.get("nombre"): local.get("id"), visita.get("nombre"): visita.get("id")}
        rival = {local.get("id"): visita.get("id"), visita.get("id"): local.get("id")}
        for pid in res.get("participantes") or []:
            sumar(pid, "partidos", jid)
        for g in res.get("goleadores") or []:
            pid = g.get("jugador_id")
            sumar(pid, "goles", jid, g.get("goles", 0) or 0)
            for campo in ("goles_penal", "goles_tiro_libre", "goles_corner"):
                sumar(pid, campo, jid, g.get(campo, 0) or 0)
            if g.get("entro_de_cambio"):
                sumar(pid, "goles_suplente", jid, g.get("goles", 0) or 0)
        for a in res.get("atajadores") or []:
            sumar(a.get("jugador_id"), "atajadas", jid, a.get("atajadas", 0) or 0)

        for ev in res.get("eventos") or []:
            tipo, nombres = ev.get("tipo") or "", ev.get("jugadores") or []
            pais = pais_de_equipo.get(ev.get("equipo"))
            if pais is None or not nombres:
                continue
            propio = lambda i: por_clave.get((pais, nombres[i])) if len(nombres) > i else None
            del_rival = lambda i: por_clave.get((rival.get(pais), nombres[i])) if len(nombres) > i else None
            if tipo.startswith("⚽"):
                sumar(propio(0), "disparos", jid)
                sumar(propio(2), "asistencias", jid)
            elif tipo in ("🎯 DISPARO DESVIADO", "🧱 TIRO LIBRE BLOQUEADO"):
                sumar(propio(0), "disparos", jid)
            elif tipo == "🧤 ATAJADA ESPECTACULAR":
                sumar(del_rival(1), "disparos", jid)
            elif tipo == "❌ PENAL FALLADO":
                sumar(propio(0), "penales_atajados", jid)
                sumar(del_rival(1), "disparos", jid)
            elif tipo == "🟨 TARJETA AMARILLA":
                sumar(propio(0), "amarillas", jid)
                sumar(propio(0), "faltas", jid)
                sumar(del_rival(1), "faltas_recibidas", jid)
            elif tipo in ("🟥 TARJETA ROJA", "🟨🟥 DOBLE AMARILLA"):
                sumar(propio(0), "rojas", jid)
            elif tipo == "🛑 FALTA":
                sumar(propio(0), "faltas", jid)
                sumar(del_rival(1), "faltas_recibidas", jid)
            elif tipo == "🧠 ROBO DE BALÓN":
                sumar(propio(0), "recuperaciones", jid)
            elif tipo == "⚡ REGATE DESTACADO":
                sumar(propio(0), "regates", jid)
    return agregado


def _valor_jugador(a: dict, codigo: str):
    m = a["metricas"]
    if codigo == "contribucion":
        return m["goles"] + m["asistencias"]
    if codigo == "tarjetas":
        return m["amarillas"] + 3 * m["rojas"]
    if codigo == "valoracion":
        return round(a.get("overall") or 0, 1)
    return m[codigo]


def _agregar_paises_mundial(juegos: list, agregado: dict) -> dict:
    """{pais_id: {nombre, bandera, pj, g, e, p, gf, gc, vallas, tiros, suma_posesion, tarjetas, faltas, partidos: [juego_id]}}"""
    paises: Dict[int, dict] = {}
    for j in juegos:
        res = j.get("resultado") or {}
        gl, gv = res.get("goles_local", 0) or 0, res.get("goles_visitante", 0) or 0
        est = j.get("estadisticas") or {}
        for lado, rival, gf, gc in (("equipo_local", "equipo_visitante", gl, gv), ("equipo_visitante", "equipo_local", gv, gl)):
            eq = j.get(lado) or {}
            pid = eq.get("id")
            if pid is None:
                continue
            p = paises.setdefault(pid, {"id": pid, "nombre": eq.get("nombre"), "bandera": eq.get("bandera"), "pj": 0, "g": 0, "e": 0,
                                        "p": 0, "gf": 0, "gc": 0, "vallas": 0, "tiros": 0, "suma_posesion": 0.0, "tarjetas": 0,
                                        "faltas": 0, "partidos": []})
            p["pj"] += 1
            p["gf"] += gf
            p["gc"] += gc
            p["vallas"] += 1 if gc == 0 else 0
            ganador = res.get("ganador_id")
            if res.get("empate") or ganador is None:
                p["e"] += 1
            elif ganador == pid:
                p["g"] += 1
            else:
                p["p"] += 1
            lado_est = est.get("local" if lado == "equipo_local" else "visitante") or {}
            p["tiros"] += lado_est.get("tiros_totales", 0) or 0
            p["suma_posesion"] += lado_est.get("p_posesion", 0) or 0
            p["partidos"].append(str(j["_id"]))
    for a in agregado.values():
        p = paises.get(a.get("pais_id"))
        if p:
            p["tarjetas"] += a["metricas"]["amarillas"] + a["metricas"]["rojas"]
            p["faltas"] += a["metricas"]["faltas"]
    aficionados = {d["id"]: d.get("aficionados", 0) for d in db["paises"].find({"id": {"$in": list(paises)}}, {"id": 1, "aficionados": 1})}
    for p in paises.values():
        p["puntos"] = p["g"] * 3 + p["e"]
        p["dg"] = p["gf"] - p["gc"]
        p["aficionados"] = aficionados.get(p["id"], 0)
        p["posesion"] = round(p["suma_posesion"] / p["pj"], 1) if p["pj"] else 0
        p["efectividad"] = round(p["gf"] * 100 / p["tiros"], 1) if p["tiros"] >= 10 else None
        p["defensa"] = round(p["gc"] / p["pj"], 2) if p["pj"] >= MINIMO_PJ_RANKING_SELECCION else None
        p["fair_play"] = round((p["tarjetas"] + p["faltas"] / 4) / p["pj"], 2) if p["pj"] >= MINIMO_PJ_RANKING_SELECCION else None
    return paises


def _armar_top_jugadores(agregado: dict, nombres_paises: dict) -> list:
    tops = []
    candidatos = list(agregado.values())
    for codigo, titulo, icono, sufijo, minimo in TOP_JUGADORES:
        lista = candidatos if codigo != "atajadas" else [a for a in candidatos if a["metricas"]["atajadas"] > 0]
        ordenados = sorted(lista, key=lambda a: (-_valor_jugador(a, codigo), a["metricas"]["partidos"], a["nombre"]))
        filas = [a for a in ordenados if _valor_jugador(a, codigo) >= max(minimo, 0.0001)][:10]
        maximo = _valor_jugador(filas[0], codigo) if filas else 0
        tops.append({"codigo": codigo, "titulo": titulo, "icono": icono, "sufijo": sufijo, "filas": [{
            "posicion": i + 1, "id": a["id"], "nombre": a["nombre"], "pais_id": a["pais_id"],
            "pais": nombres_paises.get(a["pais_id"], {}).get("nombre", "?"), "bandera": nombres_paises.get(a["pais_id"], {}).get("bandera"),
            "valor": _valor_jugador(a, codigo), "partidos": a["metricas"]["partidos"],
            "pct": round(_valor_jugador(a, codigo) * 100 / maximo) if maximo else 0,
        } for i, a in enumerate(filas)]})
    return tops


def _armar_top_selecciones(paises: dict) -> list:
    tops = []
    asc = {"defensa", "fair_play"}
    for codigo, titulo, icono, sufijo in TOP_SELECCIONES:
        clave = {"victorias": "g", "goles_favor": "gf", "diferencia": "dg"}.get(codigo, codigo)
        lista = [p for p in paises.values() if p.get(clave) is not None]
        lista.sort(key=lambda p: (p[clave] if codigo in asc else -p[clave], -p["pj"], p["nombre"] or ""))
        filas = lista[:10]
        valores = [abs(p[clave]) for p in filas] or [0]
        maximo = max(valores)
        tops.append({"codigo": codigo, "titulo": titulo, "icono": icono, "sufijo": sufijo, "asc": codigo in asc, "filas": [{
            "posicion": i + 1, "id": p["id"], "nombre": p["nombre"], "bandera": p["bandera"], "valor": p[clave], "partidos": p["pj"],
            # en las métricas "menos es mejor" la barra se invierte: el líder (el menor) llena la barra
            "pct": (round((min(valores) or 0.01) * 100 / (abs(p[clave]) or 0.01)) if codigo in asc else (round(abs(p[clave]) * 100 / maximo) if maximo else 0)),
        } for i, p in enumerate(filas)]})
    return tops


def _lider(agregado: dict, codigo: str, nombres_paises: dict, clave_salida: str) -> Optional[dict]:
    """Líder de una métrica del agregado con la forma que ya usaba la vista (nombre, pais, pais_id, jugador_id, <clave>)."""
    candidatos = [a for a in agregado.values() if _valor_jugador(a, codigo) > 0]
    if not candidatos:
        return None
    a = max(candidatos, key=lambda x: (_valor_jugador(x, codigo), -x["metricas"]["partidos"]))
    return {"nombre": a["nombre"], "pais_id": a["pais_id"], "jugador_id": a["id"], "id": a["id"],
            "pais": nombres_paises.get(a["pais_id"], {}).get("nombre", "?"), clave_salida: _valor_jugador(a, codigo),
            "metrica": codigo}


def _jugadores_desde_agregado(juegos: list, agregado: dict, paises_agregado: dict, nombres_paises: dict) -> tuple:
    """
    Líderes de jugadores y arqueros del Mundial en curso, todos desde el agregado (sin consultas
    extra): (jugadores, porteros) con la misma forma que usaba la vista.
    """
    pais = lambda pid: nombres_paises.get(pid, {}).get("nombre", "?")
    lider = lambda codigo, campo: _lider(agregado, codigo, nombres_paises, campo)
    jugadores = {clave: lider(codigo, campo) for clave, codigo, campo in (
        ("mas_partidos", "partidos", "juegos_jugados"), ("mas_goles", "goles", "goles"), ("mas_amarillas", "amarillas", "amarilla"),
        ("mas_rojas", "rojas", "roja"), ("mas_faltas", "faltas", "faltas"), ("mas_infringido", "faltas_recibidas", "faltas_recibidas"),
        ("mas_asistencias", "asistencias", "asistencias"), ("mas_recuperaciones", "recuperaciones", "recuperaciones"),
        ("super_sub", "goles_suplente", "goles"))}
    # Balón parado: goles de penal + tiro libre + córner
    balon = max(agregado.values(), key=lambda a: (a["metricas"]["goles_penal"] + a["metricas"]["goles_tiro_libre"] + a["metricas"]["goles_corner"]), default=None)
    total_balon = (balon["metricas"]["goles_penal"] + balon["metricas"]["goles_tiro_libre"] + balon["metricas"]["goles_corner"]) if balon else 0
    jugadores["especialista_balon_parado"] = ({"nombre": balon["nombre"], "jugador_id": balon["id"], "pais_id": balon["pais_id"], "pais": pais(balon["pais_id"]),
                                               "goles": total_balon, "metrica": "balon_parado"} if total_balon else None)
    # Efectividad: goles / disparos (mínimo MINIMO_TIROS_EFECTIVIDAD_GOL disparos)
    calificados = [a for a in agregado.values() if a["metricas"]["disparos"] >= MINIMO_TIROS_EFECTIVIDAD_GOL]
    efect = max(calificados, key=lambda a: (a["metricas"]["goles"] / a["metricas"]["disparos"], a["metricas"]["goles"]), default=None)
    jugadores["mejor_efectividad_gol"] = ({"nombre": efect["nombre"], "jugador_id": efect["id"], "pais_id": efect["pais_id"], "pais": pais(efect["pais_id"]),
                                           "goles": efect["metricas"]["goles"], "tiros_totales": efect["metricas"]["disparos"],
                                           "efectividad_gol": round(efect["metricas"]["goles"] * 100 / efect["metricas"]["disparos"], 1), "metrica": "goles"} if efect else None)
    # Racha: partidos SEGUIDOS (de los que jugó) anotando, en orden cronológico
    racha_actual, mejor = defaultdict(int), {"jugador": None, "partidos_consecutivos": 0}
    for j in juegos:
        res = j.get("resultado") or {}
        anotaron = {g.get("jugador_id") for g in res.get("goleadores") or [] if (g.get("goles") or 0) > 0}
        for pid in res.get("participantes") or []:
            racha_actual[pid] = racha_actual[pid] + 1 if pid in anotaron else 0
            if racha_actual[pid] > mejor["partidos_consecutivos"] and pid in agregado:
                a = agregado[pid]
                mejor = {"jugador": a["nombre"], "jugador_id": pid, "pais_id": a["pais_id"], "pais": pais(a["pais_id"]),
                         "partidos_consecutivos": racha_actual[pid], "metrica": "goles"}
    jugadores["mayor_racha_goles"] = mejor if mejor["jugador"] else None
    jugadores["especialista_aereo"] = db["jugadores"].find_one({"id": {"$in": list(agregado)}}, {"_id": 0, "id": 1, "nombre": 1, "pais_id": 1, "juego_aereo": 1},
                                                              sort=[("juego_aereo", -1)])
    if jugadores["especialista_aereo"]:
        ea = jugadores["especialista_aereo"]
        ea.update(jugador_id=ea["id"], pais=pais(ea.get("pais_id")))

    arqueros = [a for a in agregado.values() if a["metricas"]["atajadas"] > 0]
    guante = max(arqueros, key=lambda a: (a["metricas"]["atajadas"], -a["metricas"]["partidos"]), default=None)
    atajapenales = max(arqueros, key=lambda a: a["metricas"]["penales_atajados"], default=None)
    pais_vallas = max(paises_agregado.values(), key=lambda p: (p["vallas"], -p["gc"]), default=None)
    arquero_vallas = max((a for a in arqueros if pais_vallas and a["pais_id"] == pais_vallas["id"]), key=lambda a: a["metricas"]["partidos"], default=None)
    porteros = {
        "portero_mas_atajadas": ({"portero": guante["nombre"], "jugador_id": guante["id"], "pais_id": guante["pais_id"], "equipo": pais(guante["pais_id"]),
                                  "total_atajadas": guante["metricas"]["atajadas"], "metrica": "atajadas"} if guante else None),
        "portero_mas_vallas_invictas": ({"portero": arquero_vallas["nombre"], "jugador_id": arquero_vallas["id"], "pais_id": pais_vallas["id"],
                                         "pais": pais_vallas["nombre"], "partidos_sin_recibir_gol": pais_vallas["vallas"], "metrica": "vallas"}
                                        if arquero_vallas and pais_vallas["vallas"] else None),
        "atajapenales": ({"portero": atajapenales["nombre"], "jugador_id": atajapenales["id"], "pais_id": atajapenales["pais_id"],
                          "pais": pais(atajapenales["pais_id"]), "total": atajapenales["metricas"]["penales_atajados"], "metrica": "penales_atajados"}
                         if atajapenales and atajapenales["metricas"]["penales_atajados"] else None),
    }
    return jugadores, porteros


def obtener_estadisticas_generales():
    """
    Todas las métricas de /estadisticas DEL MUNDIAL EN CURSO. Se cachean en memoria hasta que termina
    otro partido (clave: Mundial activo + cantidad de partidos jugados, un conteo barato): armar todo
    lleva unos segundos porque recorre los eventos de cada partido.
    """
    clave = (_mundial_activo_id(), db["juegos"].count_documents({**_filtro_finalizados()}))
    if _cache_vista["clave"] == clave and _cache_vista["stats"] is not None:
        return _cache_vista["stats"]

    juegos = _juegos_del_mundial()
    agregado = _agregar_jugadores_mundial(juegos)
    paises_agregado = _agregar_paises_mundial(juegos, agregado)
    nombres_paises = {p["id"]: {"nombre": p.get("nombre"), "bandera": p.get("bandera")} for p in db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1})}

    partidos = _get_stats_partidos(juegos)
    partidos.update(_obtener_records_primer_gol(juegos))
    partidos["sede_mas_goleadora"] = _obtener_sede_mas_goleadora(juegos)

    # Líderes del Mundial en curso desde el agregado (los contadores de 'jugadores' acumulan mundiales)
    jugadores, porteros = _jugadores_desde_agregado(juegos, agregado, paises_agregado, nombres_paises)

    paises = _get_stats_paises(juegos)
    con_pj = [p for p in paises_agregado.values() if p["defensa"] is not None]
    if con_pj:
        mejor = min(con_pj, key=lambda p: (p["defensa"], -p["pj"]))
        paises["mejor_defensiva"] = {"id": mejor["id"], "nombre": mejor["nombre"], "bandera": mejor["bandera"],
                                     "estadisticas": {"goles_contra": mejor["gc"], "diferencia_goles": mejor["dg"], "partidos": mejor["pj"],
                                                      "gc_por_partido": mejor["defensa"], "vallas": mejor["vallas"]}}
        limpio = min(con_pj, key=lambda p: (p["fair_play"], -p["pj"]))
        paises["fair_play"] = {"id": limpio["id"], "nombre": limpio["nombre"], "bandera": limpio["bandera"], "faltas": limpio["faltas"],
                               "tarjetas": limpio["tarjetas"], "total_infracciones": limpio["tarjetas"] + limpio["faltas"], "partidos": limpio["pj"]}
    for clave_pais in ("pais_mas_goleador", "mejor_ofensiva", "mejor_efectividad_gol"):
        reg = paises.get(clave_pais)
        if reg and reg.get("id") is None:
            reg["id"] = next((pid for pid, p in paises_agregado.items() if p["nombre"] == reg.get("nombre")), None)

    tendencias = _get_stats_tendencias(juegos)
    stats = {
        "jugadores": jugadores,
        "porteros": porteros,
        "arbitros": _get_stats_arbitros(),
        "arbitros_avanzado": _get_stats_arbitros_avanzado(juegos),
        "partidos": partidos,
        "tendencias": tendencias,
        "paises": paises,
        "torneos": _get_stats_torneos(),
        "once_ideal": _get_11_ideal(),
        "once_leyendas": _get_11_ideal(leyendas=True),
        "top_jugadores": _armar_top_jugadores(agregado, nombres_paises),
        "top_selecciones": _armar_top_selecciones(paises_agregado),
        "mundial": db["mundiales"].find_one({"activo": True}, {"_id": 0, "anio": 1}),
    }
    _completar_ids_jugadores(stats)
    _cache_vista.update(clave=clave, stats=stats, juegos={str(j["_id"]): j for j in juegos}, agregado=agregado,
                        paises=paises_agregado, nombres_paises=nombres_paises)
    return stats


# --- Detalle al hacer clic (GET /estadisticas/api/detalle) ---
TITULOS_METRICA_JUGADOR = {
    "goles": "Goles", "asistencias": "Asistencias", "contribucion": "Goles + asistencias", "atajadas": "Atajadas",
    "recuperaciones": "Recuperaciones", "regates": "Regates", "disparos": "Disparos", "partidos": "Partidos jugados",
    "tarjetas": "Tarjetas", "amarillas": "Amarillas", "rojas": "Rojas", "faltas": "Faltas cometidas",
    "faltas_recibidas": "Faltas recibidas", "goles_suplente": "Goles saliendo del banco", "valoracion": "Partidos jugados",
    "balon_parado": "Goles a balón parado", "penales_atajados": "Penales atajados",
}
NOTA_METRICA = {"goles": ("gol", "goles"), "asistencias": ("asistencia", "asistencias"), "atajadas": ("atajada", "atajadas"),
                "recuperaciones": ("recuperación", "recuperaciones"), "regates": ("regate", "regates"), "disparos": ("disparo", "disparos"),
                "amarillas": ("🟨 amarilla", "🟨 amarillas"), "rojas": ("🟥 roja", "🟥 rojas"), "faltas": ("falta", "faltas"),
                "faltas_recibidas": ("falta recibida", "faltas recibidas"), "goles_suplente": ("gol desde el banco", "goles desde el banco"),
                "penales_atajados": ("penal atajado", "penales atajados")}
METRICAS_COMPUESTAS = {"contribucion": ("goles", "asistencias"), "tarjetas": ("amarillas", "rojas"),
                       "balon_parado": ("goles_penal", "goles_tiro_libre", "goles_corner"), "valoracion": ("partidos",)}


def _nota(metrica: str, n: int) -> str:
    sing, plur = NOTA_METRICA.get(metrica, (metrica, metrica))
    return f"{n} {sing if n == 1 else plur}"


def _partido_detalle(j: dict, nota: str, fases: dict) -> dict:
    res = j.get("resultado") or {}
    local, visita = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
    return {"id": str(j["_id"]), "fecha": j.get("fecha"), "fase": fases.get(j.get("fase_id"), ""), "grupo": j.get("grupo"),
            "local": {"id": local.get("id"), "nombre": local.get("nombre"), "bandera": local.get("bandera"), "goles": res.get("goles_local", 0)},
            "visitante": {"id": visita.get("id"), "nombre": visita.get("nombre"), "bandera": visita.get("bandera"), "goles": res.get("goles_visitante", 0)},
            "penales": (f"{res.get('penaltis_local')}-{res.get('penaltis_visitante')}" if res.get("penaltis_local") is not None else None),
            "nota": nota}


def obtener_detalle_estadistica(tipo: str, sujeto_id: int, metrica: str) -> Optional[dict]:
    """
    Detalle de una tarjeta o de una fila de los top 10: quién es, cuánto suma y EN QUÉ PARTIDOS sumó,
    con la contribución de cada partido. Usa el agregado cacheado por obtener_estadisticas_generales.
    """
    obtener_estadisticas_generales()   # arma (o reutiliza) el caché
    juegos, nombres_paises = _cache_vista["juegos"], _cache_vista["nombres_paises"]
    fases = {f["id"]: f.get("nombre", "") for f in db["fases"].find({}, {"id": 1, "nombre": 1})}

    if tipo == "jugador":
        a = _cache_vista["agregado"].get(sujeto_id)
        if not a:
            return None
        partes = METRICAS_COMPUESTAS.get(metrica, (metrica,))
        if any(p not in METRICAS_JUGADOR for p in partes):
            return None
        por_partido = defaultdict(list)
        for parte in partes:
            for jid, n in a["partidos_por"].get(parte, {}).items():
                if parte != "partidos":
                    por_partido[jid].append(_nota(parte if parte not in ("goles_penal", "goles_tiro_libre", "goles_corner") else "goles", n)
                                            + {"goles_penal": " de penal", "goles_tiro_libre": " de tiro libre", "goles_corner": " de córner"}.get(parte, ""))
                else:
                    por_partido[jid]
        lista = [_partido_detalle(juegos[jid], " · ".join(notas) or "Jugó el partido", fases) for jid, notas in por_partido.items() if jid in juegos]
        total = _valor_jugador(a, metrica) if metrica in ("contribucion", "tarjetas", "valoracion") else \
            sum(a["metricas"][p] for p in partes)
        pais = nombres_paises.get(a["pais_id"], {})
        sujeto = {"tipo": "jugador", "id": a["id"], "nombre": a["nombre"], "pais_id": a["pais_id"], "pais": pais.get("nombre"),
                  "bandera": pais.get("bandera"), "total": total, "partidos_jugados": a["metricas"]["partidos"],
                  "goles": a["metricas"]["goles"], "asistencias": a["metricas"]["asistencias"], "url": f"/jugadores/{a['id']}"}
    elif tipo == "seleccion":
        p = _cache_vista["paises"].get(sujeto_id)
        if not p:
            return None
        lista = []
        for jid in p["partidos"]:
            j = juegos.get(jid)
            if not j:
                continue
            res = j.get("resultado") or {}
            es_local = (j.get("equipo_local") or {}).get("id") == sujeto_id
            gf, gc = (res.get("goles_local", 0), res.get("goles_visitante", 0)) if es_local else (res.get("goles_visitante", 0), res.get("goles_local", 0))
            ganador = res.get("ganador_id")
            resultado = "Empate" if (res.get("empate") or ganador is None) else ("Victoria" if ganador == sujeto_id else "Derrota")
            notas = [resultado]
            if metrica == "vallas" and gc == 0:
                notas.append("valla invicta")
            if metrica in ("goles_favor", "diferencia", "defensa"):
                notas.append(f"{gf} a favor · {gc} en contra")
            if metrica == "vallas" and gc != 0:
                continue
            if metrica == "victorias" and resultado != "Victoria":
                continue
            lista.append(_partido_detalle(j, " · ".join(notas), fases))
        clave = {"victorias": "g", "goles_favor": "gf", "diferencia": "dg"}.get(metrica, metrica)
        sujeto = {"tipo": "seleccion", "id": p["id"], "nombre": p["nombre"], "pais_id": p["id"], "bandera": p["bandera"],
                  "total": p.get(clave), "partidos_jugados": p["pj"], "g": p["g"], "e": p["e"], "p": p["p"], "gf": p["gf"], "gc": p["gc"],
                  "url": f"/paises/{p['id']}"}
    else:
        return None
    lista.sort(key=lambda x: x.get("fecha") or "", reverse=True)
    titulo = TITULOS_METRICA_JUGADOR.get(metrica) if tipo == "jugador" else next((t[1] for t in TOP_SELECCIONES if t[0] == metrica), metrica)
    return {"titulo": titulo, "metrica": metrica, "sujeto": sujeto, "partidos": lista}
