"""
Renombra los estadios con nombres GENÉRICOS (los «comodín» que se repetían en decenas de países: «Estadio del
Progreso», «Campo del Futuro», «Estadio del Descanso», «Estadio Municipal»…) por nombres con gancho de marketing que
llevan la ciudad: «La Caldera de Sliema», «El Coloso de Kandahar», «Arena Tadjoura»… Sin repetir el estilo más de dos
veces dentro de un país. Determinístico (semilla = id de la ciudad): volver a correrlo da lo mismo.

Además del nombre en 'ciudades.estadio' actualiza la copia que guardan los partidos ('juegos.ubicacion.estadio') y
deja en null la crónica de los partidos jugados ahí (se reescribe sola con el nombre nuevo al abrir el partido, ver
cronica_service.asegurar_cronica). Respaldo en respaldos/estadios_nombres_<fecha>.json.

    python renombrar_estadios.py --muestra            # cuántos y ejemplos, sin escribir
    python renombrar_estadios.py --aplicar            # escribe (con respaldo)
    python renombrar_estadios.py --revertir ARCHIVO   # vuelve a los nombres del respaldo
"""
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime

# Nombres que se consideran genéricos: los «comodín» repetidos y los que no dicen nada
GENERICOS = {
    "Estadio del Progreso", "Estadio de la Victoria", "Estadio de la Tradición", "Arena de la Gloria", "Arena de la Costa",
    "Campo del Futuro", "Estadio del Legado", "Estadio de la Unidad", "Campo de la Historia", "Campo de la Libertad",
    "Estadio del Paraíso", "Arena del Desafío", "Campo de la Serenidad", "Arena de la Aventura", "Estadio del Refugio",
    "Campo de la Armonía", "Estadio de la Exploración", "Campo de la Esperanza", "Estadio del Descanso",
    "Estadio Municipal", "Estadio Central", "Estadio Městský stadion", "Estadio de los Héroes", "Estadio de la Esperanza",
    "Arena Nacional", "Campo de la Paz",
}
REPETIDO_DESDE = 9   # además: cualquier nombre usado en 9 o más ciudades es comodín

# Estilos (con la ciudad): apodos de cancha que suenan a tribuna llena
ESTILOS = [
    "El Coloso de {c}", "La Caldera de {c}", "El Volcán de {c}", "La Fortaleza de {c}", "El Templo de {c}",
    "La Ciudadela de {c}", "El Nido de {c}", "Coliseo {c}", "Arena {c}", "Estadio Monumental de {c}",
    "El Fortín de {c}", "La Catedral de {c}", "El Gigante de {c}", "La Olla de {c}", "El Bastión de {c}",
    "Estadio Corona de {c}", "El Faro de {c}", "El Hervidero de {c}", "{c} Arena", "Estadio Rugido de {c}",
    "El Trueno de {c}", "La Colmena de {c}", "Estadio Luz de {c}", "El Diamante de {c}",
]
POR_PAIS = 2   # cada estilo como mucho dos veces dentro de un país


def _datos():
    from services.imagenes_pais_service import db
    ciudades = list(db["ciudades"].find({}, {"_id": 0, "id": 1, "nombre": 1, "pais_id": 1, "pais": 1, "estadio": 1}))
    return db, ciudades


def plan(ciudades):
    """[(ciudad, nombre_viejo, nombre_nuevo)] de las ciudades con estadio genérico."""
    usos = Counter(c.get("estadio") for c in ciudades)
    genericos = {n for n, k in usos.items() if n and (n in GENERICOS or k >= REPETIDO_DESDE)}
    por_pais = defaultdict(list)
    for c in ciudades:
        por_pais[c["pais_id"]].append(c)
    cambios = []
    for pais_id, lista in por_pais.items():
        ocupados = {c.get("estadio") for c in lista if c.get("estadio") not in genericos}
        usados = Counter()
        vistos = set()
        ciudad_repetida = {n for n, k in Counter(c["nombre"] for c in lista).items() if k > 1}
        for c in sorted(lista, key=lambda x: x["id"]):
            if c["nombre"] in ciudad_repetida:   # ciudad cargada dos veces (Yibuti): se resuelve aparte, no se renombra
                continue
            # el mismo estadio en dos ciudades del país: la primera conserva su nombre real, la otra se renombra
            repetido = c.get("estadio") in vistos
            vistos.add(c.get("estadio"))
            if c.get("estadio") not in genericos and not repetido:
                continue
            r = random.Random(c["id"] * 104729 + 7)
            opciones = [e for e in ESTILOS if usados[e] < POR_PAIS]
            r.shuffle(opciones)
            for estilo in opciones:
                nuevo = estilo.format(c=c["nombre"])
                if nuevo not in ocupados:
                    break
            usados[estilo] += 1
            ocupados.add(nuevo)
            cambios.append((c, c.get("estadio"), nuevo))
    return cambios


def muestra():
    _, ciudades = _datos()
    cambios = plan(ciudades)
    print(f"{len(cambios)} estadios genéricos de {len(ciudades)} se renombrarían")
    print("por estilo:", Counter(n.replace(c["nombre"], "{c}") for c, _, n in cambios).most_common())
    r = random.Random(3)
    for c, viejo, nuevo in r.sample(cambios, min(30, len(cambios))):
        print(f"  {c['pais']:<22} {c['nombre']:<22} {viejo:<28} → {nuevo}")


def aplicar():
    from pymongo import UpdateMany, UpdateOne
    db, ciudades = _datos()
    cambios = plan(ciudades)
    os.makedirs("respaldos", exist_ok=True)
    archivo = f"respaldos/estadios_nombres_{datetime.now():%Y%m%d_%H%M%S}.json"
    with open(archivo, "w") as f:
        json.dump([{"id": c["id"], "estadio": viejo} for c, viejo, _ in cambios], f, ensure_ascii=False)
    db["ciudades"].bulk_write([UpdateOne({"id": c["id"]}, {"$set": {"estadio": nuevo}}) for c, _, nuevo in cambios], ordered=False)
    r = db["juegos"].bulk_write([UpdateMany({"ubicacion.id": c["id"]}, {"$set": {"ubicacion.estadio": nuevo}}) for c, _, nuevo in cambios], ordered=False)
    # la crónica de los partidos ya jugados se reescribe sola con el nombre nuevo (no durante una transmisión)
    ids = [c["id"] for c, _, _ in cambios]
    cr = db["juegos"].update_many({"ubicacion.id": {"$in": ids}, "estado": "finalizado", "resultado.cronica": {"$ne": None},
                                   "transmision.estado": {"$ne": "in_progress"}}, {"$set": {"resultado.cronica": None}})
    print(f"{len(cambios)} estadios renombrados · {r.modified_count} partidos con el nombre nuevo · {cr.modified_count} crónicas a reescribir")
    print(f"respaldo: {archivo}")


def revertir(archivo):
    from pymongo import UpdateMany, UpdateOne
    db, _ = _datos()
    datos = json.load(open(archivo))
    db["ciudades"].bulk_write([UpdateOne({"id": d["id"]}, {"$set": {"estadio": d["estadio"]}}) for d in datos], ordered=False)
    db["juegos"].bulk_write([UpdateMany({"ubicacion.id": d["id"]}, {"$set": {"ubicacion.estadio": d["estadio"]}}) for d in datos], ordered=False)
    print(f"{len(datos)} estadios vueltos a su nombre anterior")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo == "--muestra":
        muestra()
    elif modo == "--aplicar":
        aplicar()
    elif modo == "--revertir" and len(sys.argv) > 2:
        revertir(sys.argv[2])
    else:
        print(__doc__)
