"""
Logos de televisoras: 8 arquetipos propios de la TV + 4 de las marcas (logos/componer.py), para que las 3 cadenas de un
país nunca se parezcan entre sí ni a 16 px.

    numeral     el número del canal (o la inicial) en una figura rellena, con el nombre al costado
    pantalla    el nombre dentro de una pantalla redondeada con dos antenas
    ondas       punto emisor con ondas de transmisión y el nombre al costado
    lente       lente de cámara (anillos con brillo) sobre el nombre
    play        triángulo de reproducción (suelto o en un círculo) y el nombre
    franjas     barras de color inclinadas (carta de ajuste) y el nombre
    arcos       arcos concéntricos tipo arcoíris sobre el nombre
    visor       iniciales en el visor de una cámara (esquinas + punto de grabación) y el nombre debajo
    + wordmark, emblema, sello, etiqueta de logos/componer.py

componer(diseno) -> svg; el diseño lo decide generar_televisoras.py.
"""
import re
from xml.sax.saxutils import escape

from logos import componer as C
from logos.color import mezclar, tinta_sobre
from logos.texto import fuente, medir


def _numero_o_inicial(d):
    m = re.search(r"\d+", d["nombre"])
    return m.group(0) if m else C._iniciales(d["nombre"])[:1]


def _nombre_sin_numero(d):
    """El nombre para el texto del logo: si el número ya va en la figura, no se repite."""
    t = re.sub(r"\s*\b\d+\b\s*", " ", d["nombre"]).strip() if d.get("arquetipo") == "numeral" else d["nombre"]
    return C._caso(t or d["nombre"], d["caso"])


def numeral(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    num = _numero_o_inicial(d)
    relleno, tinta, ac = d["c1_base"], tinta_sobre(d["c1_base"]), d["acento"]
    forma = d["variante"] % 3
    if forma == 0:
        caja = f'<circle cx="95" cy="95" r="80" fill="{relleno}"/><circle cx="95" cy="95" r="80" fill="none" stroke="{ac}" stroke-width="8"/>'
    elif forma == 1:
        caja = f'<rect x="15" y="15" width="160" height="160" rx="40" fill="{relleno}"/><rect x="15" y="140" width="160" height="35" fill="{d["c2_sobre"]}" clip-path="url(#n{d["slug"]})"/><clipPath id="n{d["slug"]}"><rect x="15" y="15" width="160" height="160" rx="40"/></clipPath>'
    else:   # escudo
        caja = f'<path d="M20 22 H170 V110 Q170 160 95 182 Q20 160 20 110 Z" fill="{relleno}"/><path d="M20 22 H170 V40 H20 Z" fill="{ac}"/>'
    tam = C._ajustar(num, f, 120, 120, 0)
    cifra = C._texto(num, f, tam, 95, 95 + f.mayus * tam / f.upm / 2, tinta, 0, ancla="medio")[0]
    t = _nombre_sin_numero(d)
    tam_t = C._ajustar(t, f, 80, 560, d.get("espaciado", 1))
    p, ancho, _ = C._texto(t, f, tam_t, 200, 95 + f.mayus * tam_t / f.upm / 2, d["c1"], d.get("espaciado", 1), d.get("inclinacion", 0))
    return caja + cifra + p, 200 + ancho + 30, 195


def pantalla(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    t = C._caso(d["nombre"], d["caso"])
    tam = C._ajustar(t, f, 74, 520, d.get("espaciado", 2))
    ancho = medir(t, f, tam, d.get("espaciado", 2))
    w = ancho + 90
    c1, ac = d["c1"], d["acento"]
    lleno = d["variante"] % 2 == 0
    marco = (f'<rect x="20" y="60" width="{w:.1f}" height="140" rx="34" fill="{d["c1_base"]}"/>' if lleno else
             f'<rect x="20" y="60" width="{w:.1f}" height="140" rx="34" fill="none" stroke="{c1}" stroke-width="12"/>')
    tinta = tinta_sobre(d["c1_base"]) if lleno else "#ffffff"
    mx = 20 + w / 2
    antenas = (f'<path d="M{mx - 8:.1f} 58 L{mx - 52:.1f} 14 M{mx + 8:.1f} 58 L{mx + 48:.1f} 20" stroke="{ac}" stroke-width="9" stroke-linecap="round"/>'
               f'<circle cx="{mx - 52:.1f}" cy="14" r="9" fill="{ac}"/><circle cx="{mx + 48:.1f}" cy="20" r="9" fill="{ac}"/>')
    txt = C._texto(t, f, tam, mx, 130 + f.mayus * tam / f.upm / 2, tinta, d.get("espaciado", 2), d.get("inclinacion", 0), "medio")[0]
    punto = f'<circle cx="{20 + w - 26:.1f}" cy="86" r="8" fill="{ac}"/>'
    return antenas + marco + txt + punto, w + 40, 220


def ondas(d):
    f = fuente(d["fuente"], d.get("peso", 700))
    t = C._caso(d["nombre"], d["caso"])
    c1, ac = d["c1"], d["acento"]
    giro = (d["variante"] % 3) * 1
    centro = (60, 120)
    arcos = []
    for i, r in enumerate((34, 62, 90)):
        color = ac if (i + giro) % 2 == 0 else c1
        arcos.append(f'<path d="{C._arco_d(centro[0], centro[1], r, -62, 62)}" fill="none" stroke="{color}" stroke-width="13" stroke-linecap="round"/>')
    emisor = f'<circle cx="{centro[0]}" cy="{centro[1]}" r="17" fill="{c1}"/>'
    tam = 92
    p, ancho, _ = C._texto(t, f, tam, 178, 95 + f.mayus * tam / f.upm / 2, "#ffffff" if d["variante"] % 2 else c1,
                           d.get("espaciado", 0), d.get("inclinacion", 0))
    return f'<g transform="translate(0 -25)">{emisor}{"".join(arcos)}</g>' + p, 178 + ancho + 26, 190


def lente(d):
    f = fuente(d["fuente"], d.get("peso", 700))
    t = C._caso(d["nombre"], d["caso"])
    esp = d.get("espaciado", 4)
    tam = C._ajustar(t, f, 72, 460, esp)
    ancho = medir(t, f, tam, esp)
    w = max(260, ancho + 40)
    cx, cy = w / 2, 100
    c1, ac, base = d["c1"], d["acento"], d["c1_base"]
    lente_svg = (f'<circle cx="{cx:.1f}" cy="{cy}" r="86" fill="none" stroke="{c1}" stroke-width="12"/>'
                 f'<circle cx="{cx:.1f}" cy="{cy}" r="62" fill="{base}"/>'
                 f'<circle cx="{cx:.1f}" cy="{cy}" r="34" fill="{mezclar(base, "#000000", 0.45)}"/>'
                 f'<circle cx="{cx:.1f}" cy="{cy}" r="14" fill="{ac}"/>'
                 f'<path d="{C._arco_d(cx, cy, 48, 200, 250)}" fill="none" stroke="#ffffff" stroke-width="8" stroke-linecap="round" opacity=".85"/>')
    p = C._texto(t, f, tam, w / 2, 262, "#ffffff" if d["variante"] % 2 else c1, esp, d.get("inclinacion", 0), "medio")[0]
    return lente_svg + p, w, 290


def play(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    t = C._caso(d["nombre"], d["caso"])
    base, tinta, ac = d["c1_base"], tinta_sobre(d["c1_base"]), d["acento"]
    if d["variante"] % 2 == 0:   # triángulo suelto con borde redondeado
        figura = (f'<path d="M30 28 Q30 12 46 20 L160 84 Q174 92 160 100 L46 164 Q30 172 30 156 Z" fill="{base}"/>'
                  f'<path d="M58 62 L120 92 L58 122 Z" fill="{ac}"/>')
    else:                        # triángulo dentro de un círculo
        figura = (f'<circle cx="95" cy="92" r="78" fill="{base}"/>'
                  f'<path d="M74 52 L134 92 L74 132 Z" fill="{tinta}"/><circle cx="95" cy="92" r="78" fill="none" stroke="{ac}" stroke-width="6"/>')
    tam = 88
    p, ancho, _ = C._texto(t, f, tam, 196, 92 + f.mayus * tam / f.upm / 2, d["c1"], d.get("espaciado", 1), d.get("inclinacion", 0))
    return figura + p, 196 + ancho + 26, 190


def franjas(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    t = C._caso(d["nombre"], d["caso"])
    base, ac = d["c1_base"], d["acento"]
    colores = [base, ac, mezclar(base, "#ffffff", 0.45), mezclar(ac, base, 0.5)]
    tam = 90
    ancho = medir(t, f, tam, d.get("espaciado", 1))
    if d["variante"] % 2 == 0:   # barras inclinadas a la izquierda
        barras = "".join(f'<polygon points="{C._poli([(40 + i * 30, 160), (70 + i * 30, 30), (92 + i * 30, 30), (62 + i * 30, 160)])}" fill="{c}"/>'
                         for i, c in enumerate(colores))
        p = C._texto(t, f, tam, 196, 95 + f.mayus * tam / f.upm / 2, d["c1"], d.get("espaciado", 1), d.get("inclinacion", 0))[0]
        return barras + p, 196 + ancho + 26, 190
    # barras horizontales bajo el nombre
    w = ancho + 60
    p = C._texto(t, f, tam, 30, 110, d["c1"], d.get("espaciado", 1), d.get("inclinacion", 0))[0]
    paso = ancho / len(colores)
    barras = "".join(f'<rect x="{30 + i * paso:.1f}" y="134" width="{paso - 6:.1f}" height="22" rx="4" fill="{c}"/>' for i, c in enumerate(colores))
    return p + barras, w, 180


def arcos(d):
    f = fuente(d["fuente"], d.get("peso", 700))
    t = C._caso(d["nombre"], d["caso"])
    esp = d.get("espaciado", 3)
    tam = C._ajustar(t, f, 74, 480, esp)
    ancho = medir(t, f, tam, esp)
    w = max(280, ancho + 40)
    cx = w / 2
    base, ac = d["c1_base"], d["acento"]
    colores = [d["c1"], ac, mezclar(d["c1"], "#ffffff", 0.4)] if d["variante"] % 2 == 0 else [ac, d["c1"], mezclar(ac, "#ffffff", 0.35)]
    arcos_svg = "".join(f'<path d="{C._arco_d(cx, 150, r, 180, 360)}" fill="none" stroke="{c}" stroke-width="16" stroke-linecap="round"/>'
                        for r, c in zip((118, 92, 66), colores))
    p = C._texto(t, f, tam, cx, 232, "#ffffff" if d["variante"] % 3 == 0 else d["c1"], esp, d.get("inclinacion", 0), "medio")[0]
    return arcos_svg + p, w, 260


def visor(d):
    f = fuente(d["fuente"], d.get("peso", 800))
    ini = C._iniciales(d["nombre"])
    c1, ac = d["c1"], d["acento"]
    lado, x0, y0, largo = 200, 60, 20, 48
    esquinas = "".join(f'<path d="{p}" fill="none" stroke="{c1}" stroke-width="12" stroke-linecap="round"/>' for p in (
        f"M{x0} {y0 + largo} V{y0} H{x0 + largo}", f"M{x0 + lado - largo} {y0} H{x0 + lado} V{y0 + largo}",
        f"M{x0} {y0 + lado - largo} V{y0 + lado} H{x0 + largo}", f"M{x0 + lado - largo} {y0 + lado} H{x0 + lado} V{y0 + lado - largo}"))
    tam = C._ajustar(ini, f, 130, 150, 2)
    letras = C._texto(ini, f, tam, x0 + lado / 2, y0 + lado / 2 + f.mayus * tam / f.upm / 2, ac if d["variante"] % 2 else "#ffffff", 2, ancla="medio")[0]
    rec = f'<circle cx="{x0 + lado - 26}" cy="{y0 + 28}" r="10" fill="#ef4444"/>'
    t = C._caso(d["nombre"], d["caso"])
    tam_t = C._ajustar(t, f, 46, 300, d.get("espaciado", 3))
    w = max(320, medir(t, f, tam_t, d.get("espaciado", 3)) + 40)
    desplazar = (w - 320) / 2
    nombre = C._texto(t, f, tam_t, w / 2, 290, c1, d.get("espaciado", 3), 0, "medio")[0]
    return f'<g transform="translate({desplazar:.1f} 0)">{esquinas}{letras}{rec}</g>' + nombre, w, 310


ARQUETIPOS_TV = {"numeral": numeral, "pantalla": pantalla, "ondas": ondas, "lente": lente, "play": play,
                 "franjas": franjas, "arcos": arcos, "visor": visor}
ARQUETIPOS_MARCA = ("wordmark", "emblema", "sello", "etiqueta")
TODOS = list(ARQUETIPOS_TV) + list(ARQUETIPOS_MARCA)


def componer(d: dict) -> str:
    C.preparar_colores(d)
    if d["arquetipo"] in ARQUETIPOS_TV:
        cuerpo, w, h = ARQUETIPOS_TV[d["arquetipo"]](d)
    else:
        d.setdefault("rubro_corto", "Televisión")
        cuerpo, w, h = C.ARQUETIPOS[d["arquetipo"]](d)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:.0f} {h:.0f}" width="{w:.0f}" height="{h:.0f}">'
            f'<title>{escape(d["nombre"])}</title>{cuerpo}</svg>\n')
