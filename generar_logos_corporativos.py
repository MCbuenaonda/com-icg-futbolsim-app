"""
Logos de los 10 Corporativos Deportivos (config/corporativos.py): un SVG de 512x512 por corporativo, fondo transparente.

Cada uno es un diseño propio con su silueta (ninguno repite forma): se reconocen por el contorno aun a 16 px.
    VESA  monograma «V» con estrellas en arco (clásico, sin contenedor)
    APEX  la «A» es un pico nevado, tipografía extendida
    SGSH  sello circular dorado con texto en arco y halcón de perfil
    CSLS  sol naciente sobre el mar, tipografía redondeada
    IEAC  corona geométrica en un hexágono
    DPST  sello cuadrado tipo hanko con pagoda en líneas
    ASSC  arco (portal) con acacia al atardecer
    PZSG  la «Z» es una ola, wordmark itálico
    CSPG  banderín con palmera y sol
    UIDR  paralelogramo en itálica con volcán y cortes diagonales
Los textos van convertidos a trazos (logos/texto.py, fontTools): el SVG no depende de fuentes instaladas.

Uso (requiere `pip install fonttools brotli`):
    python generar_logos_corporativos.py --muestra [carpeta]   # SVGs + hoja HTML de revisión (fondos y tamaños)
    python generar_logos_corporativos.py --subir [carpeta]     # sube corporativos/<SIGLA>.svg al bucket
Al subir logos nuevos, subir VERSION_IMAGENES['corporativo'] en services/imagenes_pais_service.py.
"""
import math
from xml.sax.saxutils import escape
import os
import subprocess
import sys

from config.corporativos import CORPORATIVOS

CARPETA_BUCKET = "gs://com-icg-mundial/corporativos"
TAM = 512


def _mezclar(hexa: str, otro: str, f: float) -> str:
    a = [int(hexa[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(otro[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * f) for x, y in zip(a, b))


def _oscuro(h, f=0.45):
    return _mezclar(h, "#000000", f)


def _claro(h, f=0.35):
    return _mezclar(h, "#ffffff", f)


def _texto(t, nombre, peso, cx, base, ancho_max, tam_max, color, espaciado=0.0, inclinacion=0.0, extra=""):
    """Texto centrado en cx con la línea de base en 'base', achicado hasta entrar en ancho_max."""
    from logos.texto import fuente, medir, trazo   # fontTools solo hace falta para dibujar (no para --subir)
    f = fuente(nombre, peso)
    tam = tam_max
    while tam > 8 and medir(t, f, tam, espaciado * tam / tam_max) > ancho_max:
        tam -= 1
    d, _, _ = trazo(t, f, tam, cx, base, espaciado * tam / tam_max, inclinacion, "medio")
    return f'<path d="{d}" fill="{color}"{extra}/>'


def _estrella(cx, cy, r, picos=5, interno=0.42, giro=-90):
    pts = []
    for i in range(picos * 2):
        rr = r if i % 2 == 0 else r * interno
        a = math.radians(giro + i * 180 / picos)
        pts.append(f"{cx + rr * math.cos(a):.1f},{cy + rr * math.sin(a):.1f}")
    return " ".join(pts)


def _poli(pts):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


# --- los 10 diseños ------------------------------------------------------------------------------
def vesa(p, a, s):
    estrellas = "".join(
        f'<polygon points="{_estrella(256 + 168 * math.cos(math.radians(g)), 236 + 168 * math.sin(math.radians(g)), 15)}" fill="{a}"/>'
        for g in range(-150, -29, 20))
    return (estrellas
            + f'<polygon points="{_poli([(104, 132), (200, 132), (256, 300), (256, 404), (214, 404)])}" fill="{_claro(p, .15)}"/>'
            + f'<polygon points="{_poli([(408, 132), (312, 132), (256, 300), (256, 404), (298, 404)])}" fill="{_oscuro(p, .25)}"/>'
            + f'<polyline points="160,150 256,360 352,150" fill="none" stroke="{a}" stroke-width="7" stroke-linejoin="miter" opacity=".9"/>'
            + _texto("VESA", "cinzel", 700, 256, 476, 300, 64, "#ffffff", espaciado=22)
            + f'<rect x="150" y="490" width="212" height="4" rx="2" fill="{a}"/>')


def apex(p, a, s):
    return (f'<path d="M256 34 L474 386 H38 Z M256 176 L190 290 H322 Z" fill="{p}" fill-rule="evenodd"/>'
            f'<path d="M256 34 L322 140 L296 126 L272 150 L250 124 L222 146 L200 126 Z" fill="{a}"/>'
            f'<path d="M120 386 L170 306 H342 L392 386 Z" fill="{_oscuro(p, .3)}"/>'
            + _texto("APEX", "michroma", 400, 256, 470, 420, 70, a, espaciado=14))


def sgsh(p, a, s):
    from logos.texto import fuente, texto_en_arco
    halcon = ("M192 376 L192 262 C192 198 238 160 294 160 C338 160 370 184 380 218 L398 246 "
              "C386 250 372 248 362 240 L348 252 C328 264 312 270 300 272 C300 312 312 346 334 376 Z")
    plumas = "".join(f'<path d="M{196 - i * 4} {236 + i * 34} L{130 - i * 6} {214 + i * 38} L{196 - i * 4} {262 + i * 34} Z" fill="{a}"/>'
                     for i in range(3))
    return (f'<circle cx="256" cy="256" r="242" fill="{_oscuro(p, .2)}" stroke="{a}" stroke-width="14"/>'
            f'<circle cx="256" cy="256" r="170" fill="{p}" stroke="{a}" stroke-width="5"/>'
            f'<g fill="{a}">{texto_en_arco("SOVEREIGN GULF", fuente("cinzel", 700), 34, 256, 256, 200, -90, 3)}'
            f'{texto_en_arco("SPORTS HOLDINGS", fuente("cinzel", 700), 30, 256, 256, 200, 90, 3, abajo=True)}</g>'
            f'<polygon points="{_estrella(42, 256, 14, 4, .4)}" fill="{a}"/><polygon points="{_estrella(470, 256, 14, 4, .4)}" fill="{a}"/>'
            f'<path d="{halcon}" fill="{a}"/>{plumas}'
            f'<circle cx="320" cy="208" r="11" fill="{p}"/>'
            f'<path d="M312 222 C308 246 298 262 282 274 L298 272 C312 258 320 242 324 222 Z" fill="{p}"/>'
            f'<path d="M362 240 L380 218" stroke="{p}" stroke-width="4" stroke-linecap="round"/>'
            f'<path d="M222 312 L256 330 L290 312 M222 344 L256 362 L290 344" stroke="{p}" stroke-width="7" fill="none" stroke-linejoin="round"/>')


def csls(p, a, s):
    rayos = "".join(
        f'<polygon points="{256 + 136 * math.cos(math.radians(g - 6)):.1f},{300 + 136 * math.sin(math.radians(g - 6)):.1f} '
        f'{256 + 212 * math.cos(math.radians(g)):.1f},{300 + 212 * math.sin(math.radians(g)):.1f} '
        f'{256 + 136 * math.cos(math.radians(g + 6)):.1f},{300 + 136 * math.sin(math.radians(g + 6)):.1f}" fill="{_claro(p, .1)}"/>'
        for g in range(-165, -14, 25))
    return (rayos
            + f'<path d="M136 300 A120 120 0 0 1 376 300 Z" fill="{p}"/>'
            + f'<path d="M190 300 A66 66 0 0 1 322 300" fill="none" stroke="#ffffff" stroke-opacity=".35" stroke-width="8"/>'
            + f'<path d="M70 326 C120 306 160 346 210 326 S300 306 350 326 S420 346 442 330" fill="none" stroke="{a}" stroke-width="14" stroke-linecap="round"/>'
            + f'<path d="M120 360 C160 344 200 374 240 360 S320 344 392 362" fill="none" stroke="{a}" stroke-width="10" stroke-linecap="round" opacity=".7"/>'
            + _texto("csls", "comfortaa", 700, 256, 468, 300, 92, "#ffffff", espaciado=10))


def ieac(p, a, s):
    hexa = [(256 + 236 * math.cos(math.radians(-90 + i * 60)), 256 + 236 * math.sin(math.radians(-90 + i * 60))) for i in range(6)]
    interior = [(256 + 206 * math.cos(math.radians(-90 + i * 60)), 256 + 206 * math.sin(math.radians(-90 + i * 60))) for i in range(6)]
    corona = [(156, 268), (142, 150), (206, 206), (256, 118), (306, 206), (370, 150), (356, 268)]
    puntas = "".join(f'<circle cx="{x}" cy="{y - 12}" r="13" fill="{a}"/>' for x, y in ((142, 150), (256, 118), (370, 150)))
    return (f'<polygon points="{_poli(hexa)}" fill="{p}" stroke="{a}" stroke-width="12" stroke-linejoin="round"/>'
            f'<polygon points="{_poli(interior)}" fill="none" stroke="{a}" stroke-width="3" opacity=".6"/>'
            f'<polygon points="{_poli(corona)}" fill="{a}"/>{puntas}'
            f'<rect x="152" y="276" width="208" height="20" rx="4" fill="{a}"/>'
            f'<polygon points="{_estrella(256, 230, 18, 4, .4)}" fill="{p}"/>'
            + _texto("IEAC", "oswald", 700, 256, 392, 210, 86, a, espaciado=12))


def dpst(p, a, s):
    techo = lambda y, ancho, alto: (f'<path d="M{256 - ancho} {y} Q{256 - ancho * .55} {y - alto * .3} 256 {y - alto} '
                                    f'Q{256 + ancho * .55} {y - alto * .3} {256 + ancho} {y}" fill="none" stroke="{a}" stroke-width="12" stroke-linecap="round"/>')
    return (f'<rect x="40" y="40" width="432" height="432" rx="46" fill="{p}"/>'
            f'<rect x="66" y="66" width="380" height="380" rx="26" fill="none" stroke="{a}" stroke-width="5"/>'
            f'<line x1="256" y1="84" x2="256" y2="118" stroke="{a}" stroke-width="8" stroke-linecap="round"/>'
            + techo(170, 118, 52) + techo(238, 140, 46) + techo(306, 162, 46)
            + f'<path d="M206 176 V230 M306 176 V230 M188 244 V298 M324 244 V298" stroke="{a}" stroke-width="8"/>'
            + f'<rect x="230" y="256" width="52" height="42" rx="4" fill="{a}"/>'
            + _texto("DPST", "bungee", 400, 256, 408, 300, 70, a, espaciado=8))


def assc(p, a, s):
    arco = "M92 468 V256 A164 164 0 0 1 420 256 V468 Z"
    copa = ("M140 228 C150 206 190 198 220 206 C236 188 276 186 296 202 C326 192 366 202 374 222 "
            "C358 234 330 236 300 232 C280 242 240 244 216 236 C190 242 156 240 140 228 Z")
    return (f'<defs><clipPath id="cASSC"><path d="{arco}"/></clipPath>'
            f'<linearGradient id="gASSC" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{_oscuro(a, .25)}"/>'
            f'<stop offset="1" stop-color="{_claro(a, .3)}"/></linearGradient></defs>'
            f'<g clip-path="url(#cASSC)"><rect x="80" y="80" width="352" height="400" fill="url(#gASSC)"/>'
            f'<circle cx="300" cy="330" r="74" fill="#fde68a"/>'
            f'<path d="M80 352 C170 336 320 340 432 356 V480 H80 Z" fill="{p}"/>'
            f'<path d="{copa}" fill="{_oscuro(p, .55)}"/>'
            f'<path d="M248 360 C250 300 246 268 232 236 M250 300 C266 280 286 260 300 234 M244 272 C226 258 200 246 182 234" '
            f'stroke="{_oscuro(p, .55)}" stroke-width="12" fill="none" stroke-linecap="round"/></g>'
            f'<path d="{arco}" fill="none" stroke="{p}" stroke-width="12" stroke-linejoin="round"/>'
            + _texto("ASSC", "archivo", 400, 256, 448, 250, 64, "#ffffff", espaciado=8))


def pzsg(p, a, s):
    return (f'<path d="M96 156 C140 108 196 112 230 138 C262 162 304 160 344 128 L410 128" fill="none" stroke="{p}" stroke-width="40" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M408 132 L136 352" fill="none" stroke="{p}" stroke-width="40" stroke-linecap="round"/>'
            f'<path d="M102 356 L170 356 C210 386 252 386 286 360 C320 334 370 334 416 372" fill="none" stroke="{_claro(p, .25)}" stroke-width="40" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="M96 156 C108 132 132 122 150 130 C138 140 136 152 146 160" fill="none" stroke="{a}" stroke-width="12" stroke-linecap="round"/>'
            f'<circle cx="430" cy="104" r="14" fill="{a}"/>'
            + _texto("PZSG", "exo_italica", 800, 256, 474, 320, 74, "#ffffff", espaciado=10))


def cspg(p, a, s):
    banderin = "M78 58 L466 214 L78 370 Z"
    return (f'<rect x="56" y="40" width="16" height="420" rx="8" fill="{_claro(p, .5)}"/>'
            f'<path d="{banderin}" fill="{p}"/>'
            f'<path d="M78 300 C160 280 230 296 330 260 L466 214 L78 370 Z" fill="{_oscuro(p, .3)}"/>'
            f'<circle cx="236" cy="178" r="56" fill="{a}"/>'
            f'<path d="M150 316 C160 260 168 214 196 160" stroke="#ffffff" stroke-width="12" fill="none" stroke-linecap="round"/>'
            f'<path d="M196 160 C176 140 140 140 116 160 C142 152 168 158 196 160 Z M196 160 C210 130 240 120 268 128 C240 136 222 146 196 160 Z '
            f'M196 160 C224 156 252 170 262 196 C240 180 220 172 196 160 Z M196 160 C170 166 150 188 146 214 C162 192 178 176 196 160 Z" fill="#ffffff"/>'
            + _texto("CSPG", "righteous", 400, 266, 476, 340, 84, a, espaciado=10))


def uidr(p, a, s):
    para = [(150, 48), (478, 48), (362, 464), (34, 464)]
    cortes = "".join(f'<line x1="{x}" y1="40" x2="{x - 132}" y2="480" stroke="black" stroke-width="12"/>' for x in (388, 418))
    return (f'<defs><mask id="mUIDR" maskUnits="userSpaceOnUse" x="0" y="0" width="512" height="512">'
            f'<rect width="512" height="512" fill="white"/>{cortes}</mask></defs>'
            f'<g mask="url(#mUIDR)"><polygon points="{_poli(para)}" fill="{p}"/>'
            f'<polygon points="{_poli([(78, 420), (196, 252), (250, 252), (370, 420)])}" fill="{a}"/>'
            f'<path d="M196 252 L210 282 L224 266 L236 290 L250 252 Z" fill="{_oscuro(p, .2)}"/>'
            f'<path d="M206 236 C196 210 226 196 218 168 M238 236 C252 214 238 196 254 176" stroke="#ffffff" stroke-opacity=".7" stroke-width="9" fill="none" stroke-linecap="round"/></g>'
            + _texto("UIDR", "kanit_italica", 700, 246, 164, 196, 96, "#ffffff", espaciado=4))


DISENOS = {"VESA": vesa, "APEX": apex, "SGSH": sgsh, "CSLS": csls, "IEAC": ieac,
           "DPST": dpst, "ASSC": assc, "PZSG": pzsg, "CSPG": cspg, "UIDR": uidr}


def svg_logo(corp: dict) -> str:
    principal, acento = corp["colores"]
    cuerpo = DISENOS[corp["sigla"]](principal, acento, corp["sigla"])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {TAM} {TAM}" width="{TAM}" height="{TAM}">'
            f'<title>{escape(corp["nombre"])}</title>{cuerpo}</svg>\n')


def generar(carpeta: str) -> None:
    destino = os.path.join(carpeta, "corporativos")
    os.makedirs(destino, exist_ok=True)
    filas = []
    for corp in CORPORATIVOS:
        svg = svg_logo(corp)
        with open(os.path.join(destino, f"{corp['sigla']}.svg"), "w", encoding="utf-8") as f:
            f.write(svg)
        src = f"corporativos/{corp['sigla']}.svg"
        filas.append(f'<figure><div class="fondos"><span class="o"><img src="{src}" class="g"></span>'
                     f'<span class="c"><img src="{src}" class="g"></span></div>'
                     f'<div class="chicos"><img src="{src}" width="48"><img src="{src}" width="32"><img src="{src}" width="16"></div>'
                     f'<figcaption><b>{corp["sigla"]}</b> · {len(svg) // 1024 + 1} KB<br>{corp["nombre"]}<br>'
                     f'<small>Tier {corp["tier"]} · {corp["region"]}</small></figcaption></figure>')
    with open(os.path.join(carpeta, "logos_corporativos.html"), "w", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8"><title>Logos corporativos</title><style>'
                'body{background:#0b1220;color:#e2e8f0;font-family:system-ui,Arial;margin:0;padding:24px;'
                'display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:18px}'
                'figure{margin:0;background:#111a2e;border-radius:14px;padding:14px}'
                '.fondos{display:grid;grid-template-columns:1fr 1fr;gap:8px}.fondos span{border-radius:10px;padding:10px;display:block}'
                '.o{background:#111c2e}.c{background:#e5e7eb}.g{width:100%;display:block}'
                '.chicos{display:flex;gap:14px;align-items:center;margin:10px 0;background:#0b1220;padding:8px;border-radius:8px}'
                'small{color:#94a3b8}</style>' + "".join(filas))
    print(f"{len(CORPORATIVOS)} logos en {destino} (hoja de revisión: {carpeta}/logos_corporativos.html)")


def subir(carpeta: str) -> None:
    origen = os.path.join(carpeta, "corporativos")
    subprocess.run(["gcloud", "storage", "cp", os.path.join(origen, "*.svg"), CARPETA_BUCKET + "/",
                    "--cache-control=public, max-age=604800", "--content-type=image/svg+xml"], check=True)


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "logos_corporativos"
    if modo == "--muestra":
        generar(carpeta)
    elif modo == "--subir":
        subir(carpeta)
    else:
        print(__doc__)
