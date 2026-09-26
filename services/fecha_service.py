from datetime import datetime, timedelta
from itertools import zip_longest
import random
from typing import Dict, Any, List, Optional
from pymongo.database import Database
from pymongo import UpdateOne
from bson.objectid import ObjectId


# Diccionario con el intervalo de días entre jornadas según la confederación -- pensado como el
# ritmo real del calendario de clasificación (partidos cada 1-3 meses). Para confederacion_id 7/8
# (fases de eliminación directa y fase de grupos del propio Mundial, ver crear_siguiente_fase en
# mundial_service.py) el ritmo real es de días, no meses, así que estos valores son mucho más
# chicos -- pero son solo un PISO: ver _intervalo_minimo_para_jornada más abajo, que los eleva si
# hace falta para que una jornada no se pise con la siguiente.
INTERVALO_DIAS_POR_CONFEDERACION = {
    1: 74,  # confederacion_id = 1 -> 74 días
    2: 62,  # confederacion_id = 2 -> 62 días
    3: 68,  # confederacion_id = 3 -> 68 días
    4: 92,  # confederacion_id = 4 -> 92 días
    5: 84,  # confederacion_id = 5 -> 84 días
    6: 48,  # confederacion_id = 6 -> 48 días
    7: 10,  # confederacion_id = 7 -> 10 días
    8: 2  # confederacion_id = 8 -> 2 días
}


# Bloques de horarios disponibles para distribuir los partidos del día
BLOQUES_HORARIOS = ["10:00", "12:00", "14:00", "16:00", "17:30", "19:00", "21:00", "22:00"]

# Cuántos partidos de la MISMA confederación caben de verdad en un día -- ver
# obtener_siguiente_slot_disponible: cuando el último bloque ocupado del día es de la misma
# confederación que el que se quiere agregar, deja un "bloque de separación" libre antes de
# asignar el siguiente (pensado para intercalar partidos de distintas confederaciones que
# comparten el calendario en las fases 1-6). Como en las fases 7 en adelante TODOS los partidos
# comparten confederacion_id (8 = Mundial), ese bloque de separación entra en juego casi siempre
# y no se aprovechan los 8 bloques de BLOQUES_HORARIOS -- 5, no 8, confirmado corriendo
# obtener_siguiente_slot_disponible en secuencia con un solo confederacion_id.
PARTIDOS_POR_DIA_MISMA_CONFEDERACION = 5

# Días de aire entre el último partido ubicado de una jornada y el primero de la siguiente,
# además de los días que la jornada necesita para ubicar todos sus partidos (ver
# _intervalo_minimo_para_jornada) -- para no arrancar la jornada siguiente el mismo día en que
# termina de ubicarse la anterior.
MARGEN_DIAS_ENTRE_JORNADAS = 2


def _intervalo_minimo_para_jornada(num_partidos: int) -> int:
    """
    Días mínimos que necesita una jornada de 'num_partidos' partidos para poder ubicarlos todos
    sin invadir el espacio de la jornada siguiente (ver PARTIDOS_POR_DIA_MISMA_CONFEDERACION +
    MARGEN_DIAS_ENTRE_JORNADAS). Se usa como PISO del intervalo configurado en
    INTERVALO_DIAS_POR_CONFEDERACION (nunca lo reduce) -- bug real encontrado en la fase 7: con
    24 partidos por jornada (12 grupos x 2) y el intervalo fijo de 2 días para
    confederacion_id=8, la Jornada 2 arrancaba mientras la Jornada 1 todavía se estaba
    terminando de jugar, y lo mismo entre la 2 y la 3. Las fases 1-6 no se ven afectadas: sus
    intervalos fijos (48-92 días) ya son muchísimo más grandes que lo que da esta cuenta para la
    cantidad de partidos que manejan por jornada.
    """
    dias_para_ubicar_partidos = -(-num_partidos // PARTIDOS_POR_DIA_MISMA_CONFEDERACION)  # ceil
    return dias_para_ubicar_partidos + MARGEN_DIAS_ENTRE_JORNADAS


DIAS_SEMANA_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]


def formatear_fecha_es(fecha_str: Optional[str]) -> str:
    """
    Formatea una fecha guardada como 'YYYY-MM-DD' (ver asignar_fechas_y_horas_fase1/
    _siguiente) a texto largo en español, ej. 'Lunes 11 de Abril de 1987'.

    No depende del locale del sistema operativo (que puede no tener 'es_ES' instalado/
    habilitado en el server) -- usa tablas propias de días/meses en vez de
    datetime.strftime('%A %B', ...), que sale en inglés salvo que el locale esté configurado.
    """
    if not fecha_str:
        return "N/A"
    try:
        fecha = datetime.strptime(fecha_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return fecha_str
    return f"{DIAS_SEMANA_ES[fecha.weekday()]} {fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


def _precargar_ocupacion_dias(partidos_coll, mundial_id: Any) -> Dict[str, List[Optional[int]]]:
    """
    Reconstruye la ocupación de fechas ya persistida en Mongo para este mundial,
    como { "YYYY-MM-DD": [confederacion_id, ...] } en orden horario.
    Se usa para "sembrar" ocupacion_dias antes de asignar fechas nuevas, de forma
    que el tope de partidos por día y el corrimiento al día siguiente tengan en
    cuenta TODO lo ya agendado (de cualquier confederación/llamada anterior), no
    solo el lote que se está procesando en esta ejecución.
    """
    orden_horas = {hora: idx for idx, hora in enumerate(BLOQUES_HORARIOS)}

    partidos_por_fecha: Dict[str, list] = {}
    cursor = partidos_coll.find(
        {"mundial_id": mundial_id, "fecha": {"$ne": None, "$exists": True}},
        {"fecha": 1, "hora": 1, "confederacion_id": 1}
    )
    for p in cursor:
        partidos_por_fecha.setdefault(p["fecha"], []).append(p)

    ocupacion_dias: Dict[str, List[Optional[int]]] = {}
    for fecha, lista in partidos_por_fecha.items():
        lista_ordenada = sorted(lista, key=lambda p: orden_horas.get(p.get("hora"), len(BLOQUES_HORARIOS)))
        ocupacion_dias[fecha] = [p.get("confederacion_id") for p in lista_ordenada]

    return ocupacion_dias


def _intercalar_partidos(jornadas_dict: Dict[tuple, list]) -> list:
    """
    Combina los grupos (confederacion_id, jornada) -> [partidos] en una sola
    secuencia de (clave_grupo, partido), alternando de a uno entre grupos
    (round-robin) en vez de volcar cada grupo de forma consecutiva.
    Esto es lo que permite que, cuando hay más de una confederación con
    partidos pendientes en la misma corrida, sus partidos se intercalen en
    vez de apilarse en bloques horarios seguidos del mismo grupo.
    """
    grupos = list(jornadas_dict.items())
    listas_con_clave = [[(clave, partido) for partido in partidos] for clave, partidos in grupos]

    intercalado = []
    for tanda in zip_longest(*listas_con_clave):
        for item in tanda:
            if item is not None:
                intercalado.append(item)

    return intercalado


def asignar_fechas_y_horas_fase1(db: Database, mundial_id: Any) -> Dict[str, Any]:
    partidos_coll = db["juegos"]
    mundiales_coll = db["mundiales"]

    # 1. Obtener el año del mundial activo
    mundial = mundiales_coll.find_one({"_id": ObjectId(mundial_id)})
    if not mundial:
        return {"exito": False, "mensaje": "Mundial no encontrado."}

    anio_mundial = mundial["anio"]
    anio_inicio = anio_mundial - 3
    
    # 2. Consultar partidos de la Fase 1 sin fecha asignada
    query_sin_fecha = {
        "mundial_id": mundial_id,
        "fase_id": 1,
        "$or": [{"fecha": {"$exists": False}}, {"fecha": None}]
    }
    partidos = list(partidos_coll.find(query_sin_fecha))

    if not partidos:
        return {"exito": True, "mensaje": "No hay partidos pendientes de fecha."}

    # Control de ocupación global por fecha, sembrado con lo que ya existe en
    # Mongo para este mundial (de cualquier confederación/llamada anterior)
    ocupacion_dias = _precargar_ocupacion_dias(partidos_coll, mundial_id)
    operaciones = []

    # Agrupar partidos por (confederacion_id, jornada) para asignar la fecha base a la jornada entera
    jornadas_dict = {}
    for p in partidos:
        # Extraer el número de jornada limpiando el string "Jornada X" -> int(X)
        jornada_num = int(p["jornada"].replace("Jornada ", "").strip())
        conf_id = p["confederacion_id"]

        key = (conf_id, jornada_num)
        if key not in jornadas_dict:
            jornadas_dict[key] = []
        jornadas_dict[key].append(p)

    # 3. Calcular la fecha base de jornada para cada grupo (confederación, jornada)
    fecha_base_por_grupo = {}
    for (conf_id, jornada_num) in jornadas_dict:
        #1. Definir el rango global de la ventana eliminatoria (3 años)
        valor = 15
        cambio = random.choice([-3, -2, -1, 0, 1, 2, 3])

        # Aplicamos la modificación
        nuevo_valor = valor + cambio

        fecha_inicio_global = datetime(anio_inicio, 1, nuevo_valor)

        # Obtener el intervalo en días predefinido para esta confederación (30 por defecto si no existe),
        # nunca menor a lo que esta jornada necesita en la práctica para ubicar todos sus partidos
        # (ver _intervalo_minimo_para_jornada) -- así una jornada nunca empieza a jugarse mientras
        # la anterior todavía se está terminando de ubicar en el calendario.
        intervalo_dias = INTERVALO_DIAS_POR_CONFEDERACION.get(conf_id, 30)
        intervalo_dias = max(intervalo_dias, _intervalo_minimo_para_jornada(len(jornadas_dict[(conf_id, jornada_num)])))

        # Fecha base para la jornada específica (Jornada 1 -> offset 0, Jornada 2 -> offset 1 * intervalo, etc.)
        dias_offset = int((jornada_num - 1) * intervalo_dias)
        fecha_base_por_grupo[(conf_id, jornada_num)] = fecha_inicio_global + timedelta(days=dias_offset)

    # 4. Asignar fecha y hora, intercalando entre confederaciones/jornadas en
    #    vez de volcar cada grupo de forma consecutiva
    for (conf_id, jornada_num), partido in _intercalar_partidos(jornadas_dict):
        fecha_base_jornada = fecha_base_por_grupo[(conf_id, jornada_num)]

        # Desfase individual de 0 a 2 días dentro de la misma jornada para no juntar todos los juegos el mismo día
        variacion_dias = random.randint(0, 2)
        fecha_tentativa = fecha_base_jornada + timedelta(days=variacion_dias)

        # Obtener fecha real ajustada y la hora secuencial correspondiente
        fecha_asignada, hora_asignada = obtener_siguiente_slot_disponible(fecha_tentativa, ocupacion_dias, conf_id)

        operaciones.append(
            UpdateOne(
                {"_id": partido["_id"]},
                {"$set": {
                    "fecha": fecha_asignada.strftime("%Y-%m-%d"),
                    "hora": hora_asignada
                }}
            )
        )

    # 5. Guardar los cambios masivamente
    if operaciones:
        resultado = partidos_coll.bulk_write(operaciones)
        modificados = resultado.modified_count
    else:
        modificados = 0

    return {
        "exito": True,
        "registros_actualizados": modificados,
        "mensaje": f"Se asignaron fechas y horas exitosamente a {modificados} partidos."
    }
    

def asignar_fechas_y_horas_fase_siguiente(db: Database, mundial_id: Any, fase_actual_id: int, dias_descanso_fase: int = 20) -> Dict[str, Any]:
    partidos_coll = db["juegos"]

    # 1. Consultar partidos de la fase especificada que no tengan fecha
    query_sin_fecha = {
        "mundial_id": mundial_id,
        "fase_id": fase_actual_id,
        "$or": [{"fecha": {"$exists": False}}, {"fecha": None}],
    }
    partidos = list(partidos_coll.find(query_sin_fecha))

    if not partidos:
        return {
            "exito": True,
            "mensaje": f"No hay partidos pendientes de fecha para la Fase {fase_actual_id}.",
        }

    # Control de ocupación global por fecha, sembrado con lo que ya existe en
    # Mongo para este mundial (de cualquier confederación/llamada anterior)
    ocupacion_dias = _precargar_ocupacion_dias(partidos_coll, mundial_id)

    # 2. Agrupar partidos por (confederacion_id, jornada)
    jornadas_dict = {}
    for p in partidos:
        jornada_num = int(p["jornada"].replace("Jornada ", "").strip())
        conf_id = p["confederacion_id"]

        key = (conf_id, jornada_num)
        if key not in jornadas_dict:
            jornadas_dict[key] = []
        jornadas_dict[key].append(p)

    operaciones = []
    # Caché local para evitar múltiples consultas a Mongo por la misma confederación
    ultimas_fechas_cache = {}
    fecha_base_por_grupo = {}

    # 3. Calcular la fecha base de jornada para cada grupo (confederación, jornada)
    for (conf_id, jornada_num) in jornadas_dict:

        # Buscar la fecha del último juego registrado para esta confederación en fases anteriores
        if conf_id not in ultimas_fechas_cache:
            # 1. Armamos el filtro base para fases anteriores con fecha
            query_ultimo_partido = {
                "mundial_id": mundial_id,
                "fase_id": {"$lt": fase_actual_id},
                "fecha": {"$ne": None, "$exists": True},
            }

            # 2. Si NO es confederación 7 u 8, agregamos el filtro específico por confederacion_id
            if conf_id not in (7, 8):
                query_ultimo_partido["confederacion_id"] = conf_id

            # 3. Consultamos el último partido según el filtro dinámico
            ultimo_partido = partidos_coll.find_one(
                query_ultimo_partido,
                sort=[("fecha", -1)],  # Ordenar de mayor a menor para obtener la fecha más reciente
            )

            if ultimo_partido and "fecha" in ultimo_partido:
                fecha_str = ultimo_partido["fecha"]
                # Fecha base inicial = Última fecha conocida + días de descanso entre fases
                fecha_base_confederacion = datetime.strptime(
                    fecha_str, "%Y-%m-%d"
                ) + timedelta(days=dias_descanso_fase)
            else:
                # Fallback si no hay partidos previos con fecha
                fecha_base_confederacion = datetime(datetime.now().year, 1, 15)

            ultimas_fechas_cache[conf_id] = fecha_base_confederacion

        fecha_inicio_fase = ultimas_fechas_cache[conf_id]
        # Nunca menor a lo que esta jornada necesita en la práctica para ubicar todos sus
        # partidos (ver _intervalo_minimo_para_jornada) -- este es el fix del bug real de la
        # Fase 7, donde el intervalo fijo de 2 días para confederacion_id=8 era mucho menor a lo
        # que tardaba en ubicarse una sola jornada de todos los grupos del Mundial, y la
        # siguiente jornada arrancaba mientras la anterior todavía se estaba jugando.
        intervalo_dias = INTERVALO_DIAS_POR_CONFEDERACION.get(conf_id, 30)
        intervalo_dias = max(intervalo_dias, _intervalo_minimo_para_jornada(len(jornadas_dict[(conf_id, jornada_num)])))

        # Calcular el offset en base a la jornada (Jornada 1 = offset 0 sobre la fecha de inicio)
        dias_offset = int((jornada_num - 1) * intervalo_dias)
        fecha_base_por_grupo[(conf_id, jornada_num)] = fecha_inicio_fase + timedelta(days=dias_offset)

    # 4. Asignar fecha y hora, intercalando entre confederaciones/jornadas en
    #    vez de volcar cada grupo de forma consecutiva
    for (conf_id, jornada_num), partido in _intercalar_partidos(jornadas_dict):
        fecha_base_jornada = fecha_base_por_grupo[(conf_id, jornada_num)]

        variacion_dias = random.randint(0, 2)
        fecha_tentativa = fecha_base_jornada + timedelta(days=variacion_dias)

        fecha_asignada, hora_asignada = obtener_siguiente_slot_disponible(fecha_tentativa, ocupacion_dias, conf_id)

        operaciones.append(
            UpdateOne(
                {"_id": partido["_id"]},
                {
                    "$set": {
                        "fecha": fecha_asignada.strftime("%Y-%m-%d"),
                        "hora": hora_asignada,
                    }
                },
            )
        )

    # 5. Guardar los cambios masivamente
    if operaciones:
        resultado = partidos_coll.bulk_write(operaciones)
        modificados = resultado.modified_count
    else:
        modificados = 0

    return {
        "exito": True,
        "registros_actualizados": modificados,
        "mensaje": f"Se asignaron fechas y horas exitosamente a {modificados} partidos de la Fase {fase_actual_id}.",
    }
    
    
def obtener_siguiente_slot_disponible(
    fecha_deseada: datetime,
    ocupacion_dias: Dict[str, List[Optional[int]]],
    confederacion_id: Optional[int] = None
) -> tuple[datetime, str]:
    """
    Busca de manera secuencial el siguiente bloque horario disponible partiendo de fecha_deseada.
    Si el día tiene 8 partidos ocupados, salta al día siguiente a las 10:00.

    Cuando el último bloque ocupado de ese día es de la misma confederación y
    todavía queda más de un bloque libre ese día, se deja un bloque "de
    separación" (sin partido) antes de asignar el siguiente, para que no
    queden dos partidos seguidos de la misma confederación cuando hay
    alternativa disponible en el propio día.
    """
    fecha_actual = fecha_deseada

    while True:
        key_fecha = fecha_actual.strftime("%Y-%m-%d")
        ocupados = ocupacion_dias.setdefault(key_fecha, [])
        bloques_libres = len(BLOQUES_HORARIOS) - len(ocupados)

        if bloques_libres > 0:
            if ocupados and confederacion_id is not None and ocupados[-1] == confederacion_id and bloques_libres > 1:
                # Bloque de separación: se consume el horario pero no se asigna partido
                ocupados.append(None)
                continue

            hora = BLOQUES_HORARIOS[len(ocupados)]
            ocupados.append(confederacion_id)
            return fecha_actual, hora

        # Si el día se llenó, avanzamos al siguiente día
        fecha_actual += timedelta(days=1)