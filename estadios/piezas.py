"""
Piezas reutilizables de los estadios: perfiles y patrones de fachada, cubiertas y extras. Todo se dibuja con las
mismas herramientas de base.py (superficie paramétrica S(t, h), anillos y capas ordenadas).
"""
import math

from estadios.base import (EstadioBase, O_ATRAS, O_FACHADA, O_FONDO, O_FRENTE, O_TAPA, O_TECHO, RELLENO,
                           TRAZO, TRAZO_SUAVE, casco, polilineas, pts, segmentos)

DOS_PI = 2 * math.pi
VERDE = "#4ade80"


class Estadio(EstadioBase):

    # ================================================================ PERFILES (distancia de la fachada según la altura)
    def recto(self, extra: float = 0.0):
        d = self.d_ext + extra
        return lambda h: d

    def concavo(self, prof: float = 6.0, alto: float = None):
        d, a = self.d_ext + 2, alto or self.z_top
        return lambda h: d - prof * math.sin(math.pi * min(1.0, h / a))

    def tronco(self, ensanche: float = 9.0, alto: float = None):
        """Troncocónico: más ancho arriba (vasija)."""
        d, a = self.d_ext, alto or self.z_top
        return lambda h: d - ensanche * 0.35 + ensanche * (h / a)

    def abombado(self, prof: float = 5.0, alto: float = None):
        d, a = self.d_ext, alto or self.z_top
        return lambda h: d + prof * math.sin(math.pi * min(1.0, h / a))

    # ================================================================ FACHADA BASE
    def fachada(self, perfil, alto: float, nervios: int = 3, bandas=(0.33, 0.66), borde=None, relleno=RELLENO, ancho_borde=2.2):
        """Silueta, nervaduras verticales, bandas horizontales, borde inferior y remate superior en color."""
        self.silueta(perfil, alto, relleno)
        n = self.N
        lineas = []
        if nervios:
            for i in range(0, n, nervios):
                t = DOS_PI * i / n
                lineas += self.curva([(t, alto * k / 8) for k in range(9)], perfil)
        for f in bandas:
            lineas += self.curva([(DOS_PI * i / n, alto * f) for i in range(n + 1)], perfil)
        self.add(polilineas(lineas, TRAZO_SUAVE, 0.85), O_FACHADA)
        self.borde_inferior(perfil)
        if borde:
            arriba = self.curva([(DOS_PI * i / n, alto) for i in range(n + 1)], perfil, solo_frente=False)
            self.add(polilineas(arriba, borde, ancho_borde), O_FACHADA + 0.6)

    # ================================================================ PATRONES DE FACHADA (curvas en (t, h))
    def p_columnas(self, perfil, alto, n=48, color=TRAZO, ancho=1.6, desde=0.0, doble=False):
        lineas = []
        for i in range(n):
            t = DOS_PI * i / n
            lineas += self.curva([(t, alto * desde), (t, alto)], perfil)
            if doble:
                t2 = t + DOS_PI / n / 2
                lineas += self.curva([(t2, alto * desde), (t2, alto)], lambda h, p=perfil: p(h) + 3.5)
        self.add(polilineas(lineas, color, ancho), O_FACHADA + 0.3)

    def p_contrafuertes(self, perfil, alto, n=64, salida=6.0, color=TRAZO):
        segs = []
        for i in range(n):
            t = DOS_PI * i / n
            if not self.frente(t, perfil(0)) or self.en_hueco(t):
                continue
            pie = self.punto(perfil(0) + salida, 0, t)
            cabeza = self.punto(perfil(alto * 0.85), alto * 0.85, t)
            arriba = self.punto(perfil(alto), alto, t)
            segs += [(pie, cabeza), (cabeza, arriba)]
        self.add(segmentos(segs, color, 1.5), O_FACHADA + 0.3)

    def p_celosia(self, perfil, alto, n=36, color=None, ancho=1.0, curva=0.0):
        """Celosía diagonal en las dos direcciones (rombos), opcionalmente curvada."""
        color = color or self.P
        lineas, dt = [], DOS_PI / n
        for i in range(n):
            t0 = DOS_PI * i / n
            for sentido in (1, -1):
                lineas += self.curva([(t0 + sentido * dt * 2 * (k / 10) + curva * math.sin(math.pi * k / 10) * dt, alto * k / 10) for k in range(11)], perfil)
        self.add(polilineas(lineas, color, ancho), O_FACHADA + 0.3)

    def p_red(self, perfil, alto, n=46, color=None):
        """Red entrelazada irregular (nido de pájaro)."""
        color = color or self.P
        lineas = []
        for i in range(n):
            t0 = DOS_PI * i / n + self.rnd.uniform(-0.05, 0.05)
            amp = self.rnd.uniform(0.15, 0.4) * self.rnd.choice((1, -1))
            lineas += self.curva([(t0 + amp * (k / 12) + 0.06 * math.sin(k * 0.9 + i), alto * k / 12) for k in range(13)], perfil)
        self.add(polilineas(lineas, color, 1.3), O_FACHADA + 0.3)
        self.add(polilineas(lineas[::3], TRAZO, 0.6, 'opacity="0.6"'), O_FACHADA + 0.35)

    def p_escamas(self, perfil, alto, filas=6, cols=40, color=None):
        color = color or self.P
        lineas = []
        dt, dh = DOS_PI / cols, alto / filas
        for f in range(filas):
            for c in range(cols):
                t = DOS_PI * c / cols + (dt / 2 if f % 2 else 0)
                h0 = dh * f
                rombo = [(t, h0), (t + dt / 2, h0 + dh / 2), (t, h0 + dh), (t - dt / 2, h0 + dh / 2), (t, h0)]
                lineas += self.curva(rombo, perfil)
        self.add(polilineas(lineas, color, 0.9), O_FACHADA + 0.3)

    def p_hexagonos(self, perfil, alto, filas=5, cols=34, color=None, aberturas=True):
        color = color or self.P
        lineas, puntos_ab = [], []
        dt, dh = DOS_PI / cols, alto / filas
        for f in range(filas):
            for c in range(cols):
                t = DOS_PI * c / cols + (dt / 2 if f % 2 else 0)
                h = dh * (f + 0.5)
                hexa = [(t + dt * 0.5 * math.cos(math.pi / 3 * k), h + dh * 0.55 * math.sin(math.pi / 3 * k)) for k in range(7)]
                lineas += self.curva(hexa, perfil)
                if aberturas and (f + c) % 3 == 0 and self.frente(t, perfil(h)) and not self.en_hueco(t):
                    puntos_ab.append(self.S_(t, h, perfil))
        self.add(polilineas(lineas, color, 0.9), O_FACHADA + 0.3)
        if puntos_ab:
            self.add("".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" fill="{self.D}" opacity="0.8"/>' for x, y in puntos_ab), O_FACHADA + 0.35)

    def p_triangulos(self, perfil, alto, filas=4, cols=30, color=None, sombreado=True):
        """Facetas triangulares (diamante): retícula de triángulos, algunos con relleno."""
        color = color or self.P
        lineas, caras = [], []
        dt, dh = DOS_PI / cols, alto / filas
        for f in range(filas):
            for c in range(cols):
                t = DOS_PI * c / cols + (dt / 2 if f % 2 else 0)
                h0, h1 = dh * f, dh * (f + 1)
                tri = [(t, h0), (t + dt, h0), (t + dt / 2, h1), (t, h0)]
                lineas += self.curva(tri, perfil)
                if sombreado and (c + f) % 4 == 0 and all(self.frente(tt, perfil(hh)) and not self.en_hueco(tt) for tt, hh in tri):
                    caras.append([self.S_(tt, hh, perfil) for tt, hh in tri[:3]])
        self.add("".join(f'<polygon points="{pts(c)}" fill="{color}" fill-opacity="0.18" stroke="none"/>' for c in caras), O_FACHADA + 0.2)
        self.add(polilineas(lineas, color, 0.9), O_FACHADA + 0.3)

    def p_lamas(self, perfil, alto, n=90, ondas=4, color=None, ancho_t=0.03):
        """Lamas verticales que rotan con una onda (fachada paramétrica)."""
        color = color or self.P
        segs = []
        for i in range(n):
            t = DOS_PI * i / n
            if not self.frente(t, perfil(0)) or self.en_hueco(t):
                continue
            giro = math.sin(t * ondas) * ancho_t
            for k in range(6):
                h0, h1 = alto * k / 6, alto * (k + 1) / 6
                segs.append((self.S_(t - giro, h0, perfil), self.S_(t + giro, h1, perfil)))
        self.add(segmentos(segs, color, 1.0), O_FACHADA + 0.3)

    def p_vidrio(self, perfil, alto, cols=72, filas=6, color=None):
        color = color or self.S
        self.silueta(perfil, alto, RELLENO)
        caras = []
        for i in range(0, cols, 1):
            t = DOS_PI * i / cols
            if not self.frente(t, perfil(0)) or self.en_hueco(t):
                continue
            t2 = t + DOS_PI / cols
            caras.append([self.S_(t, 0, perfil), self.S_(t2, 0, perfil), self.S_(t2, alto, perfil), self.S_(t, alto, perfil)])
        self.add("".join(f'<polygon points="{pts(c)}" fill="{color}" fill-opacity="{0.10 + 0.08 * (k % 3) / 2:.2f}" stroke="none"/>' for k, c in enumerate(caras)), O_FACHADA)
        lineas = []
        for i in range(cols):
            lineas += self.curva([(DOS_PI * i / cols, 0), (DOS_PI * i / cols, alto)], perfil)
        for f in range(1, filas):
            lineas += self.curva([(DOS_PI * k / self.N, alto * f / filas) for k in range(self.N + 1)], perfil)
        self.add(polilineas(lineas, TRAZO_SUAVE, 0.6), O_FACHADA + 0.3)

    def p_grecas(self, perfil, h0, h1, motivos=48, color=None):
        """Greca escalonada (vasija prehispánica) en una banda horizontal."""
        color = color or self.D
        dt = DOS_PI / motivos
        curva = []
        for m in range(motivos):
            t = m * dt
            a, b, c = h0, (h0 + h1) / 2, h1
            curva += [(t, a), (t, c), (t + dt * 0.5, c), (t + dt * 0.5, b), (t + dt * 0.25, b), (t + dt * 0.25, a + (b - a) * 0.4),
                      (t + dt * 0.75, a + (b - a) * 0.4), (t + dt * 0.75, a)]
        curva.append((DOS_PI, h0))
        self.add(polilineas(self.curva(curva, perfil), color, 1.2), O_FACHADA + 0.4)

    def p_mimbre(self, perfil, alto, n=44, color=None):
        """Tejido entrecruzado (cesta): ondas diagonales en dos sentidos."""
        color = color or self.P
        lineas, dt = [], DOS_PI / n
        for i in range(n):
            t0 = DOS_PI * i / n
            for s in (1, -1):
                lineas += self.curva([(t0 + s * dt * 3 * k / 16 + 0.25 * dt * math.sin(k * 1.6), alto * k / 16) for k in range(17)], perfil)
        self.add(polilineas(lineas, color, 1.1), O_FACHADA + 0.3)

    def p_franjas(self, perfil, alto, colores, desde=0.15, hasta=0.55):
        """Franjas horizontales con los colores de la bandera."""
        k = len(colores)
        for j, color in enumerate(colores):
            h = alto * (desde + (hasta - desde) * (j + 0.5) / k)
            self.add(polilineas(self.curva([(DOS_PI * i / self.N, h) for i in range(self.N + 1)], perfil), color, 2.2), O_FACHADA + 0.45)

    def p_led(self, perfil, t_centro, ancho_t, h0, h1, color=None):
        color = color or self.D
        caras = [self.S_(t_centro - ancho_t, h0, perfil), self.S_(t_centro + ancho_t, h0, perfil),
                 self.S_(t_centro + ancho_t, h1, perfil), self.S_(t_centro - ancho_t, h1, perfil)]
        self.add(f'<polygon points="{pts(caras)}" fill="{color}" fill-opacity="0.35" stroke="{color}" stroke-width="1.2"/>', O_FACHADA + 0.5)

    def p_helice(self, perfil, alto, n=8, vueltas=0.5, color=None, ancho=1.6):
        """Rampas o líneas helicoidales alrededor."""
        color = color or self.P
        lineas = []
        for i in range(n):
            t0 = DOS_PI * i / n
            lineas += self.curva([(t0 + DOS_PI * vueltas * k / 30, alto * k / 30) for k in range(31)], perfil)
        self.add(polilineas(lineas, color, ancho), O_FACHADA + 0.35)

    # ================================================================ CUBIERTAS
    def c_anillo(self, desp: float, z: float, vuelo: float, t0=0.0, t1=DOS_PI, color=None, triangulado=False, cerchas=True,
                 opacidad=0.16, alza=7.0, columnas=True, z_interior=None):
        color = color or self.P
        ze, zi = z + alza, (z + alza if z_interior is None else z_interior)
        exterior = self.anillo(desp, ze, t0, t1)
        interior = self.anillo(desp - vuelo, zi, t0, t1)
        completo = t1 - t0 >= DOS_PI - 1e-6
        if completo:
            d = f'M{pts(exterior)} Z M{pts(list(reversed(interior)))} Z'
            partes = [f'<path d="{d}" fill="{color}" fill-opacity="{opacidad}" fill-rule="evenodd" stroke="{color}" stroke-width="1.6"/>']
        else:
            partes = [f'<polygon points="{pts(exterior + list(reversed(interior)))}" fill="{color}" fill-opacity="{opacidad}" stroke="{color}" stroke-width="1.6"/>']
        n = len(exterior)
        if cerchas:
            paso = 3 if triangulado else 4
            partes.append(segmentos([(exterior[i], interior[i]) for i in range(0, n, paso)], color, 0.8, 'opacity="0.85"'))
            if triangulado:
                partes.append(segmentos([(exterior[i], interior[min(n - 1, i + 3)]) for i in range(0, n - 3, 3)], color, 0.6, 'opacity="0.7"'))
        if columnas:
            base = self.anillo(desp, z, t0, t1)
            partes.append(segmentos([(base[i], exterior[i]) for i in range(0, n, 6)], TRAZO, 1))
        self.add("".join(partes), O_TECHO)
        return exterior, interior

    def c_membrana_mastiles(self, desp, z, mastiles=8, alto_mastil=34, vuelo=20, color=None):
        """Cubierta textil sostenida por mástiles altos y tirantes."""
        color = color or self.P
        ext, inte = self.c_anillo(desp, z, vuelo, color=color, triangulado=False, cerchas=False, opacidad=0.22)
        n = len(ext)
        for k in range(mastiles):
            t = DOS_PI * (k + 0.5) / mastiles
            i = int(n * (k + 0.5) / mastiles) % n
            pie, punta = self.punto(desp + 4, 0, t), self.punto(desp + 4, z + alto_mastil, t)
            tirantes = [(punta, inte[(i + j) % n]) for j in (-4, 0, 4)] + [(punta, self.punto(desp + 14, 0, t))]
            orden = self.orden_por(t, O_ATRAS, O_FRENTE)
            self.add(segmentos([(pie, punta)], TRAZO, 2.0) + segmentos(tirantes, TRAZO_SUAVE, 0.7), orden)

    def c_petalos(self, desp, z, k=4, alto=26, color=None, ancho_t=None):
        """Grandes pétalos que se inclinan hacia el centro."""
        color = color or self.P
        ancho_t = ancho_t or (DOS_PI / k) * 0.42
        for j in range(k):
            tc = DOS_PI * j / k + DOS_PI / (2 * k)
            # pétalo en punta: nace ancho en el borde exterior, sube y se cierra en una punta inclinada hacia el centro
            izq, der = [], []
            for m in range(11):
                f = m / 10
                ancho = ancho_t * math.sin(math.pi * (0.15 + 0.85 * f) / 1.0) * (1 - f) ** 0.5
                d = desp + 2 - 30 * f ** 1.6
                h = z + alto * math.sin(math.pi * 0.5 * f) ** 0.8
                izq.append(self.punto(d, h, tc - max(0.02, ancho)))
                der.append(self.punto(d, h, tc + max(0.02, ancho)))
            punta_in = self.punto(desp - 28, z + alto, tc)
            nervio = [self.punto(desp + 2 - 30 * (m / 10) ** 1.6, z + alto * math.sin(math.pi * 0.05 * m) ** 0.8, tc) for m in range(11)]
            costillas = [(izq[m], nervio[min(10, m + 2)]) for m in range(1, 9, 2)] + [(der[m], nervio[min(10, m + 2)]) for m in range(1, 9, 2)]
            poli = izq + [punta_in] + list(reversed(der))
            orden = self.orden_por(tc, O_TECHO - 1, O_TECHO + 2)
            self.add(f'<polygon points="{pts(poli)}" fill="{color}" fill-opacity="0.22" stroke="{color}" stroke-width="1.6"/>'
                     + polilineas([nervio], color, 1.0) + segmentos(costillas, color, 0.6, 'opacity="0.8"'), orden)

    def c_cupula(self, desp, z, alto=30, meridianos=24, paralelos=5, triangulada=True, color=None, abierta=0.0):
        """Cúpula de malla (geodésica o reticular) sobre todo el estadio. 'abierta' = tamaño relativo del óculo."""
        color = color or self.P
        from estadios.base import contorno
        def P(t, f):
            r = math.cos(f * math.pi / 2)
            x, y = contorno(self.forma, (self.a0 + desp) * r, (self.b0 + desp) * r, t)
            return self.v.p(x, y, z + alto * math.sin(f * math.pi / 2))
        tope = 1.0 - (abierta or 0.06)
        lineas = []
        for p in range(paralelos + 1):
            f = tope * p / paralelos
            lineas.append([P(DOS_PI * i / 48, f) for i in range(49)])
        for m in range(meridianos):
            t = DOS_PI * m / meridianos
            lineas.append([P(t, tope * q / 10) for q in range(11)])
            if triangulada:
                t2 = t + DOS_PI / meridianos
                for p in range(paralelos):
                    f0, f1 = tope * p / paralelos, tope * (p + 1) / paralelos
                    lineas.append([P(t, f0), P(t2, f1)] if p % 2 == 0 else [P(t2, f0), P(t, f1)])
        silueta = casco([q for l in lineas for q in l])
        self.add(f'<polygon points="{pts(silueta)}" fill="{color}" fill-opacity="0.07" stroke="none"/>', O_TECHO)
        self.add(polilineas(lineas, color, 0.8, 'opacity="0.85"'), O_TECHO + 0.5)

    def c_ola(self, desp, z, vuelo=22, amplitud=14, color=None):
        """Cubierta asimétrica ondulante: el borde exterior sube y baja como una ola."""
        color = color or self.P
        n = self.N
        ext = [self.punto(desp, z + 6 + amplitud * (0.5 + 0.5 * math.sin(DOS_PI * i / n * 2 + 0.6)) * (0.6 + 0.4 * math.cos(DOS_PI * i / n)), DOS_PI * i / n) for i in range(n)]
        inte = [self.punto(desp - vuelo, z + 4 + amplitud * 0.4 * (0.5 + 0.5 * math.sin(DOS_PI * i / n * 2 + 1.2)), DOS_PI * i / n) for i in range(n)]
        d = f'M{pts(ext)} Z M{pts(list(reversed(inte)))} Z'
        self.add(f'<path d="{d}" fill="{color}" fill-opacity="0.2" fill-rule="evenodd" stroke="{color}" stroke-width="1.8"/>'
                 + segmentos([(ext[i], inte[i]) for i in range(0, n, 3)], color, 0.7, 'opacity="0.7"')
                 + segmentos([(self.punto(desp, z, DOS_PI * i / n), ext[i]) for i in range(0, n, 8)], TRAZO, 1), O_TECHO)

    def c_hojas(self, desp, z, vuelo=26, alto=20, color=None):
        """Dos grandes cubiertas laterales curvas con nervaduras (hoja)."""
        color = color or self.P
        for (a, b) in ((math.radians(25), math.radians(155)), (math.radians(205), math.radians(335))):
            n = 40
            ext = [self.punto(desp + 6, z + 4 + alto * math.sin(math.pi * i / n), a + (b - a) * i / n) for i in range(n + 1)]
            inte = [self.punto(desp - vuelo, z + 8 + alto * 0.5 * math.sin(math.pi * i / n), a + (b - a) * i / n) for i in range(n + 1)]
            nervio = [self.punto(desp - vuelo / 2, z + 6 + alto * 0.85 * math.sin(math.pi * i / n), a + (b - a) * i / n) for i in range(n + 1)]
            nervaduras = [(nervio[i], ext[min(n, i + 3)]) for i in range(2, n - 2, 3)] + [(nervio[i], inte[min(n, i + 3)]) for i in range(2, n - 2, 3)]
            orden = self.orden_por((a + b) / 2, O_TECHO - 1, O_TECHO + 1)
            self.add(f'<polygon points="{pts(ext + list(reversed(inte)))}" fill="{color}" fill-opacity="0.2" stroke="{color}" stroke-width="1.8"/>'
                     + polilineas([nervio], color, 1.3) + segmentos(nervaduras, color, 0.6, 'opacity="0.8"'), orden)

    def c_vela(self, desp, z, color=None):
        """Dos mástiles altos con velas tensadas (velero)."""
        color = color or self.P
        for t, alto, lado in ((math.radians(150), 70, 1), (math.radians(330), 52, -1)):
            pie = self.punto(desp + 2, 0, t)
            punta = self.punto(desp + 2, z + alto, t)
            ext_vela = [self.punto(desp - 10, z + 6, t + lado * 0.9), self.punto(desp - 30, z + 4, t + lado * 0.4)]
            vela = [punta, ext_vela[0], ext_vela[1], self.punto(desp + 2, z + 8, t)]
            orden = self.orden_por(t, O_TECHO - 1, O_TECHO + 2)
            self.add(f'<polygon points="{pts(vela)}" fill="{color}" fill-opacity="0.24" stroke="{color}" stroke-width="1.6"/>'
                     + segmentos([(pie, punta)], TRAZO, 2.2)
                     + segmentos([(punta, self.punto(desp + 18, 0, t + lado * 0.2)), (punta, self.punto(desp + 18, 0, t - lado * 0.2))], TRAZO_SUAVE, 0.7), orden)

    def c_abanico(self, desp, z, varillas=14, radio=60, color=None):
        """Cubierta semicircular que se abre como abanico sobre la tribuna principal (del fondo)."""
        color = color or self.P
        v = self.v
        y_piv = -(self.b0 + desp) - 4
        pivote = v.p(0, y_piv, z + 2)
        puntas = []
        for k in range(varillas + 1):
            ang = math.pi * k / varillas
            puntas.append(v.p(radio * math.cos(ang) * 1.5, y_piv + radio * 0.35 * math.sin(ang), z + 12 + 46 * math.sin(ang)))
        pliegues = "".join(f'<polygon points="{pts([pivote, puntas[k], puntas[k + 1]])}" fill="{color}" fill-opacity="{0.12 if k % 2 else 0.26}" stroke="none"/>' for k in range(varillas))
        self.add(pliegues + segmentos([(pivote, q) for q in puntas], color, 1.1) + polilineas([puntas], color, 1.8), O_TECHO + 1)

    def c_arco(self, desp, z, alto=62, color=None, tirantes=True, cruzado=False):
        """Gran arco que cruza el estadio (sobre la tribuna del fondo o en diagonal)."""
        color = color or self.P
        v = self.v
        a = self.a0 + desp + 8
        y = -(self.b0 + desp) * (0.0 if cruzado else 0.55)
        p1 = [v.p(-a + 2 * a * i / 60, y, z + 6 + alto * math.sin(math.pi * i / 60)) for i in range(61)]
        p2 = [v.p(-a + 2 * a * i / 60, y, z + 6 + (alto - 7) * math.sin(math.pi * i / 60)) for i in range(61)]
        partes = [polilineas([p1], color, 2.6), polilineas([p2], color, 1.2),
                  segmentos([(p1[i], p2[i + 1]) for i in range(0, 60, 2)] + [(p1[i + 1], p2[i]) for i in range(0, 60, 2)], color, 0.7)]
        if tirantes:
            partes.append(segmentos([(p2[i], v.p(-a + 2 * a * i / 60, y, z + 7)) for i in range(6, 56, 5)], TRAZO_SUAVE, 0.6, 'opacity="0.7"'))
        self.add("".join(partes), O_TECHO + 3)

    def c_solar(self, desp, z, color=None, celdas=(14, 8)):
        """Cubierta plana inclinada con celdas fotovoltaicas."""
        color = color or self.P
        v = self.v
        a, b = self.a0 + desp + 2, self.b0 + desp + 2
        def q(fx, fy):
            return v.p(-a + 2 * a * fx, -b + 2 * b * fy, z + 14 + 10 * (1 - fy))
        esq = [q(0, 0), q(1, 0), q(1, 1), q(0, 1)]
        cols, filas = celdas
        lineas = [[q(i / cols, 0), q(i / cols, 1)] for i in range(1, cols)] + [[q(0, j / filas), q(1, j / filas)] for j in range(1, filas)]
        soportes = [(q(fx, fy), v.p(-a + 2 * a * fx, -b + 2 * b * fy, z)) for fx in (0.02, 0.98) for fy in (0.02, 0.98)]
        self.add(f'<polygon points="{pts(esq)}" fill="{color}" fill-opacity="0.18" stroke="{color}" stroke-width="1.8"/>'
                 + polilineas(lineas, color, 0.6, 'opacity="0.8"') + segmentos(soportes, TRAZO, 1.6), O_TECHO + 2)

    def c_mobius(self, desp, z, color=None):
        """Cinta continua retorcida: bordes que se cruzan dos veces alrededor."""
        color = color or self.P
        n = self.N
        def borde(fase):
            return [self.punto(desp - 9 + 11 * math.cos(DOS_PI * i / n / 2 + fase), z + 10 + 9 * math.sin(DOS_PI * i / n / 2 + fase), DOS_PI * i / n) for i in range(n + 1)]
        borde_a, borde_b = borde(0.0), borde(math.pi)
        caras = "".join(f'<polygon points="{pts([borde_a[i], borde_a[i + 3], borde_b[i + 3], borde_b[i]])}" fill="{color}" fill-opacity="0.12" stroke="none"/>' for i in range(0, n - 2, 3))
        self.add(caras, O_TECHO)
        reglas = [(borde_a[i], borde_b[i]) for i in range(0, n, 3)]
        self.add(polilineas([borde_a], color, 2.2) + polilineas([borde_b], self.S, 2.0) + segmentos(reglas, color, 0.6, 'opacity="0.7"'), O_TECHO + 1)

    def c_doble_desfasado(self, desp, z, color=None):
        """Dos anillos de cubierta a distinta altura, segmentados y rotados entre sí."""
        color = color or self.P
        for k, (dz, fase, col) in enumerate(((0, 0.0, color), (9, DOS_PI / 16, self.S))):
            for j in range(8):
                t0 = fase + DOS_PI * j / 8
                self.c_anillo(desp - 3 * k, z + dz, 15, t0, t0 + DOS_PI / 8 * 0.8, color=col, cerchas=True, columnas=(k == 0), opacidad=0.18)

    def cuatro_mastiles(self, desp, z, alto=58, color=None):
        """Cuatro pilonos en las esquinas que sostienen la cubierta con tensores."""
        color = color or self.P
        ext, inte = self.c_anillo(desp, z, 18, color=color, cerchas=True, opacidad=0.16, columnas=False)
        n = len(ext)
        for ang in (40, 140, 220, 320):
            t = math.radians(ang)
            x, y = self.xy(desp + 12, t)
            pie, punta = self.v.p(x, y, 0), self.v.p(x, y, z + alto)
            i = int(n * ang / 360) % n
            cables = [(punta, ext[(i + j) % n]) for j in range(-10, 11, 4)]
            orden = self.orden_por(t, O_ATRAS, O_FRENTE)
            self.add(segmentos([(pie, punta)], TRAZO, 2.6) + segmentos([(self.v.p(x - 1.5, y, 0), punta), (self.v.p(x + 1.5, y, 0), punta)], TRAZO_SUAVE, 0.8)
                     + segmentos(cables, color, 0.7, 'opacity="0.85"'), orden + 0.5)

    # ================================================================ EXTRAS
    def cilindro(self, x, y, r, z0, z1, helice=True, color=None):
        color = color or self.P
        v, n = self.v, 28
        abajo = [v.p(x + r * math.cos(DOS_PI * i / n), y + r * math.sin(DOS_PI * i / n), z0) for i in range(n)]
        arriba = [v.p(x + r * math.cos(DOS_PI * i / n), y + r * math.sin(DOS_PI * i / n), z1) for i in range(n)]
        cuerpo = casco(abajo + arriba)
        partes = [f'<polygon points="{pts(cuerpo)}" fill="{RELLENO}" stroke="{TRAZO}" stroke-width="1.1"/>']
        if helice:
            for b in range(1, 6):
                zb = z0 + (z1 - z0) * b / 6
                frente = [v.p(x + r * math.cos(math.pi * i / 14), y + r * math.sin(math.pi * i / 14), zb + 1.6 * math.cos(math.pi * i / 14)) for i in range(15)]
                partes.append(polilineas([frente], color, 1))
        partes.append(f'<polygon points="{pts(arriba)}" fill="{RELLENO}" stroke="{TRAZO}" stroke-width="1.1"/>')
        return "".join(partes)

    def torres_esquina(self, desp, z, r=7.5, helice=True, angulos=(40, 140, 220, 320)):
        for ang in angulos:
            t = math.radians(ang)
            x, y = self.xy(desp + 7, t)
            self.add(self.cilindro(x, y, r, 0, z + 4, helice), self.orden_por(t, O_ATRAS, O_FRENTE) + self.v.p(x, y)[1] / 1000)

    def focos(self, desp, z, alto=34, angulos=(35, 145, 215, 325)):
        v = self.v
        for ang in angulos:
            t = math.radians(ang)
            x, y = self.xy(desp + 5, t)
            p0, p1 = v.p(x, y, 0), v.p(x, y, z + alto)
            panel = [v.p(x - 4, y, z + alto), v.p(x + 4, y, z + alto), v.p(x + 4, y, z + alto + 6), v.p(x - 4, y, z + alto + 6)]
            self.add(segmentos([(p0, p1)], TRAZO, 1.6) + f'<polygon points="{pts(panel)}" fill="{self.D}" fill-opacity="0.35" stroke="{TRAZO}" stroke-width="1"/>',
                     self.orden_por(t, O_ATRAS - 1, O_FRENTE + 1))

    def escalinata(self, desp, ancho=34, escalones=7, t=None):
        """Escalinata monumental frente a la fachada (lado de adelante)."""
        v = self.v
        t = t if t is not None else math.radians(90 + 18)   # hacia el espectador
        x, y = self.xy(desp, t)
        ux, uy = math.cos(t), math.sin(t)
        px, py = -uy, ux
        partes = []
        for k in range(escalones):
            off = 3 + k * 2.2
            z = (escalones - k) * 1.3
            a = v.p(x + ux * off - px * ancho / 2, y + uy * off - py * ancho / 2, z)
            b = v.p(x + ux * off + px * ancho / 2, y + uy * off + py * ancho / 2, z)
            partes.append((a, b))
        self.add(segmentos(partes, TRAZO, 1.1) + segmentos([(partes[0][0], partes[-1][0]), (partes[0][1], partes[-1][1])], self.P, 1.6), O_FRENTE + 2)

    def arco_triunfo(self, desp, z, t=None):
        """Arco monumental en la entrada principal (adelante)."""
        v = self.v
        t = t if t is not None else math.radians(90 + 18)
        x, y = self.xy(desp + 16, t)
        px, py = -math.sin(t), math.cos(t)
        def q(o, h):
            return v.p(x + px * o, y + py * o, h)
        alto = z + 30
        exterior = [q(-22, 0), q(-22, alto), q(22, alto), q(22, 0), q(12, 0)] + [q(12 * math.cos(math.pi * k / 16), alto * 0.62 + 10 * math.sin(math.pi * k / 16)) for k in range(17)] + [q(-12, 0)]
        self.add(f'<polygon points="{pts(exterior)}" fill="{RELLENO}" stroke="{TRAZO}" stroke-width="1.6"/>'
                 + segmentos([(q(-22, alto - 5), q(22, alto - 5)), (q(-22, alto * 0.62 + 10), q(-12, alto * 0.62 + 10)), (q(12, alto * 0.62 + 10), q(22, alto * 0.62 + 10))], self.P, 1.4)
                 + segmentos([(q(o, 0), q(o, alto - 5)) for o in (-18, 18)], TRAZO_SUAVE, 0.8), O_FRENTE + 3)

    def skyline(self, alto_max=120, base=None):
        v = self.v
        partes, ventanas = [], []
        base = base if base is not None else v.cy - 70
        x = v.cx - 290
        while x < v.cx + 290:
            w = self.rnd.uniform(14, 30)
            h = self.rnd.uniform(40, alto_max) * (1 - abs(x - v.cx) / 640)
            partes.append(f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{RELLENO}" stroke="{TRAZO_SUAVE}" stroke-width="0.9"/>')
            v.incluir(x, base - h)
            for fy in range(int(base - h + 6), int(base) - 4, 9):
                ventanas.append(((x + 3, fy), (x + w - 3, fy)))
            x += w + self.rnd.uniform(-4, 6)
        partes.append(segmentos(ventanas, TRAZO_SUAVE, 0.4, 'opacity="0.6"'))
        self.add("".join(partes), O_FONDO)

    def torres_oficinas(self, desp, z, cantidad=3, color=None):
        """Torres de oficinas pegadas al estadio (del lado de atrás), con fachadas de vidrio."""
        color = color or self.S
        v = self.v
        for k in range(cantidad):
            t = math.radians(215 + k * 55)
            x, y = self.xy(desp + 10, t)
            w, d, h = 16, 12, z + 60 + 25 * ((k + 1) % 2)
            caras = [[v.p(x - w, y - d, 0), v.p(x + w, y - d, 0), v.p(x + w, y - d, h), v.p(x - w, y - d, h)],
                     [v.p(x + w, y - d, 0), v.p(x + w, y + d, 0), v.p(x + w, y + d, h), v.p(x + w, y - d, h)],
                     [v.p(x - w, y - d, h), v.p(x + w, y - d, h), v.p(x + w, y + d, h), v.p(x - w, y + d, h)],
                     [v.p(x - w, y + d, 0), v.p(x + w, y + d, 0), v.p(x + w, y + d, h), v.p(x - w, y + d, h)]]
            pisos = [(v.p(x - w, y + d, hh), v.p(x + w, y + d, hh)) for hh in range(6, int(h), 6)]
            parte = "".join(f'<polygon points="{pts(c)}" fill="{RELLENO}" stroke="{TRAZO}" stroke-width="1"/>' for c in caras)
            parte += f'<polygon points="{pts(caras[3])}" fill="{color}" fill-opacity="0.12" stroke="none"/>' + segmentos(pisos, TRAZO_SUAVE, 0.5)
            self.add(parte, O_ATRAS - 1 + k * 0.1)

    def arboles(self, desp, cantidad=34, r=(5.0, 7.0)):
        v = self.v
        atras, frente = [], []
        for i in range(cantidad):
            t = DOS_PI * i / cantidad + self.rnd.uniform(-0.05, 0.05)
            x, y = self.xy(desp + 16, t)
            px, py = v.p(x, y, 0)
            rr = self.rnd.uniform(*r)
            arbol = (f'<line x1="{px:.1f}" y1="{py:.1f}" x2="{px:.1f}" y2="{py - rr * 1.6:.1f}" stroke="{TRAZO_SUAVE}" stroke-width="1"/>'
                     f'<circle cx="{px:.1f}" cy="{py - rr * 2.2:.1f}" r="{rr:.1f}" fill="{RELLENO}" stroke="{VERDE}" stroke-width="1" stroke-opacity="0.7"/>')
            (frente if v.profundidad(x, y) > 0 else atras).append(arbol)
        self.add("".join(atras), O_ATRAS - 2)
        self.add("".join(frente), O_FRENTE + 4)

    def dunas(self, desp, lineas=5):
        curvas = []
        for k in range(lineas):
            dd = desp + 8 + k * 7
            curvas += self.curva([(DOS_PI * i / self.N, 1.2 * math.sin(i * 0.35 + k)) for i in range(self.N + 1)], lambda h, d=dd: d)
        self.add(polilineas(curvas, self.D, 0.7, 'opacity="0.55"'), O_FRENTE + 1)

    def banderines(self, desp, z, cantidad=16, colores=None):
        colores = colores or [self.P, self.S, self.D]
        partes = []
        for k in range(cantidad):
            t = DOS_PI * k / cantidad
            if not self.frente(t, desp):
                continue
            pie, punta = self.punto(desp, z, t), self.punto(desp, z + 12, t)
            tela = [punta, (punta[0] + 7, punta[1] + 2), (punta[0], punta[1] + 4)]
            partes.append(segmentos([(pie, punta)], TRAZO_SUAVE, 0.8) + f'<polygon points="{pts(tela)}" fill="{colores[k % len(colores)]}" stroke="none"/>')
        self.add("".join(partes), O_FRENTE + 1)
