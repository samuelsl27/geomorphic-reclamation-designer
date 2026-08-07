# Arquitectura

Documento de referencia para humanos. La versión operativa, con las reglas de
dependencia y las trampas, está en
[`../context/02_arquitectura.md`](../context/02_arquitectura.md) — si vas a
tocar código, lee esa.

---

## Idea de conjunto

El complemento es una **tubería de etapas**, cada una de las cuales produce capas
de QGIS que la siguiente consume. Lo que lo hace distinto de un generador de un
solo golpe es que **el usuario puede intervenir entre etapas**: editar una
cresta a mano, mover un fondo de valle, cambiar la cota de una boca, y volver a
lanzar desde ahí.

```
                 ENTRADAS                          (01 Entradas)
    GF_Boundary · GF_ValleyBottoms · DEM
                     │
             ┌───────┴────────┐
             │  setup_tools   │  validaciones, transición, densidad de drenaje
             └───────┬────────┘
                     │
             ┌───────┴────────┐
             │    builder     │  ← hydrology · profile · planform · naming
             └───────┬────────┘
                     │             (02 Diseño)
        GF_Channels · GF_Banks · GF_XSections
                     │
             ┌───────┴────────┐
             │     ridges     │  subcuencas Voronoi + crestas divisorias
             └───────┬────────┘
             ┌───────┴────────┐
             │   hillslopes   │  subcrestas en ápices + vaguadas
             └───────┬────────┘
             ┌───────┴────────┐
             │    divides     │  RECORTE contra el corredor + cotas
             └───────┬────────┘
             ┌───────┴────────┐
             │    topology    │  empalmes, sellado, convergencia
             └───────┬────────┘
                     │
          GF_Ridges · GF_SubRidges · GF_Swales
                     │
             ┌───────┴────────┐
             │    surface     │  TIN → ráster → curvas → corte/relleno
             └───────┬────────┘
                     │             (03 Salida / 04 Análisis)
   GF_DesignSurface · GF_Contours · GF_SubWatersheds
   GF_CutFill · GF_HaulRegions · GF_HaulRoutes
                     │
             ┌───────┴────────┐
             │     checks     │  22 comprobaciones. Solo lee
             └────────────────┘
```

## Por qué está partido así

| Módulo | Razón de existir por separado |
|---|---|
| `hydrology` | Es **Python puro sin QGIS**: es la parte que hay que poder verificar contra el libro sin arrancar un SIG, y permite `pytest` en CI |
| `compat` | Toda la diferencia entre QGIS 3.22 y 4.x, y entre PyQt5 y PyQt6, vive en un solo sitio. Sin él habría `try/except` por todos lados |
| `divides` | El recorte contra el corredor y la cota de las divisorias son **el punto donde más bugs han salido**. Aislarlo permitió 31 tests dedicados |
| `topology` | Los empalmes entre líneas son un problema de grafo, no de geometría de una línea: bucle de convergencia propio |
| `checks` | Diagnóstico separado del motor. **No corrige nada**, así que se puede ejecutar en cualquier momento sin efectos |
| `ai_*` | Completamente opcional. Sin servidor de IA, el resto funciona igual |

## Lo que hay que entender del pipeline de laderas

Es la parte delicada, y su **orden es el algoritmo**:

```
1. generar          la línea completa, con su perfil (ecuación del libro)
2. recortar         contra el corredor del cauce, por diferencia geométrica
3. NO volver a curvar
```

Invertirlo o añadir un recurvado al final produce mesetas, colas verticales y
zanjas. `divides._rehacer_laderas()` existe como recordatorio de eso: está en el
código, **desconectado**, con un aviso.

Igual de importante: **el pie de una ladera se identifica por distancia al cauce,
nunca por cota**. Donde el cauce va en relleno, la ladera baja *desde* el cauce y
el pie es el punto más alto.

## Modelo de datos

No hay base de datos ni formato propio. **El estado vive en las capas de QGIS.**

- El proyecto `.geofluv.json` guarda **parámetros y referencias** a las
  geometrías de entrada, no copias. Si el usuario edita una capa, el diseño se
  actualiza al regenerar.
- Las propiedades hidráulicas viajan como **atributos** de `GF_Channels` y
  `GF_XSections`: se consultan con la herramienta *Identificar* normal de QGIS y
  se pueden usar en expresiones, etiquetas y simbología.
- Las capas pueden ser de memoria o estar en disco (GeoPackage), a elección del
  usuario al crearlas.

Esto es deliberado: significa que **cualquier herramienta de QGIS sirve** para
inspeccionar, editar y exportar el diseño, sin que el complemento tenga que
reimplementar nada.

## La optimización con IA

El bucle lo lleva **el complemento**, no el modelo:

```
     motor regenera el diseño  ──►  volúmenes en local (exactos, rápidos)
              ▲                                  │
              │                                  ▼
    validar contra rangos ◄── JSON ──  modelo local (Ollama / LM Studio)
                                        recibe números, historial e imágenes
```

Consecuencia clave: **toda solución es geométricamente válida por
construcción**. El modelo no puede producir un diseño imposible; como mucho
propone un cambio que se sale de rango, se ignora y se anota.

El modelo corre **en local**. Sin servidor, el mismo bucle funciona en modo
numérico y no sale ningún dato del proyecto de la máquina.

## Compatibilidad QGIS 3.22 ↔ 4.x

| Diferencia | Solución |
|---|---|
| Enums Qt con ámbito | Se escribe siempre con ámbito, válido en los dos |
| `QAction` en QtGui vs QtWidgets | `from .core.compat import QAction` |
| `exec()` vs `exec_()` | Siempre `exec()` |
| `QMetaType` (≥3.38) vs `QVariant` | `compat._tipos_campo` |
| Tipos de geometría | `compat.tipo_geom()` — los enums PyQt6 no comparan con `int` |
| Campo `fid` de GeoPackage | `compat.attrs()` — por nombre, nunca por posición |

Todo en `core/compat.py`. Es la única concesión a "código defensivo" del
proyecto, y está concentrada ahí a propósito.
