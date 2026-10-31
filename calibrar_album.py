"""
Monte Carlo del álbum (SOLO LECTURA): cuántos sobres hacen falta para completar la primera página de país y cuánto del
álbum se llena con N sobres, según la cantidad de estampas por sobre, la probabilidad de cada categoría y el canje de
repetidas (COSTO_CANJE). Tamaños del catálogo desde la base real; las categorías nuevas (televisoras, marcas y sus
personajes) se pueden sumar con --nuevas para ver cómo cambiaría el reparto.

    python calibrar_album.py [--k 10] [--sims 12] [--nuevas] [--pesos JUGADOR=.4,CIUDAD=.2,...]
"""
import argparse
import random

from services import album_service as A

# lo que lleva una página de país (todos los casilleros cuentan)
PAGINA = {"JUGADOR": 22, "CIUDAD": 20, "PAIS": 1, "EQUIPO": 3, "LEYENDA": 11, "TECNICO": 5}
NUEVAS = {"LOGO": 1188, "PERSONAJE": 2580, "DUENO": 1188}   # logos de cadenas y marcas, comentaristas, dueños de cadenas y de marcas
COSTO_NUEVAS = {"LOGO": 3, "PERSONAJE": 2, "DUENO": 5}


def tamanos():
    n = {}
    for tipo, col in A.COLECCION_POR_TIPO.items():
        n[tipo] = A.db[col].count_documents({"id": {"$exists": True}, **A.FILTRO_SORTEO_POR_TIPO.get(tipo, {})})
    n["ARBITRO"] = n.get("ARBITRO", 1050)
    return n


def simular(pesos, N, costo, k, sobres_max, rng):
    tipos = list(pesos)
    w = [pesos[t] for t in tipos]
    tengo = {t: 0 for t in tipos}
    falta_pagina = {t: PAGINA.get(t, 0) for t in tipos}
    rep = 0
    primera = None
    llenado = {}
    total = sum(N.values())
    for s in range(1, sobres_max + 1):
        for t in rng.choices(tipos, w, k=k):
            if rng.random() < (N[t] - tengo[t]) / N[t]:
                tengo[t] += 1
                if falta_pagina[t] and rng.random() < falta_pagina[t] / max(1, N[t] - tengo[t] + 1):
                    falta_pagina[t] -= 1
            else:
                rep += 1
        # canje: gasta las repetidas en lo que falta de la página (lo más caro primero) y, si ya está, en lo que falte del álbum
        for objetivo in ("pagina", "album"):
            while True:
                opciones = [t for t in tipos if (falta_pagina[t] > 0 if objetivo == "pagina" else tengo[t] < N[t]) and costo[t] <= rep]
                if not opciones:
                    break
                t = max(opciones, key=lambda x: costo[x])
                rep -= costo[t]
                if objetivo == "pagina":
                    falta_pagina[t] -= 1
                tengo[t] = min(N[t], tengo[t] + 1)
        if primera is None and not any(falta_pagina.values()):
            primera = s
        if s in (500, 1000, 2000, 4000):
            llenado[s] = sum(tengo.values()) / total
    return primera or sobres_max, llenado


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--sims", type=int, default=12)
    ap.add_argument("--nuevas", action="store_true")
    ap.add_argument("--pesos", default="")
    a = ap.parse_args()
    N = tamanos()
    pesos = dict(A.PESOS_TIPO_ESTAMPA)
    costo = dict(A.COSTO_CANJE)
    if a.nuevas:
        N.update(NUEVAS)
        costo.update(COSTO_NUEVAS)
        pesos.update({"LOGO": 0.07, "PERSONAJE": 0.11, "DUENO": 0.025})
    for par in filter(None, a.pesos.split(",")):
        k, v = par.split("=")
        pesos[k] = float(v)
    suma = sum(pesos.values())
    pesos = {t: p / suma for t, p in pesos.items()}
    print("catálogo:", N, "total", sum(N.values()))
    print("pesos:", {t: round(p, 3) for t, p in pesos.items()})
    rng = random.Random(7)
    res = [simular(pesos, N, costo, a.k, 4000, rng) for _ in range(a.sims)]
    pri = sorted(r[0] for r in res)
    print(f"k={a.k}: primera página: mediana {pri[len(pri) // 2]} sobres (mín {pri[0]}, máx {pri[-1]})")
    for s in (500, 1000, 2000, 4000):
        v = [r[1][s] for r in res if s in r[1]]
        print(f"  a los {s} sobres: {100 * sum(v) / len(v):.1f}% del álbum")


if __name__ == "__main__":
    main()
