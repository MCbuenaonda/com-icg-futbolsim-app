"""
Piezas nuevas (ampliación del catálogo a ~145 conceptos): fachadas de rombos, cuadros, arcos, paneles, ladrillo,
horizontales, perforada y zigzag; cubiertas de rueda de cables, picos, visera, dientes de sierra, cubierta verde, y el
agua alrededor. Misma convención que piezas.py: curvas en (t, h) sobre la fachada y capas ordenadas.
"""
import math

from estadios.base import O_ATRAS, O_FACHADA, O_SOMBRA, O_TECHO, RELLENO, TRAZO, TRAZO_SUAVE, polilineas, pts, segmentos
from estadios.piezas import DOS_PI, VERDE, Estadio

AGUA = "#38bdf8"


class EstadioV3(Estadio):

    # ================================================================ FACHADAS
    def _celdas(self, perfil, alto, filas, cols, relleno_fn, margen=0.0):
        """Celdas (i, k) como polígonos sobre la fachada; relleno_fn(i, k) -> (color, opacidad) o None."""
        dt, dh = DOS_PI / cols, alto / filas
        partes = []
        for i in range(cols):
            t0 = i * dt
            if not self.frente(t0 + dt / 2, perfil(alto / 2)) or self.en_hueco(t0):
                continue
            for k in range(filas):
                rf = relleno_fn(i, k)
                if not rf:
                    continue
                m = margen * dt
                c = [self.S_(t0 + m, dh * k + margen * dh, perfil), self.S_(t0 + dt - m, dh * k + margen * dh, perfil),
                     self.S_(t0 + dt - m, dh * (k + 1) - margen * dh, perfil), self.S_(t0 + m, dh * (k + 1) - margen * dh, perfil)]
                partes.append(f'<polygon points="{pts(c)}" fill="{rf[0]}" fill-opacity="{rf[1]}" stroke="none"/>')
        return "".join(partes)

    def p_rombos(self, perfil, alto, filas=4, cols=28, color=None, relleno=True):
        """Retícula de rombos (fachada de rombos alternados)."""
        color = color or self.P
        dt, dh = DOS_PI / cols, alto / filas
        caras, lineas = [], []
        for k in range(filas + 1):
            for i in range(cols):
                tc = (i + 0.5 * (k % 2)) * dt
                hc = k * dh
                if not self.frente(tc, perfil(min(alto, hc))):
                    continue
                pu = [(tc, max(0, hc - dh)), (tc + dt / 2, hc), (tc, min(alto, hc + dh)), (tc - dt / 2, hc)]
                poly = [self.S_(t, h, perfil) for t, h in pu]
                if relleno and (i + k) % 2 == 0:
                    caras.append(f'<polygon points="{pts(poly)}" fill="{color}" fill-opacity="0.38" stroke="none"/>')
                lineas.append(poly + [poly[0]])
        self.add("".join(caras), O_FACHADA + 0.2)
        self.add(polilineas(lineas, color, 0.9), O_FACHADA + 0.3)

    def p_cuadros(self, perfil, alto, filas=5, cols=40, color=None):
        """Tablero: cuadros alternados con retícula."""
        color = color or self.P
        self.add(self._celdas(perfil, alto, filas, cols, lambda i, k: (color, 0.34) if (i + k) % 2 == 0 else None), O_FACHADA + 0.2)
        lineas = []
        for k in range(filas + 1):
            lineas += self.curva([(DOS_PI * i / self.N, alto * k / filas) for i in range(self.N + 1)], perfil)
        for i in range(cols):
            lineas += self.curva([(DOS_PI * i / cols, 0), (DOS_PI * i / cols, alto)], perfil)
        self.add(polilineas(lineas, TRAZO_SUAVE, 0.7), O_FACHADA + 0.3)

    def p_paneles(self, perfil, alto, filas=3, cols=28, colores=None):
        """Paneles separados con colores alternados (principal / secundario / detalle)."""
        cs = colores or [self.P, self.S, self.D]
        self.add(self._celdas(perfil, alto, filas, cols, lambda i, k: (cs[(i + 2 * k) % len(cs)], 0.5), margen=0.08), O_FACHADA + 0.2)

    def p_arcos(self, perfil, alto, filas=2, cols=44, color=None):
        """Arcadas de medio punto en hileras (coliseo, plaza de toros)."""
        color = color or TRAZO
        dt = DOS_PI / cols
        hileras = alto / filas
        lineas = []
        for f in range(filas):
            base = hileras * f
            h1, h2 = base + hileras * 0.52, base + hileras * 0.88
            for i in range(cols):
                t0, t1 = i * dt + dt * 0.12, i * dt + dt * 0.88
                arco = [(t0, base), (t0, h1)] + [(t0 + (t1 - t0) * u / 10, h1 + (h2 - h1) * math.sin(math.pi * u / 10)) for u in range(11)] + [(t1, h1), (t1, base)]
                lineas += self.curva(arco, perfil)
            lineas += self.curva([(DOS_PI * i / self.N, base + hileras) for i in range(self.N + 1)], perfil)
        self.add(polilineas(lineas, color, 1.0), O_FACHADA + 0.3)

    def p_ladrillo(self, perfil, alto, filas=12, cols=40, color=None):
        """Aparejo de ladrillo: hiladas con las juntas verticales desfasadas."""
        color = color or self.P
        dt = DOS_PI / cols
        horiz, vert = [], []
        for k in range(filas + 1):
            horiz += self.curva([(DOS_PI * i / self.N, alto * k / filas) for i in range(self.N + 1)], perfil)
        for k in range(filas):
            for i in range(cols):
                t = (i + 0.5 * (k % 2)) * dt
                vert += self.curva([(t, alto * k / filas), (t, alto * (k + 1) / filas)], perfil)
        self.add(polilineas(horiz, color, 0.8, 'opacity="0.75"') + polilineas(vert, color, 0.6, 'opacity="0.55"'), O_FACHADA + 0.3)

    def p_horizontales(self, perfil, alto, n=12, color=None):
        """Listones horizontales (persiana): líneas gruesas y finas alternadas."""
        color = color or self.P
        gruesas, finas = [], []
        for k in range(1, n + 1):
            linea = self.curva([(DOS_PI * i / self.N, alto * k / (n + 1)) for i in range(self.N + 1)], perfil)
            (gruesas if k % 2 else finas).extend(linea)
        self.add(polilineas(gruesas, color, 2.0, 'opacity="0.8"') + polilineas(finas, TRAZO_SUAVE, 0.8), O_FACHADA + 0.3)

    def p_perforada(self, perfil, alto, filas=6, cols=56, color=None):
        """Chapa perforada: malla de puntos."""
        color = color or self.S
        dt, dh = DOS_PI / cols, alto / (filas + 1)
        puntos = []
        for k in range(1, filas + 1):
            for i in range(cols):
                t = (i + 0.5 * (k % 2)) * dt
                if self.frente(t, perfil(dh * k)) and not self.en_hueco(t):
                    puntos.append(self.S_(t, dh * k, perfil))
        self.add("".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.25" fill="{color}" fill-opacity="0.85"/>' for x, y in puntos), O_FACHADA + 0.3)

    def p_zigzag(self, perfil, alto, filas=3, picos=36, color=None):
        """Líneas en zigzag horizontales (plegado)."""
        color = color or self.P
        lineas = []
        for k in range(filas):
            base, amp = alto * (k + 0.5) / filas, alto / filas * 0.32
            lineas += self.curva([(DOS_PI * j / (picos * 2), base + (amp if j % 2 else -amp)) for j in range(picos * 2 + 1)], perfil)
        self.add(polilineas(lineas, color, 1.3), O_FACHADA + 0.3)

    # ================================================================ CUBIERTAS
    def c_rueda(self, desp, z, vuelo=26, radios=36, alza=8.0, color=None):
        """Cubierta de rueda de bicicleta: anillo exterior, anillo interior y radios de cable."""
        color = color or self.P
        ze = z + alza
        ext, inte = self.anillo(desp, ze), self.anillo(desp - vuelo, ze - 3)
        n = len(ext)
        d = f'M{pts(ext)} Z M{pts(list(reversed(inte)))} Z'
        partes = [f'<path d="{d}" fill="{color}" fill-opacity="0.14" fill-rule="evenodd" stroke="{color}" stroke-width="1.6"/>',
                  segmentos([(ext[i], inte[i]) for i in range(0, n, max(1, n // radios))], color, 0.7, 'opacity="0.9"'),
                  segmentos([(self.punto(desp, z, DOS_PI * i / n), ext[i]) for i in range(0, n, 8)], TRAZO, 1.0)]
        self.add("".join(partes), O_TECHO)

    def c_picos(self, desp, z, k=8, alto=40.0, vuelo=16.0, color=None):
        """Carpa de picos: una vela triangular por tramo, con su cumbre sobre el anillo."""
        color = color or self.P
        base = self.anillo(desp, z + 4, n=k * 4)
        base_i = self.anillo(desp - vuelo, z + 4, n=k * 4)
        for j in range(k):
            ta, tb = DOS_PI * j / k, DOS_PI * (j + 1) / k
            if self.frente((ta + tb) / 2, desp):      # los del lado de la cámara taparían la cancha: solo el lado de atrás
                continue
            a, b = base[4 * j], base[(4 * j + 4) % len(base)]
            ci = base_i[4 * j + 2]
            apice = self.punto(desp - vuelo * 0.12, z + alto, (ta + tb) / 2)
            tri = f'<polygon points="{pts([a, b, apice])}" fill="{color}" fill-opacity="0.24" stroke="{color}" stroke-width="1.5"/>'
            nervios = segmentos([(apice, ci), (apice, base_i[4 * j]), (apice, base_i[(4 * j + 4) % len(base)])], color, 0.7, 'opacity="0.85"')
            self.add(tri + nervios, self.orden_por((ta + tb) / 2, O_ATRAS, O_TECHO))

    def c_visera(self, desp, z, t0=0.1, t1=3.0, vuelo=38.0, alza=26.0, color=None):
        """Visera inclinada sobre una tribuna: alta por fuera y baja hacia la cancha, con pilones en los extremos."""
        color = color or self.P
        t0, t1 = t0 + math.pi, t1 + math.pi        # el lado de atrás (visto desde la cámara), para no tapar la cancha
        ext, inte = self.c_anillo(desp, z, vuelo, t0=t0, t1=t1, color=color, triangulado=True, opacidad=0.2, alza=alza, z_interior=z + 4)
        base0, base1 = self.punto(desp, 0, t0), self.punto(desp, 0, t1)
        self.add(segmentos([(base0, ext[0]), (base1, ext[-1]), (ext[0], inte[0]), (ext[-1], inte[-1])], TRAZO, 1.6), O_TECHO + 0.1)

    def c_dientes(self, desp, z, vuelo=22.0, k=24, alto=9.0, color=None):
        """Cubierta en dientes de sierra: el borde exterior sube y baja."""
        color = color or self.P
        n = k * 2
        ext = [self.punto(desp, z + 7 + (alto if j % 2 else 0), DOS_PI * j / n) for j in range(n)]
        inte = [self.punto(desp - vuelo, z + 7, DOS_PI * j / n) for j in range(n)]
        d = f'M{pts(ext)} Z M{pts(list(reversed(inte)))} Z'
        self.add(f'<path d="{d}" fill="{color}" fill-opacity="0.2" fill-rule="evenodd" stroke="{color}" stroke-width="1.6"/>'
                 + segmentos([(ext[j], inte[j]) for j in range(0, n, 2)], color, 0.8, 'opacity="0.85"'), O_TECHO)

    def c_verde(self, desp, z, vuelo=30.0, alza=7.0):
        """Cubierta verde (azotea ajardinada) con parches de vegetación."""
        ext, inte = self.c_anillo(desp, z, vuelo, color=VERDE, cerchas=False, opacidad=0.42, alza=alza, columnas=True)
        n = len(ext)
        self.add(segmentos([(ext[i], inte[i]) for i in range(0, n, 3)], VERDE, 0.9, 'opacity="0.55"'), O_TECHO + 0.1)

    # ================================================================ EXTRAS
    def agua(self, desp, ancho=34.0, color=AGUA):
        """Estadio sobre un lago o foso: espejo de agua alrededor con ondas."""
        ext, inte = self.anillo(desp + ancho, -1.0, n=72), self.anillo(desp + 2, -1.0, n=72)
        d = f'M{pts(ext)} Z M{pts(list(reversed(inte)))} Z'
        ondas = "".join(f'<polygon points="{pts(self.anillo(desp + ancho * f, -1.0, n=72))}" fill="none" stroke="{color}" stroke-width="0.8" '
                        f'stroke-opacity="0.55" stroke-dasharray="{4 + 2 * i} {5}"/>' for i, f in enumerate((0.45, 0.7, 0.9)))
        self.add(f'<path d="{d}" fill="{color}" fill-opacity="0.2" fill-rule="evenodd" stroke="{color}" stroke-width="1.2" stroke-opacity="0.7"/>' + ondas, O_SOMBRA + 0.5)
