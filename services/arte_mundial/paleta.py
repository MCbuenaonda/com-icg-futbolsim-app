"""
Paleta del arte del Mundial a partir de los colores REALES de la bandera del anfitrión (paises.colores, ver
asignar_colores_paises.py). Roles:
  dominante  el color saturado de más área (fondo/protagonista)
  acento     otro color de la bandera bien distinto del dominante (detalles, segunda franja, uniforme)
  claro      blanco de la bandera o un crema "de papel" (tipografía sobre fondos oscuros)
  oscuro     el dominante muy oscurecido (contornos, tipografía sobre fondos claros)
Los tonos de mezcla de los bordes (poca área y "entre" dos colores) se descartan.
"""
import colorsys
from typing import Dict, List

CREMA = "#f6efdc"
TINTA = "#14161f"
ORO = "#e8b53a"


def a_rgb(h: str):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def a_hex(rgb) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(round(c)))) for c in rgb))


def mezclar(a: str, b: str, t: float) -> str:
    ra, rb = a_rgb(a), a_rgb(b)
    return a_hex([x + (y - x) * t for x, y in zip(ra, rb)])


def oscurecer(h: str, f: float) -> str:
    return a_hex([c * f for c in a_rgb(h)])


def aclarar(h: str, t: float) -> str:
    return mezclar(h, "#ffffff", t)


def luminancia(h: str) -> float:
    def canal(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(c) for c in a_rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a: str, b: str) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def saturacion(h: str) -> float:
    """Saturación HSV; los casi negros (valor < 0.2) cuentan como 0 aunque su tono sea 'puro'."""
    r, g, b = (c / 255 for c in a_rgb(h))
    _, s, v = colorsys.rgb_to_hsv(r, g, b)
    return s if v >= 0.2 else 0.0


def _distancia(a: str, b: str) -> float:
    return sum(abs(x - y) for x, y in zip(a_rgb(a), a_rgb(b)))


def texto_sobre(fondo: str, opciones: List[str]) -> str:
    """El color de `opciones` que más contrasta con `fondo` (y si ninguno llega a 4.5:1, blanco o tinta)."""
    mejor = max(opciones, key=lambda c: contraste(c, fondo))
    if contraste(mejor, fondo) >= 4.5:
        return mejor
    return max(["#ffffff", TINTA], key=lambda c: contraste(c, fondo))


def de_bandera(colores: List[dict]) -> Dict[str, str]:
    cols = [c for c in (colores or []) if c.get("hex")]
    # descartar mezclas: poca área y muy cerca de algún color con más área
    limpios = []
    for c in cols:
        if c.get("area", 1) < 0.08 and any(_distancia(c["hex"], o["hex"]) < 140 for o in limpios):
            continue
        limpios.append(c)
    hexes = [c["hex"] for c in limpios] or ["#1f4fa3", "#ffffff"]
    saturados = [h for h in hexes if saturacion(h) > 0.3 and luminancia(h) < 0.85]
    dominante = saturados[0] if saturados else hexes[0]
    if luminancia(dominante) > 0.85:          # bandera casi toda blanca (Japón): el color protagonista es el otro
        dominante = next((h for h in hexes if h != dominante), "#bb002c")
    resto = [h for h in hexes if h != dominante and _distancia(h, dominante) > 120]
    acento_sat = [h for h in resto if saturacion(h) > 0.3]
    acento = acento_sat[0] if acento_sat else (resto[0] if resto else ORO)
    if luminancia(acento) > 0.85:             # el acento no puede ser blanco: se usa oro como en tantos pósters
        acento = acento_sat[0] if acento_sat else ORO
    claro = next((h for h in hexes if luminancia(h) > 0.8), CREMA)
    oscuro = oscurecer(dominante, 0.32) if luminancia(dominante) > 0.02 else TINTA
    return {
        "dominante": dominante, "acento": acento, "claro": claro, "oscuro": oscuro,
        "dominante_claro": aclarar(dominante, 0.55), "dominante_oscuro": oscurecer(dominante, 0.62),
        "acento_oscuro": oscurecer(acento, 0.62), "crema": CREMA, "tinta": TINTA, "oro": ORO,
        "bandera": hexes,
    }
