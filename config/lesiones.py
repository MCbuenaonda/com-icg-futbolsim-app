"""
Lesiones de los jugadores (services/lesiones.py = lógica pura; services/lesiones_service.py = Mongo).

Dos orígenes durante el partido:
  contacto   después de una falta (más probable si el infractor es agresivo; mucho más con una roja directa)
  muscular   por cansancio: solo con poca energía (services/desgaste.py), más probable con la edad

Gravedad -> partidos de baja de su SELECCIÓN (se cumplen con los partidos que juega su selección):
  leve      0  (puede seguir jugando "tocado")
  moderada  1
  grave     2-3

Calibrado con calibrar_lesiones.py (solo lectura): ~0,3 lesiones por partido (~0,2 salen de la cancha), y los
goles por partido no cambian.
"""

# --- Probabilidades en el partido ---------------------------------------------------------------------------------
PROB_LESION_FALTA = 0.009          # por falta cometida, con un infractor de agresividad media (60)
FACTOR_ROJA_DIRECTA = 3.0          # una entrada de roja lastima mucho más seguido
AGRESIVIDAD_REFERENCIA = 60.0

UMBRAL_MUSCULAR = 55.0             # por encima de esta energía no hay lesiones musculares
PROB_MUSCULAR_MINUTO = 0.0012      # por minuto, con la energía en 0 (crece en proporción a lo que baja del umbral)
EDAD_RIESGO = 30                   # desde aquí cada año suma RIESGO_POR_ANIO
RIESGO_POR_ANIO = 0.06

PROB_SALE_LEVE = 0.45              # una lesión leve: a veces sale, a veces sigue "tocado"
ENERGIA_TOCADO = 15.0              # lo que pierde de energía el que sigue jugando con molestias
SEGUNDOS_ATENCION = (60, 120)      # el juego se detiene mientras lo atienden

# --- Gravedad -----------------------------------------------------------------------------------------------------
GRAVEDADES = {
    "leve": {"nombre": "Leve", "partidos": (0, 0), "icono": "bi-bandaid", "color": "info"},
    "moderada": {"nombre": "Moderada", "partidos": (1, 1), "icono": "bi-bandaid-fill", "color": "warning"},
    "grave": {"nombre": "Grave", "partidos": (2, 3), "icono": "bi-hospital", "color": "danger"},
}

# Tipo de lesión: peso al sortear y peso de cada gravedad posible
TIPOS = {
    "contacto": [
        {"codigo": "golpe_tobillo", "nombre": "golpe en el tobillo", "peso": 5, "gravedad": {"leve": 6, "moderada": 3, "grave": 1}},
        {"codigo": "esguince_tobillo", "nombre": "esguince de tobillo", "peso": 3, "gravedad": {"leve": 1, "moderada": 4, "grave": 3}},
        {"codigo": "golpe_rodilla", "nombre": "golpe en la rodilla", "peso": 3, "gravedad": {"leve": 4, "moderada": 3, "grave": 1}},
        {"codigo": "ligamentos_rodilla", "nombre": "lesión de ligamentos en la rodilla", "peso": 1, "gravedad": {"grave": 1}},
        {"codigo": "contusion_muslo", "nombre": "contusión en el muslo", "peso": 4, "gravedad": {"leve": 6, "moderada": 2}},
        {"codigo": "golpe_cabeza", "nombre": "golpe en la cabeza", "peso": 2, "gravedad": {"leve": 4, "moderada": 2}},
        {"codigo": "golpe_hombro", "nombre": "golpe en el hombro", "peso": 2, "gravedad": {"leve": 3, "moderada": 2, "grave": 1}},
    ],
    "muscular": [
        {"codigo": "calambres", "nombre": "calambres", "peso": 3, "gravedad": {"leve": 1}},
        {"codigo": "sobrecarga_gemelo", "nombre": "sobrecarga en el gemelo", "peso": 3, "gravedad": {"leve": 3, "moderada": 2}},
        {"codigo": "isquiotibial", "nombre": "molestia en el isquiotibial", "peso": 3, "gravedad": {"leve": 2, "moderada": 3, "grave": 1}},
        {"codigo": "desgarro_aductor", "nombre": "desgarro en el aductor", "peso": 1, "gravedad": {"moderada": 2, "grave": 2}},
        {"codigo": "cuadriceps", "nombre": "tirón en el cuádriceps", "peso": 2, "gravedad": {"leve": 2, "moderada": 2, "grave": 1}},
    ],
}

# --- Narración ----------------------------------------------------------------------------------------------------
TEXTOS_CONTACTO = [
    "{j} se queda en el piso tras la entrada y pide atención: {lesion}.",
    "Choque fuerte y {j} no se levanta. Entran las asistencias: {lesion}.",
    "{j} se duele después del golpe y el cuerpo médico lo revisa: {lesion}.",
]
TEXTOS_MUSCULAR = [
    "{j} se detiene de golpe y se toca la pierna: {lesion}.",
    "{j} no puede más: se tira al césped con {lesion}.",
    "Mala señal: {j} pide el cambio con gestos, {lesion}.",
]
TEXTO_SALE_CAMBIO = " No puede seguir y su DT prepara el cambio."
TEXTO_SALE_SIN_CAMBIO = " No puede seguir y, sin cambios disponibles, {equipo} se queda con uno menos."
TEXTO_SIGUE = " Le ponen hielo, vuelve a la cancha pero se le nota tocado."
TEXTO_SIGUE_SIN_CAMBIO = " Sin cambios disponibles, sigue en la cancha como puede."
TEXTO_PORTERO_SIGUE = " Sin cambios disponibles, sigue en el arco como puede."
