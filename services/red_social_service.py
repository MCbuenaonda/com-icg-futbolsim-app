"""
Red social de la FIFAV (vista /red-social y el feed del inicio).

Mezcla en una sola línea de tiempo:
  - los posts de los PARTIDOS terminados (cuenta oficial @FIFAV_Oficial; los mismos para todos: juegos_service.formatear_posts_partidos);
  - las publicaciones de las MARCAS del universo del usuario (corp_feed: firmas, rumores, renovaciones y despedidas,
    services/corporativo_marcas_service.py), cada una anclada a la fecha y hora del partido que cerró su ciclo;
  - las RESPUESTAS de las marcas a los partidos de sus patrocinados, dentro del hilo de ese partido.
Sin carrera de Corporativos (o sin sesión) solo se ven los partidos.

Orden: fecha y hora descendente; a igual momento, la publicación de la marca va arriba del partido (pasó después).
Paginación por cursor ('antes' = "fecha|hora" del último elemento mostrado). Búsqueda por selección, jugador,
tag, texto del post o marca.
"""
import re
import threading
import time
from typing import Optional

from services import corporativo_universo_service as U
from services.juegos_service import formatear_posts_partidos

db = U.db
TIPOS_MARCA = ["FIRMA", "RUMOR", "RENOVACION", "DESPEDIDA"]
FILTROS = {"todo": "Todo", "partidos": "Partidos", "prensa": "Prensa", "marcas": "Marcas", "rumores": "Rumores", "firmas": "Firmas"}
ETIQUETA_TIPO = {"FIRMA": ("Nuevo patrocinio", "bi-pen-fill"), "RUMOR": ("Rumor", "bi-ear-fill"),
                 "RENOVACION": ("Renovación", "bi-arrow-repeat"), "DESPEDIDA": ("Despedida", "bi-door-open-fill"),
                 "REACCION": ("Respuesta", "bi-chat-quote-fill")}
_puestas_al_dia: dict = {}


def _uid(usuario: Optional[dict]) -> Optional[str]:
    if not usuario:
        return None
    uid = str(usuario["_id"])
    return uid if U.obtener_universo(uid) else None


def poner_al_dia_en_segundo_plano(uid: Optional[str]) -> None:
    """El universo se pone al día al leer; para no hacer esperar al inicio, se dispara en un hilo (como mucho una vez por minuto)."""
    if not uid or _puestas_al_dia.get(uid, 0) > time.time() - 60:
        return
    _puestas_al_dia[uid] = time.time()

    def correr():
        try:
            U.poner_al_dia(uid)
        except Exception as e:
            print(f"[red social] poner al día {uid}: {e}")
    threading.Thread(target=correr, daemon=True).start()


def _cursor(antes: Optional[str]):
    if not antes or "|" not in antes:
        return None
    fecha, hora = antes.split("|", 1)
    return fecha, hora


def _filtro_tiempo(cur) -> dict:
    if not cur:
        return {}
    fecha, hora = cur
    return {"$or": [{"fecha": {"$lt": fecha}}, {"fecha": fecha, "hora": {"$lt": hora}}]}


def _marca_post(doc: dict, cat: dict) -> Optional[dict]:
    from services.corporativo_marcas_service import marca_vista
    from services.corporativo_mercado_service import valores
    m = cat.get(doc["marca_id"])
    if not m:
        return None
    v = valores()
    refs = []
    for r in doc.get("refs") or []:
        if r["tipo"] == "seleccion":
            p = v["info_paises"].get(r["ref_id"], {})
            refs.append({**r, "url": f"/paises/{r['ref_id']}", "bandera": p.get("bandera"), "pais_id": r["ref_id"]})
        else:
            j = v["info_jugadores"].get(r["ref_id"], {})
            p = v["info_paises"].get(j.get("pais_id"), {})
            refs.append({**r, "url": f"/jugadores/{r['ref_id']}", "bandera": p.get("bandera"), "pais_id": j.get("pais_id")})
    etiqueta, icono = ETIQUETA_TIPO.get(doc["tipo"], ("", "bi-megaphone"))
    # interacciones "de ambiente" (no hay una red real): proporcionales al alcance de la marca, fijas por publicación
    import zlib
    h = zlib.crc32(doc["_id"].encode())
    base = {3: 9000, 2: 3500, 1: 1200}.get(m.get("nivel", 2), 2000) * (1.6 if doc["tipo"] in ("FIRMA", "RUMOR") else 1)
    likes = int(base * (0.5 + (h % 1000) / 1000))
    interaccion = {"likes": likes, "reposts": likes // (6 + h % 5), "comentarios": likes // (12 + h % 9),
                   "visualizaciones": likes * (14 + h % 11)}
    return {"clase": "marca", "id": doc["_id"], "tipo": doc["tipo"], "etiqueta": etiqueta, "icono": icono, "marca": marca_vista(m),
            "texto": doc["texto"], "refs": refs, "fecha": doc.get("fecha") or "", "hora": doc.get("hora") or "",
            "orden": doc.get("orden", 0), "sigla": doc.get("sigla"), "juego_id": doc.get("juego_id"),
            # a veces el propio dueño firma el anuncio (fijo por publicación)
            "firma_dueno": doc["tipo"] in ("FIRMA", "RENOVACION", "DESPEDIDA") and (h // 7) % 100 < 40, **interaccion}


def _regex(q: str):
    return {"$regex": re.escape(q.strip()), "$options": "i"}


def publicaciones(usuario: Optional[dict], q: str = "", filtro: str = "todo", antes: Optional[str] = None, limite: int = 12) -> dict:
    """-> {"items": [post de partido | post de marca], "siguiente": cursor o None, "total_marcas": n}"""
    from services.corporativo_marcas_service import catalogo
    uid = _uid(usuario)
    cur = _cursor(antes)
    q = (q or "").strip()
    filtro = filtro if filtro in FILTROS else "todo"
    cat = catalogo() if uid else {}
    items = []

    # Partidos
    if filtro in ("todo", "partidos"):
        consulta = {"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}, **_filtro_tiempo(cur)}
        if q:
            rx = _regex(q)
            consulta = {"$and": [consulta, {"$or": [{"equipo_local.nombre": rx}, {"equipo_visitante.nombre": rx}, {"tag": rx},
                                                     {"resultado.cronica.post": rx}, {"resultado.goleadores.jugador_nombre": rx}]}]}
        juegos = list(db["juegos"].find(consulta).sort([("fecha", -1), ("hora", -1)]).limit(limite + 4))
        for p in formatear_posts_partidos(juegos):
            items.append({**p, "clase": "partido", "hora": p.get("hora") or "", "fecha": p.get("fecha") or "", "orden": -1,
                          "reacciones": []})

    # Prensa (global): las publicaciones de los medios, sueltas solo en su filtro; en los demás van dentro del hilo de cada partido
    if filtro == "prensa":
        from services.prensa_service import buscar
        items.extend(buscar(q, cur, limite))

    # Marcas del universo
    if uid and filtro in ("todo", "marcas", "rumores", "firmas"):
        tipos = {"rumores": ["RUMOR"], "firmas": ["FIRMA", "RENOVACION"]}.get(filtro, TIPOS_MARCA)
        consulta = {"universo_id": uid, "tipo": {"$in": tipos}, "fecha": {"$ne": None}, **_filtro_tiempo(cur)}
        if q:
            rx = _regex(q)
            marcas_q = [mid for mid, m in cat.items() if re.search(re.escape(q), m["nombre"], re.I)]
            consulta = {"$and": [consulta, {"$or": [{"texto": rx}, {"refs.nombre": rx}, {"marca_id": {"$in": marcas_q}}]}]}
        for d in db["corp_feed"].find(consulta).sort([("fecha", -1), ("hora", -1), ("orden", -1)]).limit(limite + 4):
            post = _marca_post(d, cat)
            if post:
                items.append(post)

    items.sort(key=lambda x: (x["fecha"], x["hora"], x["orden"]), reverse=True)
    pagina = items[:limite]
    if len(items) > limite:   # no partir un mismo momento entre dos páginas
        ultimo = (pagina[-1]["fecha"], pagina[-1]["hora"])
        pagina += [x for x in items[limite:] if (x["fecha"], x["hora"]) == ultimo]
    siguiente = f"{pagina[-1]['fecha']}|{pagina[-1]['hora']}" if len(items) > len(pagina) or len(pagina) >= limite else None

    # Lo que dice la prensa, en el hilo de cada partido (hasta 3: las de tono más fuerte)
    try:
        from services.prensa_service import db as db_prensa, vista as vista_prensa
        ids_partidos = [p["match_id"] for p in pagina if p["clase"] == "partido"]
        if ids_partidos:
            por = {}
            for d in db_prensa["prensa"].find({"juego_id": {"$in": ids_partidos}}):
                por.setdefault(d["juego_id"], []).append(d)
            for p in pagina:
                if p["clase"] == "partido" and por.get(p["match_id"]):
                    p["prensa"] = [vista_prensa(d) for d in sorted(por[p["match_id"]], key=lambda d: -abs(d["tono"]))[:3]]
    except Exception as e:
        print(f"[red social] prensa de los partidos: {e}")

    # Respuestas de las marcas en el hilo de cada partido
    if uid:
        por_juego = {p["match_id"]: p for p in pagina if p["clase"] == "partido"}
        if por_juego:
            for d in db["corp_feed"].find({"universo_id": uid, "tipo": "REACCION", "juego_id": {"$in": list(por_juego)}}):
                post = _marca_post(d, cat)
                if post:
                    por_juego[d["juego_id"]]["reacciones"].append(post)
            try:   # qué cadenas de TU universo transmitieron cada partido, con sus comentaristas
                from bson import ObjectId
                from services.corporativo_tv_service import transmisiones
                docs = list(db["juegos"].find({"_id": {"$in": [ObjectId(i) for i in por_juego if ObjectId.is_valid(i)]}},
                                              {"estado": 1, "equipo_local.id": 1, "equipo_visitante.id": 1}))
                for jid, filas in transmisiones(usuario, docs).items():
                    por_juego[jid]["tv"] = [{"nombre": f["tele"]["nombre"], "logo": f["tele"]["logo"], "color": f["tele"]["color"],
                                             "comentaristas": [c["nombre"] for c in ((f["tele"].get("equipo") or {}).get("comentaristas") or [])],
                                             "invitado": (f["invitado"] or {}).get("nombre")} for f in filas]
            except Exception as e:
                print(f"[red social] transmisión de los partidos: {e}")
    return {"items": pagina, "siguiente": siguiente}


def barra_lateral(usuario: Optional[dict]) -> dict:
    """Tendencias (selecciones y tags de los últimos partidos), marcas más activas del universo y números de la red."""
    from collections import Counter
    from services.corporativo_marcas_service import catalogo, marca_vista
    juegos = list(db["juegos"].find({"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}},
                                    {"equipo_local": 1, "equipo_visitante": 1, "tag": 1, "resultado.goles_local": 1,
                                     "resultado.goles_visitante": 1}).sort([("fecha", -1), ("hora", -1)]).limit(40))
    equipos = Counter()
    for j in juegos:
        goles = ((j.get("resultado") or {}).get("goles_local") or 0) + ((j.get("resultado") or {}).get("goles_visitante") or 0)
        for lado in ("equipo_local", "equipo_visitante"):
            e = j.get(lado) or {}
            if e.get("nombre"):
                equipos[(e["nombre"], e.get("bandera"))] += 1 + goles * 0.3
    tendencias = [{"nombre": n, "bandera": b, "menciones": int(c * 1234) % 9000 + 800} for (n, b), c in equipos.most_common(6)]
    uid = _uid(usuario)
    marcas = []
    total_marcas = 0
    if uid:
        cat = catalogo()
        conteo = Counter(d["marca_id"] for d in db["corp_feed"].find({"universo_id": uid}, {"marca_id": 1}).sort("creado_en", -1).limit(300))
        total_marcas = db["corp_feed"].count_documents({"universo_id": uid})
        marcas = [{**marca_vista(cat[mid]), "publicaciones": n} for mid, n in conteo.most_common(6) if mid in cat]
    return {"tendencias": tendencias, "marcas": marcas, "total_marcas": total_marcas, "con_universo": bool(uid),
            "total_partidos": db["juegos"].count_documents({"estado": "finalizado"})}


def para_inicio(usuario: Optional[dict], partidos: int = 5, marcas: int = 3) -> list:
    """Feed del inicio: los últimos partidos siempre y, entre ellos, hasta 'marcas' publicaciones de marcas de ese lapso."""
    items = publicaciones(usuario, filtro="partidos", limite=partidos)["items"][:partidos]
    if not items:
        return []
    desde = (items[-1]["fecha"], items[-1]["hora"])
    extra = [x for x in publicaciones(usuario, filtro="marcas", limite=marcas)["items"] if (x["fecha"], x["hora"]) >= desde][:marcas]
    if extra:   # las respuestas de las marcas ya vienen en el hilo de cada partido
        items = sorted(items + extra, key=lambda x: (x["fecha"], x["hora"], x["orden"]), reverse=True)
    return items
