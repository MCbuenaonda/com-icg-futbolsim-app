"""
Recorrido del balón para la cancha en vivo (lógica pura).

El motor (services/simular_service.py) trabaja por ZONAS, no por posiciones. Antes cada evento sorteaba la posición del
balón al azar dentro de su zona: la pelota saltaba de banda a banda y un disparo podía salir de un lugar distinto al de su
preparación. El Seguidor recuerda dónde quedó el balón y mueve cada jugada desde ahí, según el tipo de evento, la zona
del motor y el CARRIL del jugador que la recibe (su posición lateral en la formación, mismo cálculo que
posicionesBaseFormacion de static/js/live_match.js). También junta los pases y conducciones que el motor no narra
(«toques») para que la transmisión los anime entre un evento y el siguiente.

Coordenadas ABSOLUTAS de la cancha: x 0-100 (el local ataca hacia la derecha, x = 100), y 0-68. Internamente se calcula en
el «marco» del equipo con la pelota (x hacia el arco rival) y se convierte al guardar. Cada evento de jugada recibe:
    balon = {"o": [x, y], "d": [x, y], "t": trayectoria, "l": 1 si atacaba el local, "q": [[x, y, nombre, t], ...]}
(en q, t = "r" raso, "a" aéreo, "c" conducción)
trayectoria: "raso" | "aereo" | "tiro" | "conduccion" | "parado" | "colocar" | "fuera".
Los avisos (sustituciones, árbitro, VAR) no llevan 'balon' y no mueven la pelota.

Usa su propio random.Random: no consume el azar del motor, así que goles, tarjetas y calibraciones no cambian.
"""
import random
from typing import Callable, Dict, List, Optional, Tuple

ANCHO = 68.0
CENTRO = (50.0, 34.0)
RANGO_ZONA = {"defensa": (6.0, 33.0), "medio": (33.0, 66.0), "ataque": (66.0, 95.0)}
PUNTO_PENAL = (89.0, 34.0)
ARCO_Y = (30.4, 37.6)          # entre los palos (7,32 m)
MAX_TOQUES = 8                 # pases sin narrar que se guardan por evento (los más recientes)
# Lo más que avanza la pelota en un toque: la zona del motor es un objetivo al que se llega de a poco (al recuperar en
# su propio campo el motor ya pone al equipo «en el medio», y un regate lo pasa «al ataque»: no son 50 m de una vez)
AVANCE_MAX = {"conduccion": 12.0, "pase": 40.0, "remate": 22.0}
ZONA_REMATE = 68.0             # desde dónde se remata en jugada (en el marco del que ataca)

TIPOS_GOL = {"⚽ GOL", "⚽ GOL DE PENAL", "⚽ GOL DE TIRO LIBRE", "⚽ GOL DE CÓRNER"}
TIPOS_ATAJADA = {"🧤 ATAJADA ESPECTACULAR", "❌ PENAL FALLADO"}
TIPOS_REINICIO_CENTRO = {"👉 SILBATO INICIAL", "🔵 COMIENZA EL SEGUNDO TIEMPO", "🔵 SEGUNDO TIEMPO EXTRA", "⏱️ TIEMPO EXTRA"}
TIPOS_INTERCEPCION = {"⚡ EN TRANSICIÓN", "🧠 ROBO DE BALÓN"}
TIPOS_TARJETA = {"🟨 TARJETA AMARILLA", "🟥 TARJETA ROJA", "🟨🟥 DOBLE AMARILLA"}
# Avisos: misma lista que esEventoAviso de live_match.js (sustitución, árbitro y VAR): no mueven la pelota
TIPOS_AVISO = {
    "🔄 SUSTITUCIÓN", "👉 SILBATO INICIAL", "🚩 FINAL DEL PRIMER TIEMPO", "⏱️ TIEMPO EXTRA", "🥅 TANDA DE PENALTIS",
    "🏁 PITIDO FINAL", "⏱️ TIEMPO AÑADIDO", "🔵 COMIENZA EL SEGUNDO TIEMPO", "🔵 SEGUNDO TIEMPO EXTRA", "🖥️ REVISIÓN VAR",
    "🚩 SAQUE DE ESQUINA", "🎯 PENAL", "🗣️ RECLAMO DEL DT", "🟨 DT AMONESTADO", "🟥 DT EXPULSADO", "📋 AJUSTE TÁCTICO",
    "🚑 LESIÓN",
}


def _limitar(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def carriles(lineas: List[int]) -> Dict[int, float]:
    """y de cada puesto (slot 1..11) en la formación: cada línea repartida pareja a lo ancho (como el JS)."""
    por_linea: Dict[int, List[int]] = {}
    for i, linea in enumerate(lineas, start=1):
        por_linea.setdefault(linea, []).append(i)
    salida = {}
    for slots in por_linea.values():
        n = len(slots)
        for k, slot in enumerate(slots):
            salida[slot] = ANCHO * (k + 1) / (n + 1)
    return salida


class Seguidor:
    """
    estado() -> (el local tiene la pelota, zona del motor, nombre del que la tiene).
    carril(nombre) -> y de ese jugador en su formación (o None si no está en cancha).
    """

    def __init__(self, estado: Callable[[], Tuple[bool, str, str]], carril: Callable[[str], Optional[float]], semilla=None):
        self.estado = estado
        self.carril = carril
        self.rng = random.Random(semilla)
        self.x, self.y = CENTRO           # absolutas
        self.toques: List[list] = []      # [ox, oy, dx, dy, nombre, t] absolutas, pendientes del próximo evento
        self.inicio_cadena = None         # dónde arrancó la cadena de toques (se conserva aunque se recorten los viejos)
        self.penal = False                # hubo penal: la próxima preparación va al punto
        self.corner = None                # lado del córner pendiente (y de la banderita)
        self.falta = None                 # (x, y) absolutas de la última falta (tiro libre)
        self.tanda = False

    # --- marcos ---
    def _local(self) -> bool:
        return bool(self.estado()[0])

    def _rel(self, x: float) -> float:
        """Absoluta -> marco del equipo con la pelota (y al revés: es su propia inversa)."""
        return x if self._local() else 100.0 - x

    def _actual_rel(self) -> Tuple[float, float]:
        return self._rel(self.x), self.y

    def _y_hacia(self, nombre: Optional[str], ruido: float = 7.0) -> float:
        c = self.carril(nombre) if nombre else None
        if c is None:
            c = self.y
        return _limitar(0.3 * self.y + 0.7 * c + self.rng.uniform(-ruido, ruido), 3.0, 65.0)

    def _x_en_zona(self, x: float, zona: str, paso: Tuple[float, float], tope: Optional[float] = None) -> float:
        """x tras un toque: el paso sorteado, llevado hacia la zona del motor sin avanzar ni retroceder más que 'tope'."""
        lo, hi = RANGO_ZONA.get(zona, RANGO_ZONA["medio"])
        nuevo = x + self.rng.uniform(*paso)
        if nuevo < lo:
            nuevo = self.rng.uniform(lo, min(hi, lo + 12))
        elif nuevo > hi:
            nuevo = self.rng.uniform(max(lo, hi - 12), hi)
        if tope is not None:
            nuevo = max(x - tope, min(x + tope, nuevo))
        return nuevo

    def _mover_rel(self, xr: float, y: float) -> Tuple[float, float]:
        """Mueve el balón a (xr en el marco actual, y) y devuelve el destino ABSOLUTO."""
        self.x, self.y = self._rel(_limitar(xr, 0.0, 100.0)), _limitar(y, 0.0, ANCHO)
        return self.x, self.y

    # --- toques sin narrar ---
    def toque(self, nombre: str, tipo: str = "raso") -> None:
        """Un pase completado (o una conducción) que el motor no narra: se anima antes del próximo evento."""
        _, zona, _ = self.estado()
        self.falta = None                 # se siguió jugando: ya no hay tiro libre pendiente
        ox, oy = self.x, self.y
        if not self.toques:
            self.inicio_cadena = (ox, oy)
        xr, _ = self._actual_rel()
        if tipo == "conduccion":
            dx = self._x_en_zona(xr, zona, (5, 12), AVANCE_MAX["conduccion"])
            dy = _limitar(self.y + self.rng.uniform(-5, 5), 3.0, 65.0)
        else:
            paso = (-12, -2) if self.rng.random() < 0.22 else (4, 18)
            dx = self._x_en_zona(xr, zona, paso, AVANCE_MAX["pase"])
            dy = self._y_hacia(nombre)
        self._mover_rel(dx, dy)
        largo = ((self.x - ox) ** 2 + (self.y - oy) ** 2) ** 0.5
        t = "conduccion" if tipo == "conduccion" else ("aereo" if largo > 32 else "raso")
        self.toques.append([ox, oy, self.x, self.y, nombre, t])
        if len(self.toques) > MAX_TOQUES:
            self.toques = self.toques[-MAX_TOQUES:]

    # --- eventos ---
    def evento(self, tipo: str, jugadores: list) -> Optional[dict]:
        """Mueve el balón según el evento y devuelve el campo 'balon' (None para los avisos, que no lo mueven)."""
        if tipo == "🥅 TANDA DE PENALTIS":
            self.tanda = True
        if tipo in ("🎯 PENAL", "🖥️ VAR - PENAL"):
            self.penal = True
        if tipo in TIPOS_REINICIO_CENTRO:
            self.x, self.y = CENTRO
            self.toques = []
        if tipo in TIPOS_AVISO or tipo.startswith("🖥️ VAR"):
            return None

        jugadores = jugadores or []
        _, zona, _ = self.estado()
        ox, oy = self.x, self.y
        xr, yr = self._actual_rel()
        t = "parado"
        q = self.toques

        if self.tanda and (tipo in TIPOS_GOL or tipo in TIPOS_ATAJADA or tipo == "⏳ PREPARACIÓN"):
            # tanda: siempre en el arco de la derecha, desde el punto penal
            if tipo == "⏳ PREPARACIÓN":
                self.x, self.y = PUNTO_PENAL
                ox, oy, t = self.x, self.y, "colocar"
            else:
                ox, oy = PUNTO_PENAL
                self.x = 100.0 if tipo in TIPOS_GOL else 97.5
                self.y = self.rng.uniform(*ARCO_Y) if tipo in TIPOS_GOL else self.rng.uniform(29, 39)
                t = "tiro"
            q = []

        elif tipo == "🔵 SAQUE DE CENTRO":
            ox, oy = CENTRO
            self._mover_rel(self.rng.uniform(40, 45), self._y_hacia(jugadores[1] if len(jugadores) > 1 else None, 4))
            t = "raso"

        elif tipo == "⏳ PREPARACIÓN":
            if self.penal:
                self.penal = False
                self._mover_rel(*PUNTO_PENAL)
                ox, oy, t = self.x, self.y, "colocar"
            elif self.corner is not None and len(jugadores) == 2:
                # el centro desde la banderita al área, donde espera el rematador
                ox, oy = self.x, self.y
                self._mover_rel(self.rng.uniform(87, 94), _limitar(self._y_hacia(jugadores[0], 5), 24, 44))
                t, self.corner = "aereo", None
            elif self.falta is not None and len(jugadores) == 1:
                # tiro libre: el balón quieto donde fue la falta (fuera del área)
                fx, fy = self.falta
                self.x, self.y = fx, fy
                xr2, _ = self._actual_rel()
                if xr2 < 64:              # tiro libre directo: a tiro de arco (si la pelota iba rezagada)
                    xr2 = self.rng.uniform(66, 76)
                self._mover_rel(min(xr2, 80.0), fy)
                ox, oy, t = self.x, self.y, "colocar"
                self.falta = None
            elif len(jugadores) == 2:
                # pase al que va a rematar: si el último toque ya es ese pase, se narra aquí en vez de dos veces
                if q and q[-1][4] == jugadores[1]:
                    ox, oy, self.x, self.y = q[-1][0], q[-1][1], q[-1][2], q[-1][3]
                    q = q[:-1]
                else:
                    self._mover_rel(self._x_en_zona(xr, zona, (4, 16)), self._y_hacia(jugadores[1]))
                if self._actual_rel()[0] < ZONA_REMATE:
                    # el que va a rematar la recibe en zona de tiro: en un contraataque es un pase largo
                    self._mover_rel(self.rng.uniform(ZONA_REMATE + 2, ZONA_REMATE + 16), self.y)
                largo = ((self.x - ox) ** 2 + (self.y - oy) ** 2) ** 0.5
                t = "aereo" if largo > 28 or abs(self.y - oy) > 22 else "raso"
            else:
                # se acomoda para rematar; si quedó lejos del arco es una corrida de contraataque hasta la zona de tiro
                destino = max(self._x_en_zona(xr, zona, (3, 9), AVANCE_MAX["remate"]), self.rng.uniform(ZONA_REMATE, ZONA_REMATE + 8))
                self._mover_rel(destino, _limitar(yr + (34 - yr) * 0.3, 3, 65))
                t = "conduccion"

        elif tipo in TIPOS_GOL:
            self._mover_rel(100.0, self.rng.uniform(*ARCO_Y))
            t = "tiro"
        elif tipo in TIPOS_ATAJADA:
            self._mover_rel(97.5, self.rng.uniform(29, 39))
            t = "tiro"
        elif tipo == "🖐️ DESVÍO A CÓRNER":
            arriba = yr < 34 if self.rng.random() < 0.7 else yr >= 34
            self._mover_rel(100.0, self.rng.uniform(24, 29) if arriba else self.rng.uniform(39, 44))
            self.corner = 0.6 if arriba else ANCHO - 0.6
            t = "tiro"
        elif tipo == "🎯 DISPARO DESVIADO":
            arriba = self.rng.random() < 0.5
            self._mover_rel(100.0, self.rng.uniform(19, 29.6) if arriba else self.rng.uniform(38.4, 49))
            t = "tiro"
        elif tipo == "🛡️ CÓRNER DESPEJADO":
            self._mover_rel(self.rng.uniform(64, 78), self.rng.uniform(10, 58))
            t, self.corner = "aereo", None
        elif tipo in TIPOS_INTERCEPCION:
            # el pase o la conducción que falla: la pelota avanza un poco y ahí la corta el rival
            self._mover_rel(self._x_en_zona(xr, zona, (2, 10), AVANCE_MAX["conduccion"]), _limitar(yr + self.rng.uniform(-8, 8), 3, 65))
            t = "raso"
        elif tipo == "🔥 PRESIÓN DEFENSIVA":
            self._mover_rel(self._x_en_zona(xr, zona, (0, 4), AVANCE_MAX["conduccion"]), _limitar(yr + self.rng.uniform(-3, 3), 3, 65))
            t = "conduccion"
        elif tipo == "⚡ REGATE DESTACADO":
            self._mover_rel(self._x_en_zona(xr, zona, (6, 14), AVANCE_MAX["conduccion"]), _limitar(yr + self.rng.uniform(-7, 7), 3, 65))
            t = "conduccion"
        elif tipo == "↔️ SAQUE DE BANDA":
            self._mover_rel(_limitar(xr + self.rng.uniform(0, 6), 2, 98), 0.0 if yr < 34 else ANCHO)
            t = "fuera"
        elif tipo == "🛑 FALTA":
            self.falta = (self.x, self.y)
        # el resto (tarjetas, fuera de lugar, error de portería, desgaste...) deja la pelota donde está

        # la falta y el córner pendientes solo valen para la jugada que sigue (las tarjetas no cuentan)
        if tipo not in TIPOS_TARJETA and tipo != "🛑 FALTA":
            self.falta = None
        if tipo not in ("🖐️ DESVÍO A CÓRNER", "⏳ PREPARACIÓN"):
            self.corner = None
        self.toques = []
        salida = {"o": [round(ox, 1), round(oy, 1)], "d": [round(self.x, 1), round(self.y, 1)], "t": t,
                  "l": 1 if self._local() else 0,   # 1 = atacaba el local (colores y bloques de la cancha)
                  # dónde estaba la pelota al empezar la jugada (tras un gol, el centro): si no es donde terminó la
                  # anterior, la transmisión la coloca ahí en vez de arrastrarla
                  "s": [round(v, 1) for v in (self.inicio_cadena if q and self.inicio_cadena else (ox, oy))],
                  "q": [[round(a[2], 1), round(a[3], 1), a[4], a[5][0]] for a in q]}

        # después de la jugada: dónde queda la pelota para el próximo evento
        if tipo in TIPOS_GOL and not self.tanda:
            self.x, self.y = CENTRO                       # saque del medio
        elif tipo == "🎯 DISPARO DESVIADO":
            self._mover_rel(94.0, 34.0)                   # saque de arco del rival
        elif tipo == "🖐️ DESVÍO A CÓRNER" and self.corner is not None:
            self._mover_rel(99.4, self.corner)            # a la banderita
        elif tipo in TIPOS_ATAJADA and not self.tanda:
            self._mover_rel(96.0, 34.0)                   # en las manos del arquero
        return salida

    def posicion_rel(self, balon: dict) -> dict:
        """'posicion_balon' de siempre (destino en el marco del equipo con la pelota), para quien no lea 'balon'."""
        x, y = balon["d"]
        return {"x": round(self._rel(x), 1), "y": y}
