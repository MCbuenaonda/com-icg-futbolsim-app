/*
 * Gráficos y animaciones de las fichas de país (/paises/{id}) y jugador (/jugadores/{id}).
 *
 *  - Animaciones del DOM dentro de un contenedor .js-animar, cuando entran en pantalla:
 *      .anillo-kpi             el anillo se llena desde 0 y su número cuenta hacia arriba
 *      .barra-atributo__pista  las barras crecen escalonadas (y su valor cuenta)
 *      .barra-wdl              la barra G/E/P se despliega tramo por tramo
 *      [data-contar]           números que cuentan desde 0 (respeta prefijo, sufijo y decimales)
 *  - GraficosFIFAV: helpers de Chart.js con el mismo estilo (tooltip oscuro, ejes recesivos, brillo en las líneas,
 *    degradados, dibujo progresivo de una línea y arranque recién cuando el gráfico se ve).
 * Con "reducir movimiento" no se anima nada: todo aparece en su valor final.
 */
window.GraficosFIFAV = (function () {
    const reducido = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const facil = t => 1 - Math.pow(1 - t, 3);   // easeOutCubic

    // Ejecuta fn una sola vez, cuando el elemento entra en pantalla
    function alVer(el, fn, umbral = 0.2) {
        if (!el) return;
        if (reducido || !('IntersectionObserver' in window)) { fn(); return; }
        const io = new IntersectionObserver((entradas, obs) => {
            entradas.forEach(e => { if (e.isIntersecting) { obs.unobserve(e.target); fn(); } });
        }, { threshold: umbral });
        io.observe(el);
    }

    // ---------- Números que cuentan ----------
    function partirNumero(texto) {
        const m = String(texto).match(/^(\D*?)(-?\d+(?:[.,]\d+)?)(.*)$/s);
        if (!m) return null;
        const decimales = (m[2].split(/[.,]/)[1] || '').length;
        return { antes: m[1], valor: parseFloat(m[2].replace(',', '.')), despues: m[3], decimales, coma: m[2].includes(',') };
    }
    function contar(el, duracion = 1100, demora = 0) {
        const p = partirNumero(el.textContent.trim());
        if (!p || reducido) return;
        const fmt = v => {
            const s = v.toFixed(p.decimales);
            return p.antes + (p.coma ? s.replace('.', ',') : s) + p.despues;
        };
        el.textContent = fmt(0);
        setTimeout(() => {
            const t0 = performance.now();
            const paso = ahora => {
                const t = Math.min(1, (ahora - t0) / duracion);
                el.textContent = fmt(p.valor * facil(t));
                if (t < 1) requestAnimationFrame(paso);
            };
            requestAnimationFrame(paso);
        }, demora);
    }

    // ---------- Anillos (conic-gradient con --pct) ----------
    function animarAnillo(anillo, demora = 0) {
        const objetivo = parseFloat(getComputedStyle(anillo).getPropertyValue('--pct')) || 0;
        const numero = anillo.querySelector('span');
        if (reducido) return;
        anillo.style.setProperty('--pct', 0);
        if (numero) contar(numero, 1200, demora);
        setTimeout(() => {
            const t0 = performance.now();
            const paso = ahora => {
                const t = Math.min(1, (ahora - t0) / 1200);
                anillo.style.setProperty('--pct', (objetivo * facil(t)).toFixed(1));
                if (t < 1) requestAnimationFrame(paso);
            };
            requestAnimationFrame(paso);
        }, demora);
    }

    // ---------- Barras ----------
    function animarBarras(barras) {
        barras.forEach((b, i) => {
            const ancho = b.style.width;
            if (reducido || !ancho) return;
            b.style.transition = 'none';
            b.style.width = '0%';
            requestAnimationFrame(() => requestAnimationFrame(() => {
                b.style.transition = `width .9s cubic-bezier(.2,.8,.2,1) ${i * 45}ms`;
                b.style.width = ancho;
            }));
        });
    }
    function animarWdl(barra, demora = 0) {
        const tramos = [...barra.children];
        if (reducido || !tramos.length) return;
        const finales = tramos.map(t => t.style.flex || getComputedStyle(t).flexGrow);
        tramos.forEach(t => { t.style.transition = 'none'; t.style.flex = '0.0001'; });
        setTimeout(() => requestAnimationFrame(() => tramos.forEach((t, i) => {
            t.style.transition = `flex-grow .8s cubic-bezier(.2,.8,.2,1) ${i * 160}ms`;
            t.style.flex = finales[i];
        })), demora);
    }

    function animarDom(raiz) {
        raiz.querySelectorAll('.anillo-kpi').forEach((a, i) => alVer(a, () => animarAnillo(a, (i % 4) * 120)));
        raiz.querySelectorAll('.barra-wdl').forEach(b => alVer(b, () => animarWdl(b)));
        raiz.querySelectorAll('[data-contar]').forEach(n => alVer(n, () => contar(n, 1000)));
        // barras de atributos: por grupo, escalonadas; su valor también cuenta
        raiz.querySelectorAll('.grupo-atributos, .js-barras').forEach(grupo => alVer(grupo, () => {
            animarBarras([...grupo.querySelectorAll('.barra-atributo__pista > span')]);
            grupo.querySelectorAll('.barra-atributo__valor, .grupo-atributos__media').forEach(v => contar(v, 1000));
        }));
    }

    // ---------- Chart.js ----------
    function estilo() {
        if (!window.Chart) return;
        Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
        Chart.defaults.color = '#9ca3af';
        Chart.defaults.borderColor = 'rgba(255,255,255,.06)';
        Object.assign(Chart.defaults.plugins.tooltip, {
            backgroundColor: 'rgba(11,18,32,.96)', borderColor: 'rgba(255,255,255,.14)', borderWidth: 1, titleColor: '#f0efec',
            bodyColor: '#c3c2b7', padding: 10, cornerRadius: 10, boxPadding: 4, usePointStyle: true,
        });
    }
    // Brillo suave detrás de las líneas que lo pidan (dataset.brillo = color)
    const brillo = {
        id: 'brilloFIFAV',
        beforeDatasetDraw(chart, args) {
            const ds = chart.data.datasets[args.index];
            if (!ds.brillo) return;
            chart.ctx.save();
            chart.ctx.shadowColor = ds.brillo; chart.ctx.shadowBlur = 14; chart.ctx.shadowOffsetY = 2;
        },
        afterDatasetDraw(chart, args) { if (chart.data.datasets[args.index].brillo) chart.ctx.restore(); },
    };
    // Relleno en degradé vertical: color arriba, transparente abajo
    function degradado(color, arriba = 0.45, abajo = 0) {
        return ctx => {
            const { chart } = ctx, a = chart.chartArea;
            if (!a) return 'transparent';
            const g = chart.ctx.createLinearGradient(0, a.top, 0, a.bottom);
            g.addColorStop(0, alfa(color, arriba)); g.addColorStop(1, alfa(color, abajo));
            return g;
        };
    }
    function alfa(hex, a) {
        const n = parseInt(hex.slice(1), 16);
        return `rgba(${n >> 16}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
    }
    // La línea se dibuja de izquierda a derecha, punto por punto (patrón "progressive line" de Chart.js)
    function animacionProgresiva(puntos, total = 1400) {
        if (reducido) return false;
        const demora = total / Math.max(1, puntos);
        const anterior = ctx => ctx.index === 0 ? ctx.chart.scales.y.getPixelForValue(ctx.chart.scales.y.min < 0 && ctx.chart.scales.y.max > 0 ? 0 : ctx.chart.scales.y.min)
            : ctx.chart.getDatasetMeta(ctx.datasetIndex).data[ctx.index - 1].getProps(['y'], true).y;
        return {
            x: { type: 'number', easing: 'linear', duration: demora, from: NaN,
                 delay(ctx) { if (ctx.type !== 'data' || ctx.xStarted) return 0; ctx.xStarted = true; return ctx.index * demora; } },
            y: { type: 'number', easing: 'linear', duration: demora, from: anterior,
                 delay(ctx) { if (ctx.type !== 'data' || ctx.yStarted) return 0; ctx.yStarted = true; return ctx.index * demora; } },
        };
    }
    // Crea el gráfico recién cuando su lienzo entra en pantalla (así la animación se ve)
    function crearAlVer(canvas, config) {
        let chart = null;
        alVer(canvas, () => { estilo(); chart = new Chart(canvas, config); }, 0.25);
        return () => chart;
    }

    document.addEventListener('DOMContentLoaded', () => document.querySelectorAll('.js-animar').forEach(animarDom));

    return { reducido, alVer, contar, brillo, degradado, alfa, animacionProgresiva, crearAlVer, estilo };
})();
