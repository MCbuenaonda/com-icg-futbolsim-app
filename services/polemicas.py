"""Polémicas arbitrales (lógica pura). Sin Mongo: services/polemicas_service.py arma el análisis (cronica_service.analizar), llama aquí y guarda.

`detectar(h)` recibe el análisis de la crónica (`h`: goles, var, penales, rojas, arbs, ganador...) y devuelve las jugadas polémicas con su peso, el
lado perjudicado ('L'|'V') y el árbitro responsable ('var' o 'central'). Tono siempre de «decisión discutida»: nunca acusa de corrupción.
"""
import random
from typing import Dict, List, Optional

from config import polemicas as CP
from services import prensa as P

CIERRE = {"sensacionalista": ["¿Escándalo arbitral?", "El vestuario es un volcán.", "Esto no se queda así."],
          "analitica": ["Las imágenes dejan margen para la duda.", "Habrá que revisar el protocolo del VAR.", "La interpretación del reglamento lo explica casi todo."],
          "critica": ["El arbitraje volvió a quedar en deuda.", "Se exige más criterio.", "Así es difícil defender la decisión."],
          "oficialista": ["Hay que respetar la decisión del colegiado.", "El arbitraje trabaja con las reglas en la mano.", "Conviene bajar el tono."],
          "optimista": ["Aun así, el fútbol fue el protagonista.", "Lo bueno: el partido dejó mucho para ver.", "Hay que mirar hacia adelante."],
          "popular": ["En la calle no se habla de otra cosa.", "La afición lo vivió con rabia.", "El pueblo tiene su veredicto."]}

APERTURA = {
    "gol_anulado_decisivo": ["Polémica en el {eq}-{rival}: el VAR ({arb}) anuló el gol de {jug} y a {eq} le costó {res}.",
                             "{arb}, desde la sala VAR, le anuló un gol a {jug} ({eq}) {motivo}: terminó costando {res}.",
                             "El gol anulado a {jug} cambió la historia: {eq} se quedó sin {res} por la decisión de {arb}."],
    "gol_anulado": ["{arb} (VAR) anuló el gol de {jug} ({eq}) en el minuto {min} y dejó dudas.", "Gol anulado a {jug}: el VAR ({arb}) intervino {motivo} y el estadio protestó.",
                    "Decisión discutida: {arb} dio por malo el gol de {jug} ({eq})."],
    "penal_anulado": ["El VAR ({arb}) revirtió un penal a favor de {eq} y encendió la polémica.", "Penal que se esfumó: {arb} lo revisó y lo anuló ante {rival}.",
                      "{eq} se quedó sin penal por la revisión del VAR ({arb}): reclamos en el banquillo."],
    "roja_por_var": ["El VAR ({arb}) elevó a roja la acción de {jug} y {eq} se quedó con diez: ¿exceso?", "Roja a {jug} por llamado del VAR ({arb}): {eq} lo protesta.",
                     "{arb} mandó revisar y {jug} vio la roja; {eq} juega con diez entre reclamos."],
    "penal_decisivo": ["{arb} señaló un penal sobre {victima} que terminó decidiendo el partido: {rival} lo protesta.", "El penal de {arb} a favor de {eq} pesó en el resultado y {rival} no está de acuerdo.",
                       "Penal discutido: la decisión de {arb} inclinó el {eq}-{rival}."]}


def _lado_nombre(h: dict, lado: str) -> str:
    return h["nombre"][lado]


def detectar(h: dict) -> List[dict]:
    """[{codigo, peso, responsable, arbitro (nombre), lado (perjudicado 'L'|'V'), jugador, minuto, datos}] de un partido."""
    arbs = h.get("arbs") or {}
    items: List[dict] = []
    for v in h.get("var") or []:   # gol anulado por el VAR; perjudicado = el equipo de quien lo había marcado
        k = v.get("lado")
        if not k:
            continue
        final = (h["gl"] - h["gv"]) if k == "L" else (h["gv"] - h["gl"])
        decisivo = final in (-1, 0)
        items.append({"codigo": "gol_anulado_decisivo" if decisivo else "gol_anulado", "responsable": "var", "arbitro": arbs.get("var"), "lado": k,
                      "jugador": v.get("jugador"), "minuto": v.get("min"), "datos": {"res": "el empate" if final == -1 else "el triunfo", "motivo": v.get("motivo") or "tras revisarlo"}})
    for p in h.get("penales") or []:
        k, otro = p["lado"], ("V" if p["lado"] == "L" else "L")
        if p.get("resultado") == "anulado":   # el VAR lo revirtió: perjudicado = el que iba a cobrar
            items.append({"codigo": "penal_anulado", "responsable": "var", "arbitro": arbs.get("var"), "lado": k, "jugador": p.get("victima"), "minuto": p.get("min"), "datos": {}})
        elif p.get("resultado") == "gol":
            margen = (h["gl"] - h["gv"]) if k == "L" else (h["gv"] - h["gl"])
            if margen in (0, 1):   # el penal le dio el pase o el empate: lo discute el otro
                items.append({"codigo": "penal_decisivo", "responsable": "central", "arbitro": arbs.get("central"), "lado": otro, "jugador": p.get("victima"), "minuto": p.get("min"),
                              "datos": {"victima": p.get("victima") or "un jugador", "beneficiado": k}})
    for r in h.get("rojas") or []:
        if r.get("por_var"):
            items.append({"codigo": "roja_por_var", "responsable": "var", "arbitro": arbs.get("var"), "lado": r["lado"], "jugador": r.get("jugador"), "minuto": r.get("min"), "datos": {}})
    for i in items:
        i["peso"] = CP.PESOS[i["codigo"]]
    return [i for i in items if i["arbitro"]]


def total(items: List[dict]) -> float:
    return round(sum(i["peso"] for i in items), 2)


def titular(item: dict, h: dict, rng: random.Random) -> str:
    k = item["lado"]
    otro = "V" if k == "L" else "L"
    datos = {"arb": item["arbitro"], "eq": _lado_nombre(h, k), "rival": _lado_nombre(h, otro), "jug": item.get("jugador") or "un jugador", "min": item.get("minuto"),
             "victima": (item.get("datos") or {}).get("victima", ""), "res": (item.get("datos") or {}).get("res", ""), "motivo": (item.get("datos") or {}).get("motivo", "")}
    if item["codigo"] == "penal_decisivo":   # aquí el «eq» es quien lo recibió a favor
        datos["eq"], datos["rival"] = _lado_nombre(h, item["datos"]["beneficiado"]), _lado_nombre(h, k)
    return rng.choice(APERTURA[item["codigo"]]).format(**datos)


def nota(item: dict, h: dict, medio: dict, periodista: dict, es_del_perjudicado: bool, rng: random.Random) -> dict:
    """{tono, categoria_tono, titular, texto} de la nota de un medio sobre el árbitro responsable."""
    base = -(0.35 + 0.45 * item["peso"])
    valor = P.tono(base, medio, periodista, False)
    if es_del_perjudicado:   # la prensa del país perjudicado es más dura con el árbitro
        valor = P.limitar(valor - 0.2 - (0.1 if periodista.get("sesgo") == "patriota" else 0.0))
    valor = round(valor, 2)
    cat = P.categoria_tono(valor)
    tit = titular(item, h, rng)
    cierre = rng.choice(CIERRE.get(medio.get("linea"), CIERRE["analitica"]))
    return {"tono": valor, "categoria_tono": cat, "titular": tit, "texto": f"{tit} {cierre}"}


def peso_designacion(puntaje: Optional[float]) -> float:
    """Peso del central en el sorteo de la eliminación directa según su reputación (ya desgastada); sin dato = 1."""
    if puntaje is None:
        return 1.0
    return max(CP.PESO_MINIMO, 1.0 + CP.PESO_REPUTACION * puntaje / 100.0)


def apartado(puntaje: Optional[float]) -> bool:
    return puntaje is not None and puntaje <= CP.UMBRAL_APARTADO
