"""Rivalidades y alianzas entre personajes (services/relaciones.py lógica pura + services/relaciones_service.py Mongo).

Colección `relaciones`: {_id "<tipo>:<a>:<b>", tipo seleccion|marca|medio|tv, a, b (a < b), clase rivalidad|alianza, intensidad 0-100, motivos[]}.
- SELECCIONES: se derivan de lo jugado (misma confederación, enfrentamientos previos, márgenes cortos, eliminación directa, calor de los partidos) y
  se recalculan al terminar cada partido entre ellas; `restart_mundial` las borra. Con `UMBRAL_RIVALIDAD` es «Rivalidad» y con `UMBRAL_CLASICO` «Clásico».
- MARCAS, MEDIOS y CADENAS DE TV: se derivan de sus rasgos (rubro, rasgo del dueño, línea editorial, país) con `generar_relaciones.py`; son permanentes.
"""
UMBRAL_RIVALIDAD = 38   # ~10% de las parejas que ya se han enfrentado (578 en 1.162 partidos)
UMBRAL_CLASICO = 44     # ~2,4% de esas parejas: cuatro duelos parejos en la misma confederación o con calor, o un cruce de eliminación directa

PUNTOS_SELECCION = {"misma_confederacion": 10, "por_encuentro": 5, "tope_encuentros": 20, "margen_corto": 6, "tope_margen": 18,
                    "eliminacion_directa": 25, "por_calor": 6, "tope_calor": 24}

IMPORTANCIA_CLASICO = 1.2        # multiplicador de lo que mueve un partido a los aficionados cuando es un Clásico (fanbase_service)
RELEVANCIA_CLASICO = 0.10        # cuánto sube el interés de la prensa en un Clásico (prensa.relevancia)

# marcas: rivales del mismo rubro; el choque de los rasgos de sus dueños sube la intensidad
RIVALES_MARCA_BASE = 40
RIVALES_MARCA_ALCANCE = 10
RASGOS_CHOQUE = {("tiburon", "tiburon"): 25, ("imagen", "imagen"): 12, ("austero", "imagen"): 12, ("heredero", "fundador"): 10}
RASGOS_AFINES = {("filantropo", "futbolero"), ("fundador", "heredero"), ("futbolero", "futbolero"), ("filantropo", "filantropo"), ("austero", "austero")}
ALIADOS_POR_MARCA = 2

# medios: líneas editoriales que chocan (rivales) o coinciden (aliados) dentro de un país
LINEAS_OPUESTAS = {frozenset(("sensacionalista", "analitica")), frozenset(("oficialista", "critica")), frozenset(("optimista", "critica"))}
RIVALES_MEDIO = 60
ALIADOS_MEDIO = 50
RIVALES_TV = 45
