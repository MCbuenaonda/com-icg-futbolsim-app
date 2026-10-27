"""
Lógica de negocio del módulo Fantasy: armado del Once Ideal por fase
(fantasy_teams) y reparto de puntos al simular partidos, incluyendo la
sinergia con el Álbum de Estampas (ver services/album_service.py).

Decisiones de diseño sobre puntos ambiguos del pedido original:
- 'Asistencia: +30 pts' SÍ está implementado (PUNTOS_ASISTENCIA). El motor de
  simulación (services/simular_service.py) registra 'asistencias' en
  'stats_jugadores': se atribuye al último jugador que le dio un pase de campo
  (no despeje) al goleador, siempre que la posesión no se haya perdido en el
  medio (ver 'posible_asistente' en simular_partido_realista).
- No hay una fase global única (cada confederación avanza de fase de forma
  independiente, ver fecha_service.py): por eso el Once Ideal es por Mundial y
  el reloj de los cambios son las jornadas fantasy (ver la nota de más abajo).
- Los puntos fantasy (Once Ideal) se acumulan en 'fantasy_teams.total_points_fase',
  SEPARADO del saldo de puntos gastable (usuarios.monto) — es un puntaje de
  liga fantasy, no moneda. La 'Recompensa Pasiva' del Álbum (20%, caso b) SÍ
  se acredita a usuarios.monto, porque no depende de tener un equipo fantasy
  armado para esa fase (es un beneficio pasivo de solo poseer la estampa).
- Posiciones de 'jugadores.posicion_id': se leen de la colección real
  'posiciones' (11 posiciones granulares — Portero, Defensa izquierdo/derecho,
  Lateral izquierdo/derecho, Central izquierdo/derecho/ofensivo, Extremo
  izquierdo/derecho, Delantero), NO del diccionario simplificado POSICIONES de
  services/simular_service.py (que usa posicion_id 1-4 como si fuera un
  esquema de 4 posiciones, y no coincide con los valores reales de
  'jugadores.posicion_id').
- EQUIPOS POR FORMACIÓN (v2): cada usuario tiene hasta config/fantasy.ESCUADRAS_MAX equipos por Mundial
  ('fantasy_teams.escuadra'); empieza con 1 y desbloquea el siguiente con saldo + jornadas jugadas con el anterior
  (desbloquear_escuadra; 'usuarios.fantasy_escuadras' es PERMANENTE). Cada equipo usa una formación DISTINTA del
  catálogo del motor (config/formaciones.py), que define cuántos jugadores van por línea; cada jugador entra en la
  línea natural de su posición (config/fantasy.LINEA_DE_POSICION). Un jugador no puede estar en dos equipos del mismo
  usuario; el tope de 2 por selección y 1 leyenda es por equipo. El equipo único de antes migra solo a la escuadra 1
  (en 4-3-3, la única que cuadra con el viejo "1 por puesto").
- UN EQUIPO POR MUNDIAL + JORNADAS (rediseño a pedido del usuario): antes el Once Ideal se
  guardaba por fase_id, pero cada confederación avanza de fase a su ritmo y los partidos de
  fase 1 y fase 2 se intercalan en el calendario: la vista mostraba un equipo u otro según el
  próximo partido y cada equipo solo puntuaba en los partidos de su fase. Ahora hay UN equipo
  por usuario y Mundial ('fantasy_teams.{user_id, mundial_id}'; restart_mundial lo borra) que
  suma en TODOS los partidos del Mundial. Los cambios se liberan por JORNADA FANTASY (cada
  PARTIDOS_POR_JORNADA partidos jugados del Mundial, igual para todos): +CAMBIOS_GRATIS_POR_JORNADA
  cambios gratis por jornada, acumulables hasta TOPE_CAMBIOS_GRATIS (se acreditan al leer, con
  'jornada_credito'). Cada cambio que exceda los gratis cuesta COSTO_CAMBIO_EXTRA de saldo.
  Reemplazar a un jugador cuya selección está ELIMINADA (o no juega el Mundial) es siempre
  gratis y no consume cambios; no se puede sumar un jugador eliminado. Los equipos viejos por
  fase se migran solos al primer acceso (_equipo_del_mundial).
- PAGO POR PARTIDO (v2, pago_partido): cada partido que juega un jugador alineado paga saldo por jugar (según su
  línea), por su calificación del partido y un % de sus puntos fantasy (con la postura de la formación); ×1.5 con su
  estampa. Calibrado con calibrar_fantasy.py: un equipo deja ~66 por jornada en cualquier formación y cada desbloqueo
  se recupera en 8-11 jornadas. Antes pagaba solo el 10% de los puntos (~45 en todo un Mundial).
- Indicador de desempeño por jugador del lineup ('obtener_desempeno_lineup'):
  combina los puntos fantasy que ese jugador ya le sumó al usuario en la fase
  actual (de 'fantasy_points_history') con su 'rendimiento' de carrera
  (promedio acumulado real de rating de partido a partido, no el rating de un
  solo encuentro — ver jugadores_service.actualizar_jugadores_post_partido),
  para que el usuario pueda decidir si conviene mantenerlo o cambiarlo.
"""
import certifi
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
from services import niveles_service
from services import formaciones as FSF
from config import fantasy as CFF

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

# Orden de despliegue de sectores (Portero -> Defensa -> Medio -> Delantero)
ORDEN_SECTORES = {"Portero": 0, "Defensa": 1, "Medio": 2, "Delantero": 3}

CANTIDAD_JUGADORES_LINEUP = 11
MAX_JUGADORES_POR_PAIS = 2
# Leyendas (jugadores.leyenda): juegan casi todos los partidos de su selección, así que se permite una sola
MAX_LEYENDAS_FANTASY = 1

# Jornadas fantasy: el reloj de los cambios es la cantidad de partidos jugados del Mundial (no las
# fases, que avanzan distinto en cada confederación). Cambios gratis acumulables, como en FPL.
PARTIDOS_POR_JORNADA = 20
CAMBIOS_GRATIS_POR_JORNADA = 2
TOPE_CAMBIOS_GRATIS = 5
COSTO_CAMBIO_EXTRA = 20   # pts de saldo por CADA cambio que exceda los gratis

# Puntuación base por evento (ver reglas de negocio)
PUNTOS_GOL = 50
PUNTOS_ASISTENCIA = 30
PUNTOS_ARQUERIA_EN_CERO = 40  # solo Portero/Defensa, si su equipo no recibió goles
PUNTOS_TARJETA_AMARILLA = -10
PUNTOS_TARJETA_ROJA = -25

MULTIPLICADOR_SINERGIA = 1.5
PORCENTAJE_RECOMPENSA_PASIVA = 0.20
# Porcentaje de los puntos fantasy finales (post-sinergia) que además se acredita como
# 'monto' gastable al usuario, cuando el jugador está en su Once Ideal (casos a/c).
PORCENTAJE_MONTO_POR_PUNTOS_FANTASY = 0.10

# Umbrales de 'rendimiento' (promedio acumulado de rating, 0-100) para el indicador de
# desempeño del Once Ideal (ver obtener_desempeno_lineup).
UMBRAL_RENDIMIENTO_ALTO = 70
UMBRAL_RENDIMIENTO_BAJO = 50

FORMACION_DEFAULT = CFF.FORMACION_DEFAULT


def _mapa_posiciones() -> Dict[int, dict]:
    """{posicion_id: {"nombre", "siglas", "sector"}} desde la colección real 'posiciones'."""
    return {p["id"]: {"nombre": p.get("nombre"), "siglas": p.get("siglas"), "sector": p.get("sector")} for p in db['posiciones'].find({})}


def obtener_catalogo_formaciones() -> List[dict]:
    """Las formaciones del catálogo del motor (config/formaciones.py) con los cupos por línea del Once Ideal."""
    from config import formaciones as CF
    return [{"esquema": e, "postura": CF.FORMACIONES[e]["postura"], "etiqueta": CF.FORMACIONES[e]["etiqueta"],
             "fuerte": CF.FORMACIONES[e].get("fuerte"), "debil": CF.FORMACIONES[e].get("debil"),
             "cupos": CFF.cupos_formacion(e)} for e in CFF.FORMACIONES]


def obtener_catalogo_paises() -> List[dict]:
    """Países ordenados alfabéticamente — para el filtro de búsqueda del Once Ideal."""
    return [
        {"id": p["id"], "nombre": p.get("nombre")}
        for p in db['paises'].find({}, {"id": 1, "nombre": 1}).sort("nombre", 1)
    ]


def obtener_catalogo_posiciones() -> List[dict]:
    """Las 11 posiciones reales, ordenadas por sector (Portero/Defensa/Medio/Delantero) y nombre — para el filtro de búsqueda."""
    posiciones = list(db['posiciones'].find({}, {"id": 1, "nombre": 1, "siglas": 1, "sector": 1}))
    posiciones.sort(key=lambda p: (ORDEN_SECTORES.get(p.get("sector"), 99), p.get("nombre", "")))
    return [
        {"id": p["id"], "nombre": p.get("nombre"), "siglas": p.get("siglas"), "sector": p.get("sector")}
        for p in posiciones
    ]


_cache_jornada = {"hasta": 0.0, "datos": None}
_cache_eliminados = {"hasta": 0.0, "datos": None}


def _mundial_activo_id() -> Optional[str]:
    mundial = db['mundiales'].find_one({"activo": True}, {"_id": 1})
    return str(mundial["_id"]) if mundial else None


def jornada_actual() -> dict:
    """
    Jornada fantasy en curso: cada PARTIDOS_POR_JORNADA partidos jugados del Mundial activo (sin contar el
    que está en transmisión). {"numero", "jugados", "jugados_en_jornada", "faltan", "mundial_id"}. Caché 30 s.
    """
    ahora = time.monotonic()
    if _cache_jornada["datos"] and ahora < _cache_jornada["hasta"]:
        return _cache_jornada["datos"]
    mundial_id = _mundial_activo_id()
    jugados = db['juegos'].count_documents({"mundial_id": mundial_id, "estado": "finalizado",
                                            "transmision.estado": {"$ne": "in_progress"}}) if mundial_id else 0
    en_jornada = jugados % PARTIDOS_POR_JORNADA
    datos = {"numero": jugados // PARTIDOS_POR_JORNADA + 1, "jugados": jugados, "jugados_en_jornada": en_jornada,
             "faltan": PARTIDOS_POR_JORNADA - en_jornada, "partidos_por_jornada": PARTIDOS_POR_JORNADA,
             "pct": round(en_jornada * 100 / PARTIDOS_POR_JORNADA), "mundial_id": mundial_id}
    _cache_jornada.update(hasta=ahora + 30, datos=datos)
    return datos


def paises_eliminados() -> Dict[int, str]:
    """
    {pais_id: motivo} de las selecciones cuyos jugadores ya no pueden sumar puntos en este Mundial:
    "Eliminado" (internacional.estado ELIMINADO_*) o "No participa" (no figura en 'internacional'). Caché 30 s.
    """
    ahora = time.monotonic()
    if _cache_eliminados["datos"] is not None and ahora < _cache_eliminados["hasta"]:
        return _cache_eliminados["datos"]
    en_mundial = {d["id"]: str(d.get("estado") or "") for d in db['internacional'].find({}, {"id": 1, "estado": 1})}
    datos = {}
    if en_mundial:   # sin Mundial armado no se marca a nadie
        for p in db['paises'].find({}, {"id": 1}):
            if p["id"] not in en_mundial:
                datos[p["id"]] = "No participa"
            elif en_mundial[p["id"]].startswith("ELIMINADO"):
                datos[p["id"]] = "Eliminado"
    _cache_eliminados.update(hasta=ahora + 30, datos=datos)
    return datos


def _serializar_equipo(equipo: dict) -> dict:
    return {
        "id": str(equipo["_id"]),
        "usuario_id": str(equipo["user_id"]),
        "mundial_id": equipo.get("mundial_id"),
        "fase_id": equipo.get("fase_id"),   # legado: los equipos ya no son por fase
        "escuadra": equipo.get("escuadra", 1),
        "lineup": equipo["lineup"],
        "formacion": equipo.get("formacion", FORMACION_DEFAULT),
        "is_locked": False,
        "total_points_fase": equipo.get("total_points_fase", 0),
        "monto_ganado": equipo.get("monto_ganado", 0),
        "cambios_gratis_disponibles": equipo.get("cambios_gratis_disponibles", 0),
        "completo_desde_jornada": equipo.get("completo_desde_jornada"),
    }


def _lineas_de(ids: List[int]) -> Dict[int, str]:
    """{jugador_id: línea natural} (PORTERO/DEFENSA/MEDIO/DELANTERO) según su posicion_id."""
    return {j["id"]: CFF.LINEA_DE_POSICION.get(j.get("posicion_id"), "MEDIO")
            for j in db['jugadores'].find({"id": {"$in": list(ids)}}, {"id": 1, "posicion_id": 1})}


def _cuadra_con_formacion(lineup: List[int], formacion: str) -> bool:
    lineas = _lineas_de(lineup)
    cupos = CFF.cupos_formacion(formacion)
    return all(sum(1 for j in lineup if lineas.get(j) == l) == n for l, n in cupos.items())


def _acreditar_jornadas(equipo: dict, jornada: dict) -> None:
    """Cambios gratis de las jornadas que pasaron desde el último crédito (+N por jornada, con tope)."""
    pendientes = jornada["numero"] - equipo.get("jornada_credito", jornada["numero"])
    if pendientes > 0:
        nuevos = min(TOPE_CAMBIOS_GRATIS, equipo.get("cambios_gratis_disponibles", 0) + pendientes * CAMBIOS_GRATIS_POR_JORNADA)
        db['fantasy_teams'].update_one({"_id": equipo["_id"], "jornada_credito": equipo.get("jornada_credito")},
                                       {"$set": {"cambios_gratis_disponibles": nuevos, "jornada_credito": jornada["numero"]}})
        equipo["cambios_gratis_disponibles"], equipo["jornada_credito"] = nuevos, jornada["numero"]


def _escuadras_del_mundial(usuario_oid: ObjectId) -> List[dict]:
    """
    Los equipos del usuario en el Mundial activo (ordenados por 'escuadra'), con los cambios gratis de las jornadas ya
    acreditados. Migraciones perezosas (idempotentes):
      - equipos del esquema viejo por fase (sin mundial_id): se fusionan en uno, el de la fase más alta, con la suma
        de los puntos de todos;
      - el equipo único de antes (sin 'escuadra') pasa a ser la escuadra 1; si su alineación no cuadra con los cupos
        por línea de su formación (antes la formación era solo visual), queda en 4-3-3, que acepta el once de "1 por
        puesto"; 'completo_desde_jornada' sale de su primer registro de puntos.
    """
    jornada = jornada_actual()
    mundial_id = jornada["mundial_id"]
    equipos = list(db['fantasy_teams'].find({"user_id": usuario_oid, "mundial_id": mundial_id}))
    if not equipos:
        viejos = list(db['fantasy_teams'].find({"user_id": usuario_oid, "mundial_id": {"$exists": False}}).sort("fase_id", -1))
        if not viejos:
            return []
        equipo = viejos[0]
        total = sum(v.get("total_points_fase", 0) for v in viejos)
        db['fantasy_teams'].update_one({"_id": equipo["_id"]}, {"$set": {
            "mundial_id": mundial_id, "total_points_fase": total, "jornada_credito": jornada["numero"],
            "cambios_gratis_disponibles": min(TOPE_CAMBIOS_GRATIS, max(CAMBIOS_GRATIS_POR_JORNADA, equipo.get("cambios_gratis_disponibles", 0)))}})
        if len(viejos) > 1:
            db['fantasy_teams'].delete_many({"_id": {"$in": [v["_id"] for v in viejos[1:]]}})
        equipos = [db['fantasy_teams'].find_one({"_id": equipo["_id"]})]

    for equipo in equipos:
        if equipo.get("v2"):
            continue
        cambios = {"v2": True, "escuadra": equipo.get("escuadra") or 1}
        formacion = equipo.get("formacion")
        if formacion not in CFF.FORMACIONES or not _cuadra_con_formacion(equipo["lineup"], formacion):
            cambios["formacion"] = FORMACION_DEFAULT
        if equipo.get("completo_desde_jornada") is None:
            primero = db['fantasy_points_history'].find_one({"fantasy_team_id": equipo["_id"], "jornada": {"$exists": True}},
                                                           {"jornada": 1}, sort=[("jornada", 1)])
            cambios["completo_desde_jornada"] = (primero or {}).get("jornada") or equipo.get("jornada_credito") or jornada["numero"]
        if equipo.get("monto_ganado") is None:
            ganado = list(db['fantasy_points_history'].aggregate([
                {"$match": {"fantasy_team_id": equipo["_id"]}}, {"$group": {"_id": None, "t": {"$sum": "$monto_otorgado"}}}]))
            cambios["monto_ganado"] = ganado[0]["t"] if ganado else 0
        db['fantasy_teams'].update_one({"_id": equipo["_id"]}, {"$set": cambios})
        equipo.update(cambios)

    for equipo in equipos:
        _acreditar_jornadas(equipo, jornada)
    return sorted(equipos, key=lambda e: e.get("escuadra", 1))


def _equipo_del_mundial(usuario_oid: ObjectId, escuadra: int = 1) -> Optional[dict]:
    return next((e for e in _escuadras_del_mundial(usuario_oid) if e.get("escuadra", 1) == escuadra), None)


def datos_usuario_fantasy(usuario_id) -> dict:
    """{_id, monto, fantasy_escuadras, activo} del usuario (lo que piden el desbloqueo y la vista)."""
    oid = usuario_id if isinstance(usuario_id, ObjectId) else ObjectId(usuario_id)
    return db['usuarios'].find_one({"_id": oid}, {"monto": 1, "fantasy_escuadras": 1, "activo": 1}) or {"_id": oid}


def escuadras_desbloqueadas(usuario: dict) -> int:
    return max(1, min(CFF.ESCUADRAS_MAX, int(usuario.get("fantasy_escuadras") or 1)))


# ==========================================
# Armado del Once Ideal
# ==========================================
def _validar_alineacion(lineup: List[int], formacion: str, otros_lineups: Optional[List[List[int]]] = None) -> None:
    """
    Cupos por línea de la formación (cada jugador en la línea natural de su posición), 2 por selección y 1 leyenda
    dentro del equipo, y ningún jugador que ya esté en otro equipo del usuario.
    """
    if len(lineup) != CANTIDAD_JUGADORES_LINEUP:
        raise ValueError(f"El Once Ideal debe tener exactamente {CANTIDAD_JUGADORES_LINEUP} jugadores")
    if len(set(lineup)) != len(lineup):
        raise ValueError("No se puede repetir el mismo jugador en la alineación")

    jugadores = list(db['jugadores'].find({"id": {"$in": lineup}}, {"id": 1, "nombre": 1, "posicion_id": 1, "pais_id": 1, "leyenda": 1}))
    if len(jugadores) != len(lineup):
        raise ValueError("Uno o más jugadores de la alineación no existen")

    if sum(1 for j in jugadores if j.get("leyenda")) > MAX_LEYENDAS_FANTASY:
        raise ValueError(f"Solo puedes tener {MAX_LEYENDAS_FANTASY} leyenda por equipo")

    conteo_por_pais: Dict[int, int] = {}
    for j in jugadores:
        conteo_por_pais[j["pais_id"]] = conteo_por_pais.get(j["pais_id"], 0) + 1
    if any(c > MAX_JUGADORES_POR_PAIS for c in conteo_por_pais.values()):
        raise ValueError(f"Máximo {MAX_JUGADORES_POR_PAIS} jugadores por selección en cada equipo")

    cupos = CFF.cupos_formacion(formacion)
    nombres = {"PORTERO": "portero", "DEFENSA": "defensas", "MEDIO": "medios", "DELANTERO": "delanteros"}
    for linea, n in cupos.items():
        tiene = sum(1 for j in jugadores if CFF.LINEA_DE_POSICION.get(j.get("posicion_id")) == linea)
        if tiene != n:
            raise ValueError(f"El {formacion} lleva {n} {nombres[linea]} y tu equipo tiene {tiene}")

    en_otros = {j for otro in (otros_lineups or []) for j in otro}
    repetidos = [j.get("nombre") for j in jugadores if j["id"] in en_otros]
    if repetidos:
        raise ValueError("Ya están en otro de tus equipos: " + ", ".join(repetidos))


def calcular_cambios(lineup_anterior: List[int], lineup_nuevo: List[int], cambios_gratis: int) -> dict:
    """
    Desglose de un guardado (lógica pura salvo la consulta de países): los que salen de un país eliminado se
    reemplazan gratis; el resto consume cambios gratis; lo que sobra es 'extra' y cuesta COSTO_CAMBIO_EXTRA c/u.
    """
    salientes = set(lineup_anterior) - set(lineup_nuevo)
    eliminados = paises_eliminados()
    pais_de = {j["id"]: j.get("pais_id") for j in db['jugadores'].find({"id": {"$in": list(salientes)}}, {"id": 1, "pais_id": 1})} if salientes else {}
    gratis_eliminados = sum(1 for j in salientes if pais_de.get(j) in eliminados)
    normales = len(salientes) - gratis_eliminados
    usados = min(normales, cambios_gratis)
    extra = normales - usados
    return {"total": len(salientes), "gratis_eliminados": gratis_eliminados, "usados": usados, "extra": extra,
            "costo": extra * COSTO_CAMBIO_EXTRA, "cambios_gratis_restantes": cambios_gratis - usados}


def set_fantasy_lineup(usuario_id: str, lineup: List[int], formacion: str = FORMACION_DEFAULT, escuadra: int = 1) -> dict:
    """
    Valida y guarda uno de los equipos del usuario para el Mundial activo (suman en todas las fases). Armarlo por
    primera vez es gratis. Después, cada guardado se desglosa con calcular_cambios: los reemplazos de jugadores
    eliminados son gratis, el resto consume los cambios gratis de las jornadas de ESE equipo y cada cambio extra cobra
    COSTO_CAMBIO_EXTRA de saldo (atómico). No se puede SUMAR un jugador de una selección eliminada.
    Cada equipo usa una formación distinta (define los cupos por línea). Lanza ValueError si algo no se cumple.
    """
    if formacion not in CFF.FORMACIONES:
        raise ValueError("Formación desconocida")
    usuario_oid = ObjectId(usuario_id)
    usuario = db['usuarios'].find_one({"_id": usuario_oid})
    if not usuario or not usuario.get("activo", True):
        raise ValueError("Usuario no encontrado o inactivo")
    try:
        escuadra = int(escuadra or 1)
    except (TypeError, ValueError):
        raise ValueError("Equipo inválido")
    if escuadra < 1 or escuadra > escuadras_desbloqueadas(usuario):
        raise ValueError("Ese equipo todavía no está desbloqueado")

    jornada = jornada_actual()
    if not jornada["mundial_id"]:
        raise ValueError("No hay un Mundial activo")
    todos = _escuadras_del_mundial(usuario_oid)
    equipo = next((e for e in todos if e.get("escuadra", 1) == escuadra), None)
    otros = [e for e in todos if e is not equipo]
    if any(e.get("formacion") == formacion for e in otros):
        raise ValueError(f"Ya usas el {formacion} en otro equipo: cada equipo lleva una formación distinta")
    _validar_alineacion(lineup, formacion, [e["lineup"] for e in otros])
    anteriores = set(equipo["lineup"]) if equipo else set()

    # No se puede sumar un jugador que ya no juega (los que ya estaban se pueden mantener hasta cambiarlos)
    eliminados = paises_eliminados()
    entrantes = [j for j in lineup if j not in anteriores]
    if entrantes:
        bloqueados = [j for j in db['jugadores'].find({"id": {"$in": entrantes}}, {"nombre": 1, "pais_id": 1}) if j.get("pais_id") in eliminados]
        if bloqueados:
            raise ValueError("No puedes sumar jugadores de selecciones que ya no juegan el Mundial: "
                             + ", ".join(f"{j.get('nombre')} ({eliminados[j['pais_id']].lower()})" for j in bloqueados))

    if not equipo:
        nuevo = {"user_id": usuario_oid, "mundial_id": jornada["mundial_id"], "escuadra": escuadra, "lineup": lineup,
                 "formacion": formacion, "total_points_fase": 0, "monto_ganado": 0, "v2": True,
                 "cambios_gratis_disponibles": CAMBIOS_GRATIS_POR_JORNADA, "jornada_credito": jornada["numero"],
                 "completo_desde_jornada": jornada["numero"], "created_at": datetime.now()}
        nuevo["_id"] = db['fantasy_teams'].insert_one(nuevo).inserted_id
        desglose = {"total": 0, "gratis_eliminados": 0, "usados": 0, "extra": 0, "costo": 0, "cambios_gratis_restantes": CAMBIOS_GRATIS_POR_JORNADA}
        equipo = nuevo
    else:
        desglose = calcular_cambios(equipo["lineup"], lineup, equipo.get("cambios_gratis_disponibles", 0))
        if desglose["costo"]:
            cobro = db['usuarios'].update_one({"_id": usuario_oid, "monto": {"$gte": desglose["costo"]}},
                                              {"$inc": {"monto": -desglose["costo"]}})
            if cobro.modified_count == 0:
                raise ValueError(f"Saldo insuficiente: {desglose['extra']} cambio(s) extra cuestan {desglose['costo']} pts "
                                 f"({COSTO_CAMBIO_EXTRA} c/u)")
        db['fantasy_teams'].update_one({"_id": equipo["_id"]}, {"$set": {
            "lineup": lineup, "formacion": formacion, "cambios_gratis_disponibles": desglose["cambios_gratis_restantes"]}})
        equipo.update(lineup=lineup, formacion=formacion, cambios_gratis_disponibles=desglose["cambios_gratis_restantes"])

    # XP de niveles (nunca lanza): armar el equipo o ajustarlo, una vez por jornada
    if not anteriores or desglose["total"]:
        niveles_service.otorgar_xp(usuario_oid, "ONCE_IDEAL", niveles_service.ref_mundial("jornada", jornada["numero"]))
    niveles_service.otorgar_logro(usuario_oid, "PRIMER_ONCE_IDEAL")
    return {**_serializar_equipo(equipo), "cambios": desglose}


def estado_desbloqueo(usuario: dict, escuadras: Optional[List[dict]] = None) -> Optional[dict]:
    """
    El próximo equipo por desbloquear: {escuadra, costo, jornadas_requeridas, jornadas_cumplidas, listo, motivo}
    (None si ya están todos). Pide saldo y JORNADAS_PARA_DESBLOQUEAR jornadas con el equipo anterior armado.
    """
    abiertas = escuadras_desbloqueadas(usuario)
    if abiertas >= CFF.ESCUADRAS_MAX:
        return None
    siguiente = abiertas + 1
    if escuadras is None:
        escuadras = _escuadras_del_mundial(usuario["_id"] if isinstance(usuario["_id"], ObjectId) else ObjectId(usuario["_id"]))
    anterior = next((e for e in escuadras if e.get("escuadra", 1) == abiertas), None)
    jornada = jornada_actual()["numero"]
    cumplidas = max(0, jornada - anterior["completo_desde_jornada"]) if anterior and anterior.get("completo_desde_jornada") else 0
    costo = CFF.COSTOS_ESCUADRA[siguiente]
    motivo = None
    if not anterior:
        motivo = f"Primero arma tu equipo {abiertas}"
    elif cumplidas < CFF.JORNADAS_PARA_DESBLOQUEAR:
        faltan = CFF.JORNADAS_PARA_DESBLOQUEAR - cumplidas
        motivo = f"Juega {faltan} jornada{'s' if faltan != 1 else ''} más con tu equipo {abiertas}"
    elif (usuario.get("monto") or 0) < costo:
        motivo = f"Te faltan {costo - int(usuario.get('monto') or 0):,} de saldo"
    return {"escuadra": siguiente, "costo": costo, "jornadas_requeridas": CFF.JORNADAS_PARA_DESBLOQUEAR,
            "recupera_jornadas": round(costo / CFF.PAGO_ESPERADO_JORNADA), "pago_jornada": CFF.PAGO_ESPERADO_JORNADA,
            "jornadas_cumplidas": min(cumplidas, CFF.JORNADAS_PARA_DESBLOQUEAR), "listo": motivo is None, "motivo": motivo}


def desbloquear_escuadra(usuario_id: str) -> dict:
    """Desbloquea el siguiente equipo: cobro atómico condicionado al saldo y a que nadie lo haya desbloqueado antes."""
    usuario_oid = ObjectId(usuario_id)
    usuario = db['usuarios'].find_one({"_id": usuario_oid}, {"monto": 1, "fantasy_escuadras": 1, "activo": 1})
    if not usuario or not usuario.get("activo", True):
        raise ValueError("Usuario no encontrado o inactivo")
    estado = estado_desbloqueo(usuario)
    if not estado:
        raise ValueError("Ya tienes todos los equipos desbloqueados")
    if not estado["listo"]:
        raise ValueError(estado["motivo"])
    abiertas = estado["escuadra"] - 1
    filtro_abiertas = {"$in": [None, 1]} if abiertas == 1 else abiertas
    cobro = db['usuarios'].update_one({"_id": usuario_oid, "monto": {"$gte": estado["costo"]}, "fantasy_escuadras": filtro_abiertas},
                                      {"$inc": {"monto": -estado["costo"]}, "$set": {"fantasy_escuadras": estado["escuadra"]}})
    if cobro.modified_count == 0:
        raise ValueError("No se pudo desbloquear: revisa tu saldo e intenta de nuevo")
    db['fantasy_movimientos'].insert_one({"user_id": usuario_oid, "tipo": "DESBLOQUEO", "monto": -estado["costo"],
                                          "escuadra": estado["escuadra"], "detalle": f"Equipo {estado['escuadra']} del Once Ideal",
                                          "created_at": datetime.now()})
    niveles_service.otorgar_logro(usuario_oid, "SEGUNDO_EQUIPO_FANTASY")
    return {"escuadra": estado["escuadra"], "costo": estado["costo"]}


def obtener_escuadras(usuario_id: str) -> List[dict]:
    return [_serializar_equipo(e) for e in _escuadras_del_mundial(ObjectId(usuario_id))]


def obtener_alineacion(usuario_id: str, fase_id: Optional[int] = None) -> Optional[dict]:
    """Equipo 1 del usuario para el Mundial activo ('fase_id' se ignora: se mantiene por compatibilidad de la API)."""
    equipo = _equipo_del_mundial(ObjectId(usuario_id))
    return _serializar_equipo(equipo) if equipo else None


def _enriquecer_jugadores(jugadores: List[dict]) -> List[dict]:
    ids_paises = list({j["pais_id"] for j in jugadores})
    nombres_paises = {p["id"]: p["nombre"] for p in db['paises'].find({"id": {"$in": ids_paises}}, {"id": 1, "nombre": 1})}
    mapa_posiciones = _mapa_posiciones()
    eliminados = paises_eliminados()

    resultado = []
    for j in jugadores:
        datos_posicion = mapa_posiciones.get(j.get("posicion_id"), {})
        sector = datos_posicion.get("sector")
        resultado.append({
            "id": j["id"],
            "nombre": j.get("nombre"),
            "posicion_id": j.get("posicion_id"),
            # Bucket en MAYÚSCULAS (PORTERO/DEFENSA/MEDIO/DELANTERO) para agrupar los 11 puestos
            # granulares en los 4 slots de la formación (ver templates/fantasy_once_ideal.html).
            "posicion": sector.upper() if sector else "MEDIO",
            "posicion_nombre": datos_posicion.get("nombre", "?"),
            "posicion_siglas": datos_posicion.get("siglas", "?"),
            "pais_id": j.get("pais_id"),
            "pais_nombre": nombres_paises.get(j.get("pais_id"), "?"),
            "overall": j.get("overall", 0),
            "numero": j.get("numero"),  # dorsal, para dibujar el jersey con el número
            # Su selección ya no juega el Mundial: no suma puntos y reemplazarlo es gratis
            "eliminado": j.get("pais_id") in eliminados,
            "motivo_eliminado": eliminados.get(j.get("pais_id")),
            "leyenda": bool(j.get("leyenda")),
        })
    return resultado


def buscar_jugadores(texto: str = "", pais_id: Optional[int] = None, posicion_id: Optional[int] = None, limite: int = 30,
                     leyendas: Optional[bool] = None, linea: Optional[str] = None) -> List[dict]:
    """Búsqueda por nombre/país/posición o línea, para el selector del Once Ideal (leyendas=True: solo leyendas)."""
    filtro: Dict[str, Any] = {}
    if linea in CFF.LINEAS and posicion_id is None:
        filtro["posicion_id"] = {"$in": [p for p, l in CFF.LINEA_DE_POSICION.items() if l == linea]}
    if leyendas is True:
        filtro["leyenda"] = True
    elif leyendas is False:
        filtro["leyenda"] = {"$ne": True}
    if texto:
        filtro["nombre"] = {"$regex": re.escape(texto), "$options": "i"}
    if pais_id is not None:
        filtro["pais_id"] = pais_id
    if posicion_id is not None:
        filtro["posicion_id"] = posicion_id

    jugadores = list(db['jugadores'].find(
        filtro,
        {"id": 1, "nombre": 1, "posicion_id": 1, "pais_id": 1, "overall": 1, "numero": 1, "leyenda": 1}
    ).limit(limite))

    return _enriquecer_jugadores(jugadores)


def obtener_detalle_jugadores(ids: List[int]) -> List[dict]:
    """Datos completos (nombre/posición/país) de una lista de ids de jugadores, para prellenar una alineación ya guardada."""
    if not ids:
        return []
    jugadores = list(db['jugadores'].find(
        {"id": {"$in": ids}},
        {"id": 1, "nombre": 1, "posicion_id": 1, "pais_id": 1, "overall": 1, "numero": 1, "leyenda": 1}
    ))
    return _enriquecer_jugadores(jugadores)


# ==========================================
# Puntuación al simular un partido (sinergia con el Álbum)
# ==========================================
def _desglosar_puntos_base(stats: dict, goles_local: int, goles_visitante: int) -> List[dict]:
    """
    Desglose legible de cómo se arma 'puntos_base' para un jugador en un partido,
    concepto por concepto — es la fuente tanto de _calcular_puntos_base como del
    historial de puntos fantasy (ver procesar_eventos_jugadores_partido).
    """
    desglose = []

    goles = stats.get("goles", 0)
    if goles:
        desglose.append({"concepto": "Goles", "cantidad": goles, "puntos_unitarios": PUNTOS_GOL, "subtotal": goles * PUNTOS_GOL})

    asistencias = stats.get("asistencias", 0)
    if asistencias:
        desglose.append({"concepto": "Asistencias", "cantidad": asistencias, "puntos_unitarios": PUNTOS_ASISTENCIA, "subtotal": asistencias * PUNTOS_ASISTENCIA})

    amarillas = stats.get("amarillas", 0)
    if amarillas:
        desglose.append({"concepto": "Tarjetas amarillas", "cantidad": amarillas, "puntos_unitarios": PUNTOS_TARJETA_AMARILLA, "subtotal": amarillas * PUNTOS_TARJETA_AMARILLA})

    rojas = stats.get("rojas", 0)
    if rojas:
        desglose.append({"concepto": "Tarjetas rojas", "cantidad": rojas, "puntos_unitarios": PUNTOS_TARJETA_ROJA, "subtotal": rojas * PUNTOS_TARJETA_ROJA})

    if stats.get("posicion") in ("PORTERO", "DEFENSA"):
        equipo_no_recibio_goles = (
            (stats.get("lado") == "L" and goles_visitante == 0) or
            (stats.get("lado") == "V" and goles_local == 0)
        )
        if equipo_no_recibio_goles:
            desglose.append({"concepto": "Arquería en cero", "cantidad": 1, "puntos_unitarios": PUNTOS_ARQUERIA_EN_CERO, "subtotal": PUNTOS_ARQUERIA_EN_CERO})

    return desglose


def _calcular_puntos_base(stats: dict, goles_local: int, goles_visitante: int) -> int:
    return sum(item["subtotal"] for item in _desglosar_puntos_base(stats, goles_local, goles_visitante))


def puntos_con_postura(desglose: List[dict], formacion: str) -> int:
    """Puntos fantasy con la postura de la formación: goles/asistencias valen más en una ofensiva, la valla en una defensiva."""
    postura = FSF.postura(formacion) if formacion in CFF.FORMACIONES else 0.0
    total = 0.0
    for item in desglose:
        if item["concepto"] in ("Goles", "Asistencias"):
            total += item["subtotal"] * (1 + CFF.POSTURA_GOL * postura)
        elif item["concepto"] == "Arquería en cero":
            total += item["subtotal"] * (1 - CFF.POSTURA_VALLA * postura)
        else:
            total += item["subtotal"]
    return int(round(total))


def pago_partido(stats: dict, desglose: List[dict], formacion: str, en_album: bool) -> dict:
    """
    Lógica pura: lo que gana un jugador alineado en un partido (ver config/fantasy.py).
    {puntos_formacion, puntos_finales, pago_jugar, pago_desempeno, pago_puntos, multiplicador, monto}
    """
    multiplicador = MULTIPLICADOR_SINERGIA if en_album else 1.0
    puntos_formacion = puntos_con_postura(desglose, formacion)
    puntos_finales = int(puntos_formacion * multiplicador)
    linea = CFF.LINEA_DE_POSICION.get(stats.get("posicion_id")) or str(stats.get("posicion") or "MEDIO").upper()
    pago_jugar = CFF.PAGO_POR_PARTIDO.get(linea, CFF.PAGO_POR_PARTIDO["MEDIO"]) * (CFF.FRACCION_SUPLENTE if stats.get("entro_de_cambio") else 1.0)
    rating = stats.get("rating")
    pago_desempeno = max(0.0, (rating or CFF.RATING_BASE_PAGO) - CFF.RATING_BASE_PAGO) * CFF.PAGO_POR_PUNTO_RATING
    pago_puntos = puntos_formacion * CFF.PORCENTAJE_MONTO_POR_PUNTOS
    monto = max(0, int(round((pago_jugar + pago_desempeno + pago_puntos) * multiplicador)))
    return {"puntos_formacion": puntos_formacion, "puntos_finales": puntos_finales, "rating": rating,
            "pago_jugar": int(round(pago_jugar)), "pago_desempeno": int(round(pago_desempeno)),
            "pago_puntos": int(round(pago_puntos)), "multiplicador": multiplicador, "monto": monto}


def procesar_eventos_jugadores_partido(
    fase_id: int, stats_jugadores: Dict[int, dict], goles_local: int, goles_visitante: int,
    match_id: Optional[str] = None, mundial_id: Optional[str] = None
) -> None:
    """
    Se llama al terminar cada partido (juegos_service.aplicar_efectos_secundarios; en vivo, al terminar la transmisión).
    Por cada jugador que participó:
      a) En un equipo del Once Ideal: cobra el pago del partido (pago_partido: por jugar + desempeño + % de sus puntos
         con la postura de la formación; ×1.5 si además tiene su estampa) a usuarios.monto, y sus puntos fantasy suman
         al equipo (total_points_fase). Queda en 'fantasy_points_history' aunque no haya hecho puntos (cobró por jugar).
      b) Solo en el Álbum: 20% de los puntos base (pasiva) a usuarios.monto, en 'album_passive_rewards'.
    Un jugador está en un solo equipo por usuario (lo valida set_fantasy_lineup).
    """
    if not stats_jugadores:
        return
    mundial_id = mundial_id or _mundial_activo_id()
    jornada = jornada_actual()["numero"]

    for jugador_id, stats in stats_jugadores.items():
        try:
            jugador_id = int(jugador_id)
        except (TypeError, ValueError):
            continue
        desglose = _desglosar_puntos_base(stats, goles_local, goles_visitante)
        puntos_base = sum(item["subtotal"] for item in desglose)

        equipos_con_lineup = list(db['fantasy_teams'].find(
            {"mundial_id": mundial_id, "lineup": jugador_id}, {"user_id": 1, "formacion": 1, "escuadra": 1}))
        if not equipos_con_lineup and puntos_base == 0:
            continue
        albumes_con_jugador = list(db['user_albums'].find({"owned_jugadores": jugador_id}, {"user_id": 1}))
        ids_en_album = {a["user_id"] for a in albumes_con_jugador}
        ids_en_lineup = {eq["user_id"] for eq in equipos_con_lineup}

        for equipo in equipos_con_lineup:
            en_album = equipo["user_id"] in ids_en_album
            pago = pago_partido(stats, desglose, equipo.get("formacion") or FORMACION_DEFAULT, en_album)
            db['fantasy_teams'].update_one({"_id": equipo["_id"]},
                                           {"$inc": {"total_points_fase": pago["puntos_finales"], "monto_ganado": pago["monto"]}})
            if pago["monto"]:
                db['usuarios'].update_one({"_id": equipo["user_id"]}, {"$inc": {"monto": pago["monto"]}})
            db['fantasy_points_history'].insert_one({
                "user_id": equipo["user_id"],
                "fantasy_team_id": equipo["_id"],
                "escuadra": equipo.get("escuadra", 1),
                "formacion": equipo.get("formacion"),
                "fase_id": fase_id,   # fase del partido (informativo: el equipo suma en todas)
                "mundial_id": mundial_id,
                "jornada": jornada,
                "match_id": match_id,
                "jugador_id": jugador_id,
                "jugador_nombre": stats.get("nombre", "?"),
                "desglose": desglose,
                "puntos_base": puntos_base,
                "sinergia_album_aplicada": en_album,
                "multiplicador": pago["multiplicador"],
                "puntos_finales": pago["puntos_finales"],
                "monto_otorgado": pago["monto"],
                "pago": pago,
                "created_at": datetime.now()
            })

        # Caso b): tiene la estampa pero NO tiene a este jugador en ningún equipo. No es puntaje fantasy: va a
        # 'album_passive_rewards' (el Álbum marca qué estampas de jugador ya dieron regalía pasiva).
        if puntos_base == 0:
            continue
        for album in albumes_con_jugador:
            if album["user_id"] in ids_en_lineup:
                continue
            puntos_pasivos = int(puntos_base * PORCENTAJE_RECOMPENSA_PASIVA)
            if puntos_pasivos != 0:
                db['usuarios'].update_one({"_id": album["user_id"]}, {"$inc": {"monto": puntos_pasivos}})
                db['album_passive_rewards'].insert_one({
                    "user_id": album["user_id"],
                    "tipo_estampa": "JUGADOR",
                    "item_id": jugador_id,
                    "fase_id": fase_id,
                    "match_id": match_id,
                    "puntos_otorgados": puntos_pasivos,
                    "created_at": datetime.now()
                })


def obtener_historial_puntos_fantasy(usuario_id: str, fase_id: Optional[int] = None, limite: int = 50) -> List[dict]:
    """
    Historial de lo que sumó el Once Ideal del usuario en el Mundial, más reciente primero. 'fase_id' se ignora
    (compatibilidad): restart_mundial borra 'fantasy_points_history', así que todo lo guardado es del Mundial actual.
    """
    registros = db['fantasy_points_history'].find(
        {"user_id": ObjectId(usuario_id)}
    ).sort("created_at", -1).limit(limite)

    return [
        {
            "id": str(r["_id"]),
            "jugador_id": r["jugador_id"],
            "jugador_nombre": r.get("jugador_nombre", "?"),
            "desglose": r.get("desglose", []),
            "puntos_base": r.get("puntos_base", 0),
            "sinergia_album_aplicada": r.get("sinergia_album_aplicada", False),
            "multiplicador": r.get("multiplicador", 1.0),
            "puntos_finales": r.get("puntos_finales", 0),
            "monto_otorgado": r.get("monto_otorgado", 0),
            "escuadra": r.get("escuadra", 1),
            "pago": r.get("pago"),
            "created_at": r.get("created_at")
        }
        for r in registros
    ]


# ==========================================
# Indicador de desempeño del Once Ideal
# ==========================================
def obtener_desempeno_lineup(usuario_id: str, lineup: List[int]) -> Dict[int, dict]:
    """
    Indicador de desempeño por jugador del Once Ideal del usuario, para ayudar a decidir
    si conviene mantenerlo o cambiarlo. Combina dos señales:
      - 'puntos_totales_fase'/'partidos_puntuados': lo que ese jugador ya le sumó al
        usuario en ESTE Mundial (de 'fantasy_points_history') — mide el rendimiento fantasy
        real, pero solo cuenta partidos donde tuvo algún evento puntuable (gol, asistencia,
        tarjeta, arquería en cero); un jugador titular sin esos eventos no genera entradas.
      - 'rendimiento': el promedio acumulado real de rating de partido del jugador (ver
        jugadores_service.actualizar_jugadores_post_partido) — una señal de forma general,
        disponible incluso si todavía no le dio puntos fantasy en esta fase.
    'estado' es una clasificación simple (alto/medio/bajo) en base a 'rendimiento', para
    poder pintar un semáforo en la vista sin que el frontend tenga que conocer los umbrales.
    """
    if not lineup:
        return {}

    pipeline = [
        {"$match": {"user_id": ObjectId(usuario_id), "jugador_id": {"$in": lineup}}},
        {"$group": {
            "_id": "$jugador_id",
            "puntos_totales_fase": {"$sum": "$puntos_finales"},
            "partidos_puntuados": {"$sum": 1}
        }}
    ]
    puntos_por_jugador = {d["_id"]: d for d in db['fantasy_points_history'].aggregate(pipeline)}

    jugadores_info = {
        j["id"]: j for j in db['jugadores'].find({"id": {"$in": lineup}}, {"id": 1, "rendimiento": 1})
    }

    resultado: Dict[int, dict] = {}
    for jugador_id in lineup:
        puntos = puntos_por_jugador.get(jugador_id, {"puntos_totales_fase": 0, "partidos_puntuados": 0})
        rendimiento = jugadores_info.get(jugador_id, {}).get("rendimiento", 60.0)

        if rendimiento >= UMBRAL_RENDIMIENTO_ALTO:
            estado = "alto"
        elif rendimiento >= UMBRAL_RENDIMIENTO_BAJO:
            estado = "medio"
        else:
            estado = "bajo"

        resultado[jugador_id] = {
            "puntos_totales_fase": puntos["puntos_totales_fase"],
            "partidos_puntuados": puntos["partidos_puntuados"],
            "rendimiento": rendimiento,
            "estado": estado
        }
    return resultado
