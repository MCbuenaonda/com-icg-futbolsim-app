"""
Corporativos Deportivos — datos para las vistas (/corporativo y /corporativo/{sigla}). Cada vista primero pone
al día el universo del usuario (corporativo_universo_service.poner_al_dia).
"""
from datetime import datetime
from typing import Optional

from bson import ObjectId

from config import corporativos as C
from services import corporativo_reglas as R
from services import corporativo_fichajes_service as F
from services import corporativo_universo_service as U
from services.corporativo_mercado_service import afines, valores
from services.imagenes_pais_service import url_logo_corporativo

ESTADOS_CARRERA = {
    "BUSCANDO": {"titulo": "En búsqueda de empleo", "icono": "bi-search", "color": "info"},
    "EN_CARGO": {"titulo": "En funciones", "icono": "bi-briefcase-fill", "color": "success"},
    "PAUSA": {"titulo": "Carrera en pausa", "icono": "bi-pause-circle-fill", "color": "warning"},
    "PREAVISO": {"titulo": "En preaviso", "icono": "bi-box-arrow-right", "color": "warning"},
}


def _info_corp(sigla: str) -> dict:
    corp = C.CORPORATIVO_POR_SIGLA[sigla]
    return {**corp, "logo": url_logo_corporativo(sigla), "color": corp["colores"][0], "acento": corp["colores"][1],
            "capital_inicial": C.TIERS[corp["tier"]]["capital"], "fama_minima": C.TIERS[corp["tier"]]["fama_minima"]}


def catalogo_corporativos() -> list:
    """Los 10 corporativos sin universo (vista de bienvenida): datos fijos + cartera de la plantilla de siembra."""
    plantilla = {f["sigla"]: f for f in U.db["corp_plantilla_siembra"].find({})}
    salida = []
    for corp in C.CORPORATIVOS:
        fila = plantilla.get(corp["sigla"], {})
        salida.append({**_info_corp(corp["sigla"]), "n_selecciones": len(fila.get("selecciones", [])),
                       "n_jugadores": len(fila.get("jugadores", []))})
    return salida


def _resumen_corporativos(universo_id) -> list:
    contratos = U.contratos_activos(universo_id)
    v = valores()
    por_sigla = {}
    for c in contratos:
        fila = por_sigla.setdefault(c["sigla"], {"n_selecciones": 0, "n_jugadores": 0, "valor_cartera": 0})
        fila["n_selecciones" if c["tipo"] == "seleccion" else "n_jugadores"] += 1
        fila["valor_cartera"] += (v["selecciones"] if c["tipo"] == "seleccion" else v["jugadores"]).get(c["ref_id"], 0)
    salida = []
    for doc in U.db["corp_corporativos"].find({"universo_id": universo_id}):
        fila = por_sigla.get(doc["sigla"], {"n_selecciones": 0, "n_jugadores": 0, "valor_cartera": 0})
        salida.append({**_info_corp(doc["sigla"]), **fila, "capital": doc["capital"], "precio": doc["precio"],
                       "precio_inicial": doc["precio_inicial"], "es_del_usuario": doc["es_del_usuario"],
                       "confianza": doc["confianza"], "reputacion": doc["reputacion"],
                       "variacion": round((doc["precio"] / doc["precio_inicial"] - 1) * 100, 1) if doc["precio_inicial"] else 0})
    salida.sort(key=lambda c: (-C.ORDEN_TIER[c["tier"]], -c["valor_cartera"]))
    return salida


def obtener_vista_inicio(user_id) -> dict:
    universo = U.obtener_universo(user_id)
    if not universo:
        return {"universo": None, "catalogo": catalogo_corporativos(), "reloj": U.estado_reloj()}
    resumen = U.poner_al_dia(user_id)
    universo = U.obtener_universo(user_id)
    corporativos = _resumen_corporativos(user_id)
    ofertas = []
    for o in U.db["corp_ofertas_empleo"].find({"universo_id": user_id, "estado": {"$in": ["PENDIENTE", "EN_ESPERA"]}}).sort("ciclo", -1):
        ofertas.append({**o, "tipo": o.get("tipo", "EMPLEO"), "corp": _info_corp(o["sigla"]),
                        "objetivos_texto": [C.OBJETIVOS[x] for x in o["objetivos"]],
                        "ciclos_restantes": o["vence_ciclo"] - U.ciclo_en_curso(universo) + 1,
                        **BOTONES_OFERTA.get((o.get("tipo", "EMPLEO"), o["estado"]), BOTONES_OFERTA[("EMPLEO", "PENDIENTE")])})
    avisos = list(U.db["corp_avisos"].find({"universo_id": user_id}).sort("creado_en", -1).limit(12))
    cargo = universo.get("cargo")
    mi_corp = None
    if cargo:
        mi_corp = next((c for c in corporativos if c["sigla"] == cargo["sigla"]), None)
        doc = U.db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": cargo["sigla"]},
                                                  {"historial": 1, "ciclo_actual": 1}) or {}
        historial = doc.get("historial") or []
        ultimo = historial[-1] if historial else None
        ultimo_pago = U.db["corp_movimientos"].find_one({"universo_id": user_id, "tipo": "SUELDO_CEO"}, sort=[("ciclo", -1)])
        ciclo_ahora = U.ciclo_en_curso(universo)
        bloqueadas = [a for a in (universo.get("acciones_bloqueadas") or []) if a["consolida_ciclo"] > ciclo_ahora - 1]
        estado_obj = cargo.get("objetivos_estado") or {}
        mi_corp = {**mi_corp, "cargo": cargo, "objetivos_texto": [C.OBJETIVOS[x] for x in cargo["objetivos"]],
                   "objetivos": [{"texto": C.OBJETIVOS[x], **(estado_obj.get(x) or {"ok": None, "detalle": "se evalúa al cierre del ciclo"})}
                                 for x in cargo["objetivos"]],
                   "ultimo_pago": ultimo_pago, "acciones_bloqueadas": bloqueadas,
                   "acciones_bloqueadas_valor": sum(a["valor_al_otorgar"] for a in bloqueadas),
                   "preaviso": universo.get("preaviso") if universo["estado"] == "PREAVISO" else None,
                   "ciclos_en_cargo": U.ciclo_en_curso(universo) - cargo["desde_ciclo"],
                   "historial": historial[-20:], "ultimo_ciclo": ultimo, "ciclo_actual": doc.get("ciclo_actual") or {},
                   "honorarios_estimados": _honorarios_estimados(user_id, cargo["sigla"]),
                   "por_vencer": sum(1 for c in U.contratos_activos(user_id, cargo["sigla"])
                                     if c["hasta_ciclo"] - U.ciclo_en_curso(universo) + 1 <= C.CICLOS_AVISO_RENOVACION),
                   "movimientos": list(U.db["corp_movimientos"].find({"universo_id": user_id, "sigla": cargo["sigla"]})
                                       .sort("creado_en", -1).limit(12))}
    if mi_corp:
        mi_corp.update(_bandeja_mercado(user_id, universo, mi_corp))
    reloj = U.estado_reloj(universo)
    if not universo.get("primeras_ofertas"):
        reloj["partidos_para_ofertas"] = max(0, universo["primeras_ofertas_seq"] - reloj["seq"])
    return {
        "universo": universo, "estado": ESTADOS_CARRERA[universo["estado"]], "ofertas": ofertas, "avisos": avisos,
        "corporativos": corporativos, "mi_corporativo": mi_corp, "reloj": reloj, "puesta_al_dia": resumen,
        "pausa_restante": (universo["pausa_hasta_ciclo"] - U.ciclo_en_curso(universo) + 1) if universo.get("pausa_hasta_ciclo") else None,
        "historial": list(reversed(universo.get("historial_cargos") or [])),
        "ciclo": U.ciclo_en_curso(universo),
    }


def obtener_perfil_corporativo(user_id, sigla: str) -> Optional[dict]:
    if sigla not in C.CORPORATIVO_POR_SIGLA:
        return None
    universo = U.obtener_universo(user_id)
    if not universo:
        return None
    U.poner_al_dia(user_id)
    doc = U.db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": sigla})
    v = valores()
    region = afines(sigla)
    ciclo = U.ciclo_en_curso(U.obtener_universo(user_id))
    selecciones, jugadores = [], []
    for c in U.contratos_activos(user_id, sigla):
        valor_c = (v["selecciones"] if c["tipo"] == "seleccion" else v["jugadores"]).get(c["ref_id"], 0)
        restantes = c["hasta_ciclo"] - ciclo + 1
        base = {"ref_id": c["ref_id"], "contrato_id": str(c["_id"]), "hasta_ciclo": c["hasta_ciclo"], "ciclos_restantes": restantes,
                "satisfaccion": c["satisfaccion"], "origen": c.get("origen"), "renta_total": c.get("renta_total", 0),
                "honorarios_total": c.get("honorarios_total", 0), "neto": c.get("renta_total", 0) - c.get("honorarios_total", 0),
                "partidos": c.get("partidos", 0), "honorario": R.honorario(c["tipo"], valor_c),
                "costo_renovar": R.prima_referencia(valor_c), "puede_renovar": restantes <= C.CICLOS_AVISO_RENOVACION,
                "costo_rescindir": _costo_rescision(c, valor_c, ciclo)}
        if c["tipo"] == "seleccion":
            p = v["info_paises"].get(c["ref_id"], {})
            selecciones.append({**base, **p, "valor": v["selecciones"].get(c["ref_id"], 0), "de_region": c["ref_id"] in region})
        else:
            j = v["info_jugadores"].get(c["ref_id"], {})
            p = v["info_paises"].get(j.get("pais_id"), {})
            jugadores.append({**base, **j, "pais": p.get("nombre"), "bandera": p.get("bandera"),
                              "valor": v["jugadores"].get(c["ref_id"], 0), "de_region": j.get("pais_id") in region})
    selecciones.sort(key=lambda x: -x["valor"])
    jugadores.sort(key=lambda x: -x["valor"])
    valor_cartera = sum(x["valor"] for x in selecciones) + sum(x["valor"] for x in jugadores)
    return {
        "corp": {**_info_corp(sigla), "capital": doc["capital"], "precio": doc["precio"], "precio_inicial": doc["precio_inicial"],
                 "reputacion": doc["reputacion"], "es_del_usuario": doc["es_del_usuario"], "confianza": doc["confianza"],
                 "valor_cartera": valor_cartera,
                 "variacion": round((doc["precio"] / doc["precio_inicial"] - 1) * 100, 1) if doc["precio_inicial"] else 0},
        "selecciones": selecciones, "jugadores": jugadores,
        "perfil_ia": PERFILES_IA.get(C.CORPORATIVO_POR_SIGLA[sigla]["perfil"]),
        "universo": U.obtener_universo(user_id), "ciclo": ciclo,
        "honorarios_ciclo": sum(x["honorario"] for x in selecciones + jugadores),
        "neto_total": sum(x["neto"] for x in selecciones + jugadores),
    }


PERFILES_IA = {
    "conservador": "Prefiere estrellas consolidadas y rara vez vende.",
    "marketing": "Busca valor comercial: selecciones con hinchada y figuras mediáticas.",
    "chequera": "Paga sobreprecio sin pestañear y pide mucho por sus figuras.",
    "cantera": "Apuesta por jóvenes que se valorizan con el tiempo.",
    "equilibrado": "Sin sesgos marcados: compra y vende según el momento.",
    "volumen": "Muchos representados de valor medio para repartir el riesgo.",
    "oportunista": "Caza libres baratos y gangas de último momento.",
}


# --- Acciones del CEO sobre su cartera -----------------------------------------------------------
def _honorarios_estimados(user_id, sigla: str) -> int:
    v = valores()
    return sum(R.honorario(c["tipo"], (v["selecciones"] if c["tipo"] == "seleccion" else v["jugadores"]).get(c["ref_id"], 0))
               for c in U.contratos_activos(user_id, sigla))


def _costo_rescision(contrato: dict, valor: int, ciclo: int) -> int:
    restantes = max(0, contrato["hasta_ciclo"] - ciclo + 1)
    return int(R.honorario(contrato["tipo"], valor) * restantes * C.RESCISION_FRACCION_RESTANTE)


def _contrato_propio(user_id, contrato_id: str):
    universo = U.obtener_universo(user_id)
    if universo and universo["estado"] == "PREAVISO":
        raise ValueError("Durante el preaviso no podés tocar la cartera")
    if not universo or universo["estado"] != "EN_CARGO":
        raise ValueError("Necesitás un cargo de CEO para manejar la cartera")
    if not ObjectId.is_valid(contrato_id):
        raise ValueError("Contrato inválido")
    contrato = U.db["corp_contratos"].find_one({"_id": ObjectId(contrato_id), "universo_id": user_id, "activo": True})
    if not contrato or contrato["sigla"] != universo["cargo"]["sigla"]:
        raise ValueError("Ese representado no es de tu corporativo")
    return universo, contrato


def _nombre_ref(tipo: str, ref_id: int) -> str:
    v = valores()
    return (v["info_paises"] if tipo == "seleccion" else v["info_jugadores"]).get(ref_id, {}).get("nombre", "?")


def renovar_contrato(user_id, contrato_id: str) -> dict:
    """Renueva un contrato a punto de vencer pagando la prima de referencia (5% del valor); +10 de satisfacción."""
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, c = _contrato_propio(user_id, contrato_id)
        ciclo = U.ciclo_en_curso(universo)
        if c["hasta_ciclo"] - ciclo + 1 > C.CICLOS_AVISO_RENOVACION:
            raise ValueError(f"Solo se renueva en los últimos {C.CICLOS_AVISO_RENOVACION} ciclos del contrato")
        valor = U.valor_cartera([c])
        prima = R.prima_referencia(valor)
        corp = U.db["corp_corporativos"].find_one_and_update(
            {"universo_id": user_id, "sigla": c["sigla"], "capital": {"$gte": prima}}, {"$inc": {"capital": -prima}})
        if not corp:
            raise ValueError(f"Capital insuficiente: la renovación cuesta {prima:,}")
        duracion = R.semilla(user_id, "renovar", c["_id"], ciclo).randint(*C.DURACION_CONTRATO)
        nuevo_hasta = c["hasta_ciclo"] + duracion
        U.db["corp_contratos"].update_one({"_id": c["_id"]}, {"$set": {
            "desde_ciclo": ciclo, "hasta_ciclo": nuevo_hasta, "prima": prima, "origen": "RENOVACION",
            "satisfaccion": min(100, c["satisfaccion"] + C.SATISFACCION_RENOVACION)}})
        nombre = _nombre_ref(c["tipo"], c["ref_id"])
        U.db["corp_movimientos"].insert_one({"universo_id": user_id, "sigla": c["sigla"], "ciclo": ciclo, "tipo": "RENOVACION",
                                             "monto": -prima, "detalle": f"Renovación de {nombre} por {duracion} ciclos",
                                             "creado_en": datetime.utcnow()})
    return {"ok": True, "prima": prima, "ciclos": duracion, "nombre": nombre}


def rescindir_contrato(user_id, contrato_id: str) -> dict:
    """Rescinde un contrato pagando el 50% de los honorarios que faltaban; el representado queda libre."""
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, c = _contrato_propio(user_id, contrato_id)
        ciclo = U.ciclo_en_curso(universo)
        costo = _costo_rescision(c, U.valor_cartera([c]), ciclo)
        corp = U.db["corp_corporativos"].find_one_and_update(
            {"universo_id": user_id, "sigla": c["sigla"], "capital": {"$gte": costo}}, {"$inc": {"capital": -costo}})
        if not corp:
            raise ValueError(f"Capital insuficiente: la rescisión cuesta {costo:,}")
        U.db["corp_contratos"].update_one({"_id": c["_id"]}, {"$set": {"activo": False, "fin_ciclo": ciclo, "motivo_fin": "RESCINDIDO"}})
        nombre = _nombre_ref(c["tipo"], c["ref_id"])
        U.db["corp_movimientos"].insert_one({"universo_id": user_id, "sigla": c["sigla"], "ciclo": ciclo, "tipo": "RESCISION",
                                             "monto": -costo, "detalle": f"Rescisión de {nombre}", "creado_en": datetime.utcnow()})
    return {"ok": True, "costo": costo, "nombre": nombre}


# --- Mercado -------------------------------------------------------------------------------------
# Textos de los botones de cada oferta de empleo según (tipo, estado)
BOTONES_OFERTA = {
    ("EMPLEO", "PENDIENTE"): {"etiqueta": "Oferta de trabajo", "si": "Aceptar", "no": "Rechazar",
                              "si_msg": "Asumís la dirección general. Las demás ofertas abiertas se declinan.",
                              "no_msg": "En el próximo cierre de ciclo no recibirás ofertas. Rechazar muchas seguidas te resta fama."},
    ("HEADHUNTING", "PENDIENTE"): {"etiqueta": "Te buscan (confidencial)", "si": "Me interesa", "no": "Rechazar",
                                   "si_msg": "Si tu directorio confía en vos, va a intentar retenerte; si no, empezás el preaviso.",
                                   "no_msg": "Nadie se entera: seguís en tu cargo."},
    ("HEADHUNTING", "EN_ESPERA"): {"etiqueta": "Esperando tu decisión", "si": "Irme igual", "no": None,
                                   "si_msg": "Presentás la renuncia: un ciclo de preaviso y perdés las acciones no consolidadas.",
                                   "no_msg": "Rechazás la oferta y seguís en tu cargo con el sueldo actual."},
    ("RETENCION", "PENDIENTE"): {"etiqueta": "Contraoferta de retención", "si": "Quedarme con aumento", "no": "Irme igual",
                                 "si_msg": "Te quedás y cobrás el sueldo nuevo.", "no_msg": "Presentás la renuncia y empezás el preaviso."},
    ("RENOVACION", "PENDIENTE"): {"etiqueta": "Renovación", "si": "Renovar", "no": "No renovar",
                                  "si_msg": "Arranca una temporada nueva con objetivos nuevos.",
                                  "no_msg": "Tu contrato termina y volvés a buscar empleo (sin pausa)."},
}

TIPOS_PROPUESTA = {
    "PROPUESTA": {"titulo": "Quiere firmar con ustedes", "icono": "bi-person-plus-fill", "si": "Firmar", "no": "Rechazar"},
    "OFERTA_IA": {"titulo": "Oferta de compra", "icono": "bi-cash-stack", "si": "Vender", "no": "Rechazar"},
    "SALIDA": {"titulo": "Pide salir", "icono": "bi-emoji-frown-fill", "si": "Liberarlo", "no": "Negarme"},
    "CONTRAOFERTA": {"titulo": "Contraoferta", "icono": "bi-arrow-left-right", "si": "Pagar y firmar", "no": "Dejarla"},
}


def _bandeja_mercado(user_id, universo: dict, mi_corp: dict) -> dict:
    v = valores()
    ciclo = U.ciclo_en_curso(universo)
    propuestas = []
    for o in U.db["corp_ofertas"].find({"universo_id": user_id, "estado": "PENDIENTE", "tipo": {"$in": list(TIPOS_PROPUESTA)}}).sort("ciclo", -1):
        propuestas.append({**o, **TIPOS_PROPUESTA[o["tipo"]], "nombre": F.nombre_ref(o["ref_tipo"], o["ref_id"]),
                           "valor": F._valor(o["ref_tipo"], o["ref_id"]), "pais_id": F._pais_de(o["ref_tipo"], o["ref_id"]),
                           "costo": o.get("prima", 0) + (o.get("monto", 0) if o["tipo"] == "CONTRAOFERTA" else 0)})
    mis_ofertas = []
    for o in U.db["corp_ofertas"].find({"universo_id": user_id, "tipo": {"$in": ["FICHAJE", "TRASPASO"]}}).sort("creada_en", -1).limit(8):
        mis_ofertas.append({**o, "nombre": F.nombre_ref(o["ref_tipo"], o["ref_id"]), "pais_id": F._pais_de(o["ref_tipo"], o["ref_id"]),
                            "faltan": max(0, o.get("resolver_seq", 0) - U.seq_actual())})
    informe = F.ultimo_scouting(user_id)
    if informe:
        informe["jugadores"] = [{**x, "nombre": F.nombre_ref("jugador", x["ref_id"]), "pais_id": F._pais_de("jugador", x["ref_id"]),
                                 "valor": F._valor("jugador", x["ref_id"])} for x in informe["jugadores"]]
    corp = U.db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": mi_corp["sigla"]}, {"marketing_ciclo": 1})
    return {"propuestas": propuestas, "mis_ofertas": mis_ofertas, "scouting": informe,
            "scouting_disponible": not informe or informe["ciclo"] != ciclo,
            "marketing_disponible": (corp or {}).get("marketing_ciclo") != ciclo,
            "costo_scouting": C.COSTO_SCOUTING, "costo_marketing": C.COSTO_MARKETING,
            "ventana": U.ventana_traspasos(ciclo), "reputacion": (U.db["corp_corporativos"].find_one(
                {"universo_id": user_id, "sigla": mi_corp["sigla"]}, {"reputacion": 1}) or {}).get("reputacion")}


POR_PAGINA_MERCADO = 30


def obtener_mercado(user_id, tipo: str = "jugador", vista: str = "libres", q: str = "", conf: Optional[int] = None,
                    region: bool = False, edad_max: Optional[int] = None, orden: str = "valor", pagina: int = 1) -> Optional[dict]:
    universo = U.obtener_universo(user_id)
    if not universo:
        return None
    U.poner_al_dia(user_id)
    universo = U.obtener_universo(user_id)
    tipo = tipo if tipo in ("jugador", "seleccion") else "jugador"
    vista = vista if vista in ("libres", "rivales") else "libres"
    v = valores()
    ciclo = U.ciclo_en_curso(universo)
    cargo = universo.get("cargo") or {}
    sigla = cargo.get("sigla")
    contratos = U.contratos_activos(user_id)
    duenio = {(c["tipo"], c["ref_id"]): c for c in contratos}
    corp = U.db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": sigla}) if sigla else None
    cartera = F.calidad_cartera(contratos, sigla) if sigla else 0
    region_ids = afines(sigla) if sigla else set()
    scout = {x["ref_id"] for x in ((F.ultimo_scouting(user_id) or {}).get("jugadores") or [])}
    pendientes = {(o["ref_tipo"], o["ref_id"]) for o in U.db["corp_ofertas"].find(
        {"universo_id": user_id, "estado": "PENDIENTE", "tipo": {"$in": ["FICHAJE", "TRASPASO"]}}, {"ref_tipo": 1, "ref_id": 1})}

    fuente = v["selecciones"] if tipo == "seleccion" else v["jugadores"]
    q = (q or "").strip().lower()
    filas = []
    for ref_id, valor in fuente.items():
        c = duenio.get((tipo, ref_id))
        if (vista == "libres") == bool(c) or (c and c["sigla"] == sigla):
            continue
        if tipo == "jugador":
            info = v["info_jugadores"].get(ref_id, {})
            pais_id = info.get("pais_id")
            if edad_max and (info.get("edad") or 99) > edad_max:
                continue
        else:
            info = v["info_paises"].get(ref_id, {})
            pais_id = ref_id
        pinfo = v["info_paises"].get(pais_id, {})
        if q and q not in (info.get("nombre") or "").lower() and q not in (pinfo.get("nombre") or "").lower():
            continue
        if conf and pinfo.get("confederacion_id") != conf:
            continue
        if region and pais_id not in region_ids:
            continue
        filas.append({"ref_id": ref_id, "valor": valor, "pais_id": pais_id, "info": info, "pinfo": pinfo, "contrato": c})
    filas.sort(key=lambda f: f["valor"], reverse=orden != "valor_asc")
    total = len(filas)
    pagina = max(1, pagina)
    filas = filas[(pagina - 1) * POR_PAGINA_MERCADO: pagina * POR_PAGINA_MERCADO]
    posiciones = {p["id"]: p.get("siglas") for p in U.db["posiciones"].find({}, {"id": 1, "siglas": 1})}
    salida = []
    for f in filas:
        ref_prima = R.prima_referencia(f["valor"])
        fila = {"ref_id": f["ref_id"], "tipo": tipo, "nombre": f["info"].get("nombre"), "valor": f["valor"], "pais_id": f["pais_id"],
                "pais": f["pinfo"].get("nombre"), "bandera": f["pinfo"].get("bandera"), "rankin": f["pinfo"].get("rankin"),
                "edad": f["info"].get("edad"), "posicion": posiciones.get(f["info"].get("posicion_id")),
                "prima_ref": ref_prima, "de_region": f["pais_id"] in region_ids, "scouting": f["ref_id"] in scout and tipo == "jugador",
                "pendiente": (tipo, f["ref_id"]) in pendientes}
        if corp:
            fila["base"] = round(F.base_atractivo(corp, universo["fama"], tipo, f["ref_id"], cartera), 2)
            fila["prob"] = round(F.probabilidad(corp, universo["fama"], tipo, f["ref_id"], ref_prima, cartera) * 100)
        if f["contrato"]:
            c = f["contrato"]
            perfil = C.CORPORATIVO_POR_SIGLA[c["sigla"]]["perfil"]
            fila.update(sigla_actual=c["sigla"], logo_actual=url_logo_corporativo(c["sigla"]), satisfaccion=c["satisfaccion"],
                        clausula=int(f["valor"] * C.CLAUSULA_RESCISION_MULTIPLO),
                        pide=int(f["valor"] * C.IA_MULTIPLO_VENTA.get(perfil, C.IA_MULTIPLO_VENTA["default"])))
            if c["satisfaccion"] < C.SATISFACCION_PIDE_SALIR and corp:
                fila["prob"] = min(95, fila["prob"] + int(C.BONO_SATISFACCION_CAMBIO * 100))
        salida.append(fila)
    confederaciones = list(U.db["confederaciones"].find({"principal": 1}, {"_id": 0, "id": 1, "nombre": 1}).sort("id", 1))
    return {
        "universo": universo, "sigla": sigla, "corp": corp, "filas": salida, "total": total, "pagina": pagina,
        "paginas": max(1, -(-total // POR_PAGINA_MERCADO)), "ventana": U.ventana_traspasos(ciclo), "ciclo": ciclo,
        "filtros": {"tipo": tipo, "vista": vista, "q": q, "conf": conf, "region": region, "edad_max": edad_max, "orden": orden},
        "confederaciones": confederaciones, "reglas": {
            "peso_oferta": C.PESOS_ATRACTIVO["oferta"], "ideal": C.OFERTA_IDEAL_MULTIPLO, "rango": C.PRIMA_RANGO_OFERTA,
            "min": C.PROBABILIDAD_ACEPTA[0], "max": C.PROBABILIDAD_ACEPTA[1], "duracion": C.DURACION_CONTRATO,
            "responde": C.PARTIDOS_RESPUESTA_FICHAJE},
        "cartera": cartera,
    }


# --- Ranking de CEOs entre usuarios --------------------------------------------------------------
def obtener_ranking_ceos(user_id) -> list:
    """Todos los usuarios con carrera de CEO: fama, cargo actual, trayectoria, total cobrado y acciones (cada uno en su universo)."""
    universos = list(U.db["corp_universos"].find({}))
    if not universos:
        return []
    cobrado = {d["_id"]: -d["total"] for d in U.db["corp_movimientos"].aggregate([
        {"$match": {"tipo": "SUELDO_CEO"}}, {"$group": {"_id": "$universo_id", "total": {"$sum": "$monto"}}}])}
    precios = {(c["universo_id"], c["sigla"]): c.get("precio", 0) for c in U.db["corp_corporativos"].find({}, {"universo_id": 1, "sigla": 1, "precio": 1})}
    acciones = {}
    for t in U.db["corp_tenencias"].find({"cantidad": {"$gt": 0}}):
        acciones[t["universo_id"]] = acciones.get(t["universo_id"], 0) + t["cantidad"] * precios.get((t["universo_id"], t["sigla"]), 0)
    nombres = {str(u["_id"]): u.get("nombre") or u.get("username") for u in U.db["usuarios"].find(
        {"_id": {"$in": [U.filtro_usuario(x["_id"])["_id"] for x in universos]}}, {"username": 1, "nombre": 1})}
    filas = []
    for u in universos:
        uid = u["_id"]
        historial = u.get("historial_cargos") or []
        ciclo = u["ultimo_ciclo"] + 1
        ciclos_ceo = sum(h["hasta_ciclo"] - h["desde_ciclo"] + 1 for h in historial)
        cargo = u.get("cargo") if u.get("estado") in ("EN_CARGO", "PREAVISO") else None
        if cargo:
            ciclos_ceo += ciclo - cargo["desde_ciclo"]
        siglas = [h["sigla"] for h in historial] + ([cargo["sigla"]] if cargo else [])
        mejor_tier = max((C.CORPORATIVO_POR_SIGLA[s]["tier"] for s in siglas), key=lambda t: C.ORDEN_TIER[t], default=None)
        filas.append({
            "usuario_id": str(uid), "nombre": nombres.get(str(uid), "?"), "fama": u["fama"], "estado": ESTADOS_CARRERA[u["estado"]],
            "cargo": {**_info_corp(cargo["sigla"])} if cargo else None, "cargos": len(siglas), "ciclos_ceo": ciclos_ceo,
            "despidos": sum(1 for h in historial if h.get("motivo") == "DESPIDO"),
            "renuncias": sum(1 for h in historial if h.get("motivo") == "RENUNCIA" or str(h.get("motivo", "")).startswith("CAMBIO")),
            "mejor_tier": mejor_tier, "cobrado": int(cobrado.get(uid, 0)), "acciones": int(acciones.get(uid, 0)),
            "trayectoria": [{"sigla": s, "logo": url_logo_corporativo(s)} for s in siglas],
        })
    filas.sort(key=lambda f: (-f["fama"], -f["cobrado"], f["nombre"].lower()))
    for i, f in enumerate(filas):
        f["posicion"] = 1 + sum(1 for g in filas if (g["fama"], g["cobrado"]) > (f["fama"], f["cobrado"]))
        f["soy_yo"] = f["usuario_id"] == str(user_id)
    return filas
