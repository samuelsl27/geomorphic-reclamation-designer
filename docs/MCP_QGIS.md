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
   VSCode / Claude Code                     QGIS 3.28 – 4.x
   ┌───────────────────┐   stdio   ┌──────────────────┐  socket  ┌──────────┐
   │  asistente        │◄─────────►│ qgis-mcp-server  │◄────────►│ complemento
   │                   │   MCP     │  (proceso suelto)│  :9876   │ QGIS MCP
   └───────────────────┘           └──────────────────┘          └──────────┘
```

1. **Complemento `QGIS MCP`** — vive en tu perfil de QGIS y abre el socket.
   **QGIS tiene que estar abierto y el servidor arrancado** (*Start Server*).
2. **`qgis-mcp-server`** — proceso independiente que arranca el editor y que
   traduce entre MCP y ese socket. No se clona: `uvx` lo descarga y lo cachea.

Proyecto de referencia: <https://github.com/nkarasiak/qgis-mcp>

> **Las dos piezas llevan número de versión y tienen que coincidir.** El
> complemento se actualiza desde el gestor de QGIS y el servidor desde el JSON
> de configuración; es fácil que se separen. `scripts/configurar_mcp.py` lee la
> versión del complemento instalado y fija esa misma etiqueta, precisamente para
> que no pase.

---

## Requisitos

- **QGIS 3.28 → 4.x** (aquí se usa 4.2).
- [**`uv`**](https://docs.astral.sh/uv/getting-started/installation/), que trae
  `uvx`. El servidor pide **Python ≥ 3.12**, pero corre FUERA de QGIS: da igual
  que QGIS traiga el 3.9.

## Configuración automática

```bash
python scripts/configurar_mcp.py            # comprueba y escribe
python scripts/configurar_mcp.py --seco     # solo informa
```

Comprueba las dos piezas, lee la versión del complemento instalado y escribe
`.mcp.json` (Claude Code) y `.vscode/mcp.json` (VSCode / Copilot) fijados a esa
misma versión. **No edites esos dos ficheros a mano**: regenéralos con el guion.

## Configuración a mano

`.vscode/mcp.json` para VSCode (clave `servers`, con `type`):

```json
{
  "servers": {
    "qgis": {
      "type": "stdio",
      "command": "uvx",
      "args": [
        "--from",
        "https://github.com/nkarasiak/qgis-mcp/archive/refs/tags/v0.10.0.zip",
        "qgis-mcp-server"
      ],
      "env": { "QGIS_MCP_HOST": "127.0.0.1", "QGIS_MCP_PORT": "9876" }
    }
  }
}
```

`.mcp.json` para Claude Code es lo mismo con la clave `mcpServers` y sin `type`.

Apuntar a `.../heads/main.zip` en vez de a una etiqueta también funciona, pero
entonces el servidor se actualiza solo y acaba desincronizado del complemento.
**Fija la etiqueta.**

---

## Arrancar

1. Abre **QGIS**.
2. *Complementos → Administrar e instalar* → busca **QGIS MCP** e instálalo.
3. Reinicia QGIS, abre el complemento y pulsa **Start Server** (puerto 9876).
4. Abre el proyecto de trabajo con el diseño cargado.
5. Recarga la ventana de VSCode y comprueba con la herramienta `ping` del
   servidor `qgis`.

Si `ping` dice *«Could not connect to QGIS»*, no es la configuración: es que QGIS
está cerrado o el servidor no está arrancado.

`execute_code` pide confirmación al editor antes de ejecutar (*elicitation*).
Es a propósito: ejecuta Python arbitrario dentro de QGIS. Se puede desactivar
con `QGIS_MCP_AUTO_CONFIRM=1`, pero **no lo hagas** salvo en una sesión
desatendida y controlada.

---

## Las trampas

Están explicadas con detalle, y con las recetas de medida, en
[`../context/07_entorno_qgis_mcp.md`](../context/07_entorno_qgis_mcp.md).
Resumen:

| # | Trampa | Qué hacer |
|---|---|---|
| 1 | El perfil activo es **QGIS4**, no QGIS3 | comprobar con `QgsApplication.qgisSettingsDirPath()` |
| 2 | ~~`execute_code` devuelve la salida de la llamada **anterior**~~ | **resuelto** en el complemento ≥ 0.10.0: devuelve `stdout`/`stderr` de SU llamada |
| 3 | Recargar módulos en mal orden deja `GlobalSettings` viejo | recargar `params` primero, o reiniciar QGIS |
| 4 | Rásteres finos cargados ralentizan el pipeline | mirar las capas antes de culpar al código |
| 5 | QGIS cerrado | abrirlo y arrancar el servidor |
| 6 | Complemento y servidor con versiones distintas | `python scripts/configurar_mcp.py` |

---

## Qué puedes hacer con él

```python
# medir una capa de líneas 3D
from qgis.core import QgsProject
capa = QgsProject.instance().mapLayersByName("GRD_Ridges")[0]
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
