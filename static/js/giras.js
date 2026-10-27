/*
 * Gira de exhibición grupal (cartera de /corporativo/<SIGLA>): el botón [data-gira-grupal="<contrato_id>"] abre un modal con
 * casillas para elegir de 1 a N jugadores (GET /corporativos/giras/jugadores: costo, rango de ingreso y si puede salir),
 * suma el total y organiza la gira (POST /corporativos/giras). La gira dura unos partidos y cobra partido a partido.
 */
(() => {
    const fmt = n => Number(n || 0).toLocaleString('en-US');
    const esc = s => UI.escapar(String(s ?? ''));
    const alerta = () => document.getElementById('alertaPerfil');

    function modal() {
        let el = document.getElementById('modalGira');
        if (el) return el;
        el = document.createElement('div');
        el.className = 'modal fade'; el.id = 'modalGira'; el.tabIndex = -1;
        el.innerHTML = `<div class="modal-dialog modal-lg modal-dialog-scrollable"><div class="modal-content bg-dark border-secondary">
            <div class="modal-header border-secondary"><h5 class="modal-title fw-bold"><i class="bi bi-airplane-fill text-info me-2"></i>Gira de exhibición</h5>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Cerrar"></button></div>
            <div class="modal-body" id="giraCuerpo"></div>
            <div class="modal-footer border-secondary justify-content-between">
              <div class="small" id="giraTotal"></div>
              <button class="btn btn-info rounded-pill fw-bold" id="giraOrganizar" disabled><i class="bi bi-airplane me-1"></i>Organizar gira</button>
            </div></div></div>`;
        document.body.appendChild(el);
        return el;
    }

    async function abrir(preseleccion) {
        let d;
        try {
            const r = await UI.cargando(fetch('/corporativos/giras/jugadores', { headers: { accept: 'application/json' } }));
            d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'No se pudo cotizar la gira');
        } catch (e) { UI.mostrarAlertaEn(alerta(), e.message, 'danger'); return; }
        const tope = Math.min(d.max_por_gira, d.jugadores_restantes);
        const el = modal();
        el.querySelector('#giraCuerpo').innerHTML = `
            <p class="small text-muted mb-2">La gira dura <strong>${d.partidos} partidos</strong> del torneo y cobra su recaudación
              <strong>partido a partido</strong>. Puedes mandar hasta <strong>${tope}</strong> jugador${tope === 1 ? '' : 'es'} en esta gira
              (máximo ${d.max_por_gira} por gira; te quedan ${d.jugadores_restantes} este ciclo y ${d.giras_restantes} gira${d.giras_restantes === 1 ? '' : 's'} en curso disponible${d.giras_restantes === 1 ? '' : 's'}).
              Capital del corporativo: <strong>${fmt(d.capital)}</strong>.</p>
            ${!d.giras_restantes || !tope ? '<div class="alert alert-warning small py-2">Ahora no puedes organizar otra gira de jugadores.</div>' : ''}
            <div class="gira-lista">${d.jugadores.map(j => `
              <label class="gira-fila ${j.motivo ? 'gira-fila--off' : ''}">
                <input type="checkbox" class="form-check-input" value="${esc(j.contrato_id)}" data-costo="${j.costo}" data-min="${j.ingreso_min}" data-max="${j.ingreso_max}"
                  ${j.motivo || !tope ? 'disabled' : ''} ${!j.motivo && j.contrato_id === preseleccion && tope ? 'checked' : ''}>
                ${UI.avatar ? UI.avatar(j.ref_id, j.pais_id) : ''}
                <span class="min-w-0 flex-grow-1"><span class="d-block fw-semibold text-white text-truncate">${esc(j.nombre)}</span>
                  <span class="d-block fs-8 text-muted">${j.motivo ? esc(j.motivo) : `Costo ${fmt(j.costo)} · recauda ${fmt(j.ingreso_min)}–${fmt(j.ingreso_max)} · hasta ${j.aficionados_max} aficionados · su selección: ${j.forma_seleccion}/15`}</span></span>
                ${j.motivo ? '' : `<span class="gira-retorno" title="Retorno esperado sobre el costo">×${j.retorno}</span>`}
              </label>`).join('')}</div>`;
        const boton = el.querySelector('#giraOrganizar');
        const cajas = [...el.querySelectorAll('input[type=checkbox]')];
        const actualizar = () => {
            const elegidos = cajas.filter(c => c.checked);
            cajas.forEach(c => { if (!c.checked && !c.dataset.bloq) c.disabled = c.closest('.gira-fila--off') !== null || elegidos.length >= tope; });
            const suma = k => elegidos.reduce((a, c) => a + Number(c.dataset[k]), 0);
            el.querySelector('#giraTotal').innerHTML = elegidos.length
                ? `<strong>${elegidos.length}</strong> jugador${elegidos.length > 1 ? 'es' : ''} · cuesta <strong>${fmt(suma('costo'))}</strong> · recauda <strong class="text-success">${fmt(suma('min'))}–${fmt(suma('max'))}</strong> en ${d.partidos} partidos`
                : '<span class="text-muted">Elige uno o varios jugadores</span>';
            boton.disabled = !elegidos.length;
        };
        cajas.forEach(c => { if (c.disabled) c.dataset.bloq = '1'; c.addEventListener('change', actualizar); });
        actualizar();
        boton.onclick = async () => {
            boton.disabled = true;
            try {
                const r = await UI.cargando(fetch('/corporativos/giras', { method: 'POST', headers: { 'content-type': 'application/json', accept: 'application/json' },
                    body: JSON.stringify({ contratos: cajas.filter(c => c.checked).map(c => c.value) }) }));
                const res = await r.json().catch(() => ({}));
                if (!r.ok) throw new Error(res.detail || 'No se pudo organizar la gira');
                bootstrap.Modal.getOrCreateInstance(el).hide();
                UI.mostrarAlertaEn(alerta(), res.mensaje, 'success');
                setTimeout(() => location.reload(), 1300);
            } catch (e) { UI.mostrarAlertaEn(alerta(), e.message, 'danger'); boton.disabled = false; }
        };
        bootstrap.Modal.getOrCreateInstance(el).show();
    }

    document.addEventListener('click', ev => {
        const b = ev.target.closest('[data-gira-grupal]');
        if (b) { ev.preventDefault(); abrir(b.dataset.giraGrupal); }
    });
})();
