"""
Genera el avatar de "El Profe", el asistente virtual (services/asistente_service.py), con el mismo motor y trazo que
los avatares de jugadores (generar_avatares.py): DT veterano con canas, buzo de entrenamiento y silbato.
Salida: static/img/profe.svg (se sirve desde la app; no va al bucket). Determinístico.

    python generar_avatar_profe.py
"""
from generar_avatares import ANCHO_TRAZO, CANAS, CONTORNO, CX, Avatar, _oscurecer

BUZO, VIVO = "#14213d", "#10b981"   # azul noche con los vivos verdes de la marca


class AvatarProfe(Avatar):
    def __init__(self):
        super().__init__(jugador_id=1959, edad=56, region="rio_plata", jersey=(BUZO, VIVO))
        self.pelo, self.peinado, self.entradas = CANAS[1], "corto", True
        self.barba, self.boca = "incipiente", "dientes"

    def _camiseta(self):
        cuerpo = "M60 512C70 448 130 410 200 398L312 398C382 410 442 448 452 512Z"
        sombra = _oscurecer(BUZO, 0.75)
        return "".join([
            f'<clipPath id="cam"><path d="{cuerpo}"/></clipPath>',
            f'<path d="{cuerpo}" fill="{BUZO}"/>',
            f'<path d="M330 398C400 412 446 450 452 512L300 512Z" fill="{sombra}" clip-path="url(#cam)"/>',
            # tres vivos en las mangas y el cierre del buzo
            f'<path d="M140 420C112 444 92 474 82 512M164 412C134 440 112 474 102 512M386 420C412 444 430 474 438 512M362 412C390 440 410 474 418 512" '
            f'fill="none" stroke="{VIVO}" stroke-width="7" clip-path="url(#cam)"/>',
            f'<path d="M256 432L256 512" stroke="#cbd5e1" stroke-width="5"/>',
            # cuello alto del buzo
            f'<path d="M198 396C214 436 298 436 314 396L304 384C290 414 222 414 208 384Z" fill="{VIVO}" stroke="{CONTORNO}" stroke-width="3" stroke-linejoin="round"/>',
            f'<path d="{cuerpo}" fill="none" stroke="{CONTORNO}" stroke-width="{ANCHO_TRAZO}"/>',
            # silbato colgado
            f'<path d="M222 420C230 452 248 470 268 474" fill="none" stroke="#f8fafc" stroke-width="4"/>',
            f'<rect x="262" y="462" width="38" height="22" rx="10" fill="#e5e7eb" stroke="{CONTORNO}" stroke-width="4"/>',
            f'<circle cx="290" cy="473" r="5" fill="{CONTORNO}"/>',
        ])


if __name__ == "__main__":
    with open("static/img/profe.svg", "w", encoding="utf-8") as f:
        f.write(AvatarProfe().svg())
    print("static/img/profe.svg")
