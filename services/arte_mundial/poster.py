"""
Póster oficial del Mundial (SVG 600x900), armado como lo haría un diseñador: en capas con reglas, no al azar.
  1. FONDO       temático (rayos, cielo, franjas, ondas, montañas, ciudad, mar, desierto, selva, geométrico...)
  2. ICONO       silueta de un ícono del país o de su región (config/arte_mundial.py)
  3. FUTBOL      el elemento futbolero protagonista (balón, chilena, remate, copa, botín, red)
  4. GRILLA      composición tipográfica: dónde va la imagen y dónde el año, el país y el título, siempre sobre un
                 panel sólido para garantizar contraste (paleta.texto_sobre, mínimo 4.5:1)
Todo sale de la paleta de la bandera del anfitrión (paleta.de_bandera). Una RECETA {fondo, icono, futbol, grilla,
semilla} siempre da el mismo SVG (determinístico): en Mongo se guarda la receta, no la imagen.
Cada pieza se dibuja en una caja de 200x200 con el suelo en y=200 y se ubica con transform.
"""
import base64
import math
import os
import random
from functools import lru_cache
from typing import Dict, List, Optional

from services.arte_mundial import paleta as P

ANCHO, ALTO = 600, 900
_DIR_FUENTES = os.path.join(os.path.dirname(__file__), "fuentes")


@lru_cache(maxsize=None)
def _fuente(nombre: str) -> str:
    with open(os.path.join(_DIR_FUENTES, nombre), "rb") as f:
        return base64.b64encode(f.read()).decode()


def estilos_fuentes() -> str:
    return ("<style>"
            f"@font-face{{font-family:'Anton FV';src:url(data:font/woff;base64,{_fuente('Anton-Regular.woff')}) format('woff');}}"
            f"@font-face{{font-family:'Bebas FV';src:url(data:font/woff;base64,{_fuente('BebasNeue-Regular.woff')}) format('woff');}}"
            "</style>")


ANCHO_LETRA = {"Anton FV": 0.50, "Bebas FV": 0.40}


def texto(x, y, s, tam, color, fuente="Anton FV", ancla="middle", max_ancho=None, espaciado=0.0, trazo=None, extra="", tam_min=18):
    """Texto ajustado al ancho: achica la letra y, si no alcanza, lo parte en 2 renglones (nombres largos de país)."""
    s = s.upper()
    def ancho(t, z):
        return len(t) * z * (ANCHO_LETRA[fuente] + espaciado)
    lineas = [s]
    if max_ancho and ancho(s, tam) > max_ancho:
        tam_ajust = max_ancho / max(1, len(s) * (ANCHO_LETRA[fuente] + espaciado))
        if tam_ajust < tam * 0.62 and " " in s:   # mejor dos renglones que una letra diminuta
            palabras = s.split(" ")
            corte = min(range(1, len(palabras)), key=lambda i: abs(len(" ".join(palabras[:i])) - len(" ".join(palabras[i:]))))
            lineas = [" ".join(palabras[:corte]), " ".join(palabras[corte:])]
            tam = min(tam * 0.8, max_ancho / max(1, max(len(l) for l in lineas) * (ANCHO_LETRA[fuente] + espaciado)))
        else:
            tam = max(tam_min, tam_ajust)
    ls = f' letter-spacing="{espaciado * tam:.1f}"' if espaciado else ""
    st = f' stroke="{trazo[0]}" stroke-width="{trazo[1]}" paint-order="stroke" stroke-linejoin="round"' if trazo else ""
    salida, alto_linea = [], tam * 1.0
    y0 = y - (len(lineas) - 1) * alto_linea
    for i, l in enumerate(lineas):
        salida.append(f'<text x="{x:.1f}" y="{y0 + i * alto_linea:.1f}" font-family="{fuente}, Impact, sans-serif" font-size="{tam:.1f}" '
                      f'fill="{color}" text-anchor="{ancla}"{ls}{st} {extra}>{_escapar(l)}</text>')
    return "".join(salida)


def _escapar(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def caja(svg: str, x, y, ancho, alto=None, voltear=False) -> str:
    """Ubica una pieza dibujada en 200x200 dentro de la caja (x, y, ancho) apoyada en su base."""
    esc = ancho / 200
    alto = alto if alto is not None else ancho
    flip = f" translate(200 0) scale(-1 1)" if voltear else ""
    return f'<g transform="translate({x:.1f} {y + alto - 200 * esc:.1f}) scale({esc:.3f}){flip}">{svg}</g>'


# =================================================================================================================
# 1. FONDOS (pantalla completa 600x900)
# =================================================================================================================
def f_rayos(p, r):
    cx, cy = 300, r.choice([330, 380, 430])
    colores = [p["dominante"], p["dominante_oscuro"]]
    n = r.choice([18, 24, 32])
    rayos = []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        x0, y0 = cx + 1400 * math.cos(a0), cy + 1400 * math.sin(a0)
        x1, y1 = cx + 1400 * math.cos(a1), cy + 1400 * math.sin(a1)
        rayos.append(f'<path d="M{cx} {cy}L{x0:.0f} {y0:.0f}L{x1:.0f} {y1:.0f}Z" fill="{colores[i % 2]}"/>')
    return (f'<rect width="{ANCHO}" height="{ALTO}" fill="{p["dominante"]}"/>' + "".join(rayos)
            + f'<circle cx="{cx}" cy="{cy}" r="150" fill="{p["acento"]}" opacity=".18"/>')


def f_cielo(p, r):
    sol_x, sol_y = r.choice([(430, 230), (300, 300), (170, 250)])
    return (f'<defs><linearGradient id="fcielo" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p["dominante_oscuro"]}"/>'
            f'<stop offset=".55" stop-color="{p["dominante"]}"/><stop offset="1" stop-color="{p["dominante_claro"]}"/></linearGradient>'
            f'<radialGradient id="fhalo"><stop offset="0" stop-color="{p["acento"]}" stop-opacity=".55"/><stop offset="1" stop-color="{p["acento"]}" stop-opacity="0"/></radialGradient></defs>'
            f'<rect width="{ANCHO}" height="{ALTO}" fill="url(#fcielo)"/>'
            f'<circle cx="{sol_x}" cy="{sol_y}" r="260" fill="url(#fhalo)"/><circle cx="{sol_x}" cy="{sol_y}" r="95" fill="{p["acento"]}"/>')


def f_franjas(p, r):
    cols = (p["bandera"] + [p["acento"], p["dominante_oscuro"]])[:4]
    ang = r.choice([-28, -18, 18, 28])
    ancho = r.choice([120, 160, 200])
    bandas = "".join(f'<rect x="{-600 + i * ancho}" y="-400" width="{ancho * 0.72:.0f}" height="1800" fill="{cols[i % len(cols)]}"/>'
                     for i in range(16))
    return (f'<rect width="{ANCHO}" height="{ALTO}" fill="{p["dominante_oscuro"]}"/>'
            f'<g transform="rotate({ang} 300 450)" opacity=".92">{bandas}</g>')


def f_ondas(p, r):
    fondo = p["claro"]
    capas = [p["dominante_claro"], p["acento"], p["dominante"], p["dominante_oscuro"]]
    ondas = []
    for i, c in enumerate(capas):
        y = 520 + i * 90
        amp, per = r.choice([30, 45, 60]), r.choice([300, 400, 600])
        pts = " ".join(f"{x},{y + amp * math.sin(2 * math.pi * x / per + i):.0f}" for x in range(0, 640, 20))
        ondas.append(f'<polygon points="0,{ALTO} {pts} {ANCHO},{ALTO}" fill="{c}"/>')
    return f'<rect width="{ANCHO}" height="{ALTO}" fill="{fondo}"/>' + "".join(ondas)


def f_montanas(p, r):
    capas = [p["dominante_claro"], p["dominante"], p["dominante_oscuro"]]
    sky = f_cielo(p, r)
    sierras = []
    for i, c in enumerate(capas):
        base = 560 + i * 110
        pts, x = [f"0,{ALTO}"], 0
        while x <= ANCHO + 60:
            pts.append(f"{x},{base - r.randint(60, 200) + i * 30}")
            x += r.randint(80, 160)
        pts.append(f"{ANCHO},{ALTO}")
        sierras.append(f'<polygon points="{" ".join(pts)}" fill="{c}"/>')
    return sky + "".join(sierras)


def f_ciudad(p, r):
    sky = (f'<defs><linearGradient id="fciu" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p["dominante_oscuro"]}"/>'
           f'<stop offset="1" stop-color="{p["dominante"]}"/></linearGradient></defs><rect width="{ANCHO}" height="{ALTO}" fill="url(#fciu)"/>')
    edificios, x = [], -10
    while x < ANCHO:
        w, h = r.randint(40, 90), r.randint(140, 420)
        edificios.append(f'<rect x="{x}" y="{ALTO - h}" width="{w}" height="{h}" fill="{p["oscuro"]}"/>')
        for wy in range(ALTO - h + 14, ALTO - 10, 22):
            for wx in range(x + 8, x + w - 8, 14):
                if r.random() < 0.45:
                    edificios.append(f'<rect x="{wx}" y="{wy}" width="6" height="9" fill="{p["acento"]}" opacity=".85"/>')
        x += w + r.randint(2, 10)
    estrellas = "".join(f'<circle cx="{r.randint(0, 600)}" cy="{r.randint(0, 420)}" r="{r.choice([1, 1.5, 2])}" fill="#fff" opacity=".7"/>' for _ in range(40))
    return sky + estrellas + "".join(edificios)


def f_mar(p, r):
    sky = (f'<defs><linearGradient id="fmar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{p["dominante_claro"]}"/>'
           f'<stop offset="1" stop-color="{P.aclarar(p["acento"], .5)}"/></linearGradient></defs><rect width="{ANCHO}" height="{ALTO}" fill="url(#fmar)"/>')
    sol = f'<circle cx="300" cy="560" r="150" fill="{p["acento"]}"/>'
    mar = f'<rect y="560" width="{ANCHO}" height="340" fill="{p["dominante"]}"/>'
    lineas = "".join(f'<path d="M{r.randint(-40, 400)} {y}h{r.randint(80, 260)}" stroke="{p["dominante_claro"]}" stroke-width="5" stroke-linecap="round" opacity=".7"/>'
                     for y in range(590, 900, 26))
    return sky + sol + mar + lineas


def f_desierto(p, r):
    sky = (f'<defs><linearGradient id="fdes" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{P.mezclar(p["acento"], "#f6c26b", .5)}"/>'
           f'<stop offset="1" stop-color="{P.mezclar(p["dominante_claro"], "#fde6b5", .6)}"/></linearGradient></defs><rect width="{ANCHO}" height="{ALTO}" fill="url(#fdes)"/>')
    sol = f'<circle cx="{r.choice([160, 420])}" cy="260" r="110" fill="{P.aclarar(p["acento"], .25)}"/>'
    dunas = []
    for i, c in enumerate([P.mezclar(p["dominante_claro"], "#e9b872", .6), P.mezclar(p["dominante"], "#c98a3a", .55), p["dominante_oscuro"]]):
        y = 600 + i * 100
        dunas.append(f'<path d="M0 {ALTO}V{y}Q150 {y - 90} 300 {y - 20}T600 {y - 40}V{ALTO}Z" fill="{c}"/>')
    return sky + sol + "".join(dunas)


def f_selva(p, r):
    base = f'<rect width="{ANCHO}" height="{ALTO}" fill="{p["dominante_oscuro"]}"/>'
    hojas = []
    for _ in range(26):
        x, y = r.choice([r.randint(-60, 120), r.randint(480, 660)]), r.randint(-60, 960)
        ang, l = r.randint(0, 360), r.randint(120, 240)
        c = r.choice([p["dominante"], P.mezclar(p["dominante"], "#2f9e44", .5), P.oscurecer(p["dominante"], .8)])
        hojas.append(f'<path transform="translate({x} {y}) rotate({ang})" d="M0 0C{l * .3} -{l * .35} {l * .8} -{l * .3} {l} 0C{l * .8} {l * .3} {l * .3} {l * .35} 0 0Z" fill="{c}"/>'
                     f'<path transform="translate({x} {y}) rotate({ang})" d="M0 0L{l * .95} 0" stroke="{p["dominante_oscuro"]}" stroke-width="3"/>')
    luz = f'<circle cx="300" cy="420" r="300" fill="{p["acento"]}" opacity=".16"/>'
    return base + luz + "".join(hojas)


def f_geometrico(p, r):
    cols = [p["dominante"], p["acento"], p["dominante_oscuro"], p["claro"], p["dominante_claro"]]
    celdas, t = [], 150
    for fy in range(0, ALTO, t):
        for fx in range(0, ANCHO, t):
            c1, c2 = r.sample(cols, 2)
            forma = r.choice(["cuarto", "triangulo", "circulo", "media"])
            celdas.append(f'<rect x="{fx}" y="{fy}" width="{t}" height="{t}" fill="{c1}"/>')
            if forma == "cuarto":
                ox, oy = fx + r.choice([0, t]), fy + r.choice([0, t])
                celdas.append(f'<path d="M{ox} {oy}m{-t} 0a{t} {t} 0 0 0 {2 * t} 0a{t} {t} 0 0 0 {-2 * t} 0" fill="{c2}" clip-path="url(#c{fx}_{fy})"/>')
                celdas.append(f'<clipPath id="c{fx}_{fy}"><rect x="{fx}" y="{fy}" width="{t}" height="{t}"/></clipPath>')
            elif forma == "triangulo":
                celdas.append(f'<path d="M{fx} {fy + t}L{fx + t} {fy + t}L{fx + t} {fy}Z" fill="{c2}"/>')
            elif forma == "circulo":
                celdas.append(f'<circle cx="{fx + t / 2}" cy="{fy + t / 2}" r="{t * .36}" fill="{c2}"/>')
            else:
                celdas.append(f'<path d="M{fx} {fy + t / 2}A{t / 2} {t / 2} 0 0 1 {fx + t} {fy + t / 2}Z" fill="{c2}"/>')
    return "".join(celdas)


def f_concentrico(p, r):
    cx, cy = r.choice([(300, 420), (300, 900), (0, 450), (600, 300)])
    cols = [p["dominante_oscuro"], p["dominante"], p["acento"], p["claro"], p["dominante_claro"]]
    anillos = "".join(f'<circle cx="{cx}" cy="{cy}" r="{1100 - i * 70}" fill="{cols[i % len(cols)]}"/>' for i in range(15))
    return f'<rect width="{ANCHO}" height="{ALTO}" fill="{p["dominante_oscuro"]}"/>' + anillos


def f_retro(p, r):
    puntos = (f'<defs><pattern id="ptos" width="14" height="14" patternUnits="userSpaceOnUse">'
              f'<circle cx="7" cy="7" r="2.2" fill="{p["dominante"]}" opacity=".22"/></pattern></defs>')
    return (puntos + f'<rect width="{ANCHO}" height="{ALTO}" fill="{p["crema"]}"/><rect width="{ANCHO}" height="{ALTO}" fill="url(#ptos)"/>'
            f'<rect x="18" y="18" width="{ANCHO - 36}" height="{ALTO - 36}" fill="none" stroke="{p["dominante"]}" stroke-width="6"/>'
            f'<rect x="30" y="30" width="{ANCHO - 60}" height="{ALTO - 60}" fill="none" stroke="{p["acento"]}" stroke-width="2"/>')


FONDOS = {"rayos": f_rayos, "cielo": f_cielo, "franjas": f_franjas, "ondas": f_ondas, "montanas": f_montanas, "ciudad": f_ciudad,
          "mar": f_mar, "desierto": f_desierto, "selva": f_selva, "geometrico": f_geometrico, "concentrico": f_concentrico,
          "retro": f_retro}


# =================================================================================================================
# 2. ICONOS (silueta en caja 200x200, suelo en y=200; c = color de la silueta, d = color de detalle)
# =================================================================================================================
def i_castillo(c, d):
    alm = lambda x, y, w: "".join(f'<rect x="{x + i * w / 5}" y="{y - 12}" width="{w / 10:.1f}" height="12" fill="{c}"/>' for i in range(0, 5, 1)) + \
        "".join(f'<rect x="{x + i * w / 5 + w / 10:.1f}" y="{y - 12}" width="{w / 10:.1f}" height="12" fill="{c}"/>' for i in range(0, 5, 2))
    return (f'<rect x="12" y="80" width="44" height="120" fill="{c}"/><rect x="144" y="80" width="44" height="120" fill="{c}"/>'
            f'<rect x="56" y="110" width="88" height="90" fill="{c}"/><rect x="74" y="44" width="52" height="156" fill="{c}"/>'
            + alm(12, 80, 44) + alm(144, 80, 44) + alm(74, 44, 52)
            + f'<path d="M86 200V168A14 14 0 0 1 114 168V200Z" fill="{d}"/><rect x="26" y="110" width="8" height="18" rx="4" fill="{d}"/>'
              f'<rect x="166" y="110" width="8" height="18" rx="4" fill="{d}"/><rect x="96" y="76" width="8" height="18" rx="4" fill="{d}"/>')


def i_torre_reloj(c, d):
    return (f'<path d="M80 200V58H120V200Z M76 58L100 6L124 58Z" fill="{c}"/><rect x="74" y="54" width="52" height="8" fill="{c}"/>'
            f'<circle cx="100" cy="82" r="13" fill="{d}"/><path d="M100 82V74M100 82L106 86" stroke="{c}" stroke-width="3"/>'
            + "".join(f'<rect x="88" y="{y}" width="6" height="14" fill="{d}"/><rect x="106" y="{y}" width="6" height="14" fill="{d}"/>' for y in (112, 140, 168)))


def i_catedral(c, d):
    return (f'<path d="M34 200V60L50 20L66 60V200Z M134 200V60L150 20L166 60V200Z M66 200V100L100 72L134 100V200Z" fill="{c}"/>'
            f'<circle cx="100" cy="124" r="16" fill="{d}"/><path d="M90 200V170A10 10 0 0 1 110 170V200Z" fill="{d}"/>'
            f'<path d="M44 90h12v24h-12zM144 90h12v24h-12z" fill="{d}"/>')


def i_templo_columnas(c, d):
    cols = "".join(f'<rect x="{22 + i * 30}" y="80" width="14" height="104" fill="{c}"/>' for i in range(6))
    return (f'<path d="M8 66L100 24L192 66Z" fill="{c}"/><rect x="8" y="66" width="184" height="14" fill="{c}"/>{cols}'
            f'<rect x="4" y="184" width="192" height="8" fill="{c}"/><rect x="0" y="192" width="200" height="8" fill="{c}"/>'
            f'<circle cx="100" cy="52" r="7" fill="{d}"/>')


def i_arco(c, d):
    return (f'<path fill-rule="evenodd" d="M24 200V40H176V200H136V120A36 36 0 0 0 64 120V200Z" fill="{c}"/>'
            f'<rect x="18" y="30" width="164" height="14" fill="{c}"/><rect x="40" y="56" width="120" height="6" fill="{d}"/>'
            f'<rect x="34" y="140" width="18" height="40" fill="{d}" opacity=".7"/><rect x="148" y="140" width="18" height="40" fill="{d}" opacity=".7"/>')


def i_molino(c, d):
    aspa = lambda ang: (f'<g transform="rotate({ang} 100 70)"><rect x="96" y="-14" width="8" height="84" fill="{c}"/>'
                        f'<rect x="104" y="-10" width="22" height="70" fill="{d}" stroke="{c}" stroke-width="3"/></g>')
    return (f'<path d="M72 200L84 76H116L128 200Z" fill="{c}"/><path d="M78 80L100 50L122 80Z" fill="{c}"/>'
            + "".join(aspa(a) for a in (20, 110, 200, 290)) + f'<circle cx="100" cy="70" r="8" fill="{c}"/>'
            f'<path d="M92 200V178A8 8 0 0 1 108 178V200Z" fill="{d}"/>')


def i_puente(c, d):
    return (f'<rect x="38" y="30" width="16" height="170" fill="{c}"/><rect x="146" y="30" width="16" height="170" fill="{c}"/>'
            f'<rect x="0" y="140" width="200" height="10" fill="{c}"/>'
            f'<path d="M-10 60Q46 150 46 36Q100 150 154 36Q154 150 210 60" fill="none" stroke="{c}" stroke-width="4"/>'
            + "".join(f'<path d="M{x} {140}V{abs(100 - x) * 0.9 + 46:.0f}" stroke="{c}" stroke-width="2"/>' for x in range(60, 145, 12))
            + f'<rect x="38" y="60" width="16" height="6" fill="{d}"/><rect x="146" y="60" width="16" height="6" fill="{d}"/>')


def i_faro(c, d):
    return (f'<path d="M30 70L100 54L170 70Z" fill="{d}" opacity=".45"/>'
            f'<path d="M76 200L86 64H114L124 200Z" fill="{c}"/><rect x="84" y="40" width="32" height="24" fill="{d}"/>'
            f'<path d="M80 40L100 20L120 40Z" fill="{c}"/><path d="M82 120H118L120 146H80ZM78 172H122L124 196H76Z" fill="{d}"/>')


def i_montana_nevada(c, d):
    return (f'<path d="M0 200L70 48L104 98L132 64L200 200Z" fill="{c}"/>'
            f'<path d="M70 48L54 82L66 76L76 92L86 74L94 86L104 98Z M132 64L120 88L130 84L140 96L146 88Z" fill="{d}"/>')


def i_volcan(c, d):
    humo = "".join(f'<circle cx="{100 + dx}" cy="{40 - i * 14}" r="{14 + i * 3}" fill="{d}" opacity="{.6 - i * .1:.2f}"/>' for i, dx in enumerate((-8, 6, -4, 10)))
    return humo + f'<path d="M0 200L72 70H128L200 200Z" fill="{c}"/><path d="M72 70L84 90L96 80L108 94L120 80L128 70Z" fill="{d}" opacity=".8"/>'


def i_cupula_cebolla(c, d):
    cebolla = lambda x, y, s: (f'<path transform="translate({x} {y}) scale({s})" d="M0 0C-26 -12 -30 -40 0 -62C30 -40 26 -12 0 0Z" fill="{d}" stroke="{c}" stroke-width="5"/>'
                               f'<path transform="translate({x} {y}) scale({s})" d="M0 -62V-80M-7 -74H7" stroke="{c}" stroke-width="4"/>')
    return (f'<rect x="76" y="90" width="48" height="110" fill="{c}"/><rect x="34" y="128" width="32" height="72" fill="{c}"/>'
            f'<rect x="134" y="128" width="32" height="72" fill="{c}"/><rect x="60" y="150" width="80" height="50" fill="{c}"/>'
            + cebolla(100, 92, 1.0) + cebolla(50, 130, .62) + cebolla(150, 130, .62))


def i_mezquita(c, d):
    minarete = lambda x: (f'<rect x="{x}" y="40" width="14" height="160" fill="{c}"/><path d="M{x - 2} 40L{x + 7} 10L{x + 16} 40Z" fill="{c}"/>'
                          f'<rect x="{x - 3}" y="80" width="20" height="6" fill="{c}"/>')
    return (minarete(16) + minarete(170) + f'<rect x="44" y="120" width="112" height="80" fill="{c}"/>'
            f'<path d="M50 120A50 50 0 0 1 150 120Z" fill="{c}"/><path d="M100 70V52" stroke="{c}" stroke-width="4"/>'
            f'<path d="M104 46A8 8 0 1 1 104 30A6 6 0 1 0 104 46Z" fill="{c}"/>'
            f'<path d="M88 200V168A12 12 0 0 1 112 168V200Z" fill="{d}"/><path d="M60 150h14v20h-14zM126 150h14v20h-14z" fill="{d}"/>')


def i_luna_estrella(c, d):
    estrella = " ".join(f"{140 + 26 * math.cos(math.radians(-90 + i * 36)) * (1 if i % 2 == 0 else .42):.1f},"
                        f"{80 + 26 * math.sin(math.radians(-90 + i * 36)) * (1 if i % 2 == 0 else .42):.1f}" for i in range(10))
    return (f'<path fill-rule="evenodd" d="M96 30A70 70 0 1 0 96 170A56 56 0 1 1 96 30Z" fill="{c}"/>'
            f'<polygon points="{estrella}" fill="{d}"/>')


def i_palmera(c, d):
    hoja = lambda ang, l: (f'<path transform="translate(108 50) rotate({ang})" d="M0 0C{l * .3} -{l * .25} {l * .7} -{l * .2} {l} {l * .2}'
                           f'C{l * .7} 0 {l * .3} 0 0 0Z" fill="{c}"/>')
    return (f'<path d="M96 200C92 150 96 100 108 50L118 52C108 100 106 150 112 200Z" fill="{c}"/>'
            + "".join(hoja(a, l) for a, l in ((-160, 80), (-120, 70), (-60, 74), (-20, 84), (20, 70), (160, 66)))
            + f'<circle cx="104" cy="58" r="7" fill="{d}"/><circle cx="114" cy="60" r="7" fill="{d}"/>')


def i_rascacielos(c, d):
    edif = [(20, 90, 30), (52, 40, 34), (90, 10, 30), (124, 60, 32), (158, 100, 30)]
    s = []
    for x, y, w in edif:
        s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{200 - y}" fill="{c}"/>')
        s += [f'<rect x="{x + 5 + k * 8}" y="{yy}" width="4" height="8" fill="{d}" opacity=".8"/>' for yy in range(y + 10, 196, 16) for k in range((w - 8) // 8)]
    s.append(f'<path d="M102 10V-14M98 10H106" stroke="{c}" stroke-width="3"/>')
    return "".join(s)


def i_piramide_egipcia(c, d):
    return (f'<path d="M10 200L80 80L150 200Z" fill="{c}"/><path d="M80 80L150 200H110Z" fill="{d}" opacity=".45"/>'
            f'<path d="M120 200L164 126L200 200Z" fill="{c}"/><path d="M164 126L200 200H178Z" fill="{d}" opacity=".45"/>')


def i_baobab(c, d):
    return (f'<path d="M80 200C84 160 82 110 70 80H130C118 110 116 160 120 200Z" fill="{c}"/>'
            f'<path d="M70 82L40 60M84 80L76 46M100 80V40M116 80L128 46M130 82L162 62" stroke="{c}" stroke-width="10" stroke-linecap="round"/>'
            + "".join(f'<ellipse cx="{x}" cy="{y}" rx="{rx}" ry="12" fill="{c}"/>' for x, y, rx in ((36, 56, 26), (74, 40, 22), (100, 34, 24), (130, 40, 22), (166, 58, 26)))
            + f'<circle cx="160" cy="24" r="18" fill="{d}"/>')


def i_montana_mesa(c, d):
    return (f'<path d="M0 200L30 90H170L200 200Z" fill="{c}"/><path d="M30 90H170L164 104H36Z" fill="{d}" opacity=".5"/>'
            f'<ellipse cx="70" cy="86" rx="40" ry="10" fill="{d}" opacity=".8"/><ellipse cx="128" cy="84" rx="34" ry="9" fill="{d}" opacity=".8"/>')


def i_sol(c, d):
    rayos = "".join(f'<path transform="rotate({i * 22.5} 100 100)" d="M96 {20 if i % 2 == 0 else 30}L100 4L104 {20 if i % 2 == 0 else 30}Z" fill="{c}"/>' for i in range(16))
    return (rayos + f'<circle cx="100" cy="100" r="58" fill="{c}"/><circle cx="100" cy="100" r="44" fill="{d}"/>'
            f'<circle cx="84" cy="94" r="5" fill="{c}"/><circle cx="116" cy="94" r="5" fill="{c}"/>'
            f'<path d="M84 116Q100 128 116 116" fill="none" stroke="{c}" stroke-width="5" stroke-linecap="round"/>')


def i_pagoda(c, d):
    pisos = []
    for i, (w, y) in enumerate(((150, 170), (124, 128), (98, 88), (72, 50))):
        x = 100 - w / 2
        pisos.append(f'<rect x="{x + 14}" y="{y}" width="{w - 28}" height="{40 if i == 0 else 38}" fill="{c}"/>')
        pisos.append(f'<path d="M{x - 8} {y + 2}Q{x + 10} {y - 4} {x + 20} {y - 14}H{x + w - 20}Q{x + w - 10} {y - 4} {x + w + 8} {y + 2}Z" fill="{c}"/>')
        pisos.append(f'<rect x="{96}" y="{y + 12}" width="8" height="12" fill="{d}"/>')
    return "".join(pisos) + f'<path d="M100 36V6" stroke="{c}" stroke-width="5"/><circle cx="100" cy="10" r="5" fill="{c}"/>'


def i_torii(c, d):
    return (f'<path d="M6 34Q100 22 194 34L190 50Q100 40 10 50Z" fill="{c}"/><rect x="26" y="72" width="148" height="12" fill="{c}"/>'
            f'<path d="M44 50H60L62 200H42Z M140 50H156L158 200H138Z" fill="{c}"/><rect x="92" y="50" width="16" height="24" fill="{c}"/>'
            f'<circle cx="160" cy="130" r="30" fill="{d}" opacity=".9"/>')


def i_cerezo(c, d):
    return (f'<path d="M94 200C96 160 92 130 80 110M98 150C110 130 126 118 146 112M90 130C76 120 60 116 44 118" stroke="{c}" stroke-width="12" fill="none" stroke-linecap="round"/>'
            + "".join(f'<circle cx="{x}" cy="{y}" r="{rr}" fill="{d}"/>' for x, y, rr in
                      ((80, 96, 28), (110, 80, 32), (146, 98, 28), (50, 108, 24), (128, 60, 20), (70, 70, 20), (160, 120, 16))))


def i_cupula_palacio(c, d):
    minarete = lambda x: f'<rect x="{x}" y="70" width="10" height="130" fill="{c}"/><circle cx="{x + 5}" cy="66" r="8" fill="{c}"/>'
    return (minarete(14) + minarete(176) + f'<rect x="40" y="120" width="120" height="80" fill="{c}"/>'
            f'<path d="M58 120C50 80 80 60 100 34C120 60 150 80 142 120Z" fill="{c}"/><path d="M100 34V16" stroke="{c}" stroke-width="4"/>'
            f'<path d="M86 200V156A14 14 0 0 1 114 156V200Z" fill="{d}"/><path d="M52 150h16v24h-16zM132 150h16v24h-16z" fill="{d}"/>')


def i_hoja_arce(c, d):
    pts = [(100, 6), (112, 40), (132, 30), (126, 70), (164, 52), (156, 78), (186, 86), (150, 112), (160, 128), (110, 120),
           (106, 166), (94, 166), (90, 120), (40, 128), (50, 112), (14, 86), (44, 78), (36, 52), (74, 70), (68, 30), (88, 40)]
    return f'<polygon points="{" ".join(f"{x},{y}" for x, y in pts)}" fill="{c}"/><rect x="96" y="160" width="8" height="40" fill="{c}"/>'


def i_piramide_escalonada(c, d):
    pisos = "".join(f'<rect x="{10 + i * 16}" y="{176 - i * 24}" width="{180 - i * 32}" height="24" fill="{c}"/>' for i in range(5))
    return (pisos + f'<rect x="76" y="28" width="48" height="34" fill="{c}"/><path d="M70 30H130L120 18H80Z" fill="{c}"/>'
            f'<path d="M88 200L92 62H108L112 200Z" fill="{d}"/>'
            + "".join(f'<path d="M90 {y}H110" stroke="{c}" stroke-width="2"/>' for y in range(70, 200, 8))
            + f'<rect x="92" y="40" width="16" height="22" fill="{d}"/>')


def i_cactus(c, d):
    return (f'<rect x="84" y="30" width="32" height="170" rx="16" fill="{c}"/>'
            f'<path d="M84 120H58V70" stroke="{c}" stroke-width="24" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M116 100H144V56" stroke="{c}" stroke-width="24" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M100 40V190M58 76V112M144 62V92" stroke="{d}" stroke-width="2" opacity=".6"/><circle cx="100" cy="26" r="9" fill="{d}"/>')


def i_moai(c, d):
    return (f'<path d="M60 200L64 120C52 116 50 90 58 80L62 30Q100 4 136 30L140 120L144 200Z" fill="{c}"/>'
            f'<path d="M70 70H96M104 70H130" stroke="{d}" stroke-width="8" stroke-linecap="round"/><path d="M100 72L94 110H108Z" fill="{d}"/>'
            f'<path d="M84 128H118" stroke="{d}" stroke-width="5" stroke-linecap="round"/>')


def i_torre_celosia(c, d):
    return (f'<path d="M20 200C60 160 80 100 90 30H110C120 100 140 160 180 200H140C126 176 112 168 100 168C88 168 74 176 60 200Z" fill="{c}"/>'
            f'<rect x="52" y="118" width="96" height="10" fill="{c}"/><rect x="74" y="72" width="52" height="8" fill="{c}"/>'
            f'<path d="M96 30V4" stroke="{c}" stroke-width="5"/>'
            + "".join(f'<path d="M{100 - w} {y}L{100 + w} {y + 18}M{100 + w} {y}L{100 - w} {y + 18}" stroke="{d}" stroke-width="2" opacity=".55"/>'
                      for w, y in ((8, 40), (14, 80), (24, 130), (40, 172))))


def i_coliseo(c, d):
    arcos = "".join(f'<path d="M{x} {y + 30}V{y + 12}A8 8 0 0 1 {x + 16} {y + 12}V{y + 30}Z" fill="{d}"/>'
                    for y in (70, 110, 150) for x in range(14, 186, 24))
    return (f'<path d="M4 200V70Q100 30 196 70V200Z" fill="{c}"/>{arcos}'
            f'<path d="M4 70Q100 30 196 70" stroke="{d}" stroke-width="4" fill="none"/><path d="M150 200V40L196 60V200Z" fill="{P.oscurecer(c, .8)}"/>')


def i_opera(c, d):
    vela = lambda x, h, w: f'<path d="M{x} 170C{x + w * .2} {170 - h * .6} {x + w * .6} {170 - h} {x + w} {170 - h}C{x + w * .8} {170 - h * .5} {x + w * .9} 150 {x + w * 1.1} 170Z" fill="{c}"/>'
    return (vela(10, 80, 60) + vela(50, 110, 70) + vela(100, 90, 60) + vela(134, 60, 46)
            + f'<rect x="0" y="168" width="200" height="32" fill="{c}"/>'
            + "".join(f'<path d="M{x} 170Q{x + 10} 130 {x + 30} 100" stroke="{d}" stroke-width="2" fill="none" opacity=".6"/>' for x in (30, 80, 120)))


def i_montana_pan(c, d):
    return (f'<path d="M0 200C10 150 20 130 40 126C60 122 66 150 80 200Z" fill="{c}"/>'
            f'<path d="M70 200C76 90 100 30 130 30C164 30 176 110 188 200Z" fill="{c}"/>'
            f'<path d="M40 126L130 34" stroke="{d}" stroke-width="2"/><rect x="80" y="74" width="12" height="9" fill="{d}"/>')


def i_obelisco(c, d):
    return (f'<path d="M84 200L90 40L100 20L110 40L116 200Z" fill="{c}"/><rect x="70" y="190" width="60" height="10" fill="{c}"/>'
            f'<rect x="96" y="150" width="8" height="14" fill="{d}"/>')


ICONOS = {k[2:]: v for k, v in globals().items() if k.startswith("i_") and callable(v)}


# =================================================================================================================
# 3. FÚTBOL (protagonista; caja 200x200)
# =================================================================================================================
def _balon(cx, cy, rad, blanco="#ffffff", negro="#1b1b1b", contorno="#1b1b1b", idc="b"):
    """Balón clásico (pentágono central + 5 alrededor recortados por la esfera)."""
    def penta(x, y, s, giro=-90):
        return " ".join(f"{x + s * math.cos(math.radians(giro + i * 72)):.1f},{y + s * math.sin(math.radians(giro + i * 72)):.1f}" for i in range(5))
    centrales = f'<polygon points="{penta(cx, cy, rad * .3)}" fill="{negro}"/>'
    vecinos = "".join(f'<polygon points="{penta(cx + rad * .86 * math.cos(math.radians(-90 + 36 + i * 72)), cy + rad * .86 * math.sin(math.radians(-90 + 36 + i * 72)), rad * .3, -90 + 36 + i * 72 + 180)}" fill="{negro}"/>' for i in range(5))
    costuras = "".join(f'<path d="M{cx + rad * .3 * math.cos(math.radians(-90 + i * 72)):.1f} {cy + rad * .3 * math.sin(math.radians(-90 + i * 72)):.1f}'
                       f'L{cx + rad * .62 * math.cos(math.radians(-90 + i * 72)):.1f} {cy + rad * .62 * math.sin(math.radians(-90 + i * 72)):.1f}" stroke="{negro}" stroke-width="{rad * .04:.1f}"/>' for i in range(5))
    return (f'<clipPath id="{idc}"><circle cx="{cx}" cy="{cy}" r="{rad}"/></clipPath><circle cx="{cx}" cy="{cy}" r="{rad}" fill="{blanco}"/>'
            f'<g clip-path="url(#{idc})">{centrales}{vecinos}{costuras}</g>'
            f'<circle cx="{cx - rad * .35}" cy="{cy - rad * .4}" r="{rad * .22}" fill="#ffffff" opacity=".35"/>'
            f'<circle cx="{cx}" cy="{cy}" r="{rad}" fill="none" stroke="{contorno}" stroke-width="{rad * .06:.1f}"/>')


def u_balon(p, c):
    return _balon(100, 108, 88, contorno=p["oscuro"], idc="fb1")


def u_balon_estela(p, c):
    estela = "".join(f'<path d="M{10 + i * 6} {70 + i * 26}H{70 + i * 4}" stroke="{c}" stroke-width="{10 - i * 2}" stroke-linecap="round" opacity="{.9 - i * .2:.1f}"/>' for i in range(4))
    return estela + _balon(128, 110, 66, contorno=p["oscuro"], idc="fb2")


def _figura(trazos, color, ancho=16):
    return "".join(f'<path d="{t}" stroke="{color}" stroke-width="{ancho}" fill="none" stroke-linecap="round" stroke-linejoin="round"/>' for t in trazos)


def u_chilena(p, c):
    cuerpo = _figura(["M70 150L100 120", "M100 120L132 70", "M100 120L150 112L176 62", "M74 146L40 168", "M86 136L58 104"], c, 18)
    return (_balon(172, 34, 22, contorno=p["oscuro"], idc="fb3") + cuerpo + f'<circle cx="62" cy="160" r="15" fill="{c}"/>'
            f'<path d="M30 196H170" stroke="{c}" stroke-width="4" opacity=".4"/>')


def u_remate(p, c):
    cuerpo = _figura(["M84 64L92 116", "M92 116L74 160L80 196", "M92 116L134 140L158 132", "M86 76L60 100", "M86 76L118 70"], c, 17)
    return (cuerpo + f'<circle cx="82" cy="46" r="15" fill="{c}"/>' + _balon(172, 128, 18, contorno=p["oscuro"], idc="fb4")
            + "".join(f'<path d="M{150 + i * 4} {150 + i * 8}h-{20 + i * 6}" stroke="{c}" stroke-width="3" stroke-linecap="round" opacity=".5"/>' for i in range(3)))


def u_copa(p, c):
    oro, oro_o = P.ORO, P.oscurecer(P.ORO, .7)
    return (f'<path d="M70 200H130L124 176H76Z" fill="{p["dominante_oscuro"]}"/><rect x="74" y="170" width="52" height="8" fill="{oro_o}"/>'
            f'<path d="M86 170C88 150 92 140 98 130H102C108 140 112 150 114 170Z" fill="{oro}"/>'
            f'<path d="M98 130C70 120 52 90 56 54C66 64 80 66 92 60C88 40 92 24 100 14C108 24 112 40 108 60C120 66 134 64 144 54C148 90 130 120 102 130Z" fill="{oro}" stroke="{oro_o}" stroke-width="3"/>'
            + _balon(100, 44, 22, contorno=oro_o, idc="fb5"))


def u_botin(p, c):
    return (f'<path d="M20 150C20 120 30 96 48 92L92 90C100 110 120 120 150 124C172 128 182 140 180 156H20Z" fill="{c}"/>'
            f'<path d="M20 156H180V166H20Z" fill="{p["oscuro"]}"/>'
            + "".join(f'<rect x="{x}" y="166" width="10" height="10" fill="{p["oscuro"]}"/>' for x in (34, 70, 120, 156))
            + "".join(f'<path d="M{58 + i * 10} {96 + i * 4}l14 6" stroke="{p["claro"]}" stroke-width="4" stroke-linecap="round"/>' for i in range(4))
            + _balon(158, 70, 34, contorno=p["oscuro"], idc="fb6"))


def u_red(p, c):
    malla = "".join(f'<path d="M{x} 40V200" stroke="{c}" stroke-width="2" opacity=".55"/>' for x in range(20, 190, 14)) + \
            "".join(f'<path d="M14 {y}H186" stroke="{c}" stroke-width="2" opacity=".55"/>' for y in range(50, 200, 14))
    return (malla + f'<path d="M14 200V36H186V200" stroke="{c}" stroke-width="9" fill="none" stroke-linejoin="round"/>'
            + _balon(110, 150, 34, contorno=p["oscuro"], idc="fb7"))


FUTBOL = {k[2:]: v for k, v in globals().items() if k.startswith("u_") and callable(v)}


# =================================================================================================================
# 4. GRILLAS (composición: imagen + tipografía sobre paneles sólidos)
# =================================================================================================================
FONDOS_CARGADOS = {"geometrico", "franjas", "concentrico", "rayos", "selva", "ciudad"}


def _imagen(p, icono, futbol, x, y, w, h, r, color_silueta, color_detalle, fondo=None):
    """
    Ícono detrás corrido hacia un lado + elemento futbolero delante corrido hacia el otro (composición en diagonal,
    como en los pósters reales). En fondos cargados se apoya en un halo oscuro para que la silueta se lea.
    """
    lado = min(w, h)
    lado_ico = lado * 0.9
    sentido = r.choice([-1, 1])
    ix = x + (w - lado_ico) / 2 - sentido * w * 0.08
    halo = ""
    if fondo in FONDOS_CARGADOS:
        cx, cy, rad = x + w / 2, y + h - lado_ico * 0.48, lado * 0.6
        halo = (f'<radialGradient id="halo_img"><stop offset=".55" stop-color="{p["dominante_oscuro"]}" stop-opacity=".82"/>'
                f'<stop offset="1" stop-color="{p["dominante_oscuro"]}" stop-opacity="0"/></radialGradient>'
                f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{rad:.0f}" fill="url(#halo_img)"/>')
    ico = caja(ICONOS[icono](color_silueta, color_detalle), ix, y + h - lado_ico, lado_ico, voltear=r.random() < .3)
    t = lado * (0.5 if futbol in ("balon", "copa") else 0.6)
    fx = x + w / 2 - t / 2 + sentido * w * 0.24
    fx = min(max(fx, x - t * 0.05), x + w - t * 0.95)
    fut = caja(FUTBOL[futbol](p, P.texto_sobre(color_silueta, [p["claro"], p["acento"], p["oscuro"]])), fx, y + h - t + lado * .02, t)
    return f'{halo}<g opacity=".97">{ico}</g>{fut}'


def g_clasica(p, partes, r):
    panel = p["dominante_oscuro"]
    txt = P.texto_sobre(panel, [p["claro"], p["acento"], P.CREMA])
    acc = P.texto_sobre(panel, [p["acento"], P.ORO, p["claro"]])
    cinta = P.texto_sobre(p["claro"], [p["oscuro"], p["dominante_oscuro"], P.TINTA])
    return (partes["fondo"] + _imagen(p, partes["icono"], partes["futbol"], 70, 150, 460, 470, r, partes["silueta"], partes["detalle"], partes["fondo_nombre"])
            + f'<path d="M0 640L600 600V900H0Z" fill="{panel}"/><path d="M0 640L600 600" stroke="{p["acento"]}" stroke-width="8"/>'
            + f'<rect x="90" y="56" width="420" height="52" rx="6" fill="{p["claro"]}"/>'
            + texto(300, 95, partes["titulo"], 34, cinta, "Bebas FV", max_ancho=390, espaciado=.08)
            + texto(300, 712, partes["pais"], 84, txt, "Anton FV", max_ancho=520)
            + texto(300, 860, partes["anio"], 150, acc, "Anton FV", max_ancho=520, espaciado=.02))


def g_ano_gigante(p, partes, r):
    banda = p["dominante_oscuro"]
    txt = P.texto_sobre(banda, [p["claro"], p["acento"], P.CREMA])
    acc = P.texto_sobre(banda, [p["acento"], P.ORO, p["claro"]])
    anio = texto(300, 240, partes["anio"], 230, p["acento"], "Anton FV", max_ancho=560,
                 trazo=(p["oscuro"], 14))
    return (partes["fondo"] + anio + _imagen(p, partes["icono"], partes["futbol"], 80, 250, 440, 440, r, partes["silueta"], partes["detalle"], partes["fondo_nombre"])
            + f'<rect x="0" y="710" width="600" height="190" fill="{banda}"/><rect x="0" y="706" width="600" height="8" fill="{p["acento"]}"/>'
            + texto(300, 800, partes["pais"], 82, txt, "Anton FV", max_ancho=540)
            + texto(300, 860, partes["titulo"], 34, acc, "Bebas FV", max_ancho=520, espaciado=.1))


def g_lateral(p, partes, r):
    banda = p["dominante_oscuro"]
    acc = P.texto_sobre(banda, [p["acento"], P.ORO, p["claro"]])
    txt = P.texto_sobre(banda, [p["claro"], P.CREMA])
    return (partes["fondo"] + f'<rect x="0" y="0" width="150" height="900" fill="{banda}"/><rect x="150" y="0" width="8" height="900" fill="{p["acento"]}"/>'
            + f'<g transform="translate(118 450) rotate(-90)">{texto(0, 0, partes["anio"], 170, acc, "Anton FV", max_ancho=820, espaciado=.06)}</g>'
            + _imagen(p, partes["icono"], partes["futbol"], 180, 170, 400, 520, r, partes["silueta"], partes["detalle"], partes["fondo_nombre"])
            + f'<rect x="174" y="720" width="410" height="150" rx="8" fill="{banda}"/>'
            + texto(380, 800, partes["pais"], 70, txt, "Anton FV", max_ancho=380)
            + texto(380, 848, partes["titulo"], 28, acc, "Bebas FV", max_ancho=380, espaciado=.08)
            + f'<rect x="180" y="40" width="400" height="46" rx="6" fill="{banda}"/>'
            + texto(380, 74, partes["lema"], 28, txt, "Bebas FV", max_ancho=380, espaciado=.08))


def g_medallon(p, partes, r):
    banda = p["dominante_oscuro"]
    txt = P.texto_sobre(banda, [p["claro"], P.CREMA])
    acc = P.texto_sobre(banda, [p["acento"], P.ORO, p["claro"]])
    interior = P.mezclar(p["claro"], p["dominante_claro"], .4)
    sil = P.texto_sobre(interior, [p["dominante"], p["dominante_oscuro"], p["oscuro"]])
    return (partes["fondo"]
            + f'<circle cx="300" cy="400" r="250" fill="{p["acento"]}"/><circle cx="300" cy="400" r="232" fill="{interior}"/>'
            + f'<clipPath id="medallon"><circle cx="300" cy="400" r="232"/></clipPath>'
            + f'<g clip-path="url(#medallon)">{_imagen(p, partes["icono"], partes["futbol"], 110, 200, 380, 400, r, sil, p["acento"])}</g>'
            + f'<rect x="0" y="690" width="600" height="210" fill="{banda}"/>'
            + texto(300, 770, partes["pais"], 80, txt, "Anton FV", max_ancho=540)
            + texto(300, 868, f'{partes["titulo"]} · {partes["anio"]}', 40, acc, "Bebas FV", max_ancho=540, espaciado=.06)
            + f'<rect x="150" y="80" width="300" height="56" rx="28" fill="{banda}"/>'
            + texto(300, 122, partes["anio"], 46, acc, "Anton FV", max_ancho=260, espaciado=.08))


def g_banda(p, partes, r):
    banda = p["dominante"]
    txt = P.texto_sobre(banda, [p["claro"], P.CREMA, P.TINTA])
    acc = P.texto_sobre(p["oscuro"], [p["acento"], P.ORO, p["claro"]])
    return (partes["fondo"] + _imagen(p, partes["icono"], partes["futbol"], 60, 40, 480, 600, r, partes["silueta"], partes["detalle"], partes["fondo_nombre"])
            + f'<path d="M0 670L600 610V900H0Z" fill="{banda}"/><path d="M0 770L600 710V900H0Z" fill="{p["oscuro"]}"/>'
            + texto(30, 870, partes["anio"], 130, acc, "Anton FV", ancla="start", max_ancho=300)
            + texto(570, 700, partes["pais"], 62, txt, "Anton FV", ancla="end", max_ancho=360)
            + texto(570, 862, partes["titulo"], 28, P.texto_sobre(p["oscuro"], [p["claro"], P.CREMA]), "Bebas FV", ancla="end", max_ancho=250, espaciado=.06))


def g_retro(p, partes, r):
    tinta = P.texto_sobre(p["crema"], [p["dominante_oscuro"], p["oscuro"], P.TINTA])
    rojo = P.texto_sobre(p["crema"], [p["dominante"], p["acento"], p["dominante_oscuro"]])
    cinta = p["dominante"]
    return (partes["fondo"]
            + texto(300, 112, partes["titulo"], 40, tinta, "Bebas FV", max_ancho=500, espaciado=.12)
            + texto(300, 262, partes["anio"], 150, rojo, "Anton FV", max_ancho=500, espaciado=.04)
            + _imagen(p, partes["icono"], partes["futbol"], 90, 280, 420, 430, r, p["dominante_oscuro"], p["acento"])
            + f'<path d="M40 740H560L540 776L560 812H40L60 776Z" fill="{cinta}"/>'
            + texto(300, 796, partes["pais"], 52, P.texto_sobre(cinta, [p["crema"], p["claro"], P.TINTA]), "Anton FV", max_ancho=440)
            + texto(300, 858, partes["lema"], 26, tinta, "Bebas FV", max_ancho=480, espaciado=.12))


GRILLAS = {k[2:]: v for k, v in globals().items() if k.startswith("g_") and callable(v)}
# Fondos que ya tienen su propio marco/tipografía clásica: la grilla retro solo va con el fondo retro y viceversa
GRILLA_DE_FONDO = {"retro": ["retro"]}


# =================================================================================================================
# Composición
# =================================================================================================================
def receta_aleatoria(region: Dict, iconos_pais: List[str], r: random.Random, lemas: List[str]) -> Dict:
    fondo = r.choice(region["fondos"])
    grillas = GRILLA_DE_FONDO.get(fondo) or [g for g in GRILLAS if g != "retro"]
    iconos = [i for i in (iconos_pais or []) if i in ICONOS] or [i for i in region["iconos"] if i in ICONOS]
    # lo propio del país: su ícono favorito el 55%, el segundo el 20%; el 25% restante uno de su región (variedad
    # entre mundiales del mismo país)
    tirada = r.random()
    if iconos_pais and tirada < .55:
        icono = iconos[0]
    elif iconos_pais and tirada < .75:
        icono = iconos[1] if len(iconos) > 1 else iconos[0]
    else:
        icono = r.choice([i for i in region["iconos"] if i in ICONOS] or iconos)
    return {"fondo": fondo, "icono": icono, "futbol": r.choice(list(FUTBOL)), "grilla": r.choice(grillas),
            "lema": r.choice(lemas), "semilla": r.randint(0, 10 ** 6)}


def dibujar(receta: Dict, colores_bandera: List[dict], pais: str, anio, titulo: str) -> str:
    p = P.de_bandera(colores_bandera)
    r = random.Random(receta["semilla"])
    fondo = FONDOS[receta["fondo"]](p, r)
    # silueta del ícono: contrasta con el fondo (oscura sobre fondos claros, clara sobre oscuros)
    claro_fondo = receta["fondo"] in ("ondas", "retro", "desierto", "mar") and receta["fondo"] not in FONDOS_CARGADOS
    silueta = p["dominante_oscuro"] if claro_fondo else P.mezclar(p["claro"], p["dominante_claro"], .25)
    detalle = p["acento"] if P.contraste(p["acento"], silueta) > 1.6 else p["dominante"]
    partes = {"fondo": fondo, "fondo_nombre": receta["fondo"], "icono": receta["icono"], "futbol": receta["futbol"], "silueta": silueta, "detalle": detalle,
              "pais": pais, "anio": str(anio), "titulo": titulo, "lema": receta.get("lema", "")}
    cuerpo = GRILLAS[receta["grilla"]](p, partes, r)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ANCHO} {ALTO}" width="{ANCHO}" height="{ALTO}">'
            f'{estilos_fuentes()}<clipPath id="lienzo"><rect width="{ANCHO}" height="{ALTO}"/></clipPath>'
            f'<g clip-path="url(#lienzo)">{cuerpo}</g></svg>')


def clave(receta: Dict) -> str:
    """Combinación visual (sin la semilla): lo que no se debe repetir entre mundiales."""
    return f'{receta["fondo"]}|{receta["icono"]}|{receta["futbol"]}|{receta["grilla"]}'
