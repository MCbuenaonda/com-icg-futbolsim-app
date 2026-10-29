"""
Corporativos Deportivos — MARCAS Y PATROCINIOS (reemplaza al acuerdo publicitario).

Las marcas del catálogo (colección `marcas`, ficticias: generar_marcas.py) patrocinan a los representados de
cualquier corporativo del universo:
  - se ACERCAN solas en el cierre de cada ciclo (a veces antes dejan correr un RUMOR entre 3-4 candidatos);
    a un representado del usuario le llega una OFERTA para aceptar o rechazar; la IA acepta casi siempre;
  - el CEO puede PROMOVER a los suyos con una marca interesada (se resuelve al cierre del ciclo);
  - pagan una firma y un monto por ciclo; del corporativo del usuario, MARCA_COMISION_CEO va a su nómina
    (se cobra con el sueldo en corporativo_carrera_service.pagar_ceo);
  - con riesgo medio (roja, goleada, eliminación, sin jugar, mala racha) avisan; con riesgo alto cortan;
    al vencer pueden renovar.
Reglas: hasta MARCAS_MAX_POR_REPRESENTADO marcas por representado, nunca dos del mismo rubro, cupos por marca.

Cada movimiento deja una publicación en la RED SOCIAL del universo (corp_feed): firma, rumor, renovación,
despedida, y respuestas de la marca a los partidos de sus patrocinados (services/red_social_textos.py).

Colecciones (con universo_id, PERMANENTES como el resto de corp_*):
  corp_patrocinios {_id, universo_id, sigla, contrato_id, tipo, ref_id, marca_id, rubro, encaje, pago_ciclo, firma,
                    desde_ciclo, hasta_ciclo, pagos, cobrado, comision, riesgo, aviso_ciclo, origen MARCA|PROMOCION,
                    estado OFERTA|PROMOCION|ACTIVO|TERMINADO|CORTADO|RECHAZADA|VENCIDA|DESCARTADA, motivo, ciclo, seq,
                    desde_seq (cobra desde), vence_seq (ofertas), aviso_seq, ronda (promociones)}
  corp_marcas_rumores {_id, universo_id, marca_id, ciclo, candidatos [{tipo, ref_id, sigla, contrato_id, encaje}], estado}
  corp_feed {_id, universo_id, tipo FIRMA|RUMOR|RENOVACION|DESPEDIDA|REACCION, marca_id, ciclo, juego_id, fecha, hora,
             orden, texto, refs [{tipo, ref_id, nombre}], sigla, creado_en}
"""
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

from bson import ObjectId
from pymongo import InsertOne, UpdateOne
from pymongo.errors import BulkWriteError, DuplicateKeyError

from config import corporativos as C
from services import corporativo_reglas as R
from services import corporativo_universo_service as U
from services import red_social_textos as T
from services.corporativo_mercado_service import valores

db = U.db
ESTADOS_VIGENTES = ["ACTIVO", "OFERTA", "PROMOCION"]
SECTOR_POR_POSICION = {1: "Portero", 2: "Defensa", 3: "Defensa", 4: "Defensa", 5: "Defensa",
                       6: "Medio", 7: "Medio", 8: "Medio", 9: "Delantero", 10: "Delantero", 11: "Delantero"}
_cache_catalogo: dict = {}
_cache_anclas: Dict[int, dict] = {}
_hilo = threading.local()   # lote de escrituras del poner_al_dia en curso (uno por hilo/request)


# --- Escrituras en lote: cada escritura suelta a Atlas cuesta ~0,2 s; el cierre de un ciclo hace decenas ----------
def _lote() -> Optional[dict]:
    return getattr(_hilo, "lote", None)


def iniciar_lote() -> None:
    if _lote() is None:
        _hilo.lote = {}


def _espejo_activo() -> Optional[dict]:
    return getattr(_hilo, "espejo", None)


def _aplicar(doc: dict, cambios: dict) -> None:
    for k, v in (cambios.get("$set") or {}).items():
        doc[k] = v
    for k, v in (cambios.get("$inc") or {}).items():
        doc[k] = (doc.get(k) or 0) + v


def _ins(col: str, doc: dict) -> None:
    esp = _espejo_activo()
    if esp is not None and col in esp:
        esp[col][doc["_id"]] = dict(doc)
    lote = _lote()
    if lote is None:
        try:
            db[col].insert_one(doc)
        except DuplicateKeyError:
            pass
    else:
        lote.setdefault(col, []).append(InsertOne(doc))


def _upd(col: str, _id, cambios: dict) -> None:
    esp = _espejo_activo()
    if esp is not None and col in esp and _id in esp[col]:
        _aplicar(esp[col][_id], cambios)
    lote = _lote()
    if lote is None:
        db[col].update_one({"_id": _id}, cambios)
    else:
        lote.setdefault(col, []).append(UpdateOne({"_id": _id}, cambios))


def vaciar_lote() -> None:
    """Manda todo lo acumulado (en el cierre de cada ciclo y al final de cada poner_al_dia). Primero las altas (sin orden;
    un duplicado = reproceso y se ignora) y después las actualizaciones EN ORDEN (un mismo documento puede recibir varias)."""
    lote = _lote()
    _hilo.lote = None
    for col, ops in (lote or {}).items():
        altas = [o for o in ops if isinstance(o, InsertOne)]
        cambios = [o for o in ops if not isinstance(o, InsertOne)]
        for grupo, ordenado in ((altas, False), (cambios, True)):
            if not grupo:
                continue
            try:
                db[col].bulk_write(grupo, ordered=ordenado)
            except BulkWriteError as e:
                otros = [x for x in e.details.get("writeErrors", []) if x.get("code") != 11000]
                if otros:
                    print(f"[marcas] errores al guardar {col}: {otros[:3]}")


# --- Catálogo y contexto --------------------------------------------------------------------------
def catalogo() -> Dict[int, dict]:
    """{marca_id: doc} de la colección `marcas` (no cambia en runtime: caché de 10 minutos)."""
    if _cache_catalogo.get("hasta", 0) < time.time():
        _cache_catalogo["datos"] = {m["id"]: m for m in db["marcas"].find({}, {"_id": 0})}
        _cache_catalogo["hasta"] = time.time() + 600
    return _cache_catalogo["datos"]


def marca_vista(m: dict) -> dict:
    from services.imagenes_pais_service import url_logo_marca
    from config.marcas import ALCANCES, CONFEDERACIONES, PERFILES_MARCA, RUBROS
    pais = valores()["info_paises"].get(m.get("pais_id"), {}) if m["alcance"] == "local" else {}
    return {"pais_nombre": pais.get("nombre"), "pais_bandera": pais.get("bandera"),"id": m["id"], "nombre": m["nombre"], "slug": m["slug"], "logo": url_logo_marca(m["slug"]), "rubro": m["rubro"],
            "rubro_nombre": RUBROS[m["rubro"]]["nombre"], "rubro_icono": RUBROS[m["rubro"]]["icono"], "alcance": m["alcance"],
            "alcance_nombre": ALCANCES[m["alcance"]]["nombre"], "color": m["colores"][0], "color2": m["colores"][1],
            "lema": m.get("lema"), "perfil": PERFILES_MARCA.get(m.get("perfil"), ""), "fidelidad": m.get("fidelidad", 0.5),
            "region": (CONFEDERACIONES.get(m.get("confederacion_id")) if m["alcance"] == "continental" else None),
            "pais_id": m.get("pais_id") if m["alcance"] == "local" else None, "handle": T.handle_marca(m["nombre"]),
            "nivel": m.get("nivel", 2)}


def _ctx_encaje() -> dict:
    """Lo que hace falta para calcular el encaje de muchos representados de una vez (una carga por cierre o vista)."""
    from services.corporativo_service import _contexto_partidos
    ctx = _contexto_partidos()
    v = valores()
    orden = sorted(v["selecciones"], key=lambda pid: v["selecciones"][pid])
    ctx["pct_sel"] = {pid: (i + 1) / len(orden) for i, pid in enumerate(orden)}
    return ctx


def representado(tipo: str, ref_id: int, ctx: dict) -> dict:
    """Datos del representado para corporativo_reglas.encaje_marca."""
    from services.corporativo_ciclo_service import popularidad
    from services.corporativo_service import _titular, juego_de
    v = valores()
    if tipo == "seleccion":
        pais, valor = ref_id, v["selecciones"].get(ref_id, 0)
        rep = {"percentil": ctx["pct_sel"].get(ref_id, 0.5), "edad": None, "leyenda": False, "sector": None, "goles": 0, "titular": None}
    else:
        info = v["info_jugadores"].get(ref_id, {})
        pais, valor = info.get("pais_id"), v["jugadores"].get(ref_id, 0)
        a = ctx["agregado"].get(ref_id) or {}
        rep = {"percentil": v["percentil"].get(ref_id, 0.5), "edad": info.get("edad"), "leyenda": info.get("leyenda"),
               "sector": SECTOR_POR_POSICION.get(info.get("posicion_id")), "goles": (a.get("metricas") or {}).get("goles", 0),
               "titular": _titular(ref_id, pais, ctx)}
    juego = juego_de(tipo, ref_id, ctx)
    rep.update(tipo=tipo, pais_id=pais, valor=valor, confederacion_id=v["info_paises"].get(pais, {}).get("confederacion_id"),
               popularidad=popularidad(tipo, ref_id, valor), forma=ctx["forma"].get(pais), partidos_2=juego.get("partidos_2", 0),
               eliminada=juego["estado"] == "eliminada")
    return rep


def _nombre(tipo: str, ref_id: int) -> str:
    v = valores()
    return (v["info_paises"] if tipo == "seleccion" else v["info_jugadores"]).get(ref_id, {}).get("nombre", "?")


def _pais_nombre(tipo: str, ref_id: int) -> str:
    v = valores()
    pais = ref_id if tipo == "seleccion" else v["info_jugadores"].get(ref_id, {}).get("pais_id")
    return v["info_paises"].get(pais, {}).get("nombre", "")


def espejo(estado) -> dict:
    """Patrocinios vigentes y rumores abiertos del universo EN MEMORIA durante un poner_al_dia: se cargan una vez y las
    escrituras de las rondas los actualizan (_ins/_upd), así cada ronda (cada 4 partidos) no consulta la base."""
    e = getattr(estado, "_espejo_marcas", None)
    if e is None:
        uid = estado.uid
        e = estado._espejo_marcas = {
            "corp_patrocinios": {p["_id"]: p for p in db["corp_patrocinios"].find({"universo_id": uid, "estado": {"$in": ESTADOS_VIGENTES}})},
            "corp_marcas_rumores": {r["_id"]: r for r in db["corp_marcas_rumores"].find({"universo_id": uid, "estado": "ABIERTO"})}}
    return e


def _vigentes(col: str, estado_doc: str) -> list:
    return [d for d in list(_espejo_activo()[col].values()) if d.get("estado") == estado_doc]


def _ocupacion(uid, esp: Optional[dict] = None) -> dict:
    """Lo comprometido en el universo: rubros por representado, marcas por representado y cupos usados por marca."""
    cat = catalogo()
    por_rep: Dict[tuple, list] = {}
    por_marca: Dict[int, int] = {}
    fuente_pat = ([p for p in esp["corp_patrocinios"].values() if p.get("estado") in ESTADOS_VIGENTES] if esp is not None else
                  db["corp_patrocinios"].find({"universo_id": uid, "estado": {"$in": ESTADOS_VIGENTES}},
                                              {"tipo": 1, "ref_id": 1, "marca_id": 1, "estado": 1}))
    for p in fuente_pat:
        por_rep.setdefault((p["tipo"], p["ref_id"]), []).append(p["marca_id"])
        if p["estado"] != "PROMOCION":
            por_marca[p["marca_id"]] = por_marca.get(p["marca_id"], 0) + 1
    fuente_rum = ([r for r in esp["corp_marcas_rumores"].values() if r.get("estado") == "ABIERTO"] if esp is not None else
                  db["corp_marcas_rumores"].find({"universo_id": uid, "estado": "ABIERTO"}, {"marca_id": 1}))
    for r in fuente_rum:
        por_marca[r["marca_id"]] = por_marca.get(r["marca_id"], 0) + 1
    rubros = {k: {cat[m]["rubro"] for m in ms if m in cat} for k, ms in por_rep.items()}
    return {"por_rep": por_rep, "rubros": rubros, "por_marca": por_marca}


def puede_patrocinar(marca: dict, tipo: str, ref_id: int, ocup: dict) -> Optional[str]:
    """None si la marca puede patrocinar a este representado; si no, el motivo."""
    k = (tipo, ref_id)
    if marca["id"] in ocup["por_rep"].get(k, []):
        return "Ya está con esta marca (o en conversaciones)"
    if len(ocup["por_rep"].get(k, [])) >= C.MARCAS_MAX_POR_REPRESENTADO:
        return f"Ya tiene {C.MARCAS_MAX_POR_REPRESENTADO} marcas"
    if marca["rubro"] in ocup["rubros"].get(k, set()):
        return "Ya tiene una marca de ese rubro (exclusividad)"
    if ocup["por_marca"].get(marca["id"], 0) >= C.MARCA_CUPOS_NIVEL.get(marca.get("nivel", 2), 1):
        return "La marca no tiene cupo en este momento"
    return None


def _ocupar(ocup: dict, marca: dict, tipo: str, ref_id: int, cupo: bool = True) -> None:
    k = (tipo, ref_id)
    ocup["por_rep"].setdefault(k, []).append(marca["id"])
    ocup["rubros"].setdefault(k, set()).add(marca["rubro"])
    if cupo:
        ocup["por_marca"][marca["id"]] = ocup["por_marca"].get(marca["id"], 0) + 1


def _liberar(ocup: dict, marca_id: int, tipo: str, ref_id: int, cupo: bool = True) -> None:
    k = (tipo, ref_id)
    if marca_id in ocup["por_rep"].get(k, []):
        ocup["por_rep"][k].remove(marca_id)
    m = catalogo().get(marca_id)
    if m:
        ocup["rubros"].get(k, set()).discard(m["rubro"])
    if cupo:
        ocup["por_marca"][marca_id] = max(0, ocup["por_marca"].get(marca_id, 0) - 1)


# --- Red social: publicaciones del universo ---------------------------------------------------------
def _ancla(ciclo: int, seq: Optional[int] = None) -> dict:
    """Fecha y hora del partido de la ronda (o del que cerró el ciclo): las publicaciones aparecen justo después de él en la red."""
    clave = seq if seq is not None else ciclo * C.PARTIDOS_POR_CICLO
    if clave not in _cache_anclas:
        reg = db["corp_registro_partidos"].find_one({"seq": {"$lte": clave}}, {"juego_id": 1}, sort=[("seq", -1)])
        j = db["juegos"].find_one({"_id": ObjectId(reg["juego_id"])}, {"fecha": 1, "hora": 1}) if reg and ObjectId.is_valid(reg["juego_id"]) else None
        _cache_anclas[clave] = {"juego_id": reg["juego_id"] if reg else None, "fecha": (j or {}).get("fecha"), "hora": (j or {}).get("hora")}
    return _cache_anclas[clave]


def _publicar(uid, tipo: str, marca: dict, ciclo: int, texto: str, refs: list, clave: str, sigla: Optional[str] = None,
              ancla: Optional[dict] = None, orden: int = 0) -> None:
    usuario = getattr(_hilo, "sigla_usuario", None)
    if tipo in ("FIRMA", "RENOVACION", "DESPEDIDA") and usuario and sigla and sigla != usuario \
            and R.semilla(uid, "post", clave).random() >= C.MARCA_PROB_POST_IA:
        return   # la red no se llena con cada movimiento de la IA
    if not ancla and getattr(_hilo, "ancla_seq", None) is not None:
        if getattr(_hilo, "ancla", None) is None:
            _hilo.ancla = _ancla(ciclo, _hilo.ancla_seq)
        ancla = _hilo.ancla
    ancla = ancla or _ancla(ciclo)
    _ins("corp_feed", {"_id": f"{uid}:{clave}", "universo_id": uid, "tipo": tipo, "marca_id": marca["id"], "ciclo": ciclo,
                       "juego_id": ancla.get("juego_id"), "fecha": ancla.get("fecha"), "hora": ancla.get("hora"),
                       "orden": orden, "texto": texto, "refs": refs, "sigla": sigla, "creado_en": datetime.utcnow()})


def _ref(tipo: str, ref_id: int) -> dict:
    return {"tipo": tipo, "ref_id": ref_id, "nombre": _nombre(tipo, ref_id)}


# --- Cobros ------------------------------------------------------------------------------------------
def _cobrar(estado, corp: dict, contrato: Optional[dict], pat: dict, monto: int, ciclo: int, detalle: str) -> dict:
    """Ingreso de una marca. Del corporativo del usuario, el 5% es la comisión del CEO: se calcula sobre el total del
    ciclo (`ciclo_actual.marcas_bruto`) y se descuenta y paga con el sueldo en carrera.pagar_ceo."""
    usuario = corp.get("es_del_usuario")
    com = round(monto * C.MARCA_COMISION_CEO, 2) if usuario else 0
    corp["capital"] += monto
    corp["ciclo_actual"]["extra"] += monto
    if usuario:
        corp["ciclo_actual"]["marcas_bruto"] = corp["ciclo_actual"].get("marcas_bruto", 0) + monto
    if contrato:
        contrato["renta_total"] = contrato.get("renta_total", 0) + monto - com
        estado.tocar(contrato)
    estado.mover(corp["sigla"], ciclo, "PATROCINIO_MARCA", monto, detalle + (" (5% es tu comisión, con el sueldo)" if usuario else ""))
    return {"cobrado": monto, "comision": com}


# --- Rondas (cada MARCA_PARTIDOS_RONDA partidos, dentro de poner_al_dia) y cierre de ciclo -----------------------
RONDAS_POR_CICLO = C.PARTIDOS_POR_CICLO // C.MARCA_PARTIDOS_RONDA


def ronda_de_seq(seq: int) -> int:
    return seq // C.MARCA_PARTIDOS_RONDA


def cerrar_ciclo_marcas(estado, ciclo: int) -> None:
    """Cierre de ciclo: la última ronda del ciclo + vencimientos/renovaciones y los riesgos de fondo (llamado desde
    corporativo_acciones_service.cerrar_ciclo_acciones, antes de limpiar eventos_ciclo)."""
    ronda_marcas(estado, ciclo, ciclo * C.PARTIDOS_POR_CICLO, cierre=True)


def ronda_marcas(estado, ciclo: int, seq: int, cierre: bool = False) -> None:
    """
    Una ronda de marcas: pagan 1/RONDAS_POR_CICLO del monto por ciclo, evalúan el riesgo con lo que pasó en la ronda
    (roja, goleada; en el cierre además eliminación, ciclos sin jugar, mala racha y descontento), responden las
    promociones y resuelven los rumores de rondas anteriores, vencen las ofertas y se acercan las que tienen cupo.
    """
    cat = catalogo()
    if not cat:
        return
    uid = estado.uid
    _hilo.sigla_usuario = next((s for s, c in estado.corps.items() if c.get("es_del_usuario")), "-")
    iniciar_lote()
    _hilo.espejo = espejo(estado)
    _hilo.ancla, _hilo.ancla_seq = None, seq
    try:
        ctx = getattr(estado, "_ctx_marcas", None)
        if not ctx or ctx.get("_ciclo") != ciclo:   # el contexto de encaje se arma una vez por ciclo
            ctx = estado._ctx_marcas = {**_ctx_encaje(), "_ciclo": ciclo}
        ocup = _ocupacion(uid, _hilo.espejo)
        contratos = {(c["tipo"], c["ref_id"]): c for c in estado.contratos if c["activo"]}
        ronda = ronda_de_seq(seq)
        _procesar_activos(estado, ciclo, seq, cat, ctx, ocup, contratos, cierre)
        _procesar_promociones(estado, ciclo, seq, cat, ctx, ocup, contratos)
        _vencer_ofertas(estado, ciclo, seq, ocup, cierre)
        _resolver_rumores(estado, ciclo, seq, cat, ctx, ocup, contratos)
        _acercamientos(estado, ciclo, ronda, cat, ctx, ocup, contratos)
        for c in contratos.values():   # los hechos de la ronda ya se usaron: no cuentan dos veces
            if c.get("eventos_marcas"):
                c["eventos_marcas"] = {}
                estado.tocar(c)
    finally:
        if cierre:   # las escrituras se agrupan hasta el cierre (o el final del poner_al_dia): las lecturas van al espejo
            vaciar_lote()
        _hilo.ancla, _hilo.ancla_seq, _hilo.espejo = None, None, None


def _eventos(c: dict, ctx: dict, cierre: bool) -> dict:
    """Lo que preocupa a la marca: los hechos de la ronda (roja, goleada) y, en el cierre del ciclo, además la
    eliminación, los ciclos sin jugar, la mala racha y el descontento (así una situación de fondo no se cuenta 5 veces)."""
    ev = dict(c.get("eventos_marcas") or {})
    if not cierre:
        return ev
    if (c.get("eventos_ciclo") or {}).get("eliminada"):
        ev["eliminada"] = True
    pais = c["ref_id"] if c["tipo"] == "seleccion" else valores()["info_jugadores"].get(c["ref_id"], {}).get("pais_id")
    forma = ctx["forma"].get(pais)
    ev["sin_jugar"] = (c.get("ciclos_sin_jugar") or 0) >= 2
    ev["mala_forma"] = forma is not None and forma <= 0.25
    ev["descontento"] = (c.get("satisfaccion") or 100) < 35
    return ev


def _vigente_desde(p: dict) -> int:
    """seq desde el que cobra (los viejos guardaban solo el ciclo)."""
    return p["desde_seq"] if p.get("desde_seq") is not None else (p.get("desde_ciclo", 0) - 1) * C.PARTIDOS_POR_CICLO + 1


def _procesar_activos(estado, ciclo, seq, cat, ctx, ocup, contratos, cierre) -> None:
    uid = estado.uid
    for p in _vigentes("corp_patrocinios", "ACTIVO"):
        if _vigente_desde(p) > seq:
            continue
        marca = cat.get(p["marca_id"])
        c = contratos.get((p["tipo"], p["ref_id"]))
        corp = estado.corps.get(p["sigla"])
        if not marca or not corp:
            continue
        nombre = _nombre(p["tipo"], p["ref_id"])
        if not c or c["sigla"] != p["sigla"]:
            _upd("corp_patrocinios", p["_id"], {"$set": {"estado": "TERMINADO", "motivo": "Terminó la representación"}})
            _liberar(ocup, p["marca_id"], p["tipo"], p["ref_id"])
            continue
        ev = _eventos(c, ctx, cierre)
        riesgo = R.riesgo_marca(ev, marca.get("fidelidad", 0.5))
        es_usuario = corp.get("es_del_usuario")
        en_aviso = p.get("aviso_seq") or p.get("aviso_ciclo")
        if riesgo >= C.MARCA_RIESGO_CORTE or (en_aviso and riesgo >= C.MARCA_RIESGO_AVISO):
            motivo = _motivo_riesgo(ev)
            _upd("corp_patrocinios", p["_id"], {"$set": {"estado": "CORTADO", "riesgo": riesgo, "fin_ciclo": ciclo, "fin_seq": seq,
                                                         "motivo": f"La marca cortó por {motivo}"}})
            _liberar(ocup, p["marca_id"], p["tipo"], p["ref_id"])
            _publicar(uid, "DESPEDIDA", marca, ciclo, T.texto_despedida(marca, nombre, _pais_nombre(p["tipo"], p["ref_id"]), p["_id"]),
                      [_ref(p["tipo"], p["ref_id"])], f"adios:{p['_id']}", p["sigla"], orden=3)
            if es_usuario:
                U.avisar(uid, ciclo, "MARCA", f"{marca['nombre']} cortó el patrocinio de {nombre}",
                         f"Por {motivo}, la marca decidió no seguir. Te quedas con lo ya cobrado ({p.get('cobrado', 0):,}).",
                         "bi-x-octagon-fill", clave=f"marca-corte:{p['_id']}")
            continue
        pago = max(1, int(round(p["pago_ciclo"] / RONDAS_POR_CICLO)))
        en_tv = (c.get("tv_bono_hasta_seq") or 0) >= seq   # apareció hace poco como invitado en TV (corporativo_tv_service)
        if en_tv:
            pago = int(round(pago * C.TV_INVITADO_BONO_MARCAS))
        cobro = _cobrar(estado, corp, c, p, pago, ciclo, f"{marca['nombre']}: patrocinio de {nombre}" + (" (+ por su aparición en TV)" if en_tv else ""))
        cambios = {"$inc": {"pagos": 1, "cobrado": cobro["cobrado"], "comision": cobro["comision"]}, "$set": {}}
        if ev or cierre:   # sin hechos en la ronda, el semáforo queda como estaba
            aviso = seq if riesgo >= C.MARCA_RIESGO_AVISO else None
            cambios["$set"].update(riesgo=riesgo, aviso_seq=aviso, aviso_ciclo=ciclo if aviso else None)
            if aviso and not en_aviso and es_usuario:
                U.avisar(uid, ciclo, "MARCA", f"{marca['nombre']} está revisando el patrocinio de {nombre}",
                         f"Le preocupa {_motivo_riesgo(ev)}. Si vuelve a pasar algo así, corta. Que juegue y rinda, una gira o "
                         "una campaña de marketing ayudan.", "bi-exclamation-triangle-fill", clave=f"marca-aviso:{p['_id']}:{seq}")
        if cierre and ciclo >= p["hasta_ciclo"]:
            rng = R.semilla(uid, "marca-renueva", p["_id"], ciclo)
            if riesgo < C.MARCA_RIESGO_AVISO and rng.random() < C.MARCA_PROB_RENUEVA:
                extra = rng.randint(*C.MARCA_CICLOS)
                cambios["$set"].update(hasta_ciclo=p["hasta_ciclo"] + extra, renovaciones=p.get("renovaciones", 0) + 1)
                _publicar(uid, "RENOVACION", marca, ciclo, T.texto_renovacion(marca, nombre, _pais_nombre(p["tipo"], p["ref_id"]), extra,
                                                                               f"{p['_id']}:{ciclo}"),
                          [_ref(p["tipo"], p["ref_id"])], f"renov:{p['_id']}:{ciclo}", p["sigla"], orden=2)
                if es_usuario:
                    U.avisar(uid, ciclo, "MARCA", f"{marca['nombre']} renovó con {nombre}",
                             f"Quedó conforme y extiende el patrocinio {extra} ciclos más ({p['pago_ciclo']:,} por ciclo).", "bi-arrow-repeat",
                             clave=f"marca-renov:{p['_id']}:{ciclo}")
            else:
                cambios["$set"].update(estado="TERMINADO", motivo="Cumplido", fin_ciclo=ciclo, fin_seq=seq)
                _liberar(ocup, p["marca_id"], p["tipo"], p["ref_id"])
                if rng.random() < 0.5:
                    _publicar(uid, "DESPEDIDA", marca, ciclo, T.texto_despedida(marca, nombre, _pais_nombre(p["tipo"], p["ref_id"]), p["_id"]),
                              [_ref(p["tipo"], p["ref_id"])], f"adios:{p['_id']}", p["sigla"], orden=3)
        if not cambios["$set"]:
            del cambios["$set"]
        _upd("corp_patrocinios", p["_id"], cambios)


def _motivo_riesgo(ev: dict) -> str:
    textos = {"eliminada": "la eliminación de su selección", "roja": "una expulsión", "goleada": "una goleada en contra",
              "sin_jugar": "que casi no juega", "mala_forma": "la mala racha de su selección", "descontento": "su descontento"}
    activos = [textos[k] for k in ("eliminada", "roja", "goleada", "sin_jugar", "mala_forma", "descontento") if ev.get(k)]
    return " y ".join(activos[:2]) or "sus resultados"


def _activar(estado, ciclo: int, marca: dict, c: dict, corp: dict, encaje: int, origen: str, ocup: dict, pat_id: Optional[str] = None,
             seq: Optional[int] = None) -> dict:
    """Firma un patrocinio en el cierre (IA, promoción aceptada): cobra la firma y publica la noticia."""
    uid = estado.uid
    rng = R.semilla(uid, "marca-firma", marca["id"], c["tipo"], c["ref_id"], ciclo)
    montos = R.monto_marca(c.get("valor_actual") or _valor(c["tipo"], c["ref_id"]), marca.get("nivel", 2), encaje, corp.get("reputacion", 50))
    ciclos = rng.randint(*C.MARCA_CICLOS)
    seq = seq if seq is not None else ciclo * C.PARTIDOS_POR_CICLO
    doc = {"universo_id": uid, "sigla": c["sigla"], "contrato_id": str(c["_id"]), "tipo": c["tipo"], "ref_id": c["ref_id"],
           "marca_id": marca["id"], "rubro": marca["rubro"], "encaje": encaje, **montos, "desde_ciclo": ciclo,
           "desde_seq": seq + 1, "hasta_ciclo": ciclo + ciclos, "pagos": 0, "cobrado": 0, "comision": 0, "riesgo": 0, "aviso_ciclo": None,
           "origen": origen, "estado": "ACTIVO", "motivo": None, "ciclo": ciclo, "creado_en": datetime.utcnow()}
    nombre = _nombre(c["tipo"], c["ref_id"])
    cobro = _cobrar(estado, corp, c, doc, montos["firma"], ciclo, f"{marca['nombre']}: firma del patrocinio de {nombre}")
    doc.update(cobrado=cobro["cobrado"], comision=cobro["comision"])
    if pat_id:
        _upd("corp_patrocinios", pat_id, {"$set": doc})
    else:
        pat_id = f"{uid}:{marca['id']}:{c['tipo']}:{c['ref_id']}:r{ronda_de_seq(seq)}"
        _ins("corp_patrocinios", {"_id": pat_id, **doc})
    _ocupar(ocup, marca, c["tipo"], c["ref_id"])
    _publicar(uid, "FIRMA", marca, ciclo, T.texto_firma(marca, c["tipo"], nombre, _pais_nombre(c["tipo"], c["ref_id"]), ciclos, pat_id),
              [_ref(c["tipo"], c["ref_id"])], f"firma:{pat_id}", c["sigla"], orden=1)
    return doc


def _valor(tipo: str, ref_id: int) -> int:
    v = valores()
    return int((v["selecciones"] if tipo == "seleccion" else v["jugadores"]).get(ref_id, 0))


def _procesar_promociones(estado, ciclo, seq, cat, ctx, ocup, contratos) -> None:
    uid = estado.uid
    universo = None
    for p in _vigentes("corp_patrocinios", "PROMOCION"):
        if p.get("seq") is not None and p["seq"] >= seq:
            continue   # se hizo después de esta ronda: responde en la siguiente
        if p.get("seq") is None and p.get("ciclo", 0) > ciclo:
            continue
        universo = universo or U.obtener_universo(uid) or {}
        marca = cat.get(p["marca_id"])
        c = contratos.get((p["tipo"], p["ref_id"]))
        corp = estado.corps.get(p["sigla"])
        # la promoción ocupaba lugar en el representado (no cupo de la marca): se libera y se evalúa de nuevo
        _liberar(ocup, p["marca_id"], p["tipo"], p["ref_id"], cupo=False)
        nombre = _nombre(p["tipo"], p["ref_id"])
        if not marca or not c or not corp or c["sigla"] != p["sigla"]:
            _upd("corp_patrocinios", p["_id"], {"$set": {"estado": "DESCARTADA", "motivo": "El representado ya no está en tu cartera"}})
            continue
        traba = puede_patrocinar(marca, p["tipo"], p["ref_id"], ocup)
        encaje = R.encaje_marca(marca, representado(p["tipo"], p["ref_id"], ctx))
        prob = R.prob_promocion(encaje, corp.get("reputacion", 50), universo.get("fama", 50))
        acepta = not traba and encaje >= C.MARCA_ENCAJE_MINIMO and R.semilla(uid, "promo", p["_id"]).random() < prob
        if acepta:
            _activar(estado, ciclo, marca, c, corp, encaje, "PROMOCION", ocup, pat_id=p["_id"], seq=seq)
            U.avisar(uid, ciclo, "MARCA", f"¡{marca['nombre']} aceptó! Patrocinará a {nombre}",
                     f"Tu promoción funcionó: cobras la firma ahora y el patrocinio cada {C.MARCA_PARTIDOS_RONDA} partidos.", "bi-stars",
                     clave=f"promo-ok:{p['_id']}")
            U.dar_xp(uid, "CORP_PATROCINIO", p["_id"])
        else:
            motivo = traba or ("no encaja con lo que busca" if encaje < C.MARCA_ENCAJE_MINIMO else "eligió esperar")
            _upd("corp_patrocinios", p["_id"], {"$set": {"estado": "DESCARTADA", "motivo": motivo.capitalize()}})
            U.avisar(uid, ciclo, "MARCA", f"{marca['nombre'] if marca else 'La marca'} no tomó la propuesta por {nombre}",
                     f"Motivo: {motivo}. Puedes intentar con otra marca.", "bi-x-circle", clave=f"promo-no:{p['_id']}")


def _vencer_ofertas(estado, ciclo, seq, ocup, cierre) -> None:
    for p in _vigentes("corp_patrocinios", "OFERTA"):
        vencida = p["vence_seq"] <= seq if p.get("vence_seq") is not None else (cierre and p.get("vence_ciclo", 0) <= ciclo)
        if not vencida:
            continue
        _upd("corp_patrocinios", p["_id"], {"$set": {"estado": "VENCIDA", "motivo": "No respondiste a tiempo"}})
        _liberar(ocup, p["marca_id"], p["tipo"], p["ref_id"])


def _ofrecer(estado, ciclo: int, marca: dict, c: dict, encaje: int, ocup: dict, seq: int) -> None:
    """Oferta de una marca a un representado del USUARIO: la acepta o rechaza en los próximos MARCA_OFERTA_PARTIDOS partidos."""
    uid = estado.uid
    corp = estado.corps[c["sigla"]]
    montos = R.monto_marca(c.get("valor_actual") or _valor(c["tipo"], c["ref_id"]), marca.get("nivel", 2), encaje, corp.get("reputacion", 50))
    ciclos = R.semilla(uid, "marca-oferta", marca["id"], c["ref_id"], ciclo).randint(*C.MARCA_CICLOS)
    pat_id = f"{uid}:{marca['id']}:{c['tipo']}:{c['ref_id']}:r{ronda_de_seq(seq)}"
    if True:
        _ins("corp_patrocinios", {"_id": pat_id, "universo_id": uid, "sigla": c["sigla"], "contrato_id": str(c["_id"]),
                                           "tipo": c["tipo"], "ref_id": c["ref_id"], "marca_id": marca["id"], "rubro": marca["rubro"],
                                           "encaje": encaje, **montos, "ciclos": ciclos, "estado": "OFERTA", "origen": "MARCA",
                                           "ciclo": ciclo, "seq": seq, "vence_seq": seq + C.MARCA_OFERTA_PARTIDOS, "creado_en": datetime.utcnow()})
    _ocupar(ocup, marca, c["tipo"], c["ref_id"])
    nombre = _nombre(c["tipo"], c["ref_id"])
    U.avisar(uid, ciclo, "MARCA", f"{marca['nombre']} quiere patrocinar a {nombre}",
             f"Ofrece {montos['firma']:,} de firma y {montos['pago_ciclo']:,} por ciclo durante {ciclos} ciclos. Respóndele en los "
             f"próximos {C.MARCA_OFERTA_PARTIDOS} partidos en Marcas y patrocinios.", "bi-badge-ad-fill", clave=f"marca-oferta:{pat_id}")


def _candidatos(marca: dict, ctx: dict, ocup: dict, contratos: dict, reps: dict) -> List[tuple]:
    salida = []
    for k, c in contratos.items():
        if puede_patrocinar(marca, k[0], k[1], ocup):
            continue
        rep = reps.get(k)
        if rep is None:
            rep = reps[k] = representado(k[0], k[1], ctx)
        e = R.encaje_marca(marca, rep)
        if e and (c.get("tv_bono_hasta_seq") or 0) >= (getattr(_hilo, "ancla_seq", None) or 0):   # salió en TV: más interés
            e = min(100, e + C.TV_INVITADO_ENCAJE)
        if e >= C.MARCA_ENCAJE_MINIMO:
            salida.append((e, c))
    salida.sort(key=lambda x: -x[0])
    return salida


def _resolver_rumores(estado, ciclo, seq, cat, ctx, ocup, contratos) -> None:
    uid = estado.uid
    for r in _vigentes("corp_marcas_rumores", "ABIERTO"):
        if (r["seq"] >= seq) if r.get("seq") is not None else (r.get("ciclo", 0) >= ciclo):
            continue   # el rumor es de esta ronda: se resuelve en la siguiente
        marca = cat.get(r["marca_id"])
        _upd("corp_marcas_rumores", r["_id"], {"$set": {"estado": "RESUELTO"}})
        ocup["por_marca"][r["marca_id"]] = max(0, ocup["por_marca"].get(r["marca_id"], 0) - 1)
        if not marca:
            continue
        rng = R.semilla(uid, "rumor-resuelve", r["_id"])
        vivos = [(x["encaje"], contratos.get((x["tipo"], x["ref_id"]))) for x in r["candidatos"]]
        vivos = [(e, c) for e, c in vivos if c and not puede_patrocinar(marca, c["tipo"], c["ref_id"], ocup)]
        if not vivos:
            continue
        e, c = rng.choices(vivos, weights=[max(1, x[0] - 30) for x in vivos])[0]
        _decidir(estado, ciclo, marca, c, e, ocup, rng, seq)


def _decidir(estado, ciclo, marca, c, encaje, ocup, rng, seq) -> None:
    corp = estado.corps[c["sigla"]]
    if corp.get("es_del_usuario"):
        _ofrecer(estado, ciclo, marca, c, encaje, ocup, seq)
    elif rng.random() < C.MARCA_IA_ACEPTA:
        _activar(estado, ciclo, marca, c, corp, encaje, "MARCA", ocup, seq=seq)


def _acercamientos(estado, ciclo, ronda, cat, ctx, ocup, contratos) -> None:
    uid = estado.uid
    seq = ronda * C.MARCA_PARTIDOS_RONDA
    rng = R.semilla(uid, "marcas-acercan", ronda)
    prob = C.MARCA_PROB_ACERCARSE / RONDAS_POR_CICLO
    ids = sorted(cat)
    rng.shuffle(ids)
    reps: dict = {}
    for mid in ids:
        marca = cat[mid]
        if ocup["por_marca"].get(mid, 0) >= C.MARCA_CUPOS_NIVEL.get(marca.get("nivel", 2), 1):
            continue
        if rng.random() >= prob:
            continue
        cands = _candidatos(marca, ctx, ocup, contratos, reps)[:8]
        if not cands:
            continue
        if len(cands) >= 3 and rng.random() < C.MARCA_PROB_RUMOR:
            elegidos = rng.sample(cands, min(len(cands), rng.choice([3, 3, 4])))
            rid = f"{uid}:{mid}:r{ronda}"
            if True:
                _ins("corp_marcas_rumores", {"_id": rid, "universo_id": uid, "marca_id": mid, "ciclo": ciclo, "seq": seq, "estado": "ABIERTO",
                                                      "candidatos": [{"tipo": c["tipo"], "ref_id": c["ref_id"], "sigla": c["sigla"],
                                                                      "contrato_id": str(c["_id"]), "encaje": e} for e, c in elegidos]})
            ocup["por_marca"][mid] = ocup["por_marca"].get(mid, 0) + 1
            _publicar(uid, "RUMOR", marca, ciclo, T.texto_rumor(marca, [_nombre(c["tipo"], c["ref_id"]) for _, c in elegidos], rid),
                      [_ref(c["tipo"], c["ref_id"]) for _, c in elegidos], f"rumor:{rid}", orden=4)
        else:
            e, c = rng.choices(cands, weights=[max(1, x[0] - 30) for x in cands])[0]
            _decidir(estado, ciclo, marca, c, e, ocup, rng, seq)


# --- Partido: las marcas responden en el hilo del partido de sus patrocinados -------------------------
def reacciones_partido(estado, aporte: dict, ciclo: int, juego_id: str) -> None:
    """Llamado por cada partido en poner_al_dia: la marca comenta el resultado de su patrocinado (o lo que hizo él)."""
    try:
        iniciar_lote()
        _hilo.sigla_usuario = next((s for s, c in estado.corps.items() if c.get("es_del_usuario")), "-")
        pats = [p for p in espejo(estado)["corp_patrocinios"].values() if p.get("estado") == "ACTIVO"]
        if not pats:
            return
        v = valores()
        sel, jug = aporte.get("selecciones") or {}, aporte.get("jugadores") or {}
        candidatos = [p for p in pats if (p["tipo"] == "seleccion" and p["ref_id"] in sel)
                      or (p["tipo"] == "jugador" and v["info_jugadores"].get(p["ref_id"], {}).get("pais_id") in sel)]
        if not candidatos:
            return
        rng = R.semilla(estado.uid, "reacciones", juego_id)
        rng.shuffle(candidatos)
        juego = None
        cat = catalogo()
        hechas = 0
        usadas: set = set()
        for p in candidatos:
            if hechas >= 3 or rng.random() >= C.MARCA_PROB_REACCION:
                continue
            marca = cat.get(p["marca_id"])
            pais = p["ref_id"] if p["tipo"] == "seleccion" else v["info_jugadores"].get(p["ref_id"], {}).get("pais_id")
            situ = T.situacion_reaccion(p["tipo"], sel.get(pais), (aporte.get("diferencia") or {}).get(pais, 0), jug.get(p["ref_id"]))
            if not marca or not situ:
                continue
            if juego is None:
                juego = db["juegos"].find_one({"_id": ObjectId(juego_id)}, {"fecha": 1, "hora": 1, "equipo_local": 1, "equipo_visitante": 1,
                                                                             "resultado.goles_local": 1, "resultado.goles_visitante": 1}) or {}
            res = juego.get("resultado") or {}
            marcador = f"{(juego.get('equipo_local') or {}).get('nombre', '')} {res.get('goles_local', 0)}-{res.get('goles_visitante', 0)} " \
                       f"{(juego.get('equipo_visitante') or {}).get('nombre', '')}"
            texto = T.texto_reaccion(marca, situ, _nombre(p["tipo"], p["ref_id"]), v["info_paises"].get(pais, {}).get("nombre", ""),
                                     marcador, f"{p['_id']}:{juego_id}", usadas)
            _publicar(estado.uid, "REACCION", marca, ciclo, texto, [_ref(p["tipo"], p["ref_id"])], f"reac:{p['_id']}:{juego_id}",
                      p["sigla"], ancla={"juego_id": juego_id, "fecha": juego.get("fecha"), "hora": juego.get("hora")}, orden=0)
            hechas += 1
    except Exception as e:   # nunca frena la puesta al día del universo
        print(f"[marcas] reacciones del partido {juego_id}: {e}")


# --- Acciones del CEO -------------------------------------------------------------------------------
def _contrato_propio(user_id, contrato_id: str):
    from services.corporativo_fichajes_service import _cargo
    universo, sigla, corp = _cargo(user_id)
    if not ObjectId.is_valid(contrato_id):
        raise ValueError("Contrato inválido")
    c = db["corp_contratos"].find_one({"_id": ObjectId(contrato_id), "universo_id": user_id, "sigla": sigla, "activo": True})
    if not c:
        raise ValueError("Ese representado no es de tu corporativo")
    return universo, sigla, corp, c, U.ciclo_en_curso(universo)


def _ronda_usuario(user_id) -> tuple:
    """(seq del universo, ronda en curso, partidos que faltan para la próxima ronda)."""
    seq = (U.obtener_universo(user_id) or {}).get("cursor_seq") or U.seq_actual()
    faltan = C.MARCA_PARTIDOS_RONDA - (seq % C.MARCA_PARTIDOS_RONDA)
    return seq, ronda_de_seq(seq), faltan


def _promos_ronda(user_id, ronda: int) -> int:
    return db["corp_patrocinios"].count_documents({"universo_id": user_id, "origen": "PROMOCION", "ronda": ronda})


def promociones_disponibles(user_id) -> dict:
    """Cupo de «Promover» de la ronda en curso: {restantes, usadas, maximo, faltan (partidos para la próxima ronda)}."""
    _, ronda, faltan = _ronda_usuario(user_id)
    usadas = _promos_ronda(user_id, ronda)
    return {"restantes": max(0, C.MARCA_PROMOCIONES_POR_RONDA - usadas), "usadas": usadas,
            "maximo": C.MARCA_PROMOCIONES_POR_RONDA, "faltan": faltan}


def interesadas(user_id, contrato_id: str, ctx: Optional[dict] = None) -> dict:
    """Marcas que podrían patrocinar a este representado, por encaje, con la probabilidad de aceptar una promoción."""
    universo, sigla, corp, c, ciclo = _contrato_propio(user_id, contrato_id)
    ctx = ctx or _ctx_encaje()
    ocup = _ocupacion(user_id)
    rep = representado(c["tipo"], c["ref_id"], ctx)
    salida = []
    for m in catalogo().values():
        e = R.encaje_marca(m, rep)
        if e < C.MARCA_ENCAJE_MINIMO - 10:
            continue
        traba = puede_patrocinar(m, c["tipo"], c["ref_id"], ocup)
        montos = R.monto_marca(rep["valor"], m.get("nivel", 2), e, corp.get("reputacion", 50))
        salida.append({**marca_vista(m), "encaje": e, **montos, "traba": traba if e >= C.MARCA_ENCAJE_MINIMO else "Todavía no encaja con lo que busca",
                       "prob": R.prob_promocion(e, corp.get("reputacion", 50), universo.get("fama", 50))})
    salida.sort(key=lambda x: (x["traba"] is not None, -x["encaje"]))
    _, ronda, faltan = _ronda_usuario(user_id)
    usadas = _promos_ronda(user_id, ronda)
    actuales = [marca_vista(catalogo()[p["marca_id"]]) for p in db["corp_patrocinios"].find(
        {"universo_id": user_id, "tipo": c["tipo"], "ref_id": c["ref_id"], "estado": "ACTIVO"}) if p["marca_id"] in catalogo()]
    return {"nombre": _nombre(c["tipo"], c["ref_id"]), "tipo": c["tipo"], "marcas": salida[:12], "actuales": actuales,
            "promociones_restantes": max(0, C.MARCA_PROMOCIONES_POR_RONDA - usadas), "max_marcas": C.MARCAS_MAX_POR_REPRESENTADO,
            "comision": int(C.MARCA_COMISION_CEO * 100), "responde_en": faltan}


def promover(user_id, contrato_id: str, marca_id: int) -> dict:
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        universo, sigla, corp, c, ciclo = _contrato_propio(user_id, contrato_id)
        marca = catalogo().get(int(marca_id))
        if not marca:
            raise ValueError("Marca inexistente")
        seq, ronda, faltan = _ronda_usuario(user_id)
        if _promos_ronda(user_id, ronda) >= C.MARCA_PROMOCIONES_POR_RONDA:
            raise ValueError(f"Ya hiciste {C.MARCA_PROMOCIONES_POR_RONDA} promociones en esta ronda: en {faltan} partido{'s' if faltan != 1 else ''} puedes volver a promover")
        ocup = _ocupacion(user_id)
        traba = puede_patrocinar(marca, c["tipo"], c["ref_id"], ocup)
        if traba:
            raise ValueError(traba)
        pendientes = db["corp_patrocinios"].count_documents({"universo_id": user_id, "marca_id": marca["id"], "estado": "PROMOCION"})
        if ocup["por_marca"].get(marca["id"], 0) + pendientes >= C.MARCA_CUPOS_NIVEL.get(marca.get("nivel", 2), 1):
            raise ValueError(f"{marca['nombre']} ya está evaluando otra propuesta tuya y no tiene más cupo: prueba con otra marca")
        e = R.encaje_marca(marca, representado(c["tipo"], c["ref_id"], _ctx_encaje()))
        if e < C.MARCA_ENCAJE_MINIMO:
            raise ValueError("A esta marca todavía no le interesa: busca otra que encaje mejor")
        pat_id = f"{user_id}:promo:{marca['id']}:{c['tipo']}:{c['ref_id']}:r{ronda}"
        try:
            db["corp_patrocinios"].insert_one({"_id": pat_id, "universo_id": user_id, "sigla": sigla, "contrato_id": str(c["_id"]),
                                               "tipo": c["tipo"], "ref_id": c["ref_id"], "marca_id": marca["id"], "rubro": marca["rubro"],
                                               "encaje": e, "estado": "PROMOCION", "origen": "PROMOCION", "ciclo": ciclo, "seq": seq, "ronda": ronda,
                                               "creado_en": datetime.utcnow()})
        except DuplicateKeyError:
            raise ValueError("Ya promoviste a este representado con esa marca en esta ronda")
    return {"ok": True, "mensaje": f"Le presentaste {_nombre(c['tipo'], c['ref_id'])} a {marca['nombre']}: responde en {faltan} partido{'s' if faltan != 1 else ''}."}


def responder_oferta(user_id, pat_id: str, aceptar: bool) -> dict:
    U.poner_al_dia(user_id)
    with U.candado(user_id):
        p = db["corp_patrocinios"].find_one({"_id": pat_id, "universo_id": user_id, "estado": "OFERTA"})
        if not p:
            raise ValueError("Esa oferta ya no está disponible")
        marca = catalogo().get(p["marca_id"])
        universo = U.obtener_universo(user_id)
        ciclo = U.ciclo_en_curso(universo)
        nombre = _nombre(p["tipo"], p["ref_id"])
        seq = universo.get("cursor_seq") or U.seq_actual()
        if p.get("vence_seq") is not None and seq >= p["vence_seq"]:
            db["corp_patrocinios"].update_one({"_id": pat_id}, {"$set": {"estado": "VENCIDA", "motivo": "No respondiste a tiempo"}})
            raise ValueError("La oferta ya venció")
        if not aceptar:
            db["corp_patrocinios"].update_one({"_id": pat_id}, {"$set": {"estado": "RECHAZADA", "motivo": "La rechazaste"}})
            return {"ok": True, "mensaje": f"Rechazaste a {marca['nombre']}."}
        c = db["corp_contratos"].find_one({"_id": ObjectId(p["contrato_id"]), "activo": True, "sigla": p["sigla"]})
        if not c:
            db["corp_patrocinios"].update_one({"_id": pat_id}, {"$set": {"estado": "DESCARTADA", "motivo": "Ya no lo representas"}})
            raise ValueError("Ya no representas a " + nombre)
        firma = p["firma"]
        com = int(round(firma * C.MARCA_COMISION_CEO))   # tu 5%: se descuenta y se paga con el sueldo del cierre (marcas_bruto)
        corp = db["corp_corporativos"].find_one_and_update(
            {"universo_id": user_id, "sigla": p["sigla"]},
            {"$inc": {"capital": firma, "ciclo_actual.extra": firma, "ciclo_actual.marcas_bruto": firma}})
        db["corp_contratos"].update_one({"_id": c["_id"]}, {"$inc": {"renta_total": firma - com}})
        desde = ciclo
        db["corp_patrocinios"].update_one({"_id": pat_id}, {"$set": {
            "estado": "ACTIVO", "desde_ciclo": desde, "desde_seq": seq + 1, "hasta_ciclo": desde + p.get("ciclos", 4) - 1, "pagos": 0, "cobrado": firma,
            "comision": com, "riesgo": 0, "aviso_ciclo": None, "aceptada_ciclo": ciclo}})
        db["corp_movimientos"].insert_one({"universo_id": user_id, "sigla": p["sigla"], "ciclo": ciclo, "tipo": "PATROCINIO_MARCA",
                                           "monto": firma, "detalle": f"{marca['nombre']}: firma del patrocinio de {nombre} (5% es tu comisión, con el sueldo)",
                                           "creado_en": datetime.utcnow()})
        reg = db["corp_registro_partidos"].find_one({}, {"juego_id": 1}, sort=[("seq", -1)])
        j = db["juegos"].find_one({"_id": ObjectId(reg["juego_id"])}, {"fecha": 1, "hora": 1}) if reg else {}
        _publicar(user_id, "FIRMA", marca, ciclo, T.texto_firma(marca, p["tipo"], nombre, _pais_nombre(p["tipo"], p["ref_id"]),
                                                                 p.get("ciclos", 4), pat_id),
                  [_ref(p["tipo"], p["ref_id"])], f"firma:{pat_id}", p["sigla"],
                  ancla={"juego_id": reg["juego_id"] if reg else None, "fecha": (j or {}).get("fecha"), "hora": (j or {}).get("hora")}, orden=1)
    U.dar_xp(user_id, "CORP_PATROCINIO", pat_id)
    return {"ok": True, "mensaje": f"¡Firmado! {marca['nombre']} patrocina a {nombre}: cobraste {firma:,} de firma (tu comisión de ~{com:,} llega con el sueldo).",
            "corp": bool(corp)}


# --- Para las vistas -------------------------------------------------------------------------------
def patrocinios_por_contrato(user_id, sigla: str) -> Dict[str, list]:
    """{contrato_id: [marca vista + pago, riesgo, aviso]} de los patrocinios activos del corporativo (cartera)."""
    cat = catalogo()
    salida: Dict[str, list] = {}
    for p in db["corp_patrocinios"].find({"universo_id": user_id, "sigla": sigla, "estado": "ACTIVO"}):
        if p["marca_id"] in cat:
            salida.setdefault(p["contrato_id"], []).append({**marca_vista(cat[p["marca_id"]]), "pago_ciclo": p["pago_ciclo"],
                                                            "riesgo": p.get("riesgo", 0), "aviso": bool(p.get("aviso_ciclo")),
                                                            "hasta_ciclo": p["hasta_ciclo"]})
    return salida


def patrocinadores_de(usuario: Optional[dict], tipo: str, ref_id: int) -> list:
    """Marcas que patrocinan a una selección o jugador en el universo del usuario (fichas de país y jugador)."""
    try:
        if not usuario:
            return []
        uid = str(usuario["_id"])
        cat = catalogo()
        return [{**marca_vista(cat[p["marca_id"]]), "sigla": p["sigla"], "pago_ciclo": p["pago_ciclo"]}
                for p in db["corp_patrocinios"].find({"universo_id": uid, "tipo": tipo, "ref_id": ref_id, "estado": "ACTIVO"})
                if p["marca_id"] in cat]
    except Exception as e:
        print(f"[marcas] patrocinadores de {tipo} {ref_id}: {e}")
        return []


def patrocinios_de_pais(usuario: Optional[dict], pais_id: int) -> dict:
    """
    Marcas de una selección y de cada jugador de su plantilla en el universo del usuario (vista de plantilla y ficha del
    país): {"seleccion": [marcas], "jugadores": {jugador_id: [marcas]}, "total": n}. Una sola consulta de patrocinios.
    """
    vacio = {"seleccion": [], "jugadores": {}, "total": 0}
    try:
        if not usuario or pais_id is None:
            return vacio
        uid, cat = str(usuario["_id"]), catalogo()
        pais_id = int(pais_id)
        ids = [j["id"] for j in db["jugadores"].find({"pais_id": pais_id}, {"id": 1})]
        salida = {"seleccion": [], "jugadores": {}, "total": 0}
        for p in db["corp_patrocinios"].find({"universo_id": uid, "estado": "ACTIVO", "$or": [
                {"tipo": "seleccion", "ref_id": pais_id}, {"tipo": "jugador", "ref_id": {"$in": ids}}]}):
            if p["marca_id"] not in cat:
                continue
            mk = {**marca_vista(cat[p["marca_id"]]), "sigla": p["sigla"], "pago_ciclo": p["pago_ciclo"]}
            if p["tipo"] == "seleccion":
                salida["seleccion"].append(mk)
            else:
                salida["jugadores"].setdefault(p["ref_id"], []).append(mk)
            salida["total"] += 1
        return salida
    except Exception as e:
        print(f"[marcas] patrocinios del país {pais_id}: {e}")
        return vacio


def _salud(p: dict) -> dict:
    r = p.get("riesgo", 0)
    if p.get("aviso_ciclo") or r >= C.MARCA_RIESGO_AVISO:
        return {"nivel": "rojo", "texto": "En riesgo: la marca está revisando el patrocinio"}
    if r >= C.MARCA_RIESGO_AVISO * 0.5:
        return {"nivel": "ambar", "texto": "Atento: algún resultado preocupó a la marca"}
    return {"nivel": "verde", "texto": "Contenta"}


def resumen(user_id, sigla: str) -> dict:
    """Para el inicio de Corporativos: ofertas pendientes, ingresos por ciclo, comisión y patrocinios en riesgo."""
    cat = catalogo()
    activos = list(db["corp_patrocinios"].find({"universo_id": user_id, "sigla": sigla, "estado": "ACTIVO"}))
    seq_u = (U.obtener_universo(user_id) or {}).get("cursor_seq")
    ofertas = [_fila(p, cat, seq_u) for p in db["corp_patrocinios"].find({"universo_id": user_id, "estado": "OFERTA"}).sort("ciclo", -1)]
    pago = sum(p["pago_ciclo"] for p in activos)
    return {"activos": len(activos), "pago_ciclo": pago, "comision_ciclo": int(round(pago * C.MARCA_COMISION_CEO)),
            "en_riesgo": sum(1 for p in activos if _salud(p)["nivel"] == "rojo"), "ofertas": [o for o in ofertas if o]}


def _fila(p: dict, cat: dict, seq_ref: Optional[int] = None) -> Optional[dict]:
    m = cat.get(p["marca_id"])
    if not m:
        return None
    v = valores()
    pais = p["ref_id"] if p["tipo"] == "seleccion" else v["info_jugadores"].get(p["ref_id"], {}).get("pais_id")
    vence_en = None
    if p.get("vence_seq") is not None:
        vence_en = max(0, p["vence_seq"] - (seq_ref if seq_ref is not None else U.seq_actual()))
    return {**p, "_id": str(p["_id"]), "vence_en": vence_en, "marca": marca_vista(m), "nombre": _nombre(p["tipo"], p["ref_id"]), "pais_id": pais,
            "bandera": v["info_paises"].get(pais, {}).get("bandera"), "salud": _salud(p)}


def vista_marcas(user_id) -> Optional[dict]:
    """Página «Marcas y patrocinios»: interesadas en tu cartera, tus patrocinios, catálogo e historial."""
    universo = U.obtener_universo(user_id)
    if not universo:
        return None
    U.poner_al_dia(user_id)
    universo = U.obtener_universo(user_id)
    cat = catalogo()
    sigla = (universo.get("cargo") or {}).get("sigla")
    ciclo = U.ciclo_en_curso(universo)
    ctx = _ctx_encaje()
    ocup = _ocupacion(user_id)
    # Interesadas: por cada marca con cupo, tus representados que encajan (top 3)
    interesadas_l = []
    if sigla and universo["estado"] == "EN_CARGO":
        contratos = U.contratos_activos(user_id, sigla)
        reps = {(c["tipo"], c["ref_id"]): representado(c["tipo"], c["ref_id"], ctx) for c in contratos}
        corp = db["corp_corporativos"].find_one({"universo_id": user_id, "sigla": sigla}, {"reputacion": 1}) or {}
        for m in cat.values():
            if ocup["por_marca"].get(m["id"], 0) >= C.MARCA_CUPOS_NIVEL.get(m.get("nivel", 2), 1):
                continue
            encajan = []
            for c in contratos:
                e = R.encaje_marca(m, reps[(c["tipo"], c["ref_id"])])
                if e >= C.MARCA_ENCAJE_MINIMO and not puede_patrocinar(m, c["tipo"], c["ref_id"], ocup):
                    v = valores()
                    pais = c["ref_id"] if c["tipo"] == "seleccion" else v["info_jugadores"].get(c["ref_id"], {}).get("pais_id")
                    encajan.append({"contrato_id": str(c["_id"]), "tipo": c["tipo"], "ref_id": c["ref_id"], "nombre": _nombre(c["tipo"], c["ref_id"]),
                                    "pais_id": pais, "bandera": v["info_paises"].get(pais, {}).get("bandera"), "encaje": e,
                                    "prob": R.prob_promocion(e, corp.get("reputacion", 50), universo.get("fama", 50)),
                                    **R.monto_marca(reps[(c["tipo"], c["ref_id"])]["valor"], m.get("nivel", 2), e, corp.get("reputacion", 50))})
            if encajan:
                encajan.sort(key=lambda x: -x["encaje"])
                interesadas_l.append({**marca_vista(m), "candidatos": encajan[:3], "mejor": encajan[0]["encaje"]})
        interesadas_l.sort(key=lambda x: -x["mejor"])
    seq_u = universo.get("cursor_seq")
    mios = [_fila(p, cat, seq_u) for p in db["corp_patrocinios"].find({"universo_id": user_id, "sigla": sigla, "estado": {"$in": ["ACTIVO", "OFERTA", "PROMOCION"]}})]
    mios = [x for x in mios if x]
    historial = [_fila(p, cat) for p in db["corp_patrocinios"].find(
        {"universo_id": user_id, "estado": {"$in": ["TERMINADO", "CORTADO", "RECHAZADA", "VENCIDA", "DESCARTADA"]}}).sort("ciclo", -1).limit(40)]
    # Catálogo con a quién patrocina cada marca en tu universo
    patrocinados: Dict[int, list] = {}
    for p in db["corp_patrocinios"].find({"universo_id": user_id, "estado": "ACTIVO"}, {"marca_id": 1, "tipo": 1, "ref_id": 1, "sigla": 1}):
        patrocinados.setdefault(p["marca_id"], []).append({"nombre": _nombre(p["tipo"], p["ref_id"]), "sigla": p["sigla"], "tipo": p["tipo"],
                                                           "ref_id": p["ref_id"]})
    from config.marcas import ALCANCES, CONFEDERACIONES, RUBROS
    catalogo_l = sorted(({**marca_vista(m), "patrocina": patrocinados.get(m["id"], []),
                          "cupos": C.MARCA_CUPOS_NIVEL.get(m.get("nivel", 2), 1), "usados": ocup["por_marca"].get(m["id"], 0)}
                         for m in cat.values()), key=lambda x: (-x["nivel"], x["nombre"]))
    _, ronda, faltan = _ronda_usuario(user_id)
    promos = _promos_ronda(user_id, ronda)
    return {"universo": universo, "sigla": sigla, "ciclo": ciclo, "interesadas": interesadas_l[:24], "mios": mios,
            "historial": [h for h in historial if h], "catalogo": catalogo_l, "rubros": RUBROS, "alcances": ALCANCES,
            "confederaciones": CONFEDERACIONES, "resumen": resumen(user_id, sigla) if sigla else None,
            "promociones_restantes": max(0, C.MARCA_PROMOCIONES_POR_RONDA - promos), "max_marcas": C.MARCAS_MAX_POR_REPRESENTADO,
            "ronda_en": faltan, "partidos_ronda": C.MARCA_PARTIDOS_RONDA, "rondas_ciclo": RONDAS_POR_CICLO,
            "comision": int(C.MARCA_COMISION_CEO * 100), "en_cargo": universo["estado"] == "EN_CARGO"}
