"""
Corporativos Deportivos — economía de los representados: renta y honorario por partido jugado, mantenimiento y
patrocinio por ciclo, acuerdos publicitarios y giras (corporativo_acciones_service), avance o eliminación de fase,
satisfacción, vencimientos y renovación de la IA, cotización.

poner_al_dia (corporativo_universo_service) arma un `Estado` en memoria con los corporativos y los contratos del
universo, le aplica los partidos y cierres de ciclo pendientes y lo guarda con bulk_write junto con el cursor.
El aporte de cada partido (quién jugó, goles, asistencias, valla invicta, rojas) es igual para todos los
universos: se calcula una vez (estadisticas_service._agregar_jugadores_mundial) y se cachea en memoria.
"""
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List

from bson import ObjectId
from pymongo import UpdateOne

from config import corporativos as C
from services import corporativo_reglas as R
from services.corporativo_mercado_service import valores
from services.corporativo_universo_service import db

# Campos que escribe el procesamiento (no se pisan los que cambian las acciones del usuario, como es_del_usuario)
CAMPOS_CORP = ("capital", "sentimiento", "precio", "variacion_ciclo", "patrimonio", "historial", "ciclo_actual", "confianza",
               "saneamiento")
CAMPOS_CONTRATO = ("renta_total", "renta_ciclo", "honorarios_total", "satisfaccion", "jugo_en_ciclo", "ciclos_sin_jugar",
                   "partidos", "foto_fase", "valor_actual", "activo", "fin_ciclo", "motivo_fin", "desde_ciclo", "hasta_ciclo",
                   "prima", "origen", "pidio_salida_ciclo", "eventos_ciclo", "eventos_marcas", "tv_bono_hasta_seq")

_cache_aportes: "OrderedDict[str, dict]" = OrderedDict()
MAX_CACHE_APORTES = 3000


# --- Aporte por partido (compartido por todos los universos) -------------------------------------
def aportes_de(juego_ids: List[str]) -> Dict[str, dict]:
    """{juego_id: aporte} (corporativo_reglas.aporte_partido), cargando de una sola vez los que no estén en caché."""
    from services.estadisticas_service import PROYECCION_JUEGOS_MUNDIAL, _agregar_jugadores_mundial

    faltan = [j for j in juego_ids if j not in _cache_aportes and ObjectId.is_valid(j)]
    if faltan:
        juegos = list(db["juegos"].find({"_id": {"$in": [ObjectId(j) for j in faltan]}}, PROYECCION_JUEGOS_MUNDIAL))
        por_partido = R.separar_por_partido(_agregar_jugadores_mundial(juegos)) if juegos else {}
        posicion = {jid: d.get("posicion_id") for jid, d in valores()["info_jugadores"].items()}
        for juego in juegos:
            jid = str(juego["_id"])
            _cache_aportes[jid] = R.aporte_partido(juego, por_partido.get(jid, {}), posicion)
        while len(_cache_aportes) > MAX_CACHE_APORTES:
            _cache_aportes.popitem(last=False)
    return {j: _cache_aportes[j] for j in juego_ids if j in _cache_aportes}


def paises_que_jugaron(ciclo: int) -> set:
    """Selecciones que jugaron en los partidos del ciclo (desde el registro: igual aunque el ciclo se procese en dos visitas)."""
    entradas = db["corp_registro_partidos"].find({"seq": {"$gt": (ciclo - 1) * C.PARTIDOS_POR_CICLO,
                                                          "$lte": ciclo * C.PARTIDOS_POR_CICLO}}, {"juego_id": 1})
    aportes = aportes_de([e["juego_id"] for e in entradas])
    return {pid for a in aportes.values() for pid in a["selecciones"]}


# --- Estado en memoria de un universo ------------------------------------------------------------
class Estado:
    def __init__(self, universo_id):
        self.uid = universo_id
        self.corps = {c["sigla"]: c for c in db["corp_corporativos"].find({"universo_id": universo_id})}
        self.contratos = list(db["corp_contratos"].find({"universo_id": universo_id, "activo": True}))
        self.nuevos: List[dict] = []
        self.movimientos: List[dict] = []
        self.sucios = set()
        self._indexar()
        for c in self.corps.values():
            c.setdefault("ciclo_actual", ciclo_vacio())
            for k, v0 in ciclo_vacio().items():
                c["ciclo_actual"].setdefault(k, v0)

    def _indexar(self):
        self.por_seleccion = {c["ref_id"]: c for c in self.contratos if c["tipo"] == "seleccion" and c["activo"]}
        self.por_jugador = {c["ref_id"]: c for c in self.contratos if c["tipo"] == "jugador" and c["activo"]}

    def agregar_contrato(self, doc: dict) -> dict:
        doc.setdefault("_id", ObjectId())   # _id desde ya: el mercado del mismo ciclo puede referenciarlo
        self.contratos.append(doc)
        self.nuevos.append(doc)
        self._indexar()
        return doc

    def terminar_contrato(self, contrato: dict, ciclo: int, motivo: str) -> None:
        contrato.update(activo=False, fin_ciclo=ciclo, motivo_fin=motivo)
        self.tocar(contrato)
        self._indexar()

    def ocupados(self) -> set:
        return {(c["tipo"], c["ref_id"]) for c in self.contratos if c["activo"]}

    def tocar(self, contrato):
        self.sucios.add(id(contrato))

    def mover(self, sigla: str, ciclo: int, tipo: str, monto: int, detalle: str, ref: dict = None):
        """Asiento del libro contable; solo se guardan los del corporativo del usuario (los de la IA van agregados por ciclo)."""
        if self.corps[sigla].get("es_del_usuario"):
            self.movimientos.append({"universo_id": self.uid, "sigla": sigla, "ciclo": ciclo, "tipo": tipo, "monto": int(monto),
                                     "detalle": detalle, **(ref or {}), "creado_en": datetime.utcnow()})

    def guardar(self):
        ops = []
        ids_nuevos = {id(c) for c in self.nuevos}
        for c in self.contratos:
            if id(c) in self.sucios and id(c) not in ids_nuevos:
                ops.append(UpdateOne({"_id": c["_id"]}, {"$set": {k: c[k] for k in CAMPOS_CONTRATO if k in c}}))
        if ops:
            db["corp_contratos"].bulk_write(ops, ordered=False)
        if self.nuevos:
            db["corp_contratos"].insert_many(self.nuevos)
            self.nuevos = []
        db["corp_corporativos"].bulk_write([UpdateOne({"_id": c["_id"]}, {"$set": {k: c[k] for k in CAMPOS_CORP if k in c}})
                                            for c in self.corps.values()], ordered=False)
        if self.movimientos:
            db["corp_movimientos"].insert_many(self.movimientos)
            self.movimientos = []
        self.sucios.clear()


def ciclo_vacio() -> dict:
    """Acumulados del ciclo en curso de un corporativo. 'extra' = patrocinios de marcas, acuerdos y giras (ingresos);
    'gastos_extra' = costos de las giras; 'comision_ceo' = comisión de las marcas que cobra el CEO con el sueldo."""
    return {"renta": 0, "honorarios": 0, "amortizacion": 0, "sueldo": 0, "impago": False, "fichajes": 0,
            "patrocinio": 0, "extra": 0, "gastos_extra": 0, "fama": {}, "comision_ceo": 0, "marcas_bruto": 0, "tv": 0, "tv_invitados": 0}


# --- Partido -------------------------------------------------------------------------------------
def procesar_partido(estado: Estado, aporte: dict, ciclo: int, juego_id: str) -> None:
    v = valores()
    for pais_id, resultado in aporte["selecciones"].items():
        c = estado.por_seleccion.get(pais_id)
        if not c:
            continue
        valor = v["selecciones"].get(pais_id, 0)
        renta = R.renta_seleccion(valor, resultado)
        _acreditar(estado, c, renta, ciclo)
        _cobrar_honorario(estado, c, R.honorario_partido("seleccion", valor))   # honorario ligado a la actividad
        c["jugo_en_ciclo"] = True
        if (aporte.get("diferencia") or {}).get(pais_id, 0) <= -3:   # goleada en contra: la marca de un acuerdo puede cortar
            c.setdefault("eventos_ciclo", {})["goleada"] = True
            c.setdefault("eventos_marcas", {})["goleada"] = True   # la ronda de marcas (cada 4 partidos) los ve y los limpia
        if resultado == "victoria":
            c["satisfaccion"] = min(100, c["satisfaccion"] + C.SATISFACCION["victoria_seleccion"])
        nombre = v["info_paises"].get(pais_id, {}).get("nombre", "?")
        estado.mover(c["sigla"], ciclo, "RENTA_PARTIDO", renta, f"{nombre}: {resultado}", {"juego_id": juego_id, "ref_id": pais_id, "tipo_ref": "seleccion"})
    for jugador_id, ap in aporte["jugadores"].items():
        c = estado.por_jugador.get(jugador_id)
        if not c:
            continue
        valor_j = v["jugadores"].get(jugador_id, 0)
        renta = R.renta_jugador(valor_j, ap)
        _acreditar(estado, c, renta, ciclo)
        _cobrar_honorario(estado, c, R.honorario_partido("jugador", valor_j))
        c["jugo_en_ciclo"] = True
        c["partidos"] = c.get("partidos", 0) + 1
        if ap.get("roja"):
            c.setdefault("eventos_ciclo", {})["roja"] = True
            c.setdefault("eventos_marcas", {})["roja"] = True
        # Fama del CEO por una actuación destacada de su representado (hat-trick, gol + asistencia, valla invicta ganando)
        pais_j = v["info_jugadores"].get(jugador_id, {}).get("pais_id")
        destacada = ap.get("gol", 0) >= 3 or (ap.get("gol") and ap.get("asistencia")) or \
            (ap.get("valla_invicta") and aporte["selecciones"].get(pais_j) == "victoria")
        if destacada and estado.corps[c["sigla"]].get("es_del_usuario"):
            estado.corps[c["sigla"]]["ciclo_actual"].setdefault("fama", {})["actuacion"] = v["info_jugadores"].get(jugador_id, {}).get("nombre")
        c["satisfaccion"] = min(100, c["satisfaccion"] + C.SATISFACCION["partido_jugado"])
        hechos = [t for t, k in (("gol", "gol"), ("asist.", "asistencia"), ("valla invicta", "valla_invicta"), ("roja", "roja")) if ap.get(k)]
        nombre = v["info_jugadores"].get(jugador_id, {}).get("nombre", "?")
        estado.mover(c["sigla"], ciclo, "RENTA_PARTIDO", renta, f"{nombre}: jugó" + (f" ({', '.join(hechos)})" if hechos else ""),
                     {"juego_id": juego_id, "ref_id": jugador_id, "tipo_ref": "jugador"})


def _cobrar_honorario(estado: Estado, contrato: dict, h: int) -> None:
    """Honorario por partido jugado: se descuenta junto con la renta (el ciclo lo suma al asiento HONORARIOS)."""
    corp = estado.corps[contrato["sigla"]]
    corp["capital"] -= h
    corp["ciclo_actual"]["honorarios"] += h
    contrato["honorarios_total"] = contrato.get("honorarios_total", 0) + h
    estado.tocar(contrato)


def popularidad(tipo: str, ref_id: int, valor: int) -> float:
    """Popularidad para el patrocinio: selecciones por sus aficionados, jugadores por su valor."""
    if tipo == "seleccion":
        return R.popularidad_seleccion(valores()["info_paises"].get(ref_id, {}).get("aficionados"))
    return R.popularidad_jugador(valor)


def _acreditar(estado: Estado, contrato: dict, renta: int, ciclo: int) -> None:
    corp = estado.corps[contrato["sigla"]]
    corp["capital"] += renta
    corp["ciclo_actual"]["renta"] += renta
    contrato["renta_total"] = contrato.get("renta_total", 0) + renta
    contrato["renta_ciclo"] = contrato.get("renta_ciclo", 0) + renta
    estado.tocar(contrato)


# --- Cierre de ciclo -----------------------------------------------------------------------------
def cerrar_ciclo_economia(estado: Estado, ciclo: int) -> None:
    """Fase de fase/eliminación, honorarios, satisfacción, vencimientos (IA renueva o suelta), ROI y cotización."""
    v = valores()
    fases = {d["id"]: d for d in db["internacional"].find({}, {"_id": 0, "id": 1, "fase_eliminatoria": 1, "estado": 1})}
    jugaron = paises_que_jugaron(ciclo)

    for c in estado.contratos:
        if not c["activo"]:
            continue
        corp = estado.corps[c["sigla"]]
        valor = (v["selecciones"] if c["tipo"] == "seleccion" else v["jugadores"]).get(c["ref_id"], 0)
        # Avance / eliminación de fase (solo selecciones): se compara con la última foto que vio el contrato
        if c["tipo"] == "seleccion" and c["ref_id"] in fases:
            f = fases[c["ref_id"]]
            foto = (f.get("fase_eliminatoria"), f.get("estado"))
            previa = tuple(c["foto_fase"]) if c.get("foto_fase") else None
            if previa and foto != previa:
                eliminado = str(foto[1] or "").startswith("ELIMINADO") and not str(previa[1] or "").startswith("ELIMINADO")
                avanzo = (foto[0] or 0) > (previa[0] or 0) or ("CALIFICADO" in str(foto[1] or "") and "CALIFICADO" not in str(previa[1] or ""))
                if eliminado:
                    c.setdefault("eventos_ciclo", {})["eliminada"] = True
                elif avanzo and corp.get("es_del_usuario"):
                    corp["ciclo_actual"].setdefault("fama", {})["avance"] = v["info_paises"].get(c["ref_id"], {}).get("nombre")
                if eliminado or avanzo:
                    renta = R.renta_fase(valor, avanzo and not eliminado)
                    _acreditar(estado, c, renta, ciclo)
                    nombre = v["info_paises"].get(c["ref_id"], {}).get("nombre", "?")
                    estado.mover(c["sigla"], ciclo, "FASE", renta, f"{nombre}: {'eliminada' if eliminado else 'avanzó de fase'}",
                                 {"ref_id": c["ref_id"], "tipo_ref": "seleccion"})
            c["foto_fase"] = list(foto)
        # Patrocinio del ciclo (juegue o no; la campaña de marketing vigente lo multiplica)
        mult = C.MARKETING_BONO_PATROCINIO if (corp.get("marketing_hasta_ciclo") or 0) >= ciclo else 1.0
        pat = R.patrocinio(c["tipo"], valor, popularidad(c["tipo"], c["ref_id"], valor), mult)
        corp["capital"] += pat
        corp["ciclo_actual"]["patrocinio"] += pat
        c["renta_total"] = c.get("renta_total", 0) + pat
        # Mantenimiento del ciclo (juegue o no: el resto del honorario se cobró por partido jugado) + amortización de la prima
        h = R.honorario_mantenimiento(c["tipo"], valor)
        if corp["capital"] >= h:
            corp["capital"] -= h
            corp["ciclo_actual"]["honorarios"] += h
            c["honorarios_total"] = c.get("honorarios_total", 0) + h
        else:
            corp["ciclo_actual"]["impago"] = True
            c["satisfaccion"] = max(0, c["satisfaccion"] + C.SATISFACCION["impago"])
        duracion = max(1, c["hasta_ciclo"] - c["desde_ciclo"])
        corp["ciclo_actual"]["amortizacion"] += c.get("prima", 0) / duracion
        # Minutos: en eliminatorias una selección juega cada varios ciclos, así que "no jugó" solo cuenta si su
        # selección jugó y él no entró (banco) o si su selección está eliminada / fuera del Mundial.
        pais = c["ref_id"] if c["tipo"] == "seleccion" else v["info_jugadores"].get(c["ref_id"], {}).get("pais_id")
        eliminado = pais not in fases or str(fases[pais].get("estado") or "").startswith("ELIMINADO")
        banco = c["tipo"] == "jugador" and pais in jugaron and not c.get("jugo_en_ciclo")
        if c.get("jugo_en_ciclo"):
            c["ciclos_sin_jugar"] = 0
        elif eliminado or banco:
            c["ciclos_sin_jugar"] = c.get("ciclos_sin_jugar", 0) + 1
            c["satisfaccion"] = max(0, c["satisfaccion"] + C.SATISFACCION["ciclo_sin_jugar"])
        if C.CORPORATIVO_POR_SIGLA[c["sigla"]]["tier"] == "A":
            c["satisfaccion"] = min(100, c["satisfaccion"] + C.SATISFACCION["tier_a"])
        c["jugo_en_ciclo"] = False
        c["renta_ciclo"] = 0
        c["valor_actual"] = valor
        estado.tocar(c)

    # Acuerdos publicitarios, giras y aporte de aficionados de las giras (corporativo_acciones_service)
    from services import corporativo_acciones_service as acciones   # import diferido: acciones importa este módulo
    acciones.cerrar_ciclo_acciones(estado, ciclo)

    for sigla, corp in estado.corps.items():
        honor = sum(1 for x in estado.contratos if x["activo"] and x["sigla"] == sigla)
        ca = corp["ciclo_actual"]
        if ca["honorarios"]:
            estado.mover(sigla, ciclo, "HONORARIOS", -ca["honorarios"], f"Honorarios de {honor} representados (mantenimiento y partidos jugados)")
        if ca["patrocinio"]:
            estado.mover(sigla, ciclo, "PATROCINIO", ca["patrocinio"], f"Patrocinios de {honor} representados (juegue o no)")
        utilidad = (ca["renta"] + ca["patrocinio"] + ca["extra"] - ca["honorarios"] - ca["amortizacion"] - ca["sueldo"]
                    - ca["gastos_extra"])
        if utilidad < 0:
            for x in estado.contratos:
                if x["activo"] and x["sigla"] == sigla:
                    x["satisfaccion"] = max(0, x["satisfaccion"] + C.SATISFACCION["ciclo_perdidas"])
                    estado.tocar(x)
        corp["_utilidad"] = utilidad

    _vencimientos(estado, ciclo)


def _vencimientos(estado: Estado, ciclo: int) -> None:
    """Contratos que vencen este ciclo: la IA renueva a quien rindió; los del usuario vencen (renovar es acción suya)."""
    v = valores()
    for c in list(estado.contratos):
        if not c["activo"] or c["hasta_ciclo"] > ciclo:
            continue
        corp = estado.corps[c["sigla"]]
        nombre = (v["info_paises"].get(c["ref_id"], {}) if c["tipo"] == "seleccion" else v["info_jugadores"].get(c["ref_id"], {})).get("nombre", "?")
        rindio = c.get("renta_total", 0) >= 0.8 * c.get("honorarios_total", 0)
        valor = (v["selecciones"] if c["tipo"] == "seleccion" else v["jugadores"]).get(c["ref_id"], 0)
        prima = R.prima_renovacion(valor, c.get("satisfaccion", C.SATISFACCION_INICIAL))
        if not corp.get("es_del_usuario") and rindio and corp["capital"] >= prima:
            corp["capital"] -= prima
            duracion = R.semilla(estado.uid, "renueva", c["sigla"], c["ref_id"], ciclo).randint(*C.DURACION_CONTRATO)
            c.update(desde_ciclo=ciclo, hasta_ciclo=ciclo + duracion, prima=prima, renta_total=0, honorarios_total=0,
                     origen="RENOVACION")
        else:
            c.update(activo=False, fin_ciclo=ciclo, motivo_fin="VENCIDO")
            if corp.get("es_del_usuario"):
                from services.corporativo_universo_service import avisar
                avisar(estado.uid, ciclo, "VENCIDO", f"Se fue {nombre}",
                       f"Venció el contrato de representación de {nombre} y quedó libre.", "bi-box-arrow-right",
                       clave=f"vencido:{c['_id']}")
        estado.tocar(c)
    estado._indexar()


def cerrar_cuentas(estado: Estado, ciclo: int) -> None:
    """ROI del ciclo, historial y cotización (precio = fundamentos x sentimiento, con banda por ciclo)."""
    from services.corporativo_universo_service import valor_cartera
    for sigla, corp in estado.corps.items():
        activos = [c for c in estado.contratos if c["activo"] and c["sigla"] == sigla]
        cartera = valor_cartera(activos)
        patrimonio_inicio = corp.get("patrimonio", corp["capital"] + cartera)
        utilidad = corp.pop("_utilidad", 0)
        utilidad_op = corp.pop("_utilidad_op", utilidad)
        roi = utilidad / max(patrimonio_inicio, 1)
        rng = R.semilla(estado.uid, "cotiza", sigla, ciclo)
        noticias = -0.15 if corp["ciclo_actual"]["impago"] else 0
        # El sentimiento sigue el ROI MEDIO de la ventana (un ciclo suelto sin partidos no hunde la acción)
        rois = [h.get("roi", 0) for h in (corp.get("historial") or [])[-(C.CICLOS_VENTANA_ROI - 1):]] + [roi]
        corp["sentimiento"] = R.nuevo_sentimiento(corp.get("sentimiento", 1.0), sum(rois) / len(rois), noticias, rng)
        # El precio suma la renta esperada de los partidos YA programados de su cartera en los próximos ciclos
        esperada = renta_esperada(activos)
        nuevo = R.precio_accion(corp["capital"] + esperada, cartera, corp["sentimiento"])
        anterior = corp.get("precio") or nuevo
        corp["precio"] = R.limitar_banda(nuevo, anterior)
        corp["variacion_ciclo"] = round(corp["precio"] / anterior - 1, 4) if anterior else 0
        corp["patrimonio"] = corp["capital"] + cartera
        hist = corp.get("historial", [])
        hist.append({"ciclo": ciclo, "capital": int(corp["capital"]), "cartera": cartera, "utilidad": int(utilidad), "utilidad_op": int(utilidad_op),
                     "roi": round(roi, 5), "precio": corp["precio"], "renta": corp["ciclo_actual"]["renta"],
                     "honorarios": corp["ciclo_actual"]["honorarios"], "impago": corp["ciclo_actual"]["impago"],
                     "patrocinio": corp["ciclo_actual"]["patrocinio"], "extra": corp["ciclo_actual"]["extra"],
                     "gastos_extra": corp["ciclo_actual"]["gastos_extra"], "renta_esperada": esperada,
                     "fama": corp["ciclo_actual"].get("fama") or {}, "tv": corp["ciclo_actual"].get("tv", 0),
                     "tv_invitados": corp["ciclo_actual"].get("tv_invitados", 0)})
        corp["historial"] = hist[-60:]
        corp["ciclo_actual"] = ciclo_vacio()


def renta_esperada(contratos: list) -> int:
    """Renta neta esperada de los partidos ya programados de estos contratos en los próximos CICLOS_RENTA_ESPERADA
    ciclos (los jugadores cuentan al 60%: no siempre entran). La usa la cotización y las vistas."""
    from services.corporativo_mercado_service import partidos_en_ciclos
    v = valores()
    total = 0
    for c in contratos:
        if c["tipo"] == "seleccion":
            total += partidos_en_ciclos(c["ref_id"], C.CICLOS_RENTA_ESPERADA) * R.renta_esperada_partido("seleccion", v["selecciones"].get(c["ref_id"], 0))
        else:
            pais = v["info_jugadores"].get(c["ref_id"], {}).get("pais_id")
            total += 0.6 * partidos_en_ciclos(pais, C.CICLOS_RENTA_ESPERADA) * R.renta_esperada_partido("jugador", v["jugadores"].get(c["ref_id"], 0))
    return int(total)
