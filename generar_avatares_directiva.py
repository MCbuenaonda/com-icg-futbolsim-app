"""
Avatares ilustrados (SVG plano, busto, fondo transparente) de los 211 presidentes de federación y los 211 líderes de la afición
(colecciones 'presidentes' y 'lideres', generar_directiva.py).

  - PRESIDENTES: mismo motor que los dueños de televisión (AvatarTV, rol 'dueno'); el aspecto sale de su rasgo (`look` abajo), trajes y colores de su bandera.
  - LÍDERES: jóvenes (18-34) y MUY variados, según su `estilo`: sencillo (camiseta con los colores del país, peinado normal, a veces lentes), hincha de bufanda,
    urbano (sudadera), punk (chamarra de cuero, cresta, pelo de colores), extravagante (camisa llamativa, pelo teñido, lentes de sol) y cara pintada con los
    colores de su bandera. Pelo de colores, tatuajes (cuello y mejilla) y piercings (nariz, ceja, labio, orejas) según el estilo, todo determinístico (semilla = país).

Archivos: presidentes/<pais_id>.svg y aficionados/<pais_id>.svg.

    python generar_avatares_directiva.py --muestra [carpeta]    # 36 líderes y 12 presidentes + muestra.html para revisarlos
    python generar_avatares_directiva.py --generar [carpeta]    # todos en <carpeta>/presidentes/ y <carpeta>/aficionados/
    python generar_avatares_directiva.py --subir [carpeta]      # a gs://com-icg-mundial/
    python generar_avatares_directiva.py --asignar              # escribe `avatar` en 'presidentes' y 'lideres'
"""
import os
import random
import sys

from generar_avatares import ANCHO_TRAZO, CANAS, CONTORNO, CX, PEINADOS_POR_TEXTURA, PELOS, _elegir, _oscurecer, _region
from generar_avatares_tv import AvatarTV

LOOK_PRESIDENTE = {"institucional": "tradicional", "ambicioso": "tiburon", "austero": "ahorrador", "populista": "estrella", "reformista": "visionario"}
TINTES = ["#2dd4bf", "#3b82f6", "#ec4899", "#ef4444", "#a855f7", "#f59e0b", "#22c55e", "#e5e7eb", "#f472b6", "#38bdf8"]
SUDADERAS = ["#1f2937", "#475569", "#7c2d12", "#14532d", "#3b0764", "#111827"]
TINTA = "#1b2a3a"

PEINADOS_ESTILO = {
    "sencillo": ("corto", "raya", "degradado", "ondulado", "flequillo", "rulos", "rapado"), "hincha": ("corto", "raya", "degradado", "tupe", "rulos", "rapado", "ondulado"),
    "urbano": ("degradado", "rapado", "tupe", "trenzas", "rulos", "corto", "afro"), "punk": ("cresta", "rapado", "rastas", "afro", "trenzas", "melena", "tupe"),
    "extravagante": ("cresta", "afro", "rastas", "trenzas", "rulos", "tupe", "melena", "largo_atado"), "pintado": ("rapado", "cresta", "corto", "tupe", "degradado"),
}
# probabilidades por estilo: tinte del pelo, tatuaje de cuello, tatuaje de mejilla, piercing de nariz/ceja/labio, arete, aretes extra
PROB = {
    "sencillo": dict(tinte=0.04, cuello=0.03, mejilla=0.02, nariz=0.03, ceja=0.02, labio=0.01, arete=0.12, extra=0.02),
    "hincha": dict(tinte=0.08, cuello=0.04, mejilla=0.03, nariz=0.03, ceja=0.03, labio=0.02, arete=0.15, extra=0.03),
    "urbano": dict(tinte=0.25, cuello=0.20, mejilla=0.08, nariz=0.12, ceja=0.10, labio=0.06, arete=0.40, extra=0.15),
    "punk": dict(tinte=0.75, cuello=0.60, mejilla=0.30, nariz=0.50, ceja=0.50, labio=0.30, arete=0.90, extra=0.55),
    "extravagante": dict(tinte=0.90, cuello=0.35, mejilla=0.25, nariz=0.35, ceja=0.30, labio=0.20, arete=0.70, extra=0.35),
    "pintado": dict(tinte=0.55, cuello=0.12, mejilla=0.05, nariz=0.05, ceja=0.05, labio=0.03, arete=0.20, extra=0.05),
}
LENTES_ESTILO = {
    "sencillo": {None: 60, "fino": 14, "redondo": 14, "grueso": 4, "sol": 8}, "hincha": {None: 80, "sol": 10, "redondo": 10},
    "urbano": {None: 45, "sol": 35, "redondo": 20}, "punk": {None: 50, "sol": 40, "redondo": 10},
    "extravagante": {"sol": 45, "redondo": 30, None: 25}, "pintado": {None: 85, "sol": 15},
}


def _pesos(d):   # _elegir de generar_avatares admite claves None; esta variante también acepta cualquier clave
    return d


class AvatarAficionado(AvatarTV):
    """Líder de la afición: joven, de estilo muy variable (ver el docstring del módulo)."""

    def __init__(self, semilla, edad, region, colores, estilo):
        super().__init__(semilla, edad, region, colores, "dueno", None)
        r = random.Random(semilla * 53 + 11)
        self.estilo = estilo
        p = PROB[estilo]
        # pelo: natural (nunca canas) o teñido
        if self.pelo in CANAS:
            self.pelo = r.choice(list(PELOS.values()))
        self.teñido = r.random() < p["tinte"]
        if self.teñido:
            self.pelo = r.choice([self.c1, self.c2] + TINTES) if estilo in ("pintado", "hincha") else r.choice(TINTES)
        self.entradas = False
        pref = PEINADOS_ESTILO[estilo]
        tabla = {k: v for k, v in PEINADOS_POR_TEXTURA[self.textura].items() if k in pref}
        self.peinado = _elegir(r, tabla) if tabla else r.choice(pref)
        self.barba = _elegir(r, {"incipiente": 70, "candado": 30}) if r.random() < 0.16 else None
        self.boca = _elegir(r, {"seria": 40, "sonrisa": 40, "dientes": 20} if estilo == "punk" else {"dientes": 50, "sonrisa": 38, "seria": 12})
        opciones = LENTES_ESTILO[estilo]
        self.lentes = r.choices(list(opciones), weights=list(opciones.values()))[0]
        self.aspecto = {"punk": "rebelde", "extravagante": "relajado"}.get(estilo, "deportivo")
        self.arete = r.random() < p["arete"]
        self.aretes_extra = r.random() < p["extra"]
        self.p_nariz, self.p_ceja, self.p_labio = (r.random() < p[k] for k in ("nariz", "ceja", "labio"))
        self.t_cuello, self.t_mejilla = r.random() < p["cuello"], r.random() < p["mejilla"]
        self.lado = r.choice((-1, 1))
        self.sudadera = r.choice(SUDADERAS)
        self.rr = r

    # --- ropa --------------------------------------------------------------------------------------
    def _camiseta(self):
        e = self.estilo
        if e in ("punk", "extravagante"):
            return super()._camiseta()
        cuerpo = self._cuerpo()
        pre = f'<clipPath id="cam"><path d="{cuerpo}"/></clipPath>'
        if e == "urbano":
            col = self.sudadera
            return (pre + f'<path d="{cuerpo}" fill="{col}"/>'
                    + f'<path d="M60 512C70 448 130 410 200 398L214 398C150 430 120 470 112 512Z" fill="{_oscurecer(col, 1.4)}" clip-path="url(#cam)"/>'
                    + f'<path d="M206 398Q256 452 306 398Z" fill="{self.piel_sombra}"/>'
                    + f'<path d="M190 396Q256 470 322 396Q338 374 316 366L196 366Q172 374 190 396Z" fill="{_oscurecer(col, 0.8)}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                    + '<path d="M240 432L236 488M272 432L276 488" stroke="#e5e7eb" stroke-width="4" stroke-linecap="round"/>'
                    + f'<rect x="196" y="476" width="120" height="36" rx="10" fill="{_oscurecer(col, 0.9)}" opacity=".6"/>'
                    + self._contorno_ropa(cuerpo))
        col, ribete = self.c1, self.c2
        base = (pre + f'<path d="{cuerpo}" fill="{col}"/>'
                + f'<path d="M60 512C70 448 130 410 200 398L214 398C150 430 120 470 112 512Z" fill="{_oscurecer(col, 1.3)}" clip-path="url(#cam)"/>'
                + f'<path d="M150 440C120 462 104 486 98 512M362 440C392 462 408 486 414 512" fill="none" stroke="{ribete}" stroke-width="10"/>'
                + f'<path d="M206 398Q256 446 306 398Z" fill="{self.piel_sombra}"/>'
                + f'<path d="M204 398Q256 452 308 398" fill="none" stroke="{ribete}" stroke-width="13" stroke-linecap="round"/>')
        if e == "hincha":   # bufanda con los colores del país
            base += (f'<path d="M170 392Q256 446 342 392L348 420Q256 478 164 420Z" fill="{self.c1}" stroke="{CONTORNO}" stroke-width="3.5" stroke-linejoin="round"/>'
                     + ''.join(f'<path d="M{x} {y}Q256 {yc} {x2} {y}" fill="none" stroke="{self.c2}" stroke-width="9"/>' for x, x2, y, yc in ((176, 336, 402, 442), (170, 342, 414, 458)))
                     + f'<path d="M300 432L296 494M316 426L316 488" stroke="{self.c1}" stroke-width="12" stroke-linecap="round"/>'
                     + f'<path d="M296 484L296 504M316 478L316 500" stroke="{self.c2}" stroke-width="12" stroke-linecap="round"/>')
        return base + self._contorno_ropa(cuerpo)

    # --- tatuajes (sobre la piel: cuello y mejilla) -------------------------------------------------
    def _cuello(self):
        s = super()._cuello()
        if not self.t_cuello:
            return s
        x = CX + self.lado * 22
        enredadera = (f'<path d="M{x} 306q{self.lado * 14} 14 {self.lado * 2} 28q{-self.lado * 14} 12 {self.lado * 6} 30q{self.lado * 12} 10 {-self.lado * 2} 26" fill="none" stroke="{TINTA}" '
                      f'stroke-width="4.5" stroke-linecap="round" opacity=".8"/>'
                      f'<path d="M{x + self.lado * 10} 330l{self.lado * 8} -6M{x - self.lado * 4} 350l{-self.lado * 8} -6M{x + self.lado * 8} 368l{self.lado * 8} -4" stroke="{TINTA}" stroke-width="4" stroke-linecap="round" opacity=".8"/>')
        return s + enredadera

    def _accesorios(self):
        y = self.ojo_y
        partes = [super()._accesorios()]
        if self.estilo == "pintado":   # franjas con los colores de la bandera sobre las mejillas y la nariz
            ancho = self.mejilla + 14
            partes.append(f'<g clip-path="url(#cara)" opacity=".88"><rect x="{CX - ancho}" y="{y + 20}" width="{2 * ancho}" height="15" fill="{self.c1}"/>'
                          f'<rect x="{CX - ancho}" y="{y + 35}" width="{2 * ancho}" height="15" fill="{self.c2}"/></g>')
        if self.t_mejilla:
            x, yy = CX + self.lado * (self.mejilla - 30), y + 34
            estrella = "M0 -10L3 -3L10 -3L4 2L6 9L0 5L-6 9L-4 2L-10 -3L-3 -3Z"
            partes.append(f'<g transform="translate({x:.0f} {yy})" opacity=".85"><path d="{estrella}" fill="{TINTA}"/></g>')
        if self.p_nariz:
            partes.append(f'<circle cx="{CX + 17}" cy="{y + 52}" r="5.5" fill="none" stroke="#e5e7eb" stroke-width="2.6"/>')
        if self.p_ceja:
            s = self.lado
            partes.append(''.join(f'<circle cx="{CX + s * x}" cy="{yy}" r="3.4" fill="#e5e7eb" stroke="{CONTORNO}" stroke-width="1.6"/>' for x, yy in ((50, y - 40), (62, y - 31))))
        if self.p_labio:
            partes.append(f'<circle cx="{CX - 14}" cy="{y + 106}" r="3.6" fill="#e5e7eb" stroke="{CONTORNO}" stroke-width="1.6"/>')
        if self.aretes_extra:
            for s in (-1, 1):
                xo = CX + s * (self.mejilla - 6)
                partes.append(f'<circle cx="{xo + s * 6:.0f}" cy="226" r="4" fill="#e5e7eb" stroke="{CONTORNO}" stroke-width="1.8"/>')
        return "".join(partes)


def _colores(pais: dict) -> tuple:
    h = [c["hex"] for c in (pais.get("colores") or []) if c.get("hex")]
    h = (h + ["#1d4ed8", "#facc15"])[:2] if len(h) < 2 else h[:2]
    return h[0], h[1]


def _datos():
    from services.imagenes_pais_service import db
    paises = {p["id"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "confederacion_id": 1, "colores": 1})}
    return db, paises, list(db["presidentes"].find({}, {"_id": 0}).sort("id", 1)), list(db["lideres"].find({}, {"_id": 0}).sort("id", 1))


def presidente(x: dict, paises: dict) -> AvatarTV:
    p = paises[x["pais_id"]]
    return AvatarTV(200000 + x["id"], x["edad"], _region(p), _colores(p), "dueno", LOOK_PRESIDENTE[x["rasgo"]])


def lider(x: dict, paises: dict) -> AvatarAficionado:
    p = paises[x["pais_id"]]
    return AvatarAficionado(300000 + x["id"], x["edad"], _region(p), _colores(p), x["estilo"])


def muestra(carpeta):
    os.makedirs(carpeta, exist_ok=True)
    _, paises, pres, lid = _datos()
    celdas = []
    por_estilo = {}
    for x in lid:   # 6 de cada estilo
        if por_estilo.get(x["estilo"], 0) < 6:
            por_estilo[x["estilo"]] = por_estilo.get(x["estilo"], 0) + 1
            av = lider(x, paises)
            archivo = f"a{x['id']}.svg"
            open(os.path.join(carpeta, archivo), "w").write(av.svg())
            celdas.append(f'<figure><img src="{archivo}"><figcaption>{x["estilo_nombre"]} · {x["edad"]} · {x["pais_nombre"]}</figcaption></figure>')
    for x in pres[::18][:12]:
        av = presidente(x, paises)
        archivo = f"p{x['id']}.svg"
        open(os.path.join(carpeta, archivo), "w").write(av.svg())
        celdas.append(f'<figure><img src="{archivo}"><figcaption>Presidente · {x["rasgo_nombre"]} · {x["edad"]}</figcaption></figure>')
    open(os.path.join(carpeta, "muestra.html"), "w").write(
        '<meta charset="utf-8"><body style="background:#111c2e;color:#cbd5e1;font:12px sans-serif;display:grid;grid-template-columns:repeat(6,1fr);gap:8px;padding:8px">'
        + "".join(celdas).replace("<img", '<img style="width:100%;background:#1b2740;border-radius:10px"').replace("<figure>", '<figure style="margin:0">') + "</body>")
    print(f"{len(celdas)} SVG + muestra.html en {carpeta}")


def generar(carpeta):
    _, paises, pres, lid = _datos()
    for sub, filas, fn in (("presidentes", pres, presidente), ("aficionados", lid, lider)):
        destino = os.path.join(carpeta, sub)
        os.makedirs(destino, exist_ok=True)
        for x in filas:
            open(os.path.join(destino, f"{x['id']}.svg"), "w").write(fn(x, paises).svg())
        print(f"{len(filas)} SVG en {destino}")


def subir(carpeta):
    import subprocess
    for sub in ("presidentes", "aficionados"):
        subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, sub, "*.svg"), f"gs://com-icg-mundial/{sub}/", "--gzip-local-all",
                        "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def asignar():
    from pymongo import UpdateOne
    db, _, pres, lid = _datos()
    for col, sub, filas in (("presidentes", "presidentes", pres), ("lideres", "aficionados", lid)):
        r = db[col].bulk_write([UpdateOne({"id": x["id"]}, {"$set": {"avatar": f"{sub}/{x['id']}.svg"}}) for x in filas], ordered=False)
        print(f"{col}: avatar asignado a {r.modified_count}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "avatares_directiva_generados"
    {"--muestra": lambda: muestra(carpeta), "--generar": lambda: generar(carpeta), "--subir": lambda: subir(carpeta), "--asignar": asignar}.get(modo, lambda: print(__doc__))()
