"""
Reglas de las LEYENDAS en cancha (lógica pura, sin base de datos).

Cada selección tiene 11 leyendas (`jugadores.leyenda == True`, una por posición) además de su
plantel de 22. En un partido cada equipo puede tener a la vez:
  - como máximo MAX_LEYENDAS_EN_CANCHA leyendas, y
  - como máximo una leyenda por SECTOR (Portero / Defensa / Medio / Delantero).

El sector sale de la posición fija del jugador (catálogo `posiciones`), no de `linea_partido`:
en un 4-4-2 el extremo izquierdo juega de volante, pero sigue siendo una leyenda "delantera".
Una leyenda expulsada sigue contando (no se la puede reemplazar), así nadie "recicla" el cupo.
"""
import random

MAX_LEYENDAS_EN_CANCHA = 3

SECTOR_POR_POSICION = {
    1: "Portero",
    2: "Defensa", 3: "Defensa", 4: "Defensa", 5: "Defensa",
    6: "Medio", 7: "Medio", 8: "Medio",
    9: "Delantero", 10: "Delantero", 11: "Delantero",
}
SECTORES = ["Portero", "Defensa", "Medio", "Delantero"]


def es_leyenda(jugador: dict) -> bool:
    return bool(jugador.get("leyenda"))


def sector(jugador: dict) -> str:
    return SECTOR_POR_POSICION.get(jugador.get("posicion_id"), "Medio")


def sectores_para_leyendas(rng=random) -> set:
    """
    Líneas que arrancan con leyenda este partido: el DT sortea CUÁNTAS (0 a 3, misma probabilidad) y en
    qué líneas (sin repetir). Las demás leyendas quedan en el banco y pueden entrar de cambio.
    """
    cantidad = rng.randint(0, MAX_LEYENDAS_EN_CANCHA)
    return set(rng.sample(SECTORES, cantidad))


def leyendas_ocupando(en_cancha: list, expulsados: list = ()) -> list:
    """Leyendas que ocupan cupo: las que están en cancha más las expulsadas."""
    vistos, salida = set(), []
    for j in list(en_cancha) + list(expulsados):
        if es_leyenda(j) and j.get("id") not in vistos:
            vistos.add(j.get("id"))
            salida.append(j)
    return salida


def puede_entrar(entra: dict, sale: dict, en_cancha: list, expulsados: list = ()) -> bool:
    """
    ¿Puede `entra` reemplazar a `sale` sin romper la regla? Un jugador normal siempre puede.
    Una leyenda puede si, quitando a la que sale, quedan menos de 3 leyendas ocupando cupo y
    ninguna en su sector (así se permite leyenda por leyenda de la misma línea).
    """
    if not es_leyenda(entra):
        return True
    ocupando = [j for j in leyendas_ocupando(en_cancha, expulsados) if j.get("id") != sale.get("id")]
    if len(ocupando) >= MAX_LEYENDAS_EN_CANCHA:
        return False
    return all(sector(j) != sector(entra) for j in ocupando)


def alineacion_valida(titulares: list, expulsados: list = ()) -> bool:
    ocupando = leyendas_ocupando(titulares, expulsados)
    sectores = [sector(j) for j in ocupando]
    return len(ocupando) <= MAX_LEYENDAS_EN_CANCHA and len(sectores) == len(set(sectores))
