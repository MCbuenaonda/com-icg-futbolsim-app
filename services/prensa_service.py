"""
Prensa (Mongo): arma el contexto de un partido terminado, deja que services/prensa.py decida qué medios opinan y qué dicen, y
guarda las publicaciones en la colección `prensa` (una por medio y partido, _id = juego:medio). El contenido es GLOBAL (igual
para todos los usuarios, como la crónica); los efectos por universo (reputación, marcas, entrevistas) van aparte.

  prensa = {_id, juego_id, fecha, hora, medio_id, medio {nombre, slug, papel, linea, pais_id}, periodista {nombre, rol, estilo, sesgo},
            tipo PARTIDO|OPINION|JUGADOR|DT, tono -1..1, categoria_tono, titular, texto, valoraciones [{tipo, id, nombre, valor}]}

`asegurar_prensa(juego)` es idempotente y nunca lanza: se llama al terminar el partido (gancho de juegos_service) y desde
generar_prensa.py para los ya jugados. No corre mientras el partido sigue en transmisión (no spoilea).
"""
import time
from datetime import datetime
from typing import Dict, List, Optional

from pymongo import MongoClient
import certifi

from config.settings import MONGODB_URI
from services import prensa as P

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database("mundial")
COL = "prensa"
_cache_medios = {"hasta": 0.0, "lista": []}


def medios() -> List[dict]:
    if _cache_medios["hasta"] < time.time():
        _cache_medios["lista"] = list(db["medios"].find({}, {"_id": 0}))
        _cache_medios["hasta"] = time.time() + 600
    return _cache_medios["lista"]


def contexto(j: dict) -> dict:
    r = j.get("resultado") or {}
    lado = {}
    for k, eq, gol in (("local", "equipo_local", "goles_local"), ("visita", "equipo_visitante", "goles_visitante")):
        e = j[eq]
        lado[k] = {"id": e["id"], "nombre": e["nombre"], "goles": r.get(gol) or 0, "rankin": e.get("rankin"), "confederacion_id": e.get("confederacion_id")}
    dts = r.get("dt") or {}
    for k in ("local", "visita"):
        lado[k]["dt"] = (dts.get(k) or {}).get("nombre")
        lado[k]["dt_id"] = (dts.get(k) or {}).get("id")
    gl, gv = lado["local"]["goles"], lado["visita"]["goles"]
    ganador = "local" if gl > gv else ("visita" if gv > gl else None)
    if r.get("ganador_lado") in ("L", "V"):   # eliminación directa: manda quien avanzó (penales)
        ganador = "local" if r["ganador_lado"] == "L" else "visita"
    # calificaciones por jugador -> figura y peor del partido de cada lado
    cal = {int(k): v for k, v in (r.get("calificaciones") or {}).items()}
    ids = list(cal)
    info = {x["id"]: x for x in db["jugadores"].find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "nombre": 1, "pais_id": 1, "estado_animo": 1})}
    por_lado = {"local": [], "visita": []}
    for pid, rating in cal.items():
        x = info.get(pid)
        if x and rating:
            por_lado["local" if x["pais_id"] == lado["local"]["id"] else "visita"].append({"id": pid, "nombre": x["nombre"], "rating": round(rating, 1), "animo": x.get("estado_animo")})
    for k in ("local", "visita"):
        lista = sorted(por_lado[k], key=lambda x: -x["rating"])
        lado[k]["figura"] = lista[0] if lista else None
        lado[k]["peor"] = lista[-1] if lista else None
    est = j.get("estadisticas") or {}
    for k, ek in (("local", "local"), ("visita", "visitante")):
        s = est.get(ek) or {}
        lado[k]["tiros"] = s.get("tiros_totales", 0)
        lado[k]["pos"] = round(s.get("p_posesion", 50))
        i = db["internacional"].find_one({"id": lado[k]["id"]}, {"estadisticas.puntos": 1, "estadisticas.goles_favor": 1}) or {}
        lado[k]["pts"] = (i.get("estadisticas") or {}).get("puntos", 0)
        lado[k]["gf"] = (i.get("estadisticas") or {}).get("goles_favor", 0)
    sorpresa = False
    if ganador:
        g, p = lado[ganador], lado["visita" if ganador == "local" else "local"]
        sorpresa = bool(g.get("rankin") and p.get("rankin") and g["rankin"] > p["rankin"] + 30)
    return {"juego_id": str(j["_id"]), "fecha": j.get("fecha"), "hora": j.get("hora"), "local": lado["local"], "visita": lado["visita"],
            "ganador": ganador, "dif": gl - gv, "eliminacion": (j.get("fase_id") or 0) >= 8, "historia": (r.get("cronica") or {}).get("historia"),
            "sorpresa": sorpresa, "tag": j.get("tag")}


TIPO_PESOS = {"deportivo": {"PARTIDO": 0.35, "JUGADOR": 0.35, "OPINION": 0.15, "DT": 0.15},
              "generalista": {"PARTIDO": 0.4, "OPINION": 0.3, "JUGADOR": 0.15, "DT": 0.15},
              "interesado": {"JUGADOR": 0.4, "OPINION": 0.35, "PARTIDO": 0.25}}
ROL_DE_TIPO = {"PARTIDO": ["reportero"], "OPINION": ["columnista"], "DT": ["columnista"], "JUGADOR": ["reportero", "entrevistador"]}


def _publicacion(ctx: dict, medio: dict, rol: str, rng) -> Optional[dict]:
    medio = dict(medio, credibilidad=credibilidad_actual(medio))   # lo que pesa un medio depende de cuánto acierta
    clave = "interesado" if rol == "interesado" else medio["papel"] if medio["papel"] in TIPO_PESOS else "generalista"
    tipo = rng.choices(list(TIPO_PESOS[clave]), list(TIPO_PESOS[clave].values()))[0]
    periodistas = medio["equipo"]["periodistas"]
    candidatos = [p for p in periodistas if p["rol"] in ROL_DE_TIPO[tipo]] or periodistas
    per = rng.choice(candidatos)
    if rol == "interesado":
        lado = ctx["ganador"] or "local"
    else:
        lado = rol
    otro = "visita" if lado == "local" else "local"
    sujeto, rival = ctx[lado], ctx[otro]
    es_propio = medio.get("pais_id") == sujeto["id"]
    dif_sujeto = (sujeto["goles"] - rival["goles"]) if True else 0
    if ctx["ganador"] is None:
        resultado = 0.0
    else:
        resultado = (0.5 if ctx["ganador"] == lado else -0.5) + (0.1 * min(3, abs(ctx["dif"])) * (1 if ctx["ganador"] == lado else -1))
    jugador = None
    if tipo == "JUGADOR":
        jugador = sujeto["figura"] if resultado >= 0 else sujeto["peor"]
        if not jugador:
            tipo = "PARTIDO"
    if tipo == "JUGADOR":
        base = P.limitar((jugador["rating"] - 6.5) / 2.5)
        if medio["linea"] == "analitica":
            base = P.limitar(0.5 * base + 0.5 * resultado)
        valor = P.tono(base, medio, per, es_propio, animo=jugador.get("animo"))
    elif tipo == "DT" and not sujeto.get("dt"):
        tipo = "OPINION"
        valor = P.tono(resultado, medio, per, es_propio)
    elif tipo == "DT":
        valor = P.tono(resultado * 0.9, medio, per, es_propio, es_dt=True)
    else:
        valor = P.tono(resultado, medio, per, es_propio)
    datos = {"eq": sujeto["nombre"], "rival": rival["nombre"], "gl": sujeto["goles"], "gv": rival["goles"], "dt": sujeto.get("dt") or "su técnico",
             "tiros": sujeto["tiros"], "pos": sujeto["pos"], "pts": sujeto["pts"], "gf": sujeto["gf"], "dif": sujeto["goles"] - rival["goles"],
             "fig": (jugador or {}).get("nombre", ""), "rating": (jugador or {}).get("rating", "")}
    texto = P.redactar(tipo, valor, medio, per, datos, rng)
    if tipo == "JUGADOR":
        val = [{"tipo": "jugador", "id": jugador["id"], "nombre": jugador["nombre"], "valor": valor}]
    elif tipo == "DT":
        val = [{"tipo": "dt", "id": sujeto.get("dt_id"), "nombre": sujeto["dt"], "valor": valor}]
    else:
        val = [{"tipo": "pais", "id": sujeto["id"], "nombre": sujeto["nombre"], "valor": valor}]
    return {"_id": f"{ctx['juego_id']}:{medio['id']}", "juego_id": ctx["juego_id"], "fecha": ctx["fecha"], "hora": ctx["hora"], "medio_id": medio["id"],
            "medio": {"nombre": medio["nombre"], "slug": medio["slug"], "papel": medio["papel"], "linea": medio["linea"], "pais_id": medio.get("pais_id")},
            "periodista": {"nombre": per["nombre"], "rol": per["rol"], "estilo": per["estilo"], "sesgo": per["sesgo"]},
            "tipo": tipo, "tono": valor, **texto, "valoraciones": val, "peso": P.peso_medio(medio), "rol_cobertura": rol, "creado_en": datetime.utcnow()}


def generar(j: dict) -> List[dict]:
    """Las publicaciones del partido (sin guardar)."""
    ctx = contexto(j)
    rng = P.semilla("prensa", ctx["juego_id"])
    salida = []
    for medio, rol in P.elegir_medios(ctx, medios(), rng):
        pub = _publicacion(ctx, medio, rol, P.semilla("prensa", ctx["juego_id"], medio["id"]))
        if pub:
            salida.append(pub)
    return salida


def asegurar_prensa(j: Optional[dict], forzar: bool = False) -> int:
    """Escribe las publicaciones del partido si faltan. Idempotente; nunca lanza; no toca partidos en transmisión."""
    try:
        if not j or j.get("estado") != "finalizado" or (j.get("transmision") or {}).get("estado") == "in_progress" or not medios():
            return 0
        jid = str(j["_id"])
        if db[COL].count_documents({"juego_id": jid}, limit=1):
            if not forzar:
                return 0
            db[COL].delete_many({"juego_id": jid})
        pubs = generar(j)
        if pubs:
            db[COL].insert_many(pubs, ordered=False)
            if not forzar:   # con --forzar la reputación se reconstruye de una vez al final (generar_prensa.py)
                actualizar_reputacion(pubs)
        return len(pubs)
    except Exception as e:
        print(f"[prensa] no se pudo generar la prensa del partido: {e}")
        return 0


# --- Vistas ----------------------------------------------------------------------------------------------------------
LINEA_COLOR = {"sensacionalista": "#f43f5e", "analitica": "#38bdf8", "critica": "#f59e0b", "oficialista": "#a78bfa", "optimista": "#22c55e", "popular": "#fb923c"}
ETIQUETA = {"PARTIDO": ("Crónica", "bi-newspaper"), "OPINION": ("Opinión", "bi-chat-quote-fill"), "JUGADOR": ("Jugador", "bi-person-lines-fill"),
            "DT": ("Técnico", "bi-clipboard2-data")}
TONO_TEXTO = {"elogio": ("Elogia", "bi-hand-thumbs-up-fill"), "critica": ("Critica", "bi-hand-thumbs-down-fill"), "neutral": ("Neutral", "bi-dash-circle")}


def vista(d: dict) -> dict:
    """Una publicación lista para dibujar (la usan la red social, el resumen del partido y las fichas)."""
    import zlib
    h = zlib.crc32(d["_id"].encode())
    nombre_tono, icono_tono = TONO_TEXTO[d["categoria_tono"]]
    etiqueta, icono = ETIQUETA.get(d["tipo"], ("Nota", "bi-newspaper"))
    base = {3: 6000, 2: 2200, 4: 9000}.get(2 if d["medio"].get("pais_id") else 4, 2200)
    likes = int(base * (0.4 + (h % 1000) / 1000))
    from services.imagenes_pais_service import url_imagen_medios
    m = next((x for x in medios() if x["id"] == d["medio_id"]), {})
    per = next((p for p in (m.get("equipo") or {}).get("periodistas", []) if p["nombre"] == d["periodista"]["nombre"]), {})
    return {**{k: d[k] for k in ("tipo", "tono", "titular", "texto", "categoria_tono", "valoraciones", "fecha", "hora")},
            "periodista": {**d["periodista"], "avatar_url": url_imagen_medios(per.get("avatar"))},
            "clase": "prensa", "id": d["_id"], "juego_id": d["juego_id"], "medio_id": d["medio_id"],
            "medio": {**d["medio"], "color": LINEA_COLOR.get(d["medio"].get("linea"), "#94a3b8"), "logo": url_imagen_medios(m.get("logo"))},
            "etiqueta": etiqueta, "icono": icono, "tono_nombre": nombre_tono, "tono_icono": icono_tono, "orden": 0,
            "likes": likes, "reposts": likes // (7 + h % 5), "comentarios": likes // (13 + h % 9), "visualizaciones": likes * (12 + h % 9)}


def de_partido(juego_id: str, limite: int = 6) -> List[dict]:
    docs = list(db[COL].find({"juego_id": str(juego_id)}))
    docs.sort(key=lambda d: -abs(d["tono"]))
    return [vista(d) for d in docs[:limite]]


def sobre(tipo: str, ref, limite: int = 5) -> List[dict]:
    """Lo que dice la prensa de un jugador (id), una selección (id) o un técnico (id), lo más reciente primero."""
    try:
        campo = "id"
        docs = list(db[COL].find({"valoraciones": {"$elemMatch": {"tipo": tipo, campo: ref}}}).sort([("fecha", -1), ("hora", -1)]).limit(limite))
        return [vista(d) for d in docs]
    except Exception as e:
        print(f"[prensa] sobre {tipo} {ref}: {e}")
        return []


def buscar(q: str = "", cursor: Optional[tuple] = None, limite: int = 12) -> List[dict]:
    consulta: Dict = {}
    if q:
        import re
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        consulta["$or"] = [{"texto": rx}, {"medio.nombre": rx}, {"periodista.nombre": rx}, {"valoraciones.nombre": rx}]
    if cursor:
        fecha, hora = cursor
        corte = {"$or": [{"fecha": {"$lt": fecha}}, {"fecha": fecha, "hora": {"$lt": hora}}]}
        consulta = {"$and": [consulta, corte]} if consulta else corte
    docs = db[COL].find(consulta, {"creado_en": 0}).sort([("fecha", -1), ("hora", -1)]).limit(limite + 4)
    return [vista(d) for d in docs]


# --- Reputación mediática ---------------------------------------------------------------------------------------------
COL_REP = "prensa_reputacion"
_cache_rep = {"hasta": 0.0, "datos": {}}


def _clave(v: dict) -> Optional[str]:
    ref = v.get("id")
    return f"{v['tipo']}:{ref}" if ref is not None else None


def _agrupar(pubs: List[dict]) -> Dict[str, dict]:
    """{clave: {tipo, id, nombre, notas[tono×peso]}} de lo que dijeron las publicaciones de UN partido."""
    g: Dict[str, dict] = {}
    for p in pubs:
        for v in p["valoraciones"]:
            k = _clave(v)
            if k:
                g.setdefault(k, {"tipo": v["tipo"], "id": v["id"], "nombre": v["nombre"], "notas": []})["notas"].append(v["valor"] * p.get("peso", 1.0))
    return g


def actualizar_reputacion(pubs: List[dict]) -> None:
    """Suma al puntaje de cada persona o selección lo que dijo la prensa de un partido (bulk). Nunca lanza."""
    try:
        from pymongo import UpdateOne
        grupos = _agrupar(pubs)
        actuales = {d["_id"]: d for d in db[COL_REP].find({"_id": {"$in": list(grupos)}})}
        ops = []
        for k, g in grupos.items():
            previo = (actuales.get(k) or {}).get("puntaje", 0.0)
            ops.append(UpdateOne({"_id": k}, {"$set": {"tipo": g["tipo"], "id": g["id"], "nombre": g["nombre"], "puntaje": P.nuevo_puntaje(previo, g["notas"])},
                                              "$inc": {"notas": len(g["notas"])}}, upsert=True))
        if ops:
            db[COL_REP].bulk_write(ops, ordered=False)
            _cache_rep["hasta"] = 0.0
    except Exception as e:
        print(f"[prensa] reputación: {e}")


def reconstruir_reputacion() -> dict:
    """Recalcula TODA la reputación repasando las publicaciones en orden (por partido). Devuelve el promedio por tipo."""
    por_juego: Dict[str, List[dict]] = {}
    for d in db[COL].find({}, {"juego_id": 1, "fecha": 1, "hora": 1, "valoraciones": 1, "peso": 1}).sort([("fecha", 1), ("hora", 1)]).allow_disk_use(True):
        por_juego.setdefault(d["juego_id"], []).append(d)
    estado: Dict[str, dict] = {}
    for pubs in por_juego.values():
        for k, g in _agrupar(pubs).items():
            e = estado.setdefault(k, {"tipo": g["tipo"], "id": g["id"], "nombre": g["nombre"], "puntaje": 0.0, "notas": 0})
            e["puntaje"] = P.nuevo_puntaje(e["puntaje"], g["notas"])
            e["notas"] += len(g["notas"])
    db[COL_REP].delete_many({})
    if estado:
        db[COL_REP].insert_many([{"_id": k, **v} for k, v in estado.items()], ordered=False)
    _cache_rep["hasta"] = 0.0
    medias: Dict[str, list] = {}
    for e in estado.values():
        medias.setdefault(e["tipo"], []).append(e["puntaje"])
    return {t: round(sum(v) / len(v), 1) for t, v in medias.items()}


def reputaciones() -> Dict[str, float]:
    """{'pais:62': puntaje, ...} cacheado 60 s."""
    if _cache_rep["hasta"] < time.time():
        _cache_rep["datos"] = {d["_id"]: d["puntaje"] for d in db[COL_REP].find({}, {"puntaje": 1})}
        _cache_rep["hasta"] = time.time() + 60
    return _cache_rep["datos"]


def reputacion_centrada(tipo: str, ref) -> float:
    """Reputación de alguien (−100..100) menos la media de su tipo; 0 si la prensa no ha hablado de él."""
    if ref is None:
        return 0.0
    puntaje = reputaciones().get(f"{tipo}:{ref}")
    return 0.0 if puntaje is None else P.centrado(tipo, puntaje)


def reputacion_de(tipo: str, ref) -> Optional[dict]:
    """Para las fichas: {puntaje, centrada, etiqueta, color} o None si nunca ha salido en la prensa."""
    puntaje = reputaciones().get(f"{tipo}:{ref}") if ref is not None else None
    if puntaje is None:
        return None
    c = P.centrado(tipo, puntaje)
    return {"puntaje": round(puntaje), "centrada": round(c), "etiqueta": P.etiqueta_reputacion(c),
            "color": "#4ade80" if c >= 8 else ("#f87171" if c <= -8 else "#94a3b8")}


# --- Pronósticos y credibilidad ------------------------------------------------------------------------------------------
COL_PRON = "prensa_pronosticos"
PRONOSTICOS_HORIZONTE = 3   # se pronostican los próximos 3 partidos (como los invitados de TV)
K_CREDIBILIDAD = 10         # partidos «virtuales» de la credibilidad inicial: con pocos pronósticos casi no se mueve
_cache_cred = {"hasta": 0.0, "datos": {}}


def _stats_medios() -> Dict[int, dict]:
    if _cache_cred["hasta"] < time.time():
        res: Dict[int, dict] = {}
        for d in db[COL_PRON].find({"estado": {"$in": ["acertado", "fallado"]}}, {"medio_id": 1, "estado": 1, "exacto": 1}):
            r = res.setdefault(d["medio_id"], {"total": 0, "aciertos": 0, "exactos": 0})
            r["total"] += 1
            r["aciertos"] += d["estado"] == "acertado"
            r["exactos"] += bool(d.get("exacto"))
        _cache_cred.update(hasta=time.time() + 60, datos=res)
    return _cache_cred["datos"]


def credibilidad_actual(medio: dict) -> float:
    """La credibilidad base del medio, movida hasta ±0,3 por su acierto (acertar la mitad no la cambia)."""
    r = _stats_medios().get(medio["id"])
    base = medio.get("credibilidad", 0.6)
    if not r:
        return base
    peso = r["total"] / (r["total"] + K_CREDIBILIDAD)   # con pocos pronósticos casi no se mueve
    return round(max(0.2, min(0.95, base + (r["aciertos"] / r["total"] - 0.5) * 0.6 * peso)), 3)


def generar_pronosticos() -> int:
    """Pronósticos de los próximos PRONOSTICOS_HORIZONTE partidos que aún no los tienen (idempotente; nunca lanza)."""
    try:
        from services.asistente_reglas import probabilidades_partido
        proximos = list(db["juegos"].find({"estado": "creado"}, {"equipo_local": 1, "equipo_visitante": 1, "fecha": 1, "hora": 1, "fase_id": 1})
                        .sort([("fecha", 1), ("hora", 1)]).limit(PRONOSTICOS_HORIZONTE))
        nuevos = 0
        for j in proximos:
            jid = str(j["_id"])
            if db[COL_PRON].count_documents({"juego_id": jid}, limit=1) or not medios():
                continue
            ids = [j["equipo_local"]["id"], j["equipo_visitante"]["id"]]
            poder = {x["id"]: (x.get("estadisticas") or {}).get("poder", 0.0) for x in db["internacional"].find({"id": {"$in": ids}}, {"id": 1, "estadisticas.poder": 1})}
            probs = probabilidades_partido(poder.get(ids[0], 0.0), poder.get(ids[1], 0.0))
            ctx = {"local": {"id": ids[0], "confederacion_id": j["equipo_local"].get("confederacion_id")}, "visita": {"id": ids[1], "confederacion_id": j["equipo_visitante"].get("confederacion_id")},
                   "dif": 0, "eliminacion": (j.get("fase_id") or 0) >= 8, "historia": None, "sorpresa": False}
            rng = P.semilla("pronostico", jid)
            docs = []
            for medio, rol in P.elegir_medios(ctx, medios(), rng):
                r2 = P.semilla("pronostico", jid, medio["id"])
                per = r2.choice([p for p in medio["equipo"]["periodistas"] if p["rol"] in ("columnista", "reportero")] or medio["equipo"]["periodistas"])
                pr = P.pronostico(medio, per, probs, rol if rol in ("local", "visita") else None, r2)
                docs.append({"_id": f"{jid}:{medio['id']}", "juego_id": jid, "fecha": j.get("fecha"), "hora": j.get("hora"), "medio_id": medio["id"],
                             "medio": {"nombre": medio["nombre"], "slug": medio["slug"], "linea": medio["linea"], "pais_id": medio.get("pais_id")},
                             "periodista": {"nombre": per["nombre"], "rol": per["rol"], "estilo": per["estilo"], "sesgo": per["sesgo"]},
                             **pr, "texto": P.texto_pronostico(pr["pick"], pr["marcador"], j["equipo_local"]["nombre"], j["equipo_visitante"]["nombre"], r2),
                             "estado": "pendiente", "creado_en": datetime.utcnow()})
            if docs:
                db[COL_PRON].insert_many(docs, ordered=False)
                nuevos += len(docs)
        return nuevos
    except Exception as e:
        print(f"[prensa] pronósticos: {e}")
        return 0


def resolver_pronosticos(j: Optional[dict]) -> int:
    """Marca como acertados o fallados los pronósticos de un partido terminado (y si dieron el marcador exacto)."""
    try:
        if not j or j.get("estado") != "finalizado":
            return 0
        r = j.get("resultado") or {}
        gl, gv = r.get("goles_local") or 0, r.get("goles_visitante") or 0
        real = {"L": "L", "V": "V"}.get(r.get("ganador_lado")) or ("L" if gl > gv else "V" if gv > gl else "E")
        n = 0
        for d in db[COL_PRON].find({"juego_id": str(j["_id"]), "estado": "pendiente"}):
            ok = d["pick"] == real
            db[COL_PRON].update_one({"_id": d["_id"], "estado": "pendiente"}, {"$set": {"estado": "acertado" if ok else "fallado", "real": real, "marcador_real": [gl, gv],
                                                                                          "exacto": bool(ok and list(d["marcador"]) == [gl, gv])}})
            n += 1
        if n:
            _cache_cred["hasta"] = 0.0
        return n
    except Exception as e:
        print(f"[prensa] resolver pronósticos: {e}")
        return 0


def pronosticos_de_partido(juego_id: str) -> List[dict]:
    docs = list(db[COL_PRON].find({"juego_id": str(juego_id)}, {"creado_en": 0}))
    for d in docs:
        d["color"] = LINEA_COLOR.get(d["medio"].get("linea"), "#94a3b8")
        d["pick_nombre"] = {"L": "Local", "E": "Empate", "V": "Visita"}[d["pick"]]
    docs.sort(key=lambda d: (d["estado"] == "pendiente", d["medio"]["nombre"]))
    return docs


def ranking() -> dict:
    """Medios y periodistas por acierto (solo con pronósticos ya resueltos) y los últimos pronósticos."""
    por_medio: Dict[int, dict] = {}
    por_per: Dict[str, dict] = {}
    for d in db[COL_PRON].find({"estado": {"$in": ["acertado", "fallado"]}}):
        for tabla, clave, nombre in ((por_medio, d["medio_id"], d["medio"]["nombre"]), (por_per, f"{d['periodista']['nombre']}|{d['medio']['nombre']}", d["periodista"]["nombre"])):
            r = tabla.setdefault(clave, {"nombre": nombre, "medio": d["medio"]["nombre"], "linea": d["medio"].get("linea"), "total": 0, "aciertos": 0, "exactos": 0})
            r["total"] += 1
            r["aciertos"] += d["estado"] == "acertado"
            r["exactos"] += bool(d.get("exacto"))
    base = {m["id"]: m for m in medios()}
    filas_m = []
    for mid, r in por_medio.items():
        m = base.get(mid, {})
        filas_m.append({**r, "pct": round(100 * r["aciertos"] / r["total"]), "credibilidad": round(credibilidad_actual(m) * 100) if m else None,
                        "pais": m.get("pais"), "color": LINEA_COLOR.get(r["linea"], "#94a3b8")})
    filas_p = [{**r, "pct": round(100 * r["aciertos"] / r["total"]), "color": LINEA_COLOR.get(r["linea"], "#94a3b8")} for r in por_per.values() if r["total"] >= 2]
    recientes = [dict(d, color=LINEA_COLOR.get(d["medio"].get("linea"), "#94a3b8")) for d in db[COL_PRON].find({}, {"creado_en": 0}).sort([("fecha", -1), ("hora", -1)]).limit(30)]
    for d in recientes:
        d["pick_nombre"] = {"L": "Local", "E": "Empate", "V": "Visita"}[d["pick"]]
    return {"medios": sorted(filas_m, key=lambda x: (-x["pct"], -x["total"])), "periodistas": sorted(filas_p, key=lambda x: (-x["pct"], -x["total"]))[:30],
            "recientes": recientes, "resueltos": sum(r["total"] for r in por_medio.values())}


# --- Directorio de medios ---------------------------------------------------------------------------------------------
CONFEDERACIONES = {1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC"}
NIVEL_NOMBRE = {2: "Nacional", 3: "Continental", 4: "Global"}


def _medio_vista(m: dict, stats: Optional[dict] = None) -> dict:
    from config import medios as CM
    from services.imagenes_pais_service import url_imagen_medios
    r = (stats or _stats_medios()).get(m["id"]) or {"total": 0, "aciertos": 0, "exactos": 0}
    return {"id": m["id"], "nombre": m["nombre"], "slug": m["slug"], "logo": url_imagen_medios(m.get("logo")), "papel": m["papel"],
            "papel_nombre": CM.PAPEL_NOMBRE.get(m["papel"], m["papel"]), "nivel": m["nivel"], "nivel_nombre": NIVEL_NOMBRE.get(m["nivel"], ""),
            "pais_id": m.get("pais_id"), "pais": m.get("pais") or ("Internacional"), "confederacion_id": m.get("confederacion_id"),
            "confederacion": CONFEDERACIONES.get(m.get("confederacion_id"), ""), "linea": m["linea"], "linea_nombre": m["linea_nombre"],
            "linea_texto": m["linea_texto"], "color": LINEA_COLOR.get(m["linea"], "#94a3b8"), "credibilidad_base": round(m.get("credibilidad", 0.6) * 100),
            "credibilidad": round(credibilidad_actual(m) * 100), "pronosticos": r["total"], "aciertos": r["aciertos"], "exactos": r["exactos"],
            "pct": round(100 * r["aciertos"] / r["total"]) if r["total"] else None}


def directorio() -> List[dict]:
    stats = _stats_medios()
    return sorted((_medio_vista(m, stats) for m in medios()), key=lambda x: (-x["nivel"], x["pais"], x["nombre"]))


def ficha_medio(medio_id: int) -> Optional[dict]:
    from services.imagenes_pais_service import url_imagen_medios
    m = next((x for x in medios() if x["id"] == int(medio_id)), None)
    if not m:
        return None
    v = _medio_vista(m)
    eq = m["equipo"]
    d = eq["director"]
    notas = [vista(x) for x in db[COL].find({"medio_id": m["id"]}).sort([("fecha", -1), ("hora", -1)]).limit(6)]
    pron = list(db[COL_PRON].find({"medio_id": m["id"]}, {"creado_en": 0}).sort([("fecha", -1), ("hora", -1)]).limit(6))
    for x in pron:
        x["pick_nombre"] = {"L": "Local", "E": "Empate", "V": "Visita"}[x["pick"]]
    return {**v, "director": {**d, "avatar_url": url_imagen_medios(d.get("avatar"))},
            "periodistas": [{**p, "avatar_url": url_imagen_medios(p.get("avatar"))} for p in eq["periodistas"]],
            "notas": notas, "total_notas": db[COL].count_documents({"medio_id": m["id"]}),
            "tono_medio": round(sum(n["tono"] for n in notas) / len(notas), 2) if notas else None,
            "pronosticos_recientes": [{k: x[k] for k in ("juego_id", "texto", "estado", "pick_nombre", "exacto") if k in x} for x in pron]}
