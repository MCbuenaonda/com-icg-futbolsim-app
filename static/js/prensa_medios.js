/*
 * Directorio de medios (/red-social/medios): filtros y orden en el navegador, de a POR_PAGINA con «Mostrar más», y la ficha de cada medio en un
 * modal (GET /red-social/medios/{id}). También se abre con #medio-<id> (los enlaces de las notas de prensa).
 */
(() => {
    const esc = s => UI.escapar(String(s ?? ''));
    const POR_PAGINA = 48;
    const $ = id => document.getElementById(id);

    function modal() {
        let el = $('modalMedio');
        if (el) return el;
        el = document.createElement('div');
        el.className = 'modal fade'; el.id = 'modalMedio'; el.tabIndex = -1;
        el.innerHTML = '<div class="modal-dialog modal-dialog-centered modal-dialog-scrollable modal-lg"><div class="modal-content bg-dark border-secondary tv-ficha" id="medioCaja"></div></div>';
        document.body.appendChild(el);
        return el;
    }

    const cara = (p, clase = '') => p.avatar_url ? `<img class="tv-cara ${clase}" src="${esc(p.avatar_url)}" alt="${esc(p.nombre)}" loading="lazy" onerror="this.remove()">` : '';
    const SESGO = { neutral: 'Neutral', patriota: 'Patriota', critico: 'Crítico con los suyos' };

    function fichaHtml(m) {
        const pers = m.periodistas.map(p => `<div class="tv-persona" title="${esc(p.estilo_nombre)}: ${esc(SESGO[p.sesgo] || '')}">${cara(p)}<span><strong>${esc(p.nombre)}</strong><small>${esc(p.rol)} · ${esc(p.estilo_nombre)} · ${esc(p.sesgo_nombre || SESGO[p.sesgo] || '')}</small></span></div>`).join('');
        const notas = m.notas.map(n => `<div class="prensa-nota" style="--medio:${esc(m.color)}"><div class="min-w-0"><div class="small"><span class="text-muted">${esc(n.periodista.nombre)} · ${esc(n.etiqueta)} · ${esc(n.fecha)}</span>
            <span class="medio-tono medio-tono--${esc(n.categoria_tono)} ms-1"><i class="bi ${esc(n.tono_icono)}"></i>${esc(n.tono_nombre)}</span></div>
            <div class="text-body-secondary fs-8">${esc(n.texto)}</div><a class="fs-8 text-decoration-none" href="/juegos/${esc(n.juego_id)}">Ver el partido</a></div></div>`).join('')
            || '<div class="small text-muted">Todavía no ha publicado nada.</div>';
        const pron = m.pronosticos_recientes.map(p => `<div class="small mb-1"><span class="text-muted">${esc(p.texto)}</span> ${p.estado === 'acertado' ? '<span class="medio-tono medio-tono--elogio"><i class="bi bi-check-circle-fill"></i>' + (p.exacto ? ' exacto' : '') + '</span>'
            : (p.estado === 'fallado' ? '<span class="medio-tono medio-tono--critica"><i class="bi bi-x-circle-fill"></i></span>' : '<span class="text-muted">pendiente</span>')} <a class="fs-8 text-decoration-none" href="/juegos/${esc(p.juego_id)}">ver</a></div>`).join('')
            || '<div class="small text-muted">Sin pronósticos todavía.</div>';
        const acierto = m.pct === null ? 'sin pronósticos calificados' : `${m.aciertos} de ${m.pronosticos} (${m.pct}%)${m.exactos ? ' · ' + m.exactos + ' marcador' + (m.exactos === 1 ? '' : 'es') + ' exacto' + (m.exactos === 1 ? '' : 's') : ''}`;
        return `<div class="tv-ficha__portada" style="--tv:${esc(m.color)}">${m.logo ? `<img src="${esc(m.logo)}" alt="${esc(m.nombre)}">` : ''}</div>
            <div class="modal-body">
              <div class="d-flex justify-content-between align-items-start gap-2">
                <div><h5 class="fw-bold text-white mb-0">${esc(m.nombre)}</h5>
                  <div class="text-muted small">${m.pais_id ? UI.bandera('', { id: m.pais_id }) + ' ' : ''}${esc(m.pais)}${m.confederacion ? ' · ' + esc(m.confederacion) : ''} · ${esc(m.papel_nombre)} · ${esc(m.nivel_nombre)}</div></div>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Cerrar"></button>
              </div>
              <div class="mk-ficha__datos mt-3">
                <span style="color:${esc(m.color)}"><i class="bi bi-vector-pen"></i>Línea ${esc(m.linea_nombre.toLowerCase())}: ${esc(m.linea_texto)}</span>
                <span><i class="bi bi-shield-check"></i>Credibilidad ${m.credibilidad}/100${m.credibilidad !== m.credibilidad_base ? ' (base ' + m.credibilidad_base + ')' : ''}: es lo que pesa lo que dice en la reputación de jugadores, técnicos y selecciones.</span>
                <span><i class="bi bi-bullseye"></i>Pronósticos: ${esc(acierto)}</span>
                <span><i class="bi bi-newspaper"></i>${m.total_notas} nota${m.total_notas === 1 ? '' : 's'} publicada${m.total_notas === 1 ? '' : 's'}${m.tono_medio !== null ? ' · tono reciente ' + (m.tono_medio > 0 ? '+' : '') + m.tono_medio : ''}</span>
              </div>
              <h6 class="fw-bold text-white mt-3 mb-1 small">Quién lo dirige</h6>
              <div class="tv-equipo"><div class="tv-persona tv-persona--dueno" title="${esc(m.director.rasgo_texto)}">${cara(m.director)}<span><strong>${esc(m.director.nombre)}</strong><small>director · línea ${esc(m.director.rasgo_nombre)}</small></span></div></div>
              <h6 class="fw-bold text-white mt-3 mb-1 small">Sus periodistas</h6><div class="tv-equipo">${pers}</div>
              <h6 class="fw-bold text-white mt-3 mb-1 small">Lo último que publicó</h6><div class="prensa-lista">${notas}</div>
              <h6 class="fw-bold text-white mt-3 mb-1 small">Sus pronósticos</h6>${pron}
              <div class="mt-3"><a class="btn btn-sm btn-outline-info rounded-pill" href="/red-social/?filtro=prensa&q=${encodeURIComponent(m.nombre)}"><i class="bi bi-chat-square-text me-1"></i>Todas sus notas</a></div>
            </div>`;
    }

    async function abrir(id) {
        const el = modal();
        const caja = $('medioCaja');
        caja.innerHTML = '<div class="modal-body text-center text-muted py-5"><span class="spinner-border spinner-border-sm me-2"></span>Cargando…</div>';
        bootstrap.Modal.getOrCreateInstance(el).show();
        try {
            const r = await fetch(`/red-social/medios/${encodeURIComponent(id)}`, { headers: { accept: 'application/json' } });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'No se pudo cargar la ficha');
            caja.innerHTML = fichaHtml(d);
            history.replaceState(null, '', '#medio-' + id);
        } catch (e) {
            caja.innerHTML = `<div class="modal-body"><div class="alert alert-danger small mb-0">${esc(e.message)}</div></div>`;
        }
    }

    document.addEventListener('click', ev => { const b = ev.target.closest('[data-medio]'); if (b) { ev.preventDefault(); abrir(b.dataset.medio); } });
    document.addEventListener('hidden.bs.modal', ev => { if (ev.target.id === 'modalMedio') history.replaceState(null, '', location.pathname); });

    const lista = $('pmLista');
    const celdas = [...lista.querySelectorAll('.tv-celda')];
    let visibles = POR_PAGINA;
    const CLAVE = 'pm-orden';
    try { const o = localStorage.getItem(CLAVE); if (o && [...$('pmOrden').options].some(x => x.value === o)) $('pmOrden').value = o; } catch (e) { /* sin almacenamiento */ }

    function ordenar(a, b) {
        const o = $('pmOrden').value;
        if (o === 'credibilidad') return Number(b.dataset.cred) - Number(a.dataset.cred);
        if (o === 'acierto') return Number(b.dataset.acierto) - Number(a.dataset.acierto) || Number(b.dataset.cred) - Number(a.dataset.cred);
        if (o === 'nombre') return a.dataset.ordenNombre.localeCompare(b.dataset.ordenNombre, 'es');
        if (o === 'pais') return a.dataset.pais.localeCompare(b.dataset.pais, 'es') || a.dataset.ordenNombre.localeCompare(b.dataset.ordenNombre, 'es');
        return Number(b.dataset.nivel) - Number(a.dataset.nivel) || a.dataset.pais.localeCompare(b.dataset.pais, 'es');
    }

    function aplicar(reiniciar = true) {
        if (reiniciar) visibles = POR_PAGINA;
        const q = $('pmBuscar').value.trim().toLowerCase();
        const conf = $('pmConf').value, nivel = $('pmNivel').value, tipo = $('pmTipo').value, linea = $('pmLinea').value;
        const ok = celdas.filter(c => (!q || c.dataset.nombre.includes(q)) && (!conf || c.dataset.conf === conf) && (!nivel || c.dataset.nivel === nivel)
            && (!tipo || c.dataset.tipo === tipo) && (!linea || c.dataset.linea === linea));
        ok.sort(ordenar);
        const set = new Set(ok);
        celdas.forEach(c => { if (!set.has(c)) c.hidden = true; });
        ok.forEach((c, i) => { c.hidden = i >= visibles; lista.appendChild(c); });
        $('pmConteo').textContent = ok.length === celdas.length ? `${celdas.length} medios` : `${ok.length} de ${celdas.length} medios`;
        $('pmMas').classList.toggle('d-none', ok.length <= visibles);
        $('pmMas').textContent = `Mostrar más (${Math.max(0, ok.length - visibles)})`;
        $('pmVacio').classList.toggle('d-none', ok.length > 0);
    }

    let t = null;
    $('pmBuscar').addEventListener('input', () => { clearTimeout(t); t = setTimeout(aplicar, 150); });
    ['pmConf', 'pmNivel', 'pmTipo', 'pmLinea'].forEach(id => $(id).addEventListener('change', () => aplicar()));
    $('pmOrden').addEventListener('change', () => { try { localStorage.setItem(CLAVE, $('pmOrden').value); } catch (e) { /* sin almacenamiento */ } aplicar(); });
    $('pmMas').addEventListener('click', () => { visibles += POR_PAGINA; aplicar(false); });
    aplicar();
    const m = /^#medio-(\d+)$/.exec(location.hash);
    if (m) abrir(m[1]);
})();
