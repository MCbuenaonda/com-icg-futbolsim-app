"""
Calibración de las ESPECIALIDADES (config/especialidades.py + services/especialidades.py) con Monte Carlo. SOLO LECTURA:
simula partidos sin guardar (arnés de calibrar_formaciones.py, lecturas en caché) con las especialidades que asignaría
asignar_especialidades.calcular() inyectadas en memoria (sirve antes de --aplicar).

Uso:
    python calibrar_especialidades.py [N]                 # con efecto
    python calibrar_especialidades.py [N] --sin-efecto    # referencia: mismo reparto, sin puntos ni Pulmón
    python calibrar_especialidades.py [N] --evolucion     # N partidos seguidos aplicando la evolución en memoria
    python calibrar_especialidades.py [N] --extremos      # selección en el techo contra otra en el piso

Mide goles y tarjetas por partido, y por especialidad cómo le va a quien la tiene contra quien no (misma línea).
"""
import random
import statistics
import sys
from collections import defaultdict

import calibrar_formaciones as CFM   # arnés: lecturas en caché sobre el motor
import asignar_especialidades as AE
from config import especialidades as CE
from config.fantasy import LINEA_DE_POSICION
from services import desgaste
from services import simular_service as S

SIN_EFECTO = "--sin-efecto" in sys.argv
if SIN_EFECTO:
    sys.argv.remove("--sin-efecto")
    CE.PUNTOS_ESPECIALIDAD = 0.0
    desgaste._FACTOR_PULMON = 1.0

_asignadas = AE.calcular()
_find_real = CFM._Coleccion.find


def _find(self, filtro=None, *a, **k):
    docs = _find_real(self, filtro, *a, **k)
    if self.real.name == "jugadores":
        for d in docs:
            extra = _asignadas.get(d.get("id"))
            if extra:
                d.update(extra)
    return docs


CFM._Coleccion.find = _find


def main(n: int) -> None:
    random.seed(17)
    goles, tarjetas = [], []
    por_esp = defaultdict(lambda: {"con": defaultdict(float), "sin": defaultdict(float)})
    info = {}
    for local, visita in CFM._pares(n, 29):
        p, stats = S.simular_partido_realista(local, visita)
        goles.append(p["goles_local"] + p["goles_visitante"])
        tarjetas.append(CFM._tarjetas(p))
        for jid, st in stats.items():
            if jid not in info:
                info[jid] = _asignadas.get(jid, {}).get("especialidades", [])
            for codigo in ("definidor", "cabeceador", "regateador", "reflejos", "llegador", "atajapenales"):
                lado = "con" if codigo in info[jid] else "sin"
                linea = st.get("posicion")
                if linea not in [l for l in CE.ESPECIALIDADES[codigo]["lineas"]]:
                    continue
                c = por_esp[codigo][lado]
                c["n"] += 1
                for k in ("goles", "goles_corner", "regates_exitosos", "atajadas", "goles_encajados", "tiros_puerta", "atajadas_penales"):
                    c[k] += st.get(k, 0) or 0
    print(f"{n} partidos {'SIN efecto' if SIN_EFECTO else 'con efecto'}")
    print(f"goles/partido {statistics.mean(goles):.3f} (±{1.96 * statistics.stdev(goles) / n ** 0.5:.3f}) · tarjetas {statistics.mean(tarjetas):.2f}")
    metricas = {"definidor": "goles", "cabeceador": "goles_corner", "regateador": "regates_exitosos", "reflejos": "atajadas",
                "llegador": "goles", "atajapenales": "atajadas_penales"}
    for codigo, m in metricas.items():
        con, sin = por_esp[codigo]["con"], por_esp[codigo]["sin"]
        if con["n"] and sin["n"]:
            print(f"  {codigo:13} {m} por partido: con {con[m] / con['n']:.3f} ({int(con['n'])}) · sin {sin[m] / sin['n']:.3f}")




def evolucion(n: int) -> None:
    """
    Simula n partidos seguidos entre las mismas 24 selecciones aplicando la evolución en memoria (resumen → evaluar)
    y mide ganadas/perdidas por especialidad, el balance total y cuánto se separan las selecciones.
    """
    from services import especialidades as ES
    from collections import Counter
    leyendas = {d["id"] for d in CFM._db_real["jugadores"].find({"leyenda": True}, {"id": 1})}
    estado = {jid: {"especialidades": list(d["especialidades"]), "esp_ventana": [], "esp_partidos": {}, "leyenda": jid in leyendas}
              for jid, d in _asignadas.items()}
    linea_de, pais_de = {}, {}

    def _find_evo(self, filtro=None, *a, **k):
        docs = _find_real(self, filtro, *a, **k)
        if self.real.name == "jugadores":
            for d in docs:
                st = estado.get(d.get("id"))
                if st:
                    d["especialidades"] = list(st["especialidades"])
                    d["especialista_penales"] = "penales" in st["especialidades"]
                    d["especialista_tiros_libres"] = "tiros_libres" in st["especialidades"]
                linea_de[d.get("id")] = LINEA_DE_POSICION.get(d.get("posicion_id"), "MEDIO")
                pais_de[d.get("id")] = d.get("pais_id")
        return docs

    CFM._Coleccion.find = _find_evo
    random.seed(23)
    ganadas, perdidas, apariciones, bloqueadas = Counter(), Counter(), 0, 0
    jugadores_con_cambio = set()
    goles_ini, goles_fin = [], []
    pares = CFM._pares(n, 41)
    total_ini = sum(len(st["especialidades"]) for st in estado.values())
    for i, (local, visita) in enumerate(pares):
        p, stats = S.simular_partido_realista(local, visita)
        (goles_ini if i < n // 4 else goles_fin if i >= 3 * n // 4 else []).append(p["goles_local"] + p["goles_visitante"])
        por_pais = defaultdict(list)
        for jid, st in stats.items():
            e = estado.get(jid)
            if not e or e.get("leyenda"):
                continue
            apariciones += 1
            gc = p["goles_visitante"] if st.get("lado") == "L" else p["goles_local"]
            e["esp_ventana"] = (e["esp_ventana"] + [ES.resumen_partido(st, gc, False, str(i))])[-CE.VENTANA_GUARDADA:]
            for c in e["especialidades"]:
                e["esp_partidos"][c] = e["esp_partidos"].get(c, 0) + 1
            por_pais[pais_de.get(jid)].append({**e, "jid": jid, "linea": linea_de.get(jid), "cal": st.get("rating")})
        for pid, estados in por_pais.items():
            total = sum(len(x["especialidades"]) for j2, x in estado.items() if pais_de.get(j2) == pid and not x.get("leyenda"))
            sin_limite = {e2["jid"]: ES.evaluar(e2, total - CE.BASE_SELECCION) for e2 in estados}
            resultado = ES.evolucionar_equipo(estados, total)
            bloqueadas += sum(len(g) + len(pe) for g, pe in sin_limite.values()) - sum(len(g) + len(pe) for g, pe in resultado.values())
            for jid, (g, pe) in resultado.items():
                e = estado[jid]
                for c, _ in pe:
                    e["especialidades"].remove(c); perdidas[c] += 1; jugadores_con_cambio.add(jid)
                    e["esp_partidos"].pop(c, None)
                for c, _ in g:
                    e["especialidades"].append(c); ganadas[c] += 1; jugadores_con_cambio.add(jid)
                    e["esp_partidos"][c] = 0
    total_fin = sum(len(st["especialidades"]) for st in estado.values())
    print(f"{n} partidos, {apariciones} apariciones de jugadores")
    print(f"ganadas {sum(ganadas.values())} · perdidas {sum(perdidas.values())} · total de especialidades {total_ini} → {total_fin}")
    print(f"por aparición: gana {sum(ganadas.values()) / apariciones:.4f} · pierde {sum(perdidas.values()) / apariciones:.4f}")
    print(f"jugadores que cambiaron algo: {len(jugadores_con_cambio)} · cambios frenados por el piso o el techo: {bloqueadas}")
    print("ganadas:", ganadas.most_common())
    print("perdidas:", perdidas.most_common())
    # separación entre las 24 selecciones simuladas
    ids_paises = {x for par in pares for x in par}
    from services import fantasy_service as F
    por_pais = Counter()
    for d in F.db["jugadores"].find({"pais_id": {"$in": list(ids_paises)}, "leyenda": {"$ne": True}}, {"id": 1, "pais_id": 1}):
        por_pais[d["pais_id"]] += len(estado.get(d["id"], {}).get("especialidades", []))
    vals = sorted(por_pais.values())
    print(f"especialidades por selección (actuales) al final: mín {vals[0]} · mediana {vals[len(vals)//2]} · máx {vals[-1]} (empezaron en 16)")
    print("  reparto:", sorted(vals))
    if goles_ini and goles_fin:
        print(f"goles/partido primer cuarto {statistics.mean(goles_ini):.2f} · último cuarto {statistics.mean(goles_fin):.2f}")


def extremos(n: int) -> None:
    """
    Cuánto pesa estar en el techo contra el piso: en cada partido, una selección con sus 22 actuales llevados a
    TECHO_SELECCION especialidades (sumando válidas de su línea) contra otra en PISO_SELECCION (quitando). Se compara
    la probabilidad de ganar del lado fuerte con la base (las dos en su reparto real de 16), alternando local y visita.
    """
    from services import especialidades as ES
    jugadores = {d["id"]: d for d in CFM._db_real["jugadores"].find({"leyenda": {"$ne": True}}, {"id": 1, "pais_id": 1, "posicion_id": 1})}
    por_pais = defaultdict(list)
    for jid, d in jugadores.items():
        por_pais[d["pais_id"]].append(jid)

    def ajustar(pais_id, objetivo, rng):
        """Especialidades de los actuales de la selección llevadas a 'objetivo' (en memoria)."""
        ids = por_pais[pais_id]
        esp = {j: list(_asignadas[j]["especialidades"]) for j in ids}
        total = sum(len(v) for v in esp.values())
        while total < objetivo:
            j = rng.choice(ids)
            linea = LINEA_DE_POSICION.get(jugadores[j]["posicion_id"], "MEDIO")
            libres = [c for c, e in CE.ESPECIALIDADES.items() if linea in e["lineas"] and c not in esp[j] and e["efectos"]]
            if len(esp[j]) < CE.MAXIMO_POR_JUGADOR and libres:
                esp[j].append(rng.choice(libres)); total += 1
        while total > objetivo:
            j = rng.choice([x for x in ids if esp[x]])
            esp[j].pop(rng.randrange(len(esp[j]))); total -= 1
        return esp

    forzadas = {}
    _find_base = CFM._Coleccion.find

    def _find_ext(self, filtro=None, *a, **k):
        docs = _find_base(self, filtro, *a, **k)
        if self.real.name == "jugadores":
            for d in docs:
                if d.get("id") in forzadas:
                    d["especialidades"] = forzadas[d["id"]]
        return docs

    CFM._Coleccion.find = _find_ext
    rng = random.Random(5)
    res = {"base": [0, 0, 0], "extremos": [0, 0, 0]}   # victorias, empates, derrotas del lado A
    for i, (a, b) in enumerate(CFM._pares(n, 53)):
        for modo in ("base", "extremos"):
            forzadas.clear()
            if modo == "extremos":
                forzadas.update(ajustar(a, CE.TECHO_SELECCION, rng))
                forzadas.update(ajustar(b, CE.PISO_SELECCION, rng))
            local, visita = (a, b) if i % 2 else (b, a)
            p, _ = S.simular_partido_realista(local, visita)
            ga, gb = (p["goles_local"], p["goles_visitante"]) if i % 2 else (p["goles_visitante"], p["goles_local"])
            res[modo][0 if ga > gb else 1 if ga == gb else 2] += 1
    for modo, (v, e, d) in res.items():
        print(f"{modo:9} el lado A gana {v / n:.1%} · empata {e / n:.1%} · pierde {d / n:.1%}")
    print(f"diferencia por estar en el techo ({CE.TECHO_SELECCION}) contra el piso ({CE.PISO_SELECCION}): "
          f"{(res['extremos'][0] - res['base'][0]) / n * 100:+.1f} puntos de probabilidad de ganar")


if __name__ == "__main__":
    if "--extremos" in sys.argv:
        sys.argv.remove("--extremos")
        extremos(int(sys.argv[1]) if len(sys.argv) > 1 else 400)
        sys.exit()
    if "--evolucion" in sys.argv:
        sys.argv.remove("--evolucion")
        evolucion(int(sys.argv[1]) if len(sys.argv) > 1 else 600)
    else:
        main(int(sys.argv[1]) if len(sys.argv) > 1 else 300)
