"""
Efecto de la FORMACIÓN en el partido (lógica pura; catálogo en config/formaciones.py). Lo usa simular_service.

Todo entra como puntos de atributo en los resolver_duelo() que ya existen (mismo patrón que bonus_pie_habil):
  - superioridad numérica en la zona del duelo: jugadores de la línea propia contra los de la línea rival que la
    disputa (en el medio, medios contra medios; en ataque, delanteros contra defensas; en la salida, defensas contra
    delanteros), contra lo normal de esa zona;
  - el perfil del esquema según la acción (posesión, progresión, remate, cierre, presión, aéreo);
  - la postura: mueve la frecuencia de tiros y pases profundos (partidos más abiertos o más cerrados).
"""
from typing import Dict, List, Tuple

from config import formaciones as F


def datos(esquema: str) -> dict:
    return F.FORMACIONES.get(esquema) or F.FORMACIONES[F.ESQUEMA_POR_DEFECTO]


def lineas(esquema: str, espejo: bool = False) -> List[int]:
    """Línea de cada puesto (slot 1..11). espejo: los extremos (EI/ED) intercambian su línea (ver SLOTS_EXTREMOS)."""
    base = datos(esquema)["lineas"]
    if not espejo:
        return base
    i, d = (s - 1 for s in F.SLOTS_EXTREMOS)
    salida = list(base)
    salida[i], salida[d] = base[d], base[i]
    return salida


def faltan(cuenta: dict) -> int:
    """Jugadores de campo que le faltan a un equipo (expulsados o lesionados sin cambio), con tope."""
    en_campo = sum(cuenta.get(l, 0) for l in (2, 3, 4))
    return max(0, min(F.TOPE_INFERIORIDAD, F.JUGADORES_DE_CAMPO - en_campo))


def postura(esquema: str) -> float:
    return datos(esquema)["postura"]


def perfil(esquema: str) -> dict:
    return datos(esquema)["perfil"]


def cuentas_de_esquema(esquema: str) -> Dict[int, int]:
    c = {1: 0, 2: 0, 3: 0, 4: 0}
    for linea in lineas(esquema):
        c[linea] += 1
    return c


def cuentas(plantilla: list) -> Dict[int, int]:
    """Jugadores en cancha por línea (cambia con expulsiones y cambios de esquema)."""
    c = {1: 0, 2: 0, 3: 0, 4: 0}
    for j in plantilla:
        c[j.get("linea_partido", 3)] = c.get(j.get("linea_partido", 3), 0) + 1
    return c


def superioridad(zona: str, cuenta_ataque: dict, cuenta_defensa: dict) -> float:
    """Puntos para el que tiene la pelota (negativo = para el que defiende) por jugadores de más en la zona."""
    la, ld = F.LINEAS_DUELO.get(zona, (3, 3))
    dif = cuenta_ataque.get(la, 0) - cuenta_defensa.get(ld, 0) - F.BASE_SUPERIORIDAD.get(zona, 0)
    dif = max(-F.TOPE_SUPERIORIDAD, min(F.TOPE_SUPERIORIDAD, dif))
    return dif * F.PUNTOS_SUPERIORIDAD


def bonos(zona: str, accion: str, esquema_ataque: str, esquema_defensa: str, cuenta_ataque: dict, cuenta_defensa: dict) -> Tuple[float, float]:
    """(puntos para el atacante, puntos para el defensor) en el duelo de esta acción."""
    pa, pd = perfil(esquema_ataque), perfil(esquema_defensa)
    if accion in ("pase", "despeje"):
        if zona == "defensa":
            a, d = 0.5 * pa["posesion"], pd["presion"]
        elif zona == "medio":
            a, d = pa["posesion"], 0.5 * pd["presion"]
        else:
            a, d = 0.5 * pa["progresion"], pd["cierre"]
    elif accion == "pase_profundo":
        a, d = pa["progresion"], 0.5 * pd["cierre"]
    elif accion == "regate":
        if zona == "ataque":
            a, d = 0.5 * pa["progresion"], pd["cierre"]
        elif zona == "medio":
            a, d = 0.3 * pa["progresion"], 0.5 * pd["presion"]
        else:
            a, d = 0.0, pd["presion"]
    elif accion == "tiro":
        a, d = pa["remate"], 0.5 * pd["cierre"]
    else:
        a, d = 0.0, 0.0
    sup = superioridad(zona, cuenta_ataque, cuenta_defensa)
    contra = 0.0
    if accion in ("pase_profundo", "regate") and zona in ("defensa", "medio"):
        contra = F.CONTRAGOLPE * max(0.0, postura(esquema_defensa) - postura(esquema_ataque))
    # Inferioridad numérica: el que tiene menos jugadores de campo pierde puntos en todos sus duelos
    inf_a = faltan(cuenta_ataque) * F.PUNTOS_INFERIORIDAD_ATAQUE
    inf_d = faltan(cuenta_defensa) * F.PUNTOS_INFERIORIDAD_DEFENSA
    return (F.ESCALA_PERFIL * a + max(sup, 0.0) + contra - inf_a,
            F.ESCALA_PERFIL * d + max(-sup, 0.0) - inf_d)


def bono_aereo(esquema_ataque: str, esquema_defensa: str) -> Tuple[float, float]:
    """Córners: (puntos para el que cabecea, para el que marca)."""
    return F.ESCALA_PERFIL * perfil(esquema_ataque)["aereo"], F.ESCALA_PERFIL * perfil(esquema_defensa)["aereo"]


def pesos_con_postura(opciones: list, pesos: list, esquema: str) -> list:
    """Postura ofensiva: más tiros y pases profundos; defensiva: menos (partidos más cerrados)."""
    p = postura(esquema) - F.POSTURA_REFERENCIA   # relativa a la postura media de los DT: en promedio no cambia el volumen
    salida = []
    for op, w in zip(opciones, pesos):
        if op == "tiro":
            w = w * max(0.2, 1 + F.POSTURA_TIRO * p)
        elif op == "pase_profundo":
            w = w * max(0.2, 1 + F.POSTURA_PROFUNDO * p)
        salida.append(w)
    return salida


def ventaja(esquema: str, esquema_rival: str) -> float:
    """Ventaja esperada (en puntos de atributo, aprox.) de un esquema contra otro: la usa el DT para elegir."""
    ca, cr = cuentas_de_esquema(esquema), cuentas_de_esquema(esquema_rival)
    pa, pr = perfil(esquema), perfil(esquema_rival)
    v = superioridad("medio", ca, cr) + 0.5 * (superioridad("ataque", ca, cr) - superioridad("ataque", cr, ca))
    v += F.ESCALA_PERFIL * 0.5 * ((pa["posesion"] - 0.5 * pr["presion"]) - (pr["posesion"] - 0.5 * pa["presion"]))
    v += F.ESCALA_PERFIL * 0.5 * ((pa["remate"] - 0.5 * pr["cierre"]) - (pr["remate"] - 0.5 * pa["cierre"]))
    v += 0.5 * F.CONTRAGOLPE * (max(0.0, postura(esquema_rival) - postura(esquema)) - max(0.0, postura(esquema) - postura(esquema_rival)))
    return round(v, 2)


def reasignar_lineas(plantilla: list, esquema: str, espejo: bool = False) -> None:
    """Cambio de esquema en vivo: cada jugador pasa a la línea que su puesto ('slot') tiene en el esquema nuevo."""
    nuevas = lineas(esquema, espejo)
    for j in plantilla:
        slot = j.get("slot")
        if slot and 1 <= slot <= 11 and j.get("linea_partido") != 1:
            j["linea_partido"] = nuevas[slot - 1] if nuevas[slot - 1] != 1 else j.get("linea_partido", 3)
