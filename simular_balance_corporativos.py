"""
Simulación de balance de los Corporativos Deportivos (Monte Carlo offline, SOLO LECTURA de la base).

Reproduce los partidos ya jugados del Mundial activo en orden, con la plantilla de siembra
(sembrar_corporativos.calcular_plantilla) y las reglas de services/corporativo_reglas.py, y mide:
renta vs honorarios por representado, ROI por ciclo, confianza del directorio y pago del CEO con tres
estrategias (bueno / malo / ia). Sirve para calibrar config/corporativos.py antes de tocar la app.

    python simular_balance_corporativos.py [SIGLA_CEO] [corridas] [v1|v2]

v1 = reglas viejas (honorario fijo por ciclo, juegue o no); v2 = economía actual (mantenimiento + honorario por
partido jugado + patrocinio por ciclo + renovación más barata + sentimiento por la ROI media de la ventana).
"""
import statistics
import sys

REGLAS = "v2"
from collections import defaultdict

from config import corporativos as C
from services import corporativo_reglas as R
from services import estadisticas_service as E
import sembrar_corporativos as S


def cargar():
    juegos = E._juegos_del_mundial()
    agregado = E._agregar_jugadores_mundial(juegos)
    por_partido = R.separar_por_partido(agregado)
    paises = {p["id"]: p for p in S.db["paises"].find({}, {"_id": 0, "id": 1, "valor": 1, "aficionados": 1, "confederacion_id": 1,
                                                            "estadisticas.poder": 1})}
    jugadores = list(S.db["jugadores"].find({"leyenda": {"$ne": True}}, {"_id": 0, "id": 1, "pais_id": 1, "overall": 1, "rendimiento": 1, "edad": 1, "posicion_id": 1}))
    valores_j = R.valores_jugadores(jugadores, {k: (v.get("estadisticas") or {}).get("poder") or 0 for k, v in paises.items()})
    valores_s = {pid: R.valor_seleccion(p) for pid, p in paises.items()}
    posicion = {j["id"]: j.get("posicion_id") for j in jugadores}
    pais_de = {j["id"]: j.get("pais_id") for j in jugadores}
    plantilla = S.calcular_plantilla()
    return juegos, por_partido, valores_j, valores_s, posicion, pais_de, plantilla, paises


class Corp:
    def __init__(self, sigla, fila, valores_j, valores_s, rng):
        self.sigla, self.tier = sigla, C.CORPORATIVO_POR_SIGLA[sigla]["tier"]
        self.capital = C.TIERS[self.tier]["capital"]
        self.contratos = {}
        for pid in fila["selecciones"]:
            self.contratos[("seleccion", pid)] = self._contrato(valores_s[pid], rng, prima=0)
        for jid in fila["jugadores"]:
            self.contratos[("jugador", jid)] = self._contrato(valores_j[jid], rng, prima=0)
        self.confianza, self.sentimiento = C.CONFIANZA_INICIAL, C.SENTIMIENTO_INICIAL
        self.renta_ciclo = 0
        self.historial, self.rois, self.precio, self.variacion = [], [], 0, 0

    @staticmethod
    def _contrato(valor, rng, prima):
        dur = rng.randint(*C.DURACION_CONTRATO)
        return {"valor": valor, "restantes": dur, "amort": prima / dur, "renta": 0, "ciclos": 0, "renta_total": 0, "honorarios_total": 0}

    def valor_cartera(self):
        return sum(c["valor"] for c in self.contratos.values())


def correr(datos, sigla_ceo, estrategia, corrida):
    juegos, por_partido, valores_j, valores_s, posicion, pais_de, plantilla, paises = datos
    rng = R.semilla("balance", sigla_ceo, estrategia, corrida)
    corps = {f["sigla"]: Corp(f["sigla"], f, valores_j, valores_s, rng) for f in plantilla}
    ocupados = {k for c in corps.values() for k in c.contratos}
    victorias, jugados = defaultdict(int), defaultdict(int)
    pagos_ceo, despido = [], None
    resumen_renta = defaultdict(list)   # (tipo) -> renta - honorario por representado y ciclo

    for seq, juego in enumerate(juegos, start=1):
        ap = R.aporte_partido(juego, por_partido.get(str(juego["_id"]), {}), posicion)
        for pid, resultado in ap["selecciones"].items():
            jugados[pid] += 1
            victorias[pid] += resultado == "victoria"
        for c in corps.values():
            for pid, resultado in ap["selecciones"].items():
                k = ("seleccion", pid)
                if k in c.contratos:
                    r = R.renta_seleccion(c.contratos[k]["valor"], resultado)
                    if REGLAS == "v2":
                        h = R.honorario_partido("seleccion", c.contratos[k]["valor"])
                        r -= h
                        c.contratos[k]["hon_partidos"] = c.contratos[k].get("hon_partidos", 0) + h
                    c.contratos[k]["renta"] += r
                    c.capital += r
                    c.renta_ciclo += r
            for jid, aporte in ap["jugadores"].items():
                k = ("jugador", jid)
                if k in c.contratos:
                    r = R.renta_jugador(c.contratos[k]["valor"], aporte)
                    if REGLAS == "v2":
                        h = R.honorario_partido("jugador", c.contratos[k]["valor"])
                        r -= h
                        c.contratos[k]["hon_partidos"] = c.contratos[k].get("hon_partidos", 0) + h
                    c.contratos[k]["renta"] += r
                    c.capital += r
                    c.renta_ciclo += r

        if seq % C.PARTIDOS_POR_CICLO:
            continue
        ciclo = seq // C.PARTIDOS_POR_CICLO
        if ciclo > 1 and despido is None and evaluar_directorio(corps, sigla_ceo, ciclo):
            despido = ciclo - 1
        for c in corps.values():
            patrimonio = c.capital + c.valor_cartera()
            gasto = 0
            c.renta_ciclo += sum(_patrocinio(k, ct, paises) for k, ct in c.contratos.items()) if REGLAS == "v2" else 0
            for k, ct in list(c.contratos.items()):
                h = _honorario_ciclo(k, ct)
                pat = _patrocinio(k, ct, paises) if REGLAS == "v2" else 0
                gasto += h + ct["amort"]
                resumen_renta[k[0]].append(ct["renta"] + pat - h)
                ct["renta_total"] += ct["renta"] + pat
                ct["honorarios_total"] += h + ct.pop("hon_partidos", 0)
                ct["renta"], ct["ciclos"], ct["restantes"] = 0, ct["ciclos"] + 1, ct["restantes"] - 1
                if ct["restantes"] <= 0:
                    # vence: se renueva si rindió (renta >= 80% de lo que costó), pagando una prima nueva
                    if ct["renta_total"] >= 0.8 * ct["honorarios_total"]:
                        prima = R.prima_renovacion(ct["valor"], 70) if REGLAS == "v2" else R.prima_referencia(ct["valor"])
                        c.capital -= prima
                        c.contratos[k] = Corp._contrato(ct["valor"], rng, prima)
                    else:
                        del c.contratos[k]
                        ocupados.discard(k)
            c.capital -= sum(_honorario_ciclo(k, ct) for k, ct in c.contratos.items())
            c.capital += sum(_patrocinio(k, ct, paises) for k, ct in c.contratos.items()) if REGLAS == "v2" else 0
            utilidad = c.renta_ciclo - gasto
            es_ceo = c.sigla == sigla_ceo and despido is None
            if es_ceo:
                sueldo = R.sueldo_base(c.tier, C.FAMA_INICIAL)
                c.utilidades = getattr(c, "utilidades", []) + [utilidad]
                media = statistics.mean(c.utilidades[-C.CICLOS_VENTANA_ROI:])   # bono sobre la utilidad media de la ventana
                bono = R.bono_ciclo(statistics.mean(C.BONO_PORCENTAJE), media, sueldo)
                c.capital -= sueldo + bono
                utilidad -= sueldo + bono
                pagos_ceo.append(sueldo + bono)
            roi = utilidad / max(patrimonio, 1)
            nuevo = R.precio_accion(c.capital, c.valor_cartera(), c.sentimiento)
            c.variacion = nuevo / c.precio - 1 if c.precio else 0
            c.precio = nuevo if not c.precio else R.limitar_banda(nuevo, c.precio)
            c.rois.append(roi)
            roi_sent = statistics.mean(c.rois[-C.CICLOS_VENTANA_ROI:]) if REGLAS == "v2" else roi
            c.sentimiento = R.nuevo_sentimiento(c.sentimiento, roi_sent, 0, rng)
            c.utilidades_todas = getattr(c, "utilidades_todas", []) + [utilidad]
            c.historial.append((ciclo, round(roi * 100, 2), int(c.capital), c.confianza))
            c.renta_ciclo = 0

            c._es_ceo = es_ceo
            # Fichajes: IA (o estrategia del CEO)
            modo = estrategia if es_ceo else "ia"
            if modo == "malo":   # paga de más por veteranos de selecciones que vienen perdiendo, nunca suelta a nadie
                forma = lambda pid: victorias[pid] / jugados[pid] if jugados[pid] else 0.5
                libres = sorted((j for j in valores_j if ("jugador", j) not in ocupados and jugados[pais_de[j]] >= 1),
                                key=lambda j: (forma(pais_de[j]), -valores_j[j]))[:2]
                multiplo = 3.0
            elif modo == "bueno":
                forma = lambda pid: victorias[pid] / jugados[pid] if jugados[pid] else 0
                libres = sorted((j for j in valores_j if ("jugador", j) not in ocupados and jugados[pais_de[j]] >= 2),
                                key=lambda j: (forma(pais_de[j]), valores_j[j]), reverse=True)[:2]
                multiplo = 1.1
                for k, ct in list(c.contratos.items()):   # suelta lo que no rinde
                    if ct["ciclos"] >= 3 and k[0] == "jugador" and jugados[pais_de[k[1]]] and forma(pais_de[k[1]]) < 0.25:
                        c.capital -= _honorario_ciclo(k, ct) * ct["restantes"] * C.RESCISION_FRACCION_RESTANTE
                        del c.contratos[k]
                        ocupados.discard(k)
            else:
                libres = [j for j in rng.sample(list(valores_j), 40) if ("jugador", j) not in ocupados][:1]
                multiplo = C.IA_MULTIPLO_VENTA.get(C.CORPORATIVO_POR_SIGLA[c.sigla]["perfil"], 1.1)
            for j in libres:
                prima = R.prima_referencia(valores_j[j]) * multiplo
                if prima > c.capital * C.IA_PRESUPUESTO_FICHAJE * (2 if modo == "malo" else 1):
                    continue
                p = R.probabilidad_acepta(C.TIERS[c.tier]["reputacion"], C.FAMA_INICIAL, prima,
                                          valores_j[j], False, 50)
                if rng.random() < p:
                    c.capital -= prima
                    c.contratos[("jugador", j)] = Corp._contrato(valores_j[j], rng, prima)
                    ocupados.add(("jugador", j))
    return corps, pagos_ceo, despido, resumen_renta


def _honorario_ciclo(k, ct):
    """v1: honorario fijo por ciclo. v2: solo el mantenimiento (el resto se cobró por partido jugado)."""
    if REGLAS == "v2":
        return R.honorario_mantenimiento(k[0], ct["valor"])
    return int(round(ct["valor"] * C.HONORARIO_POR_CICLO[k[0]]))


def _patrocinio(k, ct, paises):
    pop = R.popularidad_seleccion((paises.get(k[1]) or {}).get("aficionados")) if k[0] == "seleccion" else R.popularidad_jugador(ct["valor"])
    return R.patrocinio(k[0], ct["valor"], pop)


def evaluar_directorio(corps, sigla_ceo, ciclo):
    ventana = {s: sum(c.rois[-C.CICLOS_VENTANA_ROI:]) for s, c in corps.items()}
    orden = sorted(ventana, key=ventana.get, reverse=True)
    indice = statistics.mean(c.variacion for c in corps.values())
    c = corps[sigla_ceo]
    c.confianza = R.limitar(c.confianza + R.cambio_confianza(c.tier, orden.index(sigla_ceo) + 1, ventana[sigla_ceo],
                                                              c.variacion - indice, c.capital < 0), 0, 100)
    c.posiciones = getattr(c, "posiciones", []) + [orden.index(sigla_ceo) + 1]
    return c.confianza < C.CONFIANZA_DESPIDO or c.capital < C.TIERS[c.tier]["capital"] * C.CAPITAL_MINIMO_FRACCION


def main():
    global REGLAS
    sigla = sys.argv[1] if len(sys.argv) > 1 else "UIDR"
    corridas = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    REGLAS = sys.argv[3] if len(sys.argv) > 3 else "v2"
    datos = cargar()
    print(f"{len(datos[0])} partidos -> {len(datos[0]) // C.PARTIDOS_POR_CICLO} ciclos. CEO en {sigla}. Reglas {REGLAS}.\n")
    for estrategia in ("ia", "bueno", "malo"):
        pagos, despidos, rois, capitales, rentas = [], [], [], [], defaultdict(list)
        for i in range(corridas):
            corps, pagos_ceo, despido, resumen = correr(datos, sigla, estrategia, i)
            pagos += pagos_ceo
            despidos.append(despido)
            c = corps[sigla]
            rois += [h[1] for h in c.historial]
            capitales.append(int(c.capital))
            for t, v in resumen.items():
                rentas[t] += v
        print(f"[{estrategia}] pago CEO/ciclo: media {statistics.mean(pagos):.0f}  (min {min(pagos)}, max {max(pagos)})"
              f"  despidos: {despidos}")
        print(f"        ROI/ciclo %: media {statistics.mean(rois):.2f}  p10 {statistics.quantiles(rois, n=10)[0]:.2f}"
              f"  p90 {statistics.quantiles(rois, n=10)[-1]:.2f}   capital final: {capitales}")
        for t, v in rentas.items():
            print(f"        neto por {t} y ciclo (todos los corporativos): media {statistics.mean(v):.1f}"
                  f"  positivos {sum(1 for x in v if x > 0) / len(v):.0%}")
    todas_u, todas_roi, precios = [], [], []
    for i in range(corridas):
        corps_i, *_ = correr(datos, sigla, "ia", i)
        for c in corps_i.values():
            todas_u += c.utilidades_todas
            todas_roi += c.rois
            precios.append(c.precio)
    neg = sum(1 for u in todas_u if u < 0) / len(todas_u)
    print(f"\nTODOS los corporativos (IA): ciclos con utilidad negativa {neg:.0%} | ROI mediano por ciclo {statistics.median(todas_roi) * 100:.2f}%"
          f" | ROI medio {statistics.mean(todas_roi) * 100:.2f}%")
    corps, *_ = correr(datos, sigla, "ia", 0)
    print("\nCapital final por corporativo (IA, corrida 0):")
    for c in corps.values():
        print(f"  {c.sigla} tier {c.tier}: capital {int(c.capital):>7,}  cartera {c.valor_cartera():>8,}  "
              f"ROI medio {statistics.mean(h[1] for h in c.historial):.2f}%  representados {len(c.contratos)}")
    print("Posiciones del CEO por ciclo (ia):", getattr(corps[sigla], "posiciones", []), "confianza final", corps[sigla].confianza)


if __name__ == "__main__":
    main()
