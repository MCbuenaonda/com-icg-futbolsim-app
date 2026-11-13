"""Derechos de nombre de estadios (services/naming_sedes_service.py).

Una marca ficticia le ofrece al dueño de una sede ponerle su nombre al estadio. Si acepta, cobra una firma y un pago extra
por cada partido que aloje (se suma a la regalía normal, ver venue_service.process_match_city_revenue). Todo va al saldo del
dueño. El contrato dura mientras el estadio tenga partidos por jugar en el Mundial en curso.
"""
from config.marcas import ALCANCES  # noqa: F401  (los niveles: 3 global, 2 continental, 1 local)

REGALIA_BASE = 100                                   # la misma de venue_service (se reexporta para calibrar aquí)

# pago por partido alojado = REGALIA_BASE x factor del alcance (x MULTIPLICADOR_FASE_ALTA en semifinales/3er lugar/final)
FACTOR_PAGO = {3: 0.60, 2: 0.45, 1: 0.30}             # global, continental, local
FIRMA_EN_PARTIDOS = 2                                # firma = 2 pagos por partido

CUPO_POR_MARCA = {3: 3, 2: 2, 1: 1}                  # sedes que puede bautizar una marca a la vez (ofertas abiertas + contratos)
PARTIDOS_RONDA = 8                                   # cada 8 partidos terminados del torneo se evalúan las ofertas
OFERTA_RONDAS = 1                                    # una oferta vence a los 8 partidos (la siguiente ronda)
PROB_OFERTA_SEDE = 0.50                              # por sede elegible y ronda

# castigos (suaves: nunca más de la firma ni dejan el saldo bajo cero)
PENALIZACION_FIRMA = 0.50                            # romper antes de tiempo, vender con contrato vigente o quedarse sin partidos

FORMATOS_NOMBRE = ("Arena {m}", "Estadio {m}", "{m} Arena", "{m} Stadium", "Coliseo {m}")
