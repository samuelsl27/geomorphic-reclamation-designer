# Backlog — lo que falta y lo que está a medias

Estado a **v1.0.21**. Actualiza esta página en cada sesión: mueve lo hecho a
`09_historial_sesiones.md` y añade lo nuevo.

> **Numeración**: el proyecto sigue en **1.0.x** mientras no haya nada
> definitivo. Aunque una versión cambie rótulos visibles, se numera como parche.
> El salto a 1.1 se reserva para cuando la geometría se dé por estable y el
> complemento deje de ser `experimental`.

---

## 🔴 Abierto — geometría

### P-25 · La cota de la divisoria es una ENVOLVENTE; en el original es un DISEÑO 🔴 (nuevo, 2026-08-11)

**Es el hallazgo de fondo de la v1.0.21, y lo apuntó Samuel mirando los perfiles
en 3D antes de que ninguna medida lo dijera.**

La traza en planta está bien. Comparadas las dos parejas que señaló, nuestra
divisoria y la del original van casi por el mismo sitio:

| | fid 13 vs 1829 | fid 15 vs 1788 |
|---|---|---|
| Separación en planta, p50 | **3.1 m** | **1.6 m** |
| Pendiente media | 15.3 vs 14.1 % | 17.9 vs 15.5 % |
| **Pendiente máxima** | **93.9 vs 19.5 %** | **74.4 vs 33.0 %** |
| **Vaivén** | **12.49 vs 0.00 m** | **11.67 vs 0.00 m** |

Las dos divisorias largas del original tienen vaivén **0.00 exacto**: son
estrictamente monótonas. Las nuestras no. Sumando las 13 nuestras: **113 m de
vaivén** frente a **15 m** de las 7 del original.

**De dónde sale**, medido reproduciendo el motor fuera de QGIS
(`scratchpad/banco.py` reconstruye el pipeline sin QGIS):

| | m de vaivén |
|---|---|
| Lo piden los propios puntos de control (cabeceras de subcresta) | **41** |
| Lo fabrica `base + residuo` y el anclaje de los extremos | **54** |
| Total escrito | **95** |
| Original | **15** |

Y la causa es de arquitectura, no un bug puntual. `core/divides.py` lo dice en
su propia cabecera como decisión deliberada:

> *«La cota de una divisoria no es un dato: es una consecuencia… la cota de la
> divisoria como ENVOLVENTE de lo que las laderas le piden.»*

Cada subcresta calcula su cota de coronación por su cuenta
(`z_cauce + desnivel_de_ladera(D)`, con su propio `D`), y la divisoria hereda
**toda su dispersión**. El original va al revés — manual de Carlson, p. interna
1706:

> *«GeoFluv designs ridgelines between the channels **at elevations that create
> side slopes less than a default 5:1 gradient** for the draft landform.»*

O sea: primero una cota de divisoria **suave**, y las laderas se dibujan hasta
ella. Nosotros promediamos ruido; ellos diseñan una curva.

**Lo que ya está medido de los candidatos**, sobre las 13 divisorias reales:

| | vaivén | pend. máx | meseta |
|---|---|---|---|
| Como está | 93.2 m | 95.2 % | 5 |
| Soltar el anclaje si hay cabecera a < 6.1 m | 93.2 m | 95.2 % | 5 |
| Manda la cabecera sobre el anclaje | 87.9 m | 95.2 % | 5 |
| Manda el anclaje sobre la cabecera | 88.9 m | 95.2 % | 5 |
| **Hacer monótona la secuencia de controles (PAVA)** | **42.8 m** | 100.0 % | 10 |
| Original | **15.0 m** | **33.0 %** | **2** |

Reconciliar los extremos **no sirve** (93 → 88). Hacer monótonos los controles
antes de interpolar **es la mitad del camino** (93 → 43) y deja limpias fid 13,
14, 15 y 3, pero empuja una línea al 100 % y una meseta a 10 vértices: no se
puede meter tal cual.

**Dirección respaldada por el libro**, p. 260 (§9.11.2), contra un filo
demasiado empinado:

> *«Increasing the "blend percent" will reduce that over-steepened portion.»*

Es decir: **ajustar y suavizar, no interpolar exacto ni recortar**. Encaja con
que el original tolera hasta 5.43 m entre sus cabeceras de ladera y su
divisoria, mientras nosotros las clavamos a 0.89 m (p90).

**Antes de tocar nada** hay que decidir el modelo, porque es un cambio de fondo
y afecta a `perfil_desde_control`, a `_restaurar_control` y a cómo las laderas
toman su cota de coronación.

### P-26 · Nuestras divisorias se quedan ~100 m cortas por abajo 🟠 (nuevo, 2026-08-11)

Las dos parejas comparadas: 346 m frente a 454, y 290 frente a 397. Y acaban más
altas: z=292 frente a 281, z=288 frente a 279. Con la boca del cauce a 275, el
original baja mucho más cerca de la confluencia.

Sospechosos: `holgura_divisoria_m` (4.5 m), `recortar_contra_corredor` y
`min_divisoria`. No confundir con P-22 (que va de cuántas divisorias hay, no de
cuánto miden).

### P-24 · `monotona = (n_sillas == 0)` es un error de categoría latente 🟢 (nuevo, 2026-08-11)

Una sola silla apaga la monotonía de la divisoria **entera** — 346 m de perfil
sueltos por un hoyo en la estación 88. Es la misma familia que B-036.

**No se ha tocado, y conviene saber por qué.** Se llegó a cambiar y se revirtió:
medido sobre el Ej_2 el efecto es de 95.37 → 94.30 m de vaivén (un 1 %) y a
cambio deja una meseta de 5 vértices donde había 1. En todo el ejemplo hay
**4 sillas**, no las 12 que una primera cuenta mal hecha sugirió (le faltaba el
filtro `base[i] − z_vaguada > 0.05` que aplica el motor). El vaivén no viene de
aquí.

La prueba `test_una_silla_cabe_sin_soltar_el_resto_del_perfil` ya fija el
comportamiento de `_monotonizar` que permitirá quitar el apagado cuando se
reescriba el perfil (P-25).

### P-23 · La divisoria se coloca en PLANTA para cumplir la pendiente 🟠 (nuevo, 2026-08-11)

El libro (p. 180, §7.4.3, citado entero en `01_metodo_geofluv.md` §9) dice que
*maximum straight-line slopes* se cumple **desplazando la divisoria en planta**:

> *«…the ridgeline must move towards the valley on the other side of the ridge
> to reduce the slope. As the ridgeline moves towards the other valley, the
> slopes on the other valley's side must become progressively steeper.»*

Nosotros la colocamos por **equidistancia** (Voronoi de los ejes) y después le
derivamos la cota. Nunca la movemos para equilibrar las dos laderas. El manual
de Carlson (p. interna 1706) lo formula por el otro lado —*«GeoFluv designs
ridgelines between the channels at elevations that create side slopes less than
a default 5:1 gradient»*—, o sea que la cota es una **variable derivada** del
objetivo de ladera, que es justo lo que hace `perfil_desde_control`.

Lo que falta es el grado de libertad en planta. No es una corrección de bug: es
una pieza del método sin implementar. Antes de meterse hay que medir cuánto se
apartan de la equidistancia las divisorias del original.

### P-21 · El Ej_1 no es comparable: le falta un canal 🔴 (nuevo, 2026-08-11)

Nuestro diseño del Ej_1 (Potoya) tiene **2 canales** y el original **3**. Se ve
descomponiendo su `GF_Channels`, que guarda cada canal por triplicado (eje y dos
orillas) más los arcos de cabecera: los tríos 558/581/592 y 617/640/651 m que
mueren en (663602, 4420391) son un canal entero que nosotros no tenemos.

| | nuestro | original |
|---|---|---|
| Canales | 2 (926 + 472 m) | 3 (935 + 651 + 474 m) |
| `GRD_Ridges` | 2 líneas, 278 m | — |

Mientras esto no se corrija, **cualquier medida del Ej_1 contra el original es
ruido**, y eso incluye la reverificación de ADR-009, que se quedó a medias por
esto. Es el mismo tipo de error de transcripción que se corrigió en el Ej_2
(R1↔R4 y R2↔R3 cambiados, B-022): mirar los datos de entrada **antes** de medir
la salida.

### P-22 · ¿Sobran divisorias cortas? 🟠 (nuevo, 2026-08-11)

Con el clasificador ya calibrado (ADR-021), en el Ej_2 tenemos **13 divisorias
y 2265 m** frente a **7 y 2103 m** del original, y generamos tres de 46, 46 y
52 m cuando la más corta del original mide 118 m.

**No se ha tocado ningún umbral**, a propósito. La justificación que había para
tocarlos —«faltan 4 divisorias»— resultó ser un artefacto del clasificador sin
calibrar, y cambiar un umbral con la evidencia en contra es exactamente lo que
ya salió mal una vez esta sesión. Además la precisión del clasificador está
medida sobre **nuestras** líneas, no sobre las del original: puede que alguna
divisoria suya se esté yendo al montón de laderas.

Antes de mover nada hay que: (a) verificar el clasificador contra el DXF por
color o por capa, si el original los distingue; (b) mirar los tres filtros a la
vez, porque se pisan — `ridges.long_min` (50 m en el Ej_2, y usa `xrh`, que es
una distancia divisoria-cabecera, como longitud mínima de divisoria) y
`divides.min_divisoria` (25 m).

### P-19 · Unificar el criterio de «extremo alto» 🔴 (nuevo, 2026-08-10)

Conviven **tres** criterios para decidir cuál es el extremo alto de una línea de
ladera, y uno de ellos incumple la regla de oro nº 3:

| Sitio | Criterio |
|---|---|
| `divides.py:759-762`, `1168-1170` | distancia al cauce ✅ |
| `divides.py:823`, `854`, `969` | **cota** ❌ |
| `checks.py` (`laderas_que_no_vierten`) | **cota** ❌ |
| `topology._extremo_hacia_divisoria` | proyección sobre la divisoria ✅ |

**No se ha tocado en la v1.0.20 a propósito.** Es un cambio estructural que
toca cuatro módulos y no tiene síntoma medido en el Ej_2; meterlo en la misma
tanda que las cinco correcciones de forma habría hecho imposible saber cuál
movió qué al remedir. Se hace **después** de que la v1.0.20 esté medida.

Lo que hay que hacer: una función pública `divides.extremo_alto(pts,
dist_al_cauce)` que reciba un invocable `(x, y) → distancia` —así cada módulo
inyecta el suyo (`Corredor._cerca`, `GRD_Channels`, `disenos`) sin crear
dependencias nuevas— y sustituir los cuatro sitios por cota. Respaldo, si no hay
cauces: la proyección, nunca la cota. Invariante nuevo para `context/05`:
*ningún módulo decide un extremo por cota*.

### P-17 · Remedir los dos ejemplos en QGIS real 🔴

Las correcciones de la v1.0.19 (B-023…B-027, ADR-018) y las de la v1.0.20
(B-028, B-032…B-035, ADR-019/020) están hechas, con 133 tests en verde y `ruff`
limpio, pero **no se han medido en QGIS**. Hasta entonces no se cierra. Lo que hay que hacer, por orden:

1. **Reiniciar QGIS** (se ha tocado `core/params.py`: recargar en caliente deja
   `GlobalSettings` viejo — trampa 3 de `context/07`).
2. Abrir `QGIS_GRD_Test_Ej_2.qgz`, cargar `GRD_Rom_Pla_File.grd.json` (ya
   corregido contra el `.geo`) y lanzar *Preview* + *Draw Design Surface*.
3. `python scripts/comparar_original.py <carpeta del Ej_2>` y comparar con la
   línea base de `context/06`.
4. Lo mismo con el Ej_1: **no puede empeorar**, es la red de seguridad.
5. *Check Design* en los dos.
6. Rehacer la tabla de `context/06` entera — ADR-018 cambia las cotas de
   coronación de las laderas al norte y al este, y con ellas el balance.
7. `python scripts/bump_version.py 1.0.19` y `python scripts/build_zip.py`.

Umbrales que deben cumplirse en el Ej_2 (el «antes» está en `context/06`):

| Métrica | Antes | Objetivo | Original |
|---|---|---|---|
| Peor pendiente de segmento | 955.4 % | < 100 % | 65.7 % |
| Líneas por encima del 100 % | 19 | 0 | 0 |
| Líneas por debajo del cauce | 1 | 0 | 0 |
| Meseta más larga | 27 vért. | ≤ 3 | 2 |
| Cabecera de main L1 | 23.67 % | 15.4 ± 1 % | 16.16 % |
| Cabecera de main R4 | 32.72 % | 17.44 ± 1 % | 18.29 % |

### P-18 · Las líneas de relieve son menos y más cortas que las del original 🔴 (nuevo)

Medido en el Ej_2 **antes** de esta ronda: 218 líneas frente a 244, longitud
total 14 352 m frente a 19 705 m (**−27 %**), una línea cada 13.0 m de cauce
frente a 11.5 m, y ángulo medio con el eje 51.3° frente a 60.5° (el ajuste
`angulo_subcresta_deg` es 20°, así que lo esperable serían 70°).

**Atacado en la v1.0.20, pendiente de medir.** La sospecha era buena y resultó
ser dos cosas distintas:

- **la longitud** venía del retranqueo de las vaguadas (B-032/ADR-019): eran
  ellas, no las subcrestas, las que se quedaban cortas (44.0 m frente a 63.4 de
  las subcrestas, con el original en 62.4 y 65.1);
- **la red que no cierra** venía de la regla anti-cruce, que rompía el bucle sin
  añadir vértice y solo miraba el propio canal (B-034).

**El ángulo, en cambio, NO era un bug.** Se extrajo
`hillslopes.direccion_de_ladera` y se fijó con una prueba que se mide desde la
perpendicular hacia aguas arriba, como dice el libro: el motor lo hacía bien. La
desviación medida (51.9° frente a 60.5°) es de **la regla de medir** —
`comparar_original.angulo()` usa la tangente del cauce sinuoso y el código usa la
del valle, y el plegado `min(a, 180−a)` sesga la media. **Antes de tocar la
constante hay que arreglar la medida**, no el motor.

Sigue en pie que P-02 y P-18 **discrepan en el signo** de la desviación entre
Ej_1 y Ej_2. Con la regla de medir corregida puede que la discrepancia
desaparezca sola.

### P-01 · Dos errores de tensión tractiva en el *Check Design*

Son los **únicos 2 errores** que quedan en el caso de prueba (invariante H1:
`τ > τ_crit`). Hay que decidir cuál de estas tres es:

1. un problema real del dimensionado (la sección se queda corta en esas
   estaciones);
2. un `D50` introducido demasiado fino para ese material;
3. un aviso legítimo: ese tramo necesita protección local (vanes, escollera) y
   el diseño es correcto.

**Cómo abordarlo**: listar las estaciones afectadas, su `S`, `R`, `τ` y `τ_crit`,
y ver si se concentran en un tramo o están repartidas. Si están todas en el mismo
tramo empinado, es (3).

### P-02 · Espaciado y ángulo de las subcrestas

Nuestro espaciado a lo largo del canal es 15.5 m (original 12.5 m) y el ángulo
74° (original 64°). Palanca conocida: subir *Angle from sub-ridge to channel's
perpendicular* de 10° a ~25°. Falta **verificar si es solo calibración** o si el
motor reparte los ápices de forma distinta al original.

### P-03 · Δz residual en los cruces curva de nivel / cauce

Mediana 0.021 m (original 0.001 m). Aceptable, pero se puede afinar
densificando las líneas de rotura del cauce antes del TIN.

---

## 🟡 Abierto — rendimiento

### P-04 · El pipeline pasó de ~3 s a ~15 s

Observado en la última sesión de la v1.0.17. **El grueso está en la generación
de geometría, que no se tocó.** Sospecha principal: había un ráster fino cargado
(ver `context/07_entorno_qgis_mcp.md`, trampa 4). **Confirmar antes de buscar
una regresión**: ejecutar el pipeline con el proyecto recién abierto y sin
rásteres pesados, y cronometrar por etapas.

### P-05 · Propagación en cadena en datos sintéticos de estrés

Con 500 divisorias a 4 m de distancia, el bucle de convergencia de `topology`
llega al tope `MAX_PASADAS = 30`. Los diseños reales convergen en **2 pasadas**,
así que no es urgente, pero el tope se está alcanzando en vez de converger.

---

## 🟢 Abierto — funcionalidad

### P-06 · Tercera simulación de IA sin ejecutar

Falta la prueba con **R1 y libertad total** (geometría + ajustes), objetivo de
**corte = 0**. Las dos anteriores están documentadas; esta cierra la validación
del optimizador.

### P-07 · Report Formatter incompleto

Falta: **importar/exportar formatos**, **Table Entity** y **Report Viewer**
(existen en el original). El resto del diálogo está.

### P-08 · Chat con el usuario e instrucciones gráficas para la IA

Idea futura: que el usuario converse con el modelo sobre el diseño y pueda
dibujar sobre el lienzo instrucciones que el optimizador interprete
("baja esta ladera", "más relleno aquí").

### P-09 · Objetivo de pendiente diferenciado para laderas N/E ✅ (hecho 2026-08-10)

Aplicado al trazado, no solo a las comprobaciones (ADR-018). La definición de
«ladera norte o este» pasa a `core/params.py` y la comparten el motor y
`checks`. De paso se corrigió el rumbo, que salía **invertido** para las
subcrestas y las vaguadas: se tomaba de `pts[0]` a `pts[-1]`, pero se trazan del
cauce hacia arriba, así que su primer vértice es el pie.

Queda por **medir el efecto** en los dos ejemplos: las crestas orientadas al
norte y al este bajan en la proporción 22/33, así que cambia el balance de
tierras y hay que rehacer la tabla de `context/06`.

---

## 🔵 Infraestructura (nuevo, esta sesión)

### P-16 · Un lanzador de los tests de QGIS para Windows 🔴

`test_integracion.py` y `test_gui.py` están escritos para la CI de Linux:
`setPrefixPath("/usr", True)` y `sys.path.insert(0,
"/usr/share/qgis/python/plugins")`. En Windows hay que neutralizar lo primero y
apuntar lo segundo a `%QGIS_PREFIX_PATH%\python\plugins`, y lanzarlos con
`python-qgis.bat`. Eso se hizo a mano con un envoltorio temporal para verificar
ADR-016 (ver B-021); **debería ser `scripts/correr_tests_qgis.py`**, con
detección del prefijo en los dos sistemas.

Mientras no exista, estos dos tests solo se ejecutan cuando alguien se acuerda,
que es justo cómo se llegó a B-021: rotos durante meses sin que nadie lo notara.

### P-15 · Verificar el renombrado en QGIS real ✅ (hecho 2026-08-08)

Hecho con QGIS 4.2.0: **15/15** pasos de integración y **7/7** de GUI, más una
comprobación específica de la ida y vuelta del proyecto `.grd.json`. De paso
salió B-021 (los dos tests llevaban meses rotos y se saltaban en silencio).

Queda **sin probar a mano en la interfaz**: abrir el diálogo *File… → Save
Project As* y *Settings → Save As* con el ratón, y mirar el árbol de capas en el
panel. El código está verificado; lo que falta es la comprobación visual.

Contexto original, por si hay que repetirlo: los tests que necesitan QGIS
(`test_integracion`, `test_gui`) se saltan solos si no lo encuentran, así que
las 84 pruebas en verde **no cubren esto**.

Lo que hay que mirar, por orden de riesgo:

1. **El prefijo de capa** pasa de `GF_` a `GRD_` en las 18 capas (ADR-016).
   Es lo más arriesgado de todo el renombrado, porque `layer_manager`,
   `checks`, `surface` y `divides` buscan capas **por nombre**: si se ha
   escapado una cadena, la capa no aparece o se crea duplicada. Comprobar que
   *Create Design Layers* + *Preview* + *Draw Design Surface* dejan el árbol
   completo, y que *Check Design* no da falsos «capa vacía».
2. **El grupo de capas** pasa de `GeoFluv <proyecto>` a `Geomorphic Reclamation
   <proyecto>` (`layer_manager.GRUPO_RAIZ`). Comprobar que el árbol se crea
   entero, que *Create Design Layers* mete las capas en su subgrupo, y qué pasa
   al abrir un proyecto anterior (debería crear el grupo nuevo y no perder nada).
3. **Guardar y abrir proyecto** con la extensión nueva `.grd.json` (ADR-016):
   que el filtro del diálogo la aplique, que `nombre_desde_ruta()` deje
   «mina_norte» y no «mina_norte.grd» en el rótulo del panel y en el grupo de
   capas, y lo mismo con *Load / Save As* de los ajustes (`.grd-settings.json`).
4. **El menú** `Geomorphic Reclamation` y sus 13 comandos: que aparezcan, que no
   haya quedado ninguno huérfano y que `unload()` los quite todos.
5. **Report Formatter**: que el desplegable arranque en `STANDARD` y que
   *Save As* / *Delete* escriban en la clave nueva de QSettings. Ojo: los
   formatos que hubiera guardados con la clave antigua **no se migran**, es la
   ruptura aceptada en ADR-016.
6. Rótulos del panel, títulos de ventana e informes.

### P-11 · Repositorio de complementos de QGIS

Publicar en plugins.qgis.org. Requiere cuenta OSGEO y subir el ZIP. Los campos
`homepage`/`tracker`/`repository` ya apuntan a GitHub y la marca ya está fuera
de la interfaz (ADR-015), que era el motivo más probable de rechazo.

Queda por decidir si se quita `experimental=True`, y en todo caso probar antes
en **3.22, 3.34, 3.40 y 4.2** — sobre todo en 3.22, que es donde B-020 impedía
cargar el complemento y donde nunca se ha ejecutado de verdad.

### P-12 · `scripts/comparar_original.py` ✅ (hecho 2026-08-10)

Escrito, junto con `scripts/lector_gpkg.py` (GeoPackage sin GDAL) y
`scripts/leer_geo.py` (lee el proyecto nativo `.geo`/`.ggs` del original y
compara ajuste a ajuste). Uso y salida, en `context/06_comparacion_original.md`.

Queda fuera una medida que sí se hacía a mano: **Δz en los cruces curva de nivel
/ cauce**. `GRD_Contours` pesa ~28 MB por ejemplo y cruzar 359 curvas contra los
ejes multiplica por veinte el tiempo del guion, que hoy tarda 0.13 s. Merece un
`--curvas` que lo active solo cuando se pida.

### P-14 · Endurecer el linter progresivamente

`ruff check .` está en verde, pero con una lista de reglas silenciadas en
`pyproject.toml` bajo el comentario *«pendientes de limpiar»*. Se silenciaron
para que la CI naciera en verde: **una CI roja el primer día enseña a todo el
mundo a ignorar la CI**.

Lo que queda por limpiar, y que hay que revisar **con QGIS delante**, no a
ciegas:

| Regla | Casos | Nota |
|---|---|---|
| `F841` variable local sin usar | `ai_optimizer.py:241` (`bb`), `divides.py:667` (`idx_datos`), `dock.py` ×3 (`res_top`, `area`) | **Revisar una a una**: puede ser un resto, o puede ser que alguien olvidara usarla |
| `B023` cierre que no captura la variable del bucle | `builder.py:632-636` | Falso positivo: los cierres se consumen en la misma iteración. Confirmar antes de tocar |
| `E731` lambda asignada | `ai_client.py:288`, `hillslopes.py:368` | Cosmético |
| `RUF013` `Optional` implícito | `hydrology.py` ×3 | Cosmético, pero mejora las anotaciones |
| `RUF012` valor mutable en atributo de clase | `dock.py:389` | Comprobar que no se comparte entre instancias |
| `C401`, `RUF015`, `RUF005`, `RUF046`, `RUF059`, `B007`, `B904` | varios | Cosmético |

Además, `ruff format` **no** se aplica ni se exige: reformatear de golpe 18 000
líneas de motor que funciona daría un diff en el que un cambio real pasaría
desapercibido. Si algún día se hace, fichero a fichero y en commits propios.

**Ya corregido por el linter** (v1.0.17+): `F821` en `ai_context.py` — se llamaba
a un `_c(r, g, b)` inexistente al construir la rampa de color de `GRD_CutFill`.
Como el bloque va dentro de un `try/except` que devuelve `None`, el `NameError`
se tragaba en silencio y **la imagen que recibía el modelo de IA salía sin
simbolizar**. Ver B-019.

**Familia `FA` activada** (v1.0.18): `FA102` marca cualquier unión PEP 604
(`float | None`) sin `from __future__ import annotations`. Es lo que habría
evitado B-020, que dejaba el complemento sin cargar en todo QGIS 3.22–3.28. No
saltaba antes porque `FA` no estaba en `select`, aunque `target-version` sí
fuera `py39`. Moraleja para el resto de esta tabla: **poner el target correcto
no basta si no seleccionas las reglas que lo comprueban.**

### P-13 · Cobertura de tests

84 tests, todos en verde. Sin medir cobertura. Faltan tests de
`surface.py` y `builder.py`, que son los módulos grandes con menos red de
seguridad (necesitan QGIS, así que solo correrían en local).

---

## Terminado recientemente (v1.0.18)

- ✅ **P-10 · Publicado en GitHub**: `github.com/samuelsl27/geomorphic-reclamation-designer`,
  público, con Actions en verde en toda la matriz
- ✅ La marca ajena fuera de toda la interfaz (ADR-015)
- ✅ **B-020**: el complemento no cargaba en QGIS 3.22–3.28 (Python 3.9)
- ✅ Familia `FA` de `ruff` activada, para que B-020 no pueda repetirse
- ✅ `SECURITY.md` y `docs/ARQUITECTURA.md` ajustados a lo que hace el código
- ✅ Datos del caso de trabajo y rutas de la máquina fuera del repositorio, y
  purgados también de la historia de git

## Terminado recientemente (v1.0.16 – v1.0.17)

- ✅ 22 comprobaciones C02–C52 (*Check Design / Error Log*) con ventana filtrable
  y exportación a CSV
- ✅ Conmutador de idioma de la guía (bug B-008)
- ✅ Recorte de crestas contra el corredor por diferencia geométrica (B-010)
- ✅ Sillas de cresta (libro §9.11.2, p. 259 — el porcentaje es decisión nuestra)
- ✅ Recetario del capítulo 10 en el prompt de optimización de IA
- ✅ Marcador rojo en planta al deslizar sobre *View Longitudinal Profile*
- ✅ Máscara del corredor para que las curvas no crucen el cauce (B-015)
- ✅ Revisión del motor hidráulico contra los capítulos 2 y 4 + `test_libro.py`
- ✅ Identificación del pie de ladera por distancia, no por cota (B-018)
- ✅ Retirado el recurvado tras el recorte (B-017)
- ✅ `MAX_ORDEN = 10`, `MAX_PASADAS = 30`
