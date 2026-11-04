"""
Catálogo ampliado: los 50 conceptos de catalogo.py + ~95 RECETAS nuevas (plantillas 2 y 3 del usuario). Una receta es un
diccionario declarativo —planta, perfil, fachada(s), cubierta, extras— que `_receta` dibuja con las piezas de
estadios/piezas.py y piezas_v3.py. Cada concepto lleva una `familia` (lo que lo hace parecido a otros): la asignación evita
repetir familia dentro de un país. Mismas llaves que catalogo.CONCEPTOS, así generar_estadios.py los trata igual.
"""
from estadios import catalogo as C0
from estadios.catalogo import GRUPOS as GRUPOS0, _std
from estadios.piezas_v3 import EstadioV3

GRUPOS = {**GRUPOS0, 6: "Variantes de plantilla (fachadas y cubiertas)", 7: "Sobre el agua y verdes", 8: "Torres, viseras y cables"}

# Familia de los 50 originales (los que no figuran son únicos)
FAMILIA_ORIGINAL = {
    "metropolitano": "columnas", "cilindro_columnado": "columnas", "rotonda_monumental": "columnas", "rotonda_doble": "columnas",
    "ovalo_pilares": "columnas", "anfiteatro_modular": "columnas", "coliseo_acero": "celosia", "modular": "celosia",
    "anillo_concavo": "anillo", "anillo_tradicional": "anillo", "doble_anillo": "anillo", "colgante": "anillo",
    "compacto_urbano": "urbano", "rascacielos": "urbano", "anular_abierto": "urbano",
    "ola_marina": "ola", "duna": "ola", "tortuga": "cupula", "icosaedro": "cupula", "cupula_reticular": "cupula",
    "mobius": "vidrio", "vidrio_laminado": "vidrio", "coral": "hexagonos", "hexagono": "hexagonos", "diamante": "triangulos",
    "poliedro": "triangulos", "origami": "triangulos", "loto": "petalos", "petalo_ciclopeo": "petalos",
    "membrana_tensada": "mastiles", "cuatro_mastiles": "mastiles", "carpa_nomada": "picos", "nido": "red",
}

PERFILES = {"recto": lambda e, a=0.0: e.recto(a), "concavo": lambda e, a=6.0: e.concavo(a), "tronco": lambda e, a=9.0: e.tronco(a),
            "abombado": lambda e, a=5.0: e.abombado(a)}
# cómo se llama cada extra: "dz" = (desp, z, **kw), "d" = (desp, **kw), "0" = (**kw)
FIRMA_EXTRA = {"focos": "dz", "torres_esquina": "dz", "cuatro_mastiles": "dz", "torres_oficinas": "dz", "banderines": "dz",
               "arboles": "d", "dunas": "d", "escalinata": "d", "agua": "d", "skyline": "0"}


def _receta(r, e):
    antes = [x for x in r["extras"] if x[0] in ("skyline", "agua")]
    despues = [x for x in r["extras"] if x[0] not in ("skyline", "agua")]
    for nombre, kw in antes:
        getattr(e, nombre)(**kw) if FIRMA_EXTRA[nombre] == "0" else getattr(e, nombre)(e.d_ext, **kw)
    pn, pa = r["perfil"]
    perfil, alto = _std(e, PERFILES[pn](e, pa), nervios=r["nervios"], bandas=r["bandas"], borde=r["borde"])
    for nombre, kw in r["fachada"]:
        getattr(e, nombre)(perfil, alto, **kw)
    for nombre, kw in r["cubierta"]:
        getattr(e, nombre)(e.d_ext, alto, **kw)
    for nombre, kw in despues:
        getattr(e, nombre)(e.d_ext, alto, **kw) if FIRMA_EXTRA[nombre] == "dz" else getattr(e, nombre)(e.d_ext, **kw)


def R(codigo, nombre, grupo, forma, familia, fachada=(), cubierta=(), extras=(), anillos=2, perfil=("recto", 0.0), nervios=0,
      bandas=(), borde=True, regiones=None, costero=False, hueco=None, cy_extra=0.0):
    r = {"fachada": list(fachada), "cubierta": list(cubierta), "extras": list(extras), "perfil": perfil, "nervios": nervios,
         "bandas": bandas, "borde": borde}
    return {"codigo": codigo, "nombre": nombre, "grupo": grupo, "dibujar": lambda e, r=r: _receta(r, e), "forma": forma,
            "anillos": anillos, "regiones": regiones or [], "costero": costero, "hueco": hueco, "cy_extra": cy_extra, "familia": familia}


def F(nombre, **kw):
    return (nombre, kw)


# partes reutilizadas
AN = lambda **kw: F("c_anillo", **{"vuelo": 18, **kw})
VISERA = lambda **kw: F("c_visera", **kw)
EUR = ["europa_sur", "europa_norte", "europa_este"]
NUEVOS = [
    # ------------------------------------------------------------------ 7: sobre el agua
    R("flotante_anillo", "Estadio Flotante de Anillo", 7, "oval", "agua", [F("p_columnas", n=56, ancho=1.4)], [AN(vuelo=20)], [F("agua")], costero=True, bandas=(0.5,)),
    R("flotante_vela", "Estadio Flotante de Vela", 7, "rect", "agua", [], [F("c_vela")], [F("agua", ancho=30)], costero=True, nervios=4, bandas=(0.5,)),
    R("flotante_domo", "Domo sobre el Lago", 7, "circulo", "agua", [F("p_hexagonos", filas=3, cols=30, aberturas=False)],
      [F("c_cupula", alto=36, meridianos=20, paralelos=4, triangulada=True)], [F("agua")], costero=True),
    R("flotante_ondas", "Estadio Flotante de Ondas", 7, "ovalo_largo", "agua", [F("p_horizontales", n=10)], [F("c_ola", vuelo=24, amplitud=14)], [F("agua", ancho=28)], costero=True),
    R("laguna_membrana", "Estadio de la Laguna", 7, "oval", "agua", [], [F("c_membrana_mastiles", mastiles=8, alto_mastil=40, vuelo=22)], [F("agua", ancho=38)], costero=True, nervios=3),
    R("foso_rombos", "Estadio con Foso de Rombos", 7, "oval", "agua", [F("p_rombos", filas=3, cols=30)], [AN(vuelo=14)], [F("agua", ancho=24)]),
    # ------------------------------------------------------------------ 7: cubiertas verdes
    R("techo_verde_plano", "Estadio de Techo Verde Plano", 7, "rect_largo", "verde", [F("p_horizontales", n=8)], [F("c_verde", vuelo=34)], [], nervios=0),
    R("colina_verde", "La Colina Verde", 7, "oval", "verde", [F("p_paneles", filas=2, cols=24, colores=["#4ade80", "#22c55e"])], [F("c_verde", vuelo=36)], [], perfil=("abombado", 5.0)),
    R("jardin_colgante", "El Jardín Colgante", 7, "circulo", "verde", [F("p_columnas", n=36, ancho=1.2)], [F("c_verde", vuelo=26, alza=9)], [F("arboles", cantidad=26, r=(3.5, 5.0))]),
    R("prado_urbano", "El Prado Urbano", 7, "rect", "verde", [F("p_cuadros", filas=4, cols=32)], [F("c_verde", vuelo=24)], [F("skyline", alto_max=60)]),
    R("verde_celosia", "Verde y Celosía", 7, "oval", "verde", [F("p_celosia", n=40, curva=0.5)], [F("c_verde", vuelo=30)], [], perfil=("abombado", 6.0)),
    # ------------------------------------------------------------------ 6: arcadas y piedra
    R("coliseo_piedra", "El Coliseo de Piedra", 6, "circulo", "arcos", [F("p_arcos", filas=3, cols=44)], [], [], anillos=3, regiones=EUR + ["africa_norte_medio_oriente"]),
    R("anfiteatro_arcos", "Anfiteatro de Arcos", 6, "oval", "arcos", [F("p_arcos", filas=2, cols=40)], [], [], anillos=3, regiones=EUR),
    R("arena_arcada", "La Arena de la Arcada", 6, "rect_suave", "arcos", [F("p_arcos", filas=1, cols=36), F("p_columnas", n=36, ancho=1.0)], [AN(vuelo=12)], [], regiones=EUR),
    R("coliseo_ruinas", "El Coliseo en Ruinas", 6, "oval", "arcos", [F("p_arcos", filas=3, cols=48)], [], [], anillos=3, hueco=(2.2, 3.1)),
    R("plaza_arcos", "La Plaza de Arcos", 6, "circulo", "arcos", [F("p_arcos", filas=2, cols=32)], [], [F("banderines", cantidad=24)], regiones=["europa_sur", "mesoamerica", "sudamerica"]),
    # ------------------------------------------------------------------ 8: carpas y picos
    R("arana_hexagonal", "La Araña Hexagonal", 8, "oval", "picos", [F("p_hexagonos", filas=3, cols=30, aberturas=True)], [F("c_picos", k=10, alto=36)], []),
    R("carpa_picos", "La Carpa de Picos", 8, "oval", "picos", [], [F("c_picos", k=6, alto=54)], [], nervios=3, bandas=(0.5,), regiones=["africa_norte_medio_oriente", "asia_central"]),
    R("estrella_picos", "La Estrella de Picos", 8, "circulo", "picos", [F("p_triangulos", filas=2, cols=24)], [F("c_picos", k=12, alto=38)], []),
    R("pagoda_picos", "La Pagoda de Picos", 8, "rect", "picos", [F("p_columnas", n=24, ancho=1.8)], [F("c_picos", k=8, alto=44, vuelo=12)], [], regiones=["asia_este", "asia_sudeste"]),
    R("cumbres", "Las Cumbres", 8, "ovalo_largo", "picos", [F("p_lamas", n=90, ondas=3)], [F("c_picos", k=16, alto=28)], []),
    # ------------------------------------------------------------------ 6: cúpulas de cristal
    R("domo_cristal", "El Domo de Cristal", 6, "circulo", "domo", [F("p_vidrio", cols=64, filas=4)], [F("c_cupula", alto=48, meridianos=24, paralelos=5, triangulada=True)], []),
    R("domo_geodesico", "El Domo Geodésico", 6, "oval", "domo", [F("p_triangulos", filas=2, cols=28)], [F("c_cupula", alto=40, meridianos=28, paralelos=6, triangulada=True)], []),
    R("domo_aplanado", "El Domo Aplanado", 6, "ovalo_largo", "domo", [F("p_horizontales", n=6)], [F("c_cupula", alto=26, meridianos=22, paralelos=4, triangulada=False)], []),
    R("burbuja", "La Burbuja", 6, "circulo", "domo", [], [F("c_cupula", alto=70, meridianos=18, paralelos=4, triangulada=False)], [], perfil=("abombado", 7.0)),
    R("invernadero", "El Invernadero", 6, "rect", "domo", [F("p_cuadros", filas=3, cols=36)], [F("c_cupula", alto=34, meridianos=20, paralelos=4, triangulada=False)], []),
    # ------------------------------------------------------------------ 6: ladrillo
    R("ladrillo_clasico", "El Ladrillo Clásico", 6, "rect_suave", "ladrillo", [F("p_ladrillo", filas=12, cols=40)], [], [F("focos", alto=40)], regiones=EUR),
    R("fabrica_roja", "La Fábrica Roja", 6, "rect", "ladrillo", [F("p_ladrillo", filas=10, cols=34)], [], [F("torres_esquina", r=7, helice=False)], regiones=EUR),
    R("ladrillo_arcos", "Ladrillo y Arcos", 6, "oval", "ladrillo", [F("p_ladrillo", filas=10, cols=36), F("p_arcos", filas=1, cols=36, color="#e2e8f0")], [], []),
    R("ladrillo_cubierta", "Ladrillo con Cubierta", 6, "oval", "ladrillo", [F("p_ladrillo", filas=11, cols=40)], [AN(vuelo=16)], [F("focos", alto=34)]),
    R("ladrillo_columnas", "Ladrillo y Columnas", 6, "cuadrado", "ladrillo", [F("p_ladrillo", filas=10, cols=32), F("p_columnas", n=16, ancho=2.4)], [], []),
    # ------------------------------------------------------------------ 6: pórticos y rectangulares
    R("portico_columnas", "El Pórtico de Columnas", 6, "rect", "portico", [F("p_columnas", n=24, ancho=2.6, color="#e2e8f0")], [AN(vuelo=14)], [F("escalinata", ancho=44, escalones=8)], regiones=EUR + ["mesoamerica"]),
    R("acropolis", "La Acrópolis", 6, "caja", "portico", [F("p_columnas", n=20, ancho=2.4)], [], [F("escalinata", ancho=50, escalones=10)], regiones=EUR),
    R("templo_moderno", "El Templo Moderno", 6, "rect_largo", "portico", [F("p_columnas", n=20, ancho=2.8)], [AN(vuelo=10, alza=10)], [], bandas=(0.5,)),
    R("galeria_vidrio", "La Galería de Vidrio", 6, "rect", "portico", [F("p_vidrio", cols=48, filas=5)], [AN(vuelo=12)], []),
    R("cubo_portico", "El Cubo con Pórtico", 6, "cuadrado_caja", "portico", [F("p_columnas", n=18, ancho=2.2)], [AN(vuelo=10)], []),
    # ------------------------------------------------------------------ 8: cables y rueda
    R("rueda_cables", "La Rueda de Cables", 8, "oval", "cable", [F("p_columnas", n=36, ancho=1.2)], [F("c_rueda")], [], bandas=(0.5,)),
    R("rueda_doble", "La Rueda Densa", 8, "circulo", "cable", [], [F("c_rueda", vuelo=32, radios=56)], [], nervios=3, bandas=(0.5,)),
    R("cables_pilonos", "Cuatro Pilonos y Cables", 8, "rect", "cable", [], [F("c_membrana_mastiles", mastiles=4, alto_mastil=72, vuelo=20)], [], nervios=3, bandas=(0.5,)),
    R("tensegridad", "La Tensegridad", 8, "oval", "cable", [F("p_columnas", n=18, ancho=1.2)], [F("c_arco", alto=76, cruzado=True), F("c_rueda", vuelo=14)], []),
    R("pilonos_esquina", "Pilonos de Esquina", 8, "rect_suave", "cable", [F("p_perforada", filas=4, cols=44)], [F("c_rueda", vuelo=18)], [F("cuatro_mastiles", alto=72)]),
    R("rueda_alta", "La Rueda Alta", 8, "circulo", "cable", [F("p_helice", n=16, vueltas=0.3)], [F("c_rueda", vuelo=28, alza=16)], []),
    # ------------------------------------------------------------------ 6: ondas y cintas
    R("cinta_ondulante", "La Cinta Ondulante", 6, "oval", "ola", [F("p_lamas", n=80, ondas=4)], [F("c_ola", vuelo=30, amplitud=20)], []),
    R("ola_doble", "La Ola Doble", 6, "ovalo_largo", "ola", [F("p_horizontales", n=8)], [F("c_ola", vuelo=24, amplitud=24)], []),
    R("marea_alta", "La Marea Alta", 6, "oval", "ola", [F("p_zigzag", filas=3)], [F("c_ola", vuelo=18, amplitud=22)], [F("dunas", lineas=4)], costero=True),
    R("cinta_blanca", "La Cinta Blanca", 6, "lenteja", "ola", [F("p_horizontales", n=12)], [F("c_ola", vuelo=26, amplitud=18)], []),
    R("espuma", "La Espuma", 6, "circulo", "ola", [F("p_escamas", filas=5, cols=40)], [F("c_ola", vuelo=34, amplitud=10)], [], costero=True),
    R("ola_cristal", "La Ola de Cristal", 6, "ovalo_largo", "ola", [F("p_vidrio", cols=64, filas=5)], [F("c_ola", vuelo=22, amplitud=16)], []),
    # ------------------------------------------------------------------ 6: vidrio largo
    R("lente_cristal", "La Lente de Cristal", 6, "lenteja", "vidrio", [F("p_vidrio", cols=72, filas=5)], [], [], bandas=(0.5,)),
    R("cristal_curvo", "El Cristal Curvo", 6, "ovalo_largo", "vidrio", [F("p_vidrio", cols=72, filas=8)], [AN(vuelo=14)], [], perfil=("concavo", 7.0)),
    R("prisma_largo", "El Prisma Largo", 6, "rect_largo", "vidrio", [F("p_vidrio", cols=60, filas=6)], [AN(vuelo=10)], []),
    R("bruma_azul", "La Bruma Azul", 6, "oval", "vidrio", [F("p_vidrio", cols=72, filas=7)], [], [], perfil=("tronco", 10.0)),
    # ------------------------------------------------------------------ 6: rombos
    R("rombos_rojos", "Los Rombos Rojos", 6, "oval", "rombos", [F("p_rombos", filas=4, cols=28)], [AN(vuelo=14)], []),
    R("diamante_tejido", "El Diamante Tejido", 6, "circulo", "rombos", [F("p_rombos", filas=5, cols=36)], [], []),
    R("rombos_cuenco", "El Cuenco de Rombos", 6, "oval", "rombos", [F("p_rombos", filas=4, cols=30)], [AN(vuelo=12)], [], perfil=("tronco", 12.0)),
    R("rombos_dobles", "Rombos y Columnas", 6, "rect_suave", "rombos", [F("p_rombos", filas=3, cols=24), F("p_columnas", n=24, ancho=1.2)], [], []),
    R("rombos_visera", "Rombos con Visera", 8, "oval", "rombos", [F("p_rombos", filas=4, cols=26)], [VISERA(t0=0.15, t1=3.0)], []),
    # ------------------------------------------------------------------ 8: viseras
    R("ala_principal", "El Ala Principal", 8, "oval", "visera", [], [VISERA(t0=0.1, t1=3.05, vuelo=40)], [], nervios=3, bandas=(0.5,)),
    R("visera_vela", "La Visera de Vela", 8, "rect", "visera", [F("p_columnas", n=30, ancho=1.2)], [VISERA(t0=0.2, t1=2.95, vuelo=36, alza=34)], [F("cuatro_mastiles", alto=50)]),
    R("pico_aguila", "El Pico de Águila", 8, "rect_suave", "visera", [], [VISERA(t0=0.35, t1=2.8, vuelo=46, alza=42)], [], nervios=2, bandas=(0.5,)),
    R("ala_doble", "El Ala Doble", 8, "ovalo_largo", "visera", [F("p_horizontales", n=6)], [VISERA(t0=0.1, t1=1.55, vuelo=30), VISERA(t0=1.65, t1=3.05, vuelo=30)], []),
    R("tribuna_voladiza", "La Tribuna Voladiza", 8, "rect", "visera", [F("p_celosia", n=36, curva=0.0)], [VISERA(t0=0.1, t1=3.05, vuelo=34, alza=22)], []),
    # ------------------------------------------------------------------ 8: torres y esquinas
    R("esquinas_cortadas", "Las Esquinas Cortadas", 8, "cuadrado", "torres", [F("p_columnas", n=24, ancho=1.4)], [AN(vuelo=14)], [F("torres_esquina", r=7, helice=False)]),
    R("fortaleza", "La Fortaleza", 8, "cuadrado_caja", "torres", [F("p_ladrillo", filas=8, cols=28)], [], [F("torres_esquina", r=9, helice=False)]),
    R("torres_luz", "Las Torres de Luz", 8, "rect", "torres", [F("p_cuadros", filas=3, cols=36)], [], [F("focos", alto=52)]),
    R("bastion", "El Bastión", 8, "rect_suave", "torres", [F("p_paneles", filas=2, cols=28)], [], [F("torres_esquina", r=8, helice=True)]),
    R("faros", "Los Faros", 8, "oval", "torres", [F("p_lamas", n=70, ondas=0)], [AN(vuelo=14)], [F("focos", alto=58)]),
    R("octogono_torres", "El Octógono de Torres", 8, "octogono", "torres", [F("p_celosia", n=32, curva=0.4)], [AN(vuelo=12)], [F("torres_esquina", r=6, helice=True, angulos=(0, 45, 90, 135, 180, 225, 270, 315))]),
    # ------------------------------------------------------------------ 6: cuadros, listones, paneles
    R("reticula", "La Retícula", 6, "rect", "cuadros", [F("p_cuadros", filas=4, cols=36)], [], []),
    R("tablero", "El Tablero", 6, "cuadrado", "cuadros", [F("p_cuadros", filas=6, cols=32)], [AN(vuelo=12)], []),
    R("mosaico_cuadros", "El Mosaico de Cuadros", 6, "oval", "cuadros", [F("p_cuadros", filas=5, cols=44)], [AN(vuelo=16)], []),
    R("pixel", "El Estadio Píxel", 6, "ovalo_largo", "cuadros", [F("p_cuadros", filas=8, cols=60)], [], []),
    R("listones_horizontales", "Listones Horizontales", 6, "oval", "listones", [F("p_horizontales", n=14)], [AN(vuelo=16)], []),
    R("persiana", "La Persiana", 6, "rect", "listones", [F("p_horizontales", n=20)], [], []),
    R("listones_verticales", "Listones Verticales", 6, "circulo", "listones", [F("p_lamas", n=140, ondas=0, ancho_t=0.02)], [AN(vuelo=14)], []),
    R("barras", "Las Barras", 6, "rect_largo", "listones", [F("p_columnas", n=96, ancho=0.9)], [AN(vuelo=12)], []),
    R("paneles_color", "Paneles de Color", 6, "oval", "paneles", [F("p_paneles", filas=3, cols=28)], [], []),
    R("vitral", "El Vitral", 6, "circulo", "paneles", [F("p_paneles", filas=4, cols=32)], [AN(vuelo=14)], []),
    R("mosaico_bicolor", "El Mosaico Bicolor", 6, "rect_suave", "paneles", [F("p_paneles", filas=2, cols=22)], [AN(vuelo=12)], []),
    R("teselas", "Las Teselas", 6, "oval", "paneles", [F("p_paneles", filas=4, cols=36)], [], [], perfil=("tronco", 8.0)),
    # ------------------------------------------------------------------ 6: mezclas
    R("zigzag", "El Zigzag", 6, "oval", "zigzag", [F("p_zigzag", filas=3, picos=34)], [F("c_dientes")], []),
    R("sierra", "La Sierra", 6, "rect_suave", "zigzag", [F("p_columnas", n=30, ancho=1.2)], [F("c_dientes", k=20, vuelo=26)], []),
    R("perforado", "El Perforado", 6, "oval", "perforada", [F("p_perforada", filas=6, cols=60)], [AN(vuelo=16)], []),
    R("punteado", "El Punteado", 6, "circulo", "perforada", [F("p_perforada", filas=9, cols=64)], [], []),
    R("pliegues", "Los Pliegues", 6, "ovalo_largo", "zigzag", [F("p_triangulos", filas=2, cols=30)], [F("c_dientes", k=28, vuelo=20)], []),
    R("helice_rampas", "La Hélice de Rampas", 6, "circulo", "helice", [F("p_helice", n=24, vueltas=0.8)], [AN(vuelo=14)], []),
    R("rampas_espiral", "Las Rampas en Espiral", 6, "oval", "helice", [F("p_helice", n=12, vueltas=0.6)], [], [F("torres_esquina", r=6, helice=True)]),
    R("cinturon_escamas", "El Cinturón de Escamas", 8, "oval", "escamas", [F("p_escamas", filas=5, cols=40)], [VISERA(t0=0.1, t1=3.0, vuelo=28)], []),
    R("reja_urbana", "La Reja Urbana", 6, "rect_suave", "celosia", [F("p_celosia", n=36, curva=0.0)], [AN(vuelo=14)], [F("skyline", alto_max=70)]),
    R("nido_doble", "El Nido Alargado", 6, "lenteja", "red", [F("p_red", n=60)], [AN(vuelo=16)], [], perfil=("abombado", 5.0)),
    R("coral_cuadrado", "El Coral Cuadrado", 6, "cuadrado", "hexagonos", [F("p_hexagonos", filas=4, cols=30, aberturas=True)], [], []),
    R("hexa_visera", "Hexágonos con Visera", 8, "rect", "hexagonos", [F("p_hexagonos", filas=4, cols=30, aberturas=False)], [VISERA(t0=0.15, t1=3.0, vuelo=34)], []),
    R("cesta_cuadrada", "La Cesta Cuadrada", 6, "rect_suave", "mimbre", [F("p_mimbre", n=36)], [], [], perfil=("abombado", 4.0), regiones=["africa_subsahariana", "asia_sudeste", "pacifico"]),
    R("tronco_celosia", "El Tronco de Celosía", 6, "circulo", "celosia", [F("p_celosia", n=40, curva=0.6)], [AN(vuelo=14)], [], perfil=("tronco", 14.0)),
    R("concavo_columnas", "El Cóncavo de Columnas", 6, "ovalo_largo", "columnas", [F("p_columnas", n=56, ancho=1.4)], [AN(vuelo=16)], [], perfil=("concavo", 9.0)),
    R("abombado_red", "El Abombado de Red", 6, "circulo", "red", [F("p_red", n=52)], [AN(vuelo=14)], [], perfil=("abombado", 8.0)),
]

# ----------------------------------------------------------------------------------------------- catálogo completo
CONCEPTOS = []
for c in C0.CONCEPTOS:
    CONCEPTOS.append({**c, "familia": FAMILIA_ORIGINAL.get(c["codigo"], c["codigo"])})
CONCEPTOS += NUEVOS
POR_CODIGO = {c["codigo"]: c for c in CONCEPTOS}
assert len(POR_CODIGO) == len(CONCEPTOS), "códigos repetidos"


def dibujar(concepto: dict, paleta: dict, semilla: int = 0, espejo: bool = False) -> str:
    e = EstadioV3(paleta, forma=concepto["forma"], anillos=concepto["anillos"], semilla=semilla, espejo=espejo,
                  hueco=concepto["hueco"], cy_extra=concepto["cy_extra"])
    concepto["dibujar"](e)
    return e.svg(concepto["nombre"])
