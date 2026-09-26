"""
Lógica de negocio del módulo "Inversión en Sedes / Estadios": directorio,
compra/venta de sedes (city_ownerships) y cobro de regalías + sinergia con el
Álbum de Estampas (services/album_service.py) al simular partidos.

Notas de diseño / decisiones sobre ambigüedades del pedido original:
- Límites de compra: usamos los que aparecen en la sección "Reglas de Negocio"
  (máx. 2 ciudades por país por usuario, máx. 20 en total), no los de la
  sección "Requerimientos de Código" (que decía max 1 por país / max 10 en
  total) — mismo tipo de inconsistencia entre secciones que ya apareció en
  los módulos de quinielas y ownership; las reglas de negocio numeradas son
  la fuente más explícita y se favorecen sobre el pseudocódigo del punto 2.
- 'ciudades.owner_user_id': igual que 'paises.user_id' en ownership_service.py,
  se guarda el dueño ACTUAL directo en el propio documento de la ciudad
  (0 = sin dueño, str(ObjectId) = dueño), en vez de derivarlo con una consulta
  aparte a 'city_ownerships' en cada chequeo de disponibilidad — permite un
  "reclamo" atómico igual al de selecciones (ver buy_city_venue).
- Venta "en cualquier momento": a diferencia de las selecciones (que no se
  pueden vender mientras están jugando), acá la regla de negocio dice
  explícitamente "en cualquier momento", así que sell_city_venue NO bloquea
  la venta aunque la sede esté hosteando el partido activo.
- Sinergia con el Álbum (regla 3): el dueño de la sede es UN usuario, pero la
  estampa de la ciudad la puede tener CUALQUIER usuario en su álbum. Por eso
  process_match_city_revenue trata ambos casos por separado:
    a) El dueño de la sede cobra la regalía (base + bonos), multiplicada x1.5
       si ADEMÁS tiene la estampa de esa ciudad.
    b) Todo usuario que tenga la estampa de esa ciudad y NO sea el dueño cobra
       +20 pts pasivos (mismo patrón que la "Recompensa Pasiva" del módulo
       Fantasy en services/fantasy_service.py: la sinergia con el álbum no
       depende de tener la sede comprada, es un beneficio pasivo de solo
       poseer la estampa).
"""
import certifi
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

COSTO_BASE_SEDE = 500
MAX_CIUDADES_POR_PAIS = 2
MAX_CIUDADES_TOTAL = 20
PORCENTAJE_REEMBOLSO_VENTA = 0.80

REGALIA_BASE = 100
FASE_ID_BONO_ALTO = 11  # Semifinal, 3er Lugar, Final
MULTIPLICADOR_FASE_ALTA = 3
BONO_POR_GOL = 15

BONUS_PASIVO_ALBUM = 20
MULTIPLICADOR_SINERGIA = 1.5

ESTADO_SEDE_ACTIVO = "ACTIVO"
ESTADO_SEDE_VENDIDO = "VENDIDO"


def _tiene_dueno(valor_user_id: Any) -> bool:
    """ciudades.owner_user_id: 0 (o '0'/None) significa que la sede está libre."""
    return valor_user_id not in (0, "0", None, "")


def _serializar_sede(inversion: dict, ciudad: Optional[dict] = None, pais: Optional[dict] = None) -> dict:
    inversion = dict(inversion)
    inversion["id"] = str(inversion.pop("_id"))
    inversion["user_id"] = str(inversion["user_id"])
    if ciudad:
        inversion["ciudad_nombre"] = ciudad.get("nombre")
        inversion["estadio"] = ciudad.get("estadio")
    if pais:
        inversion["pais_nombre"] = pais.get("nombre")
    return inversion


def _serializar_regalia(regalia: dict) -> dict:
    regalia = dict(regalia)
    regalia["id"] = str(regalia.pop("_id"))
    regalia["user_id"] = str(regalia["user_id"])
    return regalia


# ==========================================
# Directorio de sedes
# ==========================================
def obtener_ciudades_disponibles(pais_id: int) -> List[dict]:
    """Ciudades de un país que todavía no tienen dueño, listas para patrocinar."""
    ciudades = db['ciudades'].find(
        {"pais_id": pais_id, "owner_user_id": {"$in": [0, "0", None]}},
        {"id": 1, "nombre": 1, "estadio": 1, "tipo": 1, "pais_id": 1, "pais": 1}
    )
    return [
        {
            "ciudad_id": c["id"],
            "nombre": c.get("nombre"),
            "estadio": c.get("estadio"),
            "tipo": c.get("tipo"),
            "pais_id": c.get("pais_id"),
            "pais_nombre": c.get("pais"),
            "costo": COSTO_BASE_SEDE,
            "tiene_dueno": False,
            "es_mia": False
        }
        for c in ciudades
    ]


def buscar_ciudades_directorio(texto: str = "", usuario_id: Optional[str] = None, limite: int = 50) -> List[dict]:
    """
    Búsqueda para la vista de "Directorio de Sedes" (buscador por país/ciudad).
    No filtra por estado de propiedad acá: el frontend filtra client-side entre
    los resultados devueltos (misma lógica que buscar_jugadores en fantasy_service.py).
    """
    filtro: Dict[str, Any] = {}
    if texto:
        filtro["$or"] = [
            {"nombre": {"$regex": texto, "$options": "i"}},
            {"pais": {"$regex": texto, "$options": "i"}}
        ]

    ciudades = list(db['ciudades'].find(
        filtro,
        {"id": 1, "nombre": 1, "estadio": 1, "tipo": 1, "pais_id": 1, "pais": 1, "owner_user_id": 1}
    ).limit(limite))

    resultado = []
    for c in ciudades:
        owner_user_id = c.get("owner_user_id", 0)
        tiene_dueno = _tiene_dueno(owner_user_id)
        resultado.append({
            "ciudad_id": c["id"],
            "nombre": c.get("nombre"),
            "estadio": c.get("estadio"),
            "tipo": c.get("tipo"),
            "pais_id": c.get("pais_id"),
            "pais_nombre": c.get("pais"),
            "costo": COSTO_BASE_SEDE,
            "tiene_dueno": tiene_dueno,
            "es_mia": tiene_dueno and usuario_id is not None and str(owner_user_id) == str(usuario_id)
        })
    return resultado


# ==========================================
# Compra
# ==========================================
def buy_city_venue(user_id: str, ciudad_id: int) -> dict:
    """
    Compra/patrocina una sede para el usuario:
    - La ciudad debe existir y no tener dueño.
    - El usuario no puede superar 2 sedes activas del mismo país, ni 20 en total.
    - El usuario debe tener saldo suficiente (costo base fijo).
    Lanza ValueError con un mensaje descriptivo si alguna validación falla.
    """
    ciudad = db['ciudades'].find_one({"id": ciudad_id})
    if not ciudad:
        raise ValueError("La ciudad no existe")
    if _tiene_dueno(ciudad.get("owner_user_id", 0)):
        raise ValueError("Esta sede ya tiene dueño")

    usuario_oid = ObjectId(user_id)
    usuario = db['usuarios'].find_one({"_id": usuario_oid})
    if not usuario or not usuario.get("activo", True):
        raise ValueError("Usuario no encontrado o inactivo")

    pais_id = ciudad.get("pais_id")

    sedes_del_pais = db['city_ownerships'].count_documents({
        "user_id": usuario_oid, "pais_id": pais_id, "status": ESTADO_SEDE_ACTIVO
    })
    if sedes_del_pais >= MAX_CIUDADES_POR_PAIS:
        raise ValueError(f"Ya tenés {MAX_CIUDADES_POR_PAIS} sedes activas de este país (máximo permitido)")

    sedes_totales = db['city_ownerships'].count_documents({"user_id": usuario_oid, "status": ESTADO_SEDE_ACTIVO})
    if sedes_totales >= MAX_CIUDADES_TOTAL:
        raise ValueError(f"Ya alcanzaste el máximo de {MAX_CIUDADES_TOTAL} sedes activas en tu portafolio")

    if usuario.get("monto", 0) < COSTO_BASE_SEDE:
        raise ValueError("Saldo insuficiente para comprar esta sede")

    # Descuento atómico del saldo (evita saldo negativo por compras concurrentes)
    descuento = db['usuarios'].update_one(
        {"_id": usuario_oid, "monto": {"$gte": COSTO_BASE_SEDE}},
        {"$inc": {"monto": -COSTO_BASE_SEDE}}
    )
    if descuento.modified_count == 0:
        raise ValueError("Saldo insuficiente para comprar esta sede")

    # "Reclamo" atómico de la ciudad: solo aplica si en este momento sigue sin dueño
    reclamo = db['ciudades'].update_one(
        {"id": ciudad_id, "owner_user_id": {"$in": [0, "0", None]}},
        {"$set": {"owner_user_id": str(usuario_oid)}}
    )
    if reclamo.modified_count == 0:
        # alguien más se la llevó justo antes: revertir el descuento ya aplicado
        db['usuarios'].update_one({"_id": usuario_oid}, {"$inc": {"monto": COSTO_BASE_SEDE}})
        raise ValueError("Esta sede ya tiene dueño")

    inversion = {
        "user_id": usuario_oid,
        "ciudad_id": ciudad_id,
        "pais_id": pais_id,
        "purchase_price": COSTO_BASE_SEDE,
        "total_revenue_earned": 0,
        "matches_hosted_count": 0,
        "purchased_at": datetime.now(),
        "sold_at": None,
        "sale_price": None,
        "status": ESTADO_SEDE_ACTIVO
    }
    resultado = db['city_ownerships'].insert_one(inversion)
    inversion["_id"] = resultado.inserted_id

    pais = db['paises'].find_one({"id": pais_id}, {"nombre": 1})
    return _serializar_sede(inversion, ciudad, pais)


# ==========================================
# Venta
# ==========================================
def sell_city_venue(user_id: str, ciudad_id: int) -> dict:
    """Vende la sede activa del usuario, reembolsando el 80% de su costo de compra."""
    usuario_oid = ObjectId(user_id)

    inversion = db['city_ownerships'].find_one({
        "user_id": usuario_oid, "ciudad_id": ciudad_id, "status": ESTADO_SEDE_ACTIVO
    })
    if not inversion:
        raise ValueError("No sos dueño activo de esta sede")

    reembolso = round(inversion["purchase_price"] * PORCENTAJE_REEMBOLSO_VENTA)

    db['usuarios'].update_one({"_id": usuario_oid}, {"$inc": {"monto": reembolso}})
    db['ciudades'].update_one({"id": ciudad_id}, {"$set": {"owner_user_id": 0}})

    ahora = datetime.now()
    db['city_ownerships'].update_one(
        {"_id": inversion["_id"]},
        {"$set": {
            "status": ESTADO_SEDE_VENDIDO,
            "sold_at": ahora,
            "sale_price": reembolso
        }}
    )

    inversion_actualizada = db['city_ownerships'].find_one({"_id": inversion["_id"]})
    ciudad = db['ciudades'].find_one({"id": ciudad_id})
    pais = db['paises'].find_one({"id": inversion["pais_id"]}, {"nombre": 1})
    return _serializar_sede(inversion_actualizada, ciudad, pais)


# ==========================================
# Portafolio
# ==========================================
def obtener_portafolio_sedes(user_id: str) -> List[dict]:
    """Sedes ACTIVAS del usuario, con partidos alojados y ganancias totales."""
    inversiones = list(db['city_ownerships'].find({
        "user_id": ObjectId(user_id), "status": ESTADO_SEDE_ACTIVO
    }))
    if not inversiones:
        return []

    ids_ciudades = [inv["ciudad_id"] for inv in inversiones]
    ids_paises = list({inv["pais_id"] for inv in inversiones})

    ciudades_por_id = {c["id"]: c for c in db['ciudades'].find({"id": {"$in": ids_ciudades}})}
    paises_por_id = {p["id"]: p for p in db['paises'].find({"id": {"$in": ids_paises}}, {"id": 1, "nombre": 1})}

    return [
        _serializar_sede(inv, ciudades_por_id.get(inv["ciudad_id"]), paises_por_id.get(inv["pais_id"]))
        for inv in inversiones
    ]


# ==========================================
# Cobro de regalías al simular un partido (con sinergia del Álbum)
# ==========================================
def process_match_city_revenue(match_data: Dict[str, Any]) -> None:
    """
    Se llama cada vez que un partido termina de simularse (ver routes/simular_route.py).
    match_data: {
        "ciudad_id": Optional[int], "fase_id": Optional[int],
        "match_id": str, "goles_totales": int
    }
    No hace nada si el partido no tiene ciudad_id asignado (ver
    services/ciudades_service.asignar_ubicacion_partidos).
    """
    ciudad_id = match_data.get("ciudad_id")
    if ciudad_id is None:
        return

    ciudad = db['ciudades'].find_one({"id": ciudad_id})
    if not ciudad:
        return

    fase_id = match_data.get("fase_id")
    match_id = match_data["match_id"]
    goles_totales = match_data.get("goles_totales", 0)

    regalia = REGALIA_BASE
    if fase_id is not None and fase_id >= FASE_ID_BONO_ALTO:
        regalia *= MULTIPLICADOR_FASE_ALTA
    puntos_base = regalia + (goles_totales * BONO_POR_GOL)

    # Todos los usuarios que tienen la estampa de esta ciudad en su álbum (dueño incluido, si aplica)
    ids_con_estampa = {
        str(doc["user_id"])
        for doc in db['user_albums'].find({"owned_ciudades": ciudad_id}, {"user_id": 1})
    }

    owner_user_id = ciudad.get("owner_user_id", 0)
    ahora = datetime.now()

    if _tiene_dueno(owner_user_id):
        dueno_str = str(owner_user_id)
        dueno_tiene_estampa = dueno_str in ids_con_estampa
        total_dueno = round(puntos_base * MULTIPLICADOR_SINERGIA) if dueno_tiene_estampa else puntos_base

        dueno_oid = ObjectId(dueno_str)
        db['usuarios'].update_one({"_id": dueno_oid}, {"$inc": {"monto": total_dueno}})
        db['city_ownerships'].update_one(
            {"ciudad_id": ciudad_id, "status": ESTADO_SEDE_ACTIVO},
            {"$inc": {"total_revenue_earned": total_dueno, "matches_hosted_count": 1}}
        )
        db['city_revenue_history'].insert_one({
            "user_id": dueno_oid,
            "ciudad_id": ciudad_id,
            "match_id": match_id,
            "fase_id": fase_id,
            "total_earned": total_dueno,
            "album_synergy_applied": dueno_tiene_estampa,
            "created_at": ahora
        })
        ids_con_estampa.discard(dueno_str)  # el dueño ya cobró arriba, no cobra pasivo de nuevo

    # Recompensa pasiva (+20 pts) para todo el resto de usuarios que tienen la estampa
    for user_id_str in ids_con_estampa:
        usuario_oid = ObjectId(user_id_str)
        db['usuarios'].update_one({"_id": usuario_oid}, {"$inc": {"monto": BONUS_PASIVO_ALBUM}})
        db['city_revenue_history'].insert_one({
            "user_id": usuario_oid,
            "ciudad_id": ciudad_id,
            "match_id": match_id,
            "fase_id": fase_id,
            "total_earned": BONUS_PASIVO_ALBUM,
            "album_synergy_applied": False,
            "created_at": ahora
        })
