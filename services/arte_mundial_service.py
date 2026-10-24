"""
Póster y mascota oficiales de cada Mundial (motor en services/arte_mundial/, catálogo en config/arte_mundial.py).

En `mundiales.arte` se guarda la RECETA (no la imagen): {poster: {...}, mascota: {..., nombre}, version, elegido_en}.
Los SVG se dibujan por pedido (`svg_poster` / `svg_mascota`) y se cachean en memoria por (año, versión); las rutas
los sirven con caché del navegador y la URL lleva la versión, así un cambio del admin se ve al instante.
- `generar_para(mundial)`: al crear un Mundial (gancho en mundial_service.crear_nuevo_mundial) o con
  generar_arte_mundial.py para uno existente. Evita repetir combinaciones ya usadas (colección arte_mundial_usado).
- `propuestas(anio, tanda)`: 3 alternativas para el panel del admin; `elegir(anio, propuesta)` las aplica, solo
  antes de que se juegue el primer partido del Mundial.
- Catálogo de estampas `arte_mundial` (id = año*10 + 1 póster / + 2 mascota) para el álbum (página "Mundiales").
"""
import hashlib
import random
from datetime import datetime
from typing import Dict, List, Optional

import certifi
from pymongo import MongoClient

from config import arte_mundial as C
from config.settings import MONGODB_URI
from services.arte_mundial import mascota as MA
from services.arte_mundial import poster as PO

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database("mundial")

_cache_svg: Dict[tuple, str] = {}
_cache_arte: Dict[int, tuple] = {}   # anio -> (expira, datos)


def _region(pais: dict) -> str:
    return C.REGION_POR_PAIS.get(pais.get("nombre")) or C.REGION_POR_CONFEDERACION.get(pais.get("confederacion_id"), "europa")


def _receta(pais: dict, anio, semilla, usados_poster: set, usados_mascota: set) -> dict:
    """Póster + mascota para la sede; reintenta hasta encontrar una combinación que no se haya usado."""
    nombre_pais, region = pais["nombre"], _region(pais)
    r = random.Random(semilla)
    for _ in range(40):
        poster = PO.receta_aleatoria(C.REGIONES[region], C.ICONOS_POR_PAIS.get(nombre_pais), r, C.LEMAS)
        if PO.clave(poster) not in usados_poster:
            break
    bases = C.MASCOTAS_POR_PAIS.get(nombre_pais) or C.MASCOTAS_POR_REGION.get(region, ["leon"])
    accesorios = C.ACCESORIOS_POR_PAIS.get(nombre_pais) or C.ACCESORIOS_POR_REGION.get(region, ["ninguno"])
    for _ in range(40):
        mascota = MA.receta_aleatoria(bases, accesorios, r)
        mascota["nombre"] = MA.nombre_para(mascota["base"], C.NOMBRES_POR_BASE, r, usados_mascota)
        if f'{mascota["base"]}|{mascota["nombre"]}' not in usados_mascota and mascota["nombre"] not in usados_mascota:
            break
    return {"poster": poster, "mascota": mascota}


def _usados(excepto_anio=None):
    usados_p, usados_m = set(), set()
    for m in db["mundiales"].find({"arte": {"$exists": True}}, {"anio": 1, "arte": 1}):
        if m.get("anio") == excepto_anio:
            continue
        a = m["arte"]
        usados_p.add(PO.clave(a["poster"]))
        usados_m.add(a["mascota"].get("nombre"))
        usados_m.add(f'{a["mascota"]["base"]}|{a["mascota"].get("nombre")}')
    for u in db["arte_mundial_usado"].find({}, {"_id": 1}):
        (usados_p if u["_id"].startswith("p:") else usados_m).add(u["_id"][2:])
    return usados_p, usados_m


def _ya_empezo(mundial: dict) -> bool:
    return bool(db["juegos"].find_one({"mundial_id": str(mundial["_id"]), "estado": "finalizado"}, {"_id": 1}))


def _guardar(mundial: dict, receta: dict, origen: str) -> dict:
    version = int((mundial.get("arte") or {}).get("version", 0)) + 1
    arte = {**receta, "version": version, "origen": origen, "elegido_en": datetime.utcnow()}
    # generado con el torneo ya en marcha (p. ej. el Mundial que existía antes de esta función): el admin todavía
    # no tuvo la oportunidad de elegir, así que puede hacerlo una vez aunque ya se hayan jugado partidos
    if origen == "automatico" and _ya_empezo(mundial):
        arte["tardio"] = True
    db["mundiales"].update_one({"_id": mundial["_id"]}, {"$set": {"arte": arte}})
    for k in (f'p:{PO.clave(receta["poster"])}', f'm:{receta["mascota"]["base"]}|{receta["mascota"]["nombre"]}'):
        db["arte_mundial_usado"].update_one({"_id": k}, {"$setOnInsert": {"anio": mundial.get("anio")}}, upsert=True)
    _registrar_estampas(mundial, receta)
    _cache_arte.pop(mundial.get("anio"), None)
    return arte


def _registrar_estampas(mundial: dict, receta: dict) -> None:
    """Catálogo de estampas del álbum (página especial 'Mundiales'): póster y mascota de cada edición."""
    anio = mundial.get("anio")
    pais = db["paises"].find_one({"id": mundial.get("pais_id")}, {"nombre": 1}) or {}
    for k, (tipo, nombre) in enumerate((("poster", f"Póster {pais.get('nombre', '')} {anio}"),
                                        ("mascota", receta["mascota"]["nombre"])), start=1):
        db["arte_mundial"].update_one({"id": int(anio) * 10 + k}, {"$set": {
            "id": int(anio) * 10 + k, "anio": anio, "tipo": tipo, "nombre": nombre, "pais_id": mundial.get("pais_id"),
            "pais": pais.get("nombre")}}, upsert=True)


def generar_para(mundial: dict, forzar: bool = False) -> Optional[dict]:
    """Póster y mascota para un Mundial (no hace nada si ya tiene, salvo forzar). Nunca lanza."""
    try:
        if mundial.get("arte") and not forzar:
            return mundial["arte"]
        pais = db["paises"].find_one({"id": mundial.get("pais_id")}, {"nombre": 1, "confederacion_id": 1})
        if not pais:
            return None
        usados_p, usados_m = _usados(excepto_anio=mundial.get("anio"))
        receta = _receta(pais, mundial.get("anio"), f'{mundial.get("anio")}:{pais["nombre"]}:0', usados_p, usados_m)
        return _guardar(mundial, receta, "automatico")
    except Exception as e:
        print(f"No se pudo generar el arte del Mundial: {e}")
        return None


def propuestas(anio: int, tanda: int = 1, cantidad: int = 3) -> List[dict]:
    mundial = db["mundiales"].find_one({"anio": anio})
    if not mundial:
        return []
    pais = db["paises"].find_one({"id": mundial.get("pais_id")}, {"nombre": 1, "confederacion_id": 1})
    usados_p, usados_m = _usados(excepto_anio=anio)
    salida = []
    for i in range(cantidad):
        receta = _receta(pais, anio, f"{anio}:{pais['nombre']}:t{tanda}:{i}", usados_p, usados_m)
        usados_p.add(PO.clave(receta["poster"]))
        usados_m.add(receta["mascota"]["nombre"])
        salida.append(receta)
    return salida


def puede_cambiar(anio: int) -> bool:
    """
    El arte se puede cambiar mientras no se haya jugado ningún partido de ese Mundial; si se generó con el torneo ya
    empezado ('tardio') y nadie eligió todavía, el admin puede elegir una vez.
    """
    mundial = db["mundiales"].find_one({"anio": anio}, {"_id": 1, "arte": 1})
    if not mundial:
        return False
    arte = mundial.get("arte") or {}
    return not _ya_empezo(mundial) or (arte.get("tardio") and arte.get("origen") == "automatico")


def elegir(anio: int, receta: dict) -> dict:
    mundial = db["mundiales"].find_one({"anio": anio})
    if not mundial:
        raise ValueError("No existe ese Mundial")
    if not puede_cambiar(anio):
        raise ValueError("El Mundial ya empezó: su póster y su mascota ya son oficiales")
    if receta.get("poster", {}).get("grilla") not in PO.GRILLAS or receta.get("mascota", {}).get("base") not in MA.BASES:
        raise ValueError("Propuesta inválida")
    return _guardar(mundial, {"poster": receta["poster"], "mascota": receta["mascota"]}, "admin")


# --- Lectura para vistas e imágenes ------------------------------------------------------------------------------
def _datos(anio) -> Optional[dict]:
    try:
        anio = int(anio)
    except (TypeError, ValueError):
        return None
    ahora = datetime.utcnow().timestamp()
    en_cache = _cache_arte.get(anio)
    if en_cache and en_cache[0] > ahora:
        return en_cache[1]
    m = db["mundiales"].find_one({"anio": anio}, {"anio": 1, "pais_id": 1, "arte": 1, "activo": 1})
    datos = None
    if m and m.get("arte"):
        pais = db["paises"].find_one({"id": m.get("pais_id")}, {"nombre": 1, "colores": 1, "bandera": 1}) or {}
        datos = {"anio": anio, "pais_id": m.get("pais_id"), "pais": pais.get("nombre", ""), "bandera": pais.get("bandera"),
                 "colores": pais.get("colores") or [], "arte": m["arte"], "activo": bool(m.get("activo"))}
    _cache_arte[anio] = (ahora + 30, datos)
    return datos


def svg_poster(anio) -> Optional[str]:
    d = _datos(anio)
    if not d:
        return None
    clave = ("poster", d["anio"], d["arte"]["version"])
    if clave not in _cache_svg:
        _cache_svg[clave] = PO.dibujar(d["arte"]["poster"], d["colores"], d["pais"], d["anio"], C.TITULO_TORNEO)
    return _cache_svg[clave]


def svg_mascota(anio) -> Optional[str]:
    d = _datos(anio)
    if not d:
        return None
    clave = ("mascota", d["anio"], d["arte"]["version"])
    if clave not in _cache_svg:
        _cache_svg[clave] = MA.dibujar(d["arte"]["mascota"], d["colores"], d["anio"])
    return _cache_svg[clave]


def svg_de_receta(anio: int, receta: dict, que: str) -> str:
    """Dibujo de una propuesta (panel del admin) sin guardarla."""
    d = _datos(anio) or {}
    m = db["mundiales"].find_one({"anio": anio}, {"pais_id": 1}) or {}
    pais = db["paises"].find_one({"id": m.get("pais_id")}, {"nombre": 1, "colores": 1}) or {}
    if que == "poster":
        return PO.dibujar(receta["poster"], pais.get("colores") or [], pais.get("nombre", ""), anio, C.TITULO_TORNEO)
    return MA.dibujar(receta["mascota"], pais.get("colores") or [], anio)


def arte_de(anio) -> Optional[dict]:
    """Lo que necesitan las vistas (Jinja global `arte_mundial`): URLs versionadas, nombre y ficha de la mascota."""
    d = _datos(anio)
    if not d:
        return None
    a, v = d["arte"], d["arte"]["version"]
    mas = a["mascota"]
    base = mas["base"]
    return {
        "anio": d["anio"], "pais": d["pais"], "pais_id": d["pais_id"], "bandera": d["bandera"], "activo": d["activo"],
        "poster_url": f"/mundial/arte/{d['anio']}/poster.svg?v={v}", "mascota_url": f"/mundial/arte/{d['anio']}/mascota.svg?v={v}",
        "mascota_nombre": mas.get("nombre"), "mascota_que": C.DESCRIPCION_BASE.get(base, base),
        "mascota_tipo": "fruta" if base in MA.FRUTAS else "animal", "pose": mas.get("pose"), "accesorio": mas.get("accesorio"),
        "poster": a["poster"], "origen": a.get("origen"), "version": v,
    }


def arte_activo() -> Optional[dict]:
    m = db["mundiales"].find_one({"activo": True}, {"anio": 1})
    return arte_de(m["anio"]) if m else None


def historico() -> List[dict]:
    return [x for x in (arte_de(m["anio"]) for m in db["mundiales"].find({"arte": {"$exists": True}}, {"anio": 1}).sort("anio", -1)) if x]


_cache_tema: Dict[int, dict] = {}


def tema_sede(pais_id) -> dict:
    """
    Colores del encabezado del inicio a partir de la bandera REAL del anfitrión (paises.colores, misma paleta que el
    póster): fondo en degradé del color dominante oscurecido, franja diagonal y detalles en el color de acento, y el
    título en el acento si se lee bien sobre el fondo (si no, oro). Variables CSS --sede-*.
    """
    if pais_id in _cache_tema:
        return _cache_tema[pais_id]
    from services.arte_mundial import paleta as PA
    pais = db["paises"].find_one({"id": pais_id}, {"colores": 1}) or {}
    p = PA.de_bandera(pais.get("colores") or [])
    # el fondo siempre oscuro (texto blanco legible con cualquier bandera): el dominante bajado a un tono profundo
    factor = 0.75
    while factor > 0.2 and PA.luminancia(PA.oscurecer(p["dominante"], factor)) > 0.035:
        factor -= 0.03
    fondo = PA.oscurecer(p["dominante"], factor)
    fondo_profundo = PA.oscurecer(p["dominante"], factor * 0.55)
    acento = p["acento"] if PA.contraste(p["acento"], fondo) >= 4.5 else PA.ORO
    tema = {"fondo": fondo, "fondo_profundo": fondo_profundo, "brillo": PA.oscurecer(p["dominante"], min(1.0, factor * 1.45)),
            "acento": acento, "acento_claro": PA.aclarar(acento, 0.55), "acento_oscuro": PA.oscurecer(acento, 0.6)}
    _cache_tema[pais_id] = tema
    return tema


def etag(svg: str) -> str:
    return hashlib.md5(svg.encode()).hexdigest()
