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
    6552: _r("#d4996f","lacio","negro","corto","incipiente","seria","oval"), # Nekounam
    5012: _r("#e3ac86","lacio","castano_oscuro","tupe",None,"sonrisa","oval"), # Zagorakis
    5023: _r("#efc4a4","lacio","negro","raya",None,"seria","oval"), # Bozsik
    5354: _r("#efc4a4","lacio","rubio","corto",None,"seria","oval"), # Husiev
    5332: _r("#e3ac86","lacio","castano_oscuro","rapado","incipiente","seria","alargada"), # Inler
    4694: _r("#7a4524","rizado","negro","trenzas",None,"sonrisa","oval"), # C. Sánchez
    5822: _r("#5e331a","muy_rizado","negro","rastas","incipiente","seria","oval"), # Nkoulou
    4800: _r("#efc4a4","lacio","negro","raya","candado","seria","alargada"), # Fuchs
    4798: _r("#efc4a4","lacio","castano","largo_atado","incipiente","seria","alargada"), # Prödl
    4826: _r("#efc4a4","lacio","castano_oscuro","raya",None,"seria","alargada"), # Wilmots
    5564: _r("#5e331a","rizado","negro","rapado","incipiente","sonrisa","redonda"), # Suazo
    6192: _r("#5e331a","rizado","negro","degradado","candado","seria","oval"), # Diouf
    6060: _r("#93572e","lacio","negro","calvo","completa","seria","oval"), # Kanouté
    5772: _r("#7a4524","rizado","negro","corto","candado","seria","oval"), # Sessègnon
    5246: _r("#efc4a4","lacio","castano","corto","incipiente","seria","alargada"), # Zurawski
    6189: _r("#452313","rizado","negro","rapado",None,"sonrisa","redonda"), # P. B. Diop
    4904: _r("#f6d7c3","lacio","castano_claro","ondulado",None,"sonrisa","oval"), # McCoist
    4903: _r("#efc4a4","lacio","castano_oscuro","raya","candado","seria","oval"), # Souness
    6056: _r("#5e331a","rizado","negro","rapado","incipiente","seria","oval"), # Sissoko
    4824: _r("#efc4a4","lacio","castano_claro","flequillo",None,"seria","alargada"), # Ceulemans
    6551: _r("#d4996f","lacio","negro","raya","incipiente","seria","alargada"), # Karimi
    5318: _r("#efc4a4","lacio","castano_claro","tupe",None,"seria","alargada"), # Lustig
    5945: _r("#5e331a","rizado","negro","rapado",None,"seria","oval"), # Paintsil
    5225: _r("#efc4a4","lacio","rubio","corto",None,"seria","alargada"), # Flo
    5504: _r("#93572e","rizado","negro","degradado","completa","sonrisa","oval"), # Onyewu
    4993: _r("#e3ac86","lacio","negro","raya",None,"seria","oval"), # Arveladze
    4695: _r("#7a4524","rizado","negro","calvo",None,"sonrisa","redonda",lentes=True), # Asprilla
    4681: _r("#d4996f","lacio","negro","corto","incipiente","seria","oval"), # Pizarro
    4733: _r("#e3ac86","lacio","negro","raya",None,"seria","alargada"), # Varela
    6190: _r("#5e331a","muy_rizado","negro","rastas","candado","seria","alargada"), # Cissé
    6522: _r("#e3ac86","lacio","negro","tupe",None,"seria","oval"), # Bhutia
    6068: _r("#d4996f","rizado","castano_oscuro","ondulado","candado","seria","alargada"), # Hadji
    5320: _r("#efc4a4","lacio","negro","raya",None,"sonrisa","alargada"), # Gren
    5025: _r("#efc4a4","lacio","castano_claro","tupe",None,"seria","alargada"), # Czibor
    5821: _r("#5e331a","rizado","negro","corto","candado","sonrisa","alargada"), # Song
    5271: _r("#efc4a4","lacio","castano_oscuro","ondulado",None,"sonrisa","oval"), # Popescu
    5502: _r("#e3ac86","lacio","negro","tupe","incipiente","seria","alargada"), # Bocanegra
    5441: _r("#5e331a","rizado","negro","calvo",None,"seria","oval"), # Hutchinson
    5352: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Rotan
    4807: _r("#efc4a4","rizado","castano_claro","rulos",None,"seria","oval"), # Polster
    4857: _r("#e3ac86","lacio","negro","ondulado",None,"seria","oval"), # Balakov
    5044: _r("#f6d7c3","lacio","castano_claro","corto",None,"sonrisa","oval"), # Whelan
    5017: _r("#efc4a4","lacio","castano_oscuro","raya",None,"seria","alargada"), # Grosics
    5229: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","cuadrada"), # Krol
    4703: _r("#d4996f","lacio","negro","tupe",None,"seria","oval"), # Noboa
    4980: _r("#efc4a4","lacio","negro","tupe","completa","seria","oval"), # Ledley
    5943: _r("#452313","rizado","negro","rapado","incipiente","sonrisa","redonda"), # Kuffour
    5220: _r("#efc4a4","lacio","castano_claro","calvo",None,"seria","oval"), # Solbakken
    4976: _r("#f6d7c3","lacio","pelirrojo","calvo","completa","seria","alargada"), # Collins
    5884: _r("#e3ac86","lacio","negro","rapado",None,"seria","alargada",lentes=True), # Zidan
    5624: _r("#c68458","lacio","negro","corto",None,"seria","oval"), # C. Suárez
    6465: _r("#e3ac86","lacio","negro","raya",None,"sonrisa","oval"), # Ahn
    6689: _r("#c68458","lacio","negro","rapado","incipiente","sonrisa","oval"), # Al-Habsi
    6467: _r("#e3ac86","lacio","negro","flequillo",None,"seria","redonda"), # Cha
    5655: _r("#e3ac86","lacio","negro","corto","incipiente","seria","alargada"), # Penedo
    4940: _r("#efc4a4","lacio","rubio","corto",None,"seria","alargada"), # Poom
    5272: _r("#e3ac86","lacio","negro","corto","incipiente","seria","oval"), # Raț
    4888: _r("#efc4a4","lacio","castano_claro","raya",None,"seria","alargada"), # M. Olsen
    6466: _r("#e3ac86","lacio","negro","flequillo",None,"seria","oval"), # Lee Chung-yong
    5280: _r("#e3ac86","lacio","negro","corto","incipiente","seria","alargada"), # Marica
    4707: _r("#5e331a","rizado","negro","tupe","candado","seria","oval"), # Caicedo
    5348: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","cuadrada"), # Kucher
    4902: _r("#efc4a4","ondulado","castano","ondulado",None,"seria","alargada"), # Bremner
    4683: _r("#e3ac86","lacio","negro","corto",None,"seria","oval"), # Carmona
    5756: _r("#d4996f","lacio","negro","corto","completa","seria","oval"), # Halliche
    5763: _r("#d4996f","rizado","negro","rulos",None,"sonrisa","oval"), # Madjer
    5506: _r("#c68458","rizado","castano_oscuro","rastas",None,"sonrisa","alargada"), # Cobi Jones
    6356: _r("#d4996f","lacio","negro","raya","incipiente","seria","alargada"), # Al-Jaber
    5820: _r("#452313","lacio","negro","calvo",None,"seria","redonda",lentes=True), # N'Kono
    5052: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Hughes
    5317: _r("#efc4a4","lacio","castano_claro","corto",None,"sonrisa","oval"), # P. Andersson
    4823: _r("#efc4a4","lacio","castano_claro","corto","incipiente","seria","alargada"), # Gerets
    6228: _r("#452313","lacio","negro","calvo",None,"sonrisa","redonda"), # Radebe
    4817: _r("#e3ac86","lacio","castano_oscuro","corto","incipiente","sonrisa","cuadrada"), # Gurbanov
    5349: _r("#efc4a4","lacio","castano","rapado",None,"seria","oval"), # Rakitskyi
    6066: _r("#d4996f","lacio","negro","rapado","incipiente","seria","oval"), # Regragui
    4849: _r("#efc4a4","lacio","castano_claro","calvo","completa","seria","redonda"), # Barbarez
    6357: _r("#5e331a","rizado","negro","afro","candado","seria","oval"), # Abdullah
    6556: _r("#d4996f","lacio","negro","raya",None,"seria","alargada"), # Mahdavikia
    4663: _r("#d4996f","lacio","negro","flequillo",None,"sonrisa","alargada"), # Moreno
    5219: _r("#efc4a4","lacio","castano_claro","calvo",None,"seria","oval"), # Berg
    5274: _r("#efc4a4","lacio","castano_claro","raya",None,"seria","alargada"), # Petrescu
}


# Jugadores ACTUALES más famosos (por Wikipedias, cruzados con Wikidata por nombre y edad), hechos a mano desde su foto.
AJUSTES_ACTUALES = {
    207: _r("#e3ac86","lacio","castano_oscuro","corto","completa","seria","oval"), # Messi
    3419: _r("#e3ac86","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Cristiano Ronaldo
    1505: _r("#7a4524","rizado","negro","degradado","incipiente","seria","oval"), # Mbappé
    1063: _r("#efc4a4","lacio","castano_claro","largo_atado",None,"seria","alargada"), # Modrić
    1221: _r("#d4996f","rizado","negro","corto","completa","seria","oval"), # Salah
    1384: _r("#93572e","rizado","castano","rulos",None,"seria","oval"), # Yamal
    3167: _r("#f6d7c3","lacio","rubio","largo_atado",None,"seria","alargada"), # Haaland
    1979: _r("#efc4a4","lacio","castano_claro","corto","incipiente","seria","alargada"), # Kane
    424: _r("#f6d7c3","lacio","castano_claro","raya","incipiente","seria","alargada"), # De Bruyne
    3793: _r("#5e331a","rizado","negro","rapado","candado","seria","oval"), # Mané
    428: _r("#5e331a","rizado","negro","calvo","completa","seria","cuadrada"), # Lukaku
    419: _r("#efc4a4","lacio","negro","corto","incipiente","seria","alargada"), # Courtois
    1980: _r("#7a4524","rizado","negro","degradado","candado","seria","oval"), # Rashford
    1506: _r("#5e331a","rizado","negro","degradado","incipiente","seria","alargada"), # Dembélé
    615: _r("#5e331a","rizado","negro","rulos",None,"seria","oval"), # Vinícius
    1976: _r("#7a4524","rizado","negro","degradado",None,"seria","oval"), # Bellingham
    999: _r("#e3ac86","lacio","negro","flequillo",None,"sonrisa","oval"), # Son
    1965: _r("#efc4a4","lacio","castano","corto","completa","seria","alargada"), # Henderson
    3236: _r("#93572e","rizado","negro","largo_atado","candado","seria","alargada"), # van Dijk
    596: _r("#c68458","lacio","negro","degradado",None,"seria","oval"), # Thiago Silva
    1382: _r("#e3ac86","lacio","negro","corto","incipiente","seria","oval"), # Rodri
    2832: _r("#d4996f","rizado","negro","rulos","incipiente","seria","oval"), # Hakimi
    1076: _r("#efc4a4","rizado","castano_oscuro","rulos","incipiente","seria","alargada"), # Perišić
    1035: _r("#c68458","lacio","negro","corto",None,"sonrisa","oval"), # Navas
    1969: _r("#5e331a","rizado","negro","rapado",None,"seria","oval"), # Saka
    3417: _r("#e3ac86","lacio","castano_oscuro","corto","completa","seria","alargada"), # Bruno Fernandes
    50: _r("#efc4a4","lacio","castano_claro","ondulado",None,"seria","alargada"), # Kimmich
    1372: _r("#e3ac86","lacio","negro","tupe",None,"seria","oval"), # Pedri
    3243: _r("#d4996f","rizado","negro","degradado","incipiente","seria","alargada"), # Depay
    45: _r("#efc4a4","lacio","castano_claro","corto","incipiente","sonrisa","alargada"), # ter Stegen
    1128: _r("#efc4a4","lacio","castano_claro","ondulado",None,"seria","alargada"), # Eriksen
    289: _r("#7a4524","rizado","negro","degradado",None,"seria","oval"), # Alaba
    1373: _r("#e3ac86","lacio","castano_oscuro","ondulado","incipiente","seria","alargada"), # F. Torres
    2292: _r("#e3ac86","lacio","negro","tupe","candado","seria","oval"), # Nagatomo
    2297: _r("#e3ac86","lacio","negro","largo_atado",None,"seria","alargada"), # Minamino
    1959: _r("#efc4a4","lacio","castano_claro","raya",None,"seria","oval"), # Pickford
    4451: _r("#e3ac86","lacio","castano_oscuro","corto","incipiente","sonrisa","oval"), # Valverde
    2245: _r("#efc4a4","lacio","negro","tupe","completa","seria","alargada"), # Donnarumma
    208: _r("#e3ac86","lacio","negro","degradado",None,"seria","alargada"), # L. Martínez
    1593: _r("#efc4a4","lacio","castano_oscuro","ondulado","completa","seria","alargada"), # Kvaratskhelia
    1964: _r("#efc4a4","lacio","castano_oscuro","ondulado","incipiente","seria","alargada"), # Rice
    220: _r("#efc4a4","rizado","castano","rulos",None,"seria","oval"), # J. Álvarez
    3152: _r("#efc4a4","lacio","rubio","raya","incipiente","seria","alargada"), # Ødegaard
    1963: _r("#7a4524","rizado","negro","degradado",None,"seria","alargada"), # Alexander-Arnold
    3418: _r("#e3ac86","lacio","negro","corto","completa","seria","oval"), # B. Silva
    55: _r("#93572e","rizado","negro","raya","candado","seria","alargada"), # Sané
    200: _r("#e3ac86","lacio","castano_oscuro","corto","completa","seria","cuadrada"), # Otamendi
    1509: _r("#efc4a4","rizado","castano_oscuro","rulos",None,"seria","oval"), # Pavard
    3428: _r("#e3ac86","lacio","castano_oscuro","ondulado",None,"seria","alargada"), # J. Félix
    3255: _r("#93572e","rizado","negro","rapado","completa","seria","oval"), # Gakpo
    1504: _r("#efc4a4","lacio","castano","largo_atado","incipiente","seria","alargada"), # Rabiot
    1961: _r("#efc4a4","lacio","castano","corto",None,"seria","cuadrada"), # Stones
    1371: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # Olmo
    3241: _r("#efc4a4","lacio","castano_claro","ondulado",None,"seria","alargada"), # de Jong
    614: _r("#e3ac86","lacio","negro","degradado",None,"seria","oval"), # Richarlison
    4058: _r("#5e331a","rizado","negro","degradado","completa","seria","alargada"), # Isak
    2253: _r("#efc4a4","lacio","castano","raya",None,"seria","alargada"), # Chiesa
    1514: _r("#5e331a","muy_rizado","negro","rastas",None,"sonrisa","oval"), # Camavinga
    4384: _r("#e3ac86","lacio","negro","tupe","candado","seria","alargada"), # Çalhanoğlu
    1343: _r("#efc4a4","lacio","castano_claro","corto","completa","seria","alargada"), # Oblak
    1175: _r("#5e331a","rizado","rubio","rapado","completa","seria","oval"), # E. Valencia
    3414: _r("#e3ac86","lacio","negro","ondulado",None,"seria","alargada"), # Cancelo
    604: _r("#93572e","rizado","negro","rapado","candado","seria","oval"), # Gabriel Jesus
    1197: _r("#efc4a4","lacio","castano_oscuro","ondulado","completa","seria","alargada"), # Pulisic
    1499: _r("#efc4a4","lacio","castano_oscuro","rapado","completa","seria","oval"), # L. Hernandez
    3237: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # de Ligt
    4069: _r("#efc4a4","lacio","castano","tupe",None,"seria","alargada"), # Gyökeres
    1500: _r("#7a4524","rizado","negro","trenzas","incipiente","seria","alargada"), # Koundé
    4445: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","oval"), # Muslera
    51: _r("#efc4a4","lacio","castano","ondulado","incipiente","seria","alargada"), # Goretzka
    1125: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Christensen
    1381: _r("#e3ac86","lacio","negro","corto","completa","seria","alargada"), # Merino
    1385: _r("#e3ac86","lacio","castano_oscuro","corto","incipiente","seria","oval"), # Oyarzabal
    215: _r("#efc4a4","lacio","rubio","rapado","incipiente","seria","oval"), # Mac Allister
    62: _r("#efc4a4","lacio","castano","ondulado",None,"seria","alargada"), # Wirtz
    1513: _r("#7a4524","rizado","rubio","rulos",None,"seria","oval"), # Doué
    597: _r("#d4996f","rizado","negro","rulos","incipiente","seria","alargada"), # Marquinhos
    924: _r("#5e331a","muy_rizado","negro","afro","incipiente","seria","oval"), # Cuadrado
    426: _r("#d4996f","lacio","negro","degradado","candado","seria","alargada"), # Tielemans
    1974: _r("#7a4524","rizado","negro","degradado","completa","seria","oval"), # R. James
    779: _r("#7a4524","rizado","castano_oscuro","rulos","completa","seria","alargada"), # Choupo-Moting
    205: _r("#e3ac86","lacio","negro","tupe","incipiente","seria","alargada"), # Paredes
    434: _r("#efc4a4","rizado","castano_oscuro","rulos","candado","seria","alargada"), # Meunier
    2817: _r("#d4996f","lacio","negro","corto","incipiente","seria","alargada"), # Bounou
    3816: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Jović
    2299: _r("#e3ac86","lacio","negro","flequillo",None,"seria","oval"), # Doan
    1365: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","cuadrada"), # Unai Simón
    2833: _r("#e3ac86","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Brahim
    607: _r("#7a4524","rizado","negro","rapado","candado","seria","oval"), # Militão
    1910: _r("#efc4a4","ondulado","castano_oscuro","largo_atado","completa","seria","alargada"), # Szoboszlai
    2074: _r("#efc4a4","lacio","castano_oscuro","raya","incipiente","seria","alargada"), # Sigurðsson
    780: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Aboubakar
    1065: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Kramarić
    3786: _r("#452313","rizado","negro","rapado","completa","seria","oval"), # Koulibaly
    1366: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","oval"), # Laporte
    204: _r("#efc4a4","lacio","castano_oscuro","rapado","incipiente","seria","alargada"), # De Paul
    57: _r("#7a4524","rizado","negro","rapado","completa","seria","alargada"), # Tah
    212: _r("#e3ac86","lacio","negro","flequillo",None,"sonrisa","alargada"), # Lisandro Martínez
    3425: _r("#7a4524","rizado","negro","rapado",None,"seria","oval"), # Nuno Mendes
    1517: _r("#7a4524","rizado","castano_oscuro","trenzas","incipiente","seria","alargada"), # Barcola
    1378: _r("#efc4a4","lacio","castano_oscuro","ondulado",None,"seria","alargada"), # Cubarsí
    552: _r("#efc4a4","lacio","castano_oscuro","raya","completa","seria","alargada"), # Kolašinac
    4409: _r("#efc4a4","lacio","castano_claro","tupe","completa","seria","alargada"), # Yarmolenko
    4085: _r("#efc4a4","lacio","castano_oscuro","largo_atado","completa","seria","alargada"), # R. Rodríguez
    727: _r("#93572e","rizado","negro","rulos","completa","seria","oval"), # Vozinha
    4446: _r("#e3ac86","lacio","castano_oscuro","ondulado","incipiente","seria","oval"), # J. M. Giménez
    4080: _r("#5e331a","muy_rizado","negro","rulos","incipiente","seria","oval"), # Embolo
    3415: _r("#5e331a","rizado","negro","degradado","incipiente","seria","alargada"), # Semedo
    1018: _r("#452313","rizado","negro","rapado","completa","seria","oval"), # Kessié
    1376: _r("#e3ac86","rizado","castano_oscuro","largo_atado","completa","sonrisa","alargada"), # Raya
    4073: _r("#d4996f","rizado","negro","trenzas",None,"seria","alargada"), # Akanji
    3250: _r("#5e331a","rizado","negro","degradado",None,"seria","oval"), # Dumfries
    2295: _r("#e3ac86","lacio","negro","flequillo",None,"seria","oval"), # Kamada
    2290: _r("#e3ac86","lacio","negro","tupe",None,"seria","oval"), # Tomiyasu
    3413: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Rúben Dias
    2306: _r("#e3ac86","lacio","castano_oscuro","flequillo",None,"seria","oval"), # Tanaka
    1305: _r("#efc4a4","lacio","castano_oscuro","flequillo",None,"seria","alargada"), # McTominay
    1978: _r("#f6d7c3","ondulado","castano_claro","ondulado",None,"seria","alargada"), # Gordon
    4454: _r("#e3ac86","lacio","castano_oscuro","largo_atado",None,"seria","alargada"), # Darwin Núñez
    1073: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Pašalić
    3132: _r("#5e331a","rizado","negro","trenzas","incipiente","seria","alargada"), # Iwobi
    4458: _r("#c68458","rizado","rubio","rapado","completa","seria","oval"), # R. Araújo
    2298: _r("#e3ac86","lacio","castano_oscuro","flequillo",None,"seria","oval"), # Ueda
    3791: _r("#5e331a","rizado","negro","rapado",None,"seria","oval"), # I. Gueye
    2958: _r("#efc4a4","lacio","negro","cresta","incipiente","seria","alargada"), # Jovetić
    4050: _r("#efc4a4","lacio","castano_oscuro","flequillo",None,"seria","alargada"), # Lindelöf
    3395: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Zieliński
    3157: _r("#efc4a4","lacio","rubio","tupe",None,"seria","cuadrada"), # Sørloth
    1497: _r("#5e331a","rizado","negro","degradado","candado","seria","oval"), # Maignan
    1515: _r("#d4996f","rizado","negro","rulos","completa","seria","oval"), # Cherki
    3248: _r("#d4996f","rizado","castano_oscuro","trenzas",None,"sonrisa","alargada"), # Aké
    3614: _r("#efc4a4","lacio","rubio","tupe",None,"seria","alargada"), # Golovin
    2821: _r("#d4996f","lacio","negro","calvo","completa","seria","oval"), # Mazraoui
    1977: _r("#5e331a","rizado","negro","rastas","incipiente","seria","alargada"), # Eze
    1379: _r("#e3ac86","lacio","castano_oscuro","corto","incipiente","sonrisa","oval"), # Eric García
    1071: _r("#efc4a4","rizado","castano_oscuro","rulos","completa","seria","alargada"), # Gvardiol
    2029: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Coleman
    3813: _r("#efc4a4","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Tadić
    213: _r("#e3ac86","lacio","castano_oscuro","tupe","completa","seria","alargada"), # Tagliafico
    210: _r("#e3ac86","lacio","negro","degradado","completa","seria","oval"), # Rulli
    3812: _r("#efc4a4","lacio","castano","tupe","incipiente","seria","alargada"), # Milinković-Savić
    2301: _r("#e3ac86","lacio","castano_claro","flequillo",None,"seria","oval"), # Itakura
    64: _r("#93572e","rizado","negro","rulos",None,"seria","alargada"), # Adeyemi
    612: _r("#d4996f","lacio","negro","degradado","candado","seria","oval"), # B. Guimarães
    1193: _r("#d4996f","rizado","negro","degradado",None,"seria","oval"), # Dest
    439: _r("#efc4a4","lacio","castano","raya",None,"seria","alargada"), # De Ketelaere
    1507: _r("#efc4a4","lacio","castano_oscuro","raya",None,"sonrisa","alargada"), # Thauvin
    297: _r("#efc4a4","lacio","castano_oscuro","largo_atado","candado","seria","alargada"), # Sabitzer
    2260: _r("#e3ac86","rizado","castano_oscuro","rulos","candado","seria","oval"), # Di Lorenzo
    266: _r("#efc4a4","lacio","castano","corto","completa","seria","alargada"), # Degenek
    1074: _r("#efc4a4","lacio","castano_oscuro","raya","completa","seria","alargada"), # Vlašić
    1968: _r("#d4996f","rizado","castano_oscuro","rulos","incipiente","sonrisa","alargada"), # Calvert-Lewin
    1021: _r("#452313","rizado","negro","rapado","incipiente","seria","alargada"), # Pépé
    904: _r("#452313","rizado","negro","degradado",None,"seria","oval",lentes=True), # Dav. Sánchez
    201: _r("#e3ac86","lacio","negro","degradado",None,"seria","oval"), # C. Romero
    1960: _r("#5e331a","rizado","negro","rapado",None,"seria","oval"), # Guéhi
    1512: _r("#d4996f","rizado","negro","trenzas","candado","seria","alargada"), # Gusto
    1184: _r("#5e331a","rizado","rubio","rapado",None,"seria","oval"), # Caicedo
    3427: _r("#efc4a4","rizado","castano_oscuro","rulos","incipiente","seria","alargada"), # J. Neves
    1383: _r("#efc4a4","rizado","castano","rulos",None,"seria","oval"), # Fermín López
    1131: _r("#d4996f","rizado","negro","largo_atado",None,"seria","alargada"), # Poulsen
    1057: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Livaković
    2891: _r("#d4996f","lacio","negro","corto",None,"seria","oval"), # Lozano
    206: _r("#e3ac86","lacio","castano","degradado","incipiente","sonrisa","alargada"), # Lo Celso
    3420: _r("#e3ac86","rizado","negro","rulos","completa","seria","alargada"), # G. Ramos
    1542: _r("#efc4a4","lacio","castano_claro","raya",None,"seria","alargada"), # Davies
    2950: _r("#efc4a4","lacio","castano_oscuro","ondulado","candado","seria","alargada"), # Savić
    4077: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","sonrisa","oval"), # Freuler
    2012: _r("#d4996f","lacio","negro","tupe","completa","seria","oval"), # Taremi
    1132: _r("#f6d7c3","lacio","rubio","raya",None,"seria","alargada"), # Dolberg
    3794: _r("#452313","rizado","negro","degradado",None,"seria","alargada"), # I. Sarr
    1377: _r("#efc4a4","lacio","castano_oscuro","flequillo",None,"seria","alargada"), # Le Normand
    1220: _r("#d4996f","rizado","negro","rulos","completa","sonrisa","oval"), # Marmoush
    1210: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Weah
    3421: _r("#efc4a4","lacio","castano_oscuro","raya",None,"sonrisa","alargada"), # F. Conceição
    3823: _r("#efc4a4","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Kostić
    265: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","cuadrada"), # Ryan
    3615: _r("#efc4a4","lacio","castano_oscuro","ondulado","incipiente","seria","alargada"), # Miranchuk
    1077: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Budimir
    1301: _r("#efc4a4","lacio","castano_oscuro","raya",None,"seria","alargada"), # Tierney
    608: _r("#7a4524","rizado","negro","degradado","incipiente","seria","oval"), # Magalhães
    2246: _r("#e3ac86","rizado","negro","rulos",None,"seria","alargada"), # Bastoni
    4381: _r("#e3ac86","lacio","negro","corto","completa","seria","oval"), # Demiral
    3432: _r("#e3ac86","ondulado","castano_oscuro","ondulado","completa","seria","alargada"), # Pedro Neto
    1380: _r("#e3ac86","lacio","negro","corto",None,"seria","oval"), # Porro
    1370: _r("#e3ac86","lacio","castano_oscuro","corto","completa","seria","alargada"), # Baena
    1332: _r("#efc4a4","lacio","castano_oscuro","raya","incipiente","seria","alargada"), # Dúbravka
    2262: _r("#efc4a4","lacio","castano_oscuro","ondulado","completa","seria","alargada"), # Cristante
    4461: _r("#e3ac86","lacio","castano_oscuro","tupe","completa","seria","alargada"), # De Arrascaeta
    3391: _r("#efc4a4","lacio","castano_oscuro","raya",None,"seria","alargada"), # Bednarek
    1000: _r("#e3ac86","lacio","negro","raya",None,"sonrisa","oval"), # Hwang Hee-chan
    214: _r("#e3ac86","lacio","castano_oscuro","tupe","incipiente","seria","oval"), # Montiel
    3161: _r("#efc4a4","lacio","rubio","rapado","incipiente","seria","alargada"), # Ryerson
    1194: _r("#7a4524","rizado","negro","rulos",None,"seria","oval"), # McKennie
    1975: _r("#7a4524","rizado","negro","degradado",None,"seria","oval"), # Rogers
    1143: _r("#f6d7c3","lacio","rubio","corto",None,"sonrisa","alargada"), # Højlund
    1605: _r("#e3ac86","lacio","negro","tupe","incipiente","seria","oval"), # Mikautadze
    3805: _r("#5e331a","rizado","negro","rapado",None,"seria","alargada"), # N. Jackson
    4468: _r("#e3ac86","lacio","castano_oscuro","tupe",None,"seria","oval"), # Khusanov
    1325: _r("#efc4a4","lacio","castano_claro","raya",None,"seria","alargada"), # Pekarík
    186: _r("#d4996f","lacio","negro","rapado",None,"seria","alargada"), # Slimani
    1040: _r("#d4996f","lacio","negro","tupe","completa","seria","alargada"), # Borges
    436: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Vanaken
    4142: _r("#e3ac86","lacio","rubio","tupe",None,"seria","oval"), # Chanathip
    37: _r("#efc4a4","lacio","negro","tupe","completa","seria","alargada"), # Hysaj
    3398: _r("#efc4a4","lacio","castano_claro","corto",None,"sonrisa","alargada"), # Piątek
    3411: _r("#efc4a4","lacio","castano_oscuro","tupe","completa","seria","alargada"), # Diogo Costa
    992: _r("#e3ac86","lacio","negro","corto",None,"seria","cuadrada"), # Kim Min-jae
    2818: _r("#d4996f","ondulado","negro","ondulado",None,"sonrisa","alargada"), # Aguerd
    2250: _r("#efc4a4","lacio","negro","tupe",None,"seria","alargada"), # Tonali
    801: _r("#452313","rizado","negro","rulos",None,"seria","oval"), # J. David
    430: _r("#efc4a4","ondulado","castano_oscuro","ondulado",None,"seria","alargada"), # Lammens
    1585: _r("#efc4a4","lacio","negro","tupe","completa","seria","alargada"), # Mamardashvili
    1966: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # E. Anderson
    1367: _r("#efc4a4","lacio","castano","corto",None,"seria","alargada"), # Huijsen
    3158: _r("#efc4a4","lacio","castano_claro","raya","incipiente","seria","alargada"), # Nyland
    1327: _r("#efc4a4","lacio","rubio","tupe","incipiente","seria","alargada"), # Duda
    1008: _r("#e3ac86","lacio","negro","raya",None,"seria","oval"), # Lee Kang-in
    423: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Castagne
    3129: _r("#452313","rizado","negro","rapado","incipiente","seria","oval"), # Aina
    601: _r("#7a4524","rizado","negro","rulos","completa","seria","oval"), # Douglas Luiz
    1207: _r("#efc4a4","rizado","castano_oscuro","rulos",None,"seria","alargada"), # Aaronson
    3251: _r("#d4996f","lacio","negro","corto","incipiente","sonrisa","alargada"), # Reijnders
    4071: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Kobel
    305: _r("#efc4a4","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Baumgartner
    3244: _r("#d4996f","rizado","castano_oscuro","rulos",None,"seria","oval"), # Zirkzee
    2823: _r("#d4996f","lacio","negro","corto","incipiente","seria","alargada"), # Ounahi
    273: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Leckie
    1944: _r("#d4996f","lacio","negro","tupe","completa","seria","alargada"), # Lilipaly
    2076: _r("#f6d7c3","lacio","pelirrojo","calvo","completa","seria","alargada"), # Gunnarsson
    669: _r("#5e331a","rizado","negro","rulos",None,"seria","alargada"), # B. Traoré
    3373: _r("#c68458","rizado","negro","rulos",None,"seria","oval"), # Carrillo
    268: _r("#efc4a4","lacio","castano_oscuro","rapado","completa","seria","oval"), # Behich
    211: _r("#efc4a4","lacio","castano_oscuro","corto","completa","sonrisa","alargada"), # Pezzella
    2018: _r("#d4996f","lacio","negro","tupe","completa","seria","alargada"), # Rezaeian
    4449: _r("#efc4a4","lacio","rubio","corto",None,"seria","alargada"), # G. Varela
    802: _r("#7a4524","rizado","negro","degradado","completa","seria","oval"), # Larin
    1070: _r("#efc4a4","lacio","castano_oscuro","raya","completa","seria","alargada"), # Čaleta-Car
    292: _r("#f6d7c3","lacio","rubio","corto","completa","seria","alargada"), # Laimer
    3463: _r("#5e331a","rizado","negro","rapado",None,"seria","alargada"), # Almoez Ali
    1687: _r("#efc4a4","ondulado","castano_claro","ondulado","incipiente","seria","alargada"), # Tsimikas
    3809: _r("#efc4a4","lacio","castano_oscuro","tupe",None,"seria","alargada"), # Milenković
    1127: _r("#efc4a4","lacio","castano_oscuro","tupe",None,"seria","alargada"), # Mæhle
    4089: _r("#d4996f","lacio","negro","corto",None,"sonrisa","oval"), # R. Vargas
    3802: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Pape Gueye
    790: _r("#d4996f","lacio","negro","calvo","completa","sonrisa","oval"), # Mbeumo
    1386: _r("#efc4a4","rizado","castano_oscuro","rulos","candado","seria","alargada"), # Pino
    1453: _r("#efc4a4","lacio","castano_claro","corto","incipiente","seria","alargada"), # Hrádecký
    296: _r("#efc4a4","lacio","castano_oscuro","tupe",None,"seria","alargada"), # Gregoritsch
    3346: _r("#d4996f","rizado","negro","rulos","candado","seria","oval"), # G. Gómez
    4410: _r("#efc4a4","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Yaremchuk
    52: _r("#d4996f","lacio","negro","tupe","incipiente","seria","oval"), # Amiri
    998: _r("#e3ac86","lacio","negro","flequillo",None,"sonrisa","oval"), # Hwang In-beom
    1195: _r("#93572e","rizado","negro","rulos",None,"seria","oval"), # T. Adams
    56: _r("#efc4a4","lacio","rubio","tupe",None,"seria","alargada"), # Nübel
    2904: _r("#5e331a","rizado","negro","rapado","completa","sonrisa","alargada"), # Quiñones
    1558: _r("#d4996f","rizado","castano_oscuro","rulos",None,"seria","alargada"), # Ampadu
    2332: _r("#d4996f","lacio","negro","tupe","completa","seria","alargada"), # Al-Taamari
    63: _r("#93572e","rizado","negro","rulos","incipiente","seria","oval"), # Nmecha
    217: _r("#efc4a4","rizado","castano","rulos",None,"seria","oval"), # Simeone
    23: _r("#efc4a4","rizado","castano_oscuro","rulos","incipiente","seria","alargada"), # Berisha
    3350: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","oval"), # Almirón
    2071: _r("#f6d7c3","lacio","castano_claro","corto","completa","seria","alargada"), # Ingason
    1552: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Ward
    1169: _r("#5e331a","rizado","negro","rapado",None,"seria","oval"), # Estupiñán
    46: _r("#efc4a4","lacio","castano_claro","corto","incipiente","seria","alargada"), # Anton
    4462: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Ugarte
    61: _r("#efc4a4","lacio","castano_claro","tupe","incipiente","seria","alargada"), # Raum
    2903: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # S. Giménez
    3609: _r("#f6d7c3","lacio","rubio","largo_atado","candado","seria","alargada"), # Safonov
    1674: _r("#efc4a4","lacio","castano_oscuro","raya","candado","seria","alargada"), # Mavropanos
    2826: _r("#d4996f","rizado","negro","rapado",None,"seria","oval"), # Rahimi
    3819: _r("#efc4a4","lacio","castano_oscuro","rapado","incipiente","seria","alargada"), # Pavlović
    3390: _r("#efc4a4","lacio","castano","corto",None,"seria","alargada"), # Kiwior
    3247: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # van de Ven
    2300: _r("#d4996f","rizado","negro","rulos",None,"seria","oval"), # Z. Suzuki
    1168: _r("#5e331a","rizado","negro","rapado",None,"seria","oval"), # Pacho
    3426: _r("#e3ac86","rizado","castano_oscuro","rulos","completa","seria","alargada"), # Nunes
    3166: _r("#f6d7c3","rizado","castano_claro","rulos",None,"seria","alargada"), # Schjelderup
    4070: _r("#5e331a","rizado","negro","trenzas","incipiente","seria","alargada"), # Elanga
    4054: _r("#f6d7c3","lacio","rubio","ondulado",None,"seria","alargada"), # Bergvall
    4477: _r("#e3ac86","lacio","negro","tupe",None,"seria","oval"), # Fayzullaev
    2033: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","sonrisa","alargada"), # Brady
    1462: _r("#f6d7c3","lacio","rubio","ondulado","incipiente","sonrisa","alargada"), # Pohjanpalo
    1105: _r("#7a4524","rizado","negro","rapado","completa","sonrisa","oval"), # Bacuna
    275: _r("#452313","rizado","negro","rapado",None,"seria","alargada"), # Mabil
    271: _r("#f6d7c3","lacio","rubio","largo_atado","candado","seria","alargada"), # Irvine
    180: _r("#d4996f","lacio","negro","tupe","incipiente","sonrisa","oval",lentes=True), # Bensebaini
    4380: _r("#efc4a4","lacio","castano_oscuro","ondulado",None,"seria","alargada"), # Söyüncü
    3474: _r("#7a4524","muy_rizado","negro","afro","completa","seria","alargada"), # Afif
    1990: _r("#d4996f","rizado","negro","rulos","completa","sonrisa","oval"), # A. Hussein
    48: _r("#efc4a4","lacio","castano_claro","tupe",None,"seria","alargada"), # Mittelstädt
    1062: _r("#efc4a4","lacio","castano_claro","raya","incipiente","seria","alargada"), # Majer
    2257: _r("#efc4a4","lacio","negro","tupe",None,"seria","alargada"), # Mancini
    307: _r("#efc4a4","lacio","castano_claro","raya",None,"seria","alargada"), # Kalajdžić
    3540: _r("#efc4a4","lacio","castano_oscuro","flequillo",None,"seria","alargada"), # Hložek
    2266: _r("#efc4a4","lacio","castano_oscuro","corto",None,"sonrisa","oval"), # Raspadori
    1544: _r("#efc4a4","rizado","castano_oscuro","ondulado",None,"seria","alargada"), # N. Williams
    65: _r("#efc4a4","ondulado","rubio","ondulado","incipiente","seria","alargada"), # Woltemade
    1970: _r("#efc4a4","lacio","castano_oscuro","largo_atado","completa","seria","alargada"), # Trafford
    1907: _r("#efc4a4","rizado","castano_oscuro","ondulado","incipiente","seria","alargada"), # Kerkez
    209: _r("#e3ac86","lacio","castano_oscuro","corto",None,"seria","oval"), # Mastantuono
    561: _r("#efc4a4","ondulado","castano_oscuro","ondulado","candado","seria","alargada"), # Alajbegović
    193: _r("#c68458","lacio","negro","rapado",None,"seria","oval"), # Brahimi
    4382: _r("#efc4a4","lacio","negro","tupe","incipiente","seria","alargada"), # Ayhan
    269: _r("#452313","rizado","negro","rapado","completa","seria","oval"), # Geria
    293: _r("#f6d7c3","lacio","rubio","ondulado",None,"seria","alargada"), # Schlager
    4619: _r("#452313","rizado","negro","degradado",None,"sonrisa","oval"), # Daka
    2277: _r("#5e331a","rizado","negro","afro","incipiente","seria","oval"), # Bailey
    3404: _r("#efc4a4","rizado","castano_oscuro","ondulado",None,"sonrisa","alargada"), # Cash
    1106: _r("#93572e","muy_rizado","negro","afro",None,"seria","alargada"), # Chong
    3159: _r("#efc4a4","lacio","castano_claro","rapado",None,"seria","alargada"), # Østigård
    4404: _r("#efc4a4","lacio","castano_oscuro","rapado",None,"sonrisa","oval"), # Mykolenko
    1498: _r("#d4996f","rizado","negro","degradado","candado","seria","alargada"), # Lacroix
    1025: _r("#452313","rizado","negro","trenzas","incipiente","seria","alargada"), # Kossounou
    1069: _r("#efc4a4","lacio","castano_oscuro","raya","incipiente","seria","alargada"), # Stanišić
    47: _r("#93572e","rizado","negro","degradado",None,"seria","oval"), # Thiaw
    3155: _r("#c68458","rizado","rubio","rulos",None,"seria","alargada"), # Nusa
    1972: _r("#5e331a","rizado","negro","degradado",None,"seria","oval"), # Quansah
    3412: _r("#93572e","rizado","castano_oscuro","afro","candado","seria","alargada"), # Veiga
    2070: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # Magnússon
    4407: _r("#efc4a4","lacio","castano_oscuro","raya",None,"seria","alargada"), # Malinovskyi
    3807: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Rajković
    1124: _r("#efc4a4","ondulado","castano","largo_atado","incipiente","seria","alargada"), # J. Andersen
    3164: _r("#efc4a4","lacio","castano_claro","ondulado",None,"seria","alargada"), # Berge
    440: _r("#5e331a","rizado","negro","degradado","completa","seria","alargada"), # Lukébakio
    3826: _r("#efc4a4","lacio","castano_oscuro","tupe",None,"seria","alargada"), # Radonjić
    1200: _r("#efc4a4","lacio","castano_claro","raya","completa","seria","alargada"), # Turner
    302: _r("#efc4a4","lacio","castano_oscuro","tupe",None,"sonrisa","alargada"), # Friedl
    3254: _r("#f6d7c3","lacio","rubio","tupe",None,"seria","alargada"), # Lang
    3788: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Diatta
    4392: _r("#efc4a4","lacio","castano_oscuro","tupe","incipiente","sonrisa","oval"), # Kabak
    4391: _r("#e3ac86","lacio","negro","corto",None,"sonrisa","oval"), # Müldür
    2251: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Frattesi
    673: _r("#452313","rizado","negro","rulos","incipiente","seria","alargada"), # Tapsoba
    814: _r("#7a4524","rizado","negro","rulos",None,"seria","oval"), # Buchanan
    1502: _r("#5e331a","muy_rizado","negro","rastas","candado","seria","alargada"), # Koné
    3392: _r("#f6d7c3","rizado","rubio","rulos",None,"seria","alargada"), # Zalewski
    4464: _r("#efc4a4","rizado","castano_oscuro","ondulado",None,"seria","oval"), # Pellistri
    3423: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Inácio
    3790: _r("#452313","rizado","negro","degradado",None,"sonrisa","oval"), # P. M. Sarr
    2836: _r("#d4996f","rizado","castano_oscuro","rulos","incipiente","seria","alargada"), # Ezzalzouli
    3168: _r("#c68458","rizado","negro","rulos","incipiente","seria","alargada"), # Bobb
    1060: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Vušković
    746: _r("#93572e","rizado","negro","rulos",None,"seria","oval"), # R. Mendes
    3354: _r("#d4996f","lacio","negro","tupe","incipiente","seria","alargada"), # Sanabria
    4396: _r("#e3ac86","lacio","negro","tupe","incipiente","seria","alargada"), # Kahveci
    3148: _r("#efc4a4","lacio","castano_claro","raya","incipiente","seria","alargada"), # Ajer
    4084: _r("#e3ac86","lacio","negro","corto","completa","seria","alargada"), # Cömert
    4466: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Canobbio
    1971: _r("#efc4a4","lacio","castano_oscuro","raya",None,"seria","alargada"), # White
    3156: _r("#efc4a4","ondulado","castano","ondulado",None,"seria","alargada"), # Strand Larsen
    798: _r("#efc4a4","lacio","negro","raya","incipiente","seria","alargada"), # Eustáquio
    810: _r("#f6d7c3","lacio","rubio","tupe","incipiente","seria","alargada"), # Millar
    907: _r("#d4996f","lacio","negro","degradado","candado","seria","oval",lentes=True), # D. Muñoz
    555: _r("#efc4a4","lacio","castano_oscuro","raya","incipiente","seria","alargada"), # Dedić
    304: _r("#efc4a4","lacio","rubio","corto",None,"seria","alargada"), # Seiwald
    3249: _r("#7a4524","rizado","negro","degradado","incipiente","seria","oval"), # Maatsen
    431: _r("#efc4a4","rizado","castano_oscuro","largo_atado","incipiente","seria","alargada"), # Theate
    4398: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Aktürkoğlu
    1075: _r("#efc4a4","lacio","castano_oscuro","ondulado","incipiente","seria","alargada"), # Baturina
    1518: _r("#c68458","rizado","castano_oscuro","rulos",None,"seria","alargada"), # Akliouche
    1962: _r("#c68458","rizado","negro","rulos",None,"sonrisa","alargada"), # R. Lewis
    1064: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Sučić
    2901: _r("#d4996f","lacio","negro","corto",None,"seria","oval"), # G. Mora
    3246: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # Flekken
    421: _r("#efc4a4","lacio","castano_oscuro","raya","completa","seria","alargada"), # Mechele
    1550: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # K. Moore
    4450: _r("#e3ac86","lacio","castano_oscuro","corto","completa","seria","alargada"), # N. Nández
    2069: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # Rúnarsson
    3153: _r("#efc4a4","rizado","castano_claro","rulos",None,"seria","alargada"), # P. Berg
    3409: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Świderski
    299: _r("#f6d7c3","lacio","rubio","tupe",None,"seria","alargada"), # Lienhart
    3593: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # R. Marin
    1024: _r("#93572e","rizado","negro","degradado","incipiente","seria","oval"), # Lafont
    2902: _r("#d4996f","lacio","negro","corto",None,"seria","oval"), # Alvarado
    1333: _r("#efc4a4","lacio","castano_oscuro","tupe","completa","seria","alargada"), # Hancko
    2996: _r("#5e331a","rizado","negro","rapado",None,"seria","oval"), # Mandava
    277: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # Souttar
    4393: _r("#efc4a4","rizado","castano_oscuro","rulos","incipiente","sonrisa","alargada"), # Kadıoğlu
    1014: _r("#452313","rizado","negro","degradado","incipiente","seria","oval"), # Ndicka
    3538: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Sadílek
    291: _r("#f6d7c3","lacio","rubio","raya",None,"seria","alargada"), # Posch
    191: _r("#d4996f","rizado","negro","rulos","completa","seria","oval"), # Aït-Nouri
    2399: _r("#efc4a4","lacio","castano_oscuro","tupe","completa","seria","alargada"), # Muric
    1129: _r("#f6d7c3","lacio","rubio","ondulado",None,"seria","alargada"), # Hjulmand
    1201: _r("#7a4524","muy_rizado","negro","afro",None,"seria","oval"), # Richards
    3397: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Skóraś
    1196: _r("#7a4524","rizado","negro","degradado","incipiente","sonrisa","oval"), # Tillman
    1058: _r("#efc4a4","lacio","negro","tupe","completa","seria","alargada"), # Šutalo
    611: _r("#93572e","rizado","negro","degradado",None,"seria","oval"), # Andrey Santos
    3797: _r("#452313","rizado","negro","degradado",None,"sonrisa","oval"), # M. Sarr
    3803: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Diarra
    435: _r("#d4996f","lacio","negro","corto","incipiente","seria","alargada"), # Fernandez-Pardo
    997: _r("#e3ac86","lacio","negro","flequillo",None,"sonrisa","oval"), # Lee Jae-sung
    3422: _r("#d4996f","lacio","negro","corto","completa","seria","alargada"), # Rui Silva
    2021: _r("#d4996f","lacio","negro","tupe","completa","seria","alargada"), # Ghoddos
    1211: _r("#d4996f","lacio","negro","corto","completa","seria","oval"), # El Shenawy
    287: _r("#f6d7c3","lacio","rubio","corto","incipiente","sonrisa","alargada"), # A. Schlager
    2416: _r("#efc4a4","lacio","castano_oscuro","raya",None,"seria","alargada"), # Rashica
    1618: _r("#452313","rizado","negro","rastas","incipiente","seria","alargada"), # Ati-Zigi
    166: _r("#93572e","lacio","negro","corto","completa","sonrisa","oval"), # Al-Owais
    2889: _r("#d4996f","lacio","negro","corto","completa","seria","alargada"), # L. Chávez
    4065: _r("#efc4a4","lacio","castano_claro","largo_atado",None,"seria","alargada"), # Svanberg
    3408: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Szymański
    2779: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Haidara
    1138: _r("#f6d7c3","lacio","rubio","rapado",None,"seria","alargada"), # R. Kristensen
    1059: _r("#efc4a4","lacio","castano_claro","raya","completa","seria","alargada"), # Pongračić
    1553: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Mepham
    1192: _r("#c68458","rizado","rubio","rulos",None,"seria","alargada"), # Robinson
    3993: _r("#93572e","rizado","negro","rapado","completa","seria","oval"), # Foster
    1068: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Kotarski
    3163: _r("#efc4a4","lacio","castano_claro","raya",None,"seria","alargada"), # Thorstvedt
    422: _r("#efc4a4","rizado","castano_oscuro","rulos",None,"seria","alargada"), # De Cuyper
    808: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Johnston
    2834: _r("#d4996f","lacio","negro","degradado",None,"seria","alargada"), # El Khannouss
    420: _r("#efc4a4","lacio","castano_oscuro","tupe","completa","seria","alargada"), # Debast
    1997: _r("#d4996f","rizado","negro","rulos",None,"seria","alargada"), # Iqbal
    603: _r("#7a4524","rizado","negro","degradado",None,"seria","oval"), # Estêvão
    605: _r("#7a4524","rizado","negro","degradado","incipiente","seria","oval"), # Rayan
    3363: _r("#d4996f","lacio","negro","corto",None,"sonrisa","oval"), # D. Gómez
    59: _r("#d4996f","rizado","negro","rulos",None,"seria","alargada"), # N. Brown
    1334: _r("#efc4a4","lacio","castano_oscuro","tupe",None,"seria","alargada"), # Gyömbér
    1167: _r("#e3ac86","lacio","negro","corto","completa","seria","oval"), # Galíndez
    1037: _r("#452313","rizado","negro","trenzas","completa","sonrisa","oval"), # Waston
    2419: _r("#efc4a4","lacio","negro","tupe","completa","seria","alargada"), # Muriqi
    3430: _r("#e3ac86","lacio","castano_oscuro","tupe","completa","seria","alargada"), # R. Horta
    43: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Manaj
    1309: _r("#d4996f","rizado","negro","rulos","incipiente","seria","oval"), # Adams
    3824: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","sonrisa","alargada"), # Lukić
    4379: _r("#e3ac86","lacio","negro","tupe","incipiente","seria","alargada"), # Çakır
    3165: _r("#efc4a4","lacio","castano_claro","calvo","incipiente","seria","alargada"), # Aursnes
    1545: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # C. Roberts
    161: _r("#93572e","lacio","negro","rapado",None,"seria","alargada"), # Kanno
    379: _r("#7a4524","muy_rizado","negro","afro","completa","sonrisa","oval"), # Choudhury
    300: _r("#efc4a4","lacio","castano_claro","tupe",None,"seria","alargada"), # Wöber
    3253: _r("#efc4a4","lacio","castano_oscuro","tupe",None,"seria","alargada"), # Til
    1135: _r("#f6d7c3","lacio","#c9c9c9","corto","incipiente","seria","alargada"), # Nelsson
    563: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Katić
    3527: _r("#efc4a4","rizado","castano_claro","afro",None,"sonrisa","alargada"), # Král
    36: _r("#efc4a4","lacio","castano_oscuro","raya",None,"seria","alargada"), # Kumbulla
    3357: _r("#d4996f","rizado","castano_oscuro","rulos","completa","seria","oval"), # Alderete
    3125: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Uzoho
    2256: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Vicario
    282: _r("#efc4a4","lacio","castano_claro","raya","completa","seria","alargada"), # Metcalfe
    3557: _r("#5e331a","rizado","negro","rapado",None,"seria","oval"), # Firpo
    3162: _r("#efc4a4","lacio","castano_claro","raya",None,"seria","alargada"), # Pedersen
    1171: _r("#5e331a","muy_rizado","negro","rulos",None,"seria","oval"), # Preciado
    1011: _r("#e3ac86","lacio","negro","flequillo",None,"seria","oval"), # Oh Hyeon-gyu
    308: _r("#f6d7c3","lacio","rubio","ondulado",None,"seria","alargada"), # Wimmer
    2294: _r("#e3ac86","lacio","negro","tupe",None,"seria","oval"), # Y. Suzuki
    219: _r("#e3ac86","lacio","negro","tupe","completa","seria","alargada"), # J. M. López
    3458: _r("#d4996f","lacio","negro","corto","completa","seria","oval"), # Khoukhi
    3456: _r("#7a4524","rizado","negro","degradado","incipiente","seria","oval"), # Pedro Miguel
    560: _r("#efc4a4","lacio","negro","tupe","incipiente","sonrisa","alargada"), # Tabaković
    1002: _r("#e3ac86","lacio","negro","flequillo",None,"seria","oval"), # Jo Hyeon-woo
    1895: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Szalai
    1693: _r("#efc4a4","lacio","negro","corto","incipiente","seria","alargada"), # Pavlidis
    1030: _r("#452313","rizado","negro","degradado","incipiente","sonrisa","oval"), # Sangaré
    1560: _r("#efc4a4","lacio","castano","ondulado",None,"seria","alargada"), # Brooks
    272: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Hrustic
    1016: _r("#452313","rizado","negro","rapado","completa","seria","oval"), # Konan
    2034: _r("#efc4a4","rizado","castano_oscuro","rulos","incipiente","sonrisa","oval"), # Parrott
    1681: _r("#efc4a4","lacio","castano_oscuro","largo_atado",None,"seria","alargada"), # Tzolis
    1206: _r("#452313","rizado","negro","rulos",None,"seria","oval"), # Musah
    3150: _r("#f6d7c3","lacio","castano_claro","raya",None,"seria","alargada"), # Møller Wolfe
    432: _r("#5e331a","rizado","negro","rapado",None,"seria","alargada"), # Ngoy
    1026: _r("#452313","rizado","negro","rapado","incipiente","seria","oval"), # Diomande
    3799: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Diouf
    1212: _r("#d4996f","lacio","negro","corto","completa","seria","oval"), # Rabia
    1300: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Hanley
    2082: _r("#f6d7c3","lacio","rubio","rapado",None,"seria","alargada"), # Hermannsson
    3401: _r("#efc4a4","lacio","castano_claro","corto",None,"sonrisa","alargada"), # Kędziora
    290: _r("#7a4524","rizado","negro","degradado","incipiente","seria","oval"), # Mwene
    3303: _r("#c68458","rizado","negro","rulos",None,"seria","oval"), # Escobar
    1756: _r("#5e331a","rizado","negro","rulos","incipiente","seria","oval"), # Diawara
    4517: _r("#d4996f","lacio","negro","corto","incipiente","seria","alargada"), # Herrera
    915: _r("#7a4524","rizado","negro","rapado",None,"seria","oval"), # Lucumí
    1621: _r("#452313","rizado","negro","trenzas","incipiente","seria","alargada"), # Mensah
    41: _r("#efc4a4","lacio","negro","corto",None,"seria","alargada"), # Bajrami
    156: _r("#93572e","rizado","negro","corto","completa","seria","oval"), # Al-Amri
    4052: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Gudmundsson
    1573: _r("#452313","rizado","negro","rulos",None,"seria","oval"), # Barrow
    2261: _r("#efc4a4","lacio","castano","raya",None,"seria","alargada"), # Fagioli
    1216: _r("#c68458","rizado","castano_oscuro","rulos",None,"seria","oval"), # Ashour
    3424: _r("#e3ac86","rizado","negro","rulos","completa","sonrisa","oval"), # Araújo
    1078: _r("#efc4a4","lacio","castano_claro","corto","completa","seria","alargada"), # Pašalić
    1190: _r("#7a4524","rizado","negro","degradado",None,"seria","oval"), # Freeman
    800: _r("#452313","rizado","negro","trenzas","incipiente","seria","oval"), # Koné
    1626: _r("#452313","rizado","negro","degradado","incipiente","seria","oval"), # Nuamah
    185: _r("#d4996f","rizado","negro","ondulado","incipiente","seria","alargada"), # Chaïbi
    1673: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Vlachodimos
    4394: _r("#e3ac86","lacio","negro","corto","completa","seria","alargada"), # Bardakcı
    1315: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # McLean
    2668: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Bardhi
    1107: _r("#93572e","rizado","negro","rulos",None,"sonrisa","oval"), # Juninho Bacuna
    3471: _r("#7a4524","rizado","negro","degradado",None,"seria","alargada"), # Madibo
    792: _r("#452313","rizado","negro","rapado","incipiente","seria","oval"), # Bassogog
    3605: _r("#efc4a4","lacio","castano_oscuro","degradado",None,"seria","alargada"), # Man
    270: _r("#e3ac86","rizado","negro","rulos",None,"seria","oval"), # Arzani
    2829: _r("#d4996f","lacio","negro","corto",None,"seria","alargada"), # El Yamiq
    805: _r("#7a4524","rizado","rubio","degradado","completa","seria","oval"), # Cornelius
    1179: _r("#452313","rizado","negro","rulos","candado","seria","oval"), # F. Torres
    425: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Raskin
    793: _r("#d4996f","rizado","rubio","rulos","incipiente","seria","oval"), # St. Clair
    1180: _r("#452313","rizado","negro","trenzas",None,"seria","alargada"), # Porozo
    301: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Prass
    3533: _r("#efc4a4","lacio","castano_claro","corto","incipiente","seria","alargada"), # Zima
    1022: _r("#452313","rizado","negro","rastas","incipiente","seria","alargada"), # Wahi
    1066: _r("#efc4a4","lacio","castano_oscuro","raya","incipiente","seria","alargada"), # Matanović
    1013: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Fofana
    1172: _r("#c68458","rizado","rubio","rulos",None,"seria","oval"), # Angulo
    813: _r("#452313","rizado","negro","rapado","incipiente","seria","oval"), # Oluwaseyi
    3801: _r("#452313","rizado","negro","degradado",None,"seria","oval"), # L. Camara
    920: _r("#c68458","ondulado","negro","ondulado","incipiente","seria","alargada"), # R. Ríos
    1028: _r("#7a4524","rizado","negro","degradado","candado","seria","alargada"), # Guéla Doué
    2825: _r("#d4996f","lacio","negro","corto","incipiente","seria","alargada"), # Yassine
    1101: _r("#c68458","lacio","negro","rapado","incipiente","sonrisa","oval"), # Room
    1904: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Dibusz
    4316: _r("#d4996f","lacio","negro","corto","completa","seria","alargada"), # Maâloul
    3461: _r("#7a4524","rizado","negro","rapado","incipiente","sonrisa","oval"), # Hatem
    3376: _r("#d4996f","lacio","negro","ondulado",None,"seria","alargada"), # Lapadula
    799: _r("#efc4a4","rizado","castano_oscuro","rulos","completa","seria","alargada"), # Osorio
    3362: _r("#e3ac86","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Cubas
    4055: _r("#efc4a4","lacio","castano_claro","corto","completa","seria","alargada"), # Karlström
    807: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Laryea
    281: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # McGree
    1191: _r("#7a4524","rizado","negro","degradado","incipiente","seria","oval"), # Trusty
    2242: _r("#e3ac86","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Solomon
    1203: _r("#93572e","rizado","negro","trenzas","candado","seria","alargada"), # M. Robinson
    732: _r("#452313","rizado","negro","rapado",None,"seria","alargada"), # Duarte
    49: _r("#452313","rizado","negro","degradado",None,"seria","oval"), # Baku
    2887: _r("#d4996f","lacio","negro","degradado","incipiente","sonrisa","oval"), # J. Araujo
    3345: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Gill
    1134: _r("#efc4a4","lacio","castano","corto",None,"seria","alargada"), # M. Hermansen
    676: _r("#452313","rizado","negro","rastas",None,"seria","oval"), # Kaboré
    1338: _r("#efc4a4","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Suslov
    1511: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Truffert
    3154: _r("#f6d7c3","lacio","castano_claro","largo_atado",None,"seria","alargada"), # Aasgaard
    616: _r("#452313","rizado","negro","degradado",None,"seria","oval"), # L. Henrique
    2838: _r("#d4996f","rizado","negro","rulos","incipiente","seria","oval"), # El Ouahdi
    433: _r("#f6d7c3","rizado","rubio","rulos",None,"seria","alargada"), # Seys
    568: _r("#efc4a4","lacio","castano_oscuro","tupe",None,"seria","alargada"), # Tahirović
    569: _r("#efc4a4","rizado","castano_oscuro","ondulado",None,"seria","alargada"), # Mahmić
    1613: _r("#452313","rizado","negro","rastas","incipiente","seria","alargada"), # Yirenkyi
    1941: _r("#d4996f","lacio","negro","raya","incipiente","seria","alargada"), # Walsh
    3606: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Chipciu
    1311: _r("#efc4a4","lacio","castano_oscuro","raya",None,"seria","alargada"), # J. Souttar
    3367: _r("#d4996f","rizado","negro","rastas","completa","seria","alargada"), # Gallese
    1319: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Shankland
    1340: _r("#efc4a4","lacio","castano_oscuro","tupe",None,"sonrisa","alargada"), # Haraslín
    804: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Crépeau
    4091: _r("#efc4a4","lacio","castano_oscuro","ondulado",None,"sonrisa","alargada"), # Itten
    317: _r("#e3ac86","lacio","negro","tupe","incipiente","sonrisa","alargada"), # Emreli
    1303: _r("#efc4a4","lacio","castano_oscuro","ondulado","incipiente","seria","alargada"), # Ralston
    4330: _r("#d4996f","lacio","negro","rapado","completa","seria","alargada"), # Laïdouni
    175: _r("#7a4524","rizado","negro","degradado","completa","seria","alargada"), # Al-Buraikan
    681: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # L. Traoré
    1173: _r("#d4996f","lacio","negro","tupe",None,"seria","alargada"), # Franco
    812: _r("#efc4a4","rizado","rubio","rulos",None,"sonrisa","alargada"), # Shaffelburg
    3389: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Bułka
    3146: _r("#452313","rizado","negro","rapado",None,"seria","alargada"), # Tella
    1033: _r("#452313","rizado","negro","rapado","incipiente","seria","oval"), # Bonny
    559: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Bajraktarević
    278: _r("#efc4a4","rizado","castano_oscuro","ondulado",None,"seria","alargada"), # Circati
    3429: _r("#e3ac86","rizado","negro","rulos",None,"seria","alargada"), # M. Fernandes
    909: _r("#d4996f","lacio","negro","degradado","incipiente","seria","alargada"), # Castaño
    1316: _r("#efc4a4","lacio","castano_claro","flequillo","incipiente","seria","alargada"), # Fletcher
    1104: _r("#7a4524","rizado","negro","degradado",None,"sonrisa","oval"), # Brenet
    1683: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Bakasetas
    1458: _r("#efc4a4","lacio","castano_claro","raya",None,"seria","alargada"), # Lod
    3465: _r("#d4996f","rizado","negro","rulos","incipiente","seria","alargada"), # Alaaeldin
    4067: _r("#452313","rizado","negro","rapado","incipiente","seria","oval"), # Sema
    3347: _r("#d4996f","lacio","negro","corto",None,"seria","oval"), # J. Alonso
    1388: _r("#efc4a4","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Mets
    1226: _r("#d4996f","rizado","negro","rulos","incipiente","seria","alargada"), # Hany
    733: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Monteiro
    1308: _r("#efc4a4","lacio","castano_claro","rapado","incipiente","seria","alargada"), # Dykes
    3997: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Modiba
    3594: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Cicâldău
    2409: _r("#efc4a4","lacio","castano_oscuro","rapado","completa","seria","alargada"), # Zhegrova
    169: _r("#7a4524","rizado","negro","degradado",None,"sonrisa","oval"), # Al-Dawsari
    1341: _r("#efc4a4","lacio","castano_claro","tupe",None,"seria","alargada"), # Boženík
    1606: _r("#efc4a4","lacio","castano_oscuro","ondulado","completa","seria","alargada"), # Davitashvili
    4457: _r("#e3ac86","lacio","negro","tupe","incipiente","seria","alargada"), # Cáceres
    3160: _r("#efc4a4","lacio","rubio","raya",None,"seria","alargada"), # Heggem
    4059: _r("#efc4a4","lacio","castano_claro","ondulado",None,"sonrisa","alargada"), # Bernhardsson
    4320: _r("#d4996f","lacio","negro","corto","completa","seria","alargada"), # Ben Slimane
    2899: _r("#e3ac86","lacio","negro","rapado",None,"seria","alargada"), # Fidalgo
    4049: _r("#f6d7c3","lacio","pelirrojo","corto","completa","sonrisa","alargada"), # Johansson
    26: _r("#efc4a4","lacio","castano_claro","tupe",None,"seria","alargada"), # Mitaj
    1973: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # Hall
    2229: _r("#efc4a4","lacio","negro","corto",None,"seria","alargada"), # Gloukh
    438: _r("#efc4a4","ondulado","castano_claro","largo_atado",None,"seria","alargada"), # Godts
    797: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Sigur
    1510: _r("#452313","rizado","negro","trenzas",None,"seria","alargada"), # Jacquet
    3792: _r("#452313","rizado","negro","rulos",None,"seria","oval"), # Ndiaye
    3193: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Boxall
    1255: _r("#93572e","rizado","negro","degradado","completa","seria","oval"), # Eisa
    647: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Despodov
    2004: _r("#d4996f","lacio","negro","corto","completa","seria","alargada"), # Khalilzadeh
    1597: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Dvali
    2679: _r("#efc4a4","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Nikolov
    4638: _r("#452313","rizado","negro","cresta",None,"sonrisa","oval"), # Nakamba
    194: _r("#d4996f","lacio","negro","tupe","incipiente","seria","alargada"), # Ounas
    2680: _r("#efc4a4","lacio","castano_oscuro","rapado",None,"seria","oval"), # Kostadinov
    4539: _r("#e3ac86","lacio","negro","raya",None,"seria","oval"), # Quang Hải
    902: _r("#93572e","rizado","negro","degradado",None,"seria","oval"), # Edwards
    1113: _r("#c68458","rizado","negro","rulos",None,"seria","oval"), # Obispo
    172: _r("#7a4524","rizado","negro","rapado",None,"sonrisa","oval"), # Al-Khaibari
    4608: _r("#452313","rizado","negro","degradado",None,"sonrisa","oval"), # Sakala
    2014: _r("#d4996f","lacio","negro","tupe",None,"sonrisa","alargada"), # Niazmand
    2625: _r("#93572e","rizado","negro","rulos",None,"seria","alargada"), # Barreiro
    1178: _r("#452313","rizado","negro","trenzas","incipiente","seria","oval"), # Ramírez
    4465: _r("#efc4a4","rizado","castano_oscuro","rulos",None,"seria","alargada"), # Viñas
    3139: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Sanusi
    2259: _r("#efc4a4","rizado","castano_claro","rulos",None,"seria","alargada"), # Ruggeri
    1549: _r("#7a4524","rizado","negro","trenzas","incipiente","seria","oval"), # Thomas
    4318: _r("#d4996f","rizado","negro","degradado",None,"seria","alargada"), # Gharbi
    1223: _r("#d4996f","rizado","negro","rulos","completa","seria","oval"), # Abdelmonem
    4056: _r("#f6d7c3","lacio","rubio","ondulado",None,"seria","alargada"), # Larsson
    4399: _r("#efc4a4","lacio","castano_claro","tupe",None,"seria","alargada"), # Kılıçsoy
    3192: _r("#efc4a4","ondulado","castano_claro","ondulado",None,"sonrisa","alargada"), # Bindon
    794: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # Fougerolles
    1034: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # B. Touré
    276: _r("#efc4a4","lacio","castano_oscuro","tupe","completa","seria","alargada"), # Beach
    2835: _r("#d4996f","rizado","negro","rulos","incipiente","seria","alargada"), # El Mourabet
    1525: _r("#452313","rizado","negro","rapado","incipiente","seria","alargada"), # Biyogo Poko
    2144: _r("#f6d7c3","lacio","rubio","tupe",None,"seria","alargada"), # Edmundsson
    663: _r("#452313","rizado","negro","rastas","completa","seria","alargada"), # Yago
    3410: _r("#efc4a4","lacio","castano_oscuro","corto",None,"sonrisa","oval"), # Wszołek
    2606: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Černych
    934: _r("#452313","rizado","negro","rulos",None,"seria","oval"), # Ben Nabouhane
    1564: _r("#452313","rizado","negro","rapado","completa","seria","oval"), # Colley
    2676: _r("#efc4a4","lacio","castano_oscuro","corto",None,"sonrisa","alargada"), # Zajkov
    1620: _r("#c68458","rizado","negro","degradado",None,"seria","alargada"), # Djiku
    1225: _r("#d4996f","rizado","negro","rulos",None,"seria","alargada"), # Hafez
    4061: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # E. Smith
    1120: _r("#c68458","rizado","negro","degradado","incipiente","sonrisa","oval"), # Gorré
    1831: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Arcus
    851: _r("#d4996f","lacio","negro","tupe",None,"seria","alargada"), # Suazo
    1842: _r("#5e331a","muy_rizado","negro","rastas","completa","seria","alargada"), # Duverne
    748: _r("#7a4524","rizado","negro","rapado",None,"seria","oval"), # J. Cabral
    3601: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Burcă
    3618: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Sobolev
    1006: _r("#e3ac86","lacio","negro","raya",None,"seria","oval"), # Kim Moon-hwan
    3489: _r("#452313","rizado","negro","rapado","completa","seria","oval"), # Batubinsika
    1604: _r("#efc4a4","ondulado","castano_oscuro","ondulado","completa","seria","alargada"), # Tsitaishvili
    3202: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","sonrisa","alargada"), # Woud
    795: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Miller
    1189: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Freese
    2078: _r("#f6d7c3","lacio","rubio","largo_atado",None,"seria","alargada"), # Guðjohnsen
    994: _r("#e3ac86","lacio","negro","raya",None,"seria","oval"), # Seol Young-woo
    4395: _r("#efc4a4","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Yüksek
    53: _r("#c68458","rizado","negro","degradado","candado","seria","oval",lentes=True), # Schade
    3149: _r("#f6d7c3","lacio","rubio","corto",None,"sonrisa","alargada"), # Langås
    1501: _r("#5e331a","rizado","negro","degradado",None,"seria","alargada"), # Diouf
    2895: _r("#e3ac86","lacio","castano_oscuro","ondulado",None,"sonrisa","alargada"), # Reyes
    809: _r("#7a4524","rizado","negro","rulos","incipiente","seria","alargada"), # Ahmed
    730: _r("#7a4524","lacio","pelirrojo","corto","completa","seria","oval"), # Stopira
    1170: _r("#c68458","lacio","negro","tupe",None,"seria","alargada"), # C. Ramírez
    3301: _r("#7a4524","lacio","negro","calvo","completa","seria","oval"), # Mejía
    3203: _r("#c68458","rizado","rubio","rapado","completa","seria","oval"), # Tuiloma
    1679: _r("#efc4a4","lacio","negro","corto","incipiente","seria","alargada"), # Mantalos
    731: _r("#7a4524","rizado","negro","trenzas","completa","seria","alargada"), # Moreira
    1230: _r("#e3ac86","rizado","castano_oscuro","rulos","incipiente","seria","alargada"), # Zizo
    3369: _r("#d4996f","lacio","negro","degradado","completa","seria","alargada"), # Abram
    2414: _r("#efc4a4","rizado","castano_claro","ondulado",None,"seria","alargada"), # Vojvoda
    1591: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Kiteishvili
    1848: _r("#452313","rizado","negro","rulos",None,"seria","oval"), # Etienne
    4403: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Matviyenko
    44: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Asani
    1686: _r("#efc4a4","lacio","castano_oscuro","degradado",None,"sonrisa","alargada"), # Retsos
    2883: _r("#d4996f","lacio","negro","largo_atado",None,"sonrisa","alargada"), # Acevedo
    3487: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Mavididi
    1187: _r("#452313","rizado","negro","rulos",None,"seria","oval"), # Caicedo
    2279: _r("#5e331a","rizado","negro","rapado",None,"seria","alargada"), # Pinnock
    3316: _r("#7a4524","rizado","negro","degradado","incipiente","seria","oval"), # Blackman
    811: _r("#d4996f","lacio","negro","tupe","incipiente","seria","alargada"), # Choinière
    1330: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Strelec
    3621: _r("#f6d7c3","lacio","castano_claro","corto",None,"seria","alargada"), # Diveyev
    3134: _r("#452313","rizado","negro","rapado","incipiente","seria","oval"), # A. Adams
    3469: _r("#d4996f","lacio","negro","corto",None,"seria","alargada"), # H. Ahmed
    4321: _r("#d4996f","rizado","negro","rulos","incipiente","seria","alargada"), # Achouri
    2035: _r("#c68458","rizado","negro","degradado",None,"seria","alargada"), # Idah
    3481: _r("#452313","rizado","negro","rapado","completa","seria","alargada"), # Kalulu
    1608: _r("#452313","rizado","negro","trenzas","completa","seria","alargada"), # Opoku
    1996: _r("#d4996f","lacio","negro","tupe","incipiente","seria","alargada"), # H. Ali
    3539: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Douděra
    1219: _r("#d4996f","rizado","negro","rulos","completa","seria","oval"), # Adel
    1224: _r("#d4996f","rizado","negro","rulos",None,"sonrisa","alargada"), # Abdelmaguid
    3207: _r("#f6d7c3","lacio","castano_claro","corto",None,"seria","alargada"), # Old
    2244: _r("#e3ac86","lacio","negro","corto","completa","seria","alargada"), # Abada
    1003: _r("#e3ac86","lacio","negro","flequillo",None,"seria","oval"), # Lee Han-beom
    2000: _r("#d4996f","rizado","negro","rulos","incipiente","seria","alargada"), # Amyn
    1942: _r("#c68458","lacio","negro","raya",None,"seria","oval"), # Ferdinan
    3364: _r("#e3ac86","lacio","negro","corto",None,"seria","oval"), # R. Sosa
    283: _r("#e3ac86","lacio","negro","raya",None,"seria","alargada"), # Volpato
    556: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Bašić
    3789: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Mendy
    1600: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Gocholeishvili
    1950: _r("#efc4a4","lacio","negro","degradado","candado","seria","alargada"), # Hubner
    1185: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Castillo
    1508: _r("#7a4524","rizado","negro","degradado",None,"seria","oval"), # Restes
    2893: _r("#efc4a4","lacio","castano_oscuro","raya",None,"seria","alargada"), # A. González
    267: _r("#c68458","rizado","negro","rulos",None,"seria","alargada"), # Herrington
    1019: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Oulaï
    2075: _r("#c68458","rizado","negro","degradado","incipiente","seria","oval"), # Pálsson
    326: _r("#d4996f","lacio","negro","degradado","completa","seria","alargada"), # Mahmudov
    3006: _r("#5e331a","rizado","negro","degradado",None,"seria","alargada"), # Mexer
    2665: _r("#efc4a4","lacio","castano_claro","corto","incipiente","seria","alargada"), # Velkovski
    3903: _r("#d4996f","lacio","negro","tupe","completa","seria","alargada"), # Khribin
    1322: _r("#efc4a4","lacio","castano_claro","rapado",None,"seria","alargada"), # Hatka
    3820: _r("#efc4a4","lacio","castano_oscuro","tupe","incipiente","seria","alargada"), # Ristić
    3494: _r("#452313","rizado","rubio","degradado","incipiente","seria","alargada"), # Tshibola
    96: _r("#452313","rizado","negro","degradado","incipiente","seria","oval"), # Dala
    3127: _r("#452313","rizado","negro","rapado",None,"seria","alargada"), # Ajayi
    1538: _r("#d4996f","lacio","negro","corto","incipiente","seria","alargada"), # Bouanga
    2830: _r("#c68458","lacio","negro","rapado","incipiente","seria","alargada"), # Saïdane
    2330: _r("#d4996f","lacio","negro","corto","completa","seria","alargada"), # Al-Mardi
    2624: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Thill
    2047: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Peacock-Farrell
    3600: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Bălușă
    1318: _r("#efc4a4","lacio","rubio","corto","incipiente","seria","alargada"), # Hirst
    2627: _r("#e3ac86","rizado","castano_oscuro","ondulado","completa","sonrisa","alargada"), # Sinani
    2061: _r("#c68458","rizado","negro","degradado",None,"seria","alargada"), # Lewis
    3381: _r("#7a4524","rizado","negro","rapado",None,"seria","oval"), # M. López
    3318: _r("#d4996f","rizado","castano_oscuro","rulos",None,"seria","alargada"), # Carrasquilla
    3455: _r("#d4996f","rizado","negro","rulos","completa","seria","alargada"), # Abunada
    3147: _r("#efc4a4","lacio","castano_claro","corto","incipiente","seria","alargada"), # Selvik
    1015: _r("#452313","rizado","castano_oscuro","rapado","candado","seria","oval"), # Agbadou
    3457: _r("#d4996f","rizado","negro","rulos","completa","seria","alargada"), # Gaber
    4467: _r("#e3ac86","lacio","negro","corto",None,"sonrisa","oval"), # Nematov
    173: _r("#d4996f","rizado","negro","rulos","candado","seria","alargada"), # Al-Johani
    599: _r("#c68458","rizado","negro","degradado",None,"sonrisa","oval"), # Vanderson
    2820: _r("#d4996f","lacio","negro","tupe","incipiente","seria","alargada"), # Belammari
    1369: _r("#efc4a4","lacio","castano_oscuro","corto",None,"sonrisa","alargada"), # Fresneda
    2249: _r("#5e331a","rizado","negro","rulos",None,"sonrisa","oval"), # Kayode
    1139: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # Froholdt
    1619: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Adjetey
    2312: _r("#93572e","rizado","negro","rapado",None,"seria","oval"), # Nasib
    33: _r("#e3ac86","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Uzuni
    93: _r("#5e331a","rizado","negro","degradado","incipiente","seria","oval"), # Mata
    39: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Muçi
    58: _r("#93572e","rizado","negro","degradado","completa","seria","oval"), # Vagnoman
    274: _r("#7a4524","rizado","castano_oscuro","rulos","candado","seria","alargada"), # Yengi
    566: _r("#efc4a4","ondulado","castano_oscuro","ondulado",None,"seria","alargada"), # Malić
    529: _r("#d4996f","lacio","negro","corto","incipiente","seria","alargada"), # Lampe
    1183: _r("#c68458","lacio","negro","corto","completa","seria","oval"), # Vite
    1228: _r("#d4996f","rizado","negro","rulos","completa","seria","oval"), # Attia
    1174: _r("#c68458","lacio","negro","tupe",None,"seria","oval"), # Alcívar
    1312: _r("#efc4a4","lacio","castano_oscuro","raya","incipiente","seria","alargada"), # Hyam
    1344: _r("#efc4a4","lacio","castano_claro","calvo","candado","seria","oval"), # Drkušić
    1465: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Väisänen
    1616: _r("#5e331a","rizado","negro","rastas","incipiente","seria","alargada"), # Thomas-Asante
    1624: _r("#452313","rizado","negro","rulos","completa","seria","oval"), # Sibo
    1956: _r("#d4996f","lacio","negro","raya",None,"seria","oval"), # Vikri
    1595: _r("#efc4a4","ondulado","castano_claro","ondulado","completa","seria","alargada"), # Lobzhanidze
    1623: _r("#452313","rizado","negro","rapado","incipiente","seria","oval"), # Boakye
    2267: _r("#5e331a","rizado","negro","degradado",None,"seria","oval"), # Blake
    2038: _r("#f6d7c3","lacio","pelirrojo","corto",None,"seria","alargada"), # O'Brien
    2969: _r("#e3ac86","lacio","negro","rapado","incipiente","sonrisa","oval"), # Krstović
    3307: _r("#d4996f","lacio","#c9c9c9","corto","completa","seria","alargada"), # C. Martínez
    3309: _r("#452313","rizado","negro","rapado","incipiente","seria","oval"), # Waterman
    3359: _r("#d4996f","lacio","negro","corto",None,"seria","oval"), # Riveros
    4057: _r("#f6d7c3","ondulado","castano_oscuro","ondulado",None,"seria","alargada"), # Swedberg
    4086: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Omeragić
    4140: _r("#efc4a4","rizado","castano_oscuro","ondulado",None,"seria","alargada"), # Mickelson
    4413: _r("#efc4a4","lacio","castano_claro","rapado",None,"seria","oval"), # Bondar
    4421: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Vanat
    4484: _r("#d4996f","lacio","negro","corto",None,"seria","oval"), # Hamrobekov
    225: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Hovhannisyan
    280: _r("#e3ac86","rizado","negro","ondulado","completa","seria","alargada"), # Italiano
    429: _r("#7a4524","rizado","negro","rulos",None,"seria","alargada"), # Fofana
    670: _r("#452313","rizado","negro","rulos",None,"seria","oval"), # Tapsoba
    557: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Gojak
    996: _r("#e3ac86","lacio","negro","raya",None,"seria","oval"), # Lee Dong-gyeong
    1010: _r("#e3ac86","lacio","rubio","corto",None,"seria","oval"), # Song Min-kyu
    1141: _r("#f6d7c3","ondulado","rubio","ondulado",None,"seria","alargada"), # Bidstrup
    1434: _r("#d4996f","lacio","negro","corto",None,"sonrisa","oval"), # Sato
    1111: _r("#452313","rizado","negro","trenzas",None,"seria","alargada"), # Martha
    1466: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # Ivanov
    1470: _r("#f6d7c3","ondulado","rubio","ondulado",None,"seria","alargada"), # Valakari
    1307: _r("#f6d7c3","lacio","castano_claro","corto","incipiente","sonrisa","alargada"), # Conway
    1547: _r("#f6d7c3","lacio","rubio","corto","incipiente","seria","alargada"), # J. James
    1844: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Jean Jacques
    1940: _r("#e3ac86","lacio","negro","corto","incipiente","seria","alargada"), # Verdonk
    1556: _r("#c68458","rizado","negro","corto",None,"seria","oval"), # Dasilva
    2258: _r("#efc4a4","lacio","negro","raya","incipiente","seria","alargada"), # Coppola
    2811: _r("#efc4a4","lacio","castano_oscuro","corto","incipiente","seria","alargada"), # Teuma
    3141: _r("#452313","rizado","negro","rapado","completa","seria","oval"), # Yusuf
    3238: _r("#d4996f","rizado","castano_oscuro","degradado","incipiente","seria","alargada"), # Hartman
    3348: _r("#d4996f","lacio","negro","corto",None,"seria","oval"), # Maidana
    3256: _r("#efc4a4","rizado","castano_oscuro","rulos",None,"seria","alargada"), # van Bommel
    3312: _r("#7a4524","rizado","negro","degradado",None,"seria","oval"), # Mosquera
    3406: _r("#efc4a4","lacio","castano_oscuro","corto",None,"seria","alargada"), # Slisz
    3891: _r("#e3ac86","lacio","negro","flequillo",None,"sonrisa","oval"), # Nakamura
    4470: _r("#e3ac86","rizado","castano_oscuro","ondulado","completa","seria","alargada"), # Nasrullaev
    4472: _r("#d4996f","lacio","negro","raya",None,"seria","alargada"), # Ganiev
    4482: _r("#e3ac86","lacio","negro","corto",None,"seria","oval"), # Karimov
    189: _r("#d4996f","lacio","negro","tupe","incipiente","seria","alargada"), # Belaïd
    237: _r("#e3ac86","lacio","negro","corto","incipiente","seria","alargada"), # Bichakhchyan
    295: _r("#f6d7c3","lacio","rubio","tupe","incipiente","seria","alargada"), # Gründl
    674: _r("#452313","rizado","negro","degradado","incipiente","seria","oval"), # Djiga
    1005: _r("#e3ac86","lacio","negro","raya",None,"seria","oval"), # Lee Tae-seok
    1186: _r("#e3ac86","ondulado","castano_oscuro","ondulado","completa","seria","alargada"), # Campana
    1473: _r("#f6d7c3","lacio","rubio","corto","incipiente","seria","alargada"), # Källman
    1685: _r("#e3ac86","lacio","negro","corto","incipiente","seria","alargada"), # Koulierakis
    1582: _r("#452313","rizado","negro","degradado",None,"seria","oval"), # E. Colley
    1602: _r("#efc4a4","rizado","castano_oscuro","rulos","incipiente","seria","alargada"), # Mekvabishvili
    1776: _r("#d4996f","lacio","negro","corto","completa","sonrisa","oval"), # Akapo
    1854: _r("#c68458","lacio","negro","corto","candado","seria","oval"), # Acosta
    1984: _r("#d4996f","lacio","negro","tupe","completa","seria","alargada"), # Doski
    1998: _r("#d4996f","lacio","negro","corto","incipiente","seria","alargada"), # Bayesh
    3355: _r("#d4996f","lacio","negro","corto","incipiente","seria","oval"), # Caballero
    3528: _r("#efc4a4","lacio","negro","corto","incipiente","seria","alargada"), # Lingr
    3821: _r("#efc4a4","lacio","castano_claro","tupe","completa","seria","alargada"), # Terzić
    4256: _r("#452313","lacio","negro","rapado","completa","seria","oval"), # Denkey
    4105: _r("#452313","rizado","negro","rapado","completa","seria","alargada"), # Denswil
    4329: _r("#d4996f","lacio","negro","corto","completa","seria","alargada"), # Rafia
    4387: _r("#d4996f","lacio","negro","flequillo","incipiente","seria","alargada"), # Aydın
    4627: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Munetsi
    931: _r("#5e331a","rizado","negro","rapado","completa","seria","alargada"), # M'Changama
    781: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Kofane
    839: _r("#efc4a4","rizado","castano_oscuro","ondulado",None,"seria","alargada"), # Lichnovsky
    1114: _r("#7a4524","rizado","negro","degradado","completa","seria","oval"), # van Eijma
    1986: _r("#d4996f","lacio","negro","corto","incipiente","seria","alargada"), # Al-Ammari
    1948: _r("#efc4a4","lacio","castano_oscuro","corto","completa","sonrisa","alargada"), # Paes
    1555: _r("#efc4a4","lacio","castano_claro","corto","completa","seria","alargada"), # Norrington-Davies
    1741: _r("#452313","rizado","negro","rulos","candado","sonrisa","oval"), # S. Sow
    1938: _r("#e3ac86","lacio","negro","raya","incipiente","seria","oval"), # Baggott
    2054: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Saville
    2063: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Devenny
    2275: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # Nicholson
    2778: _r("#452313","rizado","negro","rulos",None,"sonrisa","oval"), # Sangaré
    3310: _r("#5e331a","rizado","negro","rulos","completa","seria","alargada"), # Fajardo
    3702: _r("#efc4a4","lacio","negro","corto","completa","seria","alargada"), # Vitaioli
    4511: _r("#c68458","lacio","negro","corto",None,"seria","oval"), # Farínez
    4542: _r("#e3ac86","lacio","negro","tupe",None,"seria","alargada"), # Tiến Linh
    4331: _r("#d4996f","lacio","negro","raya","completa","seria","alargada"), # Ben Romdhane
    4473: _r("#e3ac86","lacio","negro","corto",None,"seria","oval"), # Mozgovoy
    4300: _r("#452313","rizado","negro","rulos","incipiente","seria","alargada"), # García
    465: _r("#c68458","lacio","rubio","corto",None,"seria","oval"), # Verdon
    1045: _r("#c68458","lacio","negro","corto",None,"sonrisa","oval"), # Ugalde
    1313: _r("#efc4a4","lacio","castano_claro","corto","incipiente","sonrisa","alargada"), # McCrorie
    1607: _r("#452313","rizado","negro","trenzas","incipiente","seria","alargada"), # Asare
    1857: _r("#c68458","lacio","negro","degradado",None,"seria","oval"), # Palma
    1987: _r("#d4996f","lacio","negro","tupe",None,"sonrisa","alargada"), # Attwan
    1945: _r("#c68458","lacio","negro","tupe","candado","seria","oval"), # Oratmangoen
    2050: _r("#efc4a4","rizado","castano_oscuro","ondulado",None,"sonrisa","alargada"), # Hume
    2053: _r("#7a4524","rizado","negro","degradado",None,"seria","oval"), # Charles
    2027: _r("#f6d7c3","lacio","pelirrojo","tupe","completa","sonrisa","alargada"), # Scales
    2420: _r("#efc4a4","rizado","castano_oscuro","corto",None,"seria","alargada"), # Asllani
    2592: _r("#efc4a4","lacio","castano_claro","ondulado","incipiente","seria","alargada"), # Hasler
    2955: _r("#efc4a4","lacio","negro","largo_atado","completa","seria","alargada"), # Janković
    2786: _r("#452313","rizado","negro","rapado",None,"seria","oval"), # M. Fofana
    3195: _r("#c68458","lacio","negro","corto",None,"seria","oval"), # Ingham
    3365: _r("#d4996f","lacio","negro","corto",None,"seria","oval"), # Arce
    4406: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Ocheretko
    4527: _r("#d4996f","lacio","negro","corto",None,"seria","alargada"), # Savarino
    4513: _r("#d4996f","lacio","negro","corto",None,"seria","oval"), # Osorio
    4635: _r("#452313","rizado","negro","trenzas",None,"seria","alargada"), # Zemura
    4124: _r("#c68458","lacio","negro","corto",None,"seria","oval"), # Tehau
    469: _r("#452313","rizado","negro","tupe",None,"seria","oval"), # Dossou
    286: _r("#efc4a4","lacio","castano_oscuro","raya","completa","seria","alargada"), # Borrello
    668: _r("#452313","rizado","negro","rapado","completa","seria","oval"), # Touré
    530: _r("#efc4a4","lacio","castano_oscuro","corto","completa","seria","alargada"), # Haquin
    696: _r("#452313","rizado","negro","degradado",None,"seria","oval"), # Ndayishimiye
    1410: _r("#93572e","rizado","negro","rulos","completa","seria","alargada"), # Bayeh
    1754: _r("#452313","lacio","negro","rapado",None,"seria","alargada"), # Conte
    1943: _r("#efc4a4","lacio","castano_oscuro","raya","incipiente","seria","alargada"), # Haye
    2268: _r("#452313","rizado","negro","degradado",None,"seria","oval"), # Lowe
    2345: _r("#e3ac86","lacio","negro","corto",None,"seria","oval"), # Alip
    2138: _r("#efc4a4","lacio","castano_oscuro","tupe",None,"seria","alargada"), # Davidsen
    2495: _r("#f6d7c3","lacio","rubio","corto",None,"seria","alargada"), # Gutkovskis
    2631: _r("#efc4a4","lacio","castano_claro","corto",None,"seria","alargada"), # Mahmutović
    2787: _r("#452313","rizado","negro","rastas","incipiente","seria","alargada"), # Guindo
}
