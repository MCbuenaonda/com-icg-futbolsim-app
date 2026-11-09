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
    5015: _r("#e3ac86", "lacio", "negro", "flequillo", "incipiente", "seria", "alargada"),                         # Samaras
    5353: _r("#efc4a4", "lacio", "rubio", "flequillo", "incipiente", "seria", "alargada"),                         # Tymoshchuk
    6057: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "seria", "alargada"),                               # Keita
    5337: _r("#e3ac86", "rizado", "castano_oscuro", "corto", None, "seria", "alargada"),                           # Özalan
    4709: _r("#d4996f", "lacio", "negro", "corto", None, "seria", "oval"),                                         # Chilavert
    5631: _r("#d4996f", "rizado", "negro", "rulos", None, "seria", "alargada"),                                    # Hugo Sánchez
    4741: _r("#e3ac86", "lacio", "castano_oscuro", "raya", None, "seria", "alargada"),                             # Ghiggia
    5039: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "incipiente", "sonrisa", "alargada"),                  # Given
    5319: _r("#efc4a4", "lacio", "rubio", "corto", None, "seria", "oval"),                                         # S. Larsson
    6129: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "seria", "oval"),                                   # Yobo
    5268: _r("#efc4a4", "lacio", "castano_claro", "calvo", None, "sonrisa", "alargada"),                           # Koller
    4850: _r("#efc4a4", "lacio", "#4a4542", "corto", "completa", "seria", "alargada"),                             # Ibišević
    6364: _r("#e3ac86", "rizado", "castano_oscuro", "rulos", "incipiente", "seria", "alargada"),                   # Jedinak
    5741: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "sonrisa", "oval"),                                 # Yorke
    4737: _r("#e3ac86", "rizado", "castano_oscuro", "flequillo", None, "sonrisa", "alargada"),                     # Francescoli
    4685: _r("#d4996f", "lacio", "negro", "tupe", None, "sonrisa", "alargada"),                                    # Zamorano
    5241: _r("#efc4a4", "lacio", "castano_claro", "tupe", None, "seria", "alargada"),                              # Piszczek
    6237: _r("#b0703f", "muy_rizado", "negro", "trenzas", "incipiente", "seria", "alargada"),                      # Pienaar
    6368: _r("#efc4a4", "lacio", "#c9c9c9", "calvo", "incipiente", "seria", "redonda"),                            # Arnold
    4879: _r("#efc4a4", "lacio", "castano_claro", "corto", "completa", "seria", "alargada"),                       # Prosinečki
    4697: _r("#b0703f", "rizado", "negro", "corto", None, "seria", "oval"),                                        # Muriel
    5312: _r("#efc4a4", "lacio", "#4a4542", "corto", "incipiente", "seria", "redonda"),                            # Milošević
    4729: _r("#d4996f", "lacio", "negro", "tupe", None, "sonrisa", "oval"),                                        # Guerrero
    4874: _r("#efc4a4", "lacio", "castano_claro", "corto", "completa", "seria", "alargada"),                       # Pletikosa
    5283: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "seria", "alargada"),                             # Berezutski
    5244: _r("#efc4a4", "lacio", "castano_oscuro", "largo_atado", "completa", "seria", "alargada"),                # Krychowiak
    5331: _r("#efc4a4", "lacio", "rubio", "tupe", "completa", "seria", "alargada"),                                # Behrami
    5273: _r("#efc4a4", "lacio", "negro", "corto", None, "seria", "oval"),                                         # Chivu
    4841: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "alargada"),                            # Begović
    6362: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "completa", "seria", "alargada"),                      # Popovic
    4880: _r("#efc4a4", "lacio", "castano_oscuro", "raya", "incipiente", "seria", "alargada"),                     # Boban
    4799: _r("#efc4a4", "lacio", "#c9c9c9", "flequillo", None, "seria", "alargada"),                               # Happel
    5507: _r("#efc4a4", "lacio", "castano_claro", "calvo", "completa", "seria", "alargada"),                       # Bradley
    5269: _r("#efc4a4", "lacio", "castano_claro", "corto", "incipiente", "seria", "alargada"),                     # Poborský
    4895: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "oval"),                                # Tomasson
    4679: _r("#b0703f", "rizado", "negro", "corto", "incipiente", "seria", "oval"),                                # Beausejour
    5347: _r("#efc4a4", "rizado", "castano_claro", "rulos", None, "seria", "alargada"),                            # Pyatov
    4755: _r("#e3ac86", "lacio", "castano_oscuro", "corto", "completa", "seria", "alargada"),                      # Cana
    5335: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "sonrisa", "alargada"),                          # Frei
    5303: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "alargada"),                    # Stojković
    5016: _r("#e3ac86", "lacio", "castano_oscuro", "largo_atado", None, "seria", "alargada"),                      # Gekas
    5313: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "sonrisa", "oval"),                              # Žigić
    6369: _r("#efc4a4", "lacio", "castano_oscuro", "tupe", "incipiente", "seria", "alargada"),                     # Kewell
    4736: _r("#efc4a4", "lacio", "castano_oscuro", "raya", None, "sonrisa", "alargada"),                           # Schiaffino
    5089: _r("#e3ac86", "lacio", "castano_oscuro", "flequillo", None, "seria", "oval"),                            # Benayoun
    5172: _r("#efc4a4", "lacio", "negro", "corto", None, "sonrisa", "redonda"),                                    # Sedloski
    5316: _r("#efc4a4", "lacio", "castano_claro", "corto", "completa", "seria", "alargada"),                       # Granqvist
    5285: _r("#efc4a4", "lacio", "rubio", "corto", None, "sonrisa", "alargada", entradas=True),                    # Anyukov
    5262: _r("#efc4a4", "lacio", "castano_claro", "flequillo", "completa", "seria", "alargada"),                   # Jankulovski
    5944: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "seria", "alargada"),                               # Asamoah
    4805: _r("#efc4a4", "lacio", "#c9c9c9", "corto", None, "seria", "alargada"),                                   # Krankl
    5228: _r("#efc4a4", "lacio", "castano_claro", "calvo", None, "seria", "alargada"),                             # Stam
    4848: _r("#e3ac86", "lacio", "negro", "corto", "incipiente", "seria", "oval"),                                 # Salihamidžić
    6890: _r("#d4996f", "lacio", "negro", "calvo", None, "seria", "oval"),                                         # Reid
    4926: _r("#efc4a4", "lacio", "castano_claro", "flequillo", None, "seria", "alargada"),                         # Pečnik
    6831: _r("#e3ac86", "lacio", "negro", "tupe", None, "seria", "alargada"),                                      # Lê Công Vinh
    6459: _r("#e3ac86", "lacio", "negro", "corto", None, "seria", "alargada"),                                     # Hong Myung-bo
    5314: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "completa", "seria", "alargada"),                      # Isaksson
    4689: _r("#d4996f", "lacio", "negro", "raya", "completa", "sonrisa", "alargada"),                              # Yepes
    5223: _r("#7a4524", "muy_rizado", "negro", "rapado", "incipiente", "seria", "alargada"),                       # Carew
    4978: _r("#efc4a4", "lacio", "negro", "corto", None, "seria", "alargada"),                                     # Speed
    6236: _r("#7a4524", "muy_rizado", "negro", "rapado", None, "seria", "oval"),                                   # McCarthy
    5327: _r("#5e331a", "rizado", "negro", "corto", "completa", "seria", "alargada"),                              # Djourou
    5288: _r("#efc4a4", "lacio", "pelirrojo", "flequillo", "completa", "seria", "alargada", lentes=True),          # Karpin
    5948: _r("#5e331a", "muy_rizado", "negro", "calvo", None, "sonrisa", "redonda"),                               # Appiah
    4858: _r("#e3ac86", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "alargada"),                    # Petrov
    6554: _r("#e3ac86", "lacio", "negro", "tupe", "completa", "seria", "alargada"),                                # Ansarifard
    4730: _r("#7a4524", "rizado", "negro", "corto", None, "seria", "alargada"),                                    # Farfán
    5063: _r("#efc4a4", "lacio", "rubio", "rapado", "incipiente", "seria", "alargada"),                            # Sigurðsson
    4975: _r("#b0703f", "rizado", "negro", "corto", "completa", "seria", "alargada"),                              # Williams
    4660: _r("#d4996f", "lacio", "negro", "corto", None, "seria", "redonda"),                                      # Baldivieso
    4846: _r("#efc4a4", "lacio", "castano_claro", "corto", None, "seria", "alargada"),                             # Misimović
    5868: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "seria", "oval"),                                   # Eboué
    4690: _r("#d4996f", "lacio", "negro", "rapado", None, "seria", "oval"),                                        # Córdoba
    6071: _r("#d4996f", "lacio", "negro", "corto", None, "seria", "alargada"),                                     # Chamakh
    4691: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "seria", "oval"),                                   # Zapata
    6131: _r("#5e331a", "muy_rizado", "negro", "tupe", None, "seria", "redonda"),                                  # Taiwo
    6532: _r("#d4996f", "lacio", "castano_oscuro", "tupe", "incipiente", "seria", "alargada"),                     # Bachdim
    5875: _r("#d4996f", "lacio", "negro", "corto", None, "seria", "alargada"),                                     # El Hadary
    6464: _r("#e3ac86", "lacio", "negro", "flequillo", None, "sonrisa", "alargada"),                               # Ki Sung-yueng
    5062: _r("#efc4a4", "lacio", "rubio", "tupe", None, "seria", "alargada"),                                      # Sævarsson
    5242: _r("#efc4a4", "lacio", "castano_oscuro", "flequillo", None, "seria", "alargada"),                        # Deyna
    4862: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "oval"),                                # M. Petrov
    5311: _r("#efc4a4", "lacio", "castano_oscuro", "flequillo", None, "seria", "alargada"),                        # Džajić
    4717: _r("#d4996f", "lacio", "negro", "largo_atado", None, "seria", "alargada"),                               # Valdez
    5071: _r("#efc4a4", "lacio", "rubio", "tupe", None, "sonrisa", "oval"),                                        # Sigþórsson
    4819: _r("#efc4a4", "rizado", "castano_claro", "rulos", None, "sonrisa", "alargada", entradas=True),           # Pfaff
    4738: _r("#d4996f", "lacio", "negro", "raya", None, "seria", "alargada"),                                      # Rocha
    4907: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "alargada", entradas=True),     # Mucha
    5046: _r("#efc4a4", "lacio", "pelirrojo", "corto", None, "seria", "oval"),                                      # J. McCarthy
    4855: _r("#e3ac86", "lacio", "negro", "corto", "completa", "seria", "alargada", entradas=True),                # Stoyanov
    5050: _r("#efc4a4", "lacio", "#c9c9c9", "flequillo", None, "sonrisa", "alargada"),                             # Jennings
    5559: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "seria", "oval"),                                   # Figueroa
    5625: _r("#d4996f", "lacio", "negro", "tupe", None, "sonrisa", "oval"),                                        # Salcido
    5866: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "seria", "oval"),                                   # Zokora
    5824: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "sonrisa", "redonda"),                              # Geremi
    5330: _r("#e3ac86", "lacio", "castano_oscuro", "corto", "incipiente", "seria", "alargada"),                    # Yakin
    5041: _r("#efc4a4", "lacio", "castano_claro", "rapado", None, "seria", "alargada"),                            # Dunne
    5260: _r("#efc4a4", "lacio", "castano_oscuro", "corto", "completa", "seria", "alargada"),                      # Ujfaluši
    5055: _r("#efc4a4", "lacio", "#c9c9c9", "calvo", None, "sonrisa", "alargada", lentes=True),                    # M. O'Neill
    4719: _r("#d4996f", "lacio", "negro", "corto", "incipiente", "seria", "alargada"),                             # Cardozo
    4994: _r("#efc4a4", "lacio", "#8a8582", "corto", "completa", "seria", "alargada"),                             # Kavelashvili
    5738: _r("#5e331a", "muy_rizado", "negro", "rastas", None, "sonrisa", "alargada"),                             # Spann
    6193: _r("#5e331a", "muy_rizado", "negro", "rapado", None, "seria", "alargada"),                               # Keita Baldé
    4851: _r("#efc4a4", "lacio", "castano_oscuro", "corto", None, "seria", "oval"),                                # Hrgović
}
