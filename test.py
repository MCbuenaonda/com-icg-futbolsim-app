import certifi
from google.api_core.exceptions import GoogleAPIError
from pymongo.mongo_client import MongoClient
import json
MONGODB_URI = 'mongodb+srv://ingcarloscerati_db_user:C4rl056C@cluster0.yleznra.mongodb.net/'

collection_path = "collections/paises.json"
client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

def get_paises():
    try:        
        collection = db['paises']
        # Ejecutar la consulta
        paises = list(collection.find())        
        return paises
    except GoogleAPIError as e:
        print(e)
    except Exception as e:
        print(e)
        
def create_fill(pais, bandera):
    collection = db['paises']
    
    # 2. Filtro para encontrar el documento
    filtro = {"nombre": pais}

    # 3. Operador $set con el nuevo campo y su valor
    nuevo_campo = {"$set": {"bandera": bandera}}

    # 4. Actualizar el documento
    resultado = collection.update_one(filtro, nuevo_campo)

    print(f"Documentos modificados: {resultado.modified_count}")


paises = get_paises()

with open(collection_path, "r", encoding="utf-8") as file:
        paises_fifa = json.load(file)

count = 1
for pais in paises:
    if "bandera" not in pais:
        # Busca el primer elemento que coincida
        resultado = next((item for item in paises_fifa if item["nombre"] == pais["nombre"]), None)        
        if resultado:
            create_fill(pais["nombre"], resultado["bandera"])
            print(f"✅ {resultado}")
        else:
            print(f"❌ {pais["nombre"]} no encontrado")
        
        count += 1
        