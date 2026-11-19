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
        ['TANDA DE PENALTIS', 'tanda'], ['SEGUNDO TIEMPO EXTRA', 'segextra'],
        ['ANULADO', 'var'], ['VAR', 'var'],
        ['GOL DE PENAL', 'tandagol'],
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
        // en la tanda de penales (periodo 5) cada cobro tiene sus propias frases: no es un penal señalado en juego
        if (evento && evento.periodo === 5) {
            if (tipo.includes('PENAL FALLADO')) return 'tandafallo';
            if (tipo.includes('PREPARACIÓN')) return 'tandaprep';
        }
        // la PREPARACIÓN de un tiro libre o de un penal en juego (antes de saber si es gol): momento de suspenso propio
        if (tipo.includes('PREPARACIÓN') && evento && evento.periodo !== 5) {
            const desc = evento.descripcion || '';
            if (/punto penal/i.test(desc)) return 'penalcobro';
            if (/punto de tiro libre|ordena la barrera/i.test(desc)) return 'tirolibre';
            if (/córner se mece|toma posición en el área para el centro/i.test(desc)) return 'cornercobro';
        }
        for (const [fragmento, clase] of TIPOS) if (tipo.includes(fragmento)) return clase;
        return 'jugada';
    }

    // p = probabilidad de que la jugada se comente; prio = importancia (3 = nunca se descarta); cadena = quién habla y en qué orden
    // (rol[:probabilidad]); efecto = destello en pantalla; solo para goles, tarjetas y VAR.
    const CLASES = {
        gol:        { p: 1.0,  prio: 3, cadena: ['N', 'A', 'I:0.8'], efecto: 'gol' },
        penal:      { p: 1.0,  prio: 3, cadena: ['N', 'A:0.8', 'I:0.5'], efecto: 'penal' },
        // el instante ANTES del desenlace: el jugador se perfila y todavía no se sabe si será gol (siempre se narra, con suspenso)
        penalcobro: { p: 1.0,  prio: 3, cadena: ['N', 'A:0.85', 'I:0.5'] },
        tirolibre:  { p: 1.0,  prio: 2, cadena: ['N', 'A:0.75', 'I:0.4'] },
        roja:       { p: 1.0,  prio: 3, cadena: ['N', 'A', 'I:0.5'], efecto: 'roja' },
        amarilla:   { p: 0.95, prio: 2, cadena: ['N', 'A:0.55'], efecto: 'amarilla' },
        var:        { p: 1.0,  prio: 3, cadena: ['N', 'A:0.7'], efecto: 'var' },
        lesion:     { p: 0.9,  prio: 2, cadena: ['N', 'A:0.6'] },
        cambio:     { p: 0.6,  prio: 1, cadena: ['N:0.7', 'A:0.6'] },
        dt:         { p: 0.5,  prio: 1, cadena: ['N:0.6', 'A:0.6'] },
        // el desenlace de un disparo (atajada, desviado, bloqueado, córner) SIEMPRE se narra: si no, la jugada queda a medias (preparación o gol sí, pero qué pasó con el tiro no)
        atajada:    { p: 1.0,  prio: 2, cadena: ['N', 'A:0.45', 'I:0.3'] },
        remate:     { p: 1.0,  prio: 2, cadena: ['N', 'A:0.4', 'I:0.25'] },
        error:      { p: 0.8,  prio: 2, cadena: ['N', 'A:0.5'] },
        // el tiro de esquina: se anuncia con suspenso y, cuando el balón va al área, se narra el cabezazo antes del desenlace
        corner:     { p: 1.0,  prio: 2, cadena: ['N', 'A:0.7', 'I:0.4'] },
        cornercobro: { p: 1.0, prio: 1, cadena: ['N', 'A:0.6'] },
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
        segextra:   { p: 1.0,  prio: 3, cadena: ['N', 'A:0.8'] },
        tandaprep:  { p: 0.85, prio: 2, cadena: ['N', 'A:0.3'] },
        tandagol:   { p: 1.0,  prio: 3, cadena: ['N', 'A:0.8', 'I:0.5'] },
        tandafallo: { p: 1.0,  prio: 3, cadena: ['N', 'A:0.85', 'I:0.55'] },
        saque:      { p: 0.2,  prio: 0, cadena: ['N'] },
        jugada:     { p: 0.2,  prio: 0, cadena: ['N', 'A:0.4'] },
    };

    // ---------------------------------------------------------------- frases
    // Marcadores: {desc} lo que cuenta la jugada, {j} {j2} jugadores (apellido), {eq} equipo de la jugada, {rival}, {min},
    // {marc} marcador del momento, {local} {visita} {estadio}. Una frase con un marcador sin valor no se usa.
    const FRASES = {
        gol: {
            N: ['¡GOOOOL! {desc}', '¡Y ES GOL! {desc}', '¡Aaaahí está! {desc}', '{desc} ¡Qué manera de celebrar, {eq}!', '¡Se abre el grito de gol para {eq}! {desc}', '¡Gol, gol, gol! {desc}', '¡Y no lo puede creer la afición! {desc}', '¡Se estremece el estadio! {desc}'],
            A: ['Ahí marcó la diferencia: {j} supo leer el momento y {eq} lo aprovechó.', 'Fíjate en el movimiento previo: la defensa de {rival} llegó tarde.',
                'Gol que cambia el planteamiento: ahora {rival} tendrá que salir a buscarlo.', 'Eso viene de una jugada bien trabajada, {eq} lo tenía en la cabeza.',
                '{marc} en el marcador: {eq} se lo había ganado con la presión.'],
            I: ['¡Qué golazo! Esa sensación de ver entrar el balón no se compara con nada.', 'Cuando {j} agarra confianza, es difícil frenarlo.',
                'Uf, yo ahí hubiera gritado igual. ¡Qué definición!', 'Un gol así mueve a todo el vestuario; {eq} va a salir con otra cara.',
                'Ojo con {rival}: después de un gol así, lo difícil es levantar la cabeza.', 'Desde la banca se vive distinto, pero lo bonito es ver cómo se une el equipo para celebrar.', 'Un gol así se construye con varios toques; el que lo remata solo pone la firma.'],
        },
        penal: {
            N: ['{desc}', '¡Pena máxima! {desc}', '¡El árbitro señala el punto penal! {desc}', '¡El árbitro no lo duda! {desc}', 'Silbato y a señalar el punto blanco. {desc}'],
            A: ['Hay contacto claro, no hay mucho que protestar.', 'Un penal siempre es una moneda al aire para el portero.', 'Aquí pesan los nervios, del que cobra y del que lo espera.'],
            I: ['Cobrar un penal es otra cosa: las piernas pesan el doble.', 'Yo me quedo con el que cobra: tiene el partido entero en la cabeza.', 'Dicen que es fácil, hasta que te toca patearlo.', 'Más que técnica, es temple: nadie quiere ser el que falle.'],
        },
        penalcobro: {
            N: ['Silencio en el estadio... {j} acomoda el balón en el punto penal. ¿Gol o atajada?', '{j} toma carrera... ¡y cobra!', 'Todo se detiene: {j} frente al balón, el portero esperando. ¿Qué pasará?',
                'Respira hondo {j}, mira al portero... ¡va a cobrar!', '{desc} ¡Y ejecuta!', 'Es el momento de la verdad para {j}. Dos pasos... ¡y dispara!'],
            A: ['Aquí se define con la cabeza: {j} tiene el partido en los pies.', 'El portero elige un lado y reza; {j} elige el otro. ¿Quién acierta?', 'Cada segundo que pasa pesa más; el que cobra lo sabe.',
                'Un penal es una moneda al aire con mucha presión encima.'],
            I: ['Yo desde acá siento los nervios; ese camino al punto penal se hace eterno.', 'Hay que tener personalidad para pararse ahí con todo el estadio mirando.', 'Qué silencio... a mí me temblarían las piernas.'],
        },
        tirolibre: {
            N: ['Tiro libre en posición peligrosa: {j} se perfila... ¿gol o barrera?', '{desc} ¡Cuidado, que viene el disparo!', '{j} mide los pasos, el árbitro ordena la barrera... ¿qué hará?',
                'Atención al balón parado: {j} se prepara para cobrar. ¡Todo puede pasar!', 'Se hace el silencio: {j} frente a la pelota quieta... ¡y va a cobrar!'],
            A: ['Con la barrera así, {j} tiene que elegir entre colocarla o ir por la fuerza.', 'El portero de {rival} tiene que adivinar hacia dónde: ahí se decide.', 'Balón parado y todo por decidir: una de esas jugadas que levantan al estadio.',
                'Un tiro libre así vale oro; basta una buena ejecución para cambiar el partido.'],
            I: ['Cobrar un tiro libre es otra cosa: tienes que confiar en tu pierna sin pensarlo.', 'La barrera, el portero, el balón... y un segundo para decidir.'],
        },
        roja: {
            N: ['{desc}', '¡Tarjeta roja! {desc}', '¡Se complica todo para {eq}! {desc}', '¡Y se va expulsado! {desc}', 'El árbitro no lo piensa dos veces. {desc}'],
            A: ['Con uno menos, {eq} tiene que replantearlo todo: líneas más juntas y menos riesgo.', 'Esto cambia el partido por completo; {rival} puede cargar con espacios.', 'Una decisión que le cuesta carísimo a {eq}.'],
            I: ['Es lo peor que le puede pasar a un equipo: los compañeros tienen que correr por dos.', 'Desde adentro se siente cómo el equipo se queda callado un segundo.', 'Se pierde la cabeza en un segundo y se paga el resto del partido.', 'Hay que reconocer que el árbitro lo vio de frente; no hay mucho margen en esa jugada.'],
        },
        amarilla: {
            N: ['{desc}', '{desc} Ojo con esa advertencia.', 'Amonestación. {desc}', 'El árbitro saca la cartulina. {desc}', 'Advertencia para el jugador. {desc}'],
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
            N: ['{desc}', '¡Qué intervención! {desc}', '¡Salvó a su equipo! {desc}', '¡Se estira y la saca! {desc}', '¡Mano salvadora! {desc}'],
            A: ['Pura reacción: ahí se ve la diferencia entre un buen portero y uno grande.', 'Buena lectura defensiva, cerró los espacios justo a tiempo.', '{eq} sigue firme atrás.'],
            I: ['Eso es lo que más duele a un delantero: estaba dentro y aparece una mano.', 'Esas atajadas levantan al equipo entero.', 'La clave está en el posicionamiento: si el portero llega bien parado, la mitad del trabajo está hecha.'],
        },
        remate: {
            N: ['{desc}', '{desc} ¡Por poco!', 'Se le fue por centímetros. {desc}', '¡Casi! {desc}', '¡Qué cerca estuvo! {desc}'],
            A: ['Tuvo el ángulo, pero faltó precisión: ahí hay que afinar la puntería.', '{eq} está llegando, el gol está cerca.', 'La presión de {eq} va creciendo.'],
            I: ['Lo que más duele es fallar así; se queda dando vueltas en la cabeza.', 'Ya llegará; lo importante es seguir insistiendo.', 'Es difícil definir con el arco enfrente y la presión encima; hay que reconocer el intento.'],
        },
        error: {
            N: ['{desc}', '¡Qué susto! {desc}'],
            A: ['Un error así se paga caro; por suerte no pasó a mayores.', 'La concentración lo es todo: un segundo de duda y se cae todo.'],
            I: ['Todos hemos tenido un momento así; hay que seguir sin pensarlo.'],
        },
        corner: {
            N: ['Tiro de esquina para {eq}: el balón al área... ¿gol de cabeza?', '{desc} ¡Atención al área, que viene el centro!', 'Córner para {eq}: se aglomeran en el área, ¿qué pasará?',
                'Se prepara el tiro de esquina de {eq}... todos arriba, incluso los defensas.', 'Tiro de esquina. {desc}'],
            A: ['Un córner así es una oportunidad de oro: basta un cabezazo.', 'Los córners son oro: una pelota parada y todo puede cambiar.', 'Hay que cuidar los rebotes dentro del área.'],
            I: ['En los córners todo se decide por centímetros.', 'Desde adentro, esos segundos antes del centro se hacen eternos.'],
        },
        cornercobro: {
            N: ['Sale el centro... {j} se eleva entre los defensas. ¿Será gol?', 'El córner viaja al área y {j} busca el remate... ¡atención!', '{desc} ¡Ahí viene el balón!', 'Todos mirando al cielo: {j} sube a buscar el balón.'],
            A: ['Mucha gente en el área: gana el que tenga más hambre.', 'Un cabezazo y se acaba la espera.'],
            I: [],
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
        segextra: {
            N: ['{desc}', 'Arranca la segunda parte del tiempo extra. {desc}', 'Se reanuda la prórroga. {desc}'],
            A: ['Quedan quince minutos: ya no se piensa en la táctica, se piensa en no fallar.', 'Con las piernas cargadas, un error o un chispazo lo cambia todo.'],
            I: ['Aquí el cuerpo ya no responde; manda la cabeza y el corazón.'],
        },
        // tanda de penales: {tlinea} la tanda hasta ahora, {j} el tirador (o el portero en `tandafallo`), {j2} el tirador en `tandafallo`
        tandaprep: {
            N: ['{desc}', 'Silencio en el estadio. {desc}', 'El balón en el punto penal. {desc}'],
            A: ['Todo está en la cabeza del que cobra; la técnica ya no importa.', 'El portero tiene que elegir un lado y confiar.'],
            I: [],
        },
        tandaprep_subita: {
            N: ['¡Muerte súbita! El que falle, pierde. {desc}', 'Seguimos en la muerte súbita: cada cobro lo puede definir todo. {desc}', '{desc} Aquí ya no hay margen de error.'],
            A: ['En la muerte súbita no se puede fallar: el que lo hace se va a casa.'],
            I: [],
        },
        tandagol: {
            N: ['¡GOOOL! {desc} {tlinea}.', '¡Adentro! {j} no perdona desde los once metros. {tlinea}.', '{desc} La tanda va {tlinea}.'],
            A: ['Mucha personalidad de {j} para cobrar así, sin dudar.', 'Eso da confianza a todo el equipo.', 'Se nota la sangre fría de {j}.'],
            I: ['Desde el punto penal se juega la cabeza: ese lo cobró muy tranquilo.', 'Cuando entras así, el equipo respira.'],
        },
        tandagol_subita: {
            N: ['¡GOL en la muerte súbita! {desc} {tlinea}.', '¡Lo convierte {j}! Ahora la presión pasa al otro lado. {tlinea}.'],
            A: ['La presión pasa al siguiente: ahora tiene que anotar sí o sí.'],
            I: ['Anotar en muerte súbita es lo más difícil: todo el peso cae sobre tus hombros.'],
        },
        tandagol_decide: {
            N: ['¡GOOOL y se acaba! {j} anota el penal decisivo: {ganaT} gana la tanda. {tlinea}.', '¡Se define! {desc} {ganaT} se impone en los penales. {tlinea}.'],
            A: ['Un cobro con mucha frialdad para cerrar la tanda.', 'Qué manera de definir una serie tan apretada.'],
            I: ['Ese es el penal más difícil de la vida: el que te da el pase. Qué tranquilidad.'],
        },
        tandafallo: {
            N: ['¡LO ATAJA {j}! Falla {j2}. {tlinea}.', '¡{j} se queda con el penal de {j2}! {tlinea}.', '{desc} La tanda va {tlinea}.'],
            A: ['El portero leyó el cobro desde antes de que patearan.', 'Un penal fallado en una tanda pesa el doble: queda en la cabeza de todos.'],
            I: ['Fallar un penal así es muy duro; el compañero que lo ataja se convierte en héroe.', 'Nadie quiere ser el que falle, pero le puede pasar a cualquiera.'],
        },
        tandafallo_subita: {
            N: ['¡LO ATAJA {j}! Falla {j2} en la muerte súbita. {tlinea}.', '{desc} En la muerte súbita, fallar pesa el doble. {tlinea}.'],
            A: ['En la muerte súbita un fallo es casi una sentencia.'],
            I: ['Cuando se falla en una muerte súbita, el silencio es lo más duro.'],
        },
        tandafallo_decide: {
            N: ['¡LO ATAJA {j}! ¡Y se acabó la tanda! {ganaT} gana en los penales. {tlinea}.', '¡Falla {j2} y {ganaT} se lleva la tanda! {tlinea}.'],
            A: ['Cruel: un penal fallado decide una serie que estuvo ajustadísima.'],
            I: ['Duele muchísimo perder así; el que falla carga esto años, aunque no sea su culpa.'],
        },
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
    // ---------------------------------------------------------------- voces con opinión (solo TV, cuando juega el país de la televisora)
    // El ANALISTA es del país de la cadena: comenta con pasión, a favor de los suyos (festeja, se queja del árbitro, se preocupa) según lo que
    // pasa y cómo va el marcador. El INVITADO (un jugador) complementa con una mirada objetiva y equilibrada, reconociendo mérito del rival.
    // Marcadores: {pais} el país de la cadena, {contra} su rival, {j} jugador de la jugada, {marc} marcador, {etapaTxt}.
    // Claves: `propio_*` = la jugada es de la selección de la cadena, `rival_*` = del rival; el sufijo (iguala/adelante/amplia/descuenta en los
    // goles; gana/pierde en lo demás) es la situación en el marcador, y sin sufijo es la frase general.
    const SUBJ = {
        gol: {
            A: {
                propio_adelante: ['¡Eso es, {pais}! ¡Se puso arriba y se lo merecía!', '¡Qué golazo de {j}! Aquí se nota la jerarquía de {pais}, que nadie lo dude.', '¡Así se juega! {pais} está en otro nivel hoy.', 'Se los dije: {pais} iba a encontrar el camino. ¡Ahora a cuidar la ventaja!'],
                propio_iguala: ['¡Aguanten, que {pais} nunca se rinde! Este empate es justicia.', '¡Merecidísimo! {pais} venía insistiendo y por fin llegó.', '¡Esa es la garra de {pais}! Ahora a por la remontada.'],
                propio_amplia: ['¡Esto ya es una fiesta! {pais} está desatado.', '¡Qué paliza le está dando {pais} a {contra}!', 'Con {marc} esto se encamina, pero ojo, {pais}: a no confiarse.'],
                propio_descuenta: ['¡Hay vida! {pais} descuenta y todavía se puede.', '¡Ese gol nos mete de nuevo en el partido! Ahora, a empujar.'],
                propio: ['¡Gol de {pais}! ¡Esto sí es fútbol!', '¡Qué alegría! {pais} sabe lo que hace.'],
                rival_adelante: ['Ay, no... {pais} se descuidó atrás, otra vez. Se veía venir.', 'Un golpe duro para {pais}; ahora toca levantar la cabeza.', 'Eso fue un regalo de la defensa, no puede ser.'],
                rival_iguala: ['Qué dolor: {pais} tenía el partido controlado y se le escapó la ventaja.', 'Nos empatan... {pais} tiene que reaccionar ya.'],
                rival_amplia: ['Esto se está complicando muchísimo para {pais}.', 'No es el día de {pais}, hay que reconocerlo, y duele.'],
                rival_descuenta: ['Nos recortan distancia: ¡cuidado, {pais}, que esto se puede poner feo!', 'Descuenta {contra} y ahora toca aguantar.'],
                rival: ['Gol de {contra}... duele, pero {pais} tiene tiempo para responder.', 'Qué golpe para los nuestros, qué golpe.'],
            },
            I: {
                propio_adelante: ['Siendo justos, el gol llega tras una buena circulación de {pais}.', 'Ojo: {contra} dejó espacios a la espalda y {pais} lo castigó.', 'Tiene mérito {j}, aunque {contra} todavía tiene partido.'],
                propio_iguala: ['Hay que reconocer que {contra} se había metido bien atrás; el empate llega por insistencia.', 'Un gol que se venía cocinando: {pais} había mejorado.'],
                propio_amplia: ['Con la ventaja, {contra} tiene que arriesgar, y eso abre espacios para los dos.', 'El gol es merecido, pero {contra} puede responder si se suelta.'],
                propio_descuenta: ['Es un gol que le da aire a {pais}, aunque todavía le falta bastante.', 'Importante para la confianza; ahora toca ordenarse bien.'],
                propio: ['Fue un gol bien trabajado; hay que reconocerlo.'],
                rival_adelante: ['Siendo objetivos, {contra} lo buscó y encontró el hueco: no solo fue un error de {pais}.', 'Una buena jugada de {contra}; hay que aplaudir lo bien hecho.'],
                rival_iguala: ['Es una consecuencia del ritmo del partido: los dos equipos están parejos.', 'Se veía venir: {contra} venía creciendo.'],
                rival_amplia: ['{contra} está más fino ahora mismo; {pais} tendrá que cambiar algo.', 'Es un resultado exigente, pero queda partido si {pais} se ordena.'],
                rival_descuenta: ['{pais} tiene que cerrar mejor: el partido no está definido.', 'Es un gol que reanima al rival; cuidado con la ansiedad.'],
                rival: ['Buen gol de {contra}; no hay mucho que reprochar.'],
            },
        },
        penal: {
            A: {
                propio_pierde: ['¡Es la oportunidad de {pais} para meterse en el partido!', 'Penal clarísimo, ¡y justo cuando más lo necesitábamos!'],
                propio_gana: ['Un penal para sentenciar... ojalá no lo desperdiciemos.'],
                propio: ['¡Penal clarísimo! Gracias, árbitro, por fin.', 'Eso es penal en cualquier cancha del mundo; {pais} lo merece.'],
                rival_pierde: ['¿Penal? Yo no vi nada... el árbitro nos perjudica, qué barbaridad.'],
                rival_gana: ['Con la ventaja que traía {pais}, ojalá el portero se luzca.'],
                rival: ['Ay, otra vez... a rezar para que el portero la ataje.', 'Hay que ser fuertes: esto puede cambiar el partido.'],
            },
            I: {
                propio: ['Hay contacto, es penal; ahora todo depende de la cabeza del que cobra.', 'Es una falta clara; el árbitro no tenía mucha duda.'],
                rival: ['Es una falta clara; no hay mucho que discutir, aunque duela.', 'El contacto está ahí; {pais} lo pagó con una desatención.'],
            },
        },
        roja: {
            A: {
                propio: ['¡Ay, no! Esa roja condiciona todo a {pais}; para mí el árbitro se pasó.', 'Qué mala suerte... con uno menos todo cuesta el doble.', 'Una expulsión que duele, y que {pais} pudo evitar.'],
                rival: ['¡Ahora sí! {contra} se quedó con uno menos y {pais} tiene que aprovecharlo.', 'Justísima; era lo mínimo por esa entrada.', 'Se lo buscaron: ahora {pais}, a cargar sin miedo.'],
            },
            I: {
                propio: ['Objetivamente, la entrada fue fuerte; el árbitro tenía poco margen.', 'Con uno menos hay que replegar y apostar a la contra.'],
                rival: ['Aun con uno más no hay que correr riesgos: {contra} puede cerrarse muy bien.', 'La superioridad numérica no gana sola: hay que saber moverla.'],
            },
        },
        amarilla: {
            A: {
                propio: ['Esa amarilla es pura protesta: el árbitro está muy tarjetero.', 'Tarjeta que no era, para mí. Ahora a cuidarse.'],
                rival: ['Bien, que se la muestren: venían entrando fuerte a {pais}.', 'Era amarilla: {contra} está jugando al límite.'],
            },
            I: { propio: ['Fue una entrada tarde; la amarilla es correcta.'], rival: ['Es una amonestación justa, sin dudas.'] },
        },
        atajada: {
            A: {
                propio_pierde: ['Gracias a esa mano seguimos vivos; {pais} todavía puede.'],
                propio: ['¡Qué portero tiene {pais}! Una muralla, de verdad.', '¡Se vistió de héroe! Eso levanta a todo el estadio.'],
                rival: ['¡Bah! {contra} tuvo suerte con su portero, ese gol de {pais} estaba cantado.', 'Hay que mejorar la puntería, {pais}, pero se está llegando.'],
            },
            I: { propio: ['Buena lectura del portero: se adelantó y achicó bien.'], rival: ['El portero rival respondió muy bien; no hay mucho que reprochar a {pais}.'] },
        },
        remate: {
            A: {
                propio_pierde: ['{pais} necesita ese gol ya: el tiempo corre.'],
                propio: ['¡Ahí estuvo! {pais} está muy cerca, el gol va a llegar.', 'Qué lástima, por centímetros... {pais} merece más.'],
                rival: ['Uff, cerca. Menos mal que {contra} falló.', 'Nos salvamos de milagro; hay que cerrar mejor.'],
            },
            I: { propio: ['Buen intento; falta afinar un poco la definición.'], rival: ['Pudo ser peligroso: la defensa de {pais} llegó justo.'] },
        },
        error: {
            A: { propio: ['Eso no se puede regalar, {pais}; un descuido así lo pagas caro.'], rival: ['¡Qué error de {contra}! {pais} tiene que aprovechar esas.'] },
            I: { propio: ['Son errores que pasan; lo importante es no darle más vueltas.'], rival: ['Un descuido que le puede costar caro a {contra}.'] },
        },
        var: {
            A: { propio: ['Esperemos que el VAR sea justo con {pais}.'], rival: ['Que revisen bien, que {contra} se está colando.'] },
            I: { propio: ['Hay que esperar con calma: la tecnología no se equivoca tanto.'], rival: ['Toca esperar; cualquiera de las dos decisiones tiene sentido.'] },
        },
        falta: {
            A: { propio: ['Esa falta no es de tarjeta, árbitro, déjelos jugar.'], rival: ['Eso es falta, y se la están perdonando a {contra}.'] },
            I: { propio: ['Fue una falta táctica, cortó la jugada a tiempo.'], rival: ['Una falta justa: así se frena un contragolpe.'] },
        },
        offside: {
            A: { propio: ['¡Eso no es fuera de lugar! ¡Mire bien, juez de línea!'], rival: ['Bien marcado: {contra} se estaba escapando.'] },
            I: { propio: ['Fue ajustadísimo; esos centímetros son difíciles de ver.'], rival: ['La línea de {pais} salió bien sincronizada.'] },
        },
        corner: {
            A: { propio: ['A ver si ahora sí: {pais} es peligroso en pelota parada.'], rival: ['Cuidado atrás, {pais}: marquen bien.'] },
            I: { propio: ['Una pelota parada bien ejecutada puede cambiar todo.'], rival: ['En los córners hay que estar muy concentrados.'] },
        },
        regate: {
            A: { propio: ['¡Qué calidad tiene {j}! Así se juega al fútbol.'], rival: ['Hay que estar atentos con ese jugador, nos hace daño.'] },
            I: { propio: ['Un regate que rompe líneas; eso da ventaja al equipo.'], rival: ['Es un jugador que desequilibra; la marca tiene que ser doble.'] },
        },
        cambio: {
            A: { propio: ['Ese cambio es la jugada del técnico; ojalá le salga bien a {pais}.'], rival: ['{contra} se está reforzando; ojo con los de refresco.'] },
            I: { propio: ['Un cambio que aporta piernas frescas; tiene lógica.'], rival: ['Un cambio que busca equilibrio; veremos si le da resultado.'] },
        },
    };
    SUBJ.tandagol = {
        A: { propio: ['¡Qué personalidad, {j}! ¡Así se cobra, {pais}!', '¡Gol de {pais}! ¡Qué sangre fría!'], rival: ['Ay, otro más para {contra}... {pais}, ahora te toca no fallar.', 'Convirtió bien {j}; ahora nos toca a nosotros.'] },
        I: { propio: ['Lo cobró muy bien; hay que reconocerle la tranquilidad.'], rival: ['Fue un buen cobro: no tuvo opción el portero de {pais}.'] },
    };
    SUBJ.tandafallo = {   // el evento es del equipo del PORTERO: `propio` = el portero de {pais} la atajó
        A: { propio: ['¡Qué portero tiene {pais}! ¡Esa mano vale una Copa!', '¡Se vistió de héroe! ¡Vamos, {pais}!'], rival: ['No puede ser... {pais} falló y ahora toca sufrir.', 'Qué dolor, qué dolor. Había que hacerlo mejor desde los once pasos.'] },
        I: { propio: ['Muy buena lectura del portero, merece el reconocimiento.'], rival: ['Un fallo así lo puede tener cualquiera; hay que seguir con la cabeza arriba.'] },
    };
    // lo que está en juego según la etapa (se usa de vez en cuando en las jugadas más importantes)
    const ETAPA = {
        knockout: {
            A: { propio: ['Aquí no hay mañana: {pais} se juega la vida.', 'En eliminación directa un momento así vale oro para {pais}.'], rival: ['En una llave así, cualquier error le cuesta el pase a {pais}.'] },
            I: { propio: ['En eliminación directa los detalles pesan el doble; hay que mantener la calma.'], rival: ['Para {contra} cada minuto cuenta si quiere avanzar.'] },
        },
        grupos: {
            A: { propio: ['Estos puntos pueden definir el grupo de {pais}.'], rival: ['Cuidado, que el grupo se le complica a {pais} si esto no cambia.'] },
            I: { propio: ['En fase de grupos la diferencia de goles también importa.'], rival: ['Todavía hay margen en el grupo: no hay que desesperarse.'] },
        },
        clasif: {
            A: { propio: ['La clasificación de {pais} al Mundial pasa por partidos como este.'], rival: ['Un tropiezo aquí y el sueño mundialista de {pais} se aleja.'] },
            I: { propio: ['En una eliminatoria se juega partido a partido; todo suma.'], rival: ['En estas rondas largas siempre hay tiempo de recomponer.'] },
        },
    };
    // relleno entre jugadas cuando juega el país de la cadena, según cómo va el marcador
    const CHARLA_PAIS = {
        A: {
            gana: ['{pais} lo está manejando, pero ojo: hay que cerrar el partido.', 'Qué orgullo ver a {pais} así; ahora, a no relajarse.'],
            empata: ['{pais} tiene que animarse un poco más: el empate no nos sirve.', 'Esto está parejo, pero {pais} puede mucho más.'],
            pierde: ['{pais} necesita reaccionar: así no se gana, hay que meter más gente al ataque.', 'Con el {marc} cuesta, pero {pais} no se puede rendir.'],
        },
        I: {
            gana: ['Es un buen resultado para {pais}, pero {contra} no está vencido.', 'Con ventaja, lo difícil es mantener la concentración.'],
            empata: ['Igualdad justa por lo que se ve: ninguno termina de imponerse.', 'Los dos equipos se respetan; el que arriesgue mejor se lleva esto.'],
            pierde: ['{pais} tiene tiempo, pero necesita ordenar las ideas y no desesperarse.', 'Perder no es el fin; hay que seguir jugando con la cabeza fría.'],
        },
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
    const DESPEDIDA_PAIS = {
        A: {
            gana: ['¡Qué alegría! {pais} se lleva la victoria y se la ganó en la cancha.', 'Orgullo total con {pais}: ganó y lo celebramos como se debe.'],
            empata: ['Un empate que sabe a poco para {pais}, aunque se rescata algo.', 'Nos vamos con las manos vacías a medias: {pais} pudo más.'],
            pierde: ['Duele, claro que duele, pero {pais} tiene que levantarse y seguir.', 'No fue la noche de {pais}; toca aprender y volver más fuerte.'],
        },
        I: {
            gana: ['Hay que reconocer también el esfuerzo de {contra}: fue un partido exigente.', 'Una victoria merecida de {pais}, con un rival que se hizo respetar.'],
            empata: ['Un resultado justo: los dos equipos tuvieron sus momentos.', 'Ninguno se llevó el partido; los detalles lo dejaron así.'],
            pierde: ['Siendo justos, {contra} fue mejor en los momentos clave.', '{pais} puede aprender mucho de este partido; hay material para trabajar.'],
        },
    };
    const DESPEDIDA = {
        resultado: {
            tanda: ['¡Se acabó! {gg}-{gp} en el tiempo reglamentario y {gan} gana en los penales {tg} a {tp} ante {per}.', 'Final en {estadio}: empate {gg}-{gp} y {gan} se impone desde el punto penal, {tg}-{tp}.'],
            victoria: ['¡Y se acabó! {gan} se lleva el partido {gg}-{gp} ante {per}.', 'Final del partido: {gan} gana {gg} a {gp} y se queda con los tres puntos.',
                       'Termina el partido en {estadio}: {gan} {gg}, {per} {gp}.'],
            goleada: ['¡Paliza en {estadio}! {gan} golea {gg}-{gp} a {per}.', 'Se acabó, y fue una goleada: {gan} {gg}, {per} {gp}.', '¡Qué manera de ganar! {gan} arrasa a {per} por {gg}-{gp}.'],
            empate: ['Se acabó: {local} y {visita} empatan {gg}-{gp} y se reparten los puntos.', 'Final del partido en {estadio}: {local} {gg}, {visita} {gp}. Todo igual.',
                     'Termina igualado el partido: {local} {gg} - {gp} {visita}.'],
            vacio: ['Se acabó el partido: {local} y {visita} empatan sin goles.', 'Cero a cero en {estadio}: un partido de mucho cuidado en las áreas.'],
        },
        analisis: {
            tanda: ['Una tanda para el infarto: así se define el fútbol cuando ya no queda nada más que dar.', 'Los penales son una lotería con muchísima cabeza: hoy le tocó a {gan} sonreír.'],
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
        const ta = estadoTanda(eventos, eventos.length - 1, { local: data.local, visitante: data.visitante });
        const tandaRes = ta && ta.decidida ? { ganador: ta.ganador, perdedor: ta.ganador === data.local ? data.visitante : data.local, tg: Math.max(ta.gl, ta.gv), tp: Math.min(ta.gl, ta.gv) } : null;
        return { tanda: tandaRes, local: data.local, visitante: data.visitante, gl, gv, ganador: gana ? (gana === 'local' ? data.local : data.visitante) : null,
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

        // --- opinión: la selección de la cadena (si juega) y la situación del partido desde su punto de vista
        function propio(mesaIdx) {
            if (o.modo !== 'tv') return null;
            const id = mesas[mesaIdx] && mesas[mesaIdx].tele && mesas[mesaIdx].tele.pais_id;
            if (id == null) return null;
            if (id === o.idLocal) return { lado: 'local', nombre: o.local, contra: o.visitante };
            if (id === o.idVisita) return { lado: 'visita', nombre: o.visitante, contra: o.local };
            return null;
        }
        function golesDe(p, ctx) {
            if (!p || typeof ctx.golesLocal !== 'number' || typeof ctx.golesVisita !== 'number') return null;
            return p.lado === 'local' ? { a: ctx.golesLocal, b: ctx.golesVisita } : { a: ctx.golesVisita, b: ctx.golesLocal };
        }
        function estadoPropio(p, ctx) {
            const g = golesDe(p, ctx);
            return g ? (g.a > g.b ? 'gana' : (g.a < g.b ? 'pierde' : 'empata')) : null;
        }
        function etapaDelPartido() {
            const f = Number(o.fase);
            if (!f) return null;
            return f >= 8 ? 'knockout' : (f === 7 ? 'grupos' : 'clasif');
        }
        // ---- comentarios por tiempo × marcador × fase (tablas CTX_* de arriba)
        function faseClave() {
            const f = Number(o.fase);
            if (!f) return null;
            const j = Number(o.jornada) || 0, jt = Number(o.jornadasTotal) || 0, ultima = jt > 1 && j === jt;
            if (f === 7) return ultima ? 'grupos_ultima' : (j === 1 ? 'grupos_1' : 'grupos_2');
            if (f <= 5) return ultima ? 'clasif_ultima' : 'clasif';
            return { 6: 'repechaje', 8: '16vos', 9: '8vos', 10: '4tos', 11: 'semis', 12: 'tercer', 13: 'final' }[f] || null;
        }
        // a quién apoya quien habla: el analista, al país de la cadena; el invitado, al suyo si juega (si no, mira al de la cadena)
        function perspectiva(mesaIdx, codigo) {
            const inv = mesas[mesaIdx] && mesas[mesaIdx].invitado;
            if (codigo === 'I' && inv && inv.pais_id != null) {
                if (inv.pais_id === o.idLocal) return { lado: 'local', nombre: o.local, contra: o.visitante };
                if (inv.pais_id === o.idVisita) return { lado: 'visita', nombre: o.visitante, contra: o.local };
            }
            return propio(mesaIdx);
        }
        /**
         * Un comentario que depende del momento: cuánto se lleva jugado, cómo va el marcador y en qué fase del torneo se juega. Devuelve
         * {texto, clave} o null. `cfg.prio` decide con qué frecuencia entra en lugar de la frase de la jugada (más en las importantes).
         */
        function lineaContexto(codigo, mesaIdx, ctx, rng, datos, cfg) {
            if (o.modo !== 'tv' || (codigo !== 'A' && codigo !== 'I')) return null;
            const prob = cfg.prio >= 3 ? 0.8 : (cfg.prio === 2 ? 0.55 : (cfg.prio === 1 ? 0.35 : 0.2));
            if (!cfg.forzar && rng() > prob) return null;
            const minuto = parseInt(ctx.minuto, 10);
            if (isNaN(minuto) || typeof ctx.golesLocal !== 'number' || typeof ctx.golesVisita !== 'number') return null;
            const T = minuto > 90 ? 'alargue' : (minuto > 70 ? 'final' : (minuto > 45 ? 'segundo' : (minuto >= 20 ? 'primer' : 'inicio')));
            const ps = perspectiva(mesaIdx, codigo);
            const faseK = faseClave();
            const d = Object.assign({}, datos, { min: minuto });
            const pieza = (pool, clave) => (pool && pool.length ? elegirPlantilla(pool, clave, rng, d) : null);
            const dentro = t => t && t.length <= 200;
            if (!ps) {   // nadie a quien apoyar: lectura neutral (sin tono de hincha)
                const dif = Math.abs(ctx.golesLocal - ctx.golesVisita);
                const M = dif === 0 ? (ctx.golesLocal === 0 ? 'cero' : 'empate') : (dif >= 3 ? 'goleada' : 'ventaja');
                const t = pieza((CTX_NEUTRO[codigo] || {})[M], `ctxn:${codigo}:${M}`);
                return t ? { texto: t, clave: `ctx:neutro:${codigo}:${M}` } : null;
            }
            const g = ps.lado === 'local' ? { a: ctx.golesLocal, b: ctx.golesVisita } : { a: ctx.golesVisita, b: ctx.golesLocal };
            const dif = g.a - g.b;
            const M = dif === 0 ? (g.a === 0 ? 'cero' : 'empate') : (dif > 0 ? (dif >= 2 ? 'gana2' : 'gana1') : (dif <= -2 ? 'pierde2' : 'pierde1'));
            d.eq = ps.nombre; d.rival = ps.contra;
            d.marc = `${ps.nombre} ${g.a}-${g.b} ${ps.contra}`;   // el equipo de quien habla primero: así no se confunde quién va ganando
            // buenos o malos según considere: el hincha tiende al optimismo si va ganando; el invitado opina más libre
            const pOpt = codigo === 'A' ? (M.startsWith('gana') ? 0.72 : (M.startsWith('pierde') ? 0.45 : 0.6)) : 0.5;
            const tono = rng() < pOpt ? 'opt' : 'pes';
            const bespoke = CTX_MOMENTO[codigo] || {};
            const claveMomento = bespoke[`${T}_${M}`] ? `${T}_${M}` : (bespoke[`${T}_${M.replace(/\d/, '')}`] ? `${T}_${M.replace(/\d/, '')}` : null);
            let texto = null, clave = '';
            if (claveMomento && rng() < 0.55) { texto = pieza(bespoke[claveMomento], `ctxm:${codigo}:${claveMomento}`); clave = `momento:${claveMomento}`; }
            if (!texto) {
                const marcador = pieza(((CTX_MARCADOR[codigo] || {})[tono] || {})[M], `ctxk:${codigo}:${tono}:${M}`);
                if (!marcador) return null;
                const tiempo = rng() < 0.3 ? pieza(CTX_TIEMPO[T], `ctxt:${T}`) : null;
                texto = tiempo ? `${tiempo} ${marcador}` : marcador;
                clave = `marcador:${tono}:${M}`;
            }
            // la fase del torneo, a veces como segunda frase (más en las jugadas importantes)
            if (faseK && CTX_FASE[faseK] && rng() < (cfg.prio >= 3 ? 0.55 : 0.3)) {
                const f = pieza(CTX_FASE[faseK][codigo], `ctxf:${codigo}:${faseK}`);
                if (f && dentro(`${texto} ${f}`)) texto = `${texto} ${f}`;
                else if (f && !texto) texto = f;
            }
            return { texto, clave: `ctx:${codigo}:${clave}` };
        }
        // sufijo de la situación: en un gol, qué hizo (pone adelante, iguala, amplía, descuenta); en lo demás, cómo va el país de la cadena
        function sufijoSituacion(clase, evento, p, ctx) {
            if (clase === 'gol') {
                const loc = evento.equipo === o.local;
                if (typeof ctx.golesLocal !== 'number') return null;
                const d = loc ? ctx.golesLocal - ctx.golesVisita : ctx.golesVisita - ctx.golesLocal;
                return d < 0 ? 'descuenta' : (d === 0 ? 'iguala' : (d === 1 ? 'adelante' : 'amplia'));
            }
            const est = estadoPropio(p, ctx);
            return est === 'gana' || est === 'pierde' ? est : null;
        }

        // «Ioannis Pittas» -> «Ioannis Pittas de Chipre» (la primera mención de cada jugador de la jugada): así quien no conoce a los
        // jugadores sabe de qué lado va la jugada. No toca el texto si no se conoce su país o si ya lo dice.
        function conPais(texto, jugadores) {
            if (typeof o.paisDe !== 'function') return texto;
            let t = texto;
            (jugadores || []).slice(0, 3).forEach(nombre => {
                const pais = nombre && o.paisDe(nombre);
                if (!pais) return;
                const i = t.indexOf(nombre);
                if (i < 0) return;
                const despues = t.slice(i + nombre.length);
                if (/^\s*(de|del)\s/i.test(despues) || despues.trimStart().startsWith('(')) return;
                t = t.slice(0, i + nombre.length) + ' de ' + pais + despues;
            });
            return t;
        }

        function recordarPlantilla(id) { recientes.push(id); if (recientes.length > 14) recientes.shift(); }

        function elegirPlantilla(pool, clave, rng, datos) {
            const candidatas = [];
            const reunir = (evitarRecientes) => pool.forEach((plantilla, i) => {
                const id = clave + ':' + i;
                if (evitarRecientes && recientes.includes(id)) return;
                const texto = rellenar(plantilla, datos);
                if (texto) candidatas.push({ id, texto });
            });
            reunir(true);
            if (!candidatas.length) reunir(false);   // si todas se usaron hace poco, mejor repetir una que quedarse callado (sobre todo con el desenlace de un disparo)
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
                // las opiniones (analista e invitado) nunca las dice el narrador: se alternan entre ellos y, si no hay otro, repite quien habla
                const todos = ['narrador', 'analista'].concat(mesas[mesaIdx] && mesas[mesaIdx].invitado ? ['invitado'] : []);
                const alternos = todos.filter(r => r !== rol && (rol === 'narrador' || r !== 'narrador'));
                return alternos.length ? alternos[Math.floor(rng() * alternos.length)] : rol;
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
                desc: conPais(limpiarDescripcion(evento.descripcion), jugadores), j: apellido(jugadores[0]), j2: apellido(jugadores[1]),
                eq: equipoEvento, rival, min: ctx.minuto, marc: ctx.marcador, local: o.local, visita: o.visitante, estadio: o.estadio,
            };
            const pro = propio(mesaIdx);
            const lado = pro && equipoEvento ? (equipoEvento === pro.nombre ? 'propio' : 'rival') : null;
            const suf = pro && lado ? sufijoSituacion(clase, evento, pro, ctx) : null;
            if (pro) { datos.pais = pro.nombre; datos.contra = pro.contra; }
            // tanda de penales: marcador de la tanda y variantes de muerte súbita / cobro decisivo
            const ta = ctx.tanda || null;
            let claseF = clase;
            if (ta) {
                datos.tlinea = `${o.local} ${ta.gl}, ${o.visitante} ${ta.gv}`;
                if (ta.ganador) datos.ganaT = ta.ganador;
                if (ta.decidida && FRASES[clase + '_decide']) claseF = clase + '_decide';
                else if (ta.subita && FRASES[clase + '_subita']) claseF = clase + '_subita';
                // en un cobro de la tanda el rival está en `evento.equipo` o es el otro: {j2} es el tirador cuando el que habla es el portero
            }
            const salida = [];
            const pasos = soloReaccion ? ['A:0.9'] : cfg.cadena;
            let retraso = 250 + Math.floor(rng() * 300);
            pasos.forEach((paso, k) => {
                const [codigo, prob] = paso.split(':');
                if (prob && rng() > parseFloat(prob)) return;
                let pool = (FRASES[claseF] || {})[codigo] || [];
                let clavePool = `${claseF}:${codigo}`;
                // primero, lo que dicen el tiempo, el marcador y la fase del torneo (analista e invitado)
                let porContexto = false;
                if (codigo === 'A' || (codigo === 'I' && mesas[mesaIdx].invitado)) {
                    const lc = lineaContexto(codigo, mesaIdx, ctx, rng, datos, cfg);
                    if (lc) { pool = [lc.texto]; clavePool = `subj:${lc.clave}`; porContexto = true; }
                }
                // con opinión: el analista (del país de la cadena) con pasión y el invitado con una mirada objetiva
                if (!porContexto && pro && lado && (codigo === 'A' || (codigo === 'I' && mesas[mesaIdx].invitado)) && rng() < (codigo === 'A' ? 0.85 : 0.7)) {
                    const fuentes = [];
                    const etapa = etapaDelPartido();
                    if (cfg.prio >= 3 && etapa && rng() < 0.3 && ETAPA[etapa][codigo][lado]) fuentes.push([ETAPA[etapa][codigo][lado], `etapa:${etapa}:${codigo}:${lado}`]);
                    const base = (SUBJ[clase] || {})[codigo];
                    if (base) {
                        const claves = [suf && `${lado}_${suf}`, lado];
                        claves.forEach(c => { if (c && base[c] && base[c].length) fuentes.push([base[c], `${clase}:${codigo}:${c}`]); });
                    }
                    for (const [pl, cl] of fuentes) {
                        const t = elegirPlantilla(pl, cl, rng, datos);
                        if (t) { pool = [t]; clavePool = `subj:${cl}`; break; }
                    }
                }
                if (!pool.length) return;
                // en la radio no hay invitado: su comentario lo dice la misma voz
                const texto = pool.length === 1 && clavePool.startsWith('subj:') ? pool[0] : elegirPlantilla(pool, clavePool, rng, datos);
                if (!texto) return;
                // lo que pasa en la jugada siempre lo cuenta el narrador (nunca se cede a otro por haber hablado seguido)
                const rol = codigo === 'N' ? hablante(mesaIdx, codigo) : evitarRepetir(mesaIdx, hablante(mesaIdx, codigo), rng);
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
            const pro = propio(mesaIdx), estado = estadoPropio(pro, ctx);
            if (pro && estado && (codigo === 'A' || codigo === 'I') && rng() < 0.55) { pool = CHARLA_PAIS[codigo][estado]; datos.pais = pro.nombre; datos.contra = pro.contra; }
            else if (!isNaN(minuto) && minuto < 15 && rng() < 0.4) pool = CHARLA.T;
            else if (!isNaN(minuto) && minuto > 75 && rng() < 0.4) pool = CHARLA.L;
            else if (o.modo === 'radio' && rng() < 0.4) pool = RADIO_CHARLA;
            // casi siempre, lo que toca decir por el momento: tiempo, marcador y fase del torneo
            let texto = null;
            if ((codigo === 'A' || codigo === 'I') && rng() < 0.65) {
                const lc = lineaContexto(codigo, mesaIdx, ctx, rng, datos, { prio: 3, forzar: true });
                if (lc) texto = lc.texto;
            }
            if (!texto) texto = elegirPlantilla(pool, `charla:${codigo}`, rng, datos);
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
            const tipo = res.tanda ? 'tanda' : (res.ganador ? (res.diferencia >= 3 ? 'goleada' : 'victoria') : (res.gg === 0 ? 'vacio' : 'empate'));
            const datos = { gan: res.tanda ? res.tanda.ganador : res.ganador, per: res.tanda ? res.tanda.perdedor : res.perdedor, tg: res.tanda && res.tanda.tg, tp: res.tanda && res.tanda.tp, gg: res.gg, gp: res.gp, local: res.local, visita: res.visitante, estadio: res.estadio, cadena,
                            figura: res.figura && apellido(res.figura.nombre), n: res.figura && res.figura.n, rojas: res.rojas, s: res.rojas > 1 ? 's' : '',
                            golesTxt: res.figura && (res.figura.n > 1 ? `anotó ${res.figura.n} goles` : 'anotó el gol') };
            const lineas = [];
            const pon = (rol, pool, clave) => {
                const texto = elegirPlantilla(pool, 'fin:' + clave, rng, datos);
                if (texto) lineas.push({ mesa: mesaIdx, rol, texto, retraso: lineas.length ? 350 : 700, duracion: duracion(texto) + 600, prio: 3, paso: lineas.length ? 1 : 0, efecto: null, equipoEfecto: null, evento: -1 });
            };
            if (o.modo !== 'tv') {
                pon('radio', DESPEDIDA.resultado[tipo], 'r');
                pon('radio', !res.tanda && res.figura && rng() < 0.7 ? DESPEDIDA.analisis.figura : DESPEDIDA.analisis[tipo], 'a');
                pon('radio', DESPEDIDA.radio, 'x');
            } else {
                const tieneInvitado = !!mesa.invitado;
                pon('narrador', DESPEDIDA.resultado[tipo], 'r');
                const pro = propio(mesaIdx);
                const ganFin = res.tanda ? res.tanda.ganador : res.ganador, perFin = res.tanda ? res.tanda.perdedor : res.perdedor;
                const estadoFin = pro ? (ganFin === pro.nombre ? 'gana' : (perFin === pro.nombre ? 'pierde' : 'empata')) : null;
                if (pro) { datos.pais = pro.nombre; datos.contra = pro.contra; }
                pon('analista', pro && rng() < 0.85 ? DESPEDIDA_PAIS.A[estadoFin] : (!res.tanda && res.figura && rng() < 0.7 ? DESPEDIDA.analisis.figura : DESPEDIDA.analisis[tipo]), 'a');
                if (res.rojas && rng() < 0.6) pon('analista', DESPEDIDA.analisis.roja, 'ro');
                if (tieneInvitado) pon('invitado', pro && rng() < 0.65 ? DESPEDIDA_PAIS.I[estadoFin] : DESPEDIDA.invitado, 'i');
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
    // Estado de la tanda de penales hasta el evento `k` (con él incluido): cobros de cada equipo en orden, goles, si ya está decidida
    // y si se juega la muerte súbita. `partido` = {local, visitante}. null si todavía no empezó la tanda.
    function estadoTanda(eventos, k, partido) {
        if (!eventos || !partido) return null;
        let inicio = -1;
        for (let i = 0; i <= k && i < eventos.length; i++) if ((eventos[i].tipo || '').includes('TANDA DE PENALTIS')) { inicio = i; break; }
        if (inicio < 0) return null;
        const rl = [], rv = [];
        for (let i = inicio + 1; i <= k && i < eventos.length; i++) {
            const ev = eventos[i], t = ev.tipo || '';
            if (t.includes('GOL DE PENAL')) (ev.equipo === partido.local ? rl : rv).push(true);
            else if (t.includes('PENAL FALLADO')) (ev.equipo === partido.local ? rv : rl).push(false);   // el equipo del evento es el del portero
            else if (t.includes('PENAL ANULADO')) (ev.equipo === partido.local ? rl : rv).push(false);
        }
        const gl = rl.filter(Boolean).length, gv = rv.filter(Boolean).length, tl = rl.length, tv = rv.length;
        let decidida = false;
        if (tl <= 5 && tv <= 5) decidida = gl > gv + Math.max(0, 5 - tv) || gv > gl + Math.max(0, 5 - tl) || (tl === 5 && tv === 5 && gl !== gv);
        else decidida = tl === tv && gl !== gv;
        const subita = tl > 5 || tv > 5 || (tl === 5 && tv === 5 && gl === gv);
        return { rl, rv, gl, gv, tl, tv, decidida, subita, ganador: decidida ? (gl > gv ? partido.local : partido.visitante) : null };
    }

    const GOLES_TIPO = { 'GOL DE TIRO LIBRE': 'de tiro libre', 'GOL DE CÓRNER': 'de córner' };
    // Cada pieza del arbitraje: [fragmento del tipo, clase de la pieza, titular, rótulo, puesto del árbitro]; gana la primera
    const ARBITRAJE = [
        ['SILBATO INICIAL', 'inicio', '¡ARRANCA EL PARTIDO!', 'Pitido inicial', 'central'],
        ['FINAL DEL PRIMER TIEMPO', 'descanso', 'FINAL DEL PRIMER TIEMPO', 'Medio tiempo', 'central'],
        ['COMIENZA EL SEGUNDO TIEMPO', 'segundo', 'ARRANCA EL SEGUNDO TIEMPO', 'Segundo tiempo', 'central'],
        ['SEGUNDO TIEMPO EXTRA', 'extra', 'SEGUNDO TIEMPO EXTRA', 'Tiempo extra', 'central'],
        ['TIEMPO EXTRA', 'extra', '¡TIEMPO EXTRA!', 'Alargue', 'central'],
        ['TIEMPO AÑADIDO', 'anadido', 'TIEMPO AÑADIDO', 'Cuarto árbitro', 'cuarto'],
        ['PITIDO FINAL', 'final', 'FINAL DEL PARTIDO', 'Pitido final', 'central'],
        ['REVISIÓN VAR', 'revision', 'REVISIÓN VAR', 'Revisión pedida', 'cuarto'],
    ];
    function grafico(evento, indice, eventos, partido) {
        const tipo = (evento && evento.tipo) || '';
        const j = (evento && evento.jugadores) || [];
        const clase = clasificar(evento);
        // --- tanda de penales: el aviso y cada cobro, con el marcador de la tanda
        if (tipo.includes('TANDA DE PENALTIS')) return { accion: 'tanda', evento: indice, fase: 'inicio', titulo: '¡TANDA DE PENALES!', prio: 3, estado: estadoTanda(eventos, indice, partido), minuto: evento.minuto };
        if (partido && (clase === 'tandagol' || clase === 'tandafallo' || (evento.periodo === 5 && tipo.includes('PENAL ANULADO')))) {
            const fallo = clase === 'tandafallo';
            const equipoTirador = fallo ? (evento.equipo === partido.local ? partido.visitante : partido.local) : evento.equipo;
            return { accion: 'tanda', evento: indice, fase: 'cobro', resultado: clase === 'tandagol' ? 'gol' : (fallo ? 'atajado' : 'anulado'), tirador: fallo ? j[1] : j[0], portero: fallo ? j[0] : null,
                     equipo: equipoTirador, prio: 3, estado: estadoTanda(eventos, indice, partido), minuto: evento.minuto };
        }
        // --- el cuerpo arbitral: pitidos, tiempo añadido, alargue y las decisiones del VAR (con el rostro del árbitro)
        const arb = ARBITRAJE.find(a => tipo.includes(a[0]));
        if (arb) return { accion: 'arbitro', evento: indice, clase: arb[1], titulo: arb[2], rotulo: arb[3], rol: evento.arbitro_rol || arb[4], arbitro: evento.arbitro || null,
                          minutos: evento.minutos_anadidos != null ? evento.minutos_anadidos : null, detalle: arb[1] === 'revision' ? limpiarDescripcion(evento.descripcion) : null,
                          minuto: evento.minuto, adicional: evento.adicional, prio: arb[1] === 'anadido' ? 1 : 2 };
        if (tipo.includes('VAR - ')) {
            const ok = tipo.includes('CONFIRMADO'), anula = tipo.includes('ANULADO');
            return { accion: 'arbitro', evento: indice, clase: ok ? 'var_ok' : (anula ? 'var_anula' : 'var_cambia'),
                     titulo: ok ? 'DECISIÓN CONFIRMADA' : (anula ? 'JUGADA ANULADA' : 'DECISIÓN REVISADA'), rotulo: 'VAR', rol: evento.arbitro_rol === 'var' ? 'var' : 'var', arbitro: evento.arbitro || null,
                     detalle: limpiarDescripcion(evento.descripcion), minuto: evento.minuto, prio: 2 };
        }
        // --- lesión
        if (clase === 'lesion' && j.length) return { accion: 'lesion', titulo: 'LESIONADO', evento: indice, jugador: j[0], equipo: evento.equipo || null, minuto: evento.minuto, lesion: evento.lesion || null,
                                                      gravedad: evento.gravedad || null, sale: !!evento.sale_lesionado, sinCambio: !!evento.sin_cambio, prio: 2 };
        // --- el director técnico: expulsado, amonestado, reclamo al árbitro y cambio táctico (sus eventos no traen jugadores sino `dt`)
        if (evento.dt && (tipo.includes('DT EXPULSADO') || tipo.includes('DT AMONESTADO') || tipo.includes('RECLAMO DEL DT') || tipo.includes('AJUSTE TÁCTICO'))) {
            const dtBase = { evento: indice, jugador: evento.dt, equipo: evento.equipo || null, minuto: evento.minuto, esDT: true };
            if (tipo.includes('DT EXPULSADO')) return Object.assign(dtBase, { accion: 'roja', titulo: 'DT EXPULSADO', motivo: 'Expulsado del banco', prio: 3 });
            if (tipo.includes('DT AMONESTADO')) return Object.assign(dtBase, { accion: 'amarilla', titulo: 'DT AMONESTADO', rival: null, prio: 2 });
            if (tipo.includes('RECLAMO DEL DT')) return Object.assign(dtBase, { accion: 'dtreclamo', titulo: 'RECLAMO DEL DT', prio: 1 });
            return Object.assign(dtBase, { accion: 'dtajuste', titulo: 'CAMBIO TÁCTICO', de: evento.esquema_de || null, a: evento.esquema_a || null, ajuste: evento.ajuste || null, prio: 2 });
        }
        // --- el instante antes del cobro de un tiro libre o un penal: tarjeta de suspenso (aún no se sabe si será gol)
        if ((clase === 'tirolibre' || clase === 'penalcobro') && j.length) {
            return { accion: clase, titulo: clase === 'penalcobro' ? 'VA A COBRAR' : 'TIRO LIBRE', evento: indice, jugador: j[0], equipo: evento.equipo || null, minuto: evento.minuto, prio: clase === 'penalcobro' ? 3 : 2 };
        }
        // --- tiro de esquina: la tarjeta de suspenso es del EQUIPO que lo cobra (el evento no trae jugadores)
        if (clase === 'corner' && tipo.includes('SAQUE DE ESQUINA') && evento.equipo) {
            return { accion: 'esquina', titulo: 'TIRO DE ESQUINA', evento: indice, jugador: null, esEquipo: true, equipo: evento.equipo, minuto: evento.minuto, prio: 2 };
        }
        if (!j.length) return null;
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
        // penal señalado [víctima, infractor]; `equipo` es el equipo que lo cobrará
        if (clase === 'penal' && tipo.indexOf('FALLADO') < 0 && tipo.indexOf('VAR') < 0 && j.length >= 2) return Object.assign(base, { accion: 'penal', titulo: 'PENAL', victima: j[0], infractor: j[1], prio: 3 });
        // cambio [entra, sale]
        if (clase === 'cambio' && j.length >= 2) return Object.assign(base, { accion: 'cambio', titulo: 'CAMBIO', entra: j[0], sale: j[1], prio: 1 });
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

    // ---------------------------------------------------------------- datos del partido para presentar en las pausas
    // Cuenta por jugador lo ya revelado. Primer nombre de `jugadores` = protagonista (el que remata, regatea, comete la falta, ataja...).
    function estadisticas(eventos) {
        const por = {};
        const ficha = (nombre, equipo) => por[nombre] || (por[nombre] = { nombre, equipo, goles: 0, asistencias: 0, atajadas: 0, faltas: 0, amarillas: 0, rojas: 0, disparos: 0, regates: 0, robos: 0 });
        (eventos || []).forEach(ev => {
            const j = ev.jugadores || [];
            if (!j[0]) return;
            const tipo = ev.tipo || '', clase = clasificar(ev);
            if (clase === 'gol' && tipo.indexOf('TANDA') < 0 && tipo.indexOf('GOL DE PENAL') < 0) {
                ficha(j[0], ev.equipo).goles++;
                if (j[2]) ficha(j[2], ev.equipo).asistencias++;
            } else if (clase === 'atajada') {
                if (tipo.includes('TIRO LIBRE BLOQUEADO')) return;   // lo bloquea la barrera, no un portero
                ficha(j[0], ev.equipo).atajadas++;
            } else if (clase === 'remate') ficha(j[0], ev.equipo).disparos++;
            else if (clase === 'regate') ficha(j[0], ev.equipo).regates++;
            else if (clase === 'falta') ficha(j[0], ev.equipo).faltas++;
            else if (clase === 'amarilla' && tipo.includes('TARJETA AMARILLA')) ficha(j[0], ev.equipo).amarillas++;
            else if (clase === 'roja' && tipo.includes('TARJETA')) ficha(j[0], ev.equipo).rojas++;
            else if (tipo.includes('DOBLE AMARILLA')) { const f = ficha(j[0], ev.equipo); f.amarillas += 2; f.rojas++; }
            else if (tipo.includes('ROBO DE BALÓN')) ficha(j[0], ev.equipo).robos++;
        });
        return Object.values(por);
    }
    const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
    function puntaje(p) { return p.goles * 5 + p.asistencias * 3 + p.atajadas * 1 + p.regates * 0.7 + p.disparos * 0.5 + p.robos - p.faltas * 0.4 - p.amarillas - p.rojas * 3; }
    function resumenJugador(p) {
        const partes = [];
        if (p.goles) partes.push(plural(p.goles, 'gol', 'goles'));
        if (p.asistencias) partes.push(plural(p.asistencias, 'asistencia', 'asistencias'));
        if (p.atajadas) partes.push(plural(p.atajadas, 'atajada', 'atajadas'));
        if (p.regates) partes.push(plural(p.regates, 'regate', 'regates'));
        if (p.disparos) partes.push(plural(p.disparos, 'remate', 'remates'));
        if (p.robos) partes.push(plural(p.robos, 'recuperación', 'recuperaciones'));
        return partes.slice(0, 3).join(' · ');
    }
    // candidatos: [clave, titulo del dato, campo que ordena, mínimo para que valga la pena, texto de la cifra]
    const DATOS = [
        { clave: 'figura', titulo: 'La figura del partido', valor: puntaje, minimo: 3, cifra: p => resumenJugador(p), etiqueta: 'MEJOR RENDIMIENTO' },
        { clave: 'goleador', titulo: 'El goleador del partido', valor: p => p.goles, minimo: 1, cifra: p => plural(p.goles, 'gol', 'goles'), etiqueta: 'GOLEADOR' },
        { clave: 'faltas', titulo: 'El que más faltas ha cometido', valor: p => p.faltas, minimo: 2, cifra: p => plural(p.faltas, 'falta', 'faltas'), etiqueta: 'MÁS FALTAS' },
        { clave: 'tarjetas', titulo: 'El más amonestado', valor: p => p.amarillas + p.rojas * 2, minimo: 1, cifra: p => [p.amarillas ? plural(p.amarillas, 'amarilla', 'amarillas') : '', p.rojas ? plural(p.rojas, 'roja', 'rojas') : ''].filter(Boolean).join(' · '), etiqueta: 'MÁS TARJETAS' },
        { clave: 'portero', titulo: 'La muralla del partido', valor: p => p.atajadas, minimo: 2, cifra: p => plural(p.atajadas, 'atajada', 'atajadas'), etiqueta: 'MEJOR PORTERO' },
        { clave: 'regates', titulo: 'El más habilidoso', valor: p => p.regates, minimo: 2, cifra: p => plural(p.regates, 'regate destacado', 'regates destacados'), etiqueta: 'MÁS REGATES' },
        { clave: 'remates', titulo: 'El más peligroso con la pelota', valor: p => p.disparos + p.goles, minimo: 2, cifra: p => plural(p.disparos + p.goles, 'remate', 'remates'), etiqueta: 'MÁS REMATES' },
        { clave: 'robos', titulo: 'El recuperador del partido', valor: p => p.robos, minimo: 3, cifra: p => plural(p.robos, 'balón recuperado', 'balones recuperados'), etiqueta: 'MÁS RECUPERACIONES' },
    ];
    /**
     * El dato a presentar en una pausa: elige entre los que ya valen la pena (hay un líder claro) y no se hayan mostrado
     * (`usados` = claves recientes; si ya salieron todos se vuelve a empezar). azarFn() → [0, 1). Devuelve null si todavía no hay nada.
     */
    function candidatosDato(eventos) {
        const jugadores = estadisticas(eventos);
        const candidatos = [];
        if (!jugadores.length) return candidatos;
        DATOS.forEach(d => {
            const ordenados = jugadores.filter(p => d.valor(p) >= d.minimo).sort((a, b) => d.valor(b) - d.valor(a));
            if (!ordenados.length) return;
            const lider = ordenados[0];
            if (ordenados[1] && d.valor(ordenados[1]) === d.valor(lider) && d.clave !== 'figura') return;   // empate en el primer puesto: no hay líder
            candidatos.push({ clave: d.clave, titulo: d.titulo, etiqueta: d.etiqueta, jugador: lider.nombre, equipo: lider.equipo, cifra: d.cifra(lider) });
        });
        return candidatos;
    }
    function elegirDato(eventos, usados, azarFn) {
        const candidatos = candidatosDato(eventos);
        if (!candidatos.length) return null;
        const frescos = candidatos.filter(c => !(usados || []).includes(c.clave));
        const pool = frescos.length ? frescos : candidatos;
        return pool[Math.floor((azarFn || Math.random)() * pool.length)];
    }

    // ---------------------------------------------------------------- estadísticas por equipo para las plecas patrocinadas
    // Todo sale de las jugadas YA reveladas. La «posesión» es la parte de las jugadas de ataque y progresión que llevó cada equipo.
    function conteos(eventos, local) {
        const nuevo = () => ({ jugadas: 0, remates: 0, apuerta: 0, corners: 0, faltas: 0, amarillas: 0, rojas: 0, fueras: 0, regates: 0, recup: 0, atajadas: 0 });
        const c = { l: nuevo(), v: nuevo() };
        (eventos || []).forEach(ev => {
            const t = ev.tipo || '';
            if (ev.periodo === 5 || t.includes('TANDA') || t.includes('GOL DE PENAL')) return;
            const propio = ev.equipo === local ? c.l : c.v, rival = ev.equipo === local ? c.v : c.l;
            if (t.includes('TRANSICIÓN') || t.includes('PREPARACIÓN') || t.includes('REGATE DESTACADO') || t.includes('DISPARO') || t.includes('⚽ GOL')) propio.jugadas++;
            if (t.includes('REGATE DESTACADO')) propio.regates++;
            if (t.includes('DISPARO DESVIADO')) propio.remates++;
            if (t.includes('⚽ GOL')) { propio.remates++; propio.apuerta++; }
            if (t.includes('ATAJADA') && !t.includes('TIRO LIBRE BLOQUEADO')) { propio.atajadas++; rival.remates++; rival.apuerta++; }
            if (t.includes('DESVÍO A CÓRNER')) rival.corners++;
            if (t.includes('🛑') && t.includes('FALTA')) propio.faltas++;
            if (t.includes('FUERA DE LUGAR')) propio.fueras++;
            if (t.includes('TARJETA AMARILLA')) propio.amarillas++;
            if (t.includes('DOBLE AMARILLA')) { propio.amarillas += 2; propio.rojas++; } else if (t.includes('TARJETA ROJA')) propio.rojas++;
            if (t.includes('ROBO DE BALÓN') || t.includes('PRESIÓN DEFENSIVA')) propio.recup++;
        });
        return c;
    }
    // ---------------------------------------------------------------- plecas patrocinadas: UN dato a la vez, al azar entre todos
    const PLECAS = [
        { clave: 'posesion', tema: 'la posesión del balón', campo: 'jugadas', pct: true, minimo: 8 },
        { clave: 'remates', tema: 'los remates', campo: 'remates', minimo: 2 },
        { clave: 'apuerta', tema: 'los tiros a puerta', campo: 'apuerta', minimo: 2 },
        { clave: 'corners', tema: 'los tiros de esquina', campo: 'corners', minimo: 2 },
        { clave: 'regates', tema: 'los regates ganados', campo: 'regates', minimo: 3 },
        { clave: 'recup', tema: 'las recuperaciones de balón', campo: 'recup', minimo: 4 },
        { clave: 'atajadas', tema: 'las atajadas de los porteros', campo: 'atajadas', minimo: 2 },
        { clave: 'fueras', tema: 'los fueras de lugar', campo: 'fueras', minimo: 2 },
        { clave: 'faltas', tema: 'las faltas cometidas', campo: 'faltas', minimo: 3 },
        { clave: 'amarillas', tema: 'las tarjetas amarillas', campo: 'amarillas', minimo: 1 },
        { clave: 'rojas', tema: 'las expulsiones', campo: 'rojas', minimo: 1 },
    ];
    /**
     * Una pleca: {clave, tema (lo que presenta la marca), etiqueta, texto (el dato)}. Mezcla los datos de equipo con los de jugador
     * (`elegirDato`'s candidatos) y toma UNO al azar entre los que valen la pena y no se mostraron hace poco. null si no hay nada.
     */
    function elegirPleca(eventos, partido, usados, azarFn) {
        if (!partido) return null;
        const c = conteos(eventos, partido.local), sl = partido.siglaLocal || partido.local, sv = partido.siglaVisita || partido.visitante;
        const cand = [];
        PLECAS.forEach(d => {
            const l = c.l[d.campo], v = c.v[d.campo], tot = l + v;
            if (tot < d.minimo) return;
            if (d.pct) { const pl = Math.round(100 * l / tot); cand.push({ clave: d.clave, tema: d.tema, texto: `${sl} ${pl}%  ·  ${100 - pl}% ${sv}` }); }
            else cand.push({ clave: d.clave, tema: d.tema, texto: `${sl} ${l}  ·  ${v} ${sv}` });
        });
        candidatosDato(eventos).forEach(d => cand.push({ clave: 'j-' + d.clave, tema: d.titulo.charAt(0).toLowerCase() + d.titulo.slice(1), texto: `${d.jugador} (${d.equipo})  ·  ${d.cifra}` }));
        if (!cand.length) return null;
        const frescos = cand.filter(x => !(usados || []).includes(x.clave));
        const pool = frescos.length ? frescos : cand;
        return pool[Math.floor((azarFn || Math.random)() * pool.length)];
    }
    /** Las formaciones al arrancar, en el formato de la pleca. */
    function plecaFormacion(planteamiento, partido) {
        const pl = planteamiento && planteamiento.local, pv = planteamiento && planteamiento.visita;
        if (!pl || !pv || !partido) return null;
        return { clave: 'formacion', tema: 'las formaciones con las que salen a la cancha', texto: `${partido.siglaLocal || partido.local} ${pl.esquema}  ·  ${pv.esquema} ${partido.siglaVisita || partido.visitante}` };
    }

    // ---------------------------------------------------------------- comentarios de la pleca: líderes de la afición, presidentes, periodistas y jugadores
    // Solo con lo ya revelado (marcador, minuto, rojas). Subjetivos o objetivos según quién habla: la afición y los jugadores de otro país del
    // grupo opinan con el corazón o con la tabla en la mano; el presidente cuida las formas; el periodista, según su sesgo, analiza o se
    // inclina. Las leyendas no hablan.
    // Situaciones de quien habla por una de las selecciones que juegan: cero, empate, gana, gana_mucho, pierde, pierde_mucho, roja_propia, roja_rival.
    const C_PROPIO = {
        aficion: {
            efusivo: {
                cero: ['Todavía sin goles, pero la tribuna no para de cantar. ¡Vamos {eq}!', 'Se siente que el gol de {eq} está por llegar. ¡Aguanten!'],
                empate: ['{marc} y la fiesta sigue. ¡{eq} va por más!', 'Empatan, pero {eq} se siente más grande. ¡A ganarlo!'],
                gana: ['¡Qué alegría ver ganando a {eq}! ¡Que no pare la fiesta!', '¡{marc} y la gente feliz! ¡Vamos {eq}, vamos!'],
                gana_mucho: ['¡Esto es una fiesta! {eq} lo está goleando, ¡qué orgullo!', '¡Cómo gozamos! {marc}, ¡que lo recuerden!'],
                pierde: ['Duele, pero la afición no se va: ¡{eq} lo da vuelta!', 'Vamos abajo, pero con {eq} hasta el final. ¡Arriba ese ánimo!'],
                pierde_mucho: ['Está difícil, pero aquí nadie se rinde. ¡Gracias por el esfuerzo, {eq}!', '{marc}... aun así vamos a cantar hasta el último minuto.'],
                roja_propia: ['Con uno menos, {eq} necesita más aliento que nunca. ¡Fuerza!', 'La roja duele, pero ¡con diez también se puede, {eq}!'],
                roja_rival: ['¡Con uno más! Es el momento de {eq}, ¡a aprovecharlo!', 'Se quedaron con diez: ¡vamos a por ellos, {eq}!']},
            exigente: {
                cero: ['Sin goles y sin ideas. {eq} tiene que hacer más que esto.', 'Esperamos otra cosa de {eq}: más intensidad, ya.'],
                empate: ['{marc} no nos alcanza. {eq} tiene que ir a ganarlo, no a mirar.', 'Con este empate no me conformo. Se le pide más a {eq}.'],
                gana: ['Vamos ganando, sí, pero {eq} todavía no convence del todo.', '{marc}. Que no se relajen: aún falta mucho.'],
                gana_mucho: ['Así sí. Que {eq} mantenga esta intensidad todo el torneo.', '{marc} y bien merecido. Pero que no se duerman.'],
                pierde: ['Inaceptable ir perdiendo. {eq} debe reaccionar ya.', 'Así no, {eq}. La afición merece más.'],
                pierde_mucho: ['Esto es una vergüenza. Habrá que pedir cuentas a todos.', '{marc}: la afición no merece esto de {eq}.'],
                roja_propia: ['Una expulsión absurda. {eq} no puede darse esos lujos.', 'Dejar a {eq} con diez es una irresponsabilidad.'],
                roja_rival: ['Con uno más no hay excusas: {eq} tiene que ganarlo.', 'Ventaja numérica, ahora {eq} está obligado a aprovecharla.']},
            humilde: {
                cero: ['Todavía 0-0. Con paciencia, {eq} va a encontrar su momento.', 'Lo importante es que {eq} lo intente. Aquí estamos.'],
                empate: ['{marc}. Un partido muy parejo; todo puede pasar.', 'Respeto al rival: está jugando bien. Pero {eq} puede.'],
                gana: ['Qué bonito ver ganando a {eq}, pero con los pies en la tierra.', 'Contento con el marcador, aunque falta todo el partido.'],
                gana_mucho: ['Estamos felices, pero sin olvidar que el rival es digno. ¡Gracias, {eq}!', '{marc}: lo disfrutamos mucho, con respeto al rival.'],
                pierde: ['Vamos perdiendo, pero {eq} deja todo. Eso se agradece.', 'Se puede perder, lo importante es dar la cara. ¡Ánimo, {eq}!'],
                pierde_mucho: ['Hoy no se dio, pero aquí seguimos con {eq}, pase lo que pase.', 'Aplausos para {eq}, a pesar del marcador.'],
                roja_propia: ['Una expulsión que complica, pero {eq} es valiente. Ánimo.', 'Con diez cuesta; la afición está con ustedes.'],
                roja_rival: ['Se quedaron con diez; ojalá {eq} sepa aprovecharlo sin confiarse.', 'Una expulsión es mala para cualquiera; ahora a jugar bien.']}
        },
        presidente: {
            sobrio: {
                cero: ['Partido cerrado entre dos selecciones serias. Confiamos en {eq}.', 'Hay que esperar, el planteamiento de {eq} es el correcto.'],
                empate: ['{marc}: un resultado parejo. El cuerpo técnico de {eq} sabrá ajustar.', 'Respetamos al rival; {eq} está haciendo su trabajo.'],
                gana: ['Satisfechos con la actuación de {eq}; hay que mantener la calma.', '{marc}. Un buen momento para el proyecto de {eq}.'],
                gana_mucho: ['Un resultado contundente para {eq}; felicito a jugadores y cuerpo técnico.', '{marc}: orgullo para toda la federación.'],
                pierde: ['Momento complicado para {eq}, pero hay que confiar en el proceso.', 'Vamos abajo; esperamos la reacción de {eq}.'],
                pierde_mucho: ['Un resultado difícil de explicar hoy. Después del partido, evaluaremos con serenidad.', '{marc}. Debemos analizar con calma qué pasó con {eq}.'],
                roja_propia: ['La expulsión complica el plan de {eq}; confío en el carácter del equipo.', 'Con diez hay que defender con orden. Confianza en {eq}.'],
                roja_rival: ['Superioridad numérica para {eq}; hay que manejarla con inteligencia.', 'La expulsión cambia el partido, y {eq} debe aprovecharlo.']},
            presion: {
                cero: ['Se pide más de {eq}: sin goles no se ganan los partidos.', 'El pueblo quiere ver a {eq} atacar. Hay que arriesgar.'],
                empate: ['{marc} no basta; se exige un {eq} más ambicioso.', 'Un empate así no nos sirve. {eq} debe ganar.'],
                gana: ['Bien por {eq}, pero esperamos que cierre el partido.', '{marc}: justo lo que pedíamos. Que no baje el ritmo.'],
                gana_mucho: ['¡Contundente! Así quiere ver la gente a {eq}.', '{marc}: un resultado a la altura de nuestras ambiciones.'],
                pierde: ['Perder así no está en el plan. {eq} debe reaccionar o habrá consecuencias.', 'Se requiere una reacción inmediata de {eq}.'],
                pierde_mucho: ['Este resultado es inaceptable; en cuanto termine, habrá decisiones.', '{marc}: hay que revisar todo en {eq}.'],
                roja_propia: ['Una expulsión que no puede repetirse. Se exige disciplina a {eq}.', 'Con diez, {eq} se juega el partido; exigimos carácter.'],
                roja_rival: ['Es la oportunidad: {eq} debe golpear ahora.', 'Con un jugador más, no hay excusas para {eq}.']}
        },
        periodista: {
            patriota: {
                cero: ['Los nuestros mandan y el gol merece llegar: {eq} está jugando mejor.', 'Falta puntería, pero {eq} es superior. Solo es cuestión de tiempo.'],
                empate: ['{marc}: el rival está a punto de arrepentirse, {eq} tiene más para dar.', 'Empate injusto; {eq} merece más.'],
                gana: ['{marc} y justo premio para {eq}, que lo merecía desde el inicio.', '¡Qué bien juega {eq}! Es el favorito moral del partido.'],
                gana_mucho: ['¡Exhibición de {eq}! Sin discusión, una tarde histórica.', '{marc}: {eq} le da una lección de fútbol al rival.'],
                pierde: ['Injusto ir perdiendo: {eq} es mejor y la pelota no quiere entrar.', 'El marcador miente. {eq} va a remontar.'],
                pierde_mucho: ['Un resultado que no refleja lo que vimos, aunque el golpe es duro para {eq}.', '{marc}: un mal día no define a {eq}.'],
                roja_propia: ['Expulsión muy rigurosa para {eq}; el árbitro se pasó.', 'Se la jugaron al borde y {eq} paga caro.'],
                roja_rival: ['Era roja clara: ahora {eq} puede imponer su juego.', 'Ventaja numérica merecida para {eq}.']},
            critico: {
                cero: ['Sin goles porque {eq} sigue sin tener ideas claras.', 'Mucho toque y pocas ideas: así no se rompe un partido.'],
                empate: ['{marc} y para ser sinceros, {eq} no ha merecido más.', 'Tras el empate, la pregunta es qué quiere {eq}.'],
                gana: ['{marc}, aunque el funcionamiento de {eq} sigue sin convencer.', 'Gana {eq}, pero con muchos problemas que corregir.'],
                gana_mucho: ['Gran resultado, pero el rival puso poco; no engañemos con el marcador.', 'Gana {eq} con claridad; ahora vienen rivales de verdad.'],
                pierde: ['Pierde {eq} y no sorprende: faltan ideas y carácter.', 'El rival lo hace mejor, con menos recursos que {eq}.'],
                pierde_mucho: ['Derrota sin atenuantes: {eq} fue superado en todo.', '{marc}: la autocrítica debe empezar ya.'],
                roja_propia: ['Expulsión por imprudencia: {eq} se lo busca y lo paga.', 'Un error evitable que condiciona al equipo.'],
                roja_rival: ['{eq} tiene superioridad; ahora no hay pretextos.', 'El rival se quedó con diez y {eq} debe responder.']},
            neutral: {
                cero: ['Partido muy táctico con pocas ocasiones; el 0-0 refleja el equilibrio.', 'Dos equipos que se respetan; el gol puede llegar de cualquier jugada.'],
                empate: ['{marc}: un partido parejo y de ida y vuelta.', 'Reparto de méritos; ambos tuvieron ocasiones claras.'],
                gana: ['{marc}: {eq} es más efectivo en las áreas.', 'Una ventaja corta para {eq}; el partido sigue abierto.'],
                gana_mucho: ['{marc}: {eq} marcó diferencias claras en el partido.', 'Dominio y contundencia de {eq}.'],
                pierde: ['{rival} se adelanta en el marcador; {eq} debe reaccionar.', 'Ventaja para el rival; {eq} necesita cambiar el ritmo.'],
                pierde_mucho: ['{marc}: el partido se ha ido para {eq} por falta de contundencia.', 'Una diferencia importante que {eq} difícilmente revertirá.'],
                roja_propia: ['Con la expulsión, {eq} cambia su planteamiento y defiende con diez.', 'La roja condiciona el partido: {eq} deberá jugar con orden.'],
                roja_rival: ['Expulsión que cambia el partido a favor de {eq}.', 'Un hombre más para {eq}: el partido gira.']}
        }
    };
    // Quien no es de ninguno de los dos equipos (otros países del grupo, periodistas internacionales): situaciones g_cero, g_empate,
    // g_ventaja ({gan} adelante, {per} abajo), g_goleada, g_roja.
    const C_GRUPO = {
        aficion: {
            g_cero: ['Un 0-0 en nuestro grupo, atentos a cómo afecta la tabla.', 'Nadie anota aún; desde {pais} seguimos el partido con ojos de lince.'],
            g_empate: ['{marc} en el grupo: un empate que nos viene bien a {pais}.', 'Empate, y desde {pais} hacemos cuentas.'],
            g_ventaja: ['Gana {gan}; desde {pais} tomamos nota para la tabla del grupo.', '{gan} se adelanta. Nos toca vigilar de cerca desde {pais}.'],
            g_goleada: ['¡{marc}! Para {pais}, ese gol de diferencia puede pesar al final del grupo.', 'Ojo con {gan}: así se pone difícil el grupo para {pais}.'],
            g_roja: ['Una roja en el grupo; para {pais} es una noticia a tomar en cuenta.', 'Se queda con diez: ¡{pais} está atenta!']
        },
        presidente: {
            g_cero: ['Seguimos con atención este partido del grupo; {pais} sabe que cada punto cuenta.', 'Un partido cerrado; analizamos cómo queda el grupo.'],
            g_empate: ['El empate redefine el grupo; desde {pais} lo analizamos con calma.', '{marc}: un resultado que abre posibilidades para {pais}.'],
            g_ventaja: ['{gan} marcha adelante; en {pais} hacemos cuentas con prudencia.', 'La ventaja de {gan} cambia el panorama del grupo.'],
            g_goleada: ['{marc}: un resultado así condiciona la diferencia de gol del grupo.', 'El resultado de {gan} nos obliga a replantear objetivos en {pais}.'],
            g_roja: ['Una expulsión que puede cambiar la tabla del grupo; en {pais} lo seguimos de cerca.', 'Un partido que se enreda; en {pais} lo vemos con atención.']
        },
        periodista: {
            g_cero: ['Partido sin goles hasta ahora; el grupo sigue a la espera.', 'Poco fútbol y mucho cálculo: el grupo está en juego.'],
            g_empate: ['{marc}: un empate que reordena el grupo.', 'El reparto de puntos mantiene todo abierto en el grupo.'],
            g_ventaja: ['{gan} se adelanta: la tabla del grupo empieza a moverse.', 'Con la ventaja de {gan}, el grupo cambia de panorama.'],
            g_goleada: ['{marc}: ventaja clara de {gan} y un golpe a la diferencia de goles en el grupo.', 'Una goleada que pesa en la clasificación del grupo.'],
            g_roja: ['Una expulsión que puede decidir el grupo.', 'El partido se tensa con la roja y el grupo lo siente.']
        },
        jugador: {
            g_cero: ['Desde afuera se ve un partido cerrado; en el grupo cada punto es oro.', 'Nos toca mirar con atención: un 0-0 también cuenta.'],
            g_empate: ['{marc}: un empate que mantiene todo abierto para nosotros en {pais}.', 'Un empate así deja todo para los últimos partidos.'],
            g_ventaja: ['{gan} va ganando; en {pais} sabemos lo que eso significa para el grupo.', 'Cuidado con {gan}: va a ser un rival duro.'],
            g_goleada: ['{marc}: así se ganan los grupos; nosotros en {pais} tomamos nota.', 'Esa diferencia de goles va a pesar en la tabla.'],
            g_roja: ['Una expulsión así cambia todo; un respiro para los demás del grupo.', 'Jugar con diez es muy difícil; ojalá no nos toque a nosotros.']
        }
    };
    const GRUPO_CONFIG = { aficion: 'aficion', presidente: 'presidente', periodista: 'periodista', jugador: 'jugador' };
    const VARIANTE_AFICION = { festivo: 'efusivo', ultra: 'efusivo', carismatico: 'efusivo', exigente: 'exigente', humilde: 'humilde' };
    const VARIANTE_PRESIDENTE = { institucional: 'sobrio', austero: 'sobrio', reformista: 'sobrio', ambicioso: 'presion', populista: 'presion' };
    function situacionComentario(lado, partido, c) {
        const gl = partido.golesLocal, gv = partido.golesVisita, min = partido.minuto || 0;
        const rl = c.l.rojas, rv = c.v.rojas;
        if (lado === 'local' || lado === 'visita') {
            const gp = lado === 'local' ? gl : gv, gr = lado === 'local' ? gv : gl, rp = lado === 'local' ? rl : rv, rr = lado === 'local' ? rv : rl;
            if (rp > rr) return 'roja_propia';
            if (rr > rp) return 'roja_rival';
            const d = gp - gr;
            if (d === 0) return gp === 0 ? (min >= 10 ? 'cero' : null) : 'empate';
            return d >= 2 ? 'gana_mucho' : d === 1 ? 'gana' : d === -1 ? 'pierde' : 'pierde_mucho';
        }
        if (rl !== rv) return 'g_roja';
        const d = gl - gv;
        if (d === 0) return gl === 0 ? (min >= 10 ? 'g_cero' : null) : 'g_empate';
        return Math.abs(d) >= 3 ? 'g_goleada' : 'g_ventaja';
    }
    /**
     * Lo que dice `voz` (de GET /matches/live/transmision) ahora: {texto, tag}. `partido` = {local, visitante, siglaLocal, siglaVisita, golesLocal,
     * golesVisita, minuto}; azarFn() → [0, 1). null si no hay nada que decir en este momento.
     */
    function comentario(voz, partido, eventos, azarFn) {
        const az = azarFn || Math.random;
        const c = conteos(eventos, partido.local);
        const sit = situacionComentario(voz.lado, partido, c);
        if (!sit) return null;
        const tag = `#${partido.siglaLocal || partido.local}${partido.siglaVisita || partido.visitante}`.replace(/\s+/g, '');
        let pool;
        const propio = voz.lado === 'local' || voz.lado === 'visita';
        if (propio) {
            const tipo = voz.tipo;
            const vari = tipo === 'aficion' ? VARIANTE_AFICION[voz.rasgo] || 'efusivo' : tipo === 'presidente' ? VARIANTE_PRESIDENTE[voz.rasgo] || 'sobrio'
                : (voz.sesgo === 'patriota' || voz.sesgo === 'critico') ? voz.sesgo : 'neutral';
            pool = ((C_PROPIO[tipo] || {})[vari] || {})[sit];
        } else pool = ((C_GRUPO[voz.tipo] || {})[sit]);
        if (!pool || !pool.length) return null;
        const eq = voz.lado === 'visita' ? partido.visitante : partido.local, rival = voz.lado === 'visita' ? partido.local : partido.visitante;
        const gan = partido.golesLocal >= partido.golesVisita ? partido.local : partido.visitante, per = gan === partido.local ? partido.visitante : partido.local;
        const marc = propio ? (voz.lado === 'visita' ? `${partido.visitante} ${partido.golesVisita}-${partido.golesLocal} ${partido.local}` : `${partido.local} ${partido.golesLocal}-${partido.golesVisita} ${partido.visitante}`)
            : `${partido.local} ${partido.golesLocal}-${partido.golesVisita} ${partido.visitante}`;
        const frase = pool[Math.floor(az() * pool.length)]
            .replace(/\{eq\}/g, eq).replace(/\{rival\}/g, rival).replace(/\{gan\}/g, gan).replace(/\{per\}/g, per).replace(/\{marc\}/g, marc).replace(/\{pais\}/g, voz.pais || '');
        return { tag, texto: frase, situacion: sit };
    }

    // ---------------------------------------------------------------- comentarios según el TIEMPO, el MARCADOR y la FASE
    // Contexto: tiempo T (inicio <20', primer 20-45', segundo 46-70', final 71-90', alargue >90') × marcador M visto desde el país que
    // apoya quien habla (cero, empate, gana1, gana2, pierde1, pierde2) × fase (grupos por jornada, eliminatoria, repechaje, 16vos…final).
    // El ANALISTA es hincha del país de la cadena; el INVITADO es más reflexivo y puede ser optimista o pesimista, y apoya a SU país si juega.
    // Marcadores: {eq} el país de quien habla, {rival}, {marc}, {min}, {local} {visita}.
    const CTX_TIEMPO = {
        inicio: ['Todavía es temprano.', 'Apenas va el minuto {min}.', 'Falta muchísimo partido.'],
        primer: ['Estamos en el primer tiempo.', 'Va el minuto {min}.', 'El primer tiempo avanza.'],
        segundo: ['Segundo tiempo en marcha.', 'Ya pasó el descanso.', 'Se juega el segundo tiempo.'],
        final: ['Entramos en los minutos finales.', 'Ya quedan pocos minutos.', 'El reloj empieza a pesar.'],
        alargue: ['Estamos en el tiempo extra.', 'Alargue: todo puede pasar.', 'Con 30 minutos más por jugar.'],
    };
    const CTX_MARCADOR = {
        A: {
            opt: {
                cero: ['Tranquilos, que {eq} va a encontrar su gol.', 'Sin goles todavía, pero {eq} merece mucho más.'],
                empate: ['{marc} y {eq} se siente superior; el gol está por llegar.', 'Empatado, sí, pero {eq} tiene con qué ganarlo.'],
                gana1: ['¡Vamos ganando! {eq} está haciendo las cosas bien.', '{marc} y la afición de {eq} ya sueña con más.'],
                gana2: ['¡Qué manera de jugar de {eq}! Esto ya es una fiesta.', '{marc}: {eq} está dominando y se nota.'],
                pierde1: ['Un gol abajo, pero {eq} tiene calidad para darlo vuelta.', 'Perdemos {marc}, pero yo confío en {eq}.'],
                pierde2: ['Está duro, pero con {eq} nunca se sabe: ¡hay que creer!', '{marc}... aun así {eq} no se puede rendir.'],
            },
            pes: {
                cero: ['Sin goles y {eq} sin ideas... así no se gana.', 'Esto no me gusta: {eq} juega con demasiado miedo.'],
                empate: ['{marc} y siento que {eq} se está conformando.', 'Empate que sabe a poco; {eq} tiene que atreverse.'],
                gana1: ['Vamos ganando, pero {eq} me preocupa: así se puede escapar.', '{marc} es muy corto para tanta tensión.'],
                gana2: ['Ganamos, sí, pero cuidado con relajarse, {eq}.', '{marc} y aun así veo detalles que corregir en {eq}.'],
                pierde1: ['Perdiendo {marc}... {eq} no está a la altura, y lo digo con dolor.', 'Algo no funciona en {eq} y se nota.'],
                pierde2: ['Esto ya es una pesadilla para {eq}.', '{marc}: así no se puede, {eq} tiene que replantearlo todo.'],
            },
        },
        I: {
            opt: {
                cero: ['Partido cerrado; con paciencia {eq} puede abrirlo.', 'Los 0-0 se rompen con una jugada y {eq} está cerca.'],
                empate: ['Partido parejo, y {eq} tiene argumentos para inclinarlo.', '{marc}: nada está dicho y {eq} va creciendo.'],
                gana1: ['Una ventaja corta, pero bien ganada por {eq}.', '{marc}: lo importante es que {eq} mantenga la cabeza fría.'],
                gana2: ['{eq} juega con mucha confianza; así es difícil frenarlo.', 'Con {marc}, {eq} puede administrar y jugar tranquilo.'],
                pierde1: ['Un gol no es nada: {eq} sigue en el partido.', '{marc} pero {eq} sigue generando; la reacción se huele.'],
                pierde2: ['Complicado, pero ya hemos visto remontadas peores.', 'Con {marc}, {eq} juega sin presión: no tiene nada que perder.'],
            },
            pes: {
                cero: ['Mucha tensión y poca claridad en {eq}.', 'El 0-0 empieza a pesar en {eq}: faltan ideas.'],
                empate: ['{marc}: {eq} no termina de imponer condiciones.', 'El empate no es mal resultado, pero {eq} debería pedir más.'],
                gana1: ['Cuidado con {eq}: una ventaja corta es peligrosa.', '{marc} y una sola jugada de {rival} lo cambia todo.'],
                gana2: ['Va ganando {eq}, pero he visto remontadas con menos.', '{marc}: {eq} debe cuidar la ventaja, {rival} no se va a rendir.'],
                pierde1: ['{eq} deja pasar el tiempo y eso se paga.', 'Un gol abajo y {eq} sin reacción... me preocupa.'],
                pierde2: ['Con {marc} se ve difícil: {eq} pagó caro sus errores.', 'Tarde para reaccionar: {rival} manejó mejor el partido.'],
            },
        },
    };
    // frases propias de ciertos momentos (tiempo_marcador; si no hay con el marcador exacto se prueba sin el número: final_gana, alargue_pierde…)
    const CTX_MOMENTO = {
        A: {
            final_empate: ['¡Queda poco y está {marc}! ¡Vamos {eq}, a buscarlo!', 'Los minutos se acaban con el {marc}: {eq} tiene que ir por todo.'],
            final_gana1: ['¡Aguanten, {eq}! Solo hay que cuidar este golecito.', 'Falta poco y {eq} gana: ¡que se acabe ya!'],
            final_gana2: ['{marc} y a gozar los minutos finales, ¡qué orgullo de {eq}!', 'Ya casi está: {eq} lo tiene en el bolsillo.'],
            final_pierde1: ['Se acaba el tiempo y {eq} tiene que arriesgar todo.', '¡Ahora o nunca, {eq}! Un gol y se salva.'],
            final_pierde2: ['Casi sin tiempo y {marc}: qué triste, {eq}.', 'Ya no alcanza el tiempo; {eq} se va con dolor.'],
            final_cero: ['Sin goles y casi sin tiempo: {eq} tiene que sacar algo ya.', 'Faltan minutos y {eq} sigue sin pegarle: ¡hay que arriesgar!'],
            alargue_empate: ['Tiempo extra y {marc}: aquí gana el que tenga más corazón, ¡vamos {eq}!', 'Alargue: {eq} tiene que sacar fuerzas de donde sea.'],
            alargue_gana: ['En el alargue y arriba: ¡que {eq} no se descuide ahora!', 'Un gol arriba en tiempo extra... ¡qué nervios, {eq}!'],
            alargue_pierde: ['Tiempo extra y {eq} abajo: se juega todo en estos minutos.', 'Alargue en contra: {eq} no puede bajar los brazos.'],
            inicio_gana1: ['Gol tempranero de {eq}: ¡así se empieza!', 'Apenas arranca y {eq} ya golpeó primero.'],
            inicio_gana2: ['¡Y apenas empieza! {eq} ya lo tiene {marc}.', 'Qué arranque de {eq}: {marc} en pocos minutos.'],
            inicio_pierde1: ['Un gol temprano en contra... {eq} tiene todo el partido para reaccionar.', 'Mal arranque de {eq}, pero es largo el camino.'],
            inicio_pierde2: ['Apenas empezó y ya estamos {marc}... ¡esto no puede ser!', 'Un arranque de pesadilla para {eq}.'],
            segundo_empate: ['Segundo tiempo y {marc}: se define en estos minutos, {eq}.', 'Con el {marc} la segunda parte es de {eq} si se anima.'],
            segundo_pierde1: ['Segundo tiempo y {eq} abajo: toca mover las piezas.', '{eq} tiene que reaccionar ya, que el reloj corre.'],
            segundo_gana1: ['Segundo tiempo con {eq} arriba: ¡ahora a cerrarlo!', 'Con la ventaja, {eq} debe controlar y ya.'],
            primer_cero: ['Seguimos sin goles: {eq} tiene que soltarse un poco.', 'Va el primer tiempo y no pasa nada: {eq} puede más.'],
        },
        I: {
            final_empate: ['Con {marc} y poco tiempo, el que se atreva puede llevarse el partido.', 'A estas alturas los nervios pesan más que la técnica.'],
            final_gana1: ['Ahora lo difícil es administrar; {eq} tiene que cuidar la pelota.', 'Una ventaja de un gol en los minutos finales: son los más largos.'],
            final_gana2: ['Ya está resuelto; ahora es cuidar piernas y evitar lesiones.', '{marc} y a cerrar el partido con calma.'],
            final_pierde1: ['Toca arriesgar: {eq} no tiene nada que perder.', 'En estos minutos se ve el carácter de {eq}.'],
            final_pierde2: ['Es difícil: {eq} ya casi no tiene tiempo para una remontada.', 'Con {marc} y los minutos contados, {eq} se despide.'],
            final_cero: ['Un 0-0 en el final: cualquier descuido define el partido.', 'Con este marcador el que se equivoca, pierde.'],
            alargue_empate: ['En el alargue las piernas pesan: gana el que tenga la cabeza más fría.', 'Treinta minutos más: es un partido nuevo.'],
            alargue_gana: ['Arriba en el alargue: ahora a defender con orden.', 'Una ventaja en el tiempo extra pesa el doble.'],
            alargue_pierde: ['Abajo en el alargue hay que arriesgar sin perder la cabeza.', 'En el tiempo extra cada error es una sentencia.'],
            inicio_gana1: ['Un gol temprano cambia el plan de los dos.', '{eq} golpeó primero: ahora {rival} tiene que salir.'],
            inicio_gana2: ['Con {marc} tan pronto, el rival tiene que replantearlo todo.', 'Dos goles en pocos minutos cambian cualquier guion.'],
            inicio_pierde1: ['Es temprano: un gol en contra no define nada.', 'Hay que respirar: falta muchísimo partido.'],
            inicio_pierde2: ['Un arranque así es difícil de levantar, pero hay tiempo.', 'Con {marc} tan pronto, a {eq} no le queda más que reorganizarse.'],
            segundo_empate: ['El segundo tiempo es de los que mejor se cuidan físicamente.', 'Con {marc}, los cambios van a ser clave en esta parte.'],
            segundo_pierde1: ['Un gol abajo y toda la segunda parte por delante: hay margen.', 'Los cambios y el orden pueden cambiar este partido.'],
            segundo_gana1: ['La ventaja es corta: hay que cuidarla con la pelota.', 'Con un gol arriba, el segundo tiempo se juega con cabeza.'],
            primer_cero: ['Los dos se estudian; el primer gol va a marcar el partido.', 'Partido de ajedrez en este primer tiempo.'],
        },
    };
    // por la fase del torneo (perspectiva del país que apoya quien habla)
    const CTX_FASE = {
        grupos_1: { A: ['Primer partido del grupo: arrancar bien es clave para {eq}.', 'Estos puntos de arranque valen oro para {eq}.'],
                    I: ['En la primera jornada nadie quiere perder: se juega con prudencia.', 'Un debut en el Mundial siempre pesa; hay que ganarse la confianza.'] },
        grupos_2: { A: ['Segunda jornada: aquí se empieza a definir el grupo de {eq}.', 'Con este partido {eq} se acerca o se aleja de los octavos.'],
                    I: ['La segunda jornada suele definir quién depende de sí mismo.', 'Un resultado hoy y el grupo cambia por completo.'] },
        grupos_ultima: { A: ['Última jornada: {eq} se juega el pase, ¡no hay margen!', 'Todo se define hoy: {eq} no puede fallar.'],
                         I: ['En la última jornada los cálculos pesan tanto como el juego.', 'Con el pase en juego, cada gol puede cambiar la tabla.'] },
        clasif: { A: ['Cada partido de la eliminatoria cuenta: {eq} no puede regalar puntos.', 'La clasificación se gana jornada a jornada, {eq}.'],
                  I: ['Las eliminatorias son largas, pero cada punto se paga caro.', 'Aquí no hay partidos menores: todo suma.'] },
        clasif_ultima: { A: ['Último partido de la eliminatoria: {eq} se juega el sueño mundialista.', 'Hoy se define si {eq} sigue en la pelea.'],
                         I: ['Es la última oportunidad: todo se decide ahora.', 'Al final de una eliminatoria cada detalle pesa el doble.'] },
        repechaje: { A: ['Repechaje: una final por un boleto, ¡vamos {eq}!', 'Un partido por un lugar en el Mundial: {eq} lo tiene que dar todo.'],
                     I: ['Un repechaje es de los partidos más nerviosos: se juega con el corazón.', 'Aquí no importa el historial, importa el día.'] },
        '16vos': { A: ['16vos de final: aquí o te quedas o sigues, ¡vamos {eq}!', 'Eliminación directa: {eq} no puede dejar nada atrás.'],
                   I: ['Desde 16vos un error y te vas a casa.', 'En eliminación directa el que arriesga más no siempre gana.'] },
        '8vos': { A: ['Octavos de final: {eq} está a un paso de los cuartos.', 'Cada jugada vale una vida, {eq}.'],
                  I: ['En octavos ya no hay partidos fáciles.', 'Los octavos se ganan con orden y un poco de fe.'] },
        '4tos': { A: ['Cuartos de final: {eq} está tocando la historia.', 'A ganar para meterse entre los cuatro mejores, {eq}.'],
                  I: ['En cuartos todo se juega en los detalles.', 'Aquí el que se descuida se despide del Mundial.'] },
        semis: { A: ['¡Semifinal! {eq} a 90 minutos de la gran final.', 'Una semifinal así se recuerda toda la vida, {eq}.'],
                 I: ['Semifinal: los nervios, las piernas y la cabeza deciden.', 'En semifinales no se juega bonito, se juega para ganar.'] },
        tercer: { A: ['El partido por el tercer lugar: {eq} quiere cerrar con orgullo.', 'Un tercer lugar también es historia para {eq}.'],
                  I: ['El tercer lugar es un partido raro: duele la semifinal, pero hay una medalla.', 'Se juega con menos tensión, pero el orgullo pesa.'] },
        final: { A: ['¡La final! {eq} está a un paso de la gloria.', 'Todo el país mirando: ¡esta es la final de {eq}!'],
                 I: ['Una final no se juega, se sobrevive.', 'En una final nadie recuerda al que perdió.'] },
    };
    // sin país al que apoyar (la cadena y el invitado no son de los equipos): lectura neutral del partido
    const CTX_NEUTRO = {
        A: { cero: ['Con {marc} al minuto {min}, el partido sigue abierto.', 'Sin goles y mucha tensión entre {local} y {visita}.'],
             empate: ['{marc} entre {local} y {visita}: partido parejo.', 'Empate en el marcador y todo por decidir.'],
             ventaja: ['Con {marc} al minuto {min}, el partido se inclina.', 'Una ventaja que {local} y {visita} tendrán que gestionar.'],
             goleada: ['{marc} ya es un resultado difícil de revertir.', 'Una diferencia así cambia todo el partido.'] },
        I: { cero: ['Dos equipos que se respetan: el primer gol lo cambia todo.', 'El 0-0 es justo hasta ahora, pero no durará.'],
             empate: ['Un partido muy parejo; cualquier detalle lo define.', '{marc} y los dos con argumentos para ganar.'],
             ventaja: ['Una ventaja corta que se puede escapar en cualquier jugada.', 'Quien está abajo no tiene nada que perder.'],
             goleada: ['Ya es difícil que el partido cambie.', 'Una diferencia grande y el rival sin respuestas.'] },
    };
    const PRESENTA = ['{quien} presenta', '{quien} les trae', 'Un dato de {quien}'];

    const api = { crear, clasificar, grafico, estadoTanda, resumen, estadisticas, elegirDato, elegirPleca, plecaFormacion, conteos, comentario, PRESENTA, POSICIONES, tocaMarcador, apellido, limpiarDescripcion, rellenar, azar, CLASES, FRASES, CHARLA };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    root.Narracion = api;
})(typeof window !== 'undefined' ? window : globalThis);
