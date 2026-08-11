# El método: ecuaciones y constantes, con su cita

> **Regla absoluta**: si una ecuación o una constante del motor no está en esta
> página con su cita, no debe estar en el código. Si añades una, añádela aquí
> primero y ponle un test en `tests/test_libro.py` cuyo docstring sea la cita.

## Fuentes

| Clave | Referencia |
|---|---|
| **[LIBRO]** | Bugosh, N. & Martín Duque, J.F. (2024). *Geomorphic Reclamation Design*. Referencia principal del método |
| **[MOD]** | *Natural Regrade Module* — manual del módulo de Carlson (comportamiento de la interfaz y de los ajustes) |
| **[TUT]** | *Basic Natural Regrade Tutorial* — flujo de trabajo paso a paso |
| **[W86]** | Williams, G.P. (1986). *River meanders and channel size*. Journal of Hydrology 88, 147–164 |
| **[ROS]** | Rosgen, D. (1996). *Applied River Morphology* |
| **[DL78]** | Dunne, T. & Leopold, L.B. (1978). *Water in Environmental Planning* |
| **[MD17]** | Martín Duque, J.F. et al. (2017). Geomorphic reclamation… El Machorro, Alto Tajo. *Ecological Engineering* |
| **[BE19]** | Bugosh, N. & Epp, E. (2019). Evaluating sediment production from GeoFluv watersheds at La Plata Mine. *Catena* |

---

## 1. Hidrología — caudal punta

**Método racional** [LIBRO cap. 2]:

```
Qpk = C · i · A / 360          [m³/s],  i en mm/h,  A en ha
```

Dos eventos, dos secciones:

| Evento | Intensidad | Da lugar a |
|---|---|---|
| **bankfull** (formador del cauce) | P(2 años, 1 h) en mm/h | sección bankfull |
| **flood-prone** (avenida) | P(50 años, 6 h) introducida **íntegra** como intensidad horaria | sección flood-prone |

> El criterio conservador de Natural Regrade es *"colocar todo el volumen de la
> tormenta de 6 h en el canal instantáneamente"* [MOD]. No lo "corrijas" a
> mm/h dividiendo por 6: es deliberado.

Implementado en `hydrology.qpk_racional`, `intensidad_2a1h`,
`intensidad_50a6h_instantanea`.

---

## 2. Sección del canal

Trapecio simétrico, **taludes interiores 4H:1V** (`Z_TALUD = 4.0`) [MOD por defecto].

Área a partir de la velocidad máxima admisible [DL78, ROS]:

```
A = Q / v_max
W = wd · d                      (wd = relación W:D del usuario)
b = W − 2·z·d
A = d · (W − z·d)   ⇒   d = √( A / (wd − z) )      con z = 4
```

Sección flood-prone: **mismo fondo `b` y mismos taludes**, resuelta para
`A_fp = Q_fp / v_max`:

```
z·d² + b·d − A_fp = 0   ⇒   d_fp = ( −b + √(b² + 4·z·A_fp) ) / (2·z)
W_fp = b + 2·z·d_fp
```

**Ratio de atrincheramiento** (entrenchment ratio, [ROS]) `= W_fp / W_bkf`.

Hidráulica por estación:

```
P = b + 2·d·√(1+z²)         perímetro mojado
R = A / P                   radio hidráulico
τ = γw · R · S              tensión tractiva [N/m²]
```

`γw = 9810 N/m³` (`GAMMA_W`).

---

## 3. Estabilidad — Shields

```
τ_crit = θc · (γs − γw) · D50
θc = 0.045              (régimen turbulento rugoso)
γs = 2650 · 9.81 = 25 996.5 N/m³
```

Constantes: `THETA_CRIT`, `GAMMA_S`, `GAMMA_W` en `hydrology.py`.
`D50` sale del conteo Wolman del área natural de referencia.

**Criterio**: `τ > τ_crit` en una estación ⇒ error del *Check Design*
(el canal erosionaría). Los dos únicos errores que quedan abiertos en el caso de
prueba son de este tipo — ver `context/08_pendiente.md`.

---

## 4. Verificación con Manning

**No altera el dimensionado** (que es por `v_max`); es una comprobación:

```
Q = (1/n) · A(d) · R(d)^(2/3) · S^(1/2)      → calado normal d_n por bisección
v_n = Q / A(d_n)
F   = v_n / √( g · A / T )                    número de Froude
```

Avisos:
- `v_n > v_max` → la sección se queda corta para esa pendiente.
- `v_n < 0.4 · v_max` → posible sedimentación, o `v_max` optimista.

`hydrology.calado_normal_manning`.

---

## 5. Geometría de meandro — ecuaciones de régimen

**[W86], tal y como las enuncia [LIBRO] cap. 2, *Channel plan view geometry*:**

```
Rc = k · W          con  k ∈ [2.5, 3.2]
λ  = 4.53 · Rc
B  = 0.61 · λ
```

- `Rc` — radio de curvatura. *"the radius of curvature falls within a range of
  approximately 2.5 to 3.2 times the bankfull width"*
- `λ` — longitud de meandro. *"meander length … is 4.53 times the radius of
  curvature"*
- `B` — cinturón de meandro. *"the meander belt width … as 0.61 times the
  meander length"*

Constantes: `RC_MIN = 2.5`, `RC_MAX = 3.2`, `LAMBDA_POR_RC = 4.53`,
`BELT_POR_LAMBDA = 0.61`.

**Un *reach* de canal tipo A es MEDIA longitud de meandro** [LIBRO §2.2.10].

> ⚠️ **Error histórico documentado.** Hasta la v1.0.16 la cabecera de
> `hydrology.py` y el documento de especificación describían unas leyes
> potenciales (`λ = 10.9·W^1.01`, `Rc = 2.4·W^1.04`) y colocaban el rango
> 2.5–3.2 sobre el **cinturón** en vez de sobre `Rc`. **El código nunca hizo
> eso** —siempre implementó las tres ecuaciones de arriba—, pero la
> documentación contradecía al módulo, con el riesgo de que alguien "corrigiera"
> el código hacia lo incorrecto. Corregido en v1.0.17 y fijado con
> `tests/test_libro.py`.

---

## 6. Tipos de canal (Rosgen) y umbral del 4 %

[LIBRO cap. 2] y [ROS]:

| Pendiente | Tipo | W:D | Sinuosidad | Traza |
|---|---|---|---|---|
| **> 4 %** | tipo A | < 10:1 | < 1.2 | **zigzag** (onda triangular) |
| **< 4 %** | valle | > 10:1 | > 1.2 (típico 1.4–1.9) | meandro sinusoidal |

Un tramo se dibuja en zigzag **solo si** está aguas arriba de la transición **y**
su pendiente supera realmente el 4 %. Amplitud exacta de la onda triangular:

```
A = (λ/4) · √(k² − 1)          k = sinuosidad objetivo
```

El eje se densifica cada 1 m (el original densifica ~0.9 m) para que la
polilínea no recorte las curvas.

---

## 7. Perfil longitudinal del canal

**Cóncavo**, con curva vertical de **Hermite con condición de monotonía de
Fritsch–Carlson** — impide que el perfil se ondule entre puntos de control.

- La **pendiente de la boca es el valor más crítico del método** [MOD, TUT]:
  todo el perfil cuelga de ella.
- Empalme suave de **cota y pendiente** en las confluencias.
- **Las dos pendientes que pide el usuario se respetan.** Lo único que se impone
  encima es la **monotonía** (el cauce no remonta): la condición suficiente de
  Fritsch–Carlson, `0 ≤ s_cabecera/m, s_boca/m ≤ 3`, con `m` la pendiente media.
  Si actúa, se marca `ajustado` y se realimenta al optimizador
  (`perfiles_efectivos`) — invariante H7.
- **Tramo convexo de cabecera.** Si la cabecera es más tendida que la media
  (`|s_cabecera| < |m|`) **no cabe un perfil cóncavo**: para bajar el desnivel
  que hay que bajar, algún tramo intermedio tiene que ser más empinado que la
  cabecera. La curva de Hermite lo resuelve sola: la pendiente crece desde la
  boca, hace máximo en torno al 70–80 % del recorrido y **decrece hacia la
  cabecera**. Se marca en `cabecera_convexa`. Es lo que hace el original.

  Medido en el Ej_2 (Rom_Pla), pendiente media (%) por deciles boca→cabecera:

  | main L1 (cabecera pedida −15.4 %) | deciles | cabecera |
  |---|---|---|
  | original | 6.5 9.8 12.6 14.9 16.5 17.6 **18.1 18.1** 17.4 16.2 | 16.2 % |
  | nuestro | 7.7 11.4 14.5 16.8 18.5 19.5 **19.8** 19.4 18.3 16.5 | 16.5 % |

  ⚠️ **Error histórico.** Hasta la v1.0.18 el código exigía concavidad estricta
  (`s_cabecera < m < s_boca`) y, cuando no se cumplía, **re-empinaba la
  cabecera** con `s_cabecera = 2m − s_boca`. Eso sacrificaba el dato del
  usuario: main L1 salía al 25.8 % con −15.4 % pedido, y main R4 al 36.95 % con
  −17.44 %. La concavidad *estricta* no es una regla del método: el método pide
  un perfil cóncavo **en su conjunto**, y el propio original produce cabeceras
  convexas cuando el desnivel lo exige. Ver ADR-017 y B-023.
- `concavidad_perfil`: 0 = recto, 1 = curva estándar, 2 = muy cóncavo.

`profile.disenar_perfil`, `profile.estacion_transicion`.

---

## 8. Perfil de ladera y cota de cresta

**Perfil trapezoidal** [LIBRO, perfil de ladera de Horton]: convexo en cabeza
(longitud `lc`), recto en el tramo medio, cóncavo al pie (longitud `lf`).
`ridges.perfil_trapezoidal`. La pendiente del tramo recto, que es la máxima de
todo el perfil, vale

```
s_m = Δz / (D − lc/2 − lf/2)
```

**Cota de la cresta**. Se obtiene igualando esa pendiente máxima a la máxima de
Ajustes (*Maximum straight-line slopes*) y despejando el desnivel:

```
z_cresta = z_canal + Δz         con    Δz = s_max · (D − lc/2 − lf/2)
```

donde `D` es la distancia en planta del cauce a la divisoria, `s_max` la
pendiente máxima de ladera, `lc` la porción convexa (`ridges.convexo_subcresta`)
y `lf = min(lc, 0.30·D)`. `ridges.desnivel_de_ladera` y
`ridges.tramos_de_ladera` — esta última existe para que la cota de cresta y el
perfil dibujado **no puedan acotar los tramos de forma distinta**.

`Δz` **no es un múltiplo fijo de `s_max·D`**: con `lc` y `lf` saturados en sus
topes (0.6·D y 0.3·D) sale `0.55·s_max·D`; con `lc = 0.367·D` sale
`(2/3)·s_max·D`; y con una cabeza convexa pequeña frente a la ladera tiende a
`s_max·D`, que es la ladera recta. Con los ajustes de los dos ejemplos de
referencia queda entre 0.55 y 0.75.

⚠️ **Error histórico.** Hasta la v1.0.18 esta página y el docstring de
`ridges.py` decían `(2/3)·s_max·D` mientras el código usaba `0.5·s_max·D`. Es el
patrón de B-016 (documentación que contradice al código) aplicado a una
constante del método. La corrección **no** ha sido escribir 2/3 en el código:
ha sido despejarlo de la ecuación del perfil, porque cualquier constante vale
para un caso y falla en otro. Ver B-024.

**Dos objetivos de pendiente, según la orientación.** El método distingue
*Maximum straight-line slopes* (`pendiente_max_pct`) de *North or East
straight-line slopes* (`pendiente_NE_pct`), más tendido porque las laderas
orientadas al norte y al este retienen más humedad y vegetación. En el proyecto
original del Ej_2 son `m_fMaxSlope 33` y `m_fNESlope 22`. Una ladera es «norte o
este» si su acimut **de descenso** está entre 315° y 135°.

Definición única en `params.es_orientacion_NE`, `params.rumbo_de_ladera` y
`params.pendiente_max_ladera`; la usan el trazado (`ridges._z_ladera`,
`hillslopes`) y las comprobaciones (C20/C21). Ver ADR-018.

⚠️ Hasta la v1.0.18 `pendiente_NE_pct` **solo se comprobaba, no se aplicaba**:
el motor trazaba todas las laderas con la pendiente general y luego el *Error
Log* avisaba de un incumplimiento que él mismo había provocado. Y el rumbo salía
invertido para subcrestas y vaguadas, que se trazan del cauce hacia arriba.

**Sillas de cresta** [LIBRO §9.11.2, p. 259]: la cresta no es una línea de cota
monótona; lleva rebajes donde muere cada vaguada. Cita literal, que es lo único
que hay:

> «The head of the swale depressions on the valley walls in natural landforms
> tend to form **'saddles'** between the sub-ridges to either side of the
> depression. In the design, **incorporating dips in the ridgeline at these
> locations** prevents runoff water from flowing down the ridgeline in tire ruts.
> Instead, it allows it to flow off the ridge and down the valley wall swales.»

⚠️ El libro explica **por qué** existen, pero **no da ninguna cifra** de
profundidad —ni absoluta, ni relativa— y lo presenta como una **edición manual
del diseñador**. La palabra *saddle* aparece **una sola vez** en todo el libro.
Nuestro `prof_silla_pct` (25 %) es por tanto **decisión nuestra**, no del método:
ver ADR-020. Y ojo: hasta la v1.0.19 esta página y `core/divides.py` lo
atribuían al «capítulo 9.4», que es *Reference area observation*. La cita del
texto era buena; la sección, inventada.

---

## 9. Divisorias de cuenca

La frontera entre dos subcuencas contiguas se obtiene por **partición Voronoi**
de los ejes de canal, disuelta por canal y unida en cadenas continuas.

> **La divisoria NO muere en la confluencia: es una V que PASA por ella.**
> Aguas arriba del punto de unión hay divisoria por los dos lados del
> tributario, así que de la confluencia salen **DOS** crestas.
> `ridges._partir_en_confluencias()` parte la cadena en la confluencia y genera
> las dos, cada una anclada ahí en X, Y y Z.

Perfil longitudinal de la divisoria: **desciende con fuerte pendiente**. Medido
en el original: **41 % de media, 73 % de máximo**. Por eso **no** se le aplica
`pendiente_max_pct` (que es el máximo de *ladera*); solo actúa
`MAX_PENDIENTE_FILO = 100 %` como cortapicos.

Esto ya no descansa solo en la medida: el libro lo dice, y de paso dice **cuál
es el mando de verdad** (p. 180, §7.4.3, verificado literal):

> *«The units are percentages, **an approximate overall slope, not a specific
> part of the complex slope profile**. Suppose the design has fixed channel
> locations on either side of a ridge and ridge line elevations, and the slope
> steepness target specifies a flatter slope on one side of the ridge. In that
> case, **the ridgeline must move towards the valley on the other side of the
> ridge** to reduce the slope. As the ridgeline moves towards the other valley,
> the slopes on the other valley's side must become progressively steeper. The
> Natural Regrade "maximum straight-line slopes" setting helps the designer
> achieve the condition that as one side of the ridge reaches its slope
> steepness target, the other side of the ridge does not become over-steepened
> [9.11.2.].»*

Dos consecuencias, y la segunda no la teníamos:

1. Es una pendiente **media de ladera**, explícitamente «no una parte concreta
   del perfil complejo»: aplicarla segmento a segmento al filo es un error de
   categoría. Confirma ADR-009 con cita, no solo con medida.
2. El ajuste se cumple **moviendo la divisoria en PLANTA**, no retocándole la
   cota. Nosotros la colocamos por equidistancia y después le derivamos la
   cota; el método la desplaza hacia el valle contrario hasta que las dos
   laderas cumplen. Está sin implementar y sin anotar hasta ahora.

Y el filo **demasiado empinado** el libro lo reconoce como defecto, sin darle
cifra, con un remedio que **no** es recortar (p. 260, §9.11.2, única aparición
de *blend percent* en todo el libro):

> *«…the designer must also consider the effect on the ridgeline's north-to-south
> slopes. The ridgeline profile in the Figure 9-28 example **has become
> over-steepened** to the left of the vertical crosshair in the image.
> **Increasing the 'blend percent' will reduce that over-steepened portion**, as
> would slightly lessening the drop in the slope profile at the crosshairs; the
> designer used both methods to result in a satisfactory edit.»*

O sea: contra un filo empinado, **más mezcla longitudinal**, no un cortapicos
más bajo. `MAX_PENDIENTE_FILO` seguirá siendo lo que dice su nombre.

> ⚠️ La expresión *«ridge-to-toe»*, que circula en resúmenes del método, **no
> aparece ni una vez en el libro**. Es del manual de Carlson (p. interna 1718).
> No la cites como si fuera del libro.

---

## 10. Subcrestas y vaguadas

**Las dos salen del cauce y las dos mueren en la divisoria** [LIBRO glosario
p. xxxiv: la subcresta *«extends from the inside of a stream channel bend up to
a main ridge at the top of the valley wall that makes the catchment divide»*;
p. 211: *«it drew the 3D sub-ridge and swale polylines from the channel to its
sub-watershed divide polyline»*].

- **Subcrestas** en los **ápices de meandro** [p. 41, p. 174], con espaciado
  impar ⇒ márgenes alternas [p. 185, p. 191], giradas el *sub-ridge angle*
  **desde la perpendicular al cauce, hacia aguas arriba** [glosario p. xxxiv,
  rótulo p. 190]. `hillslopes.direccion_de_ladera`.
- **Vaguadas** entre subcrestas consecutivas, desde el **mismo punto del cauce**
  y hacia la margen opuesta.

### La depresión sale del CONTRASTE DE LONGITUD CONVEXA

Esta es la ecuación del relieve de ladera, y es lo único que hace falta
[LIBRO fig. 8-11, p. 204]:

> «**A depression is formed by the shorter swale convex length between the
> longer adjacent sub-ridge convex lengths** and runoff water is directed into
> the swale bottom.»

```
xc_vaguada   = 'Maximum distance from ridgeline to swale head'   [p. 191]
xc_subcresta = 1.5 · xc_vaguada                                  [p. 191]
```

`ridges.convexo_vaguada` y `ridges.convexo_subcresta`. Con el **mismo desnivel y
los mismos dos extremos**, `perfil_trapezoidal` con `lc` menor cae más deprisa:
la vaguada queda por debajo de las subcrestas de al lado. Medido con los ajustes
del Ej_2 y `D` = 70 m: **1.28 m más abajo a media ladera**.

⚠️ **La cota de coronación la fija SIEMPRE la longitud convexa de la
SUBCRESTA**, se la pregunte quien se la pregunte: es una propiedad del filo. Como
`Δz = s_max·(D − lc/2 − lf/2)` **crece al menguar `lc`**, dejar que cada línea
usara la suya haría que la vaguada coronase **más alto** que la subcresta vecina
(medido: 15.68 m frente a 12.71 m).

⚠️ **Error histórico.** Hasta la v1.0.19 *Maximum distance from ridgeline to
swale head* se interpretaba como un **retranqueo** y se le amputaban 24 m al
final de cada vaguada, con un `0.05·D` inventado como longitud convexa. Las
vaguadas llegaban a 44.0 m del cauce cuando las subcrestas llegaban a 63.4 (el
original: 62.4 y 65.1), y salían al 10.8 % de pendiente recta frente al 24.0 %
del original. Ver B-032 y ADR-019.

### Cómo termina una línea

Por orden: en el **límite** del proyecto (cota del DEM), **sobre otra línea de
ladera** ya trazada (hereda su cota en ese punto) o en la **divisoria**
(equidistancia de Voronoi). Si alcanza otra línea, **termina sobre ella**: se
añade su punto más próximo como último vértice. Antes se paraba entre 2.8 y
6.8 m antes, sin añadir nada, y el 38 % de los extremos altos quedaba en el aire
—el original solo el 13 %— (B-034).

---

## 11. Densidad de drenaje

Longitud de canal por unidad de área. Es **objetivo de diseño con varianza
admisible**, medida en el área natural de referencia [MOD, TUT]. El panel la
muestra con semáforo verde/rojo.

---

## 12. Recetario de ajuste (cap. 10 del libro)

Extraído a `core/ai_context.py`, sección
*"Recetario del libro (Bugosh & Martín Duque, 2024)"*, y usado tanto por el
optimizador de IA como por el desarrollador. Cifras del propio libro:

| Situación | Acción | Efecto medido en el libro |
|---|---|---|
| Balance 70.2 % (falta relleno) | ajustar cotas y perfiles | → 94.3 % |
| Balance 65.6 % | " | → 110.9 % |
| Balance 110.9 % (sobra material) | " | → 104.4 % |
| Perfil con exceso de material | alargar el tramo **convexo** de cabeza | hasta el 90 % de la longitud |
| Ladera demasiado empinada | bajar la pendiente máxima | 46 % → 33 % |

Estas cifras son **el orden de magnitud esperable** de cada palanca. Si un
cambio produce efectos muy distintos, sospecha del cambio.

---

## 13. Constantes internas (no del método, sino de implementación)

Estas **no** salen del libro: son tolerancias de la implementación. Cambiarlas es
legítimo, pero debe justificarse y medirse.

| Constante | Valor | Módulo | Qué es |
|---|---|---|---|
| `TOL_LLEGADA` | 20.0 m | `divides` | Distancia a la que una cabecera se considera llegada a la divisoria. **Debe ser > `TOL_EMPALME`** |
| `TOL_EMPALME` | 18.0 m | `topology` | Distancia máx. para empalmar una cresta con la divisoria |
| `TOL_ENCUENTRO` | 22.0 m | `topology` | Distancia entre dos extremos altos para crear cresta de encuentro |
| `LARGO_MAX_ENCUENTRO` | 60.0 m | `topology` | Longitud máxima de una cresta de encuentro |
| `MARGEN_LIMITE` | 3.0 m | `divides` | Holgura para dar por muerta una cabecera en el límite |
| `TOL_BORDE` | 2.0 m | `divides` | A esta distancia del límite la línea muere en él |
| `MEZCLA_CABECERA` | 25.0 m | `divides` | Longitud de mezcla del ajuste de cabecera |
| `MEZCLA_LIMITE` | 45.0 m | `divides` | Longitud de mezcla del empalme con el terreno |
| `MEZCLA_SELLADO` | 25.0 m | `topology` | Longitud de mezcla del sellado |
| `MEZCLA_FUSION` | 35.0 m | `topology` | Longitud de mezcla del desvío en planta |
| `DECAIMIENTO` | 40.0 m | `divides` | Longitud sobre la que se apaga la corrección de un espolón |
| `MAX_PENDIENTE_FILO` | 1.00 (100 %) | `divides` | **Cortapicos** del filo de divisoria, no un objetivo de diseño |
| `PASO_SONDEO` | 1.5 m | `divides` | Resolución de búsqueda del borde del corredor |
| `PASO_CRESTA` | 5.0 m | `ridges` | Densificado de crestas |
| `PASO_MARCHA` | 4.0 m | `ridges` | Paso de avance al trazar subcrestas |
| `SUAVIZADO` | 2 | `divides` | Pasadas del suavizado entre puntos de control |
| `MAX_ORDEN` | 10 | `topology` | Órdenes de cresta como máximo |
| `MAX_PASADAS` | 30 | `topology` | Tope del bucle de convergencia |
| `TOL_FUSION` | 16.0 m | `topology` | Distancia a la que una cresta se funde con la divisoria |
| `DESVIO_MAX` | 8.0 m | `topology` | Desplazamiento máx. en planta de la divisoria |
| `CELDAS_POR_CAUCE` | 3.0 | `surface` | Celdas a lo ancho del canal bankfull (usa la anchura **mediana**, no la mínima) |
| `CELDAS_MAX` | 12 000 000 | `surface` | Tope del ráster |

## 14. Ajustes de comprobación (`params.GlobalSettings`)

| Ajuste | Por defecto | Para qué |
|---|---|---|
| `holgura_divisoria_m` | 4.5 m | Holgura al comprobar que una cresta llega a su divisoria |
| `prof_silla_pct` | 25.0 % | Profundidad de las sillas de cresta. **Decisión nuestra** (ADR-020): el libro las justifica (§9.11.2, p. 259) pero no da cifra |
| `tol_cruce_breaklines_m` | 0.10 m | Tolerancia de cruce entre líneas de rotura |
| `tol_cruce_canal_m` | 1.00 m | Tolerancia de cruce con el canal |
| `long_max_lado_tin_m` | 50.0 m | Lado máximo de triángulo del TIN |
| `pend_max_linea_pct` | 300.0 % | Pendiente máxima admisible vértice a vértice |
| `ang_max_valle_ladera_deg` | 60.0° | Ángulo máximo entre vaguada y ladera |
