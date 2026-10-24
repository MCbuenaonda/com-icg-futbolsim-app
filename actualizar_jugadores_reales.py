"""
Actualiza el NOMBRE y la EDAD de los jugadores de cada selección con futbolistas reales y en actividad, ubicados según
la posición en que juegan. Nada más cambia: atributos, contadores, rasgos, dorsal, id y posicion_id quedan iguales
(el jugador real "ocupa" un lugar existente del plantel: 22 por selección, 2 por posición).

Fuente: Wikipedia en inglés.
  - Plantel: secciones "Current squad" y "Recent call-ups" de "<país> national football team" (plantillas
    {{nat fs g player}} / {{nat fs r player}}): nombre, posición general (GK/DF/MF/FW), fecha de nacimiento y partidos.
  - Posición exacta: el campo 'position' de la ficha (infobox) de cada jugador ("Left-back", "Right winger"...).
El país se resuelve desde el emoji de paises.bandera (código ISO) + el nombre en inglés de flag-icons (country.json).

Los nombres también viven en los partidos ya jugados (eventos, goleadores, crónica...), y Estadísticas vincula
eventos con jugadores por (país, nombre): --aplicar reescribe esas referencias con el mismo mapa por id, así los
números del Mundial en curso siguen siendo de cada jugador.

    python actualizar_jugadores_reales.py --cache <dir> --descargar             # baja y cachea (solo lectura)
    python actualizar_jugadores_reales.py --cache <dir> --muestra [--paises A,B] # informe, no escribe
    python actualizar_jugadores_reales.py --cache <dir> --aplicar               # respaldo + escritura
    python actualizar_jugadores_reales.py --revertir respaldos/<archivo>.json.gz
    python actualizar_jugadores_reales.py --renombrar "2901=Gilberto Mora:18" ...   # cambios puntuales a mano

<dir de cache> también debe tener flag-icons/package/country.json (ver generar_banderas.py).
Después de aplicar: generar_avatares.py --generar/--subir (la edad cambia barba/canas) y reiniciar el servidor.
"""
import argparse
import gzip
import json
import os
import re
import ssl
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

RAIZ = os.path.dirname(os.path.abspath(__file__))
API = "https://en.wikipedia.org/w/api.php?"
AGENTE = {"User-Agent": "FutbolSim/1.0 (actualizacion de planteles; uso personal no comercial)"}
PAUSA = 0.8                      # entre pedidos a la API (cortesía)
EDAD_MIN, EDAD_MAX = 16, 45      # hay arqueros veteranos en selecciones chicas

# Títulos de Wikipedia que no siguen "<nombre> national football team" (se prueban antes que los automáticos)
TITULOS_ESPECIALES = {
    "us": "United States men's national soccer team", "ca": "Canada men's national soccer team",
    "au": "Australia men's national soccer team", "nz": "New Zealand men's national football team",
    "ie": "Republic of Ireland national football team", "ci": "Ivory Coast national football team",
    "cd": "DR Congo national football team", "cg": "Congo national football team",
    "ps": "Palestine national football team", "tw": "Chinese Taipei national football team",
    "cn": "China national football team", "kr": "South Korea national football team",
    "kp": "North Korea national football team", "va": None, "mk": "North Macedonia national football team",
    "cv": "Cape Verde national football team", "sz": "Eswatini national football team",
    "gm": "Gambia national football team", "bs": "Bahamas national football team",
    "tl": "Timor-Leste national football team", "cz": "Czech Republic national football team",
    "tr": "Turkey national football team", "ru": "Russia national football team",
    "vg": "British Virgin Islands national football team", "vi": "United States Virgin Islands national soccer team",
    "kn": "Saint Kitts and Nevis national football team", "vc": "Saint Vincent and the Grenadines national football team",
    "lc": "Saint Lucia national football team", "st": "São Tomé and Príncipe national football team",
    "bn": "Brunei national football team", "la": "Laos national football team", "mo": "Macau national football team",
    "hk": "Hong Kong national football team", "sy": "Syria national football team", "ir": "Iran national football team",
    "vn": "Vietnam national football team", "bo": "Bolivia national football team", "ve": "Venezuela national football team",
    "tz": "Tanzania national football team", "md": "Moldova national football team", "ky": "Cayman Islands national football team",
    "tc": "Turks and Caicos Islands national football team", "fm": None, "gb-eng": "England national football team",
    "gb-sct": "Scotland national football team", "gb-wls": "Wales national football team",
    "gb-nir": "Northern Ireland national football team", "cw": "Curaçao national football team",
}

# Por nombre de 'paises', cuando el emoji no alcanza (Irlanda del Norte tiene la bandera del Reino Unido) o la
# página general dejó de ser la del equipo masculino
TITULO_POR_PAIS = {
    "Irlanda del Norte": "Northern Ireland national football team",
    "Suecia": "Sweden men's national football team",
}

# Siglas de posicion (colección 'posiciones') por línea
LINEA = {"POR": "GK", "LI": "DF", "LD": "DF", "DFI": "DF", "DFD": "DF", "MC": "MF", "MI": "MF", "MD": "MF",
         "EI": "FW", "ED": "FW", "DC": "FW"}
GRUESA = {"GK": ["POR"], "DF": ["DFI", "DFD", "LI", "LD"], "MF": ["MC", "MI", "MD"], "FW": ["DC", "EI", "ED"]}
# Texto de la ficha -> lugares (se busca el término más específico primero, en el orden en que aparece)
TERMINOS_POSICION = [
    ("goalkeeper", ["POR"]),
    ("left wing-back", ["LI"]), ("left wing back", ["LI"]), ("left-back", ["LI"]), ("left back", ["LI"]),
    ("right wing-back", ["LD"]), ("right wing back", ["LD"]), ("right-back", ["LD"]), ("right back", ["LD"]),
    ("wing-back", ["LI", "LD"]), ("full-back", ["LI", "LD"]), ("full back", ["LI", "LD"]),
    ("centre-back", ["DFI", "DFD"]), ("center-back", ["DFI", "DFD"]), ("centre back", ["DFI", "DFD"]),
    ("central defender", ["DFI", "DFD"]), ("sweeper", ["DFI", "DFD"]), ("defender", ["DFI", "DFD", "LI", "LD"]),
    ("left midfielder", ["MI"]), ("left-midfielder", ["MI"]), ("right midfielder", ["MD"]), ("right-midfielder", ["MD"]),
    ("wide midfielder", ["MI", "MD"]),
    ("defensive midfielder", ["MC"]), ("central midfielder", ["MC"]), ("attacking midfielder", ["MC", "MI", "MD"]),
    ("box-to-box", ["MC"]), ("playmaker", ["MC"]), ("midfielder", ["MC", "MI", "MD"]),
    ("left winger", ["EI"]), ("left wing", ["EI"]), ("right winger", ["ED"]), ("right wing", ["ED"]),
    ("inside forward", ["EI", "ED"]), ("winger", ["EI", "ED"]),
    ("centre-forward", ["DC"]), ("center forward", ["DC"]), ("centre forward", ["DC"]), ("striker", ["DC"]),
    ("second striker", ["DC"]), ("forward", ["DC", "EI", "ED"]),
]


# ---------------------------------------------------------------------------------------------------------
# Wikipedia
# ---------------------------------------------------------------------------------------------------------
def _ctx():
    import certifi
    return ssl.create_default_context(cafile=certifi.where())


def _api(params: dict) -> dict:
    import urllib.error
    params = {**params, "format": "json", "maxlag": 5}
    ultimo = None
    for intento in range(8):
        try:
            req = urllib.request.Request(API + urllib.parse.urlencode(params), headers=AGENTE)
            datos = json.load(urllib.request.urlopen(req, timeout=40, context=_ctx()))
            if "error" in datos and datos["error"].get("code") == "maxlag":
                time.sleep(5)
                continue
            time.sleep(PAUSA)
            return datos
        except urllib.error.HTTPError as e:      # 429 = demasiados pedidos: respetar Retry-After
            ultimo = e
            espera = int(e.headers.get("Retry-After") or 0) or 5 * (intento + 1)
            time.sleep(min(espera, 60))
        except Exception as e:
            ultimo = e
            time.sleep(3 + intento * 4)
    raise RuntimeError(f"La API de Wikipedia no respondió ({ultimo}): {params.get('titles') or params.get('page')}")


def _dividir(texto: str) -> List[str]:
    """Divide los parámetros de una plantilla por '|' respetando [[...]] y {{...}} anidados."""
    partes, actual, nivel_l, nivel_t, i = [], [], 0, 0, 0
    while i < len(texto):
        dos = texto[i:i + 2]
        if dos == "[[":
            nivel_l += 1; actual.append(dos); i += 2; continue
        if dos == "]]":
            nivel_l -= 1; actual.append(dos); i += 2; continue
        if dos == "{{":
            nivel_t += 1; actual.append(dos); i += 2; continue
        if dos == "}}":
            nivel_t -= 1; actual.append(dos); i += 2; continue
        if texto[i] == "|" and nivel_l == 0 and nivel_t == 0:
            partes.append("".join(actual)); actual = []
        else:
            actual.append(texto[i])
        i += 1
    partes.append("".join(actual))
    return partes


def _plantillas(wikitext: str, nombres: Tuple[str, ...]) -> List[str]:
    """Contenido de cada {{nombre|...}} del texto (con llaves anidadas)."""
    salida, i = [], 0
    patron = re.compile(r"\{\{\s*(" + "|".join(re.escape(n) for n in nombres) + r")\s*\|", re.I)
    while True:
        m = patron.search(wikitext, i)
        if not m:
            return salida
        j, nivel = m.end(), 1
        while j < len(wikitext) and nivel:
            if wikitext.startswith("{{", j):
                nivel += 1; j += 2
            elif wikitext.startswith("}}", j):
                nivel -= 1; j += 2
            else:
                j += 1
        salida.append(wikitext[m.end(): j - 2])
        i = j


def _limpiar(texto: str) -> str:
    texto = re.sub(r"<ref[^>]*/>|<ref.*?</ref>|<!--.*?-->", "", texto, flags=re.S)
    texto = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", texto)
    texto = re.sub(r"\{\{.*?\}\}|<[^>]+>|'''?", "", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _nombre_y_enlace(valor: str) -> Tuple[str, Optional[str]]:
    valor = re.sub(r"<ref.*?</ref>|<ref[^>]*/>", "", valor, flags=re.S).strip()
    m = re.search(r"\{\{\s*sortname\s*\|(.*?)\}\}", valor, flags=re.I | re.S)
    if m:
        p = [x.strip() for x in _dividir(m.group(1))]
        pos = [x for x in p if "=" not in x]
        nombre = " ".join(x for x in pos[:2] if x)
        enlace = pos[2] if len(pos) > 2 and pos[2] else None
        if "nolink" in m.group(1):
            return nombre, None
        return nombre, enlace or nombre
    m = re.search(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", valor)
    if m:
        return (m.group(2) or m.group(1)).strip(), m.group(1).strip()
    return _limpiar(valor), None


def _fecha(valor: str) -> Optional[Tuple[int, int, int]]:
    m = re.search(r"\{\{\s*(?:birth date and age|bda|birth date)\s*\|(.*?)\}\}", valor, flags=re.I | re.S)
    numeros = [x.strip() for x in _dividir(m.group(1))] if m else []
    numeros = [int(x) for x in numeros if re.fullmatch(r"\d{1,4}", x)]
    if len(numeros) >= 3 and numeros[0] > 1900:
        return numeros[0], numeros[1], numeros[2]
    m = re.search(r"(19|20)\d{2}", valor)
    return (int(m.group(0)), 7, 1) if m else None


def _jugadores_de_seccion(wikitext: str, origen: str) -> List[dict]:
    salida = []
    for cuerpo in _plantillas(wikitext, ("nat fs g player", "nat fs r player", "nat fs player")):
        campos = {}
        for parte in _dividir(cuerpo):
            if "=" in parte:
                k, v = parte.split("=", 1)
                campos[k.strip().lower()] = v.strip()
        if "name" not in campos:
            continue
        # "RET" = se retiró de la selección: se descarta de las convocatorias recientes; si figura en la convocatoria
        # vigente, sigue convocado (p. ej. Messi aparece en el plantel actual con esa marca)
        if origen == "reciente" and re.search(r"\bRET\b|\bretired\b", cuerpo, flags=re.I):
            continue
        nombre, enlace = _nombre_y_enlace(campos["name"])
        pos = (campos.get("pos") or "").strip().upper()[:2]
        caps = re.match(r"\d+", _limpiar(campos.get("caps", "")) or "")
        if not nombre or pos not in GRUESA:
            continue
        salida.append({"nombre": nombre, "enlace": enlace, "pos": pos, "nac": _fecha(campos.get("age", "")),
                       "caps": int(caps.group(0)) if caps else 0, "origen": origen})
    return salida


def _titulo_seleccion(codigo: str, nombre_en: str) -> Optional[str]:
    candidatos = []
    if codigo in TITULOS_ESPECIALES:
        if TITULOS_ESPECIALES[codigo] is None:
            return None
        candidatos.append(TITULOS_ESPECIALES[codigo])
    candidatos += [f"{nombre_en} national football team", f"{nombre_en} men's national football team",
                   f"{nombre_en} national soccer team", f"{nombre_en} men's national soccer team"]
    for t in candidatos:
        datos = _api({"action": "query", "titles": t, "redirects": 1})
        pagina = next(iter(datos["query"]["pages"].values()))
        if "missing" not in pagina:
            return pagina["title"]
    return None


def _plantel(titulo: str) -> List[dict]:
    secciones = _api({"action": "parse", "page": titulo, "prop": "sections", "redirects": 1})["parse"]["sections"]
    jugadores, vistos = [], set()
    # Algunas páginas (Bután, Samoa) ponen el plantel actual directo en "Players", sin "Current squad"
    sin_actual = not any("current squad" in _limpiar(s["line"]).lower() or _limpiar(s["line"]).lower() == "squad" for s in secciones)
    for s in secciones:
        linea = _limpiar(s["line"]).lower()
        origen = ("actual" if "current squad" in linea or linea == "squad" or (sin_actual and linea == "players")
                  else ("reciente" if "recent call" in linea else None))
        if not origen or s.get("toclevel", 1) > 2:
            continue
        wt = _api({"action": "parse", "page": titulo, "prop": "wikitext", "section": s["index"], "redirects": 1})["parse"]["wikitext"]["*"]
        for j in _jugadores_de_seccion(wt, origen):
            clave = _normalizar(j["nombre"])
            if clave not in vistos:
                vistos.add(clave)
                jugadores.append(j)
    return jugadores


def _posiciones_fichas(enlaces: List[str]) -> Dict[str, str]:
    """{enlace: texto de 'position' de la ficha}, en lotes de 50 (sigue redirecciones)."""
    salida = {}
    for i in range(0, len(enlaces), 50):
        lote = enlaces[i:i + 50]
        datos = _api({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main", "rvsection": 0,
                      "titles": "|".join(lote), "redirects": 1, "formatversion": 2})
        q = datos.get("query", {})
        alias = {}
        for tipo in ("normalized", "redirects"):
            for r in q.get(tipo, []):
                alias[r["to"]] = alias.get(r["from"], r["from"])
        for p in q.get("pages", []):
            if "revisions" not in p:
                continue
            texto = p["revisions"][0]["slots"]["main"]["content"]
            m = re.search(r"\|\s*position\s*=\s*(.+)", texto)
            if not m:
                continue
            original = p["title"]
            while original in alias:
                original = alias[original]
            salida[original] = _limpiar(m.group(1))[:120]
    return salida


# ---------------------------------------------------------------------------------------------------------
# Datos locales
# ---------------------------------------------------------------------------------------------------------
def _db():
    sys.path.insert(0, RAIZ)
    import certifi
    from pymongo import MongoClient
    from config.settings import MONGODB_URI
    return MongoClient(MONGODB_URI, tlsCAFile=certifi.where()).get_database("mundial")


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def codigo_iso(emoji: str) -> Optional[str]:
    regionales = [c for c in emoji if 0x1F1E6 <= ord(c) <= 0x1F1FF]
    if len(regionales) == 2:
        return "".join(chr(ord(c) - 0x1F1E6 + 97) for c in regionales)
    etiquetas = "".join(chr(ord(c) - 0xE0061 + 97) for c in emoji if 0xE0061 <= ord(c) <= 0xE007A)
    return f"gb-{etiquetas[2:]}" if etiquetas.startswith("gb") else None


def descargar(cache: str, solo: Optional[List[str]] = None) -> None:
    db = _db()
    nombres_en = {c["code"]: c["name"] for c in json.load(open(os.path.join(cache, "flag-icons", "package", "country.json")))}
    archivo = os.path.join(cache, "planteles.json")
    datos = json.load(open(archivo)) if os.path.exists(archivo) else {}
    paises = list(db["paises"].find({}, {"id": 1, "nombre": 1, "bandera": 1}).sort("id", 1))
    for p in paises:
        if solo and p["nombre"] not in solo:
            continue
        clave = str(p["id"])
        if clave in datos and datos[clave].get("jugadores") is not None and not solo:
            continue
        codigo = codigo_iso(p.get("bandera") or "")
        titulo = TITULO_POR_PAIS.get(p["nombre"]) or (_titulo_seleccion(codigo, nombres_en.get(codigo, p["nombre"])) if codigo else None)
        jugadores = _plantel(titulo) if titulo else []
        fichas = _posiciones_fichas([j["enlace"] for j in jugadores if j.get("enlace")])
        for j in jugadores:
            j["ficha"] = fichas.get(j.get("enlace"))
        datos[clave] = {"pais": p["nombre"], "codigo": codigo, "titulo": titulo, "jugadores": jugadores,
                        "descargado": datetime.now().isoformat(timespec="seconds")}
        print(f"{p['nombre']:28s} {titulo or 'SIN PÁGINA':55s} {len(jugadores):3d} jugadores · {len(fichas)} fichas")
        json.dump(datos, open(archivo, "w"), ensure_ascii=False, indent=1)


# ---------------------------------------------------------------------------------------------------------
# Asignación
# ---------------------------------------------------------------------------------------------------------
def _lugares_por_ficha(ficha: Optional[str]) -> List[str]:
    if not ficha:
        return []
    texto = ficha.lower()
    hallados = []
    ocupado = [False] * len(texto)
    for termino, lugares in TERMINOS_POSICION:            # más específicos primero
        for m in re.finditer(re.escape(termino), texto):
            if any(ocupado[m.start():m.end()]):
                continue
            for k in range(m.start(), m.end()):
                ocupado[k] = True
            hallados.append((m.start(), lugares))
    salida = []
    for _, lugares in sorted(hallados):
        for l in lugares:
            if l not in salida:
                salida.append(l)
    return salida


def _edad(nac, hoy: date) -> Optional[int]:
    if not nac:
        return None
    y, m, d = nac
    try:
        return hoy.year - y - ((hoy.month, hoy.day) < (m, max(1, min(d, 28))))
    except Exception:
        return None


def asignar(lugares_db: List[dict], reales: List[dict], hoy: date) -> Tuple[Dict[int, dict], List[dict]]:
    """
    lugares_db: [{id, siglas, titular, nombre, edad, overall}] (22). reales: jugadores del plantel.
    Devuelve ({id_lugar: {nombre, edad, como}}, lugares_sin_cubrir).
    """
    candidatos = []
    for j in reales:
        edad = _edad(j.get("nac"), hoy)
        if edad is None or not (EDAD_MIN <= edad <= EDAD_MAX):
            continue
        por_ficha = [l for l in _lugares_por_ficha(j.get("ficha")) if LINEA[l] == j["pos"] or j["pos"] != "GK" and LINEA[l] != "GK"]
        if j["pos"] == "GK":
            por_ficha = ["POR"]
        elif "POR" in por_ficha:
            por_ficha.remove("POR")
        linea = [l for l in GRUESA[j["pos"]] if l not in por_ficha]
        candidatos.append({**j, "edad": edad, "primarios": por_ficha[:1] or GRUESA[j["pos"]][:1] if por_ficha else [],
                           "secundarios": por_ficha[1:], "linea": linea, "orden": (j["origen"] != "actual", -j.get("caps", 0))})
    candidatos.sort(key=lambda c: c["orden"])
    cupo = {}
    for l in lugares_db:
        cupo.setdefault(l["siglas"], []).append(l)
    for sig in cupo:   # el titular (y mejor overall) primero: recibe al de más partidos
        cupo[sig].sort(key=lambda l: (not l.get("titular"), -(l.get("overall") or 0)))
    asignados: Dict[str, List[dict]] = {s: [] for s in cupo}
    usados = set()

    def poner(c, sig, como):
        if sig in asignados and len(asignados[sig]) < len(cupo[sig]) and id(c) not in usados:
            asignados[sig].append({**c, "como": como})
            usados.add(id(c))
            return True
        return False

    # 0) Quien ya está en la base y sigue activo se queda en su lugar si ese lugar es una posición de su ficha
    #    (sin ficha: cualquiera de su línea). Conserva la ortografía de la base ("Julián Álvarez", no "Alvarez").
    por_nombre = {_normalizar(l["nombre"]): l for l in lugares_db}
    fijos = {}
    for c in candidatos:
        actual = por_nombre.get(_normalizar(c["nombre"]))
        validos = (c["primarios"] + c["secundarios"]) if c.get("ficha") else GRUESA[c["pos"]]
        if actual and actual["siglas"] in validos and actual["id"] not in fijos:
            fijos[actual["id"]] = {**c, "nombre": actual["nombre"], "como": "se mantiene"}
            usados.add(id(c))
    for sig in cupo:
        libres = [l for l in cupo[sig] if l["id"] not in fijos]
        cupo[sig] = libres
    # 1) posición exacta  2) secundaria  3) misma línea
    for c in candidatos:
        if id(c) not in usados:
            any(poner(c, s, "ficha" if c.get("ficha") else "plantel") for s in (c["primarios"] or GRUESA[c["pos"]][:1]))
    for c in candidatos:
        if id(c) not in usados:
            any(poner(c, s, "secundaria") for s in c["secundarios"])
    for c in candidatos:
        if id(c) not in usados:
            any(poner(c, s, "misma línea") for s in c["linea"] + GRUESA[c["pos"]])
    # 4) Planteles cortos: antes que dejar un lugar con un nombre que no es real, un jugador de campo sobrante
    #    a otra línea (nunca de arquero a campo ni al revés)
    for c in candidatos:
        if id(c) not in usados and c["pos"] != "GK":
            any(poner(c, s, "otra línea") for s in ("DFI", "DFD", "LI", "LD", "MC", "MI", "MD", "DC", "EI", "ED"))
    resultado = dict(fijos)
    sin_cubrir = []
    for sig, lugares in cupo.items():
        elegidos = sorted(asignados[sig], key=lambda c: c["orden"])
        for lugar, c in zip(lugares, elegidos):
            resultado[lugar["id"]] = c
        sin_cubrir += lugares[len(elegidos):]
    return {k: {"nombre": v["nombre"], "edad": v["edad"], "como": v["como"], "ficha": v.get("ficha"), "caps": v.get("caps", 0)}
            for k, v in resultado.items()}, sin_cubrir


def calcular_cambios(cache: str, solo: Optional[List[str]] = None, hoy: Optional[date] = None):
    """{pais_id: {id_jugador: {viejo, nuevo, edad_vieja, edad, siglas, como}}} + informe de huecos."""
    hoy = hoy or date.today()
    db = _db()
    datos = json.load(open(os.path.join(cache, "planteles.json")))
    siglas = {p["id"]: p["siglas"] for p in db["posiciones"].find({}, {"id": 1, "siglas": 1})}
    cambios, huecos = {}, {}
    for p in db["paises"].find({}, {"id": 1, "nombre": 1}).sort("nombre", 1):
        if solo and p["nombre"] not in solo:
            continue
        reales = (datos.get(str(p["id"])) or {}).get("jugadores") or []
        lugares = [{"id": j["id"], "siglas": siglas[j["posicion_id"]], "titular": j.get("titular"), "nombre": j["nombre"],
                    "edad": j.get("edad"), "overall": j.get("overall")}
                   for j in db["jugadores"].find({"pais_id": p["id"], "leyenda": {"$ne": True}}, {"id": 1, "posicion_id": 1, "titular": 1, "nombre": 1, "edad": 1, "overall": 1})]
        asignacion, sin_cubrir = asignar(lugares, reales, hoy)
        por_id = {l["id"]: l for l in lugares}
        cambios[p["id"]] = {i: {"viejo": por_id[i]["nombre"], "nuevo": a["nombre"], "edad_vieja": por_id[i]["edad"], "edad": a["edad"],
                                "siglas": por_id[i]["siglas"], "como": a["como"], "ficha": a["ficha"]} for i, a in asignacion.items()}
        if sin_cubrir:
            huecos[p["nombre"]] = [f"{l['siglas']} ({l['nombre']})" for l in sin_cubrir]
        # Un lugar SIN cubrir conserva su nombre viejo; si ese nombre es justo el de un jugador real asignado a OTRO
        # lugar, habría dos con el mismo nombre (y los eventos del Mundial, que se vinculan por nombre, se mezclarían).
        # Se resuelve dejando al jugador real en el lugar que ya tenía su nombre (y sus números), con la edad real,
        # y el otro lugar conserva su nombre viejo.
        cs = cambios[p["id"]]
        for l in sin_cubrir:
            otro = next((i for i, c in cs.items() if c["nuevo"] == l["nombre"] and i != l["id"]), None)
            if otro is not None:
                real = cs.pop(otro)
                cs[l["id"]] = {**real, "viejo": l["nombre"], "nuevo": l["nombre"], "edad_vieja": l["edad"],
                               "siglas": l["siglas"], "como": "se mantiene (homónimo)"}
                huecos.setdefault(p["nombre"], []).append(f"{por_id[otro]['siglas']} ({por_id[otro]['nombre']})")
        # Control: ningún nombre repetido dentro de la selección (un lugar sin cubrir conserva su nombre viejo)
        finales = [cambios[p["id"]].get(l["id"], {}).get("nuevo", l["nombre"]) for l in lugares]
        repetidos = {n for n in finales if finales.count(n) > 1}
        if repetidos:
            huecos.setdefault(p["nombre"], []).append(f"NOMBRE REPETIDO: {', '.join(sorted(repetidos))}")
    return cambios, huecos


def muestra(cache: str, solo: Optional[List[str]] = None) -> None:
    db = _db()
    nombres = {p["id"]: p["nombre"] for p in db["paises"].find({}, {"id": 1, "nombre": 1})}
    cambios, huecos = calcular_cambios(cache, solo)
    total = sum(len(v) for v in cambios.values())
    renombres = sum(1 for v in cambios.values() for c in v.values() if c["viejo"] != c["nuevo"])
    for pid, cs in cambios.items():
        if solo:
            print(f"\n== {nombres[pid]} ({len(cs)}/22)")
            for i, c in sorted(cs.items(), key=lambda kv: list(LINEA).index(kv[1]["siglas"])):
                marca = "=" if c["viejo"] == c["nuevo"] else "→"
                print(f"  {c['siglas']:4s} {c['viejo'][:24]:24s} {marca} {c['nuevo'][:26]:26s} {c['edad_vieja']}→{c['edad']:<3} [{c['como']}] {(c['ficha'] or '')[:40]}")
    print(f"\nLugares cubiertos: {total} de {22 * len(cambios)} · renombrados: {renombres} · selecciones con huecos: {len(huecos)}")
    for pais, h in sorted(huecos.items(), key=lambda kv: -len(kv[1]))[:40]:
        print(f"  {pais:28s} faltan {len(h):2d}: {', '.join(h[:6])}{' …' if len(h) > 6 else ''}")


# ---------------------------------------------------------------------------------------------------------
# Escritura (respaldo, jugadores, partidos y fantasy) y reversión
# ---------------------------------------------------------------------------------------------------------
CAMPOS_TEXTO = ("opinion", "texto_narrativo")


def _reemplazador(mapa: Dict[str, str]):
    """Reemplazo de nombres completos en una sola pasada (sin encadenar: A→B y B→C no da A→C), del más largo al más corto."""
    if not mapa:
        return lambda s: s
    patron = re.compile(r"(?<![\w])(" + "|".join(re.escape(k) for k in sorted(mapa, key=len, reverse=True)) + r")(?![\w])")
    return lambda s: patron.sub(lambda m: mapa[m.group(1)], s) if isinstance(s, str) else s


# Eventos cuyo SEGUNDO jugador es del rival (así los lee estadisticas_service._agregar_jugadores_mundial)
TIPOS_SEGUNDO_RIVAL = {"🛑 FALTA", "🟨 TARJETA AMARILLA", "🧤 ATAJADA ESPECTACULAR", "❌ PENAL FALLADO"}


def reescribir_partido(res: dict, mapa_ids: Dict[int, str], mapa_local: Dict[str, str], mapa_visita: Dict[str, str],
                       equipos: Optional[Tuple[str, str]] = None, viejos: Optional[Tuple[set, set]] = None) -> dict:
    """
    Devuelve los campos de 'resultado' a $set con los nombres nuevos (no modifica 'res'). En los eventos, si un nombre
    existía en los dos equipos (viejos = nombres originales de local y visita), se resuelve igual que Estadísticas: el
    primero es del equipo del evento y el segundo, en faltas/tarjetas/atajadas/penales, del rival.
    """
    mapa = {**mapa_visita, **mapa_local}
    texto = _reemplazador(mapa)
    nuevo = {}
    for campo in ("goleadores", "atajadores"):
        if res.get(campo):
            nuevo[campo] = [{**g, "jugador_nombre": mapa_ids.get(g.get("jugador_id"), g.get("jugador_nombre"))} for g in res[campo]]
    if res.get("comentarios_jugadores"):
        nuevo["comentarios_jugadores"] = [{**c, "nombre": mapa_ids.get(c.get("jugador_id"), c.get("nombre")), "comentario": texto(c.get("comentario"))}
                                          for c in res["comentarios_jugadores"]]
    if res.get("eventos"):
        def lado_de(e, i, n):
            vl, vv = viejos if viejos else (set(mapa_local), set(mapa_visita))
            en_l, en_v = n in vl or n in mapa_local, n in vv or n in mapa_visita
            if en_l != en_v:
                return "L" if en_l else "V"
            propio = "L" if equipos and e.get("equipo") == equipos[0] else ("V" if equipos and e.get("equipo") == equipos[1] else None)
            if propio is None:
                return None
            if i >= 1 and e.get("tipo") in TIPOS_SEGUNDO_RIVAL:
                return "V" if propio == "L" else "L"
            return propio

        def renombrar(e, i, n):
            lado = lado_de(e, i, n)
            return (mapa_local if lado == "L" else mapa_visita if lado == "V" else mapa).get(n, n)

        nuevo["eventos"] = [{**e, "jugadores": [renombrar(e, i, n) for i, n in enumerate(e.get("jugadores") or [])], "descripcion": texto(e.get("descripcion"))}
                            for e in res["eventos"]]
    for campo, m in (("titulares_local", mapa_local), ("titulares_visitante", mapa_visita)):
        if res.get(campo):
            nuevo[campo] = [m.get(n, n) for n in res[campo]]
    for campo in CAMPOS_TEXTO:
        if res.get(campo):
            nuevo[campo] = texto(res[campo])
    if res.get("cronica"):   # la crónica (cronica_service) se vuelve a escribir sola con los nombres nuevos
        nuevo["cronica"] = None
    return nuevo


def renombrar(pedidos: List[str]) -> None:
    """
    Cambios puntuales a mano: cada pedido es "id=Nombre Nuevo:edad". Mismo camino que --aplicar (respaldo, jugadores,
    partidos jugados y fantasy), así el nuevo hereda los números del Mundial de ese lugar sin romper Estadísticas.
    """
    db = _db()
    cambios: Dict[int, Dict[int, dict]] = {}
    for pedido in pedidos:
        ident, resto = pedido.split("=", 1)
        nombre, _, edad = resto.rpartition(":") if ":" in resto else (resto, "", "")
        j = db["jugadores"].find_one({"id": int(ident)}, {"id": 1, "nombre": 1, "edad": 1, "pais_id": 1, "posicion_id": 1, "leyenda": 1})
        if not j:
            sys.exit(f"El id {ident} no existe")
        if db["jugadores"].find_one({"pais_id": j["pais_id"], "nombre": nombre.strip(), "id": {"$ne": j["id"]}}):
            sys.exit(f"Ya hay un {nombre.strip()} en esa selección")
        cambios.setdefault(j["pais_id"], {})[j["id"]] = {"viejo": j["nombre"], "nuevo": nombre.strip(), "edad_vieja": j.get("edad"),
                                                          "edad": int(edad) if edad else j.get("edad"), "siglas": "", "como": "manual", "ficha": None}
        print(f"  {j['id']}: {j['nombre']} ({j.get('edad')}) → {nombre.strip()} ({edad or j.get('edad')})")
    aplicar(None, (cambios, {}))


def aplicar(cache: Optional[str], precalculado=None) -> None:
    from pymongo import UpdateOne
    db = _db()
    cambios, huecos = precalculado or calcular_cambios(cache)
    por_id = {i: c for cs in cambios.values() for i, c in cs.items()}
    renombrados = {i: c for i, c in por_id.items() if c["viejo"] != c["nuevo"]}
    print(f"Lugares a actualizar: {len(por_id)} (renombrados {len(renombrados)})")

    # 1) Respaldo local (gz) de jugadores + campos con nombres de los partidos + fantasy
    os.makedirs(os.path.join(RAIZ, "respaldos"), exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    archivo = os.path.join(RAIZ, "respaldos", f"jugadores_reales_{marca}.json.gz")
    proy = {f"resultado.{c}": 1 for c in ("goleadores", "atajadores", "comentarios_jugadores", "eventos", "titulares_local", "titulares_visitante") + CAMPOS_TEXTO}
    respaldo = {
        "jugadores": [{"id": j["id"], "nombre": j["nombre"], "edad": j.get("edad")} for j in db["jugadores"].find({}, {"id": 1, "nombre": 1, "edad": 1})],
        "juegos": [{"_id": str(j["_id"]), "resultado": j.get("resultado") or {}} for j in db["juegos"].find({"resultado": {"$exists": True}}, proy)],
        "fantasy": [{"_id": str(f["_id"]), "jugador_nombre": f.get("jugador_nombre")} for f in db["fantasy_points_history"].find({}, {"jugador_nombre": 1})],
    }
    with gzip.open(archivo, "wt", encoding="utf-8") as f:
        json.dump(respaldo, f, ensure_ascii=False, default=str)
    print("Respaldo:", archivo)

    # nombres ORIGINALES de cada selección (antes de escribir): resuelven homónimos entre los dos equipos de un partido
    viejos_pais: Dict[int, set] = {}
    for jv in db["jugadores"].find({}, {"pais_id": 1, "nombre": 1}):
        viejos_pais.setdefault(jv.get("pais_id"), set()).add(jv.get("nombre"))

    # 2) Jugadores: solo nombre y edad
    ops = [UpdateOne({"id": i}, {"$set": {"nombre": c["nuevo"], "edad": c["edad"]}}) for i, c in por_id.items()]
    r = db["jugadores"].bulk_write(ops, ordered=False)
    print(f"jugadores: {r.modified_count} modificados")

    # 3) Partidos jugados: mismas referencias con los nombres nuevos
    mapa_ids = {i: c["nuevo"] for i, c in renombrados.items()}
    mapa_pais: Dict[int, Dict[str, str]] = {}
    for pid, cs in cambios.items():
        mapa_pais[pid] = {c["viejo"]: c["nuevo"] for c in cs.values() if c["viejo"] != c["nuevo"]}
    ops = []
    for j in db["juegos"].find({"resultado": {"$exists": True}}, {**proy, "equipo_local.id": 1, "equipo_visitante.id": 1,
                                                                    "equipo_local.nombre": 1, "equipo_visitante.nombre": 1}):
        loc, vis = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
        ml = mapa_pais.get(loc.get("id"), {})
        mv = mapa_pais.get(vis.get("id"), {})
        if not (ml or mv):
            continue
        nuevo = reescribir_partido(j["resultado"], mapa_ids, ml, mv, (loc.get("nombre"), vis.get("nombre")),
                                   (viejos_pais.get(loc.get("id"), set()), viejos_pais.get(vis.get("id"), set())))
        if nuevo:
            ops.append(UpdateOne({"_id": j["_id"]}, {"$set": {f"resultado.{k}": v for k, v in nuevo.items()}}))
    for k in range(0, len(ops), 100):
        db["juegos"].bulk_write(ops[k:k + 100], ordered=False)
    print(f"juegos: {len(ops)} partidos reescritos")

    # 4) Historial de puntos del Once Ideal
    ops = [UpdateOne({"_id": f["_id"]}, {"$set": {"jugador_nombre": mapa_ids[f["jugador_id"]]}})
           for f in db["fantasy_points_history"].find({"jugador_id": {"$in": list(mapa_ids)}}, {"jugador_id": 1})]
    if ops:
        db["fantasy_points_history"].bulk_write(ops, ordered=False)
    print(f"fantasy_points_history: {len(ops)} registros")
    if huecos:
        print(f"Lugares sin jugador real (conservan el actual): {sum(len(h) for h in huecos.values())} en {len(huecos)} selecciones")


def revertir(archivo: str) -> None:
    from bson import ObjectId
    from pymongo import UpdateOne
    db = _db()
    with gzip.open(archivo, "rt", encoding="utf-8") as f:
        r = json.load(f)
    db["jugadores"].bulk_write([UpdateOne({"id": j["id"]}, {"$set": {"nombre": j["nombre"], "edad": j["edad"]}}) for j in r["jugadores"]], ordered=False)
    ops = [UpdateOne({"_id": ObjectId(j["_id"])}, {"$set": {f"resultado.{k}": v for k, v in j["resultado"].items()}}) for j in r["juegos"] if j["resultado"]]
    for k in range(0, len(ops), 100):
        db["juegos"].bulk_write(ops[k:k + 100], ordered=False)
    if r["fantasy"]:
        db["fantasy_points_history"].bulk_write([UpdateOne({"_id": ObjectId(f["_id"])}, {"$set": {"jugador_nombre": f["jugador_nombre"]}}) for f in r["fantasy"]])
    print("Revertido desde", archivo)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache")
    ap.add_argument("--paises", help="lista separada por comas (nombres de paises.nombre)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--descargar", action="store_true")
    g.add_argument("--muestra", action="store_true")
    g.add_argument("--aplicar", action="store_true")
    g.add_argument("--revertir")
    g.add_argument("--renombrar", nargs="+", metavar="ID=NOMBRE:EDAD", help="cambios puntuales a mano")
    a = ap.parse_args()
    solo = [x.strip() for x in a.paises.split(",")] if a.paises else None
    if a.descargar:
        descargar(a.cache, solo)
    elif a.muestra:
        muestra(a.cache, solo)
    elif a.aplicar:
        aplicar(a.cache)
    elif a.renombrar:
        renombrar(a.renombrar)
    else:
        revertir(a.revertir)
