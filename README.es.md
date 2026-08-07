<div align="center">

# Geomorphic Reclamation Designer

**Complemento libre de QGIS para el diseño de restauración geomorfológica minera**

Diseña la red de drenaje que la naturaleza construiría en tu emplazamiento
—y la forma del terreno estable que la acompaña— sin salir de QGIS.

[![Licencia: AGPL v3](https://img.shields.io/badge/Licencia-AGPL%20v3-blue.svg)](LICENSE)
[![QGIS 3.22+ / 4.x](https://img.shields.io/badge/QGIS-3.22%20%E2%86%92%204.x-green.svg)](https://qgis.org)
[![Qt5 / Qt6](https://img.shields.io/badge/Qt-5%20%7C%206-41cd52.svg)](https://qgis.org)
[![Tests](https://img.shields.io/badge/tests-84%20en%20verde-brightgreen.svg)](tests/)

[English](README.md) · [Documentación](docs/) · [Cambios](CHANGELOG.md) · [Contribuir](CONTRIBUTING.md)

</div>

---

## Qué es

La restauración minera convencional construye taludes y bermas: líneas rectas
que el día de la entrega parecen terminadas y al día siguiente empiezan a
erosionarse. El **enfoque fluvio-geomórfico** hace lo contrario: deduce la red de
drenaje que se formaría de manera natural en ese sitio, con esos materiales y ese
clima, y construye **esa**. El resultado no necesita mantenimiento a largo plazo
porque ya está en equilibrio.

Este complemento mete todo ese flujo de trabajo dentro de QGIS:

```
límite + fondos de valle + DEM
        │
        ├─ hidrología ........ caudal punta racional, sección trapecial,
        │                      tensión tractiva de Shields, verificación Manning
        ├─ perfil largo ...... cóncavo, Hermite monótono (Fritsch–Carlson)
        ├─ planta ............ meandros según Williams (1986), o zigzag tipo A
        │                      donde la pendiente supera el 4 %
        ├─ relieve de ladera . crestas divisorias, subcrestas en los ápices de
        │                      meandro, vaguadas, sillas de cresta
        ├─ superficie ........ TIN de diseño, curvas de nivel, subcuencas
        └─ movimiento de tierras ... balance corte/relleno, regiones y acarreos
```

**Cada elemento es una capa de QGIS**, organizada en grupos y subgrupos, con las
propiedades hidráulicas como **atributos editables**. Puedes editar a mano
cualquier cresta, vaguada o canal con las herramientas normales de QGIS y
regenerar desde ahí: el flujo es re-entrante en todas las fases, que es
justamente de lo que se trata.

## Lo que lo distingue

| | |
|---|---|
| 🗺️ **QGIS nativo** | Sin pasar por CAD. Capas, atributos, estilos, árbol de capas, lienzo: todo dentro |
| 📐 **Fiel al método** | Cada ecuación es trazable a la literatura. `tests/test_libro.py` verifica cada una contra su cita |
| ✅ **Comprobador de diseño** | 22 comprobaciones (hoyos cerrados, líneas de rotura que se cruzan, tensión tractiva, densidad de drenaje, pendientes…) con un registro de errores filtrable y enlazado a las entidades |
| ♻️ **Re-entrante** | Edita cualquier fase a mano y regenera. El proyecto guarda **referencias** a las geometrías, no copias |
| 🤖 **IA local opcional** | Optimiza el diseño contra corte/relleno, distancia de acarreo o «empujabilidad» con bulldozer, usando un modelo que corre **en tu máquina** (Ollama / LM Studio). Sin servicios en la nube: tu diseño no sale del ordenador. La única conexión saliente es una búsqueda web **opcional y desactivada por defecto** para valores de referencia — ver [`SECURITY.md`](SECURITY.md) |
| 🌍 **Bilingüe** | Guía completa EN/ES. Los nombres de los ajustes quedan en inglés en los dos idiomas para que coincidan con la literatura |
| 🧩 **QGIS 3.22 → 4.x** | Qt5 y Qt6, un solo código |

## Instalación

**Desde el gestor de complementos** (cuando esté publicado): *Complementos →
Administrar e instalar complementos → Todos →* busca *Geomorphic Reclamation
Designer*.

**Desde un ZIP:**

1. Descarga el `geomorphic_reclamation_designer_vX.Y.Z.zip` más reciente de
   [Releases](../../releases), o constrúyelo con `python scripts/build_zip.py`.
2. *Complementos → Administrar e instalar complementos → Instalar a partir de ZIP.*
3. Activa **Geomorphic Reclamation Designer**. Aparecen un botón en la barra
   de herramientas y un menú *Geomorphic Reclamation*.

**Requisitos**: QGIS ≥ 3.22 (incluido 4.x), un **SRC proyectado en metros**
(p. ej. EPSG:25830) y un DEM del terreno de partida. Sin dependencias pip.

## Primeros pasos

1. **Ajustes** — introduce las *variables locales* medidas en un área natural de
   referencia estable con el mismo material y clima: distancia cresta-cabecera,
   **pendiente en la desembocadura** (el valor más crítico de todo el método),
   precipitación 2a-1h y 50a-6h, densidad de drenaje objetivo ± varianza.
2. **Setup** — dibuja el polígono del límite y las líneas de fondo de valle (2D
   aproximadas, patrón dendrítico). Selecciona límite → canal principal → punto
   de transición → DEM. El panel muestra área, cotas, longitud de valle y
   densidad de drenaje con semáforo.
3. **Canales** — añade tributarios (validados contra las reglas del método) y
   ajusta la geometría y la cuenca de cada uno.
4. **Salida** — *Dibujar superficie de diseño* (crestas + TIN + curvas) y luego
   *Actualizar corte/relleno*.
5. **Iterar** — ¿fuera de balance? Edita crestas o vaguadas, o cambia cotas y
   ajustes, y regenera. Repite hasta que densidad de drenaje y balance estén los
   dos en verde.
6. **Check Design** en cualquier momento para ver el registro de errores.

Guía completa de parámetros: el botón **Help** del complemento abre una guía
bilingüe que documenta los 97 ajustes y qué pasa al cambiar cada uno.

## Documentación

| | |
|---|---|
| [`docs/INSTALACION.md`](docs/INSTALACION.md) | Instalación y requisitos |
| [`docs/DESARROLLO.md`](docs/DESARROLLO.md) | **Cómo continuar el desarrollo** |
| [`docs/BUILD.md`](docs/BUILD.md) | Cómo generar el ZIP instalable |
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Cómo está montado el motor |
| [`docs/MCP_QGIS.md`](docs/MCP_QGIS.md) | Manejar QGIS desde el editor por MCP |
| [`AGENTS.md`](AGENTS.md) | Contrato de trabajo para agentes de IA |
| [`context/`](context/) | Memoria del proyecto: ecuaciones con cita, catálogo de bugs, decisiones, invariantes |

## El método

El complemento implementa el **método fluvio-geomórfico de diseño de formas del
terreno** publicado (Natural Regrade con GeoFluv™), desarrollado por Nicholas
Bugosh. Cada ecuación del motor es trazable a una cita en
[`context/01_metodo_geofluv.md`](context/01_metodo_geofluv.md).

- **Bugosh, N. y Martín Duque, J.F. (2024).** *Geomorphic Reclamation Design.* — referencia principal
- **Williams, G.P. (1986).** River meanders and channel size. *Journal of Hydrology* 88, 147–164.
- **Rosgen, D. (1996).** *Applied River Morphology.*
- **Dunne, T. y Leopold, L.B. (1978).** *Water in Environmental Planning.*
- **Martín Duque, J.F. et al. (2017).** Geomorphic reclamation… mina de El Machorro, Alto Tajo. *Ecological Engineering.*
- **Bugosh, N. y Epp, E. (2019).** Evaluating sediment production… La Plata Mine. *Catena* 174, 383–398.

> **Aviso de marcas y de nombre.** *GeoFluv™* y *Natural Regrade®* son marcas de
> sus titulares (N. Bugosh / Carlson Software). Este proyecto es una
> **implementación independiente y libre del método publicado**. No es un
> derivado de su software, no está afiliado ni respaldado por ellos, y no es
> compatible ni sustituto de su producto.
>
> El nombre del complemento usa *«geomorphic reclamation»*, el término
> descriptivo estándar de la disciplina. **No** es el software oficial del libro
> *Geomorphic Reclamation Design* (2024): ese libro se cita aquí como **fuente**,
> igual que cualquier trabajo científico es citado por una implementación
> independiente de los métodos que describe. Los errores de esta implementación
> son nuestros, no de sus autores.

## Quién está detrás

Desarrollado por **Samuel Sáez López**, con **Emilio Trigueros** — el mismo
equipo que está detrás de **[opengeorock.org](https://opengeorock.org/)**, en la
**Universidad Politécnica de Cartagena (UPCT)** y en **IMGA**.

La línea de trabajo del grupo es herramienta abierta y reproducible para minería
y geología aplicada: poner al alcance de cualquiera con QGIS métodos que hasta
ahora vivían dentro de software propietario caro — administraciones públicas,
consultoras pequeñas, universidades y las propias explotaciones que tienen que
hacer la restauración.

Si te resulta útil, cuéntanos cómo lo has usado. La realimentación desde
emplazamientos reales es lo que mejora la calibración.

## Contribuir

Las contribuciones son muy bienvenidas, sobre todo los informes de error con un
caso reproducible. Lee antes [`CONTRIBUTING.md`](CONTRIBUTING.md): explica el
flujo, las convenciones y el [CLA](CLA.md) que hay que firmar.

Si usas un asistente de IA para programar, apúntalo a
[`AGENTS.md`](AGENTS.md), que está escrito exactamente para eso.

## Licencia

**AGPL-3.0-or-later.** Ver [`LICENSE`](LICENSE).

En cristiano:

- ✅ **Uso libre y gratuito**, personal y profesional, en proyectos comerciales,
  para siempre. Sin cuota, sin registro, sin llamadas a casa.
- ✅ **Libre para modificar** y redistribuir.
- ⚠️ Si lo distribuyes, o **lo ofreces a usuarios a través de una red** (servicio
  web, SaaS, API), tienes que publicar tu código con la misma licencia. Eso es el
  §13 de la AGPL, y es justamente el objetivo.
- 📄 Las contribuciones requieren el [CLA](CLA.md), que permite al autor ofrecer
  el proyecto bajo una **licencia comercial aparte** a organizaciones que quieran
  explotarlo como servicio en red sin publicar su propio código.

El código es libre y lo seguirá siendo. El CLA existe para que la opción de un
servicio comercial futuro siga siendo posible, no para cerrar nada de lo que hoy
está abierto.

---

<div align="center">
<sub>© 2026 Samuel Sáez López y colaboradores · AGPL-3.0-or-later</sub>
</div>
