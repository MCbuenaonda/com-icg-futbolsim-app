"""
Script de mantenimiento para crear los índices recomendados en Mongo, según los
patrones de consulta más frecuentes de routes/services (mundial_id/fase_id/
confederacion_id/estado en 'internacional' y 'juegos', 'id' en 'paises',
'pais_id' en 'jugadores', 'puesto' en 'arbitros').

create_index es idempotente: si el índice ya existe con la misma definición no
hace nada, así que este script se puede volver a correr sin riesgo.

Correr localmente con: python3 crear_indices.py
"""
import certifi
from pymongo.mongo_client import MongoClient
from config.settings import MONGODB_URI

client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client.get_database('mundial')


def crear_indices():
    internacional = db['internacional']
    internacional.create_index(
        [("mundial_id", 1), ("confederacion_id", 1), ("fase_eliminatoria", 1)],
        name="mundial_confederacion_fase"
    )
    internacional.create_index("id", name="id")
    print("✅ Índices creados en 'internacional'")

    juegos = db['juegos']
    juegos.create_index(
        [("mundial_id", 1), ("fase_id", 1), ("confederacion_id", 1), ("grupo", 1)],
        name="mundial_fase_confederacion_grupo"
    )
    juegos.create_index("estado", name="estado")
    juegos.create_index("transmision.estado", name="transmision_estado")
    print("✅ Índices creados en 'juegos'")

    paises = db['paises']
    paises.create_index("id", name="id")
    # Usado por fanbase_service.obtener_ranking_aficionados (GET /countries/fanbase-ranking).
    paises.create_index("aficionados", name="aficionados")
    print("✅ Índices creados en 'paises'")

    historial_aficionados = db['historial_aficionados']
    historial_aficionados.create_index([("pais_id", 1), ("created_at", -1)], name="pais_fecha")
    print("✅ Índices creados en 'historial_aficionados'")

    jugadores = db['jugadores']
    jugadores.create_index("pais_id", name="pais_id")
    # 'posicion_id' + 'atajadas': usados por estadisticas_service._get_stats_porteros
    # para el leaderboard de porteros (más atajadas / valla invicta individual).
    jugadores.create_index("posicion_id", name="posicion_id")
    jugadores.create_index("atajadas", name="atajadas")
    print("✅ Índices creados en 'jugadores'")

    arbitros = db['arbitros']
    arbitros.create_index("puesto", name="puesto")
    print("✅ Índices creados en 'arbitros'")

    usuarios = db['usuarios']
    usuarios.create_index("username", unique=True, name="username")
    print("✅ Índices creados en 'usuarios'")

    quiniela_config = db['quiniela_config']
    quiniela_config.create_index("codigo", unique=True, name="codigo")
    print("✅ Índices creados en 'quiniela_config'")

    quiniela_usuario = db['quiniela_usuario']
    quiniela_usuario.create_index("usuario_id", name="usuario_id")
    quiniela_usuario.create_index(
        [("estado", 1), ("selecciones.juego_id", 1)],
        name="estado_selecciones_juego"
    )
    print("✅ Índices creados en 'quiniela_usuario'")

    paises = db['paises']
    paises.create_index("user_id", name="user_id")
    print("✅ Índice 'user_id' creado en 'paises'")

    team_ownerships = db['team_ownerships']
    team_ownerships.create_index("pais_id", name="pais_id")
    team_ownerships.create_index(
        [("user_id", 1), ("confederacion_id", 1), ("status", 1)],
        name="user_confederacion_status"
    )
    team_ownerships.create_index(
        [("pais_id", 1), ("status", 1)],
        name="pais_status"
    )
    print("✅ Índices creados en 'team_ownerships'")

    ownership_transactions = db['ownership_transactions']
    ownership_transactions.create_index("user_id", name="user_id")
    ownership_transactions.create_index("pais_id", name="pais_id")
    print("✅ Índices creados en 'ownership_transactions'")

    fantasy_teams = db['fantasy_teams']
    fantasy_teams.create_index([("user_id", 1), ("fase_id", 1)], unique=True, name="user_fase")
    fantasy_teams.create_index([("fase_id", 1), ("lineup", 1)], name="fase_lineup")
    print("✅ Índices creados en 'fantasy_teams'")

    fantasy_points_history = db['fantasy_points_history']
    fantasy_points_history.create_index([("user_id", 1), ("fase_id", 1), ("created_at", -1)], name="user_fase_fecha")
    print("✅ Índices creados en 'fantasy_points_history'")

    # Recompensa pasiva del Álbum para estampas de jugador sin lineup (caso b, ver
    # fantasy_service.procesar_eventos_jugadores_partido); lo consulta album_service
    # para marcar en el Álbum qué estampas ya dieron alguna regalía.
    album_passive_rewards = db['album_passive_rewards']
    album_passive_rewards.create_index([("user_id", 1), ("tipo_estampa", 1), ("item_id", 1)], name="user_tipo_item")
    print("✅ Índices creados en 'album_passive_rewards'")

    user_albums = db['user_albums']
    user_albums.create_index("user_id", unique=True, name="user_id")
    user_albums.create_index("owned_jugadores", name="owned_jugadores")
    # 'owned_paises' lo usa la sinergia de Álbum en ownership_service._abonar_puntos_dueno
    # y 'owned_ciudades' la sinergia de Álbum en venue_service.process_match_city_revenue.
    user_albums.create_index("owned_paises", name="owned_paises")
    user_albums.create_index("owned_ciudades", name="owned_ciudades")
    print("✅ Índices creados en 'user_albums'")

    pack_purchases = db['pack_purchases']
    pack_purchases.create_index("user_id", name="user_id")
    print("✅ Índice creado en 'pack_purchases'")

    # Nota: 'jugadores.pais_id' ya tiene índice (creado más arriba, sección de 'jugadores')
    # y lo reutilizan tanto ownership_service como fantasy_service/album_service.

    ciudades = db['ciudades']
    ciudades.create_index("id", name="id")
    ciudades.create_index("pais_id", name="pais_id")
    ciudades.create_index("owner_user_id", name="owner_user_id")
    print("✅ Índices creados en 'ciudades'")

    city_ownerships = db['city_ownerships']
    city_ownerships.create_index(
        [("user_id", 1), ("pais_id", 1), ("status", 1)],
        name="user_pais_status"
    )
    city_ownerships.create_index(
        [("ciudad_id", 1), ("status", 1)],
        name="ciudad_status"
    )
    print("✅ Índices creados en 'city_ownerships'")

    city_revenue_history = db['city_revenue_history']
    city_revenue_history.create_index("user_id", name="user_id")
    city_revenue_history.create_index("ciudad_id", name="ciudad_id")
    print("✅ Índices creados en 'city_revenue_history'")

    user_daily_rewards = db['user_daily_rewards']
    user_daily_rewards.create_index("user_id", unique=True, name="user_id")
    print("✅ Índices creados en 'user_daily_rewards'")

    trivia_history = db['trivia_history']
    trivia_history.create_index([("user_id", 1), ("session_date", 1)], name="user_session_date")
    print("✅ Índices creados en 'trivia_history'")

    reward_transactions = db['reward_transactions']
    reward_transactions.create_index("user_id", name="user_id")
    print("✅ Índices creados en 'reward_transactions'")


if __name__ == "__main__":
    crear_indices()
