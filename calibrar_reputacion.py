"""
Compara las constantes `REP_MEDIA` de services/prensa.py con los promedios REALES de la reputación mediática (solo lectura, no escribe nada).

Los efectos de la reputación (riesgo y encaje de las marcas, presión del DT) usan el puntaje CENTRADO: puntaje − REP_MEDIA[tipo]. Si la media real se separa de la
constante, TODOS los de ese tipo reciben un empujón en el mismo sentido (por ejemplo, los DT recibían ~0,025 menos de presión por partido y se despedían ~16% menos
de lo diseñado, porque la constante de DT se midió antes de que existieran las declaraciones y las reacciones de la prensa). Correrlo después de agregar cualquier
cosa que escriba notas con `valoraciones` (declaraciones, premios, escándalos, reacciones…).

  python calibrar_reputacion.py
  
Con árbitros se compara el puntaje DESGASTADO por el tiempo (el que usan las vistas y la designación), no el guardado.
"""
import statistics as st

UMBRAL = {"pais": 3.0, "jugador": 3.0, "dt": 3.0, "arbitro": 3.0}   # diferencia (en puntos de reputación) a partir de la cual se avisa


def main():
    from services import prensa as P
    from services.imagenes_pais_service import db
    from services.polemicas_service import puntajes_centrales
    reales = {}
    for d in db["prensa_reputacion"].find({}, {"tipo": 1, "puntaje": 1}):
        if d.get("tipo") != "arbitro":
            reales.setdefault(d["tipo"], []).append(d["puntaje"])
    pa = puntajes_centrales()
    if pa:
        reales["arbitro"] = list(pa.values())
    print(f"{'tipo':<9}{'n':>6}{'media real':>12}{'constante':>11}{'diferencia':>12}")
    avisos = []
    for tipo in ("pais", "jugador", "dt", "arbitro"):
        v = reales.get(tipo)
        if not v:
            continue
        media, const = st.mean(v), P.REP_MEDIA.get(tipo, 0.0)
        marca = ""
        if abs(media - const) >= UMBRAL[tipo]:
            marca = "  ⚠️ desfasada"
            avisos.append((tipo, round(media, 1)))
        print(f"{tipo:<9}{len(v):>6}{media:>12.1f}{const:>11.1f}{media - const:>+12.1f}{marca}")
    if True:
        activos = [c["dt_id"] for c in db["dt_cargos"].find({"hasta_juego": None}, {"dt_id": 1})]
        rep = {d["_id"]: d["puntaje"] for d in db["prensa_reputacion"].find({"tipo": "dt"}, {"puntaje": 1})}
        con = [rep[f"dt:{d}"] for d in activos if f"dt:{d}" in rep]
        if con:
            sesgo = -P.EFECTO_PRESION_DT * (st.mean(con) - P.REP_MEDIA["dt"]) / 100
            print(f"\nDT en funciones con reputación: {len(con)} de {len(activos)} · media {st.mean(con):.1f} · presión que suma la prensa por partido, en promedio: {sesgo:+.4f} (0 = neutral)")
    if avisos:
        print("\nPara recalibrar: actualiza REP_MEDIA en services/prensa.py →", ", ".join(f"{t}: {m}" for t, m in avisos))
    else:
        print("\nTodas las constantes están al día.")


if __name__ == "__main__":
    main()
