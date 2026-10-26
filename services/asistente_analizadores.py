"""
Analizadores del asistente "El Profe": uno por módulo, todos de SOLO LECTURA. Cada uno recibe el Contexto (precargado
una sola vez por consulta) y devuelve una lista de consejos (forma en services/asistente_reglas.py). Cada consejo dice
desde qué nivel se ve ('nivel_minimo'): los riesgos y pendientes de un módulo salen desde el Vistazo; las
oportunidades más finas, desde el Análisis o el Informe profundo.

Sin spoilers: los partidos próximos son los de estado "creado" (no simulados); nunca se lee 'resultado' de un partido
que no terminó ni el que está en transmisión.
"""
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional

import certifi
from bson import ObjectId
from pymongo.mongo_client import MongoClient

from config import corporativos as CC
from config.asistente import MODULOS_ASISTENTE, TOPE_CAMBIOS_AVISO
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')

logger = logging.getLogger(__name__)


# ==========================================
# Contexto de una consulta
# ==========================================
class Contexto:
    """Lo que comparten todos los analizadores: usuario, Mundial activo, partidos jugados y próximos partidos."""

    def __init__(self, usuario: dict, horizonte: int):
        self.uid = ObjectId(str(usuario["_id"]))
        self.uid_str = str(usuario["_id"])
        doc = db['usuarios'].find_one({"_id": self.uid}, {"username": 1, "monto": 1, "recompensas_pendientes": 1,
                                                          "sobres_gratis": 1, "sobres_platino": 1}) or {}
        self.usuario = doc
        self.nombre = doc.get("username") or usuario.get("username") or ""
        self.saldo = int(doc.get("monto") or 0)
        self.permisos = set(usuario.get("permisos") or [])
        mundial = db['mundiales'].find_one({"activo": True}, {"_id": 1})
        self.mundial_id = str(mundial["_id"]) if mundial else None
        self.jugados = db['juegos'].count_documents({"mundial_id": self.mundial_id, "estado": "finalizado",
                                                     "transmision.estado": {"$ne": "in_progress"}}) if self.mundial_id else 0
        self.horizonte = horizonte
        self.proximos = list(db['juegos'].find(
            {"mundial_id": self.mundial_id, "estado": "creado"},
            {"equipo_local": 1, "equipo_visitante": 1, "fecha": 1, "hora": 1, "fase_id": 1, "ubicacion": 1, "grupo": 1,
             "confederacion_id": 1}).sort([("fecha", 1), ("hora", 1)]).limit(horizonte)) if self.mundial_id else []
        self._cache: Dict[str, object] = {}

    def puede(self, modulo: str) -> bool:
        permiso = MODULOS_ASISTENTE.get(modulo, {}).get("permiso")
        return not permiso or permiso in self.permisos

    def memo(self, clave: str, fn: Callable):
        if clave not in self._cache:
            self._cache[clave] = fn()
        return self._cache[clave]


def consejo(modulo: str, tipo: str, titulo: str, texto: str, url: str, cta: str = "Ir", *, porque: Optional[List[str]] = None,
            numeros: Optional[List[str]] = None, valor: Optional[int] = None, confianza: str = "alta", riesgo: str = "bajo",
            urgencia: int = 0, nivel_minimo: str = "VISTAZO", clave: str = "", **extra) -> dict:
    return {"clave": clave or f"{modulo}:{titulo}", "modulo": modulo, "tipo": tipo, "titulo": titulo, "texto": texto,
            "porque": porque or [], "numeros": numeros or [], "url": url, "cta": cta, "valor": valor, "confianza": confianza,
            "riesgo": riesgo, "urgencia": urgencia, "nivel_minimo": nivel_minimo, **extra}


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


# ==========================================
# Misiones (check-in, trivia, beca)
# ==========================================
def analizar_misiones(ctx: Contexto) -> List[dict]:
    from services import rewards_service, trivia_service
    estado = rewards_service.obtener_daily_status(ctx.uid_str)
    salida = []
    if not estado["ya_reclamo_checkin_hoy"]:
        cierra_racha = estado["dias_para_bono_especial"] == 1
        bono = rewards_service.BONO_CHECKIN_DIARIO + (rewards_service.BONO_RACHA_ESPECIAL if cierra_racha else 0)
        salida.append(consejo(
            "misiones", "GRATIS", "Haz el check-in de hoy",
            "Son puntos regalados: un clic y entran al saldo." + (" Hoy además cierras la racha de 5 días." if cierra_racha else ""),
            "/misiones/", "Hacer check-in", porque=[f"Racha actual: {estado['racha_actual']} días"],
            numeros=[f"+{bono} pts"], valor=bono, urgencia=60, clave="misiones:checkin"))
    if estado["trivia_sesiones_restantes"] > 0:
        maximo = estado["trivia_sesiones_restantes"] * trivia_service.PUNTOS_MAXIMOS_SESION
        salida.append(consejo(
            "misiones", "GRATIS", f"Juega la trivia ({_plural(estado['trivia_sesiones_restantes'], 'sesión', 'sesiones')} hoy)",
            "Tres preguntas sobre el torneo; cada acierto suma.", "/misiones/", "Jugar trivia",
            porque=["Las preguntas salen de datos reales del Mundial"], numeros=[f"Hasta +{maximo} pts"], valor=maximo,
            confianza="media", urgencia=30, clave="misiones:trivia"))
    if estado["puede_reclamar_beca_emergencia"]:
        salida.append(consejo(
            "misiones", "GRATIS", "Pide la beca de emergencia",
            "Estás sin saldo y sin inversiones: te corresponde la beca para volver a jugar.", "/misiones/", "Pedir beca",
            numeros=[f"+{rewards_service.MONTO_BECA_EMERGENCIA} pts"], valor=rewards_service.MONTO_BECA_EMERGENCIA,
            urgencia=90, clave="misiones:beca"))
    return salida


# ==========================================
# Niveles (recompensas y sobres regalados)
# ==========================================
def analizar_niveles(ctx: Contexto) -> List[dict]:
    salida = []
    pendientes = int(ctx.usuario.get("recompensas_pendientes") or 0)
    if pendientes > 0:
        salida.append(consejo(
            "niveles", "GRATIS", f"Reclama {_plural(pendientes, 'recompensa', 'recompensas')} de nivel",
            "Subiste de nivel y el premio sigue esperando.", "/niveles/", "Reclamar",
            porque=["Las recompensas no vencen, pero el saldo te sirve ahora"], urgencia=70, clave="niveles:recompensas"))
    sobres = int(ctx.usuario.get("sobres_gratis") or 0)
    platino = int(ctx.usuario.get("sobres_platino") or 0)
    if (sobres or platino) and "album" in ctx.permisos:
        partes = ([_plural(sobres, "sobre gratis", "sobres gratis")] if sobres else []) + \
                 ([_plural(platino, "sobre Platino", "sobres Platino")] if platino else [])
        salida.append(consejo(
            "album", "GRATIS", f"Abre tus {' y '.join(partes)}",
            "Ya son tuyos: cada estampa nueva puede activar una sinergia ×1,5 en tus inversiones.", "/album-estampas/sobres",
            "Abrir sobres", porque=["Los sobres regalados no se cobran"] + (["El Platino trae un escudo garantizado"] if platino else []),
            urgencia=50, clave="album:sobres_regalo"))
    return salida


# ==========================================
# Selecciones (portafolio)
# ==========================================
def analizar_selecciones(ctx: Contexto) -> List[dict]:
    from services import ownership_service as OS
    inversiones = list(db['team_ownerships'].find({"user_id": ctx.uid, "status": OS.ESTADO_INVERSION_ACTIVO},
                                                  {"pais_id": 1, "purchase_price": 1, "current_value": 1}))
    if not inversiones:
        return []
    contexto = OS._contexto_paises([i["pais_id"] for i in inversiones])
    paises = {p["id"]: p for p in db['paises'].find({"id": {"$in": [i["pais_id"] for i in inversiones]}}, {"id": 1, "nombre": 1, "bandera": 1})}
    salida = []
    for inv in inversiones:
        pid = inv["pais_id"]
        estado = (contexto.get(pid) or {}).get("estado") or {}
        if estado.get("codigo") not in ("eliminado", "fuera"):
            continue
        p = paises.get(pid, {})
        valor = int(inv.get("current_value") or 0)
        plus = valor - int(inv.get("purchase_price") or 0)
        motivo = "Quedó eliminada del Mundial" if estado["codigo"] == "eliminado" else "No juega este Mundial"
        salida.append(consejo(
            "selecciones", "URGENTE", f"Vende {p.get('nombre', 'tu selección')}",
            "Ya no gana partidos ni avanza de fase: es saldo parado que puedes poner a trabajar en otra.",
            "/selecciones/portafolio", "Ver en mi portafolio", porque=[motivo, "No vuelve a cobrar dividendos este Mundial"],
            numeros=[f"Venta hoy: {valor:,} pts", f"{plus:+,} vs. la compra"], valor=valor, urgencia=80,
            clave=f"selecciones:vender:{pid}", pais_id=pid, bandera=p.get("bandera")))
    return salida


# ==========================================
# Once Ideal
# ==========================================
def analizar_once_ideal(ctx: Contexto) -> List[dict]:
    from services import fantasy_service as FS
    if not ctx.mundial_id:
        return []
    equipo = db['fantasy_teams'].find_one({"user_id": ctx.uid, "mundial_id": ctx.mundial_id})
    if not equipo:   # equipos viejos por fase (se migran al abrir /once-ideal)
        equipo = db['fantasy_teams'].find_one({"user_id": ctx.uid, "mundial_id": {"$exists": False}}, sort=[("fase_id", -1)])
    if not equipo:
        return [consejo(
            "once_ideal", "OPORTUNIDAD", "Arma tu Once Ideal",
            "Armarlo es gratis y suma puntos en todos los partidos del Mundial que quedan.", "/once-ideal/", "Armar equipo",
            porque=["Cada partido que pasa sin equipo son puntos que no sumas"], confianza="alta", urgencia=35,
            clave="once_ideal:armar")]

    salida = []
    eliminados = FS.paises_eliminados()
    jugadores = list(db['jugadores'].find({"id": {"$in": equipo.get("lineup") or []}}, {"id": 1, "nombre": 1, "pais_id": 1}))
    fuera = [j for j in jugadores if j.get("pais_id") in eliminados]
    if fuera:
        nombres = ", ".join(j.get("nombre", "?") for j in fuera[:4]) + ("…" if len(fuera) > 4 else "")
        salida.append(consejo(
            "once_ideal", "URGENTE", f"Cambia {_plural(len(fuera), 'jugador eliminado', 'jugadores eliminados')} de tu Once",
            "Sus selecciones ya no juegan: no suman más puntos. Reemplazarlos no te cuesta cambios ni saldo.",
            "/once-ideal/", "Ir al Once Ideal", porque=[nombres], numeros=[f"{len(fuera)} de 11 sin sumar"],
            urgencia=85, clave="once_ideal:eliminados", jugador_id=fuera[0]["id"], pais_id=fuera[0].get("pais_id")))

    # Cambios gratis acumulados (cálculo de solo lectura de lo que acreditaría _equipo_del_mundial)
    jornada = FS.jornada_actual()
    credito = equipo.get("jornada_credito", jornada["numero"])
    cambios = min(FS.TOPE_CAMBIOS_GRATIS, int(equipo.get("cambios_gratis_disponibles") or 0)
                  + max(0, jornada["numero"] - credito) * FS.CAMBIOS_GRATIS_POR_JORNADA)
    if cambios >= TOPE_CAMBIOS_AVISO:
        al_tope = cambios >= FS.TOPE_CAMBIOS_GRATIS
        salida.append(consejo(
            "once_ideal", "OPORTUNIDAD", f"Usa tus {cambios} cambios gratis",
            ("Llegaste al tope: los de la próxima jornada se pierden." if al_tope else "Estás cerca del tope y los que lo pasen se pierden.")
            + " Cambia a los que menos suman.", "/once-ideal/", "Hacer cambios",
            porque=[f"Faltan {jornada['faltan']} partidos para la jornada {jornada['numero'] + 1}"],
            numeros=[f"{cambios}/{FS.TOPE_CAMBIOS_GRATIS} cambios gratis", f"Cada cambio extra cuesta {FS.COSTO_CAMBIO_EXTRA} pts"],
            valor=FS.COSTO_CAMBIO_EXTRA * FS.CAMBIOS_GRATIS_POR_JORNADA if al_tope else None,
            urgencia=55 if al_tope else 25, clave="once_ideal:cambios"))
    return salida


# ==========================================
# Corporativo (carrera de CEO)
# ==========================================
def analizar_corporativo(ctx: Contexto) -> List[dict]:
    from services import corporativo_universo_service as U
    from services.corporativo_fichajes_service import nombre_ref
    universo = U.obtener_universo(ctx.uid_str)
    if not universo:
        return [consejo(
            "corporativo", "OPORTUNIDAD", "Empieza tu carrera de CEO",
            "Dirigir un corporativo te paga un sueldo por ciclo, además de lo que ganes en el resto del juego.",
            "/corporativo/", "Buscar empleo", porque=["Las primeras ofertas llegan a los pocos partidos"],
            confianza="media", urgencia=10, clave="corporativo:empezar")]

    salida = []
    ciclo = U.ciclo_en_curso(universo)
    ofertas_empleo = list(db['corp_ofertas_empleo'].find({"universo_id": ctx.uid_str, "estado": "PENDIENTE"},
                                                         {"sigla": 1, "tipo": 1, "vence_ciclo": 1, "sueldo": 1}))
    if ofertas_empleo:
        vence = min(o["vence_ciclo"] for o in ofertas_empleo) - ciclo + 1
        buscando = universo.get("estado") == "BUSCANDO"
        salida.append(consejo(
            "corporativo", "URGENTE" if buscando else "OPORTUNIDAD",
            f"Responde {_plural(len(ofertas_empleo), 'oferta de empleo', 'ofertas de empleo')}",
            ("Estás sin cargo: aceptar una oferta te pone a cobrar sueldo." if buscando
             else "Otros corporativos te quieren: compara antes de que venzan."),
            "/corporativo/", "Ver ofertas", porque=[", ".join(sorted({o["sigla"] for o in ofertas_empleo}))],
            numeros=[f"La primera vence en {_plural(max(vence, 0), 'ciclo', 'ciclos')}"],
            urgencia=75 if buscando else 40, clave="corporativo:ofertas_empleo"))

    cargo = universo.get("cargo")
    if not cargo or universo.get("estado") != "EN_CARGO":
        return salida
    sigla = cargo["sigla"]
    corp = db['corp_corporativos'].find_one({"universo_id": ctx.uid_str, "sigla": sigla}, {"confianza": 1}) or {}
    confianza = corp.get("confianza")
    if confianza is not None and confianza < CC.CONFIANZA_ULTIMATUM:
        salida.append(consejo(
            "corporativo", "URGENTE", f"El directorio de {sigla} está por despedirte",
            "La confianza está en zona de ultimátum: cumple los objetivos y cuida el ROI este ciclo.", "/corporativo/",
            "Ver objetivos", porque=["Si baja del mínimo, te despiden al cierre del ciclo"],
            numeros=[f"Confianza {confianza}/100 (despido < {CC.CONFIANZA_DESPIDO})"], urgencia=95, clave="corporativo:ultimatum"))

    por_vencer = [c for c in U.contratos_activos(ctx.uid_str, sigla) if c["hasta_ciclo"] - ciclo + 1 <= CC.CICLOS_AVISO_RENOVACION]
    if por_vencer:
        # la misma recomendación que la cartera (corporativo_reglas._senal_cartera): renovar / esperar / no renovar
        from services import corporativo_service as CS
        from services.corporativo_mercado_service import valores as _valores
        v, ctxp = _valores(), CS._contexto_partidos()
        decision = {}
        for c in por_vencer:
            valor = (v["selecciones"] if c["tipo"] == "seleccion" else v["jugadores"]).get(c["ref_id"], 0)
            sn = CS.senal_de(c["tipo"], c["ref_id"], valor, CS.juego_de(c["tipo"], c["ref_id"], ctxp), ctxp, c, ciclo)
            decision.setdefault((sn.get("renovacion") or {}).get("decision", "renovar"), []).append(c)
        renovar, esperar = decision.get("renovar", []), decision.get("esperar", [])
        if renovar:
            salida.append(consejo(
                "corporativo", "OPORTUNIDAD", f"Renueva {_plural(len(renovar), 'contrato que conviene', 'contratos que convienen')}",
                "Vienen rindiendo bien y su contrato está por vencer: si no los renuevas, se van libres y pierdes su renta.",
                "/corporativo/", "Ver cartera", porque=[", ".join(nombre_ref(c["tipo"], c["ref_id"]) for c in renovar[:4])],
                urgencia=45, clave="corporativo:renovar"))
        if esperar:
            salida.append(consejo(
                "corporativo", "GRATIS", f"Espera antes de renovar a {_plural(len(esperar), 'representado', 'representados')}",
                "Sus resultados son mixtos y todavía juegan antes de que venza el contrato: velos jugar y decide después.",
                "/corporativo/", "Ver cartera", porque=[", ".join(nombre_ref(c["tipo"], c["ref_id"]) for c in esperar[:4])],
                urgencia=20, clave="corporativo:esperar_renovar"))

    salida += _consejos_corporativo_v2(ctx, sigla, ciclo, nombre_ref)

    for o in db['corp_ofertas'].find({"universo_id": ctx.uid_str, "sigla": sigla, "estado": "PENDIENTE",
                                      "tipo": {"$in": ["SALIDA", "OFERTA_IA", "CONTRAOFERTA", "PROPUESTA"]}}):
        nombre = nombre_ref(o.get("ref_tipo", "jugador"), o.get("ref_id"))
        vence = o.get("vence_ciclo", ciclo) - ciclo + 1
        if o["tipo"] == "SALIDA":
            salida.append(consejo(
                "corporativo", "URGENTE", f"{nombre} quiere irse", "Si lo retienes sin resolver, su satisfacción sigue cayendo.",
                "/corporativo/mercado", "Ir al mercado", numeros=[f"Vence en {_plural(max(vence, 0), 'ciclo', 'ciclos')}"],
                urgencia=60, clave=f"corporativo:salida:{o['_id']}"))
        elif o["tipo"] == "OFERTA_IA":
            salida.append(consejo(
                "corporativo", "OPORTUNIDAD", f"{o.get('sigla_comprador')} ofrece {o.get('monto', 0):,} por {nombre}",
                "Una venta entra directo al capital: compárala con la renta que te deja.", "/corporativo/mercado", "Ver oferta",
                numeros=[f"Vence en {_plural(max(vence, 0), 'ciclo', 'ciclos')}"], confianza="media", riesgo="medio",
                urgencia=35, nivel_minimo="ANALISIS", clave=f"corporativo:oia:{o['_id']}"))
        elif o["tipo"] == "CONTRAOFERTA":
            salida.append(consejo(
                "corporativo", "OPORTUNIDAD", f"Contraoferta por {nombre}",
                "El rival pide más por el traspaso; si lo aceptas se firma al instante.", "/corporativo/mercado", "Ver contraoferta",
                numeros=[f"Pide {o.get('monto', 0):,}"], confianza="media", riesgo="medio", urgencia=30,
                nivel_minimo="ANALISIS", clave=f"corporativo:contra:{o['_id']}"))
        else:
            salida.append(consejo(
                "corporativo", "OPORTUNIDAD", f"{nombre} quiere firmar con {sigla}",
                "Un talento se ofrece solo: revisa si la prima vale su renta.", "/corporativo/mercado", "Ver propuesta",
                numeros=[f"Prima {o.get('prima', 0):,}"], confianza="media", riesgo="medio", urgencia=20,
                nivel_minimo="ANALISIS", clave=f"corporativo:prop:{o['_id']}"))
    return salida


def _consejos_corporativo_v2(ctx: Contexto, sigla: str, ciclo: int, nombre_ref) -> List[dict]:
    """Saneamiento, señales de venta, acuerdos y giras: con las MISMAS funciones que la cartera (corporativo_service)."""
    from services import corporativo_service as CS
    from services import corporativo_universo_service as U
    from services.corporativo_mercado_service import valores
    salida = []
    corp = db['corp_corporativos'].find_one({"universo_id": ctx.uid_str, "sigla": sigla}, {"saneamiento": 1}) or {}
    san = corp.get("saneamiento") or {}
    if san.get("estado") == "ACTIVO":
        faltan = [CC.SANEAMIENTO_OBJETIVOS[k] for k in san.get("objetivos", []) if not (san.get("progreso", {}).get(k) or {}).get("ok")]
        if faltan:
            salida.append(consejo(
                "corporativo", "URGENTE", f"Plan de saneamiento: te {'falta' if len(faltan) == 1 else 'faltan'} {len(faltan)} objetivo{'s' if len(faltan) > 1 else ''}",
                f"Si lo cumples antes del cierre del ciclo {san['hasta_ciclo']}, los accionistas aportan {san.get('aporte', 0):,} de capital.",
                "/corporativo/", "Ver el plan", porque=faltan[:3], urgencia=85, clave="corporativo:saneamiento"))
    v = valores()
    ctxp = CS._contexto_partidos()
    activos = U.contratos_activos(ctx.uid_str, sigla)
    vender = []
    for c in activos:
        valor = (v["selecciones"] if c["tipo"] == "seleccion" else v["jugadores"]).get(c["ref_id"], 0)
        sn = CS.senal_de(c["tipo"], c["ref_id"], valor, CS.juego_de(c["tipo"], c["ref_id"], ctxp), ctxp, c, ciclo)
        if sn["senal"] == "vender":
            vender.append((c, sn))
    for c, sn in vender[:2]:
        nombre = nombre_ref(c["tipo"], c["ref_id"])
        salida.append(consejo(
            "corporativo", "OPORTUNIDAD", f"Piensa en soltar a {nombre}",
            "Rinde mal y pide renovación: no lo renueves; véndelo si te ofrecen algo o rescinde antes de que te cueste más.", f"/corporativo/{sigla}", "Ver cartera",
            porque=[m["texto"] for m in sn["motivos"] if m["tono"] == "neg"][:3], confianza="media", riesgo="medio", urgencia=30,
            nivel_minimo="ANALISIS", clave=f"corporativo:vender:{c['_id']}"))
    # Marcas y patrocinios (corporativo_marcas_service): ofertas sin responder, patrocinios en riesgo y a quién promover
    try:
        from services import corporativo_marcas_service as MK
        res = MK.resumen(ctx.uid_str, sigla)
        for o in res["ofertas"][:2]:
            salida.append(consejo(
                "corporativo", "URGENTE", f"{o['marca']['nombre']} quiere patrocinar a {o['nombre']}",
                f"Firma {o['firma']:,} y {o['pago_ciclo']:,} por ciclo durante {o['ciclos']} ciclos; el {int(CC.MARCA_COMISION_CEO * 100)}% es tu comisión. "
                "Si no respondes antes del cierre del ciclo siguiente, la oferta se pierde.", "/corporativo/marcas", "Responder",
                numeros=[f"Encaje {o['encaje']}/100"], urgencia=70, clave=f"corporativo:patrocinio:{o['_id']}"))
        if res["en_riesgo"]:
            salida.append(consejo(
                "corporativo", "URGENTE", f"{res['en_riesgo']} patrocinio{'s' if res['en_riesgo'] > 1 else ''} en riesgo",
                "La marca está revisando el patrocinio: si el próximo ciclo sigue igual, corta. Que juegue, una gira o una campaña de marketing ayudan.",
                "/corporativo/marcas", "Ver patrocinios", urgencia=55, nivel_minimo="ANALISIS", clave="corporativo:marca_riesgo"))
        promos = db['corp_patrocinios'].count_documents({"universo_id": ctx.uid_str, "origen": "PROMOCION", "ciclo": ciclo})
        if promos < CC.MARCA_PROMOCIONES_POR_CICLO:
            vista = MK.vista_marcas(ctx.uid_str) or {}
            mejores = sorted(((mk, c) for mk in vista.get("interesadas", []) for c in mk["candidatos"]), key=lambda x: -x[1]["encaje"])[:3]
            if mejores:
                salida.append(consejo(
                    "corporativo", "GRATIS", "Promueve a tus representados con una marca",
                    "Hay marcas con cupo que encajan con tu cartera: preséntaselos y responden al cierre del ciclo. Firma + pago por ciclo, juegue o no.",
                    "/corporativo/marcas", "Ver marcas interesadas",
                    porque=[f"{c['nombre']} → {mk['nombre']} ({round(c['prob'] * 100)}% acepta)" for mk, c in mejores],
                    numeros=[f"{CC.MARCA_PROMOCIONES_POR_CICLO - promos} promociones disponibles este ciclo"], urgencia=25, clave="corporativo:promover"))
    except Exception as e:
        print(f"[asistente] marcas: {e}")
    if not db['corp_giras'].find_one({"universo_id": ctx.uid_str, "sigla": sigla, "ciclo": ciclo}):
        sin_partido = [c for c in activos if c["tipo"] == "seleccion" and not CS.juego_de("seleccion", c["ref_id"], ctxp).get("partidos_2")]
        if sin_partido:
            salida.append(consejo(
                "corporativo", "OPORTUNIDAD", "Organiza una gira de exhibición",
                "Tus selecciones sin partidos cercanos pueden salir de gira: recaudas y, si sos el primero en un tiempo, suman aficionados reales.",
                f"/corporativo/{sigla}", "Organizar gira", porque=[", ".join(nombre_ref("seleccion", c["ref_id"]) for c in sin_partido[:3])],
                confianza="media", urgencia=20, nivel_minimo="ANALISIS", clave="corporativo:gira"))
    return salida


# ==========================================
# Datos compartidos por los analizadores de oportunidades
# ==========================================
def _poderes(ctx: Contexto) -> Dict[int, float]:
    """'estadisticas.poder' de cada país de los próximos partidos (internacional, con 'paises' de respaldo)."""
    def cargar():
        ids = {(j.get(l) or {}).get("id") for j in ctx.proximos for l in ("equipo_local", "equipo_visitante")} - {None}
        poder = {d["id"]: (d.get("estadisticas") or {}).get("poder", 0.0) or 0.0
                 for d in db['internacional'].find({"id": {"$in": list(ids)}}, {"id": 1, "estadisticas.poder": 1})}
        faltan = [i for i in ids if i not in poder]
        if faltan:
            poder.update({d["id"]: (d.get("estadisticas") or {}).get("poder", 0.0) or 0.0
                          for d in db['paises'].find({"id": {"$in": faltan}}, {"id": 1, "estadisticas.poder": 1})})
        return poder
    return ctx.memo("poderes", cargar)


def _partidos_modelados(ctx: Contexto) -> List[dict]:
    """Los próximos partidos con las probabilidades del modelo conservador (asistente_reglas.probabilidades_partido)."""
    from services.asistente_reglas import probabilidades_partido

    def cargar():
        poder = _poderes(ctx)
        salida = []
        for j in ctx.proximos:
            l, v = j.get("equipo_local") or {}, j.get("equipo_visitante") or {}
            if l.get("id") is None or v.get("id") is None:
                continue
            salida.append({"juego": j, "local": l, "visita": v,
                           "probs": probabilidades_partido(poder.get(l["id"], 0.0), poder.get(v["id"], 0.0))})
        return salida
    return ctx.memo("partidos", cargar)


def _partidos_por_pais(ctx: Contexto) -> Dict[int, List[tuple]]:
    """{pais_id: [(p_gana, p_empata, p_pierde), ...]} de sus partidos dentro del horizonte."""
    def cargar():
        por_pais: Dict[int, List[tuple]] = {}
        for p in _partidos_modelados(ctx):
            gl, e, gv = p["probs"]
            por_pais.setdefault(p["local"]["id"], []).append((gl, e, gv))
            por_pais.setdefault(p["visita"]["id"], []).append((gv, e, gl))
        return por_pais
    return ctx.memo("por_pais", cargar)


def _album(ctx: Contexto) -> dict:
    return ctx.memo("album", lambda: db['user_albums'].find_one({"user_id": ctx.uid}, {"owned_paises": 1, "owned_ciudades": 1}) or {})


def _pct(p: float) -> str:
    return f"{round(p * 100)}%"


# ==========================================
# Quinielas (Análisis)
# ==========================================
def analizar_quinielas(ctx: Contexto) -> List[dict]:
    from services.asistente_reglas import confianza_por_prob, mejor_pronostico, valor_esperado_quiniela
    partidos = _partidos_modelados(ctx)
    if not partidos:
        return []
    candidatos = sorted(({**p, "pick": mejor_pronostico(p["probs"])} for p in partidos), key=lambda p: -p["pick"][1])
    mejor = None
    for cfg in db['quiniela_config'].find({"activa": True}, {"nombre": 1, "cantidad_partidos": 1, "costo_puntos": 1, "reglas_premio": 1}):
        n = cfg["cantidad_partidos"]
        if len(candidatos) < n or cfg["costo_puntos"] > ctx.saldo:
            continue
        elegidos = candidatos[:n]
        ev, cobra = valor_esperado_quiniela([p["pick"][1] for p in elegidos], cfg["costo_puntos"], cfg.get("reglas_premio") or [])
        if ev > 0 and (mejor is None or ev > mejor["ev"]):
            mejor = {"cfg": cfg, "elegidos": elegidos, "ev": ev, "cobra": cobra}
    if not mejor:
        return []
    texto_pick = {"LOCAL": lambda p: f"gana {p['local'].get('nombre')}", "VISITA": lambda p: f"gana {p['visita'].get('nombre')}",
                  "EMPATE": lambda p: "empate"}
    porque = [f"{p['local'].get('nombre')} vs {p['visita'].get('nombre')}: {texto_pick[p['pick'][0]](p)} ({_pct(p['pick'][1])})"
              for p in mejor["elegidos"][:5]]
    cfg = mejor["cfg"]
    return [consejo(
        "quinielas", "OPORTUNIDAD", f"Juega la {cfg['nombre']}",
        "Elige los partidos más previsibles del calendario que viene: es la quiniela que mejor rinde con estos pronósticos.",
        "/quinielas/", "Ir a quinielas", porque=porque,
        numeros=[f"Costo {cfg['costo_puntos']:,} pts", f"Cobrar algún premio: {_pct(mejor['cobra'])}"],
        valor=round(mejor["ev"]), confianza=confianza_por_prob(mejor["cobra"]), riesgo="medio", urgencia=15,
        nivel_minimo="ANALISIS", clave=f"quinielas:{cfg['_id']}")]


# ==========================================
# Selecciones: compras (Análisis)
# ==========================================
def analizar_mercado_selecciones(ctx: Contexto) -> List[dict]:
    from services import ownership_service as OS
    por_pais = _partidos_por_pais(ctx)
    if not por_pais:
        return []
    estampas = set(_album(ctx).get("owned_paises") or [])
    libres = {p["id"]: p for p in db['paises'].find({"id": {"$in": list(por_pais)}, "user_id": {"$in": [0, "0", None]}},
                                                    {"id": 1, "nombre": 1, "bandera": 1, "valor": 1})}
    opciones = []
    for pid, p in libres.items():
        valor = int(p.get("valor") or OS.VALOR_INICIAL_PAIS)
        if valor > ctx.saldo:
            continue
        mult = OS.MULTIPLICADOR_SINERGIA_ALBUM if pid in estampas else 1.0
        # Dividendo por victoria + cómo se mueve el valor de mercado (ganar ≈ +175, empatar ≈ +25, perder ≈ -80)
        dividendos = sum(g * OS.DIVIDENDO_VICTORIA * mult for g, _, _ in por_pais[pid])
        plusvalia = sum(g * 175 + e * 25 - d * 80 for g, e, d in por_pais[pid])
        ganancia = dividendos + plusvalia
        if ganancia > 0:
            opciones.append((ganancia / valor, pid, p, valor, dividendos, plusvalia, mult > 1))
    salida = []
    for _, pid, p, valor, dividendos, plusvalia, sinergia in sorted(opciones, key=lambda t: -t[0])[:2]:
        partidos = por_pais[pid]
        porque = [f"Juega {_plural(len(partidos), 'partido', 'partidos')} en lo que viene; gana el {_pct(max(g for g, _, _ in partidos))} en el mejor"]
        if sinergia:
            porque.append("Tienes su estampa: los dividendos te pagan ×1,5")
        salida.append(consejo(
            "selecciones", "OPORTUNIDAD", f"Compra {p.get('nombre')}",
            "Está libre y le vienen partidos favorables: dividendos por ganar y su valor de mercado puede subir.",
            "/selecciones/mercado", "Ir al mercado", porque=porque,
            numeros=[f"Precio {valor:,} pts", f"Dividendos esperados {round(dividendos):,}", f"Plusvalía esperada {round(plusvalia):+,}"],
            valor=round(dividendos + plusvalia), confianza="media" if sinergia else "baja", riesgo="medio", urgencia=10,
            nivel_minimo="ANALISIS", clave=f"selecciones:comprar:{pid}", pais_id=pid, bandera=p.get("bandera")))
    return salida


# ==========================================
# Once Ideal: el cambio que más suma (Análisis)
# ==========================================
def analizar_cambio_once(ctx: Contexto) -> List[dict]:
    from services import fantasy_service as FS
    equipo = db['fantasy_teams'].find_one({"user_id": ctx.uid, "mundial_id": ctx.mundial_id}, {"lineup": 1}) if ctx.mundial_id else None
    por_pais = _partidos_por_pais(ctx)
    if not equipo or not equipo.get("lineup") or not por_pais:
        return []
    eliminados = FS.paises_eliminados()
    lineup = list(db['jugadores'].find({"id": {"$in": equipo["lineup"]}}, {"id": 1, "nombre": 1, "pais_id": 1, "posicion_id": 1, "rendimiento": 1, "leyenda": 1}))
    activos = [j for j in lineup if j.get("pais_id") not in eliminados]   # los eliminados ya los avisa el Vistazo
    if not activos:
        return []
    # El más flojo: sin partido en el horizonte primero, después el de menor rendimiento
    flojo = min(activos, key=lambda j: (j.get("pais_id") in por_pais, j.get("rendimiento") or 0))
    por_pais_lineup: Dict[int, int] = {}
    for j in lineup:
        if j["id"] != flojo["id"]:
            por_pais_lineup[j.get("pais_id")] = por_pais_lineup.get(j.get("pais_id"), 0) + 1
    paises_ok = [pid for pid in por_pais if pid not in eliminados and por_pais_lineup.get(pid, 0) < FS.MAX_JUGADORES_POR_PAIS]
    # Tope de leyendas en el Once Ideal: si ya hay otra leyenda (que no es la que sale), el reemplazo no puede serlo
    otras_leyendas = sum(1 for j in lineup if j.get("leyenda") and j["id"] != flojo["id"])
    filtro_leyenda = {"leyenda": {"$ne": True}} if otras_leyendas >= FS.MAX_LEYENDAS_FANTASY else {}
    reemplazo = db['jugadores'].find_one({"posicion_id": flojo.get("posicion_id"), "pais_id": {"$in": paises_ok},
                                          "id": {"$nin": equipo["lineup"]}, **filtro_leyenda},
                                         {"id": 1, "nombre": 1, "pais_id": 1, "rendimiento": 1}, sort=[("rendimiento", -1)])
    if not reemplazo or (reemplazo.get("rendimiento") or 0) <= (flojo.get("rendimiento") or 0) + 2:
        return []
    sin_partido = flojo.get("pais_id") not in por_pais
    return [consejo(
        "once_ideal", "OPORTUNIDAD", f"Cambia a {flojo.get('nombre')} por {reemplazo.get('nombre')}",
        "Misma posición, mejor momento y con partido en lo que viene.", "/once-ideal/", "Ir al Once Ideal",
        porque=(["Su selección no juega en los próximos partidos"] if sin_partido else []) +
               [f"Rendimiento {reemplazo.get('rendimiento', 0):.1f} vs {flojo.get('rendimiento', 0):.1f}",
                f"{_plural(len(por_pais.get(reemplazo['pais_id'], [])), 'partido', 'partidos')} de su selección en el horizonte"],
        numeros=[f"Usa 1 cambio gratis (o {FS.COSTO_CAMBIO_EXTRA} pts)"], confianza="media", riesgo="bajo",
        urgencia=20 if sin_partido else 10, nivel_minimo="ANALISIS", clave=f"once_ideal:cambio:{flojo['id']}",
        jugador_id=reemplazo["id"], pais_id=reemplazo.get("pais_id"))]


# ==========================================
# Sedes (Profundo)
# ==========================================
def analizar_sedes(ctx: Contexto) -> List[dict]:
    from services import venue_service as VS
    if VS.COSTO_BASE_SEDE > ctx.saldo:
        return []
    goles_medios = 2.5
    por_ciudad: Dict[int, dict] = {}
    for p in _partidos_modelados(ctx):
        ub = p["juego"].get("ubicacion") or {}
        if ub.get("id") is None:
            continue
        regalia = VS.REGALIA_BASE * (VS.MULTIPLICADOR_FASE_ALTA if (p["juego"].get("fase_id") or 0) >= VS.FASE_ID_BONO_ALTO else 1)
        c = por_ciudad.setdefault(ub["id"], {"nombre": ub.get("nombre"), "pais_id": ub.get("pais_id"), "partidos": 0, "regalias": 0.0})
        c["partidos"] += 1
        c["regalias"] += regalia + goles_medios * VS.BONO_POR_GOL
    if not por_ciudad:
        return []
    libres = {c["id"] for c in db['ciudades'].find({"id": {"$in": list(por_ciudad)}, "owner_user_id": {"$in": VS.SIN_DUENO}}, {"id": 1})}
    mias = list(db['city_ownerships'].find({"user_id": ctx.uid, "status": VS.ESTADO_SEDE_ACTIVO}, {"pais_id": 1}))
    if len(mias) >= VS.MAX_CIUDADES_TOTAL:
        return []
    por_pais_mias: Dict[int, int] = {}
    for m in mias:
        por_pais_mias[m.get("pais_id")] = por_pais_mias.get(m.get("pais_id"), 0) + 1
    estampas = set(_album(ctx).get("owned_ciudades") or [])
    costo_neto = VS.COSTO_BASE_SEDE * (1 - VS.PORCENTAJE_REEMBOLSO_VENTA)   # comprar y revender al 80%
    opciones = []
    for cid in libres:
        c = por_ciudad[cid]
        if por_pais_mias.get(c["pais_id"], 0) >= VS.MAX_CIUDADES_POR_PAIS:
            continue
        mult = VS.MULTIPLICADOR_SINERGIA if cid in estampas else 1.0
        neto = c["regalias"] * mult - costo_neto
        if neto > 0:
            opciones.append((neto, cid, c, mult > 1))
    salida = []
    for neto, cid, c, sinergia in sorted(opciones, key=lambda t: -t[0])[:2]:
        salida.append(consejo(
            "sedes", "OPORTUNIDAD", f"Patrocina {c['nombre']}",
            "Está libre y aloja partidos en lo que viene: cobras regalía por cada uno.", "/sedes/directorio", "Ir al directorio",
            porque=[f"Aloja {_plural(c['partidos'], 'partido', 'partidos')} del calendario próximo"] +
                   (["Tienes su estampa: regalías ×1,5"] if sinergia else []),
            numeros=[f"Costo {VS.COSTO_BASE_SEDE:,} pts (recuperas el {round(VS.PORCENTAJE_REEMBOLSO_VENTA * 100)}% al vender)",
                     f"Regalías esperadas {round(c['regalias'] * (VS.MULTIPLICADOR_SINERGIA if sinergia else 1)):,}"],
            valor=round(neto), confianza="alta" if c["partidos"] >= 2 else "media", riesgo="bajo", urgencia=10,
            nivel_minimo="PROFUNDO", clave=f"sedes:{cid}", pais_id=c.get("pais_id")))
    return salida


# ==========================================
# Álbum: sinergias que te faltan (Profundo)
# ==========================================
def analizar_album(ctx: Contexto) -> List[dict]:
    album = _album(ctx)
    paises_mios = [d["pais_id"] for d in db['team_ownerships'].find({"user_id": ctx.uid, "status": "ACTIVO"}, {"pais_id": 1})]
    ciudades_mias = [d["ciudad_id"] for d in db['city_ownerships'].find({"user_id": ctx.uid, "status": "ACTIVO"}, {"ciudad_id": 1})]
    faltan_p = [p for p in paises_mios if p not in set(album.get("owned_paises") or [])]
    faltan_c = [c for c in ciudades_mias if c not in set(album.get("owned_ciudades") or [])]
    if not (faltan_p or faltan_c):
        return []
    from services.album_service import COSTO_SOBRE
    partes = ([_plural(len(faltan_p), "escudo", "escudos")] if faltan_p else []) + ([_plural(len(faltan_c), "estadio", "estadios")] if faltan_c else [])
    return [consejo(
        "album", "OPORTUNIDAD", f"Te faltan {' y '.join(partes)} para cobrar ×1,5",
        "Tus inversiones pagarían un 50% más con su estampa pegada. Los escudos son Platino (3% por estampa): es una apuesta larga.",
        "/album-estampas/sobres", "Abrir sobres",
        porque=["Las estampas de estadio son Especiales (20%) y las de escudo, Platino (3%)"],
        numeros=[f"Sobre {COSTO_SOBRE} pts"], confianza="baja", riesgo="alto", urgencia=5, nivel_minimo="PROFUNDO",
        clave="album:sinergias")]


# ==========================================
# Juego en Vivo: el próximo partido (Profundo)
# ==========================================
def analizar_juego_en_vivo(ctx: Contexto) -> List[dict]:
    from config.juego_en_vivo import ENTRADA_MONTO
    from services import juego_en_vivo_service as JV
    if ctx.saldo < ENTRADA_MONTO or not ctx.proximos:
        return []
    juego = ctx.proximos[0]
    if db['match_live_sessions'].find_one({"usuario_id": ctx.uid, "juego_id": juego["_id"]}, {"_id": 1}):
        return []
    cuotas = JV.calcular_cuotas({**juego, "mundial_id": ctx.mundial_id})
    lados = sorted((cuotas["local"], cuotas["visitante"]), key=lambda l: -l["cuota"])
    alto, bajo = lados
    if alto["cuota"] == bajo["cuota"]:
        return []
    return [consejo(
        "juego_en_vivo", "OPORTUNIDAD", f"En el próximo partido, elige a {alto['nombre']}",
        f"Arranca con {alto['cuota']:,} pts contra {bajo['cuota']:,} de {bajo['nombre']}, y en este Mundial el favorito no gana tan seguido como dice el papel.",
        "/juegos/", "Elegir país",
        porque=[f"{cuotas['local']['nombre']} vs {cuotas['visitante']['nombre']}",
                f"Favorito según el Scouter: {bajo['nombre']} ({round(bajo['probabilidad_pct'])}%)"],
        numeros=[f"Entrada {ENTRADA_MONTO:,} pts", f"+{alto['cuota'] - bajo['cuota']} pts de cuota de arranque"],
        valor=alto["cuota"] - bajo["cuota"], confianza="baja", riesgo="alto", urgencia=15, nivel_minimo="PROFUNDO",
        clave=f"juego_en_vivo:{juego['_id']}", pais_id=alto["pais_id"], bandera=alto.get("bandera"))]


# ==========================================
# Corporativo: dividendo y bolsa (Profundo)
# ==========================================
def analizar_bolsa(ctx: Contexto) -> List[dict]:
    from services import corporativo_universo_service as U
    universo = U.obtener_universo(ctx.uid_str)
    if not universo:
        return []
    salida = []
    ciclo = U.ciclo_en_curso(universo)
    corps = list(db['corp_corporativos'].find({"universo_id": ctx.uid_str},
                                              {"sigla": 1, "precio": 1, "precio_inicial": 1, "historial": {"$slice": -1},
                                               "variacion_ciclo": 1, "dividendo_ciclo": 1, "es_del_usuario": 1}))
    cargo = universo.get("cargo") if universo.get("estado") == "EN_CARGO" else None
    if cargo:
        mio = next((c for c in corps if c["sigla"] == cargo["sigla"]), None)
        utilidad = ((mio or {}).get("historial") or [{}])[-1].get("utilidad", 0)
        if mio and utilidad > 0 and mio.get("dividendo_ciclo") != ciclo:
            salida.append(consejo(
                "corporativo", "OPORTUNIDAD", f"Reparte dividendo en {cargo['sigla']}",
                "Hubo utilidad el último ciclo: repartir sube el sentimiento de la acción y cobras la parte de tus acciones.",
                "/corporativo/bolsa", "Ir a la bolsa", numeros=[f"Utilidad del ciclo {utilidad:,}", f"Hasta el {round(CC.FRACCION_MAX_DIVIDENDO * 100)}%"],
                confianza="media", riesgo="bajo", urgencia=20, nivel_minimo="PROFUNDO", clave="corporativo:dividendo"))
    # Acción "barata": mejor ROI del último ciclo entre las que bajaron (no se puede comprar la propia)
    candidatas = [c for c in corps if not (cargo and c["sigla"] == cargo["sigla"]) and (c.get("variacion_ciclo") or 0) <= 0
                  and ((c.get("historial") or [{}])[-1].get("roi") or 0) > 0]
    if candidatas:
        mejor = max(candidatas, key=lambda c: (c.get("historial") or [{}])[-1].get("roi", 0))
        roi = (mejor.get("historial") or [{}])[-1].get("roi", 0)
        salida.append(consejo(
            "corporativo", "OPORTUNIDAD", f"Mira la acción de {mejor['sigla']}",
            "Ganó dinero el último ciclo pero su acción bajó: el precio se ajusta en el próximo cierre.",
            "/corporativo/bolsa", "Ir a la bolsa",
            numeros=[f"Precio {mejor.get('precio', 0):.2f}", f"ROI del ciclo {roi * 100:+.2f}%",
                     f"Variación {(mejor.get('variacion_ciclo') or 0) * 100:+.1f}%"],
            confianza="baja", riesgo="medio", urgencia=5, nivel_minimo="PROFUNDO", clave=f"corporativo:accion:{mejor['sigla']}"))
    return salida


# ==========================================
# Seguimiento: ¿el usuario hizo lo que decía el consejo?
# ==========================================
def verificar_hecho(uid: ObjectId, clave: str, desde: datetime) -> Optional[bool]:
    """
    True si hay rastro de que el usuario hizo lo que pedía el consejo 'clave' después de 'desde' (fecha local de la
    consulta); False si se puede afirmar que no; None si este tipo de consejo no se puede verificar (lo decide la
    comparación con un escaneo nuevo: si desapareció, "ya no aplica"). Solo lectura.
    """
    partes = clave.split(":")
    modulo, tipo = partes[0], (partes[1] if len(partes) > 1 else "")
    uid_str = str(uid)
    desde_utc = desde - (datetime.now() - datetime.utcnow())   # los corporativos guardan en UTC

    if clave == "misiones:checkin":
        return db['reward_transactions'].count_documents({"user_id": uid, "type": {"$in": ["CHECKIN", "CHECKIN_ESPECIAL"]}, "created_at": {"$gte": desde}}, limit=1) > 0
    if clave == "misiones:trivia":
        return db['trivia_history'].count_documents({"user_id": uid, "created_at": {"$gte": desde}}, limit=1) > 0
    if clave == "misiones:beca":
        return db['reward_transactions'].count_documents({"user_id": uid, "type": "BECA_EMERGENCIA", "created_at": {"$gte": desde}}, limit=1) > 0
    if clave == "niveles:recompensas":
        return db['recompensas_nivel'].count_documents({"user_id": uid, "reclamada_en": {"$gte": desde}}, limit=1) > 0
    if clave == "album:sobres_regalo":
        return db['pack_purchases'].count_documents({"user_id": uid, "origen": {"$in": ["GRATIS", "PLATINO"]}, "created_at": {"$gte": desde}}, limit=1) > 0
    if clave == "album:sinergias":
        return db['pack_purchases'].count_documents({"user_id": uid, "created_at": {"$gte": desde}}, limit=1) > 0 or None
    if modulo == "selecciones" and len(partes) == 3:
        pid = int(partes[2])
        if tipo == "vender":
            return db['ownership_transactions'].count_documents({"user_id": uid, "pais_id": pid, "type": "VENTA", "created_at": {"$gte": desde}}, limit=1) > 0
        if tipo == "comprar":
            return db['team_ownerships'].count_documents({"user_id": uid, "pais_id": pid, "status": "ACTIVO"}, limit=1) > 0 or None
    if modulo == "once_ideal":
        equipo = db['fantasy_teams'].find_one({"user_id": uid}, {"lineup": 1}, sort=[("_id", -1)]) if tipo != "armar" else None
        if tipo == "armar":
            return db['fantasy_teams'].count_documents({"user_id": uid}, limit=1) > 0
        if tipo == "cambio" and len(partes) == 3 and equipo:
            return int(partes[2]) not in (equipo.get("lineup") or [])
        if tipo in ("eliminados", "cambios"):   # solo se resuelven guardando el Once (XP de la acción)
            return db['xp_eventos'].count_documents({"user_id": uid, "accion": "ONCE_IDEAL", "creado_en": {"$gte": desde}}, limit=1) > 0 or None
    if modulo == "quinielas" and len(partes) == 2:
        try:
            config_id = ObjectId(partes[1])
        except Exception:
            return None
        return db['quiniela_usuario'].count_documents({"usuario_id": uid, "quiniela_config_id": config_id, "fecha_creacion": {"$gte": desde}}, limit=1) > 0 or None
    if modulo == "sedes" and len(partes) == 2:
        return db['city_ownerships'].count_documents({"user_id": uid, "ciudad_id": int(partes[1]), "status": "ACTIVO"}, limit=1) > 0 or None
    if modulo == "juego_en_vivo" and len(partes) == 2:
        try:
            return db['match_live_sessions'].count_documents({"usuario_id": uid, "juego_id": ObjectId(partes[1])}, limit=1) > 0 or None
        except Exception:
            return None
    if modulo == "corporativo":
        if tipo == "empezar":
            return db['corp_universos'].count_documents({"_id": uid_str}, limit=1) > 0
        if tipo == "ofertas_empleo":
            return db['corp_ofertas_empleo'].count_documents({"universo_id": uid_str, "resuelta_en": {"$gte": desde_utc}}, limit=1) > 0 or None
        if tipo in ("salida", "oia", "contra", "prop"):
            oferta = db['corp_ofertas'].find_one({"_id": ":".join(partes[2:])}, {"estado": 1})
            if oferta and oferta.get("estado") in ("ACEPTADA", "RECHAZADA"):
                return True
            return False if oferta and oferta.get("estado") == "VENCIDA" else None
        if tipo == "dividendo":
            return db['corp_movimientos'].count_documents({"universo_id": uid_str, "tipo": "DIVIDENDO", "creado_en": {"$gte": desde_utc}}, limit=1) > 0 or None
        if tipo == "saneamiento":
            corp = db['corp_corporativos'].find_one({"universo_id": uid_str, "es_del_usuario": True}, {"saneamiento": 1}) or {}
            return True if (corp.get("saneamiento") or {}).get("estado") == "CUMPLIDO" else None
        if tipo == "vender" and len(partes) == 3 and ObjectId.is_valid(partes[2]):
            c = db['corp_contratos'].find_one({"_id": ObjectId(partes[2])}, {"activo": 1, "fin_ciclo": 1})
            return True if c and not c.get("activo") else None
        if tipo == "acuerdo":
            return db['corp_acuerdos'].count_documents({"universo_id": uid_str, "creado_en": {"$gte": desde_utc}}, limit=1) > 0 or None
        if tipo == "promover":
            return db['corp_patrocinios'].count_documents({"universo_id": uid_str, "origen": "PROMOCION", "creado_en": {"$gte": desde_utc}}, limit=1) > 0 or None
        if tipo == "patrocinio" and len(partes) >= 3:
            p = db['corp_patrocinios'].find_one({"_id": ":".join(partes[2:])}, {"estado": 1})
            if p and p.get("estado") in ("ACTIVO", "RECHAZADA"):
                return True
            return False if p and p.get("estado") == "VENCIDA" else None
        if tipo == "gira":
            return db['corp_giras'].count_documents({"universo_id": uid_str, "es_usuario": True, "creado_en": {"$gte": desde_utc}}, limit=1) > 0 or None
        if tipo == "accion" and len(partes) == 3:
            return db['corp_operaciones_bolsa'].count_documents({"universo_id": uid_str, "sigla": partes[2], "tipo": "COMPRA", "creado_en": {"$gte": desde_utc}}, limit=1) > 0 or None
    return None


# ==========================================
# Registro y ejecución
# ==========================================
ANALIZADORES: Dict[str, Callable[[Contexto], List[dict]]] = {
    "misiones": analizar_misiones,
    "niveles": analizar_niveles,
    "selecciones": analizar_selecciones,
    "once_ideal": analizar_once_ideal,
    "corporativo": analizar_corporativo,
    "quinielas": analizar_quinielas,
    "selecciones:mercado": analizar_mercado_selecciones,
    "once_ideal:cambio": analizar_cambio_once,
    "sedes": analizar_sedes,
    "album": analizar_album,
    "juego_en_vivo": analizar_juego_en_vivo,
    "corporativo:bolsa": analizar_bolsa,
}


def ejecutar_todos(ctx: Contexto) -> List[dict]:
    """Corre cada analizador permitido para el rol; si uno falla se registra y se sigue (no rompe el informe)."""
    consejos: List[dict] = []
    for nombre, fn in ANALIZADORES.items():
        modulo = nombre.split(":")[0]
        if not ctx.puede(modulo):
            continue
        try:
            consejos.extend(c for c in fn(ctx) if ctx.puede(c["modulo"]))
        except Exception as e:   # noqa: BLE001 - un módulo roto no debe tirar el informe
            logger.error(f"Asistente: falló el analizador '{nombre}': {e}")
    return consejos
