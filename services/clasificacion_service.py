
from services.juegos_service import es_fase_confederacion_completada
from services.ownership_service import procesar_bono_avance_fase
from bson import ObjectId
import pymongo

def obtener_tablas_posiciones_por_grupo(db, fase_id: int, confederacion_id: int) -> dict:
    """
    Agrupa los países por su campo 'grupo' y los ordena por el criterio de desempate oficial:
    Puntos -> Diferencia de Goles -> Goles a Favor -> Poder/Ranking.
    """
    collection_internacional = db['internacional']
    
    # 1. Obtener todos los países de la fase y confederación solicitada
    paises = list(collection_internacional.find({
        "fase_eliminatoria": fase_id,
        "confederacion_id": confederacion_id
    }))

    tablas = {}

    # 2. Agrupar países por la letra de su grupo
    for pais in paises:
        grupo = pais.get("grupo")
        if not grupo:
            continue
            
        if grupo not in tablas:
            tablas[grupo] = []
            
        stats = pais.get("estadisticas", {})
        
        # Mapeamos la estructura para el procesamiento
        tablas[grupo].append({
            "pais_id": pais.get("id"),
            "nombre": pais.get("nombre"),
            "bandera": pais.get("bandera"),
            "grupo": grupo,
            "puntos": stats.get("puntos", 0),
            "diferencia_goles": stats.get("diferencia_goles", 0),
            "goles_favor": stats.get("goles_favor", 0),
            "goles_contra": stats.get("goles_contra", 0),
            "juegos_jugados": stats.get("juegos_jugados", 0),
            "poder": stats.get("poder", 0)
        })

    # 3. Ordenar cada grupo según los criterios reglamentarios
    for grupo, lista_paises in tablas.items():
        tablas[grupo] = sorted(
            lista_paises,
            key=lambda x: (
                x["puntos"],
                x["diferencia_goles"],
                x["goles_favor"],
                x["poder"]  # Criterio final de desempate
            ),
            reverse=True
        )

    return tablas


def obtener_tabla_grupo_de_equipo(db, fase_id: int, confederacion_id: int, pais_id: int):
    """
    Devuelve (letra_grupo, equipos_ordenados) del grupo al que pertenece 'pais_id' dentro de
    fase_id/confederacion_id -- reutiliza obtener_tablas_posiciones_por_grupo (ya trae el orden
    reglamentario) y busca cuál de los grupos devueltos contiene a ese país, en vez de repetir
    la consulta a 'internacional'. (None, []) si no se encuentra (ej. fases de eliminación
    directa, que no tienen tabla de grupos).
    """
    grupos = obtener_tablas_posiciones_por_grupo(db, fase_id, confederacion_id)
    for letra, equipos in grupos.items():
        if any(equipo["pais_id"] == pais_id for equipo in equipos):
            return letra, equipos
    return None, []


def obtener_tabla_posiciones_general(db, fase_id: int, confederacion_id: int) -> list:
    """
    Obtiene una tabla única para confederaciones como CONMEBOL.
    """
    collection_internacional = db['internacional']
    
    paises = list(collection_internacional.find({
        "fase_eliminatoria": fase_id,
        "confederacion_id": confederacion_id
    }))

    tabla_general = []
    for pais in paises:
        stats = pais.get("estadisticas", {})
        tabla_general.append({
            "pais_id": pais.get("id"),
            "nombre": pais.get("nombre"),
            "puntos": stats.get("puntos", 0),
            "diferencia_goles": stats.get("diferencia_goles", 0),
            "goles_favor": stats.get("goles_favor", 0),
            "poder": stats.get("poder", 0)
        })

    # Orden general
    return sorted(
        tabla_general,
        key=lambda x: (
            x["puntos"],
            x["diferencia_goles"],
            x["goles_favor"],
            x["poder"]
        ),
        reverse=True
    )

# funciones para procesar la clasificación de los equipos según la fase y confederación
def validar_fase_confederacion_completada(db, juego_id: str):
    # Obtener fase_id y confederacion_id del partido simulado
    juego_info = db['juegos'].find_one({"_id": ObjectId(juego_id)})
    fase_id = juego_info.get("fase_id")
    confederacion_id = juego_info.get("confederacion_id")

    fase_completada = False
    # Verificar si fue el último partido pendiente de la fase/confederación
    if es_fase_confederacion_completada(db, fase_id, confederacion_id):
        fase_completada = True
        if fase_id == 1:
            procesar_clasificacion_fase_1(db, confederacion_id)
        elif fase_id == 2:
            procesar_clasificacion_fase_2(db, confederacion_id)
        elif fase_id == 3:
            procesar_clasificacion_fase_3(db, confederacion_id)
        elif fase_id == 4:
            procesar_clasificacion_fase_4(db, confederacion_id)
        elif fase_id == 5:
            procesar_clasificacion_fase_5(db, confederacion_id)
        elif fase_id == 6:
            procesar_clasificacion_fase_6(db, confederacion_id)
        elif fase_id == 7:
            procesar_clasificacion_fase_7(db, confederacion_id)
        elif fase_id >= 8:
            # procesar_clasificacion_fase ya maneja genéricamente 8 (16vos) a 13 (Final) --
            # antes este 'elif' solo disparaba para fase_id == 8, así que ningún ganador de
            # 8vos/4tos/semis/3er puesto/final quedaba marcado con su estado
            # "CLASIFICADO_<ronda>_<grupo>", y crear_siguiente_fase() (mundial_service.py)
            # nunca encontraba países para poblar la ronda siguiente -- el torneo se quedaba
            # sin partidos pendientes en silencio, sin ninguna excepción, apenas terminaba
            # 8vos de Final.
            procesar_clasificacion_fase(db, confederacion_id, fase_id)
        # copiar el estado y las estadisticas de los paises que jugaron en la fase de la coleccion 'internacional' a la coleccion 'paises'
        copiar_estado_y_estadisticas_a_paises(db, fase_id, confederacion_id)
    
    return fase_completada

# función para verificar si todos los partidos de una fase y confederación han sido jugados
def procesar_clasificacion_fase_1(db, confederacion_id: int):
    """
    Procesa el avance/eliminación de los equipos de Fase 1 hacia la Fase 2 o Mundial
    según la confederación correspondiente.
    """
    print(f"🏆 Procesando clasificación final de Fase 1 para Confederación ID: {confederacion_id}")
    actualizaciones = []

    # =========================================================================
    # UEFA (ID: 1) - 12 Grupos
    # =========================================================================
    if confederacion_id == 1:
        # 1. Obtener tablas de posiciones de cada grupo
        tablas_grupos = obtener_tablas_posiciones_por_grupo(db, fase_id=1, confederacion_id=1)

        primeros = []
        segundos = []
        terceros = []

        for grupo_id, tabla in tablas_grupos.items():
            if len(tabla) >= 1: primeros.append(tabla[0])
            if len(tabla) >= 2: segundos.append(tabla[1])
            if len(tabla) >= 3: terceros.append(tabla[2])
            # El resto (4to hacia abajo) quedan eliminados
            for rest in tabla[3:]:
                actualizaciones.append((rest["pais_id"], "ELIMINADO_FASE_1"))

        # Avanzan directo al Mundial (12 primeros lugares)
        for p in primeros:
            actualizaciones.append((p["pais_id"], "CALIFICADO_MUNDIAL"))

        # Pasan a Fase 2 (12 segundos lugares)
        for s in segundos:
            actualizaciones.append((s["pais_id"], "CLASIFICADO_FASE_2"))

        # Criterio de desempate para mejores 3° lugares (Puntos -> Dif. Goles -> Goles Favor)
        terceros_ordenados = ordenar_posiciones_globales(terceros)

        # 4 mejores terceros pasan a Fase 2, el resto se elimina
        for i, t in enumerate(terceros_ordenados):
            if i < 4:
                actualizaciones.append((t["pais_id"], "CLASIFICADO_FASE_2"))
            else:
                actualizaciones.append((t["pais_id"], "ELIMINADO_FASE_1"))

    # =========================================================================
    # CONMEBOL (ID: 2) - Tabla Única
    # =========================================================================
    elif confederacion_id == 2:
        tabla_unica = obtener_tabla_posiciones_general(db, fase_id=1, confederacion_id=2)

        for i, equipo in enumerate(tabla_unica):
            posicion = i + 1
            if posicion <= 6:
                # 1° al 6° -> Clasificación directa al Mundial
                actualizaciones.append((equipo["pais_id"], "CALIFICADO_MUNDIAL"))
            elif posicion == 7:
                # 7° -> Repechaje Internacional
                actualizaciones.append((equipo["pais_id"], "REPECHAJE_INTERNACIONAL"))
            else:
                # Resto -> Eliminados
                actualizaciones.append((equipo["pais_id"], "ELIMINADO_FASE_1"))

    # =========================================================================
    # CONCACAF (ID: 3), OFC (ID: 5), AFC (ID: 6) - Eliminatorias de 2 equipos
    # =========================================================================
    elif confederacion_id in [3, 5, 6]:
        # En estos formatos de 2 equipos, califica quien acumuló más goles globales en sus 2 partidos
        grupos_parejas = db['juegos'].distinct("grupo", {"fase_id": 1, "confederacion_id": confederacion_id})

        for grupo in grupos_parejas:
            ganador_id, perdedor_id = resolver_eliminatoria_dos_equipos(db, fase_id=1, grupo=grupo, confederacion_id=confederacion_id)

            if ganador_id:
                actualizaciones.append((ganador_id, "CLASIFICADO_FASE_2"))
            if perdedor_id:
                actualizaciones.append((perdedor_id, "ELIMINADO_FASE_1"))

    # =========================================================================
    # CAF (ID: 4) - 9 Grupos
    # =========================================================================
    elif confederacion_id == 4:
        tablas_grupos = obtener_tablas_posiciones_por_grupo(db, fase_id=1, confederacion_id=4)

        primeros = []
        segundos = []

        for grupo_id, tabla in tablas_grupos.items():
            if len(tabla) >= 1: primeros.append(tabla[0])
            if len(tabla) >= 2: segundos.append(tabla[1])
            # Eliminar 3° en adelante
            for rest in tabla[2:]:
                actualizaciones.append((rest["pais_id"], "ELIMINADO_FASE_1"))

        # 1.° lugar de cada grupo -> Boleto directo al Mundial
        for p in primeros:
            actualizaciones.append((p["pais_id"], "CALIFICADO_MUNDIAL"))

        # Ordenar los segundos lugares globales para obtener los 4 mejores
        segundos_ordenados = ordenar_posiciones_globales(segundos)

        for i, s in enumerate(segundos_ordenados):
            if i < 4:
                actualizaciones.append((s["pais_id"], "CLASIFICADO_FASE_2"))
            else:
                actualizaciones.append((s["pais_id"], "ELIMINADO_FASE_1"))

    actualizar_estatus_paises_bulk(db, actualizaciones)


def procesar_clasificacion_fase_2(db, confederacion_id: int):
    """
    Procesa el avance/eliminación de los equipos de Fase 2 hacia la Fase 3 o Mundial
    según la confederación correspondiente.
    """
    fase_id = 2
    print(f"🏆 Procesando clasificación final de Fase 2 para Confederación ID: {confederacion_id}")
    actualizaciones = []

    # =========================================================================
    # UEFA (ID: 1) - 4 Grupos
    # =========================================================================
    if confederacion_id == 1:
        # 1. Obtener tablas de posiciones de cada grupo
        tablas_grupos = obtener_tablas_posiciones_por_grupo(db, fase_id=fase_id, confederacion_id=confederacion_id)

        primeros = []

        for grupo_id, tabla in tablas_grupos.items():
            if len(tabla) >= 1: primeros.append(tabla[0])
            # El resto (2do hacia abajo) quedan eliminados
            for rest in tabla[1:]:
                actualizaciones.append((rest["pais_id"], "ELIMINADO_FASE_2"))

        # Avanzan directo al Mundial (4 primeros lugares)
        for p in primeros:
            actualizaciones.append((p["pais_id"], "CALIFICADO_MUNDIAL"))

    # =========================================================================
    # CAF (ID: 4) - Eliminatorias de 2 equipos
    # =========================================================================
    elif confederacion_id in [4]:
        # En estos formatos de 2 equipos, califica quien acumuló más goles globales en sus 2 partidos
        grupos_parejas = db['juegos'].distinct("grupo", {"fase_id": fase_id, "confederacion_id": confederacion_id})

        for grupo in grupos_parejas:
            ganador_id, perdedor_id = resolver_eliminatoria_dos_equipos(db, fase_id=fase_id, grupo=grupo, confederacion_id=confederacion_id)

            if ganador_id:
                actualizaciones.append((ganador_id, "CLASIFICADO_FASE_3"))
            if perdedor_id:
                actualizaciones.append((perdedor_id, "ELIMINADO_FASE_2"))

    # =========================================================================
    # CONCACAF (ID: 3) - 6 Grupos, OFC (ID: 5) - 2 Grupos, AFC (ID: 6) - 9 Grupos
    # =========================================================================
    elif confederacion_id in [3,5,6]:
        tablas_grupos = obtener_tablas_posiciones_por_grupo(db, fase_id=fase_id, confederacion_id=confederacion_id)

        primeros = []
        segundos = []

        for grupo_id, tabla in tablas_grupos.items():
            if len(tabla) >= 1: primeros.append(tabla[0])
            if len(tabla) >= 2: segundos.append(tabla[1])
            # Eliminar 3° en adelante
            for rest in tabla[2:]:
                actualizaciones.append((rest["pais_id"], "ELIMINADO_FASE_2"))

        # 1.° lugar de cada grupo -> Boleto a fase 3
        for p in primeros:
            actualizaciones.append((p["pais_id"], "CLASIFICADO_FASE_3"))

        # 2.° lugar de cada grupo -> Boleto a fase 3
        for p in segundos:
            actualizaciones.append((p["pais_id"], "CLASIFICADO_FASE_3"))

    actualizar_estatus_paises_bulk(db, actualizaciones)


def procesar_clasificacion_fase_3(db, confederacion_id: int):
    """
    Procesa el avance/eliminación de los equipos de Fase 3 hacia la Fase 4 o Mundial
    según la confederación correspondiente.
    """
    fase_id = 3
    print(f"🏆 Procesando clasificación final de Fase 3 para Confederación ID: {confederacion_id}")
    actualizaciones = []

    # =========================================================================
    # CONCACAF (ID: 3) - Eliminatoria 3 Grupos
    # =========================================================================
    if confederacion_id == 3:
        # 1. Obtener tablas de posiciones de cada grupo
        tablas_grupos = obtener_tablas_posiciones_por_grupo(db, fase_id=fase_id, confederacion_id=confederacion_id)

        primeros = []
        segundos = []
        terceros = []

        for grupo_id, tabla in tablas_grupos.items():
            if len(tabla) >= 1: primeros.append(tabla[0])
            if len(tabla) >= 2: segundos.append(tabla[1])
            if len(tabla) >= 3: terceros.append(tabla[2])
            # El resto (4to hacia abajo) quedan eliminados
            for rest in tabla[3:]:
                actualizaciones.append((rest["pais_id"], "ELIMINADO_FASE_3"))

        # Avanzan directo al Mundial (12 primeros lugares)
        for p in primeros:
            actualizaciones.append((p["pais_id"], "CALIFICADO_MUNDIAL"))

        # Pasan a Fase 2 (12 segundos lugares)
        for s in segundos:
            actualizaciones.append((s["pais_id"], "CALIFICADO_MUNDIAL"))

        # Criterio de desempate para mejores 3° lugares (Puntos -> Dif. Goles -> Goles Favor)
        terceros_ordenados = ordenar_posiciones_globales(terceros)

        # 2 mejores terceros pasan a Fase 2, el resto se elimina
        for i, t in enumerate(terceros_ordenados):
            if i < 2:
                actualizaciones.append((t["pais_id"], "REPECHAJE_INTERNACIONAL"))
            else:
                actualizaciones.append((t["pais_id"], "ELIMINADO_FASE_3"))

    # =========================================================================
    # CAF (ID: 4), OFC (ID: 5) - Eliminatorias de 2 equipos
    # =========================================================================
    elif confederacion_id in [4,5]:
        # En estos formatos de 2 equipos, califica quien acumuló más goles globales en sus 2 partidos
        grupos_parejas = db['juegos'].distinct("grupo", {"fase_id": fase_id, "confederacion_id": confederacion_id})

        for grupo in grupos_parejas:
            ganador_id, perdedor_id = resolver_eliminatoria_dos_equipos(db, fase_id=fase_id, grupo=grupo, confederacion_id=confederacion_id)

            if ganador_id:
                estatus = "REPECHAJE_INTERNACIONAL" if confederacion_id == 4 else "CLASIFICADO_FASE_4"
                actualizaciones.append((ganador_id, estatus))
            if perdedor_id:
                actualizaciones.append((perdedor_id, "ELIMINADO_FASE_3"))

    # =========================================================================
    # AFC (ID: 6) - 3 Grupos
    # =========================================================================
    elif confederacion_id == 6:
        tablas_grupos = obtener_tablas_posiciones_por_grupo(db, fase_id=fase_id, confederacion_id=confederacion_id)

        primeros = []
        segundos = []
        terceros = []
        cuartos = []

        for grupo_id, tabla in tablas_grupos.items():
            if len(tabla) >= 1: primeros.append(tabla[0])
            if len(tabla) >= 2: segundos.append(tabla[1])
            if len(tabla) >= 3: terceros.append(tabla[2])
            if len(tabla) >= 4: cuartos.append(tabla[3])
            # Eliminar 3° en adelante
            for rest in tabla[4:]:
                actualizaciones.append((rest["pais_id"], "ELIMINADO_FASE_3"))

        # 1.° lugar de cada grupo -> Boleto al Mundial
        for p in primeros:
            actualizaciones.append((p["pais_id"], "CALIFICADO_MUNDIAL"))

        # 2.° lugar de cada grupo -> Boleto al Mundial
        for p in segundos:
            actualizaciones.append((p["pais_id"], "CALIFICADO_MUNDIAL"))

        # 3.° lugar de cada grupo -> Boleto a fase 4
        for p in terceros:
            actualizaciones.append((p["pais_id"], "CLASIFICADO_FASE_4"))

        # 4.° lugar de cada grupo -> Boleto a fase 4
        for p in cuartos:
            actualizaciones.append((p["pais_id"], "CLASIFICADO_FASE_4"))

    actualizar_estatus_paises_bulk(db, actualizaciones)

# funcion para obtener clasificados de la fase 4
def procesar_clasificacion_fase_4(db, confederacion_id: int):
    """
    Procesa el avance/eliminación de los equipos de Fase 4 hacia la Fase 5 o Mundial
    según la confederación correspondiente.
    """
    fase_id = 4
    print(f"🏆 Procesando clasificación final de Fase 4 para Confederación ID: {confederacion_id}")
    actualizaciones = []

    # =========================================================================
    # CONCACAF (ID: 3) - Eliminatoria 3 Grupos
    # =========================================================================
    if confederacion_id == 6:
        # 1. Obtener tablas de posiciones de cada grupo
        tablas_grupos = obtener_tablas_posiciones_por_grupo(db, fase_id=fase_id, confederacion_id=confederacion_id)

        primeros = []
        segundos = []

        for grupo_id, tabla in tablas_grupos.items():
            if len(tabla) >= 1: primeros.append(tabla[0])
            if len(tabla) >= 2: segundos.append(tabla[1])
            # El resto (4to hacia abajo) quedan eliminados
            for rest in tabla[2:]:
                actualizaciones.append((rest["pais_id"], "ELIMINADO_FASE_4"))

        # Avanzan directo al Mundial (12 primeros lugares)
        for p in primeros:
            actualizaciones.append((p["pais_id"], "CALIFICADO_MUNDIAL"))

        # Pasan a Fase 2 (12 segundos lugares)
        for s in segundos:
            actualizaciones.append((s["pais_id"], "CLASIFICADO_FASE_5"))


    # =========================================================================
    # OFC (ID: 5) - Eliminatorias de 2 equipos
    # =========================================================================
    elif confederacion_id == 5:
        # En estos formatos de 2 equipos, califica quien acumuló más goles globales en sus 2 partidos
        grupos_parejas = db['juegos'].distinct("grupo", {"fase_id": fase_id, "confederacion_id": confederacion_id})

        for grupo in grupos_parejas:
            ganador_id, perdedor_id = resolver_eliminatoria_dos_equipos(db, fase_id=fase_id, grupo=grupo, confederacion_id=confederacion_id)

            if ganador_id:
                actualizaciones.append((ganador_id, "CALIFICADO_MUNDIAL"))
            if perdedor_id:
                actualizaciones.append((perdedor_id, "REPECHAJE_INTERNACIONAL"))

    actualizar_estatus_paises_bulk(db, actualizaciones)
                
# funcion para obtener clasificados de la fase 5
def procesar_clasificacion_fase_5(db, confederacion_id: int):
    """
    Procesa el avance/eliminación de los equipos de Fase 5 hacia el Mundial
    según la confederación correspondiente.
    """
    fase_id = 5
    print(f"🏆 Procesando clasificación final de Fase 5 para Confederación ID: {confederacion_id}")
    actualizaciones = []

    # =========================================================================
    # AFC (ID: 6) - Eliminatorias de 2 equipos
    # =========================================================================
    if confederacion_id == 6:
        # En estos formatos de 2 equipos, califica quien acumuló más goles globales en sus 2 partidos
        grupos_parejas = db['juegos'].distinct("grupo", {"fase_id": fase_id, "confederacion_id": confederacion_id})

        for grupo in grupos_parejas:
            ganador_id, perdedor_id = resolver_eliminatoria_dos_equipos(db, fase_id=fase_id, grupo=grupo, confederacion_id=confederacion_id)

            if ganador_id:
                actualizaciones.append((ganador_id, "REPECHAJE_INTERNACIONAL"))
            if perdedor_id:
                actualizaciones.append((perdedor_id, "ELIMINADO_FASE_5"))

    actualizar_estatus_paises_bulk(db, actualizaciones)


# funcion para obtener clasificados de la fase 6
def procesar_clasificacion_fase_6(db, confederacion_id: int):
    """
    Procesa el avance/eliminación de los equipos de Fase 5 hacia el Mundial
    según la confederación correspondiente.
    """
    fase_id = 6
    print(f"🏆 Procesando clasificación final de Fase 6 para Confederación ID: {confederacion_id}")
    actualizaciones = []

    # =========================================================================
    # REPECHAJE (ID: 7) - Eliminatorias de 3 equipos
    # =========================================================================
    if confederacion_id == 7:
        # 1. Obtener tablas de posiciones de cada grupo
        tablas_grupos = obtener_tablas_posiciones_por_grupo(db, fase_id=fase_id, confederacion_id=confederacion_id)

        primeros = []

        for grupo_id, tabla in tablas_grupos.items():
            if len(tabla) >= 1: primeros.append(tabla[0])
            # El resto (4to hacia abajo) quedan eliminados
            for rest in tabla[1:]:
                actualizaciones.append((rest["pais_id"], "ELIMINADO_REPECHAJE"))

        # Avanzan directo al Mundial (12 primeros lugares)
        for p in primeros:
            actualizaciones.append((p["pais_id"], "CALIFICADO_MUNDIAL"))

    actualizar_estatus_paises_bulk(db, actualizaciones)


# funcion para obtener clasificados de la fase 6
def procesar_clasificacion_fase_7(db, confederacion_id: int):
    """
    Procesa el avance/eliminación de los equipos de Fase 7 hacia el Mundial
    según la confederación correspondiente.
    """
    fase_id = 7
    print(f"🏆 Procesando clasificación final de Fase 7 para Confederación ID: {confederacion_id}")
    actualizaciones = []

    # =========================================================================
    # MUNDIAL (ID: 8) - Eliminatorias de 4 equipos
    # =========================================================================
    if confederacion_id == 8:
        # 1. Obtener tablas de posiciones de cada grupo
        tablas_grupos = obtener_tablas_posiciones_por_grupo(db, fase_id=fase_id, confederacion_id=confederacion_id)

        primeros = []
        segundos = []
        terceros = []

        for grupo_id, tabla in tablas_grupos.items():
            if len(tabla) >= 1: primeros.append(tabla[0])
            if len(tabla) >= 2: segundos.append(tabla[1])
            if len(tabla) >= 3: terceros.append(tabla[2])
            # El resto (4to hacia abajo) quedan eliminados
            for rest in tabla[3:]:
                actualizaciones.append((rest["pais_id"], "ELIMINADO_FASE_GRUPOS"))

        # Avanzan directo al Mundial (12 primeros lugares)
        for p in primeros:
            actualizaciones.append((p["pais_id"], "CLASIFICADO_16VOS_1"))

        # Pasan a Fase 2 (12 segundos lugares)
        for s in segundos:
            actualizaciones.append((s["pais_id"], "CLASIFICADO_16VOS_2"))

        # Criterio de desempate para mejores 3° lugares (Puntos -> Dif. Goles -> Goles Favor)
        terceros_ordenados = ordenar_posiciones_globales(terceros)

        # 8 mejores terceros pasan a Fase 2, el resto se elimina
        for i, t in enumerate(terceros_ordenados):
            if i < 8:
                actualizaciones.append((t["pais_id"], "CLASIFICADO_16VOS_3"))
            else:
                actualizaciones.append((t["pais_id"], "ELIMINADO_FASE_GRUPOS"))

    actualizar_estatus_paises_bulk(db, actualizaciones)


def procesar_clasificacion_fase(db, confederacion_id: int, fase_id: int):
    """
    Procesa el avance/eliminación de los equipos de Fase 8 hacia 8vos)
    según la confederación correspondiente.
    """
    print(f"🏆 Procesando clasificación final de Fase {fase_id} para Confederación ID: {confederacion_id}")
    actualizaciones = []

    # =========================================================================
    # MUNDIAL (ID: 8) - Eliminatorias de 2 equipos
    # =========================================================================
    if confederacion_id == 8:
        # En estos formatos de 2 equipos, califica quien acumuló más goles globales en sus 2 partidos
        grupos_parejas = db['juegos'].distinct("grupo", {"fase_id": fase_id, "confederacion_id": confederacion_id})

        for grupo in grupos_parejas:
            ganador_id, perdedor_id = resolver_eliminatoria_dos_equipos(db, fase_id=fase_id, grupo=grupo, confederacion_id=confederacion_id)

            _grupo = grupo.replace("Grupo ", "")

            if fase_id == 8:
                status_ganador = "CLASIFICADO_8VOS"
                status_perdedor = "ELIMINADO_16VOS"
            elif fase_id == 9:
                status_ganador = "CLASIFICADO_4TOS"
                status_perdedor = "ELIMINADO_8VOS"
            elif fase_id == 10:
                status_ganador = "CLASIFICADO_SEMIS"
                status_perdedor = "ELIMINADO_4TOS"
            elif fase_id == 11:
                status_ganador = "CLASIFICADO_FINAL"
                status_perdedor = f"CLASIFICADO_3ER_{_grupo}"
            elif fase_id == 12:
                status_ganador = "GANADOR_3ER_LUGAR"
                status_perdedor = "GANADOR_4TO_LUGAR"
            elif fase_id == 13:
                status_ganador = "GANADOR_COPA_MUNDIAL"
                status_perdedor = "GANADOR_SUBCAMPEON"

            if ganador_id:
                actualizaciones.append((ganador_id, f"{status_ganador}_{_grupo}"))
            if perdedor_id:
                actualizaciones.append((perdedor_id, status_perdedor))

    actualizar_estatus_paises_bulk(db, actualizaciones)



# función para resolver eliminatorias de 2 equipos en confederaciones como CONCACAF, OFC y AFC
def resolver_eliminatoria_dos_equipos(db, fase_id: int, grupo: str, confederacion_id: int):
    """
    Suma el marcador global entre 2 equipos. Si empatan en goles globales,
    evalúa quién ganó la tanda de penaltis en el partido de vuelta.
    """
    juegos = list(db['juegos'].find({"fase_id": fase_id, "grupo": grupo, "confederacion_id": confederacion_id}))
    if len(juegos) < 2 and fase_id < 8:
        return None, None

    # Obtener los IDs de ambos países participantes
    id_equipo_a = juegos[0]["equipo_local"]["id"]
    id_equipo_b = juegos[0]["equipo_visitante"]["id"]
    
    # return id_equipo_b, id_equipo_a

    goles_a = 0
    goles_b = 0
    penaltis_ganador = None

    for j in juegos:
        # Suma de goles de A
        if j["equipo_local"]["id"] == id_equipo_a: goles_a += j.get("resultado").get("goles_local", 0)
        if j["equipo_visitante"]["id"] == id_equipo_a: goles_a += j.get("resultado").get("goles_visitante", 0)

        # Suma de goles de B
        if j["equipo_local"]["id"] == id_equipo_b: goles_b += j.get("resultado").get("goles_local", 0)
        if j["equipo_visitante"]["id"] == id_equipo_b: goles_b += j.get("resultado").get("goles_visitante", 0)

        # Si hubo tanda de penaltis en la vuelta
        if j.get("resultado").get("penaltis_local") is not None and j.get("resultado").get("penaltis_visitante") is not None:
            if j["resultado"]["penaltis_local"] > j["resultado"]["penaltis_visitante"]:
                penaltis_ganador = j["equipo_local"]["id"]
            else:
                penaltis_ganador = j["equipo_visitante"]["id"]

    # Definir ganador y perdedor
    if goles_a > goles_b:
        return id_equipo_a, id_equipo_b
    elif goles_b > goles_a:
        return id_equipo_b, id_equipo_a
    else:
        # Si empataron globalmente, avanza el ganador de los penaltis
        if penaltis_ganador == id_equipo_a:
            return id_equipo_a, id_equipo_b
        else:
            return id_equipo_b, id_equipo_a

# función para ordenar posiciones globales según criterios de desempate
def ordenar_posiciones_globales(lista_posiciones):
    """Ordena equipos por Puntos -> Diferencia de Goles -> Goles a Favor"""
    return sorted(
        lista_posiciones, 
        key=lambda x: (x.get("puntos", 0), x.get("diferencia_goles", 0), x.get("goles_favor", 0)), 
        reverse=True
    )

# función para actualizar en batch el estatus de varios países en la base de datos
def actualizar_estatus_paises_bulk(db, actualizaciones: list):
    """
    Actualiza en un solo bulk_write la condición final/estatus de varios países en
    'internacional', en vez de un update_one por país. `actualizaciones` es una lista
    de tuplas (pais_id, estatus).

    Este es también el único punto por donde pasan TODOS los cambios de
    estado de avance/eliminación de fase (venga de un formato de grupos o de
    eliminatoria a 2 equipos), así que es donde se dispara el bono de
    clasificación del módulo de Dueño de Selecciones (+300 pts si el país
    avanzó y tiene dueño) — ver services/ownership_service.py.
    """
    if not actualizaciones:
        return

    operaciones = [
        pymongo.UpdateOne({"id": pais_id}, {"$set": {"estado": estatus}})
        for pais_id, estatus in actualizaciones
    ]
    db['internacional'].bulk_write(operaciones)

    for pais_id, estatus in actualizaciones:
        try:
            procesar_bono_avance_fase(pais_id, estatus)
        except Exception as e:
            print(f"⚠️ Error al procesar bono de avance de fase para país {pais_id}: {e}")

# función para copiar el estado y las estadísticas de los países de la colección 'internacional' a la colección 'paises'
def copiar_estado_y_estadisticas_a_paises(db, fase_id: int, confederacion_id: int):
    """
    Copia el estado y las estadísticas de los países que jugaron en la fase
    de la colección 'internacional' a la colección 'paises'.
    """
    campos_sumar = {
        "puntos",
        "juegos_jugados",
        "juegos_ganados",
        "juegos_empatados",
        "juegos_perdidos",
        "goles_favor",
        "goles_contra",
        "diferencia_goles"
    }

    paises_internacional = list(db['internacional'].find({
        "fase_eliminatoria": fase_id,
        "confederacion_id": confederacion_id
    }))

    operaciones_paises = []
    paises_historial = []

    for pais in paises_internacional:
        stats = pais.get("estadisticas", {})

        # Diccionarios de actualización para MongoDB
        inc_updates = {}
        set_updates = {
            "estado": pais.get("estado", "")
        }

        # Clasificar cada subcampo de estadísticas
        for clave, valor in stats.items():
            if clave in campos_sumar:
                inc_updates[f"estadisticas.{clave}"] = valor
            else:
                set_updates[f"estadisticas.{clave}"] = valor

        # Construir la consulta de actualización dinámica
        update_query = {"$set": set_updates}
        if inc_updates:
            update_query["$inc"] = inc_updates

        operaciones_paises.append(pymongo.UpdateOne({"id": pais["id"]}, update_query))

        # Preparar el estado final para guardarlo en la colección 'historial'
        del pais["_id"]
        paises_historial.append(pais)

    # Ejecutar en batch: un bulk_write para 'paises' y un insert_many para 'historial'
    if operaciones_paises:
        db['paises'].bulk_write(operaciones_paises)
    if paises_historial:
        db['historial'].insert_many(paises_historial)

# validamos si esta el equipo anfitrion entre los calificados
def validacion_equipo_anfitrion(db, mundial_id: int):
    # 1. Asegurar que mundial_id sea ObjectId si viene como string
    if isinstance(mundial_id, str):
        mundial_id = ObjectId(mundial_id)
    
    mundial = db['mundiales'].find_one({"_id": mundial_id})
    if not mundial:
        return {"status": "error", "message": "Mundial no encontrado"}    
    
    # obtiene el id del pais sede
    sede_id = mundial["pais_id"]
    
    # 2. Verificar si el país sede ya está calificado
    anfitrion = db['paises'].find_one({"id": sede_id, "estado": "CALIFICADO_MUNDIAL"})

    if anfitrion: 
        print("Anfitrion calificado")
    else: # No esta calificado, se reemplaza por un pais del ultimo lugar calificado
        pais_sede = db['paises'].find_one({"id": sede_id})
        if not pais_sede:
            return {"status": "error", "message": "País sede no encontrado"}
    
        confederacion_sede_id = pais_sede["confederacion_id"]
    
        # obtener de la coleccion 'paises' los paises de la confederacion_saede_id, con estado 'CALIFICADO_MUNDIAL' ordenados por el campo estadisticas.rankin
        paises_confederacion = list(db['paises'].find({"confederacion_id": confederacion_sede_id, "estado": "CALIFICADO_MUNDIAL"}).sort("estadisticas.rankin", pymongo.DESCENDING))
        
        # el pais con el rankin mas bajo queda eliminado de la coleccion con un update
        pais_bajo_id = paises_confederacion[0]["id"]
        db['paises'].update_one({"id": pais_bajo_id}, {"$set": {"estado": "ELIMINADO_ANFITRION"}})
        
        print(f"Pais eliminado: {pais_bajo_id}, confederacion: {confederacion_sede_id}")

        
    # se actualiza el pais anfitrion como parter del mundial        
    db['paises'].update_one({"id": sede_id}, {"$set": {"estado": "CALIFICADO_MUNDIAL_ANFITRION"}})
        
    return {"status": "ok", "message": "Anfitrión calificado y cupo reajustado"}
    
    
    
    
    
    