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
    function rostroComentarista(c, rol) {
        const img = c && c.avatar_url ? `<img src="${e(c.avatar_url)}" alt="" loading="lazy" decoding="async" onerror="this.remove()">` : '<i class="bi bi-person-fill"></i>';
        return `<span class="tv-asiento__rostro">${img}</span>`;
    }
    function asiento(rol, nombre, rostro) {
        return `<div class="tv-asiento tv-asiento--${rol}" data-rol="${rol}"><span class="tv-asiento__cuerpo"></span>${rostro}</div>`;
    }
    // las placas con los nombres van aparte de los asientos (el escritorio tapa a los asientos y las placas deben verse encima)
    function placa(rol, nombre) {
        return `<span class="tv-placa tv-placa--${rol}" data-rol="${rol}"><b>${e(nombre || ROLES[rol])}</b><small>${ROLES[rol]}</small></span>`;
    }
    function dibujarTV(mesa, i) {
        const t = mesa.tele, com = mesa.comentaristas || [];
        const narr = com.find(c => c.rol === 'narrador') || com[0], anal = com.find(c => c.rol === 'analista') || com[1];
        const inv = mesa.invitado;
        const rostroInv = inv ? `<span class="tv-asiento__rostro">${window.UI ? UI.avatar(inv.jugador_id, inv.pais_id, '') : ''}</span>` : '';
        return `<div class="tv-set" data-mesa="${i}" style="--tv:${e(t.color)};--tv2:${e(t.color2)};">
            <div class="tv-set__marco">
                <div class="tv-set__pantalla">
                    <div class="tv-set__estudio"><span class="tv-set__panel tv-set__panel--a"></span><span class="tv-set__panel tv-set__panel--b"></span>
                        ${t.logo ? `<img class="tv-set__marca" src="${e(t.logo)}" alt="" loading="lazy" decoding="async" onerror="this.remove()">` : ''}</div>
                    <div class="tv-set__hud">
                        <span class="tv-set__marcador" data-hud><b data-hud-local></b><i data-hud-goles>0 - 0</i><b data-hud-visita></b><em data-hud-min></em></span>
                        <span class="tv-set__envivo"><i></i>EN VIVO</span>
                    </div>
                    <div class="tv-set__mosca">${t.logo ? `<img src="${e(t.logo)}" alt="${e(t.nombre)}" onerror="this.remove()">` : e(t.nombre)}</div>
                    <div class="tv-set__mesa">
                        ${asiento('analista', anal && anal.nombre, rostroComentarista(anal))}
                        ${asiento('narrador', narr && narr.nombre, rostroComentarista(narr))}
                        ${inv ? asiento('invitado', inv.nombre, rostroInv) : ''}
                    </div>
                    <span class="tv-set__escritorio"></span>
                    <div class="tv-set__placas">${placa('analista', anal && anal.nombre)}${placa('narrador', narr && narr.nombre)}${inv ? placa('invitado', inv.nombre) : ''}</div>
                    <div class="tv-set__rotulo" aria-live="polite"><span class="tv-set__quien"></span><p class="tv-set__texto"></p></div>
                    <div class="tv-set__flash" aria-hidden="true"></div>
                    <div class="tv-set__grafico" aria-hidden="true"></div>
                </div>
                <div class="tv-set__bisel"><span class="tv-set__led"></span><small>${e(t.nombre)}${t.lema ? ' · ' + e(t.lema) : ''}</small></div>
            </div><div class="tv-set__pie"></div></div>`;
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
        est = { matchId, listo: false, cursor: null, mesas: [], colas: [], ultimo: data, narrador: null, tele: [], ultimoMarcador: Date.now() };
        const info = await cargarMesa();
        if (!est || est.matchId !== matchId) return;   // cambió el partido mientras cargaba
        const modo = info.modo === 'tv' && (info.mesas || []).length ? 'tv' : 'radio';
        const mesas = modo === 'tv' ? info.mesas.slice(0, 2) : [{}];
        raiz.innerHTML = modo === 'tv' ? `<div class="tv-vivo__mesas tv-vivo__mesas--${mesas.length}">${mesas.map(dibujarTV).join('')}</div>` : dibujarRadio();
        raiz.dataset.modo = modo;
        est.modo = modo;
        est.narrador = window.Narracion.crear({
            matchId, local: data.local, visitante: data.visitante, idLocal: data.id_local, idVisita: data.id_visita,
            estadio: data.estadio, modo, mesas: modo === 'tv' ? mesas : [],
        });
        est.tele = modo === 'tv' ? mesas.map(m => m.tele || {}) : [];
        est.mesas = mesas.map((_, i) => ({
            raiz: raiz.querySelector(`[data-mesa="${i}"]`), mostrando: null, timer: null, ultimaFin: Date.now(), fundido: null,
            grafico: null, graficoTimer: null, ultimoMarcador: Date.now() + i * 40000,
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
    let plantillas = { ids: {}, dorsales: {}, posiciones: {} };   // las completa live_match.js (GET /matches/live/plantillas)
    const GRAFICO_MS = { jugador: 4800, marcador: 6200 };
    const ACCION_TXT = { gol: 'GOL', amarilla: 'TARJETA AMARILLA', roja: 'TARJETA ROJA', atajo: 'PENAL ATAJADO' };

    function equipoId(nombre) {
        const d = est && est.ultimo;
        if (!d || !nombre) return null;
        return nombre === d.local ? d.id_local : (nombre === d.visitante ? d.id_visita : null);
    }
    function ordinal(n) { return `${n}.º`; }
    function imagenPais(id, tipo) { return window.UI && UI.urlImagenPais ? UI.urlImagenPais(id, tipo) : null; }

    function htmlJugador(g) {
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
            </div></div>`;
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

    // tipo: 'jugador' (datos del gráfico de Narracion.grafico) o 'marcador'. Una pieza a la vez por televisor; la tarjeta de
    // un gol o una roja pasa por encima de un comercial que esté saliendo.
    function mostrarGrafico(i, tipo, datos) {
        if (!est || !est.listo || est.modo !== 'tv') return;
        const m = est.mesas[i];
        const cont = m && m.raiz.querySelector('.tv-set__grafico');
        if (!cont || m.cerrada) return;
        if (m.grafico && !(tipo === 'jugador' && m.grafico === 'marcador') && !(datos && datos.prio >= 3 && m.grafico === 'jugador')) return;
        clearTimeout(m.graficoTimer);
        m.grafico = tipo;
        cont.innerHTML = tipo === 'jugador' ? htmlJugador(datos) : htmlMarcador(i);
        cont.className = `tv-set__grafico tv-set__grafico--${tipo} is-activo`;
        m.raiz.classList.add('con-grafico');
        const dur = (reducido ? 0.6 : 1) * GRAFICO_MS[tipo];
        m.graficoTimer = setTimeout(() => {
            cont.classList.add('is-saliendo');
            m.graficoTimer = setTimeout(() => {
                cont.className = 'tv-set__grafico'; cont.innerHTML = ''; m.grafico = null; m.raiz.classList.remove('con-grafico');
            }, reducido ? 0 : 450);
        }, dur);
        if (tipo === 'marcador') est.mesas[i].ultimoMarcador = Date.now();
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
        return { marcador: `${data.goles_local}-${data.goles_visitante}`, minuto: String(data.minuto_actual != null ? Math.floor(data.minuto_actual) : '') };
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
        const eventos = data.eventos || [];
        if (eventos.length <= est.cursor) { if (data.finalizado && !est.despedida) despedir(data); return; }
        const llegada = Date.now(), ctx = contexto(data);
        let pitidoFinal = false;
        for (let k = est.cursor; k < eventos.length; k++) {
            // el marcador del momento del evento: si hay varios nuevos solo el último puede citar el marcador actual
            const c = k === eventos.length - 1 ? ctx : { marcador: '', minuto: ctx.minuto };
            const its = est.narrador.proponer(eventos[k], k, c);
            const g = est.modo === 'tv' ? window.Narracion.grafico(eventos[k], k, eventos) : null;
            if (g && its.length) {
                // la tarjeta sustituye al destello de «¡GOL!» / tarjeta (el gol conserva la sacudida de la pantalla)
                if (its[0].efecto) its[0].efecto = its[0].efecto === 'gol' ? 'sacude' : null;
                setTimeout(() => { if (est && est.matchId === data.match_id) mostrarGrafico(its[0].mesa, 'jugador', g); }, Math.max(0, (k - est.cursor) * 600) + 150);
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
            const g = m.raiz.querySelector('.tv-set__grafico'); if (g) { g.className = 'tv-set__grafico'; g.innerHTML = ''; }
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

    function ponerPlantillas(p) { plantillas = { ids: p.ids || {}, dorsales: p.dorsales || {}, posiciones: p.posiciones || {} }; }
    window.TransmisionVivo = { actualizar, plantillas: ponerPlantillas, grafico: mostrarGrafico };
})();
