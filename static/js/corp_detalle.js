/*
 * Perfil de tu corporativo (templates/corporativo_perfil.html):
 *   - evento 'corp:promos' (lo emite marcas.js al promover): actualiza el contador «Promociones a marcas» (#cupoPromos)
 *     y, si se agotaron, bloquea todos los botones «Promover» de la cartera.
 *   - [data-detalle-contrato] (la franja de datos de cada representado): abre un modal con el detalle del contrato,
 *     lo que puede hacer ahora (promover, gira, renovar) y cómo subir su satisfacción (window.CORP_SATISFACCION,
 *     las mismas reglas que aplica corporativo_ciclo_service).
 */
(() => {
    const fmt = n => Math.round(Number(n || 0)).toLocaleString('en-US');
    const esc = s => UI.escapar(String(s ?? ''));
    const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
    const reglas = window.CORP_SATISFACCION || null;
    const CORTO = { partido: 'jugar su próximo partido', victoria: 'una victoria', gira: 'una gira', renovar: 'renovarlo' };
    const cupo = document.getElementById('cupoPromos');
    let promos = cupo ? { restantes: Number(cupo.dataset.restantes), maximo: Number(cupo.dataset.maximo), faltan: Number(cupo.dataset.faltan) } : null;

    // --- Contador de promociones y bloqueo de «Promover» ---
    const textoAgotadas = p => `Ya usaste tus promociones de esta ronda: se renuevan en ${plural(p.faltan, 'partido', 'partidos')}`;

    function pintarPromos(p) {
        promos = p;
        if (cupo) {
            cupo.dataset.restantes = p.restantes;
            cupo.classList.toggle('corp-cupo--agotado', p.restantes <= 0);
            const num = cupo.querySelector('[data-promos-restantes]');
            if (num) {
                num.textContent = p.restantes;
                num.classList.remove('corp-cupo__cambio'); void num.offsetWidth; num.classList.add('corp-cupo__cambio');
            }
            const puntos = cupo.querySelector('[data-promos-puntos]');
            if (puntos) puntos.innerHTML = Array.from({ length: p.maximo }, (_, i) => `<i class="${i < p.restantes ? 'is-libre' : ''}"></i>`).join('');
            const nota = cupo.querySelector('[data-promos-nota]');
            if (nota) nota.textContent = `${p.restantes > 0 ? 'En esta ronda' : 'Agotadas'} · se renuevan en ${plural(p.faltan, 'partido', 'partidos')}`;
        }
        if (p.restantes <= 0) {
            document.querySelectorAll('[data-promover]').forEach(b => { b.disabled = true; b.title = textoAgotadas(p); });
        }
    }
    document.addEventListener('corp:promos', ev => pintarPromos(ev.detail));

    // --- Modal de detalle ---
    function modal() {
        let el = document.getElementById('modalDetalleContrato');
        if (el) return el;
        el = document.createElement('div');
        el.className = 'modal fade'; el.id = 'modalDetalleContrato'; el.tabIndex = -1;
        el.setAttribute('aria-labelledby', 'detContratoTitulo');
        el.innerHTML = '<div class="modal-dialog modal-dialog-centered modal-dialog-scrollable modal-lg"><div class="modal-content bg-dark border-secondary" id="detContratoCaja"></div></div>';
        document.body.appendChild(el);
        return el;
    }

    const estadoSatisfaccion = s => s >= 60 ? { clase: 'bien', texto: 'Contento' }
        : s >= 35 ? { clase: 'medio', texto: 'Conforme' }
        : s >= 30 ? { clase: 'mal', texto: 'Descontento: las marcas lo notan' }
        : { clase: 'mal', texto: 'Muy descontento: pide salir' };

    // Para cada regla que la sube: ¿se puede aprovechar ahora? (texto del estado y si está disponible)
    function estadoRegla(r, d) {
        const jg = d.juego || {};
        if (r.clave === 'partido' || r.clave === 'victoria') {
            if (jg.estado === 'programado') {
                const cuando = jg.faltan != null ? `en ${plural(jg.faltan, 'partido', 'partidos')} del torneo` : 'pronto';
                return { ok: true, texto: `Próximo partido ${cuando}${jg.rival ? ` contra ${jg.rival}` : ''}` };
            }
            if (jg.estado === 'eliminada') return { ok: false, texto: 'Su selección está eliminada: ya no suma por aquí' };
            return { ok: false, texto: 'Su selección no tiene partido programado todavía' };
        }
        if (r.clave === 'gira') {
            if (d.de_gira) return { ok: true, texto: 'Está de gira ahora: ya la sumó' };
            if (d.gira_ok) return { ok: true, texto: 'Disponible ahora', accion: 'gira' };
            return { ok: false, texto: d.gira_motivo || 'No disponible por ahora' };
        }
        if (r.clave === 'renovar') {
            if (d.puede_renovar) return { ok: true, texto: `Disponible: cuesta ${fmt(d.costo_renovar)}`, accion: 'renovar' };
            const espera = Math.max(1, d.ciclos_restantes - 3);
            return { ok: false, texto: `Podrás renovarlo en ${plural(espera, 'ciclo', 'ciclos')}` };
        }
        if (r.clave === 'tier_a') return r.activo ? { ok: true, texto: 'Tu corporativo es Tier A: suma solo' } : { ok: false, texto: `Tu corporativo es Tier ${reglas.tier}` };
        return { ok: false, texto: '' };
    }

    // Para cada regla que la baja: ¿le está pasando?
    function alertaRegla(r, d) {
        const jg = d.juego || {};
        if (r.clave === 'sin_jugar') {
            if (d.ciclos_sin_jugar > 0) return `Lleva ${plural(d.ciclos_sin_jugar, 'ciclo', 'ciclos')} sin jugar`;
            if (jg.estado === 'eliminada') return 'Su selección está eliminada: le pasará cada ciclo';
        }
        return '';
    }

    function bloqueSatisfaccion(d) {
        if (!reglas) return '';
        const s = Math.round(d.satisfaccion || 0);
        const est = estadoSatisfaccion(s);
        const u = reglas.umbrales;
        const sube = reglas.sube.filter(r => !r.solo || r.solo === d.tipo).map(r => {
            const e = estadoRegla(r, d);
            return { ...r, e };
        });
        // proyección: lo que suma con lo que hoy está a su alcance (un partido y las acciones disponibles)
        const alcance = sube.filter(r => r.e.ok && r.clave !== 'tier_a' && !(r.clave === 'gira' && d.de_gira));
        const proyectada = Math.min(100, s + alcance.reduce((a, r) => a + r.valor, 0));
        const filasSube = sube.map(r => `
            <li class="cd-regla ${r.e.ok ? 'cd-regla--ok' : ''}">
              <span class="cd-delta cd-delta--sube">+${r.valor}</span>
              <div class="min-w-0 flex-grow-1"><div class="text-white">${esc(r.texto)}</div><small class="${r.e.ok ? 'text-success' : 'text-muted'}">${r.e.ok ? '<i class="bi bi-check-circle-fill me-1"></i>' : ''}${esc(r.e.texto)}</small></div>
              ${r.e.accion ? `<button type="button" class="btn btn-sm btn-outline-${r.e.accion === 'gira' ? 'info' : 'success'} rounded-pill flex-shrink-0" data-detalle-accion="${r.e.accion}">${r.e.accion === 'gira' ? '<i class="bi bi-airplane"></i> Gira' : '<i class="bi bi-arrow-repeat"></i> Renovar'}</button>` : ''}
            </li>`).join('');
        const filasBaja = reglas.baja.map(r => {
            const alerta = alertaRegla(r, d);
            return `<li class="cd-regla ${alerta ? 'cd-regla--alerta' : ''}"><span class="cd-delta cd-delta--baja">${r.valor}</span>
              <div class="min-w-0"><div class="text-white">${esc(r.texto)}</div>${alerta ? `<small class="text-danger"><i class="bi bi-exclamation-triangle-fill me-1"></i>${esc(alerta)}</small>` : ''}</div></li>`;
        }).join('');
        return `
          <section class="cd-seccion">
            <h6 class="cd-titulo d-flex align-items-center gap-2"><span><i class="bi bi-emoji-smile-fill me-1"></i>Satisfacción</span>
              <button type="button" class="cd-info" data-cd-reglas aria-expanded="false" aria-controls="cdReglas"
                      title="Ver cómo sube y qué la baja"><i class="bi bi-info-circle-fill"></i><span>¿Cómo sube?</span></button></h6>
            <div class="cd-satis">
              <div class="cd-satis__valor cd-satis__valor--${est.clase}">${s}<small>/100</small></div>
              <div class="flex-grow-1 min-w-0">
                <div class="cd-satis__estado cd-satis__estado--${est.clase}">${esc(est.texto)}</div>
                <div class="cd-barra" role="img" aria-label="Satisfacción ${s} de 100">
                  <span class="cd-barra__relleno cd-barra__relleno--${est.clase}" style="width:${s}%"></span>
                  ${proyectada > s ? `<span class="cd-barra__proyeccion" style="left:${s}%;width:${proyectada - s}%" title="Hasta ${proyectada} con lo que tienes a tu alcance"></span>` : ''}
                  <i class="cd-barra__marca" style="left:${u.pide_salir}%" title="Debajo de ${u.pide_salir} pide salir"></i>
                  <i class="cd-barra__marca" style="left:${u.marcas}%" title="Debajo de ${u.marcas} las marcas lo ven descontento"></i>
                  <i class="cd-barra__marca cd-barra__marca--bien" style="left:${u.renovacion}%" title="Desde ${u.renovacion} renovar es más barato"></i>
                </div>
                <div class="cd-barra__leyenda"><span>${u.pide_salir} pide salir</span><span>${u.marcas} marcas en alerta</span><span>${u.renovacion}+ renovación más barata</span></div>
              </div>
            </div>
            ${proyectada > s ? `<div class="cd-proyeccion"><i class="bi bi-graph-up-arrow me-1"></i>Con lo que está a tu alcance puede llegar a <strong>${proyectada}</strong> (${alcance.map(r => `+${r.valor} por ${esc(CORTO[r.clave] || r.texto.toLowerCase())}`).join(', ')}).</div>` : ''}
            <div class="cd-reglas-bloque" id="cdReglas" hidden>
            <div class="row g-3 mt-1">
              <div class="col-md-7"><div class="cd-subtitulo text-success">Cómo subirla</div><ul class="cd-reglas">${filasSube}</ul></div>
              <div class="col-md-5"><div class="cd-subtitulo text-danger">Qué la baja</div><ul class="cd-reglas">${filasBaja}</ul></div>
            </div>
            <small class="text-muted d-block mt-2">Con ${u.renovacion} o más, renovarlo cuesta menos (hasta ${u.descuento_renovacion}% menos con 100). Debajo de ${u.marcas} las marcas pueden cortar su patrocinio y debajo de ${u.pide_salir} pide salir.</small>
            </div>
          </section>`;
    }

    function bloquePatrocinadores(d) {
        const lista = d.patrocinadores || [];
        const filas = lista.map(m => `
            <li class="cd-marca" style="--marca:${esc(m.color || '#64748b')}">
              <img src="${esc(m.logo)}" alt="" class="cd-marca__logo" onerror="this.style.visibility='hidden'">
              <div class="min-w-0 flex-grow-1">
                <div class="text-white fw-semibold text-truncate">${esc(m.nombre)}</div>
                <small class="text-muted"><i class="bi ${esc(m.rubro_icono || 'bi-tag')} me-1"></i>${esc(m.rubro_nombre || '')}${m.alcance_nombre ? ` · ${esc(m.alcance_nombre)}` : ''}</small>
                ${m.aviso ? '<small class="d-block text-danger"><i class="bi bi-exclamation-triangle-fill me-1"></i>Está revisando el patrocinio</small>' : ''}
              </div>
              <div class="text-end flex-shrink-0">
                <strong class="text-info">+${fmt(m.pago_ciclo)}</strong><small class="d-block text-muted">por ciclo · hasta el ${m.hasta_ciclo}</small>
              </div>
            </li>`).join('');
        const vacio = `<div class="cd-vacio"><i class="bi bi-badge-ad"></i>Todavía no tiene patrocinadores. Promuévelo con una marca que encaje con su perfil (máximo 3, una por rubro).</div>`;
        return `<section class="cd-seccion"><h6 class="cd-titulo"><i class="bi bi-badge-ad-fill me-1"></i>Patrocinadores${lista.length ? ` <span class="cd-cuenta">${lista.length}/3</span>` : ''}</h6>
            ${lista.length ? `<ul class="cd-lista">${filas}</ul>` : vacio}</section>`;
    }

    function bloqueTelevision(d) {
        if (d.tipo !== 'jugador') return '';
        const lista = d.invitaciones_tv || [];
        const filas = lista.map(i => {
            const hecha = i.estado === 'REALIZADA';
            const partido = i.local && i.visita
                ? `${UI.bandera(i.bandera_local || '')} ${esc(i.local)} <span class="text-muted">vs</span> ${UI.bandera(i.bandera_visita || '')} ${esc(i.visita)}`
                : 'Partido por confirmar';
            const enlace = hecha ? `/juegos/${encodeURIComponent(i.juego_id)}` : `/scouter/${encodeURIComponent(i.juego_id)}`;
            return `
            <li class="cd-tv ${hecha ? '' : 'cd-tv--proxima'}">
              <span class="cd-tv__logo"><img src="${esc(i.logo)}" alt="${esc(i.cadena)}" onerror="this.style.visibility='hidden'"></span>
              <div class="min-w-0 flex-grow-1">
                <div class="text-white fw-semibold text-truncate">${esc(i.cadena)}${i.papel ? ` <small class="text-muted fw-normal">· ${esc(i.papel)}</small>` : ''}</div>
                <a href="${enlace}" class="cd-tv__partido">${partido}</a>
                <small class="d-block text-muted">${esc(i.fecha || '')}${i.hora ? ` · ${esc(i.hora)}` : ''}</small>
              </div>
              <div class="text-end flex-shrink-0">
                ${hecha
                    ? `<span class="cd-tv__estado cd-tv__estado--hecha"><i class="bi bi-mic-fill"></i> Comentó</span>
                       <small class="d-block text-info">+${fmt(i.pago)}</small>${i.aficionados ? `<small class="d-block text-muted">+${fmt(i.aficionados)} aficionados</small>` : ''}`
                    : '<span class="cd-tv__estado"><i class="bi bi-calendar-event"></i> Invitado</span><small class="d-block text-muted">cobra al jugarse</small>'}
              </div>
            </li>`;
        }).join('');
        const vacio = `<div class="cd-vacio"><i class="bi bi-broadcast"></i>Todavía no lo han invitado. Las cadenas que transmiten un partido invitan a comentarlo a un representado cuya selección no juega en el ciclo (sin gira ni renovación pendiente).</div>`;
        return `<section class="cd-seccion"><h6 class="cd-titulo"><i class="bi bi-person-video3 me-1"></i>Invitado a comentar en TV${lista.length ? ` <span class="cd-cuenta">${lista.length}</span>` : ''}</h6>
            ${lista.length ? `<ul class="cd-lista">${filas}</ul>` : vacio}</section>`;
    }

    function bloqueNumeros(d) {
        const neto = d.neto || 0;
        const dato = (titulo, valor, clase = '') => `<div class="cd-dato"><span>${titulo}</span><strong class="${clase}">${valor}</strong></div>`;
        return `
          <section class="cd-seccion">
            <h6 class="cd-titulo"><i class="bi bi-cash-coin me-1"></i>Números del contrato</h6>
            <div class="cd-datos">
              ${dato('Neto acumulado', (neto > 0 ? '+' : '') + fmt(neto), neto > 0 ? 'text-success' : (neto < 0 ? 'text-danger' : ''))}
              ${dato('Ingresos', '+' + fmt(d.renta_total), 'text-success')}
              ${dato('Honorarios pagados', fmt(d.honorarios_total))}
              ${dato('Patrocinio por ciclo', '+' + fmt(d.patrocinio), 'text-info')}
              ${dato('Honorario por ciclo', fmt(d.honorario))}
              ${d.tipo === 'jugador' ? dato('Partidos jugados', fmt(d.partidos)) : ''}
              ${dato('Contrato', `hasta el ciclo ${d.hasta_ciclo} · ${plural(d.ciclos_restantes, 'ciclo', 'ciclos')}`)}
              ${dato('Rescindir costaría', fmt(d.costo_rescindir))}
            </div>
          </section>`;
    }

    function bloqueAcciones(d) {
        const p = promos;
        const nMarcas = (d.marcas || []).length;
        let promo;
        if (nMarcas >= 3) promo = { ok: false, texto: 'Ya tiene 3 marcas: es el máximo por representado' };
        else if (p && p.restantes <= 0) promo = { ok: false, texto: textoAgotadas(p) };
        else promo = { ok: true, texto: p ? `Te ${p.restantes === 1 ? 'queda' : 'quedan'} ${plural(p.restantes, 'promoción', 'promociones')} en esta ronda · la marca responde en la siguiente` : 'Disponible' };
        const gira = d.de_gira ? { ok: true, texto: 'De gira ahora: cobra partido a partido hasta volver' }
            : d.gira_ok ? { ok: true, texto: 'Disponible ahora' } : { ok: false, texto: d.gira_motivo || 'No disponible por ahora' };
        const fila = (icono, titulo, e, accion, extra = '') => `
            <li class="cd-accion ${e.ok ? '' : 'cd-accion--no'}">
              <i class="bi ${icono} cd-accion__icono"></i>
              <div class="min-w-0 flex-grow-1"><div class="text-white fw-semibold">${titulo}</div><small class="${e.ok ? 'text-secondary' : 'text-warning'}">${esc(e.texto)}</small>${extra}</div>
              ${accion && e.ok ? accion : ''}
            </li>`;
        const marcasTxt = nMarcas ? `<small class="d-block text-muted">Lo patrocinan: ${esc(d.marcas.join(', '))}${d.marcas_pago ? ` (+${fmt(d.marcas_pago)} por ciclo)` : ''}${(d.marcas_aviso || []).length ? ` · <span class="text-danger">revisando: ${esc(d.marcas_aviso.join(', '))}</span>` : ''}</small>` : '';
        const filas = [
            fila('bi-megaphone-fill', 'Promover con una marca', promo, '<button type="button" class="btn btn-sm btn-outline-warning rounded-pill flex-shrink-0" data-detalle-accion="promover"><i class="bi bi-megaphone"></i> Promover</button>', marcasTxt),
            fila('bi-airplane-fill', 'Gira de exhibición', gira, d.de_gira ? '' : '<button type="button" class="btn btn-sm btn-outline-info rounded-pill flex-shrink-0" data-detalle-accion="gira"><i class="bi bi-airplane"></i> Gira</button>'),
            fila('bi-arrow-repeat', 'Renovación', d.puede_renovar ? { ok: true, texto: `Disponible: cuesta ${fmt(d.costo_renovar)} y suma satisfacción` } : { ok: false, texto: `Se abre en los últimos 3 ciclos del contrato` },
                 '<button type="button" class="btn btn-sm btn-outline-success rounded-pill flex-shrink-0" data-detalle-accion="renovar"><i class="bi bi-arrow-repeat"></i> Renovar</button>',
                 d.renovacion ? `<small class="d-block cd-renov cd-renov--${esc(d.renovacion.decision)}">${esc(d.renovacion.texto)}</small>` : ''),
        ];
        if (d.tv) filas.push(fila('bi-broadcast', 'Televisión', { ok: true, texto: `Lo transmite ${d.tv.nombre}: ${d.tv.jugados} de ${d.tv.partidos} partidos del contrato` }));
        if (d.invitado_tv) filas.push(fila('bi-person-video3', 'Invitado en TV', { ok: true, texto: `${d.invitado_tv.nombre} lo invitó (${d.invitado_tv.fecha}): cobra al jugarse el partido` }));
        return `<section class="cd-seccion"><h6 class="cd-titulo"><i class="bi bi-lightning-charge-fill me-1"></i>Lo que puedes hacer</h6><ul class="cd-acciones">${filas.join('')}</ul></section>`;
    }

    let tarjetaAbierta = null;
    function abrirDetalle(zona) {
        let d;
        try { d = JSON.parse(zona.dataset.detalleContrato); } catch (e) { return; }
        tarjetaAbierta = zona.closest('.corp-contrato');
        const el = modal();
        el.querySelector('#detContratoCaja').innerHTML = `
            <div class="modal-header border-secondary">
              <div class="min-w-0">
                <h5 class="modal-title fw-bold text-white" id="detContratoTitulo">${esc(d.nombre)}</h5>
                <small class="text-muted">${d.tipo === 'seleccion' ? 'Selección' : 'Jugador'}${d.pais ? ` · ${esc(d.pais)}` : ''}</small>
              </div>
              <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Cerrar"></button>
            </div>
            <div class="modal-body">${bloqueSatisfaccion(d)}${bloqueAcciones(d)}${bloquePatrocinadores(d)}${bloqueTelevision(d)}${bloqueNumeros(d)}</div>`;
        bootstrap.Modal.getOrCreateInstance(el).show();
    }

    // Los botones del modal usan los de la tarjeta (mismo flujo de siempre: cotización, confirmación, cobro)
    const SELECTOR_ACCION = {
        promover: '[data-promover]',
        gira: '[data-gira-grupal], [data-contrato-accion="gira"]',
        renovar: '[data-contrato-accion="renovar"]',
    };
    document.addEventListener('click', ev => {
        const info = ev.target.closest('[data-cd-reglas]');
        if (info) {
            const bloque = document.getElementById('cdReglas');
            if (!bloque) return;
            bloque.hidden = !bloque.hidden;
            info.setAttribute('aria-expanded', String(!bloque.hidden));
            info.classList.toggle('is-abierto', !bloque.hidden);
            info.querySelector('span').textContent = bloque.hidden ? '¿Cómo sube?' : 'Ocultar reglas';
            return;
        }
        const accion = ev.target.closest('[data-detalle-accion]');
        if (accion) {
            const boton = tarjetaAbierta && tarjetaAbierta.querySelector(SELECTOR_ACCION[accion.dataset.detalleAccion]);
            const el = document.getElementById('modalDetalleContrato');
            if (!boton || boton.disabled) { accion.disabled = true; return; }
            el.addEventListener('hidden.bs.modal', () => boton.click(), { once: true });
            bootstrap.Modal.getOrCreateInstance(el).hide();
            return;
        }
        const zona = ev.target.closest('[data-detalle-contrato]');
        // los chips con su propia acción (televisora, señal desplegable, enlaces) siguen funcionando como antes
        if (!zona || ev.target.closest('button, a, details, summary, [data-tv-ficha]')) return;
        abrirDetalle(zona);
    });
    document.addEventListener('keydown', ev => {
        if ((ev.key === 'Enter' || ev.key === ' ') && ev.target.matches && ev.target.matches('[data-detalle-contrato]')) {
            ev.preventDefault();
            abrirDetalle(ev.target);
        }
    });
})();
