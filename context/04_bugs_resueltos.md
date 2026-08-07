# Catálogo de bugs resueltos

> **Léelo antes de "arreglar" cualquier cosa de geometría.** Cada entrada tiene
> el síntoma, la **causa raíz** y la medida que demostró la corrección. Lo más
> reciente arriba.

---

## B-021 · Los tests que necesitan QGIS llevaban meses sin ejecutarse 🔴

**Síntoma.** Ninguno, y ese es exactamente el problema. `pytest -q` daba
**84/84 en verde** mientras `test_integracion.py` y `test_gui.py` estaban rotos
en cinco sitios distintos. Se descubrió al ir a verificar ADR-016 con QGIS
delante, que es la primera vez que se ejecutan de verdad en esta máquina.

**Causa raíz.** `tests/conftest.py` los **salta solos** si no encuentra
`qgis.core`, con un mensaje claro… que nadie lee cuando el resumen dice «84
passed». En CI tampoco corren (no hay QGIS). Resultado: un test que se salta en
silencio es indistinguible de un test que pasa, y el motor fue evolucionando
por debajo sin que nada avisara. Lo que había derivado:

| Sitio | El test pedía | El motor hace |
|---|---|---|
| `crestas` | `n = generar_crestas(...)`, `n >= 3` | devuelve `(n, crestas_3d)` |
| `subcrestas` | `ns, nv = generar_subcrestas(...)` | devuelve `(ns, nv, avisos)` |
| `curvas` | campo `f["maestra"]` | el campo es `is_index` (ADR-015, campos en inglés) |
| `centr` | `"Plan de movimiento" in txt` | el informe está en inglés (ADR-015) |
| `informes` | `"estación" in t1` | ídem |
| `test_gui` | `dock.tabs.count() == 4` | son 5 desde la pestaña *AI Optimization* |
| `test_gui` | `dock.btn_generar` | ya no existe: son `btn_prev` y `btn_draw` |

Ninguna era un fallo del motor: **el motor estaba bien y el test, desfasado**.
Pero mientras estuvieran rotos no podían detectar nada, que es lo grave: el
renombrado de ADR-016 es búsqueda de capas *por nombre*, justo lo que estos dos
tests son los únicos en cubrir.

**Corrección.** Ajustados los siete puntos al comportamiento real, aprovechando
para que las llamadas sean **las mismas que hace el panel** (`generar_subcrestas`
ahora recibe `dem` y `crestas`, como en `dock._preview`) en vez de una versión
simplificada que no probaba el camino real.

**Medido.** Con QGIS 4.2.0 sobre el DEM sintético: **15/15 pasos** de
integración y **7/7** de GUI. 73 subcrestas y 73 vaguadas, 1796 curvas (370
maestras), corte 759,288 m³ / relleno 881,815 m³ (C/R 86.1 %), 19 regiones de
acarreo y 17 movimientos. Regeneración tras editar geometría y auto-perfil, OK.

**Cómo ejecutarlos en Windows.** Los dos están escritos para la CI de Linux:
fijan el prefijo a `/usr` y buscan `processing` en
`/usr/share/qgis/python/plugins`. Para correrlos aquí hay que neutralizar
`QgsApplication.setPrefixPath` y añadir
`%QGIS_PREFIX_PATH%\python\plugins` a `sys.path`, luego lanzarlos con
`"C:\Program Files\QGIS 4.2.0\bin\python-qgis.bat"`. Ver P-16 en
`context/08_pendiente.md`: esto debería estar en `scripts/`, no reinventarse
cada vez.

---

## B-020 · El complemento NO cargaba en QGIS 3.22–3.28 (Python 3.9) 🔴

**Síntoma.** Ninguno *en el PC de desarrollo*, que tiene QGIS 4.2 con Python
3.12. En QGIS 3.22, 3.26 o 3.28 —que llevan **Python 3.9**— el complemento
falla al importarse, entero:

```
TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'
```

Y `metadata.txt` declara `qgisMinimumVersion=3.22`. Es decir: se prometía un
rango de compatibilidad en el que el complemento no arrancaba.

**Causa raíz.** `core/params.py` anota diez campos de las dataclass con
`float | None`, `tuple | None`, `int | None`. Esa sintaxis de unión es
**PEP 604 y no existe hasta Python 3.10**. En 3.9 la anotación se *evalúa* al
definir la clase y revienta ahí mismo. No es un fallo de tipado: es un error de
ejecución en tiempo de importación.

**Cómo apareció.** Lo cazó la **CI de GitHub** en el primer push, en la matriz
de Python 3.9. Nunca lo habría encontrado una prueba manual: el entorno de
desarrollo no tiene ningún Python 3.9 y QGIS 4.2 traga la sintaxis sin
pestañear. Es el argumento entero a favor de tener CI con matriz de versiones.

**Corrección.** `from __future__ import annotations` en la cabecera de
`params.py`: las anotaciones pasan a ser cadenas y no se evalúan. Las dataclass
funcionan igual porque no llaman a `get_type_hints()`.

**Para que no vuelva.** Se activa la familia **`FA`** de `ruff` en
`pyproject.toml`. Con `target-version = "py39"` ya configurado, **FA102** marca
cualquier PEP 604 que no lleve el `from __future__`. Comprobado quitando la
línea: salta. Antes no se cazaba porque `FA` no estaba en `select`, aunque el
`target-version` fuera correcto.

**Lección.** Declarar un rango de compatibilidad en `metadata.txt` no lo
verifica nadie. Si dices 3.22, algo tiene que **ejecutar** el código en el
Python de 3.22. Y ojo con el patrón general: *el entorno de desarrollo es el
más moderno del parque, así que es el que menos bugs de compatibilidad
encuentra*.

---

## B-019 · `NameError` silencioso en la rampa de color de GRD_CutFill

**Síntoma.** Ninguno visible… y ese es el problema. La capa `GRD_CutFill (m)` se
quedaba **sin simbolizar**, así que la imagen de corte/relleno que se le pasaba
al modelo de IA en cada iteración salía en escala de grises, sin la rampa
divergente ni la leyenda de rangos. El modelo estaba "viendo" mucho menos de lo
que creíamos.

**Causa raíz.** En `ai_context._simbolizar_cutfill()` se llamaba a
`_c(r, g, b)` — una función que **no existe en ninguna parte del proyecto**.
Debía ser `QColor`, que ya está importado en la cabecera del módulo. Como todo
el bloque va dentro de un `try/except Exception: return None`, el `NameError`
se tragaba en silencio y no llegaba ni al registro.

**Corrección.** `QColor(r, g, b)`.

**Cómo apareció.** Lo cazó `ruff` con la regla **F821** (*undefined-name*) al
montar el repositorio. Es el argumento a favor de tener el linter: un bug que
llevaba versiones ahí, invisible, y que ninguna prueba manual iba a encontrar
porque el síntoma era «la imagen se ve un poco sosa».

**Lección.** Un `except Exception` mudo esconde bugs indefinidamente. Cuando
escribas uno, que al menos deje rastro en el registro.

---

## B-018 · El pie de la ladera se identificaba por COTA (v1.0.17) 🔴 el peor

**Síntoma.** En la zona donde el cauce discurre **por encima** del perímetro
(margen oeste-sur), las líneas de cresta salían como una **meseta plana** seguida
de una **zanja** que bajaba hasta 1047.85 m. El original dibuja ahí una ladera
suave hacia el borde.

**Causa raíz.** En dos sitios el código tomaba como *pie de ladera* el extremo
de cota más baja de la línea. Pero **el pie no es el punto bajo**: donde el
cauce va en relleno, la ladera desciende *desde* el cauce, así que el pie es el
punto **MÁS ALTO**. El código cogía el extremo equivocado y anclaba el extremo
que muere en el límite a la cota de la orilla, 105 m más allá.

**Corrección.** Identificar el pie por **distancia al corredor del cauce**:

```python
# divides.ajustar_divisorias, paso 1 (recorte)
_k0, _d0, _s0 = corr._cerca(pz[0][0],  pz[0][1])
_k1, _d1, _s1 = corr._cerca(pz[-1][0], pz[-1][1])
en_inicio = _d0 <= _d1
pie = pz[0] if en_inicio else pz[-1]

# divides._empalmar_con_el_limite
_k0, d0, _s0 = corr._cerca(pts[0][0],  pts[0][1])
_k1, d1, _s1 = corr._cerca(pts[-1][0], pts[-1][1])
k = len(pts) - 1 if d0 <= d1 else 0
```

**Medida.**

| idx | antes | después | original |
|---|---|---|---|
| 3 | 1079.16→1062.00, 14.7 % | 1079.72→1062.00, **15.3 %** | 1079.08→1062.00, 12.4 % |
| 7 | 1072.49→1062.00, 12.0 % | 1073.42→1062.00, **13.3 %** | 1072.47→1062.00, 14.2 % |

**Lección → regla de oro nº 3 de `AGENTS.md`.** Nunca identifiques geometría por
la cota.

**Intento fallido por el camino.** Se probó quitar la cláusula de monotonía
(`monotona=False`) pensando que era la culpable. Producía zanjas en otros casos.
Revertido: la monotonía se queda; el problema era la identificación del pie.

---

## B-017 · Curvado aplicado DESPUÉS del recorte (v1.0.17)

**Síntoma.** Los cauces que acaban antes de la parte alta hacían formas raras.
Palabras del usuario:
> *"antes hacías la geometría y recortabas, quedando bien, sin embargo ahora
> aplicas otra vez un curvado tras recorte, esto lo tienes que solucionar, ya
> que el resultado de antes era mejor"*

**Causa raíz.** Se había introducido `_rehacer_laderas()` para "mejorar" el
perfil de las laderas después del recorte contra el corredor. Volver a aplicar
la ecuación de perfil sobre una línea ya recortada le impone cotas que no
corresponden a su nueva longitud → colas verticales y mesetas.

**Corrección.** `_rehacer_laderas()` se **mantiene en el código pero NO se
llama**, con un aviso destacado en el docstring. Orden correcto e inamovible:
**primero curvar, después recortar. Y nunca volver a curvar.**

**Lección → regla de oro nº 4.**

---

## B-016 · Ecuaciones equivocadas en la DOCUMENTACIÓN (v1.0.17)

**Síntoma.** Ninguno visible: el diseño salía bien.

**Causa raíz.** La cabecera de `hydrology.py` y el documento
`Especificacion_motor_hidraulico_GeoFluvQ_v1.1.md` describían leyes potenciales
(`λ = 10.9·W^1.01`, `Rc = 2.4·W^1.04`) y ponían el rango 2.5–3.2 sobre el
**cinturón** en vez de sobre `Rc`. **El código nunca hizo eso.**

**Por qué importa.** Un agente que lea la documentación y "corrija" el código
para que coincida rompería el motor. Documentación errónea es peor que sin
documentación.

**Corrección.** Cabecera y especificación corregidas + `tests/test_libro.py`
(17 tests), donde **el docstring de cada test es la cita del libro** que se
verifica. Si alguien vuelve a cambiar una constante, el test lo dice y además
dice de dónde sale el valor bueno.

---

## B-015 · Curvas de nivel cruzando las líneas del cauce (v1.0.17)

**Síntoma.** Las curvas de nivel intersectaban las líneas del cauce ⇒ dos cotas
para el mismo punto.

**Corrección.** `surface.mascara_corredor(ruta, disenos, margen=1.5)` protege el
corredor del cauce del filtro de suavizado, y `suavizar_raster(...,
mascara_fija=...)` lo respeta. Resolución de celda ligada a la anchura
**mediana** del bankfull (`_celda_para_el_cauce`, `CELDAS_POR_CAUCE = 3.0`), no
a la mínima, que disparaba el número de celdas.

**Medida.** Δz mediana en los cruces curva/cauce: **0.021 m** (el original,
0.001 m). Antes había cruces francos.

---

## B-014 · El suavizado corría DESPUÉS del limitador de pendiente (v1.0.16)

**Síntoma.** Un segmento al 220 % junto a un punto de anclaje.

**Causa raíz.** Suavizar después de limitar vuelve a empinar lo que el limitador
acababa de corregir, y ya no hay quien lo arregle.

**Corrección.** Orden fijo en `perfil_desde_control()`:
`_restaurar_control → _monotonizar → _suavizar_entre_control → _limitar_pendiente`
(**el limitador, el ÚLTIMO**).

**Medida.** Peor gradiente vértice a vértice: 2070 % → **92 %**.

**Lección → regla de oro nº 6.**

---

## B-013 · `_indices_fijos` fijaba siempre los extremos (v1.0.16)

**Causa raíz.** Si los dos extremos están clavados, el limitador de pendiente no
tiene grados de libertad y no converge nunca.

**Corrección.** Fijar **solo las estaciones de espolón**, no los extremos.

---

## B-012 · `pendiente_max_pct` aplicada al perfil de la DIVISORIA (v1.0.16)

**Síntoma.** La divisoria quedaba **17 m colgada** sobre el cauce.

**Causa raíz.** Se le aplicaba la pendiente máxima de *ladera*. Pero una
divisoria no es una ladera: en el original **desciende al 41 % de media y al
73 % de máximo**.

**Corrección.** Sustituido por `MAX_PENDIENTE_FILO = 1.00` (100 %), que actúa
**solo como cortapicos**, no como objetivo.

**Medida.** Extremo bajo de la divisoria sobre el lecho: **+2.29 m**, idéntico al
original (+2.29 m). Distancia al eje: 6.62 m (original 7.12 m).

---

## B-011 · `limite_de_ladera` = 2 × media: heurística sin justificación (v1.0.16)

**Síntoma.** El usuario dudó del cambio:
> *"Esta última modificación que has hecho no sé si es correcta, es posible que
> no, revísalo bien con la documentación y el libro guía."*

Tenía razón. **El libro prescribe reconstruir el perfil con la ecuación**, no
recortar con un múltiplo de la media.

**Corrección.** Retirada la heurística; se reconstruye con `perfil_trapezoidal`.

**Lección → regla de oro nº 1.** Ninguna constante sin cita.

---

## B-010 · Recorte "de fuera hacia dentro" (v1.0.16)

**Síntoma.** Una de las dos crestas de un par quedaba recortada y la otra no.
Palabras del usuario, que son la regla de la casa:
> *"Las implementaciones de código que hagamos para solucionar los problemas
> deben de funcionar en todos los escenarios, no solo en el ejemplo que estamos
> usando para depurar el código."*

**Causa raíz.** El recorte avanzaba desde los extremos hacia dentro, así que se
saltaba las **incursiones a mitad de línea**: si la línea entra en el corredor,
sale y vuelve a entrar, solo veía la primera.

**Corrección.** `recortar_contra_corredor()` hace una **diferencia geométrica**
real y devuelve **todos** los trozos que quedan fuera del corredor.

---

## B-009 · `sellar_contra_divisorias` movía solo el último vértice (v1.0.16)

**Síntoma.** Un escalón de **26 m en 4 m** de longitud.

**Corrección.** `topology._sellar_extremo(pts, z_nuevo, mezcla=25.0)`: reparte la
corrección con *smoothstep* e impone monotonía.

**Lección → regla de oro nº 5.** Las correcciones de extremo **se mezclan**.

---

## B-008 · Los botones de idioma de la guía se ocultaban a sí mismos (v1.0.16)

**Síntoma.** La guía salía en inglés y el botón de español no hacía nada.

**Causa raíz.** Los botones del conmutador usaban el mismo atributo `data-l` que
los bloques de contenido, así que la regla CSS
`html[data-idioma="es"] [data-l="en"]{display:none}` ocultaba **el propio botón**
del idioma inactivo.

**Corrección.** Los botones usan un atributo **distinto**, `data-idioma`.
Además: `localStorage` con clave `gfq_lang_v2`, dentro de `try` (falla en
`file://` en algunos navegadores), `arranque()` con respaldo por `readyState`
(si el documento ya está cargado, `DOMContentLoaded` no vuelve a dispararse), y
`data-idioma="es"` escrito ya en el `<html>` para que sin JavaScript la guía se
vea igual. El botón *Help* pasa `#lang=xx` según el idioma de QGIS.

---

## B-007 · Faltaba una cresta divisoria entera (v1.0.14) 🔴

**Síntoma.** Cotas incoherentes y un cono de triangulación alrededor de la unión
de dos cauces.

**Causa raíz.** La frontera Voronoi entre dos cuencas contiguas **no es una línea
que muere en la confluencia: es una V que PASA por ella.** Aguas arriba del punto
de unión hay divisoria por los dos lados del tributario. El código buscaba el
vértice más próximo a la confluencia y se quedaba con **una sola** de las mitades.

**Medida.** La cadena compartida tenía 305.8 m entre los dos extremos de la V —
exactamente los extremos de las **DOS** crestas que dibuja el original
(178.3 m y 96.9 m).

**Corrección.** `ridges._partir_en_confluencias()` parte la cadena en la
confluencia y genera las dos, cada una anclada ahí en X, Y y Z.

---

## B-006 · Atributos desplazados una columna en GeoPackage (v1.0.11) 🔴

**Síntoma.** Al elegir *"Save layers to a folder"*, las capas salían **vacías**
(`GRD_Channels`, `GRD_XSections`, `GRD_Contours`, `GRD_HaulRegions`,
`GRD_HaulRoutes` con 0 entidades). De ahí venían también *"no veo las curvas"*,
*"Mass Haul da problemas"* y *"Highlight Tractive Force Zones no muestra nada"*.

**Causa raíz.** GPKG añade siempre un campo `fid` de clave primaria **al
principio**. Como los atributos se rellenaban **por posición**, todos los valores
se desplazaban una columna.

**Corrección.** `compat.attrs()` alinea los valores con los campos reales.

**Lección → regla de oro nº 8.**

---

## B-005 · Todo el canal salía en zigzag (v1.0.10)

**Síntoma.** Semilongitud de onda constante de 24.5 m en toda la traza y
sinuosidad 1.12 (el original, 1.20).

**Causa raíz.** Marcar la transición con *Pick* cerca de la boca convertía
**todo** el canal en tipo A.

**Corrección.** Un tramo va en zigzag solo si está aguas arriba de la transición
**y** su pendiente supera realmente el 4 %. Amplitud exacta de la onda
triangular `A = (λ/4)·√(k²−1)` y densificado del eje cada 1 m.

---

## B-004 · Vaguadas sobreexcavadas (v1.0.10)

**Causa raíz.** La cabecera de la vaguada se rebajaba un **15 % arbitrario** del
desnivel.

**Corrección.** Se retranquea la distancia *Maximum distance from ridgeline to
swale head* y toma la cota **de la ladera** en ese punto. Si nace donde se
encuentran dos subcrestas ya trazadas, hereda la cota de ese encuentro.
Retranqueo acotado al 40 % de la ladera (un valor absurdo —400 m en una ladera
de 120 m— dejaba el canal sin vaguadas).

---

## B-003 · Divisorias partidas en esquirlas de Voronoi (v1.0.10)

**Síntoma.** 48 trozos de ~7 m en vez de una cresta.

**Corrección.** Unión en cadenas continuas, suavizado en planta y perfil
longitudinal de cresta cuya cota nunca baja de la cota de cresta de diseño.
Solo el extremo que muere en el límite empalma con el DEM; el interior ya no
copia la topografía original.

---

## B-002 · Colas verticales en subcrestas (v1.0.16)

**Síntoma.** Las subcrestas fid 180, 182 y 218 conservaban colas verticales tras
el recorte.

**Corrección.** Recorte de cola en `hillslopes._recortar_cola` + mezcla del
extremo. Ver también B-017: el intento de arreglarlo recurvando fue peor.

---

## B-001 · Orden de recarga de módulos en QGIS (entorno, no del producto)

**Síntoma.** `AttributeError` al leer un ajuste nuevo de `GlobalSettings` tras
recargar el complemento desde el MCP.

**Causa raíz.** El script de recarga ordenaba los módulos **por longitud de
nombre**, así que `project.py` se recargaba antes que `params.py` y
`GlobalSettings` se quedaba viejo.

**Corrección/paliativo.** Recargar `params` primero, o reiniciar QGIS.
Ver `context/07_entorno_qgis_mcp.md`.

---

## Patrones que se repiten (léelos aunque no leas lo demás)

1. **Identificar geometría por cota** → B-018. Usa distancias y topología.
2. **Parchear el último vértice** → B-009, B-002. Mezcla la corrección.
3. **Corregir después en vez de generar bien** → B-017. Primero curvar, luego recortar.
4. **Orden de las etapas del pipeline** → B-014, B-017. El orden ES el algoritmo.
5. **Heurísticas sin cita** → B-011. El libro manda.
6. **Documentación que contradice al código** → B-016. Es más peligrosa que la falta de documentación.
7. **Recorrer desde los extremos** → B-010. Usa operaciones geométricas de conjunto.
8. **Rellenar por posición** → B-006. Siempre por nombre de campo.
