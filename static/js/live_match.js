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

    // Reproducción automática EN EL SERVIDOR (services/pulso_service.py): Cloud Scheduler da un "pulso" por minuto que
    // cierra la transmisión terminada y arranca la siguiente a su hora, aunque nadie tenga la página abierta. Aquí solo
    // se muestra y se configura (interruptor + ritmo, para quien puede simular) y se cuenta la espera hasta el próximo
    // partido. El navegador de un admin da además un pulso de respaldo cuando llega la hora (POST /matches/pulso/tick):
    // el servidor decide igual que siempre, así que nunca adelanta ni duplica un partido.
    const toggleAutoPlay = document.getElementById('toggleAutoPlay');
    const selectRitmo = document.getElementById('selectRitmo');
    const autoPlayEstado = document.getElementById('autoPlayEstado');
    const textoEsperaEspectador = document.getElementById('textoEsperaEspectador');
    let autoPlayActivo = false;
    let pulso = null;                 // último GET /matches/pulso
    let autoPlayIntervalId = null;    // cuenta regresiva en pantalla
    let respaldoEnviado = 0;          // último pulso de respaldo (ms)
    try { localStorage.removeItem('futbolsim_autoplay_live'); } catch (e) {}   // el interruptor viejo vivía en el navegador

    const horaLocal = iso => new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const faltaTexto = ms => {
        const s = Math.max(0, Math.round(ms / 1000)), m = Math.floor(s / 60);
        return m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m}:${String(s % 60).padStart(2, '0')}`;
    };

    function aplicarPulso(datos) {
        pulso = datos || pulso;
        if (!pulso) return;
        autoPlayActivo = !!pulso.activo;
        if (toggleAutoPlay) { toggleAutoPlay.checked = autoPlayActivo; toggleAutoPlay.disabled = false; }
        if (selectRitmo) { selectRitmo.value = String(pulso.intervalo_min); selectRitmo.disabled = false; }
        if (textoEsperaEspectador) {
            textoEsperaEspectador.textContent = autoPlayActivo
                ? `Los partidos arrancan solos: uno cada ${pulso.intervalo_min} minutos. Esta página se actualiza sola.`
                : 'El próximo partido empieza cuando un administrador lo ponga en marcha. Esta página se actualiza sola.';
        }
        actualizarVisibilidadBotonSimular();
    }

    async function cargarPulso() {
        try {
            const r = await fetch('/matches/pulso');
            if (r.ok) aplicarPulso(await r.json());
        } catch (e) { /* sin red: se reintenta en la próxima espera */ }
        return pulso;
    }

    async function guardarPulso(cambios) {
        const r = await fetch('/matches/pulso/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(cambios) });
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.detail || 'No se pudo guardar la reproducción automática.');
        aplicarPulso(d);
    }

    // Con la reproducción automática prendida, "Simular siguiente partido" sobra (arranca solo a su hora)
    function actualizarVisibilidadBotonSimular() {
        if (btnSimular) btnSimular.classList.toggle('d-none', autoPlayActivo);
        if (btnSimularOtro) btnSimularOtro.classList.toggle('d-none', autoPlayActivo);
    }

    function cancelarAutoPlayProgramado() {
        if (autoPlayIntervalId) { clearInterval(autoPlayIntervalId); autoPlayIntervalId = null; }
        if (autoPlayEstado) autoPlayEstado.classList.add('d-none');
    }

    // Entre partidos: cuenta regresiva hasta la hora del próximo (para todos). Al llegar, el admin da un pulso de
    // respaldo y todos vuelven a consultar la transmisión.
    async function programarAutoPlay() {
        if (autoPlayIntervalId || !autoPlayEstado) return;
        await cargarPulso();
        if (!pulso || !pulso.activo || !pulso.proximo_inicio) { cancelarAutoPlayProgramado(); return; }
        const objetivo = new Date(pulso.proximo_inicio).getTime();
        const pintar = () => {
            const falta = objetivo - Date.now();
            autoPlayEstado.innerHTML = falta > 0
                ? `<i class="bi bi-clock-history"></i><span>Próximo partido a las <b>${horaLocal(pulso.proximo_inicio)}</b> · faltan <b>${faltaTexto(falta)}</b></span><small>Un partido cada ${pulso.intervalo_min} min · el torneo sigue aunque cierres el navegador</small>`
                : `<i class="bi bi-broadcast"></i><span>Arrancando el próximo partido…</span><small>Un partido cada ${pulso.intervalo_min} min</small>`;
            return falta;
        };
        pintar();
        autoPlayEstado.classList.remove('d-none');
        autoPlayIntervalId = setInterval(async () => {
            if (pintar() > 0) return;
            // Llegó la hora: el pulso del servidor lo arranca en menos de un minuto; el admin además da uno de respaldo
            if (window.LIVE_CONFIG.puedeSimular && Date.now() - respaldoEnviado > 20000) {
                respaldoEnviado = Date.now();
                try { aplicarPulso(await (await fetch('/matches/pulso/tick', { method: 'POST' })).json()); } catch (e) {}
            }
            if (Date.now() % 10000 < 1000) consultarEstado();   // cada ~10 s: ¿ya arrancó?
        }, 1000);
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
        programarAutoPlay();
        mostrarJuegoEnVivoInactivo();
        // Sin permiso para simular no hay botón: se sigue consultando (más espaciado) para que
        // la transmisión aparezca sola cuando un administrador arranque el próximo partido.
        if (!btnSimular) programarReconsultaInactivo();
    }

    // Minuto con tiempo añadido ("90+3"): los partidos nuevos traen 'periodo'/'adicional' (services/arbitraje.py)
    function minutoTexto(ev) {
        const m = Math.round(ev.minuto || 0);
        return ev.adicional ? `${m}+${ev.adicional}` : `${m}`;
    }
    function esDeTanda(ev) {
        return ev.periodo === 5 || (!ev.periodo && ev.minuto == 120 && (ev.tipo || '').includes('PENAL'));
    }
    function badgeMinuto(evento) {
        if (esDeTanda(evento)) return '<span class="badge bg-danger rounded-pill me-3 fs-6">PEN</span>';
        if (evento.tipo.includes('VAR')) return `<span class="badge bg-dark text-accent border rounded-pill me-3 fs-6">'${minutoTexto(evento)}</span>`;
        if ((evento.periodo || 0) >= 3 || (!evento.periodo && evento.minuto > 90)) return `<span class="badge bg-warning text-dark rounded-pill me-3 fs-6">'${minutoTexto(evento)}</span>`;
        if (evento.adicional) return `<span class="badge bg-info text-dark rounded-pill me-3 fs-6">'${minutoTexto(evento)}</span>`;
        return `<span class="badge bg-primary rounded-pill me-3 fs-6">'${minutoTexto(evento)}</span>`;
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

    // Cronología: cada evento con su categoría (color/peso visual) y el lado del equipo. Los
    // eventos de "relleno" (transición, preparación, presión; ~70% del total) se marcan para que el
    // filtro "Jugadas clave" (por defecto) los oculte vía CSS sin volver a renderizar.
    const TIPOS_RELLENO = ['EN TRANSICIÓN', 'PREPARACIÓN', 'PRESIÓN DEFENSIVA'];
    // Lesión (services/lesiones.py): con 'sin_cambio' el lesionado se va y su equipo queda con uno menos; si hubo
    // cambio, el '🔄 SUSTITUCIÓN' que sigue ya lo saca
    const EVENTO_LESION = '🚑 LESIÓN';
    const TIPOS_DT = ['🗣️ RECLAMO DEL DT', '🟨 DT AMONESTADO', '🟥 DT EXPULSADO', '📋 AJUSTE TÁCTICO'];
    const saleSinCambio = ev => ev.tipo === EVENTO_LESION && ev.sin_cambio;
    function categoriaEvento(tipo) {
        const t = tipo || '';
        if (t === '🟥 DT EXPULSADO') return 'dt-roja';
        if (t === '🟨 DT AMONESTADO') return 'dt-amarilla';
        if (t === '🗣️ RECLAMO DEL DT' || t === '📋 AJUSTE TÁCTICO') return 'dt';
        if (t.includes('ANULADO')) return 'var';
        if (t.includes('GOL')) return 'gol';
        if (t.includes('ROJA')) return 'roja';
        if (t.includes('AMARILLA')) return 'amarilla';
        if (t.includes('SUSTITUCIÓN')) return 'cambio';
        if (t === EVENTO_LESION) return 'lesion';
        if (t.includes('ATAJADA') || t.includes('DISPARO') || t.includes('CÓRNER') || t.includes('TIRO LIBRE') || t.includes('ERROR')) return 'ocasion';
        if (t.includes('SILBATO') || t.includes('PITIDO') || t.includes('FINAL DEL') || t.includes('SAQUE DE CENTRO')) return 'hito';
        if (TIPOS_RELLENO.some(r => t.includes(r))) return 'relleno';
        return 'jugada';
    }
    const contadorEventos = document.getElementById('contadorEventos');
    document.querySelectorAll('[data-filtro-cronologia]').forEach(boton => boton.addEventListener('click', () => {
        document.querySelectorAll('[data-filtro-cronologia]').forEach(b => b.classList.toggle('active', b === boton));
        listaEventos.classList.toggle('cronologia--clave', boton.dataset.filtroCronologia === 'clave');
    }));

    function festejarMascota() {
        let nodo = document.getElementById('mascotaFestejo');
        if (!nodo) {
            nodo = document.createElement('div');
            nodo.id = 'mascotaFestejo';
            nodo.className = 'mascota-festejo';
            nodo.setAttribute('aria-hidden', 'true');
            nodo.innerHTML = `<span class="mascota-festejo__globo"></span><img alt="" src="${UI.escapar(mascota.url)}">`;
            document.body.appendChild(nodo);
        }
        nodo.querySelector('.mascota-festejo__globo').textContent = `¡GOOOL de ${mascota.anfitrion}!`;
        nodo.classList.remove('mascota-festejo--activa');
        void nodo.offsetWidth;   // reinicia la animación si hay dos goles seguidos
        nodo.classList.add('mascota-festejo--activa');
    }

    let cronologiaUltimoTotal = 0;
    let cronologiaMatchId = null;
    function renderEventos(eventos, nombreEquipoLocal, nombreEquipoVisitante, matchId) {
        // Solo los eventos que no estaban en el poll anterior se animan (el innerHTML se rehace cada 3 s)
        if (cronologiaMatchId !== matchId) { cronologiaMatchId = matchId; cronologiaUltimoTotal = 0; }
        const totalAnterior = cronologiaUltimoTotal;
        cronologiaUltimoTotal = (eventos || []).length;
        if (!eventos || eventos.length === 0) {
            listaEventos.innerHTML = '<div class="text-muted text-center py-3">Esperando el primer evento del partido...</div>';
            if (contadorEventos) contadorEventos.textContent = '';
            return;
        }
        // Gol del anfitrión entre los eventos nuevos de este poll (no al abrir la página): la mascota sale a festejar
        if (totalAnterior > 0 && mascota && eventos.slice(totalAnterior).some(ev => (ev.tipo || '').startsWith('⚽') && ev.equipo === mascota.anfitrion)) {
            festejarMascota();
        }
        let claves = 0;
        // Del más reciente al más antiguo, igual que una transmisión real
        const items = eventos.slice().reverse().map((evento, i) => {
            const categoria = categoriaEvento(evento.tipo);
            if (categoria !== 'relleno') claves += 1;
            const lado = evento.equipo === nombreEquipoLocal ? 'local' : (evento.equipo === nombreEquipoVisitante ? 'visitante' : 'neutral');
            const nuevo = totalAnterior > 0 && i < eventos.length - totalAnterior;
            return `
            <div class="evento evento--${categoria} evento--${lado}${nuevo ? ' evento--nuevo' : ''}">
                ${badgeMinuto(evento)}
                <div class="evento__cuerpo">
                    <div class="evento__tipo">${evento.tipo}${evento.equipo ? ` <span class="evento__equipo">${escaparHtml(evento.equipo)}</span>` : ''}${evento.especialidad_nombre ? ` <span class="evento__especialidad" title="La especialidad del jugador decidió la jugada"><i class="bi bi-stars"></i> ${escaparHtml(evento.especialidad_nombre)}</span>` : ''}</div>
                    <div class="evento__texto">${resaltarJugadores(evento.descripcion, evento.jugadores)}</div>
                </div>
            </div>`;
        }).join('');
        listaEventos.innerHTML = items;
        if (contadorEventos) contadorEventos.textContent = `${claves} clave · ${eventos.length}`;
    }

    // Marcador estilo TV: banderas, siglas, escudos de marca de agua y la ilustración del estadio.
    // Las imágenes solo se cargan cuando cambia el partido (el polling de 3 s no las vuelve a pedir).
    let marcadorTvMatchId = null;
    function ponerImagen(id, url) {
        const img = document.getElementById(id);
        if (!img) return;
        if (!url) { img.classList.add('d-none'); return; }
        img.onerror = () => img.classList.add('d-none');
        img.src = url;
        img.classList.remove('d-none');
    }
    function renderMarcadorTv(data) {
        if (marcadorTvMatchId === data.match_id) return;
        marcadorTvMatchId = data.match_id;
        const url = (id, tipo) => (id && window.UI && UI.urlImagenPais) ? UI.urlImagenPais(id, tipo) : null;
        ponerImagen('marcadorBanderaLocal', url(data.id_local, 'bandera'));
        ponerImagen('marcadorBanderaVisitante', url(data.id_visita, 'bandera'));
        ponerImagen('marcadorEscudoLocal', url(data.id_local, 'escudo'));
        ponerImagen('marcadorEscudoVisitante', url(data.id_visita, 'escudo'));
        ponerImagen('marcadorEstadio', data.estadio_img);
        const siglasL = document.getElementById('marcadorSiglasLocal');
        const siglasV = document.getElementById('marcadorSiglasVisitante');
        if (siglasL) siglasL.textContent = data.siglas_local || '';
        if (siglasV) siglasV.textContent = data.siglas_visitante || '';
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
    let canchaIds = {};
    let canchaLeyendas = new Set();
    let mascota = null;   // {anfitrion, url, nombre}: festeja los goles del anfitrión (arte_mundial_service)
    let canchaLineasLocal = [];
    let canchaLineasVisitante = [];
    // En qué top 10 / premios de /estadisticas están los jugadores y las selecciones del partido
    // (GET /matches/live/destacados, una vez por partido; es el estado PREVIO al partido)
    let canchaDestacados = { jugadores: {}, paises: { local: [], visitante: [] } };
    let canchaDestacadosMatchId = null;

    async function actualizarDestacadosSiCorresponde(matchId) {
        if (!matchId || matchId === canchaDestacadosMatchId) return;
        canchaDestacadosMatchId = matchId;   // se marca antes: la primera vez puede tardar unos segundos
        try {
            const resp = await fetch('/matches/live/destacados');
            if (!resp.ok) { canchaDestacadosMatchId = null; return; }
            const data = await resp.json();
            canchaDestacados = { jugadores: data.jugadores || {}, paises: data.paises || { local: [], visitante: [] } };
        } catch (e) {
            canchaDestacadosMatchId = null;   // se reintenta en el próximo poll
        }
    }

    // ---------------------------------------------------------------------------------------
    // Lo que está en juego (GET /matches/live/interes): se pide una vez por partido y se re-pinta en cada poll con el
    // marcador YA REVELADO ("así como va"), así nunca adelanta el resultado.
    // ---------------------------------------------------------------------------------------
    let interesVivo = null, interesMatchId = null;
    const interesCaja = document.getElementById('interesVivo');
    async function actualizarInteresSiCorresponde(matchId) {
        if (!matchId || matchId === interesMatchId) return;
        interesMatchId = matchId;
        interesVivo = null;
        try {
            const resp = await fetch('/matches/live/interes');
            if (!resp.ok) { interesMatchId = null; return; }
            interesVivo = await resp.json();
        } catch (e) { interesMatchId = null; }
    }
    const ESTADO_TEXTO = { clasificado: 'clasificado', eliminado: 'eliminado', depende: 'depende de sí', necesita: 'necesita ayuda' };
    function renderInteresVivo(data) {
        if (!interesCaja) return;
        const iv = interesVivo;
        if (!iv || iv.match_id !== data.match_id || !(iv.chips.length || iv.escenarios || iv.serie)) { interesCaja.classList.add('d-none'); return; }
        const gl = Number(data.goles_local) || 0, gv = Number(data.goles_visitante) || 0;
        const fin = !!data.finalizado;
        const prefijo = fin ? 'Final' : 'Así como va';
        const e = escaparHtml;
        let vivoHtml = '';
        if (iv.escenarios) {
            const filas = ['local', 'visita'].filter(l => iv.escenarios[l]).map(lado => {
                const esc = iv.escenarios[lado];
                const res = lado === 'local' ? (gl > gv ? 'gana' : gl === gv ? 'empata' : 'pierde') : (gv > gl ? 'gana' : gl === gv ? 'empata' : 'pierde');
                const ahora = esc.por_resultado[res];
                const cambia = ahora.codigo !== esc.hoy.codigo;
                const nombre = lado === 'local' ? iv.local : iv.visita;
                const clave = ahora.codigo === 'clasificado' || ahora.codigo === 'eliminado';
                return `<div class="iv-equipo iv-equipo--${ahora.codigo} ${cambia && clave ? 'iv-equipo--alerta' : ''}">
                    <span class="iv-equipo__nombre">${UI.bandera('', { id: iv.ids[lado] })} ${e(nombre)}</span>
                    <span class="iv-equipo__antes">Antes: ${e(ESTADO_TEXTO[esc.hoy.codigo] || esc.hoy.texto)}</span>
                    <span class="iv-equipo__ahora"><small>${prefijo}</small><strong>${e((ESTADO_TEXTO[ahora.codigo] || ahora.texto).replace(/^./, c => c.toUpperCase()))}</strong></span>
                </div>`;
            });
            if (filas.length) vivoHtml = `<div class="iv-vivo">${filas.join('')}</div>`;
        } else if (iv.serie) {
            let tl = gl, tv = gv, texto;
            if (iv.serie.tipo === 'vuelta' && iv.serie.ida) { tl += Number(iv.serie.ida.goles_local) || 0; tv += Number(iv.serie.ida.goles_visita) || 0; }
            const global = iv.serie.tipo === 'vuelta' && iv.serie.ida ? ` <small>(global ${tl}-${tv})</small>` : '';
            if (tl !== tv) texto = `${prefijo}, avanza <strong>${e(tl > tv ? iv.local : iv.visita)}</strong>${global}`;
            else texto = fin ? `Empate${global}: se definió en el alargue o los penales` : `${prefijo}: empate${global}, se iría al alargue`;
            vivoHtml = `<div class="iv-serie"><i class="bi bi-arrow-left-right"></i><span>${texto}</span></div>`;
        }
        const chips = iv.chips.map(c => `<li class="motivo motivo--${e(c.tipo)}"><i class="bi ${e(c.icono)}"></i><span>${e(c.texto)}</span></li>`).join('');
        interesCaja.innerHTML = `
            <div class="iv__cabecera">
                <span class="iv__titulo"><i class="bi bi-binoculars-fill"></i>Lo que está en juego</span>
                ${iv.nivel ? `<span class="partido-card__nivel partido-card__nivel--${e(iv.nivel.codigo)} iv__nivel"><i class="bi ${e(iv.nivel.icono)}"></i>${e(iv.nivel.texto)}</span>` : ''}
            </div>
            ${vivoHtml}
            ${chips ? `<ul class="iv__motivos">${chips}</ul>` : ''}`;
        interesCaja.classList.remove('d-none');
    }

    let canchaLineasIniciales = { local: [], visitante: [] };
    let canchaFormaciones = {};     // esquema -> línea de cada puesto (para el cambio de esquema en vivo)
    let canchaPlanteamiento = {};   // {local|visita: {esquema, etiqueta, postura, motivo}}
    let canchaEspejo = {};          // {local|visita: bool}: qué extremo va de segundo delantero

    // Esquema vigente de un lado según los ajustes ya revelados (📋 AJUSTE TÁCTICO con esquema_a): la cancha se reacomoda
    function esquemaVigente(lado, data) {
        const plan = canchaPlanteamiento[lado === 'local' ? 'local' : 'visita'] || {};
        const nombre = lado === 'local' ? data.local : data.visitante;
        const cambios = (data.eventos || []).filter(ev => ev.tipo === '📋 AJUSTE TÁCTICO' && ev.equipo === nombre && ev.esquema_a);
        return cambios.length ? cambios[cambios.length - 1].esquema_a : plan.esquema;
    }

    function actualizarLineasPorEsquema(data) {
        ['local', 'visitante'].forEach(lado => {
            const esq = esquemaVigente(lado, data);
            let lineas = (esq && canchaFormaciones[esq]) || canchaLineasIniciales[lado];
            // El extremo que juega arriba se sortea por partido (services/formaciones.lineas): EI (puesto 9) y ED (11)
            if (esq && canchaFormaciones[esq] && canchaEspejo[lado === 'local' ? 'local' : 'visita']) {
                lineas = lineas.slice();
                [lineas[8], lineas[10]] = [lineas[10], lineas[8]];
            }
            if (lado === 'local') canchaLineasLocal = lineas; else canchaLineasVisitante = lineas;
        });
    }
    let canchaArbitros = {};   // cuerpo arbitral con su rostro (/matches/live/plantillas): {rol: {nombre, url}}
    let canchaDT = {};   // DT de cada lado (/matches/live/plantillas): {local|visita: {id, nombre, estilo, arquetipo, avatar_url, record}}

    // Fila del DT al tope de "Jugadores en Cancha": lo que hizo desde el banco sale SOLO de los eventos ya revelados
    function renderFilaDT(lado, data) {
        const dt = canchaDT[lado === 'local' ? 'local' : 'visita'];
        if (!dt) return null;
        const propios = (data.eventos || []).filter(ev => ev.dt_id === dt.id);
        const ajustes = propios.filter(ev => ev.tipo === '📋 AJUSTE TÁCTICO');
        const reclamos = propios.filter(ev => ev.tipo === '🗣️ RECLAMO DEL DT').length;
        const amonestado = propios.find(ev => ev.tipo === '🟨 DT AMONESTADO');
        const expulsado = propios.find(ev => ev.tipo === '🟥 DT EXPULSADO');
        const ultimoAjuste = ajustes.length ? ajustes[ajustes.length - 1] : null;
        const textoAjuste = { ataque: 'Al ataque', cerrar: 'Cerrojo', normal: 'Plan inicial' };
        const iconos = [];
        const plan = canchaPlanteamiento[lado === 'local' ? 'local' : 'visita'];
        const esqAhora = esquemaVigente(lado, data);
        if (plan && plan.esquema) {
            const cambio = esqAhora && esqAhora !== plan.esquema;
            iconos.push(`<span class="once-ico once-dt__esquema ${cambio ? 'once-dt__esquema--cambio' : ''}" title="${escaparHtml(plan.motivo || '')}">🧩 ${escaparHtml(plan.esquema)}${cambio ? ` → <b>${escaparHtml(esqAhora)}</b>` : ` <small>${escaparHtml(plan.etiqueta || '')}</small>`}</span>`);
        }
        if (ultimoAjuste) iconos.push(`<span class="once-ico once-dt__ajuste once-dt__ajuste--${escaparHtml(ultimoAjuste.ajuste || 'normal')}" title="Ajuste táctico en el ${minutoTexto(ultimoAjuste)}">📋 ${escaparHtml(textoAjuste[ultimoAjuste.ajuste] || 'Ajuste')}<small>${minutoTexto(ultimoAjuste)}</small></span>`);
        if (reclamos) iconos.push(`<span class="once-ico" title="${reclamos} reclamo${reclamos > 1 ? 's' : ''}">🗣️${reclamos > 1 ? `<small>×${reclamos}</small>` : ''}</span>`);
        if (amonestado && !expulsado) iconos.push(`<span class="once-ico" title="Amonestado en el ${minutoTexto(amonestado)}">🟨<small>${minutoTexto(amonestado)}</small></span>`);
        if (expulsado) iconos.push(`<span class="once-ico" title="Expulsado en el ${minutoTexto(expulsado)}">🟥<small>${minutoTexto(expulsado)}</small></span>`);
        const fila = document.createElement('div');
        fila.className = `list-group-item bg-dark text-white p-0 border-secondary border-opacity-10 small once-dt${expulsado ? ' once-dt--expulsado' : ''}`;
        fila.innerHTML = `
            <a href="/tecnicos/${dt.id}" target="_blank" rel="noopener" class="once-fila once-dt__fila d-flex justify-content-between align-items-center py-1 px-3 text-decoration-none text-white">
                <span class="d-flex align-items-center gap-2" style="min-width: 0;">
                    <span class="once-dt__avatar">${dt.avatar_url ? `<img src="${escaparHtml(dt.avatar_url)}" alt="" onerror="this.remove()">` : '<i class="bi bi-person-workspace"></i>'}<b>DT</b></span>
                    <span class="d-flex flex-column" style="min-width: 0;">
                        <span class="text-truncate fw-semibold">${escaparHtml(dt.nombre)} <span class="text-muted fw-normal">· ${escaparHtml(dt.estilo || 'DT')}</span></span>
                        <span class="once-iconos">${expulsado ? '<span class="once-dt__tribuna">En la tribuna: dirige el ayudante</span>' : `<span class="once-dt__arquetipo">${escaparHtml(dt.arquetipo || '')}</span>`}${iconos.join('')}</span>
                    </span>
                </span>
                <span class="badge rounded-pill once-dt__record" title="Récord en el cargo antes de este partido">${escaparHtml(dt.record)}</span>
            </a>`;
        return fila;
    }

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
            canchaIds = data.ids || {};
            canchaLeyendas = new Set(data.leyendas || []);
            canchaDT = data.dt || {};
            canchaArbitros = data.arbitros || {};
            mascota = data.mascota_url ? { anfitrion: data.anfitrion, url: data.mascota_url, nombre: data.mascota_nombre } : null;
            canchaLineasLocal = data.lineas_local || [];
            canchaLineasVisitante = data.lineas_visitante || [];
            canchaLineasIniciales = { local: canchaLineasLocal, visitante: canchaLineasVisitante };
            canchaFormaciones = data.formaciones || {};
            canchaPlanteamiento = data.planteamiento || {};
            canchaEspejo = data.espejo_extremos || {};
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
    // equipo se trate -- no hay un "lado" físico fijo de cancha en el motor de simulación. Aquí
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
    // '🧤 ATAJADA ESPECTACULAR' / '🖐️ DESVÍO A CÓRNER' / '❌ PENAL FALLADO' entraron aquí porque
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
        if (evento.balon && evento.balon.l != null) return evento.balon.l === 1;   // recorrido nuevo: lo dice el motor
        const esEquipoLocal = esCanchaEquipoLocal(evento.equipo);
        return CANCHA_TIPOS_EQUIPO_DEFENSOR.has(evento.tipo) ? !esEquipoLocal : esEquipoLocal;
    }

    function canchaPosicionVisual(evento) {
        if (evento.balon) return { x: evento.balon.d[0], y: evento.balon.d[1] };   // ya absolutas (services/balon.py)
        const { x, y } = evento.posicion_balon;
        return { x: esCanchaAtacanteLocal(evento) ? x : (100 - x), y };
    }

    // x llega 0-100 (mapea directo a left% del balón) pero el viewBox del SVG es 105 de ancho
    // (dimensiones reales de cancha en metros) -- se reescala solo para el trazo. y ya es 0-68,
    // coincide 1 a 1 con el alto del viewBox.
    function canchaXaSvg(x) { return (x / 100) * 105; }

    // ---------------------------------------------------------------------------------------
    // Jugadores en la Cancha en Vivo: 22 fichas (jersey de la selección con el dorsal) que se reacomodan con
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
        '👉 SILBATO INICIAL', '🚩 FINAL DEL PRIMER TIEMPO', '⏱️ TIEMPO EXTRA', '🥅 TANDA DE PENALTIS', '🏁 PITIDO FINAL',
        '⏱️ TIEMPO AÑADIDO', '🔵 COMIENZA EL SEGUNDO TIEMPO', '🔵 SEGUNDO TIEMPO EXTRA', '🖥️ REVISIÓN VAR',
        '🚩 SAQUE DE ESQUINA', '🎯 PENAL',
        '🗣️ RECLAMO DEL DT', '🟨 DT AMONESTADO', '🟥 DT EXPULSADO', '📋 AJUSTE TÁCTICO', '🚑 LESIÓN'
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
            } else if ((CANCHA_TIPOS_EXPULSION.has(ev.tipo) || saleSinCambio(ev)) && jugadores.length >= 1) {
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
        // Con el recorrido nuevo los protagonistas los mueve el animador (reproducirJugada), paso a paso
        const conAnimador = evento.balon && window.CanchaJugada && !canchaMovimientoReducido && evento.tipo !== '🚩 FUERA DE LUGAR';
        const protagonistas = (evento.tipo === CANCHA_TIPO_SUSTITUCION || conAnimador) ? [] : (evento.jugadores || []);
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
    const CANCHA_SEPARACION_MINIMA = 4.5; // la ficha (jersey) mide ~4.4 m de ancho, ver .cancha-jugador
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
                // Jersey de su selección con el dorsal encima; si la imagen no carga, queda la
                // ficha redonda de color de equipo de siempre (cancha-jugador--sin-jersey).
                const paisId = f.lado === 'local' ? data.id_local : data.id_visita;
                el.innerHTML = '<img class="cancha-jugador__jersey" alt="" draggable="false"><span class="cancha-jugador__dorsal"></span>';
                const jersey = el.querySelector('.cancha-jugador__jersey');
                const urlJersey = paisId != null && window.UI ? UI.urlImagenPais(paisId, 'jersey') : null;
                if (urlJersey) {
                    jersey.addEventListener('error', () => el.classList.add('cancha-jugador--sin-jersey'), { once: true });
                    jersey.src = urlJersey;
                } else {
                    el.classList.add('cancha-jugador--sin-jersey');
                }
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
            el.classList.toggle('cancha-jugador--leyenda', canchaLeyendas.has(f.nombre));
            el.querySelector('.cancha-jugador__dorsal').textContent = canchaDorsales[f.nombre] ?? '';
            const posicion = canchaPlantillas[f.nombre] ? ` · ${canchaPlantillas[f.nombre]}` : '';
            el.title = `${f.nombre}${posicion}${canchaLeyendas.has(f.nombre) ? ' · Leyenda' : ''}`;

            el.classList.remove('cancha-jugador--activo', 'cancha-jugador--secundario', 'cancha-jugador--gol', 'cancha-jugador--amarilla');
            void el.offsetWidth; // reinicia la animación si el mismo jugador repite protagonismo
            if (f.rol) el.classList.add(`cancha-jugador--${f.rol}`);
            const animacion = claseAnimacionFicha(eventoBase.tipo, f.rol);
            if (animacion) el.classList.add(animacion);

            const aplicarPosicion = () => {
                if (!esNueva && eventoBase.balon && window.CanchaJugada && !canchaMovimientoReducido) {
                    // el equipo se desplaza en bloque durante toda la jugada, sin llegar antes que la pelota
                    const ms = Math.round(Math.max(800, canchaPresupuestoMs * 0.85));
                    el.style.transition = `left ${ms}ms ease-in-out, top ${ms}ms ease-in-out, opacity 0.45s ease, scale 0.3s ease`;
                } else {
                    el.style.transition = '';
                }
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

    // Trazo del recorrido del balón: recto para pases, tiros y conducciones; en arco para los balones aéreos.
    // opciones.ms = cuánto tarda en dibujarse (lo mismo que el balón en recorrerlo); opciones.curva = el tipo de paso.
    function dibujarTrazoBalon(desde, hasta, tipo, esLocal, opciones = {}) {
        if (!canchaTrazos) return;
        const x1 = canchaXaSvg(desde.x), y1 = desde.y;
        const x2 = canchaXaSvg(hasta.x), y2 = hasta.y;
        const largo = Math.hypot(x2 - x1, y2 - y1) || 0.01;
        const ms = opciones.ms || 600;
        const aereo = opciones.curva === 'aereo';

        const trazo = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        // En arco: el punto de control se levanta "hacia arriba" de la pantalla, proporcional al largo
        const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2 - (aereo ? Math.min(14, largo * 0.35) : 0);
        trazo.setAttribute('d', aereo
            ? `M ${x1.toFixed(1)} ${y1.toFixed(1)} Q ${cx.toFixed(1)} ${cy.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}`
            : `M ${x1.toFixed(1)} ${y1.toFixed(1)} L ${x2.toFixed(1)} ${y2.toFixed(1)}`);
        const claseColor = esLocal ? 'cancha-trazo--local' : 'cancha-trazo--visitante';
        const claseFuerza = esCanchaTipoDisparo(tipo) ? ' cancha-trazo--fuerte' : '';
        const claseCurva = opciones.curva === 'conduccion' ? ' cancha-trazo--conduccion' : (aereo ? ' cancha-trazo--aereo' : '');
        trazo.setAttribute('class', `cancha-trazo ${claseColor}${claseFuerza}${claseCurva}`);
        canchaTrazos.appendChild(trazo);
        const total = trazo.getTotalLength ? trazo.getTotalLength() || largo : largo;
        trazo.style.strokeDasharray = `${total}`;
        trazo.style.strokeDashoffset = `${total}`;

        // Fuerza reflow para que el navegador registre el trazo "invisible" antes de animarlo a 0
        void trazo.getBoundingClientRect();
        trazo.style.transition = `stroke-dashoffset ${ms}ms ${aereo ? 'ease-in-out' : 'linear'}, opacity 0.4s ease ${ms}ms`;
        trazo.style.strokeDashoffset = '0';

        // Se retira poco después de dibujarse, para no acumular trazos de jugadas viejas
        setTimeout(() => {
            trazo.style.opacity = '0';
            setTimeout(() => trazo.remove(), 450);
        }, ms + 400);
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

        const marcas = [];
        puntos.forEach(evento => {
            marcas.push({ ...canchaPosicionVisual(evento), alfa: 0.22 });
            ((evento.balon && evento.balon.q) || []).forEach(([x, y]) => marcas.push({ x, y, alfa: 0.1 }));
        });
        marcas.forEach(({ x, y, alfa }) => {
            const px = (x / 100) * ancho;
            const py = (y / 68) * alto;
            const rg = bctx.createRadialGradient(px, py, 0, px, py, radio);
            rg.addColorStop(0, `rgba(0,0,0,${alfa})`);
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
        [['Local', data.goles_local, data.bandera_local, data.id_local], ['Visitante', data.goles_visitante, data.bandera_visitante, data.id_visita]].forEach(([lado, goles, bandera, paisId]) => {
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
            // Escudo de la selección (o el emoji si no hay imagen); solo se redibuja si cambió
            const claveBandera = `${paisId}|${bandera}`;
            if (elBandera.dataset.clave !== claveBandera) {
                elBandera.dataset.clave = claveBandera;
                elBandera.innerHTML = window.UI ? UI.bandera(bandera || '🏳️', { id: paisId ?? null, tipo: 'escudo' }) : (bandera || '🏳️');
            }
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
    const CANCHA_AVISO_DURACION_MS = 3600;
    const CANCHA_AVISO_CAMBIO_MS = 4200;   // el cambio tiene su animación de entrada y salida
    const CANCHA_AVISO_GOL_MS = 4800;
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

    // Goles: también tienen su ventana (rostro del goleador, minuto y marcador) además de la jugada en la cancha
    const esGolAviso = ev => (ev.tipo || '').startsWith('⚽') && !esDeTanda(ev);

    function marcadorHasta(eventos, i, local, visitante) {
        let l = 0, v = 0;
        for (let k = 0; k <= i; k++) {
            const e = eventos[k];
            if (!esGolAviso(e)) continue;
            if (e.equipo === local) l++; else if (e.equipo === visitante) v++;
        }
        return { l, v };
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
            const gol = esGolAviso(ev);
            if (!esEventoAviso(ev) && !gol) return;
            if (ev.tipo === CANCHA_TIPO_SUSTITUCION && (ev.jugadores || []).length < 2) return;
            const clave = claveAviso(ev);
            if (canchaAvisosVistos.has(clave)) return;
            canchaAvisosVistos.add(clave);
            if (i < desdeIndice) return;
            const extra = gol ? {
                marcador: marcadorHasta(eventos, i, data.local, data.visitante),
                golesJugador: eventos.slice(0, i + 1).filter(e => esGolAviso(e) && (e.jugadores || [])[0] === (ev.jugadores || [])[0]).length,
            } : {};
            canchaAvisosCola.push({ ev, local: data.local, visitante: data.visitante, idLocal: data.id_local, idVisita: data.id_visita, ...extra });
        });
        if (!canchaAvisoMostrando) mostrarSiguienteAviso();
    }

    // --- piezas de la ventana -----------------------------------------------------------------------
    const ROL_ARBITRO = { central: 'Árbitro central', linea1: 'Juez de línea', linea2: 'Juez de línea', cuarto: '4to árbitro', var: 'VAR' };

    function urlArbitro(nombre, rol) {
        if (nombre) {
            const a = Object.values(canchaArbitros).find(x => x.nombre === nombre);
            if (a && a.url) return a.url;
        }
        return (canchaArbitros[rol || 'central'] || {}).url || null;
    }

    function rostro(url, clase = '', alt = '') {
        return `<span class="cancha-aviso__rostro ${clase}">${url ? `<img src="${escaparHtml(url)}" alt="${escaparHtml(alt)}" onerror="this.remove()">` : ''}<i class="bi bi-person-fill"></i></span>`;
    }
    function rostroJugador(nombre, paisId, clase = '') {
        const id = canchaIds[nombre];
        const bandera = paisId != null && window.UI ? UI.urlImagenPais(paisId, 'plana') : null;
        const url = id != null && window.UI ? UI.urlAvatar(id) : null;
        return `<span class="cancha-aviso__rostro cancha-aviso__rostro--jugador ${clase}"${bandera ? ` style="--bandera-url: url('${escaparHtml(bandera)}')"` : ''}>`
            + `${url ? `<img src="${escaparHtml(url)}" alt="${escaparHtml(nombre)}" onerror="this.remove()">` : ''}<i class="bi bi-person-fill"></i></span>`;
    }

    // Texto corto con lo importante en negritas: nombres (jugadores, árbitro, DT, equipos), minutos y marcadores
    function resaltarAviso(texto, nombres) {
        let html = escaparHtml(texto);
        const lista = [...new Set(nombres.filter(n => n && n.length > 2))].sort((a, b) => b.length - a.length).map(escaparHtml);
        const patrones = lista.map(n => n.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
        patrones.push("\\d+(?:\\+\\d+)?(?:'|&#39;|&#039;)", '\\d+\\s*-\\s*\\d+', '\\+\\d+ minutos?', '\\+\\d+', '\\d+ minutos?');
        return html.replace(new RegExp(`(${patrones.join('|')})`, 'g'), '<strong>$1</strong>');
    }
    function primeraFrase(texto, tope = 96) {
        const t = (texto || '').replace(/\s+/g, ' ').trim();
        const m = t.match(/^.+?[.!?](?=\s|$)/);
        let f = m ? m[0] : t;
        if (f.length > tope) f = f.slice(0, tope).replace(/\s+\S*$/, '') + '…';
        return f;
    }
    function textoCortoAviso(ev, local, visitante) {
        const eq = ev.equipo || '';
        switch (ev.tipo) {
            case '⏱️ TIEMPO AÑADIDO': {
                const n = ev.minutos_anadidos || 0;
                return `Levanta el cartel: se jugará${n === 1 ? '' : 'n'} +${n} minuto${n === 1 ? '' : 's'} más.`;
            }
            case '🚩 SAQUE DE ESQUINA': return `Tiro de esquina para ${eq}.`;
            case '🎯 PENAL': return `¡Penal para ${eq}!`;
            case '👉 SILBATO INICIAL': return `¡Rueda el balón! ${local} vs ${visitante}.`;
            case '🚑 LESIÓN': {
                const j = (ev.jugadores || [])[0] || '';
                const sigue = ev.sale_lesionado ? (ev.sin_cambio ? 'sale y su equipo queda con uno menos' : 'tiene que salir') : 'sigue en la cancha';
                return `${j}: ${ev.lesion || 'lesión'}${ev.gravedad ? ` (${ev.gravedad})` : ''}, ${sigue}.`;
            }
            default: return primeraFrase(ev.descripcion);
        }
    }

    // Arma el contenido de la ventana según el tipo de aviso; devuelve la clase de color.
    function armarContenidoAviso(item) {
        const { ev, local, visitante, idLocal, idVisita } = item;
        const encabezado = document.getElementById('canchaAvisoEncabezado');
        const titulo = document.getElementById('canchaAvisoTitulo');
        const cuerpo = document.getElementById('canchaAvisoCuerpo');
        const minuto = `${minutoTexto(ev)}'`;
        const lado = ev.equipo === local ? 'local' : (ev.equipo === visitante ? 'visitante' : null);
        const paisId = lado === 'local' ? idLocal : (lado === 'visitante' ? idVisita : null);
        cuerpo.innerHTML = '';

        // --- Gol: rostro del goleador, minuto, marcador y cómo fue ---
        if (esGolAviso(ev)) {
            const goleador = (ev.jugadores || [])[0] || '';
            const m = item.marcador || { l: 0, v: 0 };
            const como = ev.de_penal || ev.tipo.includes('PENAL') ? 'de penal' : (ev.tipo.includes('TIRO LIBRE') ? 'de tiro libre' : (ev.tipo.includes('CÓRNER') ? 'tras un córner' : ''));
            const cuenta = item.golesJugador >= 3 ? '¡Hat-trick!' : (item.golesJugador === 2 ? '¡Doblete!' : '');
            encabezado.textContent = ev.equipo || '';
            titulo.innerHTML = `<span class="cancha-aviso__gol-grito">¡GOOOL!</span>`;
            cuerpo.innerHTML = `
                <div class="cancha-aviso__gol">
                  ${rostroJugador(goleador, paisId, 'cancha-aviso__rostro--gol')}
                  <div class="cancha-aviso__gol-datos">
                    <div class="cancha-aviso__gol-nombre">${canchaDorsales[goleador] != null ? `<span class="cancha-aviso__dorsal">${escaparHtml(String(canchaDorsales[goleador]))}</span>` : ''}<strong>${escaparHtml(goleador)}</strong></div>
                    <div class="cancha-aviso__gol-meta"><strong>${escaparHtml(minuto)}</strong>${como ? ` · ${escaparHtml(como)}` : ''}${cuenta ? ` · <span class="cancha-aviso__gol-cuenta">${cuenta}</span>` : ''}</div>
                    <div class="cancha-aviso__gol-marcador"><span class="${lado === 'local' ? 'is-anota' : ''}">${escaparHtml(local)} <strong>${m.l}</strong></span><span>-</span><span class="${lado === 'visitante' ? 'is-anota' : ''}"><strong>${m.v}</strong> ${escaparHtml(visitante)}</span></div>
                  </div>
                </div>`;
            return `gol cancha-aviso--${lado || 'local'}`;
        }

        // --- Sustitución: el que sale se va y el que entra aparece, con su rostro ---
        if (ev.tipo === CANCHA_TIPO_SUSTITUCION) {
            const [entra, sale] = ev.jugadores;
            const pos = nombre => canchaPlantillas[nombre] ? ` · ${escaparHtml(canchaPlantillas[nombre])}` : '';
            encabezado.textContent = ev.equipo || '';
            titulo.innerHTML = `🔄 Sustitución · <strong>${escaparHtml(minuto)}</strong>`;
            const ficha = (nombre, clase, icono, rotulo) => `
                <div class="cancha-aviso__cambio-lado cancha-aviso__cambio-lado--${clase}">
                  ${rostroJugador(nombre, paisId)}
                  <div class="cancha-aviso__cambio-nombre"><i class="bi ${icono}"></i><strong>${escaparHtml(nombre)}</strong></div>
                  <small>${rotulo}${canchaDorsales[nombre] != null ? ` · #${escaparHtml(String(canchaDorsales[nombre]))}` : ''}${pos(nombre)}</small>
                </div>`;
            cuerpo.innerHTML = `<div class="cancha-aviso__cambio">${ficha(sale, 'sale', 'bi-arrow-down-circle-fill', 'Sale')}`
                + `<span class="cancha-aviso__cambio-flechas" aria-hidden="true"><i class="bi bi-arrow-left-right"></i></span>`
                + `${ficha(entra, 'entra', 'bi-arrow-up-circle-fill', 'Entra')}</div>`;
            return lado || 'local';
        }

        // --- Árbitro / VAR / DT / lesión: rostro de quien marca y un texto corto con lo importante en negritas ---
        const esVar = esEventoVar(ev);
        const esDT = TIPOS_DT.includes(ev.tipo);
        const esLesion = ev.tipo === EVENTO_LESION;
        const dt = esDT ? (canchaDT[lado === 'local' ? 'local' : 'visita'] || {}) : null;
        const nombreArbitro = ev.arbitro || (canchaArbitros[ev.arbitro_rol || (esVar ? 'var' : 'central')] || {}).nombre || '';
        let cara, quien;
        if (esDT) {
            cara = rostro(dt.avatar_url, 'cancha-aviso__rostro--dt', dt.nombre || '');
            quien = `<strong>${escaparHtml(dt.nombre || 'DT')}</strong><small>DT · ${escaparHtml(ev.equipo || '')}</small>`;
        } else if (esLesion) {
            const j = (ev.jugadores || [])[0] || '';
            cara = rostroJugador(j, paisId);
            quien = `<strong>${escaparHtml(j)}</strong><small>Atención médica</small>`;
        } else {
            cara = rostro(urlArbitro(nombreArbitro, ev.arbitro_rol || (esVar ? 'var' : 'central')), esVar ? 'cancha-aviso__rostro--var' : 'cancha-aviso__rostro--arbitro', nombreArbitro);
            quien = `<strong>${escaparHtml(nombreArbitro || (esVar ? 'VAR' : 'Árbitro'))}</strong><small>${ROL_ARBITRO[ev.arbitro_rol] || (esVar ? 'VAR' : 'Árbitro central')}</small>`;
        }
        encabezado.textContent = esVar ? (lado ? `VAR · ${ev.equipo}` : 'VAR') : (esDT || esLesion ? (ev.equipo || '') : 'Árbitro');
        titulo.innerHTML = `${escaparHtml(ev.tipo)} · <strong>${escaparHtml(minuto)}</strong>`;
        const nombres = [...(ev.jugadores || []), nombreArbitro, ev.dt, dt && dt.nombre, local, visitante];
        cuerpo.innerHTML = `
            <div class="cancha-aviso__marca">
              ${cara}
              <div class="cancha-aviso__marca-texto">
                <div class="cancha-aviso__quien">${quien}</div>
                <div class="cancha-aviso__descripcion">${resaltarAviso(textoCortoAviso(ev, local, visitante), nombres)}</div>
              </div>
            </div>`;
        return esVar ? 'var' : (esDT || esLesion ? (lado || 'arbitro') : 'arbitro');
    }

    function mostrarSiguienteAviso() {
        const siguiente = canchaAvisosCola.shift();
        if (!siguiente) { canchaAvisoMostrando = false; return; }
        canchaAvisoMostrando = true;
        const gol = esGolAviso(siguiente.ev);
        // el gol espera a que la pelota llegue a la red en la cancha
        setTimeout(() => {
            const clase = armarContenidoAviso(siguiente);
            canchaAviso.classList.remove('cancha-aviso--local', 'cancha-aviso--visitante', 'cancha-aviso--arbitro', 'cancha-aviso--var',
                'cancha-aviso--gol', 'cancha-aviso--cambio', 'cancha-aviso--visible');
            clase.split(' ').forEach(c => canchaAviso.classList.add(c.startsWith('cancha-aviso--') ? c : `cancha-aviso--${c}`));
            if (siguiente.ev.tipo === CANCHA_TIPO_SUSTITUCION) canchaAviso.classList.add('cancha-aviso--cambio');
            void canchaAviso.offsetWidth; // reinicia la animación de entrada
            canchaAviso.classList.add('cancha-aviso--visible');
            const dura = gol ? CANCHA_AVISO_GOL_MS : (siguiente.ev.tipo === CANCHA_TIPO_SUSTITUCION ? CANCHA_AVISO_CAMBIO_MS : CANCHA_AVISO_DURACION_MS);
            setTimeout(() => {
                canchaAviso.classList.remove('cancha-aviso--visible');
                setTimeout(mostrarSiguienteAviso, 400); // deja terminar la salida antes de la próxima
            }, dura);
        }, gol && !canchaMovimientoReducido ? 900 : 0);
    }

    const bloqueCanchaVivo = document.getElementById('bloqueCanchaVivo');
    const canchaVisible = () => !bloqueCanchaVivo || bloqueCanchaVivo.offsetParent !== null;

    // ---------------------------------------------------------------------------------------------
    // Cola de animación de la cancha: cada poll (3 s) puede traer varios eventos nuevos y antes se
    // animaba solo el último (los anteriores se saltaban). Ahora cada evento con jugada en la cancha
    // (posicion_balon) o aviso se anima por separado y en orden, repartidos en el tiempo hasta el
    // próximo poll: balón, trazo, etiqueta del jugador, fichas y avisos. renderCancha y
    // renderJugadoresCancha siguen igual: se les pasa el partido "cortado" hasta ese evento.
    // ---------------------------------------------------------------------------------------------
    const COLA_PASO_MIN_MS = 1200;     // ningún evento dura menos que esto en pantalla
    const COLA_PASO_MAX_MS = 2600;
    const COLA_MAX_PENDIENTES = 8;     // si se acumulan (pestaña en segundo plano), se saltan los más viejos
    let colaCancha = [], colaDatos = null, colaPartido = null, colaAnimados = 0, colaTimer = null;
    let colaLibreEn = 0;                 // hasta cuándo dura la jugada que se está animando (no se corta)
    let canchaMsPorEvento = 4800;        // cada cuánto revela un evento la transmisión (ms_por_evento del payload)

    function encolarCancha(data) {
        const eventos = data.eventos || [];
        if (data.match_id !== colaPartido) {   // partido nuevo (o primera carga): arranca desde lo ya revelado
            clearTimeout(colaTimer); colaTimer = null;
            colaCancha = [];
            colaPartido = data.match_id;
            colaAnimados = Math.max(0, eventos.length - 1);   // al entrar a mitad del partido no se repite la historia
            reiniciarJugadoresCanchaSiCambioPartido(data.match_id);
        }
        colaDatos = data;
        if (data.ms_por_evento) canchaMsPorEvento = data.ms_por_evento;
        for (let k = colaAnimados + 1; k <= eventos.length; k++) {
            const ev = eventos[k - 1];
            if (ev.posicion_balon || esEventoAviso(ev) || k === eventos.length) colaCancha.push(k);
        }
        colaAnimados = Math.max(colaAnimados, eventos.length);
        if (colaCancha.length > COLA_MAX_PENDIENTES) colaCancha = colaCancha.slice(-COLA_MAX_PENDIENTES);
        if (!colaTimer) {
            const espera = colaLibreEn - Date.now();
            if (espera > 0) colaTimer = setTimeout(pasoCola, espera);   // deja terminar la jugada en curso
            else pasoCola();
        }
    }

    function pasoCola() {
        colaTimer = null;
        if (!colaCancha.length || !colaDatos) return;
        const k = colaCancha.shift();
        const parcial = { ...colaDatos, eventos: (colaDatos.eventos || []).slice(0, k) };
        const ev = parcial.eventos[k - 1];
        // Cada jugada llena el tiempo hasta el próximo evento; si hay varias esperando, se reparten ese tiempo
        // (un aviso solo se muestra, no lleva jugada)
        const animada = window.CanchaJugada && !canchaMovimientoReducido;
        const base = animada ? canchaMsPorEvento * 0.92 : COLA_PASO_MAX_MS;
        canchaPresupuestoMs = (ev && esEventoAviso(ev))
            ? COLA_PASO_MIN_MS
            : Math.max(COLA_PASO_MIN_MS, base / (1 + colaCancha.length));
        colaLibreEn = Date.now() + canchaPresupuestoMs;
        try {
            renderJugadoresCancha(parcial);   // primero el bloque: después el animador mueve a los protagonistas
            renderCancha(parcial);
        } catch (e) { console.error(e); }
        if (!colaCancha.length) return;
        colaTimer = setTimeout(pasoCola, canchaPresupuestoMs);
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
        if (window.CanchaJugada && !canchaMovimientoReducido) {
            // Jugada animada: toques sin narrar, pase/centro/tiro con su curva y los jugadores que la protagonizan
            canchaPosicionActual = reproducirJugada(ultimoConPosicion, data, posicionNueva, esLocal) || posicionNueva;
            return;
        } else {
            // Movimiento reducido (o sin el módulo): un solo salto como antes
            canchaBalon.style.transition = '';
            canchaBalon.style.transform = '';
            canchaBalon.style.opacity = '';
            dibujarTrazoBalon(canchaPosicionActual, posicionNueva, ultimoConPosicion.tipo, esLocal);
            canchaBalon.style.left = `${Math.max(0, Math.min(100, posicionNueva.x))}%`;
            canchaBalon.style.top = `${Math.max(0, Math.min(100, (posicionNueva.y / 68) * 100))}%`;
            mostrarEtiquetaJugada(ultimoConPosicion, data, posicionNueva);
            aplicarEfectoBalon(ultimoConPosicion.tipo);
        }
        canchaPosicionActual = posicionNueva;
    }

    // Nombre del jugador protagonista del evento (siempre el primero de la lista, ver simular_service.py) junto al
    // balón, tanto en el tooltip como en la etiqueta flotante que se desvanece sola, con su posición granular
    // (POR/LD/MC... de canchaPlantillas). El equipo (evento.equipo) va arriba del nombre y el tipo de evento abajo.
    function mostrarEtiquetaJugada(evento, data, pos) {
        const leftBalonPct = Math.max(0, Math.min(100, pos.x));
        const topBalonPct = Math.max(0, Math.min(100, (pos.y / 68) * 100));
        const jugadorPrincipal = (evento.jugadores && evento.jugadores[0]) || '';
        const posicionSigla = canchaPlantillas[jugadorPrincipal] || '';
        const tipoEvento = evento.tipo || '';
        // El equipo del propio jugador cuando está en cancha (en un saque de banda el evento es del que saca, pero el
        // nombrado es el que la mandó afuera); si no, el del evento
        const fichaPrincipal = typeof fichaDe === 'function' ? fichaDe(jugadorPrincipal) : null;
        const equipoEvento = fichaPrincipal ? (fichaPrincipal.esLocal ? data.local : data.visitante) : (evento.equipo || '');
        let textoNombre = jugadorPrincipal;
        if (posicionSigla) textoNombre += ` · ${posicionSigla}`;

        const textoTooltip = [equipoEvento, textoNombre, tipoEvento].filter(Boolean).join(' — ');
        canchaBalon.title = textoTooltip || 'Posición del balón';
        if (!canchaEtiquetaJugador || !(jugadorPrincipal || tipoEvento)) return;
        if (canchaEtiquetaJugadorEquipo) {
            canchaEtiquetaJugadorEquipo.textContent = equipoEvento;
            canchaEtiquetaJugadorEquipo.hidden = !equipoEvento;
            // Color según 'evento.equipo' (no según quién ataca: en faltas o robos son equipos distintos);
            // los neutros (Árbitro/VAR) en gris
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

    function aplicarEfectoBalon(tipo) {
        tipo = tipo || '';
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

    // ---------------------------------------------------------------------------------------------
    // Animador de jugadas (static/js/cancha_jugada.js arma el guion): el balón recorre cada paso con su curva
    // (raso, aéreo con sombra, tiro, conducción, colocar), cada receptor corre a donde le llega la pelota, el que
    // conduce va pegado a ella y el arquero se estira. Todo dentro del tiempo que hay hasta el próximo evento.
    // ---------------------------------------------------------------------------------------------
    const canchaMovimientoReducido = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    let canchaAnimacionId = 0;
    let canchaPresupuestoMs = 1500;   // lo fija pasoCola para cada evento
    let canchaBalonSombra = null;
    const canchaRedes = {};
    const ALTURA_BALON_PX = 20;

    function prepararElementosJugada() {
        if (!canchaWrapperEl) return;
        if (!canchaBalonSombra) {
            canchaBalonSombra = document.createElement('div');
            canchaBalonSombra.className = 'cancha-balon-sombra';
            canchaWrapperEl.insertBefore(canchaBalonSombra, canchaBalon);
        }
        ['izq', 'der'].forEach(lado => {
            if (canchaRedes[lado]) return;
            const red = document.createElement('div');
            red.className = `cancha-red cancha-red--${lado}`;
            canchaWrapperEl.appendChild(red);
            canchaRedes[lado] = red;
        });
    }

    function fichaDe(nombre) {
        if (!nombre) return null;
        const local = canchaFichas.get(`local|${nombre}`);
        if (local) return { el: local, esLocal: true };
        const visita = canchaFichas.get(`visitante|${nombre}`);
        return visita ? { el: visita, esLocal: false } : null;
    }

    // Lleva la ficha de un jugador a un punto de la cancha (un paso detrás de la pelota, mirando al arco rival)
    function moverFicha(nombre, punto, ms, ease = 'ease-in-out', separacion = 2.2) {
        const f = fichaDe(nombre);
        if (!f || !punto) return null;
        const x = limitar(punto.x + (f.esLocal ? -separacion : separacion), CANCHA_X_MIN, CANCHA_X_MAX);
        const y = limitar(punto.y, CANCHA_Y_MIN, CANCHA_Y_MAX);
        f.el.style.transition = `left ${Math.round(ms)}ms ${ease}, top ${Math.round(ms)}ms ${ease}, opacity 0.45s ease, scale 0.3s ease`;
        f.el.style.left = `${x}%`;
        f.el.style.top = `${(y / 68) * 100}%`;
        return f.el;
    }

    function marcarFicha(nombre, clase, ms) {
        const f = fichaDe(nombre);
        if (!f) return;
        f.el.classList.remove(clase);
        void f.el.offsetWidth;
        f.el.classList.add(clase);
        if (ms) setTimeout(() => f.el.classList.remove(clase), ms);
    }

    function dibujarBalonEn(paso, f) {
        let x, y, altura = 0, opacidad = 1;
        if (paso.curva === 'colocar') {
            // la pelota se repone: se desvanece donde estaba y aparece donde se reanuda
            const antes = f < 0.5;
            ({ x, y } = antes ? paso.desde : paso.hasta);
            opacidad = antes ? 1 - 2 * f : 2 * f - 1;
        } else if (paso.curva === 'parado') {
            ({ x, y } = paso.hasta);
        } else {
            ({ x, y, altura } = CanchaJugada.posicion(paso, f));
            if (paso.curva === 'fuera' && f > 0.85) opacidad = 1 - (f - 0.85) * 3;
        }
        const left = `${Math.max(0, Math.min(100, x))}%`;
        const top = `${Math.max(0, Math.min(100, (y / 68) * 100))}%`;
        canchaBalon.style.left = left;
        canchaBalon.style.top = top;
        canchaBalon.style.opacity = String(Math.max(0, opacidad));
        canchaBalon.style.transform = altura ? `translateY(${-altura * ALTURA_BALON_PX}px) scale(${1 + altura * 0.45})` : '';
        if (canchaBalonSombra) {
            canchaBalonSombra.style.left = left;
            canchaBalonSombra.style.top = top;
            canchaBalonSombra.style.opacity = String(Math.max(0, opacidad) * (0.55 - altura * 0.25));
            canchaBalonSombra.style.transform = `scale(${1 - altura * 0.35})`;
        }
    }

    function iniciarPaso(paso, evento, data, g) {
        if (['raso', 'aereo', 'tiro', 'conduccion', 'fuera'].includes(paso.curva)) {
            dibujarTrazoBalon(paso.desde, paso.hasta, paso.curva === 'tiro' ? evento.tipo : '', paso.l === 1, { ms: paso.ms, curva: paso.curva });
        }
        if (paso.curva === 'conduccion' && paso.portador) {
            moverFicha(paso.portador, paso.hasta, paso.ms, 'linear');
        } else if (paso.portador) {
            moverFicha(paso.portador, paso.desde, Math.min(300, paso.ms));
        }
        if (paso.receptor && paso.receptor !== paso.portador) moverFicha(paso.receptor, paso.hasta, paso.ms * 0.95);
        if (paso.marca) moverFicha(paso.marca, paso.hasta, paso.ms, 'ease-in-out', -1.5);
        if (paso.arquero) setTimeout(() => moverFicha(paso.arquero, paso.hasta, Math.max(180, paso.ms * 0.35), 'ease-out', 0), paso.ms * 0.6);
        if (!paso.principal) return;
        const protagonista = paso.receptor || paso.portador || paso.marca || paso.arquero;
        if (protagonista) marcarFicha(protagonista, 'cancha-jugador--activo', 2200);
        mostrarEtiquetaJugada(evento, data, paso.hasta);
        setTimeout(() => finalizarJugada(paso, evento, g), paso.ms);
    }

    function finalizarJugada(paso, evento, g) {
        aplicarEfectoBalon(evento.tipo);
        if (g.efecto === 'gol') {
            const red = canchaRedes[paso.hasta.x >= 50 ? 'der' : 'izq'];
            if (red) { red.classList.remove('cancha-red--sacude'); void red.offsetWidth; red.classList.add('cancha-red--sacude'); }
            if (paso.portador) marcarFicha(paso.portador, 'cancha-jugador--gol', 2400);
        } else if (g.efecto === 'atajada' && paso.arquero) {
            marcarFicha(paso.arquero, 'cancha-jugador--estirada', 900);
        } else if (evento.tipo === '🟨 TARJETA AMARILLA' && evento.jugadores) {
            marcarFicha(evento.jugadores[0], 'cancha-jugador--amarilla', 2200);
        }
    }

    function reproducirJugada(evento, data, posNueva, atacaLocal) {
        prepararElementosJugada();
        const id = ++canchaAnimacionId;
        const g = evento.balon
            ? CanchaJugada.guion(evento, canchaPosicionActual)
            : CanchaJugada.guionViejo(evento, canchaPosicionActual, posNueva, atacaLocal);
        const presupuesto = canchaPresupuestoMs * 0.92;
        const pasos = CanchaJugada.repartir(g.pasos, presupuesto);
        // Si sobra tiempo después de una jugada abierta, el que se quedó con la pelota la controla y avanza un poco
        // hacia el arco rival (menos de lo que la transmisión repone de golpe: el próximo evento sale de ahí)
        const principal = pasos[pasos.length - 1];
        const sobra = presupuesto - pasos.reduce((a, p) => a + p.ms, 0);
        const quien = principal.receptor || (principal.curva === 'conduccion' ? principal.portador : null);
        if (sobra > 500 && !g.efecto && ['raso', 'aereo', 'conduccion'].includes(principal.curva) && fichaDe(quien)) {
            const sentido = fichaDe(quien).esLocal ? 1 : -1;
            const hasta = { x: limitar(principal.hasta.x + sentido * 2, 1, 99), y: principal.hasta.y };
            pasos.push({ desde: principal.hasta, hasta, curva: 'conduccion', portador: quien, receptor: quien, l: principal.l, ms: Math.round(sobra * 0.9) });
            g.final = hasta;
        }
        let acumulado = 0;
        pasos.forEach(p => { p.inicio = acumulado; acumulado += p.ms; });
        canchaBalon.style.transition = 'none';   // el balón lo mueve el animador, no la transición CSS

        pasos.forEach(p => {
            if (p.inicio === 0) iniciarPaso(p, evento, data, g);
            else setTimeout(() => { if (id === canchaAnimacionId) iniciarPaso(p, evento, data, g); }, p.inicio);
        });
        const comienzo = performance.now();
        const cuadro = ahora => {
            if (id !== canchaAnimacionId) return;
            const t = ahora - comienzo;
            const paso = pasos.find(p => t < p.inicio + p.ms) || pasos[pasos.length - 1];
            dibujarBalonEn(paso, Math.min(1, Math.max(0, (t - paso.inicio) / paso.ms)));
            if (t < acumulado) requestAnimationFrame(cuadro);
        };
        requestAnimationFrame(cuadro);
        return g.final;
    }

    function actualizarInfoPartido(data) {
        infoPartidoGrupo.innerHTML = data.grupo ? `<i class="bi bi-grid-3x3-gap-fill me-1"></i>${data.grupo}` : '';
        infoPartidoGrupo.classList.toggle('d-none', !data.grupo);

        // Ilustración del estadio + nombre; solo se redibuja si cambió (el polling no la hace parpadear)
        const claveEstadio = `${data.estadio}|${data.estadio_img}`;
        if (infoPartidoEstadio.dataset.clave !== claveEstadio) {
            infoPartidoEstadio.dataset.clave = claveEstadio;
            const imagen = data.estadio_img
                ? `<span class="estadio-ilustracion estadio-ilustracion--mini d-inline-block align-middle me-2"><img src="${UI.escapar(data.estadio_img)}" alt="" decoding="async" onerror="this.parentNode.remove()"></span>`
                : '<i class="bi bi-geo-alt-fill me-1"></i>';
            infoPartidoEstadio.innerHTML = data.estadio ? `${imagen}${UI.escapar(data.estadio)}` : '';
        }
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
                        <span class="me-1">${UI.bandera(e.bandera, { id: e.pais_id ?? null })}</span>
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
    // así que se estima aquí con un heurístico simple a partir de los eventos ya revelados
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
    // Goles del partido (la tanda de penales no cuenta como gol del jugador en la lista)
    const TIPOS_GOL_LISTA = new Set(['⚽ GOL', '⚽ GOL DE TIRO LIBRE', '⚽ GOL DE CÓRNER']);
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
    // Energía (0-100) del jugador al minuto revelado (GET /matches/live -> 'energia', por id). Partidos anteriores a
    // la curva de energía no la traen: null = sin barra. Sin dato todavía (recién entra) = fresco.
    function energiaDe(data, nombre) {
        const mapa = data.energia || {};
        if (!Object.keys(mapa).length) return null;
        const id = canchaIds[nombre];
        const valor = id != null ? mapa[String(id)] : undefined;
        return valor == null ? 100 : valor;
    }

    function calcularEstadoJugadoresEnCancha(data) {
        // Listas en el ORDEN del once inicial: el que entra de cambio ocupa el lugar del que sale, así nadie se mueve
        const onceLocal = [...canchaTitularesLocal];
        const onceVisitante = [...canchaTitularesVisitante];
        const quitar = (lista, nombre) => { const i = lista.indexOf(nombre); if (i >= 0) lista.splice(i, 1); };
        const ratings = new Map();
        const acciones = new Map(); // nombre -> [{ tipo, minuto, peso }], en orden cronológico
        const expulsados = new Set();
        // Lo que hizo cada jugador (para los íconos de la lista) y los que ya no están en cancha
        const info = new Map();   // nombre -> { goles, asistencias, amarillas, roja, entro, salio }
        const infoDe = nombre => { if (!info.has(nombre)) info.set(nombre, { goles: 0, asistencias: 0, amarillas: 0, roja: null, entro: null, salio: null, lesion: null }); return info.get(nombre); };
        const fueraLocal = [], fueraVisitante = [];
        const fueraDe = equipo => equipo === data.local ? fueraLocal : (equipo === data.visitante ? fueraVisitante : null);
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
                    const lugar = once.indexOf(jugadores[1]);
                    if (lugar >= 0) once[lugar] = jugadores[0];   // entra en el mismo lugar del que sale
                    else if (!once.includes(jugadores[0])) once.push(jugadores[0]);
                    const fuera = fueraDe(ev.equipo);
                    if (fuera && !fuera.includes(jugadores[1])) fuera.push(jugadores[1]);
                }
                infoDe(jugadores[0]).entro = minutoTexto(ev);
                infoDe(jugadores[1]).salio = minutoTexto(ev);
                if (porteros[ev.equipo] === jugadores[1]) porteros[ev.equipo] = jugadores[0];
            } else if ((ev.tipo === '🟥 TARJETA ROJA' || ev.tipo === '🟨🟥 DOBLE AMARILLA') && jugadores.length >= 1) {
                const once = onceDe(ev.equipo);
                if (once) quitar(once, jugadores[0]);
                const fuera = fueraDe(ev.equipo);
                if (fuera && !fuera.includes(jugadores[0])) fuera.push(jugadores[0]);
                expulsados.add(jugadores[0]);
                infoDe(jugadores[0]).roja = minutoTexto(ev);
                if (ev.tipo === '🟨🟥 DOBLE AMARILLA') infoDe(jugadores[0]).amarillas += 1;
            } else if (ev.tipo === EVENTO_LESION && jugadores.length >= 1) {
                infoDe(jugadores[0]).lesion = { minuto: minutoTexto(ev), nombre: ev.lesion || 'lesión', gravedad: ev.gravedad || 'leve', sale: !!ev.sale_lesionado };
                if (ev.sin_cambio) {
                    const once = onceDe(ev.equipo);
                    if (once) quitar(once, jugadores[0]);
                    const fuera = fueraDe(ev.equipo);
                    if (fuera && !fuera.includes(jugadores[0])) fuera.push(jugadores[0]);
                    infoDe(jugadores[0]).salio = minutoTexto(ev);
                }
            } else if (TIPOS_GOL_LISTA.has(ev.tipo) && jugadores.length >= 1) {
                infoDe(jugadores[0]).goles += 1;
                if (ev.tipo === '⚽ GOL' && jugadores[2]) infoDe(jugadores[2]).asistencias += 1;
            } else if ((ev.tipo === '🟨 TARJETA AMARILLA' || ev.tipo === '🖥️ VAR - TARJETA REVISADA') && jugadores.length >= 1) {
                infoDe(jugadores[0]).amarillas += 1;
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
            return { nombre, posicion: canchaPlantillas[nombre] || '', rating, acciones: acciones.get(nombre) || [],
                     info: info.get(nombre) || null, destacados: (canchaDestacados.jugadores || {})[nombre] || [],
                     energia: energiaDe(data, nombre) };
        }
        const fueraDeCancha = nombre => ({ ...filaDe(nombre), fuera: true });

        // En cancha primero; al final, los que salieron (cambio o expulsión) en el orden en que salieron
        return {
            local: onceLocal.map(filaDe).concat(fueraLocal.filter(n => !onceLocal.includes(n)).map(fueraDeCancha)),
            visitante: onceVisitante.map(filaDe).concat(fueraVisitante.filter(n => !onceVisitante.includes(n)).map(fueraDeCancha))
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
    // de listeners (registrados una sola vez aquí) alcanza para todas las filas, presentes y
    // futuras, sin tener que instanciar bootstrap.Collapse a mano.
    const jugadoresExpandidos = new Set();
    document.addEventListener('shown.bs.collapse', e => {
        if (e.target.dataset.jugador) jugadoresExpandidos.add(e.target.dataset.jugador);
    });
    document.addEventListener('hidden.bs.collapse', e => {
        if (e.target.dataset.jugador) jugadoresExpandidos.delete(e.target.dataset.jugador);
    });

    // Rostro del jugador (bucket jugadores/<id>.svg) sobre la bandera de su país, con el dorsal del color
    // de su equipo en la esquina. Sin 'loading=lazy': la lista se rearma en cada poll y la imagen sale de
    // caché sin parpadear. Si no hay id o la imagen falla, queda el dorsal solo, como antes.
    function avatarJugadorEnCancha(nombre, lado, paisId, dorsal) {
        const id = canchaIds[nombre];
        const base = (window.PAISES_IMG || {}).base;
        const dorsalHtml = dorsal != null ? `<span class="once-dorsal once-dorsal--${lado}">${dorsal}</span>` : '';
        if (id == null || !base) return dorsalHtml;
        const bandera = paisId != null && window.UI ? UI.urlImagenPais(paisId, 'plana') : null;
        const fondo = bandera ? ` style="--bandera-url: url('${bandera}')"` : '';
        return `<span class="once-avatar once-avatar--${lado}">
                    <span class="avatar-jugador"${fondo}><img src="${window.UI ? UI.urlAvatar(id) : base + '/jugadores/' + encodeURIComponent(id) + '.svg'}" alt="" decoding="async"
                        onerror="this.closest('.once-avatar').classList.add('once-avatar--sin-imagen')"></span>${dorsalHtml}</span>`;
    }

    // Barra de desgaste físico (services/desgaste.py): verde fresco, ámbar desde 70 (empieza a rendir menos),
    // rojo bajo 30 (fundido); el número lo dice también para quien no distingue colores
    function barraEnergia(energia) {
        const e = Math.max(0, Math.min(100, Math.round(energia)));
        const nivel = e >= 70 ? 'alta' : (e >= 30 ? 'media' : 'baja');
        const texto = e >= 70 ? 'Fresco' : (e >= 30 ? 'Cansado' : 'Fundido');
        return `<span class="once-energia once-energia--${nivel}" title="Energía ${e}% · ${texto}" role="img" aria-label="Energía ${e} por ciento, ${texto.toLowerCase()}">
            <span class="once-energia__barra"><span class="once-energia__relleno" style="width:${e}%"></span></span>
            <span class="once-energia__valor">${e}</span></span>`;
    }

    function renderFilaJugadorEnCancha(jugador, lado, paisId) {
        const fila = document.createElement('div');
        fila.className = 'list-group-item bg-dark text-white p-0 border-secondary border-opacity-10 small'
            + (jugador.fuera ? ' once-fila--fuera' : '') + ((jugador.destacados || []).length ? ' once-fila--destacada' : '');

        const idAcciones = `once-acciones-${lado}-${slugJugador(jugador.nombre)}`;
        const expandido = jugadoresExpandidos.has(jugador.nombre);
        const posicionTexto = jugador.posicion ? ` <span class="text-muted">· ${jugador.posicion}</span>` : '';
        // Mismo dorsal y color de equipo que su ficha en la cancha, para ubicarlo de un vistazo
        const dorsal = canchaDorsales[jugador.nombre];
        const dorsalHtml = avatarJugadorEnCancha(jugador.nombre, lado, paisId, dorsal);

        // Íconos: goles, asistencias, tarjetas, entró / salió (con el minuto)
        const inf = jugador.info || {};
        const iconos = [];
        if (inf.goles) iconos.push(`<span class="once-ico" title="${inf.goles} gol${inf.goles > 1 ? 'es' : ''}">⚽${inf.goles > 1 ? `<small>×${inf.goles}</small>` : ''}</span>`);
        if (inf.asistencias) iconos.push(`<span class="once-ico" title="${inf.asistencias} asistencia${inf.asistencias > 1 ? 's' : ''}"><i class="bi bi-share-fill once-ico--asistencia"></i>${inf.asistencias > 1 ? `<small>×${inf.asistencias}</small>` : ''}</span>`);
        if (inf.amarillas && !inf.roja) iconos.push('<span class="once-ico" title="Amonestado">🟨</span>');
        if (inf.roja) iconos.push(`<span class="once-ico" title="Expulsado en el ${inf.roja}'">🟥<small>${inf.roja}'</small></span>`);
        if (inf.entro) iconos.push(`<span class="once-ico once-ico--entra" title="Entró en el ${inf.entro}'"><i class="bi bi-arrow-up-circle-fill"></i><small>${inf.entro}'</small></span>`);
        if (inf.salio) iconos.push(`<span class="once-ico once-ico--sale" title="Salió en el ${inf.salio}'"><i class="bi bi-arrow-down-circle-fill"></i><small>${inf.salio}'</small></span>`);
        if (inf.lesion) iconos.push(`<span class="once-ico once-ico--lesion once-ico--${escaparHtml(inf.lesion.gravedad)}" title="${escaparHtml(`Lesión ${inf.lesion.gravedad} en el ${inf.lesion.minuto}': ${inf.lesion.nombre}${inf.lesion.sale ? '' : ' (sigue tocado)'}`)}">🚑<small>${inf.lesion.minuto}'</small></span>`);
        const energiaHtml = (!jugador.fuera && jugador.energia != null) ? barraEnergia(jugador.energia) : '';
        // En qué top 10 / premios de Estadísticas está (antes de este partido)
        const dest = jugador.destacados || [];
        const textoDestacado = d => d.posicion ? `#${d.posicion} ${d.titulo}` : d.titulo;
        const destacadoHtml = dest.length
            ? `<span class="once-destacado" title="En Estadísticas: ${escaparHtml(dest.map(textoDestacado).join(' · '))}"><i class="bi ${dest[0].icono}"></i><span class="once-destacado__texto">${escaparHtml(textoDestacado(dest[0]))}</span>${dest.length > 1 ? `<small>+${dest.length - 1}</small>` : ''}</span>`
            : '';
        const destacadosDetalle = dest.length
            ? `<div class="once-destacados-detalle mb-1">${dest.map(d => `<span class="once-destacado once-destacado--chip"><i class="bi ${d.icono}"></i>${escaparHtml(textoDestacado(d))}${d.valor != null ? ` <small class="text-muted">(${d.valor} ${escaparHtml(d.sufijo || '')})</small>` : ''}</span>`).join('')}</div>`
            : '';

        const accionesHtml = jugador.acciones.length
            ? jugador.acciones.slice().reverse().map(a => {
                const signo = a.peso > 0 ? '+' : '';
                const clase = a.peso > 0 ? 'text-success' : (a.peso < 0 ? 'text-danger' : 'text-muted');
                return `<div class="${clase}">${signo}${a.peso.toFixed(2)} &nbsp;${a.tipo} &nbsp;<span class="text-muted">· ${Math.round(a.minuto)}'</span></div>`;
            }).join('')
            : '<div class="text-muted fst-italic">Todavía no tiene acciones que hayan afectado su rendimiento.</div>';

        fila.innerHTML = `
            <div class="once-fila d-flex justify-content-between align-items-center py-1 px-3" style="cursor:pointer;"
                 data-bs-toggle="collapse" data-bs-target="#${idAcciones}"
                 aria-expanded="${expandido}" aria-controls="${idAcciones}">
                <span class="d-flex align-items-center gap-2" style="min-width: 0;">
                    ${dorsalHtml}<span class="d-flex flex-column" style="min-width: 0;">
                        <span class="text-truncate">${canchaLeyendas.has(jugador.nombre) ? '<span class="insignia-leyenda insignia-leyenda--compacta" title="Leyenda"><i class="bi bi-award-fill"></i></span> ' : ''}${jugador.nombre}${posicionTexto}</span>
                        ${iconos.length || destacadoHtml ? `<span class="once-iconos">${iconos.join('')}${destacadoHtml}</span>` : ''}
                        ${energiaHtml}
                    </span>
                </span>
                <span class="d-flex align-items-center gap-1">
                    <span class="badge rounded-pill ${claseBadgeRating(jugador.rating)}">${jugador.rating.toFixed(1)}</span>
                    <i class="bi bi-chevron-down text-muted" style="font-size:.65rem;"></i>
                </span>
            </div>
            <div class="collapse${expandido ? ' show' : ''}" id="${idAcciones}" data-jugador="${jugador.nombre}">
                <div class="px-3 pb-2 pt-1 border-top border-secondary border-opacity-10" style="font-size:.72rem;">
                    ${destacadosDetalle}${accionesHtml}
                </div>
            </div>
        `;
        return fila;
    }

    function renderDestacadosPais(idContenedor, lista) {
        const cont = document.getElementById(idContenedor);
        if (!cont) return;
        if (!lista.length) { cont.innerHTML = ''; cont.classList.add('d-none'); return; }
        const texto = d => d.posicion ? `#${d.posicion} ${d.titulo}` : d.titulo;
        const visibles = lista.slice(0, 4);
        cont.innerHTML = visibles.map(d => `<span class="once-destacado once-destacado--chip" title="En Estadísticas: ${escaparHtml(texto(d))}${d.valor != null ? ` (${d.valor} ${escaparHtml(d.sufijo || '')})` : ''}"><i class="bi ${d.icono}"></i>${escaparHtml(texto(d))}</span>`).join('')
            + (lista.length > visibles.length ? `<span class="once-destacado once-destacado--chip" title="${escaparHtml(lista.slice(4).map(texto).join(' · '))}">+${lista.length - visibles.length}</span>` : '');
        cont.classList.remove('d-none');
    }

    function renderJugadoresEnCancha(data) {
        if (!onceListaLocal || !onceListaVisitante) return;
        if (onceNombreLocal) onceNombreLocal.textContent = data.local;
        if (onceNombreVisitante) onceNombreVisitante.textContent = data.visitante;

        renderDestacadosPais('onceDestacadosLocal', canchaDestacados.paises.local || []);
        renderDestacadosPais('onceDestacadosVisitante', canchaDestacados.paises.visitante || []);
        const estado = calcularEstadoJugadoresEnCancha(data);
        onceListaLocal.innerHTML = '';
        const dtLocal = renderFilaDT('local', data);
        if (dtLocal) onceListaLocal.appendChild(dtLocal);
        estado.local.forEach(j => onceListaLocal.appendChild(renderFilaJugadorEnCancha(j, 'local', data.id_local)));
        onceListaVisitante.innerHTML = '';
        const dtVisita = renderFilaDT('visitante', data);
        if (dtVisita) onceListaVisitante.appendChild(dtVisita);
        estado.visitante.forEach(j => onceListaVisitante.appendChild(renderFilaJugadorEnCancha(j, 'visitante', data.id_visita)));

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
        '⚽ GOL DE TIRO LIBRE': '⚽',
        '⚽ GOL DE CÓRNER': '⚽',
        '🖥️ VAR - TARJETA REVISADA': '🟨',
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
            // Detalle del gol: tiro libre, córner, penal en juego (⚽ GOL + de_penal) o penal de la tanda
            const detalle = ev.tipo === '⚽ GOL DE TIRO LIBRE' ? 'tiro libre'
                : ev.tipo === '⚽ GOL DE CÓRNER' ? 'córner'
                : ev.tipo === '⚽ GOL DE PENAL' ? 'tanda de penales'
                : ev.de_penal ? 'penal'
                : ev.tipo === '🖥️ VAR - TARJETA REVISADA' ? 'roja revisada por el VAR' : '';
            const entrada = { minuto: esDeTanda(ev) ? 'PEN' : minutoTexto(ev), icono, nombre, detalle };
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
                    <span class="badge bg-dark border border-secondary">${e.minuto}${e.minuto === 'PEN' ? '' : "'"}</span>
                    <span>${e.icono}</span>
                    <span class="text-white small text-truncate">${escaparHtml(e.nombre)}${e.detalle ? ` <small class="text-muted">(${e.detalle})</small>` : ''}</span>
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
        minutoActual.textContent = data.finalizado ? 'FINAL'
            : (data.adicional_actual ? `${data.minuto_actual}+${data.adicional_actual}'` : `${data.minuto_actual}'`);
        minutoActual.classList.toggle('marcador-tv__minuto--final', !!data.finalizado);
        renderEventos(data.eventos, data.local, data.visitante, data.match_id);
        renderMarcadorTv(data);
        await actualizarPlantillasSiCorresponde(data.match_id);
        actualizarLineasPorEsquema(data);
        actualizarDestacadosSiCorresponde(data.match_id);   // sin await: la primera vez puede tardar, se ve en el próximo poll
        actualizarInteresSiCorresponde(data.match_id).then(() => renderInteresVivo(data));
        // La cancha virtual no se dibuja si está oculta (celular): ahorra el trabajo más pesado de cada poll
        if (canchaVisible()) encolarCancha(data);   // cada evento nuevo se anima por separado (ver "Cola de animación")
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
            programarAutoPlay();
            if (!btnSimularOtro) programarReconsultaInactivo(); // sin permiso de simular: esperar el próximo partido
        } else {
            cancelarAutoPlayProgramado();   // ya arrancó (lo arrancó el pulso o un admin): fuera la cuenta regresiva
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
    // (puntos, multiplicador vigente, cooldown); aquí solo se muestra. Se consulta en el mismo
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
        // una sola vez por partido: saldo del navbar + XP de niveles ganada (toast)
        if (contenedor.dataset.saldoRefrescado !== String(estado.juego_id) && window.UI) {
            contenedor.dataset.saldoRefrescado = String(estado.juego_id);
            UI.refrescarSaldo();
        }
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
            if (!resp.ok) throw new Error(data.detail || 'No se pudo iniciar la simulación.');
            if (!data.encontrado) {
                mostrarInactivo(data.mensaje || 'No hay partidos pendientes por simular.');
                return;
            }
            iniciarPolling();
        } catch (e) {
            errorSimular.textContent = e.message;
            errorSimular.classList.remove('d-none');
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

    // Interruptor y ritmo: se guardan en el servidor (aplican para todos y siguen con el navegador cerrado)
    if (toggleAutoPlay) {
        toggleAutoPlay.addEventListener('change', async () => {
            const pedido = toggleAutoPlay.checked;
            toggleAutoPlay.disabled = true;
            try {
                await guardarPulso({ activo: pedido });
                UI.toast(pedido ? `Reproducción automática prendida: un partido cada ${pulso.intervalo_min} min` : 'Reproducción automática apagada',
                         { icono: pedido ? 'bi-play-circle-fill' : 'bi-pause-circle-fill' });
                cancelarAutoPlayProgramado();
                if (!panelInactivo.classList.contains('d-none') || !panelFinalizado.classList.contains('d-none')) programarAutoPlay();
            } catch (e) {
                toggleAutoPlay.checked = !pedido;
                UI.toast(e.message, { icono: 'bi-exclamation-triangle-fill' });
            } finally {
                toggleAutoPlay.disabled = false;
            }
        });
    }
    if (selectRitmo) {
        selectRitmo.addEventListener('change', async () => {
            try {
                await guardarPulso({ intervalo_min: Number(selectRitmo.value) });
                UI.toast(`Ritmo: un partido cada ${selectRitmo.value} min`, { icono: 'bi-clock-history' });
                cancelarAutoPlayProgramado();
                if (!panelInactivo.classList.contains('d-none') || !panelFinalizado.classList.contains('d-none')) programarAutoPlay();
            } catch (e) {
                UI.toast(e.message, { icono: 'bi-exclamation-triangle-fill' });
                if (pulso) selectRitmo.value = String(pulso.intervalo_min);
            }
        });
    }
    cargarPulso();

    // Al cargar la página: si ya hay un partido en curso (arrancado por otra pestaña/usuario),
    // lo detecta solo y empieza a pollear sin que haga falta tocar el botón.
    consultarEstado().then(() => {
        if (!panelEnVivo.classList.contains('d-none') && !pollHandle) {
            pollHandle = setInterval(consultarEstado, POLL_MS);
        }
    });
});

// ---------------------------------------------------------------------------------------------
// Accesos rápidos flotantes (#vivoAtajos en live_match.html): llevan a cada sección con
// desplazamiento suave, marcan la sección que se está viendo y muestran la Tabla solo si el
// partido tiene tabla de grupo (#panelTablaGrupo deja de estar oculto).
// ---------------------------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', function () {
    const barra = document.getElementById('vivoAtajos');
    if (!barra) return;
    const reducido = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const botones = [...barra.querySelectorAll('.vivo-atajos__btn')];
    const destino = btn => document.querySelector(btn.getAttribute('href'));

    botones.forEach(btn => btn.addEventListener('click', e => {
        const el = destino(btn);
        if (!el) return;
        e.preventDefault();
        el.scrollIntoView({ behavior: reducido ? 'auto' : 'smooth', block: 'start' });
        marcar(btn);
    }));

    function marcar(activo) {
        botones.forEach(b => b.classList.toggle('activo', b === activo));
    }

    // La Tabla de posiciones solo existe en fase de grupos: el botón sigue al panel
    const tabla = document.getElementById('panelTablaGrupo');
    const btnTabla = botones.find(b => b.hasAttribute('data-opcional'));
    const sincronizarTabla = () => { if (tabla && btnTabla) btnTabla.classList.toggle('d-none', tabla.classList.contains('d-none')); };
    sincronizarTabla();
    if (tabla) new MutationObserver(sincronizarTabla).observe(tabla, { attributes: true, attributeFilter: ['class'] });

    // Sección a la vista -> botón activo
    if ('IntersectionObserver' in window) {
        const porId = new Map(botones.map(b => [b.getAttribute('href').slice(1), b]));
        const espia = new IntersectionObserver(entradas => entradas.forEach(en => {
            if (en.isIntersecting && porId.has(en.target.id)) marcar(porId.get(en.target.id));
        }), { rootMargin: '-30% 0px -60% 0px' });
        botones.forEach(b => { const el = destino(b); if (el) espia.observe(el); });
    }
});
