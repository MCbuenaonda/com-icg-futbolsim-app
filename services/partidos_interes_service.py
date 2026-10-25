"""
"Por qué mirar este partido": motivos de interés de un partido PENDIENTE, para las tarjetas de /juegos (chips) y el
detalle previo /simulador/?id= (sección completa).

Motivos (cada uno con un peso: la suma da el nivel "imperdible / caliente / interesante"):
  - DECISIVO (fase de grupos): con la misma matemática de clasificación del Scouter
    (prematch_service._determinar_estado_clasificacion: techo de puntos propio contra el de los rivales), se prueba cada
    resultado posible del partido (gana / empata / pierde) para cada equipo: si alguno lo deja CLASIFICADO o ELIMINADO,
    el partido puede definir su suerte. Es conservador como el Scouter (el resto de los partidos quedan abiertos).
  - SERIE: partido de vuelta de un cruce a dos partidos (con el marcador de la ida) o eliminación directa (fases 8+).
  - TOP 10: la selección o alguno de sus jugadores está en los top 10 de /estadisticas. Se toman de la caché de
    estadisticas_service (si quedó un partido atrasada se usa igual y se refresca en segundo plano; si todavía no existe,
    se arma en segundo plano y los tops aparecen en la próxima visita: armarla lleva varios segundos).
  - DT: el técnico de alguno está en la cuerda floja (riesgo de cese alto) o debuta en el cargo.
"""
import threading
from collections import defaultdict
from typing import Any, Dict, List, Optional

from bson import ObjectId

from services import estadisticas_service as E
from services import prematch_service as P
from services import tecnicos_service as T
from services.clasificacion_service import obtener_tablas_posiciones_por_grupo

db = P.db

# Listas de /estadisticas que cuentan para las tarjetas (en el detalle se muestran todas)
LISTAS_SELECCION_CLAVE = {"puntos", "victorias", "goles_favor", "defensa", "diferencia"}
LISTAS_JUGADOR_CLAVE = {"goles", "asistencias", "contribucion", "atajadas", "valoracion"}
PODIO = 3                       # solo suma al nivel quien está entre los 3 primeros de una lista clave
RIESGO_CUERDA_FLOJA = 25        # % de chance de cese tras el partido
TOP = 10
PESOS = {"decisivo": 4, "serie": 3, "mata_mata": 4, "dt_riesgo": 2, "dt_debut": 1, "top_seleccion": 1, "top_jugador": 1}
NIVELES = [(6, "imperdible", "Imperdible", "bi-fire"), (4, "caliente", "Partido caliente", "bi-thermometer-high"),
           (2, "interesante", "Para seguir", "bi-eye-fill")]

_refrescando = threading.Lock()


# --- Top 10 de Estadísticas ------------------------------------------------------------------------------------------
def _refrescar_estadisticas():
    if not _refrescando.acquire(blocking=False):
        return
    try:
        E.obtener_estadisticas_generales()
    except Exception as e:
        print(f"[interes] no se pudo refrescar estadísticas: {e}")
    finally:
        _refrescando.release()


def _estadisticas(bloquear: bool) -> Optional[dict]:
    """Las estadísticas del Mundial: al día si están en caché; si quedaron viejas se usan igual (y se refrescan aparte)."""
    stats = E._cache_vista.get("stats")
    if bloquear or stats is None:
        if stats is None and not bloquear:
            threading.Thread(target=_refrescar_estadisticas, daemon=True).start()
            return None
        return E.obtener_estadisticas_generales()
    clave = (E._mundial_activo_id(), db["juegos"].count_documents({**E._filtro_finalizados()}))
    if E._cache_vista.get("clave") != clave:
        threading.Thread(target=_refrescar_estadisticas, daemon=True).start()
    return stats


def _tops_por_pais(stats: Optional[dict]) -> Dict[int, dict]:
    """{pais_id: {'selecciones': [{titulo, posicion, valor, sufijo, icono}], 'jugadores': [{nombre, id, titulo, posicion, ...}]}}"""
    salida: Dict[int, dict] = defaultdict(lambda: {"selecciones": [], "jugadores": []})
    if not stats:
        return salida
    for bloque in stats.get("top_selecciones") or []:
        for f in (bloque.get("filas") or [])[:TOP]:
            salida[f["id"]]["selecciones"].append({"codigo": bloque["codigo"], "titulo": bloque["titulo"], "icono": bloque.get("icono"), "posicion": f["posicion"],
                                                   "valor": f.get("valor"), "sufijo": bloque.get("sufijo", "")})
    for bloque in stats.get("top_jugadores") or []:
        for f in (bloque.get("filas") or [])[:TOP]:
            salida[f["pais_id"]]["jugadores"].append({"id": f["id"], "codigo": bloque["codigo"], "nombre": f["nombre"], "titulo": bloque["titulo"], "icono": bloque.get("icono"),
                                                      "posicion": f["posicion"], "valor": f.get("valor"), "sufijo": bloque.get("sufijo", "")})
    return salida


# Líderes de cada selección en el Mundial (ficha /paises/{id}): (métrica del agregado, título, ícono, sufijo)
LIDERES_PAIS = [("goles", "Goleador", "bi-dribbble", "goles"), ("asistencias", "Asistidor", "bi-share-fill", "asist."),
                ("atajadas", "Arquero", "bi-hand-index-thumb-fill", "atajadas"), ("recuperaciones", "Recuperador", "bi-shield-fill-check", "recup."),
                ("regates", "Regateador", "bi-lightning-fill", "regates"), ("disparos", "Más disparos", "bi-bullseye", "disparos")]


def destacados_de_pais(pais_id: int) -> Optional[dict]:
    """Para la ficha del país: en qué top 10 de /estadisticas aparece la selección y cada jugador suyo, y los líderes de
    la selección en el Mundial. Nunca espera a Estadísticas (si no está armada devuelve None y aparece en la próxima visita)."""
    stats = _estadisticas(bloquear=False)
    if not stats:
        return None
    tops = _tops_por_pais(stats).get(pais_id) or {"selecciones": [], "jugadores": []}
    por_jugador: Dict[int, dict] = {}
    for x in sorted(tops["jugadores"], key=lambda x: x["posicion"]):
        j = por_jugador.setdefault(x["id"], {"id": x["id"], "nombre": x["nombre"], "listas": []})
        j["listas"].append(x)
    jugadores = sorted(por_jugador.values(), key=lambda j: (j["listas"][0]["posicion"], -len(j["listas"])))
    for j in jugadores:
        j["mejor"] = j["listas"][0]["posicion"]
        j["resumen"] = " · ".join(f"#{x['posicion']} {x['titulo'].lower()} ({x['valor']})" for x in j["listas"])

    agregado = E._cache_vista.get("agregado") or {}
    propios = [a for a in agregado.values() if a.get("pais_id") == pais_id]
    lideres = []
    for metrica, titulo, icono, sufijo in LIDERES_PAIS:
        con = [a for a in propios if (a["metricas"].get(metrica) or 0) > 0]
        if not con:
            continue
        a = max(con, key=lambda a: (a["metricas"][metrica], -(a["metricas"].get("partidos") or 0)))
        lideres.append({"titulo": titulo, "icono": icono, "sufijo": sufijo, "id": a["id"], "nombre": a["nombre"],
                        "valor": a["metricas"][metrica], "partidos": a["metricas"].get("partidos") or 0})
    if not (tops["selecciones"] or jugadores or lideres):
        return None
    return {"selecciones": sorted(tops["selecciones"], key=lambda x: x["posicion"]), "jugadores": jugadores,
            "por_jugador": {j["id"]: j for j in jugadores}, "lideres": lideres}


# --- Matemática de clasificación ---------------------------------------------------------------------------------------
ETIQUETA_ESTADO = {
    P.EstadoClasificacion.MATHEMATICALLY_QUALIFIED: ("clasificado", "Clasificado"),
    P.EstadoClasificacion.ELIMINATED: ("eliminado", "Eliminado"),
    P.EstadoClasificacion.DEPENDS_ON_SELF: ("depende", "Depende de sí"),
    P.EstadoClasificacion.NEEDS_OUTSIDE_RESULTS: ("necesita", "Necesita ayuda"),
}


def _contexto_grupo(juego: dict, cache: dict, incluir_id=None) -> Optional[dict]:
    """Tabla, partidos restantes y reglas del grupo del partido (cacheado por grupo dentro de un mismo pedido)."""
    fase, conf, grupo = juego.get("fase_id"), juego.get("confederacion_id"), juego.get("grupo")
    if not grupo or fase is None or fase in P.FASES_ELIMINACION_DIRECTA:
        return None
    clave = (juego.get("mundial_id"), fase, conf, grupo, str(incluir_id))
    if clave in cache:
        return cache[clave]
    if (fase, conf) not in cache:
        cache[(fase, conf)] = obtener_tablas_posiciones_por_grupo(db, fase, conf)
    tabla = cache[(fase, conf)].get(grupo.split()[-1])
    if not tabla:
        cache[clave] = None
        return None
    restantes: Dict[int, int] = defaultdict(int)
    # el partido en transmisión ya está guardado como finalizado, pero sus efectos sobre la tabla todavía no se aplicaron:
    # para el cálculo cuenta como pendiente (incluir_id)
    pendientes = {"estado": {"$ne": "finalizado"}} if incluir_id is None else {"$or": [{"estado": {"$ne": "finalizado"}}, {"_id": incluir_id}]}
    for p in db["juegos"].find({"mundial_id": juego.get("mundial_id"), "fase_id": fase, "confederacion_id": conf, "grupo": grupo,
                                **pendientes}, {"equipo_local.id": 1, "equipo_visitante.id": 1}):
        for lado in ("equipo_local", "equipo_visitante"):
            pid = (p.get(lado) or {}).get("id")
            if pid is not None:
                restantes[pid] += 1
    reglas = P._obtener_reglas_clasificacion_grupo(fase, len(tabla))
    cache[clave] = {"tabla": tabla, "restantes": restantes, "cupos_directos": reglas["cupos_directos"],
                    "total_cupos": reglas["cupos_directos"] + len(reglas["posiciones_con_posibilidad"]), "equipos": len(tabla)}
    return cache[clave]


def _analisis(tabla, restantes, extra: Dict[int, int] = None, menos: set = frozenset()) -> Dict[int, dict]:
    salida = {}
    for idx, f in enumerate(tabla, start=1):
        pid = f["pais_id"]
        pts = f["puntos"] + (extra or {}).get(pid, 0)
        rest = restantes.get(pid, 0) - (1 if pid in menos else 0)
        salida[pid] = {"posicion": idx, "puntos": pts, "partidos_restantes": rest, "puntos_maximos": pts + 3 * max(0, rest)}
    return salida


def escenarios_decisivos(juego: dict, cache: dict, incluir_id=None) -> Optional[dict]:
    """Para cada equipo del partido: su estado hoy y cómo queda si gana, empata o pierde (fase de grupos)."""
    ctx = _contexto_grupo(juego, cache, incluir_id)
    if not ctx:
        return None
    l, v = (juego.get("equipo_local") or {}).get("id"), (juego.get("equipo_visitante") or {}).get("id")
    if l not in ctx["restantes"] or v not in ctx["restantes"]:
        return None
    hoy = _analisis(ctx["tabla"], ctx["restantes"])
    if l not in hoy or v not in hoy:
        return None
    resultados = {"gana": (3, 0), "empata": (1, 1), "pierde": (0, 3)}
    equipos = {}
    for pid, rival in ((l, v), (v, l)):
        estado_hoy, _ = P._determinar_estado_clasificacion(pid, hoy, ctx["cupos_directos"], ctx["total_cupos"])
        por_resultado = {}
        for nombre, (pts_propios, pts_rival) in resultados.items():
            despues = _analisis(ctx["tabla"], ctx["restantes"], {pid: pts_propios, rival: pts_rival}, {pid, rival})
            est, _ = P._determinar_estado_clasificacion(pid, despues, ctx["cupos_directos"], ctx["total_cupos"])
            por_resultado[nombre] = {"codigo": ETIQUETA_ESTADO[est][0], "texto": ETIQUETA_ESTADO[est][1]}
        cod_hoy = ETIQUETA_ESTADO[estado_hoy][0]
        define = cod_hoy not in ("clasificado", "eliminado") and any(r["codigo"] in ("clasificado", "eliminado") for r in por_resultado.values())
        equipos[pid] = {"hoy": {"codigo": cod_hoy, "texto": ETIQUETA_ESTADO[estado_hoy][1]}, "por_resultado": por_resultado,
                        "posicion": hoy[pid]["posicion"], "puntos": hoy[pid]["puntos"], "restantes": hoy[pid]["partidos_restantes"],
                        "define": define, "ultima_fecha": hoy[pid]["partidos_restantes"] == 1}
    return {"equipos": equipos, "cupos": ctx["total_cupos"], "equipos_grupo": ctx["equipos"]}


def _frase_decisiva(nombre: str, e: dict) -> Optional[str]:
    pr = e["por_resultado"]
    clasifica = [r for r in ("gana", "empata") if pr[r]["codigo"] == "clasificado"]
    elimina = [r for r in ("pierde", "empata") if pr[r]["codigo"] == "eliminado"]
    if clasifica and elimina:
        return f"{nombre} se juega todo: {'con un empate' if 'empata' in clasifica else 'ganando'} clasifica y {'empatando' if 'empata' in elimina else 'perdiendo'} queda afuera"
    if clasifica:
        return f"{nombre} clasifica si {'no pierde' if 'empata' in clasifica else 'gana'}"
    if elimina:
        return f"{nombre} queda eliminado si {'no gana' if 'empata' in elimina else 'pierde'}"
    return None


# --- Motivos de cada partido ----------------------------------------------------------------------------------------
def motivos_partidos(juegos: List[dict], detalle: bool = False, en_vivo: bool = False) -> Dict[str, dict]:
    """{juego_id: {'puntaje', 'nivel', 'chips': [...], 'detalle'?: {...}}} para una lista de partidos pendientes."""
    if not juegos:
        return {}
    cache: Dict[Any, Any] = {}
    tops = _tops_por_pais(_estadisticas(bloquear=False))   # nunca espera: armar Estadísticas en frío lleva varios segundos
    ids_paises = {(j.get(lado) or {}).get("id") for j in juegos for lado in ("equipo_local", "equipo_visitante")}
    paises = {p["id"]: p for p in db["paises"].find({"id": {"$in": list(ids_paises)}}, {"id": 1, "dt_id": 1, "federacion_paciencia": 1})}
    cargos = {c["pais_id"]: c for c in db["dt_cargos"].find({"pais_id": {"$in": list(ids_paises)}, "hasta_juego": None}, {"juegos": 0})}
    dts = {d["id"]: d for d in db["directores_tecnicos"].find({"id": {"$in": [p.get("dt_id") for p in paises.values() if p.get("dt_id")]}}, {"_id": 0})}

    salida = {}
    for j in juegos:
        jid = str(j["_id"])
        loc, vis = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
        nombres = {loc.get("id"): loc.get("nombre"), vis.get("id"): vis.get("nombre")}
        chips, puntaje, det = [], 0, {}

        # 1) ¿define algo?
        fase = j.get("fase_id")
        if fase in P.FASES_ELIMINACION_DIRECTA:
            chips.append({"tipo": "mata_mata", "icono": "bi-lightning-charge-fill", "texto": "Eliminación directa: el que pierde se va"})
            puntaje += PESOS["mata_mata"]
            det["serie"] = {"tipo": "mata_mata"}
        elif j.get("tipo") == "vuelta" and (_contexto_grupo(j, cache, j["_id"] if en_vivo else None) or {}).get("equipos") == 2:
            ida = None
            try:
                from services.juegos_service import obtener_marcador_ida_grupo_dos_equipos
                ida = obtener_marcador_ida_grupo_dos_equipos(db, jid, loc.get("id"), vis.get("id"))
            except Exception:
                pass
            texto = "Partido de vuelta: se define la serie"
            if ida:
                texto += f" (ida {ida.get('goles_local', 0)}-{ida.get('goles_visita', 0)})"
            chips.append({"tipo": "serie", "icono": "bi-arrow-repeat", "texto": texto})
            puntaje += PESOS["serie"]
            det["serie"] = {"tipo": "vuelta", "ida": ida}
        else:
            try:
                esc = escenarios_decisivos(j, cache, j["_id"] if en_vivo else None)
            except Exception as e:
                print(f"[interes] escenarios de {jid}: {e}")
                esc = None
            if esc:
                det["escenarios"] = esc
                for pid, e in esc["equipos"].items():
                    frase = _frase_decisiva(nombres.get(pid), e) if e["define"] else None
                    if frase:
                        chips.append({"tipo": "decisivo", "icono": "bi-flag-fill", "texto": frase})
                        puntaje += PESOS["decisivo"]
                if not any(c["tipo"] == "decisivo" for c in chips) and any(e["ultima_fecha"] and e["hoy"]["codigo"] in ("depende", "necesita")
                                                                         for e in esc["equipos"].values()):
                    chips.append({"tipo": "decisivo", "icono": "bi-hourglass-bottom", "texto": "Última fecha del grupo con la clasificación abierta"})
                    puntaje += PESOS["decisivo"] - 1

        # 2) DT en la cuerda floja o debutando
        det["dts"] = {}
        for pid in (loc.get("id"), vis.get("id")):
            p, cg = paises.get(pid) or {}, cargos.get(pid)
            dt = dts.get(p.get("dt_id"))
            if not dt or not cg:
                continue
            riesgo = round(T.prob_cese(cg, p.get("federacion_paciencia") or 1.0, False) * 100)
            info = {"id": dt["id"], "nombre": dt["nombre"], "riesgo": riesgo, "partidos": cg.get("partidos", 0),
                    "record": f'{cg.get("ganados", 0)}-{cg.get("empatados", 0)}-{cg.get("perdidos", 0)}',
                    "arquetipo": T.arquetipo(dt)["titulo"], "estilo": T.ETIQUETA_ESTILO.get(dt.get("estilo"), ""),
                    "debut": cg.get("partidos", 0) == 0 and cg.get("motivo_inicio") == "REEMPLAZO", "regreso": bool(cg.get("regreso")),
                    "sobre": round((cg.get("puntos", 0) - cg.get("esperados", 0)) / cg["partidos"], 2) if cg.get("partidos") else 0.0}
            det["dts"][pid] = info
            if riesgo >= RIESGO_CUERDA_FLOJA:
                chips.append({"tipo": "dt_riesgo", "icono": "bi-thermometer-high", "texto": f"DT en la cuerda floja: {dt['nombre']} ({riesgo}%)"})
                puntaje += PESOS["dt_riesgo"]
            elif info["debut"]:
                chips.append({"tipo": "dt_debut", "icono": "bi-stars", "texto": f"{'Vuelve' if info['regreso'] else 'Debuta'} {dt['nombre']} en el banco de {nombres.get(pid)}"})
                puntaje += PESOS["dt_debut"]

        # 3) Top 10 de Estadísticas
        det["tops"] = {}
        for pid in (loc.get("id"), vis.get("id")):
            t = tops.get(pid)
            if not t or not (t["selecciones"] or t["jugadores"]):
                continue
            det["tops"][pid] = t
            clave_sel = [x for x in t["selecciones"] if x["codigo"] in LISTAS_SELECCION_CLAVE]
            if clave_sel:
                mejor = min(clave_sel, key=lambda x: x["posicion"])
                chips.append({"tipo": "top_seleccion", "icono": "bi-bar-chart-fill",
                              "texto": f"{nombres.get(pid)}: #{mejor['posicion']} en {mejor['titulo'].lower()}"})
                puntaje += PESOS["top_seleccion"] if mejor["posicion"] <= PODIO else 0
            clave_jug = [x for x in t["jugadores"] if x["codigo"] in LISTAS_JUGADOR_CLAVE]
            if clave_jug:
                figura = min(clave_jug, key=lambda x: x["posicion"])
                chips.append({"tipo": "top_jugador", "icono": "bi-star-fill",
                              "texto": f"{figura['nombre']}, #{figura['posicion']} en {figura['titulo'].lower()}"})
                puntaje += PESOS["top_jugador"] if figura["posicion"] <= PODIO else 0

        nivel = next(({"codigo": c, "texto": tx, "icono": ic} for umbral, c, tx, ic in NIVELES if puntaje >= umbral), None)
        orden = {"decisivo": 0, "mata_mata": 0, "serie": 1, "dt_riesgo": 2, "dt_debut": 3, "top_jugador": 4, "top_seleccion": 5}
        chips.sort(key=lambda c: orden.get(c["tipo"], 9))
        salida[jid] = {"puntaje": puntaje, "nivel": nivel, "chips": chips, **({"detalle": det} if detalle else {})}
    return salida


def motivos_partido(juego_id: str) -> Optional[dict]:
    """Para el detalle previo: los motivos de un partido con todo el detalle (escenarios, DTs y tops completos)."""
    j = db["juegos"].find_one({"_id": ObjectId(juego_id)})
    if not j or j.get("estado") == "finalizado":
        return None
    return motivos_partidos([j], detalle=True).get(juego_id)


def motivos_en_vivo() -> Optional[dict]:
    """Para /en-vivo: los motivos del partido en transmisión, con los escenarios por lado (local/visita) para que el
    navegador muestre "así como va" con el marcador ya revelado. No adelanta nada: tablas, cargos de DT y Estadísticas
    todavía no cuentan este partido (sus efectos se aplican al terminar la transmisión)."""
    from services.live_match_service import _match_en_progreso
    j = _match_en_progreso()
    if not j:
        return None
    jid = str(j["_id"])
    mot = motivos_partidos([j], detalle=True, en_vivo=True).get(jid) or {}
    det = mot.get("detalle") or {}
    loc, vis = (j.get("equipo_local") or {}), (j.get("equipo_visitante") or {})
    ids = {"local": loc.get("id"), "visita": vis.get("id")}
    esc = (det.get("escenarios") or {}).get("equipos") or {}
    return {"match_id": jid, "nivel": mot.get("nivel"), "chips": mot.get("chips") or [],
            "local": loc.get("nombre"), "visita": vis.get("nombre"), "ids": ids,
            "escenarios": {lado: esc.get(pid) for lado, pid in ids.items() if esc.get(pid)} or None,
            "serie": det.get("serie"),
            "dts": {lado: (det.get("dts") or {}).get(pid) for lado, pid in ids.items() if (det.get("dts") or {}).get(pid)}}
