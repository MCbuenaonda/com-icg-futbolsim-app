"""
Paleta de un estadio a partir de los colores REALES de la bandera (paises.colores: [{hex, area}]), en 3 roles:
  principal   estructura y cubierta (el color de más área que se lea sobre el fondo oscuro)
  secundario  gradas, rellenos y franjas
  detalle     remates, pantallas, banderines
Los colores muy oscuros se aclaran (contraste con el fondo #141c2e) y el blanco/gris queda como detalle. Si la
bandera tiene un solo color fuerte, el secundario es una variación de su tono.
"""
import colorsys

FONDO = (0x14, 0x1C, 0x2E)


def _rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb) -> str:
    return "#" + "".join(f"{max(0, min(255, int(round(c)))):02x}" for c in rgb)


def _lum(rgb) -> float:
    def canal(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (canal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def legible(h: str, minimo: float = 4.6) -> str:
    """Aclara el color (misma tonalidad) hasta que contraste con el fondo oscuro."""
    r, g, b = (c / 255 for c in _rgb(h))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    for _ in range(30):
        rgb = tuple(c * 255 for c in colorsys.hls_to_rgb(hh, ll, ss))
        if contraste(rgb, FONDO) >= minimo:
            return _hex(rgb)
        ll = min(0.92, ll + 0.04)
    return _hex(tuple(c * 255 for c in colorsys.hls_to_rgb(hh, ll, ss)))


def _saturacion(h: str) -> float:
    r, g, b = (c / 255 for c in _rgb(h))
    return colorsys.rgb_to_hls(r, g, b)[2]


def _girar(h: str, grados: float, luz: float = 0.0) -> str:
    r, g, b = (c / 255 for c in _rgb(h))
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return _hex(tuple(c * 255 for c in colorsys.hls_to_rgb((hh + grados / 360) % 1, max(0.0, min(1.0, ll + luz)), ss)))


def paleta(colores: list) -> dict:
    """{principal, secundario, detalle} desde paises.colores (lista [{hex, area}] o de hex)."""
    lista = [c["hex"] if isinstance(c, dict) else c for c in sorted(colores or [], key=lambda c: -(c.get("area", 0) if isinstance(c, dict) else 0))]
    fuertes = [h for h in lista if _saturacion(h) >= 0.25]
    neutros = [h for h in lista if _saturacion(h) < 0.25]
    if not fuertes:
        fuertes = ["#3b82f6"]
    principal = legible(fuertes[0])
    secundario = legible(fuertes[1]) if len(fuertes) > 1 else legible(_girar(fuertes[0], 0, 0.18))
    if len(fuertes) > 2:
        detalle = legible(fuertes[2])
    elif neutros:
        detalle = legible(neutros[0], 6.0)
    else:
        detalle = "#f8fafc"
    return {"principal": principal, "secundario": secundario, "detalle": detalle}


def invertir(p: dict) -> dict:
    """Variante (para países con más ciudades que diseños): intercambia principal y secundario."""
    return {"principal": p["secundario"], "secundario": p["principal"], "detalle": p["detalle"]}
