# Arquitectura

## Vista de conjunto

```
                        ┌──────────────────────────┐
   USUARIO (QGIS)  ───► │  gui/dock.py             │  panel acoplable, 5 pestañas
                        │  Setup │ Channels │      │
                        │  Output │ DWG │ AI       │
                        └───────────┬──────────────┘
                                    │ (gui → core, NUNCA al revés)
    ┌───────────────────────────────┼───────────────────────────────┐
    ▼                               ▼                               ▼
┌─────────┐                  ┌─────────────┐                 ┌─────────────┐
│ params  │◄─────────────────│  builder    │────────────────►│  surface    │
│ project │                  │ (orquesta)  │                 │ TIN/curvas/ │
└─────────┘                  └──────┬──────┘                 │ corte-relleno│
                                    │                        └─────────────┘
        ┌───────────┬───────────────┼──────────────┬──────────────┐
        ▼           ▼               ▼              ▼              ▼
   hydrology    profile         planform       ridges       layer_manager
   (Q, τ, λ)   (perfil Z)      (traza XY)    (crestas)      (capas/grupos)
                                                 │
                                    ┌────────────┼────────────┐
                                    ▼            ▼            ▼
                               hillslopes     divides     topology
                              (subcrestas,  (recorte y   (empalmes y
                               vaguadas)     cota)        sellado)
                                    │
                                    ▼
                                 checks  (Error Log — solo lee)
```

## Flujo de datos, fase por fase

### Fase 1 — Setup (`setup_tools.py`)

**Entradas del usuario** (capas de `01 Entradas`):

| Capa | Tipo | Qué es |
|---|---|---|
| `GF_Boundary` | Polígono | Límite del área a rehabilitar |
| `GF_ValleyBottoms` | Línea 2D | Fondos de valle aproximados, patrón dendrítico |
| DEM | Ráster | Terreno de partida |

**Salidas**: área, cotas, longitud de valle, **densidad de drenaje con
semáforo**, punto de transición (automático desde el DEM o manual).

Validaciones: `validar_limite`, `validar_canal_principal`, `validar_tributario`
(un tributario debe conectar con un canal existente, no cruzar el límite ni
otros valles), `orientar_aguas_abajo`.

### Fase 2 — Canales (`builder.py`)

Para cada canal, `GeoFluvBuilder`:

1. **Hidrología** (`hydrology`): subcuenca → `Qpk` racional bankfull y
   flood-prone → sección trapecial → τ, Manning, Froude.
2. **Perfil longitudinal** (`profile`): cóncavo, Hermite monótono, empalme de
   cota **y pendiente** en las confluencias.
3. **Planta** (`planform`): meandro sinusoidal con λ y cinturón ligados al
   caudal bankfull, o zigzag tipo A si S > 4 % aguas arriba de la transición.
   Amplitud resuelta para la sinuosidad objetivo. Bordes paralelos en 3D.
4. **Nombres** (`naming`): R1 / L1 / R1L1 según margen mirando aguas abajo.

**Capas generadas** (`02 Diseño`): `GF_Channels` (eje 3D), `GF_Banks`,
`GF_XSections` (un punto por estación con toda la hidráulica como atributos).

### Fase 3 — Relieve de ladera

Orden **estricto**, cada etapa sobre el resultado de la anterior:

```
ridges.generar_subcuencas       Voronoi de los ejes → subcuencas reales
ridges.generar_crestas          divisorias, partidas en las confluencias,
                                suavizadas, con perfil de cresta
hillslopes.generar_subcrestas   subcrestas en ápices de meandro + vaguadas
divides.ajustar_divisorias      1 RECORTE contra el corredor
                                2 cotas de la divisoria
                                3a corte en divisorias
                                3b enganche de cabeceras
                                3c empalme con el límite
topology.*                      empalmes, crestas de encuentro, sellado,
                                fusión con divisorias (bucle de convergencia)
```

> **El orden ES el algoritmo.** Ver reglas de oro 4 y 6 en `AGENTS.md` y los
> bugs B-014 y B-017.

**Capas** (`02 Diseño`): `GF_Ridges`, `GF_SubRidges`, `GF_Swales`.

### Fase 4 — Superficie (`surface.py`)

```
líneas 3D (ejes, bordes, crestas, subcrestas, vaguadas)  ─┐
puntos del límite con cota del terreno                   ─┤► QgsTinInterpolator
                                                          ┘
   → ráster de diseño (celda automática, ligada a la anchura mediana bankfull)
   → suavizado con máscara que PROTEGE el corredor del cauce
   → recorte al límite (fuera, NoData)
   → gdal:contour → GF_Contours (LineStringZ, con maestras)
   → corte/relleno dentro del límite + esponjamiento/compactación
   → GF_HaulRegions (polígonos) y GF_HaulRoutes (acarreos optimizados)
```

### Fase 5 — Revisión (`checks.py`)

22 comprobaciones **C02–C52**, agrupadas en: Entradas · Trazado · Líneas de
rotura/TIN · Pendientes · Hidráulica · Superficie/volúmenes. Devuelve
`Hallazgo`s con severidad, grupo y geometría; la ventana (`gui/check_dialog.py`)
permite filtrar, pulsar una fila para hacer zoom a la entidad y exportar a CSV.

**`checks.py` solo LEE.** No corrige nada.

### Fase 6 — Optimización con IA (opcional, `ai_*.py`)

El bucle lo lleva el complemento, no el modelo:

```
motor GeoFluv regenera el diseño   →  volúmenes en local (exactos, rápidos)
        ▲                                       │
        │                                       ▼
   validar contra rangos  ◄── JSON ──  modelo local (Ollama / LM Studio)
                                        recibe números, historial e imágenes
```

Toda solución es **geométricamente válida por construcción**: el modelo solo
sugiere qué variables mover. Sin modelo, el mismo bucle funciona en modo
numérico. Ver `core/ai_context.py` (`MEMORIA`, 7 secciones) y
`core/ai_optimizer.py`.

## Árbol de capas de QGIS

```
GeoFluv <proyecto>
├── 01 Entradas   GF_Boundary · GF_ValleyBottoms · DEM
├── 02 Diseño     GF_Channels · GF_Banks · GF_XSections
│                 GF_Ridges · GF_SubRidges · GF_Swales
├── 03 Salida     GF_DesignSurface · GF_Contours · GF_SubWatersheds
└── 04 Análisis   GF_CutFill (m) · GF_HaulRegions · GF_HaulRoutes
```

Almacenamiento a elegir al crear las capas: **memoria**, una carpeta elegida, o
una carpeta nueva junto al proyecto QGIS con nombre + fecha y hora
(`layer_manager.carpeta_unica_proyecto`).

> El prefijo `GF_` y la extensión `.geofluv.json` **se conservan por
> compatibilidad**. No los renombres (regla de oro 9).

## Ciclo de edición del usuario

Es lo que hace especial a este complemento: **cada fase es re-entrante**.

```
Setup → Añadir canales → «Generar / actualizar diseño de canales»
  → «Dibujar superficie de diseño» (crestas + TIN + curvas)
  → «Actualizar corte/relleno»
  → si está fuera de rango:
        edita crestas o vaguadas a mano en QGIS,
        o «Perfil longitudinal automático»,
        o cambia cotas y ajustes de canal
  → «Dibujar curvas de nivel GeoFluv»  (re-TIN, sin regenerar canales)
  → «Releer fondos de valle»           (regenera TODO desde las geometrías)
  → repetir hasta densidad de drenaje y balance en verde
  → «Centroides de corte/relleno» para planificar el movimiento de tierras
```

El proyecto `.geofluv.json` guarda **referencias** a las geometrías, no copias:
si el usuario edita una capa, el diseño se actualiza al regenerar.

## Reglas de dependencia

```
compat        ← todo el mundo
params        ← project ← builder
hydrology     → nada del proyecto (Python puro, testeable aislado)
profile,
planform      → hydrology
builder       → profile, planform, hydrology, params, naming
ridges        → salida de builder, params
hillslopes,
divides,
topology      → ridges, params
surface       → capas ya creadas
checks        → lee capas; NO escribe
ai_*          → ai_client → (HTTP local); ai_optimizer → builder + surface
gui/*         → core/*                    ← NUNCA core/* → gui/*
```

`hydrology.py` es **Python puro sin QGIS** a propósito: se puede testear
aislado y es donde vive la parte del método que hay que poder verificar contra
el libro sin arrancar un SIG.

## Compatibilidad QGIS 3.22 ↔ 4.x

Todo lo que depende de la versión pasa por `core/compat.py`:

| Diferencia | Cómo se resuelve |
|---|---|
| Enums Qt con/sin ámbito | Se escribe siempre con ámbito (`Qt.CursorShape.WaitCursor`) |
| `QAction` en QtGui (Qt6) vs QtWidgets (Qt5) | `from .core.compat import QAction` |
| `exec()` vs `exec_()` | Siempre `exec()` |
| Campos `QMetaType` (≥3.38) vs `QVariant` | `compat._tipos_campo` |
| Comparar tipos de geometría | `compat.tipo_geom()` (los enums PyQt6 no comparan con `int`) |
| Formato de *identify* de ráster | `compat.formato_identify_valor` |
| Filtros de `QgsMapLayerComboBox` | `compat.filtro_capas_*` |
| Niveles de `messageBar` | `compat.nivel_msg` |
| Enums del interpolador TIN | resueltos con respaldos |
| Campo `fid` que añade GPKG | `compat.attrs()` — **por nombre, nunca por posición** |
