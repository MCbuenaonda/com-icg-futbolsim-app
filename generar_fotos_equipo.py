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
from plantilla_foto import cuerpo as CU
from plantilla_foto import uniforme as UN

ANCHO, ALTO = 1600, 910
ESCALA_CABEZA = 0.52
SUELO_ATRAS = 612      # suela de la fila de atrás (la tapan en parte los de adelante)
SUELO_ADELANTE = 900   # suela de la fila de adelante
GRUPOS = {1: ("Titulares", range(1, 12)), 2: ("Suplentes", range(12, 23)), 3: ("Leyendas", range(23, 34))}
# Orden en la foto por posicion_id: atrás (izq→der, el arquero en la punta como en las fotos oficiales) y adelante
FILA_ATRAS = [4, 2, 3, 5, 7, 1]       # LI, DFI, DFD, LD, MC, POR
FILA_ADELANTE = [6, 9, 10, 11, 8]     # MI, EI, DC, ED, MD
COLORES_ARQUERO = ["#2b8a3e", "#f59f00", "#212529", "#7048e8", "#e8590c", "#0c8599"]
COLORES_BOTIN = ["#1c7ed6", "#212529", "#f8f9fa", "#e03131", "#f59f00", "#37b24d", "#7048e8"]
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


# --- Figuras (cuerpos en plantilla_foto/cuerpo.py, uniformes en plantilla_foto/uniforme.py) ---------------------
def _complexion(jugador_id: int, arquero: bool, agachado: bool):
    """Estatura y complexión de cada jugador, fijas (semilla = su id): no todos miden lo mismo, como en la vida real."""
    r = random.Random(jugador_id * 7919 + 13)
    h = r.triangular(0.9, 1.1, 1.0) + (0.05 if arquero else 0.0)
    w = r.triangular(0.94, 1.08, 1.0)
    if agachado:   # agachados la diferencia se nota menos
        h = 1 + (h - 1) * 0.5
    return h, w


def _brazo(k, piel, sombra_piel, hombro, mano_pt, lado, h, w, arquero, afuera=None):
    """Brazo completo: piel (con volumen), manga y mano. 'afuera' = hacia dónde se dobla el codo."""
    P = CU.proporciones(h, w)
    l1, l2 = P["brazo"], P["antebrazo"]
    codo = CU.codo(hombro, mano_pt, l1, l2, afuera if afuera is not None else -lado)
    s = CU.pieza([(hombro, codo, *P["r_brazo"]), (codo, mano_pt, *P["r_antebrazo"])], piel, sombra_piel, bulto=0.16)
    s += UN.manga(k, hombro, codo, w, larga=arquero, mano=mano_pt)
    direccion = (mano_pt[0] - codo[0], mano_pt[1] - codo[1])
    guante = "#f1f3f5" if UN.luz(k["camiseta"]) < 170 else "#2b2f36"
    s += CU.mano(mano_pt, direccion, P["r_mano"], guante if arquero else piel, sombra_piel, guante=arquero)
    return s


def _jugador(j, k, av, h, w, agachado, brazos, retro):
    """Capas de un jugador en coordenadas locales (origen = base del cuello):
    'atras' (brazo que pasa por detrás de la espalda), 'cuerpo', 'brazos' (los que van al hombro del compañero:
    se dibujan después de todos los cuerpos de la fila) y 'cabeza'."""
    arquero = j.get("posicion_id") == 1
    P = CU.proporciones(h, w)
    pose = (CU.pose_agachado if agachado else CU.pose_de_pie)(h, w)
    piel, sombra_piel = av.piel, av.piel_sombra
    S, W, R = P["hombro"], P["cintura"], P["ruedo"] - (8 if agachado else 0)
    capas = {"atras": "", "cuerpo": "", "brazos": ""}
    cuerpo = []
    # piernas: piel, medias y botines; en cuclillas primero la pierna (atrás) y después el muslo
    for lado in ("i", "d"):
        s = -1 if lado == "i" else 1
        cadera, rodilla, tobillo = pose[f"cadera_{lado}"], pose[f"rodilla_{lado}"], pose[f"tobillo_{lado}"]
        cuerpo.append(CU.pieza([(rodilla, tobillo, *P["r_pierna"])], piel, sombra_piel, bulto=0.3))
        cuerpo.append(UN.medias(k, rodilla, tobillo, w, agachado))
        cuerpo.append(CU.bota(tobillo, s, k.get("botin", "#1c1c22"), escala=1.22 * w))
        cuerpo.append(CU.pieza([(cadera, rodilla, *P["r_muslo"])], piel, sombra_piel, bulto=0.18))
    cuerpo.append(UN.short(k, (pose["cadera_i"], pose["cadera_d"]), (pose["rodilla_i"], pose["rodilla_d"]), W, R, w, agachado))
    # "abrazo": el brazo pasa por detrás de la espalda del compañero y no se ve; su mano se dibuja aparte (foto())
    cuerpo.append(UN.camiseta(k, str(j["id"]), S, W, R, str(j.get("numero") or ""), retro, agachado))
    for lado, tipo in brazos.items():
        s = -1 if lado == "i" else 1
        hombro = pose[f"hombro_{lado}"]
        if tipo == "colgado":       # relajado al costado, el codo apenas doblado
            cuerpo.append(_brazo(k, piel, sombra_piel, hombro, (s * (S + 1), 182 * h), s, h, w, arquero))
        elif tipo == "rodilla":     # en cuclillas: la mano apoyada en la rodilla
            rod = pose[f"rodilla_{lado}"]
            cuerpo.append(_brazo(k, piel, sombra_piel, hombro, (rod[0] - s * 10, rod[1] - 40), s, h, w, arquero, afuera=-s))
    capas["cuerpo"] = "".join(cuerpo)
    s = ESCALA_CABEZA
    capas["cabeza"] = f'<g transform="translate({-256 * s:.1f} {-408 * s:.1f}) scale({s})">{_cabeza(av, str(j["id"]))}</g>'
    return capas


def _fila_abrazada(fila: list, agachado: bool, retro: bool) -> list:
    """Una fila abrazada, en capas: brazos que abrazan (detrás de todos los torsos), cuerpos, manos sobre los hombros y
    cabezas. 'fila' = [{j, h, w, x, y, k, av, S}] de izquierda a derecha."""
    cuerpos, cabezas, manos, abrazos = [], [], [], []
    ultimo = len(fila) - 1
    afuera = "rodilla" if agachado else "colgado"
    for i, f in enumerate(fila):
        brazos = {"i": afuera if i == 0 else "oculto", "d": afuera if i == ultimo else "oculto"}
        c = _jugador(f["j"], f["k"], f["av"], f["h"], f["w"], agachado, brazos, retro)
        cuerpos.append(f'<g transform="translate({f["x"]:.1f} {f["y"]:.1f})">{c["cuerpo"]}</g>')
        cabezas.append(f'<g transform="translate({f["x"]:.1f} {f["y"]:.1f})">{c["cabeza"]}</g>')
    for i in range(ultimo):
        a, b = fila[i], fila[i + 1]
        # mano derecha de 'a' en el hombro izquierdo de 'b' y mano izquierda de 'b' en el hombro derecho de 'a'
        for duenio, sobre, lado in ((a, b, -1), (b, a, 1)):
            punto = (sobre["x"] + lado * (sobre["S"] - 26), sobre["y"] + 5)
            arquero = duenio["j"].get("posicion_id") == 1
            s_lado = -lado
            hombro = (s_lado * (duenio["S"] - 15), 27)
            local = (punto[0] - duenio["x"], punto[1] - duenio["y"])
            brazo = _brazo(duenio["k"], duenio["av"].piel, duenio["av"].piel_sombra, hombro, local, s_lado,
                           duenio["h"], duenio["w"], arquero, afuera=s_lado)
            abrazos.append(f'<g transform="translate({duenio["x"]:.1f} {duenio["y"]:.1f})">{brazo}</g>')
            guante = "#f1f3f5" if UN.luz(duenio["k"]["camiseta"]) < 170 else "#2b2f36"
            r_mano = CU.proporciones(duenio["h"], duenio["w"])["r_mano"]
            manos.append(CU.mano(punto, (-lado * 0.45, 1), r_mano * 1.12, guante if arquero else duenio["av"].piel,
                                 duenio["av"].piel_sombra, guante=arquero))
    return abrazos + cuerpos + manos + cabezas


def foto(jugadores: list, region: str, kit_campo: dict, grupo: int, semilla: int) -> str:
    rnd = random.Random(semilla)
    k_campo = {**kit_campo, "botin": rnd.choice(COLORES_BOTIN)}
    arq = next((c for c in COLORES_ARQUERO if UN.distancia(c, k_campo["camiseta"]) > 160 and UN.distancia(c, k_campo["short"]) > 120),
               next((c for c in COLORES_ARQUERO if UN.distancia(c, k_campo["camiseta"]) > 160), "#2b8a3e"))
    k_arq = {**UN.kit_arquero(k_campo, arq), "botin": k_campo["botin"]}
    retro = grupo == 3
    por_pos = {}
    for j in jugadores:
        por_pos.setdefault(j.get("posicion_id"), j)
    atras = [por_pos[p] for p in FILA_ATRAS if p in por_pos]
    adelante = [por_pos[p] for p in FILA_ADELANTE if p in por_pos]
    usados = {id(j) for j in atras + adelante}
    adelante += [j for j in jugadores if id(j) not in usados][: max(0, 5 - len(adelante))]

    def preparar(lista, agachado, paso, suelo, arco_max=0.0):
        x0 = ANCHO / 2 - paso * (len(lista) - 1) / 2
        centro = (len(lista) - 1) / 2
        fila = []
        for i, j in enumerate(lista):
            arquero = j.get("posicion_id") == 1
            h, w = _complexion(j["id"], arquero, agachado)
            arco = arco_max * (1 - (abs(i - centro) / max(1.0, centro)) ** 2)
            x, y = x0 + i * paso, suelo - CU.alto_hasta_suela(h, agachado) + arco
            k = k_arq if arquero else k_campo
            av = GA.Avatar(j["id"], j.get("edad") or 25, region, (k["camiseta"], k["ribete"]))
            fila.append({"j": j, "h": h, "w": w, "x": x, "y": y, "k": k, "av": av, "S": CU.proporciones(h, w)["hombro"]})
        return fila

    # fila de atrás de pie y fila de adelante en cuclillas, las dos ABRAZADAS: los brazos de adentro pasan por detrás de
    # la espalda del compañero (solo asoma la manga) y la mano reaparece sobre su hombro; los de las puntas dejan el
    # brazo de afuera colgando (atrás) o la mano en la rodilla (adelante). La de adelante va en un arco suave.
    figuras = (_fila_abrazada(preparar(atras, False, 166, SUELO_ATRAS), False, retro)
               + _fila_abrazada(preparar(adelante, True, 178, SUELO_ADELANTE - 6, 16.0), True, retro))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ANCHO} {ALTO}" width="{ANCHO}" height="{ALTO}" '
            f'stroke-linecap="round">{UN.defs_comunes()}{"".join(figuras)}</svg>')


# --- Datos ---------------------------------------------------------------------------------------------
def _imagen(url):
    """Imagen del bucket (PIL). Requiere Pillow."""
    import io
    import ssl
    import urllib.request

    import certifi
    from PIL import Image
    contexto = ssl.create_default_context(cafile=certifi.where())
    return Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=20, context=contexto).read()))


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
            analisis = UN.analizar_jersey(_imagen(f"{IMAGENES_PAISES_URL}/jersey/{quote(p['nombre'])}.png"))
        except Exception as e:
            print(f"  ⚠️ jersey de {p['nombre']}: {e}")
            analisis = {"patron": "liso", "camiseta": "#3b5bdb", "rayas": "#ffffff", "ribete": "#ffffff"}
        jerseys[pid] = UN.kit_final(p["nombre"], analisis, random.Random(pid))
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
