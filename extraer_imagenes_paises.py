"""
HERRAMIENTA HISTÓRICA: la app ya NO usa estas imágenes locales. El origen vigente es el bucket
gs://com-icg-mundial (<tipo>/<paises.nombre>.png, ver services/imagenes_pais_service.py); este
script queda solo como referencia: el dump 'data_base64' y la copia local static/img/paises se
borraron (2026-10), así que para volver a correrlo hay que conseguir de nuevo el dump SQL.

Extrae las imágenes de países del dump SQL 'data_base64' (tabla `images`: id, pais_id,
confederacion_id, bandera, jersey, icono, escudo -- cada imagen como data URI en base64) y las
guarda como archivos, por el 'id' de la colección 'paises' de Mongo (ver DUMP_A_PAIS_ID), en:

    static/img/paises/<pais_id>/bandera.png
    static/img/paises/<pais_id>/jersey.png
    static/img/paises/<pais_id>/icono.png
    static/img/paises/<pais_id>/escudo.png

Quedan servidas por la app en /static/img/paises/<pais_id>/<tipo>.png.

Uso:  python extraer_imagenes_paises.py [archivo_sql] [carpeta_destino]
      (por defecto: data_base64 y static/img/paises)

Idempotente: se puede volver a correr, sobrescribe los archivos. No toca la base de datos.

Ojo con el dump: 180 escudos vienen declarados como 'image/png' pero en realidad son GIF. El
formato se detecta por los primeros bytes (no por lo que dice el data URI) y los GIF se convierten
a PNG con 'sips' (viene con macOS), para que cada país tenga siempre los mismos 4 nombres de
archivo. Si 'sips' no está disponible, se guardan como .gif y se avisa.
"""
import base64
import binascii
import os
import re
import shutil
import subprocess
import sys

COLUMNAS_IMAGEN = ["bandera", "jersey", "icono", "escudo"]
EXTENSIONES = {"image/png": "png", "image/jpeg": "jpg", "image/jpg": "jpg", "image/gif": "gif",
               "image/webp": "webp", "image/svg+xml": "svg"}
# Firma de los primeros bytes de cada formato, para validar que lo decodificado sea una imagen real
FIRMAS = {"png": b"\x89PNG\r\n\x1a\n", "jpg": b"\xff\xd8\xff", "gif": b"GIF8", "webp": b"RIFF"}

# El dump NO usa los ids de Mongo: su 'pais_id' es el orden alfabético (en español, con otros nombres)
# de la base de origen. Esta tabla lleva cada pais_id del dump al 'paises.id' de Mongo; se armó
# emparejando orden alfabético + confederación y se verificó a ojo bandera por bandera (211/211).
DUMP_A_PAIS_ID = {
    1: 155, 2: 11, 3: 12, 4: 13, 5: 101, 6: 66, 7: 67, 8: 156, 9: 102, 10: 1, 11: 14, 12: 68,
    13: 157, 14: 15, 15: 16, 16: 69, 17: 158, 18: 159, 19: 70, 20: 17, 21: 71, 22: 103, 23: 72, 24: 18,
    25: 2, 26: 19, 27: 104, 28: 3, 29: 160, 30: 20, 31: 105, 32: 106, 33: 161, 34: 107, 35: 162, 36: 108,
    37: 73, 38: 109, 39: 4, 40: 164, 41: 21, 42: 5, 43: 110, 44: 111, 45: 165, 46: 166, 47: 112, 48: 74,
    49: 22, 50: 75, 51: 76, 52: 23, 53: 77, 54: 6, 55: 79, 56: 113, 57: 78, 58: 167, 59: 114, 60: 24,
    61: 25, 62: 26, 63: 27, 64: 28, 65: 116, 66: 168, 67: 29, 68: 201, 69: 30, 70: 117, 71: 31, 72: 118,
    73: 32, 74: 119, 75: 33, 76: 80, 77: 34, 78: 169, 79: 81, 80: 120, 81: 122, 82: 121, 83: 82, 84: 83,
    85: 84, 86: 170, 87: 35, 88: 171, 89: 172, 90: 36, 91: 173, 92: 174, 93: 37, 94: 38, 95: 39, 96: 85,
    97: 202, 98: 40, 99: 203, 100: 87, 101: 88, 102: 41, 103: 42, 104: 89, 105: 175, 106: 176, 107: 43, 108: 123,
    109: 177, 110: 44, 111: 178, 112: 179, 113: 124, 114: 45, 115: 180, 116: 125, 117: 126, 118: 46, 119: 47, 120: 48,
    121: 181, 122: 49, 123: 127, 124: 182, 125: 128, 126: 183, 127: 129, 128: 50, 129: 130, 130: 131, 131: 132, 132: 90,
    133: 51, 134: 184, 135: 52, 136: 91, 137: 133, 138: 185, 139: 134, 140: 186, 141: 92, 142: 135, 143: 136, 144: 53,
    145: 204, 146: 205, 147: 187, 148: 54, 149: 188, 150: 189, 151: 93, 152: 206, 153: 7, 154: 8, 155: 55, 156: 56,
    157: 94, 158: 163, 159: 138, 160: 137, 161: 57, 162: 95, 163: 139, 164: 58, 165: 59, 166: 207, 167: 208, 168: 96,
    169: 60, 170: 97, 171: 98, 172: 140, 173: 141, 174: 61, 175: 142, 176: 143, 177: 190, 178: 191, 179: 144, 180: 192,
    181: 115, 182: 145, 183: 146, 184: 147, 185: 62, 186: 63, 187: 99, 188: 209, 189: 193, 190: 194, 191: 148, 192: 195,
    193: 196, 194: 149, 195: 210, 196: 100, 197: 150, 198: 86, 199: 197, 200: 64, 201: 65, 202: 151, 203: 9, 204: 198,
    205: 211, 206: 10, 207: 199, 208: 200, 209: 152, 210: 153, 211: 154,
}

_VALOR = r"(NULL|'(?:[^'\\]|\\.)*')"
FILA = re.compile(
    r"\(\s*(\d+)\s*,\s*(\d+|NULL)\s*,\s*(\d+|NULL)\s*,\s*" + r"\s*,\s*".join([_VALOR] * 4) + r"\s*\)"
)
DATA_URI = re.compile(r"^data:([\w/+.-]+);base64,(.*)$", re.S)


def extraer(ruta_sql: str = "data_base64", destino: str = os.path.join("static", "img", "paises")) -> dict:
    with open(ruta_sql, encoding="utf-8") as f:
        contenido = f.read()

    resumen = {"filas": 0, "guardadas": 0, "convertidas": 0, "vacias": 0, "errores": []}
    for _id, pais_id, _confederacion_id, *imagenes in FILA.findall(contenido):
        resumen["filas"] += 1
        pais_id_mongo = DUMP_A_PAIS_ID.get(int(pais_id)) if pais_id != "NULL" else None
        if pais_id_mongo is None:
            resumen["errores"].append(f"fila id={_id}: pais_id {pais_id} sin equivalencia en Mongo")
            continue
        pais_id = str(pais_id_mongo)
        carpeta = os.path.join(destino, pais_id)
        os.makedirs(carpeta, exist_ok=True)
        for columna, valor in zip(COLUMNAS_IMAGEN, imagenes):
            if valor in ("NULL", "''"):
                resumen["vacias"] += 1
                continue
            match = DATA_URI.match(valor[1:-1])  # sin las comillas simples del SQL
            if not match:
                resumen["errores"].append(f"pais {pais_id} / {columna}: no es un data URI")
                continue
            tipo, datos_b64 = match.groups()
            extension = EXTENSIONES.get(tipo)
            if not extension:
                resumen["errores"].append(f"pais {pais_id} / {columna}: tipo no soportado ({tipo})")
                continue
            try:
                datos = base64.b64decode(datos_b64, validate=True)
            except (binascii.Error, ValueError) as e:
                resumen["errores"].append(f"pais {pais_id} / {columna}: base64 inválido ({e})")
                continue
            # Formato REAL según los primeros bytes (el dump trae GIFs etiquetados como PNG)
            real = next((ext for ext, firma in FIRMAS.items() if datos.startswith(firma)), None)
            if real is None and extension != "svg":
                resumen["errores"].append(f"pais {pais_id} / {columna}: el contenido no es una imagen reconocible")
                continue
            extension = real or extension
            ruta = os.path.join(carpeta, f"{columna}.{extension}")
            with open(ruta, "wb") as salida:
                salida.write(datos)
            if extension != "png" and _convertir_a_png(ruta):
                resumen["convertidas"] += 1
            elif extension != "png":
                resumen["errores"].append(f"pais {pais_id} / {columna}: guardada como .{extension} (no se pudo convertir a PNG)")
            resumen["guardadas"] += 1
    return resumen


def _convertir_a_png(ruta: str) -> bool:
    """Convierte 'ruta' a PNG con 'sips' (macOS) y borra el original. False si no se pudo."""
    if not shutil.which("sips"):
        return False
    ruta_png = os.path.splitext(ruta)[0] + ".png"
    resultado = subprocess.run(["sips", "-s", "format", "png", ruta, "--out", ruta_png], capture_output=True)
    if resultado.returncode != 0 or not os.path.exists(ruta_png):
        return False
    os.remove(ruta)
    return True


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "data_base64"
    carpeta_destino = sys.argv[2] if len(sys.argv) > 2 else os.path.join("static", "img", "paises")
    r = extraer(ruta, carpeta_destino)
    print(f"Filas: {r['filas']} | imágenes guardadas: {r['guardadas']} (convertidas a PNG: {r['convertidas']}) | vacías: {r['vacias']} | errores: {len(r['errores'])}")
    for error in r["errores"]:
        print("  ⚠️ ", error)
    print(f"Destino: {os.path.abspath(carpeta_destino)}")
