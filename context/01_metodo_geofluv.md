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
- El perfil debe seguir siendo **monótono y cóncavo**: si el usuario (o la IA)
  pide una pendiente de boca mayor que la pendiente media del valle, el motor la
  recorta. Esa limitación se realimenta al optimizador (`perfiles_efectivos`).
- `concavidad_perfil`: 0 = recto, 1 = curva estándar, 2 = muy cóncavo.

`profile.disenar_perfil`, `profile.estacion_transicion`.

---

## 8. Perfil de ladera y cota de cresta

**Perfil trapezoidal** [LIBRO, perfil de ladera de Horton]: convexo en cabeza
(longitud `xc`), recto en el tramo medio, cóncavo al pie.
`ridges.perfil_trapezoidal`, `ridges.perfil_ladera`.

**Cota de la cresta**:

```
z_cresta = z_canal + (2/3) · s_max · D
```

donde `D` es la distancia en planta del cauce a la divisoria y `s_max` la
pendiente máxima de ladera. El perfil intermedio es *smoothstep*: cóncavo al
pie, convexo en la cresta, con pendiente ≤ `s_max`.

**Sillas de cresta** [LIBRO §9.4]: la cresta no es una línea de cota monótona;
lleva rebajes entre culminaciones (`prof_silla_pct`, por defecto 25 %).

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

---

## 10. Subcrestas y vaguadas

- **Subcrestas** en los **ápices de meandro**, con espaciado impar ⇒ márgenes
  alternas, giradas hacia aguas arriba el *Angle from sub-ridge to channel's
  perpendicular*, y terminadas en la divisoria.
- **Vaguadas** intermedias, con perfil más cóncavo (`u²`).
- La cabecera de una vaguada se **retranquea** la distancia *Maximum distance
  from ridgeline to swale head* y toma la cota **de la ladera** en ese punto
  (no un porcentaje arbitrario del desnivel). El retranqueo está acotado al
  40 % de la ladera.
- Si una vaguada nace donde se encuentran dos subcrestas ya trazadas, hereda la
  cota de ese punto de encuentro.

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
| `prof_silla_pct` | 25.0 % | Profundidad de las sillas de cresta [LIBRO §9.4] |
| `tol_cruce_breaklines_m` | 0.10 m | Tolerancia de cruce entre líneas de rotura |
| `tol_cruce_canal_m` | 1.00 m | Tolerancia de cruce con el canal |
| `long_max_lado_tin_m` | 50.0 m | Lado máximo de triángulo del TIN |
| `pend_max_linea_pct` | 300.0 % | Pendiente máxima admisible vértice a vértice |
| `ang_max_valle_ladera_deg` | 60.0° | Ángulo máximo entre vaguada y ladera |
