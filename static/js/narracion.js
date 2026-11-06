/*
 * Narración de la transmisión en vivo (/en-vivo): a cada jugada ya revelada le asigna quién la comenta y qué dice.
 * Lógica pura (sin DOM): la usa static/js/transmision_vivo.js y se prueba con node (module.exports al final).
 *
 * Hablantes: narrador (cantado, repite la crónica de la jugada), analista (táctico), invitado (un jugador) y, cuando no
 * hay cadena que transmita el partido, el narrador de radio (una sola voz). Todo sale de plantillas con una semilla
 * (partido + índice de la jugada): la misma jugada dice lo mismo al recargar y no hay dos partidos iguales.
 * Nunca usa datos que todavía no se hayan revelado: solo el evento, el marcador y el minuto del momento.
 */
(function (root) {
    'use strict';

    // ---------------------------------------------------------------- azar con semilla
    function hash(texto) {
        let h = 1779033703 ^ texto.length;
        for (let i = 0; i < texto.length; i++) {
            h = Math.imul(h ^ texto.charCodeAt(i), 3432918353);
            h = (h << 13) | (h >>> 19);
        }
        return () => {
            h = Math.imul(h ^ (h >>> 16), 2246822507);
            h = Math.imul(h ^ (h >>> 13), 3266489909);
            return (h ^= h >>> 16) >>> 0;
        };
    }
    function azar(semilla) {   // mulberry32
        let a = hash(String(semilla))();
        return () => {
            a = (a + 0x6D2B79F5) | 0;
            let t = Math.imul(a ^ (a >>> 15), 1 | a);
            t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    }

    // ---------------------------------------------------------------- qué es cada jugada
    const TIPOS = [   // [fragmento del tipo, clase]; gana la primera coincidencia
        ['ANULADO', 'var'], ['VAR', 'var'],
        ['PENAL', 'penal'],
        ['GOL', 'gol'],
        ['ROJA', 'roja'], ['DT EXPULSADO', 'roja'],
        ['AMARILLA', 'amarilla'], ['DT AMONESTADO', 'amarilla'],
        ['SUSTITUCIÓN', 'cambio'], ['LESIÓN', 'lesion'],
        ['RECLAMO DEL DT', 'dt'], ['AJUSTE TÁCTICO', 'dt'],
        ['ATAJADA', 'atajada'], ['DESVÍO A CÓRNER', 'atajada'], ['CÓRNER DESPEJADO', 'atajada'], ['TIRO LIBRE BLOQUEADO', 'atajada'],
        ['DISPARO DESVIADO', 'remate'], ['ERROR DE PORTERÍA', 'error'], ['SAQUE DE ESQUINA', 'corner'],
        ['REGATE', 'regate'], ['FALTA', 'falta'], ['FUERA DE LUGAR', 'offside'], ['SAQUE DE BANDA', 'banda'],
        ['ROBO DE BALÓN', 'robo'], ['EN TRANSICIÓN', 'robo'], ['PRESIÓN DEFENSIVA', 'robo'],
        ['PREPARACIÓN', 'preparacion'], ['DESGASTE', 'desgaste'],
        ['SILBATO INICIAL', 'inicio'], ['FINAL DEL PRIMER TIEMPO', 'descanso'], ['COMIENZA EL SEGUNDO TIEMPO', 'segundo'],
        ['TIEMPO AÑADIDO', 'anadido'], ['TIEMPO EXTRA', 'extra'], ['TANDA DE PENALTIS', 'tanda'], ['PITIDO FINAL', 'final'],
        ['SAQUE DE CENTRO', 'saque'],
    ];
    function clasificar(evento) {
        const tipo = (evento && evento.tipo) || '';
        for (const [fragmento, clase] of TIPOS) if (tipo.includes(fragmento)) return clase;
        return 'jugada';
    }

    // p = probabilidad de que la jugada se comente; prio = importancia (3 = nunca se descarta); cadena = quién habla y en qué orden
    // (rol[:probabilidad]); efecto = destello en pantalla; solo para goles, tarjetas y VAR.
    const CLASES = {
        gol:        { p: 1.0,  prio: 3, cadena: ['N', 'A', 'I:0.8'], efecto: 'gol' },
        penal:      { p: 1.0,  prio: 3, cadena: ['N', 'A:0.8', 'I:0.5'], efecto: 'penal' },
        roja:       { p: 1.0,  prio: 3, cadena: ['N', 'A', 'I:0.5'], efecto: 'roja' },
        amarilla:   { p: 0.95, prio: 2, cadena: ['N', 'A:0.55'], efecto: 'amarilla' },
        var:        { p: 1.0,  prio: 3, cadena: ['N', 'A:0.7'], efecto: 'var' },
        lesion:     { p: 0.9,  prio: 2, cadena: ['N', 'A:0.6'] },
        cambio:     { p: 0.6,  prio: 1, cadena: ['N:0.7', 'A:0.6'] },
        dt:         { p: 0.5,  prio: 1, cadena: ['N:0.6', 'A:0.6'] },
        atajada:    { p: 0.85, prio: 2, cadena: ['N', 'A:0.45', 'I:0.3'] },
        remate:     { p: 0.6,  prio: 1, cadena: ['N', 'A:0.4', 'I:0.25'] },
        error:      { p: 0.8,  prio: 2, cadena: ['N', 'A:0.5'] },
        corner:     { p: 0.35, prio: 1, cadena: ['N:0.6', 'A:0.5'] },
        regate:     { p: 0.35, prio: 1, cadena: ['N', 'A:0.5'] },
        falta:      { p: 0.3,  prio: 0, cadena: ['N:0.5', 'A:0.6'] },
        offside:    { p: 0.3,  prio: 0, cadena: ['N:0.5', 'A:0.6'] },
        banda:      { p: 0.08, prio: 0, cadena: ['N'] },
        robo:       { p: 0.07, prio: 0, cadena: ['N:0.6', 'A:0.6'] },
        preparacion:{ p: 0.25, prio: 0, cadena: ['N'] },
        desgaste:   { p: 0.5,  prio: 1, cadena: ['N:0.5', 'A'] },
        inicio:     { p: 1.0,  prio: 3, cadena: ['N', 'A', 'I:0.6'] },
        descanso:   { p: 1.0,  prio: 3, cadena: ['N', 'A', 'I:0.6'] },
        segundo:    { p: 1.0,  prio: 3, cadena: ['N', 'A:0.7'] },
        anadido:    { p: 1.0,  prio: 2, cadena: ['N', 'A:0.6'] },
        extra:      { p: 1.0,  prio: 3, cadena: ['N', 'A'] },
        tanda:      { p: 1.0,  prio: 3, cadena: ['N', 'A', 'I:0.7'] },
        final:      { p: 0,    prio: 3, cadena: ['N', 'A', 'I'] },   // el pitido final lo cubre la despedida (crear().despedida)
        saque:      { p: 0.2,  prio: 0, cadena: ['N'] },
        jugada:     { p: 0.2,  prio: 0, cadena: ['N', 'A:0.4'] },
    };

    // ---------------------------------------------------------------- frases
    // Marcadores: {desc} lo que cuenta la jugada, {j} {j2} jugadores (apellido), {eq} equipo de la jugada, {rival}, {min},
    // {marc} marcador del momento, {local} {visita} {estadio}. Una frase con un marcador sin valor no se usa.
    const FRASES = {
        gol: {
            N: ['¡GOOOOL! {desc}', '¡Y ES GOL! {desc}', '¡Aaaahí está! {desc}', '{desc} ¡Qué manera de celebrar, {eq}!', '¡Se abre el grito de gol para {eq}! {desc}'],
            A: ['Ahí marcó la diferencia: {j} supo leer el momento y {eq} lo aprovechó.', 'Fíjate en el movimiento previo: la defensa de {rival} llegó tarde.',
                'Gol que cambia el planteamiento: ahora {rival} tendrá que salir a buscarlo.', 'Eso viene de una jugada bien trabajada, {eq} lo tenía en la cabeza.',
                '{marc} en el marcador: {eq} se lo había ganado con la presión.'],
            I: ['¡Qué golazo! Esa sensación de ver entrar el balón no se compara con nada.', 'Cuando {j} agarra confianza, es difícil frenarlo.',
                'Uf, yo ahí hubiera gritado igual. ¡Qué definición!', 'Un gol así mueve a todo el vestuario; {eq} va a salir con otra cara.',
                'Ojo con {rival}: después de un gol así, lo difícil es levantar la cabeza.'],
        },
        penal: {
            N: ['{desc}', '¡Pena máxima! {desc}', '¡El árbitro señala el punto penal! {desc}'],
            A: ['Hay contacto claro, no hay mucho que protestar.', 'Un penal siempre es una moneda al aire para el portero.', 'Aquí pesan los nervios, del que cobra y del que lo espera.'],
            I: ['Cobrar un penal es otra cosa: las piernas pesan el doble.', 'Yo me quedo con el que cobra: tiene el partido entero en la cabeza.', 'Dicen que es fácil, hasta que te toca patearlo.'],
        },
        roja: {
            N: ['{desc}', '¡Tarjeta roja! {desc}', '¡Se complica todo para {eq}! {desc}'],
            A: ['Con uno menos, {eq} tiene que replantearlo todo: líneas más juntas y menos riesgo.', 'Esto cambia el partido por completo; {rival} puede cargar con espacios.', 'Una decisión que le cuesta carísimo a {eq}.'],
            I: ['Es lo peor que le puede pasar a un equipo: los compañeros tienen que correr por dos.', 'Desde adentro se siente cómo el equipo se queda callado un segundo.', 'Se pierde la cabeza en un segundo y se paga el resto del partido.'],
        },
        amarilla: {
            N: ['{desc}', '{desc} Ojo con esa advertencia.', 'Amonestación. {desc}'],
            A: ['Una amarilla que condiciona: {j} ahora tiene que cuidar cada entrada.', 'El árbitro marca la línea; toca jugar con inteligencia.', 'Hay que medir la intensidad a partir de ahora.'],
            I: ['Con amarilla uno juega a medias: la cabeza va por un lado y las piernas por otro.', 'Se aprende a convivir con la tarjeta, pero no es fácil.'],
        },
        var: {
            N: ['{desc}', 'Se detiene el juego. {desc}', 'Atención, el VAR entra en escena. {desc}'],
            A: ['Ahora manda la revisión: toca esperar sin adelantarse.', 'Estas pausas rompen el ritmo, pero la decisión tiene que ser la correcta.', 'En estas jugadas los centímetros mandan.'],
            I: ['Esperar al VAR se hace eterno desde la cancha.', 'Cuando el árbitro se lleva la mano al oído, el corazón se te sube a la garganta.'],
        },
        lesion: {
            N: ['{desc}', 'Se detiene el partido. {desc}', 'Atención médica en el campo. {desc}'],
            A: ['Ojalá no sea nada serio; en estos partidos cada minuto cuenta.', 'Si tiene que salir, el cuerpo técnico ya debe tener el cambio listo.'],
            I: ['Las lesiones son lo más duro; uno siempre piensa primero en el compañero.'],
        },
        cambio: {
            N: ['{desc}', 'Movimiento en el banquillo. {desc}', 'Cambio. {desc}'],
            A: ['Frescura para {eq}: el técnico busca cambiar el ritmo.', 'Un cambio que dice mucho de las intenciones del entrenador.', 'Veremos si el que entra aporta desde el primer toque.'],
            I: ['Entrar de cambio es un reto: tienes que meterte en el partido en segundos.'],
        },
        dt: {
            N: ['{desc}', 'Desde la banda. {desc}'],
            A: ['El técnico mueve las piezas; se nota que no le gusta lo que ve.', 'Los ajustes desde el banquillo pueden cambiar la dinámica.'],
            I: ['Cuando el técnico grita así, todos en la cancha lo escuchan y lo sienten.'],
        },
        atajada: {
            N: ['{desc}', '¡Qué intervención! {desc}', '¡Salvó a su equipo! {desc}'],
            A: ['Pura reacción: ahí se ve la diferencia entre un buen portero y uno grande.', 'Buena lectura defensiva, cerró los espacios justo a tiempo.', '{eq} sigue firme atrás.'],
            I: ['Eso es lo que más duele a un delantero: estaba dentro y aparece una mano.', 'Esas atajadas levantan al equipo entero.'],
        },
        remate: {
            N: ['{desc}', '{desc} ¡Por poco!', 'Se le fue por centímetros. {desc}'],
            A: ['Tuvo el ángulo, pero faltó precisión: ahí hay que afinar la puntería.', '{eq} está llegando, el gol está cerca.', 'La presión de {eq} va creciendo.'],
            I: ['Lo que más duele es fallar así; se queda dando vueltas en la cabeza.', 'Ya llegará; lo importante es seguir insistiendo.'],
        },
        error: {
            N: ['{desc}', '¡Qué susto! {desc}'],
            A: ['Un error así se paga caro; por suerte no pasó a mayores.', 'La concentración lo es todo: un segundo de duda y se cae todo.'],
            I: ['Todos hemos tenido un momento así; hay que seguir sin pensarlo.'],
        },
        corner: {
            N: ['{desc}', 'Tiro de esquina. {desc}'],
            A: ['Los córners son oro: una pelota parada y todo puede cambiar.', 'Hay que cuidar los rebotes dentro del área.'],
            I: ['En los córners todo se decide por centímetros.'],
        },
        regate: {
            N: ['{desc}', '{desc} ¡Qué calidad!'],
            A: ['Habilidad pura en espacio corto; así se rompen defensas.', 'Cada vez que {j} la toca, la defensa de {rival} tiembla.'],
            I: ['Ese tipo de regate se entrena desde niño; no se improvisa.'],
        },
        falta: {
            N: ['{desc}', 'Silbato. {desc}'],
            A: ['Una falta táctica a tiempo corta el ritmo del rival.', 'Interrumpe el partido, pero ordena a {eq}.'],
            I: ['Esas faltas son parte del juego; mientras no pase de ahí...'],
        },
        offside: {
            N: ['{desc}', 'Bandera arriba. {desc}'],
            A: ['La línea de {rival} sube justo en el momento clave.', 'Fuera de lugar por muy poco; esos milímetros matan ataques.'],
            I: ['El tiempo exacto de arrancar lo es todo; unos centímetros y se acaba la jugada.'],
        },
        banda: { N: ['{desc}'], A: ['Se juega mucho por los costados.'], I: [] },
        robo: {
            N: ['{desc}', 'Cambia la posesión. {desc}'],
            A: ['Buena presión: recuperar alto desordena al rival.', 'La recuperación es el primer paso para atacar.'],
            I: ['Cuando el balón se recupera arriba, cambia todo.'],
        },
        preparacion: { N: ['{desc}', 'Atención. {desc}'], A: ['Se viene algo; ojo con esa jugada.'], I: [] },
        desgaste: {
            N: ['{desc}', 'El físico pasa factura. {desc}'],
            A: ['Con este ritmo las piernas pesan y los espacios se abren.', 'Los cambios van a ser clave si el cansancio sigue.'],
            I: [],
        },
        inicio: {
            N: ['¡Y se pone en marcha el partido! {desc}', '¡Rueda el balón! {desc}'],
            A: ['Atentos a cómo plantean los equipos estos primeros minutos.', 'Los primeros minutos son de tanteo; ambos quieren sentir el partido.'],
            I: ['Se siente la emoción desde aquí; qué ganas de ver jugar a estos dos equipos.'],
        },
        descanso: {
            N: ['{desc}', 'Se acaba el primer tiempo. {desc}'],
            A: ['Habrá mucho que ajustar en el vestuario.', 'Buen momento para recuperar el aliento y replantear.'],
            I: ['El descanso es oro: te hidratas, escuchas al técnico y vuelves distinto.'],
        },
        segundo: { N: ['{desc}', 'Arranca la segunda mitad. {desc}'], A: ['Veremos con qué ajustes sale cada técnico.'], I: [] },
        anadido: { N: ['{desc}', 'Atención al cartel. {desc}'], A: ['En el descuento todo se vale; el que quiere, gana.'], I: [] },
        extra: { N: ['Tiempo extra. {desc}', '{desc}'], A: ['Las piernas pesan ya: el que tenga más aire se llevará esto.'], I: [] },
        tanda: {
            N: ['¡Se viene la tanda de penales! {desc}', '{desc}'],
            A: ['Los nervios mandan en la tanda; no hay táctica que valga.'],
            I: ['La tanda se vive distinto desde adentro: es pura cabeza.'],
        },
        final: {
            N: ['{desc}', '¡Se acabó! {desc}'],
            A: ['Un partido que deja lecciones para ambos equipos.', 'Hay mucho que analizar de lo que se vio hoy.'],
            I: ['Respeto para los dos equipos; así es el fútbol.'],
        },
        saque: { N: ['{desc}'], A: [], I: [] },
        jugada: { N: ['{desc}'], A: ['Es un partido que se está jugando con mucha intensidad.'], I: [] },
    };

    // charla entre jugadas, cuando nadie ha hablado en un rato (siempre sin adelantar nada del resultado)
    const CHARLA = {
        N: ['Seguimos en {estadio}, con este {local} contra {visita}.', 'Va el minuto {min}: aquí no hay nada decidido.', '{local} y {visita} se miden con mucho respeto.',
            'Les recuerdo que están en vivo con nosotros en {estadio}.', 'Con el {marc} en el marcador, nadie se puede confiar.',
            'Sigue el partido entre {local} y {visita}, minuto {min}.'],
        A: ['Hay que fijarse en cómo se ordenan atrás: ahí se gana el partido.', 'El que domine el medio campo tendrá la última palabra.', 'Mucho ojo con las segundas jugadas.',
            'El ritmo está intenso: veremos quién aguanta mejor.', 'Los espacios entre líneas van a ser clave.', 'Con el {marc} en el marcador, el que se descuide la paga.'],
        I: ['Se siente la tensión desde aquí; es un partido para jugarlo con la cabeza fría.', 'Ojalá la afición se lleve un buen espectáculo.', 'Los partidos se deciden en los detalles.',
            'Desde la cancha, estos minutos se viven muy rápido.'],
        T: ['Todavía es temprano: nadie quiere arriesgar demasiado.'],            // minuto < 15
        L: ['Se acerca el cierre: cada balón pesa el doble.', 'Ya se juega con el reloj encima.'],   // minuto > 75
    };
    const RADIO_CHARLA = ['Aquí, desde la cabina, les seguimos contando este {local} contra {visita}.', 'Quien se una ahora: minuto {min}, y el partido sigue abierto.',
                          'Transmitimos en vivo para todos ustedes, desde {estadio}.', 'No se muevan de sintonía: esto sigue.'];

    // ---------------------------------------------------------------- utilidades de texto
    function apellido(nombre) {
        const partes = String(nombre || '').trim().split(/\s+/);
        return partes.length > 1 ? partes[partes.length - 1] : (partes[0] || '');
    }
    function limpiarDescripcion(texto) {
        let t = String(texto || '').replace(/\s*\([^)]*\)/g, '').replace(/\s+/g, ' ').trim();
        if (t.length > 112) {   // se lee en pantalla: la crónica entera es demasiado larga para un solo mensaje
            const corte = t.slice(0, 112);
            const punto = Math.max(corte.lastIndexOf('. '), corte.lastIndexOf('! '), corte.lastIndexOf('? '));
            t = punto > 38 ? corte.slice(0, punto + 1) : corte.replace(/\s+\S*$/, '') + '…';
        }
        return t;
    }
    function rellenar(plantilla, datos) {
        let vacio = false;
        const texto = plantilla.replace(/\{(\w+)\}/g, (_, clave) => {
            const v = datos[clave];
            if (v === undefined || v === null || v === '') { vacio = true; return ''; }
            return v;
        });
        return vacio ? null : texto.replace(/\s+/g, ' ').trim();
    }

    // ---------------------------------------------------------------- despedida al terminar el partido
    // Se usa solo con lo ya revelado (el partido terminó): marcador, quién anotó y cuántos expulsados hubo.
    // {gan} ganador, {per} perdedor, {gg} goles del ganador, {gp} goles del perdedor, {figura} el goleador del partido, {n} sus goles.
    const DESPEDIDA = {
        resultado: {
            victoria: ['¡Y se acabó! {gan} se lleva el partido {gg}-{gp} ante {per}.', 'Final del partido: {gan} gana {gg} a {gp} y se queda con los tres puntos.',
                       'Termina el partido en {estadio}: {gan} {gg}, {per} {gp}.'],
            goleada: ['¡Paliza en {estadio}! {gan} golea {gg}-{gp} a {per}.', 'Se acabó, y fue una goleada: {gan} {gg}, {per} {gp}.', '¡Qué manera de ganar! {gan} arrasa a {per} por {gg}-{gp}.'],
            empate: ['Se acabó: {local} y {visita} empatan {gg}-{gp} y se reparten los puntos.', 'Final del partido en {estadio}: {local} {gg}, {visita} {gp}. Todo igual.',
                     'Termina igualado el partido: {local} {gg} - {gp} {visita}.'],
            vacio: ['Se acabó el partido: {local} y {visita} empatan sin goles.', 'Cero a cero en {estadio}: un partido de mucho cuidado en las áreas.'],
        },
        analisis: {
            figura: ['Para mí la figura fue {figura}, que {golesTxt}.', 'Hay que destacar a {figura}: {golesTxt} y marcó la diferencia.'],
            victoria: ['{gan} lo ganó con orden y paciencia: se llevó los puntos por detalles.', 'Un resultado que premia a {gan}, que supo aprovechar mejor sus momentos.',
                       '{per} tuvo sus opciones, pero le faltó contundencia.'],
            goleada: ['El marcador habla solo: {gan} fue muy superior en todas las líneas.', '{per} nunca encontró cómo frenar a {gan}; una tarde para olvidar.'],
            empate: ['Un empate justo: ninguno quiso arriesgar de más y los dos se llevan algo.', 'Se repartieron los puntos y ninguno puede quejarse demasiado.',
                     'Un partido parejo que se pudo haber inclinado para cualquiera.'],
            vacio: ['Dos defensas sólidas y poca claridad arriba: así se explica el cero a cero.'],
            roja: ['Y no podemos olvidar que hubo {rojas} expulsado{s}: eso condicionó el partido.'],
        },
        invitado: ['Quiero darles las gracias por invitarme; ha sido un placer comentar este partido con ustedes.', 'Muchas gracias por la invitación, fue una experiencia increíble verlo desde aquí.',
                   'Gracias a todos los que nos vieron; para mí es un honor estar en esta mesa.'],
        gracias: ['Gracias a todos por acompañarnos durante este partido.', 'Muchas gracias a quienes nos siguieron hasta el último minuto.', 'Un agradecimiento enorme a quienes estuvieron con nosotros en esta transmisión.'],
        adios: ['Con esto nos despedimos desde {cadena}. ¡Hasta la próxima transmisión!', 'Esto fue todo desde {cadena}. ¡Nos vemos en el próximo partido, hasta pronto!',
                'Nos despedimos de ustedes desde {cadena}: ¡cuídense mucho y hasta la próxima!'],
        adiosAnalista: ['¡Hasta la próxima, amigos!', 'Nos vemos en el próximo partido, ¡un abrazo!', 'Gracias, y que sigan disfrutando del fútbol. ¡Adiós!'],
        radio: ['Y con esto termina nuestra transmisión. Gracias por sintonizarnos, ¡hasta la próxima!', 'Se acaba la emisión: gracias por su compañía, ¡nos escuchamos en el próximo partido!',
                'Hasta aquí llegamos desde la cabina. Gracias por acompañarnos y hasta pronto.'],
    };
    /** Resumen del partido terminado a partir de los eventos revelados: marcador, ganador, goleadores y expulsados. */
    function resumen(data) {
        const eventos = (data && data.eventos) || [];
        const gl = data.goles_local || 0, gv = data.goles_visitante || 0;
        const goleadores = {};
        let rojas = 0;
        eventos.forEach(ev => {
            const c = clasificar(ev);
            if (c === 'gol' && (ev.tipo || '').indexOf('TANDA') < 0 && (ev.tipo || '').indexOf('GOL DE PENAL') < 0 && (ev.jugadores || [])[0]) {
                const nombre = ev.jugadores[0]; goleadores[nombre] = (goleadores[nombre] || { nombre, equipo: ev.equipo, n: 0 }); goleadores[nombre].n++;
            }
            if (c === 'roja') rojas++;
        });
        const lista = Object.values(goleadores).sort((a, b) => b.n - a.n);
        const gana = gl > gv ? 'local' : (gv > gl ? 'visitante' : null);
        return { local: data.local, visitante: data.visitante, gl, gv, ganador: gana ? (gana === 'local' ? data.local : data.visitante) : null,
                 perdedor: gana ? (gana === 'local' ? data.visitante : data.local) : null, gg: Math.max(gl, gv), gp: Math.min(gl, gv),
                 diferencia: Math.abs(gl - gv), figura: lista[0] && lista[0].n >= 1 ? lista[0] : null, rojas, estadio: data.estadio };
    }

    // ---------------------------------------------------------------- el narrador de un partido
    /**
     * opciones: { matchId, local, visitante, idLocal, idVisita, estadio, modo: 'tv'|'radio', mesas: [{tele:{pais_id}, comentaristas, invitado}] }
     * proponer(evento, indice, ctx) -> [{mesa, rol, texto, retraso, duracion, prio, efecto, equipoEfecto}]
     *   ctx: { marcador: '1-0' | '', minuto, goles?: {local, visitante} }
     * charla(ctx, mesa) -> una intervención de relleno (o null)
     */
    function crear(opciones) {
        const o = Object.assign({ modo: 'radio', mesas: [] }, opciones);
        const mesas = o.modo === 'tv' ? o.mesas : [];
        const recientes = [];            // plantillas usadas hace poco (no se repiten)
        const ultimos = mesas.length ? mesas.map(() => []) : [[]];   // últimos hablantes por mesa
        let contadorCharla = 0;

        function recordarPlantilla(id) { recientes.push(id); if (recientes.length > 14) recientes.shift(); }

        function elegirPlantilla(pool, clave, rng, datos) {
            const candidatas = [];
            pool.forEach((plantilla, i) => {
                const id = clave + ':' + i;
                if (recientes.includes(id)) return;
                const texto = rellenar(plantilla, datos);
                if (texto) candidatas.push({ id, texto });
            });
            if (!candidatas.length) return null;
            const elegida = candidatas[Math.floor(rng() * candidatas.length)];
            recordarPlantilla(elegida.id);
            return elegida.texto;
        }

        // quién habla en esta mesa para un rol de la cadena (N narrador, A analista, I invitado)
        function hablante(mesaIdx, codigo) {
            if (o.modo !== 'tv') return 'radio';
            const mesa = mesas[mesaIdx] || {};
            if (codigo === 'I') return mesa.invitado ? 'invitado' : 'analista';
            return codigo === 'A' ? 'analista' : 'narrador';
        }
        function evitarRepetir(mesaIdx, rol, rng) {
            const hist = ultimos[mesaIdx] || (ultimos[mesaIdx] = []);
            if (o.modo === 'tv' && hist.length >= 2 && hist[hist.length - 1] === rol && hist[hist.length - 2] === rol) {
                const alternos = ['narrador', 'analista'].concat(mesas[mesaIdx] && mesas[mesaIdx].invitado ? ['invitado'] : []).filter(r => r !== rol);
                return alternos[Math.floor(rng() * alternos.length)];
            }
            return rol;
        }
        function registrar(mesaIdx, rol) {
            const hist = ultimos[mesaIdx] || (ultimos[mesaIdx] = []);
            hist.push(rol); if (hist.length > 4) hist.shift();
        }
        function duracion(texto) { return Math.min(5400, Math.max(2400, 2000 + texto.length * 34)); }

        function mesaDelEvento(evento, rng) {
            if (mesas.length <= 1) return 0;
            const equipoId = evento.equipo === o.local ? o.idLocal : (evento.equipo === o.visitante ? o.idVisita : null);
            const propia = mesas.findIndex(m => m.tele && equipoId != null && m.tele.pais_id === equipoId);
            return propia >= 0 ? propia : Math.floor(rng() * mesas.length);
        }

        function cadenaParaMesa(evento, clase, cfg, indice, mesaIdx, rng, ctx, soloReaccion) {
            const jugadores = evento.jugadores || [];
            const equipo = evento.equipo;
            const esLocal = equipo === o.local;
            const equipoEvento = (equipo === o.local || equipo === o.visitante) ? equipo : null;
            const rival = equipoEvento ? (esLocal ? o.visitante : o.local) : null;
            const datos = {
                desc: limpiarDescripcion(evento.descripcion), j: apellido(jugadores[0]), j2: apellido(jugadores[1]),
                eq: equipoEvento, rival, min: ctx.minuto, marc: ctx.marcador, local: o.local, visita: o.visitante, estadio: o.estadio,
            };
            const salida = [];
            const pasos = soloReaccion ? ['A:0.9'] : cfg.cadena;
            let retraso = 250 + Math.floor(rng() * 300);
            pasos.forEach((paso, k) => {
                const [codigo, prob] = paso.split(':');
                if (prob && rng() > parseFloat(prob)) return;
                const pool = (FRASES[clase] || {})[codigo] || [];
                if (!pool.length) return;
                // en la radio no hay invitado: su comentario lo dice la misma voz
                const texto = elegirPlantilla(pool, `${clase}:${codigo}`, rng, datos);
                if (!texto) return;
                const rol = evitarRepetir(mesaIdx, hablante(mesaIdx, codigo), rng);
                registrar(mesaIdx, rol);
                // `paso` ordena la cadena; solo el primero espera un poco (los demás entran en cuanto termina el anterior)
                salida.push({
                    mesa: mesaIdx, rol, texto, retraso: salida.length ? 350 : retraso, duracion: duracion(texto), prio: cfg.prio, paso: salida.length,
                    efecto: k === 0 && !soloReaccion ? (cfg.efecto || null) : null, equipoEfecto: equipoEvento, evento: indice,
                });
            });
            return salida;
        }

        function proponer(evento, indice, ctx) {
            ctx = ctx || {};
            const clase = clasificar(evento);
            const cfg = CLASES[clase] || CLASES.jugada;
            const rng = azar(`${o.matchId}:${indice}`);
            if (rng() > cfg.p) return [];
            const principal = mesaDelEvento(evento, rng);
            let salida = cadenaParaMesa(evento, clase, cfg, indice, principal, rng, ctx, false);
            // la otra cadena (si hay dos) reacciona corto en jugadas importantes
            if (mesas.length > 1 && cfg.prio >= 2 && rng() < 0.4) {
                const otra = (principal + 1) % mesas.length;
                salida = salida.concat(cadenaParaMesa(evento, clase, cfg, indice, otra, rng, ctx, true));
            }
            return salida;
        }

        function charla(ctx, mesaIdx) {
            ctx = ctx || {};
            mesaIdx = mesaIdx || 0;
            const rng = azar(`${o.matchId}:charla:${contadorCharla++}`);
            const datos = { min: ctx.minuto, marc: ctx.marcador, local: o.local, visita: o.visitante, estadio: o.estadio };
            const minuto = parseInt(ctx.minuto, 10);
            let codigo = o.modo === 'tv' ? ['N', 'A', 'A', 'I'][Math.floor(rng() * 4)] : 'N';
            if (codigo === 'I' && !(mesas[mesaIdx] && mesas[mesaIdx].invitado)) codigo = 'A';
            let pool = CHARLA[codigo];
            if (!isNaN(minuto) && minuto < 15 && rng() < 0.4) pool = CHARLA.T;
            else if (!isNaN(minuto) && minuto > 75 && rng() < 0.4) pool = CHARLA.L;
            else if (o.modo === 'radio' && rng() < 0.4) pool = RADIO_CHARLA;
            const texto = elegirPlantilla(pool, `charla:${codigo}`, rng, datos);
            if (!texto) return null;
            const rol = evitarRepetir(mesaIdx, hablante(mesaIdx, codigo), rng);
            registrar(mesaIdx, rol);
            return { mesa: mesaIdx, rol, texto, retraso: 0, duracion: duracion(texto), prio: 0, paso: 0, efecto: null, equipoEfecto: null, evento: -1 };
        }

        /**
         * La despedida de una mesa (o de la radio): el narrador cierra el marcador, el analista comenta cómo fue el partido, el invitado
         * agradece y el narrador se despide. Devuelve intervenciones con `cierre: true` en la última. resumen = Narracion.resumen(data).
         */
        function despedida(res, mesaIdx) {
            mesaIdx = mesaIdx || 0;
            const rng = azar(`${o.matchId}:fin:${mesaIdx}`);
            const mesa = mesas[mesaIdx] || {};
            const cadena = (mesa.tele && mesa.tele.nombre) || '';
            const tipo = res.ganador ? (res.diferencia >= 3 ? 'goleada' : 'victoria') : (res.gg === 0 ? 'vacio' : 'empate');
            const datos = { gan: res.ganador, per: res.perdedor, gg: res.gg, gp: res.gp, local: res.local, visita: res.visitante, estadio: res.estadio, cadena,
                            figura: res.figura && apellido(res.figura.nombre), n: res.figura && res.figura.n, rojas: res.rojas, s: res.rojas > 1 ? 's' : '',
                            golesTxt: res.figura && (res.figura.n > 1 ? `anotó ${res.figura.n} goles` : 'anotó el gol') };
            const lineas = [];
            const pon = (rol, pool, clave) => {
                const texto = elegirPlantilla(pool, 'fin:' + clave, rng, datos);
                if (texto) lineas.push({ mesa: mesaIdx, rol, texto, retraso: lineas.length ? 350 : 700, duracion: duracion(texto) + 600, prio: 3, paso: lineas.length ? 1 : 0, efecto: null, equipoEfecto: null, evento: -1 });
            };
            if (o.modo !== 'tv') {
                pon('radio', DESPEDIDA.resultado[tipo], 'r');
                pon('radio', res.figura && rng() < 0.7 ? DESPEDIDA.analisis.figura : DESPEDIDA.analisis[tipo], 'a');
                pon('radio', DESPEDIDA.radio, 'x');
            } else {
                const tieneInvitado = !!mesa.invitado;
                pon('narrador', DESPEDIDA.resultado[tipo], 'r');
                pon('analista', res.figura && rng() < 0.7 ? DESPEDIDA.analisis.figura : DESPEDIDA.analisis[tipo], 'a');
                if (res.rojas && rng() < 0.6) pon('analista', DESPEDIDA.analisis.roja, 'ro');
                if (tieneInvitado) pon('invitado', DESPEDIDA.invitado, 'i');
                pon('analista', DESPEDIDA.gracias, 'g');
                pon('narrador', DESPEDIDA.adios, 'x');
                if (!tieneInvitado || rng() < 0.6) pon('analista', DESPEDIDA.adiosAnalista, 'y');
            }
            if (lineas.length) lineas[lineas.length - 1].cierre = true;
            return lineas;
        }

        return { proponer, charla, despedida, modo: o.modo, mesas: mesas.length };
    }

    // ---------------------------------------------------------------- gráficos de transmisión (tarjetas de jugador)
    // Solo las jugadas verdaderamente importantes llevan tarjeta, como en una transmisión de TV: gol, amonestado, expulsado y el
    // portero que ataja un penal. Orden de los nombres en `evento.jugadores` (lo deja el motor): gol [goleador, portero, asistente];
    // amarilla [amonestado, rival]; roja y doble amarilla [expulsado]; penal fallado [portero, tirador].
    const GOLES_TIPO = { 'GOL DE TIRO LIBRE': 'de tiro libre', 'GOL DE CÓRNER': 'de córner' };
    function grafico(evento, indice, eventos) {
        const tipo = (evento && evento.tipo) || '';
        const j = (evento && evento.jugadores) || [];
        if (!j.length) return null;
        const clase = clasificar(evento);
        const base = { evento: indice, jugador: j[0], equipo: evento.equipo || null, minuto: evento.minuto };
        if (clase === 'gol' && !tipo.includes('TANDA') && tipo.indexOf('GOL DE PENAL') < 0) {
            const previos = (eventos || []).slice(0, indice + 1).filter(e => clasificar(e) === 'gol' && ((e.jugadores || [])[0] === j[0])).length;
            let tipoGol = evento.de_penal ? 'de penal' : null;
            for (const [frag, texto] of Object.entries(GOLES_TIPO)) if (tipo.includes(frag)) tipoGol = texto;
            return Object.assign(base, { accion: 'gol', titulo: tipoGol ? `GOL ${tipoGol.toUpperCase()}` : 'GOL', portero: j[1] || null, asistente: j[2] || null, nGol: previos, prio: 3 });
        }
        if (tipo.includes('DOBLE AMARILLA')) return Object.assign(base, { accion: 'roja', titulo: 'EXPULSADO', motivo: 'Segunda amarilla', prio: 3 });
        if (tipo.includes('TARJETA ROJA')) return Object.assign(base, { accion: 'roja', titulo: 'EXPULSADO', motivo: 'Roja directa', prio: 3 });
        if (tipo.includes('TARJETA AMARILLA')) return Object.assign(base, { accion: 'amarilla', titulo: 'AMONESTADO', rival: j[1] || null, prio: 2 });
        if (tipo.includes('PENAL FALLADO') && j.length >= 2) return Object.assign(base, { accion: 'atajo', titulo: '¡ATAJÓ EL PENAL!', tirador: j[1], prio: 3 });
        return null;
    }
    const POSICIONES = { POR: 'Portero', DFI: 'Defensa', DFD: 'Defensa', LI: 'Lateral', LD: 'Lateral', MI: 'Mediocampista', MC: 'Mediocampista', MD: 'Mediocampista',
                         EI: 'Extremo', DC: 'Delantero', ED: 'Extremo' };
    // la línea de tiempo de una jugada para el gráfico del marcador (estadio + marcador + logo de la cadena): ¿toca uno?
    // `clase` de la jugada actual y `desde` = ms desde el último; en los hitos siempre (arranque, descanso, final).
    function tocaMarcador(clase, desde, azarFn) {
        if (clase === 'inicio' || clase === 'descanso' || clase === 'final') return true;
        if (desde < 150000) return false;                       // nunca dos seguidos: al menos 2,5 minutos entre uno y otro
        const p = Math.min(0.5, (desde - 150000) / 600000 + 0.05);   // de 5 % a 50 % según lleve sin salir
        return (azarFn || Math.random)() < p;
    }

    const api = { crear, clasificar, grafico, resumen, POSICIONES, tocaMarcador, apellido, limpiarDescripcion, rellenar, azar, CLASES, FRASES, CHARLA };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    root.Narracion = api;
})(typeof window !== 'undefined' ? window : globalThis);
