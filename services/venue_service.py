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
  pueden vender mientras están jugando), aquí la regla de negocio dice
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
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import IMAGENES_PAISES_URL, MONGODB_URI
from services import niveles_service

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


SIN_DUENO = [0, "0", None, ""]


def _filtro_directorio(texto: str = "", usuario_id: Optional[str] = None, estado: str = "") -> Dict[str, Any]:
    """
    Filtro de Mongo del Directorio de Sedes. 'estado': "" (todas), "disponible", "mias" u
    "ocupada" (de otros usuarios). Se resuelve en el servidor -- antes se filtraba en el navegador
    sobre las primeras 50 ciudades, así que "Mis sedes" no encontraba las tuyas si no estaban ahí.
    El texto se escapa: es input del usuario usado como regex.
    """
    filtro: Dict[str, Any] = {}
    if texto:
        patron = re.escape(texto)
        filtro["$or"] = [
            {"nombre": {"$regex": patron, "$options": "i"}},
            {"pais": {"$regex": patron, "$options": "i"}}
        ]
    if estado == "disponible":
        filtro["owner_user_id"] = {"$in": SIN_DUENO}
    elif estado == "mias":
        filtro["owner_user_id"] = str(usuario_id) if usuario_id else "__nadie__"
    elif estado == "ocupada":
        filtro["owner_user_id"] = {"$nin": SIN_DUENO + ([str(usuario_id)] if usuario_id else [])}
    return filtro


def contar_ciudades_directorio(texto: str = "", usuario_id: Optional[str] = None, estado: str = "") -> int:
    return db['ciudades'].count_documents(_filtro_directorio(texto, usuario_id, estado))


def buscar_ciudades_directorio(texto: str = "", usuario_id: Optional[str] = None, limite: int = 50,
                               estado: str = "", saltar: int = 0) -> List[dict]:
    """Página de resultados del Directorio de Sedes (ver _filtro_directorio), ordenada por país y ciudad."""
    ciudades = list(db['ciudades'].find(
        _filtro_directorio(texto, usuario_id, estado),
        {"id": 1, "nombre": 1, "estadio": 1, "tipo": 1, "pais_id": 1, "pais": 1, "owner_user_id": 1, "estadio_imagen": 1}
    ).sort([("pais", 1), ("nombre", 1)]).skip(max(0, saltar)).limit(limite))

    programados = partidos_programados([c["id"] for c in ciudades])
    estampas = _estampas_ciudades(usuario_id)
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
            "es_mia": tiene_dueno and usuario_id is not None and str(owner_user_id) == str(usuario_id),
            "estadio_img": f"{IMAGENES_PAISES_URL}/{c['estadio_imagen']}" if c.get("estadio_imagen") else None,
            "programados": (programados.get(c["id"]) or {}).get("n", 0),
            "proximo": (programados.get(c["id"]) or {}).get("proximo"),
            "tengo_estampa": c["id"] in estampas,
        })
    return resultado


# ==========================================
# Datos para las vistas (directorio y portafolio)
# ==========================================
def partidos_programados(ids_ciudades: Optional[List[int]] = None) -> Dict[int, dict]:
    """{ciudad_id: {'n': partidos por jugarse ahí, 'proximo': el primero}} (juegos 'creado' con sede asignada)."""
    filtro: Dict[str, Any] = {"estado": "creado", "ubicacion.id": {"$exists": True}}
    if ids_ciudades is not None:
        filtro["ubicacion.id"] = {"$in": list(ids_ciudades)}
    salida: Dict[int, dict] = {}
    for j in db['juegos'].find(filtro, {"ubicacion.id": 1, "fecha": 1, "hora": 1, "fase_id": 1,
                                        "equipo_local.id": 1, "equipo_local.nombre": 1, "equipo_visitante.id": 1,
                                        "equipo_visitante.nombre": 1}).sort([("fecha", 1), ("hora", 1)]):
        cid = (j.get("ubicacion") or {}).get("id")
        d = salida.setdefault(cid, {"n": 0, "proximo": None})
        d["n"] += 1
        if d["proximo"] is None:
            loc, vis = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
            from services.tecnicos_service import fecha_corta
            d["proximo"] = {"id": str(j["_id"]), "fecha": j.get("fecha"), "fecha_txt": fecha_corta(j.get("fecha")), "hora": j.get("hora"), "fase_alta": (j.get("fase_id") or 0) >= FASE_ID_BONO_ALTO,
                            "local": loc.get("nombre"), "local_id": loc.get("id"), "visita": vis.get("nombre"), "visita_id": vis.get("id")}
    return salida


def _estampas_ciudades(usuario_id: Optional[str]) -> set:
    if not usuario_id:
        return set()
    album = db['user_albums'].find_one({"user_id": ObjectId(str(usuario_id))}, {"owned_ciudades": 1}) or {}
    return set(album.get("owned_ciudades") or [])


def resumen_directorio(usuario_id: str) -> dict:
    """Encabezado del Directorio: cupos del usuario, totales y las mejores OPORTUNIDADES (sedes libres con más partidos
    programados: cada partido paga regalía al dueño)."""
    total = db['ciudades'].count_documents({})
    libres = db['ciudades'].count_documents({"owner_user_id": {"$in": SIN_DUENO}})
    mias = db['city_ownerships'].count_documents({"user_id": ObjectId(str(usuario_id)), "status": ESTADO_SEDE_ACTIVO})
    programados = partidos_programados()
    ids = list(programados)
    libres_con_partidos = {c["id"]: c for c in db['ciudades'].find({"id": {"$in": ids}, "owner_user_id": {"$in": SIN_DUENO}},
                                                                    {"id": 1, "nombre": 1, "estadio": 1, "pais_id": 1, "pais": 1, "estadio_imagen": 1})}
    estampas = _estampas_ciudades(usuario_id)
    orden = sorted(libres_con_partidos, key=lambda cid: (-programados[cid]["n"], programados[cid]["proximo"]["fecha"] or ""))
    oportunidades = []
    for cid in orden[:6]:
        c, p = libres_con_partidos[cid], programados[cid]
        # regalía esperada: base (×3 en fase alta) + goles promedio del torneo (~3,8) × bono por gol
        estimada = round(p["n"] * (REGALIA_BASE + 3.8 * BONO_POR_GOL) * (MULTIPLICADOR_SINERGIA if cid in estampas else 1))
        oportunidades.append({"ciudad_id": cid, "nombre": c.get("nombre"), "estadio": c.get("estadio"), "pais_id": c.get("pais_id"),
                              "pais_nombre": c.get("pais"), "programados": p["n"], "proximo": p["proximo"],
                              "estadio_img": f"{IMAGENES_PAISES_URL}/{c['estadio_imagen']}" if c.get("estadio_imagen") else None,
                              "tengo_estampa": cid in estampas, "regalia_estimada": estimada, "costo": COSTO_BASE_SEDE})
    return {"total": total, "libres": libres, "ocupadas": total - libres, "mias": mias, "max_total": MAX_CIUDADES_TOTAL,
            "max_por_pais": MAX_CIUDADES_POR_PAIS, "con_partidos": len(programados), "oportunidades": oportunidades,
            "reglas": {"base": REGALIA_BASE, "fase_alta": MULTIPLICADOR_FASE_ALTA, "por_gol": BONO_POR_GOL,
                       "sinergia": MULTIPLICADOR_SINERGIA, "pasivo": BONUS_PASIVO_ALBUM, "costo": COSTO_BASE_SEDE,
                       "reembolso": int(PORCENTAJE_REEMBOLSO_VENTA * 100)}}


def obtener_portafolio_vista(user_id: str) -> dict:
    """Portafolio para la vista: cada sede con su recupero (ganado vs. pagado), sinergia de álbum, próximo partido y últimas
    regalías; totales; y la serie de ingresos acumulados de las sedes (para el gráfico)."""
    usuario_oid = ObjectId(str(user_id))
    sedes = obtener_portafolio_sedes(user_id)
    ids = [s["ciudad_id"] for s in sedes]
    programados = partidos_programados(ids)
    estampas = _estampas_ciudades(user_id)
    imgs = {c["id"]: c.get("estadio_imagen") for c in db['ciudades'].find({"id": {"$in": ids}}, {"id": 1, "estadio_imagen": 1})}
    desde = {s["ciudad_id"]: s.get("purchased_at") for s in sedes}
    historial = [h for h in db['city_revenue_history'].find({"user_id": usuario_oid, "ciudad_id": {"$in": ids}}).sort("created_at", 1)
                 if not desde.get(h["ciudad_id"]) or h["created_at"] >= desde[h["ciudad_id"]]]
    por_ciudad: Dict[int, List[dict]] = {}
    for h in historial:
        por_ciudad.setdefault(h["ciudad_id"], []).append(h)
    for s in sedes:
        ganado, pagado = s.get("total_revenue_earned", 0), s.get("purchase_price") or COSTO_BASE_SEDE
        p = programados.get(s["ciudad_id"]) or {}
        s.update({"recupero_pct": round(ganado / pagado * 100) if pagado else 0, "neto": ganado - pagado,
                  "tengo_estampa": s["ciudad_id"] in estampas, "programados": p.get("n", 0), "proximo": p.get("proximo"),
                  "reembolso": round(pagado * PORCENTAJE_REEMBOLSO_VENTA),
                  "estadio_img": f"{IMAGENES_PAISES_URL}/{imgs[s['ciudad_id']]}" if imgs.get(s["ciudad_id"]) else None,
                  "ultimas": [{"monto": h["total_earned"], "sinergia": h.get("album_synergy_applied"), "fecha": h["created_at"]}
                              for h in reversed(por_ciudad.get(s["ciudad_id"], [])[-3:])]})
    sedes.sort(key=lambda s: -s.get("total_revenue_earned", 0))
    acumulado, serie = 0, []
    for h in historial:
        acumulado += h["total_earned"]
        serie.append({"x": h["created_at"].strftime("%d/%m %H:%M"), "y": acumulado})
    invertido = sum(s.get("purchase_price") or COSTO_BASE_SEDE for s in sedes)
    ganado = sum(s.get("total_revenue_earned", 0) for s in sedes)
    return {"sedes": sedes, "serie": serie, "invertido": invertido, "ganado": ganado, "neto": ganado - invertido,
            "recupero_pct": round(ganado / invertido * 100) if invertido else 0,
            "partidos": sum(s.get("matches_hosted_count", 0) for s in sedes),
            "con_sinergia": sum(1 for s in sedes if s["tengo_estampa"]), "programados": sum(s["programados"] for s in sedes),
            "max_total": MAX_CIUDADES_TOTAL, "max_por_pais": MAX_CIUDADES_POR_PAIS,
            "reglas": {"base": REGALIA_BASE, "fase_alta": MULTIPLICADOR_FASE_ALTA, "por_gol": BONO_POR_GOL, "sinergia": MULTIPLICADOR_SINERGIA}}


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
        raise ValueError(f"Ya tienes {MAX_CIUDADES_POR_PAIS} sedes activas de este país (máximo permitido)")

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

    # XP de niveles (nunca lanza). Vender no da XP.
    niveles_service.otorgar_xp(usuario_oid, "SEDE_COMPRA", inversion["_id"])
    niveles_service.otorgar_logro(usuario_oid, "PRIMERA_SEDE")

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
        niveles_service.otorgar_xp(dueno_oid, "SEDE_REGALIA", f"{match_id}:{ciudad_id}")
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
