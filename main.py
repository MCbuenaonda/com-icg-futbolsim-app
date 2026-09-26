from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from services.auth_service import exigir_sesion_activa
from routes.simular_route import route as simular_route
from routes.home_route import route as home_route
from routes.paises_route import route as paises_route
from routes.jugadores_route import route as jugadores_route
from routes.confederacion_route import route as confederacion_route
from routes.juegos_route import route as juegos_route
from routes.estadisticas_route import route as estadisticas_route
from routes.auth_route import route as auth_route
from routes.quinielas_route import route as quinielas_route, route_vistas as quinielas_vistas_route
from routes.ownership_route import route as ownership_route, route_vistas as ownership_vistas_route
from routes.fantasy_route import route as fantasy_route, route_vistas as fantasy_vistas_route
from routes.album_route import route as album_route, route_vistas as album_vistas_route
from routes.venue_route import route as venue_route, route_vistas as venue_vistas_route
from routes.rewards_route import route_rewards, route_trivia, route_vistas as rewards_vistas_route
from routes.prematch_route import route as prematch_route, route_vistas as prematch_vistas_route
from routes.live_match_route import route as live_match_route, route_vistas as live_match_vistas_route
from routes.fanbase_route import route as fanbase_route, route_vistas as fanbase_vistas_route


app = FastAPI(title="Simulador de Fútbol")

# Montar carpeta de archivos estáticos (CSS, JS, imágenes)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers de PÁGINA (renderizan HTML vía base.html): requieren sesión activa, ver
# services/auth_service.py::exigir_sesion_activa -- sin sesión, cualquier vista redirige a
# /login antes de renderizar, en vez de mostrar el dashboard/navbar del sistema. Los routers de
# API JSON (sin '_requiere_sesion') quedan sin tocar a propósito: varios GETs están documentados
# como públicos (ej. /matches/live) y varias rutas de meta-juego ya hacen su propio chequeo de
# sesión en escritura.
_requiere_sesion = [Depends(exigir_sesion_activa)]

app.include_router(home_route, dependencies=_requiere_sesion)
app.include_router(auth_route)
app.include_router(quinielas_route)
app.include_router(quinielas_vistas_route, dependencies=_requiere_sesion)
app.include_router(ownership_route)
app.include_router(ownership_vistas_route, dependencies=_requiere_sesion)
app.include_router(fantasy_route)
app.include_router(fantasy_vistas_route, dependencies=_requiere_sesion)
app.include_router(album_route)
app.include_router(album_vistas_route, dependencies=_requiere_sesion)
app.include_router(venue_route)
app.include_router(venue_vistas_route, dependencies=_requiere_sesion)
app.include_router(route_rewards)
app.include_router(route_trivia)
app.include_router(rewards_vistas_route, dependencies=_requiere_sesion)
app.include_router(simular_route, dependencies=_requiere_sesion)
app.include_router(paises_route, dependencies=_requiere_sesion)
app.include_router(jugadores_route, dependencies=_requiere_sesion)
app.include_router(confederacion_route, dependencies=_requiere_sesion)
app.include_router(juegos_route, dependencies=_requiere_sesion)
app.include_router(estadisticas_route, dependencies=_requiere_sesion)
app.include_router(prematch_route)
app.include_router(prematch_vistas_route, dependencies=_requiere_sesion)
app.include_router(live_match_route)
app.include_router(live_match_vistas_route, dependencies=_requiere_sesion)
app.include_router(fanbase_route)
app.include_router(fanbase_vistas_route, dependencies=_requiere_sesion)
