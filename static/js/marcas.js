/*
 * Marcas y patrocinios (Corporativos): acciones compartidas por la cartera (/corporativo/<SIGLA>), el inicio de
 * Corporativos y la página /corporativo/marcas.
 *   [data-promover="<contrato_id>"]  -> modal con las marcas interesadas en ese representado (GET /corporativos/contratos/{id}/marcas)
 *                                       y botón «Promover» por marca (POST .../promover, la marca responde en la siguiente ronda: cada 4 partidos).
 *   [data-promover-marca]            -> promover directo (página de marcas: data-contrato + data-marca).
 *   [data-patrocinio-respuesta]      -> aceptar / rechazar una oferta de patrocinio (POST /corporativos/patrocinios/{id}/{respuesta}).
 * Los mensajes van al elemento #alertaMarcas (o #alertaPerfil) de la página.
 */
(() => {
    const fmt = n => Number(n || 0).toLocaleString('en-US');
    const esc = s => UI.escapar(String(s ?? ''));
    const alertaEl = () => document.getElementById('alertaMarcas') || document.getElementById('alertaPerfil') || document.getElementById('alertaCorp');
    const avisar = (msg, tipo) => { const el = alertaEl(); if (el) { UI.mostrarAlertaEn(el, msg, tipo); el.scrollIntoView({ block: 'center', behavior: 'smooth' }); } };

    async function post(url, cuerpo) {
        const resp = await UI.cargando(fetch(url, {
            method: 'POST', headers: { accept: 'application/json', 'content-type': 'application/json' },
            body: cuerpo ? JSON.stringify(cuerpo) : undefined
        }));
        const datos = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(datos.detail || 'No se pudo completar la acción');
        return datos;
    }

    function modal() {
        let el = document.getElementById('modalPromover');
        if (el) return el;
        el = document.createElement('div');
        el.className = 'modal fade'; el.id = 'modalPromover'; el.tabIndex = -1;
        el.innerHTML = `<div class="modal-dialog modal-lg modal-dialog-scrollable"><div class="modal-content bg-dark border-secondary">
            <div class="modal-header border-secondary"><h5 class="modal-title fw-bold" id="promTitulo">Promover</h5>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Cerrar"></button></div>
            <div class="modal-body" id="promCuerpo"></div></div></div>`;
        document.body.appendChild(el);
        return el;
    }

    function filaMarca(mk, contrato, restantes) {
        const bloqueada = mk.traba || restantes <= 0;
        const motivo = mk.traba || (restantes <= 0 ? 'Ya usaste tus promociones de esta ronda' : '');
        return `<div class="prom-marca ${bloqueada ? 'prom-marca--off' : ''}" style="--marca:${esc(mk.color)}">
            <span class="marca-avatar"><img src="${esc(mk.logo)}" alt=""></span>
            <div class="min-w-0 flex-grow-1">
                <div class="d-flex align-items-center gap-2 flex-wrap"><strong>${esc(mk.nombre)}</strong>
                    <span class="x-post-rubro"><i class="bi ${esc(mk.rubro_icono)}"></i>${esc(mk.rubro_nombre)} · ${esc(mk.alcance_nombre)}${mk.region ? ' ' + esc(mk.region) : ''}</span></div>
                <div class="small text-muted">Busca: ${esc(mk.perfil.toLowerCase())}</div>
                <div class="prom-encaje" title="Encaje ${mk.encaje}/100"><span style="width:${mk.encaje}%"></span></div>
                <div class="small mt-1">Firma <strong>${fmt(mk.firma)}</strong> · <strong>${fmt(mk.pago_ciclo)}</strong> por ciclo
                    ${bloqueada ? `<span class="text-warning ms-1"><i class="bi bi-lock-fill"></i> ${esc(motivo)}</span>`
                                : `<span class="text-info ms-1">· ${Math.round(mk.prob * 100)}% de que acepte</span>`}</div>
            </div>
            <button class="btn btn-sm btn-outline-success rounded-pill flex-shrink-0" data-promover-marca="${mk.id}" data-contrato="${esc(contrato)}"
                data-nombre-marca="${esc(mk.nombre)}" ${bloqueada ? 'disabled' : ''}><i class="bi bi-megaphone-fill"></i> Promover</button>
        </div>`;
    }

    async function abrirPromover(contrato, nombre) {
        let datos;
        try {
            const r = await UI.cargando(fetch(`/corporativos/contratos/${encodeURIComponent(contrato)}/marcas`, { headers: { accept: 'application/json' } }));
            datos = await r.json();
            if (!r.ok) throw new Error(datos.detail || 'No se pudieron cargar las marcas');
        } catch (e) { avisar(e.message, 'danger'); return; }
        const el = modal();
        el.querySelector('#promTitulo').textContent = `Promover a ${datos.nombre} con una marca`;
        const actuales = datos.actuales.length
            ? `<div class="mb-3 small"><span class="text-muted">Ya lo patrocinan:</span> ${datos.actuales.map(a => `<span class="prom-actual" style="--marca:${esc(a.color)}"><img src="${esc(a.logo)}" alt="">${esc(a.nombre)}</span>`).join(' ')}</div>` : '';
        el.querySelector('#promCuerpo').innerHTML = `
            <p class="small text-muted mb-2">Le presentas el representado a una marca; responde en <strong>${datos.responde_en} partido${datos.responde_en === 1 ? '' : 's'}</strong> (las marcas deciden cada 4 partidos).
              Máximo ${datos.max_marcas} marcas por representado y una por rubro. Te quedan <strong>${datos.promociones_restantes}</strong> promociones en esta ronda.
              Del patrocinio, el ${datos.comision}% es tu comisión y se cobra con tu sueldo.</p>
            ${actuales}
            ${datos.marcas.length ? datos.marcas.map(mk => filaMarca(mk, contrato, datos.promociones_restantes)).join('')
                                   : '<p class="text-muted">Por ahora ninguna marca está interesada en este representado: que juegue y gane le sube el encaje.</p>'}`;
        bootstrap.Modal.getOrCreateInstance(el).show();
    }

    document.addEventListener('click', async ev => {
        const abrir = ev.target.closest('[data-promover]');
        if (abrir) { ev.preventDefault(); abrirPromover(abrir.dataset.promover, abrir.dataset.nombre); return; }

        const prom = ev.target.closest('[data-promover-marca]');
        if (prom) {
            ev.preventDefault();
            prom.disabled = true;
            try {
                const d = await post(`/corporativos/contratos/${encodeURIComponent(prom.dataset.contrato)}/promover`, { marca_id: Number(prom.dataset.promoverMarca) });
                const m = document.getElementById('modalPromover');
                if (m) bootstrap.Modal.getOrCreateInstance(m).hide();
                avisar(d.mensaje, 'success');
                prom.innerHTML = '<i class="bi bi-hourglass-split"></i> Promovido';
                // cupo de la ronda ya descontado: el contador del perfil se actualiza y, si se agotó, se bloquea «Promover»
                if (d.promos) {
                    document.dispatchEvent(new CustomEvent('corp:promos', { detail: d.promos }));
                    if (d.promos.restantes <= 0) {
                        document.querySelectorAll('[data-promover-marca]').forEach(b => {
                            if (b === prom) return;
                            b.disabled = true;
                            b.title = 'Ya usaste tus promociones de esta ronda';
                        });
                    }
                }
            } catch (e) { avisar(e.message, 'danger'); prom.disabled = false; }
            return;
        }

        const resp = ev.target.closest('[data-patrocinio-respuesta]');
        if (resp) {
            ev.preventDefault();
            const { patrocinioRespuesta: respuesta, patrocinio, marca, nombre, firma } = resp.dataset;
            const ok = await UI.confirmar(respuesta === 'aceptar'
                ? { titulo: `¿Aceptar a ${marca}?`, mensaje: `Patrocinará a ${nombre}: cobras ${fmt(firma)} de firma ahora (tu comisión incluida) y el patrocinio en pagos cada 4 partidos desde la próxima ronda.`, textoConfirmar: 'Aceptar' }
                : { titulo: `¿Rechazar a ${marca}?`, mensaje: `La oferta para ${nombre} se pierde y la marca queda libre para otros.`, textoConfirmar: 'Rechazar', peligro: true });
            if (!ok) return;
            try {
                const d = await post(`/corporativos/patrocinios/${encodeURIComponent(patrocinio)}/${respuesta}`);
                avisar(d.mensaje, 'success');
                UI.refrescarSaldo && UI.refrescarSaldo();
                setTimeout(() => location.reload(), 1400);
            } catch (e) { avisar(e.message, 'danger'); }
        }
    });
})();
