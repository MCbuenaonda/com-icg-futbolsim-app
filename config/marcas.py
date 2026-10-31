"""
Catálogo de marcas FICTICIAS que patrocinan jugadores y selecciones en la carrera de Corporativos
(colección `marcas`, la carga generar_marcas.py --aplicar; logos en el bucket marcas/<slug>.svg).

Ningún nombre ni logo es de una marca real: generar_marcas.py valida cada nombre contra LISTA_NEGRA
(coincidencia y parecido). La economía (cuánto paga cada marca) NO se guarda en el catálogo: sale de
`nivel` + las constantes de config/corporativos.py, así recalibrar no obliga a recargar la colección.
"""

# código -> nombre visible, ícono (Bootstrap Icons), paletas (principal, acento), familias de símbolos que le quedan,
# tipografías que le quedan y perfiles que suele buscar (peso)
RUBROS = {
    "indumentaria": {"nombre": "Indumentaria deportiva", "icono": "bi-person-standing",
                     "paletas": [("#e11d48", "#fde047"), ("#22c55e", "#0f172a"), ("#3b82f6", "#f97316"), ("#f43f5e", "#ffffff"),
                                 ("#a3e635", "#14532d"), ("#f97316", "#1e3a8a")],
                     "familias": ["movimiento", "geometrico"], "fuentes": ["kanit_italica", "anton", "teko", "archivo", "russo", "bebas"],
                     "perfiles": {"goleadores": 3, "figuras_forma": 3, "promesas": 2, "aficion": 1}},
    "calzado": {"nombre": "Calzado", "icono": "bi-lightning-charge",
                "paletas": [("#f97316", "#1c1917"), ("#38bdf8", "#f8fafc"), ("#facc15", "#111827"), ("#ef4444", "#fef3c7"),
                            ("#10b981", "#0f172a")],
                "familias": ["movimiento", "objeto", "geometrico"], "fuentes": ["exo_italica", "kanit_italica", "stencil", "oswald", "bungee"],
                "perfiles": {"goleadores": 4, "promesas": 3, "figuras_forma": 2}},
    "bebidas": {"nombre": "Bebidas", "icono": "bi-cup-straw",
                "paletas": [("#ef4444", "#ffffff"), ("#06b6d4", "#fef08a"), ("#84cc16", "#14532d"), ("#f472b6", "#3b0764"),
                            ("#fb923c", "#7c2d12"), ("#60a5fa", "#ffffff")],
                "familias": ["natural", "geometrico"], "fuentes": ["pacifico", "righteous", "comfortaa", "rubik", "bungee"],
                "perfiles": {"aficion": 4, "selecciones": 3, "figuras_forma": 2}},
    "alimentos": {"nombre": "Alimentos", "icono": "bi-basket",
                  "paletas": [("#f59e0b", "#7f1d1d"), ("#22c55e", "#fef3c7"), ("#ef4444", "#fde68a"), ("#d97706", "#ffffff"),
                              ("#fb7185", "#4c0519")],
                  "familias": ["natural", "objeto", "geometrico"], "fuentes": ["pacifico", "rubik", "comfortaa", "righteous", "kanit"],
                  "perfiles": {"aficion": 3, "selecciones": 3, "veteranos": 2}},
    "tecnologia": {"nombre": "Tecnología", "icono": "bi-cpu",
                   "paletas": [("#8b5cf6", "#22d3ee"), ("#22d3ee", "#0f172a"), ("#6366f1", "#f0abfc"), ("#14b8a6", "#e2e8f0"),
                               ("#a78bfa", "#facc15")],
                   "familias": ["tecnologia", "geometrico"], "fuentes": ["michroma", "montserrat", "russo", "exo_italica", "rubik"],
                   "perfiles": {"promesas": 4, "figuras_forma": 2, "aficion": 2}},
    "telefonia": {"nombre": "Telefonía", "icono": "bi-phone",
                  "paletas": [("#a855f7", "#f8fafc"), ("#f43f5e", "#fef9c3"), ("#0ea5e9", "#facc15"), ("#22c55e", "#ecfccb"),
                              ("#f97316", "#ffffff")],
                  "familias": ["tecnologia", "movimiento", "geometrico"], "fuentes": ["montserrat", "rubik", "kanit", "comfortaa", "righteous"],
                  "perfiles": {"aficion": 4, "selecciones": 2, "goleadores": 2}},
    "automotriz": {"nombre": "Automotriz", "icono": "bi-car-front",
                   "paletas": [("#ef4444", "#e5e7eb"), ("#94a3b8", "#0f172a"), ("#3b82f6", "#e2e8f0"), ("#facc15", "#18181b"),
                               ("#10b981", "#f8fafc")],
                   "familias": ["movimiento", "objeto", "geometrico"], "fuentes": ["michroma", "russo", "oswald", "blackops", "exo_italica"],
                   "perfiles": {"veteranos": 3, "figuras_forma": 2, "selecciones": 2, "leyendas": 1}},
    "banca": {"nombre": "Banca y finanzas", "icono": "bi-bank",
              "paletas": [("#3b82f6", "#e2e8f0"), ("#10b981", "#ecfdf5"), ("#eab308", "#1c1917"), ("#0ea5e9", "#f0f9ff"),
                          ("#14b8a6", "#fef3c7")],
              "familias": ["geometrico", "objeto"], "fuentes": ["cinzel", "montserrat", "playfair", "oswald", "archivo"],
              "perfiles": {"veteranos": 3, "defensas": 3, "selecciones": 2}},
    "aerolineas": {"nombre": "Aerolíneas y viajes", "icono": "bi-airplane",
                   "paletas": [("#38bdf8", "#ffffff"), ("#14b8a6", "#fde68a"), ("#f43f5e", "#e0f2fe"), ("#6366f1", "#fcd34d"),
                               ("#0ea5e9", "#f97316")],
                   "familias": ["natural", "movimiento", "objeto"], "fuentes": ["montserrat", "playfair", "oswald", "comfortaa", "kanit"],
                   "perfiles": {"selecciones": 4, "aficion": 3, "leyendas": 1}},
    "energia": {"nombre": "Energía", "icono": "bi-fuel-pump",
                "paletas": [("#f59e0b", "#1e293b"), ("#ef4444", "#facc15"), ("#84cc16", "#1a2e05"), ("#fb923c", "#ffffff"),
                            ("#22c55e", "#fde047")],
                "familias": ["natural", "movimiento", "tecnologia"], "fuentes": ["archivo", "russo", "anton", "oswald", "stencil"],
                "perfiles": {"goleadores": 2, "selecciones": 3, "veteranos": 2}},
    "seguros": {"nombre": "Seguros", "icono": "bi-shield-check",
                "paletas": [("#3b82f6", "#f1f5f9"), ("#0d9488", "#fef3c7"), ("#6366f1", "#e0e7ff"), ("#0284c7", "#facc15")],
                "familias": ["geometrico", "objeto", "natural"], "fuentes": ["cinzel", "montserrat", "playfair", "rubik", "kanit"],
                "perfiles": {"defensas": 4, "veteranos": 3, "selecciones": 1}},
    "videojuegos": {"nombre": "Videojuegos y streaming", "icono": "bi-controller",
                    "paletas": [("#ec4899", "#22d3ee"), ("#a3e635", "#3b0764"), ("#f43f5e", "#fde047"), ("#8b5cf6", "#4ade80"),
                                ("#22d3ee", "#f472b6")],
                    "familias": ["tecnologia", "geometrico", "movimiento"], "fuentes": ["bungee", "blackops", "righteous", "russo", "teko"],
                    "perfiles": {"promesas": 4, "goleadores": 2, "aficion": 2}},
    "lujo": {"nombre": "Relojes y lujo", "icono": "bi-gem",
             "paletas": [("#d4af37", "#111827"), ("#e5e7eb", "#b45309"), ("#c084fc", "#fef3c7"), ("#fbbf24", "#450a0a")],
             "familias": ["geometrico", "objeto"], "fuentes": ["playfair", "cinzel", "michroma", "montserrat"],
             "perfiles": {"leyendas": 4, "figuras_forma": 2, "veteranos": 2}},
}

ALCANCES = {
    "global": {"nombre": "Global", "nivel": 3},
    "continental": {"nombre": "Continental", "nivel": 2},
    "local": {"nombre": "Local", "nivel": 1},
}

# Qué busca cada perfil (lo evalúa corporativo_reglas.encaje_marca)
PERFILES_MARCA = {
    "goleadores": "Goleadores y atacantes decisivos",
    "figuras_forma": "Figuras en buena racha",
    "promesas": "Jóvenes promesa",
    "aficion": "Selecciones y jugadores con mucha afición",
    "selecciones": "Selecciones que avanzan en el torneo",
    "veteranos": "Veteranos confiables",
    "defensas": "Arqueros y defensores sólidos",
    "leyendas": "Leyendas del fútbol",
}

# Confederaciones (ids de la colección `confederaciones`) para las marcas continentales
CONFEDERACIONES = {1: "UEFA", 2: "CONMEBOL", 3: "CONCACAF", 4: "CAF", 5: "OFC", 6: "AFC"}

# (nombre, rubro, alcance, región): región = None (global), id de confederación (continental) o nombre del país (local).
# Incluye las 10 del acuerdo publicitario anterior (Volta Energy, Nórdica Air, Kubo Telecom, ...).
MARCAS = [
    # indumentaria
    ("Arkada", "indumentaria", "global", None), ("Velmo Sport", "indumentaria", "global", None),
    ("Trama Athletics", "indumentaria", "continental", 1), ("Zurda", "indumentaria", "continental", 2),
    ("Okan Kit", "indumentaria", "continental", 4), ("Tessel", "indumentaria", "continental", 6),
    ("Tiki Sport", "indumentaria", "continental", 5), ("Gambeta", "indumentaria", "local", "Argentina"),
    ("Rondo Wear", "indumentaria", "local", "España"), ("Craque Wear", "indumentaria", "local", "Brasil"),
    ("Kopje Kits", "indumentaria", "local", "Sudáfrica"),
    # calzado
    ("Cumbre Calzado", "calzado", "global", None), ("Tacoz", "calzado", "global", None),
    ("Pisada", "calzado", "continental", 2), ("Stollen", "calzado", "continental", 1),
    ("Grama Boots", "calzado", "continental", 3), ("Zancada", "calzado", "local", "México"),
    ("Botinera", "calzado", "local", "Chile"), ("Hayate Run", "calzado", "local", "Japón"),
    ("Garra Boots", "calzado", "local", "Uruguay"),
    # bebidas
    ("Brisa Bebidas", "bebidas", "global", None), ("Kolaka", "bebidas", "global", None),
    ("Fresquito", "bebidas", "continental", 3), ("Altiplano Agua", "bebidas", "continental", 2),
    ("Nordquell", "bebidas", "continental", 1), ("Sabana Juice", "bebidas", "continental", 4),
    ("Mate Bravo", "bebidas", "local", "Paraguay"), ("Chai Rush", "bebidas", "local", "India"),
    ("Tropik", "bebidas", "local", "Brasil"), ("Hielo Sur", "bebidas", "local", "Argentina"),
    # alimentos
    ("Granero", "alimentos", "global", None), ("Mordisco", "alimentos", "global", None),
    ("Cosecha Andina", "alimentos", "continental", 2), ("Nori Nori", "alimentos", "continental", 6),
    ("Baobab Foods", "alimentos", "continental", 4), ("Kumara Crunch", "alimentos", "continental", 5),
    ("Bocata", "alimentos", "local", "España"), ("Arepa Plena", "alimentos", "local", "Venezuela"),
    ("Maizal", "alimentos", "local", "México"), ("Maple Bites", "alimentos", "local", "Canadá"),
    # tecnología
    ("Nebulix", "tecnologia", "global", None), ("Cuantia", "tecnologia", "global", None),
    ("Synapta", "tecnologia", "continental", 1), ("Datayo", "tecnologia", "continental", 2),
    ("Codexa", "tecnologia", "continental", 6), ("Circuito Norte", "tecnologia", "continental", 3),
    ("Seorin Tech", "tecnologia", "local", "Corea del Sur"), ("Neuralia", "tecnologia", "local", "Estados Unidos"),
    ("Bytebao", "tecnologia", "local", "China"),
    # telefonía
    ("Kubo Telecom", "telefonia", "global", None), ("Ondanet", "telefonia", "global", None),
    ("Señal Sur", "telefonia", "continental", 2), ("Antenna Uno", "telefonia", "continental", 1),
    ("Mbalu Mobile", "telefonia", "continental", 4), ("Lagoon Mobile", "telefonia", "continental", 5),
    ("Celuar", "telefonia", "local", "Colombia"), ("Aló Móvil", "telefonia", "local", "México"),
    ("Dialink", "telefonia", "local", "Nigeria"),
    # automotriz
    ("Sierra Motors", "automotriz", "global", None), ("Torvan", "automotriz", "global", None),
    ("Rueda Libre", "automotriz", "continental", 2), ("Vigor Trucks", "automotriz", "continental", 1),
    ("Volantis", "automotriz", "continental", 1), ("Kamino", "automotriz", "continental", 6),
    ("Duna Motors", "automotriz", "local", "Arabia Saudita"), ("Pampa Pickup", "automotriz", "local", "Argentina"),
    ("Mesa Trucks", "automotriz", "local", "Estados Unidos"),
    # banca
    ("Atlas Bank", "banca", "global", None), ("Monedo", "banca", "global", None),
    ("Ceiba Financiera", "banca", "continental", 3), ("Fondo Austral", "banca", "continental", 2),
    ("Kapital Nord", "banca", "continental", 1), ("Nyota Pay", "banca", "continental", 4),
    ("Peso Fácil", "banca", "local", "México"), ("Kumo Bank", "banca", "local", "Japón"),
    ("Dirham Plus", "banca", "local", "Marruecos"),
    # aerolíneas y viajes
    ("Nórdica Air", "aerolineas", "global", None), ("Altavía", "aerolineas", "global", None),
    ("Ruta Viajes", "aerolineas", "continental", 2), ("Albatros Air", "aerolineas", "continental", 5),
    ("Monzón Airways", "aerolineas", "continental", 6), ("Caribe Sky", "aerolineas", "continental", 3),
    ("Savanna Wings", "aerolineas", "continental", 4), ("Meseta Air", "aerolineas", "local", "España"),
    ("Pacífico Jet", "aerolineas", "local", "Perú"),
    # energía
    ("Volta Energy", "energia", "global", None), ("Brasa Energía", "energia", "global", None),
    ("Ventisca Renovables", "energia", "continental", 1), ("Pampero Gas", "energia", "continental", 2),
    ("Sahel Power", "energia", "continental", 4), ("Golfo Fuel", "energia", "continental", 6),
    ("Geysir Power", "energia", "local", "Islandia"), ("Llanos Energía", "energia", "local", "Colombia"),
    ("Rift Power", "energia", "local", "Kenia"),
    # seguros
    ("Faro Seguros", "seguros", "global", None), ("Escudo Vital", "seguros", "global", None),
    ("Ancla Seguros", "seguros", "continental", 2), ("Tutela", "seguros", "continental", 1),
    ("Baluarte", "seguros", "continental", 3), ("Imara Assurance", "seguros", "continental", 4),
    ("Kizuna Life", "seguros", "local", "Japón"), ("Muralla Seguros", "seguros", "local", "Chile"),
    ("Nilo Seguros", "seguros", "local", "Egipto"),
    # videojuegos y streaming
    ("Pixel Play", "videojuegos", "global", None), ("Arcadión", "videojuegos", "global", None),
    ("Streamo", "videojuegos", "global", None), ("Combo Gamer", "videojuegos", "continental", 2),
    ("Nexo Arena", "videojuegos", "continental", 1), ("Joystika", "videojuegos", "continental", 3),
    ("Afro Arcade", "videojuegos", "continental", 4), ("Kiwi Live", "videojuegos", "continental", 5),
    ("Hado Games", "videojuegos", "local", "Japón"),
    # relojes y lujo
    ("Meridiano", "lujo", "global", None), ("Ébano & Oro", "lujo", "global", None),
    ("Kronvald", "lujo", "continental", 1), ("Perla del Golfo", "lujo", "continental", 6),
    ("Andes Gold", "lujo", "continental", 2), ("Zafiro Lux", "lujo", "continental", 3),
    ("Alhambra Joyas", "lujo", "local", "España"), ("Obsidiana", "lujo", "local", "México"),
    ("Kiriko Atelier", "lujo", "local", "Corea del Sur"),
]

LEMAS = {
    "indumentaria": ["Hecho para la cancha", "Cada partido, otra piel", "Juega con todo", "La camiseta habla"],
    "calzado": ["Cada paso cuenta", "Pisa fuerte", "Velocidad desde el suelo", "El primer toque empieza abajo"],
    "bebidas": ["Refresca el segundo tiempo", "Sabor de tribuna", "Brinda por el gol", "Frío como un penal"],
    "alimentos": ["Energía de verdad", "Del campo a la cancha", "Sabor que se comparte", "El alimento del hincha"],
    "tecnologia": ["El futuro juega hoy", "Datos que ganan partidos", "Inteligencia en cada jugada", "Conectados al juego"],
    "telefonia": ["Señal en todo el estadio", "Más cerca de tu equipo", "Cada gol, en tus manos", "Hablemos de fútbol"],
    "automotriz": ["Potencia en ruta", "Llega primero", "Hecho para durar", "Maneja como juegas"],
    "banca": ["Tu futuro, bien defendido", "Solidez de campeón", "Invierte en tu juego", "Confianza que se gana"],
    "aerolineas": ["Volamos con la hinchada", "Cada viaje, una final", "Despega con tu selección", "El mundo es la cancha"],
    "energia": ["Energía que mueve multitudes", "Combustible para ganar", "Prende el partido", "Fuerza que no se apaga"],
    "seguros": ["Cubrimos cada jugada", "Tranquilidad de visitante", "La mejor defensa", "Protegemos lo que importa"],
    "videojuegos": ["Juega sin pausa", "El partido sigue online", "Presiona start", "Tu próxima jugada"],
    "lujo": ["El tiempo de los grandes", "Precisión de campeón", "Para los que dejan huella", "Clase en cada detalle"],
}

# Palabras genéricas de rubro: no se comparan solas contra LISTA_NEGRA (sí el nombre completo)
GENERICAS = {"mobile", "telecom", "motors", "bank", "sport", "energy", "power", "trucks", "foods", "boots", "games", "wear"}

# Marcas reales famosas: ningún nombre del catálogo puede coincidir ni parecerse (generar_marcas.py lo verifica)
LISTA_NEGRA = """
adidas nike puma reebok umbro kappa joma diadora lotto mizuno asics newbalance underarmour fila hummel errea macron
lecoqsportif uhlsport kelme penalty topper athleta olympikus charly lining anta xtep peak erke 361 skechers vans converse
jordan hoka brooks saucony salomon onrunning columbia patagonia northface decathlon kipsta castore lululemon gymshark
cocacola coca pepsi fanta sprite gatorade powerade redbull monster rockstar heineken budweiser corona carlsberg stella
guinness amstel brahma quilmes aguila polar modelo tecate skol asahi kirin sapporo tsingtao efes peroni mahou
nestle danone evian volvic perrier sanpellegrino bonafont cristal lipton nestea tropicana minutemaid schweppes
mcdonalds burgerking kfc subway pizzahut dominos lays doritos pringles kelloggs oreo mars snickers twix kitkat nutella
ferrero milka cadbury hershey bimbo arcor alicorp gloria nissin maggi knorr heinz kraft unilever mondelez
apple samsung huawei xiaomi oppo vivo sony lg microsoft google intel amd nvidia ibm dell hp lenovo asus acer
cisco oracle sap meta facebook amazon alibaba tencent baidu bytedance tiktok netflix spotify youtube twitch hisense tcl
vodafone movistar telefonica claro tigo orange tmobile verizon att etisalat ooredoo mtn airtel safaricom jio entel
personal digicel telcel vivo tim wind three ee o2 kddi docomo softbank sktelecom kt
toyota volkswagen bmw mercedes audi ford chevrolet nissan honda hyundai kia peugeot renault fiat seat skoda opel
tesla volvo mazda subaru mitsubishi suzuki jeep dodge ram cadillac lexus porsche ferrari lamborghini maserati
bentley rollsroyce jaguar landrover byd geely chery citroen dacia mini alfaromeo
santander bbva hsbc barclays citi citibank jpmorgan chase visa mastercard amex americanexpress paypal itau bradesco
nubank ing ubs creditsuisse deutschebank bnp societegenerale scotiabank banorte bancolombia galicia macro mercadopago
emirates qatar etihad lufthansa iberia latam avianca aeromexico copa delta united american klm airfrance turkish
ryanair easyjet singapore cathay qantas jal ana condor garuda saudia aerolineas gol azul jetblue airbnb booking expedia
shell bp exxon mobil chevron total totalenergies petrobras pemex ypf repsol eni gazprom lukoil aramco adnoc
petronas sinopec ecopetrol pdvsa enel iberdrola edf engie
allianz axa mapfre generali zurich metlife prudential aig aviva chubb sura
playstation xbox nintendo sega ea easports konami ubisoft activision blizzard epic fortnite steam valve riot
rolex omega tagheuer hublot cartier patek audemars breitling tissot longines seiko casio citizen swatch
louisvuitton gucci prada chanel hermes dior versace armani burberry tiffany bulgari
emiratesairline mastercardcard heinekenbeer hyundaimotor kiamotors visa fifa uefa conmebol concacaf
""".split()


# Rasgo del dueño -> (ajuste de fidelidad, ajuste de la probabilidad de renovar al vencer el patrocinio).
# Con el reparto real de rasgos el promedio de las 121 marcas casi no cambia (fidelidad +0,002, renovación +0,008).
AJUSTE_DUENO = {
    "heredero": (0.04, 0.06), "futbolero": (0.06, 0.03), "filantropo": (0.03, 0.03), "tiburon": (-0.08, -0.08),
    "austero": (-0.10, -0.08), "fundador": (-0.03, -0.04), "imagen": (-0.12, 0.0),
}
