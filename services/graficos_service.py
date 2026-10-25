"""
"El Mundial en gráficos" (/estadisticas/graficos): los datos de cada gráfico del Mundial EN CURSO, listos para
Chart.js. Reusa la carga y los agregados de estadisticas_service (misma caché: se recalcula solo cuando termina un
partido) y suma lo que esa vista no tenía: series en el tiempo, clima/aforo, historial de aficionados y pronósticos.

Los pronósticos usan el mismo modelo conservador que el asistente (asistente_reglas.probabilidades_partido,
calibrado fuera de muestra): el 'poder' de cada selección predice poco en este motor, así que las probabilidades
salen prudentes a propósito. Sin spoilers: solo partidos finalizados y fuera de transmisión.
"""
import math
import random
import statistics
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from config.eliminatorias import RONDAS_POR_CONFEDERACION
from services import estadisticas_service as ES
from services.asistente_reglas import probabilidades_partido

db = ES.db

_cache = {"clave": None, "datos": None}

NOMBRE_CONFEDERACION = {1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC", 7: "Repechaje", 8: "Mundial"}
VENTANA_MEDIA_MOVIL = 20
TOP_CARRERA_GOLEADORES = 5
TOP_AFICIONADOS = 5
PROXIMOS_PRONOSTICO = 8
SIMULACIONES_TITULO = 3000
EQUIPOS_SIMULADOS = 32
MINIMO_PJ = ES.MINIMO_PJ_RANKING_SELECCION


def _goles(j: dict) -> tuple:
    r = j.get("resultado") or {}
    return r.get("goles_local", 0) or 0, r.get("goles_visitante", 0) or 0


def _pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    if len(xs) < 3:
        return None
    try:
        return round(statistics.correlation(xs, ys), 2)
    except statistics.StatisticsError:
        return None


# ==========================================
# Ritmo del torneo
# ==========================================
def _ritmo(juegos: list, programados: int) -> dict:
    """Media móvil de goles por partido, goles acumulados y su proyección al total programado."""
    goles = [sum(_goles(j)) for j in juegos]
    n = len(goles)
    media = sum(goles) / n if n else 0
    movil = []
    for i in range(n):
        ventana = goles[max(0, i - VENTANA_MEDIA_MOVIL + 1): i + 1]
        movil.append(round(sum(ventana) / len(ventana), 2))
    acumulados, total = [], 0
    for g in goles:
        total += g
        acumulados.append(total)
    # Proyección: cada partido que falta aporta la media con su varianza (banda del 90%: ±1,645 σ√k)
    desvio = statistics.pstdev(goles) if n > 1 else 0
    proyeccion = []
    paso = max(1, (programados - n) // 40)
    for k in range(0, programados - n + 1, paso):
        centro = total + media * k
        banda = 1.645 * desvio * math.sqrt(k)
        proyeccion.append({"x": n + k, "y": round(centro), "min": round(centro - banda), "max": round(centro + banda)})
    if proyeccion and proyeccion[-1]["x"] != programados and programados > n:
        k = programados - n
        proyeccion.append({"x": programados, "y": round(total + media * k), "min": round(total + media * k - 1.645 * desvio * math.sqrt(k)),
                           "max": round(total + media * k + 1.645 * desvio * math.sqrt(k))})
    return {"media_movil": movil, "media": round(media, 2), "acumulados": acumulados, "proyeccion": proyeccion,
            "programados": programados, "jugados": n, "total_goles": total,
            "goles_finales": proyeccion[-1] if proyeccion else None, "ventana": VENTANA_MEDIA_MOVIL}


def _marcadores(juegos: list) -> dict:
    """Mapa de calor de marcadores (local × visita, 5+ agrupado)."""
    tope = 5
    cuenta = Counter((min(gl, tope), min(gv, tope)) for gl, gv in (_goles(j) for j in juegos))
    filas = [[cuenta.get((l, v), 0) for v in range(tope + 1)] for l in range(tope + 1)]
    frecuente = max(cuenta.items(), key=lambda kv: kv[1]) if cuenta else None
    return {"filas": filas, "etiquetas": [str(i) for i in range(tope)] + [f"{tope}+"], "maximo": max(cuenta.values()) if cuenta else 0,
            "frecuente": {"marcador": f"{frecuente[0][0]}-{frecuente[0][1]}", "veces": frecuente[1]} if frecuente else None,
            "total": len(juegos)}


# ==========================================
# Confederaciones
# ==========================================
def _confederaciones(juegos: list, agregado: dict) -> list:
    pendientes = Counter(d.get("confederacion_id") for d in db["juegos"].find(
        {"mundial_id": ES._mundial_activo_id(), "estado": "creado"}, {"confederacion_id": 1}))
    fase_actual: Dict[int, int] = {}
    for d in db["internacional"].find({}, {"confederacion_id": 1, "fase_eliminatoria": 1}):
        c = d.get("confederacion_id")
        fase_actual[c] = max(fase_actual.get(c, 0), d.get("fase_eliminatoria") or 0)
    datos: Dict[int, dict] = defaultdict(lambda: {"jugados": 0, "goles": 0, "tarjetas": 0})
    pais_conf = {p["id"]: p.get("confederacion_id") for p in db["paises"].find({}, {"id": 1, "confederacion_id": 1})}
    for j in juegos:
        c = j.get("confederacion_id") or pais_conf.get((j.get("equipo_local") or {}).get("id"))
        datos[c]["jugados"] += 1
        datos[c]["goles"] += sum(_goles(j))
    for a in agregado.values():
        c = pais_conf.get(a.get("pais_id"))
        if c in datos:
            datos[c]["tarjetas"] += a["metricas"]["amarillas"] + a["metricas"]["rojas"]
    salida = []
    for c in sorted(set(datos) | set(pendientes)):
        if c not in NOMBRE_CONFEDERACION or c in (7, 8):
            continue
        d = datos[c]
        pj = d["jugados"]
        salida.append({"id": c, "nombre": NOMBRE_CONFEDERACION[c], "jugados": pj, "pendientes": pendientes.get(c, 0),
                       "ronda": fase_actual.get(c), "rondas": RONDAS_POR_CONFEDERACION.get(c),
                       "goles_por_partido": round(d["goles"] / pj, 2) if pj else 0,
                       "tarjetas_por_partido": round(d["tarjetas"] / pj, 2) if pj else 0})
    return salida


# ==========================================
# Selecciones
# ==========================================
def _selecciones(paises: dict) -> dict:
    con_pj = [p for p in paises.values() if p["pj"] >= MINIMO_PJ]
    puntos = [{"id": p["id"], "nombre": p["nombre"], "bandera": p.get("bandera"), "pj": p["pj"],
               "ataque": round(p["gf"] / p["pj"], 2), "defensa": round(p["gc"] / p["pj"], 2), "dg": p["dg"],
               "posesion": p["posesion"], "ppp": round(p["puntos"] / p["pj"], 2)} for p in con_pj]
    destacados = {p["id"] for p in sorted(puntos, key=lambda p: (-(p["ataque"] - p["defensa"]), -p["pj"]))[:5]}
    for p in puntos:
        p["destacado"] = p["id"] in destacados
    med = lambda k: round(statistics.median([p[k] for p in puntos]), 2) if puntos else 0
    top_dg = sorted(paises.values(), key=lambda p: (-p["dg"], -p["gf"]))[:10]
    return {
        "dispersion": puntos, "mediana_ataque": med("ataque"), "mediana_defensa": med("defensa"),
        "posesion_r": _pearson([p["posesion"] for p in puntos], [p["ppp"] for p in puntos]),
        "top_dg": [{"id": p["id"], "nombre": p["nombre"], "bandera": p.get("bandera"), "dg": p["dg"], "gf": p["gf"], "gc": p["gc"],
                    "pj": p["pj"]} for p in top_dg],
        "minimo_pj": MINIMO_PJ,
    }


TRAYECTORIAS_DESTACADAS = 5


def _trayectorias(juegos: list, nombres: dict) -> dict:
    """
    Balance partido a partido de cada selección: todas arrancan en 0 y suman +1 por victoria, 0 por empate y -1 por
    derrota (por el marcador del partido, alargue incluido; una tanda de penales cuenta como empate). 'juegos' viene en
    orden cronológico. Destacadas por defecto: las de mejor balance final.
    """
    confederacion = {p["id"]: p.get("confederacion_id") for p in db["paises"].find({}, {"id": 1, "confederacion_id": 1})}
    series: Dict[int, dict] = {}
    for j in juegos:
        loc, vis = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
        if loc.get("id") is None or vis.get("id") is None:
            continue
        gl, gv = _goles(j)
        for yo, rival, gf, gc in ((loc, vis, gl, gv), (vis, loc, gv, gl)):
            s = series.setdefault(yo["id"], {"id": yo["id"], "nombre": nombres.get(yo["id"], {}).get("nombre") or yo.get("nombre"),
                                             "bandera": nombres.get(yo["id"], {}).get("bandera") or yo.get("bandera"),
                                             "conf": NOMBRE_CONFEDERACION.get(confederacion.get(yo["id"]), ""), "valores": [0], "partidos": []})
            s["valores"].append(s["valores"][-1] + (1 if gf > gc else (-1 if gf < gc else 0)))
            s["partidos"].append([rival.get("nombre"), gf, gc])   # compacto: [rival, goles a favor, goles en contra]
    lista = sorted(series.values(), key=lambda s: (-s["valores"][-1], -len(s["partidos"]), s["nombre"] or ""))
    return {"series": lista, "destacados": [s["id"] for s in lista[:TRAYECTORIAS_DESTACADAS]],
            "confederaciones": sorted({s["conf"] for s in lista if s["conf"]})}


def _aficionados() -> dict:
    """Curva de aficionados de las 5 selecciones más populares, partido a partido (historial_aficionados)."""
    top = list(db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1, "aficionados": 1}).sort("aficionados", -1).limit(TOP_AFICIONADOS))
    series = []
    for p in top:
        hist = list(db["historial_aficionados"].find({"pais_id": p["id"]}, {"aficionados_totales_resultantes": 1, "aficionados_ganados_perdidos": 1})
                    .sort("created_at", 1))
        if not hist:
            continue
        inicio = hist[0]["aficionados_totales_resultantes"] - hist[0].get("aficionados_ganados_perdidos", 0)
        valores = [inicio] + [h["aficionados_totales_resultantes"] for h in hist]
        series.append({"id": p["id"], "nombre": p["nombre"], "bandera": p.get("bandera"), "valores": valores,
                       "cambio": valores[-1] - valores[0]})
    return {"series": series}


# ==========================================
# Jugadores
# ==========================================
def _jugadores(juegos: list, agregado: dict, nombres_paises: dict) -> dict:
    # Carrera de goleadores: goles acumulados de los 5 máximos, partido a partido del torneo
    top = sorted(agregado.values(), key=lambda a: (-a["metricas"]["goles"], a["metricas"]["partidos"]))[:TOP_CARRERA_GOLEADORES]
    ids = [a["id"] for a in top]
    por_partido = [{g.get("jugador_id"): g.get("goles", 0) or 0 for g in ((j.get("resultado") or {}).get("goleadores") or [])} for j in juegos]
    carrera = []
    for a in top:
        acum, total = [], 0
        for p in por_partido:
            total += p.get(a["id"], 0)
            acum.append(total)
        pais = nombres_paises.get(a.get("pais_id"), {})
        carrera.append({"id": a["id"], "nombre": a["nombre"], "pais": pais.get("nombre"), "pais_id": a.get("pais_id"),
                        "valores": acum, "goles": total})

    # Cómo llegan los goles (parte de un todo, 4 tipos)
    tipos = Counter()
    for a in agregado.values():
        m = a["metricas"]
        quietos = m["goles_penal"] + m["goles_tiro_libre"] + m["goles_corner"]
        tipos["En jugada"] += max(0, m["goles"] - quietos)
        tipos["Penal"] += m["goles_penal"]
        tipos["Tiro libre"] += m["goles_tiro_libre"]
        tipos["Córner"] += m["goles_corner"]
    suplentes = sum(a["metricas"]["goles_suplente"] for a in agregado.values())

    # Goles por sector del campo y por edad (ordinal)
    posiciones = {p["id"]: p.get("sector") for p in db["posiciones"].find({}, {"id": 1, "sector": 1})}
    edades = {d["id"]: d.get("edad") for d in db["jugadores"].find({"id": {"$in": [a["id"] for a in agregado.values() if a["metricas"]["goles"]]}},
                                                                    {"id": 1, "edad": 1})}
    sectores, por_edad = Counter(), Counter()
    bandas = [(0, 21, "≤21"), (22, 24, "22-24"), (25, 27, "25-27"), (28, 30, "28-30"), (31, 33, "31-33"), (34, 99, "34+")]
    for a in agregado.values():
        g = a["metricas"]["goles"]
        if not g:
            continue
        sectores[posiciones.get(a.get("posicion_id"), "Otro")] += g
        edad = edades.get(a["id"])
        for desde, hasta, etiqueta in bandas:
            if edad is not None and desde <= edad <= hasta:
                por_edad[etiqueta] += g
                break
    orden_sector = ["Delantero", "Medio", "Defensa", "Portero"]
    return {
        "carrera": carrera, "partidos": len(juegos),
        "tipos": [{"tipo": t, "goles": tipos[t]} for t in ("En jugada", "Penal", "Tiro libre", "Córner")],
        "suplentes": suplentes, "total_goles": sum(tipos.values()),
        "sectores": [{"sector": s, "goles": sectores.get(s, 0)} for s in orden_sector],
        "edades": [{"banda": e, "goles": por_edad.get(e, 0)} for _, _, e in bandas],
    }


# ==========================================
# Estadios y clima
# ==========================================
def _estadios() -> dict:
    juegos = list(db["juegos"].find(ES._filtro_finalizados(), {"clima.condicion": 1, "clima.temperatura_c": 1, "aforo.porcentaje_ocupacion": 1,
                                                                "resultado.goles_local": 1, "resultado.goles_visitante": 1}))
    por_clima: Dict[str, List[int]] = defaultdict(list)
    ocupacion = Counter()
    temperatura = []
    for j in juegos:
        g = sum(_goles(j))
        c = (j.get("clima") or {}).get("condicion")
        if c:
            por_clima[c].append(g)
        t = (j.get("clima") or {}).get("temperatura_c")
        if t is not None:
            temperatura.append((t, g))
        o = (j.get("aforo") or {}).get("porcentaje_ocupacion")
        if o is not None:
            ocupacion[min(int(o // 10) * 10, 90)] += 1
    clima = sorted(({"condicion": c, "partidos": len(v), "promedio": round(sum(v) / len(v), 2)} for c, v in por_clima.items() if len(v) >= 5),
                   key=lambda x: -x["promedio"])
    return {"clima": clima, "ocupacion": [{"banda": f"{b}-{b + 10}%", "partidos": ocupacion.get(b, 0)} for b in range(0, 100, 10)],
            "temperatura_r": _pearson([t for t, _ in temperatura], [g for _, g in temperatura]),
            "con_datos": sum(ocupacion.values()), "minimo": 30, "con_clima": len(temperatura)}


# ==========================================
# Técnicos (services/tecnicos_service.py)
# ==========================================
MINIMO_MOTOR_DT = 30   # partidos jugados con el DT en el motor (reclamos, ajustes) para mostrar sus gráficos


def _tecnicos() -> dict:
    from services.tecnicos_service import fecha_corta
    """Ceses por confederación y a lo largo del torneo; y, con suficientes partidos jugados con el DT en el motor,
    rendimiento por estilo, reclamos según el temperamento y efecto de los ajustes tácticos."""
    siglas = {1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC"}
    conf = {p["id"]: siglas.get(p.get("confederacion_id"), "?") for p in db["paises"].find({}, {"id": 1, "confederacion_id": 1})}
    ceses = list(db["dt_cargos"].find({"motivo_fin": "CESE"}, {"pais_id": 1, "cese_por_eliminacion": 1, "hasta_fecha_juego": 1}))
    por_conf = {s: {"conf": s, "resultados": 0, "eliminacion": 0} for s in siglas.values()}
    for c in ceses:
        fila = por_conf.get(conf.get(c["pais_id"]))
        if fila:
            fila["eliminacion" if c.get("cese_por_eliminacion") else "resultados"] += 1
    tiempo, n = [], 0
    for c in sorted(ceses, key=lambda c: c.get("hasta_fecha_juego") or ""):
        n += 1
        tiempo.append({"fecha": fecha_corta(c.get("hasta_fecha_juego")) or c.get("hasta_fecha_juego"), "n": n})
    # partidos jugados con el DT en el motor: traen 'reclamos' en resultado.dt.*
    juegos = list(db["juegos"].find({**ES._filtro_finalizados(), "resultado.dt.local.reclamos": {"$exists": True}},
                                    {"resultado.dt": 1, "resultado.goles_local": 1, "resultado.goles_visitante": 1, "resultado.local": 1,
                                     "resultado.visitante": 1, "resultado.eventos.tipo": 1, "resultado.eventos.dt_id": 1,
                                     "resultado.eventos.equipo": 1, "resultado.eventos.ajuste": 1}))
    salida = {"ceses_conf": list(por_conf.values()), "ceses_tiempo": tiempo, "total_ceses": len(ceses),
              "regresos": db["dt_cargos"].count_documents({"regreso": True}), "motor": len(juegos), "minimo": MINIMO_MOTOR_DT}
    if len(juegos) < MINIMO_MOTOR_DT:
        return salida
    dts = {d["id"]: d for d in db["directores_tecnicos"].find({}, {"_id": 0, "id": 1, "estilo": 1, "temperamento": 1})}
    estilos = {e: {"estilo": e, "partidos": 0, "puntos": 0, "gf": 0, "gc": 0} for e in ("ofensivo", "equilibrado", "defensivo")}
    bandas = [("Frío (≤42)", 0, 42), ("Firme (43-67)", 43, 67), ("Caliente (≥68)", 68, 100)]
    temple = {b[0]: {"banda": b[0], "partidos": 0, "reclamos": 0, "amonestado": 0, "expulsado": 0} for b in bandas}
    ajustes = {"ataque": {"n": 0, "gol": 0}, "cerrar": {"n": 0, "mantuvo": 0}}
    for j in juegos:
        r = j["resultado"]
        for lado, gf, gc, eq in (("local", r["goles_local"], r["goles_visitante"], r.get("local")),
                                 ("visita", r["goles_visitante"], r["goles_local"], r.get("visitante"))):
            dt = (r.get("dt") or {}).get(lado) or {}
            d = dts.get(dt.get("id"))
            if not d:
                continue
            e = estilos.get(d.get("estilo"))
            if e:
                e["partidos"] += 1
                e["puntos"] += 3 if gf > gc else (1 if gf == gc else 0)
                e["gf"] += gf
                e["gc"] += gc
            t = next(temple[b[0]] for b in bandas if b[1] <= (d.get("temperamento") or 55) <= b[2])
            t["partidos"] += 1
            t["reclamos"] += dt.get("reclamos", 0)
            t["amonestado"] += bool(dt.get("amonestado"))
            t["expulsado"] += bool(dt.get("expulsado"))
            # efecto de los ajustes: tras "ataque", ¿llegó un gol propio?; tras "cerrar", ¿ganó el partido?
            eventos = r.get("eventos") or []
            for k, ev in enumerate(eventos):
                if ev.get("tipo") == "📋 AJUSTE TÁCTICO" and ev.get("dt_id") == dt.get("id") and ev.get("ajuste") in ajustes:
                    a = ajustes[ev["ajuste"]]
                    a["n"] += 1
                    if ev["ajuste"] == "ataque":
                        a["gol"] += any(x.get("tipo", "").startswith("⚽ GOL") and x.get("equipo") == eq for x in eventos[k + 1:])
                    else:
                        a["mantuvo"] += gf > gc
    salida["estilos"] = [{**e, "ppp": round(e["puntos"] / e["partidos"], 2) if e["partidos"] else 0,
                          "gfp": round(e["gf"] / e["partidos"], 2) if e["partidos"] else 0,
                          "gcp": round(e["gc"] / e["partidos"], 2) if e["partidos"] else 0} for e in estilos.values()]
    salida["temple"] = [{**t, **{f"{k}_p": round(t[k] / t["partidos"], 2) if t["partidos"] else 0 for k in ("reclamos", "amonestado", "expulsado")}}
                        for t in temple.values()]
    salida["ajustes"] = {"ataque": {**ajustes["ataque"], "pct": round(100 * ajustes["ataque"]["gol"] / ajustes["ataque"]["n"]) if ajustes["ataque"]["n"] else 0},
                         "cerrar": {**ajustes["cerrar"], "pct": round(100 * ajustes["cerrar"]["mantuvo"] / ajustes["cerrar"]["n"]) if ajustes["cerrar"]["n"] else 0}}
    return salida


# ==========================================
# Pronósticos
# ==========================================
def _poderes() -> Dict[int, dict]:
    salida = {}
    for d in db["internacional"].find({}, {"id": 1, "nombre": 1, "bandera": 1, "estado": 1, "estadisticas.poder": 1}):
        if str(d.get("estado") or "").startswith("ELIMINADO"):
            continue
        salida[d["id"]] = {"id": d["id"], "nombre": d.get("nombre"), "bandera": d.get("bandera"),
                           "poder": (d.get("estadisticas") or {}).get("poder", 0.0) or 0.0}
    return salida


def _proximos(poderes: Dict[int, dict]) -> list:
    """Probabilidades del modelo para los próximos partidos del calendario."""
    salida = []
    for j in db["juegos"].find({"mundial_id": ES._mundial_activo_id(), "estado": "creado"},
                               {"equipo_local": 1, "equipo_visitante": 1, "fecha": 1}).sort([("fecha", 1), ("hora", 1)]).limit(PROXIMOS_PRONOSTICO):
        l, v = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
        pl, pe, pv = probabilidades_partido((poderes.get(l.get("id")) or {}).get("poder", 0.0), (poderes.get(v.get("id")) or {}).get("poder", 0.0))
        salida.append({"id": str(j["_id"]), "local": l.get("nombre"), "visita": v.get("nombre"), "local_id": l.get("id"), "visita_id": v.get("id"),
                       "local_bandera": l.get("bandera"), "visita_bandera": v.get("bandera"),
                       "p_local": round(pl * 100), "p_empate": round(pe * 100), "p_visita": 100 - round(pl * 100) - round(pe * 100)})
    return salida


def _candidatos_titulo(poderes: Dict[int, dict]) -> dict:
    """
    Monte Carlo: "si el Mundial empezara hoy con las 32 selecciones de mayor poder", eliminación directa con cruces al
    azar y el modelo conservador (empate = penales 50/50). Semilla fija: el resultado solo cambia si cambian los datos.
    """
    equipos = sorted(poderes.values(), key=lambda p: -p["poder"])[:EQUIPOS_SIMULADOS]
    if len(equipos) < 2:
        return {"equipos": [], "simulaciones": 0}
    rng = random.Random(sum(int(p["poder"] * 100) for p in equipos))
    campeon = Counter()
    for _ in range(SIMULACIONES_TITULO):
        vivos = equipos[:]
        rng.shuffle(vivos)
        while len(vivos) > 1:
            siguiente = []
            for a, b in zip(vivos[::2], vivos[1::2]):
                pa, pe, _ = probabilidades_partido(a["poder"], b["poder"])
                x = rng.random()
                gana_a = x < pa or (pa <= x < pa + pe and rng.random() < 0.5)
                siguiente.append(a if gana_a else b)
            vivos = siguiente
        campeon[vivos[0]["id"]] += 1
    top = [{**poderes[i], "pct": round(c * 100 / SIMULACIONES_TITULO, 1)} for i, c in campeon.most_common(10)]
    return {"equipos": top, "simulaciones": SIMULACIONES_TITULO, "cupo": EQUIPOS_SIMULADOS,
            "uniforme": round(100 / len(equipos), 1)}


# ==========================================
# Punto de entrada
# ==========================================
def obtener_graficos() -> Dict[str, Any]:
    """Todo lo de /estadisticas/graficos. Misma clave de caché que /estadisticas (Mundial + partidos jugados)."""
    ES.obtener_estadisticas_generales()   # arma (o reusa) la carga y los agregados del Mundial
    cv = ES._cache_vista
    clave = cv["clave"]
    if _cache["clave"] == clave and _cache["datos"] is not None:
        return _cache["datos"]

    juegos = sorted(cv["juegos"].values(), key=lambda j: (j.get("fecha") or "", j.get("hora") or ""))
    agregado, paises, nombres = cv["agregado"], cv["paises"], cv["nombres_paises"]
    tendencias = cv["stats"]["tendencias"]
    programados = len(juegos) + db["juegos"].count_documents({"mundial_id": ES._mundial_activo_id(), "estado": "creado"})
    poderes = _poderes()
    ritmo = _ritmo(juegos, programados)
    datos = {
        "resumen": {"jugados": len(juegos), "programados": programados, "goles": tendencias.get("total_goles", 0),
                    "promedio": tendencias.get("promedio_goles", 0), "ambos_marcan": tendencias.get("pct_ambos_marcan", 0),
                    "resultados": tendencias.get("resultados") or {}, "pct_avance": round(len(juegos) * 100 / programados) if programados else 0},
        "ritmo": ritmo,
        "franjas": tendencias.get("goles_por_franja") or [],
        "marcadores": _marcadores(juegos),
        "confederaciones": _confederaciones(juegos, agregado),
        "selecciones": _selecciones(paises),
        "aficionados": _aficionados(),
        "trayectorias": _trayectorias(juegos, nombres),
        "jugadores": _jugadores(juegos, agregado, nombres),
        "estadios": _estadios(),
        "tecnicos": _tecnicos(),
        "proximos": _proximos(poderes),
        "titulo": _candidatos_titulo(poderes),
        "mundial": cv["stats"].get("mundial"),
    }
    _cache.update(clave=clave, datos=datos)
    return datos
