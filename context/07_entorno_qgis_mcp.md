# Entorno de pruebas: QGIS real vía MCP

Ningún cambio geométrico se da por bueno sin medirlo en QGIS. El PC de
desarrollo tiene **QGIS 4.2** con el complemento `qgis_mcp_plugin`, que abre un
socket y permite ejecutar Python **dentro** de QGIS desde el editor.

Configuración e instalación: `docs/MCP_QGIS.md` y `.mcp.json`.

---

## Las cinco trampas (te van a morder si no las lees)

### 1. El perfil activo es `QGIS4`, no `QGIS3`

```
%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins
```

Instalar en `QGIS3` significa editar código que **nadie ejecuta** y volverse
loco buscando por qué el cambio no hace nada. `scripts/deploy_local.py` detecta
el perfil correcto; si dudas, comprueba en QGIS:

```python
from qgis.core import QgsApplication
print(QgsApplication.qgisSettingsDirPath())
```

### 2. `execute_code` devuelve la salida de la llamada ANTERIOR

Hay un desfase de un turno en el MCP. Si lees el resultado tal cual, estarás
mirando lo que imprimiste **antes**.

**Truco**: termina cada llamada con una marca distinta y comprueba que la marca
que lees es la que enviaste.

```python
...tu código...
print("MARCA-7")        # cambia el número en cada llamada
```

Si lees `MARCA-6`, esa salida es de la llamada anterior: repite.

### 3. Orden de recarga de módulos

Recargar ordenando los módulos **por longitud de nombre** recarga `project.py`
antes que `params.py`, así que `GlobalSettings` se queda con la versión vieja y
salta un `AttributeError` al leer un ajuste nuevo.

**Recarga `params` primero.** Guion seguro:

```python
import importlib, sys
ORDEN = ["compat", "params", "project", "naming", "hydrology", "profile",
         "planform", "setup_tools", "builder", "ridges", "hillslopes",
         "divides", "topology", "surface", "checks", "structures",
         "layer_manager", "ai_client", "ai_context", "ai_optimizer"]
for nombre in ORDEN:
    m = sys.modules.get(f"geomorphic_reclamation_designer.core.{nombre}")
    if m:
        importlib.reload(m)
# la gui va después, siempre
for k in [k for k in sys.modules if k.startswith("geomorphic_reclamation_designer.gui")]:
    importlib.reload(sys.modules[k])
print("MARCA-recarga")
```

> **Ante cualquier `AttributeError` raro después de tocar `params.py`:
> reinicia QGIS antes de investigar nada.** Se han perdido horas depurando un
> módulo viejo cargado en memoria.

### 4. Rásteres finos cargados ralentizan todo

Si el pipeline pasa de ~3 s a ~15 s **sin haber tocado el motor**, mira primero
qué capas hay cargadas. Un ráster de diseño fino en el lienzo basta.
No busques una regresión de rendimiento antes de descartar esto.

### 5. QGIS tiene que estar abierto

El MCP habla con un complemento **dentro** de QGIS. Si `ping` falla con
*"Could not connect to QGIS"*, no es que el MCP esté mal configurado: es que
QGIS está cerrado o el complemento `qgis_mcp_plugin` no está activado/arrancado.

---

## Recetas útiles

### Medir una capa de líneas 3D

```python
from qgis.core import QgsProject
capa = QgsProject.instance().mapLayersByName("GF_Ridges")[0]
for f in capa.getFeatures():
    zs = [v.z() for v in f.geometry().vertices()]
    L  = f.geometry().length()
    dz = max(zs) - min(zs)
    print(f"{f.id():4d} {max(zs):8.2f}->{min(zs):8.2f}  L={L:7.1f}  "
          f"pend={100*dz/L if L else 0:5.1f}%")
print("MARCA-medir")
```

### Peor gradiente vértice a vértice

```python
peor = 0.0
for f in capa.getFeatures():
    vs = list(f.geometry().vertices())
    for a, b in zip(vs, vs[1:]):
        d = ((a.x()-b.x())**2 + (a.y()-b.y())**2) ** 0.5
        if d > 1e-6:
            peor = max(peor, abs(a.z()-b.z()) / d)
print(f"peor gradiente: {100*peor:.0f} %")
print("MARCA-grad")
```

### Distancia de una línea al eje del cauce

```python
from qgis.core import QgsProject, QgsGeometry
ejes = QgsProject.instance().mapLayersByName("GF_Channels")[0]
union = QgsGeometry.unaryUnion([f.geometry() for f in ejes.getFeatures()])
for f in capa.getFeatures():
    print(f.id(), round(f.geometry().distance(union), 2))
print("MARCA-dist")
```

### Lanzar el *Check Design* sin abrir la ventana

```python
from geomorphic_reclamation_designer.core import checks
h = checks.revisar(proyecto, ajustes)
print(checks.resumen(h))          # (errores, avisos, informativos)
for x in h:
    if x.severidad == "error":
        print(x.codigo, x.texto)
print("MARCA-check")
```

### Recargar el complemento entero

```python
from qgis import utils
utils.reloadPlugin("geomorphic_reclamation_designer")
print("MARCA-reload")
```

(Después de tocar `params.py`, mejor reiniciar QGIS — ver trampa 3.)

### Captura del lienzo

Vía la herramienta `get_canvas_screenshot` del MCP, o:

```python
from qgis.utils import iface
iface.mapCanvas().saveAsImage("C:/temp/captura.png")
print("MARCA-shot")
```

---

## Flujo de trabajo recomendado

```
1. editar en VSCode        →  src/geomorphic_reclamation_designer/...
2. python scripts/deploy_local.py
3. (MCP) reloadPlugin, o reiniciar QGIS si tocaste params.py
4. (MCP) regenerar el diseño
5. (MCP) medir con las recetas de arriba
6. comparar con context/06_comparacion_original.md
7. si mejora: pytest -q, commit, actualizar context/
```

Para iterar rápido, `deploy_local.py` acepta `--watch` y recopia al guardar.
