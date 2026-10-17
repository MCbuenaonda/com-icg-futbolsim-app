"""
Generador de ilustraciones de estadios (SVG, dibujo de líneas en vista 3/4) para las ciudades sede.

En lugar de dibujar 4.246 estadios a mano, cada estadio se arma combinando piezas (planta, anillos
de gradas, techo, torres de esquina, torres de iluminación y entorno) en un catálogo de diseños
base; el color del trazo de acento sale de la bandera de cada país. Ver CLAUDE.md
("Ilustraciones de estadios").

Uso (en este orden; cada paso es idempotente):
    python generar_estadios.py --muestra [carpeta]   # un SVG por diseño, para revisar (sin Mongo ni bucket)
    python generar_estadios.py --generar [carpeta]   # 36 diseños x 12 colores = 432 SVG en <carpeta>/estadios/
    python generar_estadios.py --subir [carpeta]     # VACÍA gs://com-icg-mundial/estadios/ y sube los SVG
    python generar_estadios.py --asignar             # escribe ciudades.estadio_imagen en Mongo

Generar los SVG no necesita dependencias (es texto). --asignar lee el color de cada bandera del
bucket con Pillow (pip install pillow; solo para este script, la app no lo usa).
"""
import math
import os
import random
import sys

ANCHO, ALTO = 640, 400

# --- Estilo -------------------------------------------------------------------------------------
TRAZO = "#e2e8f0"          # líneas principales (claras, para el tema oscuro)
TRAZO_SUAVE = "#94a3b8"    # filas de gradas, detalles
RELLENO = "#141c2e"        # relleno de las superficies (tapa lo que queda detrás)
RELLENO_GRADAS = "#1b2640"
CESPED = "#1f5f3a"
LINEAS_CANCHA = "#a7f3c7"


# --- Proyección 3/4 ------------------------------------------------------------------------------
class Vista:
    """Proyecta coordenadas del mundo (x a lo largo de la cancha, y a lo ancho, z altura) a la imagen."""

    def __init__(self, giro_grados=-18.0, aplastado=0.52, escala=2.25, cx=ANCHO / 2, cy=ALTO / 2 + 18):
        self.c, self.s = math.cos(math.radians(giro_grados)), math.sin(math.radians(giro_grados))
        self.k, self.e, self.cx, self.cy = aplastado, escala, cx, cy
        self.caja = [math.inf, math.inf, -math.inf, -math.inf]  # lo que ocupa el dibujo, para encuadrarlo

    def p(self, x, y, z=0.0):
        xr = x * self.c - y * self.s
        yr = x * self.s + y * self.c
        punto = (self.cx + xr * self.e, self.cy + yr * self.e * self.k - z * self.e * 0.62)
        self.incluir(*punto)
        return punto

    def incluir(self, x, y):
        c = self.caja
        c[0], c[1], c[2], c[3] = min(c[0], x), min(c[1], y), max(c[2], x), max(c[3], y)


def _pts(puntos):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in puntos)


def _segmentos(segs, color, ancho, extra=""):
    """Muchas líneas sueltas con el mismo estilo en un solo <path> (los SVG pesan bastante menos)."""
    if not segs:
        return ""
    d = "".join(f"M{a[0]:.1f} {a[1]:.1f}L{b[0]:.1f} {b[1]:.1f}" for a, b in segs)
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{ancho}" {extra}/>'


def _casco(puntos):
    """Casco convexo (cadena monótona): la silueta de la fachada entre el anillo del suelo y el superior."""
    pts = sorted(set((round(x, 1), round(y, 1)) for x, y in puntos))
    if len(pts) < 3:
        return pts
    def cruz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    abajo, arriba = [], []
    for p in pts:
        while len(abajo) >= 2 and cruz(abajo[-2], abajo[-1], p) <= 0:
            abajo.pop()
        abajo.append(p)
    for p in reversed(pts):
        while len(arriba) >= 2 and cruz(arriba[-2], arriba[-1], p) <= 0:
            arriba.pop()
        arriba.append(p)
    return abajo[:-1] + arriba[:-1]


def _contorno(forma, a, b, t):
    """Punto del borde de la planta en el parámetro t (superelipse: 2 = óvalo, 4 = rectángulo redondeado)."""
    n = {"oval": 2.0, "rect": 4.5, "circulo": 2.0, "octogono": 3.0}[forma]
    c, s = math.cos(t), math.sin(t)
    return (a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s))


class Estadio:
    def __init__(self, diseno, acento, semilla=0):
        self.d = diseno
        self.acento = acento
        # con arco o skyline hace falta más aire arriba: el estadio baja un poco en la imagen
        self.v = Vista(cy=ALTO / 2 + (48 if diseno.get("techo") == "arco" else 18))
        self.rnd = random.Random(semilla)
        self.capas = []  # (orden, svg)
        forma = diseno["forma"]
        # Borde interior (alrededor de la cancha) según la forma
        self.a0, self.b0 = {"oval": (74, 50), "rect": (61, 43), "circulo": (66, 66), "octogono": (66, 47)}[forma]
        self.forma = forma
        self.N = 72  # puntos por anillo

    # --- utilidades geométricas ---
    def anillo(self, desplazamiento, z, t0=0.0, t1=2 * math.pi, n=None):
        n = n or self.N
        return [self._punto(desplazamiento, z, t0 + (t1 - t0) * i / n) for i in range(n + (0 if t1 - t0 >= 2 * math.pi - 1e-6 else 1))]

    def _punto(self, desplazamiento, z, t):
        x, y = _contorno(self.forma, self.a0 + desplazamiento, self.b0 + desplazamiento, t)
        return self.v.p(x, y, z)

    def add(self, svg, orden=0):
        self.capas.append((orden, svg))

    # --- piezas ---
    def niveles(self):
        """Anillos de gradas: lista de (desp_interior, z_interior, desp_exterior, z_exterior)."""
        res, d, z = [], 4.0, 1.0
        for i in range(self.d["anillos"]):
            prof = 15.0 if i == 0 else 12.0
            alto = 9.0 if i == 0 else 8.5
            res.append((d, z, d + prof, z + alto))
            d, z = d + prof + 2.5, z + alto + 2.5  # pasillo / concourse entre anillos
        return res

    def dibujar(self):
        niveles = self.niveles()
        d_ext, z_top = niveles[-1][2], niveles[-1][3]
        self.d_ext, self.z_top = d_ext, z_top
        if self.d.get("entorno") == "skyline":
            self._skyline()
        self._sombra(d_ext)
        self._fachada(d_ext + 1.5, z_top)
        # superficie superior (tapa la parte trasera de la fachada)
        self.add(f'<polygon points="{_pts(self.anillo(d_ext + 1.5, z_top))}" fill="{RELLENO}" stroke="{TRAZO}" stroke-width="1.6"/>', 20)
        for (di, zi, de, ze) in reversed(niveles):
            self._gradas(di, zi, de, ze)
        self._cancha()
        techo = self.d.get("techo")
        if techo:
            getattr(self, f"_techo_{techo}")(d_ext + 1.5, z_top)
        if self.d.get("torres"):
            self._torres_esquina(d_ext + 1.5, z_top)
        if self.d.get("focos"):
            self._focos(d_ext + 1.5, z_top)
        if self.d.get("entorno") == "arboles":
            self._arboles(d_ext)
        return self.svg()

    def _sombra(self, d_ext):
        self.add(f'<polygon points="{_pts(self.anillo(d_ext + 9, 0))}" fill="#000" opacity="0.25"/>', 0)

    def _fachada(self, d, z_top):
        """Pared exterior: tiras verticales entre el anillo del suelo y el superior, de atrás hacia adelante."""
        base = self.anillo(d, 0)
        arriba = self.anillo(d, z_top)
        n = len(base)
        # silueta rellena (tapa lo de atrás) y nervaduras verticales solo en la mitad visible (la de
        # adelante: donde el anillo del suelo queda más abajo en la imagen que el centro)
        partes = [f'<polygon points="{_pts(_casco(base + arriba))}" fill="{RELLENO}" stroke="none"/>']
        paso = 2 if self.d.get("fachada") == "costillas" else 3
        centro_y = sum(p[1] for p in base) / n
        partes.append(_segmentos([(base[i], arriba[i]) for i in range(0, n, paso) if base[i][1] > centro_y - 4], TRAZO_SUAVE, 0.9))
        # bandas horizontales de la fachada (pisos), también solo adelante
        for f in (0.33, 0.66):
            anillo_f = self.anillo(d, z_top * f)
            partes.append(_segmentos([(anillo_f[i], anillo_f[(i + 1) % n]) for i in range(n) if base[i][1] > centro_y - 4], TRAZO_SUAVE, 0.8))
        partes.append(_segmentos([(base[i], base[(i + 1) % n]) for i in range(n) if base[i][1] > centro_y - 4], TRAZO, 1.4))
        # borde superior en color de acento
        partes.append(f'<polygon points="{_pts(arriba)}" fill="none" stroke="{self.acento}" stroke-width="2.2"/>')
        self.add("".join(partes), 10)

    def _gradas(self, di, zi, de, ze):
        ext = self.anillo(de, ze)
        inte = self.anillo(di, zi)
        partes = [f'<polygon points="{_pts(ext)}" fill="{RELLENO_GRADAS}" stroke="{TRAZO}" stroke-width="1.2"/>']
        filas = 5
        for f in range(1, filas):
            r = f / filas
            partes.append(f'<polygon points="{_pts(self.anillo(di + (de - di) * r, zi + (ze - zi) * r))}" fill="none" stroke="{TRAZO_SUAVE}" stroke-width="0.6"/>')
        # pasillos radiales (escaleras)
        n = len(ext)
        partes.append(_segmentos([(inte[i], ext[i]) for i in range(0, n, 6)], TRAZO_SUAVE, 0.7))
        partes.append(f'<polygon points="{_pts(inte)}" fill="{RELLENO}" stroke="{TRAZO}" stroke-width="1"/>')
        self.add("".join(partes), 30 - di / 100)

    def _cancha(self):
        v = self.v
        L, W, z = 52.5, 34.0, 1.0

        def rect(x0, y0, x1, y1):
            return _pts([v.p(x0, y0, z), v.p(x1, y0, z), v.p(x1, y1, z), v.p(x0, y1, z)])

        def circulo(cx, cy, r, a0=0, a1=2 * math.pi, n=40):
            return _pts([v.p(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n), z) for i in range(n + 1)])

        # franjas de césped
        partes = [f'<polygon points="{rect(-L - 3, -W - 3, L + 3, W + 3)}" fill="{CESPED}"/>']
        for i in range(10):
            if i % 2:
                x0 = -L + 2 * L * i / 10
                partes.append(f'<polygon points="{rect(x0, -W, x0 + 2 * L / 10, W)}" fill="#26704a"/>')
        lc = f'fill="none" stroke="{LINEAS_CANCHA}" stroke-width="1"'
        partes.append(f'<polygon points="{rect(-L, -W, L, W)}" {lc}/>')
        partes.append(f'<polyline points="{_pts([v.p(0, -W, z), v.p(0, W, z)])}" {lc}/>')
        partes.append(f'<polyline points="{circulo(0, 0, 9.15)}" {lc}/>')
        for s in (-1, 1):
            partes.append(f'<polygon points="{rect(s * L, -20.15, s * (L - 16.5), 20.15)}" {lc}/>')
            partes.append(f'<polygon points="{rect(s * L, -9.16, s * (L - 5.5), 9.16)}" {lc}/>')
            partes.append(f'<polygon points="{rect(s * L, -3.66, s * (L + 1.8), 3.66)}" fill="none" stroke="{TRAZO}" stroke-width="1"/>')
        self.add("".join(partes), 40)

    # --- techos ---
    def _banda_techo(self, d_ext, z_top, vuelo, t0=0.0, t1=2 * math.pi, triangulado=False):
        z = z_top + 7
        exterior = self.anillo(d_ext, z, t0, t1)
        interior = self.anillo(d_ext - vuelo, z, t0, t1)
        completo = t1 - t0 >= 2 * math.pi - 1e-6
        if completo:
            path = f'M{_pts(exterior)} Z M{_pts(list(reversed(interior)))} Z'
            partes = [f'<path d="{path}" fill="{self.acento}" fill-opacity="0.16" fill-rule="evenodd" stroke="{self.acento}" stroke-width="1.6"/>']
        else:
            partes = [f'<polygon points="{_pts(exterior + list(reversed(interior)))}" fill="{self.acento}" fill-opacity="0.16" stroke="{self.acento}" stroke-width="1.6"/>']
        n = len(exterior)
        paso = 3 if triangulado else 4
        partes.append(_segmentos([(exterior[i], interior[i]) for i in range(0, n, paso)], self.acento, 0.8, 'opacity="0.8"'))
        if triangulado:
            partes.append(_segmentos([(exterior[i], interior[i + 3]) for i in range(0, n - 3, 3)], self.acento, 0.6, 'opacity="0.7"'))
        # columnas que sostienen el techo (desde el borde superior de la fachada)
        base = self.anillo(d_ext, z_top, t0, t1)
        partes.append(_segmentos([(base[i], exterior[i]) for i in range(0, n, 6)], TRAZO, 1))
        return "".join(partes)

    def _techo_anillo(self, d, z):
        self.add(self._banda_techo(d, z, 16), 50)

    def _techo_membrana(self, d, z):
        self.add(self._banda_techo(d, z, 20, triangulado=True), 50)

    def _techo_laterales(self, d, z):
        # solo sobre las tribunas largas (lados de la cancha)
        self.add(self._banda_techo(d, z, 15, math.radians(35), math.radians(145)), 50)
        self.add(self._banda_techo(d, z, 15, math.radians(215), math.radians(325)), 50)

    def _techo_principal(self, d, z):
        # una sola tribuna principal techada (lado del fondo)
        self.add(self._banda_techo(d, z, 18, math.radians(215), math.radians(325)), 50)

    def _techo_arco(self, d, z):
        # techo en anillo + un gran arco que cruza el estadio de punta a punta
        self.add(self._banda_techo(d, z, 14), 50)
        v = self.v
        a = self.a0 + d + 8
        y = -(self.b0 + d) * 0.55  # sobre la tribuna del fondo, para que se lea como arco
        pts = [v.p(-a + 2 * a * i / 60, y, z + 6 + 62 * math.sin(math.pi * i / 60)) for i in range(61)]
        pts2 = [v.p(-a + 2 * a * i / 60, y, z + 6 + 55 * math.sin(math.pi * i / 60)) for i in range(61)]
        partes = [f'<polyline points="{_pts(pts)}" fill="none" stroke="{self.acento}" stroke-width="2.6"/>',
                  f'<polyline points="{_pts(pts2)}" fill="none" stroke="{self.acento}" stroke-width="1.2"/>',
                  _segmentos([(pts[i], pts2[i + 1]) for i in range(0, 60, 2)] + [(pts[i + 1], pts2[i]) for i in range(0, 60, 2)], self.acento, 0.7)]
        # cables del arco al techo
        partes.append(_segmentos([(pts2[i], v.p(-a + 2 * a * i / 60, y, z + 7)) for i in range(6, 56, 6)], TRAZO_SUAVE, 0.6, 'opacity="0.7"'))
        self.add("".join(partes), 60)

    # --- extras ---
    def _cilindro(self, x, y, r, z0, z1, bandas=6):
        v = self.v
        n = 28
        abajo = [v.p(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n), z0) for i in range(n)]
        arriba = [v.p(x + r * math.cos(2 * math.pi * i / n), y + r * math.sin(2 * math.pi * i / n), z1) for i in range(n)]
        izq = min(range(n), key=lambda i: abajo[i][0])
        der = max(range(n), key=lambda i: abajo[i][0])
        cuerpo = [abajo[izq], abajo[der], arriba[der], arriba[izq]]
        partes = [f'<polygon points="{_pts(abajo)}" fill="{RELLENO}" stroke="{TRAZO}" stroke-width="1.1"/>',
                  f'<polygon points="{_pts(cuerpo)}" fill="{RELLENO}" stroke="none"/>',
                  f'<line x1="{abajo[izq][0]:.1f}" y1="{abajo[izq][1]:.1f}" x2="{arriba[izq][0]:.1f}" y2="{arriba[izq][1]:.1f}" stroke="{TRAZO}" stroke-width="1.1"/>',
                  f'<line x1="{abajo[der][0]:.1f}" y1="{abajo[der][1]:.1f}" x2="{arriba[der][0]:.1f}" y2="{arriba[der][1]:.1f}" stroke="{TRAZO}" stroke-width="1.1"/>']
        # rampas helicoidales: bandas inclinadas solo en la mitad visible
        for b in range(1, bandas):
            zb = z0 + (z1 - z0) * b / bandas
            frente = [v.p(x + r * math.cos(math.pi * i / 14), y + r * math.sin(math.pi * i / 14), zb + 1.6 * math.cos(math.pi * i / 14)) for i in range(15)]
            partes.append(f'<polyline points="{_pts(frente)}" fill="none" stroke="{self.acento}" stroke-width="1"/>')
        partes.append(f'<polygon points="{_pts(arriba)}" fill="{RELLENO}" stroke="{TRAZO}" stroke-width="1.1"/>')
        return "".join(partes)

    def _torres_esquina(self, d, z_top):
        for ang in (40, 140, 220, 320):
            t = math.radians(ang)
            x, y = _contorno(self.forma, self.a0 + d + 7, self.b0 + d + 7, t)
            prof = self.v.p(x, y)[1]
            # las de atrás quedan detrás de la fachada (orden menor), las de adelante encima
            orden = 5 if ang in (220, 320) else 65
            self.add(self._cilindro(x, y, 7.5, 0, z_top + 4), orden + prof / 1000)

    def _focos(self, d, z_top):
        v = self.v
        for ang in (35, 145, 215, 325):
            t = math.radians(ang)
            x, y = _contorno(self.forma, self.a0 + d + 5, self.b0 + d + 5, t)
            p0, p1 = v.p(x, y, 0), v.p(x, y, z_top + 34)
            orden = 4 if ang in (215, 325) else 66
            panel = [v.p(x - 4, y, z_top + 34), v.p(x + 4, y, z_top + 34), v.p(x + 4, y, z_top + 40), v.p(x - 4, y, z_top + 40)]
            self.add(f'<line x1="{p0[0]:.1f}" y1="{p0[1]:.1f}" x2="{p1[0]:.1f}" y2="{p1[1]:.1f}" stroke="{TRAZO}" stroke-width="1.6"/>'
                     f'<polygon points="{_pts(panel)}" fill="{self.acento}" fill-opacity="0.35" stroke="{TRAZO}" stroke-width="1"/>', orden)

    def _arboles(self, d_ext):
        v = self.v
        partes_atras, partes_frente = [], []
        for i in range(34):
            t = 2 * math.pi * i / 34 + self.rnd.uniform(-0.05, 0.05)
            x, y = _contorno(self.forma, self.a0 + d_ext + 16, self.b0 + d_ext + 16, t)
            px, py = v.p(x, y, 0)
            r = self.rnd.uniform(5.0, 7.0)
            arbol = (f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{px:.1f}" y2="{py - r * 1.6:.1f}" stroke="{TRAZO_SUAVE}" stroke-width="1"/>'
                     f'<circle cx="{px:.1f}" cy="{py - r * 2.2:.1f}" r="{r:.1f}" fill="{RELLENO}" stroke="{TRAZO_SUAVE}" stroke-width="1"/>')
            (partes_frente if math.sin(t) * self.v.c + math.cos(t) * self.v.s > -0.1 else partes_atras).append(arbol)
        self.add("".join(partes_atras), 2)
        self.add("".join(partes_frente), 70)

    def _skyline(self):
        partes, ventanas = [], []
        x = 40
        while x < ANCHO - 40:
            w = self.rnd.uniform(14, 30)
            h = self.rnd.uniform(40, 120) * (1 - abs(x - ANCHO / 2) / ANCHO)
            base = 150
            partes.append(f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{RELLENO}" stroke="{TRAZO_SUAVE}" stroke-width="0.9"/>')
            self.v.incluir(x, base - h)
            for fy in range(int(base - h + 6), base - 4, 9):
                ventanas.append(((x + 3, fy), (x + w - 3, fy)))
            x += w + self.rnd.uniform(-4, 6)
        partes.append(_segmentos(ventanas, TRAZO_SUAVE, 0.4, 'opacity="0.6"'))
        self.add("".join(partes), 1)

    def svg(self):
        cuerpo = "".join(s for _, s in sorted(self.capas, key=lambda c: c[0]))
        # Encuadre: el viewBox se ajusta a lo dibujado (con margen) y mantiene la proporción 16:10,
        # así los estadios grandes (3 anillos, arco, skyline) no quedan cortados ni pegados al borde.
        x0, y0, x1, y1 = self.v.caja
        margen = 14
        x0, y0, x1, y1 = x0 - margen, y0 - margen, x1 + margen, y1 + margen
        w, h = x1 - x0, y1 - y0
        if w / h > ANCHO / ALTO:
            nh = w * ALTO / ANCHO
            y0, h = y0 - (nh - h) / 2, nh
        else:
            nw = h * ANCHO / ALTO
            x0, w = x0 - (nw - w) / 2, nw
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.0f} {y0:.0f} {w:.0f} {h:.0f}" width="{ANCHO}" height="{ALTO}" '
                f'stroke-linejoin="round" stroke-linecap="round">{cuerpo}</svg>')


# --- Catálogo de diseños ------------------------------------------------------------------------
# Los 8 primeros son los de la muestra aprobada; el resto combina las mismas piezas (cada forma con
# cada tipo de techo, variando anillos y extras) para llegar a 36 diseños distintos.
DISENOS = [
    {"forma": "oval", "anillos": 2, "techo": "anillo", "fachada": "costillas"},
    {"forma": "rect", "anillos": 2, "techo": None, "torres": True},
    {"forma": "oval", "anillos": 3, "techo": "membrana", "entorno": "arboles"},
    {"forma": "rect", "anillos": 1, "techo": "laterales", "focos": True},
    {"forma": "circulo", "anillos": 2, "techo": "membrana"},
    {"forma": "rect", "anillos": 3, "techo": "arco"},
    {"forma": "octogono", "anillos": 2, "techo": "principal", "focos": True, "entorno": "skyline"},
    {"forma": "rect", "anillos": 2, "techo": "anillo", "torres": True, "entorno": "skyline"},
]


def _completar_catalogo(total=36):
    formas = ["oval", "rect", "circulo", "octogono"]
    techos = [None, "anillo", "membrana", "laterales", "principal", "arco"]
    entornos = [None, "arboles", "skyline"]
    vistos = {tuple(sorted((k, v) for k, v in d.items() if v)) for d in DISENOS}
    i = 0
    while len(DISENOS) < total:
        forma = formas[i % len(formas)]
        techo = techos[(i // len(formas) + i) % len(techos)]
        d = {
            "forma": forma,
            "anillos": 1 + (i * 7 // 3) % 3,
            "techo": techo,
            "torres": forma in ("rect", "octogono") and i % 3 == 1,
            "focos": techo in (None, "laterales", "principal") and i % 2 == 0,
            "entorno": entornos[(i // 2) % 3],
            "fachada": "costillas" if i % 4 == 0 else None,
        }
        clave = tuple(sorted((k, v) for k, v in d.items() if v))
        if clave not in vistos:
            vistos.add(clave)
            DISENOS.append(d)
        i += 1


_completar_catalogo()

# --- Paleta: el color de acento de cada país es el de esta lista más parecido al de su bandera -------
PALETA = [
    "#ef4444", "#f97316", "#f59e0b", "#eab308", "#84cc16", "#22c55e",
    "#10b981", "#06b6d4", "#38bdf8", "#3b82f6", "#6366f1", "#a855f7",
]
CARPETA_BUCKET = "gs://com-icg-mundial/estadios"


def nombre_archivo(diseno: int, color: int) -> str:
    """Ruta dentro del bucket (lo que se guarda en ciudades.estadio_imagen)."""
    return f"estadios/d{diseno + 1:02d}-c{color + 1:02d}.svg"


def generar(carpeta):
    """Los 36 diseños x 12 colores (432 SVG) en <carpeta>/estadios/."""
    destino = os.path.join(carpeta, "estadios")
    os.makedirs(destino, exist_ok=True)
    for di, d in enumerate(DISENOS):
        for ci, color in enumerate(PALETA):
            with open(os.path.join(carpeta, nombre_archivo(di, ci)), "w") as f:
                f.write(Estadio(d, color, semilla=di).dibujar())
    print(f"{len(DISENOS) * len(PALETA)} SVG en {destino}")


def _colores_bandera(url):
    """Índices de PALETA de los 2 colores más presentes (y saturados) de la bandera. Requiere Pillow."""
    import colorsys
    import io
    import ssl
    import urllib.request
    from collections import Counter

    import certifi
    from PIL import Image

    contexto = ssl.create_default_context(cafile=certifi.where())  # el Python de macOS no trae certificados propios
    datos = urllib.request.urlopen(url, timeout=20, context=contexto).read()
    imagen = Image.open(io.BytesIO(datos)).convert("RGBA").resize((32, 32))
    tonos = Counter()
    for r, g, b, a in imagen.getdata():
        if a < 200:
            continue
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        if s < 0.35 or v < 0.25:  # blanco, negro y grises no cuentan
            continue
        tonos[min(range(len(PALETA)), key=lambda i: _distancia_tono(h, PALETA[i]))] += 1
    elegidos = [i for i, _ in tonos.most_common(2)]
    if not elegidos:
        return [9, 8]  # banderas sin color saturado: azul / celeste
    if len(elegidos) == 1:
        elegidos.append((elegidos[0] + 6) % len(PALETA))  # el opuesto en la paleta
    return elegidos


def _distancia_tono(h, color_hex):
    import colorsys
    r, g, b = (int(color_hex[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h2 = colorsys.rgb_to_hsv(r, g, b)[0]
    d = abs(h - h2)
    return min(d, 1 - d)


def asignar():
    """
    Guarda en cada ciudad su imagen (ciudades.estadio_imagen). Dentro de un país no se repite el
    diseño: las primeras 36 ciudades (por id) van con el color principal de la bandera y, si el país
    tiene más, las siguientes repiten diseños con el segundo color. Determinístico (semilla = pais_id):
    volver a correrlo da el mismo resultado. Campo permanente: restart_mundial no lo toca.
    """
    from urllib.parse import quote
    from pymongo import UpdateOne
    from config.settings import IMAGENES_PAISES_URL
    from services.imagenes_pais_service import db

    paises = {p["id"]: p["nombre"] for p in db["paises"].find({}, {"id": 1, "nombre": 1})}
    ciudades_por_pais = {}
    for c in db["ciudades"].find({}, {"id": 1, "pais_id": 1}).sort("id", 1):
        ciudades_por_pais.setdefault(c["pais_id"], []).append(c["id"])

    operaciones, sin_color = [], []
    for pais_id, ids in ciudades_por_pais.items():
        try:
            colores = _colores_bandera(f"{IMAGENES_PAISES_URL}/bandera/{quote(paises[pais_id])}.png")
        except Exception as e:  # sin bandera: colores por defecto
            sin_color.append((pais_id, str(e)))
            colores = [9, 8]
        orden = list(range(len(DISENOS)))
        random.Random(pais_id).shuffle(orden)
        for k, ciudad_id in enumerate(ids):
            imagen = nombre_archivo(orden[k % len(DISENOS)], colores[(k // len(DISENOS)) % 2])
            operaciones.append(UpdateOne({"id": ciudad_id}, {"$set": {"estadio_imagen": imagen}}))
    resultado = db["ciudades"].bulk_write(operaciones)
    print(f"Ciudades actualizadas: {resultado.modified_count} de {len(operaciones)} | países sin color de bandera: {len(sin_color)}")
    for pais_id, error in sin_color[:5]:
        print(f"  ⚠️ país {pais_id}: {error}")


def subir(carpeta):
    """Vacía estadios/ en el bucket y sube los SVG (comprimidos, con caché de 7 días)."""
    import subprocess
    subprocess.run(["gcloud", "storage", "rm", f"{CARPETA_BUCKET}/**", "-q"], check=False)
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "estadios", "*.svg"), f"{CARPETA_BUCKET}/",
                    "--gzip-local-all", "--content-type=image/svg+xml",
                    "--cache-control=public, max-age=604800", "-q"], check=True)


def muestra(carpeta):
    os.makedirs(carpeta, exist_ok=True)
    colores = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#a855f7", "#06b6d4", "#ec4899", "#84cc16"]
    for i, d in enumerate(DISENOS):
        with open(os.path.join(carpeta, f"d{i + 1:02d}.svg"), "w") as f:
            f.write(Estadio(d, colores[i % len(colores)], semilla=i).dibujar())
    print(f"{len(DISENOS)} diseños de muestra en {carpeta}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "estadios_generados"
    if modo == "--muestra":
        muestra(carpeta)
    elif modo == "--generar":
        generar(carpeta)
    elif modo == "--asignar":
        asignar()
    elif modo == "--subir":
        subir(carpeta)
    else:
        print(__doc__)
