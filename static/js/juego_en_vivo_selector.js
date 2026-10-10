/*
 * Selector del Juego en Vivo (elegir país + riesgo inicial), compartido por /juegos (modal) y
 * por el panel inactivo de /en-vivo/ (próximo partido). Trabaja contra la API /live-game
 * (routes/juego_en_vivo_route.py); los puntos y el cobro los calcula siempre el backend.
 *
 * Uso: JuegoEnVivoSelector.render(contenedor, datosCuotas, { onCambio(datosNuevos) })
 *   'datosCuotas' es la respuesta de GET /live-game/matches/{id}/odds (o /live-game/next).
 */
(function () {
    const API = '/live-game';
    const CATEGORIAS = {
        favorito: { texto: 'Favorito', clase: 'bg-success' },
        equilibrado: { texto: 'Equilibrado', clase: 'bg-secondary' },
        underdog: { texto: 'Debil', clase: 'jev-badge-underdog' },
    };

    function escapar(texto) {
        return String(texto ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function formatearPuntos(n) {
        return Number(n || 0).toLocaleString('es-AR');
    }

    async function pedir(metodo, url, cuerpo) {
        const resp = await fetch(url, {
            method: metodo,
            headers: cuerpo ? { 'Content-Type': 'application/json' } : undefined,
            body: cuerpo ? JSON.stringify(cuerpo) : undefined,
        });
        let datos = null;
        try { datos = await resp.json(); } catch (e) { /* sin cuerpo */ }
        if (!resp.ok) throw new Error((datos && datos.detail) || 'No se pudo completar la operación.');
        return datos;
    }

    // x2 usa un naranja propio (.jev-btn-x2): el tema del sitio pinta 'warning' de verde
    function claseBotonRiesgo(multiplicador, activo) {
        if (multiplicador >= 3) return activo ? 'btn-danger' : 'btn-outline-danger';
        if (multiplicador >= 2) return activo ? 'jev-btn-x2 jev-btn-x2--activo' : 'jev-btn-x2';
        return activo ? 'btn-success' : 'btn-outline-success';
    }

    function claseAvisoRiesgo(multiplicador) {
        if (multiplicador >= 3) return 'text-danger';
        if (multiplicador >= 2) return 'jev-texto-x2';
        return 'text-muted';
    }

    function textoAvisoRiesgo(multiplicador) {
        if (multiplicador >= 3) return '⚠️ Extremo: cada evento vale el triple, para bien y para mal. Es fácil quedarse en 0.';
        if (multiplicador >= 2) return '⚠️ Arriesgado: cada evento vale el doble, para bien y para mal.';
        return 'Podrás cambiar el riesgo durante el partido (una vez por minuto, o después de un gol).';
    }

    function render(contenedor, datos, opciones = {}) {
        const sesion = datos.sesion;
        const estado = {
            pais: sesion ? sesion.pais_id : null,
            riesgo: sesion ? sesion.multiplicador_elegido : 1,
            ocupado: false,
        };

        function dibujar(mensaje, esError) {
            const equipos = [datos.local, datos.visitante].map(eq => {
                const cat = CATEGORIAS[eq.categoria] || CATEGORIAS.equilibrado;
                const activo = estado.pais === eq.pais_id;
                return `
                    <button type="button" class="jev-equipo ${activo ? 'jev-equipo--activo' : ''}" data-pais="${eq.pais_id}" ${datos.disponible ? '' : 'disabled'}>
                        <div class="jev-equipo__bandera">${escapar(eq.bandera || '🏳️')}</div>
                        <div class="jev-equipo__nombre" title="${escapar(eq.nombre)}">${escapar(eq.nombre)}</div>
                        <div class="small text-muted">${eq.probabilidad_pct}% de ganar</div>
                        <span class="badge ${cat.clase} my-1">${cat.texto}</span>
                        <div class="jev-equipo__cuota">${formatearPuntos(eq.cuota)} <span class="small fw-normal">pts</span></div>
                    </button>`;
            }).join('');

            const riesgos = datos.niveles_riesgo.map(n => {
                const activo = estado.riesgo === n.multiplicador;
                return `<button type="button" class="btn btn-sm jev-riesgo ${claseBotonRiesgo(n.multiplicador, activo)}" data-riesgo="${n.multiplicador}" ${datos.disponible ? '' : 'disabled'}>
                            x${n.multiplicador}<small>${escapar(n.nombre)}</small></button>`;
            }).join('');

            const elegido = sesion
                ? `<div class="alert alert-success py-2 small mb-3">🎮 Vas con <strong>${escapar(sesion.pais_nombre)}</strong> ·
                       ${formatearPuntos(sesion.puntos_iniciales)} pts · riesgo x${sesion.multiplicador_elegido}</div>`
                : '';
            const noDisponible = datos.disponible ? '' : '<div class="alert alert-secondary py-2 small mb-3">Este partido ya empezó o ya se jugó: solo puedes verlo como espectador.</div>';
            const cambiaPais = sesion && estado.pais !== sesion.pais_id;
            const cambiaRiesgo = sesion && estado.riesgo !== sesion.multiplicador_elegido;
            let textoConfirmar = `Jugar por ${formatearPuntos(datos.entrada)} de saldo`;
            if (sesion) textoConfirmar = cambiaPais ? 'Cambiar de país' : 'Guardar riesgo';
            const puedeConfirmar = datos.disponible && !estado.ocupado && estado.pais != null && (!sesion || cambiaPais || cambiaRiesgo);

            contenedor.innerHTML = `
                ${noDisponible}${elegido}
                <p class="small text-muted mb-2">
                    Paga la entrada de <strong>${formatearPuntos(datos.entrada)}</strong> de tu saldo
                    (tienes <strong>${formatearPuntos(datos.monto_usuario)}</strong>) y recibe una cuota de puntos
                    según el favoritismo. Cada evento del partido suma o resta según tu país; al final tus puntos vuelven a tu saldo.
                </p>
                <div class="jev-equipos mb-3">${equipos}</div>
                <div class="fw-semibold small mb-1">Riesgo inicial</div>
                <div class="jev-riesgos mb-1">${riesgos}</div>
                <div class="jev-aviso-riesgo mb-3 ${claseAvisoRiesgo(estado.riesgo)}">${textoAvisoRiesgo(estado.riesgo)}</div>
                ${mensaje ? `<div class="alert ${esError ? 'alert-danger' : 'alert-success'} py-2 small">${escapar(mensaje)}</div>` : ''}
                <div class="d-flex gap-2 flex-wrap justify-content-end">
                    ${sesion && datos.disponible ? `<button type="button" class="btn btn-sm btn-outline-danger" data-accion="cancelar" ${estado.ocupado ? 'disabled' : ''}>Cancelar elección (reembolso)</button>` : ''}
                    <button type="button" class="btn btn-sm btn-success fw-bold" data-accion="confirmar" ${puedeConfirmar ? '' : 'disabled'}>
                        ${estado.ocupado ? '<span class="spinner-border spinner-border-sm me-1"></span>' : '🎮 '}${textoConfirmar}
                    </button>
                </div>`;

            contenedor.querySelectorAll('[data-pais]').forEach(b => b.addEventListener('click', () => {
                estado.pais = Number(b.dataset.pais); dibujar();
            }));
            contenedor.querySelectorAll('[data-riesgo]').forEach(b => b.addEventListener('click', () => {
                estado.riesgo = Number(b.dataset.riesgo); dibujar();
            }));
            const btnConfirmar = contenedor.querySelector('[data-accion="confirmar"]');
            if (btnConfirmar) btnConfirmar.addEventListener('click', confirmar);
            const btnCancelar = contenedor.querySelector('[data-accion="cancelar"]');
            if (btnCancelar) btnCancelar.addEventListener('click', cancelar);
        }

        async function ejecutar(accion, mensajeOk) {
            estado.ocupado = true; dibujar();
            try {
                const nuevos = await accion();
                if (opciones.onCambio) opciones.onCambio(nuevos);
                render(contenedor, nuevos, opciones);
                // Mensaje de éxito sobre el render nuevo
                const alerta = document.createElement('div');
                alerta.className = 'alert alert-success py-2 small mt-2 mb-0';
                alerta.textContent = mensajeOk;
                contenedor.appendChild(alerta);
            } catch (e) {
                estado.ocupado = false; dibujar(e.message, true);
            }
        }

        function confirmar() {
            const juegoId = datos.juego_id;
            ejecutar(async () => {
                if (sesion && estado.pais === sesion.pais_id) {
                    await pedir('PUT', `${API}/sessions/${juegoId}/risk`, { multiplicador: estado.riesgo });
                    return pedir('GET', `${API}/matches/${juegoId}/odds`);
                }
                if (sesion) await pedir('DELETE', `${API}/sessions/${juegoId}`);
                return pedir('POST', `${API}/sessions`, { juego_id: juegoId, pais_id: estado.pais, multiplicador: estado.riesgo });
            }, '¡Listo! Tu elección quedó guardada.');
        }

        function cancelar() {
            ejecutar(() => pedir('DELETE', `${API}/sessions/${datos.juego_id}`), 'Elección cancelada: se te reembolsó la entrada.');
        }

        dibujar();
    }

    window.JuegoEnVivoSelector = { render, pedir, escapar, formatearPuntos, claseBotonRiesgo };
})();
