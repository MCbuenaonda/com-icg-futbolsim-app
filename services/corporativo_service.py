"""
Corporativos Deportivos — datos para las vistas (/corporativo y /corporativo/{sigla}). Cada vista primero pone
al día el universo del usuario (corporativo_universo_service.poner_al_dia).
"""
from datetime import datetime
from typing import Optional

from bson import ObjectId

from config import corporativos as C
from services import corporativo_reglas as R
from services import corporativo_fichajes_service as F
from services import corporativo_universo_service as U
from services.corporativo_mercado_service import afines, valores
from services.imagenes_pais_service import url_logo_corporativo

ESTADOS_CARRERA = {
    "BUSCANDO": {"titulo": "En búsqueda de empleo", "icono": "bi-search", "color": "info"},
    "EN_CARGO": {"titulo": "En funciones", "icono": "bi-briefcase-fill", "color": "success"},
    "PAUSA": {"titulo": "Carrera en pausa", "icono": "bi-pause-circle-fill", "color": "warning"},
    "PREAVISO": {"titulo": "En preaviso", "icono": "bi-box-arrow-right", "color": "warning"},
}


CONF_SIGLA = {1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC"}
CONF_COLOR = {1: "#3b82f6", 2: "#22c55e", 3: "#ef4444", 4: "#f59e0b", 5: "#06b6d4", 6: "#a855f7"}
CICLOS_CALENDARIO = 6


# --- Cuándo juega cada representado y qué conviene hacer con él ----------------------------------
def _contexto_partidos() -> dict:
    """Lo que necesitan las vistas para ubicar cada representado en el calendario (una carga por request)."""
    from services.corporativo_acciones_service import forma_selecciones
    from services.corporativo_mercado_service import calendario_paises
    eliminadas = {d["id"] for d in U.db["internacional"].find({"estado": {"$regex": "^ELIMINADO"}}, {"id": 1})}
    vivas = {d["id"] for d in U.db["internacional"].find({}, {"id": 1})} - eliminadas
    try:
        from services import estadisticas_service as E
        agregado, paises_ag = E._cache_vista.get("agregado") or {}, E._cache_vista.get("paises") or {}
    except Exception:
        agregado, paises_ag = {}, {}
    return {"cal": calendario_paises(), "forma": forma_selecciones(), "eliminadas": eliminadas, "vivas": vivas,
            "ciclo": U.estado_reloj()["ciclo"], "seq": U.seq_actual(), "agregado": agregado, "paises_ag": paises_ag}


def juego_de(tipo: str, ref_id: int, ctx: dict) -> dict:
    """{"estado": programado|eliminada|sin_partido, "faltan", "ciclo", "en_ciclos", "rival", "rival_bandera", "pais_id"}."""
    v = valores()
    pais = ref_id if tipo == "seleccion" else v["info_jugadores"].get(ref_id, {}).get("pais_id")
    d = ctx["cal"].get(pais)
    if d:
        rival = v["info_paises"].get(d["rival_id"], {})
        return {"estado": "programado", "pais_id": pais, "faltan": d["faltan"], "ciclo": d["ciclo"], "juego_id": d.get("juego_id"),
                "en_ciclos": max(0, d["ciclo"] - ctx["ciclo"]), "rival": rival.get("nombre"), "rival_bandera": rival.get("bandera"),
                "rival_id": d["rival_id"], "local": d["local"], "partidos_2": len([i for i in d["posiciones"] if i < 2 * C.PARTIDOS_POR_CICLO])}
    if pais in ctx["eliminadas"] or pais not in ctx["vivas"]:
        return {"estado": "eliminada", "pais_id": pais, "partidos_2": 0}
    return {"estado": "sin_partido", "pais_id": pais, "partidos_2": 0}


def _titular(jugador_id: int, pais_id, ctx: dict) -> Optional[float]:
    a = ctx["agregado"].get(jugador_id)
    p = ctx["paises_ag"].get(pais_id) or {}
    pj = p.get("pj")
    if not a or not pj:
        return None
    return min(1.0, (a["metricas"].get("partidos") or 0) / pj)


def senal_de(tipo: str, ref_id: int, valor: int, juego: dict, ctx: dict, contrato: Optional[dict] = None, ciclo: int = 0) -> dict:
    """Señal de comprar (mercado) o vender (cartera) con su '¿por qué?' (corporativo_reglas.senales)."""
    from services.corporativo_ciclo_service import popularidad
    datos = {"tipo": tipo, "valor": valor, "popularidad": popularidad(tipo, ref_id, valor), "partidos_2_ciclos": juego.get("partidos_2", 0),
             "sin_partido": juego["estado"] == "sin_partido", "eliminada": juego["estado"] == "eliminada",
             "forma": ctx["forma"].get(juego.get("pais_id")),
             "titular": _titular(ref_id, juego.get("pais_id"), ctx) if tipo == "jugador" else None}
    if contrato:
        datos.update(prima=contrato.get("prima", 0), satisfaccion=contrato.get("satisfaccion"), ciclos_sin_jugar=contrato.get("ciclos_sin_jugar", 0),
                     renta_total=contrato.get("renta_total", 0),
                     costos_total=contrato.get("honorarios_total", 0) + contrato.get("prima", 0),
                     valor_firma=contrato.get("valor_firma"), ciclos_restantes=contrato["hasta_ciclo"] - ciclo + 1)
        # partidos programados de su selección antes de que venza el contrato (y antes de su último ciclo)
        ciclos_partidos = [R.ciclo_de_seq(ctx["seq"] + i + 1) for i in (ctx["cal"].get(juego.get("pais_id")) or {}).get("posiciones", [])] \
            if "seq" in ctx else []
        datos.update(partidos_antes_vencer=sum(1 for k in ciclos_partidos if k <= contrato["hasta_ciclo"]),
                     partidos_antes_ultimo=sum(1 for k in ciclos_partidos if k < contrato["hasta_ciclo"]))
    return R.senales(datos)


def _giras_vista(A, user_id, sigla: str, universo: dict) -> list:
    """Giras recientes agrupadas (una gira grupal = una fila), con su avance partido a partido."""
    seq = universo.get("cursor_seq") or U.seq_actual()
    grupos: dict = {}
    for g in A.giras_de(user_id, sigla):
        k = g.get("grupo_id") or g["_id"]
        f = grupos.setdefault(k, {"nombres": [], "costo": 0, "ingreso": 0, "cobrado": 0, "aficionados": 0, "estado": g["estado"],
                                  "ciclo": g["ciclo"], "cobra_ciclo": g.get("cobra_ciclo"), "partidos": g.get("partidos"),
                                  "desde_seq": g.get("desde_seq"), "hasta_seq": g.get("hasta_seq"), "v2": g.get("desde_seq") is not None})
        f["nombres"].append(A._nombre(g["tipo"], g["ref_id"]))
        f["costo"] += g.get("costo") or 0
        f["ingreso"] += g.get("ingreso") or 0
        f["cobrado"] += g.get("cobrado") or (g.get("ingreso") or 0 if g["estado"] == "COBRADA" else 0)
        f["aficionados"] += g.get("aficionados") or 0
    salida = []
    for f in list(grupos.values())[:6]:
        f["ref_nombre"] = ", ".join(f["nombres"])
        if f["v2"]:
            f["jugados"] = max(0, min(f["partidos"], seq - f["desde_seq"] + 1))
        salida.append(f)
    return salida


def sugerencias_huecos(cal: dict, ctx: dict, user_id, capital: float) -> list:
    """
    Para los ciclos del calendario en que tu cartera no juega (o casi no juega), hasta CAL_SUGERENCIAS_POR_HUECO
    representados LIBRES en tu universo que sí juegan en ese ciclo: selecciones y sus jugadores titulares (sin leyendas),
    ordenados por renta esperada en ese ciclo contra su prima de referencia, y solo si la prima entra en la mitad del capital.
    -> [{"ciclo", "partidos_cartera", "vacio", "sugerencias": [{tipo, ref_id, nombre, pais_id, bandera, partidos, prima, renta, url}]}]
    """
    from services.corporativo_ciclo_service import popularidad
    v = valores()
    ciclo0 = ctx["ciclo"]
    totales = [sum(f["celdas"][k] for f in cal["filas"]) for k in range(len(cal["ciclos"]))]
    huecos = [k for k, n in enumerate(totales) if n <= C.CAL_ACTIVIDAD_FLOJA][:4]
    if not huecos:
        return []
    ocupados = {(c["tipo"], c["ref_id"]) for c in U.contratos_activos(user_id)}
    # partidos de cada selección en cada ciclo del calendario
    por_ciclo: dict = {}
    for pais, d in ctx["cal"].items():
        for i in d.get("posiciones", []):
            k = R.ciclo_de_seq(ctx["seq"] + i + 1) - ciclo0
            if 0 <= k < len(cal["ciclos"]):
                por_ciclo.setdefault(k, {}).setdefault(pais, 0)
                por_ciclo[k][pais] += 1
    jugadores_por_pais: dict = {}
    for jid, info in v["info_jugadores"].items():
        if not info.get("leyenda") and ("jugador", jid) not in ocupados:
            jugadores_por_pais.setdefault(info.get("pais_id"), []).append(jid)
    tope = max(0, capital) * 0.5
    salida = []
    for k in huecos:
        candidatos = []
        for pais, n in (por_ciclo.get(k) or {}).items():
            pinfo = v["info_paises"].get(pais, {})
            if ("seleccion", pais) not in ocupados and pais not in ctx["eliminadas"]:
                valor = v["selecciones"].get(pais, 0)
                prima = R.prima_referencia(valor)
                if 0 < prima <= tope:
                    renta = R.renta_esperada_ciclo("seleccion", valor, 2 * n, popularidad("seleccion", pais, valor))
                    candidatos.append({"tipo": "seleccion", "ref_id": pais, "nombre": pinfo.get("nombre"), "pais_id": pais,
                                       "bandera": pinfo.get("bandera"), "partidos": n, "prima": prima, "renta": renta})
            mejores = sorted(jugadores_por_pais.get(pais, []), key=lambda j: -v["jugadores"].get(j, 0))[:6]
            for jid in mejores:
                titular = _titular(jid, pais, ctx)
                if titular is not None and titular < 0.5:
                    continue
                valor = v["jugadores"].get(jid, 0)
                prima = R.prima_referencia(valor)
                if 0 < prima <= tope:
                    renta = R.renta_esperada_ciclo("jugador", valor, 2 * n, popularidad("jugador", jid, valor), titular or 0.8)
                    candidatos.append({"tipo": "jugador", "ref_id": jid, "nombre": v["info_jugadores"][jid].get("nombre"), "pais_id": pais,
                                       "bandera": pinfo.get("bandera"), "partidos": n, "prima": prima, "renta": renta})
        candidatos.sort(key=lambda x: -(x["renta"] / max(x["prima"], 1)))
        elegidos = []
        sel = next((x for x in candidatos if x["tipo"] == "seleccion"), None)   # una selección si hay (juega todo el ciclo)
        if sel:
            elegidos.append(sel)
        elegidos += [x for x in candidatos if x is not sel][:C.CAL_SUGERENCIAS_POR_HUECO - len(elegidos)]
        for x in elegidos:
            x["url"] = f"/corporativo/mercado?tipo={x['tipo']}&q={x['nombre']}"
        salida.append({"ciclo": cal["ciclos"][k], "indice": k, "partidos_cartera": totales[k], "vacio": totales[k] == 0,
                       "sugerencias": elegidos})
    return salida


def calendario_cartera(contratos: list, ctx: dict) -> dict:
    """Grilla de los próximos CICLOS_CALENDARIO ciclos por selección involucrada (representada o país de un jugador
    representado) y la lista de los próximos partidos de la cartera."""
    v = valores()
    ciclo0 = ctx["ciclo"]
    filas = {}
    for c in contratos:
        pais = c["ref_id"] if c["tipo"] == "seleccion" else v["info_jugadores"].get(c["ref_id"], {}).get("pais_id")
        if pais is None:
            continue
        fila = filas.setdefault(pais, {"pais_id": pais, "nombre": v["info_paises"].get(pais, {}).get("nombre"),
                                        "bandera": v["info_paises"].get(pais, {}).get("bandera"), "seleccion": False, "jugadores": [],
                                        "celdas": [0] * CICLOS_CALENDARIO, "eliminada": pais in ctx["eliminadas"]})
        if c["tipo"] == "seleccion":
            fila["seleccion"] = True
        else:
            fila["jugadores"].append(v["info_jugadores"].get(c["ref_id"], {}).get("nombre"))
    seq = U.seq_actual()   # una sola lectura del reloj (antes se consultaba por cada partido programado)
    for pais, fila in filas.items():
        d = ctx["cal"].get(pais)
        for i in (d or {}).get("posiciones", []):
            k = R.ciclo_de_seq(seq + i + 1) - ciclo0
            if 0 <= k < CICLOS_CALENDARIO:
                fila["celdas"][k] += 1
        fila["proximo"] = juego_de("seleccion", pais, ctx)
    orden = sorted(filas.values(), key=lambda f: (f["proximo"].get("faltan", 10 ** 6), f["nombre"] or ""))
    proximos, vistos = [], set()
    for f in orden:   # un partido entre dos selecciones de la cartera aparece una sola vez
        if f["proximo"]["estado"] == "programado" and f["proximo"].get("juego_id") not in vistos:
            vistos.add(f["proximo"].get("juego_id"))
            proximos.append(f)
    proximos = proximos[:8]
    totales = [sum(f["celdas"][k] for f in orden) for k in range(CICLOS_CALENDARIO)]
    return {"ciclos": [ciclo0 + k for k in range(CICLOS_CALENDARIO)], "filas": orden, "proximos": proximos, "totales": totales,
            "flojo": C.CAL_ACTIVIDAD_FLOJA,
            "con_partido": sum(1 for f in orden if any(f["celdas"])), "total": len(orden)}


def _saneamiento_vista(corp_doc: dict) -> Optional[dict]:
    s = corp_doc.get("saneamiento") or {}
    if not s:
        return None
    progreso = s.get("progreso") or {}
    return {**s, "objetivos_vista": [{"codigo": k, "texto": C.SANEAMIENTO_OBJETIVOS[k], **(progreso.get(k) or {"ok": False, "detalle": "se evalúa al cierre del ciclo"})}
                                     for k in s.get("objetivos", [])],
            "cumplidos": sum(1 for k in s.get("objetivos", []) if (progreso.get(k) or {}).get("ok")),
            "total": len(s.get("objetivos", []))}


def _info_corp(sigla: str) -> dict:
    corp = C.CORPORATIVO_POR_SIGLA[sigla]
    return {**corp, "logo": url_logo_corporativo(sigla), "color": corp["colores"][0], "acento": corp["colores"][1],
            "capital_inicial": C.TIERS[corp["tier"]]["capital"], "fama_minima": C.TIERS[corp["tier"]]["fama_minima"]}


def catalogo_corporativos() -> list:
    """Los 10 corporativos sin universo (vista de bienvenida): datos fijos + cartera de la plantilla de siembra."""
    plantilla = {f["sigla"]: f for f in U.db["corp_plantilla_siembra"].find({})}
    salida = []
    for corp in C.CORPORATIVOS:
        fila = plantilla.get(corp["sigla"], {})
        salida.append({**_info_corp(corp["sigla"]), "n_selecciones": len(fila.get("selecciones", [])),
                       "n_jugadores": len(fila.get("jugadores", []))})
    return salida


def _resumen_corporativos(universo_id) -> list:
    contratos = U.contratos_activos(universo_id)
    v = valores()
    por_sigla = {}
    for c in contratos:
        fila = por_sigla.setdefault(c["sigla"], {"n_selecciones": 0, "n_jugadores": 0, "valor_cartera": 0})
        fila["n_selecciones" if c["tipo"] == "seleccion" else "n_jugadores"] += 1
        fila["valor_cartera"] += (v["selecciones"] if c["tipo"] == "seleccion" else v["jugadores"]).get(c["ref_id"], 0)
    salida = []
    for doc in U.db["corp_corporativos"].find({"universo_id": universo_id}):
        fila = por_sigla.get(doc["sigla"], {"n_selecciones": 0, "n_jugadores": 0, "valor_cartera": 0})
        salida.append({**_info_corp(doc["sigla"]), **fila, "capital": doc["capital"], "precio": doc["precio"],
                       "precio_inicial": doc["precio_inicial"], "es_del_usuario": doc["es_del_usuario"],
                       "confianza": doc["confianza"], "reputacion": doc["reputacion"],
                       "variacion": round((doc["precio"] / doc["precio_inicial"] - 1) * 100, 1) if doc["precio_inicial"] else 0})
    salida.sort(key=lambda c: (-C.ORDEN_TIER[c["tier"]], -c["valor_cartera"]))
    return salida


def obtener_vista_inicio(user_id) -> dict:
    universo = U.obtener_universo(user_id)
    if not universo:
        return {"universo": None, "catalogo": catalogo_corporativos(), "reloj": U.estado_reloj()}
    resumen = U.poner_al_dia(user_id)
    universo = U.obtener_universo(user_id)
    corporativos = _resumen_corporativos(user_id)
    ofertas = []
    for o in U.db["corp_ofertas_empleo"].find({"universo_id": user_id, "estado": {"$in": ["PENDIENTE", "EN_ESPERA"]}}).sort("ciclo", -1):
        ofertas.append({**o, "tipo": o.get("tipo", "EMPLEO"), "corp": _info_corp(o["sigla"]),
                        "objetivos_texto": [C.OBJETIVOS[x] for x in o["objetivos"]],
                        "ciclos_restantes": o["vence_ciclo"] - U.ciclo_en_curso(universo) + 1,
                        **BOTONES_OFERTA.get((o.get("tipo", "EMPLEO"), o["estado"]), BOTONES_OFERTA[("EMPLEO", "PENDIENTE")])})
    avisos = list(U.db["corp_avisos"].find({"universo_id": user_id}).sort("creado_en", -1).limit(12))
    cargo = universo.get("cargo")
    mi_corp = None
    if cargo:
        mi_corp = next((c for c in corporativos if c["sigla"] == cargo["sigla"]), None)
        doc = U.db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": cargo["sigla"]},
                                                  {"historial": 1, "ciclo_actual": 1, "saneamiento": 1, "marketing_hasta_ciclo": 1, "capital": 1}) or {}
        historial = doc.get("historial") or []
        ultimo = historial[-1] if historial else None
        ultimo_pago = U.db["corp_movimientos"].find_one({"universo_id": user_id, "tipo": "SUELDO_CEO"}, sort=[("ciclo", -1)])
        ciclo_ahora = U.ciclo_en_curso(universo)
        bloqueadas = [a for a in (universo.get("acciones_bloqueadas") or []) if a["consolida_ciclo"] > ciclo_ahora - 1]
        estado_obj = cargo.get("objetivos_estado") or {}
        mi_corp = {**mi_corp, "cargo": cargo, "objetivos_texto": [C.OBJETIVOS[x] for x in cargo["objetivos"]],
                   "objetivos": [{"texto": C.OBJETIVOS[x], **(estado_obj.get(x) or {"ok": None, "detalle": "se evalúa al cierre del ciclo"})}
                                 for x in cargo["objetivos"]],
                   "ultimo_pago": ultimo_pago, "acciones_bloqueadas": bloqueadas,
                   "acciones_bloqueadas_valor": sum(a["valor_al_otorgar"] for a in bloqueadas),
                   "preaviso": universo.get("preaviso") if universo["estado"] == "PREAVISO" else None,
                   "ciclos_en_cargo": U.ciclo_en_curso(universo) - cargo["desde_ciclo"],
                   "historial": historial[-20:], "ultimo_ciclo": ultimo, "ciclo_actual": doc.get("ciclo_actual") or {},
                   "honorarios_estimados": _honorarios_estimados(user_id, cargo["sigla"]),
                   "por_vencer": sum(1 for c in U.contratos_activos(user_id, cargo["sigla"])
                                     if c["hasta_ciclo"] - U.ciclo_en_curso(universo) + 1 <= C.CICLOS_AVISO_RENOVACION),
                   "movimientos": list(U.db["corp_movimientos"].find({"universo_id": user_id, "sigla": cargo["sigla"]})
                                       .sort("creado_en", -1).limit(12))}
        # Economía v2: calendario de la cartera, saneamiento, acuerdos/giras y lo que se espera cobrar
        from services import corporativo_acciones_service as A
        from services.corporativo_ciclo_service import renta_esperada
        ctx = _contexto_partidos()
        activos = U.contratos_activos(user_id, cargo["sigla"])
        nombrar = lambda d: {**d, "ref_nombre": A._nombre(d["tipo"], d["ref_id"])}
        cal = calendario_cartera(activos, ctx)
        try:
            cal["huecos"] = sugerencias_huecos(cal, ctx, user_id, doc.get("capital", 0))
        except Exception as e:
            print(f"[corporativos] sugerencias del calendario: {e}")
            cal["huecos"] = []
        mi_corp.update(calendario=cal, saneamiento=_saneamiento_vista(doc),
                       acuerdos=[nombrar(a) for a in A.acuerdos_de(user_id, cargo["sigla"]) if a["estado"] == "ACTIVO"],
                       giras=_giras_vista(A, user_id, cargo["sigla"], universo), renta_esperada=renta_esperada(activos),
                       marketing_activo=(doc.get("marketing_hasta_ciclo") or 0) >= ciclo_ahora,
                       marketing_hasta=doc.get("marketing_hasta_ciclo"))
    if mi_corp:
        mi_corp.update(_bandeja_mercado(user_id, universo, mi_corp))
    reloj = U.estado_reloj(universo)
    if not universo.get("primeras_ofertas"):
        reloj["partidos_para_ofertas"] = max(0, universo["primeras_ofertas_seq"] - reloj["seq"])
    return {
        "universo": universo, "estado": ESTADOS_CARRERA[universo["estado"]], "ofertas": ofertas, "avisos": avisos,
        "corporativos": corporativos, "mi_corporativo": mi_corp, "reloj": reloj, "puesta_al_dia": resumen,
        "pausa_restante": (universo["pausa_hasta_ciclo"] - U.ciclo_en_curso(universo) + 1) if universo.get("pausa_hasta_ciclo") else None,
        "historial": list(reversed(universo.get("historial_cargos") or [])),
        "ciclo": U.ciclo_en_curso(universo), "economia": reglas_economia(),
    }


def reglas_economia() -> dict:
    """Números para el explicador «Cómo gana dinero tu corporativo» (en % del valor del representado)."""
    pct = lambda x: round(x * 100, 2)
    rs, rj = C.RENTA_SELECCION, C.RENTA_JUGADOR
    return {
        "seleccion": {"victoria": pct(rs["jugar"] + rs["victoria"]), "empate": pct(rs["jugar"] + rs["empate"]), "derrota": pct(rs["jugar"] + rs["derrota"]),
                      "avance": pct(rs["avance_fase"]), "eliminacion": pct(rs["eliminacion"])},
        "jugador": {"jugar": pct(rj["jugar"]), "gol": pct(rj["gol"]), "asistencia": pct(rj["asistencia"]), "valla": pct(rj["valla_invicta"]), "roja": pct(rj["roja"])},
        "honorario_partido": {k: pct(v) for k, v in C.HONORARIO_POR_PARTIDO.items()},
        "mantenimiento": {k: pct(v) for k, v in C.HONORARIO_MANTENIMIENTO.items()},
        "patrocinio": {k: pct(v) for k, v in C.PATROCINIO_POR_CICLO.items()}, "popularidad": C.POPULARIDAD_RANGO,
        "partidos_por_ciclo": C.PARTIDOS_ESPERADOS_POR_CICLO, "ciclo_partidos": C.PARTIDOS_POR_CICLO,
        "marketing": {"costo": C.COSTO_MARKETING, "bono": C.MARKETING_BONO_PATROCINIO, "ciclos": C.MARKETING_CICLOS},
        "acuerdos_max": C.ACUERDOS_MAX_ACTIVOS, "gira_ciclos": C.GIRA_CICLOS_SIN_PARTIDO, "renovacion": int(C.PRIMA_RENOVACION * 100),
    }


def obtener_perfil_corporativo(user_id, sigla: str) -> Optional[dict]:
    if sigla not in C.CORPORATIVO_POR_SIGLA:
        return None
    universo = U.obtener_universo(user_id)
    if not universo:
        return None
    U.poner_al_dia(user_id)
    doc = U.db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": sigla})
    v = valores()
    region = afines(sigla)
    ciclo = U.ciclo_en_curso(U.obtener_universo(user_id))
    ctx = _contexto_partidos()
    from services import corporativo_acciones_service as A
    from services.corporativo_ciclo_service import popularidad
    acuerdos = {a["contrato_id"]: a for a in A.acuerdos_de(user_id, sigla) if a["estado"] == "ACTIVO"}
    en_curso = A._giras_en_curso(user_id, sigla)
    seq_u = universo.get("cursor_seq") or U.seq_actual()
    lim_giras = A._limites(user_id, sigla, ciclo, en_curso)
    gira_este_ciclo = not lim_giras["giras_restantes"]   # (nombre viejo: ahora = sin lugar para otra gira en curso)
    from services import corporativo_marcas_service as M
    marcas_contrato = M.patrocinios_por_contrato(user_id, sigla) if doc.get("es_del_usuario") else {}
    selecciones, jugadores = [], []
    for c in U.contratos_activos(user_id, sigla):
        valor_c = (v["selecciones"] if c["tipo"] == "seleccion" else v["jugadores"]).get(c["ref_id"], 0)
        restantes = c["hasta_ciclo"] - ciclo + 1
        base = {"ref_id": c["ref_id"], "contrato_id": str(c["_id"]), "tipo_contrato": c["tipo"], "hasta_ciclo": c["hasta_ciclo"], "ciclos_restantes": restantes,
                "satisfaccion": c["satisfaccion"], "origen": c.get("origen"), "renta_total": c.get("renta_total", 0),
                "honorarios_total": c.get("honorarios_total", 0), "neto": c.get("renta_total", 0) - c.get("honorarios_total", 0),
                "partidos": c.get("partidos", 0), "honorario": R.honorario(c["tipo"], valor_c),
                "costo_renovar": R.prima_renovacion(valor_c, c["satisfaccion"]), "puede_renovar": restantes <= C.CICLOS_AVISO_RENOVACION,
                "costo_rescindir": _costo_rescision(c, valor_c, ciclo)}
        juego = juego_de(c["tipo"], c["ref_id"], ctx)
        motivo_gira = A._motivo_no_disponible(user_id, c, seq_u, ciclo, en_curso) if doc.get("es_del_usuario") else None
        if not motivo_gira and not lim_giras["giras_restantes"]:
            motivo_gira = f"Ya tienes {C.GIRAS_SIMULTANEAS} giras en curso"
        base.update(juego=juego, senal=senal_de(c["tipo"], c["ref_id"], valor_c, juego, ctx, c, ciclo),
                    patrocinio=R.patrocinio(c["tipo"], valor_c, popularidad(c["tipo"], c["ref_id"], valor_c)),
                    acuerdo=acuerdos.get(str(c["_id"])), marcas=marcas_contrato.get(str(c["_id"]), []), ciclos_sin_jugar=c.get("ciclos_sin_jugar", 0),
                    gira_ok=motivo_gira is None, gira_motivo=motivo_gira,
                    de_gira=next((g for g in en_curso if g["tipo"] == c["tipo"] and g["ref_id"] == c["ref_id"]), None))
        if c["tipo"] == "seleccion":
            p = v["info_paises"].get(c["ref_id"], {})
            selecciones.append({**base, **p, "valor": v["selecciones"].get(c["ref_id"], 0), "de_region": c["ref_id"] in region})
        else:
            j = v["info_jugadores"].get(c["ref_id"], {})
            p = v["info_paises"].get(j.get("pais_id"), {})
            jugadores.append({**base, **j, "pais": p.get("nombre"), "bandera": p.get("bandera"),
                              "valor": v["jugadores"].get(c["ref_id"], 0), "de_region": j.get("pais_id") in region})
    selecciones.sort(key=lambda x: -x["valor"])
    jugadores.sort(key=lambda x: -x["valor"])
    valor_cartera = sum(x["valor"] for x in selecciones) + sum(x["valor"] for x in jugadores)
    return {
        "corp": {**_info_corp(sigla), "capital": doc["capital"], "precio": doc["precio"], "precio_inicial": doc["precio_inicial"],
                 "reputacion": doc["reputacion"], "es_del_usuario": doc["es_del_usuario"], "confianza": doc["confianza"],
                 "valor_cartera": valor_cartera,
                 "variacion": round((doc["precio"] / doc["precio_inicial"] - 1) * 100, 1) if doc["precio_inicial"] else 0},
        "selecciones": selecciones, "jugadores": jugadores,
        "perfil_ia": PERFILES_IA.get(C.CORPORATIVO_POR_SIGLA[sigla]["perfil"]),
        "universo": U.obtener_universo(user_id), "ciclo": ciclo,
        "honorarios_ciclo": sum(x["honorario"] for x in selecciones + jugadores),
        "neto_total": sum(x["neto"] for x in selecciones + jugadores),
        "patrocinio_ciclo": sum(x["patrocinio"] for x in selecciones + jugadores),
        "saneamiento": _saneamiento_vista(doc), "exposicion": exposicion(selecciones, jugadores),
        "acuerdos_activos": len(acuerdos), "acuerdos_max": C.ACUERDOS_MAX_ACTIVOS, "gira_este_ciclo": gira_este_ciclo,
        "giras_limites": lim_giras, "giras_en_curso": len({g.get("grupo_id") or g["_id"] for g in en_curso}),
        "marcas_resumen": M.resumen(user_id, sigla) if doc.get("es_del_usuario") else None,
        "senales": {"vender": sum(1 for x in selecciones + jugadores if x["senal"]["senal"] == "vender"),
                    "renovacion": sum(1 for x in selecciones + jugadores if x["senal"].get("renovacion"))},
    }


def exposicion(selecciones: list, jugadores: list) -> list:
    """Valor de la cartera por confederación (para la dona del perfil y de la bolsa)."""
    v = valores()
    tot = {}
    for x in selecciones:
        conf = v["info_paises"].get(x["ref_id"], {}).get("confederacion_id")
        tot[conf] = tot.get(conf, 0) + x["valor"]
    for x in jugadores:
        conf = v["info_paises"].get(x.get("pais_id"), {}).get("confederacion_id")
        tot[conf] = tot.get(conf, 0) + x["valor"]
    total = sum(tot.values()) or 1
    return sorted(({"conf": CONF_SIGLA.get(k, "?"), "color": CONF_COLOR.get(k, "#64748b"), "valor": val,
                    "pct": round(val * 100 / total)} for k, val in tot.items() if k), key=lambda e: -e["valor"])


PERFILES_IA = {
    "conservador": "Prefiere estrellas consolidadas y rara vez vende.",
    "marketing": "Busca valor comercial: selecciones con hinchada y figuras mediáticas.",
    "chequera": "Paga sobreprecio sin pestañear y pide mucho por sus figuras.",
    "cantera": "Apuesta por jóvenes que se valorizan con el tiempo.",
    "equilibrado": "Sin sesgos marcados: compra y vende según el momento.",
    "volumen": "Muchos representados de valor medio para repartir el riesgo.",
    "oportunista": "Caza libres baratos y gangas de último momento.",
}


# --- Acciones del CEO sobre su cartera -----------------------------------------------------------
def _honorarios_estimados(user_id, sigla: str) -> int:
    v = valores()
    return sum(R.honorario(c["tipo"], (v["selecciones"] if c["tipo"] == "seleccion" else v["jugadores"]).get(c["ref_id"], 0))
               for c in U.contratos_activos(user_id, sigla))


def _costo_rescision(contrato: dict, valor: int, ciclo: int) -> int:
    restantes = max(0, contrato["hasta_ciclo"] - ciclo + 1)
    return int(R.honorario(contrato["tipo"], valor) * restantes * C.RESCISION_FRACCION_RESTANTE)


def _contrato_propio(user_id, contrato_id: str):
    universo = U.obtener_universo(user_id)
    if universo and universo["estado"] == "PREAVISO":
        raise ValueError("Durante el preaviso no puedes tocar la cartera")
    if not universo or universo["estado"] != "EN_CARGO":
        raise ValueError("Necesitas un cargo de CEO para manejar la cartera")
    if not ObjectId.is_valid(contrato_id):
        raise ValueError("Contrato inválido")
    contrato = U.db["corp_contratos"].find_one({"_id": ObjectId(contrato_id), "universo_id": user_id, "activo": True})
    if not contrato or contrato["sigla"] != universo["cargo"]["sigla"]:
        raise ValueError("Ese representado no es de tu corporativo")
    return universo, contrato


def _nombre_ref(tipo: str, ref_id: int) -> str:
    v = valores()
    return (v["info_paises"] if tipo == "seleccion" else v["info_jugadores"]).get(ref_id, {}).get("nombre", "?")


def renovar_contrato(user_id, contrato_id: str) -> dict:
    """Renueva un contrato a punto de vencer pagando la prima de RENOVACIÓN (60% de la de referencia, menos si está
    contento: R.prima_renovacion); +10 de satisfacción. Arranca un período nuevo: los totales de rendimiento vuelven a 0."""
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, c = _contrato_propio(user_id, contrato_id)
        ciclo = U.ciclo_en_curso(universo)
        if c["hasta_ciclo"] - ciclo + 1 > C.CICLOS_AVISO_RENOVACION:
            raise ValueError(f"Solo se renueva en los últimos {C.CICLOS_AVISO_RENOVACION} ciclos del contrato")
        valor = U.valor_cartera([c])
        prima = R.prima_renovacion(valor, c.get("satisfaccion", C.SATISFACCION_INICIAL))
        corp = U.db["corp_corporativos"].find_one_and_update(
            {"universo_id": user_id, "sigla": c["sigla"], "capital": {"$gte": prima}}, {"$inc": {"capital": -prima}})
        if not corp:
            raise ValueError(f"Capital insuficiente: la renovación cuesta {prima:,}")
        duracion = R.semilla(user_id, "renovar", c["_id"], ciclo).randint(*C.DURACION_CONTRATO)
        nuevo_hasta = c["hasta_ciclo"] + duracion
        U.db["corp_contratos"].update_one({"_id": c["_id"]}, {"$set": {
            "desde_ciclo": ciclo, "hasta_ciclo": nuevo_hasta, "prima": prima, "origen": "RENOVACION", "renta_total": 0, "honorarios_total": 0,
            "satisfaccion": min(100, c["satisfaccion"] + C.SATISFACCION_RENOVACION)}})
        nombre = _nombre_ref(c["tipo"], c["ref_id"])
        U.db["corp_movimientos"].insert_one({"universo_id": user_id, "sigla": c["sigla"], "ciclo": ciclo, "tipo": "RENOVACION",
                                             "monto": -prima, "detalle": f"Renovación de {nombre} por {duracion} ciclos",
                                             "creado_en": datetime.utcnow()})
    return {"ok": True, "prima": prima, "ciclos": duracion, "nombre": nombre}


def rescindir_contrato(user_id, contrato_id: str) -> dict:
    """Rescinde un contrato pagando el 50% de los honorarios que faltaban; el representado queda libre."""
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, c = _contrato_propio(user_id, contrato_id)
        ciclo = U.ciclo_en_curso(universo)
        costo = _costo_rescision(c, U.valor_cartera([c]), ciclo)
        corp = U.db["corp_corporativos"].find_one_and_update(
            {"universo_id": user_id, "sigla": c["sigla"], "capital": {"$gte": costo}}, {"$inc": {"capital": -costo}})
        if not corp:
            raise ValueError(f"Capital insuficiente: la rescisión cuesta {costo:,}")
        U.db["corp_contratos"].update_one({"_id": c["_id"]}, {"$set": {"activo": False, "fin_ciclo": ciclo, "motivo_fin": "RESCINDIDO"}})
        nombre = _nombre_ref(c["tipo"], c["ref_id"])
        U.db["corp_movimientos"].insert_one({"universo_id": user_id, "sigla": c["sigla"], "ciclo": ciclo, "tipo": "RESCISION",
                                             "monto": -costo, "detalle": f"Rescisión de {nombre}", "creado_en": datetime.utcnow()})
    return {"ok": True, "costo": costo, "nombre": nombre}


# --- Mercado -------------------------------------------------------------------------------------
# Textos de los botones de cada oferta de empleo según (tipo, estado)
BOTONES_OFERTA = {
    ("EMPLEO", "PENDIENTE"): {"etiqueta": "Oferta de trabajo", "si": "Aceptar", "no": "Rechazar",
                              "si_msg": "Asumes la dirección general. Las demás ofertas abiertas se declinan.",
                              "no_msg": "En el próximo cierre de ciclo no recibirás ofertas. Rechazar muchas seguidas te resta fama."},
    ("HEADHUNTING", "PENDIENTE"): {"etiqueta": "Te buscan (confidencial)", "si": "Me interesa", "no": "Rechazar",
                                   "si_msg": "Si tu directorio confía en ti, va a intentar retenerte; si no, empiezas el preaviso.",
                                   "no_msg": "Nadie se entera: sigues en tu cargo."},
    ("HEADHUNTING", "EN_ESPERA"): {"etiqueta": "Esperando tu decisión", "si": "Irme igual", "no": None,
                                   "si_msg": "Presentas la renuncia: un ciclo de preaviso y pierdes las acciones no consolidadas.",
                                   "no_msg": "Rechazas la oferta y sigues en tu cargo con el sueldo actual."},
    ("RETENCION", "PENDIENTE"): {"etiqueta": "Contraoferta de retención", "si": "Quedarme con aumento", "no": "Irme igual",
                                 "si_msg": "Te quedas y cobras el sueldo nuevo.", "no_msg": "Presentas la renuncia y empiezas el preaviso."},
    ("RENOVACION", "PENDIENTE"): {"etiqueta": "Renovación", "si": "Renovar", "no": "No renovar",
                                  "si_msg": "Arranca una temporada nueva con objetivos nuevos.",
                                  "no_msg": "Tu contrato termina y vuelves a buscar empleo (sin pausa)."},
}

TIPOS_PROPUESTA = {
    "PROPUESTA": {"titulo": "Quiere firmar con ustedes", "icono": "bi-person-plus-fill", "si": "Firmar", "no": "Rechazar"},
    "OFERTA_IA": {"titulo": "Oferta de compra", "icono": "bi-cash-stack", "si": "Vender", "no": "Rechazar"},
    "SALIDA": {"titulo": "Pide salir", "icono": "bi-emoji-frown-fill", "si": "Liberarlo", "no": "Negarme"},
    "CONTRAOFERTA": {"titulo": "Contraoferta", "icono": "bi-arrow-left-right", "si": "Pagar y firmar", "no": "Dejarla"},
}


def _bandeja_mercado(user_id, universo: dict, mi_corp: dict) -> dict:
    v = valores()
    ciclo = U.ciclo_en_curso(universo)
    propuestas = []
    for o in U.db["corp_ofertas"].find({"universo_id": user_id, "estado": "PENDIENTE", "tipo": {"$in": list(TIPOS_PROPUESTA)}}).sort("ciclo", -1):
        propuestas.append({**o, **TIPOS_PROPUESTA[o["tipo"]], "nombre": F.nombre_ref(o["ref_tipo"], o["ref_id"]),
                           "valor": F._valor(o["ref_tipo"], o["ref_id"]), "pais_id": F._pais_de(o["ref_tipo"], o["ref_id"]),
                           "costo": o.get("prima", 0) + (o.get("monto", 0) if o["tipo"] == "CONTRAOFERTA" else 0)})
    mis_ofertas = []
    for o in U.db["corp_ofertas"].find({"universo_id": user_id, "tipo": {"$in": ["FICHAJE", "TRASPASO"]}}).sort("creada_en", -1).limit(8):
        mis_ofertas.append({**o, "nombre": F.nombre_ref(o["ref_tipo"], o["ref_id"]), "pais_id": F._pais_de(o["ref_tipo"], o["ref_id"]),
                            "faltan": max(0, o.get("resolver_seq", 0) - U.seq_actual())})
    informe = F.ultimo_scouting(user_id)
    if informe:
        informe["jugadores"] = [{**x, "nombre": F.nombre_ref("jugador", x["ref_id"]), "pais_id": F._pais_de("jugador", x["ref_id"]),
                                 "valor": F._valor("jugador", x["ref_id"])} for x in informe["jugadores"]]
    corp = U.db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": mi_corp["sigla"]}, {"marketing_ciclo": 1})
    from services import corporativo_marcas_service as M
    try:
        marcas = M.resumen(user_id, mi_corp["sigla"])
    except Exception as e:
        print(f"[corporativos] resumen de marcas: {e}")
        marcas = None
    return {"propuestas": propuestas, "mis_ofertas": mis_ofertas, "scouting": informe, "marcas": marcas,
            "scouting_disponible": not informe or informe["ciclo"] != ciclo,
            "marketing_disponible": (corp or {}).get("marketing_ciclo") != ciclo,
            "costo_scouting": C.COSTO_SCOUTING, "costo_marketing": C.COSTO_MARKETING,
            "ventana": U.ventana_traspasos(ciclo), "reputacion": (U.db["corp_corporativos"].find_one(
                {"universo_id": user_id, "sigla": mi_corp["sigla"]}, {"reputacion": 1}) or {}).get("reputacion")}


POR_PAGINA_MERCADO = 30


def obtener_mercado(user_id, tipo: str = "jugador", vista: str = "libres", q: str = "", conf: Optional[int] = None,
                    region: bool = False, edad_max: Optional[int] = None, orden: str = "valor", pagina: int = 1,
                    leyendas: bool = False, pronto: bool = False) -> Optional[dict]:
    universo = U.obtener_universo(user_id)
    if not universo:
        return None
    U.poner_al_dia(user_id)
    universo = U.obtener_universo(user_id)
    tipo = tipo if tipo in ("jugador", "seleccion") else "jugador"
    vista = vista if vista in ("libres", "rivales") else "libres"
    v = valores()
    ciclo = U.ciclo_en_curso(universo)
    cargo = universo.get("cargo") or {}
    sigla = cargo.get("sigla")
    contratos = U.contratos_activos(user_id)
    duenio = {(c["tipo"], c["ref_id"]): c for c in contratos}
    corp = U.db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": sigla}) if sigla else None
    cartera = F.calidad_cartera(contratos, sigla) if sigla else 0
    region_ids = afines(sigla) if sigla else set()
    scout = {x["ref_id"] for x in ((F.ultimo_scouting(user_id) or {}).get("jugadores") or [])}
    pendientes = {(o["ref_tipo"], o["ref_id"]) for o in U.db["corp_ofertas"].find(
        {"universo_id": user_id, "estado": "PENDIENTE", "tipo": {"$in": ["FICHAJE", "TRASPASO"]}}, {"ref_tipo": 1, "ref_id": 1})}

    fuente = v["selecciones"] if tipo == "seleccion" else v["jugadores"]
    ctx = _contexto_partidos()
    q = (q or "").strip().lower()
    filas = []
    for ref_id, valor in fuente.items():
        c = duenio.get((tipo, ref_id))
        if (vista == "libres") == bool(c) or (c and c["sigla"] == sigla):
            continue
        if tipo == "jugador":
            info = v["info_jugadores"].get(ref_id, {})
            pais_id = info.get("pais_id")
            if edad_max and (info.get("edad") or 99) > edad_max:
                continue
            if leyendas and not info.get("leyenda"):
                continue
        else:
            info = v["info_paises"].get(ref_id, {})
            pais_id = ref_id
        pinfo = v["info_paises"].get(pais_id, {})
        if q and q not in (info.get("nombre") or "").lower() and q not in (pinfo.get("nombre") or "").lower():
            continue
        if conf and pinfo.get("confederacion_id") != conf:
            continue
        if region and pais_id not in region_ids:
            continue
        juego = juego_de(tipo, ref_id, ctx)
        if pronto and not juego.get("partidos_2"):
            continue
        filas.append({"ref_id": ref_id, "valor": valor, "pais_id": pais_id, "info": info, "pinfo": pinfo, "contrato": c, "juego": juego})
    if orden == "pronto":
        filas.sort(key=lambda f: (f["juego"].get("faltan", 10 ** 6), -f["valor"]))
    elif orden == "senal":   # primero las mejores señales de compra (más motivos a favor, recuperación más rápida)
        for f in filas:
            f["senal"] = senal_de(tipo, f["ref_id"], f["valor"], f["juego"], ctx)
        filas.sort(key=lambda f: (f["senal"]["senal"] != "comprar", f["senal"]["recupera_ciclos"] or 99, -f["valor"]))
    else:
        filas.sort(key=lambda f: f["valor"], reverse=orden != "valor_asc")
    total = len(filas)
    pagina = max(1, pagina)
    filas = filas[(pagina - 1) * POR_PAGINA_MERCADO: pagina * POR_PAGINA_MERCADO]
    posiciones = {p["id"]: p.get("siglas") for p in U.db["posiciones"].find({}, {"id": 1, "siglas": 1})}
    salida = []
    for f in filas:
        ref_prima = R.prima_referencia(f["valor"])
        fila = {"ref_id": f["ref_id"], "tipo": tipo, "nombre": f["info"].get("nombre"), "valor": f["valor"], "pais_id": f["pais_id"],
                "pais": f["pinfo"].get("nombre"), "bandera": f["pinfo"].get("bandera"), "rankin": f["pinfo"].get("rankin"),
                "edad": f["info"].get("edad"), "posicion": posiciones.get(f["info"].get("posicion_id")),
                "prima_ref": ref_prima, "de_region": f["pais_id"] in region_ids, "scouting": f["ref_id"] in scout and tipo == "jugador",
                "pendiente": (tipo, f["ref_id"]) in pendientes, "leyenda": bool(f["info"].get("leyenda")),
                "juego": f["juego"], "senal": f.get("senal") or senal_de(tipo, f["ref_id"], f["valor"], f["juego"], ctx)}
        if corp:
            fila["base"] = round(F.base_atractivo(corp, universo["fama"], tipo, f["ref_id"], cartera), 2)
            fila["prob"] = round(F.probabilidad(corp, universo["fama"], tipo, f["ref_id"], ref_prima, cartera) * 100)
        if f["contrato"]:
            c = f["contrato"]
            perfil = C.CORPORATIVO_POR_SIGLA[c["sigla"]]["perfil"]
            fila.update(sigla_actual=c["sigla"], logo_actual=url_logo_corporativo(c["sigla"]), satisfaccion=c["satisfaccion"],
                        clausula=int(f["valor"] * C.CLAUSULA_RESCISION_MULTIPLO),
                        pide=int(f["valor"] * C.IA_MULTIPLO_VENTA.get(perfil, C.IA_MULTIPLO_VENTA["default"])))
            if c["satisfaccion"] < C.SATISFACCION_PIDE_SALIR and corp:
                fila["prob"] = min(95, fila["prob"] + int(C.BONO_SATISFACCION_CAMBIO * 100))
        salida.append(fila)
    confederaciones = list(U.db["confederaciones"].find({"principal": 1}, {"_id": 0, "id": 1, "nombre": 1}).sort("id", 1))
    return {
        "universo": universo, "sigla": sigla, "corp": corp, "filas": salida, "total": total, "pagina": pagina,
        "paginas": max(1, -(-total // POR_PAGINA_MERCADO)), "ventana": U.ventana_traspasos(ciclo), "ciclo": ciclo,
        "filtros": {"tipo": tipo, "vista": vista, "q": q, "conf": conf, "region": region, "edad_max": edad_max, "orden": orden, "leyendas": leyendas,
                    "pronto": pronto},
        "confederaciones": confederaciones, "reglas": {
            "peso_oferta": C.PESOS_ATRACTIVO["oferta"], "ideal": C.OFERTA_IDEAL_MULTIPLO, "rango": C.PRIMA_RANGO_OFERTA,
            "min": C.PROBABILIDAD_ACEPTA[0], "max": C.PROBABILIDAD_ACEPTA[1], "duracion": C.DURACION_CONTRATO,
            "responde": C.PARTIDOS_RESPUESTA_FICHAJE},
        "cartera": cartera,
    }


# --- Ranking de CEOs entre usuarios --------------------------------------------------------------
def obtener_ranking_ceos(user_id) -> list:
    """Todos los usuarios con carrera de CEO: fama, cargo actual, trayectoria, total cobrado y acciones (cada uno en su universo)."""
    universos = list(U.db["corp_universos"].find({}))
    if not universos:
        return []
    cobrado = {d["_id"]: -d["total"] for d in U.db["corp_movimientos"].aggregate([
        {"$match": {"tipo": "SUELDO_CEO"}}, {"$group": {"_id": "$universo_id", "total": {"$sum": "$monto"}}}])}
    precios = {(c["universo_id"], c["sigla"]): c.get("precio", 0) for c in U.db["corp_corporativos"].find({}, {"universo_id": 1, "sigla": 1, "precio": 1})}
    acciones = {}
    for t in U.db["corp_tenencias"].find({"cantidad": {"$gt": 0}}):
        acciones[t["universo_id"]] = acciones.get(t["universo_id"], 0) + t["cantidad"] * precios.get((t["universo_id"], t["sigla"]), 0)
    nombres = {str(u["_id"]): u.get("nombre") or u.get("username") for u in U.db["usuarios"].find(
        {"_id": {"$in": [U.filtro_usuario(x["_id"])["_id"] for x in universos]}}, {"username": 1, "nombre": 1})}
    filas = []
    for u in universos:
        uid = u["_id"]
        historial = u.get("historial_cargos") or []
        ciclo = u["ultimo_ciclo"] + 1
        ciclos_ceo = sum(h["hasta_ciclo"] - h["desde_ciclo"] + 1 for h in historial)
        cargo = u.get("cargo") if u.get("estado") in ("EN_CARGO", "PREAVISO") else None
        if cargo:
            ciclos_ceo += ciclo - cargo["desde_ciclo"]
        siglas = [h["sigla"] for h in historial] + ([cargo["sigla"]] if cargo else [])
        mejor_tier = max((C.CORPORATIVO_POR_SIGLA[s]["tier"] for s in siglas), key=lambda t: C.ORDEN_TIER[t], default=None)
        filas.append({
            "usuario_id": str(uid), "nombre": nombres.get(str(uid), "?"), "fama": u["fama"], "estado": ESTADOS_CARRERA[u["estado"]],
            "cargo": {**_info_corp(cargo["sigla"])} if cargo else None, "cargos": len(siglas), "ciclos_ceo": ciclos_ceo,
            "despidos": sum(1 for h in historial if h.get("motivo") == "DESPIDO"),
            "renuncias": sum(1 for h in historial if h.get("motivo") == "RENUNCIA" or str(h.get("motivo", "")).startswith("CAMBIO")),
            "mejor_tier": mejor_tier, "cobrado": int(cobrado.get(uid, 0)), "acciones": int(acciones.get(uid, 0)),
            "trayectoria": [{"sigla": s, "logo": url_logo_corporativo(s)} for s in siglas],
        })
    filas.sort(key=lambda f: (-f["fama"], -f["cobrado"], f["nombre"].lower()))
    for i, f in enumerate(filas):
        f["posicion"] = 1 + sum(1 for g in filas if (g["fama"], g["cobrado"]) > (f["fama"], f["cobrado"]))
        f["soy_yo"] = f["usuario_id"] == str(user_id)
    return filas
