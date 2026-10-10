/* Simulación en Vivo (templates/live_match.html): polling de la transmisión, cancha animada,
   jugadores, momentum, tabla de grupo y panel del Juego en Vivo. Los permisos del usuario llegan
   por window.LIVE_CONFIG (definido en el template antes de cargar este archivo). */
document.addEventListener('DOMContentLoaded', function () {
    const POLL_MS = 3000;
    let pollHandle = null;

    const panelInactivo = document.getElementById('panelInactivo');
    const panelEnVivo = document.getElementById('panelEnVivo');
    const panelFinalizado = document.getElementById('panelFinalizado');
    const mensajeInactivo = document.getElementById('mensajeInactivo');
    const errorSimular = document.getElementById('errorSimular');
    const btnSimular = document.getElementById('btnSimular');
    const btnSimularOtro = document.getElementById('btnSimularOtro');

    const nombreLocal = document.getElementById('nombreLocal');
    const nombreVisitante = document.getElementById('nombreVisitante');
    const marcador = document.getElementById('marcador');
    const minutoActual = document.getElementById('minutoActual');
    const barraTiempo = document.getElementById('barraTiempo');
    const segundosRestantes = document.getElementById('segundosRestantes');
    const badgeEstado = document.getElementById('badgeEstado');
    const listaEventos = document.getElementById('listaEventos');
    const canchaWrapperEl = document.getElementById('canchaWrapper');
    const canchaBalon = document.getElementById('canchaBalon');
    const canchaEtiquetaJugador = document.getElementById('canchaEtiquetaJugador');
    const canchaAviso = document.getElementById('canchaAviso');
    const canchaEtiquetaJugadorEquipo = document.getElementById('canchaEtiquetaJugadorEquipo');
    const canchaEtiquetaJugadorNombre = document.getElementById('canchaEtiquetaJugadorNombre');
    const canchaEtiquetaJugadorTipo = document.getElementById('canchaEtiquetaJugadorTipo');
    const canchaTrazos = document.getElementById('canchaTrazos');
    const canchaHeatmapCanvas = document.getElementById('canchaHeatmapCanvas');
    const canchaJugadoresCapa = document.getElementById('canchaJugadores');
    const canchaLeyenda = document.getElementById('canchaLeyenda');
    const canchaEtiquetaLocal = document.getElementById('canchaEtiquetaLocal');
    const canchaEtiquetaVisitante = document.getElementById('canchaEtiquetaVisitante');
    const btnCanchaModoVivo = document.getElementById('btnCanchaModoVivo');
    const btnCanchaModoCalor = document.getElementById('btnCanchaModoCalor');
    const toggleMarcadorCancha = document.getElementById('toggleMarcadorCancha');
    const canchaMarcadorAgua = document.getElementById('canchaMarcadorAgua');

    const infoPartidoGrupo = document.getElementById('infoPartidoGrupo');
    const infoPartidoEstadio = document.getElementById('infoPartidoEstadio');
    const infoPartidoFecha = document.getElementById('infoPartidoFecha');
    const infoPartidoAforo = document.getElementById('infoPartidoAforo');

    const panelTablaGrupo = document.getElementById('panelTablaGrupo');
    const tablaGrupoLetra = document.getElementById('tablaGrupoLetra');
    const tablaGrupoBody = document.getElementById('tablaGrupoBody');

    const momentumLeyendaLocal = document.getElementById('momentumLeyendaLocal');
    const momentumLeyendaVisitante = document.getElementById('momentumLeyendaVisitante');
    const golesTarjetasNombreLocal = document.getElementById('golesTarjetasNombreLocal');
    const golesTarjetasNombreVisitante = document.getElementById('golesTarjetasNombreVisitante');
    const golesTarjetasLocal = document.getElementById('golesTarjetasLocal');
    const golesTarjetasVisitante = document.getElementById('golesTarjetasVisitante');

    const onceNombreLocal = document.getElementById('onceNombreLocal');
    const onceNombreVisitante = document.getElementById('onceNombreVisitante');
    const onceMomentumLocal = document.getElementById('onceMomentumLocal');
    const onceMomentumVisitante = document.getElementById('onceMomentumVisitante');
    const onceListaLocal = document.getElementById('onceListaLocal');
    const onceListaVisitante = document.getElementById('onceListaVisitante');

    // Reproducción automática: encadena "Simular siguiente partido" solo, con una pausa entre
    // partido y partido para poder leer el resultado -- el toggle se puede prender/apagar en
    // cualquier momento, y tiene efecto inmediato durante esa pausa (la cancela si se apaga a
    // mitad de la cuenta regresiva, o arranca una si se prende mientras ya se está esperando).
    // La preferencia se guarda en localStorage (misma clave que templates/base.html) para que
    // el encadenado siga funcionando -- vía el badge flotante -- aunque el usuario se salga de
    // esta página, y para que el toggle recuerde su estado real al volver acá.
    const AUTOPLAY_STORAGE_KEY = 'futbolsim_autoplay_live';
    const AUTO_PLAY_DELAY_MS = 10000;
    const toggleAutoPlay = document.getElementById('toggleAutoPlay');
    const autoPlayEstado = document.getElementById('autoPlayEstado');
    let autoPlayTimeoutId = null;
    let autoPlayIntervalId = null;

    function leerAutoPlayGuardado() {
        try {
            return localStorage.getItem(AUTOPLAY_STORAGE_KEY) === '1';
        } catch (e) {
            return false;
        }
    }

    function guardarAutoPlay(activo) {
        try {
            if (activo) localStorage.setItem(AUTOPLAY_STORAGE_KEY, '1');
            else localStorage.removeItem(AUTOPLAY_STORAGE_KEY);
        } catch (e) {
            // localStorage no disponible (modo privado, etc.) -- la preferencia no persiste
            // entre páginas/recargas, pero la reproducción automática sigue andando acá.
        }
    }

    // Solo quien puede simular partidos tiene reproducción automática (ver base.html)
    let autoPlayActivo = window.LIVE_CONFIG.puedeSimular && leerAutoPlayGuardado();
    if (toggleAutoPlay) toggleAutoPlay.checked = autoPlayActivo;

    // Con la reproducción automática prendida, "Simular siguiente partido" es redundante (se
    // dispara solo) -- se oculta en vez de dejarlo ahí sin uso.
    function actualizarVisibilidadBotonSimular() {
        if (btnSimular) btnSimular.classList.toggle('d-none', autoPlayActivo);
        if (btnSimularOtro) btnSimularOtro.classList.toggle('d-none', autoPlayActivo);
    }
    actualizarVisibilidadBotonSimular();

    function cancelarAutoPlayProgramado() {
        if (autoPlayTimeoutId) { clearTimeout(autoPlayTimeoutId); autoPlayTimeoutId = null; }
        if (autoPlayIntervalId) { clearInterval(autoPlayIntervalId); autoPlayIntervalId = null; }
        if (autoPlayEstado) autoPlayEstado.classList.add('d-none');
    }

    function programarAutoPlay(boton) {
        if (!autoPlayActivo || autoPlayTimeoutId || !autoPlayEstado) return;
        let restante = AUTO_PLAY_DELAY_MS / 1000;
        const actualizarTexto = () => {
            autoPlayEstado.textContent = `🔁 Reproducción automática: el próximo partido arranca en ${restante}s...`;
        };
        actualizarTexto();
        autoPlayEstado.classList.remove('d-none');
        autoPlayIntervalId = setInterval(() => {
            restante -= 1;
            if (restante > 0) actualizarTexto();
        }, 1000);
        autoPlayTimeoutId = setTimeout(() => {
            cancelarAutoPlayProgramado();
            if (autoPlayActivo) simularSiguiente(boton);
        }, AUTO_PLAY_DELAY_MS);
    }

    function detenerPolling() {
        if (pollHandle) {
            clearInterval(pollHandle);
            pollHandle = null;
        }
    }

    function quitarPanelCargando() {
        const cargando = document.getElementById('panelCargando');
        if (cargando) cargando.remove();
    }

    function mostrarInactivo(mensaje) {
        quitarPanelCargando();
        detenerPolling();
        panelEnVivo.classList.add('d-none');
        panelInactivo.classList.remove('d-none');
        mensajeInactivo.textContent = mensaje || 'No hay ningún partido en transmisión en este momento.';
        if (btnSimular) programarAutoPlay(btnSimular);
        mostrarJuegoEnVivoInactivo();
        // Sin permiso para simular no hay botón: se sigue consultando (más espaciado) para que
        // la transmisión aparezca sola cuando un administrador arranque el próximo partido.
        if (!btnSimular) programarReconsultaInactivo();
    }

    function badgeMinuto(evento) {
        if (evento.minuto == 120 && evento.tipo.includes('PENAL')) return '<span class="badge bg-danger rounded-pill me-3 fs-6">PEN</span>';
        if (evento.tipo.includes('VAR')) return `<span class="badge bg-dark text-accent border rounded-pill me-3 fs-6">'${evento.minuto}</span>`;
        if (evento.minuto > 90) return `<span class="badge bg-warning text-dark rounded-pill me-3 fs-6">'${evento.minuto}</span>`;
        return `<span class="badge bg-primary rounded-pill me-3 fs-6">'${evento.minuto}</span>`;
    }

    // Escapa texto libre antes de insertarlo en innerHTML (defensa en profundidad: la
    // descripción viene de plantillas fijas server-side, pero se escapa igual antes de envolver
    // los nombres en <strong>, mismo criterio que resaltar_jugadores_en_descripcion en
    // services/juegos_service.py).
    function escaparHtml(texto) {
        const div = document.createElement('div');
        div.textContent = texto;
        return div.innerHTML;
    }

    function resaltarJugadores(descripcion, jugadores) {
        let texto = escaparHtml(descripcion || '');
        (jugadores || []).forEach(nombre => {
            if (!nombre) return;
            const nombreEscapado = escaparHtml(nombre);
            texto = texto.split(nombreEscapado).join(`<strong class="evento-jugador">${nombreEscapado}</strong>`);
        });
        return texto;
    }

    function renderEventos(eventos) {
        if (!eventos || eventos.length === 0) {
            listaEventos.innerHTML = '<div class="text-muted text-center py-3">Esperando el primer evento del partido...</div>';
            return;
        }
        // Del más reciente al más antiguo, igual que una transmisión real
        const items = eventos.slice().reverse().map(evento => `
            <div class="list-group-item bg-dark text-white d-flex align-items-start py-3 border-bottom border-secondary">
                ${badgeMinuto(evento)}
                <div>
                    <strong>${evento.tipo}</strong>
                    <span class="text-muted">(${evento.equipo})</span>:
                    <span>${resaltarJugadores(evento.descripcion, evento.jugadores)}</span>
                </div>
            </div>
        `).join('');
        listaEventos.innerHTML = items;
    }

    // Cancha en Vivo: posiciona el balón (<div>#canchaBalon, left/top en %) según
    // evento.posicion_balon.x/y del último evento revelado -- x ya viene 0-100 (mapea directo
    // a left%), y viene 0-68 (se reescala a top%). La transición CSS (left/top 0.6s) hace que
    // el desplazamiento entre acciones consecutivas se vea fluido en vez de saltar. Además se
    // dibuja un trazo (<line> dentro del SVG, en unidades de su viewBox 105x68) entre la
    // posición anterior y la nueva, animado con stroke-dasharray/dashoffset en el mismo lapso.
    let canchaUltimoEventoKey = null;
    let canchaPosicionActual = { x: 50, y: 34 }; // arranca en el centro de la cancha (saque inicial)
    let canchaNombreLocal = null;
    let canchaEtiquetaJugadorTimeout = null;

    // Mapa nombre de jugador -> sigla de posición (POR/LD/LI/MC/ED/etc.), para la etiqueta
    // flotante de la Cancha en Vivo y las cards de "Jugadores en Cancha". Se pide UNA sola vez
    // por partido (no en cada poll de 3s, ver renderEnVivo) porque la posición de un jugador no
    // cambia durante el juego. 'canchaTitularesLocal/Visitante' son el 11 inicial tal cual lo
    // arma el backend (services/simular_service.py::seleccionar_plantilla_titular, orden
    // POR->DEF->MED->DEL) -- el estado de "quién sigue en cancha ahora" se deriva de esto más
    // las sustituciones/expulsiones ya reveladas, ver actualizarOnceEnCancha().
    let canchaPlantillas = {};
    let canchaPlantillasMatchId = null;
    let canchaTitularesLocal = [];
    let canchaTitularesVisitante = [];
    let canchaDorsales = {};
    let canchaLineasLocal = [];
    let canchaLineasVisitante = [];

    async function actualizarPlantillasSiCorresponde(matchId) {
        if (!matchId || matchId === canchaPlantillasMatchId) return;
        try {
            const resp = await fetch('/matches/live/plantillas');
            if (!resp.ok) return;
            const data = await resp.json();
            canchaPlantillas = data.jugadores || {};
            canchaTitularesLocal = data.titulares_local || [];
            canchaTitularesVisitante = data.titulares_visitante || [];
            canchaDorsales = data.dorsales || {};
            canchaLineasLocal = data.lineas_local || [];
            canchaLineasVisitante = data.lineas_visitante || [];
            canchaPlantillasMatchId = matchId;
        } catch (e) {
            // Sin conexión momentánea o partido recién terminado -- la etiqueta simplemente
            // sigue mostrando solo el nombre hasta el próximo poll, sin romper nada.
        }
    }

    // Tipos de evento que representan la resolución de un disparo (a favor o en contra) --
    // reciben el trazo "fuerte" (más grosor/resplandor); todo lo demás (pases, transición,
    // presión, preparación, faltas, sustituciones) es un trazo fino de "circulación de balón".
    const CANCHA_TIPOS_DISPARO = new Set([
        '🎯 DISPARO DESVIADO', '🧤 ATAJADA ESPECTACULAR', '🖐️ DESVÍO A CÓRNER',
        '🧱 TIRO LIBRE BLOQUEADO', '🛡️ CÓRNER DESPEJADO'
    ]);

    function esCanchaTipoDisparo(tipo) {
        return (tipo || '').startsWith('⚽') || CANCHA_TIPOS_DISPARO.has(tipo);
    }

    // 'posicion_balon.x' del backend es simétrico: siempre representa qué tan metido está en
    // SU PROPIO ataque quien tiene la pelota (0=su defensa, 100=su ataque), sin importar de qué
    // equipo se trate -- no hay un "lado" físico fijo de cancha en el motor de simulación. Acá
    // se espeja para el equipo visitante (xVisual = 100 - x) para que, en la vista, el local
    // SIEMPRE ataque hacia la derecha y el visitante SIEMPRE hacia la izquierda durante todo el
    // partido, como en una transmisión real -- sin tocar el backend.
    function esCanchaEquipoLocal(equipo) {
        return equipo === canchaNombreLocal;
    }

    // En estos tipos de evento, 'evento.equipo' es el equipo que DEFIENDE en esa jugada (a
    // quien se le atribuye la falta/tarjeta/robo/despeje), pero 'posicion_balon' se calculó
    // relativo a la zona del equipo que ATACABA en ese momento (ver services/simular_service.py,
    // 'zona_balon' siempre es relativo a quien tiene el balón) -- así que para saber a qué lado
    // corresponde la coordenada hay que mirar al equipo CONTRARIO al que figura en 'equipo'.
    // '🧤 ATAJADA ESPECTACULAR' / '🖐️ DESVÍO A CÓRNER' / '❌ PENAL FALLADO' entraron acá porque
    // el backend ahora atribuye esos eventos al equipo del propio arquero (antes al del
    // rematador, un bug -- ver services/simular_service.py), pero la posición sigue calculada
    // en el frame del equipo atacante, mismo caso que el resto de este set.
    const CANCHA_TIPOS_EQUIPO_DEFENSOR = new Set([
        '🛡️ CÓRNER DESPEJADO', '🔥 PRESIÓN DEFENSIVA', '🖥️ VAR - TARJETA REVISADA',
        '🟨 TARJETA AMARILLA', '🛑 FALTA', '⚠️ ERROR DE PORTERÍA', '🧠 ROBO DE BALÓN',
        '⚡ EN TRANSICIÓN', '🟥 TARJETA ROJA', '🟨🟥 DOBLE AMARILLA',
        '🧤 ATAJADA ESPECTACULAR', '🖐️ DESVÍO A CÓRNER', '❌ PENAL FALLADO'
    ]);

    // Determina si el equipo que efectivamente tenía/disputaba el balón en este evento (no
    // necesariamente el que figura en 'evento.equipo', ver arriba) es el local -- este es el
    // criterio correcto tanto para espejar la posición como para elegir el color del trazo.
    function esCanchaAtacanteLocal(evento) {
        const esEquipoLocal = esCanchaEquipoLocal(evento.equipo);
        return CANCHA_TIPOS_EQUIPO_DEFENSOR.has(evento.tipo) ? !esEquipoLocal : esEquipoLocal;
    }

    function canchaPosicionVisual(evento) {
        const { x, y } = evento.posicion_balon;
        return { x: esCanchaAtacanteLocal(evento) ? x : (100 - x), y };
    }

    // x llega 0-100 (mapea directo a left% del balón) pero el viewBox del SVG es 105 de ancho
    // (dimensiones reales de cancha en metros) -- se reescala solo para el trazo. y ya es 0-68,
    // coincide 1 a 1 con el alto del viewBox.
    function canchaXaSvg(x) { return (x / 100) * 105; }

    // ---------------------------------------------------------------------------------------
    // Jugadores en la Cancha en Vivo: 22 fichas (círculo con el dorsal) que se reacomodan con
    // cada evento revelado. No hay posiciones reales de jugadores en el motor (trabaja por zonas),
    // así que es una coreografía derivada de los datos que sí existen: la formación de cada
    // equipo (lineas_* de /matches/live/plantillas, alineadas con titulares_*), la zona y la
    // posición del balón del último evento, y sus protagonistas (jugadores[0], jugadores[1]).
    // Todo se calcula en el "marco de ataque" de cada equipo (x 0-100 hacia el arco rival) y
    // después se espeja el visitante, igual que el balón (el local siempre ataca a la derecha).
    // ---------------------------------------------------------------------------------------
    const CANCHA_X_POR_LINEA = { 1: 5, 2: 21, 3: 40, 4: 58 };
    // Cuánto empuja hacia adelante el equipo con la pelota según la zona del balón (y cuánto
    // retrocede el rival: CANCHA_FACTOR_REPLIEGUE de eso)
    const CANCHA_EMPUJE_POR_ZONA = { defensiva: 0, mediocampo: 10, ataque: 20 };
    const CANCHA_FACTOR_REPLIEGUE = 0.6;
    const CANCHA_TIPOS_EXPULSION = new Set(['🟥 TARJETA ROJA', '🟨🟥 DOBLE AMARILLA']);
    const CANCHA_TIPO_SUSTITUCION = '🔄 SUSTITUCIÓN';
    // Decisiones del árbitro / VAR: igual que la sustitución, se muestran en una ventana y no como jugada
    const CANCHA_TIPOS_ARBITRO = new Set([
        '👉 SILBATO INICIAL', '🚩 FINAL DEL PRIMER TIEMPO', '⏱️ TIEMPO EXTRA', '🥅 TANDA DE PENALTIS', '🏁 PITIDO FINAL'
    ]);
    function esEventoVar(ev) { return (ev.tipo || '').startsWith('🖥️ VAR'); }
    function esEventoAviso(ev) {
        return ev.tipo === CANCHA_TIPO_SUSTITUCION || CANCHA_TIPOS_ARBITRO.has(ev.tipo) || esEventoVar(ev);
    }
    // Margen para que ninguna ficha quede cortada contra el borde de la cancha (radio ~1.6 u.)
    const CANCHA_X_MIN = 2.5, CANCHA_X_MAX = 97.5, CANCHA_Y_MIN = 2.5, CANCHA_Y_MAX = 65.5;

    const canchaFichas = new Map();        // clave "lado|nombre" -> elemento
    let canchaJugadoresUltimaClave = null;
    let canchaJugadoresUltimaJugadaClave = null; // última jugada (no aviso) a la que se acomodaron las fichas

    // Quién está en cancha y en qué "slot" de la formación (índice del titular al que ocupa):
    // arranca del 11 inicial y reproduce TODOS los eventos revelados -- el que entra hereda el
    // slot del que sale (mismo criterio que el motor con 'linea_saliente'), el expulsado se va
    // sin reemplazo. Se recalcula desde cero cada vez, igual que calcularEstadoJugadoresEnCancha.
    function calcularAlineacionEnCancha(data) {
        const alineacion = { local: new Map(), visitante: new Map() };
        canchaTitularesLocal.forEach((nombre, i) => alineacion.local.set(nombre, i));
        canchaTitularesVisitante.forEach((nombre, i) => alineacion.visitante.set(nombre, i));

        (data.eventos || []).forEach(ev => {
            const lado = ev.equipo === data.local ? 'local' : (ev.equipo === data.visitante ? 'visitante' : null);
            const jugadores = ev.jugadores || [];
            if (!lado) return;
            const enCancha = alineacion[lado];
            if (ev.tipo === CANCHA_TIPO_SUSTITUCION && jugadores.length >= 2 && enCancha.has(jugadores[1])) {
                const slot = enCancha.get(jugadores[1]);
                enCancha.delete(jugadores[1]);
                enCancha.set(jugadores[0], slot);
            } else if (CANCHA_TIPOS_EXPULSION.has(ev.tipo) && jugadores.length >= 1) {
                enCancha.delete(jugadores[0]);
            }
        });
        return alineacion;
    }

    // Posición "de pizarra" de cada slot de la formación, en el marco de ataque del equipo: cada
    // línea a su profundidad (CANCHA_X_POR_LINEA), repartida pareja a lo ancho; en líneas de 4+
    // los de las puntas (laterales / carrileros / extremos) van un poco más adelantados.
    function posicionesBaseFormacion(lineas) {
        const porLinea = {};
        lineas.forEach((linea, slot) => { (porLinea[linea] = porLinea[linea] || []).push(slot); });
        const base = [];
        Object.entries(porLinea).forEach(([linea, slots]) => {
            const n = slots.length;
            slots.forEach((slot, k) => {
                const esPunta = n >= 4 && (k === 0 || k === n - 1);
                base[slot] = {
                    x: CANCHA_X_POR_LINEA[linea] + (esPunta ? 3 : 0),
                    y: (68 * (k + 1)) / (n + 1),
                    linea: Number(linea)
                };
            });
        });
        return base;
    }

    function limitar(valor, min, max) { return Math.max(min, Math.min(max, valor)); }

    // Calcula dónde va cada ficha para un evento dado. Devuelve [{ clave, lado, nombre, slot,
    // x, y, portero, rol }] en coordenadas VISUALES (x 0-100 izquierda->derecha, y 0-68).
    function calcularFichasCancha(data, evento, alineacion) {
        const pos = canchaPosicionVisual(evento);
        const atacaLocal = esCanchaAtacanteLocal(evento);
        const empuje = CANCHA_EMPUJE_POR_ZONA[evento.zona] ?? CANCHA_EMPUJE_POR_ZONA.mediocampo;
        // Una sustitución no es una jugada: el que entra aparece en su posición, no corre al balón
        const protagonistas = evento.tipo === CANCHA_TIPO_SUSTITUCION ? [] : (evento.jugadores || []);
        const fichas = [];

        [['local', canchaLineasLocal], ['visitante', canchaLineasVisitante]].forEach(([lado, lineas]) => {
            const base = posicionesBaseFormacion(lineas);
            const esLocal = lado === 'local';
            const tieneLaPelota = esLocal === atacaLocal;
            const desplazamiento = tieneLaPelota ? empuje : -empuje * CANCHA_FACTOR_REPLIEGUE;

            alineacion[lado].forEach((slot, nombre) => {
                const b = base[slot];
                if (!b) return;
                const portero = b.linea === 1;
                // El arquero casi no sale de su área; el resto del equipo se mueve en bloque y se
                // "cierra" un poco hacia el lado de la cancha donde está la pelota.
                let x = b.x + desplazamiento * (portero ? 0.15 : 1);
                let y = portero ? b.y : b.y + (pos.y - b.y) * 0.15;
                // Pequeño movimiento aleatorio para que no se vean estáticos entre eventos
                if (!portero) { x += (Math.random() - 0.5) * 3; y += (Math.random() - 0.5) * 3; }
                x = limitar(x, 2, 97);
                y = limitar(y, 3, 65);
                const xVisual = esLocal ? x : 100 - x;

                let rol = null;
                let xFinal = xVisual, yFinal = y;
                if (nombre === protagonistas[0]) {
                    // El protagonista va a la pelota, un paso detrás de ella (mirando al arco
                    // rival) para que el balón quede "en sus pies" sin taparle el dorsal
                    rol = 'activo';
                    xFinal = pos.x + (esLocal ? -2.5 : 2.5); yFinal = pos.y;
                } else if (protagonistas.length > 1 && protagonistas.slice(1).includes(nombre)) {
                    // Quien disputa / asiste se acerca a unos metros de la jugada
                    rol = 'secundario';
                    xFinal = pos.x + (esLocal ? -4 : 4);
                    yFinal = pos.y + (y < pos.y ? -3 : 3);
                }
                fichas.push({
                    clave: `${lado}|${nombre}`, lado, nombre, slot, portero, rol, linea: b.linea,
                    x: limitar(xFinal, CANCHA_X_MIN, CANCHA_X_MAX), y: limitar(yFinal, CANCHA_Y_MIN, CANCHA_Y_MAX)
                });
            });
        });
        separarFichas(fichas);
        if (evento.tipo === '🚩 FUERA DE LUGAR') {
            // Separar puede volver a adelantar a alguien: se repite una vez y se vuelve a fijar la línea
            acomodarFueraDeLugar(fichas, atacaLocal);
            separarFichas(fichas);
            acomodarFueraDeLugar(fichas, atacaLocal);
        }
        return fichas;
    }

    // Fuera de lugar: el infractor (protagonista, sobre la pelota) tiene que quedar adelantado.
    // La línea defensiva rival se arma unos metros por detrás de él y nadie más -- compañeros y
    // rivales, salvo el arquero rival que sigue en su arco -- queda más adelante que esa línea.
    // Todo en x visual: 'adelante' es hacia el arco que ataca el equipo del infractor.
    const CANCHA_DISTANCIA_LINEA_FUERA_DE_LUGAR = 4;
    function acomodarFueraDeLugar(fichas, atacaLocal) {
        const infractor = fichas.find(f => f.rol === 'activo');
        if (!infractor) return;
        const sentido = atacaLocal ? 1 : -1;
        const linea = infractor.x - sentido * CANCHA_DISTANCIA_LINEA_FUERA_DE_LUGAR;
        const ladoAtacante = atacaLocal ? 'local' : 'visitante';
        fichas.forEach(f => {
            if (f === infractor || f.portero) return;
            const esDefensaRival = f.lado !== ladoAtacante && f.linea === 2;
            if (esDefensaRival) {
                // Línea defensiva casi recta, apenas desalineada para que se vea natural
                f.x = linea - sentido * (f.xLineaJitter ??= Math.random() * 1.2);
            } else if ((f.x - linea) * sentido > -1.5) {
                // Quien estaba a la altura de la línea o más adelante, vuelve atrás de ella
                f.x = linea - sentido * (1.5 + (f.xAtrasJitter ??= Math.random() * 3));
            }
            f.x = limitar(f.x, CANCHA_X_MIN, CANCHA_X_MAX);
        });
    }

    // Separa las fichas que quedaron encimadas (típico: un delantero y el defensor que lo marca),
    // para que se lea el dorsal de cada una. Unas pocas pasadas de "empujar" cada par que esté a
    // menos de CANCHA_SEPARACION_MINIMA; el protagonista (sobre la pelota) no se mueve, empuja el
    // otro. x viene en % del ancho (105 m) e y en metros (68), de ahí el 1.05 para medir parejo.
    const CANCHA_SEPARACION_MINIMA = 3.6;
    function separarFichas(fichas) {
        for (let pasada = 0; pasada < 8; pasada++) {
            let huboAjuste = false;
            for (let i = 0; i < fichas.length; i++) {
                for (let j = i + 1; j < fichas.length; j++) {
                    const a = fichas[i], b = fichas[j];
                    let dx = (b.x - a.x) * 1.05, dy = b.y - a.y;
                    let d = Math.hypot(dx, dy);
                    if (d >= CANCHA_SEPARACION_MINIMA) continue;
                    if (d < 0.01) { dx = 0.01; dy = (i % 2 ? 1 : -1); d = Math.hypot(dx, dy); }
                    const faltante = CANCHA_SEPARACION_MINIMA - d;
                    const ux = dx / d, uy = dy / d;
                    const fijaA = a.rol === 'activo', fijaB = b.rol === 'activo';
                    const partA = fijaA ? 0 : (fijaB ? 1 : 0.5);
                    const partB = 1 - partA;
                    a.x -= (ux * faltante * partA) / 1.05; a.y -= uy * faltante * partA;
                    b.x += (ux * faltante * partB) / 1.05; b.y += uy * faltante * partB;
                    huboAjuste = true;
                }
            }
            fichas.forEach(f => { f.x = limitar(f.x, CANCHA_X_MIN, CANCHA_X_MAX); f.y = limitar(f.y, CANCHA_Y_MIN, CANCHA_Y_MAX); });
            if (!huboAjuste) break;
        }
    }

    function claseAnimacionFicha(tipo, rol) {
        if (rol !== 'activo') return null;
        if (tipo.startsWith('⚽')) return 'cancha-jugador--gol';
        if (tipo === '🟨 TARJETA AMARILLA') return 'cancha-jugador--amarilla';
        return null;
    }

    function renderJugadoresCancha(data) {
        if (!canchaJugadoresCapa || !canchaLineasLocal.length || !canchaLineasVisitante.length) return;
        const eventos = data.eventos || [];
        // 'evento' = el último revelado; 'jugada' = la última que no es aviso (sustitución /
        // árbitro / VAR), que es a la que se acomodan las fichas, igual que el balón
        let evento = null, jugada = null;
        for (let i = eventos.length - 1; i >= 0; i--) {
            if (!eventos[i].posicion_balon) continue;
            if (!evento) evento = eventos[i];
            if (!esEventoAviso(eventos[i])) { jugada = eventos[i]; break; }
        }
        if (!evento) return;

        // Mismo criterio que renderCancha: solo se reacomoda cuando hay un evento nuevo, no en
        // cada poll de 3s (si no, el movimiento aleatorio haría "temblar" a las fichas).
        const clave = `${data.match_id}-${evento.segundos_acumulados ?? evento.minuto}-${evento.tipo}-${eventos.length}`;
        if (clave === canchaJugadoresUltimaClave) return;
        canchaJugadoresUltimaClave = clave;

        // Si lo nuevo es solo un aviso (la jugada ya estaba dibujada), nadie se mueve; en una
        // sustitución, además, el que entra aparece justo donde estaba el que sale. Si en el mismo
        // poll llegó una jugada nueva y después un aviso, las fichas sí se acomodan a esa jugada.
        const claveJugada = jugada ? `${data.match_id}-${jugada.segundos_acumulados ?? jugada.minuto}-${jugada.tipo}` : null;
        const esAviso = esEventoAviso(evento) && (!jugada || claveJugada === canchaJugadoresUltimaJugadaClave);
        canchaJugadoresUltimaJugadaClave = claveJugada;
        const eventoBase = esAviso ? evento : jugada;
        const esSustitucion = esAviso && evento.tipo === CANCHA_TIPO_SUSTITUCION;
        const [entraSust, saleSust] = esSustitucion ? (evento.jugadores || []) : [];

        const alineacion = calcularAlineacionEnCancha(data);
        const fichas = calcularFichasCancha(data, eventoBase, alineacion);
        const vigentes = new Set();

        fichas.forEach(f => {
            vigentes.add(f.clave);
            let el = canchaFichas.get(f.clave);
            const esNueva = !el;
            if (esNueva) {
                el = document.createElement('div');
                // Entra invisible en su lugar y aparece (sustituto o primer render del partido)
                el.className = `cancha-jugador cancha-jugador--${f.lado} cancha-jugador--oculto`;
                const fichaSale = esSustitucion && f.nombre === entraSust ? canchaFichas.get(`${f.lado}|${saleSust}`) : null;
                if (fichaSale) {
                    f.x = parseFloat(fichaSale.style.left);
                    f.y = (parseFloat(fichaSale.style.top) / 100) * 68;
                }
                el.style.left = `${f.x}%`;
                el.style.top = `${(f.y / 68) * 100}%`;
                canchaJugadoresCapa.appendChild(el);
                canchaFichas.set(f.clave, el);
            }
            el.classList.toggle('cancha-jugador--portero', f.portero);
            el.textContent = canchaDorsales[f.nombre] ?? '';
            const posicion = canchaPlantillas[f.nombre] ? ` · ${canchaPlantillas[f.nombre]}` : '';
            el.title = `${f.nombre}${posicion}`;

            el.classList.remove('cancha-jugador--activo', 'cancha-jugador--secundario', 'cancha-jugador--gol', 'cancha-jugador--amarilla');
            void el.offsetWidth; // reinicia la animación si el mismo jugador repite protagonismo
            if (f.rol) el.classList.add(`cancha-jugador--${f.rol}`);
            const animacion = claseAnimacionFicha(eventoBase.tipo, f.rol);
            if (animacion) el.classList.add(animacion);

            const aplicarPosicion = () => {
                el.style.left = `${f.x}%`;
                el.style.top = `${(f.y / 68) * 100}%`;
                el.classList.remove('cancha-jugador--oculto');
            };
            if (esNueva && esSustitucion) setTimeout(aplicarPosicion, 700); // aparece cuando el que sale ya se fue
            else if (esNueva) requestAnimationFrame(() => requestAnimationFrame(aplicarPosicion));
            else if (!esAviso) aplicarPosicion();
        });

        // Los que ya no están en cancha (sustituidos o expulsados) se desvanecen y salen; si la
        // salida es justo por la roja de este evento, primero parpadean en rojo.
        canchaFichas.forEach((el, claveFicha) => {
            if (vigentes.has(claveFicha)) return;
            canchaFichas.delete(claveFicha);
            const nombre = claveFicha.slice(claveFicha.indexOf('|') + 1);
            const esExpulsionAhora = CANCHA_TIPOS_EXPULSION.has(eventoBase.tipo) && (eventoBase.jugadores || [])[0] === nombre;
            const retraso = esExpulsionAhora ? 1200 : 0;
            if (esExpulsionAhora) el.classList.add('cancha-jugador--roja');
            setTimeout(() => {
                el.classList.add('cancha-jugador--oculto');
                setTimeout(() => el.remove(), 500);
            }, retraso);
        });
    }

    // Partido nuevo (otro match_id): se limpian las fichas del anterior para no mezclar planteles
    function reiniciarJugadoresCanchaSiCambioPartido(matchId) {
        if (canchaFichas.size && canchaJugadoresCapa && canchaJugadoresCapa.dataset.matchId !== String(matchId)) {
            canchaFichas.clear();
            canchaJugadoresCapa.innerHTML = '';
            canchaJugadoresUltimaClave = null;
            canchaJugadoresUltimaJugadaClave = null;
        }
        if (canchaJugadoresCapa) canchaJugadoresCapa.dataset.matchId = String(matchId);
    }

    // Ubica la etiqueta flotante del jugador siguiendo al balón, pero sin dejar que se corte
    // contra los bordes de la cancha cuando la jugada ocurre cerca de una línea de banda/fondo.
    // Mide el ancho/alto real de la etiqueta (getBoundingClientRect funciona igual con
    // opacity:0) contra el tamaño real del wrapper -- que cambia con el viewport, así que un
    // margen fijo en % no alcanza en pantallas angostas -- y desplaza el punto de anclaje
    // (transform translate) en vez de mover el balón, que debe quedar en su posición exacta.
    function posicionarEtiquetaJugador(leftPct, topPct) {
        if (!canchaEtiquetaJugador) return;
        canchaEtiquetaJugador.style.left = `${leftPct}%`;
        canchaEtiquetaJugador.style.top = `${topPct}%`;

        let anchorX = -50; // % -- por defecto centrada sobre el balón
        let anchorY = -145; // % -- por defecto flotando por encima del balón

        const wrapperRect = canchaWrapperEl ? canchaWrapperEl.getBoundingClientRect() : null;
        const labelRect = canchaEtiquetaJugador.getBoundingClientRect();

        if (wrapperRect && wrapperRect.width && labelRect.width) {
            const margen = 6; // px de aire respecto al borde de la cancha
            const xPx = (leftPct / 100) * wrapperRect.width;
            const mitadAncho = labelRect.width / 2;

            if (xPx - mitadAncho < margen) {
                anchorX = Math.min(0, -((xPx - margen) / labelRect.width) * 100);
            } else if (xPx + mitadAncho > wrapperRect.width - margen) {
                const sobra = (xPx + mitadAncho) - (wrapperRect.width - margen);
                anchorX = Math.max(-100, -50 - (sobra / labelRect.width) * 100);
            }

            const yPx = (topPct / 100) * wrapperRect.height;
            if (yPx - labelRect.height * 1.45 < margen) {
                anchorY = 30; // no entra por arriba: la mostramos debajo del balón
            }
        }

        canchaEtiquetaJugador.style.transform = `translate(${anchorX}%, ${anchorY}%)`;
    }

    function dibujarTrazoBalon(desde, hasta, tipo, esLocal) {
        if (!canchaTrazos) return;
        const x1 = canchaXaSvg(desde.x), y1 = desde.y;
        const x2 = canchaXaSvg(hasta.x), y2 = hasta.y;
        const largo = Math.hypot(x2 - x1, y2 - y1) || 0.01;

        const linea = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        linea.setAttribute('x1', x1.toFixed(1));
        linea.setAttribute('y1', y1.toFixed(1));
        linea.setAttribute('x2', x2.toFixed(1));
        linea.setAttribute('y2', y2.toFixed(1));
        const claseColor = esLocal ? 'cancha-trazo--local' : 'cancha-trazo--visitante';
        const claseFuerza = esCanchaTipoDisparo(tipo) ? ' cancha-trazo--fuerte' : '';
        linea.setAttribute('class', `cancha-trazo ${claseColor}${claseFuerza}`);
        linea.style.strokeDasharray = `${largo}`;
        linea.style.strokeDashoffset = `${largo}`;
        canchaTrazos.appendChild(linea);

        // Fuerza reflow para que el navegador registre el estado inicial (trazo "invisible",
        // dashoffset == largo) antes de animar a 0 -- mismo truco que el reinicio del pulso del
        // balón más abajo, si no el cambio a dashoffset:0 se aplicaría de una sin transición.
        void linea.getBoundingClientRect();
        linea.style.transition = 'stroke-dashoffset 0.6s linear, opacity 0.4s ease 0.6s';
        linea.style.strokeDashoffset = '0';

        // Se retira del SVG un instante después de terminar de dibujarse, para no acumular
        // trazos de jugadas viejas superpuestos indefinidamente.
        setTimeout(() => {
            linea.style.opacity = '0';
            setTimeout(() => linea.remove(), 450);
        }, 700);
    }

    // Mapa de Calor: acumula TODOS los eventos con posicion_balon revelados hasta el momento
    // (no solo el último, a diferencia del modo Vivo) en un canvas transparente superpuesto al
    // SVG, para mostrar dónde se concentró la disputa del balón durante el partido.
    let canchaModo = 'vivo'; // 'vivo' | 'calor'
    let canchaUltimosEventos = [];

    // Lookup table de color térmico (verde -> amarillo -> rojo), armada una sola vez sobre un
    // canvas auxiliar de 1x256px -- el índice (0-255) representa la intensidad acumulada de un
    // píxel del heatmap, igual que hace heatmap.js internamente.
    const CANCHA_GRADIENTE_TERMICO = (() => {
        const lienzoGradiente = document.createElement('canvas');
        lienzoGradiente.width = 1;
        lienzoGradiente.height = 256;
        const gctx = lienzoGradiente.getContext('2d');
        const grad = gctx.createLinearGradient(0, 256, 0, 0);
        grad.addColorStop(0.0, 'rgba(16, 60, 20, 0)');
        grad.addColorStop(0.35, 'rgba(16, 185, 129, 0.85)');
        grad.addColorStop(0.65, 'rgba(255, 213, 0, 0.9)');
        grad.addColorStop(1.0, 'rgba(255, 45, 32, 1)');
        gctx.fillStyle = grad;
        gctx.fillRect(0, 0, 1, 256);
        return gctx.getImageData(0, 0, 1, 256).data; // Uint8ClampedArray, RGBA x 256
    })();

    function renderHeatmap(eventos) {
        if (!canchaHeatmapCanvas) return;
        const wrapper = canchaHeatmapCanvas.parentElement;
        const ancho = Math.max(1, wrapper.clientWidth || 640);
        const alto = Math.max(1, wrapper.clientHeight || Math.round(ancho * 68 / 105));
        if (canchaHeatmapCanvas.width !== ancho) canchaHeatmapCanvas.width = ancho;
        if (canchaHeatmapCanvas.height !== alto) canchaHeatmapCanvas.height = alto;

        const ctx = canchaHeatmapCanvas.getContext('2d');
        ctx.clearRect(0, 0, ancho, alto);

        // Un aviso (sustitución / árbitro / VAR) no es una jugada: no marca zona de juego
        const puntos = (eventos || []).filter(e => e.posicion_balon && !esEventoAviso(e));
        if (!puntos.length) return;

        // Buffer intermedio en escala de grises: cada evento dibuja un degradado radial suave
        // (centro opaco, borde transparente) con composición normal -- las zonas donde varios
        // puntos se solapan "acumulan opacidad" naturalmente, sin necesitar un compositado
        // especial.
        const buffer = document.createElement('canvas');
        buffer.width = ancho;
        buffer.height = alto;
        const bctx = buffer.getContext('2d');
        const radio = Math.max(ancho, alto) * 0.07;

        puntos.forEach(evento => {
            const { x, y } = canchaPosicionVisual(evento);
            const px = (x / 100) * ancho;
            const py = (y / 68) * alto;
            const rg = bctx.createRadialGradient(px, py, 0, px, py, radio);
            rg.addColorStop(0, 'rgba(0,0,0,0.22)');
            rg.addColorStop(1, 'rgba(0,0,0,0)');
            bctx.fillStyle = rg;
            bctx.beginPath();
            bctx.arc(px, py, radio, 0, Math.PI * 2);
            bctx.fill();
        });

        // Recolorea el buffer: el canal alfa acumulado de cada píxel se usa como índice del
        // gradiente térmico -- así una zona muy transitada (alfa alto) sale roja, una zona
        // apenas tocada (alfa bajo) sale verde.
        const datosImagen = bctx.getImageData(0, 0, ancho, alto);
        const pix = datosImagen.data;
        for (let i = 0; i < pix.length; i += 4) {
            const alfaAcumulado = pix[i + 3];
            if (alfaAcumulado === 0) continue;
            const idx = Math.min(255, alfaAcumulado) * 4;
            pix[i] = CANCHA_GRADIENTE_TERMICO[idx];
            pix[i + 1] = CANCHA_GRADIENTE_TERMICO[idx + 1];
            pix[i + 2] = CANCHA_GRADIENTE_TERMICO[idx + 2];
            pix[i + 3] = Math.min(255, alfaAcumulado * 1.6); // más contraste que la opacidad cruda
        }
        ctx.putImageData(datosImagen, 0, 0);
    }

    function actualizarModoCancha() {
        const esCalor = canchaModo === 'calor';
        if (canchaBalon) canchaBalon.classList.toggle('d-none', esCalor);
        if (canchaTrazos) canchaTrazos.classList.toggle('d-none', esCalor);
        if (canchaEtiquetaJugador) canchaEtiquetaJugador.classList.toggle('d-none', esCalor);
        if (canchaJugadoresCapa) canchaJugadoresCapa.classList.toggle('d-none', esCalor);
        if (canchaHeatmapCanvas) canchaHeatmapCanvas.classList.toggle('d-none', !esCalor);
        if (btnCanchaModoVivo) btnCanchaModoVivo.classList.toggle('active', !esCalor);
        if (btnCanchaModoCalor) btnCanchaModoCalor.classList.toggle('active', esCalor);
        if (canchaLeyenda) {
            canchaLeyenda.textContent = esCalor
                ? 'Mapa de calor acumulado de disputas de balón durante el partido'
                : 'Posición aproximada del balón según el último evento revelado';
        }
        if (esCalor) renderHeatmap(canchaUltimosEventos);
    }

    // Marcador en cancha (marca de agua): preferencia por visitante en localStorage, envuelta en
    // try/catch -- si el navegador lo bloquea, el toggle igual funciona, solo no se recuerda.
    const MARCADOR_CANCHA_STORAGE_KEY = 'liveMatchMarcadorEnCancha';
    function leerPreferenciaMarcadorCancha() {
        try { return localStorage.getItem(MARCADOR_CANCHA_STORAGE_KEY) === '1'; } catch (e) { return false; }
    }
    function aplicarMarcadorCancha(activo) {
        if (canchaMarcadorAgua) canchaMarcadorAgua.classList.toggle('d-none', !activo);
    }
    if (toggleMarcadorCancha) {
        toggleMarcadorCancha.checked = leerPreferenciaMarcadorCancha();
        aplicarMarcadorCancha(toggleMarcadorCancha.checked);
        toggleMarcadorCancha.addEventListener('change', () => {
            aplicarMarcadorCancha(toggleMarcadorCancha.checked);
            try { localStorage.setItem(MARCADOR_CANCHA_STORAGE_KEY, toggleMarcadorCancha.checked ? '1' : '0'); } catch (e) { /* sin persistencia */ }
        });
    }

    // Actualiza goles y banderas de la marca de agua; si un número cambia, "late" una vez.
    function renderMarcadorAgua(data) {
        if (!canchaMarcadorAgua) return;
        [['Local', data.goles_local, data.bandera_local], ['Visitante', data.goles_visitante, data.bandera_visitante]].forEach(([lado, goles, bandera]) => {
            const elGoles = document.getElementById(`canchaAguaGoles${lado}`);
            const elBandera = document.getElementById(`canchaAguaBandera${lado}`);
            const texto = String(goles ?? 0);
            if (elGoles.textContent !== texto) {
                const esCambio = elGoles.dataset.matchId === String(data.match_id);
                elGoles.textContent = texto;
                if (esCambio) {
                    elGoles.classList.remove('cancha-marcador-agua__goles--cambio');
                    void elGoles.offsetWidth;
                    elGoles.classList.add('cancha-marcador-agua__goles--cambio');
                }
            }
            elGoles.dataset.matchId = String(data.match_id);
            elBandera.textContent = bandera || '🏳️';
        });
    }

    if (btnCanchaModoVivo) {
        btnCanchaModoVivo.addEventListener('click', () => { canchaModo = 'vivo'; actualizarModoCancha(); });
    }
    if (btnCanchaModoCalor) {
        btnCanchaModoCalor.addEventListener('click', () => { canchaModo = 'calor'; actualizarModoCancha(); });
    }

    // Sustituciones y decisiones del árbitro / VAR: en vez de tratarlas como jugada (mover el balón
    // y la etiqueta), se muestra una ventana sobre la cancha con la info del evento. Si se revelan
    // varias juntas (un mismo poll), se muestran en cola, una detrás de otra.
    const CANCHA_AVISO_DURACION_MS = 3500;
    // Al entrar a un partido ya empezado (o recargar), solo se muestran los avisos de los últimos
    // eventos -- "lo que acaba de pasar", ej. el silbato inicial -- y no todo lo anterior.
    const CANCHA_AVISO_EVENTOS_RECIENTES = 3;
    const canchaAvisosVistos = new Set();
    let canchaAvisosMatchId = null;
    const canchaAvisosCola = [];
    let canchaAvisoMostrando = false;

    function claveAviso(ev) {
        return `${ev.segundos_acumulados ?? ev.minuto}|${ev.tipo}|${ev.equipo}|${(ev.jugadores || []).join('|')}`;
    }

    function mostrarAvisosNuevos(data) {
        if (!canchaAviso) return;
        const eventos = data.eventos || [];
        const esPrimerRender = canchaAvisosMatchId !== data.match_id;
        if (esPrimerRender) {
            canchaAvisosMatchId = data.match_id;
            canchaAvisosVistos.clear();
            canchaAvisosCola.length = 0;
        }
        const desdeIndice = esPrimerRender ? eventos.length - CANCHA_AVISO_EVENTOS_RECIENTES : 0;
        eventos.forEach((ev, i) => {
            if (!esEventoAviso(ev)) return;
            if (ev.tipo === CANCHA_TIPO_SUSTITUCION && (ev.jugadores || []).length < 2) return;
            const clave = claveAviso(ev);
            if (canchaAvisosVistos.has(clave)) return;
            canchaAvisosVistos.add(clave);
            if (i >= desdeIndice) canchaAvisosCola.push({ ev, local: data.local, visitante: data.visitante });
        });
        if (!canchaAvisoMostrando) mostrarSiguienteAviso();
    }

    // Arma el contenido de la ventana según el tipo de aviso; devuelve la clase de color.
    function armarContenidoAviso(ev, local, visitante) {
        const encabezado = document.getElementById('canchaAvisoEncabezado');
        const titulo = document.getElementById('canchaAvisoTitulo');
        const cuerpo = document.getElementById('canchaAvisoCuerpo');
        const minuto = `${Math.round(ev.minuto)}'`;
        cuerpo.innerHTML = '';

        if (ev.tipo === CANCHA_TIPO_SUSTITUCION) {
            const [entra, sale] = ev.jugadores;
            const conPosicion = nombre => canchaPlantillas[nombre] ? `${nombre} · ${canchaPlantillas[nombre]}` : nombre;
            encabezado.textContent = ev.equipo || '';
            titulo.textContent = `🔄 Sustitución · ${minuto}`;
            [['entra', 'bi-arrow-up-circle-fill', entra], ['sale', 'bi-arrow-down-circle-fill', sale]].forEach(([clase, icono, nombre]) => {
                const fila = document.createElement('div');
                fila.className = `cancha-aviso__fila cancha-aviso__fila--${clase}`;
                fila.innerHTML = `<i class="bi ${icono}"></i><span class="cancha-aviso__dorsal"></span><span class="cancha-aviso__nombre"></span>`;
                fila.querySelector('.cancha-aviso__dorsal').textContent = canchaDorsales[nombre] ?? '';
                fila.querySelector('.cancha-aviso__nombre').textContent = conPosicion(nombre);
                cuerpo.appendChild(fila);
            });
            return ev.equipo === local ? 'local' : 'visitante';
        }

        // Árbitro / VAR: el tipo de evento como título y la descripción del motor como cuerpo (ya
        // trae el nombre del árbitro, el jugador y el marcador cuando corresponde)
        const esVar = esEventoVar(ev);
        const esEquipo = ev.equipo === local || ev.equipo === visitante;
        encabezado.textContent = esVar ? (esEquipo ? `VAR · ${ev.equipo}` : 'VAR') : 'Árbitro';
        titulo.textContent = `${ev.tipo} · ${minuto}`;
        const descripcion = document.createElement('div');
        descripcion.className = 'cancha-aviso__descripcion';
        descripcion.textContent = ev.descripcion || '';
        cuerpo.appendChild(descripcion);
        return esVar ? 'var' : 'arbitro';
    }

    function mostrarSiguienteAviso() {
        const siguiente = canchaAvisosCola.shift();
        if (!siguiente) { canchaAvisoMostrando = false; return; }
        canchaAvisoMostrando = true;
        const { ev, local, visitante } = siguiente;
        const clase = armarContenidoAviso(ev, local, visitante);

        canchaAviso.classList.remove('cancha-aviso--local', 'cancha-aviso--visitante', 'cancha-aviso--arbitro', 'cancha-aviso--var', 'cancha-aviso--visible');
        canchaAviso.classList.add(`cancha-aviso--${clase}`);
        void canchaAviso.offsetWidth; // reinicia la animación de entrada
        canchaAviso.classList.add('cancha-aviso--visible');

        setTimeout(() => {
            canchaAviso.classList.remove('cancha-aviso--visible');
            setTimeout(mostrarSiguienteAviso, 400); // deja terminar la salida antes de la próxima
        }, CANCHA_AVISO_DURACION_MS);
    }

    function renderCancha(data) {
        if (!canchaBalon) return;
        const eventos = data.eventos || [];
        canchaUltimosEventos = eventos;
        canchaNombreLocal = data.local;

        if (canchaEtiquetaLocal) canchaEtiquetaLocal.textContent = data.local || 'Local';
        if (canchaEtiquetaVisitante) canchaEtiquetaVisitante.textContent = data.visitante || 'Visitante';

        // En Modo Mapa de Calor se recalcula con la lista completa de eventos revelados hasta
        // ahora en cada actualización -- el resumen táctico se va completando a medida que
        // avanza la transmisión, en vez de solo mostrar la última jugada como el Modo Vivo.
        if (canchaModo === 'calor') {
            renderHeatmap(eventos);
        }

        mostrarAvisosNuevos(data);

        // Partidos simulados antes de este campo no traen 'posicion_balon' en sus eventos --
        // se busca el más reciente que sí lo tenga; si ninguno lo tiene, el balón se queda en
        // su posición por defecto (centro de la cancha) sin romper nada.
        // Los avisos se saltean: el balón se queda donde estaba (ver mostrarAvisosNuevos)
        let ultimoConPosicion = null;
        for (let i = eventos.length - 1; i >= 0; i--) {
            if (eventos[i].posicion_balon && !esEventoAviso(eventos[i])) { ultimoConPosicion = eventos[i]; break; }
        }
        if (!ultimoConPosicion) return;

        // El polling repite el mismo 'data.eventos' hasta que se revela uno nuevo -- sin este
        // chequeo, tanto el trazo como la animación de gol/tarjeta se reiniciarían en cada tick
        // de 3s en vez de dispararse una sola vez por jugada.
        const clave = `${ultimoConPosicion.segundos_acumulados ?? ultimoConPosicion.minuto}-${ultimoConPosicion.tipo}`;
        if (clave === canchaUltimoEventoKey) return;
        canchaUltimoEventoKey = clave;

        const esLocal = esCanchaAtacanteLocal(ultimoConPosicion);
        const posicionNueva = canchaPosicionVisual(ultimoConPosicion);
        dibujarTrazoBalon(canchaPosicionActual, posicionNueva, ultimoConPosicion.tipo, esLocal);

        const leftBalonPct = Math.max(0, Math.min(100, posicionNueva.x));
        const topBalonPct = Math.max(0, Math.min(100, (posicionNueva.y / 68) * 100));
        const leftBalon = `${leftBalonPct}%`;
        const topBalon = `${topBalonPct}%`;
        canchaBalon.style.left = leftBalon;
        canchaBalon.style.top = topBalon;
        canchaPosicionActual = posicionNueva;

        // Nombre del jugador protagonista del evento (siempre el primero de la lista, ver
        // simular_service.py -- el protagonista va primero en cada evento) junto al balón, tanto
        // en el tooltip como en la etiqueta flotante que se desvanece sola. Se le suma la
        // posición granular (POR/LD/LI/MC/ED/etc., desde canchaPlantillas -- pedidas una vez por
        // partido, ver actualizarPlantillasSiCorresponde). El equipo (evento.equipo, tal cual lo
        // arma el backend) va en su propio renglón arriba del nombre, y el tipo de evento
        // (ej. "⚽ GOL", "🛑 FALTA") en un renglón aparte abajo.
        const jugadorPrincipal = (ultimoConPosicion.jugadores && ultimoConPosicion.jugadores[0]) || '';
        const posicionSigla = canchaPlantillas[jugadorPrincipal] || '';
        const tipoEvento = ultimoConPosicion.tipo || '';
        const equipoEvento = ultimoConPosicion.equipo || '';
        let textoNombre = jugadorPrincipal;
        if (posicionSigla) textoNombre += ` · ${posicionSigla}`;

        const textoTooltip = [equipoEvento, textoNombre, tipoEvento].filter(Boolean).join(' — ');
        canchaBalon.title = textoTooltip || 'Posición del balón';
        if (canchaEtiquetaJugador && (jugadorPrincipal || tipoEvento)) {
            if (canchaEtiquetaJugadorEquipo) {
                canchaEtiquetaJugadorEquipo.textContent = equipoEvento;
                canchaEtiquetaJugadorEquipo.hidden = !equipoEvento;
                // Color según el equipo tal cual figura en 'evento.equipo' (no 'esLocal', que
                // identifica a quién ATACA en la jugada -- para tipos defensor-atribuidos, ver
                // CANCHA_TIPOS_EQUIPO_DEFENSOR, son equipos distintos). Equipos neutros
                // (Árbitro/VAR) quedan en gris en vez de heredar el color de un lado.
                const esNeutro = !equipoEvento || (equipoEvento !== data.local && equipoEvento !== data.visitante);
                canchaEtiquetaJugadorEquipo.style.color = esNeutro
                    ? '#b9c2cc'
                    : (esCanchaEquipoLocal(equipoEvento) ? '#3987e5' : '#e66767');
            }
            if (canchaEtiquetaJugadorNombre) {
                canchaEtiquetaJugadorNombre.textContent = textoNombre;
                canchaEtiquetaJugadorNombre.hidden = !jugadorPrincipal;
            }
            if (canchaEtiquetaJugadorTipo) {
                canchaEtiquetaJugadorTipo.textContent = tipoEvento;
                canchaEtiquetaJugadorTipo.hidden = !tipoEvento;
            }
            posicionarEtiquetaJugador(leftBalonPct, topBalonPct);
            canchaEtiquetaJugador.classList.add('cancha-etiqueta-jugador--visible');
            clearTimeout(canchaEtiquetaJugadorTimeout);
            canchaEtiquetaJugadorTimeout = setTimeout(() => {
                canchaEtiquetaJugador.classList.remove('cancha-etiqueta-jugador--visible');
            }, 2500);
        }

        const tipo = ultimoConPosicion.tipo || '';
        let claseEfecto = null;
        if (tipo.startsWith('⚽')) {
            claseEfecto = 'cancha-balon--gol';
        } else if (tipo.includes('DOBLE AMARILLA') || tipo.includes('TARJETA ROJA')) {
            claseEfecto = 'cancha-balon--tarjeta-roja';
        } else if (tipo.includes('TARJETA AMARILLA')) {
            claseEfecto = 'cancha-balon--tarjeta-amarilla';
        }

        if (claseEfecto) {
            canchaBalon.classList.remove('cancha-balon--gol', 'cancha-balon--tarjeta-amarilla', 'cancha-balon--tarjeta-roja');
            void canchaBalon.offsetWidth; // fuerza reflow para poder re-disparar la animación en el próximo gol/tarjeta
            canchaBalon.classList.add(claseEfecto);
        }
    }

    function actualizarInfoPartido(data) {
        infoPartidoGrupo.innerHTML = data.grupo ? `<i class="bi bi-grid-3x3-gap-fill me-1"></i>${data.grupo}` : '';
        infoPartidoGrupo.classList.toggle('d-none', !data.grupo);

        infoPartidoEstadio.innerHTML = data.estadio ? `<i class="bi bi-geo-alt-fill me-1"></i>${data.estadio}` : '';
        infoPartidoEstadio.classList.toggle('d-none', !data.estadio);

        const fechaTexto = data.fecha ? `${data.fecha}${data.hora ? ' · ' + data.hora : ''}` : '';
        infoPartidoFecha.innerHTML = fechaTexto ? `<i class="bi bi-calendar-event me-1"></i>${fechaTexto}` : '';
        infoPartidoFecha.classList.toggle('d-none', !fechaTexto);

        if (data.aforo) {
            const pct = data.aforo.porcentaje_ocupacion != null ? ` (${data.aforo.porcentaje_ocupacion}%)` : '';
            infoPartidoAforo.innerHTML = `<i class="bi bi-people-fill me-1"></i>${data.aforo.asistencia.toLocaleString('es-AR')}${pct}`;
            infoPartidoAforo.classList.remove('d-none');
        } else {
            infoPartidoAforo.classList.add('d-none');
        }
    }

    // Tabla del Grupo: se pide UNA sola vez por partido (services/live_match_service.py
    // documenta por qué -- la tabla oficial está congelada mientras dura la transmisión) y desde
    // ahí en más todo es proyección aritmética en el cliente sobre esa foto fija, disparada solo
    // cuando el marcador parcial cambia (un gol se acaba de revelar).
    let tablaGrupoData = null;
    let matchIdTablaCargada = null;
    let posicionesAnterioresTabla = null; // Map pais_id -> índice, para animar el reordenamiento
    let marcadorAnteriorTabla = null;

    function calcularPuntosPartido(golesPropios, golesRival) {
        if (golesPropios > golesRival) return 3;
        if (golesPropios === golesRival) return 1;
        return 0;
    }

    function calcularTablaProyectada(golesLocal, golesVisitante) {
        const { id_local, id_visita, equipos } = tablaGrupoData;
        const proyectada = equipos.map(e => ({ ...e }));
        for (const e of proyectada) {
            if (e.pais_id === id_local) {
                e.juegos_jugados += 1;
                e.goles_favor += golesLocal;
                e.goles_contra += golesVisitante;
                e.diferencia_goles += (golesLocal - golesVisitante);
                e.puntos += calcularPuntosPartido(golesLocal, golesVisitante);
            } else if (e.pais_id === id_visita) {
                e.juegos_jugados += 1;
                e.goles_favor += golesVisitante;
                e.goles_contra += golesLocal;
                e.diferencia_goles += (golesVisitante - golesLocal);
                e.puntos += calcularPuntosPartido(golesVisitante, golesLocal);
            }
        }
        // Mismo criterio de desempate que services/clasificacion_service.py::obtener_tablas_posiciones_por_grupo
        proyectada.sort((a, b) =>
            b.puntos - a.puntos ||
            b.diferencia_goles - a.diferencia_goles ||
            b.goles_favor - a.goles_favor ||
            b.poder - a.poder
        );
        return proyectada;
    }

    function renderTablaGrupo(golesLocal, golesVisitante, animar) {
        const proyectada = calcularTablaProyectada(golesLocal, golesVisitante);
        tablaGrupoLetra.textContent = tablaGrupoData.grupo || '';
        panelTablaGrupo.classList.remove('d-none');

        const posicionesNuevas = new Map();
        proyectada.forEach((e, i) => posicionesNuevas.set(e.pais_id, i));

        tablaGrupoBody.innerHTML = proyectada.map((e, i) => {
            const esProtagonista = e.pais_id === tablaGrupoData.id_local || e.pais_id === tablaGrupoData.id_visita;
            const dif = e.diferencia_goles;
            const claseDif = dif > 0 ? 'text-success' : (dif < 0 ? 'text-danger' : 'text-muted');
            return `
                <tr data-pais-id="${e.pais_id}" class="${esProtagonista ? 'tabla-grupo-fila-protagonista' : ''}">
                    <td class="text-center fw-bold text-muted">${i + 1}</td>
                    <td>
                        <span class="me-1">${e.bandera || ''}</span>
                        <span class="${esProtagonista ? 'fw-bold text-accent' : 'text-white'}">${e.nombre}</span>
                        <small class="text-muted">${e.siglas ? '(' + e.siglas + ')' : ''}</small>
                    </td>
                    <td class="text-center">${e.juegos_jugados}</td>
                    <td class="text-center fw-bold ${claseDif}">${dif > 0 ? '+' : ''}${dif}</td>
                    <td class="text-center fw-bold text-accent">${e.puntos}</td>
                </tr>
            `;
        }).join('');

        if (animar && posicionesAnterioresTabla) {
            tablaGrupoBody.querySelectorAll('tr').forEach(fila => {
                const paisId = Number(fila.dataset.paisId);
                const antes = posicionesAnterioresTabla.get(paisId);
                const despues = posicionesNuevas.get(paisId);
                if (antes === undefined || despues === undefined) return;
                const delta = antes - despues; // positivo = subió, negativo = bajó

                if (delta !== 0) {
                    const alto = fila.getBoundingClientRect().height || 40;
                    fila.style.transition = 'none';
                    fila.style.transform = `translateY(${delta * alto}px)`;
                    requestAnimationFrame(() => {
                        fila.style.transition = 'transform 0.6s ease';
                        fila.style.transform = 'translateY(0)';
                    });
                    fila.classList.add(delta > 0 ? 'tabla-grupo-fila--sube' : 'tabla-grupo-fila--baja');
                    setTimeout(() => fila.classList.remove('tabla-grupo-fila--sube', 'tabla-grupo-fila--baja'), 2000);
                } else if (paisId === tablaGrupoData.id_local || paisId === tablaGrupoData.id_visita) {
                    fila.classList.add('tabla-grupo-fila--igual');
                    setTimeout(() => fila.classList.remove('tabla-grupo-fila--igual'), 2000);
                }
            });
        }

        posicionesAnterioresTabla = posicionesNuevas;
    }

    async function actualizarTablaGrupoSiCorresponde(data) {
        if (data.match_id !== matchIdTablaCargada) {
            matchIdTablaCargada = data.match_id;
            posicionesAnterioresTabla = null;
            tablaGrupoData = null;
            try {
                const resp = await fetch('/matches/live/tabla-grupo');
                if (resp.ok) tablaGrupoData = await resp.json();
            } catch (e) {
                tablaGrupoData = null;
            }
            if (tablaGrupoData && tablaGrupoData.equipos && tablaGrupoData.equipos.length) {
                renderTablaGrupo(data.goles_local, data.goles_visitante, false);
            } else {
                panelTablaGrupo.classList.add('d-none');
            }
            marcadorAnteriorTabla = `${data.goles_local}-${data.goles_visitante}`;
            return;
        }

        if (!tablaGrupoData || !tablaGrupoData.equipos || !tablaGrupoData.equipos.length) return;
        const marcadorActual = `${data.goles_local}-${data.goles_visitante}`;
        if (marcadorAnteriorTabla !== marcadorActual) {
            renderTablaGrupo(data.goles_local, data.goles_visitante, true);
        }
        marcadorAnteriorTabla = marcadorActual;
    }

    // Momentum del Partido: no existe un stat de "presión" real en el motor de simulación,
    // así que se estima acá con un heurístico simple a partir de los eventos ya revelados
    // (mismos 'tipo' que ya usa badgeMinuto/renderEventos): cada tipo de evento suma o resta
    // presión al equipo que lo protagoniza (ver services/simular_service.py para a qué equipo
    // le queda atribuido 'equipo' en cada evento -- ej. en un tiro/atajada/córner es el equipo
    // ATACANTE que generó la jugada, en una falta/tarjeta es el equipo que la comete), y ese
    // valor decae con el tiempo si no pasa nada más -- así la curva sube y baja como en las
    // gráficas de "momentum" de una transmisión real, sin pretender ser una métrica exacta.
    // '❌ PENAL FALLADO' quedó en +6 (antes -5): antes 'evento.equipo' era el equipo que TIRABA
    // el penal (así que "malo para quien tira" tenía sentido con signo negativo); ahora
    // 'equipo' es el del ARQUERO que ataja (ver fix de atribución de equipo/arquero en
    // services/simular_service.py) -- un penal atajado es bueno para el arquero/su equipo, no
    // malo, así que el signo tenía que invertirse.
    const EVENTO_PESO_MOMENTUM = {
        '⚽ GOL': 16,
        '⚽ GOL DE PENAL': 16,
        '❌ PENAL FALLADO': 6,
        '🎯 DISPARO DESVIADO': 3,
        '🧤 ATAJADA ESPECTACULAR': 4,
        '🖐️ DESVÍO A CÓRNER': 3,
        '⚡ REGATE DESTACADO': 3,
        '🧠 ROBO DE BALÓN': 3,
        '🚩 FUERA DE LUGAR': -2,
        '🛑 FALTA': -2,
        '🟨 TARJETA AMARILLA': -4,
        '🟥 TARJETA ROJA': -8,
        '🟨🟥 DOBLE AMARILLA': -8,
        '⚠️ ERROR DE PORTERÍA': -5
    };
    const EVENTOS_CLAVE_MOMENTUM = new Set([
        '⚽ GOL', '⚽ GOL DE PENAL', '🟥 TARJETA ROJA', '🟨🟥 DOBLE AMARILLA', '🟨 TARJETA AMARILLA'
    ]);
    const DECAY_MOMENTUM_POR_MINUTO = 0.90;
    const MOMENTUM_MAX_ABS = 20;

    let eventosPorMinutoMomentum = new Map();

    // Jugadores en Cancha: rating individual en vivo (badge estilo templates/simulador.html,
    // mismos umbrales de color) + momentum acumulado por equipo, todo derivado de vuelta desde
    // cero en cada poll a partir de 'data.eventos' -- igual criterio que el resto de esta vista,
    // para no arrastrar estado inconsistente si se recarga la página a mitad de partido.
    //
    // EVENTO_PESO_JUGADOR es un primo chico de EVENTO_PESO_MOMENTUM: misma idea (qué tipos de
    // evento suman/restan mérito), pero en la escala 3.0-10.0 de 'calcular_rating_partido'
    // (services/simular_service.py). Pesos calibrados con 40 partidos simulados para que el rating
    // en vivo al final del partido se acerque al rating real que guarda el motor, por posición
    // (el motor además cuenta pases, regates y recuperaciones que no generan evento visible, así
    // que nunca va a coincidir exacto -- solo en promedio y tendencia).
    const EVENTO_PESO_JUGADOR = {
        '⚽ GOL': 1.4,
        '⚽ GOL DE PENAL': 1.4,
        '⚽ GOL DE TIRO LIBRE': 1.4,
        '⚽ GOL DE CÓRNER': 1.4,
        '❌ PENAL FALLADO': 0.8,  // el protagonista es el arquero que lo atajó (ver ejecutar_penal)
        '🧤 ATAJADA ESPECTACULAR': 0.3,
        '🖐️ DESVÍO A CÓRNER': 0.15,
        '⚡ REGATE DESTACADO': 0.25,
        '🧠 ROBO DE BALÓN': 0.3,
        '🎯 DISPARO DESVIADO': 0,  // se lista como acción, pero no mueve el rating (el motor tampoco lo castiga casi)
        '🚩 FUERA DE LUGAR': -0.05,
        '🛑 FALTA': -0.15,
        '🟨 TARJETA AMARILLA': -0.4,
        '🟥 TARJETA ROJA': -3.0,
        '🟨🟥 DOBLE AMARILLA': -3.0,
        '⚠️ ERROR DE PORTERÍA': -1.0
    };
    // '⚡ EN TRANSICIÓN' (pérdida de balón sin falta, jugadores = [defensor, atacante]) no tiene un
    // único protagonista: le suma un poco al que recuperó y le resta un poco al que la perdió.
    // Peso chico a propósito -- pasa decenas de veces por partido, es la acción defensiva más común.
    const EVENTO_TRANSICION = '⚡ EN TRANSICIÓN';
    const PESO_RECUPERACION_JUGADOR = 0.04;
    const PESO_PERDIDA_JUGADOR = -0.08;
    // Gol recibido: se lo resta al arquero en cancha del equipo que lo recibe (el motor hace lo
    // mismo con 'goles_encajados'; los penales no cuentan, igual que allá).
    const TIPOS_GOL_ENCAJADO_PORTERO = new Set(['⚽ GOL', '⚽ GOL DE TIRO LIBRE', '⚽ GOL DE CÓRNER']);
    const PESO_GOL_ENCAJADO_PORTERO = -0.4;
    const RATING_BASE = 6.7; // mismo RATING_BASE "partido normal" que calcular_rating_partido
    const RATING_MIN = 3.0;
    const RATING_MAX = 10.0;
    const RATING_MAX_EXPULSADO = 4.5; // mismo tope que calcular_rating_partido para un jugador expulsado

    function claseBadgeRating(rating) {
        if (rating >= 7.5) return 'bg-success';
        if (rating >= 6.5) return 'bg-primary';
        if (rating >= 6.0) return 'bg-secondary';
        return 'bg-danger';
    }

    function claseBadgeMomentumEquipo(valor) {
        if (valor > 1) return 'bg-success';
        if (valor < -1) return 'bg-danger';
        return 'bg-secondary';
    }

    function textoMomentumEquipo(valor) {
        const redondeado = Math.round(valor);
        return redondeado > 0 ? `+${redondeado}` : `${redondeado}`;
    }

    // Recorre TODOS los eventos revelados hasta ahora y devuelve, por equipo: quién sigue en
    // cancha (arrancando del 11 inicial, actualizado por sustituciones/expulsiones ya reveladas)
    // y el rating acumulado de cada uno de esos jugadores.
    function calcularEstadoJugadoresEnCancha(data) {
        const onceLocal = new Set(canchaTitularesLocal);
        const onceVisitante = new Set(canchaTitularesVisitante);
        const ratings = new Map();
        const acciones = new Map(); // nombre -> [{ tipo, minuto, peso }], en orden cronológico
        const expulsados = new Set();
        // Arquero en cancha de cada equipo: el titular de línea 1, actualizado si sale de cambio
        const porteros = {
            [data.local]: canchaTitularesLocal[canchaLineasLocal.indexOf(1)],
            [data.visitante]: canchaTitularesVisitante[canchaLineasVisitante.indexOf(1)]
        };

        function onceDe(equipo) {
            if (equipo === data.local) return onceLocal;
            if (equipo === data.visitante) return onceVisitante;
            return null;
        }

        (data.eventos || []).forEach(ev => {
            const jugadores = ev.jugadores || [];

            if (ev.tipo === '🔄 SUSTITUCIÓN' && jugadores.length >= 2) {
                const once = onceDe(ev.equipo);
                if (once) {
                    once.delete(jugadores[1]);
                    once.add(jugadores[0]);
                }
                if (porteros[ev.equipo] === jugadores[1]) porteros[ev.equipo] = jugadores[0];
            } else if ((ev.tipo === '🟥 TARJETA ROJA' || ev.tipo === '🟨🟥 DOBLE AMARILLA') && jugadores.length >= 1) {
                const once = onceDe(ev.equipo);
                if (once) once.delete(jugadores[0]);
                expulsados.add(jugadores[0]);
            }

            function sumarAccion(nombre, tipo, peso) {
                ratings.set(nombre, (ratings.has(nombre) ? ratings.get(nombre) : RATING_BASE) + peso);
                if (!acciones.has(nombre)) acciones.set(nombre, []);
                acciones.get(nombre).push({ tipo, minuto: ev.minuto, peso });
            }

            if (ev.tipo === EVENTO_TRANSICION && jugadores.length >= 2) {
                sumarAccion(jugadores[0], '🧹 RECUPERACIÓN', PESO_RECUPERACION_JUGADOR);
                sumarAccion(jugadores[1], '💨 PÉRDIDA DE BALÓN', PESO_PERDIDA_JUGADOR);
                return;
            }

            if (TIPOS_GOL_ENCAJADO_PORTERO.has(ev.tipo)) {
                const rival = ev.equipo === data.local ? data.visitante : data.local;
                if (porteros[rival]) sumarAccion(porteros[rival], '🥅 GOL RECIBIDO', PESO_GOL_ENCAJADO_PORTERO);
            }

            const protagonista = jugadores[0];
            const peso = protagonista ? EVENTO_PESO_JUGADOR[ev.tipo] : undefined;
            if (peso !== undefined) sumarAccion(protagonista, ev.tipo, peso);
        });

        function filaDe(nombre) {
            const max = expulsados.has(nombre) ? RATING_MAX_EXPULSADO : RATING_MAX;
            const crudo = ratings.has(nombre) ? ratings.get(nombre) : RATING_BASE;
            const rating = Math.max(RATING_MIN, Math.min(max, crudo));
            return { nombre, posicion: canchaPlantillas[nombre] || '', rating, acciones: acciones.get(nombre) || [] };
        }

        return {
            local: Array.from(onceLocal).map(filaDe),
            visitante: Array.from(onceVisitante).map(filaDe)
        };
    }

    function calcularMomentumAcumuladoPorEquipo(data) {
        let local = 0, visitante = 0;
        (data.eventos || []).forEach(ev => {
            const peso = EVENTO_PESO_MOMENTUM[ev.tipo];
            if (!peso) return;
            if (ev.equipo === data.local) local += peso;
            else if (ev.equipo === data.visitante) visitante += peso;
        });
        return { local, visitante };
    }

    // Serie del momentum acumulado (sin decaimiento, a diferencia de calcularSerieMomentum que
    // alimenta el gráfico grande de "📈 Momentum del Partido") de UN solo equipo, minuto a
    // minuto -- para el mini-gráfico ("sparkline") de su card en "Jugadores en Cancha".
    // Antes esta serie era una suma acumulada SIN decaimiento -- una vez que subía se quedaba
    // "plana" ahí (solo saltos puntuales en cada evento con peso), así que se veía como una línea
    // recta la mayor parte del partido. Ahora usa el mismo decaimiento por minuto que ya usa el
    // gráfico grande de "📈 Momentum del Partido" (DECAY_MOMENTUM_POR_MINUTO), pero por equipo
    // independiente (sin restarle el peso del rival) -- así refleja el "momento" reciente de ESE
    // equipo, con subidas y bajadas visibles en vez de una tendencia casi plana.
    function calcularSerieAcumuladaEquipo(data, nombreEquipo) {
        const maxMinuto = Math.max(90, Math.ceil(data.minuto_actual || 0));
        const porMinuto = new Map();
        (data.eventos || []).forEach(ev => {
            if (ev.equipo !== nombreEquipo) return;
            const peso = EVENTO_PESO_MOMENTUM[ev.tipo];
            if (!peso) return;
            const m = Math.min(maxMinuto, Math.max(0, Math.round(ev.minuto)));
            porMinuto.set(m, (porMinuto.get(m) || 0) + peso);
        });

        const valores = new Array(maxMinuto + 1).fill(0);
        let actual = 0;
        for (let m = 0; m <= maxMinuto; m++) {
            actual *= DECAY_MOMENTUM_POR_MINUTO;
            actual += porMinuto.get(m) || 0;
            valores[m] = actual;
        }
        return valores;
    }

    // Mini-gráficos ("sparkline") de momentum acumulado en las cards de "Jugadores en Cancha" --
    // sin ejes/leyenda/tooltip, solo la forma de la tendencia; el número exacto sigue al lado
    // (#onceMomentumLocal/Visitante). Reutilizan Chart.js, ya cargado para el gráfico grande.
    let onceMomentumChartLocal = null;
    let onceMomentumChartVisitante = null;

    function inicializarSparklineMomentum(idCanvas, color, colorRelleno) {
        const canvas = document.getElementById(idCanvas);
        if (!canvas || typeof Chart === 'undefined') return null;
        return new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: { labels: [0], datasets: [
                { data: [0], borderColor: color, backgroundColor: colorRelleno, fill: 'origin', tension: 0.35, pointRadius: 0, borderWidth: 1.5 }
            ] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: { intersect: false },
                scales: {
                    x: { display: false },
                    y: { display: false }
                },
                plugins: { legend: { display: false }, tooltip: { enabled: false } }
            }
        });
    }

    function renderSparklineMomentum(chart, valores) {
        if (!chart) return;
        chart.data.labels = valores.map((_, i) => i);
        chart.data.datasets[0].data = valores;
        chart.update('none');
    }

    // Id de DOM seguro a partir de un nombre de jugador -- hay nombres con espacios, acentos o
    // apóstrofes (ej. "N'Douassel") que romperían un selector CSS/data-bs-target tal cual.
    function slugJugador(nombre) {
        return nombre.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-zA-Z0-9]+/g, '-').toLowerCase();
    }

    // Qué jugadores tienen su fila de "Jugadores en Cancha" desplegada ahora mismo -- las listas
    // se reconstruyen enteras en cada poll de 3s (mismo criterio que el resto de esta vista), así
    // que sin este estado persistente cualquier fila abierta se volvería a cerrar sola en el
    // siguiente render. Los eventos de Bootstrap burbujean hasta 'document', así que un solo par
    // de listeners (registrados una sola vez acá) alcanza para todas las filas, presentes y
    // futuras, sin tener que instanciar bootstrap.Collapse a mano.
    const jugadoresExpandidos = new Set();
    document.addEventListener('shown.bs.collapse', e => {
        if (e.target.dataset.jugador) jugadoresExpandidos.add(e.target.dataset.jugador);
    });
    document.addEventListener('hidden.bs.collapse', e => {
        if (e.target.dataset.jugador) jugadoresExpandidos.delete(e.target.dataset.jugador);
    });

    function renderFilaJugadorEnCancha(jugador, lado) {
        const fila = document.createElement('div');
        fila.className = 'list-group-item bg-dark text-white p-0 border-secondary border-opacity-10 small';

        const idAcciones = `once-acciones-${lado}-${slugJugador(jugador.nombre)}`;
        const expandido = jugadoresExpandidos.has(jugador.nombre);
        const posicionTexto = jugador.posicion ? ` <span class="text-muted">· ${jugador.posicion}</span>` : '';
        // Mismo dorsal y color de equipo que su ficha en la cancha, para ubicarlo de un vistazo
        const dorsal = canchaDorsales[jugador.nombre];
        const dorsalHtml = dorsal != null ? `<span class="once-dorsal once-dorsal--${lado}">${dorsal}</span>` : '';

        const accionesHtml = jugador.acciones.length
            ? jugador.acciones.slice().reverse().map(a => {
                const signo = a.peso > 0 ? '+' : '';
                const clase = a.peso > 0 ? 'text-success' : (a.peso < 0 ? 'text-danger' : 'text-muted');
                return `<div class="${clase}">${signo}${a.peso.toFixed(2)} &nbsp;${a.tipo} &nbsp;<span class="text-muted">· ${Math.round(a.minuto)}'</span></div>`;
            }).join('')
            : '<div class="text-muted fst-italic">Todavía no tiene acciones que hayan afectado su rendimiento.</div>';

        fila.innerHTML = `
            <div class="d-flex justify-content-between align-items-center py-1 px-3" style="cursor:pointer;"
                 data-bs-toggle="collapse" data-bs-target="#${idAcciones}"
                 aria-expanded="${expandido}" aria-controls="${idAcciones}">
                <span class="d-flex align-items-center gap-2" style="min-width: 0;">
                    ${dorsalHtml}<span class="text-truncate">${jugador.nombre}${posicionTexto}</span>
                </span>
                <span class="d-flex align-items-center gap-1">
                    <span class="badge rounded-pill ${claseBadgeRating(jugador.rating)}">${jugador.rating.toFixed(1)}</span>
                    <i class="bi bi-chevron-down text-muted" style="font-size:.65rem;"></i>
                </span>
            </div>
            <div class="collapse${expandido ? ' show' : ''}" id="${idAcciones}" data-jugador="${jugador.nombre}">
                <div class="px-3 pb-2 pt-1 border-top border-secondary border-opacity-10" style="font-size:.72rem;">
                    ${accionesHtml}
                </div>
            </div>
        `;
        return fila;
    }

    function renderJugadoresEnCancha(data) {
        if (!onceListaLocal || !onceListaVisitante) return;
        if (onceNombreLocal) onceNombreLocal.textContent = data.local;
        if (onceNombreVisitante) onceNombreVisitante.textContent = data.visitante;

        const estado = calcularEstadoJugadoresEnCancha(data);
        onceListaLocal.innerHTML = '';
        estado.local.forEach(j => onceListaLocal.appendChild(renderFilaJugadorEnCancha(j, 'local')));
        onceListaVisitante.innerHTML = '';
        estado.visitante.forEach(j => onceListaVisitante.appendChild(renderFilaJugadorEnCancha(j, 'visitante')));

        const momentum = calcularMomentumAcumuladoPorEquipo(data);
        if (onceMomentumLocal) {
            onceMomentumLocal.textContent = textoMomentumEquipo(momentum.local);
            onceMomentumLocal.className = `badge rounded-pill ${claseBadgeMomentumEquipo(momentum.local)}`;
        }
        if (onceMomentumVisitante) {
            onceMomentumVisitante.textContent = textoMomentumEquipo(momentum.visitante);
            onceMomentumVisitante.className = `badge rounded-pill ${claseBadgeMomentumEquipo(momentum.visitante)}`;
        }

        if (!onceMomentumChartLocal) onceMomentumChartLocal = inicializarSparklineMomentum('onceMomentumChartLocal', '#3987e5', 'rgba(57, 135, 229, 0.25)');
        if (!onceMomentumChartVisitante) onceMomentumChartVisitante = inicializarSparklineMomentum('onceMomentumChartVisitante', '#e66767', 'rgba(230, 103, 103, 0.25)');
        renderSparklineMomentum(onceMomentumChartLocal, calcularSerieAcumuladaEquipo(data, data.local));
        renderSparklineMomentum(onceMomentumChartVisitante, calcularSerieAcumuladaEquipo(data, data.visitante));
    }

    function calcularSerieMomentum(data) {
        const maxMinuto = Math.max(90, Math.ceil(data.minuto_actual || 0));
        const porMinuto = new Map();
        (data.eventos || []).forEach(ev => {
            const m = Math.min(maxMinuto, Math.max(0, Math.round(ev.minuto)));
            if (!porMinuto.has(m)) porMinuto.set(m, []);
            porMinuto.get(m).push(ev);
        });

        const valores = new Array(maxMinuto + 1).fill(0);
        let actual = 0;
        for (let m = 0; m <= maxMinuto; m++) {
            actual *= DECAY_MOMENTUM_POR_MINUTO;
            for (const ev of (porMinuto.get(m) || [])) {
                const peso = EVENTO_PESO_MOMENTUM[ev.tipo];
                if (!peso) continue;
                if (ev.equipo === data.local) actual += peso;
                else if (ev.equipo === data.visitante) actual -= peso;
            }
            valores[m] = Math.max(-MOMENTUM_MAX_ABS, Math.min(MOMENTUM_MAX_ABS, actual));
        }
        eventosPorMinutoMomentum = porMinuto;
        return { valores, maxMinuto };
    }

    function colorPuntoMomentum(evs, equipoObjetivo) {
        const delEquipo = evs.filter(e => e.equipo === equipoObjetivo);
        if (delEquipo.some(e => e.tipo === '⚽ GOL' || e.tipo === '⚽ GOL DE PENAL')) return '#facc15';
        if (delEquipo.some(e => e.tipo === '🟥 TARJETA ROJA' || e.tipo === '🟨🟥 DOBLE AMARILLA')) return '#e34948';
        if (delEquipo.some(e => e.tipo === '🟨 TARJETA AMARILLA')) return '#eda100';
        return null;
    }

    let momentumChart = null;
    function inicializarMomentumChart() {
        const canvas = document.getElementById('momentumChart');
        if (!canvas || typeof Chart === 'undefined') return;
        momentumChart = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: { labels: [0], datasets: [
                { label: 'Local', data: [0], borderColor: '#3987e5', backgroundColor: 'rgba(57, 135, 229, 0.25)', fill: 'origin', tension: 0.35, pointRadius: 0, borderWidth: 2 },
                { label: 'Visitante', data: [0], borderColor: '#e66767', backgroundColor: 'rgba(230, 103, 103, 0.25)', fill: 'origin', tension: 0.35, pointRadius: 0, borderWidth: 2 }
            ] },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 300 },
                interaction: { mode: 'index', intersect: false },
                scales: {
                    x: {
                        ticks: { color: '#acb1b9', maxTicksLimit: 10, callback: (val, idx) => `${idx}'` },
                        grid: { color: 'rgba(255,255,255,0.05)' }
                    },
                    y: {
                        min: -MOMENTUM_MAX_ABS, max: MOMENTUM_MAX_ABS,
                        ticks: { display: false },
                        grid: { color: (ctx) => ctx.tick.value === 0 ? 'rgba(255,255,255,0.35)' : 'rgba(255,255,255,0.05)' }
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => `Minuto ${items[0].label}'`,
                            label: (item) => {
                                const evs = eventosPorMinutoMomentum.get(item.dataIndex) || [];
                                if (evs.length) return evs.map(e => `${e.tipo} (${e.equipo})`);
                                return `${item.dataset.label}: presión ${Math.abs(item.raw).toFixed(0)}`;
                            }
                        }
                    }
                }
            }
        });
    }

    function renderMomentum(data) {
        if (!momentumChart) return;
        const { valores, maxMinuto } = calcularSerieMomentum(data);
        momentumChart.data.labels = Array.from({ length: maxMinuto + 1 }, (_, i) => i);
        momentumChart.data.datasets[0].data = valores.map(v => v > 0 ? v : 0);
        momentumChart.data.datasets[1].data = valores.map(v => v < 0 ? v : 0);
        momentumChart.data.datasets[0].pointRadius = valores.map((_, m) => {
            const evs = eventosPorMinutoMomentum.get(m) || [];
            return evs.some(e => e.equipo === data.local && EVENTOS_CLAVE_MOMENTUM.has(e.tipo)) ? 5 : 0;
        });
        momentumChart.data.datasets[1].pointRadius = valores.map((_, m) => {
            const evs = eventosPorMinutoMomentum.get(m) || [];
            return evs.some(e => e.equipo === data.visitante && EVENTOS_CLAVE_MOMENTUM.has(e.tipo)) ? 5 : 0;
        });
        momentumChart.data.datasets[0].pointBackgroundColor = valores.map((_, m) => colorPuntoMomentum(eventosPorMinutoMomentum.get(m) || [], data.local) || '#3987e5');
        momentumChart.data.datasets[1].pointBackgroundColor = valores.map((_, m) => colorPuntoMomentum(eventosPorMinutoMomentum.get(m) || [], data.visitante) || '#e66767');
        momentumChart.update();
    }

    // Goles y Tarjetas: los eventos solo traen minuto/equipo/tipo/descripcion -- no hay un
    // campo estructurado de jugador -- así que el nombre se extrae de la descripción con
    // regex, mismo patrón ya usado en templates/base.html para la línea de goleador del
    // badge flotante. Cada tipo de gol/tarjeta tiene su propia plantilla de texto fija en
    // services/simular_service.py, de ahí las distintas expresiones según el 'tipo'.
    const ICONO_POR_TIPO_GT = {
        '⚽ GOL': '⚽',
        '⚽ GOL DE PENAL': '⚽',
        '🟨 TARJETA AMARILLA': '🟨',
        '🟥 TARJETA ROJA': '🟥',
        '🟨🟥 DOBLE AMARILLA': '🟥'
    };
    const REGEX_JUGADOR_POR_TIPO = [
        { tipo: '⚽ GOL', regex: /¡Golazo de ([^!]+)!/ },
        { tipo: '⚽ GOL DE PENAL', regex: /¡Gol de ([^!]+) en la tanda de penaltis!/ },
        { tipo: '🟨 TARJETA AMARILLA', regex: /Amonestación para ([^.]+?) por juego brusco/ },
        { tipo: '🟨 TARJETA AMARILLA', regex: /Tarjeta amarilla para ([^.]+?) por derribar/ },
        { tipo: '🟥 TARJETA ROJA', regex: /¡Entrada desmedida! ([^.]+) recibe roja directa/ },
        { tipo: '🟨🟥 DOBLE AMARILLA', regex: /¡Segunda amarilla! ([^.]+) se va expulsado/ }
    ];

    function extraerNombreJugador(evento) {
        // Preferir el campo estructurado 'jugadores' (agregado en simular_service.py) -- el
        // regex de abajo queda solo como fallback para partidos simulados antes de ese cambio,
        // que no lo tienen persistido.
        if (evento.jugadores && evento.jugadores.length) return evento.jugadores[0];
        for (const { tipo, regex } of REGEX_JUGADOR_POR_TIPO) {
            if (tipo !== evento.tipo) continue;
            const match = evento.descripcion.match(regex);
            if (match) return match[1].trim();
        }
        return null;
    }

    function renderGolesTarjetas(data) {
        const porEquipo = { local: [], visit: [] };
        (data.eventos || []).forEach(ev => {
            const icono = ICONO_POR_TIPO_GT[ev.tipo];
            if (!icono) return;
            const nombre = extraerNombreJugador(ev);
            if (!nombre) return;
            const entrada = { minuto: ev.minuto, icono, nombre };
            if (ev.equipo === data.local) porEquipo.local.push(entrada);
            else if (ev.equipo === data.visitante) porEquipo.visit.push(entrada);
        });
        // Más reciente primero, mismo criterio que la Cronología en Vivo.
        porEquipo.local.reverse();
        porEquipo.visit.reverse();

        const renderLista = (contenedor, lista) => {
            if (!lista.length) {
                contenedor.innerHTML = '<div class="text-muted text-center small py-2">Sin eventos aún</div>';
                return;
            }
            contenedor.innerHTML = lista.map(e => `
                <div class="surface-soft p-2 px-2 d-flex align-items-center gap-2">
                    <span class="badge bg-dark border border-secondary">${e.minuto}'</span>
                    <span>${e.icono}</span>
                    <span class="text-white small text-truncate">${e.nombre}</span>
                </div>
            `).join('');
        };
        renderLista(golesTarjetasLocal, porEquipo.local);
        renderLista(golesTarjetasVisitante, porEquipo.visit);
    }

    inicializarMomentumChart();

    async function renderEnVivo(data) {
        quitarPanelCargando();
        panelInactivo.classList.add('d-none');
        panelEnVivo.classList.remove('d-none');

        nombreLocal.textContent = data.local;
        nombreVisitante.textContent = data.visitante;
        marcador.textContent = `${data.goles_local} - ${data.goles_visitante}`;
        renderMarcadorAgua(data);
        minutoActual.textContent = `${data.minuto_actual}'`;
        renderEventos(data.eventos);
        await actualizarPlantillasSiCorresponde(data.match_id);
        renderCancha(data);
        reiniciarJugadoresCanchaSiCambioPartido(data.match_id);
        renderJugadoresCancha(data);
        renderJugadoresEnCancha(data);
        actualizarInfoPartido(data);
        await actualizarTablaGrupoSiCorresponde(data);
        momentumLeyendaLocal.textContent = data.local;
        momentumLeyendaVisitante.textContent = data.visitante;
        renderMomentum(data);
        golesTarjetasNombreLocal.textContent = data.local;
        golesTarjetasNombreVisitante.textContent = data.visitante;
        renderGolesTarjetas(data);

        const pct = Math.min(100, Math.max(0, (data.segundos_transcurridos / (data.segundos_transcurridos + data.segundos_restantes)) * 100));
        barraTiempo.style.width = `${pct}%`;
        segundosRestantes.textContent = Math.max(0, Math.round(data.segundos_restantes));

        if (data.finalizado) {
            badgeEstado.innerHTML = '<i class="bi bi-flag-fill me-1"></i>FINALIZADO';
            badgeEstado.classList.remove('bg-danger');
            badgeEstado.classList.add('bg-secondary');
            barraTiempo.classList.remove('bg-danger');
            barraTiempo.classList.add('bg-secondary');
            panelFinalizado.classList.remove('d-none');
            if (!jevProximoFinalMostrado) {
                jevProximoFinalMostrado = true;
                jevMostrarProximo(document.getElementById('jevProximoFinal'), document.getElementById('jevProximoFinalTitulo'), document.getElementById('jevProximoFinalSelector'));
            }
            detenerPolling();
            if (btnSimularOtro) programarAutoPlay(btnSimularOtro);
            else programarReconsultaInactivo(); // sin permiso de simular: esperar el próximo partido
        } else {
            badgeEstado.innerHTML = '<i class="bi bi-circle-fill me-1 blink-dot"></i>EN VIVO';
            badgeEstado.classList.remove('bg-secondary');
            badgeEstado.classList.add('bg-danger');
            barraTiempo.classList.remove('bg-secondary');
            barraTiempo.classList.add('bg-danger');
            panelFinalizado.classList.add('d-none');
            jevProximoFinalMostrado = false;
        }
    }

    // ---------------------------------------------------------------------------------------
    // Juego en Vivo (services/juego_en_vivo_service.py vía /live-game): el backend calcula todo
    // (puntos, multiplicador vigente, cooldown); acá solo se muestra. Se consulta en el mismo
    // ciclo de polling que la transmisión, en su propio try/catch para no romperla.
    // ---------------------------------------------------------------------------------------
    const JEV_HABILITADO = window.LIVE_CONFIG.juegoEnVivoHabilitado;
    const jevPanel = document.getElementById('jevPanel');
    const jevResumenInactivo = document.getElementById('jevResumenInactivo');
    const jevProximo = document.getElementById('jevProximo');
    const jevProximoTitulo = document.getElementById('jevProximoTitulo');
    const jevProximoSelector = document.getElementById('jevProximoSelector');
    const JEV_MAX_TOASTS_POR_POLL = 4;
    const jev = {
        matchId: null,          // partido al que corresponde el estado mostrado
        ultimoMatchVisto: null, // para pedir el resumen cuando /matches/live pase a 404
        txVistas: null,         // cuántas transacciones ya se mostraron (null = primer render: no se tostean)
        saldoMostrado: null,
        estado: null,
        estadoRecibidoEn: 0,
        chart: null,
        ocupado: false,
        mensaje: null,
    };
    let jevToastsCapa = null;
    let jevProximoFinalMostrado = false;
    let jevTickHandle = null;

    function jevPuntos(n) { return JuegoEnVivoSelector.formatearPuntos(n); }
    function jevSigno(n) { return n > 0 ? `+${jevPuntos(n)}` : jevPuntos(n); }
    function jevNombreRiesgo(m) {
        const nivel = (jev.estado && jev.estado.niveles_riesgo || []).find(n => n.multiplicador === m);
        return nivel ? nivel.nombre : '';
    }

    async function actualizarJuegoEnVivo(data) {
        if (!JEV_HABILITADO || !jevPanel) return;
        jev.ultimoMatchVisto = data.match_id;
        try {
            const estado = await JuegoEnVivoSelector.pedir('GET', `/live-game/state?juego_id=${encodeURIComponent(data.match_id)}`);
            renderJuegoEnVivo(estado, data);
        } catch (e) {
            // Un error del juego no debe tapar la transmisión: se deja el último estado dibujado
        }
    }

    function reiniciarJuegoSiCambioPartido(juegoId) {
        if (jev.matchId === juegoId) return;
        jev.matchId = juegoId;
        jev.txVistas = null;
        jev.saldoMostrado = null;
        jev.mensaje = null;
        if (jev.chart) { jev.chart.destroy(); jev.chart = null; }
    }

    function renderJuegoEnVivo(estado, data) {
        reiniciarJuegoSiCambioPartido(estado.juego_id || data.match_id);
        jevPanel.classList.remove('d-none');
        if (estado.modo !== 'jugador') {
            jev.estado = null;
            jevPanel.innerHTML = `<div class="text-center small text-muted">👀 Modo espectador: no elegiste país para este partido.
                <a href="/juegos" class="link-success">Elige país en Juegos</a> para jugar los próximos.</div>`;
            return;
        }
        jev.estado = estado;
        jev.estadoRecibidoEn = Date.now();

        const nuevas = jev.txVistas === null ? [] : estado.transacciones.slice(jev.txVistas);
        jev.txVistas = estado.transacciones.length;

        if (!jevPanel.querySelector('#jevSaldo')) jevPanel.innerHTML = jevMarkupPanel();
        jevRenderCabecera(estado);
        jevRenderSaldo(estado.puntos_actuales);
        jevRenderRiesgo();
        jevRenderFeed(estado);
        jevRenderGrafico(estado);
        jevRenderResumen(document.getElementById('jevResumenEnVivo'), estado);
        nuevas.slice(-JEV_MAX_TOASTS_POR_POLL).forEach(jevMostrarToast);
        if (!jevTickHandle) jevTickHandle = setInterval(jevRenderRiesgo, 1000);
    }

    function jevMarkupPanel() {
        return `
            <div class="card border border-success border-opacity-50 shadow-sm" style="background: rgba(25, 135, 84, .08);">
                <div class="card-body p-3">
                    <div class="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-2">
                        <h6 class="fw-bold text-white mb-0">🎮 Juego en Vivo · <span id="jevPais"></span></h6>
                        <span id="jevEstadoBadge" class="badge"></span>
                    </div>
                    <div id="jevAlerta"></div>
                    <div class="row g-3 align-items-center">
                        <div class="col-6 col-md-4 text-white">
                            <div class="small text-muted">Saldo</div>
                            <div id="jevSaldo" class="jev-saldo">0</div>
                            <div id="jevNeto" class="small"></div>
                        </div>
                        <div class="col-6 col-md-3 text-center">
                            <div class="small text-muted mb-1">Riesgo actual</div>
                            <span id="jevMultiplicador" class="badge rounded-pill px-3 py-2 jev-multiplicador">x1</span>
                            <div id="jevMultiplicadorAviso" class="small mt-1"></div>
                        </div>
                        <div class="col-12 col-md-5">
                            <div class="jev-riesgos" id="jevRiesgos"></div>
                            <div class="progress mt-2" style="height: 5px; background-color: rgba(255,255,255,0.08);">
                                <div id="jevCooldownBarra" class="progress-bar bg-info" style="width: 0%"></div>
                            </div>
                            <div id="jevCooldownTexto" class="small text-muted mt-1"></div>
                        </div>
                    </div>
                    <div class="row g-3 mt-1">
                        <div class="col-12 col-md-7">
                            <div class="small text-muted mb-1">Evolución del saldo</div>
                            <div class="jev-grafico"><canvas id="jevGrafico"></canvas></div>
                        </div>
                        <div class="col-12 col-md-5">
                            <div class="small text-muted mb-1">Impacto de cada evento</div>
                            <div id="jevFeed" class="jev-feed text-white"></div>
                        </div>
                    </div>
                    <div id="jevResumenEnVivo"></div>
                </div>
            </div>`;
    }

    function jevRenderCabecera(estado) {
        document.getElementById('jevPais').textContent = `${estado.pais_bandera || ''} ${estado.pais_nombre}`.trim();
        const badge = document.getElementById('jevEstadoBadge');
        const estados = {
            pendiente: ['Por empezar', 'bg-secondary'], en_curso: ['Jugando', 'bg-success'],
            eliminada: ['Sin puntos', 'bg-danger'], finalizada: ['Finalizado', 'bg-secondary'], cancelada: ['Reembolsado', 'bg-secondary'],
        };
        const [texto, clase] = estados[estado.estado] || [estado.estado, 'bg-secondary'];
        badge.className = `badge ${clase}`;
        badge.textContent = texto;
        const neto = estado.puntos_actuales - estado.puntos_iniciales;
        const elNeto = document.getElementById('jevNeto');
        elNeto.className = `small ${neto > 0 ? 'text-success' : neto < 0 ? 'text-danger' : 'text-muted'}`;
        elNeto.textContent = `Inicial ${jevPuntos(estado.puntos_iniciales)} · ${jevSigno(neto)}`;
        document.getElementById('jevAlerta').innerHTML = estado.estado === 'eliminada'
            ? '<div class="alert alert-danger py-2 small">Te quedaste en 0 puntos: sigues viendo el partido, pero ya no sumas ni restas.</div>'
            : (jev.mensaje ? `<div class="alert alert-${jev.mensaje.tipo} py-2 small">${escaparHtml(jev.mensaje.texto)}</div>` : '');
    }

    // Saldo: cuenta animada desde el valor anterior + "latido" verde/rojo
    function jevRenderSaldo(saldo) {
        const el = document.getElementById('jevSaldo');
        const anterior = jev.saldoMostrado;
        jev.saldoMostrado = saldo;
        if (anterior === null || anterior === saldo) { el.textContent = jevPuntos(saldo); return; }
        el.classList.remove('jev-saldo--sube', 'jev-saldo--baja');
        void el.offsetWidth;
        el.classList.add(saldo > anterior ? 'jev-saldo--sube' : 'jev-saldo--baja');
        const inicio = performance.now(), duracion = 700;
        const paso = ahora => {
            const t = Math.min(1, (ahora - inicio) / duracion);
            el.textContent = jevPuntos(Math.round(anterior + (saldo - anterior) * t));
            if (t < 1 && jev.saldoMostrado === saldo) requestAnimationFrame(paso);
        };
        requestAnimationFrame(paso);
    }

    // Multiplicador actual, cambio pendiente y botones con cooldown. Se repinta cada 1s con una
    // cuenta regresiva local desde el último estado del backend (que es quien valida de verdad).
    function jevRenderRiesgo() {
        const estado = jev.estado;
        if (!estado || !document.getElementById('jevRiesgos')) return;
        const transcurrido = (Date.now() - jev.estadoRecibidoEn) / 1000;
        const m = estado.multiplicador_actual;
        const badge = document.getElementById('jevMultiplicador');
        badge.className = `badge rounded-pill px-3 py-2 jev-multiplicador ${m >= 3 ? 'bg-danger jev-multiplicador--extremo' : m >= 2 ? 'jev-badge-x2 jev-multiplicador--alto' : m > 1 ? 'bg-info text-dark' : 'bg-success'}`;
        badge.textContent = `x${m} · ${jevNombreRiesgo(m)}`;

        const aviso = document.getElementById('jevMultiplicadorAviso');
        const pendiente = estado.multiplicador_pendiente;
        const segPendiente = pendiente ? Math.max(0, Math.ceil(pendiente.segundos_para_activar - transcurrido)) : 0;
        if (pendiente && segPendiente > 0) {
            aviso.className = 'small mt-1 text-info';
            aviso.textContent = `Cambio a x${pendiente.multiplicador} en ${segPendiente} s`;
        } else if (m >= 3) {
            aviso.className = 'small mt-1 text-danger fw-semibold';
            aviso.textContent = '⚠️ Riesgo extremo: todo vale el triple';
        } else if (m >= 2) {
            aviso.className = 'small mt-1 jev-texto-x2 fw-semibold';
            aviso.textContent = '⚠️ Riesgo alto: todo vale el doble';
        } else {
            aviso.textContent = '';
        }

        const activo = ['pendiente', 'en_curso'].includes(estado.estado);
        const restante = Math.max(0, Math.ceil(estado.cooldown.segundos_restantes - transcurrido));
        const puede = activo && !jev.ocupado && (estado.cooldown.puede_cambiar || restante === 0);
        const elegido = pendiente && segPendiente > 0 ? pendiente.multiplicador : m;
        const htmlRiesgos = estado.niveles_riesgo.map(n => {
            const actual = n.multiplicador === elegido;
            return `<button type="button" class="btn btn-sm jev-riesgo ${JuegoEnVivoSelector.claseBotonRiesgo(n.multiplicador, actual)}"
                        data-jev-riesgo="${n.multiplicador}" ${puede && !actual ? '' : 'disabled'}>x${n.multiplicador}<small>${escaparHtml(n.nombre)}</small></button>`;
        }).join('');
        // Solo se reemplazan los botones si cambió algo (si no, el tick de 1s podría "comerse" un click)
        const contRiesgos = document.getElementById('jevRiesgos');
        if (contRiesgos.dataset.html !== htmlRiesgos) {
            contRiesgos.dataset.html = htmlRiesgos;
            contRiesgos.innerHTML = htmlRiesgos;
            contRiesgos.querySelectorAll('[data-jev-riesgo]').forEach(b => b.addEventListener('click', () => jevCambiarRiesgo(Number(b.dataset.jevRiesgo))));
        }

        const barra = document.getElementById('jevCooldownBarra');
        const texto = document.getElementById('jevCooldownTexto');
        if (!activo) {
            barra.style.width = '0%'; texto.textContent = '';
        } else if (jev.ocupado) {
            texto.textContent = 'Aplicando cambio…';
        } else if (puede) {
            barra.style.width = '0%';
            texto.textContent = estado.cooldown.liberado_por_gol ? '¡Gol! Puedes cambiar el riesgo ahora.' : 'Puedes cambiar el riesgo (tarda 10 s en aplicarse).';
        } else {
            barra.style.width = `${Math.min(100, (restante / estado.cooldown_total_segundos) * 100)}%`;
            texto.textContent = `Próximo cambio en ${restante} s (o después de un gol)`;
        }
    }

    async function jevCambiarRiesgo(multiplicador) {
        if (!jev.estado || jev.ocupado) return;
        jev.ocupado = true; jevRenderRiesgo();
        try {
            const estado = await JuegoEnVivoSelector.pedir('PUT', `/live-game/sessions/${jev.estado.juego_id}/risk`, { multiplicador });
            jev.mensaje = { tipo: 'info', texto: estado.multiplicador_pendiente
                ? `Riesgo x${multiplicador} pedido: se aplica en ${estado.multiplicador_pendiente.segundos_para_activar} s.`
                : `Riesgo cambiado a x${multiplicador}.` };
            jev.ocupado = false;
            renderJuegoEnVivo(estado, { match_id: estado.juego_id });
        } catch (e) {
            jev.ocupado = false;
            jev.mensaje = { tipo: 'warning', texto: e.message };
            jevRenderCabecera(jev.estado); jevRenderRiesgo();
        }
        setTimeout(() => { jev.mensaje = null; if (jev.estado) jevRenderCabecera(jev.estado); }, 5000);
    }

    function jevTextoTransaccion(t) {
        const emoji = (t.evento_tipo || '').split(' ')[0];
        const base = t.multiplicador !== 1 ? ` <span class="text-muted">(${jevSigno(t.puntos_base)} × x${t.multiplicador})</span>` : '';
        return `<span class="text-muted">${Math.round(t.minuto ?? 0)}'</span> ${emoji} ${escaparHtml(t.descripcion)}${base}`;
    }

    function jevRenderFeed(estado) {
        const feed = document.getElementById('jevFeed');
        if (!estado.transacciones.length) {
            feed.innerHTML = '<div class="text-muted fst-italic">Todavía no hubo eventos que muevan tus puntos.</div>';
            return;
        }
        feed.innerHTML = estado.transacciones.slice().reverse().map(t => `
            <div class="jev-feed__item">
                <span class="jev-feed__texto">${jevTextoTransaccion(t)}</span>
                <span class="jev-feed__puntos ${t.puntos_netos > 0 ? 'text-success' : t.puntos_netos < 0 ? 'text-danger' : 'text-muted'}">${jevSigno(t.puntos_netos)}</span>
            </div>`).join('');
    }

    function jevMostrarToast(t) {
        if (!jevToastsCapa) {
            jevToastsCapa = document.createElement('div');
            jevToastsCapa.className = 'jev-toasts';
            document.body.appendChild(jevToastsCapa);
        }
        const toast = document.createElement('div');
        toast.className = `jev-toast ${t.puntos_netos > 0 ? 'jev-toast--positivo' : t.puntos_netos < 0 ? 'jev-toast--negativo' : ''}`;
        const emoji = (t.evento_tipo || '').split(' ')[0];
        toast.textContent = `${emoji} ${t.descripcion}: ${jevSigno(t.puntos_netos)} puntos${t.multiplicador !== 1 ? ` (x${t.multiplicador})` : ''}`;
        jevToastsCapa.appendChild(toast);
        setTimeout(() => { toast.style.transition = 'opacity .4s'; toast.style.opacity = '0'; setTimeout(() => toast.remove(), 450); }, 4000);
    }

    // Saldo por minuto: un punto por transacción (verde suma / rojo resta, más grande si fue gol)
    function jevRenderGrafico(estado) {
        const canvas = document.getElementById('jevGrafico');
        if (!canvas || typeof Chart === 'undefined') return;
        const puntos = [{ x: 0, y: estado.puntos_iniciales, t: null }].concat(
            estado.transacciones.map(t => ({ x: t.minuto ?? 0, y: t.saldo_resultante, t }))
        );
        const colores = puntos.map(p => !p.t ? '#b9c2cc' : p.t.puntos_netos >= 0 ? '#3ecf74' : '#e66767');
        const radios = puntos.map(p => p.t && (p.t.evento_tipo || '').startsWith('⚽') ? 5 : 2.5);
        const datos = puntos.map(({ x, y }) => ({ x, y }));
        if (jev.chart) {
            const ds = jev.chart.data.datasets;
            ds[0].data = datos; ds[0].pointBackgroundColor = colores; ds[0].pointRadius = radios;
            ds[1].data = [{ x: 0, y: estado.puntos_iniciales }, { x: Math.max(90, datos[datos.length - 1].x), y: estado.puntos_iniciales }];
            jev.chart.update('none');
            return;
        }
        jev.chart = new Chart(canvas, {
            type: 'line',
            data: { datasets: [
                { label: 'Saldo', data: datos, borderColor: '#3ecf74', backgroundColor: 'rgba(62, 207, 116, .12)', fill: true,
                  stepped: true, pointBackgroundColor: colores, pointBorderWidth: 0, pointRadius: radios, borderWidth: 2 },
                { label: 'Inicial', data: [{ x: 0, y: estado.puntos_iniciales }, { x: 90, y: estado.puntos_iniciales }],
                  borderColor: 'rgba(185, 194, 204, .45)', borderDash: [4, 4], pointRadius: 0, borderWidth: 1 },
            ] },
            options: {
                responsive: true, maintainAspectRatio: false, animation: false,
                plugins: { legend: { display: false }, tooltip: { callbacks: {
                    title: items => `${Math.round(items[0].parsed.x)}'`,
                    label: item => item.datasetIndex === 0 ? `Saldo: ${jevPuntos(item.parsed.y)}` : `Inicial: ${jevPuntos(item.parsed.y)}`,
                } } },
                scales: {
                    x: { type: 'linear', min: 0, suggestedMax: 90, ticks: { color: '#8b949e', callback: v => `${v}'` }, grid: { color: 'rgba(255,255,255,.05)' } },
                    y: { beginAtZero: true, ticks: { color: '#8b949e' }, grid: { color: 'rgba(255,255,255,.05)' } },
                },
            },
        });
    }

    // Resumen final (en el panel cuando la transmisión termina, y en el panel inactivo después)
    function jevRenderResumen(contenedor, estado) {
        if (!contenedor) return;
        const r = estado && estado.resumen;
        if (!r) { contenedor.innerHTML = ''; return; }
        const neto = r.puntos_finales - (estado.entrada_monto || 0);
        const rp = r.ranking_partido || {}, rt = r.ranking_torneo || {};
        const destacados = (r.eventos_destacados || []).map(t => `
            <div class="jev-feed__item"><span class="jev-feed__texto">${jevTextoTransaccion(t)}</span>
            <span class="jev-feed__puntos ${t.puntos_netos >= 0 ? 'text-success' : 'text-danger'}">${jevSigno(t.puntos_netos)}</span></div>`).join('')
            || '<div class="text-muted fst-italic">Ningún evento movió tus puntos.</div>';
        contenedor.innerHTML = `
            <div class="border-top border-secondary mt-3 pt-3 text-white">
                <h6 class="fw-bold mb-3">🏁 Resumen de tu partida · ${escaparHtml(estado.pais_nombre)} vs ${escaparHtml(estado.rival_nombre)}</h6>
                <div class="row g-2 text-center mb-3">
                    <div class="col-6 col-md-3"><div class="small text-muted">Puntos iniciales</div><div class="jev-resumen-cifra">${jevPuntos(r.puntos_iniciales)}</div></div>
                    <div class="col-6 col-md-3"><div class="small text-muted">Puntos finales</div><div class="jev-resumen-cifra">${jevPuntos(r.puntos_finales)}</div></div>
                    <div class="col-6 col-md-3"><div class="small text-muted">Ganado / perdido</div>
                        <div class="jev-resumen-cifra ${r.neto >= 0 ? 'text-success' : 'text-danger'}">${jevSigno(r.neto)}</div></div>
                    <div class="col-6 col-md-3"><div class="small text-muted">Riesgo máximo</div><div class="jev-resumen-cifra">x${r.multiplicador_maximo}</div></div>
                </div>
                <p class="small mb-2">💰 Se acreditaron <strong>${jevPuntos(r.monto_acreditado)}</strong> a tu saldo
                    (entrada ${jevPuntos(estado.entrada_monto)} → <span class="${neto >= 0 ? 'text-success' : 'text-danger'}">${jevSigno(neto)}</span>).</p>
                <p class="small mb-2">🏆 Ranking del partido: <strong>#${rp.posicion ?? '-'}</strong> de ${rp.total ?? 0}
                    · Ranking del torneo: <strong>#${rt.posicion ?? '-'}</strong> de ${rt.total ?? 0}</p>
                <div class="small text-muted mb-1">Eventos que más te impactaron</div>
                <div class="jev-feed">${destacados}</div>
            </div>`;
    }

    // Fuera de transmisión: resumen del último partido visto + selector del próximo
    async function mostrarJuegoEnVivoInactivo() {
        if (!JEV_HABILITADO || !jevProximo) return;
        if (jevPanel) jevPanel.classList.add('d-none');
        if (jev.ultimoMatchVisto) {
            try {
                const estado = await JuegoEnVivoSelector.pedir('GET', `/live-game/state?juego_id=${encodeURIComponent(jev.ultimoMatchVisto)}`);
                if (estado.modo === 'jugador' && estado.resumen) {
                    jevResumenInactivo.classList.remove('d-none');
                    jevRenderResumen(jevResumenInactivo, estado);
                }
            } catch (e) { /* sin resumen */ }
        }
        jevMostrarProximo(jevProximo, jevProximoTitulo, jevProximoSelector);
    }

    // Selector de país del próximo partido (el que va a tomar "Simular siguiente")
    async function jevMostrarProximo(caja, titulo, contenedor) {
        if (!JEV_HABILITADO || !caja) return;
        try {
            const datos = await JuegoEnVivoSelector.pedir('GET', '/live-game/next');
            titulo.textContent = `${datos.local.nombre} vs ${datos.visitante.nombre}`;
            JuegoEnVivoSelector.render(contenedor, datos);
            caja.classList.remove('d-none');
        } catch (e) {
            caja.classList.add('d-none');
        }
    }

    async function consultarEstado() {
        try {
            const resp = await fetch('/matches/live');
            if (resp.status === 404) {
                mostrarInactivo();
                return;
            }
            if (!resp.ok) {
                throw new Error('No se pudo consultar el estado en vivo.');
            }
            const data = await resp.json();
            await renderEnVivo(data);
            actualizarJuegoEnVivo(data); // sin await: el juego no demora ni rompe la transmisión
        } catch (e) {
            mostrarInactivo('Ocurrió un error al consultar la transmisión.');
        }
    }

    const RECONSULTA_INACTIVO_MS = 10000;
    let reconsultaInactivoId = null;
    function programarReconsultaInactivo() {
        if (reconsultaInactivoId) return;
        reconsultaInactivoId = setTimeout(async () => {
            reconsultaInactivoId = null;
            try {
                const resp = await fetch('/matches/live');
                if (resp.ok) iniciarPolling();       // empezó un partido: polling normal
                else programarReconsultaInactivo();  // sigue sin partido
            } catch (e) {
                programarReconsultaInactivo();
            }
        }, RECONSULTA_INACTIVO_MS);
    }

    function iniciarPolling() {
        consultarEstado();
        detenerPolling();
        pollHandle = setInterval(consultarEstado, POLL_MS);
    }

    async function simularSiguiente(boton) {
        // Si esto se disparó por click manual mientras había una cuenta regresiva de la
        // reproducción automática esperando, se cancela -- ya se está simulando "ahora".
        cancelarAutoPlayProgramado();
        errorSimular.classList.add('d-none');
        boton.disabled = true;
        try {
            const resp = await fetch('/matches/simulate-next-auto', { method: 'POST' });
            const data = await resp.json();
            if (!resp.ok) {
                if (resp.status === 401 && autoPlayActivo) {
                    autoPlayActivo = false;
                    if (toggleAutoPlay) toggleAutoPlay.checked = false;
                    guardarAutoPlay(false);
                }
                throw new Error(data.detail || 'No se pudo iniciar la simulación.');
            }
            if (!data.encontrado) {
                // Torneo terminado -- no queda nada para encadenar, se apaga la reproducción
                // automática para no reintentar cada 10s indefinidamente sin sentido.
                if (autoPlayActivo) {
                    autoPlayActivo = false;
                    if (toggleAutoPlay) toggleAutoPlay.checked = false;
                    guardarAutoPlay(false);
                }
                mostrarInactivo(data.mensaje || 'No hay partidos pendientes por simular.');
                return;
            }
            iniciarPolling();
        } catch (e) {
            errorSimular.textContent = e.message;
            errorSimular.classList.remove('d-none');
            // Reintento automático tras la misma pausa, si la reproducción automática sigue activa.
            if (autoPlayActivo) programarAutoPlay(boton);
        } finally {
            boton.disabled = false;
        }
    }

    if (btnSimular) {
        btnSimular.addEventListener('click', () => simularSiguiente(btnSimular));
    }
    if (btnSimularOtro) {
        btnSimularOtro.addEventListener('click', () => simularSiguiente(btnSimularOtro));
    }

    if (toggleAutoPlay) {
        toggleAutoPlay.addEventListener('change', function () {
            autoPlayActivo = toggleAutoPlay.checked;
            guardarAutoPlay(autoPlayActivo);
            actualizarVisibilidadBotonSimular();
            if (!autoPlayActivo) {
                cancelarAutoPlayProgramado();
                return;
            }
            // Si se prende mientras ya se está en la pausa entre partidos (inactivo o recién
            // finalizado), arranca la cuenta regresiva ahora mismo; si el partido sigue en vivo,
            // no hay nada que programar todavía -- se hace solo cuando termine.
            if (!panelInactivo.classList.contains('d-none') && btnSimular) {
                programarAutoPlay(btnSimular);
            } else if (!panelFinalizado.classList.contains('d-none') && btnSimularOtro) {
                programarAutoPlay(btnSimularOtro);
            }
        });
    }

    // Al cargar la página: si ya hay un partido en curso (arrancado por otra pestaña/usuario),
    // lo detecta solo y empieza a pollear sin que haga falta tocar el botón.
    consultarEstado().then(() => {
        if (!panelEnVivo.classList.contains('d-none') && !pollHandle) {
            pollHandle = setInterval(consultarEstado, POLL_MS);
        }
    });
});
