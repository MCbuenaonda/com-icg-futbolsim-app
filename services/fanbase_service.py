"""
Servicio de "Popularidad y Base de Aficionados por Selección".

Responsabilidades:
  - calculate_match_fanbase_delta: calcula cuánto suma/resta de 'aficionados' un partido
    puntual para UN equipo (resultado + efecto estrella + sorpresa David vs Goliat).
  - actualizar_aficionados_post_partido: aplica ese delta a AMBOS equipos del partido en
    'paises', guarda el total resultante embebido en el propio documento de 'juegos', y deja
    un registro en el historial ('historial_aficionados') con el motivo del cambio.
  - obtener_ranking_aficionados: listado de selecciones ordenadas por 'aficionados', para el
    endpoint GET /countries/fanbase-ranking.
  - obtener_historial_aficionados_pais: evolución de aficionados de un país a lo largo del
    torneo (fuente del historial pedido en el requerimiento).

Diseño: 'aficionados' vive SOLO en 'paises' (el roster permanente), no en 'internacional' --
a diferencia de 'poder'/'rankin' (que sí se sincronizan a ambas colecciones porque alimentan
el sorteo de cupos de repechaje), la base de aficionados es una métrica de popularidad de la
selección en sí, independiente del mundial/fase en curso (así lo pidió el requerimiento:
"independiente del ranking FIFA del país"). El SNAPSHOT del total resultante sí se guarda en
'juegos.equipo_local/equipo_visitante.aficionados' (a pedido explícito), para que el feed de
"Últimos Partidos" pueda mostrar el número de "likes" de cada post sin tener que reconsultar
'paises' (que para entonces ya tiene un valor más nuevo que el de ese partido puntual).
"""
import certifi
import random
from datetime import datetime
from typing import Any, Dict, Optional
from bson import ObjectId
from pymongo.collection import Collection
from pymongo.mongo_client import MongoClient
from pymongo import ReturnDocument
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

# Base UNIFORME de aficionados: todos los países arrancan con exactamente este valor (ver
# mundial_service.restart_mundial y el script de migración ajustar_aficionados_paises.py). No
# es un rango aleatorio -- a pedido explícito, todas las selecciones parten parejas y lo que
# las diferencia después es lo que van ganando/perdiendo partido a partido.
AFICIONADOS_INICIAL = 100_000

# a) Componente resultado -- ESCALADO COMO PORCENTAJE de los aficionados ACTUALES del equipo
# (ya no puntos fijos: sobre una base de 100,000, +100/-30 puntos fijos eran imperceptibles).
# Cada categoría define un rango [mínimo, máximo] de variación porcentual; se sortea un valor
# dentro del rango para que el impacto no sea siempre idéntico ante resultados similares.
FASE_MUNDIAL_GRUPOS = 7  # a partir de acá el partido "vale más" (fase de grupos del Mundial en adelante)
FASES_ELIMINACION_DIRECTA = {8, 9, 10, 11, 12, 13}  # perder acá = quedar eliminado del Mundial
DIFERENCIA_GOLES_GOLEADA = 3  # diferencia de goles a partir de la cual una victoria/derrota es "por goleada"

RANGO_PCT_VICTORIA_GOLEADA = (0.05, 0.10)      # +5% a +10%
RANGO_PCT_VICTORIA_NORMAL = (0.02, 0.045)      # +2% a +4.5%
RANGO_PCT_EMPATE = (-0.01, 0.01)               # -1% a +1%
RANGO_PCT_DERROTA_AJUSTADA = (-0.035, -0.015)  # -1.5% a -3.5%
RANGO_PCT_DERROTA_GOLEADA = (-0.10, -0.05)     # -5% a -10%

# b) Componente "Efecto Estrella": compensación cuando el equipo pierde o empata pero igual
# hubo algo para destacar (un gol propio o una actuación individual sobresaliente). También
# expresado como porcentaje de los aficionados actuales, no como punto fijo.
BONO_PCT_EFECTO_ESTRELLA = 0.01  # +1% extra
# Umbral de rating de partido (0-10, ver simular_service.calcular_rating_partido) a partir del
# cual se considera una "actuación sobresaliente" aunque el jugador no haya anotado.
UMBRAL_RATING_SOBRESALIENTE = 8.0

# c) Componente sorpresa (David vs Goliat): multiplica el delta ya calculado (funciona igual de
# bien sobre un delta porcentual que sobre uno de puntos fijos).
DIFERENCIA_RANKING_SORPRESA = 15
MULTIPLICADOR_SORPRESA = 1.5

# Piso de aficionados: nunca puede caer por debajo de este valor (antes era 0 -- con la base de
# 100,000 se sube a 1,000 para que un equipo nunca quede en absolutamente cero aficionados).
AFICIONADOS_MINIMO = 1_000


def _calcular_delta_detallado(match_data: Dict[str, Any], player_events: Dict[int, dict], team_id: int, aficionados_actual: int) -> Dict[str, Any]:
    """
    Lógica real del algoritmo (a + b + c). Devuelve no solo el delta final sino también las
    señales intermedias (resultado, si fue goleada, si hubo efecto estrella, si hubo sorpresa,
    goles) para que tanto 'calculate_match_fanbase_delta' (contrato público, solo el número)
    como el generador de 'motivo' del historial puedan reusar el mismo cálculo sin duplicar la
    lógica de negocio.
    """
    es_local = team_id == match_data["id_local"]

    goles_propios = match_data["goles_local"] if es_local else match_data["goles_visitante"]
    goles_rival = match_data["goles_visitante"] if es_local else match_data["goles_local"]
    rankin_propio = match_data.get("rankin_local" if es_local else "rankin_visitante") or 0
    rankin_rival = match_data.get("rankin_visitante" if es_local else "rankin_local") or 0
    fase_id = match_data.get("fase_id") or 1

    # La base sobre la que se calculan los porcentajes es la cantidad ACTUAL de aficionados del
    # equipo (no la inicial de 100,000 ni un valor fijo) -- así el impacto de un partido crece o
    # se achica junto con la popularidad real que ya tiene la selección.
    base = max(aficionados_actual, AFICIONADOS_MINIMO)
    diferencia_goles = abs(goles_propios - goles_rival)
    es_goleada = diferencia_goles >= DIFERENCIA_GOLES_GOLEADA

    # a) Componente resultado
    if goles_propios > goles_rival:
        resultado = "victoria"
        rango_pct = RANGO_PCT_VICTORIA_GOLEADA if es_goleada else RANGO_PCT_VICTORIA_NORMAL
    elif goles_propios == goles_rival:
        resultado = "empate"
        rango_pct = RANGO_PCT_EMPATE
    else:
        resultado = "derrota"
        rango_pct = RANGO_PCT_DERROTA_GOLEADA if es_goleada else RANGO_PCT_DERROTA_AJUSTADA

    delta = round(base * random.uniform(*rango_pct))

    # b) Efecto Estrella: solo compensa cuando el equipo NO ganó (si ganó ya se llevó el bono
    # completo del punto 'a'). Alcanza con que UN jugador propio haya anotado o tenido un
    # rating sobresaliente -- no se acumulan bonos por cada jugador destacado, es un bono fijo
    # de "hubo algo para rescatar del partido".
    hubo_efecto_estrella = False
    if resultado in ("empate", "derrota"):
        lado_equipo = "L" if es_local else "V"
        hubo_efecto_estrella = any(
            stats.get("lado") == lado_equipo
            and (stats.get("goles", 0) > 0 or stats.get("rating", 0) >= UMBRAL_RATING_SOBRESALIENTE)
            for stats in (player_events or {}).values()
        )
        if hubo_efecto_estrella:
            delta += round(base * BONO_PCT_EFECTO_ESTRELLA)

    # c) Sorpresa (David vs Goliat): solo tiene sentido sobre una victoria. 'rankin' más BAJO
    # es mejor puesto (como el ranking FIFA real: #1 es el mejor). "Un rival que le supera por
    # más de 15 lugares" = el rival tiene un número de ranking MENOR (mejor) que el propio por
    # más de 15 posiciones.
    hubo_sorpresa = False
    if resultado == "victoria" and rankin_propio and rankin_rival:
        diferencia_ranking = rankin_propio - rankin_rival
        if diferencia_ranking > DIFERENCIA_RANKING_SORPRESA:
            hubo_sorpresa = True
            delta = round(delta * MULTIPLICADOR_SORPRESA)

    return {
        "delta": delta, "resultado": resultado, "es_goleada": es_goleada,
        "hubo_efecto_estrella": hubo_efecto_estrella, "hubo_sorpresa": hubo_sorpresa,
        "goles_propios": goles_propios, "goles_rival": goles_rival, "fase_id": fase_id
    }


def calculate_match_fanbase_delta(match_data: Dict[str, Any], player_events: Dict[int, dict], team_id: int, aficionados_actual: int) -> int:
    """
    Calcula la variación de aficionados ('delta_aficionados') de UN equipo tras un partido, como
    un PORCENTAJE de sus aficionados actuales (ver RANGO_PCT_* más arriba) -- no un punto fijo.

    :param match_data: datos del partido ya jugado -- se espera:
        {
          "fase_id": int,
          "id_local": int, "id_visitante": int,
          "goles_local": int, "goles_visitante": int,
          "rankin_local": int, "rankin_visitante": int  # ranking FIFA de cada equipo AL
              MOMENTO del partido (se usa el 'rankin' embebido en 'juegos.equipo_local/
              equipo_visitante', tal como quedó grabado cuando se generó el fixture -- ver
              juegos_service.construir_objeto_equipo -- no el ranking actual, que puede haber
              cambiado desde entonces).
        }
    :param player_events: 'stats_jugadores' tal como lo arma
        services/simular_service.simular_partido_realista -- {jugador_id: {goles, rating,
        lado, ...}}. Se usa para el componente "Efecto Estrella".
    :param team_id: id (campo 'id' de 'paises', no el ObjectId) del equipo a evaluar. Debe
        coincidir con 'match_data["id_local"]' o 'match_data["id_visitante"]'.
    :param aficionados_actual: cantidad de aficionados que tiene el equipo AHORA (antes de
        aplicar este partido) -- es la base sobre la que se calcula el porcentaje. Esta función
        sigue siendo pura (no consulta Mongo); quien la llama es responsable de leer este valor.
    :return: delta de aficionados (puede ser negativo). NO aplica el piso de AFICIONADOS_MINIMO
        acá -- eso lo hace la capa de persistencia (ver _aplicar_delta_aficionados), porque el
        piso depende del valor ACTUAL en la base al momento de escribir, no al momento de leer.
    """
    return _calcular_delta_detallado(match_data, player_events, team_id, aficionados_actual)["delta"]


def _generar_motivo(detalle: Dict[str, Any]) -> str:
    """Descripción breve y legible del cambio de aficionados, para el historial -- refleja tanto
    el resultado como la MAGNITUD del cambio (goleada vs. resultado ajustado)."""
    resultado = detalle["resultado"]
    fase_id = detalle["fase_id"]
    es_goleada = detalle["es_goleada"]

    if resultado == "victoria":
        if detalle["hubo_sorpresa"]:
            return "Victoria sorpresa ante un rival muy mejor rankeado"
        if es_goleada:
            return "Gran victoria por goleada"
        return "Victoria en el Mundial" if fase_id >= FASE_MUNDIAL_GRUPOS else "Victoria en fase de clasificación"

    if resultado == "empate":
        return "Empate con actuación destacada" if detalle["hubo_efecto_estrella"] else "Empate sin sobresaltos"

    # derrota
    if fase_id in FASES_ELIMINACION_DIRECTA:
        return "Eliminación del Mundial"
    if es_goleada:
        return "Pérdida severa de afición tras derrota dolorosa"
    return "Derrota ajustada con actuación destacada (efecto estrella)" if detalle["hubo_efecto_estrella"] else "Derrota ajustada"


def _aplicar_delta_aficionados(coleccion: Collection, pais_id: int, delta: int) -> int:
    """
    Aplica 'aficionados = max(AFICIONADOS_MINIMO, (aficionados_actual o AFICIONADOS_INICIAL) +
    delta)' de forma ATÓMICA y en un solo round-trip a Mongo, vía un update de tipo pipeline de
    agregación.

    Por qué no un '$inc' simple: los operadores de update clásicos no se pueden combinar sobre
    el MISMO campo en una sola operación (no se puede pedir '$inc' y '$max' juntos sobre
    'aficionados' en un solo update), así que un '$inc' plano no puede garantizar el piso
    mínimo de forma atómica -- requeriría una lectura previa (find_one) y un '$set' aparte, lo
    que abre una condición de carrera entre la lectura y la escritura. El update-pipeline de
    abajo hace la inicialización (si hace falta), la suma Y el piso mínimo en una sola operación
    atómica del lado del servidor, y devuelve el total resultante.

    :return: 'aficionados_totales_resultantes' después de aplicar el delta.
    """
    documento = coleccion.find_one_and_update(
        {"id": pais_id},
        [{
            "$set": {
                "aficionados": {
                    "$max": [AFICIONADOS_MINIMO, {"$add": [{"$ifNull": ["$aficionados", AFICIONADOS_INICIAL]}, delta]}]
                }
            }
        }],
        projection={"aficionados": 1},
        return_document=ReturnDocument.AFTER
    )
    return documento.get("aficionados", AFICIONADOS_MINIMO) if documento else AFICIONADOS_MINIMO


def _registrar_historial_aficionados(pais_id: int, match_id: Optional[str], delta: int, total_resultante: int, motivo: str) -> None:
    """Inserta un registro en 'historial_aficionados' con la evolución de este país."""
    db["historial_aficionados"].insert_one({
        "pais_id": pais_id,
        "partido_id": match_id,
        "aficionados_ganados_perdidos": delta,
        "aficionados_totales_resultantes": total_resultante,
        "motivo": motivo,
        "created_at": datetime.now()
    })


def actualizar_aficionados_post_partido(
    match_data: Dict[str, Any], player_events: Dict[int, dict], match_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calcula y aplica el delta de aficionados de AMBOS equipos de un partido recién simulado.
    Se llama desde routes/simular_route.py al terminar de registrar el resultado del partido.

    Efectos:
      1. Actualiza 'paises.aficionados' de ambos equipos (atómico, sin bajar de 0).
      2. Si se pasa 'match_id', guarda el total resultante embebido en el propio documento de
         'juegos' ('equipo_local.aficionados' / 'equipo_visitante.aficionados' según
         corresponda) -- a pedido explícito, para que el partido quede con un snapshot de
         cuántos aficionados tenía cada equipo en ese momento.
      3. Deja un registro en 'historial_aficionados' por cada equipo, con el delta, el total
         resultante y un motivo descriptivo del cambio.

    :return: {"local": {...}, "visitante": {...}} -- cada uno con 'delta' y
        'aficionados_totales', para que la vista pueda mostrar el resumen post-partido sin
        tener que recalcular ni reconsultar nada.
    """
    id_local = match_data["id_local"]
    id_visita = match_data["id_visitante"]

    paises_coll = db["paises"]
    # El delta ahora es un PORCENTAJE de los aficionados ACTUALES de cada equipo (ver
    # _calcular_delta_detallado), así que hace falta leerlos antes de calcular -- una sola
    # consulta batched para ambos equipos, no dos round-trips separados.
    aficionados_actuales = {
        p["id"]: p.get("aficionados", AFICIONADOS_INICIAL)
        for p in paises_coll.find({"id": {"$in": [id_local, id_visita]}}, {"id": 1, "aficionados": 1})
    }
    aficionados_actual_local = aficionados_actuales.get(id_local, AFICIONADOS_INICIAL)
    aficionados_actual_visita = aficionados_actuales.get(id_visita, AFICIONADOS_INICIAL)

    detalle_local = _calcular_delta_detallado(match_data, player_events, id_local, aficionados_actual_local)
    detalle_visita = _calcular_delta_detallado(match_data, player_events, id_visita, aficionados_actual_visita)

    total_local = _aplicar_delta_aficionados(paises_coll, id_local, detalle_local["delta"])
    total_visita = _aplicar_delta_aficionados(paises_coll, id_visita, detalle_visita["delta"])

    _registrar_historial_aficionados(id_local, match_id, detalle_local["delta"], total_local, _generar_motivo(detalle_local))
    _registrar_historial_aficionados(id_visita, match_id, detalle_visita["delta"], total_visita, _generar_motivo(detalle_visita))

    if match_id:
        try:
            db["juegos"].update_one(
                {"_id": ObjectId(match_id)},
                {"$set": {
                    "equipo_local.aficionados": total_local,
                    "equipo_visitante.aficionados": total_visita
                }}
            )
        except Exception:
            pass  # match_id inválido/inexistente: no debe tirar abajo el resto del cálculo ya aplicado

    return {
        "local": {"delta": detalle_local["delta"], "aficionados_totales": total_local},
        "visitante": {"delta": detalle_visita["delta"], "aficionados_totales": total_visita}
    }


def obtener_ranking_aficionados(limite: int = 250) -> list:
    """
    Selecciones ordenadas de MAYOR a MENOR por 'aficionados' -- independiente del ranking
    FIFA (se incluye 'rankin_fifa' solo como dato de referencia, no se usa para ordenar).
    Un solo query con sort a nivel de Mongo (no se trae todo a Python para ordenar ahí).
    """
    paises_coll = db["paises"]
    cursor = paises_coll.find(
        {},
        {"_id": 0, "id": 1, "nombre": 1, "bandera": 1, "aficionados": 1, "estadisticas.rankin": 1}
    ).sort("aficionados", -1).limit(limite)

    return [
        {
            "pais_id": p.get("id"),
            "nombre": p.get("nombre", "?"),
            "bandera": p.get("bandera"),
            "aficionados": p.get("aficionados", AFICIONADOS_INICIAL),
            "rankin_fifa": p.get("estadisticas", {}).get("rankin", 0)
        }
        for p in cursor
    ]


def obtener_historial_aficionados_pais(pais_id: int, limite: int = 50) -> list:
    """Evolución de aficionados de un país, más reciente primero -- fuente del historial pedido."""
    registros = db["historial_aficionados"].find({"pais_id": pais_id}).sort("created_at", -1).limit(limite)
    return [
        {
            "partido_id": r.get("partido_id"),
            "aficionados_ganados_perdidos": r.get("aficionados_ganados_perdidos", 0),
            "aficionados_totales_resultantes": r.get("aficionados_totales_resultantes", 0),
            "motivo": r.get("motivo", "?"),
            "created_at": r.get("created_at")
        }
        for r in registros
    ]
