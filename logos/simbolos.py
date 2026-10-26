"""
Biblioteca de ~40 símbolos de marca (isotipos) paramétricos, dibujados en una caja de 100x100 centrada en (50,50).
Cada función recibe (c1, c2, v) -> str con elementos SVG: c1 = color principal, c2 = acento, v = variante (rng):
grosor, giro, relleno o contorno. Ninguno copia un isotipo real: son formas geométricas propias.
Los símbolos se agrupan por "familia" (geométrico, natural, movimiento, tecnología, objeto) para repartir variedad.
"""
import math
import random


def _poli(puntos) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in puntos)


def _regular(n, r, cx=50, cy=50, giro=-90):
    return [(cx + r * math.cos(math.radians(giro + i * 360 / n)), cy + r * math.sin(math.radians(giro + i * 360 / n))) for i in range(n)]


def _estrella(n, r, ri, cx=50, cy=50, giro=-90):
    pts = []
    for i in range(n * 2):
        rr = r if i % 2 == 0 else ri
        a = math.radians(giro + i * 180 / n)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def _arco(cx, cy, r, a0, a1):
    x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
    x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
    grande = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M{x0:.1f} {y0:.1f} A{r} {r} 0 {grande} 1 {x1:.1f} {y1:.1f}"


# --- geométricos -------------------------------------------------------------------------------
def arcos_dobles(c1, c2, v):
    g = v.uniform(7, 11)
    return (f'<path d="{_arco(50, 50, 38, 200, 340)}" fill="none" stroke="{c1}" stroke-width="{g:.1f}" stroke-linecap="round"/>'
            f'<path d="{_arco(50, 50, 24, 20, 160)}" fill="none" stroke="{c2}" stroke-width="{g:.1f}" stroke-linecap="round"/>')


def triangulo_cortado(c1, c2, v):
    return (f'<polygon points="{_poli([(50, 10), (92, 86), (8, 86)])}" fill="{c1}"/>'
            f'<polygon points="{_poli([(30, 86), (62, 30), (70, 44), (46, 86)])}" fill="{c2}"/>')


def hexagono_hueco(c1, c2, v):
    return (f'<polygon points="{_poli(_regular(6, 42, giro=v.choice([-90, 0])))}" fill="{c1}"/>'
            f'<polygon points="{_poli(_regular(6, 20, giro=v.choice([-90, 0])))}" fill="{c2}"/>')


def diamante_partido(c1, c2, v):
    return (f'<polygon points="50,6 92,50 50,94" fill="{c1}"/><polygon points="50,6 8,50 50,94" fill="{c2}"/>'
            f'<line x1="50" y1="6" x2="50" y2="94" stroke="#ffffff" stroke-opacity=".35" stroke-width="2"/>')


def media_luna(c1, c2, v):
    return (f'<circle cx="50" cy="50" r="40" fill="{c1}"/><circle cx="{v.choice([64, 36])}" cy="42" r="30" fill="{c2}"/>')


def cuadros_pixel(c1, c2, v):
    celdas = [(x, y) for x in range(3) for y in range(3)]
    llenas = v.sample(celdas, 6)
    return "".join(f'<rect x="{12 + x * 26}" y="{12 + y * 26}" width="22" height="22" rx="3" fill="{c1 if (x + y) % 2 else c2}"/>' for x, y in llenas)


def anillos(c1, c2, v):
    g = v.uniform(6, 10)
    return (f'<circle cx="38" cy="50" r="24" fill="none" stroke="{c1}" stroke-width="{g:.1f}"/>'
            f'<circle cx="62" cy="50" r="24" fill="none" stroke="{c2}" stroke-width="{g:.1f}"/>')


def trebol_geometrico(c1, c2, v):
    return "".join(f'<circle cx="{cx}" cy="{cy}" r="17" fill="{c1 if i % 2 == 0 else c2}"/>'
                   for i, (cx, cy) in enumerate([(50, 30), (70, 50), (50, 70), (30, 50)]))


def cubo_isometrico(c1, c2, v):
    return (f'<polygon points="50,10 86,30 50,50 14,30" fill="{c2}"/><polygon points="14,30 50,50 50,92 14,72" fill="{c1}"/>'
            f'<polygon points="86,30 50,50 50,92 86,72" fill="{c1}" fill-opacity=".72"/>')


def infinito(c1, c2, v):
    g = v.uniform(8, 12)
    return (f'<path d="M50 50 C38 30, 12 30, 12 50 C12 70, 38 70, 50 50 C62 30, 88 30, 88 50 C88 70, 62 70, 50 50Z" fill="none" '
            f'stroke="{c1}" stroke-width="{g:.1f}" stroke-linejoin="round"/><circle cx="88" cy="50" r="{g / 2 + 1:.1f}" fill="{c2}"/>')


def corte_diagonal(c1, c2, v):
    franjas = "".join(f'<polygon points="{_poli([(20 + i * 18, 90), (40 + i * 18, 10), (50 + i * 18, 10), (30 + i * 18, 90)])}" fill="{c2 if i == 1 else c1}"/>' for i in range(3))
    return franjas


def espiral_cuadrada(c1, c2, v):
    return (f'<path d="M50 50 h14 v-24 h-38 v52 h62 v-70 h-74" fill="none" stroke="{c1}" stroke-width="8" stroke-linejoin="miter"/>'
            f'<rect x="44" y="44" width="12" height="12" fill="{c2}"/>')


def diamante_facetado(c1, c2, v):
    return (f'<polygon points="22,36 36,18 64,18 78,36 50,88" fill="{c1}"/>'
            f'<polygon points="22,36 78,36 50,88" fill="{c2}"/><polygon points="36,18 50,36 64,18" fill="#ffffff" fill-opacity=".35"/>')


# --- naturales ---------------------------------------------------------------------------------
def hoja(c1, c2, v):
    return (f'<path d="M20 80 C20 40, 50 14, 84 16 C84 52, 60 82, 20 80Z" fill="{c1}"/>'
            f'<path d="M24 76 C42 58, 58 42, 76 24" fill="none" stroke="{c2}" stroke-width="4" stroke-linecap="round"/>')


def gota(c1, c2, v):
    return (f'<path d="M50 8 C66 34, 80 50, 80 64 C80 82, 66 92, 50 92 C34 92, 20 82, 20 64 C20 50, 34 34, 50 8Z" fill="{c1}"/>'
            f'<path d="M38 66 C38 74, 44 80, 52 80" fill="none" stroke="{c2}" stroke-width="5" stroke-linecap="round"/>')


def llama(c1, c2, v):
    return (f'<path d="M50 6 C62 26, 82 40, 76 66 C72 84, 60 94, 50 94 C34 94, 22 82, 24 64 C26 50, 36 46, 38 32 C46 42, 48 50, 46 58 C56 48, 56 26, 50 6Z" fill="{c1}"/>'
            f'<path d="M50 56 C58 64, 62 72, 58 82 C54 90, 42 90, 40 80 C38 72, 46 66, 50 56Z" fill="{c2}"/>')


def sol_rayos(c1, c2, v):
    n = v.choice([8, 10, 12])
    rayos = "".join(f'<line x1="{50 + 30 * math.cos(math.radians(i * 360 / n)):.1f}" y1="{50 + 30 * math.sin(math.radians(i * 360 / n)):.1f}" '
                    f'x2="{50 + 44 * math.cos(math.radians(i * 360 / n)):.1f}" y2="{50 + 44 * math.sin(math.radians(i * 360 / n)):.1f}" '
                    f'stroke="{c2}" stroke-width="6" stroke-linecap="round"/>' for i in range(n))
    return rayos + f'<circle cx="50" cy="50" r="22" fill="{c1}"/>'


def montana(c1, c2, v):
    return (f'<polygon points="6,86 38,26 56,56 68,40 94,86" fill="{c1}"/>'
            f'<polygon points="38,26 47,43 40,40 33,45" fill="{c2}"/><polygon points="68,40 74,51 68,48 62,52" fill="{c2}"/>')


def ola_rizo(c1, c2, v):
    return (f'<path d="M6 70 C24 70, 30 40, 54 34 C74 30, 88 46, 80 60 C74 70, 60 66, 62 56 C64 50, 72 52, 70 56" fill="none" '
            f'stroke="{c1}" stroke-width="9" stroke-linecap="round"/><path d="M6 86 C28 76, 50 92, 94 78" fill="none" stroke="{c2}" stroke-width="6" stroke-linecap="round"/>')


def ondas_triples(c1, c2, v):
    return "".join(f'<path d="M8 {34 + i * 16} C24 {24 + i * 16}, 40 {44 + i * 16}, 56 {34 + i * 16} S 84 {24 + i * 16}, 92 {34 + i * 16}" '
                   f'fill="none" stroke="{c1 if i != 1 else c2}" stroke-width="7" stroke-linecap="round"/>' for i in range(3))


def alas(c1, c2, v):
    return (f'<path d="M50 60 C36 44, 18 40, 6 42 C18 52, 30 60, 50 72Z" fill="{c1}"/>'
            f'<path d="M50 60 C64 44, 82 40, 94 42 C82 52, 70 60, 50 72Z" fill="{c1}"/>'
            f'<path d="M50 30 L58 52 L50 64 L42 52Z" fill="{c2}"/>')


def pluma_ascendente(c1, c2, v):
    return (f'<path d="M18 88 C30 60, 52 28, 88 12 C80 40, 60 70, 18 88Z" fill="{c1}"/>'
            f'<path d="M22 84 L70 32" stroke="{c2}" stroke-width="3"/>')


# --- movimiento ---------------------------------------------------------------------------------
def rayo(c1, c2, v):
    return (f'<polygon points="58,4 22,56 46,56 38,96 80,40 54,40" fill="{c1}"/>'
            f'<polygon points="58,4 46,40 54,40" fill="{c2}"/>')


def estrella_cinetica(c1, c2, v):
    lineas = "".join(f'<line x1="{6 + i * 4}" y1="{40 + i * 10}" x2="{30 + i * 2}" y2="{40 + i * 10}" stroke="{c2}" stroke-width="5" stroke-linecap="round"/>' for i in range(3))
    return lineas + f'<polygon points="{_poli(_estrella(5, 32, 14, cx=62, cy=50))}" fill="{c1}"/>'


def chevrons(c1, c2, v):
    return "".join(f'<polyline points="{14 + i * 22},18 {40 + i * 22},50 {14 + i * 22},82" fill="none" stroke="{c1 if i < 2 else c2}" '
                   f'stroke-width="11" stroke-linejoin="round" stroke-linecap="round"/>' for i in range(3))


def flecha_ascendente(c1, c2, v):
    return (f'<polyline points="8,82 34,56 52,70 88,26" fill="none" stroke="{c1}" stroke-width="10" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<polygon points="70,20 94,16 90,40" fill="{c2}"/>')


def pulso(c1, c2, v):
    return (f'<polyline points="4,54 30,54 38,30 50,80 60,20 70,54 96,54" fill="none" stroke="{c1}" stroke-width="8" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="60" cy="20" r="6" fill="{c2}"/>')


def rueda_velocidad(c1, c2, v):
    return (f'<circle cx="60" cy="50" r="30" fill="none" stroke="{c1}" stroke-width="10"/><circle cx="60" cy="50" r="9" fill="{c2}"/>'
            + "".join(f'<line x1="4" y1="{36 + i * 14}" x2="{24 - i * 4}" y2="{36 + i * 14}" stroke="{c2}" stroke-width="6" stroke-linecap="round"/>' for i in range(3)))


def bandera_ondeante(c1, c2, v):
    return (f'<line x1="18" y1="10" x2="18" y2="94" stroke="{c2}" stroke-width="7" stroke-linecap="round"/>'
            f'<path d="M22 14 C40 6, 56 24, 88 14 L88 52 C56 62, 40 44, 22 52Z" fill="{c1}"/>')


def punto_y_arco(c1, c2, v):
    return (f'<circle cx="50" cy="22" r="13" fill="{c2}"/>'
            f'<path d="M14 82 C26 46, 74 46, 86 82" fill="none" stroke="{c1}" stroke-width="13" stroke-linecap="round"/>')


# --- tecnología -----------------------------------------------------------------------------------
def orbita(c1, c2, v):
    return (f'<ellipse cx="50" cy="50" rx="44" ry="16" fill="none" stroke="{c1}" stroke-width="5" transform="rotate(-30 50 50)"/>'
            f'<ellipse cx="50" cy="50" rx="44" ry="16" fill="none" stroke="{c1}" stroke-width="5" transform="rotate(30 50 50)"/>'
            f'<circle cx="50" cy="50" r="11" fill="{c2}"/>')


def senal(c1, c2, v):
    return (f'<circle cx="24" cy="76" r="9" fill="{c2}"/>' + "".join(
        f'<path d="{_arco(24, 76, 24 + i * 20, -90, 0)}" fill="none" stroke="{c1}" stroke-width="9" stroke-linecap="round"/>' for i in range(3)))


def engranaje(c1, c2, v):
    dientes = "".join(f'<rect x="44" y="4" width="12" height="18" rx="2" fill="{c1}" transform="rotate({i * 45} 50 50)"/>' for i in range(8))
    return dientes + f'<circle cx="50" cy="50" r="30" fill="{c1}"/><circle cx="50" cy="50" r="13" fill="{c2}"/>'


def lente(c1, c2, v):
    return (f'<path d="M4 50 C24 18, 76 18, 96 50 C76 82, 24 82, 4 50Z" fill="{c1}"/>'
            f'<circle cx="50" cy="50" r="17" fill="{c2}"/><circle cx="56" cy="44" r="5" fill="#ffffff" fill-opacity=".8"/>')


def chip(c1, c2, v):
    pines = "".join(f'<rect x="{26 + i * 14}" y="6" width="6" height="14" fill="{c2}"/><rect x="{26 + i * 14}" y="80" width="6" height="14" fill="{c2}"/>' for i in range(4))
    return pines + f'<rect x="16" y="18" width="68" height="64" rx="10" fill="{c1}"/><rect x="34" y="36" width="32" height="28" rx="4" fill="{c2}"/>'


def boton_play(c1, c2, v):
    return (f'<rect x="8" y="14" width="84" height="72" rx="22" fill="{c1}"/><polygon points="40,32 68,50 40,68" fill="{c2}"/>')


# --- objetos del rubro --------------------------------------------------------------------------
def avion(c1, c2, v):
    return (f'<path d="M8 58 L46 50 L64 12 L74 14 L66 48 L90 44 C96 44, 96 52, 90 54 L66 54 L74 88 L64 90 L46 58 L8 62Z" fill="{c1}"/>'
            f'<circle cx="80" cy="49" r="3" fill="{c2}"/>')


def corona(c1, c2, v):
    return (f'<polygon points="12,74 16,30 34,52 50,20 66,52 84,30 88,74" fill="{c1}"/>'
            f'<rect x="12" y="78" width="76" height="10" rx="3" fill="{c2}"/>')


def reloj(c1, c2, v):
    return (f'<circle cx="50" cy="50" r="40" fill="none" stroke="{c1}" stroke-width="8"/>'
            f'<line x1="50" y1="50" x2="50" y2="24" stroke="{c2}" stroke-width="7" stroke-linecap="round"/>'
            f'<line x1="50" y1="50" x2="70" y2="60" stroke="{c1}" stroke-width="7" stroke-linecap="round"/>')


def pelota_paneles(c1, c2, v):
    return (f'<circle cx="50" cy="50" r="42" fill="{c1}"/><polygon points="{_poli(_regular(5, 15))}" fill="{c2}"/>'
            + "".join(f'<line x1="{50 + 15 * math.cos(math.radians(-90 + i * 72)):.1f}" y1="{50 + 15 * math.sin(math.radians(-90 + i * 72)):.1f}" '
                      f'x2="{50 + 40 * math.cos(math.radians(-90 + i * 72)):.1f}" y2="{50 + 40 * math.sin(math.radians(-90 + i * 72)):.1f}" stroke="{c2}" stroke-width="4"/>' for i in range(5)))


def zapatilla(c1, c2, v):
    return (f'<path d="M6 70 C6 56, 18 54, 30 52 L44 34 C52 40, 60 44, 70 48 C86 54, 94 60, 94 72 Z" fill="{c1}"/>'
            f'<rect x="6" y="72" width="88" height="10" rx="5" fill="{c2}"/>')


def escudo_moderno(c1, c2, v):
    return (f'<path d="M50 6 L86 18 V48 C86 72, 70 86, 50 94 C30 86, 14 72, 14 48 V18Z" fill="{c1}"/>'
            f'<path d="M50 6 L86 18 V48 C86 72, 70 86, 50 94Z" fill="{c2}" fill-opacity=".55"/>')


def taza_vapor(c1, c2, v):
    return (f'<path d="M18 40 H74 V68 C74 82, 64 90, 46 90 C28 90, 18 82, 18 68Z" fill="{c1}"/>'
            f'<path d="M74 48 C90 48, 90 70, 74 70" fill="none" stroke="{c1}" stroke-width="6"/>'
            + "".join(f'<path d="M{34 + i * 12} 30 C{30 + i * 12} 22, {40 + i * 12} 18, {36 + i * 12} 8" fill="none" stroke="{c2}" stroke-width="4" stroke-linecap="round"/>' for i in range(3)))


def auto_perfil(c1, c2, v):
    return (f'<path d="M6 66 C6 56, 14 52, 24 50 L36 34 C40 30, 46 28, 54 28 L68 28 C76 28, 82 34, 86 42 L92 52 C96 56, 96 66, 94 68Z" fill="{c1}"/>'
            f'<circle cx="28" cy="70" r="11" fill="{c2}"/><circle cx="74" cy="70" r="11" fill="{c2}"/>')


SIMBOLOS = {
    # familia -> funciones (el generador evita repetir símbolo dentro de un rubro)
    "geometrico": [arcos_dobles, triangulo_cortado, hexagono_hueco, diamante_partido, media_luna, cuadros_pixel, anillos,
                   trebol_geometrico, cubo_isometrico, infinito, corte_diagonal, espiral_cuadrada, diamante_facetado],
    "natural": [hoja, gota, llama, sol_rayos, montana, ola_rizo, ondas_triples, alas, pluma_ascendente],
    "movimiento": [rayo, estrella_cinetica, chevrons, flecha_ascendente, pulso, rueda_velocidad, bandera_ondeante],
    "tecnologia": [orbita, senal, engranaje, lente, chip, boton_play],
    "objeto": [avion, corona, reloj, pelota_paneles, zapatilla, escudo_moderno, taza_vapor, auto_perfil],
}
# Los símbolos-objeto solo tienen sentido en ciertos rubros (generar_marcas.py los filtra)
OBJETOS_RUBRO = {
    "avion": ["aerolineas"], "corona": ["lujo", "banca", "bebidas"], "reloj": ["lujo", "seguros"],
    "pelota_paneles": ["indumentaria", "calzado", "videojuegos"], "zapatilla": ["calzado", "indumentaria"],
    "escudo_moderno": ["seguros", "banca"], "llama": ["energia", "alimentos"], "taza_vapor": ["alimentos", "bebidas"], "auto_perfil": ["automotriz"],
}
TODOS = {f.__name__: f for fam in SIMBOLOS.values() for f in fam}


def dibujar(nombre: str, c1: str, c2: str, semilla) -> str:
    return TODOS[nombre](c1, c2, random.Random(semilla))
