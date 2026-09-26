"""
Lógica de negocio del módulo "Dueño de Selecciones / Accionista": mercado,
compra/venta de selecciones (team_ownerships), y actualización de valor +
dividendos al simular partidos y al avanzar de fase.

Notas de diseño / decisiones sobre ambigüedades del pedido original:
- 'paises.user_id': la app no tiene un id numérico para usuarios (solo el
  ObjectId nativo de Mongo en 'usuarios._id'), así que "user_id > 0" se
  implementa como "truthy y distinto de 0/'0'" en vez de una comparación
  numérica literal: 0 (int) = sin dueño, str(ObjectId) = dueño actual.
- Tipos de 'ownership_transactions.type': se usan los sustantivos que pediste
  en las REGLAS DE NEGOCIO (COMPRA/VENTA/DIVIDENDO), no los verbos que
  aparecían en la sección de esquemas (COMPRAR/VENDER) — inconsistencia entre
  ambas secciones de tu mensaje, y las reglas de negocio son más explícitas.
  Se agrega un 4to tipo, BONO_CLASIFICACION, para diferenciar el bono de
  avance de fase (+300) del dividendo por victoria en un partido (+150):
  son dos eventos económicos distintos y conviene poder auditarlos por separado.
- "Vender solo si no está jugando en ese instante": esta app simula partidos
  de forma síncrona (todo el partido se resuelve dentro de un solo request),
  no existe un estado real de "partido en curso" en la base. Como proxy se
  bloquea la venta si el país es local o visitante del PRÓXIMO partido activo
  (el que devolvería obtener_juego_activo) — es el caso más parecido a
  "está por jugar ahora mismo" que se puede detectar con el modelo de datos actual.
- El bono de avance de fase (+300) NO se engancha en el simulador de partidos:
  para los formatos de grupos (la mayoría de las fases 1-7), el avance se
  decide recién cuando se cierra TODO el grupo, no en un partido individual.
  El punto de enganche correcto es actualizar_estatus_paises_bulk en
  clasificacion_service.py, que es por donde pasan TODOS los cambios de
  estado de avance/eliminación, sea el formato que sea (ver procesar_bono_avance_fase).
- Sinergia con el Álbum de Estampas ('user_albums.owned_paises', mismo campo
  que ya usa services/album_service.py): el módulo de selecciones tenía esta
  sinergia pendiente (a diferencia de Fantasy y Sedes, que ya la tenían). Se
  aplica sobre CUALQUIER pago al dueño (dividendo por victoria o bono de
  avance de fase), en el mismo punto único _abonar_puntos_dueno:
    a) El dueño de la selección cobra el pago normal, multiplicado x1.5 si
       ADEMÁS tiene la estampa de ese país pegada en su álbum.
    b) Todo usuario que tenga la estampa de ese país y NO sea el dueño cobra
       +20 pts pasivos por ese mismo evento (mismo criterio que la sinergia
       de Sedes en services/venue_service.py: no depende de ser dueño de la
       selección, es un beneficio pasivo de solo poseer la estampa).
"""
import certifi
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

VALOR_INICIAL_PAIS = 1000
DIVIDENDO_VICTORIA = 150
BONO_AVANCE_FASE = 300

MULTIPLICADOR_SINERGIA_ALBUM = 1.5
BONUS_PASIVO_ALBUM = 20

ESTADO_INVERSION_ACTIVO = "ACTIVO"
ESTADO_INVERSION_VENDIDO = "VENDIDO"

TIPO_TRANSACCION_COMPRA = "COMPRA"
TIPO_TRANSACCION_VENTA = "VENTA"
TIPO_TRANSACCION_DIVIDENDO = "DIVIDENDO"
TIPO_TRANSACCION_BONO_CLASIFICACION = "BONO_CLASIFICACION"
TIPO_TRANSACCION_SINERGIA_ALBUM = "SINERGIA_ALBUM"


def _tiene_estampa_pais(user_id: Any, pais_id: int) -> bool:
    usuario_oid = user_id if isinstance(user_id, ObjectId) else ObjectId(user_id)
    album = db['user_albums'].find_one({"user_id": usuario_oid, "owned_paises": pais_id}, {"_id": 1})
    return album is not None


def _tiene_dueno(valor_user_id: Any) -> bool:
    """paises.user_id: 0 (o '0'/None) significa que la selección está libre."""
    return valor_user_id not in (0, "0", None, "")


def _serializar_inversion(inversion: dict, pais: Optional[dict] = None) -> dict:
    inversion = dict(inversion)
    inversion["id"] = str(inversion.pop("_id"))
    inversion["user_id"] = str(inversion["user_id"])
    inversion["plusvalia"] = inversion["current_value"] - inversion["purchase_price"]
    if pais:
        inversion["pais_nombre"] = pais.get("nombre")
        inversion["pais_bandera"] = pais.get("bandera")
    return inversion


def _serializar_transaccion(transaccion: dict) -> dict:
    transaccion = dict(transaccion)
    transaccion["id"] = str(transaccion.pop("_id"))
    transaccion["user_id"] = str(transaccion["user_id"])
    return transaccion


# ==========================================
# Mercado
# ==========================================
def obtener_mercado(confederacion_id: Optional[int] = None) -> List[dict]:
    """Lista los países SIN dueño disponibles para comprar, ordenados por confederación y valor."""
    filtro: Dict[str, Any] = {"user_id": {"$in": [0, "0", None]}}
    if confederacion_id is not None:
        filtro["confederacion_id"] = confederacion_id

    paises = db['paises'].find(
        filtro,
        {"id": 1, "nombre": 1, "bandera": 1, "confederacion_id": 1, "valor": 1}
    ).sort([("confederacion_id", 1), ("valor", -1)])

    return [
        {
            "pais_id": p["id"],
            "nombre": p.get("nombre"),
            "bandera": p.get("bandera"),
            "confederacion_id": p.get("confederacion_id"),
            "valor": p.get("valor", VALOR_INICIAL_PAIS)
        }
        for p in paises
    ]


# ==========================================
# Compra
# ==========================================
def buy_team(user_id: str, pais_id: int) -> dict:
    """
    Compra una selección para el usuario:
    - El país debe existir y no tener dueño.
    - El usuario no puede tener ya otra selección ACTIVA de la misma confederación.
    - El usuario debe tener saldo suficiente (== pais.valor actual).
    Lanza ValueError con un mensaje descriptivo si alguna validación falla.
    """
    pais = db['paises'].find_one({"id": pais_id})
    if not pais:
        raise ValueError("La selección no existe")
    if _tiene_dueno(pais.get("user_id", 0)):
        raise ValueError("Esta selección ya tiene dueño")

    usuario_oid = ObjectId(user_id)
    usuario = db['usuarios'].find_one({"_id": usuario_oid})
    if not usuario or not usuario.get("activo", True):
        raise ValueError("Usuario no encontrado o inactivo")

    confederacion_id = pais.get("confederacion_id")
    ya_tiene_de_la_confederacion = db['team_ownerships'].find_one({
        "user_id": usuario_oid,
        "confederacion_id": confederacion_id,
        "status": ESTADO_INVERSION_ACTIVO
    })
    if ya_tiene_de_la_confederacion:
        raise ValueError("Ya tenés una selección activa de esta confederación (máximo 1 por confederación)")

    costo = pais.get("valor", VALOR_INICIAL_PAIS)
    if usuario.get("monto", 0) < costo:
        raise ValueError("Saldo insuficiente para comprar esta selección")

    # Descuento atómico del saldo (evita saldo negativo por compras concurrentes)
    descuento = db['usuarios'].update_one(
        {"_id": usuario_oid, "monto": {"$gte": costo}},
        {"$inc": {"monto": -costo}}
    )
    if descuento.modified_count == 0:
        raise ValueError("Saldo insuficiente para comprar esta selección")

    # "Reclamo" atómico del país: solo aplica si en este momento sigue sin dueño
    # (evita que dos usuarios compren el mismo país en simultáneo)
    reclamo = db['paises'].update_one(
        {"id": pais_id, "user_id": {"$in": [0, "0", None]}},
        {"$set": {"user_id": str(usuario_oid)}}
    )
    if reclamo.modified_count == 0:
        # alguien más se la llevó justo antes: revertir el descuento ya aplicado
        db['usuarios'].update_one({"_id": usuario_oid}, {"$inc": {"monto": costo}})
        raise ValueError("Esta selección ya tiene dueño")

    inversion = {
        "user_id": usuario_oid,
        "pais_id": pais_id,
        "confederacion_id": confederacion_id,
        "purchase_price": costo,
        "current_value": costo,
        "total_dividends_earned": 0,
        "purchased_at": datetime.now(),
        "sold_at": None,
        "sale_price": None,
        "status": ESTADO_INVERSION_ACTIVO
    }
    resultado = db['team_ownerships'].insert_one(inversion)
    inversion["_id"] = resultado.inserted_id

    db['ownership_transactions'].insert_one({
        "user_id": usuario_oid,
        "pais_id": pais_id,
        "type": TIPO_TRANSACCION_COMPRA,
        "amount_points": -costo,
        "created_at": datetime.now()
    })

    return _serializar_inversion(inversion, pais)


# ==========================================
# Venta
# ==========================================
def sell_team(user_id: str, pais_id: int) -> dict:
    """
    Vende la selección activa del usuario al valor de mercado actual del país.
    Bloquea la venta si el país es local o visitante del partido activo en este momento.
    """
    # import diferido para evitar import circular (juegos_service no depende de ownership_service)
    from services.juegos_service import obtener_juego_activo

    usuario_oid = ObjectId(user_id)

    inversion = db['team_ownerships'].find_one({
        "user_id": usuario_oid,
        "pais_id": pais_id,
        "status": ESTADO_INVERSION_ACTIVO
    })
    if not inversion:
        raise ValueError("No sos dueño activo de esta selección")

    juego_activo, _ = obtener_juego_activo()
    if juego_activo:
        ids_en_juego = {
            juego_activo.get("equipo_local", {}).get("id"),
            juego_activo.get("equipo_visitante", {}).get("id")
        }
        if pais_id in ids_en_juego:
            raise ValueError("No podés vender una selección que está por jugar en este momento")

    pais = db['paises'].find_one({"id": pais_id})
    valor_actual = pais.get("valor", inversion["current_value"]) if pais else inversion["current_value"]

    db['usuarios'].update_one({"_id": usuario_oid}, {"$inc": {"monto": valor_actual}})
    db['paises'].update_one({"id": pais_id}, {"$set": {"user_id": 0}})

    ahora = datetime.now()
    db['team_ownerships'].update_one(
        {"_id": inversion["_id"]},
        {"$set": {
            "status": ESTADO_INVERSION_VENDIDO,
            "current_value": valor_actual,
            "sold_at": ahora,
            "sale_price": valor_actual
        }}
    )

    db['ownership_transactions'].insert_one({
        "user_id": usuario_oid,
        "pais_id": pais_id,
        "type": TIPO_TRANSACCION_VENTA,
        "amount_points": valor_actual,
        "created_at": ahora
    })

    inversion_actualizada = db['team_ownerships'].find_one({"_id": inversion["_id"]})
    return _serializar_inversion(inversion_actualizada, pais)


# ==========================================
# Portafolio
# ==========================================
def obtener_portafolio(user_id: str) -> List[dict]:
    """Selecciones ACTIVAS del usuario, con su valor de compra/actual y plusvalía."""
    inversiones = list(db['team_ownerships'].find({
        "user_id": ObjectId(user_id),
        "status": ESTADO_INVERSION_ACTIVO
    }))
    if not inversiones:
        return []

    ids_paises = [inv["pais_id"] for inv in inversiones]
    paises_por_id = {
        p["id"]: p for p in db['paises'].find({"id": {"$in": ids_paises}}, {"id": 1, "nombre": 1, "bandera": 1})
    }

    return [_serializar_inversion(inv, paises_por_id.get(inv["pais_id"])) for inv in inversiones]


# ==========================================
# Actualización de valor + dividendos al simular un partido
# ==========================================
def procesar_valor_y_dividendos_partido(match_data: Dict[str, Any]) -> None:
    """
    Se llama cada vez que un partido termina de simularse (ver routes/simular_route.py).
    match_data: {
        "pais_id_local": int, "pais_id_visita": int,
        "goles_local": int, "goles_visitante": int,
        "ganador_lado": "L" | "V" | "E"
    }
    Actualiza el 'valor' de mercado de AMBOS países y, si alguno tiene dueño,
    le abona el dividendo de +150 pts por ganar (ver reglas de negocio).
    """
    pais_id_local = match_data["pais_id_local"]
    pais_id_visita = match_data["pais_id_visita"]
    goles_local = match_data["goles_local"]
    goles_visitante = match_data["goles_visitante"]
    ganador_lado = match_data["ganador_lado"]

    if ganador_lado == "L":
        _actualizar_valor_pais(pais_id_local, "GANADOR", goles_favor=goles_local)
        _actualizar_valor_pais(pais_id_visita, "PERDEDOR", goles_contra=goles_local)
    elif ganador_lado == "V":
        _actualizar_valor_pais(pais_id_visita, "GANADOR", goles_favor=goles_visitante)
        _actualizar_valor_pais(pais_id_local, "PERDEDOR", goles_contra=goles_visitante)
    else:
        _actualizar_valor_pais(pais_id_local, "EMPATE", goles_favor=goles_local)
        _actualizar_valor_pais(pais_id_visita, "EMPATE", goles_favor=goles_visitante)


def _actualizar_valor_pais(pais_id: int, resultado: str, goles_favor: int = 0, goles_contra: int = 0) -> None:
    pais = db['paises'].find_one({"id": pais_id}, {"valor": 1, "user_id": 1})
    if not pais:
        return

    valor_actual = pais.get("valor", VALOR_INICIAL_PAIS)

    if resultado == "GANADOR":
        nuevo_valor = valor_actual + 100 + (goles_favor * 50)
    elif resultado == "EMPATE":
        nuevo_valor = valor_actual + (goles_favor * 20)
    else:  # PERDEDOR
        nuevo_valor = max(100, valor_actual - 50 - (goles_contra * 20))

    db['paises'].update_one({"id": pais_id}, {"$set": {"valor": nuevo_valor}})

    user_id = pais.get("user_id", 0)
    if not _tiene_dueno(user_id):
        return

    # Sincronizar el snapshot 'current_value' de la inversión activa
    db['team_ownerships'].update_one(
        {"pais_id": pais_id, "status": ESTADO_INVERSION_ACTIVO},
        {"$set": {"current_value": nuevo_valor}}
    )

    if resultado == "GANADOR":
        _abonar_puntos_dueno(user_id, pais_id, DIVIDENDO_VICTORIA, TIPO_TRANSACCION_DIVIDENDO)


# ==========================================
# Bono de avance de fase (ver clasificacion_service.actualizar_estatus_paises_bulk)
# ==========================================
def procesar_bono_avance_fase(pais_id: int, nuevo_estatus: str) -> None:
    """
    Si el país avanzó de fase (cualquier estatus que no empiece con 'ELIMINADO')
    y tiene dueño, le abona el bono de clasificación de +300 pts.
    """
    if nuevo_estatus.startswith("ELIMINADO"):
        return

    pais = db['paises'].find_one({"id": pais_id}, {"user_id": 1})
    if not pais:
        return

    user_id = pais.get("user_id", 0)
    if _tiene_dueno(user_id):
        _abonar_puntos_dueno(user_id, pais_id, BONO_AVANCE_FASE, TIPO_TRANSACCION_BONO_CLASIFICACION)


def _abonar_puntos_dueno(user_id: Any, pais_id: int, monto: int, tipo: str) -> None:
    usuario_oid = ObjectId(user_id) if not isinstance(user_id, ObjectId) else user_id

    # Sinergia con el Álbum: si el propio dueño tiene la estampa de este país, el pago
    # (dividendo o bono de clasificación, según 'tipo') se multiplica x1.5.
    dueno_tiene_estampa = _tiene_estampa_pais(usuario_oid, pais_id)
    monto_final = round(monto * MULTIPLICADOR_SINERGIA_ALBUM) if dueno_tiene_estampa else monto

    db['usuarios'].update_one({"_id": usuario_oid}, {"$inc": {"monto": monto_final}})
    db['team_ownerships'].update_one(
        {"pais_id": pais_id, "status": ESTADO_INVERSION_ACTIVO},
        {"$inc": {"total_dividends_earned": monto_final}}
    )
    db['ownership_transactions'].insert_one({
        "user_id": usuario_oid,
        "pais_id": pais_id,
        "type": tipo,
        "amount_points": monto_final,
        "album_synergy_applied": dueno_tiene_estampa,
        "created_at": datetime.now()
    })

    # Recompensa pasiva (+20 pts) para todo el resto de usuarios que tienen la estampa
    # de este país en su álbum, sin ser los dueños de la selección.
    otros_con_estampa = db['user_albums'].find(
        {"owned_paises": pais_id, "user_id": {"$ne": usuario_oid}},
        {"user_id": 1}
    )
    for doc in otros_con_estampa:
        otro_user_id = doc["user_id"]
        db['usuarios'].update_one({"_id": otro_user_id}, {"$inc": {"monto": BONUS_PASIVO_ALBUM}})
        db['ownership_transactions'].insert_one({
            "user_id": otro_user_id,
            "pais_id": pais_id,
            "type": TIPO_TRANSACCION_SINERGIA_ALBUM,
            "amount_points": BONUS_PASIVO_ALBUM,
            "album_synergy_applied": False,
            "created_at": datetime.now()
        })
