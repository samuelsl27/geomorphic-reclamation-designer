# Política de seguridad

## Versiones con soporte

| Versión | Soporte |
|---|---|
| 1.0.17 y posteriores | ✅ |
| < 1.0.17 | ❌ |

## Informar de una vulnerabilidad

**No abras un issue público** para una vulnerabilidad. Escribe a
**samuelimga@gmail.com** con:

- qué es y qué permite hacer;
- cómo reproducirlo;
- versión del complemento, de QGIS y sistema operativo.

Respuesta en un plazo razonable (proyecto pequeño, sin equipo de guardia). Se te
acreditará en el aviso salvo que prefieras lo contrario.

## Superficie de ataque

El complemento se ejecuta **dentro del proceso de QGIS**, con los permisos del
usuario. Puntos a tener en cuenta:

| Punto | Detalle |
|---|---|
| **Ficheros de proyecto `.geofluv.json`** | Se cargan con `json.load` (nunca `eval`/`pickle`), pero un fichero de origen desconocido puede apuntar a rutas de capa arbitrarias. **No abras proyectos que no sean tuyos sin revisarlos.** |
| **Optimización con IA** | El modelo habla **solo con `localhost`** (Ollama / LM Studio). No hay servicios en la nube: los datos del diseño (números e imágenes) no salen de tu máquina, salvo lo que tú permitas en la fila siguiente. |
| **Búsqueda web del optimizador** | Es la **única** salida a Internet del complemento: una consulta HTTPS a DuckDuckGo. Está **desactivada por defecto** (casilla *Allow web search* en la pestaña de IA) y solo se dispara si el modelo local pide una consulta. Lo que viaja es **el texto de esa consulta**, redactado por el modelo y truncado a 200 caracteres, no el proyecto. Si no quieres ninguna conexión saliente, deja la casilla sin marcar. |
| **Escritura de ficheros** | Solo en la carpeta que elige el usuario para las capas y en la carpeta de optimización, junto al proyecto. |
| **Dependencias** | **Ninguna** dependencia pip. Solo biblioteca estándar y la API de QGIS/Qt, es decir: cero cadena de suministro propia. |
| **Ejecución de código** | El complemento **no ejecuta** código de configuración, de proyectos ni de respuestas del modelo. Las respuestas del modelo se interpretan como **JSON con variables numéricas validadas contra rangos**; lo que se sale de rango se ignora y se registra. |

## Fuera de alcance

- Vulnerabilidades de QGIS, Qt, GDAL o del sistema operativo: repórtalas a esos
  proyectos.
- Que el usuario ejecute a propósito código en la consola de Python de QGIS.
- Riesgos derivados de exponer voluntariamente un servidor de IA local a la red.
