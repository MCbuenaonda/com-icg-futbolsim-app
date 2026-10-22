"""
Genera el póster y la mascota oficiales de un Mundial que todavía no los tiene (los nuevos ya se generan solos al
crearse, ver mundial_service.crear_nuevo_mundial). Motor: services/arte_mundial/, servicio: services/arte_mundial_service.py.

    python generar_arte_mundial.py --mundial-activo            # el Mundial en curso (si no tiene arte)
    python generar_arte_mundial.py --todos                     # todos los Mundiales sin arte (archivo histórico)
    python generar_arte_mundial.py --anio 1900 --forzar        # vuelve a tirar (cambia el arte de esa edición)

Para elegir entre propuestas está el panel /admin/arte-mundial.
"""
import sys

from services import arte_mundial_service as AS


def main(args):
    forzar = "--forzar" in args
    if "--mundial-activo" in args:
        filtro = {"activo": True}
    elif "--anio" in args:
        filtro = {"anio": int(args[args.index("--anio") + 1])}
    elif "--todos" in args:
        filtro = {}
    else:
        print(__doc__)
        return
    for m in AS.db["mundiales"].find(filtro):
        arte = AS.generar_para(m, forzar=forzar)
        datos = AS.arte_de(m["anio"]) if arte else None
        print(f"Mundial {m['anio']}: " + (f"póster {datos['poster']['fondo']}/{datos['poster']['icono']}/{datos['poster']['grilla']} · "
                                          f"mascota {datos['mascota_nombre']} ({datos['mascota_que']})" if datos else "sin arte"))


if __name__ == "__main__":
    main(sys.argv[1:])
