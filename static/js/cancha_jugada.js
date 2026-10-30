/*
 * Guion de cada jugada de la Cancha en Vivo (lógica pura, sin DOM: se prueba con node).
 *
 * El motor guarda por evento el recorrido del balón (services/balon.py), en coordenadas ABSOLUTAS de la cancha
 * (x 0-100, el local ataca a la derecha; y 0-68):
 *   balon = { s: inicio de la jugada, o: origen, d: destino, t: trayectoria, l: 1 si atacaba el local,
 *             q: [[x, y, nombre, 'r'|'a'|'c'], ...] pases y conducciones que el motor no narra }
 * guion(evento, posActual) lo convierte en PASOS que el animador de live_match.js reproduce en orden:
 *   { desde, hasta, curva, portador, receptor, marca, principal, l }
 *   curva: raso | aereo | tiro | conduccion | colocar (la pelota se repone) | fuera | parado (pausa)
 * Los partidos viejos no traen 'balon': guionViejo arma un solo paso desde donde estaba la pelota, con los tiros al arco.
 */
(function (raiz) {
    'use strict';

    // Peso relativo de cada curva en el tiempo de la jugada (un tiro es rápido, un centro tarda)
    const PESO = { raso: 1, aereo: 1.35, conduccion: 1.15, tiro: 0.6, colocar: 0.5, fuera: 0.85, parado: 0.45 };
    const MIN_PASO_MS = 220;
    // Tope por curva: un tiro nunca es lento; una conducción o una pausa pueden estirarse
    const MAX_PASO_MS = { raso: 1800, aereo: 2300, conduccion: 2600, tiro: 900, colocar: 900, fuera: 1500, parado: 2500 };
    const CURVA_CORTA = { r: 'raso', a: 'aereo', c: 'conduccion' };
    const UMBRAL_COLOCAR = 2.5;   // más que esto entre donde quedó la pelota y donde arranca la jugada: se repone

    const TIPOS_TIRO = new Set(['🎯 DISPARO DESVIADO', '🧤 ATAJADA ESPECTACULAR', '🖐️ DESVÍO A CÓRNER', '❌ PENAL FALLADO']);
    const TIPOS_ATAJADA = new Set(['🧤 ATAJADA ESPECTACULAR', '❌ PENAL FALLADO', '🖐️ DESVÍO A CÓRNER']);
    const TIPOS_INTERCEPCION = new Set(['⚡ EN TRANSICIÓN', '🧠 ROBO DE BALÓN']);

    const distancia = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
    const punto = par => ({ x: par[0], y: par[1] });
    const esGol = tipo => (tipo || '').startsWith('⚽');
    const enBanderita = p => (p.x < 1.5 || p.x > 98.5) && (p.y < 1.5 || p.y > 66.5);

    // Qué hace cada jugador nombrado en la jugada principal: el que lleva la pelota al empezar (portador), el que la
    // tiene al terminar (receptor) y el rival que se acerca (marca)
    function actores(evento, curva, origen) {
        const t = evento.tipo || '';
        const j = evento.jugadores || [];
        if (t === '⏳ PREPARACIÓN') {
            if (j.length === 2 && enBanderita(origen)) return { receptor: j[0], marca: j[1] };   // centro de córner
            if (j.length === 2) return { portador: j[0], receptor: j[1] };                      // pase al que remata
            if (curva === 'colocar') return { portador: j[0] };                                  // penal o tiro libre
            return { portador: j[0], receptor: j[0] };                                           // se acomoda para rematar
        }
        if (t === '🔵 SAQUE DE CENTRO') return { portador: j[0], receptor: j[1] };
        if (TIPOS_INTERCEPCION.has(t)) return { portador: j[1], receptor: j[0] };
        if (t === '🔥 PRESIÓN DEFENSIVA') return j.length > 1 ? { portador: j[1], receptor: j[1], marca: j[0] } : { marca: j[0] };
        if (t === '⚡ REGATE DESTACADO') return { portador: j[0], receptor: j[0] };
        if (TIPOS_ATAJADA.has(t)) return { arquero: j[0], portador: j[1] };
        if (esGol(t) || TIPOS_TIRO.has(t)) return { portador: j[0] };
        if (t === '🛡️ CÓRNER DESPEJADO' || t === '↔️ SAQUE DE BANDA') return { portador: j[0] };
        if (t === '🛑 FALTA') return { marca: j[0], portador: j[1] };
        return { portador: j[0] };
    }

    function efecto(tipo) {
        if (esGol(tipo)) return 'gol';
        if (TIPOS_ATAJADA.has(tipo)) return 'atajada';
        if (tipo === '🎯 DISPARO DESVIADO' || tipo === '↔️ SAQUE DE BANDA') return 'fuera';
        if (tipo === '🛑 FALTA' || (tipo || '').includes('TARJETA') || (tipo || '').includes('AMARILLA')) return 'parada';
        return null;
    }

    function guion(evento, posActual) {
        const b = evento.balon;
        if (!b) return null;
        const pasos = [];
        let actual = posActual || { x: 50, y: 34 };
        const inicio = punto(b.s || b.o);
        if (distancia(actual, inicio) > UMBRAL_COLOCAR) {
            pasos.push({ desde: actual, hasta: inicio, curva: 'colocar', l: b.l });
            actual = inicio;
        }
        (b.q || []).forEach(([x, y, nombre, t]) => {
            const hasta = { x, y };
            pasos.push({ desde: actual, hasta, curva: CURVA_CORTA[t] || 'raso', receptor: nombre, portador: t === 'c' ? nombre : null, l: b.l });
            actual = hasta;
        });
        const origen = punto(b.o);
        if (distancia(actual, origen) > UMBRAL_COLOCAR) {
            pasos.push({ desde: actual, hasta: origen, curva: 'colocar', l: b.l });
            actual = origen;
        }
        const curva = b.t || 'raso';
        // una diferencia chica no se repone: la jugada sale de donde está la pelota
        const destino = curva === 'parado' || curva === 'colocar' ? actual : punto(b.d);
        pasos.push({ desde: actual, hasta: destino, curva, principal: true, l: b.l, ...actores(evento, curva, origen) });
        return { pasos, efecto: efecto(evento.tipo), final: pasos[pasos.length - 1].hasta };
    }

    // Partidos simulados antes del recorrido: un solo paso desde donde quedó la pelota; los tiros terminan en el arco
    function guionViejo(evento, posActual, posNueva, atacaLocal) {
        const t = evento.tipo || '';
        let hasta = { x: posNueva.x, y: posNueva.y };
        let curva = 'raso';
        const lineaArco = atacaLocal ? 100 : 0;
        if (esGol(t)) {
            hasta = { x: lineaArco, y: Math.min(37.4, Math.max(30.6, posNueva.y)) };
            curva = 'tiro';
        } else if (TIPOS_ATAJADA.has(t)) {
            hasta = { x: atacaLocal ? 97.5 : 2.5, y: Math.min(39, Math.max(29, posNueva.y)) };
            curva = 'tiro';
        } else if (t === '🎯 DISPARO DESVIADO') {
            hasta = { x: lineaArco, y: posNueva.y < 34 ? Math.min(28, posNueva.y) : Math.max(40, posNueva.y) };
            curva = 'tiro';
        }
        const j = evento.jugadores || [];
        const desde = posActual || { x: 50, y: 34 };
        return {
            pasos: [{ desde, hasta, curva, principal: true, l: atacaLocal ? 1 : 0, receptor: curva === 'tiro' ? null : j[0], portador: curva === 'tiro' ? j[0] : null }],
            efecto: efecto(t), final: hasta
        };
    }

    // Reparte el tiempo disponible entre los pasos según su peso, sin bajar ni pasar los topes
    function repartir(pasos, totalMs) {
        const pesos = pasos.map(p => PESO[p.curva] || 1);
        const suma = pesos.reduce((a, b) => a + b, 0) || 1;
        return pasos.map((p, i) => ({ ...p, ms: Math.round(Math.max(MIN_PASO_MS, Math.min(MAX_PASO_MS[p.curva] || 1800, totalMs * pesos[i] / suma))) }));
    }

    const suave = f => f < 0.5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2;   // acelera y frena (pase)
    const sale = f => 1 - Math.pow(1 - f, 3);                                       // sale fuerte (tiro)

    // Dónde está la pelota en la fracción f (0..1) del paso; 'altura' 0..1 para los balones aéreos
    function posicion(paso, f) {
        let g = f;
        if (paso.curva === 'tiro' || paso.curva === 'fuera') g = sale(f);
        else if (paso.curva === 'raso' || paso.curva === 'aereo') g = suave(f);
        const x = paso.desde.x + (paso.hasta.x - paso.desde.x) * g;
        const y = paso.desde.y + (paso.hasta.y - paso.desde.y) * g;
        let altura = 0;
        if (paso.curva === 'aereo') altura = Math.min(1, distancia(paso.desde, paso.hasta) / 40) * 4 * f * (1 - f);
        return { x, y, altura };
    }

    const api = { guion, guionViejo, repartir, posicion, actores, efecto, PESO };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else raiz.CanchaJugada = api;
})(typeof window !== 'undefined' ? window : this);
