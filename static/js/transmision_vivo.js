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
        est = { matchId, listo: false, cursor: null, mesas: [], colas: [], ultimo: data, narrador: null };
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
        est.mesas = mesas.map((_, i) => ({
            raiz: raiz.querySelector(`[data-mesa="${i}"]`), mostrando: null, timer: null, ultimaFin: Date.now(), fundido: null,
        }));
        est.colas = mesas.map(() => []);
        est.cursor = (data.eventos || []).length;   // no se cuenta la historia: se narra desde aquí
        est.listo = true;
        actualizarHud(data);
        est.mesas.forEach((_, i) => programar(i));
        // saludo al entrar (si no hay nada más que decir)
        const saludo = est.narrador.charla(contexto(data), 0);
        if (saludo) encolar([Object.assign(saludo, { prio: 1 })], Date.now() + 400);
    }

    function detener() {
        if (!est) return;
        (est.mesas || []).forEach(m => { clearTimeout(m.timer); clearTimeout(m.fundido); });
        est = null;
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
        marcarHablante(m, null, false);
        m.mostrando = null;
        m.ultimaFin = Date.now();
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
        if (eventos.length <= est.cursor) return;
        const llegada = Date.now(), ctx = contexto(data);
        for (let k = est.cursor; k < eventos.length; k++) {
            // el marcador del momento del evento: si hay varios nuevos solo el último puede citar el marcador actual
            const c = k === eventos.length - 1 ? ctx : { marcador: '', minuto: ctx.minuto };
            const its = est.narrador.proponer(eventos[k], k, c);
            if (its.length) encolar(its, llegada + (k - est.cursor) * 600);
        }
        est.cursor = eventos.length;
    }

    // al volver a la pestaña se descarta lo acumulado: el partido siguió y los comentarios viejos no tienen sentido
    document.addEventListener('visibilitychange', () => {
        if (document.hidden || !est || !est.listo) return;
        est.colas.forEach(c => { c.length = 0; });
        est.cursor = (est.ultimo && est.ultimo.eventos ? est.ultimo.eventos.length : est.cursor);
        est.mesas.forEach((m, i) => { if (!m.mostrando) programar(i); });
    });

    window.TransmisionVivo = { actualizar };
})();
