# Cómo continuar el desarrollo

Guía práctica para trabajar desde **VSCode**, con o sin asistente de IA. Léela
una vez entera; después basta con volver a la sección que necesites.

---

## 1. Montar el entorno (una sola vez)

### 1.1 Qué carpeta abrir en VSCode

**Abre la carpeta del repositorio, no la carpeta que la contiene.**

```bash
git clone https://github.com/samuelsl27/geomorphic-reclamation-designer.git
cd geomorphic-reclamation-designer
code .
```

**Por qué importa.** Casi todo lo que hace cómodo este repositorio se activa
solo cuando **la raíz del espacio de trabajo es la raíz del repositorio**:

| Fichero | Solo funciona si el repositorio es la raíz |
|---|---|
| `.vscode/settings.json` | rutas de Pylance, pytest, estilo |
| `.vscode/tasks.json` | las tareas de desplegar, construir y testear |
| `.mcp.json` | el servidor MCP de QGIS |
| `AGENTS.md` / `CLAUDE.md` | el asistente los carga por estar en la raíz |
| `.git` | los comandos de git van sobre el repositorio |

Si abres la carpeta padre, VSCode no aplica la configuración de la subcarpeta,
el terminal arranca en el sitio equivocado y el asistente no encuentra
`AGENTS.md`. Se puede trabajar, pero peleando.

### 1.1 bis · Documentación de referencia con copyright

El libro y los manuales del método **no están en el repositorio y no deben
entrar**: tienen copyright y no son nuestros para redistribuir. Guárdalos
**fuera** del árbol del repositorio; así git ni los ve, que es la situación
segura. Si necesitas tenerlos a la vista en la misma ventana de VSCode, usa un
espacio de trabajo de varias raíces con el repositorio como **primera raíz**
(así toda la configuración de arriba sigue funcionando) y las carpetas de
consulta añadidas aparte y excluidas de la búsqueda.

El `.gitignore` cubre además `*.pdf`, `*.docx` y las extensiones de datos
(`*.tif`, `*.dxf`, `*.gpkg`, `*.grd.json`…) por si acaso.

### 1.2 Extensiones de VSCode

Al abrir la carpeta, VSCode ofrecerá instalar las recomendadas
(`.vscode/extensions.json`): Python, Pylance, debugpy, Ruff, Claude Code,
GitLens, markdownlint, EditorConfig. Acepta.

### 1.3 Entorno de Python para las herramientas

Este entorno es **solo para tests y linters**. El complemento se ejecuta dentro
del Python de QGIS, no en este.

```bash
python -m venv .venv
.venv\Scripts\activate          # Linux/Mac: source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

Deberías ver los 84 tests (los que necesitan QGIS se saltan solos).

### 1.4 Que Pylance entienda `qgis.*`

```bash
python scripts/configurar_vscode.py
```

Busca las instalaciones de QGIS, elige **la más nueva**, te dice cuál ha elegido
y escribe las rutas correctas en `.vscode/settings.json` (intérprete,
`apps/qgis/python`, sus `plugins` y el `site-packages` de la versión de Python
que traiga esa instalación).

Después: `Ctrl+Shift+P → Developer: Reload Window`.

> **En esta máquina hay tres QGIS instalados** — 3.42.3, 3.44.6 y **4.2.0** —,
> así que comprueba que la que elige es con la que trabajas. Si no:
>
> ```bash
> python scripts/configurar_vscode.py --listar
> python scripts/configurar_vscode.py --qgis "C:\Program Files\QGIS 3.44.6"
> ```

Sin esto, Pylance subraya en rojo todos los `from qgis.core import …`. Es
**cosmético** —no impide ejecutar nada— pero convierte el editor en un árbol de
Navidad y acabas ignorando también los avisos que sí importan.

### 1.5 MCP de QGIS

```bash
python scripts/configurar_mcp.py
```

Detecta el complemento `qgis_mcp_plugin` y el servidor, y escribe `.mcp.json` y
`.vscode/mcp.json`. Detalles y solución de problemas en
[`MCP_QGIS.md`](MCP_QGIS.md).

---

## 2. El ciclo de trabajo diario

```
┌─ editar en VSCode ──────────────────────────────────────┐
│  src/geomorphic_reclamation_designer/core/...                            │
└────────────────────┬────────────────────────────────────┘
                     ▼
   python scripts/deploy_local.py        (o la tarea «Instalar en QGIS»)
                     ▼
   en QGIS: reloadPlugin("geomorphic_reclamation_designer")
            (si tocaste params.py → REINICIA QGIS)
                     ▼
   regenerar el diseño y MEDIR
                     ▼
   pytest -q  →  commit  →  actualizar context/
```

**Atajos de VSCode** (Ctrl+Shift+P → *Run Task*, o Ctrl+Shift+B para la de
compilación por defecto):

| Tarea | Qué hace |
|---|---|
| **Instalar en QGIS (deploy)** | Copia al perfil. Es la de por defecto: `Ctrl+Shift+B` |
| **Instalar en QGIS y vigilar** | Igual, pero recopia cada vez que guardas |
| **Generar ZIP instalable** | Guía + comprobaciones + zip |
| **Tests** | `pytest -q` |
| **Tests del libro** | Solo las ecuaciones, en modo verboso |
| **Lint (ruff)** | Estilo |
| **Subir version** | Te pregunta patch/minor/major |
| **TODO: publicar version** | Encadena guía → lint → tests → zip |

### Iteración rápida

Deja corriendo la tarea *«Instalar en QGIS y vigilar»* en una terminal. Cada vez
que guardes, el complemento se recopia solo. En QGIS solo tienes que recargar.

---

## 3. Antes de tocar el motor geométrico

**Esto es lo importante de toda la guía.** El motor es delicado: casi todos los
bugs graves del proyecto han venido de "mejoras" razonables que rompían un
invariante.

1. **Lee [`context/04_bugs_resueltos.md`](../context/04_bugs_resueltos.md)**, en
   particular la sección final *«Patrones que se repiten»*. Es muy probable que
   lo que vas a arreglar ya se arreglara, o que la forma que se te está
   ocurriendo ya se probara y fallara.
2. **Consulta [`context/05_invariantes.md`](../context/05_invariantes.md)** y di
   en voz alta cuál se está rompiendo. Si no puedes nombrarlo, todavía no sabes
   cuál es el problema.
3. **Reproduce con una medida**, no con una impresión.
4. **Cambia lo mínimo**, en el módulo que corresponde.
5. **Mide en QGIS** y compara con
   [`context/06_comparacion_original.md`](../context/06_comparacion_original.md).

Las cinco causas de casi todos los problemas geométricos de este proyecto:

| # | Causa | Bug |
|---|---|---|
| 1 | Identificar un extremo por su **cota** en vez de por distancia al cauce | B-018 |
| 2 | Corregir el **último vértice** en vez de mezclar la corrección | B-009 |
| 3 | **Recurvar después de recortar** | B-017 |
| 4 | **Orden equivocado** de las etapas del perfil | B-014 |
| 5 | Recorrer **desde los extremos** en vez de usar geometría de conjuntos | B-010 |

---

## 4. Trabajar con un asistente de IA

El repositorio está preparado para esto. La pieza central es
**[`AGENTS.md`](../AGENTS.md)**: el contrato de trabajo, con 12 reglas de oro
destiladas de todos los bugs del proyecto. Lo leen Claude Code, Codex, Cursor y
Copilot (`CLAUDE.md` apunta a él, así que hay **una sola fuente de verdad**).

### Cómo empezar una sesión

Con Claude Code, en la terminal integrada de VSCode:

```
claude
```

y como primer mensaje:

```
/contexto arreglar las colas verticales de las subcrestas en la zona norte
```

El comando `/contexto` obliga al asistente a leer `AGENTS.md`, el catálogo de
bugs y el backlog **antes** de tocar nada, y a resumirte el estado. Eso solo ya
evita la mitad de los problemas.

### Comandos disponibles (`.claude/commands/`)

| Comando | Para qué |
|---|---|
| `/contexto <tarea>` | Cargar la memoria del proyecto antes de empezar. **Empieza siempre por aquí** |
| `/qgis-probar <qué>` | Instalar en QGIS y **medir** el cambio vía MCP |
| `/comparar-original <qué>` | Comparar contra la salida del programa original |
| `/revisar-libro <área>` | Contrastar ecuaciones y constantes contra las citas |
| `/build` | Generar el zip con todas las comprobaciones |
| `/nueva-version <x.y.z>` | Cerrar una versión: número, changelog, tests, zip, tag |
| `/cerrar-sesion` | **Volcar a `context/` lo aprendido.** No te lo saltes |

### Subagentes (`.claude/agents/`)

Se invocan solos cuando la tarea encaja, o a mano (*«usa el subagente
geometria»*):

- **`geometria`** — crestas, divisorias, laderas, perfiles, recortes.
- **`hidraulica`** — caudales, secciones, Manning, Shields, meandros. Conoce las
  ecuaciones y sus citas de memoria.
- **`qgis-tester`** — instala y **mide** vía MCP. No opina: mide.

### La regla que hace que esto funcione

**Termina siempre con `/cerrar-sesion`.** Vuelca a `context/` lo que has
aprendido: bugs con causa raíz, decisiones, medidas y —muy importante— los
**intentos fallidos**. Saber que algo se probó y no funcionó vale tanto como la
solución, y es lo que un asistente no puede deducir del código.

Sin ese paso, la siguiente sesión empieza de cero y se repiten los mismos
errores. Con él, arranca sabiendo dónde está el proyecto.

---

## 5. Añadir un ajuste nuevo

Un ajuste toca cinco sitios. Si te dejas alguno, la sensación es de que "no hace
nada":

1. **`core/params.py`** — el campo en `GlobalSettings` o en `ChannelSettings`,
   con su valor por defecto. Léelo siempre con `d.get(clave, defecto)` para no
   romper proyectos antiguos.
2. **`gui/settings_dialog.py`** o **`gui/channel_dialog.py`** — el control, con
   su rango y sus unidades. El nombre visible **en inglés**.
3. **El motor** — donde se usa de verdad.
4. **`scripts/guia_datos.py`** — la documentación bilingüe, explicando **qué
   pasa al subirlo o bajarlo**. Después `python scripts/genera_guia.py`.
5. **`core/ai_context.py`** — si el optimizador puede moverlo, su rango
   permitido.

Y un test en `tests/`. Si el ajuste sale del método, añádelo a
`context/01_metodo_geofluv.md` **con su cita**.

> ⚠️ Después de tocar `params.py`, **reinicia QGIS**. La recarga en caliente deja
> `GlobalSettings` viejo en memoria y salta un `AttributeError` que parece un bug
> de otra cosa.

---

## 6. Publicar una versión

```bash
python scripts/bump_version.py patch      # o minor / major / 1.0.18
# ... redacta CHANGELOG.md y actualiza context/ ...
python scripts/genera_guia.py
ruff check . && pytest -q
python scripts/build_zip.py
git add -A && git commit -m "chore: versión 1.0.18"
git tag -a v1.0.18 -m "v1.0.18"
git push && git push --tags
```

El `push` de la etiqueta dispara `.github/workflows/release.yml`, que vuelve a
pasar los tests, construye el zip y **publica la release en GitHub con el zip
adjunto y las notas sacadas del CHANGELOG**.

O, con el asistente: `/nueva-version 1.0.18`, que hace todo lo anterior.

---

## 7. Subir a GitHub (la primera vez)

El repositorio local ya está inicializado, con historia y todo confirmado.

1. **Crea el repositorio vacío** en GitHub —sin README, sin licencia, sin
   `.gitignore`— con el nombre `geomorphic-reclamation-designer`.
2. Conéctalo y sube:

   ```bash
   git remote add origin https://github.com/<usuario>/geomorphic-reclamation-designer.git
   git branch -M main
   git push -u origin main
   git push --tags
   ```

3. En **Settings → General**: activa *Issues* y *Discussions*.
4. En **Settings → Actions → General**: permite las Actions (vienen ya en
   `.github/workflows/`).
5. En **Settings → Branches**: protege `main` (requiere PR y que pase CI). Si
   vas a trabajar solo, puedes dejarlo para más adelante.
6. Rellena la descripción y los *topics* del repositorio:
   `qgis` `qgis-plugin` `mining` `reclamation` `geomorphology` `hydrology`
   `landform-design` `python`.
7. Cuando esté publicado, **actualiza las URLs**: en `metadata.txt`
   (`repository`, `tracker`), en `pyproject.toml` y en los enlaces del final del
   `CHANGELOG.md`. Ahora apuntan a `opengeorock/…`; ponlas donde lo hayas
   subido de verdad.

> **Antes del primer `push`**, comprueba que no se cuela nada que no debe:
> `git ls-files | findstr /i "pdf tif dxf gpkg grd.json"` no debe devolver
> nada. El `.gitignore` ya excluye los PDF del método (tienen copyright), los
> datos de proyecto y los rásteres.

---

## 8. Estructura, en una tabla

| Carpeta | Qué es | ¿Va en el zip? |
|---|---|---|
| `src/geomorphic_reclamation_designer/` | **El complemento** | ✅ sí, todo |
| `scripts/` | Herramientas de desarrollo | ❌ |
| `tests/` | pytest | ❌ (antes iban dentro: son 40 KB menos) |
| `context/` | Memoria del proyecto | ❌ |
| `docs/` | Documentación | ❌ |
| `.claude/`, `.vscode/`, `.github/` | Configuración | ❌ |
| `dist/` | Los zips generados | — (no se versiona) |

`build_zip.py` sabe exactamente qué excluir, y **verifica** que el zip tenga una
sola carpeta raíz `geomorphic_reclamation_designer/` y ningún `__pycache__`. Un zip con dos
carpetas raíz QGIS lo instala mal y el error que da no dice por qué.

---

## 9. Preguntas frecuentes

**¿Por qué las capas se llaman `GRD_*` y antes eran `GF_*`?**
`GRD` es *Geomorphic Reclamation Designer*. `GF` venía de *GeoFluv*, que es una
marca registrada, y no pintaba nada en algo que el usuario ve en su panel de
capas. Se renombró en ADR-016 aceptando la ruptura, que era el momento de
pagarla.

**Tenía `geofluv_q` instalado, ¿qué hago?**
Desinstálalo desde el gestor de complementos: para QGIS son dos complementos
distintos y tendrías dos botones. Renombra tus `.geofluv.json` a `.grd.json`
(mismo contenido) y vuelve a generar las capas.

**Pylance me subraya todos los `import qgis` en rojo.**
Ajusta `python.analysis.extraPaths` en `.vscode/settings.json` a tu instalación
(§1.4). Es cosmético: no afecta a la ejecución.

**He cambiado algo y QGIS no se entera.**
Por orden: (1) ¿copiaste con `deploy_local.py`? (2) ¿al perfil correcto? En QGIS,
`from qgis.core import QgsApplication; print(QgsApplication.qgisSettingsDirPath())`.
(3) ¿recargaste el complemento? (4) ¿tocaste `params.py`? Entonces reinicia QGIS.

**El pipeline va lento de repente.**
Mira qué capas hay cargadas. Un ráster de diseño fino en el lienzo basta para
pasar de 3 a 15 segundos. Descarta eso antes de buscar una regresión.

**¿Puedo usar otro asistente que no sea Claude Code?**
Sí. `AGENTS.md` es el estándar que leen Codex, Cursor y Copilot. Lo específico de
Claude Code son los comandos y subagentes de `.claude/`; el contrato es común.
