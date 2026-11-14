"""Agentes (representantes) de los jugadores y selecciones: catálogo FICTICIO de 100 en la colección permanente `agentes`
(generar_agentes.py) y contratos por universo en `corp_agentes` (services/corporativo_agentes_service.py).

Un agente trabaja para UN representado de tu cartera. Mejora lo que pagan y lo que se interesan las MARCAS (bono sobre firma y
pago por ciclo, más encaje) y mueve el riesgo de corte de sus patrocinios; a cambio se queda con una comisión de lo que paguen.
Todo se escala por su `calidad` (prestigio, 0..1) y por si conoce la región del representado (misma confederación = completo,
otra = a la mitad). Bien elegido deja ~+1-3% sobre lo que pagan las marcas y más ofertas; mal elegido, ~-3%: se nota, no asusta.
"""
TOTAL_AGENTES = 100
# agentes por confederación (id de confederación -> cantidad); suman TOTAL_AGENTES
AGENTES_POR_CONFEDERACION = {1: 30, 4: 20, 6: 18, 3: 14, 2: 10, 5: 8}

RASGOS = {
    "tiburon": {"nombre": "Tiburón", "icono": "bi-lightning-charge-fill", "bono_pago": 0.13, "encaje": 4, "riesgo": 6, "comision": (0.09, 0.10),
                "texto": "Exprime a las marcas: consigue más dinero, pero a veces las incomoda y el patrocinio corre más riesgo.",
                "look": "tiburon"},
    "leal": {"nombre": "Leal", "icono": "bi-shield-heart", "bono_pago": 0.07, "encaje": 3, "riesgo": -5, "comision": (0.05, 0.06),
             "texto": "Cobra poco y cuida la relación con las marcas: los patrocinios duran y rara vez se rompen.", "look": "tradicional"},
    "discreto": {"nombre": "Discreto", "icono": "bi-eye-slash-fill", "bono_pago": 0.09, "encaje": 2, "riesgo": -10, "comision": (0.07, 0.08),
                 "texto": "Maneja todo sin ruido: baja mucho el riesgo de que una marca se asuste y corte.", "look": "ahorrador"},
    "relacionista": {"nombre": "Relacionista", "icono": "bi-people-fill", "bono_pago": 0.09, "encaje": 9, "riesgo": 0, "comision": (0.08, 0.09),
                     "texto": "Conoce a todo el mundo: las marcas se acercan más a su representado.", "look": "mecenas"},
    "estratega": {"nombre": "Estratega", "icono": "bi-bullseye", "bono_pago": 0.12, "encaje": 5, "riesgo": -3, "comision": (0.08, 0.09),
                  "texto": "Arma cada contrato con cabeza: buen pago, buen encaje y poco riesgo.", "look": "visionario"},
}
PESOS_RASGO = {"tiburon": 20, "leal": 24, "discreto": 18, "relacionista": 20, "estratega": 18}

CUPO_POR_AGENTE = 3            # representados que puede llevar a la vez en un mismo universo
MAX_AGENTES_USUARIO = 6        # contratos de agente simultáneos de tu corporativo
CICLOS_CONTRATO = 4            # duración del contrato (se puede renovar al vencer)
ESCALA_CALIDAD = (0.6, 1.4)    # multiplicador de sus efectos según su calidad (0 -> 0,6; 1 -> 1,4)
ESCALA_REGION_AJENA = 0.5      # si no conoce la región del representado, sus bonos valen la mitad
PENALIZACION_CANCELAR = 0.5    # cancelar antes de tiempo: medio ciclo de la comisión de ese representado
SINERGIA_ALBUM_COMISION = 0.01 # con su estampa del álbum, 1 punto menos de comisión (mínimo MIN_COMISION)
MIN_COMISION = 0.04
ID_ESTAMPA_BASE = 900000       # id de su estampa en `album_medios` = 900000 + agente.id
