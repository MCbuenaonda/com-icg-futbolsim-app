"""
Catálogo de FORMACIONES (esquemas tácticos). Lo usan services/formaciones.py (efecto en los duelos del motor),
services/tecnicos.py (cómo elige el DT) y las vistas.

Cada esquema:
  lineas   la línea (1 POR, 2 DEF, 3 MED, 4 DEL) de cada puesto granular posicion_id 1..11
           (1 POR, 2 DFI, 3 DFD, 4 LI, 5 LD, 6 MI, 7 MC, 8 MD, 9 EI, 10 DC, 11 ED; colección `posiciones`).
  postura  -1 (muy defensiva) .. +1 (muy ofensiva): mueve la frecuencia de tiros y pases profundos.
  perfil   -1..+1 por aspecto del juego; cada punto vale ESCALA_PERFIL puntos de atributo en el duelo que corresponde:
           posesion (pases en salida y en el medio), progresion (pase profundo, regate hacia el área),
           remate (tiro), cierre (defender el área propia), presion (recuperar en campo rival y en el medio),
           aereo (córners y balón parado).
Calibrado con Monte Carlo (calibrar_formaciones.py): goles y tarjetas por partido del torneo sin cambio, ningún esquema
dominante («piedra, papel o tijera») y una elección óptima frente al rival vale ~5-8 puntos de probabilidad de ganar.
"""

FORMACIONES = {
    "3-4-3": {"nombre": "3-4-3", "postura": 1.0, "etiqueta": "Muy ofensiva",
              "lineas": [1, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4],
              "perfil": {"posesion": 0.0, "progresion": 0.6, "remate": 0.7, "cierre": -0.8, "presion": 0.6, "aereo": -0.2},
              "fuerte": "remate y presión arriba", "debil": "la espalda de la defensa"},
    "4-3-3": {"nombre": "4-3-3", "postura": 0.6, "etiqueta": "Ofensiva",
              "lineas": [1, 2, 2, 2, 2, 3, 3, 3, 4, 4, 4],
              "perfil": {"posesion": 0.1, "progresion": 0.7, "remate": 0.4, "cierre": -0.3, "presion": 0.4, "aereo": 0.0},
              "fuerte": "progresión por las bandas", "debil": "el medio contra cinco volantes"},
    "4-2-3-1": {"nombre": "4-2-3-1", "postura": 0.3, "etiqueta": "Neutral ofensiva",
                "lineas": [1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 3],
                "perfil": {"posesion": 0.4, "progresion": 0.4, "remate": 0.3, "cierre": -0.1, "presion": 0.1, "aereo": -0.2},
                "fuerte": "creación entre líneas", "debil": "las bandas"},
    "4-4-2": {"nombre": "4-4-2", "postura": 0.0, "etiqueta": "Neutral",
              "lineas": [1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4],
              "perfil": {"posesion": -0.3, "progresion": 0.0, "remate": 0.1, "cierre": 0.4, "presion": 0.0, "aereo": 0.3},
              "fuerte": "equilibrio y cierre en zona propia", "debil": "la posesión"},
    "3-5-2": {"nombre": "3-5-2", "postura": 0.0, "etiqueta": "Neutral",
              "lineas": [1, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4],
              "perfil": {"posesion": 0.7, "progresion": 0.1, "remate": 0.0, "cierre": -0.2, "presion": 0.2, "aereo": 0.0},
              "fuerte": "la posesión en el medio", "debil": "las bandas en defensa"},
    "4-1-4-1": {"nombre": "4-1-4-1", "postura": -0.3, "etiqueta": "Neutral defensiva",
                "lineas": [1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 3],
                "perfil": {"posesion": 0.3, "progresion": -0.2, "remate": -0.2, "cierre": 0.4, "presion": 0.2, "aereo": 0.0},
                "fuerte": "la intercepción en el medio", "debil": "poca gente arriba"},
    "4-5-1": {"nombre": "4-5-1", "postura": -0.6, "etiqueta": "Defensiva",
              "lineas": [1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 3],
              "perfil": {"posesion": -0.2, "progresion": 0.2, "remate": -0.4, "cierre": 0.6, "presion": -0.3, "aereo": 0.1},
              "fuerte": "el bloque medio y el contragolpe", "debil": "el remate"},
    "5-3-2": {"nombre": "5-3-2", "postura": -1.0, "etiqueta": "Muy defensiva",
              "lineas": [1, 2, 2, 2, 2, 2, 3, 3, 3, 4, 4],
              "perfil": {"posesion": -0.4, "progresion": 0.0, "remate": -0.3, "cierre": 0.9, "presion": -0.5, "aereo": 0.6},
              "fuerte": "el área propia y el juego aéreo", "debil": "la posesión y el gol"},
}
ESQUEMAS = list(FORMACIONES)

# Cada aspecto del perfil se centra en 0 PONDERADO por cuánto usan los DT cada esquema (medido con calibrar_formaciones.py
# sobre las decisiones reales): diferencian a los esquemas entre sí, pero en promedio el torneo no cambia. Sin esto los
# perfiles sumaban más ataque que defensa (+6,5% de goles); centrados por igual (sin ponderar) quedaba +5%.
USO_REFERENCIA = {"4-4-2": 162, "4-2-3-1": 145, "4-3-3": 140, "4-1-4-1": 106, "3-5-2": 103, "4-5-1": 81, "5-3-2": 33, "3-4-3": 30}
_total_uso = sum(USO_REFERENCIA.values())
for _aspecto in ("posesion", "progresion", "remate", "cierre", "presion", "aereo"):
    _media = sum(FORMACIONES[e]["perfil"][_aspecto] * w for e, w in USO_REFERENCIA.items()) / _total_uso
    for _f in FORMACIONES.values():
        _f["perfil"][_aspecto] = round(_f["perfil"][_aspecto] - _media, 3)
POSTURA_REFERENCIA = round(sum(FORMACIONES[e]["postura"] * w for e, w in USO_REFERENCIA.items()) / _total_uso, 3)

# --- Efecto en el motor (puntos de atributo en resolver_duelo) ---------------------------------------
ESCALA_PERFIL = 5.0               # un perfil de +1 = +5 puntos de atributo en su duelo
PUNTOS_SUPERIORIDAD = 2.0         # por jugador de más en la zona del duelo (contra lo normal de esa zona)
TOPE_SUPERIORIDAD = 2             # jugadores de diferencia que cuentan como máximo
# Inferioridad numérica (expulsión o lesionado sin cambio): el equipo con menos jugadores de campo pierde estos puntos
# en TODOS sus duelos, en cualquier zona (cubre más terreno con menos gente); por jugador que le falta: con la pelota
# (_ATAQUE) y defendiendo (_DEFENSA, pesa más: le sobran rivales sin marca). Más el desgaste extra
# (FACTOR_DESGASTE_INFERIORIDAD). Calibrado con calibrar_inferioridad.py --diez contra el fútbol real (con 10 se recibe
# ~50% más goles y se anota ~30% menos).
PUNTOS_INFERIORIDAD_ATAQUE = 18.0
PUNTOS_INFERIORIDAD_DEFENSA = 28.0
TOPE_INFERIORIDAD = 3
JUGADORES_DE_CAMPO = 10
FACTOR_DESGASTE_INFERIORIDAD = 0.15   # +15% de gasto por minuto por jugador que falta
# Extremos en los esquemas de dos puntas: en el catálogo el extremo DERECHO es el segundo delantero y el izquierdo
# juega de medio (asimétrico: el ED anotaba ~4 veces más que el EI). Cada equipo sortea en cada partido cuál de los
# dos va arriba (espejo), así se reparte.
SLOTS_EXTREMOS = (9, 11)   # EI, ED (posicion_id = slot)
# Lo "normal" en cada zona (4-4-2 contra 4-4-2), desde el equipo con la pelota: en su salida (defensa) sus defensas
# contra los delanteros rivales; en el medio, medios contra medios; en ataque, sus delanteros contra los defensas rivales.
LINEAS_DUELO = {"defensa": (2, 4), "medio": (3, 3), "ataque": (4, 2)}
BASE_SUPERIORIDAD = {"defensa": 2, "medio": 0, "ataque": -2}
# Postura: cuánto mueve la frecuencia de tiros (zona de ataque) y de pases profundos (medio) por punto de postura
POSTURA_TIRO = 0.12
POSTURA_PROFUNDO = 0.08
# Contragolpe: el equipo más defensivo, al salir contra uno más ofensivo, gana en el pase profundo y el regate (espacios
# a la espalda): puntos por cada punto de diferencia de postura. Es lo que hace que lo ofensivo no domine siempre.
CONTRAGOLPE = 6.0

# --- Cómo elige el DT ---------------------------------------------------------------------------------
# Preferencias por estilo (sobre los 8 esquemas): el punto de partida antes del contexto
PREFERENCIAS_ESTILO = {
    "ofensivo": {"3-4-3": 22, "4-3-3": 30, "4-2-3-1": 20, "4-4-2": 10, "3-5-2": 8, "4-1-4-1": 5, "4-5-1": 3, "5-3-2": 2},
    "equilibrado": {"3-4-3": 6, "4-3-3": 14, "4-2-3-1": 18, "4-4-2": 18, "3-5-2": 18, "4-1-4-1": 12, "4-5-1": 8, "5-3-2": 6},
    "defensivo": {"3-4-3": 2, "4-3-3": 6, "4-2-3-1": 8, "4-4-2": 18, "3-5-2": 10, "4-1-4-1": 18, "4-5-1": 20, "5-3-2": 18},
}
ANCHO_POSTURA = 0.55              # qué tanto pesa acercarse a la postura que pide el partido
PESO_VENTAJA_RIVAL = 0.9          # cuánto busca ganarle el medio/las bandas al esquema probable del rival (x lectura)
MALA_RACHA = 0.30                 # forma (puntos de los últimos 5 / 15) que lo hace cambiar de esquema
BUENA_RACHA = 0.60                # forma que lo hace repetir el que le viene funcionando
MINIMO_HISTORIAL = 3              # partidos con un esquema para que su rendimiento cuente
