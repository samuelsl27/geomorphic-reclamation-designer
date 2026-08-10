# -*- coding: utf-8 -*-
"""Contenido de la guía bilingüe del complemento (neutro, sin caso de estudio)."""

# (nombre del ajuste tal cual aparece en la interfaz, inglés, español)
GENERAL = [
 ("__what", """<b>What this plugin does.</b> It designs a reclaimed landform the way a mature
natural catchment is built: a drainage network of channels with concave
longitudinal profiles, meanders sized by the flow they carry, ridges and swales
on the hillslopes, and the surface that ties all of it together. The result is a
landform that sheds water the way the surrounding terrain does, so it needs no
permanent structures to stay stable. This is the fluvial-geomorphic
(Natural Regrade / GeoFluv-type) approach, as published by Bugosh &amp; Martín
Duque (2024). This plugin is an independent implementation of that published
method and is not affiliated with, endorsed by or derived from its software.""",
 """<b>Qué hace el complemento.</b> Diseña una restauración construida como se construye
una cuenca natural madura: una red de drenaje con canales de perfil longitudinal
cóncavo, meandros dimensionados por el caudal que llevan, crestas y vaguadas en
las laderas, y la superficie que enlaza todo. El resultado evacua el agua como
lo hace el terreno del entorno, así que no necesita estructuras permanentes para
mantenerse estable. Es el método fluvio-geomórfico (tipo Natural Regrade /
GeoFluv) publicado por Bugosh y Martín Duque (2024). Este complemento es una
implementación independiente de ese método publicado y no está afiliado,
respaldado ni derivado de su programa."""),
 ("__method", """<b>The design sequence.</b> Everything hangs off three inputs: a boundary
polygon (where you may reshape), one or more valley-bottom polylines (where the
water will run) and a DEM of the existing ground (what you start from). From
there the plugin builds, in order: the network topology (which channel feeds
which, on which bank), the sub-watersheds, the longitudinal profile of every
channel, the peak flow at every station, the plan geometry (zig-zag where the
slope is steep, meanders where it is gentle), the ridges and swales of each
hillslope, the design surface, the contours and the earthwork balance.""",
 """<b>La secuencia de diseño.</b> Todo cuelga de tres entradas: un polígono de
límite (dónde se puede remodelar), una o varias polilíneas de fondo de valle
(por dónde correrá el agua) y un DEM del terreno existente (de qué se parte). A
partir de ahí el complemento construye, en este orden: la topología de la red
(qué canal alimenta a cuál y por qué margen), las subcuencas, el perfil
longitudinal de cada canal, el caudal punta en cada estación, la geometría en
planta (zigzag donde la pendiente es fuerte, meandros donde es suave), las
crestas y vaguadas de cada ladera, la superficie de diseño, las curvas de nivel
y el balance de tierras."""),
 ("__iterate", """<b>It is meant to be iterated.</b> Every element is an ordinary QGIS layer that
you can edit. Move a valley bottom, drag the vertices of a ridge, change a
setting, and regenerate: the design is rebuilt from the inputs. Nothing is
frozen. The usual loop is Preview → look at the drainage density → Draw Design
Surface → look at the cut/fill → adjust → repeat.""",
 """<b>Está pensado para iterar.</b> Cada elemento es una capa normal de QGIS que
puedes editar. Mueve un fondo de valle, arrastra los vértices de una cresta,
cambia un ajuste y regenera: el diseño se reconstruye a partir de las entradas.
Nada queda congelado. El ciclo habitual es Preview → mirar la densidad de
drenaje → Draw Design Surface → mirar el corte/relleno → ajustar → repetir."""),
 ("File...", """Opens, saves and names the design project (<code>.grd.json</code>). The
project file stores the settings, the list of channels and <i>references</i> to
the input layers and features — not the coordinates. That is deliberate: you can
edit the input polylines afterwards and regenerate, and the project still points
at them. Keep the project file next to the QGIS project so relative paths stay
short.""",
 """Abre, guarda y nombra el proyecto de diseño (<code>.grd.json</code>). El
fichero guarda los ajustes, la lista de canales y <i>referencias</i> a las capas
y entidades de entrada, no las coordenadas. Es a propósito: puedes editar
después las polilíneas de entrada y regenerar, y el proyecto sigue apuntando a
ellas. Guarda el fichero junto al proyecto de QGIS para que las rutas relativas
sean cortas."""),
 ("Settings...", """Opens the <i>Global Settings</i> dialog (documented in the
Setup tab of this guide). <b>Load / Save As</b> inside that dialog store the
settings in a separate <code>.grd-settings.json</code>, so a calibrated set
of values can be reused across projects with similar material and climate.""",
 """Abre el diálogo <i>Global Settings</i> (documentado en la
pestaña Setup de esta guía). <b>Load / Save As</b> dentro de ese diálogo guardan
los ajustes en un <code>.grd-settings.json</code> aparte, de modo que un
juego de valores ya calibrado se puede reutilizar en proyectos con material y
clima parecidos."""),
 ("__layers", """<b>Layer organisation.</b> Everything lands in the layer panel under
<code>Geomorphic Reclamation &lt;project&gt;</code>, split into <code>01 Inputs</code> (boundary,
valley bottoms), <code>02 Design</code> (channels, banks, cross-sections,
ridges, sub-ridges, swales), <code>03 Output</code> (design surface, contours,
sub-watersheds) and <code>04 Analysis</code> (cut/fill raster, centroids, haul
regions and routes). Layer names all start with <code>GRD_</code> and the
attribute fields follow the report nomenclature, so they can be styled, joined
and exported like any other QGIS data.""",
 """<b>Organización de las capas.</b> Todo aparece en el panel de capas bajo
<code>Geomorphic Reclamation &lt;proyecto&gt;</code>, repartido en <code>01 Inputs</code>
(límite, fondos de valle), <code>02 Design</code> (canales, bordes, secciones,
crestas, subcrestas, vaguadas), <code>03 Output</code> (superficie de diseño,
curvas, subcuencas) y <code>04 Analysis</code> (ráster de corte/relleno,
centroides, regiones y rutas de acarreo). Todos los nombres empiezan por
<code>GRD_</code> y los campos siguen la nomenclatura de los informes, así que se
pueden simbolizar, unir y exportar como cualquier dato de QGIS."""),
 ("__storage", """<b>Where the layers live.</b> When you press <i>Create Design Layers</i> you
choose the storage: <b>virtual (memory)</b> is the fastest but is lost when QGIS
closes; <b>a folder you choose</b> writes each layer as a GeoPackage; <b>the
project folder</b> creates a new dated sub-folder next to the saved
<code>.qgz</code> so each run keeps its own complete layer set. Use memory while
exploring and a folder once the design matters.""",
 """<b>Dónde se guardan las capas.</b> Al pulsar <i>Create Design Layers</i>
eliges el almacenamiento: <b>virtual (memoria)</b> es el más rápido pero se
pierde al cerrar QGIS; <b>una carpeta que elijas</b> escribe cada capa como
GeoPackage; <b>la carpeta del proyecto</b> crea una subcarpeta nueva con fecha y
hora junto al <code>.qgz</code> guardado, de modo que cada generación conserva
su juego completo de capas. Usa memoria mientras exploras y una carpeta cuando
el diseño ya importa."""),
 ("__units", """<b>Units and CRS.</b> The project must be in a projected CRS in metres.
Lengths and elevations are metres, areas hectares, flows m³/s, drainage density
metres of channel per hectare, and rainfall is entered in centimetres in the
Global Settings dialog (as in the original) but handled internally in
millimetres. Slopes are percentages and are <b>negative downstream</b>.""",
 """<b>Unidades y SRC.</b> El proyecto debe estar en un SRC proyectado en metros.
Las longitudes y cotas van en metros, las áreas en hectáreas, los caudales en
m³/s, la densidad de drenaje en metros de canal por hectárea, y la lluvia se
introduce en centímetros en el diálogo de ajustes globales (como en el original)
aunque internamente se maneja en milímetros. Las pendientes son porcentajes y
son <b>negativas aguas abajo</b>."""),
]

SETUP = [
 ("__intro", """The Setup tab collects the three things the design cannot start without, in
the order you need them.""",
 """La pestaña Setup reúne las tres cosas sin las que el diseño no puede empezar,
en el orden en que las necesitas."""),
 ("Create Design Layers", """Builds the group tree and the two empty input layers
(<code>GRD_Boundary</code>, <code>GRD_ValleyBottoms</code>) so you can draw into
them, and asks where the layers should be stored. You can skip it entirely and
point the plugin at your own polygon and line layers instead — the selectors
accept any layer of the right geometry type.""",
 """Crea el árbol de grupos y las dos capas de entrada vacías
(<code>GRD_Boundary</code>, <code>GRD_ValleyBottoms</code>) para que dibujes en
ellas, y pregunta dónde guardar las capas. Puedes saltártelo por completo y
apuntar el complemento a tus propias capas de polígono y de línea: los
selectores aceptan cualquier capa del tipo de geometría correcto."""),
 ("Design Boundary", """Pick the polygon that delimits what may be reshaped. Everything is measured
inside it: the sub-watershed areas, the drainage density, the cut and fill
volumes, and the design surface is clipped to it. Its edge is also the boundary
condition of the design: ridges and hillslope lines that reach it tie into the
existing ground elevation there, so the new landform meets the surrounding
terrain without a step. A boundary drawn tight around the disturbance leaves
little room for the drainage network; a generous one gives the design somewhere
to develop.""",
 """Elige el polígono que delimita lo que se puede remodelar. Todo se mide dentro
de él: las áreas de las subcuencas, la densidad de drenaje, los volúmenes de
corte y relleno, y la superficie de diseño se recorta a él. Su borde es además
la condición de contorno del diseño: las crestas y las líneas de ladera que
llegan a él empalman con la cota del terreno existente, de modo que la forma
nueva se encuentra con el terreno del entorno sin escalón. Un límite ajustado a
la zona alterada deja poco sitio a la red de drenaje; uno generoso le da espacio
para desarrollarse."""),
 ("Area (ha)", """Read-only. The area of the accepted boundary. It is the denominator of the
drainage density, so watch it: it tells you how much channel length the design
should have.""",
 """Solo lectura. El área del límite aceptado. Es el denominador de la densidad de
drenaje, así que conviene tenerlo presente: te dice cuánta longitud de canal
debería tener el diseño."""),
 ("Select Main Channel", """Pick the polyline that will be the main valley bottom — the trunk of the
network, the one that carries the water out of the area. Draw it as the <i>valley
bottom</i>, not as the channel: the meanders are added by the plugin around this
line. Its two ends matter: the lower one is the outlet (its elevation and mouth
slope are the most critical values of the whole design) and the upper one is the
head.""",
 """Elige la polilínea que será el fondo de valle principal: el tronco de la red,
el que saca el agua de la zona. Dibújala como <i>fondo de valle</i>, no como
cauce: los meandros los añade el complemento alrededor de esta línea. Sus dos
extremos importan: el inferior es la desembocadura (su cota y su pendiente de
boca son los valores más críticos de todo el diseño) y el superior es la
cabecera."""),
 ("Data for main channel", """Read-only feedback sampled from the DEM and the design: <b>Head Elev.</b> and
<b>Base Elev.</b> are the elevations at the two ends, <b>Valley Length</b> the
plan length of the polyline, and <b>Drainage Density</b> the ratio of channel
length to sub-watershed area, with a traffic light against the target. Use these
four numbers as your first sanity check: if the head is lower than the mouth the
polyline is drawn backwards.""",
 """Información de vuelta, solo lectura, tomada del DEM y del diseño: <b>Head
Elev.</b> y <b>Base Elev.</b> son las cotas de los dos extremos, <b>Valley
Length</b> la longitud en planta de la polilínea, y <b>Drainage Density</b> la
relación entre longitud de canal y área de subcuenca, con semáforo frente al
objetivo. Usa estos cuatro números como primera comprobación: si la cabecera
está más baja que la boca, la polilínea está dibujada al revés."""),
 ("Surface for Elevations", """The DEM of the ground you start from. It supplies the head and mouth
elevations, the elevation at which the design ties into the boundary, and it is
the reference against which cut and fill are measured. Its resolution sets the
precision of the volumes: a coarse DEM gives smooth but approximate volumes.
Without a DEM the plugin can still lay out the network, but elevations have to be
entered by hand and there is no earthwork balance.""",
 """El DEM del terreno de partida. Proporciona las cotas de cabecera y boca, la
cota a la que el diseño empalma con el límite, y es la referencia contra la que
se miden el corte y el relleno. Su resolución fija la precisión de los
volúmenes: un DEM grueso da volúmenes suaves pero aproximados. Sin DEM el
complemento puede trazar la red, pero las cotas hay que introducirlas a mano y
no hay balance de tierras."""),
 ("__gs", """<hr><h3>Global Settings  <span class='sub'>(Settings... button)</span></h3>
These are the local variables of the method: they describe the material, the
climate and the geometry of a stable landform at this particular site. They are
the values you should calibrate against a natural reference area nearby.""",
 """<hr><h3>Global Settings  <span class='sub'>(botón Settings...)</span></h3>
Son las variables locales del método: describen el material, el clima y la
geometría de una forma estable en este sitio concreto. Son los valores que
conviene calibrar contra un área natural de referencia cercana."""),
 ("Maximum distance from ridgeline to channel's head (m)", """How far below the drainage divide a stable channel head can start. It is the
length of hillslope that can shed water without incising. <b>Larger</b> values
give longer hillslopes, higher ridges above the channel and fewer, longer
channels — more earthwork and a coarser drainage texture. <b>Smaller</b> values
push channel heads up towards the divide, giving a denser network. If your
channel heads end up further from the divide than this value the plugin warns
you: that hillslope is likely to erode and cut its own channel.""",
 """A qué distancia por debajo de la divisoria puede arrancar una cabecera de canal
estable. Es la longitud de ladera capaz de evacuar agua sin encajarse. Valores
<b>mayores</b> dan laderas más largas, crestas más altas sobre el canal y menos
canales pero más largos: más movimiento de tierras y una textura de drenaje más
gruesa. Valores <b>menores</b> empujan las cabeceras hacia la divisoria y dan
una red más densa. Si alguna cabecera queda más lejos de la divisoria que este
valor, el complemento avisa: esa ladera tenderá a erosionarse y a excavar su
propio canal."""),
 ("Maximum convex portion of sub-ridge", """The length of the convex (rounded) top of every hillslope line, expressed
either as <b>1.5 × the ridgeline-to-head distance</b> or as a <b>percent of the
overall length</b>. A natural hillslope is convex near the divide, roughly
straight in the middle and concave at the foot; this value decides how much of
it is the convex crown. <b>Longer</b> convex portions give softer, more rounded
divides and steeper mid-slopes; <b>shorter</b> ones give sharper crests. The
percent mode adapts to each hillslope length, the factor mode keeps the same
absolute length everywhere.""",
 """La longitud de la coronación convexa (redondeada) de cada línea de ladera,
expresada como <b>1.5 × la distancia cresta-cabecera</b> o como un <b>porcentaje
de la longitud total</b>. Una ladera natural es convexa junto a la divisoria,
casi recta en el centro y cóncava al pie; este valor decide cuánto de ella es la
coronación convexa. Porciones convexas <b>más largas</b> dan divisorias más
suaves y redondeadas y laderas medias más empinadas; <b>más cortas</b> dan
crestas más agudas. El modo porcentaje se adapta a la longitud de cada ladera;
el modo factor mantiene la misma longitud absoluta en todas."""),
 ("Maximum convex portion of swale (m)", """Same idea for the swales (the valley lines of the hillslope). Off by default,
which makes swales almost entirely concave — they drop away from the divide
immediately, which is what gives the hillslope its relief against the ridges. If
you enable it, swales get a convex head too and the hillslope becomes flatter and
less articulated.""",
 """La misma idea para las vaguadas (las líneas de valle de la ladera).
Desactivado por defecto, lo que hace las vaguadas casi enteramente cóncavas:
caen desde la divisoria de inmediato, que es lo que da a la ladera su relieve
frente a las crestas. Si lo activas, las vaguadas tienen también cabeza convexa
y la ladera queda más tendida y menos articulada."""),
 ("Slope at the mouth of the main valley bottom channel (%)", """The most critical value in the design. It fixes the gradient of the outlet, and
because the whole profile hangs from it, it sets the elevation of the entire
channel and therefore the cut/fill balance. <b>Steeper</b> (more negative) sinks
the downstream reach: much more cut, much less fill. <b>Flatter</b> raises it:
more fill. It has a hard geometric limit — it must be <i>less</i> steep than the
average valley gradient (mouth-to-head drop over length), otherwise no monotonic
concave profile exists and the plugin flattens the profile to a straight line and
warns you. Match it to the grade of the receiving channel it discharges into.""",
 """El valor más crítico del diseño. Fija la pendiente de la desembocadura y, como
todo el perfil cuelga de ella, determina la cota de todo el canal y por tanto el
balance corte/relleno. <b>Más empinada</b> (más negativa) hunde el tramo final:
mucho más corte y mucho menos relleno. <b>Más tendida</b> lo eleva: más relleno.
Tiene un límite geométrico duro: debe ser <i>menos</i> empinada que la pendiente
media del valle (desnivel cabecera-boca partido por la longitud), porque si no
no existe un perfil monótono y cóncavo; en ese caso el complemento aplana el
perfil a una recta y avisa. Ajústala a la pendiente del cauce receptor al que
desagua."""),
 ("'A' channel reach (m)", """Half the wavelength of the zig-zag used on channels steeper than 4 % (type A
channels, which do not meander: they step). <b>Shorter</b> reaches give a
tighter zig-zag, more direction changes and — because the method puts a ridge and
a swale at every zig-zag apex — a much denser set of hillslope lines on the steep
reaches. <b>Longer</b> reaches give a straighter, coarser steep reach. This
value, not the sub-ridge spacing, controls hillslope line density above 4 %.""",
 """La semilongitud de onda del zigzag que se usa en los canales de más del 4 % de
pendiente (canales tipo A, que no meandrean: escalonan). Un <i>reach</i> <b>más
corto</b> da un zigzag más apretado, más cambios de dirección y —como el método
coloca una cresta y una vaguada en cada ápice del zigzag— un conjunto de líneas
de ladera mucho más denso en los tramos empinados. Uno <b>más largo</b> da un
tramo empinado más recto y más grueso. Es este valor, y no el espaciado de
subcrestas, el que controla la densidad de líneas de ladera por encima del
4 %."""),
 ("'A' channel sinuosity (&lt;1.2)", """Sinuosity of the zig-zag reaches: channel length divided by valley length.
Steep channels are close to straight in nature, so the useful range is roughly
1.02–1.20. <b>Higher</b> lengthens the steep reach and lowers its gradient
slightly; <b>lower</b> makes it straighter and steeper. Above ~1.2 the shape
stops looking like a steep natural channel.""",
 """Sinuosidad de los tramos en zigzag: longitud de canal partida por longitud de
valle. Los canales empinados son casi rectos en la naturaleza, así que el rango
útil va aproximadamente de 1.02 a 1.20. <b>Más alta</b> alarga el tramo empinado
y baja algo su pendiente; <b>más baja</b> lo hace más recto y más empinado. Por
encima de ~1.2 la forma deja de parecerse a un canal natural empinado."""),
 ("2-yr, 1-hr (cm)", """The storm that shapes the channel. The bankfull section — the one the channel
carries without spilling — is sized for the peak flow of this event. <b>Larger</b>
rainfall means a bigger bankfull channel, and because the meander geometry is
derived from the bankfull width, also longer meander wavelengths and hillslope
lines spaced further apart. <b>Smaller</b> gives a tighter, more finely textured
network. Take it from local rainfall records, not from a default.""",
 """La tormenta que da forma al cauce. La sección bankfull —la que el canal lleva
sin desbordar— se dimensiona para el caudal punta de este evento. Una lluvia
<b>mayor</b> significa un cauce bankfull más grande y, como la geometría del
meandro se deriva de la anchura bankfull, también longitudes de onda de meandro
mayores y líneas de ladera más separadas. <b>Menor</b> da una red más apretada y
de textura más fina. Tómala de los registros de lluvia locales, no de un valor
por defecto."""),
 ("50-yr, 6-hr (cm)", """The storm that sizes the flood-prone area: the width the water occupies when it
spills out of the bankfull channel. The method introduces the whole 6-hour depth
as if it arrived instantaneously, which is deliberately conservative. It
determines the entrenchment ratio (flood-prone width over bankfull width): a
wide flood-prone area lets a big event spread out and lose energy, a narrow one
keeps it confined and erosive.""",
 """La tormenta que dimensiona el área inundable: la anchura que ocupa el agua
cuando desborda del cauce bankfull. El método introduce la lluvia entera de las
6 horas como si llegase instantáneamente, lo que es conservador a propósito.
Determina el ratio de atrincheramiento (anchura inundable partida por anchura
bankfull): un área inundable ancha deja que un evento grande se extienda y
pierda energía; una estrecha lo mantiene confinado y erosivo."""),
 ("Target drainage density (m/ha)", """How much channel length per hectare a mature catchment has in this material
and climate. It is the single best indicator that the network has the right
texture, and it is what you measure in a natural reference area. The plugin does
not force it: it compares the design against it and shows a traffic light per
channel. <b>Higher</b> targets demand more or longer valley bottoms; if the
design falls short, the hillslopes between channels are too long and will
eventually cut their own channels.""",
 """Cuánta longitud de canal por hectárea tiene una cuenca madura en este material
y este clima. Es el mejor indicador de que la red tiene la textura correcta, y es
lo que se mide en un área natural de referencia. El complemento no lo fuerza:
compara el diseño con él y muestra un semáforo por canal. Objetivos <b>más
altos</b> exigen más fondos de valle o más largos; si el diseño se queda corto,
las laderas entre canales son demasiado largas y acabarán excavando sus propios
cauces."""),
 ("Target drainage density variance (%)", """The tolerance of that traffic light. <b>Wider</b> variance accepts more
departure from the target before flagging a channel; <b>narrower</b> makes the
check strict. It changes only the warning, never the geometry.""",
 """La tolerancia de ese semáforo. Una varianza <b>más amplia</b> acepta más
desviación del objetivo antes de marcar un canal; <b>más estrecha</b> hace la
comprobación estricta. Cambia solo el aviso, nunca la geometría."""),
 ("Force ridges to be lower than the design boundary", """When on, no designed ridge is allowed to rise above the existing ground at the
boundary. Use it when the reclaimed landform must stay hidden behind the
surrounding relief, or when the boundary elevation is a hard constraint (a haul
road, a property line). When off, ridges take the elevation the hillslope
geometry asks for, which may stand above the boundary terrain.""",
 """Activado, ninguna cresta de diseño puede quedar por encima del terreno
existente en el límite. Úsalo cuando la forma restaurada deba quedar oculta tras
el relieve del entorno, o cuando la cota del límite sea una restricción dura (una
pista, un linde). Desactivado, las crestas toman la cota que pide la geometría de
la ladera, que puede quedar por encima del terreno del límite."""),
 ("Angle from sub-ridge to channel's perpendicular, upstream (deg)", """How much the hillslope lines are swept upstream from the perpendicular to the
valley. <b>0°</b> means strictly perpendicular; <b>larger</b> angles rake them
upstream, which is what natural interfluves do — they point back up the valley.
Every line of a channel shares the same angle, so they stay sub-parallel and do
not cross. Increase it if your hillslope lines look too radial compared with a
natural reference.""",
 """Cuánto se inclinan las líneas de ladera hacia aguas arriba respecto a la
perpendicular del valle. <b>0°</b> es estrictamente perpendicular; ángulos
<b>mayores</b> las peinan hacia aguas arriba, que es lo que hacen los
interfluvios naturales: apuntan valle arriba. Todas las líneas de un canal
comparten el mismo ángulo, así que quedan subparalelas y no se cruzan. Súbelo si
tus líneas de ladera se ven demasiado radiales frente a una referencia
natural."""),
 ("North or East straight-line slopes (%)", """The straight-line slope target for the shaded aspects (roughly 315°–135°),
which hold moisture longer and can therefore stand steeper and revegetate
better. Keeping this above the general maximum reproduces the natural asymmetry
between sunny and shaded hillsides.""",
 """El objetivo de pendiente recta para las orientaciones umbrías (aproximadamente
315°–135°), que retienen humedad más tiempo y por tanto aguantan más pendiente y
revegetan mejor. Mantenerlo por encima del máximo general reproduce la asimetría
natural entre solanas y umbrías."""),
 ("Maximum straight-line slopes (%)", """The steepest straight-line gradient allowed from a ridge crest down to the
channel. It sets how high the ridges stand above the channel: ridge height is
roughly this slope times half the hillslope length. <b>Higher</b> values give
taller ridges, deeper valleys and considerably more fill; <b>lower</b> values
give a subdued, flatter landform with less earthwork but less relief to shed
water. <i>Check Ridgeline Slope</i> lists every line that exceeds it.""",
 """La pendiente recta máxima admisible desde la coronación de una cresta hasta el
canal. Fija cuánto se levantan las crestas sobre el canal: la altura de cresta es
aproximadamente esta pendiente por la mitad de la longitud de ladera. Valores
<b>más altos</b> dan crestas más altas, valles más profundos y bastante más
relleno; valores <b>más bajos</b> dan una forma apagada y más tendida, con menos
movimiento de tierras pero menos relieve para evacuar el agua. <i>Check Ridgeline
Slope</i> lista todas las líneas que lo superan."""),
 ("Maximum / Minimum cut / fill (%)", """The acceptable window for the cut-to-fill ratio. It drives the traffic light on
the Output tab and the verdict in the volume report. A design outside the window
either has material left over to haul away or needs borrow. Widen the window if
you have somewhere to take material to or from; narrow it if the site must
balance on its own.""",
 """La ventana admisible de la relación corte/relleno. Gobierna el semáforo de la
pestaña Output y el veredicto del informe de volúmenes. Un diseño fuera de la
ventana o sobra material que hay que llevarse o necesita préstamo. Amplía la
ventana si tienes dónde llevar o de dónde traer material; estréchala si el sitio
debe equilibrarse por sí solo."""),
 ("Cut swell factor / Fill shrink factor", """Bulking and compaction. Excavated material occupies more than in place (swell)
and placed material occupies less than loose (shrink). The volumes are corrected
with these factors before the ratio is judged, so they decide whether a
geometrically balanced design is balanced <i>in practice</i>. Take them from the
material, not from a default of 1.000, which means no correction at all.""",
 """Esponjamiento y compactación. El material excavado ocupa más que en banco
(esponjamiento) y el colocado ocupa menos que suelto (compactación). Los
volúmenes se corrigen con estos factores antes de juzgar la relación, así que
deciden si un diseño geométricamente equilibrado lo está <i>en la práctica</i>.
Tómalos del material, no del valor por defecto 1.000, que significa ninguna
corrección."""),
 ("Maximum distance between connecting channels (m)", """The snapping tolerance used to decide that a tributary polyline joins another
one. <b>Larger</b> tolerances forgive sloppy drawing but can connect channels
you did not mean to connect; <b>smaller</b> ones demand precise endpoints. If a
tributary ends further than this from its receiving channel the plugin still
connects it but warns you about the gap.""",
 """La tolerancia de enganche que decide que una polilínea de tributario se une a
otra. Tolerancias <b>mayores</b> perdonan un dibujo descuidado pero pueden
conectar canales que no querías; <b>menores</b> exigen extremos precisos. Si un
tributario acaba más lejos de su canal receptor que esta distancia, el
complemento lo conecta igualmente pero avisa del hueco."""),
 ("Channel: head elevation tolerance (m) / head slope tolerance (%)", """How far a specified head elevation or head slope may differ from what the
terrain and the profile actually give before you get a warning. They never change
the geometry: they only tell you that what you asked for and what the site allows
have drifted apart.""",
 """Cuánto puede diferir una cota o una pendiente de cabecera especificadas de lo
que el terreno y el perfil dan realmente antes de recibir un aviso. Nunca cambian
la geometría: solo te dicen que lo que has pedido y lo que el sitio permite se han
separado."""),
 ("Crossing breaklines: elevation tolerance (m)", """Two design lines that cross in plan should meet at the same elevation; where they
do not, the triangulation has to choose one of the two and leaves flipped
triangles and tiny closed contours. Above this difference <i>Check Design</i>
reports the crossing. <b>Smaller</b> values are stricter and surface every
millimetre of mismatch, as the original Error Log does; <b>larger</b> values keep
only the crossings big enough to show up in the contours.""",
 """Dos líneas de diseño que se cruzan en planta deberían coincidir en cota; donde no
lo hacen, la triangulación tiene que elegir una de las dos y deja triángulos
volteados y curvas de nivel cerradas diminutas. Por encima de esta diferencia
<i>Check Design</i> avisa del cruce. Valores <b>menores</b> son más estrictos y
sacan hasta el milímetro de desajuste, como el Error Log del original; valores
<b>mayores</b> dejan solo los cruces con entidad suficiente para notarse en las
curvas."""),
 ("Crossing inside the channel: tolerance (m)", """The same tolerance, applied inside the channel corridor. The centreline and the
bankfull and flood-prone lines are parallel offsets of the same section, so they
cross each other on the meander bends by construction, and a hillslope line that
dies at the bank crosses them at the bank depth. Those crossings are the expected
geometry, so they are only reported when the difference is far larger than a bank
depth. Set it to about the deepest bankfull depth in your design.""",
 """La misma tolerancia dentro del corredor del cauce. El eje y las líneas de
bankfull y flood-prone son desplazamientos paralelos de la misma sección, así que
se cruzan entre sí en los meandros por construcción, y una línea de ladera que
muere en la orilla las cruza a la cota del cajero. Esos cruces son la geometría
esperada, así que solo se avisa cuando la diferencia es muy superior a un calado
de cajero. Ponlo del orden del mayor calado bankfull de tu diseño."""),
 ("Maximum triangle mesh line length (m)", """Where there are no breaklines the triangulation has to join distant points and
the surface comes out as a flat facet with no relief. <i>Check Design</i> reports
the area that is further than half this distance from any design line, and where
the worst point is. <b>Smaller</b> values demand a denser network of ridges and
swales; <b>larger</b> values tolerate open floodplain or terrace areas.""",
 """Donde no hay líneas de rotura la triangulación tiene que unir puntos lejanos y la
superficie sale como una faceta plana sin relieve. <i>Check Design</i> avisa de la
superficie que queda a más de la mitad de esta distancia de cualquier línea de
diseño, y de dónde está el peor punto. Valores <b>menores</b> exigen una red más
densa de crestas y vaguadas; valores <b>mayores</b> toleran zonas abiertas de
llanura de inundación o terraza."""),
 ("Breakline elevation spike above (%)", """Slope between two contiguous vertices of a design line above which
<i>Check Design</i> calls it an elevation spike. A natural slope never reaches
these gradients between two points a couple of metres apart, so a value above the
threshold is almost always an editing mistake or a line that was truncated
against a confluence.""",
 """Pendiente entre dos vértices contiguos de una línea de diseño por encima de la
cual <i>Check Design</i> la considera un pico de cota. Una ladera natural nunca
alcanza esos gradientes entre dos puntos separados un par de metros, así que un
valor por encima del umbral es casi siempre un error de edición o una línea
recortada contra una confluencia."""),
 ("Valley across the slope above (deg)", """Angle between a valley input line and the terrain's downslope direction above
which <i>Check Design</i> flags it as drawn across the slope. That is one of the
classic layout mistakes: the wall on the upslope side drains into the channel but
the opposite wall slopes away from it and never delivers its runoff.""",
 """Ángulo entre una línea de fondo de valle y la dirección de máxima pendiente del
terreno por encima del cual <i>Check Design</i> la señala como trazada a media
ladera. Es uno de los errores de trazado clásicos: la ladera de aguas arriba
vierte al canal, pero la de enfrente se aleja de él y nunca le entrega su
escorrentía."""),
 ("Bed material D50, Wolman count (mm)", """The median grain size of the channel bed, from a Wolman pebble count in the
reference area. It sets the critical shear stress (Shields) against which the
tractive force of every cross-section is checked. <b>Coarser</b> material
tolerates more shear, so steeper and narrower channels pass; <b>finer</b>
material fails sooner and pushes you towards flatter gradients, wider sections or
armouring. Leave it at zero and the check cannot be made — nothing gets
highlighted.""",
 """El tamaño mediano de grano del lecho, de un conteo Wolman en el área de
referencia. Fija la tensión tractiva crítica (Shields) contra la que se comprueba
la fuerza tractiva de cada sección. Un material <b>más grueso</b> tolera más
tensión, así que pasan canales más empinados y estrechos; uno <b>más fino</b>
falla antes y te empuja hacia pendientes más suaves, secciones más anchas o
escollera. Si lo dejas a cero la comprobación no se puede hacer y no se resalta
nada."""),
 ("Contour interval / Index contour interval (m)", """Vertical spacing of the contours drawn from the design surface, and of the
emphasised index contours. Purely presentational: they do not touch the surface.
A small interval reads better on gentle ground but clutters steep slopes.""",
 """Equidistancia de las curvas de nivel dibujadas desde la superficie de diseño y
de las curvas maestras destacadas. Puramente de presentación: no tocan la
superficie. Una equidistancia pequeña se lee mejor en terreno tendido pero
abarrota las laderas empinadas."""),
 ("Cross-section station interval (m)", """The spacing at which the hydraulic cross-sections are computed and stored.
<b>Denser</b> stations give a finer hydraulic record and better tractive-force
maps but a heavier layer and slower reports; <b>coarser</b> stations may miss a
short critical reach.""",
 """El intervalo al que se calculan y guardan las secciones hidráulicas. Estaciones
<b>más densas</b> dan un registro hidráulico más fino y mejores mapas de fuerza
tractiva, pero una capa más pesada y informes más lentos; estaciones <b>más
espaciadas</b> pueden pasar por alto un tramo crítico corto."""),
]

CHANNELS = [
 ("__intro", """The Channels tab is where the network grows and where each channel gets its own
hydraulics. Everything here applies to the <i>current</i> channel selected in the
drop-down, except Add and Delete.""",
 """La pestaña Channels es donde crece la red y donde cada canal recibe su propia
hidráulica. Todo lo de aquí se aplica al canal <i>actual</i> seleccionado en el
desplegable, salvo Add y Delete."""),
 ("Add / Delete", """<b>Add</b> attaches another valley-bottom polyline to the network. The plugin
works out which existing channel receives it, at which station, and on which bank
looking downstream, and names it accordingly (R1, L1, R1L1…). Order matters: a
tributary can only connect to a channel added before it, which keeps the network
dendritic and free of loops. <b>Delete</b> removes the current channel and,
necessarily, everything that drained into it.""",
 """<b>Add</b> añade otra polilínea de fondo de valle a la red. El complemento
deduce qué canal existente la recibe, en qué estación y por qué margen mirando
aguas abajo, y la nombra en consecuencia (R1, L1, R1L1…). El orden importa: un
tributario solo puede conectarse a un canal añadido antes, lo que mantiene la red
dendrítica y sin bucles. <b>Delete</b> elimina el canal actual y, necesariamente,
todo lo que desaguaba en él."""),
 ("Name", """Renames the current channel. The automatic R/L names describe the topology, so
rename only when a local name is clearer for the report.""",
 """Renombra el canal actual. Los nombres automáticos R/L describen la topología,
así que renombra solo cuando un nombre local sea más claro para el informe."""),
 ("Transition", """Marks by clicking the point where the steep zig-zag reach ends and the
meandering valley-bottom reach begins. It can only bring that transition
<i>earlier</i>: a reach is drawn as type A only where the profile slope really
exceeds 4 %, so picking a point far downstream will not turn a gentle reach into
a zig-zag. Leave it unset and the plugin finds the 4 % crossing itself.""",
 """Marca con un clic el punto donde acaba el tramo empinado en zigzag y empieza el
tramo de fondo de valle con meandros. Solo puede <i>adelantar</i> esa transición:
un tramo se dibuja como tipo A únicamente donde la pendiente del perfil supera
realmente el 4 %, así que marcar un punto muy aguas abajo no convertirá un tramo
tendido en zigzag. Déjalo sin marcar y el complemento localiza por sí mismo el
cruce del 4 %."""),
 ("Vanes", """Places Rosgen-type flow deflectors alternating banks from the transition
downstream. They steer the current away from the outer bank of each bend, which
is where a young channel erodes first. Useful on the reaches the tractive-force
check flags as marginal.""",
 """Coloca deflectores de flujo tipo Rosgen alternando márgenes desde la transición
hacia aguas abajo. Desvían la corriente de la margen exterior de cada curva, que
es donde un cauce joven erosiona primero. Útiles en los tramos que la
comprobación de fuerza tractiva marca como justos."""),
 ("__cs", """<hr><h3>Current Channel Settings — Geometry tab</h3>""",
 """<hr><h3>Current Channel Settings — pestaña Geometry</h3>"""),
 ("Maximum Water Velocity (m/s)", """The design velocity used to size the section: area equals flow divided by
velocity. It is inversely related to the cross-section, so a <b>higher</b>
velocity gives a smaller, narrower channel and a <b>lower</b> velocity a larger
one. It should be the velocity the bed material can stand without moving — set it
too high and the section comes out too small for the slope, which the Manning
check will tell you.""",
 """La velocidad de diseño con la que se dimensiona la sección: el área es el
caudal partido por la velocidad. Es inversa a la sección, así que una velocidad
<b>mayor</b> da un canal más pequeño y estrecho, y una <b>menor</b> uno más
grande. Debe ser la velocidad que el material del lecho aguanta sin moverse: si
la pones muy alta la sección sale demasiado pequeña para la pendiente, y la
verificación de Manning te lo dirá."""),
 ("Upstream Slope %", """The gradient at the channel head. Together with the mouth slope it defines the
concave vertical curve. <b>Steeper</b> (more negative) drops the channel earlier,
which means more cut in the upper catchment and less fill downstream. It must be
<i>steeper</i> than the average valley gradient, otherwise the profile cannot be
concave and gets flattened, with a warning.""",
 """La pendiente en la cabecera. Junto con la pendiente de boca define la curva
vertical cóncava. <b>Más empinada</b> (más negativa) hace bajar el canal antes,
lo que significa más corte en la cuenca alta y menos relleno aguas abajo. Debe
ser <i>más</i> empinada que la pendiente media del valle, porque si no el perfil
no puede ser cóncavo y se aplana, con aviso."""),
 ("Downstream slope % (only on the main channel)", """The mouth gradient of this channel. Only the main channel has one, because a
tributary must join its receiving channel with the receiving channel's elevation
<i>and</i> gradient — that is what makes the confluence hydraulically smooth
instead of a step. See the Setup tab for what this value does to the volumes.""",
 """La pendiente de boca de este canal. Solo el canal principal la tiene, porque un
tributario debe empalmar con la cota <i>y</i> la pendiente del canal receptor en
la confluencia: eso es lo que hace la unión hidráulicamente suave en vez de un
escalón. Mira la pestaña Setup para saber qué hace este valor a los
volúmenes."""),
 ("Width-to-Depth (two values: slope &gt; 4 % and &lt; 4 %)", """The shape of the trapezoidal section, given separately for steep and gentle
reaches because natural channels change shape at that threshold. <b>Higher</b>
W:D gives a wide, shallow channel: more friction, lower shear on the bed, easier
to revegetate, but a wider disturbed corridor. <b>Lower</b> W:D gives a narrow,
deep channel: more shear on the bed and more erosive. Steep reaches normally take
a lower value than gentle ones.""",
 """La forma de la sección trapezoidal, dada por separado para tramos empinados y
tendidos porque los canales naturales cambian de forma en ese umbral. Un W:D
<b>más alto</b> da un canal ancho y somero: más rozamiento, menos tensión en el
lecho, más fácil de revegetar, pero un corredor alterado más ancho. Un W:D <b>más
bajo</b> da un canal estrecho y profundo: más tensión en el lecho y más erosivo.
Los tramos empinados suelen llevar un valor más bajo que los tendidos."""),
 ("Sinuosity (two values: slope &gt; 4 % and &lt; 4 %)", """Channel length over valley length, again split at 4 %. On the gentle reach this
is what produces the meanders: <b>higher</b> sinuosity means a longer channel
over the same valley, so a gentler gradient, lower shear and a more natural plan
form, at the cost of more channel to excavate. On the steep reach it stays low
because steep natural channels are nearly straight. The plugin cannot exceed the
meander belt the flow allows, so asking for a very high sinuosity on a small
channel will be capped.""",
 """Longitud de canal partida por longitud de valle, otra vez separada en el 4 %. En
el tramo tendido es lo que produce los meandros: una sinuosidad <b>más alta</b>
significa un canal más largo sobre el mismo valle, así que pendiente más suave,
menos tensión y una planta más natural, a costa de más cauce que excavar. En el
tramo empinado se mantiene baja porque los canales naturales empinados son casi
rectos. El complemento no puede superar el cinturón de meandro que permite el
caudal, así que pedir una sinuosidad muy alta en un canal pequeño se
recortará."""),
 ("Sub-ridge spacing on sinusoidal channel", """How many meander apices to skip between hillslope lines, <b>on the meandering
reach only</b>. On the zig-zag reaches the method puts a ridge and a swale at
<i>every</i> zig-zag, and their frequency is governed by the 'A' channel reach
instead. <b>1</b> gives a line pair at every apex — the densest, most articulated
hillslope; <b>3</b> or more gives longer, smoother hillslopes with fewer lines
and less earthwork. An odd number makes the pairs alternate banks naturally.""",
 """Cuántos ápices de meandro se salta entre líneas de ladera, <b>solo en el tramo
sinuoso</b>. En los tramos en zigzag el método coloca una cresta y una vaguada en
<i>cada</i> zigzag, y su frecuencia la gobierna el 'A' channel reach. <b>1</b> da
un par de líneas en cada ápice: la ladera más densa y articulada; <b>3</b> o más
da laderas más largas y suaves, con menos líneas y menos movimiento de tierras.
Un número impar hace que los pares alternen márgenes de forma natural."""),
 ("Specify head elevation / mouth elevation", """By default both are sampled from the DEM. Tick them to impose a value — the
mouth elevation especially, because in a final design the outlet has to match the
receiving channel exactly. <b>Pick</b> samples the DEM at the corresponding end so
you can see what the terrain gives before overriding it. If a specified elevation
departs from the terrain by more than the tolerance you get a warning.""",
 """Por defecto ambas se toman del DEM. Márcalas para imponer un valor,
especialmente la cota de boca, porque en un diseño final la desembocadura tiene
que coincidir exactamente con el cauce receptor. <b>Pick</b> toma la cota del DEM
en el extremo correspondiente para que veas qué da el terreno antes de
sobrescribirlo. Si una cota especificada se aparta del terreno más que la
tolerancia, recibes un aviso."""),
 ("Specify sub-ridge/swale convex length", """Overrides the global convex settings for this channel only, so a steep tributary
can have a different hillslope shape from the trunk. <b>Maximum distance from
ridgeline to swale head</b> is the <b>convex length</b> of the swale — the
distance from the divide over which the slope is still convex before it inflects
into its concave lower part. It is <b>not</b> a set-back: sub-ridges and swales
both run from the channel all the way up to the divide. What makes the swale a
depression is that its convex length is <b>shorter</b> than that of the
sub-ridges on either side, so with the same drop it falls away faster and sits
below them. The sub-ridge convex length is 1.5 times this value. A
<b>smaller</b> value digs the swale deeper and gives a more dissected hillslope;
a <b>larger</b> one flattens the contrast until sub-ridge and swale are alike.
Values larger than the hillslope itself are capped.""",
 """Sobrescribe los ajustes convexos globales solo para este canal, de modo que un
tributario empinado pueda tener una forma de ladera distinta del tronco.
<b>Maximum distance from ridgeline to swale head</b> es la <b>longitud
convexa</b> de la vaguada: la distancia desde la divisoria en la que la ladera
todavía es convexa, antes de inflexionar a su parte cóncava. <b>No</b> es un
retranqueo: subcrestas y vaguadas salen las dos del cauce y suben las dos hasta
la divisoria. Lo que convierte la vaguada en una depresión es que su longitud
convexa es <b>más corta</b> que la de las subcrestas de al lado, así que con el
mismo desnivel cae más deprisa y queda por debajo. La longitud convexa de la
subcresta es 1.5 veces este valor. Un valor <b>menor</b> encaja más la vaguada y
da una ladera más disecada; uno <b>mayor</b> aplana el contraste hasta que
subcresta y vaguada se parecen. Los valores mayores que la propia ladera se
recortan."""),
 ("Random scale factors on sinusoidal channel", """When on, the radius of curvature of each bend varies randomly inside the stable
range (2.5–3.2 times the bankfull width), which makes the plan form look natural
rather than machine-made. When off, every bend is identical: more regular, easier
to compare between runs, and reproducible — which is what you want while
calibrating.""",
 """Activado, el radio de curvatura de cada curva varía al azar dentro del rango
estable (2.5–3.2 veces la anchura bankfull), lo que da a la planta un aspecto
natural en vez de fabricado. Desactivado, todas las curvas son idénticas: más
regular, más fácil de comparar entre generaciones y reproducible, que es lo que
interesa mientras calibras."""),
 ("Manning's n (hydraulic verification)", """Used only to <i>check</i> the section, never to size it: the plugin computes the
normal depth, velocity and Froude number for the design flow and warns if the
velocity comes out above the design velocity (the section is short for that
slope) or well below it (possible sedimentation). Pick n from the expected bed
roughness and vegetation.""",
 """Se usa solo para <i>comprobar</i> la sección, nunca para dimensionarla: el
complemento calcula el calado normal, la velocidad y el número de Froude para el
caudal de diseño y avisa si la velocidad sale por encima de la de diseño (la
sección es corta para esa pendiente) o muy por debajo (posible sedimentación).
Elige n según la rugosidad del lecho y la vegetación previstas."""),
 ("Override global D50 for this channel", """Lets one channel have its own bed material — a headwater reach on coarse rock
waste and a lower reach on fines, for instance. It changes only that channel's
tractive-force check.""",
 """Permite que un canal tenga su propio material de lecho: por ejemplo un tramo de
cabecera sobre estéril grueso y un tramo bajo sobre finos. Cambia solo la
comprobación de fuerza tractiva de ese canal."""),
 ("__ws", """<hr><h3>Current Channel Settings — Watershed tab</h3>""",
 """<hr><h3>Current Channel Settings — pestaña Watershed</h3>"""),
 ("Use Rational Runoff Method / Runoff Coefficient", """The peak flow comes from the rational method: flow equals coefficient times
rainfall intensity times area. The <b>runoff coefficient</b> is the fraction of
rainfall that becomes surface flow, and it is the strongest lever you have on
channel size after the rainfall itself: bare compacted spoil runs off far more
than a vegetated soil. <b>Higher</b> coefficients give bigger channels, longer
meander wavelengths and hillslope lines further apart; <b>lower</b> ones give a
finer network. Choose it for the <i>reclaimed, vegetated</i> condition, not for
the bare state, unless you are designing for the construction period.""",
 """El caudal punta sale del método racional: caudal igual a coeficiente por
intensidad de lluvia por área. El <b>coeficiente de escorrentía</b> es la
fracción de lluvia que se convierte en escorrentía superficial, y es la palanca
más fuerte sobre el tamaño del canal después de la propia lluvia: un estéril
desnudo y compactado escurre mucho más que un suelo con vegetación. Coeficientes
<b>más altos</b> dan canales más grandes, longitudes de onda de meandro mayores y
líneas de ladera más separadas; <b>más bajos</b> dan una red más fina. Elígelo
para la condición <i>restaurada y vegetada</i>, no para el estado desnudo, salvo
que estés diseñando para el periodo de obra."""),
 ("Use manual Qpk", """Replaces the rational method with peak flows you supply for the two storms.
Use it when you have a proper hydrological study, a gauged record or a regional
formula you trust more than the rational method — typically on larger catchments,
where the rational method loses validity.""",
 """Sustituye el método racional por caudales punta que tú introduces para las dos
tormentas. Úsalo cuando tengas un estudio hidrológico en regla, un registro
aforado o una fórmula regional en la que confíes más que en el método racional:
normalmente en cuencas grandes, donde el método racional pierde validez."""),
 ("Additional watershed area (ha)", """Catchment that drains into this channel from <i>outside</i> the design
boundary — an upstream slope, a road, an undisturbed hillside. Ignoring it is a
classic way to undersize a channel. Its own runoff coefficient is set separately
because that land usually has a different cover from the reclaimed area.""",
 """Cuenca que desagua en este canal desde <i>fuera</i> del límite de diseño: una
ladera aguas arriba, una pista, una vertiente sin alterar. Ignorarla es una forma
clásica de infradimensionar un canal. Su coeficiente de escorrentía se fija
aparte porque ese terreno suele tener una cubierta distinta de la del área
restaurada."""),
 ("At head of channel / Evenly along length", """Where that outside area delivers its water. <b>At head</b> loads the whole flow
at station zero, so the channel is sized large from its very beginning — the
conservative choice, and the right one when the inflow arrives as a concentrated
discharge. <b>Evenly along length</b> spreads it, so the section grows gradually
downstream, which suits a slope that drains diffusely along the whole reach.""",
 """Por dónde entrega su agua esa área exterior. <b>At head</b> carga todo el
caudal en la estación cero, así que el canal se dimensiona grande desde el mismo
principio: la opción conservadora, y la correcta cuando la aportación llega como
una descarga concentrada. <b>Evenly along length</b> lo reparte, de modo que la
sección crece gradualmente aguas abajo, lo que encaja con una ladera que drena
de forma difusa a lo largo de todo el tramo."""),
 ("__data", """<b>Data for current channel</b> (read-only) reports the valley length, the reach
area, the additional area and the drainage density with its traffic light.
<b>Profile</b> opens the longitudinal profile of the channel against the original
ground, and <b>Report</b> the hydraulic table of its cross-sections.""",
 """<b>Data for current channel</b> (solo lectura) da la longitud de valle, el área
del tramo, el área adicional y la densidad de drenaje con su semáforo.
<b>Profile</b> abre el perfil longitudinal del canal frente al terreno original, y
<b>Report</b> la tabla hidráulica de sus secciones."""),
]

OUTPUT = [
 ("__intro", """The Output tab turns the network into a surface and tells you what it costs in
earthwork.""",
 """La pestaña Output convierte la red en una superficie y te dice lo que cuesta en
movimiento de tierras."""),
 ("Preview", """Generates the channels, banks and cross-sections without building the surface.
It is the fast loop: run it after every change of setting to see the plan
geometry, the drainage density and the hydraulic warnings before paying for a
full interpolation.""",
 """Genera los canales, los bordes y las secciones sin construir la superficie. Es
el ciclo rápido: ejecútalo tras cada cambio de ajuste para ver la geometría en
planta, la densidad de drenaje y los avisos hidráulicos antes de pagar una
interpolación completa."""),
 ("Reread Valley Bottoms", """Re-reads the input polylines from their layer. Use it after editing a valley
bottom in QGIS so the design picks up the new geometry.""",
 """Vuelve a leer las polilíneas de entrada desde su capa. Úsalo después de editar
un fondo de valle en QGIS para que el diseño recoja la geometría nueva."""),
 ("Draw Design Surface...", """The full build: sub-watersheds, divide ridges, sub-ridges, swales, the
interpolated surface and the contours. <b>Number of lines in a channel</b> (3, 5
or 7) chooses how much of the channel cross-section is drawn as breaklines: 3 is
the centreline plus bankfull edges, 5 adds the bed, 7 adds the flood-prone
edges. More lines describe the channel better in the surface, at the cost of a
heavier triangulation.""",
 """La construcción completa: subcuencas, crestas divisorias, subcrestas, vaguadas,
la superficie interpolada y las curvas. <b>Number of lines in a channel</b> (3, 5
o 7) elige cuánta sección del canal se dibuja como líneas de rotura: 3 es el eje
más los bordes bankfull, 5 añade el fondo y 7 añade los bordes del área
inundable. Más líneas describen mejor el canal en la superficie, a costa de una
triangulación más pesada."""),
 ("__tri", """<hr><h3>Triangulate and Contour From Design TIN <span class='sub'>(pop-up after Draw Design Surface)</span></h3>""",
 """<hr><h3>Triangulate and Contour From Design TIN <span class='sub'>(ventana tras Draw Design Surface)</span></h3>"""),
 ("Output surface resolution (cell size)", """The pixel size of the design raster. <b>Finer</b> cells capture the channel and
the ridge crests faithfully and give precise volumes, but the raster grows with
the square of the reduction and everything downstream slows down. <b>Coarser</b>
cells smooth the design and can swallow narrow channels altogether. As a rule,
keep the cell smaller than half the bankfull width.""",
 """El tamaño de píxel del ráster de diseño. Celdas <b>más finas</b> recogen
fielmente el canal y las coronaciones de cresta y dan volúmenes precisos, pero el
ráster crece con el cuadrado de la reducción y todo lo que viene después se
ralentiza. Celdas <b>más gruesas</b> suavizan el diseño y pueden tragarse los
canales estrechos. Como regla, mantén la celda por debajo de la mitad de la
anchura bankfull."""),
 ("Interpolate Ridges and Valleys", """Uses the ridges, sub-ridges and swales as breaklines of the triangulation. With
it off the surface would only know about the channels and the hillslope relief
would disappear, so leave it on for any real design.""",
 """Usa las crestas, subcrestas y vaguadas como líneas de rotura de la
triangulación. Desactivado, la superficie solo conocería los canales y el relieve
de ladera desaparecería, así que déjalo activado en cualquier diseño real."""),
 ("Minimize Flat Triangles (densify breaklines)", """Adds intermediate vertices along the breaklines at the given interval. Long
triangles spanning distant vertices are what produce artificial terraces and flat
facets. A <b>smaller</b> interval removes them at the cost of more triangles; a
<b>larger</b> one is faster but leaves the surface coarser between vertices.""",
 """Añade vértices intermedios en las líneas de rotura al intervalo indicado. Los
triángulos largos entre vértices lejanos son los que producen terrazas
artificiales y facetas planas. Un intervalo <b>menor</b> los elimina a costa de
más triángulos; uno <b>mayor</b> es más rápido pero deja la superficie más
grosera entre vértices."""),
 ("Clip surface to the Design Boundary", """Sets everything outside the boundary to no-data, which is what you want: there
is no design out there, and leaving interpolated values beyond the perimeter
falsifies both the map and the volumes.""",
 """Pone todo lo que queda fuera del límite como sin datos, que es lo correcto:
ahí no hay diseño, y dejar valores interpolados más allá del perímetro falsea
tanto el plano como los volúmenes."""),
 ("Surface rounding / naturalness", """A raw triangulation of ridges and valleys is faceted and sharp-crested; real
divides and interfluves are rounded, because hillslope diffusion (creep) has
worked on them for a long time. The <b>smoothing degree</b> applies that same
process as a low-pass filter, and the <b>filter radius</b> sets how wide it
reaches. <b>0</b> leaves the raw TIN. Moderate values round the crests without
moving the channels or the divides. <b>High</b> values start eating the relief
itself and flattening the design, and they slightly reduce the extreme volumes.""",
 """Una triangulación cruda de crestas y valles sale facetada y con aristas vivas;
las divisorias e interfluvios reales están redondeados, porque la difusión de
ladera (creep) ha trabajado sobre ellos mucho tiempo. El <b>grado de
suavizado</b> aplica ese mismo proceso como filtro paso bajo, y el <b>radio del
filtro</b> fija su alcance. <b>0</b> deja el TIN crudo. Valores moderados
redondean las coronaciones sin mover los canales ni las divisorias. Valores
<b>altos</b> empiezan a comerse el relieve y aplanan el diseño, y reducen
ligeramente los volúmenes extremos."""),
 ("Draw Contours / Contour Interval / Index Interval", """Whether to draw contours from the new surface and at what vertical spacing,
with the index contours emphasised. The contours are 3D lines: each one carries
its own elevation in the geometry, so they can be used in 3D views and exported
as such.""",
 """Si dibujar curvas de nivel de la superficie nueva y a qué equidistancia, con las
curvas maestras destacadas. Las curvas son líneas 3D: cada una lleva su cota en
la geometría, así que sirven para vistas 3D y se pueden exportar como tales."""),
 ("Min Contour Length", """Discards contours shorter than this. It cleans up the swarm of tiny closed
rings that any interpolation produces. Careful: a small closed contour can also
be a real defect — a pit where water cannot escape — so check before hiding them
all.""",
 """Descarta las curvas más cortas que esto. Limpia el enjambre de anillos cerrados
minúsculos que produce cualquier interpolación. Cuidado: una curva cerrada
pequeña puede ser también un defecto real —un hoyo del que el agua no puede
salir— así que compruébalo antes de esconderlas todas."""),
 ("Contour Smoothing Method / Bezier Smoothing Factor", """<b>No Smoothing</b> draws the contours exactly as the raster gives them, with
visible stair-stepping on gentle ground. <b>Bezier Smoothing</b> rounds them; a
<b>higher</b> factor gives smoother, more legible lines but they drift further
from the true surface, so do not push it if the contours are going to be used for
setting out.""",
 """<b>No Smoothing</b> dibuja las curvas exactamente como las da el ráster, con
escalonado visible en terreno tendido. <b>Bezier Smoothing</b> las redondea; un
factor <b>más alto</b> da líneas más suaves y legibles pero que se apartan más de
la superficie real, así que no lo fuerces si las curvas van a servir para
replanteo."""),
 ("__cf", """<hr><h3>Cut / Fill</h3>""", """<hr><h3>Corte / relleno</h3>"""),
 ("Comparison Surface", """The surface the design is compared against — normally the original ground, but
you can point it at an intermediate stage to measure one phase of the works
instead of the whole job.""",
 """La superficie contra la que se compara el diseño: normalmente el terreno
original, aunque puedes apuntarla a una fase intermedia para medir una etapa de
la obra en vez del trabajo completo."""),
 ("Update Cut / Fill", """Integrates the difference inside the boundary and reports cut, fill and their
ratio, with the traffic light against the acceptable window. Read the ratio
together with the swell and shrink factors: a design that balances geometrically
may not balance once the material is moved.""",
 """Integra la diferencia dentro del límite e informa del corte, el relleno y su
relación, con el semáforo frente a la ventana admisible. Lee la relación junto
con los factores de esponjamiento y compactación: un diseño que cuadra
geométricamente puede no cuadrar una vez movido el material."""),
 ("Summary Report...", """The overall report of the work area: channels, lengths, densities, areas and
volumes, with the fields you choose in the Report Formatter.""",
 """El informe general del área de trabajo: canales, longitudes, densidades, áreas y
volúmenes, con los campos que elijas en el Report Formatter."""),
]

DWG = [
 ("__intro", """The DWG tab is the analysis and editing toolbox: it works on what has already
been generated.""",
 """La pestaña DWG es la caja de herramientas de análisis y edición: trabaja sobre
lo ya generado."""),
 ("Edit design inputs / Edit design surface in drawing", """Two working modes. In <b>inputs</b> mode you change boundary, valley bottoms and
settings, and regenerating rebuilds everything. In <b>surface</b> mode you edit
the generated lines directly — dragging vertices, editing profiles — and the other
tabs are locked to remind you that regenerating from the inputs would throw those
manual edits away.""",
 """Dos modos de trabajo. En modo <b>inputs</b> cambias el límite, los fondos de
valle y los ajustes, y al regenerar se reconstruye todo. En modo <b>surface</b>
editas directamente las líneas generadas —arrastrando vértices, editando
perfiles— y las otras pestañas se bloquean para recordarte que regenerar desde
las entradas se llevaría por delante esas ediciones manuales."""),
 ("Draw Design Contours", """Re-interpolates the surface and redraws the contours, reopening the triangulate
and contour options. Use it after editing design lines by hand.""",
 """Vuelve a interpolar la superficie y redibuja las curvas, reabriendo las opciones
de triangulación y curvado. Úsalo tras editar líneas de diseño a mano."""),
 ("3D Contour Viewer / 3D Surface Viewer", """Opens the QGIS 3D view on the contours or on the surface. The fastest way to
catch a defect the plan view hides: a reversed drainage, a closed hollow, a ridge
that does not reach the boundary.""",
 """Abre la vista 3D de QGIS sobre las curvas o sobre la superficie. La forma más
rápida de detectar un defecto que la planta esconde: un drenaje invertido, una
depresión cerrada, una cresta que no llega al límite."""),
 ("Calculate Design Volume", """Reports cut, fill and net volume inside the boundary, in place and corrected for
swell and shrink, and produces the <code>GRD_CutFill</code> raster clipped to the
perimeter: negative is cut, positive is fill.""",
 """Informa del corte, el relleno y el neto dentro del límite, en banco y corregidos
por esponjamiento y compactación, y genera el ráster <code>GRD_CutFill</code>
recortado al perímetro: negativo es corte, positivo es relleno."""),
 ("Mass Haul", """Groups the cut and fill into connected regions above a minimum volume you set —
match it to the equipment, because regions smaller than a machine's working unit
are not worth planning. It draws the regions as polygons with their volume, area
and mean depth, computes the volume-weighted centroids and proposes the haul
plan by nearest assignment, drawing each haul as a line with its volume,
distance and volume × distance.""",
 """Agrupa el corte y el relleno en regiones conexas por encima de un volumen mínimo
que fijas tú: ajústalo a la maquinaria, porque regiones más pequeñas que la unidad
de trabajo de una máquina no merece la pena planificarlas. Dibuja las regiones
como polígonos con su volumen, área y profundidad media, calcula los centroides
ponderados por volumen y propone el plan de acarreo por asignación al más
próximo, dibujando cada acarreo como una línea con su volumen, su distancia y su
volumen × distancia."""),
 ("Channel Cross-Section Report", """The hydraulic table station by station: flows, bankfull and flood-prone
dimensions, wetted perimeter, hydraulic radius, entrenchment, shear stress
against the critical value, Manning check, Froude number and meander geometry.""",
 """La tabla hidráulica estación por estación: caudales, dimensiones bankfull y de
área inundable, perímetro mojado, radio hidráulico, atrincheramiento, tensión
tractiva frente a la crítica, verificación de Manning, número de Froude y
geometría del meandro."""),
 ("Highlight Tractive Force Zones", """Colours the cross-sections by the ratio of acting shear to critical shear:
green below 80 %, amber 80–100 %, red above. Red means the design flow can move
the bed material at that station, so either the gradient is too steep there, the
section too narrow, or the material too fine. Needs a D50 to work.""",
 """Colorea las secciones por la relación entre la tensión actuante y la crítica:
verde por debajo del 80 %, ámbar entre 80 y 100 %, rojo por encima. Rojo
significa que el caudal de diseño puede mover el material del lecho en esa
estación, así que o la pendiente es excesiva ahí, o la sección demasiado
estrecha, o el material demasiado fino. Necesita un D50 para funcionar."""),
 ("Check Ridgeline Slope", """Lists every ridge, sub-ridge and swale whose steepest segment exceeds the
maximum straight-line slope, with its worst and mean gradient and its length.
Click a row and the line is selected and zoomed to in the canvas, so you can fix
it on the spot.""",
 """Lista todas las crestas, subcrestas y vaguadas cuyo segmento más empinado supera
la pendiente recta máxima, con su pendiente peor y media y su longitud. Pulsa una
fila y la línea queda seleccionada y centrada en el lienzo, para corregirla en el
momento."""),
 ("Check Design (Error Log)", """Runs every design check at once and lists the findings by severity, with the
feature involved and a suggested fix. It groups them into <b>Inputs</b> (settings
that contradict the method), <b>Layout</b> (valleys drawn across the slope,
channels too close to high ground), <b>Breaklines / TIN</b> (lines that cross at
different elevations, duplicate vertices, elevation spikes, areas with no
breaklines nearby), <b>Slopes</b> (gradients above the straight-line targets,
valley walls that are not steeper than their channel, ridges above the boundary),
<b>Hydraulics</b> (tractive force, velocity, Rosgen ranges, drainage density) and
<b>Surface / volumes</b> (closed depressions, isolated peaks, cut/fill balance).
<b>Errors</b> break the design or the triangulation; <b>warnings</b> mean the
design departs from the method or from your own settings; <b>notes</b> are checks
that passed, or crossings that are the expected geometry. Click a row to select
and zoom to the feature; the panel below explains it and proposes the correction.
The result can be exported to CSV. The tolerances that decide what counts as a
finding are in <i>Settings &gt; Drawing Settings</i>.""",
 """Ejecuta de una vez todas las comprobaciones del diseño y lista los hallazgos por
gravedad, con la entidad implicada y la corrección sugerida. Los agrupa en
<b>Inputs</b> (ajustes que contradicen el método), <b>Layout</b> (valles trazados
a media ladera, canales demasiado cerca de zonas altas), <b>Breaklines / TIN</b>
(líneas que se cruzan a distinta cota, vértices duplicados, picos de cota, zonas
sin líneas de rotura cerca), <b>Slopes</b> (pendientes por encima de los
objetivos, laderas que no vierten a su canal, crestas por encima del límite),
<b>Hydraulics</b> (tensión tractiva, velocidad, rangos de Rosgen, densidad de
drenaje) y <b>Surface / volumes</b> (depresiones cerradas, picos aislados,
balance corte/relleno). Los <b>errores</b> rompen el diseño o la triangulación;
los <b>avisos</b> indican que el diseño se aparta del método o de tus propios
ajustes; las <b>notas</b> son comprobaciones superadas, o cruces que son la
geometría esperada. Pulsa una fila para seleccionar la entidad y centrarla; el
panel inferior la explica y propone la corrección. El resultado se puede exportar
a CSV. Las tolerancias que deciden qué es un hallazgo están en <i>Settings &gt;
Drawing Settings</i>."""),
 ("View Longitudinal Profile", """With features selected anywhere in the project it draws the profile of all of
them superimposed, labelled by layer and feature id, with check boxes to show or
hide each series and the original ground underneath. With nothing selected it
shows the design profile of the current channel.""",
 """Con entidades seleccionadas en cualquier parte del proyecto dibuja el perfil de
todas ellas superpuestas, identificadas por capa e identificador de entidad, con
casillas para mostrar u ocultar cada serie y el terreno original por debajo. Sin
selección muestra el perfil de diseño del canal actual."""),
 ("Edit Longitudinal Profile", """Reshapes the profile of a selected line by hand: double-click to move a control
point and blend the change into the neighbours by a percentage. Raising the high
end of a ridge adds fill around it; lowering a swale adds cut. It is the tool for
local volume adjustments that do not deserve a change of settings.""",
 """Reforma a mano el perfil de una línea seleccionada: doble clic para mover un
punto de control y mezclar el cambio con los vecinos según un porcentaje.
Levantar el extremo alto de una cresta añade relleno alrededor; bajar una vaguada
añade corte. Es la herramienta para los ajustes locales de volumen que no merecen
un cambio de ajustes."""),
 ("Auto Longitudinal Profile", """Applies a profile rule to many lines at once instead of one by one.""",
 """Aplica una regla de perfil a muchas líneas a la vez en vez de una por una."""),
 ("Save Design Surface TIN", """Exports the design surface so it can be taken to other software or used as the
comparison surface of a later phase.""",
 """Exporta la superficie de diseño para llevarla a otro programa o usarla como
superficie de comparación de una fase posterior."""),
 ("Project Inspector", """A panel that follows the cursor and reports the design at that point in
continuous form: channel, station, elevation, gradient, section dimensions,
flows and shear. The quickest way to interrogate the design without opening a
single attribute table.""",
 """Un panel que sigue al cursor e informa del diseño en ese punto de forma
continua: canal, estación, cota, pendiente, dimensiones de la sección, caudales y
tensión. La forma más rápida de interrogar el diseño sin abrir una sola tabla de
atributos."""),
]

AI = [
 ("__intro", """<b>This tab is optional.</b> Everything above works without it. It connects to a
language model running <i>on your own machine</i> (Ollama or LM Studio); nothing
leaves the computer unless you enable web search. If no server is running the tab
says so and the rest of the plugin is unaffected.<br><br>
<b>How the loop works.</b> The plugin drives the search and does the arithmetic:
it regenerates the design with its own engine and measures the volumes locally,
so every candidate is geometrically valid and the run converges even if the model
is wrong. The model acts as a <i>guide</i>: it receives the numbers, the history
and the images, and returns which variables to move and why, as bounded
parameters — never raw geometry. Proposals outside the allowed ranges are
discarded and logged. Without a model the same loop runs in numeric mode.<br><br>
<b>Start from a design you already believe in.</b> The optimisation refines; it
does not invent. Build a sound design first with the conventional tabs.""",
 """<b>Esta pestaña es opcional.</b> Todo lo anterior funciona sin ella. Se conecta
a un modelo de lenguaje que corre <i>en tu propia máquina</i> (Ollama o LM
Studio); nada sale del ordenador salvo que habilites la búsqueda web. Si no hay
servidor, la pestaña lo indica y el resto del complemento no se ve
afectado.<br><br>
<b>Cómo funciona el bucle.</b> El complemento lleva la búsqueda y hace las
cuentas: regenera el diseño con su propio motor y mide los volúmenes en local,
así que todo candidato es geométricamente válido y la búsqueda converge aunque el
modelo se equivoque. El modelo actúa de <i>guía</i>: recibe los números, el
historial y las imágenes, y devuelve qué variables mover y por qué, como
parámetros acotados, nunca geometría en bruto. Las propuestas fuera de los rangos
permitidos se descartan y se registran. Sin modelo, el mismo bucle funciona en
modo numérico.<br><br>
<b>Parte de un diseño que ya te convenza.</b> La optimización afina, no inventa.
Construye primero un diseño sólido con las pestañas convencionales."""),
 ("Scan for local models / Server / Model", """Probes the usual ports for a local server and lists what it finds; the drop-down
then lists the installed models. Reasoning models with vision get the most out of
this tab, because they can read the maps as well as the numbers. The line below
reports the model's size, quantisation, context window and whether it declares
vision.""",
 """Sondea los puertos habituales buscando un servidor local y lista lo que
encuentra; el desplegable enumera entonces los modelos instalados. Los modelos
con razonamiento y visión son los que más aprovechan esta pestaña, porque pueden
leer los planos además de los números. La línea de abajo informa del tamaño del
modelo, la cuantización, la ventana de contexto y si declara visión."""),
 ("Temperature", """How much the model's answers vary. <b>Low</b> (around 0.1–0.3) gives repeatable,
conservative decisions, which is what a search needs. <b>Higher</b> values explore
more but also invent more and can break the JSON format. Note that the plugin
sends this value explicitly, so it overrides whatever the server has configured —
Ollama's own default is much higher than what suits this task.""",
 """Cuánto varían las respuestas del modelo. <b>Baja</b> (en torno a 0.1–0.3) da
decisiones repetibles y conservadoras, que es lo que una búsqueda necesita.
Valores <b>más altos</b> exploran más pero también inventan más y pueden romper
el formato JSON. Ojo: el complemento envía este valor explícitamente, así que
sobrescribe lo que tenga configurado el servidor. El valor por defecto de Ollama
es bastante más alto de lo que conviene aquí."""),
 ("Context (tokens)", """The window the model can read in one turn. This one matters more than it looks:
the prompt carries the metrics, the region tables, the per-line geometry and the
history, so a small window silently truncates it and the model loses the
instructions. The plugin sends the value explicitly because the server default is
often far too small. <b>Larger</b> windows keep everything but cost memory on the
GPU; if the server fails to load the model, bring it down.""",
 """La ventana que el modelo puede leer en un turno. Importa más de lo que parece:
el prompt lleva las métricas, las tablas de regiones, la geometría línea a línea y
el historial, así que una ventana pequeña lo trunca en silencio y el modelo pierde
las instrucciones. El complemento envía el valor explícitamente porque el valor
por defecto del servidor suele ser demasiado pequeño. Ventanas <b>mayores</b>
mantienen todo pero cuestan memoria en la GPU; si el servidor no consigue cargar
el modelo, bájalo."""),
 ("Send design and cut/fill images to the model", """Attaches the plan of the design, the cut/fill map, the earthwork regions and the
ridge/swale layout, each with its legend and with the georeference printed in the
footer (extent, metres per pixel and the pixel-to-coordinate formula) so the model
can relate what it sees to the coordinate tables. Needs a vision model; with a
text-only model leave it off and it will work from the numbers alone.""",
 """Adjunta la planta del diseño, el mapa de corte/relleno, las regiones de
movimiento de tierras y el trazado de crestas y vaguadas, cada uno con su leyenda
y con la georreferencia impresa en el pie (extensión, metros por píxel y la
fórmula píxel-coordenada) para que el modelo pueda relacionar lo que ve con las
tablas de coordenadas. Necesita un modelo con visión; con uno solo de texto
déjalo desactivado y trabajará solo con los números."""),
 ("Allow web search for reference data", """Lets the model ask for a web search when it needs an external figure — typical
runoff coefficients for a material, say. It only searches when the model asks,
and the results arrive in the next turn. Leave it off to keep the run entirely
offline.""",
 """Permite que el modelo pida una búsqueda web cuando necesite un dato externo:
coeficientes de escorrentía típicos de un material, por ejemplo. Solo busca
cuando el modelo lo pide, y los resultados llegan en el turno siguiente. Déjalo
desactivado para que la ejecución sea totalmente sin conexión."""),
 ("Enable model reasoning / thinking", """Turns on the explicit reasoning of models that support it. Slower per iteration
but the decisions are noticeably better, and the reasoning is written to the log
and to the session folder, which is what lets you audit why a change was made.""",
 """Activa el razonamiento explícito de los modelos que lo soportan. Más lento por
iteración pero las decisiones son claramente mejores, y el razonamiento se escribe
en el registro y en la carpeta de la sesión, que es lo que te permite auditar por
qué se hizo un cambio."""),
 ("__goals", """<hr><h3>Goals</h3>Several can be active at once; the score is the average of how well each is
met, so conflicting goals pull against each other and the run stalls at a
compromise. If that happens the final report says so.""",
 """<hr><h3>Objetivos</h3>Pueden estar activos varios a la vez; la puntuación es la media del grado de
cumplimiento de cada uno, así que objetivos contradictorios tiran en direcciones
opuestas y la búsqueda se queda en un compromiso. Si ocurre, el informe final lo
dice."""),
 ("Reach a target FILL / CUT volume", """Drives the design towards a volume you enter. Use it when the quantity is set
by something outside the design: the spoil you have to place, the material you
are allowed to take, a licence condition.""",
 """Lleva el diseño hacia un volumen que tú introduces. Úsalo cuando la cantidad la
fija algo externo al diseño: el estéril que hay que colocar, el material que se
puede retirar, una condición de la autorización."""),
 ("Balance cut and fill", """Pushes the net volume towards zero so the site closes on itself with no import
or export. Be aware that a site whose starting point is far from its target
surface — a deep void to fill, or a large heap to remove — may not be able to
balance at all, no matter how the variables move.""",
 """Empuja el volumen neto hacia cero para que el sitio se cierre sobre sí mismo sin
importar ni exportar material. Ten en cuenta que un sitio cuyo punto de partida
está muy lejos de su superficie objetivo —un hueco profundo que rellenar, o un
gran acopio que retirar— puede no ser capaz de equilibrarse en absoluto, muevas
las variables como quieras."""),
 ("Cut on the high ground, fill on the low ground", """Rewards designs where the excavation sits above the fill, so the material can be
pushed downhill. That is what makes a regrade executable with a dozer instead of
requiring load-and-haul, which is usually the difference between an affordable job
and an expensive one. It is reported as an index: positive means cut above fill,
negative means you are digging low and filling high.""",
 """Premia los diseños en los que la excavación queda por encima del relleno, de
modo que el material se pueda empujar cuesta abajo. Eso es lo que hace un
remodelado ejecutable con bulldozer en vez de exigir carga y transporte, que
suele ser la diferencia entre una obra asequible y una cara. Se informa como un
índice: positivo significa corte arriba y relleno abajo, negativo que estás
excavando abajo y rellenando arriba."""),
 ("Minimise haul work (volume × distance)", """Prefers designs where the material travels less. Add it when the earthmoving
cost, not the total volume, is what decides.""",
 """Prefiere diseños en los que el material recorre menos distancia. Añádelo cuando
lo que decide es el coste del movimiento de tierras y no el volumen total."""),
 ("Keep every ridge/swale slope below the maximum", """Keeps the search inside the stability limit while it chases volumes. Without it,
a run told only to balance earthwork will happily build hillslopes steeper than
the material can hold.""",
 """Mantiene la búsqueda dentro del límite de estabilidad mientras persigue
volúmenes. Sin él, una ejecución a la que solo se le pide equilibrar tierras
construirá alegremente laderas más empinadas de lo que el material aguanta."""),
 ("Keep the drainage density within its target range", """Protects the texture of the network from being sacrificed to the volume
objectives.""",
 """Protege la textura de la red para que no se sacrifique a los objetivos de
volumen."""),
 ("Keep the tractive force below the Shields critical value", """Protects the channels from being made erosive in the pursuit of a volume
target.""",
 """Protege los canales para que no se vuelvan erosivos persiguiendo un objetivo de
volumen."""),
 ("__vars", """<hr><h3>What the optimisation may change</h3>Nothing moves unless you allow it. Every variable is bounded by the deviation
you set <i>and</i> by its physical limits, so the search cannot leave the valid
design space.""",
 """<hr><h3>Qué puede cambiar la optimización</h3>Nada se mueve si no lo autorizas. Toda variable está acotada por la desviación
que fijes <i>y</i> por sus límites físicos, así que la búsqueda no puede salirse
del espacio de diseño válido."""),
 ("Channel plan geometry (X, Y)", """Lets the valley bottoms shift sideways up to the metres you allow, at control
points from head to mouth, keeping the ends fixed. This is how the model moves a
channel towards the ground where you want to cut, or away from where you want to
fill. <b>Generous</b> margins give it real freedom but change the layout you
drew; <b>tight</b> ones keep your plan and only fine-tune it.""",
 """Permite que los fondos de valle se desplacen lateralmente hasta los metros que
autorices, en puntos de control de cabecera a boca y manteniendo los extremos
fijos. Es así como el modelo lleva un canal hacia el terreno donde interesa
cortar, o lo aparta de donde interesa rellenar. Márgenes <b>generosos</b> le dan
libertad real pero cambian el trazado que dibujaste; <b>estrechos</b> conservan tu
planta y solo la afinan."""),
 ("Channel profile: slopes and vertical curve", """Opens the head and mouth gradients and the shape of the vertical curve. The
curve shape goes from straight, through the standard concave form, to strongly
concave, which sinks the middle reach and adds cut in the centre of the catchment
without touching the end elevations — often the cleanest way to gain volume.""",
 """Abre las pendientes de cabecera y boca y la forma de la curva vertical. La forma
va desde recta, pasando por la cóncava estándar, hasta muy cóncava, que hunde el
tramo medio y añade corte en el centro de la cuenca sin tocar las cotas de los
extremos: a menudo la forma más limpia de ganar volumen."""),
 ("Ridge and swale longitudinal profiles", """Lets the model do the equivalent of <i>Edit Longitudinal Profile</i> on the
hillslope lines: raise or lower the high end of all sub-ridges or of all swales
by a percentage, or of one single line identified by its key in the table it
receives. Raising ridges adds fill, lowering swales adds cut, and both
redistribute the earthwork by region without touching the channels — which is
exactly what you want when the totals are right but they sit in the wrong
places.""",
 """Permite al modelo hacer el equivalente a <i>Edit Longitudinal Profile</i> sobre
las líneas de ladera: subir o bajar un porcentaje el extremo alto de todas las
subcrestas o de todas las vaguadas, o de una sola línea identificada por su clave
en la tabla que recibe. Subir crestas añade relleno, bajar vaguadas añade corte, y
ambas cosas redistribuyen el movimiento de tierras por regiones sin tocar los
canales, que es justo lo que interesa cuando los totales están bien pero están en
el sitio equivocado."""),
 ("May go beyond the design boundary", """Allows the design to spill a given number of metres outside the boundary, on the
lower or the upper part only. It buys volume where the perimeter is the binding
constraint, but it commits you to disturbing ground outside the original
footprint — so it is a permitting decision as much as a design one. Leave it off
if the boundary is a hard limit.""",
 """Permite que el diseño se salga un número de metros del límite, solo por la parte
baja o por la alta. Compra volumen donde el perímetro es la restricción que manda,
pero te compromete a alterar terreno fuera de la huella original, así que es una
decisión de tramitación tanto como de diseño. Déjalo desactivado si el límite es
un tope duro."""),
 ("Global Settings / Channel settings buttons", """One button for the global settings and <b>one for each channel</b> in the
network. Inside, every setting has a tick box for whether it may change and a
deviation percentage, and the resulting range is shown next to it, already clipped
to the physical limits. Opening few variables makes the effect of each change
easy to attribute; opening many gives the search more room but needs more
iterations to find its way.""",
 """Un botón para los ajustes globales y <b>uno por cada canal</b> de la red. Dentro,
cada ajuste tiene una casilla de si puede cambiar y un porcentaje de desviación, y
al lado se muestra el rango resultante, ya recortado a los límites físicos. Abrir
pocas variables hace fácil atribuir el efecto de cada cambio; abrir muchas da más
espacio a la búsqueda pero necesita más iteraciones para orientarse."""),
 ("__run", """<hr><h3>Run</h3>""", """<hr><h3>Ejecución</h3>"""),
 ("Iterations", """How many candidates to try. Each one regenerates the design and, with a model
attached, waits for its answer, so the wall-clock cost is roughly iterations
times (model time plus evaluation time). Start with a handful to see whether the
variables you opened actually move the metrics.""",
 """Cuántos candidatos probar. Cada uno regenera el diseño y, con modelo conectado,
espera su respuesta, así que el tiempo total es aproximadamente iteraciones por
(tiempo de modelo más tiempo de evaluación). Empieza con unas pocas para ver si
las variables que has abierto mueven de verdad las métricas."""),
 ("Allowed error (tolerance)", """How close to a target counts as met. <b>Tight</b> tolerances demand precision
and may never be satisfied; <b>loose</b> ones accept a design sooner. It also
scales the partial credit given to near misses, so it shapes the search, not just
the verdict.""",
 """Cuánto de cerca de un objetivo cuenta como cumplido. Tolerancias
<b>estrechas</b> exigen precisión y puede que nunca se satisfagan; <b>amplias</b>
aceptan un diseño antes. También escala el crédito parcial que se da a los casi
aciertos, así que moldea la búsqueda y no solo el veredicto."""),
 ("Volume mesh step", """The grid used to integrate the volumes during the search. This is the
speed-versus-precision dial: a <b>coarse</b> step makes each iteration fast, so
you can afford many, at the price of approximate volumes; a <b>fine</b> step is
precise but can make a long run impractical. Search coarse, then verify the
winning design at full resolution with <i>Calculate Design Volume</i>.""",
 """La malla con la que se integran los volúmenes durante la búsqueda. Es el mando
de velocidad frente a precisión: un paso <b>grueso</b> hace cada iteración rápida,
así que puedes permitirte muchas, a cambio de volúmenes aproximados; un paso
<b>fino</b> es preciso pero puede hacer impracticable una ejecución larga. Busca
en grueso y verifica después el diseño ganador a resolución completa con
<i>Calculate Design Volume</i>."""),
 ("__log", """<b>Progress log.</b> Every iteration reports what the model proposes, its
reasoning, the effect it expects, the mesh and area used, the number of earthwork
regions and the measured result, and whether the change was accepted. It also
flags <b>closed pits</b> in the surface — cells whose eight neighbours are all
higher, where water cannot escape, which is always a design defect and usually
means a missing divide ridge or breaklines that do not meet in elevation. Drag the
separator above the log to make it taller, or open it in its own resizable
window.""",
 """<b>Registro de progreso.</b> Cada iteración informa de lo que propone el modelo,
su motivo, el efecto que espera, la malla y el área usadas, el número de regiones
de movimiento de tierras y el resultado medido, y si el cambio se aceptó. También
señala los <b>hoyos cerrados</b> de la superficie —celdas cuyas ocho vecinas están
más altas, donde el agua no puede salir— que son siempre un defecto de diseño y
suelen significar que falta una cresta divisoria o que dos líneas de rotura no
encajan en cota. Arrastra el separador de encima del registro para agrandarlo, o
ábrelo en su propia ventana redimensionable."""),
 ("__folder", """<b>Session folder.</b> Each run creates its own dated folder next to the project
file, holding the base prompt, the model's memory document, the exact prompt of
every iteration, the raw answers, the history and result in JSON, the images, the
rasters and the coordinate tables of the channels and of every ridge and swale.
Everything the model was told is auditable afterwards.""",
 """<b>Carpeta de la sesión.</b> Cada ejecución crea su propia carpeta con fecha
junto al fichero del proyecto, con el prompt base, el documento de memoria del
modelo, el prompt exacto de cada iteración, las respuestas crudas, el historial y
el resultado en JSON, las imágenes, los rásteres y las tablas de coordenadas de
los canales y de cada cresta y vaguada. Todo lo que se le dijo al modelo queda
auditable después."""),
 ("Apply best solution to the project", """Writes the winning values into the project settings. If the best solution also
shifted the valley bottoms it offers to write those into the input layer. Then
rebuild at full resolution with <i>Draw Design Surface</i> and check the result
yourself: the optimisation proposes, you decide.""",
 """Escribe los valores ganadores en los ajustes del proyecto. Si la mejor solución
desplazaba además los fondos de valle, ofrece escribirlos en la capa de entrada.
Después reconstruye a resolución completa con <i>Draw Design Surface</i> y
comprueba el resultado tú mismo: la optimización propone, tú decides."""),
 ("__nosol", """<b>If no solution is found</b> the run keeps the best design it reached, says so
explicitly, and suggests what to change: widen the deviation ranges, relax the
tolerance, check whether the goals are compatible with each other, open more
variables, allow the boundary overrun, or run more iterations.""",
 """<b>Si no encuentra solución</b>, la ejecución conserva el mejor diseño alcanzado,
lo dice explícitamente y sugiere qué cambiar: ampliar los rangos de desviación,
relajar la tolerancia, comprobar si los objetivos son compatibles entre sí, abrir
más variables, permitir la extralimitación del límite o hacer más iteraciones."""),
]

PESTANAS = [
    ("general", "General", GENERAL),
    ("setup", "Setup", SETUP),
    ("channels", "Channels", CHANNELS),
    ("output", "Output", OUTPUT),
    ("dwg", "DWG", DWG),
    ("ai", "AI Optimization", AI),
]
