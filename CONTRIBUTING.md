# Cómo contribuir

Gracias por el interés. Este proyecto es pequeño y muy específico, así que las
convenciones importan más de lo normal: el motor geométrico es delicado y una
"mejora" bienintencionada puede romper invariantes que costaron meses de
depuración.

*English speakers: this file is in Spanish because that is the project's working
language, but pull requests and issues in English are perfectly welcome.*

---

## Antes de nada

1. **Lee [`AGENTS.md`](AGENTS.md).** Está escrito para agentes de IA, pero las
   12 reglas de oro valen igual para personas y explican por qué el código es
   como es.
2. **Mira [`context/04_bugs_resueltos.md`](context/04_bugs_resueltos.md).**
   Puede que lo que quieres arreglar ya se arregló, o que se intentara arreglar
   de la forma que se te está ocurriendo y no funcionara.
3. **Firma el [CLA](CLA.md).** Para cambios pequeños basta `git commit -s`.

---

## Informar de un error

Lo más útil que puedes aportar. Usa la plantilla de issue e incluye:

- **Versión** del complemento y de QGIS, y sistema operativo.
- **Qué esperabas y qué salió**, con captura si es geométrico.
- **Una medida**, no una impresión: cota, longitud, pendiente, distancia.
  «La cresta queda mal» no se puede depurar; «el extremo bajo queda 17.4 m por
  encima del cauce, debería estar a ~2 m» sí.
- **Cómo reproducirlo**: si puedes, un proyecto mínimo (límite + un par de
  fondos de valle + un DEM pequeño) que lo muestre.
- El **`.geofluv.json`** y el registro del panel, si los tienes.

Un caso reproducible vale más que diez informes vagos.

## Proponer una funcionalidad

Abre un issue **antes** de escribir código. Explica el problema real que
resuelve, y si sale del método, la **cita** de dónde sale. Si es una opción de la
interfaz, di también qué pasa al cambiarla, porque hay que documentarla en la
guía.

---

## Preparar el entorno

```bash
git clone https://github.com/opengeorock/geomorphic-reclamation-designer.git
cd geomorphic-reclamation-designer

python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

pytest -q                        # 84 tests; los que necesitan QGIS se saltan solos
python scripts/deploy_local.py   # instala en tu perfil de QGIS para probarlo
```

Detalles en [`docs/DESARROLLO.md`](docs/DESARROLLO.md).

---

## El ciclo de un cambio

```
1. LEER      context/ del área que tocas
2. REPRODUCIR  un test que falle, o una medida concreta en QGIS
3. ENTENDER  la causa raíz — no parchees el síntoma al final del pipeline
4. CAMBIAR   lo mínimo, en el módulo que corresponde
5. PROBAR    pytest -q  →  todo en verde
6. VERIFICAR en QGIS real. Mide, no mires
7. COMPARAR  contra context/06_comparacion_original.md si es geométrico
8. DOCUMENTAR context/ + CHANGELOG.md
```

### Lo que hace que un PR se acepte rápido

- **Un solo cambio con sentido.** No mezcles un renombrado masivo con lógica.
- **Un test** que falle antes y pase después.
- **La medida** en la descripción del PR: antes → después, y el valor del
  programa original si es geométrico.
- **La entrada en `context/`**: bug nuevo → `04`, decisión → `03`, tarea →
  `08`, y siempre una línea en `09`.

### Lo que hace que se rechace

- Una constante nueva sin cita del libro.
- Una corrección que solo se puede justificar con el caso de prueba de quien la
  escribe.
- Una dependencia pip nueva.
- Desactivar un test para que pase.
- Renombrar el prefijo `GF_` o la extensión `.geofluv.json`.
- Editar `src/geomorphic_reclamation_designer/help/guide.html` a mano (se genera: edita
  `scripts/guia_datos.py` y ejecuta `python scripts/genera_guia.py`).

---

## Estilo

- **Python 3.9+** (el que trae QGIS). Solo biblioteca estándar y API de QGIS/Qt.
- **Identificadores y comentarios en español**; **nombres de ajustes y de capas
  en inglés**, para que coincidan con la interfaz y con la literatura.
- **Docstrings que explican el porqué**, no el qué. El estilo de la casa es
  contar la razón física o el bug que motivó el código.
- Líneas ≤ 88 caracteres. `ruff check .` en CI. **`ruff format` no se exige**:
  reformatear el motor existente de golpe daría un diff en el que no se vería
  ningún cambio real. Si formateas algo, hazlo fichero a fichero y en un
  commit aparte.
- Compatibilidad Qt5 **y** Qt6: enums con ámbito, `exec()`, `QAction` desde
  `core/compat.py`, tipos de geometría con `compat.tipo_geom()`.
- Nada de `print()` en `src/`.

## Mensajes de commit

En español, imperativo, con ámbito, y **con la medida en el cuerpo**:

```
fix(divides): identificar el pie de ladera por distancia al cauce, no por cota

Donde el cauce va en relleno la ladera baja DESDE el cauce, así que el pie es
el punto más alto. El código cogía el extremo equivocado y anclaba el extremo
del límite a la cota de la orilla 105 m más allá.

Medido: subcresta idx 3 pasa de 1079.16→1062.00 (14.7 %) a 1079.72→1062.00
(15.3 %); el original da 1079.08→1062.00 (12.4 %).

Signed-off-by: Nombre Apellidos <correo@ejemplo.org>
```

Ámbitos: `core`, `gui`, `divides`, `ridges`, `surface`, `hydrology`, `checks`,
`ai`, `build`, `docs`, `tests`, `ctx`.
Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`.

---

## Traducciones

La guía (`scripts/guia_datos.py`) está en inglés y español. Si quieres añadir un
idioma, abre un issue primero: hay que ampliar el generador y el conmutador.

**No traduzcas los nombres de los ajustes ni de las capas.** Se mantienen en
inglés en todos los idiomas a propósito, para que coincidan letra por letra con
la interfaz del programa de referencia y con la literatura.

---

## Convivencia

Se aplica el [Código de Conducta](CODE_OF_CONDUCT.md). En resumen: trata a la
gente bien, critica el código y no a la persona, y da por supuesta la buena
intención.

## Dudas

Abre un issue con la etiqueta `question`, o escribe a samuelimga@gmail.com.
