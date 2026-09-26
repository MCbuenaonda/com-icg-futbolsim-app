"""
Marcas rápidas (íconos) para la vista del simulador: por cada país de un
partido, indican si el usuario logueado tiene algo relacionado con ese país
en otros módulos de la app — para poder identificar de un vistazo si "tiene
algo en juego" en el partido que está mirando.

Decisiones de diseño:
- Quiniela: se marca el lado (LOCAL/VISITA) que el usuario pronosticó en
  ALGUNA de sus quinielas para este partido puntual (mismo juego_id) — un
  pronóstico de EMPATE no tiene un país al que atribuirle la marca, así que
  no enciende ningún lado (si tiene un pronóstico de LOCAL en un boleto y de
  VISITA en otro, se marcan los dos lados).
- Fantasy: se marca el lado si algún jugador de esa selección está en el Once
  Ideal del usuario para la fase de ESTE partido (fase_id) — no cualquier
  alineación del usuario, la que corresponde a esta fase puntual.
- Dueño de sede/ciudad: NO es una marca "por país" (la sede no le pertenece a
  ninguno de los dos equipos necesariamente — en fases finales se juega en el
  país anfitrión del Mundial, que puede no ser ni el local ni el visitante),
  así que se devuelve aparte en 'dueno_sede', no mezclada en 'local'/'visita'.
"""
import certifi
from typing import Any, Dict, Optional
from bson import ObjectId
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')


def _tiene_dueno(valor_user_id: Any, usuario_oid: ObjectId) -> bool:
    """Mismo criterio que ownership_service/venue_service: 0/'0'/None = sin dueño."""
    return valor_user_id not in (0, "0", None, "") and str(valor_user_id) == str(usuario_oid)


def obtener_marcas_partido(
    usuario_id: str,
    juego_id: str,
    id_local: int,
    id_visita: int,
    fase_id: Optional[int],
    ciudad_id: Optional[int]
) -> Dict[str, Any]:
    """
    Devuelve: {
        "local": {"quiniela": bool, "fantasy": bool, "dueno_pais": bool},
        "visita": {"quiniela": bool, "fantasy": bool, "dueno_pais": bool},
        "dueno_sede": bool
    }
    Todas las consultas son defensivas (try/except) para que un error acá
    nunca tumbe la vista del partido — es información puramente informativa.
    """
    usuario_oid = ObjectId(usuario_id)
    marcas_local = {"quiniela": False, "fantasy": False, "dueno_pais": False}
    marcas_visita = {"quiniela": False, "fantasy": False, "dueno_pais": False}
    dueno_sede = False

    # --- Quiniela: pronósticos del usuario para ESTE partido ---
    try:
        juego_oid = ObjectId(juego_id)
        pronosticos = set()
        for boleto in db['quiniela_usuario'].find(
            {"usuario_id": usuario_oid, "selecciones.juego_id": juego_oid},
            {"selecciones": 1}
        ):
            for s in boleto.get("selecciones", []):
                if s.get("juego_id") == juego_oid:
                    pronosticos.add(s.get("pronostico"))
        marcas_local["quiniela"] = "LOCAL" in pronosticos
        marcas_visita["quiniela"] = "VISITA" in pronosticos
    except Exception:
        pass

    # --- Fantasy: jugadores de cada país en el Once Ideal del usuario para esta fase ---
    try:
        if fase_id is not None:
            equipo = db['fantasy_teams'].find_one({"user_id": usuario_oid, "fase_id": fase_id}, {"lineup": 1})
            lineup = equipo.get("lineup") if equipo else None
            if lineup:
                paises_en_lineup = {
                    j["pais_id"] for j in db['jugadores'].find(
                        {"id": {"$in": lineup}, "pais_id": {"$in": [id_local, id_visita]}},
                        {"pais_id": 1}
                    )
                }
                marcas_local["fantasy"] = id_local in paises_en_lineup
                marcas_visita["fantasy"] = id_visita in paises_en_lineup
    except Exception:
        pass

    # --- Dueño de selección (país) ---
    try:
        pais_local_doc = db['paises'].find_one({"id": id_local}, {"user_id": 1})
        pais_visita_doc = db['paises'].find_one({"id": id_visita}, {"user_id": 1})
        if pais_local_doc:
            marcas_local["dueno_pais"] = _tiene_dueno(pais_local_doc.get("user_id", 0), usuario_oid)
        if pais_visita_doc:
            marcas_visita["dueno_pais"] = _tiene_dueno(pais_visita_doc.get("user_id", 0), usuario_oid)
    except Exception:
        pass

    # --- Dueño de sede/ciudad ---
    try:
        if ciudad_id is not None:
            ciudad_doc = db['ciudades'].find_one({"id": ciudad_id}, {"owner_user_id": 1})
            if ciudad_doc:
                dueno_sede = _tiene_dueno(ciudad_doc.get("owner_user_id", 0), usuario_oid)
    except Exception:
        pass

    return {"local": marcas_local, "visita": marcas_visita, "dueno_sede": dueno_sede}
