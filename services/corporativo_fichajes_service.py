"""
Corporativos Deportivos — mercado de fichajes (fase 3).

Tipos de `corp_ofertas`:
  FICHAJE      el CEO ofrece una prima a un LIBRE; se resuelve PARTIDOS_RESPUESTA_FICHAJE partidos después.
  TRASPASO     el CEO ofrece un monto al corporativo rival por uno de sus representados (solo en ventana de
               traspasos) + la prima de referencia al representado. Pagar la cláusula obliga al rival a vender;
               si no, la IA acepta (>= lo que pide su perfil), contraoferta (>= 85% de eso) o rechaza. El
               representado decide igual (más fácil si está descontento).
  CONTRAOFERTA la IA pide un monto mayor por un TRASPASO; el CEO acepta (se firma al instante) o la deja vencer.
  PROPUESTA    un talento libre se ofrece al corporativo del CEO pidiendo una prima: aceptar firma al instante.
  OFERTA_IA    un rival ofrece un monto por una figura del CEO: aceptar la vende al instante.
  SALIDA       un representado del CEO con satisfacción < 30 pide irse: liberarlo (gratis) o negarse (-10 de
               satisfacción y los rivales huelen la oportunidad).
Lo que resuelve el sistema corre dentro de poner_al_dia (sobre el `Estado` en memoria de corporativo_ciclo_service);
lo que acepta el CEO corre con el candado del universo. Todo lo aleatorio con semilla (universo, oferta/ciclo).
"""
from datetime import datetime
from typing import Optional

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from config import corporativos as C
from services import corporativo_reglas as R
from services import corporativo_universo_service as U
from services.corporativo_mercado_service import afines, valores

db = U.db


# --- Helpers -------------------------------------------------------------------------------------
def nuevo_contrato(uid, sigla: str, tipo: str, ref_id: int, prima: int, duracion: int, ciclo: int, origen: str) -> dict:
    fase = None
    if tipo == "seleccion":
        f = db["internacional"].find_one({"id": ref_id}, {"fase_eliminatoria": 1, "estado": 1})
        fase = [f.get("fase_eliminatoria"), f.get("estado")] if f else None
    return {"universo_id": uid, "sigla": sigla, "tipo": tipo, "ref_id": ref_id, "activo": True,
            "valor_firma": _valor(tipo, ref_id), "prima": int(prima), "desde_ciclo": ciclo, "hasta_ciclo": ciclo + duracion,
            "satisfaccion": C.SATISFACCION_INICIAL, "ciclos_sin_jugar": 0, "renta_total": 0, "honorarios_total": 0,
            "origen": origen, "creado_en": datetime.utcnow(), "foto_fase": fase}


def _valor(tipo: str, ref_id: int) -> int:
    v = valores()
    return int((v["selecciones"] if tipo == "seleccion" else v["jugadores"]).get(ref_id, 0))


def nombre_ref(tipo: str, ref_id: int) -> str:
    v = valores()
    return (v["info_paises"] if tipo == "seleccion" else v["info_jugadores"]).get(ref_id, {}).get("nombre", "?")


def _pais_de(tipo: str, ref_id: int) -> Optional[int]:
    return ref_id if tipo == "seleccion" else valores()["info_jugadores"].get(ref_id, {}).get("pais_id")


def calidad_cartera(contratos: list, sigla: str) -> float:
    """0-100: percentil medio de los jugadores representados (la "vidriera" del corporativo)."""
    pct = valores()["percentil"]
    xs = [pct.get(c["ref_id"], 0) for c in contratos if c["activo"] and c["sigla"] == sigla and c["tipo"] == "jugador"]
    return round(100 * sum(xs) / len(xs), 1) if xs else 30.0


def base_atractivo(corp: dict, fama: float, tipo: str, ref_id: int, cartera: float) -> float:
    """Parte del atractivo que no depende de la prima (para mostrar la probabilidad en vivo en el mercado)."""
    p = C.PESOS_ATRACTIVO
    afin = _pais_de(tipo, ref_id) in afines(corp["sigla"])
    return p["reputacion"] * corp["reputacion"] + p["fama"] * fama + p["afinidad"] * (100 if afin else 0) + p["cartera"] * cartera


def probabilidad(corp: dict, fama: float, tipo: str, ref_id: int, prima: float, cartera: float, satisfaccion=None) -> float:
    base = base_atractivo(corp, fama, tipo, ref_id, cartera)
    p = (base + C.PESOS_ATRACTIVO["oferta"] * R.puntaje_oferta(prima, _valor(tipo, ref_id))) / 100
    if satisfaccion is not None and satisfaccion < C.SATISFACCION_PIDE_SALIR:
        p += C.BONO_SATISFACCION_CAMBIO
    return R.limitar(p, *C.PROBABILIDAD_ACEPTA)


def _insertar_oferta(doc: dict) -> Optional[dict]:
    try:
        db["corp_ofertas"].insert_one(doc)
        return doc
    except DuplicateKeyError:
        return None


def _mov(estado_o_none, uid, sigla, ciclo, tipo, monto, detalle):
    doc = {"universo_id": uid, "sigla": sigla, "ciclo": ciclo, "tipo": tipo, "monto": int(monto), "detalle": detalle,
           "creado_en": datetime.utcnow()}
    if estado_o_none is not None:
        estado_o_none.movimientos.append(doc)
    else:
        db["corp_movimientos"].insert_one(doc)


# --- Dentro de poner_al_dia: resolver ofertas del CEO --------------------------------------------
def resolver_pendientes(estado, universo: dict, seq: int, ciclo: int) -> None:
    """Resuelve las ofertas FICHAJE/TRASPASO cuya respuesta tocaba en este partido."""
    uid = universo["_id"]
    for o in db["corp_ofertas"].find({"universo_id": uid, "estado": "PENDIENTE", "tipo": {"$in": ["FICHAJE", "TRASPASO"]},
                                      "resolver_seq": {"$lte": seq}}):
        comprador = estado.corps.get(o["sigla"])
        if not comprador or not comprador.get("es_del_usuario"):
            _cerrar_oferta(o, "CANCELADA", "Ya no diriges ese corporativo")
            continue
        nombre = nombre_ref(o["ref_tipo"], o["ref_id"])
        actual = (estado.por_seleccion if o["ref_tipo"] == "seleccion" else estado.por_jugador).get(o["ref_id"])
        rng = R.semilla(uid, "oferta", o["_id"])
        cartera = calidad_cartera(estado.contratos, o["sigla"])
        if o["tipo"] == "FICHAJE":
            if actual:
                _cerrar_oferta(o, "RECHAZADA", f"{nombre} firmó con {actual['sigla']} antes de responderte")
            elif comprador["capital"] < o["prima"]:
                _cerrar_oferta(o, "RECHAZADA", "No había capital para pagar la prima al momento de firmar")
            elif rng.random() < probabilidad(comprador, universo["fama"], o["ref_tipo"], o["ref_id"], o["prima"], cartera):
                _firmar(estado, comprador, o, ciclo, "FICHAJE")
                _cerrar_oferta(o, "ACEPTADA", f"{nombre} aceptó tu oferta")
                U.dar_xp(uid, "CORP_FICHAJE", o["_id"], ("PRIMER_FICHAJE",))
            else:
                _cerrar_oferta(o, "RECHAZADA", f"{nombre} prefirió no firmar")
        else:  # TRASPASO
            if not actual or actual["sigla"] != o["sigla_vendedor"]:
                _cerrar_oferta(o, "RECHAZADA", f"{nombre} ya no está en {o['sigla_vendedor']}")
                continue
            vendedor = estado.corps[o["sigla_vendedor"]]
            valor = _valor(o["ref_tipo"], o["ref_id"])
            pide = int(valor * C.IA_MULTIPLO_VENTA.get(C.CORPORATIVO_POR_SIGLA[o["sigla_vendedor"]]["perfil"], C.IA_MULTIPLO_VENTA["default"]))
            clausula = int(valor * C.CLAUSULA_RESCISION_MULTIPLO)
            costo = o["monto"] + o["prima"]
            if comprador["capital"] < costo:
                _cerrar_oferta(o, "RECHAZADA", "No había capital para cerrar el traspaso")
            elif o["monto"] < clausula and o["monto"] < pide:
                if o["monto"] >= pide * C.CONTRAOFERTA_UMBRAL:
                    _insertar_oferta({**{k: o[k] for k in ("universo_id", "sigla", "sigla_vendedor", "ref_tipo", "ref_id", "prima", "duracion")},
                                      "_id": f"{o['_id']}:contra", "tipo": "CONTRAOFERTA", "monto": pide, "ciclo": ciclo,
                                      "vence_ciclo": ciclo + C.CICLOS_VENCE_PROPUESTA, "estado": "PENDIENTE", "creada_en": datetime.utcnow()})
                    _cerrar_oferta(o, "CONTRAOFERTA", f"{o['sigla_vendedor']} pide {pide:,} por {nombre}")
                else:
                    _cerrar_oferta(o, "RECHAZADA", f"{o['sigla_vendedor']} no vende a {nombre} por ese monto")
            elif rng.random() < probabilidad(comprador, universo["fama"], o["ref_tipo"], o["ref_id"], o["prima"], cartera, actual["satisfaccion"]):
                _traspasar(estado, comprador, vendedor, actual, o, ciclo)
                _cerrar_oferta(o, "ACEPTADA", f"{nombre} llega desde {o['sigla_vendedor']}")
                U.dar_xp(uid, "CORP_FICHAJE", o["_id"], ("PRIMER_FICHAJE",))
            else:
                _cerrar_oferta(o, "RECHAZADA", f"{o['sigla_vendedor']} aceptó, pero {nombre} no quiso cambiar de corporativo")
        U.avisar(uid, ciclo, "FICHAJE", "Respuesta a tu oferta", db["corp_ofertas"].find_one({"_id": o["_id"]})["resultado"],
                 "bi-pen-fill", clave=f"resp:{o['_id']}")


def _cerrar_oferta(o: dict, estado: str, resultado: str) -> None:
    db["corp_ofertas"].update_one({"_id": o["_id"]}, {"$set": {"estado": estado, "resultado": resultado, "resuelta_en": datetime.utcnow()}})


def _firmar(estado, corp: dict, o: dict, ciclo: int, origen: str) -> None:
    corp["capital"] -= o["prima"]
    corp["ciclo_actual"]["fichajes"] = corp["ciclo_actual"].get("fichajes", 0) + 1
    if corp.get("es_del_usuario") and o["ref_tipo"] == "jugador" and _es_top50(o["ref_id"]):   # fama: fichaje de un top 50
        corp["ciclo_actual"].setdefault("fama", {})["top50"] = nombre_ref("jugador", o["ref_id"])
    estado.agregar_contrato(nuevo_contrato(estado.uid, corp["sigla"], o["ref_tipo"], o["ref_id"], o["prima"], o["duracion"], ciclo, origen))
    estado.mover(corp["sigla"], ciclo, "FICHAJE", -o["prima"], f"Prima de firma de {nombre_ref(o['ref_tipo'], o['ref_id'])}")


def _es_top50(jugador_id: int) -> bool:
    v = valores()["jugadores"]
    if jugador_id not in v:
        return False
    return sum(1 for x in v.values() if x > v[jugador_id]) < 50


def _traspasar(estado, comprador: dict, vendedor: dict, contrato: dict, o: dict, ciclo: int) -> None:
    estado.terminar_contrato(contrato, ciclo, f"TRASPASO:{comprador['sigla']}")
    vendedor["capital"] += o["monto"]
    comprador["capital"] -= o["monto"]
    estado.mover(comprador["sigla"], ciclo, "TRASPASO", -o["monto"], f"Traspaso de {nombre_ref(o['ref_tipo'], o['ref_id'])} desde {vendedor['sigla']}")
    estado.mover(vendedor["sigla"], ciclo, "TRASPASO", o["monto"], f"Venta de {nombre_ref(o['ref_tipo'], o['ref_id'])} a {comprador['sigla']}")
    _firmar(estado, comprador, o, ciclo, "TRASPASO")
    # el costo de adquisición (prima + traspaso) se amortiza en la duración del contrato, como en los clubes:
    # pagar de más por un traspaso pesa en la utilidad de cada ciclo y el directorio lo ve
    estado.contratos[-1]["prima"] = o["prima"] + o["monto"]


# --- Dentro de poner_al_dia: el mercado en el cierre de ciclo ------------------------------------
def cerrar_ciclo_mercado(estado, universo: dict, ciclo: int) -> None:
    uid = universo["_id"]
    db["corp_ofertas"].update_many({"universo_id": uid, "estado": "PENDIENTE", "tipo": {"$in": ["PROPUESTA", "OFERTA_IA", "CONTRAOFERTA"]},
                                    "vence_ciclo": {"$lte": ciclo}}, {"$set": {"estado": "VENCIDA"}})
    # Un pedido de salida ignorado cuenta como negado
    for o in db["corp_ofertas"].find({"universo_id": uid, "estado": "PENDIENTE", "tipo": "SALIDA", "vence_ciclo": {"$lte": ciclo}}):
        c = estado.por_seleccion.get(o["ref_id"]) if o["ref_tipo"] == "seleccion" else estado.por_jugador.get(o["ref_id"])
        if c:
            c["satisfaccion"] = max(0, c["satisfaccion"] + C.SATISFACCION["salida_negada"])
            estado.tocar(c)
        _cerrar_oferta(o, "NEGADA", "No respondiste: el representado se queda, pero más descontento")

    sigla_usuario = next((s for s, c in estado.corps.items() if c.get("es_del_usuario")), None)
    ventana = U.ventana_traspasos(ciclo)
    rng = R.semilla(uid, "mercado", ciclo)
    _ia_fichajes(estado, universo, ciclo, rng)
    _ia_limpieza(estado, ciclo)
    if sigla_usuario and universo.get("estado") == "EN_CARGO":
        _pedidos_salida(estado, uid, sigla_usuario, ciclo)
        _propuestas_entrantes(estado, universo, sigla_usuario, ciclo, rng)
        if ventana["abierta"]:
            _ofertas_ia_por_figuras(estado, uid, sigla_usuario, ciclo, rng)


def _candidatos_libres(estado, tipo: str) -> list:
    v = valores()
    ocupados = estado.ocupados()
    fuente = v["selecciones"] if tipo == "seleccion" else v["jugadores"]
    return [i for i in fuente if (tipo, i) not in ocupados]


def _ia_fichajes(estado, universo: dict, ciclo: int, rng) -> None:
    v = valores()
    pct = v["percentil"]
    for sigla, corp in estado.corps.items():
        if corp.get("es_del_usuario"):
            continue
        perfil = C.PERFILES_IA[C.CORPORATIVO_POR_SIGLA[sigla]["perfil"]]
        region = afines(sigla)
        for _ in range(perfil["fichajes"]):
            if rng.random() < perfil["prob_seleccion"]:
                tipo = "seleccion"
                pool = _candidatos_libres(estado, tipo)
                # región de afinidad y, a igualdad, mejor ranking
                pesos = [(C.PESO_AFINIDAD_IA if p in region else 1.0) * (1 + (212 - (v["info_paises"].get(p, {}).get("rankin") or 211)) / 211)
                         for p in pool]
            else:
                tipo = "jugador"
                pmin, pmax = perfil["percentil"]
                pool = [j for j in _candidatos_libres(estado, tipo) if pmin <= pct.get(j, 0) <= pmax
                        and (v["info_jugadores"].get(j, {}).get("edad") or 30) <= perfil["edad"]]
                # Leyendas: tope por corporativo y menos peso en el sorteo (que no se las lleven todas de una)
                leyendas_propias = sum(1 for c in estado.contratos if c["activo"] and c["sigla"] == sigla and c["tipo"] == "jugador"
                                       and v["info_jugadores"].get(c["ref_id"], {}).get("leyenda"))
                if leyendas_propias >= C.MAX_LEYENDAS_IA_POR_CORP:
                    pool = [j for j in pool if not v["info_jugadores"].get(j, {}).get("leyenda")]
                if len(pool) > 400:
                    pool = rng.sample(pool, 400)
                pesos = [(C.PESO_AFINIDAD_IA if v["info_jugadores"].get(j, {}).get("pais_id") in region else 1.0)
                         * (C.PESO_LEYENDA_IA if v["info_jugadores"].get(j, {}).get("leyenda") else 1.0) for j in pool]
            if not pool:
                continue
            ref = rng.choices(pool, weights=pesos)[0]
            prima = int(R.prima_referencia(_valor(tipo, ref)) * perfil["multiplo"])
            if prima > corp["capital"] * C.IA_PRESUPUESTO_FICHAJE:
                continue
            cartera = calidad_cartera(estado.contratos, sigla)
            if rng.random() < probabilidad(corp, 50, tipo, ref, prima, cartera):
                corp["capital"] -= prima
                duracion = rng.randint(*C.DURACION_CONTRATO)
                estado.agregar_contrato(nuevo_contrato(estado.uid, sigla, tipo, ref, prima, duracion, ciclo, "FICHAJE_IA"))


def _ia_limpieza(estado, ciclo: int) -> None:
    """La IA suelta a los que no juegan hace rato y a los descontentos (quedan libres para el mercado)."""
    for c in list(estado.contratos):
        if not c["activo"] or estado.corps[c["sigla"]].get("es_del_usuario"):
            continue
        if c.get("ciclos_sin_jugar", 0) >= C.IA_CICLOS_SIN_JUGAR_RESCINDE and c["tipo"] == "jugador":
            costo = int(R.honorario(c["tipo"], _valor(c["tipo"], c["ref_id"])) * max(0, c["hasta_ciclo"] - ciclo) * C.RESCISION_FRACCION_RESTANTE)
            estado.corps[c["sigla"]]["capital"] -= costo
            estado.terminar_contrato(c, ciclo, "RESCINDIDO_IA")
        elif c["satisfaccion"] < C.SATISFACCION_PIDE_SALIR:
            estado.terminar_contrato(c, ciclo, "SALIDA")


def _pedidos_salida(estado, uid, sigla: str, ciclo: int) -> None:
    for c in estado.contratos:
        if c["activo"] and c["sigla"] == sigla and c["satisfaccion"] < C.SATISFACCION_PIDE_SALIR and not c.get("pidio_salida_ciclo"):
            c["pidio_salida_ciclo"] = ciclo
            estado.tocar(c)
            nombre = nombre_ref(c["tipo"], c["ref_id"])
            _insertar_oferta({"_id": f"{uid}:salida:{c['_id']}:{ciclo}", "universo_id": uid, "tipo": "SALIDA", "sigla": sigla,
                              "ref_tipo": c["tipo"], "ref_id": c["ref_id"], "contrato_id": c["_id"], "ciclo": ciclo,
                              "vence_ciclo": ciclo + C.CICLOS_VENCE_PROPUESTA, "estado": "PENDIENTE", "creada_en": datetime.utcnow()})
            U.avisar(uid, ciclo, "SALIDA", f"{nombre} quiere irse",
                     f"La satisfacción de {nombre} cayó a {c['satisfaccion']}: pide que lo liberes.", "bi-emoji-frown-fill",
                     clave=f"salida:{c['_id']}:{ciclo}")


def _propuestas_entrantes(estado, universo: dict, sigla: str, ciclo: int, rng) -> None:
    corp = estado.corps[sigla]
    v = valores()
    n = rng.randint(*C.PROPUESTAS_ENTRANTES_POR_CICLO)
    # Se ofrecen talentos acordes a la vidriera del corporativo: reputación alta atrae mejores percentiles
    centro = corp["reputacion"] / 100
    pool = [j for j in _candidatos_libres(estado, "jugador") if abs(v["percentil"].get(j, 0) - centro) < 0.2]
    for ref in rng.sample(pool, min(n, len(pool))):
        prima = int(R.prima_referencia(_valor("jugador", ref)) * rng.uniform(*C.PROPUESTA_PRIMA_RANGO))
        nombre = nombre_ref("jugador", ref)
        if _insertar_oferta({"_id": f"{universo['_id']}:prop:{ciclo}:{ref}", "universo_id": universo["_id"], "tipo": "PROPUESTA",
                             "sigla": sigla, "ref_tipo": "jugador", "ref_id": ref, "prima": prima,
                             "duracion": rng.randint(*C.DURACION_CONTRATO), "ciclo": ciclo,
                             "vence_ciclo": ciclo + C.CICLOS_VENCE_PROPUESTA, "estado": "PENDIENTE", "creada_en": datetime.utcnow()}):
            U.avisar(universo["_id"], ciclo, "PROPUESTA", f"{nombre} quiere trabajar con ustedes",
                     f"Pide una prima de {prima:,} para firmar.", "bi-person-plus-fill", clave=f"prop:{ciclo}:{ref}")


def _ofertas_ia_por_figuras(estado, uid, sigla: str, ciclo: int, rng) -> None:
    mios = sorted([c for c in estado.contratos if c["activo"] and c["sigla"] == sigla],
                  key=lambda c: -_valor(c["tipo"], c["ref_id"]))[:5]
    if not mios or rng.random() > C.PROB_OFERTA_IA_POR_ESTRELLA:
        return
    c = rng.choice(mios)
    rivales = [s for s, x in estado.corps.items() if s != sigla]
    comprador = rng.choice(rivales)
    monto = int(_valor(c["tipo"], c["ref_id"]) * rng.uniform(*C.MULTIPLO_OFERTA_IA))
    if monto > estado.corps[comprador]["capital"] * 0.5:
        return
    nombre = nombre_ref(c["tipo"], c["ref_id"])
    if _insertar_oferta({"_id": f"{uid}:oia:{ciclo}:{c['_id']}", "universo_id": uid, "tipo": "OFERTA_IA", "sigla": sigla,
                         "sigla_comprador": comprador, "ref_tipo": c["tipo"], "ref_id": c["ref_id"], "contrato_id": c["_id"],
                         "monto": monto, "ciclo": ciclo, "vence_ciclo": ciclo + C.CICLOS_VENCE_PROPUESTA, "estado": "PENDIENTE",
                         "creada_en": datetime.utcnow()}):
        U.avisar(uid, ciclo, "OFERTA_IA", f"{comprador} ofrece {monto:,} por {nombre}",
                 "Puedes aceptar la venta (el monto entra al capital) o rechazarla.", "bi-cash-stack", clave=f"oia:{ciclo}:{c['_id']}")


# --- Acciones del CEO ----------------------------------------------------------------------------
def _cargo(user_id) -> tuple:
    universo = U.obtener_universo(user_id)
    if universo and universo["estado"] == "PREAVISO":
        raise ValueError("Durante el preaviso no puedes operar en el mercado")
    if not universo or universo["estado"] != "EN_CARGO":
        raise ValueError("Necesitas un cargo de CEO para operar en el mercado")
    sigla = universo["cargo"]["sigla"]
    return universo, sigla, db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": sigla})


def ofertar(user_id, tipo: str, ref_id: int, prima: int, duracion: int, monto: int = 0) -> dict:
    """Oferta del CEO por un libre (FICHAJE) o por un representado de un rival (TRASPASO, solo en ventana)."""
    if tipo not in ("seleccion", "jugador"):
        raise ValueError("Tipo inválido")
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, sigla, corp = _cargo(user_id)
        ciclo = U.ciclo_en_curso(universo)
        valor = _valor(tipo, ref_id)
        if not valor:
            raise ValueError("No existe ese representado")
        ref = R.prima_referencia(valor)
        pmin, pmax = C.PRIMA_RANGO_OFERTA
        if not (ref * pmin <= prima <= ref * pmax):
            raise ValueError(f"La prima tiene que estar entre {int(ref * pmin):,} y {int(ref * pmax):,}")
        if not (C.DURACION_CONTRATO[0] <= duracion <= C.DURACION_CONTRATO[1]):
            raise ValueError("Duración inválida")
        if db["corp_ofertas"].count_documents({"universo_id": user_id, "estado": "PENDIENTE", "tipo": {"$in": ["FICHAJE", "TRASPASO"]}}) >= C.TOPE_OFERTAS_PENDIENTES:
            raise ValueError(f"Ya tienes {C.TOPE_OFERTAS_PENDIENTES} ofertas abiertas: espera las respuestas")
        if db["corp_ofertas"].find_one({"universo_id": user_id, "estado": "PENDIENTE", "ref_tipo": tipo, "ref_id": ref_id,
                                        "tipo": {"$in": ["FICHAJE", "TRASPASO"]}}):
            raise ValueError("Ya tienes una oferta abierta por él")
        actual = db["corp_contratos"].find_one({"universo_id": user_id, "tipo": tipo, "ref_id": ref_id, "activo": True})
        doc = {"_id": f"{user_id}:fich:{tipo}:{ref_id}:{U.seq_actual()}", "universo_id": user_id, "sigla": sigla, "ref_tipo": tipo,
               "ref_id": ref_id, "prima": int(prima), "duracion": int(duracion), "ciclo": ciclo,
               "resolver_seq": U.seq_actual() + C.PARTIDOS_RESPUESTA_FICHAJE, "estado": "PENDIENTE", "creada_en": datetime.utcnow()}
        if actual:
            if actual["sigla"] == sigla:
                raise ValueError("Ya lo representas")
            if not U.ventana_traspasos(ciclo)["abierta"]:
                raise ValueError("La ventana de traspasos está cerrada: solo puedes ofertar por libres")
            if monto <= 0:
                raise ValueError("Indica el monto del traspaso para el corporativo rival")
            doc.update(tipo="TRASPASO", sigla_vendedor=actual["sigla"], monto=int(monto))
        else:
            doc["tipo"] = "FICHAJE"
        if corp["capital"] < doc["prima"] + doc.get("monto", 0):
            raise ValueError("No te alcanza el capital para esa oferta")
        if not _insertar_oferta(doc):
            raise ValueError("Ya enviaste esa oferta")
    return {"ok": True, "tipo": doc["tipo"], "responde_en": C.PARTIDOS_RESPUESTA_FICHAJE, "nombre": nombre_ref(tipo, ref_id)}


def cancelar_oferta(user_id, oferta_id: str) -> dict:
    r = db["corp_ofertas"].update_one({"_id": oferta_id, "universo_id": user_id, "estado": "PENDIENTE",
                                       "tipo": {"$in": ["FICHAJE", "TRASPASO"]}}, {"$set": {"estado": "CANCELADA", "resultado": "La retiraste"}})
    if not r.modified_count:
        raise ValueError("La oferta ya no está abierta")
    return {"ok": True}


def responder(user_id, oferta_id: str, aceptar: bool) -> dict:
    """Respuesta del CEO a PROPUESTA / OFERTA_IA / SALIDA / CONTRAOFERTA."""
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, sigla, corp = _cargo(user_id)
        ciclo = U.ciclo_en_curso(universo)
        o = db["corp_ofertas"].find_one({"_id": oferta_id, "universo_id": user_id, "estado": "PENDIENTE",
                                         "tipo": {"$in": ["PROPUESTA", "OFERTA_IA", "SALIDA", "CONTRAOFERTA"]}})
        if not o or o["sigla"] != sigla:
            raise ValueError("La propuesta ya no está disponible")
        nombre = nombre_ref(o["ref_tipo"], o["ref_id"])
        if not aceptar:
            if o["tipo"] == "SALIDA":
                db["corp_contratos"].update_one({"_id": o["contrato_id"]}, {"$inc": {"satisfaccion": C.SATISFACCION["salida_negada"]}})
            _cerrar_oferta(o, "RECHAZADA" if o["tipo"] != "SALIDA" else "NEGADA", "La rechazaste")
            return {"ok": True}

        if o["tipo"] in ("PROPUESTA", "CONTRAOFERTA"):
            ocupado = db["corp_contratos"].find_one({"universo_id": user_id, "tipo": o["ref_tipo"], "ref_id": o["ref_id"], "activo": True})
            costo = o["prima"] + (o["monto"] if o["tipo"] == "CONTRAOFERTA" else 0)
            if o["tipo"] == "PROPUESTA" and ocupado:
                _cerrar_oferta(o, "VENCIDA", "Ya firmó con otro")
                raise ValueError(f"{nombre} ya firmó con otro corporativo")
            if o["tipo"] == "CONTRAOFERTA" and (not ocupado or ocupado["sigla"] != o["sigla_vendedor"]):
                _cerrar_oferta(o, "VENCIDA", "Ya no está disponible")
                raise ValueError(f"{nombre} ya no está en {o['sigla_vendedor']}")
            pago = db["corp_corporativos"].find_one_and_update({"_id": corp["_id"], "capital": {"$gte": costo}}, {"$inc": {"capital": -costo}})
            if not pago:
                raise ValueError(f"Capital insuficiente: necesitas {costo:,}")
            if o["tipo"] == "CONTRAOFERTA":
                db["corp_contratos"].update_one({"_id": ocupado["_id"]}, {"$set": {"activo": False, "fin_ciclo": ciclo, "motivo_fin": f"TRASPASO:{sigla}"}})
                db["corp_corporativos"].update_one({"universo_id": user_id, "sigla": o["sigla_vendedor"]}, {"$inc": {"capital": o["monto"]}})
                _mov(None, user_id, sigla, ciclo, "TRASPASO", -o["monto"], f"Traspaso de {nombre} desde {o['sigla_vendedor']}")
            # costo de adquisición amortizable: prima + traspaso (si fue una contraoferta)
            db["corp_contratos"].insert_one(nuevo_contrato(user_id, sigla, o["ref_tipo"], o["ref_id"], costo, o["duracion"], ciclo, o["tipo"]))
            _mov(None, user_id, sigla, ciclo, "FICHAJE", -o["prima"], f"Prima de firma de {nombre}")
            _cerrar_oferta(o, "ACEPTADA", f"Firmaste a {nombre}")
            U.dar_xp(user_id, "CORP_FICHAJE", o["_id"], ("PRIMER_FICHAJE",))
        elif o["tipo"] == "OFERTA_IA":
            c = db["corp_contratos"].find_one({"_id": o["contrato_id"], "activo": True})
            if not c:
                raise ValueError("Ese representado ya no está en tu cartera")
            comprador = db["corp_corporativos"].find_one_and_update({"universo_id": user_id, "sigla": o["sigla_comprador"], "capital": {"$gte": o["monto"]}},
                                                                    {"$inc": {"capital": -o["monto"]}})
            if not comprador:
                _cerrar_oferta(o, "VENCIDA", "El comprador se quedó sin capital")
                raise ValueError(f"{o['sigla_comprador']} ya no puede pagar ese monto")
            db["corp_contratos"].update_one({"_id": c["_id"]}, {"$set": {"activo": False, "fin_ciclo": ciclo, "motivo_fin": f"VENTA:{o['sigla_comprador']}"}})
            duracion = R.semilla(user_id, "venta", o["_id"]).randint(*C.DURACION_CONTRATO)
            db["corp_contratos"].insert_one(nuevo_contrato(user_id, o["sigla_comprador"], c["tipo"], c["ref_id"], 0, duracion, ciclo, "COMPRA_IA"))
            db["corp_corporativos"].update_one({"_id": corp["_id"]}, {"$inc": {"capital": o["monto"]}})
            _mov(None, user_id, sigla, ciclo, "VENTA", o["monto"], f"Venta de {nombre} a {o['sigla_comprador']}")
            _cerrar_oferta(o, "ACEPTADA", f"Vendiste a {nombre}")
        else:  # SALIDA: liberarlo
            db["corp_contratos"].update_one({"_id": o["contrato_id"]}, {"$set": {"activo": False, "fin_ciclo": ciclo, "motivo_fin": "LIBERADO"}})
            _cerrar_oferta(o, "ACEPTADA", f"Liberaste a {nombre}")
    return {"ok": True, "nombre": nombre}


def scouting(user_id) -> dict:
    """Paga COSTO_SCOUTING y revela los libres jóvenes con mejor rendimiento por valor en el Mundial."""
    from services.estadisticas_service import _cache_vista, obtener_estadisticas_generales
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, sigla, corp = _cargo(user_id)
        ciclo = U.ciclo_en_curso(universo)
        if db["corp_scouting"].find_one({"universo_id": user_id, "ciclo": ciclo}):
            raise ValueError("Ya pediste un informe este ciclo")
        pago = db["corp_corporativos"].find_one_and_update({"_id": corp["_id"], "capital": {"$gte": C.COSTO_SCOUTING}},
                                                           {"$inc": {"capital": -C.COSTO_SCOUTING}})
        if not pago:
            raise ValueError(f"El informe cuesta {C.COSTO_SCOUTING:,} de capital")
        obtener_estadisticas_generales()
        agregado = _cache_vista.get("agregado") or {}
        v = valores()
        ocupados = {c["ref_id"] for c in db["corp_contratos"].find({"universo_id": user_id, "tipo": "jugador", "activo": True}, {"ref_id": 1})}

        def puntaje(jid):
            m = agregado[jid]["metricas"]
            aporte = m["partidos"] * 1.5 + m["goles"] * 8 + m["asistencias"] * 5
            return aporte / max(v["jugadores"].get(jid, 1), 1) * 1000

        candidatos = [j for j in agregado if j not in ocupados and (v["info_jugadores"].get(j, {}).get("edad") or 99) <= C.EDAD_MAXIMA_SCOUTING
                      and agregado[j]["metricas"]["partidos"] >= 1]
        elegidos = sorted(candidatos, key=puntaje, reverse=True)[:C.SCOUTING_INFORMES]
        informe = [{"ref_id": j, "nota": f"{agregado[j]['metricas']['partidos']} PJ, {agregado[j]['metricas']['goles']} goles, "
                                        f"{agregado[j]['metricas']['asistencias']} asist. en el Mundial"} for j in elegidos]
        db["corp_scouting"].insert_one({"universo_id": user_id, "ciclo": ciclo, "jugadores": informe, "creado_en": datetime.utcnow()})
        _mov(None, user_id, sigla, ciclo, "SCOUTING", -C.COSTO_SCOUTING, "Informe de scouting")
    return {"ok": True, "informe": [{"nombre": nombre_ref("jugador", x["ref_id"]), **x} for x in informe]}


def marketing(user_id) -> dict:
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, sigla, corp = _cargo(user_id)
        ciclo = U.ciclo_en_curso(universo)
        if corp.get("marketing_ciclo") == ciclo:
            raise ValueError("Ya hiciste una campaña este ciclo")
        if corp["reputacion"] >= 100:
            raise ValueError("La reputación ya está al máximo")
        pago = db["corp_corporativos"].find_one_and_update(
            {"_id": corp["_id"], "capital": {"$gte": C.COSTO_MARKETING}},
            {"$inc": {"capital": -C.COSTO_MARKETING}, "$set": {"marketing_ciclo": ciclo,
                                                              "marketing_hasta_ciclo": ciclo + C.MARKETING_CICLOS - 1,
                                                              "reputacion": min(100, corp["reputacion"] + C.MARKETING_REPUTACION)}})
        if not pago:
            raise ValueError(f"La campaña cuesta {C.COSTO_MARKETING:,} de capital")
        _mov(None, user_id, sigla, ciclo, "MARKETING", -C.COSTO_MARKETING,
             f"Campaña de marketing (+{C.MARKETING_REPUTACION} reputación, patrocinios x{C.MARKETING_BONO_PATROCINIO} por {C.MARKETING_CICLOS} ciclos)")
    return {"ok": True}


def ultimo_scouting(user_id) -> Optional[dict]:
    return db["corp_scouting"].find_one({"universo_id": user_id}, sort=[("ciclo", -1)])
