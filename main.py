from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.exception_handlers import http_exception_handler
from config.secciones import pagina_inicial
from services.auth_service import context_usuario_actual, es_request_html, obtener_usuario_actual, requiere_permiso
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
from routes.juego_en_vivo_route import route as juego_en_vivo_route
from routes.admin_route import route as admin_route
from routes.torneo_route import route_arbitros, route_cara_a_cara, route_cuadro, route_palmares, route_ranking


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

# Acceso por ROLES (config/secciones.py + colección 'roles', ver services/auth_service.py):
# cada router -- de PÁGINA y de API -- exige sesión activa y el permiso de su sección. Sin sesión,
# las páginas redirigen a /login (y las APIs responden 401); sin permiso, 403 (el handler de abajo
# lo muestra como página 'sin_permiso.html' cuando es navegación HTML). Las acciones sensibles
# dentro de un router (simular, reiniciar) tienen además su propia dependencia en la ruta.
#
# Excepciones a propósito: auth (login/logout/cuenta: hacen su propio chequeo) y la API de
# /matches/live* (live_match_route): sus GET son públicos -- los consume el badge flotante de
# base.html en todas las páginas -- y su única escritura (simulate-next-auto) exige
# 'simular_partidos' en la propia ruta.
def _permiso(*codigos):
    return [Depends(requiere_permiso(*codigos))]


app.include_router(auth_route)
app.include_router(home_route, dependencies=_permiso("inicio"))
app.include_router(simular_route, dependencies=_permiso("partidos"))
app.include_router(juegos_route, dependencies=_permiso("partidos"))
app.include_router(paises_route, dependencies=_permiso("paises"))
app.include_router(jugadores_route, dependencies=_permiso("paises"))
app.include_router(confederacion_route, dependencies=_permiso("paises"))
app.include_router(estadisticas_route, dependencies=_permiso("estadisticas"))
app.include_router(route_cara_a_cara, dependencies=_permiso("cara_a_cara"))
app.include_router(route_cuadro, dependencies=_permiso("cuadro"))
app.include_router(route_palmares, dependencies=_permiso("palmares"))
app.include_router(route_arbitros, dependencies=_permiso("arbitros"))
app.include_router(route_ranking, dependencies=_permiso("ranking_usuarios"))
app.include_router(prematch_route, dependencies=_permiso("scouter"))
app.include_router(prematch_vistas_route, dependencies=_permiso("scouter"))
app.include_router(live_match_route)
app.include_router(live_match_vistas_route, dependencies=_permiso("en_vivo"))
app.include_router(juego_en_vivo_route, dependencies=_permiso("juego_en_vivo"))
app.include_router(fanbase_route, dependencies=_permiso("aficionados"))
app.include_router(fanbase_vistas_route, dependencies=_permiso("aficionados"))
app.include_router(quinielas_route, dependencies=_permiso("quinielas"))
app.include_router(quinielas_vistas_route, dependencies=_permiso("quinielas"))
app.include_router(ownership_route, dependencies=_permiso("selecciones"))
app.include_router(ownership_vistas_route, dependencies=_permiso("selecciones"))
app.include_router(fantasy_route, dependencies=_permiso("once_ideal"))
app.include_router(fantasy_vistas_route, dependencies=_permiso("once_ideal"))
app.include_router(album_route, dependencies=_permiso("album"))
app.include_router(album_vistas_route, dependencies=_permiso("album"))
app.include_router(venue_route, dependencies=_permiso("sedes"))
app.include_router(venue_vistas_route, dependencies=_permiso("sedes"))
app.include_router(route_rewards, dependencies=_permiso("misiones"))
app.include_router(route_trivia, dependencies=_permiso("misiones"))
app.include_router(rewards_vistas_route, dependencies=_permiso("misiones"))
app.include_router(admin_route, dependencies=_permiso("gestion_usuarios"))


_templates_errores = Jinja2Templates(directory="templates", context_processors=[context_usuario_actual])


@app.exception_handler(StarletteHTTPException)
async def _manejar_http_exception(request: Request, exc: StarletteHTTPException):
    """403 en navegación HTML -> página amigable 'sin_permiso.html'; todo lo demás, igual que antes."""
    if exc.status_code == 403 and es_request_html(request):
        return _templates_errores.TemplateResponse(
            request=request, name="sin_permiso.html", status_code=403,
            context={"mensaje": exc.detail, "url_inicio": pagina_inicial((obtener_usuario_actual(request) or {}).get("permisos") or set())},
        )
    return await http_exception_handler(request, exc)
