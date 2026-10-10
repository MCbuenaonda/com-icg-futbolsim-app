import certifi
from fastapi import HTTPException, status
from google.api_core.exceptions import GoogleAPIError
from pymongo.mongo_client import MongoClient
from pymongo import UpdateOne
from config.settings import MONGODB_URI
from typing import Dict, Any, Tuple

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

def get_paises(logger):
    try:        
        collection = db['paises']
        # Ejecutar la consulta
        paises = list(collection.find())        
        return paises
    except GoogleAPIError as e:
        logger.error(f"Error de MongoBD: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error de MongoBD: {str(e)}")
    except Exception as e:
        logger.error(f"Error al obtener el pais: {str(e)}")
        raise HTTPException(status_code=409, detail=f"Error al obtener el pais: {str(e)}")

def get_pais(id_pais, logger):
    try:        
        collection = db['paises']
        # Ejecutar la consulta
        pais = collection.find_one({"id": int(id_pais)})
        
        # obtener las ciudades del pais
        if pais:
            collection_ciudades = db['ciudades']
            ciudades = list(collection_ciudades.find({"pais_id": int(id_pais)}))
            pais['ciudades'] = ciudades
        return pais
    except GoogleAPIError as e:
        logger.error(f"Error de MongoBD: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error de MongoBD: {str(e)}")
    except Exception as e:
        logger.error(f"Error al obtener el pais: {str(e)}")
        raise HTTPException(status_code=409, detail=f"Error al obtener el pais: {str(e)}")


def get_anfitrion(confederacion_id, logger):
    try:        
        logger.info(f"Consultando pais anfitrion de la confederacion {confederacion_id}")
        collection = db['paises']
        # Pipeline de agregación
        pipeline = [
            {'$match': {'confederacion_id': confederacion_id}},
            {'$sample': {'size': 1}}
        ]
        
        # Ejecutar la consulta
        anfitrion = collection.aggregate(pipeline)
        # Convertir el cursor a una lista y obtener el primer (y único) documento
        anfitrion = list(anfitrion)[0]
        return anfitrion              
    except GoogleAPIError as e:
        logger.error(f"Error de MongoBD: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error de MongoBD: {str(e)}")
    except Exception as e:
        logger.error(f"Error al obtener el pais: {str(e)}")
        raise HTTPException(status_code=409, detail=f"Error al obtener el pais: {str(e)}")


# función para actualizar las estadísticas de los países después de un partido
def actualizar_estadisticas_pais(pais_local: int, pais_visita: int, goles_local: int, goles_visita: int, estadisticas: dict):
    """
    Actualiza las estadísticas de los países en la colección 'internacional' después de un partido.

    :param db: Conexión a la base de datos MongoDB.
    :param pais_local: ID del país local.
    :param pais_visita: ID del país visitante.
    :param goles_local: Goles anotados por el equipo local.
    :param goles_visita: Goles anotados por el equipo visitante.
    """
    collection = db['internacional']
    
    # Determinar el resultado del partido
    if goles_local > goles_visita:
        puntos_local, puntos_visita = 3, 0
        juegos_ganados_local, juegos_ganados_visita = 1, 0
        juegos_perdidos_local, juegos_perdidos_visita = 0, 1
        juegos_empatados_local, juegos_empatados_visita = 0, 0
    elif goles_local < goles_visita:
        puntos_local, puntos_visita = 0, 3
        juegos_ganados_local, juegos_ganados_visita = 0, 1
        juegos_perdidos_local, juegos_perdidos_visita = 1, 0
        juegos_empatados_local, juegos_empatados_visita = 0, 0
    else:  # Empate
        puntos_local, puntos_visita = 1, 1
        juegos_ganados_local, juegos_ganados_visita = 0, 0
        juegos_perdidos_local, juegos_perdidos_visita = 0, 0
        juegos_empatados_local, juegos_empatados_visita = 1, 1

    # Función auxiliar para calcular estadísticas actualizadas
    def calcular_estadisticas(estadisticas, puntos, juegos_ganados, juegos_empatados, juegos_perdidos, goles_favor, goles_contra):
        estadisticas["puntos"] += puntos
        estadisticas["juegos_jugados"] += 1
        estadisticas["juegos_ganados"] += juegos_ganados
        estadisticas["juegos_empatados"] += juegos_empatados
        estadisticas["juegos_perdidos"] += juegos_perdidos
        estadisticas["goles_favor"] += goles_favor
        estadisticas["goles_contra"] += goles_contra
        estadisticas["diferencia_goles"] = estadisticas["goles_favor"] - estadisticas["goles_contra"]
        return estadisticas
    
    # Función auxiliar para actualizar estadísticas adicionales
    def actualizar_estadisticas_adicionales(estadisticas, nuevas_estadisticas, juegos_jugados_previos):
        """
        Promedia las métricas del partido recién jugado con el histórico acumulado, usando
        'juegos_jugados_previos' (el conteo ANTES de sumar este partido) como peso, para que
        sea un promedio real a lo largo de todo el torneo.

        Antes: 'p_posesion/p_ofensiva/p_defensiva' se recalculaban como
        (valor_actual + valor_partido) / 2 sin importar cuántos partidos ya se habían
        jugado -- eso no es un promedio, es una media móvil que sobrepesa siempre el último
        partido (ej. tras el partido 1 el valor queda en la mitad de lo que debería,
        value/2, y converge mal a medida que se juegan más partidos). Y
        'efectividad_gol/promedio_gol' directamente se pisaban con el valor del último
        partido, perdiendo todo el historial -- inconsistente con 'goles_favor/goles_contra'
        del mismo documento, que sí son sumas acumuladas reales.
        """
        total_previo = max(0, juegos_jugados_previos)
        for key in ["p_posesion", "p_ofensiva", "p_defensiva", "efectividad_gol", "promedio_gol"]:
            promedio_actual = estadisticas.get(key, 0)
            valor_partido = nuevas_estadisticas.get(key, 0)
            acumulado = promedio_actual * total_previo
            decimales = 2 if key == "promedio_gol" else 1
            estadisticas[key] = round((acumulado + valor_partido) / (total_previo + 1), decimales)
        return estadisticas

    # Actualizar estadísticas del país local
    pais_local_data = collection.find_one({"id": pais_local})
    if pais_local_data:
        estadisticas_local = pais_local_data.get("estadisticas", {})
        juegos_previos_local = estadisticas_local.get("juegos_jugados", 0)
        estadisticas_local = calcular_estadisticas(
            estadisticas_local, puntos_local, juegos_ganados_local, juegos_empatados_local,
            juegos_perdidos_local, goles_local, goles_visita
        )
        estadisticas_local = actualizar_estadisticas_adicionales(estadisticas_local, estadisticas["local"], juegos_previos_local)
        collection.update_one({"id": pais_local}, {"$set": {"estadisticas": estadisticas_local}})

    # Actualizar estadísticas del país visitante
    pais_visita_data = collection.find_one({"id": pais_visita})
    if pais_visita_data:
        estadisticas_visita = pais_visita_data.get("estadisticas", {})
        juegos_previos_visita = estadisticas_visita.get("juegos_jugados", 0)
        estadisticas_visita = calcular_estadisticas(
            estadisticas_visita, puntos_visita, juegos_ganados_visita, juegos_empatados_visita,
            juegos_perdidos_visita, goles_visita, goles_local
        )
        estadisticas_visita = actualizar_estadisticas_adicionales(estadisticas_visita, estadisticas["visitante"], juegos_previos_visita)
        collection.update_one({"id": pais_visita}, {"$set": {"estadisticas": estadisticas_visita}})

# función para actualizar el poder y ranking de un país después de un partido
def actualizar_poder_y_rankin(lado, pais_id, resultado, partido):
    #: diferencia_goles, rankin_oponente, poder_oponente
    paises_coll = db['internacional']
    paises_stats = db['paises']    
    
    # 1. Obtener el país y su rival
    pais = paises_coll.find_one({"id": pais_id})
    id_oponente = partido["id_visitante"] if lado == "L" else partido["id_local"]
    oponente = paises_coll.find_one({"id": id_oponente})
    
    # Lectura de poder actual (Default 0 para alinearse al torneo desde cero)
    poder_actual = pais.get("estadisticas", {}).get("poder", 0.0)
    poder_oponente = oponente.get("estadisticas", {}).get("poder", 0.0)
    
    # 2. Factor oponente basado en PODER relativo
    # Si el rival tiene más poder, ganar le da un extra (hasta 1.5x)
    # Si el rival tiene menos poder, ganar le da un poco menos (mínimo 0.7x)
    diferencia_poder = poder_oponente - poder_actual
    
    # Normalización del factor entre 0.7 y 1.5
    if diferencia_poder > 0:
        factor_oponente = 1.0 + min(0.5, diferencia_poder / 100.0)
    elif diferencia_poder < 0:
        factor_oponente = max(0.7, 1.0 + (diferencia_poder / 100.0))
    else:
        factor_oponente = 1.0  # Si están iguales (como en la Jornada 1), el factor es neutro
        
    # 3. Diferencia de goles
    goles_favor = partido["goles_local"] if lado == "L" else partido["goles_visitante"]
    goles_contra = partido["goles_visitante"] if lado == "L" else partido["goles_local"]
    diff_goles = abs(goles_favor - goles_contra)

    # 4. Determinar la variación según el resultado
    ganador = resultado["ganador_lado"]
    k_factor = 10.0  # Constante de impacto para dar mayor dinamismo
    
    if (lado == "L" and ganador == "L") or (lado == "V" and ganador == "V"):
        # VICTORIA: Puntos base + bono por diferencia de goles * factor rival
        bono_goles = diff_goles * 1.5
        cambio_poder = (k_factor + bono_goles) * factor_oponente
        
    elif ganador == "E":  # Empate
        # EMPATE: Si el rival es superior (+poder), sumar un poco; si es inferior, restar un poco
        # Pequeño bono si hubo goles en el empate
        bono_empate_goles = goles_favor * 0.5
        cambio_poder = ((factor_oponente - 1.0) * k_factor) + bono_empate_goles
        
    else:
        # DERROTA: Resta según la diferencia de goles y la debilidad del rival
        penalizacion_goles = diff_goles * 1.2
        cambio_poder = -(k_factor + penalizacion_goles) * (2.0 - factor_oponente)

    # 5. Guardar poder actualizado con redondeo. Se permite que quede en negativo a propósito
    # (antes se pisaba con max(0.0, ...)): con el piso duro en 0, varios equipos en mala racha
    # terminaban todos empatados justo en 0.0 sin forma de diferenciarse entre sí, y
    # recalcular_rankin() ordena por este mismo campo -- el ranking del fondo de la tabla
    # quedaba resuelto casi al azar (por el orden en que Mongo devuelve los documentos) en vez
    # de reflejar quién viene peor. Dejarlo negativo conserva esa diferenciación real para el
    # ranking; si hace falta no mostrar números negativos, recortar a 0 en la capa de vista
    # (ver templates/pais.html), no acá.
    poder_actualizado = round(poder_actual + cambio_poder, 2)

    paises_coll.update_one(
        {"id": pais_id}, 
        {"$set": {"estadisticas.poder": poder_actualizado}}
    )
    
    paises_stats.update_one(
        {"id": pais_id}, 
        {"$set": {"estadisticas.poder": poder_actualizado}}
    )



# función para recalcular el ranking de todos los países basado en su poder
def recalcular_rankin():
    paises_coll = db['paises']
    internacional_coll = db['internacional']

    # Obtener todos los países y ordenarlos por poder
    paises = list(paises_coll.find().sort("estadisticas.poder", -1))

    # Solo se arma una operación para 'internacional' si el país realmente está activo ahí
    # (torneo en curso) -- antes se generaba una UpdateOne por cada uno de los ~211 países
    # de 'paises', aunque la mayoría no matchea ningún documento en 'internacional' (que solo
    # tiene los países activos de la fase actual, normalmente bastantes menos que 211).
    ids_en_internacional = set(internacional_coll.distinct("id"))

    # Asignar el nuevo ranking en batch (1 bulk_write por colección en vez de
    # 2 update_one por país)
    operaciones_paises = []
    operaciones_internacional = []

    for i, pais in enumerate(paises):
        nuevo_rankin = i + 1
        filtro = {"id": pais["id"]}
        cambio = {"$set": {"estadisticas.rankin": nuevo_rankin}}
        operaciones_paises.append(UpdateOne(filtro, cambio))
        if pais["id"] in ids_en_internacional:
            operaciones_internacional.append(UpdateOne(filtro, cambio))

    if operaciones_paises:
        paises_coll.bulk_write(operaciones_paises)
    if operaciones_internacional:
        internacional_coll.bulk_write(operaciones_internacional)

# ==========================================
# Trayectoria del país por Mundial (perfil /paises/{id})
# ==========================================
def obtener_trayectoria_pais(pais_id: int) -> list:
    """
    Por cada Mundial (más reciente primero): hasta qué fase llegó el país y cómo terminó (de
    'historial', que guarda una foto por país al cerrar cada fase, y de 'internacional' para el
    Mundial en curso), más su balance de partidos en ese torneo (de 'juegos', por mundial_id).
    """
    nombres_fase = {f["id"]: f.get("nombre", "") for f in db["fases"].find({}, {"id": 1, "nombre": 1})}
    trayectoria = []
    for m in db["mundiales"].find({}, {"anio": 1, "activo": 1, "campeon": 1}).sort("anio", -1):
        mid = str(m["_id"])
        fotos = list(db["historial"].find({"id": pais_id, "mundial_id": mid}, {"fase_eliminatoria": 1, "estado": 1}))
        actual = db["internacional"].find_one({"id": pais_id, "mundial_id": mid}, {"fase_eliminatoria": 1, "estado": 1}) if m.get("activo") else None
        candidatos = fotos + ([actual] if actual else [])
        if not candidatos:
            continue
        ultima = max(candidatos, key=lambda d: d.get("fase_eliminatoria") or 0)
        balance = {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0}
        for j in db["juegos"].find({"mundial_id": mid, "estado": "finalizado", "$or": [{"equipo_local.id": pais_id}, {"equipo_visitante.id": pais_id}]},
                                   {"equipo_local.id": 1, "resultado.goles_local": 1, "resultado.goles_visitante": 1, "resultado.ganador_id": 1, "resultado.ganador_lado": 1}):
            res = j.get("resultado") or {}
            es_local = (j.get("equipo_local") or {}).get("id") == pais_id
            gf = res.get("goles_local", 0) if es_local else res.get("goles_visitante", 0)
            gc = res.get("goles_visitante", 0) if es_local else res.get("goles_local", 0)
            balance["pj"] += 1
            balance["gf"] += gf or 0
            balance["gc"] += gc or 0
            if res.get("ganador_lado") in ("L", "V"):
                balance["g" if res.get("ganador_id") == pais_id else "p"] += 1
            else:
                balance["e"] += 1
        estado = (ultima.get("estado") or "").upper()
        trayectoria.append({
            "anio": m.get("anio"), "activo": bool(m.get("activo")),
            "campeon": m.get("campeon") == pais_id,
            "fase": nombres_fase.get(ultima.get("fase_eliminatoria"), f"Fase {ultima.get('fase_eliminatoria')}"),
            "estado": estado.replace("_", " ").capitalize() if estado else "",
            "eliminado": estado.startswith("ELIMINADO"),
            **balance,
        })
    return trayectoria
