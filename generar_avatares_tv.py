"""
Avatares ilustrados (SVG plano, busto, fondo transparente) del dueño y los dos comentaristas de cada televisora
(colección 'televisoras', campo 'equipo' de generar_equipo_tv.py).

Mismo motor que generar_avatares.py (piezas, trazo y rasgos por REGIÓN del país) con dos variaciones propias:
  - COMPLEXIÓN: delgado, normal, robusto o gordo (cara, cuello y hombros; el gordo con papada).
  - ASPECTO: ejecutivo, elegante, intelectual, rebelde, relajado, desaliñado, creativo o deportivo, cada uno con su ropa,
    accesorios, peinado y gesto. El dueño lo toma de su rasgo; los comentaristas llevan además auriculares con micrófono
    y la chamarra o los colores de su cadena.
Semilla = id de la cadena y rol (determinístico). Archivos: tv_equipo/<id>-d.svg (dueño), -c1.svg y -c2.svg (comentaristas).

    python generar_avatares_tv.py --muestra [carpeta]   # 24 personas variadas + muestra.html para revisarlas
    python generar_avatares_tv.py --generar [carpeta]   # todas en <carpeta>/tv_equipo/
    python generar_avatares_tv.py --subir [carpeta]     # a gs://com-icg-mundial/tv_equipo/
    python generar_avatares_tv.py --asignar             # escribe equipo.dueno.avatar y equipo.comentaristas[i].avatar
"""
import os
import random
import sys

from generar_avatares import ANCHO_TRAZO, CANAS, CONTORNO, CX, PEINADOS_POR_TEXTURA, Avatar, _elegir, _espejo, _oscurecer, _region
from generar_avatares_tecnicos import AvatarTecnico

COMPLEXION = {"delgado": 22, "normal": 44, "robusto": 20, "gordo": 14}
# (cara: mejilla, mandíbula, mentón) · ancho de hombros · ancho de cuello
MEDIDAS = {"delgado": ((0.90, 0.80, 0.78), 0.86, 0.82), "normal": ((1.0, 1.0, 1.0), 1.0, 1.0),
           "robusto": ((1.07, 1.14, 1.22), 1.14, 1.15), "gordo": ((1.17, 1.30, 1.50), 1.30, 1.35)}
ASPECTOS = ["ejecutivo", "elegante", "intelectual", "rebelde", "relajado", "desaliñado", "creativo", "deportivo"]
ASPECTO_DUENO = {   # rasgo del dueño -> aspectos probables
    "mecenas": {"elegante": 5, "relajado": 3, "creativo": 2}, "visionario": {"creativo": 5, "intelectual": 4, "rebelde": 1},
    "estrella": {"relajado": 4, "elegante": 3, "rebelde": 3}, "tiburon": {"ejecutivo": 6, "elegante": 3},
    "impaciente": {"ejecutivo": 4, "rebelde": 3, "desaliñado": 3}, "ahorrador": {"desaliñado": 4, "intelectual": 4, "ejecutivo": 2},
    "tradicional": {"elegante": 5, "ejecutivo": 4, "intelectual": 2}}
ASPECTO_COMENTARISTA = {"deportivo": 34, "relajado": 14, "intelectual": 12, "rebelde": 10, "desaliñado": 10, "elegante": 8, "creativo": 8, "ejecutivo": 4}
PELO_ASPECTO = {"rebelde": ("cresta", "melena", "rastas", "largo_atado", "degradado", "trenzas", "afro"),
                "desaliñado": ("ondulado", "largo_atado", "melena", "rulos", "flequillo", "afro"),
                "intelectual": ("raya", "corto", "ondulado", "rulos", "afro"), "ejecutivo": ("corto", "raya", "degradado", "rapado", "afro", "calvo"),
                "elegante": ("raya", "corto", "degradado", "ondulado", "calvo", "rulos"),
                "creativo": ("ondulado", "largo_atado", "tupe", "flequillo", "rulos", "melena", "afro"),
                "relajado": ("ondulado", "corto", "tupe", "rulos", "melena", "flequillo", "afro"),
                "deportivo": ("corto", "degradado", "rapado", "tupe", "rulos", "afro", "trenzas")}
MOSTAZA, VERDE_BOTELLA, TWEED = "#c58f2a", "#2f5a46", "#7a5b43"


def _claro(h):
    n = int(h[1:], 16)
    return (n >> 16) * 0.3 + ((n >> 8) & 255) * 0.59 + (n & 255) * 0.11 > 150


class AvatarTV(Avatar):
    def __init__(self, semilla, edad, region, colores, rol, rasgo=None):
        c1, c2 = colores
        super().__init__(semilla, edad, region, (c1, c2))
        self.c1, self.c2, self.rol = c1, c2, rol
        r = random.Random(semilla * 31 + 7)
        self.complexion = _elegir(r, COMPLEXION)
        if rol == "dueno":
            self.aspecto = _elegir(r, ASPECTO_DUENO.get(rasgo, {"ejecutivo": 1}))
        else:
            self.aspecto = _elegir(r, ASPECTO_COMENTARISTA)
        a = self.aspecto
        pref = PELO_ASPECTO[a]
        tabla = {k: v for k, v in PEINADOS_POR_TEXTURA[self.textura].items() if k in pref}
        self.peinado = _elegir(r, tabla or PEINADOS_POR_TEXTURA[self.textura])
        prob_canas = 0.05 if edad < 40 else 0.3 if edad < 52 else 0.6 if edad < 62 else 0.88
        if r.random() < prob_canas:
            self.pelo = r.choice(CANAS)
        self.entradas = r.random() < min(0.7, 0.1 + max(0, edad - 30) * 0.016)
        if edad >= 55 and a in ("ejecutivo", "elegante", "intelectual") and r.random() < 0.2:
            self.peinado = "calvo"
        self.barba = {"rebelde": _elegir(r, {"candado": 45, "completa": 35, "incipiente": 20}),
                      "desaliñado": "incipiente", "creativo": r.choice([None, "candado", "incipiente"]),
                      "intelectual": r.choice([None, None, "candado"]), "relajado": r.choice([None, "incipiente", "completa"]),
                      "elegante": r.choice([None, None, "candado"]), "ejecutivo": r.choice([None, None, None, "incipiente"]),
                      "deportivo": r.choice([None, None, "incipiente", "completa"])}[a]
        self.boca = {"rebelde": "seria", "intelectual": _elegir(r, {"seria": 55, "sonrisa": 45}), "relajado": "dientes",
                     "desaliñado": _elegir(r, {"seria": 50, "sonrisa": 50}), "ejecutivo": _elegir(r, {"seria": 60, "sonrisa": 40}),
                     "elegante": "sonrisa", "creativo": _elegir(r, {"sonrisa": 60, "dientes": 40}), "deportivo": _elegir(r, {"dientes": 55, "sonrisa": 45})}[a]
        self.lentes = {"intelectual": "grueso", "creativo": r.choice(["redondo", None]), "relajado": r.choice(["sol", None]),
                       "ejecutivo": r.choice([None, None, "fino"]), "elegante": r.choice([None, "fino"]), "desaliñado": r.choice([None, "grueso"]),
                       "deportivo": r.choice([None, None, None, "fino"]), "rebelde": r.choice([None, "sol"])}[a]
        self.arete = a == "rebelde" and r.random() < 0.7
        self.traje = r.choice(["#1f2a44", "#2b2f36", "#15171b", "#3a3f4a"]) if a == "ejecutivo" else r.choice(["#d8d2c4", "#b8bec9", "#3c3a35"])
        self._ajustar_complexion()

    # --- complexión ---------------------------------------------------------------------------------
    def _ajustar_complexion(self):
        (m, mand, men), self.f_hombros, self.f_cuello = MEDIDAS[self.complexion]
        self.mejilla *= m
        self.mandibula *= mand
        self.menton *= men
        self.contorno_cara = _espejo([
            (CX, self.top), (CX + self.sien * 0.62, self.top + 10), (CX + self.sien, self.top + 58),
            (CX + self.mejilla, 245), (CX + self.mandibula, 312), (CX + self.menton, self.menton_y - 4),
            (CX + self.menton * 0.35, self.menton_y + 4),
        ])[:-1]

    def _cuerpo(self):
        f = self.f_hombros
        x = lambda v: 256 + (v - 256) * f
        return f"M{x(60):.0f} 512C{x(70):.0f} 448 {x(130):.0f} 410 200 398L312 398C{x(382):.0f} 410 {x(442):.0f} 448 {x(452):.0f} 512Z"

    def _cuello(self):
        w = self.f_cuello
        papada = ""
        if self.complexion == "gordo":
            papada = (f'<path d="M{CX - self.menton * 1.05:.0f} {self.menton_y - 6}Q{CX} {self.menton_y + 34} {CX + self.menton * 1.05:.0f} {self.menton_y - 6}" '
                      f'fill="{self.piel}" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>')
        return (f'<path d="M{CX - 46 * w:.0f} 300L{CX + 46 * w:.0f} 300L{CX + 54 * w:.0f} 410C{CX + 20} 428 {CX - 20} 428 {CX - 54 * w:.0f} 410Z" fill="{self.piel}" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>'
                f'<path d="M{CX - 50 * w:.0f} 340C{CX - 20} 372 {CX + 20} 372 {CX + 52 * w:.0f} 340L{CX + 50 * w:.0f} 300L{CX - 46 * w:.0f} 300Z" fill="{self.piel_sombra}"/>') + papada

    # --- ropa ----------------------------------------------------------------------------------------
    def _contorno_ropa(self, cuerpo):
        return f'<path d="{cuerpo}" fill="none" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>'

    def _camiseta(self):
        cuerpo = self._cuerpo()
        luz = lambda c: f'<path d="M60 512C70 448 130 410 200 398L214 398C150 430 120 470 112 512Z" fill="{_oscurecer(c, 1.3)}" clip-path="url(#cam)"/>'
        pre = f'<clipPath id="cam"><path d="{cuerpo}"/></clipPath>'
        a = self.aspecto
        solapa = lambda c: (f'<path d="M200 398L232 432L256 512L222 470L204 444L178 438Z" fill="{_oscurecer(c, 0.8)}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                            f'<path d="M312 398L280 432L256 512L290 470L308 444L334 438Z" fill="{_oscurecer(c, 0.8)}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>')
        camisa_v = lambda c: f'<path d="M204 398L256 512L308 398Z" fill="{c}"/>'
        cuello_camisa = lambda c: (f'<path d="M204 396L246 408L232 430Z M308 396L266 408L280 430Z" fill="{c}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>')
        if a in ("ejecutivo", "elegante"):
            saco = self.traje
            corbata = self.c1 if a == "ejecutivo" else self.c2
            extra = ""
            if a == "elegante":
                extra = f'<path d="M348 462L384 458L382 468L350 472Z" fill="{_oscurecer(saco, 1.2)}"/><path d="M354 462L362 448L370 456L378 446L380 460Z" fill="{self.c1}" stroke="{CONTORNO}" stroke-width="2.5" stroke-linejoin="round"/>'
            return (pre + f'<path d="{cuerpo}" fill="{saco}"/>' + luz(saco) + camisa_v("#f5f6f8")
                    + f'<path d="M244 404L268 404L263 426L249 426Z" fill="{corbata}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                    + f'<path d="M249 426L263 426L276 494L256 512L236 494Z" fill="{corbata}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                    + cuello_camisa("#f5f6f8") + solapa(saco) + extra + self._contorno_ropa(cuerpo))
        if a == "intelectual":
            saco = TWEED
            return (pre + f'<path d="{cuerpo}" fill="{saco}"/>' + luz(saco)
                    + f'<path d="M204 398L256 480L308 398Z" fill="#e9e4d8"/>'
                    + f'<path d="M232 410L256 424L280 410L280 438L256 424L232 438Z" fill="{self.c1}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/><circle cx="256" cy="424" r="7" fill="{_oscurecer(self.c1, 0.75)}" stroke="{CONTORNO}" stroke-width="2.5"/>'
                    + cuello_camisa("#e9e4d8") + solapa(saco)
                    + ''.join(f'<circle cx="{256 + dx}" cy="{y}" r="3.2" fill="{_oscurecer(saco, 0.6)}"/>' for dx, y in ((-6, 470), (6, 492))) + self._contorno_ropa(cuerpo))
        if a == "rebelde":
            cuero = "#1b1b1f"
            return (pre + f'<path d="{cuerpo}" fill="{cuero}"/>' + luz("#3a3a42")
                    + f'<path d="M214 398L256 512L298 398Z" fill="{self.c1}"/><path d="M230 440L282 440" stroke="{self.c2}" stroke-width="9" opacity=".85"/>'
                    + f'<path d="M200 398L206 440L248 512L226 440Z" fill="#2a2a31" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                    + f'<path d="M312 398L306 440L264 512L286 440Z" fill="#2a2a31" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                    + f'<path d="M256 470L256 512" stroke="#9aa0a6" stroke-width="4"/>' + self._contorno_ropa(cuerpo))
        if a == "relajado":
            base = "#f3e9d2" if not _claro(self.c1) else _oscurecer(self.c1, 0.55)
            flores = ''.join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{col}" opacity=".9"/>' for x, y, r, col in
                             ((120, 470, 11, self.c1), (170, 440, 8, self.c2), (360, 460, 12, self.c2), (330, 430, 8, self.c1), (400, 500, 10, self.c1),
                              (100, 505, 8, self.c2), (230, 490, 9, self.c2), (300, 500, 10, self.c1), (150, 500, 7, "#ffffff")))
            return (pre + f'<path d="{cuerpo}" fill="{base}"/>' + flores
                    + f'<path d="M200 398L218 460L256 420L294 460L312 398Z" fill="{self.piel_sombra}"/>'
                    + f'<path d="M200 398L240 410L222 462L196 420Z M312 398L272 410L290 462L316 420Z" fill="{base}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                    + self._contorno_ropa(cuerpo))
        if a == "desaliñado":
            camisa = r"#b9b6a8"
            arrugas = ''.join(f'<path d="{d}" stroke="{_oscurecer(camisa, 0.7)}" stroke-width="3" fill="none"/>' for d in
                              ("M110 470L150 486", "M360 480L400 462", "M180 500L220 490", "M300 502L340 494", "M130 440L160 452"))
            return (pre + f'<path d="{cuerpo}" fill="{camisa}"/>' + arrugas
                    + f'<path d="M200 398L220 420L206 440Z M312 398L292 424L312 446Z" fill="{_oscurecer(camisa, 1.1)}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                    + f'<path d="M236 420L276 430L270 460L262 512L240 512L248 470Z" fill="{self.c1}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                    + f'<path d="M226 410L252 424L286 414L278 404L248 408Z" fill="{_oscurecer(self.c1, 0.8)}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                    + self._contorno_ropa(cuerpo))
        if a == "creativo":
            sueter = MOSTAZA if self.rnd.random() < 0.5 else VERDE_BOTELLA
            return (pre + f'<path d="{cuerpo}" fill="{sueter}"/>' + luz(sueter)
                    + f'<path d="M{CX - 62 * self.f_cuello:.0f} 372C{CX - 40} 420 {CX + 40} 420 {CX + 62 * self.f_cuello:.0f} 372L{CX + 62 * self.f_cuello:.0f} 398C{CX + 30} 424 {CX - 30} 424 {CX - 62 * self.f_cuello:.0f} 398Z" fill="{_oscurecer(sueter, 0.85)}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                    + ''.join(f'<path d="M{CX - 56 * self.f_cuello:.0f} {y}Q{CX} {y + 18} {CX + 56 * self.f_cuello:.0f} {y}" stroke="{_oscurecer(sueter, 0.7)}" stroke-width="2.5" fill="none"/>' for y in (384, 396))
                    + self._contorno_ropa(cuerpo))
        # deportivo: chamarra de la cadena
        chamarra = self.c1
        return (pre + f'<path d="{cuerpo}" fill="{chamarra}"/>' + luz(chamarra)
                + f'<path d="M150 418C120 440 96 470 86 512M362 418C392 440 416 470 426 512" fill="none" stroke="{self.c2}" stroke-width="12"/>'
                + f'<path d="M204 398L256 440L308 398L308 380L204 380Z" fill="{_oscurecer(chamarra, 0.8)}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                + f'<path d="M256 440L256 512" stroke="{self.c2}" stroke-width="5"/>'
                + f'<circle cx="326" cy="456" r="15" fill="{self.c2}" stroke="{CONTORNO}" stroke-width="3"/>' + self._contorno_ropa(cuerpo))

    # --- accesorios ----------------------------------------------------------------------------------
    def _accesorios(self):
        y = self.ojo_y
        partes = []
        if self.lentes == "grueso":
            partes.append("".join(f'<rect x="{CX + s * 46 - 31}" y="{y - 21}" width="62" height="42" rx="10" fill="#fff" fill-opacity="0.1" stroke="#1d1a17" stroke-width="7"/>' for s in (-1, 1))
                          + f'<path d="M{CX - 15} {y - 6}Q{CX} {y - 12} {CX + 15} {y - 6}" fill="none" stroke="#1d1a17" stroke-width="6"/>')
        elif self.lentes == "redondo":
            partes.append("".join(f'<circle cx="{CX + s * 46}" cy="{y}" r="27" fill="#fff" fill-opacity="0.1" stroke="#b08d3c" stroke-width="4.5"/>' for s in (-1, 1))
                          + f'<path d="M{CX - 19} {y - 4}Q{CX} {y - 12} {CX + 19} {y - 4}" fill="none" stroke="#b08d3c" stroke-width="4"/>')
        elif self.lentes == "fino":
            partes.append("".join(f'<rect x="{CX + s * 46 - 30}" y="{y - 19}" width="60" height="38" rx="14" fill="#fff" fill-opacity="0.1" stroke="#6b6b6b" stroke-width="3.5"/>' for s in (-1, 1))
                          + f'<path d="M{CX - 16} {y - 6}Q{CX} {y - 12} {CX + 16} {y - 6}" fill="none" stroke="#6b6b6b" stroke-width="3.5"/>')
        elif self.lentes == "sol":
            partes.append("".join(f'<path d="M{CX + s * 46 - 33} {y - 20}H{CX + s * 46 + 33}L{CX + s * 46 + 27} {y + 24}Q{CX + s * 46} {y + 30} {CX + s * 46 - 27} {y + 24}Z" fill="#14161a" stroke="#14161a" stroke-width="4" stroke-linejoin="round"/>'
                                  f'<path d="M{CX + s * 46 - 22} {y - 12}L{CX + s * 46 - 6} {y - 12}" stroke="#fff" stroke-opacity=".5" stroke-width="3"/>' for s in (-1, 1))
                          + f'<path d="M{CX - 13} {y - 8}Q{CX} {y - 14} {CX + 13} {y - 8}" fill="none" stroke="#14161a" stroke-width="5"/>')
        if self.aspecto == "desaliñado":   # ojeras
            col = _oscurecer(self.piel, 0.7)
            partes.append("".join(f'<path d="M{CX + s * 22} {y + 30}Q{CX + s * 46} {y + 42} {CX + s * 70} {y + 30}" fill="none" stroke="{col}" stroke-width="4" stroke-opacity=".7"/>' for s in (-1, 1)))
        if self.arete:
            x = CX - (self.mejilla - 6) - 4
            partes.append(f'<circle cx="{x:.0f}" cy="268" r="6" fill="#d9d9d9" stroke="{CONTORNO}" stroke-width="2.5"/>')
        return "".join(partes)

    def _desorden(self):
        """Mechones sueltos del desaliñado y del rebelde."""
        if self.aspecto not in ("desaliñado", "rebelde") or self.peinado == "calvo":
            return ""
        r = random.Random(self.top + int(self.sien))
        mech = "".join(f'<path d="M{CX + dx} {self.top - 4}q{r.randint(-14, 14)} {-r.randint(14, 26)} {r.randint(-20, 20)} {-r.randint(24, 40)}" stroke="{self.pelo}" stroke-width="6" fill="none" stroke-linecap="round"/>'
                       for dx in (-50, -22, 8, 36, 62))
        return mech

    def _auriculares(self):
        if self.rol != "comentarista":
            return ""
        x = self.mejilla + 8
        return (f'<path d="M{CX - x:.0f} 228Q{CX} {2 * (self.top - 6) - 228} {CX + x:.0f} 228" fill="none" stroke="#1e2430" stroke-width="9"/>'
                f'<rect x="{CX - x - 15:.0f}" y="216" width="26" height="46" rx="11" fill="#2b3342" stroke="{CONTORNO}" stroke-width="3"/>'
                f'<rect x="{CX + x - 11:.0f}" y="216" width="26" height="46" rx="11" fill="#2b3342" stroke="{CONTORNO}" stroke-width="3"/>'
                f'<path d="M{CX - x - 6:.0f} 262Q{CX - x - 4:.0f} 318 {CX - 36} {self.ojo_y + 84}" fill="none" stroke="#1e2430" stroke-width="5"/>'
                f'<circle cx="{CX - 34}" cy="{self.ojo_y + 85}" r="9" fill="#14161a" stroke="{CONTORNO}" stroke-width="2.5"/>')

    def svg(self):
        cuerpo = (self._pelo_detras() + self._cuello() + self._camiseta() + self._orejas() + self._cara()
                  + AvatarTecnico._arrugas(self) + self._barba() + self._ojos() + self._cejas() + self._accesorios()
                  + self._nariz() + self._boca() + self._pelo() + self._desorden() + self._auriculares())
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" '
                f'stroke-linecap="round">{cuerpo}</svg>')


# --- Datos (Mongo) ------------------------------------------------------------------------------------
def _datos():
    from services.imagenes_pais_service import db
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "confederacion_id": 1})}
    return paises, list(db["televisoras"].find({"equipo": {"$exists": True}}, {"id": 1, "nombre": 1, "pais_id": 1, "colores": 1, "equipo": 1}).sort("id", 1))


def personas(t):
    """[(archivo, rol, edad, rasgo, semilla)] del equipo de una cadena."""
    eq = t["equipo"]
    base = t["id"] * 10
    filas = [(f"{t['id']}-d.svg", "dueno", eq["dueno"]["edad"], eq["dueno"]["rasgo"], base + 1)]
    for i, c in enumerate(eq["comentaristas"], 1):
        filas.append((f"{t['id']}-c{i}.svg", "comentarista", c["edad"], None, base + 1 + i))
    return filas


def dibujar(t, paises, rol, edad, rasgo, semilla):
    colores = (t["colores"][0], t["colores"][1])
    return AvatarTV(semilla, edad, _region(paises[t["pais_id"]]), colores, rol, rasgo).svg()


def _todas():
    paises, cadenas = _datos()
    for t in cadenas:
        for archivo, rol, edad, rasgo, semilla in personas(t):
            yield t, paises, archivo, rol, edad, rasgo, semilla


def muestra(carpeta):
    os.makedirs(carpeta, exist_ok=True)
    todas = list(_todas())
    cupo, elegidas = {}, []   # 6 de cada complexión, de regiones y aspectos distintos
    for fila in todas[:: 7]:
        t, paises, archivo, rol, edad, rasgo, semilla = fila
        c = AvatarTV(semilla, edad, _region(paises[t["pais_id"]]), tuple(t["colores"][:2]), rol, rasgo).complexion
        if cupo.get(c, 0) < 6:
            cupo[c] = cupo.get(c, 0) + 1
            elegidas.append(fila)
    celdas = []
    for t, paises, archivo, rol, edad, rasgo, semilla in elegidas:
        svg = dibujar(t, paises, rol, edad, rasgo, semilla)
        with open(os.path.join(carpeta, archivo), "w") as f:
            f.write(svg)
        av = AvatarTV(semilla, edad, _region(paises[t["pais_id"]]), tuple(t["colores"][:2]), rol, rasgo)
        celdas.append(f'<figure><img src="{archivo}"><figcaption>{rol} · {av.aspecto} · {av.complexion} · {edad} · {t["nombre"]}</figcaption></figure>')
    with open(os.path.join(carpeta, "muestra.html"), "w") as f:
        f.write('<meta charset="utf-8"><body style="background:#111c2e;color:#cbd5e1;font:12px sans-serif;display:grid;grid-template-columns:repeat(6,1fr);gap:8px;padding:8px">'
                + "".join(celdas).replace("<img", '<img style="width:100%;background:#1b2740;border-radius:10px"').replace("<figure>", '<figure style="margin:0">') + "</body>")
    print(f"{len(elegidas)} SVG + muestra.html en {carpeta}")


def generar(carpeta):
    destino = os.path.join(carpeta, "tv_equipo")
    os.makedirs(destino, exist_ok=True)
    n = 0
    for t, paises, archivo, rol, edad, rasgo, semilla in _todas():
        with open(os.path.join(destino, archivo), "w") as f:
            f.write(dibujar(t, paises, rol, edad, rasgo, semilla))
        n += 1
    print(f"{n} SVG en {destino}")


def subir(carpeta):
    import subprocess
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "tv_equipo", "*.svg"), "gs://com-icg-mundial/tv_equipo/",
                    "--gzip-local-all", "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def asignar():
    from pymongo import UpdateOne
    from services.imagenes_pais_service import db
    _, cadenas = _datos()
    ops = []
    for t in cadenas:
        cambios = {"equipo.dueno.avatar": f"tv_equipo/{t['id']}-d.svg"}
        for i in (1, 2):
            cambios[f"equipo.comentaristas.{i - 1}.avatar"] = f"tv_equipo/{t['id']}-c{i}.svg"
        ops.append(UpdateOne({"id": t["id"]}, {"$set": cambios}))
    r = db["televisoras"].bulk_write(ops, ordered=False)
    print(f"Cadenas con avatares asignados: {r.modified_count}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "avatares_tv_generados"
    {"--muestra": lambda: muestra(carpeta), "--generar": lambda: generar(carpeta), "--subir": lambda: subir(carpeta),
     "--asignar": asignar}.get(modo, lambda: print(__doc__))()
