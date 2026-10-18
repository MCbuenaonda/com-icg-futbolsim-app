"""
XP retroactiva de los Niveles de Socio FIFAV (services/niveles_service.py): recorre lo que cada usuario
ya hizo y le otorga la misma XP que darían hoy los ganchos de cada módulo, con la FECHA ORIGINAL de
cada acción (así los topes diarios se aplican por el día en que pasó) y los mismos 'ref' que usan
los ganchos: es idempotente (índice único de 'xp_eventos') y se puede volver a correr para reponer XP
que no se haya otorgado por un error puntual. Las recompensas de los niveles alcanzados quedan
PENDIENTES para que cada usuario las reclame en /niveles.

    python calcular_xp_retroactivo.py --muestra    # dry run: XP y nivel resultante por usuario
    python calcular_xp_retroactivo.py --aplicar    # escribe xp_eventos / usuarios.xp / recompensas_nivel
"""
import sys
from collections import defaultdict
from datetime import datetime

from config.niveles import REGLAS_XP, XP_LOGRO, XP_TRIVIA_BASE, XP_TRIVIA_POR_ACIERTO, datos_nivel, nivel_para_xp
from services import niveles_service as N
from services.album_service import CAMPO_ALBUM_POR_TIPO, _catalogo_album

db = N.db


def _eventos_por_usuario() -> dict:
    """{user_id: [(fecha, accion, ref, xp | None)]} con todo lo que ya pasó, ordenable por fecha."""
    ev = defaultdict(list)
    mundial = N.ref_mundial()

    def agregar(uid, fecha, accion, ref, xp=None):
        if uid and fecha:
            ev[uid].append((fecha, accion, str(ref), xp))

    for rt in db["reward_transactions"].find({"type": {"$in": ["CHECKIN", "CHECKIN_ESPECIAL"]}}):
        dia = rt["created_at"].date().isoformat()
        agregar(rt["user_id"], rt["created_at"], "CHECKIN", dia)
        if rt["type"] == "CHECKIN_ESPECIAL":
            agregar(rt["user_id"], rt["created_at"], "CHECKIN_RACHA", dia)

    for t in db["trivia_history"].find({"estado": "COMPLETADA"}):
        fecha = t.get("completed_at") or t.get("created_at")
        agregar(t["user_id"], fecha, "TRIVIA", t["_id"], XP_TRIVIA_BASE + XP_TRIVIA_POR_ACIERTO * int(t.get("correct_answers") or 0))
        agregar(t["user_id"], fecha, "LOGRO", "PRIMERA_TRIVIA")

    for p in db["pack_purchases"].find({}):
        if p.get("origen", "COMPRA") == "COMPRA":
            agregar(p["user_id"], p["created_at"], "SOBRE", p["_id"])
        agregar(p["user_id"], p["created_at"], "LOGRO", "PRIMER_SOBRE")
        for e in p.get("stickers_obtained", []):
            if e.get("duplicado"):
                continue
            platino = e["tipo"] == "ARBITRO"
            agregar(p["user_id"], p["created_at"], "ESTAMPA_PLATINO" if platino else "ESTAMPA_NUEVA", f"{mundial}:{e['tipo']}:{e['id']}")
            if platino:
                agregar(p["user_id"], p["created_at"], "LOGRO", "PRIMERA_PLATINO")

    # Páginas completas: desde el estado actual del álbum (misma regla que album_service._paginas_completas)
    catalogo = _catalogo_album()
    jugadores_por_pais, ciudades_por_pais = defaultdict(set), defaultdict(set)
    for j, p in catalogo["pais_de_jugador"].items():
        jugadores_por_pais[p].add(j)
    for c, p in catalogo["pais_de_ciudad"].items():
        ciudades_por_pais[p].add(c)
    ids_arbitros = {a["id"] for a in catalogo["arbitros"]}
    ahora = datetime.now()
    for album in db["user_albums"].find({}):
        owned = {tipo: set(album.get(campo, [])) for tipo, campo in CAMPO_ALBUM_POR_TIPO.items()}
        for pais in catalogo["paises"]:
            pid = pais["pais_id"]
            if pid in owned["PAIS"] and jugadores_por_pais[pid] <= owned["JUGADOR"] and ciudades_por_pais[pid] <= owned["CIUDAD"]:
                agregar(album["user_id"], ahora, "PAGINA_COMPLETA", f"{mundial}:{pid}")
        if ids_arbitros and ids_arbitros <= owned["ARBITRO"]:
            agregar(album["user_id"], ahora, "PAGINA_COMPLETA", f"{mundial}:arbitros")

    for b in db["quiniela_usuario"].find({}):
        agregar(b["usuario_id"], b["fecha_creacion"], "QUINIELA", b["_id"])
        agregar(b["usuario_id"], b["fecha_creacion"], "LOGRO", "PRIMERA_QUINIELA")
        if b.get("estado") == "GANADA":
            agregar(b["usuario_id"], b.get("fecha_resolucion") or b["fecha_creacion"], "QUINIELA_GANADA", b["_id"])

    for s in db["match_live_sessions"].find({"estado": "finalizada"}):
        fecha = s.get("finalizado_en") or s.get("creado_en")
        agregar(s["usuario_id"], fecha, "JUEGO_VIVO", s["_id"])
        agregar(s["usuario_id"], fecha, "LOGRO", "PRIMER_JUEGO_VIVO")
        if int(s.get("monto_acreditado") or 0) > int(s.get("entrada_monto") or 0):
            agregar(s["usuario_id"], fecha, "JUEGO_VIVO_GANANCIA", s["_id"])

    for f in db["fantasy_teams"].find({}):
        agregar(f["user_id"], f["created_at"], "ONCE_IDEAL", f"{mundial}:fase:{f['fase_id']}")
        agregar(f["user_id"], f["created_at"], "LOGRO", "PRIMER_ONCE_IDEAL")

    for o in db["team_ownerships"].find({}):
        agregar(o["user_id"], o["purchased_at"], "SELECCION_COMPRA", o["_id"])
        agregar(o["user_id"], o["purchased_at"], "LOGRO", "PRIMERA_SELECCION")
    for t in db["ownership_transactions"].find({"type": {"$in": ["DIVIDENDO", "BONO_CLASIFICACION"]}}):
        agregar(t["user_id"], t["created_at"], "SELECCION_DIVIDENDO", t["_id"])

    duenos_de_ciudad = defaultdict(set)
    for c in db["city_ownerships"].find({}):
        agregar(c["user_id"], c["purchased_at"], "SEDE_COMPRA", c["_id"])
        agregar(c["user_id"], c["purchased_at"], "LOGRO", "PRIMERA_SEDE")
        duenos_de_ciudad[c["user_id"]].add(c["ciudad_id"])
    for r in db["city_revenue_history"].find({}):
        if r["ciudad_id"] in duenos_de_ciudad.get(r["user_id"], set()):   # solo el cobro del dueño (no el pasivo por estampa)
            agregar(r["user_id"], r["created_at"], "SEDE_REGALIA", f"{r['match_id']}:{r['ciudad_id']}")

    return ev


def _simular(eventos, ya_otorgados: set, usos_previos: dict) -> int:
    """XP que sumaría --aplicar, con las mismas reglas que otorgar_xp (único por ref + tope diario)."""
    vistos, usos, total = set(ya_otorgados), defaultdict(int, usos_previos), 0
    for fecha, accion, ref, xp in sorted(eventos, key=lambda e: e[0]):
        if (accion, ref) in vistos:
            continue
        regla = REGLAS_XP.get(accion, {})
        dia = fecha.date().isoformat()
        tope = regla.get("tope_diario")
        if tope and usos[(accion, dia)] >= tope:
            continue
        vistos.add((accion, ref))
        usos[(accion, dia)] += 1
        total += xp if xp is not None else (XP_LOGRO if accion == "LOGRO" else regla.get("xp", 0))
    return total


def main(aplicar: bool):
    eventos = _eventos_por_usuario()
    usuarios = {u["_id"]: u for u in db["usuarios"].find({"_id": {"$in": list(eventos)}}, {"username": 1, "xp": 1})}
    for uid, lista in sorted(eventos.items(), key=lambda kv: -len(kv[1])):
        usuario = usuarios.get(uid)
        if not usuario:
            continue   # actividad de un usuario ya borrado
        previos = list(db["xp_eventos"].find({"user_id": uid}, {"accion": 1, "ref": 1, "fecha": 1}))
        ya = {(p["accion"], p["ref"]) for p in previos}
        usos = defaultdict(int)
        for p in previos:
            usos[(p["accion"], p["fecha"])] += 1
        xp_actual = int(usuario.get("xp") or 0)
        nuevo = _simular(lista, ya, usos)
        nivel = nivel_para_xp(xp_actual + nuevo)
        print(f"{usuario.get('username', uid):<20} acciones {len(lista):>4}  XP {xp_actual:>5} + {nuevo:>5} = {xp_actual + nuevo:>5}  "
              f"-> nivel {nivel} ({datos_nivel(nivel)['titulo']})")
        if aplicar:
            for fecha, accion, ref, xp in sorted(lista, key=lambda e: e[0]):
                if accion == "LOGRO":
                    N.otorgar_logro(uid, ref, fecha=fecha, retroactivo=True)
                else:
                    N.otorgar_xp(uid, accion, ref, xp=xp, fecha=fecha, retroactivo=True)
            final = db["usuarios"].find_one({"_id": uid}, {"xp": 1, "nivel": 1, "recompensas_pendientes": 1})
            print(f"{'':<20} aplicado: XP {final.get('xp')} nivel {final.get('nivel')} recompensas pendientes {final.get('recompensas_pendientes')}")


if __name__ == "__main__":
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    if modo not in ("--muestra", "--aplicar"):
        print(__doc__)
    else:
        main(aplicar=modo == "--aplicar")
