"""
Corrige los nombres de las imágenes del bucket que quedaron con tildes/ñ "descompuestas" (Unicode NFD).

Al subir archivos desde macOS, "ú" puede quedar guardada como "u" + acento suelto: el nombre se ve
igual, pero la URL es otra y la app (que pide el nombre de 'paises.nombre', en NFC) recibe 404.
Este script busca esos nombres en las carpetas de imágenes de país y los renombra a NFC, con el mismo
Cache-Control que el resto del bucket. Correrlo después de subir imágenes nuevas.

    python normalizar_imagenes_bucket.py --muestra    # solo lista lo que habría que renombrar
    python normalizar_imagenes_bucket.py --aplicar    # renombra (gcloud storage mv)
"""
import subprocess
import sys
import unicodedata

BUCKET = "gs://com-icg-mundial"
CARPETAS = ["bandera", "escudo", "icono", "jersey"]
CACHE = "public, max-age=604800"


def _nombres_nfd():
    for carpeta in CARPETAS:
        salida = subprocess.run(["gcloud", "storage", "ls", f"{BUCKET}/{carpeta}/"], capture_output=True, text=True, check=True).stdout
        for linea in salida.splitlines():
            origen = linea.strip()
            destino = unicodedata.normalize("NFC", origen)
            if origen and origen != destino:
                yield origen, destino


def main(aplicar: bool):
    pendientes = list(_nombres_nfd())
    if not pendientes:
        print("Todos los nombres ya están bien (NFC).")
        return
    for origen, destino in pendientes:
        print(("Renombrando " if aplicar else "Hay que renombrar ") + destino.rsplit("/", 2)[-2] + "/" + destino.rsplit("/", 1)[-1])
        if aplicar:
            subprocess.run(["gcloud", "storage", "mv", origen, destino], check=True, capture_output=True)
            subprocess.run(["gcloud", "storage", "objects", "update", destino, f"--cache-control={CACHE}"], check=True, capture_output=True)
    if not aplicar:
        print(f"{len(pendientes)} archivo(s). Corré con --aplicar para renombrarlos.")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo not in ("--muestra", "--aplicar"):
        print(__doc__)
    else:
        main(aplicar=modo == "--aplicar")
