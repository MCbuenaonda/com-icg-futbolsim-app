# leer la coleccion de mongo Jugadores, por cada jugador obtener su pais, buscar el pais en la coleccion de paises y actualizar el campo de pais_id en cada jugador
import certifi
from pymongo.mongo_client import MongoClient
from bson.objectid import ObjectId

MONGODB_URI = 'mongodb+srv://ingcarloscerati_db_user:C4rl056C@cluster0.yleznra.mongodb.net/'
#paises_cambio = ["Bahréin","Bangladesh","Brunéi Darussalam","EE UU","Guinea Bissáu","Kazajstán","Mali","Macedonia","Qatar","Suazilandia","Taipei","Holanda","Rumanía"]
paises_cambio = ["Bahrein","Banglades","Mali"]

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

collection_jugadores = db.get_collection('jugadores')
collection_paises = db.get_collection('paises')
collection_ciudades = db.get_collection('ciudades')

ciudades = collection_ciudades.find()
#jugadores = collection_jugadores.find()

idx = 1

for ciudad in ciudades:
    pais = ciudad['pais']
    _pais = collection_paises.find_one({"nombre": pais})
    
    if _pais:
        pais_id = _pais['id']
        if pais_id != ciudad['pais_id']:
            print(f"✅ {idx} - Actualizando ciudad [{ciudad['nombre']}] -- {ciudad['pais_id']} por {pais_id}")
            collection_ciudades.update_one({"_id": ObjectId(ciudad["_id"])}, {"$set": {"pais_id": pais_id}})
    else: 
        print(f"❌ {idx} - No se encontró el país [{pais}] para la ciudad [{ciudad['nombre']}]")       
        # if pais in paises_cambio:
        #     if pais == "Bahrein":
        #         pais = "Baréin"
        #     elif pais == "Banglades":
        #         pais = "Bangladés"
        #     elif pais == "Mali":
        #         pais = "Malí"
        
                        
        #     print(f"❌ {idx} - Actualizando el país [{pais}] para el ciudad [{ciudad['nombre']}]")    
        #     collection_ciudades.update_one({"_id": ObjectId(ciudad["_id"])}, {"$set": {"pais": pais}})
    
    idx += 1



# Bahréin - Baréin
# Bangladesh - Bangladés
# Brunéi Darussalam - Brunéi
# EE UU - Estados Unidos
# Guinea Bissáu - Guinea-Bisáu
# Kazajstán - Kazajistán
# Mali - Malí
# Macedonia - Macedonia del Norte
# Qatar - Catar
# Suazilandia - Esuatini
# Taipei - Taiwán
# Holanda - Países Bajos