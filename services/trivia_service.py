"""
Lógica de negocio de la Trivia Dinámica: generación de preguntas a partir de
datos reales de MongoDB (paises, ciudades, juegos, jugadores, posiciones) y
validación de las respuestas enviadas por el usuario.

Notas de diseño / decisiones sobre ambigüedades del pedido original:
- Las preguntas y su respuesta correcta se guardan en 'trivia_history' con
  estado PENDIENTE apenas se generan (nunca se le manda la respuesta correcta
  al cliente, ver TriviaPreguntaOut). 'validate_trivia_answers' busca esa
  misma sesión por 'session_id' + 'user_id' y recién ahí revela cuál era la
  correcta — si la validación se hiciera confiando en lo que manda el cliente,
  cualquiera podría autoacreditarse los 30 pts sin jugar.
- "Máximo 3 sesiones de trivia por día calendario": se cuenta contra CUALQUIER
  sesión generada ese día (PENDIENTE o COMPLETADA), no solo las completadas.
  Si solo contara las completadas, un usuario podría generar sesiones sin
  límite y quedarse con la que le tocaron preguntas más fáciles antes de
  responder — igual que otros límites "por día" de esta app (recompensa
  diaria, quinielas), se cuenta el intento, no el resultado.
- Los 5 generadores de preguntas cubren las 5 colecciones pedidas (paises,
  ciudades, juegos, jugadores, posiciones) con 8 variantes en total, elegidas
  al azar sin repetir tipo dentro de una misma sesión de 3 preguntas. Si una
  variante no tiene datos suficientes en este momento (ej. mundial recién
  creado sin partidos finalizados todavía), se descarta y se intenta con otra
  (manejo defensivo, ver _generar_pregunta_valida).
"""
import certifi
import random
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

PREGUNTAS_POR_SESION = 3
OPCIONES_POR_PREGUNTA = 4
PUNTOS_POR_RESPUESTA_CORRECTA = 10
PUNTOS_MAXIMOS_SESION = 30
MAX_SESIONES_TRIVIA_DIA = 3

ESTADO_TRIVIA_PENDIENTE = "PENDIENTE"
ESTADO_TRIVIA_COMPLETADA = "COMPLETADA"


def _armar_pregunta(enunciado: str, correcta: str, distractores: List[str]) -> Optional[dict]:
    """Arma una pregunta con 4 opciones mezcladas, o None si no hay 3 distractores válidos."""
    distractores_validos = list({d for d in distractores if d and d != correcta})
    if len(distractores_validos) < OPCIONES_POR_PREGUNTA - 1:
        return None

    opciones = [correcta] + random.sample(distractores_validos, OPCIONES_POR_PREGUNTA - 1)
    random.shuffle(opciones)

    return {
        "enunciado": enunciado,
        "opciones": opciones,
        "respuesta_correcta_idx": opciones.index(correcta)
    }


# ==========================================
# Generadores de preguntas (uno por variante de dato)
# ==========================================
def _pregunta_confederacion_pais() -> Optional[dict]:
    muestra = list(db['paises'].aggregate([{"$sample": {"size": 1}}]))
    if not muestra:
        return None
    pais = muestra[0]

    confederacion = db['confederaciones'].find_one({"id": pais.get("confederacion_id")})
    if not confederacion:
        return None

    otras = list(db['confederaciones'].aggregate([
        {"$match": {"id": {"$ne": pais.get("confederacion_id")}}},
        {"$sample": {"size": 5}}
    ]))

    return _armar_pregunta(
        f"¿A qué confederación pertenece la selección de {pais.get('nombre')}?",
        confederacion.get("nombre"),
        [c.get("nombre") for c in otras]
    )


def _pregunta_ranking_pais() -> Optional[dict]:
    muestra = list(db['paises'].aggregate([{"$sample": {"size": 1}}]))
    if not muestra:
        return None
    pais = muestra[0]

    rankin = pais.get("estadisticas", {}).get("rankin") if isinstance(pais.get("estadisticas"), dict) else None
    if rankin is None:
        rankin = pais.get("rankin")
    if not rankin:
        return None

    distractores = list({max(1, rankin + delta) for delta in (-5, -2, 3, 7, 11) if rankin + delta != rankin})

    return _armar_pregunta(
        f"¿Cuál es la posición de {pais.get('nombre')} en el ranking FIFAV actual?",
        str(rankin),
        [str(d) for d in distractores]
    )


def _pregunta_siglas_pais() -> Optional[dict]:
    muestra = list(db['paises'].aggregate([{"$match": {"siglas": {"$exists": True, "$ne": None}}}, {"$sample": {"size": 1}}]))
    if not muestra:
        return None
    pais = muestra[0]

    otras = list(db['paises'].aggregate([
        {"$match": {"id": {"$ne": pais.get("id")}, "siglas": {"$exists": True, "$ne": None}}},
        {"$sample": {"size": 5}}
    ]))

    return _armar_pregunta(
        f"¿Cuáles son las siglas de la selección de {pais.get('nombre')}?",
        pais.get("siglas"),
        [p.get("siglas") for p in otras]
    )


def _pregunta_pais_de_ciudad() -> Optional[dict]:
    muestra = list(db['ciudades'].aggregate([{"$match": {"pais": {"$exists": True, "$ne": None}}}, {"$sample": {"size": 1}}]))
    if not muestra:
        return None
    ciudad = muestra[0]

    otras = list(db['ciudades'].aggregate([
        {"$match": {"pais_id": {"$ne": ciudad.get("pais_id")}, "pais": {"$exists": True, "$ne": None}}},
        {"$sample": {"size": 10}}
    ]))

    return _armar_pregunta(
        f"¿A qué país pertenece la ciudad de {ciudad.get('nombre')}?",
        ciudad.get("pais"),
        [c.get("pais") for c in otras]
    )


def _pregunta_ciudad_del_estadio() -> Optional[dict]:
    muestra = list(db['ciudades'].aggregate([{"$match": {"estadio": {"$exists": True, "$ne": None}}}, {"$sample": {"size": 1}}]))
    if not muestra:
        return None
    ciudad = muestra[0]

    otras = list(db['ciudades'].aggregate([
        {"$match": {"id": {"$ne": ciudad.get("id")}}},
        {"$sample": {"size": 5}}
    ]))

    return _armar_pregunta(
        f"¿En qué ciudad se encuentra el estadio {ciudad.get('estadio')}?",
        ciudad.get("nombre"),
        [c.get("nombre") for c in otras]
    )


def _pregunta_resultado_partido() -> Optional[dict]:
    muestra = list(db['juegos'].aggregate([
        {"$match": {"estado": "finalizado"}},
        {"$sample": {"size": 1}}
    ]))
    if not muestra:
        return None
    juego = muestra[0]
    resultado = juego.get("resultado") or {}
    local = resultado.get("local")
    visitante = resultado.get("visitante")
    goles_local = resultado.get("goles_local")
    goles_visitante = resultado.get("goles_visitante")
    if not local or not visitante or goles_local is None or goles_visitante is None:
        return None

    correcto = f"{goles_local} - {goles_visitante}"
    candidatos_falsos = [
        f"{goles_local + 1} - {goles_visitante}",
        f"{goles_local} - {goles_visitante + 1}",
        f"{goles_local + 1} - {goles_visitante + 1}",
        f"{max(0, goles_local - 1)} - {goles_visitante}",
        f"{goles_local} - {max(0, goles_visitante - 1)}"
    ]

    return _armar_pregunta(
        f"¿Cuál fue el marcador final de {local} vs {visitante}?",
        correcto,
        candidatos_falsos
    )


def _pregunta_ganador_partido() -> Optional[dict]:
    muestra = list(db['juegos'].aggregate([
        {"$match": {"estado": "finalizado"}},
        {"$sample": {"size": 1}}
    ]))
    if not muestra:
        return None
    juego = muestra[0]
    resultado = juego.get("resultado") or {}
    local = resultado.get("local")
    visitante = resultado.get("visitante")
    if not local or not visitante:
        return None

    if resultado.get("empate"):
        correcto = "Empate"
    elif resultado.get("ganador_lado") == "L":
        correcto = local
    elif resultado.get("ganador_lado") == "V":
        correcto = visitante
    else:
        return None

    otro_equipo = list(db['paises'].aggregate([
        {"$match": {"nombre": {"$nin": [local, visitante]}}},
        {"$sample": {"size": 1}}
    ]))
    distractores = [local, visitante, "Empate"]
    if otro_equipo:
        distractores.append(otro_equipo[0].get("nombre"))

    return _armar_pregunta(
        f"¿Quién ganó el partido entre {local} y {visitante}?",
        correcto,
        distractores
    )


def _pregunta_pais_de_jugador() -> Optional[dict]:
    muestra = list(db['jugadores'].aggregate([{"$sample": {"size": 1}}]))
    if not muestra:
        return None
    jugador = muestra[0]

    pais = db['paises'].find_one({"id": jugador.get("pais_id")})
    if not pais:
        return None

    otros = list(db['paises'].aggregate([
        {"$match": {"id": {"$ne": jugador.get("pais_id")}}},
        {"$sample": {"size": 5}}
    ]))

    return _armar_pregunta(
        f"¿A qué selección pertenece el jugador {jugador.get('nombre')}?",
        pais.get("nombre"),
        [p.get("nombre") for p in otros]
    )


def _pregunta_posicion_de_jugador() -> Optional[dict]:
    muestra = list(db['jugadores'].aggregate([{"$sample": {"size": 1}}]))
    if not muestra:
        return None
    jugador = muestra[0]

    posiciones = {p["id"]: p["nombre"] for p in db['posiciones'].find({})}
    posicion_correcta = posiciones.get(jugador.get("posicion_id"))
    if not posicion_correcta:
        return None

    otras_posiciones = [nombre for pid, nombre in posiciones.items() if pid != jugador.get("posicion_id")]

    return _armar_pregunta(
        f"¿Cuál es la posición de {jugador.get('nombre')}?",
        posicion_correcta,
        otras_posiciones
    )


GENERADORES_PREGUNTA = [
    _pregunta_confederacion_pais,
    _pregunta_ranking_pais,
    _pregunta_siglas_pais,
    _pregunta_pais_de_ciudad,
    _pregunta_ciudad_del_estadio,
    _pregunta_resultado_partido,
    _pregunta_ganador_partido,
    _pregunta_pais_de_jugador,
    _pregunta_posicion_de_jugador
]


# ==========================================
# Generación de sesión de trivia
# ==========================================
def generate_dynamic_trivia(user_id: str) -> dict:
    """
    Genera una sesión de 3 preguntas de opción múltiple con datos reales de
    Mongo, la guarda como PENDIENTE en 'trivia_history' (con las respuestas
    correctas, nunca expuestas al cliente) y devuelve solo enunciados/opciones.
    """
    usuario_oid = ObjectId(user_id)
    usuario = db['usuarios'].find_one({"_id": usuario_oid})
    if not usuario or not usuario.get("activo", True):
        raise ValueError("Usuario no encontrado o inactivo")

    hoy_str = date.today().isoformat()
    sesiones_hoy = db['trivia_history'].count_documents({"user_id": usuario_oid, "session_date": hoy_str})
    if sesiones_hoy >= MAX_SESIONES_TRIVIA_DIA:
        raise ValueError(f"Ya alcanzaste el límite de {MAX_SESIONES_TRIVIA_DIA} sesiones de trivia por hoy")

    # Se recorren los generadores en orden aleatorio, cada uno como máximo una vez
    # (así no se repite el mismo tipo de pregunta dentro de una misma sesión).
    generadores_shuffle = list(GENERADORES_PREGUNTA)
    random.shuffle(generadores_shuffle)

    preguntas: List[dict] = []
    for generador in generadores_shuffle:
        if len(preguntas) >= PREGUNTAS_POR_SESION:
            break
        try:
            pregunta = generador()
        except Exception:
            pregunta = None
        if pregunta:
            preguntas.append(pregunta)

    if len(preguntas) < PREGUNTAS_POR_SESION:
        raise ValueError("No hay suficientes datos en este momento para generar la trivia. Probá de nuevo más tarde.")

    sesion = {
        "user_id": usuario_oid,
        "session_date": hoy_str,
        "questions_asked": len(preguntas),
        "preguntas": preguntas,
        "correct_answers": 0,
        "points_rewarded": 0,
        "respuestas_usuario": None,
        "estado": ESTADO_TRIVIA_PENDIENTE,
        "created_at": datetime.now(),
        "completed_at": None
    }
    resultado = db['trivia_history'].insert_one(sesion)

    return {
        "session_id": str(resultado.inserted_id),
        "preguntas": [
            {"indice": i, "enunciado": p["enunciado"], "opciones": p["opciones"]}
            for i, p in enumerate(preguntas)
        ]
    }


# ==========================================
# Validación de respuestas
# ==========================================
def validate_trivia_answers(user_id: str, session_id: str, respuestas: List[Optional[int]]) -> dict:
    """
    Valida las respuestas de una sesión PENDIENTE contra lo que se guardó al
    generarla, acredita +10 pts por acierto (máx. 30) en 'usuarios.monto' y
    la marca como COMPLETADA en 'trivia_history'.
    """
    usuario_oid = ObjectId(user_id)
    sesion_oid = ObjectId(session_id)

    sesion = db['trivia_history'].find_one({"_id": sesion_oid, "user_id": usuario_oid})
    if not sesion:
        raise ValueError("Sesión de trivia no encontrada")
    if sesion.get("estado") != ESTADO_TRIVIA_PENDIENTE:
        raise ValueError("Esta sesión de trivia ya fue completada")

    preguntas = sesion.get("preguntas", [])
    if len(respuestas) != len(preguntas):
        raise ValueError(f"Se esperaban {len(preguntas)} respuestas, se recibieron {len(respuestas)}")

    detalle = []
    correctas = 0
    for pregunta, respuesta_usuario in zip(preguntas, respuestas):
        correcta_idx = pregunta["respuesta_correcta_idx"]
        es_correcta = respuesta_usuario is not None and respuesta_usuario == correcta_idx
        if es_correcta:
            correctas += 1
        detalle.append({
            "enunciado": pregunta["enunciado"],
            "opciones": pregunta["opciones"],
            "respuesta_usuario_idx": respuesta_usuario,
            "respuesta_correcta_idx": correcta_idx,
            "es_correcta": es_correcta
        })

    puntos = min(correctas * PUNTOS_POR_RESPUESTA_CORRECTA, PUNTOS_MAXIMOS_SESION)
    ahora = datetime.now()

    if puntos > 0:
        db['usuarios'].update_one({"_id": usuario_oid}, {"$inc": {"monto": puntos}})

    db['trivia_history'].update_one(
        {"_id": sesion_oid},
        {"$set": {
            "estado": ESTADO_TRIVIA_COMPLETADA,
            "correct_answers": correctas,
            "points_rewarded": puntos,
            "respuestas_usuario": respuestas,
            "completed_at": ahora
        }}
    )

    return {
        "correct_answers": correctas,
        "total_questions": len(preguntas),
        "points_rewarded": puntos,
        "detalle": detalle,
        "completed_at": ahora
    }
