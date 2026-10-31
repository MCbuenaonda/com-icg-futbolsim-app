"""
Logos (cabeceras) de los medios de comunicación: 4 arquetipos con siluetas distintas.

    periodico   la cabecera clásica: el nombre en serifa con doble filete arriba y abajo
    bloque      el nombre en blanco sobre un rectángulo de color con una pestaña de acento
    deportivo   paralelogramo inclinado con el nombre en itálica y estelas de velocidad
    sello       sello redondo con las iniciales y el nombre al costado

componer(d) -> svg; el diseño (arquetipo, fuente, paleta) lo decide generar_logos_medios.py. Los colores se ajustan para leerse
sobre el fondo oscuro de la app (reusa logos/color.py).
"""
from xml.sax.saxutils import escape

from logos import componer as C
from logos.color import FONDO, contraste, legible, mezclar, tinta_sobre
from logos.texto import fuente, medir, trazo


def _t(t, f, tam, x, base, color, esp=0.0, incl=0.0, ancla="inicio"):
    d, ancho, alto = trazo(t, f, tam, x, base, esp, incl, ancla)
    return f'<path d="{d}" fill="{color}"/>', ancho, alto


def periodico(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    tam = C._ajustar(d["nombre_c"], f, 110, 640, d["espaciado"])
    cuerpo_t, ancho, alto = _t(d["nombre_c"], f, tam, 0, 0, d["c1"], d["espaciado"])
    w = max(ancho + 80, 220)
    base = 100 + alto * 0.5
    x0 = (w - ancho) / 2
    t, _, _ = _t(d["nombre_c"], f, tam, x0, base, d["c1"], d["espaciado"])
    ac = d["acento"]
    filetes = (f'<rect x="30" y="34" width="{w - 60:.0f}" height="7" fill="{ac}"/><rect x="30" y="47" width="{w - 60:.0f}" height="2.5" fill="{ac}"/>'
               f'<rect x="30" y="{base + 24:.0f}" width="{w - 60:.0f}" height="2.5" fill="{ac}"/><rect x="30" y="{base + 33:.0f}" width="{w - 60:.0f}" height="7" fill="{ac}"/>')
    return filetes + t, w, base + 70


def bloque(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    tam = C._ajustar(d["nombre_c"], f, 96, 620, d["espaciado"])
    _, ancho, alto = _t(d["nombre_c"], f, tam, 0, 0, "#000", d["espaciado"])
    w, h = ancho + 130, alto + 90
    tinta = tinta_sobre(d["c1_base"])
    t, _, _ = _t(d["nombre_c"], f, tam, 78, h / 2 + alto / 2, tinta, d["espaciado"])
    return (f'<rect x="10" y="10" width="{w - 20:.0f}" height="{h - 20:.0f}" rx="16" fill="{d["c1_base"]}"/>'
            f'<rect x="10" y="10" width="40" height="{h - 20:.0f}" rx="16" fill="{d["acento"]}"/><rect x="34" y="10" width="16" height="{h - 20:.0f}" fill="{d["acento"]}"/>') + t, w, h


def deportivo(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    tam = C._ajustar(d["nombre_c"], f, 100, 600, d["espaciado"])
    _, ancho, alto = _t(d["nombre_c"], f, tam, 0, 0, "#000", d["espaciado"], 0.2)
    h = alto + 80
    w = ancho + 190
    sk = 34
    tinta = tinta_sobre(d["c1_base"])
    t, _, _ = _t(d["nombre_c"], f, tam, 108, h / 2 + alto / 2, tinta, d["espaciado"], 0.2)
    forma = f'<polygon points="{70 + sk},12 {w - 10:.0f},12 {w - 10 - sk:.0f},{h - 12:.0f} 70,{h - 12:.0f}" fill="{d["c1_base"]}"/>'
    estelas = "".join(f'<polygon points="{10 + i * 14 + sk * (1 - k / 3)},{12 + k * (h - 24) / 3:.0f} {40 + i * 14 + sk * (1 - k / 3)},{12 + k * (h - 24) / 3:.0f} {30 + i * 14 + sk * (1 - (k + 1) / 3)},{12 + (k + 1) * (h - 24) / 3:.0f} {i * 14 + sk * (1 - (k + 1) / 3)},{12 + (k + 1) * (h - 24) / 3:.0f}" fill="{d["acento"]}"/>'
                      for i, k in ((0, 0), (1, 1), (0, 2)))
    return estelas + forma + t, w, h


def sello(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    ini = C._iniciales(d["nombre"])
    fi = fuente("playfair" if d["fuente"] not in ("anton", "bebas", "teko") else d["fuente"], 800)
    tam = C._ajustar(d["nombre_c"], f, 90, 560, d["espaciado"])
    _, ancho, alto = _t(d["nombre_c"], f, tam, 0, 0, "#000", d["espaciado"])
    r = 78
    cx, cy = r + 24, r + 24
    ti, ai, _ = _t(ini, fi, 76, 0, 0, "#000")
    ti, _, _ = _t(ini, fi, 76, cx - ai / 2, cy + 27, tinta_sobre(d["c1_base"]))
    t, _, _ = _t(d["nombre_c"], f, tam, 2 * r + 70, cy + alto / 2, d["c1"], d["espaciado"])
    anillo = (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{d["c1_base"]}"/><circle cx="{cx}" cy="{cy}" r="{r - 10}" fill="none" stroke="{d["acento"]}" stroke-width="4"/>')
    return anillo + ti + t, 2 * r + 70 + ancho + 30, 2 * r + 48


ARQUETIPOS = {"periodico": periodico, "bloque": bloque, "deportivo": deportivo, "sello": sello}


def componer(d: dict) -> str:
    c1, c2 = d["paleta"]
    d["c1_base"] = c1
    d["c1"] = legible(c1)
    d["acento"] = c2 if contraste(c2, FONDO) >= 3 else legible(mezclar(c1, "#ffffff", 0.55))
    d["nombre_c"] = C._caso(d["nombre"], d["caso"])
    cuerpo, w, h = ARQUETIPOS[d["arquetipo"]](d)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}">'
            f'<title>{escape(d["nombre"])}</title>{cuerpo}</svg>\n')
