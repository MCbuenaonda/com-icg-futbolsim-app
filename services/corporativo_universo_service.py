"""
Corporativos Deportivos — universo y reloj.

Cada usuario juega en su propio "universo": los 10 corporativos (1 lo dirige él cuando tiene cargo, el resto la
IA), sus contratos de representación, ofertas y avisos llevan `universo_id` (= _id del usuario).

Reloj: el único gancho en la simulación es `registrar_partido` (desde juegos_service.aplicar_efectos_secundarios,
que corre tanto en el flujo manual como al terminar la transmisión en vivo: nunca spoilea). Agrega
{seq, juego_id} a `corp_registro_partidos` con un contador atómico. Cada universo guarda `cursor_seq` y
`ultimo_ciclo` y se pone al día AL LEER (`poner_al_dia`, con un candado por universo): reproduce en orden los
partidos nuevos y cierra los ciclos que se completaron (ciclo c = seq hasta c * PARTIDOS_POR_CICLO). No hay
tareas en segundo plano y un usuario que no entra no cuesta nada.
"""
import logging
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional

import certifi
from bson import ObjectId
from pymongo import ASCENDING, MongoClient, ReturnDocument, UpdateOne
from pymongo.errors import DuplicateKeyError

from config import corporativos as C
from config.settings import MONGODB_URI
from services import corporativo_reglas as R
from services.corporativo_mercado_service import valores

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database("mundial")
logger = logging.getLogger(__name__)

SEGUNDOS_CANDADO = 60
_indices_listos = False
_hilo_indices = None
MS_INDICES = 120000   # tope por índice: en el cluster compartido de Atlas un createIndexes puede no confirmar nunca


def asegurar_indices() -> None:
    """
    Crea los índices del módulo en un hilo de fondo (una sola vez por proceso; también los crea crear_indices.py).
    ⚠️ Nunca en el camino de un request: Atlas a veces tarda minutos en confirmar un createIndexes (write concern),
    y esperarlo dentro de una ruta dejaba colgado el servidor entero.
    """
    global _hilo_indices
    if _indices_listos or (_hilo_indices is not None and _hilo_indices.is_alive()):
        return

    def _trabajo():
        try:
            _crear_indices()
        except Exception as e:   # se reintenta en la próxima activación del módulo
            logger.error(f"Corporativos: no se pudieron crear los índices todavía: {e}")

    _hilo_indices = threading.Thread(target=_trabajo, name="corp-indices", daemon=True)
    _hilo_indices.start()


def _crear_indices() -> None:
    global _indices_listos
    db["corp_registro_partidos"].create_index("juego_id", unique=True, maxTimeMS=MS_INDICES)
    db["corp_registro_partidos"].create_index("seq", unique=True, maxTimeMS=MS_INDICES)
    db["corp_corporativos"].create_index([("universo_id", ASCENDING), ("sigla", ASCENDING)], unique=True, maxTimeMS=MS_INDICES)
    db["corp_contratos"].create_index([("universo_id", ASCENDING), ("tipo", ASCENDING), ("ref_id", ASCENDING)], unique=True,
                                      partialFilterExpression={"activo": True}, name="contrato_activo_unico", maxTimeMS=MS_INDICES)
    db["corp_contratos"].create_index([("universo_id", ASCENDING), ("sigla", ASCENDING), ("activo", ASCENDING)], maxTimeMS=MS_INDICES)
    db["corp_ofertas_empleo"].create_index([("universo_id", ASCENDING), ("estado", ASCENDING)], maxTimeMS=MS_INDICES)
    db["corp_avisos"].create_index([("universo_id", ASCENDING), ("creado_en", -1)], maxTimeMS=MS_INDICES)
    db["corp_ofertas"].create_index([("universo_id", ASCENDING), ("estado", ASCENDING), ("tipo", ASCENDING)], maxTimeMS=MS_INDICES)
    db["corp_movimientos"].create_index([("universo_id", ASCENDING), ("sigla", ASCENDING), ("creado_en", -1)], maxTimeMS=MS_INDICES)
    db["corp_tenencias"].create_index([("universo_id", ASCENDING), ("sigla", ASCENDING)], unique=True, maxTimeMS=MS_INDICES)
    db["corp_operaciones_bolsa"].create_index([("universo_id", ASCENDING), ("creado_en", -1)], maxTimeMS=MS_INDICES)
    _indices_listos = True


# --- Reloj global --------------------------------------------------------------------------------
def registrar_partido(juego_id, juego_doc: Optional[dict] = None) -> None:
    """Anota un partido terminado en el registro global. Idempotente y NUNCA lanza (no frena la simulación)."""
    try:
        juego_id = str(juego_id)
        if db["corp_registro_partidos"].find_one({"juego_id": juego_id}, {"_id": 1}):
            return
        seq = db["corp_reloj"].find_one_and_update({"_id": "partidos"}, {"$inc": {"seq": 1}}, upsert=True,
                                                   return_document=ReturnDocument.AFTER)["seq"]
        juego_doc = juego_doc or {}
        _actualizar_ventana(seq, juego_doc)
        db["corp_registro_partidos"].insert_one({
            "seq": seq, "juego_id": juego_id, "mundial_id": juego_doc.get("mundial_id"), "fase_id": juego_doc.get("fase_id"),
            "registrado_en": datetime.utcnow(),
        })
    except DuplicateKeyError:
        pass   # otro proceso lo registró a la vez: queda un hueco en seq, no importa (los ciclos son rangos)
    except Exception as e:
        logger.error(f"Corporativos: no se pudo registrar el partido {juego_id}: {e}")


def _actualizar_ventana(seq: int, juego_doc: dict) -> None:
    """
    Ventana de traspasos: se abre cuando un partido inaugura una fase más alta del Mundial (o empieza un Mundial
    nuevo) y dura CICLOS_VENTANA_TRASPASOS ciclos desde ahí.
    """
    fase, mundial = juego_doc.get("fase_id"), juego_doc.get("mundial_id")
    if fase is None:
        return
    reloj = db["corp_reloj"].find_one({"_id": "partidos"}) or {}
    if reloj.get("mundial_id") != mundial:
        db["corp_reloj"].update_one({"_id": "partidos"}, {"$set": {"mundial_id": mundial, "fase_max": fase, "ventana_desde_seq": seq}})
    elif fase > (reloj.get("fase_max") or 0):
        db["corp_reloj"].update_one({"_id": "partidos", "$or": [{"fase_max": {"$lt": fase}}, {"fase_max": {"$exists": False}}]},
                                    {"$set": {"fase_max": fase, "ventana_desde_seq": seq}})


def ventana_traspasos(ciclo: int) -> dict:
    """{"abierta": bool, "hasta_ciclo": n} para el ciclo dado."""
    reloj = db["corp_reloj"].find_one({"_id": "partidos"}) or {}
    desde = reloj.get("ventana_desde_seq")
    if not desde:
        return {"abierta": False, "hasta_ciclo": None}
    hasta = R.ciclo_de_seq(desde) + C.CICLOS_VENTANA_TRASPASOS
    return {"abierta": ciclo <= hasta, "hasta_ciclo": hasta}


def seq_actual() -> int:
    return int((db["corp_reloj"].find_one({"_id": "partidos"}) or {}).get("seq") or 0)


def estado_reloj(universo: Optional[dict] = None) -> dict:
    seq = seq_actual()
    ciclo_en_curso = seq // C.PARTIDOS_POR_CICLO + 1
    jugados = seq % C.PARTIDOS_POR_CICLO
    return {"seq": seq, "ciclo": ciclo_en_curso, "jugados_en_ciclo": jugados,
            "faltan": C.PARTIDOS_POR_CICLO - jugados, "pct": round(jugados * 100 / C.PARTIDOS_POR_CICLO)}


# --- Universo ------------------------------------------------------------------------------------
def dar_xp(user_id, accion: str, ref, logros: tuple = ()) -> None:
    """XP y logros de Niveles (services/niveles_service.py: idempotente por ref, nunca lanza)."""
    from services import niveles_service as N   # import diferido: niveles no depende de este módulo
    N.otorgar_xp(user_id, accion, ref)
    for codigo in logros:
        N.otorgar_logro(user_id, codigo)


def filtro_usuario(user_id) -> dict:
    """Filtro sobre `usuarios`: el universo usa el _id del usuario como string (así lo da la sesión), `usuarios` guarda ObjectId."""
    return {"_id": ObjectId(user_id) if isinstance(user_id, str) and ObjectId.is_valid(user_id) else user_id}


def obtener_universo(user_id) -> Optional[dict]:
    return db["corp_universos"].find_one({"_id": user_id})


def avisar(universo_id, ciclo: int, tipo: str, titulo: str, texto: str, icono: str = "bi-bell-fill", clave: Optional[str] = None) -> None:
    """Agrega un aviso a la bandeja. 'clave' lo hace idempotente (reprocesar un ciclo no duplica avisos)."""
    doc = {"universo_id": universo_id, "ciclo": ciclo, "tipo": tipo, "titulo": titulo, "texto": texto, "icono": icono,
           "leido": False, "creado_en": datetime.utcnow()}
    if clave:
        doc["_id"] = f"{universo_id}:{clave}"
    try:
        db["corp_avisos"].insert_one(doc)
    except DuplicateKeyError:
        pass


def crear_universo(user_id) -> dict:
    """Crea el universo del usuario (copia de la plantilla de siembra) y lo deja BUSCANDO empleo."""
    asegurar_indices()
    existente = obtener_universo(user_id)
    if existente:
        return existente
    plantilla = list(db["corp_plantilla_siembra"].find({}))
    if len(plantilla) != len(C.CORPORATIVOS):
        raise ValueError("El módulo todavía no está listo (falta la plantilla de siembra de los corporativos)")
    seq = seq_actual()
    ciclo = seq // C.PARTIDOS_POR_CICLO
    v = valores()
    ahora = datetime.utcnow()
    fases = {d["id"]: [d.get("fase_eliminatoria"), d.get("estado")]
             for d in db["internacional"].find({}, {"_id": 0, "id": 1, "fase_eliminatoria": 1, "estado": 1})}

    contratos, corporativos = [], []
    for fila in plantilla:
        sigla = fila["sigla"]
        tier = C.TIERS[C.CORPORATIVO_POR_SIGLA[sigla]["tier"]]
        valor_cartera = 0
        for tipo, ids in (("seleccion", fila["selecciones"]), ("jugador", fila["jugadores"])):
            for ref_id in ids:
                valor = v["selecciones" if tipo == "seleccion" else "jugadores"].get(ref_id, 0)
                valor_cartera += valor
                # misma semilla para todos los universos: todos arrancan con el mismo mundo
                duracion = R.semilla("siembra", sigla, tipo, ref_id).randint(*C.DURACION_CONTRATO)
                contratos.append({"universo_id": user_id, "sigla": sigla, "tipo": tipo, "ref_id": ref_id, "activo": True,
                                  "valor_firma": valor, "prima": 0, "desde_ciclo": ciclo, "hasta_ciclo": ciclo + duracion,
                                  "satisfaccion": C.SATISFACCION_INICIAL, "ciclos_sin_jugar": 0, "renta_total": 0,
                                  "honorarios_total": 0, "origen": "SIEMBRA", "creado_en": ahora,
                                  "foto_fase": fases.get(ref_id) if tipo == "seleccion" else None})
        precio = R.precio_accion(tier["capital"], valor_cartera, C.SENTIMIENTO_INICIAL)
        corporativos.append({"universo_id": user_id, "sigla": sigla, "capital": tier["capital"],
                             "capital_inicial": tier["capital"], "reputacion": tier["reputacion"], "es_del_usuario": False,
                             "confianza": C.CONFIANZA_INICIAL, "sentimiento": C.SENTIMIENTO_INICIAL,
                             "precio": precio, "precio_inicial": precio, "creado_en": ahora})

    universo = {"_id": user_id, "estado": "BUSCANDO", "fama": C.FAMA_INICIAL, "cursor_seq": seq, "ultimo_ciclo": ciclo,
                "creado_seq": seq, "primeras_ofertas_seq": seq + C.PARTIDOS_PRIMERAS_OFERTAS, "primeras_ofertas": False,
                "sin_ofertas_hasta_ciclo": 0, "rechazos_seguidos": 0, "cargo": None, "pausa_hasta_ciclo": None,
                "historial_cargos": [], "candado_hasta": None, "creado_en": ahora}
    try:
        db["corp_universos"].insert_one(universo)
    except DuplicateKeyError:
        return obtener_universo(user_id)   # doble click: ya lo creó el otro request
    db["corp_corporativos"].insert_many(corporativos)
    db["corp_contratos"].insert_many(contratos)
    avisar(user_id, ciclo + 1, "BIENVENIDA", "Estás en el mercado laboral",
           f"Tu perfil ya circula entre los 10 corporativos. En los próximos {C.PARTIDOS_PRIMERAS_OFERTAS} partidos "
           "deberían llegarte las primeras ofertas de trabajo.", "bi-briefcase-fill", clave="bienvenida")
    return universo


# --- Poner al día --------------------------------------------------------------------------------
def poner_al_dia(user_id) -> dict:
    """
    Reproduce los partidos registrados después del cursor del universo y cierra los ciclos completos (con tope
    CICLOS_MAXIMOS_POR_PEDIDO por request). Candado por universo: si otro request lo está procesando, no hace nada.
    -> {"ciclos": n cerrados, "partidos": n procesados, "atraso": bool}
    """
    from services import corporativo_carrera_service as carrera   # imports diferidos: ambos importan este módulo
    from services import corporativo_ciclo_service as economia
    from services import corporativo_fichajes_service as fichajes
    from services import corporativo_bolsa_service as bolsa
    from services import corporativo_marcas_service as marcas

    ahora = datetime.utcnow()
    universo = db["corp_universos"].find_one_and_update(
        {"_id": user_id, "$or": [{"candado_hasta": None}, {"candado_hasta": {"$lt": ahora}}]},
        {"$set": {"candado_hasta": ahora + timedelta(seconds=SEGUNDOS_CANDADO)}}, return_document=ReturnDocument.AFTER)
    if not universo:
        return {"ciclos": 0, "partidos": 0, "atraso": False}
    resumen = {"ciclos": 0, "partidos": 0, "atraso": False}
    try:
        limite = (C.CICLOS_MAXIMOS_POR_PEDIDO + 1) * C.PARTIDOS_POR_CICLO
        pendientes = list(db["corp_registro_partidos"].find({"seq": {"$gt": universo["cursor_seq"]}}).sort("seq", 1).limit(limite))
        if not pendientes:
            return resumen
        estado = economia.Estado(user_id)
        aportes = economia.aportes_de([e["juego_id"] for e in pendientes])
        for entrada in pendientes:
            seq = entrada["seq"]
            if entrada["juego_id"] in aportes:
                economia.procesar_partido(estado, aportes[entrada["juego_id"]], universo["ultimo_ciclo"] + 1, entrada["juego_id"])
                marcas.reacciones_partido(estado, aportes[entrada["juego_id"]], universo["ultimo_ciclo"] + 1, entrada["juego_id"])
            fichajes.resolver_pendientes(estado, universo, seq, universo["ultimo_ciclo"] + 1)
            if not universo.get("primeras_ofertas") and seq >= universo["primeras_ofertas_seq"]:
                carrera.ofertas_iniciales(universo)
                universo["primeras_ofertas"] = True
            universo["cursor_seq"] = seq
            resumen["partidos"] += 1
            while (universo["ultimo_ciclo"] + 1) * C.PARTIDOS_POR_CICLO <= seq:
                ciclo = universo["ultimo_ciclo"] + 1
                economia.cerrar_ciclo_economia(estado, ciclo)      # renta de fase, honorarios, satisfacción, vencimientos
                carrera.pagar_ceo(estado, universo, ciclo)         # sueldo + bono (sale de la utilidad del ciclo)
                economia.cerrar_cuentas(estado, ciclo)             # ROI, historial y cotización
                bolsa.consolidar_acciones(universo, ciclo)          # acciones del bono que cumplieron su plazo
                carrera.evaluar_directorio(estado, universo, ciclo)  # quiebras, objetivos, confianza, despido
                bolsa.dividendos_ia(estado, universo, ciclo)        # la IA con utilidad reparte dividendo
                fichajes.cerrar_ciclo_mercado(estado, universo, ciclo)
                carrera.cerrar_ciclo(universo, ciclo, estado)      # ofertas, pausa, preaviso, temporada, headhunting
                universo["ultimo_ciclo"] = ciclo
                resumen["ciclos"] += 1
                estado.guardar()
                _guardar_avance(universo)
            if resumen["ciclos"] >= C.CICLOS_MAXIMOS_POR_PEDIDO:
                resumen["atraso"] = seq < seq_actual()
                break
        estado.guardar()
        _guardar_avance(universo)
    finally:
        try:
            marcas.vaciar_lote()   # reacciones de los últimos partidos (si no hubo cierre de ciclo)
        except Exception as e:
            print(f"[corporativos] publicaciones de marcas: {e}")
        db["corp_universos"].update_one({"_id": user_id}, {"$set": {"candado_hasta": None}})
    return resumen


@contextmanager
def candado(user_id):
    """Toma el candado del universo para una acción del usuario (no se mezcla con un poner_al_dia en curso)."""
    ahora = datetime.utcnow()
    tomado = db["corp_universos"].find_one_and_update(
        {"_id": user_id, "$or": [{"candado_hasta": None}, {"candado_hasta": {"$lt": ahora}}]},
        {"$set": {"candado_hasta": ahora + timedelta(seconds=SEGUNDOS_CANDADO)}})
    if not tomado:
        raise ValueError("Tu universo se está actualizando con los últimos partidos; intenta de nuevo en unos segundos")
    try:
        yield tomado
    finally:
        db["corp_universos"].update_one({"_id": user_id}, {"$set": {"candado_hasta": None}})


def _guardar_avance(universo: dict) -> None:
    db["corp_universos"].update_one({"_id": universo["_id"]}, {"$set": {
        "cursor_seq": universo["cursor_seq"], "ultimo_ciclo": universo["ultimo_ciclo"],
        "primeras_ofertas": universo.get("primeras_ofertas", False)}})


def ciclo_en_curso(universo: dict) -> int:
    return universo["ultimo_ciclo"] + 1


def contratos_activos(universo_id, sigla: Optional[str] = None) -> list:
    filtro = {"universo_id": universo_id, "activo": True}
    if sigla:
        filtro["sigla"] = sigla
    return list(db["corp_contratos"].find(filtro))


def valor_cartera(contratos: list) -> int:
    v = valores()
    return sum((v["selecciones"] if c["tipo"] == "seleccion" else v["jugadores"]).get(c["ref_id"], 0) for c in contratos)


def refrescar_precios(universo_id) -> None:
    """(fase 5 mueve el sentimiento; aquí solo se recalcula el precio con la cartera valuada hoy)."""
    ops = []
    for corp in db["corp_corporativos"].find({"universo_id": universo_id}):
        precio = R.precio_accion(corp["capital"], valor_cartera(contratos_activos(universo_id, corp["sigla"])), corp["sentimiento"])
        ops.append(UpdateOne({"_id": corp["_id"]}, {"$set": {"precio": precio}}))
    if ops:
        db["corp_corporativos"].bulk_write(ops)
