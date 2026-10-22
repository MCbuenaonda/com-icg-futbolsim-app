"""
Fotos de equipo para el álbum: 3 por selección (titulares 1-11, suplentes 12-22, leyendas 23-33), estilo "foto
oficial antes del partido": 6 de pie atrás y 5 agachados adelante, cuerpo completo con el uniforme de su selección
(colores del jersey del bucket, como los avatares), dorsal en el pecho y el arquero con otro color y guantes.
La cara de cada jugador es la de su avatar (mismo motor y semilla que generar_avatares.py). Fondo TRANSPARENTE: en
la estampa la bandera va de fondo y el escudo en una esquina (ver templates/partials/estampas.html::equipo).

    python generar_fotos_equipo.py --muestra [carpeta] [--paises A,B]   # unas selecciones, para revisar
    python generar_fotos_equipo.py --generar [carpeta]                   # las 633 en <carpeta>/fotos_equipo/
    python generar_fotos_equipo.py --subir [carpeta]                     # sube a gs://com-icg-mundial/fotos_equipo/
    python generar_fotos_equipo.py --asignar                             # crea/actualiza la colección 'fotos_equipo'

Archivo: fotos_equipo/<pais_id>-<grupo>.svg (grupo 1 titulares, 2 suplentes, 3 leyendas). Requiere Pillow (colores
del jersey). Id de la estampa = pais_id * 10 + grupo (único y estable).
"""
import os
import random
import re
import sys

import generar_avatares as GA

ANCHO, ALTO = 1600, 910
ESCALA_CABEZA = 0.52
GRUPOS = {1: ("Titulares", range(1, 12)), 2: ("Suplentes", range(12, 23)), 3: ("Leyendas", range(23, 34))}
# Orden en la foto por posicion_id: atrás (izq→der, el arquero en la punta como en las fotos oficiales) y adelante
FILA_ATRAS = [4, 2, 3, 5, 7, 1]       # LI, DFI, DFD, LD, MC, POR
FILA_ADELANTE = [6, 9, 10, 11, 8]     # MI, EI, DC, ED, MD
COLORES_ARQUERO = ["#2b8a3e", "#f59f00", "#212529", "#7048e8", "#e8590c", "#0c8599"]
COLORES_BOTIN = ["#1c7ed6", "#212529", "#f8f9fa", "#e03131", "#f59f00", "#37b24d"]
C = GA.CONTORNO
T = 4  # trazo


def _claro(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b > 150


def _luz(hex_color):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _distancia(a, b):
    return sum(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) for i in (1, 3, 5))


def _cabeza(av: "GA.Avatar", sufijo: str) -> str:
    """Solo la cabeza del avatar (sin la camiseta del retrato), con ids únicos para poder repetirla en un SVG."""
    partes = (av._pelo_detras() + av._cuello() + av._orejas() + av._cara() + av._barba() + av._ojos() + av._cejas()
              + av._nariz() + av._boca() + av._pelo())
    return re.sub(r'(id="|url\(#)([\w-]+)', lambda m: f"{m.group(1)}{m.group(2)}_{sufijo}", partes)


def _uniforme(principal, secundario, rnd):
    short = secundario if _distancia(secundario, principal) > 120 else ("#f8f9fa" if not _claro(principal) else "#212529")
    return {"camiseta": principal, "sombra": GA._oscurecer(principal, 0.8), "detalle": secundario, "short": short,
            "medias": principal, "botin": rnd.choice(COLORES_BOTIN)}


def _camiseta(u, piel, arquero, retro, numero):
    """Torso con mangas (cortas; largas el arquero), cuello y dorsal. Origen: base del cuello."""
    cam = u["camiseta"]
    partes = []
    if arquero:   # mangas largas hasta las muñecas + guantes
        partes.append(f'<path d="M-72 6L-104 60L-100 150L-82 152L-80 72L-64 44Z M72 6L104 60L100 150L82 152L80 72L64 44Z" fill="{cam}" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>')
    cuerpo = "M-40 -6L-72 4L-104 58L-80 72L-64 42L-62 156L62 156L64 42L80 72L104 58L72 4L40 -6C20 10 -20 10 -40 -6Z"
    partes.append(f'<path d="{cuerpo}" fill="{cam}" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>')
    partes.append(f'<path d="M30 0L72 4L104 58L80 72L64 42L62 156L20 156Z" fill="{u["sombra"]}" opacity=".55"/>')
    partes.append(f'<path d="M-104 58L-80 72M104 58L80 72" stroke="{u["detalle"]}" stroke-width="7"/>')
    if retro:     # cuello polo con cordón, como las camisetas de antes
        partes.append(f'<path d="M-40 -6L-14 22L0 8L14 22L40 -6" fill="{u["detalle"]}" stroke="{C}" stroke-width="3" stroke-linejoin="round"/>'
                      f'<path d="M-4 14L-4 40M4 14L4 40" stroke="{u["detalle"]}" stroke-width="3"/>')
    else:
        partes.append(f'<path d="M-40 -6C-20 12 20 12 40 -6" fill="none" stroke="{u["detalle"]}" stroke-width="8" stroke-linecap="round"/>')
    # dorsal legible: el color de detalle si contrasta en luminosidad con la camiseta; si no, blanco o casi negro
    if abs(_luz(u["detalle"]) - _luz(cam)) >= 90:
        color_num = u["detalle"]
    else:
        color_num = "#ffffff" if _luz(cam) < 140 else "#14213d"
    partes.append(f'<text x="0" y="122" text-anchor="middle" font-family="Arial Black, Arial, Helvetica, sans-serif" font-weight="900" '
                  f'font-size="74" fill="{color_num}" stroke="{C}" stroke-width="2" paint-order="stroke">{numero}</text>')
    return "".join(partes)


def _jugador_de_pie(u, piel, arquero, retro, numero):
    """Jugador parado (fila de atrás): brazos a los costados."""
    guante = "#f1f3f5"
    p = []
    # piernas, medias y botines (la fila de adelante tapa buena parte)
    for s in (-1, 1):
        p.append(f'<path d="M{s * 12} 214L{s * 44} 214L{s * 42} 330L{s * 16} 330Z" fill="{piel}" stroke="{C}" stroke-width="{T}"/>')
        p.append(f'<path d="M{s * 15} 272L{s * 43} 272L{s * 42} 334L{s * 16} 334Z" fill="{u["medias"]}" stroke="{C}" stroke-width="{T}"/>')
        p.append(f'<path d="M{s * 12} 332L{s * 46} 332C{s * 58} 336 {s * 62} 350 {s * 54} 354L{s * 10} 354Z" fill="{u["botin"]}" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>')
    p.append(f'<path d="M-64 150L64 150L66 216L4 216L0 196L-4 216L-66 216Z" fill="{u["short"]}" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>')
    # brazos (debajo de las mangas)
    for s in (-1, 1):
        if not arquero:
            p.append(f'<path d="M{s * 78} 62L{s * 106} 56L{s * 106} 150L{s * 80} 150Z" fill="{piel}" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>')
        p.append(f'<circle cx="{s * 93}" cy="{160}" r="17" fill="{guante if arquero else piel}" stroke="{C}" stroke-width="{T}"/>')
    p.append(_camiseta(u, piel, arquero, retro, numero))
    return "".join(p)


def _jugador_agachado(u, piel, arquero, retro, numero):
    """Jugador agachado (fila de adelante): rodillas afuera y manos en las rodillas."""
    guante = "#f1f3f5"
    p = []
    for s in (-1, 1):
        # muslo (cadera -> rodilla) y pierna (rodilla -> pie)
        p.append(f'<path d="M{s * 14} 196L{s * 66} 186L{s * 126} 232L{s * 98} 268Z" fill="{piel}" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>')
        p.append(f'<path d="M{s * 94} 240L{s * 122} 240L{s * 118} 330L{s * 92} 330Z" fill="{piel}" stroke="{C}" stroke-width="{T}"/>')
        p.append(f'<path d="M{s * 94} 272L{s * 121} 272L{s * 119} 334L{s * 92} 334Z" fill="{u["medias"]}" stroke="{C}" stroke-width="{T}"/>')
        p.append(f'<path d="M{s * 86} 332L{s * 124} 332C{s * 138} 336 {s * 142} 350 {s * 132} 354L{s * 84} 354Z" fill="{u["botin"]}" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>')
    p.append(f'<path d="M-64 150L64 150L84 214L20 222L0 200L-20 222L-84 214Z" fill="{u["short"]}" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>')
    for s in (-1, 1):
        # brazo hacia la rodilla
        color = u["camiseta"] if arquero else piel
        p.append(f'<path d="M{s * 80} 64L{s * 106} 56L{s * 130} 224L{s * 104} 234Z" fill="{color}" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>')
        p.append(f'<circle cx="{s * 116}" cy="{236}" r="18" fill="{guante if arquero else piel}" stroke="{C}" stroke-width="{T}"/>')
    p.append(_camiseta(u, piel, arquero, retro, numero).replace("M-72 6L-104 60L-100 150L-82 152L-80 72L-64 44Z M72 6L104 60L100 150L82 152L80 72L64 44Z", "M0 0Z"))
    return "".join(p)


def _figura(j, x, y_cuello, agachado, u_campo, u_arquero, region, retro):
    arquero = j.get("posicion_id") == 1
    edad = j.get("edad") or 25
    u = u_arquero if arquero else u_campo
    av = GA.Avatar(j["id"], edad, region, (u["camiseta"], u["detalle"]))   # misma semilla que su avatar = misma cara
    cuerpo = (_jugador_agachado if agachado else _jugador_de_pie)(u, av.piel, arquero, retro, j.get("numero") or "")
    s = ESCALA_CABEZA
    # en el avatar (512) la base del cuello queda en y≈408 y el centro en x=256
    cabeza = f'<g transform="translate({-256 * s:.1f} {-408 * s:.1f}) scale({s})">{_cabeza(av, str(j["id"]))}</g>'
    return f'<g transform="translate({x} {y_cuello})">{cuerpo}{cabeza}</g>'


def foto(jugadores: list, region: str, jersey: tuple, grupo: int, semilla: int) -> str:
    rnd = random.Random(semilla)
    principal, secundario = jersey
    u_campo = _uniforme(principal, secundario, rnd)
    arq = next(c for c in COLORES_ARQUERO if _distancia(c, principal) > 160)
    u_arquero = {**u_campo, "camiseta": arq, "sombra": GA._oscurecer(arq, 0.8), "detalle": "#f8f9fa" if not _claro(arq) else "#212529",
                 "medias": arq}
    retro = grupo == 3
    por_pos = {}
    for j in jugadores:
        por_pos.setdefault(j.get("posicion_id"), j)
    atras = [por_pos[p] for p in FILA_ATRAS if p in por_pos]
    adelante = [por_pos[p] for p in FILA_ADELANTE if p in por_pos]
    usados = {id(j) for j in atras + adelante}
    adelante += [j for j in jugadores if id(j) not in usados][: max(0, 5 - len(adelante))]
    figuras = []
    paso = 240
    x0 = ANCHO / 2 - paso * (len(atras) - 1) / 2
    for i, j in enumerate(atras):
        figuras.append(_figura(j, x0 + i * paso, 240, False, u_campo, u_arquero, region, retro))
    x0 = ANCHO / 2 - paso * (len(adelante) - 1) / 2   # entre los de atrás, como en las fotos oficiales
    for i, j in enumerate(adelante):
        figuras.append(_figura(j, x0 + i * paso, 548, True, u_campo, u_arquero, region, retro))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ANCHO} {ALTO}" width="{ANCHO}" height="{ALTO}" '
            f'stroke-linecap="round">{"".join(figuras)}</svg>')


# --- Datos ---------------------------------------------------------------------------------------------
def _datos(solo=None):
    from urllib.parse import quote
    from config.settings import IMAGENES_PAISES_URL
    from services.imagenes_pais_service import db
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "confederacion_id": 1})}
    if solo:
        paises = {i: p for i, p in paises.items() if p["nombre"] in solo}
    jerseys = {}
    for pid, p in paises.items():
        try:
            jerseys[pid] = GA._colores_jersey(f"{IMAGENES_PAISES_URL}/jersey/{quote(p['nombre'])}.png")
        except Exception as e:
            print(f"  ⚠️ jersey de {p['nombre']}: {e}")
            jerseys[pid] = ("#3b5bdb", "#ffffff")
    por_pais = {}
    for j in db["jugadores"].find({"pais_id": {"$in": list(paises)}}, {"id": 1, "edad": 1, "pais_id": 1, "posicion_id": 1, "numero": 1}):
        por_pais.setdefault(j["pais_id"], []).append(j)
    return paises, jerseys, por_pais


def _fotos_de(pid, paises, jerseys, por_pais):
    region = GA._region(paises[pid])
    for grupo, (_, dorsales) in GRUPOS.items():
        js = sorted([j for j in por_pais.get(pid, []) if j.get("numero") in dorsales], key=lambda j: j["numero"])
        if js:
            yield grupo, foto(js, region, jerseys[pid], grupo, pid * 10 + grupo)


def generar(carpeta, solo=None):
    destino = os.path.join(carpeta, "fotos_equipo")
    os.makedirs(destino, exist_ok=True)
    paises, jerseys, por_pais = _datos(solo)
    n = 0
    for pid in paises:
        for grupo, svg in _fotos_de(pid, paises, jerseys, por_pais):
            with open(os.path.join(destino, f"{pid}-{grupo}.svg"), "w") as f:
                f.write(svg)
            n += 1
    print(f"{n} fotos en {destino}")


def subir(carpeta):
    import subprocess
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "fotos_equipo", "*.svg"), "gs://com-icg-mundial/fotos_equipo/",
                    "--gzip-local-all", "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def asignar():
    """Colección 'fotos_equipo' (catálogo de estampas): {id = pais_id*10+grupo, pais_id, grupo, nombre, imagen}."""
    from pymongo import UpdateOne
    from services.imagenes_pais_service import db
    ops = []
    for p in db["paises"].find({}, {"id": 1, "nombre": 1}):
        for grupo, (titulo, _) in GRUPOS.items():
            doc = {"id": p["id"] * 10 + grupo, "pais_id": p["id"], "grupo": grupo, "nombre": f"{titulo} de {p['nombre']}",
                   "imagen": f"fotos_equipo/{p['id']}-{grupo}.svg"}
            ops.append(UpdateOne({"id": doc["id"]}, {"$set": doc}, upsert=True))
    r = db["fotos_equipo"].bulk_write(ops, ordered=False)
    print(f"fotos_equipo: {r.upserted_count} nuevas, {r.modified_count} actualizadas ({len(ops)} en total)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--paises")]
    solo = None
    for a in sys.argv[1:]:
        if a.startswith("--paises="):
            solo = [x.strip() for x in a.split("=", 1)[1].split(",")]
    modo = args[0] if args else ""
    carpeta = args[1] if len(args) > 1 else "fotos_generadas"
    {"--muestra": lambda: generar(carpeta, solo or ["Argentina", "México", "Brasil", "Japón"]),
     "--generar": lambda: generar(carpeta), "--subir": lambda: subir(carpeta), "--asignar": asignar}.get(modo, lambda: print(__doc__))()
