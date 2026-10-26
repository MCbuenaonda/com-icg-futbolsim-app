"""Utilidades de color de los logos (sin dependencias: las usa también generar_marcas.py --aplicar)."""
import colorsys

FONDO = "#111c2e"
OSCURO = "#0b1220"


def _rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in rgb)


def mezclar(a, b, f):
    return _hex([x + (y - x) * f for x, y in zip(_rgb(a), _rgb(b))])


def luminancia(h):
    def canal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b):
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def legible(c, fondo=FONDO, minimo=3.0):
    """Aclara el color hasta que se lea sobre el fondo oscuro."""
    paso = 0
    while contraste(c, fondo) < minimo and paso < 12:
        c = mezclar(c, "#ffffff", 0.12)
        paso += 1
    return c


def tinta_sobre(c):
    """Blanco u oscuro, lo que mejor se lea sobre un relleno c."""
    return "#ffffff" if contraste("#ffffff", c) >= contraste(OSCURO, c) else OSCURO


def girar_tono(h, grados):
    """Corre el matiz (para que dos marcas con la misma paleta base no queden iguales)."""
    r, g, b = (v / 255 for v in _rgb(h))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb((hh + grados / 360) % 1, ll, ss)
    return _hex([r * 255, g * 255, b * 255])


