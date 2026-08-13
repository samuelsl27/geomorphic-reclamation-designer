# Bitácora de sesiones

Una entrada por sesión de trabajo, lo más reciente arriba. **Añade la tuya al
terminar.** Plantilla al final.

---

## 2026-08-13 · v1.0.25 — la divisoria era equidistante de la línea equivocada

**Versión**: 1.0.25. Regenerada y medida en QGIS **headless**; falta mirarla en
la interfaz y rehacer la tabla de `context/06`.

**De dónde salió.** Samuel dijo que las crestas que separan las cuencas seguían
saliendo más quebradas que las del original, con un pico raro, un enlace extraño
entre el tramo zigzag y el sinuoso, y crestas de subcuenca donde el original no
pone ninguna. Cuatro zonas marcadas en rojo sobre una captura.

**Lo que desatascó el diagnóstico** fue medir `|d₁ − d₂|` —la diferencia de
distancias a los dos cauces más próximos— en cada vértice de las divisorias del
original, contra dos referencias distintas: sus **líneas de valle** y sus **ejes
meandriformes**. Sale 0.02–0.73 m contra las primeras y 1.0–2.9 m contra los
segundos. Nosotros, exactamente al revés. Todo lo demás salió de ahí.

**La cadena de correcciones**, cada una destapando la siguiente:

1. **B-045**, la fuente del Voronoi: las líneas de valle, no los ejes.
2. **B-049**, regresión que creó la anterior: `hillslopes` seguía parando la
   marcha en la equidistancia de los ejes. Detectada **antes** de regenerar,
   midiendo la separación entre las dos curvas (mediana 1.12 m, p99 7.52).
3. **B-046**, el troceado: confluencias ajenas y brazos de nudo triple. De 11
   divisorias a **7**, las mismas que el original.
4. **B-047**, el enlace A↔sinuoso: las dos ondas compartían una sola fase.
5. **B-048** y **B-050**, los picos de las líneas de ladera: un ping-pong entre
   dos divisorias que se comía las 30 pasadas de `revisar`, y una cola de
   empalme que apuntaba al punto más próximo en vez de a donde va la línea.
6. **B-051**, la cota: el pie se anclaba a la rasante y el perfil llevaba un pie
   cóncavo de 75 m.
7. **B-052**, la emisión: el original pone una retícula y **borra** los vértices
   que caen sobre la recta.

**Dos veces me equivoqué y hubo que corregirlo con datos**: dije que el original
tenía 6 divisorias (tiene **7**; descarté la fid 1957 sin comprobarla) y dije que
dos de las nuestras se quedaban 96 m cortas (estaban **partidas**). El
clasificador fiable de divisoria no es la longitud ni la equidistancia: es la
**malla de emisión de 6.10 m**.

**Lo que se midió y NO se cambió.** El desacuerdo entre las dos particiones del
territorio —la rejilla de `builder`, que alimenta el caudal, y el Voronoi de
`ridges`, que dibuja las divisorias— es de −1.03 % a +0.68 % por cuenca y +0.01 %
en total. Unificarlas es reordenar `builder.construir()` entero, y no se hace por
un 1 %.

**Infraestructura.** `mcp__qgis__execute_code` se cancelaba siempre, aunque
`ping` y `get_layers` respondieran. La salida fue
`scripts/regenerar_en_qgis_headless.py`, que reproduce `dock._preview` entero con
el python de QGIS sin tocar los GeoPackage del usuario — y que cierra **P-16**.
De paso apareció que `tests/test_integracion.py` desempaquetaba dos valores de
una tupla de tres y llevaba **desde la v1.0.21 sin ejecutarse**, porque
`conftest` se salta ese fichero cuando no hay QGIS y la CI no lo tiene.

**Revisión de generalidad.** A petición de Samuel se repasaron las constantes
nuevas: cuatro estaban en metros y atadas a la escala del Ej_2 (el margen del
nudo triple, la tolerancia del límite, la ventana de mezcla y la del adelgazado).
Las cuatro pasan a ser relativas — porcentaje de la distancia, múltiplo de la
banda del límite, fracción de la longitud del canal y fracción del paso.

---

## 2026-08-10 · v1.0.20 — la forma del relieve de ladera

**Versión**: 1.0.20, **sin cerrar**: falta medirla en QGIS (P-17).

**De dónde salió.** El usuario regeneró con la v1.0.19 y dijo que el resultado
«no tiene nada que ver» con el original, con dos zonas marcadas en las curvas de
nivel. La v1.0.19 había arreglado el **perfil del cauce** —y eso sí funcionó:
main R4 sale `4.8 10.8 15.0 18.3 20.7 22.0 22.1 21.0 19.7 17.5` frente al
original `4.5 9.8 13.9 17.2 19.7 21.3 21.9 21.7 20.7 18.7`— pero el relieve que
cuelga de él seguía mal.

**Lo que desatascó el diagnóstico** fue descubrir que el DXF del original
**distingue por color** las 127 subcrestas (amarillo) de las 117 vaguadas
(cian). Separadas, se vio en una medida: **nuestras subcrestas llegan bien**
(63.4 m frente a 65.1) y **las vaguadas no** (44.0 frente a 62.4). Mezcladas, las
medias se compensaban y no se veía nada.

**Y la causa de fondo estaba en el libro**, no en el código: *Maximum distance
from ridgeline to swale head* **no es un retranqueo, es la longitud convexa de
la vaguada** (p. 191), y la depresión sale de que ese tramo es **más corto** que
el de las subcrestas vecinas (fig. 8-11, p. 204). Nosotros amputábamos 24 m a
cada vaguada.

**Bugs corregidos**: **B-028** (traza y cotas de la divisoria desemparejadas),
**B-032** (el retranqueo), **B-033** (`fundir_con_divisorias` pegaba el último
vértice), **B-034** (la marcha se paraba en el aire), **B-035** (contador de
sillas acumulado). **Decisiones**: ADR-019, ADR-020.

**Medidas.** El «antes» está en `context/06`. Verificado sin QGIS: la depresión
de la vaguada sale sola de la ecuación (1.28 m a media ladera), y el reparto de
las correcciones de extremo ya no deja acantilados. **133 tests** (117 → 133).

**Tres hipótesis mías que medí y descarté**, para que nadie las repita:

1. *La red del original es un mallado cerrado de extremos compartidos.* **No**:
   el 87 % de sus extremos tampoco coincide exactamente con otro.
2. *El original cubre más terreno.* **No**: distancia de un punto cualquiera a
   la línea más cercana, p50 4.9 m el original y 5.0 m el nuestro.
3. *Sus líneas curvan y las nuestras son rectas.* **No**: el original es aún más
   recto (sinuosidad 1.000; las nuestras 1.021).

**Y dos equivocaciones propias que conviene recordar:**

- **Le hice al usuario una pregunta con la premisa al revés.** Le propuse «que
  la divisoria emerja» porque creí que el original no tenía capa de divisorias.
  El libro dice justo lo contrario (glosario p. xxxiv, p. 211): la divisoria
  existe y las líneas de ladera tienen que **llegar** a ella. Hubo que
  corregirlo antes de implementar nada.
- **Casi estropeo el arreglo de las vaguadas.** Quitar el retranqueo sin más
  habría hecho que coronaran **más alto** que las subcrestas, porque la cota de
  coronación se calculaba con la longitud convexa de la línea que pregunta y
  `Δz` crece al menguar `lc`. Lo tapaba el propio retranqueo. **Cuando quites un
  parche, mira qué estaba tapando.**

**Y una corrección a un agente**: me avisó de una «cita inventada» sobre las
sillas en `divides.py`. No lo era: el texto entrecomillado es literal del libro.
Lo que estaba mal era la **sección** (§9.11.2, p. 259, no 9.4) y que el libro no
da ninguna cifra de profundidad, así que el 25 % es decisión nuestra (ADR-020).

**Lo que NO se ha tocado a propósito**: el criterio de «extremo alto», que sigue
decidiéndose por cota en cuatro sitios (→ P-19). Es estructural, no tiene
síntoma medido en el Ej_2, y meterlo en la misma tanda habría hecho imposible
saber cuál de los cambios movió qué al remedir. Y el ángulo de subcresta, que se
verificó con una prueba y **está bien**: la desviación medida es de la regla de
medir, no del motor.

**Pendiente**: P-17 (medir en QGIS), P-19, y arreglar `comparar_original.angulo()`
antes de volver a juzgar el ángulo.

---

## 2026-08-10 · v1.0.19 — el segundo ejemplo destapa cinco bugs de geometría

**Versión**: 1.0.19, **sin cerrar todavía**: falta remedir en QGIS real.

**Qué se hizo.** Meter el **segundo ejemplo de referencia** (Rom_Pla, 6 canales,
35.6 ha) y depurar contra él. El primero (Potoya, 2 canales) llevaba meses
dando el visto bueno a un motor que fallaba en cuanto había confluencias
múltiples, tributarios cortos y empinados, o un tramo con el cauce por encima
del perímetro.

**Lo primero fue construir la regla de medir**, porque no existía: `context/06`
afirmaba que `scripts/comparar_original.py` estaba escrito y no lo estaba
(P-12). Tres guiones nuevos, sin QGIS ni GDAL, ejecutables desde consola:
`lector_gpkg.py` (GeoPackage con `sqlite3` + parser WKB propio),
`comparar_original.py` y `leer_geo.py`.

Del parser hay que saber una cosa: el DXF del original llega con **arcos**, así
que sus polilíneas son `CompoundCurve` (tipo 9) y no `LineString`. Un lector que
solo entienda el tipo 2 devuelve **cero** entidades y la comparación sale vacía
**sin dar ningún error**. Es el mismo patrón que el MCP roto o el `except`
mudo: el fallo silencioso es el caro.

**Y lo segundo fue leer los datos de entrada** (→ B-022). Aparecieron los
ficheros nativos del programa original —`Ej_2_GeoFluv_File.geo` y
`GeoFluv_Ej2_Settings.ggs`—, que estaban en la carpeta desde el principio sin
usar. Los ajustes globales coincidían en las 22 claves; el `.geo` destapó **15
diferencias de canal**: los parámetros de R1↔R4 y R2↔R3 estaban **tecleados en
orden invertido**. Media sesión comparando geometrías que diferían por eso.

**Bugs corregidos**: B-022 (datos), **B-023** (perfil del cauce), **B-024**
(cota de cresta), **B-025** (muro vertical al empalmar), **B-026** (mesetas),
**B-027** (extremo alto supuesto). Más dos fallos **latentes** que ningún
ejemplo dispara —0 líneas `junction` en los dos— pero que se arreglaron porque
se ven leyendo y no midiendo: `ai_optimizer` no llamaba a
`divides.ajustar_divisorias` (puntuaba una superficie distinta de la del
usuario) y `topology.crestas_de_encuentro` emparejaba encuentros **por
coordenada X** y dejaba el extremo bajo de sus vaguadas colgado en mitad de la
ladera.

**Decisiones**: ADR-017 (cabecera convexa del perfil), ADR-018 (pendiente N-E
aplicada al trazado, cierra P-09).

**Medidas.** El «antes» completo de los dos ejemplos está en `context/06`. Lo
peor: 955 % de pendiente en un segmento de subcresta (el original no pasa de
65.7 %), 19 líneas por encima del 100 %, mesetas de 27 vértices y la cabecera de
main L1 al 23.67 % con −15.4 % pedido. Verificado ya sin QGIS: las pendientes de
cabecera vuelven al valor pedido y el reparto de las correcciones de extremo ya
no deja mesetas. **117 tests en verde** (84 → 117) y `ruff` limpio.

**Intentos fallidos y equivocaciones propias** — esto vale oro:

1. **Se anunció que las crestas salían un 27 % más bajas que las del original.**
   Era una medida mal hecha: se dividió la mediana de un reparto entre la
   mediana de otro. Medido **por línea**, la pendiente recta cresta-pie da
   p50 17.4 % frente a 19.0 %. La corrección de B-024 seguía siendo necesaria
   (código y documentación no pueden decir cosas distintas) pero su efecto es
   modesto, no el que se había anunciado.
2. **Se supuso que el factor del desnivel de ladera estaba entre 0.55 y 2/3.**
   El test lo tumbó: con `lc` = 12 m en una ladera de 60 m es **0.80**. Y el
   factor 2/3 no sale de `lc = D/3` sino de `lc = 0.367·D`. Las dos veces el
   test escrito *mientras* se hacía el cambio cazó la suposición.
3. **La primera versión de la mezcla adaptativa (B-026) se quedaba corta.**
   Se planteó como «alargar la mezcla hasta donde la línea ya rebasaba la cota
   objetivo», y seguía dejando mesetas de 7 vértices. La cota correcta sale de
   la pendiente máxima del smoothstep: `m ≥ 1.5·|dz|/gradiente`.

**Pendiente / nuevo en el backlog**: remedir los dos ejemplos en QGIS real y
rehacer la tabla de `context/06` (ADR-018 cambia el balance de tierras), pasar
*Check Design*, y cerrar 1.0.19 con `bump_version.py` y el zip.

---

## 2026-08-07 · La marca sale de los nombres de fichero y de capa (ADR-016)

**Versión**: sin subir (queda en 1.0.18). Cambio en el árbol, sin cerrar
versión ni tocar el CHANGELOG — decisión del usuario.

**Qué se hizo.** Rematar lo que ADR-015 dejó a medias. ADR-015 limpió rótulos y
menús pero dejó fuera el prefijo `GF_` y la extensión `.geofluv.json` con el
argumento de que eran «compatibilidad técnica, no de cara al público». Ese
argumento no se sostiene: el prefijo se ve en **cada capa del panel de capas** y
la extensión en **cada diálogo de guardado**.

- `GF_` → `GRD_` en las 18 capas (171 apariciones en 19 ficheros de código).
- `.geofluv.json` → `.grd.json`, `.geofluv-settings.json` → `.grd-settings.json`.
  **Ruptura limpia**: no se lee la extensión antigua, porque mantenerla en el
  filtro del diálogo deja la marca justo donde se quería quitar. El JSON no
  cambia, así que migrar es renombrar el fichero.
- Formato `GEOFLUV` del Report Formatter → `STANDARD`; clave de QSettings
  `GeoFluvQ/report_formats` → `GeomorphicReclamation/report_formats`.
- Ficheros que el complemento propone o escribe: `geofluv_check.csv`,
  `geofluv_optimization_log.txt`, los cinco temporales `geofluv_*.tif` y la
  memoria de IA `memoria_geofluv.md` → todos con `grd_` / nombre descriptivo.
- Prompts del optimizador: «diseño GeoFluv» → «diseño fluvio-geomórfico»,
  dejando **una** cita del método con atribución para que el modelo lo reconozca.

**Lo que costó tiempo.** Darse cuenta de que `AGENTS.md` **prohibía
explícitamente este cambio** en tres sitios (§1 regla 9, §10 y §12). Había que
reescribirlas en el mismo commit: si no, la siguiente sesión de cualquier agente
lo revierte por contrato. Es el tipo de cosa que no aparece si solo miras el
código.

**Decisión de fondo.** Ahora o nunca. El complemento aún no está en
`plugins.qgis.org`, así que el universo de proyectos rotos es el del propio
autor. Dentro de seis meses el argumento de compatibilidad ya no sería retórico.

**Verificado en QGIS 4.2.0 real** (P-15, cerrado): **15/15** pasos de
integración, **7/7** de GUI, 84 unitarias y `ruff` limpio. Más una prueba
específica de la ida y vuelta del `.grd.json`: la extensión se aplica, el
esquema del JSON no cambia, `nombre_desde_ruta()` deja «mina_norte» y no
«mina_norte.grd», y un fichero renombrado desde `.geofluv.json` se lee igual —
que es la demostración de que migrar es renombrar y nada más.

**Lo que apareció por el camino** (→ B-021). Los dos tests que necesitan QGIS
llevaban **meses rotos** en siete puntos, y nadie se había enterado porque
`conftest.py` los salta en silencio y el resumen dice «84 passed». Ninguno era
fallo del motor —el motor estaba bien y el test desfasado (firmas que pasaron a
devolver tuplas, campos e informes traducidos al inglés en ADR-015, una pestaña
nueva, un botón que ya no existe)—, pero mientras estuvieran rotos **no podían
detectar nada**, y son los únicos que cubren la búsqueda de capas por nombre,
que es exactamente lo que ADR-016 toca.

Aprovechado para que el test llame como llama el panel de verdad
(`generar_subcrestas` con `dem` y `crestas`), no una versión simplificada.

**Para la próxima sesión.** P-16: `scripts/correr_tests_qgis.py`, para que estos
dos tests no dependan de que alguien monte el envoltorio a mano. Y la
comprobación visual de los diálogos de fichero, que es lo único de P-15 que
queda sin mirar con el ratón.

---

## 2026-08-07 · v1.0.18 — publicación en GitHub

**Versión**: **1.0.18** (sin cambios de motor; rótulos, compatibilidad y
documentación). Primera versión publicada.

**Qué se hizo.** Revisión completa del repositorio antes de hacerlo público y de
enviarlo a `plugins.qgis.org`.

- 🔴 **La marca ajena seguía entera en la interfaz** (→ ADR-015). ADR-014 había
  renombrado el paquete y el repositorio, pero nadie había mirado lo que ve el
  usuario: menú `Natural &Regrade`, seis comandos *GeoFluv …*, panel `GeoFluvQ
  ver.X`, grupo de capas `GeoFluv <proyecto>`, guía *GeoFluvQ — Natural
  Regrade*. Justo lo que el §12 prohíbe y lo que revisa el repositorio oficial
  de QGIS. 119 líneas en 20 ficheros + guía regenerada.
- **Datos del caso de trabajo fuera de `context/` y del CHANGELOG**: había
  **coordenadas UTM reales** del emplazamiento (B-007, en dos sitios), el nombre
  del proyecto QGIS y el del grupo de capas de referencia. Sustituidos por
  descripciones sin georreferencia. Las cotas y las longitudes se quedan: son la
  tabla de referencia y no identifican nada por sí solas.
- **Rutas absolutas de la máquina de desarrollo** (perfil de usuario y carpeta
  de trabajo) → `%APPDATA%` y redacción genérica, en `AGENTS.md`,
  `docs/BUILD.md`, `docs/DESARROLLO.md` y `context/07`.
- **Historia de git reescrita** (`git filter-repo`) para purgar de *todos* los
  commits las coordenadas, los nombres del caso y las rutas absolutas:
  anonimizar solo el estado actual no sirve de nada si el dato sigue a un
  `git log -S` de distancia. Se hizo antes del primer push, cuando es gratis.
- 🔴 **`SECURITY.md` decía lo que no era.** Afirmaba que el complemento habla
  «solo con localhost» y que «no sale ningún dato de tu máquina», pero
  `ai_client.buscar_web()` consulta DuckDuckGo. Es *opt-in* y está desactivada
  por defecto, así que el fallo era de documentación, no de código — pero en un
  documento de seguridad eso es exactamente lo que no puede fallar. Corregido
  también en `docs/ARQUITECTURA.md` y en los dos README.
- URLs del repositorio → `github.com/samuelsl27/…` (cuenta personal; no existe
  la organización `opengeorock` en GitHub). Los enlaces a `opengeorock.org` y la
  autoría del equipo se mantienen.
- `.gitignore`: `*.pdf` y `*.docx` globales, no solo bajo `docs/metodo/`.
- 🔴 **B-020: el complemento no cargaba en QGIS 3.22–3.28.** `params.py` usaba
  `float | None` (PEP 604) en anotaciones de dataclass; en **Python 3.9** —el
  que traen esas versiones de QGIS— la anotación se evalúa al definir la clase
  y revienta con `TypeError`. Y `metadata.txt` declaraba
  `qgisMinimumVersion=3.22`. **Lo cazó la CI en el primer push**, en la matriz
  de 3.9; aquí no había forma de verlo, porque el PC de desarrollo va con QGIS
  4.2 y Python 3.12. Corregido con `from __future__ import annotations` y
  blindado activando la familia `FA` de `ruff` (FA102 lo marca solo;
  comprobado quitando la línea).
- **Versión cerrada como 1.0.18.** Se etiquetó primero como 1.1.0 —cambian
  rótulos visibles y el nombre del grupo de capas—, pero **el proyecto se queda
  en la serie 1.0.x mientras no haya nada definitivo**: el motor sigue
  calibrándose contra el original y el complemento sale como `experimental`. El
  salto a 1.1 se reserva para cuando la geometría se dé por estable. La release
  1.1.0 y su etiqueta se retiraron de GitHub el mismo día, antes de que nadie
  las instalara: en el gestor de complementos de QGIS, publicar 1.0.18 después
  de una 1.1.0 haría que la nueva **no** se ofreciera como actualización.

**Medido.** `ruff check .` limpio y **84 tests en verde** después del
renombrado: ningún test dependía de los rótulos. **CI en verde en la matriz
completa** (3.9, 3.10, 3.11, 3.12 + lint + metadatos + ZIP). El zip se
construye y verifica: 40 ficheros, 0.24 MB.

**Comprobado y limpio.** Historia de git (un solo autor, ningún fichero de datos
ha existido nunca en el árbol), `.gitignore`, `build_zip.py`, workflows de
GitHub sin secretos, `.claude/settings.local.json` correctamente ignorado.

**Lecciones.**

1. Un renombrado «por marca» que solo toca el nombre del paquete deja el riesgo
   intacto: lo que se juzga es lo que se ve. Cuando una decisión sea de naming,
   la lista de sitios a revisar es *menú, botones, títulos de ventana, mensajes,
   informes, guía y nombres de grupo de capas*, no `metadata.txt`.
2. **El entorno de desarrollo es el más moderno del parque, así que es el que
   menos bugs de compatibilidad encuentra.** Declarar `qgisMinimumVersion=3.22`
   no lo verifica nadie: hace falta algo que *ejecute* el código en el Python de
   esa versión. La matriz de la CI pagó su coste en el primer push.
3. Anonimizar el estado actual no sirve si el dato sigue en la historia. Purgar
   antes del primer push es gratis; después, no.

**Pendiente**: **verificar el renombrado en QGIS real** (los tests que necesitan
QGIS se saltan sin él; afecta al grupo de capas vía `layer_manager`), decidir si
se quita `experimental=True` y escribir `scripts/comparar_original.py` (P-12).

---

## 2026-08-07 · Reparar el MCP de QGIS y el arranque del entorno

**Versión**: 1.0.17 (sin cambios de motor; nada de `src/` tocado)

**Qué se hizo.**

- 🔴 **El MCP llevaba tiempo sin funcionar y no era evidente.** `.mcp.json` y
  `.vscode/mcp.json` describían `jjsantos01/qgis_mcp` en una ruta local
  **inexistente**, mientras que el complemento instalado en QGIS ya era
  **QGIS MCP** de `nkarasiak/qgis-mcp`. Configuración y realidad hablaban de
  proyectos distintos, así que el editor se quedaba sin herramientas y la única
  forma seria de validar geometría estaba muerta sin que saltara ningún aviso.
- Servidor reconfigurado a `uvx --from <etiqueta de GitHub> qgis-mcp-server`:
  **sin clonar y sin rutas de una máquina concreta**, para que el fichero, que
  va al repositorio, sirva tal cual a cualquiera que lo clone.
- **Versión fijada a una etiqueta, no a `main`.** Complemento y servidor se
  actualizan por sitios distintos y se desincronizan solos.
  `scripts/configurar_mcp.py` reescrito: lee la versión del complemento
  instalado, fija esa misma, hace un `ping` real por el socket (no basta con que
  el puerto acepte: otra cosa puede estar ocupándolo) y avisa si hay perfiles
  con versiones distintas.
- **Trampa 2 verificada como resuelta** (ver abajo).

**Medido.** Arrancando el servidor desde el propio `.vscode/mcp.json`:
118 herramientas, `ping` → `{"pong": true}`, `get_qgis_info` → QGIS
4.2.0-Belém do Pará, perfil `QGIS4/profiles/default`, con el proyecto de
prueba cargado.

**Trampa 2 (`execute_code` devolvía la salida de la llamada anterior): muerta.**
Tres marcas seguidas devolvieron cada una la suya, por el socket directo y por
la ruta completa cliente MCP → servidor → socket. La respuesta trae ahora
`stdout` y `stderr` separados. El ritual del `print("MARCA-n")` ya no hace
falta. Documentado como resuelto —no borrado— en `context/07`.

**Lección.** Una configuración rota no falla ruidosamente: simplemente no
aparecen las herramientas, y se acaba trabajando «a ojo» sin darse cuenta de que
se ha perdido el instrumento de medida. Es el mismo patrón que B-019 (el
`except` mudo) en otra capa: **el fallo silencioso es el caro**.

**Además**: `scripts/configurar_vscode.py` (nuevo) detecta las instalaciones de
QGIS de la máquina —aquí conviven 3.42.3, 3.44.6 y 4.2.0— y escribe las rutas de
Pylance, que antes había que poner a mano.

**Pendiente**: recargar la ventana de VSCode para que tome el servidor. Queda un
`qgis_mcp_plugin` v0.2.1 antiguo en el perfil `QGIS3`, inofensivo pero el guion
avisa de él cada vez.

---

## 2026-07 · Preparación del repositorio para desarrollo con IA

**Versión**: 1.0.17 (sin cambios de motor)

**Qué se hizo.**

- Reestructuración completa del proyecto como repositorio de desarrollo:
  `src/` · `scripts/` · `tests/` · `docs/` · `context/` · `.claude/` ·
  `.vscode/` · `.github/`.
- **AGENTS.md**: contrato de trabajo para agentes de IA, con 12 reglas de oro
  destiladas de todos los bugs del proyecto.
- **`context/`**: la memoria (glosario, método con citas, arquitectura,
  decisiones ADR, catálogo de bugs, invariantes, comparación con el original,
  entorno MCP, backlog, esta bitácora).
- **Renombrado** `geofluv_q` → `geomorphic_reclamation_designer`, nombre público
  *Geomorphic Reclamation Designer* (ADR-014, motivo de marca registrada).
  Barato porque todas las importaciones son relativas: solo 3 ficheros tocados.
- **Licencia AGPL-3.0-or-later + CLA** (ADR-013).
- Guiones de construcción: `build_zip.py`, `deploy_local.py`, `bump_version.py`.
- Configuración de MCP de QGIS 4.2, VSCode y GitHub Actions.
- Repositorio git inicializado con historia por versiones.

**Decisiones**: ADR-012, ADR-013, ADR-014.

**Pendiente**: publicar en GitHub (P-10), escribir
`scripts/comparar_original.py` (P-12).

---

## 2026-07 · v1.0.17 — el pie de ladera y el orden del pipeline

**Qué se hizo.**

- 🔴 **B-018**: el pie de ladera se identificaba por **cota** en dos sitios de
  `divides.py`. Donde el cauce va en relleno, el pie es el punto **más alto**.
  Corregido con `Corredor._cerca()` (distancia). Era la causa de la meseta y la
  zanja del margen oeste-sur.
- **B-017**: retirado el recurvado tras el recorte
  (`_rehacer_laderas` conservado pero desconectado, con aviso).
- **B-015**: máscara del corredor para que las curvas de nivel no crucen el
  cauce. Δz mediana en los cruces: 0.021 m.
- **B-016**: corregidas las ecuaciones de la **documentación** de
  `hydrology.py` (el código siempre estuvo bien) + `tests/test_libro.py`,
  17 tests cuyo docstring es la cita del libro.
- Marcador rojo en planta al deslizar sobre *View Longitudinal Profile*.
- Revisión completa del motor hidráulico contra los capítulos 2 y 4.

**Medidas**: subcresta idx 3: 1079.72→1062.00 (15.3 %), original
1079.08→1062.00 (12.4 %). *Check Design*: (2, 67, 56).

**Intento fallido**: quitar la monotonía (`monotona=False`) para arreglar las
zanjas. Producía zanjas en otros casos. Revertido.

**Observación sin resolver**: el pipeline pasó de ~3 s a ~15 s (→ P-04).

---

## 2026-07 · v1.0.16 — comprobaciones, divisorias y guía

**Qué se hizo.**

- **`core/checks.py`** nuevo: 22 comprobaciones C02–C52 con `Hallazgo`,
  `revisar()` y `resumen()`, y `gui/check_dialog.py` con filtros por severidad
  y grupo, filas pulsables y exportación a CSV. Errores: 13 → 9 → 2.
- **`core/divides.py`** nuevo (~1100 líneas): `Corredor`,
  `recortar_contra_corredor` por diferencia geométrica (B-010),
  `perfil_desde_control` con el orden correcto de etapas (B-014),
  `ajustar_extremo` con mezcla *smoothstep* (B-009).
- **Sillas de cresta** (libro §9.11.2, p. 259) y **recetario del capítulo 10** metido en el
  prompt de optimización de IA.
- Retirada la heurística `limite_de_ladera = 2 × media` (B-011).
- Retirado `pendiente_max_pct` del perfil de las divisorias →
  `MAX_PENDIENTE_FILO = 100 %` (B-012).
- Conmutador de idioma de la guía arreglado (B-008).
- `MAX_ORDEN = 10`, `MAX_PASADAS = 30`.

**Medidas**: peor gradiente 2070 % → 92 %. Empalmes forzados 27 (peor 19.68 m)
→ 1 (0.09 m). Divisoria: +2.29 m sobre el lecho, igual que el original.

---

## Sesiones anteriores (resumen)

| Versión | Hito |
|---|---|
| **1.0.14** | Guía bilingüe reescrita (97 ajustes, 23 bloques). **B-007**: faltaba una cresta divisoria entera (la V de la confluencia). Detección de hoyos cerrados y picos aislados. Panel de IA que abre al instante. Mucha más información para el modelo (trazados, tablas por línea, georreferencia quemada en las imágenes) |
| **1.0.13** | Primera comparación geométrica sistemática con el original. Perfiles de crestas y vaguadas editables por la IA. Concavidad del perfil como variable. Búsqueda web conectada. Realimentación de pendientes efectivas |
| **1.0.12** | Pestaña **AI Optimization**: modelo local (Ollama / LM Studio), objetivos combinables, carpeta de trabajo por sesión (ADR-004) |
| **1.0.11** | 🔴 **B-006**: atributos desplazados en GeoPackage (`compat.attrs`). Cresta divisoria anclada en la confluencia. Curvas de nivel 3D. *Check Ridgeline Slope* como tabla enlazada |
| **1.0.10** | Comparación con el DXF original. **B-005** meandros restaurados, **B-004** vaguadas sin sobreexcavar, **B-003** divisorias como cadenas continuas. Ventana de triangulación y curvado. Recorte al perímetro. Mass Haul gráfico |
| **1.0.1 – 1.0.9** | Esqueleto, panel, ajustes, gestor de capas, proyecto JSON, Setup, hidrología, motor de canales, crestas/subcrestas/vaguadas, TIN, curvas, corte/relleno |

---

## Plantilla

```markdown
## AAAA-MM-DD · vX.Y.Z — título corto

**Qué se hizo.**
- …

**Bugs corregidos**: B-0xx (añádelos a 04_bugs_resueltos.md)
**Decisiones**: ADR-0xx (añádelas a 03_decisiones.md)

**Medidas.** (antes → después, y el valor del original si aplica)

**Intentos fallidos.** (qué se probó, por qué no funcionó — esto vale oro)

**Pendiente / nuevo en el backlog**: P-xx
```
