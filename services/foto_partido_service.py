"""
La foto del partido: una imagen tipo fotografía deportiva del MEJOR MOMENTO de un partido jugado, generada con
Vertex AI (modelo Gemini de imagen; también acepta los 'imagen-*') a pedido del admin desde el resumen (/juegos/{id}) y guardada en el bucket público:

    gs://com-icg-mundial/fotos_juego/<AAAA>/<MM>/<DD>/<TAG>/<marca de tiempo>.jpg (o .png si el modelo devuelve PNG)

Por qué no se manda solo la crónica: con un texto parecido, el modelo cae siempre en la misma composición genérica
("jugador festejando en un estadio") y solo cambia la camiseta. Aquí se arma una ESCENA a partir de la cronología
(services/cronica_service.analizar): cuál es el momento (el gol agónico, el tercero del hat-trick, la atajada, el
último penal de la tanda...), cómo fue la jugada (cabezazo de córner, tiro libre por encima de la barrera, penal...),
los colores reales de cada camiseta (paises.colores), la hora (día, atardecer o noche con reflectores), el clima, cuánta
gente había y el ángulo de cámara. La crónica va al final como contexto, SIN nombres propios: los jugadores son reales
y el modelo no debe (ni puede) dibujar a personas reales identificables.

Cupo: FOTOS_POR_DIA por día (zona FOTOS_ZONA_HORARIA), contado en 'fotos_partido_cupo' con un $inc condicional (si la
generación falla se devuelve el cupo). Cada foto queda en 'fotos_partido' (permanente: restart_mundial no la toca).
"""
import hashlib
import io
import random
import re
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote
from zoneinfo import ZoneInfo

from pymongo import DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from config.settings import (FOTOS_BUCKET, FOTOS_POR_DIA, FOTOS_TAMANO, FOTOS_ZONA_HORARIA, GCP_PROJECT, IMAGENES_PAISES_URL,
                             VERTEX_LOCATION, VERTEX_MODELO_IMAGEN)
from services import cronica_service as CR
from services.juegos_service import db

CARPETA = "fotos_juego"
_cliente = {"genai": None, "gcs": None}
_lock_clientes = threading.Lock()


class ErrorFoto(Exception):
    """Error que se le muestra tal cual al admin (cupo agotado, partido sin jugar, Vertex rechazó el prompt...)."""


# --- Colores: hex de la bandera -> nombre en inglés (el modelo entiende mejor "royal blue" que "#0037a7") ----------
COLORES = [
    ("white", (245, 245, 245)), ("black", (20, 20, 20)), ("red", (200, 20, 30)), ("dark red", (120, 15, 25)),
    ("orange", (240, 120, 20)), ("yellow", (250, 210, 20)), ("gold", (205, 160, 40)), ("green", (0, 135, 60)),
    ("dark green", (0, 80, 40)), ("light green", (120, 200, 90)), ("sky blue", (100, 170, 230)), ("royal blue", (20, 60, 170)),
    ("navy blue", (15, 30, 80)), ("turquoise", (0, 170, 170)), ("purple", (100, 40, 140)), ("maroon", (110, 20, 50)),
    ("grey", (140, 140, 140)), ("pink", (230, 120, 170)), ("brown", (110, 70, 30)),
]


def _nombre_color(hex_: str) -> str:
    h = (hex_ or "").lstrip("#")
    if len(h) != 6:
        return "white"
    rgb = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return min(COLORES, key=lambda c: sum((a - b) ** 2 for a, b in zip(rgb, c[1])))[0]


def _uniforme(pais_id) -> Tuple[str, str]:
    """(color principal, color secundario) de la camiseta, desde los colores reales de la bandera."""
    p = db["paises"].find_one({"id": pais_id}, {"colores": 1}) or {}
    cols = [c for c in sorted(p.get("colores") or [], key=lambda c: -(c.get("area") or 0))]
    nombres = []
    for c in cols:
        n = _nombre_color(c.get("hex"))
        if n not in nombres:
            nombres.append(n)
    nombres += ["white", "black"]
    return nombres[0], nombres[1] if nombres[1] != nombres[0] else nombres[2]


def _uniformes(loc_id, vis_id) -> Dict[str, Tuple[str, str]]:
    """El visitante usa su segundo color si choca con el del local (como un uniforme alternativo)."""
    l, v = _uniforme(loc_id), _uniforme(vis_id)
    if v[0] == l[0] or {v[0], l[0]} <= {"white", "grey"} or {v[0], l[0]} <= {"red", "dark red", "maroon"}:
        v = (v[1], v[0])
    return {"L": l, "V": v}


def _dorsal(pais_id, nombre) -> Optional[int]:
    j = db["jugadores"].find_one({"pais_id": pais_id, "nombre": nombre}, {"numero": 1}) if nombre else None
    return (j or {}).get("numero")


# --- Ambiente: hora, clima, público, cámara -----------------------------------------------------------------------
def _luz(hora: Optional[str]) -> str:
    try:
        h = int((hora or "15:00").split(":")[0])
    except ValueError:
        h = 15
    if h < 12:
        return "late-morning daylight, crisp shadows on the grass"
    if h < 17:
        return "bright afternoon daylight, hard sun and long stand shadows across the pitch"
    if h < 19:
        return "golden-hour light, warm low sun mixed with the first floodlights, orange sky above the stands"
    return "night match under powerful white floodlights, dark sky, glowing pitch, light haze above the crowd"


def _clima(clima: dict) -> str:
    c = (clima or {}).get("condicion") or ""
    if "Lluvia" in c:
        return "heavy rain falling, soaked kits, water spraying off the ball and the boots, puddles reflecting the lights"
    if "Nieve" in c or "Frio" in c or "Frío" in c:
        return "freezing cold, light snow in the air, visible breath, players in long sleeves and gloves"
    if "Calor" in c:
        return "scorching heat, sweat-soaked kits, heat shimmer over the pitch"
    if "Nublado" in c:
        return "overcast grey sky, soft diffused light"
    return "clear weather"


def _publico(aforo: dict, cancha: str) -> str:
    pct = (aforo or {}).get("porcentaje_ocupacion")
    if pct is None:
        return f"a large crowd in the stands of {cancha}"
    if pct >= 85:
        return f"a packed, roaring {cancha}, fans with scarves and flags in the team colors, smoke and confetti"
    if pct >= 55:
        return f"a lively crowd filling most of {cancha}, flags waving"
    if pct >= 30:
        return f"a half-empty {cancha}, scattered groups of fans, empty seats visible in the background"
    return f"a nearly empty {cancha}, echoing stands with a few hundred loyal fans"


# Cámaras de foto deportiva por tipo de momento: se sortean con la semilla del partido + cuántas fotos tiene (así
# volver a generar da otra toma del mismo momento).
CAMARAS = {
    "remate": [
        "shot from behind the goal through the net with a 300mm telephoto lens, ball frozen mid-flight",
        "low angle from pitch level beside the post, 24mm wide lens, grass blades in the foreground",
        "sideline telephoto 400mm at eye level, shallow depth of field, crowd blurred into bokeh",
        "high angle from the stands, 70-200mm, showing the shape of the play and the defenders",
    ],
    "festejo": [
        "tight telephoto 400mm portrait of the celebration, screaming faces, crowd in creamy bokeh",
        "wide 24mm shot at pitch level as teammates pile on, stands erupting behind them",
        "shot from the stands looking down on the celebration by the corner flag, fans leaning over the barrier",
        "motion-blurred panning shot of the scorer sprinting toward the fans, sharp face, streaked background",
    ],
    "atajada": [
        "shot from behind the goal, 300mm, goalkeeper fully stretched in the air, fingertips on the ball",
        "low side angle at the post, 35mm, goalkeeper diving across the frame, turf flying",
        "telephoto from the sideline freezing the save at its peak, ball deflecting off the glove",
    ],
    "drama": [
        "documentary-style telephoto close-up, raw emotion, shallow depth of field",
        "wide establishing shot of the whole stadium at the decisive instant, players small against the stands",
        "low angle 35mm amid the players, tension on every face",
    ],
}

ACCION_GOL = {
    "penal": "a {num}striker in {col} smashing a penalty kick into the corner while the goalkeeper dives the wrong way",
    "tiro_libre": "a {num}player in {col} curling a free kick over the defensive wall into the top corner, the wall jumping in vain",
    "corner": "a {num}player in {col} rising above the defenders to power a header from a corner kick into the net",
}
ACCION_JUGADA = [
    "a {num}striker in {col} firing a low, hard shot past the diving goalkeeper inside the box",
    "a {num}forward in {col} hitting a spectacular volley from the edge of the box, ball flying into the net",
    "a {num}attacker in {col} chipping the ball over the onrushing goalkeeper in a one-on-one",
    "a {num}player in {col} scoring with a diving header at the near post",
    "a {num}winger in {col} cutting inside and curling the ball into the far top corner",
]


def _num(n) -> str:
    return f"number {n} " if n else ""


def _momento(h: dict, juego: dict, rnd: random.Random, u: Dict[str, Tuple[str, str]]) -> dict:
    """El momento a fotografiar: {'tipo': remate/festejo/atajada/drama, 'accion': inglés, 'emocion': inglés,
    'lado': L/V protagonista, 'texto': descripción en español para el pie de foto}."""
    p = h["principal"]
    clave = p.get("clave")
    nom, otro = h["nombre"], {"L": "V", "V": "L"}
    loc, vis = juego.get("equipo_local") or {}, juego.get("equipo_visitante") or {}
    pid = {"L": loc.get("id"), "V": vis.get("id")}
    col = lambda k: f"a {u[k][0]} shirt with {u[k][1]} details"

    def gol(g, festejo: bool, emocion: str, texto: str):
        k = g["lado"]
        n = _num(_dorsal(pid[k], g["autor"]))
        if festejo:
            accion = (f"a {n}player in {col(k)} celebrating the goal he just scored, arms wide open, teammates running "
                      f"to hug him, opponents in {col(otro[k])} slumped on the grass")
        else:
            plantilla = ACCION_GOL.get(g["tipo"]) or rnd.choice(ACCION_JUGADA)
            accion = plantilla.format(num=n, col=col(k)) + f", defenders in {col(otro[k])} too late to block"
        d = g["despues"]
        accion += f", in the {g['min']}th minute{' of stoppage time' if g.get('adic') else ''}, making it {d['L']}-{d['V']}"
        return {"tipo": "festejo" if festejo else "remate", "accion": accion, "emocion": emocion, "lado": k,
                "texto": texto.format(autor=g["autor"], equipo=nom[k], min=CR._mins(g["min"], g.get("adic", 0)))}

    goles = h["goles"]
    decisivo = CR._gol_decisivo(h)
    if clave == "tanda":
        k = p["equipo"]
        ult = h["tanda"][-1] if h["tanda"] else None
        if ult and not ult["gol"]:
            k_ar = otro[ult["lado"]]
            return {"tipo": "atajada", "lado": k_ar, "emocion": "explosion of joy, the shootout is over",
                    "accion": f"the goalkeeper in a bright keeper kit saving the decisive penalty of the shootout, the taker in {col(ult['lado'])} "
                              f"falling to his knees, teammates in {col(k_ar)} sprinting from the halfway line",
                    "texto": f"La atajada que definió la tanda de penales para {nom[k_ar]}"}
        return {"tipo": "festejo", "lado": k, "emocion": "pure euphoria after a penalty shootout",
                "accion": f"players in {col(k)} sprinting from the halfway line to celebrate the winning penalty of the shootout, "
                          f"opponents in {col(otro[k])} crouched in despair",
                "texto": f"El último penal de la tanda: {nom[k]} lo gana desde los doce pasos"}
    if clave in ("agonico", "empate_agonico", "super_sub", "leyenda_decisiva", "ajuste_decisivo") and p.get("gol"):
        return gol(p["gol"], True, "last-minute delirium, disbelief and joy",
                   "{autor} en el {min}: el gol agónico de {equipo}" if clave != "leyenda_decisiva" else "{autor}, leyenda de {equipo}, decide en el {min}")
    if clave == "hat_trick":
        suyos = [g for g in goles if g["autor"] == p["jugador"]]
        g = suyos[2] if len(suyos) >= 3 else suyos[-1]
        r = gol(g, rnd.random() < 0.5, "triumph, a player holding up three fingers", "{autor} completa su hat-trick en el {min}")
        r["accion"] += ", the player raising three fingers to the crowd" if r["tipo"] == "festejo" else ""
        return r
    if clave in ("remontada", "remontada_epica", "sorpresa", "minima", "clara", "con_diez") and decisivo:
        emocion = {"remontada_epica": "an epic comeback completed, tears and screams", "sorpresa": "a historic upset, the underdog's fans in tears",
                   "con_diez": "heroic, ten men holding on"}.get(clave, "the winning goal, intense joy")
        return gol(decisivo, clave in ("remontada_epica", "sorpresa") or rnd.random() < 0.4, emocion,
                   "{autor} marca el gol del triunfo de {equipo} en el {min}")
    if clave in ("paliza", "goleada") and goles:
        k = p["equipo"]
        suyos = [g for g in goles if g["lado"] == k]
        return gol(suyos[-1], rnd.random() < 0.5, "a dominant team enjoying a rout", "{autor} pone otro más para {equipo} en el {min}, en una goleada")
    if clave in ("rescate", "empate_loco", "empate") and goles:
        return gol(goles[-1], rnd.random() < 0.5, "relief and fury, a match that swung back and forth",
                   "{autor} iguala para {equipo} en el {min}")
    if clave == "arquero_figura":
        k = p["lado"]
        return {"tipo": "atajada", "lado": k, "emocion": "a goalkeeper single-handedly holding the result",
                "accion": f"the goalkeeper of the team in {col(k)} (wearing a contrasting keeper kit) making a spectacular flying save, "
                          f"an attacker in {col(otro[k])} with hands on his head",
                "texto": f"{p['arquero']}, figura con {p['n']} atajadas para {nom[k]}"}
    if clave == "var_decisivo":
        k = p["lado"]
        return {"tipo": "drama", "lado": k, "emocion": "tension and outrage while the decision is reviewed",
                "accion": f"the referee in black at the pitch-side VAR monitor making the square TV signal, players in {col(k)} protesting "
                          f"angrily, players in {col(otro[k])} waiting with hands on hips",
                "texto": f"El VAR le anula un gol a {nom[k]} y cambia el partido"}
    if clave in ("expulsion_pesa", "roja_empate") and p.get("roja"):
        r = p["roja"]
        k = r["lado"]
        return {"tipo": "drama", "lado": k, "emocion": "anger and disbelief",
                "accion": f"the referee in black holding a red card high above a player in {col(k)}, teammates surrounding the referee",
                "texto": f"La roja a {r['jugador']} ({nom[k]}) en el {CR._mins(r['min'], r.get('adic', 0))}"}
    if clave == "cero_cero":
        k = "L" if h["atajadas"]["L"] >= h["atajadas"]["V"] else "V"
        return {"tipo": "atajada", "lado": k, "emocion": "a tense, goalless battle",
                "accion": f"the goalkeeper of the team in {col(k)} punching the ball away in a crowded box, players in {col(otro[k])} jumping for the header",
                "texto": f"Un 0-0 de arcos cerrados: el arquero de {nom[k]} salva su valla"}
    if goles:   # cualquier otro partido con goles: el gol del triunfo o el primero
        g = decisivo or goles[0]
        return gol(g, rnd.random() < 0.4, "the turning point of the match", "{autor} marca para {equipo} en el {min}")
    k = rnd.choice("LV")
    return {"tipo": "drama", "lado": k, "emocion": "fierce competition",
            "accion": f"a fierce midfield duel, a player in {col(k)} sliding in to win the ball from a player in {col(otro[k])}",
            "texto": f"El duelo en el medio entre {nom['L']} y {nom['V']}"}


# --- La crónica sin nombres propios ------------------------------------------------------------------------------
def _sin_nombres(texto: str, cronica: dict, h: dict) -> str:
    res = cronica.get("resaltar") or {}
    reemplazos = [(n, "un jugador") for n in res.get("jugadores") or []] + [(n, "el árbitro") for n in res.get("arbitros") or []]
    reemplazos += [(n, "el técnico") for n in (h.get("dt") or {}).values() if n]
    for n, r in sorted(reemplazos, key=lambda x: -len(x[0])):
        texto = texto.replace(n, r)
    return re.sub(r"\s+", " ", texto).strip()


def _contexto_cronica(juego: dict, h: dict) -> str:
    cronica = (juego.get("resultado") or {}).get("cronica") or {}
    if not cronica:
        return ""
    partes = [cronica.get("titular") or ""] + (cronica.get("parrafos") or [])[:3]
    return _sin_nombres(" ".join(partes), cronica, h)[:900]


# --- Prompt ------------------------------------------------------------------------------------------------------
def armar_prompt(juego: dict, variante: int = 0) -> dict:
    """{'prompt', 'momento' (pie de foto en español), 'semilla'} para un partido jugado. 'variante' = cuántas fotos ya
    tiene el partido: cambia la cámara y, si hay opciones, la jugada (volver a generar no repite la misma toma)."""
    h = CR.analizar(juego)
    semilla = int(hashlib.sha256(f"{juego['_id']}:{variante}".encode()).hexdigest()[:8], 16)
    rnd = random.Random(semilla)
    u = _uniformes((juego.get("equipo_local") or {}).get("id"), (juego.get("equipo_visitante") or {}).get("id"))
    m = _momento(h, juego, rnd, u)
    ub = juego.get("ubicacion") or {}
    # Dónde se jugó: estadio, ciudad y país de la sede (juegos.ubicacion)
    lugar = ", ".join(x for x in (ub.get("estadio"), ub.get("nombre"), ub.get("pais")) if x) or "a national stadium"
    loc, vis = (juego.get("equipo_local") or {}).get("nombre"), (juego.get("equipo_visitante") or {}).get("nombre")
    marcador = f"{h['gl']}-{h['gv']}" + (f" ({h['pl']}-{h['pv']} on penalties)" if h["hubo_tanda"] and h["pl"] is not None else "")
    camara = rnd.choice(CAMARAS[m["tipo"]])
    cronica = _contexto_cronica(juego, h)

    prompt = (
        f"Award-winning professional sports photograph, photojournalism, shot on a full-frame DSLR. "
        f"The defining moment of an international football (soccer) match between the national teams of {loc} and {vis} "
        f"({h['fase']}, final score {marcador}). "
        f"MOMENT: {m['accion']}. Mood: {m['emocion']}. "
        f"KITS: {loc} wear {u['L'][0]} shirts with {u['L'][1]} details; {vis} wear {u['V'][0]} shirts with {u['V'][1]} details. "
        f"LOCATION: {lugar}. The stadium architecture, the skyline or landscape glimpsed beyond the stands and the fans "
        f"should feel typical of {ub.get('nombre') or 'the host city'}, {ub.get('pais') or 'the host country'}. "
        f"SETTING: {_publico(juego.get('aforo'), 'the stadium')}; {_luz(juego.get('hora'))}; {_clima(juego.get('clima'))}. "
        f"CAMERA: {camara}. "
        f"Photorealistic, natural skin and fabric detail, motion and sweat, dramatic but realistic color grading, 16:9. "
        f"All players are fictional, anonymous athletes, not resembling any real person. "
        f"No text, no letters, no scoreboard, no logos, no sponsor brands, no badges, no watermark."
    )
    if cronica:
        prompt += f" Match report for context (Spanish, names removed): {cronica}"
    return {"prompt": prompt, "momento": m["texto"], "tipo": m["tipo"], "semilla": semilla}


# --- Cupo diario --------------------------------------------------------------------------------------------------
def _hoy() -> str:
    return datetime.now(ZoneInfo(FOTOS_ZONA_HORARIA)).strftime("%Y-%m-%d")


def cupo_restante() -> int:
    d = db["fotos_partido_cupo"].find_one({"_id": _hoy()}) or {}
    return max(0, FOTOS_POR_DIA - int(d.get("n") or 0))


def _reservar_cupo() -> str:
    """$inc condicional: solo suma si quedan fotos hoy. Con el cupo lleno el filtro no encuentra el documento, el
    upsert intenta crear uno con el mismo _id y falla por clave duplicada = no hay cupo."""
    dia = _hoy()
    try:
        db["fotos_partido_cupo"].find_one_and_update({"_id": dia, "n": {"$lt": FOTOS_POR_DIA}}, {"$inc": {"n": 1}},
                                                      upsert=True, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError:
        raise ErrorFoto(f"Ya se generaron las {FOTOS_POR_DIA} fotos de hoy. El cupo se renueva a la medianoche.")
    return dia


def _devolver_cupo(dia: str):
    db["fotos_partido_cupo"].update_one({"_id": dia, "n": {"$gt": 0}}, {"$inc": {"n": -1}})


# --- Vertex AI y Cloud Storage --------------------------------------------------------------------------------------
def _clientes():
    with _lock_clientes:
        if _cliente["genai"] is None:
            from google import genai
            from google.cloud import storage
            _cliente["genai"] = genai.Client(vertexai=True, project=GCP_PROJECT, location=VERTEX_LOCATION)
            _cliente["gcs"] = storage.Client(project=GCP_PROJECT)
    return _cliente["genai"], _cliente["gcs"]


EXTENSION = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _generar_imagen(prompt: str) -> Tuple[bytes, str]:
    """(bytes, mime) de la imagen. Los modelos 'imagen-*' usan generate_images; los Gemini de imagen
    ('gemini-*-image', los que hoy tiene el proyecto) usan generate_content pidiendo una IMAGEN como respuesta."""
    if VERTEX_MODELO_IMAGEN.startswith("imagen"):
        return _generar_con_imagen(prompt)
    return _generar_con_gemini(prompt)


def _generar_con_gemini(prompt: str) -> Tuple[bytes, str]:
    from google.genai import types
    genai_cli, _ = _clientes()
    completa = types.ImageConfig(aspect_ratio="16:9", image_size=FOTOS_TAMANO, output_mime_type="image/jpeg",
                                 output_compression_quality=88, prominent_people=types.ProminentPeople.BLOCK_PROMINENT_PEOPLE)
    intentos = [(["IMAGE"], completa), (["TEXT", "IMAGE"], types.ImageConfig(aspect_ratio="16:9", image_size=FOTOS_TAMANO))]
    r = None
    for modalidades, imagen_cfg in intentos:
        try:
            r = genai_cli.models.generate_content(
                model=VERTEX_MODELO_IMAGEN, contents=prompt,
                config=types.GenerateContentConfig(response_modalities=modalidades, image_config=imagen_cfg, candidate_count=1))
            break
        except Exception as e:
            # 400 por una opción que este modelo no acepta (formato, calidad, celebridades): se reintenta con lo mínimo.
            # Un pedido rechazado con 400 no genera imagen ni se cobra.
            if "400" in str(e) and imagen_cfg is completa:
                print(f"[foto_partido] el modelo no aceptó la configuración completa, reintento simple: {str(e)[:200]}")
                continue
            raise
    cand = (r.candidates or [None])[0] if r else None
    for parte in ((cand.content.parts if cand and cand.content else None) or []):
        if parte.inline_data and parte.inline_data.data:
            return parte.inline_data.data, parte.inline_data.mime_type or "image/png"
    motivo = getattr(cand, "finish_reason", None) if cand else (getattr(r.prompt_feedback, "block_reason", None) if r and r.prompt_feedback else None)
    texto = " ".join(p.text for p in ((cand.content.parts if cand and cand.content else None) or []) if getattr(p, "text", None))[:200]
    raise ErrorFoto("Vertex AI no devolvió imagen" + (f" (motivo: {motivo})" if motivo else "") + (f": {texto}" if texto else "") + ". No se descontó del cupo.")


def _generar_con_imagen(prompt: str) -> Tuple[bytes, str]:
    from google.genai import types
    genai_cli, _ = _clientes()
    r = genai_cli.models.generate_images(
        model=VERTEX_MODELO_IMAGEN, prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1, aspect_ratio="16:9", output_mime_type="image/jpeg", output_compression_quality=88,
            person_generation=types.PersonGeneration.ALLOW_ADULT, enhance_prompt=False, include_rai_reason=True,
        ),
    )
    imgs = r.generated_images or []
    if not imgs or not imgs[0].image or not imgs[0].image.image_bytes:
        motivo = imgs[0].rai_filtered_reason if imgs else None
        raise ErrorFoto("Vertex AI no devolvió imagen" + (f" (filtro de seguridad: {motivo})" if motivo else "") + ". No se descontó del cupo.")
    return imgs[0].image.image_bytes, "image/jpeg"


def ruta_foto(juego: dict, ahora: datetime, extension: str = "jpg") -> str:
    a, m, d = (juego.get("fecha") or "0000-00-00")[:10].split("-")
    tag = re.sub(r"[^A-Za-z0-9]", "", juego.get("tag") or "") or str(juego["_id"])
    return f"{CARPETA}/{a}/{m}/{d}/{tag}/{ahora.strftime('%Y%m%d-%H%M%S')}.{extension}"


def url_publica(ruta: str) -> str:
    return f"{IMAGENES_PAISES_URL}/{quote(ruta)}"


def _subir(ruta: str, datos: bytes, mime: str = "image/jpeg"):
    _, gcs = _clientes()
    blob = gcs.bucket(FOTOS_BUCKET).blob(ruta)
    blob.cache_control = "public, max-age=31536000, immutable"   # nombre único por foto: nunca cambia
    blob.upload_from_file(io.BytesIO(datos), content_type=mime)


# --- API del servicio ---------------------------------------------------------------------------------------------
def fotos_del_partido(juego_id: str) -> List[dict]:
    fotos = list(db["fotos_partido"].find({"juego_id": juego_id}, {"prompt": 0}).sort("creada_en", DESCENDING))
    for f in fotos:
        f["_id"] = str(f["_id"])
        f["url"] = url_publica(f["ruta"])
    return fotos


def generar_foto(juego: dict, usuario: dict) -> dict:
    """Genera, sube y registra una foto. Lanza ErrorFoto con un mensaje para el admin si algo no se puede."""
    if not juego or not juego.get("resultado"):
        raise ErrorFoto("El partido todavía no se jugó.")
    if (juego.get("transmision") or {}).get("estado") == "in_progress":
        raise ErrorFoto("El partido se está transmitiendo: la foto se puede generar cuando termine.")
    variante = db["fotos_partido"].count_documents({"juego_id": str(juego["_id"])})
    p = armar_prompt(juego, variante)
    dia = _reservar_cupo()
    try:
        datos, mime = _generar_imagen(p["prompt"])
        ahora = datetime.now(ZoneInfo(FOTOS_ZONA_HORARIA))
        ruta = ruta_foto(juego, ahora, EXTENSION.get(mime, "png"))
        _subir(ruta, datos, mime)
    except ErrorFoto:
        _devolver_cupo(dia)
        raise
    except Exception as e:
        _devolver_cupo(dia)
        texto, tipo = str(e), type(e).__name__
        print(f"[foto_partido] {tipo}: {texto[:500]}")   # el error original, para el log del servidor
        if tipo in ("DefaultCredentialsError", "RefreshError") or "credentials" in texto.lower() or "reauth" in texto.lower():
            with _lock_clientes:   # descartar el cliente: al iniciar sesión, el próximo intento lo crea de nuevo sin reiniciar
                _cliente["genai"] = _cliente["gcs"] = None
            if tipo == "RefreshError" or "reauth" in texto.lower():
                raise ErrorFoto("La sesión de Google Cloud venció (en local: gcloud auth application-default login de nuevo).")
            raise ErrorFoto("No hay credenciales de Google Cloud en el servidor (en local: gcloud auth application-default login).")
        if "PERMISSION_DENIED" in texto or "403" in texto:
            raise ErrorFoto("Google Cloud negó el permiso (Vertex AI o el bucket). Revisa los roles de la cuenta de servicio.")
        raise ErrorFoto(f"No se pudo generar la foto: {texto[:300]}")
    doc = {"juego_id": str(juego["_id"]), "tag": juego.get("tag"), "fecha_juego": juego.get("fecha"), "ruta": ruta,
           "momento": p["momento"], "tipo": p["tipo"], "prompt": p["prompt"], "modelo": VERTEX_MODELO_IMAGEN,
           "creada_en": ahora.replace(tzinfo=None), "dia_cupo": dia, "usuario": usuario.get("username") or usuario.get("nombre") or str(usuario.get("_id"))}
    db["fotos_partido"].insert_one(doc)
    return {"url": url_publica(ruta), "momento": p["momento"], "tipo": p["tipo"], "ruta": ruta, "restantes": cupo_restante()}
