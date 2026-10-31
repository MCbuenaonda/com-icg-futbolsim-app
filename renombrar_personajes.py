"""
Les pone nombres VEROSÍMILES (config/nombres_reales.py: nombres y apellidos comunes de cada país, no de personas conocidas) a los
personajes ficticios, que antes salían de mezclar nombres de jugadores del sistema y se veían repetidos:
  - televisoras.equipo: dueño y comentaristas (algunos comentaristas con apodo),
  - marcas.dueno,
  - medios.equipo: director y periodistas (algunos periodistas con apodo).
Cada nombre sigue al país de la persona (el mismo que usan sus avatares, así cara y nombre combinan). Solo cambia el NOMBRE: rasgos,
edades y avatares quedan igual. También actualiza las copias del nombre en prensa, prensa_pronosticos y corp_entrevistas, y después
hay que volver a correr agregar_estampas_medios.py --aplicar (el álbum guarda el nombre). Determinístico (semilla = persona).
Si se vuelven a correr generar_equipo_tv.py / generar_dueno_marcas.py / generar_medios.py, correr esto otra vez después.

    python renombrar_personajes.py --muestra [N]        # ejemplos, no escribe
    python renombrar_personajes.py --aplicar            # escribe (respaldo en respaldos/personajes_nombres_<fecha>.json)
    python renombrar_personajes.py --revertir ARCHIVO   # vuelve a los nombres del respaldo
"""
import json
import os
import random
import sys
import zlib
from datetime import datetime

from config import nombres_reales as NR
from generar_equipo_tv import _db, _norm, _prohibidos


def _iso_paises(db):
    return {p["id"]: (p.get("iso") or "").upper() for p in db["paises"].find({}, {"id": 1, "iso": 1})}


class Nombrador:
    def __init__(self, db):
        self.usados = _prohibidos(db)   # nadie se llama igual que un jugador, árbitro o técnico del sistema
        self.listas = {c: (n.split(), NR.lista(a)) for c, (n, a) in NR.CULTURAS.items()}   # los prefijos solo se unen en apellidos

    def nombre(self, clave: str, iso: str, apellidos_entidad: set, rol: str = None) -> str:
        cultura = NR.CULTURA_POR_ISO.get(iso, "en")
        nombres, apellidos = self.listas[cultura]
        rng = random.Random(zlib.crc32(clave.encode()))
        for _ in range(500):
            n, a = rng.choice(nombres), rng.choice(apellidos)
            completo = f"{a} {n}" if cultura in NR.APELLIDO_PRIMERO else f"{n} {a}"
            if _norm(completo) in self.usados or a in apellidos_entidad:
                continue
            self.usados.add(_norm(completo))
            apellidos_entidad.add(a)
            if rol in NR.PROB_APODO and cultura in NR.APODOS and rng.random() < NR.PROB_APODO[rol]:
                return f'{n} "{rng.choice(NR.APODOS[cultura])}" {a}'
            return completo
        raise RuntimeError(f"sin nombres libres para {clave} ({cultura})")


def plan(db):
    """[(coleccion, filtro, campo, viejo, nuevo, medio_id|None)] de todos los personajes."""
    iso = _iso_paises(db)
    N = Nombrador(db)
    cambios = []
    for t in db["televisoras"].find({"equipo": {"$exists": True}}, {"id": 1, "pais_id": 1, "equipo": 1}).sort("id", 1):
        ap = set()
        eq = t["equipo"]
        cambios.append(("televisoras", {"id": t["id"]}, "equipo.dueno.nombre", eq["dueno"]["nombre"], N.nombre(f"tv:{t['id']}:d", iso.get(t["pais_id"], ""), ap), None))
        for i, c in enumerate(eq["comentaristas"]):
            cambios.append(("televisoras", {"id": t["id"]}, f"equipo.comentaristas.{i}.nombre", c["nombre"],
                            N.nombre(f"tv:{t['id']}:c{i}", iso.get(t["pais_id"], ""), ap, "comentarista"), None))
    from generar_dueno_marcas import armar as armar_marcas   # el país del dueño (el mismo de su avatar)
    actuales = {m["id"]: m["dueno"]["nombre"] for m in db["marcas"].find({"dueno": {"$exists": True}}, {"id": 1, "dueno.nombre": 1})}
    for m, pais, _ in armar_marcas(db):
        if m["id"] in actuales:
            cambios.append(("marcas", {"id": m["id"]}, "dueno.nombre", actuales[m["id"]], N.nombre(f"marca:{m['id']}", iso.get(pais, ""), set()), None))
    todos = sorted(iso)
    for m in db["medios"].find({"equipo": {"$exists": True}}, {"id": 1, "pais_id": 1, "equipo": 1}).sort("id", 1):
        pais = m.get("pais_id") or todos[m["id"] % len(todos)]   # los internacionales: el país que usa su avatar
        ap = set()
        cambios.append(("medios", {"id": m["id"]}, "equipo.director.nombre", m["equipo"]["director"]["nombre"],
                        N.nombre(f"medio:{m['id']}:d", iso.get(pais, ""), ap), m["id"]))
        for i, p in enumerate(m["equipo"]["periodistas"]):
            cambios.append(("medios", {"id": m["id"]}, f"equipo.periodistas.{i}.nombre", p["nombre"],
                            N.nombre(f"medio:{m['id']}:p{i}", iso.get(pais, ""), ap, "periodista"), m["id"]))
    return cambios


def _escribir(db, cambios, al_reves=False):
    from pymongo import UpdateMany, UpdateOne
    por_col = {}
    for col, filtro, campo, viejo, nuevo, medio_id in cambios:
        de, a = (nuevo, viejo) if al_reves else (viejo, nuevo)
        por_col.setdefault(col, []).append(UpdateOne(filtro, {"$set": {campo: a}}))
        if medio_id is not None and ".periodistas." in campo or (medio_id is not None and campo.endswith("director.nombre")):
            for c in ("prensa", "prensa_pronosticos", "corp_entrevistas"):
                por_col.setdefault(c, []).append(UpdateMany({"medio_id": medio_id, "periodista.nombre": de}, {"$set": {"periodista.nombre": a}}))
    for col, ops in por_col.items():
        r = db[col].bulk_write(ops, ordered=False)
        print(f"  {col}: {r.modified_count} documentos")


def muestra(n):
    db = _db()
    cambios = plan(db)
    paso = max(1, len(cambios) // n)
    for col, filtro, campo, viejo, nuevo, _ in cambios[::paso][:n]:
        print(f"{col:<12} {campo:<32} {viejo:<30} → {nuevo}")
    print(f"\n{len(cambios)} personajes; {sum(1 for c in cambios if '\"' in c[4])} con apodo; {len({c[4] for c in cambios})} nombres distintos")


def aplicar():
    db = _db()
    cambios = plan(db)
    os.makedirs("respaldos", exist_ok=True)
    archivo = f"respaldos/personajes_nombres_{datetime.now():%Y%m%d_%H%M%S}.json"
    json.dump(cambios, open(archivo, "w"), ensure_ascii=False)
    _escribir(db, cambios)
    print(f"{len(cambios)} nombres cambiados; respaldo: {archivo}")
    print("Falta: python agregar_estampas_medios.py --aplicar (el álbum guarda los nombres)")


def revertir(archivo):
    db = _db()
    _escribir(db, json.load(open(archivo)), al_reves=True)
    print("nombres restaurados; correr agregar_estampas_medios.py --aplicar")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo == "--muestra":
        muestra(int(sys.argv[2]) if len(sys.argv) > 2 else 30)
    elif modo == "--aplicar":
        aplicar()
    elif modo == "--revertir" and len(sys.argv) > 2:
        revertir(sys.argv[2])
    else:
        print(__doc__)
