"""
Uniformes de la foto de equipo: el diseño de la camiseta se lee de la imagen del jersey de cada país (colores, rayas,
aros, mitades, banda, cuadros y el color del ribete) y se DIBUJA de nuevo, sin logos ni escudos (esas imágenes traen
marcas reales). Short y medias salen de kits.py o de una regla. Torso, mangas y short con textura de tela y volumen.
"""
import math
from typing import Dict, List, Optional, Tuple

from plantilla_foto import cuerpo as CU
from plantilla_foto.kits import KITS, BLANCO, NEGRO

C, T = CU.C, CU.T


# --- color -----------------------------------------------------------------------------------------------------
def hex_rgb(h: str) -> Tuple[int, int, int]:
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def rgb_hex(c) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(round(v)))) for v in c))


def distancia(a: str, b: str) -> float:
    return sum(abs(x - y) for x, y in zip(hex_rgb(a), hex_rgb(b)))


def luz(h: str) -> float:
    r, g, b = hex_rgb(h)
    return 0.299 * r + 0.587 * g + 0.114 * b


def oscurecer(h: str, f: float) -> str:
    return rgb_hex(tuple(v * f for v in hex_rgb(h)))


def aclarar(h: str, f: float) -> str:
    return rgb_hex(tuple(v + (255 - v) * f for v in hex_rgb(h)))


# --- lectura del jersey (imagen 220x220 del bucket) -----------------------------------------------------------
def _dos_grupos(pixeles: List[Tuple[int, int, int]]):
    """k-medias con k=2: (color mayoritario, color minoritario, fracción del minoritario)."""
    def d(a, b):
        return sum(abs(x - y) for x, y in zip(a, b))
    c1 = max(set(pixeles), key=pixeles.count)
    c2 = max(pixeles, key=lambda p: d(p, c1))
    for _ in range(8):
        g1 = [p for p in pixeles if d(p, c1) <= d(p, c2)]
        g2 = [p for p in pixeles if d(p, c1) > d(p, c2)]
        if not g1 or not g2:
            break
        c1 = tuple(sum(v) / len(g1) for v in zip(*g1))
        c2 = tuple(sum(v) / len(g2) for v in zip(*g2))
    g1n = sum(1 for p in pixeles if d(p, c1) <= d(p, c2))
    if g1n < len(pixeles) - g1n:
        c1, c2 = c2, c1
        g1n = len(pixeles) - g1n
    return c1, c2, 1 - g1n / max(1, len(pixeles))


def _tramos(muestras: List[int], minimo: int = 4) -> List[int]:
    """Etiquetas (0/1) a lo largo de una línea -> lista de tramos (ignora manchas cortas: logos, sombras)."""
    tramos = []
    for e in muestras:
        if tramos and tramos[-1][0] == e:
            tramos[-1][1] += 1
        else:
            tramos.append([e, 1])
    limpios = []
    for e, n in tramos:
        if n < minimo and limpios:
            limpios[-1][1] += n
        elif limpios and limpios[-1][0] == e:
            limpios[-1][1] += n
        else:
            limpios.append([e, n])
    return [e for e, _ in limpios]


def analizar_jersey(imagen) -> Dict:
    """Diseño de la camiseta desde la imagen (PIL RGBA): colores, patrón, cantidad de franjas y ribete."""
    im = imagen.convert("RGBA").resize((220, 220))
    px = im.load()

    def color(x, y):
        r, g, b, a = px[x, y]
        return (r, g, b) if a > 200 else None

    cuerpo = [c for y in range(72, 192, 2) for x in range(74, 148, 2) if (c := color(x, y))]
    if len(cuerpo) < 50:
        return {"patron": "liso", "camiseta": "#3b5bdb", "rayas": BLANCO, "ribete": BLANCO}
    c1, c2, frac = _dos_grupos(cuerpo)

    def etiqueta(c):
        return 0 if sum(abs(a - b) for a, b in zip(c, c1)) <= sum(abs(a - b) for a, b in zip(c, c2)) else 1

    contraste = sum(abs(a - b) for a, b in zip(c1, c2))
    patron, franjas = "liso", 0
    if contraste > 110 and frac > 0.16:
        fila = _tramos([etiqueta(c) for x in range(58, 162) if (c := color(x, 136))])
        columna = _tramos([etiqueta(c) for y in range(70, 196) if (c := color(110, y))])
        diagonal = _tramos([etiqueta(c) for t in range(0, 100) if (c := color(66 + int(t * 0.84), 70 + int(t * 1.2)))])
        if len(fila) >= 4 and len(columna) >= 4:
            patron = "cuadros"
        elif len(fila) >= 4:
            patron, franjas = "rayas", max(3, (len(fila) + 1) // 2)
        elif len(columna) >= 4:
            patron, franjas = "aros", max(3, (len(columna) + 1) // 2)
        elif len(fila) == 2 and 0.3 < frac < 0.7:
            patron = "mitades"
        elif len(diagonal) == 3 and diagonal[1] == 1:
            patron = "banda"
    # ribete: el color del cuello (arriba al centro) si se distingue de la camiseta
    cuello = [c for y in range(10, 34) for x in range(96, 124) if (c := color(x, y))]
    ribete = None
    if cuello:
        lejano = max(cuello, key=lambda c: sum(abs(a - b) for a, b in zip(c, c1)))
        if sum(abs(a - b) for a, b in zip(lejano, c1)) > 120:
            ribete = rgb_hex(lejano)
    return {"patron": patron, "franjas": franjas, "camiseta": rgb_hex(c1), "rayas": rgb_hex(c2),
            "ribete": ribete or (rgb_hex(c2) if contraste > 110 else (BLANCO if luz(rgb_hex(c1)) < 150 else NEGRO))}


def kit_final(nombre_pais: str, analisis: Dict, rnd) -> Dict:
    """Une la lectura del jersey con la tabla de uniformes reales; si el país no está, short y medias por regla."""
    k = {**analisis}
    fijo = KITS.get(nombre_pais, {})
    k.update({c: v for c, v in fijo.items()})
    if fijo.get("camiseta") and "patron" not in fijo and k.get("patron") in ("rayas", "aros", "cuadros", "mitades", "banda"):
        # la tabla dice el color real; el patrón de la imagen se respeta solo si sus colores coinciden
        if distancia(analisis["camiseta"], fijo["camiseta"]) > 140:
            k["patron"] = "liso"
    cam = k["camiseta"]
    if "short" not in fijo:
        alterno = k.get("rayas") if k.get("patron") != "liso" else k.get("ribete")
        if alterno and distancia(alterno, cam) > 150:
            k["short"] = alterno
        else:
            k["short"] = BLANCO if luz(cam) < 140 else NEGRO
    if "medias" not in fijo:
        k["medias"] = cam if k.get("patron") == "liso" else k["short"]
    k.setdefault("ribete", BLANCO if luz(cam) < 150 else NEGRO)
    if distancia(k["ribete"], cam) < 90:
        k["ribete"] = BLANCO if luz(cam) < 150 else NEGRO
    k.setdefault("cuello", rnd.choice(["redondo", "v", "redondo"]))
    k["franjas"] = k.get("franjas") or 5
    return k


def kit_arquero(k: Dict, color: str) -> Dict:
    return {**k, "patron": "liso", "camiseta": color, "rayas": color, "short": oscurecer(color, 0.55), "medias": color,
            "ribete": BLANCO if luz(color) < 150 else NEGRO}


# --- dibujo ------------------------------------------------------------------------------------------------------
def defs_comunes() -> str:
    """Textura de tela y degradado de volumen, compartidos por todas las figuras del SVG."""
    return ('<defs>'
            '<pattern id="tela" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
            '<rect width="2.2" height="5" fill="#ffffff" opacity=".09"/></pattern>'
            '<pattern id="malla" width="8" height="8" patternUnits="userSpaceOnUse">'
            '<path d="M0 4L4 0L8 4L4 8Z" fill="none" stroke="#000" stroke-width=".6" opacity=".07"/></pattern>'
            '<linearGradient id="volumen" x1="0" y1="0" x2="1" y2="0.25">'
            '<stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset=".42" stop-color="#fff" stop-opacity="0"/>'
            '<stop offset=".7" stop-color="#000" stop-opacity=".06"/><stop offset="1" stop-color="#000" stop-opacity=".3"/></linearGradient>'
            '<radialGradient id="pliegue" cx=".5" cy="1" r=".7"><stop offset="0" stop-color="#000" stop-opacity=".18"/>'
            '<stop offset="1" stop-color="#000" stop-opacity="0"/></radialGradient>'
            '</defs>')


def torso_path(hombro: float, cintura: float, ruedo: float, agachado: bool = False) -> str:
    """Silueta de la camiseta: hombros redondeados, se ajusta a la cintura y cae con una curva suave al ruedo."""
    S, W, R = hombro, cintura, ruedo
    if agachado:   # inclinado hacia adelante: más corto y ancho abajo
        W = W * 1.08
    return (f"M-30 -3Q-52 -1 {_f(-(S - 6))} 7Q{_f(-S)} 13 {_f(-S)} 32L{_f(-(S - 5))} 64"
            f"C{_f(-(S - 3))} 102 {_f(-W)} 122 {_f(-(W + 2))} {_f(R)}Q0 {_f(R + 9)} {_f(W + 2)} {_f(R)}"
            f"C{_f(W)} 122 {_f(S - 3)} 102 {_f(S - 5)} 64L{_f(S)} 32Q{_f(S)} 13 {_f(S - 6)} 7Q52 -1 30 -3Q0 9 -30 -3Z")


def _f(v):
    return f"{v:.1f}"


def _patron(k: Dict, S: float, R: float) -> str:
    """Diseño de la camiseta dentro del torso (se recorta con el clipPath)."""
    p, col, n = k.get("patron"), k.get("rayas"), k.get("franjas") or 5
    if p == "rayas":
        ancho = 2 * S / (2 * n - 1)
        return "".join(f'<rect x="{_f(-S + ancho * (2 * i + 1))}" y="-20" width="{_f(ancho)}" height="{_f(R + 40)}" fill="{col}"/>' for i in range(n - 1))
    if p == "aros":
        alto = (R + 20) / (2 * n - 1)
        return "".join(f'<rect x="{_f(-S - 10)}" y="{_f(-10 + alto * (2 * i + 1))}" width="{_f(2 * S + 20)}" height="{_f(alto)}" fill="{col}"/>' for i in range(n - 1))
    if p == "mitades":
        return f'<rect x="0" y="-20" width="{_f(S + 10)}" height="{_f(R + 40)}" fill="{col}"/>'
    if p == "banda":
        return f'<path d="M{_f(-S + 4)} -6L{_f(-S + 40)} -6L{_f(S + 6)} {_f(R - 36)}L{_f(S + 6)} {_f(R + 4)}Z" fill="{col}"/>'
    if p == "cuadros":
        lado = 2 * S / 7
        return "".join(f'<rect x="{_f(-S + c * lado)}" y="{_f(-8 + f * lado)}" width="{_f(lado)}" height="{_f(lado)}" fill="{col}"/>'
                       for f in range(int((R + 20) / lado) + 1) for c in range(8) if (f + c) % 2)
    return ""


def camiseta(k: Dict, ident: str, S: float, W: float, R: float, numero: str, retro: bool, agachado: bool = False) -> str:
    d = torso_path(S, W, R, agachado)
    cam = k["camiseta"]
    partes = [f'<clipPath id="ct{ident}"><path d="{d}"/></clipPath>',
              f'<path d="{d}" fill="{cam}" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>',
              f'<g clip-path="url(#ct{ident})">{_patron(k, S, R)}'
              f'<rect x="{_f(-S)}" y="-10" width="{_f(2 * S)}" height="{_f(R + 20)}" fill="url(#malla)"/>'
              f'<rect x="{_f(-S)}" y="-10" width="{_f(2 * S)}" height="{_f(R + 20)}" fill="url(#tela)"/>'
              f'<rect x="{_f(-S)}" y="-10" width="{_f(2 * S)}" height="{_f(R + 20)}" fill="url(#volumen)"/>'
              # pliegues suaves de la tela en la cintura
              f'<path d="M{_f(-W + 6)} {_f(R - 30)}q14 10 26 4M{_f(W - 8)} {_f(R - 26)}q-12 9 -24 3" fill="none" stroke="#000" stroke-width="2.4" opacity=".14"/>'
              f'</g>',
              f'<path d="{d}" fill="none" stroke="{C}" stroke-width="{T}" stroke-linejoin="round"/>']
    rib = k["ribete"]
    if retro:   # cuello polo con cordón, como las camisetas de antes
        partes.append(f'<path d="M-30 -3L-12 20L0 8L12 20L30 -3" fill="{rib}" stroke="{C}" stroke-width="2.6" stroke-linejoin="round"/>'
                      f'<path d="M-3 14V36M3 14V36" stroke="{rib}" stroke-width="2.6"/>')
    elif k.get("cuello") == "v":
        partes.append(f'<path d="M-30 -3L0 26L30 -3" fill="none" stroke="{rib}" stroke-width="6.5" stroke-linejoin="round"/>'
                      f'<path d="M-24 -3L0 19L24 -3" fill="none" stroke="{C}" stroke-width="1.6" opacity=".55"/>')
    else:
        partes.append(f'<path d="M-30 -3Q0 16 30 -3" fill="none" stroke="{rib}" stroke-width="7" stroke-linecap="round"/>')
    # dorsal al frente, claro: el ribete si contrasta; si no, blanco o casi negro (con contorno)
    num_col = rib if abs(luz(rib) - luz(cam)) >= 90 and k.get("patron") == "liso" else ("#ffffff" if luz(cam) < 150 else "#14213d")
    contorno = "#ffffff" if luz(num_col) < 90 else C
    partes.append(f'<text x="0" y="{_f(R * 0.62 + 4)}" text-anchor="middle" font-family="Arial Black, Arial, Helvetica, sans-serif" '
                  f'font-weight="900" font-size="{_f(min(60, R * 0.4))}" fill="{num_col}" stroke="{contorno}" stroke-width="3.2" '
                  f'paint-order="stroke" letter-spacing="-2">{numero}</text>')
    return "".join(partes)


def manga(k: Dict, hombro: Tuple[float, float], codo: Tuple[float, float], w: float, larga: bool = False, mano=None) -> str:
    """Manga sobre el brazo: corta (hasta ~45% del brazo, con puño del ribete) o larga hasta la muñeca (arquero)."""
    cam = k["camiseta"]
    fin = codo if not larga else mano
    if not larga:
        t = 0.48
        fin = (hombro[0] + (codo[0] - hombro[0]) * t, hombro[1] + (codo[1] - hombro[1]) * t)
    tramos = [(hombro, fin, 21 * w, 18.5 * w)]
    if larga:
        tramos = [(hombro, codo, 21 * w, 17 * w), (codo, mano, 16.5 * w, 13 * w)]
    s = CU.pieza(tramos, cam, oscurecer(cam, 0.72), bulto=0.06)
    # puño del ribete al final de la manga
    a, b = tramos[-1][0], tramos[-1][1]
    s += CU.banda(a, b, tramos[-1][3], k["ribete"], 5.5)
    return s


def short(k: Dict, caderas: Tuple, rodillas: Tuple, cintura: float, R: float, w: float, agachado: bool) -> str:
    """Short: tiro central + perneras sobre los muslos, con franja lateral del ribete y pliegue central."""
    col = k["short"]
    sombra = oscurecer(col, 0.72)
    piernas = []
    for cadera, rodilla in zip(caderas, rodillas):
        t = 0.42 if agachado else 0.5
        fin = (cadera[0] + (rodilla[0] - cadera[0]) * t, cadera[1] + (rodilla[1] - cadera[1]) * t)
        piernas.append((cadera, fin, 27 * w, 25 * w))
    W = cintura * (1.08 if agachado else 1.0)
    tiro = (f"M{_f(-W)} {_f(R - 14)}L{_f(W)} {_f(R - 14)}L{_f(W + 2)} {_f(caderas[1][1] + 8)}"
            f"Q0 {_f(caderas[1][1] + 26)} {_f(-W - 2)} {_f(caderas[0][1] + 8)}Z")
    s = (f'<path d="{tiro}" fill="{C}" stroke="{C}" stroke-width="{T * 2}" stroke-linejoin="round"/>'
         + "".join(f'<path d="{CU.tubo(a, b, ra, rb, 0.04)}" fill="{C}" stroke="{C}" stroke-width="{T * 2}"/>' for a, b, ra, rb in piernas)
         + f'<path d="{tiro}" fill="{col}"/>'
         + "".join(f'<path d="{CU.tubo(a, b, ra, rb, 0.04)}" fill="{col}"/>' for a, b, ra, rb in piernas)
         + "".join(f'<path d="{CU.sombra_tubo(a, b, ra, rb)}" fill="{sombra}" opacity=".35"/>' for a, b, ra, rb in piernas))
    # franjas laterales y costura central
    for (a, b, ra, rb), lado in zip(piernas, (-1, 1)):
        x0 = a[0] + lado * ra * 0.82
        x1 = b[0] + lado * rb * 0.82
        s += f'<path d="M{_f(x0)} {_f(a[1] - 6)}L{_f(x1)} {_f(b[1] - 2)}" stroke="{k["ribete"]}" stroke-width="5" opacity=".9"/>'
    s += f'<path d="M0 {_f(R - 6)}V{_f(caderas[0][1] + 18)}" stroke="{sombra}" stroke-width="2.4" opacity=".7"/>'
    return s


def medias(k: Dict, rodilla, tobillo, w: float, agachado: bool) -> str:
    """Media sobre la pierna (desde debajo de la rodilla) con la banda del ribete arriba."""
    t = 0.2 if agachado else 0.3
    ini = (rodilla[0] + (tobillo[0] - rodilla[0]) * t, rodilla[1] + (tobillo[1] - rodilla[1]) * t)
    col = k["medias"]
    s = CU.pieza([(ini, tobillo, 16.5 * w, 11.5 * w)], col, oscurecer(col, 0.72), bulto=0.22)
    dx, dy = tobillo[0] - ini[0], tobillo[1] - ini[1]
    largo = math.hypot(dx, dy) or 1
    borde = (ini[0] + dx / largo * 9, ini[1] + dy / largo * 9)
    banda = k["ribete"] if distancia(k["ribete"], col) > 90 else (BLANCO if luz(col) < 150 else NEGRO)
    s += CU.banda(ini, borde, 16.5 * w * 1.05, banda, 6)
    return s
