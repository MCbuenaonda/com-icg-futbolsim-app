"""
Retratos a medida de DTs reales (2.ª tanda), tomados de su foto de Wikidata (solo se miran sus rasgos; la foto no se guarda).
`generar_avatares_tecnicos.AJUSTES_TECNICO` los incorpora sin pisar a los de la primera tanda.
"""
def _t(piel, pelo, peinado, barba, boca, forma, anteojos=False, entradas=False, textura="lacio", ojos="marron"):
    return {"piel": piel, "textura": textura, "pelo": pelo, "ojos": ojos, "peinado": peinado, "barba": barba, "boca": boca,
            "forma": forma, "anteojos": anteojos, "entradas": entradas}


AJUSTES_TECNICOS_2 = {
    7: _t("#e3ac86", "negro", "corto", None, "seria", "oval"),                                                     # Pablo Escobar
    16: _t("#d4996f", "#4a4542", "raya", None, "sonrisa", "oval", entradas=True),                                  # Jaime Pizarro
    17: _t("#efc4a4", "#4a4542", "corto", "completa", "seria", "alargada"),                                        # Caputto
    18: _t("#efc4a4", "#c9c9c9", "ondulado", None, "sonrisa", "alargada"),                                         # Pellegrini
    20: _t("#efc4a4", "castano_oscuro", "corto", "incipiente", "sonrisa", "alargada"),                             # Sierra
    21: _t("#d4996f", "#8a8582", "raya", None, "sonrisa", "redonda", entradas=True),                               # Pinto
    22: _t("#d4996f", "#8a8582", "corto", None, "sonrisa", "redonda"),                                             # Suárez
    23: _t("#d4996f", "negro", "raya", None, "seria", "oval"),                                                     # Osorio
    26: _t("#d4996f", "#c9c9c9", "raya", None, "seria", "oval"),                                                   # Zambrano
    27: _t("#5e331a", "negro", "rapado", None, "seria", "oval"),                                                   # Borja
    28: _t("#efc4a4", "castano_oscuro", "corto", "completa", "seria", "alargada"),                                 # Urrutia
    32: _t("#d4996f", "negro", "flequillo", None, "sonrisa", "oval"),                                              # Cardozo
    39: _t("#5e331a", "#8a8582", "corto", None, "seria", "oval", entradas=True, textura="muy_rizado"),              # Uribe
    49: _t("#e3ac86", "#c9c9c9", "corto", None, "seria", "redonda", entradas=True),                                # Richard Pérez
    51: _t("#efc4a4", "castano_oscuro", "corto", None, "seria", "redonda"),                                        # Daja
    48: _t("#efc4a4", "castano_oscuro", "corto", "incipiente", "seria", "alargada", textura="rizado"),             # Amorebieta
    66: _t("#efc4a4", "#4a4542", "corto", "incipiente", "seria", "alargada", entradas=True),                       # Der Zakarian
    62: _t("#efc4a4", "#8a8582", "corto", "incipiente", "seria", "oval"),                                          # Somoza
    68: _t("#e3ac86", "negro", "corto", None, "seria", "alargada"),                                                # Manucharyan
    69: _t("#e3ac86", "negro", "corto", None, "seria", "alargada"),                                                # Arasbiliz
    71: _t("#efc4a4", "castano_oscuro", "corto", "incipiente", "seria", "alargada", textura="rizado"),             # Hasenhüttl
    72: _t("#efc4a4", "#8a8582", "corto", None, "seria", "alargada", entradas=True),                               # Pauritsch
    73: _t("#efc4a4", "#8a8582", "calvo", "incipiente", "seria", "alargada"),                                      # Struber
    74: _t("#efc4a4", "#4a4542", "corto", None, "seria", "alargada"),                                              # Gregoritsch
    75: _t("#efc4a4", "castano_claro", "corto", None, "seria", "alargada"),                                        # Herzog
    78: _t("#e3ac86", "#4a4542", "corto", "incipiente", "sonrisa", "redonda"),                                     # Abbasov
    79: _t("#efc4a4", "#8a8582", "corto", None, "seria", "redonda"),                                               # Ponomaryov
    81: _t("#efc4a4", "castano_claro", "flequillo", None, "seria", "alargada"),                                    # Broos
    85: _t("#efc4a4", "castano_claro", "calvo", "incipiente", "seria", "oval"),                                    # Ciman
    87: _t("#efc4a4", "#8a8582", "corto", None, "seria", "redonda", entradas=True),                                # Dulub
    88: _t("#efc4a4", "castano_oscuro", "raya", None, "seria", "alargada", entradas=True),                         # Kubarev
    91: _t("#efc4a4", "#c9c9c9", "corto", None, "seria", "alargada"),                                              # Halilhodžić
    96: _t("#efc4a4", "castano_oscuro", "corto", None, "sonrisa", "redonda", entradas=True),                       # Mladenov
    97: _t("#e3ac86", "negro", "corto", None, "seria", "oval"),                                                    # Petev
    98: _t("#efc4a4", "#8a8582", "corto", None, "seria", "alargada"),                                              # Yankov
    99: _t("#efc4a4", "castano_oscuro", "corto", None, "sonrisa", "alargada"),                                     # Donkov
    100: _t("#efc4a4", "#8a8582", "corto", "candado", "seria", "alargada"),                                        # Penev
    104: _t("#e3ac86", "negro", "corto", "completa", "seria", "alargada"),                                         # Nicolaou
    106: _t("#efc4a4", "#4a4542", "calvo", "incipiente", "seria", "oval"),                                         # Tudor
    108: _t("#efc4a4", "#8a8582", "corto", None, "seria", "alargada"),                                             # Skočić
    110: _t("#efc4a4", "#8a8582", "calvo", "incipiente", "seria", "alargada"),                                     # Krznar
    114: _t("#efc4a4", "castano_oscuro", "corto", None, "sonrisa", "redonda"),                                     # Mølby
    115: _t("#efc4a4", "rubio", "flequillo", None, "sonrisa", "oval"),                                             # Lerby
    117: _t("#efc4a4", "#c9c9c9", "corto", None, "seria", "alargada", entradas=True),                              # Moyes
    118: _t("#efc4a4", "castano_claro", "corto", None, "seria", "oval"),                                           # Strachan
    120: _t("#efc4a4", "castano_claro", "corto", None, "seria", "oval", entradas=True),                            # Lambert
    121: _t("#efc4a4", "castano_claro", "corto", None, "sonrisa", "redonda", entradas=True),                       # Weiss
    125: _t("#efc4a4", "#c9c9c9", "corto", "incipiente", "sonrisa", "redonda"),                                    # Mentel
    126: _t("#efc4a4", "negro", "raya", None, "seria", "alargada"),                                                # Zildžović
    127: _t("#efc4a4", "negro", "corto", "completa", "sonrisa", "alargada"),                                       # Riera
    128: _t("#efc4a4", "#8a8582", "corto", None, "sonrisa", "redonda"),                                            # Kek
    143: _t("#efc4a4", "#c9c9c9", "calvo", None, "seria", "redonda"),                                              # Paatelainen
    151: _t("#e3ac86", "negro", "corto", None, "seria", "alargada"),                                               # Coleman
    152: _t("#efc4a4", "#c9c9c9", "corto", None, "seria", "alargada"),                                              # Hughes
    154: _t("#efc4a4", "castano_claro", "corto", None, "sonrisa", "alargada"),                                     # Sampson
    157: _t("#efc4a4", "negro", "rulos", None, "seria", "alargada", textura="rizado"),                             # Gutsaev
    159: _t("#e3ac86", "negro", "rulos", None, "seria", "alargada", textura="rizado"),                             # Chivadze
    163: _t("#efc4a4", "negro", "corto", None, "seria", "alargada"),                                               # Bula
    167: _t("#e3ac86", "castano_oscuro", "corto", "incipiente", "seria", "alargada"),                              # Dellas
    171: _t("#efc4a4", "#c9c9c9", "calvo", "incipiente", "seria", "alargada"),                                     # Rossi
    173: _t("#efc4a4", "castano_oscuro", "corto", "completa", "seria", "redonda"),                                 # Varga
    174: _t("#efc4a4", "castano_oscuro", "corto", None, "seria", "alargada"),                                      # Dárdai
    181: _t("#efc4a4", "castano_oscuro", "corto", "incipiente", "seria", "oval"),                                  # St Ledger
    182: _t("#efc4a4", "#4a4542", "corto", None, "seria", "alargada"),                                             # Aldridge
    183: _t("#efc4a4","castano_claro","ondulado",None,"seria","oval"), # Whelan
    187: _t("#efc4a4","#8a8582","corto",None,"seria","oval",entradas=True), # Boothroyd
    188: _t("#efc4a4","castano_claro","corto",None,"seria","cuadrada",entradas=True), # McClaren
    189: _t("#efc4a4","castano_oscuro","corto",None,"seria","oval"), # Cotterill
    190: _t("#efc4a4","castano_oscuro","corto","completa","sonrisa","alargada"), # Southgate
    191: _t("#f6d7c3","rubio","corto",None,"seria","alargada"), # Hallgrímsson
    192: _t("#efc4a4","castano_oscuro","raya",None,"seria","alargada"), # Sverrisson
    193: _t("#f6d7c3","rubio","corto","incipiente","seria","alargada"), # McShane
    194: _t("#efc4a4","castano_claro","rapado",None,"seria","oval"), # Steinsson
    197: _t("#f6d7c3","rubio","flequillo",None,"seria","alargada"), # Samuelsen
    198: _t("#efc4a4","castano_claro","raya","candado","seria","oval",anteojos=True), # J. M. Olsen
    201: _t("#e3ac86","#4a4542","corto",None,"seria","oval",entradas=True), # Grant
    212: _t("#efc4a4","castano_oscuro","corto",None,"seria","alargada"), # Neustädter
    213: _t("#efc4a4","#8a8582","corto",None,"seria","oval",anteojos=True,entradas=True), # Yarovenko
    215: _t("#efc4a4","negro","corto",None,"seria","alargada"), # Rusnac
    236: _t("#efc4a4","castano_oscuro","ondulado",None,"seria","alargada"), # Saibene
    241: _t("#efc4a4","negro","corto",None,"seria","alargada"), # Andonovski
    254: _t("#efc4a4","castano_oscuro","corto","incipiente","seria","alargada"), # Savinov
    256: _t("#e3ac86","negro","ondulado","incipiente","seria","alargada",textura="rizado"), # Vukićević
    259: _t("#e3ac86","negro","corto",None,"seria","oval",entradas=True), # Savićević
    264: _t("#f6d7c3","rubio","corto",None,"seria","redonda",entradas=True), # Hogmo
    271: _t("#efc4a4","#4a4542","corto",None,"seria","oval",anteojos=True), # Michniewicz
    273: _t("#efc4a4","castano_claro","raya",None,"seria","alargada"), # Tarasiewicz
    281: _t("#efc4a4","castano_claro","calvo",None,"seria","oval"), # Koubek
    283: _t("#efc4a4","#8a8582","corto",None,"sonrisa","redonda",entradas=True), # Vrba
    285: _t("#efc4a4","negro","tupe",None,"seria","alargada"), # Galásek
    286: _t("#e3ac86","negro","calvo",None,"seria","oval"), # Zenga
    292: _t("#efc4a4","castano_oscuro","calvo","candado","seria","cuadrada"), # Cherchesov
    293: _t("#d4996f","negro","raya","candado","seria","oval"), # Gazzaev
    294: _t("#efc4a4","castano_oscuro","corto",None,"seria","redonda"), # Slutsky
    295: _t("#efc4a4","castano_claro","raya",None,"seria","alargada"), # Kononov
    297: _t("#efc4a4","#6e6a68","corto",None,"seria","alargada",entradas=True), # Mazza
    299: _t("#e3ac86","#6e6a68","ondulado","completa","seria","oval"), # Cevoli
    304: _t("#efc4a4","castano_oscuro","corto",None,"seria","alargada"), # Rajović
    305: _t("#efc4a4","castano_oscuro","ondulado",None,"sonrisa","alargada"), # Petrović
    307: _t("#efc4a4","castano_claro","corto",None,"seria","alargada"), # Nilsson
    311: _t("#efc4a4","#c9c9c9","corto",None,"seria","alargada",entradas=True), # Petković
    312: _t("#efc4a4","castano","corto",None,"seria","alargada",anteojos=True), # Weiler
    313: _t("#efc4a4","castano_oscuro","largo_atado","completa","seria","alargada"), # Schmidt
    320: _t("#e3ac86","negro","tupe","completa","seria","alargada"), # Şahin
    321: _t("#efc4a4","#4a4542","corto",None,"seria","cuadrada",anteojos=True,entradas=True), # Lyutyi
    323: _t("#efc4a4","castano_claro","raya","incipiente","seria","alargada"), # Fedorov
    324: _t("#efc4a4","castano","corto",None,"seria","redonda",entradas=True), # Pyatenko
    325: _t("#efc4a4","#c9c9c9","raya",None,"seria","alargada"), # Protasov
    356: _t("#5e331a","negro","calvo",None,"seria","redonda"), # Best
    362: _t("#efc4a4","negro","tupe",None,"seria","cuadrada"), # Koch
    365: _t("#efc4a4","castano_oscuro","corto","completa","seria","oval"), # Edgar
    366: _t("#d4996f","#8a8582","corto",None,"seria","alargada",entradas=True), # Guimarães
    368: _t("#d4996f","negro","raya",None,"seria","alargada"), # Campos
    369: _t("#93572e","negro","calvo",None,"seria","oval"), # Wright
    391: _t("#efc4a4","castano_claro","calvo",None,"seria","alargada"), # Bradley
    392: _t("#e3ac86","castano_oscuro","ondulado",None,"seria","alargada"), # Arena
    393: _t("#efc4a4","castano_claro","raya",None,"seria","alargada"), # Marsch
    395: _t("#efc4a4","castano_claro","calvo",None,"sonrisa","oval"), # Berhalter
    413: _t("#93572e","negro","rastas","completa","seria","alargada",textura="muy_rizado"), # Mustivar
    414: _t("#5e331a","rubio","corto","incipiente","seria","alargada",textura="rizado"), # Eloi
    416: _t("#d4996f","#c9c9c9","raya",None,"seria","alargada",entradas=True), # Rueda
    444: _t("#5e331a","negro","calvo","incipiente","sonrisa","redonda"), # Moore
    446: _t("#d4996f","castano_oscuro","raya",None,"seria","redonda"), # Herrera
    447: _t("#efc4a4","negro","corto",None,"seria","oval"), # Passy
    449: _t("#d4996f","#8a8582","raya",None,"seria","alargada",entradas=True), # Aguirre
}
