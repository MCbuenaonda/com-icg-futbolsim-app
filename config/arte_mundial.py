"""
Catálogo del arte de cada Mundial (póster y mascota), ver services/arte_mundial/.

El anfitrión puede ser CUALQUIERA de las 211 selecciones (mundial_service.crear_nuevo_mundial elige al azar dentro de
la confederación que toca), así que todo se resuelve en dos niveles:
  1. ICONOS_POR_PAIS: lo propio del país (curado para las sedes más reconocibles), se prefiere siempre.
  2. REGIONES: fondos e íconos de su región (por confederación, con excepciones en REGION_POR_PAIS).
Para sumar piezas a la biblioteca: dibujarlas en services/arte_mundial/poster.py (FONDOS / ICONOS / FUTBOL) y
nombrarlas acá en las regiones o países donde tienen sentido.
"""

TITULO_TORNEO = "COPA MUNDIAL DE LA FIFAV"
TITULO_CORTO = "COPA MUNDIAL"

# --- Regiones: fondos e íconos con sentido en cada una -----------------------------------------------------------
FONDOS_UNIVERSALES = ["rayos", "cielo", "franjas", "ondas", "geometrico", "concentrico", "retro", "montanas", "ciudad", "mar"]
REGIONES = {
    "europa": {"fondos": FONDOS_UNIVERSALES,
               "iconos": ["castillo", "torre_reloj", "catedral", "templo_columnas", "arco", "molino", "puente", "faro", "montana_nevada"]},
    "europa_este": {"fondos": FONDOS_UNIVERSALES,
                    "iconos": ["cupula_cebolla", "castillo", "catedral", "montana_nevada", "puente", "torre_reloj"]},
    "nordica": {"fondos": ["cielo", "montanas", "mar", "ondas", "geometrico", "retro", "concentrico", "franjas"],
                "iconos": ["montana_nevada", "faro", "volcan", "castillo", "molino"]},
    "medio_oriente": {"fondos": ["desierto", "rayos", "geometrico", "cielo", "concentrico", "retro", "franjas", "ciudad"],
                      "iconos": ["mezquita", "luna_estrella", "palmera", "rascacielos", "arco"]},
    "africa_norte": {"fondos": ["desierto", "rayos", "geometrico", "cielo", "concentrico", "retro", "mar"],
                     "iconos": ["mezquita", "luna_estrella", "palmera", "piramide_egipcia", "arco"]},
    "africa": {"fondos": ["rayos", "cielo", "concentrico", "geometrico", "selva", "desierto", "ondas", "retro"],
               "iconos": ["baobab", "montana_mesa", "palmera", "sol", "montana_nevada"]},
    "asia_este": {"fondos": ["rayos", "cielo", "ondas", "geometrico", "concentrico", "retro", "montanas", "ciudad"],
                  "iconos": ["pagoda", "torii", "volcan", "rascacielos", "cerezo"]},
    "asia_sur": {"fondos": ["rayos", "cielo", "selva", "concentrico", "geometrico", "retro", "mar", "montanas"],
                 "iconos": ["cupula_palacio", "pagoda", "palmera", "montana_nevada", "sol"]},
    "norteamerica": {"fondos": ["ciudad", "rayos", "cielo", "franjas", "montanas", "geometrico", "retro", "concentrico"],
                     "iconos": ["rascacielos", "puente", "montana_nevada", "hoja_arce", "faro"]},
    "mesoamerica": {"fondos": ["rayos", "cielo", "selva", "desierto", "geometrico", "concentrico", "retro", "franjas"],
                    "iconos": ["piramide_escalonada", "cactus", "sol", "volcan", "palmera"]},
    "caribe": {"fondos": ["mar", "cielo", "rayos", "selva", "ondas", "concentrico", "retro", "geometrico"],
               "iconos": ["palmera", "faro", "sol", "volcan"]},
    "sudamerica": {"fondos": ["rayos", "cielo", "montanas", "selva", "ondas", "geometrico", "concentrico", "retro", "franjas"],
                   "iconos": ["montana_nevada", "sol", "palmera", "volcan"]},
    "oceania": {"fondos": ["mar", "cielo", "ondas", "rayos", "selva", "concentrico", "retro"],
                "iconos": ["palmera", "volcan", "sol", "faro", "moai"]},
}
REGION_POR_CONFEDERACION = {1: "europa", 2: "sudamerica", 3: "caribe", 4: "africa", 5: "oceania", 6: "asia_sur"}
_grupos = {
    "europa_este": "Rusia, Ucrania, Bielorrusia, Moldavia, Rumanía, Bulgaria, Serbia, Montenegro, Macedonia del Norte, "
                   "Georgia, Armenia, Azerbaiyán, Kazajistán, Polonia, Eslovaquia, República Checa, Hungría, Bosnia y Herzegovina, "
                   "Kosovo, Albania, Letonia, Lituania, Estonia",
    "nordica": "Noruega, Suecia, Finlandia, Dinamarca, Islandia, Islas Feroe",
    "medio_oriente": "Arabia Saudita, Catar, Emiratos Árabes Unidos, Kuwait, Baréin, Omán, Yemen, Jordania, Siria, Irak, Irán, "
                     "Líbano, Palestina, Israel, Turquía, Afganistán, Pakistán, Turkmenistán, Uzbekistán, Tayikistán, Kirguistán",
    "africa_norte": "Marruecos, Argelia, Túnez, Libia, Egipto, Sudán, Mauritania",
    "asia_este": "Japón, Corea del Sur, Corea del Norte, China, Taiwán, Hong Kong, Macao, Mongolia",
    "norteamerica": "Estados Unidos, Canadá, Bermudas",
    "mesoamerica": "México, Guatemala, Belice, Honduras, El Salvador, Nicaragua, Costa Rica, Panamá",
    "oceania": "Australia, Nueva Zelanda, Guam",
    "sudamerica": "Guyana, Surinam",
}
REGION_POR_PAIS = {p.strip(): region for region, lista in _grupos.items() for p in lista.split(",")}

# --- Lo propio de cada país (primero en la lista = favorito) -----------------------------------------------------
ICONOS_POR_PAIS = {
    "México": ["piramide_escalonada", "sol", "cactus"], "España": ["molino", "castillo", "catedral"],
    "Francia": ["torre_celosia", "arco"], "Italia": ["coliseo", "templo_columnas"], "Grecia": ["templo_columnas"],
    "Inglaterra": ["torre_reloj", "puente"], "Escocia": ["castillo"], "Gales": ["castillo"], "Irlanda": ["faro", "castillo"],
    "Alemania": ["arco", "castillo"], "Países Bajos": ["molino"], "Bélgica": ["catedral", "molino"], "Portugal": ["faro", "torre_reloj"],
    "Suiza": ["montana_nevada"], "Austria": ["montana_nevada", "catedral"], "Rusia": ["cupula_cebolla"], "Ucrania": ["cupula_cebolla"],
    "Turquía": ["mezquita"], "Islandia": ["volcan", "faro"], "Noruega": ["montana_nevada", "faro"],
    "Egipto": ["piramide_egipcia", "palmera"], "Marruecos": ["mezquita", "palmera"], "Arabia Saudita": ["mezquita", "luna_estrella"],
    "Catar": ["rascacielos", "mezquita"], "Emiratos Árabes Unidos": ["rascacielos"], "Irán": ["mezquita"],
    "Sudáfrica": ["montana_mesa"], "Kenia": ["baobab", "montana_nevada"], "Tanzania": ["montana_nevada", "baobab"],
    "Senegal": ["baobab"], "Madagascar": ["baobab"], "Nigeria": ["sol", "palmera"], "Camerún": ["volcan", "palmera"],
    "Japón": ["torii", "volcan", "cerezo"], "China": ["pagoda"], "Corea del Sur": ["pagoda", "cerezo"], "Corea del Norte": ["pagoda"],
    "India": ["cupula_palacio"], "Tailandia": ["pagoda"], "Vietnam": ["pagoda"], "Indonesia": ["volcan", "palmera"],
    "Nepal": ["montana_nevada", "pagoda"], "Camboya": ["pagoda"], "Myanmar": ["pagoda"], "Malasia": ["rascacielos"],
    "Singapur": ["rascacielos"], "Australia": ["opera", "palmera"], "Nueva Zelanda": ["montana_nevada", "volcan"],
    "Estados Unidos": ["rascacielos", "puente"], "Canadá": ["hoja_arce", "montana_nevada"],
    "Brasil": ["montana_pan", "palmera"], "Argentina": ["obelisco", "sol"], "Uruguay": ["sol", "faro"],
    "Perú": ["montana_nevada", "sol"], "Bolivia": ["montana_nevada", "sol"], "Chile": ["moai", "montana_nevada"],
    "Ecuador": ["volcan"], "Colombia": ["montana_nevada", "palmera"], "Venezuela": ["montana_mesa", "palmera"],
    "Paraguay": ["sol"], "Cuba": ["palmera", "faro"], "Jamaica": ["palmera", "sol"], "Costa Rica": ["volcan"],
    "Guatemala": ["piramide_escalonada", "volcan"], "Honduras": ["piramide_escalonada"], "Belice": ["piramide_escalonada"],
    "El Salvador": ["volcan"], "Nicaragua": ["volcan"], "Panamá": ["rascacielos", "palmera"],
    "Fiyi": ["palmera"], "Tahití": ["palmera", "volcan"], "Samoa": ["palmera"], "Islas Cook": ["palmera"],
}

# Lemas cortos (bajo el título, opcionales)
LEMAS = ["UN MUNDO, UNA PELOTA", "LA FIESTA DE TODOS", "EL MUNDO EN JUEGO", "PASIÓN SIN FRONTERAS", "UNIDOS POR EL FÚTBOL",
         "LA GLORIA ESPERA", "EL JUEGO DE TODOS", "CORAZÓN MUNDIALISTA"]


# =================================================================================================================
# MASCOTA: qué es (base), cómo se llama y qué accesorio lleva. Las bases se dibujan en services/arte_mundial/mascota.py
# =================================================================================================================
# Bases preferidas por país (animal, fruta/comida o símbolo natural representativo); el primero es el favorito.
MASCOTAS_POR_PAIS = {
    "México": ["chile", "ajolote", "jaguar", "aguacate", "mazorca"], "España": ["naranja", "toro", "limon"],
    "Estados Unidos": ["aguila", "perro", "castor"], "Canadá": ["alce", "castor", "oso"], "Brasil": ["tucan", "jaguar", "coco"],
    "Argentina": ["capibara", "condor", "sol"], "Uruguay": ["sol", "capibara"], "Chile": ["condor", "chile"],
    "Perú": ["llama", "papa", "condor"], "Bolivia": ["llama", "papa"], "Ecuador": ["tucan", "tortuga"], "Colombia": ["condor", "tucan", "aguacate"],
    "Venezuela": ["tucan", "mango"], "Paraguay": ["jaguar", "mango"], "Cuba": ["coco", "pina"], "Jamaica": ["mango", "coco"],
    "Costa Rica": ["tucan", "pina"], "Guatemala": ["quetzal", "mazorca", "jaguar"], "Honduras": ["tucan", "pina"], "Panamá": ["tucan", "pina"],
    "Francia": ["gallo", "queso"], "Alemania": ["leon", "aguila"], "Inglaterra": ["leon", "perro"], "Italia": ["lobo", "tomate", "limon"],
    "Portugal": ["gallo", "naranja"], "Países Bajos": ["leon", "queso"], "Bélgica": ["leon"], "Suiza": ["queso", "vaca"],
    "Rusia": ["oso", "lobo"], "Ucrania": ["girasol"], "Grecia": ["buho", "limon"], "Turquía": ["lobo"], "Escocia": ["unicornio", "perro"],
    "Gales": ["dragon", "oveja"], "Irlanda": ["perro", "papa"], "Islandia": ["frailecillo", "pinguino"], "Noruega": ["alce", "frailecillo"],
    "Suecia": ["alce"], "Finlandia": ["oso"], "Dinamarca": ["leon"], "Polonia": ["aguila"], "Croacia": ["perro"], "Serbia": ["aguila"],
    "Japón": ["zorro", "mono"], "Corea del Sur": ["tigre"], "Corea del Norte": ["tigre"], "China": ["panda"], "India": ["tigre", "elefante", "mango"],
    "Tailandia": ["elefante", "mango"], "Vietnam": ["tigre"], "Indonesia": ["tigre", "coco"], "Australia": ["canguro", "koala"],
    "Nueva Zelanda": ["kiwi"], "Arabia Saudita": ["halcon", "camello"], "Catar": ["halcon", "camello"], "Emiratos Árabes Unidos": ["halcon"],
    "Irán": ["leon"], "Egipto": ["camello", "halcon"], "Marruecos": ["leon", "naranja"], "Nigeria": ["aguila"], "Camerún": ["leon"],
    "Senegal": ["leon"], "Ghana": ["aguila"], "Sudáfrica": ["leon", "elefante"], "Kenia": ["leon", "elefante"], "Costa de Marfil": ["elefante"],
    "Tanzania": ["jirafa", "elefante"], "Madagascar": ["lemur"], "Etiopía": ["leon"], "Argelia": ["zorro"], "Túnez": ["aguila"],
    "Fiyi": ["coco", "pina"], "Tahití": ["coco"], "Samoa": ["coco"], "Papúa Nueva Guinea": ["ave_paraiso"],
}
# Si el país no tiene lista propia: bases de su región
MASCOTAS_POR_REGION = {
    "europa": ["leon", "aguila", "perro", "lobo", "oso", "limon"], "europa_este": ["oso", "lobo", "aguila", "girasol"],
    "nordica": ["alce", "oso", "frailecillo", "lobo"], "medio_oriente": ["halcon", "camello", "leon", "lobo"],
    "africa_norte": ["leon", "camello", "zorro", "halcon"], "africa": ["leon", "elefante", "jirafa", "aguila", "mango"],
    "asia_este": ["panda", "tigre", "zorro", "mono"], "asia_sur": ["tigre", "elefante", "mango", "mono", "coco"],
    "norteamerica": ["aguila", "oso", "castor", "perro"], "mesoamerica": ["jaguar", "tucan", "chile", "aguacate", "mazorca"],
    "caribe": ["coco", "pina", "mango", "tucan", "tortuga"], "sudamerica": ["jaguar", "llama", "tucan", "condor", "capibara"],
    "oceania": ["coco", "tortuga", "pina", "ave_paraiso"],
}
# Nombres por base (al estilo de Naranjito, Pique, Juanito...). Si una base no tiene, se arma un diminutivo.
NOMBRES_POR_BASE = {
    "naranja": ["Naranjito", "Naranjín", "Gajito"], "chile": ["Pique", "Chilito", "Jalapeñito", "Picosito"],
    "aguacate": ["Aguacatito", "Guaco"], "pina": ["Piñito", "Piñón"], "tomate": ["Tomatín", "Rojito"], "limon": ["Limoncito", "Citrín"],
    "mango": ["Manguito", "Mangú"], "coco": ["Coquito", "Coco"], "mazorca": ["Elotito", "Choclito", "Mazorquín"],
    "papa": ["Papito", "Papín"], "cactus": ["Nopalito", "Espinín"], "sol": ["Solcito", "Soleado", "Inti"], "queso": ["Quesito", "Gruyín"],
    "girasol": ["Girasolín", "Soni"], "perro": ["Striker", "Canelo", "Firulais", "Golazo"], "lobo": ["Lupo", "Lobito", "Aullido"],
    "zorro": ["Kitsu", "Zorrito"], "oso": ["Misha", "Osito", "Bruno"], "panda": ["Bambú", "Pandi"], "koala": ["Koalín", "Eucalipto"],
    "leon": ["Leoncio", "Melenas", "Leo"], "tigre": ["Tigrín", "Rayas", "Ho"], "jaguar": ["Balam", "Yagua", "Jaguarín"],
    "conejo": ["Saltarín", "Conejín"], "canguro": ["Saltos", "Kangú"], "elefante": ["Trompito", "Elefantín"], "mono": ["Monchi", "Chango"],
    "toro": ["Torito", "Bravo"], "llama": ["Llamita", "Lanudo"], "aguila": ["Plumas", "Aquilino", "Vuelo"], "gallo": ["Footix", "Gallito", "Kikirikí"],
    "tucan": ["Tucanito", "Pico"], "kiwi": ["Kiwito", "Kiri"], "pinguino": ["Pingüi", "Frac"], "ajolote": ["Axo", "Ajolotín"],
    "alce": ["Alcino", "Astas"], "castor": ["Dientes", "Castorín"], "capibara": ["Capi", "Carpincho"], "condor": ["Cóndorito", "Alado"],
    "halcon": ["Halconcito", "Saqr"], "camello": ["Jorobas", "Camelín"], "buho": ["Atenea", "Buhito"], "frailecillo": ["Lundi", "Frailín"],
    "jirafa": ["Cuellito", "Jira"], "lemur": ["Colitas", "Lemi"], "tortuga": ["Caparazón", "Tortu"], "quetzal": ["Quetzi", "Plumín"],
    "vaca": ["Muuu", "Lechera"], "oveja": ["Lanita", "Bee"], "dragon": ["Draig", "Fuego"], "unicornio": ["Cuernito", "Unik"],
    "ave_paraiso": ["Plumaje", "Kumul"],
}
# Accesorio típico por región (además de la camiseta y el balón, que van siempre)
ACCESORIOS_POR_REGION = {
    "mesoamerica": ["sombrero_charro", "pañuelo", "ninguno"], "caribe": ["sombrero_paja", "vincha", "ninguno"],
    "sudamerica": ["vincha", "pañuelo", "gorra", "ninguno"], "europa": ["bufanda", "boina", "gorra", "ninguno"],
    "europa_este": ["bufanda", "gorro_lana", "ninguno"], "nordica": ["gorro_lana", "bufanda", "ninguno"],
    "medio_oriente": ["bufanda", "vincha", "ninguno"], "africa_norte": ["bufanda", "vincha", "ninguno"],
    "africa": ["vincha", "bufanda", "gorra", "ninguno"], "asia_este": ["vincha", "gorra", "ninguno"],
    "asia_sur": ["vincha", "bufanda", "ninguno"], "norteamerica": ["gorra", "bufanda", "ninguno"],
    "oceania": ["corona_flores", "sombrero_paja", "ninguno"],
}
ACCESORIOS_POR_PAIS = {"México": ["sombrero_charro", "pañuelo"], "España": ["pañuelo", "ninguno"], "Francia": ["boina", "bufanda"],
                       "Perú": ["gorro_lana"], "Bolivia": ["gorro_lana"], "Escocia": ["boina"], "Japón": ["vincha"]}

# Cómo se presenta cada base en la ficha de la mascota ("Pique es un chile jalapeño...")
DESCRIPCION_BASE = {
    "naranja": "una naranja", "limon": "un limón", "tomate": "un tomate", "chile": "un chile jalapeño", "aguacate": "un aguacate",
    "mango": "un mango", "pina": "una piña", "coco": "un coco", "mazorca": "una mazorca de maíz", "papa": "una papa",
    "queso": "un queso", "girasol": "un girasol", "sol": "el sol",
    "perro": "un perro", "lobo": "un lobo", "zorro": "un zorro", "oso": "un oso", "panda": "un panda", "koala": "un koala",
    "leon": "un león", "tigre": "un tigre", "jaguar": "un jaguar", "canguro": "un canguro", "elefante": "un elefante",
    "mono": "un mono", "toro": "un toro", "vaca": "una vaca", "llama": "una llama", "oveja": "una oveja", "camello": "un camello",
    "jirafa": "una jirafa", "unicornio": "un unicornio", "capibara": "un capibara", "castor": "un castor", "alce": "un alce",
    "lemur": "un lémur", "ajolote": "un ajolote", "tortuga": "una tortuga", "dragon": "un dragón", "aguila": "un águila",
    "halcon": "un halcón", "condor": "un cóndor", "gallo": "un gallo", "tucan": "un tucán", "quetzal": "un quetzal",
    "kiwi": "un kiwi", "pinguino": "un pingüino", "frailecillo": "un frailecillo", "buho": "un búho", "ave_paraiso": "un ave del paraíso",
}
