"""
Televisoras FICTICIAS: 3 por país (633), que compran los derechos de transmisión de las selecciones que representan
los corporativos (colección `televisoras`, la carga generar_televisoras.py --aplicar; logos en el bucket
televisoras/<slug>.svg). Las reglas de los contratos viven en config/corporativos.py (TV_*).

Los nombres se arman con la costumbre de cada idioma (como se llaman de verdad las cadenas de cada lugar: «Canal 9…»,
«Rede…», «…Broadcasting», «Al…», «…Télé») y raíces propias de ese idioma (astros, paisajes, aves, flores). Ningún
nombre es de una cadena real: generar_televisoras.py los valida contra LISTA_NEGRA (igualdad y parecido).
"""

# --- Idioma de cada país (por ISO; el Reino Unido por id de país) ------------------------------------------------
GRUPOS = {
    "es": "AR BO CL CO EC PY PE UY VE ES CR CU SV GT HN MX NI PA PR DO GQ AD",
    "pt": "BR PT AO CV GW MZ ST TL MO",
    "en_gb": "GB IE GI MT",
    "en_am": "US CA AG AI BS BB BZ BM DM GD GY JM KY TC VG VI MS KN VC LC TT",
    "en_af": "GH NG KE UG TZ ZA ZM ZW MW BW NA LS SZ LR SL GM SS ET ER SO",
    "en_oc": "AU NZ GU AS FJ CK SB PG WS TO VU",
    "fr": "FR BE CH LU HT NC PF",
    "fr_af": "BJ BF BI CM TD KM CG CI GA GN MG ML NE CF CD RW SN TG DJ SC MU",
    "ar": "DZ EG LY MA MR TN SD SA BH QA AE IQ JO KW LB OM PS SY YE",
    "de": "DE AT LI",
    "nl": "NL AW CW SR",
    "it": "IT SM",
    "nordico": "DK FI IS FO NO SE EE",
    "este": ("BY BA BG HR SK SI CZ PL RU RS ME MK UA AL XK GR CY HU RO MD LV LT GE AM IL TR AZ KZ KG TM UZ IR AF TJ "
             "IN PK BD NP BT LK MV CN HK TW KP KR JP MN ID MY BN PH SG TH VN KH LA MM"),
}
GRUPO_POR_ISO = {iso: g for g, lista in GRUPOS.items() for iso in lista.split()}

# Patrones por papel de la cadena: {R} raíz, {r} raíz en minúscula (para fusiones), {N} número de canal
PAPELES = ("generalista", "regional", "deportiva")
PATRONES = {
    "es": {"generalista": ["Red {R}", "{R} Televisión", "Tele{r}", "Canal {N} {R}", "Sistema {R}", "{R}visión"],
           "regional": ["{R} TV", "Canal {R}", "Señal {R}", "Tele {R} {N}", "Onda {R}", "{R} Noticias"],
           "deportiva": ["{R} Deportes", "{R} Sports", "Gol {R}", "Pasión {R}", "{R} Fútbol", "Tele{r} Deportes"]},
    "pt": {"generalista": ["Rede {R}", "TV {R}", "{R} Televisão", "Sistema {R}", "Canal {N} {R}"],
           "regional": ["{R} TV", "Canal {R}", "Sinal {R}", "Onda {R}", "TV {R} {N}"],
           "deportiva": ["{R} Esporte", "{R} Sports", "Gol {R}", "Arena {R}", "{R} Futebol"]},
    "en": {"generalista": ["{R} Broadcasting", "{R} Television", "{R} Network", "Channel {N} {R}", "{R} One", "{R} Media"],
           "regional": ["{R} TV", "{R} {N}", "{R} Plus", "{R} Vision", "TV {R}"],
           "deportiva": ["{R} Sports", "{R} Sport {N}", "{R} Arena", "{R} Goal", "{R} Pitch"]},
    "fr": {"generalista": ["Télé {R}", "{R} Télévision", "Réseau {R}", "Canal {R}", "Radio-Télé {R}"],
           "regional": ["{R} TV", "{R} {N}", "Télé{r}", "Onde {R}", "Signal {R}"],
           "deportiva": ["{R} Sport", "{R} Sports {N}", "Télé {R} Sport", "Arène {R}", "{R} Sport Plus"]},
    "ar": {"generalista": ["Al {R}", "Qanat {R}", "Shabakat {R}", "{R} TV"],
           "regional": ["Al {R} {N}", "{R} Plus", "{R} 24", "Sawt {R}"],
           "deportiva": ["{R} Sport", "Al {R} Riyadiya", "{R} Sports", "Malaab {R}"]},
    "de": {"generalista": ["{R} TV", "{R} Fernsehen", "Kanal {R}", "Sender {R}", "{R} Eins"],
           "regional": ["{R} {N}", "{R} Plus", "TV {R}", "{R}funk"],
           "deportiva": ["{R} Sport", "{R} Sport {N}", "{R} Arena", "{R} Sportkanal"]},
    "nl": {"generalista": ["{R} Omroep", "Kanaal {R}", "{R} TV"],
           "regional": ["{R} {N}", "TV {R}", "{R} Plus"],
           "deportiva": ["{R} Sport", "{R} Sport {N}", "{R} Sportkanaal"]},
    "it": {"generalista": ["Tele{r}", "Rete {R}", "Canale {R}", "{R} TV"],
           "regional": ["{R} {N}", "Canale {N} {R}", "TV {R}", "Onda {R}"],
           "deportiva": ["{R} Sport", "Sport {R}", "{R} Calcio", "Arena {R}"]},
    "nordico": {"generalista": ["{R} TV", "Kanal {R}", "{R}kanalen"],
                "regional": ["{R} {N}", "TV {R}", "{R} Plus"],
                "deportiva": ["{R} Sport", "{R} Sport {N}", "{R} Arena"]},
    "este": {"generalista": ["{R} TV", "Kanal {R}", "{R} Network", "{R} Media"],
             "regional": ["{R} {N}", "TV {R}", "{R} Plus", "{R} One"],
             "deportiva": ["{R} Sport", "{R} Sports", "{R} Arena", "{R} Sport {N}"]},
}
PATRONES_GRUPO = {"en_gb": "en", "en_am": "en", "en_af": "en", "en_oc": "en", "fr_af": "fr"}
# Retoques por país dentro del grupo "este" (idioma de la cadena)
PATRONES_PAIS = {
    "TR": {"generalista": ["{R} TV", "Kanal {R}"], "regional": ["{R} {N}", "TV {R}"], "deportiva": ["{R} Spor", "{R} Spor {N}"]},
    "AZ": {"generalista": ["{R} TV", "Kanal {R}"], "regional": ["{R} {N}", "TV {R}"], "deportiva": ["{R} İdman", "{R} Spor"]},
    "IR": {"generalista": ["Shabake {R}", "{R} TV"], "regional": ["{R} {N}", "Sima-ye {R}"], "deportiva": ["{R} Varzesh", "{R} Sport"]},
    "AF": {"generalista": ["{R} TV", "Shabake {R}"], "regional": ["{R} {N}", "TV {R}"], "deportiva": ["{R} Varzesh", "{R} Sport"]},
    "RU": {"generalista": ["{R} TV", "Kanal {R}"], "regional": ["{R} {N}", "TV {R}"], "deportiva": ["{R} Sport", "{R} Arena"]},
    "ID": {"generalista": ["{R} TV", "Saluran {R}"], "regional": ["{R} {N}", "TV {R}"], "deportiva": ["{R} Sports", "{R} Olahraga"]},
    "MY": {"generalista": ["{R} TV", "Saluran {R}"], "regional": ["{R} {N}", "TV {R}"], "deportiva": ["{R} Sukan", "{R} Sports"]},
    "BN": {"generalista": ["{R} TV", "Saluran {R}"], "regional": ["{R} {N}", "TV {R}"], "deportiva": ["{R} Sukan", "{R} Sports"]},
    "PH": {"generalista": ["{R} Network", "{R} TV"], "regional": ["{R} {N}", "TV {R}"], "deportiva": ["{R} Sports", "{R} Arena"]},
}

# --- Raíces por grupo (sin repetir dentro del grupo) ------------------------------------------------------------
RAICES = {
    "es": ["Sol", "Luna", "Cóndor", "Quetzal", "Jaguar", "Ceiba", "Pampa", "Brisa", "Cumbre", "Estrella", "Horizonte",
           "Faro", "Aurora", "Volcán", "Laguna", "Selva", "Cielo", "Lucero", "Alba", "Puma", "Colibrí", "Palma", "Roble",
           "Cerro", "Valle", "Sierra", "Coral", "Trueno", "Rayo", "Cometa", "Órbita", "Nube", "Viento", "Cristal",
           "Ámbar", "Zafiro", "Esmeralda", "Fuego", "Prisma", "Rumbo", "Brújula", "Cénit", "Nova", "Gaviota", "Halcón",
           "Tucán", "Arcoíris", "Mirador", "Atalaya", "Bahía", "Cascada", "Vértice", "Meridiano", "Ocaso", "Alborada",
           "Relámpago", "Marea", "Oleaje", "Arrecife", "Manglar", "Caoba", "Jacarandá", "Orquídea", "Girasol",
           "Amanecer", "Plenilunio", "Altiplano", "Llanura", "Pradera", "Duna", "Cordillera", "Acuarela", "Mosaico",
           "Tormenta", "Centella", "Ventisca"],
    "pt": ["Sol", "Lua", "Estrela", "Onda", "Serra", "Ipê", "Arara", "Tucano", "Jangada", "Farol", "Horizonte",
           "Raio", "Trovão", "Vento", "Céu", "Areia", "Baía", "Sabiá", "Caju", "Palmeira", "Cachoeira", "Vale", "Cume",
           "Rumo", "Bússola", "Maré", "Luar", "Girassol", "Pitanga", "Acácia", "Orvalho", "Alvorada", "Ventania"],
    "en_gb": [], "en_oc": [],
    "en_am": ["Beacon", "Harbor", "Summit", "Horizon", "Compass", "Lighthouse", "Thunder", "Falcon", "Tide", "Breeze",
              "Cedar", "Maple", "Pine", "Ridge", "Prairie", "Reef", "Lagoon", "Sunrise", "Starlight", "Orbit", "Spark",
              "Vista", "Crest", "Peak", "Echo", "Solstice", "Equinox", "Zenith", "Comet", "Halo", "Kestrel", "Osprey",
              "Heron", "Lynx", "Bison", "Cascade", "Glacier", "Amber", "Jade", "Indigo", "Cobalt", "Anchor", "Mariner",
              "Tradewind", "Calypso", "Mango", "Hibiscus", "Palmetto", "Conch", "Flamingo", "Hummingbird", "Pelican",
              "Marlin", "Sargasso", "Seagrape", "Frigate", "Redwood", "Aspen", "Sequoia", "Canyon", "Mesa", "Bayou",
              "Frontier", "Lodestar", "Sandpiper", "Driftwood", "Coralline", "Breakwater", "Sundial", "Wildwind"],
    "en_af": ["Baobab", "Savanna", "Zuri", "Jua", "Nyota", "Mwezi", "Upepo", "Tembo", "Twiga", "Imbali", "Ilanga",
              "Inkanyezi", "Lerato", "Mvula", "Kuda", "Zola", "Sankofa", "Adinkra", "Kente", "Marimba", "Jacaranda",
              "Acacia", "Mopane", "Impala", "Kudu", "Nyala", "Oryx", "Cheetah", "Hornbill", "Weaver", "Rift", "Msasa",
              "Amani", "Baraka", "Pamoja", "Kilele", "Bahari", "Ziwa", "Mlima", "Nuru", "Tumaini", "Fahari", "Shujaa",
              "Imara", "Ndovu", "Umoja", "Imvula", "Ilitha", "Khaya", "Lesedi", "Naledi", "Tshepo", "Ayo", "Ife",
              "Akoma", "Zawadi", "Neema", "Bongo", "Duma", "Mbali"],
    "fr": ["Soleil", "Étoile", "Horizon", "Azur", "Mistral", "Écume", "Rivage", "Phare", "Aube", "Aurore", "Lumière",
           "Éclat", "Opale", "Saphir", "Hirondelle", "Alouette", "Faucon", "Cèdre", "Sommet", "Comète", "Prisme",
           "Boussole", "Embrun", "Marée"],
    "fr_af": ["Savane", "Harmattan", "Teranga", "Lagune", "Fleuve", "Palmier", "Karité", "Acajou", "Ébène", "Calao",
              "Ibis", "Pélican", "Antilope", "Rônier", "Fromager", "Néré", "Balafon", "Djembé", "Griot", "Pirogue",
              "Ténéré", "Flamboyant", "Manguier", "Bougainvillier", "Colibri", "Tourterelle", "Aigle", "Panthère",
              "Gazelle", "Okapi", "Corail", "Volcan", "Brousse", "Oasis", "Dune", "Mangrove", "Arc-en-ciel", "Lune",
              "Croissant", "Rosée", "Orage", "Tonnerre", "Éclair", "Kora", "Sahel", "Tamarinier", "Vanille",
              "Cauri", "Lagon Bleu", "Héron", "Cascade", "Termitière", "Goyavier", "Papyrus", "Hippocampe"],
    "ar": ["Fajr", "Najm", "Qamar", "Shams", "Bahr", "Sahra", "Waha", "Nakhla", "Sahab", "Barq", "Ufuq", "Riyah",
           "Zahra", "Ward", "Yasmin", "Lulu", "Marjan", "Fanar", "Jabal", "Wadi", "Nahr", "Saqr", "Dhahab", "Fidda",
           "Zumurrud", "Kawkab", "Nujoom", "Badr", "Diyar", "Ghaim", "Matar", "Nasim", "Bustan", "Rimal", "Kathib",
           "Sanabil", "Zaitoun", "Rumman", "Ghazal", "Maha", "Hudhud", "Shahin", "Amwaj", "Mawj", "Shati", "Rawabi",
           "Durra", "Yaqut", "Anbar", "Misk", "Qandil", "Mishkat", "Siraj", "Raya", "Sahil", "Ghadir", "Dalia",
           "Sidra", "Nakhil Alwan", "Tilal", "Faiha", "Ziyad"],
    "de": ["Weitblick", "Bergkristall", "Morgenrot", "Edelweiss", "Adler", "Falke", "Eiche", "Linde", "Leuchtturm",
           "Sternschnuppe", "Gipfel", "Föhn", "Enzian", "Alpenglühn"],
    "nl": [], "it": ["Orizzonte", "Vela", "Brezza", "Vetta", "Aquila", "Falco", "Cipresso", "Ulivo", "Ambra",
                     "Maestrale", "Scirocco", "Tramonto", "Stellina"],
    "nordico": [], "este": [],
}

# --- Raíces propias de un país (ISO, o id de país para las 4 naciones del Reino Unido) --------------------------
RAICES_PAIS = {
    # Reino Unido e Irlanda
    "24": ["Thistle", "Highland", "Saltire", "Kelpie"], "31": ["Draig", "Seren", "Celyn", "Eryri"],
    "36": ["Lionheart", "Pennine", "Oakhurst", "Downland"], "38": ["Causeway", "Mourne", "Linen", "Lagan Bridge"],
    "IE": ["Tara", "Clover", "Fáilte", "Liffey Lights"], "GI": ["Barbary", "Strait", "Pillar"],
    "MT": ["Xemx", "Kewkba", "Luzzu", "Farfett"],
    # Oceanía
    "AU": ["Wattle", "Kookaburra", "Coolabah", "Bilby"], "NZ": ["Kererū", "Kōwhai", "Rangi"],
    "GU": ["Tasi", "Paluma", "Håfa"], "AS": ["Matagi", "Tutuila", "Talofa"], "FJ": ["Drua", "Kula", "Tabua"],
    "CK": ["Tiare", "Vaka", "Marama"], "SB": ["Kesa", "Ngali", "Hakwa"], "PG": ["Kumul", "Kundu", "Bilum"],
    "WS": ["Manaia", "Lagi", "Fetu"], "TO": ["Heilala", "Fetu'u", "Lupe"], "VU": ["Namele", "Yasur", "Nakamal"],
    "NC": ["Cagou", "Niaouli", "Lagon"], "PF": ["Hei", "Hina", "Fetia"],
    # Caribe y otros de habla francesa/neerlandesa/portuguesa
    "HT": ["Solèy", "Lakansyèl", "Kolibri", "Lanmè"], "AW": ["Solo", "Laman", "Trupial", "Kunuku"],
    "CW": ["Dushi", "Wayaká", "Kokolishi"], "SR": ["Kankantri", "Liba", "Sabakoe", "Fayalobi"],
    "NL": ["Zeewind", "Duin", "Tulp", "Polder"], "MO": ["Calçada", "Guia", "Taipa"],
    # África con lengua propia
    "ET": ["Tsehay", "Kokeb", "Biftu", "Selam"], "ER": ["Berhan", "Semay", "Kokob"], "SO": ["Hiddig", "Qorrax", "Badda"],
    "MG": ["Masoandro", "Kintana", "Varika"], "KM": ["Ylang", "Karthala", "Lagon Vert"],
    "RW": ["Inyenyeri", "Izuba", "Umucyo"], "BI": ["Ikirezi", "Inkuba", "Umuseke"],
    "SC": ["Zwazo", "Lamer", "Koko Dmer"], "MU": ["Dodo", "Paille-en-queue", "Tamarin", "Morne"],
    # Andorra (catalán)
    "AD": ["Estel", "Isard", "Llum"],
    # Nórdicos y bálticos
    "DK": ["Havbølge", "Lyngbakke", "Stormfugl", "Fyrtårn"], "NO": ["Fjellvind", "Midnattsol", "Havørn", "Polarlys"],
    "SE": ["Norrsken", "Fjällvind", "Stjärnfall", "Älvdal"], "FI": ["Revontuli", "Tähtitaivas", "Kuutamo", "Aalto"],
    "IS": ["Norðurljós", "Jökull", "Eldfjall", "Lundi"], "FO": ["Tjaldur", "Drangar", "Brimið"],
    "EE": ["Virmaline", "Täheke", "Laine"], "LV": ["Saulīte", "Zvaigzne", "Dzintars", "Stārķis"],
    "LT": ["Aušrinė", "Žaibas", "Gintaras", "Vėtra"],
    # Europa del este y Balcanes
    "BY": ["Zorka", "Busel", "Vasilok"], "BA": ["Jablan", "Vihor", "Sunčani"], "BG": ["Zornitsa", "Iskra", "Orlitsa"],
    "HR": ["Jadran", "Galeb", "Bura", "Zvjezdica"], "SK": ["Sokolík", "Jaspis", "Hviezda"], "SI": ["Lipa", "Zarja", "Kresnik"],
    "CZ": ["Jitřenka", "Hvězdička", "Duha", "Křišťál"], "PL": ["Jutrzenka", "Sokół", "Bursztyn", "Orlik"],
    "RU": ["Rassvet", "Berezka", "Gorizont", "Volna"], "RS": ["Zora", "Oluja", "Lastavica"], "ME": ["Galija", "Lovćen", "Tara Kanjon", "Orlovo Krilo"],
    "MK": ["Sonce", "Burevesnik", "Ezero"], "UA": ["Kalyna", "Promin", "Zoriana", "Sokil"],
    "AL": ["Shqiponja", "Diell", "Yll", "Dallgë"], "XK": ["Agim", "Ylberi", "Rrufe"], "GR": ["Aktina", "Meltemi", "Asterias", "Delfini"],
    "CY": ["Kyma", "Akamas", "Ilios"], "HU": ["Hajnal", "Csillag", "Turul", "Délibáb"], "RO": ["Luceafăr", "Zori", "Șoim", "Brădet"],
    "MD": ["Codru", "Busuioc", "Ciocârlia"], "GE": ["Mze", "Varskvlavi", "Mtsvane"], "AM": ["Arev", "Astgh", "Tsiatsan", "Sevan"],
    "IL": ["Shemesh", "Kochav", "Zohar", "Galim"],
    # Turquía y Asia central
    "TR": ["Yıldız", "Şafak", "Doğan", "Poyraz"], "AZ": ["Ulduz", "Şəfəq", "Xəzər"], "KZ": ["Tulpar", "Zhuldyz", "Dala"],
    "KG": ["Jyldyz", "Shumkar", "Ak-Kuu"], "TM": ["Ýyldyz", "Altyn", "Gyrat"], "UZ": ["Yulduz", "Quyosh", "Lochin", "Bahor"],
    "IR": ["Setareh", "Khorshid", "Simorgh", "Baran"], "AF": ["Aftab", "Kohsar", "Shaheen", "Lajward"],
    "TJ": ["Sitora", "Oftob", "Lola"],
    # Asia del sur
    "IN": ["Surya", "Akash", "Mayur", "Kamal"], "PK": ["Chand", "Sitara", "Basant", "Sarsabz"],
    "BD": ["Shapla", "Dhrubotara", "Nodi"], "NP": ["Himal", "Lali", "Danfe"], "BT": ["Takin", "Norbu", "Kuenga"],
    "LK": ["Tharu", "Mihira", "Sayura"], "MV": ["Kandu", "Hulhangu", "Fehi"],
    # Asia del este
    "CN": ["Xinghe", "Huaguang", "Jinfeng", "Longteng"], "HK": ["Bauhinia", "Harbourlight", "Peakview"],
    "TW": ["Yushan", "Taroko", "Lantian"], "KP": ["Jindallae", "Byeolbit", "Saebyeok"],
    "KR": ["Haneul", "Mugunghwa", "Baram", "Hanbit"], "JP": ["Hoshizora", "Hinode", "Kazeoto", "Tsubasa"],
    "MN": ["Naran", "Burged", "Saran", "Tal Nutag"],
    # Sudeste asiático
    "ID": ["Mentari", "Pelangi", "Samudra", "Cendrawasih"], "MY": ["Harimau", "Kenyalang", "Bayu", "Purnama"],
    "BN": ["Mutiara", "Embun", "Cahaya"], "PH": ["Bituin", "Araw", "Agila", "Sampaguita"],
    "SG": ["Orkid", "Senja", "Tembusu", "Kampong"], "TH": ["Dao", "Tawan", "Rung"], "VN": ["Sao Mai", "Sen Vàng", "Bình Minh"],
    "KH": ["Reaksmey", "Phkay", "Tonle", "Sovann"], "LA": ["Champa", "Tavan", "Saeng"], "MM": ["Thazin", "Padauk", "Shwe"],
}

# --- Perfil de cada cadena (cómo paga) y papel ---------------------------------------------------------------
PERFILES = {
    "generosa": {"nombre": "Generosa", "descripcion": "Paga bien aunque el equipo pierda", "icono": "bi-cash-stack"},
    "resultadista": {"nombre": "Resultadista", "descripcion": "Paga mucho las victorias y poco lo demás", "icono": "bi-trophy"},
    "fiel": {"nombre": "Fiel", "descripcion": "Renueva fácil y exige menos para el bono", "icono": "bi-heart"},
}
PAPEL_NOMBRE = {"generalista": "Cadena nacional", "regional": "Cadena regional", "deportiva": "Canal deportivo"}
NIVEL_POR_PAPEL = {"generalista": 3, "deportiva": 2, "regional": 1}
NIVELES = {1: "Regional", 2: "Nacional", 3: "Líder de audiencia"}

LEMAS = {
    "generalista": ["La señal de todo el país", "Siempre contigo", "Donde se ve lo que importa", "La pantalla de la familia",
                    "Primero en tu casa", "Lo vemos juntos", "La que más se ve", "Hecha para ti"],
    "regional": ["Cerca de tu gente", "La voz de tu región", "Lo nuestro, en vivo", "Tu barrio en pantalla",
                 "Contamos lo que pasa", "La señal de aquí", "Nuestra tierra, nuestra tele", "De aquí para el mundo"],
    "deportiva": ["Vive cada jugada", "Pasión en vivo", "El gol se ve aquí", "La cancha en tu sala", "Noventa minutos de emoción",
                  "Donde juega tu selección", "Todo el fútbol, toda la emoción", "La casa del deporte"],
}

# --- Diseño de los logos -----------------------------------------------------------------------------------------
# Paletas propias de la TV (principal, acento); una de las 3 cadenas de cada país usa los colores de su bandera
PALETAS = [("#e11d48", "#fde047"), ("#2563eb", "#f8fafc"), ("#16a34a", "#facc15"), ("#7c3aed", "#22d3ee"),
           ("#ea580c", "#1e293b"), ("#0891b2", "#fef3c7"), ("#db2777", "#f9a8d4"), ("#ca8a04", "#1c1917"),
           ("#0f766e", "#a7f3d0"), ("#dc2626", "#ffffff"), ("#4f46e5", "#fbbf24"), ("#059669", "#f0fdf4"),
           ("#9333ea", "#fde68a"), ("#0284c7", "#f97316"), ("#be123c", "#fecdd3"), ("#65a30d", "#1a2e05"),
           ("#c026d3", "#fdf4ff"), ("#d97706", "#7c2d12"), ("#1d4ed8", "#93c5fd"), ("#e879f9", "#3b0764"),
           ("#f43f5e", "#0f172a"), ("#14b8a6", "#134e4a"), ("#f59e0b", "#ffffff"), ("#6366f1", "#e0e7ff"),
           ("#84cc16", "#365314"), ("#0ea5e9", "#082f49"), ("#ef4444", "#fbbf24"), ("#a855f7", "#f5f3ff")]
FUENTES_PAPEL = {
    "generalista": ["montserrat", "oswald", "archivo", "rubik", "playfair", "cinzel", "michroma"],
    "regional": ["kanit", "comfortaa", "righteous", "rubik", "montserrat", "bebas", "pacifico"],
    "deportiva": ["anton", "teko", "russo", "kanit_italica", "exo_italica", "bungee", "stencil", "blackops"],
}

# --- Cadenas reales (los nombres no pueden ser iguales ni parecidos) ---------------------------------------------
LISTA_NEGRA = [
    # América
    "televisa", "tvazteca", "azteca", "imagen", "multimedios", "canalonce", "telemundo", "univision", "unimas", "globo",
    "redeglobo", "record", "recordtv", "bandeirantes", "band", "sbt", "redetv", "redevida", "tvcultura", "telefe",
    "eltrece", "americatv", "canal13", "canal9", "tvpublica", "tycsports", "caracol", "rcn", "canaluno", "ecuavisa",
    "teleamazonas", "gamavision", "tctelevision", "unitel", "redbolivision", "atb", "panamericana", "latina", "atv",
    "willax", "tvperu", "teledoce", "saeta", "montecarlo", "venevision", "televen", "globovision", "megavision", "mega",
    "chilevision", "chv", "tvn", "canal13chile", "teletica", "repretel", "telemetro", "tvmax", "telesistema",
    "telemicro", "colorvision", "telecentro", "teleantillas", "wapa", "telemundopr", "canal4", "canal2", "telecorporacion",
    "vtv", "tvj", "cvm", "cnc3", "tv6", "zns", "flow", "digicel", "fox", "abc", "nbc", "cbs", "cw", "pbs", "espn",
    "hbo", "cnn", "tnt", "tbs", "amc", "showtime", "starz", "peacock", "bravo", "discovery", "cbc", "ctv", "global",
    "globaltv", "citytv", "tsn", "sportsnet", "tva", "telequebec", "directv", "dazn", "paramount", "nickelodeon",
    # Europa
    "bbc", "itv", "sky", "skysports", "channel4", "channel5", "rte", "virgin", "virginmedia", "s4c", "stv", "utv",
    "tg4", "btsport", "eurosport", "ard", "zdf", "rtl", "sat1", "prosieben", "vox", "orf", "srf", "rts", "rsi", "rai",
    "mediaset", "canale5", "italia1", "rete4", "la7", "tf1", "francetv", "france2", "m6", "canalplus", "canal",
    "bfm", "lci", "arte", "tv5", "tv5monde", "rtbf", "vtm", "vrt", "npo", "rtl4", "sbs", "nos", "tve", "rtve", "antena3",
    "telecinco", "lasexta", "cuatro", "tv3", "telemadrid", "canalsur", "rtp", "sic", "tvi", "dr", "tv2", "nrk", "svt",
    "tv4", "yle", "mtv3", "ruv", "kringvarp", "err", "ltv", "lrt", "tvp", "polsat", "tvn24", "ct", "nova", "prima",
    "markiza", "joj", "rtvslo", "popty", "hrt", "rtl2", "rtrs", "rtcg", "mrt", "sitel", "bnt", "btv", "tvr", "protv",
    "antena1", "mtva", "rtlklub", "tv2hu", "ert", "ant1", "alpha", "skai", "open", "rik", "trt", "atvturkey", "showtv",
    "kanald", "startv", "ntv", "haberturk", "channelone", "pervyikanal", "rossiya", "rentv", "ctc", "matchtv", "zvezda",
    "1plus1", "ictv", "inter", "stb", "belarus1", "ont", "khabar", "imedi", "rustavi", "armenia", "shant", "keshet",
    "reshet", "kan", "rtsh", "topchannel", "klan", "rtk", "pink", "prva", "nova s", "arena sport", "tring",
    # Asia y Oceanía
    "nhk", "fuji", "fujitv", "tbsjapan", "asahi", "tvasahi", "nippontv", "tvtokyo", "wowow", "jsports", "kbs", "mbc",
    "jtbc", "tvn", "channela", "mbn", "tvchosun", "ebs", "cctv", "hunantv", "dragontv", "zhejiangtv", "tvb", "viutv",
    "hoytv", "rthk", "cts", "ttv", "ftv", "tvbs", "settv", "pts", "kctv", "mongoltv", "mnb", "doordarshan", "star",
    "starsports", "zee", "sony", "colors", "suntv", "asianet", "ndtv", "aajtak", "ptv", "geo", "ary", "hum", "dunya",
    "samaa", "btv", "channeli", "rupavahini", "sirasa", "tvm", "abscbn", "gma", "tv5ph", "ibc", "untv", "mediacorp",
    "channel8", "suria", "vasantham", "cna", "starhub", "singtel", "astro", "tv3my", "ntv7", "8tv", "tv9", "rtm",
    "rcti", "sctv", "indosiar", "transtv", "trans7", "metrotv", "antv", "mnctv", "tvri", "kompastv", "tvone",
    "ch3", "ch7", "mcot", "thaipbs", "workpoint", "one31", "gmm", "amarin", "pptv", "truevisions", "vtv", "htv",
    "vtc", "thvl", "ctn", "bayon", "hangmeas", "tvk", "lnt", "mrtv", "mntv", "skynet", "fortune", "mitv", "lotus",
    "macaulotus", "tdm", "tolo", "ariana", "irib", "presstv", "manoto", "varzesh", "abcaustralia", "seven", "nine",
    "ten", "foxtel", "optus", "kayo", "stan", "win", "prime", "southerncross", "tvnz", "three", "maoritv", "whakaata",
    "fbc", "fijione", "maitv", "emtv", "tvwan", "nbcpng", "sibc", "tvtonga", "tntv", "polynesie1ere", "nc1ere",
    # Medio Oriente y África
    "aljazeera", "jazeera", "alarabiya", "arabiya", "rotana", "dubaitv", "abudhabi", "sharjah", "ktv", "bahraintv",
    "omantv", "jordantv", "roya", "lbci", "mtvlebanon", "aljadeed", "future", "almanar", "manar", "almayadeen",
    "alhayat", "hayat", "almajd", "alghad", "alsharqiya", "iraqiya", "watan", "ertu", "cbcegypt", "ontv", "dmc",
    "nile", "alnahar", "nahar", "2m", "alaoula", "medi1", "entv", "ennahar", "echorouk", "shorouk", "watania",
    "hannibal", "nessma", "beinsports", "bein", "ssc", "nour", "alnour", "thuraya", "sama", "samadubai", "nakheel",
    "sabc", "etv", "mnet", "supersport", "dstv", "gotv", "startimes", "nta", "ait", "channelstv", "tvc", "galaxy",
    "ktn", "ntvkenya", "citizen", "kbc", "nbs", "ubc", "tbc", "itvtanzania", "azamtv", "znbc", "zbc", "gbc", "tv3ghana",
    "joy", "joyprime", "utvghana", "rtssenegal", "2stv", "tfm", "rti", "nci", "crtv", "equinoxe", "rtnc", "rtb", "ortm",
    "tpa", "zimbo", "stv", "miramar", "ebc", "fana", "ebs", "rtg", "tvzimbo", "orc", "rtm", "sntv", "universaltv",
]
# Palabras de cadena que no cuentan al comparar con la lista negra
GENERICAS = {"canal", "canale", "kanal", "kanaal", "channel", "tele", "television", "televisao", "televisión", "television",
             "tv", "red", "rede", "rete", "reseau", "network", "broadcasting", "media", "vision", "visión", "plus", "one",
             "sports", "sport", "spor", "deportes", "esporte", "noticias", "fernsehen", "omroep", "sender", "senal", "sinal",
             "signal", "onda", "onde", "arena", "sistema", "shabakat", "shabake", "qanat", "sawt", "riyadiya", "malaab",
             "futbol", "futebol", "calcio", "goal", "pitch", "gol", "pasion", "doel", "eins", "funk", "saluran", "olahraga",
             "sukan", "varzesh", "idman", "kanalen", "noticias", "radio", "radiotele", "arene", "but", "tor"}


# Rasgo del dueño -> (ajuste de fidelidad, ajuste de exigencia) de su cadena (suma a los valores base del catálogo).
# Con el reparto real de rasgos el promedio de las 633 cadenas casi no cambia (fidelidad +0,003, exigencia +0,005).
AJUSTE_DUENO = {
    "mecenas": (0.08, -0.05), "visionario": (0.03, -0.02), "estrella": (0.0, -0.03), "tiburon": (-0.05, 0.05),
    "impaciente": (-0.08, 0.05), "ahorrador": (-0.03, 0.03), "tradicional": (0.08, 0.0),
}
