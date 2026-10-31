"""
Directores técnicos: la FEDERACIÓN de cada selección mantiene o cambia a su DT según los resultados.

Datos (todo PERMANENTE: restart_mundial no lo toca, la carrera de un DT sigue entre mundiales):
  - directores_tecnicos   5 por país (agregar_tecnicos.py), con sus rasgos (ver services/tecnicos.py).
  - paises.dt_id          el DT en funciones; paises.federacion_paciencia (0.7 impaciente .. 1.3 paciente).
  - dt_cargos             un documento por cargo: {pais_id, dt_id, desde_juego, hasta_juego (None = vigente),
                          motivo_inicio INICIO|REEMPLAZO, motivo_fin CESE|None, partidos, ganados, empatados,
                          perdidos, gf, gc, puntos, esperados, presion, juegos[], creado_en, cerrado_en, ...}.

Después de cada partido (gancho al final de juegos_service.aplicar_efectos_secundarios, así en la transmisión en
vivo queda diferido y no spoilea) `registrar_partido` suma el resultado al cargo vigente de cada lado y la federación
decide (`decidir_cese`, determinístico: semilla = id del partido + país):
  - PRESIÓN del cargo = media móvil de (puntos esperados - puntos obtenidos), más golpes por goleadas en contra y por
    la expulsión del DT. Esperados: según el prestigio (aficionados) de los dos equipos, así a las potencias se les
    exige más.
  - Probabilidad de cese = curva logística de la presión, escalada por la (im)paciencia de la federación; nunca antes
    de MIN_PARTIDOS en el cargo. Un DT que rinde por encima de lo esperado casi nunca se va.
  - Eliminación de la selección: la federación evalúa una sola vez, con más probabilidad de cambiarlo.
  - Reemplazo: uno de los otros 4 del banco, con más peso a los de más fama y a los que ya le dieron resultados a
    esa selección; uno cesado hace poco puede volver, pero es poco probable.
asignar_tecnicos_partidos.py usa las mismas funciones puras para reconstruir las carreras desde el primer partido.
"""
import math
import random
from datetime import datetime, timezone
from typing import Dict, List, Optional

import certifi
from pymongo.mongo_client import MongoClient

from config.settings import MONGODB_URI
from services import tecnicos as T

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

# --- Reglas de la federación ------------------------------------------------------------------------------------
MIN_PARTIDOS = 3                  # nadie es cesado antes de dirigir 3 partidos
MEMORIA_PRESION = 0.6             # presion = 0.6·presion + 0.4·(esperados - puntos)
GOLPE_GOLEADA = 0.6               # perder por 3 o más
GOLPE_EXPULSION = 0.3             # el DT terminó en la tribuna
PROB_CESE_MAX = 0.55
UMBRAL_PRESION = 1.25             # presión (en puntos por partido) a la que la probabilidad llega a la mitad del máximo
PENDIENTE = 3.0
PROB_CESE_ELIMINADO = 0.35        # base al quedar eliminada (+ según la presión)
PACIENCIA_MIN, PACIENCIA_MAX = 0.7, 1.3
VENTANA_REGRESO = 5               # un cesado en los últimos 5 partidos del país casi no vuelve
PESO_RECIENTE = 0.15

PROB_GANAR_PAREJO, PROB_EMPATE = 0.40, 0.20     # del motor (Monte Carlo): local y visita parejos
SENSIBILIDAD_PRESTIGIO = 0.35


def paciencia_para(pais_id: int) -> float:
    r = random.Random(f"paciencia|{pais_id}")
    return round(r.uniform(PACIENCIA_MIN, PACIENCIA_MAX), 2)


def puntos_esperados(aficionados_propios: float, aficionados_rival: float) -> float:
    d = SENSIBILIDAD_PRESTIGIO * math.log(max(aficionados_propios or 1, 1) / max(aficionados_rival or 1, 1))
    t = math.tanh(d)
    gana = PROB_GANAR_PAREJO + 0.18 * t
    return 3 * gana + PROB_EMPATE


def sumar_partido(cargo: dict, gf: int, gc: int, esperados: float, dt_expulsado: bool, juego_id: str, prensa: float = 0.0) -> dict:
    """Actualiza el cargo en memoria con el resultado (no decide nada)."""
    puntos = 3 if gf > gc else (1 if gf == gc else 0)
    cargo["partidos"] = cargo.get("partidos", 0) + 1
    cargo["ganados"] = cargo.get("ganados", 0) + (gf > gc)
    cargo["empatados"] = cargo.get("empatados", 0) + (gf == gc)
    cargo["perdidos"] = cargo.get("perdidos", 0) + (gf < gc)
    cargo["gf"] = cargo.get("gf", 0) + gf
    cargo["gc"] = cargo.get("gc", 0) + gc
    cargo["puntos"] = cargo.get("puntos", 0) + puntos
    cargo["esperados"] = round(cargo.get("esperados", 0) + esperados, 3)
    from services.prensa import EFECTO_PRESION_DT
    golpe = (GOLPE_GOLEADA if gc - gf >= 3 else 0) + (GOLPE_EXPULSION if dt_expulsado else 0) - EFECTO_PRESION_DT * prensa / 100   # la prensa suma o resta presión
    cargo["presion"] = round(MEMORIA_PRESION * cargo.get("presion", 0.0) + (1 - MEMORIA_PRESION) * (esperados - puntos) + golpe, 3)
    cargo.setdefault("juegos", []).append(juego_id)
    return cargo


def prob_cese(cargo: dict, paciencia: float, eliminado: bool) -> float:
    presion = cargo.get("presion", 0.0) / (paciencia or 1.0)
    if eliminado:
        return min(0.85, PROB_CESE_ELIMINADO + 0.4 / (1 + math.exp(-PENDIENTE * (presion - 0.5))))
    if cargo.get("partidos", 0) < MIN_PARTIDOS:
        return 0.0
    return PROB_CESE_MAX / (1 + math.exp(-PENDIENTE * (presion - UMBRAL_PRESION)))


def decidir_cese(cargo: dict, paciencia: float, eliminado: bool, juego_id: str, pais_id: int) -> bool:
    return random.Random(f"fed|{juego_id}|{pais_id}").random() < prob_cese(cargo, paciencia, eliminado)


def elegir_reemplazo(pais_id: int, saliente_id: int, banco: List[dict], cargos_pais: List[dict], partidos_pais: int,
                     juego_id: str) -> dict:
    """Uno de los otros DT del país. cargos_pais = cargos anteriores de ese país (con 'cerrado_en_partido')."""
    rng = random.Random(f"reemplazo|{juego_id}|{pais_id}")
    candidatos = [d for d in banco if d["id"] != saliente_id] or banco
    pesos = []
    for d in candidatos:
        w = 1.0 + 0.25 * math.log1p(d.get("wikis") or 0)
        previos = [c for c in cargos_pais if c["dt_id"] == d["id"] and c.get("partidos")]
        if previos:
            pts = sum(c["puntos"] for c in previos) / max(1, sum(c["partidos"] for c in previos))
            w *= max(0.4, min(1.8, 1 + 0.6 * (pts - 1.4)))
            ultimo_cese = max((c.get("cerrado_en_partido") or -99) for c in previos)
            if partidos_pais - ultimo_cese <= VENTANA_REGRESO:
                w *= PESO_RECIENTE
        pesos.append(w)
    return rng.choices(candidatos, weights=pesos)[0]


def elegir_inicial(pais_id: int, banco: List[dict], semilla: str = "inicio") -> dict:
    return random.Random(f"{semilla}|{pais_id}").choice(sorted(banco, key=lambda d: d["id"]))


# --- Persistencia -------------------------------------------------------------------------------------------------
def _ahora():
    return datetime.now(timezone.utc)


def _eliminado(pais_id: int) -> bool:
    """Quedó afuera del Mundial en curso: 'paises.estado' ELIMINADO_* (las eliminadas salen de 'internacional')."""
    p = db["paises"].find_one({"id": pais_id}, {"estado": 1})
    return str((p or {}).get("estado", "")).startswith("ELIMINADO")


def nuevo_cargo(pais_id: int, dt: dict, motivo: str, juego_id: Optional[str], mundial_id: Optional[str],
                partido_pais: int = 0, fecha_juego: Optional[str] = None) -> dict:
    return {"pais_id": pais_id, "dt_id": dt["id"], "dt_nombre": dt["nombre"], "mundial_id": mundial_id,
            "desde_juego": juego_id, "desde_fecha_juego": fecha_juego, "desde_partido_pais": partido_pais,
            "hasta_juego": None, "motivo_inicio": motivo, "motivo_fin": None,
            "partidos": 0, "ganados": 0, "empatados": 0, "perdidos": 0, "gf": 0, "gc": 0, "puntos": 0,
            "esperados": 0.0, "presion": 0.0, "juegos": [], "creado_en": _ahora(), "cerrado_en": None}


def asegurar_dt_en_todos(mundial_id: Optional[str] = None) -> int:
    """Le pone DT a las selecciones que no tienen (al crear un Mundial). Devuelve cuántas asignó."""
    asignados = 0
    bancos: Dict[int, List[dict]] = {}
    for d in db["directores_tecnicos"].find({}, {"id": 1, "nombre": 1, "pais_id": 1}):
        bancos.setdefault(d["pais_id"], []).append(d)
    for p in db["paises"].find({}, {"id": 1, "dt_id": 1, "federacion_paciencia": 1}):
        banco = bancos.get(p["id"])
        if not banco or p.get("dt_id"):
            continue
        dt = elegir_inicial(p["id"], banco)
        db["dt_cargos"].insert_one(nuevo_cargo(p["id"], dt, "INICIO", None, mundial_id))
        db["paises"].update_one({"id": p["id"]}, {"$set": {"dt_id": dt["id"], "federacion_paciencia": p.get("federacion_paciencia") or paciencia_para(p["id"])}})
        asignados += 1
    return asignados


# --- Formación: contexto para la decisión del DT y su historial por esquema -------------------------------------
def _rating(pais_id) -> float:
    d = db["internacional"].find_one({"id": pais_id}, {"estadisticas": 1}) or db["paises"].find_one({"id": pais_id}, {"estadisticas": 1}) or {}
    e = d.get("estadisticas") or {}
    jj = e.get("juegos_jugados") or 0
    return ((e.get("goles_favor") or 0) - (e.get("goles_contra") or 0)) / (jj + 5)   # contracción: pocos partidos -> cerca de 0


def _forma(pais_id) -> Optional[float]:
    """Puntos de sus últimos 5 partidos / 15 (None si no jugó)."""
    puntos = []
    for j in db["juegos"].find({"estado": "finalizado", "$or": [{"equipo_local.id": pais_id}, {"equipo_visitante.id": pais_id}]},
                               {"resultado.ganador_id": 1, "resultado.empate": 1}).sort([("fecha", -1), ("hora", -1)]).limit(5):
        r = j.get("resultado") or {}
        puntos.append(1 if r.get("empate") else (3 if r.get("ganador_id") == pais_id else 0))
    return sum(puntos) / 15 if puntos else None


def contexto_tactico(pais_id, rival_id, dt: Optional[dict], dt_rival: Optional[dict], local: bool,
                     eliminacion: bool = False, marcador_ida: Optional[dict] = None) -> dict:
    """Lo que el DT mira para elegir el esquema (tecnicos.elegir_esquema). Nunca lanza."""
    try:
        global_ = None
        if marcador_ida:
            propios = marcador_ida.get("goles_local", 0) if local else marcador_ida.get("goles_visita", 0)
            ajenos = marcador_ida.get("goles_visita", 0) if local else marcador_ida.get("goles_local", 0)
            global_ = propios - ajenos
        return {"fuerza": round(_rating(pais_id) - _rating(rival_id), 3), "forma": _forma(pais_id), "local": local,
                "serie": {"vuelta": True, "global": global_} if global_ is not None else None, "eliminacion": eliminacion,
                "historial": (dt or {}).get("esquemas") or {}, "ultimo": (dt or {}).get("ultimo_esquema"),
                "rival_probable": T.esquema_probable(dt_rival, (dt_rival or {}).get("ultimo_esquema"))}
    except Exception as e:
        print(f"[tecnicos] contexto táctico: {e}")
        return {}


def _registrar_esquema(dt_id, esquema: Optional[str], gf: int, gc: int) -> None:
    """Suma el partido al historial del DT con ese esquema (directores_tecnicos.esquemas, permanente)."""
    if not dt_id or not esquema:
        return
    puntos = 3 if gf > gc else (1 if gf == gc else 0)
    db["directores_tecnicos"].update_one({"id": dt_id}, {"$inc": {f"esquemas.{esquema}.pj": 1, f"esquemas.{esquema}.pts": puntos,
                                                                  f"esquemas.{esquema}.gf": gf, f"esquemas.{esquema}.gc": gc},
                                                         "$set": {"ultimo_esquema": esquema}})


def registrar_partido(juego: Optional[dict]) -> None:
    """Suma el partido terminado al cargo de cada DT y la federación decide. Idempotente por juego. Nunca lanza."""
    try:
        if not juego or juego.get("estado") != "finalizado" or not juego.get("resultado"):
            return
        res, jid = juego["resultado"], str(juego["_id"])
        lados = [(res["id_local"], res["id_visitante"], res["goles_local"], res["goles_visitante"], "local"),
                 (res["id_visitante"], res["id_local"], res["goles_visitante"], res["goles_local"], "visita")]
        afic = {p["id"]: p.get("aficionados") or 1 for p in db["paises"].find({"id": {"$in": [res["id_local"], res["id_visitante"]]}},
                                                                                {"id": 1, "aficionados": 1})}
        for pais_id, rival_id, gf, gc, lado in lados:
            cargo = db["dt_cargos"].find_one({"pais_id": pais_id, "hasta_juego": None})
            if not cargo or jid in (cargo.get("juegos") or []):
                continue
            dt_partido = (res.get("dt") or {}).get(lado) or {}
            try:
                from services.prensa_service import reputacion_centrada
                prensa = reputacion_centrada("dt", cargo.get("dt_id"))
            except Exception:
                prensa = 0.0
            sumar_partido(cargo, gf, gc, puntos_esperados(afic.get(pais_id), afic.get(rival_id)), bool(dt_partido.get("expulsado")), jid, prensa)
            campos = {k: cargo[k] for k in ("partidos", "ganados", "empatados", "perdidos", "gf", "gc", "puntos", "esperados", "presion")}
            ok = db["dt_cargos"].update_one({"_id": cargo["_id"], "juegos": {"$ne": jid}}, {"$set": campos, "$push": {"juegos": jid}})
            if not ok.modified_count:
                continue
            esquema = res.get("tactica_local") if lado == "local" else res.get("tactica_visita")
            _registrar_esquema(cargo.get("dt_id"), esquema, gf, gc)
            pais = db["paises"].find_one({"id": pais_id}, {"federacion_paciencia": 1, "nombre": 1})
            eliminado = _eliminado(pais_id)
            if eliminado and cargo.get("evaluado_eliminado"):
                continue
            if eliminado:
                db["dt_cargos"].update_one({"_id": cargo["_id"]}, {"$set": {"evaluado_eliminado": True}})
            paciencia = (pais or {}).get("federacion_paciencia") or paciencia_para(pais_id)
            if decidir_cese(cargo, paciencia, eliminado, jid, pais_id):
                _cesar(cargo, pais_id, jid, juego.get("mundial_id"), juego.get("fecha"), eliminado)
    except Exception as e:
        print(f"[tecnicos] no se pudo registrar el partido: {e}")


def _partidos_del_pais(pais_id: int) -> int:
    return sum(c.get("partidos", 0) for c in db["dt_cargos"].find({"pais_id": pais_id}, {"partidos": 1}))


def _cesar(cargo: dict, pais_id: int, jid: str, mundial_id, fecha, eliminado: bool) -> None:
    jugados = _partidos_del_pais(pais_id)
    cerrado = db["dt_cargos"].update_one(
        {"_id": cargo["_id"], "hasta_juego": None},
        {"$set": {"hasta_juego": jid, "motivo_fin": "CESE", "cerrado_en": _ahora(), "cerrado_en_partido": jugados, "hasta_fecha_juego": fecha,
                  "cese_por_eliminacion": eliminado}})
    if not cerrado.modified_count:
        return
    banco = list(db["directores_tecnicos"].find({"pais_id": pais_id}, {"id": 1, "nombre": 1, "wikis": 1}))
    cargos_pais = list(db["dt_cargos"].find({"pais_id": pais_id}, {"dt_id": 1, "puntos": 1, "partidos": 1, "cerrado_en_partido": 1}))
    nuevo = elegir_reemplazo(pais_id, cargo["dt_id"], banco, cargos_pais, jugados, jid)
    db["dt_cargos"].insert_one({**nuevo_cargo(pais_id, nuevo, "REEMPLAZO", jid, mundial_id, jugados, fecha),
                                "reemplaza_a": cargo["dt_id"], "regreso": any(c["dt_id"] == nuevo["id"] for c in cargos_pais)})
    db["paises"].update_one({"id": pais_id}, {"$set": {"dt_id": nuevo["id"]}})
    _cache.clear()


# --- Lectura para las vistas ----------------------------------------------------------------------------------------
_cache: Dict = {}


def dt_de_pais(pais_id: int) -> Optional[dict]:
    p = db["paises"].find_one({"id": pais_id}, {"dt_id": 1})
    if not p or not p.get("dt_id"):
        return None
    return db["directores_tecnicos"].find_one({"id": p["dt_id"]}, {"_id": 0})


def cargo_vigente(pais_id: int) -> Optional[dict]:
    return db["dt_cargos"].find_one({"pais_id": pais_id, "hasta_juego": None}, {"juegos": 0})


def ultimos_cambios(limite: int = 10) -> List[dict]:
    """Los últimos relevos de DT (para el feed del inicio)."""
    nuevos = list(db["dt_cargos"].find({"motivo_inicio": "REEMPLAZO"}, {"juegos": 0}).sort([("desde_fecha_juego", -1), ("creado_en", -1)]).limit(limite))
    return nuevos


# --- Directorio y perfil (/tecnicos) -------------------------------------------------------------------------------
SIGLA_CONF = {1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC"}
ETIQUETA_ESTILO = {"ofensivo": "Ofensivo", "equilibrado": "Equilibrado", "defensivo": "Defensivo"}
TIPOS_DT = ("🗣️ RECLAMO DEL DT", "🟨 DT AMONESTADO", "🟥 DT EXPULSADO", "📋 AJUSTE TÁCTICO")


def etiqueta_rasgo(valor) -> str:
    v = valor or 55
    return "muy alto" if v >= 75 else "alto" if v >= 62 else "medio" if v >= 48 else "bajo" if v >= 35 else "muy bajo"


def _mundial_activo() -> Optional[str]:
    m = db["mundiales"].find_one({"activo": True}, {"_id": 1})
    return str(m["_id"]) if m else None


def _stats_mundial() -> Dict[int, dict]:
    """Por DT, lo que hizo en los partidos del Mundial en curso (resultado.dt + sus eventos). Cacheado por partidos jugados."""
    mundial = _mundial_activo()
    filtro = {"estado": "finalizado", "resultado.dt": {"$exists": True}, "transmision.estado": {"$ne": "in_progress"}}
    if mundial:
        filtro["mundial_id"] = mundial
    clave = (mundial, db["juegos"].count_documents(filtro))
    if _cache.get("stats_clave") == clave:
        return _cache["stats"]
    stats: Dict[int, dict] = {}
    for j in db["juegos"].find(filtro, {"resultado.dt": 1, "resultado.goles_local": 1, "resultado.goles_visitante": 1,
                                         "resultado.local": 1, "resultado.visitante": 1, "resultado.eventos.tipo": 1,
                                         "resultado.eventos.dt_id": 1, "resultado.eventos.equipo": 1}):
        r = j["resultado"]
        for lado, gf, gc in (("local", r["goles_local"], r["goles_visitante"]), ("visita", r["goles_visitante"], r["goles_local"])):
            dt = (r.get("dt") or {}).get(lado)
            if not dt:
                continue
            s = stats.setdefault(dt["id"], {"partidos": 0, "ganados": 0, "empatados": 0, "perdidos": 0, "gf": 0, "gc": 0,
                                            "reclamos": 0, "amonestado": 0, "expulsado": 0, "ajustes": 0, "ajustes_con_gol": 0})
            s["partidos"] += 1
            s["ganados"] += gf > gc
            s["empatados"] += gf == gc
            s["perdidos"] += gf < gc
            s["gf"] += gf
            s["gc"] += gc
            equipo = r["local"] if lado == "local" else r["visitante"]
            ajusto = False
            for e in r.get("eventos") or []:
                if e.get("dt_id") == dt["id"]:
                    t = e.get("tipo")
                    s["reclamos"] += t == "🗣️ RECLAMO DEL DT"
                    s["amonestado"] += t == "🟨 DT AMONESTADO"
                    s["expulsado"] += t == "🟥 DT EXPULSADO"
                    if t == "📋 AJUSTE TÁCTICO":
                        s["ajustes"] += 1
                        ajusto = True
                elif ajusto and e.get("tipo", "").startswith("⚽ GOL") and e.get("tipo") != "⚽ GOL DE PENAL" and e.get("equipo") == equipo:
                    s["ajustes_con_gol"] += 1
                    ajusto = False
    for s in stats.values():
        s["puntos_pct"] = round((3 * s["ganados"] + s["empatados"]) / (3 * s["partidos"]) * 100) if s["partidos"] else 0
    _cache.update({"stats_clave": clave, "stats": stats})
    return stats


def _carrera() -> Dict[int, dict]:
    """Por DT, la suma de todos sus cargos (permanente: incluye mundiales anteriores)."""
    carrera: Dict[int, dict] = {}
    for c in db["dt_cargos"].find({}, {"juegos": 0}):
        k = carrera.setdefault(c["dt_id"], {"cargos": 0, "partidos": 0, "ganados": 0, "empatados": 0, "perdidos": 0,
                                            "ceses": 0, "regresos": 0, "esperados": 0.0, "puntos": 0})
        k["cargos"] += 1
        for campo in ("partidos", "ganados", "empatados", "perdidos", "puntos"):
            k[campo] += c.get(campo, 0)
        k["esperados"] += c.get("esperados", 0.0)
        k["ceses"] += c.get("motivo_fin") == "CESE"
        k["regresos"] += bool(c.get("regreso"))
    for k in carrera.values():
        k["sobre_esperado"] = round((k["puntos"] - k["esperados"]) / k["partidos"], 2) if k["partidos"] else 0.0
    return carrera


def listar_tecnicos() -> dict:
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1, "confederacion_id": 1, "dt_id": 1, "estado": 1,
                                                       "federacion_paciencia": 1})}
    stats, carrera = _stats_mundial(), _carrera()
    vigentes = {c["dt_id"]: c for c in db["dt_cargos"].find({"hasta_juego": None}, {"juegos": 0})}
    filas = []
    for t in db["directores_tecnicos"].find({}, {"_id": 0}).sort("id", 1):
        p = paises.get(t["pais_id"], {})
        s, c = stats.get(t["id"], {}), carrera.get(t["id"], {})
        filas.append({**t, "pais_nombre": p.get("nombre"), "bandera": p.get("bandera"),
                      "confederacion": SIGLA_CONF.get(p.get("confederacion_id"), ""), "en_funciones": p.get("dt_id") == t["id"],
                      "estilo_nombre": ETIQUETA_ESTILO.get(t.get("estilo"), "—"),
                      "partidos": s.get("partidos", 0), "ganados": s.get("ganados", 0), "empatados": s.get("empatados", 0),
                      "perdidos": s.get("perdidos", 0), "puntos_pct": s.get("puntos_pct", 0), "expulsado": s.get("expulsado", 0),
                      "amonestado": s.get("amonestado", 0), "ajustes": s.get("ajustes", 0),
                      "ceses": c.get("ceses", 0), "cargos": c.get("cargos", 0), "sobre_esperado": c.get("sobre_esperado", 0.0)})
        fila = filas[-1]
        cg = vigentes.get(t["id"]) if fila["en_funciones"] else None
        pj = (cg or {}).get("partidos", 0)
        fila.update({"riesgo": round(prob_cese(cg, p.get("federacion_paciencia") or 1.0, False) * 100) if cg else None,
                     "cargo_pj": pj, "cargo_record": f'{cg.get("ganados", 0)}-{cg.get("empatados", 0)}-{cg.get("perdidos", 0)}' if cg else None,
                     "cargo_sobre": round((cg.get("puntos", 0) - cg.get("esperados", 0)) / pj, 2) if pj else 0.0,
                     "arquetipo": arquetipo(t)["titulo"]})
    en_funciones = [f for f in filas if f["en_funciones"]]
    cuerda_floja = sorted([f for f in en_funciones if f["cargo_pj"] >= MIN_PARTIDOS and (f["riesgo"] or 0) > 0],
                          key=lambda f: (-f["riesgo"], f["cargo_sobre"]))[:5]
    intocables = sorted([f for f in en_funciones if f["cargo_pj"] >= MIN_PARTIDOS], key=lambda f: (-f["cargo_sobre"], -f["cargo_pj"]))[:5]
    con_partidos = [f for f in en_funciones if f["partidos"] >= 5]
    destacados = []
    if con_partidos:
        mejor = max(con_partidos, key=lambda f: (f["puntos_pct"], f["partidos"]))
        destacados.append({"titulo": "Mejor rendimiento", "fila": mejor, "detalle": f"{mejor['puntos_pct']}% de los puntos"})
    caliente = max(filas, key=lambda f: (f["expulsado"], f["amonestado"]), default=None)
    if caliente and (caliente["expulsado"] or caliente["amonestado"]):
        destacados.append({"titulo": "El más caliente", "fila": caliente,
                           "detalle": f"{caliente['amonestado']} amonestaci{'ón' if caliente['amonestado'] == 1 else 'ones'} · {caliente['expulsado']} expulsi{'ón' if caliente['expulsado'] == 1 else 'ones'}"})
    estratega = max(filas, key=lambda f: (f["ajustes"], f["partidos"]), default=None)
    if estratega and estratega["ajustes"]:
        destacados.append({"titulo": "El que más mueve el tablero", "fila": estratega, "detalle": f"{estratega['ajustes']} ajustes tácticos"})
    ceses = db["dt_cargos"].count_documents({"motivo_fin": "CESE"})
    return {"filas": filas, "destacados": destacados, "en_funciones": len(en_funciones), "ceses": ceses,
            "confederaciones": [v for k, v in sorted(SIGLA_CONF.items())], "ultimos_cambios": _relevos(9, paises),
            "cuerda_floja": cuerda_floja, "intocables": intocables,
            "regresos": db["dt_cargos"].count_documents({"regreso": True}),
            "expulsiones": sum(f["expulsado"] for f in filas), "ajustes": sum(f["ajustes"] for f in filas),
            "reales": sum(1 for f in filas if not f.get("ficticio"))}


def _relevos(limite: int, paises: Optional[dict] = None) -> List[dict]:
    paises = paises or {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1, "federacion": 1})}
    nombres = {t["id"]: t["nombre"] for t in db["directores_tecnicos"].find({}, {"id": 1, "nombre": 1})}
    salida = []
    cambios = ultimos_cambios(limite)
    # los cargos que terminaron en cada relevo, en UNA consulta (antes una por relevo)
    salientes = {(s["pais_id"], s.get("dt_id"), s.get("hasta_juego")): s for s in db["dt_cargos"].find(
        {"hasta_juego": {"$in": [c.get("desde_juego") for c in cambios if c.get("desde_juego")]}},
        {"pais_id": 1, "dt_id": 1, "hasta_juego": 1, "ganados": 1, "empatados": 1, "perdidos": 1, "cese_por_eliminacion": 1})} if cambios else {}
    for c in cambios:
        p = paises.get(c["pais_id"], {})
        saliente = salientes.get((c["pais_id"], c.get("reemplaza_a"), c.get("desde_juego"))) or {}
        salida.append({"pais_id": c["pais_id"], "pais": p.get("nombre"), "bandera": p.get("bandera"),
                       "fecha_txt": fecha_corta(c.get("desde_fecha_juego")), "por_eliminacion": saliente.get("cese_por_eliminacion"),
                       "record_sale": f'{saliente.get("ganados", 0)}-{saliente.get("empatados", 0)}-{saliente.get("perdidos", 0)}' if saliente else None,
                       "entra_id": c["dt_id"], "entra": c.get("dt_nombre") or nombres.get(c["dt_id"]),
                       "sale_id": c.get("reemplaza_a"), "sale": nombres.get(c.get("reemplaza_a")), "regreso": c.get("regreso"),
                       "desde_juego": c.get("desde_juego"), "creado_en": c.get("creado_en")})
    return salida


def perfil_tecnico(tecnico_id: int) -> Optional[dict]:
    t = db["directores_tecnicos"].find_one({"id": tecnico_id}, {"_id": 0})
    if not t:
        return None
    pais = db["paises"].find_one({"id": t["pais_id"]}, {"_id": 0, "id": 1, "nombre": 1, "bandera": 1, "federacion": 1,
                                                          "confederacion_id": 1, "dt_id": 1, "federacion_paciencia": 1})
    cargos = list(db["dt_cargos"].find({"dt_id": tecnico_id}).sort([("desde_partido_pais", 1), ("creado_en", 1)]))
    vigente = next((c for c in cargos if c.get("hasta_juego") is None and pais and pais.get("dt_id") == tecnico_id), None)
    # bitácora: los partidos del Mundial en curso que dirigió, con lo que hizo
    partidos = []
    filtro = {"estado": "finalizado", "$or": [{"resultado.dt.local.id": tecnico_id}, {"resultado.dt.visita.id": tecnico_id}],
              "transmision.estado": {"$ne": "in_progress"}}
    for j in db["juegos"].find(filtro, {"fecha": 1, "fase_id": 1, "jornada": 1, "resultado.dt": 1, "resultado.local": 1,
                                         "resultado.visitante": 1, "resultado.id_local": 1, "resultado.id_visitante": 1,
                                         "resultado.goles_local": 1, "resultado.goles_visitante": 1,
                                         "resultado.eventos.tipo": 1, "resultado.eventos.dt_id": 1}).sort([("fecha", -1), ("hora", -1)]):
        r = j["resultado"]
        local = (r.get("dt") or {}).get("local", {}).get("id") == tecnico_id
        gf, gc = (r["goles_local"], r["goles_visitante"]) if local else (r["goles_visitante"], r["goles_local"])
        propios = [e["tipo"] for e in r.get("eventos") or [] if e.get("dt_id") == tecnico_id]
        partidos.append({"id": str(j["_id"]), "fecha": j.get("fecha"), "jornada": j.get("jornada"),
                         "rival": r["visitante"] if local else r["local"], "rival_id": r["id_visitante"] if local else r["id_local"],
                         "gf": gf, "gc": gc, "resultado": "G" if gf > gc else "E" if gf == gc else "P",
                         "ajustes": propios.count("📋 AJUSTE TÁCTICO"), "reclamos": propios.count("🗣️ RECLAMO DEL DT"),
                         "amonestado": "🟨 DT AMONESTADO" in propios, "expulsado": "🟥 DT EXPULSADO" in propios})
    stats = _stats_mundial().get(tecnico_id, {})
    carrera = _carrera().get(tecnico_id, {})
    # comparación con los colegas que dirigen hoy
    todos = [s for s in _stats_mundial().values() if s.get("partidos", 0) >= 3]
    media_pct = round(sum(s["puntos_pct"] for s in todos) / len(todos)) if todos else None
    banco = list(db["directores_tecnicos"].find({"pais_id": t["pais_id"], "id": {"$ne": tecnico_id}}, {"_id": 0, "id": 1, "nombre": 1, "edad": 1, "estilo": 1}))
    # fechas de cada cargo (primer y último partido que dirigió) y la serie de puntos reales vs esperados (cronológica)
    fechas_juegos = {p["id"]: p["fecha"] for p in partidos}
    for c in cargos:
        js = [j for j in (c.get("juegos") or []) if j in fechas_juegos]
        c["desde_txt"] = fecha_corta(fechas_juegos.get(js[0]) if js else c.get("desde_fecha_juego"))
        c["hasta_txt"] = fecha_corta(fechas_juegos.get(c.get("hasta_juego")) or c.get("hasta_fecha_juego")) if c.get("hasta_juego") else None
        c.pop("juegos", None)
    afic = {q["id"]: q.get("aficionados") or 1 for q in db["paises"].find({}, {"id": 1, "aficionados": 1})}
    real = esperado = 0.0
    serie = []
    for k, pm in enumerate(reversed(partidos), start=1):
        real += 3 if pm["resultado"] == "G" else 1 if pm["resultado"] == "E" else 0
        esperado += puntos_esperados(afic.get(t["pais_id"]), afic.get(pm["rival_id"]))
        serie.append({"n": k, "rival": pm["rival"], "marcador": f'{pm["gf"]}-{pm["gc"]}', "real": real, "esperado": round(esperado, 2)})
    for pm in partidos:
        pm["fecha_txt"] = fecha_corta(pm["fecha"])
    # percentil de cada rasgo entre todos los técnicos (y el promedio, para el radar)
    claves = ["lectura", "motivacion", "temperamento", "confianza_leyendas"]
    todos_rasgos = list(db["directores_tecnicos"].find({}, {"_id": 0, **{k: 1 for k in claves}}))
    promedio = {k: round(sum(x.get(k) or 0 for x in todos_rasgos) / max(1, len(todos_rasgos)), 1) for k in claves}
    percentil = {k: round(100 * sum(1 for x in todos_rasgos if (x.get(k) or 0) < (t.get(k) or 0)) / max(1, len(todos_rasgos))) for k in claves}
    rasgos = [("Lectura de partido", "lectura", "bi-eye"), ("Motivación", "motivacion", "bi-fire"),
              ("Temperamento", "temperamento", "bi-megaphone"), ("Confianza en las leyendas", "confianza_leyendas", "bi-award")]
    # Esquemas: sus preferencias por estilo y su rendimiento real con cada uno (directores_tecnicos.esquemas)
    from config import formaciones as CF
    pref = CF.PREFERENCIAS_ESTILO.get(t.get("estilo") or "equilibrado", CF.PREFERENCIAS_ESTILO["equilibrado"])
    total_pref = sum(pref.values()) or 1
    esquemas_vista = []
    for e in CF.ESQUEMAS:
        h = (t.get("esquemas") or {}).get(e) or {}
        esquemas_vista.append({"esquema": e, "etiqueta": CF.FORMACIONES[e]["etiqueta"], "postura": CF.FORMACIONES[e]["postura"],
                               "preferencia": round(100 * pref.get(e, 0) / total_pref), "pj": h.get("pj", 0),
                               "ppp": round(h.get("pts", 0) / h["pj"], 2) if h.get("pj") else None,
                               "gf": h.get("gf", 0), "gc": h.get("gc", 0)})
    esquemas_vista.sort(key=lambda x: (-x["pj"], -x["preferencia"]))
    return {**t, "esquemas_vista": esquemas_vista, "pais": pais, "confederacion": SIGLA_CONF.get((pais or {}).get("confederacion_id"), ""),
            "estilo_nombre": ETIQUETA_ESTILO.get(t.get("estilo"), "—"), "en_funciones": bool(vigente), "cargo_vigente": vigente,
            "cargos": cargos, "partidos_mundial": partidos, "stats": stats, "carrera": carrera, "media_pct": media_pct,
            "rasgos": [{"nombre": n, "clave": k, "valor": t.get(k), "etiqueta": etiqueta_rasgo(t.get(k)), "icono": i,
                        "percentil": percentil[k], "promedio": promedio[k]} for n, k, i in rasgos],
            "arquetipo": arquetipo(t), "serie": serie, "racha": [pm["resultado"] for pm in partidos[:5]][::-1],
            "sobre_esperado_mundial": round((serie[-1]["real"] - serie[-1]["esperado"]) / len(serie), 2) if serie else None,
            "banco": banco, "presion": round((vigente or {}).get("presion", 0.0), 2) if vigente else None,
            "prob_cese": round(prob_cese(vigente, (pais or {}).get("federacion_paciencia") or 1.0, False) * 100) if vigente else None}


def arquetipo(t: dict) -> dict:
    """Etiqueta del DT a partir de sus rasgos (para las vistas): rol por lectura/motivación, estilo y temple."""
    lec, mot, tem = t.get("lectura") or 55, t.get("motivacion") or 55, t.get("temperamento") or 55
    if lec >= 65 and lec >= mot:
        rol, desc_rol = "Estratega", "lee el partido como pocos y mueve el tablero a tiempo"
    elif mot >= 65:
        rol, desc_rol = "Motivador", "contagia al plantel y saca lo mejor de cada jugador"
    elif lec < 45 and mot < 45:
        rol, desc_rol = "Conservador", "confía en el plan inicial y cambia poco"
    else:
        rol, desc_rol = "Técnico", "equilibra la pizarra y el vestuario"
    estilo = {"ofensivo": "ofensivo", "defensivo": "pragmático", "equilibrado": "equilibrado"}.get(t.get("estilo"), "equilibrado")
    temple = "de sangre caliente" if tem >= 68 else ("de temple frío" if tem <= 42 else "de carácter firme")
    desc_temple = ("discute cada fallo y suele terminar amonestado" if tem >= 68 else
                   "casi nunca protesta: el árbitro rara vez lo mira" if tem <= 42 else "reclama cuando hace falta")
    icono = {"Estratega": "bi-diagram-3-fill", "Motivador": "bi-fire", "Conservador": "bi-shield-fill", "Técnico": "bi-clipboard-check"}[rol]
    return {"titulo": f"{rol} {estilo} {temple}", "rol": rol, "icono": icono,
            "descripcion": f"{desc_rol.capitalize()}; {desc_temple}."}


MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def fecha_corta(fecha) -> Optional[str]:
    """'1897-05-22' -> '22-May-1897' (las fechas del torneo son strings ISO)."""
    try:
        a, m, d = str(fecha)[:10].split("-")
        return f"{int(d):02d}-{MESES[int(m) - 1]}-{int(a)}"
    except (ValueError, IndexError):
        return None


def tarjeta_pais(pais_id: int) -> Optional[dict]:
    """Para /paises/{id}: el DT en funciones (cargo, presión, racha), el banco de la federación y la línea de tiempo
    de los técnicos de la selección con el rango de fechas de cada uno (primer y último partido que dirigió)."""
    pais = db["paises"].find_one({"id": pais_id}, {"dt_id": 1, "federacion": 1, "federacion_paciencia": 1})
    if not pais or not pais.get("dt_id"):
        return None
    dt = db["directores_tecnicos"].find_one({"id": pais["dt_id"]}, {"_id": 0})
    cargos = list(db["dt_cargos"].find({"pais_id": pais_id}).sort([("desde_partido_pais", 1), ("creado_en", 1)]))
    ids = {j for c in cargos for j in (c.get("juegos") or [])}
    from bson import ObjectId
    juegos = {str(j["_id"]): j for j in db["juegos"].find({"_id": {"$in": [ObjectId(i) for i in ids]}},
                                                           {"fecha": 1, "resultado.id_local": 1, "resultado.goles_local": 1,
                                                            "resultado.goles_visitante": 1})}
    def _resultado(jid):
        r = (juegos.get(jid) or {}).get("resultado") or {}
        if not r:
            return None
        gf, gc = (r["goles_local"], r["goles_visitante"]) if r.get("id_local") == pais_id else (r["goles_visitante"], r["goles_local"])
        return "G" if gf > gc else "E" if gf == gc else "P"
    linea = []
    for c in cargos:
        js = c.get("juegos") or []
        desde = (juegos.get(js[0]) or {}).get("fecha") if js else None
        hasta = (juegos.get(c["hasta_juego"]) or {}).get("fecha") if c.get("hasta_juego") else None
        linea.append({**{k: c.get(k) for k in ("dt_id", "dt_nombre", "partidos", "ganados", "empatados", "perdidos", "motivo_fin",
                                               "cese_por_eliminacion", "regreso", "hasta_juego", "puntos", "esperados")},
                      # sin partidos dirigidos todavía: la fecha del partido que provocó el relevo (cuando asumió)
                      "desde": fecha_corta(desde or c.get("desde_fecha_juego")), "sin_debut": not js,
                      "hasta": fecha_corta(hasta or c.get("hasta_fecha_juego")),
                      "vigente": c.get("hasta_juego") is None, "racha": [x for x in (_resultado(j) for j in js[-5:]) if x]})
    linea.reverse()   # el más reciente primero
    cargo = next((c for c in cargos if c.get("hasta_juego") is None), {})
    actual = next((x for x in linea if x["vigente"]), {})
    banco = list(db["directores_tecnicos"].find({"pais_id": pais_id, "id": {"$ne": pais["dt_id"]}},
                                                {"_id": 0, "id": 1, "nombre": 1, "edad": 1, "estilo": 1}).sort("id", 1))
    riesgo = round(prob_cese(cargo, pais.get("federacion_paciencia") or 1.0, False) * 100) if cargo else 0
    pj = cargo.get("partidos", 0)
    return {"dt": dt, "estilo_nombre": ETIQUETA_ESTILO.get((dt or {}).get("estilo"), "—"), "cargo": cargo, "actual": actual,
            "banco": [{**b, "estilo_nombre": ETIQUETA_ESTILO.get(b.get("estilo"), "")} for b in banco],
            "linea": linea, "anteriores": [x for x in linea if not x["vigente"]], "federacion": pais.get("federacion"), "riesgo": riesgo,
            "presion_nivel": "alta" if riesgo >= 25 else "media" if riesgo >= 8 else "baja",
            "puntos_pct": round(cargo.get("puntos", 0) / (3 * pj) * 100) if pj else 0,
            "sobre_esperado": round((cargo.get("puntos", 0) - cargo.get("esperados", 0)) / pj, 2) if pj else 0.0,
            "protegido": pj < MIN_PARTIDOS}


def ceses_del_partido(juego_id: str) -> List[dict]:
    """Los técnicos que su federación cesó tras este partido, con quién los reemplazó (para el resumen /juegos/{id})."""
    salida = []
    for c in db["dt_cargos"].find({"hasta_juego": str(juego_id), "motivo_fin": "CESE"}, {"juegos": 0}):
        pais = db["paises"].find_one({"id": c["pais_id"]}, {"_id": 0, "id": 1, "nombre": 1, "bandera": 1, "federacion": 1}) or {}
        nuevo = db["dt_cargos"].find_one({"pais_id": c["pais_id"], "desde_juego": str(juego_id), "motivo_inicio": "REEMPLAZO"}, {"juegos": 0}) or {}
        sale = db["directores_tecnicos"].find_one({"id": c["dt_id"]}, {"_id": 0}) or {}
        entra = db["directores_tecnicos"].find_one({"id": nuevo.get("dt_id")}, {"_id": 0}) or {} if nuevo else {}
        pj = c.get("partidos", 0)
        salida.append({
            "pais_id": c["pais_id"], "pais": pais.get("nombre"), "bandera": pais.get("bandera"),
            "federacion": pais.get("federacion") or f"La federación de {pais.get('nombre', '')}",
            "por_eliminacion": bool(c.get("cese_por_eliminacion")),
            "sale": {"id": c["dt_id"], "nombre": c.get("dt_nombre") or sale.get("nombre"), "partidos": pj,
                     "record": f'{c.get("ganados", 0)}-{c.get("empatados", 0)}-{c.get("perdidos", 0)}',
                     "sobre": round((c.get("puntos", 0) - c.get("esperados", 0)) / pj, 2) if pj else 0.0,
                     "desde": fecha_corta(c.get("desde_fecha_juego")), "arquetipo": arquetipo(sale)["titulo"] if sale else ""},
            "entra": ({"id": nuevo["dt_id"], "nombre": nuevo.get("dt_nombre") or entra.get("nombre"), "regreso": bool(nuevo.get("regreso")),
                       "edad": entra.get("edad"), "arquetipo": arquetipo(entra)["titulo"] if entra else ""} if nuevo else None),
        })
    return salida
