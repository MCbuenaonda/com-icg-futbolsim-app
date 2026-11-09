"""
Avatares ilustrados (SVG plano, busto, fondo transparente) de los directores técnicos ('directores_tecnicos').

Mismo motor que generar_avatares.py (mismas piezas, mismo trazo, rasgos por REGIÓN del país) con:
  - Traje: saco oscuro (azul marino, gris carbón o negro), camisa clara y corbata del color principal de la
    bandera del país ('paises.colores'); pañuelo en el bolsillo con el segundo color.
  - Edad real del técnico (35-75): canas, entradas y calvicie cada vez más probables, arrugas en la frente
    desde los 50 y surcos desde los 58; algunos con anteojos.
  - Peinados sobrios (sin crestas, rastas ni melenas).
Semilla = id del técnico (determinístico). Archivo: tecnicos/<id>.svg en el bucket.

    python generar_avatares_tecnicos.py --muestra [carpeta]   # 40 técnicos de regiones y edades distintas
    python generar_avatares_tecnicos.py --generar [carpeta]   # todos en <carpeta>/tecnicos/
    python generar_avatares_tecnicos.py --subir [carpeta]     # a gs://com-icg-mundial/tecnicos/
    python generar_avatares_tecnicos.py --asignar             # escribe directores_tecnicos.avatar_imagen
"""
import os
import random
import sys

from generar_avatares import CONTORNO, ANCHO_TRAZO, CX, CANAS, OJOS, PELOS, Avatar, _elegir, _oscurecer, _region

# --- Retratos a medida (DTs reales de las selecciones más grandes, de su foto de Wikidata: tono de piel, pelo, barba, calvicie,
# anteojos; con las canas y entradas de hoy, porque el DT se muestra como es ahora). Se aplican DESPUÉS del sorteo normal.
AJUSTES_TECNICO = {
    1: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#4a4542', "ojos": 'marron', "peinado": 'raya', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": True, "entradas": True},
    2: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#6e6a68', "ojos": 'marron', "peinado": 'calvo', "barba": 'incipiente', "boca": 'seria', "forma": 'redonda', "anteojos": False, "entradas": False},
    3: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#c9c9c9', "ojos": 'azul', "peinado": 'raya', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": True, "entradas": True},
    4: {"piel": '#d4996f', "textura": 'lacio', "pelo": 'negro', "ojos": 'marron', "peinado": 'raya', "barba": None, "boca": 'seria', "forma": 'oval', "anteojos": False, "entradas": False},
    5: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#6e6a68', "ojos": 'marron', "peinado": 'corto', "barba": 'incipiente', "boca": 'seria', "forma": 'cuadrada', "anteojos": False, "entradas": False},
    11: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#6e6a68', "ojos": 'marron', "peinado": 'corto', "barba": 'incipiente', "boca": 'seria', "forma": 'cuadrada', "anteojos": False, "entradas": False},
    12: {"piel": '#b0703f', "textura": 'rizado', "pelo": '#b5b5b5', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'sonrisa', "forma": 'redonda', "anteojos": True, "entradas": False},
    13: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": True},
    14: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#c9c9c9', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'oval', "anteojos": False, "entradas": False},
    15: {"piel": '#e3ac86', "textura": 'lacio', "pelo": 'castano_oscuro', "ojos": 'marron', "peinado": 'corto', "barba": 'incipiente', "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    41: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#c9c9c9', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'dientes', "forma": 'oval', "anteojos": False, "entradas": False},
    42: {"piel": '#e3ac86', "textura": 'lacio', "pelo": 'negro', "ojos": 'marron', "peinado": 'raya', "barba": 'incipiente', "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    43: {"piel": '#d4996f', "textura": 'lacio', "pelo": 'negro', "ojos": 'marron', "peinado": 'corto', "barba": 'incipiente', "boca": 'dientes', "forma": 'oval', "anteojos": False, "entradas": False},
    44: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#6e6a68', "ojos": 'marron', "peinado": 'corto', "barba": 'incipiente', "boca": 'sonrisa', "forma": 'cuadrada', "anteojos": False, "entradas": False},
    45: {"piel": '#efc4a4', "textura": 'ondulado', "pelo": 'castano', "ojos": 'marron', "peinado": 'ondulado', "barba": None, "boca": 'seria', "forma": 'oval', "anteojos": False, "entradas": False},
    56: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'azul', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": True, "entradas": True},
    57: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#6e6a68', "ojos": 'marron', "peinado": 'raya', "barba": None, "boca": 'seria', "forma": 'oval', "anteojos": False, "entradas": False},
    58: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'redonda', "anteojos": True, "entradas": True},
    59: {"piel": '#efc4a4', "textura": 'lacio', "pelo": 'castano', "ojos": 'azul', "peinado": 'raya', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    60: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'azul', "peinado": 'corto', "barba": 'incipiente', "boca": 'seria', "forma": 'alargada', "anteojos": True, "entradas": True},
    131: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#6e6a68', "ojos": 'marron', "peinado": 'corto', "barba": 'incipiente', "boca": 'seria', "forma": 'cuadrada', "anteojos": False, "entradas": False},
    133: {"piel": '#e3ac86', "textura": 'lacio', "pelo": 'negro', "ojos": 'marron', "peinado": 'calvo', "barba": 'completa', "boca": 'seria', "forma": 'oval', "anteojos": False, "entradas": False},
    134: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#6e6a68', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    146: {"piel": '#e3ac86', "textura": 'lacio', "pelo": 'castano_claro', "ojos": 'marron', "peinado": 'raya', "barba": 'incipiente', "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    147: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": True},
    148: {"piel": '#e3ac86', "textura": 'lacio', "pelo": 'castano_oscuro', "ojos": 'marron', "peinado": 'raya', "barba": 'incipiente', "boca": 'seria', "forma": 'oval', "anteojos": False, "entradas": False},
    150: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    176: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'azul', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'cuadrada', "anteojos": False, "entradas": False},
    177: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#4a4542', "ojos": 'marron', "peinado": 'raya', "barba": 'incipiente', "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    178: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'redonda', "anteojos": False, "entradas": True},
    179: {"piel": '#f6d7c3', "textura": 'lacio', "pelo": 'rubio_oscuro', "ojos": 'azul', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    180: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#4a4542', "ojos": 'marron', "peinado": 'raya', "barba": None, "boca": 'seria', "forma": 'cuadrada', "anteojos": False, "entradas": False},
    206: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'redonda', "anteojos": False, "entradas": True},
    207: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#a8a4a2', "ojos": 'marron', "peinado": 'raya', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    208: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'marron', "peinado": 'rapado', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": True},
    209: {"piel": '#e3ac86', "textura": 'lacio', "pelo": 'negro', "ojos": 'marron', "peinado": 'raya', "barba": 'incipiente', "boca": 'seria', "forma": 'oval', "anteojos": False, "entradas": False},
    210: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": True},
    266: {"piel": '#d4996f', "textura": 'rizado', "pelo": 'castano_oscuro', "ojos": 'marron', "peinado": 'ondulado', "barba": None, "boca": 'seria', "forma": 'cuadrada', "anteojos": False, "entradas": False},
    267: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'azul', "peinado": 'calvo', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    268: {"piel": '#d4996f', "textura": 'rizado', "pelo": 'negro', "ojos": 'marron', "peinado": 'ondulado', "barba": None, "boca": 'seria', "forma": 'oval', "anteojos": False, "entradas": False},
    269: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#c9c9c9', "ojos": 'azul', "peinado": 'raya', "barba": 'incipiente', "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    270: {"piel": '#efc4a4', "textura": 'rizado', "pelo": 'castano_oscuro', "ojos": 'marron', "peinado": 'ondulado', "barba": None, "boca": 'seria', "forma": 'oval', "anteojos": False, "entradas": False},
    276: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#c9c9c9', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    277: {"piel": '#efc4a4', "textura": 'lacio', "pelo": '#b5b5b5', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": True, "entradas": True},
    278: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#6e6a68', "ojos": 'marron', "peinado": 'rapado', "barba": None, "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
    279: {"piel": '#e3ac86', "textura": 'lacio', "pelo": '#6e6a68', "ojos": 'marron', "peinado": 'corto', "barba": None, "boca": 'seria', "forma": 'oval', "anteojos": False, "entradas": False},
    280: {"piel": '#e3ac86', "textura": 'lacio', "pelo": 'castano_oscuro', "ojos": 'marron', "peinado": 'corto', "barba": 'incipiente', "boca": 'seria', "forma": 'alargada', "anteojos": False, "entradas": False},
}

# 2.ª tanda de DTs reales, en retratos_tecnicos_a_medida.py; no pisa a los de arriba
from retratos_tecnicos_a_medida import AJUSTES_TECNICOS_2
AJUSTES_TECNICO.update({k: v for k, v in AJUSTES_TECNICOS_2.items() if k not in AJUSTES_TECNICO})

SACOS = {"#1f2a44": 40, "#2b2f36": 35, "#15171b": 25}       # azul marino, carbón, negro
CAMISAS = {"#f5f6f8": 70, "#dce8f5": 30}
PEINADOS_DT = {"corto": 30, "raya": 26, "degradado": 14, "ondulado": 10, "rapado": 10, "calvo": 10}


def _color_corbata(colores):
    """Primer color de la bandera que no sea blanco ni casi negro (para que la corbata se vea sobre la camisa)."""
    hexes = [c["hex"] for c in (colores or []) if c.get("hex")]
    for h in hexes:
        n = int(h[1:], 16)
        r, g, b = n >> 16, (n >> 8) & 255, n & 255
        if 60 < (r + g + b) / 3 < 225:
            return h, next((x for x in hexes if x != h), "#f5f6f8")
    return "#8a1c2b", "#f5f6f8"


class AvatarTecnico(Avatar):
    def __init__(self, tecnico_id, edad, region, colores_bandera):
        corbata, panuelo = _color_corbata(colores_bandera)
        super().__init__(tecnico_id * 7919 + 3, edad, region, (corbata, panuelo))
        r = random.Random(tecnico_id)
        self.saco = _elegir(r, SACOS)
        self.camisa = _elegir(r, CAMISAS)
        self.corbata, self.panuelo = corbata, panuelo
        self.peinado = _elegir(r, PEINADOS_DT)
        prob_canas = 0.08 if edad < 45 else 0.35 if edad < 55 else 0.65 if edad < 65 else 0.9
        if r.random() < prob_canas:
            self.pelo = r.choice(CANAS)
        self.entradas = r.random() < min(0.75, 0.2 + (edad - 35) * 0.018)
        if edad >= 55 and r.random() < 0.18:
            self.peinado = "calvo"
        if self.barba == "completa" and edad >= 50 and r.random() < 0.5:
            self.barba = "candado"
        self.anteojos = r.random() < (0.12 if edad < 50 else 0.3)
        self.boca = _elegir(r, {"sonrisa": 45, "seria": 40, "dientes": 15})
        aj = AJUSTES_TECNICO.get(tecnico_id)
        if aj:
            for k in ("piel", "textura", "peinado", "barba", "boca", "forma", "anteojos", "entradas"):
                if k in aj:
                    setattr(self, k, aj[k])
            if "pelo" in aj:
                self.pelo = PELOS.get(aj["pelo"], aj["pelo"])
            if "ojos" in aj:
                self.ojos = OJOS[aj["ojos"]]
            if "piel" in aj:
                self.piel_sombra = _oscurecer(self.piel, 0.9)
            self._geometria()

    # --- traje ---------------------------------------------------------------------------------------
    def _camiseta(self):
        cuerpo = "M60 512C70 448 130 410 200 398L312 398C382 410 442 448 452 512Z"
        luz = _oscurecer(self.saco, 1.35)
        solapa = _oscurecer(self.saco, 0.8)
        return (f'<clipPath id="cam"><path d="{cuerpo}"/></clipPath>'
                f'<path d="{cuerpo}" fill="{self.saco}"/>'
                f'<path d="M60 512C70 448 130 410 200 398L214 398C150 430 120 470 112 512Z" fill="{luz}" clip-path="url(#cam)"/>'
                # camisa en V
                f'<path d="M204 398L256 512L308 398Z" fill="{self.camisa}"/>'
                # corbata: nudo y caída
                f'<path d="M244 404L268 404L263 426L249 426Z" fill="{self.corbata}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                f'<path d="M249 426L263 426L276 494L256 512L236 494Z" fill="{self.corbata}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                f'<path d="M252 440L262 434M248 462L266 452M244 484L270 470" stroke="{_oscurecer(self.corbata, 0.75)}" stroke-width="3" stroke-linecap="round"/>'
                # cuello de la camisa
                f'<path d="M204 396L246 408L232 430Z M308 396L266 408L280 430Z" fill="{self.camisa}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                # solapas del saco
                f'<path d="M200 398L232 432L256 512L222 470L204 444L178 438Z" fill="{solapa}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                f'<path d="M312 398L280 432L256 512L290 470L308 444L334 438Z" fill="{solapa}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                # pañuelo en el bolsillo
                f'<path d="M348 462L384 458L382 468L350 472Z" fill="{_oscurecer(self.saco, 1.2)}"/>'
                f'<path d="M354 462L362 448L370 456L378 446L380 460Z" fill="{self.panuelo}" stroke="{CONTORNO}" stroke-width="2.5" stroke-linejoin="round"/>'
                f'<path d="{cuerpo}" fill="none" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>')

    # --- edad: arrugas y anteojos ---------------------------------------------------------------------
    def _arrugas(self):
        col = _oscurecer(self.piel, 0.72)
        partes = []
        if self.edad >= 50:
            y = self.top + (58 if self.entradas or self.peinado == "calvo" else 66)
            lineas = 2 if self.edad < 62 else 3
            for k in range(lineas):
                partes.append(f'<path d="M{CX - 46 + k * 6} {y + k * 11}Q{CX} {y - 6 + k * 11} {CX + 46 - k * 6} {y + k * 11}" '
                              f'fill="none" stroke="{col}" stroke-width="2.4" stroke-linecap="round" stroke-opacity="0.8"/>')
        if self.edad >= 58:
            y = self.ojo_y + 52
            partes.append(f'<path d="M{CX - 38} {y}Q{CX - 46} {y + 22} {CX - 36} {y + 40}M{CX + 38} {y}Q{CX + 46} {y + 22} {CX + 36} {y + 40}" '
                          f'fill="none" stroke="{col}" stroke-width="2.4" stroke-linecap="round" stroke-opacity="0.75"/>')
        return "".join(partes)

    def _anteojos(self):
        if not self.anteojos:
            return ""
        y = self.ojo_y
        marco = "#2a2420" if self.rnd.random() < 0.6 else "#6b6b6b"
        lentes = "".join(f'<rect x="{CX + s * 46 - 30}" y="{y - 20}" width="60" height="40" rx="14" fill="#ffffff" fill-opacity="0.12" '
                         f'stroke="{marco}" stroke-width="4.5"/>' for s in (-1, 1))
        return lentes + f'<path d="M{CX - 16} {y - 6}Q{CX} {y - 14} {CX + 16} {y - 6}" fill="none" stroke="{marco}" stroke-width="4"/>'

    def svg(self):
        cuerpo = (self._pelo_detras() + self._cuello() + self._camiseta() + self._orejas() + self._cara() + self._arrugas()
                  + self._barba() + self._ojos() + self._cejas() + self._anteojos() + self._nariz() + self._boca() + self._pelo())
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" '
                f'stroke-linecap="round">{cuerpo}</svg>')


# --- Datos (Mongo) ------------------------------------------------------------------------------------
def _datos():
    from services.imagenes_pais_service import db
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "confederacion_id": 1, "colores": 1})}
    tecnicos = list(db["directores_tecnicos"].find({}, {"id": 1, "nombre": 1, "edad": 1, "pais_id": 1}).sort("id", 1))
    return paises, tecnicos


def avatar_de(t, paises):
    pais = paises[t["pais_id"]]
    return AvatarTecnico(t["id"], t.get("edad") or 50, _region(pais), pais.get("colores")).svg()


def muestra(carpeta, tecnicos=None):
    """Una muestra variada (regiones y edades) para revisar el estilo; acepta una lista de técnicos sin insertar."""
    os.makedirs(carpeta, exist_ok=True)
    paises, en_base = _datos()
    tecnicos = tecnicos if tecnicos is not None else en_base
    elegidos = tecnicos[::max(1, len(tecnicos) // 40)][:40]
    for t in elegidos:
        with open(os.path.join(carpeta, f"{t['id']:04d}_{paises[t['pais_id']]['nombre']}_{t['edad']}.svg"), "w") as f:
            f.write(avatar_de(t, paises))
    print(f"{len(elegidos)} SVG en {carpeta}")


def generar(carpeta):
    destino = os.path.join(carpeta, "tecnicos")
    os.makedirs(destino, exist_ok=True)
    paises, tecnicos = _datos()
    for t in tecnicos:
        with open(os.path.join(destino, f"{t['id']}.svg"), "w") as f:
            f.write(avatar_de(t, paises))
    print(f"{len(tecnicos)} SVG en {destino}")


def generar_solo(carpeta, ids):
    """Solo los técnicos indicados (p. ej. los retratos de AJUSTES_TECNICO): `--solo <carpeta> 1,2,3`."""
    destino = os.path.join(carpeta, "tecnicos")
    os.makedirs(destino, exist_ok=True)
    paises, tecnicos = _datos()
    n = 0
    for t in tecnicos:
        if t["id"] in ids:
            with open(os.path.join(destino, f"{t['id']}.svg"), "w") as f:
                f.write(avatar_de(t, paises))
            n += 1
    print(f"{n} SVG en {destino}")


def subir_solo(carpeta, ids):
    import subprocess
    subprocess.run(["gcloud", "storage", "cp", *[os.path.join(carpeta, "tecnicos", f"{i}.svg") for i in ids], "gs://com-icg-mundial/tecnicos/",
                    "--gzip-local-all", "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def subir(carpeta):
    import subprocess
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "tecnicos", "*.svg"), "gs://com-icg-mundial/tecnicos/",
                    "--gzip-local-all", "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def asignar():
    from pymongo import UpdateOne
    from services.imagenes_pais_service import db
    _, tecnicos = _datos()
    r = db["directores_tecnicos"].bulk_write([UpdateOne({"_id": t["_id"]}, {"$set": {"avatar_imagen": f"tecnicos/{t['id']}.svg"}})
                                              for t in tecnicos])
    print(f"Técnicos con avatar: {r.matched_count}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "avatares_generados"
    ids_solo = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else list(AJUSTES_TECNICO)
    {"--muestra": lambda: muestra(carpeta), "--generar": lambda: generar(carpeta), "--subir": lambda: subir(carpeta),
     "--asignar": asignar, "--solo": lambda: generar_solo(carpeta, ids_solo),
     "--subir-solo": lambda: subir_solo(carpeta, ids_solo)}.get(modo, lambda: print(__doc__))()
