"""
Corporativos Deportivos — bolsa de TU universo (fase 5).

Cada corporativo tiene ACCIONES_POR_CORPORATIVO acciones; el precio lo fija el cierre de ciclo
(corporativo_ciclo_service.cerrar_cuentas: fundamentos x sentimiento, banda ±20%) y queda en
`corp_corporativos.precio` + `historial[].precio`. El usuario compra y vende con su saldo (`usuarios.monto`):
  - comisión COMISION_BOLSA por operación, tope TOPE_TENENCIA de las acciones de cada corporativo;
  - información privilegiada: mientras dirige un corporativo (EN_CARGO / PREAVISO) NO puede comprar sus acciones;
    sí puede vender las que ya consolidó (así cobra la parte del bono que recibió en acciones);
  - antes de operar se pone al día el universo: siempre se opera al precio del último cierre.
Tenencias en `corp_tenencias` (una por universo+sigla) y libro en `corp_operaciones_bolsa`.
En el cierre de ciclo: consolidan las acciones bloqueadas del bono del CEO y los corporativos de la IA con
utilidad reparten dividendo (el usuario cobra la parte de sus acciones). El CEO decide el dividendo de su corporativo.
"""
from datetime import datetime
from statistics import mean
from typing import Optional

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from config import corporativos as C
from services import corporativo_reglas as R
from services import corporativo_universo_service as U
from services.imagenes_pais_service import url_logo_corporativo


def _db():
    return U.db


def _oper(uid, sigla: str, tipo: str, cantidad: float, precio: float, monto: int, ciclo: int, comision: int = 0,
          _id: Optional[str] = None) -> bool:
    doc = {"universo_id": uid, "sigla": sigla, "tipo": tipo, "cantidad": round(cantidad, 2), "precio": precio, "monto": int(monto),
           "comision": int(comision), "ciclo": ciclo, "creado_en": datetime.utcnow()}
    if _id:
        doc["_id"] = _id
    try:
        _db()["corp_operaciones_bolsa"].insert_one(doc)
        return True
    except DuplicateKeyError:
        return False


def _sumar_tenencia(uid, sigla: str, cantidad: float, costo: float) -> None:
    _db()["corp_tenencias"].update_one({"universo_id": uid, "sigla": sigla},
                                       {"$inc": {"cantidad": round(cantidad, 2), "costo_total": round(costo, 2)},
                                        "$set": {"actualizado_en": datetime.utcnow()}}, upsert=True)


def _acreditar(uid, monto: int) -> None:
    if monto:
        _db()["usuarios"].update_one(U.filtro_usuario(uid), {"$inc": {"monto": int(monto)}})


# --- Cierre de ciclo -----------------------------------------------------------------------------
def consolidar_acciones(universo: dict, ciclo: int) -> None:
    """Las acciones del bono del CEO que cumplieron CICLOS_CONSOLIDACION_ACCIONES pasan a sus tenencias (operables)."""
    # se lee de la base: pagar_ceo pudo agregar un paquete en este mismo cierre
    bloqueadas = (_db()["corp_universos"].find_one({"_id": universo["_id"]}, {"acciones_bloqueadas": 1}) or {}).get("acciones_bloqueadas") or []
    listas = [a for a in bloqueadas if a["consolida_ciclo"] <= ciclo]
    if not listas:
        return
    uid = universo["_id"]
    for a in listas:
        if _oper(uid, a["sigla"], "CONSOLIDACION", a["cantidad"], 0, a["valor_al_otorgar"], ciclo,
                 _id=f"{uid}:consolida:{a['sigla']}:{a['otorgada_ciclo']}"):
            _sumar_tenencia(uid, a["sigla"], a["cantidad"], a["valor_al_otorgar"])
    resto = [a for a in bloqueadas if a["consolida_ciclo"] > ciclo]
    universo["acciones_bloqueadas"] = resto
    _db()["corp_universos"].update_one({"_id": uid}, {"$set": {"acciones_bloqueadas": resto}})
    U.avisar(uid, ciclo, "ACCIONES", "Acciones consolidadas",
             f"Consolidaron {sum(a['cantidad'] for a in listas):,.0f} acciones de tu bono: ya podés venderlas en la bolsa.",
             "bi-unlock-fill", clave=f"consolida:{ciclo}")


def _pagar_dividendo(uid, sigla: str, monto_total: int, ciclo: int, corp: dict) -> int:
    """Descuenta el dividendo del capital (en memoria o en la base según quién llame) y paga la parte del usuario."""
    por_accion = monto_total / C.ACCIONES_POR_CORPORATIVO
    tenencia = _db()["corp_tenencias"].find_one({"universo_id": uid, "sigla": sigla}) or {}
    if not tenencia.get("cantidad"):
        return 0
    parte = int(tenencia["cantidad"] * por_accion)
    if _oper(uid, sigla, "DIVIDENDO", tenencia.get("cantidad") or 0, round(por_accion, 4), parte, ciclo, _id=f"{uid}:div:{sigla}:{ciclo}"):
        _acreditar(uid, parte)
        if parte:
            U.avisar(uid, ciclo, "DIVIDENDO", f"Dividendo de {sigla}",
                     f"{sigla} repartió {monto_total:,} entre sus accionistas: te tocaron {parte:,} por tus acciones.",
                     "bi-cash-coin", clave=f"div:{sigla}:{ciclo}")
    return parte


def dividendos_ia(estado, universo: dict, ciclo: int) -> None:
    """Los corporativos de la IA con utilidad y capital sano reparten parte de la utilidad del ciclo (sube su acción)."""
    for sigla, corp in estado.corps.items():
        if corp.get("es_del_usuario"):
            continue
        ultimo = (corp.get("historial") or [{}])[-1]
        utilidad = ultimo.get("utilidad", 0)
        if utilidad <= 0 or corp["capital"] < corp.get("capital_inicial", 0) or ultimo.get("roi", 0) < C.IA_ROI_DIVIDENDO / 10:
            continue
        monto = int(utilidad * C.IA_FRACCION_DIVIDENDO)
        if monto <= 0:
            continue
        corp["capital"] -= monto
        corp["sentimiento"] = round(R.limitar(corp.get("sentimiento", 1) + C.SENTIMIENTO_DIVIDENDO, *C.SENTIMIENTO_RANGO), 4)
        _pagar_dividendo(universo["_id"], sigla, monto, ciclo, corp)


# --- Acciones del usuario ------------------------------------------------------------------------
def _precio(uid, sigla: str) -> dict:
    corp = _db()["corp_corporativos"].find_one({"universo_id": uid, "sigla": sigla})
    if not corp:
        raise ValueError("Corporativo inválido")
    return corp


def _bloqueo_insider(universo: dict, sigla: str) -> bool:
    cargo = universo.get("cargo") or {}
    return universo["estado"] in ("EN_CARGO", "PREAVISO") and cargo.get("sigla") == sigla


def comprar(user_id, sigla: str, cantidad: int) -> dict:
    sigla = sigla.upper()
    if sigla not in C.CORPORATIVO_POR_SIGLA or cantidad <= 0:
        raise ValueError("Operación inválida")
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo = U.obtener_universo(user_id)
        if not universo:
            raise ValueError("Primero activá el módulo de Corporativos")
        if _bloqueo_insider(universo, sigla):
            raise ValueError(f"Información privilegiada: mientras dirigís {sigla} no podés comprar sus acciones")
        corp = _precio(user_id, sigla)
        tenencia = _db()["corp_tenencias"].find_one({"universo_id": user_id, "sigla": sigla}) or {}
        tope = C.ACCIONES_POR_CORPORATIVO * C.TOPE_TENENCIA
        if (tenencia.get("cantidad") or 0) + cantidad > tope:
            raise ValueError(f"Tope: no podés tener más de {tope:,.0f} acciones de un corporativo ({C.TOPE_TENENCIA:.0%})")
        bruto = cantidad * corp["precio"]
        comision = max(1, round(bruto * C.COMISION_BOLSA))
        total = int(round(bruto + comision))
        pago = _db()["usuarios"].find_one_and_update({**U.filtro_usuario(user_id), "monto": {"$gte": total}},
                                                     {"$inc": {"monto": -total}}, return_document=ReturnDocument.AFTER)
        if not pago:
            raise ValueError(f"Saldo insuficiente: la compra cuesta {total:,} (incluye {comision:,} de comisión)")
        ciclo = U.ciclo_en_curso(universo)
        _sumar_tenencia(user_id, sigla, cantidad, total)
        _oper(user_id, sigla, "COMPRA", cantidad, corp["precio"], -total, ciclo, comision)
    U.dar_xp(user_id, "CORP_ACCIONES", f"{sigla}:{datetime.utcnow().isoformat()}")
    return {"ok": True, "total": total, "comision": comision, "precio": corp["precio"]}


def vender(user_id, sigla: str, cantidad: float) -> dict:
    sigla = sigla.upper()
    if sigla not in C.CORPORATIVO_POR_SIGLA or cantidad <= 0:
        raise ValueError("Operación inválida")
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo = U.obtener_universo(user_id)
        if not universo:
            raise ValueError("Primero activá el módulo de Corporativos")
        tenencia = _db()["corp_tenencias"].find_one_and_update(
            {"universo_id": user_id, "sigla": sigla, "cantidad": {"$gte": cantidad}},
            {"$inc": {"cantidad": -cantidad}}, return_document=ReturnDocument.BEFORE)
        if not tenencia:
            raise ValueError("No tenés esa cantidad de acciones")
        corp = _precio(user_id, sigla)
        # el costo promedio sale en proporción a lo vendido
        costo_salida = tenencia["costo_total"] * cantidad / tenencia["cantidad"]
        _db()["corp_tenencias"].update_one({"_id": tenencia["_id"]}, {"$inc": {"costo_total": -round(costo_salida, 2)}})
        bruto = cantidad * corp["precio"]
        comision = max(1, round(bruto * C.COMISION_BOLSA))
        neto = int(round(bruto - comision))
        _acreditar(user_id, neto)
        ciclo = U.ciclo_en_curso(universo)
        _oper(user_id, sigla, "VENTA", cantidad, corp["precio"], neto, ciclo, comision)
    return {"ok": True, "neto": neto, "comision": comision, "resultado": int(neto - costo_salida)}


def repartir_dividendo(user_id, fraccion: float) -> dict:
    """El CEO reparte hasta FRACCION_MAX_DIVIDENDO de la utilidad del último ciclo (una vez por ciclo); sube la acción."""
    if not (0 < fraccion <= C.FRACCION_MAX_DIVIDENDO):
        raise ValueError(f"El dividendo va de 1% a {C.FRACCION_MAX_DIVIDENDO:.0%} de la utilidad")
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo = U.obtener_universo(user_id)
        if not universo or universo["estado"] != "EN_CARGO":
            raise ValueError("Solo el CEO en funciones decide el dividendo")
        sigla = universo["cargo"]["sigla"]
        corp = _db()["corp_corporativos"].find_one({"universo_id": user_id, "sigla": sigla})
        ciclo = U.ciclo_en_curso(universo)
        if corp.get("dividendo_ciclo") == ciclo:
            raise ValueError("Ya repartiste un dividendo este ciclo")
        utilidad = ((corp.get("historial") or [{}])[-1]).get("utilidad", 0)
        if utilidad <= 0:
            raise ValueError("No hubo utilidad el último ciclo: no hay nada que repartir")
        monto = int(utilidad * fraccion)
        actualizado = _db()["corp_corporativos"].find_one_and_update(
            {"_id": corp["_id"], "capital": {"$gte": monto}},
            {"$inc": {"capital": -monto}, "$set": {"dividendo_ciclo": ciclo,
                                                   "sentimiento": round(R.limitar(corp.get("sentimiento", 1) + C.SENTIMIENTO_DIVIDENDO, *C.SENTIMIENTO_RANGO), 4)}})
        if not actualizado:
            raise ValueError("Capital insuficiente")
        _db()["corp_movimientos"].insert_one({"universo_id": user_id, "sigla": sigla, "ciclo": ciclo, "tipo": "DIVIDENDO", "monto": -monto,
                                              "detalle": f"Dividendo a los accionistas ({fraccion:.0%} de la utilidad)", "creado_en": datetime.utcnow()})
        parte = _pagar_dividendo(user_id, sigla, monto, ciclo, actualizado)
    return {"ok": True, "monto": monto, "parte": parte}


# --- Vista ---------------------------------------------------------------------------------------
def obtener_bolsa(user_id) -> Optional[dict]:
    universo = U.obtener_universo(user_id)
    if not universo:
        return None
    U.poner_al_dia(user_id)
    universo = U.obtener_universo(user_id)
    corps = list(_db()["corp_corporativos"].find({"universo_id": user_id}))
    tenencias = {t["sigla"]: t for t in _db()["corp_tenencias"].find({"universo_id": user_id})}
    saldo = (_db()["usuarios"].find_one(U.filtro_usuario(user_id), {"monto": 1}) or {}).get("monto", 0)
    tope = C.ACCIONES_POR_CORPORATIVO * C.TOPE_TENENCIA

    # Serie por ciclo: precio de cada corporativo e índice FIFAV 10 (promedio de precio / precio inicial, base 100)
    ciclos = sorted({h["ciclo"] for c in corps for h in (c.get("historial") or [])})
    series = {}
    for c in corps:
        por_ciclo = {h["ciclo"]: h["precio"] for h in (c.get("historial") or [])}
        series[c["sigla"]] = [round(por_ciclo[k] / c["precio_inicial"] * 100, 1) if k in por_ciclo and c["precio_inicial"] else None for k in ciclos]
    indice = [round(mean(v for v in col if v is not None), 1) if any(v is not None for v in col) else None
              for col in zip(*series.values())] if ciclos else []

    filas, cartera_valor, cartera_costo = [], 0, 0
    for c in sorted(corps, key=lambda c: -c["precio"] * C.ACCIONES_POR_CORPORATIVO):
        info = C.CORPORATIVO_POR_SIGLA[c["sigla"]]
        t = tenencias.get(c["sigla"]) or {}
        cantidad = round(t.get("cantidad") or 0, 2)
        valor = cantidad * c["precio"]
        cartera_valor += valor
        cartera_costo += t.get("costo_total") or 0 if cantidad else 0
        filas.append({
            "sigla": c["sigla"], "nombre": info["nombre"], "tier": info["tier"], "logo": url_logo_corporativo(c["sigla"]),
            "color": info["colores"][0], "precio": c["precio"], "variacion_ciclo": round((c.get("variacion_ciclo") or 0) * 100, 1),
            "variacion_total": round((c["precio"] / c["precio_inicial"] - 1) * 100, 1) if c["precio_inicial"] else 0,
            "capitalizacion": int(c["precio"] * C.ACCIONES_POR_CORPORATIVO), "capital": c["capital"],
            "cantidad": cantidad, "valor": int(valor), "costo": int(t.get("costo_total") or 0) if cantidad else 0,
            "resultado": int(valor - (t.get("costo_total") or 0)) if cantidad else 0,
            "participacion": round(cantidad / C.ACCIONES_POR_CORPORATIVO * 100, 2),
            "disponible": max(0, int(tope - cantidad)), "bloqueo_compra": _bloqueo_insider(universo, c["sigla"]),
            "es_del_usuario": c.get("es_del_usuario"), "serie": series.get(c["sigla"], []),
        })
    bloqueadas = [{**a, "logo": url_logo_corporativo(a["sigla"]), "valor_hoy": int(a["cantidad"] * next((c["precio"] for c in corps if c["sigla"] == a["sigla"]), 0))}
                  for a in (universo.get("acciones_bloqueadas") or [])]
    operaciones = list(_db()["corp_operaciones_bolsa"].find({"universo_id": user_id}).sort("creado_en", -1).limit(15))
    cargo = universo.get("cargo") or {}
    mi_corp = next((c for c in corps if c["sigla"] == cargo.get("sigla")), None) if universo["estado"] == "EN_CARGO" else None
    dividendo = None
    if mi_corp:
        utilidad = ((mi_corp.get("historial") or [{}])[-1]).get("utilidad", 0)
        dividendo = {"sigla": mi_corp["sigla"], "utilidad": utilidad, "maximo": int(max(0, utilidad) * C.FRACCION_MAX_DIVIDENDO),
                     "disponible": utilidad > 0 and mi_corp.get("dividendo_ciclo") != U.ciclo_en_curso(universo)}
    return {
        "universo": universo, "filas": filas, "saldo": saldo, "ciclos": ciclos, "indice": indice,
        "indice_actual": indice[-1] if indice else 100, "cartera_valor": int(cartera_valor), "cartera_costo": int(cartera_costo),
        "bloqueadas": bloqueadas, "operaciones": operaciones, "dividendo": dividendo, "ciclo": U.ciclo_en_curso(universo),
        "reglas": {"comision": C.COMISION_BOLSA, "tope": C.TOPE_TENENCIA, "acciones": C.ACCIONES_POR_CORPORATIVO,
                   "banda": C.BANDA_COTIZACION_CICLO, "max_dividendo": C.FRACCION_MAX_DIVIDENDO},
    }
