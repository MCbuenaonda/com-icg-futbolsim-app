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


# --- Giras v2: duran partidos, cobran partido a partido y una gira de jugadores lleva a varios -----------------
def _seq_universo(universo: dict) -> int:
    return universo.get("cursor_seq") or U.seq_actual()


def _giras_en_curso(uid, sigla: Optional[str] = None) -> list:
    q = {"universo_id": uid, "estado": "EN_CURSO"}
    if sigla:
        q["sigla"] = sigla
    return list(db["corp_giras"].find(q))


def _proximo_partido_en(pais_id) -> Optional[int]:
    """Cuántos partidos del torneo faltan para el próximo de esta selección (None si no tiene programado)."""
    d = calendario_paises().get(pais_id)
    return min(d["posiciones"]) if d and d.get("posiciones") else None


def _juega_en_ciclo_activo(pais_id) -> Optional[int]:
    """
    Si la selección todavía tiene partido por jugar en lo que queda del ciclo activo: cuántos partidos del torneo faltan
    para el ÚLTIMO de ellos (None si ya no juega en este ciclo, o porque ya jugó o porque no tiene partido programado).
    """
    d = calendario_paises().get(pais_id)
    if not d or not d.get("posiciones"):
        return None
    seq = U.seq_actual()
    quedan = C.PARTIDOS_POR_CICLO - seq % C.PARTIDOS_POR_CICLO   # partidos que le quedan al ciclo activo
    en_ciclo = [i for i in d["posiciones"] if i < quedan]
    return max(en_ciclo) if en_ciclo else None


def _motivo_no_disponible(uid, c: dict, seq: int, ciclo: int, en_curso: list) -> Optional[str]:
    if any(g["tipo"] == c["tipo"] and g["ref_id"] == c["ref_id"] for g in en_curso):
        return "Ya está de gira"
    if c["tipo"] == "jugador":
        previa = db["corp_giras"].find_one({"universo_id": uid, "tipo": "jugador", "ref_id": c["ref_id"],
                                            "$or": [{"hasta_seq": {"$gt": seq - C.GIRA_JUGADOR_ENFRIAMIENTO_PARTIDOS}},
                                                    {"hasta_seq": None, "ciclo": {"$gt": ciclo - C.GIRA_JUGADOR_ENFRIAMIENTO}}]})
        if previa:
            falta = (previa.get("hasta_seq") or seq) + C.GIRA_JUGADOR_ENFRIAMIENTO_PARTIDOS - seq
            return f"Volvió de gira hace poco: puede salir en ~{max(1, falta)} partidos"
        # Solo sale de gira si su selección ya no juega en el ciclo activo (no juega o ya jugó su partido del ciclo)
        ultimo = _juega_en_ciclo_activo(_pais_de("jugador", c["ref_id"]))
        if ultimo is not None:
            return ("Su selección juega este ciclo: podrá salir de gira cuando juegue "
                    + ("el próximo partido" if ultimo == 0 else f"su partido (en {ultimo + 1} partidos)"))
        return None
    if db["corp_giras"].find_one({"universo_id": uid, "tipo": "seleccion", "ref_id": c["ref_id"], "ciclo": {"$gt": ciclo - C.GIRA_ENFRIAMIENTO}}):
        return f"Hizo una gira hace poco (cada {C.GIRA_ENFRIAMIENTO} ciclos)"
    prox = _proximo_partido_en(c["ref_id"])
    if prox is not None and prox < C.GIRA_SELECCION_PARTIDOS:
        return f"Juega en {prox + 1} partido{'s' if prox else ''}: la gira dura {C.GIRA_SELECCION_PARTIDOS} y no puede tener partidos en medio"
    return None


def _cotizar(uid, c: dict, seq: int, ciclo: int, en_curso: list) -> dict:
    valor = _valor(c["tipo"], c["ref_id"])
    pais = _pais_de(c["tipo"], c["ref_id"])
    pop = _popularidad(c["tipo"], c["ref_id"], valor)
    base = {"contrato_id": str(c["_id"]), "tipo": c["tipo"], "ref_id": c["ref_id"], "nombre": _nombre(c["tipo"], c["ref_id"]),
            "pais_id": pais, "motivo": _motivo_no_disponible(uid, c, seq, ciclo, en_curso)}
    if c["tipo"] == "seleccion":
        lo, hi = C.GIRA_RECAUDACION
        return {**base, "costo": R.gira_costo(valor), "ingreso_min": int(valor * lo * pop / 1.1), "ingreso_max": int(valor * hi * pop / 1.1),
                "partidos": C.GIRA_SELECCION_PARTIDOS, "suma_aficionados": _gira_suma_aficionados(pais, ciclo)}
    costo = R.gira_jugador_costo_v2(valor)
    retorno = R.gira_jugador_retorno(pop, forma_selecciones().get(pais, 0), _forma_jugador(c))
    return {**base, "costo": costo, "ingreso_min": int(costo * retorno * 0.85), "ingreso_max": int(costo * retorno * 1.15),
            "retorno": round(retorno, 2), "partidos": C.GIRA_JUGADOR_PARTIDOS, "aficionados_max": C.GIRA_JUGADOR_AFICIONADOS_MAX,
            "forma_seleccion": round(forma_selecciones().get(pais, 0) * 15)}


def _limites(uid, sigla: str, ciclo: int, en_curso: list) -> dict:
    grupos = {g.get("grupo_id") or g["_id"] for g in en_curso}
    usados = db["corp_giras"].count_documents({"universo_id": uid, "sigla": sigla, "tipo": "jugador", "ciclo": ciclo,
                                               "estado": {"$in": ["EN_CURSO", "COBRADA"]}})
    return {"giras_restantes": max(0, C.GIRAS_SIMULTANEAS - len(grupos)), "jugadores_restantes": max(0, C.GIRA_JUGADORES_POR_CICLO - usados),
            "max_por_gira": C.GIRA_MAX_JUGADORES, "partidos": C.GIRA_JUGADOR_PARTIDOS}


def giras_jugadores(user_id) -> dict:
    """Para el modal de gira grupal: cada jugador de tu corporativo con su cotización y si puede salir, y los límites."""
    from services.corporativo_fichajes_service import _cargo
    universo, sigla, corp = _cargo(user_id)
    ciclo, seq = U.ciclo_en_curso(universo), _seq_universo(universo)
    en_curso = _giras_en_curso(user_id, sigla)
    jugadores = [_cotizar(user_id, c, seq, ciclo, en_curso) for c in U.contratos_activos(user_id, sigla) if c["tipo"] == "jugador"]
    jugadores.sort(key=lambda x: (x["motivo"] is not None, -x["ingreso_max"]))
    return {"jugadores": jugadores, **_limites(user_id, sigla, ciclo, en_curso), "capital": int(corp.get("capital", 0))}


def cotizar_gira(user_id, contrato_id: str) -> dict:
    """Cotización de UNA gira (la de selección; la de jugadores va por giras_jugadores)."""
    universo, sigla, corp, c, ciclo = _contexto(user_id, contrato_id)
    q = _cotizar(user_id, c, _seq_universo(universo), ciclo, _giras_en_curso(user_id, sigla))
    return {**q, "disponible": q["motivo"] is None, "cobra": f"partido a partido durante {q['partidos']} partidos"}


def _gira_suma_aficionados(pais_id, ciclo: int) -> bool:
    """La gira de selección de un usuario suma aficionados reales si nadie hizo otra con ella hace poco (todos los usuarios)."""
    return not db["corp_giras"].find_one({"tipo": "seleccion", "ref_id": pais_id, "es_usuario": True,
                                          "ciclo": {"$gt": ciclo - C.GIRA_ENFRIAMIENTO}})


def _doc_gira(uid, sigla: str, c: dict, seq: int, ciclo: int, grupo_id: str, es_usuario: bool) -> dict:
    """Documento de una gira v2 con su ingreso ya sorteado (se cobra en partes iguales, partido a partido)."""
    valor = _valor(c["tipo"], c["ref_id"])
    pais = _pais_de(c["tipo"], c["ref_id"])
    pop = _popularidad(c["tipo"], c["ref_id"], valor)
    rng = R.semilla(uid, "gira2", str(c["_id"]), seq)
    if c["tipo"] == "seleccion":
        costo, partidos = R.gira_costo(valor), C.GIRA_SELECCION_PARTIDOS
        ingreso = R.gira_recaudacion(valor, pop, rng)
    else:
        costo, partidos = R.gira_jugador_costo_v2(valor), C.GIRA_JUGADOR_PARTIDOS
        ingreso = R.gira_jugador_ingreso_v2(costo, pop, forma_selecciones().get(pais, 0), _forma_jugador(c), rng)
    return {"_id": f"{uid}:{sigla}:{c['tipo']}:{c['ref_id']}:s{seq}", "universo_id": uid, "sigla": sigla, "tipo": c["tipo"],
            "ref_id": c["ref_id"], "contrato_id": str(c["_id"]), "grupo_id": grupo_id, "ciclo": ciclo, "desde_seq": seq + 1,
            "hasta_seq": seq + partidos, "partidos": partidos, "costo": costo, "ingreso": ingreso, "cobrado": 0, "aficionados": None,
            "es_usuario": es_usuario, "suma_aficionados": c["tipo"] == "jugador" or (es_usuario and _gira_suma_aficionados(pais, ciclo)),
            "estado": "EN_CURSO", "creado_en": datetime.utcnow()}


def organizar_gira_jugadores(user_id, contrato_ids: list) -> dict:
    """Gira de varios jugadores a la vez (1 a GIRA_MAX_JUGADORES): cuesta ahora y cobra partido a partido durante la gira."""
    ids = [x for x in dict.fromkeys(contrato_ids or []) if ObjectId.is_valid(x)]
    if not ids:
        raise ValueError("Elige al menos un jugador")
    if len(ids) > C.GIRA_MAX_JUGADORES:
        raise ValueError(f"Una gira lleva como máximo {C.GIRA_MAX_JUGADORES} jugadores")
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        from services.corporativo_fichajes_service import _cargo
        universo, sigla, corp = _cargo(user_id)
        ciclo, seq = U.ciclo_en_curso(universo), _seq_universo(universo)
        en_curso = _giras_en_curso(user_id, sigla)
        lim = _limites(user_id, sigla, ciclo, en_curso)
        if not lim["giras_restantes"]:
            raise ValueError(f"Ya tienes {C.GIRAS_SIMULTANEAS} giras en curso: espera a que vuelva alguna")
        if len(ids) > lim["jugadores_restantes"]:
            raise ValueError(f"Este ciclo solo puedes mandar {lim['jugadores_restantes']} jugador(es) más de gira")
        contratos = list(db["corp_contratos"].find({"_id": {"$in": [ObjectId(x) for x in ids]}, "universo_id": user_id, "sigla": sigla,
                                                     "activo": True, "tipo": "jugador"}))
        if len(contratos) != len(ids):
            raise ValueError("Algún jugador elegido no es de tu corporativo")
        for c in contratos:
            motivo = _motivo_no_disponible(user_id, c, seq, ciclo, en_curso)
            if motivo:
                raise ValueError(f"{_nombre('jugador', c['ref_id'])}: {motivo}")
        grupo = f"{user_id}:{sigla}:g{seq}:{len(en_curso)}"
        docs = [_doc_gira(user_id, sigla, c, seq, ciclo, grupo, True) for c in contratos]
        costo = sum(d["costo"] for d in docs)
        pago = db["corp_corporativos"].find_one_and_update(
            {"_id": corp["_id"], "capital": {"$gte": costo}}, {"$inc": {"capital": -costo, "ciclo_actual.gastos_extra": costo}})
        if not pago:
            raise ValueError(f"La gira cuesta {costo:,} de capital")
        db["corp_giras"].insert_many(docs)
        nombres = ", ".join(_nombre("jugador", d["ref_id"]) for d in docs)
        _mov(user_id, sigla, ciclo, "GIRA", -costo, f"Gira de exhibición de {nombres} (organización)")
    U.dar_xp(user_id, "CORP_GIRA", grupo)
    return {"ok": True, "mensaje": f"¡De gira! {nombres}: costó {costo:,} y cobra partido a partido durante {C.GIRA_JUGADOR_PARTIDOS} partidos."}


def organizar_gira(user_id, contrato_id: str) -> dict:
    """Gira de una selección (o de un solo jugador, que va por la gira grupal)."""
    universo, sigla, corp, c, ciclo = _contexto(user_id, contrato_id)
    if c["tipo"] == "jugador":
        return organizar_gira_jugadores(user_id, [contrato_id])
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, sigla, corp, c, ciclo = _contexto(user_id, contrato_id, "seleccion")
        seq = _seq_universo(universo)
        en_curso = _giras_en_curso(user_id, sigla)
        if not _limites(user_id, sigla, ciclo, en_curso)["giras_restantes"]:
            raise ValueError(f"Ya tienes {C.GIRAS_SIMULTANEAS} giras en curso: espera a que vuelva alguna")
        motivo = _motivo_no_disponible(user_id, c, seq, ciclo, en_curso)
        if motivo:
            raise ValueError(motivo)
        doc = _doc_gira(user_id, sigla, c, seq, ciclo, f"{user_id}:{sigla}:g{seq}:sel{c['ref_id']}", True)
        pago = db["corp_corporativos"].find_one_and_update(
            {"_id": corp["_id"], "capital": {"$gte": doc["costo"]}}, {"$inc": {"capital": -doc["costo"], "ciclo_actual.gastos_extra": doc["costo"]}})
        if not pago:
            raise ValueError(f"La gira cuesta {doc['costo']:,} de capital")
        db["corp_giras"].insert_one(doc)
        _mov(user_id, sigla, ciclo, "GIRA", -doc["costo"], f"Gira de exhibición de {_nombre('seleccion', c['ref_id'])} (organización)")
    U.dar_xp(user_id, "CORP_GIRA", doc["_id"])
    return {"ok": True, "mensaje": f"¡De gira! {_nombre('seleccion', c['ref_id'])} recauda partido a partido durante {doc['partidos']} partidos."}


def _cargar_giras(estado) -> list:
    if getattr(estado, "_giras_v2", None) is None:
        estado._giras_v2 = list(db["corp_giras"].find({"universo_id": estado.uid, "estado": "EN_CURSO"}))
    return estado._giras_v2


def procesar_giras_partido(estado, seq: int, ciclo: int) -> None:
    """Por cada partido registrado (dentro de poner_al_dia): cada gira en curso cobra su parte y, en el último partido,
    vuelve (aficionados, satisfacción y aviso). Si alguna se pasó de fecha (no se procesó a tiempo) cobra lo que le falta."""
    try:
        giras = _cargar_giras(estado)
        if not giras:
            return
        from services import corporativo_marcas_service as M
        M.iniciar_lote()
        por_grupo: dict = {}
        for g in giras:
            if g["estado"] != "EN_CURSO" or seq < g["desde_seq"]:
                continue
            corp = estado.corps.get(g["sigla"])
            if not corp:
                continue
            hecho = min(seq, g["hasta_seq"]) - g["desde_seq"] + 1
            objetivo = g["ingreso"] * hecho // g["partidos"]
            parte = objetivo - g.get("cobrado", 0)
            c = _contrato_por_id(estado, g["contrato_id"])
            if parte:
                corp["capital"] += parte
                corp["ciclo_actual"]["extra"] += parte
                if c:
                    c["renta_total"] = c.get("renta_total", 0) + parte
                    estado.tocar(c)
                g["cobrado"] = objetivo
                grupo = por_grupo.setdefault(g.get("grupo_id") or g["_id"], {"sigla": g["sigla"], "monto": 0, "nombres": [], "fin": []})
                grupo["monto"] += parte
                grupo["nombres"].append(_nombre(g["tipo"], g["ref_id"]))
            cambios = {"cobrado": g["cobrado"]}
            if seq >= g["hasta_seq"]:
                cambios.update(_terminar_gira(estado, g, c, ciclo))
                g["estado"] = "COBRADA"
                por_grupo.setdefault(g.get("grupo_id") or g["_id"], {"sigla": g["sigla"], "monto": 0, "nombres": [], "fin": []})["fin"].append(g)
            M._upd("corp_giras", g["_id"], {"$set": cambios})
        for gid, info in por_grupo.items():
            if info["monto"]:
                estado.mover(info["sigla"], ciclo, "GIRA", info["monto"], f"Gira de {', '.join(dict.fromkeys(info['nombres']))}: recaudación del partido")
            if info["fin"] and estado.corps[info["sigla"]].get("es_del_usuario"):
                total = sum(x["ingreso"] for x in info["fin"])
                costo = sum(x["costo"] for x in info["fin"])
                afic = sum(x.get("aficionados") or 0 for x in info["fin"])
                nombres = ", ".join(_nombre(x["tipo"], x["ref_id"]) for x in info["fin"])
                U.avisar(estado.uid, ciclo, "GIRA", f"Volvió la gira de {nombres}",
                         f"Recaudó {total:,} (costó {costo:,})" + (f" y sumó {afic:,} aficionados." if afic else "."), "bi-airplane-fill",
                         clave=f"gira:{gid}")
    except Exception as e:
        print(f"[corporativos] giras del partido {seq}: {e}")


def _terminar_gira(estado, g: dict, c: Optional[dict], ciclo: int) -> dict:
    """Vuelta de la gira: aficionados (con las reglas globales de siempre) y satisfacción."""
    pais = _pais_de(g["tipo"], g["ref_id"])
    rng = R.semilla(estado.uid, "gira2-afic", g["_id"])
    aficionados = 0
    if g["tipo"] == "seleccion":
        if g.get("es_usuario") and g.get("suma_aficionados"):
            pop = _popularidad("seleccion", g["ref_id"], _valor("seleccion", g["ref_id"]))
            aficionados = _sumar_aficionados_gira(pais, R.gira_aficionados(_aficionados(pais), pop, rng), f"{MOTIVO_GIRA} ({g['sigla']})")
    else:
        aporte = R.aporte_aficionados_jugador(forma_selecciones().get(pais, 0), _forma_jugador(c or {}), rng)
        aficionados = _aporte_agrupado(pais, ciclo, aporte) if aporte else 0
    if c:
        c["satisfaccion"] = min(100, c["satisfaccion"] + C.GIRA_SATISFACCION)
        estado.tocar(c)
    g["aficionados"] = aficionados
    return {"estado": "COBRADA", "aficionados": aficionados}


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
            _ia_gira(estado, sigla, corp, propios, ciclo, rng)


def _ia_gira(estado, sigla: str, corp: dict, propios: list, ciclo: int, rng) -> None:
    """La IA organiza giras v2: una selección sin partidos cerca o 1-2 jugadores (sus giras de selección no suman aficionados)."""
    seq = ciclo * C.PARTIDOS_POR_CICLO
    giras = _cargar_giras(estado)
    if sum(1 for g in giras if g["sigla"] == sigla and g["estado"] == "EN_CURSO") >= C.GIRAS_SIMULTANEAS:
        return
    ocupados = {(g["tipo"], g["ref_id"]) for g in giras if g["estado"] == "EN_CURSO"}
    selecciones = [c for c in propios if c["tipo"] == "seleccion" and (c["tipo"], c["ref_id"]) not in ocupados
                   and (_proximo_partido_en(c["ref_id"]) is None or _proximo_partido_en(c["ref_id"]) >= C.GIRA_SELECCION_PARTIDOS)]
    # Misma regla que el usuario: un jugador sale de gira solo si su selección ya no juega en el ciclo activo
    jugadores = [c for c in propios if c["tipo"] == "jugador" and (c["tipo"], c["ref_id"]) not in ocupados
                 and _juega_en_ciclo_activo(_pais_de("jugador", c["ref_id"])) is None]
    if selecciones and rng.random() < 0.5:
        elegidos = [rng.choice(selecciones)]
    elif jugadores:
        elegidos = rng.sample(jugadores, min(len(jugadores), rng.choice([1, 2])))
    else:
        return
    grupo = f"{estado.uid}:{sigla}:g{seq}:ia"
    docs = [_doc_gira(estado.uid, sigla, c, seq, ciclo, grupo, False) for c in elegidos]
    costo = sum(d["costo"] for d in docs)
    if corp["capital"] < costo * 4:
        return
    from services import corporativo_marcas_service as M
    M.iniciar_lote()
    for d in docs:
        M._ins("corp_giras", d)
        giras.append(d)
    corp["capital"] -= costo
    corp["ciclo_actual"]["gastos_extra"] += costo


# --- Para las vistas -----------------------------------------------------------------------------
def acuerdos_de(universo_id, sigla: str) -> list:
    return list(db["corp_acuerdos"].find({"universo_id": universo_id, "sigla": sigla}).sort("desde_ciclo", -1).limit(30))


def giras_de(universo_id, sigla: str) -> list:
    return list(db["corp_giras"].find({"universo_id": universo_id, "sigla": sigla}).sort([("ciclo", -1), ("desde_seq", -1)]).limit(30))
