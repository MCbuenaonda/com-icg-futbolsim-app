"""
Forma de los jugadores para el Once Ideal: historial partido a partido del Mundial activo, nivel de forma por sus
últimos partidos, ficha del jugador (ventana de /once-ideal) y el Ojeador (sugerencias pagas por posición).

- Los puntos fantasy de cada partido se RECONSTRUYEN desde los partidos guardados (goleadores, asistencias y tarjetas de
  los eventos vía estadisticas_service._agregar_jugadores_mundial, valla invicta por el marcador): sirven para todos los
  partidos ya jugados. La calificación del partido existe desde que se guarda 'resultado.calificaciones'.
- Forma = promedio de los últimos PARTIDOS_FORMA partidos de (puntos + calificación sobre la base × 20), ubicada en
  percentiles contra todos los jugadores con al menos MINIMO_PARTIDOS_FORMA partidos.
- Todo se calcula una vez por (Mundial, partidos jugados) y queda en memoria.
"""
import bisect
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from config import fantasy as CFF
from services import estadisticas_service as E
from services import fantasy_service as FS

db = FS.db
_cache = {"clave": None, "datos": None}
_candado = threading.Lock()
PESO_CALIFICACION = 20


def _puntos_partido(m: dict, linea: str, gc: int) -> int:
    pts = m["goles"] * FS.PUNTOS_GOL + m["asistencias"] * FS.PUNTOS_ASISTENCIA
    pts += m["amarillas"] * FS.PUNTOS_TARJETA_AMARILLA + m["rojas"] * FS.PUNTOS_TARJETA_ROJA
    if linea in ("PORTERO", "DEFENSA") and gc == 0:
        pts += FS.PUNTOS_ARQUERIA_EN_CERO
    return pts


def _indice(p: dict) -> float:
    cal = p.get("calificacion")
    return p["puntos"] + ((cal - CFF.RATING_BASE_PAGO) * PESO_CALIFICACION if cal is not None else 0.0)


def _construir(clave: tuple) -> dict:
    # Reusa los partidos y el agregado de /estadisticas si están al día (cargarlos de Atlas lleva varios segundos)
    if E._cache_vista.get("clave") == clave and E._cache_vista.get("agregado") is not None:
        juegos = sorted(E._cache_vista["juegos"].values(), key=lambda j: (j.get("fecha") or "", j.get("hora") or ""))
        agregado = E._cache_vista["agregado"]
        cals = {str(j["_id"]): (j.get("resultado") or {}).get("calificaciones") for j in db["juegos"].find(
            {**E._filtro_finalizados(), "resultado.calificaciones": {"$exists": True}}, {"resultado.calificaciones": 1})}
    else:
        proyeccion = dict(E.PROYECCION_JUEGOS_MUNDIAL)
        proyeccion["resultado.calificaciones"] = 1
        juegos = list(db["juegos"].find(E._filtro_finalizados(), proyeccion).sort([("fecha", 1), ("hora", 1)]))
        agregado = E._agregar_jugadores_mundial(juegos) if juegos else {}
        cals = {str(j["_id"]): (j.get("resultado") or {}).get("calificaciones") for j in juegos}
    por_id = {str(j["_id"]): (orden, j) for orden, j in enumerate(juegos)}
    historial: Dict[int, List[dict]] = {}
    for jid, a in agregado.items():
        jugados = a["partidos_por"].get("partidos") or {}
        if not jugados:
            continue
        linea = CFF.LINEA_DE_POSICION.get(a.get("posicion_id"), "MEDIO")
        filas = []
        for juego_id in jugados:
            orden, j = por_id[juego_id]
            res = j.get("resultado") or {}
            local, visita = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
            es_local = local.get("id") == a.get("pais_id")
            gf = (res.get("goles_local") if es_local else res.get("goles_visitante")) or 0
            gc = (res.get("goles_visitante") if es_local else res.get("goles_local")) or 0
            rival = visita if es_local else local
            m = {k: (a["partidos_por"].get(k) or {}).get(juego_id, 0) for k in ("goles", "asistencias", "amarillas", "rojas")}
            cal = (cals.get(juego_id) or {}).get(str(jid))
            filas.append({"orden": orden, "juego_id": juego_id, "fecha": j.get("fecha"), "rival": rival.get("nombre"),
                          "rival_id": rival.get("id"), "bandera": rival.get("bandera") or "", "local": es_local,
                          "marcador": f"{gf}-{gc}", "resultado": "V" if gf > gc else ("D" if gf < gc else "E"),
                          "valla": linea in ("PORTERO", "DEFENSA") and gc == 0, **m,
                          "puntos": _puntos_partido(m, linea, gc), "calificacion": cal})
        filas.sort(key=lambda f: f["orden"])
        historial[jid] = filas
    # Forma: promedio de los últimos partidos y su percentil
    forma = {}
    for jid, filas in historial.items():
        if len(filas) < CFF.MINIMO_PARTIDOS_FORMA:
            continue
        ult = filas[-CFF.PARTIDOS_FORMA:]
        forma[jid] = sum(_indice(p) for p in ult) / len(ult)
    ordenados = sorted(forma.values())
    percentiles = {jid: bisect.bisect_left(ordenados, v) / max(1, len(ordenados) - 1) for jid, v in forma.items()}
    return {"historial": historial, "forma": forma, "percentil": percentiles, "partidos": len(juegos)}


_refrescando = {"activo": False}


def _refrescar(clave: tuple) -> None:
    try:
        with _candado:
            if _cache["clave"] != clave:
                _cache.update(clave=clave, datos=_construir(clave))
    finally:
        _refrescando["activo"] = False


def datos(esperar: bool = True) -> Optional[dict]:
    """
    Historial y forma de todos los jugadores, por (Mundial, partidos jugados). Con esperar=False nunca bloquea: si hay
    datos de un partido atrás los devuelve y recalcula en un hilo (None si todavía no hay nada calculado).
    """
    jornada = FS.jornada_actual()
    clave = (jornada["mundial_id"], jornada["jugados"])
    if _cache["clave"] == clave and _cache["datos"]:
        return _cache["datos"]
    if not esperar:
        if not _refrescando["activo"]:
            _refrescando["activo"] = True
            threading.Thread(target=_refrescar, args=(clave,), daemon=True).start()
        return _cache["datos"]
    with _candado:
        if _cache["clave"] != clave or not _cache["datos"]:
            _cache.update(clave=clave, datos=_construir(clave))
    return _cache["datos"]


def nivel_de(jugador_id: int, d: Optional[dict] = None) -> dict:
    """{codigo, etiqueta, percentil, indice, partidos} del nivel de forma (codigo None = sin partidos suficientes)."""
    d = d or datos()
    partidos = len(d["historial"].get(jugador_id) or [])
    if jugador_id not in d["percentil"]:
        return {"codigo": None, "etiqueta": "Sin datos", "percentil": None, "indice": None, "partidos": partidos}
    p = d["percentil"][jugador_id]
    codigo, etiqueta = next((c, e) for minimo, c, e in CFF.NIVELES_FORMA if p >= minimo)
    return {"codigo": codigo, "etiqueta": etiqueta, "percentil": round(p, 3), "indice": round(d["forma"][jugador_id], 1),
            "partidos": partidos}


def niveles_de(ids: List[int], esperar: bool = False) -> Dict[int, dict]:
    """Niveles de forma de varios jugadores ({} si todavía se están calculando y esperar=False)."""
    d = datos(esperar)
    return {i: nivel_de(i, d) for i in ids} if d else {}


def _calendario() -> Dict[int, dict]:
    try:
        from services.corporativo_mercado_service import calendario_paises
        return calendario_paises()
    except Exception:
        return {}


def _proximo(pais_id: int, cal: Dict[int, dict]) -> Optional[dict]:
    c = cal.get(pais_id)
    if not c:
        return None
    rival = db["paises"].find_one({"id": c.get("rival_id")}, {"nombre": 1, "bandera": 1}) or {}
    return {"faltan": c.get("faltan"), "rival": rival.get("nombre"), "bandera": rival.get("bandera") or "", "local": c.get("local")}


def ficha(jugador_id: int, usuario_id: Optional[str] = None) -> Optional[dict]:
    """Ficha del jugador para la ventana del Once Ideal: datos, forma, próximo partido, historial y lo que te pagó."""
    j = db["jugadores"].find_one({"id": jugador_id}, {"_id": 0, "id": 1, "nombre": 1, "edad": 1, "overall": 1, "posicion_id": 1,
                                                      "pais_id": 1, "numero": 1, "leyenda": 1, "rendimiento": 1, "pie_habil": 1,
                                                      "estado_animo": 1})
    if not j:
        return None
    pais = db["paises"].find_one({"id": j.get("pais_id")}, {"nombre": 1, "bandera": 1}) or {}
    pos = db["posiciones"].find_one({"id": j.get("posicion_id")}, {"nombre": 1, "siglas": 1}) or {}
    d = datos()
    historial = d["historial"].get(jugador_id) or []
    eliminados = FS.paises_eliminados()
    ganado, escuadra = 0, None
    if usuario_id:
        uid = ObjectId(usuario_id)
        tot = list(db["fantasy_points_history"].aggregate([
            {"$match": {"user_id": uid, "jugador_id": jugador_id}},
            {"$group": {"_id": None, "monto": {"$sum": "$monto_otorgado"}, "puntos": {"$sum": "$puntos_finales"}, "n": {"$sum": 1}}}]))
        ganado = tot[0] if tot else {"monto": 0, "puntos": 0, "n": 0}
        eq = db["fantasy_teams"].find_one({"user_id": uid, "mundial_id": FS.jornada_actual()["mundial_id"], "lineup": jugador_id},
                                          {"escuadra": 1, "formacion": 1})
        escuadra = {"numero": eq.get("escuadra", 1), "formacion": eq.get("formacion")} if eq else None
    totales = {k: sum(p[k] for p in historial) for k in ("goles", "asistencias", "amarillas", "rojas", "puntos")}
    totales["vallas"] = sum(1 for p in historial if p["valla"])
    return {
        "id": j["id"], "nombre": j.get("nombre"), "edad": j.get("edad"), "overall": round(j.get("overall") or 0, 1),
        "numero": j.get("numero"), "leyenda": bool(j.get("leyenda")), "pie_habil": j.get("pie_habil"),
        "estado_animo": j.get("estado_animo"), "rendimiento": round(j.get("rendimiento") or 0, 1),
        "pais_id": j.get("pais_id"), "pais": pais.get("nombre"), "bandera": pais.get("bandera") or "",
        "posicion": pos.get("nombre"), "siglas": pos.get("siglas"), "linea": CFF.LINEA_DE_POSICION.get(j.get("posicion_id")),
        "eliminado": eliminados.get(j.get("pais_id")),
        "nivel": nivel_de(jugador_id, d), "proximo": _proximo(j.get("pais_id"), _calendario()),
        "partidos": [{k: v for k, v in p.items() if k != "orden"} for p in historial[-20:]],
        "totales": {**totales, "partidos": len(historial)},
        "ganado": ganado or None, "escuadra": escuadra,
    }


# --- Ojeador ---------------------------------------------------------------------------------------------------------
def _porque(filas: List[dict], proximo: Optional[dict]) -> str:
    ult = filas[-CFF.PARTIDOS_FORMA:]
    partes = []
    goles, asist = sum(p["goles"] for p in ult), sum(p["asistencias"] for p in ult)
    vallas = sum(1 for p in ult if p["valla"])
    if goles:
        partes.append(f"{goles} gol{'es' if goles != 1 else ''} en sus últimos {len(ult)}")
    if asist:
        partes.append(f"{asist} asistencia{'s' if asist != 1 else ''}")
    if vallas:
        partes.append(f"{vallas} valla{'s' if vallas != 1 else ''} invicta{'s' if vallas != 1 else ''}")
    cals = [p["calificacion"] for p in ult if p.get("calificacion") is not None]
    if cals:
        partes.append(f"calificación media {sum(cals) / len(cals):.1f}")
    if not partes:
        partes.append(f"{len(filas)} partidos jugados")
    if proximo:
        partes.append("juega el próximo partido" if proximo["faltan"] == 0 else f"juega en {proximo['faltan']} partidos")
    return " · ".join(partes)


def _sugerir(uid: ObjectId, posicion_id: int, nivel: str, escuadra: int) -> List[dict]:
    reglas = CFF.OJEADOR_NIVELES[nivel]
    d = datos()
    equipos = FS._escuadras_del_mundial(uid)
    en_equipos = {j for e in equipos for j in e["lineup"]}
    destino = next((e for e in equipos if e.get("escuadra", 1) == escuadra), None)
    destino_ids = set(destino["lineup"]) if destino else set()
    info_destino = list(db["jugadores"].find({"id": {"$in": list(destino_ids)}}, {"pais_id": 1, "leyenda": 1})) if destino_ids else []
    por_pais: Dict[int, int] = {}
    for j in info_destino:
        por_pais[j["pais_id"]] = por_pais.get(j["pais_id"], 0) + 1
    tiene_leyenda = any(j.get("leyenda") for j in info_destino)
    eliminados = FS.paises_eliminados()
    cal = _calendario()

    candidatos = []
    for j in db["jugadores"].find({"posicion_id": posicion_id}, {"id": 1, "pais_id": 1, "leyenda": 1}):
        jid = j["id"]
        p = d["percentil"].get(jid)
        if p is None or not (reglas["desde"] <= p < reglas["hasta"]):
            continue
        if jid in en_equipos or j.get("pais_id") in eliminados:
            continue
        if por_pais.get(j.get("pais_id"), 0) >= FS.MAX_JUGADORES_POR_PAIS or (j.get("leyenda") and tiene_leyenda):
            continue
        c = cal.get(j.get("pais_id"))
        faltan = c.get("faltan") if c else None
        if faltan is None or faltan > CFF.JUEGA_PRONTO_PARTIDOS * 3:
            continue
        pronto = 1.0 if faltan <= CFF.JUEGA_PRONTO_PARTIDOS else 0.5
        candidatos.append((d["forma"][jid] * pronto / (1 + faltan / 200), jid))
    candidatos.sort(reverse=True)
    sugerencias = []
    for _, jid in candidatos[:reglas["cantidad"]]:
        pais_id = next(j["pais_id"] for j in db["jugadores"].find({"id": jid}, {"pais_id": 1}))
        proximo = _proximo(pais_id, cal)
        sugerencias.append({"jugador_id": jid, "nivel": nivel_de(jid, d), "proximo": proximo,
                            "porque": _porque(d["historial"][jid], proximo)})
    return sugerencias


def consultar_ojeador(usuario_id: str, posicion_id: int, nivel: str, escuadra: int = 1) -> dict:
    """
    Sugerencias del Ojeador para UNA posición, según el nivel pagado (config/fantasy.OJEADOR_NIVELES). Cobro atómico;
    sin candidatos no cobra. La misma consulta (usuario, posición, nivel, equipo) es gratis hasta que se juegue otro
    partido. Devuelve {sugerencias: [... con los datos del jugador], cobrado, precio, gratis}.
    """
    if nivel not in CFF.OJEADOR_NIVELES:
        raise ValueError("Nivel del Ojeador desconocido")
    if not db["posiciones"].find_one({"id": posicion_id}, {"_id": 1}):
        raise ValueError("Posición desconocida")
    uid = ObjectId(usuario_id)
    usuario = db["usuarios"].find_one({"_id": uid}, {"monto": 1, "fantasy_escuadras": 1, "activo": 1})
    if not usuario or not usuario.get("activo", True):
        raise ValueError("Usuario no encontrado o inactivo")
    if escuadra < 1 or escuadra > FS.escuadras_desbloqueadas(usuario):
        raise ValueError("Ese equipo todavía no está desbloqueado")
    reglas = CFF.OJEADOR_NIVELES[nivel]
    jugados = FS.jornada_actual()["jugados"]
    clave = {"user_id": uid, "posicion_id": posicion_id, "nivel": nivel, "escuadra": escuadra, "jugados": jugados}
    previa = db["fantasy_ojeador"].find_one(clave)
    if previa:
        sugerencias, cobrado, gratis = previa["sugerencias"], 0, True
    else:
        sugerencias = _sugerir(uid, posicion_id, nivel, escuadra)
        cobrado, gratis = 0, False
        if sugerencias:
            cobro = db["usuarios"].update_one({"_id": uid, "monto": {"$gte": reglas["precio"]}}, {"$inc": {"monto": -reglas["precio"]}})
            if cobro.modified_count == 0:
                raise ValueError(f"El Ojeador {reglas['nombre']} cuesta {reglas['precio']} de saldo y no te alcanza")
            cobrado = reglas["precio"]
            pos = db["posiciones"].find_one({"id": posicion_id}, {"siglas": 1}) or {}
            db["fantasy_ojeador"].insert_one({**clave, "sugerencias": sugerencias, "precio": cobrado, "created_at": datetime.now()})
            db["fantasy_movimientos"].insert_one({"user_id": uid, "tipo": "OJEADOR", "monto": -cobrado, "escuadra": escuadra,
                                                  "detalle": f"Ojeador {reglas['nombre']} · {pos.get('siglas', '')}",
                                                  "created_at": datetime.now()})
    detalle = {j["id"]: j for j in FS.obtener_detalle_jugadores([s["jugador_id"] for s in sugerencias])}
    salida = [{**detalle[s["jugador_id"]], **s} for s in sugerencias if s["jugador_id"] in detalle]
    return {"sugerencias": salida, "cobrado": cobrado, "precio": reglas["precio"], "gratis": gratis, "nivel": nivel}


def niveles_ojeador() -> List[dict]:
    return [{"codigo": c, **v} for c, v in CFF.OJEADOR_NIVELES.items()]
