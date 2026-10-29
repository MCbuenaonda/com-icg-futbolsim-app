"""
"El calendario del Mundial" (/estadisticas/calendario) y la tarjeta "Un día como hoy" del inicio.

  - Estadísticas por FECHA del Mundial en curso: calendario de calor (partidos y goles por día), por mes, por día de la
    semana y por horario de inicio, y récords por fecha (día más goleador, racha de días seguidos con partidos...).
  - EFEMÉRIDES: los eventos relevantes del torneo con su fecha:
      partido  → partidos memorables según la historia principal de su crónica (resultado.cronica.historia/titular)
      gol      → hitos de goles del torneo (el 1, 100, 250, 500, 1000...)
      record   → mayor goleada, partido con más goles, arranque de cada confederación y de cada fase
      dt       → ceses de técnicos (dt_cargos) y DT expulsados
      eliminacion → la fecha del último partido de cada selección eliminada
  - "Un día como hoy": "hoy" es la fecha del torneo (el último partido jugado); se buscan efemérides del mismo día y mes
    en años anteriores, si no de la misma semana del año anterior, si no las más importantes de los últimos 30 días.
Solo lectura; nunca cuenta el partido en transmisión (estadisticas_service._filtro_finalizados). Cacheado en memoria
por (mundial, partidos jugados), como graficos_service.
"""
import threading
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Dict, List, Optional

from services import estadisticas_service as ES
from services.tecnicos_service import fecha_corta

db = ES.db

# Historias de la crónica que hacen memorable un partido: (peso, ícono, etiqueta)
HISTORIAS = {
    "remontada_epica": (95, "bi-rocket-takeoff-fill", "Remontada épica"),
    "tanda": (90, "bi-bullseye", "Definición por penales"),
    "agonico": (86, "bi-alarm-fill", "Gol agónico"),
    "paliza": (85, "bi-lightning-charge-fill", "Paliza"),
    "hat_trick": (82, "bi-3-circle-fill", "Hat-trick"),
    "sorpresa": (82, "bi-emoji-surprise-fill", "Batacazo"),
    "var_decisivo": (78, "bi-display", "El VAR decidió"),
    "leyenda_decisiva": (78, "bi-award-fill", "Una leyenda decidió"),
    "con_diez": (72, "bi-shield-fill", "Ganó con diez"),
    "remontada": (70, "bi-arrow-repeat", "Remontada"),
    "empate_agonico": (70, "bi-alarm", "Empate agónico"),
    "rescate": (68, "bi-life-preserver", "Rescate"),
    "ajuste_decisivo": (66, "bi-clipboard-check", "La pizarra del DT"),
    "goleada": (60, "bi-dribbble", "Goleada"),
    "empate_loco": (60, "bi-shuffle", "Empate loco"),
}
HITOS_GOL = [1, 100, 250, 500, 750, 1000, 1500, 2000, 2500, 3000, 4000, 5000]
DESTACADA = 80
TIPOS = [("partido", "Partidos memorables", "bi-stars"), ("gol", "Hitos de goles", "bi-dribbble"), ("record", "Récords y arranques", "bi-trophy-fill"),
         ("dt", "Técnicos", "bi-clipboard-check"), ("eliminacion", "Eliminaciones", "bi-x-octagon-fill")]
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
SIGLA_CONF = {1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC", 7: "Repechaje", 8: "Mundial"}
TIPOS_GOL = ("⚽ GOL", "⚽ GOL DE TIRO LIBRE", "⚽ GOL DE CÓRNER")   # '⚽ GOL DE PENAL' es solo de la tanda

_cache: Dict = {"clave": None, "datos": None}


def _fecha(iso: str) -> Optional[date]:
    try:
        a, m, d = (int(x) for x in str(iso)[:10].split("-"))
        return date(a, m, d)
    except (ValueError, TypeError):
        return None


def _juegos() -> List[dict]:
    proy = {"fecha": 1, "hora": 1, "fase_id": 1, "confederacion_id": 1, "jornada": 1, "grupo": 1,
            "equipo_local.id": 1, "equipo_local.nombre": 1, "equipo_local.bandera": 1,
            "equipo_visitante.id": 1, "equipo_visitante.nombre": 1, "equipo_visitante.bandera": 1,
            "resultado.goles_local": 1, "resultado.goles_visitante": 1, "resultado.cronica.historia": 1, "resultado.cronica.titular": 1,
            "resultado.eventos.tipo": 1, "resultado.eventos.jugadores": 1, "resultado.eventos.equipo": 1,
            "resultado.eventos.segundos_acumulados": 1, "resultado.eventos.dt_id": 1, "resultado.eventos.dt": 1, "resultado.eventos.minuto": 1,
            "resultado.eventos.adicional": 1}
    juegos = [j for j in db["juegos"].find(ES._filtro_finalizados(), proy) if _fecha(j.get("fecha"))]
    juegos.sort(key=lambda j: (j["fecha"], j.get("hora") or "", str(j["_id"])))
    return juegos


def _partido(j: dict) -> dict:
    r, loc, vis = j.get("resultado") or {}, j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
    return {"id": str(j["_id"]), "fecha": j["fecha"], "hora": j.get("hora"), "local": loc.get("nombre"), "local_id": loc.get("id"),
            "visita": vis.get("nombre"), "visita_id": vis.get("id"), "gl": r.get("goles_local", 0), "gv": r.get("goles_visitante", 0),
            "conf": SIGLA_CONF.get(j.get("confederacion_id"), ""), "jornada": j.get("jornada")}


def _goles_validos(eventos: List[dict]) -> List[dict]:
    """Los goles del partido en orden, sin los anulados por el VAR (el anulado comparte segundo con su GOL ANULADO)."""
    anulados = {e.get("segundos_acumulados") for e in eventos if e.get("tipo") == "🖥️ VAR - GOL ANULADO"}
    return [e for e in eventos if e.get("tipo") in TIPOS_GOL and e.get("segundos_acumulados") not in anulados]


# --- Estadísticas por fecha ---------------------------------------------------------------------------------------
def _estadisticas(juegos: List[dict]) -> dict:
    por_dia: Dict[str, dict] = {}
    for j in juegos:
        p = _partido(j)
        d = por_dia.setdefault(j["fecha"], {"fecha": j["fecha"], "partidos": 0, "goles": 0, "lista": []})
        d["partidos"] += 1
        d["goles"] += p["gl"] + p["gv"]
        d["lista"].append(p)
    if not por_dia:
        return {"meses": [], "por_mes": [], "por_dow": [], "por_hora": [], "records": {}, "dias": {}}

    inicio, fin = _fecha(min(por_dia)), _fecha(max(por_dia))
    max_goles = max(d["goles"] for d in por_dia.values())
    # calendario: un bloque por mes con los días entre el primero y el último jugado (también los sin partidos)
    meses, dia = [], inicio.replace(day=1)
    while dia <= fin:
        mes = {"anio": dia.year, "mes": dia.month, "nombre": f"{MESES[dia.month - 1]} {dia.year}", "offset": dia.weekday(), "dias": []}
        d = dia
        while d.month == mes["mes"]:
            iso = d.isoformat()
            info = por_dia.get(iso)
            mes["dias"].append({"fecha": iso, "dia": d.day, "partidos": info["partidos"] if info else 0, "goles": info["goles"] if info else 0,
                                "fuera": not (inicio <= d <= fin)})
            d += timedelta(days=1)
        if any(x["partidos"] for x in mes["dias"]) or inicio <= dia <= fin:
            meses.append(mes)
        dia = d

    por_mes = defaultdict(lambda: {"partidos": 0, "goles": 0})
    por_dow = defaultdict(lambda: {"partidos": 0, "goles": 0})
    por_hora = defaultdict(lambda: {"partidos": 0, "goles": 0})
    jornadas = defaultdict(lambda: {"goles": 0, "partidos": 0})
    for j in juegos:
        f = _fecha(j["fecha"])
        g = (j.get("resultado") or {}).get("goles_local", 0) + (j.get("resultado") or {}).get("goles_visitante", 0)
        for agg, clave in ((por_mes, (f.year, f.month)), (por_dow, f.weekday()), (por_hora, j.get("hora") or "—")):
            agg[clave]["partidos"] += 1
            agg[clave]["goles"] += g
        jk = (j.get("fase_id"), j.get("confederacion_id"), j.get("jornada"))
        jornadas[jk]["goles"] += g
        jornadas[jk]["partidos"] += 1

    def _gpp(x):
        return round(x["goles"] / x["partidos"], 2) if x["partidos"] else 0

    # racha de días seguidos con partidos
    fechas = sorted(_fecha(x) for x in por_dia)
    mejor = actual = 1
    fin_racha = fechas[0]
    for a, b in zip(fechas, fechas[1:]):
        actual = actual + 1 if (b - a).days == 1 else 1
        if actual > mejor:
            mejor, fin_racha = actual, b
    dia_goles = max(por_dia.values(), key=lambda d: (d["goles"], d["partidos"]))
    dia_partidos = max(por_dia.values(), key=lambda d: (d["partidos"], d["goles"]))
    jk, jv = max(jornadas.items(), key=lambda kv: (kv[1]["goles"], -kv[1]["partidos"]))
    fases = {f["id"]: f.get("nombre") for f in db["fases"].find({}, {"id": 1, "nombre": 1})}
    sin_goles = [d for d in por_dia.values() if d["goles"] == 0]
    records = {
        "dia_goles": {**{k: dia_goles[k] for k in ("fecha", "goles", "partidos")}, "fecha_txt": fecha_corta(dia_goles["fecha"])},
        "dia_partidos": {**{k: dia_partidos[k] for k in ("fecha", "goles", "partidos")}, "fecha_txt": fecha_corta(dia_partidos["fecha"])},
        "jornada": {"texto": f"{jk[2] or 'Jornada'} · {fases.get(jk[0], '')} {SIGLA_CONF.get(jk[1], '')}".strip(), **jv},
        "racha": {"dias": mejor, "desde_txt": fecha_corta((fin_racha - timedelta(days=mejor - 1)).isoformat()), "hasta_txt": fecha_corta(fin_racha.isoformat())},
        "sin_goles": len(sin_goles),
        "primero": {**_partido(juegos[0]), "fecha_txt": fecha_corta(juegos[0]["fecha"])},
        "ultimo": {**_partido(juegos[-1]), "fecha_txt": fecha_corta(juegos[-1]["fecha"])},
        "dias_con_partidos": len(por_dia), "dias_totales": (fin - inicio).days + 1,
    }
    return {
        "meses": meses, "max_goles_dia": max_goles,
        "por_mes": [{"mes": f"{MESES[m - 1][:3]} {a}", **v, "gpp": _gpp(v)} for (a, m), v in sorted(por_mes.items())],
        "por_dow": [{"dia": DIAS[d], **por_dow[d], "gpp": _gpp(por_dow[d])} for d in range(7)],
        "por_hora": [{"hora": h, **v, "gpp": _gpp(v)} for h, v in sorted(por_hora.items())],
        "records": records,
        "dias": {k: {"fecha_txt": fecha_corta(k), "goles": v["goles"], "partidos": v["lista"]} for k, v in por_dia.items()},
    }


# --- Efemérides ----------------------------------------------------------------------------------------------------
def _efemerides(juegos: List[dict]) -> List[dict]:
    efe: List[dict] = []

    def add(fecha, tipo, icono, peso, titulo, texto, **extra):
        efe.append({"fecha": fecha, "fecha_txt": fecha_corta(fecha), "tipo": tipo, "icono": icono, "peso": peso,
                    "destacada": peso >= DESTACADA, "titulo": titulo, "texto": texto, **extra})

    total_goles, hitos = 0, list(HITOS_GOL)
    mayor_goleada = max(juegos, key=lambda j: abs((j.get("resultado") or {}).get("goles_local", 0) - (j.get("resultado") or {}).get("goles_visitante", 0)), default=None)
    mas_goles = max(juegos, key=lambda j: (j.get("resultado") or {}).get("goles_local", 0) + (j.get("resultado") or {}).get("goles_visitante", 0), default=None)
    arranques_conf, arranques_fase = set(), set()
    fases = {f["id"]: f.get("nombre") for f in db["fases"].find({}, {"id": 1, "nombre": 1})}
    ultimo_por_pais: Dict[int, dict] = {}
    for j in juegos:
        p = _partido(j)
        r = j.get("resultado") or {}
        marcador = f"{p['local']} {p['gl']}-{p['gv']} {p['visita']}"
        # partidos memorables (historia principal de la crónica)
        historia = (r.get("cronica") or {}).get("historia")
        if historia in HISTORIAS:
            peso, icono, etiqueta = HISTORIAS[historia]
            add(j["fecha"], "partido", icono, peso, etiqueta, (r.get("cronica") or {}).get("titular") or marcador, juego_id=p["id"],
                marcador=marcador, local_id=p["local_id"], visita_id=p["visita_id"])
        # hitos de goles
        goles = _goles_validos(r.get("eventos") or [])
        for k, ev in enumerate(goles, start=1):
            n = total_goles + k
            if hitos and n == hitos[0]:
                hitos.pop(0)
                autor = (ev.get("jugadores") or ["?"])[0]
                minuto = f"{ev.get('minuto', '')}" + (f"+{ev['adicional']}" if ev.get("adicional") else "")
                add(j["fecha"], "gol", "bi-dribbble", 92 if n in (1, 1000) else 84, f"Gol número {n:,}".replace(",", "."),
                    f"{autor} ({ev.get('equipo')}) a los {minuto}' en {marcador}" if n > 1 else f"{autor} ({ev.get('equipo')}) abrió el marcador del Mundial a los {minuto}' en {marcador}",
                    juego_id=p["id"], marcador=marcador)
        total_goles += len(goles) if goles else (p["gl"] + p["gv"])
        # arranques
        if j.get("confederacion_id") not in arranques_conf:
            arranques_conf.add(j.get("confederacion_id"))
            add(j["fecha"], "record", "bi-flag-fill", 64, f"Arranca {SIGLA_CONF.get(j.get('confederacion_id'), 'la eliminatoria')}",
                f"Primer partido: {marcador}", juego_id=p["id"], marcador=marcador)
        fk = (j.get("confederacion_id"), j.get("fase_id"))
        if fk not in arranques_fase and j.get("fase_id") not in (None, 1):
            arranques_fase.add(fk)
            add(j["fecha"], "record", "bi-signpost-2-fill", 66, f"Comienza la {fases.get(j.get('fase_id'), 'nueva fase')}",
                f"{SIGLA_CONF.get(j.get('confederacion_id'), '')}: {marcador}", juego_id=p["id"], marcador=marcador)
        # DT expulsados
        for ev in r.get("eventos") or []:
            if ev.get("tipo") == "🟥 DT EXPULSADO":
                add(j["fecha"], "dt", "bi-person-x-fill", 74, "DT expulsado", f"{ev.get('dt')} ({ev.get('equipo')}) se fue a la tribuna en {marcador}",
                    juego_id=p["id"], dt_id=ev.get("dt_id"), marcador=marcador)
        for pid in (p["local_id"], p["visita_id"]):
            ultimo_por_pais[pid] = {**p, "marcador": marcador}
    for j, titulo, peso in ((mayor_goleada, "La mayor goleada del Mundial", 88), (mas_goles, "El partido con más goles", 86)):
        if j:
            p = _partido(j)
            marcador = f"{p['local']} {p['gl']}-{p['gv']} {p['visita']}"
            add(j["fecha"], "record", "bi-trophy-fill", peso, titulo, marcador, juego_id=p["id"], marcador=marcador)

    # ceses de técnicos
    nombres = {t["id"]: t["nombre"] for t in db["directores_tecnicos"].find({}, {"id": 1, "nombre": 1})}
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "estado": 1, "federacion": 1})}
    # los reemplazos en UNA consulta (antes una por cese: ~40 viajes a la base por cada armado)
    reemplazos = {(r["pais_id"], r.get("desde_juego")): r for r in db["dt_cargos"].find(
        {"motivo_inicio": "REEMPLAZO"}, {"pais_id": 1, "desde_juego": 1, "dt_id": 1, "regreso": 1})}
    for c in db["dt_cargos"].find({"motivo_fin": "CESE", "hasta_fecha_juego": {"$ne": None}}, {"juegos": 0}):
        nuevo = reemplazos.get((c["pais_id"], c.get("hasta_juego")))
        pais = paises.get(c["pais_id"], {}).get("nombre", "")
        texto = f"{nombres.get(c['dt_id'], '?')} deja el banco de {pais} ({c.get('ganados', 0)}-{c.get('empatados', 0)}-{c.get('perdidos', 0)})"
        if nuevo:
            texto += f"; {'vuelve' if nuevo.get('regreso') else 'asume'} {nombres.get(nuevo['dt_id'], '?')}"
        add(c["hasta_fecha_juego"], "dt", "bi-clipboard-x", 62 if c.get("cese_por_eliminacion") else 70,
            "Cese tras la eliminación" if c.get("cese_por_eliminacion") else "Cese del DT", texto, juego_id=c.get("hasta_juego"),
            dt_id=c["dt_id"], pais_id=c["pais_id"])

    # eliminaciones: el último partido de cada selección eliminada
    for pid, p in paises.items():
        if str(p.get("estado", "")).startswith("ELIMINADO") and pid in ultimo_por_pais:
            u = ultimo_por_pais[pid]
            add(u["fecha"], "eliminacion", "bi-x-octagon-fill", 58, f"{p['nombre']} queda eliminado", f"Su último partido: {u['marcador']}",
                juego_id=u["id"], pais_id=pid)

    efe.sort(key=lambda e: (e["fecha"], -e["peso"]), reverse=True)
    return efe


# --- Un día como hoy ---------------------------------------------------------------------------------------------------
def un_dia_como_hoy(datos: Optional[dict] = None, limite: int = 3) -> Optional[dict]:
    datos = datos or obtener_calendario()
    if not datos or not datos.get("hoy"):
        return None
    hoy = _fecha(datos["hoy"])
    efe = datos["efemerides"]
    anteriores = [e for e in efe if _fecha(e["fecha"]) and _fecha(e["fecha"]).year < hoy.year]
    mismo = [e for e in anteriores if (_fecha(e["fecha"]).month, _fecha(e["fecha"]).day) == (hoy.month, hoy.day)]
    modo = "mismo_dia"
    if not mismo:
        try:
            ref = hoy.replace(year=hoy.year - 1)
        except ValueError:
            ref = hoy - timedelta(days=365)
        mismo = [e for e in anteriores if abs((_fecha(e["fecha"]) - ref).days) <= 3]
        modo = "semana"
    if not mismo:
        mismo = [e for e in efe if 0 <= (hoy - _fecha(e["fecha"])).days <= 30]
        modo = "reciente"
    items = sorted(mismo, key=lambda e: -e["peso"])[:limite]
    return {"hoy": datos["hoy"], "hoy_txt": fecha_corta(datos["hoy"]), "dia": hoy.day, "mes": MESES[hoy.month - 1], "anio": hoy.year,
            "dia_semana": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][hoy.weekday()],
            "modo": modo, "items": [{**e, "hace": _hace(hoy, _fecha(e["fecha"]))} for e in items]}


def _hace(hoy: date, f: date) -> str:
    dias = (hoy - f).days
    if dias <= 0:
        return "hoy"
    if dias == 1:
        return "ayer"
    if 360 <= dias <= 370:
        return "hace un año"
    if dias >= 30:
        meses = round(dias / 30.4)
        return f"hace {meses} {'mes' if meses == 1 else 'meses'}"
    return f"hace {dias} días"


# --- Punto de entrada ---------------------------------------------------------------------------------------------------
def obtener_calendario() -> dict:
    clave = (ES._mundial_activo_id(), db["juegos"].count_documents({**ES._filtro_finalizados()}))
    if _cache["clave"] == clave and _cache["datos"] is not None:
        return _cache["datos"]
    juegos = _juegos()
    est = _estadisticas(juegos)
    efe = _efemerides(juegos)
    conteo = Counter(e["tipo"] for e in efe)
    datos = {**est, "efemerides": efe, "tipos": [{"codigo": c, "nombre": n, "icono": i, "n": conteo.get(c, 0)} for c, n, i in TIPOS],
             "hoy": juegos[-1]["fecha"] if juegos else None, "total_partidos": len(juegos),
             "total_goles": sum((j.get("resultado") or {}).get("goles_local", 0) + (j.get("resultado") or {}).get("goles_visitante", 0) for j in juegos),
             "mundial": (db["mundiales"].find_one({"activo": True}, {"anio": 1}) or {}).get("anio")}
    datos["un_dia_como_hoy"] = un_dia_como_hoy(datos)
    _cache.update(clave=clave, datos=datos)
    return datos


_armando = threading.Lock()


def _armar_en_segundo_plano():
    if not _armando.acquire(blocking=False):
        return
    try:
        obtener_calendario()
    except Exception as e:
        print(f"[calendario] no se pudo armar: {e}")
    finally:
        _armando.release()


def un_dia_como_hoy_inicio() -> Optional[dict]:
    """Para la tarjeta del inicio: nunca espera (armar el calendario en frío lleva varios segundos). Usa lo último armado
    aunque esté un partido atrasado y lo refresca en un hilo; si todavía no hay nada, no muestra la tarjeta esta vez."""
    clave = (ES._mundial_activo_id(), db["juegos"].count_documents({**ES._filtro_finalizados()}))
    if _cache["clave"] != clave:
        threading.Thread(target=_armar_en_segundo_plano, daemon=True).start()
    return (_cache["datos"] or {}).get("un_dia_como_hoy")
