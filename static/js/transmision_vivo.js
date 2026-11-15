/*
 * «Transmisión en Vivo» de /en-vivo: en lugar del listado de jugadas, una mesa de narradores que comentan el partido.
 *  - Con cadenas de TV de TU universo que lo transmiten: un televisor por cadena (1 o 2), con su mesa (2 comentaristas
 *    y el invitado), logo, marcador y rótulo con lo que dice quien habla.
 *  - Sin cadena (o sin sesión): una radio con un narrador genérico.
 * Cada jugada ya revelada la comenta alguien (static/js/narracion.js decide quién y qué dice); los mensajes no se acumulan:
 * sale uno y entra otro. Lo llama live_match.js en cada poll con el payload de GET /matches/live.
 */
(function () {
    'use strict';

    const raiz = document.getElementById('transmisionVivo');
    if (!raiz || !window.Narracion) return;

    const reducido = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const MAX_COLA = 5;          // mensajes pendientes por mesa
    const CADUCA_MS = 14000;     // un comentario de relleno que llega tarde ya no tiene sentido
    const SILENCIO_MIN = 6500;   // sin hablar, a los 6,5-11 s entra charla de relleno
    const SILENCIO_EXTRA = 4500;
    const FUNDIDO_MS = reducido ? 0 : 280;

    const ROLES = { narrador: 'Narrador', analista: 'Analista', invitado: 'Invitado', radio: 'Radio' };
    const e = (t) => (window.UI && UI.escapar ? UI.escapar(t) : String(t == null ? '' : t).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])));

    let est = null;   // estado del partido en curso (null = nada cargado)

    // ---------------------------------------------------------------- botón «Ver cronología completa»
    const btnCronologia = document.getElementById('btnVerCronologia');
    const bloqueCronologia = document.getElementById('bloqueCronologia');
    if (btnCronologia && bloqueCronologia) {
        btnCronologia.addEventListener('click', () => {
            const abre = bloqueCronologia.classList.contains('d-none');
            bloqueCronologia.classList.toggle('d-none', !abre);
            btnCronologia.setAttribute('aria-expanded', abre ? 'true' : 'false');
            btnCronologia.innerHTML = abre ? '<i class="bi bi-broadcast me-1"></i>Volver a la transmisión'
                : '<i class="bi bi-list-columns-reverse me-1"></i>Ver cronología completa';
            raiz.classList.toggle('d-none', abre);
        });
    }

    // ---------------------------------------------------------------- dibujo
    // El set es el <template id="tplSetTV"> de live_match.html (partials/set_tv.html): se clona y se completan los `data-slot` con la cadena,
    // el partido, los comentaristas y el invitado. Los colores y el logo viajan en variables CSS del contenedor (--primary-color,
    // --accent-color, --text-color, --logo-url): para otra televisora solo cambian esas cuatro.
    function slot(raiz, nombre) { return raiz.querySelector(`[data-slot="${nombre}"]`); }
    function ponerImg(raiz, nombre, url) {
        const img = slot(raiz, nombre);
        if (!img) return;
        if (url) { img.src = url; img.hidden = false; img.onerror = () => { img.hidden = true; }; } else img.hidden = true;
    }
    function rostroImg(url) { return url ? `<img src="${e(url)}" alt="" loading="lazy" decoding="async" onerror="this.remove()">` : '<i class="bi bi-person-fill"></i>'; }
    function dibujarTV(mesa, i) {
        const plantilla = document.getElementById('tplSetTV');
        if (!plantilla) return '';
        const t = mesa.tele, com = mesa.comentaristas || [], d = est.ultimo || {};
        const narr = com.find(c => c.rol === 'narrador') || com[0], anal = com.find(c => c.rol === 'analista') || com[1];
        const inv = mesa.invitado;
        const nodo = plantilla.content.firstElementChild.cloneNode(true);
        nodo.dataset.mesa = i;
        nodo.style.setProperty('--primary-color', t.color);
        nodo.style.setProperty('--accent-color', t.color2);
        nodo.style.setProperty('--logo-url', t.logo ? `url("${t.logo}")` : 'none');
        const mosca = slot(nodo, 'mosca');
        if (mosca) mosca.innerHTML = t.logo ? `<img src="${e(t.logo)}" alt="${e(t.nombre)}" onerror="this.remove()">` : e(t.nombre);
        const origen = slot(nodo, 'origen');
        if (origen) {
            if (t.pais) { slot(nodo, 'origen-nombre').textContent = t.pais; ponerImg(nodo, 'origen-icono', imagenPais(t.pais_id, 'icono')); origen.hidden = false; origen.title = 'Televisora de ' + t.pais; }
            else origen.remove();
        }
        slot(nodo, 'bisel').textContent = t.nombre + (t.lema ? ' · ' + t.lema : '');
        ponerImg(nodo, 'estadio', d.estadio_img);
        ponerImg(nodo, 'escudo-local', imagenPais(d.id_local, 'escudo'));
        ponerImg(nodo, 'escudo-visita', imagenPais(d.id_visita, 'escudo'));
        [['analista', anal], ['narrador', narr]].forEach(([rol, c]) => {
            slot(nodo, rol + '-rostro').innerHTML = rostroImg(c && c.avatar_url);
            slot(nodo, rol + '-nombre').textContent = (c && c.nombre) || ROLES[rol];
        });
        if (inv) {
            slot(nodo, 'invitado-rostro').innerHTML = window.UI ? UI.avatar(inv.jugador_id, inv.pais_id, '') : '';
            slot(nodo, 'invitado-nombre').textContent = inv.nombre;
        } else nodo.querySelectorAll('.tv-asiento--invitado, .tv-placa--invitado').forEach(n => n.remove());
        return nodo.outerHTML;
    }
    // goleadores del partido en la pantalla LED de la derecha: solo los goles ya revelados (sin tanda), con su país y minuto
    function pintarGoles(data) {
        if (!est || est.modo !== 'tv' || !window.Narracion) return;
        const eventos = data.eventos || [];
        const goles = eventos.filter(ev => window.Narracion.clasificar(ev) === 'gol' && ev.periodo !== 5 && !(ev.tipo || '').includes('TANDA') && !(ev.tipo || '').includes('GOL DE PENAL') && (ev.jugadores || [])[0]);
        const firma = goles.map(g => g.jugadores[0] + g.minuto).join('|');
        if (firma === est.firmaGoles) return;
        est.firmaGoles = firma;
        const html = goles.slice(-4).map(g => {
            const m = Math.floor(g.minuto) + (g.adicional ? '+' + g.adicional : '');
            return `<li><b>${e(g.jugadores[0])}</b><small>${e(g.equipo)} · ${m}'</small></li>`;
        }).join('');
        est.mesas.forEach(mesa => { const ul = mesa.raiz && mesa.raiz.querySelector('[data-slot="goles"]'); if (ul) ul.innerHTML = html; });
    }
    function dibujarRadio() {
        return `<div class="radio-set" data-mesa="0">
            <div class="radio-set__aparato" aria-hidden="true">
                <span class="radio-set__antena"></span>
                <div class="radio-set__cuerpo">
                    <div class="radio-set__parlante"><span></span></div>
                    <div class="radio-set__panel">
                        <div class="radio-set__dial"><i class="radio-set__aguja"></i><span>88</span><span>94</span><span>100</span><span>106</span></div>
                        <div class="radio-set__eq"><i></i><i></i><i></i><i></i><i></i><i></i></div>
                        <div class="radio-set__perillas"><b></b><b></b><em class="radio-set__aire">ON AIR</em></div>
                    </div>
                </div>
            </div>
            <div class="radio-set__escena">
                <div class="radio-set__locutor" data-rol="radio"><span class="radio-set__rostro"><i class="bi bi-person-fill"></i><i class="bi bi-mic-fill radio-set__mic"></i></span></div>
                <div class="radio-set__globo"><span class="tv-set__quien"></span><p class="tv-set__texto"></p></div>
            </div>
            <div class="radio-set__marcador" data-hud><b data-hud-local></b><i data-hud-goles>0 - 0</i><b data-hud-visita></b><em data-hud-min></em></div>
        </div>`;
    }

    // ---------------------------------------------------------------- arranque por partido
    async function cargarMesa() {
        try {
            const resp = await fetch('/matches/live/transmision');
            if (!resp.ok) throw new Error(resp.status);
            return await resp.json();
        } catch (err) {
            return { modo: 'radio', mesas: [] };
        }
    }

    async function iniciar(data) {
        const matchId = data.match_id;
        detener();
        est = { matchId, listo: false, cursor: null, mesas: [], colas: [], ultimo: data, narrador: null, tele: [], ultimoMarcador: Date.now(),
                patro: { paises: {}, jugadores: {} }, datosUsados: [], plecasUsadas: [], ultimoDato: Date.now() };
        const info = await cargarMesa();
        if (!est || est.matchId !== matchId) return;   // cambió el partido mientras cargaba
        const modo = info.modo === 'tv' && (info.mesas || []).length ? 'tv' : 'radio';
        const mesas = modo === 'tv' ? info.mesas.slice(0, 2) : [{}];
        raiz.innerHTML = modo === 'tv' ? `<div class="tv-vivo__mesas tv-vivo__mesas--${mesas.length}">${mesas.map(dibujarTV).join('')}</div>` : dibujarRadio();
        raiz.dataset.modo = modo;
        est.modo = modo;
        est.narrador = window.Narracion.crear({
            matchId, local: data.local, visitante: data.visitante, idLocal: data.id_local, idVisita: data.id_visita,
            estadio: data.estadio, fase: data.fase_id, paisDe: nombre => plantillas.paises[nombre], modo, mesas: modo === 'tv' ? mesas : [],
        });
        est.tele = modo === 'tv' ? mesas.map(m => m.tele || {}) : [];
        est.voces = modo === 'tv' ? (info.voces || []) : [];
        est.vocesUsadas = [];
        est.convenios = modo === 'tv' ? mesas.map(m => m.convenios || []) : [];
        est.patro = modo === 'tv' ? Object.assign({ paises: {}, jugadores: {} }, info.patrocinadores || {}) : { paises: {}, jugadores: {} };
        est.mesas = mesas.map((_, i) => ({
            raiz: raiz.querySelector(`[data-mesa="${i}"]`), mostrando: null, timer: null, ultimaFin: Date.now(), fundido: null,
            grafico: null, graficoPrio: 0, graficoTimer: null, ultimoMarcador: Date.now() + i * 40000,
        }));
        est.colas = mesas.map(() => []);
        est.cursor = (data.eventos || []).length;   // no se cuenta la historia: se narra desde aquí
        est.listo = true;
        actualizarHud(data);
        if (data.finalizado) { est.despedida = true; est.mesas.forEach((_, i) => mostrarCierre(i)); return; }
        est.mesas.forEach((_, i) => programar(i));
        // saludo al entrar (si no hay nada más que decir)
        const saludo = est.narrador.charla(contexto(data), 0);
        if (saludo) encolar([Object.assign(saludo, { prio: 1 })], Date.now() + 400);
    }

    function detener() {
        if (!est) return;
        (est.mesas || []).forEach(m => { clearTimeout(m.timer); clearTimeout(m.fundido); clearTimeout(m.graficoTimer); });
        est = null;
    }

    // ---------------------------------------------------------------- gráficos de transmisión (como en la TV)
    // Tarjeta de jugador (gol, amonestado, expulsado, portero que ataja un penal) y el «comercial» del marcador con el estadio
    // de fondo y, al final, el logo de la cadena. Solo en la televisión: la radio no tiene pantalla.
    let plantillas = { ids: {}, dorsales: {}, posiciones: {}, paises: {}, arbitros: {}, planteamiento: {} };   // las completa live_match.js (GET /matches/live/plantillas)
    const GRAFICO_MS = { jugador: 6800, marcador: 6200, dato: 9600, penal: 5000, cambio: 4600, arbitro: 6800, tanda: 4600 };   // la tarjeta de jugador y el dato terminan con el logo
    const ACCION_TXT = { gol: 'GOL', amarilla: 'TARJETA AMARILLA', roja: 'TARJETA ROJA', atajo: 'PENAL ATAJADO', lesion: 'LESIÓN' };
    const ROL_ARBITRO = { central: 'Árbitro central', linea1: 'Juez de línea', linea2: 'Juez de línea', cuarto: 'Cuarto árbitro', var: 'Árbitro VAR' };

    function equipoId(nombre) {
        const d = est && est.ultimo;
        if (!d || !nombre) return null;
        return nombre === d.local ? d.id_local : (nombre === d.visitante ? d.id_visita : null);
    }
    function ordinal(n) { return `${n}.º`; }
    // con dos cadenas, la que tiene los derechos del equipo del evento (si no, la primera)
    function mesaDelEquipo(nombre) {
        const id = equipoId(nombre);
        const k = est.tele.findIndex(t => t && id != null && t.pais_id === id);
        return k >= 0 ? k : 0;
    }
    function imagenPais(id, tipo) { return window.UI && UI.urlImagenPais ? UI.urlImagenPais(id, tipo) : null; }

    // cierre común de las tarjetas: cortina con los colores y logo de la cadena (como al final del comercial del marcador)
    function cierreCadena(i) {
        const t = (est && est.tele[i]) || {};
        return `<span class="tv-gfx__cortina"></span><div class="tv-gfx__cadena">${t.logo ? `<img src="${e(t.logo)}" alt="${e(t.nombre)}" onerror="this.remove()">` : `<b>${e(t.nombre || '')}</b>`}${t.lema ? `<small>${e(t.lema)}</small>` : ''}</div>`;
    }
    function carita(nombre, clase = '') {
        const id = plantillas.ids[nombre];
        const img = id != null && window.UI && UI.urlAvatar ? `<img src="${e(UI.urlAvatar(id))}" alt="" decoding="async" onerror="this.remove()">` : '<i class="bi bi-person-fill"></i>';
        return `<span class="tv-gfx__cara ${clase}">${img}</span>`;
    }

    function htmlJugador(g, mesa) {
        const paisId = equipoId(g.equipo);
        const id = plantillas.ids[g.jugador];
        const dorsal = plantillas.dorsales[g.jugador];
        const pos = window.Narracion.POSICIONES[plantillas.posiciones[g.jugador]] || '';
        const bandera = imagenPais(paisId, 'plana'), escudo = imagenPais(paisId, 'escudo');
        const cara = id != null && window.UI && UI.urlAvatar ? `<img src="${e(UI.urlAvatar(id))}" alt="" decoding="async" onerror="this.remove()">` : '<i class="bi bi-person-fill"></i>';
        let detalle = '';
        if (g.accion === 'gol') {
            const l1 = g.nGol > 1 ? `${ordinal(g.nGol)} gol en el partido` : (g.titulo === 'GOL' ? 'Abre su cuenta en el partido' : '');
            detalle = [l1, g.asistente ? `Asistencia: ${e(g.asistente)}` : (g.portero ? `Anota ante ${e(g.portero)}` : '')].filter(Boolean).map(t => `<span>${t}</span>`).join('');
        } else if (g.accion === 'amarilla') detalle = `<span>${g.rival ? 'Falta sobre ' + e(g.rival) : 'Primera advertencia'}</span>`;
        else if (g.accion === 'roja') detalle = `<span>${e(g.motivo || '')}</span><span>Su equipo se queda con uno menos</span>`;
        else if (g.accion === 'atajo') detalle = `<span>Detuvo el disparo de ${e(g.tirador)}</span>`;
        else if (g.accion === 'lesion') detalle = [g.lesion ? `<span>${e(g.lesion.charAt(0).toUpperCase() + g.lesion.slice(1))}${g.gravedad ? ` · ${e(g.gravedad)}` : ''}</span>` : '',
            `<span>${g.sale ? 'Sale del campo' : 'Sigue en el campo, tocado'}</span>`, g.sinCambio ? '<span>Su equipo se queda con uno menos</span>' : ''].join('');
        const nombre = e(g.jugador);
        return `<div class="tv-gfx tv-gfx--jugador tv-gfx--${g.accion}" style="${bandera ? `--bandera:url('${e(bandera)}');` : ''}">
            <div class="tv-gfx__fondo">${escudo ? `<img class="tv-gfx__escudo" src="${e(escudo)}" alt="" onerror="this.remove()">` : ''}</div>
            <span class="tv-gfx__barrido"></span>
            <div class="tv-gfx__rostro"><span>${cara}</span>${dorsal != null ? `<b class="tv-gfx__dorsal">${e(dorsal)}</b>` : ''}</div>
            <div class="tv-gfx__cuerpo">
                <small class="tv-gfx__tag">${ACCION_TXT[g.accion] || e(g.titulo)}${g.minuto != null ? ` · ${Math.floor(g.minuto)}'` : ''}</small>
                <strong class="tv-gfx__titulo">${e(g.titulo)}</strong>
                <span class="tv-gfx__nombre">${nombre}</span>
                <span class="tv-gfx__meta">${[pos, e(g.equipo || '')].filter(Boolean).join(' · ')}</span>
                <span class="tv-gfx__detalle">${detalle}</span>
            </div>${cierreCadena(mesa)}</div>`;
    }

    // penal señalado: el área con el punto penal, quién recibió la falta y quién la cometió
    function htmlPenal(g, mesa) {
        const paisId = equipoId(g.equipo);
        const bandera = imagenPais(paisId, 'plana'), escudo = imagenPais(paisId, 'escudo');
        return `<div class="tv-gfx tv-gfx--jugador tv-gfx--penal" style="${bandera ? `--bandera:url('${e(bandera)}');` : ''}">
            <div class="tv-gfx__fondo">${escudo ? `<img class="tv-gfx__escudo" src="${e(escudo)}" alt="" onerror="this.remove()">` : ''}</div>
            <span class="tv-gfx__barrido"></span>
            <div class="tv-gfx__area" aria-hidden="true"><svg viewBox="0 0 200 130">
                <rect x="2" y="2" width="196" height="126" rx="3" class="area-linea"/><rect x="58" y="2" width="84" height="26" class="area-linea"/>
                <rect x="18" y="2" width="164" height="62" class="area-linea"/><path d="M78 64 A24 24 0 0 0 122 64" class="area-linea"/>
                <circle cx="100" cy="46" r="3" class="area-punto"/><circle cx="100" cy="46" r="3" class="area-onda"/><circle cx="100" cy="112" r="5.5" class="area-balon"/></svg></div>
            <div class="tv-gfx__cuerpo">
                <small class="tv-gfx__tag">PENAL${g.minuto != null ? ` · ${Math.floor(g.minuto)}'` : ''}</small>
                <strong class="tv-gfx__titulo">¡PENAL!</strong>
                <span class="tv-gfx__nombre">a favor de ${e(g.equipo || '')}</span>
                <div class="tv-gfx__duelo">
                    <span class="tv-gfx__duelista tv-gfx__duelista--v">${carita(g.victima)}<b>${e(g.victima)}</b><small>recibe la falta</small></span>
                    <i class="bi bi-lightning-charge-fill"></i>
                    <span class="tv-gfx__duelista tv-gfx__duelista--i">${carita(g.infractor)}<b>${e(g.infractor)}</b><small>comete la falta</small></span>
                </div></div></div>`;
    }

    // el rostro del árbitro (de plantillas.arbitros: {rol: {nombre, url}}); si el evento no trae el nombre se usa el del puesto
    function arbitroDe(g) {
        const a = plantillas.arbitros || {};
        if (g.arbitro) for (const r of Object.keys(a)) if (a[r] && a[r].nombre === g.arbitro) return { nombre: g.arbitro, url: a[r].url };
        const x = a[g.rol] || a.central || {};
        return { nombre: g.arbitro || x.nombre || '', url: g.arbitro ? null : x.url };
    }
    // pitidos, tiempo añadido, alargue y VAR: tarjeta con el árbitro que lo marca
    function htmlArbitro(g, mesa) {
        const ar = arbitroDe(g);
        const cara = ar.url ? `<img src="${e(ar.url)}" alt="" decoding="async" onerror="this.remove()">` : '<i class="bi bi-person-fill"></i>';
        const extra = g.clase === 'anadido' && g.minutos != null ? `<span class="tv-gfx__anadido" title="Minutos añadidos">+${e(g.minutos)}<small>MIN</small></span>` : '';
        const marca = g.minuto != null ? `${Math.floor(g.minuto)}${g.adicional ? '+' + g.adicional : ''}'` : '';
        return `<div class="tv-gfx tv-gfx--jugador tv-gfx--arbitro tv-gfx--arb-${e(g.clase)}">
            <div class="tv-gfx__fondo"></div><span class="tv-gfx__barrido"></span>
            <div class="tv-gfx__rostro"><span>${cara}</span><b class="tv-gfx__dorsal tv-gfx__dorsal--rol"><i class="bi bi-flag-fill"></i></b></div>
            <div class="tv-gfx__cuerpo">
                <small class="tv-gfx__tag">${e(g.rotulo)}${marca ? ` · ${marca}` : ''}</small>
                <strong class="tv-gfx__titulo tv-gfx__titulo--largo">${e(g.titulo)}</strong>
                <span class="tv-gfx__nombre">${e(ar.nombre)}</span>
                <span class="tv-gfx__meta">${e(ROL_ARBITRO[g.rol] || 'Árbitro')}</span>
                ${extra}${g.detalle ? `<span class="tv-gfx__detalle"><span>${e(g.detalle)}</span></span>` : ''}
            </div>${cierreCadena(mesa)}</div>`;
    }
    // tanda de penales: marcador con los cobros de cada equipo (● gol, ✕ fallado) y el último cobro
    function htmlTanda(g, mesa) {
        const d = est.ultimo || {}, t = g.estado || { rl: [], rv: [], gl: 0, gv: 0, subita: false, decidida: false };
        const escL = imagenPais(d.id_local, 'escudo'), escV = imagenPais(d.id_visita, 'escudo');
        const casillas = Math.max(5, t.rl.length, t.rv.length);
        const puntos = (r) => Array.from({ length: casillas }, (_, k) => `<i class="tv-gfx__tiro ${r[k] === true ? 'tv-gfx__tiro--gol' : (r[k] === false ? 'tv-gfx__tiro--falla' : '')}${k === r.length - 1 && g.fase === 'cobro' ? ' es-ultimo' : ''}">${r[k] === true ? '<i class="bi bi-circle-fill"></i>' : (r[k] === false ? '<i class="bi bi-x-lg"></i>' : '')}</i>`).join('');
        const fila = (nombre, esc, r, goles) => `<div class="tv-gfx__tanda-fila ${g.equipo === nombre ? 'es-tirador' : ''}">${esc ? `<img src="${e(esc)}" alt="" onerror="this.remove()">` : ''}<b>${e(nombre)}</b><span class="tv-gfx__tiros">${puntos(r)}</span><em>${goles}</em></div>`;
        let pie = '';
        if (g.fase === 'inicio') pie = '<span>El ganador se decide desde el punto penal</span>';
        else if (g.resultado === 'gol') pie = `<span class="ok"><i class="bi bi-check-circle-fill"></i>${e(g.tirador)} anota</span>`;
        else if (g.resultado === 'atajado') pie = `<span class="mal"><i class="bi bi-hand-index-thumb-fill"></i>${e(g.portero)} ataja el disparo de ${e(g.tirador)}</span>`;
        else pie = `<span class="mal"><i class="bi bi-slash-circle-fill"></i>Penal anulado a ${e(g.tirador)}</span>`;
        if (t.decidida) pie += `<span class="gana"><i class="bi bi-trophy-fill"></i>Gana ${e(t.ganador)}</span>`;
        return `<div class="tv-gfx tv-gfx--jugador tv-gfx--tanda">
            <div class="tv-gfx__fondo"></div><span class="tv-gfx__barrido"></span>
            <div class="tv-gfx__tanda">
                <small class="tv-gfx__tag">${t.subita ? 'MUERTE SÚBITA' : 'TANDA DE PENALES'}</small>
                ${fila(d.local, escL, t.rl, t.gl)}${fila(d.visitante, escV, t.rv, t.gv)}
                <div class="tv-gfx__tanda-pie">${pie}</div>
            </div></div>`;
    }

    // cambio: sale uno (rojo), entra otro (verde)
    function htmlCambio(g, mesa) {
        const paisId = equipoId(g.equipo);
        const bandera = imagenPais(paisId, 'plana'), escudo = imagenPais(paisId, 'escudo');
        const lado = (nombre, clase, etiqueta) => `<div class="tv-gfx__movimiento tv-gfx__movimiento--${clase}">${carita(nombre)}${plantillas.dorsales[nombre] != null ? `<b class="tv-gfx__dorsal">${e(plantillas.dorsales[nombre])}</b>` : ''}<strong>${e(nombre)}</strong><em><i class="bi bi-arrow-${clase === 'sale' ? 'down' : 'up'}-circle-fill"></i>${etiqueta}</em></div>`;
        return `<div class="tv-gfx tv-gfx--jugador tv-gfx--cambio" style="${bandera ? `--bandera:url('${e(bandera)}');` : ''}">
            <div class="tv-gfx__fondo">${escudo ? `<img class="tv-gfx__escudo" src="${e(escudo)}" alt="" onerror="this.remove()">` : ''}</div>
            <span class="tv-gfx__barrido"></span>
            <div class="tv-gfx__cambio">
                <small class="tv-gfx__tag">CAMBIO${g.minuto != null ? ` · ${Math.floor(g.minuto)}'` : ''} · ${e(g.equipo || '')}</small>
                <div class="tv-gfx__cambio-fila">${lado(g.sale, 'sale', 'SALE')}<i class="bi bi-arrow-left-right tv-gfx__flecha"></i>${lado(g.entra, 'entra', 'ENTRA')}</div>
            </div></div>`;
    }

    // dato del partido «presentado por» el dueño de una marca patrocinadora (o, sin patrocinador, por el analista de la mesa)
    function marcaDelDato(dato, i) {
        const p = est.patro || { paises: {}, jugadores: {} };
        const conDueno = lista => (lista || []).filter(m => m.dueno && m.dueno.nombre);
        // con convenio: la cadena que transmite prefiere a una de SUS marcas aliadas (a veces; sin dinero, solo presentación)
        const conv = conDueno((est.convenios || [])[i]);
        if (conv.length && Math.random() < 0.55) return { ...conv[Math.floor(Math.random() * conv.length)], convenio: true };
        const id = plantillas.ids[dato.jugador];
        let lista = conDueno(p.jugadores[String(id)]);                                   // 1.º: quien patrocina al propio jugador
        if (!lista.length) lista = conDueno(p.paises[String(equipoId(dato.equipo))]);    // 2.º: quien patrocina a su selección
        if (!lista.length) lista = [].concat(...Object.values(p.paises).map(conDueno));  // 3.º: cualquiera de las dos selecciones
        if (lista.length) return lista[Math.floor(Math.random() * lista.length)];
        return conv.length ? { ...conv[Math.floor(Math.random() * conv.length)], convenio: true } : null;
    }
    function htmlDato(i, d) {
        const marca = d.marca, t = est.tele[i] || {};
        const m = est.mesas[i];
        const analista = m && m.raiz.querySelector('.tv-asiento--analista .tv-asiento__rostro img');
        const quien = marca ? marca.dueno.nombre : (m.raiz.querySelector('.tv-placa--analista b') || {}).textContent || 'El analista';
        const rostro = marca ? (marca.dueno.avatar_url ? `<img src="${e(marca.dueno.avatar_url)}" alt="" onerror="this.remove()">` : '<i class="bi bi-person-fill"></i>')
                             : (analista ? `<img src="${e(analista.src)}" alt="">` : '<i class="bi bi-person-fill"></i>');
        const presenta = window.Narracion.PRESENTA[Math.floor(Math.random() * window.Narracion.PRESENTA.length)].replace('{quien}', `<b>${e(quien)}</b>`);
        const paisId = equipoId(d.equipo);
        const bandera = imagenPais(paisId, 'plana'), escudo = imagenPais(paisId, 'escudo');
        const pos = window.Narracion.POSICIONES[plantillas.posiciones[d.jugador]] || '';
        const colores = marca ? `--tv:${e(marca.color)};--tv2:${e(marca.color2)};` : '';
        const cierre = marca
            ? `<span class="tv-gfx__cortina"></span><div class="tv-gfx__cadena tv-gfx__cadena--marca">${marca.logo ? `<img src="${e(marca.logo)}" alt="${e(marca.nombre)}" onerror="this.remove()">` : `<b>${e(marca.nombre)}</b>`}${marca.lema ? `<small>${e(marca.lema)}</small>` : ''}<span class="tv-gfx__marca-pie">${marca.convenio ? `Marca aliada de ${e(t.nombre || 'la cadena')}` : 'Patrocinador oficial'}</span></div>`
            : cierreCadena(i);
        return `<div class="tv-gfx tv-gfx--dato" style="${colores}${bandera ? `--bandera:url('${e(bandera)}');` : ''}">
            <div class="tv-gfx__dato-fondo"></div>
            <div class="tv-gfx__presenta"><span class="tv-gfx__presenta-cara">${rostro}</span><span class="tv-gfx__presenta-texto">${presenta}</span>${marca ? `<small>${e(marca.nombre)}</small>` : '<small>Análisis de la transmisión</small>'}</div>
            <div class="tv-gfx__dato">
                <small class="tv-gfx__tag">${e(d.etiqueta)}</small>
                <strong class="tv-gfx__titulo">${e(d.titulo)}</strong>
                <div class="tv-gfx__dato-jugador">${carita(d.jugador)}
                    <div><b>${e(d.jugador)}</b><small>${escudo ? `<img src="${e(escudo)}" alt="" onerror="this.remove()">` : ''}${[e(d.equipo || ''), pos].filter(Boolean).join(' · ')}</small></div></div>
                <span class="tv-gfx__dato-cifra">${e(d.cifra)}</span>
            </div>${cierre}</div>`;
    }
    // marca que patrocina un tablero: una aliada de la cadena (la mayoría de las veces) o cualquiera de las del partido
    function marcaDePleca(i) {
        const conDueno = lista => (lista || []).filter(m => m.dueno && m.dueno.nombre);
        const conv = conDueno((est.convenios || [])[i]);
        const p = est.patro || { paises: {}, jugadores: {} };
        const partido = [].concat(...Object.values(p.paises).map(conDueno), ...Object.values(p.jugadores).map(conDueno));
        const pool = conv.length && (!partido.length || Math.random() < 0.7) ? conv.map(m => ({ ...m, convenio: true })) : partido;
        return pool.length ? pool[Math.floor(Math.random() * pool.length)] : null;
    }
    // al arrancar, el planteamiento de los dos equipos presentado por una marca (después del árbitro y del comercial del marcador)
    function mostrarFormacion(i) {
        if (!est || est.modo !== 'tv' || !est.mesas[i] || est.mesas[i].cerrada) return;
        const pl = window.Narracion.plecaFormacion(plantillas.planteamiento, datosPartido());
        if (pl) mostrarPleca(i, pl);
    }
    function datosPartido() {
        const u = est.ultimo || {};
        return { local: u.local, visitante: u.visitante, siglaLocal: u.siglas_local || u.local, siglaVisita: u.siglas_visitante || u.visitante };
    }

    // ---------------------------------------------------------------- pleca patrocinada (lower third)
    // Un dato a la vez, debajo de los comentaristas: círculo con el logo del patrocinador, barra de color con «<marca> presenta …» y
    // barra blanca con el dato. Va en su propia capa: no corta la narración ni las tarjetas (una tarjeta importante la retira).
    // pleca de COMENTARIO: es de la televisora (sus colores, sin marca): el rostro de quien habla en el círculo, «nombre · cargo» arriba
    // (con el logo del medio si es periodista) y «#TAG comentario» abajo
    function htmlPlecaComentario(i, d) {
        const t = est.tele[i] || {}, v = d.voz;
        const url = v.jugador_id && window.UI && UI.urlAvatar ? UI.urlAvatar(v.jugador_id) : v.avatar_url;
        const rostro = url ? `<img class="tv-pleca__rostro" src="${e(url)}" alt="" onerror="this.remove()">` : '<i class="bi bi-person-fill"></i>';
        const colores = t.color ? `--tv:${e(t.color)};--tv2:${e(t.color2)};` : '';
        return `<div class="tv-pleca tv-pleca--comenta" style="${colores}">
            <span class="tv-pleca__persona">${rostro}</span>
            <div class="tv-pleca__barra">
                <div class="tv-pleca__sup"><span><b>${e(v.nombre)}</b> · ${e(v.cargo)}</span>${v.medio_logo ? `<img class="tv-pleca__medio" src="${e(v.medio_logo)}" alt="${e(v.medio || '')}" onerror="this.remove()">` : ''}</div>
                <div class="tv-pleca__inf"><span><b class="tv-pleca__tag">${e(d.tag)}</b> ${e(d.texto)}</span></div>
            </div></div>`;
    }
    function htmlPleca(i, d) {
        const t = est.tele[i] || {}, marca = d.marca;
        const nombre = marca ? marca.nombre : (t.nombre || 'La transmisión');
        const logo = marca ? (marca.logo ? `<img src="${e(marca.logo)}" alt="" onerror="this.remove()">` : `<b>${e(marca.nombre.slice(0, 2))}</b>`)
                           : (t.logo ? `<img src="${e(t.logo)}" alt="" onerror="this.remove()">` : '<i class="bi bi-broadcast"></i>');
        const colores = marca ? `--tv:${e(marca.color)};--tv2:${e(marca.color2)};` : '';
        return `<div class="tv-pleca" style="${colores}">
            <span class="tv-pleca__aro"><span class="tv-pleca__logo">${logo}</span></span>
            <div class="tv-pleca__barra">
                <div class="tv-pleca__sup"><span><b>${e(nombre)}</b> presenta ${e(d.tema)}</span></div>
                <div class="tv-pleca__inf"><span>${e(d.texto)}</span></div>
            </div></div>`;
    }
    function retirarPleca(m) {
        const cont = m.raiz.querySelector('.tv-set__pleca');
        clearTimeout(m.plecaTimer); m.pleca = false;
        if (cont) { cont.className = 'tv-set__pleca'; cont.innerHTML = ''; }
    }
    function mostrarPleca(i, d) {
        if (!est || est.modo !== 'tv') return false;
        const m = est.mesas[i], cont = m && m.raiz.querySelector('.tv-set__pleca');
        if (!cont || m.cerrada || m.pleca) return false;
        if (m.grafico && m.graficoPrio >= 3) return false;
        if (!d.voz) d.marca = d.marca || marcaDePleca(i);
        m.pleca = true; m.ultimaPleca = Date.now();
        cont.innerHTML = d.voz ? htmlPlecaComentario(i, d) : htmlPleca(i, d);
        cont.className = 'tv-set__pleca is-activo' + (d.voz ? ' tv-set__pleca--comenta' : '');
        clearTimeout(m.plecaTimer);
        m.plecaTimer = setTimeout(() => {
            cont.classList.add('is-saliendo');
            m.plecaTimer = setTimeout(() => { cont.className = 'tv-set__pleca'; cont.innerHTML = ''; m.pleca = false; }, reducido ? 0 : 900);
        }, reducido ? 5000 : (d.voz ? 9500 : 7200));
        return true;
    }
    // un comentario de alguien que opina del partido (más peso a los de las dos selecciones que a los del grupo), sin repetir a los últimos 5
    function elegirComentario(u) {
        const voces = (est.voces || []).filter(v => !est.vocesUsadas.includes(v.nombre));
        if (!voces.length) return null;
        const p = datosPartido();
        p.golesLocal = u.goles_local; p.golesVisita = u.goles_visitante; p.minuto = u.minuto_actual;
        const peso = v => (v.lado === 'local' || v.lado === 'visita') ? 3 : 1;
        for (let n = 0; n < 6; n++) {
            let r = Math.random() * voces.reduce((a, v) => a + peso(v), 0), voz = voces[0];
            for (const v of voces) { r -= peso(v); if (r <= 0) { voz = v; break; } }
            const c = window.Narracion.comentario(voz, p, u.eventos, Math.random);
            if (c) return { voz, tag: c.tag, texto: c.texto, clave: 'c-' + voz.nombre };
        }
        return null;
    }
    // cada cierto tiempo (más a menudo que los datos de pantalla completa) sale una pleca con UN dato al azar
    function quizaPleca() {
        if (!est || est.modo !== 'tv' || !window.Narracion.elegirPleca || !est.ultimo || est.ultimo.finalizado) return;
        const u = est.ultimo, ahora = Date.now();
        if (u.minuto_actual < 5) return;
        est.mesas.forEach((m, i) => {
            if (m.cerrada || m.pleca || (m.grafico && m.grafico !== 'marcador') || ahora - (m.ultimaPleca || 0) < 55000 + i * 20000 || Math.random() > 0.45) return;
            const d = (Math.random() < 0.4 && elegirComentario(u)) || window.Narracion.elegirPleca(u.eventos, datosPartido(), est.plecasUsadas, Math.random);
            if (!d) return;
            if (mostrarPleca(i, d)) {
                if (d.voz) { est.vocesUsadas.push(d.voz.nombre); if (est.vocesUsadas.length > 5) est.vocesUsadas.shift(); }
                else { est.plecasUsadas.push(d.clave); if (est.plecasUsadas.length > 6) est.plecasUsadas.shift(); }
            }
        });
    }
    function htmlMarcador(i) {
        const d = est.ultimo || {}, t = est.tele[i] || {};
        const escL = imagenPais(d.id_local, 'escudo'), escV = imagenPais(d.id_visita, 'escudo');
        const fase = [d.grupo ? (String(d.grupo).startsWith('Grupo') ? d.grupo : 'Grupo ' + d.grupo) : '', d.estadio].filter(Boolean).join(' · ');
        return `<div class="tv-gfx tv-gfx--marcador">
            ${d.estadio_img ? `<div class="tv-gfx__estadio"><img src="${e(d.estadio_img)}" alt="" onerror="this.remove()"></div>` : ''}
            <div class="tv-gfx__velo"></div>
            <div class="tv-gfx__tablero">
                <div class="tv-gfx__equipo">${escL ? `<img src="${e(escL)}" alt="" onerror="this.remove()">` : ''}<b>${e(d.siglas_local || d.local)}</b></div>
                <div class="tv-gfx__cuenta"><strong>${e(d.goles_local)} - ${e(d.goles_visitante)}</strong><em>${e(d.finalizado ? 'FINAL' : minutoTexto(d))}</em></div>
                <div class="tv-gfx__equipo tv-gfx__equipo--v"><b>${e(d.siglas_visitante || d.visitante)}</b>${escV ? `<img src="${e(escV)}" alt="" onerror="this.remove()">` : ''}</div>
                ${fase ? `<small class="tv-gfx__fase">${e(fase)}</small>` : ''}
            </div>
            <span class="tv-gfx__cortina"></span>
            <div class="tv-gfx__cadena">${t.logo ? `<img src="${e(t.logo)}" alt="${e(t.nombre)}" onerror="this.remove()">` : `<b>${e(t.nombre || '')}</b>`}${t.lema ? `<small>${e(t.lema)}</small>` : ''}</div>
        </div>`;
    }

    // tipo: 'jugador' (gol, tarjetas, penal atajado), 'penal', 'cambio', 'dato' o 'marcador'. Una pieza a la vez por televisor: la de
    // `prio` 3 (gol, expulsión, penal) interrumpe a lo que esté en pantalla; las demás esperan a que termine la actual.
    function mostrarGrafico(i, tipo, datos) {
        if (!est || !est.listo || est.modo !== 'tv') return false;
        const m = est.mesas[i];
        const cont = m && m.raiz.querySelector('.tv-set__grafico');
        if (!cont || m.cerrada) return false;
        const prio = (datos && datos.prio) || 1;
        if (m.grafico && prio < 3 && prio <= m.graficoPrio) return false;
        if (prio >= 3 && m.pleca) retirarPleca(m);
        clearTimeout(m.graficoTimer);
        m.grafico = tipo; m.graficoPrio = prio;
        const html = { jugador: () => htmlJugador(datos, i), arbitro: () => htmlArbitro(datos, i), tanda: () => htmlTanda(datos, i), penal: () => htmlPenal(datos, i), cambio: () => htmlCambio(datos, i), dato: () => htmlDato(i, datos), marcador: () => htmlMarcador(i) };
        cont.innerHTML = html[tipo]();
        cont.className = `tv-set__grafico tv-set__grafico--${tipo === 'arbitro' ? 'jugador' : tipo} is-activo`;   // el árbitro usa la misma animación que la tarjeta de jugador
        m.raiz.classList.add('con-grafico');
        const dur = (reducido ? 0.6 : 1) * GRAFICO_MS[tipo];
        m.graficoTimer = setTimeout(() => {
            cont.classList.add('is-saliendo');
            m.graficoTimer = setTimeout(() => {
                cont.className = 'tv-set__grafico'; cont.innerHTML = ''; m.grafico = null; m.graficoPrio = 0; m.raiz.classList.remove('con-grafico');
            }, reducido ? 0 : 450);
        }, dur);
        if (tipo === 'marcador') est.mesas[i].ultimoMarcador = Date.now();
        return true;
    }
    // en una pausa (nadie ha hablado en un rato) puede salir un dato del partido presentado por el dueño de una marca patrocinadora
    // o, si ninguna de las dos selecciones tiene patrocinador, por el analista; nunca antes del minuto 8 ni dos seguidos
    function quizaDato(i) {
        if (!est || est.modo !== 'tv' || !window.Narracion.elegirDato) return false;
        const m = est.mesas[i], ahora = Date.now();
        if (m.cerrada || m.grafico || (est.ultimo && est.ultimo.minuto_actual < 8)) return false;
        if (ahora - est.ultimoDato < 70000 || ahora - m.ultimoMarcador < 25000 || Math.random() > 0.5) return false;
        const d = window.Narracion.elegirDato(est.ultimo.eventos, est.datosUsados, Math.random);
        if (!d) return false;
        d.marca = marcaDelDato(d, i);
        if (!mostrarGrafico(i, 'dato', d)) return false;
        est.ultimoDato = ahora;
        est.datosUsados.push(d.clave); if (est.datosUsados.length > 6) est.datosUsados.shift();
        return true;
    }
    // el comercial del marcador sale de vez en cuando (y en el arranque, el descanso y el final); nunca sobre una tarjeta
    function quizaMarcador(clase) {
        if (!est || est.modo !== 'tv' || !window.Narracion.tocaMarcador) return;
        const hito = clase === 'inicio' || clase === 'descanso' || clase === 'final';
        est.mesas.forEach((m, i) => {
            if (m.cerrada || m.grafico || (!hito && Date.now() - m.ultimoMarcador < 20000)) return;
            // con dos cadenas no salen a la vez: la segunda entra un momento después
            if (window.Narracion.tocaMarcador(clase, Date.now() - m.ultimoMarcador)) setTimeout(() => mostrarGrafico(i, 'marcador'), i * 1800);
        });
    }

    // ---------------------------------------------------------------- datos del momento
    function minutoTexto(data) {
        return data.finalizado ? 'FINAL' : (data.adicional_actual ? `${data.minuto_actual}+${data.adicional_actual}'` : `${data.minuto_actual}'`);
    }
    function contexto(data) {
        return { golesLocal: data.goles_local, golesVisita: data.goles_visitante, marcador: `${data.goles_local}-${data.goles_visitante}`, minuto: String(data.minuto_actual != null ? Math.floor(data.minuto_actual) : '') };
    }
    function actualizarHud(data) {
        raiz.querySelectorAll('[data-hud]').forEach(h => {
            const set = (sel, v) => { const n = h.querySelector(sel); if (n && n.textContent !== v) n.textContent = v; };
            set('[data-hud-local]', data.siglas_local || data.local);
            set('[data-hud-visita]', data.siglas_visitante || data.visitante);
            set('[data-hud-goles]', `${data.goles_local} - ${data.goles_visitante}`);
            set('[data-hud-min]', minutoTexto(data));
        });
    }

    // ---------------------------------------------------------------- cola de mensajes
    function encolar(intervenciones, llegada) {
        // la cola va en el ORDEN DE LA JUGADA (cada evento con su cadena de frases), no por hora de llegada: así el análisis de un
        // gol no queda detrás de la narración del evento siguiente
        // una jugada importante (gol, roja...) deja atrás lo menor que siga pendiente en esa mesa: su comentario sale enseguida
        const urgentes = new Set(intervenciones.filter(it => it.prio >= 3 && !it.paso).map(it => Math.min(it.mesa, est.colas.length - 1)));
        urgentes.forEach(i => { est.colas[i] = est.colas[i].filter(x => x.prio >= 3); });
        intervenciones.forEach(it => {
            const cola = est.colas[Math.min(it.mesa, est.colas.length - 1)];
            cola.push(Object.assign({}, it, { llegada, disponible: llegada + (it.paso ? 0 : (it.retraso || 0)) }));
        });
        est.colas.forEach((cola, i) => {
            while (cola.length > MAX_COLA) {   // se descartan primero los menos importantes, los más viejos
                let k = 0, peor = Infinity;
                cola.forEach((it, idx) => { if (it.prio < peor) { peor = it.prio; k = idx; } });
                if (peor >= 3) break;
                cola.splice(k, 1);
            }
            programar(i);
        });
    }

    function programar(i) {
        if (!est || !est.listo) return;
        const m = est.mesas[i];
        if (m.cerrada) return;                         // la transmisión ya terminó: solo queda el logo
        if (m.mostrando) return;                       // ya hay un mensaje en pantalla: al terminar pide el siguiente
        clearTimeout(m.timer);
        const cola = est.colas[i], ahora = Date.now();
        while (cola.length && cola[0].prio < 3 && ahora - cola[0].disponible > CADUCA_MS) cola.shift();
        // con atraso, los comentarios de seguimiento (2.º y 3.º de una cadena) de jugadas viejas ceden el paso a lo más reciente
        while (cola.length > 1 && cola[0].paso > 0 && ahora - cola[0].llegada > 9000 && cola.some(x => x.paso === 0 && x.prio >= 2 && x.evento > cola[0].evento)) cola.shift();
        if (cola.length) {
            const espera = Math.max(0, (cola[0].paso ? 350 : cola[0].disponible - ahora));
            m.timer = setTimeout(() => mostrarSiguiente(i), espera);
            return;
        }
        // sin nada pendiente: tras un silencio, charla de relleno (no cuando el partido ya terminó)
        if (est.ultimo && est.ultimo.finalizado) return;
        const hasta = m.ultimaFin + SILENCIO_MIN + Math.random() * SILENCIO_EXTRA;
        m.timer = setTimeout(() => {
            if (!est || !est.listo || m.mostrando || est.colas[i].length) return programar(i);
            if (quizaDato(i)) { m.ultimaFin = Date.now() + GRAFICO_MS.dato * 0.6; return programar(i); }   // la pausa se llena con el dato
            const c = est.narrador.charla(contexto(est.ultimo), i);
            if (c) mostrar(i, c); else programar(i);
        }, Math.max(500, hasta - ahora));
    }

    function mostrarSiguiente(i) {
        if (!est || !est.listo) return;
        const it = est.colas[i].shift();
        if (!it) return programar(i);
        mostrar(i, it);
    }

    function nombreDe(i, rol) {
        const mesa = est.mesas[i];
        if (!mesa || est.modo !== 'tv') return 'Narrador';
        const asientoEl = mesa.raiz.querySelector(`.tv-placa--${rol} b`);
        return asientoEl ? asientoEl.textContent : ROLES[rol];
    }

    function mostrar(i, it) {
        const m = est.mesas[i];
        if (!m || !m.raiz) return;
        m.mostrando = it;
        const quien = m.raiz.querySelector('.tv-set__quien'), texto = m.raiz.querySelector('.tv-set__texto');
        const caja = quien.parentElement;
        const poner = () => {
            quien.innerHTML = `<b>${e(nombreDe(i, it.rol))}</b><small>${ROLES[it.rol] || ''}</small>`;
            quien.dataset.rol = it.rol;
            texto.textContent = it.texto;
            caja.classList.remove('is-saliendo');
            caja.classList.add('is-visible');
            marcarHablante(m, it.rol, true);
            if (it.efecto) destello(m, it);
        };
        if (caja.classList.contains('is-visible') && FUNDIDO_MS) {
            caja.classList.add('is-saliendo');
            clearTimeout(m.fundido);
            m.fundido = setTimeout(poner, FUNDIDO_MS);
        } else poner();
        clearTimeout(m.timer);
        m.timer = setTimeout(() => terminar(i), (it.duracion || 3500) + FUNDIDO_MS);
    }

    function terminar(i) {
        if (!est) return;
        const m = est.mesas[i];
        const fin = m.mostrando && m.mostrando.cierre;
        marcarHablante(m, null, false);
        m.mostrando = null;
        m.ultimaFin = Date.now();
        if (fin) { mostrarCierre(i); return; }
        const cola = est.colas[i];
        // si no sigue otro mensaje en seguida, el rótulo se retira para que no quede el último congelado
        const sigue = cola.length && cola[0].disponible - Date.now() < 1500;
        if (!sigue) {
            const caja = m.raiz.querySelector('.tv-set__texto').parentElement;
            caja.classList.add('is-saliendo');
            clearTimeout(m.fundido);
            m.fundido = setTimeout(() => { if (!m.mostrando) caja.classList.remove('is-visible', 'is-saliendo'); }, FUNDIDO_MS + 20);
        }
        programar(i);
    }

    function marcarHablante(m, rol, habla) {
        m.raiz.querySelectorAll('.tv-asiento, .tv-placa, .radio-set__locutor').forEach(a => a.classList.toggle('habla', habla && a.dataset.rol === rol));
        m.raiz.classList.toggle('esta-hablando', !!habla);
    }

    // ---------------------------------------------------------------- destellos (gol, tarjetas, VAR, penal)
    const DESTELLOS = {
        gol: { titulo: '¡GOOOL!', icono: 'bi-bullseye', clase: 'gol' },
        penal: { titulo: '¡PENAL!', icono: 'bi-record-circle', clase: 'penal' },
        amarilla: { titulo: 'TARJETA AMARILLA', icono: 'bi-square-fill', clase: 'amarilla' },
        roja: { titulo: 'TARJETA ROJA', icono: 'bi-square-fill', clase: 'roja' },
        var: { titulo: 'REVISIÓN VAR', icono: 'bi-tv', clase: 'var' },
    };
    function destello(m, it) {
        if (it.efecto === 'sacude') {   // gol con tarjeta de jugador: solo se mueve la pantalla
            const pantalla = m.raiz.querySelector('.tv-set__pantalla');
            if (pantalla && !reducido) { pantalla.classList.remove('sacude'); void pantalla.offsetWidth; pantalla.classList.add('sacude'); }
            return;
        }
        const d = DESTELLOS[it.efecto];
        if (!d) return;
        const nodo = m.raiz.querySelector('.tv-set__flash');
        if (!nodo) {   // la radio no tiene pantalla: el aparato se sacude con el grito de gol
            if (it.efecto === 'gol' && !reducido) { m.raiz.classList.remove('grito'); void m.raiz.offsetWidth; m.raiz.classList.add('grito'); }
            return;
        }
        nodo.className = `tv-set__flash tv-set__flash--${d.clase}`;
        nodo.innerHTML = `<i class="bi ${d.icono}"></i><strong>${d.titulo}</strong>${it.equipoEfecto ? `<small>${e(it.equipoEfecto)}</small>` : ''}`;
        void nodo.offsetWidth;   // reinicia la animación si hay dos seguidos
        nodo.classList.add('is-activo');
        const pantalla = m.raiz.querySelector('.tv-set__pantalla');
        if (pantalla && !reducido && (it.efecto === 'gol' || it.efecto === 'roja')) {
            pantalla.classList.remove('sacude'); void pantalla.offsetWidth; pantalla.classList.add('sacude');
        }
        clearTimeout(nodo._t);
        nodo._t = setTimeout(() => nodo.classList.remove('is-activo'), 2600);
    }

    // ---------------------------------------------------------------- entrada desde live_match.js
    function actualizar(data) {
        if (!data || !data.match_id) return;
        if (!est || est.matchId !== data.match_id) { iniciar(data); return; }
        est.ultimo = data;
        if (!est.listo) return;
        actualizarHud(data);
        try { quizaPleca(); } catch (err) { console.error('Pleca:', err); }
        try { pintarGoles(data); } catch (err) { console.error('Goleadores:', err); }
        const eventos = data.eventos || [];
        if (eventos.length <= est.cursor) { if (data.finalizado && !est.despedida) despedir(data); return; }
        const llegada = Date.now(), ctx = contexto(data);
        let pitidoFinal = false;
        for (let k = est.cursor; k < eventos.length; k++) {
            // el marcador del momento del evento: si hay varios nuevos solo el último puede citar el marcador actual
            const partido = { local: data.local, visitante: data.visitante };
            const c = Object.assign(k === eventos.length - 1 ? ctx : { marcador: '', minuto: ctx.minuto }, { tanda: window.Narracion.estadoTanda(eventos, k, partido) });
            const its = est.narrador.proponer(eventos[k], k, c);
            const g = est.modo === 'tv' ? window.Narracion.grafico(eventos[k], k, eventos, partido) : null;
            if (g) {
                // la tarjeta sustituye al destello de «¡GOL!» / tarjeta (el gol conserva la sacudida de la pantalla)
                if (its.length && its[0].efecto) its[0].efecto = its[0].efecto === 'gol' ? 'sacude' : null;
                const tipoG = { penal: 'penal', cambio: 'cambio', arbitro: 'arbitro', tanda: 'tanda' }[g.accion] || 'jugador';
                // el arbitraje y la tanda se ven en todos los televisores; lo demás, en el de la cadena que narra la jugada
                const mesasG = (g.accion === 'arbitro' || g.accion === 'tanda') ? est.mesas.map((_, n) => n) : [its.length ? its[0].mesa : mesaDelEquipo(g.equipo)];
                mesasG.forEach(mesaG => setTimeout(() => { if (est && est.matchId === data.match_id) mostrarGrafico(mesaG, tipoG, g); }, Math.max(0, (k - est.cursor) * 600) + 150));
                // al arrancar y en el descanso, después del árbitro sale el comercial del marcador
                const claseG = window.Narracion.clasificar(eventos[k]);
                if (g.accion === 'arbitro' && (claseG === 'inicio' || claseG === 'descanso')) setTimeout(() => quizaMarcador(claseG), 8200);
                if (g.accion === 'arbitro' && claseG === 'inicio') est.mesas.forEach((_, n) => setTimeout(() => mostrarFormacion(n), 17500 + n * 1500));
            } else if (est.modo === 'tv') {
                const clase = window.Narracion.clasificar(eventos[k]);
                // en el pitido final no hay comercial: la despedida termina con el logo de la cadena
                if (clase !== 'final' && (k === eventos.length - 1 || clase === 'inicio' || clase === 'descanso')) setTimeout(() => quizaMarcador(clase), 1200);
            }
            if (window.Narracion.clasificar(eventos[k]) === 'final') pitidoFinal = true;
            if (its.length) encolar(its, llegada + (k - est.cursor) * 600);
        }
        est.cursor = eventos.length;
        // el pitido final (último evento) o el aviso de partido terminado: empieza la despedida
        if ((pitidoFinal || data.finalizado) && !est.despedida) despedir(data);
    }

    // ---------------------------------------------------------------- final del partido: despedida y logo de la cadena
    // Al terminar el partido los narradores comentan cómo fue, dan las gracias y se despiden; después ya no hay mesa: se queda
    // el logo de la cadena (o la radio fuera del aire) hasta que empiece otro partido o se salga de la vista.
    function despedir(data) {
        if (!est || !est.listo || est.despedida) return;
        est.despedida = true;
        const res = window.Narracion.resumen(data);
        const llegada = Date.now();
        est.mesas.forEach((m, i) => {
            const its = est.narrador.despedida(res, i);
            if (its.length) encolar(its, llegada + i * 1200);   // con dos cadenas no se despiden exactamente a la vez
            else mostrarCierre(i);
        });
    }

    function htmlCierre(i) {
        const d = est.ultimo || {}, t = est.tele[i] || {};
        return `<div class="tv-set__cierre">
            ${t.logo ? `<img class="tv-set__cierre-logo" src="${e(t.logo)}" alt="${e(t.nombre)}" onerror="this.remove()">` : `<b class="tv-set__cierre-nombre">${e(t.nombre || '')}</b>`}
            ${t.lema ? `<small class="tv-set__cierre-lema">${e(t.lema)}</small>` : ''}
            <span class="tv-set__cierre-linea"></span>
            <strong class="tv-set__cierre-fin">Fin de la transmisión</strong>
            <span class="tv-set__cierre-resultado">${e(d.local)} <i>${e(d.goles_local)} - ${e(d.goles_visitante)}</i> ${e(d.visitante)}</span>
            <small class="tv-set__cierre-gracias">Gracias por acompañarnos · ¡Hasta la próxima transmisión!</small></div>`;
    }
    function mostrarCierre(i) {
        if (!est) return;
        const m = est.mesas[i];
        if (!m || m.cerrada) return;
        m.cerrada = true;
        clearTimeout(m.timer); clearTimeout(m.fundido); clearTimeout(m.graficoTimer);
        est.colas[i].length = 0; m.mostrando = null; m.grafico = null;
        marcarHablante(m, null, false);
        if (est.modo === 'tv') {
            const pantalla = m.raiz.querySelector('.tv-set__pantalla');
            const g = m.raiz.querySelector('.tv-set__grafico'); if (g) { g.className = 'tv-set__grafico'; g.innerHTML = ''; } retirarPleca(m);
            if (pantalla && !pantalla.querySelector('.tv-set__cierre')) pantalla.insertAdjacentHTML('beforeend', htmlCierre(i));
            m.raiz.classList.remove('con-grafico'); m.raiz.classList.add('tv-set--fuera');
        } else {
            const caja = m.raiz.querySelector('.tv-set__texto');
            const quien = m.raiz.querySelector('.tv-set__quien');
            if (quien) quien.innerHTML = '<b>Radio</b><small>Fuera del aire</small>';
            if (caja) caja.textContent = 'Fin de la transmisión. Gracias por sintonizarnos: ¡hasta la próxima!';
            const globo = m.raiz.querySelector('.radio-set__globo'); if (globo) { globo.classList.remove('is-saliendo'); globo.classList.add('is-visible'); }
            m.raiz.classList.add('radio-set--fuera');
        }
    }

    // al volver a la pestaña se descarta lo acumulado: el partido siguió y los comentarios viejos no tienen sentido
    document.addEventListener('visibilitychange', () => {
        if (document.hidden || !est || !est.listo) return;
        if (est.despedida) { est.mesas.forEach((_, i) => mostrarCierre(i)); return; }   // el partido terminó mientras no mirabas
        est.colas.forEach(c => { c.length = 0; });
        est.cursor = (est.ultimo && est.ultimo.eventos ? est.ultimo.eventos.length : est.cursor);
        est.mesas.forEach((m, i) => { if (!m.mostrando) programar(i); });
    });

    function ponerPlantillas(p) { plantillas = { ids: p.ids || {}, dorsales: p.dorsales || {}, posiciones: p.posiciones || {}, paises: p.paises || {}, arbitros: p.arbitros || {}, planteamiento: p.planteamiento || {} }; }
    window.TransmisionVivo = { actualizar, plantillas: ponerPlantillas, grafico: mostrarGrafico };
})();
