"""
Corporativos Deportivos — TELEVISORAS: derechos de transmisión de las selecciones representadas.

Catálogo: colección `televisoras` (633 FICTICIAS, 3 por país: generar_televisoras.py; logos en el bucket
televisoras/<slug>.svg). Solo las 3 cadenas del país de una selección pueden ofertar por ella. Reglas en
config/corporativos.py (TV_*) y corporativo_reglas.tv_* (puras: también las usa simular_balance_corporativos.py).

Flujo (igual para el usuario y la IA; la IA elige sola la mejor oferta):
  1. Cierre de ciclo: una selección representada sin TV recibe una oferta INICIAL de una de sus 3 cadenas (las
     populares atraen a la líder de audiencia). La IA la firma; al usuario le queda en OFERTA hasta el cierre del ciclo
     siguiente (si no responde, se firma sola).
  2. Cada partido de la selección (dentro de poner_al_dia): la cadena paga según el resultado (victoria > empate >
     derrota = mínimo).
  3. A TV_AVISO_PARTIDOS del final: la cadena actual ofrece RENOVACION (o no, si fue mal) y las otras dos pueden ofertar
     (COMPETENCIA), con la tarifa corregida por los resultados (tv_forma). El usuario elige una (queda FIRMADA).
  4. Último partido: bono si sacó al menos la `exigencia` de la cadena; empieza la FIRMADA o, si no eligió, una de las
     ofertas al azar (la IA: la mejor).
  Termina antes si el corporativo deja de representar a la selección o si la selección queda eliminada (sin bono).

Colección corp_tv_contratos (PERMANENTE como el resto de corp_*):
  {_id, universo_id, sigla, contrato_id (representación), pais_id, televisora_id, tipo INICIAL|RENOVACION|COMPETENCIA,
   estado OFERTA|FIRMADA|ACTIVO|TERMINADO|RECHAZADA|VENCIDA, partidos, jugados, resultados [v/e/d], tarifa {victoria,
   empate, derrota, bono}, exigencia, forma, cobrado, bono_cobrado, sigue_a (contrato de TV al que reemplaza), ciclo,
   seq, desde_seq, vence_ciclo, terminado_ciclo, motivo, es_usuario, creado_en}
Escrituras dentro de poner_al_dia: en el lote de corporativo_marcas_service (iniciar_lote/vaciar_lote) + un espejo en
memoria de los vigentes, así un ciclo no suma viajes a la base.
"""
import time
from datetime import datetime
from typing import Dict, List, Optional

from config import corporativos as C
from config import televisoras as T
from services import corporativo_reglas as R
from services import corporativo_universo_service as U
from services.corporativo_mercado_service import valores

db = U.db
COL = "corp_tv_contratos"
VIGENTES = ("OFERTA", "FIRMADA", "ACTIVO")
LETRA = {"victoria": "V", "empate": "E", "derrota": "D"}
_cache = {"hasta": 0.0, "por_id": {}, "por_pais": {}}


# --- Catálogo ------------------------------------------------------------------------------------------------
def catalogo() -> Dict[int, dict]:
    """{televisora_id: doc} (no cambia en runtime: caché de 10 minutos)."""
    if _cache["hasta"] < time.time():
        docs = list(db["televisoras"].find({}, {"_id": 0}))
        _cache["por_id"] = {t["id"]: t for t in docs}
        por_pais: Dict[int, list] = {}
        for t in docs:
            por_pais.setdefault(t["pais_id"], []).append(t)
        _cache["por_pais"] = {k: sorted(v, key=lambda x: x["id"]) for k, v in por_pais.items()}
        _cache["hasta"] = time.time() + 600
    return _cache["por_id"]


def del_pais(pais_id: int) -> List[dict]:
    catalogo()
    return _cache["por_pais"].get(pais_id, [])


def tele_vista(t: dict) -> dict:
    from services.imagenes_pais_service import url_logo_televisora
    pais = valores()["info_paises"].get(t["pais_id"], {})
    perfil = T.PERFILES.get(t.get("perfil"), {})
    return {"id": t["id"], "nombre": t["nombre"], "slug": t["slug"], "logo": url_logo_televisora(t["slug"]),
            "pais_id": t["pais_id"], "pais": pais.get("nombre"), "bandera": pais.get("bandera"),
            "confederacion_id": t.get("confederacion_id"), "papel": t.get("papel"), "papel_nombre": T.PAPEL_NOMBRE.get(t.get("papel"), ""),
            "nivel": t.get("nivel", 2), "nivel_nombre": T.NIVELES.get(t.get("nivel", 2), ""), "perfil": t.get("perfil"),
            "perfil_nombre": perfil.get("nombre", ""), "perfil_descripcion": perfil.get("descripcion", ""),
            "perfil_icono": perfil.get("icono", "bi-tv"), "lema": t.get("lema"), "color": t["colores"][0], "color2": t["colores"][1],
            "exigencia": int(round(t.get("exigencia", 0.55) * 100)), "fidelidad": t.get("fidelidad", 0.5)}


def _tarifa_de(t: dict, pais_id: int, forma: float = 1.0) -> Dict[str, int]:
    from services.corporativo_ciclo_service import popularidad
    valor = valores()["selecciones"].get(pais_id, 0)
    return R.tv_tarifa(valor, popularidad("seleccion", pais_id, valor), t.get("nivel", 2), t.get("perfil", "generosa"), forma)


# --- Espejo y escrituras (dentro de poner_al_dia) --------------------------------------------------------------------
def _espejo(estado) -> Dict[str, dict]:
    e = getattr(estado, "_tv", None)
    if e is None:
        e = estado._tv = {d["_id"]: d for d in db[COL].find({"universo_id": estado.uid, "estado": {"$in": list(VIGENTES)}})}
    return e


def _ins(estado, doc: dict) -> None:
    from services import corporativo_marcas_service as M
    _espejo(estado)[doc["_id"]] = doc
    M._ins(COL, dict(doc))


def _upd(estado, doc: dict, cambios: dict) -> None:
    from services import corporativo_marcas_service as M
    doc.update(cambios)
    M._upd(COL, doc["_id"], {"$set": cambios})


def _de_pais(estado, pais_id: int, estados=VIGENTES) -> List[dict]:
    return [d for d in _espejo(estado).values() if d["pais_id"] == pais_id and d["estado"] in estados]


def _es_usuario(estado, sigla: str) -> bool:
    return bool(estado.corps.get(sigla, {}).get("es_del_usuario"))


def _oferta(estado, c: dict, t: dict, tipo: str, ciclo: int, seq: int, forma: float, sigue_a: Optional[str] = None) -> dict:
    rng = R.semilla(estado.uid, "tv-partidos", c["ref_id"], t["id"], seq)
    doc = {"_id": f"tv:{estado.uid}:{c['ref_id']}:{t['id']}:{seq}", "universo_id": estado.uid, "sigla": c["sigla"],
           "contrato_id": str(c["_id"]), "pais_id": c["ref_id"], "televisora_id": t["id"], "tipo": tipo, "estado": "OFERTA",
           "partidos": rng.randint(*C.TV_PARTIDOS), "jugados": 0, "resultados": [], "tarifa": _tarifa_de(t, c["ref_id"], forma),
           "exigencia": t.get("exigencia", 0.55), "forma": forma, "cobrado": 0, "bono_cobrado": 0, "sigue_a": sigue_a,
           "ciclo": ciclo, "seq": seq, "desde_seq": None, "vence_ciclo": ciclo + C.TV_OFERTA_CICLOS if tipo == "INICIAL" else None,
           "terminado_ciclo": None, "motivo": None, "es_usuario": _es_usuario(estado, c["sigla"]), "creado_en": datetime.utcnow()}
    _ins(estado, doc)
    return doc


def _activar(estado, doc: dict, seq: int, ciclo: int, motivo: Optional[str] = None) -> None:
    _upd(estado, doc, {"estado": "ACTIVO", "desde_seq": seq + 1, "motivo": motivo, "firmado_ciclo": ciclo})
    t = catalogo().get(doc["televisora_id"], {})
    nombre = valores()["info_paises"].get(doc["pais_id"], {}).get("nombre", "?")
    estado.mover(doc["sigla"], ciclo, "TV_CONTRATO", 0, f"{t.get('nombre', 'TV')} transmitirá a {nombre}: {doc['partidos']} partidos"
                 + (f" ({motivo})" if motivo else ""), {"ref_id": doc["pais_id"], "tipo_ref": "seleccion"})


def _cobrar(estado, doc: dict, c: Optional[dict], monto: int, ciclo: int, detalle: str, juego_id: Optional[str] = None) -> None:
    corp = estado.corps.get(doc["sigla"])
    if not corp or monto <= 0:
        return
    corp["capital"] += monto
    corp["ciclo_actual"]["extra"] += monto
    corp["ciclo_actual"]["tv"] = corp["ciclo_actual"].get("tv", 0) + monto
    if c:
        c["renta_total"] = c.get("renta_total", 0) + monto
        c["renta_ciclo"] = c.get("renta_ciclo", 0) + monto
        estado.tocar(c)
    estado.mover(doc["sigla"], ciclo, "TV_PAGO", monto, detalle,
                 {"ref_id": doc["pais_id"], "tipo_ref": "seleccion", **({"juego_id": juego_id} if juego_id else {})})


def _representacion(estado, doc: dict) -> Optional[dict]:
    c = estado.por_seleccion.get(doc["pais_id"])
    return c if c and str(c["_id"]) == doc["contrato_id"] and c.get("activo", True) else None


# --- Por partido ----------------------------------------------------------------------------------------------------
def procesar_partido(estado, aporte: dict, ciclo: int, juego_id: str, seq: int) -> None:
    """La cadena paga el partido de cada selección con TV; a TV_AVISO_PARTIDOS del final, ofertas; al final, bono y relevo."""
    try:
        for pais_id, resultado in (aporte.get("selecciones") or {}).items():
            activos = _de_pais(estado, pais_id, ("ACTIVO",))
            if not activos:
                continue
            doc = activos[0]
            if doc.get("desde_seq") and seq < doc["desde_seq"]:
                continue
            c = _representacion(estado, doc)
            if not c:
                _terminar(estado, doc, ciclo, seq, "Terminó la representación", bono=False)
                continue
            monto = doc["tarifa"].get(resultado, doc["tarifa"]["derrota"])
            t = catalogo().get(doc["televisora_id"], {})
            nombre = valores()["info_paises"].get(pais_id, {}).get("nombre", "?")
            _cobrar(estado, doc, c, monto, ciclo, f"{t.get('nombre', 'TV')}: {nombre} ({resultado})", juego_id)
            _upd(estado, doc, {"jugados": doc["jugados"] + 1, "resultados": doc["resultados"] + [resultado],
                               "cobrado": doc["cobrado"] + monto})
            faltan = doc["partidos"] - doc["jugados"]
            if faltan == C.TV_AVISO_PARTIDOS:
                _ofertas_renovacion(estado, doc, c, ciclo, seq)
            if faltan <= 0:
                _terminar(estado, doc, ciclo, seq, "Cumplió el contrato", bono=True)
                _siguiente(estado, doc, c, ciclo, seq)
    except Exception as e:
        print(f"[corporativos] televisoras, partido {juego_id}: {e}")


def _ofertas_renovacion(estado, actual: dict, c: dict, ciclo: int, seq: int) -> None:
    from services.corporativo_ciclo_service import popularidad
    if any(d.get("sigue_a") == actual["_id"] for d in _de_pais(estado, actual["pais_id"])):
        return
    pct = R.tv_pct(actual["resultados"])
    forma = R.tv_forma(pct)
    valor = valores()["selecciones"].get(actual["pais_id"], 0)
    pop = popularidad("seleccion", actual["pais_id"], valor)
    rng = R.semilla(estado.uid, "tv-renueva", actual["_id"], seq)
    nuevas = 0
    for t in del_pais(actual["pais_id"]):
        if t["id"] == actual["televisora_id"]:
            sigue = rng.random() < R.tv_prob_renueva(t.get("fidelidad", 0.5), pct)
            tipo = "RENOVACION"
        else:
            sigue = rng.random() < R.tv_prob_compite(t.get("nivel", 2), pct, pop)
            tipo = "COMPETENCIA"
        if sigue:
            _oferta(estado, c, t, tipo, ciclo, seq, forma, sigue_a=actual["_id"])
            nuevas += 1
    if not nuevas:   # siempre queda una: la cadena más chica del país, con la tarifa más baja
        t = min(del_pais(actual["pais_id"]), key=lambda x: x.get("nivel", 2))
        _oferta(estado, c, t, "RENOVACION" if t["id"] == actual["televisora_id"] else "COMPETENCIA", ciclo, seq,
                round(forma * 0.9, 3), sigue_a=actual["_id"])


def _terminar(estado, doc: dict, ciclo: int, seq: int, motivo: str, bono: bool) -> None:
    extra = {}
    if bono:
        pct = R.tv_pct(doc["resultados"])
        b = R.tv_bono(doc["tarifa"], doc["partidos"], pct, doc.get("exigencia", 0.55))
        if b:
            c = _representacion(estado, doc)
            t = catalogo().get(doc["televisora_id"], {})
            nombre = valores()["info_paises"].get(doc["pais_id"], {}).get("nombre", "?")
            _cobrar(estado, doc, c, b, ciclo, f"{t.get('nombre', 'TV')}: bono por el rendimiento de {nombre} ({int(pct * 100)}% de los puntos)")
            extra = {"bono_cobrado": b, "cobrado": doc["cobrado"] + b}
    _upd(estado, doc, {"estado": "TERMINADO", "terminado_ciclo": ciclo, "terminado_seq": seq, "motivo": motivo, **extra})
    if not bono:   # sin relevo: las ofertas que esperaban a este contrato ya no aplican
        for o in [d for d in _de_pais(estado, doc["pais_id"], ("OFERTA", "FIRMADA")) if d.get("sigue_a") == doc["_id"]]:
            _upd(estado, o, {"estado": "VENCIDA", "motivo": motivo})


def _siguiente(estado, actual: dict, c: dict, ciclo: int, seq: int) -> None:
    pendientes = [d for d in _de_pais(estado, actual["pais_id"], ("OFERTA", "FIRMADA")) if d.get("sigue_a") == actual["_id"]]
    if not pendientes:
        return
    firmada = next((d for d in pendientes if d["estado"] == "FIRMADA"), None)
    motivo = None
    if firmada:
        elegida = firmada
    elif _es_usuario(estado, actual["sigla"]):
        elegida = R.semilla(estado.uid, "tv-azar", actual["_id"]).choice(sorted(pendientes, key=lambda d: d["_id"]))
        motivo = "no elegiste: se firmó una de las ofertas al azar"
    else:
        elegida = max(pendientes, key=lambda d: R.tv_esperado(d["tarifa"]))
    _activar(estado, elegida, seq, ciclo, motivo)
    for d in pendientes:
        if d is not elegida:
            _upd(estado, d, {"estado": "VENCIDA" if d["estado"] == "OFERTA" else "RECHAZADA", "motivo": "Se firmó otra oferta"})


# --- Cierre de ciclo ------------------------------------------------------------------------------------------------
def cerrar_ciclo_tv(estado, ciclo: int) -> None:
    """Representaciones terminadas, selecciones eliminadas, ofertas iniciales vencidas (se firman) y ofertas nuevas."""
    try:
        from services.fantasy_service import paises_eliminados
        eliminados = paises_eliminados()
        seq = ciclo * C.PARTIDOS_POR_CICLO
        for doc in list(_espejo(estado).values()):
            if doc["estado"] not in VIGENTES:
                continue
            if not _representacion(estado, doc):
                if doc["estado"] == "ACTIVO":
                    _terminar(estado, doc, ciclo, seq, "Terminó la representación", bono=False)
                else:
                    _upd(estado, doc, {"estado": "VENCIDA", "motivo": "Terminó la representación"})
            elif doc["pais_id"] in eliminados:
                if doc["estado"] == "ACTIVO":
                    _terminar(estado, doc, ciclo, seq, "La selección quedó eliminada", bono=False)
                else:
                    _upd(estado, doc, {"estado": "VENCIDA", "motivo": "La selección quedó eliminada"})
        # ofertas iniciales sin respuesta: se firman solas
        for doc in [d for d in _espejo(estado).values() if d["estado"] == "OFERTA" and d["tipo"] == "INICIAL"
                    and (d.get("vence_ciclo") or 0) <= ciclo]:
            if not _de_pais(estado, doc["pais_id"], ("ACTIVO",)):
                _activar(estado, doc, seq, ciclo, "no respondiste: se firmó sola")
                for o in _de_pais(estado, doc["pais_id"], ("OFERTA",)):
                    if o is not doc and o["tipo"] == "INICIAL":
                        _upd(estado, o, {"estado": "VENCIDA", "motivo": "Se firmó otra oferta"})
            else:
                _upd(estado, doc, {"estado": "VENCIDA", "motivo": "Ya tiene televisora"})
        # ofertas nuevas a las selecciones representadas sin TV
        from services.corporativo_ciclo_service import popularidad
        for pais_id, c in list(estado.por_seleccion.items()):
            if pais_id in eliminados or not c.get("activo", True) or _de_pais(estado, pais_id) or not del_pais(pais_id):
                continue
            rng = R.semilla(estado.uid, "tv-inicial", pais_id, ciclo)
            if rng.random() >= C.TV_PROB_OFERTA_INICIAL:
                continue
            valor = valores()["selecciones"].get(pais_id, 0)
            pop = popularidad("seleccion", pais_id, valor)
            cadenas = del_pais(pais_id)
            t = rng.choices(cadenas, weights=[R.tv_peso_inicial(x.get("nivel", 2), pop) for x in cadenas])[0]
            doc = _oferta(estado, c, t, "INICIAL", ciclo, seq, 1.0)
            if not _es_usuario(estado, c["sigla"]):
                _activar(estado, doc, seq, ciclo)
    except Exception as e:
        print(f"[corporativos] televisoras, cierre del ciclo {ciclo}: {e}")


# --- Acciones del usuario ------------------------------------------------------------------------------------------
def responder(user_id, tv_id: str, aceptar: bool) -> dict:
    from services.corporativo_fichajes_service import _cargo
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, sigla, corp = _cargo(user_id)
        doc = db[COL].find_one({"_id": tv_id, "universo_id": user_id, "sigla": sigla, "estado": "OFERTA"})
        if not doc:
            raise ValueError("Esa oferta ya no está disponible")
        t = catalogo().get(doc["televisora_id"], {})
        nombre = valores()["info_paises"].get(doc["pais_id"], {}).get("nombre", "?")
        if not db["corp_contratos"].find_one({"_id": _oid(doc["contrato_id"]), "activo": True, "sigla": sigla}):
            db[COL].update_one({"_id": tv_id}, {"$set": {"estado": "VENCIDA", "motivo": "Ya no lo representas"}})
            raise ValueError(f"Ya no representas a {nombre}")
        if not aceptar:
            db[COL].update_one({"_id": tv_id}, {"$set": {"estado": "RECHAZADA", "motivo": "La rechazaste"}})
            return {"ok": True, "mensaje": f"Rechazaste la oferta de {t.get('nombre', 'la televisora')}."}
        ciclo = U.ciclo_en_curso(universo)
        seq = universo.get("cursor_seq") or U.seq_actual()
        hermanas = {"universo_id": user_id, "pais_id": doc["pais_id"], "estado": "OFERTA", "_id": {"$ne": tv_id}}
        if doc.get("sigue_a"):   # renovación: empieza cuando termine el contrato actual
            db[COL].update_one({"_id": tv_id}, {"$set": {"estado": "FIRMADA", "firmado_ciclo": ciclo}})
            db[COL].update_many({**hermanas, "sigue_a": doc["sigue_a"]}, {"$set": {"estado": "RECHAZADA", "motivo": "Elegiste otra oferta"}})
            mensaje = (f"¡Firmado! {t.get('nombre')} transmitirá a {nombre} cuando termine el contrato actual "
                       f"({doc['partidos']} partidos, {doc['tarifa']['victoria']:,} por victoria).")
        else:
            if db[COL].find_one({"universo_id": user_id, "pais_id": doc["pais_id"], "estado": "ACTIVO"}):
                raise ValueError(f"{nombre} ya tiene televisora")
            db[COL].update_one({"_id": tv_id}, {"$set": {"estado": "ACTIVO", "desde_seq": seq + 1, "firmado_ciclo": ciclo}})
            db[COL].update_many(hermanas, {"$set": {"estado": "RECHAZADA", "motivo": "Elegiste otra oferta"}})
            mensaje = (f"¡Firmado! {t.get('nombre')} transmite a {nombre} los próximos {doc['partidos']} partidos: "
                       f"{doc['tarifa']['victoria']:,} por victoria, {doc['tarifa']['empate']:,} por empate y {doc['tarifa']['derrota']:,} por derrota.")
        db["corp_movimientos"].insert_one({"universo_id": user_id, "sigla": sigla, "ciclo": ciclo, "tipo": "TV_CONTRATO", "monto": 0,
                                           "detalle": f"{t.get('nombre')}: contrato de transmisión de {nombre} ({doc['partidos']} partidos)",
                                           "creado_en": datetime.utcnow()})
    U.dar_xp(user_id, "CORP_TV", tv_id, ("PRIMER_CONTRATO_TV",))
    return {"ok": True, "mensaje": mensaje}


def _oid(x):
    from bson import ObjectId
    return ObjectId(x)


# --- Para las vistas ------------------------------------------------------------------------------------------------
def _fila(d: dict) -> Optional[dict]:
    t = catalogo().get(d["televisora_id"])
    if not t:
        return None
    pais = valores()["info_paises"].get(d["pais_id"], {})
    pct = R.tv_pct(d.get("resultados") or [])
    faltan = d["partidos"] - d.get("jugados", 0)
    return {"id": d["_id"], "estado": d["estado"], "tipo": d.get("tipo"), "tele": tele_vista(t), "pais_id": d["pais_id"],
            "pais": pais.get("nombre"), "bandera": pais.get("bandera"), "sigla": d["sigla"], "partidos": d["partidos"],
            "jugados": d.get("jugados", 0), "faltan": faltan, "resultados": [LETRA.get(r, "?") for r in d.get("resultados") or []],
            "tarifa": d["tarifa"], "esperado": R.tv_esperado(d["tarifa"]), "bono_total": d["tarifa"]["bono"] * d["partidos"],
            "exigencia": int(round(d.get("exigencia", 0.55) * 100)), "pct": int(round(pct * 100)) if pct is not None else None,
            "bono_en_camino": pct is not None and pct >= d.get("exigencia", 0.55), "cobrado": d.get("cobrado", 0),
            "bono_cobrado": d.get("bono_cobrado", 0), "forma": d.get("forma", 1.0), "sigue_a": d.get("sigue_a"),
            "aviso": d["estado"] == "ACTIVO" and faltan <= C.TV_AVISO_PARTIDOS, "motivo": d.get("motivo"),
            "vence_ciclo": d.get("vence_ciclo"), "ciclo": d.get("ciclo"), "terminado_ciclo": d.get("terminado_ciclo")}


def resumen(user_id, sigla: str) -> dict:
    """Para el inicio de Corporativos y la pestaña Ingresos: lo de tu corporativo con las cadenas."""
    docs = list(db[COL].find({"universo_id": user_id, "sigla": sigla, "estado": {"$in": list(VIGENTES)}}))
    activos = [_fila(d) for d in docs if d["estado"] == "ACTIVO"]
    ofertas = [_fila(d) for d in docs if d["estado"] == "OFERTA"]
    total = list(db[COL].aggregate([{"$match": {"universo_id": user_id, "sigla": sigla}},
                                    {"$group": {"_id": None, "cobrado": {"$sum": "$cobrado"}, "bonos": {"$sum": "$bono_cobrado"}}}]))
    return {"activos": [a for a in activos if a], "ofertas": [o for o in ofertas if o], "firmadas": [_fila(d) for d in docs if d["estado"] == "FIRMADA"],
            "cobrado_total": (total[0]["cobrado"] if total else 0), "bonos_total": (total[0]["bonos"] if total else 0)}


def tv_por_contrato(user_id, sigla: str) -> Dict[str, dict]:
    """{contrato_id: {nombre, logo, jugados, partidos}} de la televisora vigente de cada selección (chip de la cartera)."""
    salida = {}
    for d in db[COL].find({"universo_id": user_id, "sigla": sigla, "estado": "ACTIVO"}):
        t = catalogo().get(d["televisora_id"])
        if t:
            v = tele_vista(t)
            salida[d["contrato_id"]] = {"nombre": v["nombre"], "logo": v["logo"], "color": v["color"], "jugados": d.get("jugados", 0),
                                        "partidos": d["partidos"], "id": t["id"]}
    return salida


def tv_de_pais(usuario: Optional[dict], pais_id: int) -> Optional[dict]:
    """La televisora que transmite a una selección en el universo del usuario (franja de /paises/{id})."""
    if not usuario:
        return None
    try:
        d = db[COL].find_one({"universo_id": str(usuario["_id"]), "pais_id": int(pais_id), "estado": "ACTIVO"})
        return _fila(d) if d else None
    except Exception:
        return None


def ficha(user_id, tele_id: int) -> Optional[dict]:
    """Datos del modal: la cadena, cómo pagaría hoy a su selección y su historia en tu universo."""
    t = catalogo().get(int(tele_id))
    if not t:
        return None
    v = tele_vista(t)
    tarifa = _tarifa_de(t, t["pais_id"])
    historia = [_fila(d) for d in db[COL].find({"universo_id": user_id, "televisora_id": t["id"],
                                                 "estado": {"$in": ["ACTIVO", "TERMINADO", "FIRMADA"]}}).sort("seq", -1).limit(8)]
    transmite = next((h for h in historia if h and h["estado"] == "ACTIVO"), None)
    hermanas = [tele_vista(x) for x in del_pais(t["pais_id"]) if x["id"] != t["id"]]
    return {**v, "tarifa_hoy": tarifa, "esperado_hoy": R.tv_esperado(tarifa), "bono_hoy": tarifa["bono"],
            "historia": [h for h in historia if h], "transmite": transmite, "hermanas": hermanas,
            "partidos_rango": list(C.TV_PARTIDOS)}


def vista_televisoras(user_id) -> Optional[dict]:
    """Página «Televisoras»: ofertas, tus contratos, el catálogo de las 633 y tu historial."""
    universo = U.obtener_universo(user_id)
    if not universo:
        return None
    U.poner_al_dia(user_id)
    universo = U.obtener_universo(user_id)
    sigla = (universo.get("cargo") or {}).get("sigla")
    ciclo = U.ciclo_en_curso(universo)
    cat = catalogo()
    mis = [d for d in db[COL].find({"universo_id": user_id, "sigla": sigla, "estado": {"$in": list(VIGENTES)}})] if sigla else []
    ofertas = [_fila(d) for d in mis if d["estado"] == "OFERTA"]
    actuales = {}
    for d in mis:   # la tarifa vigente de cada selección, para comparar las ofertas
        if d["estado"] == "ACTIVO":
            actuales[d["pais_id"]] = R.tv_esperado(d["tarifa"])
    for o in ofertas:
        if o:
            o["actual_esperado"] = actuales.get(o["pais_id"])
    contratos = [_fila(d) for d in mis if d["estado"] in ("ACTIVO", "FIRMADA")]
    historial = [_fila(d) for d in db[COL].find({"universo_id": user_id, "sigla": sigla, "estado": {"$in": ["TERMINADO", "RECHAZADA", "VENCIDA"]}})
                 .sort([("terminado_ciclo", -1), ("ciclo", -1)]).limit(40)] if sigla else []
    # qué transmite cada cadena en tu universo (cualquier corporativo)
    transmite: Dict[int, dict] = {}
    for d in db[COL].find({"universo_id": user_id, "estado": "ACTIVO"}, {"televisora_id": 1, "pais_id": 1, "sigla": 1}):
        transmite[d["televisora_id"]] = {"sigla": d["sigla"], "pais": valores()["info_paises"].get(d["pais_id"], {}).get("nombre")}
    mis_paises = {c["ref_id"] for c in U.contratos_activos(user_id, sigla) if c["tipo"] == "seleccion"} if sigla else set()
    catalogo_l = []
    for t in cat.values():
        v = tele_vista(t)
        v["transmite"] = transmite.get(t["id"])
        v["mi_seleccion"] = t["pais_id"] in mis_paises
        v["esperado_hoy"] = R.tv_esperado(_tarifa_de(t, t["pais_id"]))
        catalogo_l.append(v)
    catalogo_l.sort(key=lambda x: (-x["nivel"], x["pais"] or "", x["nombre"]))
    corp = db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": sigla}, {"ciclo_actual": 1}) if sigla else None
    res = resumen(user_id, sigla) if sigla else None
    return {"universo": universo, "sigla": sigla, "ciclo": ciclo, "en_cargo": universo["estado"] == "EN_CARGO",
            "ofertas": [o for o in ofertas if o], "contratos": [c for c in contratos if c], "historial": [h for h in historial if h],
            "catalogo": catalogo_l, "confederaciones": {1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC"},
            "niveles": T.NIVELES, "perfiles": T.PERFILES, "papeles": T.PAPEL_NOMBRE, "mis_selecciones": len(mis_paises),
            "tv_ciclo": int(((corp or {}).get("ciclo_actual") or {}).get("tv", 0)),
            "cobrado_total": (res or {}).get("cobrado_total", 0), "bonos_total": (res or {}).get("bonos_total", 0),
            "aviso_partidos": C.TV_AVISO_PARTIDOS, "partidos_rango": list(C.TV_PARTIDOS)}


# --- Invitados de TV: un jugador representado como invitado especial en la transmisión de un partido -------------------
# Colección corp_tv_invitados {_id universo:juego:televisora, universo_id, juego_id, televisora_id, pais_tv, jugador_id,
# contrato_id, sigla, estado PROGRAMADA|REALIZADA|CANCELADA, pago, aficionados, motivo, fecha, hora, decidido_seq,
# realizado_seq, creado_en}. Se eligen al final de cada poner_al_dia para los próximos TV_INVITADO_HORIZONTE partidos
# reales y se cobran cuando el partido se procesa (realizar_invitados, por partido). Reglas en config TV_INVITADO_*.
COL_INV = "corp_tv_invitados"
MOTIVO_INVITADOS = "📺 Invitados en TV"


def _espejo_inv(estado) -> Dict[str, dict]:
    """Invitaciones programadas + las recientes (para el enfriamiento) del universo, en memoria durante poner_al_dia."""
    e = getattr(estado, "_tv_inv", None)
    if e is None:
        desde = U.seq_actual() - C.TV_INVITADO_ENFRIAMIENTO_PARTIDOS - C.TV_INVITADO_HORIZONTE
        e = estado._tv_inv = {d["_id"]: d for d in db[COL_INV].find(
            {"universo_id": estado.uid, "$or": [{"estado": "PROGRAMADA"}, {"decidido_seq": {"$gte": desde}}]})}
    return e


def _elegible(estado, c: dict, ciclo: int, seq: int, en_gira: set, ocupados: set) -> bool:
    """Las condiciones del invitado: sin gira, su selección no juega en lo que queda del ciclo, fuera de la ventana de
    renovación, sin otra invitación programada ni reciente."""
    from services.corporativo_acciones_service import _juega_en_ciclo_activo
    if not c.get("activo", True) or c["ref_id"] in en_gira or c["ref_id"] in ocupados:
        return False
    if c.get("hasta_ciclo") is not None and c["hasta_ciclo"] - ciclo + 1 <= C.CICLOS_AVISO_RENOVACION:
        return False
    pais = valores()["info_jugadores"].get(c["ref_id"], {}).get("pais_id")
    return _juega_en_ciclo_activo(pais) is None


def programar_invitados(estado, ciclo: int, seq: int) -> None:
    """Para los próximos TV_INVITADO_HORIZONTE partidos: cada cadena con contrato ACTIVO de una de las dos selecciones,
    con TV_INVITADO_PROB, elige un invitado AL AZAR entre los representados que cumplen las condiciones."""
    try:
        espejo_inv = _espejo_inv(estado)
        proximos = list(db["juegos"].find({"estado": "creado"}, {"equipo_local.id": 1, "equipo_visitante.id": 1, "fecha": 1, "hora": 1})
                        .sort([("fecha", 1), ("hora", 1)]).limit(C.TV_INVITADO_HORIZONTE))
        if not proximos:
            return
        from services.corporativo_acciones_service import _cargar_giras
        en_gira = {g["ref_id"] for g in _cargar_giras(estado) if g.get("tipo") == "jugador" and g.get("estado") == "EN_CURSO"}
        ocupados = {d["jugador_id"] for d in espejo_inv.values()
                    if d["estado"] == "PROGRAMADA" or (d.get("decidido_seq") or 0) > seq - C.TV_INVITADO_ENFRIAMIENTO_PARTIDOS}
        jugadores = sorted((c for c in estado.contratos if c["tipo"] == "jugador" and c.get("activo", True)), key=lambda c: str(c["_id"]))
        for j in proximos:
            jid = str(j["_id"])
            for lado in ("equipo_local", "equipo_visitante"):
                pais_tv = (j.get(lado) or {}).get("id")
                contrato_tv = next(iter(_de_pais(estado, pais_tv, ("ACTIVO",))), None) if pais_tv is not None else None
                if not contrato_tv:
                    continue
                inv_id = f"{estado.uid}:{jid}:{contrato_tv['televisora_id']}"
                if inv_id in espejo_inv:
                    continue
                rng = R.semilla(estado.uid, "tv-invitado", jid, contrato_tv["televisora_id"])
                if rng.random() >= C.TV_INVITADO_PROB:
                    # queda registrado que esta cadena no lleva invitado (así no se vuelve a sortear en cada visita)
                    doc = {"_id": inv_id, "universo_id": estado.uid, "juego_id": jid, "televisora_id": contrato_tv["televisora_id"],
                           "pais_tv": pais_tv, "jugador_id": None, "estado": "SIN_INVITADO", "decidido_seq": seq, "creado_en": datetime.utcnow()}
                    espejo_inv[inv_id] = doc
                    _ins_inv(doc)
                    continue
                pool = [c for c in jugadores if _elegible(estado, c, ciclo, seq, en_gira, ocupados)]
                if not pool:
                    continue
                c = rng.choice(pool)   # al azar: todos los que cumplen tienen la misma probabilidad
                ocupados.add(c["ref_id"])
                doc = {"_id": inv_id, "universo_id": estado.uid, "juego_id": jid, "televisora_id": contrato_tv["televisora_id"],
                       "pais_tv": pais_tv, "jugador_id": c["ref_id"], "contrato_id": str(c["_id"]), "sigla": c["sigla"],
                       "estado": "PROGRAMADA", "pago": None, "aficionados": None, "fecha": j.get("fecha"), "hora": j.get("hora"),
                       "decidido_seq": seq, "creado_en": datetime.utcnow()}
                espejo_inv[inv_id] = doc
                _ins_inv(doc)
                if _es_usuario(estado, c["sigla"]):
                    t = catalogo().get(contrato_tv["televisora_id"], {})
                    v = valores()
                    nombre = v["info_jugadores"].get(c["ref_id"], {}).get("nombre", "?")
                    rival = (j.get("equipo_visitante" if lado == "equipo_local" else "equipo_local") or {}).get("id")
                    partido = f"{v['info_paises'].get(pais_tv, {}).get('nombre', '?')} vs {v['info_paises'].get(rival, {}).get('nombre', '?')}"
                    U.avisar(estado.uid, ciclo, "TV", f"{t.get('nombre', 'Una televisora')} invitó a {nombre}",
                             f"Va de invitado especial a la transmisión de {partido} ({j.get('fecha')} {j.get('hora') or ''}). "
                             "Cobra cuando se juegue el partido, suma aficionados a su selección y sus marcas pagan más unas rondas.",
                             "bi-broadcast", clave=f"tv-invitado:{inv_id}")
    except Exception as e:
        print(f"[corporativos] invitados de TV: {e}")


def _ins_inv(doc: dict) -> None:
    from services import corporativo_marcas_service as M
    M._ins(COL_INV, dict(doc))


def _upd_inv(doc: dict, cambios: dict) -> None:
    from services import corporativo_marcas_service as M
    doc.update(cambios)
    M._upd(COL_INV, doc["_id"], {"$set": cambios})


def realizar_invitados(estado, juego_id: str, ciclo: int, seq: int) -> None:
    """El partido se jugó: cada invitación PROGRAMADA cobra (si el jugador sigue representado y sin gira), suma aficionados
    a su selección y deja a sus marcas pagando más por TV_INVITADO_RONDAS_MARCAS rondas."""
    try:
        pendientes = [d for d in _espejo_inv(estado).values() if d.get("juego_id") == juego_id and d["estado"] == "PROGRAMADA"]
        if not pendientes:
            return
        from services.corporativo_acciones_service import _aporte_agrupado, _cargar_giras
        from services.corporativo_ciclo_service import popularidad
        en_gira = {g["ref_id"] for g in _cargar_giras(estado) if g.get("tipo") == "jugador" and g.get("estado") == "EN_CURSO"}
        v = valores()
        for d in pendientes:
            c = estado.por_jugador.get(d["jugador_id"])
            if not c or str(c["_id"]) != d["contrato_id"] or not c.get("activo", True) or d["jugador_id"] in en_gira:
                _upd_inv(d, {"estado": "CANCELADA", "motivo": "Ya no cumplía las condiciones", "realizado_seq": seq})
                continue
            corp = estado.corps.get(c["sigla"])
            if not corp:
                continue
            t = catalogo().get(d["televisora_id"], {})
            valor = v["jugadores"].get(d["jugador_id"], 0)
            pop = popularidad("jugador", d["jugador_id"], valor)
            pago = R.tv_invitado_pago(valor, pop, t.get("nivel", 2))
            corp["capital"] += pago
            corp["ciclo_actual"]["extra"] += pago
            corp["ciclo_actual"]["tv_invitados"] = corp["ciclo_actual"].get("tv_invitados", 0) + pago
            c["renta_total"] = c.get("renta_total", 0) + pago
            c["renta_ciclo"] = c.get("renta_ciclo", 0) + pago
            c["tv_bono_hasta_seq"] = seq + C.TV_INVITADO_RONDAS_MARCAS * C.MARCA_PARTIDOS_RONDA
            estado.tocar(c)
            info = v["info_jugadores"].get(d["jugador_id"], {})
            fans = _aporte_agrupado(info.get("pais_id"), ciclo, R.tv_invitado_aficionados(R.semilla(d["_id"], "fans"), pop),
                                    prefijo="tv:", tope=C.TV_INVITADO_TOPE_AFICIONADOS, motivo=MOTIVO_INVITADOS,
                                    clave_historial="tv_invitados")
            _upd_inv(d, {"estado": "REALIZADA", "pago": pago, "aficionados": fans, "realizado_seq": seq})
            estado.mover(c["sigla"], ciclo, "TV_INVITADO", pago,
                         f"{t.get('nombre', 'TV')}: {info.get('nombre', '?')} de invitado en la transmisión"
                         + (f" (+{fans} aficionados a {v['info_paises'].get(info.get('pais_id'), {}).get('nombre', 'su selección')})" if fans else ""),
                         {"juego_id": juego_id, "ref_id": d["jugador_id"], "tipo_ref": "jugador"})
            if _es_usuario(estado, c["sigla"]):
                U.avisar(estado.uid, ciclo, "TV", f"{info.get('nombre', '?')} estuvo en {t.get('nombre', 'la TV')}",
                         f"Cobraste {pago:,}" + (f", sumó {fans} aficionados a su selección" if fans else "")
                         + " y sus marcas pagan más las próximas rondas.", "bi-broadcast", clave=f"tv-realizada:{d['_id']}")
    except Exception as e:
        print(f"[corporativos] invitados de TV, partido {juego_id}: {e}")


def _invitado_vista(d: dict) -> Optional[dict]:
    if not d or not d.get("jugador_id"):
        return None
    info = valores()["info_jugadores"].get(d["jugador_id"], {})
    return {"jugador_id": d["jugador_id"], "nombre": info.get("nombre", "?"), "pais_id": info.get("pais_id"), "sigla": d.get("sigla"),
            "estado": d["estado"], "pago": d.get("pago"), "aficionados": d.get("aficionados")}


def transmisiones(usuario: Optional[dict], juegos: List[dict]) -> Dict[str, list]:
    """{juego_id: [{tele, pais_id, pais, invitado|None}]}: qué cadenas de TU universo transmiten cada partido y su invitado.
    Pendientes: por los contratos ACTIVO de las dos selecciones; jugados: por las invitaciones registradas."""
    if not usuario or not juegos:
        return {}
    try:
        uid = str(usuario["_id"])
        paises = {p for j in juegos for p in ((j.get("equipo_local") or {}).get("id"), (j.get("equipo_visitante") or {}).get("id")) if p is not None}
        activos = {d["pais_id"]: d for d in db[COL].find({"universo_id": uid, "estado": "ACTIVO", "pais_id": {"$in": list(paises)}},
                                                          {"pais_id": 1, "televisora_id": 1})}
        ids = [str(j["_id"]) for j in juegos]
        invs: Dict[str, list] = {}
        for d in db[COL_INV].find({"universo_id": uid, "juego_id": {"$in": ids}}):
            invs.setdefault(d["juego_id"], []).append(d)
        v = valores()
        salida: Dict[str, list] = {}
        for j in juegos:
            jid = str(j["_id"])
            filas, vistos = [], set()
            jugado = j.get("estado") == "finalizado"
            for d in invs.get(jid, []):
                t = catalogo().get(d["televisora_id"])
                if t and d["estado"] != "CANCELADA":
                    vistos.add(d["televisora_id"])
                    filas.append({"tele": tele_vista(t), "pais_id": d["pais_tv"], "pais": v["info_paises"].get(d["pais_tv"], {}).get("nombre"),
                                  "invitado": _invitado_vista(d), "decidido": True})
            if not jugado:
                for lado in ("equipo_local", "equipo_visitante"):
                    p = (j.get(lado) or {}).get("id")
                    d = activos.get(p)
                    if d and d["televisora_id"] not in vistos:
                        t = catalogo().get(d["televisora_id"])
                        if t:
                            vistos.add(d["televisora_id"])
                            filas.append({"tele": tele_vista(t), "pais_id": p, "pais": v["info_paises"].get(p, {}).get("nombre"),
                                          "invitado": None, "decidido": False})
            if filas:
                salida[jid] = filas
        return salida
    except Exception as e:
        print(f"[corporativos] transmisiones: {e}")
        return {}


def invitaciones_de(usuario: Optional[dict], jugador_id: int) -> List[dict]:
    """Las apariciones en TV de un jugador en el universo del usuario (ficha del jugador)."""
    if not usuario:
        return []
    try:
        docs = list(db[COL_INV].find({"universo_id": str(usuario["_id"]), "jugador_id": int(jugador_id),
                                       "estado": {"$in": ["PROGRAMADA", "REALIZADA"]}}).sort("decidido_seq", -1).limit(20))
        if not docs:
            return []
        from bson import ObjectId
        juegos = {str(j["_id"]): j for j in db["juegos"].find({"_id": {"$in": [ObjectId(d["juego_id"]) for d in docs if ObjectId.is_valid(d["juego_id"])]}},
                                                              {"equipo_local.id": 1, "equipo_local.nombre": 1, "equipo_visitante.id": 1,
                                                               "equipo_visitante.nombre": 1, "fecha": 1, "hora": 1, "estado": 1})}
        salida = []
        for d in docs:
            t = catalogo().get(d["televisora_id"])
            j = juegos.get(d["juego_id"], {})
            if not t:
                continue
            salida.append({"tele": tele_vista(t), "estado": d["estado"], "pago": d.get("pago"), "aficionados": d.get("aficionados"),
                           "juego_id": d["juego_id"], "local": (j.get("equipo_local") or {}).get("nombre"),
                           "visita": (j.get("equipo_visitante") or {}).get("nombre"), "fecha": j.get("fecha") or d.get("fecha"),
                           "sigla": d.get("sigla")})
        return salida
    except Exception as e:
        print(f"[corporativos] invitaciones del jugador: {e}")
        return []


def invitaciones_por_jugador(user_id, jugador_ids: List[int], por_jugador: int = 10) -> Dict[int, List[dict]]:
    """{jugador_id: [invitaciones a TV, la más reciente primero]} de varios jugadores en una sola consulta (detalle de
    cada representado en el perfil del corporativo). Incluye las programadas y las ya realizadas, con el partido."""
    if not jugador_ids:
        return {}
    try:
        from bson import ObjectId
        from services.fecha_service import formatear_fecha_es
        docs = list(db[COL_INV].find({"universo_id": user_id, "jugador_id": {"$in": [int(j) for j in jugador_ids]},
                                       "estado": {"$in": ["PROGRAMADA", "REALIZADA"]}},
                                      {"jugador_id": 1, "juego_id": 1, "televisora_id": 1, "estado": 1, "pago": 1, "aficionados": 1,
                                       "fecha": 1, "hora": 1, "decidido_seq": 1}).sort("decidido_seq", -1))
        ids = {ObjectId(d["juego_id"]) for d in docs if ObjectId.is_valid(d.get("juego_id", ""))}
        juegos = {str(j["_id"]): j for j in db["juegos"].find({"_id": {"$in": list(ids)}},
                                                              {"equipo_local.nombre": 1, "equipo_local.bandera": 1, "equipo_visitante.nombre": 1,
                                                               "equipo_visitante.bandera": 1, "fecha": 1, "hora": 1})}
        cat = catalogo()
        salida: Dict[int, List[dict]] = {}
        for d in docs:
            t = cat.get(d["televisora_id"])
            lista = salida.setdefault(d["jugador_id"], [])
            if not t or len(lista) >= por_jugador:
                continue
            j = juegos.get(d["juego_id"], {})
            fecha = j.get("fecha") or d.get("fecha")
            vista = tele_vista(t)
            lista.append({"cadena": vista["nombre"], "logo": vista["logo"], "tele_id": vista["id"], "papel": vista.get("papel_nombre", ""),
                          "estado": d["estado"], "pago": d.get("pago"), "aficionados": d.get("aficionados"), "juego_id": d["juego_id"],
                          "local": (j.get("equipo_local") or {}).get("nombre"), "visita": (j.get("equipo_visitante") or {}).get("nombre"),
                          "bandera_local": (j.get("equipo_local") or {}).get("bandera"), "bandera_visita": (j.get("equipo_visitante") or {}).get("bandera"),
                          "fecha": formatear_fecha_es(fecha) if fecha else "", "hora": j.get("hora") or d.get("hora")})
        return salida
    except Exception as e:
        print(f"[corporativos] invitaciones a TV de la cartera: {e}")
        return {}


def invitaciones_programadas(user_id, sigla: str) -> Dict[int, dict]:
    """{jugador_id: invitación} de tus jugadores con una invitación por delante (chip de la cartera e Ingresos)."""
    salida = {}
    for d in db[COL_INV].find({"universo_id": user_id, "sigla": sigla, "estado": "PROGRAMADA"}):
        t = catalogo().get(d["televisora_id"])
        if t:
            salida[d["jugador_id"]] = {"tele": tele_vista(t), "fecha": d.get("fecha"), "hora": d.get("hora"), "juego_id": d["juego_id"]}
    return salida
