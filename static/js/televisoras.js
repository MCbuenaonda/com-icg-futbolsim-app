/*
 * Televisoras (Corporativos): la página /corporativo/televisoras y los chips de TV de la cartera y del inicio.
 *   [data-tv-ficha="<id>"]       -> ficha de la cadena en un modal (GET /corporativos/televisoras/{id})
 *   [data-tv-respuesta]          -> aceptar / rechazar una oferta (POST /corporativos/tv/{id}/{respuesta})
 *   #tvFiltros                   -> filtros y orden del catálogo, en el navegador, de a POR_PAGINA con «Mostrar más»
 * Los mensajes van a #alertaTv (o #alertaPerfil / #alertaCorp).
 */
(() => {
    const fmt = n => Number(n || 0).toLocaleString('en-US');
    const esc = s => UI.escapar(String(s ?? ''));
    const alertaEl = () => document.getElementById('alertaTv') || document.getElementById('alertaPerfil') || document.getElementById('alertaCorp');
    const avisar = (msg, tipo) => { const el = alertaEl(); if (el) { UI.mostrarAlertaEn(el, msg, tipo); el.scrollIntoView({ block: 'center', behavior: 'smooth' }); } };
    const POR_PAGINA = 48;

    // --- Ficha de la cadena ---
    function modal() {
        let el = document.getElementById('modalTv');
        if (el) return el;
        el = document.createElement('div');
        el.className = 'modal fade'; el.id = 'modalTv'; el.tabIndex = -1;
        el.setAttribute('aria-labelledby', 'tvFichaTitulo');
        el.innerHTML = `<div class="modal-dialog modal-dialog-centered modal-dialog-scrollable"><div class="modal-content bg-dark border-secondary tv-ficha" id="tvFichaCaja"></div></div>`;
        document.body.appendChild(el);
        return el;
    }

    const LETRAS = { V: 'Victoria', E: 'Empate', D: 'Derrota' };
    const resultados = r => (r || []).map(x => `<span class="tv-res tv-res--${esc(x)}" title="${LETRAS[x] || ''}">${esc(x)}</span>`).join('');

    // Dueño y comentaristas de la cadena (ficticios; ver generar_equipo_tv.py). Vacío si la cadena aún no los tiene.
    function equipoHtml(eq, aj) {
        if (!eq || !eq.dueno) return '';
        const d = eq.dueno;
        const signo = n => (n > 0 ? '+' : '') + n;
        const efecto = aj && (aj.fidelidad || aj.exigencia)
            ? ` Efecto en la cadena: fidelidad ${signo(aj.fidelidad)}, exigencia del bono ${signo(aj.exigencia)} puntos.` : '';
        const cara = (p, clase = '') => p.avatar_url ? `<img class="tv-cara ${clase}" src="${esc(p.avatar_url)}" alt="${esc(p.nombre)}" loading="lazy" onerror="this.remove()">` : '';
        const coment = (eq.comentaristas || []).map(c => `<div class="tv-persona">${cara(c)}<span><strong>${esc(c.nombre)}</strong><small>comentarista</small></span></div>`).join('');
        return `<h6 class="fw-bold text-white mt-3 mb-1 small">Quién la maneja</h6>
            <div class="tv-equipo">
              <div class="tv-persona tv-persona--dueno" title="${esc(d.rasgo_texto)}">${cara(d)}<span><strong>${esc(d.nombre)}</strong><small>dueño · ${esc(d.rasgo_nombre)}</small></span></div>
              ${coment}
            </div>
            <div class="fs-8 text-muted mt-1">${esc(d.rasgo_texto)}${esc(efecto)} En la transmisión comentan ${(eq.comentaristas || []).map(c => esc(c.nombre)).join(' y ')}.</div>`;
    }

    function fichaHtml(t) {
        const tar = t.tarifa_hoy;
        const historia = (t.historia || []).map(h => `<div class="tv-ficha__hist"><span>${esc(h.pais)} · ${esc(h.sigla)}</span>
            <span class="d-flex gap-1 align-items-center">${resultados(h.resultados)}<small class="text-muted ms-1">${h.estado === 'ACTIVO' ? 'transmitiendo' : 'cobró ' + fmt(h.cobrado)}</small></span></div>`).join('')
            || '<div class="small text-muted">Todavía no firmó con nadie en tu universo.</div>';
        const hermanas = (t.hermanas || []).map(h => `<button type="button" class="tv-hermana" data-tv-ficha="${h.id}" title="${esc(h.nombre)}"><img src="${esc(h.logo)}" alt="${esc(h.nombre)}"></button>`).join('');
        return `<div class="tv-ficha__portada" style="--tv:${esc(t.color)}"><img src="${esc(t.logo)}" alt="${esc(t.nombre)}"></div>
            <div class="modal-body">
              <div class="d-flex justify-content-between align-items-start gap-2">
                <div><h5 class="fw-bold text-white mb-0" id="tvFichaTitulo">${esc(t.nombre)}</h5>
                  <div class="text-muted small">${UI.bandera(t.bandera || '', { id: t.pais_id })} ${esc(t.pais)} · «${esc(t.lema)}»</div></div>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Cerrar"></button>
              </div>
              <div class="mk-ficha__datos mt-3">
                <span><i class="bi bi-tv"></i>${esc(t.papel_nombre)} · ${esc(t.nivel_nombre)}</span>
                <span><i class="bi ${esc(t.perfil_icono)}"></i>${esc(t.perfil_nombre)}: ${esc(t.perfil_descripcion.toLowerCase())}</span>
                <span><i class="bi bi-gift"></i>Da el bono con el ${t.exigencia}% de los puntos</span>
                <span><i class="bi bi-heart-pulse"></i>Fidelidad ${Math.round(t.fidelidad * 100)}/100 ${t.fidelidad >= 0.7 ? '(renueva fácil)' : (t.fidelidad < 0.45 ? '(exigente para renovar)' : '')}</span>
              </div>
              <h6 class="fw-bold text-white mt-3 mb-1 small">Lo que pagaría hoy a ${esc(t.pais)} por partido</h6>
              <div class="tv-ficha__tarifa">
                <div><i class="bi bi-trophy-fill text-success"></i><strong>${fmt(tar.victoria)}</strong><small>victoria</small></div>
                <div><i class="bi bi-dash-circle-fill text-warning"></i><strong>${fmt(tar.empate)}</strong><small>empate</small></div>
                <div><i class="bi bi-x-circle-fill text-danger"></i><strong>${fmt(tar.derrota)}</strong><small>derrota</small></div>
                <div><i class="bi bi-gift-fill text-info"></i><strong>${fmt(tar.bono)}</strong><small>bono por partido</small></div>
              </div>
              <div class="fs-8 text-muted mt-1">Contratos de ${t.partidos_rango[0]} a ${t.partidos_rango[1]} partidos. La tarifa sube o baja según los resultados del contrato anterior.</div>
              ${equipoHtml(t.equipo, t.ajuste_dueno)}
              <h6 class="fw-bold text-white mt-3 mb-1 small">En tu universo</h6>${historia}
              ${hermanas ? `<h6 class="fw-bold text-white mt-3 mb-1 small">Las otras cadenas de ${esc(t.pais)}</h6><div class="d-flex gap-2">${hermanas}</div>` : ''}
            </div>`;
    }

    async function abrirFicha(id) {
        const el = modal();
        const caja = el.querySelector('#tvFichaCaja');
        caja.innerHTML = '<div class="modal-body text-center text-muted py-5"><span class="spinner-border spinner-border-sm me-2"></span>Cargando…</div>';
        bootstrap.Modal.getOrCreateInstance(el).show();
        try {
            const r = await fetch(`/corporativos/televisoras/${encodeURIComponent(id)}`, { headers: { accept: 'application/json' } });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'No se pudo cargar la ficha');
            caja.innerHTML = fichaHtml(d);
        } catch (e) {
            caja.innerHTML = `<div class="modal-body"><div class="alert alert-danger small mb-0">${esc(e.message)}</div></div>`;
        }
    }

    // --- Detalle de un contrato (fila de «Tus contratos») ---
    function contratoHtml(c) {
        const ch = c.cadena, activo = c.estado === 'ACTIVO';
        const pctTxt = c.pct === null || c.pct === undefined ? 'sin partidos aún' : `${c.pct}% de los puntos`;
        const bono = c.bono_en_camino
            ? `<span class="text-success"><i class="bi bi-gift-fill"></i> El bono va en camino</span>`
            : (c.alcanzable ? `<span class="text-warning"><i class="bi bi-hourglass-split"></i> Aún alcanzas el bono</span>` : `<span class="text-danger"><i class="bi bi-x-circle"></i> El bono ya no es alcanzable</span>`);
        const prox = c.proximo ? `<span><i class="bi bi-calendar-event"></i>Próximo partido de ${esc(c.pais)}: ${c.proximo.faltan === 0 ? 'es el siguiente' : 'en ' + c.proximo.faltan + ' partidos'} vs ${esc(c.proximo.rival || '?')}</span>` : '';
        const invitados = (c.invitados || []).map(i => `<div class="tv-ficha__hist"><span><a href="/jugadores/${esc(i.jugador_id)}" class="text-white text-decoration-none">${esc(i.jugador)}</a>
            <small class="text-muted d-block">${esc(i.partido || '')}${i.fecha ? ' · ' + esc(i.fecha) : ''}</small></span>
            <span class="text-end">${i.estado === 'REALIZADA' ? `<strong>${fmt(i.pago)}</strong><small class="text-muted d-block">${i.aficionados ? '+' + fmt(i.aficionados) + ' aficionados' : 'realizado'}</small>` : '<span class="badge text-bg-info">Programado</span>'}</span></div>`).join('')
            || '<div class="small text-muted">Esta cadena todavía no ha llevado invitados de tu universo.</div>';
        const rel = (c.relacionadas || []).map(r => `<div class="tv-ficha__hist"><span>${esc(r.tele.nombre)} <small class="text-muted">· ${esc(r.tipo === 'RENOVACION' ? 'renovación' : 'competencia')}</small></span><span>${fmt(r.esperado)} / partido</span></div>`).join('');
        const hermanas = (c.hermanas || []).map(h => `<button type="button" class="tv-hermana" data-tv-ficha="${h.id}" title="${esc(h.nombre)}"><img src="${esc(h.logo)}" alt="${esc(h.nombre)}"></button>`).join('');
        return `<div class="tv-ficha__portada" style="--tv:${esc(ch.color)}"><img src="${esc(ch.logo)}" alt="${esc(ch.nombre)}"></div>
            <div class="modal-body">
              <div class="d-flex justify-content-between align-items-start gap-2">
                <div><h5 class="fw-bold text-white mb-0" id="tvFichaTitulo">${esc(ch.nombre)}</h5>
                  <div class="text-muted small">${UI.bandera(c.bandera || '', { id: c.pais_id })} ${esc(c.pais)} · «${esc(c.lema)}» · ${esc(ch.papel_nombre)}, ${esc(ch.nivel_nombre)}</div></div>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Cerrar"></button>
              </div>
              <div class="mt-2">${activo ? '<span class="badge text-bg-success">Transmitiendo</span>' : '<span class="badge text-bg-info">Firmado: empieza al terminar el actual</span>'}
                ${c.aviso ? '<span class="badge text-bg-warning ms-1"><i class="bi bi-bell-fill"></i> Renovación abierta</span>' : ''}
                <span class="badge text-bg-dark ms-1">${esc(c.tipo === 'INICIAL' ? 'Contrato inicial' : (c.tipo === 'RENOVACION' ? 'Renovación' : 'Contrato por competencia'))}</span></div>

              <h6 class="fw-bold text-white mt-3 mb-1 small">Avance del contrato</h6>
              <div class="tv-avance my-1"><span style="width:${c.partidos ? Math.round(c.jugados * 100 / c.partidos) : 0}%"></span></div>
              <div class="small d-flex flex-wrap gap-2 align-items-center"><span>${c.jugados}/${c.partidos} partidos</span>${resultados(c.resultados)}
                <span class="text-muted">· ${c.cuenta.victoria} V · ${c.cuenta.empate} E · ${c.cuenta.derrota} D</span></div>

              <div class="tv-ficha__tarifa mt-3">
                <div><i class="bi bi-cash-coin text-success"></i><strong>${fmt(c.ganado)}</strong><small>ganado en total</small></div>
                <div><i class="bi bi-tv text-info"></i><strong>${fmt(c.cobrado)}</strong><small>por partidos</small></div>
                <div><i class="bi bi-gift-fill text-warning"></i><strong>${fmt(c.bono_cobrado)}</strong><small>bono cobrado</small></div>
                <div><i class="bi bi-graph-up text-primary"></i><strong>${fmt(c.esperado)}</strong><small>esperado / partido</small></div>
              </div>

              <h6 class="fw-bold text-white mt-3 mb-1 small">Lo que paga por partido</h6>
              <div class="tv-ficha__tarifa">
                <div><i class="bi bi-trophy-fill text-success"></i><strong>${fmt(c.pago_victoria)}</strong><small>victoria</small></div>
                <div><i class="bi bi-dash-circle-fill text-warning"></i><strong>${fmt(c.pago_empate)}</strong><small>empate</small></div>
                <div><i class="bi bi-x-circle-fill text-danger"></i><strong>${fmt(c.pago_derrota)}</strong><small>derrota</small></div>
                <div><i class="bi bi-gift-fill text-info"></i><strong>${fmt(c.bono_partido)}</strong><small>bono por partido</small></div>
              </div>

              <h6 class="fw-bold text-white mt-3 mb-1 small">El bono</h6>
              <div class="small">La cadena lo da con el ${c.exigencia}% de los puntos: bono total de <strong>${fmt(c.bono_total)}</strong>. Llevas ${pctTxt} (${c.puntos} de ${c.puntos_necesarios} puntos necesarios).<br>
                ${activo ? bono : ''}${activo && c.puntos_faltan > 0 && c.alcanzable ? ` · te faltan ${c.puntos_faltan} puntos de ${c.puntos_posibles} posibles` : ''}</div>

              <div class="mk-ficha__datos mt-3">
                <span><i class="bi ${esc(ch.perfil_icono)}"></i>${esc(ch.perfil_nombre)}: ${esc(c.perfil_texto.toLowerCase())}</span>
                <span><i class="bi bi-heart-pulse"></i>Fidelidad ${Math.round(ch.fidelidad * 100)}/100 ${ch.fidelidad >= 0.7 ? '(renueva fácil)' : (ch.fidelidad < 0.45 ? '(exigente para renovar)' : '')}</span>
                <span><i class="bi bi-speedometer2"></i>Tarifa con forma ×${Number(c.forma).toFixed(2)} según los resultados del contrato anterior</span>
                ${c.firmado_ciclo ? `<span><i class="bi bi-pen"></i>Firmado en el ciclo ${c.firmado_ciclo}</span>` : ''}
                ${c.previos ? `<span><i class="bi bi-arrow-repeat"></i>${c.previos} contrato${c.previos > 1 ? 's' : ''} anterior${c.previos > 1 ? 'es' : ''} con ${esc(c.pais)}</span>` : ''}
                ${prox}
              </div>

              ${equipoHtml(ch.equipo, ch.ajuste_dueno)}
              <h6 class="fw-bold text-white mt-3 mb-1 small">Invitados de esta cadena en tu universo</h6>${invitados}
              ${rel ? `<h6 class="fw-bold text-white mt-3 mb-1 small">Ofertas para cuando termine</h6>${rel}` : ''}
              <h6 class="fw-bold text-white mt-3 mb-1 small">Con esta cadena en total</h6>
              <div class="small text-muted">${c.cadena_contratos} contrato${c.cadena_contratos === 1 ? '' : 's'} · ${fmt(c.cadena_cobrado)} por partidos · ${fmt(c.cadena_bonos)} en bonos</div>
              ${hermanas ? `<h6 class="fw-bold text-white mt-3 mb-1 small">Las otras cadenas de ${esc(c.pais)}</h6><div class="d-flex gap-2 align-items-center">${hermanas}</div>` : ''}
              <div class="mt-3"><button type="button" class="btn btn-sm btn-outline-info" data-tv-ficha="${ch.id}"><i class="bi bi-info-circle me-1"></i>Ficha de la cadena</button></div>
            </div>`;
    }

    async function abrirContrato(id) {
        const el = modal();
        const caja = el.querySelector('#tvFichaCaja');
        caja.innerHTML = '<div class="modal-body text-center text-muted py-5"><span class="spinner-border spinner-border-sm me-2"></span>Cargando…</div>';
        bootstrap.Modal.getOrCreateInstance(el).show();
        try {
            const r = await fetch(`/corporativos/tv-contrato/${encodeURIComponent(id)}`, { headers: { accept: 'application/json' } });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'No se pudo cargar el contrato');
            caja.innerHTML = contratoHtml(d);
        } catch (e) {
            caja.innerHTML = `<div class="modal-body"><div class="alert alert-danger small mb-0">${esc(e.message)}</div></div>`;
        }
    }

    // --- Ofertas ---
    async function responder(boton) {
        const aceptar = boton.dataset.tvRespuesta === 'aceptar';
        const ok = await UI.confirmar({
            titulo: aceptar ? 'Firmar contrato de transmisión' : 'Rechazar oferta',
            mensaje: aceptar ? `${boton.dataset.cadena} transmitirá los partidos de ${boton.dataset.pais}.`
                             : `¿Rechazar la oferta de ${boton.dataset.cadena} por ${boton.dataset.pais}?`,
            textoConfirmar: aceptar ? 'Firmar' : 'Rechazar', peligro: !aceptar
        });
        if (!ok) return;
        try {
            const r = await UI.cargando(fetch(`/corporativos/tv/${encodeURIComponent(boton.dataset.tv)}/${aceptar ? 'aceptar' : 'rechazar'}`,
                { method: 'POST', headers: { accept: 'application/json' } }));
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.detail || 'No se pudo completar la acción');
            avisar(d.mensaje, 'success');
            setTimeout(() => location.reload(), 1400);
        } catch (e) { avisar(e.message, 'danger'); }
    }

    document.addEventListener('click', ev => {
        const f = ev.target.closest('[data-tv-ficha]');
        const ct = !f && ev.target.closest('[data-tv-contrato]');
        if (ct) { abrirContrato(ct.dataset.tvContrato); return; }
        if (f) { ev.preventDefault(); abrirFicha(f.dataset.tvFicha); return; }
        const b = ev.target.closest('[data-tv-respuesta]');
        if (b) { ev.preventDefault(); responder(b); }
    });

    document.addEventListener('keydown', ev => {
        if (ev.key !== 'Enter' && ev.key !== ' ') return;
        const ct = ev.target.closest && ev.target.closest('[data-tv-contrato]');
        if (ct && ev.target === ct) { ev.preventDefault(); abrirContrato(ct.dataset.tvContrato); }
    });

    // --- Catálogo: filtros, orden y «Mostrar más» ---
    const barra = document.getElementById('tvFiltros');
    if (!barra) return;
    const $ = id => document.getElementById(id);
    const lista = $('tvCatalogoLista');
    const celdas = [...lista.querySelectorAll('.tv-celda')];
    let visibles = POR_PAGINA;
    const CLAVE = 'tv-catalogo-orden';
    try { const o = localStorage.getItem(CLAVE); if (o && [...$('tvOrden').options].some(x => x.value === o)) $('tvOrden').value = o; } catch (e) { /* sin almacenamiento */ }

    function ordenar(a, b) {
        const o = $('tvOrden').value;
        if (o === 'pago') return Number(b.dataset.pago) - Number(a.dataset.pago);
        if (o === 'nombre') return a.dataset.ordenNombre.localeCompare(b.dataset.ordenNombre, 'es');
        if (o === 'pais') return a.dataset.pais.localeCompare(b.dataset.pais, 'es') || Number(b.dataset.nivel) - Number(a.dataset.nivel);
        return Number(b.dataset.nivel) - Number(a.dataset.nivel) || Number(b.dataset.pago) - Number(a.dataset.pago);
    }

    function aplicar(reiniciar = true) {
        if (reiniciar) visibles = POR_PAGINA;
        const q = $('tvBuscar').value.trim().toLowerCase();
        const conf = $('tvConf').value, nivel = $('tvNivel').value, perfil = $('tvPerfil').value;
        const mias = $('tvMias').checked, transmiten = $('tvTransmiten').checked;
        const ok = celdas.filter(c => (!q || c.dataset.nombre.includes(q)) && (!conf || c.dataset.conf === conf)
            && (!nivel || c.dataset.nivel === nivel) && (!perfil || c.dataset.perfil === perfil)
            && (!mias || c.dataset.mia === '1') && (!transmiten || c.dataset.transmite === '1'));
        ok.sort(ordenar);
        const set = new Set(ok);
        celdas.forEach(c => { if (!set.has(c)) c.hidden = true; });
        ok.forEach((c, i) => { c.hidden = i >= visibles; lista.appendChild(c); });
        $('tvConteo').textContent = ok.length === celdas.length ? `${celdas.length} cadenas` : `${ok.length} de ${celdas.length} cadenas`;
        $('tvMas').classList.toggle('d-none', ok.length <= visibles);
        $('tvMas').textContent = `Mostrar más (${Math.max(0, ok.length - visibles)})`;
        $('tvVacio').classList.toggle('d-none', ok.length > 0);
    }

    let t = null;
    $('tvBuscar').addEventListener('input', () => { clearTimeout(t); t = setTimeout(aplicar, 150); });
    ['tvConf', 'tvNivel', 'tvPerfil', 'tvMias', 'tvTransmiten'].forEach(id => $(id).addEventListener('change', () => aplicar()));
    $('tvOrden').addEventListener('change', () => { try { localStorage.setItem(CLAVE, $('tvOrden').value); } catch (e) { /* sin almacenamiento */ } aplicar(); });
    $('tvMas').addEventListener('click', () => { visibles += POR_PAGINA; aplicar(false); });
    aplicar();
})();
