"""
Asistente virtual "El Profe": cobra con el saldo un escaneo de todo lo del usuario y devuelve consejos accionables
(reglas en config/asistente.py, lógica pura en services/asistente_reglas.py, analizadores en
services/asistente_analizadores.py). Las consultas quedan en 'asistente_consultas' (permanente: restart_mundial no la
toca) y alimentan el historial de /asistente y el feed de Mi Cuenta.

Reglas de cobro:
- El primer Vistazo del día es gratis; el resto se cobra con un $inc condicional ($gte) — sin saldo no hay consulta.
- Un informe sigue vigente hasta que se juega otro partido: volver a consultar el mismo nivel (o uno menor) mientras
  tanto re-escanea sin cobrar (refleja lo que el usuario ya hizo).
- Garantía: si no aparece ningún consejo accionable (sin contar lo gratis), se devuelve el pago.
- Tope de TOPE_CONSULTAS_PAGAS_DIA consultas cobradas por día.
"""
from datetime import datetime
from typing import Any, Dict, Optional

import certifi
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.mongo_client import MongoClient

from config.asistente import (HISTORIAL_VISTA, MODULOS_ASISTENTE, NIVELES_ASISTENTE, ORDEN_NIVELES, TIPOS_CONSEJO,
                              TOPE_CONSULTAS_PAGAS_DIA, VISTAZO_GRATIS_POR_DIA)
from config.settings import MONGODB_URI
from services import asistente_analizadores as A
from services import asistente_reglas as R
from services import niveles_service

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

COLECCION = "asistente_consultas"
COLECCION_DESCARTES = "asistente_descartes"

# Seguimiento de cada consejo (asistente_consultas.seguimiento.<clave>): HECHO (detectado solo), NO_APLICA (desapareció
# sin rastro de que el usuario lo hiciera), LISTO (lo marcó el usuario) o DESCARTADO (no se le vuelve a mostrar hoy).
ESTADOS_SEGUIMIENTO = ("HECHO", "NO_APLICA", "LISTO", "DESCARTADO")
CONSEJOS_LOGRO_ALUMNO = 10


def _hoy() -> str:
    return datetime.now().date().isoformat()


def _k(clave: str) -> str:
    """La clave como nombre de campo de Mongo (sin '.' ni '$')."""
    return clave.replace(".", "_").replace("$", "_")


def _descartes_de_hoy(uid: ObjectId) -> set:
    return {d["clave"] for d in db[COLECCION_DESCARTES].find({"user_id": uid, "dia": _hoy()}, {"clave": 1})}


def analizar(usuario: dict, nivel: str) -> Dict[str, Any]:
    """
    Escaneo sin cobro (lo usa consultar y sirve para probar contra la base real sin tocar el saldo). Los consejos que el
    usuario descartó hoy no entran (liberan su lugar); 'claves_actuales' son TODOS los que siguen vigentes, aunque el
    nivel no los muestre o estén descartados (sirve para decidir qué "ya no aplica").
    """
    if nivel not in NIVELES_ASISTENTE:
        raise ValueError("Nivel de consulta inválido")
    ctx = A.Contexto(usuario, NIVELES_ASISTENTE[nivel]["horizonte"])
    todos = A.ejecutar_todos(ctx)
    descartados = _descartes_de_hoy(ctx.uid)
    informe = R.seleccionar([c for c in todos if c["clave"] not in descartados], nivel)
    informe["claves_actuales"] = [c["clave"] for c in todos]
    informe["frase"] = R.frase_profe(informe["resumen"], ctx.nombre)
    informe["partidos_jugados"] = ctx.jugados
    informe["mundial_id"] = ctx.mundial_id
    return informe


def _vistazos_gratis_hoy(uid: ObjectId) -> int:
    return db[COLECCION].count_documents({"user_id": uid, "dia": _hoy(), "gratis_del_dia": True})


def _vigente(uid: ObjectId, jugados: int, mundial_id: Optional[str]) -> Optional[dict]:
    """El último informe pago (o gratis del día) mientras no se haya jugado otro partido."""
    ultimo = db[COLECCION].find_one({"user_id": uid}, sort=[("fecha", -1)])
    if ultimo and ultimo.get("partidos_jugados") == jugados and ultimo.get("mundial_id") == mundial_id:
        return ultimo
    return None


def _partidos_jugados() -> tuple:
    mundial = db['mundiales'].find_one({"activo": True}, {"_id": 1})
    mundial_id = str(mundial["_id"]) if mundial else None
    jugados = db['juegos'].count_documents({"mundial_id": mundial_id, "estado": "finalizado",
                                            "transmision.estado": {"$ne": "in_progress"}}) if mundial_id else 0
    return jugados, mundial_id


def consultar(usuario: dict, nivel: str, precio_esperado: Optional[int] = None) -> Dict[str, Any]:
    """
    Cobra (si corresponde), escanea y guarda la consulta. Lanza ValueError con un mensaje para el usuario.
    'precio_esperado' es lo que mostraba la página: si el precio real es mayor (se jugó un partido y venció el informe,
    o ya se usó el Vistazo gratis) no se cobra y se avisa, así nunca se cobra algo que el usuario no confirmó.
    """
    if nivel not in NIVELES_ASISTENTE:
        raise ValueError("Nivel de consulta inválido")
    uid = ObjectId(str(usuario["_id"]))
    jugados, mundial_id = _partidos_jugados()

    # 1) Informe vigente de un nivel igual o mayor: re-escaneo sin cobrar
    vigente = _vigente(uid, jugados, mundial_id)
    if vigente and R.orden_nivel(vigente["nivel"]) >= R.orden_nivel(nivel):
        informe = analizar(usuario, vigente["nivel"])
        seguimiento = _actualizar_seguimiento(usuario, vigente, set(informe["claves_actuales"]))
        # Se conservan los consejos anteriores ya resueltos (se ven tachados) junto a los del escaneo nuevo
        for lista in ("consejos", "gratis"):
            nuevas = {c["clave"] for c in informe[lista]}
            informe[lista] = informe[lista] + [c for c in vigente.get(lista) or []
                                               if c["clave"] not in nuevas and _k(c["clave"]) in seguimiento]
        db[COLECCION].update_one({"_id": vigente["_id"]}, {"$set": {"actualizado_en": datetime.now(), "consejos": informe["consejos"],
                                                                    "gratis": informe["gratis"], "resumen": informe["resumen"]}})
        return {**informe, "id": str(vigente["_id"]), "cobrado": 0, "devuelto": False, "reutilizado": True,
                "seguimiento": _seguimiento_publico(informe, seguimiento),
                "nombre_nivel": NIVELES_ASISTENTE[vigente["nivel"]]["nombre"], "fecha": datetime.now().strftime("%d/%m %H:%M"),
                "saldo": _saldo(uid)}

    # 2) Precio: primer Vistazo del día gratis; tope de consultas pagas
    precio = NIVELES_ASISTENTE[nivel]["precio"]
    gratis_del_dia = nivel == "VISTAZO" and _vistazos_gratis_hoy(uid) < VISTAZO_GRATIS_POR_DIA
    if gratis_del_dia:
        precio = 0
    elif db[COLECCION].count_documents({"user_id": uid, "dia": _hoy(), "cobrado": {"$gt": 0}}) >= TOPE_CONSULTAS_PAGAS_DIA:
        raise ValueError(f"El Profe ya atendió {TOPE_CONSULTAS_PAGAS_DIA} consultas pagas hoy. Vuelve mañana.")

    if precio_esperado is not None and precio > precio_esperado:
        raise ValueError(f"El precio cambió: ahora el {NIVELES_ASISTENTE[nivel]['nombre']} cuesta {precio:,} pts "
                         "(se jugó un partido o ya usaste el gratis de hoy). Recarga la página para confirmarlo.")

    # 3) Cobro atómico
    if precio > 0:
        cobro = db['usuarios'].update_one({"_id": uid, "monto": {"$gte": precio}}, {"$inc": {"monto": -precio}})
        if cobro.modified_count == 0:
            raise ValueError(f"No te alcanza el saldo: el {NIVELES_ASISTENTE[nivel]['nombre']} cuesta {precio:,} pts.")

    # 4) Escaneo (si falla, se devuelve el pago)
    try:
        informe = analizar(usuario, nivel)
    except Exception:
        if precio > 0:
            db['usuarios'].update_one({"_id": uid}, {"$inc": {"monto": precio}})
        raise

    # 5) Garantía: sin nada accionable, se devuelve
    devuelto = precio > 0 and not informe["consejos"]
    if devuelto:
        db['usuarios'].update_one({"_id": uid}, {"$inc": {"monto": precio}})

    ahora = datetime.now()
    doc = {"user_id": uid, "nivel": nivel, "precio": NIVELES_ASISTENTE[nivel]["precio"], "cobrado": 0 if devuelto else precio,
           "devuelto": devuelto, "gratis_del_dia": gratis_del_dia, "dia": _hoy(), "fecha": ahora, "actualizado_en": ahora,
           "mundial_id": mundial_id, "partidos_jugados": jugados, "consejos": informe["consejos"], "gratis": informe["gratis"],
           "bloqueados": informe["bloqueados"], "resumen": informe["resumen"], "plan": informe["plan"], "frase": informe["frase"]}
    resultado = db[COLECCION].insert_one(doc)
    # XP de niveles (nunca lanza): consultar es participar, pague o no
    niveles_service.otorgar_xp(uid, "ASISTENTE", resultado.inserted_id)
    niveles_service.otorgar_logro(uid, "PRIMER_INFORME")
    return {**informe, "id": str(resultado.inserted_id), "cobrado": doc["cobrado"], "devuelto": devuelto, "seguimiento": {},
            "gratis_del_dia": gratis_del_dia, "reutilizado": False, "nombre_nivel": NIVELES_ASISTENTE[nivel]["nombre"],
            "fecha": ahora.strftime("%d/%m %H:%M"), "saldo": _saldo(uid)}


# ==========================================
# Seguimiento de consejos
# ==========================================
def _actualizar_seguimiento(usuario: dict, doc: dict, claves_actuales: Optional[set] = None) -> Dict[str, dict]:
    """
    Decide el estado de cada consejo todavía pendiente de una consulta y lo guarda: HECHO si hay rastro de que el
    usuario lo hizo (asistente_analizadores.verificar_hecho), NO_APLICA si ya no aparece en un escaneo nuevo y no hay
    rastro. 'claves_actuales' evita re-escanear cuando quien llama ya lo hizo. Devuelve el seguimiento completo.
    """
    uid = ObjectId(str(usuario["_id"]))
    seguimiento = dict(doc.get("seguimiento") or {})
    pendientes = [c for c in (doc.get("consejos") or []) + (doc.get("gratis") or []) if _k(c["clave"]) not in seguimiento]
    if not pendientes:
        return seguimiento
    nuevos: Dict[str, dict] = {}
    sin_veredicto = []
    for c in pendientes:
        try:
            hecho = A.verificar_hecho(uid, c["clave"], doc["fecha"])
        except Exception:   # noqa: BLE001 - un verificador roto no debe romper la vista
            hecho = None
        if hecho:
            nuevos[_k(c["clave"])] = {"estado": "HECHO", "fecha": datetime.now(), "tipo": c["tipo"]}
        else:
            sin_veredicto.append(c)
    if sin_veredicto:
        if claves_actuales is None:
            claves_actuales = set(analizar(usuario, doc["nivel"])["claves_actuales"])
        for c in sin_veredicto:
            if c["clave"] not in claves_actuales:
                nuevos[_k(c["clave"])] = {"estado": "NO_APLICA", "fecha": datetime.now(), "tipo": c["tipo"]}
    if nuevos:
        db[COLECCION].update_one({"_id": doc["_id"]}, {"$set": {f"seguimiento.{k}": v for k, v in nuevos.items()}})
        seguimiento.update(nuevos)
        if any(v["estado"] == "HECHO" and v["tipo"] != "GRATIS" for v in nuevos.values()):
            _quizas_logro_alumno(uid)
    return seguimiento


def _quizas_logro_alumno(uid: ObjectId) -> None:
    """Logro ALUMNO_APLICADO: CONSEJOS_LOGRO_ALUMNO consejos (no gratis) que el Profe detectó como hechos."""
    if _contar_atendidos(uid, solo_detectados=True)[0] >= CONSEJOS_LOGRO_ALUMNO:
        niveles_service.otorgar_logro(uid, "ALUMNO_APLICADO")


def _contar_atendidos(uid: ObjectId, solo_detectados: bool = False, limite: Optional[int] = None) -> tuple:
    """(atendidos, total) de consejos no gratis de las consultas del usuario (las últimas 'limite' si se indica)."""
    validos = ("HECHO",) if solo_detectados else ("HECHO", "LISTO")
    cursor = db[COLECCION].find({"user_id": uid}, {"consejos.clave": 1, "consejos.tipo": 1, "seguimiento": 1}).sort("fecha", -1)
    if limite:
        cursor = cursor.limit(limite)
    atendidos = total = 0
    for d in cursor:
        seg = d.get("seguimiento") or {}
        for c in d.get("consejos") or []:
            if c.get("tipo") == "GRATIS":
                continue
            estado = (seg.get(_k(c["clave"])) or {}).get("estado")
            if estado in ("NO_APLICA", "DESCARTADO"):
                continue   # no cuentan ni a favor ni en contra
            total += 1
            atendidos += estado in validos
    return atendidos, total


def _seguimiento_publico(doc: dict, seguimiento: Dict[str, dict]) -> Dict[str, str]:
    """{clave original: estado} para la vista."""
    return {c["clave"]: seguimiento[_k(c["clave"])]["estado"] for c in (doc.get("consejos") or []) + (doc.get("gratis") or [])
            if _k(c["clave"]) in seguimiento}


def obtener_seguimiento(usuario: dict, consulta_id: str) -> Optional[dict]:
    """Estados actualizados de los consejos de una consulta propia (la vista lo pide después de pintar el informe)."""
    try:
        oid = ObjectId(consulta_id)
    except (InvalidId, TypeError):
        return None
    doc = db[COLECCION].find_one({"_id": oid, "user_id": ObjectId(str(usuario["_id"]))})
    if not doc:
        return None
    seguimiento = _actualizar_seguimiento(usuario, doc)
    estados = _seguimiento_publico(doc, seguimiento)
    pagos = [c for c in doc.get("consejos") or []]
    atendidos = sum(1 for c in pagos if estados.get(c["clave"]) in ("HECHO", "LISTO"))
    return {"estados": estados, "atendidos": atendidos, "total": len(pagos)}


def marcar_consejo(usuario: dict, consulta_id: str, clave: str, accion: str) -> dict:
    """
    El usuario marca un consejo: 'listo' (lo hizo y el Profe no lo puede detectar), 'descartar' (no le interesa: no se
    le vuelve a mostrar hoy) o 'deshacer' (vuelve a pendiente). Un consejo HECHO o NO_APLICA no se puede cambiar.
    """
    if accion not in ("listo", "descartar", "deshacer"):
        raise ValueError("Acción inválida")
    try:
        oid = ObjectId(consulta_id)
    except (InvalidId, TypeError):
        raise ValueError("Informe inválido")
    uid = ObjectId(str(usuario["_id"]))
    doc = db[COLECCION].find_one({"_id": oid, "user_id": uid}, {"consejos": 1, "gratis": 1, "seguimiento": 1})
    if not doc:
        raise ValueError("No se encontró ese informe")
    consejo = next((c for c in (doc.get("consejos") or []) + (doc.get("gratis") or []) if c["clave"] == clave), None)
    if not consejo:
        raise ValueError("Ese consejo no está en el informe")
    actual = ((doc.get("seguimiento") or {}).get(_k(clave)) or {}).get("estado")
    if actual in ("HECHO", "NO_APLICA"):
        raise ValueError("Ese consejo ya está resuelto")
    campo = f"seguimiento.{_k(clave)}"
    if accion == "deshacer":
        db[COLECCION].update_one({"_id": oid}, {"$unset": {campo: ""}})
        db[COLECCION_DESCARTES].delete_many({"user_id": uid, "clave": clave, "dia": _hoy()})
        return {"clave": clave, "estado": None}
    estado = "LISTO" if accion == "listo" else "DESCARTADO"
    db[COLECCION].update_one({"_id": oid}, {"$set": {campo: {"estado": estado, "fecha": datetime.now(), "tipo": consejo["tipo"]}}})
    if estado == "DESCARTADO":
        db[COLECCION_DESCARTES].update_one({"user_id": uid, "clave": clave, "dia": _hoy()},
                                           {"$set": {"creado_en": datetime.now()}}, upsert=True)
    return {"clave": clave, "estado": estado}


def _saldo(uid: ObjectId) -> int:
    return int((db['usuarios'].find_one({"_id": uid}, {"monto": 1}) or {}).get("monto") or 0)


def _serializar(doc: dict) -> dict:
    """Apto para JSON (la vista lo embebe con |tojson): fechas como texto."""
    salida = {k: (v.strftime("%d/%m %H:%M") if isinstance(v, datetime) else v) for k, v in doc.items()
              if k not in ("_id", "user_id", "seguimiento")}
    salida["seguimiento"] = _seguimiento_publico(doc, doc.get("seguimiento") or {})
    return {**salida, "id": str(doc["_id"]), "nombre_nivel": NIVELES_ASISTENTE.get(doc.get("nivel"), {}).get("nombre", doc.get("nivel"))}


def obtener_informe(usuario: dict, consulta_id: str) -> Optional[dict]:
    """Una consulta guardada del propio usuario (para volver a abrirla desde el historial, sin cobrar)."""
    try:
        oid = ObjectId(consulta_id)
    except (InvalidId, TypeError):
        return None
    doc = db[COLECCION].find_one({"_id": oid, "user_id": ObjectId(str(usuario["_id"]))})
    return _serializar(doc) if doc else None


def obtener_vista(usuario: dict) -> Dict[str, Any]:
    """Todo lo de /asistente: niveles con su precio de hoy, informe vigente, historial y la frase del Profe."""
    uid = ObjectId(str(usuario["_id"]))
    jugados, mundial_id = _partidos_jugados()
    vistazo_gratis = _vistazos_gratis_hoy(uid) < VISTAZO_GRATIS_POR_DIA
    vigente = _vigente(uid, jugados, mundial_id)
    pagas_hoy = db[COLECCION].count_documents({"user_id": uid, "dia": _hoy(), "cobrado": {"$gt": 0}})
    saldo = _saldo(uid)
    permisos = set(usuario.get("permisos") or [])

    niveles = []
    for codigo in ORDEN_NIVELES:
        cfg = NIVELES_ASISTENTE[codigo]
        gratis = codigo == "VISTAZO" and vistazo_gratis
        cubierto = bool(vigente) and R.orden_nivel(vigente["nivel"]) >= R.orden_nivel(codigo)
        modulos = [{**m, "codigo": k, "a_fondo": R.orden_nivel(m["profundo_desde"]) <= R.orden_nivel(codigo)}
                   for k, m in MODULOS_ASISTENTE.items() if not m["permiso"] or m["permiso"] in permisos]
        niveles.append({**cfg, "precio_hoy": 0 if (gratis or cubierto) else cfg["precio"], "gratis_hoy": gratis,
                        "cubierto": cubierto, "modulos": modulos,
                        "alcanza": gratis or cubierto or saldo >= cfg["precio"]})

    historial = [_serializar(d) for d in db[COLECCION].find({"user_id": uid}, {"consejos": 0, "gratis": 0, "plan": 0})
                 .sort("fecha", -1).limit(HISTORIAL_VISTA)]
    nombre = usuario.get("username") or ""
    atendidos, total = _contar_atendidos(uid, limite=HISTORIAL_VISTA)
    frase = R.frase_bienvenida(vistazo_gratis, nombre)
    if total >= 3:
        frase += f" Seguiste {atendidos} de mis últimos {total} consejos." + (" ¡Así me gusta!" if atendidos * 2 >= total else "")
    return {
        "atendidos": atendidos, "total_consejos": total,
        "niveles": niveles, "saldo": saldo, "vistazo_gratis": vistazo_gratis, "pagas_hoy": pagas_hoy,
        "tope_pagas": TOPE_CONSULTAS_PAGAS_DIA, "vigente": _serializar(vigente) if vigente else None,
        "historial": historial, "frase": frase, "partidos_jugados": jugados,
        "modulos": MODULOS_ASISTENTE, "tipos": TIPOS_CONSEJO,
    }
