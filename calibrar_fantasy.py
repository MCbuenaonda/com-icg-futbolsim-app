"""
Calibración del pago del Once Ideal v2 (config/fantasy.py). SOLO LECTURA: simula partidos sin guardar (mismo arnés con
lecturas en caché que calibrar_formaciones.py) y mide con los partidos reales del Mundial cuánto juega un equipo.

Uso:
    python calibrar_fantasy.py [N]     # N partidos simulados (200 por defecto)

Mide:
  - pago medio por partido jugado de un alineado, por línea y titular/suplente (con fantasy_service.pago_partido);
  - partidos por jornada que juega un jugador de una selección viva (últimas 10 jornadas reales);
  - saldo por jornada de un equipo por formación y jornadas para recuperar cada desbloqueo (meta 8-10);
  - referencia: lo que deja una sede (regalía) y una selección (dividendo) en una jornada.
"""
import random
import statistics
import sys
from collections import defaultdict

import calibrar_formaciones as CFM   # aplica el arnés de lecturas en caché sobre el motor
from config import fantasy as CFF
from services import fantasy_service as FS
from services import simular_service as S
from services import estadisticas_service as E

LINEA_STATS = {"PORTERO": "PORTERO", "DEFENSA": "DEFENSA", "MEDIO": "MEDIO", "DELANTERO": "DELANTERO"}


def pagos_por_aparicion(n: int) -> dict:
    """{(linea, suplente): [stats de cada aparición]} simulando n partidos."""
    apariciones = defaultdict(list)
    for local, visita in CFM._pares(n, 23):
        p, stats = S.simular_partido_realista(local, visita)
        for jid, st in stats.items():
            linea = CFF.LINEA_DE_POSICION.get(st.get("posicion_id")) or LINEA_STATS.get(st.get("posicion"), "MEDIO")
            st = dict(st)
            apariciones[(linea, bool(st.get("entro_de_cambio")))].append((st, p["goles_local"], p["goles_visitante"]))
    return apariciones


def monto_medio(apariciones: list, formacion: str) -> float:
    return statistics.mean(FS.pago_partido(st, FS._desglosar_puntos_base(st, gl, gv), formacion, False)["monto"]
                           for st, gl, gv in apariciones)


def ritmo_real() -> float:
    """Partidos por jornada de un jugador de una selección viva, en las últimas 10 jornadas (200 partidos)."""
    juegos = list(FS.db["juegos"].find(E._filtro_finalizados(), {"equipo_local.id": 1, "equipo_visitante.id": 1, "resultado.participantes": 1,
                                                                 "fecha": 1, "hora": 1}).sort([("fecha", 1), ("hora", 1)]))[-200:]
    eliminados = FS.paises_eliminados()
    vivos = {d["id"] for d in FS.db["internacional"].find({}, {"id": 1}) if d["id"] not in eliminados}
    jugadores = list(FS.db["jugadores"].find({"pais_id": {"$in": list(vivos)}, "leyenda": {"$ne": True}}, {"id": 1}))
    aparic = defaultdict(int)
    for j in juegos:
        for pid in (j.get("resultado") or {}).get("participantes") or []:
            aparic[pid] += 1
    # Un usuario elige titulares: el 60% de su selección que más juega
    por_jugador = sorted((aparic.get(j["id"], 0) for j in jugadores), reverse=True)
    titulares = por_jugador[:int(len(por_jugador) * 0.6)]
    return statistics.mean(titulares) / (len(juegos) / FS.PARTIDOS_POR_JORNADA)


def main(n: int) -> None:
    random.seed(5)
    ap = pagos_por_aparicion(n)
    print(f"{n} partidos simulados")
    print("pago medio por partido jugado (formación neutral 4-4-2):")
    for linea in CFF.LINEAS:
        tit, sup = ap.get((linea, False), []), ap.get((linea, True), [])
        print(f"  {linea:9} titular {monto_medio(tit, '4-4-2'):5.1f} ({len(tit)})  suplente {monto_medio(sup, '4-4-2') if sup else 0:5.1f} ({len(sup)})")
    ritmo = ritmo_real()
    print(f"\npartidos por jornada de un titular de una selección viva: {ritmo:.3f}")
    print("\nsaldo por jornada de un equipo (titulares) y jornadas para recuperar cada desbloqueo:")
    for esq in CFF.FORMACIONES:
        cupos = CFF.cupos_formacion(esq)
        por_partido = sum(n_l * monto_medio(ap[(l, False)], esq) for l, n_l in cupos.items())
        jornada = por_partido * ritmo
        rec = " · ".join(f"eq{k} {c / jornada:4.1f}" for k, c in CFF.COSTOS_ESCUADRA.items())
        print(f"  {esq:8} {jornada:6.1f} por jornada  ({por_partido:.0f} si jugaran los 11)  recupera: {rec}")
    # Referencia: sede (regalía por partido alojado) y selección (dividendo por victoria)
    from services import venue_service as V, ownership_service as O
    print(f"\nreferencia: una sede paga {V.REGALIA_BASE}+{V.BONO_POR_GOL}/gol por partido alojado (cuesta {V.COSTO_BASE_SEDE});"
          f" una selección {O.DIVIDENDO_VICTORIA} por victoria (cuesta desde {O.VALOR_INICIAL_PAIS});"
          f" una selección viva juega ~{ritmo / 0.75:.2f} partidos por jornada")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
