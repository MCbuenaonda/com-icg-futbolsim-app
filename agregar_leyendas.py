"""
Agrega las LEYENDAS de cada selección: un once histórico (una por cada una de las 11 posiciones) de futbolistas
ya retirados de su selección, como jugadores nuevos de la colección 'jugadores' con `leyenda: true`.

    python agregar_leyendas.py --cache <dir> --descargar [--paises A,B]   # baja y cachea (solo lectura)
    python agregar_leyendas.py --cache <dir> --muestra [--paises A,B]     # informe, no escribe
    python agregar_leyendas.py --cache <dir> --aplicar                    # inserta (respaldo en respaldos/)
    python agregar_leyendas.py --revertir                                 # borra las leyendas y sus estampas

<dir> es el mismo cache de actualizar_jugadores_reales.py (usa su planteles.json para resolver la página de
Wikipedia de cada selección y para excluir a los convocados actuales) y escribe ahí leyendas.json.

Fuentes:
  - Wikidata (una consulta por selección): todos los que jugaron en ella (P54), con partidos/goles (P1350/P1351),
    años en la selección (P580/P582), fecha de nacimiento, fama (cantidad de Wikipedias con artículo) y su artículo
    en inglés. Las selecciones con predecesora histórica la suman (Rusia ← URSS, Serbia ← Yugoslavia...).
  - Wikipedia: la posición exacta de la ficha (infobox) de los mejores candidatos.
  - leyendas_curadas.json (opcional): el once histórico elegido a mano para las potencias, por posición.

Reglas:
  - Solo retirados de su selección: ni convocados actuales (planteles.json ni la base) ni quien siga activo según
    Wikidata. Cada persona es leyenda de UNA sola selección (la de más partidos).
  - Puntaje = fama (log de wikis) + partidos con la selección; asignación por posición en pasadas: exacta de la
    ficha → otra posición de su ficha → misma línea → otra línea (nunca un arquero fuera del arco ni al revés).
  - Edad = la de su plenitud: punto medio de su etapa en la selección (24-31; arqueros 26-33; sin dato, 27/29).
  - Atributos: 80 parejo (±2 según los favoritos de su línea), moral y forma también en 80.
    Se guardan en 'atributos_base' para que restart_mundial los restaure (ver mundial_service.restart_mundial).
  - Dorsal 22 + posicion_id (23..33), id desde max(id)+1.

Después de aplicar: generar_avatares.py --generar/--subir/--asignar para los ids nuevos y reiniciar el servidor.
"""
import argparse
import gzip
import json
import math
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Dict, List, Optional

import actualizar_jugadores_reales as AR

RAIZ = os.path.dirname(os.path.abspath(__file__))
WDQS = "https://query.wikidata.org/sparql?"
AGENTE = {"User-Agent": "FutbolSim/1.0 (leyendas por seleccion; uso personal no comercial)"}
PAUSA_WD = 1.0
CANDIDATOS_POR_PAIS = 400          # filas de Wikidata (ordenadas por fama)
FICHAS_POR_PAIS = 70               # a los mejores se les lee la posición exacta en Wikipedia
ARCHIVO_CURADAS = os.path.join(RAIZ, "leyendas_curadas.json")
# Ficticias para los lugares que quedan vacíos (selecciones chicas sin suficientes futbolistas históricos registrados)
ARCHIVO_INVENTADAS = os.path.join(RAIZ, "leyendas_inventadas.json")

SIGLAS = ["POR", "DFI", "DFD", "LI", "LD", "MI", "MC", "MD", "EI", "DC", "ED"]   # posicion_id 1..11
POSICION_ID = {s: i + 1 for i, s in enumerate(SIGLAS)}
SECTOR = {"POR": "Portero", "DFI": "Defensa", "DFD": "Defensa", "LI": "Defensa", "LD": "Defensa",
          "MI": "Medio", "MC": "Medio", "MD": "Medio", "EI": "Delantero", "DC": "Delantero", "ED": "Delantero"}

# Selecciones que heredan los registros de una predecesora (como en sus propias páginas de Wikipedia)
PREDECESORAS = {
    "Russia national football team": ["Soviet Union national football team"],
    "Serbia national football team": ["Yugoslavia national football team", "Serbia and Montenegro national football team"],
    "Czech Republic national football team": ["Czechoslovakia national football team"],
    "DR Congo national football team": [],
}

ATRIBUTOS = ["agilidad", "agresividad", "anticipacion", "compostura", "concentracion", "control_balon",
             "fuerza_disparo", "fuerza_fisica", "juego_aereo", "precision_pase", "precision_tiro", "regate",
             "resistencia", "velocidad", "vision_juego"]
NIVEL_LEYENDA = 80.0
ESTADO_INICIAL = 80.0              # moral y forma_actual: también 80 (pesan en el overall; el motor no las usa en duelos)
CONTADORES = ["goles", "goles_temp", "botin", "estrella", "faltas", "faltas_temp", "amarilla", "amarilla_temp", "roja",
              "roja_temp", "lesiones", "titular", "juegos_jugados", "asistencias", "asistencias_temp", "atajadas",
              "atajadas_penales", "faltas_recibidas", "recuperaciones", "tiros_desviados", "tiros_puerta",
              "goles_corner", "goles_tiro_libre"]


# ---------------------------------------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------------------------------------
def _sparql(consulta: str) -> dict:
    ultimo = None
    for intento in range(6):
        try:
            req = urllib.request.Request(WDQS + urllib.parse.urlencode({"query": consulta, "format": "json"}), headers=AGENTE)
            datos = json.load(urllib.request.urlopen(req, timeout=90, context=AR._ctx()))
            time.sleep(PAUSA_WD)
            return datos
        except Exception as e:
            ultimo = e
            espera = 5 * (intento + 1)
            if hasattr(e, "headers") and e.headers.get("Retry-After"):
                espera = int(e.headers.get("Retry-After"))
            time.sleep(min(espera, 60))
    raise RuntimeError(f"Wikidata no respondió: {ultimo}")


def _consulta_equipo(qid: str) -> str:
    return f"""SELECT ?p ?en ?es ?nac ?sl ?art (MIN(?ini) AS ?desde) (MAX(?fin) AS ?hasta) (MAX(?caps) AS ?pj)
 (MAX(?gol) AS ?gl) (GROUP_CONCAT(DISTINCT ?posL; separator="/") AS ?pos) WHERE {{
 ?p p:P54 ?st . ?st ps:P54 wd:{qid} .
 OPTIONAL {{ ?st pq:P580 ?ini }} OPTIONAL {{ ?st pq:P582 ?fin }} OPTIONAL {{ ?st pq:P1350 ?caps }} OPTIONAL {{ ?st pq:P1351 ?gol }}
 ?p wikibase:sitelinks ?sl .
 OPTIONAL {{ ?p wdt:P569 ?nac }}
 OPTIONAL {{ ?p wdt:P413 ?po . ?po rdfs:label ?posL FILTER(lang(?posL)="en") }}
 OPTIONAL {{ ?p rdfs:label ?en FILTER(lang(?en)="en") }} OPTIONAL {{ ?p rdfs:label ?es FILTER(lang(?es)="es") }}
 OPTIONAL {{ ?art schema:about ?p ; schema:isPartOf <https://en.wikipedia.org/> }}
}} GROUP BY ?p ?en ?es ?nac ?sl ?art ORDER BY DESC(?sl) LIMIT {CANDIDATOS_POR_PAIS}"""


def _qids(titulos: List[str]) -> Dict[str, str]:
    """{título de Wikipedia: QID de Wikidata}."""
    salida = {}
    for i in range(0, len(titulos), 50):
        lote = titulos[i:i + 50]
        datos = AR._api({"action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "titles": "|".join(lote),
                         "redirects": 1, "formatversion": 2})
        q = datos.get("query", {})
        alias = {}
        for tipo in ("normalized", "redirects"):
            for r in q.get(tipo, []):
                alias[r["to"]] = alias.get(r["from"], r["from"])
        for p in q.get("pages", []):
            qid = (p.get("pageprops") or {}).get("wikibase_item")
            original = p["title"]
            while original in alias:
                original = alias[original]
            if qid:
                salida[original] = qid
                salida[p["title"]] = qid
    return salida


def _año(valor: str) -> Optional[int]:
    return int(valor[:4]) if re.match(r"\d{4}-", valor or "") else None


def _entero(valor: str) -> int:
    """Número de Wikidata; los "valor desconocido" llegan como URL (genid) y cuentan como 0."""
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return 0


def _fila(b: dict) -> dict:
    g = lambda k: b.get(k, {}).get("value", "")
    nac = g("nac")
    art = g("art")
    return {
        "qid": g("p").rsplit("/", 1)[-1],
        # nombre común: el título del artículo en inglés sin la aclaración ("Zico (footballer)" -> "Zico");
        # si no hay artículo, la etiqueta en español o en inglés
        "nombre": (re.sub(r"\s*\(.*?\)\s*$", "", urllib.parse.unquote(art.rsplit("/", 1)[-1]).replace("_", " ")) if art else "")
                  or g("es") or g("en"),
        "nombre_en": g("en"),
        "nac": [int(nac[:4]), int(nac[5:7]), int(nac[8:10])] if re.match(r"\d{4}-\d{2}-\d{2}", nac) else None,
        "fama": int(g("sl") or 0),
        "enlace": urllib.parse.unquote(art.rsplit("/", 1)[-1]).replace("_", " ") if art else None,
        "desde": _año(g("desde")), "hasta": _año(g("hasta")),
        "pj": _entero(g("pj")), "goles": _entero(g("gl")),
        "pos_wd": g("pos"),
    }


def descargar(cache: str, solo: Optional[List[str]] = None) -> None:
    planteles = json.load(open(os.path.join(cache, "planteles.json")))
    archivo = os.path.join(cache, "leyendas.json")
    datos = json.load(open(archivo)) if os.path.exists(archivo) else {}
    titulos = {k: v.get("titulo") for k, v in planteles.items() if v.get("titulo")}
    todos = sorted(set(titulos.values()) | {t for ts in PREDECESORAS.values() for t in ts})
    qids = _qids(todos)
    for clave, info in sorted(planteles.items(), key=lambda kv: int(kv[0])):
        if solo and info["pais"] not in solo:
            continue
        if clave in datos and not solo:
            continue
        titulo = titulos.get(clave)
        equipos = [titulo] + PREDECESORAS.get(titulo, []) if titulo else []
        candidatos: Dict[str, dict] = {}
        for t in equipos:
            qid = qids.get(t)
            if not qid:
                continue
            for b in _sparql(_consulta_equipo(qid))["results"]["bindings"]:
                f = _fila(b)
                if not f["nombre"]:
                    continue
                previo = candidatos.get(f["qid"])
                if previo:   # jugó en la selección y en su predecesora: se suman
                    previo["pj"] += f["pj"]
                    previo["goles"] += f["goles"]
                    previo["desde"] = min(x for x in (previo["desde"], f["desde"]) if x) if (previo["desde"] or f["desde"]) else None
                    previo["hasta"] = max(x for x in (previo["hasta"], f["hasta"]) if x) if (previo["hasta"] or f["hasta"]) else None
                else:
                    candidatos[f["qid"]] = f
        if not candidatos and titulo and "men's" not in titulo:
            # algunas páginas pasaron a ser generales (p. ej. "Sweden national football team" ahora cubre
            # masculina y femenina, con otro QID): se prueba la variante "men's"
            alt = titulo.replace(" national ", " men's national ", 1)
            qid = _qids([alt]).get(alt)
            if qid:
                for b in _sparql(_consulta_equipo(qid))["results"]["bindings"]:
                    f = _fila(b)
                    candidatos.setdefault(f["qid"], f)
        lista = sorted(candidatos.values(), key=lambda c: -_puntaje(c))
        fichas = AR._posiciones_fichas([c["enlace"] for c in lista[:FICHAS_POR_PAIS] if c.get("enlace")])
        for c in lista:
            c["ficha"] = fichas.get(c.get("enlace"))
        datos[clave] = {"pais": info["pais"], "titulo": titulo, "equipos": equipos, "candidatos": lista,
                        "descargado": datetime.now().isoformat(timespec="seconds")}
        print(f"{info['pais']:28s} {len(lista):4d} candidatos · {len(fichas)} fichas", flush=True)
        json.dump(datos, open(archivo, "w"), ensure_ascii=False)


# ---------------------------------------------------------------------------------------------------------
# Selección
# ---------------------------------------------------------------------------------------------------------
def _puntaje(c: dict) -> float:
    """Fama mundial (log de wikis con artículo) + trayectoria con la selección (log de partidos)."""
    return math.log1p(c.get("fama") or 0) * 1.0 + math.log1p(c.get("pj") or 0) * 0.6


def activo(c: dict, hoy: date) -> bool:
    """¿Sigue jugando para su selección? (sin fin de etapa y etapa reciente, o etapa que termina este año o después)."""
    if c.get("hasta") and c["hasta"] >= hoy.year - 1:
        return True
    if not c.get("hasta"):
        nac = (c.get("nac") or [None])[0]
        if (c.get("desde") or 0) >= hoy.year - 16 or (nac and nac >= hoy.year - 40):
            return True
    return False


def _lugares(c: dict) -> List[str]:
    """Posiciones posibles en orden de preferencia: ficha de Wikipedia, si no la de Wikidata."""
    lugares = AR._lugares_por_ficha(c.get("ficha")) or AR._lugares_por_ficha(c.get("pos_wd"))
    return [l for l in lugares if l in POSICION_ID]


def _es_arquero(c: dict) -> bool:
    lugares = _lugares(c)
    return bool(lugares) and lugares[0] == "POR"


def edad_plenitud(c: dict) -> int:
    arquero = _es_arquero(c)
    if c.get("origen") == "inventada":   # ficticia: edad fija por nombre (determinística)
        rng = random.Random(c["nombre"])
        return rng.randint(26, 33) if arquero else rng.randint(24, 31)
    nac = (c.get("nac") or [None])[0]
    desde, hasta = c.get("desde"), c.get("hasta")
    if nac and (desde or hasta):
        medio = ((desde or hasta) + (hasta or desde)) / 2
        edad = int(round(medio - nac))
    else:
        edad = 29 if arquero else 27
    return max(26, min(33, edad)) if arquero else max(24, min(31, edad))


def elegir_once(candidatos: List[dict], curadas: Dict[str, str]) -> Dict[str, dict]:
    """{sigla: candidato} -- primero las curadas (por nombre o QID), después las pasadas automáticas."""
    elegidos: Dict[str, dict] = {}
    usados = set()
    indice = {}
    for c in candidatos:
        for k in (c["qid"], AR._normalizar(c["nombre"]), AR._normalizar(c.get("nombre_en") or ""), AR._normalizar(c.get("enlace") or "")):
            if k:
                indice.setdefault(k, c)
    for sigla, nombre in (curadas or {}).items():
        c = indice.get(nombre) or indice.get(AR._normalizar(nombre))
        if c and sigla in POSICION_ID and c["qid"] not in usados:
            elegidos[sigla] = {**c, "origen": "curada"}
            usados.add(c["qid"])

    orden = sorted([c for c in candidatos if c["qid"] not in usados and _lugares(c)], key=lambda c: -_puntaje(c))

    def pasada(opciones_de):
        for c in orden:
            if c["qid"] in usados:
                continue
            for sigla in opciones_de(c):
                if sigla not in elegidos:
                    elegidos[sigla] = {**c, "origen": "auto"}
                    usados.add(c["qid"])
                    break

    # Por TALLA: de mayor a menor puntaje, cada uno toma la mejor posición libre de su ficha y, si no hay,
    # una de su misma línea (así un Ronaldo no queda afuera porque Pelé ocupó el 9); recién al final se
    # completan huecos con jugadores de campo de otra línea.
    pasada(lambda c: _lugares(c) + [s for s in SIGLAS if SECTOR[s] == SECTOR[_lugares(c)[0]] and s not in _lugares(c)])
    pasada(lambda c: [s for s in SIGLAS if s != "POR"] if not _es_arquero(c) else [])
    return elegidos


def calcular(cache: str, solo: Optional[List[str]] = None, hoy: Optional[date] = None):
    """[(pais_id, pais, {sigla: leyenda}, descartados)] con las exclusiones aplicadas."""
    hoy = hoy or date.today()
    db = AR._db()
    datos = json.load(open(os.path.join(cache, "leyendas.json")))
    planteles = json.load(open(os.path.join(cache, "planteles.json")))
    curadas = json.load(open(ARCHIVO_CURADAS)) if os.path.exists(ARCHIVO_CURADAS) else {}
    curadas.pop("_comentario", None)
    inventadas = json.load(open(ARCHIVO_INVENTADAS)) if os.path.exists(ARCHIVO_INVENTADAS) else {}
    inventadas.pop("_comentario", None)
    # convocados actuales: los del plantel descargado y los que ya están en la base
    actuales: Dict[str, set] = {}
    for clave, info in planteles.items():
        actuales[clave] = {AR._normalizar(j["nombre"]) for j in info.get("jugadores") or []}
    for j in db["jugadores"].find({"leyenda": {"$ne": True}}, {"pais_id": 1, "nombre": 1}):
        actuales.setdefault(str(j["pais_id"]), set()).add(AR._normalizar(j.get("nombre")))
    # cada persona, leyenda de UNA selección: la de más partidos (a igualdad, la primera en orden de id)
    hogar: Dict[str, tuple] = {}
    for clave, info in datos.items():
        for c in info["candidatos"]:
            mejor = hogar.get(c["qid"])
            if not mejor or c["pj"] > mejor[1]:
                hogar[c["qid"]] = (clave, c["pj"])
    salida = []
    for clave, info in sorted(datos.items(), key=lambda kv: int(kv[0])):
        if solo and info["pais"] not in solo:
            continue
        validos, descartados = [], []
        for c in info["candidatos"]:
            motivo = None
            if hogar.get(c["qid"], (clave,))[0] != clave:
                motivo = f"leyenda de otra selección ({datos[hogar[c['qid']][0]]['pais']})"
            elif activo(c, hoy):
                motivo = "sigue en actividad"
            elif {AR._normalizar(c["nombre"]), AR._normalizar(c.get("nombre_en") or "")} & actuales.get(clave, set()):
                motivo = "está en el plantel actual"
            (descartados if motivo else validos).append(c if not motivo else {**c, "motivo": motivo})
        once = elegir_once(validos, curadas.get(info["pais"]) or {})
        # Lugares vacíos: leyenda FICTICIA (nombre inspirado en famosos no futbolistas del país)
        usados = {AR._normalizar(c["nombre"]) for c in once.values()} | actuales.get(clave, set())
        for sigla, inv in (inventadas.get(info["pais"]) or {}).items():
            if sigla in once or sigla not in POSICION_ID or AR._normalizar(inv["nombre"]) in usados:
                continue
            once[sigla] = {"qid": f"ficticia:{clave}:{sigla}", "nombre": inv["nombre"], "nombre_en": inv["nombre"],
                           "nac": None, "fama": 0, "pj": 0, "goles": 0, "desde": None, "hasta": None, "enlace": None,
                           "ficha": "Goalkeeper" if sigla == "POR" else None, "pos_wd": "", "origen": "inventada",
                           "inspirado_en": inv.get("inspirado_en")}
        # curadas que no se pudieron usar (no está en Wikidata con esa selección, sigue activo, etc.)
        for sigla, nombre in (curadas.get(info["pais"]) or {}).items():
            if (once.get(sigla) or {}).get("origen") != "curada":
                motivo = next((d["motivo"] for d in descartados if AR._normalizar(nombre) in
                               (AR._normalizar(d["nombre"]), AR._normalizar(d.get("nombre_en") or ""), d["qid"])), "no encontrado")
                descartados.append({"nombre": nombre, "motivo": f"curada {sigla}: {motivo}", "qid": ""})
        salida.append((int(clave), info["pais"], once, descartados))
    return salida


def muestra(cache: str, solo: Optional[List[str]] = None) -> None:
    resultado = calcular(cache, solo)
    completas = sum(1 for _, _, once, _ in resultado if len(once) == 11)
    huecos = []
    for pais_id, pais, once, descartados in resultado:
        print(f"\n=== {pais} ({len(once)}/11) ===")
        for sigla in SIGLAS:
            c = once.get(sigla)
            if not c:
                print(f"  {sigla:4s} —  (sin candidato)")
                continue
            print(f"  {sigla:4s} {c['nombre'][:30]:30s} {edad_plenitud(c):3d} años · {c['pj']:3d} PJ · fama {c['fama']:3d} · "
                  f"{(c.get('ficha') or c.get('pos_wd') or '?')[:38]:38s} [{c['origen']}]")
        if len(once) < 11:
            huecos.append(f"{pais} ({len(once)}/11)")
        for d in descartados:
            if d.get("motivo", "").startswith("curada"):
                print(f"  ⚠️ {d['nombre']} ({d['motivo']})")
        destacados = [d for d in descartados if d.get("motivo") == "sigue en actividad"][:4]
        if destacados:
            print("  (en actividad, quedan afuera: " + ", ".join(d["nombre"] for d in destacados) + ")")
    print(f"\nSelecciones con el once completo: {completas}/{len(resultado)}")
    if huecos:
        print("Con huecos: " + "; ".join(huecos))


# ---------------------------------------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------------------------------------
def _documento(nuevo_id: int, pais_id: int, pais: str, sigla: str, c: dict, fama_pct: float) -> dict:
    from services.jugadores_service import recalcular_overall, ATRIBUTOS_CLAVE_POR_SECTOR
    rng = random.Random(nuevo_id)
    sector = SECTOR[sigla]
    favoritos = set(ATRIBUTOS_CLAVE_POR_SECTOR.get(sector, []))
    attrs = {}
    for a in ATRIBUTOS:
        base = NIVEL_LEYENDA + (1.5 if a in favoritos else -1.0)
        attrs[a] = round(base + rng.uniform(-0.5, 0.5), 1)
    attrs["control_balón"] = attrs["control_balon"]
    attrs["rendimiento"] = NIVEL_LEYENDA
    attrs["moral"] = ESTADO_INICIAL
    attrs["forma_actual"] = ESTADO_INICIAL
    attrs["overall"] = recalcular_overall(dict(attrs), sector)
    pie = rng.choices(["derecho", "izquierdo", "ambidiestro"], weights=[0.74, 0.20, 0.06])[0]
    if sigla in ("LI", "MI", "EI") and rng.random() < 0.5:
        pie = "izquierdo"
    doc = {
        "id": nuevo_id, "nombre": c["nombre"], "posicion_id": POSICION_ID[sigla], "pais_id": pais_id, "pais": pais,
        "numero": 22 + POSICION_ID[sigla], "edad": edad_plenitud(c), "leyenda": True,
        "fama": round(fama_pct, 4), "wikis": c.get("fama") or 0, "wikidata": None if c.get("origen") == "inventada" else c["qid"],
        **({"ficticia": True, "inspirado_en": c.get("inspirado_en")} if c.get("origen") == "inventada" else {}),
        "trayectoria_seleccion": {"desde": c.get("desde"), "hasta": c.get("hasta"), "partidos": c.get("pj"), "goles": c.get("goles")},
        "pie_habil": pie, "especialista_penales": False, "especialista_tiros_libres": False,
        "estado_animo": "Concentrado", "bonificaciones": None,
        **{k: 0 for k in CONTADORES}, **attrs,
    }
    doc["atributos_base"] = {k: doc[k] for k in list(attrs.keys())}
    return doc


def aplicar(cache: str) -> None:
    db = AR._db()
    if db["jugadores"].count_documents({"leyenda": True}):
        sys.exit("Ya hay leyendas cargadas: --revertir primero si querés volver a generarlas.")
    resultado = calcular(cache)
    todas = [(pais_id, pais, sigla, c) for pais_id, pais, once, _ in resultado for sigla, c in once.items()]
    # fama relativa entre TODAS las leyendas (precio en corporativos): percentil del log de wikis
    orden = sorted(todas, key=lambda t: (t[3].get("fama") or 0, t[3].get("pj") or 0))
    n = max(len(orden) - 1, 1)
    fama_pct = {(t[0], t[2]): i / n for i, t in enumerate(orden)}
    siguiente = (db["jugadores"].find_one(sort=[("id", -1)]) or {"id": 0})["id"] + 1
    docs = []
    for pais_id, pais, sigla, c in sorted(todas, key=lambda t: (t[0], POSICION_ID[t[2]])):
        docs.append(_documento(siguiente, pais_id, pais, sigla, c, fama_pct[(pais_id, sigla)]))
        siguiente += 1
    os.makedirs(os.path.join(RAIZ, "respaldos"), exist_ok=True)
    archivo = os.path.join(RAIZ, "respaldos", f"leyendas_{datetime.now():%Y%m%d_%H%M%S}.json.gz")
    with gzip.open(archivo, "wt", encoding="utf-8") as f:
        json.dump({"ids": [d["id"] for d in docs], "docs": docs}, f, ensure_ascii=False, default=str)
    if docs:
        db["jugadores"].insert_many(docs, ordered=False)
    print(f"Leyendas insertadas: {len(docs)} (ids {docs[0]['id'] if docs else '-'}..{docs[-1]['id'] if docs else '-'})")
    print(f"Respaldo de lo insertado: {archivo}")
    print("Ahora: generar_avatares.py --generar/--subir/--asignar y reiniciar el servidor.")


def revertir() -> None:
    db = AR._db()
    ids = [j["id"] for j in db["jugadores"].find({"leyenda": True}, {"id": 1})]
    if not ids:
        print("No hay leyendas cargadas.")
        return
    albums = db["user_albums"].update_many({"owned_jugadores": {"$in": ids}}, {"$pull": {"owned_jugadores": {"$in": ids}}})
    fantasy = db["fantasy_teams"].count_documents({"lineup": {"$in": ids}})
    contratos = db["corp_contratos"].count_documents({"tipo": "jugador", "ref_id": {"$in": ids}, "activo": True})
    r = db["jugadores"].delete_many({"leyenda": True})
    print(f"Leyendas borradas: {r.deleted_count} · estampas quitadas de {albums.modified_count} álbumes")
    if fantasy or contratos:
        print(f"⚠️ Quedan referencias: {fantasy} Once Ideal y {contratos} contratos de corporativos con leyendas.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache")
    ap.add_argument("--paises", help="lista separada por comas (nombres de 'paises')")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--descargar", action="store_true")
    g.add_argument("--muestra", action="store_true")
    g.add_argument("--aplicar", action="store_true")
    g.add_argument("--revertir", action="store_true")
    a = ap.parse_args()
    solo = [x.strip() for x in a.paises.split(",")] if a.paises else None
    if a.revertir:
        revertir()
    elif not a.cache:
        ap.error("--cache es obligatorio")
    elif a.descargar:
        descargar(a.cache, solo)
    elif a.muestra:
        muestra(a.cache, solo)
    else:
        aplicar(a.cache)
