"""
Entrevistas de la prensa a TUS representados (Corporativos). Cuando un medio escribe sobre un jugador o una selección de tu
cartera (services/prensa_service), su entrevistador puede pedir hablar con él: te llega como una decisión en «Decisiones» con
tres posturas (prudente, seguro de sí o polémico) o declinar. Lo que sale es determinístico (semilla = universo + entrevista +
postura) y depende de la postura, la línea del medio, el estilo del periodista, el tema de la nota y el ánimo del jugador.

Efectos (solo en TU universo): la reputación mediática del representado se ajusta (`corp_prensa_ajustes`, se desgasta con los
ciclos y la usa el riesgo de corte de las marcas), cambia la satisfacción de su contrato y se da un poco de XP.

  corp_entrevistas = {_id "ent:<universo>:<juego>:<medio>", universo_id, sigla, contrato_id, tipo (jugador|seleccion), ref_id,
                      nombre, medio_id, periodista, juego_id, tono_nota, tema, estado PENDIENTE|RESPONDIDA|DECLINADA|VENCIDA,
                      creado_seq, vence_seq, postura, exito, resultado {...}}
"""
from datetime import datetime
from typing import Dict, List, Optional

from config import corporativos as C
from config import medios as CM
from services import corporativo_reglas as R
from services import corporativo_universo_service as U
from services import prensa as P
from services import prensa_service as PS

db = U.db
COL = "corp_entrevistas"
COL_AJUSTE = "corp_prensa_ajustes"


def _tema(tipo: str, tono: float, nombre: str) -> str:
    if tipo == "seleccion":
        return f"La prensa habla fuerte de {nombre}" + (": se ganó los elogios." if tono > 0 else ": no perdona lo ocurrido.")
    return f"Tras su última nota, quieren escuchar a {nombre}" + (" después de elogiarlo." if tono > 0 else " después de criticarlo.")


def solicitar(estado, seq: int, ciclo: int) -> None:
    """Al final de cada poner_al_dia (al día): vence las viejas y abre las nuevas por lo que dijo la prensa de tu cartera."""
    try:
        sigla = next((s for s, k in estado.corps.items() if k.get("es_del_usuario")), None)
        if not sigla:
            return
        uid = estado.uid
        for d in db[COL].find({"universo_id": uid, "estado": "PENDIENTE", "vence_seq": {"$lte": seq}}):
            _cerrar(d, "VENCIDA", ciclo, seq, {"reputacion": CM.DECLINAR[0] // 2, "satisfaccion": -1})
        abiertas = db[COL].count_documents({"universo_id": uid, "estado": "PENDIENTE"})
        if abiertas >= CM.ENTREVISTA_MAX_PENDIENTES:
            return
        jugadores = {c["ref_id"]: c for c in estado.contratos if c["sigla"] == sigla and c["tipo"] == "jugador" and c.get("activo", True)}
        selecciones = {c["ref_id"]: c for c in estado.contratos if c["sigla"] == sigla and c["tipo"] == "seleccion" and c.get("activo", True)}
        juegos = [str(r["juego_id"]) for r in db["corp_registro_partidos"].find({"seq": {"$gt": seq - CM.ENTREVISTA_VENTANA_PARTIDOS, "$lte": seq}}, {"juego_id": 1})]
        if not juegos or not (jugadores or selecciones):
            return
        medios = {m["id"]: m for m in PS.medios()}
        for pub in db[PS.COL].find({"juego_id": {"$in": juegos}}).sort("fecha", -1):
            if abiertas >= CM.ENTREVISTA_MAX_PENDIENTES:
                break
            v = pub["valoraciones"][0]
            tipo = "jugador" if v["tipo"] == "jugador" and v["id"] in jugadores else \
                   ("seleccion" if v["tipo"] == "pais" and v["id"] in selecciones and abs(pub["tono"]) >= CM.ENTREVISTA_TONO_SELECCION else None)
            if not tipo:
                continue
            eid = f"ent:{uid}:{pub['_id']}"
            if db[COL].find_one({"_id": eid}, {"_id": 1}):
                continue
            prob = CM.ENTREVISTA_PROB_JUGADOR if tipo == "jugador" else CM.ENTREVISTA_PROB_SELECCION
            if R.semilla(uid, "entrevista", pub["_id"]).random() >= prob:
                continue
            medio = medios.get(pub["medio_id"])
            if not medio:
                continue
            per = next((p for p in medio["equipo"]["periodistas"] if p["rol"] == "entrevistador"), pub["periodista"])
            contrato = (jugadores if tipo == "jugador" else selecciones)[v["id"]]
            doc = {"_id": eid, "universo_id": uid, "sigla": sigla, "contrato_id": str(contrato["_id"]), "tipo": tipo, "ref_id": v["id"],
                   "nombre": v["nombre"], "medio_id": medio["id"], "periodista": {"nombre": per["nombre"], "estilo": per["estilo"], "sesgo": per.get("sesgo")},
                   "juego_id": pub["juego_id"], "tono_nota": pub["tono"], "tema": _tema(tipo, pub["tono"], v["nombre"]), "estado": "PENDIENTE",
                   "creado_seq": seq, "vence_seq": seq + CM.ENTREVISTA_VENCE_PARTIDOS, "ciclo": ciclo, "creado_en": datetime.utcnow()}
            db[COL].insert_one(doc)
            abiertas += 1
            U.avisar(uid, ciclo, "PRENSA", f"{medio['nombre']} pide una entrevista con {v['nombre']}", f"{doc['tema']} Respóndela en Decisiones: tu postura decide si le sube o le baja la imagen.",
                     "bi-mic-fill", clave=f"entrevista:{eid}")
    except Exception as e:
        print(f"[corporativos] entrevistas: {e}")


def listar(user_id) -> List[dict]:
    """Las entrevistas abiertas de tu universo, con el medio y las probabilidades de cada postura."""
    medios = {m["id"]: m for m in PS.medios()}
    salida = []
    seq = U.seq_actual()
    for d in db[COL].find({"universo_id": user_id, "estado": "PENDIENTE"}).sort("creado_seq", -1):
        m = medios.get(d["medio_id"]) or {}
        salida.append({**d, "id": d["_id"], "medio": {"nombre": m.get("nombre", "?"), "linea": m.get("linea_nombre"), "color": PS.LINEA_COLOR.get(m.get("linea"), "#94a3b8"),
                                                     "alcance": CM.NIVELES.get(m.get("nivel"))},
                       "restan": max(0, d["vence_seq"] - seq),
                       "posturas": [{"codigo": k, "nombre": CM.POSTURA_NOMBRE[k], "texto": CM.POSTURA_TEXTO[k], "prob": round(prob_exito(d, k, m) * 100)} for k in CM.POSTURAS]})
    return salida


def prob_exito(d: dict, postura: str, medio: dict) -> float:
    p = CM.POSTURAS[postura][0]
    linea, estilo = medio.get("linea"), (d.get("periodista") or {}).get("estilo")
    p += {"critica": -0.10, "sensacionalista": -0.06 if postura == "polemico" else -0.03, "oficialista": 0.08, "optimista": 0.05}.get(linea, 0.0)
    p += {"entrevistador": 0.05, "polemista": -0.08, "sensacionalista": -0.04}.get(estilo, 0.0)
    p += 0.08 if d.get("tono_nota", 0) > 0.3 else (-0.08 if d.get("tono_nota", 0) < -0.3 else 0.0)
    if d["tipo"] == "jugador":
        info = db["jugadores"].find_one({"id": d["ref_id"]}, {"estado_animo": 1}) or {}
        p += P.ANIMO.get(info.get("estado_animo"), 0.0) * 0.6
    return P.limitar(p, 0.05, 0.95)


def ajuste(uid, tipo: str, ref_id, ciclo: int) -> float:
    """Lo que tus entrevistas movieron la reputación de un representado en TU universo (se desgasta con los ciclos)."""
    d = db[COL_AJUSTE].find_one({"_id": f"{uid}:{tipo}:{ref_id}"})
    if not d:
        return 0.0
    return d["valor"] * CM.AJUSTE_REPUTACION_DECAE ** max(0, ciclo - d.get("ciclo", ciclo))


def _aplicar(uid, d: dict, rep: int, satisf: int, ciclo: int) -> None:
    tipo = "jugador" if d["tipo"] == "jugador" else "pais"
    actual = ajuste(uid, tipo, d["ref_id"], ciclo)
    nuevo = P.limitar(actual + rep, -CM.AJUSTE_REPUTACION_MAX, CM.AJUSTE_REPUTACION_MAX)
    db[COL_AJUSTE].update_one({"_id": f"{uid}:{tipo}:{d['ref_id']}"}, {"$set": {"universo_id": uid, "tipo": tipo, "ref_id": d["ref_id"], "valor": round(nuevo, 2), "ciclo": ciclo}}, upsert=True)
    if satisf:
        from bson import ObjectId
        c = db["corp_contratos"].find_one({"_id": ObjectId(d["contrato_id"]), "universo_id": uid, "activo": True}, {"satisfaccion": 1})
        if c:
            db["corp_contratos"].update_one({"_id": c["_id"]}, {"$set": {"satisfaccion": round(max(0, min(100, (c.get("satisfaccion") or 0) + satisf)), 1)}})


def _cerrar(d: dict, estado: str, ciclo: int, seq: int, resultado: dict, postura: Optional[str] = None, exito: Optional[bool] = None) -> None:
    _aplicar(d["universo_id"], d, resultado.get("reputacion", 0), resultado.get("satisfaccion", 0), ciclo)
    db[COL].update_one({"_id": d["_id"], "estado": "PENDIENTE"}, {"$set": {"estado": estado, "postura": postura, "exito": exito, "resultado": resultado, "cerrado_seq": seq}})


def responder(user_id, entrevista_id: str, postura: str) -> dict:
    from services.corporativo_fichajes_service import _cargo
    if postura not in CM.POSTURAS and postura != "declinar":
        raise ValueError("Postura inválida")
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, sigla, corp = _cargo(user_id)
        d = db[COL].find_one({"_id": entrevista_id, "universo_id": user_id, "sigla": sigla, "estado": "PENDIENTE"})
        if not d:
            raise ValueError("Esa entrevista ya no está disponible")
        ciclo, seq = U.ciclo_en_curso(universo), U.seq_actual()
        if postura == "declinar":
            _cerrar(d, "DECLINADA", ciclo, seq, {"reputacion": CM.DECLINAR[0], "satisfaccion": CM.DECLINAR[1]}, "declinar", None)
            return {"ok": True, "exito": None, "mensaje": f"Declinaste la entrevista de {d['nombre']}: la prensa lo nota (reputación {CM.DECLINAR[0]:+d})."}
        medio = next((m for m in PS.medios() if m["id"] == d["medio_id"]), {})
        _, rep_ok, rep_mal, sat_ok, sat_mal = CM.POSTURAS[postura]
        salio_bien = R.semilla(user_id, "entrevista-resultado", d["_id"], postura).random() < prob_exito(d, postura, medio)
        rep, sat = (rep_ok, sat_ok) if salio_bien else (rep_mal, sat_mal)
        _cerrar(d, "RESPONDIDA", ciclo, seq, {"reputacion": rep, "satisfaccion": sat}, postura, salio_bien)
        U.dar_xp(user_id, "CORP_ENTREVISTA", entrevista_id)
        txt = (f"Salió bien: {d['nombre']} quedó muy bien parado ({medio.get('nombre', 'el medio')}). Reputación {rep:+d} y satisfacción {sat:+d}."
               if salio_bien else f"Salió mal: {d['nombre']} se equivocó en {medio.get('nombre', 'la entrevista')}. Reputación {rep:+d} y satisfacción {sat:+d}.")
        return {"ok": True, "exito": salio_bien, "mensaje": txt}
