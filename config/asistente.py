"""
Reglas del asistente virtual "El Profe" (services/asistente_*.py, vista /asistente).

El usuario paga con su saldo un escaneo de todo lo suyo y recibe consejos accionables que enlazan a la vista del
módulo (el Profe nunca compra/vende por él). Tres niveles: cuanto más se paga, más módulos se analizan a fondo,
más consejos entran y más números se muestran. Lo GRATIS (check-in, recompensas, sobres regalados) sale siempre y
no ocupa cupo. Sin spoilers: solo datos públicos (poder/Elo, estado del torneo, carteras propias), nunca el
resultado de un partido sin finalizar ni el que está en transmisión.
"""

# Orden = profundidad. 'horizonte' = cuántos partidos próximos mira. 'detalle': basico (qué y por qué),
# numeros (+ probabilidad y ganancia estimada), completo (+ riesgo, prioridad y plan de la jornada).
NIVELES_ASISTENTE = {
    "VISTAZO": {
        "codigo": "VISTAZO", "nombre": "Vistazo", "precio": 75, "max_consejos": 3, "horizonte": 10, "detalle": "basico",
        "icono": "bi-eye-fill", "color": "#38bdf8",
        "resumen": "Lo urgente de tus carteras y lo que tienes gratis para cobrar.",
    },
    "ANALISIS": {
        "codigo": "ANALISIS", "nombre": "Análisis", "precio": 250, "max_consejos": 6, "horizonte": 20, "detalle": "numeros",
        "icono": "bi-graph-up-arrow", "color": "#22c55e",
        "resumen": "Más oportunidades en quinielas, selecciones y Once Ideal, con probabilidades y ganancia estimada.",
    },
    "PROFUNDO": {
        "codigo": "PROFUNDO", "nombre": "Informe profundo", "precio": 600, "max_consejos": 10, "horizonte": 40, "detalle": "completo",
        "icono": "bi-gem", "color": "#facc15",
        "resumen": "Todo el juego: sedes, álbum, Juego en Vivo, corporativo y bolsa, con valor esperado y plan de la jornada.",
    },
}
ORDEN_NIVELES = ["VISTAZO", "ANALISIS", "PROFUNDO"]

VISTAZO_GRATIS_POR_DIA = 1          # el primer Vistazo de cada día no se cobra
TOPE_CONSULTAS_PAGAS_DIA = 6        # anti-spam: consultas cobradas por día
HISTORIAL_VISTA = 10                # consultas que muestra el historial

# Módulos que escanea: nombre, ícono, color, permiso (config/secciones.py) y el nivel desde el que se analiza a fondo
# (los riesgos/pendientes de cada módulo salen desde el Vistazo; ver 'nivel_minimo' de cada consejo).
MODULOS_ASISTENTE = {
    "misiones":      {"nombre": "Misiones",         "icono": "bi-calendar-check-fill", "color": "#facc15", "permiso": "misiones",     "url": "/misiones/",              "profundo_desde": "VISTAZO"},
    "niveles":       {"nombre": "Niveles",          "icono": "bi-award-fill",          "color": "#f59e0b", "permiso": "niveles",      "url": "/niveles/",               "profundo_desde": "VISTAZO"},
    "selecciones":   {"nombre": "Selecciones",      "icono": "bi-briefcase-fill",      "color": "#22c55e", "permiso": "selecciones",  "url": "/selecciones/portafolio", "profundo_desde": "ANALISIS"},
    "once_ideal":    {"nombre": "Once Ideal",       "icono": "bi-stars",               "color": "#a78bfa", "permiso": "once_ideal",   "url": "/once-ideal/",            "profundo_desde": "ANALISIS"},
    "quinielas":     {"nombre": "Quinielas",        "icono": "bi-ticket-perforated",   "color": "#38bdf8", "permiso": "quinielas",    "url": "/quinielas/",             "profundo_desde": "ANALISIS"},
    "juego_en_vivo": {"nombre": "Juego en Vivo",    "icono": "bi-controller",          "color": "#f472b6", "permiso": "juego_en_vivo", "url": "/juegos/",               "profundo_desde": "PROFUNDO"},
    "sedes":         {"nombre": "Sedes",            "icono": "bi-geo-alt-fill",        "color": "#fb923c", "permiso": "sedes",        "url": "/sedes/directorio",       "profundo_desde": "PROFUNDO"},
    "album":         {"nombre": "Álbum",            "icono": "bi-collection-fill",     "color": "#2dd4bf", "permiso": "album",        "url": "/album-estampas/sobres",  "profundo_desde": "PROFUNDO"},
    "corporativo":   {"nombre": "Corporativo",      "icono": "bi-buildings-fill",      "color": "#60a5fa", "permiso": "corporativos", "url": "/corporativo/",           "profundo_desde": "PROFUNDO"},
}

# Tipos de consejo (orden de aparición en el informe)
TIPOS_CONSEJO = {
    "URGENTE":     {"nombre": "Urgente",       "icono": "bi-exclamation-octagon-fill", "color": "#ef4444"},
    "OPORTUNIDAD": {"nombre": "Oportunidades", "icono": "bi-lightning-charge-fill",    "color": "#22c55e"},
    "GRATIS":      {"nombre": "Gratis",        "icono": "bi-gift-fill",                "color": "#facc15"},
}

# Peso de la confianza en la prioridad y bono por urgencia (services/asistente_reglas.py)
PESO_CONFIANZA = {"alta": 1.0, "media": 0.7, "baja": 0.45}
BONO_URGENTE = 100000
PUNTOS_POR_URGENCIA = 40            # urgencia 0-100 → hasta 4000 de prioridad extra

# Umbrales de los analizadores
ELO_FAVORITO_CLARO = 70.0           # % de victoria para recomendar una quiniela
TOPE_CAMBIOS_AVISO = 4              # cambios gratis del Once Ideal desde los que se avisa que se pierden

# Modelo de partido del Profe (services/asistente_reglas.probabilidades_partido). El favoritismo sale del 'poder' con la
# misma escala Elo del Juego en Vivo (ESCALA_PODER), pero las probabilidades se ACHICAN: medido fuera de muestra sobre
# los 415 partidos del Mundial (oct 2026, forma previa a cada partido), aun con mucha diferencia el favorito gana
# ~55%, empata ~20% y pierde ~25%. El 'poder' se recalcula con los mismos resultados, así que leído en crudo promete
# de más (91% en apariencia). Recalibrar si el motor empieza a distinguir más a los equipos.
ESCALA_PODER = 100.0
FAVORITO_GANA = (0.36, 0.22)        # base + pendiente × x  (x = 0 parejo … 1 máximo favoritismo)
EMPATE = (0.30, -0.10)
