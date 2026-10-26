"""
Corporativos Deportivos — carrera del CEO (reglas en config/corporativos.py):
BUSCANDO -> (oferta) -> EN_CARGO -> [headhunting: PREAVISO -> otro cargo] -> RENUNCIA/DESPIDO/FIN_CONTRATO -> PAUSA -> BUSCANDO.

En cada cierre de ciclo (poner_al_dia, sobre el `Estado` en memoria de corporativo_ciclo_service), en este orden:
  pagar_ceo          sueldo base + bono (sobre la utilidad operativa media de la ventana; 25% en acciones bloqueadas)
                     -> usuarios.monto. Idempotente: el asiento de sueldo tiene _id (universo, ciclo).
  evaluar_directorio quiebras, objetivos de la temporada, ranking de ROI contra los otros 9, confianza,
                     ultimátum y despido.
  cerrar_ciclo       vencimiento de ofertas, fin de la pausa, fin del preaviso, cierre de temporada (renovación),
                     ofertas de empleo y headhunting.
Las ofertas de empleo (corp_ofertas_empleo) tienen tipo EMPLEO, HEADHUNTING, RETENCION o RENOVACION; todo con semilla
(universo, ciclo) y _id determinístico.
"""
from datetime import datetime
from statistics import mean
from typing import Optional

from pymongo.errors import DuplicateKeyError

from config import corporativos as C
from services import corporativo_reglas as R
from services import corporativo_universo_service as U
from services.corporativo_universo_service import avisar, ciclo_en_curso, obtener_universo

ESTADOS_CON_CARGO = ("EN_CARGO", "PREAVISO")


def _db():
    return U.db


# --- Ofertas de empleo ---------------------------------------------------------------------------
def _corps_elegibles(universo: dict, solo_tier: Optional[str] = None, tier_minimo: Optional[str] = None) -> list:
    fama = universo["fama"]
    actual = (universo.get("cargo") or {}).get("sigla")
    con_oferta = {o["sigla"] for o in _db()["corp_ofertas_empleo"].find({"universo_id": universo["_id"], "estado": "PENDIENTE"}, {"sigla": 1})}
    return [c for c in C.CORPORATIVOS
            if c["sigla"] != actual and c["sigla"] not in con_oferta
            and C.TIERS[c["tier"]]["fama_minima"] <= fama + C.MARGEN_FAMA_OFERTA
            and (solo_tier is None or c["tier"] == solo_tier)
            and (tier_minimo is None or C.ORDEN_TIER[c["tier"]] >= C.ORDEN_TIER[tier_minimo])]


def _crear_oferta(universo: dict, corp: dict, ciclo: int, tipo: str, rng, mejora: float = 0.0, sueldo: Optional[int] = None,
                  vence: Optional[int] = None) -> Optional[dict]:
    tier = corp["tier"]
    sueldo = sueldo or int(round(R.sueldo_base(tier, universo["fama"]) * (1 + mejora)))
    vence = vence or (C.CICLOS_VENCE_HEADHUNTING if tipo in ("HEADHUNTING", "RETENCION", "RENOVACION") else C.CICLOS_VENCE_OFERTA)
    oferta = {
        "_id": f"{universo['_id']}:{ciclo}:{corp['sigla']}:{tipo}",
        "universo_id": universo["_id"], "sigla": corp["sigla"], "tipo": tipo, "ciclo": ciclo, "vence_ciclo": ciclo + vence,
        "sueldo_base": sueldo, "bono_pct": round(rng.uniform(*C.BONO_PORCENTAJE), 3),
        "objetivos": rng.sample(C.OBJETIVOS_POR_TIER[tier], C.OBJETIVOS_SORTEADOS),
        "estado": "PENDIENTE", "creada_en": datetime.utcnow(),
    }
    try:
        _db()["corp_ofertas_empleo"].insert_one(oferta)
    except DuplicateKeyError:
        return None
    textos = {
        "EMPLEO": (f"Oferta de trabajo de {corp['sigla']}", f"{corp['nombre']} (tier {tier}) te ofrece la dirección general: sueldo base "
                   f"{sueldo:,} por ciclo más {oferta['bono_pct']:.0%} de bono sobre la utilidad.", "bi-envelope-paper-fill"),
        "HEADHUNTING": (f"{corp['sigla']} te quiere", f"Confidencial: {corp['nombre']} (tier {tier}) quiere que seas su CEO. Ofrece "
                        f"{sueldo:,} por ciclo. Si aceptas, cumples un ciclo de preaviso.", "bi-incognito"),
        "RETENCION": (f"{corp['sigla']} quiere retenerte", f"El directorio se enteró de la oferta y te sube el sueldo base a {sueldo:,}.",
                      "bi-hand-thumbs-up-fill"),
        "RENOVACION": (f"{corp['sigla']} te ofrece renovar", f"Renovación por otra temporada: sueldo base {sueldo:,} y objetivos nuevos.",
                       "bi-arrow-repeat"),
    }
    titulo, texto, icono = textos[tipo]
    avisar(universo["_id"], ciclo, tipo, titulo, texto, icono, clave=f"oferta:{oferta['_id']}")
    return oferta


def ofertas_iniciales(universo: dict) -> None:
    """Las 2 primeras ofertas (tier C) llegan a los pocos partidos de activar el módulo."""
    ciclo = ciclo_en_curso(universo)
    rng = R.semilla(universo["_id"], "iniciales")
    candidatos = _corps_elegibles(universo, solo_tier="C")
    for corp in rng.sample(candidatos, min(C.OFERTAS_INICIALES, len(candidatos))):
        _crear_oferta(universo, corp, ciclo, "EMPLEO", rng)


# --- Cierre de ciclo: sueldo ---------------------------------------------------------------------
def pagar_ceo(estado, universo: dict, ciclo: int) -> None:
    """Sueldo + bono del ciclo (sobre la utilidad operativa media de la ventana): se descuenta del capital del corporativo."""
    cargo = universo.get("cargo")
    if universo["estado"] not in ESTADOS_CON_CARGO or not cargo:
        return
    corp = estado.corps[cargo["sigla"]]
    util_op = corp.get("_utilidad", 0)
    previas = [h.get("utilidad_op", h["utilidad"]) for h in (corp.get("historial") or [])[-(C.CICLOS_VENTANA_ROI - 1):]]
    media = mean(previas + [util_op])
    sueldo = cargo["sueldo_base"]
    bono = R.bono_ciclo(cargo["bono_pct"], media, sueldo)
    en_acciones = int(bono * C.FRACCION_BONO_EN_ACCIONES)
    efectivo = sueldo + bono - en_acciones
    comision = int(corp["ciclo_actual"].get("comision_ceo") or 0)   # 5% de las marcas: ya se descontó del ingreso del corporativo
    uid = universo["_id"]
    try:
        _db()["corp_movimientos"].insert_one({"_id": f"{uid}:sueldo:{ciclo}", "universo_id": uid, "sigla": cargo["sigla"], "ciclo": ciclo,
                                             "tipo": "SUELDO_CEO", "monto": -efectivo, "sueldo": sueldo, "bono": bono,
                                             "bono_acciones": en_acciones, "comision": comision,
                                             "detalle": f"Tu sueldo ({sueldo:,})" + (f" + bono ({bono:,}, {en_acciones:,} en acciones)" if bono else "")
                                             + (f" + comisión de marcas ({comision:,})" if comision else ""),
                                             "creado_en": datetime.utcnow()})
        _db()["usuarios"].update_one(U.filtro_usuario(uid), {"$inc": {"monto": efectivo + comision}})
        if en_acciones and corp.get("precio"):
            _db()["corp_universos"].update_one({"_id": uid}, {"$push": {"acciones_bloqueadas": {
                "sigla": cargo["sigla"], "cantidad": round(en_acciones / corp["precio"], 2), "valor_al_otorgar": en_acciones,
                "otorgada_ciclo": ciclo, "consolida_ciclo": ciclo + C.CICLOS_CONSOLIDACION_ACCIONES}}})
    except DuplicateKeyError:
        pass   # este ciclo ya se pagó (reproceso): solo se repite el descuento en memoria del corporativo
    corp["capital"] -= efectivo
    corp["ciclo_actual"]["sueldo"] = efectivo
    corp["_utilidad_op"] = util_op
    corp["_utilidad"] = util_op - efectivo
    corp["_pago_ceo"] = {"sueldo": sueldo, "bono": bono, "acciones": en_acciones, "efectivo": efectivo, "comision": comision}


# --- Cierre de ciclo: directorio -----------------------------------------------------------------
def _roi_ventana(corp: dict) -> float:
    return sum(h["roi"] for h in (corp.get("historial") or [])[-C.CICLOS_VENTANA_ROI:])


def _roi_desde(corp: dict, ciclo_desde: int) -> float:
    return sum(h["roi"] for h in (corp.get("historial") or []) if h["ciclo"] >= ciclo_desde)


def _quiebras(estado, ciclo: int) -> None:
    """Capital negativo: la IA reestructura (vende a precio de remate sus 3 representados más caros) y la acción se desploma."""
    from services.corporativo_fichajes_service import nombre_ref
    for sigla, corp in estado.corps.items():
        if corp["capital"] >= 0:
            continue
        caros = sorted([c for c in estado.contratos if c["activo"] and c["sigla"] == sigla],
                       key=lambda c: -(c.get("valor_actual") or 0))[:3]
        for c in caros:
            corp["capital"] += int((c.get("valor_actual") or 0) * 0.5)
            estado.terminar_contrato(c, ciclo, "QUIEBRA")
        corp["precio"] = round(corp["precio"] * (1 - C.QUIEBRA_CAIDA_COTIZACION), 2)
        corp["sentimiento"] = C.SENTIMIENTO_RANGO[0]
        if corp.get("es_del_usuario"):
            avisar(estado.uid, ciclo, "QUIEBRA", f"{sigla} entró en concurso",
                   "El capital quedó en negativo: se remataron " + ", ".join(nombre_ref(c["tipo"], c["ref_id"]) for c in caros)
                   + " y la acción se desplomó.", "bi-exclamation-octagon-fill", clave=f"quiebra:{sigla}:{ciclo}")


def evaluar_objetivos(estado, universo: dict) -> dict:
    """{codigo: {"ok": bool, "detalle": str}} de los objetivos de la temporada del cargo actual."""
    cargo = universo["cargo"]
    corp = estado.corps[cargo["sigla"]]
    activos = [c for c in estado.contratos if c["activo"] and c["sigla"] == cargo["sigla"]]
    salida = {}
    roi = _roi_desde(corp, cargo.get("temporada_desde", cargo["desde_ciclo"]))
    for cod in cargo["objetivos"]:
        if cod.startswith("roi_"):
            meta = int(cod.split("_")[1]) / 100
            salida[cod] = {"ok": roi >= meta, "detalle": f"{roi * 100:+.1f}% de {meta * 100:.0f}%"}
        elif cod.startswith("selecciones_grupos_"):
            meta = int(cod.split("_")[-1])
            fases = {d["id"]: d for d in _db()["internacional"].find({"id": {"$in": [c["ref_id"] for c in activos if c["tipo"] == "seleccion"]}},
                                                                     {"id": 1, "fase_eliminatoria": 1, "estado": 1})}
            n = sum(1 for d in fases.values() if (d.get("fase_eliminatoria") or 0) >= 7 or "CALIFICADO_MUNDIAL" in str(d.get("estado") or ""))
            salida[cod] = {"ok": n >= meta, "detalle": f"{n} de {meta}"}
        elif cod in ("cotizacion_inicial", "cotizacion_mas_10"):
            meta = cargo.get("precio_inicio", corp["precio"]) * (1.1 if cod == "cotizacion_mas_10" else 1.0)
            salida[cod] = {"ok": corp["precio"] >= meta, "detalle": f"{corp['precio']:.2f} de {meta:.2f}"}
        elif cod == "capital_inicial":
            meta = cargo.get("capital_inicio", corp["capital"])
            salida[cod] = {"ok": corp["capital"] >= meta, "detalle": f"{int(corp['capital']):,} de {int(meta):,}"}
        elif cod == "jugadores_10_partidos":
            n = sum(1 for c in activos if c["tipo"] == "jugador" and c.get("partidos", 0) >= 3)
            salida[cod] = {"ok": n >= 10, "detalle": f"{n} de 10"}
        elif cod == "goleador_torneo":
            lider = _goleador_mundial()
            ok = lider is not None and any(c["tipo"] == "jugador" and c["ref_id"] == lider for c in activos)
            salida[cod] = {"ok": ok, "detalle": "lo representas" if ok else "no lo representas"}
    return salida


def _goleador_mundial() -> Optional[int]:
    mundial = _mundial_activo()
    fila = list(_db()["juegos"].aggregate([
        {"$match": {"mundial_id": mundial, "estado": "finalizado"}}, {"$unwind": "$resultado.goleadores"},
        {"$group": {"_id": "$resultado.goleadores.jugador_id", "goles": {"$sum": "$resultado.goleadores.goles"}}},
        {"$sort": {"goles": -1}}, {"$limit": 1}]))
    return fila[0]["_id"] if fila else None


def evaluar_saneamiento(estado, universo: dict, ciclo: int) -> None:
    """
    Plan de saneamiento para TODOS los corporativos del universo (usuario e IA). Se abre cuando el corporativo está en
    rojo (capital < SANEAMIENTO_CAPITAL del inicial, o pérdida operativa en 3 de los últimos 4 ciclos) con 3 objetivos
    para los próximos SANEAMIENTO_DURACION ciclos. Cumplirlo trae un aporte de los accionistas; mientras está activo,
    el directorio da tregua al CEO del usuario (ver evaluar_directorio). Idempotente por ciclo (vive en corp["saneamiento"]).
    """
    uid = universo["_id"]
    for sigla, corp in estado.corps.items():
        san = corp.get("saneamiento") or {}
        hist = corp.get("historial") or []
        activos = [c for c in estado.contratos if c["activo"] and c["sigla"] == sigla]
        es_usuario = corp.get("es_del_usuario")
        if san.get("estado") == "ACTIVO":
            if san.get("evaluado_ciclo") == ciclo:
                continue
            progreso = _progreso_saneamiento(estado, uid, sigla, corp, san, hist, activos)
            san.update(progreso=progreso, evaluado_ciclo=ciclo)
            if all(p["ok"] for p in progreso.values()):
                aporte = int(round(C.APORTE_SANEAMIENTO * corp.get("capital_inicial", C.TIERS[C.CORPORATIVO_POR_SIGLA[sigla]["tier"]]["capital"]), -1))
                corp["capital"] += aporte
                corp["confianza"] = int(R.limitar(corp.get("confianza", C.CONFIANZA_INICIAL) + C.SANEAMIENTO_CONFIANZA, 0, 100))
                corp["sentimiento"] = round(R.limitar(corp.get("sentimiento", 1.0) + C.SANEAMIENTO_SENTIMIENTO, *C.SENTIMIENTO_RANGO), 4)
                san.update(estado="CUMPLIDO", fin_ciclo=ciclo, aporte_cobrado=aporte, espera_hasta=ciclo + C.SANEAMIENTO_ESPERA)
                estado.mover(sigla, ciclo, "APORTE_ACCIONISTAS", aporte, "Aporte de los accionistas: plan de saneamiento cumplido")
                if es_usuario:
                    universo["fama"] = min(100, universo["fama"] + C.SANEAMIENTO_FAMA)
                    _db()["corp_universos"].update_one({"_id": uid}, {"$set": {"fama": universo["fama"]}})
                    avisar(uid, ciclo, "SANEAMIENTO", "¡Plan de saneamiento cumplido!",
                           f"Los accionistas aportan {aporte:,} de capital, el directorio recupera confianza (+{C.SANEAMIENTO_CONFIANZA}) "
                           f"y tu fama sube (+{C.SANEAMIENTO_FAMA}).", "bi-shield-fill-check", clave=f"saneamiento-ok:{sigla}:{ciclo}")
            elif ciclo >= san["hasta_ciclo"]:
                san.update(estado="FALLIDO", fin_ciclo=ciclo, espera_hasta=ciclo + C.SANEAMIENTO_ESPERA)
                if es_usuario:
                    avisar(uid, ciclo, "SANEAMIENTO", "Terminó el plan de saneamiento sin cumplirse",
                           "Se terminó la tregua: desde ahora el directorio vuelve a evaluarte como siempre.",
                           "bi-shield-x", clave=f"saneamiento-fin:{sigla}:{ciclo}")
            corp["saneamiento"] = san
            continue
        if san and ciclo < (san.get("espera_hasta") or 0):
            continue
        capital_ini = corp.get("capital_inicial") or C.TIERS[C.CORPORATIVO_POR_SIGLA[sigla]["tier"]]["capital"]
        rojos, ventana = C.SANEAMIENTO_CICLOS_ROJO
        ultimos = hist[-ventana:]
        en_rojo = corp["capital"] < C.SANEAMIENTO_CAPITAL * capital_ini or (
            len(ultimos) >= ventana and sum(1 for h in ultimos if h.get("utilidad_op", h.get("utilidad", 0)) < 0) >= rojos)
        if not en_rojo or corp["capital"] < 0:
            continue
        rng = R.semilla(uid, "saneamiento", sigla, ciclo)
        objetivos = rng.sample(sorted(set(C.SANEAMIENTO_OBJETIVOS) - C.SANEAMIENTO_NO_SORTEAR), C.SANEAMIENTO_SORTEADOS)
        nuevo = {"estado": "ACTIVO", "desde_ciclo": ciclo + 1, "hasta_ciclo": ciclo + C.SANEAMIENTO_DURACION, "abierto_ciclo": ciclo,
                 "objetivos": objetivos, "honorarios_inicio": sum(R.honorario(c["tipo"], c.get("valor_actual") or 0) for c in activos),
                 "aporte": int(round(C.APORTE_SANEAMIENTO * capital_ini, -1)), "progreso": {}}
        nuevo["progreso"] = _progreso_saneamiento(estado, uid, sigla, corp, nuevo, hist, activos)
        corp["saneamiento"] = nuevo
        if es_usuario:
            avisar(uid, ciclo, "SANEAMIENTO", "El directorio abrió un plan de saneamiento",
                   f"{sigla} viene en números rojos. Tienes {C.SANEAMIENTO_DURACION} ciclos para cumplir 3 objetivos: si lo logras, los "
                   f"accionistas aportan {nuevo['aporte']:,}. Mientras dure, hay tregua: el directorio no te despide por el ranking.",
                   "bi-shield-fill-exclamation", clave=f"saneamiento:{sigla}:{ciclo}")


def _progreso_saneamiento(estado, uid, sigla: str, corp: dict, san: dict, hist: list, activos: list) -> dict:
    desde = san["desde_ciclo"]
    salida = {}
    for cod in san["objetivos"]:
        if cod == "utilidad_2":
            n = sum(1 for h in hist if h["ciclo"] >= desde and h.get("utilidad", 0) > 0)
            salida[cod] = {"ok": n >= 2, "detalle": f"{min(n, 2)} de 2 ciclos"}
        elif cod in ("acuerdo_1", "patrocinio_1"):
            n = _db()["corp_patrocinios"].count_documents({"universo_id": uid, "sigla": sigla, "desde_ciclo": {"$gte": desde},
                                                           "estado": {"$in": ["ACTIVO", "TERMINADO", "CORTADO"]}})
            if cod == "acuerdo_1":
                n += _db()["corp_acuerdos"].count_documents({"universo_id": uid, "sigla": sigla, "desde_ciclo": {"$gte": desde}})
            salida[cod] = {"ok": n >= 1, "detalle": f"{min(n, 1)} de 1"}
        elif cod == "gira_1":
            n = _db()["corp_giras"].count_documents({"universo_id": uid, "sigla": sigla, "ciclo": {"$gte": desde}})
            salida[cod] = {"ok": n >= 1, "detalle": f"{min(n, 1)} de 1"}
        elif cod == "honorarios":
            ahora = sum(R.honorario(c["tipo"], c.get("valor_actual") or 0) for c in activos)
            meta = san.get("honorarios_inicio", ahora) * 0.9
            salida[cod] = {"ok": ahora <= meta, "detalle": f"{int(ahora):,} por ciclo (meta {int(meta):,})"}
        elif cod == "satisfaccion_50":
            media = (sum(c["satisfaccion"] for c in activos) / len(activos)) if activos else 0
            salida[cod] = {"ok": media >= 50, "detalle": f"{media:.0f} de 50"}
    return salida


def _fama_por_resultados(universo: dict, ultimo: dict) -> tuple:
    """(+fama, motivos) del ciclo por lo que hicieron los representados del CEO (con tope por ciclo)."""
    f = ultimo.get("fama") or {}
    motivos, suma = [], 0
    if f.get("avance"):
        suma += C.FAMA["avance_fase"]; motivos.append(f"{f['avance']} avanzó de fase")
    if f.get("actuacion"):
        suma += C.FAMA["actuacion"]; motivos.append(f"actuación destacada de {f['actuacion']}")
    if f.get("top50"):
        suma += C.FAMA["fichaje_top50"]; motivos.append(f"fichaste a {f['top50']} (top 50)")
    # el patrocinio no cuenta: cubre solo el mantenimiento, así que valdría siempre; cuenta lo que se ganó jugando y gestionando
    if ultimo.get("renta", 0) > 0 and (ultimo.get("renta", 0) + ultimo.get("extra", 0)) > ultimo.get("honorarios", 0) > 0:
        suma += C.FAMA["renta_mayor_honorarios"]; motivos.append("tus representados rindieron más de lo que costaron")
    return min(suma, C.FAMA_TOPE_RESULTADOS_CICLO), motivos


def evaluar_directorio(estado, universo: dict, ciclo: int) -> None:
    _quiebras(estado, ciclo)
    evaluar_saneamiento(estado, universo, ciclo)
    cargo = universo.get("cargo")
    if universo["estado"] not in ESTADOS_CON_CARGO or not cargo:
        return
    uid, sigla = universo["_id"], cargo["sigla"]
    corp = estado.corps[sigla]
    ultimo = (corp.get("historial") or [{}])[-1]
    pago = corp.pop("_pago_ceo", None) or {}
    objetivos = evaluar_objetivos(estado, universo)
    cargo["objetivos_estado"] = objetivos
    cambios = {"cargo.objetivos_estado": objetivos}
    if ultimo.get("utilidad", 0) > 0:
        universo["fama"] = min(100, universo["fama"] + C.FAMA["ciclo_utilidad"])
        cambios["fama"] = universo["fama"]
        U.dar_xp(uid, "CORP_CICLO_UTILIDAD", f"{sigla}:{ciclo}")
    extra_fama, motivos_fama = _fama_por_resultados(universo, ultimo)
    if extra_fama:
        universo["fama"] = min(100, universo["fama"] + extra_fama)
        cambios["fama"] = universo["fama"]
        avisar(uid, ciclo, "FAMA", f"Tu fama sube (+{extra_fama})", "Por " + ", ".join(motivos_fama) + ".", "bi-star-fill",
               clave=f"fama:{ciclo}")
    if universo["estado"] == "PREAVISO":
        _db()["corp_universos"].update_one({"_id": uid}, {"$set": cambios})
        return
    ventana = {s: _roi_ventana(c) for s, c in estado.corps.items()}
    posicion = sorted(ventana, key=ventana.get, reverse=True).index(sigla) + 1
    indice = mean(c.get("variacion_ciclo", 0) for c in estado.corps.values())
    ciclos_en_cargo = ciclo - cargo["desde_ciclo"] + 1
    antes = corp["confianza"]
    delta = R.cambio_confianza(C.CORPORATIVO_POR_SIGLA[sigla]["tier"], posicion, ventana[sigla],
                               corp.get("variacion_ciclo", 0) - indice, ultimo.get("impago", False)) if ciclos_en_cargo >= 1 else 0
    corp["confianza"] = int(R.limitar(antes + delta, 0, 100))
    tregua = (corp.get("saneamiento") or {}).get("estado") == "ACTIVO"
    if tregua:   # plan de saneamiento en curso: la confianza no cae hasta la zona de despido
        corp["confianza"] = max(corp["confianza"], C.CONFIANZA_DESPIDO + 1)
    cargo["ultima_posicion"] = posicion
    cambios.update({"cargo.ultima_posicion": posicion})
    _db()["corp_universos"].update_one({"_id": uid}, {"$set": cambios})
    avisar(uid, ciclo, "CIERRE", f"Cierre del ciclo {ciclo}",
           f"Utilidad {ultimo.get('utilidad', 0):+,} · cobraste {pago.get('efectivo', 0):,}"
           + (f" (+{pago['acciones']:,} en acciones)" if pago.get("acciones") else "")
           + f" · puesto {posicion} de 10 en ROI · confianza {corp['confianza']} ({delta:+d}).",
           "bi-clipboard-data-fill", clave=f"cierre:{ciclo}")
    despido = None
    if ciclos_en_cargo >= 2:
        if corp["confianza"] < C.CONFIANZA_DESPIDO and not tregua:
            despido = f"la confianza del directorio cayó a {corp['confianza']}"
        elif corp["capital"] < corp.get("capital_inicial", C.TIERS[C.CORPORATIVO_POR_SIGLA[sigla]["tier"]]["capital"]) * C.CAPITAL_MINIMO_FRACCION:
            despido = "el capital quedó por debajo del 25% del inicial"
    if despido:
        despedir(estado, universo, ciclo, despido)
    elif corp["confianza"] < C.CONFIANZA_ULTIMATUM <= antes and not tregua:
        avisar(uid, ciclo, "ULTIMATUM", "Ultimátum del directorio",
               f"La confianza cayó a {corp['confianza']}. Si baja de {C.CONFIANZA_DESPIDO}, quedas afuera.",
               "bi-exclamation-triangle-fill", clave=f"ultimatum:{ciclo}")


def despedir(estado, universo: dict, ciclo: int, motivo: str) -> None:
    uid, cargo = universo["_id"], universo["cargo"]
    universo.update(estado="PAUSA", cargo=None, fama=max(0, universo["fama"] + C.FAMA["despido"]),
                    pausa_hasta_ciclo=ciclo + C.CICLOS_PAUSA["despido"])
    estado.corps[cargo["sigla"]]["es_del_usuario"] = False
    _cerrar_cargo(uid, cargo, ciclo, "DESPIDO", universo)
    _db()["corp_corporativos"].update_one({"universo_id": uid, "sigla": cargo["sigla"]}, {"$set": {"es_del_usuario": False}})
    avisar(uid, ciclo, "DESPIDO", f"Despedido de {cargo['sigla']}",
           f"El directorio te despidió: {motivo}. Pierdes las acciones no consolidadas y tu carrera queda en pausa "
           f"{C.CICLOS_PAUSA['despido']} ciclos.", "bi-x-octagon-fill", clave=f"despido:{ciclo}")


def _cerrar_cargo(uid, cargo: dict, ciclo: int, motivo: str, universo: dict, conservar_acciones: bool = False) -> None:
    """Cierra el cargo actual: historial, ofertas de mercado abiertas y acciones bloqueadas del corporativo."""
    historial = {k: v for k, v in cargo.items() if k != "objetivos_estado"} | {"hasta_ciclo": ciclo, "motivo": motivo,
                                                                             "objetivos_estado": cargo.get("objetivos_estado")}
    # se pierden solo las acciones de este corporativo que todavía no consolidaron (salvo fin de contrato)
    actuales = (_db()["corp_universos"].find_one({"_id": uid}, {"acciones_bloqueadas": 1}) or {}).get("acciones_bloqueadas") or []
    bloqueadas = [a for a in actuales if a["sigla"] != cargo["sigla"] or conservar_acciones or a["consolida_ciclo"] <= ciclo]
    _db()["corp_universos"].update_one({"_id": uid}, {
        "$set": {"estado": universo["estado"], "cargo": universo.get("cargo"), "fama": universo["fama"],
                 "pausa_hasta_ciclo": universo.get("pausa_hasta_ciclo"), "acciones_bloqueadas": bloqueadas, "preaviso": None},
        "$push": {"historial_cargos": historial}})
    universo["acciones_bloqueadas"] = bloqueadas
    _db()["corp_ofertas"].update_many({"universo_id": uid, "estado": "PENDIENTE", "sigla": cargo["sigla"]},
                                      {"$set": {"estado": "CANCELADA", "resultado": "Dejaste el cargo"}})


# --- Cierre de ciclo: carrera --------------------------------------------------------------------
def cerrar_ciclo(universo: dict, ciclo: int, estado=None) -> None:
    uid = universo["_id"]
    vencidas = list(_db()["corp_ofertas_empleo"].find({"universo_id": uid, "estado": "PENDIENTE", "vence_ciclo": {"$lte": ciclo}}))
    if vencidas:
        _db()["corp_ofertas_empleo"].update_many({"_id": {"$in": [o["_id"] for o in vencidas]}}, {"$set": {"estado": "VENCIDA"}})
        avisar(uid, ciclo, "OFERTA_VENCIDA", "Ofertas vencidas",
               "Venció la oferta de " + ", ".join(o["sigla"] for o in vencidas) + ": nadie espera para siempre.",
               "bi-hourglass-bottom", clave=f"vencidas:{ciclo}")
        if any(o["tipo"] == "RENOVACION" for o in vencidas) and universo["estado"] == "EN_CARGO":
            _fin_contrato(estado, universo, ciclo)
        if any(o["tipo"] == "RETENCION" for o in vencidas):
            _db()["corp_ofertas_empleo"].update_many({"universo_id": uid, "estado": "EN_ESPERA"}, {"$set": {"estado": "VENCIDA"}})

    if universo["estado"] == "PAUSA" and ciclo >= (universo.get("pausa_hasta_ciclo") or 0):
        universo["estado"] = "BUSCANDO"
        _db()["corp_universos"].update_one({"_id": uid}, {"$set": {"estado": "BUSCANDO", "pausa_hasta_ciclo": None}})
        avisar(uid, ciclo, "FIN_PAUSA", "De vuelta en el mercado",
               "Terminó tu pausa: los corporativos vuelven a considerar tu perfil.", "bi-arrow-repeat", clave=f"finpausa:{ciclo}")

    if universo["estado"] == "PREAVISO" and ciclo >= (universo.get("preaviso") or {}).get("hasta_ciclo", 0):
        _completar_cambio(estado, universo, ciclo)

    if universo["estado"] == "EN_CARGO":
        _cierre_temporada(estado, universo, ciclo)

    if universo["estado"] == "BUSCANDO" and ciclo > (universo.get("sin_ofertas_hasta_ciclo") or 0):
        rng = R.semilla(uid, "empleo", ciclo)
        if rng.random() < R.probabilidad_oferta_empleo(universo["fama"]):
            candidatos = _corps_elegibles(universo)
            if candidatos:
                # los corporativos grandes miran primero a los CEOs con fama
                pesos = [1 + C.ORDEN_TIER[c["tier"]] for c in candidatos]
                _crear_oferta(universo, rng.choices(candidatos, weights=pesos)[0], ciclo, "EMPLEO", rng)
    elif universo["estado"] == "EN_CARGO" and estado is not None:
        _headhunting(estado, universo, ciclo)


def _headhunting(estado, universo: dict, ciclo: int) -> None:
    """Otro corporativo tienta al CEO si su ROI de la temporada supera el promedio del universo (confidencial)."""
    cargo = universo["cargo"]
    if _db()["corp_ofertas_empleo"].find_one({"universo_id": universo["_id"], "estado": {"$in": ["PENDIENTE", "EN_ESPERA"]}}):
        return
    desde = cargo.get("temporada_desde", cargo["desde_ciclo"])
    rois = {s: _roi_desde(c, desde) for s, c in estado.corps.items()}
    propio = rois.pop(cargo["sigla"])
    rng = R.semilla(universo["_id"], "headhunting", ciclo)
    if rng.random() >= R.probabilidad_headhunting(universo["fama"], propio > mean(rois.values())):
        return
    tier_actual = C.CORPORATIVO_POR_SIGLA[cargo["sigla"]]["tier"]
    candidatos = _corps_elegibles(universo, tier_minimo=tier_actual)   # te buscan los de tu tier o más grandes
    if candidatos:
        corp = rng.choice(candidatos)
        sueldo = int(max(cargo["sueldo_base"], R.sueldo_base(corp["tier"], universo["fama"])) * (1 + rng.uniform(*C.MEJORA_SUELDO_HEADHUNTING)))
        _crear_oferta(universo, corp, ciclo, "HEADHUNTING", rng, sueldo=sueldo)


def _cierre_temporada(estado, universo: dict, ciclo: int) -> None:
    """Al empezar un Mundial nuevo se cierra la temporada del CEO: objetivos, fama, título y renovación (o no)."""
    cargo = universo["cargo"]
    activo = _mundial_activo()
    if not activo or cargo.get("mundial_id") in (None, activo) or cargo.get("temporada_cerrada"):
        return
    uid = universo["_id"]
    objetivos = cargo.get("objetivos_estado") or {}
    cumplidos = sum(1 for o in objetivos.values() if o.get("ok"))
    fama = universo["fama"] + C.FAMA["objetivo"] * cumplidos
    titulo = False
    if estado is not None:
        desde = cargo.get("temporada_desde", cargo["desde_ciclo"])
        rois = {s: _roi_desde(c, desde) for s, c in estado.corps.items()}
        titulo = max(rois, key=rois.get) == cargo["sigla"]
        if titulo:
            fama += C.FAMA["titulo_temporada"]
    universo["fama"] = min(100, fama)
    _db()["corp_universos"].update_one({"_id": uid}, {"$set": {"fama": universo["fama"], "cargo.temporada_cerrada": True}})
    cargo["temporada_cerrada"] = True
    corp = estado.corps[cargo["sigla"]] if estado is not None else _db()["corp_corporativos"].find_one({"universo_id": uid, "sigla": cargo["sigla"]})
    rng = R.semilla(uid, "renovacion", ciclo)
    info = C.CORPORATIVO_POR_SIGLA[cargo["sigla"]]
    texto = f"Cumpliste {cumplidos} de {len(objetivos)} objetivos" + (" y tu corporativo tuvo el mejor ROI del universo" if titulo else "")
    if cumplidos >= C.OBJETIVOS_PARA_RENOVAR:
        _crear_oferta(universo, info, ciclo, "RENOVACION", rng, sueldo=int(cargo["sueldo_base"] * (1 + C.MEJORA_RENOVACION)))
        avisar(uid, ciclo, "TEMPORADA", "Fin de temporada", texto + ": el directorio te ofrece renovar con aumento.", "bi-trophy-fill",
               clave=f"temporada:{ciclo}")
    elif corp["confianza"] >= C.CONFIANZA_RENUEVA_SIN_OBJETIVOS:
        _crear_oferta(universo, info, ciclo, "RENOVACION", rng, sueldo=cargo["sueldo_base"])
        avisar(uid, ciclo, "TEMPORADA", "Fin de temporada", texto + ": el directorio confía en ti y renueva, sin aumento.",
               "bi-clipboard-check-fill", clave=f"temporada:{ciclo}")
    else:
        avisar(uid, ciclo, "TEMPORADA", "Fin de temporada", texto + ": el directorio no renueva tu contrato.", "bi-clipboard-x-fill",
               clave=f"temporada:{ciclo}")
        _fin_contrato(estado, universo, ciclo)


def _fin_contrato(estado, universo: dict, ciclo: int) -> None:
    cargo = universo["cargo"]
    universo.update(estado="BUSCANDO", cargo=None)
    if estado is not None:
        estado.corps[cargo["sigla"]]["es_del_usuario"] = False
    _cerrar_cargo(universo["_id"], cargo, ciclo, "FIN_CONTRATO", universo, conservar_acciones=True)
    _db()["corp_corporativos"].update_one({"universo_id": universo["_id"], "sigla": cargo["sigla"]}, {"$set": {"es_del_usuario": False}})


def _completar_cambio(estado, universo: dict, ciclo: int) -> None:
    """Termina el preaviso: el CEO deja su corporativo (pierde las acciones no consolidadas) y asume el nuevo."""
    uid, viejo = universo["_id"], universo["cargo"]
    oferta = _db()["corp_ofertas_empleo"].find_one({"_id": universo["preaviso"]["oferta_id"]})
    if viejo["desde_ciclo"] > ciclo - C.CICLOS_RENUNCIA_TEMPRANA:
        universo["fama"] = max(0, universo["fama"] + C.FAMA["renuncia_temprana"])
    nuevo = _cargo_desde_oferta(oferta, ciclo + 1, estado.corps[oferta["sigla"]] if estado is not None else None)
    universo.update(estado="EN_CARGO", cargo=nuevo)
    if estado is not None:
        estado.corps[viejo["sigla"]]["es_del_usuario"] = False
        estado.corps[oferta["sigla"]]["es_del_usuario"] = True
        estado.corps[oferta["sigla"]]["confianza"] = C.CONFIANZA_INICIAL
    _cerrar_cargo(uid, viejo, ciclo, f"CAMBIO:{oferta['sigla']}", universo)
    _db()["corp_corporativos"].update_one({"universo_id": uid, "sigla": viejo["sigla"]}, {"$set": {"es_del_usuario": False}})
    _db()["corp_corporativos"].update_one({"universo_id": uid, "sigla": oferta["sigla"]}, {"$set": {"es_del_usuario": True, "confianza": C.CONFIANZA_INICIAL}})
    avisar(uid, ciclo, "CARGO", f"Nuevo CEO de {oferta['sigla']}", f"Terminó tu preaviso en {viejo['sigla']}: ya diriges {oferta['sigla']}.",
           "bi-briefcase-fill", clave=f"cambio:{ciclo}")
    U.dar_xp(uid, "CORP_CARGO", oferta["_id"], ("ASCENSO_TIER_A",) if C.CORPORATIVO_POR_SIGLA[oferta["sigla"]]["tier"] == "A" else ())


def _cargo_desde_oferta(oferta: dict, ciclo: int, corp: Optional[dict]) -> dict:
    corp = corp or _db()["corp_corporativos"].find_one({"universo_id": oferta["universo_id"], "sigla": oferta["sigla"]})
    return {"sigla": oferta["sigla"], "desde_ciclo": ciclo, "temporada_desde": ciclo, "sueldo_base": oferta["sueldo_base"],
            "bono_pct": oferta["bono_pct"], "objetivos": oferta["objetivos"], "mundial_id": _mundial_activo(), "oferta_id": oferta["_id"],
            "precio_inicio": corp.get("precio"), "capital_inicio": corp.get("capital")}


# --- Acciones del usuario ------------------------------------------------------------------------
def aceptar_oferta(user_id, oferta_id: str) -> dict:
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo = obtener_universo(user_id)
        if not universo:
            raise ValueError("Primero tienes que buscar empleo")
        oferta = _db()["corp_ofertas_empleo"].find_one({"_id": oferta_id, "universo_id": user_id, "estado": {"$in": ["PENDIENTE", "EN_ESPERA"]}})
        if not oferta:
            raise ValueError("La oferta ya no está disponible")
        ciclo = ciclo_en_curso(universo)
        tipo = oferta.get("tipo", "EMPLEO")
        if tipo == "EMPLEO":
            if universo["estado"] != "BUSCANDO":
                raise ValueError("Solo puedes aceptar una oferta de empleo mientras buscas trabajo")
            return _asumir(universo, oferta, ciclo)
        if tipo == "RENOVACION":
            cargo = universo["cargo"]
            nuevo = {**_cargo_desde_oferta(oferta, ciclo, None), "desde_ciclo": cargo["desde_ciclo"]}
            _resolver(oferta_id, "ACEPTADA")
            _db()["corp_universos"].update_one({"_id": user_id}, {"$set": {"cargo": nuevo}})
            avisar(user_id, ciclo, "CARGO", f"Renovaste con {oferta['sigla']}", "Arranca una temporada nueva con objetivos nuevos.",
                   "bi-arrow-repeat", clave=f"renovo:{oferta_id}")
            return {"ok": True, "renovado": True}
        if tipo == "RETENCION":
            cargo = universo["cargo"]
            _resolver(oferta_id, "ACEPTADA")
            _db()["corp_ofertas_empleo"].update_many({"universo_id": user_id, "estado": "EN_ESPERA"}, {"$set": {"estado": "RECHAZADA"}})
            _db()["corp_universos"].update_one({"_id": user_id}, {"$set": {"cargo.sueldo_base": oferta["sueldo_base"]}})
            return {"ok": True, "retenido": True, "sueldo": oferta["sueldo_base"]}
        # HEADHUNTING
        if universo["estado"] != "EN_CARGO":
            raise ValueError("Esa oferta era para tu cargo actual")
        corp_actual = _db()["corp_corporativos"].find_one({"universo_id": user_id, "sigla": universo["cargo"]["sigla"]})
        if oferta["estado"] == "PENDIENTE" and corp_actual["confianza"] >= C.CONFIANZA_CONTRAOFERTA:
            # El directorio actual contraoferta: el CEO elige entre quedarse (con aumento) o irse igual
            _db()["corp_ofertas_empleo"].update_one({"_id": oferta_id}, {"$set": {"estado": "EN_ESPERA"}})
            rng = R.semilla(user_id, "retencion", oferta_id)
            info = C.CORPORATIVO_POR_SIGLA[universo["cargo"]["sigla"]]
            _crear_oferta(universo, info, ciclo, "RETENCION", rng, sueldo=int(universo["cargo"]["sueldo_base"] * (1 + C.MEJORA_CONTRAOFERTA)))
            return {"ok": True, "contraoferta": True}
        _resolver(oferta_id, "ACEPTADA")
        _db()["corp_ofertas_empleo"].update_many({"universo_id": user_id, "estado": "PENDIENTE", "tipo": "RETENCION"}, {"$set": {"estado": "RECHAZADA"}})
        hasta = ciclo + C.CICLOS_PREAVISO - 1
        _db()["corp_universos"].update_one({"_id": user_id}, {"$set": {"estado": "PREAVISO", "preaviso": {"oferta_id": oferta_id, "sigla": oferta["sigla"], "hasta_ciclo": hasta}}})
        avisar(user_id, ciclo, "PREAVISO", f"Te vas a {oferta['sigla']}",
               f"Presentaste tu renuncia en {universo['cargo']['sigla']}: cumples el preaviso hasta el cierre del ciclo {hasta} (cobras, pero no puedes fichar).",
               "bi-box-arrow-right", clave=f"preaviso:{oferta_id}")
        return {"ok": True, "preaviso": True}


def _resolver(oferta_id: str, estado: str) -> None:
    _db()["corp_ofertas_empleo"].update_one({"_id": oferta_id}, {"$set": {"estado": estado, "resuelta_en": datetime.utcnow()}})


def _asumir(universo: dict, oferta: dict, ciclo: int) -> dict:
    uid = universo["_id"]
    _resolver(oferta["_id"], "ACEPTADA")
    corp = C.CORPORATIVO_POR_SIGLA[oferta["sigla"]]
    cargo = _cargo_desde_oferta(oferta, ciclo, None)
    _db()["corp_universos"].update_one({"_id": uid}, {"$set": {"estado": "EN_CARGO", "cargo": cargo, "rechazos_seguidos": 0}})
    _db()["corp_corporativos"].update_many({"universo_id": uid}, {"$set": {"es_del_usuario": False}})
    _db()["corp_corporativos"].update_one({"universo_id": uid, "sigla": oferta["sigla"]}, {"$set": {"es_del_usuario": True, "confianza": C.CONFIANZA_INICIAL}})
    # el resto de las ofertas abiertas se declinan solas (sin castigo de fama)
    _db()["corp_ofertas_empleo"].update_many({"universo_id": uid, "estado": "PENDIENTE"}, {"$set": {"estado": "DESCARTADA"}})
    avisar(uid, ciclo, "CARGO", f"Nuevo CEO de {oferta['sigla']}",
           f"Asumiste la dirección general de {corp['nombre']}. El directorio espera resultados: revisa tus objetivos.",
           "bi-briefcase-fill", clave=f"cargo:{oferta['_id']}")
    U.dar_xp(uid, "CORP_CARGO", oferta["_id"], ("PRIMER_CARGO",) + (("ASCENSO_TIER_A",) if corp["tier"] == "A" else ()))
    return {"ok": True, "sigla": oferta["sigla"]}


def rechazar_oferta(user_id, oferta_id: str) -> dict:
    universo = obtener_universo(user_id)
    if not universo:
        raise ValueError("Primero tienes que buscar empleo")
    oferta = _db()["corp_ofertas_empleo"].find_one_and_update(
        {"_id": oferta_id, "universo_id": user_id, "estado": {"$in": ["PENDIENTE", "EN_ESPERA"]}},
        {"$set": {"estado": "RECHAZADA", "resuelta_en": datetime.utcnow()}})
    if not oferta:
        raise ValueError("La oferta ya no está disponible")
    tipo = oferta.get("tipo", "EMPLEO")
    if tipo == "RENOVACION":
        U.poner_al_dia(user_id)
        with U.candado(user_id):
            universo = obtener_universo(user_id)
            if universo["estado"] == "EN_CARGO":
                _fin_contrato(None, universo, ciclo_en_curso(universo))
        return {"ok": True}
    if tipo == "RETENCION":
        # rechazar la retención = irse igual: se acepta la oferta en espera
        espera = _db()["corp_ofertas_empleo"].find_one({"universo_id": user_id, "estado": "EN_ESPERA"})
        if espera:
            return aceptar_oferta(user_id, espera["_id"])
        return {"ok": True}
    if tipo != "EMPLEO":
        return {"ok": True}
    rechazos = universo.get("rechazos_seguidos", 0) + 1
    cambios = {"rechazos_seguidos": rechazos, "sin_ofertas_hasta_ciclo": ciclo_en_curso(universo)}
    castigo = rechazos > C.RECHAZOS_SIN_PENALIDAD
    if castigo:
        cambios["fama"] = max(0, universo["fama"] + C.FAMA["rechazo_repetido"])
    _db()["corp_universos"].update_one({"_id": user_id}, {"$set": cambios})
    return {"ok": True, "castigo_fama": castigo}


def renunciar(user_id) -> dict:
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo = obtener_universo(user_id)
        if not universo or universo["estado"] != "EN_CARGO":
            raise ValueError("No tienes un cargo del que renunciar")
        ciclo = ciclo_en_curso(universo)
        cargo = universo["cargo"]
        fama_antes = universo["fama"]
        if ciclo - cargo["desde_ciclo"] < C.CICLOS_RENUNCIA_TEMPRANA:
            universo["fama"] = max(0, universo["fama"] + C.FAMA["renuncia_temprana"])
        universo.update(estado="PAUSA", cargo=None, pausa_hasta_ciclo=ciclo + C.CICLOS_PAUSA["renuncia"])
        # renunciar conserva las acciones consolidadas; las bloqueadas de este corporativo se pierden
        _cerrar_cargo(user_id, cargo, ciclo, "RENUNCIA", universo)
        _db()["corp_corporativos"].update_one({"universo_id": user_id, "sigla": cargo["sigla"]}, {"$set": {"es_del_usuario": False}})
        avisar(user_id, ciclo, "RENUNCIA", f"Dejaste {cargo['sigla']}",
               f"Renunciaste a la dirección de {cargo['sigla']}. Tomás una pausa de {C.CICLOS_PAUSA['renuncia']} ciclo antes de volver al mercado.",
               "bi-door-open-fill", clave=f"renuncia:{ciclo}:{cargo['sigla']}")
    return {"ok": True, "fama_perdida": fama_antes - universo["fama"]}


def _mundial_activo() -> Optional[str]:
    m = _db()["mundiales"].find_one({"activo": True}, {"_id": 1}) or _db()["mundiales"].find_one({}, {"_id": 1}, sort=[("_id", -1)])
    return str(m["_id"]) if m else None
