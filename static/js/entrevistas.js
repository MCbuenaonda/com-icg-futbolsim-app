/*
 * Entrevistas que piden los medios por tus representados (Decisiones de Corporativos).
 *   [data-entrevista="<id>"][data-postura="prudente|seguro|polemico|declinar"] -> POST /corporativos/entrevistas/{id}/{postura}
 * Muestra el resultado y recarga para que la entrevista desaparezca de la lista.
 */
(() => {
    document.addEventListener('click', async ev => {
        const b = ev.target.closest('[data-entrevista]');
        if (!b) return;
        ev.preventDefault();
        const caja = b.closest('.ent-card');
        caja.querySelectorAll('button').forEach(x => { x.disabled = true; });
        const alerta = document.getElementById('alertaEntrevistas') || document.getElementById('alertaCorp');
        try {
            const r = await UI.cargando(fetch(`/corporativos/entrevistas/${encodeURIComponent(b.dataset.entrevista)}/${encodeURIComponent(b.dataset.postura)}`,
                { method: 'POST', headers: { accept: 'application/json' } }));
            const d = await r.json().catch(() => ({}));
            if (!r.ok) throw new Error(d.detail || 'No se pudo responder la entrevista');
            UI.mostrarAlertaEn(alerta, d.mensaje, d.exito === false ? 'warning' : 'success');
            setTimeout(() => location.reload(), 2200);
        } catch (e) {
            UI.mostrarAlertaEn(alerta, e.message, 'danger');
            caja.querySelectorAll('button').forEach(x => { x.disabled = false; });
        }
    });
})();
