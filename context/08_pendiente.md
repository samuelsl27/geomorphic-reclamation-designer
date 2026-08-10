# Backlog — lo que falta y lo que está a medias

Estado a **v1.0.18**. Actualiza esta página en cada sesión: mueve lo hecho a
`09_historial_sesiones.md` y añade lo nuevo.

> **Numeración**: el proyecto sigue en **1.0.x** mientras no haya nada
> definitivo. Aunque una versión cambie rótulos visibles, se numera como parche.
> El salto a 1.1 se reserva para cuando la geometría se dé por estable y el
> complemento deje de ser `experimental`.

---

## 🔴 Abierto — geometría

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

### P-09 · Objetivo de pendiente diferenciado para laderas N/E

Ahora todas las laderas usan la pendiente máxima global. El método admite
objetivos distintos según orientación (las laderas norte y este suelen
tolerar menos pendiente por humedad y vegetación). `checks._es_NE` ya sabe
identificarlas.

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
- ✅ Sillas de cresta (libro §9.4)
- ✅ Recetario del capítulo 10 en el prompt de optimización de IA
- ✅ Marcador rojo en planta al deslizar sobre *View Longitudinal Profile*
- ✅ Máscara del corredor para que las curvas no crucen el cauce (B-015)
- ✅ Revisión del motor hidráulico contra los capítulos 2 y 4 + `test_libro.py`
- ✅ Identificación del pie de ladera por distancia, no por cota (B-018)
- ✅ Retirado el recurvado tras el recorte (B-017)
- ✅ `MAX_ORDEN = 10`, `MAX_PASADAS = 30`
