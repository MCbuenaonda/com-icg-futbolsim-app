"""
Probabilidades de cada selección: clasificar al Mundial, llegar a dieciseisavos, octavos, cuartos, semifinales, la
final y ser campeona. Monte Carlo del RESTO del torneo con el reglamento real de cada eliminatoria.

MODELO DE PARTIDO (elegido con los datos, ver el análisis en CLAUDE.md):
  - Los goles de cada equipo siguen una Poisson casi perfecta (varianza ≈ media) e independiente de la del rival
    (r = 0,03); no hay ventaja de local (38% gana el local, 39% el visitante).
  - Goles esperados de A contra B: λ = μ · ataque(A) · defensa(B), con ataque y defensa = goles a favor / en contra
    por partido de cada equipo en ESTE Mundial, contraídos hacia la media con el peso de K_CONTRACCION partidos
    virtuales. K = 20 fue el de mejor log-loss fuera de muestra (1,0686 contra 1,0818 de no saber nada; Elo 1,0705)
    y está bien calibrado (empates predichos 22,2% contra 22,8% reales).
  - No se usa el overall ni el 'poder': en el motor la calidad de plantilla casi no mueve los goles (pendiente
    0,01 ± 0,03 en 3.600 partidos simulados) y el overall actual está contaminado por los resultados (ganar lo sube).

TORNEO: parte del estado real (tablas y partidos que faltan de la fase en curso de cada confederación; los
eliminados ya no están en 'internacional') y simula lo que falta: fases futuras con grupos sorteados al azar como
grupos_service.asignar_grupos_fase, llaves de ida y vuelta (global y penales), repechaje (2 grupos de 3), regla
del anfitrión, sorteo del Mundial por bombos de ranking con las restricciones por confederación, fase de grupos a
una vuelta, 8 mejores terceros, dieciseisavos (1° contra 3° evitando el mismo grupo) y llaves a partido único con
alargue y penales. El partido que se está transmitiendo cuenta como no jugado (no adelanta nada).

Se guarda una corrida por cada cantidad de partidos jugados en la colección 'probabilidades_mundial' (así queda la
historia para el gráfico de evolución). Se recalcula en un hilo de fondo al terminar un partido o al abrir una
ficha si está desactualizada; restart_mundial borra la colección.
"""
import math
import os
import random
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from services.estadisticas_service import db, _mundial_activo_id

K_CONTRACCION = 20
ITERACIONES = 3000
MINUTOS_CANDADO = 6   # un recálculo colgado libera el candado después de esto
ETAPAS = ["mundial", "dieciseisavos", "octavos", "cuartos", "semifinal", "final", "campeon"]
NOMBRE_ETAPA = {"mundial": "Clasificar al Mundial", "dieciseisavos": "Dieciseisavos", "octavos": "Octavos de final",
                "cuartos": "Cuartos de final", "semifinal": "Semifinales", "final": "Final", "campeon": "Campeón"}

# Reglamento de cada fase (confederación, fase): qué le pasa a cada posición del grupo (en una llave de 2 equipos,
# 1 = ganador del global). M = Mundial, R = repechaje, S = siguiente fase. "mejores" = (posición, cuántos, destino)
# entre todos los grupos. Refleja clasificacion_service.procesar_clasificacion_fase_N.
REGLAS = {
    (1, 1): {"pos": {1: "M", 2: "S"}, "mejores": (3, 4, "S")},
    (1, 2): {"pos": {1: "M"}},
    (2, 1): {"pos": {1: "M", 2: "M", 3: "M", 4: "M", 5: "M", 6: "M", 7: "R"}},
    (3, 1): {"pos": {1: "S"}},
    (3, 2): {"pos": {1: "S", 2: "S"}},
    (3, 3): {"pos": {1: "M", 2: "M"}, "mejores": (3, 2, "R")},
    (4, 1): {"pos": {1: "M"}, "mejores": (2, 4, "S")},
    (4, 2): {"pos": {1: "S"}},
    (4, 3): {"pos": {1: "R"}},
    (5, 1): {"pos": {1: "S"}},
    (5, 2): {"pos": {1: "S", 2: "S"}},
    (5, 3): {"pos": {1: "S"}},
    (5, 4): {"pos": {1: "M", 2: "R"}},
    (6, 1): {"pos": {1: "S"}},
    (6, 2): {"pos": {1: "S", 2: "S"}},
    (6, 3): {"pos": {1: "M", 2: "M", 3: "S", 4: "S"}},
    (6, 4): {"pos": {1: "M", 2: "S"}},
    (6, 5): {"pos": {1: "R"}},
    (7, 6): {"pos": {1: "M"}},
}
# Cantidad de grupos de cada fase (grupos_service.REGLAS_FASE_GRUPOS) para las fases que todavía no se sortearon
GRUPOS_FASE = {1: {1: 12, 2: 1, 3: 2, 4: 9, 5: 2, 6: 10}, 2: {1: 4, 3: 6, 4: 2, 5: 2, 6: 9},
               3: {3: 3, 4: 1, 5: 2, 6: 3}, 4: {5: 1, 6: 2}, 5: {6: 1}, 6: {7: 2}}
ESTADOS_MUNDIAL = ("CALIFICADO_MUNDIAL", "CALIFICADO_MUNDIAL_ANFITRION")


# =================================================================================================================
# Modelo de partido
# =================================================================================================================
def _poisson(lam: float, rnd=random.random) -> int:
    # Knuth: con λ ≈ 2 son 3-4 iteraciones
    limite, k, p = math.exp(-lam), 0, rnd()
    while p > limite:
        k += 1
        p *= rnd()
    return k


class Modelo:
    def __init__(self, finalizados: List[tuple]):
        gf, gc, pj = defaultdict(float), defaultdict(float), defaultdict(int)
        total = 0
        for a, b, ga, gb in finalizados:
            gf[a] += ga; gc[a] += gb; pj[a] += 1
            gf[b] += gb; gc[b] += ga; pj[b] += 1
            total += ga + gb
        self.mu = (total / (2 * len(finalizados))) if finalizados else 1.8
        k, mu = K_CONTRACCION, self.mu
        self.ataque = defaultdict(lambda: 1.0, {t: (gf[t] + k * mu) / (pj[t] + k) / mu for t in pj})
        self.defensa = defaultdict(lambda: 1.0, {t: (gc[t] + k * mu) / (pj[t] + k) / mu for t in pj})
        self._cache = {}

    def lambdas(self, a, b):
        par = (a, b)
        if par not in self._cache:
            self._cache[par] = (self.mu * self.ataque[a] * self.defensa[b], self.mu * self.ataque[b] * self.defensa[a])
        return self._cache[par]

    def partido(self, a, b):
        la, lb = self.lambdas(a, b)
        return _poisson(la), _poisson(lb)

    def eliminatoria(self, a, b) -> int:
        """Partido único con alargue (un tercio del partido) y penales 50/50: devuelve el ganador."""
        ga, gb = self.partido(a, b)
        if ga == gb:
            la, lb = self.lambdas(a, b)
            ga, gb = _poisson(la / 3), _poisson(lb / 3)
            if ga == gb:
                return a if random.random() < 0.5 else b
        return a if ga > gb else b


# =================================================================================================================
# Estado real
# =================================================================================================================
def _clave_estado(mundial_id: str) -> int:
    """Cantidad de partidos jugados (sin el que se transmite): cambia exactamente cuando termina un partido."""
    return db["juegos"].count_documents({"mundial_id": mundial_id, "estado": "finalizado", "transmision.estado": {"$ne": "in_progress"}})


def _cargar_estado(mundial_id: str) -> dict:
    juegos = list(db["juegos"].find({"mundial_id": mundial_id}, {
        "confederacion_id": 1, "fase_id": 1, "grupo": 1, "estado": 1, "transmision.estado": 1, "fecha": 1, "hora": 1,
        "equipo_local.id": 1, "equipo_visitante.id": 1, "resultado.goles_local": 1, "resultado.goles_visitante": 1,
        "resultado.penaltis_local": 1, "resultado.penaltis_visitante": 1}))
    jugados, pendientes = [], defaultdict(list)
    resultados = defaultdict(list)   # (conf, fase, grupo) -> [(a, b, ga, gb, pa, pb)]
    for j in juegos:
        a, b = (j.get("equipo_local") or {}).get("id"), (j.get("equipo_visitante") or {}).get("id")
        if a is None or b is None:
            continue
        clave = (j.get("confederacion_id"), j.get("fase_id"), (j.get("grupo") or "").replace("Grupo ", ""))
        jugado = j.get("estado") == "finalizado" and (j.get("transmision") or {}).get("estado") != "in_progress"
        if jugado:
            r = j.get("resultado") or {}
            ga, gb = r.get("goles_local") or 0, r.get("goles_visitante") or 0
            jugados.append((a, b, ga, gb))
            resultados[clave].append((a, b, ga, gb, r.get("penaltis_local"), r.get("penaltis_visitante")))
        else:
            pendientes[clave].append((a, b))
    equipos = {}
    for d in db["internacional"].find({}, {
            "id": 1, "confederacion_id": 1, "fase_eliminatoria": 1, "grupo": 1, "estado": 1, "estadisticas.poder": 1}):
        equipos[d["id"]] = {"conf": d.get("confederacion_id"), "fase": d.get("fase_eliminatoria"), "grupo": d.get("grupo"),
                            "estado": d.get("estado") or "", "poder": (d.get("estadisticas") or {}).get("poder") or 0.0}
    paises = {p["id"]: {"conf": p.get("confederacion_id"), "rankin": (p.get("estadisticas") or {}).get("rankin") or 999}
              for p in db["paises"].find({}, {"id": 1, "confederacion_id": 1, "estadisticas.rankin": 1})}
    mundial = db["mundiales"].find_one({"activo": True}, {"pais_id": 1}) or {}
    return {"jugados": jugados, "pendientes": pendientes, "resultados": resultados, "equipos": equipos,
            "paises": paises, "anfitrion": mundial.get("pais_id")}


# =================================================================================================================
# Simulación de un torneo
# =================================================================================================================
def _tabla(equipos: List[int], partidos: List[tuple], poder: dict) -> List[int]:
    """Orden de un grupo: puntos, diferencia, goles a favor, poder (desempate final, como clasificacion_service)."""
    pts, dg, gf = defaultdict(int), defaultdict(int), defaultdict(int)
    for a, b, ga, gb in partidos:
        gf[a] += ga; gf[b] += gb; dg[a] += ga - gb; dg[b] += gb - ga
        if ga > gb:
            pts[a] += 3
        elif gb > ga:
            pts[b] += 3
        else:
            pts[a] += 1; pts[b] += 1
    orden = sorted(equipos, key=lambda t: (pts[t], dg[t], gf[t], poder.get(t, 0.0), random.random()), reverse=True)
    return orden, {t: (pts[t], dg[t], gf[t]) for t in equipos}


def _jugar_grupo(modelo, equipos, jugados, pendientes, poder, ida_vuelta=True):
    """Completa un grupo: con 2 equipos es una llave (global + penales); con más, liga (ida y vuelta o una vuelta)."""
    partidos = [(a, b, ga, gb) for a, b, ga, gb, *_ in jugados]
    if len(equipos) == 2:
        a, b = equipos
        tanda = None
        for x, y, ga, gb, pa, pb in jugados:
            if pa is not None and pb is not None:
                tanda = x if pa > pb else y
        restantes = pendientes if (jugados or pendientes) else [(a, b), (b, a)]
        for x, y in restantes:
            partidos.append((x, y, *modelo.partido(x, y)))
        goles = defaultdict(int)
        for x, y, ga, gb in partidos:
            goles[x] += ga; goles[y] += gb
        if goles[a] != goles[b]:
            ganador = a if goles[a] > goles[b] else b
        elif tanda is not None and not restantes:
            ganador = tanda
        else:   # alargue en la vuelta y, si sigue igual, penales
            ga, gb = _poisson(modelo.lambdas(a, b)[0] / 3), _poisson(modelo.lambdas(a, b)[1] / 3)
            ganador = (a if ga > gb else b) if ga != gb else (a if random.random() < 0.5 else b)
        perdedor = b if ganador == a else a
        return [ganador, perdedor], {ganador: (0, 0, 0), perdedor: (0, 0, 0)}
    if not jugados and not pendientes:
        pendientes = [(a, b) for i, a in enumerate(equipos) for b in equipos[i + 1:]]
        if ida_vuelta:
            pendientes += [(b, a) for a, b in pendientes]
    for a, b in pendientes:
        partidos.append((a, b, *modelo.partido(a, b)))
    return _tabla(equipos, partidos, poder)


def _sortear_grupos(equipos: List[int], n_grupos: int) -> List[List[int]]:
    """Como grupos_service.asignar_grupos_fase: se mezclan y se reparten en ronda."""
    lista = equipos[:]
    random.shuffle(lista)
    grupos = [[] for _ in range(n_grupos)]
    for i, t in enumerate(lista):
        grupos[i % n_grupos].append(t)
    return [g for g in grupos if g]


def _aplicar_reglas(regla: dict, grupos_ordenados: List[tuple]):
    """Destinos (M/R/S) de una fase ya jugada a partir del orden de cada grupo."""
    destinos = defaultdict(list)
    for orden, _ in grupos_ordenados:
        for pos, t in enumerate(orden, start=1):
            if pos in regla["pos"]:
                destinos[regla["pos"][pos]].append(t)
    if "mejores" in regla:
        pos, cuantos, destino = regla["mejores"]
        candidatos = [(stats[orden[pos - 1]], orden[pos - 1]) for orden, stats in grupos_ordenados if len(orden) >= pos]
        candidatos.sort(key=lambda c: (c[0], random.random()), reverse=True)
        destinos[destino] += [t for _, t in candidatos[:cuantos]]
    return destinos


def _simular_confederacion(modelo, estado, conf, mundial, repechaje):
    """Juega lo que falta de la confederación (fase en curso + las siguientes) y anota quién va al Mundial o al repechaje."""
    eq = estado["equipos"]
    poder = {t: e["poder"] for t, e in eq.items()}
    vivos = [t for t, e in eq.items() if e["conf"] == conf]
    if not vivos:
        return
    for t in [t for t in vivos if eq[t]["estado"] in ESTADOS_MUNDIAL]:
        mundial.add(t)
    for t in [t for t in vivos if eq[t]["estado"].startswith("REPECHAJE")]:
        repechaje.append(t)
    en_juego = [t for t in vivos if eq[t]["estado"] not in ESTADOS_MUNDIAL and not eq[t]["estado"].startswith("REPECHAJE")]
    if not en_juego:
        return
    fase = min(eq[t]["fase"] or 1 for t in en_juego)
    # fase en curso: grupos reales con sus resultados y partidos pendientes
    por_grupo = defaultdict(list)
    for t in en_juego:
        if (eq[t]["fase"] or 1) == fase:
            por_grupo[eq[t]["grupo"]].append(t)
    grupos = [(g, sorted(ts)) for g, ts in sorted(por_grupo.items())]
    while True:
        regla = REGLAS.get((conf, fase))
        if regla is None:
            return
        ordenados = []
        for letra, equipos in grupos:
            clave = (conf, fase, letra)
            ordenados.append(_jugar_grupo(modelo, equipos, estado["resultados"].get(clave, []) if letra else [],
                                          estado["pendientes"].get(clave, []) if letra else [], poder))
        destinos = _aplicar_reglas(regla, ordenados)
        mundial.update(destinos.get("M", []))
        repechaje.extend(destinos.get("R", []))
        siguientes = destinos.get("S", [])
        if not siguientes:
            return
        fase += 1
        n = GRUPOS_FASE.get(fase, {}).get(conf, 1)
        grupos = [(None, g) for g in _sortear_grupos(siguientes, n)]


def _simular_mundial(modelo, estado, mundial: set, conteo):
    """Sorteo, fase de grupos y llaves del Mundial (desde cero: todavía no se sorteó)."""
    paises = estado["paises"]
    poder = {t: e["poder"] for t, e in estado["equipos"].items()}
    equipos = sorted(mundial, key=lambda t: paises.get(t, {}).get("rankin", 999))
    anfitrion = estado["anfitrion"]
    if anfitrion in equipos:
        equipos.remove(anfitrion)
        equipos.insert(0, anfitrion)
    bombos = [equipos[i * 12:(i + 1) * 12] for i in range(4)]
    grupos = None
    for _ in range(200):
        grupos = [[] for _ in range(12)]
        ok = True
        for i, bombo in enumerate(bombos):
            disponibles = bombo[:]
            random.shuffle(disponibles)
            if i == 0 and anfitrion in disponibles:
                disponibles.remove(anfitrion)
                grupos[0].append(anfitrion)
            for g in range(12):
                if i == 0 and g == 0 and grupos[0]:
                    continue
                elegido = next((t for t in disponibles if _cabe(grupos[g], t, paises)), None)
                if elegido is None:
                    ok = False
                    break
                grupos[g].append(elegido)
                disponibles.remove(elegido)
            if not ok:
                break
        if ok:
            break
    if not grupos or len([t for g in grupos for t in g]) < 48:   # sorteo imposible (no debería pasar): se reparte al azar
        lista = equipos[:]
        random.shuffle(lista)
        grupos = [lista[i::12] for i in range(12)]
    primeros, segundos, terceros = [], [], []
    for letra, g in enumerate(grupos):
        orden, stats = _jugar_grupo(modelo, g, [], [], poder, ida_vuelta=False)
        primeros.append((orden[0], letra)); segundos.append((orden[1], letra))
        terceros.append((stats[orden[2]], orden[2], letra))
    terceros.sort(key=lambda c: (c[0], random.random()), reverse=True)
    terceros = [(t, l) for _, t, l in terceros[:8]]
    for t, _ in primeros + segundos + terceros:
        conteo[t]["dieciseisavos"] += 1
    # dieciseisavos (grupos_service.asignar_grupos_16vos): 8 primeros contra los 8 terceros y el resto entre sí,
    # evitando cruzar con el mismo grupo de la fase anterior
    random.shuffle(primeros); random.shuffle(segundos); random.shuffle(terceros)
    cruces = _emparejar(primeros[:8], terceros)
    bolsa = segundos + primeros[8:]
    random.shuffle(bolsa)
    cruces += _emparejar(bolsa[:8], bolsa[8:])
    ronda = [modelo.eliminatoria(a, b) for a, b in cruces]
    for etapa in ("octavos", "cuartos", "semifinal", "final"):
        for t in ronda:
            conteo[t][etapa] += 1
        if etapa == "final":
            break
        ronda = [modelo.eliminatoria(ronda[i], ronda[i + 1]) for i in range(0, len(ronda), 2)]
    campeon = modelo.eliminatoria(ronda[0], ronda[1])
    conteo[campeon]["campeon"] += 1


def _cabe(grupo, t, paises):
    conf = paises.get(t, {}).get("conf")
    misma = sum(1 for x in grupo if paises.get(x, {}).get("conf") == conf)
    return misma < (2 if conf == 1 else 1)


def _emparejar(locales, visitantes):
    disponibles = visitantes[:]
    cruces = []
    for t, letra in locales:
        idx = next((i for i, (_, l) in enumerate(disponibles) if l != letra), 0)
        rival, _ = disponibles.pop(idx)
        cruces.append((t, rival))
    return cruces


def simular(iteraciones: int = ITERACIONES, semilla: Optional[int] = None) -> dict:
    mundial_id = _mundial_activo_id()
    estado = _cargar_estado(mundial_id)
    modelo = Modelo(estado["jugados"])
    random.seed(semilla)
    conteo = defaultdict(lambda: defaultdict(int))
    confs = sorted({e["conf"] for e in estado["equipos"].values() if e["conf"] and e["conf"] <= 7})
    for _ in range(iteraciones):
        mundial, repechaje = set(), []
        for conf in confs:
            if conf == 7:
                continue
            _simular_confederacion(modelo, estado, conf, mundial, repechaje)
        # repechaje: 2 grupos de 3 a ida y vuelta, gana el 1° de cada uno (o el real, si ya se sorteó)
        if 7 in confs:
            _simular_confederacion(modelo, estado, 7, mundial, [])
        elif len(repechaje) >= 2:
            for g in _sortear_grupos(repechaje, 2):
                orden, _ = _jugar_grupo(modelo, g, [], [], {})
                mundial.add(orden[0])
        # anfitrión: si no clasificó, entra y sale el peor rankeado de su confederación (validacion_equipo_anfitrion)
        anf = estado["anfitrion"]
        if anf and anf not in mundial:
            conf_anf = estado["paises"].get(anf, {}).get("conf")
            mismos = [t for t in mundial if estado["paises"].get(t, {}).get("conf") == conf_anf]
            if mismos:
                mundial.discard(max(mismos, key=lambda t: estado["paises"].get(t, {}).get("rankin", 999)))
            mundial.add(anf)
        for t in mundial:
            conteo[t]["mundial"] += 1
        if len(mundial) >= 48:
            _simular_mundial(modelo, estado, set(sorted(mundial)[:48]) if len(mundial) > 48 else mundial, conteo)
    return {"conteo": conteo, "iteraciones": iteraciones, "mundial_id": mundial_id, "modelo": modelo}


# =================================================================================================================
# Persistencia, cálculo en segundo plano y lectura para las vistas
# =================================================================================================================
def recalcular(iteraciones: int = ITERACIONES) -> Optional[dict]:
    """Corre la simulación y guarda una corrida por cantidad de partidos jugados (idempotente por clave)."""
    mundial_id = _mundial_activo_id()
    clave = _clave_estado(mundial_id)
    if db["probabilidades_mundial"].find_one({"mundial_id": mundial_id, "clave": clave}, {"_id": 1}):
        return None
    inicio = time.time()
    r = simular(iteraciones)
    n = r["iteraciones"]
    paises = {str(t): [round(c[e] / n, 4) for e in ETAPAS] for t, c in r["conteo"].items()}
    doc = {"mundial_id": mundial_id, "clave": clave, "generado_en": datetime.utcnow(), "iteraciones": n,
           "segundos": round(time.time() - inicio, 1), "mu": round(r["modelo"].mu, 3), "etapas": ETAPAS, "paises": paises}
    db["probabilidades_mundial"].update_one({"mundial_id": mundial_id, "clave": clave}, {"$setOnInsert": doc}, upsert=True)
    return doc


def recalcular_en_segundo_plano() -> bool:
    """
    Lanza el recálculo en un PROCESO aparte (python -m services.probabilidades_service --recalcular): la simulación
    usa CPU unos segundos y en un hilo frenaría al servidor web (GIL). Un candado en Mongo evita lanzar dos a la vez
    (también entre varios workers). Nunca lanza; devuelve si arrancó uno.
    """
    try:
        mundial_id = _mundial_activo_id()
        clave = _clave_estado(mundial_id)
        if db["probabilidades_mundial"].find_one({"mundial_id": mundial_id, "clave": clave}, {"_id": 1}):
            return False
        ahora = datetime.utcnow()
        candado = db["probabilidades_candado"].find_one_and_update(
            {"_id": mundial_id, "$or": [{"hasta": {"$lt": ahora}}, {"clave": {"$ne": clave}}]},
            {"$set": {"clave": clave, "hasta": ahora + timedelta(minutes=MINUTOS_CANDADO)}}, upsert=False)
        if candado is None:
            try:
                db["probabilidades_candado"].insert_one({"_id": mundial_id, "clave": clave,
                                                         "hasta": ahora + timedelta(minutes=MINUTOS_CANDADO)})
            except Exception:
                return False   # ya hay uno corriendo para esta clave
        raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        subprocess.Popen([sys.executable, "-m", "services.probabilidades_service", "--recalcular"], cwd=raiz,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception as e:
        print(f"Probabilidades: no se pudo lanzar el recálculo: {e}")
        return False


def probabilidades_pais(pais_id: int) -> Optional[dict]:
    """
    Para la ficha del país: la última corrida (y si está desactualizada, dispara el recálculo), sus probabilidades
    acumuladas por etapa y la evolución de cada una partido a partido.
    """
    mundial_id = _mundial_activo_id()
    clave = _clave_estado(mundial_id)
    corridas = list(db["probabilidades_mundial"].find({"mundial_id": mundial_id}, {"clave": 1, "generado_en": 1, "iteraciones": 1,
                                                                                    f"paises.{pais_id}": 1}).sort("clave", 1))
    desactualizada = not corridas or corridas[-1]["clave"] != clave
    if desactualizada:
        recalcular_en_segundo_plano()
    if not corridas:
        return {"pendiente": True}
    ultima = corridas[-1]
    valores = (ultima.get("paises") or {}).get(str(pais_id)) or [0.0] * len(ETAPAS)
    iteraciones = ultima.get("iteraciones") or ITERACIONES
    # asegurado / eliminado según el estado REAL (no según la simulación: 3.000 de 3.000 no es certeza)
    inter = db["internacional"].find_one({"id": pais_id}, {"estado": 1}) or {}
    anfitrion = (db["mundiales"].find_one({"activo": True}, {"pais_id": 1}) or {}).get("pais_id")
    asegurado_mundial = pais_id == anfitrion or (inter.get("estado") or "") in ESTADOS_MUNDIAL
    eliminado = not inter and not asegurado_mundial
    etapas = []
    for e, p in zip(ETAPAS, valores):
        # margen de error de Monte Carlo (95%): no es la incertidumbre del modelo, solo la del muestreo
        margen = 1.96 * math.sqrt(max(p * (1 - p), 0) / iteraciones)
        etapas.append({"codigo": e, "nombre": NOMBRE_ETAPA[e], "p": p, "pct": round(p * 100, 1), "margen": round(margen * 100, 1),
                       "asegurado": e == "mundial" and asegurado_mundial, "imposible": eliminado})
    historia = [{"clave": c["clave"], "valores": (c.get("paises") or {}).get(str(pais_id)) or [0.0] * len(ETAPAS)} for c in corridas]
    return {"pendiente": False, "eliminado": eliminado, "asegurado_mundial": asegurado_mundial, "etapas": etapas, "historia": historia, "clave": ultima["clave"], "clave_actual": clave,
            "desactualizada": desactualizada, "iteraciones": iteraciones, "generado_en": ultima.get("generado_en")}


if __name__ == "__main__":
    if "--recalcular" in sys.argv:
        # unos segundos de margen: al terminar un partido, la clasificación de fase y el sorteo de la siguiente se
        # procesan justo después del gancho que lanza este proceso
        time.sleep(4)
        try:
            doc = recalcular()
            print("Probabilidades:", f"corrida {doc['clave']} en {doc['segundos']} s" if doc else "ya estaban al día")
        finally:
            db["probabilidades_candado"].update_one({"_id": _mundial_activo_id()}, {"$set": {"hasta": datetime.utcnow()}})
