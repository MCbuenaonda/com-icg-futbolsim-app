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
        if (f) { ev.preventDefault(); abrirFicha(f.dataset.tvFicha); return; }
        const b = ev.target.closest('[data-tv-respuesta]');
        if (b) { ev.preventDefault(); responder(b); }
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
