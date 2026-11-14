"""Premios del Mundial: servicio con Mongo (lógica de mérito y votación en services/premios.py; reglas en config/premios.py).

Colección `premios_mundial` (PERMANENTE: el Palmarés guarda cada edición; `restart_mundial` la borra junto con `mundiales`): una por Mundial y categoría
{_id "<mundial_id>:<categoria>", mundial_id, anio, categoria, ganador, finalistas, votantes, curiosidades, otorgado_en}. Se otorgan al cerrar el Mundial
(`update_data_mundial`, tras marcar al campeón; idempotente, nunca lanza). Mientras el torneo sigue, `carrera_actual()` muestra quién lidera cada categoría
por mérito (sin votar). Las notas de la prensa son notas `PREMIO` en `prensa` ancladas a la Gran Final, con valoración positiva sobre el ganador (reputación).
"""
import logging
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo import UpdateOne

from config import premios as CP
from services import premios as PR
from services import prensa as P
from services import prensa_service as PS

logger = logging.getLogger(__name__)
db = PS.db
COL = "premios_mundial"
_cache: Dict[str, Any] = {"clave": None, "datos": None, "hasta": 0.0}


def _partidos_copa(mundial_id: str) -> List[dict]:
    return list(db["juegos"].find(
        {"mundial_id": mundial_id, "estado": "finalizado", "fase_id": {"$gte": CP.FASE_COPA}, "transmision.estado": {"$ne": "in_progress"}},
        {"fase_id": 1, "equipo_local.id": 1, "equipo_local.nombre": 1, "equipo_visitante.id": 1, "equipo_visitante.nombre": 1, "resultado.goles_local": 1,
         "resultado.goles_visitante": 1, "resultado.calificaciones": 1, "resultado.goleadores": 1, "resultado.atajadores": 1, "resultado.dt": 1, "resultado.arbitros": 1,
         "resultado.eventos.tipo": 1, "resultado.eventos.equipo": 1, "resultado.cronica.historia": 1, "fecha": 1}))


def _pool(mundial_id: str) -> Dict[str, List[dict]]:
    """Candidatos de cada categoría con sus números de la Copa (fase >= FASE_COPA)."""
    juegos = _partidos_copa(mundial_id)
    ids = {int(k) for j in juegos for k in ((j.get("resultado") or {}).get("calificaciones") or {})}
    info = {d["id"]: d for d in db["jugadores"].find({"id": {"$in": list(ids)}}, {"_id": 0, "id": 1, "nombre": 1, "edad": 1, "posicion_id": 1, "pais_id": 1, "leyenda": 1})}
    jug: Dict[int, dict] = {}
    equipos: Dict[int, dict] = {}   # juego limpio: sanciones por selección
    partidos_lista: List[dict] = []   # partido del Mundial
    dts: Dict[int, dict] = {}
    centrales: Dict[str, dict] = {}
    for j in juegos:
        r = j.get("resultado") or {}
        gl, gv = r.get("goles_local") or 0, r.get("goles_visitante") or 0
        local, visita = j["equipo_local"], j["equipo_visitante"]
        recibidos = {local["id"]: gv, visita["id"]: gl}
        for k, rating in (r.get("calificaciones") or {}).items():
            d = info.get(int(k))
            if not d or d.get("leyenda") or not rating:
                continue
            a = jug.setdefault(d["id"], {"id": d["id"], "nombre": d["nombre"], "pais_id": d.get("pais_id"), "edad": d.get("edad"), "posicion_id": d.get("posicion_id"),
                                         "suma": 0.0, "partidos": 0, "goles": 0, "atajadas": 0, "vallas": 0})
            a["suma"] += rating
            a["partidos"] += 1
            if d.get("posicion_id") == 1 and recibidos.get(d.get("pais_id")) == 0:
                a["vallas"] += 1
        for g in r.get("goleadores") or []:
            if g.get("jugador_id") in jug:
                jug[g["jugador_id"]]["goles"] += g.get("goles", 0) or 0
        for g in r.get("atajadores") or []:
            if g.get("jugador_id") in jug:
                jug[g["jugador_id"]]["atajadas"] += g.get("atajadas", 0) or 0
        tarjetas = {local["nombre"]: 0, visita["nombre"]: 0}
        for e in r.get("eventos") or []:
            t, eq_nombre = e.get("tipo") or "", e.get("equipo")
            if eq_nombre in tarjetas:
                tarjetas[eq_nombre] += CP.PUNTOS_TARJETA["DOBLE"] if "DOBLE AMARILLA" in t else (CP.PUNTOS_TARJETA["ROJA"] if "TARJETA ROJA" in t else (CP.PUNTOS_TARJETA["AMARILLA"] if "TARJETA AMARILLA" in t else 0))
        for eq in (local, visita):
            a = equipos.setdefault(eq["id"], {"id": eq["id"], "nombre": eq["nombre"], "pais_id": eq["id"], "partidos": 0, "sanciones": 0})
            a["partidos"] += 1
            a["sanciones"] += tarjetas.get(eq["nombre"], 0)
        historia = ((r.get("cronica") or {}).get("historia")) or None
        partidos_lista.append({"id": str(j["_id"]), "nombre": f"{local['nombre']} {gl}-{gv} {visita['nombre']}", "pais_id": None, "partidos": 1, "goles": gl + gv, "goles_totales": gl + gv,
                               "historia": historia, "drama": CP.HISTORIA_DRAMA.get(historia, (0.0, ""))[0], "historia_nombre": CP.HISTORIA_DRAMA.get(historia, (0.0, ""))[1], "eliminacion": (j.get("fase_id") or 0) >= 8, "fecha": j.get("fecha")})
        for lado, eq, gf, gc in (("local", local, gl, gv), ("visita", visita, gv, gl)):
            dt = (r.get("dt") or {}).get(lado) or {}
            if dt.get("id") is None:
                continue
            a = dts.setdefault(dt["id"], {"id": dt["id"], "nombre": dt.get("nombre", "?"), "pais_id": eq["id"], "partidos": 0, "puntos": 0, "dif": 0, "fase_max": CP.FASE_COPA})
            a["partidos"] += 1
            a["puntos"] += 3 if gf > gc else (1 if gf == gc else 0)
            a["dif"] += gf - gc
            a["fase_max"] = max(a["fase_max"], j.get("fase_id") or CP.FASE_COPA)
        central = (r.get("arbitros") or {}).get("central") if isinstance(r.get("arbitros"), dict) else None
        if central:
            c = centrales.setdefault(central, {"nombre": central, "partidos": 0, "juegos": []})
            c["partidos"] += 1
            c["juegos"].append(str(j["_id"]))
    jugadores = []
    for a in jug.values():
        a["rating"] = a["suma"] / a["partidos"]
        jugadores.append(a)
    # árbitros: id y polémicas del central en sus partidos
    out_arb = []
    if centrales:
        docs = {d["nombre"]: d for d in db["arbitros"].find({"nombre": {"$in": list(centrales)}, "puesto": "Arbitro central"}, {"id": 1, "nombre": 1, "pais_id": 1})}
        from services.polemicas_service import puntaje_actual
        for nombre, c in centrales.items():
            d = docs.get(nombre)
            if not d:
                continue
            pol = sum(1 for p in db["polemicas"].find({"_id": {"$in": c["juegos"]}}, {"items": 1}) for it in p.get("items") or [] if it.get("arbitro_id") == d["id"])
            out_arb.append({"id": d["id"], "nombre": nombre, "pais_id": d.get("pais_id"), "partidos": c["partidos"], "polemicas": pol, "reputacion": puntaje_actual(d["id"]) or 0})
    return {"jugador": [a for a in jugadores if a.get("posicion_id") != 1], "portero": [a for a in jugadores if a.get("posicion_id") == 1],
            "joven": [a for a in jugadores if (a.get("edad") or 99) <= CP.EDAD_JOVEN], "tecnico": list(dts.values()), "arbitro": out_arb,
            "goleador": [a for a in jugadores if a["goles"] > 0], "juego_limpio": list(equipos.values()), "partido": partidos_lista}


def _mundial_activo() -> Optional[dict]:
    return db["mundiales"].find_one({"activo": True})


# --- La carrera (antes del cierre) -----------------------------------------------------------------------------------------
def carrera_actual() -> Optional[List[dict]]:
    """[{categoria, nombre, icono, color, candidatos: [top 3 por mérito]}] del Mundial en curso; None si no hay partidos de la Copa. Caché de 60 s."""
    m = _mundial_activo()
    if not m:
        return None
    mid = str(m["_id"])
    if _cache["clave"] == mid and _cache["hasta"] > time.time():
        return _cache["datos"]
    try:
        pool = _pool(mid)
    except Exception as e:
        logger.error(f"Premios: carrera: {e}")
        return None
    filas = []
    for cat, meta in CP.CATEGORIAS.items():
        cands = PR.candidatos(cat, pool[cat])[:3]
        if cands:
            filas.append({"categoria": cat, **meta, "candidatos": [{"id": c["id"], "nombre": c["nombre"], "pais_id": c.get("pais_id"), "merito": c["merito"], "partidos": c["partidos"],
                                                                      "detalle": _detalle(cat, c)} for c in cands]})
    datos = filas or None
    _cache.update(clave=mid, datos=datos, hasta=time.time() + 60)
    return datos


def _detalle(cat: str, c: dict) -> str:
    if cat in ("jugador", "joven"):
        return f"{c['rating']:.2f} de calificación · {c['goles']} gol{'es' if c['goles'] != 1 else ''}"
    if cat == "portero":
        return f"{c['rating']:.2f} de calificación · {c['atajadas']} atajadas · {c['vallas']} valla{'s' if c['vallas'] != 1 else ''} invicta{'s' if c['vallas'] != 1 else ''}"
    if cat == "tecnico":
        return f"{c['puntos']} puntos en {c['partidos']} partidos · dif. {c['dif']:+d}"
    if cat == "goleador":
        return f"{c['goles']} gol{'es' if c['goles'] != 1 else ''} en {c['partidos']} partido{'s' if c['partidos'] != 1 else ''}"
    if cat == "juego_limpio":
        return f"{c['sanciones']} punto{'s' if c['sanciones'] != 1 else ''} de sanción en {c['partidos']} partido{'s' if c['partidos'] != 1 else ''}"
    if cat == "partido":
        return f"{c['goles_totales']} gol{'es' if c['goles_totales'] != 1 else ''}" + (f" · {c['historia_nombre']}" if c.get("historia_nombre") else "")
    return f"{c['partidos']} partido{'s' if c['partidos'] != 1 else ''} · {c['polemicas']} polémica{'s' if c['polemicas'] != 1 else ''}"


# --- El cierre ---------------------------------------------------------------------------------------------------------------
def asegurar_premios(mundial_id) -> int:
    """Vota y guarda los premios del Mundial (idempotente). Se llama al marcar al campeón. Nunca lanza."""
    try:
        mid = str(mundial_id)
        if db[COL].count_documents({"mundial_id": mid}, limit=1):
            return 0
        m = db["mundiales"].find_one({"_id": ObjectId(mid)}) or {}
        pool = _pool(mid)
        medios = PS.medios()
        final = db["juegos"].find_one({"mundial_id": mid, "fase_id": 13, "estado": "finalizado"}, {"fecha": 1, "hora": 1})
        docs, notas = [], []
        for cat, meta in CP.CATEGORIAS.items():
            cands = PR.candidatos(cat, pool[cat])
            res = PR.resultado_directo(cat, cands) if meta.get("directo") else PR.resultado(cat, cands, PR.votar(cat, cands, medios, f"premios:{mid}"))
            if not res:
                continue
            por_id = {c["id"]: c for c in cands}
            for x in [res["ganador"]] + res["finalistas"]:
                x["detalle"] = _detalle(cat, por_id[x["id"]])
            docs.append({"_id": f"{mid}:{cat}", "mundial_id": mid, "anio": m.get("anio"), "otorgado_en": datetime.utcnow(), **res})
            g = res["ganador"]
            if final and medios:
                medio = next((x for x in medios if x.get("pais_id") is None), medios[0])
                per = medio["equipo"]["periodistas"][0]
                titular = f"{meta['nombre']}: {g['nombre']}."
                notas.append({"_id": f"{mid}:{cat}:premio", "juego_id": str(final["_id"]), "fecha": final.get("fecha"), "hora": final.get("hora"), "medio_id": medio["id"],
                              "medio": {"nombre": medio["nombre"], "slug": medio["slug"], "papel": medio["papel"], "linea": medio["linea"], "pais_id": medio.get("pais_id")},
                              "periodista": {"nombre": per["nombre"], "rol": per["rol"], "estilo": per["estilo"], "sesgo": per["sesgo"]},
                              "tipo": "PREMIO", "tono": CP.VALOR_REPUTACION, "categoria_tono": "elogio", "titular": titular,
                              "texto": (f"{titular} {g['detalle']}." if meta.get("directo") else f"{titular} El jurado de {res['votantes']} medios lo eligió con {g['puntos']} puntos.")
                                       + (f" {res['curiosidades'][0]}" if res["curiosidades"] else ""),
                              "valoraciones": [{"tipo": meta["tipo"], "id": g["id"], "nombre": g["nombre"], "valor": CP.VALOR_REPUTACION}] if meta["tipo"] else [], "peso": 1.5, "rol_cobertura": "interesado",
                              "creado_en": datetime.utcnow()})
        if docs:
            db[COL].insert_many(docs, ordered=False)
        if notas:
            res = db[PS.COL].bulk_write([UpdateOne({"_id": x["_id"]}, {"$setOnInsert": x}, upsert=True) for x in notas], ordered=False)
            nuevas = [x for x in notas if x["_id"] in set(res.upserted_ids.values())]
            if nuevas:
                PS.actualizar_reputacion(nuevas)
        return len(docs)
    except Exception as e:
        print(f"[premios] no se pudieron otorgar: {e}")
        return 0


# --- Vistas ----------------------------------------------------------------------------------------------------------------------
def vista_palmares() -> Dict[str, Any]:
    """{carrera: [...] | None, otorgados: [{anio, premios: [...]}]} para el Palmarés."""
    docs = list(db[COL].find({}).sort([("anio", -1)]))
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1})}
    por_anio: Dict[Any, List[dict]] = defaultdict(list)
    for d in docs:
        meta = CP.CATEGORIAS.get(d["categoria"], {})
        def pub(x):
            return {**x, "pais": (paises.get(x.get("pais_id")) or {}).get("nombre", ""), "bandera": (paises.get(x.get("pais_id")) or {}).get("bandera", "")}
        por_anio[d.get("anio")].append({"categoria": d["categoria"], "nombre": meta.get("nombre", d["categoria"]), "icono": meta.get("icono", "bi-award-fill"), "color": meta.get("color", "#eab308"),
                                        "tipo": meta.get("tipo"), "ganador": pub(d["ganador"]), "finalistas": [pub(f) for f in d.get("finalistas") or []], "votantes": d.get("votantes"),
                                        "curiosidades": d.get("curiosidades") or []})
    otorgados = [{"anio": a, "premios": sorted(v, key=lambda x: list(CP.CATEGORIAS).index(x["categoria"]) if x["categoria"] in CP.CATEGORIAS else 99)} for a, v in por_anio.items()]
    carrera = None
    m = _mundial_activo()
    if m and not db[COL].count_documents({"mundial_id": str(m["_id"])}, limit=1):
        carrera = carrera_actual()
        for fila in carrera or []:
            for c in fila["candidatos"]:
                p = paises.get(c.get("pais_id")) or {}
                c["pais"], c["bandera"] = p.get("nombre", ""), p.get("bandera", "")
    return {"carrera": carrera, "otorgados": otorgados}


def premios_de(tipo: str, ref) -> List[dict]:
    """Premios ganados por un jugador, técnico o árbitro ([{nombre, anio, icono}]) para sus fichas."""
    try:
        cats = [c for c, m in CP.CATEGORIAS.items() if m["tipo"] == tipo]
        return [{"nombre": CP.CATEGORIAS[d["categoria"]]["nombre"], "anio": d.get("anio"), "icono": CP.CATEGORIAS[d["categoria"]]["icono"]}
                for d in db[COL].find({"categoria": {"$in": cats}, "ganador.id": ref})]
    except Exception:
        return []


def limpiar() -> None:
    db[COL].delete_many({})
