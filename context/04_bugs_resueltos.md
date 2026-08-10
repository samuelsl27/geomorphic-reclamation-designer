# Catálogo de bugs resueltos

> **Léelo antes de "arreglar" cualquier cosa de geometría.** Cada entrada tiene
> el síntoma, la **causa raíz** y la medida que demostró la corrección. Lo más
> reciente arriba.

---

> **Los cinco siguientes (B-022 … B-027) salen del SEGUNDO ejemplo de
> referencia** (Rom_Pla, 6 canales, 35.6 ha). El primero (Potoya, 2 canales) no
> los destapaba: hacen falta confluencias múltiples, tributarios cortos y
> empinados, y un tramo con el cauce por encima del perímetro. Lección
> transversal: **un solo caso de prueba valida un solo escenario**, por bien
> que salga.

## B-022 · Los parámetros de los tributarios estaban tecleados en orden invertido

**No es un bug del código**, pero se documenta porque costó media sesión y
volverá a pasar.

**Síntoma.** El Ej_2 salía con geometrías que no se parecían al original y no
había forma de saber cuánto era motor y cuánto dato.

**Causa raíz.** En `GRD_Rom_Pla_File.grd.json` los parámetros de R1↔R4 y R2↔R3
estaban cruzados: `main R4` llevaba la pendiente de cabecera (−12 %) y la
velocidad (1.40 m/s) de `main R1`, y así los cuatro. La **correspondencia de
canales sí era correcta** —las cotas de cabecera coinciden con menos de 0.1 m
(main 338.64/338.65, R2 323.46/323.46, R1 303.06/303.06, L1 320.00/320.00)—,
solo estaban mal los valores.

**Cómo se encontró.** Aparecieron los ficheros NATIVOS del programa original en
`Ej_2_Rom_Pla/GeoFluv_origen/`: `Ej_2_GeoFluv_File.geo` (proyecto completo, con
un bloque `BEGIN CHANNEL` por canal) y `GeoFluv_Ej2_Settings.ggs` (ajustes
globales). Estaban ahí desde el principio, sin usar.

**Corrección.** `scripts/leer_geo.py`, que los lee y compara o fusiona ajuste a
ajuste. Los ajustes globales del `.ggs` coincidían en las 22 claves; el `.geo`
destapó **15 diferencias de canal**, todas corregidas.

**Lección.** Cuando un ejemplo de referencia traiga el proyecto nativo del
programa original, **léelo antes de medir geometría**. Comparar geometrías sin
haber comparado los datos de entrada es medir dos cosas a la vez.

---

## B-027 · El extremo que muere en la divisoria se SUPONÍA, no se medía 🔴

**Síntoma.** Líneas de ladera invertidas y sellados que subían el pie en vez de
la cabecera.

**Causa raíz.** `topology._lejos_del_cauce(pts)` era literalmente
`return pts[-1]`, con el comentario «arranca siempre en el cauce». Deja de ser
cierto en cuanto `divides` **parte** una línea contra el corredor o la
**invierte**, y no lo es **nunca** para las líneas de encuentro
(`channel = "junction"`), que van de alto a bajo. Cuando falla,
`sellar_contra_divisorias` sube el **pie** a la cota de la divisoria y después
fuerza monotonía ascendente: la línea entera queda del revés.

**Corrección.** `topology._extremo_hacia_divisoria(pts, idx, divisorias)`, que
lo **mide**: de los dos extremos, el que se proyecta más cerca de la red de
divisorias. Se usa en los tres sitios que tenían la suposición. Tampoco por
cota (regla de oro nº 3): por construcción las divisorias están lejos del cauce
—las recorta `Corredor`— así que el pie no puede ganar esa comparación.

**Lección.** Un comentario que dice «siempre» sobre una invariante que otro
módulo puede romper es una suposición disfrazada de documentación.

---

## B-026 · Mesetas al bajar un extremo de línea 🔴

**Síntoma.** Líneas de ladera con un tramo completamente plano seguido de una
rampa. Medido en el Ej_2: la subcresta fid 65 (main R3 idx 15) subía
284.8 → 303.2 m en siete vértices y después se quedaba **48 m completamente
planos** a 303.2. **10 de las 218** líneas de relieve tenían esa firma, con
mesetas de hasta **27 vértices**; el original no pasa de **2**.

**Causa raíz.** `divides.ajustar_extremo` repartía la corrección sobre una
longitud FIJA (`mezcla`). Los vértices que quedaban fuera conservaban su cota
vieja y, cuando esa cota contradecía el nuevo extremo, el recorte de monotonía
—que es correcto y hay que conservarlo, ver B-018— los arrastraba a todos a la
misma cota. La meseta no la produce la monotonía: la produce **mezclar poco**.

**Corrección.** La mezcla se alarga. La corrección vale `dz·w(d)` con `w` el
smoothstep `3u²−2u³`, cuya pendiente máxima es `1.5/m`; para que no invierta el
sentido de la línea hace falta

```
|dz| · 1.5/m ≤ gradiente     ⇒     m ≥ 1.5 · |dz| / gradiente
```

Es una cota (supone gradiente uniforme), así que `ajustar_extremo` comprueba el
resultado y vuelve a alargar si se ha quedado corta. Converge en dos o tres
vueltas.

**Medida.**

```
antes: 284.8 … 302.9 303.2 303.2 303.2 303.2 303.2 303.2 303.2
ahora: 284.8 … 300.7 301.2 301.4 301.5 301.5 301.6 301.9 302.4 303.2
```

**De paso.** `topology._sellar_extremo` hacía el mismo reparto con su propia
copia del código. Ahora delega en `divides.ajustar_extremo`: con el duplicado,
esta corrección se habría añadido a una de las dos y no a la otra.

---

## B-025 · Muro vertical al empalmar una subcresta con su divisoria 🔴

**Síntoma.** Subcrestas que terminan en la cota correcta… con un salto vertical
en el último segmento. Medido en el Ej_2: la subcresta fid 57 (main R3 idx 7)
subía de **300.7 a 336.0 m en 3.69 m** de recorrido, un **955 %**. El original
no pasa de **65.7 %** en ninguna de sus 244 líneas de cresta. **12 subcrestas y
3 vaguadas** del Ej_2 pasaban del 100 %.

**Causa raíz.** `topology.empalmar_en_divisorias` elegía la divisoria más
próxima **en planta** (`_mejor_proyeccion`) y metía toda la diferencia de cota
en la cola, sin mirar qué pendiente salía y sin repartir nada. Y
`_densificar3` con `n = max(1, int(d // 4))` no densifica por debajo de 4 m, así
que los 35.3 m de desnivel caían en **un solo segmento**.

Es la regla de oro nº 5 («toda corrección de extremos se mezcla, no se pega»)
incumplida en un sitio nuevo, once meses después de B-009.

**Corrección.** Se comprueba la pendiente del tramo que se añade contra
`MAX_PENDIENTE_EMPALME` (100 %, el mismo valor que `divides.MAX_PENDIENTE_FILO`).
Si no pasa, se prueban las divisorias siguientes (`_proyecciones` devuelve la
lista ordenada, no solo la mejor); si ninguna vale, **no se empalma** y queda
constancia en el registro. Un hueco en planta lo resuelve el TIN; un muro de
35 m, no. La cota la arregla después `divides`, que baja la divisoria a la cota
de la cabecera — que es el orden de mando documentado: **manda la ladera, la
divisoria se calcula como envolvente**.

---

## B-024 · La cota de cresta no casaba con el perfil que se dibujaba

**Síntoma.** Ninguno evidente. Las crestas salían algo más bajas de lo que la
documentación decía, y el perfil de ladera nunca llegaba a agotar la pendiente
máxima de Ajustes: se quedaba en el **75 %** de ella.

**Causa raíz.** `ridges._z_ladera` usaba `Δz = 0.5·s_max·D` mientras el
docstring del propio módulo (`ridges.py:12`) y `context/01_metodo_geofluv.md`
decían `(2/3)·s_max·D`. Es el patrón de **B-016** —documentación que contradice
al código— aplicado a una constante del método: un agente que leyera la
documentación y «corrigiera» el código hacia 2/3 tampoco habría acertado.

**Corrección.** No es escribir 2/3 en el código. El desnivel de una ladera **no
es un múltiplo fijo** de `s_max·D`: sale de la propia ecuación del perfil que se
va a dibujar. En `perfil_trapezoidal` la pendiente del tramo recto —la máxima de
todo el perfil— vale `s_m = dz/(D − lc/2 − lf/2)`; igualarla a `s_max` da

```
Δz = s_max · (D − lc/2 − lf/2)
```

que con `lc` y `lf` saturados en sus topes (0.6·D y 0.3·D) es `0.55·s_max·D`,
con `lc = 0.367·D` es `(2/3)·s_max·D`, y con una cabeza convexa pequeña tiende a
`s_max·D` (ladera recta). `ridges.tramos_de_ladera()` es el único sitio donde se
acotan `lc` y `lf`, y la usan las dos funciones: no pueden desincronizarse.

Retirada `ridges.perfil_ladera()`: no la llamaba nadie y su docstring describía
el perfil superado de dos parábolas, con `H = s_max·D/2`. Dejarla ahí era
mantener viva la contradicción.

**Dos suposiciones que el test tumbó mientras se escribía**, y por las que está
escrito: el rango del factor **no** es 0.55–0.667 (con `lc` = 12 m en una ladera
de 60 m es **0.80**), y el factor 2/3 no sale de `lc = D/3` sino de
`lc = 0.367·D`.

**Aviso sobre la magnitud.** Al detectar esto se dijo que las crestas salían un
27 % más bajas que las del original. **Era una medida mal hecha**: se dividió la
mediana de un reparto entre la mediana de otro. Medido **por línea**, la
pendiente recta cresta-pie da p50 = 17.4 % frente a 19.0 % del original en el
Ej_2 (media 21.6 % frente a 21.0 %), es decir mucho más cerca. La corrección
sigue siendo necesaria —código y documentación no pueden decir cosas
distintas—, pero su efecto es modesto.

---

## B-023 · El perfil del cauce sacrificaba la pendiente de cabecera pedida 🔴

**Síntoma.** Los tributarios cortos y empinados salían con la cabecera al doble
de la pendiente pedida. Medido en el Ej_2:

| canal | pedida | nuestra | original |
|---|---|---|---|
| main L1 | −15.4 % | **−26.91 %** | −16.16 % |
| main R4 | −17.44 % | **−36.95 %** | −18.29 % |
| main | −18.0 % | −18.0 % | −17.57 % |

**Causa raíz.** `profile.disenar_perfil` exigía **concavidad estricta**,
`s_cabecera < m < s_boca` con `m` la pendiente media. Cuando no se cumplía —es
decir, cuando la cabecera pedida era **más tendida que la media**— re-empinaba
la cabecera con `s_cabecera = 2m − s_boca` para forzar una parábola cóncava.

El canal principal salía bien porque su cabecera **sí** es más empinada que la
media; los tributarios cortos, no. Y como de la cota del cauce cuelgan las
crestas, las laderas y la superficie, el error se propagaba a todo el diseño.

**Corrección.** Solo se impone la **monotonía** (Fritsch–Carlson, `0 ≤ s/m ≤ 3`,
más el signo). Si la cabecera es más tendida que la media, algún tramo
intermedio **tiene** que ser más empinado que ella: la cúbica de Hermite lo
resuelve sola en cuanto se deja de forzar la concavidad, con la pendiente
creciendo desde la boca, haciendo máximo en torno al 70–80 % del recorrido y
decreciendo hacia la cabecera — un **tramo convexo de cabecera**, que es lo que
hace el original. Ver ADR-017.

**Medida.** Deciles de pendiente boca → cabecera de main L1:

```
original  6.5  9.8 12.6 14.9 16.5 17.6 18.1 18.1 17.4 16.2
antes     6.6  8.8 10.9 13.0 15.2 17.3 19.4 21.6 23.7 25.8
ahora     7.7 11.4 14.5 16.8 18.5 19.5 19.8 19.4 18.3 16.5
```

Máximo en el decil 7 y descenso hacia la cabecera, como el original, y monótono.

**Lección.** «Cóncavo» en el método significa cóncavo **en su conjunto**. La
concavidad estricta era una regla que nos habíamos inventado, y se notaba
porque obligaba a tirar un dato del usuario para poder cumplirla. **Cuando una
restricción te obliga a ignorar lo que el usuario ha pedido, sospecha de la
restricción.**

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
   Y por **suposición** tampoco → B-027: «arranca siempre en el cauce» dejó de
   ser cierto en cuanto otro módulo pudo partir o invertir la línea.
2. **Parchear el último vértice** → B-009, B-002, **B-025**. Mezcla la
   corrección. Y mézclala **lo suficiente**: repartir poco produce mesetas
   (B-026), que es el mismo defecto por el otro lado.
3. **Corregir después en vez de generar bien** → B-017. Primero curvar, luego recortar.
4. **Orden de las etapas del pipeline** → B-014, B-017. El orden ES el algoritmo.
5. **Heurísticas sin cita** → B-011. El libro manda.
6. **Documentación que contradice al código** → B-016, **B-024**. Es más
   peligrosa que la falta de documentación. Cuando una constante y una ecuación
   dicen cosas distintas, la cura no es copiar la constante: es **despejarla**
   de la ecuación, para que no puedan volver a separarse.
7. **Recorrer desde los extremos** → B-010. Usa operaciones geométricas de conjunto.
8. **Rellenar por posición** → B-006. Siempre por nombre de campo.
9. **Un solo caso de prueba valida un solo escenario** → B-022…B-027. Cinco
   bugs de golpe al meter el segundo ejemplo, todos en código que llevaba meses
   «validado» contra el primero.
10. **Código duplicado que se desincroniza** → B-024, B-026. Dos copias del
    mismo reparto con smoothstep, dos versiones de la misma ecuación, dos
    definiciones de «ladera norte o este» (ADR-018). Siempre se arregla una.
11. **Una restricción que te obliga a ignorar lo que el usuario ha pedido es
    sospechosa** → B-023. La concavidad estricta del perfil no estaba en el
    método: nos la habíamos inventado, y se notaba porque para cumplirla había
    que tirar la pendiente de cabecera del usuario.
12. **Leer los datos de entrada antes de medir la salida** → B-022. Media
    sesión comparando geometrías que diferían porque los parámetros estaban
    tecleados en otro orden.
