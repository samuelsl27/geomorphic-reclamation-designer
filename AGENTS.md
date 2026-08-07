# AGENTS.md — instrucciones para agentes de IA

> Este fichero es el contrato de trabajo para cualquier agente (Claude Code,
> Codex, Copilot, Cursor, Continue…) que toque este repositorio. **Léelo entero
> antes de escribir la primera línea.** Si algo de lo que vas a hacer choca con
> lo que dice aquí, para y pregunta al humano.
>
> *This file is written in Spanish because that is the working language of the
> project (code comments, docstrings, commit messages and the domain vocabulary
> are all Spanish). Answer the user in Spanish unless they write in English.*

---

## 0. Resumen en 30 segundos

**Geomorphic Reclamation Designer** es un complemento de QGIS (3.22 → 4.x,
Qt5 y Qt6) que diseña la rehabilitación geomorfológica de terrenos mineros
siguiendo el método fluvio-geomórfico publicado por N. Bugosh
(*Natural Regrade / GeoFluv™*, marca de su titular; ver §12).

En vez de taludes y bermas rectos, el complemento **construye la red de drenaje
que se formaría de manera natural** en ese sitio con esos materiales y ese
clima, y la superficie estable asociada:

```
límite + fondos de valle + DEM
        │
        ├─ hidrología (Qpk racional, sección trapecial, Shields, Manning)
        ├─ perfil longitudinal cóncavo (Hermite monótono, Fritsch–Carlson)
        ├─ planta con meandros (Williams 1986) o zigzag tipo A si S > 4 %
        ├─ crestas divisorias, subcrestas y vaguadas
        ├─ TIN → superficie de diseño → curvas de nivel
        └─ balance corte/relleno + acarreos
```

Cada elemento es **una capa de QGIS**, organizada en grupos y subgrupos, con las
propiedades hidráulicas como **atributos editables**. El usuario puede editar
cualquier fase a mano y regenerar la geometría desde ahí.

- Versión actual: **1.0.17**
- Autor: **Samuel Sáez López** — equipo **IMGA / UPCT**, mismo equipo de
  [opengeorock.org](https://opengeorock.org/)
- Licencia: **AGPL-3.0-or-later + CLA** (ver `LICENSE`, `CLA.md`)

---

## 1. Reglas de oro (no negociables)

1. **Nunca inventes una ecuación.** Toda fórmula geométrica o hidráulica del
   motor sale del libro de referencia (Bugosh & Martín Duque, *Geomorphic
   Reclamation Design*, 2024) o de un paper citado. Si vas a introducir una
   constante o una relación nueva, tiene que estar en
   `context/01_metodo_geofluv.md` con su cita, o no entra.
   *Ya nos ha pasado*: se coló un `limite_de_ladera = 2 × media` como heurística
   sin justificación y hubo que retirarlo. Ver `context/04_bugs_resueltos.md`.

2. **La corrección tiene que valer para TODOS los escenarios, no para el caso
   con el que depuras.** Frase literal del usuario:
   > *"Las implementaciones de código que hagamos para solucionar los problemas
   > deben de funcionar en todos los escenarios, no solo en el ejemplo que
   > estamos usando para depurar el código."*
   Antes de dar por buena una corrección, pregúntate: ¿qué pasa si el cauce está
   POR ENCIMA del perímetro? ¿si la ladera es plana? ¿si la línea entra y sale
   del corredor varias veces? ¿si hay un solo canal? Ese es el listón.

3. **No identifiques la geometría por la cota.** El pie de una ladera NO es
   siempre el punto más bajo: donde el cauce va en relleno, la ladera baja
   *desde* el cauce y el pie es el punto MÁS ALTO. Identifica siempre por
   **distancia al corredor del cauce** (`Corredor._cerca()`), nunca por Z.
   Este fue el peor bug del proyecto entero.

4. **Orden del pipeline geométrico: primero curvar, después recortar. Nunca al
   revés, y nunca volver a curvar tras recortar.** Aplicar de nuevo la ecuación
   de perfil sobre una línea ya recortada le mete una cola vertical o una
   meseta. `divides._rehacer_laderas()` existe pero está **deliberadamente
   desconectado** y tiene un aviso en el docstring: no lo reactives.

5. **Toda corrección de extremos se mezcla, no se pega.** Mover el último
   vértice y dejar el resto quieto produce un escalón (medimos 26 m en 4 m de
   longitud). Usa `ajustar_extremo()` / `_sellar_extremo()`, que reparten la
   corrección con *smoothstep* sobre una longitud de mezcla y luego imponen
   monotonía.

6. **El suavizado va ANTES que el limitador de pendiente.** Si suavizas después,
   el limitador ya no puede corregir lo que el suavizado ha vuelto a empinar.
   Orden correcto en `perfil_desde_control()`:
   `_restaurar_control → _monotonizar → _suavizar_entre_control → _limitar_pendiente`.

7. **Compatibilidad Qt5 + Qt6 siempre.** Escribe enums con ámbito
   (`Qt.CursorShape.WaitCursor`), usa `exec()` y no `exec_()`, importa `QAction`
   desde `core/compat.py`, y compara tipos de geometría con `compat.tipo_geom()`
   (los enums de PyQt6 no se comparan con enteros). Todo lo que dependa de la
   versión de QGIS pasa por `core/compat.py`; no metas `try/except ImportError`
   sueltos por los módulos.

8. **Los atributos se rellenan por nombre de campo, no por posición.** GeoPackage
   añade un campo `fid` al principio y desplaza todo. Usa `compat.attrs()`.

9. **No rompas la compatibilidad de proyectos existentes.** El prefijo de capa
   `GRD_`, el nombre de fichero `*.grd.json` y las claves del JSON se
   mantienen. Cualquier campo nuevo se lee con `d.get(clave, valor_por_defecto)`.
   *(Hasta ADR-016 el prefijo era `GF_` y la extensión `.geofluv.json`. Se
   renombraron a propósito, aceptando la ruptura, para sacar la marca de todo lo
   que el usuario ve. Esa ruptura ya está pagada: no vuelvas a moverlos.)*

10. **Cambio de comportamiento = test.** Todo arreglo de geometría o de hidráulica
    entra con su test en `tests/`, y el docstring del test cita la fuente
    (página o sección del libro) cuando verifica una ecuación.

---

## 2. Mapa del repositorio

```
geomorphic-reclamation-designer/
├── AGENTS.md                  ← estás aquí
├── CLAUDE.md                  ← puntero a este fichero
├── README.md / README.es.md   ← cara pública en GitHub
├── LICENSE  CLA.md  NOTICE    ← AGPL-3.0-or-later + acuerdo de contribución
├── CHANGELOG.md  CONTRIBUTING.md  SECURITY.md  CODE_OF_CONDUCT.md
├── pyproject.toml             ← metadatos, ruff, pytest
├── .mcp.json                  ← servidor MCP de QGIS (ver §8)
├── .vscode/                   ← settings, tasks, launch, extensiones, mcp
├── .claude/                   ← comandos y subagentes de Claude Code
├── .github/                   ← CI, plantillas de issue y PR
│
├── src/geomorphic_reclamation_designer/        ← EL COMPLEMENTO (esto es lo que se empaqueta)
│   ├── __init__.py            ← classFactory de QGIS
│   ├── metadata.txt           ← metadatos del complemento (versión aquí)
│   ├── plugin.py              ← menú 'Geomorphic Reclamation' + botón de barra
│   ├── icon.png
│   ├── core/                  ← el motor (sin Qt salvo lo imprescindible)
│   ├── gui/                   ← diálogos y panel acoplable
│   └── help/guide.html        ← guía bilingüe GENERADA (no editar a mano)
│
├── scripts/                   ← herramientas de desarrollo
│   ├── build_zip.py           ← genera el .zip instalable
│   ├── deploy_local.py        ← copia el complemento al perfil de QGIS
│   ├── bump_version.py        ← sube la versión en todos los sitios a la vez
│   ├── genera_guia.py         ← regenera help/guide.html
│   └── guia_datos.py          ← el TEXTO de la guía (esto sí se edita)
│
├── tests/                     ← pytest; algunos requieren QGIS instalado
├── context/                   ← MEMORIA DEL PROYECTO (ver §3)
└── docs/                      ← documentación para humanos
```

### Módulos de `core/` (el motor)

| Módulo | Responsabilidad | No debe |
|---|---|---|
| `compat.py` | Absorber diferencias QGIS 3.22↔4.x, PyQt5↔6 | contener lógica de diseño |
| `params.py` | `GlobalSettings` y `ChannelSettings` (todos los ajustes) | tocar capas |
| `project.py` | Estado del proyecto y serialización `.grd.json` | calcular geometría |
| `naming.py` | Convención R1 / L1 / R1L1 | |
| `setup_tools.py` | Fase Setup: validaciones, DEM, transición, densidad de drenaje | |
| `hydrology.py` | Qpk racional, sección trapecial, Manning, Shields, meandros (Williams 1986) | conocer QGIS |
| `profile.py` | Perfil longitudinal cóncavo (Hermite monótono) | |
| `planform.py` | Traza en planta: meandros, zigzag tipo A, bordes paralelos | |
| `builder.py` | **Orquestador** del motor de canales | |
| `ridges.py` | Crestas divisorias, perfil de ladera, subcuencas Voronoi | |
| `hillslopes.py` | Subcrestas en ápices de meandro y vaguadas intermedias | |
| `divides.py` | Recorte contra el corredor y cota derivada de las divisorias | |
| `topology.py` | Empalmes y sellado entre líneas de ladera y divisorias | |
| `surface.py` | TIN, ráster de diseño, curvas de nivel, corte/relleno, acarreos | |
| `checks.py` | 22 comprobaciones C02–C52 (el *Error Log*) | corregir nada, solo informar |
| `structures.py` | Vanes y escena de vegetación | |
| `layer_manager.py` | Árbol de capas, grupos y almacenamiento | |
| `ai_client.py` | Cliente Ollama / LM Studio (local) | |
| `ai_context.py` | `MEMORIA` + imágenes y tablas que se le pasan al modelo | |
| `ai_optimizer.py` | Bucle de optimización, candidatos y puntuación | |

**Dependencias permitidas** (no crees ciclos):

```
compat ← todo
params ← project ← builder
hydrology → (nada del proyecto)
profile, planform → hydrology
builder → profile, planform, hydrology, params
ridges → builder(salida), params
hillslopes, divides, topology → ridges, params
surface → (capas ya creadas)
checks → lee capas, no escribe
gui/* → core/*        (NUNCA core/* → gui/*)
```

---

## 3. `context/` — la memoria del proyecto

**Antes de tocar geometría, lee el fichero de `context/` que corresponda.** Ahí
está condensado todo lo aprendido en meses de depuración contra la salida del
programa original. No repitas errores que ya están documentados.

| Fichero | Cuándo leerlo |
|---|---|
| `00_glosario.md` | Siempre la primera vez. Vocabulario ES/EN del método |
| `01_metodo_geofluv.md` | Antes de tocar `hydrology`, `profile`, `planform`, `ridges`. Ecuaciones con su cita |
| `02_arquitectura.md` | Antes de mover código entre módulos |
| `03_decisiones.md` | Registro de decisiones (ADR). Por qué las cosas son como son |
| `04_bugs_resueltos.md` | **Siempre antes de "arreglar" algo**. Catálogo de bugs y su causa raíz |
| `05_invariantes.md` | Reglas geométricas que el diseño debe cumplir SIEMPRE |
| `06_comparacion_original.md` | Métricas medidas contra la salida del GeoFluv original |
| `07_entorno_qgis_mcp.md` | Cómo probar en QGIS de verdad, y sus trampas |
| `08_pendiente.md` | Backlog: lo que falta y lo que está a medias |
| `09_historial_sesiones.md` | Bitácora. **Añade una entrada al terminar tu sesión** |

**Al terminar una sesión de trabajo, actualiza `context/`**: bug nuevo →
`04`, decisión de diseño → `03`, tarea terminada o nueva → `08`, y siempre una
línea en `09`. Esa es la única forma de que la siguiente sesión no empiece de
cero.

---

## 4. Cómo hacer un cambio (el ciclo)

```
1. LEER      context/04_bugs_resueltos.md + el fichero de context/ del área
2. REPRODUCIR  test que falle, o medida concreta en QGIS. Sin medida no hay bug
3. ENTENDER  la causa raíz. NO parchees el síntoma en el borde del pipeline
4. CAMBIAR   lo mínimo, en el módulo que corresponde
5. PROBAR    pytest -q  →  84 tests deben seguir en verde
6. VERIFICAR en QGIS real vía MCP (§8): mide, no mires
7. COMPARAR  contra la salida del original si el cambio es geométrico (§context/06)
8. DOCUMENTAR context/ + CHANGELOG.md
9. EMPAQUETAR python scripts/build_zip.py
```

### Sobre el paso 3

El error recurrente de este proyecto ha sido **parchear al final**: la línea sale
mal, se le pega una corrección en el último vértice, y aparece un escalón. Si
una línea sale con forma rara, el fallo está en cómo se genera o en qué extremo
se toma como pie, no en el vértice final.

### Sobre el paso 6

"Parece que ya está bien" no vale. Mide: cota del extremo, pendiente máxima
vértice a vértice, distancia al eje del cauce, número de errores del *Check
Design*. `context/06_comparacion_original.md` tiene la tabla de referencia con
los valores del programa original sobre el mismo terreno.

---

## 5. Estilo de código

- **Python 3.9+** (el que trae QGIS). Sin dependencias externas nuevas: solo
  la API de QGIS/Qt y la biblioteca estándar. `numpy` solo si ya está garantizado
  por QGIS. **Nada de pip install en el complemento.**
- **Idioma**: identificadores y comentarios en **español**; los nombres de los
  ajustes y de las capas, en **inglés**, para que coincidan con la interfaz del
  programa original (`GRD_Ridges`, `Maximum distance from ridgeline to swale
  head`…). No traduzcas esos. **Excepción (ADR-015 y ADR-016)**: donde el rótulo
  original llevaba la marca, va sin ella — *Design Boundary*, no *GeoFluv
  Boundary*; prefijo `GRD_`, no `GF_`.
- **Docstrings que explican el PORQUÉ**, no el qué. El estilo de la casa es
  contar la razón física o el bug que motivó el código:
  ```python
  # El pie de la ladera NO es el punto bajo: donde el cauce va en relleno la
  # ladera desciende DESDE el cauce, así que el pie es el punto alto. Se
  # identifica por distancia al corredor, nunca por cota.
  ```
- Líneas ≤ 88 caracteres. `ruff` configurado en `pyproject.toml`.
- Constantes de método en MAYÚSCULAS arriba del módulo, con su unidad y su
  justificación en el comentario.
- Nada de `print()` en `src/`: usa el registro del panel o
  `QgsMessageLog.logMessage`.
- Funciones "privadas" del módulo con `_` delante. Si una función `_x` empieza a
  usarse desde otro módulo, se le quita el guion y se documenta.

---

## 6. Tests

```bash
pytest -q                         # todo
pytest tests/test_libro.py -q     # solo ecuaciones del libro
pytest -q -k divisorias           # un área
```

| Fichero | Qué cubre | Necesita QGIS |
|---|---|---|
| `test_libro.py` (17) | Cada ecuación contra su cita del libro. **El docstring ES la cita** | no |
| `test_hidraulica.py` (10) | Racional, Manning, Shields, meandros | no |
| `test_divisorias.py` (31) | Recorte, perfiles, monotonía, empalmes | no |
| `test_checks.py` (17) | Las 22 comprobaciones | no |
| `test_optimizador.py` (9) | Rangos, candidatos, puntuación | no |
| `test_integracion.py` | Flujo completo headless (15 pasos) | **sí** |
| `test_gui.py` | Construcción de la interfaz (7 pasos) | **sí** |

Los dos últimos se saltan solos si no encuentran `qgis.core`. En CI solo corren
los que no necesitan QGIS.

**Al añadir un test de ecuación**, el docstring debe decir de dónde sale:

```python
def test_longitud_de_onda_del_meandro():
    """Williams (1986), recogido en el libro §2.2.8: lambda = 4.53 * Rc."""
```

---

## 7. Compilar, instalar y versionar

```bash
python scripts/build_zip.py                 # → dist/geomorphic_reclamation_designer_v1.0.17.zip
python scripts/build_zip.py --deploy        # además lo instala en el perfil de QGIS
python scripts/deploy_local.py              # solo copiar (desarrollo rápido)
python scripts/genera_guia.py               # regenerar help/guide.html
python scripts/bump_version.py 1.0.18       # sube la versión en TODOS los sitios
```

El zip contiene una **única carpeta raíz `geomorphic_reclamation_designer/`**, que es lo que QGIS
espera en *Instalar a partir de ZIP*. `build_zip.py` excluye `__pycache__`,
`.pyc`, `.git` y ficheros de desarrollo, y **falla** si la versión de
`metadata.txt` y la de `__init__.py` no coinciden.

**La versión vive en tres sitios** y `bump_version.py` los toca todos:
`src/geomorphic_reclamation_designer/metadata.txt`, `src/geomorphic_reclamation_designer/__init__.py` y
`scripts/genera_guia.py` (`VER`). El número de versión también aparece en el
panel (`gui/dock.py`, constante `VERSION`) — ese también se actualiza solo.

---

## 8. QGIS de verdad, vía MCP

El PC de desarrollo tiene **QGIS 4.2** con el complemento **QGIS MCP**
([`nkarasiak/qgis-mcp`](https://github.com/nkarasiak/qgis-mcp)), que abre un
socket y permite ejecutar código dentro de QGIS desde el editor. `.mcp.json`
(Claude Code) y `.vscode/mcp.json` (VSCode) lo configuran, y los **genera**
`python scripts/configurar_mcp.py`. Ver `docs/MCP_QGIS.md` para arrancarlo.

Con eso puedes: listar capas, ejecutar Python dentro de QGIS, medir geometrías,
recargar el complemento y hacer capturas del lienzo. **Es la única forma seria
de validar un cambio geométrico.**

### Trampas conocidas (te van a morder)

1. **Comprueba cuál es el perfil activo** (aquí es `QGIS4`, no `QGIS3`). Ruta
   del complemento:
   `%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins`
   Instalar en el perfil equivocado significa editar código que nadie ejecuta.

2. **El complemento y el servidor tienen que ir a la misma versión.** Se
   actualizan por sitios distintos y se separan solos; la configuración fija una
   etiqueta (`v0.10.0`), no `main`. `python scripts/configurar_mcp.py` lo cuadra.
   *(El viejo desfase de un turno de `execute_code`, que obligaba a rematar cada
   llamada con un `print("MARCA-n")`, está resuelto desde 0.10.0.)*

3. **Orden de recarga de módulos.** Recargar ordenando por longitud de nombre
   recarga `project.py` antes que `params.py` y `GlobalSettings` se queda viejo →
   `AttributeError` al leer un ajuste nuevo. **Recarga `params` primero**, o
   reinicia QGIS. Ante cualquier `AttributeError` raro tras un cambio de ajustes:
   reinicia QGIS antes de investigar.

4. **Rásteres finos cargados ralentizan todo.** Si el pipeline pasa de ~3 s a
   ~15 s sin haber tocado el motor, mira qué capas hay cargadas antes de buscar
   una regresión de rendimiento.

---

## 9. Git y commits

- Rama de trabajo: `main`. Ramas de tema: `fix/…`, `feat/…`, `docs/…`.
- Mensajes en **español**, imperativo, con ámbito:
  ```
  fix(divides): identificar el pie de ladera por distancia al cauce, no por cota

  Donde el cauce va en relleno la ladera baja DESDE el cauce, así que el pie
  es el punto más alto. El código cogía el extremo equivocado y anclaba el
  extremo del límite a la cota de la orilla 105 m más allá, dejando una
  meseta plana y una zanja hasta 1047.85.

  Medido: subcresta idx 3 pasa de 1079.16→1062.00 (14.7 %) a
  1079.72→1062.00 (15.3 %); el original da 1079.08→1062.00 (12.4 %).
  ```
  Ámbitos: `core`, `gui`, `divides`, `ridges`, `surface`, `hydrology`,
  `checks`, `ai`, `build`, `docs`, `tests`, `ctx`.
- **El cuerpo del commit lleva la MEDIDA**, no una impresión. Es lo que permite
  reconstruir el razonamiento meses después.
- Un commit = un cambio con sentido. No mezcles renombrados masivos con lógica.

---

## 10. Lo que NO debes hacer

- ❌ Reactivar `divides._rehacer_laderas()`.
- ❌ Identificar extremos de línea por cota.
- ❌ Aplicar `pendiente_max_pct` (el máximo de ladera) al perfil longitudinal de
  una **divisoria**: la divisoria del original desciende al 41 % de media y 73 %
  de máximo. Ahí solo actúa `MAX_PENDIENTE_FILO = 100 %` como cortapicos.
- ❌ Añadir dependencias pip al complemento.
- ❌ Usar `exec_()`, enums Qt sin ámbito, o comparar tipos de geometría con `int`.
- ❌ Rellenar atributos por posición.
- ❌ Editar `src/geomorphic_reclamation_designer/help/guide.html` a mano (se regenera; edita
  `scripts/guia_datos.py`).
- ❌ Renombrar el prefijo `GRD_` de las capas ni la extensión `.grd.json` (ya se
  renombraron una vez en ADR-016; una segunda ruptura no la paga nadie).
- ❌ Meter la marca en nada que el usuario vea: rótulo, título, mensaje, filtro
  de diálogo, nombre de fichero propuesto o texto de la guía (§12).
- ❌ Cambiar una constante del método "porque queda mejor" sin cita.
- ❌ Dar por bueno un cambio geométrico sin medirlo en QGIS.

---

## 11. Cuando no estés seguro

Pregunta. En concreto, **para siempre** y pregunta si:

- el cambio toca una ecuación del método y no encuentras la cita;
- la corrección solo la puedes justificar con el caso de prueba actual;
- hay que romper compatibilidad de proyectos o de nombres de capa;
- el arreglo implica desactivar un test;
- el resultado "parece mejor" pero no sabes medir en qué.

---

## 12. Nota legal que debes respetar

*GeoFluv™* y *Natural Regrade®* son marcas de sus titulares (N. Bugosh /
Carlson Software). Este proyecto es una **implementación independiente y
libre del método publicado**, no un derivado de su software, y no está
afiliado ni respaldado por ellos. En texto público (README, metadata, interfaz,
mensajes) usa siempre la forma *"método fluvio-geomórfico (tipo Natural
Regrade)"* citando la fuente, y **nunca** presentes el complemento como
"GeoFluv" a secas ni como compatible u oficial.

**Desde ADR-016 la marca no aparece en NADA de cara al usuario**: ni en el
prefijo de capa (`GRD_`), ni en la extensión del proyecto (`.grd.json`) o de los
ajustes (`.grd-settings.json`), ni en el formato por defecto del *Report
Formatter* (`STANDARD`), ni en los nombres que se proponen al exportar, ni en la
clave de QSettings (`GeomorphicReclamation/…`). Solo sobreviven **identificadores
internos** que no se muestran en ninguna parte (`GeoFluvBuilder`,
`GeoFluvProject`, `GeoFluvDock`, `GeoFluvQPlugin`): renombrarlos sería ruido sin
beneficio, pero tampoco los propagues a código nuevo.

Los comentarios y docstrings **sí** nombran la marca cuando citan el método o
miden contra la salida del programa original. Eso no es presentarse como el
producto, es atribuir la fuente, y es obligatorio (regla de oro nº 1).

**Esto ya se incumplió una vez y costó una revisión entera**: hasta ADR-015 el
menú se llamaba *Natural Regrade* y media interfaz decía *GeoFluv*. Antes de
añadir un rótulo, un título de ventana, un mensaje o un texto de guía,
comprueba que no mete la marca. Los comentarios y docstrings que **citan** el
método o miden contra la salida del original sí pueden nombrarla: citar la
fuente con atribución es obligatorio (regla de oro nº 1), presentarse como el
producto no.

Toda contribución entra bajo **AGPL-3.0-or-later** y requiere firmar el
`CLA.md`, que otorga a Samuel Sáez López los derechos necesarios para
ofrecer el proyecto también bajo licencia comercial en el futuro. No aceptes
ni integres código de terceros sin CLA, ni código copiado de un producto
propietario.
