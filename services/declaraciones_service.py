"""Declaraciones tras el partido (rueda de prensa): servicio con Mongo. La lógica y los textos están en services/declaraciones.py.

Colección `declaraciones` (contenido GLOBAL, igual para todos; `restart_mundial` la borra):
    {_id: "<juego>:<lado>:<dt|jugador>", juego_id, fecha, hora, lado, equipo {id, nombre, bandera}, hablante {tipo 'dt'|'jugador', id, nombre},
     tipo, titulo, cita, valor, creado_en}
Las REACCIONES de los medios son notas normales de la colección `prensa` con tipo "REACCION" y `declaracion_id`, así la reputación mediática, las
fichas y la red social las reconocen sin cambios (valoraciones sobre el DT o el jugador que habló).
Gancho: `asegurar_declaraciones(juego)` al final de aplicar_efectos_secundarios, DESPUÉS de la prensa (idempotente, nunca lanza, no toca partidos
en transmisión).
"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from pymongo import UpdateOne

from services import declaraciones as D
from services import prensa as P
from services import prensa_service as PS

logger = logging.getLogger(__name__)
db = PS.db
COL = "declaraciones"


def _contexto_lados(j: dict) -> tuple:
    """(ctx de prensa, {'local': c, 'visita': c}) con lo que necesita declaraciones.py de cada lado."""
    ctx = PS.contexto(j)
    resultado = j.get("resultado") or {}
    eventos = resultado.get("eventos") or []
    nombres = {"local": ctx["local"]["nombre"], "visita": ctx["visita"]["nombre"]}
    dts_ids = [ctx[k].get("dt_id") for k in ("local", "visita") if ctx[k].get("dt_id")]
    temperamentos = {d["id"]: d.get("temperamento") for d in db["directores_tecnicos"].find({"id": {"$in": dts_ids}}, {"id": 1, "temperamento": 1})} if dts_ids else {}
    expulsados = {"local": None, "visita": None}
    roja = {"local": 0, "visita": 0}
    dt_exp = {"local": False, "visita": False}
    penal_contra = {"local": False, "visita": False}
    for e in eventos:
        tipo = e.get("tipo") or ""
        for lado in ("local", "visita"):
            otro = "visita" if lado == "local" else "local"
            if e.get("equipo") != nombres[lado]:
                continue
            if "DT EXPULSADO" in tipo:
                dt_exp[lado] = True
            elif "ROJA" in tipo or "DOBLE AMARILLA" in tipo:
                roja[lado] += 1
                if expulsados[lado] is None and e.get("jugadores"):
                    expulsados[lado] = e["jugadores"][0]
            elif tipo.strip() == "🎯 PENAL":
                penal_contra[otro] = True   # el penal se cobra A FAVOR del equipo del evento
    ids_exp = {}
    for lado, nombre in expulsados.items():
        if nombre:
            doc = db["jugadores"].find_one({"nombre": nombre, "pais_id": ctx[lado]["id"]}, {"id": 1, "nombre": 1})
            if doc:
                ids_exp[lado] = {"id": doc["id"], "nombre": doc["nombre"]}
    # Las LEYENDAS no hablan: son retiradas (algunas ya fallecieron) y no se les ponen palabras en la boca; solo jugadores actuales
    candidatos = [x["id"] for x in ids_exp.values()] + [ctx[k]["figura"]["id"] for k in ("local", "visita") if ctx[k].get("figura")]
    leyendas = {d["id"] for d in db["jugadores"].find({"id": {"$in": candidatos}, "leyenda": True}, {"id": 1})} if candidatos else set()
    ids_exp = {k: v for k, v in ids_exp.items() if v["id"] not in leyendas}
    lados = {}
    for lado in ("local", "visita"):
        otro = "visita" if lado == "local" else "local"
        s, r = ctx[lado], ctx[otro]
        res = "E" if ctx["ganador"] is None else ("V" if ctx["ganador"] == lado else "D")
        lados[lado] = {"eq": s["nombre"], "rival": r["nombre"], "gl": s["goles"], "gv": r["goles"], "dif": s["goles"] - r["goles"], "res": res,
                       "eliminacion": ctx["eliminacion"], "historia": ctx.get("historia"), "sorpresa": ctx.get("sorpresa") and ctx["ganador"] == lado,
                       "dt": s.get("dt"), "dt_id": s.get("dt_id"), "temperamento": temperamentos.get(s.get("dt_id")),
                       "roja_propia": roja[lado], "dt_expulsado": dt_exp[lado], "penal_contra": penal_contra[lado],
                       "expulsado": ids_exp.get(lado),
                       "figura": None if (s.get("figura") or {}).get("id") in leyendas else s.get("figura")}
    return ctx, lados


def asegurar_declaraciones(j: Optional[dict]) -> int:
    """Escribe las declaraciones del partido y las reacciones de la prensa si faltan. Idempotente; nunca lanza."""
    try:
        if not j or j.get("estado") != "finalizado" or (j.get("transmision") or {}).get("estado") == "in_progress" or not PS.medios():
            return 0
        jid = str(j["_id"])
        ctx, lados = _contexto_lados(j)
        rng = P.semilla("declaraciones", jid)
        declaraciones = D.declaraciones_del_partido(lados, rng)
        if not declaraciones:
            return 0
        ahora = datetime.utcnow()
        docs, notas, usados = [], [], set()
        elegidos = P.elegir_medios(ctx, PS.medios(), P.semilla("declaraciones-medios", jid))
        for d in declaraciones:
            c, s = lados[d["lado"]], ctx[d["lado"]]
            did = f"{jid}:{d['lado']}:{d['hablante']['tipo']}"
            docs.append({"_id": did, "juego_id": jid, "fecha": ctx["fecha"], "hora": ctx["hora"], "lado": d["lado"],
                         "equipo": {"id": s["id"], "nombre": s["nombre"]}, "hablante": d["hablante"], "tipo": d["tipo"], "titulo": D.TITULO[d["tipo"]],
                         "cita": d["cita"], "valor": d["valor"], "creado_en": ahora})
            candidatos = [(m, rol) for m, rol in elegidos if m["id"] not in usados and rol in (d["lado"], "interesado")]
            for medio, rol in candidatos[:D.REACCIONES_POR_DECLARACION]:
                usados.add(medio["id"])
                m = dict(medio, credibilidad=PS.credibilidad_actual(medio))
                per_rng = P.semilla("declaracion-reaccion", did, medio["id"])
                per = per_rng.choice(medio["equipo"]["periodistas"])
                r = D.reaccion(d, c, m, per, medio.get("pais_id") == s["id"], per_rng)
                val = {"tipo": d["hablante"]["tipo"], "id": d["hablante"]["id"], "nombre": d["hablante"]["nombre"], "valor": r["tono"]}
                notas.append({"_id": f"{did}:{medio['id']}", "juego_id": jid, "declaracion_id": did, "fecha": ctx["fecha"], "hora": ctx["hora"], "medio_id": medio["id"],
                              "medio": {"nombre": medio["nombre"], "slug": medio["slug"], "papel": medio["papel"], "linea": medio["linea"], "pais_id": medio.get("pais_id")},
                              "periodista": {"nombre": per["nombre"], "rol": per["rol"], "estilo": per["estilo"], "sesgo": per["sesgo"]},
                              "tipo": "REACCION", **r, "valoraciones": [val], "peso": P.peso_medio(m), "rol_cobertura": rol, "creado_en": ahora})
        if docs:
            db[COL].bulk_write([UpdateOne({"_id": x["_id"]}, {"$setOnInsert": x}, upsert=True) for x in docs], ordered=False)
        nuevas = []
        if notas:
            res = db[PS.COL].bulk_write([UpdateOne({"_id": x["_id"]}, {"$setOnInsert": x}, upsert=True) for x in notas], ordered=False)
            ids_nuevos = set(res.upserted_ids.values())
            nuevas = [x for x in notas if x["_id"] in ids_nuevos]
        if nuevas:   # solo lo recién escrito suma a la reputación (repetir la llamada no la infla)
            PS.actualizar_reputacion(nuevas)
        return len(docs)
    except Exception as e:
        print(f"[declaraciones] no se pudieron generar: {e}")
        return 0


# --- Vistas -----------------------------------------------------------------------------------------------------------
def _vista(d: dict, reacciones: List[dict]) -> dict:
    from services.tecnicos_service import fecha_corta
    return {"id": d["_id"], "juego_id": d["juego_id"], "fecha_corta": fecha_corta(d.get("fecha")) or d.get("fecha"), "tipo": d["tipo"], "titulo": d["titulo"], "cita": d["cita"],
            "hablante": d["hablante"], "equipo": d["equipo"], "reacciones": [PS.vista(x) for x in reacciones]}


def _con_reacciones(docs: List[dict]) -> List[dict]:
    if not docs:
        return []
    por: Dict[str, List[dict]] = {}
    for n in db[PS.COL].find({"declaracion_id": {"$in": [d["_id"] for d in docs]}}):
        por.setdefault(n["declaracion_id"], []).append(n)
    return [_vista(d, sorted(por.get(d["_id"], []), key=lambda x: -abs(x["tono"]))) for d in docs]


def de_partido(juego_id: str) -> List[dict]:
    try:
        return _con_reacciones(list(db[COL].find({"juego_id": str(juego_id)}).sort("lado", 1)))
    except Exception as e:
        print(f"[declaraciones] de_partido: {e}")
        return []


def de_hablante(tipo: str, ref, limite: int = 5) -> List[dict]:
    try:
        return _con_reacciones(list(db[COL].find({"hablante.tipo": tipo, "hablante.id": ref}).sort([("fecha", -1), ("hora", -1)]).limit(limite)))
    except Exception as e:
        print(f"[declaraciones] de_hablante: {e}")
        return []


def para_partidos(ids: List[str], limite: int = 2) -> Dict[str, List[dict]]:
    """{juego_id: [declaraciones con su primera reacción]} en UNA consulta (el hilo de cada partido en la red social)."""
    salida: Dict[str, List[dict]] = {}
    try:
        docs = list(db[COL].find({"juego_id": {"$in": ids}}))
        por_juego: Dict[str, List[dict]] = {}
        for d in docs:
            por_juego.setdefault(d["juego_id"], []).append(d)
        elegidas = [d for lista in por_juego.values() for d in sorted(lista, key=lambda x: x["hablante"]["tipo"])[:limite]]
        for v in _con_reacciones(elegidas):
            salida.setdefault(v["juego_id"], []).append({**v, "reacciones": v["reacciones"][:1]})
    except Exception as e:
        print(f"[declaraciones] para_partidos: {e}")
    return salida
