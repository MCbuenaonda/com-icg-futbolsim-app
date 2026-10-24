"""
Generador de avatares ilustrados (SVG plano, busto) para los 840 árbitros de la colección 'arbitros'.

Reusa el motor de generar_avatares.py (mismas piezas, mismo trazo, mismos rasgos por REGIÓN del país)
con tres diferencias:
  - Uniforme de árbitro: camiseta negra clásica, cuello polo y vivos blancos, insignia en el pecho
    (genérica, no reproduce el logo real de la FIFA).
  - Género: la colección no lo trae, se infiere del nombre. La lista de árbitras está en MUJERES
    (revisada a mano sobre los 840 nombres); --asignar lo guarda en 'arbitros.genero' ("F"/"M").
    Para corregir un caso: editar MUJERES y volver a correr --generar, --subir y --asignar.
  - País: 'arbitros.pais_id' venía de una base vieja; se resuelve por 'arbitros.pais' (+ ALIAS_PAIS) y
    --asignar lo corrige con el id real de 'paises' (nada más lo usaba).
  - Edad: la colección no la trae; sale de la semilla (28-46 años: más canas, entradas y barba).

'arbitros' no tiene id numérico: el archivo se nombra con el _id de Mongo ("arbitros/<_id>.svg") y la
semilla es crc32("nombre|pais"), así que siempre sale el mismo dibujo. Las vistas buscan al
árbitro por NOMBRE (los partidos solo guardan el nombre), ver services/imagenes_pais_service.py.

Uso (en este orden; cada paso es idempotente):
    python generar_avatares_arbitros.py --muestra [carpeta]   # árbitros/árbitras de varias regiones
    python generar_avatares_arbitros.py --muestra-var [carpeta]  # los 210 VAR de arbitros_var.json, sin tocar la base
    python generar_avatares_arbitros.py --generar [carpeta]   # todos los SVG (840 + 210 VAR) en <carpeta>/arbitros/
    python generar_avatares_arbitros.py --subir [carpeta]     # sube a gs://com-icg-mundial/arbitros/
    python generar_avatares_arbitros.py --asignar             # escribe arbitros.avatar_imagen, genero y pais_id
"""
import os
import random
import sys
import zlib

from generar_avatares import (CONTORNO, ANCHO_TRAZO, CX, CANAS, PELOS, Avatar, _elegir, _espejo, _oscurecer, _region, _suave)

CAMISETA = "#16181d"
CAMISETA_LUZ = "#2a2e37"
VIVOS = "#f4f4f4"

# Árbitras (por nombre, tal como está en 'arbitros.nombre')
MUJERES = {
    "Zahra Ahmadi", "Adelina Deda", "Bibiana Steinhaus", "Silvia Mora", "Esperança Cabral", "Shania Henry", "Nouf Al-Anzi",
    "Fatiha Bencheneb", "María Laura Fortunato", "Anahit Mkhitaryan", "Michelle de Kort", "Kate Jacewicz", "Sara Telek",
    "Aynur Rzayeva", "Khadijah Major", "Fatimah Al-Hayki", "Salma Islam", "Tia Sealy", "Lotte Cuypers", "Miriam Palma",
    "Mariam Ali", "Jahzara Thomas", "Volha Tsiareshka", "Adriana Farfán", "Aida Kadić", "Tebogo Mosete",
    "Edina Alves Batista", "Nurul Syahmina", "Yana Demireva", "Aïssata Bako", "Josiane Mukamana", "Dechen Wangmo",
    "Telma Correia", "Sok Theary", "Carine Atezambong", "Myriam Marcotte", "Amina Abakar", "María Belén Carvajal",
    "Qin Liang", "Christiana Kyriacou", "María Victoria Daza", "Faïza Maoulida", "Christelle Ngoundoulou", "Ri Kum-hwa",
    "Chung Hae-won", "Fatou Coulibaly", "Marianela Araya", "Vesna Budimir", "Milagros Segura", "Farieda Curiel",
    "Amber Degallerie", "Susana Corella", "Tori Penso", "Shaimaa Elsayed", "Ivonne Tovar", "Amal Al Junaibi",
    "Fiori Habtemariam", "Lorraine Watson", "Miroslava Ostatníková", "Petra Stipič", "Marta Huerta de Aza", "Anni Koppel",
    "Lidya Tafesse", "Kristel Ann Caricungan", "Lina Lehtovaara", "Priyanka Singh", "Stéphanie Frappart",
    "Brenda Ignoumba", "Fatou Bah", "Teona Sturua", "Theresa Bremansu", "Nicole Viagas", "Sabrina La Touche",
    "Chrysoula Kourompylia", "Elisha De Jesus", "Astrid Gramajo", "Fanta Koné", "Celestina Nchama", "Aissata Embaló",
    "Swanna Campbell", "Chantal Boulos", "Melissa Borjas", "Leung Yuen Ting", "Katalin Kulcsár", "Ranjita Devi",
    "Deliana Fatma", "Sian Massey-Ellis", "Tiba Al-Hussaini", "Mahsa Ghorbani", "Paula Brady", "Deborah, Wright",
    "Helga Einarsdóttir", "Kasey Bramwell", "Faylinn Maenu'u", "Jolene Nicholas", "Marva James", "Liat Vaknin",
    "Maria Sole Ferrieri Caputi", "Odette Hamilton", "Kenesha Reid", "Yoshimi Yamashita", "Esra'a Al-Mbaidin",
    "Elvira Nurmustafina", "Caroline Wanjala", "Zulfira Zakirova", "Besarta Lulaj", "Aisha Al-Dosari",
    "Phommasone Thong", "Puleng Motloi", "Montšeng Sekonyela", "Viola Raudzinš", "Doumouh Al Bakkar", "Hawa Kromah",
    "Khulood Al-Mabrouk", "Sarah Wenger", "Jelena Macevska", "Joelle Gies", "Irena Velevačkoska",
    "Doraline Rasoanandrasana", "Nurul Azurin", "Grace Nyandule", "Aishath Nasheeda", "Fanta Diarra", "Fatiha Jermoumi",
    "Queency Seevraz", "Hawa Al-Bakari", "Karen Díaz", "Natalia Ceban", "Munkhtogoo Erdenebat", "Jelena Kovačević",
    "Cloe Fenton", "Olívia César", "Edna Tembe", "Thida Oo", "Nangula Amutenya", "Nani Maharjan", "Srijana Khadka",
    "Tatiana Guzman", "Aichatou Garba", "Monica Løkkeberg", "Isabelle Wacalie", "Anna-Marie Keighley",
    "Zahra Al-Zadjali", "Shona Shukrula", "Hina Liaqat", "Heba Saadieh", "Mélida Pérez", "Jacqueline Akik",
    "Zulma Quiñónez", "Gabriela Chávez", "Monika Mularczyk", "Catarina Campos", "Mayra Alejo", "Hana Hattab",
    "Marie-Josée Malou", "Lucie Ratajová", "Lixy Encarcacion", "Salima Mukansanga", "Petruta Iugulescu",
    "Anastasia Pustovoytova", "Mereana Faaofo", "Faranisese Fuavai", "Chantel Perreira", "Francesca Benvenuti",
    "Jolene Skerritt", "Brenda William", "Vivian Robinson", "Elizabete Tomé", "Adja Ndiaye", "Ana Minić",
    "Dianne Alphonse", "Theresa Bangura", "Abirami Apbai", "Hanna Hattab", "Aya Hakam", "Khadija Ahmed",
    "Nokwanda Maziya", "Fatima Hassan", "Tess Olofsson", "Esther Staubli", "Astrid Darson", "Pansa Chaisanit",
    "Chen Hui-Wen", "Jonesia Rukyaa", "Gulnora Ergasheva", "Adelia Mendonça", "Crystal Sobers", "Dorsaf Ghorbal",
    "Kadine Delancy", "Melis Özçiğdem", "Kateryna Monzul", "Shamirah Nabadda", "Claudia Umpiérrez",
    "Edita Mirobidova", "Anna Tovo", "Bùi Thị Thu Trang", "Hibo Omar", "Diana Chikotesha", "Chipo Moyo",
}

# Peinados de árbitra por textura de pelo (los de árbitro usan los de generar_avatares, más sobrios)
PEINADOS_MUJER = {
    "lacio": {"coleta": 26, "rodete": 20, "melena": 16, "melena_corta": 14, "trenza": 12, "pixie": 8},
    "ondulado": {"coleta": 24, "rodete": 20, "melena": 18, "melena_corta": 12, "trenza": 12, "pixie": 6},
    "rizado": {"rodete": 24, "coleta": 18, "afro": 14, "trenza": 14, "melena_corta": 10, "pixie": 8, "rastas": 10},
    "muy_rizado": {"rodete": 24, "afro": 16, "trenzas": 14, "rastas": 12, "coleta": 14, "pixie": 10},
}
PEINADOS_LLAMATIVOS = ("cresta", "rastas", "trenzas", "melena", "largo_atado", "tupe")

# 'arbitros.pais_id' viene de una base vieja (no coincide con paises.id): el país se resuelve por NOMBRE.
# Nombres de 'arbitros.pais' que difieren de 'paises.nombre' (Bahréin no está en 'paises': queda sin país).
ALIAS_PAIS = {"Suazilandia": "Esuatini", "Taipei": "Taiwán", "Holanda": "Países Bajos", "Macedonia": "Macedonia del Norte",
              "Brunéi Darussalam": "Brunéi", "Guinea Bissáu": "Guinea-Bisáu", "Bangladesh": "Bangladés", "Qatar": "Catar",
              "Mali": "Malí", "EE UU": "Estados Unidos", "Kazajstán": "Kazajistán"}
REGION_SIN_PAIS = {"Bahréin": "africa_norte_medio_oriente"}


class AvatarArbitro(Avatar):
    def __init__(self, semilla, region, mujer):
        self.mujer = mujer
        edad = random.Random(semilla + 1).randint(28, 46)
        super().__init__(semilla, edad, region, (CAMISETA, VIVOS))
        r = self.rnd
        if mujer:
            self.barba = None
            self.entradas = False
            self.peinado = _elegir(r, PEINADOS_MUJER[self.textura])
            if self.pelo in CANAS and r.random() < 0.85:  # pocas árbitras canosas
                self.pelo = PELOS[_elegir(r, {"negro": 50, "castano_oscuro": 35, "castano": 15})]
        elif self.peinado in PEINADOS_LLAMATIVOS:
            self.peinado = _elegir(r, {"corto": 40, "degradado": 30, "rapado": 20, "calvo": 10})

    def _geometria(self):
        super()._geometria()
        if not self.mujer:
            return
        # cara un poco más angosta en la mandíbula y el mentón
        self.mandibula *= 0.9
        self.menton *= 0.85
        self.menton_y -= 6
        self.contorno_cara = _espejo([
            (CX, self.top), (CX + self.sien * 0.62, self.top + 10), (CX + self.sien, self.top + 58),
            (CX + self.mejilla, 245), (CX + self.mandibula, 312), (CX + self.menton, self.menton_y - 4),
            (CX + self.menton * 0.35, self.menton_y + 4),
        ])[:-1]

    # --- uniforme ------------------------------------------------------------------------------------
    def _camiseta(self):
        cuerpo = "M60 512C70 448 130 410 200 398L312 398C382 410 442 448 452 512Z"
        insignia = "M332 448L370 448L370 470C370 484 360 492 351 496C342 492 332 484 332 470Z"
        return (f'<clipPath id="cam"><path d="{cuerpo}"/></clipPath>'
                f'<path d="{cuerpo}" fill="{CAMISETA}"/>'
                # luz sobre el hombro izquierdo (como la sombra de la cara, luz desde la izquierda)
                f'<path d="M60 512C70 448 130 410 200 398L214 398C150 430 120 470 112 512Z" fill="{CAMISETA_LUZ}" clip-path="url(#cam)"/>'
                f'<path d="M150 418C120 440 96 470 86 512M362 418C392 440 416 470 426 512" fill="none" stroke="{VIVOS}" stroke-width="7"/>'
                # insignia en el pecho: escudo con borde dorado y una pelota
                f'<path d="{insignia}" fill="#1d3f8f" stroke="#e2b53e" stroke-width="3.5" stroke-linejoin="round"/>'
                f'<circle cx="351" cy="468" r="8" fill="#fff" stroke="#e2b53e" stroke-width="2"/>'
                f'<path d="M351 462l5 4-2 6h-6l-2-6Z" fill="#1d3f8f"/>'
                # cuello polo blanco
                f'<path d="M204 396L256 430L234 450Z M308 396L256 430L278 450Z" fill="{VIVOS}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>'
                f'<path d="M256 430L256 466" stroke="{VIVOS}" stroke-width="3" stroke-opacity="0.5"/>'
                f'<path d="{cuerpo}" fill="none" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>')

    # --- rasgos de árbitra ---------------------------------------------------------------------------
    def _ojos(self):
        base = super()._ojos()
        if not self.mujer:
            return base
        y = self.ojo_y
        pestanas = "".join(
            f'<path d="M{CX + s * 66} {y - 4}l{s * 8} -7M{CX + s * 60} {y - 10}l{s * 6} -9M{CX + s * 52} {y - 13}l{s * 3} -9" '
            f'stroke="{CONTORNO}" stroke-width="2.6" stroke-linecap="round"/>' for s in (-1, 1))
        return base + pestanas

    def _cejas(self):
        if not self.mujer:
            return super()._cejas()
        r = self.rnd
        grosor = r.uniform(4.5, 6.5)
        y = self.ojo_y - 32
        color = _oscurecer(self.pelo, 0.85)
        return "".join(
            f'<path d="M{CX + s * 24} {y + 8}Q{CX + s * 50} {y - 8} {CX + s * 72} {y + 4}'
            f'L{CX + s * 72} {y + 4 + grosor * 0.4:.1f}Q{CX + s * 50} {y - 8 + grosor:.1f} {CX + s * 24} {y + 8 + grosor:.1f}Z" fill="{color}"/>'
            for s in (-1, 1))

    def _boca(self):
        base = super()._boca()
        if not self.mujer:
            return base
        # un toque de color en el labio inferior
        y = self.ojo_y + 82 + (4 if self.forma == "alargada" else 0)
        labio = _oscurecer(self.piel, 0.62)
        return base + f'<path d="M{CX - 16} {y + 17}Q{CX} {y + 25} {CX + 16} {y + 17}" fill="none" stroke="{labio}" stroke-width="5" stroke-linecap="round" stroke-opacity="0.55"/>'

    def _pelo_detras(self):
        p, color = self.peinado, self.pelo
        trazo = f'stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}" stroke-linejoin="round"'
        s, t = self.sien, self.top
        if p == "coleta":
            # coleta alta que asoma por detrás y cae hacia el hombro derecho
            cola = [(CX + s * 0.5, t - 20), (CX + s + 34, t + 30), (CX + s + 44, t + 150), (CX + s + 24, t + 250),
                    (CX + s + 4, t + 170), (CX + s - 2, t + 60)]
            return f'<path d="{_suave(cola)}" fill="{color}" {trazo}/>'
        if p == "rodete":
            return f'<circle cx="{CX}" cy="{t - 36}" r="36" fill="{color}" {trazo}/>'
        if p == "trenza":
            eslabones = "".join(f'<ellipse cx="{CX - s - 18 + k * 3:.1f}" cy="{t + 120 + k * 34}" rx="17" ry="21" fill="{color}" {trazo}/>'
                                for k in range(6))
            return eslabones
        if p == "melena_corta":
            pts = [(CX - s - 20, t + 30), (CX - s - 26, t + 160), (CX - self.mejilla - 14, 318), (CX - 60, 326),
                   (CX + 60, 326), (CX + self.mejilla + 14, 318), (CX + s + 26, t + 160), (CX + s + 20, t + 30), (CX, t - 28)]
            return f'<path d="{_suave(pts)}" fill="{color}" {trazo}/>'
        return super()._pelo_detras()

    def _pelo(self):
        p, color = self.peinado, self.pelo
        brillo = _oscurecer(color, 1.35) if color != "#1c1714" else "#3a322c"
        trazo = f'stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}" stroke-linejoin="round"'
        t = self.top
        if p in ("coleta", "rodete", "trenza"):
            # pelo recogido: liso sobre la cabeza con raya al costado
            forma = self._casquete(18, t + 34)
            return (f'<path d="{_suave(forma)}" fill="{color}" {trazo}/>'
                    f'<path d="M{CX - 30} {t + 30}Q{CX - 26} {t} {CX - 18} {t - 14}" fill="none" stroke="{_oscurecer(color, 0.6)}" stroke-width="3" stroke-linecap="round"/>'
                    f'<path d="M{CX - 10} {t - 10}Q{CX + 40} {t - 16} {CX + 84} {t + 20}" fill="none" stroke="{brillo}" stroke-width="3" stroke-linecap="round"/>')
        if p == "melena_corta":
            forma = self._casquete(26, t + 40)
            mechon = [(CX - self.sien * 0.9, t + 70), (CX - self.sien * 0.6, t + 4), (CX + 10, t - 6), (CX + self.sien * 0.7, t + 20),
                      (CX + self.sien * 0.2, t + 30), (CX - self.sien * 0.4, t + 46)]
            return f'<path d="{_suave(forma)}" fill="{color}" {trazo}/>' + f'<path d="{_suave(mechon)}" fill="{color}" {trazo}/>'
        if p == "pixie":
            forma = self._casquete(22, t + 36)
            flequillo = [(CX - self.sien * 0.85, t + 60), (CX - self.sien * 0.7, t + 6), (CX, t - 14), (CX + self.sien * 0.75, t + 14),
                         (CX + self.sien * 0.5, t + 48), (CX - self.sien * 0.2, t + 40)]
            return (f'<path d="{_suave(forma)}" fill="{color}" {trazo}/>' + f'<path d="{_suave(flequillo)}" fill="{color}" {trazo}/>'
                    f'<path d="M{CX - 40} {t + 8}Q{CX + 10} {t - 6} {CX + 52} {t + 16}" fill="none" stroke="{brillo}" stroke-width="3" stroke-linecap="round"/>')
        return super()._pelo()


# --- Datos (Mongo) ------------------------------------------------------------------------------------
def _datos():
    from services.imagenes_pais_service import db

    paises = {p["nombre"]: p for p in db["paises"].find({}, {"id": 1, "nombre": 1, "confederacion_id": 1})}
    arbitros = list(db["arbitros"].find({}, {"nombre": 1, "pais": 1, "genero": 1, "origen": 1}).sort("_id", 1))
    return paises, arbitros


def _pais_de(a, paises):
    return paises.get(ALIAS_PAIS.get(a.get("pais"), a.get("pais")))


def _es_mujer(a):
    """Los 840 originales: por la lista MUJERES. Los VAR (agregar_arbitros_var.py) traen su género en el doc."""
    if a.get("origen") == "var_generado":
        return a.get("genero") == "F"
    return a["nombre"] in MUJERES


def _semilla(a):
    return zlib.crc32(f"{a['nombre']}|{a.get('pais')}".encode())


def _avatar_de(a, paises):
    pais = _pais_de(a, paises)
    region = _region(pais) if pais else REGION_SIN_PAIS.get(a.get("pais"), "diversa")
    return AvatarArbitro(_semilla(a), region, _es_mujer(a)).svg()


def muestra(carpeta):
    """Árbitros y árbitras de países de regiones distintas, para revisar el estilo."""
    os.makedirs(carpeta, exist_ok=True)
    elegidos = {"Alemania", "Francia", "Brasil", "Argentina", "Japón", "Corea del Sur", "Marruecos", "Senegal", "Ruanda",
                "Jamaica", "India", "Estados Unidos", "Irán", "Suiza", "Fiyi", "México"}
    paises, arbitros = _datos()
    for a in arbitros:
        if a.get("pais") in elegidos:
            with open(os.path.join(carpeta, f"{a['pais']}_{'F' if _es_mujer(a) else 'M'}_{a['nombre']}.svg"), "w") as f:
                f.write(_avatar_de(a, paises))
    print(f"Muestra en {carpeta}")


def muestra_var(carpeta):
    """Los 210 árbitros VAR de arbitros_var.json, antes de insertarlos (misma semilla que tendrán en la base)."""
    import json
    os.makedirs(carpeta, exist_ok=True)
    paises, _ = _datos()
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "arbitros_var.json"), encoding="utf-8") as f:
        filas = json.load(f)["arbitros"]
    for i, a in enumerate(filas):
        a = {**a, "origen": "var_generado"}
        with open(os.path.join(carpeta, f"{i:03d}.svg"), "w") as f:
            f.write(_avatar_de(a, paises))
    print(f"{len(filas)} SVG en {carpeta}")


def generar(carpeta):
    destino = os.path.join(carpeta, "arbitros")
    os.makedirs(destino, exist_ok=True)
    paises, arbitros = _datos()
    for a in arbitros:
        with open(os.path.join(destino, f"{a['_id']}.svg"), "w") as f:
            f.write(_avatar_de(a, paises))
    print(f"{len(arbitros)} SVG en {destino} ({sum(_es_mujer(a) for a in arbitros)} árbitras)")


def subir(carpeta):
    import subprocess
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "arbitros", "*.svg"), "gs://com-icg-mundial/arbitros/",
                    "--gzip-local-all", "--content-type=image/svg+xml", "--cache-control=public, max-age=604800", "-q"], check=True)


def asignar():
    """avatar_imagen + genero, y corrige pais_id (base vieja) con el id real del país resuelto por nombre."""
    from pymongo import UpdateOne
    from services.imagenes_pais_service import db
    paises, arbitros = _datos()
    ops = []
    for a in arbitros:
        pais = _pais_de(a, paises)
        ops.append(UpdateOne({"_id": a["_id"]}, {"$set": {"avatar_imagen": f"arbitros/{a['_id']}.svg",
                                                          "genero": "F" if _es_mujer(a) else "M",
                                                          "pais_id": pais["id"] if pais else None}}))
    r = db["arbitros"].bulk_write(ops)
    print(f"Árbitros actualizados: {r.modified_count} de {len(ops)}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "avatares_generados"
    {"--muestra": lambda: muestra(carpeta), "--muestra-var": lambda: muestra_var(carpeta), "--generar": lambda: generar(carpeta),
     "--subir": lambda: subir(carpeta), "--asignar": asignar}.get(modo, lambda: print(__doc__))()
