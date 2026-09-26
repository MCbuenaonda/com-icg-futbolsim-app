import certifi
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI
from services.clasificacion_service import procesar_clasificacion_fase, procesar_clasificacion_fase_1, copiar_estado_y_estadisticas_a_paises, procesar_clasificacion_fase_2, procesar_clasificacion_fase_3, procesar_clasificacion_fase_4, procesar_clasificacion_fase_5, procesar_clasificacion_fase_6, procesar_clasificacion_fase_7
from services.mundial_service import crear_siguiente_fase

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

mundial = db["mundiales"].find_one({"activo": True})
mundial_id = str(mundial["_id"])

for i in range(8):
    confederacion_id = i + 1
    num_fases = 1
    
    if confederacion_id == 1:
        num_fases = 2
    elif confederacion_id in [3,4]:
        num_fases = 3
    elif confederacion_id == 5:
        num_fases = 4
    elif confederacion_id == 6:
        num_fases = 5
    elif confederacion_id == 7:
        num_fases = 1
    elif confederacion_id == 8:
        num_fases = 7

    for j in range(num_fases):
        if confederacion_id == 7:
            j = 5
        
        if confederacion_id == 8:
            fase_id = j + 7    
        else:
            fase_id = j + 1    
        
        siguiente_fase = fase_id + 1
        
        if fase_id == 1:
            procesar_clasificacion_fase_1(db, confederacion_id)
        elif fase_id == 2:
            procesar_clasificacion_fase_2(db, confederacion_id)
        elif fase_id == 3:
            procesar_clasificacion_fase_3(db, confederacion_id)
        elif fase_id == 4:
            procesar_clasificacion_fase_4(db, confederacion_id)
        elif fase_id == 5:
            procesar_clasificacion_fase_5(db, confederacion_id)
        elif fase_id == 6:
            procesar_clasificacion_fase_6(db, confederacion_id)
        elif fase_id == 7:
            procesar_clasificacion_fase_7(db, confederacion_id)
        elif fase_id >= 8:
            procesar_clasificacion_fase(db, confederacion_id, fase_id)
        
        copiar_estado_y_estadisticas_a_paises(db, fase_id, confederacion_id)
        crear_siguiente_fase(siguiente_fase, confederacion_id, mundial_id)





