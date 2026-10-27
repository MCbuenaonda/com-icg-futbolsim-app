"""
Calibración de las FORMACIONES (config/formaciones.py + services/formaciones.py) con Monte Carlo. SOLO LECTURA: simula
partidos con simular_partido_realista sin guardar nada (las consultas a Mongo se cachean en memoria).

Uso:
    python calibrar_formaciones.py --promedios [N]     # goles/tarjetas por partido con la elección normal del DT vs. los reales
    python calibrar_formaciones.py --matriz [N]        # esquema contra esquema: % de victorias y goles (N partidos por celda)
    python calibrar_formaciones.py --eleccion [N]      # cuánto vale elegir el mejor esquema contra el del rival

Criterios (ver CLAUDE.md): goles y tarjetas por partido del torneo sin cambio (±2-3%), ningún esquema dominante, una elección
óptima frente al rival vale ~5-8 puntos de probabilidad de ganar.
"""
import random
import statistics
import sys
import time

from services import simular_service as S
from services import tecnicos_service as TS
from config import formaciones as CF

# --- Caché de lecturas (el motor consulta Mongo en cada partido) ---------------------------------------------------
_cache_find, _cache_find_one = {}, {}


class _Coleccion:
    def __init__(self, real):
        self.real = real

    def find(self, filtro=None, *a, **k):
        clave = repr((filtro, a, sorted(k.items())))
        if clave not in _cache_find:
            _cache_find[clave] = list(self.real.find(filtro, *a, **k))
        return [dict(x) for x in _cache_find[clave]]

    def find_one(self, filtro=None, *a, **k):
        clave = repr((filtro, a, sorted(k.items())))
        if clave not in _cache_find_one:
            _cache_find_one[clave] = self.real.find_one(filtro, *a, **k)
        d = _cache_find_one[clave]
        return dict(d) if d else d

    def __getattr__(self, nombre):
        return getattr(self.real, nombre)


class _Base:
    """La base del motor con lecturas en caché (las colecciones se crean dentro de simular_partido_realista)."""
    def __init__(self, real):
        self.real, self.cols = real, {}

    def __getitem__(self, nombre):
        if nombre not in self.cols:
            self.cols[nombre] = _Coleccion(self.real[nombre])
        return self.cols[nombre]

    def __getattr__(self, nombre):
        return self[nombre] if not nombre.startswith("_") else getattr(self.real, nombre)


_db_real = S.db
S.db = _Base(S.db)
_arbitros = []
_real_cuarteta = S.obtener_cuarteta_arbitral


def _cuarteta(excluir=()):
    if len(_arbitros) < 40:
        _arbitros.append(_real_cuarteta(excluir))
    return random.choice(_arbitros)


S.obtener_cuarteta_arbitral = _cuarteta
_dts = {}
_real_dt = S.obtener_dt_en_funciones


def _dt(pais):
    pid = (pais or {}).get("id")
    if pid not in _dts:
        _dts[pid] = _real_dt(pais)
    return _dts[pid]


S.obtener_dt_en_funciones = _dt
_ctx = {}
_real_ctx = TS.contexto_tactico


def _contexto(*a, **k):
    clave = repr((a[:2], a[4:], k))
    if clave not in _ctx:
        _ctx[clave] = _real_ctx(*a, **k)
    return _ctx[clave]


TS.contexto_tactico = _contexto
_memo = {}
_real_rating, _real_forma = TS._rating, TS._forma
TS._rating = lambda pid: _memo.setdefault(("r", pid), _real_rating(pid)) if ("r", pid) not in _memo else _memo[("r", pid)]
TS._forma = lambda pid: _memo.setdefault(("f", pid), _real_forma(pid)) if ("f", pid) not in _memo else _memo[("f", pid)]


def _pares(n: int, semilla: int = 7) -> list:
    """Pares de selecciones del Mundial en curso (vivas) para simular."""
    ids = sorted(d["id"] for d in _db_real["internacional"].find({}, {"id": 1}))
    rng = random.Random(semilla)
    grupo = rng.sample(ids, min(len(ids), 24))   # 24 selecciones: las lecturas se cachean rápido
    return [tuple(rng.sample(grupo, 2)) for _ in range(n)]


def _tarjetas(p) -> int:
    return sum(1 for e in p["eventos"] if any(k in (e.get("tipo") or "") for k in ("AMARILLA", "ROJA")) and "DT" not in (e.get("tipo") or ""))


def _jugar(par, esquemas=None):
    p, _ = S.simular_partido_realista(par[0], par[1], esquemas_forzados=esquemas)
    return p["goles_local"], p["goles_visitante"], _tarjetas(p)


def promedios(n: int) -> None:
    reales = list(_db_real["juegos"].find({"estado": "finalizado", "resultado.goles_local": {"$exists": True}},
                                     {"resultado.goles_local": 1, "resultado.goles_visitante": 1}).limit(3000))
    goles_reales = statistics.mean((j["resultado"]["goles_local"] or 0) + (j["resultado"]["goles_visitante"] or 0) for j in reales)
    t = time.time()
    goles, tarjetas = [], []
    for par in _pares(n):
        gl, gv, tj = _jugar(par)
        goles.append(gl + gv)
        tarjetas.append(tj)
    print(f"{n} partidos en {time.time() - t:.0f}s")
    print(f"goles/partido: simulado {statistics.mean(goles):.3f} (±{1.96 * statistics.stdev(goles) / n ** 0.5:.3f})  vs jugados {goles_reales:.3f}")
    print(f"tarjetas/partido: {statistics.mean(tarjetas):.2f}")


def matriz(n: int) -> None:
    pares = _pares(n, 11)
    lista = [e for e in (sys.argv[3].split(",") if len(sys.argv) > 3 else CF.ESQUEMAS)]
    print("victorias del esquema de la fila (local y visita alternados) | goles totales por partido")
    resultados = {}
    for a in lista:
        fila = []
        for b in lista:
            g = e = 0
            goles = []
            for i, par in enumerate(pares):
                if i % 2:
                    gl, gv, _ = _jugar(par, (a, b))
                    mio, suyo = gl, gv
                else:
                    gl, gv, _ = _jugar(par, (b, a))
                    mio, suyo = gv, gl
                g += mio > suyo
                e += mio == suyo
                goles.append(gl + gv)
            pts = (3 * g + e) / n
            resultados[(a, b)] = (g / n, pts, statistics.mean(goles))
            fila.append(f"{g / n:4.0%}/{statistics.mean(goles):.1f}")
        print(f"{a:8} " + " ".join(fila))
        sys.stdout.flush()
    print("\npuntos medios por esquema (contra todos):")
    for a in lista:
        print(f"  {a:8} {statistics.mean(resultados[(a, b)][1] for b in lista):.3f} pts/partido")


def eleccion(n: int) -> None:
    """Contra un rival que juega su esquema, cuánto gana el que elige el mejor esquema vs el que elige el peor (según ventaja)."""
    from services import formaciones as FS
    pares = _pares(n, 13)
    rivales = ["4-3-3", "4-4-2", "3-5-2", "4-5-1"]
    for r in rivales:
        orden = sorted(CF.ESQUEMAS, key=lambda e: FS.ventaja(e, r))
        peor, mejor = orden[0], orden[-1]
        res = {}
        for esq in (peor, "4-4-2", mejor):
            g = 0
            for i, par in enumerate(pares):
                gl, gv, _ = _jugar(par, (esq, r) if i % 2 else (r, esq))
                mio, suyo = (gl, gv) if i % 2 else (gv, gl)
                g += mio > suyo
            res[esq] = g / n
        print(f"contra {r}: mejor {mejor} {res[mejor]:.1%} | 4-4-2 {res['4-4-2']:.1%} | peor {peor} {res[peor]:.1%}")
        sys.stdout.flush()


if __name__ == "__main__":
    if "--sin-efecto" in sys.argv:   # referencia: el mismo motor sin el efecto de la formación
        CF.ESCALA_PERFIL = CF.PUNTOS_SUPERIORIDAD = CF.POSTURA_TIRO = CF.POSTURA_PROFUNDO = 0.0
        sys.argv.remove("--sin-efecto")
    modo = sys.argv[1] if len(sys.argv) > 1 else ""
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    {"--promedios": promedios, "--matriz": matriz, "--eleccion": eleccion}.get(modo, lambda n: print(__doc__))(n)
