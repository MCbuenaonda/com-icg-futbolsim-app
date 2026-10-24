"""
Escribe la crónica (services/cronica_service.py) de los partidos jugados que no la tienen o la tienen de una versión
anterior. No hace falta para que funcione (se escribe sola al abrir cada partido), pero así el feed del inicio y
todos los resúmenes ya la muestran. No toca los textos viejos (resultado.opinion / texto_narrativo).

    python generar_cronicas.py              # los que faltan o están desactualizados
    python generar_cronicas.py --forzar     # todos (vuelve a escribirlas)
    python generar_cronicas.py --muestra 5  # imprime 5 crónicas, no escribe
"""
import sys

from services import cronica_service as CS


def main(args):
    if "--muestra" in args:
        n = int(args[args.index("--muestra") + 1]) if len(args) > args.index("--muestra") + 1 else 5
        for j in CS.db["juegos"].find({"estado": "finalizado"}).limit(n):
            c = CS.generar(j)
            print(f"\n## {c['titular']}\n" + "\n".join(c["parrafos"]) + f"\nPOST: {c['post']}")
        return
    filtro = {"estado": "finalizado", "resultado": {"$exists": True}}
    if "--forzar" not in args:
        filtro["$or"] = [{"resultado.cronica": {"$exists": False}}, {"resultado.cronica": None},
                         {"resultado.cronica.version": {"$ne": CS.VERSION}}]
    hechos = 0
    for j in CS.db["juegos"].find(filtro):
        if "--forzar" in args and j.get("resultado", {}).get("cronica"):
            j["resultado"]["cronica"] = None
            CS.db["juegos"].update_one({"_id": j["_id"]}, {"$set": {"resultado.cronica": None}})
        if CS.asegurar_cronica(j):
            hechos += 1
    print(f"Crónicas escritas: {hechos}")


if __name__ == "__main__":
    main(sys.argv[1:])
