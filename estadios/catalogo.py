"""
Los 50 conceptos de estadios (plantilla maestra del usuario, 5 grupos). Cada uno: codigo, nombre, grupo, forma de la
planta, anillos de gradas y una función que arma su arquitectura con las piezas de estadios/piezas.py. Los culturales
llevan 'regiones' (generar_avatares.REGION_POR_PAIS) y/o 'costero': se asignan con preferencia donde encajan.
"""
import math

from estadios.base import O_FACHADA, O_FRENTE, O_TAPA, O_TECHO, RELLENO, TRAZO, TRAZO_SUAVE, contorno, polilineas, pts, segmentos
from estadios.piezas import DOS_PI, VERDE, Estadio

GRUPOS = {1: "Clásicos y exoesqueléticos", 2: "Orgánicos y tensados", 3: "Geométricos y paramétricos",
          4: "Culturales y simbólicos", 5: "Alta tecnología y urbanos"}


def _std(e, perfil=None, alto=None, nervios=3, bandas=(0.33, 0.66), borde=True):
    """Lo común: sombra, gradas, cancha, fachada y tapa con el remate en el color principal."""
    perfil = perfil or e.recto()
    alto = alto if alto is not None else e.z_top
    e.basico()
    e.fachada(perfil, alto, nervios=nervios, bandas=bandas, borde=e.P if borde else None)
    e.tapa(perfil(alto), alto, None)
    return perfil, alto


# ===================================================================== GRUPO 1: clásicos y exoesqueléticos
def metropolitano_clasico(e):
    perfil, alto = _std(e, nervios=0, bandas=(0.5,))
    e.p_columnas(perfil, alto, n=40, color=TRAZO, ancho=2.2)
    e.focos(e.d_ext, alto, alto=40)


def coliseo_acero(e):
    perfil, alto = _std(e, nervios=0, bandas=())
    e.p_celosia(perfil, alto, n=32, curva=0.8, ancho=1.2)
    e.c_anillo(e.d_ext, alto, 28, triangulado=True, opacidad=0.12)


def anillo_concavo(e):
    perfil, alto = _std(e, e.concavo(7), nervios=2, bandas=(0.5,))
    e.c_anillo(perfil(alto), alto, 14, opacidad=0.14, alza=4)


def cilindro_columnado(e):
    perfil, alto = _std(e, e.recto(1), nervios=0, bandas=())
    e.p_columnas(perfil, alto, n=60, color=TRAZO, ancho=1.8)
    e.add(polilineas(e.curva([(DOS_PI * i / e.N, alto * 0.9) for i in range(e.N + 1)], perfil), e.D, 1.2), O_FACHADA + 0.5)
    e.c_anillo(e.d_ext + 1, alto, 18, triangulado=True, opacidad=0.22)


def rotonda_monumental(e):
    perfil, alto = _std(e, e.recto(2), nervios=0, bandas=())
    e.p_columnas(perfil, alto, n=28, color=e.P, ancho=3.0)
    e.p_led(perfil, math.radians(108), 0.35, alto * 0.45, alto * 0.85)
    e.escalinata(e.d_ext + 2, ancho=46, escalones=9)


def gigante_concreto(e):
    perfil, alto = _std(e, nervios=4, bandas=(0.2, 0.4, 0.6, 0.8))
    e.torres_esquina(e.d_ext, alto, r=8, helice=True, angulos=(30, 90, 150, 210, 270, 330))


def anfiteatro_modular(e):
    perfil, alto = _std(e, nervios=0, bandas=(0.5,))
    e.p_columnas(perfil, alto, n=8, color=e.P, ancho=3.2)
    e.p_columnas(perfil, alto * 0.5, n=32, color=TRAZO_SUAVE, ancho=0.9)
    e.c_membrana_mastiles(e.d_ext, alto, mastiles=8, alto_mastil=30, vuelo=18)


def ovalo_pilares(e):
    perfil, alto = _std(e, nervios=0, bandas=(0.66,))
    e.p_contrafuertes(perfil, alto, n=64, salida=7, color=e.P)


def rotonda_doble_columna(e):
    perfil, alto = _std(e, nervios=0, bandas=())
    e.p_columnas(perfil, alto, n=64, color=TRAZO_SUAVE, ancho=1.0, doble=True)
    e.add(polilineas(e.curva([(DOS_PI * i / e.N, alto) for i in range(e.N + 1)], lambda h: perfil(h) + 3.5), e.P, 2.0), O_FACHADA + 0.6)


def anillo_tradicional(e):
    perfil, alto = _std(e)
    e.c_anillo(e.d_ext, alto, 18, triangulado=False, opacidad=0.18)


# ===================================================================== GRUPO 2: orgánicos, biomiméticos y tensados
def nido_pajaro(e):
    perfil, alto = _std(e, e.abombado(6, None), nervios=0, bandas=(), borde=False)
    e.p_red(perfil, alto, n=56)
    e.c_anillo(perfil(alto), alto, 20, cerchas=False, opacidad=0.1, alza=3, columnas=False)


def capullo_loto(e):
    perfil, alto = _std(e, nervios=4, bandas=(0.5,))
    e.c_petalos(e.d_ext, alto, k=8, alto=44, ancho_t=0.36)


def ola_marina(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.c_ola(e.d_ext, alto, vuelo=24, amplitud=16)


def piel_serpiente(e):
    perfil, alto = _std(e, nervios=0, bandas=(), borde=True)
    e.p_escamas(perfil, alto, filas=6, cols=42)


def caparazon_tortuga(e):
    perfil, alto = _std(e, nervios=0, bandas=(), borde=False)
    e.p_hexagonos(perfil, alto, filas=3, cols=30, aberturas=False)
    e.c_cupula(e.d_ext, alto, alto=34, meridianos=18, paralelos=3, triangulada=False, abierta=0.45)


def hoja_tropical(e):
    perfil, alto = _std(e, nervios=4, bandas=(0.5,))
    e.c_hojas(e.d_ext, alto, vuelo=26, alto=22)


def coral_marino(e):
    perfil, alto = _std(e, e.abombado(4), nervios=0, bandas=(), borde=False)
    e.p_hexagonos(perfil, alto, filas=5, cols=40, aberturas=True)
    e.p_red(perfil, alto, n=20, color=e.S)


def duna_arena(e):
    perfil, alto = _std(e, e.abombado(5), nervios=0, bandas=(0.3, 0.55, 0.8), borde=False)
    e.c_ola(e.d_ext, alto, vuelo=14, amplitud=6, color=e.D)
    e.dunas(e.d_ext, lineas=6)


def petalo_ciclopeo(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.c_petalos(e.d_ext, alto, k=4, alto=50, ancho_t=0.7)


def membrana_tensada(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.c_membrana_mastiles(e.d_ext, alto, mastiles=10, alto_mastil=44, vuelo=24, color=e.D)


# ===================================================================== GRUPO 3: geométricos, futuristas y paramétricos
def diamante_facetado(e):
    perfil, alto = _std(e, nervios=0, bandas=(), borde=True)
    e.p_triangulos(perfil, alto, filas=4, cols=26)


def icosaedro(e):
    perfil, alto = _std(e, nervios=0, bandas=(0.5,))
    e.c_cupula(e.d_ext, alto, alto=88, meridianos=20, paralelos=5, triangulada=True)


def cubo_flotante(e):
    perfil = e.recto(4)
    alto = e.z_top + 10
    e.basico()
    e.fachada(perfil, alto, nervios=2, bandas=(0.25, 0.5, 0.75), borde=e.P)
    v = e.v
    ext = e.anillo(perfil(alto), alto)
    hueco = [v.p(*contorno("oval", e.a0 + 4 + 8 * math.sin(3 * DOS_PI * i / 64) ** 2, e.b0 + 4, DOS_PI * i / 64), alto) for i in range(64)]
    d = f'M{pts(ext)} Z M{pts(list(reversed(hueco)))} Z'
    e.add(f'<path d="{d}" fill="{RELLENO}" fill-rule="evenodd" stroke="{TRAZO}" stroke-width="1.4"/>'
          f'<polygon points="{pts(hueco)}" fill="none" stroke="{e.S}" stroke-width="1.8"/>', O_TECHO)


def hexagono_parametrico(e):
    perfil, alto = _std(e, nervios=0, bandas=(), borde=True)
    e.p_hexagonos(perfil, alto, filas=5, cols=34, aberturas=True)
    e.c_anillo(e.d_ext, alto, 16, opacidad=0.14)


def anillo_mobius(e):
    perfil, alto = _std(e, nervios=0, bandas=(), borde=False)
    e.p_vidrio(perfil, alto, cols=60, filas=4)
    e.c_mobius(e.d_ext, alto)


def origami(e):
    perfil, alto = _std(e, e.recto(2), nervios=0, bandas=(), borde=True)
    e.p_triangulos(perfil, alto, filas=2, cols=20)
    picos = []
    for i in range(21):
        t = DOS_PI * i / 20
        picos.append((t, alto + (8 if i % 2 else 0)))
    e.add(polilineas(e.curva(picos, perfil), e.P, 1.8), O_FACHADA + 0.6)


def vortex_espiral(e):
    perfil, alto = _std(e, e.concavo(4), nervios=0, bandas=(), borde=True)
    e.p_helice(perfil, alto, n=18, vueltas=0.45)
    e.c_anillo(perfil(alto), alto, 20, opacidad=0.14, z_interior=alto + 16)


def cupula_reticular(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.c_cupula(e.d_ext, alto, alto=60, meridianos=22, paralelos=5, triangulada=True, color=e.P, abierta=0.35)


def poliedro_irregular(e):
    perfil, alto = _std(e, e.recto(3), nervios=0, bandas=(), borde=True)
    e.p_triangulos(perfil, alto, filas=1, cols=12, sombreado=True)
    for k in range(3):
        e.p_led(perfil, math.radians(70 + k * 30), 0.12, alto * 0.25, alto * 0.7, color=e.S)


def lamas_ondulantes(e):
    perfil, alto = _std(e, e.recto(1), nervios=0, bandas=(), borde=True)
    e.p_lamas(perfil, alto, n=110, ondas=5, ancho_t=0.035)


# ===================================================================== GRUPO 4: culturales y simbólicos
def carpa_nomada(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.c_petalos(e.d_ext, alto, k=6, alto=24, color=e.D, ancho_t=0.5)
    e.c_membrana_mastiles(e.d_ext, alto, mastiles=6, alto_mastil=36, vuelo=10, color=e.D)
    e.dunas(e.d_ext, lineas=3)


def cuenco_prehispanico(e):
    perfil, alto = _std(e, e.tronco(10), nervios=0, bandas=(), borde=True)
    e.p_grecas(perfil, alto * 0.35, alto * 0.75, motivos=40)
    e.add(polilineas(e.curva([(DOS_PI * i / e.N, alto * 0.25) for i in range(e.N + 1)], perfil), e.S, 1.4), O_FACHADA + 0.5)


def coliseo_solar(e):
    perfil, alto = _std(e, nervios=0, bandas=(0.5,))
    e.p_lamas(perfil, alto, n=60, ondas=0, ancho_t=0.0)
    rayos = []
    n = 48
    for i in range(n):
        t = DOS_PI * i / n
        largo = 9 if i % 2 else 5
        rayos.append((e.punto(perfil(alto), alto, t), e.punto(perfil(alto) + largo, alto + 2, t)))
    e.add(segmentos(rayos, e.P, 1.6), O_TECHO)


def vela_barco(e):
    perfil, alto = _std(e, nervios=4, bandas=(0.5,))
    e.c_vela(e.d_ext, alto)


def cinturon_campeon(e):
    perfil, alto = _std(e, e.recto(1), nervios=4, bandas=())
    # correa ancha en la parte alta (la mitad superior de la fachada) con remaches y una gran hebilla al frente
    franja = []
    for i in range(0, 72, 1):
        t = DOS_PI * i / 72
        if e.frente(t, perfil(alto)):
            franja.append([e.S_(t, alto * 0.5, perfil), e.S_(t + DOS_PI / 72, alto * 0.5, perfil), e.S_(t + DOS_PI / 72, alto, perfil), e.S_(t, alto, perfil)])
    e.add("".join(f'<polygon points="{pts(c)}" fill="{e.P}" fill-opacity="0.55" stroke="none"/>' for c in franja), O_FACHADA + 0.6)
    for dz, color, ancho in ((0.5, e.D, 1.4), (1.0, e.D, 1.4)):
        e.add(polilineas(e.curva([(DOS_PI * i / e.N, alto * dz) for i in range(e.N + 1)], perfil), color, ancho), O_FACHADA + 0.7)
    remaches = [e.S_(DOS_PI * i / 48, alto * 0.75, perfil) for i in range(48) if e.frente(DOS_PI * i / 48, perfil(alto))]
    e.add("".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.3" fill="{e.D}"/>' for x, y in remaches), O_FACHADA + 0.8)
    e.p_led(perfil, math.radians(108), 0.42, alto * 0.25, alto * 1.15, color=e.S)


def corona_real(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.4,))
    picos = []
    n = 24
    for i in range(n * 2 + 1):
        t = DOS_PI * i / (n * 2)
        picos.append((t, alto + (14 if i % 2 else 0)))
    e.add(polilineas(e.curva(picos, perfil, solo_frente=False), e.P, 1.8), O_TECHO)
    puntas = [e.S_(DOS_PI * (2 * i + 1) / (n * 2), alto + 14, perfil) for i in range(n)]
    e.add("".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.8" fill="{e.D}"/>' for x, y in puntas), O_TECHO + 0.1)


def cesta_mimbre(e):
    perfil, alto = _std(e, e.abombado(4), nervios=0, bandas=(), borde=True)
    e.p_mimbre(perfil, alto, n=40)


def timon_nautico(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    ext, inte = e.c_anillo(e.d_ext, alto, 16, opacidad=0.16)
    rayos, perillas = [], []
    for k in range(8):
        t = DOS_PI * k / 8 + DOS_PI / 16
        a, b = e.punto(e.d_ext - 16, alto + 7, t), e.punto(e.d_ext + 12, alto + 7, t)
        rayos.append((a, b))
        perillas.append(b)
    e.add(segmentos(rayos, e.P, 2.6) + "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{RELLENO}" stroke="{e.D}" stroke-width="1.6"/>' for x, y in perillas), O_TECHO + 1)


def abanico(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.c_abanico(e.d_ext, alto, varillas=16, radio=48)


def arco_triunfo_moderno(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.c_anillo(e.d_ext, alto, 14, opacidad=0.12)
    e.arco_triunfo(e.d_ext, alto)


# ===================================================================== GRUPO 5: alta tecnología, sostenibles y urbanos
def anidado_rascacielos(e):
    e.skyline(alto_max=90)
    perfil, alto = _std(e, nervios=2, bandas=(0.33, 0.66))
    e.torres_oficinas(e.d_ext, alto, cantidad=3)
    e.c_anillo(e.d_ext, alto, 15, opacidad=0.16)


def solar_integrado(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.c_solar(e.d_ext - 10, alto, celdas=(16, 8))


def colgante(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.c_arco(e.d_ext, alto, alto=86, cruzado=True)
    e.c_anillo(e.d_ext, alto, 16, opacidad=0.12, columnas=False, cerchas=False)


def doble_anillo_desfasado(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.c_doble_desfasado(e.d_ext, alto)


def modular_desmontable(e):
    perfil, alto = _std(e, nervios=0, bandas=(0.5,), borde=True)
    e.p_columnas(perfil, alto, n=36, color=TRAZO, ancho=1.4)
    e.p_celosia(perfil, alto, n=36, curva=0.0, color=TRAZO_SUAVE, ancho=0.8)
    nudos = []
    for i in range(36):
        t = DOS_PI * i / 36
        for f in (0, 0.5, 1):
            if e.frente(t, perfil(alto * f)) and not e.en_hueco(t):
                nudos.append(e.S_(t, alto * f, perfil))
    e.add("".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.5" fill="{e.D}"/>' for x, y in nudos), O_FACHADA + 0.6)


def terraza_verde(e):
    e.basico()
    escalones = 4
    base = e.d_ext + 12
    alto = e.z_top
    for k in range(escalones):
        d = base - k * 4
        z = alto * (k + 1) / escalones
        perfil = (lambda dd: (lambda h: dd))(d)
        e.silueta(perfil, z)
        borde = e.curva([(DOS_PI * i / e.N, z) for i in range(e.N + 1)], perfil)
        e.add(polilineas(borde, VERDE, 1.4, 'opacity="0.85"'), O_FACHADA + 0.5 + k * 0.01)
        e.add(polilineas(e.curva([(DOS_PI * i / e.N, z - 1.2) for i in range(e.N + 1)], perfil), e.P, 0.7, 'opacity="0.6"'), O_FACHADA + 0.4)
    e.tapa(base - (escalones - 1) * 4, alto, e.P)
    e.arboles(e.d_ext + 6, cantidad=28, r=(3.5, 5.0))


def cuatro_mastiles(e):
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.cuatro_mastiles(e.d_ext, alto, alto=60)


def vidrio_laminado(e):
    e.basico()
    perfil, alto = e.recto(1), e.z_top
    e.p_vidrio(perfil, alto, cols=84, filas=7)
    e.borde_inferior(perfil)
    e.tapa(perfil(alto), alto, e.P)
    e.c_anillo(e.d_ext + 1, alto, 12, opacidad=0.1, cerchas=False)


def compacto_urbano(e):
    e.skyline(alto_max=70)
    perfil, alto = _std(e, nervios=2, bandas=(0.25, 0.5, 0.75))
    e.c_anillo(e.d_ext, alto, 14, opacidad=0.18, alza=5)


def anular_abierto(e):
    e.skyline(alto_max=110)
    perfil, alto = _std(e, nervios=3, bandas=(0.5,))
    e.c_anillo(e.d_ext, alto, 18, opacidad=0.18, t0=e.hueco[1], t1=e.hueco[0] + DOS_PI)


# ===================================================================== CATÁLOGO
def _c(codigo, nombre, grupo, fn, forma="oval", anillos=2, regiones=None, costero=False, hueco=None, cy_extra=0.0):
    return {"codigo": codigo, "nombre": nombre, "grupo": grupo, "dibujar": fn, "forma": forma, "anillos": anillos,
            "regiones": regiones or [], "costero": costero, "hueco": hueco, "cy_extra": cy_extra}


CONCEPTOS = [
    _c("metropolitano", "Estadio Metropolitano Clásico", 1, metropolitano_clasico, "oval", 2),
    _c("coliseo_acero", "Coliseo de Acero", 1, coliseo_acero, "circulo", 2),
    _c("anillo_concavo", "Anillo Cóncavo", 1, anillo_concavo, "circulo", 2),
    _c("cilindro_columnado", "El Cilindro Columnado", 1, cilindro_columnado, "circulo", 2),
    _c("rotonda_monumental", "Rotonda Monumental", 1, rotonda_monumental, "circulo", 2),
    _c("gigante_concreto", "El Gigante de Concreto", 1, gigante_concreto, "oval", 3),
    _c("anfiteatro_modular", "Anfiteatro Modular", 1, anfiteatro_modular, "poligono:8", 2),
    _c("ovalo_pilares", "El Óvalo de Pilares", 1, ovalo_pilares, "oval", 2),
    _c("rotonda_doble", "Rotonda de Doble Columna", 1, rotonda_doble_columna, "circulo", 2),
    _c("anillo_tradicional", "El Anillo Tradicional", 1, anillo_tradicional, "oval", 2),
    _c("nido", "Estadio Nido de Pájaro", 2, nido_pajaro, "oval", 2),
    _c("loto", "El Capullo de Loto", 2, capullo_loto, "circulo", 2, regiones=["asia_sur", "asia_sudeste"]),
    _c("ola_marina", "La Ola Marina", 2, ola_marina, "oval", 2, costero=True),
    _c("piel_serpiente", "El Piel de Serpiente", 2, piel_serpiente, "oval", 2),
    _c("tortuga", "El Caparazón de Tortuga", 2, caparazon_tortuga, "oval", 1),
    _c("hoja_tropical", "La Hoja Tropical", 2, hoja_tropical, "rect", 2, regiones=["caribe", "caribe_hispano", "africa_subsahariana", "asia_sudeste", "pacifico"]),
    _c("coral", "El Coral Marino", 2, coral_marino, "oval", 2, costero=True),
    _c("duna", "La Duna de Arena", 2, duna_arena, "oval", 1, regiones=["africa_norte_medio_oriente", "asia_central"]),
    _c("petalo_ciclopeo", "El Pétalo Ciclópeo", 2, petalo_ciclopeo, "oval", 2),
    _c("membrana_tensada", "Estructura de Membrana Tensada", 2, membrana_tensada, "oval", 2),
    _c("diamante", "El Diamante Multifacetado", 3, diamante_facetado, "poligono:10", 2),
    _c("icosaedro", "Icosaedro Esférico", 3, icosaedro, "circulo", 2),
    _c("cubo_flotante", "El Cubo Flotante", 3, cubo_flotante, "caja", 2),
    _c("hexagono", "El Hexágono Paramétrico", 3, hexagono_parametrico, "oval", 2),
    _c("mobius", "El Anillo de Möbius", 3, anillo_mobius, "oval", 2),
    _c("origami", "El Estadio Origami", 3, origami, "poligono:10", 2, regiones=["asia_este"]),
    _c("vortex", "El Vórtex Espiral", 3, vortex_espiral, "circulo", 2),
    _c("cupula_reticular", "La Cúpula Reticular Triangular", 3, cupula_reticular, "oval", 2),
    _c("poliedro", "El Poliedro Irregular", 3, poliedro_irregular, "poligono:12", 2),
    _c("lamas", "Fachada Paramétrica Ondulante", 3, lamas_ondulantes, "oval", 2),
    _c("carpa_nomada", "La Carpa Nómada", 4, carpa_nomada, "oval", 2, regiones=["africa_norte_medio_oriente", "asia_central"]),
    _c("cuenco_prehispanico", "El Cuenco de Cerámica Prehispánica", 4, cuenco_prehispanico, "circulo", 2, regiones=["mesoamerica", "sudamerica", "caribe_hispano"]),
    _c("coliseo_solar", "El Coliseo Solar", 4, coliseo_solar, "circulo", 2, regiones=["mesoamerica", "sudamerica", "africa_norte_medio_oriente"]),
    _c("vela_barco", "El Estadio Vela de Barco", 4, vela_barco, "rect", 2, costero=True),
    _c("cinturon", "El Cinturón de Campeón", 4, cinturon_campeon, "circulo", 2),
    _c("corona", "La Corona Real", 4, corona_real, "circulo", 2, regiones=["europa_norte", "europa_sur"]),
    _c("cesta_mimbre", "El Estadio Cesta de Mimbre", 4, cesta_mimbre, "oval", 2, regiones=["africa_subsahariana", "asia_sudeste", "pacifico"]),
    _c("timon", "El Timón Náutico", 4, timon_nautico, "circulo", 2, costero=True),
    _c("abanico", "El Abanico Desplegable", 4, abanico, "rect", 2, regiones=["asia_este"]),
    _c("arco_triunfo", "El Arco del Triunfo Moderno", 4, arco_triunfo_moderno, "rect", 1, regiones=["europa_sur", "europa_norte", "europa_este"]),
    _c("rascacielos", "Estadio Anidado en Rascacielos", 5, anidado_rascacielos, "rect", 2),
    _c("solar", "El Estadio Solar Integrado", 5, solar_integrado, "rect", 2),
    _c("colgante", "El Estadio Colgante", 5, colgante, "oval", 2, cy_extra=40),
    _c("doble_anillo", "Doble Anillo Desfasado", 5, doble_anillo_desfasado, "circulo", 2),
    _c("modular", "El Estadio Modular Desmontable", 5, modular_desmontable, "rect", 2),
    _c("terraza_verde", "El Estadio Terraza Verde", 5, terraza_verde, "oval", 2),
    _c("cuatro_mastiles", "Cuatro Mástiles Esquineros", 5, cuatro_mastiles, "rect", 2),
    _c("vidrio_laminado", "Fachada de Vidrio Laminado", 5, vidrio_laminado, "rect", 2),
    _c("compacto_urbano", "El Estadio Compacto Urbano", 5, compacto_urbano, "rect", 2),
    _c("anular_abierto", "El Estadio Anular Abierto", 5, anular_abierto, "oval", 2, hueco=(2.75, 3.55)),
]
POR_CODIGO = {c["codigo"]: c for c in CONCEPTOS}


def dibujar(concepto: dict, paleta: dict, semilla: int = 0, espejo: bool = False) -> str:
    e = Estadio(paleta, forma=concepto["forma"], anillos=concepto["anillos"], semilla=semilla, espejo=espejo,
                hueco=concepto["hueco"], cy_extra=concepto["cy_extra"])
    concepto["dibujar"](e)
    return e.svg(concepto["nombre"])
