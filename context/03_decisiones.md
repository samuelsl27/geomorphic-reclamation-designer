# Registro de decisiones (ADR)

Formato: **contexto → decisión → consecuencias → alternativas descartadas**.
Lo más reciente arriba. No borres una decisión superada: márcala y explica qué
la sustituyó.

---

## ADR-021 · Un clasificador que se compara con el original se calibra primero

**Fecha**: 2026-08 · **Estado**: aceptada · **Origen**: bug B-036

**Contexto.** El original mete divisorias y líneas de ladera en la **misma**
capa `GF_Ridges`; nosotros las tenemos separadas. Para comparar como con como
hay que clasificarlas, y no vale mirar los extremos: una divisoria muere en la
**confluencia** de los dos cauces que separa, así que su extremo bajo también
está pegado a un cauce. Con una tolerancia de 10 m, las 244 líneas del Ej_2
salen clasificadas como ladera. Lo que sí discrimina es la **equidistancia**.

**Decisión.** Todo clasificador que se use para medir el original se **calibra
contra nuestros propios datos**, donde la respuesta se conoce porque las capas
ya vienen separadas, y `comparar_original.py` **imprime esa calibración en cada
ejecución** y avisa si falla.

**Evidencia.** Con los umbrales elegidos a ojo (razón > 0.75 en más de la mitad
de los vértices) la precisión sobre nuestros datos es del **65 %**, y el
original salía con 17 divisorias. Calibrado (> 0.80 en más del 80 % de los
vértices) acierta 13 de 13 sin ningún falso positivo entre 219 líneas de
ladera, y el original tiene **7**.

**Consecuencia.** La diferencia real es la contraria de la que se creía: no nos
faltan divisorias, **nos sobran**. Las nuestras son 13 y 2265 m frente a 7 y
2103 m, y generamos tres de 46, 46 y 52 m cuando la más corta del original mide
118 m. Se había planificado una fase entera para bajar el umbral de longitud
mínima y «recuperar las 4 que faltaban»; se habría ido en la dirección
equivocada. El umbral **no se toca** hasta tener una medida mejor.

---

## ADR-020 · Las sillas de cresta son decisión NUESTRA, no del libro

**Fecha**: 2026-08-10 · **Estado**: aceptada

**Contexto.** `prof_silla_pct = 25 %` estaba documentado —en `context/01`, en el
glosario, en `core/params.py` y en `core/divides.py`— como si viniera del
«capítulo 9.4 del libro». Al leer el libro entero para esta ronda resultó que:

- la palabra *saddle* aparece **una sola vez** en las 273 páginas, en **§9.11.2,
  p. 259**, no en 9.4 (que es *Reference area observation*);
- el texto que teníamos entrecomillado en el código **sí es literal y correcto**
  —eso no estaba inventado— pero explica **por qué** existen las sillas, no
  cuánto miden;
- el libro **no da ninguna cifra** de profundidad, ni absoluta ni relativa, y lo
  presenta como una **edición manual del diseñador** con *Edit Longitudinal
  Profile*.

**Decisión.** Se conserva `prof_silla_pct` con su valor por defecto de 25 %,
pero **etiquetado como decisión de diseño nuestra**, no como constante del
método. La cita se corrige a §9.11.2, p. 259, y se acompaña de la advertencia de
que el libro no da magnitud.

**Consecuencias.** Deja de incumplir la regla de oro nº 1 por la vía sutil: no
era una constante sin cita, era una constante con una cita que no decía lo que
se le atribuía. Queda claro para el siguiente que quiera ajustarla que no está
tocando el método, está tocando una decisión nuestra.

**Alternativas descartadas.** *Quitar las sillas del motor* y dejar que el
usuario las añada a mano, que es como lo describe el libro. Se descartó porque
el rebaje en la cabecera de vaguada es geomorfológicamente correcto y el propio
libro dice que hay que incorporarlo al diseño; lo que no dice es cuánto.

---

## ADR-019 · `dist_cresta_swale_m` es una LONGITUD CONVEXA, no un retranqueo

**Fecha**: 2026-08-10 · **Estado**: aceptada · **Origen**: B-032

**Contexto.** El ajuste *Maximum distance from ridgeline to swale head* se
estaba usando para **amputar** metros del final de cada vaguada
(`hillslopes._recortar_cola`). El libro, tabla de ajustes del *Geometry tab*
(p. 191), dice otra cosa:

> *«maximum distance from ridgeline to swale head — option 1 — **specify swale
> convex length** based on reference area observations»*
> *«maximum convex length of a sub-ridge – **1.5 x** 'xx' — sub-ridge convex
> length calculated as 1.5 x the specified swale convex length»*

Y el mecanismo del relieve, figura 8-11, p. 204:

> *«**A depression is formed by the shorter swale convex length between the
> longer adjacent sub-ridge convex lengths** and runoff water is directed into
> the swale bottom.»*

Es decir: subcresta y vaguada **salen las dos del cauce y mueren las dos en la
divisoria** (p. 211); lo que hunde la vaguada es que su **tramo convexo es más
corto**, no que sea más corta.

Medido en el Ej_2:

| | nuestro | original |
|---|---|---|
| Alcance del extremo alto, subcrestas | 63.4 m | 65.1 m ✅ |
| Alcance del extremo alto, **vaguadas** | **44.0 m** | **62.4 m** ❌ |
| Pendiente recta de vaguada (p50 S-O) | 10.8 % | 24.0 % |

**Decisión.**

1. `dist_cresta_swale_m` pasa a ser la **longitud convexa de la vaguada**
   (`ridges.convexo_vaguada`), con este orden: el ajuste del canal; si no, el
   global `convexo_swale_m` cuando `convexo_swale_activo`; si no,
   `max_dist_cresta_cabecera` (xrh), citado de la p. 236 («*the convex swale
   length, xc, was similar to the xrh value*»).
2. La subcresta sigue con 1.5 × esa longitud (`convexo_subcresta`, que ya era
   correcto en sus dos ramas).
3. **La cota de coronación la fija SIEMPRE la longitud convexa de la
   SUBCRESTA.** Es una propiedad del filo, no de la línea que pregunta. Como
   `Δz = s_max·(D − lc/2 − lf/2)` **crece al menguar `lc`**, dejar que cada
   línea usara la suya habría hecho que la vaguada coronara **más alto** que la
   subcresta vecina (medido, D = 70 m: 15.68 m frente a 12.71 m). Estaba
   enmascarado por el retranqueo, y quitarlo sin esto habría empeorado el
   diseño.
4. `hillslopes._recortar_cola` se conserva **desconectada**, como
   `divides._rehacer_laderas`, con el aviso de por qué.

**Consecuencias.** La depresión de la vaguada **sale sola de la ecuación que ya
teníamos**, sin ningún parámetro nuevo: con el mismo desnivel y los mismos
extremos, el perfil de menor longitud convexa cae hasta **1.28 m más a media
ladera**. Cambia el balance corte/relleno (las vaguadas suben hasta el filo), así
que la tabla de `context/06` hay que rehacerla entera.

**Alternativas descartadas.** *Quitar solo el retranqueo y dejar la longitud
convexa como estaba* (`0.05·D` inventado). No sirve: las vaguadas llegarían
arriba pero seguirían sin formar depresión frente a las subcrestas, que es todo
el punto del patrón.

---

## ADR-018 · La pendiente N-E es un objetivo de DISEÑO, no solo una comprobación

**Fecha**: 2026-08-10 · **Estado**: aceptada · **Cierra** P-09

**Contexto.** El método tiene **dos** objetivos de pendiente de ladera:
*Maximum straight-line slopes* (`pendiente_max_pct`) y *North or East
straight-line slopes* (`pendiente_NE_pct`), más tendido porque las laderas
orientadas al norte y al este retienen más humedad y vegetación. En el proyecto
original del Ej_2 son `m_fMaxSlope 33` y `m_fNESlope 22`.

Nuestro motor **leía el segundo ajuste y no lo usaba para nada**: trazaba todas
las laderas con la pendiente general y `pendiente_NE_pct` solo aparecía en
`checks.pendientes_de_ladera` (C20/C21). Es decir, el complemento avisaba de un
incumplimiento que él mismo acababa de provocar.

Además la orientación estaba **invertida**. `checks._rumbo` tomaba el acimut de
`pts[0]` a `pts[-1]`, pero las subcrestas y las vaguadas se trazan del cauce
hacia arriba, así que su primer vértice es el **pie**: lo que mira al sur se
clasificaba como norte, y al revés.

**Decisión.**

1. La definición de «ladera norte o este» vive **una sola vez**, en
   `core/params.py` (que no importa QGIS): `es_orientacion_NE(acimut)`,
   `rumbo_de_ladera(pts)` y `pendiente_max_ladera(glob, acimut)`. Las usan
   tanto el trazado (`ridges`, `hillslopes`) como `checks`. Tenerlas dos veces
   era garantizar que el motor y el *Error Log* acabaran discrepando.
2. `rumbo_de_ladera` devuelve el acimut **de descenso**, tomando como cabeza el
   extremo de mayor cota. Aquí usar la cota **no** contradice la regla de oro
   nº 3: la orientación de una ladera *es por definición* la dirección de
   máxima pendiente descendente, no un rasgo que se esté deduciendo de ella.
3. `ridges._z_ladera` recibe `glob` y elige el objetivo: ya conoce el canal más
   próximo, y la ladera desciende hacia él, así que la orientación se sabe **sin
   haber trazado la línea todavía**. Eso resuelve el huevo y la gallina (la
   pendiente decide la cota de coronación, que decide dónde está la cresta).

**Consecuencias.** Las crestas de las laderas orientadas al norte y al este
bajan en la proporción 22/33 = **0.67** respecto de las demás. Cambia la
superficie de diseño, el balance de tierras y las cotas de coronación, así que
la tabla de referencia de `context/06` hay que rehacerla entera después de este
cambio. Los avisos C20/C21 dejan de dispararse por culpa del propio motor.

**Alternativas descartadas.**

- *Aplicarlo como post-proceso, bajando las crestas ya trazadas.* Sería parchear
  al final, que es el error recurrente del proyecto (§4 de `AGENTS.md`): la
  cota de coronación es un dato de entrada del perfil, no un resultado que se
  pueda retocar sin deformar la ladera.
- *Poner los helpers en `ridges.py` y que `checks` los importe.* `checks` no
  importa `ridges` hoy y arrastrarlo entero (con QGIS) para dos funciones de
  trigonometría no compensa. `params` ya lo importan los dos y es Python puro.

---

## ADR-017 · El perfil del cauce respeta las pendientes pedidas; la cabecera puede ser convexa

**Fecha**: 2026-08-10 · **Estado**: aceptada · **Origen**: B-023

**Contexto.** `profile.disenar_perfil` exigía **concavidad estricta**,
`s_cabecera < m < s_boca` con `m` la pendiente media. Cuando no se cumplía —es
decir, cuando la cabecera pedida era **más tendida** que la media— re-empinaba
la cabecera con `s_cabecera = 2m − s_boca` para forzar una parábola cóncava.

Medido en el Ej_2 (Rom_Pla) con `scripts/comparar_original.py`:

| canal | pedida | nuestra (antes) | original |
|---|---|---|---|
| main L1 | −15.4 % | **−26.91 %** | −16.16 % |
| main R4 | −17.44 % | **−36.95 %** | −18.29 % |
| main | −18.0 % | −18.0 % | −17.57 % |

El canal principal salía bien porque su cabecera **sí** es más empinada que la
media; los tributarios cortos y empinados, no. Y como de la cota del cauce
cuelgan las crestas, las laderas y la superficie, el error se propagaba a todo.

**Decisión.** Las dos pendientes del usuario **se respetan**. Lo único que se
impone encima es la **monotonía**: la condición suficiente de Fritsch–Carlson
para la cúbica de Hermite, `0 ≤ s_cabecera/m, s_boca/m ≤ 3`, más el signo (una
pendiente que remonta se lleva a 0). Si actúa, se marca `ajustado` y se informa
(invariante H7).

Cuando `|s_cabecera| < |m|` el perfil **no puede** ser cóncavo en todo su
recorrido: para bajar el desnivel que hay que bajar, algún tramo intermedio
tiene que ser más empinado que la cabecera. La cúbica de Hermite lo resuelve
sola, con la pendiente creciendo desde la boca, haciendo máximo en torno al
70–80 % del recorrido y decreciendo hacia la cabecera: un **tramo convexo de
cabecera**. Se marca en `PerfilLongitudinal.cabecera_convexa`, se avisa desde
`builder` y se expone en `perfiles_efectivos` para el optimizador.

**Consecuencias.** main L1 pasa de 25.8 % a 16.5 % en la cabecera (original
16.2 %) y main R4 de 35.2 % a 19.4 % (original 18.7 %), con la misma forma de
perfil que el original —máximo en el decil 7 y descenso hacia la cabecera— y
manteniendo la monotonía. El aviso de `builder` deja de ser «te he recortado la
pendiente» y pasa a ser «el tramo alto es convexo», que es información de
diseño, no un recorte. `checks.perfil_ajustado` (C02) deja de dispararse en los
casos en que la pendiente pedida sí era realizable.

**Alternativas descartadas.**

- *Dejar la concavidad estricta y avisar mejor.* No sirve: el problema no era
  la comunicación, era que el diseño salía mal. Y el original demuestra que la
  cabecera convexa es la solución correcta, no un mal menor.
- *Añadir un tramo convexo explícito, con su longitud como ajuste nuevo.* No
  hace falta ninguna constante nueva: la propia curva de Hermite lo produce en
  cuanto se deja de forzar la concavidad. Regla de oro nº 1 — no metas una
  constante que no necesitas.

**La concavidad estricta no es una regla del método.** El método pide un perfil
cóncavo **en su conjunto** [LIBRO cap. 2, DL78]; el propio programa original
produce cabeceras convexas cuando el desnivel lo exige, y así está medido.

---

## ADR-016 · La marca sale también de los NOMBRES DE FICHERO y de capa

**Fecha**: 2026-08-07 · **Estado**: aceptada · **Completa a** ADR-015 ·
**Deroga** la parte de ADR-014/ADR-015 que conservaba `GF_` y `.geofluv.json`

**Contexto.** ADR-015 limpió los rótulos, los menús y los títulos, pero dejó
fuera a propósito lo que llamó «compatibilidad técnica»: el prefijo de capa
`GF_`, las extensiones `.geofluv.json` y `.geofluv-settings.json`, la clave de
QSettings `GeoFluvQ/report_formats` y el formato por defecto `GEOFLUV` del
Report Formatter.

El razonamiento de entonces era que eso «no es de cara al público». **No es
cierto, y basta con abrir el complemento para verlo**: el prefijo aparece en
cada capa del panel de capas de QGIS, la extensión aparece en el filtro del
diálogo *Open / Save Project As*, en el nombre de todo fichero que el usuario
guarda y en el texto de ayuda; el formato `GEOFLUV` es la primera entrada del
desplegable del Report Formatter. Es exactamente el mismo incumplimiento del
§12 que motivó ADR-015, un nivel más abajo.

Lo que sí era cierto era el coste: romperlo invalida los proyectos ya guardados.
Pero el complemento **todavía no se ha publicado en el repositorio oficial de
QGIS**, así que el universo de proyectos afectados es el del propio autor. Es
ahora o nunca: dentro de seis meses el argumento de compatibilidad ya no será
retórico.

**Decisión.** `GRD`, por *Geomorphic Reclamation Designer*:

| Antes | Ahora |
|---|---|
| prefijo de capa `GF_` (18 capas) | `GRD_` |
| proyecto `*.geofluv.json` | `*.grd.json` |
| ajustes `*.geofluv-settings.json` | `*.grd-settings.json` |
| formato por defecto `GEOFLUV` | `STANDARD` |
| clave QSettings `GeoFluvQ/report_formats` | `GeomorphicReclamation/report_formats` |
| exporta `geofluv_check.csv`, `geofluv_optimization_log.txt` | `grd_check.csv`, `grd_optimization_log.txt` |
| temporales `geofluv_*.tif` | `grd_*.tif` |
| memoria de IA `memoria_geofluv.md` | `memoria_metodo.md` |

La extensión y su filtro se definen **una sola vez**, en `core/project.py`
(`EXT_PROYECTO`, `FILTRO_PROYECTO`, `EXT_AJUSTES`, `FILTRO_AJUSTES`), en vez de
repetirse en cada `QFileDialog`. `nombre_desde_ruta()` quita la extensión
entera: con `os.path.splitext` el proyecto se habría llamado «mina.grd».

**Ruptura limpia, sin capa de compatibilidad.** Se descartó leer también la
extensión antigua: mantener `*.geofluv.json` en el filtro de apertura deja la
marca justo donde se quería quitar. El contenido del JSON no cambia —mismas
claves, mismo esquema—, así que migrar es **renombrar el fichero**. Las capas se
regeneran desde las entradas, que es el diseño de siempre, así que ahí no hay
nada que migrar.

**Qué NO se toca.** Los identificadores internos que no se muestran en ninguna
parte: `GeoFluvBuilder`, `GeoFluvProject`, `GeoFluvDock`, `GeoFluvQPlugin`.
Renombrarlos es ruido en el diff sin beneficio para nadie. Y siguen sin tocarse
los comentarios y docstrings que citan el método o miden contra la salida del
programa original: eso es atribución de la fuente, obligatoria por la regla de
oro nº 1.

**Consecuencias.**

- Hubo que **reescribir tres reglas de `AGENTS.md`** (§1.9, §10 y §12) que
  prohibían explícitamente este cambio. Sin eso, la siguiente sesión de
  cualquier agente lo habría revertido por contrato.
- Un proyecto anterior se abre renombrando `x.geofluv.json` → `x.grd.json`.
- Las 84 pruebas que no necesitan QGIS siguen en verde; el árbol de capas y los
  diálogos de fichero **están pendientes de verificar en QGIS real** (§8), que
  es donde `test_integracion.py` y `test_gui.py` se saltan solos.

**Alternativas descartadas.**

- *No hacer nada*: es incumplir §12 en el panel de capas y en cada diálogo de
  guardado, que es donde más se ve.
- *`.grdesign.json` o `.geomorph.json`*: inequívocas, pero más largas. Se
  aceptó el matiz de que en entorno SIG `.grd` suena a ráster de Surfer: no hay
  colisión real, porque el glob es `*.grd.json` y el fichero es JSON.
- *Aceptar también la extensión antigua al abrir*: costaba una línea y salvaba
  la migración, pero deja «geofluv» escrito en el filtro del diálogo, que es
  precisamente lo que se quería eliminar.
- *Renombrar también las clases*: diff enorme, cero beneficio visible.

---

## ADR-015 · La marca sale también de la INTERFAZ, no solo del nombre

**Fecha**: 2026-08-07 · **Estado**: aceptada · **Completa a** ADR-014

**Contexto.** ADR-014 renombró el paquete, el repositorio y el nombre público,
pero **no tocó el texto que ve el usuario**. Al revisar el repositorio antes de
publicarlo se encontró que la interfaz seguía presentando el complemento como el
producto original: el menú de QGIS se llamaba `Natural &Regrade`, seis comandos
eran *Design GeoFluv Regrade*, *Draw GeoFluv Contours*, *Calculate GeoFluv
Volume*…, el panel se titulaba `GeoFluvQ ver.X`, el grupo de capas `GeoFluv
<proyecto>` y la guía *GeoFluvQ — Natural Regrade*.

Es decir: el propio §12 de `AGENTS.md` («nunca presentes el complemento como
GeoFluv a secas… tampoco en la interfaz») se estaba incumpliendo en el sitio más
visible de todos. Y es justo lo que revisa el repositorio oficial de
complementos de QGIS antes de aprobar una publicación.

**Decisión.** Todo texto que el usuario ve va **sin la marca**:

| Antes | Ahora |
|---|---|
| menú `Natural &Regrade` | `Geomorphic &Reclamation` |
| `Design GeoFluv Regrade` | `Design Regrade` |
| `Draw GeoFluv Contours` | `Draw Design Contours` |
| `Calculate GeoFluv Volume` | `Calculate Design Volume` |
| `Create GeoFluv Layers` | `Create Design Layers` |
| `GeoFluv Boundary` | `Design Boundary` |
| `GeoFluv Project Inspector` | `Project Inspector` |
| `Natural Regrade Global Settings` | `Global Settings` |
| panel `GeoFluvQ ver.X` | `Geomorphic Reclamation Designer ver.X` |
| grupo de capas `GeoFluv <proyecto>` | `Geomorphic Reclamation <proyecto>` |

**Qué NO se toca** (compatibilidad técnica, ADR-014): prefijo `GF_`, extensión
`.geofluv.json` y `.geofluv-settings.json`, la clave de QSettings
`GeoFluvQ/report_formats`, y las clases `GeoFluvBuilder`, `GeoFluvProject`,
`GeoFluvDock`, `GeoFluvQPlugin`.

> ⚠️ **SUPERADO por ADR-016.** Este párrafo ya no está vigente. El prefijo, las
> dos extensiones, la clave de QSettings y el formato `GEOFLUV` **sí** son de
> cara al usuario —se ven en el panel de capas y en cada diálogo de fichero— y
> se renombraron a `GRD_`, `.grd.json`, `.grd-settings.json`,
> `GeomorphicReclamation/report_formats` y `STANDARD`. De lo de arriba solo
> siguen en pie las **clases**.

**Qué tampoco se toca**: los **comentarios y docstrings** que citan el método o
miden contra la salida del programa original. Citar la fuente con atribución es
legítimo y además es la trazabilidad del motor (regla de oro nº 1). Lo que no
vale es *presentarse* como ese producto.

**La única mención de la marca en texto de usuario** es ahora la cita atribuida
de la portada de la guía: *«método fluvio-geomórfico (tipo Natural Regrade /
GeoFluv) publicado por Bugosh y Martín Duque (2024)… implementación
independiente, no afiliada ni derivada de su programa»*. Esa es la forma
prescrita por §12 y debe conservarse.

**Consecuencias.**
- El usuario que venga del programa original ve otros rótulos. Se ha conservado
  **el mismo orden y la misma estructura** de menú y panel para que siga
  reconociendo la secuencia de trabajo.
- El grupo de capas cambia de nombre: un proyecto anterior abrirá y creará el
  grupo nuevo. Las capas `GF_*` y el `.geofluv.json` siguen intactos, así que no
  se pierde nada, pero conviene avisarlo en el changelog.
- 84 tests siguen en verde y `ruff` limpio: ningún test dependía de los rótulos.

**Alternativas descartadas.**
- *Dejarlo como estaba*: es el riesgo que ADR-014 quiso evitar, y reaparece
  entero en el punto más visible.
- *Cambiar solo el panel y la guía*: el menú es lo primero que ve el revisor de
  plugins.qgis.org y lo que aparece en las capturas.
- *Renombrar también `GF_` y las clases*: rompería proyectos existentes sin
  ganar nada; §12 ya los clasifica como internos.

---

## ADR-014 · Nombre público «Geomorphic Reclamation Designer»

**Fecha**: 2026-07 · **Estado**: aceptada

**Contexto.** El proyecto se ha llamado internamente `geofluv_q` / *GeoFluvQ*.
*GeoFluv™* y *Natural Regrade®* son **marcas registradas** de sus titulares
(N. Bugosh / Carlson Software). Publicar en GitHub un complemento libre con ese
nombre es un riesgo legal innecesario y además induce a pensar que es el
producto original o un derivado suyo.

**Decisión.**
- Nombre público del complemento: **Geomorphic Reclamation Designer**.
- Paquete Python / carpeta del complemento: `geomorphic_reclamation_designer`.
- Repositorio: `geomorphic-reclamation-designer`.
- **Se conservan** por compatibilidad técnica: prefijo de capa `GF_`, extensión
  `.geofluv.json`, clases `GeoFluvBuilder`, `GeoFluvDock`, `GeoFluvProject`.
- El método se cita siempre como *"método fluvio-geomórfico (tipo Natural
  Regrade)"*, con la referencia bibliográfica.

**Por qué este nombre.** *«Geomorphic reclamation»* es el **término estándar y
descriptivo** del campo, no la marca de nadie: se usa así en la literatura
revisada por pares (Martín Duque et al. 2017; Bugosh & Epp 2019). Un nombre
descriptivo es exactamente lo que interesa aquí: nadie puede reclamar derechos
exclusivos sobre él, y dice qué hace el programa sin apoyarse en la marca ajena.

**Ojo con una confusión posible.** *Geomorphic Reclamation Design* (2024) es
además el **título del libro** de Bugosh & Martín Duque, que es nuestra
referencia principal. El nombre del complemento se le parece mucho. Para que no
parezca el software oficial del libro:

- el `NOTICE` lo dice explícitamente;
- el README cita el libro **como fuente**, con sus autores, no como respaldo;
- nunca se usa la formulación *«el software del libro»* ni equivalentes.

Si algún día llegara una objeción de los autores, el cambio es barato (§«Por qué
el renombrado fue barato»).

**Consecuencias.** Los usuarios que tenían `geofluv_q` instalado verán un
complemento nuevo en la lista; deben desinstalar el viejo. **Los proyectos
`.geofluv.json` y las capas `GF_*` siguen funcionando sin tocar nada.**

**Por qué el renombrado fue barato.** Todo el código usa **importaciones
relativas** (`from .core.compat import …`), así que renombrar la carpeta raíz
solo obligó a tocar el nombre de la carpeta, `metadata.txt` y `__init__.py`.
Merece la pena conservar esa propiedad: **no metas importaciones absolutas del
paquete** en `src/`.

**Alternativas descartadas.**
- *Seguir con GeoFluvQ*: riesgo de marca al publicar.
- *Mine Geomorphological Rehabilitation*: correcto pero largo y algo genérico;
  «rehabilitation» es menos usado que «reclamation» en la literatura del campo.
- *OpenRegrade / GeoRegrade*: cortos y con buena resonancia, pero *«regrade»*
  evoca directamente *Natural Regrade®*, que es justo lo que se quería evitar.
- *Renombrar también `GF_` y `.geofluv.json`*: rompería todos los proyectos ya
  hechos por el autor a cambio de nada.

---

## ADR-013 · Licencia AGPL-3.0-or-later + CLA

**Fecha**: 2026-07 · **Estado**: aceptada

**Contexto.** El autor quiere: (a) que el código sea **siempre libre**, (b) que
cualquiera pueda usarlo **gratis, personal y profesionalmente**, y (c)
reservarse la posibilidad de **cobrar en el futuro por un servicio web / en
servidor**.

**Decisión.** **AGPL-3.0-or-later** para el código, más un **CLA** que otorga a
Samuel Sáez López los derechos necesarios para relicenciar (modelo *open core /
doble licencia*).

**Por qué AGPL y no GPL o MIT.** La AGPL es la única de las tres que cubre el
caso *"alguien monta un SaaS con esto y no devuelve nada"*: su §13 obliga a
publicar el código fuente **también a los usuarios que interactúan por red**.
Eso es exactamente lo que preserva la opción comercial del autor: un tercero que
quiera ofrecerlo como servicio sin liberar su código tendrá que negociar una
licencia comercial.

**Por qué el CLA es imprescindible.** Sin él, el autor **no podría** ofrecer una
licencia comercial, porque el copyright de las contribuciones sería de cada
contribuyente y la AGPL no permite relicenciar código ajeno.

**Consecuencias.**
- Todo contribuyente firma el CLA antes de que se acepte su PR.
- Cada fichero fuente lleva cabecera de copyright y licencia.
- Nunca se integra código de terceros sin CLA ni código de origen propietario.

**Alternativas descartadas.**
- *MIT/Apache*: no cumple (c) — cualquiera monta el SaaS y no devuelve nada.
- *GPL-3.0*: no cubre el uso por red, que es justo el caso que preocupa.
- *AGPL sin CLA*: bloquearía al propio autor para relicenciar.
- *Fuente disponible no libre (BSL)*: incumple (a).

---

## ADR-012 · `context/` como memoria explícita del proyecto

**Fecha**: 2026-07 · **Estado**: aceptada

**Contexto.** El desarrollo se ha hecho en sesiones largas con asistentes de IA
que pierden el contexto al terminar. Se han repetido errores ya resueltos y se
ha perdido tiempo redescubriendo por qué una constante vale lo que vale.

**Decisión.** Carpeta `context/` versionada con el conocimiento condensado
(método con citas, bugs con causa raíz, decisiones, invariantes, métricas
medidas, trampas del entorno, backlog y bitácora), y obligación en `AGENTS.md`
de leerla antes de tocar y de actualizarla al terminar.

**Consecuencias.** Cuesta unos minutos por sesión. A cambio, cualquier agente
arranca con el estado real del proyecto en lugar de deducirlo del código.

**Alternativas descartadas.** *Comentarios en el código* (no cuentan la historia
transversal); *issues de GitHub* (no los lee un agente por defecto);
*documentación de usuario* (público distinto, objetivo distinto).

---

## ADR-011 · Primero curvar, después recortar; nunca volver a curvar

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-017

**Decisión.** El perfil de una línea de ladera se calcula **una sola vez**, con
la geometría completa, y **después** se recorta contra el corredor del cauce.
`divides._rehacer_laderas()` se conserva pero **no se llama**, con aviso en el
docstring.

**Consecuencias.** Una línea recortada conserva la forma de la curva original en
el tramo que sobrevive — que es lo que hace el original y lo que el usuario
identificó como el resultado bueno.

---

## ADR-010 · El pie de ladera se identifica por distancia, no por cota

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-018

**Decisión.** `Corredor._cerca(x, y) → (índice, distancia, estación)` es el
criterio único para saber qué extremo de una línea es el pie.

**Razón física.** Donde el cauce va **en relleno**, la ladera desciende *desde*
el cauce: el pie es el punto **más alto**. Cualquier criterio basado en Z falla
en ese caso, que es frecuente en el margen alto del perímetro.

---

## ADR-009 · La divisoria no tiene límite de pendiente de ladera

**Fecha**: 2026-07 · **Estado**: aceptada, **reverificada 2026-08** ·
**Origen**: bug B-012

**Decisión.** Al perfil longitudinal de una divisoria **no** se le aplica
`pendiente_max_pct`. Solo actúa `MAX_PENDIENTE_FILO = 100 %` como cortapicos.

**Evidencia.** La divisoria del original desciende al **41 % de media y 73 % de
máximo**. Aplicarle el máximo de ladera la dejaba 17 m colgada sobre el cauce.

**Reverificación (v1.0.21).** Se puso en duda al medir el Ej_2, donde las
divisorias del original no pasan de 34 % teniendo `pendiente_max_pct` = 33 %, y
además su segmento más empinado mide **33.000 % exacto**. Parecía un recorte.
No lo es:

* Los dos ejemplos tienen `pendiente_max_pct` = 33 % y en los dos **las líneas
  de `GF_Ridges` lo superan de largo**: máximo 65.7 % en el Ej_2 y 84.7 % en el
  Ej_1, con el 14 % y el 52 % de los segmentos por encima del 33 %. Eso no
  necesita separar divisorias de laderas y por sí solo cierra la cuestión: el
  ajuste no es un tope del perfil longitudinal de las crestas.
* En el Ej_2 el 33.000 % es **un único segmento**, y el siguiente baja a
  30.475: no hay acumulación contra el tope, que es lo que delata un recorte.
  Las líneas de ladera, en cambio, atraviesan el 33 % sin discontinuidad
  ninguna (108 / 72 / 79 / 67 / 67 segmentos por decil).
* El Ej_1 **no sirve de contraste**: nuestro diseño allí tiene 2 canales frente
  a los 3 del original, así que no es comparable. Anotado en `08_pendiente.md`.

Lo que sí quedó claro es que el defecto que se buscaba no era de tope sino de
ruido: la mediana ya coincidía (10.9 % frente a 11.8 %) y todo el error estaba
en la cola. Ver **B-036**.

---

## ADR-008 · Correcciones de extremo mezcladas con *smoothstep*

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-009

**Decisión.** Ninguna corrección de cota se aplica a un solo vértice.
`ajustar_extremo()` y `_sellar_extremo()` reparten la corrección sobre una
longitud de mezcla (`MEZCLA_*`) con `3u² − 2u³` y después imponen monotonía
direccional.

---

## ADR-007 · Orden fijo dentro de `perfil_desde_control()`

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-014

**Decisión.**
`_restaurar_control → _monotonizar → _suavizar_entre_control → _limitar_pendiente`.
**El limitador de pendiente va SIEMPRE el último.**

---

## ADR-006 · Recorte por diferencia geométrica, no recorriendo desde los extremos

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-010

**Decisión.** `recortar_contra_corredor()` calcula la diferencia geométrica real
y devuelve **todos** los trozos exteriores al corredor.

**Principio general.** *"Las implementaciones deben funcionar en todos los
escenarios, no solo en el ejemplo con el que depuramos."* Recorrer desde los
extremos es un atajo que solo funciona en la topología del caso de prueba.

---

## ADR-005 · La máscara del corredor protege el cauce del suavizado

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-015

**Decisión.** `surface.mascara_corredor(...)` genera una máscara fija que
`suavizar_raster()` respeta, y la celda del ráster se dimensiona con
`CELDAS_POR_CAUCE = 3.0` sobre la anchura **mediana** del bankfull.

**Por qué la mediana y no la mínima.** Con la mínima, un solo tramo estrecho
disparaba el número de celdas por encima de `CELDAS_MAX = 12 000 000`.

---

## ADR-004 · La IA es guía, no motor

**Fecha**: 2026-06 · **Estado**: aceptada

**Decisión.** El bucle de optimización lo lleva el complemento. El modelo local
recibe números, historial e imágenes y devuelve **en JSON qué variables mover y
por qué**. El complemento valida cada propuesta contra rangos y regenera la
geometría con el motor.

**Consecuencia clave.** **Toda solución es geométricamente válida por
construcción.** El modelo no puede producir un diseño imposible; como mucho,
propone un cambio que se ignora por salirse de rango (y queda anotado).

**Además.** El modelo corre **en local** (Ollama / LM Studio): sin servidor, el
resto del complemento funciona igual y el mismo bucle sigue en modo numérico.
No sale ningún dato del proyecto a Internet.

---

## ADR-003 · La divisoria es una V que pasa por la confluencia

**Fecha**: 2026-06 · **Estado**: aceptada · **Origen**: bug B-007

**Decisión.** `ridges._partir_en_confluencias()` parte la cadena Voronoi en la
confluencia y genera **dos** crestas, ancladas ahí en X, Y y Z.

**Razón geométrica.** Aguas arriba de la unión hay divisoria por los **dos**
lados del tributario.

---

## ADR-002 · Atributos por nombre de campo

**Fecha**: 2026-05 · **Estado**: aceptada · **Origen**: bug B-006

**Decisión.** `compat.attrs()` es el único camino para rellenar atributos.
GeoPackage añade un campo `fid` al principio y desplaza todo lo demás.

---

## ADR-001 · `hydrology.py` sin QGIS

**Fecha**: 2026-04 · **Estado**: aceptada

**Decisión.** El módulo hidráulico es **Python puro**, sin importar `qgis.*`.

**Razón.** Es la parte que hay que poder verificar contra el libro sin arrancar
un SIG. Permite `pytest` en CI sin instalar QGIS, y hace `test_libro.py` posible.

**Consecuencia.** Cualquier cosa que necesite capas va en `builder` o en
`surface`, no en `hydrology`.
