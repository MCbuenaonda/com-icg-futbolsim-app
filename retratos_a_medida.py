"""
Retratos a medida de leyendas (2.ª tanda): las de más fama que aún no tenían, tomados de su foto de Wikidata (solo se miran sus
rasgos —piel, pelo, barba, calvicie, lentes—; la foto no se guarda). `generar_avatares.AJUSTES_JUGADOR` los incorpora sin pisar
a los de la primera tanda.
"""
def _r(piel, textura, pelo, peinado, barba, boca, forma, cuello="redondo", **extra):
    return {"piel": piel, "textura": textura, "pelo": pelo, "peinado": peinado, "barba": barba, "boca": boca, "forma": forma,
            "cuello_camiseta": cuello, "ojos": extra.pop("ojos", "marron"), **extra}


AJUSTES_LEYENDAS_2 = {
    5323: _r("#e3ac86", "lacio", "castano_oscuro", "tupe", "candado", "sonrisa", "alargada"),                       # Ibrahimović
    4983: _r("#efc4a4", "lacio", "castano_claro", "largo_atado", "completa", "seria", "alargada", ojos="azul"),     # Bale
    5026: _r("#e3ac86", "lacio", "castano_oscuro", "raya", None, "seria", "alargada", entradas=True),              # Puskás
    6016: _r("#5e331a", "muy_rizado", "#8a8582", "calvo", "completa", "seria", "oval", lentes=True),               # Weah
    4827: _r("#e3ac86", "lacio", "castano_oscuro", "corto", "completa", "seria", "oval"),                          # Hazard
    5873: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "sonrisa", "oval"),                                 # Drogba
    5828: _r("#5e331a", "muy_rizado", "negro", "rapado", "candado", "sonrisa", "redonda"),                         # Eto'o
    5356: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "seria", "alargada", entradas=True),              # Shevchenko
    5281: _r("#efc4a4", "lacio", "castano_oscuro", "raya", None, "seria", "alargada", entradas=True),              # Yashin
    4981: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "oval"),                                # Giggs
    5060: _r("#efc4a4", "lacio", "castano_oscuro", "flequillo", None, "seria", "alargada"),                           # Best
    4881: _r("#efc4a4", "lacio", "castano_claro", "corto", "incipiente", "seria", "oval"),                         # Rakitić
    5305: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "alargada"),                           # Vidić
    5870: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "sonrisa", "redonda"),                              # Yaya Touré
    4884: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "completa", "seria", "alargada", entradas=True),        # Mandžukić
    5259: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "sonrisa", "oval"),                               # Čech
    4792: _r("#e3ac86", "lacio", "negro", "corto", "incipiente", "seria", "oval"),                                 # Mkhitaryan
    5342: _r("#e3ac86", "lacio", "#6e6a68", "corto", "completa", "seria", "redonda", entradas=True),               # Arda Turan
    4979: _r("#efc4a4", "lacio", "castano", "corto", "completa", "seria", "alargada"),                             # Ramsey
    6563: _r("#e3ac86", "lacio", "castano_oscuro", "tupe", "candado", "seria", "alargada"),                        # Nakata
    5333: _r("#efc4a4", "lacio", "castano_claro", "tupe", "incipiente", "seria", "redonda"),                       # Shaqiri
    6280: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "seria", "alargada"),                               # Adebayor
    4860: _r("#e3ac86", "lacio", "castano_oscuro", "corto", None, "sonrisa", "oval", entradas=True),               # Stoichkov
    5291: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "seria", "alargada", lentes=True),                # Arshavin
    4891: _r("#e3ac86", "lacio", "castano_oscuro", "raya", None, "seria", "alargada"),                             # Laudrup
    5632: _r("#e3ac86", "lacio", "castano_oscuro", "corto", "incipiente", "sonrisa", "alargada"),                  # Chicharito
    6565: _r("#e3ac86", "lacio", "negro", "flequillo", None, "seria", "alargada"),                                 # Okazaki
    6463: _r("#e3ac86", "lacio", "castano_oscuro", "flequillo", None, "sonrisa", "redonda"),                       # Park Ji-sung
    5276: _r("#e3ac86", "lacio", "#8a8582", "corto", None, "sonrisa", "redonda", entradas=True),                   # Hagi
    4696: _r("#d4996f", "lacio", "negro", "degradado", "incipiente", "seria", "alargada"),                         # Falcao
    6133: _r("#5e331a", "muy_rizado", "negro", "rapado", "incipiente", "sonrisa", "oval"),                         # Mikel John Obi
    4820: _r("#b0703f", "rizado", "negro", "rapado", "incipiente", "seria", "alargada"),                           # Kompany
    5290: _r("#efc4a4", "lacio", "#8a8582", "raya", None, "seria", "redonda", entradas=True),                      # Blokhin
    5231: _r("#5e331a", "muy_rizado", "negro", "corto", None, "seria", "alargada"),                                # Seedorf
    4883: _r("#efc4a4", "lacio", "#8a8582", "corto", None, "seria", "alargada", entradas=True),                    # Šuker
    5224: _r("#efc4a4", "lacio", "castano_claro", "corto", "incipiente", "sonrisa", "alargada"),                   # Solskjær
    5287: _r("#e3ac86", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "oval"),                        # Dzagoev
    4913: _r("#efc4a4", "lacio", "castano_oscuro", "cresta", None, "seria", "alargada"),                           # Hamšík
    4885: _r("#efc4a4", "lacio", "rubio", "corto", None, "sonrisa", "oval"),                                       # Schmeichel
    6365: _r("#e3ac86", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "oval"),                        # Cahill
    5304: _r("#efc4a4", "lacio", "castano_claro", "corto", "incipiente", "seria", "alargada", entradas=True),      # Ivanović
    4708: _r("#b0703f", "rizado", "negro", "corto", None, "seria", "oval"),                                        # Valencia
    5264: _r("#efc4a4", "lacio", "rubio", "flequillo", None, "seria", "alargada"),                                    # Nedvěd
    5946: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "sonrisa", "redonda"),                              # Essien
    6564: _r("#e3ac86", "lacio", "negro", "largo_atado", None, "seria", "oval"),                                   # Endō
    5048: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "alargada"),                    # Keane
    5245: _r("#efc4a4", "lacio", "rubio", "corto", "completa", "seria", "alargada"),                               # Błaszczykowski
    5289: _r("#efc4a4", "lacio", "castano_oscuro", "raya", None, "seria", "alargada"),                             # Kerzhakov
    5324: _r("#efc4a4", "lacio", "castano_claro", "calvo", None, "seria", "oval"),                                 # Ljungberg
    4821: _r("#efc4a4", "lacio", "castano_claro", "degradado", "completa", "seria", "alargada"),                   # Alderweireld
    6566: _r("#e3ac86", "lacio", "negro", "flequillo", None, "seria", "alargada"),                                 # Miura
    4894: _r("#efc4a4", "lacio", "castano_claro", "tupe", "incipiente", "seria", "alargada"),                      # Bendtner
    5045: _r("#efc4a4", "lacio", "#8a8582", "corto", "incipiente", "seria", "redonda", entradas=True),             # Roy Keane
    5951: _r("#7a4524", "muy_rizado", "negro", "tupe", "candado", "seria", "alargada"),                            # Boateng
    4822: _r("#efc4a4", "lacio", "castano_claro", "corto", "completa", "seria", "alargada"),                       # Vertonghen
    4676: _r("#e3ac86", "lacio", "negro", "calvo", "completa", "seria", "alargada"),                               # Bravo
    5950: _r("#5e331a", "muy_rizado", "negro", "cresta", None, "sonrisa", "oval"),                                 # Gyan
    5266: _r("#efc4a4", "lacio", "castano_oscuro", "flequillo", None, "seria", "alargada"),                           # Rosický
    4861: _r("#efc4a4", "lacio", "negro", "raya", "incipiente", "seria", "alargada"),                              # Berbatov
    4878: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "alargada"),                    # Srna
    5865: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "seria", "redonda"),                                # Kolo Touré
    4693: _r("#c68458", "rizado", "#c9a24a", "afro", None, "sonrisa", "alargada"),                                 # Valderrama
    4905: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "seria", "alargada", lentes=True, entradas=True), # Dalglish
    6072: _r("#d4996f", "lacio", "negro", "degradado", "completa", "seria", "alargada"),                           # Ziyech
    5623: _r("#e3ac86", "lacio", "negro", "corto", None, "seria", "oval"),                                         # Márquez
    6558: _r("#e3ac86", "lacio", "negro", "largo_atado", None, "seria", "alargada"),                               # Nakazawa
    6562: _r("#e3ac86", "lacio", "negro", "flequillo", None, "seria", "oval"),                                        # Nakamura
    5309: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "seria", "alargada", entradas=True),              # Stojković
    5509: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "oval", entradas=True),                 # Donovan
    5345: _r("#e3ac86", "lacio", "negro", "corto", "incipiente", "seria", "alargada"),                             # Hakan Şükür
    5322: _r("#d4996f", "lacio", "negro", "calvo", None, "seria", "oval"),                                         # Larsson
    4875: _r("#e3ac86", "lacio", "negro", "raya", None, "seria", "alargada"),                                      # Ćorluka
    6560: _r("#e3ac86", "lacio", "negro", "corto", None, "seria", "oval"),                                         # Konno
    5267: _r("#e3ac86", "lacio", "negro", "corto", "completa", "seria", "alargada"),                               # Baroš
    5510: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "completa", "seria", "alargada"),                      # Dempsey
    4957: _r("#e3ac86", "lacio", "castano_oscuro", "raya", None, "seria", "alargada"),                             # Litmanen
    5501: _r("#e3ac86", "lacio", "#8a8582", "calvo", "completa", "sonrisa", "oval"),                               # Howard
    6557: _r("#e3ac86", "lacio", "negro", "corto", None, "seria", "oval"),                                         # Kawaguchi
    5284: _r("#efc4a4", "rizado", "castano_oscuro", "corto", "incipiente", "seria", "alargada"),                   # Zhirkov
    4882: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "seria", "alargada", entradas=True),              # Olić
    5243: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "seria", "alargada", entradas=True),              # Boniek
    6567: _r("#e3ac86", "lacio", "negro", "corto", None, "seria", "redonda"),                                      # Tamada
    4802: _r("#e3ac86", "lacio", "negro", "corto", "candado", "sonrisa", "alargada"),                              # Vastić
    5040: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "oval"),                                # O'Shea
    4847: _r("#efc4a4", "lacio", "castano_oscuro", "tupe", "completa", "seria", "alargada"),                       # Pjanić
    5218: _r("#efc4a4", "lacio", "pelirrojo", "corto", None, "seria", "redonda"),                                  # Riise
    4829: _r("#efc4a4", "lacio", "castano_claro", "tupe", "completa", "seria", "alargada"),                        # Mertens
    5872: _r("#5e331a", "muy_rizado", "negro", "rapado", "incipiente", "seria", "oval"),                           # Kalou
    5829: _r("#5e331a", "muy_rizado", "negro", "calvo", None, "sonrisa", "redonda"),                               # Milla
    5086: _r("#efc4a4", "lacio", "castano_oscuro", "flequillo", None, "seria", "alargada"),                        # Vollach
    5308: _r("#efc4a4", "lacio", "#8a8582", "calvo", "completa", "seria", "redonda"),                              # Stanković
    4886: _r("#efc4a4", "lacio", "rubio", "corto", "incipiente", "seria", "alargada"),                             # Kjær
    5336: _r("#e3ac86", "lacio", "castano_oscuro", "corto", None, "seria", "oval"),                                # Rüştü
    5325: _r("#efc4a4", "lacio", "castano_oscuro", "flequillo", "incipiente", "seria", "alargada"),                   # Sommer
    5306: _r("#e3ac86", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "alargada", entradas=True),     # Kolarov
    5874: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "seria", "alargada"),                               # Gervinho
    4918: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "completa", "seria", "alargada", entradas=True),      # Handanović
    6361: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "alargada"),                            # Milligan
    4901: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "seria", "alargada"),                             # Fletcher
    4887: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "seria", "oval"),                                 # Agger
    4906: _r("#efc4a4", "lacio", "#c9c9c9", "corto", None, "sonrisa", "alargada", entradas=True),                  # Law
    5310: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "alargada"),                            # Matić
    5452: _r("#e3ac86", "lacio", "negro", "raya", "completa", "seria", "alargada"),                                # Ruiz
    5011: _r("#e3ac86", "lacio", "negro", "corto", "incipiente", "seria", "oval"),                                 # Karagounis
    5329: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "alargada"),                            # Lichtsteiner
    4908: _r("#efc4a4", "lacio", "castano_claro", "corto", "incipiente", "seria", "alargada"),                     # Škrtel
    5334: _r("#efc4a4", "lacio", "castano_oscuro", "tupe", "completa", "seria", "alargada"),                       # Seferović
    5007: _r("#e3ac86", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "oval"),                        # Papastathopoulos
    4728: _r("#e3ac86", "lacio", "castano_oscuro", "corto", "completa", "sonrisa", "alargada"),                    # Pizarro
    6359: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "sonrisa", "alargada", entradas=True),            # Schwarzer
    5051: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "oval"),                                # Evans
    5070: _r("#efc4a4", "lacio", "castano_claro", "corto", "completa", "seria", "oval"),                           # Gudjohnsen
    5343: _r("#e3ac86", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "oval"),                        # Altıntop
    5024: _r("#efc4a4", "lacio", "castano_oscuro", "raya", None, "seria", "alargada"),                             # Albert
    6063: _r("#d4996f", "lacio", "negro", "rapado", "completa", "seria", "oval"),                                  # Benatia
    5232: _r("#efc4a4", "lacio", "castano_oscuro", "flequillo", None, "seria", "alargada"),                           # Neeskens
    6132: _r("#5e331a", "muy_rizado", "negro", "rapado", "completa", "sonrisa", "oval"),                           # Moses
    6555: _r("#e3ac86", "lacio", "#8a8582", "calvo", "incipiente", "seria", "alargada"),                           # Daei
    6138: _r("#5e331a", "muy_rizado", "negro", "rastas", None, "sonrisa", "alargada"),                             # Kanu
    5279: _r("#e3ac86", "lacio", "negro", "corto", "incipiente", "sonrisa", "alargada"),                           # Mutu
    4982: _r("#efc4a4", "lacio", "#c9c9c9", "corto", None, "sonrisa", "alargada"),                                 # Rush
    5027: _r("#efc4a4", "lacio", "castano_oscuro", "raya", None, "seria", "alargada"),                             # Kocsis
    5282: _r("#efc4a4", "lacio", "castano_oscuro", "rapado", "completa", "seria", "alargada"),                     # Ignashevich
    4952: _r("#efc4a4", "lacio", "rubio", "flequillo", None, "seria", "alargada"),                                    # Hyypiä
    5238: _r("#efc4a4", "lacio", "rubio", "corto", "incipiente", "sonrisa", "alargada"),                           # Glik
    5341: _r("#e3ac86", "lacio", "negro", "corto", None, "seria", "alargada"),                                     # Emre
    5247: _r("#efc4a4", "lacio", "castano_claro", "calvo", None, "sonrisa", "redonda"),                            # Lato
    6360: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "alargada"),                    # Neill
    5326: _r("#efc4a4", "lacio", "castano_oscuro", "raya", "incipiente", "seria", "alargada"),                     # Schär
    4836: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "sonrisa", "alargada"),                           # Hleb
    5344: _r("#e3ac86", "lacio", "negro", "corto", "incipiente", "seria", "alargada"),                             # Burak Yılmaz
    5455: _r("#7a4524", "muy_rizado", "negro", "calvo", None, "seria", "oval"),                                    # Wanchope
    4687: _r("#c68458", "rizado", "negro", "rulos", "completa", "seria", "alargada"),                             # Higuita
    5307: _r("#e3ac86", "lacio", "castano_oscuro", "raya", None, "seria", "alargada"),                             # Mihajlović
    6136: _r("#7a4524", "muy_rizado", "negro", "rapado", None, "sonrisa", "oval"),                                 # Odemwingie
    5830: _r("#5e331a", "muy_rizado", "negro", "calvo", None, "sonrisa", "redonda"),                               # Mboma
    5328: _r("#efc4a4", "lacio", "castano_claro", "rapado", None, "seria", "alargada"),                            # Senderos
    5338: _r("#e3ac86", "lacio", "#8a8582", "raya", None, "seria", "redonda", entradas=True),                      # Terim
    4876: _r("#e3ac86", "lacio", "#6e6a68", "corto", "completa", "seria", "alargada"),                             # Bilić
    5627: _r("#e3ac86", "rizado", "castano_oscuro", "corto", None, "seria", "alargada"),                           # Guardado
    5014: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "alargada"),                    # Charisteas
    6134: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "sonrisa", "oval"),                                 # Okocha
}
