# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.1.0/).
Versionado [SemVer](https://semver.org/lang/es/).

Los códigos `B-0xx` remiten a [`context/04_bugs_resueltos.md`], los `ADR-0xx` a
[`context/03_decisiones.md`] y los `P-xx` a [`context/08_pendiente.md`].

## [No publicado]

### Añadido
- **Repositorio de desarrollo completo** para trabajar desde VSCode con
  asistentes de IA: `src/` · `scripts/` · `tests/` · `docs/` · `context/` ·
  `.claude/` · `.vscode/` · `.github/`.
- **`AGENTS.md`**: contrato de trabajo para agentes de IA, con 12 reglas de oro
  destiladas de todos los bugs del proyecto.
- **`context/`**: memoria del proyecto en 10 documentos — glosario, método con
  citas, arquitectura, decisiones (ADR), catálogo de bugs con causa raíz,
  invariantes, comparación medida con el programa original, trampas del entorno
  QGIS/MCP, backlog y bitácora de sesiones.
- **Guiones de construcción**: `build_zip.py`, `deploy_local.py` (con `--watch`),
  `bump_version.py`.
- **Configuración de MCP de QGIS**, tareas y depuración de VSCode, comandos y
  subagentes de Claude Code.
- **GitHub Actions**: CI (ruff + pytest en 3.9–3.12) y publicación automática de
  la release con el ZIP al etiquetar.
- Licencia **AGPL-3.0-or-later**, **CLA**, `NOTICE`, `CONTRIBUTING.md`,
  `SECURITY.md`, `CODE_OF_CONDUCT.md`, `AUTHORS.md`.

### Corregido
- **B-019 · `NameError` silencioso en la rampa de color de `GF_CutFill`.**
  `ai_context._simbolizar_cutfill()` llamaba a `_c(r, g, b)`, una función que no
  existe; debía ser `QColor`. Como el bloque va dentro de un `try/except` mudo,
  el fallo se tragaba en silencio y **la capa de corte/relleno se quedaba sin
  simbolizar**, de modo que la imagen que recibía el modelo de IA en cada
  iteración salía sin la rampa divergente ni la leyenda de rangos. Detectado por
  `ruff` (regla F821) al montar el repositorio.

### Cambiado
- **Nombre del complemento**: *GeoFluvQ — Natural Regrade* → **Geomorphic
  Reclamation Designer**. Paquete `geofluv_q` → `geomorphic_reclamation_designer`,
  repositorio `geomorphic-reclamation-designer` (ADR-014). *GeoFluv™* y *Natural
  Regrade®* son marcas de sus titulares; *«geomorphic reclamation»* es el término
  descriptivo estándar del campo, que nadie puede reclamar en exclusiva.
- Los tests salen del paquete del complemento y viven en `tests/` del repositorio
  (no se empaquetan en el ZIP: **−40 KB**).
- Cabeceras **SPDX** de copyright y licencia en los 37 ficheros fuente.

### Compatibilidad
- **Los proyectos existentes siguen funcionando sin tocar nada.** Se conservan el
  prefijo de capa `GF_`, la extensión `.geofluv.json` y las claves del JSON.
- Quien tuviera instalado `geofluv_q` debe **desinstalarlo**: son dos
  complementos distintos para QGIS.

---

## [1.0.17] — 2026-07

### Corregido
- 🔴 **B-018 · El pie de ladera se identificaba por COTA.** Donde el cauce
  discurre en relleno, la ladera desciende *desde* el cauce y el pie es el punto
  **más alto**; el código cogía el extremo equivocado y anclaba el extremo del
  límite a la cota de la orilla 105 m más allá, produciendo una meseta plana y
  una zanja hasta 1047.85 m en el margen oeste-sur. Ahora se identifica por
  **distancia al corredor** (`Corredor._cerca()`). ADR-010.
- **B-017 · Recurvado después del recorte.** Se aplicaba de nuevo la ecuación de
  perfil sobre líneas ya recortadas, con colas verticales y mesetas como
  resultado. `divides._rehacer_laderas()` se conserva pero **desconectado**, con
  aviso en el docstring. Orden inamovible: **primero curvar, después recortar**.
  ADR-011.
- **B-015 · Curvas de nivel cruzando el cauce** (dos cotas para un mismo punto).
  Nueva `surface.mascara_corredor()` que protege el corredor del filtro de
  suavizado; celda del ráster ligada a la anchura **mediana** del bankfull.
  Δz mediana en los cruces: **0.021 m**. ADR-005.
- **B-016 · Ecuaciones equivocadas en la DOCUMENTACIÓN** de `hydrology.py` y en
  la especificación (leyes potenciales inexistentes, y el rango 2.5–3.2 puesto
  sobre el cinturón en vez de sobre `Rc`). **El código siempre estuvo bien**,
  pero la documentación podía inducir a "corregirlo" hacia lo incorrecto.

### Añadido
- **`tests/test_libro.py`** — 17 tests donde **el docstring de cada uno es la
  cita del libro** que se verifica. Total: **84 tests**.
- Marcador rojo en planta (`QgsRubberBand`, `ICON_CIRCLE`) al deslizar sobre
  *View Longitudinal Profile*.
- Revisión completa del motor hidráulico contra los capítulos 2 y 4: ecuaciones
  de régimen (Williams 1986), Shields, Manning, método racional y geometría de
  meandro.

### Medido
| | |
|---|---|
| Subcresta idx 3 | 1079.72→1062.00, 15.3 % (original 1079.08→1062.00, 12.4 %) |
| Subcresta idx 7 | 1073.42→1062.00, 13.3 % (original 1072.47→1062.00, 14.2 %) |
| *Check Design* | **2 errores**, 67 avisos, 56 informativos |

### Conocido
- Los 2 errores restantes son de **tensión tractiva** (P-01).
- El pipeline pasó de ~3 s a ~15 s; probablemente por rásteres finos cargados,
  pendiente de confirmar (P-04).

---

## [1.0.16] — 2026-07

### Añadido
- **`core/checks.py` + `gui/check_dialog.py` — «Check Design (Error Log)».**
  22 comprobaciones **C02–C52** agrupadas en Entradas · Trazado · Líneas de
  rotura/TIN · Pendientes · Hidráulica · Superficie/volúmenes, con ventana
  filtrable por severidad y grupo, filas pulsables (zoom a la entidad) y
  exportación a CSV.
- **`core/divides.py`** (~1100 líneas): clase `Corredor`, recorte por diferencia
  geométrica, perfiles desde puntos de control, ajuste de extremos con mezcla.
- **Sillas de cresta** (libro §9.4), ajuste `prof_silla_pct` (25 % por defecto).
- **Recetario del capítulo 10** del libro incorporado al prompt de optimización
  de IA, con las cifras del propio libro (balance 70.2→94.3 %, 65.6→110.9 %,
  110.9→104.4 %; tramo convexo hasta el 90 %; pendiente 46→33 %).
- Ajustes nuevos: `holgura_divisoria_m`, `prof_silla_pct`,
  `tol_cruce_breaklines_m`, `tol_cruce_canal_m`, `long_max_lado_tin_m`,
  `pend_max_linea_pct`, `ang_max_valle_ladera_deg`.

### Corregido
- **B-010 · Recorte «de fuera hacia dentro»**: se saltaba las incursiones a mitad
  de línea. Sustituido por **diferencia geométrica** que devuelve todos los
  trozos exteriores al corredor. ADR-006.
- **B-014 · El suavizado corría después del limitador de pendiente** (segmento al
  220 % junto a un anclaje). Orden fijo:
  `_restaurar_control → _monotonizar → _suavizar_entre_control → _limitar_pendiente`.
  ADR-007.
- **B-013 · `_indices_fijos` fijaba siempre los extremos**, así que el limitador
  no podía converger. Ahora fija solo las estaciones de espolón.
- **B-012 · `pendiente_max_pct` aplicada al perfil de la divisoria**, que la
  dejaba 17 m colgada. La divisoria del original desciende al **41 % de media y
  73 % de máximo**: sustituido por `MAX_PENDIENTE_FILO = 100 %` como cortapicos.
  ADR-009.
- **B-011 · Heurística `limite_de_ladera = 2 × media`** sin justificación en la
  literatura. Retirada; se reconstruye con la ecuación del libro.
- **B-009 · `sellar_contra_divisorias` movía solo el último vértice** (escalón de
  26 m en 4 m). Nuevo `topology._sellar_extremo()` con mezcla *smoothstep* de
  25 m y monotonía. ADR-008.
- **B-008 · El conmutador de idioma de la guía se ocultaba a sí mismo**: los
  botones compartían el atributo `data-l` con el contenido. Ahora usan
  `data-idioma`, con `localStorage` (`gfq_lang_v2`) dentro de `try`, respaldo por
  `readyState` y `data-idioma` escrito ya en el `<html>`. El botón *Help* pasa
  `#lang=xx` según el idioma de QGIS.
- **B-002 · Colas verticales** en las subcrestas fid 180, 182 y 218.

### Cambiado
- `MAX_ORDEN` 6 → **10**, `MAX_PASADAS` 12 → **30**.

### Medido
| | antes | después |
|---|---|---|
| Peor gradiente vértice a vértice | 2070 % | **92 %** |
| Empalmes forzados con el límite | 27 (peor 19.68 m) | **1** (0.09 m) |
| Errores del *Check Design* | 13 | **2** |
| Extremo bajo de la divisoria sobre el lecho | — | **+2.29 m** (= original) |

---

## [1.0.14] — 2026-06

### Corregido
- 🔴 **B-007 · Faltaba una cresta divisoria entera.** La frontera Voronoi entre
  dos cuencas **no muere en la confluencia: es una V que PASA por ella** (aguas
  arriba hay divisoria por los dos lados del tributario, así que salen **DOS**
  crestas). El código se quedaba con una de las mitades. La cadena compartida
  medía 305.8 m entre (X1, Y1) y (X2, Y2) — los extremos
  exactos de las dos crestas del original (178.3 m y 96.9 m). De ahí venían las
  cotas incoherentes y el cono de triangulación en la unión de cauces. ADR-003.

### Añadido
- **Guía de ayuda reescrita** (`help/guide.html`): bilingüe, organizada con las
  mismas pestañas del programa, **97 ajustes documentados** y 23 bloques de
  contexto, explicando qué pasa al adoptar un valor u otro.
- **Detección automática de incoherencias**: hoyos cerrados (celdas con las 8
  vecinas más altas: el agua no puede salir) y picos aislados, localizados,
  contados y avisados en el registro, el informe y el prompt de la IA.
- Panel de IA que **abre al instante**: sondeo por socket (0.25 s por puerto) y
  escaneo diferido, en vez de peticiones HTTP a 6 puertos × 2 hosts al construir.
- Registro de optimización **redimensionable y desacoplable**, con copiar,
  guardar y ajuste de línea.
- Mucha más información para el modelo: trazado de cada canal en coordenadas,
  `data/canales_NN.csv` cada 25 m, **tabla de cada cresta y vaguada una a una**
  (`data/lineas_NN.csv`) para poder modificar una sola línea, imagen
  `lines_NN.png` y **georreferencia quemada al pie de todas las imágenes**.

---

## [1.0.13] — 2026-06

### Añadido
- **Primera comparación geométrica sistemática con el original** (mismo terreno,
  mismos ajustes): canal principal 924.2 m vs 935.2 m (−1.2 %), sinuosidad 1.254
  vs 1.269, tributario 471.3 m vs 473.8 m (−0.5 %).
- Perfiles de crestas y vaguadas **editables por la IA** (`ridges_pct`,
  `swales_pct`, y `per_line` con clave `"canal|indice"`).
- **Concavidad del perfil como variable** (`concavidad_perfil`: 0 recto, 1
  estándar, 2 muy cóncavo).
- Búsqueda web conectada, razonamiento explícito (`think` de Ollama), tabla de
  regiones de corte y relleno en el prompt.
- **Realimentación de pendientes efectivas** (`perfiles_efectivos`): si el motor
  recorta la pendiente pedida por monotonía, se detecta que el candidato no ha
  cambiado nada y se avisa al modelo para que pruebe por otro lado.

---

## [1.0.12] — 2026-06

### Añadido
- **Pestaña «AI Optimization»** (opcional). Modelo **en local** (Ollama /
  LM Studio); sin servidor, el resto funciona igual y el bucle sigue en modo
  numérico. El bucle lo lleva el complemento y el motor regenera el diseño, de
  modo que **toda solución es geométricamente válida**. ADR-004.
- Objetivos combinables: volumen de relleno/excavación, equilibrio, `dozer_idx`
  (corte arriba y relleno abajo, para empujar cuesta abajo), acarreo mínimo,
  pendientes de cresta, densidad de drenaje y tensión tractiva.
- Carpeta de trabajo por sesión con `prompt_base.md`, `memoria_geofluv.md`, el
  prompt de cada iteración, `historial.json`, `resultado.json`, `images/`,
  `rasters/` y `data/`.

---

## [1.0.11] — 2026-05

### Corregido
- 🔴 **B-006 · Atributos desplazados una columna en GeoPackage.** GPKG añade
  siempre un campo `fid` al principio; como se rellenaba **por posición**, las
  capas guardadas en disco salían **vacías** (`GF_Channels`, `GF_XSections`,
  `GF_Contours`, `GF_HaulRegions`, `GF_HaulRoutes` con 0 entidades). De ahí
  venían «no veo las curvas», «Mass Haul da problemas» y «Highlight Tractive
  Force Zones no muestra nada». Nuevo `compat.attrs()`. ADR-002.
- Cresta divisoria anclada en la confluencia en X, Y **y Z**.
- Retranqueo de vaguada acotado al 40 % de la ladera (un valor absurdo dejaba el
  canal sin vaguadas).

### Añadido
- **Curvas de nivel 3D** (`LineStringZ`); las capas 2D antiguas se sustituyen
  automáticamente.
- *Check Ridgeline Slope* como **tabla ordenable enlazada**: al pulsar una fila
  se selecciona la línea, se hace zoom y se activa su capa.
- *View Longitudinal Profile* de **todas** las entidades seleccionadas del
  proyecto, superpuestas, con leyenda, casillas por serie, cursor con cotas y
  exageración vertical.

---

## [1.0.10] — 2026-05

Primera comparación en QGIS contra el DXF del original (17 polilíneas de canal,
106 de cresta/vaguada, 147 curvas).

### Corregido
- **B-005 · Todo el canal salía en zigzag** (semilongitud de onda constante de
  24.5 m, sinuosidad 1.12 vs 1.20 del original) porque marcar la transición cerca
  de la boca convertía toda la traza en tipo A. Ahora un tramo va en zigzag solo
  si está aguas arriba de la transición **y** supera realmente el 4 %. Amplitud
  exacta `A = (λ/4)·√(k²−1)` y densificado del eje cada 1 m.
- **B-004 · Vaguadas sobreexcavadas**: se rebajaba la cabecera un 15 % arbitrario
  del desnivel. Ahora se retranquea la distancia del ajuste y toma la cota **de
  la ladera** en ese punto, o la del encuentro de dos subcrestas.
- **B-003 · Divisorias partidas** en 48 esquirlas de Voronoi de ~7 m. Unidas en
  cadenas continuas, suavizadas y con perfil de cresta propio; solo el extremo
  que muere en el límite empalma con el DEM.

### Añadido
- Ventana **«Triangulate and Contour From Design TIN»**: resolución, filtro de
  difusión de ladera, densificado de líneas de rotura, recorte al límite,
  intervalo y maestras, longitud mínima y suavizado Bezier.
- Superficie **recortada al perímetro** (NoData fuera).
- **Mass Haul gráfico**: `GF_HaulRegions` y `GF_HaulRoutes`.
- Almacenamiento de capas a elegir: memoria, carpeta elegida, o carpeta nueva
  junto al proyecto con nombre + fecha y hora.
- *Calculate GeoFluv Volume* con esponjamiento y compactación.

---

## [1.0.1] – [1.0.9] — 2026-04 / 2026-05

Construcción del complemento por partes:

- **Parte 1** — Esqueleto, panel acoplable, ajustes globales y por canal, gestor
  de capas y grupos, proyecto JSON, Setup completo (límite, canal principal,
  transición automática/manual, DEM, tributarios con validación, densidad de
  drenaje con semáforo), hidrología (método racional, secciones trapezoidales,
  geometría de meandros según Williams 1986).
- **Parte 2** — Motor de canales: perfiles longitudinales cóncavos (Hermite con
  monotonía de Fritsch–Carlson, respetando la pendiente de boca como valor
  crítico) con empalme suave de cota y pendiente en las confluencias; planta
  sinusoidal con λ y cinturón ligados al caudal bankfull y amplitud resuelta para
  la sinuosidad objetivo; zigzag tipo A; bordes 3D; capa de secciones con la
  hidráulica por estación; subcuencas por proximidad; nombres R1/L1/R1L1; visor
  de perfil longitudinal; informes por canal y resumen.
- **Parte 3** — Crestas como divisorias equidistantes (Voronoi de los ejes),
  cota de cresta `z_canal + (2/3)·s_max·D` con perfil *smoothstep*; subcrestas en
  ápices de meandro (espaciado impar ⇒ márgenes alternas) y vaguadas con perfil
  más cóncavo; subcuencas reales; superficie de diseño por `QgsTinInterpolator`;
  curvas con maestras; balance corte/relleno con semáforo; centroides de regiones
  conexas con plan de acarreo optimizado; perfil longitudinal automático.

[No publicado]: https://github.com/opengeorock/geomorphic-reclamation-designer/compare/v1.0.17...HEAD
[1.0.17]: https://github.com/opengeorock/geomorphic-reclamation-designer/releases/tag/v1.0.17
[1.0.16]: https://github.com/opengeorock/geomorphic-reclamation-designer/releases/tag/v1.0.16
[1.0.14]: https://github.com/opengeorock/geomorphic-reclamation-designer/releases/tag/v1.0.14
[1.0.13]: https://github.com/opengeorock/geomorphic-reclamation-designer/releases/tag/v1.0.13
[1.0.12]: https://github.com/opengeorock/geomorphic-reclamation-designer/releases/tag/v1.0.12
[1.0.11]: https://github.com/opengeorock/geomorphic-reclamation-designer/releases/tag/v1.0.11
[1.0.10]: https://github.com/opengeorock/geomorphic-reclamation-designer/releases/tag/v1.0.10
