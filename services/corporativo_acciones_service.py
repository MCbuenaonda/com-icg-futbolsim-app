"""
Corporativos Deportivos — acciones del CEO entre partidos: acuerdos publicitarios, giras de exhibición (de una
selección o de un jugador) y la conducta de la IA con esas mismas herramientas.

Por qué: una selección juega ~1 vez cada 94 partidos (~4,7 ciclos), así que la mayoría de los ciclos un
representado no genera renta por partidos. Estas acciones dan ingresos (y satisfacción) en esos ciclos vacíos.

Colecciones (todas con universo_id, PERMANENTES como el resto de corp_*):
  corp_acuerdos  {_id, universo_id, sigla, contrato_id, tipo, ref_id, marca, colores, adelanto, pago_ciclo,
                  desde_ciclo, hasta_ciclo, pagos, cobrado, estado ACTIVO|TERMINADO|CORTADO, motivo}
  corp_giras     {_id, universo_id, sigla, tipo seleccion|jugador, ref_id, contrato_id, ciclo, cobra_ciclo, costo,
                  ingreso, aficionados, es_usuario, estado PENDIENTE|COBRADA}
  corp_giras_aficionados  {_id "<pais>:<ciclo>", pais_id, ciclo, aficionados, giras} — aporte agrupado de las giras
                  de jugadores (todos los universos) con tope por selección y ciclo.

Aficionados reales (paises.aficionados, globales): solo las giras de SELECCIÓN del usuario (+1% a +3%, una cada
GIRA_ENFRIAMIENTO ciclos por selección entre todos los usuarios) y un aporte mínimo de las giras de jugadores (0 a 10,
tope TOPE_AFICIONADOS_GIRAS_JUGADOR por selección y ciclo). Las giras de selección de la IA no los tocan.
Las acciones del usuario corren con el candado del universo; el cierre de ciclo, dentro de poner_al_dia.
"""
from datetime import datetime
from typing import Optional

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import corporativos as C
from services import corporativo_reglas as R
from services import corporativo_universo_service as U
from services.corporativo_mercado_service import calendario_paises, partidos_en_ciclos, valores

db = U.db
MOTIVO_GIRA = "🌍 Gira de exhibición"
MOTIVO_GIRAS_JUGADORES = "🌍 Giras de jugadores"


# --- Helpers -------------------------------------------------------------------------------------
def _valor(tipo: str, ref_id: int) -> int:
    v = valores()
    return int((v["selecciones"] if tipo == "seleccion" else v["jugadores"]).get(ref_id, 0))


def _nombre(tipo: str, ref_id: int) -> str:
    v = valores()
    return (v["info_paises"] if tipo == "seleccion" else v["info_jugadores"]).get(ref_id, {}).get("nombre", "?")


def _pais_de(tipo: str, ref_id: int) -> Optional[int]:
    return ref_id if tipo == "seleccion" else valores()["info_jugadores"].get(ref_id, {}).get("pais_id")


def _popularidad(tipo: str, ref_id: int, valor: int) -> float:
    from services.corporativo_ciclo_service import popularidad
    return popularidad(tipo, ref_id, valor)


def _eliminada(pais_id) -> bool:
    d = db["internacional"].find_one({"id": pais_id}, {"estado": 1})
    return not d or str(d.get("estado") or "").startswith("ELIMINADO")


def forma_selecciones() -> dict:
    """{pais_id: puntos de sus últimos 5 partidos / 15} del Mundial activo (para las giras y las señales)."""
    from services.estadisticas_service import _filtro_finalizados
    clave = U.seq_actual()
    if _cache_forma.get("clave") == clave:
        return _cache_forma["datos"]
    puntos: dict = {}
    for j in db["juegos"].find(_filtro_finalizados(), {"equipo_local.id": 1, "equipo_visitante.id": 1, "resultado.ganador_id": 1,
                                                       "resultado.empate": 1, "fecha": 1, "hora": 1}).sort([("fecha", -1), ("hora", -1)]):
        r = j.get("resultado") or {}
        for lado in ("equipo_local", "equipo_visitante"):
            pid = (j.get(lado) or {}).get("id")
            lista = puntos.setdefault(pid, [])
            if len(lista) < 5:
                lista.append(1 if r.get("empate") else (3 if r.get("ganador_id") == pid else 0))
    datos = {pid: sum(p) / 15 for pid, p in puntos.items() if p}
    _cache_forma.update(clave=clave, datos=datos)
    return datos


_cache_forma: dict = {}


def _forma_jugador(contrato: dict) -> float:
    """0..1: si viene jugando con su selección (partidos con el contrato) y aportando (renta por partidos)."""
    partidos = contrato.get("partidos", 0)
    return R.limitar(partidos / 4, 0, 1) * 0.7 + (0.3 if (contrato.get("renta_total") or 0) > 0 else 0)


# --- Acciones del usuario ------------------------------------------------------------------------
def _contexto(user_id, contrato_id: str, tipo: Optional[str] = None):
    from services.corporativo_fichajes_service import _cargo
    universo, sigla, corp = _cargo(user_id)
    if not ObjectId.is_valid(contrato_id):
        raise ValueError("Contrato inválido")
    c = db["corp_contratos"].find_one({"_id": ObjectId(contrato_id), "universo_id": user_id, "sigla": sigla, "activo": True})
    if not c:
        raise ValueError("Ese representado no es de tu corporativo")
    if tipo and c["tipo"] != tipo:
        raise ValueError("Esta acción es para " + ("selecciones" if tipo == "seleccion" else "jugadores"))
    return universo, sigla, corp, c, U.ciclo_en_curso(universo)


def cotizar_acuerdo(user_id, contrato_id: str) -> dict:
    """Lo que pagaría la marca (sin firmar nada): para el modal."""
    universo, sigla, corp, c, ciclo = _contexto(user_id, contrato_id)
    valor = _valor(c["tipo"], c["ref_id"])
    m = R.acuerdo_montos(valor, _popularidad(c["tipo"], c["ref_id"], valor), corp.get("reputacion", 50),
                         R.semilla(user_id, "acuerdo", str(c["_id"]), ciclo))
    marca = _marca(user_id, c, ciclo)
    return {"marca": marca[0], "colores": marca[1:], **m, "total": m["adelanto"] + m["pago_ciclo"] * m["ciclos"],
            "riesgo": "La marca puede cortar el acuerdo si " + ("tu selección pierde por 3 o más o la eliminan"
                                                                 if c["tipo"] == "seleccion" else "el jugador ve una roja o su selección queda eliminada")}


def _marca(uid, c: dict, ciclo: int) -> tuple:
    return R.semilla(uid, "marca", str(c["_id"]), ciclo).choice(C.MARCAS_ACUERDO)


def firmar_acuerdo(user_id, contrato_id: str) -> dict:
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, sigla, corp, c, ciclo = _contexto(user_id, contrato_id)
        if db["corp_acuerdos"].find_one({"universo_id": user_id, "contrato_id": str(c["_id"]), "estado": "ACTIVO"}):
            raise ValueError("Este representado ya tiene un acuerdo publicitario vigente")
        if db["corp_acuerdos"].count_documents({"universo_id": user_id, "sigla": sigla, "estado": "ACTIVO"}) >= C.ACUERDOS_MAX_ACTIVOS:
            raise ValueError(f"Tu corporativo ya tiene {C.ACUERDOS_MAX_ACTIVOS} acuerdos vigentes: espera a que termine alguno")
        doc = _nuevo_acuerdo(user_id, sigla, corp, c, ciclo)
        db["corp_acuerdos"].insert_one(doc)
        db["corp_corporativos"].update_one({"_id": corp["_id"]}, {"$inc": {"capital": doc["adelanto"], "ciclo_actual.extra": doc["adelanto"]}})
        _mov(user_id, sigla, ciclo, "ACUERDO", doc["adelanto"], f"{doc['marca']}: adelanto por {_nombre(c['tipo'], c['ref_id'])}")
    U.dar_xp(user_id, "CORP_ACUERDO", doc["_id"])
    return {"ok": True, "acuerdo": {k: v for k, v in doc.items() if k != "creado_en"}}


def _nuevo_acuerdo(uid, sigla: str, corp: dict, c: dict, ciclo: int) -> dict:
    valor = _valor(c["tipo"], c["ref_id"])
    m = R.acuerdo_montos(valor, _popularidad(c["tipo"], c["ref_id"], valor), corp.get("reputacion", 50),
                         R.semilla(uid, "acuerdo", str(c["_id"]), ciclo))
    marca = _marca(uid, c, ciclo)
    return {"_id": f"{uid}:{sigla}:{c['_id']}:{ciclo}", "universo_id": uid, "sigla": sigla, "contrato_id": str(c["_id"]),
            "tipo": c["tipo"], "ref_id": c["ref_id"], "marca": marca[0], "colores": list(marca[1:]), "adelanto": m["adelanto"],
            "pago_ciclo": m["pago_ciclo"], "desde_ciclo": ciclo, "hasta_ciclo": ciclo + m["ciclos"] - 1, "pagos": 0,
            "cobrado": m["adelanto"], "estado": "ACTIVO", "motivo": None, "creado_en": datetime.utcnow()}


def _gira_validar(user_id, sigla: str, c: dict, ciclo: int, tipo: str):
    if db["corp_giras"].count_documents({"universo_id": user_id, "sigla": sigla, "ciclo": ciclo}) >= C.GIRAS_POR_CICLO:
        raise ValueError("Tu corporativo ya organizó una gira este ciclo")
    enfriamiento = C.GIRA_ENFRIAMIENTO if tipo == "seleccion" else C.GIRA_JUGADOR_ENFRIAMIENTO
    if db["corp_giras"].find_one({"universo_id": user_id, "tipo": tipo, "ref_id": c["ref_id"], "ciclo": {"$gt": ciclo - enfriamiento}}):
        raise ValueError(f"Ya hizo una gira hace poco: puede volver a salir después de {enfriamiento} ciclos")


def cotizar_gira(user_id, contrato_id: str) -> dict:
    universo, sigla, corp, c, ciclo = _contexto(user_id, contrato_id)
    valor = _valor(c["tipo"], c["ref_id"])
    pais = _pais_de(c["tipo"], c["ref_id"])
    pop = _popularidad(c["tipo"], c["ref_id"], valor)
    if c["tipo"] == "seleccion":
        lo, hi = C.GIRA_RECAUDACION
        proximos = partidos_en_ciclos(pais, C.GIRA_CICLOS_SIN_PARTIDO)
        return {"tipo": "seleccion", "costo": R.gira_costo(valor), "ingreso_min": int(valor * lo * pop / 1.1), "ingreso_max": int(valor * hi * pop / 1.1),
                "disponible": proximos == 0, "motivo": (f"Tiene {proximos} partido(s) en los próximos {C.GIRA_CICLOS_SIN_PARTIDO} ciclos: "
                                                        "las giras se hacen cuando no hay partidos" if proximos else None),
                "suma_aficionados": _gira_suma_aficionados(pais, ciclo), "cobra": "al cierre del ciclo siguiente"}
    lo, hi = C.GIRA_JUGADOR_INGRESO
    return {"tipo": "jugador", "costo": R.gira_jugador_costo(valor), "ingreso_min": int(valor * lo * pop / 1.1),
            "ingreso_max": int(valor * hi * pop / 1.1), "disponible": True, "motivo": None,
            "forma_seleccion": round(forma_selecciones().get(pais, 0) * 15), "cobra": "al cierre de este ciclo",
            "aficionados_max": C.GIRA_JUGADOR_AFICIONADOS_MAX}


def _gira_suma_aficionados(pais_id, ciclo: int) -> bool:
    """La gira de selección de un usuario suma aficionados reales si nadie hizo otra con ella hace poco (todos los usuarios)."""
    return not db["corp_giras"].find_one({"tipo": "seleccion", "ref_id": pais_id, "es_usuario": True,
                                          "ciclo": {"$gt": ciclo - C.GIRA_ENFRIAMIENTO}})


def organizar_gira(user_id, contrato_id: str) -> dict:
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, sigla, corp, c, ciclo = _contexto(user_id, contrato_id)
        _gira_validar(user_id, sigla, c, ciclo, c["tipo"])
        valor = _valor(c["tipo"], c["ref_id"])
        pais = _pais_de(c["tipo"], c["ref_id"])
        if c["tipo"] == "seleccion":
            if partidos_en_ciclos(pais, C.GIRA_CICLOS_SIN_PARTIDO):
                raise ValueError("Tiene partidos en los próximos ciclos: las giras se hacen cuando no hay partidos")
            costo, cobra = R.gira_costo(valor), ciclo + 1
        else:
            costo, cobra = R.gira_jugador_costo(valor), ciclo
        pago = db["corp_corporativos"].find_one_and_update(
            {"_id": corp["_id"], "capital": {"$gte": costo}}, {"$inc": {"capital": -costo, "ciclo_actual.gastos_extra": costo}})
        if not pago:
            raise ValueError(f"La gira cuesta {costo:,} de capital")
        doc = {"_id": f"{user_id}:{sigla}:{c['tipo']}:{c['ref_id']}:{ciclo}", "universo_id": user_id, "sigla": sigla, "tipo": c["tipo"],
               "ref_id": c["ref_id"], "contrato_id": str(c["_id"]), "ciclo": ciclo, "cobra_ciclo": cobra, "costo": costo,
               "ingreso": None, "aficionados": None, "es_usuario": True,
               "suma_aficionados": c["tipo"] == "jugador" or _gira_suma_aficionados(pais, ciclo),
               "estado": "PENDIENTE", "creado_en": datetime.utcnow()}
        db["corp_giras"].insert_one(doc)
        _mov(user_id, sigla, ciclo, "GIRA", -costo, f"Gira de exhibición de {_nombre(c['tipo'], c['ref_id'])} (organización)")
    U.dar_xp(user_id, "CORP_GIRA", doc["_id"])
    return {"ok": True, "gira": {k: v for k, v in doc.items() if k != "creado_en"}}


def _mov(uid, sigla, ciclo, tipo, monto, detalle):
    db["corp_movimientos"].insert_one({"universo_id": uid, "sigla": sigla, "ciclo": ciclo, "tipo": tipo, "monto": int(monto),
                                       "detalle": detalle, "creado_en": datetime.utcnow()})


# --- Cierre de ciclo (dentro de poner_al_dia, sobre el Estado en memoria) --------------------------
def cerrar_ciclo_acciones(estado, ciclo: int) -> None:
    """Pagos y cortes de los acuerdos, cobro de las giras (y sus aficionados) y lo que hace la IA."""
    _procesar_acuerdos(estado, ciclo)   # solo los acuerdos viejos, hasta que venzan
    _procesar_giras(estado, ciclo)
    _ia_acciones(estado, ciclo)
    try:   # marcas y patrocinios (usa los eventos del ciclo: se limpian después)
        from services.corporativo_marcas_service import cerrar_ciclo_marcas
        cerrar_ciclo_marcas(estado, ciclo)
    except Exception as e:
        print(f"[corporativos] marcas del ciclo {ciclo}: {e}")
    for c in estado.contratos:   # las marcas de este ciclo ya se usaron
        if c.get("eventos_ciclo"):
            c["eventos_ciclo"] = {}
            estado.tocar(c)


def _contrato_por_id(estado, contrato_id: str) -> Optional[dict]:
    return next((c for c in estado.contratos if str(c["_id"]) == contrato_id), None)


def _procesar_acuerdos(estado, ciclo: int) -> None:
    for a in db["corp_acuerdos"].find({"universo_id": estado.uid, "estado": "ACTIVO", "desde_ciclo": {"$lte": ciclo}}):
        c = _contrato_por_id(estado, a["contrato_id"])
        corp = estado.corps.get(a["sigla"])
        if not corp:
            continue
        if not c or not c["activo"]:
            db["corp_acuerdos"].update_one({"_id": a["_id"]}, {"$set": {"estado": "TERMINADO", "motivo": "Terminó la representación"}})
            continue
        ev = c.get("eventos_ciclo") or {}
        pais = _pais_de(c["tipo"], c["ref_id"])
        motivo = None
        rng = R.semilla(estado.uid, "corte", a["_id"], ciclo)
        if ev.get("roja") and rng.random() < C.ACUERDO_PROB_CORTE["roja"]:
            motivo = "una expulsión"
        elif ev.get("goleada") and rng.random() < C.ACUERDO_PROB_CORTE["goleada"]:
            motivo = "una goleada en contra"
        elif ev.get("eliminada") and rng.random() < C.ACUERDO_PROB_CORTE["eliminada"]:
            motivo = "la eliminación de su selección"
        nombre = _nombre(c["tipo"], c["ref_id"])
        if motivo:
            db["corp_acuerdos"].update_one({"_id": a["_id"]}, {"$set": {"estado": "CORTADO", "motivo": f"La marca cortó tras {motivo}"}})
            if corp.get("es_del_usuario"):
                U.avisar(estado.uid, ciclo, "ACUERDO", f"{a['marca']} cortó el acuerdo con {nombre}",
                         f"Después de {motivo}, la marca decidió no seguir. Te quedas con lo ya cobrado ({a['cobrado']:,}).",
                         "bi-x-circle-fill", clave=f"acuerdo-corte:{a['_id']}")
            continue
        pago = a["pago_ciclo"]
        corp["capital"] += pago
        corp["ciclo_actual"]["extra"] += pago
        c["renta_total"] = c.get("renta_total", 0) + pago
        estado.tocar(c)
        estado.mover(a["sigla"], ciclo, "ACUERDO", pago, f"{a['marca']}: pago por {nombre}")
        fin = ciclo >= a["hasta_ciclo"]
        db["corp_acuerdos"].update_one({"_id": a["_id"]}, {"$inc": {"pagos": 1, "cobrado": pago},
                                                           "$set": {"estado": "TERMINADO" if fin else "ACTIVO",
                                                                    "motivo": "Cumplido" if fin else None}})


def _procesar_giras(estado, ciclo: int) -> None:
    for g in db["corp_giras"].find({"universo_id": estado.uid, "estado": "PENDIENTE", "cobra_ciclo": {"$lte": ciclo}}):
        corp = estado.corps.get(g["sigla"])
        c = _contrato_por_id(estado, g["contrato_id"])
        if not corp:
            continue
        valor = _valor(g["tipo"], g["ref_id"])
        pop = _popularidad(g["tipo"], g["ref_id"], valor)
        rng = R.semilla(estado.uid, "gira", g["_id"])
        nombre = _nombre(g["tipo"], g["ref_id"])
        pais = _pais_de(g["tipo"], g["ref_id"])
        if g["tipo"] == "seleccion":
            ingreso = R.gira_recaudacion(valor, pop, rng)
            aficionados = 0
            if g.get("es_usuario") and g.get("suma_aficionados"):
                aficionados = _sumar_aficionados_gira(pais, R.gira_aficionados(_aficionados(pais), pop, rng), f"{MOTIVO_GIRA} ({g['sigla']})")
        else:
            ingreso = R.gira_jugador_ingreso(valor, pop, rng)
            aporte = R.aporte_aficionados_jugador(forma_selecciones().get(pais, 0), _forma_jugador(c or {}), rng)
            aficionados = _aporte_agrupado(pais, ciclo, aporte) if aporte else 0
        corp["capital"] += ingreso
        corp["ciclo_actual"]["extra"] += ingreso
        if c:
            c["renta_total"] = c.get("renta_total", 0) + ingreso
            c["satisfaccion"] = min(100, c["satisfaccion"] + C.GIRA_SATISFACCION)
            estado.tocar(c)
        estado.mover(g["sigla"], ciclo, "GIRA", ingreso, f"Gira de {nombre}: recaudación" + (f" (+{aficionados:,} aficionados)" if aficionados else ""))
        db["corp_giras"].update_one({"_id": g["_id"]}, {"$set": {"estado": "COBRADA", "ingreso": ingreso, "aficionados": aficionados}})
        if corp.get("es_del_usuario"):
            U.avisar(estado.uid, ciclo, "GIRA", f"Volvió la gira de {nombre}",
                     f"Recaudación {ingreso:,} (costó {g['costo']:,})" + (f" y {aficionados:,} aficionados nuevos para su selección." if aficionados else "."),
                     "bi-airplane-fill", clave=f"gira:{g['_id']}")


def _aficionados(pais_id) -> int:
    return int((db["paises"].find_one({"id": pais_id}, {"aficionados": 1}) or {}).get("aficionados") or C.AFICIONADOS_BASE)


def _sumar_aficionados_gira(pais_id, delta: int, motivo: str) -> int:
    """Gira de selección del usuario: suma aficionados reales (Popularidad) con los helpers de fanbase_service."""
    if not delta or pais_id is None:
        return 0
    try:
        from services.fanbase_service import _aplicar_delta_aficionados, _registrar_historial_aficionados
        total = _aplicar_delta_aficionados(db["paises"], pais_id, delta)
        _registrar_historial_aficionados(pais_id, None, delta, total, motivo)
        return delta
    except Exception as e:
        print(f"[corporativos] no se pudieron sumar los aficionados de la gira: {e}")
        return 0


def _aporte_agrupado(pais_id, ciclo: int, aporte: int) -> int:
    """
    Giras de jugadores: suma un aporte mínimo a su selección con tope por selección y ciclo (entre todos los
    universos) y deja UN registro por selección y ciclo en historial_aficionados («🌍 Giras de jugadores»).
    Devuelve lo que efectivamente sumó.
    """
    if pais_id is None:
        return 0
    clave = f"{pais_id}:{ciclo}"
    try:
        db["corp_giras_aficionados"].update_one({"_id": clave}, {"$setOnInsert": {"pais_id": pais_id, "ciclo": ciclo, "aficionados": 0, "giras": 0}},
                                                upsert=True)
    except DuplicateKeyError:
        pass
    doc = db["corp_giras_aficionados"].find_one({"_id": clave}) or {}
    suma = max(0, min(aporte, C.TOPE_AFICIONADOS_GIRAS_JUGADOR - int(doc.get("aficionados") or 0)))
    if not suma:
        return 0
    act = db["corp_giras_aficionados"].find_one_and_update(
        {"_id": clave, "aficionados": {"$lte": C.TOPE_AFICIONADOS_GIRAS_JUGADOR - suma}},
        {"$inc": {"aficionados": suma, "giras": 1}}, return_document=ReturnDocument.AFTER)
    if not act:
        return 0
    try:
        from services.fanbase_service import _aplicar_delta_aficionados
        total = _aplicar_delta_aficionados(db["paises"], pais_id, suma)
        db["historial_aficionados"].update_one(
            {"_id": f"giras_jugadores:{clave}"},
            {"$set": {"pais_id": pais_id, "partido_id": None, "aficionados_ganados_perdidos": act["aficionados"],
                      "aficionados_totales_resultantes": total,
                      "motivo": f"{MOTIVO_GIRAS_JUGADORES}: +{act['aficionados']} aficionados ({act['giras']} gira{'s' if act['giras'] > 1 else ''})"},
             "$setOnInsert": {"created_at": datetime.now()}}, upsert=True)
    except Exception as e:
        print(f"[corporativos] no se pudo registrar el aporte de las giras de jugadores: {e}")
    return suma


# --- La IA ---------------------------------------------------------------------------------------
def _ia_acciones(estado, ciclo: int) -> None:
    """Los corporativos de la IA también firman acuerdos y organizan giras (más seguido si están en saneamiento).
    Sus giras de SELECCIÓN no tocan los aficionados reales (se multiplicarían con cada universo)."""
    for sigla, corp in estado.corps.items():
        if corp.get("es_del_usuario"):
            continue
        rng = R.semilla(estado.uid, "ia-acciones", sigla, ciclo)
        factor = 2.0 if (corp.get("saneamiento") or {}).get("estado") == "ACTIVO" else 1.0
        propios = [c for c in estado.contratos if c["activo"] and c["sigla"] == sigla]
        if not propios:
            continue
        # (los acuerdos publicitarios los reemplazaron las marcas: corporativo_marcas_service)
        if rng.random() < C.IA_PROB_GIRA * factor:
            selecciones = [c for c in propios if c["tipo"] == "seleccion" and not partidos_en_ciclos(c["ref_id"], C.GIRA_CICLOS_SIN_PARTIDO)]
            candidatos = selecciones or [c for c in propios if c["tipo"] == "jugador"]
            if candidatos and not db["corp_giras"].find_one({"universo_id": estado.uid, "sigla": sigla, "ciclo": ciclo}):
                c = rng.choice(candidatos)
                valor = _valor(c["tipo"], c["ref_id"])
                costo = R.gira_costo(valor) if c["tipo"] == "seleccion" else R.gira_jugador_costo(valor)
                if corp["capital"] >= costo * 4:
                    try:
                        db["corp_giras"].insert_one({"_id": f"{estado.uid}:{sigla}:{c['tipo']}:{c['ref_id']}:{ciclo}", "universo_id": estado.uid,
                                                     "sigla": sigla, "tipo": c["tipo"], "ref_id": c["ref_id"], "contrato_id": str(c["_id"]),
                                                     "ciclo": ciclo, "cobra_ciclo": ciclo + 1, "costo": costo, "ingreso": None,
                                                     "aficionados": None, "es_usuario": False, "suma_aficionados": c["tipo"] == "jugador",
                                                     "estado": "PENDIENTE", "creado_en": datetime.utcnow()})
                        corp["capital"] -= costo
                        corp["ciclo_actual"]["gastos_extra"] += costo
                    except DuplicateKeyError:
                        pass


# --- Para las vistas -----------------------------------------------------------------------------
def acuerdos_de(universo_id, sigla: str) -> list:
    return list(db["corp_acuerdos"].find({"universo_id": universo_id, "sigla": sigla}).sort("desde_ciclo", -1).limit(30))


def giras_de(universo_id, sigla: str) -> list:
    return list(db["corp_giras"].find({"universo_id": universo_id, "sigla": sigla}).sort("ciclo", -1).limit(30))
