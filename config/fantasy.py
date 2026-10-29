"""
Reglas del Once Ideal (fantasy) v2: varios equipos por formación, pago por partido, Ojeador y forma del jugador.
Lógica en services/fantasy_service.py (equipos y pago) y services/fantasy_rendimiento.py (forma, ficha, Ojeador).
Calibrado con calibrar_fantasy.py (solo lectura): ver los números en CLAUDE.md.
"""
from config import formaciones as CF

# --- Equipos (escuadras) -------------------------------------------------------------------------------------------
# Se empieza con 1; los demás se desbloquean de a uno con saldo + jornadas jugadas con el equipo anterior.
# El desbloqueo es PERMANENTE (usuarios.fantasy_escuadras): restart_mundial borra los equipos, no los espacios.
ESCUADRAS_MAX = 4
COSTOS_ESCUADRA = {2: 550, 3: 650, 4: 750}
JORNADAS_PARA_DESBLOQUEAR = 3

# Cada equipo usa una formación distinta del catálogo del motor (config/formaciones.py): define cuántos jugadores van
# en cada línea. Cada jugador entra en la línea NATURAL de su posición (posicion_id de la colección 'posiciones').
LINEA_DE_POSICION = {1: "PORTERO", 2: "DEFENSA", 3: "DEFENSA", 4: "DEFENSA", 5: "DEFENSA",
                     6: "MEDIO", 7: "MEDIO", 8: "MEDIO", 9: "DELANTERO", 10: "DELANTERO", 11: "DELANTERO"}
LINEAS = ("PORTERO", "DEFENSA", "MEDIO", "DELANTERO")
_NOMBRE_LINEA = {1: "PORTERO", 2: "DEFENSA", 3: "MEDIO", 4: "DELANTERO"}


def cupos_formacion(esquema: str) -> dict:
    """{'PORTERO': 1, 'DEFENSA': n, 'MEDIO': n, 'DELANTERO': n} según las líneas del esquema."""
    datos = CF.FORMACIONES.get(esquema) or CF.FORMACIONES["4-3-3"]
    cupos = {l: 0 for l in LINEAS}
    for linea in datos["lineas"]:
        cupos[_NOMBRE_LINEA[linea]] += 1
    return cupos


FORMACIONES = list(CF.ESQUEMAS)
FORMACION_DEFAULT = "4-3-3"   # la única válida con un once de "1 por puesto" (el equipo viejo migra a esta)

# --- Pago por partido (saldo) --------------------------------------------------------------------------------------
# Cada partido que juega un jugador alineado paga: por jugar + por su desempeño (calificación del partido) + un % de
# sus puntos fantasy (con la postura de la formación). Con la estampa del jugador en el álbum, todo ×1.5.
# Por jugar, según la línea: el delantero y el medio cobran algo menos de base porque los goles ya les suman (así
# ninguna formación paga claramente más que otra; calibrar_fantasy.py). Recalibrado cuando los medios pasaron a anotar
# ~30% de los goles (antes 5%; el delantero cobraba 12): ~65 por jornada en las 8 formaciones.
PAGO_POR_PARTIDO = {"PORTERO": 25, "DEFENSA": 25, "MEDIO": 22, "DELANTERO": 20}
FRACCION_SUPLENTE = 0.5            # si entró de cambio
RATING_BASE_PAGO = 6.8             # = simular_service.RATING_BASE: desde ahí cada punto de calificación paga
PAGO_POR_PUNTO_RATING = 15
PORCENTAJE_MONTO_POR_PUNTOS = 0.20
# Postura de la formación (−1 muy defensiva .. +1 muy ofensiva): los goles y asistencias valen más en una ofensiva,
# la valla invicta vale más en una defensiva.
# Lo que deja en promedio un equipo armado con titulares de selecciones vivas por jornada (calibrar_fantasy.py: 65-67
# en cualquier formación). Lo usan la vista y El Profe para estimar cuándo se recupera un desbloqueo.
PAGO_ESPERADO_JORNADA = 65
POSTURA_GOL = 0.10
POSTURA_VALLA = 0.60

# --- Forma del jugador ---------------------------------------------------------------------------------------------
PARTIDOS_FORMA = 5                 # últimos partidos que cuentan para su nivel
MINIMO_PARTIDOS_FORMA = 2
NIVELES_FORMA = [                  # (percentil mínimo, código, etiqueta)
    (0.90, "racha", "En racha"),
    (0.70, "forma", "En forma"),
    (0.30, "regular", "Regular"),
    (0.00, "bajo", "Bajo"),
]

# --- Ojeador (sugerencias pagas, una posición) ---------------------------------------------------------------------
OJEADOR_NIVELES = {
    "basico": {"nombre": "Básico", "precio": 40, "desde": 0.50, "hasta": 0.75, "cantidad": 3,
               "texto": "Jugadores cumplidores (entre el 50% y el 75% de forma)"},
    "pro": {"nombre": "Pro", "precio": 120, "desde": 0.75, "hasta": 0.90, "cantidad": 4,
            "texto": "Jugadores en forma (entre el 75% y el 90%)"},
    "elite": {"nombre": "Élite", "precio": 300, "desde": 0.90, "hasta": 1.01, "cantidad": 5,
              "texto": "Lo mejor del momento (el 10% más en forma)"},
}
JUEGA_PRONTO_PARTIDOS = 60         # "juega pronto": su próximo partido está dentro de estos partidos del calendario
