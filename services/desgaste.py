"""
Desgaste físico DURANTE el partido (lógica pura, sin base de datos; la usa simular_service).

Cada jugador entra a la cancha con ENERGIA_INICIAL. La energía baja:
  - con el tiempo de juego (GASTO_POR_MINUTO; el arquero también: su desgaste es de concentración y reflejos), y
  - con cada acción que protagoniza (COSTO_ACCION: regatear y presionar cansan más que pasar),
multiplicado por su resistencia (más resistencia = gasta menos) y por el clima (juegos_service.generar_clima_partido
-> modificadores.desgaste: calor/humedad 1.1-1.25).

Por debajo de UMBRAL_FATIGA sus atributos de juego rinden menos (hasta PERDIDA_MAXIMA con la energía en 0): un
delantero cansado define peor al final que al principio. Los valores sin cansancio se guardan en jugador["_base"] y
los atributos del dict se reescriben en el lugar, así todos los duelos del motor (que leen jugador.get("precision_tiro"),
etc.) quedan afectados sin tocar cada fórmula. El que entra de cambio llega con energía completa ("piernas frescas").
"""

ENERGIA_INICIAL = 100.0
GASTO_POR_MINUTO = 0.55            # ~50 en 90' para un jugador de campo promedio, antes de acciones
FACTOR_PORTERO = 1.0                # con menos, los partidos se cerraban al final (Monte Carlo)
COSTO_ACCION = {
    "regate": 0.35, "presion": 0.2, "duelo": 0.25, "tiro": 0.2, "pase_profundo": 0.12, "pase": 0.04, "despeje": 0.06,
}
RESISTENCIA_REFERENCIA = 60.0      # la media del mundo: gasta el 100%
SENSIBILIDAD_RESISTENCIA = 0.012   # cada punto de resistencia sobre/bajo la referencia: -/+1.2% de gasto
UMBRAL_FATIGA = 70.0               # desde aquí para abajo se nota el cansancio
PERDIDA_MAXIMA = 0.10              # con 0 de energía, los atributos rinden un 10% menos...
PERDIDA_DEFENSIVA = 0.38           # ...y los defensivos más: el cansado llega tarde a cerrar (más goles al final)
ATRIBUTOS_DEFENSIVOS = {"anticipacion", "concentracion", "fuerza_fisica", "agresividad"}
ATRIBUTOS_ATAQUE_DT = {"precision_tiro", "fuerza_disparo", "regate", "vision_juego", "precision_pase", "control_balon", "velocidad"}
ATRIBUTOS_DEFENSA_DT = {"anticipacion", "concentracion", "fuerza_fisica"}   # mismos que services/tecnicos.py
UMBRAL_AVISO = 30.0               # se narra una vez "🥵 se nota el cansancio" al cruzarlo

ATRIBUTOS = ("agilidad", "agresividad", "anticipacion", "compostura", "concentracion", "control_balon",
             "fuerza_disparo", "fuerza_fisica", "juego_aereo", "precision_pase", "precision_tiro", "regate",
             "resistencia", "velocidad", "vision_juego", "rendimiento")


def iniciar(jugador: dict) -> dict:
    """Prepara a un jugador que entra a la cancha (titular o suplente): energía completa y atributos base."""
    jugador["_base"] = {a: float(jugador.get(a, 60) or 60) for a in ATRIBUTOS}
    jugador["energia"] = ENERGIA_INICIAL
    jugador["_avisado"] = False
    _refrescar(jugador)
    return jugador


def multiplicador(energia: float, perdida: float = PERDIDA_MAXIMA) -> float:
    if energia >= UMBRAL_FATIGA:
        return 1.0
    return 1.0 - perdida * (UMBRAL_FATIGA - max(energia, 0.0)) / UMBRAL_FATIGA


def _factor_gasto(jugador: dict, mod_clima: float) -> float:
    base = (jugador.get("_base") or {}).get("resistencia", jugador.get("resistencia", 60)) or 60
    factor = max(0.5, 1.0 - (float(base) - RESISTENCIA_REFERENCIA) * SENSIBILIDAD_RESISTENCIA)
    if jugador.get("linea_partido") == 1:
        factor *= FACTOR_PORTERO
    return factor * (mod_clima or 1.0)


def _refrescar(jugador: dict) -> None:
    e = jugador.get("energia", ENERGIA_INICIAL)
    m, m_def = multiplicador(e), multiplicador(e, PERDIDA_DEFENSIVA)
    # Ajuste del DT (services/tecnicos.py): {general, ataque, defensa} en puntos, después del cansancio
    aj = jugador.get("_ajuste") or {}
    general, ataque, defensa = aj.get("general", 0.0), aj.get("ataque", 0.0), aj.get("defensa", 0.0)
    for a, v in (jugador.get("_base") or {}).items():
        valor = v * (m_def if a in ATRIBUTOS_DEFENSIVOS else m)
        if aj:
            valor += general + (ataque if a in ATRIBUTOS_ATAQUE_DT else defensa if a in ATRIBUTOS_DEFENSA_DT else 0.0)
        jugador[a] = round(valor, 2)


def refrescar(jugador: dict) -> None:
    """Vuelve a calcular los atributos del partido (después de cambiar jugador['_ajuste'])."""
    if "_base" in jugador:
        _refrescar(jugador)


def _gastar(jugador: dict, cantidad: float, mod_clima: float) -> bool:
    """Descuenta energía; devuelve True si este gasto la hizo cruzar UMBRAL_AVISO (para narrarlo una sola vez)."""
    if "_base" not in jugador:
        iniciar(jugador)
    antes = jugador["energia"]
    jugador["energia"] = max(0.0, antes - cantidad * _factor_gasto(jugador, mod_clima))
    _refrescar(jugador)
    if not jugador["_avisado"] and jugador["energia"] < UMBRAL_AVISO <= antes and jugador.get("linea_partido") != 1:
        jugador["_avisado"] = True
        return True
    return False


def paso_del_tiempo(en_cancha: list, segundos: float, mod_clima: float = 1.0) -> list:
    """Gasto por minutos jugados de todos los que están en cancha. Devuelve a los que acaban de 'fundirse'."""
    if segundos <= 0:
        return []
    return [j for j in en_cancha if _gastar(j, GASTO_POR_MINUTO * segundos / 60.0, mod_clima)]


def accion(jugador: dict, tipo: str, mod_clima: float = 1.0) -> bool:
    """Gasto extra por protagonizar una acción. Devuelve True si cruzó el umbral de aviso."""
    if not jugador:
        return False
    return _gastar(jugador, COSTO_ACCION.get(tipo, 0.2), mod_clima)


def peso_para_salir(jugador: dict) -> float:
    """Peso al elegir a quién sacar en un cambio: el más cansado es mucho más probable."""
    return 1.0 + (ENERGIA_INICIAL - jugador.get("energia", ENERGIA_INICIAL)) ** 2 / 100.0
