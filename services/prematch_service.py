"""
Servicio de "Análisis Pre-Partido y Pronóstico de Clasificación" (Pre-Match Scouter).

Punto de entrada: analyze_pre_match_status(match_id).

Mapeo REAL de fases usado por esta app (verificado contra services/clasificacion_service.py,
services/international_service.py y services/juegos_service.py — no asumido):
  - Fases 1 a 6: eliminatorias por confederación, grupos de 2 a 10 equipos, ida y vuelta.
  - Fase 7:      fase de grupos del Mundial propiamente dicho (grupos de 4 equipos, 3 jornadas
                 porque a partir de la fase 7 'generar_partidos_fase' solo genera la ida).
  - Fases 8-13:  eliminación directa a partido único (16vos, 8vos, 4tos, semis, 3er puesto, final)
                 — confirmado también en
                 juegos_service.evaluar_tiempo_extra_grupo_dos_equipos ("A partir de la fase 8
                 los partidos son knockout a partido único").

NOTA: esto difiere de la numeración "Fase 8 = grupos / Fases 9-13 = knockout" que a veces se usa
informalmente; se implementó contra la numeración real del código (fase 7 = grupos, 8-13 =
knockout) para que el análisis salga correcto contra los datos reales de 'internacional'/'juegos'.

Manejo de "excepciones matemáticas": todas las fórmulas con denominadores variables (magic
number, probabilidad Elo) están explícitamente acotadas/protegidas contra división por cero,
overflow y grupos sin rivales (ver _probabilidad_victoria_elo y _determinar_estado_clasificacion).
"""
import re
import certifi
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
from schemas.prematch_schema import EstadoClasificacion
from services.clasificacion_service import obtener_tablas_posiciones_por_grupo

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

FASE_MUNDIAL_GRUPOS = 7
FASES_ELIMINACION_DIRECTA = {8, 9, 10, 11, 12, 13}


# ==========================================
# Reglas de clasificación por tamaño de grupo
# ==========================================
def _obtener_reglas_clasificacion_grupo(fase_id: int, cantidad_equipos: int) -> Dict[str, Any]:
    """
    Devuelve, según la fase y el tamaño real del grupo, cuántos puestos clasifican DIRECTO
    y cuáles quedan en zona de "posibilidades" (repechaje / mejor segundo / mejor tercero).
    Determina tanto el ESTADO_CLASIFICACION de cada equipo como el resaltado de la tabla.

    NOTA sobre una ambigüedad del enunciado de negocio: para grupos de 5-6 equipos en fases
    1-6, la regla se redactó como "Clasifican 1º, 2º y 3º con posibilidades" -- a diferencia
    de los otros tramos (3-4 equipos, 10 equipos), no se aclaró explícitamente cuál puesto es
    100% directo y cuáles son "con posibilidades". Se asumió 1º directo y 2º/3º con
    posibilidades, siguiendo el mismo patrón "1 directo + resto en zona de posibilidad" que
    tienen el resto de los tramos. Si la intención real era otra (ej. los 3 puestos sujetos a
    comparación entre grupos, ninguno 100% directo), ajustar acá.
    """
    if fase_id == FASE_MUNDIAL_GRUPOS:
        if cantidad_equipos == 4:
            return {"cupos_directos": 2, "posiciones_con_posibilidad": {3}}
        # Fallback conservador para tamaños de grupo no contemplados en la fase de grupos del Mundial.
        return {"cupos_directos": max(1, cantidad_equipos // 2), "posiciones_con_posibilidad": set()}

    if 1 <= fase_id <= 6:
        if cantidad_equipos <= 2:
            return {"cupos_directos": 1, "posiciones_con_posibilidad": set()}
        if cantidad_equipos in (3, 4):
            return {"cupos_directos": 1, "posiciones_con_posibilidad": {2}}
        if cantidad_equipos in (5, 6):
            return {"cupos_directos": 1, "posiciones_con_posibilidad": {2, 3}}
        if cantidad_equipos >= 10:
            return {"cupos_directos": 6, "posiciones_con_posibilidad": {7}}

    # Fallback: tamaño de grupo/fase sin regla explícita conocida -- solo el 1º directo, sin
    # zona de posibilidad, para no dejar el cálculo indefinido.
    return {"cupos_directos": 1, "posiciones_con_posibilidad": set()}


# ==========================================
# Probabilidad de victoria (comparativa H2H)
# ==========================================
def _probabilidad_victoria_elo(poder_local: float, poder_visitante: float) -> Tuple[float, float]:
    """
    Probabilidad de victoria aproximada vía la fórmula de "expected score" de Elo, usando
    'poder' (ver paises_service.actualizar_poder_y_rankin) como el rating de cada equipo.
    Es una referencia rápida de favoritismo para la ficha pre-partido, no reemplaza al motor
    de simulación real (services/simular_service.py).

    Protegida contra overflow (diferencias de poder extremas) y acotada a [1%, 99%] para que
    nunca se muestre una certeza absoluta (0% / 100%) de cara a un partido que no se jugó.
    """
    diferencia = poder_visitante - poder_local
    try:
        prob_local = 1.0 / (1.0 + 10 ** (diferencia / 400.0))
    except OverflowError:
        prob_local = 0.01 if diferencia > 0 else 0.99
    prob_local = max(0.01, min(0.99, prob_local))
    return round(prob_local * 100, 1), round((1 - prob_local) * 100, 1)


# ==========================================
# Estado de clasificación matemática
# ==========================================
def _determinar_estado_clasificacion(
    pais_id: int, analisis_por_equipo: Dict[int, dict], cupos_directos: int, total_cupos: int
) -> Tuple[EstadoClasificacion, Optional[int]]:
    """
    Heurística estándar de "matemáticas de clasificación" (la misma que usan la mayoría de los
    calculadores deportivos): compara el TECHO de cada equipo (puntos actuales + partidos
    restantes * 3) contra el PISO/TECHO de sus rivales directos. No es un solver combinatorio
    exhaustivo (que sería innecesariamente costoso para grupos de hasta 10 equipos con reglas
    de "mejores X" cruzadas entre grupos), pero da la clasificación correcta en el
    aplastante caso general y es conservadora en los bordes (nunca declara clasificado/eliminado
    de más).

    Devuelve (estado, puntos_para_calificar). 'puntos_para_calificar' es None cuando el estado
    ya quedó % definido (MATHEMATICALLY_QUALIFIED / ELIMINATED) y es el "magic number" estimado
    en caso contrario: cuántos puntos more le alcanzan al equipo para volverse inalcanzable por
    su principal amenaza (el rival con mejor techo), sin pasarse de lo que puede sumar como máximo.
    """
    equipo = analisis_por_equipo[pais_id]
    rivales = [r for pid, r in analisis_por_equipo.items() if pid != pais_id]

    if not rivales:
        # Grupo de 1 equipo (caso degenerado, no debería ocurrir en un torneo real) -- clasifica
        # directo por descarte, no hay contra quién comparar.
        return EstadoClasificacion.MATHEMATICALLY_QUALIFIED, None

    # ¿Cuántos rivales podrían, en su mejor caso, superar los puntos ACTUALES del equipo?
    rivales_que_podrian_superarlo = sum(1 for r in rivales if r["puntos_maximos"] > equipo["puntos"])
    # ¿Cuántos rivales YA tienen, hoy, más puntos que el TECHO del equipo (ni ganando todo lo alcanza)?
    rivales_ya_inalcanzables = sum(1 for r in rivales if r["puntos"] > equipo["puntos_maximos"])

    if rivales_que_podrian_superarlo < cupos_directos:
        return EstadoClasificacion.MATHEMATICALLY_QUALIFIED, None

    if rivales_ya_inalcanzables >= total_cupos:
        return EstadoClasificacion.ELIMINATED, None

    # Todavía en pelea: magic number aproximado respecto al rival con mejor techo (la principal
    # amenaza), acotado a lo máximo que el equipo puede sumar en lo que le queda.
    techo_maxima_amenaza = max(r["puntos_maximos"] for r in rivales)
    tope_propio = equipo["puntos_maximos"] - equipo["puntos"]
    puntos_para_calificar = max(0, min(techo_maxima_amenaza - equipo["puntos"] + 1, tope_propio))

    if equipo["posicion"] <= total_cupos:
        return EstadoClasificacion.DEPENDS_ON_SELF, puntos_para_calificar
    return EstadoClasificacion.NEEDS_OUTSIDE_RESULTS, puntos_para_calificar


# ==========================================
# Veredicto en texto (flavor text del "scouter")
# ==========================================
def _frase_equipo(equipo: dict) -> str:
    nombre = equipo["nombre"]
    estado = equipo["estado_clasificacion"]
    restantes = equipo["partidos_restantes"]
    necesarios = equipo["puntos_para_calificar"]

    if estado == EstadoClasificacion.KNOCKOUT_STAGE:
        return f"{nombre} juega su pase a la siguiente ronda a partido único"
    if estado == EstadoClasificacion.MATHEMATICALLY_QUALIFIED:
        return f"{nombre} ya está matemáticamente clasificado"
    if estado == EstadoClasificacion.ELIMINATED:
        return f"{nombre} está matemáticamente eliminado"

    if necesarios is not None:
        if necesarios <= 1:
            frase_necesidad = f"{nombre} necesita ganar o empatar para asegurar su lugar"
        elif restantes > 0 and necesarios >= restantes * 3:
            frase_necesidad = f"{nombre} está obligado a ganar todos los partidos que le quedan para tener chances"
        else:
            frase_necesidad = f"{nombre} está obligado a ganar para mantener esperanzas"
    else:
        frase_necesidad = f"{nombre} sigue con chances"

    if estado == EstadoClasificacion.NEEDS_OUTSIDE_RESULTS:
        frase_necesidad += ", y además depende de que otros resultados lo favorezcan"

    return frase_necesidad


def _generar_veredicto_scouter(home: dict, away: dict) -> str:
    frase_home = _frase_equipo(home)
    frase_away = _frase_equipo(away)
    return f"{frase_home[0].upper()}{frase_home[1:]}, mientras que {frase_away}."


# ==========================================
# Utilidades
# ==========================================
def _extraer_numero_jornada(jornada_str: Optional[str]) -> Optional[int]:
    if not jornada_str:
        return None
    encontrado = re.search(r"\d+", jornada_str)
    return int(encontrado.group()) if encontrado else None


# ==========================================
# Rama: fases de eliminación directa (8-13, partido único)
# ==========================================
def _analizar_eliminacion_directa(juego: dict, id_local: int, id_visita: int, mundial_id: Any) -> Dict[str, Any]:
    internacional_coll = db["internacional"]
    equipos = list(internacional_coll.find({"id": {"$in": [id_local, id_visita]}, "mundial_id": mundial_id}))
    datos_por_id = {e["id"]: e for e in equipos}

    equipo_local_juego = juego.get("equipo_local") or {}
    equipo_visita_juego = juego.get("equipo_visitante") or {}

    stats_local = (datos_por_id.get(id_local) or {}).get("estadisticas", {})
    stats_visita = (datos_por_id.get(id_visita) or {}).get("estadisticas", {})

    prob_local, prob_visita = _probabilidad_victoria_elo(stats_local.get("poder", 0), stats_visita.get("poder", 0))

    def _armar(pid, equipo_juego, stats, probabilidad) -> dict:
        return {
            "pais_id": pid,
            "nombre": equipo_juego.get("nombre", "?"),
            "bandera": equipo_juego.get("bandera"),
            "puntos": 0, "posicion": 0, "partidos_jugados": stats.get("juegos_jugados", 0),
            "partidos_restantes": 1, "puntos_maximos_alcanzables": 0,
            "estado_clasificacion": EstadoClasificacion.KNOCKOUT_STAGE,
            "puntos_para_calificar": None,
            "probabilidad_victoria_pct": probabilidad,
            "p_ofensiva": stats.get("p_ofensiva", 0), "p_defensiva": stats.get("p_defensiva", 0),
            "p_posesion": stats.get("p_posesion", 0), "poder": stats.get("poder", 0),
            "goles_favor": stats.get("goles_favor", 0), "goles_contra": stats.get("goles_contra", 0)
        }

    home = _armar(id_local, equipo_local_juego, stats_local, prob_local)
    away = _armar(id_visita, equipo_visita_juego, stats_visita, prob_visita)

    return {
        "match_id": str(juego["_id"]), "fase_id": juego.get("fase_id"), "grupo": juego.get("grupo"),
        "confederacion_id": juego.get("confederacion_id"), "cantidad_equipos_grupo": 2,
        "jornada_actual": None, "jornadas_totales": 1, "es_eliminacion_directa": True,
        "home_team_analysis": home, "away_team_analysis": away, "group_standings_summary": [],
        "scouter_verdict": _generar_veredicto_scouter(home, away)
    }


# ==========================================
# Rama: fases de grupos (1-7)
# ==========================================
def _analizar_fase_grupos(
    juego: dict, id_local: int, id_visita: int, fase_id: int, confederacion_id: int,
    mundial_id: Any, grupo: str
) -> Dict[str, Any]:
    if not grupo:
        raise ValueError("El partido no tiene un grupo asignado; no se puede calcular la tabla de posiciones.")

    # 1. Tabla oficial del grupo, con el MISMO criterio de desempate que usa el resto de la
    #    app (puntos -> diferencia de goles -> goles a favor -> poder, ver clasificacion_service).
    tablas = obtener_tablas_posiciones_por_grupo(db, fase_id, confederacion_id)
    _grupo = grupo.split()[-1]
    tabla_grupo = tablas.get(_grupo)
    if not tabla_grupo:
        raise ValueError(
            f"No hay datos de clasificación disponibles para el grupo '{grupo}' de la fase {fase_id} "
            f"(es posible que esta fase ya haya finalizado y los equipos ya se hayan movido de 'internacional')."
        )

    cantidad_equipos = len(tabla_grupo)
    reglas = _obtener_reglas_clasificacion_grupo(fase_id, cantidad_equipos)
    cupos_directos = reglas["cupos_directos"]
    posiciones_posibilidad = reglas["posiciones_con_posibilidad"]
    total_cupos = cupos_directos + len(posiciones_posibilidad)

    # 2. Partidos de TODO el grupo (jugados y por jugar) en una sola consulta, para sacar
    #    tanto las jornadas totales como los partidos restantes de cada equipo sin N+1 queries.
    juegos_coll = db["juegos"]
    partidos_grupo = list(juegos_coll.find(
        {"mundial_id": mundial_id, "fase_id": fase_id, "confederacion_id": confederacion_id, "grupo": grupo},
        {"jornada": 1, "estado": 1, "equipo_local.id": 1, "equipo_visitante.id": 1}
    ))
    jornadas_totales = len({p["jornada"] for p in partidos_grupo if p.get("jornada")}) or None

    partidos_restantes_por_equipo: Dict[int, int] = defaultdict(int)
    for p in partidos_grupo:
        if p.get("estado") == "finalizado":
            continue
        l_id = (p.get("equipo_local") or {}).get("id")
        v_id = (p.get("equipo_visitante") or {}).get("id")
        if l_id is not None:
            partidos_restantes_por_equipo[l_id] += 1
        if v_id is not None:
            partidos_restantes_por_equipo[v_id] += 1

    jornada_actual = _extraer_numero_jornada(juego.get("jornada"))

    # 3. Techo/piso de cada equipo del grupo, para poder comparar a cada uno contra sus rivales.
    analisis_por_equipo: Dict[int, dict] = {}
    for idx, fila in enumerate(tabla_grupo, start=1):
        pid = fila["pais_id"]
        restantes = partidos_restantes_por_equipo.get(pid, 0)
        puntos_actuales = fila["puntos"]
        analisis_por_equipo[pid] = {
            "posicion": idx, "puntos": puntos_actuales, "partidos_restantes": restantes,
            "puntos_maximos": puntos_actuales + restantes * 3,
            "partidos_jugados": fila.get("juegos_jugados", 0),
            "diferencia_goles": fila.get("diferencia_goles", 0),
            "nombre": fila.get("nombre", "?"), "bandera": fila.get("bandera")
        }

    for pid, info in analisis_por_equipo.items():
        estado, puntos_para_calificar = _determinar_estado_clasificacion(
            pid, analisis_por_equipo, cupos_directos, total_cupos
        )
        info["estado"] = estado
        info["puntos_para_calificar"] = puntos_para_calificar

    # 4. Estadísticas extra (p_ofensiva/p_defensiva/p_posesion/poder) para la comparativa H2H,
    #    en una sola consulta puntual sobre los 2 equipos del partido (no sobre todo el grupo).
    internacional_coll = db["internacional"]
    docs_h2h = {
        e["id"]: e for e in internacional_coll.find({"id": {"$in": [id_local, id_visita]}, "mundial_id": mundial_id})
    }

    def _armar_team_analysis(pid: int, probabilidad: float) -> dict:
        info = analisis_por_equipo.get(pid)
        if info is None:
            raise ValueError(f"El equipo id={pid} no aparece en la tabla del grupo '{grupo}'.")
        stats_extra = (docs_h2h.get(pid) or {}).get("estadisticas", {})
        return {
            "pais_id": pid, "nombre": info["nombre"], "bandera": info["bandera"],
            "puntos": info["puntos"], "posicion": info["posicion"],
            "partidos_jugados": info["partidos_jugados"], "partidos_restantes": info["partidos_restantes"],
            "puntos_maximos_alcanzables": info["puntos_maximos"],
            "estado_clasificacion": info["estado"], "puntos_para_calificar": info["puntos_para_calificar"],
            "probabilidad_victoria_pct": probabilidad,
            "p_ofensiva": stats_extra.get("p_ofensiva", 0), "p_defensiva": stats_extra.get("p_defensiva", 0),
            "p_posesion": stats_extra.get("p_posesion", 0), "poder": stats_extra.get("poder", 0),
            "goles_favor": stats_extra.get("goles_favor", 0), "goles_contra": stats_extra.get("goles_contra", 0)
        }

    poder_local = (docs_h2h.get(id_local) or {}).get("estadisticas", {}).get("poder", 0)
    poder_visita = (docs_h2h.get(id_visita) or {}).get("estadisticas", {}).get("poder", 0)
    prob_local, prob_visita = _probabilidad_victoria_elo(poder_local, poder_visita)

    home = _armar_team_analysis(id_local, prob_local)
    away = _armar_team_analysis(id_visita, prob_visita)

    # 5. Tabla resumida para el frontend, marcando la zona de cada puesto.
    standings_summary: List[dict] = []
    for pid, info in sorted(analisis_por_equipo.items(), key=lambda kv: kv[1]["posicion"]):
        posicion = info["posicion"]
        if posicion <= cupos_directos:
            zona = "DIRECTO"
        elif posicion in posiciones_posibilidad:
            zona = "POSIBILIDAD"
        else:
            zona = "ELIMINADO"
        standings_summary.append({
            "posicion": posicion, "pais_id": pid, "nombre": info["nombre"], "bandera": info["bandera"],
            "puntos": info["puntos"], "partidos_jugados": info["partidos_jugados"],
            "diferencia_goles": info["diferencia_goles"], "zona": zona,
            "es_equipo_analizado": pid in (id_local, id_visita)
        })

    return {
        "match_id": str(juego["_id"]), "fase_id": fase_id, "grupo": grupo, "confederacion_id": confederacion_id,
        "cantidad_equipos_grupo": cantidad_equipos, "jornada_actual": jornada_actual,
        "jornadas_totales": jornadas_totales, "es_eliminacion_directa": False,
        "home_team_analysis": home, "away_team_analysis": away,
        "group_standings_summary": standings_summary,
        "scouter_verdict": _generar_veredicto_scouter(home, away)
    }


# ==========================================
# Punto de entrada
# ==========================================
def analyze_pre_match_status(match_id: str) -> Dict[str, Any]:
    """
    Arma el análisis pre-partido completo para 'match_id' (id de 'juegos'): identifica los 2
    equipos, su grupo/fase, calcula el estado de clasificación matemática de cada uno (fases
    1-7) o el % de probabilidad de avanzar de ronda (fases 8-13), y una comparativa H2H.

    Lanza ValueError (que la ruta traduce a HTTP 404/400) ante cualquier dato insuficiente o
    inconsistente: match_id inválido, partido inexistente, o grupo sin datos de clasificación
    disponibles (fase ya completada y removida de 'internacional').
    """
    juegos_coll = db["juegos"]

    try:
        object_id = ObjectId(match_id)
    except (InvalidId, TypeError) as e:
        raise ValueError(f"'{match_id}' no es un id de partido válido.") from e

    juego = juegos_coll.find_one({"_id": object_id})
    if not juego:
        raise ValueError(f"No se encontró el partido '{match_id}'.")

    equipo_local = juego.get("equipo_local") or {}
    equipo_visitante = juego.get("equipo_visitante") or {}
    id_local = equipo_local.get("id")
    id_visita = equipo_visitante.get("id")
    fase_id = juego.get("fase_id")

    if id_local is None or id_visita is None or fase_id is None:
        raise ValueError("El partido no tiene los datos mínimos (equipos/fase) para el análisis.")

    if fase_id in FASES_ELIMINACION_DIRECTA:
        return _analizar_eliminacion_directa(juego, id_local, id_visita, juego.get("mundial_id"))

    return _analizar_fase_grupos(
        juego, id_local, id_visita, fase_id, juego.get("confederacion_id"),
        juego.get("mundial_id"), juego.get("grupo")
    )
