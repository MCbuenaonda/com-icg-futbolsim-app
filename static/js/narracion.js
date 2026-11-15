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
        // el desenlace de un disparo (atajada, desviado, bloqueado, córner) SIEMPRE se narra: si no, la jugada queda a medias (preparación o gol sí, pero qué pasó con el tiro no)
        atajada:    { p: 1.0,  prio: 2, cadena: ['N', 'A:0.45', 'I:0.3'] },
        remate:     { p: 1.0,  prio: 2, cadena: ['N', 'A:0.4', 'I:0.25'] },
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
                // con opinión: el analista (del país de la cadena) con pasión y el invitado con una mirada objetiva
                if (pro && lado && (codigo === 'A' || (codigo === 'I' && mesas[mesaIdx].invitado)) && rng() < (codigo === 'A' ? 0.85 : 0.7)) {
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
    function elegirDato(eventos, usados, azarFn) {
        const jugadores = estadisticas(eventos);
        if (!jugadores.length) return null;
        const candidatos = [];
        DATOS.forEach(d => {
            const ordenados = jugadores.filter(p => d.valor(p) >= d.minimo).sort((a, b) => d.valor(b) - d.valor(a));
            if (!ordenados.length) return;
            const lider = ordenados[0];
            if (ordenados[1] && d.valor(ordenados[1]) === d.valor(lider) && d.clave !== 'figura') return;   // empate en el primer puesto: no hay líder
            candidatos.push({ clave: d.clave, titulo: d.titulo, etiqueta: d.etiqueta, jugador: lider.nombre, equipo: lider.equipo, cifra: d.cifra(lider) });
        });
        if (!candidatos.length) return null;
        const frescos = candidatos.filter(c => !(usados || []).includes(c.clave));
        const pool = frescos.length ? frescos : candidatos;
        return pool[Math.floor((azarFn || Math.random)() * pool.length)];
    }

    // ---------------------------------------------------------------- tableros de estadísticas por equipo (plecas patrocinadas)
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
    const TABLEROS = [
        { clave: 'dominio', titulo: 'Dominio del partido', etiqueta: 'ESTADÍSTICAS', minimo: 8, filas: [
            { nombre: 'Posesión', campo: 'jugadas', pct: true }, { nombre: 'Remates', campo: 'remates' }, { nombre: 'Tiros a puerta', campo: 'apuerta' }, { nombre: 'Córners', campo: 'corners' }] },
        { clave: 'duelos', titulo: 'Duelos y recuperaciones', etiqueta: 'RENDIMIENTO', minimo: 6, filas: [
            { nombre: 'Regates ganados', campo: 'regates' }, { nombre: 'Recuperaciones', campo: 'recup' }, { nombre: 'Atajadas', campo: 'atajadas' }, { nombre: 'Fueras de lugar', campo: 'fueras' }] },
        { clave: 'disciplina', titulo: 'Juego y disciplina', etiqueta: 'DISCIPLINA', minimo: 4, filas: [
            { nombre: 'Faltas', campo: 'faltas' }, { nombre: 'Amarillas', campo: 'amarillas' }, { nombre: 'Rojas', campo: 'rojas' }] },
    ];
    /** Un tablero con las cifras de cada equipo: `usados` = claves recientes (no repite hasta agotar), null si todavía no hay nada que mostrar. */
    function elegirTablero(eventos, partido, usados, azarFn) {
        if (!partido) return null;
        const c = conteos(eventos, partido.local);
        const listos = TABLEROS.map(t => {
            const filas = t.filas.map(f => {
                const l = c.l[f.campo], v = c.v[f.campo], tot = l + v;
                return { nombre: f.nombre, l: f.pct ? Math.round(tot ? 100 * l / tot : 50) : l, v: f.pct ? 100 - Math.round(tot ? 100 * l / tot : 50) : v,
                         pct: !!f.pct, frac: tot ? l / tot : 0.5, tot };
            });
            const total = filas.reduce((a, f) => a + (f.pct ? 0 : f.tot), 0) + (filas[0].pct ? filas[0].tot : 0);
            return { clave: t.clave, titulo: t.titulo, etiqueta: t.etiqueta, filas, total, minimo: t.minimo };
        }).filter(t => t.total >= t.minimo);
        if (!listos.length) return null;
        const frescos = listos.filter(t => !(usados || []).includes(t.clave));
        const pool = frescos.length ? frescos : listos;
        return pool[Math.floor((azarFn || Math.random)() * pool.length)];
    }
    /** El planteamiento de cada equipo al arrancar (esquema y estilo), en el formato del tablero. */
    function tableroFormacion(planteamiento, partido) {
        const pl = (planteamiento && planteamiento.local) || null, pv = (planteamiento && planteamiento.visita) || null;
        if (!pl || !pv || !partido) return null;
        return { clave: 'formacion', titulo: 'Así salen a la cancha', etiqueta: 'ALINEACIONES', formacion: true,
                 filas: [{ nombre: 'Formación', l: pl.esquema, v: pv.esquema, texto: true }, { nombre: 'Estilo', l: pl.etiqueta || '', v: pv.etiqueta || '', texto: true }] };
    }
    const PRESENTA = ['{quien} presenta', '{quien} les trae', 'Un dato de {quien}'];

    const api = { crear, clasificar, grafico, estadoTanda, resumen, estadisticas, elegirDato, elegirTablero, tableroFormacion, conteos, PRESENTA, POSICIONES, tocaMarcador, apellido, limpiarDescripcion, rellenar, azar, CLASES, FRASES, CHARLA };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    root.Narracion = api;
})(typeof window !== 'undefined' ? window : globalThis);
