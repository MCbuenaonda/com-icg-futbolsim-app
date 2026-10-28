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
    jugadores.create_index("leyenda", name="leyenda", sparse=True)   # leyendas (agregar_leyendas.py)
    print("✅ Índices creados en 'jugadores'")

    arbitros = db['arbitros']
    arbitros.create_index("puesto", name="puesto")
    # 'id' numérico (asignar_id_arbitros.py): estampas de árbitro del álbum (user_albums.owned_arbitros)
    arbitros.create_index("id", name="id", unique=True)
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

    # Evolución de especialidades (services/especialidades_service.py): por jugador (ficha), partido (resumen) y país (plantilla)
    historial_esp = db['especialidades_historial']
    historial_esp.create_index([("jugador_id", 1), ("fecha", -1)], name="jugador_fecha")
    historial_esp.create_index([("juego_id", 1)], name="juego")
    historial_esp.create_index([("pais_id", 1), ("fecha", 1)], name="pais_fecha")
    print("✅ Índices creados en 'especialidades_historial'")

    fantasy_teams = db['fantasy_teams']
    # Once Ideal: uno por usuario y Mundial (ya no por fase; services/fantasy_service.py). Si en la base quedó el
    # índice único viejo user_fase, no molesta: el equipo nuevo no tiene fase_id (se indexa como null) y hay uno solo
    # por usuario; restart_mundial borra fantasy_teams.
    fantasy_teams.create_index([("user_id", 1), ("mundial_id", 1)], name="user_mundial")
    fantasy_teams.create_index([("mundial_id", 1), ("lineup", 1)], name="mundial_lineup")
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

    # Niveles (services/niveles_service.py): el índice único es lo que hace idempotente a otorgar_xp
    # (una acción nunca suma XP dos veces) y el de fecha cuenta los topes diarios.
    xp_eventos = db['xp_eventos']
    xp_eventos.create_index([("user_id", 1), ("accion", 1), ("ref", 1)], name="user_accion_ref", unique=True)
    xp_eventos.create_index([("user_id", 1), ("fecha", 1), ("accion", 1)], name="user_fecha_accion")
    xp_eventos.create_index([("user_id", 1), ("creado_en", -1)], name="user_creado")
    db['recompensas_nivel'].create_index([("user_id", 1), ("nivel", 1)], name="user_nivel", unique=True)
    print("✅ Índices creados en 'xp_eventos' y 'recompensas_nivel'")

    # Corporativos Deportivos (services/corporativo_universo_service.py): registro global de partidos (seq y
    # juego_id únicos), un corporativo por sigla en cada universo y la exclusividad de los contratos activos.
    from services.corporativo_universo_service import asegurar_indices
    asegurar_indices()
    print("✅ Índices creados en las colecciones 'corp_*'")

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

    asistente_consultas = db['asistente_consultas']
    asistente_consultas.create_index([("user_id", 1), ("fecha", -1)], name="user_fecha")
    asistente_consultas.create_index([("user_id", 1), ("dia", 1)], name="user_dia")
    print("✅ Índices creados en 'asistente_consultas'")
    db['asistente_descartes'].create_index([("user_id", 1), ("dia", 1), ("clave", 1)], name="user_dia_clave")
    print("✅ Índices creados en 'asistente_descartes'")


if __name__ == "__main__":
    crear_indices()
