import random
import string
from typing import Dict, Any, List, Optional, Tuple
from pymongo.database import Database
from pymongo import UpdateOne

# Matriz centralizada de reglas: REGLAS_FASE_GRUPOS[fase_id][confederacion_id] = num_grupos
REGLAS_FASE_GRUPOS = {
    1: {1: 12, 2: 1, 3: 2, 4: 9, 5: 2, 6: 10},
    2: {1: 4, 3: 6, 4: 2, 5: 2, 6: 9},
    3: {3: 3, 4: 1, 5: 2, 6: 3},
    4: {5: 1, 6: 2},
    5: {6: 1},
    6: {7: 2}
}

def generar_nombres_grupos(cantidad: int) -> List[str]:
    """Genera letras de grupo: ['A', 'B', 'C', ...]"""
    return [string.ascii_uppercase[i] for i in range(cantidad)]

def asignar_grupos_fase(db: Database, fase_id: int, mundial_id: Any, confederacion_id: Optional[int] = None) -> Dict[str, Any]:
    internacional_coll = db["internacional"]
    
    # 1. Obtener todas las reglas para la fase solicitada
    reglas_fase = REGLAS_FASE_GRUPOS.get(fase_id, {})
    
    if not reglas_fase:
        return {
            "exito": False,
            "mensaje": f"No existen reglas configuradas para la Fase {fase_id}.",
        }
            
    # 2. Filtrar si es una fase > 1 o si se envió específicamente una confederación
    if fase_id > 1 and confederacion_id is not None:
        if confederacion_id in reglas_fase:
            # Se aísla ÚNICAMENTE la confederación solicitada
            reglas_grupos = {confederacion_id: reglas_fase[confederacion_id]}
        else:
            return {
                "exito": True,
                "registros_actualizados": 0,
                "mensaje": f"La Confederación {confederacion_id} no requiere asignación de grupos en la Fase {fase_id}.",
            }
    else:
        # Fase 1 (o si no se especificó confederación): procesa todo lo definido en la fase
        reglas_grupos = reglas_fase
    

    operaciones_actualizacion = []
    resumen_grupos = {}

    # 3. Iterar según las reglas resultantes (sea 1 sola confederación o todas)
    for conf_id, num_grupos in reglas_grupos.items():
        # 1. Obtener países activos en la colección 'internacional' para este mundial
        paises = list(internacional_coll.find({
            "mundial_id": mundial_id,
            "confederacion_id": conf_id
        }))

        if not paises:
            continue

        # 2. Mezclar aleatoriamente las selecciones para el sorteo
        random.shuffle(paises)

        nombres_grupos = generar_nombres_grupos(num_grupos)
        
        # Estructura para almacenar los índices por grupo
        conteo_por_grupo = {grupo: 0 for grupo in nombres_grupos}
        
        # 3. Distribuir selecciones equitativamente (Round Robin / Sorteo)
        for idx, pais in enumerate(paises):
            # Asignación Cíclica: País 0 -> Grupo A, País 1 -> Grupo B, ...
            grupo_designado = nombres_grupos[idx % num_grupos]
            conteo_por_grupo[grupo_designado] += 1
            idx_grupo = conteo_por_grupo[grupo_designado] # Posición dentro del grupo (1, 2, 3...)

            # Preparar la actualización para MongoDB
            operaciones_actualizacion.append(
                UpdateOne(
                    {"_id": pais["_id"]},
                    {"$set": {
                        "grupo": grupo_designado,
                        "idx_grupo": idx_grupo
                    }}
                )
            )

        resumen_grupos[f"confederacion_{conf_id}"] = {
            "total_paises": len(paises),
            "total_grupos": num_grupos,
            "distribucion": conteo_por_grupo
        }

    # 4. Ejecutar actualización masiva en MongoDB
    if operaciones_actualizacion:
        resultado = internacional_coll.bulk_write(operaciones_actualizacion)
        modificados = resultado.modified_count
    else:
        modificados = 0

    return {
        "exito": True,
        "registros_actualizados": modificados,
        "resumen": resumen_grupos,
        "mensaje": "Sorteo y asignación de grupos realizada exitosamente."
    }


def creacion_grupos_mundial(db, mundial_id):
    internacional_coll = db["internacional"]

    # obtener paises de coleccion internacionales ordenados por el rankin del mejor al peor
    paises = list(internacional_coll.find({"confederacion_id": 8}).sort("estadisticas.rankin", 1))
    
    # 1. Separar al anfitrión del resto de los países
    anfitrion = None
    demas_paises = []
    
    # el biombo_uno tendra al pais con el estado 'CALIFICADO_MUNDIAL_ANFITRION' y los 11 primeros lugares de los paises
    for pais in paises:
        if pais['estado'] == 'CALIFICADO_MUNDIAL_ANFITRION':
            anfitrion = pais
        else:
            demas_paises.append(pais)
    
    
    # 2. Asignar el anfitrión como el PRIMER elemento del biombo_uno
    biombo_uno = []
    if anfitrion:
        biombo_uno.append(anfitrion)

    # 3. Llenar los biombos en orden con los demás países
    biombo_dos = []
    biombo_tres = []
    biombo_cuatro = []

    for pais in demas_paises:
        if len(biombo_uno) < 12:
            biombo_uno.append(pais)
        elif len(biombo_dos) < 12:
            biombo_dos.append(pais)
        elif len(biombo_tres) < 12:
            biombo_tres.append(pais)
        elif len(biombo_cuatro) < 12:
            biombo_cuatro.append(pais)
    
    # 4 biombos en las variables biombo_1, biombo_2, biombo_3, biombo_4:
    biombos = [biombo_uno, biombo_dos, biombo_tres, biombo_cuatro]

    # 1. Ejecutar el sorteo en memoria
    grupos_resultado = sortear_grupos_mundial(biombos)

    # 2. Guardar las modificaciones en la base de datos MongoDB
    guardar_grupos_en_db(db, grupos_resultado)
    

# funcion para la validacion en la construccion de grupos
def validar_reglas_fifa(grupo: List[Dict[str, Any]], pais: Dict[str, Any]) -> bool:
    """
    Verifica si un país puede ingresar a un grupo respetando las reglas de la FIFA.
    """
    conf_id = pais.get('conf_id')
    
    # Contar cuántos países de la misma confederación hay actualmente en el grupo
    misma_confederacion = sum(1 for p in grupo if p.get('conf_id') == conf_id)
    
    # Regla UEFA (conf_id == 1): Máximo 2 por grupo
    if conf_id == 1:
        return misma_confederacion < 2
    
    # Demás confederaciones (CONMEBOL, CONCACAF, CAF, AFC, OFC): Máximo 1 por grupo
    return misma_confederacion < 1


def sortear_grupos_mundial(biombos: List[List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Realiza el sorteo de los 12 grupos (A a L) asignando 1 equipo de cada biombo por grupo.
    """
    nombres_grupos = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
    
    # Reintentos por si un sorteo queda bloqueado sin combinaciones válidas
    max_intentos = 1000
    
    for intento in range(max_intentos):
        grupos = {g: [] for g in nombres_grupos}
        sorteo_exitoso = True

        for idx_biombo, biombo in enumerate(biombos):
            # Copia del biombo para ir extrayendo de forma aleatoria
            equipos_disponibles = biombo.copy()
            random.shuffle(equipos_disponibles)
            
            # Si estamos en el Biombo 1, asegurar que el ANFITRION vaya al Grupo A
            if idx_biombo == 0:
                anfitrion = next((p for p in equipos_disponibles if p.get('estado') == 'CALIFICADO_MUNDIAL_ANFITRION'), None)
                if anfitrion:
                    equipos_disponibles.remove(anfitrion)
                    anfitrion['grupo'] = 'A'
                    anfitrion['idx_grupo'] = 1
                    grupos['A'].append(anfitrion)

            # Recorrer cada grupo para asignarle un equipo del biombo actual
            for letra_grupo in nombres_grupos:
                # Si el Grupo A ya recibió al anfitrión en el Biombo 1, saltarlo
                if idx_biombo == 0 and letra_grupo == 'A' and len(grupos['A']) == 1:
                    continue
                
                # Buscar un país candidato que cumpla las reglas en este grupo
                candidato_valido = None
                for pais in equipos_disponibles:
                    if validar_reglas_fifa(grupos[letra_grupo], pais):
                        candidato_valido = pais
                        break
                
                if candidato_valido:
                    # Asignar metadata del grupo al objeto del país
                    idx_posicion = len(grupos[letra_grupo]) + 1
                    candidato_valido['grupo'] = letra_grupo
                    candidato_valido['idx_grupo'] = idx_posicion
                    
                    grupos[letra_grupo].append(candidato_valido)
                    equipos_disponibles.remove(candidato_valido)
                else:
                    # No hay países válidos sin romper las reglas de la FIFA -> Reintentar sorteo completo
                    sorteo_exitoso = False
                    break
            
            if not sorteo_exitoso:
                break
                
        if sorteo_exitoso:
            return grupos

    raise Exception("No se pudo generar una distribución válida de grupos tras varios intentos. Revisa los biombos.")


def guardar_grupos_en_db(db, grupos: Dict[str, List[Dict[str, Any]]]):
    """
    Persiste los datos de grupo e idx_grupo en la colección 'internacional' de MongoDB.
    """
    for letra_grupo, lista_paises in grupos.items():
        for pais in lista_paises:
            db['internacional'].update_one(
                {"id": pais['id']},
                {
                    "$set": {
                        "grupo": pais['grupo'],
                        "idx_grupo": pais['idx_grupo']
                    }
                }
            )
            

# funcion para asignar grupos de 16vos
def asignar_grupos_16vos(db: Database, mundial_id: Any) -> Dict[str, Any]:
    internacional_coll = db["internacional"]

    # 1. Obtener países según sus estados de clasificación para 16vos
    paises_cat_1 = list(internacional_coll.find({"estado": "CLASIFICADO_16VOS_1"}))    
    paises_cat_2 = list(internacional_coll.find({"estado": "CLASIFICADO_16VOS_2"}))
    paises_cat_3 = list(internacional_coll.find({"estado": "CLASIFICADO_16VOS_3"}))

    # Validaciones básicas de consistencia
    if len(paises_cat_1) != 12 or len(paises_cat_3) != 8:
        return {
            "exito": False,
            "mensaje": f"Estructura inválida. Se esperaban 12 en CAT_1 y 8 en CAT_3 (Actual: CAT_1={len(paises_cat_1)}, CAT_3={len(paises_cat_3)})."
        }
        
    # 2. Mezclar selecciones para el sorteo aleatorio de cruces
    random.shuffle(paises_cat_1)
    random.shuffle(paises_cat_2)
    random.shuffle(paises_cat_3)

    # 8 de CAT_1 van directo contra CAT_3; los 4 restantes se unen a CAT_2
    cat_1_para_cat_3 = paises_cat_1[:8]
    cat_1_sobrantes = paises_cat_1[8:]
    
    bolsa_segunda_llave = paises_cat_2 + cat_1_sobrantes
    random.shuffle(bolsa_segunda_llave)    

    total_partidos = len(cat_1_para_cat_3) + (len(bolsa_segunda_llave) // 2)
    
    # Nombres para cada llave/partido (Grupo A, Grupo B, ...)
    nombres_grupos = generar_nombres_grupos(total_partidos)
    
    operaciones_actualizacion = []
    resumen_enfrentamientos = {}
    grupo_idx = 0
    
    # HELPER: Función interna para emparejar evitando grupos previos idénticos
    def emparejar_sin_repetir_grupo(locales: List[dict], visitantes: List[dict]) -> List[tuple]:
        parejas = []
        visitantes_disponibles = visitantes.copy()

        for local in locales:
            grupo_previo_local = local.get("grupo")
            candidato_idx = None

            # Buscar un rival que no comparta el grupo de la fase anterior
            for idx, candidato in enumerate(visitantes_disponibles):
                if candidato.get("grupo") != grupo_previo_local:
                    candidato_idx = idx
                    break

            # Si no hay opción ideal, tomar el primero disponible
            if candidato_idx is None:
                candidato_idx = 0

            rival = visitantes_disponibles.pop(candidato_idx)
            parejas.append((local, rival))

        return parejas
    
    # SECCIÓN 3: Cruce Bloque 1 (8 equipos de CAT_1 vs 8 equipos de CAT_3)
    cruces_bloque_1 = emparejar_sin_repetir_grupo(cat_1_para_cat_3, paises_cat_3)

    for p1, p3 in cruces_bloque_1:
        grupo_nombre = nombres_grupos[grupo_idx]

        operaciones_actualizacion.extend([
            UpdateOne({"_id": p1["_id"]}, {"$set": {"grupo": grupo_nombre, "idx_grupo": 1}}),
            UpdateOne({"_id": p3["_id"]}, {"$set": {"grupo": grupo_nombre, "idx_grupo": 2}})
        ])

        resumen_enfrentamientos[grupo_nombre] = {
            "local": p1.get("nombre", str(p1["_id"])),
            "visitante": p3.get("nombre", str(p3["_id"])),
            "tipo": "CAT_1 vs CAT_3"
        }
        grupo_idx += 1

    # SECCIÓN 4: Cruce Bloque 2 (Mezcla de 4 sobrantes CAT_1 + CAT_2 entre sí)
    mitad = len(bolsa_segunda_llave) // 2
    locales_b2 = bolsa_segunda_llave[:mitad]
    visitantes_b2 = bolsa_segunda_llave[mitad:]

    cruces_bloque_2 = emparejar_sin_repetir_grupo(locales_b2, visitantes_b2)
    
    for p_a, p_b in cruces_bloque_2:
        grupo_nombre = nombres_grupos[grupo_idx]

        operaciones_actualizacion.extend([
            UpdateOne({"_id": p_a["_id"]}, {"$set": {"grupo": grupo_nombre, "idx_grupo": 1}}),
            UpdateOne({"_id": p_b["_id"]}, {"$set": {"grupo": grupo_nombre, "idx_grupo": 2}})
        ])

        resumen_enfrentamientos[grupo_nombre] = {
            "local": p_a.get("nombre", str(p_a["_id"])),
            "visitante": p_b.get("nombre", str(p_b["_id"])),
            "tipo": "CAT_2 / CAT_1_REMANENTE"
        }
        grupo_idx += 1

    # Ejecución masiva en MongoDB
    if operaciones_actualizacion:
        resultado = internacional_coll.bulk_write(operaciones_actualizacion)
        modificados = resultado.modified_count
    else:
        modificados = 0

    return {
        "exito": True,
        "registros_actualizados": modificados,
        "total_partidos": total_partidos,
        "enfrentamientos": resumen_enfrentamientos,
        "mensaje": "Emparejamientos de 16vos con restricción de grupo previo completados."
    }

# Funcion para 8vos de final
# def asignar_grupos_8vos_(db: Database, mundial_id: Any) -> Dict[str, Any]:
#     internacional_coll = db["internacional"]

#     # Definit de pares de llaves para octavos de final
#     pares_llaves = [
#         ("A", "B"), ("C", "D"), ("E", "F"), ("G", "H"),
#         ("I", "J"), ("K", "L"), ("M", "N"), ("O", "P")
#     ]

#     # 1. Obtener los países clasificados para 8vos
#     # Se busca por el patrón 'CLASIFICADO_8VOS_'
#     paises_8vos = list(internacional_coll.find({"estado": {"$regex": "^CLASIFICADO_8VOS_"}}))

#     # Map auxiliar para acceso rápido por estado (ej. "CLASIFICADO_8VOS_A": doc)
#     mapa_paises = {pais["estado"]: pais for pais in paises_8vos}

#     if len(paises_8vos) != 16:
#         return {
#             "exito": False,
#             "mensaje": f"Se esperaban 16 equipos para 8vos de final, pero se encontraron {len(paises_8vos)}."
#         }

#     # Nombres para cada partido/llave (Grupo A, Grupo B, ..., Grupo H)
#     total_partidos = len(pares_llaves)
#     nombres_grupos = generar_nombres_grupos(total_partidos)

#     operaciones_actualizacion = []
#     resumen_enfrentamientos = {}

#     # 2. Iterar sobre las parejas fijas de octavos
#     for idx, (letra_1, letra_2) in enumerate(pares_llaves):
#         estado_1 = f"CLASIFICADO_8VOS_{letra_1}"
#         estado_2 = f"CLASIFICADO_8VOS_{letra_2}"

#         pais_1 = mapa_paises.get(estado_1)
#         pais_2 = mapa_paises.get(estado_2)

#         # Validar que ambas selecciones existan para el cruce
#         if not pais_1 or not pais_2:
#             return {
#                 "exito": False,
#                 "mensaje": f"Falta alguna de las selecciones para el cruce {estado_1} vs {estado_2}."
#             }

#         grupo_nombre = nombres_grupos[idx]

#         # Sorteo de condición de local/visitante dentro del partido
#         pareja = [pais_1, pais_2]
#         random.shuffle(pareja)
#         p_local, p_visitante = pareja[0], pareja[1]

#         # Preparar actualizaciones para MongoDB
#         operaciones_actualizacion.extend([
#             UpdateOne(
#                 {"_id": p_local["_id"]},
#                 {"$set": {"grupo": grupo_nombre, "idx_grupo": 1}}
#             ),
#             UpdateOne(
#                 {"_id": p_visitante["_id"]},
#                 {"$set": {"grupo": grupo_nombre, "idx_grupo": 2}}
#             )
#         ])

#         resumen_enfrentamientos[grupo_nombre] = {
#             "local": p_local.get("nombre", str(p_local["_id"])),
#             "visitante": p_visitante.get("nombre", str(p_visitante["_id"])),
#             "cruce": f"{letra_1} vs {letra_2}"
#         }

#     # 3. Ejecutar actualización masiva en MongoDB
#     if operaciones_actualizacion:
#         resultado = internacional_coll.bulk_write(operaciones_actualizacion)
#         modificados = resultado.modified_count
#     else:
#         modificados = 0

#     return {
#         "exito": True,
#         "registros_actualizados": modificados,
#         "total_partidos": total_partidos,
#         "enfrentamientos": resumen_enfrentamientos,
#         "mensaje": "Emparejamientos de octavos de final asignados exitosamente."
#     }



def _procesar_cruces_fase(
    db: Database,
    mundial_id: Any,
    prefijo_estado: str,
    pares_llaves: List[Tuple[str, str]],
    nombre_fase: str
) -> Dict[str, Any]:
    """
    Función interna genérica para procesar emparejamientos directos por parejas de letras.
    """
    internacional_coll = db["internacional"]

    # 1. Obtener los países clasificados para la fase correspondiente
    paises = list(internacional_coll.find({"estado": {"$regex": f"^{prefijo_estado}_"}}))

    mapa_paises = {pais["estado"]: pais for pais in paises}
    total_esperado = len(pares_llaves) * 2

    if len(paises) != total_esperado:
        return {
            "exito": False,
            "mensaje": f"Se esperaban {total_esperado} equipos para {nombre_fase}, pero se encontraron {len(paises)}."
        }

    # Asignar nombres de grupos (Grupo A, Grupo B, etc.)
    total_partidos = len(pares_llaves)
    nombres_grupos = generar_nombres_grupos(total_partidos)

    operaciones_actualizacion = []
    resumen_enfrentamientos = {}

    # 2. Iterar sobre las parejas de la fase
    for idx, (letra_1, letra_2) in enumerate(pares_llaves):
        estado_1 = f"{prefijo_estado}_{letra_1}"
        estado_2 = f"{prefijo_estado}_{letra_2}"

        pais_1 = mapa_paises.get(estado_1)
        pais_2 = mapa_paises.get(estado_2)

        if not pais_1 or not pais_2:
            return {
                "exito": False,
                "mensaje": f"Falta alguna de las selecciones para el cruce {estado_1} vs {estado_2}."
            }

        grupo_nombre = nombres_grupos[idx]

        # Sorteo de localía (idx_grupo: 1 o 2)
        pareja = [pais_1, pais_2]
        random.shuffle(pareja)
        p_local, p_visitante = pareja[0], pareja[1]

        operaciones_actualizacion.extend([
            UpdateOne(
                {"_id": p_local["_id"]},
                {"$set": {"grupo": grupo_nombre, "idx_grupo": 1}}
            ),
            UpdateOne(
                {"_id": p_visitante["_id"]},
                {"$set": {"grupo": grupo_nombre, "idx_grupo": 2}}
            )
        ])

        resumen_enfrentamientos[grupo_nombre] = {
            "local": p_local.get("nombre", str(p_local["_id"])),
            "visitante": p_visitante.get("nombre", str(p_visitante["_id"])),
            "cruce": f"{letra_1} vs {letra_2}"
        }

    # 3. Guardar en MongoDB
    modificados = 0
    if operaciones_actualizacion:
        resultado = internacional_coll.bulk_write(operaciones_actualizacion)
        modificados = resultado.modified_count

    return {
        "exito": True,
        "registros_actualizados": modificados,
        "total_partidos": total_partidos,
        "enfrentamientos": resumen_enfrentamientos,
        "mensaje": f"Emparejamientos de {nombre_fase} asignados exitosamente."
    }

# ==========================================
# FUNCIONES ESPECÍFICAS DE CADA FASE
# ==========================================

def asignar_grupos_8vos(db: Database, mundial_id: Any) -> Dict[str, Any]:
    pares = [
        ("A", "B"), ("C", "D"), ("E", "F"), ("G", "H"),
        ("I", "J"), ("K", "L"), ("M", "N"), ("O", "P")
    ]
    return _procesar_cruces_fase(db, mundial_id, "CLASIFICADO_8VOS", pares, "Octavos de Final")

def asignar_grupos_4tos(db: Database, mundial_id: Any) -> Dict[str, Any]:
    pares = [("A", "B"), ("C", "D"), ("E", "F"), ("G", "H")]
    return _procesar_cruces_fase(db, mundial_id, "CLASIFICADO_4TOS", pares, "Cuartos de Final")


def asignar_grupos_semis(db: Database, mundial_id: Any) -> Dict[str, Any]:
    pares = [("A", "B"), ("C", "D")]
    return _procesar_cruces_fase(db, mundial_id, "CLASIFICADO_SEMIS", pares, "Semifinales")


def asignar_grupos_3er_lugar(db: Database, mundial_id: Any) -> Dict[str, Any]:
    pares = [("A", "B")]
    return _procesar_cruces_fase(db, mundial_id, "CLASIFICADO_3ER", pares, "Tercer Lugar")


def asignar_grupos_final(db: Database, mundial_id: Any) -> Dict[str, Any]:
    pares = [("A", "B")]
    return _procesar_cruces_fase(db, mundial_id, "CLASIFICADO_FINAL", pares, "Gran Final")