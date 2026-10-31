"""
Corrige la colección 'ciudades' para que cada país tenga sus 20 ciudades (una sola corrida; respaldo en respaldos/):

  1. Yibuti tenía sus 20 ciudades cargadas TRES veces (ids 4167-4206 son copias de 4147-4166): los partidos y las
     estampas del álbum que apuntan a una copia pasan a la ciudad original (si el usuario ya tenía la original, la
     copia cuenta como repetida) y las copias se borran.
  2. Gambia, Pakistán, Tanzania y Surinam tenían una ciudad repetida dentro de sus 20: la segunda pasa a ser otra
     ciudad real del país (mismo id: lo que la referencie sigue funcionando).
  3. 15 países se cargaron con 19: se agrega una ciudad real a cada uno, con su estadio y su ilustración (el concepto
     que le toca según generar_estadios.asignacion, dibujado y subido al bucket estadios_v2/).
  Malta queda con 21 (su ciudad 21 ya alojó partidos).

    python corregir_ciudades.py --muestra    # qué haría, sin escribir
    python corregir_ciudades.py --aplicar    # escribe (respaldo en respaldos/ciudades_correccion_<fecha>.json)
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime

YIBUTI_ORIGINALES = range(4147, 4167)
YIBUTI_COPIAS = range(4167, 4207)

# ciudad repetida dentro del país -> otra ciudad real del país (id que se reutiliza: nombre, estadio)
RENOMBRAR = {
    1439: ("Kanifing", "El Coloso de Kanifing"),              # Gambia (Gunjur repetida)
    2972: ("Mardan", "El Gigante de Mardan"),                 # Pakistán (Islamabad repetida)
    3795: ("Mtwara", "Estadio Nangwanda Sijaona"),            # Tanzania (Dodoma repetida)
    3725: ("Zanderij", "Arena Zanderij"),                     # Surinam (Albina repetida)
}

# país con 19 -> ciudad real que falta (nombre, estadio)
NUEVAS = {
    "Palestina": ("Salfit", "Estadio Olivar de Salfit"),
    "Panamá": ("Las Tablas", "Estadio Carnaval de Las Tablas"),
    "Papúa Nueva Guinea": ("Alotau", "Arena Alotau"),
    "Perú": ("Tumbes", "Estadio Mariscal Cáceres"),
    "Polonia": ("Zabrze", "Estadio Ernest Pohl"),
    "Portugal": ("Faro", "Estadio Algarve"),
    "Catar": ("Lusail", "Estadio Lusail"),
    "RD del Congo": ("Matadi", "Estadio Puerto de Matadi"),
    "República Centroafricana": ("Birao", "El Fortín de Birao"),
    "República Dominicana": ("Samaná", "Estadio Bahía de Samaná"),
    "Ruanda": ("Ruhango", "El Nido de Ruhango"),
    "Rumanía": ("Suceava", "Estadio Areni"),
    "Samoa": ("Vailima", "Estadio Vailima"),
    "Samoa Americana": ("Ta'ū", "Arena Ta'ū"),
    "San Cristóbal y Nieves": ("Frigate Bay", "Arena Frigate Bay"),
}
CAMPOS_UBICACION = ("id", "nombre", "tipo", "estadio", "pais_id", "pais")


def _db():
    from services.imagenes_pais_service import db
    return db


def _plan(db):
    originales = {c["nombre"]: c for c in db["ciudades"].find({"id": {"$in": list(YIBUTI_ORIGINALES)}}, {"_id": 0})}
    copias = list(db["ciudades"].find({"id": {"$in": list(YIBUTI_COPIAS)}}, {"_id": 0}))
    a_original = {c["id"]: originales[c["nombre"]]["id"] for c in copias if c["nombre"] in originales}
    paises = {p["nombre"]: p["id"] for p in db["paises"].find({"nombre": {"$in": list(NUEVAS)}}, {"id": 1, "nombre": 1})}
    tope = db["ciudades"].find_one(sort=[("id", -1)])["id"]
    nuevas = []
    for i, (pais, (nombre, estadio)) in enumerate(sorted(NUEVAS.items())):
        nuevas.append({"id": tope + 1 + i, "nombre": nombre, "tipo": "Ciudad", "estadio": estadio, "pais_id": paises[pais], "pais": pais})
    return originales, copias, a_original, nuevas


def muestra():
    db = _db()
    originales, copias, a_original, nuevas = _plan(db)
    print(f"Yibuti: {len(originales)} originales, {len(copias)} copias a borrar ({len(a_original)} con su original)")
    print(f"  partidos en copias: {db['juegos'].count_documents({'ubicacion.id': {'$in': list(a_original)}})}"
          f" · álbumes con copias: {db['user_albums'].count_documents({'owned_ciudades': {'$in': list(a_original)}})}"
          f" · sedes compradas: {db['city_ownerships'].count_documents({'ciudad_id': {'$in': list(a_original)}})}")
    for cid, (nombre, estadio) in RENOMBRAR.items():
        c = db["ciudades"].find_one({"id": cid}, {"_id": 0, "nombre": 1, "pais": 1, "estadio": 1})
        print(f"  {c['pais']}: {c['nombre']} ({c['estadio']}) → {nombre} ({estadio})")
    for n in nuevas:
        print(f"  nueva {n['id']}: {n['pais']} · {n['nombre']} · {n['estadio']}")


def aplicar():
    from pymongo import UpdateOne
    import generar_estadios as GE
    db = _db()
    originales, copias, a_original, nuevas = _plan(db)
    copias_ids = list(a_original)
    renombrar_ids = list(RENOMBRAR)

    # --- respaldo de todo lo que se toca ---
    os.makedirs("respaldos", exist_ok=True)
    archivo = f"respaldos/ciudades_correccion_{datetime.now():%Y%m%d_%H%M%S}.json"
    juegos = list(db["juegos"].find({"ubicacion.id": {"$in": copias_ids}}, {"ubicacion": 1}))
    albumes = list(db["user_albums"].find({"owned_ciudades": {"$in": copias_ids}}, {"owned_ciudades": 1, "repetidas": 1}))
    respaldo = {"copias_borradas": copias,
                "renombradas": list(db["ciudades"].find({"id": {"$in": renombrar_ids}}, {"_id": 0})),
                "nuevas_ids": [n["id"] for n in nuevas],
                "juegos": [{"_id": str(j["_id"]), "ubicacion": j["ubicacion"]} for j in juegos],
                "albumes": [{"_id": str(a["_id"]), "owned_ciudades": a["owned_ciudades"], "repetidas": a.get("repetidas")} for a in albumes]}
    with open(archivo, "w") as f:
        json.dump(respaldo, f, ensure_ascii=False, default=str)

    # --- 1. Yibuti: partidos y estampas a la ciudad original, después se borran las copias ---
    por_id = {c["id"]: c for c in originales.values()}
    ops = []
    for j in juegos:
        orig = por_id[a_original[j["ubicacion"]["id"]]]
        ops.append(UpdateOne({"_id": j["_id"]}, {"$set": {"ubicacion": {k: orig.get(k) for k in CAMPOS_UBICACION}}}))
    if ops:
        db["juegos"].bulk_write(ops, ordered=False)
    for a in albumes:
        nuevas_ciudades, repetidas = [], 0
        for cid in a["owned_ciudades"]:
            cid = a_original.get(cid, cid)
            if cid in nuevas_ciudades:
                repetidas += 1      # ya tenía la original: la copia cuenta como repetida (se puede canjear o vender)
            else:
                nuevas_ciudades.append(cid)
        cambio = {"$set": {"owned_ciudades": nuevas_ciudades}}
        if repetidas:
            cambio["$inc"] = {"repetidas.CIUDAD": repetidas}
        db["user_albums"].update_one({"_id": a["_id"]}, cambio)
    borradas = db["ciudades"].delete_many({"id": {"$in": copias_ids}}).deleted_count

    # --- 2. ciudades repetidas dentro del país: pasan a ser otra ciudad real ---
    for cid, (nombre, estadio) in RENOMBRAR.items():
        db["ciudades"].update_one({"id": cid}, {"$set": {"nombre": nombre, "estadio": estadio}})
        db["juegos"].update_many({"ubicacion.id": cid}, {"$set": {"ubicacion.nombre": nombre, "ubicacion.estadio": estadio}})

    # --- 3. la ciudad que faltaba, con la ilustración de estadio que le toca ---
    db["ciudades"].insert_many([dict(n) for n in nuevas])
    asignacion = GE.asignacion()
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "colores": 1})}
    carpeta = tempfile.mkdtemp(prefix="estadios_nuevos_")
    os.makedirs(os.path.join(carpeta, "estadios_v2"), exist_ok=True)
    for n in nuevas:
        a = asignacion[n["id"]]
        with open(os.path.join(carpeta, a["imagen"]), "w") as f:
            f.write(GE.dibujar(paises[a["pais_id"]], a["codigo"], a["variante"]))
        db["ciudades"].update_one({"id": n["id"]}, {"$set": {"estadio_imagen": a["imagen"]}})
    GE.subir(carpeta)
    print(f"Yibuti: {borradas} copias borradas · {len(juegos)} partidos y {len(albumes)} álbumes pasados a la original")
    print(f"{len(RENOMBRAR)} ciudades repetidas convertidas en otra ciudad · {len(nuevas)} ciudades nuevas con estadio e ilustración")
    print(f"respaldo: {archivo}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    {"--muestra": muestra, "--aplicar": aplicar}.get(modo, lambda: print(__doc__))()
