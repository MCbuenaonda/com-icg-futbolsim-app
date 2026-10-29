/*
 * Filtros y orden de la cartera del corporativo (/corporativo/{sigla}). Todo en el navegador: cada representado trae
 * sus datos en atributos data-* (macro datos_cartera de corporativo_perfil.html).
 */
document.addEventListener('DOMContentLoaded', function () {
    const barra = document.getElementById('filtrosCartera');
    if (!barra) return;
    const $ = id => document.getElementById(id);
    const items = [...document.querySelectorAll('[data-cartera]')];
    const rejillas = [...document.querySelectorAll('[data-rejilla]')];
    const flags = new Set();
    const CLAVE = 'corp-cartera-orden';

    try { const o = localStorage.getItem(CLAVE); if (o && [...$('fcOrden').options].some(x => x.value === o)) $('fcOrden').value = o; } catch (e) { /* sin almacenamiento */ }

    function valor(el, campo) {
        return campo === 'nombre' ? el.dataset.nombre : Number(el.dataset[campo] || 0);
    }

    function aplicar() {
        const q = $('fcBuscar').value.trim().toLowerCase();
        const tipo = $('fcTipo').value, conf = $('fcConf').value;
        const [campo, sentido] = $('fcOrden').value.split(':');
        let visibles = 0;
        items.forEach(el => {
            const f = new Set((el.dataset.flags || '').split(' ').filter(Boolean));
            const ok = (!q || el.dataset.nombre.includes(q)) && (!tipo || el.dataset.tipo === tipo)
                && (!conf || el.dataset.conf === conf) && [...flags].every(x => f.has(x));
            el.classList.toggle('d-none', !ok);
            if (ok) visibles++;
        });
        rejillas.forEach(r => {
            const hijos = [...r.querySelectorAll(':scope > [data-cartera]')];
            hijos.sort((a, b) => {
                const va = valor(a, campo), vb = valor(b, campo);
                const c = typeof va === 'string' ? va.localeCompare(vb, 'es') : va - vb;
                return sentido === 'desc' ? -c : c;
            }).forEach(h => r.appendChild(h));
            const hay = hijos.some(h => !h.classList.contains('d-none'));
            r.classList.toggle('d-none', !hay);
            const titulo = document.querySelector(`[data-seccion="${r.dataset.rejilla}"]`);
            if (titulo) titulo.classList.toggle('d-none', !hay);
        });
        $('fcConteo').textContent = visibles === items.length ? `${items.length} representados` : `Mostrando ${visibles} de ${items.length}`;
        $('fcVacio').classList.toggle('d-none', visibles > 0 || !items.length);
    }

    let temporizador = null;
    $('fcBuscar').addEventListener('input', () => { clearTimeout(temporizador); temporizador = setTimeout(aplicar, 150); });
    ['fcTipo', 'fcConf'].forEach(id => $(id).addEventListener('change', aplicar));
    $('fcOrden').addEventListener('change', () => { try { localStorage.setItem(CLAVE, $('fcOrden').value); } catch (e) { /* sin almacenamiento */ } aplicar(); });
    barra.querySelectorAll('[data-flag]').forEach(b => b.addEventListener('click', () => {
        const f = b.dataset.flag;
        flags.has(f) ? flags.delete(f) : flags.add(f);
        b.classList.toggle('is-activo', flags.has(f));
        b.setAttribute('aria-pressed', flags.has(f));
        aplicar();
    }));
    $('fcLimpiar').addEventListener('click', () => {
        $('fcBuscar').value = ''; $('fcTipo').value = ''; $('fcConf').value = '';
        flags.clear();
        barra.querySelectorAll('[data-flag]').forEach(b => { b.classList.remove('is-activo'); b.setAttribute('aria-pressed', 'false'); });
        aplicar();
    });
    // Los chips que no aplican a nadie de la cartera se ocultan (p. ej. «De gira» si no hay giras en curso)
    barra.querySelectorAll('[data-flag]').forEach(b => {
        if (!items.some(el => (el.dataset.flags || '').split(' ').includes(b.dataset.flag))) b.classList.add('d-none');
    });
    aplicar();
});
