"""
Genera las imágenes de bandera de cada selección para el bucket gs://com-icg-mundial (ver
services/imagenes_pais_service.py), a partir de dos sets libres (licencia MIT):

  - flag-icons (https://github.com/lipis/flag-icons), SVG 4:3   -> bandera/ (ondeada) y bandera_plana/
  - circle-flags (https://github.com/HatScripts/circle-flags)    -> icono/ (circular)

Carpetas que produce (un PNG por país, nombrado EXACTAMENTE como paises.nombre, en NFC):
  bandera/        bandera ondeada con relieve, fondo transparente, ~240 px de ancho (para usar en línea)
  icono/          bandera circular 256×256 con un aro y un brillo suaves (marcas de agua de tarjetas)
  bandera_plana/  bandera plana a sangre 400×300, sin transparencia (fondos con background-size: cover)

El código ISO de cada país sale de su emoji (paises.bandera): 2 indicadores regionales, o la secuencia de
etiquetas de las subdivisiones británicas (gb-eng, gb-sct, gb-wls). Determinístico.

Dependencias (NO van en requirements.txt: solo las usa este script): Pillow, numpy y Playwright con Chromium
(para pasar los SVG a PNG con fidelidad).

  python generar_banderas.py --fuentes <dir> --salida <dir> --muestra     # hoja de contacto antes/después
  python generar_banderas.py --fuentes <dir> --salida <dir> --generar     # las 211 en las 3 carpetas
  python generar_banderas.py --respaldar                                  # bandera/ e icono/ -> *_v1/ en el bucket
  python generar_banderas.py --salida <dir> --subir                       # sube las 3 carpetas

<dir de fuentes> = carpeta con 'flag-icons/package/flags/4x3/*.svg' y 'circle-flags/*/flags/*.svg'.
Vuelta atrás: gcloud storage cp 'gs://com-icg-mundial/bandera_v1/*' gs://com-icg-mundial/bandera/ (ídem icono)
y bajar VERSION_IMAGENES en services/imagenes_pais_service.py.
"""
import argparse
import glob
import io
import os
import subprocess
import sys
import unicodedata
from typing import Dict, Optional

BUCKET = "gs://com-icg-mundial"
CACHE_CONTROL = "public, max-age=604800"

# Medidas de salida
ANCHO_BANDERA = 240          # bandera ondeada (4:3 + margen para la onda)
LADO_ICONO = 256
PLANA = (400, 300)

# Render de trabajo (alta resolución, después se reduce)
BASE = (960, 720)

MUESTRA = ["Argentina", "Brasil", "Japón", "Inglaterra", "Escocia", "Gales", "Nepal", "Suiza", "Estados Unidos",
           "España", "México", "Kosovo", "Sudáfrica", "Corea del Sur", "Arabia Saudita", "Canadá", "Francia",
           "Países Bajos", "Bután", "Sri Lanka", "Belice", "Uruguay", "Portugal", "Australia"]


# ---------------------------------------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------------------------------------
def codigo_iso(emoji: str) -> Optional[str]:
    regionales = [c for c in emoji if 0x1F1E6 <= ord(c) <= 0x1F1FF]
    if len(regionales) == 2:
        return "".join(chr(ord(c) - 0x1F1E6 + 97) for c in regionales)
    etiquetas = "".join(chr(ord(c) - 0xE0061 + 97) for c in emoji if 0xE0061 <= ord(c) <= 0xE007A)
    return f"gb-{etiquetas[2:]}" if etiquetas.startswith("gb") else None


def paises() -> Dict[str, str]:
    """{nombre (NFC): código ISO} de las 211 selecciones."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import certifi
    from pymongo import MongoClient
    from config.settings import MONGODB_URI
    db = MongoClient(MONGODB_URI, tlsCAFile=certifi.where()).get_database("mundial")
    salida = {}
    for p in db["paises"].find({}, {"nombre": 1, "bandera": 1}):
        codigo = codigo_iso(p.get("bandera") or "")
        if not codigo:
            raise SystemExit(f"No se pudo sacar el código ISO de {p.get('nombre')} ({p.get('bandera')!r})")
        salida[unicodedata.normalize("NFC", p["nombre"])] = codigo
    return salida


def rutas_svg(fuentes: str, codigo: str) -> tuple:
    rect = os.path.join(fuentes, "flag-icons", "package", "flags", "4x3", f"{codigo}.svg")
    circulo = os.path.join(glob.glob(os.path.join(fuentes, "circle-flags", "*", "flags"))[0], f"{codigo}.svg")
    for r in (rect, circulo):
        if not os.path.exists(r):
            raise SystemExit(f"Falta {r}")
    return rect, circulo


# ---------------------------------------------------------------------------------------------------------
# Render SVG -> imagen (Chromium)
# ---------------------------------------------------------------------------------------------------------
class Renderizador:
    def __init__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._navegador = self._pw.chromium.launch()
        self._pagina = self._navegador.new_page(device_scale_factor=1)

    def svg(self, ruta: str, ancho: int, alto: int):
        from PIL import Image
        import base64
        self._pagina.set_viewport_size({"width": ancho, "height": alto})
        # El SVG va embebido (data URI): una página armada en memoria no puede cargar file://
        datos = base64.b64encode(open(ruta, "rb").read()).decode()
        self._pagina.set_content(f'<html><body style="margin:0;background:transparent">'
                                 f'<img src="data:image/svg+xml;base64,{datos}" style="display:block;width:{ancho}px;height:{alto}px">'
                                 f'</body></html>')
        self._pagina.wait_for_function("document.images[0].complete && document.images[0].naturalWidth > 0")
        png = self._pagina.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": ancho, "height": alto})
        return Image.open(io.BytesIO(png)).convert("RGBA")

    def captura_html(self, html: str, ancho: int, destino: str):
        # Se abre desde un archivo para que pueda mostrar las imágenes locales (file://)
        archivo = os.path.splitext(destino)[0] + ".html"
        with open(archivo, "w", encoding="utf-8") as f:
            f.write(html)
        self._pagina.set_viewport_size({"width": ancho, "height": 600})
        self._pagina.goto(f"file://{archivo}")
        self._pagina.wait_for_timeout(600)
        self._pagina.screenshot(path=destino, full_page=True)

    def cerrar(self):
        self._navegador.close()
        self._pw.stop()


# ---------------------------------------------------------------------------------------------------------
# Efectos
# ---------------------------------------------------------------------------------------------------------
def esquinas_redondeadas(img, radio: int):
    from PIL import Image, ImageDraw
    mascara = Image.new("L", img.size, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, img.size[0] - 1, img.size[1] - 1), radius=radio, fill=255)
    a = img.getchannel("A")
    from PIL import ImageChops
    img.putalpha(ImageChops.multiply(a, mascara))
    return img


def ondear(plana):
    """
    Bandera ondeando: cada columna baja/sube con una onda cuya amplitud crece del asta (izquierda) al borde
    libre, y el brillo sigue la pendiente de la onda (luces y sombras en los pliegues).
    """
    import numpy as np
    from PIL import Image
    src = np.asarray(plana).astype(np.float32)                 # (H, W, 4)
    alto, ancho = src.shape[:2]
    amplitud = alto * 0.06
    margen = int(amplitud * 1.25) + 2
    u = np.linspace(0, 1, ancho)
    envolvente = 0.2 + 0.8 * u ** 1.1
    fase = 2 * np.pi * 1.3 * u + 0.35
    dy = amplitud * envolvente * np.sin(fase)                  # desplazamiento vertical por columna
    pendiente = np.cos(fase) * envolvente                      # -1..1: hacia dónde mira el paño

    alto_salida = alto + 2 * margen
    yy = np.arange(alto_salida, dtype=np.float32)[:, None] - margen - dy[None, :]
    y0 = np.floor(yy).astype(int)
    t = (yy - y0)[..., None]
    def tomar(y):
        valido = (y >= 0) & (y < alto)
        yc = np.clip(y, 0, alto - 1)
        px = src[yc, np.arange(ancho)[None, :]]
        px[~valido] = 0
        return px
    salida = tomar(y0) * (1 - t) + tomar(y0 + 1) * t     # interpolación vertical (alfa incluido: bordes suaves)

    # Relieve: luz en las caras que miran a la izquierda-arriba, sombra en los valles; leve degradado general
    luz = 0.16 * pendiente[None, :] + 0.05 * (0.5 - np.linspace(0, 1, alto_salida))[:, None]
    rgb = salida[..., :3]
    aclarar = luz > 0
    luz3 = np.repeat(luz[..., None], 3, axis=2)
    rgb = np.where(np.repeat(aclarar[..., None], 3, axis=2), rgb + (255 - rgb) * luz3, rgb * (1 + luz3))
    salida[..., :3] = np.clip(rgb, 0, 255)
    return Image.fromarray(salida.astype(np.uint8), "RGBA")


def contorno_tenue(img, grosor: int = 3, opacidad: int = 70):
    """Un borde interior muy tenue que sigue la silueta (las banderas blancas no se pierden sobre fondo claro u oscuro)."""
    from PIL import Image, ImageFilter, ImageChops
    a = img.getchannel("A")
    interior = a.filter(ImageFilter.MinFilter(grosor * 2 + 1))
    borde = ImageChops.subtract(a, interior)
    capa = Image.new("RGBA", img.size, (15, 23, 42, 0))
    capa.putalpha(borde.point(lambda v: v * opacidad // 255))
    return Image.alpha_composite(img, capa)


def icono_circular(circulo):
    """Bandera circular con un aro suave y un brillo diagonal leve (volumen sin el plástico de los 2010)."""
    import numpy as np
    from PIL import Image
    lado = circulo.size[0]
    yy, xx = np.mgrid[0:lado, 0:lado].astype(np.float32)
    c = (lado - 1) / 2
    r = np.hypot(xx - c, yy - c) / c                       # 0 centro .. 1 borde
    rgba = np.asarray(circulo).astype(np.float32)
    # brillo: degradado diagonal desde arriba a la izquierda, más fuerte cerca del borde superior
    diag = ((c - xx) + (c - yy)) / (2 * c)                 # -1..1
    brillo = np.clip(diag, 0, 1) ** 1.6 * 0.22
    # sombra interior suave hacia el borde (da volumen)
    sombra = np.clip((r - 0.78) / 0.22, 0, 1) ** 2 * 0.22
    rgb = rgba[..., :3]
    rgb = rgb + (255 - rgb) * brillo[..., None]
    rgb = rgb * (1 - sombra[..., None])
    rgba[..., :3] = np.clip(rgb, 0, 255)
    img = Image.fromarray(rgba.astype(np.uint8), "RGBA")
    return contorno_tenue(img, grosor=max(2, lado // 128), opacidad=90)


def guardar_png(img, ruta: str, paleta: bool = True):
    """PNG con paleta de 256 colores (con alfa): ~5x más liviano y a la vista igual (medido: Brasil 32 KB -> 6,6 KB)."""
    from PIL import Image
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    if paleta:
        img = img.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE)
    img.save(ruta, "PNG", optimize=True)


def generar_pais(render: Renderizador, fuentes: str, salida: str, nombre: str, codigo: str) -> None:
    from PIL import Image
    rect, circulo = rutas_svg(fuentes, codigo)
    plana = render.svg(rect, *BASE)

    # bandera_plana: a sangre y sin transparencia (Nepal y otras con huecos quedan sobre un azul noche)
    fondo = Image.new("RGBA", plana.size, (17, 28, 46, 255))
    guardar_png(Image.alpha_composite(fondo, plana).convert("RGB").resize(PLANA, Image.LANCZOS),
                os.path.join(salida, "bandera_plana", f"{nombre}.png"))

    # bandera: ondeada
    ondeada = ondear(esquinas_redondeadas(plana.copy(), radio=BASE[1] // 28))
    alto = round(ondeada.size[1] * ANCHO_BANDERA / ondeada.size[0])
    ondeada = contorno_tenue(ondeada.resize((ANCHO_BANDERA, alto), Image.LANCZOS), grosor=1, opacidad=80)
    guardar_png(ondeada, os.path.join(salida, "bandera", f"{nombre}.png"))

    # icono: circular
    circ = render.svg(circulo, LADO_ICONO * 2, LADO_ICONO * 2)
    guardar_png(icono_circular(circ).resize((LADO_ICONO, LADO_ICONO), Image.LANCZOS),
                os.path.join(salida, "icono", f"{nombre}.png"))


# ---------------------------------------------------------------------------------------------------------
# Modos
# ---------------------------------------------------------------------------------------------------------
def muestra(fuentes: str, salida: str) -> None:
    from urllib.parse import quote
    todos = paises()
    render = Renderizador()
    try:
        filas = []
        for nombre in MUESTRA:
            nombre = unicodedata.normalize("NFC", nombre)
            if nombre not in todos:
                print(f"(no está en paises: {nombre})")
                continue
            generar_pais(render, fuentes, salida, nombre, todos[nombre])
            viejo = f"https://storage.googleapis.com/com-icg-mundial/{{}}/{quote(nombre)}.png"
            nuevo = lambda t: f"file://{os.path.join(salida, t, nombre)}.png"
            filas.append(f"""
            <div class="pais"><b>{nombre}</b>
              <div class="par"><span>antes</span><img src="{viejo.format('bandera')}" style="height:44px"><img src="{viejo.format('bandera')}" style="height:22px">
                   <img src="{viejo.format('icono')}" style="height:56px"></div>
              <div class="par"><span>nuevo</span><img src="{nuevo('bandera')}" style="height:44px"><img src="{nuevo('bandera')}" style="height:17px">
                   <img src="{nuevo('icono')}" style="height:56px"><img src="{nuevo('bandera_plana')}" style="height:34px;border-radius:4px"></div>
            </div>""")
        html = f"""<html><body style="margin:0;padding:18px;background:#0b1220;font:13px system-ui;color:#cbd5e1">
          <style>.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}} .pais{{background:#111c2e;border-radius:12px;padding:10px}}
          .par{{display:flex;align-items:center;gap:10px;margin-top:6px}} .par span{{width:42px;color:#64748b;font-size:11px}}</style>
          <div class="grid">{''.join(filas)}</div></body></html>"""
        destino = os.path.join(salida, "muestra.png")
        render.captura_html(html, 1500, destino)
        print("Hoja de muestra:", destino)
    finally:
        render.cerrar()


def generar(fuentes: str, salida: str) -> None:
    todos = paises()
    render = Renderizador()
    try:
        for i, (nombre, codigo) in enumerate(sorted(todos.items()), 1):
            generar_pais(render, fuentes, salida, nombre, codigo)
            if i % 20 == 0:
                print(f"{i}/{len(todos)}")
    finally:
        render.cerrar()
    for carpeta in ("bandera", "icono", "bandera_plana"):
        hechos = {os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(salida, carpeta, "*.png"))}
        faltan = set(todos) - {unicodedata.normalize("NFC", h) for h in hechos}
        print(f"{carpeta}: {len(hechos)} archivos" + (f" · FALTAN {sorted(faltan)}" if faltan else " · completo"))


def respaldar() -> None:
    for carpeta in ("bandera", "icono"):
        subprocess.run(["gcloud", "storage", "cp", f"{BUCKET}/{carpeta}/*", f"{BUCKET}/{carpeta}_v1/"], check=True)
    print("Respaldo listo: bandera_v1/ e icono_v1/")


def subir(salida: str) -> None:
    for carpeta in ("bandera", "icono", "bandera_plana"):
        subprocess.run(["gcloud", "storage", "cp", os.path.join(salida, carpeta, "*.png"), f"{BUCKET}/{carpeta}/",
                        f"--cache-control={CACHE_CONTROL}", "--content-type=image/png"], check=True)
    print("Subidas: bandera/, icono/ y bandera_plana/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fuentes")
    ap.add_argument("--salida")
    grupo = ap.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--muestra", action="store_true")
    grupo.add_argument("--generar", action="store_true")
    grupo.add_argument("--respaldar", action="store_true")
    grupo.add_argument("--subir", action="store_true")
    args = ap.parse_args()
    if args.muestra:
        muestra(args.fuentes, args.salida)
    elif args.generar:
        generar(args.fuentes, args.salida)
    elif args.respaldar:
        respaldar()
    else:
        subir(args.salida)
