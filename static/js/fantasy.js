/*
 * Once Ideal (/once-ideal/): equipos por formación, buscador, Ojeador y ficha del jugador.
 * Los datos llegan en <script id="datosFantasy"> (routes/fantasy_route.py). Las reglas se validan otra vez en el
 * servidor (services/fantasy_service.py): aquí solo se adelantan los avisos.
 */
document.addEventListener('DOMContentLoaded', function () {
    const C = JSON.parse(document.getElementById('datosFantasy').textContent);
    const E = UI.escapar;
    const LINEAS = ['DELANTERO', 'MEDIO', 'DEFENSA', 'PORTERO'];   // de arriba hacia abajo en la cancha
    const NOMBRE_LINEA = { PORTERO: 'Portero', DEFENSA: 'Defensas', MEDIO: 'Medios', DELANTERO: 'Delanteros' };
    const NOMBRE_LINEA_UNO = { PORTERO: 'portero', DEFENSA: 'defensa', MEDIO: 'medio', DELANTERO: 'delantero' };
    const INSIGNIA_LEYENDA = '<span class="insignia-leyenda insignia-leyenda--compacta" title="Leyenda: parte del once histórico de su selección"><i class="bi bi-award-fill"></i></span>';
    const formaciones = Object.fromEntries(C.formaciones.map(f => [f.esquema, f]));
    const lineaDe = j => C.lineaDePosicion[String(j.posicion_id)] || 'MEDIO';
    const $ = id => document.getElementById(id);
    const alerta = (msg, tipo) => UI.mostrarAlertaEn($('alertaFantasy'), msg, tipo);

    // --- Estado de cada equipo -------------------------------------------------------------------------------------
    const equipos = {};
    for (let n = 1; n <= C.abiertas; n++) {
        const e = C.escuadras.find(x => x.escuadra === n);
        equipos[n] = {
            existe: !!e, formacion: e ? e.formacion : null, jugadores: e ? e.jugadores.slice() : [],
            original: e ? e.lineup.slice() : [], cambiosGratis: e ? e.cambios_gratis_disponibles : 0,
            puntos: e ? e.total_points_fase : 0, ganado: e ? e.monto_ganado : 0,
        };
    }
    // Un equipo nuevo arranca con la primera formación que no use otro
    for (let n = 1; n <= C.abiertas; n++) {
        if (!equipos[n].formacion) equipos[n].formacion = C.formaciones.map(f => f.esquema).find(f => !usadaPorOtro(f, n)) || '4-3-3';
    }
    let activa = 1;
    let vistaDesbloqueo = false;
    const niveles = {};          // {jugador_id: {codigo, etiqueta, ...}}
    let ultimosResultados = [];

    function usadaPorOtro(formacion, n) {
        return Object.entries(equipos).some(([k, e]) => Number(k) !== n && e.formacion === formacion && (e.existe || e.jugadores.length));
    }
    function equipoDe(jugadorId) {
        const k = Object.keys(equipos).find(k => equipos[k].jugadores.some(j => j.id === jugadorId));
        return k ? Number(k) : null;
    }
    const eq = () => equipos[activa];
    const cupos = () => formaciones[eq().formacion].cupos;

    // --- Pestañas --------------------------------------------------------------------------------------------------
    function renderPestanas() {
        let html = '';
        for (let n = 1; n <= C.maximo; n++) {
            if (n <= C.abiertas) {
                const e = equipos[n];
                html += `<button type="button" role="tab" class="once-tab ${!vistaDesbloqueo && n === activa ? 'is-activa' : ''}" data-equipo="${n}" aria-selected="${!vistaDesbloqueo && n === activa}">
                    <strong>Equipo ${n}</strong><small>${E(e.formacion)} · ${e.jugadores.length}/11${e.ganado ? ` · <b>+${e.ganado}</b>` : ''}</small></button>`;
            } else if (C.desbloqueo && n === C.desbloqueo.escuadra) {
                html += `<button type="button" role="tab" class="once-tab once-tab--bloqueada ${vistaDesbloqueo ? 'is-activa' : ''}" data-desbloqueo="1" aria-selected="${vistaDesbloqueo}">
                    <strong><i class="bi bi-lock-fill"></i> Equipo ${n}</strong><small>${C.desbloqueo.listo ? 'Listo para abrir' : `${C.desbloqueo.jornadas_cumplidas}/${C.desbloqueo.jornadas_requeridas} jornadas`}</small></button>`;
            } else {
                html += `<span class="once-tab once-tab--futura"><strong><i class="bi bi-lock"></i> Equipo ${n}</strong><small>Más adelante</small></span>`;
            }
        }
        $('pestanasEquipos').innerHTML = html;
        $('pestanasEquipos').querySelectorAll('[data-equipo]').forEach(b => b.addEventListener('click', () => {
            activa = Number(b.dataset.equipo); vistaDesbloqueo = false; renderTodo(); ejecutarBusqueda();
        }));
        $('pestanasEquipos').querySelectorAll('[data-desbloqueo]').forEach(b => b.addEventListener('click', () => {
            vistaDesbloqueo = true; renderTodo();
        }));
    }

    function renderDesbloqueo() {
        const d = C.desbloqueo;
        const tarjeta = $('tarjetaDesbloqueo');
        $('tarjetaEquipo').classList.toggle('d-none', vistaDesbloqueo);
        tarjeta.classList.toggle('d-none', !vistaDesbloqueo || !d);
        if (!vistaDesbloqueo || !d) return;
        const pct = Math.round(d.jornadas_cumplidas * 100 / d.jornadas_requeridas);
        tarjeta.innerHTML = `<div class="card-body p-3 p-md-4 text-center">
            <div class="once-desbloqueo__icono"><i class="bi bi-${d.listo ? 'unlock-fill' : 'lock-fill'}"></i></div>
            <h2 class="h4 fw-bold text-white">Equipo ${d.escuadra}</h2>
            <p class="text-muted small mb-3">Un equipo más con otra formación y otros 11 jugadores que también te pagan en cada partido.
                Un equipo armado deja unos ${d.pago_jornada} de saldo por jornada: el desbloqueo se recupera en unas ${d.recupera_jornadas} jornadas.</p>
            <div class="once-desbloqueo__req">
                <div><span>Costo</span><strong class="text-warning">${d.costo.toLocaleString('es-MX')}</strong></div>
                <div><span>Jornadas con tu equipo ${d.escuadra - 1}</span><strong>${d.jornadas_cumplidas}/${d.jornadas_requeridas}</strong>
                    <div class="once-jornada__barra"><i style="width:${pct}%"></i></div></div>
            </div>
            ${d.motivo ? `<p class="small text-info mt-3 mb-2"><i class="bi bi-info-circle me-1"></i>${E(d.motivo)}</p>` : ''}
            <button type="button" id="btnDesbloquear" class="btn btn-warning fw-bold rounded-pill px-4 mt-2" ${d.listo ? '' : 'disabled'}>
                <i class="bi bi-unlock-fill me-1"></i>Desbloquear por ${d.costo.toLocaleString('es-MX')}</button>
        </div>`;
        const btn = $('btnDesbloquear');
        if (btn) btn.addEventListener('click', desbloquear);
    }

    async function desbloquear() {
        const d = C.desbloqueo;
        if (!await UI.confirmar({ titulo: `Desbloquear el equipo ${d.escuadra}`, mensaje: `Se cobran ${d.costo.toLocaleString('es-MX')} de tu saldo. El espacio queda tuyo también en los próximos Mundiales.`, textoConfirmar: 'Desbloquear' })) return;
        try {
            const r = await fetch(C.urls.desbloquear, { method: 'POST' });
            const datos = await r.json();
            if (!r.ok) throw new Error(datos.detail || 'No se pudo desbloquear');
            UI.refrescarSaldo();
            UI.toast && UI.toast(`¡Equipo ${datos.escuadra} desbloqueado!`);
            setTimeout(() => window.location.reload(), 700);
        } catch (err) { alerta(err.message, 'danger'); }
    }

    // --- Formación y cancha ----------------------------------------------------------------------------------------
    function renderFormacion() {
        const sel = $('selectFormacion');
        sel.innerHTML = C.formaciones.map(f => {
            const usada = usadaPorOtro(f.esquema, activa);
            return `<option value="${E(f.esquema)}" ${usada ? 'disabled' : ''} ${f.esquema === eq().formacion ? 'selected' : ''}>${E(f.esquema)} · ${E(f.etiqueta)}${usada ? ' (en otro equipo)' : ''}</option>`;
        }).join('');
        const f = formaciones[eq().formacion];
        const c = f.cupos;
        $('infoFormacion').innerHTML = `<span class="once-postura once-postura--${f.postura > 0.2 ? 'ofe' : f.postura < -0.2 ? 'def' : 'neu'}">${E(f.etiqueta)}</span>
            <span>${c.DEFENSA} DEF · ${c.MEDIO} MED · ${c.DELANTERO} DEL</span>
            <span class="text-muted">${f.postura > 0.2 ? 'Los goles y asistencias pagan más' : f.postura < -0.2 ? 'La valla invicta paga más' : 'Paga parejo'}</span>`;
        $('tituloEquipo').textContent = `Equipo ${activa}`;
        const e = eq();
        $('kpisEquipo').innerHTML = e.existe ? `<span><i class="bi bi-cash-coin text-warning"></i> Te ha pagado <b>${e.ganado.toLocaleString('es-MX')}</b></span>
            <span><i class="bi bi-star-fill text-success"></i> <b>${e.puntos.toLocaleString('es-MX')}</b> pts fantasy</span>
            <span><i class="bi bi-arrow-repeat text-info"></i> <b>${e.cambiosGratis}</b> cambios gratis</span>`
            : '<span class="text-info"><i class="bi bi-stars"></i> Equipo nuevo: armarlo la primera vez es gratis</span>';
    }

    function claseNivel(id) {
        const n = niveles[id];
        return n && n.codigo ? `once-ficha__estado--${n.codigo}` : '';
    }
    function tituloNivel(id) {
        const n = niveles[id];
        return n && n.codigo ? `Forma: ${n.etiqueta}` : '';
    }

    function renderCancha() {
        const c = cupos();
        for (const linea of LINEAS) {
            const jug = eq().jugadores.filter(j => lineaDe(j) === linea);
            let html = `<div class="once-linea__titulo">${NOMBRE_LINEA[linea]} <span>${jug.length}/${c[linea]}</span></div><div class="once-linea__fichas">`;
            jug.forEach(j => {
                html += `<div class="once-ficha ${j.eliminado ? 'once-ficha--eliminada' : ''}">
                    ${j.eliminado ? `<span class="once-ficha__eliminado"><i class="bi bi-person-x-fill"></i> ${E(j.motivo_eliminado || 'Eliminado')}</span>` : ''}
                    ${!j.eliminado && j.lesion ? `<span class="once-ficha__eliminado once-ficha__lesion" title="${E(`${j.lesion.nombre}: no juega ni cobra hasta cumplir ${j.lesion.restantes} partido(s) de baja`)}">🚑 Baja · ${E(j.lesion.restantes)}</span>` : ''}
                    <button type="button" class="once-ficha__foto once-ficha__abrir" data-ficha="${j.id}" title="Ver la ficha de ${E(j.nombre)}" aria-label="Ver la ficha de ${E(j.nombre)}">
                        ${UI.avatar(j.id, j.pais_id)}<span class="avatar-dorsal">${E(j.numero ?? '')}</span>
                        <span class="once-ficha__estado ${claseNivel(j.id)}" title="${E(tituloNivel(j.id))}"></span></button>
                    <button type="button" class="once-ficha__quitar" data-quitar="${j.id}" aria-label="Quitar a ${E(j.nombre)}" title="Quitar"><i class="bi bi-x"></i></button>
                    <span class="once-ficha__nombre">${j.leyenda ? INSIGNIA_LEYENDA + ' ' : ''}${E(j.nombre)}</span>
                    <span class="once-ficha__meta">${j.eliminado ? '<b class="text-danger">cambio gratis</b>' : `${E(j.posicion_siglas)} · ${E(j.overall)}${niveles[j.id] && niveles[j.id].codigo ? ` · <b>${E(niveles[j.id].etiqueta)}</b>` : ''}`}</span>
                </div>`;
            });
            for (let i = jug.length; i < c[linea]; i++) {
                html += `<button type="button" class="once-ficha once-ficha--vacia" data-linea="${linea}" title="Buscar ${NOMBRE_LINEA_UNO[linea]}">
                    <span class="once-ficha__hueco"><i class="bi bi-plus-lg"></i></span>
                    <span class="once-ficha__nombre">${NOMBRE_LINEA_UNO[linea]}</span></button>`;
            }
            html += '</div>';
            $(`bloque${linea.charAt(0)}${linea.slice(1).toLowerCase()}`).innerHTML = html;
        }
        document.querySelectorAll('.once-cancha [data-linea]').forEach(b => b.addEventListener('click', () => {
            $('filtroPosicion').value = 'L:' + b.dataset.linea;
            ejecutarBusqueda();
            if (window.innerWidth < 992) $('resultadosBusqueda').scrollIntoView({ behavior: 'smooth', block: 'start' });
        }));
        document.querySelectorAll('.once-cancha [data-quitar]').forEach(b => b.addEventListener('click', () => {
            eq().jugadores = eq().jugadores.filter(j => j.id !== Number(b.dataset.quitar));
            renderTodo();
        }));
        const total = eq().jugadores.length;
        $('contadorJugadores').textContent = total;
        $('btnGuardarAlineacion').disabled = total !== 11;
    }

    function renderTodo() {
        renderPestanas();
        renderDesbloqueo();
        if (!vistaDesbloqueo) { renderFormacion(); renderCancha(); }
        renderizarResultados(ultimosResultados);
    }

    $('selectFormacion').addEventListener('change', async function () {
        const nueva = this.value, c = formaciones[nueva].cupos;
        const sobran = LINEAS.flatMap(l => eq().jugadores.filter(j => lineaDe(j) === l).slice(c[l]));
        if (sobran.length && !await UI.confirmar({ titulo: `Cambiar a ${nueva}`, textoConfirmar: 'Cambiar',
                mensaje: `En el ${nueva} no caben: ${sobran.map(j => j.nombre).join(', ')}. Salen del equipo y puedes poner a otros.` })) {
            this.value = eq().formacion; return;
        }
        eq().formacion = nueva;
        eq().jugadores = eq().jugadores.filter(j => !sobran.includes(j));
        renderTodo();
    });

    // --- Agregar jugadores -----------------------------------------------------------------------------------------
    function motivoNoAgregar(j) {
        const otro = equipoDe(j.id);
        if (otro === activa) return 'Ya está en este equipo';
        if (otro) return `Ya está en tu equipo ${otro}`;
        if (j.eliminado && !eq().original.includes(j.id)) return `${j.pais_nombre} ${j.motivo_eliminado === 'No participa' ? 'no juega el Mundial' : 'quedó eliminada'}`;
        return null;
    }

    function agregarJugador(j) {
        if (vistaDesbloqueo) { alerta('Elige uno de tus equipos para agregar jugadores.', 'warning'); return false; }
        const motivo = motivoNoAgregar(j);
        if (motivo) { alerta(`${j.nombre}: ${motivo.toLowerCase()}.`, 'warning'); return false; }
        const linea = lineaDe(j), c = cupos();
        if (eq().jugadores.filter(x => lineaDe(x) === linea).length >= c[linea]) {
            alerta(`El ${eq().formacion} lleva ${c[linea]} ${NOMBRE_LINEA[linea].toLowerCase()} y ya están todos: quita a uno o cambia de formación.`, 'warning');
            return false;
        }
        if (j.leyenda && eq().jugadores.some(x => x.leyenda)) { alerta(`Solo puedes tener ${C.reglas.maxLeyendas} leyenda por equipo.`, 'warning'); return false; }
        if (eq().jugadores.filter(x => x.pais_id === j.pais_id).length >= C.reglas.maxPorPais) {
            alerta(`Ya tienes ${C.reglas.maxPorPais} jugadores de ${j.pais_nombre} en este equipo.`, 'warning'); return false;
        }
        eq().jugadores.push(j);
        $('alertaFantasy').classList.add('d-none');
        renderTodo();
        cargarNiveles([j.id]);
        return true;
    }

    // --- Buscador --------------------------------------------------------------------------------------------------
    let numeroBusqueda = 0, temporizador = null;
    function renderizarResultados(jugadores) {
        ultimosResultados = jugadores;
        const lineaLlena = j => eq() && eq().jugadores.filter(x => lineaDe(x) === lineaDe(j)).length >= cupos()[lineaDe(j)];
        const orden = j => (motivoNoAgregar(j) ? 2 : 0) + (lineaLlena(j) ? 1 : 0);
        const lista = jugadores.slice().sort((a, b) => orden(a) - orden(b));
        $('resultadosBusqueda').innerHTML = lista.map(j => {
            const motivo = motivoNoAgregar(j);
            const n = niveles[j.id];
            return `<div class="once-resultado ${motivo ? 'once-resultado--eliminado' : lineaLlena(j) ? 'once-resultado--cubierta' : ''}">
                <button type="button" class="once-resultado__foto" data-ficha="${j.id}" aria-label="Ver la ficha de ${E(j.nombre)}">${UI.avatar(j.id, j.pais_id, 'sm')}<span class="avatar-dorsal">${E(j.numero ?? '')}</span></button>
                <span class="once-resultado__info">
                    <strong>${E(j.nombre)} ${j.leyenda ? INSIGNIA_LEYENDA : ''}</strong>
                    <small>${UI.bandera('', { id: j.pais_id })} ${E(j.pais_nombre)} · ${E(j.posicion_siglas)}${n && n.codigo ? ` · <span class="nivel-forma nivel-forma--${n.codigo}">${E(n.etiqueta)}</span>` : ''}</small>
                </span>
                ${motivo ? `<span class="once-resultado__aviso once-resultado__aviso--fuera">${E(motivo)}</span>` : (lineaLlena(j) ? '<span class="once-resultado__aviso">Línea llena</span>' : '')}
                <span class="once-resultado__ovr">${E(j.overall)}</span>
                <button type="button" class="once-resultado__mas" data-agregar="${j.id}" ${motivo ? 'disabled' : ''} aria-label="Agregar a ${E(j.nombre)}"><i class="bi bi-plus-circle-fill"></i></button>
            </div>`;
        }).join('') || '<div class="text-muted small p-2">Sin resultados.</div>';
        $('resultadosBusqueda').querySelectorAll('[data-agregar]').forEach(b => b.addEventListener('click', () =>
            agregarJugador(lista.find(j => j.id === Number(b.dataset.agregar)))));
    }

    function ejecutarBusqueda() {
        const params = new URLSearchParams({ q: $('buscarJugador').value.trim() });
        const pais = $('filtroPais').value, pos = $('filtroPosicion').value;
        if (pais) params.set('pais_id', pais);
        if (pos.startsWith('L:')) params.set('linea', pos.slice(2)); else if (pos) params.set('posicion_id', pos);
        $('resultadosBusqueda').innerHTML = '<div class="text-center text-muted py-3"><span class="spinner-border spinner-border-sm me-2"></span>Buscando jugadores…</div>';
        const consulta = ++numeroBusqueda;
        fetch(`${C.urls.buscar}?${params}`)
            .then(r => { if (!r.ok) throw new Error(); return r.json(); })
            .then(datos => { if (consulta !== numeroBusqueda) return; renderizarResultados(datos); cargarNiveles(datos.map(j => j.id)); })
            .catch(() => { if (consulta === numeroBusqueda) $('resultadosBusqueda').innerHTML = '<div class="text-danger small py-3 text-center"><i class="bi bi-exclamation-triangle me-1"></i>No se pudo buscar. Intenta de nuevo.</div>'; });
    }
    $('buscarJugador').addEventListener('input', () => { clearTimeout(temporizador); temporizador = setTimeout(ejecutarBusqueda, 300); });
    $('filtroPais').addEventListener('change', ejecutarBusqueda);
    $('filtroPosicion').addEventListener('change', ejecutarBusqueda);

    // --- Niveles de forma (se calculan en el servidor sin bloquear: si todavía no están, se reintenta) ---------------
    let reintentos = 0;
    function cargarNiveles(ids) {
        const faltan = [...new Set(ids)].filter(id => !(id in niveles));
        if (!faltan.length) return;
        fetch(`${C.urls.niveles}?ids=${faltan.slice(0, 60).join(',')}`)
            .then(r => r.ok ? r.json() : null)
            .then(d => {
                if (!d) return;
                if (d.calculando && reintentos++ < 6) { setTimeout(() => cargarNiveles(faltan), 3000); return; }
                Object.entries(d.niveles).forEach(([k, v]) => { niveles[Number(k)] = v; });
                if (!vistaDesbloqueo) renderCancha();
                renderizarResultados(ultimosResultados);
            }).catch(() => {});
    }

    // --- Guardar ---------------------------------------------------------------------------------------------------
    $('btnGuardarAlineacion').addEventListener('click', async function () {
        const e = eq();
        const lineup = e.jugadores.map(j => j.id);
        if (e.existe) {
            // Mismo desglose que services/fantasy_service.calcular_cambios
            const salientes = e.original.filter(id => !lineup.includes(id));
            const gratisEliminados = salientes.filter(id => (C.escuadras.find(x => x.escuadra === activa).jugadores.find(j => j.id === id) || {}).eliminado).length;
            const normales = salientes.length - gratisEliminados;
            const usados = Math.min(normales, e.cambiosGratis);
            const extra = normales - usados;
            if (salientes.length) {
                const partes = [];
                if (gratisEliminados) partes.push(`${gratisEliminados} reemplazo(s) de eliminados (gratis)`);
                if (usados) partes.push(`${usados} con cambios gratis (te quedan ${e.cambiosGratis - usados})`);
                if (extra) partes.push(`${extra} extra = ${extra * C.reglas.costoExtra} de saldo`);
                if (!await UI.confirmar({ titulo: extra ? 'Guardar con cambios extra' : 'Guardar cambios', mensaje: `Cambias ${salientes.length} jugador(es): ${partes.join(' + ')}.`,
                        textoConfirmar: extra ? `Guardar y pagar ${extra * C.reglas.costoExtra}` : 'Guardar', peligro: !!extra })) return;
            }
        }
        const btn = this;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
        try {
            const r = await fetch(C.urls.guardar, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lineup, formacion: e.formacion, escuadra: activa }) });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'No se pudo guardar el equipo.');
            const c = d.cambios || {};
            alerta(c.costo ? `¡Equipo guardado! Se cobraron ${c.costo} por ${c.extra} cambio(s) extra.` : '¡Equipo guardado!', 'success');
            UI.refrescarSaldo();
            setTimeout(() => window.location.reload(), 900);
        } catch (err) {
            alerta(err.message, 'danger');
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-check2-circle me-1"></i>Guardar equipo';
        }
    });

    // --- Ojeador ---------------------------------------------------------------------------------------------------
    let nivelOjeador = C.ojeador[0].codigo;
    function renderNivelesOjeador() {
        $('ojeadorNiveles').innerHTML = C.ojeador.map(n => `<button type="button" role="radio" aria-checked="${n.codigo === nivelOjeador}"
            class="ojeador-nivel ${n.codigo === nivelOjeador ? 'is-activo' : ''}" data-nivel="${n.codigo}" title="${E(n.texto)}">
            <strong>${E(n.nombre)}</strong><small>${n.precio}</small></button>`).join('');
        $('ojeadorNiveles').querySelectorAll('[data-nivel]').forEach(b => b.addEventListener('click', () => { nivelOjeador = b.dataset.nivel; renderNivelesOjeador(); }));
    }
    renderNivelesOjeador();

    $('btnOjeador').addEventListener('click', async function () {
        if (vistaDesbloqueo) { alerta('Elige uno de tus equipos para pedir sugerencias.', 'warning'); return; }
        const n = C.ojeador.find(x => x.codigo === nivelOjeador);
        const pos = $('ojeadorPosicion');
        if (!await UI.confirmar({ titulo: `Ojeador ${n.nombre}`, textoConfirmar: `Pedir (${n.precio})`,
                mensaje: `${n.texto}. Posición: ${pos.options[pos.selectedIndex].text}, para tu equipo ${activa}. Cuesta ${n.precio} de saldo; si no encuentra a nadie no se cobra, y volver a verla es gratis hasta el próximo partido.` })) return;
        const caja = $('ojeadorResultados');
        caja.innerHTML = '<div class="text-center text-muted py-3"><span class="spinner-border spinner-border-sm me-2"></span>El ojeador revisa los partidos…</div>';
        try {
            const r = await fetch(C.urls.ojeador, { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ posicion_id: Number(pos.value), nivel: nivelOjeador, escuadra: activa }) });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'No se pudo consultar al Ojeador');
            if (d.cobrado) UI.refrescarSaldo();
            renderOjeador(d);
        } catch (err) { caja.innerHTML = `<div class="text-danger small py-2"><i class="bi bi-exclamation-triangle me-1"></i>${E(err.message)}</div>`; }
    });

    function renderOjeador(d) {
        const caja = $('ojeadorResultados');
        if (!d.sugerencias.length) {
            caja.innerHTML = '<div class="text-muted small py-2">No encontró jugadores de ese nivel que te sirvan ahora (no se cobró). Prueba otro nivel u otra posición.</div>';
            return;
        }
        d.sugerencias.forEach(s => { niveles[s.id] = s.nivel; });
        caja.innerHTML = `<div class="small text-muted">${d.gratis ? 'Consulta ya pagada: vigente hasta el próximo partido.' : `Se cobraron ${d.cobrado}.`}</div>` +
            d.sugerencias.map(s => `<div class="ojeador-sugerencia">
                <button type="button" class="once-resultado__foto" data-ficha="${s.id}" aria-label="Ver la ficha de ${E(s.nombre)}">${UI.avatar(s.id, s.pais_id, 'sm')}</button>
                <div class="min-w-0 flex-grow-1">
                    <strong>${E(s.nombre)}</strong> <span class="nivel-forma nivel-forma--${E(s.nivel.codigo || '')}">${E(s.nivel.etiqueta)}</span>
                    <small class="d-block text-muted">${UI.bandera('', { id: s.pais_id })} ${E(s.pais_nombre)} · ${E(s.posicion_siglas)}</small>
                    <small class="d-block">${E(s.porque)}</small>
                </div>
                <button type="button" class="btn btn-sm btn-outline-success rounded-pill" data-agregar-ojeador="${s.id}" ${motivoNoAgregar(s) ? 'disabled' : ''}>Agregar</button>
            </div>`).join('');
        caja.querySelectorAll('[data-agregar-ojeador]').forEach(b => b.addEventListener('click', () => {
            const s = d.sugerencias.find(x => x.id === Number(b.dataset.agregarOjeador));
            if (agregarJugador(s)) b.disabled = true;
        }));
    }

    // --- Ficha del jugador (ventana) -------------------------------------------------------------------------------
    const modal = new bootstrap.Modal($('modalFicha'));
    let grafico = null;
    document.addEventListener('click', ev => {
        const b = ev.target.closest('[data-ficha]');
        if (b) abrirFicha(Number(b.dataset.ficha));
    });

    async function abrirFicha(id) {
        const cuerpo = $('fichaCuerpo');
        cuerpo.innerHTML = '<div class="text-center text-muted py-5"><span class="spinner-border me-2"></span>Cargando ficha…</div>';
        modal.show();
        try {
            const r = await fetch(C.urls.ficha.replace('{id}', id));
            if (!r.ok) throw new Error();
            renderFicha(await r.json());
        } catch (e) { cuerpo.innerHTML = '<div class="text-danger text-center py-4">No se pudo cargar la ficha.</div>'; }
    }

    function renderFicha(f) {
        const n = f.nivel || {};
        const t = f.totales;
        const prox = f.proximo ? (f.proximo.faltan === 0 ? `Juega el próximo partido vs ${E(f.proximo.rival)}` : `Juega en ${f.proximo.faltan} partidos vs ${E(f.proximo.rival)}`) : (f.eliminado ? E(f.eliminado) : 'Sin partido programado');
        const lesionTxt = f.lesion ? `🚑 Lesionado (${E(f.lesion.nombre)}): baja por ${E(f.lesion.restantes)} partido${f.lesion.restantes == 1 ? '' : 's'} de su selección · ` : '';
        const enEquipo = equipoDe(f.id);
        const puedeAgregar = !vistaDesbloqueo && !enEquipo && !f.eliminado;
        $('fichaCuerpo').innerHTML = `
            <div class="ficha-pop__cabeza">
                <span class="ficha-pop__avatar">${UI.avatar(f.id, f.pais_id)}<span class="avatar-dorsal">${E(f.numero ?? '')}</span></span>
                <div class="min-w-0">
                    <h3 id="fichaTitulo" class="h4 fw-bold text-white mb-1">${E(f.nombre)} ${f.leyenda ? INSIGNIA_LEYENDA : ''}</h3>
                    <div class="small text-muted">${UI.bandera(f.bandera, { id: f.pais_id })} ${E(f.pais)} · ${E(f.posicion)} (${E(f.siglas)})${f.edad ? ` · ${E(f.edad)} años` : ''}</div>
                    <div class="d-flex flex-wrap gap-1 mt-2">
                        <span class="nivel-forma nivel-forma--${E(n.codigo || 'sin')}" title="Según sus últimos ${n.partidos || 0} partidos">${n.codigo === 'racha' ? '🔥 ' : ''}${E(n.etiqueta || 'Sin datos')}</span>
                        ${lesionTxt ? `<span class="ficha-pop__chip text-danger">${lesionTxt.replace(/ · $/, "")}</span>` : ""}<span class="ficha-pop__chip"><i class="bi bi-calendar-event"></i> ${prox}</span>
                        <span class="ficha-pop__chip">OVR ${E(f.overall)}</span>
                        ${enEquipo ? `<span class="ficha-pop__chip ficha-pop__chip--ok"><i class="bi bi-check2"></i> En tu equipo ${enEquipo}</span>` : ''}
                    </div>
                    ${(f.especialidades || []).length ? `<div class="esp-iconos">${f.especialidades.map(e => `<span class="esp-chip esp-chip--mini" title="${E(e.descripcion)}"><i class="bi ${E(e.icono)}"></i>${E(e.nombre)}</span>`).join('')}</div>` : ''}
                </div>
            </div>
            <div class="ficha-pop__kpis">
                <div><strong>${t.partidos}</strong><span>Partidos</span></div>
                <div><strong>${t.goles}</strong><span>Goles</span></div>
                <div><strong>${t.asistencias}</strong><span>Asist.</span></div>
                <div><strong>${t.vallas}</strong><span>Vallas</span></div>
                <div><strong>${t.puntos}</strong><span>Pts fantasy</span></div>
                <div><strong class="text-warning">${f.ganado ? f.ganado.monto : 0}</strong><span>Te pagó</span></div>
            </div>
            <h4 class="h6 text-white mt-3 mb-1">Partido a partido <small class="text-muted fw-normal">(puntos fantasy de cada partido en este Mundial)</small></h4>
            ${f.partidos.length ? `<div class="ficha-pop__grafico"><canvas id="graficoFicha" aria-label="Puntos fantasy por partido" role="img"></canvas></div>
                <details class="mt-2"><summary class="small text-muted">Ver datos</summary>
                <div class="table-responsive"><table class="table table-sm table-dark small mb-0"><thead><tr><th>Rival</th><th>Marcador</th><th>G</th><th>A</th><th>Calif.</th><th>Pts</th></tr></thead><tbody>
                ${f.partidos.slice().reverse().map(p => `<tr><td>${UI.bandera(p.bandera, { id: p.rival_id })} ${E(p.rival)}</td><td>${E(p.marcador)} (${E(p.resultado)})</td><td>${p.goles}</td><td>${p.asistencias}</td><td>${p.calificacion ?? '—'}</td><td>${p.puntos}</td></tr>`).join('')}
                </tbody></table></div></details>`
              : '<p class="text-muted small">Todavía no juega en este Mundial.</p>'}
            ${puedeAgregar ? `<button type="button" id="fichaAgregar" class="btn btn-success fw-bold rounded-pill w-100 mt-3"><i class="bi bi-plus-circle me-1"></i>Agregar a mi equipo ${activa}</button>` : ''}`;
        const btn = $('fichaAgregar');
        if (btn) btn.addEventListener('click', async () => {
            const lista = await fetch(`${C.urls.buscar}?q=${encodeURIComponent(f.nombre)}&pais_id=${f.pais_id}`).then(r => r.json()).catch(() => []);
            const j = lista.find(x => x.id === f.id);
            if (j && agregarJugador(j)) modal.hide();
        });
        dibujarGrafico(f.partidos);
    }

    function dibujarGrafico(partidos) {
        if (grafico) { grafico.destroy(); grafico = null; }
        const canvas = $('graficoFicha');
        if (!canvas || !window.Chart) return;
        if (window.GraficosFIFAV) GraficosFIFAV.estilo();
        const color = getComputedStyle(document.documentElement).getPropertyValue('--s1').trim() || '#3987e5';
        grafico = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: partidos.map(p => `${p.resultado} ${p.rival}`),
                datasets: [{ label: 'Puntos fantasy', data: partidos.map(p => p.puntos), backgroundColor: color,
                    borderRadius: 4, borderSkipped: 'start', maxBarThickness: 28 }],
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                animation: GraficosFIFAV && GraficosFIFAV.reducido ? false : { duration: 700 },
                plugins: { legend: { display: false }, tooltip: { callbacks: {
                    title: items => { const p = partidos[items[0].dataIndex]; return `${p.local ? 'vs' : 'en'} ${p.rival} · ${p.marcador}`; },
                    label: item => { const p = partidos[item.dataIndex];
                        return [`${p.puntos} pts fantasy`, `${p.goles} G · ${p.asistencias} A${p.valla ? ' · valla invicta' : ''}`,
                                p.calificacion != null ? `Calificación ${p.calificacion}` : 'Calificación: no registrada'].filter(Boolean); },
                } } },
                scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, callback(v) { const l = this.getLabelForValue(v); return l.length > 12 ? l.slice(0, 11) + '…' : l; } } },
                          y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,.06)' } } },
            },
        });
    }
    $('modalFicha').addEventListener('hidden.bs.modal', () => { if (grafico) { grafico.destroy(); grafico = null; } });

    // --- Arranque --------------------------------------------------------------------------------------------------
    if (window.location.hash.startsWith('#equipo-')) {
        const n = Number(window.location.hash.slice(8));
        if (equipos[n]) activa = n;
    }
    renderTodo();
    ejecutarBusqueda();
    cargarNiveles(Object.values(equipos).flatMap(e => e.jugadores.map(j => j.id)));
});
