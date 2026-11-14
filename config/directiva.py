"""Presidentes de federación y líderes de la afición (barras): 211 de cada uno, FICTICIOS, uno por selección.

Colecciones permanentes `presidentes` y `lideres` (generar_directiva.py; `id` = id del país). Reaccionan tras los partidos con una cita corta
(`directiva_voces`) y mueven un poco dos cosas, siempre suave: el presidente la paciencia de la federación con su DT (la probabilidad de cese) y el líder
el crecimiento de aficionados de su selección y la presión que siente el DT. Sin efecto en el motor de partidos ni en tu dinero.
"""
ID_ESTAMPA_PRESIDENTE = 1000000   # estampa = base + id del país (Dorada, página «Federaciones»)
ID_ESTAMPA_LIDER = 1100000        # estampa = base + id del país (Dorada, página «Peñas»)

# Presidente de federación: `paciencia` se suma al factor 1,00 de la paciencia con el DT (más alto = tarda más en cesarlo)
RASGOS_PRESIDENTE = {
    "institucional": {"nombre": "Institucional", "icono": "bi-bank2", "paciencia": 0.10, "peso": 24,
                      "texto": "Respeta los procesos y protege al DT: tarda más en cambiarlo."},
    "ambicioso": {"nombre": "Ambicioso", "icono": "bi-rocket-takeoff-fill", "paciencia": -0.12, "peso": 20,
                  "texto": "Quiere resultados ya: si no llegan, cambia de técnico antes."},
    "austero": {"nombre": "Austero", "icono": "bi-piggy-bank-fill", "paciencia": 0.05, "peso": 18,
                "texto": "Cuida cada peso y no le gusta pagar un despido: aguanta un poco más."},
    "populista": {"nombre": "Populista", "icono": "bi-megaphone-fill", "paciencia": -0.06, "peso": 18,
                  "texto": "Se deja llevar por lo que pide la afición: si la tribuna aprieta, él también."},
    "reformista": {"nombre": "Reformista", "icono": "bi-diagram-3-fill", "paciencia": -0.03, "peso": 20,
                   "texto": "Siempre tiene un proyecto nuevo: le gustan los cambios, incluso el de técnico."},
}
# Líder de la afición: `pos`/`neg` multiplican el cambio de aficionados tras un partido (positivo o negativo); `presion` se suma a la presión del DT
# (derrota / victoria; positivo = más presión). Todo dentro de ±10% y ±0,06.
RASGOS_LIDER = {
    "festivo": {"nombre": "Festivo", "icono": "bi-emoji-sunglasses-fill", "pos": 1.10, "neg": 0.95, "presion_derrota": 0.00, "presion_victoria": -0.01, "peso": 24,
                "texto": "Todo es fiesta: celebra los triunfos a lo grande y perdona las derrotas."},
    "exigente": {"nombre": "Exigente", "icono": "bi-exclamation-diamond-fill", "pos": 0.95, "neg": 1.10, "presion_derrota": 0.05, "presion_victoria": -0.01, "peso": 20,
                 "texto": "No perdona: las derrotas le duelen a la afición y aprieta al técnico."},
    "ultra": {"nombre": "Ultra", "icono": "bi-fire", "pos": 1.08, "neg": 1.08, "presion_derrota": 0.04, "presion_victoria": 0.00, "peso": 18,
              "texto": "Vive cada partido a tope: sube y baja el ánimo de la tribuna más que nadie."},
    "humilde": {"nombre": "Humilde", "icono": "bi-heart-fill", "pos": 1.00, "neg": 0.90, "presion_derrota": 0.00, "presion_victoria": -0.02, "peso": 18,
                "texto": "Aguanta y alienta pase lo que pase: las derrotas pesan menos."},
    "carismatico": {"nombre": "Carismático", "icono": "bi-stars", "pos": 1.06, "neg": 0.97, "presion_derrota": 0.01, "presion_victoria": -0.01, "peso": 20,
                    "texto": "Arrastra gente: contagia a nuevos aficionados con cada victoria."},
}
# Estilos del líder (solo el aspecto del avatar y su etiqueta; los jóvenes son muy variados)
ESTILOS_LIDER = {
    "sencillo": {"nombre": "Sencillo", "peso": 26}, "hincha": {"nombre": "Hincha de bufanda", "peso": 20}, "urbano": {"nombre": "Urbano", "peso": 16},
    "punk": {"nombre": "Punk", "peso": 12}, "extravagante": {"nombre": "Extravagante", "peso": 14}, "pintado": {"nombre": "Cara pintada", "peso": 12},
}
# Qué tan seguido hablan tras un partido (siempre en eliminación directa, goleada o cese del DT)
PROB_PRESIDENTE_NORMAL = 0.25
PROB_LIDER = 0.60
