# Bitácora de sesiones

Una entrada por sesión de trabajo, lo más reciente arriba. **Añade la tuya al
terminar.** Plantilla al final.

---

## 2026-08-07 · Revisión previa a la publicación en GitHub

**Versión**: 1.0.17 (sin cambios de motor; solo rótulos y documentación)

**Qué se hizo.** Revisión completa del repositorio antes de hacerlo público y de
enviarlo a `plugins.qgis.org`.

- 🔴 **La marca ajena seguía entera en la interfaz** (→ ADR-015). ADR-014 había
  renombrado el paquete y el repositorio, pero nadie había mirado lo que ve el
  usuario: menú `Natural &Regrade`, seis comandos *GeoFluv …*, panel `GeoFluvQ
  ver.X`, grupo de capas `GeoFluv <proyecto>`, guía *GeoFluvQ — Natural
  Regrade*. Justo lo que el §12 prohíbe y lo que revisa el repositorio oficial
  de QGIS. 119 líneas en 20 ficheros + guía regenerada.
- **Datos del caso de trabajo fuera de `context/` y del CHANGELOG**: había
  **coordenadas UTM reales** del emplazamiento (B-007, en dos sitios), el nombre
  del proyecto QGIS y el del grupo de capas de referencia. Sustituidos por
  descripciones sin georreferencia. Las cotas y las longitudes se quedan: son la
  tabla de referencia y no identifican nada por sí solas.
- **Rutas de la máquina** (`%USERPROFILE%\…`, `<ruta de trabajo>\…`) → `%APPDATA%` y
  redacción genérica, en `AGENTS.md`, `docs/BUILD.md`, `docs/DESARROLLO.md` y
  `context/07`.
- 🔴 **`SECURITY.md` decía lo que no era.** Afirmaba que el complemento habla
  «solo con localhost» y que «no sale ningún dato de tu máquina», pero
  `ai_client.buscar_web()` consulta DuckDuckGo. Es *opt-in* y está desactivada
  por defecto, así que el fallo era de documentación, no de código — pero en un
  documento de seguridad eso es exactamente lo que no puede fallar. Corregido
  también en `docs/ARQUITECTURA.md` y en los dos README.
- URLs del repositorio → `github.com/samuelsl27/…` (cuenta personal; no existe
  la organización `opengeorock` en GitHub). Los enlaces a `opengeorock.org` y la
  autoría del equipo se mantienen.
- `.gitignore`: `*.pdf` y `*.docx` globales, no solo bajo `docs/metodo/`.

**Medido.** `ruff check .` limpio y **84 tests en verde** después del
renombrado: ningún test dependía de los rótulos. El zip se construye y verifica.

**Comprobado y limpio.** Historia de git (un solo autor, ningún fichero de datos
ha existido nunca en el árbol), `.gitignore`, `build_zip.py`, workflows de
GitHub sin secretos, `.claude/settings.local.json` correctamente ignorado.

**Lección.** Un renombrado «por marca» que solo toca el nombre del paquete deja
el riesgo intacto: lo que se juzga es lo que se ve. Cuando una decisión sea de
naming, la lista de sitios a revisar es *menú, botones, títulos de ventana,
mensajes, informes, guía y nombres de grupo de capas*, no `metadata.txt`.

**Pendiente**: decidir si la primera publicación sale con `experimental=True`
(ahora sí lo está) y escribir `scripts/comparar_original.py` (P-12).

---

## 2026-08-07 · Reparar el MCP de QGIS y el arranque del entorno

**Versión**: 1.0.17 (sin cambios de motor; nada de `src/` tocado)

**Qué se hizo.**

- 🔴 **El MCP llevaba tiempo sin funcionar y no era evidente.** `.mcp.json` y
  `.vscode/mcp.json` describían `jjsantos01/qgis_mcp` en una ruta local
  **inexistente**, mientras que el complemento instalado en QGIS ya era
  **QGIS MCP** de `nkarasiak/qgis-mcp`. Configuración y realidad hablaban de
  proyectos distintos, así que el editor se quedaba sin herramientas y la única
  forma seria de validar geometría estaba muerta sin que saltara ningún aviso.
- Servidor reconfigurado a `uvx --from <etiqueta de GitHub> qgis-mcp-server`:
  **sin clonar y sin rutas de una máquina concreta**, para que el fichero, que
  va al repositorio, sirva tal cual a cualquiera que lo clone.
- **Versión fijada a una etiqueta, no a `main`.** Complemento y servidor se
  actualizan por sitios distintos y se desincronizan solos.
  `scripts/configurar_mcp.py` reescrito: lee la versión del complemento
  instalado, fija esa misma, hace un `ping` real por el socket (no basta con que
  el puerto acepte: otra cosa puede estar ocupándolo) y avisa si hay perfiles
  con versiones distintas.
- **Trampa 2 verificada como resuelta** (ver abajo).

**Medido.** Arrancando el servidor desde el propio `.vscode/mcp.json`:
118 herramientas, `ping` → `{"pong": true}`, `get_qgis_info` → QGIS
4.2.0-Belém do Pará, perfil `QGIS4/profiles/default`, con el proyecto de
prueba cargado.

**Trampa 2 (`execute_code` devolvía la salida de la llamada anterior): muerta.**
Tres marcas seguidas devolvieron cada una la suya, por el socket directo y por
la ruta completa cliente MCP → servidor → socket. La respuesta trae ahora
`stdout` y `stderr` separados. El ritual del `print("MARCA-n")` ya no hace
falta. Documentado como resuelto —no borrado— en `context/07`.

**Lección.** Una configuración rota no falla ruidosamente: simplemente no
aparecen las herramientas, y se acaba trabajando «a ojo» sin darse cuenta de que
se ha perdido el instrumento de medida. Es el mismo patrón que B-019 (el
`except` mudo) en otra capa: **el fallo silencioso es el caro**.

**Además**: `scripts/configurar_vscode.py` (nuevo) detecta las instalaciones de
QGIS de la máquina —aquí conviven 3.42.3, 3.44.6 y 4.2.0— y escribe las rutas de
Pylance, que antes había que poner a mano.

**Pendiente**: recargar la ventana de VSCode para que tome el servidor. Queda un
`qgis_mcp_plugin` v0.2.1 antiguo en el perfil `QGIS3`, inofensivo pero el guion
avisa de él cada vez.

---

## 2026-07 · Preparación del repositorio para desarrollo con IA

**Versión**: 1.0.17 (sin cambios de motor)

**Qué se hizo.**

- Reestructuración completa del proyecto como repositorio de desarrollo:
  `src/` · `scripts/` · `tests/` · `docs/` · `context/` · `.claude/` ·
  `.vscode/` · `.github/`.
- **AGENTS.md**: contrato de trabajo para agentes de IA, con 12 reglas de oro
  destiladas de todos los bugs del proyecto.
- **`context/`**: la memoria (glosario, método con citas, arquitectura,
  decisiones ADR, catálogo de bugs, invariantes, comparación con el original,
  entorno MCP, backlog, esta bitácora).
- **Renombrado** `geofluv_q` → `geomorphic_reclamation_designer`, nombre público
  *Geomorphic Reclamation Designer* (ADR-014, motivo de marca registrada).
  Barato porque todas las importaciones son relativas: solo 3 ficheros tocados.
- **Licencia AGPL-3.0-or-later + CLA** (ADR-013).
- Guiones de construcción: `build_zip.py`, `deploy_local.py`, `bump_version.py`.
- Configuración de MCP de QGIS 4.2, VSCode y GitHub Actions.
- Repositorio git inicializado con historia por versiones.

**Decisiones**: ADR-012, ADR-013, ADR-014.

**Pendiente**: publicar en GitHub (P-10), escribir
`scripts/comparar_original.py` (P-12).

---

## 2026-07 · v1.0.17 — el pie de ladera y el orden del pipeline

**Qué se hizo.**

- 🔴 **B-018**: el pie de ladera se identificaba por **cota** en dos sitios de
  `divides.py`. Donde el cauce va en relleno, el pie es el punto **más alto**.
  Corregido con `Corredor._cerca()` (distancia). Era la causa de la meseta y la
  zanja del margen oeste-sur.
- **B-017**: retirado el recurvado tras el recorte
  (`_rehacer_laderas` conservado pero desconectado, con aviso).
- **B-015**: máscara del corredor para que las curvas de nivel no crucen el
  cauce. Δz mediana en los cruces: 0.021 m.
- **B-016**: corregidas las ecuaciones de la **documentación** de
  `hydrology.py` (el código siempre estuvo bien) + `tests/test_libro.py`,
  17 tests cuyo docstring es la cita del libro.
- Marcador rojo en planta al deslizar sobre *View Longitudinal Profile*.
- Revisión completa del motor hidráulico contra los capítulos 2 y 4.

**Medidas**: subcresta idx 3: 1079.72→1062.00 (15.3 %), original
1079.08→1062.00 (12.4 %). *Check Design*: (2, 67, 56).

**Intento fallido**: quitar la monotonía (`monotona=False`) para arreglar las
zanjas. Producía zanjas en otros casos. Revertido.

**Observación sin resolver**: el pipeline pasó de ~3 s a ~15 s (→ P-04).

---

## 2026-07 · v1.0.16 — comprobaciones, divisorias y guía

**Qué se hizo.**

- **`core/checks.py`** nuevo: 22 comprobaciones C02–C52 con `Hallazgo`,
  `revisar()` y `resumen()`, y `gui/check_dialog.py` con filtros por severidad
  y grupo, filas pulsables y exportación a CSV. Errores: 13 → 9 → 2.
- **`core/divides.py`** nuevo (~1100 líneas): `Corredor`,
  `recortar_contra_corredor` por diferencia geométrica (B-010),
  `perfil_desde_control` con el orden correcto de etapas (B-014),
  `ajustar_extremo` con mezcla *smoothstep* (B-009).
- **Sillas de cresta** (libro §9.4) y **recetario del capítulo 10** metido en el
  prompt de optimización de IA.
- Retirada la heurística `limite_de_ladera = 2 × media` (B-011).
- Retirado `pendiente_max_pct` del perfil de las divisorias →
  `MAX_PENDIENTE_FILO = 100 %` (B-012).
- Conmutador de idioma de la guía arreglado (B-008).
- `MAX_ORDEN = 10`, `MAX_PASADAS = 30`.

**Medidas**: peor gradiente 2070 % → 92 %. Empalmes forzados 27 (peor 19.68 m)
→ 1 (0.09 m). Divisoria: +2.29 m sobre el lecho, igual que el original.

---

## Sesiones anteriores (resumen)

| Versión | Hito |
|---|---|
| **1.0.14** | Guía bilingüe reescrita (97 ajustes, 23 bloques). **B-007**: faltaba una cresta divisoria entera (la V de la confluencia). Detección de hoyos cerrados y picos aislados. Panel de IA que abre al instante. Mucha más información para el modelo (trazados, tablas por línea, georreferencia quemada en las imágenes) |
| **1.0.13** | Primera comparación geométrica sistemática con el original. Perfiles de crestas y vaguadas editables por la IA. Concavidad del perfil como variable. Búsqueda web conectada. Realimentación de pendientes efectivas |
| **1.0.12** | Pestaña **AI Optimization**: modelo local (Ollama / LM Studio), objetivos combinables, carpeta de trabajo por sesión (ADR-004) |
| **1.0.11** | 🔴 **B-006**: atributos desplazados en GeoPackage (`compat.attrs`). Cresta divisoria anclada en la confluencia. Curvas de nivel 3D. *Check Ridgeline Slope* como tabla enlazada |
| **1.0.10** | Comparación con el DXF original. **B-005** meandros restaurados, **B-004** vaguadas sin sobreexcavar, **B-003** divisorias como cadenas continuas. Ventana de triangulación y curvado. Recorte al perímetro. Mass Haul gráfico |
| **1.0.1 – 1.0.9** | Esqueleto, panel, ajustes, gestor de capas, proyecto JSON, Setup, hidrología, motor de canales, crestas/subcrestas/vaguadas, TIN, curvas, corte/relleno |

---

## Plantilla

```markdown
## AAAA-MM-DD · vX.Y.Z — título corto

**Qué se hizo.**
- …

**Bugs corregidos**: B-0xx (añádelos a 04_bugs_resueltos.md)
**Decisiones**: ADR-0xx (añádelas a 03_decisiones.md)

**Medidas.** (antes → después, y el valor del original si aplica)

**Intentos fallidos.** (qué se probó, por qué no funcionó — esto vale oro)

**Pendiente / nuevo en el backlog**: P-xx
```
