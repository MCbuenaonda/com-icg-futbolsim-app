"""
Texto -> trazos SVG (paths) con fontTools: los logos publicados no dependen de ninguna fuente instalada.
Solo lo usan los scripts que generan logos (requiere `pip install fonttools brotli`).

    f = fuente("montserrat", peso=800)
    d, ancho, alto = trazo("VOLTA", f, tam=72, espaciado=4, inclinacion=0.18)
"""
import functools
import os
from typing import Tuple

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

DIR = os.path.join(os.path.dirname(__file__), "fuentes")

# nombre -> (archivo, es_variable). Familias elegidas para cubrir estilos muy distintos (ver LEEME.txt)
FUENTES = {
    "anton": ("Anton-Regular.woff", False),            # condensada pesada, póster
    "bebas": ("BebasNeue-Regular.woff", False),        # condensada limpia, mayúsculas
    "archivo": ("ArchivoBlack-Regular.ttf", False),    # grotesca muy negra
    "righteous": ("Righteous-Regular.ttf", False),     # display redondeada retro
    "bungee": ("Bungee-Regular.ttf", False),           # bloques, señalética
    "stencil": ("SairaStencilOne-Regular.ttf", False), # stencil deportiva
    "russo": ("RussoOne-Regular.ttf", False),          # tecno-deportiva
    "blackops": ("BlackOpsOne-Regular.ttf", False),    # stencil militar/extrema
    "kanit_italica": ("Kanit-BoldItalic.ttf", False),  # itálica deportiva
    "kanit": ("Kanit-SemiBold.ttf", False),            # geométrica amable
    "playfair": ("PlayfairDisplay[wght].ttf", True),   # serifa de contraste (lujo)
    "montserrat": ("Montserrat[wght].ttf", True),      # geométrica clásica
    "oswald": ("Oswald[wght].ttf", True),              # condensada versátil
    "rubik": ("Rubik[wght].ttf", True),                # redondeada suave
    "teko": ("Teko[wght].ttf", True),                  # ultra condensada, marcador deportivo
    "exo_italica": ("Exo2-Italic[wght].ttf", True),    # futurista itálica (velocidad)
    "comfortaa": ("Comfortaa[wght].ttf", True),        # redondeada liviana (consumo)
    "michroma": ("Michroma-Regular.ttf", False),       # extendida tecnológica
    "cinzel": ("Cinzel[wght].ttf", True),              # romana clásica (seguros, banca, lujo)
    "pacifico": ("Pacifico-Regular.ttf", False),       # caligráfica (bebidas, alimentos)
}


class Fuente:
    def __init__(self, nombre: str, peso: int = 700):
        archivo, variable = FUENTES[nombre]
        fnt = TTFont(os.path.join(DIR, archivo))
        if variable:
            # instanciar una fuente variable es lento (hasta ~25 s): se guarda la instancia en una caché en disco
            import tempfile
            cache = os.path.join(tempfile.gettempdir(), f"logos_{nombre}_{peso}.ttf")
            if os.path.exists(cache):
                fnt = TTFont(cache)
            else:
                from fontTools.varLib.instancer import instantiateVariableFont
                eje = next((a for a in fnt["fvar"].axes if a.axisTag == "wght"), None)
                if eje:
                    fnt = instantiateVariableFont(fnt, {"wght": max(eje.minValue, min(eje.maxValue, peso))})
                    fnt.save(cache)
                    fnt = TTFont(cache)
        self.nombre, self.peso = nombre, peso
        self.glyphs = fnt.getGlyphSet()
        self.cmap = fnt.getBestCmap()
        self.upm = fnt["head"].unitsPerEm
        self.hmtx = fnt["hmtx"]
        os2 = fnt["OS/2"]
        self.mayus = getattr(os2, "sCapHeight", 0) or int(self.upm * 0.7)
        self.ascender = fnt["hhea"].ascent


def _num(x: float) -> str:
    """Coordenadas con 1 decimal: los logos pesan ~3 veces menos y no se nota."""
    t = f"{x:.1f}"
    return t[:-2] if t.endswith(".0") else t


@functools.lru_cache(maxsize=64)
def fuente(nombre: str, peso: int = 700) -> Fuente:
    return Fuente(nombre, peso)


def medir(texto: str, f: Fuente, tam: float, espaciado: float = 0) -> float:
    esc = tam / f.upm
    ancho = 0.0
    for ch in texto:
        g = f.cmap.get(ord(ch)) or f.cmap.get(ord("?"))
        ancho += (f.hmtx[g][0] if g else f.upm * 0.3) * esc + espaciado
    return max(0.0, ancho - espaciado)


def trazo(texto: str, f: Fuente, tam: float, x: float = 0, y: float = 0, espaciado: float = 0,
          inclinacion: float = 0.0, ancla: str = "inicio") -> Tuple[str, float, float]:
    """
    Path 'd' del texto con la línea de base en y. ancla: inicio | medio | fin (respecto de x).
    inclinacion: falsa itálica (0.2 = ~11°). Devuelve (d, ancho, alto de mayúsculas).
    """
    esc = tam / f.upm
    ancho = medir(texto, f, tam, espaciado)
    cursor = x - (ancho / 2 if ancla == "medio" else ancho if ancla == "fin" else 0)
    partes = []
    for ch in texto:
        g = f.cmap.get(ord(ch))
        avance = (f.hmtx[g][0] if g else f.upm * 0.3) * esc
        if g and ch != " ":
            pen = SVGPathPen(f.glyphs, ntos=_num)
            # x' = esc*x + inclinacion*esc*y + cursor ; y' = -esc*y + y_base (las fuentes tienen y hacia arriba)
            f.glyphs[g].draw(TransformPen(pen, (esc, 0, inclinacion * esc, -esc, cursor, y)))
            d = pen.getCommands()
            if d:
                partes.append(d)
        cursor += avance + espaciado
    return " ".join(partes), ancho, f.mayus * esc


def texto_en_arco(texto: str, f: Fuente, tam: float, cx: float, cy: float, radio: float, centro_grados: float = -90,
                  espaciado: float = 0, abajo: bool = False) -> str:
    """Texto a lo largo de un arco (sellos circulares): cada letra como path rotado. abajo=True lee de izquierda a
    derecha por la parte inferior del círculo."""
    esc = tam / f.upm
    anchos = []
    for ch in texto:
        g = f.cmap.get(ord(ch))
        anchos.append((f.hmtx[g][0] if g else f.upm * 0.3) * esc + espaciado)
    total = sum(anchos) - espaciado
    import math
    angulo_total = total / radio
    sentido = -1 if abajo else 1
    a = math.radians(centro_grados) - sentido * angulo_total / 2
    salida = []
    for ch, w in zip(texto, anchos):
        medio = a + sentido * (w / 2) / radio
        g = f.cmap.get(ord(ch))
        if g and ch != " ":
            pen = SVGPathPen(f.glyphs, ntos=_num)
            px, py = cx + radio * math.cos(medio), cy + radio * math.sin(medio)
            rot = math.degrees(medio) + (90 if not abajo else -90)
            glifo_w = w - espaciado
            # se dibuja centrado en (0,0) y se ubica con transform
            f.glyphs[g].draw(TransformPen(pen, (esc, 0, 0, -esc, -glifo_w / 2, (f.mayus * esc / 2) if not abajo else (f.mayus * esc / 2))))
            salida.append(f'<path transform="translate({px:.1f} {py:.1f}) rotate({rot:.1f})" d="{pen.getCommands()}"/>')
        a += sentido * w / radio
    return "".join(salida)
