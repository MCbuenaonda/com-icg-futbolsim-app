"""
Ajuste retroactivo del cuerpo arbitral en los partidos YA JUGADOS (los simulados antes de services/arbitraje.py):

- resultado.arbitros.var: un árbitro VAR (5to) por partido, sorteado con semilla = id del partido (determinístico) y de
  un país distinto a los dos equipos.
- En cada evento arbitral, 'arbitro' y 'arbitro_rol' (lo que necesitan las estadísticas por puesto de /arbitros):
    · fuera de lugar: el juez de línea que nombra el texto ("El juez de línea (X)...");
    · desvío a córner: el juez de línea del lado donde atacaba el equipo que ganó el córner;
    · faltas, tarjetas y silbatos: el central; cambios: el 4to (services/arbitraje.asignar_arbitros);
    · decisiones del VAR (todas fueron anulaciones): el VAR, con var_decision "revierte" y 'var_pedido_por' = el 4to
      (el que pidió la revisión), y el texto pasa al formato nuevo ("{VAR} da por mala la jugada...").
- No se agregan ni quitan eventos (los índices los usa el Juego en Vivo), no se toca el marcador, los minutos ni nada
  que mueva estadísticas de jugadores o selecciones, y no se inventa tiempo añadido.
- resultado.cronica = None: la crónica se reescribe sola con el VAR (o con generar_cronicas.py --forzar).

    python asignar_arbitros_partidos.py --muestra     # qué cambiaría en 3 partidos, sin escribir
    python asignar_arbitros_partidos.py --aplicar     # aplica (respaldo en respaldos/)
    python asignar_arbitros_partidos.py --revertir    # restaura el último respaldo
"""
import glob
import gzip
import json
import os
import random
import re
import sys
from datetime import datetime

from bson import ObjectId
from pymongo import UpdateOne

from services import arbitraje
from services.imagenes_pais_service import db

RAIZ = os.path.dirname(os.path.abspath(__file__))
FILTRO = {"estado": "finalizado", "resultado.arbitros": {"$type": "object"}, "resultado.arbitros.var": {"$exists": False},
          "transmision.estado": {"$ne": "in_progress"}}
RE_JUEZ = re.compile(r"juez de línea \(([^)]+)\)")


def _periodo(seg: float) -> int:
    return 1 if seg < 2700 else (2 if seg < 5400 else (3 if seg < 6300 else 4))


def _vars():
    return list(db["arbitros"].find({"puesto": arbitraje.PUESTOS["var"]}, {"nombre": 1, "pais_id": 1}))


def ajustar(juego: dict, vars_disponibles: list) -> dict:
    """Devuelve {arbitros, eventos} ajustados (no escribe)."""
    res = juego["resultado"]
    arbitros = dict(res["arbitros"])
    excluir = {(juego.get("equipo_local") or {}).get("id"), (juego.get("equipo_visitante") or {}).get("id")}
    neutrales = [a for a in vars_disponibles if a.get("pais_id") not in excluir] or vars_disponibles
    arbitros["var"] = random.Random(str(juego["_id"])).choice(neutrales)["nombre"]
    local = res.get("local") or (juego.get("equipo_local") or {}).get("nombre")
    central, var, cuarto = arbitros.get("central") or "el árbitro", arbitros["var"], arbitros.get("cuarto")
    eventos = [dict(e) for e in res.get("eventos") or []]
    en_tanda = False
    for e in eventos:
        tipo, seg = e.get("tipo"), float(e.get("segundos_acumulados") or (e.get("minuto") or 0) * 60)
        js = e.get("jugadores") or []
        if tipo == "🥅 TANDA DE PENALTIS":
            en_tanda = True
        if tipo == "🚩 FUERA DE LUGAR":
            nombre = (RE_JUEZ.search(e.get("descripcion") or "") or [None, None])[1]
            rol = next((r for r in ("linea1", "linea2") if arbitros.get(r) == nombre), None)
            rol = rol or arbitraje.rol_juez_de_linea(e.get("equipo") == local, _periodo(seg))
            e["arbitro_rol"], e["arbitro"] = rol, arbitros.get(rol)
        elif tipo == "🖐️ DESVÍO A CÓRNER":
            # el evento lo firma el arquero (equipo que defiende): el córner es del otro
            rol = arbitraje.rol_juez_de_linea(e.get("equipo") != local, _periodo(seg))
            e["arbitro_rol"], e["arbitro"] = rol, arbitros.get(rol)
        elif tipo in ("🖥️ VAR - GOL ANULADO", "🖥️ VAR - TARJETA REVISADA", "🖥️ VAR - PENAL ANULADO"):
            jug = js[0] if js else "el jugador"
            if tipo == "🖥️ VAR - GOL ANULADO":
                motivo = re.search(r"anula el gol de .+? ((?:por|porque) [^.]+)\.", e.get("descripcion") or "")
                e["descripcion"] = f"{var} da por mala la jugada y {central} anula el gol de {jug} {motivo.group(1) if motivo else 'por mano previa'}."
            elif tipo == "🖥️ VAR - TARJETA REVISADA":
                e["descripcion"] = f"{var} da por mala la roja: {central} revisa en el monitor y la baja a amarilla para {jug}."
            else:
                motivo = "el cobrador se detuvo de forma antirreglamentaria" if en_tanda else "la falta había sido fuera del área"
                e["descripcion"] = f"{var} da por mala la jugada: {motivo}. {central} anula el penal de {jug}."
            e["arbitro_rol"], e["arbitro"], e["var_decision"] = "var", var, "revierte"
            if cuarto:
                e["var_pedido_por"] = cuarto
    arbitraje.asignar_arbitros(eventos, arbitros)
    return {"arbitros": arbitros, "eventos": eventos}


def _juegos():
    return list(db["juegos"].find(FILTRO, {"resultado.arbitros": 1, "resultado.eventos": 1, "resultado.local": 1,
                                           "equipo_local": 1, "equipo_visitante": 1}))


def muestra():
    juegos, vars_disp = _juegos(), _vars()
    print(f"Partidos a ajustar: {len(juegos)} · árbitros VAR disponibles: {len(vars_disp)}")
    conteo = {}
    for j in juegos:
        nuevo = ajustar(j, vars_disp)
        for e in nuevo["eventos"]:
            if e.get("arbitro_rol"):
                conteo[e["arbitro_rol"]] = conteo.get(e["arbitro_rol"], 0) + 1
    print("Eventos con árbitro por rol:", conteo)
    for j in juegos[:3]:
        nuevo = ajustar(j, vars_disp)
        print(f"\n{j['_id']} · VAR: {nuevo['arbitros']['var']}")
        for e in nuevo["eventos"]:
            if e.get("arbitro_rol") in ("var", "linea1", "linea2") and (e.get("arbitro_rol") == "var" or e["tipo"] != "🚩 FUERA DE LUGAR"):
                print(f"   {e.get('minuto')}' {e['tipo']:<26} {e['arbitro_rol']}: {e['arbitro']} | {e['descripcion'][:90]}")


def aplicar():
    juegos, vars_disp = _juegos(), _vars()
    if not juegos:
        print("No hay partidos para ajustar.")
        return
    os.makedirs(os.path.join(RAIZ, "respaldos"), exist_ok=True)
    archivo = os.path.join(RAIZ, "respaldos", f"arbitros_partidos_{datetime.now():%Y%m%d_%H%M%S}.json.gz")
    with gzip.open(archivo, "wt", encoding="utf-8") as f:
        json.dump([{"_id": str(j["_id"]), "arbitros": j["resultado"]["arbitros"], "eventos": j["resultado"]["eventos"]} for j in juegos],
                  f, ensure_ascii=False, default=str)
    ops = []
    for j in juegos:
        nuevo = ajustar(j, vars_disp)
        ops.append(UpdateOne({"_id": j["_id"], "resultado.arbitros.var": {"$exists": False}},
                             {"$set": {"resultado.arbitros": nuevo["arbitros"], "resultado.eventos": nuevo["eventos"], "resultado.cronica": None}}))
    r = db["juegos"].bulk_write(ops)
    print(f"Partidos ajustados: {r.modified_count} de {len(ops)} · respaldo: {archivo}")


def revertir():
    archivos = sorted(glob.glob(os.path.join(RAIZ, "respaldos", "arbitros_partidos_*.json.gz")))
    if not archivos:
        print("No hay respaldo.")
        return
    with gzip.open(archivos[-1], "rt", encoding="utf-8") as f:
        datos = json.load(f)
    ops = [UpdateOne({"_id": ObjectId(d["_id"])}, {"$set": {"resultado.arbitros": d["arbitros"], "resultado.eventos": d["eventos"],
                                                             "resultado.cronica": None}}) for d in datos]
    r = db["juegos"].bulk_write(ops)
    print(f"Restaurados {r.modified_count} partidos desde {archivos[-1]}")


if __name__ == "__main__":
    {"--muestra": muestra, "--aplicar": aplicar, "--revertir": revertir}.get(
        sys.argv[1] if len(sys.argv) > 1 else "", lambda: print(__doc__))()
