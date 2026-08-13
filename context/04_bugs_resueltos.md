# Catálogo de bugs resueltos

> **Léelo antes de "arreglar" cualquier cosa de geometría.** Cada entrada tiene
> el síntoma, la **causa raíz** y la medida que demostró la corrección. Lo más
> reciente arriba.

---

## B-045 · La divisoria era equidistante del EJE, no de la LÍNEA DE VALLE 🔴

**Síntoma.** Las crestas que separan las cuencas salen más quebradas que las del
original, con picos. Giro acumulado **70 °/100 m** de media frente a 6.5–31.3 del
original; ángulo de giro máximo **42.9°** frente a 17.3°; radio de curvatura
mínimo 7 m frente a 19 m y p10 32 m frente a 74 m.

**Causa raíz.** `ridges._capa_puntos_canales` muestreaba `d.puntos`, el **eje
meandriforme**. La divisoria heredaba así la ondulación del meandro, con la
longitud de onda del meandro y una amplitud que depende del **desfase entre dos
cauces vecinos** — o sea, de algo que no la debería gobernar en absoluto.

El método la quiere equidistante de las **polilíneas de fondo de valle**:

> *«The main ridgelines are shown between the tributary channels and are
> **sub-parallel to the channels**»* — Natural Regrade Module, p. 36-37.
>
> El Preview muestra *«main ridgelines (yellow) and **valley centerlines (more
> linear blue)**»*, y los ejes zigzag o sinuosos *«will be designed **around**
> the more linear valley input lines»* — LIBRO p. 242, pie de la fig. 9-13.

**La medida.** `|d₁ − d₂|` en cada vértice, contra las dos líneas más próximas:

| | a las líneas de VALLE | a los EJES meandriformes |
|---|---|---|
| original (7 divisorias) | **0.02 – 0.73 m** | 1.0 – 2.9 m (máx 15.5) |
| nuestro, v1.0.24 (11) | 1.77 – 4.52 m | **0.14 – 1.78 m** |

Y al revés: repitiendo el Voronoi sobre **muestras** de las líneas de valle, la
divisoria del original queda a 0.02–0.85 m de la frontera resultante, con el
mismo resultado para pasos de muestreo de 0.5, 1 y 5 m — el error de aproximar
la bisectriz de dos curvas por la de dos nubes de puntos vale ~h²/8d, o sea
0.05 m con h = 5 m y d = 65 m. **Lo único que importa es de qué línea se
muestrea.**

**La corrección.** `ridges._muestras_de_valle(d)` devuelve los puntos de `d.dens`
(ya densificado a 1 m por `builder`), con respaldo a `d.puntos` si un diseño no
lo trae. `_geoms_ejes` sigue devolviendo el eje meandriforme **a propósito**: la
distancia cauce-divisoria que gobierna la cota de ladera se mide al agua de
verdad. Hay una prueba que lo fija.

**Efecto lateral medido y aceptado.** El área de cada subcuenca cambia entre
**−1.21 % y +1.97 %** (rejilla de 2 m dentro del límite del Ej_2), y `Qpk` es
proporcional al área.

**Lo que NO era.** No era falta de suavizado. La ondulación tiene λ ≈ 40–50 m y
amplitud de metros: para borrarla habría que suavizar tanto que la divisoria
dejaría de ser equidistante de nada. `_suavizar_xy` se revisó y **se dejó como
estaba**, con la cuenta en su docstring.

---

## B-046 · La red de divisorias se troceaba donde no toca 🔴

**Corregido y medido sobre el Ej_2 regenerado: de 11 divisorias a 7, que son
exactamente las que tiene el original.**

**Primero, dos correcciones a lo que yo mismo había escrito en esta sesión.**

1. **El original tiene 7 divisorias y 2102.9 m**, no 6 y 1985. Me quedé con la
   lista de cinco FID que me dio Samuel más las que encontré por equidistancia, y
   **descarté la fid 1957 (117.5 m) sin comprobarla**, cuando estaba en mi propia
   salida. Ya estaba en ADR-021 y en el docstring de `encadenar_arcos`.
   El clasificador bueno **no es la longitud ni la equidistancia**, es la **malla
   de emisión**: las 7 divisorias tienen ≥ 88 % de sus segmentos en múltiplos
   enteros de 6.10 m (`m_fMaxDistOnRidges`), y ninguna otra línea de `GF_Ridges`
   pasa de 0.40. Separación limpia, sin umbral que discutir.
2. **`cresta 1` (116.0 m) NO es una colilla**: es la homóloga de la fid 1957
   (117.5 m). Lo que sobra de verdad son `cresta 10` (45.7) y `cresta 11` (45.9),
   y el original **sí dibuja algo ahí** —fids 1883 (41.6 m) y 1830 (49.9 m)— pero
   fuera de la malla de 6.10: son red de ladera, no divisorias.

**Causa (a): `_partir_en_confluencias` parte en confluencias AJENAS.**
`puntos_confluencia` (`ridges.py`) devuelve `(x, y, z)` a secas, sin decir de qué
pareja de cauces es cada confluencia, y el único filtro es la distancia, con
`tol_conf = max(3·PASO_CRESTA, max_dist_cresta_cabecera)` = **50 m** en el Ej_2.
Prueba en los datos:

```
cresta 5.fin ≡ cresta 6.ini = (719670.09, 4408225.34, 289.091453)  — distancia 0.000 m
    confluencia de main L1 a 38.28 m, z de lecho = 289.091453   ← la cadena separa main|R1
cresta 8.fin ≡ cresta 9.ini = (719753.84, 4408245.98, 285.047133)  — distancia 0.000 m
    confluencia de main R1 a 33.54 m, z de lecho = 285.047133   ← la cadena separa R1|R2
```

La cota del corte coincide **a seis decimales** con el lecho de una confluencia
que está a 33–38 m y que **no es de los dos cauces que esa divisoria separa**.
`cresta 5+6` = 389.5 m frente a los 383.8 de la fid 1921; `cresta 8+9` = 320.2
frente a 325.5 de la fid 1882. **No sobran divisorias: sobran dos cortes.**

Eso **cierra P-26 con la explicación correcta**: no nos quedábamos 96 m cortos,
estaban partidas. Emparejando por geometría y no por longitud, los siete residuos
son ≤ 12 m y el total 2097.2 frente a 2102.9 m (**−0.27 %**).

**Causa (b): el tercer brazo de un nudo triple se emite como divisoria.**
`encadenar_arcos` cose solo la pareja más enfrentada y el bucle final emite el
brazo sobrante como cadena propia. Los extremos de `cresta 10` y `cresta 11`
equidistan de **tres** cauces a 42.68/42.68/42.68 y 50.78/50.78/50.78 m: es la
definición de vértice de Voronoi.

**El criterio implementado es topológico, no de longitud** (`ridges.toca_el_limite`):
una divisoria separa dos subcuencas, nace en la confluencia donde sus aguas se
juntan y se aleja de ella hasta salir del área de diseño, así que **un extremo
llega siempre al límite**. Lo que no existe es una divisoria con los dos
extremos dentro: eso es el brazo suelto del nudo triple.
Verificado sobre las 7 del original: las 7 tienen un extremo a **0.00 m** del
límite y el otro a 70–135 m. Aplicado a nuestras 10, se queda con **7** y tira
las tres que no lo son (97.1, 42.1 y 40.4 m), cuyos extremos equidistan de
**tres** cauces — la definición de vértice de Voronoi.

**Resultado medido tras las dos mitades**: 7 divisorias y 1981.0 m frente a las
7 y 2102.9 del original; `|d₁−d₂|` de 0.40 a 0.99 m (original 0.02–0.73); giro
de 18.7 a 36.3 °/100 m (original 6.5–31.3); ángulo máximo 21.9° (original 17.3);
radio mínimo 15.8 m (original 19). Seis de las siete cumplen además el criterio
completo límite→confluencia; la séptima llega al límite pero acaba a 49 m de su
confluencia en vez de a 25, o sea que **le sigue faltando un trozo**.

**Y NO vale un umbral de longitud.** La divisoria legítima más corta del original
mide **25.0 m** (fid 1922), que es exactamente `divides.min_divisoria`. Un umbral
en 80 m mataría las crestas 6 y 9, que no sobran: **son el trozo que les falta**
a las 5 y 8. Los tres filtros de longitud que hay hoy son además el mismo número
tres veces (1×, ½× y ½× de `max_dist_cresta_cabecera`), y esa constante **no
significa longitud de divisoria**: es *xrh*, distancia divisoria→cabecera
(LIBRO p. 189).

**Descartado por medida**: el criterio del «casquete final del tributario» da
**0 %** en las tres líneas sospechosas, así que no las explica. Y el criterio de
estación tampoco, porque el original **sí** tiene divisoria aguas abajo de la
boca del último tributario (fid 1789, main|R4).

---

## B-049 · La marcha de ladera paraba en la equidistancia de los EJES 🔴

**Regresión creada por B-045**, detectada antes de regenerar.

**Síntoma esperado** (no observado aún, porque no se ha regenerado): la subcresta
deja de morir sobre la divisoria. Vuelve B-034 por un lado —extremos altos en el
aire— y `divides._cortar_en_divisorias` amputa por el otro.

**Causa raíz.** `hillslopes._trazar_ladera` paraba cuando `d_otro <= d_propio`
medido sobre `_geoms_ejes` (los **ejes meandriformes**), mientras que desde
B-045 `GRD_Ridges` está sobre el eje medial de las **líneas de valle**. Son dos
curvas distintas.

**La medida.** Reconstruyendo el eje medial de los valles desde los 378 vértices
de `GRD_Ridges`, la separación entre las dos curvas tiene **mediana 1.12 m, p90
4.83, p95 6.63 y p99 7.52 m**. Contra las tolerancias del propio código:

| tolerancia | dónde | % de vértices fuera |
|---|---|---|
| 2.0 m («ya está sobre una divisoria») | `topology` | **32.9 %** |
| 2.5 m (`sellar_contra_divisorias`) | `topology` | **25.1 %** |
| 4.5 m (`holgura_divisoria_m`) | `divides` | 11.3 % |
| 24 m (`radio = 6·PASO_MARCHA`) | `hillslopes` | 0.3 % |

El gancho de 24 m con el que la ladera cuelga de la divisoria **aguanta** (factor
3 sobre el p99). Las que no aguantan son las dos primeras.

**La corrección.** `_trazar_ladera` recibe `geoms_div` (líneas de valle) y la
condición de parada se mide contra él; `geoms` (ejes) se queda **intacto** para
`_z_ladera`, porque la cota de ladera depende de la distancia **al agua**. El
diccionario se construye en `generar_subcrestas` y no se importa de `ridges` a
propósito: el bloque `from .ridges import (...)` lo parchea
`tests/test_registro_laderas.py` por cadena exacta.

**Pendiente de la regeneración**: subir las dos tolerancias de `topology` (2.0 y
2.5 m) al p95 medido de separación eje↔valle. **No copiar el 7 m de aquí**: hay
que recalcularlo con la geometría nueva.

---

## B-044 · `encadenar_arcos` rebanaba un `QgsPointXY` 🔴

---

## B-047 · El enlace del tramo A con el sinuoso daba un salto 🔴

**Síntoma.** «El enlace entre la zona sinuosa y la recta hace una geometría
extraña.» En el eje `main` del Ej_2, entre los vértices 548 y 549 (estaciones
628.8 y 634.1 m), el desplazamiento respecto al fondo de valle pasaba de
**+0.10 m a −5.11 m en un paso de densificado de 1 m**, con giros de **108.7° y
98.1°**. El original, en esa misma transición, no pasa de 66.6°, y los vértices
de su zigzag giran 59.2°, que es exactamente el ápice teórico para k = 1.15 y
reach = 20 m.

**Causa raíz — dos cosas a la vez.**

1. La forma de onda se **elegía** en cada vértice, y las dos tienen amplitud y
   longitud de onda distintas pero **compartían una sola fase acumulada**. Al
   cambiar λ, el mismo valor de fase cae en un sitio distinto de cada onda, así
   que cuando le tocaba el relevo la triangular podía estar en cualquier punto de
   su ciclo: el desplazamiento saltaba.
2. La rampa `min(1, |s − s_t| / (λ/8))` estaba ahí para disimularlo, y con
   λ/8 ≈ 5 m frente a una amplitud de 5.7 m no disimulaba nada: clavaba el
   desplazamiento a cero en un punto y lo soltaba cinco metros después.

Y de fondo, `abs(pendiente(s)) > 4 %` se evaluaba **vértice a vértice**, así que
con la pendiente rondando el umbral la condición parpadeaba.

**La corrección.** Las dos ondas se calculan **siempre**, cada una con su fase, y
se mezclan con *smoothstep* sobre una ventana de **una longitud de meandro del
canal A** (`2 × reach`; el *reach* es media longitud de meandro, LIBRO p. 35). La
estación de transición se decide **una vez**, antes del bucle, como la más aguas
arriba entre la marcada por el usuario y el cruce del 4 % — que es único porque
el perfil es cóncavo. La rampa de la transición desaparece; la de los extremos se
queda.

**La medida.** Mismo caso de banco, código anterior contra el nuevo:

| | giro máximo | dónde | salto máx. en la transición | sinuosidad |
|---|---|---|---|---|
| antes | 69.1° | **en la transición** | 1.59 m (×1.34 el del resto) | 1.181 |
| ahora | **59.2°** = ápice teórico | igual que el resto | 1.06 m (×0.96) | 1.175 |

---

## B-048 · Una subcresta se doblaba 180° sobre sí misma 🔴

**Síntoma.** `GRD_SubRidges` fid 86 (canal `main R2`, índice 15) salía con **66
vértices oscilando entre tres puntos**, 260.6 m de longitud, **sinuosidad 8.318**
y 28 giros de más de 60°, con máximo de **180.00°**. Otras quince subcrestas con
anomalías menores del mismo origen. En el original, las 117 vaguadas tienen
sinuosidad 1.000 y ángulo de giro máximo **0.00°**, y el 94 % de las 120
subcrestas son rectas perfectas.

**Causa raíz — una decisión no idempotente dentro de un bucle de punto fijo.**
`topology.revisar()` repite el pase hasta que nada cambia, con tope de 30
pasadas. El primer filtro de `empalmar_en_divisorias` era

```python
for d_xy, _fid, punto in _proyecciones(...):
    if d_xy < 0.5 or d_xy > tol:
        continue            # <- continue DEL BUCLE DE CANDIDATAS
```

Ese `d_xy < 0.5` quería decir «ya muere sobre la divisoria, no hay nada que
hacer», pero lo que hacía era descartar **esa candidata** y probar la
**siguiente**, hasta 18 m más allá — y prolongar la línea otra vez. A la pasada
siguiente la más próxima era la que acababa de alcanzar, descartada de nuevo, y
volvía a la anterior. **Ping-pong, una cola por pasada.**

**Reproducido aparte** con la lógica anterior y una ladera de 6 vértices que ya
moría sobre una divisoria, con otra a 8 m: 30 pasadas sin converger, **66
vértices, 260.0 m y giro máximo de 180.0°** — la línea real clavada.

**La corrección.** La decisión sale a `topology.destino_de_empalme()`, que tiene
prueba propia: si la candidata más próxima está a menos de `TOL_PEGADO` = 0.5 m,
**la línea está terminada y se devuelve None**. Segunda línea de defensa,
`_se_dobla()`: una cola que sale hacia atrás respecto al último tramo de la
propia línea no se admite nunca.

**Explica también P-05**: el bucle no llegaba a punto fijo, se comía las 30
pasadas.

---

## B-044 · `encadenar_arcos` rebanaba un `QgsPointXY` 🔴

**Síntoma.** Con el DEM ya resuelto (B-042), «Draw Design Surface» llegaba a las
divisorias y moría ahí: ni crestas, ni subcrestas, ni vaguadas, ni superficie,
ni curvas. `GRD_Ridges` quedaba truncada y vacía.

```
ridges.py:996  generar_crestas    -> for dens in encadenar_arcos(arcos)
ridges.py:683  encadenar_arcos    -> math.dist(pto(ext[a])[:2], ...)
TypeError: QgsPointXY.__getitem__(): argument 1 has unexpected type 'slice'
```

**Causa raíz — y no es la línea, es dónde se metió la función.** En el módulo
conviven dos representaciones de punto: `QgsPointXY` (lo que dan `asPolyline()`
y `asMultiPolyline()`) y la tupla plana `(x, y)`. Se parecen lo bastante para
engañar —ambas admiten `p[0]`, `p[1]`, `len(p)` y `x, y = p`, y hasta
`math.dist` funciona con las dos— pero **el `QgsPointXY` no admite rebanadas**.

`_densificar_xy` era el **único normalizador** del camino: recibía `QgsPointXY`
y devolvía tuplas. B-040 insertó `encadenar_arcos` **entre la fuente y el
normalizador**:

```python
# antes de B-040
for pts in partes:                          # QgsPointXY
    dens = _densificar_xy(pts, PASO_CRESTA)      # <- normalizaba AQUI

# despues de B-040
for pts in _cadenas_continuas(inter):
    arcos.append(pts)                       # QgsPointXY, sin normalizar
for dens in encadenar_arcos(arcos):         # <- codigo NUEVO, aguas arriba
    dens = _densificar_xy(dens, PASO_CRESTA)
```

La función nueva se escribió contra el tipo que circula **después** de
normalizar. Su propio docstring lo decía —«devuelve una lista de listas de
(x, y)»— y era falso: devolvía lo que le entraba.

**Corrección.** `_xy(p)` como único sitio donde vive la diferencia;
`encadenar_arcos` normaliza en su entrada, con lo que toda su aritmética interna
—y las dos llamadas a `_tangente`— trabaja con tuplas y el docstring vuelve a
ser cierto; `_densificar_xy` acepta las dos formas.

**Patrón para el catálogo.** *Al insertar una función nueva en un pipeline, hay
que mirar qué tipo circula EN ESE PUNTO, no el que circula donde se la probó.*
Un normalizador solo protege lo que va detrás de él.

**Y la lección de los tests, que es la mitad del bug.** Las 164 pruebas estaban
en verde: le pasaban **tuplas**, que sí admiten `[:2]`. El doble `_PtXY` ni
siquiera tenía acceso por índice, así que a nadie se le ocurrió pasarle puntos.
*Un doble más permisivo que el objeto real no prueba nada.* Ahora `_PtXY` imita
al `QgsPointXY` de verdad —comprobado contra QGIS 3.44: `p[0]`/`p[1]` sí,
`len(p)` 2, `x, y = p` sí, `p[-1]` IndexError, `p[:2]` TypeError— y los
escenarios de encadenado se pasan con los dos tipos.

**Medido.** El test nuevo lanza el mismo `TypeError` ejecutado contra el código
de la v1.0.24, y pasa con el arreglo. Cadena idéntica con tuplas y con puntos de
QGIS en los cuatro escenarios (dos arcos, sentido invertido, nudo triple, ciclo).

**Contexto.** Todo el trabajo de divisorias de la v1.0.24 se midió reproduciendo
el motor **fuera** de QGIS; el CHANGELOG lo avisaba. Este es el primer fallo de
esa clase que aflora al ejecutarlo dentro. Ver B-042 (el que lo tapaba) y B-040
(el que lo introdujo).

---

## B-042 · El DEM se guardaba como objeto, no como referencia 🔴

**Síntoma.** «Draw Design Surface» no llegaba a arrancar:
`Design error: wrapped C/C++ object of type QgsRasterLayer has been deleted`.

**Causa raíz.** El panel guardaba el **objeto** de la capa de elevaciones en
`self.dem_layer`. QGIS destruye el objeto C++ en cuanto la capa sale del
proyecto —el usuario la quita del árbol, se lee otro proyecto,
`removeMapLayer`—, pero el envoltorio de Python sobrevive. La primera lectura,
`dem_layer.dataProvider().identify(...)` en `setup_tools.cota_dem`, revienta.
`cota_dem` solo comprobaba `is None`, y no había un solo `sip.isdeleted` en todo
el código. Lo que mató la capa fue B-043.

**Lo revelador.** El resto del complemento **ya lo hacía bien**: las capas
vectoriales se re-resuelven por nombre en cada uso vía
`LayerManager.obtener_capa` y nunca se cachea el objeto. El ráster era la única
excepción, y por eso fue el único que falló.

**Corrección.** `compat.capa_viva()` (sip, con reserva de tocar la capa y ver si
protesta; en `compat` porque depende de la versión, regla de oro nº 7).
`dem_layer` pasa a ser una propiedad: comprueba que la capa viva y, si no, la
recupera por `proyecto.ruta_dem` —adoptando la que ya esté cargada, o
recargándola del disco— y avisa. `cota_dem` con capa muerta **lanza un error de
dominio** en vez de dejar salir el mensaje de sip; devolver `None` habría sido
peor, porque las cotas caerían al cálculo de reserva y saldría un diseño
silenciosamente equivocado.

**Patrón para el catálogo.** *Guardar el objeto de una capa de QGIS en vez de
re-resolverla es una bomba de relojería.* Y de propina: los seis `except` del
panel enseñaban solo `str(e)` en una barra que caduca a los seis segundos, sin
`traceback` en ninguna parte. Acotar este fallo costó reconstruir a mano la
cadena de llamadas entera. Ahora la traza va al registro de QGIS.

**Medido.** 12 pruebas nuevas en `tests/test_capas.py`, incluida la que impide
la trampa evidente: que la recuperación devuelva **el propio cadáver** por tener
la ruta que se busca.

---

## B-043 · La capa del terreno se duplicaba al abrir el proyecto 🔴

**Síntoma.** Samuel: *«al abrir de nuevas el proyecto se carga la capa en el
grupo de input, a pesar de ya existir»*. Al arrancar no se genera ninguna capa
ráster —el terreno lo elige el usuario— pero al reabrir aparecía repetido.

**Causa raíz.** `_cargar_dem` construía **siempre** un `QgsRasterLayer` nuevo
desde `proyecto.ruta_dem` y lo añadía a «01 Inputs», sin mirar si ese mismo
fichero ya estaba cargado en el proyecto de QGIS.

**Por qué importa más de lo que parece.** No es una molestia estética: es la
causa de B-042. El usuario borra la copia sobrante —lo lógico— y con ella muere
el objeto al que apuntaba el panel.

**Corrección.** `setup_tools.raster_por_ruta()` busca una capa rastera **viva**
del proyecto con esa ruta, comparando con `os.path.normcase(os.path.normpath())`
—en Windows la misma ruta se escribe de varias formas y en crudo parecen
ficheros distintos—. `_cargar_dem` la reutiliza y **la deja donde el usuario la
tenga**, sin moverla de grupo. El mismo buscador sustituye el bucle calcado que
ya había en `_capa_comparacion`.

Ver B-042.

---

## B-040 · La red de divisorias se emitía TROCEADA en los nudos 🔴

**Síntoma.** Samuel señaló que el problema estaba ya en la forma **en planta**,
sobre todo en los extremos de las crestas. Medido:

| Extremos de divisoria | En el LÍMITE | En una CONFLUENCIA | **EN EL AIRE** |
|---|---|---|---|
| Original (14) | 7 (50 %) | 7 (50 %) | **0** |
| Nuestro (26) | 7 (27 %) | 9 (35 %) | **10 (38 %)** |

Los diez extremos en el aire coinciden **exactamente (0.0 m)** con el extremo de
otra divisoria, y se agrupan en **cuatro nudos**. Y la prueba de que solo estaba
troceada: fundiéndolas por sus extremos salen **siete cadenas** con las
longitudes del original.

```
NUESTRO fusionado:  461  399  389  325  234  197  116
ORIGINAL:           454  397  384  325  238  188  118
```

**Causa raíz.** `generar_crestas` compara las subcuencas **por parejas** y emite
cada frontera como entidad, todo dentro del doble bucle. Un punto donde se tocan
tres subcuencas es un **vértice del diagrama de Voronoi**, y ahí **termina** cada
una de las tres aristas — calculadas en tres iteraciones distintas, sin
comunicación entre ellas. Desde dentro del bucle no hay forma de saber que son
el mismo nudo.

**Y un efecto que no se había medido: la cota del nudo era triple.** Los tres
arcos clasifican ese punto como extremo LIBRE y cada uno le resuelve **su**
cota. En el nudo de grado 3 del Ej_2:

```
289.09   299.35   286.01      ->  13.34 m de discrepancia en el MISMO punto
```

`GRD_Ridges` es línea de rotura del TIN, así que ahí la triangulación no puede
salir bien.

**Corrección.** El doble bucle solo **recoge** los arcos, y `encadenar_arcos`
los cose. En un nudo de grado 3 continúa la pareja cuyas tangentes están **más
enfrentadas** —una divisoria no gira 120° en un nudo—, que es el mismo criterio
de coseno que ya usaba `_salir_por_bisectriz`. La tangente se mide por **longitud
de arco**, no por número de vértices.

`QgsGeometry.mergeLines()` no vale: solo funde nodos de grado 2 y en un punto
triple deja los tres arcos.

**El filtro de longitud pasa a la CADENA**, y eso importa por dos motivos:
descartar un arco corto antes de encadenar partiría la cadena por el medio y
dejaría dos extremos nuevos en el aire; y aplicado a la cadena cae solo el brazo
sobrante de cada nudo triple. **Sin ningún umbral nuevo**: el `0.5·long_min`
existía porque una rama es un fragmento, y al emitir cadenas se aplica el
umbral completo.

```
13 arcos -> 9 cadenas -> filtro long_min (50 m) -> 7 cadenas
extremos en el aire: 10 -> 0
```

**Cierra P-22 y P-26.** Los dos muñones de 46 m que caen son los brazos
sobrantes de los nudos: hace tres rondas se midió que «generamos divisorias de
46, 46 y 52 m que el original no tiene» sin saber qué eran.

---

## B-041 · La salida de la confluencia se mezclaba por ÍNDICE 🟠

**Síntoma.** El original llega a la confluencia **perfectamente recto** (p50
**0.0°** de giro en sus últimos 20 m, máx 16°) y nosotros doblamos **35.5° de
mediana y hasta 92°**.

**Causa raíz.** `_salir_por_bisectriz` mezclaba un rayo sintético que avanza
`PASO_CRESTA` **exactos por índice** con una cadena cuyo paso real está entre 5
y 10 m (`_densificar_xy` reparte en `floor(d/paso)` trozos) y que
`_suavizar_xy` altera además de forma desigual. Restar dos parametrizaciones
distintas del mismo índice tiene dos firmas, y las dos se midieron: el espaciado
colapsa en el centro del smoothstep, y **el final de la mezcla cae en una
estación arbitraria** — con `largo` = 50 m, el índice 10 podía estar entre 50 y
100 m, y ahí se pegaba la traza cruda de golpe. En la fid=7 se midieron **109° y
131°** justo pasado ese punto.

**Corrección.** La dirección de prueba y la mezcla van las dos por **longitud de
arco**.

**Lo que además se midió**: la **dirección** de salida ya era correcta en **7 de
nuestras 9 confluencias**, a menos de 4° de la del original. O sea que el
defecto no era elegir mal la bisectriz, sino el pegado.

> ⚠️ **Queda por confirmar en la regeneración.** Medida sobre cadenas
> sintéticas, la función **añade** giro en todos los casos en que la traza no
> viene ya alineada con la bisectriz (20° → 15.1, 45° → 42.3, 89° → 98.4, contra
> 0.9, 2.6 y 6.3 sin ella). Si tras regenerar el giro no baja hacia el 0.0° del
> original, la función hay que **desactivarla**.

---

## B-038 · El suelo tumbaba la divisoria, y su docstring decía lo contrario 🔴

**Síntoma.** Samuel miró los perfiles 3D de la v1.0.22 y dijo que las divisorias
«son crestas de montaña, por lo que deben ser los puntos más altos», y que las
nuestras no lo parecen. Medido, tenía razón:

```
desnivel de cada divisoria
NUESTRAS:  60.5  57.4  30.0  28.9  26.4  17.1 │ 6.5  4.9  3.6  2.9  2.4  2.1  1.3
ORIGINAL:  64.1  61.3  34.8  29.4  28.8  15.4   11.5
```

**Siete de trece con menos de 7 m de desnivel**, una con **2.4 m en 117 m**,
cuando la más pequeña del original tiene 11.5. No son crestas: son líneas
tumbadas.

**Causa raíz.** Dos, las dos mías de la v1.0.22 y las dos en el mismo sitio.

**1. `suelo_de_cresta` se aplicaba punto a punto, y no es continuo.** Su
docstring afirmaba que era *«`max` de funciones continuas, así que es continuo y
no escribe escalones»*. **Falso**: lo que cambia no son las funciones, es **el
CONJUNTO** — `lados` son los dos cauces más próximos, y esa pareja cambia de
miembros a lo largo de la divisoria. `techo_de_ladera` se salva de eso porque
usa `min` y el que entra y sale es el lejano, cuyo término es el mayor; el `max`
del suelo está dominado **justo por él**.

Medido en el Ej_2: el suelo mandaba en el **40.9 %** de los vértices de
divisoria (167 de 408) y él mismo saltaba hasta **15.80 m** entre vértices
consecutivos. La fid=1 tenía **sus 24 vértices pegados al suelo**: no era una
curva, era el perfil del lecho + 0.25.

**2. `resolver_extremo_libre` tomaba el `min` sobre TODA la línea.** El factor de
amplificación del despeje es `1/peso`, y los pesos pequeños están precisamente
junto al extremo fijo, que es donde la divisoria muere: ahí la distancia al
cauce tiende a cero, el techo tiende al propio anclaje y el candidato tiende a
`z_fijo`. **Un solo punto del pie tumbaba los 117 m enteros.**

**Corrección.** El techo y el suelo entran los dos como **cotas del extremo
libre**, nunca punto a punto, con una guarda de peso mínimo (0.5) que acota la
amplificación a ×2. El suelo manda sobre el techo: una divisoria bajo el lecho
es un error duro y quedarse corto de pendiente es solo un objetivo incumplido,
que el propio manual llama *«a best-fit slope adjustment toward the specified
target value»* (p. 1718). Lo que la curva no cumpla se **informa**.

| | v1.0.22 | v1.0.23 | Original |
|---|---|---|---|
| Divisorias > 60 m con < 8 m de desnivel | 4 de 10 | **2 de 10** | 0 |
| fid=1 (117 m) | 2.4 m | **12.7 m** | mín. 11.5 |
| fid=7 (99 m) | 2.9 m | **14.5 m** | |
| Desnivel máximo | 60.5 m | 68.2 m | 64.1 m |

La guarda hizo falta **en las dos direcciones**: sin ella, al meter el suelo dos
divisorias se disparaban a **240 y 100 m** de desnivel.

**Y es lo que dice el método**: la cota de la cresta es la que da la pendiente de
ladera objetivo (NRM p. 1706, *«at elevations that create side slopes less than
a default 5:1 gradient»*; LIBRO pp. 270 y 272, donde la cota de la cresta es
**la incógnita**), y existe un ajuste para **impedir** que la cresta supere el
borde GeoFluv (NRM p. 1717), lo que confirma que por defecto son los máximos del
diseño.

---

## B-039 · Los micro-segmentos los dejaba el propio remuestreo 🟠

**Síntoma.** El 4.3 % de los segmentos de divisoria por debajo de 1 m —el más
corto de **0.43 m con un giro de 119°**— cuando el original no tiene **ni uno**.
Eran los que inflaban la métrica del giro acumulado hasta un falso 220°.

**Causa raíz.** `divides.remuestrear` reinserta los vértices que se conservan
por forma **en su propia estación**, sin ninguna guarda de separación, y esa
estación puede caer a centímetros de una marca regular. Y es **lo último que
toca la planta** de una divisoria: nada posterior la vuelve a limpiar.

**Corrección.** Dos guardas, y la segunda es la que lo arregla: el vértice
reinsertado **desplaza** a la marca vecina si está a menos de medio paso; y los
conservados **tampoco se amontonan entre ellos**, porque un quiebro espurio no
aporta un vértice sino un **racimo** y todos superan la tolerancia. De cada
racimo se queda **el que más se desvía**, no el primero: quedarse con el primero
se comía el ápice de las curvas cerradas, y la prueba de la horquilla de la
v1.0.21 lo detectó al momento.

Segmentos por debajo de 1 m: **4.3 % → 0.0 %**; el más corto, de 0.43 a 2.55 m.

**Lo que NO se tocó.** `_salir_por_bisectriz` era la otra sospechosa —en la
v1.0.22 le solté la guarda de `cos < 0.2` a `cos <= 0`, así que se dispara mucho
más—, pero medida con las dos guardas sobre cadenas de espaciado irregular y
ángulos de salida de 0 a 110°, **no reproduce el defecto**: mismo resultado con
las dos y ningún segmento corto. Sin dato que lo respalde, no se cambia.

---

## B-037 · La divisoria se preguntaba su propia cota anterior 🔴

**Síntoma.** Samuel sacó el perfil 3D de dos divisorias y las comparó con las
del original. La traza en planta era casi la misma; el perfil, otra cosa:

| | fid 13 vs 1829 | fid 15 vs 1788 |
|---|---|---|
| Separación en planta, p50 | 3.1 m ✅ | 1.6 m ✅ |
| Pendiente media | 15.3 vs 14.1 % ✅ | 17.9 vs 15.5 % ✅ |
| **Pendiente máxima** | **93.9 vs 19.5 %** | **74.4 vs 33.0 %** |
| **Vaivén** | **12.49 vs 0.00 m** | **11.67 vs 0.00 m** |

Sumando las 13: **113 m de vaivén contra 15 m** del original. Y giros de hasta
**104°** en los últimos 20 m, contra 33 del original.

**Causa raíz.** Tres cosas encadenadas, y la tercera es un bucle:

1. **El signo estaba invertido.** `ridges._perfil_cresta:720` hacía
   `z = max(z, z_env)`: obligaba a la divisoria a estar **al menos** a la cota
   de diseño. Pero el ajuste se llama *Maximum straight-line slopes* y acota
   **por arriba** (ver ADR-022). Era un suelo donde debía haber un techo.
2. **El suelo se reimponía DESPUÉS de suavizar** (líneas 729-730). El propio
   comentario decía que el suavizado existía «para evitar que los saltos de la
   envolvente dejen dientes en la cresta», y la línea siguiente lo anulaba: el
   suavizado podía rellenar valles pero no rebajar ni un pico. El perfil que
   salía era la **envolvente superior** de `z_env`.
3. **`z_env` no era una curva, era una función a trozos**, porque tomaba la cota
   del canal **más próximo** y una divisoria de Voronoi es equidistante de dos.
   Medido: el ganador cambia en el **21.2 %** de los pasos de vértice a vértice,
   y con él la cota de lecho salta **4.15 m de mediana, 18.72 de p90 y 29.96 de
   máximo**.

Y el bucle, con cita de línea:

```
ridges._perfil_cresta:720   la divisoria NACE como envolvente de las laderas
hillslopes.py:312-323       la cabecera de ladera HEREDA esa cota
topology.py:580, :662       la reestampa con max(), hasta 30 pasadas
divides.py:937              la lee de vuelta como z_cab = max(z de TODA la
                            línea) y la usa como PUNTO DE CONTROL
divides.py:679-689          _restaurar_control la clava exacta
```

La guarda prevista contra esto, `Corredor.techo_cresta`, **era vacua por
construcción**: valía `z_lecho + s_max·d` (la ladera recta) mientras la
coronación real vale `z_lecho + s_max·(d − lc/2 − lf/2)`, entre un 31 % y un
45 % menos; y encima tomaba `max(…, z_DEM)`. Su propio docstring decía que
existía justo para romper este bucle.

**Corrección.** ADR-022, en cinco cortes:

- `ridges.techo_de_ladera(lados)` — techo, `min` sobre **los dos** cauces, cada
  uno con su pendiente y su longitud convexa. `min` de continuas es continua, así
  que el salto desaparece por construcción. Medido: el salto máximo del techo
  pasa de **30.14 a 6.85 m** y los pasos con salto > 2 m del 14.5 % al 7.4 %.
  Con tres lados no mejora (6.85 m), que confirma que dos es el número.
- `ridges._perfil_cresta` — **una sola curva vertical** entre dos anclas, sin
  suelo por vértice y sin re-suavizado. El extremo libre se resuelve en **forma
  cerrada** aprovechando que `perfil_trapezoidal` es exactamente lineal en el
  desnivel:
  `z_alto = min_x[(techo(x) − z_bajo·f(x)) / (1 − f(x))]`.
  Con un techo con un diente de 30 m, el perfil no tiene ningún salto mayor de
  1 m y su vaivén es **exactamente 0**.
- Los tres eslabones del bucle cortados: `hillslopes` (la ladera cuelga de la
  divisoria, y ahora el comentario lo dice), `divides` (deja de derivar la cota
  de las cabeceras; la curva **sobrevive al recorte** porque `_limpiar_vertices`,
  `remuestrear` y `recortar_contra_corredor` interpolan las tres componentes) y
  `topology` (fuera el trinquete `max(z_lin, z0)`; la divisoria no se mueve en
  cota, solo en planta).
- El **gancho** (P-27): `_partir_en_confluencias` sustituía el vértice de
  **mínima distancia** por el punto de confluencia. Ese vértice es el pie de la
  perpendicular, así que el segmento nuevo salía **perpendicular a la traza** y
  podía medir hasta 50 m. Ahora se **parte** ahí y no se inserta nada: ADR-003
  queda intacto, porque lo que da las dos crestas es el corte. Y
  `_salir_por_bisectriz` se rendía con `ref[0] < 0.2`, siendo `ref[0]` el coseno
  entre traza y bisectriz: **cos(90°) = 0 < 0.2**, o sea que descartaba
  exactamente los ganchos que existía para enderezar.
- `checks` C20/C21 medía la pendiente **longitudinal** de `GRD_Ridges` contra un
  objetivo de **ladera**. Es el error de categoría que ADR-009 nombra y que el
  LIBRO p. 180 declara: *«an approximate overall slope, **not a specific part of
  the complex slope profile**»*.

**Cómo se llegó.** No con una hipótesis mejor, sino **dejando de proponerlas**.
Cinco conclusiones mías se cayeron por el camino, y cuatro al contrastarlas
contra el original; están listadas abajo y en `08_pendiente.md`. La causa
apareció al listar los sesenta picos uno a uno con su entorno, y al medir el
salto del canal más próximo vértice a vértice.

---

## B-036 · La monotonía global convertía la divisoria en un trinquete 🔴

**Síntoma.** El perfil longitudinal de `GRD_Ridges` no se parecía al del
original: mesetas larguísimas, segmentos clavados al 100 % y vaivén. Medido en
el Ej_2 sobre las divisorias del original separadas de sus líneas de ladera:

| | Nuestro (v1.0.20) | Original |
|---|---|---|
| Pendiente vértice a vértice, p50 | 10.9 % | 11.8 % ✅ |
| p90 | 31.4 % | 18.6 % |
| **máx** | **100.0 %** | **33.0 %** |
| Segmentos > 33 % | **8.45 %** | **0.00 %** |
| Meseta más larga | **28 vért.** | 2 |
| Vaivén, p50 | **6.7 m** | 1.2 m |

**La mediana ya coincidía**: el ritmo de descenso estaba bien y el defecto
estaba entero en la cola.

**Causa raíz.** `_monotonizar` decidía el sentido del perfil con **los dos
extremos de la divisoria entera** (`sube = zs[-1] >= zs[0]`). Una divisoria
puede tener una loma legítima —sube desde una confluencia, corona y baja a
otra—, y ahí el sentido único la destroza. La divisoria fid=52 del Ej_2, entera:

```
i=0..27   z = 289.31 EXACTO durante 48.8 m      <- meseta de 28 vertices
i=29,30   CONTROL (cabeceras), sube a 297.09
i=31..36  z = 297.23 EXACTO                     <- segunda meseta
i=37..41  -42 %, -100 %, -100 %, -100 %, -100 % <- acantilado
```

Va de 289 a 297 y baja a 276, o sea una loma. Como 276 < 289, la monotonía la
declaraba **descendente** y se volvía un trinquete: los puntos de control son
intocables, así que el perfil quedaba encaramado detrás de ellos y todo lo
demás se aplanaba contra su cota; al llegar al extremo anclado en 276 había que
soltar 21 m en 19, y `_limitar_pendiente` los escribía como cuatro segmentos al
100.0 % clavado — que no es una pendiente, es el cortafuegos escribiendo su
propio tope.

Un solo fallo explicaba las tres cosas: las mesetas, los picos y el vaivén.

**Corrección.** La monotonía se aplica **tramo a tramo entre puntos fijos**, en
el sentido que marcan sus dos extremos, y el perfil no puede salirse del
intervalo que ellos encierran. Reproducido el caso en `test_divisorias.py`: la
loma sobrevive, no queda ningún tramo llano detrás de la corona y el filo deja
de apoyarse en el cortafuegos.

Dos correcciones más de la misma tanda:

* `puntos_de_control` **funde** las cabeceras separadas menos que el paso de
  vértices y se queda con la más alta. Antes las dos aterrizaban en el mismo
  índice y `_restaurar_control` dejaba la que llegara **la última**: el
  resultado dependía del orden del diccionario. La ventana se mide contra el
  arranque del grupo, no contra el último que entró, para que una hilera
  separada algo menos que la ventana no se funda en cadena.
* `max_dist_vertices_cresta` = `m_fMaxDistOnRidges` del `.geo` del original
  (6.1 m). Su espaciado medido da 6.1 / 12.2 / 24.4 / 30.5 — múltiplos exactos,
  o sea vértices sobre una retícula. El nuestro iba de 0.7 a 9.5 m dentro de
  una misma línea, con el 53 % de los tramos por debajo de 3 m. Aplicado a las
  divisorias del Ej_2: 723 → 406 vértices, espaciado p50 5.99 m, 4 % de tramos
  cortos. Se conservan los vértices cuya pérdida desviaría la traza más de
  0.5 m: el ajuste es una distancia **máxima entre vértices**, no licencia para
  comerse una curva cerrada (sin esa salvaguarda una se recortaba 1.8 m).

**Y dos medidas mías que hubo que retirar por el camino**, porque el sesgo es
fácil de repetir:

1. «41 de los 41 segmentos por encima del 40 % tienen una cabecera a menos de
   20 m, el 100 %». Cierto, pero **la tasa base es del 81 %**: casi cualquier
   segmento del filo tiene una cabecera cerca. Un porcentaje alto no dice nada
   si no lo comparas con el que saldría por azar.
2. «Nuestras cabeceras vecinas discrepan 4.00 m de p90 frente a 1.30 del
   original». Son el p90 de **ocho pares** en todo el diseño, y lo marca uno
   solo. No es un fenómeno general y no podía explicar 60 segmentos por encima
   del 33 %. La hipótesis de que la discrepancia fuese la diferencia de cota
   entre los dos cauces también se midió y quedó descartada (r = 0.18).

Ninguna de las dos era la causa. La causa apareció al dejar de contrastar
hipótesis y **listar los picos uno a uno con su entorno**.

---

> **B-028 … B-035 salen de comparar el relieve de LADERA del Ej_2 contra el
> DXF del original**, que distingue por color las 127 subcrestas (amarillo) de
> las 117 vaguadas (cian). Esa separación fue lo que permitió ver que nuestras
> **subcrestas llegaban bien** (63.4 m frente a 65.1) y las **vaguadas no**
> (44.0 frente a 62.4). Sin separarlas, las medias se compensaban y no se veía
> nada.

## B-032 · «Maximum distance from ridgeline to swale head» se tomaba por un retranqueo 🔴

**Síntoma.** Las vaguadas salían cortas y demasiado tendidas, el relieve de
ladera no se parecía al del original y las curvas de nivel formaban abanicos con
cuñas vacías.

**Causa raíz.** Ese ajuste **no es un retranqueo: es la longitud convexa (xc) de
la vaguada** [LIBRO p. 191]. Se usaba para **amputar** 24 m del final de cada
vaguada (`hillslopes._recortar_cola`), y encima la longitud convexa de verdad
salía de un `0.05·D` inventado.

**Corrección.** ADR-019. `ridges.convexo_vaguada()`; el retranqueo desaparece.
La depresión sale de la ecuación que ya teníamos: con el mismo desnivel y los
mismos extremos, el perfil de menor longitud convexa cae **1.28 m más** a media
ladera [LIBRO fig. 8-11, p. 204].

**Lo que casi estropea el arreglo.** La cota de coronación la calculaba
`_z_ladera` con la longitud convexa de **la línea que pregunta**. Como
`Δz = s_max·(D − lc/2 − lf/2)` crece al menguar `lc`, quitar el retranqueo sin
más habría hecho que las vaguadas coronaran **más alto** que las subcrestas
(medido, D = 70 m: 15.68 m frente a 12.71 m). Lo tapaba precisamente el
retranqueo. **Cuando quites un parche, mira qué estaba tapando.**

**Medido (antes).** Alcance de vaguada 44.0 m (original 62.4); longitud media
52.0 m (68.4); pendiente recta p50 S-O 10.8 % (24.0); longitud total del
relieve 14 468 m (19 705).

---

## B-035 · El contador de sillas era acumulado entre divisorias

**Causa raíz.** `res["sillas"]` se sumaba dentro del bucle
`for f in capa_div.getFeatures()` y se usaba como `monotona=(res["sillas"]==0)`.
En cuanto **una** divisoria generaba una silla, **todas las siguientes** del
mismo pase se calculaban sin monotonía. Solo la primera podía recibir el
tratamiento monótono.

**Corrección.** Contador local por divisoria; `res["sillas"]` solo agrega para
el registro.

---

## B-034 · La marcha de ladera se paraba EN EL AIRE 🔴

**Síntoma.** Extremos altos que no tocan nada: el **38 %** de los nuestros, con
un hueco mediano de **10.1 m** hasta la línea vecina. En el original son el
**13 %** y **2.3 m**.

**Causa raíz.** Dos, en el mismo `if`:

1. Al detectar otra línea a menos de `0.7·PASO_MARCHA`, se rompía el bucle **sin
   añadir vértice**. La línea quedaba entre 2.8 y 6.8 m corta —un paso entero de
   holgura, según dónde cayera— y solo heredaba la **cota**.
2. Solo se miraban las líneas del **propio canal**. El argumento era que las de
   canales opuestos debían poder llegar las dos a la cresta de encuentro, pero
   eso ya lo garantiza la equidistancia de Voronoi; lo único que conseguía la
   excepción era permitir que dos laderas de canales distintos **se cruzaran**,
   sin que ninguna comprobación posterior lo arreglara.

**Corrección.** La marcha **termina sobre** la otra línea: se añade como último
vértice su punto más próximo. Y `_RegistroLaderas`, uno solo para todos los
canales, con `QgsSpatialIndex` —antes era un barrido lineal completo en cada uno
de los hasta 600 pasos de cada marcha— y eligiendo la **más cercana** en vez de
la primera en orden de inserción, que es de donde se heredaba la cota.

---

## B-033 · `fundir_con_divisorias` PEGABA el último vértice 🔴

**Síntoma.** Líneas completamente planas con un salto de 20–25 m en el último
segmento. Peor caso medido: **1017 %**.

**Causa raíz.**

```python
ajustes_sub[f.id()] = pts[:-1] + [(sobre[0], sobre[1], z_req)]
```

Dos fallos a la vez: mueve **siempre** el último vértice —aunque la cabecera sea
el primero, que es lo que pasa en cuanto `divides` parte o invierte la línea— y
le **clava** la cota nueva sin mezclar, con `sobre` hasta a `TOL_FUSION = 16 m`
en planta.

Es la regla de oro nº 5 incumplida **en un sitio nuevo**, después de B-009 y
B-025. Y explica por qué `ajustar_extremo` daba bien en las pruebas offline con
esos mismos perfiles (148 % y 4 %): el acantilado no lo hacía ella, ya venía
hecho.

**Corrección.** Pasa por `_sellar_extremo`, que delega en
`divides.ajustar_extremo` y reparte con la mezcla adaptativa de B-026.

---

## B-028 · La traza y las cotas de una divisoria salían de objetos distintos 🔴

**Síntoma.** Laderas con la cota de coronación disparatada, planas, o con
acantilado final. Sin ningún aviso.

**Causa raíz.** `ridges._perfil_cresta` hace `dens = dens[::-1]` cuando el
perfil viene al revés. Es una **reasignación local**: no toca la lista del
llamante. Pero devuelve `zs` en ese orden invertido, y `generar_crestas` lo
emparejaba con `rama`, que sigue en el orden original:

```python
crestas_3d.append((QgsGeometry.fromPolylineXY(
    [QgsPointXY(x, y) for x, y in rama]), zs))     # zs del revés
```

Resultado: **la mitad de las divisorias** —todas aquellas en las que el segundo
extremo sale más alto que el primero— iban en `crestas_3d` con las cotas
invertidas. Y `crestas_3d` es justo lo que `hillslopes._trazar_ladera` consulta
como respaldo para la cota de coronación (radio 24 m): esas laderas heredaban la
cota **del otro extremo de la divisoria**, decenas de metros de error.

**Corrección.** `ridges.traza_y_cotas(linea)` deriva la geometría 2D y el array
de cotas de la **misma** polilínea 3D. La cura no es acordarse de emparejar
bien: es que no haya dos objetos entre los que elegir.

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
13. **Una cita que no dice lo que se le atribuye** → B-032, ADR-020. Peor que
    una constante sin cita, porque parece que la tiene. Dos variantes vistas:
    un ajuste del método **interpretado al revés** (`dist_cresta_swale_m` era
    una longitud convexa y se usaba como retranqueo) y una cita **real pero con
    la sección equivocada** (las sillas: §9.11.2, no 9.4, y sin ninguna cifra).
    Comprueba la sección, no solo que las comillas existan.
14. **Cuando quites un parche, mira qué estaba tapando** → B-032. El retranqueo
    de las vaguadas ocultaba que la cota de coronación se calculaba con la
    longitud convexa equivocada. Quitarlo sin más habría dejado las vaguadas
    POR ENCIMA de las subcrestas.
15. **Dos objetos que hay que mantener emparejados acaban desemparejándose** →
    B-028. Una geometría y su array de cotas, devueltos por separado, con una
    inversión local en medio. Devuelve UNA cosa, o derívalas las dos del mismo
    sitio.
16. **Una propiedad global impuesta a una forma que solo la cumple a trozos** →
    B-036. La divisoria era «monótona» mirando sus dos extremos, y una loma
    legítima en medio la convertía en un trinquete. Si una restricción se
    decide con dos puntos y se aplica a doscientos, pregúntate entre qué puntos
    es realmente cierta.
17. **Un porcentaje sin su tasa base no es una prueba** → B-036. «El 100 % de
    los picos tiene una cabecera cerca» dejó de impresionar cuando resultó que
    el 81 % de todos los segmentos la tiene. Y un p90 de ocho datos es el
    segundo peor dato, no un percentil.
18. **Cuando dos hipótesis seguidas fallan, deja de proponer hipótesis** →
    B-036. La causa apareció al listar los sesenta picos con su entorno —
    posición en la línea, longitud del segmento, qué tenían cerca— en vez de
    seguir buscando confirmación a una idea previa.
19. **Un clasificador que no has calibrado te inventa los datos** → B-036,
    ADR-021. Separar las divisorias del original «por equidistancia» con
    umbrales a ojo daba 17; calibrado contra nuestros propios datos, donde la
    respuesta se conoce, la precisión era del 65 % y el número real es 7. Sobre
    esa cifra falsa se había planificado una fase entera para «recuperar las 4
    divisorias que faltaban» — cuando en realidad nos sobran.

20. **Un bucle de realimentación entre dos módulos** → B-037. A calculaba su
    cota de B y B la suya de A, con un `max()` en medio que solo dejaba subir y
    hasta 30 pasadas para acumular. Se detecta preguntando, de cada dato de
    entrada, **de dónde salió**; si la respuesta lleva de vuelta al mismo sitio,
    no es un dato, es un eco. Y ojo con la guarda que alguien puso para
    romperlo: la de aquí llevaba dos versiones sin poder morder.
21. **Un signo al revés se disfraza de ruido** → B-037. `max(z, z_env)` donde
    debía ir `min` no produce un error evidente: produce una línea fea. La
    pregunta que lo destapa es de qué lado acota el ajuste, y esa la contesta la
    documentación, no el código.
22. **Una constante que compara dos magnitudes distintas nunca muerde** →
    B-037. `techo_cresta` valía `s_max·d` y lo que quería acotar valía
    `s_max·(d − lc/2 − lf/2)`. Si un filtro no rechaza nunca nada, mide otra
    cosa.
23. **Un umbral relativo al NÚMERO DE VÉRTICES deja de valer si cambias la
    longitud de las líneas** → B-040. `margen = 0.08·len(dens)` significaba
    10-20 m mientras las divisorias eran arcos sueltos, y pasó a 40-80 m al
    emitirlas encadenadas. Si un umbral tiene que expresar una DISTANCIA,
    exprésalo en metros de arco: contar vértices lo ata al espaciado, que es
    justo lo que cambia.
23. **«`min` de continuas es continuo» no salva a `max`** → B-038. El argumento
    que hace continuo al techo NO vale para el suelo, aunque la fórmula se le
    parezca: lo que cambia no son las funciones, es **el conjunto** sobre el que
    se agrega. El `min` ignora al miembro que entra y sale porque su término es
    el mayor; el `max` está dominado justo por él. Si copias un razonamiento de
    continuidad de un sitio a otro, comprueba **quién domina la agregación**.
24. **Un docstring que afirma una propiedad es una hipótesis, no una prueba** →
    B-038. El de `suelo_de_cresta` decía que no escribía escalones, y escribía
    saltos de 15.80 m en el 40.9 % de los vértices. Lo escribí yo dos versiones
    antes. Cuando un comentario asegure una propiedad matemática, mídela.
25. **Dividir por algo que tiende a cero convierte centímetros en decenas de
    metros** → B-038. El despeje del extremo libre amplifica por `1/peso`, y los
    pesos pequeños están justo donde la información no sirve. Acota la
    amplificación **antes** de que el caso raro te la encuentre.