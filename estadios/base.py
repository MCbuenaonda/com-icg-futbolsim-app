"""
Base del motor de estadios: proyección 3/4, plantas, superficie paramétrica de la fachada, gradas, cancha y encuadre.

La fachada se modela como una superficie S(t, h): t = ángulo alrededor de la planta (0..2π), h = altura (0..alto);
su distancia a la cancha la da un PERFIL(h) (recto, cóncavo, troncocónico...). Cualquier patrón de fachada (columnas,
celosía, escamas, hexágonos, lamas...) es un conjunto de curvas en (t, h) que se proyectan y se dibujan solo en la
mitad visible (la de adelante).
"""
import math
import random

ANCHO, ALTO = 640, 400

TRAZO = "#e2e8f0"          # líneas principales (claras, para el tema oscuro)
TRAZO_SUAVE = "#94a3b8"    # filas de gradas, detalles
RELLENO = "#141c2e"        # relleno de superficies (tapa lo que queda detrás)
RELLENO_GRADAS = "#1b2640"
CESPED = "#1f5f3a"
CESPED_FRANJA = "#26704a"
LINEAS_CANCHA = "#a7f3c7"

# Orden de las capas (se pintan de menor a mayor)
O_FONDO, O_SOMBRA, O_ATRAS, O_FACHADA, O_TAPA, O_GRADAS, O_CANCHA, O_TECHO, O_FRENTE = 1, 2, 5, 10, 20, 30, 40, 50, 65


def pts(puntos) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in puntos)


def segmentos(segs, color, ancho, extra="") -> str:
    """Muchas líneas sueltas con el mismo estilo en un solo <path> (los SVG pesan bastante menos)."""
    segs = [s for s in segs if s]
    if not segs:
        return ""
    d = "".join(f"M{a[0]:.1f} {a[1]:.1f}L{b[0]:.1f} {b[1]:.1f}" for a, b in segs)
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{ancho}" {extra}/>'


def polilineas(lineas, color, ancho, extra="") -> str:
    """Varias polilíneas con el mismo estilo en un solo <path>."""
    d = "".join("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in l) for l in lineas if len(l) > 1)
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{ancho}" {extra}/>' if d else ""


def casco(puntos):
    """Casco convexo (cadena monótona): silueta rellena de una pieza."""
    p = sorted(set((round(x, 1), round(y, 1)) for x, y in puntos))
    if len(p) < 3:
        return p

    def cruz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    abajo, arriba = [], []
    for q in p:
        while len(abajo) >= 2 and cruz(abajo[-2], abajo[-1], q) <= 0:
            abajo.pop()
        abajo.append(q)
    for q in reversed(p):
        while len(arriba) >= 2 and cruz(arriba[-2], arriba[-1], q) <= 0:
            arriba.pop()
        arriba.append(q)
    return abajo[:-1] + arriba[:-1]


def contorno(forma: str, a: float, b: float, t: float):
    """Punto del borde de la planta en el parámetro t. Formas: oval, circulo, rect, caja, octogono, poligono:<k>."""
    c, s = math.cos(t), math.sin(t)
    if forma.startswith("poligono"):
        k = int(forma.split(":")[1])
        seg = 2 * math.pi / k
        r = math.cos(math.pi / k) / math.cos((t % seg) - math.pi / k)
        return a * c * r, b * s * r
    n = {"oval": 2.0, "circulo": 2.0, "rect": 4.5, "caja": 9.0, "octogono": 3.0}.get(forma, 2.0)
    return a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s)


class Vista:
    """Proyecta coordenadas del mundo (x a lo largo de la cancha, y a lo ancho, z altura) a la imagen."""

    def __init__(self, giro_grados=-18.0, aplastado=0.52, escala=2.25, cx=ANCHO / 2, cy=ALTO / 2 + 18):
        self.c, self.s = math.cos(math.radians(giro_grados)), math.sin(math.radians(giro_grados))
        self.k, self.e, self.cx, self.cy = aplastado, escala, cx, cy
        self.caja = [math.inf, math.inf, -math.inf, -math.inf]

    def p(self, x, y, z=0.0):
        xr = x * self.c - y * self.s
        yr = x * self.s + y * self.c
        punto = (self.cx + xr * self.e, self.cy + yr * self.e * self.k - z * self.e * 0.62)
        self.incluir(*punto)
        return punto

    def profundidad(self, x, y) -> float:
        """> 0: hacia el frente de la imagen (más cerca del espectador)."""
        return x * self.s + y * self.c

    def incluir(self, x, y):
        c = self.caja
        c[0], c[1], c[2], c[3] = min(c[0], x), min(c[1], y), max(c[2], x), max(c[3], y)


class EstadioBase:
    """
    Un estadio: planta + gradas + cancha + lo que agregue cada concepto (fachada, cubierta, extras).
    paleta = {principal, secundario, detalle}; espejo = vista desde el otro lado (variante).
    """
    MEDIDAS = {"oval": (74, 50), "circulo": (66, 66), "rect": (61, 43), "caja": (61, 43), "octogono": (66, 47)}

    def __init__(self, paleta: dict, forma: str = "oval", anillos: int = 2, semilla: int = 0, espejo: bool = False,
                 hueco=None, cy_extra: float = 0.0):
        self.pal = paleta
        self.P, self.S, self.D = paleta["principal"], paleta["secundario"], paleta["detalle"]
        self.forma = forma
        self.a0, self.b0 = self.MEDIDAS.get(forma, (68, 52)) if not forma.startswith("poligono") else (70, 54)
        self.anillos = anillos
        self.hueco = hueco            # (t0, t1): sector sin tribuna (herradura)
        self.rnd = random.Random(semilla)
        self.v = Vista(giro_grados=18.0 if espejo else -18.0, cy=ALTO / 2 + 18 + cy_extra)
        self.capas = []
        self.N = 96
        self._niveles = None

    # --- geometría ---
    def xy(self, desp: float, t: float):
        return contorno(self.forma, self.a0 + desp, self.b0 + desp, t)

    def punto(self, desp: float, z: float, t: float):
        x, y = self.xy(desp, t)
        return self.v.p(x, y, z)

    def en_hueco(self, t: float) -> bool:
        if not self.hueco:
            return False
        t = t % (2 * math.pi)
        a, b = self.hueco
        return a <= t <= b

    def anillo(self, desp: float, z: float, t0: float = 0.0, t1: float = 2 * math.pi, n: int = None):
        n = n or self.N
        completo = t1 - t0 >= 2 * math.pi - 1e-6
        return [self.punto(desp, z, t0 + (t1 - t0) * i / n) for i in range(n + (0 if completo else 1))]

    def frente(self, t: float, desp: float = 0.0) -> bool:
        x, y = self.xy(desp, t)
        return self.v.profundidad(x, y) > -0.12 * (self.b0 + desp)

    def add(self, svg: str, orden: float = 0):
        if svg:
            self.capas.append((orden, svg))

    def orden_por(self, t: float, base_atras: float = O_ATRAS, base_frente: float = O_FRENTE) -> float:
        """Orden para piezas sueltas alrededor (torres, mástiles): las de atrás detrás de la fachada."""
        x, y = self.xy(0, t)
        return base_frente if self.v.profundidad(x, y) > 0 else base_atras

    # --- niveles de gradas ---
    def niveles(self):
        if self._niveles is None:
            res, d, z = [], 4.0, 1.0
            for i in range(self.anillos):
                prof, alto = (15.0, 12.5) if i == 0 else (12.0, 11.5)
                res.append((d, z, d + prof, z + alto))
                d, z = d + prof + 2.5, z + alto + 2.5
            self._niveles = res
        return self._niveles

    @property
    def d_ext(self):
        return self.niveles()[-1][2] + 1.5

    @property
    def z_top(self):
        return self.niveles()[-1][3]

    # --- superficie de la fachada ---
    def S_(self, t: float, h: float, perfil):
        return self.punto(perfil(h), h, t)

    def visibles(self, n: int = None, desp: float = 0.0):
        n = n or self.N
        return [i for i in range(n) if self.frente(2 * math.pi * i / n, desp) and not self.en_hueco(2 * math.pi * i / n)]

    def curva(self, puntos_th, perfil, solo_frente=True):
        """Curva de la superficie dada como [(t, h)] → lista de tramos visibles (polilíneas en pantalla)."""
        tramos, actual = [], []
        for t, h in puntos_th:
            ok = (not solo_frente or self.frente(t, perfil(h))) and not self.en_hueco(t)
            if ok:
                actual.append(self.S_(t, h, perfil))
            elif actual:
                tramos.append(actual)
                actual = []
        if actual:
            tramos.append(actual)
        return tramos

    def silueta(self, perfil, alto: float, relleno: str = RELLENO, extra: str = ""):
        """Relleno de la fachada (tapa lo de atrás): casco de los anillos a varias alturas."""
        puntos = []
        for f in (0, 0.25, 0.5, 0.75, 1.0):
            h = alto * f
            puntos += self.anillo(perfil(h), h, n=48)
        self.add(f'<polygon points="{pts(casco(puntos))}" fill="{relleno}" stroke="none" {extra}/>', O_FACHADA - 0.5)

    def borde_inferior(self, perfil):
        segs = []
        base = self.anillo(perfil(0), 0)
        n = len(base)
        for i in range(n):
            t = 2 * math.pi * i / n
            if self.frente(t, perfil(0)) and not self.en_hueco(t):
                segs.append((base[i], base[(i + 1) % n]))
        self.add(segmentos(segs, TRAZO, 1.4), O_FACHADA + 0.4)

    def tapa(self, desp: float, z: float, color_borde: str = None, ancho: float = 2.0, hueco_interior: float = None):
        """Superficie superior de la fachada (tapa la parte trasera) con el borde en color."""
        ext = self.anillo(desp, z)
        if hueco_interior is not None:
            inte = self.anillo(hueco_interior, z)
            d = f'M{pts(ext)} Z M{pts(list(reversed(inte)))} Z'
            self.add(f'<path d="{d}" fill="{RELLENO}" fill-rule="evenodd" stroke="{TRAZO}" stroke-width="1.4"/>', O_TAPA)
        else:
            self.add(f'<polygon points="{pts(ext)}" fill="{RELLENO}" stroke="{TRAZO}" stroke-width="1.4"/>', O_TAPA)
        if color_borde:
            self.add(f'<polygon points="{pts(ext)}" fill="none" stroke="{color_borde}" stroke-width="{ancho}"/>', O_TAPA + 0.1)

    # --- gradas, cancha y sombra ---
    def sombra(self, desp: float):
        self.add(f'<polygon points="{pts(self.anillo(desp + 9, 0, n=60))}" fill="#000" opacity="0.25"/>', O_SOMBRA)

    def gradas(self):
        for (di, zi, de, ze) in reversed(self.niveles()):
            if self.hueco:
                a, b = self.hueco
                t0, t1 = b, a + 2 * math.pi
                ext, inte = self.anillo(de, ze, t0, t1), self.anillo(di, zi, t0, t1)
                cuerpo = ext + list(reversed(inte))
                partes = [f'<polygon points="{pts(cuerpo)}" fill="{RELLENO_GRADAS}" stroke="{TRAZO}" stroke-width="1.2"/>']
                for f in range(1, 5):
                    r = f / 5
                    partes.append(polilineas([self.anillo(di + (de - di) * r, zi + (ze - zi) * r, t0, t1)], self.S, 0.6, 'opacity="0.55"'))
                n = len(ext)
                partes.append(segmentos([(inte[i], ext[i]) for i in range(0, n, 6)], TRAZO_SUAVE, 0.7))
            else:
                ext, inte = self.anillo(de, ze), self.anillo(di, zi)
                partes = [f'<polygon points="{pts(ext)}" fill="{RELLENO_GRADAS}" stroke="{TRAZO}" stroke-width="1.2"/>']
                for f in range(1, 5):
                    r = f / 5
                    partes.append(f'<polygon points="{pts(self.anillo(di + (de - di) * r, zi + (ze - zi) * r))}" fill="none" stroke="{self.S}" stroke-width="0.6" opacity="0.55"/>')
                n = len(ext)
                partes.append(segmentos([(inte[i], ext[i]) for i in range(0, n, 6)], TRAZO_SUAVE, 0.7))
                partes.append(f'<polygon points="{pts(inte)}" fill="{RELLENO}" stroke="{TRAZO}" stroke-width="1"/>')
            self.add("".join(partes), O_GRADAS - di / 100)

    def cancha(self):
        v = self.v
        L, W, z = 52.5, 34.0, 1.0

        def rect(x0, y0, x1, y1):
            return pts([v.p(x0, y0, z), v.p(x1, y0, z), v.p(x1, y1, z), v.p(x0, y1, z)])

        def circ(cx, cy, r, n=40):
            return pts([v.p(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n), z) for i in range(n + 1)])

        partes = [f'<polygon points="{rect(-L - 3, -W - 3, L + 3, W + 3)}" fill="{CESPED}"/>']
        for i in range(10):
            if i % 2:
                x0 = -L + 2 * L * i / 10
                partes.append(f'<polygon points="{rect(x0, -W, x0 + 2 * L / 10, W)}" fill="{CESPED_FRANJA}"/>')
        lc = f'fill="none" stroke="{LINEAS_CANCHA}" stroke-width="1"'
        partes.append(f'<polygon points="{rect(-L, -W, L, W)}" {lc}/>')
        partes.append(f'<polyline points="{pts([v.p(0, -W, z), v.p(0, W, z)])}" {lc}/>')
        partes.append(f'<polyline points="{circ(0, 0, 9.15)}" {lc}/>')
        for s in (-1, 1):
            partes.append(f'<polygon points="{rect(s * L, -20.15, s * (L - 16.5), 20.15)}" {lc}/>')
            partes.append(f'<polygon points="{rect(s * L, -9.16, s * (L - 5.5), 9.16)}" {lc}/>')
            partes.append(f'<polygon points="{rect(s * L, -3.66, s * (L + 1.8), 3.66)}" fill="none" stroke="{TRAZO}" stroke-width="1"/>')
        self.add("".join(partes), O_CANCHA)

    def basico(self):
        """Sombra, gradas y cancha: lo que tienen todos."""
        self.sombra(self.d_ext + 4)
        self.gradas()
        self.cancha()

    # --- salida ---
    def svg(self, titulo: str = "") -> str:
        cuerpo = "".join(s for _, s in sorted(self.capas, key=lambda c: c[0]))
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
        t = f"<title>{titulo}</title>" if titulo else ""
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.0f} {y0:.0f} {w:.0f} {h:.0f}" width="{ANCHO}" height="{ALTO}" '
                f'stroke-linejoin="round" stroke-linecap="round">{t}{cuerpo}</svg>')
