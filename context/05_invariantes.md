# Invariantes del diseño

Reglas que un diseño correcto cumple **siempre**. Si un cambio rompe una de
estas, el cambio está mal, por bien que se vea el resultado en el caso de prueba.

Muchas están automatizadas en `core/checks.py` (columna «Check»). Las que no,
son responsabilidad del que toca el código.

## Geometría de las líneas

| # | Invariante | Check |
|---|---|---|
| G1 | **Un punto del terreno tiene UNA sola cota.** Las curvas de nivel no cruzan las líneas del cauce | C-cruces |
| G2 | Ninguna línea de rotura cruza a otra en planta sin coincidir en cota (tolerancia `tol_cruce_breaklines_m = 0.10 m`) | sí |
| G3 | Ninguna cresta, subcresta o vaguada entra en el corredor del cauce | sí |
| G4 | El perfil longitudinal de un canal es **monótono descendente** aguas abajo | sí |
| G5 | El perfil longitudinal de un canal es **cóncavo** (o recto), nunca convexo en su conjunto | sí |
| G6 | Ninguna línea 3D tiene un gradiente vértice a vértice > `pend_max_linea_pct` (300 %) | sí |
| G7 | Ninguna línea tiene vértices duplicados ni segmentos de longitud ~0 | sí |
| G8 | Toda cresta de ladera **llega** a su divisoria (holgura `holgura_divisoria_m = 4.5 m`) o muere en el límite | sí |
| G9 | Toda línea que muere en el límite **empalma con el DEM** en ese punto, con mezcla, sin escalón | sí |
| G10 | El extremo bajo de una divisoria queda **por encima** del lecho del cauce en la confluencia (referencia: +2.29 m) | — |
| G11 | Ningún triángulo del TIN tiene un lado > `long_max_lado_tin_m` (50 m) sin línea de rotura que lo justifique | sí |

## Topología de la red

| # | Invariante | Check |
|---|---|---|
| T1 | Todo tributario **conecta** con un canal existente | sí |
| T2 | Ningún canal cruza el límite salvo el principal en su boca | sí |
| T3 | Ningún fondo de valle cruza a otro | sí |
| T4 | De cada confluencia salen **DOS** crestas divisorias aguas arriba, no una | — |
| T5 | El caudal es **creciente aguas abajo** en toda la red | sí |
| T6 | Los nombres siguen la convención R/L mirando aguas abajo, sin duplicados | — |
| T7 | Las subcuencas cubren el límite sin solaparse | — |

## Hidráulica

| # | Invariante | Check |
|---|---|---|
| H1 | `τ ≤ τ_crit` (Shields) en toda estación, o se marca error | sí |
| H2 | `W_fp ≥ W_bkf` — la sección de avenida contiene a la formadora | sí |
| H3 | `b = W − 2·z·d > 0` — el ancho de fondo es positivo | sí |
| H4 | `Q_fp > Q_bkf` en toda estación | sí |
| H5 | `v_n` (Manning) dentro de `[0.4·v_max, v_max]`, o se avisa | sí |
| H6 | `W:D < 10` y sinuosidad `< 1.2` si `S > 4 %`; al revés si `S < 4 %` | sí |
| H7 | La pendiente de la boca introducida por el usuario **manda**; si se recorta por monotonía, se **informa** (`perfiles_efectivos`) | — |

## Superficie

| # | Invariante | Check |
|---|---|---|
| S1 | **No hay hoyos cerrados**: ninguna celda tiene sus 8 vecinas más altas (el agua no podría salir) | sí |
| S2 | No hay picos aislados | sí |
| S3 | Fuera del límite, la superficie es **NoData** | sí |
| S4 | Toda ladera **vierte** a un cauce o a una vaguada | sí |
| S5 | El ángulo entre vaguada y ladera no supera `ang_max_valle_ladera_deg` (60°) | sí |
| S6 | La densidad de drenaje resultante está dentro del objetivo ± varianza | sí |
| S7 | El balance corte/relleno está dentro de la varianza admisible | sí |

## Invariantes del código (no del diseño)

| # | Invariante |
|---|---|
| C1 | `core/*` **no importa** `gui/*` |
| C2 | `hydrology.py` **no importa** `qgis.*` |
| C3 | Ninguna dependencia pip nueva en `src/` |
| C4 | Los atributos se rellenan **por nombre de campo** (`compat.attrs`) |
| C5 | Toda diferencia de versión de QGIS/Qt pasa por `core/compat.py` |
| C6 | Ningún `print()` en `src/` |
| C7 | La versión coincide en `metadata.txt`, `__init__.py`, `dock.VERSION` y `genera_guia.VER` |
| C8 | `checks.py` no modifica ninguna capa |
| C9 | `divides._rehacer_laderas()` **no se llama desde ningún sitio** |
| C10 | Todo campo nuevo del proyecto se lee con `d.get(clave, defecto)` |

## Cómo se comprueban

```bash
pytest -q                                   # C1–C10 + G/H de laboratorio
```

En QGIS, con el diseño generado: botón **Check Design (Error Log)**, o desde el
MCP:

```python
from geomorphic_reclamation_designer.core import checks
hallazgos = checks.revisar(proyecto, ajustes)
print(checks.resumen(hallazgos))            # (errores, avisos, informativos)
```

**Estado de referencia del caso de prueba (v1.0.17):** `(2, 67, 56)` — los 2
errores son de tensión tractiva (H1) y están en el backlog, ver
`context/08_pendiente.md`.
