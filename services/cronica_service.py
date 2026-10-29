"""
Crónica de cada partido jugado, escrita como lo haría un cronista (mezcla de periodista de diario y relator de radio)
a partir de la CRONOLOGÍA real del partido (resultado.eventos), no solo del marcador final.

  1. analizar(juego)   lee el partido en orden: cada gol con su contexto (abre, empata, da vuelta, sentencia...),
                       rojas, VAR, atajadas, cambios, leyendas, desgaste, tanda de penales; y detecta las HISTORIAS
                       del partido con prioridad (remontada, gol agónico, goleada, hat-trick, sorpresa, penales...).
  2. redactar(h)       arma la nota: titular + entrada + primer tiempo + segundo tiempo (+ alargue/penales) +
                       figuras y números + cierre con lo que significa el resultado, más el post corto del feed FIFAV.
Cada bloque tiene varias plantillas y la elección usa como semilla el id del partido: el mismo partido siempre se
cuenta igual, dos partidos parecidos se cuentan distinto.

Se guarda en resultado.cronica = {version, titular, parrafos, post, historia, generada_en}. `asegurar_cronica(juego)`
la genera AL LEER si falta o es de una VERSION anterior (subir VERSION regenera todas al consultarlas); nunca durante
una transmisión en vivo (spoiler). generar_cronicas.py la genera de una vez para todos los partidos jugados.
"""
import random
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional

import certifi
from pymongo import MongoClient

from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database("mundial")

VERSION = 7   # 6: planteamiento de los DT (formaciones v2); 7: especialidades de los jugadores
TIPOS_GOL = ("⚽ GOL", "⚽ GOL DE TIRO LIBRE", "⚽ GOL DE CÓRNER", "⚽ GOL DE PENAL")
COMPETICION = {1: "las Eliminatorias de la UEFA", 2: "las Eliminatorias de la CONMEBOL", 3: "las Eliminatorias de la CONCACAF",
               4: "las Eliminatorias de la CAF", 5: "las Eliminatorias de la OFC", 6: "las Eliminatorias de la AFC"}
SIGUIENTE_FASE = {8: "los octavos de final", 9: "los cuartos de final", 10: "las semifinales", 11: "la gran final"}

_nombres_fases: Optional[Dict[int, str]] = None
_leyendas_por_pais: Dict[int, set] = {}
_rigor_por_arbitro: Optional[Dict[str, float]] = None
_perfil_var: Optional[Dict[str, dict]] = None


def _rigor(nombre) -> Optional[float]:
    global _rigor_por_arbitro
    if _rigor_por_arbitro is None:
        _rigor_por_arbitro = {a["nombre"]: a["rigor"] for a in db["arbitros"].find({"rigor": {"$exists": True}}, {"nombre": 1, "rigor": 1})}
    return _rigor_por_arbitro.get(nombre)


def _perfil(nombre_var) -> dict:
    """Personalidad del VAR (asignar_perfil_var.py): etiquetas de intervención y severidad."""
    global _perfil_var
    if _perfil_var is None:
        _perfil_var = {a["nombre"]: a for a in db["arbitros"].find({"var_intervencion_etiqueta": {"$exists": True}},
                                                                   {"nombre": 1, "var_intervencion_etiqueta": 1, "var_severidad_etiqueta": 1})}
    return _perfil_var.get(nombre_var) or {}


def _fase(fid) -> str:
    global _nombres_fases
    if _nombres_fases is None:
        _nombres_fases = {f["id"]: f.get("nombre", "") for f in db["fases"].find({}, {"id": 1, "nombre": 1})}
    return _nombres_fases.get(fid, "")


def _leyendas(pais_id) -> set:
    if pais_id not in _leyendas_por_pais:
        _leyendas_por_pais[pais_id] = {j["nombre"] for j in db["jugadores"].find({"pais_id": pais_id, "leyenda": True}, {"nombre": 1})}
    return _leyendas_por_pais[pais_id]


# =================================================================================================================
# 1. ANÁLISIS
# =================================================================================================================
def analizar(juego: dict) -> dict:
    res = juego.get("resultado") or {}
    loc, vis = juego.get("equipo_local") or {}, juego.get("equipo_visitante") or {}
    nl, nv = res.get("local") or loc.get("nombre", "Local"), res.get("visitante") or vis.get("nombre", "Visitante")
    lado = lambda eq: "L" if eq == nl else ("V" if eq == nv else None)
    nombre = {"L": nl, "V": nv}
    otro = {"L": "V", "V": "L"}
    leyendas = {"L": _leyendas(loc.get("id")), "V": _leyendas(vis.get("id"))}

    goles, rojas, var, cambios, tanda, desgaste, lesiones = [], [], [], [], [], [], []
    atajadas, porteros, amarillas, errores, desviados = Counter(), defaultdict(Counter), Counter(), Counter(), Counter()
    marcador = {"L": 0, "V": 0}
    en_tanda = alargue = False
    arbs = res.get("arbitros") if isinstance(res.get("arbitros"), dict) else {}
    anadido = {}               # periodo -> minutos del cartel del 4to árbitro
    penales, revisadas = [], []  # penales en juego; rojas que el VAR bajó a amarilla
    penal_pendiente, roja_por_var = None, False
    dt_expulsiones, ajustes = [], []   # director técnico (services/tecnicos.py)
    # equipo de cada jugador (el VAR firma los goles anulados como "VAR")
    lado_jugador = {n: k for k in "LV" for n in (res.get("titulares_" + ("local" if k == "L" else "visitante")) or [])}
    for e in res.get("eventos") or []:
        if e.get("tipo") == "🔄 SUSTITUCIÓN" and lado(e.get("equipo")) and e.get("jugadores"):
            lado_jugador.setdefault(e["jugadores"][0], lado(e.get("equipo")))
    for e in res.get("eventos") or []:
        t, m, js, ld = e.get("tipo") or "", int(e.get("minuto") or 0), e.get("jugadores") or [], lado(e.get("equipo"))
        seg = int(e.get("segundos_acumulados") or m * 60)
        # periodo y descuento: los partidos con tiempo añadido traen 'periodo'/'adicional' (services/arbitraje.py);
        # los viejos se cortan por segundos de juego (45' = 2700 s, 90' = 5400 s)
        per = e.get("periodo") or (1 if seg < 2700 else (2 if seg < 5400 else 3))
        per = 3 if per >= 3 else per
        ad = int(e.get("adicional") or 0)
        if t == "🥅 TANDA DE PENALTIS":
            en_tanda = True
            continue
        if t == "⏱️ TIEMPO EXTRA":
            alargue = True
        if t == "⏱️ TIEMPO AÑADIDO":
            anadido[e.get("periodo") or per] = e.get("minutos_anadidos")
            continue
        if en_tanda:
            if t == "⚽ GOL DE PENAL" and ld:
                tanda.append({"lado": ld, "gol": True, "tirador": js[0] if js else ""})
            elif t == "❌ PENAL FALLADO" and ld:   # el evento lo firma el equipo del arquero
                tanda.append({"lado": otro[ld], "gol": False, "tirador": js[1] if len(js) > 1 else "", "arquero": js[0] if js else ""})
            continue
        if t == "🎯 PENAL" and ld:
            penal_pendiente = {"min": m, "adic": ad, "per": per, "seg": seg, "lado": ld, "victima": js[0] if js else "",
                               "infractor": js[1] if len(js) > 1 else "", "resultado": None}
            penales.append(penal_pendiente)
            continue
        if t == "🖥️ VAR - CONFIRMADO":
            if goles and goles[-1]["seg"] == seg:
                goles[-1]["var_ok"] = True
            elif rojas and rojas[-1]["seg"] == seg:
                rojas[-1]["var_ok"] = True
            elif penal_pendiente:
                penal_pendiente["var_ok"] = True
            continue
        if t == "🖥️ VAR - PENAL ANULADO" and penal_pendiente:
            penal_pendiente.update(resultado="anulado", tirador=js[0] if js else "")
            penal_pendiente = None
            continue
        if t == "❌ PENAL FALLADO" and penal_pendiente:
            penal_pendiente.update(resultado="atajado", arquero=js[0] if js else "", tirador=js[1] if len(js) > 1 else "")
            penal_pendiente = None
            continue
        if t == "🖥️ VAR - TARJETA REVISADA" and ld:
            revisadas.append({"min": m, "adic": ad, "per": per, "seg": seg, "lado": ld, "jugador": js[0] if js else ""})
            continue
        if t == "🖥️ VAR - ROJA DIRECTA":
            roja_por_var = True
            continue
        if t in TIPOS_GOL and ld:
            antes = dict(marcador)
            marcador[ld] += 1
            if e.get("de_penal") and penal_pendiente:
                penal_pendiente.update(resultado="gol", tirador=js[0] if js else "")
                penal_pendiente = None
            goles.append({"min": m, "adic": ad, "per": per, "penal": bool(e.get("de_penal")), "seg": seg, "lado": ld, "autor": js[0] if js else "", "asistente": js[2] if len(js) > 2 else None,
                          "tipo": "penal" if e.get("de_penal") else {"⚽ GOL DE TIRO LIBRE": "tiro_libre", "⚽ GOL DE CÓRNER": "corner", "⚽ GOL DE PENAL": "penal"}.get(t, "jugada"),
                          "antes": antes, "despues": dict(marcador), "leyenda": (js[0] if js else "") in leyendas[ld],
                          "especialidad": e.get("especialidad_nombre")})
        elif t in ("🟥 TARJETA ROJA", "🟨🟥 DOBLE AMARILLA") and ld:
            rojas.append({"min": m, "adic": ad, "per": per, "seg": seg, "lado": ld, "jugador": js[0] if js else "", "doble": "DOBLE" in t,
                          "por_var": roja_por_var})
            roja_por_var = False
        elif t == "🟨 TARJETA AMARILLA" and ld:
            amarillas[ld] += 1
        elif t == "🖥️ VAR - GOL ANULADO":
            jug = js[0] if js else ""
            motivo = re.search(r"anula el gol de .+? ((?:por|porque) [^.]+)\.", e.get("descripcion") or "")
            var.append({"min": m, "adic": ad, "per": per, "seg": seg, "jugador": jug, "lado": lado_jugador.get(jug),
                        "motivo": motivo.group(1) if motivo else None, "marcador": dict(marcador)})
        elif t in ("🧤 ATAJADA ESPECTACULAR", "🖐️ DESVÍO A CÓRNER") and ld and js:
            atajadas[ld] += 1
            porteros[ld][js[0]] += 1
        elif t == "⚠️ ERROR DE PORTERÍA" and ld:
            errores[ld] += 1
        elif t == "🎯 DISPARO DESVIADO" and ld:
            desviados[ld] += 1
        elif t == "🔄 SUSTITUCIÓN" and ld and len(js) >= 2:
            cambios.append({"min": m, "adic": ad, "per": per, "seg": seg, "lado": ld, "entra": js[0], "sale": js[1], "leyenda": js[0] in leyendas[ld]})
        elif t == "🥵 DESGASTE" and ld and js:
            desgaste.append({"min": m, "lado": ld, "jugador": js[0]})
        elif t == "🚑 LESIÓN" and ld and js and e.get("sale_lesionado"):
            lesiones.append({"min": m, "lado": ld, "jugador": js[0], "lesion": e.get("lesion") or "una lesión",
                             "sin_cambio": bool(e.get("sin_cambio")), "equipo": e.get("equipo")})
        elif t == "🟥 DT EXPULSADO" and ld:
            dt_expulsiones.append({"min": m, "adic": ad, "per": per, "seg": seg, "lado": ld, "dt": e.get("dt") or ""})
        elif t == "📋 AJUSTE TÁCTICO" and ld:
            ajustes.append({"min": m, "adic": ad, "per": per, "seg": seg, "lado": ld, "dt": e.get("dt") or "", "ajuste": e.get("ajuste"),
                            "marcador": dict(marcador), "esquema_de": e.get("esquema_de"), "esquema_a": e.get("esquema_a")})

    gl, gv = int(res.get("goles_local") or 0), int(res.get("goles_visitante") or 0)
    pl, pv = res.get("penaltis_local"), res.get("penaltis_visitante")
    hubo_tanda = bool(tanda) or (gl == gv and pl not in (None, 0) or pv not in (None, 0)) and bool(tanda)
    if gl != gv:
        ganador = "L" if gl > gv else "V"
    elif hubo_tanda and pl is not None and pv is not None and pl != pv:
        ganador = "L" if pl > pv else "V"
    else:
        ganador = None
    estad = juego.get("estadisticas") or {}
    titulares = {"L": res.get("titulares_local") or [], "V": res.get("titulares_visitante") or []}
    h = {
        "id": str(juego.get("_id")), "nombre": nombre, "gl": gl, "gv": gv, "pl": pl, "pv": pv, "tanda": tanda, "hubo_tanda": hubo_tanda,
        "alargue": alargue, "ganador": ganador, "goles": goles, "rojas": rojas, "var": var, "cambios": cambios, "desgaste": desgaste, "lesiones": lesiones,
        "atajadas": atajadas, "porteros": porteros, "amarillas": amarillas, "errores": errores, "desviados": desviados,
        "ranking": {"L": loc.get("rankin"), "V": vis.get("rankin")}, "fase_id": juego.get("fase_id"), "fase": _fase(juego.get("fase_id")),
        "grupo": juego.get("grupo"), "confederacion_id": juego.get("confederacion_id"), "tag": juego.get("tag") or "",
        "estadio": (juego.get("ubicacion") or {}).get("estadio"), "ciudad": (juego.get("ubicacion") or {}).get("nombre"),
        "arbitro": arbs.get("central"), "arbs": arbs, "rigor": _rigor(arbs.get("central")), "anadido": anadido,
        "penales": penales, "revisadas": revisadas,
        "posesion": {"L": (estad.get("local") or {}).get("p_posesion"), "V": (estad.get("visitante") or {}).get("p_posesion")},
        "tiros": {"L": (estad.get("local") or {}).get("tiros_totales"), "V": (estad.get("visitante") or {}).get("tiros_totales")},
        "asistencia": (juego.get("aforo") or {}).get("asistencia"), "clima": (juego.get("clima") or {}).get("descripcion") or (juego.get("clima") or {}).get("tipo"),
        "leyendas_titulares": {k: [n for n in titulares[k] if n in leyendas[k]] for k in "LV"},
        # planteamiento de cada DT (formaciones v2): {L|V: {esquema, etiqueta, motivo, cambios}}
        "planteamiento": {"L": (res.get("planteamiento") or {}).get("local"), "V": (res.get("planteamiento") or {}).get("visita")},
        "goleadores_sub": {g["jugador_nombre"] for g in res.get("goleadores") or [] if g.get("entro_de_cambio")},
        "dt": {"L": ((res.get("dt") or {}).get("local") or {}).get("nombre"), "V": ((res.get("dt") or {}).get("visita") or {}).get("nombre")},
        "dt_expulsiones": dt_expulsiones, "ajustes": ajustes,
    }
    # el ajuste "al ataque" que rindió: el primer gol del equipo después del ajuste, si le cambió el resultado
    for a in ajustes:
        if a["ajuste"] != "ataque":
            continue
        gol = next((g for g in goles if g["seg"] > a["seg"] and g["lado"] == a["lado"]), None)
        if gol and gol["antes"][a["lado"]] < gol["antes"][otro[a["lado"]]]:
            a["gol"] = gol
    h["historias"] = _historias(h)
    h["principal"] = h["historias"][0] if h["historias"] else {"clave": "neutro", "prio": 0}
    h["figura"] = _figura(h, res)
    if h["principal"]["clave"] == "arquero_figura":   # si la historia es el arquero, la figura es él
        p = h["principal"]
        h["figura"] = {"nombre": p["arquero"], "lado": p["lado"], "goles": 0, "asistencias": 0, "atajadas": p["n"]}
    return h


def _historias(h) -> List[dict]:
    goles, nombre, gan = h["goles"], h["nombre"], h["ganador"]
    dif, total = abs(h["gl"] - h["gv"]), h["gl"] + h["gv"]
    hs = []
    def add(clave, prio, **datos):
        hs.append({"clave": clave, "prio": prio, **datos})
    # peor desventaja que tuvo cada equipo
    peor = {"L": 0, "V": 0}
    for g in goles:
        d = g["despues"]
        peor["L"] = max(peor["L"], d["V"] - d["L"])
        peor["V"] = max(peor["V"], d["L"] - d["V"])
    if h["hubo_tanda"] and gan:
        add("tanda", 95, equipo=gan)
    if gan and peor[gan] >= 2:
        add("remontada_epica", 98, equipo=gan, desventaja=peor[gan])
    elif gan and peor[gan] == 1 and h["gl"] != h["gv"]:
        add("remontada", 91, equipo=gan)
    if not gan or h["gl"] == h["gv"]:
        for k in "LV":
            if peor[k] >= 2 and h["gl"] == h["gv"]:
                add("rescate", 86, equipo=k, desventaja=peor[k])
    # gol decisivo agónico: el último gol que cambió el resultado
    if goles:
        ult = goles[-1]
        d, a = ult["despues"], ult["antes"]
        if ult["min"] >= 85:
            if gan and h["gl"] != h["gv"] and ult["lado"] == gan and a[gan] == a[{"L": "V", "V": "L"}[gan]]:
                add("agonico", 90, gol=ult)
            elif d["L"] == d["V"] and h["gl"] == h["gv"]:
                add("empate_agonico", 85, gol=ult)
    if gan and dif >= 5:
        add("paliza", 88, equipo=gan)
    elif gan and dif >= 3:
        add("goleada", 80, equipo=gan)
    por_jugador = Counter((g["autor"], g["lado"]) for g in goles)
    for (autor, ld), n in por_jugador.most_common():
        if n >= 3:
            add("hat_trick", 87, jugador=autor, lado=ld, n=n)
        elif n == 2:
            add("doblete", 58, jugador=autor, lado=ld)
    rk = h["ranking"]
    if gan and rk.get(gan) and rk.get({"L": "V", "V": "L"}[gan]) and rk[gan] - rk[{"L": "V", "V": "L"}[gan]] >= 25 and h["gl"] != h["gv"]:
        add("sorpresa", 84, equipo=gan)
    for r in h["rojas"]:
        if gan and r["lado"] == gan:
            add("con_diez", 78, equipo=gan, roja=r)
        elif gan and r["lado"] != gan:
            add("expulsion_pesa", 66, roja=r)
        elif not gan:
            add("roja_empate", 55, roja=r)
    if total >= 4 and h["gl"] == h["gv"]:
        add("empate_loco", 76)
    if total == 0:
        add("cero_cero", 50)
    for k in "LV":   # arquero figura: muchas atajadas, o bastantes con el arco en cero
        en_cero = (h["gv"] if k == "L" else h["gl"]) == 0
        if h["atajadas"][k] >= 7 or (h["atajadas"][k] >= 5 and en_cero):
            add("arquero_figura", 68 if (gan == k or gan is None) else 57, lado=k, arquero=h["porteros"][k].most_common(1)[0][0], n=h["atajadas"][k])
    for g in goles:
        if g["leyenda"]:
            decisivo = gan == g["lado"] and g is _gol_decisivo(h)
            add("leyenda_decisiva" if decisivo else "leyenda_goleadora", 83 if decisivo else 62, gol=g)
        if g["autor"] in h["goleadores_sub"]:
            decisivo = (gan == g["lado"] and g is _gol_decisivo(h)) or (h["gl"] == h["gv"] and g is goles[-1] and g["min"] >= 80)
            if decisivo:
                add("super_sub", 70, gol=g)
    if goles and goles[0]["min"] <= 4:
        add("madrugador", 40, gol=goles[0])
    for v in h["var"]:
        # gol anulado que habría cambiado el resultado: le quitó el empate o el triunfo a ese equipo
        k = v.get("lado")
        if k:
            final = (h["gl"] - h["gv"]) if k == "L" else (h["gv"] - h["gl"])
            if final in (-1, 0):
                add("var_decisivo", 82, lado=k, jugador=v["jugador"], anulado=v)
                break
    for a in h.get("ajustes") or []:
        # el DT movió el tablero y el gol que llegó después le salvó o le dio el partido
        k = a["lado"]
        if a.get("gol") and (gan == k or (gan is None and h["gl"] == h["gv"])):
            add("ajuste_decisivo", 72 if gan == k else 63, lado=k, equipo=k, dt=a["dt"], gol=a["gol"])
            break
    for x in h.get("dt_expulsiones") or []:
        add("dt_expulsado", 46, lado=x["lado"], dt=x["dt"])
    if h["var"]:
        add("var", 45, n=len(h["var"]))
    if gan and dif == 1:
        add("minima", 54, equipo=gan)
    elif gan and dif == 2:
        add("clara", 52, equipo=gan)
    elif h["gl"] == h["gv"] and 0 < total < 4:
        add("empate", 48)
    hs.sort(key=lambda x: -x["prio"])
    return hs


def _gol_decisivo(h):
    """El gol que dejó al ganador arriba para siempre (el 'gol del triunfo')."""
    gan = h["ganador"]
    if not gan or h["gl"] == h["gv"]:
        return None
    perd = {"L": "V", "V": "L"}[gan]
    final_perd = h["gl"] if perd == "L" else h["gv"]
    for g in h["goles"]:
        if g["lado"] == gan and g["despues"][gan] == final_perd + 1:
            return g
    return None


def _figura(h, res):
    puntos = Counter()
    lado_de = {}
    for g in h["goles"]:
        puntos[g["autor"]] += 3 + (1 if g is _gol_decisivo(h) else 0)
        lado_de[g["autor"]] = g["lado"]
        if g["asistente"]:
            puntos[g["asistente"]] += 2
            lado_de[g["asistente"]] = g["lado"]
    for k in "LV":
        for arquero, n in h["porteros"][k].items():
            puntos[arquero] += n * 0.8 + (2 if (k == "L" and h["gv"] == 0) or (k == "V" and h["gl"] == 0) else 0)
            lado_de[arquero] = k
    if not puntos:
        return None
    for jugador, ld in lado_de.items():
        if ld == h["ganador"]:
            puntos[jugador] += 2      # la figura sale, salvo actuación enorme, del que ganó
    nombre, pts = puntos.most_common(1)[0]
    ld = lado_de[nombre]
    return {"nombre": nombre, "lado": ld, "goles": sum(1 for g in h["goles"] if g["autor"] == nombre),
            "asistencias": sum(1 for g in h["goles"] if g["asistente"] == nombre), "atajadas": h["porteros"][ld].get(nombre, 0)}


# =================================================================================================================
# 2. REDACCIÓN
# =================================================================================================================
def _mins(m, adicional=0):
    return f"{m}+{adicional}'" if adicional else f"{m}'"


def _marc(d):
    return f'{d["L"]}-{d["V"]}'


TITULARES = {
    "remontada_epica": ["¡Épico! {g} remonta {desv} en contra y se lo lleva ante {p}", "{g} resucita: de estar {desv} abajo a ganarle {m} a {p}",
                        "Remontada para la historia: {g} da vuelta un partido perdido ante {p}", "{g} no se rinde nunca y tumba a {p} en una remontada épica"],
    "remontada": ["{g} lo da vuelta y vence {m} a {p}", "Remontada de {g}: empezó perdiendo y terminó festejando ante {p}",
                  "{g} reacciona a tiempo y le gana {m} a {p}", "De atrás y con carácter: {g} supera a {p}"],
    "rescate": ["{e} rescata un empate que parecía imposible ante {o}", "{e} se levanta de {desv} abajo y empata con {o}",
                "Reacción de orgullo: {e} iguala {m} con {o} tras ir perdiendo por {desv}"],
    "agonico": ["¡En la última! {autor} le da el triunfo a {g} sobre {p} en el {min}", "{g} lo gana sobre la hora: {autor} decide en el {min}",
                "Agónico: gol de {autor} en el {min} y {g} vence a {p}", "{autor} aparece en el final y {g} se queda con todo ante {p}"],
    "empate_agonico": ["{autor} rescata un punto para {e} en el {min}", "Empate sobre la hora: {autor} iguala en el {min}",
                       "¡No se terminaba! {autor} empata en el {min} y reparto entre {l} y {v}"],
    "paliza": ["Paliza histórica: {g} aplasta {m} a {p}", "{g} no tiene piedad y le hace {gg} a {p}", "Baile de {g}: {m} a {p}"],
    "goleada": ["Goleada de {g}: {m} a {p}", "{g} pasa por encima de {p} y gana {m}", "Festival de {g}, que golea {m} a {p}",
                "Sin discusión: {g} vapulea {m} a {p}"],
    "tanda": ["{g} gana en los penales y deja afuera a {p}", "Desde los doce pasos: {g} vence a {p} en la tanda ({pg}-{pp})",
              "Infarto en los penales: {g} se impone a {p}", "{g} tuvo más puntería en la tanda y elimina a {p}"],
    "hat_trick": ["Noche de {jug}: hat-trick y {e} {res}", "¡Triplete de {jug}! {e} {res}", "{jug} se lleva la pelota a casa: tres goles para {e}"],
    "sorpresa": ["¡Batacazo! {g} sorprende a {p} y gana {m}", "Golpe de {g}: vence {m} a {p}, que era el favorito", "David venció a Goliat: {g} {m} {p}"],
    "con_diez": ["Con uno menos y con el corazón: {g} le gana {m} a {p}", "{g} resiste con diez y vence a {p}", "Heroico {g}: con diez hombres derrota a {p}"],
    "leyenda_decisiva": ["La leyenda no se oxida: {autor} le da el triunfo a {g}", "{autor} vuelve a ser héroe: {g} vence {m} a {p}",
                         "Clase eterna: gol de {autor} y {g} supera a {p}"],
    "empate_loco": ["Partidazo en {ciudad}: {l} y {v} empatan {m}", "Locura total: {l} y {v} igualan {m} en un partido de ida y vuelta",
                    "Empate vibrante: {m} entre {l} y {v}"],
    "cero_cero": ["Empate sin goles entre {l} y {v}", "{l} y {v} no se sacan ventaja: 0-0", "Cerrojo y respeto: {l} y {v} igualan sin goles"],
    "arquero_figura": ["Las manos de {arq} sostuvieron a {e}", "{arq}, el muro de {e}", "Noche de atajadas: {arq} brilla en el arco de {e}"],
    "super_sub": ["{autor} entra y define: {g} vence {m} a {p}", "Cambio con premio: {autor} saltó al campo y le dio el triunfo a {g}"],
    "doblete": ["Doblete de {jug} y {e} {res}", "{jug} firma dos goles: {e} {res} ante {o}", "La noche de {jug}: dos goles para {e}"],
    "expulsion_pesa": ["{g} aprovecha la expulsión y vence {m} a {p}", "La roja pesó: {g} supera {m} a {p}", "{p} se quedó con diez y {g} no perdonó"],
    "roja_empate": ["Empate caliente entre {l} y {v}: {m} y expulsión", "{l} y {v} igualan {m} en un partido picante",
                    "Tarjeta roja y tablas: {l} {m} {v}"],
    "leyenda_goleadora": ["La leyenda {autor} dejó su sello en {l} {m} {v}", "Gol de leyenda: {autor} marcó en {l} {m} {v}"],
    "minima": ["{g} gana por la mínima ante {p}", "Triunfo ajustado de {g}: {m} a {p}", "{g} sufre pero vence {m} a {p}", "{g} se lo lleva por un gol ante {p}"],
    "clara": ["{g} vence con autoridad a {p}", "Triunfo claro de {g}: {m} a {p}", "{g} se impone {m} ante {p}"],
    "empate": ["Reparto de puntos entre {l} y {v}", "{l} y {v} igualan {m}", "Tablas entre {l} y {v}"],
    "var_decisivo": ["Polémica: el VAR le anuló un gol a {jug} y {e} {res} ante {o}", "{var} lo vio en la pantalla: gol anulado a {e}, que {res} ante {o}",
                     "El VAR decidió: sin el gol de {jug}, {e} {res} ante {o}"],
    "var": ["El VAR, protagonista entre {l} y {v}: {m}"],
    "ajuste_decisivo": ["La pizarra de {dt}: {e} fue al ataque y {res} ante {o}", "{dt} movió el tablero y {e} {res} ante {o}",
                        "Golpe de timón de {dt}: {e} se lanzó arriba y {res} ante {o}"],
    "dt_expulsado": ["Partido caliente: {dt} terminó en la tribuna y {e} {res} ante {o}", "{dt} expulsado por protestar; {e} {res} ante {o}"],
    "neutro": ["{l} y {v} cierran su duelo {m}"],
}

ENTRADAS = [
    "{lugar} fue el escenario del duelo entre {l} y {v} por {comp}.",
    "{l} recibió a {v} {lugar_en} en un partido de {comp}.",
    "Por {comp}, {l} y {v} se midieron {lugar_en}.",
    "Se jugó {lugar_en} un nuevo capítulo de {comp}: {l} frente a {v}.",
    "El pitazo de {arb} puso en marcha el cruce entre {l} y {v} {lugar_en}, válido por {comp}.",
]

APERTURA = [  # primer gol del partido
    "{min}: {autor} abrió el marcador para {e}{asis}.", "El primero llegó a los {mm} minutos: {autor} puso arriba a {e}{asis}.",
    "{autor} rompió el cero en el {min}{asis} y {e} se puso en ventaja.", "Fue {autor} el que destrabó el partido en el {min}{asis}.",
]
EMPATA = [
    "{autor} empató para {e} en el {min}{asis} ({marc}).", "{e} respondió rápido: {autor} igualó en el {min}{asis}.",
    "Pero {e} no se quedó atrás y {autor} puso el {marc} en el {min}{asis}.", "La igualdad llegó en el {min} por intermedio de {autor}{asis}.",
]
ADELANTE = [
    "{autor} volvió a poner adelante a {e} en el {min}{asis} ({marc}).", "En el {min}, {autor} desniveló para {e}{asis}: {marc}.",
    "{e} pasó al frente con el gol de {autor} en el {min}{asis}.",
]
DA_VUELTA = [
    "¡Y lo dio vuelta! {autor} marcó en el {min}{asis} y {e} pasó al frente ({marc}).", "La remontada se completó en el {min}: {autor}{asis} puso el {marc}.",
    "En el {min} llegó el gol que cambió la historia: {autor}{asis}, {marc} para {e}.",
]
AMPLIA = [
    "{autor} amplió la ventaja de {e} en el {min}{asis} ({marc}).", "En el {min}, {autor} estiró la diferencia{asis}: {marc}.",
    "{e} siguió golpeando y {autor} anotó en el {min}{asis} para el {marc}.",
]
SENTENCIA = [
    "{autor} liquidó el pleito en el {min}{asis} ({marc}).", "El {marc} de {autor} en el {min} fue la sentencia{asis}.",
    "{autor} sentenció la historia en el {min}{asis}: {marc}.",
]
DESCUENTA = [
    "{autor} descontó para {e} en el {min}{asis} ({marc}).", "{e} se acercó con el gol de {autor} en el {min}{asis}: {marc}.",
    "Hubo descuento de {e}: {autor} marcó en el {min}{asis}.",
]
DETALLE_TIPO = {"tiro_libre": [" con un tiro libre que se clavó al ángulo", " de pelota parada, un tiro libre perfecto", " con un remate de tiro libre imposible para el arquero"],
                "corner": [" de cabeza tras un córner", " en una jugada de córner", " ganando de arriba en un tiro de esquina"],
                "penal": [" desde el punto penal", " de penal"], "jugada": [""]}
# Frases que arrancan con una palabra común (se pueden pasar a minúscula después de "En el complemento,")
PALABRAS_INICIO = {"En", "El", "La", "Las", "Los", "Pero", "Hubo", "Ya", "Fue", "Así", "Desde", "Con", "Tras"}
EXCLAMACIONES = ["¡Golazo!", "¡Qué definición!", "¡Gol, gol, gol!", "¡Tremendo!", "¡Estalló el estadio!"]

SIN_GOLES_1T = ["El primer tiempo se fue sin goles: {sintesis}", "Los primeros 45 minutos terminaron en blanco. {sintesis}",
                "No hubo goles en la primera mitad. {sintesis}"]
SINTESIS_SIN_GOLES = {
    "atajadas": ["{arq} tuvo que lucirse para sostener el cero.", "La más clara la tapó {arq}.", "Hubo llegadas, pero {arq} estuvo atento."],
    "parejo": ["Mucho roce en el medio y pocas situaciones claras.", "Fue un tiempo de estudio, con las defensas bien paradas.",
               "Los dos equipos se cuidaron más de lo que arriesgaron."],
}
CIERRE_1T = ["Al descanso se fueron {marc}.", "El entretiempo llegó con el {marc}.", "Así, {marc}, terminó la primera mitad."]
SEGUNDO_SIN_GOLES = ["El complemento no cambió nada en el marcador.", "En el segundo tiempo no hubo más goles.",
                     "La segunda mitad pasó sin goles, con más fricción que juego."]
ARRANQUE_2T = ["En el complemento,", "Tras el descanso,", "En la segunda mitad,", "Ya en el segundo tiempo,"]
ROJAS = ["En el {min}, {arb} le mostró la roja a {jug}{doble} y {e} se quedó con diez.",
         "La expulsión de {jug} en el {min}{doble} dejó a {e} con un hombre menos: {arb} no dudó.",
         "{e} sufrió un golpe en el {min}: {arb} expulsó a {jug}{doble}."]
ROJA_VAR_CONFIRMA = [" Hubo revisión y {var} confirmó la decisión desde la sala VAR.", " El VAR, con {var}, respaldó lo que vio el central."]
ROJA_POR_VAR = ["En el {min}, el VAR vio lo que nadie vio: {var} llamó a {arb} al monitor y {jug} terminó expulsado; {e} se quedó con diez.",
                "Golpe desde la sala VAR en el {min}: {var} recomendó revisar y {arb} cambió la falta por roja directa para {jug}."]
ROJA_REVISADA = ["En el {min}, {arb} le había mostrado la roja a {jug}, pero {var} la revisó y quedó en amarilla: respiró {e}.",
                 "Polémica en el {min}: roja para {jug}, que el VAR ({var}) bajó a amarilla tras la revisión."]
GOL_ANULADO = ["En el {min}, {jug} festejó un gol que no fue: {quien} lo anuló{motivo}.",
               "{e} gritó en el {min}, pero el festejo duró poco: {quien} invalidó el gol de {jug}{motivo}.",
               "Hubo un gol de {jug} en el {min} que no subió al marcador: {quien} lo anuló{motivo}."]
GOL_VAR_OK = [" Hubo revisión, pero {var} lo dio por bueno.", " El 4to árbitro pidió revisarlo y {var}, desde la sala VAR, lo convalidó.",
              " Tras una revisión tensa, {var} lo confirmó."]
GOL_DESCUENTO = [" Fue en pleno descuento: {cuarto}, el 4to árbitro, había levantado el cartel con {n} minutos.",
                 " Corría el tiempo añadido que marcó el 4to árbitro, {cuarto}."]
PENAL_COBRADO = ["En el {min}, {arb} sancionó penal por una falta de {inf} sobre {vic}.",
                 "{arb} señaló el punto penal en el {min}: {inf} derribó a {vic} dentro del área."]
PENAL_ATAJADO = ["En el {min}, {arb} cobró penal por una falta de {inf} sobre {vic}, pero {arq} se lo atajó a {tir}.",
                 "{arq} fue figura en el {min}: le detuvo el penal a {tir} después de que {arb} sancionara la falta de {inf}."]
PENAL_ANULADO = ["En el {min}, {arb} marcó penal para {e}, pero tras la revisión {var} lo dio por malo: la falta había sido fuera del área.",
                 "Hubo penal para {e} en el {min}... que no fue: {var} lo revisó desde la sala VAR y {arb} lo anuló."]
PENAL_VAR_OK = [" El VAR ({var}) lo revisó y lo dio por bueno.", " Tras la revisión, {var} confirmó el penal."]
ARBITRO_ENTRADA = {
    "estricto": ["Dirigió {arb}, uno de los silbatos más estrictos del torneo.", "El juez fue {arb}, de mano dura con las tarjetas."],
    "permisivo": ["Dirigió {arb}, un árbitro que deja jugar.", "El juez fue {arb}, de los que cortan poco el juego."],
    "normal": ["Dirigió {arb}.", "El árbitro central fue {arb}."],
}
ARBITRO_VAR_ENTRADA = [" En la sala VAR estuvo {var}{perfil}.", " {var} estuvo a cargo del VAR{perfil}."]
PERFIL_VAR_TEXTO = {
    ("intervencionista", "implacable"): ", de los que revisan todo y no perdonan",
    ("intervencionista", None): ", de los que piden revisar casi todo",
    ("deja correr", None): ", de los que intervienen poco",
    (None, "implacable"): ", implacable cuando revisa",
    (None, "respeta al campo"): ", que suele respetar lo que marca el central",
}
ARBITRO_TARJETAS = {
    "muchas": ["{arb} tuvo una tarde de trabajo: mostró {n} tarjetas.", "Partido caliente para {arb}, que sacó {n} tarjetas."],
    "pocas": ["{arb} casi no tuvo que sacar tarjetas: apenas {n_txt}.", "Partido limpio: {arb} mostró apenas {n_txt}."],
}
CAMBIOS_LEYENDA = ["Desde el banco entró la leyenda {jug} ({min}) para cambiar la cara de {e}.", "{e} apostó por la experiencia: ingresó {jug}, una leyenda, en el {min}."]
LESION_FR = ["Mala noticia para {equipo}: {jug} se fue lesionado en el {min}' ({lesion}).",
             "En el {min}' {jug} tuvo que dejar la cancha por {lesion}.",
             "El {min}' trajo una baja: {jug}, con {lesion}, no pudo seguir."]
LESION_SIN_CAMBIO_FR = ["Sin cambios disponibles, {equipo} jugó el resto con uno menos.",
                        "Como ya no le quedaban cambios, {equipo} terminó con diez."]
DESGASTE_FR = ["El cansancio se hizo sentir en el tramo final, sobre todo en {jug}.", "En el último cuarto de hora las piernas pesaban: {jug} pedía el cambio a gritos."]
ALARGUE = ["El empate llevó el partido a la prórroga.", "No alcanzaron los 90 minutos: hubo tiempo extra.", "Fueron necesarios 30 minutos más."]
TANDA_FR = ["En la tanda, {g} fue más certero: {pg}-{pp}.", "Los penales sonrieron a {g}, que convirtió {pg} contra {pp}.",
            "Desde los doce pasos, {g} se impuso {pg}-{pp}."]
TANDA_ATAJADA = [" {arq} se vistió de héroe con una atajada clave.", " La figura de la tanda fue {arq}, que le detuvo el remate a {tir}."]
FIGURA_FR = ["La figura fue {nom}, {logro}.", "El nombre propio del partido: {nom}, {logro}.", "Se destacó {nom}, {logro}."]
NUMEROS_FR = ["{dom} manejó la pelota ({pos}% de posesión) y remató {tiros} veces.", "La posesión fue para {dom} ({pos}%), con {tiros} remates en total.",
              "En los números, {dom} tuvo más el balón ({pos}%) y {tiros} disparos."]
CIERRE_GANA = ["{g} suma tres puntos de oro.", "Victoria importante para {g}, que sigue en carrera.", "Tres puntos que valen mucho para {g}."]
CIERRE_EMPATE = ["Un punto para cada uno.", "Reparto que deja a ambos con cuentas pendientes.", "El empate deja todo abierto."]
POST = {
    "remontada_epica": ["¡REMONTADA ÉPICA! {g} da vuelta {desv} en contra ante {p} 🔥🔄", "Nunca den por muerto a {g} 🧟 Remonta {desv} y gana {m}"],
    "remontada": ["{g} lo da vuelta y gana {m} 🔄💪", "De atrás y con garra: {g} {m} {p} 🔥"],
    "rescate": ["{e} rescata un empate de las cenizas 🔥 {m}"],
    "agonico": ["¡AGÓNICO! {autor} en el {min} y {g} se lo lleva ⏱️⚽", "Sobre la hora: {autor} le da el triunfo a {g} 😱"],
    "empate_agonico": ["¡No se terminaba! {autor} empata en el {min} ⏱️🤝"],
    "paliza": ["Paliza de {g}: {m} 🌪️", "{g} no tuvo piedad: {m} a {p} 🚀"],
    "goleada": ["Goleada de {g} ⚽⚽⚽ {m} a {p}", "{g} pasó por encima: {m} 🔥"],
    "tanda": ["¡Infarto en los penales! {g} avanza ({pg}-{pp}) 🥅", "{g} gana la tanda y sigue en carrera 🎯"],
    "hat_trick": ["¡Hat-trick de {jug}! 🎩⚽⚽⚽", "{jug} se llevó la pelota a casa 🎩"],
    "sorpresa": ["¡BATACAZO! {g} sorprende a {p} {m} 😱", "David venció a Goliat: {g} {m} {p} 🪨"],
    "con_diez": ["Con diez y con el alma: {g} gana {m} 🦁"],
    "leyenda_decisiva": ["La leyenda {autor} decide el partido ✨ {g} {m} {p}"],
    "empate_loco": ["¡Partidazo! {l} {m} {v} 🎢", "Ida y vuelta sin respiro: {m} 🍿"],
    "cero_cero": ["Cerrojo total: {l} 0-0 {v} 🧱", "Ajedrez en la cancha: 0-0 ♟️"],
    "arquero_figura": ["{arq} fue una muralla 🧤🧱"],
    "super_sub": ["Cambio ganador: {autor} entra y define 🔁⚽"],
    "doblete": ["Doblete de {jug} ⚽⚽", "{jug} se llevó la noche con dos goles 🔥"],
    "expulsion_pesa": ["La roja pesó y {g} lo aprovechó: {m} 🟥", "{g} no perdonó al rival con diez: {m}"],
    "roja_empate": ["Partido caliente y empate: {l} {m} {v} 🟥🤝"],
    "leyenda_goleadora": ["Gol de leyenda: {autor} ✨"],
    "minima": ["{g} gana por la mínima {m} 😮‍💨", "Sufrido pero valioso: {g} {m} {p}"],
    "clara": ["{g} cumple con autoridad: {m} 💪"],
    "empate": ["{l} y {v} se reparten puntos: {m} 🤝"],
    "var_decisivo": ["Polémica 🖥️ El VAR le anuló un gol a {jug} y {e} {res}", "{var} desde la sala VAR: gol anulado a {jug} 🖥️❌"],
    "var": ["El VAR tuvo trabajo en {l} {m} {v} 🖥️"],
    "ajuste_decisivo": ["📋 La pizarra de {dt} cambió el partido: {e} {res}", "{dt} mandó a {e} al ataque y le salió 📋⚽"],
    "dt_expulsado": ["🟥 {dt} se fue a la tribuna por protestar", "Calentura en el banco: expulsado {dt} 🟥🗣️"],
    "neutro": ["{l} {m} {v}"],
}


DT_EXPULSADO = ["A los {min}, {arb} expulsó a {dt}, DT de {e}, por sus protestas: el resto lo vio desde la tribuna.",
                "{dt} se pasó de la raya en el {min}: {arb} lo mandó a la tribuna y {e} se quedó sin su técnico.",
                "Clima caliente en el {min}: {dt}, entrenador de {e}, vio la roja por reclamar."]
DT_AJUSTE = ["En el {min}, {dt} movió el tablero: mandó a {e} al ataque, con más gente en el área.",
             "{dt} no esperó más y en el {min} lanzó a {e} arriba, adelantando las líneas.",
             "Desde el banco, {dt} cambió el plan en el {min}: {e} pasó a jugarse todo al ataque."]


def _asis(g, r):
    if not g.get("asistente") or g["tipo"] in ("penal", "tiro_libre"):
        return ""
    return r.choice([f", a pase de {g['asistente']}", f" tras una asistencia de {g['asistente']}", f" con un pase medido de {g['asistente']}"])


def _frase_gol(h, g, r, idx):
    ld, a, d = g["lado"], g["antes"], g["despues"]
    rival = {"L": "V", "V": "L"}[ld]
    if idx == 0:
        banco = APERTURA
    elif a[ld] < a[rival] and d[ld] == d[rival]:
        banco = EMPATA
    elif a[ld] == a[rival] and any(x["despues"][ld] < x["despues"][rival] for x in h["goles"][:idx]):
        banco = DA_VUELTA
    elif a[ld] == a[rival]:
        banco = ADELANTE
    elif a[ld] > a[rival]:
        banco = SENTENCIA if (g["min"] >= 75 and d[ld] - d[rival] >= 2) else AMPLIA
    else:
        banco = DESCUENTA
    frase = r.choice(banco).format(min=_mins(g["min"], g.get("adic")), mm=g["min"], autor=g["autor"], e=h["nombre"][ld], asis=_asis(g, r),
                                   marc=_marc(d))
    detalle = r.choice(DETALLE_TIPO.get(g["tipo"], [""]))
    if detalle:
        frase = frase.replace(f"{g['autor']}", f"{g['autor']}{detalle}", 1) if banco is not DA_VUELTA else frase
    if g["leyenda"]:
        frase = frase.replace(g["autor"], f"la leyenda {g['autor']}", 1)
    frase = frase[0].upper() + frase[1:]
    if g["tipo"] == "tiro_libre" and r.random() < .6:
        frase = r.choice(EXCLAMACIONES) + " " + frase
    if g.get("especialidad") and r.random() < .7:   # la especialidad del jugador decidió la jugada (config/especialidades.py)
        esp = g["especialidad"]
        frase = frase.rstrip() + " " + r.choice([f"Le hizo honor a su especialidad: {esp}.",
                                                  f"Especialidad de la casa: {esp}.",
                                                  f"Ahí pesó su especialidad ({esp})."])
    return frase


EN_LETRAS = {1: "un gol", 2: "dos goles", 3: "tres goles", 4: "cuatro goles", 5: "cinco goles"}


def _datos_titular(h, hist):
    gan = hist.get("equipo") or h["ganador"]
    perd = {"L": "V", "V": "L"}.get(gan) if gan else None
    m = f'{h["gl"]}-{h["gv"]}' if (gan != "V") else f'{h["gv"]}-{h["gl"]}'
    gol = hist.get("gol") or {}
    ld = hist.get("lado") or (gol.get("lado") if gol else None) or gan or "L"
    e = h["nombre"][hist.get("equipo") or ld]
    o = h["nombre"][{"L": "V", "V": "L"}[hist.get("equipo") or ld]]
    res_txt = "gana" if h["ganador"] == ld else ("empata" if h["ganador"] is None else "cae")
    pg = (h["pl"] if gan == "L" else h["pv"]) if gan else ""
    pp = (h["pv"] if gan == "L" else h["pl"]) if gan else ""
    return {"g": h["nombre"][gan] if gan else h["nombre"]["L"], "p": h["nombre"][perd] if perd else h["nombre"]["V"], "m": m,
            "gg": max(h["gl"], h["gv"]), "l": h["nombre"]["L"], "v": h["nombre"]["V"], "e": e, "o": o, "desv": EN_LETRAS.get(hist.get("desventaja"), ""),
            "autor": gol.get("autor", ""), "min": _mins(gol["min"], gol.get("adic")) if gol else "", "jug": hist.get("jugador", ""), "res": res_txt,
            "arq": hist.get("arquero", ""), "ciudad": h["ciudad"] or "la sede", "pg": pg, "pp": pp,
            "var": h["arbs"].get("var") or "El VAR", "arb": h["arbitro"] or "el árbitro", "dt": hist.get("dt", "")}


def redactar(h: dict) -> dict:
    r = random.Random(h["id"])
    principal = h["principal"]
    datos = _datos_titular(h, principal)
    titular = r.choice(TITULARES.get(principal["clave"]) or TITULARES["neutro"]).format(**datos)
    nombre = h["nombre"]
    parrafos = []

    # --- Entrada: dónde, por qué y el resumen de la historia ---
    if h["fase_id"] and h["fase_id"] >= 7:
        comp = f"la {h['fase']} del Mundial" if h["fase_id"] >= 8 else f"la fase de grupos del Mundial{(' (' + h['grupo'] + ')') if h.get('grupo') else ''}"
    else:
        comp = COMPETICION.get(h["confederacion_id"], "las Eliminatorias") + (f", {h['grupo']}" if h.get("grupo") else "")
    lugar = f"El {h['estadio']} de {h['ciudad']}" if h["estadio"] and h["ciudad"] else (h["ciudad"] or "La cancha")
    lugar_en = f"en el {h['estadio']}" if h["estadio"] else (f"en {h['ciudad']}" if h["ciudad"] else "")
    entrada = r.choice(ENTRADAS).format(lugar=lugar, lugar_en=lugar_en, l=nombre["L"], v=nombre["V"], comp=comp, arb=h["arbitro"] or "el árbitro")
    extras = []
    if h["asistencia"]:
        cifra = f"{h['asistencia']:,}".replace(",", ".")
        extras.append(r.choice([f"hubo {cifra} personas en las tribunas", f"lo vieron {cifra} espectadores", f"{cifra} hinchas colmaron el estadio"]))
    if h["clima"]:
        extras.append(f"bajo un clima {str(h['clima']).lower()}")
    if extras:
        frase = " y ".join(extras)
        entrada += " " + frase[0].upper() + frase[1:] + "."
    leyendas_txt = []
    for k in "LV":
        if h["leyendas_titulares"][k]:
            ls = h["leyendas_titulares"][k]
            leyendas_txt.append(f"{nombre[k]} salió con {('la leyenda ' + ls[0]) if len(ls) == 1 else ('las leyendas ' + ', '.join(ls[:-1]) + ' y ' + ls[-1])}")
    if leyendas_txt:
        entrada += " " + r.choice(["Como dato especial, ", "Hubo historia en la cancha: ", "Detalle de lujo: "]) + "; ".join(leyendas_txt) + "."
    plan = h.get("planteamiento") or {}
    if plan.get("L") and plan.get("V"):
        def _esq(k):
            p = plan[k]
            return f"un {p['esquema']} {str(p.get('etiqueta') or '').lower()}".rstrip()
        entrada += " " + r.choice([
            f"En la pizarra, {nombre['L']} salió con {_esq('L')} y {nombre['V']} respondió con {_esq('V')}.",
            f"Los técnicos se jugaron sus cartas: {_esq('L')} para {nombre['L']}, {_esq('V')} para {nombre['V']}.",
            f"{nombre['L']} se paró con {_esq('L')}; enfrente, {nombre['V']} eligió {_esq('V')}.",
        ])
        cambio = next((p for k in "LV" for p in (plan.get(k) or {}).get("cambios") or []), None)
        if cambio and not (h.get("principal") or {}).get("clave") == "ajuste_decisivo":
            k = next(k for k in "LV" if cambio in ((plan.get(k) or {}).get("cambios") or []))
            entrada += " " + r.choice([f"En el {cambio['minuto']}' {nombre[k]} pasó del {cambio['de']} al {cambio['a']}.",
                                       f"Al {cambio['minuto']}', {nombre[k]} cambió el dibujo: del {cambio['de']} al {cambio['a']}."])
    arbs = h["arbs"]
    if h["arbitro"] and h["arbitro"] not in entrada:
        etiqueta = _etiqueta_rigor(h["rigor"])
        entrada += " " + r.choice(ARBITRO_ENTRADA[etiqueta]).format(arb=h["arbitro"])
        if arbs.get("var") and (h["var"] or h["revisadas"] or any(g.get("var_ok") for g in h["goles"]) or h["penales"]):
            pv = _perfil(arbs["var"])
            iv, sv = pv.get("var_intervencion_etiqueta"), pv.get("var_severidad_etiqueta")
            perfil_txt = (PERFIL_VAR_TEXTO.get((iv, sv)) or PERFIL_VAR_TEXTO.get((iv, None))
                          or PERFIL_VAR_TEXTO.get((None, sv)) or "")
            entrada += r.choice(ARBITRO_VAR_ENTRADA).format(var=arbs["var"], perfil=perfil_txt)
    parrafos.append(entrada)

    # --- Línea de tiempo por período (goles, rojas e ingresos de leyendas), por segundos de juego ---
    goles = h["goles"]
    items = {1: [], 2: [], 3: []}
    for i, g in enumerate(goles):
        frase = _frase_gol(h, g, r, i)
        if g.get("var_ok"):
            frase += r.choice(GOL_VAR_OK).format(var=arbs.get("var") or "el VAR")
        n_cartel = h["anadido"].get(g["per"] if g["per"] < 3 else 4)
        if g.get("adic") and g["per"] == 2 and arbs.get("cuarto") and n_cartel:
            frase += r.choice(GOL_DESCUENTO).format(cuarto=arbs["cuarto"], n=n_cartel)
        items[g["per"]].append((g["seg"], frase))
    arb, var_nom = h["arbitro"] or "el árbitro", arbs.get("var") or "el VAR"
    for roja in h["rojas"]:
        datos_roja = dict(min=_mins(roja["min"], roja.get("adic")), jug=roja["jugador"], e=nombre[roja["lado"]], arb=arb, var=var_nom,
                          doble=" por doble amarilla" if roja["doble"] else "")
        frase = r.choice(ROJA_POR_VAR if roja.get("por_var") else ROJAS).format(**datos_roja)
        if roja.get("var_ok"):
            frase += r.choice(ROJA_VAR_CONFIRMA).format(var=var_nom)
        items[roja["per"]].append((roja["seg"], frase))
    for rv in h["revisadas"]:
        items[rv["per"]].append((rv["seg"], r.choice(ROJA_REVISADA).format(min=_mins(rv["min"], rv.get("adic")), jug=rv["jugador"], arb=arb,
                                                                            var=var_nom, e=nombre[rv["lado"]])))
    for v in h["var"]:
        quien = (f"el VAR ({arbs['var']})" if arbs.get("var") else f"{arb}, tras consultar el VAR,")
        motivo = f" {v['motivo']}" if v.get("motivo") else ""
        items[v["per"]].append((v["seg"], r.choice(GOL_ANULADO).format(min=_mins(v["min"], v.get("adic")), jug=v["jugador"], quien=quien,
                                                                       motivo=motivo, e=nombre.get(v.get("lado"), "El equipo"))))
    for pen in h["penales"]:
        datos_pen = dict(min=_mins(pen["min"], pen.get("adic")), arb=arb, var=var_nom, inf=pen["infractor"], vic=pen["victima"],
                         e=nombre[pen["lado"]], arq=pen.get("arquero", ""), tir=pen.get("tirador", ""))
        if pen["resultado"] == "gol":
            frase = r.choice(PENAL_COBRADO).format(**datos_pen)
        elif pen["resultado"] == "atajado":
            frase = r.choice(PENAL_ATAJADO).format(**datos_pen)
        elif pen["resultado"] == "anulado":
            frase = r.choice(PENAL_ANULADO).format(**datos_pen)
        else:
            continue
        if pen.get("var_ok") and pen["resultado"] != "anulado":
            frase += r.choice(PENAL_VAR_OK).format(var=var_nom)
        items[pen["per"]].append((pen["seg"] - 0.5, frase))   # antes del gol de penal
    for x in h.get("dt_expulsiones") or []:
        items[x["per"]].append((x["seg"], r.choice(DT_EXPULSADO).format(dt=x["dt"], e=nombre[x["lado"]], arb=arb,
                                                                       min=_mins(x["min"], x.get("adic")))))
    for a in h.get("ajustes") or []:
        if a.get("gol"):
            items[a["per"]].append((a["seg"], r.choice(DT_AJUSTE).format(dt=a["dt"], e=nombre[a["lado"]], min=_mins(a["min"], a.get("adic")))))
    ingresos = defaultdict(list)   # leyendas que entran, agrupadas por equipo y período
    for c in h["cambios"]:
        if c["leyenda"]:
            ingresos[(c["per"], c["lado"])].append(c)
    for (per, ld), lista in ingresos.items():
        if len(lista) == 1:
            frase = r.choice(CAMBIOS_LEYENDA).format(jug=lista[0]["entra"], min=_mins(lista[0]["min"], lista[0].get("adic")), e=nombre[ld])
        else:
            nombres = ", ".join(c["entra"] for c in lista[:-1]) + " y " + lista[-1]["entra"]
            frase = r.choice([f"{nombre[ld]} apostó por la experiencia con los ingresos de las leyendas {nombres}.",
                              f"Desde el banco de {nombre[ld]} saltaron las leyendas {nombres}."])
        items[per].append((lista[0]["seg"], frase))
    for k in items:
        items[k].sort(key=lambda x: x[0])

    goles_1t = [g for g in goles if g["per"] == 1]
    if items[1]:
        texto = " ".join(t for _, t in items[1])
        if goles_1t:
            texto += " " + r.choice(CIERRE_1T).format(marc=_marc(goles_1t[-1]["despues"]))
        else:
            texto = r.choice(SIN_GOLES_1T).format(sintesis=texto)
        parrafos.append(texto)
    else:
        mejor_arq = max("LV", key=lambda k: h["atajadas"][k])
        if h["atajadas"][mejor_arq] >= 2:
            sint = r.choice(SINTESIS_SIN_GOLES["atajadas"]).format(arq=h["porteros"][mejor_arq].most_common(1)[0][0])
        else:
            sint = r.choice(SINTESIS_SIN_GOLES["parejo"])
        parrafos.append(r.choice(SIN_GOLES_1T).format(sintesis=sint))

    if items[2]:
        cuerpo = " ".join(t for _, t in items[2])
        if cuerpo.startswith("¡"):
            parrafos.append(r.choice(["El complemento trajo lo mejor.", "El segundo tiempo fue otra historia.", "Tras el descanso, el partido se encendió."]) + " " + cuerpo)
        else:
            primera = cuerpo.split(" ", 1)[0]
            if primera in PALABRAS_INICIO:
                cuerpo = cuerpo[0].lower() + cuerpo[1:]
                parrafos.append(r.choice(ARRANQUE_2T) + " " + cuerpo)
            else:
                # arranca con un nombre propio: no se puede pasar a minúscula, va con una frase de apertura propia
                parrafos.append(r.choice(["El complemento siguió con emociones.", "En el segundo tiempo hubo más.",
                                          "La segunda mitad tuvo su propia historia."]) + " " + cuerpo)
    else:
        parrafos.append(r.choice(SEGUNDO_SIN_GOLES))
    if h["desgaste"] and r.random() < .7:
        parrafos[-1] += " " + r.choice(DESGASTE_FR).format(jug=h["desgaste"][-1]["jugador"])
    for l in (h.get("lesiones") or [])[:2]:   # lesiones que sacaron a alguien de la cancha (services/lesiones.py)
        frase = r.choice(LESION_FR).format(jug=l["jugador"], min=l["min"], lesion=l["lesion"], equipo=l["equipo"])
        if l["sin_cambio"]:
            frase += " " + r.choice(LESION_SIN_CAMBIO_FR).format(equipo=l["equipo"])
        parrafos[-1] += " " + frase

    # --- Alargue y penales ---
    if h["alargue"]:
        txt = r.choice(ALARGUE)
        if items[3]:
            txt += " " + " ".join(t for _, t in items[3])
        if h["hubo_tanda"] and h["ganador"]:
            gan = h["ganador"]
            pg, pp = (h["pl"], h["pv"]) if gan == "L" else (h["pv"], h["pl"])
            txt += " " + r.choice(TANDA_FR).format(g=nombre[gan], pg=pg, pp=pp)
            atajada = next((t for t in h["tanda"] if not t["gol"] and t.get("arquero") and t["lado"] != gan), None)
            if atajada:
                txt += r.choice(TANDA_ATAJADA).format(arq=atajada["arquero"], tir=atajada["tirador"])
        parrafos.append(txt)

    # --- Figura y números ---
    cierre = []
    f = h["figura"]
    if f:
        logros = []
        if f["goles"]:
            logros.append("autor de " + ("un gol" if f["goles"] == 1 else f"{f['goles']} goles"))
        if f["asistencias"]:
            logros.append("con " + ("una asistencia" if f["asistencias"] == 1 else f"{f['asistencias']} asistencias"))
        if f["atajadas"] and not f["goles"]:
            logros.append(f"con {f['atajadas']} atajadas de alto nivel")
        cierre.append(r.choice(FIGURA_FR).format(nom=f"{f['nombre']} ({nombre[f['lado']]})", logro=" y ".join(logros) or "imparable toda la noche"))
    n_tarjetas = h["amarillas"]["L"] + h["amarillas"]["V"] + len(h["rojas"])
    if h["arbitro"] and (n_tarjetas >= 6 or (n_tarjetas <= 1 and _etiqueta_rigor(h["rigor"]) != "estricto" and r.random() < .5)):
        clave = "muchas" if n_tarjetas >= 6 else "pocas"
        cierre.append(r.choice(ARBITRO_TARJETAS[clave]).format(arb=h["arbitro"], n=n_tarjetas,
                                                               n_txt="ninguna" if n_tarjetas == 0 else "una"))
    pos = h["posesion"]
    if pos.get("L") and pos.get("V"):
        dom = "L" if pos["L"] >= pos["V"] else "V"
        cierre.append(r.choice(NUMEROS_FR).format(dom=nombre[dom], pos=round(pos[dom]), tiros=h["tiros"].get(dom) or 0))
    # --- Lo que significa ---
    if h["ganador"] and h["fase_id"] and h["fase_id"] >= 8:
        gan = nombre[h["ganador"]]
        if h["fase_id"] == 13:
            cierre.append(r.choice([f"¡{gan} es campeón del mundo!", f"{gan} levanta la Copa del Mundo de la FIFAV.", f"La gloria es de {gan}: campeón del Mundial."]))
        elif h["fase_id"] == 12:
            cierre.append(f"{gan} se queda con el tercer puesto.")
        elif h["fase_id"] in SIGUIENTE_FASE:
            perd = nombre[{"L": "V", "V": "L"}[h["ganador"]]]
            cierre.append(r.choice([f"{gan} avanza a {SIGUIENTE_FASE[h['fase_id']]} y {perd} se despide del Mundial.",
                                    f"Con este triunfo, {gan} se mete en {SIGUIENTE_FASE[h['fase_id']]}; {perd} queda eliminado."]))
    elif h["ganador"] and h["gl"] != h["gv"]:
        cierre.append(r.choice(CIERRE_GANA).format(g=nombre[h["ganador"]]))
    elif h["gl"] == h["gv"]:
        cierre.append(r.choice(CIERRE_EMPATE))
    parrafos.append(" ".join(cierre))

    post = r.choice(POST.get(principal["clave"]) or POST["neutro"]).format(**datos)
    if h["tag"]:
        post += f" {h['tag']}"
    return {"titular": titular, "parrafos": [p for p in parrafos if p.strip()], "post": post}


def _etiqueta_rigor(rigor) -> str:
    if rigor is None:
        return "normal"
    return "permisivo" if rigor < 0.92 else ("estricto" if rigor > 1.08 else "normal")


def nombres_a_resaltar(juego: dict) -> dict:
    """Jugadores, árbitros y equipos del partido: la vista los resalta en la crónica (filtro resaltar_cronica)."""
    res = juego.get("resultado") or {}
    jugadores = set(res.get("titulares_local") or []) | set(res.get("titulares_visitante") or [])
    for e in res.get("eventos") or []:
        jugadores.update(n for n in (e.get("jugadores") or []) if n)
    arbitros = [n for n in (res.get("arbitros") or {}).values() if isinstance(n, str) and n] if isinstance(res.get("arbitros"), dict) else []
    equipos = [n for n in (res.get("local"), res.get("visitante")) if n]
    jugadores.update(d.get("nombre") for d in (res.get("dt") or {}).values() if isinstance(d, dict) and d.get("nombre"))   # los DT, como jugadores
    return {"jugadores": sorted(jugadores - set(arbitros) - set(equipos)), "arbitros": arbitros, "equipos": equipos}


def _es_primer_tiempo(goles, i):
    """Gol del primer tiempo (incluye su descuento, 45+N)."""
    return goles[i].get("per", 1) == 1


# =================================================================================================================
# 3. PERSISTENCIA (generar al leer)
# =================================================================================================================
def generar(juego: dict) -> dict:
    h = analizar(juego)
    texto = redactar(h)
    return {"version": VERSION, **texto, "historia": h["principal"]["clave"], "resaltar": nombres_a_resaltar(juego),
            "generada_en": datetime.utcnow()}


def asegurar_cronica(juego: Optional[dict]) -> Optional[dict]:
    """
    Devuelve la crónica del partido; si falta o es de una versión anterior la genera y la guarda (update condicional,
    así dos lecturas a la vez no pisan nada raro). Nunca durante la transmisión en vivo. Nunca lanza.
    """
    try:
        if not juego or juego.get("estado") != "finalizado" or not juego.get("resultado"):
            return None
        if (juego.get("transmision") or {}).get("estado") == "in_progress":
            return None
        actual = (juego.get("resultado") or {}).get("cronica")
        if actual and actual.get("version") == VERSION:
            return actual
        nueva = generar(juego)
        db["juegos"].update_one({"_id": juego["_id"], "$or": [{"resultado.cronica": {"$exists": False}},
                                                              {"resultado.cronica.version": {"$ne": VERSION}},
                                                              {"resultado.cronica": None}]},
                                {"$set": {"resultado.cronica": nueva}})
        juego["resultado"]["cronica"] = nueva
        return nueva
    except Exception as e:
        print(f"No se pudo generar la crónica del partido {juego.get('_id') if juego else '?'}: {e}")
        return None
