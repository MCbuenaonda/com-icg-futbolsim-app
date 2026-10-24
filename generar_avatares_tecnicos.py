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

from generar_avatares import CONTORNO, ANCHO_TRAZO, CX, CANAS, Avatar, _elegir, _oscurecer, _region

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
    {"--muestra": lambda: muestra(carpeta), "--generar": lambda: generar(carpeta), "--subir": lambda: subir(carpeta),
     "--asignar": asignar}.get(modo, lambda: print(__doc__))()
