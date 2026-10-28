"""
Efecto de las ESPECIALIDADES en el partido (lógica pura; catálogo en config/especialidades.py). Lo usa simular_service.

Como la formación y el pie hábil, todo entra como puntos de atributo en los resolver_duelo() que ya existen:
puntos(jugador, accion, rol, zona) suma los de sus especialidades que aplican a esa jugada. Las condiciones del partido
viajan en el propio dict del jugador: '_revulsivo' (entró de cambio) y '_partido_grande' (eliminación directa / serie).
"""
import random
from typing import List, Optional

from config import especialidades as CE


def de(jugador: dict) -> List[str]:
    return [c for c in (jugador.get("especialidades") or []) if c in CE.ESPECIALIDADES]


def _aplica(efecto: dict, accion: str, rol: str, zona: Optional[str], jugador: dict) -> bool:
    if efecto["accion"] not in ("*", accion):
        return False
    if efecto["rol"] not in ("*", rol):
        return False
    if efecto.get("zonas") and zona not in efecto["zonas"]:
        return False
    if efecto.get("linea_partido") and jugador.get("linea_partido") not in efecto["linea_partido"]:
        return False
    return True


def _cumple(esp: dict, jugador: dict) -> bool:
    cond = esp.get("condicion")
    if cond == "revulsivo":
        return bool(jugador.get("_revulsivo"))
    if cond == "partido_grande":
        return bool(jugador.get("_partido_grande"))
    return True


def puntos(jugador: Optional[dict], accion: str, rol: str, zona: Optional[str] = None) -> float:
    """Puntos de atributo que suman las especialidades del jugador en esta jugada (0 si no tiene ninguna que aplique)."""
    if not jugador or not jugador.get("especialidades"):
        return 0.0
    total = 0.0
    for codigo in de(jugador):
        esp = CE.ESPECIALIDADES[codigo]
        if not _cumple(esp, jugador):
            continue
        for ef in esp["efectos"]:
            if _aplica(ef, accion, rol, zona, jugador):
                total += ef["factor"] * CE.PUNTOS_ESPECIALIDAD
    return total


def decisiva(jugador: Optional[dict], accion: str, rol: str, zona: Optional[str] = None) -> Optional[str]:
    """La especialidad que más pesó en esta jugada (para narrar), o None."""
    if not jugador or not jugador.get("especialidades"):
        return None
    mejor, peso = None, 0.0
    for codigo in de(jugador):
        esp = CE.ESPECIALIDADES[codigo]
        if not esp.get("narrar") or not _cumple(esp, jugador):
            continue
        p = sum(ef["factor"] for ef in esp["efectos"] if _aplica(ef, accion, rol, zona, jugador))
        if p > peso:
            mejor, peso = codigo, p
    return mejor


_GENERICAS = ["{j} hace valer su especialidad: {e}.", "Especialidad de la casa ({e}) para {j}."]


def frase(codigo: Optional[str], nombre: str) -> str:
    """Frase para la narración: la propia de la especialidad o una genérica (para que no se repita siempre igual)."""
    esp = CE.ESPECIALIDADES.get(codigo or "")
    if not esp or not esp.get("narrar"):
        return ""
    if random.random() < 0.55:
        return esp["narrar"].format(j=nombre) + "."
    return random.choice(_GENERICAS).format(j=nombre, e=esp["nombre"], e_min=esp["nombre"].lower())


def extra_evento(codigo: Optional[str]) -> dict:
    """Campos aditivos del evento cuando una especialidad decidió la jugada (EventoOut los lista)."""
    esp = CE.ESPECIALIDADES.get(codigo or "")
    return {"especialidad": codigo, "especialidad_nombre": esp["nombre"]} if esp else {}


def factor_gasto(jugador: dict) -> float:
    """Multiplicador del gasto de energía (services/desgaste.py): el Pulmón se cansa menos."""
    return CE.FACTOR_PULMON if "pulmon" in (jugador.get("especialidades") or []) else 1.0


def vista(codigos) -> list:
    """[{codigo, nombre, icono, descripcion}] para las vistas."""
    return [{"codigo": c, **{k: CE.ESPECIALIDADES[c][k] for k in ("nombre", "icono", "descripcion")}}
            for c in (codigos or []) if c in CE.ESPECIALIDADES]


# =====================================================================================================================
# EVOLUCIÓN (reglas en config/especialidades.GANAR / PERDER; persistencia en services/especialidades_service.py)
# =====================================================================================================================
_FIGURA_GRANDE = {"PORTERO": 8.2, "DEFENSA": 7.5, "MEDIO": 7.7, "DELANTERO": 8.7}


def resumen_partido(stats: dict, goles_en_contra: int, grande: bool, juego_id: str) -> dict:
    """Resumen compacto de un partido de un jugador (lo que leen las reglas). 'stats' = stats_jugadores[id] del motor."""
    linea_p = str(stats.get("posicion") or "MEDIO").upper()
    g, a = int(stats.get("goles", 0) or 0), int(stats.get("asistencias", 0) or 0)
    cal = stats.get("rating")
    sub, salio = bool(stats.get("entro_de_cambio")), bool(stats.get("salio_de_cambio"))
    en = stats.get("energia_final")
    r = {"j": juego_id, "g": g, "a": a, "ga": g + a, "r": int(stats.get("recuperaciones", 0) or 0),
         "rg": int(stats.get("regates_exitosos", 0) or 0), "at": int(stats.get("atajadas", 0) or 0),
         "ap": int(stats.get("atajadas_penales", 0) or 0), "gco": int(stats.get("goles_corner", 0) or 0),
         "gp": int(stats.get("goles_penal", 0) or 0), "gtl": int(stats.get("goles_tiro_libre", 0) or 0),
         "cal": round(float(cal), 2) if cal is not None else None, "sub": int(sub),
         "comp": int(not sub and not salio and not stats.get("expulsado")),
         "en": round(float(en), 1) if en is not None else None,
         "v": int(linea_p in ("PORTERO", "DEFENSA") and goles_en_contra == 0 and not sub),
         "gr": int(bool(grande)), "sub_ga": int(sub and g + a > 0)}
    r["comp_fuerte"] = int(r["comp"] and (r["en"] or 0) >= 45)
    r["gr_ok"] = int(grande and (g > 0 or (cal or 0) >= _FIGURA_GRANDE.get(linea_p, 8.0)))
    return r


def _umbral(valor, linea: str):
    return valor.get(linea) if isinstance(valor, dict) else valor


def _metricas(ventana: list) -> dict:
    """Sumas, medias y cuentas de la ventana (las medias de 'cal'/'en' ignoran los partidos sin dato)."""
    out = {}
    claves = {k for p in ventana for k in p if k != "j"}
    for k in claves:
        vals = [p[k] for p in ventana if p.get(k) is not None]
        out[k] = {"suma": sum(vals), "media": (sum(vals) / len(vals)) if vals else None, "cuenta": sum(1 for v in vals if v)}
    return out


def _escala_ganar(desvio: float) -> float:
    return max(0.6, min(2.0, 1.0 + CE.EQUILIBRIO_UMBRAL * desvio))


def _rating_pierde(linea: str, desvio: float) -> float:
    return CE.RATING_PIERDE.get(linea, 6.5) + CE.EQUILIBRIO_RATING * desvio


def _cumple_ganar(regla: dict, ventana: list, linea: str, desvio: float = 0.0) -> Optional[dict]:
    """Métricas de la ventana si se cumple la regla de ganar (None si no)."""
    if regla.get("filtro"):
        ventana = [p for p in ventana if p.get(regla["filtro"])]
    if linea not in regla["lineas"] or len(ventana) < regla["n"]:
        return None
    vent = ventana[-regla["n"]:]
    m = _metricas(vent)
    escala = _escala_ganar(desvio)
    for tipo in ("suma", "media", "cuenta"):
        for clave, minimo in (regla.get(tipo) or {}).items():
            u = _umbral(minimo, linea)
            if u is None:
                return None
            u = u * escala if tipo != "cuenta" else max(1, round(u * escala))
            val = (m.get(clave) or {}).get(tipo)
            if val is None or val < u:
                return None
    return m


def _cumple_perder(codigo: str, ventana: list, linea: str, desvio: float = 0.0) -> bool:
    regla = CE.PERDER.get(codigo)
    if regla and regla.get("filtro"):
        ventana = [p for p in ventana if p.get(regla["filtro"])]
    if not regla or len(ventana) < regla["n"]:
        return False
    vent = ventana[-regla["n"]:]
    m = _metricas(vent)
    if "solo_rating" in regla:
        cal = (m.get("cal") or {}).get("media")
        return cal is not None and cal < _rating_pierde(linea, desvio) - regla["solo_rating"]
    for tipo, base in (("suma_max", "suma"), ("media_max", "media"), ("cuenta_max", "cuenta")):
        for clave, maximo in (regla.get(tipo) or {}).items():
            u = _umbral(maximo, linea)
            if u is None:
                continue
            val = (m.get(clave) or {}).get(base)
            if val is None or val > u:
                return False
    if not regla.get("sin_rating"):
        cal = (m.get("cal") or {}).get("media")
        if cal is None or cal >= _rating_pierde(linea, desvio):
            return False
    return True


def _motivo(codigo: str, m: dict, n: int) -> str:
    datos = {"n": n}
    for k, v in m.items():
        datos[k] = v["cuenta"] if k in ("v", "sub_ga", "gr_ok", "comp_fuerte") else v["suma"]
        datos[f"{k}_m"] = f"{v['media']:.1f}" if v["media"] is not None else "—"
    try:
        return CE.MOTIVO_GANAR.get(codigo, "").format(**datos)
    except (KeyError, IndexError):
        return ""


def evaluar(estado: dict, desvio: float = 0.0) -> tuple:
    """
    Lógica pura de la evolución después de un partido. estado = {linea (natural), especialidades, esp_ventana,
    esp_partidos {codigo: partidos jugados con ella}}. Devuelve (ganadas [(codigo, motivo)], perdidas [(codigo, motivo)]).
    Primero las pérdidas (con período de gracia), después como mucho GANADAS_POR_PARTIDO nueva, con tope de 3.
    """
    if estado.get("leyenda"):   # las leyendas no evolucionan (config/especialidades.py)
        return [], []
    linea, ventana = estado.get("linea") or "MEDIO", estado.get("esp_ventana") or []
    actuales = [c for c in (estado.get("especialidades") or []) if c in CE.ESPECIALIDADES]
    jugados = estado.get("esp_partidos") or {}
    perdidas = []
    for c in actuales:
        if jugados.get(c, 0) >= CE.PARTIDOS_GRACIA and _cumple_perder(c, ventana, linea, desvio):
            perdidas.append((c, CE.MOTIVO_PERDER.format(n=CE.PERDER[c]["n"])))
    quedan = [c for c in actuales if c not in {p[0] for p in perdidas}]
    ganadas = []
    if len(quedan) < CE.MAXIMO_POR_JUGADOR:
        candidatas = []
        for c, regla in CE.GANAR.items():
            if c in quedan or c in {p[0] for p in perdidas}:
                continue
            m = _cumple_ganar(regla, ventana, linea, desvio)
            if m is not None:
                candidatas.append((c, _motivo(c, m, regla["n"])))
        ganadas = candidatas[:CE.GANADAS_POR_PARTIDO]
    return ganadas, perdidas


def evolucionar_equipo(estados: list, total: int) -> dict:
    """
    Evolución de los jugadores de UNA selección en un partido, con equilibrio, piso y techo (lógica pura; la usan
    especialidades_service y calibrar_especialidades). estados = [{jid, linea, especialidades, esp_ventana, esp_partidos,
    cal (calificación del partido)}], total = especialidades de sus 22 actuales ANTES del partido.
    Devuelve {jid: (ganadas, perdidas)} solo de los que cambian. Primero las pérdidas (sin bajar del piso), después las
    ganadas por calificación del partido (sin pasar el techo: con el techo lleno, una nueva entra solo si otro compañero
    perdió una en este mismo partido).
    """
    desvio = total - CE.BASE_SELECCION
    propuestas = {e["jid"]: evaluar(e, desvio) for e in estados}
    salida, actual = {}, total
    for jid, (g, p) in propuestas.items():
        aplicadas = []
        for x in p:
            if actual - 1 >= CE.PISO_SELECCION:
                aplicadas.append(x)
                actual -= 1
        if aplicadas:
            salida[jid] = ([], aplicadas)
    orden = sorted(estados, key=lambda e: -(e.get("cal") or 0))
    for e in orden:
        g, _ = propuestas[e["jid"]]
        for x in g:
            if actual + 1 <= CE.TECHO_SELECCION:
                ganadas, perdidas = salida.get(e["jid"], ([], []))
                salida[e["jid"]] = (ganadas + [x], perdidas)
                actual += 1
    return salida


def progreso(estado: dict, maximo: int = 3) -> dict:
    """
    Para la ficha: las especialidades más cerca de ganarse (fracción de cada condición) y las que están en riesgo
    (la regla de pérdida ya se cumple pero falta el período de gracia, o se cumple con la mitad de la ventana).
    """
    linea, ventana = estado.get("linea") or "MEDIO", estado.get("esp_ventana") or []
    actuales = set(estado.get("especialidades") or [])
    cerca = []
    for c, regla in CE.GANAR.items():
        if c in actuales or linea not in regla["lineas"]:
            continue
        base = [p for p in ventana if p.get(regla["filtro"])] if regla.get("filtro") else ventana
        vent = base[-regla["n"]:]
        m = _metricas(vent) if vent else {}
        partes = []
        for tipo in ("suma", "media", "cuenta"):
            for clave, minimo in (regla.get(tipo) or {}).items():
                u = _umbral(minimo, linea)
                if not u:
                    continue
                val = ((m.get(clave) or {}).get(tipo) or 0) * (len(vent) / regla["n"] if tipo == "media" else 1)
                partes.append(min(1.0, val / u))
        if partes:
            frac = min(partes) * 0.6 + (sum(partes) / len(partes)) * 0.4
            if frac > 0:
                cerca.append({**vista([c])[0], "progreso": round(frac * 100), "partidos": f"{len(vent)}/{regla['n']}"})
    cerca.sort(key=lambda x: -x["progreso"])
    riesgo = [vista([c])[0] for c in actuales if c in CE.PERDER and _cumple_perder(c, ventana, linea)]
    return {"cerca": cerca[:maximo], "riesgo": riesgo, "partidos_registrados": len(ventana)}


def situacion_cambio(va_perdiendo: bool, va_ganando: bool, minuto: int) -> str:
    if va_perdiendo:
        return "perdiendo"
    if va_ganando and minuto >= CE.MINUTO_CERRAR:
        return "ganando"
    return "empate" if not va_ganando else ""


def peso_cambio(jugador: dict, situacion: str, lectura: float) -> tuple:
    """(peso para entrar, especialidad que lo motivó o None). lectura 0..1: cuánto pesa el criterio del DT."""
    buscadas = CE.PREFERENCIA_CAMBIO.get(situacion) or []
    propias = [c for c in de(jugador) if c in buscadas]
    if not propias:
        return 1.0, None
    return 1.0 + CE.PESO_ESPECIALIDAD_CAMBIO * lectura, propias[0]
