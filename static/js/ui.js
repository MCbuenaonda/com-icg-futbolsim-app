/*
 * Utilidades de interfaz compartidas por todas las páginas (cargado en templates/base.html).
 *
 *   UI.escapar(texto)                 -> texto seguro para meter en innerHTML (evita inyección de HTML)
 *   UI.confirmar({titulo, mensaje, textoConfirmar, peligro}) -> Promise<boolean>, modal propio
 *                                        (reemplaza al confirm() nativo del navegador)
 *   UI.refrescarSaldo()               -> vuelve a pedir el saldo y actualiza la pill del navbar y la
 *                                        insignia de nivel (avisa "+N XP" con un toast si sumó XP)
 *   UI.toast(mensaje, {icono, tipo, enlace, duracion}) -> aviso flotante abajo a la derecha
 *   UI.alerta(contenedor, mensaje, tipo) -> alerta Bootstrap descartable dentro de 'contenedor'
 *   UI.bandera(emoji, {tipo, id, clase}) -> HTML de la imagen del país (bandera/plana/escudo/icono/jersey)
 *                                        o el emoji escapado si no hay imagen; mismo criterio que
 *                                        el macro 'bandera' de templates/partials/macros.html
 *   UI.urlImagenPais(id, tipo)        -> URL de la imagen en el bucket (null si el país no se conoce)
 *   UI.jersey(paisId, numero)         -> jersey de la selección con el dorsal encima (.jersey-dorsal)
 *   UI.avatar(jugadorId, paisId, tam) -> avatar ilustrado del jugador sobre su bandera (.avatar-jugador),
 *                                        mismo criterio que el macro 'avatar' de partials/macros.html
 *
 *   UI.cargando(promesa)            -> muestra la barra de carga mientras la promesa no termina
 *
 * Además, al cargar: toda tarjeta clicable con role="button" se vuelve accesible por teclado
 * (tabindex + Enter/Espacio), y los botones de solo ícono heredan su 'title' como aria-label.
 */
(function () {
    function escapar(texto) {
        return String(texto ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    // ---------- Imágenes de selección ----------
    // Vienen del bucket público (window.PAISES_IMG, lo arma base.html desde
    // services/imagenes_pais_service.py): <base>/<tipo>/<nombre del país>.png. Si el país no se
    // conoce, o la imagen no carga, se muestra el emoji.
    function urlImagenPais(id, tipo = 'bandera') {
        const datos = window.PAISES_IMG || {};
        const nombre = (datos.porId || {})[String(id)];
        if (!nombre || !datos.base) return null;
        // Misma regla que services/imagenes_pais_service.url_imagen_pais: carpeta por tipo + versión (caché de 7 días)
        const carpeta = (datos.carpetas || {})[tipo] || tipo;
        const version = (datos.versiones || {})[tipo];
        return `${datos.base}/${carpeta}/${encodeURIComponent(nombre)}.png${version ? '?v=' + version : ''}`;
    }
    // Si la imagen falla, la reemplaza por el emoji guardado en data-emoji
    const ON_ERROR_EMOJI = "this.replaceWith(document.createTextNode(this.dataset.emoji || ''))";
    function bandera(emoji, { tipo = 'bandera', id = null, clase = '' } = {}) {
        const paisId = id ?? ((window.PAISES_IMG || {}).porBandera || {})[emoji];
        const url = paisId != null ? urlImagenPais(paisId, tipo) : null;
        if (!url) return escapar(emoji || '');
        return `<img src="${url}" class="img-pais img-pais--${tipo} ${escapar(clase)}" alt="" data-emoji="${escapar(emoji || '')}" loading="lazy" decoding="async" onerror="${ON_ERROR_EMOJI}">`;
    }

    function jersey(paisId, numero, clase = '') {
        const url = paisId != null ? urlImagenPais(paisId, 'jersey') : null;
        const img = url ? `<img src="${url}" alt="" loading="lazy" decoding="async" onerror="this.parentNode.classList.add('jersey-dorsal--sin-imagen')">` : '';
        return `<span class="jersey-dorsal ${url ? '' : 'jersey-dorsal--sin-imagen'} ${escapar(clase)}">${img}<span>${escapar(numero ?? '')}</span></span>`;
    }

    // URL del avatar ilustrado (bucket jugadores/<id>.svg) con su versión, igual que imagenes_pais_service.url_avatar
    function urlAvatar(jugadorId) {
        const datos = window.PAISES_IMG || {};
        const v = (datos.versiones || {}).avatar;
        return datos.base && jugadorId != null ? `${datos.base}/jugadores/${encodeURIComponent(jugadorId)}.svg${v ? '?v=' + v : ''}` : null;
    }

    function avatar(jugadorId, paisId = null, tam = '') {
        const base = (window.PAISES_IMG || {}).base;
        const bandera = paisId != null ? urlImagenPais(paisId, 'plana') : null;   // fondo: la versión plana a sangre
        const fondo = bandera ? ` style="--bandera-url: url('${bandera}')"` : '';
        const img = base && jugadorId != null
            ? `<img src="${urlAvatar(jugadorId)}" alt="" loading="lazy" decoding="async" onerror="this.remove()">`
            : '<i class="bi bi-person-fill"></i>';
        return `<span class="avatar-jugador ${tam ? 'avatar-jugador--' + escapar(tam) : ''}"${fondo}>${img}</span>`;
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

    function confirmar({ titulo = '¿Confirmas?', mensaje = '', textoConfirmar = 'Confirmar', peligro = false } = {}) {
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

    // ---------- Toast (aviso flotante) ----------
    function toast(mensaje, { icono = 'bi-stars', tipo = 'xp', enlace = null, duracion = 4000 } = {}) {
        let pila = document.getElementById('uiToasts');
        if (!pila) {
            pila = document.createElement('div');
            pila.id = 'uiToasts';
            pila.className = 'ui-toasts';
            pila.setAttribute('aria-live', 'polite');
            document.body.appendChild(pila);
        }
        const nodo = document.createElement(enlace ? 'a' : 'div');
        nodo.className = `ui-toast ui-toast--${escapar(tipo)}`;
        if (enlace) nodo.href = enlace;
        nodo.innerHTML = `<i class="bi ${escapar(icono)}"></i><span>${escapar(mensaje)}</span>`;
        pila.appendChild(nodo);
        setTimeout(() => { nodo.classList.add('ui-toast--sale'); setTimeout(() => nodo.remove(), 400); }, duracion);
    }

    // Insignia de nivel del navbar (templates/base.html): aro de progreso, número y globito de pendientes
    function actualizarInsigniaNivel({ xp, nivel, titulo, pct, pendientes }) {
        const insignia = document.getElementById('nivelNavbar');
        if (!insignia || xp === undefined) return;
        const xpAnterior = Number(insignia.dataset.xp);
        const nivelAnterior = Number(insignia.dataset.nivel);
        insignia.dataset.xp = xp;
        insignia.dataset.nivel = nivel;
        insignia.style.setProperty('--pct', pct);
        insignia.querySelector('.nivel-insignia__numero').textContent = nivel;
        insignia.title = `Nivel ${nivel} · ${titulo} · ${Number(xp).toLocaleString('en-US')} XP`;
        const globo = insignia.querySelector('.nivel-insignia__globo');
        globo.textContent = pendientes;
        globo.classList.toggle('d-none', !pendientes);
        if (!Number.isNaN(xpAnterior) && xp > xpAnterior) toast(`+${xp - xpAnterior} XP`, { icono: 'bi-stars', enlace: '/niveles/' });
        if (!Number.isNaN(nivelAnterior) && nivel > nivelAnterior) {
            toast(`¡Subiste a nivel ${nivel} · ${titulo}!${pendientes ? ' Tienes una recompensa esperando' : ''}`,
                  { icono: 'bi-trophy-fill', tipo: 'nivel', enlace: '/niveles/', duracion: 7000 });
        }
    }

    // ---------- Saldo del navbar ----------
    async function refrescarSaldo() {
        const pill = document.getElementById('saldoUsuarioNavbar');
        if (!pill) return;
        try {
            const resp = await fetch('/cuenta/saldo', { headers: { accept: 'application/json' } });
            if (!resp.ok) return;
            const datos = await resp.json();
            const { monto } = datos;
            actualizarInsigniaNivel(datos);
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

    // ---------------------------------------------------------------------------------------------
    // Indicadores de carga (para que una espera no parezca un cuelgue):
    //  - Barra de progreso arriba al navegar (clic en un link interno o envío de un formulario) y en
    //    cada fetch que tarda más de RETARDO_FETCH ms.
    //  - Si la navegación tarda más de RETARDO_AVISO ms, un aviso con una pelota girando y el nombre de
    //    lo que se está abriendo.
    //  Los polls periódicos (en vivo, saldo) no la encienden: ver SIN_CARGADOR. UI.cargando(promesa)
    //  la muestra mientras dure cualquier otra espera.
    // ---------------------------------------------------------------------------------------------
    const RETARDO_FETCH = 400, RETARDO_AVISO = 700;
    const SIN_CARGADOR = [/\/matches\/live/, /\/matches\/pulso/, /\/live-game\//, /\/cuenta\/saldo/, /\/niveles\/visto/, /\/seguimiento$/];
    let barra = null, aviso = null, activos = 0, timerAviso = null;

    function asegurarNodos() {
        if (barra) return;
        barra = document.createElement('div');
        barra.className = 'ui-barra-carga';
        barra.setAttribute('aria-hidden', 'true');
        aviso = document.createElement('div');
        aviso.className = 'ui-aviso-carga';
        aviso.setAttribute('role', 'status');
        aviso.innerHTML = '<span class="ui-aviso-carga__pelota"><i class="bi bi-dribbble"></i></span><span class="ui-aviso-carga__texto">Cargando…</span>';
        document.body.append(barra, aviso);
    }
    function iniciarBarra() {
        asegurarNodos();
        barra.classList.remove('ui-barra-carga--fin');
        void barra.offsetWidth;
        barra.classList.add('ui-barra-carga--activa');
    }
    function terminarBarra() {
        if (!barra || activos > 0) return;
        barra.classList.add('ui-barra-carga--fin');
        setTimeout(() => { if (activos === 0) barra.classList.remove('ui-barra-carga--activa', 'ui-barra-carga--fin'); }, 350);
    }
    let timerSeguridad = null;
    function navegando(texto) {
        iniciarBarra();
        clearTimeout(timerAviso);
        clearTimeout(timerSeguridad);
        // Si la navegación se cancela (descarga, 204, error de red) la página sigue aquí: no dejar la barra colgada
        timerSeguridad = setTimeout(limpiarNavegacion, 20000);
        timerAviso = setTimeout(() => {
            aviso.querySelector('.ui-aviso-carga__texto').textContent = texto ? `Abriendo ${texto}…` : 'Cargando…';
            aviso.classList.add('ui-aviso-carga--visible');
        }, RETARDO_AVISO);
    }
    function limpiarNavegacion() {
        clearTimeout(timerAviso);
        clearTimeout(timerSeguridad);
        if (aviso) aviso.classList.remove('ui-aviso-carga--visible');
        activos = 0;
        terminarBarra();
    }
    async function cargando(promesa) {
        activos++; iniciarBarra();
        try { return await promesa; } finally { activos = Math.max(0, activos - 1); terminarBarra(); }
    }

    document.addEventListener('click', e => {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        const a = e.target.closest('a[href]');
        if (!a || a.target === '_blank' || a.hasAttribute('download') || a.dataset.bsToggle || a.dataset.sinCargador !== undefined) return;
        const url = new URL(a.href, location.href);
        if (url.origin !== location.origin || url.protocol.startsWith('javascript')) return;
        if (url.pathname === location.pathname && url.search === location.search && url.hash) return;   // ancla en la misma página
        const texto = (a.getAttribute('aria-label') || a.textContent || '').replace(/\s+/g, ' ').trim();
        navegando(texto.length > 0 && texto.length <= 40 ? texto : '');
    });
    document.addEventListener('submit', e => {
        if (e.defaultPrevented || e.target.dataset.sinCargador !== undefined) return;
        navegando('');
    });
    window.addEventListener('pageshow', limpiarNavegacion);   // volver con "atrás" (bfcache) no deja la barra colgada

    const fetchOriginal = window.fetch.bind(window);
    window.fetch = function (recurso, opciones) {
        const url = typeof recurso === 'string' ? recurso : (recurso && recurso.url) || '';
        if (SIN_CARGADOR.some(rx => rx.test(url)) || (opciones && opciones.keepalive)) return fetchOriginal(recurso, opciones);
        let contado = false;
        const t = setTimeout(() => { contado = true; activos++; iniciarBarra(); }, RETARDO_FETCH);
        return fetchOriginal(recurso, opciones).finally(() => {
            clearTimeout(t);
            if (contado) { activos = Math.max(0, activos - 1); terminarBarra(); }
        });
    };

    window.UI = { escapar, bandera, urlImagenPais, jersey, avatar, confirmar, refrescarSaldo, toast, alerta, mostrarAlertaEn, mejorarAccesibilidad, paginador, cargando, urlAvatar };
})();
