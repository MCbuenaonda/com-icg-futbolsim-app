"""
Catálogo de ESPECIALIDADES de los jugadores (campo permanente jugadores.especialidades: [codigo, ...]).
Lógica en services/especialidades.py (puntos en cada duelo) y asignación en asignar_especialidades.py.

Cada especialidad:
  nombre, icono (Bootstrap Icons), descripcion (lo que hace, para la ficha)
  lineas     líneas naturales donde se asigna (PORTERO/DEFENSA/MEDIO/DELANTERO; config/fantasy.LINEA_DE_POSICION)
  atributos  atributos del jugador que la sostienen (la asignación prefiere a quien los tiene más altos)
  efectos    [{accion, rol, factor, zonas?, linea_partido?}] → factor × PUNTOS_ESPECIALIDAD puntos de atributo en el duelo
             acciones: pase, pase_profundo, regate, tiro (va a puerta), gol (remate contra el arquero),
                       aereo (córner), penal, '*' (todas); rol: atk (el que la intenta) / def (el que la defiende) / '*'
  condicion  'revulsivo' (solo si entró de cambio) o 'partido_grande' (solo en eliminación directa / serie)
  peso       frecuencia relativa al repartirla (1 por defecto)
  narrar     frase para cuando la especialidad decide un gol o una atajada ({j} = jugador)
Penales y Tiros libres ya tenían efecto propio (especialista_penales/especialista_tiros_libres en simular_service):
sus efectos aquí quedan vacíos y la asignación mantiene sincronizados esos booleanos.
Calibrado con calibrar_especialidades.py: goles y tarjetas del torneo sin cambio, mejora visible en su jugada.
"""

PUNTOS_ESPECIALIDAD = 5.0      # +5 puntos de atributo en su duelo (impacto moderado, como el pie hábil)
FACTOR_PULMON = 0.85           # el Pulmón gasta un 15% menos de energía

ESPECIALIDADES = {
    # --- Porteros ---
    "atajapenales": {"nombre": "Atajapenales", "icono": "bi-hand-index-thumb", "lineas": ["PORTERO"],
                     "atributos": ["agilidad", "concentracion", "anticipacion"],
                     "descripcion": "Adivina el lado: ataja más penales, en el partido y en la tanda.",
                     "efectos": [{"accion": "penal", "rol": "def", "factor": 1.4}],
                     "narrar": "{j}, el atajapenales, vuelve a adivinar"},
    "reflejos": {"nombre": "Reflejos felinos", "icono": "bi-lightning", "lineas": ["PORTERO"],
                 "atributos": ["agilidad", "concentracion"],
                 "descripcion": "Reacciona rápido: ataja más remates, tiros libres y cabezazos.",
                 "efectos": [{"accion": "gol", "rol": "def", "factor": 1.0}],
                 "narrar": "Los reflejos de {j} salvan a su equipo"},
    "dominio_area": {"nombre": "Dominio del área", "icono": "bi-bounding-box", "lineas": ["PORTERO"],
                     "atributos": ["juego_aereo", "fuerza_fisica", "compostura"],
                     "descripcion": "Sale por arriba: su equipo despeja más córners.",
                     "efectos": [{"accion": "aereo", "rol": "def", "factor": 1.0}],
                     "narrar": "{j} manda en su área"},
    # --- Defensas ---
    "marcador": {"nombre": "Marcador implacable", "icono": "bi-shield-fill-check", "lineas": ["DEFENSA"],
                 "atributos": ["fuerza_fisica", "anticipacion", "agresividad"],
                 "descripcion": "Difícil de pasar: frena más regates.",
                 "efectos": [{"accion": "regate", "rol": "def", "factor": 1.0}],
                 "narrar": "{j} no deja pasar a nadie"},
    "anticipacion": {"nombre": "Anticipación", "icono": "bi-eye-fill", "lineas": ["DEFENSA", "MEDIO"],
                     "atributos": ["anticipacion", "concentracion", "vision_juego"],
                     "descripcion": "Lee la jugada antes: corta más pases y pases profundos.",
                     "efectos": [{"accion": "pase", "rol": "def", "factor": 0.8}, {"accion": "pase_profundo", "rol": "def", "factor": 1.0}],
                     "narrar": "{j} se anticipa"},
    "torre": {"nombre": "Torre", "icono": "bi-building", "lineas": ["DEFENSA"],
              "atributos": ["juego_aereo", "fuerza_fisica"],
              "descripcion": "Gana por arriba en las dos áreas: córners a favor y en contra.",
              "efectos": [{"accion": "aereo", "rol": "*", "factor": 1.0}],
              "narrar": "{j}, una torre, gana por arriba"},
    "lateral_ida_vuelta": {"nombre": "Lateral de ida y vuelta", "icono": "bi-arrow-left-right", "lineas": ["DEFENSA"],
                           "atributos": ["velocidad", "resistencia", "precision_pase"],
                           "descripcion": "Sale jugando: mejores pases desde atrás y en profundidad.",
                           "efectos": [{"accion": "pase", "rol": "atk", "factor": 1.0, "zonas": ["defensa"]},
                                       {"accion": "pase_profundo", "rol": "atk", "factor": 0.6}],
                           "narrar": "{j} pasa al ataque"},
    # --- Medios ---
    "organizador": {"nombre": "Organizador", "icono": "bi-diagram-3-fill", "lineas": ["MEDIO"],
                    "atributos": ["vision_juego", "precision_pase"],
                    "descripcion": "Pone el pase filtrado: mejora el pase profundo y el pase en el medio.",
                    "efectos": [{"accion": "pase_profundo", "rol": "atk", "factor": 1.0},
                                {"accion": "pase", "rol": "atk", "factor": 0.6, "zonas": ["medio"]}],
                    "narrar": "Pase filtrado de {j}, el organizador"},
    "recuperador": {"nombre": "Recuperador", "icono": "bi-arrow-repeat", "lineas": ["MEDIO", "DEFENSA"],
                    "atributos": ["anticipacion", "agresividad", "resistencia"],
                    "descripcion": "Presiona y roba: corta más pases y regates en el medio.",
                    "efectos": [{"accion": "pase", "rol": "def", "factor": 1.0, "zonas": ["medio"]},
                                {"accion": "regate", "rol": "def", "factor": 0.8, "zonas": ["medio"]}],
                    "narrar": "{j} recupera la pelota"},
    "llegador": {"nombre": "Llegador", "icono": "bi-bullseye", "lineas": ["MEDIO"],
                 "atributos": ["precision_tiro", "fuerza_disparo", "velocidad"],
                 "descripcion": "Llega al área desde atrás: remata mejor cuando juega en el medio.",
                 "efectos": [{"accion": "tiro", "rol": "atk", "factor": 1.0, "linea_partido": [3]},
                             {"accion": "gol", "rol": "atk", "factor": 0.6, "linea_partido": [3]}],
                 "narrar": "{j} llega desde atrás"},
    "pulmon": {"nombre": "Pulmón", "icono": "bi-heart-pulse-fill", "lineas": ["MEDIO", "DEFENSA"],
               "atributos": ["resistencia", "fuerza_fisica"],
               "descripcion": "Corre todo el partido: se cansa un 15% menos.",
               "efectos": [], "narrar": None},
    # --- Delanteros ---
    "definidor": {"nombre": "Definidor", "icono": "bi-crosshair", "lineas": ["DELANTERO"],
                  "atributos": ["precision_tiro", "compostura", "fuerza_disparo"],
                  "descripcion": "Frío frente al arco: más remates a puerta y más goles.",
                  "efectos": [{"accion": "tiro", "rol": "atk", "factor": 1.0}, {"accion": "gol", "rol": "atk", "factor": 0.8}],
                  "narrar": "{j}, un definidor de los que no perdonan"},
    "cabeceador": {"nombre": "Cabeceador", "icono": "bi-arrow-up-circle-fill", "lineas": ["DELANTERO", "DEFENSA"],
                   "atributos": ["juego_aereo", "fuerza_fisica"],
                   "descripcion": "Peligro en los córners: conecta y cabecea mejor.",
                   "efectos": [{"accion": "aereo", "rol": "atk", "factor": 1.2}],
                   "narrar": "{j}, el cabeceador, gana por arriba"},
    "regateador": {"nombre": "Regateador", "icono": "bi-shuffle", "lineas": ["DELANTERO", "MEDIO"],
                   "atributos": ["regate", "agilidad", "control_balon"],
                   "descripcion": "Desequilibra en el uno contra uno: gana más regates.",
                   "efectos": [{"accion": "regate", "rol": "atk", "factor": 1.0}],
                   "narrar": "{j} deja rivales en el camino"},
    "contragolpeador": {"nombre": "Contragolpeador", "icono": "bi-wind", "lineas": ["DELANTERO", "MEDIO"],
                        "atributos": ["velocidad", "agilidad"],
                        "descripcion": "Letal saliendo rápido: mejor pase profundo y regate desde atrás.",
                        "efectos": [{"accion": "pase_profundo", "rol": "atk", "factor": 0.8},
                                    {"accion": "regate", "rol": "atk", "factor": 0.8, "zonas": ["defensa", "medio"]}],
                        "narrar": "{j} sale disparado al contragolpe"},
    # --- Cualquier línea ---
    "penales": {"nombre": "Penales", "icono": "bi-record-circle", "lineas": ["DEFENSA", "MEDIO", "DELANTERO"],
                "atributos": ["precision_tiro", "compostura"],
                "descripcion": "Primero en la fila para cobrar penales y más preciso desde los once metros.",
                "efectos": [], "booleano": "especialista_penales", "narrar": None},
    "tiros_libres": {"nombre": "Tiros libres", "icono": "bi-flag-fill", "lineas": ["DEFENSA", "MEDIO", "DELANTERO"],
                     "atributos": ["precision_tiro", "fuerza_disparo"],
                     "descripcion": "Cobra los tiros libres directos y les da más precisión.",
                     "efectos": [], "booleano": "especialista_tiros_libres", "narrar": None},
    "revulsivo": {"nombre": "Revulsivo", "icono": "bi-lightning-charge-fill", "lineas": ["MEDIO", "DELANTERO"],
                  "atributos": ["velocidad", "regate", "agilidad"],
                  "descripcion": "Cambia el partido desde el banco: rinde más cuando entra de cambio.",
                  "efectos": [{"accion": "*", "rol": "atk", "factor": 0.7}], "condicion": "revulsivo", "peso": 0.7,
                  "narrar": "{j} entra y lo cambia todo"},
    "partidos_grandes": {"nombre": "Partidos grandes", "icono": "bi-trophy-fill", "lineas": ["PORTERO", "DEFENSA", "MEDIO", "DELANTERO"],
                         "atributos": ["compostura", "concentracion"],
                         "descripcion": "Aparece cuando más importa: rinde más en eliminación directa.",
                         "efectos": [{"accion": "*", "rol": "*", "factor": 0.5}], "condicion": "partido_grande", "peso": 0.4,
                         "narrar": "{j} aparece en el partido grande"},
}

# --- Reparto con PARIDAD: el mismo cupo para todas las selecciones (asignar_especialidades.py) ---
CUPO_POR_LINEA = {"PORTERO": 2, "DEFENSA": 5, "MEDIO": 5, "DELANTERO": 4}   # 16 entre los 22 actuales
CUPO_LEYENDAS_POR_LINEA = {"PORTERO": 1, "DEFENSA": 3, "MEDIO": 3, "DELANTERO": 2}   # 9 entre las 11 leyendas
MAXIMO_POR_JUGADOR = 3
# Probabilidad de que un jugador que ya tiene k especialidades reciba otra (frena que se concentren en pocos)
PESO_POR_CANTIDAD = {0: 1.0, 1: 0.45, 2: 0.15}

# =====================================================================================================================
# EVOLUCIÓN: se ganan y se pierden con el rendimiento (services/especialidades.evaluar + especialidades_service)
# =====================================================================================================================
# Cada partido jugado deja un resumen en jugadores.esp_ventana (los últimos VENTANA_GUARDADA). Claves del resumen:
#   g goles, a asistencias, r recuperaciones, rg regates exitosos, at atajadas, ap penales atajados, gco goles de córner,
#   gp goles de penal, gtl goles de tiro libre, cal calificación, sub entró de cambio, comp jugó completo, en energía
#   final, v valla invicta (portero/defensa), gr partido grande (eliminación directa), ga = g + a, sub_ga entró y
#   anotó o asistió, gr_ok partido grande con gol o calificación alta
# Reglas: {"n": partidos de la ventana, "lineas": [...], y condiciones}
#   "suma": {clave: mínimo}  "media": {clave: mínimo | {LINEA: mínimo}}  "cuenta": {clave: mínimo de partidos con valor > 0}
#   Pérdida: "suma_max"/"media_max"/"cuenta_max" (máximos) y, salvo "sin_rating", calificación media < RATING_PIERDE.
#   "solo_rating": X = se pierde solo con calificación media < RATING_PIERDE − X (roles que dependen de que haya
#   penales o tiros libres: no se pierden por falta de oportunidades). "filtro": "sub"/"gr" = la ventana cuenta solo los
#   partidos en que entró de cambio / de eliminación directa. Las LEYENDAS no evolucionan (atributos de 80: acapararían).
# Umbrales por línea medidos con partidos simulados (delanteros ~0,6 goles y 12,5 regates por partido; defensas ~10
# recuperaciones; porteros ~4,3 atajadas; la calificación media cambia por línea).
VENTANA_GUARDADA = 8
PARTIDOS_GRACIA = 6            # una especialidad no se pierde antes de jugar 6 partidos con ella
GANADAS_POR_PARTIDO = 1        # como máximo una nueva por partido
RATING_PIERDE = {"PORTERO": 6.8, "DEFENSA": 6.15, "MEDIO": 6.35, "DELANTERO": 7.0}

GANAR = {
    "definidor":          {"n": 4, "lineas": ["DELANTERO"], "suma": {"g": 5}},
    "llegador":           {"n": 5, "lineas": ["MEDIO"], "suma": {"g": 2}},
    "organizador":        {"n": 5, "lineas": ["MEDIO"], "suma": {"a": 2}},
    "lateral_ida_vuelta": {"n": 5, "lineas": ["DEFENSA"], "suma": {"a": 2}},
    "regateador":         {"n": 4, "lineas": ["DELANTERO", "MEDIO"], "media": {"rg": {"DELANTERO": 18, "MEDIO": 6.5}}},
    "recuperador":        {"n": 4, "lineas": ["MEDIO", "DEFENSA"], "media": {"r": {"MEDIO": 7, "DEFENSA": 15}}},
    "anticipacion":       {"n": 4, "lineas": ["DEFENSA", "MEDIO"], "media": {"r": {"DEFENSA": 13, "MEDIO": 6}, "cal": {"DEFENSA": 7.1, "MEDIO": 7.3}}},
    "marcador":           {"n": 5, "lineas": ["DEFENSA"], "cuenta": {"v": 3}, "media": {"r": 11}},
    "torre":              {"n": 6, "lineas": ["DEFENSA"], "suma": {"gco": 1}, "cuenta": {"v": 2}},
    "cabeceador":         {"n": 6, "lineas": ["DELANTERO", "DEFENSA"], "suma": {"gco": 1, "g": 2}},
    "reflejos":           {"n": 4, "lineas": ["PORTERO"], "media": {"at": 6.5, "cal": 7.8}},
    "dominio_area":       {"n": 5, "lineas": ["PORTERO"], "cuenta": {"v": 3}},
    "atajapenales":       {"n": 6, "lineas": ["PORTERO"], "suma": {"ap": 2}},
    "pulmon":             {"n": 5, "lineas": ["MEDIO", "DEFENSA"], "cuenta": {"comp_fuerte": 4}},
    "revulsivo":          {"n": 4, "lineas": ["MEDIO", "DELANTERO"], "cuenta": {"sub_ga": 2}, "filtro": "sub"},
    "partidos_grandes":   {"n": 3, "lineas": ["PORTERO", "DEFENSA", "MEDIO", "DELANTERO"], "cuenta": {"gr_ok": 2}, "filtro": "gr"},
    "contragolpeador":    {"n": 5, "lineas": ["DELANTERO", "MEDIO"], "suma": {"ga": 5}, "media": {"rg": {"DELANTERO": 15, "MEDIO": 5}}},
    "penales":            {"n": 6, "lineas": ["DEFENSA", "MEDIO", "DELANTERO"], "suma": {"gp": 3}},
    "tiros_libres":       {"n": 6, "lineas": ["DEFENSA", "MEDIO", "DELANTERO"], "suma": {"gtl": 2}},
}

PERDER = {
    "definidor":          {"n": 6, "suma_max": {"g": 0}},
    "llegador":           {"n": 6, "suma_max": {"g": 0}},
    "organizador":        {"n": 6, "suma_max": {"a": 0}},
    "lateral_ida_vuelta": {"n": 6, "suma_max": {"a": 0}},
    "regateador":         {"n": 6, "media_max": {"rg": {"DELANTERO": 7, "MEDIO": 1.5, "DEFENSA": 1}}},
    "recuperador":        {"n": 6, "media_max": {"r": {"MEDIO": 2.5, "DEFENSA": 7}}},
    "anticipacion":       {"n": 6, "media_max": {"r": {"MEDIO": 2.5, "DEFENSA": 7}}},
    "marcador":           {"n": 6, "cuenta_max": {"v": 0}},
    "torre":              {"n": 6, "cuenta_max": {"v": 0}},
    "cabeceador":         {"n": 6, "suma_max": {"gco": 0, "g": 0}},
    "reflejos":           {"n": 6, "media_max": {"at": 3.5}},
    "dominio_area":       {"n": 6, "cuenta_max": {"v": 0}},
    "atajapenales":       {"n": 6, "solo_rating": 0.5},
    "pulmon":             {"n": 6, "media_max": {"en": 35}, "sin_rating": True},
    "revulsivo":          {"n": 4, "cuenta_max": {"sub_ga": 0}, "filtro": "sub"},
    "partidos_grandes":   {"n": 3, "cuenta_max": {"gr_ok": 0}, "filtro": "gr"},
    "contragolpeador":    {"n": 6, "suma_max": {"ga": 0}},
    "penales":            {"n": 6, "solo_rating": 0.5},
    "tiros_libres":       {"n": 6, "solo_rating": 0.5},
}

# Motivos legibles (historial y ficha)
MOTIVO_GANAR = {
    "definidor": "{g} goles en sus últimos {n} partidos", "llegador": "{g} goles llegando desde el medio",
    "organizador": "{a} asistencias en sus últimos {n} partidos", "lateral_ida_vuelta": "{a} asistencias desde la defensa",
    "regateador": "{rg_m} regates por partido", "recuperador": "{r_m} recuperaciones por partido",
    "anticipacion": "{r_m} recuperaciones por partido y gran nivel", "marcador": "{v} vallas invictas y {r_m} recuperaciones",
    "torre": "gol de córner y {v} vallas invictas", "cabeceador": "{gco} goles de córner", "reflejos": "{at_m} atajadas por partido",
    "dominio_area": "{v} vallas invictas", "atajapenales": "{ap} penales atajados", "pulmon": "{comp_fuerte} partidos completos sin fundirse",
    "revulsivo": "decisivo {sub_ga} veces entrando de cambio", "partidos_grandes": "figura en {gr_ok} partidos de eliminación",
    "contragolpeador": "{ga} goles + asistencias y desborde", "penales": "{gp} goles de penal", "tiros_libres": "{gtl} goles de tiro libre",
}
MOTIVO_PERDER = "Rindió por debajo en sus últimos {n} partidos"

# --- Cambios del técnico: a quién mete según el partido (services/especialidades.peso_cambio) ---
PREFERENCIA_CAMBIO = {
    "perdiendo": ["definidor", "revulsivo", "regateador", "contragolpeador", "llegador", "cabeceador"],
    "ganando":   ["marcador", "anticipacion", "recuperador", "torre", "pulmon"],
    "empate":    ["revulsivo", "organizador", "pulmon"],
}
PESO_ESPECIALIDAD_CAMBIO = 2.5      # con lectura máxima, una especialidad buscada multiplica la chance de entrar por 3,5
MINUTO_CERRAR = 70                  # ganando desde aquí, el DT busca cerrar el partido
TEXTO_CAMBIO = {
    "perdiendo": "El técnico busca el gol y apuesta por su especialidad: {esp}.",
    "ganando": "El técnico quiere cerrar el partido y elige por su especialidad: {esp}.",
    "empate": "El técnico mueve el banco buscando su especialidad: {esp}.",
}

# --- Equilibrio entre selecciones: que nadie se vuelva invencible ni se desplome (ES.evolucionar_equipo) ---
# Una fuerza que regresa al centro: cuanto más arriba de su base está una selección, más le cuesta ganar una nueva y más
# fácil pierde las que no sostiene (y al revés). Más techo y piso de seguridad. Así, jugar más partidos (CONMEBOL ~18 de
# eliminatoria contra ~6 de OFC) solo hace que una selección llegue antes a su equilibrio, no que siga subiendo.
BASE_SELECCION = 16            # = suma de CUPO_POR_LINEA (los 22 actuales)
PISO_SELECCION = 10
TECHO_SELECCION = 22
EQUILIBRIO_UMBRAL = 0.05       # ×(1 + 0.05 · desvío) a los mínimos para ganar (acotado a 0,6..2)
EQUILIBRIO_RATING = 0.03       # + 0.03 · desvío a la calificación que hace perder una
