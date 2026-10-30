"""
Árbitros: directorio por puesto (/arbitros/) y perfil (/arbitros/perfil?nombre=...).

Los partidos guardan el NOMBRE de cada árbitro por rol (resultado.arbitros.{central, linea1, linea2, cuarto, var}) y cada
evento arbitral dice quién actuó ('arbitro', 'arbitro_rol', ver services/arbitraje.py; los partidos viejos se ajustaron
con asignar_arbitros_partidos.py). Qué se cuenta de cada puesto:
  - central: faltas y tarjetas del partido (mismo criterio que estadisticas_service._contar_faltas_tarjetas), expulsiones,
    penales cobrados, resultados y su rigor (arbitros.rigor);
  - jueces de línea: fueras de lugar, córners y saques de banda que señalaron;
  - 4to árbitro: cambios anunciados, revisiones del VAR que pidió y minutos de descuento que marcó;
  - VAR: revisiones, cuántas dio por buenas (confirma) y cuántas por malas (revierte), goles anulados.
Todo sale de una sola consulta con proyección, cacheada por cantidad de partidos jugados.
"""
import certifi
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from pymongo import DESCENDING
from pymongo.mongo_client import MongoClient

from config.settings import MONGODB_URI
from services import arbitraje
from services.estadisticas_service import _contar_faltas_tarjetas

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

ROLES = [("central", "Central"), ("linea1", "Línea 1"), ("linea2", "Línea 2"), ("cuarto", "4to árbitro"), ("var", "VAR")]
NOMBRE_ROL = dict(ROLES)
ROL_POR_PUESTO = {puesto: rol for rol, puesto in arbitraje.PUESTOS.items()}
TIPOS_CORNER = {"🚩 SAQUE DE ESQUINA", "🖐️ DESVÍO A CÓRNER"}
TIPO_BANDA = "↔️ SAQUE DE BANDA"

# Cómo se muestra cada puesto en el directorio: la métrica principal (barra de cada ficha), las 3 métricas de la
# ficha, los órdenes posibles y los destacados (título, color, métrica, al revés = el menor, texto)
PESTANAS = {
    "central": {"icono": "bi-person-badge-fill", "color": "#eab308",
                "principal": ("Severidad", "tarjetas_prom", "🟨/PJ"),
                "metricas": [("Faltas/PJ", "faltas_prom"), ("Rojas", "expulsiones"), ("Penales", "penales")],
                "ordenes": [("partidos", "más partidos"), ("tarjetas_prom", "más tarjetas/PJ"), ("faltas_prom", "más faltas/PJ"),
                            ("expulsiones", "más expulsiones"), ("rigor", "más estricto (rigor)")],
                "destacados": [("🟨 El más estricto", "#eab308", "tarjetas_prom", False, "{v} tarjetas por partido"),
                               ("🕊️ El más permisivo", "#14b8a6", "tarjetas_prom", True, "{v} tarjetas por partido"),
                               ("🟥 Más expulsiones", "#ef4444", "expulsiones", False, "{v} expulsiones")]},
    "linea": {"icono": "bi-flag-fill", "color": "#38bdf8",
              "principal": ("Fueras de lugar", "offsides_prom", "por partido"),
              "metricas": [("Fueras de lugar", "offsides"), ("Córners", "corners"), ("Saques de banda", "bandas")],
              "ordenes": [("partidos", "más partidos"), ("offsides", "más fueras de lugar"), ("offsides_prom", "más fueras de lugar/PJ"),
                          ("corners", "más córners"), ("bandas", "más saques de banda")],
              "destacados": [("🚩 Bandera rápida", "#38bdf8", "offsides", False, "{v} fueras de lugar"),
                             ("📐 Más córners señalados", "#a855f7", "corners", False, "{v} córners"),
                             ("↔️ Más saques de banda", "#22c55e", "bandas", False, "{v} saques de banda")]},
    "cuarto": {"icono": "bi-stopwatch-fill", "color": "#a855f7",
               "principal": ("Cambios anunciados", "cambios_prom", "por partido"),
               "metricas": [("Cambios", "cambios"), ("Revisiones", "revisiones_pedidas"), ("Añadido/tiempo", "anadido_prom")],
               "ordenes": [("partidos", "más partidos"), ("cambios", "más cambios"), ("revisiones_pedidas", "más revisiones pedidas"),
                           ("anadido_prom", "más tiempo añadido")],
               "destacados": [("🖥️ Más revisiones pedidas", "#a855f7", "revisiones_pedidas", False, "{v} revisiones al VAR"),
                              ("🔄 Más cambios anunciados", "#22c55e", "cambios", False, "{v} cambios"),
                              ("⏱️ El más generoso con el descuento", "#f97316", "anadido_prom", False, "{v} min por tiempo")]},
    "var": {"icono": "bi-display-fill", "color": "#22d3ee",
            "principal": ("Revisiones", "revisiones", ""),
            "metricas": [("Revisiones", "revisiones"), ("Confirmó", "confirmadas"), ("Revirtió", "revertidas")],
            "ordenes": [("partidos", "más partidos"), ("revisiones", "más revisiones"), ("revertidas", "más decisiones revertidas"),
                        ("goles_anulados", "más goles anulados"), ("intervencion", "más intervencionista (perfil)"), ("severidad", "más implacable (perfil)")],
            "destacados": [("🖥️ El más consultado", "#22d3ee", "revisiones", False, "{v} revisiones"),
                           ("❌ Más goles anulados", "#ef4444", "goles_anulados", False, "{v} goles anulados"),
                           ("✅ Más jugadas confirmadas", "#22c55e", "confirmadas", False, "{v} confirmadas")]},
}
GRUPO_DE_ROL = {"central": "central", "linea1": "linea", "linea2": "linea", "cuarto": "cuarto", "var": "var"}
PROYECCION_EVENTOS = {"resultado.arbitros": 1, "resultado.ganador_lado": 1, "resultado.eventos.tipo": 1, "resultado.eventos.arbitro": 1,
                      "resultado.eventos.arbitro_rol": 1, "resultado.eventos.var_decision": 1, "resultado.eventos.var_pedido_por": 1,
                      "resultado.eventos.minutos_anadidos": 1}

_cache: Dict[str, Any] = {"clave": None, "stats": None}


def _datos_arbitros() -> List[dict]:
    return list(db["arbitros"].find({}, {"_id": 0, "nombre": 1, "pais": 1, "pais_id": 1, "puesto": 1, "rigor": 1, "rigor_etiqueta": 1,
                                         "var_intervencion": 1, "var_severidad": 1, "var_intervencion_etiqueta": 1, "var_severidad_etiqueta": 1}))


def _acciones_del_partido(res: dict) -> Dict[tuple, Counter]:
    """Lo que hizo cada árbitro (por nombre y rol) en un partido."""
    arbitros = res.get("arbitros") if isinstance(res.get("arbitros"), dict) else {}
    eventos = res.get("eventos") or []
    acciones: Dict[tuple, Counter] = defaultdict(Counter)
    for rol, nombre in arbitros.items():
        if isinstance(nombre, str) and nombre:
            acciones[(nombre, rol)]["partidos"] = 1
    central = arbitros.get("central")
    if central:
        faltas, tarjetas, expulsiones = _contar_faltas_tarjetas(eventos)
        c = acciones[(central, "central")]
        c.update(faltas=faltas, tarjetas=tarjetas, expulsiones=expulsiones)
        c[{"L": "gana_local", "V": "gana_visitante"}.get(res.get("ganador_lado"), "empates")] += 1
    for e in eventos:
        tipo, rol, nombre = e.get("tipo"), e.get("arbitro_rol"), e.get("arbitro")
        if tipo == "🎯 PENAL" and central:
            acciones[(central, "central")]["penales"] += 1
        if e.get("var_pedido_por"):     # partidos viejos: la revisión la pidió el 4to (no hay evento propio)
            acciones[(e["var_pedido_por"], "cuarto")]["revisiones_pedidas"] += 1
        if not nombre:
            continue
        if rol in ("linea1", "linea2"):
            if tipo == "🚩 FUERA DE LUGAR":
                acciones[(nombre, rol)]["offsides"] += 1
            elif tipo in TIPOS_CORNER:
                acciones[(nombre, rol)]["corners"] += 1
            elif tipo == TIPO_BANDA:
                acciones[(nombre, rol)]["bandas"] += 1
        elif rol == "cuarto":
            if tipo == "🔄 SUSTITUCIÓN":
                acciones[(nombre, rol)]["cambios"] += 1
            elif tipo == "🖥️ REVISIÓN VAR":
                acciones[(nombre, rol)]["revisiones_pedidas"] += 1
            elif tipo == "⏱️ TIEMPO AÑADIDO":
                acciones[(nombre, rol)]["anadido_min"] += int(e.get("minutos_anadidos") or 0)
                acciones[(nombre, rol)]["carteles"] += 1
        elif rol == "var" and tipo in arbitraje.TIPOS_DECISION_VAR:
            c = acciones[(nombre, rol)]
            c["revisiones"] += 1
            c["confirmadas" if e.get("var_decision") == "confirma" else "revertidas"] += 1
            if tipo == "🖥️ VAR - GOL ANULADO":
                c["goles_anulados"] += 1
    return acciones


def _estadisticas() -> Dict[tuple, Counter]:
    clave = db["juegos"].count_documents({"estado": "finalizado"})
    if _cache["clave"] == clave and _cache["stats"] is not None:
        return _cache["stats"]
    stats: Dict[tuple, Counter] = defaultdict(Counter)
    for j in db["juegos"].find({"estado": "finalizado", "resultado.arbitros": {"$type": "object"}}, PROYECCION_EVENTOS):
        for k, c in _acciones_del_partido(j.get("resultado") or {}).items():
            stats[k].update(c)
    _cache.update(clave=clave, stats=stats)
    return stats


def _fila(a: dict, rol: str, c: Counter) -> dict:
    n = c.get("partidos", 0)
    prom = lambda v: round(v / n, 1) if n else 0
    fila = {"nombre": a["nombre"], "pais": a.get("pais", ""), "pais_id": a.get("pais_id"), "puesto": a.get("puesto", ""),
            "rol": rol, "rol_nombre": NOMBRE_ROL[rol], "partidos": n}
    if rol == "central":
        fila.update(faltas=c["faltas"], tarjetas=c["tarjetas"], expulsiones=c["expulsiones"], penales=c["penales"],
                    faltas_prom=prom(c["faltas"]), tarjetas_prom=prom(c["tarjetas"]),
                    gana_local=c["gana_local"], empates=c["empates"], gana_visitante=c["gana_visitante"],
                    pct_gana_local=round(100 * c["gana_local"] / n) if n else 0,
                    pct_empate=round(100 * c["empates"] / n) if n else 0,
                    pct_gana_visitante=round(100 * c["gana_visitante"] / n) if n else 0,
                    rigor=a.get("rigor") or 0, rigor_etiqueta=a.get("rigor_etiqueta") or arbitraje.etiqueta_rigor(a.get("rigor")))
    elif rol in ("linea1", "linea2"):
        fila.update(offsides=c["offsides"], corners=c["corners"], offsides_prom=prom(c["offsides"]), corners_prom=prom(c["corners"]),
                    bandas=c["bandas"], bandas_prom=prom(c["bandas"]))
    elif rol == "cuarto":
        fila.update(cambios=c["cambios"], revisiones_pedidas=c["revisiones_pedidas"], cambios_prom=prom(c["cambios"]),
                    carteles=c["carteles"], anadido_min=c["anadido_min"],
                    anadido_prom=round(c["anadido_min"] / c["carteles"], 1) if c["carteles"] else 0)
    else:
        fila.update(revisiones=c["revisiones"], confirmadas=c["confirmadas"], revertidas=c["revertidas"],
                    goles_anulados=c["goles_anulados"], revisiones_prom=prom(c["revisiones"]),
                    # personalidad (asignar_perfil_var.py): cuánto revisa y cuánto da por malo
                    intervencion=a.get("var_intervencion") or 0, severidad=a.get("var_severidad") or 0,
                    intervencion_etiqueta=a.get("var_intervencion_etiqueta") or "", severidad_etiqueta=a.get("var_severidad_etiqueta") or "",
                    pct_revertidas=round(100 * c["revertidas"] / c["revisiones"]) if c["revisiones"] else 0)
    return fila


def listar_por_puesto() -> List[dict]:
    """Las 5 pestañas del directorio: todos los árbitros de cada puesto (hayan trabajado o no) con sus números."""
    stats = _estadisticas()
    por_rol = defaultdict(list)
    vistos = set()   # hay nombres repetidos dentro de un puesto: los partidos guardan solo el nombre, cuentan para el primero
    for a in _datos_arbitros():
        rol = ROL_POR_PUESTO.get(a.get("puesto"))
        if rol:
            clave = (a["nombre"], rol)
            por_rol[rol].append(_fila(a, rol, Counter() if clave in vistos else stats.get(clave, Counter())))
            vistos.add(clave)
    pestanas = []
    for rol, nombre in ROLES:
        cfg = PESTANAS[GRUPO_DE_ROL[rol]]
        filas = sorted(por_rol[rol], key=lambda f: (-f["partidos"], f["nombre"]))
        activos = [f for f in filas if f["partidos"]]
        con_rodaje = [f for f in activos if f["partidos"] >= 2] or activos
        clave_principal = cfg["principal"][1]
        destacados = []
        for titulo, color, clave, al_reves, detalle in cfg["destacados"]:
            base = con_rodaje if (clave.endswith("_prom") or clave.startswith("pct")) else activos
            if not base:
                continue
            elegido = (min if al_reves else max)(base, key=lambda f: (f.get(clave) or 0, f["partidos"] * (-1 if al_reves else 1)))
            if elegido.get(clave) or al_reves:
                destacados.append({"titulo": titulo, "color": color, "fila": elegido, "detalle": detalle.format(v=elegido.get(clave))})
        pestanas.append({
            "codigo": rol, "nombre": nombre, "icono": cfg["icono"], "color": cfg["color"], "filas": filas,
            "activos": len(activos), "partidos": sum(f["partidos"] for f in filas), "destacados": destacados,
            "principal": {"etiqueta": cfg["principal"][0], "clave": clave_principal, "unidad": cfg["principal"][2],
                          "max": max([f.get(clave_principal) or 0 for f in activos] + [1])},
            "metricas": cfg["metricas"], "ordenes": cfg["ordenes"],
        })
    return pestanas


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _chips(rol: str, c: Counter) -> List[str]:
    """Lo que hizo en UN partido, para la bitácora del perfil."""
    if rol == "central":
        chips = [f"🛑 {c['faltas']}", f"🟨 {c['tarjetas']}"] + ([f"🟥 {c['expulsiones']}"] if c["expulsiones"] else [])
        return chips + ([f"🎯 {_plural(c['penales'], 'penal', 'penales')}"] if c["penales"] else [])
    if rol in ("linea1", "linea2"):
        chips = [f"🚩 {_plural(c['offsides'], 'fuera de lugar', 'fueras de lugar')}"]
        chips += [f"📐 {_plural(c['corners'], 'córner', 'córners')}"] if c["corners"] else []
        return chips + ([f"↔️ {_plural(c['bandas'], 'saque de banda', 'saques de banda')}"] if c["bandas"] else [])
    if rol == "cuarto":
        chips = [f"🔄 {_plural(c['cambios'], 'cambio', 'cambios')}"]
        if c["revisiones_pedidas"]:
            chips.append(f"🖥️ pidió {_plural(c['revisiones_pedidas'], 'revisión', 'revisiones')}")
        if c["carteles"]:
            chips.append(f"⏱️ +{c['anadido_min']} min")
        return chips
    if not c["revisiones"]:
        return ["🖥️ sin revisiones"]
    chips = [f"🖥️ {_plural(c['revisiones'], 'revisión', 'revisiones')}"]
    if c["confirmadas"]:
        chips.append(f"✅ {_plural(c['confirmadas'], 'confirmada', 'confirmadas')}")
    if c["revertidas"]:
        chips.append(f"❌ {_plural(c['revertidas'], 'revertida', 'revertidas')}")
    return chips


def perfil_arbitro(nombre: str) -> Optional[Dict[str, Any]]:
    """Ficha del árbitro: su puesto, sus números en ese puesto y la bitácora de partidos con lo que hizo en cada uno."""
    candidatos = [a for a in _datos_arbitros() if a["nombre"] == nombre]
    if not candidatos:
        return None
    info = candidatos[0]
    rol_principal = ROL_POR_PUESTO.get(info.get("puesto")) or "central"
    roles_posibles = [ROL_POR_PUESTO[a["puesto"]] for a in candidatos if a.get("puesto") in ROL_POR_PUESTO] or [rol_principal]
    juegos = list(db["juegos"].find(
        {"estado": "finalizado", "$or": [{f"resultado.arbitros.{rol}": nombre} for rol in roles_posibles]},
        {"equipo_local": 1, "equipo_visitante": 1, "fecha": 1, "fase_id": 1, "resultado.goles_local": 1,
         "resultado.goles_visitante": 1, **PROYECCION_EVENTOS}).sort([("fecha", DESCENDING)]))
    nombres_fase = {f["id"]: f.get("nombre", "") for f in db["fases"].find({}, {"id": 1, "nombre": 1})}
    por_rol = Counter()
    partidos = []
    for j in juegos:
        res = j.get("resultado") or {}
        arbitros = res.get("arbitros") or {}
        rol = next((r for r in roles_posibles if arbitros.get(r) == nombre), rol_principal)
        por_rol[rol] += 1
        hizo = _acciones_del_partido(res).get((nombre, rol), Counter())
        local, visitante = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
        partidos.append({
            "id": str(j["_id"]), "fecha": j.get("fecha"), "fase": nombres_fase.get(j.get("fase_id"), ""),
            "rol": NOMBRE_ROL[rol], "es_principal": rol == rol_principal, "chips": _chips(rol, hizo),
            "local": {"id": local.get("id"), "nombre": local.get("nombre"), "bandera": local.get("bandera") or "", "goles": res.get("goles_local", 0)},
            "visitante": {"id": visitante.get("id"), "nombre": visitante.get("nombre"), "bandera": visitante.get("bandera") or "", "goles": res.get("goles_visitante", 0)},
        })
    fila = _fila(info, rol_principal, _estadisticas().get((nombre, rol_principal), Counter()))
    return {
        "nombre": nombre, "pais": info.get("pais", ""), "pais_id": info.get("pais_id"), "puesto": info.get("puesto", ""),
        "rol": rol_principal, "rol_nombre": NOMBRE_ROL[rol_principal], "total_partidos": len(juegos),
        "por_rol": [{"rol": etiqueta, "partidos": por_rol[r]} for r, etiqueta in ROLES],
        "numeros": fila, "central": fila if rol_principal == "central" else {}, "partidos": partidos,
    }


def comparar_con_colegas(perfil: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cómo se compara con los colegas de su MISMO puesto que ya trabajaron: promedio del puesto en la métrica principal y
    qué porcentaje de ellos tiene un número menor (para el central, también en faltas por partido).
    """
    rol = perfil.get("rol")
    pestana = next((p for p in listar_por_puesto() if p["codigo"] == rol), None)
    yo = perfil.get("numeros") or {}
    if not pestana or not yo.get("partidos"):
        return {}
    colegas = [f for f in pestana["filas"] if f["partidos"]]
    n = len(colegas)
    clave = pestana["principal"]["clave"]
    pct = lambda k: round(100 * sum(1 for f in colegas if (f.get(k) or 0) < (yo.get(k) or 0)) / n)
    resultado = {
        "metrica": pestana["principal"]["etiqueta"], "unidad": pestana["principal"]["unidad"], "valor": yo.get(clave),
        "liga": round(sum(f.get(clave) or 0 for f in colegas) / n, 1), "pct": pct(clave),
        "ranking_partidos": 1 + sum(1 for f in colegas if f["partidos"] > yo["partidos"]), "total_colegas": n,
    }
    if rol == "central":
        resultado.update(liga_tarjetas=resultado["liga"], pct_mas_estricto=resultado["pct"],
                         liga_faltas=round(sum(f["faltas_prom"] for f in colegas) / n, 1), pct_mas_faltas=pct("faltas_prom"))
    elif rol in ("linea1", "linea2"):
        resultado.update(liga_bandas=round(sum(f["bandas_prom"] for f in colegas) / n, 1), pct_bandas=pct("bandas_prom"))
    return resultado
