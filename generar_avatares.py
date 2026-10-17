"""
Generador de avatares ilustrados (SVG plano, busto caricaturesco) para los jugadores.

Cada jugador tiene su propio avatar, armado con piezas paramétricas (forma de cara, peinado, cejas,
nariz, boca, barba, camiseta) y una semilla = su id, así que siempre sale el mismo. La camiseta usa
los colores del jersey de su selección (bucket jersey/<pais>.png). El fondo es TRANSPARENTE: la
marca de agua de la bandera la pone el CSS de la app, así la imagen pesa poco (~6-10 KB).

Rasgos: el tono de piel, el color y el tipo de pelo y el color de ojos se eligen con probabilidades
según la REGIÓN del país, pero toda región incluye todos los tonos (los planteles reales son
diversos) y en los países con planteles históricamente muy diversos las probabilidades son parejas.
Todos los avatares usan el mismo trazo: no hay rasgos exagerados según el origen.

Uso (en este orden; cada paso es idempotente):
    python generar_avatares.py --muestra [carpeta]   # avatares de jugadores de varias regiones, para revisar
    python generar_avatares.py --generar [carpeta]   # los 4.642 SVG en <carpeta>/jugadores/
    python generar_avatares.py --subir [carpeta]     # sube a gs://com-icg-mundial/jugadores/
    python generar_avatares.py --asignar             # escribe jugadores.avatar_imagen en Mongo

--muestra/--generar leen de Mongo (jugadores, paises) y del bucket (colores del jersey) con Pillow
(pip install pillow; solo para este script, la app no lo usa).
"""
import math
import os
import random
import sys

CX = 256
CONTORNO = "#1f1a17"
ANCHO_TRAZO = 5

# --- Paletas ----------------------------------------------------------------------------------------
PIELES = ["#f6d7c3", "#efc4a4", "#e3ac86", "#d4996f", "#c68458",
          "#b0703f", "#93572e", "#7a4524", "#5e331a", "#452313"]
PELOS = {
    "negro": "#1c1714", "castano_oscuro": "#3b2416", "castano": "#5e3a22", "castano_claro": "#8a5a33",
    "rubio_oscuro": "#b08445", "rubio": "#d9b56c", "pelirrojo": "#a2502b",
}
CANAS = ["#8c8c8c", "#b5b5b5"]
OJOS = {"marron": "#4a2c17", "avellana": "#7a5a2a", "verde": "#4f7a4a", "azul": "#3f6f9a"}

# --- Regiones: pesos de tono de piel (10, de claro a oscuro), color de pelo, textura y ojos -------------
# Toda región tiene peso > 0 en todos los tonos: dentro de cada plantel siempre hay variedad.
REGIONES = {
    "europa_norte": {"piel": [24, 26, 16, 8, 5, 4, 4, 4, 4, 3], "pelo": {"rubio": 22, "rubio_oscuro": 22, "castano_claro": 20, "castano": 18, "castano_oscuro": 10, "negro": 6, "pelirrojo": 4},
                     "textura": {"lacio": 55, "ondulado": 30, "rizado": 9, "muy_rizado": 6}, "ojos": {"azul": 40, "verde": 15, "avellana": 15, "marron": 30}},
    "europa_sur": {"piel": [8, 22, 26, 18, 10, 6, 4, 3, 2, 1], "pelo": {"negro": 30, "castano_oscuro": 34, "castano": 20, "castano_claro": 10, "rubio_oscuro": 5, "rubio": 1},
                   "textura": {"lacio": 40, "ondulado": 38, "rizado": 16, "muy_rizado": 6}, "ojos": {"marron": 60, "avellana": 20, "verde": 12, "azul": 8}},
    "europa_este": {"piel": [18, 30, 22, 12, 6, 4, 3, 2, 2, 1], "pelo": {"castano": 26, "castano_oscuro": 24, "castano_claro": 18, "rubio_oscuro": 14, "negro": 12, "rubio": 6},
                    "textura": {"lacio": 55, "ondulado": 33, "rizado": 8, "muy_rizado": 4}, "ojos": {"azul": 25, "verde": 15, "avellana": 20, "marron": 40}},
    "diversa": {"piel": [12, 13, 12, 10, 9, 9, 9, 9, 9, 8], "pelo": {"negro": 32, "castano_oscuro": 24, "castano": 18, "castano_claro": 10, "rubio_oscuro": 8, "rubio": 6, "pelirrojo": 2},
                "textura": {"lacio": 30, "ondulado": 25, "rizado": 20, "muy_rizado": 25}, "ojos": {"marron": 62, "avellana": 14, "verde": 10, "azul": 14}},
    "rio_plata": {"piel": [10, 24, 26, 18, 10, 5, 3, 2, 1, 1], "pelo": {"castano_oscuro": 34, "negro": 26, "castano": 24, "castano_claro": 10, "rubio_oscuro": 5, "rubio": 1},
                  "textura": {"lacio": 42, "ondulado": 36, "rizado": 14, "muy_rizado": 8}, "ojos": {"marron": 62, "avellana": 18, "verde": 10, "azul": 10}},
    "sudamerica": {"piel": [3, 8, 14, 20, 20, 15, 9, 6, 3, 2], "pelo": {"negro": 58, "castano_oscuro": 28, "castano": 10, "castano_claro": 4},
                   "textura": {"lacio": 45, "ondulado": 25, "rizado": 15, "muy_rizado": 15}, "ojos": {"marron": 86, "avellana": 10, "verde": 3, "azul": 1}},
    "mesoamerica": {"piel": [2, 6, 12, 20, 24, 18, 9, 5, 3, 1], "pelo": {"negro": 66, "castano_oscuro": 24, "castano": 8, "castano_claro": 2},
                    "textura": {"lacio": 62, "ondulado": 24, "rizado": 9, "muy_rizado": 5}, "ojos": {"marron": 90, "avellana": 8, "verde": 1, "azul": 1}},
    "caribe": {"piel": [1, 2, 3, 4, 6, 10, 16, 22, 20, 16], "pelo": {"negro": 82, "castano_oscuro": 16, "castano": 2},
               "textura": {"lacio": 4, "ondulado": 8, "rizado": 28, "muy_rizado": 60}, "ojos": {"marron": 95, "avellana": 5}},
    "caribe_hispano": {"piel": [3, 6, 10, 14, 16, 16, 14, 10, 7, 4], "pelo": {"negro": 64, "castano_oscuro": 26, "castano": 8, "castano_claro": 2},
                       "textura": {"lacio": 22, "ondulado": 22, "rizado": 26, "muy_rizado": 30}, "ojos": {"marron": 88, "avellana": 9, "verde": 2, "azul": 1}},
    "africa_norte_medio_oriente": {"piel": [3, 10, 22, 26, 18, 10, 5, 3, 2, 1], "pelo": {"negro": 62, "castano_oscuro": 30, "castano": 7, "castano_claro": 1},
                                   "textura": {"lacio": 22, "ondulado": 38, "rizado": 28, "muy_rizado": 12}, "ojos": {"marron": 84, "avellana": 12, "verde": 3, "azul": 1}},
    "africa_subsahariana": {"piel": [1, 1, 2, 3, 4, 7, 14, 22, 24, 22], "pelo": {"negro": 92, "castano_oscuro": 8},
                            "textura": {"lacio": 2, "ondulado": 3, "rizado": 20, "muy_rizado": 75}, "ojos": {"marron": 98, "avellana": 2}},
    "asia_sur": {"piel": [1, 3, 6, 12, 20, 22, 18, 10, 5, 3], "pelo": {"negro": 82, "castano_oscuro": 16, "castano": 2},
                 "textura": {"lacio": 46, "ondulado": 38, "rizado": 12, "muy_rizado": 4}, "ojos": {"marron": 94, "avellana": 5, "verde": 1}},
    "asia_este": {"piel": [12, 30, 30, 15, 6, 3, 2, 1, 1, 0.5], "pelo": {"negro": 82, "castano_oscuro": 16, "castano": 2},
                  "textura": {"lacio": 86, "ondulado": 10, "rizado": 3, "muy_rizado": 1}, "ojos": {"marron": 98, "avellana": 2}},
    "asia_sudeste": {"piel": [3, 10, 18, 24, 22, 13, 6, 2, 1, 1], "pelo": {"negro": 86, "castano_oscuro": 14},
                     "textura": {"lacio": 72, "ondulado": 18, "rizado": 7, "muy_rizado": 3}, "ojos": {"marron": 98, "avellana": 2}},
    "asia_central": {"piel": [6, 18, 26, 22, 14, 7, 4, 1, 1, 1], "pelo": {"negro": 64, "castano_oscuro": 28, "castano": 7, "castano_claro": 1},
                     "textura": {"lacio": 66, "ondulado": 26, "rizado": 6, "muy_rizado": 2}, "ojos": {"marron": 80, "avellana": 14, "verde": 4, "azul": 2}},
    "pacifico": {"piel": [1, 2, 4, 7, 12, 18, 22, 18, 10, 6], "pelo": {"negro": 86, "castano_oscuro": 14},
                 "textura": {"lacio": 12, "ondulado": 30, "rizado": 33, "muy_rizado": 25}, "ojos": {"marron": 97, "avellana": 3}},
}

# País (nombre en Mongo) -> región. Los que no estén acá usan la región por defecto de su confederación.
REGION_POR_PAIS = {}
for _region, _paises in {
    "europa_norte": ["Noruega", "Suecia", "Finlandia", "Islandia", "Dinamarca", "Islas Feroe", "Alemania", "Escocia", "Gales",
                     "Irlanda", "Irlanda del Norte", "Estonia", "Letonia", "Lituania", "Luxemburgo", "Austria", "Liechtenstein"],
    "europa_sur": ["España", "Portugal", "Italia", "Grecia", "Malta", "Chipre", "San Marino", "Andorra", "Gibraltar"],
    "europa_este": ["Rusia", "Ucrania", "Bielorrusia", "Moldavia", "Rumanía", "Bulgaria", "Serbia", "Croacia", "Bosnia y Herzegovina",
                    "Montenegro", "Macedonia del Norte", "Albania", "Kosovo", "Eslovenia", "Hungría", "Polonia", "República Checa", "Eslovaquia"],
    "diversa": ["Francia", "Inglaterra", "Países Bajos", "Bélgica", "Suiza", "Brasil", "Estados Unidos", "Canadá", "Colombia",
                "Ecuador", "Venezuela", "Panamá", "Costa Rica", "Australia", "Nueva Zelanda", "Surinam", "Guyana", "Sudáfrica"],
    "rio_plata": ["Argentina", "Uruguay", "Chile"],
    "africa_norte_medio_oriente": ["Turquía", "Armenia", "Azerbaiyán", "Georgia", "Israel", "Marruecos", "Argelia", "Túnez", "Libia",
                                   "Egipto", "Arabia Saudita", "Catar", "Emiratos Árabes Unidos", "Irak", "Irán", "Jordania", "Kuwait",
                                   "Líbano", "Omán", "Palestina", "Siria", "Yemen", "Baréin", "Sudán", "Mauritania"],
    "asia_central": ["Kazajistán", "Kirguistán", "Tayikistán", "Turkmenistán", "Uzbekistán", "Afganistán", "Mongolia"],
    "asia_sur": ["India", "Pakistán", "Bangladés", "Sri Lanka", "Nepal", "Bután", "Maldivas"],
    "asia_este": ["China", "Japón", "Corea del Sur", "Corea del Norte", "Taiwán", "Hong Kong", "Macao"],
    "asia_sudeste": ["Tailandia", "Vietnam", "Filipinas", "Indonesia", "Malasia", "Singapur", "Camboya", "Laos", "Myanmar", "Brunéi",
                     "Timor Oriental", "Guam"],
    "caribe_hispano": ["Cuba", "República Dominicana", "Puerto Rico", "Belice", "Honduras", "Nicaragua", "Aruba", "Curazao"],
    "mesoamerica": ["México", "Guatemala", "El Salvador", "Bolivia", "Perú", "Paraguay"],
    "pacifico": ["Fiyi", "Samoa", "Samoa Americana", "Tonga", "Papúa Nueva Guinea", "Islas Salomón", "Vanuatu", "Tahití",
                 "Islas Cook", "Nueva Caledonia"],
}.items():
    for _p in _paises:
        REGION_POR_PAIS[_p] = _region
REGION_POR_CONFEDERACION = {1: "europa_sur", 2: "sudamerica", 3: "caribe", 4: "africa_subsahariana", 5: "pacifico", 6: "asia_sudeste"}

PEINADOS_POR_TEXTURA = {
    "lacio": {"corto": 18, "raya": 18, "ondulado": 8, "rapado": 8, "degradado": 12, "largo_atado": 5, "calvo": 3,
              "flequillo": 10, "tupe": 9, "melena": 5, "cresta": 4},
    "ondulado": {"corto": 16, "raya": 12, "ondulado": 20, "rapado": 8, "degradado": 11, "largo_atado": 5, "rulos": 4,
                 "tupe": 9, "melena": 7, "flequillo": 6, "cresta": 2},
    "rizado": {"rulos": 26, "corto": 11, "rapado": 11, "degradado": 15, "ondulado": 6, "afro": 6, "calvo": 2,
               "rastas": 8, "trenzas": 7, "cresta": 8},
    "muy_rizado": {"rapado": 22, "degradado": 19, "rulos": 11, "afro": 10, "corto": 7, "calvo": 5,
                   "trenzas": 11, "rastas": 9, "cresta": 6},
}


def _elegir(rnd, pesos):
    claves = list(pesos)
    return rnd.choices(claves, weights=[pesos[k] for k in claves])[0]


def _oscurecer(hex_color, f):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(c * f))) for c in (r, g, b)))


def _suave(puntos, cerrado=True):
    """Path suave que pasa por los puntos (Catmull-Rom -> Bézier cúbica)."""
    n = len(puntos)
    if n < 3:
        return ""
    d = f"M{puntos[0][0]:.1f} {puntos[0][1]:.1f}"
    rango = range(n) if cerrado else range(n - 1)
    for i in rango:
        p0 = puntos[(i - 1) % n] if cerrado or i > 0 else puntos[i]
        p1, p2 = puntos[i], puntos[(i + 1) % n]
        p3 = puntos[(i + 2) % n] if cerrado or i + 2 < n else p2
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d + ("Z" if cerrado else "")


def _espejo(puntos_derecha):
    """Contorno simétrico: puntos del lado derecho (de arriba hacia abajo) + su reflejo."""
    izquierda = [(2 * CX - x, y) for x, y in reversed(puntos_derecha)]
    return puntos_derecha + izquierda


class Avatar:
    def __init__(self, jugador_id, edad, region, jersey):
        self.rnd = random.Random(jugador_id)
        r = self.rnd
        reg = REGIONES[region]
        self.piel = r.choices(PIELES, weights=reg["piel"])[0]
        self.piel_sombra = _oscurecer(self.piel, 0.9)
        self.textura = _elegir(r, reg["textura"])
        self.pelo = PELOS[_elegir(r, reg["pelo"])]
        if edad >= 33 and r.random() < 0.18:
            self.pelo = r.choice(CANAS)
        self.ojos = OJOS[_elegir(r, reg["ojos"])]
        self.edad = edad
        self.peinado = _elegir(r, PEINADOS_POR_TEXTURA[self.textura])
        if edad >= 31 and self.peinado in ("raya", "ondulado", "largo_atado") and r.random() < 0.25:
            self.peinado = "corto"
        self.entradas = edad >= 30 and r.random() < 0.3
        prob_barba = 0.25 if edad < 23 else (0.5 if edad < 30 else 0.65)
        self.barba = _elegir(r, {"incipiente": 45, "candado": 25, "completa": 30}) if r.random() < prob_barba else None
        self.boca = _elegir(r, {"dientes": 45, "sonrisa": 35, "seria": 20})
        self.forma = _elegir(r, {"oval": 35, "cuadrada": 25, "redonda": 20, "alargada": 20})
        self.cuello_camiseta = _elegir(r, {"redondo": 45, "v": 35, "polo": 20})
        # forma de ojos: variación general (no depende de la región)
        self.forma_ojos = _elegir(r, {"almendrado": 45, "redondo": 30, "rasgado": 25})
        self.jersey = jersey  # (principal, secundario)
        self._geometria()

    # --- geometría de la cara -----------------------------------------------------------------------
    def _geometria(self):
        hw = self.rnd.uniform(112, 124)
        forma = {"oval": (0.95, 1.0, 0.72, 0.30, 352), "cuadrada": (0.97, 1.0, 0.86, 0.42, 346),
                 "redonda": (1.0, 1.04, 0.80, 0.36, 338), "alargada": (0.92, 0.94, 0.70, 0.30, 364)}[self.forma]
        self.top = 112
        self.sien = hw * forma[0]
        self.mejilla = hw * forma[1]
        self.mandibula = hw * forma[2]
        self.menton = hw * forma[3]
        self.menton_y = forma[4]
        self.contorno_cara = _espejo([
            (CX, self.top), (CX + self.sien * 0.62, self.top + 10), (CX + self.sien, self.top + 58),
            (CX + self.mejilla, 245), (CX + self.mandibula, 312), (CX + self.menton, self.menton_y - 4),
            (CX + self.menton * 0.35, self.menton_y + 4),
        ])[:-1]
        self.ojo_y = 236 + (6 if self.forma == "alargada" else 0)

    # --- piezas --------------------------------------------------------------------------------------
    def _camiseta(self):
        principal, secundario = self.jersey
        sombra = _oscurecer(principal, 0.78)
        cuerpo = "M60 512C70 448 130 410 200 398L312 398C382 410 442 448 452 512Z"
        partes = [f'<clipPath id="cam"><path d="{cuerpo}"/></clipPath>',
                  f'<path d="{cuerpo}" fill="{principal}"/>',
                  f'<path d="M330 398C400 412 446 450 452 512L300 512Z" fill="{sombra}" clip-path="url(#cam)"/>',
                  # vivos en los hombros (detalle del jersey)
                  f'<path d="M150 418C120 440 96 470 86 512M362 418C392 440 416 470 426 512" fill="none" stroke="{secundario}" stroke-width="9"/>']
        if self.cuello_camiseta == "v":
            partes.append(f'<path d="M206 398L256 452L306 398Z" fill="{self.piel_sombra}" stroke="{secundario}" stroke-width="10" stroke-linejoin="round"/>')
        elif self.cuello_camiseta == "polo":
            partes.append(f'<path d="M204 396L256 430L234 448Z M308 396L256 430L278 448Z" fill="{secundario}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>')
        else:
            partes.append(f'<path d="M204 398C222 428 290 428 308 398" fill="none" stroke="{secundario}" stroke-width="12" stroke-linecap="round"/>')
        partes.append(f'<path d="{cuerpo}" fill="none" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>')
        return "".join(partes)

    def _cuello(self):
        return (f'<path d="M{CX - 46} 300L{CX + 46} 300L{CX + 54} 410C{CX + 20} 428 {CX - 20} 428 {CX - 54} 410Z" fill="{self.piel}" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>'
                f'<path d="M{CX - 50} 340C{CX - 20} 372 {CX + 20} 372 {CX + 52} 340L{CX + 50} 300L{CX - 46} 300Z" fill="{self.piel_sombra}"/>')

    def _orejas(self):
        partes = []
        for s in (-1, 1):
            x = CX + s * (self.mejilla - 6)
            partes.append(f'<ellipse cx="{x:.1f}" cy="240" rx="21" ry="33" fill="{self.piel}" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>'
                          f'<path d="M{x + s * 4:.1f} 222C{x + s * 12:.1f} 232 {x + s * 10:.1f} 252 {x + s * 2:.1f} 260" fill="none" stroke="{CONTORNO}" stroke-width="3"/>')
        return "".join(partes)

    def _cara(self):
        d = _suave(self.contorno_cara)
        # franja de sombra sobre el borde derecho de la cara (luz desde la izquierda, como las referencias)
        sombra = _suave([(CX + self.sien * 0.55, self.top - 20), (CX + self.sien + 30, self.top), (CX + self.mejilla + 30, 260),
                         (CX + self.menton + 30, self.menton_y + 20), (CX + self.menton * 0.6, self.menton_y + 10),
                         (CX + self.mandibula * 0.72, 300), (CX + self.mejilla * 0.74, 240), (CX + self.sien * 0.7, 160)])
        return (f'<clipPath id="cara"><path d="{d}"/></clipPath>'
                f'<path d="{d}" fill="{self.piel}"/>'
                f'<path d="{sombra}" fill="{self.piel_sombra}" clip-path="url(#cara)"/>'
                f'<path d="{d}" fill="none" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>')

    def _ojos(self):
        """Ojos más expresivos: iris grande con aro, doble brillo, pliegue del párpado y pestañas."""
        y = self.ojo_y
        ancho, alto_sup, alto_inf = {"almendrado": (23, 16, 10), "redondo": (21, 19, 13), "rasgado": (23, 12, 8)}[self.forma_ojos]
        pliegue = _oscurecer(self.piel, 0.72)
        partes = []
        for s in (-1, 1):
            x = CX + s * 46
            ojo = f"M{x - ancho} {y}Q{x} {y - alto_sup * 1.6:.1f} {x + ancho} {y}Q{x} {y + alto_inf * 1.4:.1f} {x - ancho} {y}Z"
            partes.append(
                f'<clipPath id="ojo{s}"><path d="{ojo}"/></clipPath>'
                f'<path d="{ojo}" fill="#fff"/>'
                f'<g clip-path="url(#ojo{s})">'
                f'<circle cx="{x + s * 1.5}" cy="{y - 1}" r="10" fill="{self.ojos}" stroke="{_oscurecer(self.ojos, 0.55)}" stroke-width="2"/>'
                f'<circle cx="{x + s * 1.5}" cy="{y - 1}" r="4.6" fill="#120d0a"/>'
                f'<circle cx="{x + s * 1.5 - 3.4:.1f}" cy="{y - 4.6:.1f}" r="2.9" fill="#fff"/>'
                f'<circle cx="{x + s * 1.5 + 3.2:.1f}" cy="{y + 2.6:.1f}" r="1.3" fill="#fff" fill-opacity="0.85"/>'
                f'<path d="M{x - ancho} {y - 2}Q{x} {y - alto_sup * 1.4:.1f} {x + ancho} {y - 2}" fill="none" stroke="#000" stroke-opacity="0.12" stroke-width="5"/>'
                f'</g>'
                # párpado superior grueso con pestaña hacia afuera
                f'<path d="M{x - ancho - 2} {y + 1}Q{x} {y - alto_sup * 1.7:.1f} {x + ancho + 2} {y + 1}" fill="none" stroke="{CONTORNO}" stroke-width="4.5" stroke-linecap="round"/>'
                f'<path d="M{x + s * (ancho + 1)} {y - 1}l{s * 6} -5" stroke="{CONTORNO}" stroke-width="3" stroke-linecap="round"/>'
                # línea inferior y pliegue del párpado
                f'<path d="M{x - ancho + 5} {y + 3}Q{x} {y + alto_inf * 1.5:.1f} {x + ancho - 4} {y + 2}" fill="none" stroke="{CONTORNO}" stroke-width="1.6" stroke-opacity="0.7"/>'
                f'<path d="M{x - ancho + 4} {y - alto_sup - 3:.1f}Q{x} {y - alto_sup * 1.9 - 3:.1f} {x + ancho - 2} {y - alto_sup - 4:.1f}" fill="none" stroke="{pliegue}" stroke-opacity="0.55" stroke-width="1.8" stroke-linecap="round"/>')
            if self.edad >= 30:
                partes.append(f'<path d="M{x - 12} {y + alto_inf + 6}Q{x} {y + alto_inf + 10} {x + 12} {y + alto_inf + 6}" fill="none" stroke="{_oscurecer(self.piel, 0.7)}" stroke-width="2" stroke-linecap="round"/>')
        return "".join(partes)

    def _cejas(self):
        r = self.rnd
        grosor = r.uniform(7, 11)
        inclinacion = r.uniform(-4, 5)
        y = self.ojo_y - 30
        color = self.pelo if self.peinado != "calvo" or self.pelo not in CANAS else "#3b2a20"
        partes = []
        for s in (-1, 1):
            xi, xe = CX + s * 22, CX + s * 74
            partes.append(f'<path d="M{xi} {y + 6 + inclinacion:.1f}Q{CX + s * 46} {y - 6:.1f} {xe} {y + 2 - inclinacion:.1f}'
                          f'L{xe} {y + 2 - inclinacion + grosor * 0.5:.1f}Q{CX + s * 46} {y - 6 + grosor:.1f} {xi} {y + 6 + inclinacion + grosor:.1f}Z" fill="{color}"/>')
        return "".join(partes)

    def _nariz(self):
        ancho = self.rnd.choice([13, 16, 19])
        largo = self.rnd.choice([0, 5, 9])
        y0, y1 = self.ojo_y + 8, self.ojo_y + 48 + largo
        return (f'<path d="M{CX + 6} {y0}C{CX + 12} {y0 + 20} {CX + 16} {y1 - 14} {CX + 12} {y1 - 6}" fill="none" stroke="{_oscurecer(self.piel, 0.68)}" stroke-width="3.5" stroke-linecap="round"/>'
                f'<path d="M{CX - 6} {y0 + 6}L{CX - 4} {y1 - 18}" stroke="#fff" stroke-opacity="0.45" stroke-width="4" stroke-linecap="round"/>'
                f'<path d="M{CX - ancho} {y1 - 2}Q{CX - ancho + 6} {y1 + 8} {CX - 4} {y1 + 3}M{CX + 4} {y1 + 3}Q{CX + ancho - 6} {y1 + 8} {CX + ancho} {y1 - 2}" fill="none" stroke="{CONTORNO}" stroke-width="3" stroke-linecap="round"/>')

    def _barba(self):
        if not self.barba:
            return ""
        color = self.pelo
        if self.barba == "candado":
            y = self.ojo_y + 70
            return (f'<path d="M{CX - 34} {y + 2}Q{CX} {y - 10} {CX + 34} {y + 2}Q{CX} {y - 2} {CX - 34} {y + 2}Z" fill="{color}"/>'
                    f'<path d="M{CX - 30} {self.menton_y - 22}Q{CX} {self.menton_y - 32} {CX + 30} {self.menton_y - 22}L{CX + self.menton * 0.9:.1f} {self.menton_y - 4}'
                    f'Q{CX} {self.menton_y + 8} {CX - self.menton * 0.9:.1f} {self.menton_y - 4}Z" fill="{color}" clip-path="url(#cara)"/>')
        y0 = self.ojo_y + 42  # la barba arranca debajo de los pómulos
        zona = _suave([(CX - self.mejilla - 10, y0 - 10), (CX - self.mejilla + 14, y0), (CX - 42, self.ojo_y + 70), (CX, self.ojo_y + 64),
                       (CX + 42, self.ojo_y + 70), (CX + self.mejilla - 14, y0), (CX + self.mejilla + 10, y0 - 10),
                       (CX + self.mejilla + 10, self.menton_y + 30), (CX - self.mejilla - 10, self.menton_y + 30)])
        opacidad = "0.3" if self.barba == "incipiente" else "1"
        return f'<path d="{zona}" fill="{color}" fill-opacity="{opacidad}" clip-path="url(#cara)"/>'

    def _boca(self):
        y = self.ojo_y + 82 + (4 if self.forma == "alargada" else 0)
        labio = _oscurecer(self.piel, 0.72)
        if self.boca == "dientes":
            return (f'<path d="M{CX - 40} {y - 6}Q{CX} {y + 30} {CX + 40} {y - 6}Q{CX} {y + 4} {CX - 40} {y - 6}Z" fill="#fff" stroke="{CONTORNO}" stroke-width="3.5" stroke-linejoin="round"/>'
                    f'<path d="M{CX - 34} {y + 5}Q{CX} {y + 14} {CX + 34} {y + 5}" fill="none" stroke="#d9d4cf" stroke-width="2"/>'
                    f'<path d="M{CX - 22} {y + 22}Q{CX} {y + 30} {CX + 22} {y + 22}" fill="none" stroke="{labio}" stroke-width="3" stroke-linecap="round"/>')
        if self.boca == "sonrisa":
            return (f'<path d="M{CX - 34} {y}Q{CX} {y + 18} {CX + 34} {y}" fill="none" stroke="{CONTORNO}" stroke-width="4" stroke-linecap="round"/>'
                    f'<path d="M{CX - 16} {y + 16}Q{CX} {y + 22} {CX + 16} {y + 16}" fill="none" stroke="{labio}" stroke-width="3" stroke-linecap="round"/>')
        return (f'<path d="M{CX - 26} {y + 4}Q{CX} {y + 8} {CX + 26} {y + 4}" fill="none" stroke="{CONTORNO}" stroke-width="4" stroke-linecap="round"/>'
                f'<path d="M{CX - 14} {y + 15}Q{CX} {y + 19} {CX + 14} {y + 15}" fill="none" stroke="{labio}" stroke-width="3" stroke-linecap="round"/>')

    # --- pelo ------------------------------------------------------------------------------------------
    def _casquete(self, volumen, linea_frente=None):
        """Pelo que cubre la parte de arriba de la cabeza: contorno exterior + línea de nacimiento."""
        s, t = self.sien, self.top
        lf = linea_frente if linea_frente is not None else t + 40
        sienes_y = t + (44 if self.entradas else 62)
        exterior = [(CX - s - 8, t + 92), (CX - s - 6, t + 30), (CX - s * 0.6, t - volumen * 0.7),
                    (CX, t - volumen), (CX + s * 0.6, t - volumen * 0.7), (CX + s + 6, t + 30), (CX + s + 8, t + 92)]
        nacimiento = [(CX + s - 4, t + 92), (CX + s - 10, sienes_y), (CX + s * 0.45, lf - (14 if self.entradas else 0)),
                      (CX, lf + (10 if self.entradas else 0)), (CX - s * 0.45, lf - (14 if self.entradas else 0)),
                      (CX - s + 10, sienes_y), (CX - s + 4, t + 92)]
        return exterior + nacimiento

    def _pelo_detras(self):
        if self.peinado == "afro":
            pts = []
            for i in range(26):
                a = math.pi + math.pi * i / 25
                rr = 1.0 + 0.06 * math.sin(i * 2.7)
                pts.append((CX + (self.sien + 52) * math.cos(a) * rr, self.top + 75 + 128 * math.sin(a) * rr))
            pts += [(CX + self.sien + 30, self.top + 120), (CX - self.sien - 30, self.top + 120)]
            return f'<path d="{_suave(pts)}" fill="{self.pelo}" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>'
        if self.peinado == "melena":
            # pelo largo suelto que cae por detrás hasta los hombros
            pts = [(CX - self.sien - 22, self.top + 40), (CX - self.sien - 30, self.top + 170), (CX - self.mejilla - 20, 372),
                   (CX - 70, 382), (CX + 70, 382), (CX + self.mejilla + 20, 372), (CX + self.sien + 30, self.top + 170),
                   (CX + self.sien + 22, self.top + 40), (CX, self.top - 30)]
            return f'<path d="{_suave(pts)}" fill="{self.pelo}" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>'
        if self.peinado == "rastas":
            rastas = []
            for s in (-1, 1):
                for k in range(4):
                    x = CX + s * (self.sien + 10 - k * 13)
                    rastas.append(f'<rect x="{x - 12:.1f}" y="{self.top + 24 + k * 4}" width="24" height="{250 - k * 22}" rx="12" '
                                  f'fill="{self.pelo}" stroke="{CONTORNO}" stroke-width="3.5"/>')
            return "".join(rastas)
        if self.peinado == "largo_atado":
            return (f'<circle cx="{CX + 8}" cy="{self.top - 32}" r="27" fill="{self.pelo}" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>')
        return ""

    def _pelo(self):
        p, color = self.peinado, self.pelo
        brillo = _oscurecer(color, 1.35) if color != PELOS["negro"] else "#3a322c"
        trazo = f'stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}" stroke-linejoin="round"'
        if p == "calvo":
            return f'<path d="M{CX - 50} {self.top + 26}Q{CX - 20} {self.top + 8} {CX + 10} {self.top + 14}" fill="none" stroke="#fff" stroke-opacity="0.35" stroke-width="6" stroke-linecap="round"/>'
        if p == "rapado":
            return f'<path d="{_suave(self._casquete(8, self.top + 30))}" fill="{color}" fill-opacity="0.85" {trazo}/>'
        if p == "degradado":
            lados = f'<path d="{_suave(self._casquete(10, self.top + 34))}" fill="{color}" fill-opacity="0.45"/>'
            arriba = [(CX - self.sien * 0.82, self.top + 46), (CX - self.sien * 0.9, self.top - 6), (CX, self.top - 36),
                      (CX + self.sien * 0.9, self.top - 6), (CX + self.sien * 0.82, self.top + 46), (CX, self.top + 36)]
            return lados + f'<path d="{_suave(arriba)}" fill="{color}" {trazo}/>'
        if p == "rulos":
            base = self._casquete(30, self.top + 38)
            rulos = "".join(f'<circle cx="{CX + (self.sien + 4) * math.cos(a):.1f}" cy="{self.top + 46 - (self.sien * 0.62 + 14) * math.sin(a):.1f}" r="15" fill="{color}" {trazo}/>'
                            for a in [math.pi * i / 10 for i in range(11)])
            return f'<path d="{_suave(base)}" fill="{color}" {trazo}/>' + rulos + \
                   "".join(f'<circle cx="{CX + 34 * k:.1f}" cy="{self.top + 8 - 6 * abs(k):.1f}" r="14" fill="{color}" {trazo}/>' for k in (-2, -1, 0, 1, 2))
        if p == "afro":
            return f'<path d="{_suave(self._casquete(20, self.top + 34))}" fill="{color}" {trazo}/>'
        if p == "raya":
            forma = self._casquete(34, self.top + 34)
            raya = f'<path d="M{CX - 34} {self.top + 30}Q{CX - 30} {self.top - 4} {CX - 22} {self.top - 26}" fill="none" stroke="{_oscurecer(color, 0.6)}" stroke-width="3.5" stroke-linecap="round"/>'
            mechones = f'<path d="M{CX - 14} {self.top - 18}Q{CX + 40} {self.top - 30} {CX + 80} {self.top + 8}M{CX - 4} {self.top + 2}Q{CX + 44} {self.top - 8} {CX + 88} {self.top + 26}" fill="none" stroke="{brillo}" stroke-width="3" stroke-linecap="round"/>'
            return f'<path d="{_suave(forma)}" fill="{color}" {trazo}/>' + raya + mechones
        if p == "ondulado":
            forma = self._casquete(52, self.top + 36)
            ondas = "".join(f'<path d="M{CX - 60 + 30 * k} {self.top - 4}q12 -22 26 -6" fill="none" stroke="{brillo}" stroke-width="3" stroke-linecap="round"/>' for k in range(5))
            return f'<path d="{_suave(forma)}" fill="{color}" {trazo}/>' + ondas
        if p == "largo_atado":
            return f'<path d="{_suave(self._casquete(14, self.top + 32))}" fill="{color}" {trazo}/>' + \
                   f'<path d="M{CX - 40} {self.top + 6}Q{CX} {self.top - 10} {CX + 40} {self.top + 6}" fill="none" stroke="{brillo}" stroke-width="3" stroke-linecap="round"/>'
        if p == "cresta":
            lados = f'<path d="{_suave(self._casquete(8, self.top + 30))}" fill="{color}" fill-opacity="0.35"/>'
            cresta = [(CX - 24, self.top + 36), (CX - 30, self.top - 8), (CX - 16, self.top - 50), (CX, self.top - 64),
                      (CX + 16, self.top - 50), (CX + 30, self.top - 8), (CX + 24, self.top + 36)]
            return lados + f'<path d="{_suave(cresta)}" fill="{color}" {trazo}/>' + \
                   f'<path d="M{CX - 4} {self.top - 50}Q{CX + 8} {self.top - 10} {CX + 2} {self.top + 26}" fill="none" stroke="{brillo}" stroke-width="3"/>'
        if p == "trenzas":
            base = f'<path d="{_suave(self._casquete(12, self.top + 34))}" fill="{color}" {trazo}/>'
            lineas = "".join(f'<path d="M{CX + k * 22} {self.top + 32 - abs(k) * 4}Q{CX + k * 26} {self.top - 2} {CX + k * 14} {self.top - 10}" '
                             f'fill="none" stroke="{brillo}" stroke-width="3" stroke-dasharray="5 5"/>' for k in (-3, -2, -1, 0, 1, 2, 3))
            return base + lineas
        if p == "rastas":
            base = f'<path d="{_suave(self._casquete(22, self.top + 36))}" fill="{color}" {trazo}/>'
            lineas = "".join(f'<path d="M{CX + k * 20} {self.top + 34}Q{CX + k * 24} {self.top} {CX + k * 12} {self.top - 18}" fill="none" stroke="{brillo}" stroke-width="3"/>'
                             for k in (-3, -2, -1, 0, 1, 2, 3))
            return base + lineas
        if p == "melena":
            forma = self._casquete(26, self.top + 40)
            raya = f'<path d="M{CX + 6} {self.top + 36}Q{CX + 4} {self.top} {CX + 10} {self.top - 24}" fill="none" stroke="{_oscurecer(color, 0.6)}" stroke-width="3.5" stroke-linecap="round"/>'
            return f'<path d="{_suave(forma)}" fill="{color}" {trazo}/>' + raya
        if p == "flequillo":
            # flequillo recto con puntas sobre la frente
            s_ = self.sien
            pts = [(CX - s_ - 8, self.top + 92), (CX - s_ - 6, self.top + 26), (CX - s_ * 0.6, self.top - 20), (CX, self.top - 28),
                   (CX + s_ * 0.6, self.top - 20), (CX + s_ + 6, self.top + 26), (CX + s_ + 8, self.top + 92), (CX + s_ - 6, self.top + 70)]
            for k in range(6, -7, -2):
                pts.append((CX + k * s_ / 7.5, self.top + (66 if k % 4 == 0 else 54)))
            pts.append((CX - s_ + 6, self.top + 70))
            return f'<path d="{_suave(pts)}" fill="{color}" {trazo}/>' + \
                   f'<path d="M{CX - 40} {self.top + 2}Q{CX + 10} {self.top - 14} {CX + 60} {self.top + 8}" fill="none" stroke="{brillo}" stroke-width="3"/>'
        if p == "tupe":
            forma = self._casquete(40, self.top + 38)
            frente = [(CX - self.sien * 0.7, self.top + 30), (CX - self.sien * 0.6, self.top - 30), (CX - 10, self.top - 66),
                      (CX + 40, self.top - 72), (CX + self.sien * 0.75, self.top - 40), (CX + self.sien * 0.8, self.top + 26), (CX, self.top + 20)]
            return f'<path d="{_suave(forma)}" fill="{color}" {trazo}/>' + f'<path d="{_suave(frente)}" fill="{color}" {trazo}/>' + \
                   f'<path d="M{CX - 30} {self.top - 40}Q{CX + 20} {self.top - 74} {CX + 66} {self.top - 34}M{CX - 20} {self.top - 14}Q{CX + 24} {self.top - 44} {CX + 76} {self.top - 6}" fill="none" stroke="{brillo}" stroke-width="3" stroke-linecap="round"/>'
        # corto
        forma = self._casquete(24, self.top + 36)
        return f'<path d="{_suave(forma)}" fill="{color}" {trazo}/>' + \
               f'<path d="M{CX - 50} {self.top + 4}Q{CX + 10} {self.top - 16} {CX + 70} {self.top + 10}" fill="none" stroke="{brillo}" stroke-width="3" stroke-linecap="round"/>'

    def svg(self):
        cuerpo = (self._pelo_detras() + self._camiseta() + self._cuello() + self._orejas() + self._cara() + self._barba()
                  + self._ojos() + self._cejas() + self._nariz() + self._boca() + self._pelo())
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" '
                f'stroke-linecap="round">{cuerpo}</svg>')


# --- Datos (Mongo + bucket) ---------------------------------------------------------------------------
def _colores_jersey(url):
    """(principal, secundario) del jersey: los dos colores más presentes y distintos entre sí. Requiere Pillow."""
    import io
    import ssl
    import urllib.request

    import certifi
    from PIL import Image

    contexto = ssl.create_default_context(cafile=certifi.where())
    imagen = Image.open(io.BytesIO(urllib.request.urlopen(url, timeout=20, context=contexto).read())).convert("RGBA").resize((64, 64))
    opacos = Image.new("RGB", imagen.size)
    pixeles = [p[:3] for p in imagen.getdata() if p[3] > 200]
    opacos.putdata(pixeles + [(0, 0, 0)] * (64 * 64 - len(pixeles)))
    paleta = opacos.quantize(colors=6)
    conteo = sorted(paleta.getcolors(), reverse=True)
    rgb = paleta.getpalette()
    colores = [tuple(rgb[i * 3:i * 3 + 3]) for _, i in conteo]
    colores = [c for c in colores if c != (0, 0, 0)] or [(60, 90, 160)]
    principal = colores[0]
    secundario = max(colores[1:] or [(255, 255, 255)], key=lambda c: sum(abs(a - b) for a, b in zip(c, principal)))
    if sum(abs(a - b) for a, b in zip(secundario, principal)) < 90:
        secundario = (255, 255, 255) if sum(principal) < 400 else (30, 30, 30)
    return tuple("#{:02x}{:02x}{:02x}".format(*c) for c in (principal, secundario))


def _datos(solo_paises=None):
    from urllib.parse import quote
    from config.settings import IMAGENES_PAISES_URL
    from services.imagenes_pais_service import db

    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "confederacion_id": 1})}
    if solo_paises:
        paises = {i: p for i, p in paises.items() if p["nombre"] in solo_paises}
    jerseys = {}
    for pid, p in paises.items():
        try:
            jerseys[pid] = _colores_jersey(f"{IMAGENES_PAISES_URL}/jersey/{quote(p['nombre'])}.png")
        except Exception as e:
            print(f"  ⚠️ jersey de {p['nombre']}: {e}")
            jerseys[pid] = ("#3b5bdb", "#ffffff")
    filtro = {"pais_id": {"$in": list(paises)}}
    jugadores = list(db["jugadores"].find(filtro, {"id": 1, "nombre": 1, "edad": 1, "pais_id": 1}).sort("id", 1))
    return paises, jerseys, jugadores


def _region(pais):
    return REGION_POR_PAIS.get(pais["nombre"], REGION_POR_CONFEDERACION.get(pais.get("confederacion_id"), "diversa"))


def _avatar_de(j, paises, jerseys):
    pais = paises[j["pais_id"]]
    return Avatar(j["id"], j.get("edad") or 25, _region(pais), jerseys[j["pais_id"]]).svg()


def muestra(carpeta):
    """2 jugadores de cada uno de 8 países de regiones distintas (16 avatares) + un plantel completo."""
    os.makedirs(carpeta, exist_ok=True)
    elegidos = ["Argentina", "Brasil", "Francia", "Japón", "Senegal", "Marruecos", "Noruega", "México",
                "Jamaica", "India", "Fiyi", "Croacia"]
    paises, jerseys, jugadores = _datos(elegidos)
    por_pais = {}
    for j in jugadores:
        por_pais.setdefault(j["pais_id"], []).append(j)
    for pid, js in por_pais.items():
        for j in js[:4]:
            with open(os.path.join(carpeta, f"{paises[pid]['nombre']}_{j['id']}.svg"), "w") as f:
                f.write(_avatar_de(j, paises, jerseys))
    print(f"Muestra en {carpeta}")


def generar(carpeta):
    destino = os.path.join(carpeta, "jugadores")
    os.makedirs(destino, exist_ok=True)
    paises, jerseys, jugadores = _datos()
    for j in jugadores:
        with open(os.path.join(destino, f"{j['id']}.svg"), "w") as f:
            f.write(_avatar_de(j, paises, jerseys))
    print(f"{len(jugadores)} SVG en {destino}")


def subir(carpeta):
    import subprocess
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "jugadores", "*.svg"), "gs://com-icg-mundial/jugadores/",
                    "--gzip-local-all", "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def asignar():
    from pymongo import UpdateOne
    from services.imagenes_pais_service import db
    ops = [UpdateOne({"id": j["id"]}, {"$set": {"avatar_imagen": f"jugadores/{j['id']}.svg"}})
           for j in db["jugadores"].find({}, {"id": 1})]
    r = db["jugadores"].bulk_write(ops)
    print(f"Jugadores actualizados: {r.modified_count} de {len(ops)}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "avatares_generados"
    {"--muestra": lambda: muestra(carpeta), "--generar": lambda: generar(carpeta),
     "--subir": lambda: subir(carpeta), "--asignar": asignar}.get(modo, lambda: print(__doc__))()
