"""
Simula (SOLO LECTURA, no escribe nada) cuántas crisis de imagen deportivas habría salido con los partidos ya jugados: recorre el torneo en rondas de PARTIDOS_RONDA partidos y
aplica los mismos candidatos y sorteos de services/escandalos_deportivos_service.py. No conoce la presión histórica de los DT (solo goleadas), así que subestima un poco a los DT.

  python calibrar_escandalos_deportivos.py [rondas_max]
"""
import collections
import random
import sys

from config import escandalos as CE


def main(rondas_max: int = 200):
    from services import escandalos as E
    from services import escandalos_deportivos_service as S
    db = S.db
    juegos = list(db["juegos"].find({"estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}},
                                    {"equipo_local.id": 1, "equipo_local.nombre": 1, "equipo_visitante.id": 1, "equipo_visitante.nombre": 1, "resultado.goles_local": 1,
                                     "resultado.goles_visitante": 1, "resultado.dt": 1, "resultado.eventos.tipo": 1, "resultado.eventos.equipo": 1, "resultado.eventos.jugadores": 1})
                  .sort([("fecha", 1), ("hora", 1)]))
    n = CE.PARTIDOS_RONDA
    por_tipo, por_motivo, por_sev, ejemplos = collections.Counter(), collections.Counter(), collections.Counter(), {}
    en_crisis = {}
    rondas = 0
    for i in range(n, len(juegos) + 1, n):
        if rondas >= rondas_max:
            break
        rondas += 1
        ventana = juegos[max(0, i - n):i]
        previos = [str(j["_id"]) for j in juegos[max(0, i - CE.VENTANA_ARBITRO):i]]
        rng = random.Random(f"cal-esc-dep:{i}")
        vigentes = {k for k, hasta in en_crisis.items() if hasta > rondas}
        for c in S.elegir(S.candidatos(ventana, previos, con_presion=False), vigentes, rng):
            sev = E.elegir_severidad(rng)
            en_crisis[(c["tipo"], c["ref_id"])] = rondas + 2   # 16 partidos = 2 rondas
            por_tipo[c["tipo"]] += 1
            por_motivo[(c["tipo"], c["motivo"])] += 1
            por_sev[sev] += 1
            ejemplos.setdefault((c["tipo"], c["motivo"]), E.titular_deportivo(c["tipo"], c["motivo"], c, random.Random(1)))
    print(f"{rondas} rondas de {n} partidos ({rondas * n} partidos)")
    print("crisis por tipo:", dict(por_tipo), "· por severidad:", dict(sorted(por_sev.items())))
    print("por motivo:", {f'{t}/{m}': v for (t, m), v in por_motivo.items()})
    total = sum(por_tipo.values())
    print(f"≈ {total / rondas:.2f} crisis por ronda ({total / (rondas * n) * 100:.1f} por cada 100 partidos)")
    for k, v in ejemplos.items():
        print(f"  - {k[0]}/{k[1]}: {v}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
