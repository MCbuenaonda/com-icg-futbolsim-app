"""
Árbitros: directorio (/arbitros/) y perfil (/arbitros/perfil?nombre=...).

Los partidos guardan solo el NOMBRE de cada árbitro (resultado.arbitros.{central, linea1, linea2,
cuarto}); el vínculo con la colección 'arbitros' (país, puesto) también es por nombre. Faltas y
tarjetas se cuentan de 'resultado.eventos' con el mismo criterio que la vista de estadísticas
(estadisticas_service._contar_faltas_tarjetas), solo para los partidos que dirigió como central.
"""
import certifi
from collections import defaultdict
from typing import Any, Dict, List, Optional

from pymongo import DESCENDING
from pymongo.mongo_client import MongoClient

from config.settings import MONGODB_URI
from services.estadisticas_service import _contar_faltas_tarjetas

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

ROLES = [("central", "Central"), ("linea1", "Línea 1"), ("linea2", "Línea 2"), ("cuarto", "4to árbitro")]


def _datos_arbitros() -> Dict[str, dict]:
    return {a["nombre"]: a for a in db["arbitros"].find({}, {"_id": 0, "nombre": 1, "pais": 1, "pais_id": 1, "puesto": 1})}


def listar_arbitros() -> List[dict]:
    """Un renglón por árbitro que ya dirigió como central: partidos y promedios por partido."""
    filas = defaultdict(lambda: {"partidos": 0, "faltas": 0, "tarjetas": 0, "expulsiones": 0, "gana_local": 0})
    for j in db["juegos"].find({"estado": "finalizado", "resultado.arbitros.central": {"$ne": None}},
                               {"resultado.arbitros.central": 1, "resultado.eventos.tipo": 1, "resultado.ganador_lado": 1}):
        res = j.get("resultado") or {}
        nombre = (res.get("arbitros") or {}).get("central")
        if not nombre:
            continue
        faltas, tarjetas, expulsiones = _contar_faltas_tarjetas(res.get("eventos") or [])
        f = filas[nombre]
        f["partidos"] += 1
        f["faltas"] += faltas
        f["tarjetas"] += tarjetas
        f["expulsiones"] += expulsiones
        f["gana_local"] += 1 if res.get("ganador_lado") == "L" else 0
    datos = _datos_arbitros()
    resultado = []
    for nombre, f in filas.items():
        info = datos.get(nombre, {})
        n = f["partidos"]
        resultado.append({
            "nombre": nombre, "pais": info.get("pais", ""), "puesto": info.get("puesto", ""),
            "partidos": n, "faltas_prom": round(f["faltas"] / n, 1), "tarjetas_prom": round(f["tarjetas"] / n, 1),
            "expulsiones": f["expulsiones"], "pct_gana_local": round(100 * f["gana_local"] / n),
        })
    return sorted(resultado, key=lambda r: (-r["partidos"], r["nombre"]))


def perfil_arbitro(nombre: str) -> Optional[Dict[str, Any]]:
    """Partidos en los que participó (en cualquier rol) y estadísticas de los que dirigió como central."""
    filtro = {"estado": "finalizado", "$or": [{f"resultado.arbitros.{rol}": nombre} for rol, _ in ROLES]}
    juegos = list(db["juegos"].find(filtro, {
        "equipo_local": 1, "equipo_visitante": 1, "fecha": 1, "tag": 1, "fase_id": 1, "resultado.arbitros": 1,
        "resultado.goles_local": 1, "resultado.goles_visitante": 1, "resultado.ganador_lado": 1, "resultado.eventos.tipo": 1,
    }).sort([("fecha", DESCENDING)]))
    if not juegos:
        return None
    nombres_fase = {f["id"]: f.get("nombre", "") for f in db["fases"].find({}, {"id": 1, "nombre": 1})}
    info = _datos_arbitros().get(nombre, {})
    por_rol = {rol: 0 for rol, _ in ROLES}
    central = {"partidos": 0, "faltas": 0, "tarjetas": 0, "expulsiones": 0, "gana_local": 0, "empates": 0, "gana_visitante": 0}
    partidos = []
    for j in juegos:
        res = j.get("resultado") or {}
        arbitros = res.get("arbitros") or {}
        rol = next(r for r, _ in ROLES if arbitros.get(r) == nombre)
        por_rol[rol] += 1
        faltas, tarjetas, expulsiones = _contar_faltas_tarjetas(res.get("eventos") or [])
        if rol == "central":
            central["partidos"] += 1
            central["faltas"] += faltas
            central["tarjetas"] += tarjetas
            central["expulsiones"] += expulsiones
            central[{"L": "gana_local", "V": "gana_visitante"}.get(res.get("ganador_lado"), "empates")] += 1
        local, visitante = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
        partidos.append({
            "id": str(j["_id"]), "fecha": j.get("fecha"), "fase": nombres_fase.get(j.get("fase_id"), ""),
            "rol": dict(ROLES)[rol], "es_central": rol == "central",
            "local": {"nombre": local.get("nombre"), "bandera": local.get("bandera") or "", "goles": res.get("goles_local", 0)},
            "visitante": {"nombre": visitante.get("nombre"), "bandera": visitante.get("bandera") or "", "goles": res.get("goles_visitante", 0)},
            "faltas": faltas, "tarjetas": tarjetas,
        })
    n = central["partidos"]
    return {
        "nombre": nombre, "pais": info.get("pais", ""), "puesto": info.get("puesto", ""),
        "total_partidos": len(juegos), "por_rol": [{"rol": etiqueta, "partidos": por_rol[r]} for r, etiqueta in ROLES],
        "central": {**central,
                    "faltas_prom": round(central["faltas"] / n, 1) if n else 0,
                    "tarjetas_prom": round(central["tarjetas"] / n, 1) if n else 0,
                    "pct_gana_local": round(100 * central["gana_local"] / n) if n else 0,
                    "pct_empate": round(100 * central["empates"] / n) if n else 0,
                    "pct_gana_visitante": round(100 * central["gana_visitante"] / n) if n else 0},
        "partidos": partidos,
    }
