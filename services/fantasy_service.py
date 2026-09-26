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
- '¿Qué fase está "actual"/"iniciada"?': esta app no tiene una fase global
  única (cada confederación avanza de fase de forma independiente, ver
  fecha_service.py). Se define "fase iniciada" como: ya se jugó al menos un
  partido de esa fase_id (sin importar la confederación) — ver fase_ya_iniciada.
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
- Acomodo de formaciones (FORMACIONES_GRANULARES): a pedido explícito del
  usuario, cada formación define qué posiciones GRANULARES (por siglas) caen
  en cada línea — esto NO es un agrupamiento genérico por sector, reubica
  posiciones puntuales (ej. el Central Ofensivo/MC cae a la línea defensiva en
  3-5-2; el Delantero/DC sube a la línea media en 4-4-2 y 3-5-2). Las 3
  formaciones soportadas usan, cada una, las 10 posiciones de campo exactas
  una sola vez (sin repetir ninguna) — por eso 'set_fantasy_lineup' valida la
  alineación de forma agnóstica a la formación elegida: siempre exige
  exactamente 1 jugador por cada una de las 11 posiciones reales que existan
  en la colección 'posiciones' (Portero + las 10 de campo), sin repetir
  ninguna. La formación elegida (guardada en 'fantasy_teams.formacion') es
  puramente una preferencia visual de cómo agrupar esas 11 posiciones en 3
  líneas al armar el equipo — cambiar de formación NO invalida jugadores ya
  elegidos, solo reordena en qué línea se muestran.
- Cambios gratis por fase (a pedido explícito del usuario): 'fase_ya_iniciada'
  se dispara con el PRIMER partido de ese fase_id en CUALQUIER confederación,
  pero como cada confederación avanza de fase de forma independiente, eso
  bloqueaba/penalizaba cambios cuando en la práctica a la mayoría de las
  confederaciones todavía les quedaban muchos partidos de esa fase por jugar.
  Para suavizar eso: cada vez que una confederación completa por completo esa
  fase_id (ver 'refrescar_cambios_gratis_fase', llamada desde
  routes/simular_route.py en el mismo punto donde ya se dispara
  'crear_siguiente_fase'), se le RESETEA (no acumula) a 5 la cantidad de
  cambios gratis disponibles para todos los equipos de esa fase_id. Al guardar
  una alineación con la fase iniciada, la cantidad de jugadores distintos
  respecto a la alineación anterior se descuenta de ese crédito mientras
  alcance; si el usuario cambia más jugadores de los que tiene de crédito
  gratis en un solo guardado, se cobra la penalización de 20 pts de siempre
  por ese guardado (y se consume el crédito que quedaba disponible).
- Recompensa en 'monto' sobre los puntos fantasy (a pedido explícito del
  usuario): además de sumar a 'total_points_fase' (puntaje de liga, no
  moneda), los casos a) y c) ahora también acreditan un porcentaje
  (PORCENTAJE_MONTO_POR_PUNTOS_FANTASY) de los puntos finales del jugador a
  'usuarios.monto' — a diferencia de la recompensa pasiva del Álbum (caso b,
  20%, por solo poseer la estampa), esta es un incentivo adicional por tener
  al jugador realmente alineado en el Once Ideal.
- Indicador de desempeño por jugador del lineup ('obtener_desempeno_lineup'):
  combina los puntos fantasy que ese jugador ya le sumó al usuario en la fase
  actual (de 'fantasy_points_history') con su 'rendimiento' de carrera
  (promedio acumulado real de rating de partido a partido, no el rating de un
  solo encuentro — ver jugadores_service.actualizar_jugadores_post_partido),
  para que el usuario pueda decidir si conviene mantenerlo o cambiarlo.
"""
import certifi
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

# Orden de despliegue de sectores (Portero -> Defensa -> Medio -> Delantero)
ORDEN_SECTORES = {"Portero": 0, "Defensa": 1, "Medio": 2, "Delantero": 3}

CANTIDAD_JUGADORES_LINEUP = 11
MAX_JUGADORES_POR_PAIS = 2
COSTO_CAMBIO_FASE_INICIADA = 20

# Cantidad de cambios gratis que se otorgan (se resetea a este valor, no se acumula) cada
# vez que una confederación completa la fase — ver refrescar_cambios_gratis_fase.
CAMBIOS_GRATIS_POR_VENTANA = 5

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

FORMACION_DEFAULT = "4-3-3"

# Acomodo de las 10 posiciones de campo (por siglas) en cada línea, según el
# esquema explícito que definió el usuario. El Portero (POR) es fijo en las 3.
FORMACIONES_GRANULARES = {
    "4-3-3": {
        "DEFENSA": ["LI", "DFI", "DFD", "LD"],
        "MEDIO": ["MI", "MC", "MD"],
        "DELANTERO": ["EI", "DC", "ED"]
    },
    "4-4-2": {
        "DEFENSA": ["LI", "DFI", "DFD", "LD"],
        "MEDIO": ["MI", "MC", "DC", "MD"],
        "DELANTERO": ["EI", "ED"]
    },
    "3-5-2": {
        "DEFENSA": ["DFI", "MC", "DFD"],
        "MEDIO": ["LI", "MI", "MD", "LD", "DC"],
        "DELANTERO": ["EI", "ED"]
    }
}


def _mapa_posiciones() -> Dict[int, dict]:
    """{posicion_id: {"nombre", "siglas", "sector"}} desde la colección real 'posiciones'."""
    return {p["id"]: {"nombre": p.get("nombre"), "siglas": p.get("siglas"), "sector": p.get("sector")} for p in db['posiciones'].find({})}


def obtener_formaciones_granulares() -> Dict[str, Dict[str, List[dict]]]:
    """
    FORMACIONES_GRANULARES resuelto con los datos reales de cada posición
    (id/nombre/siglas), listo para que el frontend arme los 11 "slots" con
    nombre propio de cada formación (ver templates/fantasy_once_ideal.html).
    """
    mapa_posiciones = _mapa_posiciones()
    siglas_a_id = {v["siglas"]: pid for pid, v in mapa_posiciones.items()}

    def _resolver(sigla: str) -> Optional[dict]:
        pid = siglas_a_id.get(sigla)
        if pid is None:
            return None
        return {"id": pid, "siglas": sigla, "nombre": mapa_posiciones[pid]["nombre"]}

    resultado: Dict[str, Dict[str, List[dict]]] = {}
    for formacion, lineas in FORMACIONES_GRANULARES.items():
        resultado[formacion] = {
            linea: [p for p in (_resolver(s) for s in siglas) if p]
            for linea, siglas in lineas.items()
        }
    return resultado


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


def fase_ya_iniciada(fase_id: int) -> bool:
    """Una fase se considera 'iniciada' apenas se jugó el primer partido de esa fase (cualquier confederación)."""
    return db['juegos'].count_documents({"fase_id": fase_id, "estado": "finalizado"}) > 0


def _serializar_equipo(equipo: dict, fase_iniciada: Optional[bool] = None) -> dict:
    return {
        "id": str(equipo["_id"]),
        "usuario_id": str(equipo["user_id"]),
        "fase_id": equipo["fase_id"],
        "lineup": equipo["lineup"],
        "formacion": equipo.get("formacion", FORMACION_DEFAULT),
        "is_locked": fase_iniciada if fase_iniciada is not None else equipo.get("is_locked", False),
        "total_points_fase": equipo.get("total_points_fase", 0),
        "cambios_gratis_disponibles": equipo.get("cambios_gratis_disponibles", 0)
    }


# ==========================================
# Armado del Once Ideal
# ==========================================
def _validar_alineacion(lineup: List[int]) -> None:
    if len(lineup) != CANTIDAD_JUGADORES_LINEUP:
        raise ValueError(f"El Once Ideal debe tener exactamente {CANTIDAD_JUGADORES_LINEUP} jugadores")
    if len(set(lineup)) != len(lineup):
        raise ValueError("No se puede repetir el mismo jugador en la alineación")

    jugadores = list(db['jugadores'].find({"id": {"$in": lineup}}, {"id": 1, "posicion_id": 1, "pais_id": 1}))
    if len(jugadores) != len(lineup):
        raise ValueError("Uno o más jugadores de la alineación no existen")

    # Máximo 2 jugadores por selección
    conteo_por_pais: Dict[int, int] = {}
    for j in jugadores:
        conteo_por_pais[j["pais_id"]] = conteo_por_pais.get(j["pais_id"], 0) + 1
    excedidos = [pid for pid, cantidad in conteo_por_pais.items() if cantidad > MAX_JUGADORES_POR_PAIS]
    if excedidos:
        raise ValueError(f"Máximo {MAX_JUGADORES_POR_PAIS} jugadores por selección (excedido en país id {excedidos})")

    # Cada una de las 11 posiciones reales (Portero + las 10 de campo) debe cubrirse con
    # exactamente 1 jugador — sin repetir ninguna. Es agnóstico a la formación elegida:
    # las 3 formaciones soportadas usan las mismas 10 posiciones de campo, solo cambia en
    # qué línea se muestra cada una (ver FORMACIONES_GRANULARES y su nota de diseño arriba).
    mapa_posiciones = _mapa_posiciones()
    ids_requeridos = set(mapa_posiciones.keys())
    ids_lineup = [j["posicion_id"] for j in jugadores]

    if len(set(ids_lineup)) != len(ids_lineup):
        repetidas = {pid for pid in ids_lineup if ids_lineup.count(pid) > 1}
        siglas_repetidas = ", ".join(sorted(mapa_posiciones.get(pid, {}).get("siglas", "?") for pid in repetidas))
        raise ValueError(f"No podés tener más de un jugador en la misma posición: {siglas_repetidas}")

    if set(ids_lineup) != ids_requeridos:
        faltantes = ids_requeridos - set(ids_lineup)
        siglas_faltantes = ", ".join(sorted(mapa_posiciones.get(pid, {}).get("siglas", "?") for pid in faltantes))
        raise ValueError(f"Faltan jugadores para estas posiciones: {siglas_faltantes}")


def set_fantasy_lineup(usuario_id: str, fase_id: int, lineup: List[int], formacion: str = FORMACION_DEFAULT) -> dict:
    """
    Valida y guarda el Once Ideal del usuario para una fase.

    Si ya existía una alineación para esa fase Y la fase ya se empezó a jugar (en
    cualquier confederación), la cantidad de jugadores que cambiaron respecto a la
    alineación anterior se descuenta del crédito de cambios gratis del equipo
    ('cambios_gratis_disponibles' — se resetea a CAMBIOS_GRATIS_POR_VENTANA cada vez que
    una confederación completa esa fase, ver refrescar_cambios_gratis_fase). Si la cantidad
    de cambios excede el crédito disponible, se cobra la penalización plana de siempre
    (COSTO_CAMBIO_FASE_INICIADA) por todo el guardado, y se consume el crédito que quedaba.

    'formacion' es solo la preferencia visual de agrupamiento (ver nota de
    diseño arriba) — no afecta la validación, que es la misma para las 3.
    Lanza ValueError con un mensaje descriptivo si alguna validación falla.
    """
    _validar_alineacion(lineup)

    if formacion not in FORMACIONES_GRANULARES:
        formacion = FORMACION_DEFAULT

    usuario_oid = ObjectId(usuario_id)
    usuario = db['usuarios'].find_one({"_id": usuario_oid})
    if not usuario or not usuario.get("activo", True):
        raise ValueError("Usuario no encontrado o inactivo")

    equipo_existente = db['fantasy_teams'].find_one({"user_id": usuario_oid, "fase_id": fase_id})
    iniciada = fase_ya_iniciada(fase_id)

    cambios_gratis_restantes = equipo_existente.get("cambios_gratis_disponibles", 0) if equipo_existente else 0

    if equipo_existente and iniciada:
        cantidad_cambios = len(set(equipo_existente["lineup"]) - set(lineup))

        if cantidad_cambios <= cambios_gratis_restantes:
            # Cubierto por el crédito de cambios gratis de la fase: no se cobra penalización.
            cambios_gratis_restantes -= cantidad_cambios
        else:
            if usuario.get("monto", 0) < COSTO_CAMBIO_FASE_INICIADA:
                raise ValueError(
                    f"Saldo insuficiente para pagar la penalización de {COSTO_CAMBIO_FASE_INICIADA} pts "
                    f"por cambiar la alineación con la fase ya iniciada"
                )
            descuento = db['usuarios'].update_one(
                {"_id": usuario_oid, "monto": {"$gte": COSTO_CAMBIO_FASE_INICIADA}},
                {"$inc": {"monto": -COSTO_CAMBIO_FASE_INICIADA}}
            )
            if descuento.modified_count == 0:
                raise ValueError(
                    f"Saldo insuficiente para pagar la penalización de {COSTO_CAMBIO_FASE_INICIADA} pts "
                    f"por cambiar la alineación con la fase ya iniciada"
                )
            cambios_gratis_restantes = 0

    if equipo_existente:
        db['fantasy_teams'].update_one(
            {"_id": equipo_existente["_id"]},
            {"$set": {
                "lineup": lineup, "formacion": formacion, "is_locked": iniciada,
                "cambios_gratis_disponibles": cambios_gratis_restantes
            }}
        )
        equipo_existente["lineup"] = lineup
        equipo_existente["formacion"] = formacion
        equipo_existente["cambios_gratis_disponibles"] = cambios_gratis_restantes
        return _serializar_equipo(equipo_existente, fase_iniciada=iniciada)

    nuevo_equipo = {
        "user_id": usuario_oid,
        "fase_id": fase_id,
        "lineup": lineup,
        "formacion": formacion,
        "is_locked": iniciada,
        "total_points_fase": 0,
        "cambios_gratis_disponibles": 0,
        "created_at": datetime.now()
    }
    resultado = db['fantasy_teams'].insert_one(nuevo_equipo)
    nuevo_equipo["_id"] = resultado.inserted_id
    return _serializar_equipo(nuevo_equipo, fase_iniciada=iniciada)


def refrescar_cambios_gratis_fase(fase_id: int) -> None:
    """
    Se llama cuando una confederación completa por completo una fase (ver
    routes/simular_route.py, mismo punto donde se dispara crear_siguiente_fase).
    Resetea (NO acumula) a CAMBIOS_GRATIS_POR_VENTANA el crédito de cambios gratis de
    TODOS los equipos fantasy de esa fase_id, sin importar cuánto crédito les quedaba.
    """
    db['fantasy_teams'].update_many(
        {"fase_id": fase_id},
        {"$set": {"cambios_gratis_disponibles": CAMBIOS_GRATIS_POR_VENTANA}}
    )


def obtener_alineacion(usuario_id: str, fase_id: int) -> Optional[dict]:
    equipo = db['fantasy_teams'].find_one({"user_id": ObjectId(usuario_id), "fase_id": fase_id})
    if not equipo:
        return None
    return _serializar_equipo(equipo, fase_iniciada=fase_ya_iniciada(fase_id))


def obtener_equipo_mas_reciente_anterior(usuario_id: str, fase_id_actual: int) -> Optional[dict]:
    """
    Busca el equipo fantasy MÁS RECIENTE (mayor fase_id) que el usuario haya guardado en una
    fase ANTERIOR a 'fase_id_actual'. Sirve para el "carry-over" del Once Ideal entre fases.

    Por qué hace falta: la fase "actual" del módulo Fantasy (ver routes/fantasy_route.py
    ::fantasy_home) se recalcula en CADA visita a partir del próximo partido pendiente de TODO
    el torneo, combinando las 6 confederaciones -- y como cada una avanza de fase a su propio
    ritmo, ese número avanza apenas CUALQUIERA de ellas completa una fase, no solo la del
    usuario. Un usuario puede volver a la página después de haber armado su equipo y encontrar
    que la fase "actual" ya avanzó más allá de la fase en la que armó su Once Ideal -- sin este
    carry-over, 'obtener_alineacion' para la fase nueva no encuentra nada y el usuario ve una
    alineación completamente vacía, aunque su equipo anterior sigue intacto en 'fantasy_teams'
    (nada en el flujo normal de avance de fase borra esos documentos, solo restart_mundial()).
    """
    equipo = db['fantasy_teams'].find_one(
        {"user_id": ObjectId(usuario_id), "fase_id": {"$lt": fase_id_actual}},
        sort=[("fase_id", -1)]
    )
    if not equipo:
        return None
    return _serializar_equipo(equipo)


def _enriquecer_jugadores(jugadores: List[dict]) -> List[dict]:
    ids_paises = list({j["pais_id"] for j in jugadores})
    nombres_paises = {p["id"]: p["nombre"] for p in db['paises'].find({"id": {"$in": ids_paises}}, {"id": 1, "nombre": 1})}
    mapa_posiciones = _mapa_posiciones()

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
            "overall": j.get("overall", 0)
        })
    return resultado


def buscar_jugadores(texto: str = "", pais_id: Optional[int] = None, posicion_id: Optional[int] = None, limite: int = 30) -> List[dict]:
    """Búsqueda por nombre/país/posición, para el selector de jugadores del Once Ideal."""
    filtro: Dict[str, Any] = {}
    if texto:
        filtro["nombre"] = {"$regex": texto, "$options": "i"}
    if pais_id is not None:
        filtro["pais_id"] = pais_id
    if posicion_id is not None:
        filtro["posicion_id"] = posicion_id

    jugadores = list(db['jugadores'].find(
        filtro,
        {"id": 1, "nombre": 1, "posicion_id": 1, "pais_id": 1, "overall": 1}
    ).limit(limite))

    return _enriquecer_jugadores(jugadores)


def obtener_detalle_jugadores(ids: List[int]) -> List[dict]:
    """Datos completos (nombre/posición/país) de una lista de ids de jugadores, para prellenar una alineación ya guardada."""
    if not ids:
        return []
    jugadores = list(db['jugadores'].find(
        {"id": {"$in": ids}},
        {"id": 1, "nombre": 1, "posicion_id": 1, "pais_id": 1, "overall": 1}
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


def procesar_eventos_jugadores_partido(
    fase_id: int, stats_jugadores: Dict[int, dict], goles_local: int, goles_visitante: int,
    match_id: Optional[str] = None
) -> None:
    """
    Se llama al terminar de simular un partido (ver routes/simular_route.py).
    Por cada jugador que participó, calcula sus puntos base y los distribuye
    entre los usuarios que lo tengan en su Once Ideal de esta fase y/o en su Álbum:
      a) Solo en el Once Ideal          -> 100% de los puntos base -> total_points_fase.
      b) Solo en el Álbum (sin lineup)  -> 20% de los puntos base (pasiva)  -> usuarios.monto.
      c) En AMBOS                       -> 150% (sinergia x1.5)   -> total_points_fase.
    Los casos a) y c) (los que SÍ tocan total_points_fase) quedan además
    registrados en 'fantasy_points_history', con el desglose de cómo se armó
    el puntaje — es la fuente del historial que se muestra en el Once Ideal
    (ver obtener_historial_puntos_fantasy). El caso b) NO se registra ahí
    porque no es puntaje fantasy: es un beneficio pasivo del Álbum a
    usuarios.monto, fuera del alcance de "cálculo de puntos fantasy".

    Además, en los casos a) y c), se acredita a 'usuarios.monto' un porcentaje
    (PORCENTAJE_MONTO_POR_PUNTOS_FANTASY) de los puntos finales del jugador — un
    incentivo en moneda gastable por tener al jugador realmente alineado, aparte del
    puntaje de liga fantasy (que sigue siendo un contador separado, no moneda).
    """
    if not stats_jugadores:
        return

    for jugador_id, stats in stats_jugadores.items():
        desglose = _desglosar_puntos_base(stats, goles_local, goles_visitante)
        puntos_base = sum(item["subtotal"] for item in desglose)
        if puntos_base == 0:
            continue

        equipos_con_lineup = list(db['fantasy_teams'].find(
            {"fase_id": fase_id, "lineup": jugador_id},
            {"user_id": 1}
        ))
        ids_en_lineup = {eq["user_id"] for eq in equipos_con_lineup}

        albumes_con_jugador = list(db['user_albums'].find(
            {"owned_jugadores": jugador_id},
            {"user_id": 1}
        ))
        ids_en_album = {a["user_id"] for a in albumes_con_jugador}

        # Casos a) y c): tiene al jugador en su Once Ideal de esta fase
        for equipo in equipos_con_lineup:
            en_album = equipo["user_id"] in ids_en_album
            multiplicador = MULTIPLICADOR_SINERGIA if en_album else 1.0
            puntos_finales = int(puntos_base * multiplicador)
            monto_otorgado = int(puntos_finales * PORCENTAJE_MONTO_POR_PUNTOS_FANTASY)

            db['fantasy_teams'].update_one(
                {"_id": equipo["_id"]},
                {"$inc": {"total_points_fase": puntos_finales}}
            )
            if monto_otorgado != 0:
                db['usuarios'].update_one({"_id": equipo["user_id"]}, {"$inc": {"monto": monto_otorgado}})
            db['fantasy_points_history'].insert_one({
                "user_id": equipo["user_id"],
                "fantasy_team_id": equipo["_id"],
                "fase_id": fase_id,
                "match_id": match_id,
                "jugador_id": jugador_id,
                "jugador_nombre": stats.get("nombre", "?"),
                "desglose": desglose,
                "puntos_base": puntos_base,
                "sinergia_album_aplicada": en_album,
                "multiplicador": multiplicador,
                "puntos_finales": puntos_finales,
                "monto_otorgado": monto_otorgado,
                "created_at": datetime.now()
            })

        # Caso b): tiene la estampa pero NO tiene lineup con este jugador en esta fase.
        # No se registra en 'fantasy_points_history' (no es puntaje fantasy, ver
        # docstring arriba), sino en 'album_passive_rewards' -- únicamente para poder
        # marcar en el Álbum (templates/album_coleccion.html) qué estampas de jugador
        # ya le generaron alguna regalía pasiva al usuario.
        for album in albumes_con_jugador:
            if album["user_id"] in ids_en_lineup:
                continue  # ya cubierto arriba (caso c)
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


def obtener_historial_puntos_fantasy(usuario_id: str, fase_id: int, limite: int = 50) -> List[dict]:
    """Historial de eventos que sumaron/restaron 'total_points_fase' para el usuario en esta fase, más recientes primero."""
    registros = db['fantasy_points_history'].find(
        {"user_id": ObjectId(usuario_id), "fase_id": fase_id}
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
            "created_at": r.get("created_at")
        }
        for r in registros
    ]


# ==========================================
# Indicador de desempeño del Once Ideal
# ==========================================
def obtener_desempeno_lineup(usuario_id: str, fase_id: int, lineup: List[int]) -> Dict[int, dict]:
    """
    Indicador de desempeño por jugador del Once Ideal del usuario, para ayudar a decidir
    si conviene mantenerlo o cambiarlo. Combina dos señales:
      - 'puntos_totales_fase'/'partidos_puntuados': lo que ese jugador ya le sumó al
        usuario en ESTA fase (de 'fantasy_points_history') — mide el rendimiento fantasy
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
        {"$match": {"user_id": ObjectId(usuario_id), "fase_id": fase_id, "jugador_id": {"$in": lineup}}},
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
