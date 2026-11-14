"""Clima económico (services/clima_economico.py): un estado GLOBAL por ciclo de corporativos (cada PARTIDOS_POR_CICLO partidos) que mueve un poco
lo que pagan las marcas, las televisoras y el patrocinio base de los contratos. Igual para todos los universos y para la IA; suave y con vuelta a la media.

Cadena de Markov con semilla por ciclo (reproducible, no se guarda): ~69% de los ciclos en normal, ~17% en auge y ~14% en recesión (las recesiones duran
~1,7 ciclos). Multiplicador medio ≈ 1,000: el ROI promedio no cambia, solo se reparte en el tiempo.

Seguro (opcional, del corporativo del usuario): prima = SEGURO_PRIMA de lo que habría ingresado por marcas, TV y patrocinio base ese ciclo (sin recesión ni
crisis); indemnización = SEGURO_COBERTURA de lo que se dejó de ganar por la recesión y por la rebaja de las crisis de marcas (services/escandalos.py).
"""
ESTADOS = ("auge", "normal", "recesion")
FACTOR = {"auge": 1.10, "normal": 1.00, "recesion": 0.88}
NOMBRE = {"auge": "Auge", "normal": "Normal", "recesion": "Recesión"}
TRANSICIONES = {"normal": {"normal": 0.75, "auge": 0.125, "recesion": 0.125},
                "auge": {"auge": 0.50, "normal": 0.50, "recesion": 0.0},
                "recesion": {"recesion": 0.40, "normal": 0.60, "auge": 0.0}}
SEGURO_PRIMA = 0.015
SEGURO_COBERTURA = 0.60
