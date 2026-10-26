"""
Compositor de logos de marca: 8 arquetipos con siluetas distintas, para que dos marcas no se confundan ni a 16 px.

    wordmark    solo tipografía con un detalle (inicial de color, subrayado, barra, punto)
    monograma   1-2 iniciales grandes (anillo, cuadrado redondeado o entrelazadas)
    lateral     símbolo + nombre al costado
    apilado     símbolo arriba + nombre abajo
    emblema     forma cerrada rellena (círculo, hexágono, diamante con banda, octógono, banderín, cuadrado)
    sello       sello circular con el nombre en arco
    etiqueta    píldora rellena con el símbolo en un círculo y el nombre
    movimiento  banda inclinada con el nombre en itálica y estelas de velocidad

componer(diseno) -> svg. `diseno` lo decide generar_marcas.py (qué arquetipo, símbolo, fuente, paleta y variante
le toca a cada marca, sin repetir); acá solo se dibuja. Los colores se ajustan para leerse sobre el fondo oscuro
de la app (#111c2e).
"""
import math
from xml.sax.saxutils import escape

from logos import simbolos
from logos.color import FONDO, OSCURO, contraste, girar_tono, legible, luminancia, mezclar, tinta_sobre  # noqa: F401
from logos.texto import fuente, medir, texto_en_arco, trazo



# --- piezas ----------------------------------------------------------------------------------------
def _caso(nombre, caso):
    return nombre.upper() if caso == "mayus" else nombre.lower() if caso == "minus" else nombre


def _texto(t, f, tam, x, base, color, espaciado=0.0, inclinacion=0.0, ancla="inicio"):
    d, ancho, alto = trazo(t, f, tam, x, base, espaciado, inclinacion, ancla)
    return f'<path d="{d}" fill="{color}"/>', ancho, alto


def _ajustar(t, f, tam, ancho_max, espaciado=0.0):
    while tam > 10 and medir(t, f, tam, espaciado) > ancho_max:
        tam -= 1
    return tam


def _simbolo(nombre, c1, c2, x, y, tam, semilla):
    return f'<g transform="translate({x:.1f} {y:.1f}) scale({tam / 100:.3f})">{simbolos.dibujar(nombre, c1, c2, semilla)}</g>'


def _iniciales(nombre):
    palabras = [p for p in nombre.replace("&", " ").split() if p[0].isalpha()]
    if len(palabras) >= 2:
        return (palabras[0][0] + palabras[1][0]).upper()
    return palabras[0][0].upper()


def _poli(pts):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def _regular(n, r, cx, cy, giro=-90):
    return [(cx + r * math.cos(math.radians(giro + i * 360 / n)), cy + r * math.sin(math.radians(giro + i * 360 / n))) for i in range(n)]


# --- arquetipos (devuelven cuerpo, ancho, alto) ---------------------------------------------------------
def wordmark(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    t = _caso(d["nombre"], d["caso"])
    tam, esp = 120, d.get("espaciado", 2)
    c1, ac = d["c1"], d["acento"]
    variante = d["variante"] % 4
    x0, base = 30, 140
    if variante == 0:   # inicial de otro color
        p1, a1, _ = _texto(t[0], f, tam, x0, base, ac, inclinacion=d.get("inclinacion", 0))
        p2, a2, _ = _texto(t[1:], f, tam, x0 + a1 + esp, base, c1, esp, d.get("inclinacion", 0))
        ancho = a1 + esp + a2
        cuerpo = p1 + p2
    else:
        cuerpo, ancho, alto = _texto(t, f, tam, x0, base, c1, esp, d.get("inclinacion", 0))
        if variante == 1:   # subrayado en curva
            cuerpo += (f'<path d="M{x0 + 6} {base + 24} Q{x0 + ancho * .5} {base + 46} {x0 + ancho - 4} {base + 16}" fill="none" '
                       f'stroke="{ac}" stroke-width="10" stroke-linecap="round"/>')
        elif variante == 2:  # barra vertical antes del nombre
            cuerpo = f'<rect x="{x0}" y="{base - alto}" width="14" height="{alto:.1f}" fill="{ac}"/>' + _texto(t, f, tam, x0 + 30, base, c1, esp, d.get("inclinacion", 0))[0]
            ancho += 30
        else:               # punto final de acento
            cuerpo += f'<circle cx="{x0 + ancho + 18:.1f}" cy="{base - 9}" r="11" fill="{ac}"/>'
            ancho += 32
    return cuerpo, x0 * 2 + ancho, 190


def monograma(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    ini = _iniciales(d["nombre"])
    c1, ac = d["c1"], d["acento"]
    variante = d["variante"] % 3
    if variante == 0:   # anillo grueso
        tam = _ajustar(ini, f, 170, 170, 2)
        texto = _texto(ini, f, tam, 160, 160 + f.mayus * tam / f.upm / 2, c1, 2, ancla="medio")[0]
        return (f'<circle cx="160" cy="160" r="138" fill="none" stroke="{c1}" stroke-width="16"/>'
                f'<path d="{_arco_d(160, 160, 138, -60, 30)}" fill="none" stroke="{ac}" stroke-width="16"/>' + texto, 320, 320)
    if variante == 1:   # cuadrado redondeado relleno
        tinta = tinta_sobre(d["c1_base"])
        tam = _ajustar(ini, f, 180, 200, 2)
        texto = _texto(ini, f, tam, 160, 160 + f.mayus * tam / f.upm / 2, tinta, 2, ancla="medio")[0]
        return (f'<rect x="20" y="20" width="280" height="280" rx="64" fill="{d["c1_base"]}"/>'
                f'<rect x="20" y="246" width="280" height="54" rx="0" fill="{d["c2_sobre"]}" clip-path="url(#r{d["slug"]})"/>'
                f'<clipPath id="r{d["slug"]}"><rect x="20" y="20" width="280" height="280" rx="64"/></clipPath>' + texto, 320, 320)
    # entrelazadas: la segunda letra desplazada y de otro color
    a = ini[0]
    b = ini[1] if len(ini) > 1 else d["nombre"][1].upper()
    tam = 210
    pa = _texto(a, f, tam, 128, 250, c1, ancla="medio")[0]
    pb = _texto(b, f, tam, 196, 250, ac, ancla="medio")[0]
    return f'<g opacity=".92">{pa}</g>{pb}', 320, 300


def _arco_d(cx, cy, r, a0, a1):
    x0, y0 = cx + r * math.cos(math.radians(a0)), cy + r * math.sin(math.radians(a0))
    x1, y1 = cx + r * math.cos(math.radians(a1)), cy + r * math.sin(math.radians(a1))
    return f"M{x0:.1f} {y0:.1f} A{r} {r} 0 {1 if (a1 - a0) % 360 > 180 else 0} 1 {x1:.1f} {y1:.1f}"


def lateral(d):
    f = fuente(d["fuente"], d.get("peso", 700))
    t = _caso(d["nombre"], d["caso"])
    simb = _simbolo(d["simbolo"], d["c1"], d["acento"], 20, 20, 150, d["semilla"])
    tam = 96
    p, ancho, alto = _texto(t, f, tam, 196, 95 + f.mayus * tam / f.upm / 2, d["c1"] if d["variante"] % 2 else "#ffffff",
                            d.get("espaciado", 0), d.get("inclinacion", 0))
    divisor = f'<rect x="184" y="40" width="4" height="110" rx="2" fill="{d["acento"]}" opacity=".7"/>' if d["variante"] % 3 == 0 else ""
    if divisor:
        p = p.replace("<path ", '<path transform="translate(14 0)" ', 1)
        ancho += 14
    return simb + divisor + p, 196 + ancho + 24, 190


def apilado(d):
    f = fuente(d["fuente"], d.get("peso", 700))
    t = _caso(d["nombre"], d["caso"])
    esp = d.get("espaciado", 4)
    tam = _ajustar(t, f, 76, 460, esp)
    ancho = medir(t, f, tam, esp)
    w = max(260, ancho + 40)
    simb = _simbolo(d["simbolo"], d["c1"], d["acento"], w / 2 - 85, 16, 170, d["semilla"])
    p = _texto(t, f, tam, w / 2, 268, "#ffffff" if d["variante"] % 2 else d["c1"], esp, d.get("inclinacion", 0), "medio")[0]
    return simb + p, w, 300


def emblema(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    t = _caso(d["nombre"], "mayus" if d["caso"] != "minus" else "minus")
    relleno, tinta, c2s = d["c1_base"], tinta_sobre(d["c1_base"]), d["c2_sobre"]
    forma = d["variante"] % 6
    cx, cy = 160, 160
    if forma == 0:
        caja = f'<circle cx="{cx}" cy="{cy}" r="148" fill="{relleno}"/><circle cx="{cx}" cy="{cy}" r="132" fill="none" stroke="{c2s}" stroke-width="4"/>'
        ancho_txt, base, sy = 184, 232, 54
    elif forma == 1:
        caja = f'<polygon points="{_poli(_regular(6, 152, cx, cy, -90))}" fill="{relleno}"/>'
        ancho_txt, base, sy = 200, 236, 54
    elif forma == 2:   # diamante con banda horizontal
        caja = (f'<polygon points="{_poli(_regular(4, 156, cx, cy, -90))}" fill="{relleno}"/>'
                f'<rect x="6" y="196" width="308" height="62" rx="8" fill="{c2s}"/>')
        tinta_banda = tinta_sobre(c2s)
        tam = _ajustar(t, f, 50, 270, 2)
        txt = _texto(t, f, tam, cx, 227 + f.mayus * tam / f.upm / 2, tinta_banda, 2, ancla="medio")[0]
        simb = _simbolo(d["simbolo"], tinta, c2s, cx - 52, 66, 104, d["semilla"])
        return caja + simb + txt, 320, 320
    elif forma == 3:
        caja = f'<polygon points="{_poli(_regular(8, 154, cx, cy, -67.5))}" fill="{relleno}"/>'
        ancho_txt, base, sy = 220, 236, 52
    elif forma == 4:   # banderín vertical (punta abajo)
        caja = f'<path d="M30 14 H290 V220 L160 310 L30 220 Z" fill="{relleno}"/><rect x="30" y="14" width="260" height="16" fill="{c2s}"/>'
        ancho_txt, base, sy = 224, 218, 50
    else:              # cuadrado con esquina cortada
        caja = f'<polygon points="22,22 248,22 298,72 298,298 72,298 22,248" fill="{relleno}"/>'
        ancho_txt, base, sy = 230, 252, 52
    tam = _ajustar(t, f, 50, ancho_txt, 2)
    txt = _texto(t, f, tam, cx, base, tinta, 2, ancla="medio")[0]
    simb = _simbolo(d["simbolo"], tinta, c2s, cx - 62, sy, 124, d["semilla"])
    return caja + simb + txt, 320, 320


def sello(d):
    f = fuente(d["fuente"], d.get("peso", 700))
    t = _caso(d["nombre"], "mayus")
    c1, ac = d["c1"], d["acento"]
    cx = cy = 160
    tam = 32
    while tam > 16 and medir(t, f, tam, 3) > 2 * math.pi * 122 * 0.42:
        tam -= 1
    arriba = texto_en_arco(t, f, tam, cx, cy, 122, -90, 3)
    abajo = texto_en_arco(d["rubro_corto"].upper(), f, 22, cx, cy, 124, 90, 4, abajo=True)
    lleno = d["variante"] % 2 == 0
    fondo = f'<circle cx="{cx}" cy="{cy}" r="152" fill="{d["c1_base"]}"/>' if lleno else ""
    tinta = tinta_sobre(d["c1_base"]) if lleno else c1
    acento = d["c2_sobre"] if lleno else ac
    return (fondo
            + f'<circle cx="{cx}" cy="{cy}" r="152" fill="none" stroke="{acento}" stroke-width="8"/>'
            + f'<circle cx="{cx}" cy="{cy}" r="96" fill="none" stroke="{tinta}" stroke-width="3"/>'
            + f'<g fill="{tinta}">{arriba}{abajo}</g>'
            + f'<circle cx="{cx - 128}" cy="{cy}" r="6" fill="{acento}"/><circle cx="{cx + 128}" cy="{cy}" r="6" fill="{acento}"/>'
            + _simbolo(d["simbolo"], tinta, acento, cx - 62, cy - 62, 124, d["semilla"]), 320, 320)


def etiqueta(d):
    f = fuente(d["fuente"], d.get("peso", 700))
    t = _caso(d["nombre"], d["caso"])
    relleno, tinta, c2s = d["c1_base"], tinta_sobre(d["c1_base"]), d["c2_sobre"]
    tam = 76
    ancho = medir(t, f, tam, d.get("espaciado", 1))
    w = 176 + ancho + 56
    circulo = f'<circle cx="92" cy="90" r="62" fill="{tinta}"/>'
    simb = _simbolo(d["simbolo"], relleno, c2s if contraste(c2s, tinta) > 1.6 else relleno, 50, 48, 84, d["semilla"])
    txt = _texto(t, f, tam, 176, 90 + f.mayus * tam / f.upm / 2, tinta, d.get("espaciado", 1), d.get("inclinacion", 0))[0]
    return f'<rect x="10" y="10" width="{w - 20:.1f}" height="160" rx="80" fill="{relleno}"/>' + circulo + simb + txt, w, 180


def movimiento(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    t = _caso(d["nombre"], "mayus" if d["caso"] == "mayus" else d["caso"])
    relleno, tinta, ac = d["c1_base"], tinta_sobre(d["c1_base"]), d["acento"]
    tam = 92
    ancho = medir(t, f, tam, d.get("espaciado", 2))
    x0, sesgo = 120, 40
    w = x0 + ancho + 90
    banda = f'<polygon points="{_poli([(x0 - 10 + sesgo, 22), (w - 10, 22), (w - 10 - sesgo, 168), (x0 - 10, 168)])}" fill="{relleno}"/>'
    estelas = "".join(f'<polygon points="{_poli([(x0 - 40 - i * 34 + sesgo * .6, 40 + i * 40), (x0 - 22 - i * 8 + sesgo * .6, 40 + i * 40), (x0 - 30 - i * 8, 66 + i * 40), (x0 - 48 - i * 34, 66 + i * 40)])}" fill="{ac}"/>'
                      for i in range(3))
    txt = _texto(t, f, tam, x0 + 24, 95 + f.mayus * tam / f.upm / 2, tinta, d.get("espaciado", 2), 0.22)[0]
    return estelas + banda + txt, w, 190


ARQUETIPOS = {"wordmark": wordmark, "monograma": monograma, "lateral": lateral, "apilado": apilado,
              "emblema": emblema, "sello": sello, "etiqueta": etiqueta, "movimiento": movimiento}


def preparar_colores(d):
    """c1 / acento legibles sobre fondo oscuro; c1_base y c2_sobre para formas rellenas."""
    c1, c2 = d["paleta"]
    d["c1_base"] = c1
    d["c1"] = legible(c1)
    d["acento"] = c2 if contraste(c2, FONDO) >= 3 else legible(mezclar(c1, "#ffffff", 0.55))
    d["c2_sobre"] = c2 if contraste(c2, c1) >= 1.8 else tinta_sobre(c1)
    return d


def componer(d: dict) -> str:
    preparar_colores(d)
    cuerpo, w, h = ARQUETIPOS[d["arquetipo"]](d)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}">'
            f'<title>{escape(d["nombre"])}</title>{cuerpo}</svg>\n')
