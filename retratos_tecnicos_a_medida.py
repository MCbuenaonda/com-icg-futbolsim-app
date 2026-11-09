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
}
