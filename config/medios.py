"""
Medios de comunicación FICTICIOS (colección `medios`, la carga generar_medios.py --aplicar): 2 por país —un diario
generalista y un medio deportivo— más 12 internacionales (6 globales y 1 por confederación). Cada uno tiene un DIRECTOR
(su rasgo fija la línea editorial) y 3 periodistas (4 en los internacionales) con su estilo y su sesgo.

Los nombres usan la costumbre de prensa de cada idioma (los mismos grupos de idioma y raíces que config/televisoras.py) y
se validan contra LISTA_NEGRA_PRENSA (igualdad y parecido con medios reales).
"""

PAPELES = ("generalista", "deportivo")
PAPEL_NOMBRE = {"generalista": "Diario generalista", "deportivo": "Medio deportivo", "global": "Medio global", "continental": "Medio continental"}
NIVEL_POR_PAPEL = {"generalista": 2, "deportivo": 2, "continental": 3, "global": 4}   # alcance 1..4
NIVELES = {2: "Nacional", 3: "Continental", 4: "Global"}

PATRONES = {
    "es": {"generalista": ["Diario {R}", "El {R}", "La {R}", "Gaceta {R}", "{R} Hoy"],
           "deportivo": ["{R} Deportes", "Marcador {R}", "Tribuna {R}", "{R} Sport", "Gol {R}"]},
    "pt": {"generalista": ["Diário {R}", "O {R}", "Gazeta {R}", "{R} Hoje"],
           "deportivo": ["{R} Esportes", "Placar {R}", "Tribuna {R}", "{R} Sport"]},
    "en": {"generalista": ["The {R} Times", "{R} Herald", "{R} Post", "Daily {R}", "{R} Chronicle"],
           "deportivo": ["{R} Sports Daily", "The {R} Score", "{R} Sports Desk", "Pitch {R}"]},
    "fr": {"generalista": ["Le {R}", "La Gazette {R}", "Journal {R}", "{R} Matin"],
           "deportivo": ["{R} Sport", "Le Stade {R}", "{R} Foot", "La Tribune {R}"]},
    "ar": {"generalista": ["Al {R}", "Sawt {R}", "Akhbar {R}", "{R} Daily"],
           "deportivo": ["{R} Riyadi", "Al {R} Sport", "Malaeb {R}"]},
    "de": {"generalista": ["{R} Zeitung", "Der {R}", "{R} Kurier", "Tageblatt {R}"],
           "deportivo": ["{R} Sport", "Sportblatt {R}", "{R} Fussball"]},
    "nl": {"generalista": ["De {R}", "{R} Courant", "Dagblad {R}"],
           "deportivo": ["{R} Sport", "Sportkrant {R}", "{R} Voetbal"]},
    "it": {"generalista": ["Il {R}", "Corriere {R}", "La Voce {R}", "{R} Oggi"],
           "deportivo": ["{R} Sport", "Sport {R}", "Calcio {R}", "Il {R} Sportivo"]},
    "nordico": {"generalista": ["{R} Posten", "{R} Tidende", "Dagen {R}"],
                "deportivo": ["{R} Sport", "Sport {R}", "{R} Fotboll"]},
    "este": {"generalista": ["{R} Daily", "Dnevnik {R}", "{R} Gazeta", "{R} Times"],
             "deportivo": ["{R} Sport", "Sport {R}", "{R} Arena", "{R} Futbol"]},
}
PATRONES_GRUPO = {"en_gb": "en", "en_am": "en", "en_af": "en", "en_oc": "en", "fr_af": "fr"}

# Línea editorial -> (nombre, descripción). Sale del rasgo del director.
LINEAS = {
    "sensacionalista": ("Sensacionalista", "Titulares estridentes: exagera triunfos y fracasos y vive del escándalo."),
    "analitica": ("Analítica", "Datos y contexto: opina con números y rara vez se deja llevar por el resultado."),
    "critica": ("Crítica", "Duda de todo: señala errores, exige más y no perdona un mal resultado."),
    "oficialista": ("Oficialista", "Cercana a las federaciones y a los técnicos: suaviza las críticas."),
    "optimista": ("Optimista", "Busca lo bueno: celebra a las promesas y le da a cada derrota su lado positivo."),
    "popular": ("Popular", "Habla como la afición: se emociona con las estrellas y con las rivalidades."),
}
LINEAS_POR_PAPEL = {"generalista": {"oficialista": 3, "critica": 3, "popular": 2, "analitica": 1, "optimista": 1},
                    "deportivo": {"analitica": 3, "sensacionalista": 3, "popular": 2, "critica": 2, "optimista": 1},
                    "global": {"analitica": 4, "critica": 2, "sensacionalista": 2}, "continental": {"analitica": 3, "popular": 2, "critica": 2, "optimista": 1}}

# Periodistas: rol -> estilos posibles; sesgo hacia el país del medio
ROLES = ("columnista", "reportero", "entrevistador")
ESTILOS = {
    "analista": ("Analista", "Lee el juego con datos y táctica."), "polemista": ("Polemista", "Opina fuerte y busca la controversia."),
    "cronista": ("Cronista", "Cuenta el partido con ritmo y detalle."), "entrevistador": ("Entrevistador", "Consigue las declaraciones que nadie más logra."),
    "sensacionalista": ("Sensacionalista", "Busca el titular antes que la verdad."), "estadistico": ("Estadístico", "Todo lo mide: rachas, promedios y récords."),
}
ESTILOS_POR_ROL = {"columnista": {"analista": 3, "polemista": 4, "sensacionalista": 1, "estadistico": 2},
                   "reportero": {"cronista": 4, "estadistico": 2, "analista": 2, "sensacionalista": 1},
                   "entrevistador": {"entrevistador": 5, "cronista": 2, "polemista": 1}}
SESGOS = {"neutral": 55, "patriota": 35, "critico": 10}   # patriota = favorece a las selecciones y jugadores de su país
SESGO_NOMBRE = {"neutral": "Neutral", "patriota": "Patriota", "critico": "Crítico con los suyos"}

INTERNACIONALES = [   # (id, nombre, papel, confederación o None)
    (9001, "Agencia Meridiano", "global", None), (9002, "Tribuna Planetaria", "global", None), (9003, "Cronos Sports International", "global", None),
    (9004, "La Línea de Banda", "global", None), (9005, "Observatorio del Balón", "global", None), (9006, "Gaceta del Mundial", "global", None),
    (9007, "Diario del Viejo Continente", "continental", 1), (9008, "Cono Sur Deportivo", "continental", 2), (9009, "El Istmo Deportivo", "continental", 3),
    (9010, "Sahel Sport Tribune", "continental", 4), (9011, "Pacífico Sur Press", "continental", 5), (9012, "Gran Asia Sports", "continental", 6),
]

LISTA_NEGRA_PRENSA = """
elpais elmundo marca as abc lavanguardia elperiodico sport mundodeportivo larazon elconfidencial publico eldiario
lanacion clarin pagina12 ole infobae cronista perfil elpais elcomercio elespectador eltiempo elheraldo elnuevodia
reforma milenio eluniversal excelsior lajornada record esto mediotiempo diariodemexico folha oglobo estadao lance
ge placar correio gazzetta corriere repubblica lastampa tuttosport lequipe lemonde lefigaro leparisien lib liberation
bild kicker spiegel welt sueddeutsche faz zeit times guardian telegraph independent dailymail mirror sun express
sky bbc espn fox nytimes washingtonpost wsj usatoday latimes chicagotribune theathletic athletic goal bleacherreport
cbssports nbcsports yahoosports reuters ap afp efe ansa tass xinhua kyodo yonhap aljazeera alarabiya skynews
globo universal nacion tribuna cronica diario heraldo gaceta periodico noticias hoy
""".split()
GENERICAS = {"diario", "el", "la", "le", "il", "der", "de", "the", "daily", "post", "times", "herald", "gaceta", "gazeta", "sport", "sports", "deportes",
             "hoy", "hoje", "arena", "journal", "tribuna", "marcador", "gol", "calcio", "futbol", "foot", "fussball", "voetbal", "posten"}


# --- Entrevistas a tus representados (services/corporativo_prensa_service.py) ------------------------------------------
ENTREVISTA_MAX_PENDIENTES = 3        # las que puede tener abiertas un CEO a la vez
ENTREVISTA_VENTANA_PARTIDOS = 3      # solo se piden por lo que pasó en los últimos 3 partidos del torneo
ENTREVISTA_VENCE_PARTIDOS = 10       # vence a los 10 partidos sin respuesta (cuenta como declinar suave)
ENTREVISTA_PROB_JUGADOR = 0.75       # un medio pide al jugador sobre el que acaba de escribir
ENTREVISTA_PROB_SELECCION = 0.30     # y, más rara vez, a la selección (el vocero) si la nota fue fuerte
ENTREVISTA_TONO_SELECCION = 0.5      # |tono| mínimo de la nota para pedir una entrevista por una selección
AJUSTE_REPUTACION_MAX = 60           # lo que una entrevista puede mover la reputación de tu universo (se desgasta 30% por ciclo)
AJUSTE_REPUTACION_DECAE = 0.7
# postura -> (prob. de que salga bien, reputación si sale bien, reputación si sale mal, satisfacción si bien, satisfacción si mal)
POSTURAS = {"prudente": (0.85, 6, -2, 2, -1), "seguro": (0.65, 12, -8, 4, -4), "polemico": (0.45, 20, -18, 6, -8)}
POSTURA_NOMBRE = {"prudente": "Prudente", "seguro": "Seguro de sí", "polemico": "Polémico"}
POSTURA_TEXTO = {"prudente": "Respuestas medidas: poco riesgo, poco brillo.", "seguro": "Va con todo, pero un traspié se nota.",
                 "polemico": "Declaraciones fuertes: puede dispararle la imagen o hundirla."}
DECLINAR = (-2, -2)                  # reputación y satisfacción al declinar
