"""
Catálogo de televisoras ficticias (config/televisoras.py): 3 por país (633). Arma el nombre de cada una con la costumbre
de su idioma, diseña su logo (logos/television.py), lo valida y carga la colección `televisoras`.

Uso (logos: requiere `pip install fonttools brotli`):
    python generar_televisoras.py --muestra [carpeta]   # SVGs + hoja HTML de revisión por confederación (solo lee paises)
    python generar_televisoras.py --subir [carpeta]     # sube televisoras/<slug>.svg al bucket
    python generar_televisoras.py --aplicar             # carga/actualiza la colección `televisoras` (upsert por id)
    python generar_televisoras.py --revertir            # borra la colección `televisoras`

Determinístico (semilla fija). Reglas:
  - nombres únicos en todo el catálogo y ninguno igual o parecido a una cadena real (LISTA_NEGRA); si una combinación
    choca, se prueba otro patrón u otra raíz;
  - las 3 cadenas de un país no repiten arquetipo, paleta ni la primera palabra del nombre;
  - en todo el catálogo no se repite (arquetipo, fuente, paleta);
  - cada nombre se dibuja solo con una tipografía que tenga TODAS sus letras (ð, ł, ő, ș, ə…).
id = pais_id * 10 + 1..3 (1 cadena nacional, 2 regional, 3 deportiva). Al subir logos nuevos, subir
VERSION_IMAGENES['televisora'] en services/imagenes_pais_service.py.
"""
import difflib
import os
import random
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict

from config import televisoras as T

CARPETA_BUCKET = "gs://com-icg-mundial/televisoras"
SEMILLA = 2027
PESO_FUENTE = {"playfair": 800, "montserrat": 800, "oswald": 700, "rubik": 700, "teko": 600, "exo_italica": 800,
               "comfortaa": 700, "cinzel": 700}
SOLO_MAYUS = {"cinzel", "bebas", "anton", "bungee", "michroma", "stencil", "blackops"}
SIMBOLOS_TV = ["senal", "orbita", "lente", "boton_play", "sol_rayos", "estrella_cinetica", "pulso", "ondas_triples",
               "anillos", "rayo"]
CONFEDERACIONES = {2: "CONMEBOL", 3: "CONCACAF", 1: "UEFA", 4: "CAF", 6: "AFC", 5: "OFC"}


def slug(nombre: str) -> str:
    t = unicodedata.normalize("NFKD", nombre.replace("&", " y ").replace("+", " plus ")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _plano(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower())


_NEGRA = [_plano(n) for n in T.LISTA_NEGRA if len(_plano(n)) >= 2]
_GENERICAS = {_plano(g) for g in T.GENERICAS}


def parecido_a_real(nombre: str):
    """La cadena real a la que se parece el nombre (o None)."""
    candidatos = {_plano(nombre)} | {_plano(p) for p in re.split(r"[\s\-]+", nombre)
                                      if len(_plano(p)) >= 3 and _plano(p) not in _GENERICAS}
    for c in candidatos:
        for real in _NEGRA:
            if c == real or (len(real) >= 4 and len(c) >= 4 and difflib.SequenceMatcher(None, c, real).ratio() >= 0.84):
                return real
    return None


def _paises():
    import certifi
    from pymongo import MongoClient
    from config.settings import MONGODB_URI
    db = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())["mundial"]
    return list(db["paises"].find({}, {"_id": 0, "id": 1, "nombre": 1, "iso": 1, "confederacion_id": 1, "colores": 1}).sort("id"))


MAX_FUSION = 9   # una raíz más larga no se pega a otra palabra («Sternschnuppefunk»)


def _sin_acentos(t: str) -> str:
    return unicodedata.normalize("NFC", "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn"))


def _armar(patron: str, raiz: str, numero: int):
    """Nombre desde el patrón; None si el patrón pega la raíz a otra palabra y no conviene (larga o compuesta)."""
    pegado = bool(re.search(r"\w\{[Rr]\}|\{[Rr]\}\w", patron))
    if pegado:
        if len(raiz) > MAX_FUSION or " " in raiz or "-" in raiz or "'" in raiz:
            return None
        raiz_f = _sin_acentos(raiz)          # Halcón + visión -> Halconvisión
        minus = raiz_f[0].lower() + raiz_f[1:]
        texto = patron.format(R=raiz_f, r=minus, N=numero)
        texto = re.sub(r"(Tele|Télé)([eé])", lambda m: m.group(1) + ("" if m.group(1) == "Tele" else ""), texto) \
            if re.search(r"(Tele|Télé)[eé]", texto) else texto     # Teleesmeralda -> Telesmeralda
    else:
        texto = patron.format(R=raiz, r=raiz[0].lower() + raiz[1:], N=numero)
    return re.sub(r"\s+", " ", texto).strip()


def _paleta_pais(p):
    """(principal, acento) desde los colores reales de la bandera; None si no da para un logo."""
    from logos.color import contraste
    lista = [c["hex"] if isinstance(c, dict) else c for c in sorted(p.get("colores") or [], key=lambda c: -(c.get("area", 0) if isinstance(c, dict) else 0))]
    lista = [c for c in lista if isinstance(c, str) and re.match(r"^#[0-9a-fA-F]{6}$", c)]
    for a in lista:
        for b in lista:
            if a != b and contraste(a, b) >= 1.8:
                return (a.lower(), b.lower())
    return None


def _soporta(nombre_fuente: str, texto: str) -> bool:
    from logos.texto import fuente
    f = fuente(nombre_fuente, PESO_FUENTE.get(nombre_fuente, 800))
    return all(ch == " " or ord(ch) in f.cmap for ch in texto)


def disenar(paises=None):
    """Lista de televisoras con nombre, datos de catálogo y diseño de logo (determinístico)."""
    from logos.television import TODOS
    paises = paises or _paises()
    rng = random.Random(SEMILLA)
    pools = {g: rng.sample(lista, len(lista)) for g, lista in T.RAICES.items()}   # raíces de grupo, sin repetir
    usados_nombre, usados_combo = set(), set()
    uso_arq, uso_paleta, uso_fuente = Counter(), Counter(), Counter()
    salida, problemas = [], []
    for p in paises:
        iso = (p.get("iso") or "").upper()
        grupo = T.GRUPO_POR_ISO.get(iso)
        if not grupo:
            problemas.append(f"sin grupo de idioma: {p['nombre']} ({iso})")
            continue
        patrones = T.PATRONES_PAIS.get(iso) or T.PATRONES[T.PATRONES_GRUPO.get(grupo, grupo)]
        propias = list(T.RAICES_PAIS.get(str(p["id"])) or T.RAICES_PAIS.get(iso) or [])
        numeros = rng.sample(range(2, 14), 3)
        primeras, raices_pais = set(), set()
        arqs_pais, paletas_pais = set(), set()
        paleta_bandera = _paleta_pais(p)
        perfiles = rng.sample(list(T.PERFILES), 3)
        for k, papel in enumerate(T.PAPELES):
            # --- nombre ---
            nombre = None
            opciones = patrones[papel][:]
            rng.shuffle(opciones)
            fuentes_raiz = propias if propias else pools.get(grupo, [])
            for intento in range(200):
                raiz_lista = [r for r in fuentes_raiz if r not in raices_pais] or fuentes_raiz
                if not raiz_lista:
                    break
                raiz = raiz_lista[intento % len(raiz_lista)] if propias else raiz_lista[0]
                patron = opciones[intento % len(opciones)]
                cand = _armar(patron, raiz, numeros[k])
                if not cand:
                    continue
                primera = _plano(cand.split()[0])
                if (_plano(cand) in usados_nombre or primera in primeras or parecido_a_real(cand)):
                    if not propias and intento % len(opciones) == len(opciones) - 1:
                        pools[grupo].append(pools[grupo].pop(0))   # esa raíz no sirve: al final de la fila
                    continue
                nombre = cand
                break
            if not nombre:
                problemas.append(f"sin nombre válido: {p['nombre']} / {papel}")
                continue
            if not propias and raiz in pools.get(grupo, []):
                pools[grupo].remove(raiz)
            raices_pais.add(raiz)
            primeras.add(_plano(nombre.split()[0]))
            usados_nombre.add(_plano(nombre))
            # --- diseño ---
            arq = min((a for a in TODOS if a not in arqs_pais), key=lambda a: (uso_arq[a], rng.random()))
            if papel == "generalista" and paleta_bandera and paleta_bandera not in paletas_pais:
                paleta = paleta_bandera
            else:
                paleta = min((tuple(x) for x in T.PALETAS if tuple(x) not in paletas_pais),
                             key=lambda x: (uso_paleta[x], rng.random()))
            caso_base = rng.choice(["mayus", "titulo", "titulo", "minus"])
            fuentes = sorted(T.FUENTES_PAPEL[papel], key=lambda f: (uso_fuente[f], rng.random()))
            fte = None
            for f in fuentes:
                caso = "mayus" if f in SOLO_MAYUS else ("titulo" if f == "pacifico" else caso_base)
                texto = nombre.upper() if caso == "mayus" else nombre.lower() if caso == "minus" else nombre
                if (arq, f, paleta) not in usados_combo and _soporta(f, texto + "0123456789"):
                    fte = f
                    break
            if not fte:   # ninguna del papel tiene esas letras: la más completa del catálogo
                for f in ("montserrat", "rubik", "oswald", "playfair", "kanit"):
                    if _soporta(f, nombre + nombre.upper()):
                        fte, caso = f, "titulo"
                        break
            if not fte:
                problemas.append(f"sin tipografía para {nombre!r}")
                fte, caso = "montserrat", "titulo"
            arqs_pais.add(arq)
            paletas_pais.add(paleta)
            usados_combo.add((arq, fte, paleta))
            uso_arq[arq] += 1
            uso_paleta[paleta] += 1
            uso_fuente[fte] += 1
            perfil = perfiles[k]
            salida.append({
                "id": p["id"] * 10 + k + 1, "pais_id": p["id"], "pais": p["nombre"], "confederacion_id": p.get("confederacion_id"),
                "nombre": nombre, "slug": slug(nombre), "papel": papel, "nivel": T.NIVEL_POR_PAPEL[papel], "perfil": perfil,
                "exigencia": round({"generosa": 0.55, "resultadista": 0.6, "fiel": 0.45}[perfil] + rng.uniform(-0.04, 0.04), 2),
                "fidelidad": round({"generosa": 0.55, "resultadista": 0.4, "fiel": 0.85}[perfil] + rng.uniform(-0.05, 0.05), 2),
                "lema": rng.choice(T.LEMAS[papel]), "colores": list(paleta), "colores_bandera": paleta == paleta_bandera,
                "diseno": {"arquetipo": arq, "fuente": fte, "variante": rng.randrange(12), "caso": caso,
                           "simbolo": rng.choice(SIMBOLOS_TV),
                           "espaciado": rng.choice([3, 5, 7]) if caso == "mayus" else rng.choice([0, 1, 2])},
            })
    # slugs únicos (dos nombres distintos pueden dar el mismo slug al quitar acentos)
    vistos = Counter()
    for t in salida:
        vistos[t["slug"]] += 1
        if vistos[t["slug"]] > 1:
            t["slug"] = f"{t['slug']}-{t['pais_id']}"
    return salida, problemas


def svg_de(t: dict) -> str:
    from logos.television import componer
    dz = t["diseno"]
    d = {"nombre": t["nombre"], "slug": t["slug"], "paleta": tuple(t["colores"]), "arquetipo": dz["arquetipo"],
         "simbolo": dz["simbolo"], "fuente": dz["fuente"], "peso": PESO_FUENTE.get(dz["fuente"], 800),
         "variante": dz["variante"], "caso": dz["caso"], "espaciado": dz["espaciado"], "semilla": t["id"],
         "rubro_corto": "Televisión"}
    return componer(d)


def muestra(carpeta: str) -> None:
    teles, problemas = disenar()
    for pr in problemas:
        print("⚠️ ", pr)
    destino = os.path.join(carpeta, "televisoras")
    os.makedirs(destino, exist_ok=True)
    por_conf = defaultdict(lambda: defaultdict(list))
    pesos = []
    for t in teles:
        svg = svg_de(t)
        pesos.append(len(svg))
        with open(os.path.join(destino, f"{t['slug']}.svg"), "w", encoding="utf-8") as f:
            f.write(svg)
        por_conf[t["confederacion_id"]][t["pais"]].append(t)
    secciones = []
    for cid, nombre_conf in CONFEDERACIONES.items():
        filas = []
        for pais, lista in por_conf.get(cid, {}).items():
            tarjetas = []
            for t in lista:
                src, dz = f"televisoras/{t['slug']}.svg", t["diseno"]
                tarjetas.append(
                    f'<figure><div class="o"><img src="{src}"></div><div class="c"><img src="{src}"></div>'
                    f'<div class="chicos"><img src="{src}" style="height:32px"><img src="{src}" style="height:16px"></div>'
                    f'<figcaption><b>{t["nombre"]}</b><br><small>{T.PAPEL_NOMBRE[t["papel"]]} · {T.NIVELES[t["nivel"]]} · '
                    f'{T.PERFILES[t["perfil"]]["nombre"]}<br>{dz["arquetipo"]} · {dz["fuente"]}{" · colores de la bandera" if t["colores_bandera"] else ""}'
                    f'<br>«{t["lema"]}»</small></figcaption></figure>')
            filas.append(f'<div class="pais"><h3>{pais}</h3><section>{"".join(tarjetas)}</section></div>')
        secciones.append(f'<h2 id="c{cid}">{nombre_conf}</h2>{"".join(filas)}')
    indice = " · ".join(f'<a href="#c{cid}">{n}</a>' for cid, n in CONFEDERACIONES.items())
    with open(os.path.join(carpeta, "televisoras.html"), "w", encoding="utf-8") as f:
        f.write('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Televisoras</title><style>'
                'body{background:#0b1220;color:#e2e8f0;font-family:system-ui,Arial;margin:0;padding:20px}a{color:#86efac}'
                'h2{margin:34px 0 10px;font-size:20px;color:#86efac;border-bottom:1px solid #1e293b;padding-bottom:6px}'
                'h3{margin:16px 0 6px;font-size:14px;color:#cbd5e1}'
                'section{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}'
                '@media(max-width:800px){section{grid-template-columns:1fr}}'
                'figure{margin:0;background:#111a2e;border-radius:12px;padding:10px;display:grid;gap:6px;min-width:0}'
                '.o,.c{height:96px;border-radius:8px;display:flex;align-items:center;justify-content:center;padding:10px;overflow:hidden;min-width:0}'
                '.o{background:#111c2e}.c{background:#e5e7eb}.o img,.c img{width:100%;height:100%;min-width:0;object-fit:contain}'
                '.chicos{display:flex;gap:12px;align-items:center;background:#0b1220;padding:6px;border-radius:6px;overflow:hidden;min-width:0}.chicos img{max-width:60%;object-fit:contain}'
                'small{color:#94a3b8;font-size:11px}</style>'
                f'<p>{len(teles)} televisoras · {len(problemas)} problemas · peso medio {sum(pesos) // max(1, len(pesos)) // 1024 + 1} KB · {indice}</p>'
                + "".join(secciones))
    print(f"{len(teles)} logos en {destino} (hoja: {carpeta}/televisoras.html); problemas: {len(problemas)}")


def subir(carpeta: str) -> None:
    subprocess.run(["gcloud", "storage", "cp", os.path.join(carpeta, "televisoras", "*.svg"), CARPETA_BUCKET + "/",
                    "--cache-control=public, max-age=604800", "--content-type=image/svg+xml"], check=True)


def _db():
    import certifi
    from pymongo import MongoClient
    from config.settings import MONGODB_URI
    return MongoClient(MONGODB_URI, tlsCAFile=certifi.where())["mundial"]


def aplicar() -> None:
    teles, problemas = disenar()
    if problemas:
        sys.exit("Hay problemas, corregir config/televisoras.py:\n" + "\n".join(problemas))
    from pymongo import ASCENDING, UpdateOne
    db = _db()
    ops = []
    for t in teles:
        doc = {k: v for k, v in t.items() if k != "pais"}
        doc["logo"] = f"televisoras/{t['slug']}.svg"
        doc["ficticia"] = True
        ops.append(UpdateOne({"id": t["id"]}, {"$set": doc}, upsert=True))
    r = db["televisoras"].bulk_write(ops)
    db["televisoras"].create_index([("id", ASCENDING)], unique=True)
    db["televisoras"].create_index([("slug", ASCENDING)], unique=True)
    db["televisoras"].create_index([("pais_id", ASCENDING)])
    print(f"televisoras: {r.upserted_count} nuevas, {r.modified_count} actualizadas ({len(ops)} en total)")


def revertir() -> None:
    print("televisoras borradas:", _db()["televisoras"].delete_many({"ficticia": True}).deleted_count)


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    carpeta = sys.argv[2] if len(sys.argv) > 2 else "televisoras_muestra"
    if modo == "--muestra":
        muestra(carpeta)
    elif modo == "--subir":
        subir(carpeta)
    elif modo == "--aplicar":
        aplicar()
    elif modo == "--revertir":
        revertir()
    else:
        print(__doc__)
