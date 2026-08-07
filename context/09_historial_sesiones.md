# Bitácora de sesiones

Una entrada por sesión de trabajo, lo más reciente arriba. **Añade la tuya al
terminar.** Plantilla al final.

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
