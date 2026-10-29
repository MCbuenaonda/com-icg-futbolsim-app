"""
Cuerpo arbitral del partido (lógica pura, sin Mongo; la usan simular_service.py y asignar_arbitros_partidos.py).

Roles (resultado.arbitros): central, linea1, linea2, cuarto y var (5to árbitro).
- Central: silbatos, faltas, tarjetas y penales. Su RIGOR (arbitros.rigor, permanente) cambia cuántas tarjetas saca.
- Jueces de línea: cada uno cubre una mitad. En el 1T (y 1º del alargue) linea1 cubre el campo donde ATACA el local
  y linea2 el de la visita; en el 2T se invierten (los equipos cambian de lado). Marcan fuera de lugar y córners.
- 4to árbitro: anuncia los cambios, levanta el cartel del tiempo añadido y PIDE la revisión del VAR.
- VAR (5to): revisa lo que pide el 4to y decide si lo marcado en el campo es bueno (CONFIRMA) o no (REVIERTE).

Reloj: 'segundos_acumulados' de los eventos es la línea de tiempo continua (incluye los descuentos). Al terminar el
partido `aplicar_reloj` le pone a cada evento 'periodo' (1, 2, 3, 4 alargue, 5 tanda), 'minuto' (topado en 45/90/
105/120 durante el descuento) y 'adicional' (el +N), y `asignar_arbitros` el árbitro que actuó ('arbitro',
'arbitro_rol'). `minuto_texto` lo muestra ("90+3'").
"""
import math
import random
from typing import Dict, List, Optional

# --- Reloj ---------------------------------------------------------------------------------------------------------
# Minuto reglamentario en el que termina cada periodo (en segundos de juego)
FIN_PERIODO = {1: 2700, 2: 5400, 3: 6300, 4: 7200}
INICIO_PERIODO = {1: 0, 2: 2700, 3: 5400, 4: 6300}
PERIODO_TANDA = 5

# Tiempo añadido: lo que el 4to árbitro computa por cada parada del periodo (en minutos)
ANADIDO_BASE = {1: 0.4, 2: 0.9, 3: 0.2, 4: 0.5}
ANADIDO_POR_TIPO = {
    "🔄 SUSTITUCIÓN": 0.3,
    "🖥️ REVISIÓN VAR": 1.0,
    "⚽ GOL": 0.45, "⚽ GOL DE TIRO LIBRE": 0.45, "⚽ GOL DE CÓRNER": 0.45,
    "🟥 TARJETA ROJA": 0.6, "🟨🟥 DOBLE AMARILLA": 0.6,
    "🎯 PENAL": 0.6,
    "🥵 DESGASTE": 0.2,
    "🚑 LESIÓN": 0.7,
    "🟥 DT EXPULSADO": 0.5,
    "🟨 TARJETA AMARILLA": 0.1,
}
ANADIDO_RANGO = {1: (1, 4), 2: (2, 8), 3: (0, 2), 4: (1, 3)}


def calcular_anadido(eventos_periodo: List[dict], periodo: int, rng=random) -> int:
    """Minutos de descuento según las paradas del periodo (cambios, VAR, goles, rojas, penales, atención médica)."""
    total = ANADIDO_BASE[periodo] + sum(ANADIDO_POR_TIPO.get(e.get("tipo"), 0) for e in eventos_periodo)
    total += rng.uniform(-0.4, 0.6)
    minimo, maximo = ANADIDO_RANGO[periodo]
    return int(max(minimo, min(maximo, round(total))))


def aplicar_reloj(eventos: List[dict], inicios: Dict[int, float]) -> None:
    """
    Le pone a cada evento su periodo, minuto y adicional. 'inicios' = {periodo: segundo de la línea de tiempo en el
    que empezó} (el 1 siempre en 0; el 5 = la tanda). Los eventos de un periodo se identifican por segundo.
    """
    orden = sorted(inicios.items())
    for e in eventos:
        seg = float(e.get("segundos_acumulados") or 0)
        periodo = 1
        for p, desde in orden:
            if seg >= desde:
                periodo = p
        if e.get("periodo"):          # ya marcado al crearlo (los del cambio de periodo)
            periodo = e["periodo"]
        e["periodo"] = periodo
        if periodo == PERIODO_TANDA:
            e["minuto"], e["adicional"] = 120, 0
            continue
        reloj = INICIO_PERIODO[periodo] + (seg - inicios.get(periodo, INICIO_PERIODO[periodo]))
        fin = FIN_PERIODO[periodo]
        if reloj >= fin and e.get("tipo") not in TIPOS_CIERRE_EN_PUNTO:
            e["minuto"], e["adicional"] = fin // 60, max(1, math.ceil((reloj - fin) / 60))
        else:
            e["minuto"], e["adicional"] = int(min(reloj, fin) // 60), 0


# El cartel del añadido se levanta justo al cumplirse el minuto reglamentario
TIPOS_CIERRE_EN_PUNTO = {"⏱️ TIEMPO AÑADIDO"}


def minuto_texto(evento: dict) -> str:
    """'90+3'' / '45'' / 'PEN' (tanda). Partidos viejos sin 'adicional' se ven como siempre."""
    if evento.get("periodo") == PERIODO_TANDA:
        return "PEN"
    m = int(evento.get("minuto") or 0)
    a = int(evento.get("adicional") or 0)
    return f"{m}+{a}'" if a else f"{m}'"


# --- Jueces de línea -----------------------------------------------------------------------------------------------
def rol_juez_de_linea(atacante_es_local: bool, periodo: int) -> str:
    """Qué juez de línea ve la jugada: el del lado donde ataca ese equipo en ese periodo."""
    primer_mitad = periodo in (1, 3)
    return "linea1" if atacante_es_local == primer_mitad else "linea2"


# --- Rigor del central ----------------------------------------------------------------------------------------------
RIGOR_MIN, RIGOR_MAX = 0.75, 1.30
# Cuánto del rigor pasa a la probabilidad de cobrar falta (las tarjetas lo reciben entero)
PESO_RIGOR_FALTAS = 0.3


def etiqueta_rigor(rigor: Optional[float]) -> str:
    if rigor is None:
        return ""
    return "permisivo" if rigor < 0.92 else ("estricto" if rigor > 1.08 else "normal")


def factor_faltas(rigor: float) -> float:
    return 1 + PESO_RIGOR_FALTAS * ((rigor or 1.0) - 1)


# --- VAR -----------------------------------------------------------------------------------------------------------
# Probabilidad de que una jugada pase a revisión y, si pasa, de que el VAR la revierta. Producto = lo que antes era
# "5% de revisión x 50% de anular" (2,5%): el marcador promedio no cambia, solo se narran también las confirmaciones.
PROB_REVISION = {"gol": 0.08, "roja": 0.08, "penal": 0.08, "penal_tanda": 0.05}
PROB_REVIERTE = {"gol": 0.3125, "roja": 0.3125, "penal": 0.3125, "penal_tanda": 0.5}

MOTIVOS_GOL_ANULADO = [
    "por mano previa de {jug}",
    "por un fuera de lugar milimétrico en el inicio de la jugada",
    "por una falta en ataque antes del remate",
    "porque el balón había salido antes del centro",
]
PEDIDOS = [
    "El 4to árbitro ({cuarto}) se lleva la mano al auricular: el VAR revisa {que}.",
    "Atención: el 4to árbitro ({cuarto}) avisa que hay revisión de {que}.",
    "Se frena todo. El 4to árbitro ({cuarto}) pide revisar {que} en la sala VAR.",
]
QUE_SE_REVISA = {
    "gol": "el gol de {jug}",
    "roja": "la entrada de {jug}",
    "penal": "el cobro del penal de {jug}",
    "penal_tanda": "el cobro de {jug}",
    "falta": "una acción de {jug} que el central no vio",
}


# Personalidad del VAR (arbitros.var_intervencion / var_severidad, asignar_perfil_var.py): multiplican la probabilidad
# de revisar y la de revertir. Independientes y con promedio 1: la tasa de anulación del torneo no cambia.
VAR_INTERVENCION_MIN, VAR_INTERVENCION_MAX = 0.45, 1.8
VAR_SEVERIDAD_MIN, VAR_SEVERIDAD_MAX = 0.6, 1.4


def etiqueta_intervencion(factor: Optional[float]) -> str:
    if factor is None:
        return ""
    return "deja correr" if factor < 0.8 else ("intervencionista" if factor > 1.25 else "equilibrado")


def etiqueta_severidad(factor: Optional[float]) -> str:
    if factor is None:
        return ""
    return "respeta al campo" if factor < 0.87 else ("implacable" if factor > 1.13 else "ecuánime")


def debe_revisar(tipo: str, rng=random, intervencion: float = 1.0) -> bool:
    return rng.random() < min(1.0, PROB_REVISION[tipo] * (intervencion or 1.0))


def revierte(tipo: str, rng=random, severidad: float = 1.0) -> bool:
    return rng.random() < min(1.0, PROB_REVIERTE[tipo] * (severidad or 1.0))


def texto_pedido(arbitros: dict, tipo: str, jugador: str, rng=random) -> str:
    que = QUE_SE_REVISA[tipo].format(jug=jugador)
    return (rng.choice(PEDIDOS).format(cuarto=arbitros.get("cuarto", "el 4to árbitro"), que=que)
            + f" Desde la sala, {arbitros.get('var', 'el VAR')} analiza las imágenes.")


def texto_confirma(arbitros: dict, tipo: str, jugador: str, rng=random) -> str:
    var = arbitros.get("var", "El VAR")
    return {
        "gol": rng.choice([f"{var} da por buena la jugada: el gol de {jugador} sube al marcador.",
                           f"Tras revisar, {var} confirma lo marcado en el campo. ¡Vale el gol de {jugador}!"]),
        "roja": f"{var} confirma lo que vio {arbitros.get('central', 'el central')}: la roja a {jugador} se mantiene.",
        "penal": f"{var} da por bueno el penal: {jugador} vuelve al punto de cobro.",
        "penal_tanda": f"{var} da por bueno el penal: {jugador} vuelve al punto de cobro.",
    }[tipo]


def texto_gol_anulado(arbitros: dict, jugador: str, rng=random) -> str:
    motivo = rng.choice(MOTIVOS_GOL_ANULADO).format(jug=jugador)
    return f"{arbitros.get('var', 'El VAR')} da por mala la jugada y {arbitros.get('central', 'el central')} anula el gol de {jugador} {motivo}."


# --- Árbitro de cada evento ----------------------------------------------------------------------------------------
ROL_POR_TIPO = {
    "👉 SILBATO INICIAL": "central", "🚩 FINAL DEL PRIMER TIEMPO": "central", "🔵 COMIENZA EL SEGUNDO TIEMPO": "central",
    "⏱️ TIEMPO EXTRA": "central", "🔵 SEGUNDO TIEMPO EXTRA": "central", "🏁 PITIDO FINAL": "central",
    "🥅 TANDA DE PENALTIS": "central",
    "🛑 FALTA": "central", "🟨 TARJETA AMARILLA": "central", "🟥 TARJETA ROJA": "central", "🟨🟥 DOBLE AMARILLA": "central",
    "🎯 PENAL": "central",
    "🔄 SUSTITUCIÓN": "cuarto", "⏱️ TIEMPO AÑADIDO": "cuarto", "🖥️ REVISIÓN VAR": "cuarto",
}
TIPOS_DECISION_VAR = {"🖥️ VAR - GOL ANULADO", "🖥️ VAR - TARJETA REVISADA", "🖥️ VAR - PENAL ANULADO",
                      "🖥️ VAR - CONFIRMADO", "🖥️ VAR - ROJA DIRECTA", "🖥️ VAR - PENAL"}
TIPOS_JUEZ_DE_LINEA = {"🚩 FUERA DE LUGAR", "🚩 SAQUE DE ESQUINA"}


def asignar_arbitros(eventos: List[dict], arbitros: dict) -> None:
    """'arbitro_rol' + 'arbitro' en los eventos arbitrales que todavía no los tienen (los de línea los pone el motor)."""
    for e in eventos:
        if e.get("arbitro_rol"):
            e.setdefault("arbitro", arbitros.get(e["arbitro_rol"]))
            continue
        tipo = e.get("tipo")
        rol = ROL_POR_TIPO.get(tipo) or ("var" if tipo in TIPOS_DECISION_VAR else None)
        if rol:
            e["arbitro_rol"], e["arbitro"] = rol, arbitros.get(rol)
            if rol == "var" and "var_decision" not in e:
                e["var_decision"] = "confirma" if tipo == "🖥️ VAR - CONFIRMADO" else "revierte"


def elegir_cuerpo_arbitral(por_puesto: Dict[str, List[dict]], excluir_paises=(), rng=random) -> Dict[str, dict]:
    """Un árbitro por puesto, de un país distinto a los dos equipos (si hay de dónde elegir)."""
    elegidos = {}
    for rol, puesto in PUESTOS.items():
        candidatos = por_puesto.get(puesto) or []
        neutrales = [a for a in candidatos if a.get("pais_id") not in excluir_paises]
        elegidos[rol] = rng.choice(neutrales or candidatos) if (neutrales or candidatos) else {"nombre": None}
    # la personalidad del VAR viaja con el partido (no se persiste en el resultado: es permanente en 'arbitros')
    return elegidos


PUESTOS = {"central": "Arbitro central", "linea1": "Arbitro de línea 1", "linea2": "Arbitro de línea 2",
           "cuarto": "4to Arbitro", "var": "Arbitro VAR"}
