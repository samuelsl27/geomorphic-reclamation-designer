# Manejar QGIS desde el editor: MCP

**MCP** (Model Context Protocol) permite que el asistente del editor hable con
QGIS: listar capas, ejecutar Python **dentro** de QGIS, medir geometrías,
recargar el complemento y hacer capturas del lienzo.

Para este proyecto no es un lujo: **es la única forma seria de validar un cambio
geométrico**. Sin ello, la única alternativa es abrir QGIS, mirar la pantalla y
opinar — y así es como se cuelan las regresiones.

---

## Las dos piezas

```
   VSCode / Claude Code                     QGIS 4.2
   ┌───────────────────┐   stdio   ┌──────────────────┐  socket  ┌──────────┐
   │  asistente        │◄─────────►│ qgis_mcp_server  │◄────────►│ complemento
   │                   │   MCP     │  (proceso suelto)│  :9876   │ qgis_mcp_plugin
   └───────────────────┘           └──────────────────┘          └──────────┘
```

1. **`qgis_mcp_plugin`** — complemento de QGIS. Vive en tu perfil y abre un
   socket. **QGIS tiene que estar abierto y el complemento arrancado.**
2. **`qgis_mcp_server.py`** — proceso independiente que arranca el editor y que
   traduce entre MCP y ese socket.

Proyecto de referencia: <https://github.com/jjsantos01/qgis_mcp>

---

## Configuración automática

```bash
python scripts/configurar_mcp.py
```

Busca las dos piezas y escribe `.mcp.json` (Claude Code) y `.vscode/mcp.json`
(VSCode / Copilot). Si no encuentra el servidor:

```bash
git clone https://github.com/jjsantos01/qgis_mcp
python scripts/configurar_mcp.py --ruta C:\ruta\a\qgis_mcp\src\qgis_mcp
```

Para ver qué haría sin escribir nada: `--seco`.

## Configuración a mano

`.mcp.json` en la raíz del repositorio:

```json
{
  "mcpServers": {
    "qgis": {
      "command": "uv",
      "args": [
        "--directory",
        "C:/ruta/a/qgis_mcp/src/qgis_mcp",
        "run",
        "qgis_mcp_server.py"
      ],
      "env": { "QGIS_MCP_HOST": "127.0.0.1", "QGIS_MCP_PORT": "9876" }
    }
  }
}
```

Sin [`uv`](https://docs.astral.sh/uv/), usa el Python del entorno:

```json
{
  "mcpServers": {
    "qgis": {
      "command": "python",
      "args": ["C:/ruta/a/qgis_mcp/src/qgis_mcp/qgis_mcp_server.py"]
    }
  }
}
```

---

## Arrancar

1. Abre **QGIS 4.2**.
2. *Complementos → Administrar e instalar* → activa **QGIS MCP**.
3. Ábrelo y pulsa **Start server** (puerto 9876).
4. Abre el proyecto de trabajo con el diseño cargado.
5. En el editor, comprueba con la herramienta `ping` del servidor `qgis`.

Si `ping` dice *«Could not connect to QGIS»*, no es la configuración: es que QGIS
está cerrado o el servidor no está arrancado.

---

## Las trampas

Están explicadas con detalle, y con las recetas de medida, en
[`../context/07_entorno_qgis_mcp.md`](../context/07_entorno_qgis_mcp.md).
Resumen:

| # | Trampa | Qué hacer |
|---|---|---|
| 1 | El perfil activo es **QGIS4**, no QGIS3 | comprobar con `QgsApplication.qgisSettingsDirPath()` |
| 2 | `execute_code` devuelve la salida de la llamada **anterior** | terminar cada llamada con `print("MARCA-n")` y comprobar que lees la tuya |
| 3 | Recargar módulos en mal orden deja `GlobalSettings` viejo | recargar `params` primero, o reiniciar QGIS |
| 4 | Rásteres finos cargados ralentizan el pipeline | mirar las capas antes de culpar al código |
| 5 | QGIS cerrado | abrirlo y arrancar el servidor |

---

## Qué puedes hacer con él

```python
# medir una capa de líneas 3D
from qgis.core import QgsProject
capa = QgsProject.instance().mapLayersByName("GF_Ridges")[0]
for f in capa.getFeatures():
    zs = [v.z() for v in f.geometry().vertices()]
    print(f.id(), round(max(zs), 2), round(min(zs), 2),
          round(f.geometry().length(), 1))
print("MARCA-1")
```

```python
# lanzar el Check Design sin abrir la ventana
from geomorphic_reclamation_designer.core import checks
h = checks.revisar(proyecto, ajustes)
print(checks.resumen(h))          # (errores, avisos, informativos)
print("MARCA-2")
```

```python
# recargar el complemento
from qgis import utils
utils.reloadPlugin("geomorphic_reclamation_designer")
print("MARCA-3")
```

Más recetas —peor gradiente vértice a vértice, distancia al eje del cauce, Δz en
los cruces con las curvas— en
[`../context/07_entorno_qgis_mcp.md`](../context/07_entorno_qgis_mcp.md).

---

## Seguridad

El servidor MCP ejecuta **Python arbitrario dentro de QGIS**, con tus permisos.

- Escucha solo en **`127.0.0.1`**. No lo expongas a la red.
- Arráncalo solo cuando lo vayas a usar.
- No lo dejes corriendo con proyectos que contengan datos sensibles si vas a
  usar un asistente en la nube.
