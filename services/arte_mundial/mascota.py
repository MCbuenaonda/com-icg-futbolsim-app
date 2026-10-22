"""
Mascota oficial del Mundial (SVG 500x600, fondo transparente), estilo dibujo animado con contorno (misma familia que
los avatares y las fotos de equipo). La constante de las mascotas reales: lleva el UNIFORME del anfitrión y un BALÓN;
lo que cambia es QUÉ es (config/arte_mundial.py::MASCOTAS_POR_PAIS / MASCOTAS_POR_REGION):
  - FRUTA u objeto (Naranjito, Pique): el cuerpo ES la fruta, con cara, la camiseta le cubre la mitad de abajo.
  - ANIMAL: cabeza grande (orejas, hocico o pico y rasgos: melena, rayas, manchas, cuernos, astas...) + cuerpo con
    camiseta, short, medias y botines.
Las dos con guantes blancos de mascota clásica, una pose (saludar, festejar, patear, pisar el balón), una expresión
y un accesorio de la región. Receta {base, pose, expresion, accesorio, semilla} -> siempre el mismo SVG.
"""
import math
import random
from typing import Dict, List

from services.arte_mundial import paleta as P
from services.arte_mundial.poster import _balon

ANCHO, ALTO = 500, 600
C = "#1f1a17"   # contorno (el de los avatares)
T = 5


def _trazo(extra=""):
    return f'stroke="{C}" stroke-width="{T}" stroke-linejoin="round" stroke-linecap="round" {extra}'


# =================================================================================================================
# BASES
# =================================================================================================================
# Animales: piel, hocico/claro, orejas, hocico, extras, cola
ANIMALES = {
    "perro": dict(piel="#c98a4b", claro="#f1d6b0", orejas="caidas", hocico="perro", cola="perro"),
    "lobo": dict(piel="#7d8597", claro="#e9ecef", orejas="puntiagudas", hocico="perro", cola="esponjosa"),
    "zorro": dict(piel="#e8590c", claro="#fff4e6", orejas="puntiagudas", hocico="gato", cola="esponjosa", extras=["punta_cola"]),
    "oso": dict(piel="#8b5a2b", claro="#d9a066", orejas="redondas", hocico="oso"),
    "panda": dict(piel="#f8f9fa", claro="#ffffff", orejas="redondas", hocico="oso", extras=["antifaz"], orejas_color="#212529"),
    "koala": dict(piel="#a5a5a5", claro="#e9ecef", orejas="peludas", hocico="nariz_grande"),
    "leon": dict(piel="#e0a43a", claro="#f8e1a8", orejas="redondas", hocico="gato", extras=["melena"], cola="leon"),
    "tigre": dict(piel="#f08c00", claro="#fff4e6", orejas="redondas", hocico="gato", extras=["rayas"], cola="larga"),
    "jaguar": dict(piel="#f2b134", claro="#fff3d6", orejas="redondas", hocico="gato", extras=["manchas"], cola="larga"),
    "canguro": dict(piel="#c4844f", claro="#f0d3b0", orejas="largas", hocico="perro", cola="gruesa"),
    "elefante": dict(piel="#9aa5b1", claro="#c9d1d9", orejas="elefante", hocico="trompa"),
    "mono": dict(piel="#7a4a2a", claro="#e8c39e", orejas="mono", hocico="mono", cola="rizada"),
    "toro": dict(piel="#5c3a21", claro="#c99872", orejas="pequenas", hocico="ancho", extras=["cuernos", "aro_nariz"], cola="larga"),
    "vaca": dict(piel="#f8f9fa", claro="#f4a6b4", orejas="pequenas", hocico="ancho", extras=["cuernos", "manchas_vaca"], cola="larga"),
    "llama": dict(piel="#f1e3c8", claro="#fffaf0", orejas="largas", hocico="largo", extras=["lana"]),
    "oveja": dict(piel="#495057", claro="#6c757d", orejas="caidas", hocico="largo", extras=["lana_blanca"]),
    "camello": dict(piel="#d4a373", claro="#f1d6b0", orejas="pequenas", hocico="largo"),
    "jirafa": dict(piel="#f2c14e", claro="#fff3d6", orejas="pequenas", hocico="largo", extras=["osiconos", "manchas_jirafa"]),
    "unicornio": dict(piel="#ffffff", claro="#ffe3ec", orejas="pequenas", hocico="largo", extras=["cuerno_unico", "crin"]),
    "capibara": dict(piel="#9c6b3f", claro="#b98a5f", orejas="pequenas", hocico="ancho"),
    "castor": dict(piel="#7b4a2a", claro="#c08b5c", orejas="pequenas", hocico="ancho", extras=["dientes"], cola="castor"),
    "alce": dict(piel="#6b4226", claro="#a47148", orejas="pequenas", hocico="ancho", extras=["astas"]),
    "lemur": dict(piel="#adb5bd", claro="#ffffff", orejas="puntiagudas", hocico="gato", extras=["antifaz_lemur"], cola="anillos"),
    "ajolote": dict(piel="#f7a8c4", claro="#ffd6e5", orejas="branquias", hocico="reptil"),
    "tortuga": dict(piel="#74b816", claro="#d8f5a2", orejas="ninguna", hocico="reptil", extras=["caparazon"]),
    "dragon": dict(piel="#2b8a3e", claro="#b2f2bb", orejas="puntiagudas", hocico="reptil", extras=["cuernitos", "alas"], cola="dragon"),
    # aves
    "aguila": dict(piel="#5c3d2e", claro="#ffffff", orejas="ninguna", hocico="pico_curvo", extras=["cabeza_blanca"], ave=True),
    "halcon": dict(piel="#8d6e63", claro="#efebe9", orejas="ninguna", hocico="pico_curvo", ave=True),
    "condor": dict(piel="#212529", claro="#f8f9fa", orejas="ninguna", hocico="pico_curvo", extras=["collar_blanco"], ave=True),
    "gallo": dict(piel="#f8f9fa", claro="#ffffff", orejas="ninguna", hocico="pico_corto", extras=["cresta", "barbilla"], ave=True),
    "tucan": dict(piel="#212529", claro="#fff3bf", orejas="ninguna", hocico="pico_tucan", ave=True),
    "quetzal": dict(piel="#2b8a3e", claro="#e03131", orejas="ninguna", hocico="pico_corto", extras=["penacho"], ave=True),
    "kiwi": dict(piel="#8b6f47", claro="#c4a77d", orejas="ninguna", hocico="pico_largo", ave=True),
    "pinguino": dict(piel="#212529", claro="#ffffff", orejas="ninguna", hocico="pico_corto", extras=["cara_blanca"], ave=True),
    "frailecillo": dict(piel="#212529", claro="#ffffff", orejas="ninguna", hocico="pico_frailecillo", extras=["cara_blanca"], ave=True),
    "buho": dict(piel="#8b6f47", claro="#e9d8a6", orejas="mechones", hocico="pico_corto", extras=["ojos_buho"], ave=True),
    "ave_paraiso": dict(piel="#f08c00", claro="#ffe066", orejas="ninguna", hocico="pico_corto", extras=["penacho"], ave=True),
}
# Frutas/objetos: color, forma y adornos
FRUTAS = {
    "naranja": dict(color="#f7941d", forma="redonda", adorno="hoja", textura="poros"),
    "limon": dict(color="#fcc419", forma="ovalada_h", adorno="hoja", textura="poros"),
    "tomate": dict(color="#e03131", forma="achatada", adorno="caliz"),
    "chile": dict(color="#2f9e44", forma="chile", adorno="tallo"),
    "aguacate": dict(color="#4c7a2c", forma="pera", adorno="tallo_corto"),
    "mango": dict(color="#ff922b", forma="ovalada", adorno="hoja", degradado="#fab005"),
    "pina": dict(color="#f5c518", forma="ovalada", adorno="corona", textura="rombos"),
    "coco": dict(color="#7b4a2a", forma="redonda", adorno="tres_puntos", textura="fibras"),
    "mazorca": dict(color="#ffd43b", forma="alargada", adorno="chala", textura="granos"),
    "papa": dict(color="#c9a46b", forma="papa", textura="ojitos"),
    "queso": dict(color="#ffd43b", forma="cuna", textura="agujeros"),
    "girasol": dict(color="#8b5a2b", forma="redonda_chica", adorno="petalos"),
    "sol": dict(color="#ffc61a", forma="redonda", adorno="rayos"),
}
BASES = list(ANIMALES) + list(FRUTAS)
POSES = ["saludar", "festejar", "patear", "pisar"]
EXPRESIONES = ["alegre", "picaro", "entusiasta"]


# =================================================================================================================
# Cara (compartida)
# =================================================================================================================
def _ojos(cx, cy, expresion, sep=40, r=21, color_iris="#2b1d14", grandes=False):
    if grandes:
        r = 30
    partes = []
    for i, s in enumerate((-1, 1)):
        x = cx + s * sep
        if expresion == "picaro" and s == 1:
            partes.append(f'<path d="M{x - r} {cy + 2}Q{x} {cy - r} {x + r} {cy + 2}" fill="none" {_trazo()}/>')
            continue
        partes.append(f'<ellipse cx="{x}" cy="{cy}" rx="{r}" ry="{r * 1.12:.1f}" fill="#ffffff" {_trazo()}/>')
        partes.append(f'<circle cx="{x + 4}" cy="{cy + 3}" r="{r * .58:.1f}" fill="{color_iris}"/>')
        partes.append(f'<circle cx="{x + 9}" cy="{cy - 4}" r="{r * .22:.1f}" fill="#ffffff"/>')
    return "".join(partes)


def _cejas(cx, cy, expresion, sep=40):
    alto = 12 if expresion == "entusiasta" else 6
    return "".join(f'<path d="M{cx + s * sep - 18} {cy - 34 - (alto if s == 1 and expresion == "picaro" else 0)}Q{cx + s * sep} {cy - 34 - alto - 8} {cx + s * sep + 18} {cy - 34}" '
                   f'fill="none" {_trazo()}/>' for s in (-1, 1))


def _boca(cx, cy, expresion, ancho=56):
    if expresion == "entusiasta":
        return (f'<path d="M{cx - ancho / 2} {cy}Q{cx} {cy + ancho * .95} {cx + ancho / 2} {cy}Z" fill="#7a1f1f" {_trazo()}/>'
                f'<path d="M{cx - ancho * .22} {cy + ancho * .42}Q{cx} {cy + ancho * .26} {cx + ancho * .22} {cy + ancho * .42}Q{cx} {cy + ancho * .7} {cx - ancho * .22} {cy + ancho * .42}Z" fill="#ff8787"/>'
                f'<path d="M{cx - ancho * .4} {cy + 3}H{cx + ancho * .4}V{cy + 12}H{cx - ancho * .4}Z" fill="#ffffff"/>')
    if expresion == "picaro":
        return f'<path d="M{cx - ancho / 2} {cy + 4}Q{cx + 6} {cy + ancho * .6} {cx + ancho / 2} {cy - 6}" fill="none" {_trazo()}/>'
    return (f'<path d="M{cx - ancho / 2} {cy}Q{cx} {cy + ancho * .7} {cx + ancho / 2} {cy}Q{cx} {cy + ancho * .25} {cx - ancho / 2} {cy}Z" fill="#7a1f1f" {_trazo()}/>'
            f'<path d="M{cx - ancho * .16} {cy + ancho * .3}Q{cx} {cy + ancho * .22} {cx + ancho * .16} {cy + ancho * .3}Q{cx} {cy + ancho * .45} {cx - ancho * .16} {cy + ancho * .3}Z" fill="#ff8787"/>')


def _cachetes(cx, cy, sep=62):
    return "".join(f'<ellipse cx="{cx + s * sep}" cy="{cy}" rx="14" ry="9" fill="#ff8787" opacity=".55"/>' for s in (-1, 1))


# =================================================================================================================
# Cuerpo con uniforme (compartido): camiseta, short, piernas, brazos, balón según la pose
# =================================================================================================================
POSE_GEOMETRIA = {
    #           mano izq      mano der     pie izq     pie der      balón (x, y, r)
    "saludar": ((128, 400), (378, 196), (214, 550), (290, 550), (372, 542, 32)),
    "festejar": ((92, 92), (408, 92), (206, 550), (296, 550), (130, 545, 30)),
    "patear": ((112, 330), (372, 312), (212, 550), (372, 500), (424, 474, 32)),
    "pisar": ((150, 404), (382, 250), (206, 550), (318, 500), (330, 538, 34)),
}


def _uniforme(pal):
    cam = pal["dominante"]
    detalle = pal["acento"] if P.contraste(pal["acento"], cam) > 1.4 else pal["claro"]
    short = pal["claro"] if P.contraste(pal["claro"], cam) > 1.3 else pal["dominante_oscuro"]
    num = P.texto_sobre(cam, [detalle, pal["claro"], "#ffffff", P.TINTA])
    return {"camiseta": cam, "detalle": detalle, "short": short, "medias": cam, "botin": P.TINTA, "numero": num}


def _pierna(cadera, pie, u, piel):
    (x0, y0), (x1, y1) = cadera, pie
    medio = (x0 + (x1 - x0) * .55, y0 + (y1 - y0) * .55)
    ang = math.degrees(math.atan2(y1 - y0, x1 - x0)) - 90
    return (f'<path d="M{x0} {y0}L{x1:.0f} {y1:.0f}" stroke="{C}" stroke-width="34" stroke-linecap="round"/>'
            f'<path d="M{x0} {y0}L{x1:.0f} {y1:.0f}" stroke="{piel}" stroke-width="24" stroke-linecap="round"/>'
            f'<path d="M{medio[0]:.0f} {medio[1]:.0f}L{x1:.0f} {y1:.0f}" stroke="{C}" stroke-width="35" stroke-linecap="round"/>'
            f'<path d="M{medio[0]:.0f} {medio[1]:.0f}L{x1:.0f} {y1:.0f}" stroke="{u["medias"]}" stroke-width="25" stroke-linecap="round"/>'
            f'<g transform="translate({x1:.0f} {y1:.0f}) rotate({ang if abs(ang) > 25 else 0:.0f})">'
            f'<path d="M-20 -6Q-22 18 0 20H34Q44 18 40 6Q30 -10 -20 -6Z" fill="{u["botin"]}" {_trazo()}/></g>')


def _brazo(hombro, mano, color, guante="#ffffff"):
    (x0, y0), (x1, y1) = hombro, mano
    return (f'<path d="M{x0} {y0}L{x1} {y1}" stroke="{C}" stroke-width="30" stroke-linecap="round"/>'
            f'<path d="M{x0} {y0}L{x1} {y1}" stroke="{color}" stroke-width="20" stroke-linecap="round"/>'
            f'<circle cx="{x1}" cy="{y1}" r="22" fill="{guante}" {_trazo()}/>'
            f'<path d="M{x1 - 8} {y1 - 6}v10M{x1} {y1 - 8}v12M{x1 + 8} {y1 - 6}v10" stroke="{C}" stroke-width="2.5" opacity=".5"/>')


def _ondas_saludo(x, y):
    return "".join(f'<path d="M{x + 30 + i * 10} {y - 30 - i * 6}q12 12 0 26" fill="none" stroke="{C}" stroke-width="4" stroke-linecap="round" opacity=".6"/>' for i in range(2))


def _short(u, y=420):
    return (f'<path d="M188 {y}H312L322 {y + 52}H258L250 {y + 40}L242 {y + 52}H178Z" fill="{u["short"]}" {_trazo()}/>'
            f'<path d="M188 {y + 8}H312" stroke="{u["detalle"]}" stroke-width="6"/>')


def _camiseta_animal(u, numero):
    cuerpo = "M182 292Q250 270 318 292L330 330L318 428H182L170 330Z"
    return (f'<path d="{cuerpo}" fill="{u["camiseta"]}" {_trazo()}/>'
            f'<path d="M216 286Q250 304 284 286" fill="none" stroke="{u["detalle"]}" stroke-width="9" stroke-linecap="round"/>'
            f'<path d="M318 292L330 330L318 428H292Z" fill="{P.oscurecer(u["camiseta"], .82)}" opacity=".55"/>'
            f'<text x="250" y="392" text-anchor="middle" font-family="Anton FV, Impact, sans-serif" font-size="70" fill="{u["numero"]}" '
            f'stroke="{C}" stroke-width="3" paint-order="stroke">{numero}</text>')


# =================================================================================================================
# Cabeza de ANIMAL (centro 250, 186)
# =================================================================================================================
def _cabeza_animal(a, expresion, rnd):
    piel, claro = a["piel"], a["claro"]
    oc = a.get("orejas_color", P.oscurecer(piel, .85))
    cx, cy, rx, ry = 250, 186, 112, 100
    if a["hocico"] == "largo":
        rx, ry = 96, 112
    ex = set(a.get("extras", []))
    atras, frente = [], []
    # --- detrás de la cabeza ---
    if "melena" in ex:
        puntas = " ".join(f"{cx + 150 * math.cos(math.radians(i * 15)):.0f},{cy + 140 * math.sin(math.radians(i * 15)):.0f} "
                          f"{cx + 122 * math.cos(math.radians(i * 15 + 7.5)):.0f},{cy + 116 * math.sin(math.radians(i * 15 + 7.5)):.0f}" for i in range(24))
        atras.append(f'<polygon points="{puntas}" fill="{P.oscurecer(piel, .72)}" {_trazo()}/>')
    if "lana" in ex or "lana_blanca" in ex:
        col = "#ffffff" if "lana_blanca" in ex else P.aclarar(piel, .4)
        atras += [f'<circle cx="{cx + 108 * math.cos(math.radians(i * 30)):.0f}" cy="{cy - 30 + 96 * math.sin(math.radians(i * 30)):.0f}" r="34" fill="{col}" {_trazo()}/>' for i in range(12)]
    if "crin" in ex:
        atras.append(f'<path d="M210 90Q190 140 160 170Q200 160 214 130Q210 170 186 210Q230 180 236 120Z" fill="#cc5de8" {_trazo()}/>')
    if "alas" in ex:
        atras += [f'<path transform="translate({250 + s * 120} 300) scale({s} 1)" d="M0 0Q60 -90 120 -60Q90 -40 100 -10Q70 -30 60 0Q40 -20 0 0Z" fill="{P.oscurecer(piel, .8)}" {_trazo()}/>' for s in (-1, 1)]
    # orejas
    o = a["orejas"]
    for s in (-1, 1):
        if o == "redondas":
            atras.append(f'<circle cx="{cx + s * 82}" cy="{cy - 78}" r="34" fill="{oc}" {_trazo()}/><circle cx="{cx + s * 82}" cy="{cy - 78}" r="17" fill="{claro if "antifaz" not in ex else "#495057"}"/>')
        elif o == "puntiagudas":
            atras.append(f'<path d="M{cx + s * 50} {cy - 82}L{cx + s * 96} {cy - 150}L{cx + s * 110} {cy - 52}Z" fill="{oc}" {_trazo()}/>'
                         f'<path d="M{cx + s * 66} {cy - 84}L{cx + s * 94} {cy - 128}L{cx + s * 100} {cy - 70}Z" fill="{claro}"/>')
        elif o == "caidas":
            atras.append(f'<path d="M{cx + s * 70} {cy - 70}Q{cx + s * 150} {cy - 60} {cx + s * 128} {cy + 40}Q{cx + s * 100} {cy + 30} {cx + s * 90} {cy - 20}Z" fill="{P.oscurecer(piel, .7)}" {_trazo()}/>')
        elif o == "largas":
            atras.append(f'<ellipse transform="rotate({s * 14} {cx + s * 52} {cy - 140})" cx="{cx + s * 52}" cy="{cy - 140}" rx="24" ry="66" fill="{oc}" {_trazo()}/>'
                         f'<ellipse transform="rotate({s * 14} {cx + s * 52} {cy - 140})" cx="{cx + s * 52}" cy="{cy - 136}" rx="11" ry="46" fill="{claro}"/>')
        elif o == "elefante":
            atras.append(f'<path d="M{cx + s * 80} {cy - 60}Q{cx + s * 190} {cy - 110} {cx + s * 190} {cy + 10}Q{cx + s * 180} {cy + 90} {cx + s * 96} {cy + 40}Z" fill="{oc}" {_trazo()}/>')
        elif o == "pequenas":
            atras.append(f'<ellipse transform="rotate({s * -40} {cx + s * 104} {cy - 50})" cx="{cx + s * 104}" cy="{cy - 50}" rx="28" ry="15" fill="{oc}" {_trazo()}/>')
        elif o == "peludas":
            atras.append(f'<circle cx="{cx + s * 100}" cy="{cy - 56}" r="48" fill="{piel}" {_trazo()}/><circle cx="{cx + s * 104}" cy="{cy - 52}" r="28" fill="{claro}"/>')
        elif o == "mono":
            atras.append(f'<circle cx="{cx + s * 112}" cy="{cy + 6}" r="30" fill="{piel}" {_trazo()}/><circle cx="{cx + s * 112}" cy="{cy + 6}" r="16" fill="{claro}"/>')
        elif o == "branquias":
            atras += [f'<path transform="rotate({s * (i * 26 - 26)} {cx + s * 90} {cy - 10})" d="M{cx + s * 90} {cy - 10}q{s * 60} -14 {s * 74} 6q{s * -22} 14 {s * -74} -6Z" fill="#e64980" {_trazo()}/>' for i in range(3)]
        elif o == "mechones":
            atras.append(f'<path d="M{cx + s * 56} {cy - 80}L{cx + s * 92} {cy - 140}L{cx + s * 104} {cy - 66}Z" fill="{P.oscurecer(piel, .8)}" {_trazo()}/>')
    if "astas" in ex:
        for s in (-1, 1):
            atras.append(f'<path d="M{cx + s * 60} {cy - 80}C{cx + s * 90} {cy - 150} {cx + s * 160} {cy - 140} {cx + s * 180} {cy - 190}" fill="none" stroke="{C}" stroke-width="26" stroke-linecap="round"/>'
                         f'<path d="M{cx + s * 60} {cy - 80}C{cx + s * 90} {cy - 150} {cx + s * 160} {cy - 140} {cx + s * 180} {cy - 190}" fill="none" stroke="#d4a373" stroke-width="16" stroke-linecap="round"/>'
                         + "".join(f'<path d="M{cx + s * (100 + k * 26)} {cy - 136 - k * 8}l{s * 10} -46" stroke="{C}" stroke-width="22" stroke-linecap="round"/>'
                                   f'<path d="M{cx + s * (100 + k * 26)} {cy - 136 - k * 8}l{s * 10} -46" stroke="#d4a373" stroke-width="12" stroke-linecap="round"/>' for k in range(3)))
    if "cuernos" in ex:
        atras += [f'<path d="M{cx + s * 70} {cy - 70}Q{cx + s * 140} {cy - 80} {cx + s * 150} {cy - 150}Q{cx + s * 120} {cy - 110} {cx + s * 84} {cy - 96}Z" fill="#f1e3c8" {_trazo()}/>' for s in (-1, 1)]
    if "osiconos" in ex:
        atras += [f'<path d="M{cx + s * 36} {cy - 96}V{cy - 150}" stroke="{C}" stroke-width="18" stroke-linecap="round"/><path d="M{cx + s * 36} {cy - 96}V{cy - 150}" stroke="{piel}" stroke-width="10" stroke-linecap="round"/>'
                  f'<circle cx="{cx + s * 36}" cy="{cy - 154}" r="12" fill="#8b5a2b" {_trazo()}/>' for s in (-1, 1)]
    if "cuernitos" in ex:
        atras += [f'<path d="M{cx + s * 40} {cy - 88}L{cx + s * 58} {cy - 140}L{cx + s * 70} {cy - 84}Z" fill="#ffe066" {_trazo()}/>' for s in (-1, 1)]
    # --- la cabeza ---
    frente.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{piel}" {_trazo()}/>')
    if "cabeza_blanca" in ex:
        frente.append(f'<ellipse cx="{cx}" cy="{cy - 6}" rx="{rx - 6}" ry="{ry - 10}" fill="#ffffff"/>')
    if "cara_blanca" in ex:
        frente.append(f'<ellipse cx="{cx}" cy="{cy + 16}" rx="{rx - 26}" ry="{ry - 24}" fill="#ffffff"/>')
    if "collar_blanco" in ex:
        frente.append(f'<path d="M{cx - 90} {cy + 74}Q{cx} {cy + 124} {cx + 90} {cy + 74}Q{cx} {cy + 104} {cx - 90} {cy + 74}Z" fill="#ffffff" {_trazo()}/>')
    if "rayas" in ex:
        frente += [f'<path d="M{cx + s * (rx - 6)} {cy - 30 + k * 26}l{-s * 34} 8" stroke="{C}" stroke-width="7" stroke-linecap="round"/>' for s in (-1, 1) for k in range(3)]
        frente.append(f'<path d="M{cx - 20} {cy - ry + 8}l10 26M{cx} {cy - ry + 4}v30M{cx + 20} {cy - ry + 8}l-10 26" stroke="{C}" stroke-width="7" stroke-linecap="round"/>')
    if "manchas" in ex:
        frente += [f'<circle cx="{cx + dx}" cy="{cy + dy}" r="{rr}" fill="none" stroke="{P.oscurecer(piel, .45)}" stroke-width="5"/>'
                   for dx, dy, rr in ((-70, -40, 9), (66, -50, 8), (-30, -78, 7), (34, -76, 6), (-86, 10, 7), (86, 12, 8))]
    if "manchas_vaca" in ex:
        frente += [f'<path d="M{cx - 80} {cy - 60}q30 -20 40 10q-10 30 -40 10z" fill="#212529"/>', f'<path d="M{cx + 50} {cy - 80}q40 0 30 36q-30 6 -30 -36z" fill="#212529"/>']
    if "manchas_jirafa" in ex:
        frente += [f'<rect x="{cx + dx}" y="{cy + dy}" width="22" height="18" rx="6" fill="#b5651d"/>' for dx, dy in ((-70, -60), (40, -70), (-80, 0), (56, -4))]
    if "antifaz" in ex:
        frente += [f'<ellipse transform="rotate({s * 20} {cx + s * 40} {cy - 6})" cx="{cx + s * 40}" cy="{cy - 6}" rx="30" ry="38" fill="#212529"/>' for s in (-1, 1)]
    if "antifaz_lemur" in ex:
        frente += [f'<circle cx="{cx + s * 40}" cy="{cy - 6}" r="34" fill="#212529"/>' for s in (-1, 1)]
        frente.append(f'<path d="M{cx - 18} {cy - 60}L{cx} {cy + 30}L{cx + 18} {cy - 60}Z" fill="#ffffff"/>')
    # hocico / pico
    h = a["hocico"]
    oy = cy - 10        # altura de los ojos
    boca_y = cy + 50
    if h in ("perro", "oso", "nariz_grande"):
        frente.append(f'<ellipse cx="{cx}" cy="{cy + 46}" rx="{56 if h == "perro" else 50}" ry="40" fill="{claro}" {_trazo()}/>')
        frente.append(f'<ellipse cx="{cx}" cy="{cy + 24}" rx="{22 if h != "nariz_grande" else 30}" ry="{15 if h != "nariz_grande" else 26}" fill="#2b1d14"/>')
        boca_y = cy + 52
    elif h == "gato":
        frente.append(f'<ellipse cx="{cx - 22}" cy="{cy + 44}" rx="28" ry="22" fill="{claro}" {_trazo()}/><ellipse cx="{cx + 22}" cy="{cy + 44}" rx="28" ry="22" fill="{claro}" {_trazo()}/>')
        frente.append(f'<path d="M{cx - 12} {cy + 22}H{cx + 12}L{cx} {cy + 36}Z" fill="#e64980" {_trazo()}/>')
        frente += [f'<path d="M{cx + s * 40} {cy + 42 + k * 10}l{s * 54} {k * 8 - 8}" stroke="{C}" stroke-width="3" stroke-linecap="round"/>' for s in (-1, 1) for k in range(3)]
        boca_y = cy + 56
    elif h == "ancho":
        frente.append(f'<ellipse cx="{cx}" cy="{cy + 48}" rx="74" ry="44" fill="{claro}" {_trazo()}/>')
        frente += [f'<ellipse cx="{cx + s * 26}" cy="{cy + 36}" rx="9" ry="12" fill="#2b1d14"/>' for s in (-1, 1)]
        boca_y = cy + 64
    elif h == "largo":
        frente.append(f'<ellipse cx="{cx}" cy="{cy + 64}" rx="54" ry="48" fill="{claro}" {_trazo()}/>')
        frente += [f'<ellipse cx="{cx + s * 18}" cy="{cy + 56}" rx="7" ry="10" fill="#2b1d14"/>' for s in (-1, 1)]
        boca_y = cy + 80
        oy = cy - 26
    elif h == "trompa":
        frente.append(f'<path d="M{cx - 26} {cy + 10}Q{cx - 30} {cy + 110} {cx + 20} {cy + 140}Q{cx + 40} {cy + 146} {cx + 46} {cy + 126}Q{cx + 10} {cy + 110} {cx + 26} {cy + 10}Z" fill="{piel}" {_trazo()}/>')
        boca_y = None
    elif h == "mono":
        frente.append(f'<path d="M{cx} {cy - 30}C{cx - 30} {cy - 70} {cx - 92} {cy - 40} {cx - 80} {cy + 20}C{cx - 74} {cy + 80} {cx - 30} {cy + 96} {cx} {cy + 96}'
                      f'C{cx + 30} {cy + 96} {cx + 74} {cy + 80} {cx + 80} {cy + 20}C{cx + 92} {cy - 40} {cx + 30} {cy - 70} {cx} {cy - 30}Z" fill="{claro}" {_trazo()}/>')
        frente.append(f'<path d="M{cx - 8} {cy + 26}h16" stroke="{C}" stroke-width="6" stroke-linecap="round"/>')
        boca_y = cy + 56
    elif h == "reptil":
        boca_y = cy + 40
    elif h.startswith("pico"):
        if h == "pico_curvo":
            frente.append(f'<path d="M{cx - 34} {cy + 16}Q{cx} {cy - 4} {cx + 34} {cy + 16}Q{cx + 30} {cy + 70} {cx + 2} {cy + 84}Q{cx + 8} {cy + 56} {cx - 34} {cy + 16}Z" fill="#fab005" {_trazo()}/>')
        elif h == "pico_tucan":
            frente.append(f'<path d="M{cx - 24} {cy + 10}Q{cx + 120} {cy - 10} {cx + 170} {cy + 50}Q{cx + 90} {cy + 80} {cx - 24} {cy + 54}Z" fill="#fd7e14" {_trazo()}/>'
                          f'<path d="M{cx + 120} {cy + 12}Q{cx + 160} {cy + 30} {cx + 170} {cy + 50}Q{cx + 140} {cy + 56} {cx + 116} {cy + 54}Z" fill="#212529"/>'
                          f'<path d="M{cx - 24} {cy + 34}Q{cx + 60} {cy + 30} {cx + 150} {cy + 50}" fill="none" stroke="#ffd43b" stroke-width="6"/>')
            frente.insert(1, f'<ellipse cx="{cx - 10}" cy="{cy + 40}" rx="64" ry="50" fill="{claro}"/>')
        elif h == "pico_largo":
            frente.append(f'<path d="M{cx - 14} {cy + 20}L{cx + 10} {cy + 150}L{cx + 22} {cy + 148}L{cx + 14} {cy + 20}Z" fill="#e9c46a" {_trazo()}/>')
        elif h == "pico_frailecillo":
            frente.append(f'<path d="M{cx - 30} {cy + 10}Q{cx + 40} {cy + 4} {cx + 52} {cy + 44}Q{cx + 20} {cy + 76} {cx - 30} {cy + 64}Z" fill="#fd7e14" {_trazo()}/>'
                          f'<path d="M{cx + 10} {cy + 12}Q{cx + 22} {cy + 40} {cx + 10} {cy + 70}" fill="none" stroke="#ffd43b" stroke-width="7"/>')
        else:
            frente.append(f'<path d="M{cx - 22} {cy + 24}L{cx + 22} {cy + 24}L{cx} {cy + 60}Z" fill="#fab005" {_trazo()}/>')
        boca_y = None
    if "dientes" in ex and boca_y:
        frente.append(f'<path d="M{cx - 16} {boca_y + 10}h32v24h-32z M{cx} {boca_y + 10}v24" fill="#ffffff" {_trazo()}/>')
    if "aro_nariz" in ex:
        frente.append(f'<circle cx="{cx}" cy="{cy + 82}" r="16" fill="none" stroke="#fab005" stroke-width="7"/>')
    if "cresta" in ex:
        frente.insert(0, f'<path d="M{cx - 40} {cy - 86}Q{cx - 50} {cy - 140} {cx - 20} {cy - 124}Q{cx - 10} {cy - 164} {cx + 14} {cy - 126}Q{cx + 40} {cy - 150} {cx + 40} {cy - 90}Z" fill="#e03131" {_trazo()}/>')
    if "barbilla" in ex:
        frente.append(f'<path d="M{cx - 8} {cy + 58}Q{cx - 26} {cy + 110} {cx} {cy + 108}Q{cx + 18} {cy + 96} {cx + 8} {cy + 58}Z" fill="#e03131" {_trazo()}/>')
    if "penacho" in ex:
        frente.insert(0, "".join(f'<path transform="rotate({k * 16 - 16} {cx} {cy - 90})" d="M{cx} {cy - 90}Q{cx - 16} {cy - 150} {cx} {cy - 176}Q{cx + 16} {cy - 150} {cx} {cy - 90}Z" fill="{claro if k % 2 else P.aclarar(piel, .3)}" {_trazo()}/>' for k in range(3)))
    if "cuerno_unico" in ex:
        frente.insert(0, f'<path d="M{cx - 14} {cy - 96}L{cx} {cy - 176}L{cx + 14} {cy - 96}Z" fill="#ffe066" {_trazo()}/>')
    # ojos, cejas, boca
    frente.append(_cejas(cx, oy, expresion))
    frente.append(_ojos(cx, oy, expresion, grandes="ojos_buho" in ex))
    if boca_y:
        frente.append(_boca(cx, boca_y, expresion, 46))
    if h not in ("trompa",) and not a.get("ave"):
        frente.append(_cachetes(cx, cy + 30, 74))
    return "".join(atras), "".join(frente)


def _cola(a, rnd):
    tipo, piel = a.get("cola"), a["piel"]
    if not tipo:
        return ""
    if tipo == "perro":
        return f'<path d="M320 400Q380 380 384 320" fill="none" stroke="{C}" stroke-width="26" stroke-linecap="round"/><path d="M320 400Q380 380 384 320" fill="none" stroke="{piel}" stroke-width="16" stroke-linecap="round"/>'
    if tipo == "esponjosa":
        punta = "#ffffff" if "punta_cola" in a.get("extras", []) else P.aclarar(piel, .3)
        return (f'<path d="M314 410Q420 420 420 320Q400 360 360 360Q330 390 314 410Z" fill="{piel}" {_trazo()}/>'
                f'<path d="M420 320Q414 350 392 360Q404 330 420 320Z" fill="{punta}" {_trazo()}/>')
    if tipo in ("larga", "leon"):
        extra = f'<circle cx="402" cy="300" r="16" fill="{P.oscurecer(piel, .7)}" {_trazo()}/>' if tipo == "leon" else ""
        return (f'<path d="M318 410Q400 420 402 300" fill="none" stroke="{C}" stroke-width="20" stroke-linecap="round"/>'
                f'<path d="M318 410Q400 420 402 300" fill="none" stroke="{piel}" stroke-width="11" stroke-linecap="round"/>' + extra)
    if tipo == "rizada":
        return f'<path d="M318 410Q420 420 410 330Q400 290 370 310Q360 340 390 340" fill="none" stroke="{C}" stroke-width="18" stroke-linecap="round"/><path d="M318 410Q420 420 410 330Q400 290 370 310Q360 340 390 340" fill="none" stroke="{piel}" stroke-width="9" stroke-linecap="round"/>'
    if tipo == "gruesa":
        return f'<path d="M300 430Q420 470 440 560Q380 500 300 470Z" fill="{piel}" {_trazo()}/>'
    if tipo == "castor":
        return f'<ellipse transform="rotate(-30 380 470)" cx="380" cy="470" rx="34" ry="60" fill="#5c3d2e" {_trazo()}/>'
    if tipo == "anillos":
        return "".join(f'<path d="M{316 + i * 14} {410 - i * 30}q14 -10 18 -30" fill="none" stroke="{C}" stroke-width="22" stroke-linecap="round"/>'
                       f'<path d="M{316 + i * 14} {410 - i * 30}q14 -10 18 -30" fill="none" stroke="{"#212529" if i % 2 else "#ffffff"}" stroke-width="14" stroke-linecap="round"/>' for i in range(6))
    if tipo == "dragon":
        return f'<path d="M318 420Q430 430 430 340L460 330L436 312L424 340Q410 400 318 400Z" fill="{piel}" {_trazo()}/>'
    return ""


# =================================================================================================================
# Cuerpo de FRUTA/objeto (centro 250, 250)
# =================================================================================================================
def _forma_fruta(f):
    forma = f["forma"]
    if forma == "redonda":
        return "M250 96A160 160 0 1 1 249.9 96Z", 150, 250
    if forma == "redonda_chica":
        return "M250 130A120 120 0 1 1 249.9 130Z", 150, 250
    if forma == "achatada":
        return "M250 116C350 116 410 170 410 260C410 360 340 420 250 420C160 420 90 360 90 260C90 170 150 116 250 116Z", 150, 260
    if forma == "ovalada":
        return "M250 80C340 80 390 170 390 270C390 370 330 430 250 430C170 430 110 370 110 270C110 170 160 80 250 80Z", 140, 260
    if forma == "ovalada_h":
        return "M250 120C370 120 430 190 430 270C430 350 370 410 250 410C130 410 70 350 70 270C70 190 130 120 250 120Z", 160, 260
    if forma == "chile":
        return "M222 92C290 84 320 150 316 250C312 340 300 410 250 440C230 452 214 440 206 420C188 360 180 250 186 170C190 120 200 96 222 92Z", 110, 240
    if forma == "pera":
        return "M250 80C300 80 316 130 320 180C380 220 400 290 390 340C376 410 320 440 250 440C180 440 124 410 110 340C100 290 120 220 180 180C184 130 200 80 250 80Z", 130, 270
    if forma == "alargada":
        return "M250 60C320 60 340 150 340 260C340 370 310 440 250 440C190 440 160 370 160 260C160 150 180 60 250 60Z", 120, 250
    if forma == "papa":
        return "M240 110C330 96 400 160 404 250C408 340 360 420 260 426C160 432 96 370 98 280C100 190 150 124 240 110Z", 150, 260
    if forma == "cuna":
        return "M100 420L130 150Q250 120 400 210L410 420Z", 150, 270
    return "M250 96A160 160 0 1 1 249.9 96Z", 150, 250


def _fruta(f, nombre, pal, u, numero, expresion, rnd):
    d, medio_ancho, cara_y = _forma_fruta(f)
    color = f["color"]
    sombra = P.oscurecer(color, .82)
    partes_atras, partes = [], []
    # adornos detrás
    if f.get("adorno") == "rayos":
        partes_atras.append("".join(f'<path transform="rotate({i * 22.5} 250 256)" d="M236 90L250 40L264 90Z" fill="{P.oscurecer(color, .9)}" {_trazo()}/>' for i in range(16)))
    if f.get("adorno") == "petalos":
        partes_atras.append("".join(f'<ellipse transform="rotate({i * 30} 250 250)" cx="250" cy="96" rx="34" ry="62" fill="#fcc419" {_trazo()}/>' for i in range(12)))
    if f.get("adorno") == "corona":
        partes_atras.append("".join(f'<path transform="rotate({k * 18 - 36} 250 96)" d="M250 96Q226 40 250 -6Q274 40 250 96Z" fill="#40c057" {_trazo()}/>' for k in range(5)))
    if f.get("adorno") == "chala":
        partes_atras.append("".join(f'<path transform="translate(250 0) scale({s} 1)" d="M60 430Q140 300 100 120Q70 200 40 300Z" fill="#82c91e" {_trazo()}/>' for s in (-1, 1)))
    # cuerpo
    grad = ""
    if f.get("degradado"):
        grad = (f'<linearGradient id="gfr" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{f["degradado"]}"/>'
                f'<stop offset="1" stop-color="{color}"/></linearGradient>')
    relleno = "url(#gfr)" if grad else color
    partes.append(f'{grad}<clipPath id="cfr"><path d="{d}"/></clipPath><path d="{d}" fill="{relleno}"/>')
    tex = f.get("textura")
    if tex == "poros":
        partes.append("".join(f'<circle cx="{rnd.randint(110, 390)}" cy="{rnd.randint(110, 300)}" r="2.5" fill="{sombra}" clip-path="url(#cfr)"/>' for _ in range(40)))
    elif tex == "rombos":
        partes.append("".join(f'<path d="M{x} 60L{x + 400} 460M{x + 400} 60L{x} 460" stroke="{P.oscurecer(color, .7)}" stroke-width="4" clip-path="url(#cfr)"/>' for x in range(-300, 500, 46)))
    elif tex == "fibras":
        partes.append("".join(f'<path d="M{x} 100q10 150 -6 320" stroke="{P.oscurecer(color, .7)}" stroke-width="3" fill="none" clip-path="url(#cfr)"/>' for x in range(110, 400, 22)))
    elif tex == "granos":
        partes.append("".join(f'<ellipse cx="{x}" cy="{y}" rx="13" ry="11" fill="{P.aclarar(color, .3)}" stroke="{P.oscurecer(color, .8)}" stroke-width="2" clip-path="url(#cfr)"/>'
                              for y in range(70, 300, 24) for x in range(170 + (y // 24 % 2) * 12, 340, 26)))
    elif tex == "ojitos":
        partes.append("".join(f'<path d="M{x} {y}q6 -4 12 0" stroke="{P.oscurecer(color, .6)}" stroke-width="3" fill="none"/>' for x, y in ((160, 170), (320, 150), (350, 260), (140, 280))))
    elif tex == "agujeros":
        partes.append("".join(f'<ellipse cx="{x}" cy="{y}" rx="{rr}" ry="{rr * .8:.0f}" fill="{P.oscurecer(color, .8)}" clip-path="url(#cfr)"/>' for x, y, rr in ((170, 220, 16), (330, 240, 12), (240, 190, 9), (360, 320, 14))))
    partes.append(f'<g clip-path="url(#cfr)"><path d="{d}" fill="{sombra}" opacity=".35" transform="translate(40 10)"/></g>')
    # camiseta: la mitad de abajo de la fruta
    cam_y = cara_y + 66
    partes.append(f'<g clip-path="url(#cfr)"><rect x="0" y="{cam_y}" width="500" height="400" fill="{u["camiseta"]}"/>'
                  f'<path d="M0 {cam_y}H500" stroke="{u["detalle"]}" stroke-width="12"/>'
                  f'<rect x="320" y="{cam_y}" width="200" height="400" fill="{P.oscurecer(u["camiseta"], .82)}" opacity=".5"/></g>')
    partes.append(f'<text x="250" y="{cam_y + 74}" text-anchor="middle" font-family="Anton FV, Impact, sans-serif" font-size="62" fill="{u["numero"]}" '
                  f'stroke="{C}" stroke-width="3" paint-order="stroke">{numero}</text>')
    partes.append(f'<path d="{d}" fill="none" {_trazo()}/>')
    # adornos delante
    ad = f.get("adorno")
    if ad == "hoja":
        partes.append(f'<path d="M250 100Q252 80 246 64" stroke="{C}" stroke-width="6" fill="none"/><path d="M250 76Q290 40 320 70Q290 100 250 76Z" fill="#40c057" {_trazo()}/>')
    elif ad == "caliz":
        partes.append("".join(f'<path transform="rotate({i * 72} 250 118)" d="M250 118Q236 96 250 70Q264 96 250 118Z" fill="#2f9e44" {_trazo()}/>' for i in range(5)))
    elif ad == "tallo":
        partes.append(f'<path d="M226 96Q220 60 250 40" stroke="{C}" stroke-width="22" fill="none" stroke-linecap="round"/><path d="M226 96Q220 60 250 40" stroke="#2b8a3e" stroke-width="12" fill="none" stroke-linecap="round"/>'
                      f'<path d="M196 104Q226 80 256 104Q226 116 196 104Z" fill="#2b8a3e" {_trazo()}/>')
    elif ad == "tallo_corto":
        partes.append(f'<path d="M250 84V60" stroke="{C}" stroke-width="16" stroke-linecap="round"/><path d="M250 84V60" stroke="#5c3d2e" stroke-width="8" stroke-linecap="round"/>')
    elif ad == "tres_puntos":
        partes.append("".join(f'<circle cx="{250 + dx}" cy="{122 + dy}" r="9" fill="#3b2314"/>' for dx, dy in ((-20, 0), (20, 0), (0, 22))))
    # cara
    cy = cara_y - 10
    cara = _cejas(250, cy, expresion) + _ojos(250, cy, expresion) + _boca(250, cy + 48, expresion, 60) + _cachetes(250, cy + 34, 76)
    if ad == "petalos":
        cara = _ojos(250, cy, expresion, sep=32, r=17) + _boca(250, cy + 40, expresion, 44)
    return "".join(partes_atras), "".join(partes) + cara, medio_ancho, cam_y


# =================================================================================================================
# Accesorios
# =================================================================================================================
def _accesorio(nombre, pal, top, centro_x=250, ancho=110):
    a, d = pal["acento"], pal["dominante"]
    if nombre == "sombrero_charro":
        return (f'<ellipse cx="{centro_x}" cy="{top + 24}" rx="{ancho * 1.5:.0f}" ry="30" fill="#c9a227" {_trazo()}/>'
                f'<path d="M{centro_x - 56} {top + 22}Q{centro_x - 50} {top - 70} {centro_x} {top - 80}Q{centro_x + 50} {top - 70} {centro_x + 56} {top + 22}Z" fill="#c9a227" {_trazo()}/>'
                f'<path d="M{centro_x - 54} {top + 8}Q{centro_x} {top - 6} {centro_x + 54} {top + 8}" stroke="{d}" stroke-width="10" fill="none"/>'
                f'<path d="M{centro_x - ancho * 1.4:.0f} {top + 26}Q{centro_x} {top + 54} {centro_x + ancho * 1.4:.0f} {top + 26}" stroke="{a}" stroke-width="6" fill="none"/>')
    if nombre == "sombrero_paja":
        return (f'<ellipse cx="{centro_x}" cy="{top + 18}" rx="{ancho * 1.2:.0f}" ry="22" fill="#e9c46a" {_trazo()}/>'
                f'<path d="M{centro_x - 60} {top + 16}Q{centro_x - 56} {top - 40} {centro_x} {top - 44}Q{centro_x + 56} {top - 40} {centro_x + 60} {top + 16}Z" fill="#e9c46a" {_trazo()}/>'
                f'<path d="M{centro_x - 58} {top + 2}H{centro_x + 58}" stroke="{d}" stroke-width="10"/>')
    if nombre == "gorra":
        return (f'<path d="M{centro_x - 82} {top + 30}Q{centro_x - 80} {top - 50} {centro_x} {top - 54}Q{centro_x + 80} {top - 50} {centro_x + 82} {top + 30}Z" fill="{d}" {_trazo()}/>'
                f'<path d="M{centro_x + 20} {top + 26}Q{centro_x + 120} {top + 20} {centro_x + 150} {top + 40}Q{centro_x + 100} {top + 50} {centro_x + 20} {top + 40}Z" fill="{P.oscurecer(d, .75)}" {_trazo()}/>'
                f'<circle cx="{centro_x}" cy="{top - 52}" r="9" fill="{a}" {_trazo()}/>')
    if nombre == "boina":
        return (f'<path d="M{centro_x - 96} {top + 20}Q{centro_x - 70} {top - 50} {centro_x + 20} {top - 46}Q{centro_x + 110} {top - 30} {centro_x + 96} {top + 20}Q{centro_x} {top + 4} {centro_x - 96} {top + 20}Z" fill="{P.TINTA if d == a else d}" {_trazo()}/>'
                f'<path d="M{centro_x + 10} {top - 46}l4 -16" stroke="{C}" stroke-width="6" stroke-linecap="round"/>')
    if nombre == "gorro_lana":
        rayas = "".join(f'<path d="M{centro_x - 86} {top - 10 + k * 20}H{centro_x + 86}" stroke="{a if k % 2 else "#ffffff"}" stroke-width="9"/>' for k in range(2))
        return (f'<path d="M{centro_x - 90} {top + 30}Q{centro_x - 90} {top - 80} {centro_x} {top - 84}Q{centro_x + 90} {top - 80} {centro_x + 90} {top + 30}Z" fill="{d}" {_trazo()}/>'
                + rayas + f'<circle cx="{centro_x}" cy="{top - 88}" r="22" fill="#ffffff" {_trazo()}/>')
    if nombre == "vincha":
        return (f'<path d="M{centro_x - 104} {top + 46}Q{centro_x} {top + 20} {centro_x + 104} {top + 46}" stroke="{C}" stroke-width="30" fill="none"/>'
                f'<path d="M{centro_x - 104} {top + 46}Q{centro_x} {top + 20} {centro_x + 104} {top + 46}" stroke="{d}" stroke-width="20" fill="none"/>'
                f'<circle cx="{centro_x}" cy="{top + 32}" r="10" fill="{a}"/><path d="M{centro_x + 100} {top + 48}l40 20M{centro_x + 100} {top + 48}l46 -4" stroke="{d}" stroke-width="12" stroke-linecap="round"/>')
    if nombre == "corona_flores":
        return "".join(f'<circle cx="{centro_x + 100 * math.cos(math.radians(200 + i * 20)):.0f}" cy="{top + 40 + 40 * math.sin(math.radians(200 + i * 20)):.0f}" r="16" '
                       f'fill="{["#ff6b6b", "#ffd43b", "#ffffff", "#ff922b"][i % 4]}" {_trazo()}/>' for i in range(8))
    return ""


def _bufanda(pal, y):
    a, d = pal["acento"], pal["dominante"]
    return (f'<path d="M180 {y}Q250 {y + 30} 320 {y}L322 {y + 30}Q250 {y + 58} 178 {y + 30}Z" fill="{a}" {_trazo()}/>'
            f'<path d="M286 {y + 22}L300 {y + 110}L330 {y + 106}L306 {y + 20}Z" fill="{a}" {_trazo()}/>'
            f'<path d="M290 {y + 50}l24 -3M294 {y + 76}l24 -3" stroke="{d}" stroke-width="8"/>')


def _panuelo(pal, y):
    return (f'<path d="M196 {y}Q250 {y + 20} 304 {y}L250 {y + 64}Z" fill="{pal["acento"]}" {_trazo()}/>'
            + "".join(f'<circle cx="{250 + dx}" cy="{y + dy}" r="4" fill="#ffffff"/>' for dx, dy in ((-20, 12), (14, 16), (0, 34))))


# =================================================================================================================
# Composición
# =================================================================================================================
def dibujar(receta: Dict, colores_bandera: List[dict], anio) -> str:
    pal = P.de_bandera(colores_bandera)
    rnd = random.Random(receta["semilla"])
    base, pose, expresion, acc = receta["base"], receta["pose"], receta["expresion"], receta.get("accesorio", "ninguno")
    u = _uniforme(pal)
    numero = str(anio)[-2:]
    manos_pies = POSE_GEOMETRIA[pose]
    (mi, md, pi, pd, (bx, by, br)) = manos_pies
    capas = []
    if base in FRUTAS:
        f = FRUTAS[base]
        # si la fruta y la camiseta casi no se distinguen (chile verde con camiseta verde), la camiseta va del acento
        if P._distancia(f["color"], u["camiseta"]) < 150:
            u = _uniforme({**pal, "dominante": pal["acento"], "acento": pal["dominante"]})
        atras, cuerpo, medio, cam_y = _fruta(f, base, pal, u, numero, expresion, rnd)
        color_brazo = P.oscurecer(f["color"], .9)
        hombro_y = cam_y + 10
        hombros = ((250 - medio + 14, hombro_y), (250 + medio - 14, hombro_y))
        capas.append(atras)
        capas.append(_short(u, 418))
        capas.append(_pierna((222, 466), pi, u, color_brazo) + _pierna((278, 466), pd, u, color_brazo))
        capas.append(cuerpo)
        capas.append(_brazo(hombros[0], mi, color_brazo) + _brazo(hombros[1], md, color_brazo))
        if acc in ("bufanda",):
            pass  # en las frutas la bufanda taparía la cara: se usa el pañuelo
        if acc in ("bufanda", "pañuelo"):   # pañuelo chico al cuello, sin tapar el número
            capas.append(f'<g transform="translate(250 {cam_y - 14}) scale(.62) translate(-250 {-(cam_y - 14)})">{_panuelo(pal, cam_y - 14)}</g>')
        top = {"chile": 92, "alargada": 64, "ovalada": 86, "pera": 84}.get(f["forma"], 104) if f.get("adorno") not in ("corona", "rayos", "petalos") else None
        if top is not None and acc not in ("ninguno", "bufanda", "pañuelo"):
            capas.append(_accesorio(acc, pal, top - 20, ancho=90))
    else:
        a = ANIMALES[base]
        cabeza_atras, cabeza = _cabeza_animal(a, expresion, rnd)
        piel = a["piel"]
        capas.append(_cola(a, rnd))
        capas.append(_short(u, 420))
        capas.append(_pierna((222, 468), pi, u, piel) + _pierna((278, 468), pd, u, piel))
        capas.append(_camiseta_animal(u, numero))
        if "caparazon" in a.get("extras", []):
            capas.append(f'<path d="M170 300Q120 360 170 430" fill="none" stroke="#5c940d" stroke-width="22" stroke-linecap="round"/>')
        capas.append(_brazo((186, 304), mi, piel) + _brazo((314, 304), md, piel))
        if acc == "bufanda":
            capas.append(_bufanda(pal, 272))
        elif acc == "pañuelo":
            capas.append(_panuelo(pal, 278))
        capas.append(cabeza_atras + cabeza)
        if acc not in ("ninguno", "bufanda", "pañuelo") and not set(a.get("extras", [])) & {"astas", "cuernos", "cresta", "penacho", "cuerno_unico", "osiconos", "melena"}:
            capas.append(_accesorio(acc, pal, 100))
    if pose == "saludar":
        capas.append(_ondas_saludo(*md))
    sombra = f'<ellipse cx="250" cy="575" rx="170" ry="16" fill="#000" opacity=".18"/>'
    balon = _balon(bx, by, br, contorno=C, idc="balon_mascota")
    from services.arte_mundial.poster import estilos_fuentes
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ANCHO} {ALTO}" width="{ANCHO}" height="{ALTO}" stroke-linecap="round">'
            f'{estilos_fuentes()}{sombra}{"".join(capas)}{balon}</svg>')


def receta_aleatoria(bases: List[str], accesorios: List[str], r: random.Random) -> Dict:
    validas = [b for b in bases if b in BASES] or ["leon"]
    tirada = r.random()   # la favorita del país sale más seguido
    base = validas[0] if tirada < .45 else r.choice(validas)
    return {"base": base, "pose": r.choice(POSES), "expresion": r.choice(EXPRESIONES),
            "accesorio": r.choice(accesorios or ["ninguno"]), "semilla": r.randint(0, 10 ** 6)}


def nombre_para(base: str, nombres_por_base: Dict[str, List[str]], r: random.Random, usados=()) -> str:
    """
    Nombre que no se haya usado en otro Mundial: primero los curados (Pique, Naranjito...), después variantes del
    diminutivo de la base (-ito, -ín, -ón, -i...) y, si una base ya se usó muchísimo, una "dinastía" (Naranjito II).
    """
    usados = set(usados)
    curados = list(nombres_por_base.get(base, []))
    r.shuffle(curados)
    raiz = base.replace("_", " ").split(" ")[0].replace("ñ", "ñ")
    raiz = raiz[:-1] if raiz[-1] in "aeiou" else raiz
    variantes = [raiz.capitalize() + suf for suf in ("ito", "ín", "ón", "i", "illo", "ucho", "ete", "ote")]
    for nombre in curados + variantes:
        if nombre not in usados:
            return nombre
    romanos = ["II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]
    for rom in romanos:
        for nombre in (curados or variantes):
            if f"{nombre} {rom}" not in usados:
                return f"{nombre} {rom}"
    return f"{(curados or variantes)[0]} {r.randint(11, 99)}"
