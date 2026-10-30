"""
Cuerpos de la foto de equipo: extremidades redondeadas con volumen (no bloques rígidos), articulaciones sin costuras
y sombras suaves. Todo en coordenadas locales con origen en la base del cuello (y hacia abajo).

Cada extremidad es un TUBO (dos círculos unidos por curvas) con un leve abultado de músculo. Para que los tramos de
un brazo o una pierna se vean como una sola pieza, se dibujan en dos pasadas: primero todos los contornos (relleno y
trazo oscuro) y encima todos los rellenos sin trazo.

Proporciones: 'h' (estatura, ~0.9-1.1) estira torso y piernas; 'w' (complexión, ~0.94-1.08) ensancha.
"""
import math
from typing import Dict, List, Optional, Tuple

Punto = Tuple[float, float]
C = "#1f1a17"   # contorno (el mismo de los avatares)
T = 2.7         # grosor del contorno (fino y suave)


def _f(v: float) -> str:
    return f"{v:.1f}"


def tubo(a: Punto, b: Punto, ra: float, rb: float, bulto: float = 0.12) -> str:
    """Path de un tramo redondeado de 'a' (radio ra) a 'b' (radio rb), con el lado +n algo abultado (músculo)."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    largo = math.hypot(dx, dy) or 1.0
    ux, uy = dx / largo, dy / largo
    nx, ny = -uy, ux
    p1 = (ax + nx * ra, ay + ny * ra)
    p2 = (bx + nx * rb, by + ny * rb)
    c1 = (ax + ux * largo * 0.3 + nx * ra * (1 + bulto), ay + uy * largo * 0.3 + ny * ra * (1 + bulto))
    c2 = (ax + ux * largo * 0.72 + nx * rb * (1 + bulto * 0.8), ay + uy * largo * 0.72 + ny * rb * (1 + bulto * 0.8))
    q1 = (bx - nx * rb, by - ny * rb)
    q2 = (ax - nx * ra, ay - ny * ra)
    d1 = (ax + ux * largo * 0.72 - nx * rb * (1 + bulto * 0.3), ay + uy * largo * 0.72 - ny * rb * (1 + bulto * 0.3))
    d2 = (ax + ux * largo * 0.3 - nx * ra * (1 + bulto * 0.4), ay + uy * largo * 0.3 - ny * ra * (1 + bulto * 0.4))
    return (f"M{_f(p1[0])} {_f(p1[1])}C{_f(c1[0])} {_f(c1[1])} {_f(c2[0])} {_f(c2[1])} {_f(p2[0])} {_f(p2[1])}"
            f"A{_f(rb)} {_f(rb)} 0 0 0 {_f(q1[0])} {_f(q1[1])}"
            f"C{_f(d1[0])} {_f(d1[1])} {_f(d2[0])} {_f(d2[1])} {_f(q2[0])} {_f(q2[1])}"
            f"A{_f(ra)} {_f(ra)} 0 0 0 {_f(p1[0])} {_f(p1[1])}Z")


def banda(a: Punto, b: Punto, r: float, color: str, grosor: float = 6.0) -> str:
    """Banda que cruza la extremidad en 'b' (puño de la manga, borde de la media): una línea perpendicular al tramo."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    largo = math.hypot(dx, dy) or 1.0
    ux, uy = dx / largo, dy / largo
    nx, ny = -uy, ux
    c = (b[0] - ux * grosor / 2, b[1] - uy * grosor / 2)
    r = r * 0.96
    return (f'<path d="M{_f(c[0] + nx * r)} {_f(c[1] + ny * r)}L{_f(c[0] - nx * r)} {_f(c[1] - ny * r)}" stroke="{color}" '
            f'stroke-width="{_f(grosor)}" stroke-linecap="butt"/>'
            f'<path d="M{_f(c[0] + nx * r - ux * grosor / 2)} {_f(c[1] + ny * r - uy * grosor / 2)}L{_f(c[0] - nx * r - ux * grosor / 2)} '
            f'{_f(c[1] - ny * r - uy * grosor / 2)}" stroke="{C}" stroke-width="1.4" opacity=".5"/>')


def sombra_tubo(a: Punto, b: Punto, ra: float, rb: float) -> str:
    """Franja de sombra dentro del tubo, sobre el lado -n (da volumen sin salirse del contorno)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    largo = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / largo, dx / largo
    k = 0.42
    a2 = (a[0] - nx * ra * k, a[1] - ny * ra * k)
    b2 = (b[0] - nx * rb * k, b[1] - ny * rb * k)
    return tubo(a2, b2, ra * 0.5, rb * 0.5, 0.0)


def pieza(tramos: List[Tuple[Punto, Punto, float, float]], color: str, sombra: Optional[str] = None, bulto: float = 0.12) -> str:
    """Una extremidad de varios tramos como una sola forma: contornos, rellenos y (opcional) sombra suave."""
    contornos = "".join(f'<path d="{tubo(a, b, ra, rb, bulto)}" fill="{C}" stroke="{C}" stroke-width="{T * 2}" stroke-linejoin="round"/>'
                        for a, b, ra, rb in tramos)
    rellenos = "".join(f'<path d="{tubo(a, b, ra, rb, bulto)}" fill="{color}"/>' for a, b, ra, rb in tramos)
    sombras = ""
    if sombra:
        sombras = "".join(f'<path d="{sombra_tubo(a, b, ra, rb)}" fill="{sombra}" opacity=".32"/>' for a, b, ra, rb in tramos)
    return contornos + rellenos + sombras


def codo(hombro: Punto, mano: Punto, l1: float, l2: float, afuera: float) -> Punto:
    """Codo (o rodilla) por cinemática inversa de dos tramos. 'afuera' = hacia qué lado se dobla (+1 / -1)."""
    dx, dy = mano[0] - hombro[0], mano[1] - hombro[1]
    d = math.hypot(dx, dy) or 1.0
    d = min(d, l1 + l2 - 0.5)
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    hh = math.sqrt(max(0.0, l1 * l1 - a * a))
    ux, uy = dx / d, dy / d
    mx, my = hombro[0] + ux * a, hombro[1] + uy * a
    return (mx - uy * hh * afuera, my + ux * hh * afuera)


def mano(p: Punto, direccion: Punto, r: float, color: str, sombra: str, guante: bool = False) -> str:
    """Mano redondeada con pulgar, orientada según el antebrazo (o guante de arquero, más grande)."""
    ang = math.degrees(math.atan2(direccion[1], direccion[0])) - 90
    r = r * (1.25 if guante else 1.0)
    return (f'<g transform="translate({_f(p[0])} {_f(p[1])}) rotate({ang:.0f})">'
            f'<ellipse cx="{_f(r * 0.55)}" cy="{_f(r * 0.2)}" rx="{_f(r * 0.42)}" ry="{_f(r * 0.6)}" fill="{color}" stroke="{C}" stroke-width="{T}" '
            f'transform="rotate(-28 {_f(r * 0.55)} {_f(r * 0.2)})"/>'
            f'<ellipse cx="0" cy="{_f(r * 0.45)}" rx="{_f(r * 0.92)}" ry="{_f(r * 1.08)}" fill="{color}" stroke="{C}" stroke-width="{T}"/>'
            f'<path d="M{_f(-r * 0.5)} {_f(r * 0.95)}Q0 {_f(r * 1.25)} {_f(r * 0.5)} {_f(r * 0.95)}" fill="none" stroke="{sombra}" stroke-width="{_f(r * 0.3)}" opacity=".45"/>'
            + (f'<path d="M{_f(-r * 0.75)} {_f(r * 0.1)}H{_f(r * 0.75)}" stroke="{C}" stroke-width="2" opacity=".5"/>' if guante else "")
            + "</g>")


def bota(tobillo: Punto, sentido: int, color: str, suela: str = "#f1f3f5", escala: float = 1.0) -> str:
    """Botín redondeado apuntando hacia afuera (sentido -1 izquierda / +1 derecha)."""
    x, y = tobillo
    s = sentido
    e = escala
    d = (f"M{_f(x - s * 13 * e)} {_f(y - 6 * e)}C{_f(x - s * 15 * e)} {_f(y + 10 * e)} {_f(x - s * 14 * e)} {_f(y + 16 * e)} {_f(x - s * 6 * e)} {_f(y + 17 * e)}"
         f"L{_f(x + s * 26 * e)} {_f(y + 17 * e)}C{_f(x + s * 36 * e)} {_f(y + 16 * e)} {_f(x + s * 36 * e)} {_f(y + 4 * e)} {_f(x + s * 24 * e)} {_f(y + 1 * e)}"
         f"C{_f(x + s * 14 * e)} {_f(y - 2 * e)} {_f(x + s * 10 * e)} {_f(y - 9 * e)} {_f(x + s * 6 * e)} {_f(y - 10 * e)}Z")
    return (f'<path d="{d}" fill="{color}" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>'
            f'<path d="M{_f(x - s * 7 * e)} {_f(y + 14 * e)}H{_f(x + s * 28 * e)}" stroke="{suela}" stroke-width="{_f(3.2 * e)}" stroke-linecap="round"/>'
            f'<path d="M{_f(x + s * 3 * e)} {_f(y - 4 * e)}l{_f(s * 8 * e)} 3m{_f(-s * 9 * e)} 4l{_f(s * 8 * e)} 3" stroke="{suela}" stroke-width="2" opacity=".85"/>')


# =================================================================================================================
# Poses: dónde está cada articulación (origen = base del cuello)
# =================================================================================================================
def proporciones(h: float, w: float) -> Dict[str, float]:
    return {
        "hombro": 68 * w, "cintura": 50 * w, "ruedo": 158 * h,
        "brazo": 80 * h, "antebrazo": 74 * h, "r_brazo": (17 * w, 13.5 * w), "r_antebrazo": (13.5 * w, 10 * w),
        "muslo": 88 * h, "pierna": 86 * h, "r_muslo": (23 * w, 16.5 * w), "r_pierna": (16.5 * w, 10.5 * w),
        "r_mano": 11.5 * w,
    }


def pose_de_pie(h: float, w: float) -> Dict[str, Punto]:
    p = proporciones(h, w)
    pies = 340 * h
    return {
        "hombro_i": (-(p["hombro"] - 15), 27), "hombro_d": (p["hombro"] - 15, 27),
        "cadera_i": (-22 * w, 166 * h), "cadera_d": (22 * w, 166 * h),
        "rodilla_i": (-26 * w, 166 * h + p["muslo"]), "rodilla_d": (26 * w, 166 * h + p["muslo"]),
        "tobillo_i": (-27 * w, pies - 16), "tobillo_d": (27 * w, pies - 16),
    }


def pose_agachado(h: float, w: float) -> Dict[str, Punto]:
    return {
        "hombro_i": (-(68 * w - 15), 27), "hombro_d": (68 * w - 15, 27),
        "cadera_i": (-24 * w, 166 * h), "cadera_d": (24 * w, 166 * h),
        "rodilla_i": (-64 * w, 206 * h), "rodilla_d": (64 * w, 206 * h),
        "tobillo_i": (-60 * w, 316 * h), "tobillo_d": (60 * w, 316 * h),
    }


def alto_hasta_suela(h: float, agachado: bool) -> float:
    """De la base del cuello a la suela del botín (para apoyar a todos en el mismo suelo)."""
    return (316 * h if agachado else 340 * h - 16) + 17
