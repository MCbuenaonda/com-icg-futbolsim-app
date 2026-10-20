"""
Logos de los 10 Corporativos Deportivos (config/corporativos.py): un SVG por corporativo, fondo transparente,
escudo con los dos colores de marca, emblema de su región y la sigla.

Uso:
    python generar_logos_corporativos.py --muestra [carpeta]   # SVGs + una hoja HTML para revisarlos
    python generar_logos_corporativos.py --subir [carpeta]     # sube corporativos/<SIGLA>.svg al bucket

Es texto puro (sin dependencias). Para cambiar un logo: editar su emblema o colores en config/corporativos.py
(o el dibujo en EMBLEMAS) y volver a correr --muestra y --subir.
"""
import math
import os
import subprocess
import sys

from config.corporativos import CORPORATIVOS

CARPETA_BUCKET = "gs://com-icg-mundial/corporativos"
TAM = 512
ESCUDO = "M256 26 L456 90 V246 C456 372 366 452 256 492 C146 452 56 372 56 246 V90 Z"


def _oscurecer(hexa: str, f: float) -> str:
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (int(r * f), int(g * f), int(b * f))


def _estrella(cx, cy, r, picos=5, interno=0.45, giro=-90):
    pts = []
    for i in range(picos * 2):
        rr = r if i % 2 == 0 else r * interno
        a = math.radians(giro + i * 180 / picos)
        pts.append(f"{cx + rr * math.cos(a):.1f},{cy + rr * math.sin(a):.1f}")
    return " ".join(pts)


# Cada emblema dibuja dentro de la zona (130..382, 92..290) con el color de acento 'a' y el claro 'c'.
def _escudo(a, c):
    estrellas = "".join(f'<polygon points="{_estrella(x, y, 20)}" fill="{c}"/>' for x, y in ((196, 128), (256, 112), (316, 128)))
    return (estrellas +
            f'<path d="M150 160 L256 286 L362 160 L318 160 L256 236 L194 160 Z" fill="{a}"/>')


def _cumbre(a, c):
    return (f'<path d="M132 280 L226 146 L262 196 L304 134 L380 280 Z" fill="{a}"/>'
            f'<path d="M226 146 L250 180 L236 176 L222 190 L208 172 Z M304 134 L328 170 L314 166 L302 178 L288 160 Z" fill="{c}"/>'
            f'<path d="M150 296 H362" stroke="{c}" stroke-width="6" stroke-linecap="round"/>')


def _halcon(a, c):
    """Halcón de frente con las alas abiertas (estilo heráldico), plumas escalonadas en las puntas."""
    def ala(signo):
        x = lambda v: 256 + signo * v
        return (f'<path d="M{x(18)} 186 C{x(60)} 150 {x(110)} 124 {x(132)} 112 L{x(126)} 140 L{x(118)} 150 '
                f'L{x(122)} 172 L{x(108)} 180 L{x(110)} 204 L{x(94)} 210 L{x(92)} 232 L{x(70)} 230 '
                f'C{x(52)} 232 {x(30)} 236 {x(18)} 244 Z" fill="{a}"/>')
    return (ala(1) + ala(-1)
            + f'<path d="M256 150 C276 150 286 168 284 196 C282 232 272 262 256 286 C240 262 230 232 228 196 C226 168 236 150 256 150 Z" fill="{a}"/>'
            + f'<path d="M256 286 L236 304 L256 298 L276 304 Z" fill="{a}"/>'
            + f'<circle cx="256" cy="140" r="22" fill="{a}"/>'
            + f'<path d="M256 140 L272 150 L256 168 Z" fill="{c}"/>'
            + f'<circle cx="250" cy="134" r="5" fill="{c}"/>'
            + f'<path d="M244 206 Q256 214 268 206 M242 226 Q256 234 270 226" stroke="{c}" stroke-width="4" fill="none" opacity=".7"/>')


def _sol(a, c):
    rayos = "".join(
        f'<polygon points="{256 + 66 * math.cos(math.radians(g - 7)):.1f},{196 + 66 * math.sin(math.radians(g - 7)):.1f} '
        f'{256 + 112 * math.cos(math.radians(g)):.1f},{196 + 112 * math.sin(math.radians(g)):.1f} '
        f'{256 + 66 * math.cos(math.radians(g + 7)):.1f},{196 + 66 * math.sin(math.radians(g + 7)):.1f}" fill="{a}"/>'
        for g in range(0, 360, 30))
    return (rayos + f'<circle cx="256" cy="196" r="58" fill="{a}"/>'
            f'<circle cx="256" cy="196" r="40" fill="none" stroke="{c}" stroke-width="6"/>'
            f'<path d="M234 190 q8 -8 16 0 M262 190 q8 -8 16 0 M238 214 q18 14 36 0" stroke="{c}" stroke-width="6" fill="none" stroke-linecap="round"/>')


def _corona(a, c):
    return (f'<path d="M150 266 L136 140 L196 196 L256 116 L316 196 L376 140 L362 266 Z" fill="{a}"/>'
            f'<rect x="146" y="252" width="220" height="34" rx="6" fill="{a}"/>'
            + "".join(f'<circle cx="{x}" cy="{y}" r="13" fill="{c}"/>' for x, y in ((136, 136), (256, 110), (376, 136)))
            + "".join(f'<circle cx="{x}" cy="269" r="8" fill="{c}"/>' for x in (190, 256, 322)))


def _pagoda(a, c):
    techo = lambda y, w: (f'<path d="M{256 - w} {y} Q256 {y - 40} {256 + w} {y} Q{256 + w * 0.6} {y - 2} {256 + w * 0.55} {y - 22} '
                          f'L{256 - w * 0.55} {y - 22} Q{256 - w * 0.6} {y - 2} {256 - w} {y} Z" fill="{a}"/>')
    return (techo(172, 74) + techo(226, 100) + techo(280, 126)
            + f'<rect x="222" y="170" width="68" height="36" fill="{c}" opacity=".9"/>'
            + f'<rect x="206" y="222" width="100" height="36" fill="{c}" opacity=".9"/>'
            + f'<path d="M256 104 V134" stroke="{a}" stroke-width="8" stroke-linecap="round"/><circle cx="256" cy="100" r="9" fill="{c}"/>')


def _acacia(a, c):
    return (f'<path d="M150 270 A106 106 0 0 1 362 270 Z" fill="{c}" opacity=".9"/>'
            f'<path d="M248 286 L252 214 L214 182 M252 214 L292 176 M252 230 L230 212" stroke="{a}" stroke-width="12" fill="none" stroke-linecap="round"/>'
            f'<path d="M168 186 Q256 128 344 178 Q300 196 256 190 Q206 198 168 186 Z" fill="{a}"/>'
            f'<path d="M140 286 H372" stroke="{a}" stroke-width="10" stroke-linecap="round"/>')


def _ola(a, c):
    return (f'<path d="M136 236 C176 140 290 124 330 184 C350 214 322 246 292 232 C270 222 276 194 300 196 '
            f'C282 168 222 172 200 220 C186 250 160 264 136 236 Z" fill="{a}"/>'
            f'<path d="M136 266 Q176 244 216 266 T296 266 T376 266" stroke="{c}" stroke-width="10" fill="none" stroke-linecap="round"/>'
            f'<path d="M150 292 Q190 270 230 292 T310 292 T370 292" stroke="{a}" stroke-width="8" fill="none" stroke-linecap="round"/>')


def _palmera(a, c):
    hojas = "".join(
        f'<path d="M262 152 Q{262 + dx * 0.5} {152 + dy - 40} {262 + dx} {152 + dy} Q{262 + dx * 0.55} {152 + dy - 14} 262 160 Z" fill="{a}"/>'
        for dx, dy in ((-112, 18), (-82, 60), (108, 22), (84, 64), (-20, -50), (40, -46)))
    return (f'<path d="M244 292 Q248 222 262 156" stroke="{c}" stroke-width="16" fill="none" stroke-linecap="round"/>'
            + hojas + f'<circle cx="250" cy="170" r="10" fill="{c}"/><circle cx="270" cy="172" r="10" fill="{c}"/>'
            f'<path d="M150 292 Q256 262 362 292" stroke="{a}" stroke-width="10" fill="none" stroke-linecap="round"/>')


def _volcan(a, c):
    return (f'<path d="M132 284 L222 168 L240 182 L272 182 L290 168 L380 284 Z" fill="{a}"/>'
            f'<path d="M222 168 L240 182 L256 172 L272 182 L290 168 L276 196 L256 188 L236 196 Z" fill="{c}"/>'
            + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" opacity=".85"/>' for x, y, r in ((256, 140, 20), (282, 112, 16), (240, 100, 12)))
            + f'<path d="M150 296 H362" stroke="{c}" stroke-width="6" stroke-linecap="round"/>')


EMBLEMAS = {"escudo": _escudo, "cumbre": _cumbre, "halcon": _halcon, "sol": _sol, "corona": _corona,
            "pagoda": _pagoda, "acacia": _acacia, "ola": _ola,
            "palmera": _palmera, "volcan": _volcan}


def svg_logo(corp: dict) -> str:
    principal, acento = corp["colores"]
    oscuro = _oscurecer(principal, 0.35)
    gid = f"g{corp['sigla']}"
    emblema = EMBLEMAS[corp["emblema"]](acento, "#ffffff")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {TAM} {TAM}" width="{TAM}" height="{TAM}">
<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="{principal}"/><stop offset="1" stop-color="{oscuro}"/></linearGradient></defs>
<path d="{ESCUDO}" fill="url(#{gid})" stroke="{acento}" stroke-width="12" stroke-linejoin="round"/>
<path d="{ESCUDO}" fill="none" stroke="#ffffff" stroke-opacity=".25" stroke-width="3" transform="translate(256 259) scale(.9) translate(-256 -259)"/>
{emblema}
<rect x="166" y="318" width="180" height="6" rx="3" fill="{acento}"/>
<text x="256" y="408" text-anchor="middle" font-family="Montserrat, 'Segoe UI', Arial, sans-serif" font-weight="800"
 font-size="{86 if len(corp['sigla']) <= 4 else 74}" letter-spacing="6" fill="#ffffff">{corp['sigla']}</text>
</svg>
"""


def generar(carpeta: str) -> None:
    destino = os.path.join(carpeta, "corporativos")
    os.makedirs(destino, exist_ok=True)
    tarjetas = []
    for corp in CORPORATIVOS:
        with open(os.path.join(destino, f"{corp['sigla']}.svg"), "w", encoding="utf-8") as f:
            f.write(svg_logo(corp))
        tarjetas.append(f'<figure><img src="corporativos/{corp["sigla"]}.svg"><figcaption><b>{corp["sigla"]}</b>'
                        f'<br>{corp["nombre"]}<br><small>Tier {corp["tier"]} · {corp["region"]}</small></figcaption></figure>')
    with open(os.path.join(carpeta, "logos_corporativos.html"), "w", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8"><style>body{background:#0b1220;color:#e2e8f0;font-family:Arial;'
                'display:grid;grid-template-columns:repeat(5,1fr);gap:18px;padding:24px}figure{margin:0;text-align:center;'
                'background:#111a2e;border-radius:14px;padding:14px}img{width:100%}small{color:#94a3b8}</style>'
                + "".join(tarjetas))
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
