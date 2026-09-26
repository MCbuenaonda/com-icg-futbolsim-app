"""
Script de solo lectura para inspeccionar las colecciones de Mongo y el
esquema (campos + tipos) de un documento de muestra por colección.
Correr localmente con: python3 ver_esquema.py
"""
import certifi
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI


def describir_valor(valor, profundidad=0):
    sangria = "  " * profundidad
    if isinstance(valor, dict):
        lineas = []
        for clave, sub_valor in valor.items():
            lineas.append(f"{sangria}- {clave}: {tipo_legible(sub_valor)}")
            if isinstance(sub_valor, (dict, list)):
                lineas.append(describir_valor(sub_valor, profundidad + 1))
        return "\n".join(lineas)
    if isinstance(valor, list):
        if not valor:
            return f"{sangria}  (lista vacía)"
        return f"{sangria}  [0] -> {tipo_legible(valor[0])}\n" + describir_valor(valor[0], profundidad + 1)
    return ""


def tipo_legible(valor):
    return type(valor).__name__


def main():
    client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
    db = client.get_database("mundial")

    nombres_colecciones = sorted(db.list_collection_names())
    print(f"Base de datos: mundial ({len(nombres_colecciones)} colecciones)\n")

    for nombre in nombres_colecciones:
        coll = db[nombre]
        total = coll.estimated_document_count()
        muestra = coll.find_one()

        print("=" * 70)
        print(f"Colección: {nombre}  (~{total} documentos)")
        print("=" * 70)

        if muestra is None:
            print("  (colección vacía)")
        else:
            for campo, valor in muestra.items():
                print(f"- {campo}: {tipo_legible(valor)}")
                if isinstance(valor, (dict, list)):
                    detalle = describir_valor(valor, 1)
                    if detalle:
                        print(detalle)
        print()


if __name__ == "__main__":
    main()
