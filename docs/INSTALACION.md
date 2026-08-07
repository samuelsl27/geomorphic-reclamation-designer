# Instalación y requisitos

## Requisitos

| | |
|---|---|
| **QGIS** | ≥ 3.22, incluido **4.0 / 4.2+** (Qt6 / PyQt6) |
| **SRC** | Proyectado **en metros** (p. ej. EPSG:25830). Obligatorio |
| **Datos** | Un DEM del terreno de partida |
| **Dependencias** | **Ninguna.** Solo biblioteca estándar y la API de QGIS/Qt |

## Instalar

### Desde un ZIP

1. Descarga `geomorphic_reclamation_designer_vX.Y.Z.zip` de
   [Releases](https://github.com/samuelsl27/geomorphic-reclamation-designer/releases).
2. *Complementos → Administrar e instalar complementos → **Instalar a partir de
   ZIP***.
3. Elige el fichero → *Instalar complemento*.
4. En *Instalados*, activa **Geomorphic Reclamation Designer**.

Aparecen un botón en la barra de herramientas y un menú
**Geomorphic Reclamation**.

> El complemento está marcado como **experimental**. Si no lo ves en la lista:
> *Configuración → Mostrar también complementos experimentales*.

### Desde el repositorio de complementos

Cuando esté publicado: *Complementos → Administrar e instalar → Todos →* buscar
*Geomorphic Reclamation Designer*.

### Desde el código fuente (desarrollo)

```bash
git clone https://github.com/samuelsl27/geomorphic-reclamation-designer.git
cd geomorphic-reclamation-designer
python scripts/deploy_local.py
```

Ver [`DESARROLLO.md`](DESARROLLO.md).

---

## Si venías de `geofluv_q`

Es un complemento **distinto** para QGIS, con otro nombre de carpeta.
**Desinstala el antiguo** desde el gestor de complementos, o tendrás dos botones
y dos menús.

**Tus proyectos siguen funcionando.** Se conservan el prefijo de capa `GF_`, la
extensión `.geofluv.json` y las claves del fichero de proyecto: abre tu
`.geofluv.json` con el complemento nuevo y sigue donde lo dejaste.

El motivo del cambio de nombre está en
[`../context/03_decisiones.md`](../context/03_decisiones.md) (ADR-014).

---

## Preparar el proyecto de QGIS

1. **SRC proyectado en metros.** *Proyecto → Propiedades → SRC*. Con coordenadas
   geográficas (grados) los cálculos de longitud, área y pendiente no tienen
   sentido y el complemento avisa.
2. **Carga el DEM** del terreno de partida.
3. **Guarda el proyecto de QGIS** antes de empezar: el complemento guarda su
   `.geofluv.json` y, si quieres, las capas en disco, junto a él.

## Primer diseño

1. **Ajustes…** — las variables locales medidas en un área natural de referencia
   estable, con el mismo material y clima. La **pendiente en la desembocadura**
   es el valor más crítico de todo el método.
2. **Setup** — *Create Layers*, dibuja el límite (polígono) y los fondos de valle
   (líneas 2D, patrón dendrítico) en `01 Entradas`. Selecciona límite → canal
   principal → punto de transición → DEM.
3. **Channels** — añade los tributarios y ajusta cada canal.
4. **Output** — *Draw Design Surface* y *Update Cut/Fill*.
5. **Check Design** — el registro de errores.

El botón **Help** abre la guía bilingüe con los 97 ajustes documentados.

---

## Problemas

| Síntoma | Solución |
|---|---|
| No aparece en la lista de complementos | Activa *Mostrar también complementos experimentales* |
| *"El complemento no es válido"* | Reconstruye el zip con `scripts/build_zip.py`, que verifica la estructura |
| *"Se requiere un SRC proyectado"* | *Proyecto → Propiedades → SRC*, elige uno en metros |
| Errores de PyQt tras actualizar QGIS | Reinicia QGIS. Si sigue, abre un issue con la versión exacta |
| Las capas guardadas salen vacías | Bug B-006, corregido en 1.0.11. Actualiza |
| La superficie tarda muchísimo | La resolución se calcula sola, pero un límite enorme con canales muy estrechos da rásteres gigantes. Mira el aviso del registro |

Más ayuda: [Issues](https://github.com/samuelsl27/geomorphic-reclamation-designer/issues).
