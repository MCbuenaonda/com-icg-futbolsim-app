/*
 * Utilidades de interfaz compartidas por todas las páginas (cargado en templates/base.html).
 *
 *   UI.escapar(texto)                 -> texto seguro para meter en innerHTML (evita inyección de HTML)
 *   UI.confirmar({titulo, mensaje, textoConfirmar, peligro}) -> Promise<boolean>, modal propio
 *                                        (reemplaza al confirm() nativo del navegador)
 *   UI.refrescarSaldo()               -> vuelve a pedir el saldo y actualiza la pill del navbar
 *   UI.alerta(contenedor, mensaje, tipo) -> alerta Bootstrap descartable dentro de 'contenedor'
 *
 * Además, al cargar: toda tarjeta clicable con role="button" se vuelve accesible por teclado
 * (tabindex + Enter/Espacio), y los botones de solo ícono heredan su 'title' como aria-label.
 */
(function () {
    function escapar(texto) {
        return String(texto ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    // ---------- Modal de confirmación ----------
    let modalEl = null;
    function asegurarModal() {
        if (modalEl) return modalEl;
        modalEl = document.createElement('div');
        modalEl.className = 'modal fade';
        modalEl.tabIndex = -1;
        modalEl.setAttribute('aria-hidden', 'true');
        modalEl.setAttribute('aria-labelledby', 'uiConfirmarTitulo');
        modalEl.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content bg-dark text-white border border-secondary">
                    <div class="modal-header border-secondary">
                        <h5 class="modal-title fw-bold" id="uiConfirmarTitulo"></h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Cerrar"></button>
                    </div>
                    <div class="modal-body" id="uiConfirmarMensaje"></div>
                    <div class="modal-footer border-secondary">
                        <button type="button" class="btn btn-outline-light" data-bs-dismiss="modal">Cancelar</button>
                        <button type="button" class="btn fw-bold" id="uiConfirmarAceptar"></button>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(modalEl);
        return modalEl;
    }

    function confirmar({ titulo = '¿Confirmás?', mensaje = '', textoConfirmar = 'Confirmar', peligro = false } = {}) {
        const el = asegurarModal();
        el.querySelector('#uiConfirmarTitulo').textContent = titulo;
        el.querySelector('#uiConfirmarMensaje').textContent = mensaje;
        const aceptar = el.querySelector('#uiConfirmarAceptar');
        aceptar.textContent = textoConfirmar;
        aceptar.className = `btn fw-bold ${peligro ? 'btn-danger' : 'btn-success'}`;
        const modal = bootstrap.Modal.getOrCreateInstance(el);
        return new Promise(resolve => {
            let resultado = false;
            const alAceptar = () => { resultado = true; modal.hide(); };
            const alCerrar = () => {
                aceptar.removeEventListener('click', alAceptar);
                el.removeEventListener('hidden.bs.modal', alCerrar);
                resolve(resultado);
            };
            aceptar.addEventListener('click', alAceptar);
            el.addEventListener('hidden.bs.modal', alCerrar);
            modal.show();
            el.addEventListener('shown.bs.modal', () => aceptar.focus(), { once: true });
        });
    }

    // ---------- Saldo del navbar ----------
    async function refrescarSaldo() {
        const pill = document.getElementById('saldoUsuarioNavbar');
        if (!pill) return;
        try {
            const resp = await fetch('/cuenta/saldo', { headers: { accept: 'application/json' } });
            if (!resp.ok) return;
            const { monto } = await resp.json();
            const anterior = Number(pill.dataset.monto || NaN);
            pill.dataset.monto = monto;
            pill.innerHTML = `<i class="bi bi-coin me-1"></i>${Number(monto).toLocaleString('en-US')} pts`;
            if (!Number.isNaN(anterior) && anterior !== monto) {
                pill.classList.remove('saldo-pill--cambio');
                void pill.offsetWidth;
                pill.classList.add('saldo-pill--cambio');
            }
        } catch (e) { /* el saldo se verá actualizado en la próxima carga */ }
    }

    // ---------- Alertas ----------
    function alerta(contenedor, mensaje, tipo = 'info') {
        if (!contenedor) return;
        contenedor.innerHTML = `<div class="alert alert-${tipo} alert-dismissible fade show" role="alert">
            ${escapar(mensaje)}<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Cerrar"></button></div>`;
    }

    // Alerta de página sobre un elemento '.alert' existente (lo que antes era una función
    // mostrarAlerta copiada en cada template de meta-juego)
    function mostrarAlertaEn(elemento, mensaje, tipo = 'info') {
        if (!elemento) return;
        elemento.className = `alert alert-${tipo}`;
        elemento.setAttribute('role', tipo === 'danger' ? 'alert' : 'status');
        elemento.textContent = mensaje;
        elemento.classList.remove('d-none');
        elemento.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    // ---------- Accesibilidad automática ----------
    function mejorarAccesibilidad(raiz = document) {
        // Tarjetas/divs clicables con role="button": alcanzables con Tab y activables con Enter/Espacio
        raiz.querySelectorAll('[role="button"]:not(button):not(a):not([tabindex])').forEach(el => {
            el.tabIndex = 0;
            el.addEventListener('keydown', ev => {
                if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); el.click(); }
            });
        });
        // Botones/links de solo ícono: el 'title' como nombre accesible
        raiz.querySelectorAll('button[title]:not([aria-label]), a[title]:not([aria-label])').forEach(el => {
            if (!el.textContent.trim()) el.setAttribute('aria-label', el.getAttribute('title'));
        });
    }

    // ---------- Paginador "Mostrar más" (listas largas renderizadas en el servidor) ----------
    // Muestra de a 'porPagina' entre los elementos VISIBLES (respeta los filtros de cada página,
    // que ocultan con la clase d-none) y agrega debajo un contador + botón "Mostrar más".
    // Cada página llama a .reiniciar() después de aplicar sus filtros.
    function paginador({ items, porPagina = 24, despuesDe, etiqueta = 'elementos' }) {
        let limite = porPagina;
        const pie = document.createElement('div');
        pie.className = 'text-center mt-3 ui-paginador';
        pie.innerHTML = `<p class="text-muted small mb-2" aria-live="polite"></p>
            <button type="button" class="btn btn-outline-light btn-sm"><i class="bi bi-arrow-down-circle me-1"></i>Mostrar más</button>`;
        despuesDe.insertAdjacentElement('afterend', pie);
        const contador = pie.querySelector('p');
        const boton = pie.querySelector('button');

        function refrescar() {
            const visibles = [...items()].filter(el => !el.classList.contains('d-none'));
            visibles.forEach((el, i) => el.classList.toggle('ui-pag-oculto', i >= limite));
            const mostrados = Math.min(limite, visibles.length);
            contador.textContent = visibles.length > porPagina ? `Mostrando ${mostrados} de ${visibles.length} ${etiqueta}` : '';
            boton.classList.toggle('d-none', visibles.length <= limite);
        }
        boton.addEventListener('click', () => { limite += porPagina; refrescar(); });
        refrescar();
        return { refrescar, reiniciar() { limite = porPagina; refrescar(); } };
    }

    document.addEventListener('DOMContentLoaded', () => {
        mejorarAccesibilidad();
        const pill = document.getElementById('saldoUsuarioNavbar');
        if (pill && pill.dataset.monto === undefined) pill.dataset.monto = pill.textContent.replace(/[^\d]/g, '');
    });

    window.UI = { escapar, confirmar, refrescarSaldo, alerta, mostrarAlertaEn, mejorarAccesibilidad, paginador };
})();
