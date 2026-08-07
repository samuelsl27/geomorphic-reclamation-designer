# `context/` — memoria del proyecto

Esta carpeta es **la memoria a largo plazo** del desarrollo. No es documentación
de usuario (eso está en `docs/`) ni documentación de API: es lo que un agente de
IA o un desarrollador nuevo necesita saber para **no repetir errores ya
cometidos** y para **no romper lo que ya funciona**.

Nació porque el desarrollo se ha hecho en sesiones largas con asistentes de IA
que pierden el contexto entre sesiones. Todo lo que se aprendió depurando contra
la salida del programa original —y costó horas— está condensado aquí.

## Ficheros

| Fichero | Contenido | Se actualiza |
|---|---|---|
| `00_glosario.md` | Vocabulario ES/EN del método y del código | rara vez |
| `01_metodo_geofluv.md` | Ecuaciones y constantes **con su cita** | al añadir una ecuación |
| `02_arquitectura.md` | Módulos, flujo de datos, capas generadas | al mover código |
| `03_decisiones.md` | Registro de decisiones (ADR): qué, por qué, alternativas | al decidir algo |
| `04_bugs_resueltos.md` | Catálogo de bugs con causa raíz y medida | con cada bug |
| `05_invariantes.md` | Reglas que el diseño debe cumplir siempre | rara vez |
| `06_comparacion_original.md` | Métricas medidas contra el GeoFluv original | tras cada comparación |
| `07_entorno_qgis_mcp.md` | Cómo probar en QGIS y sus trampas | al descubrir una trampa |
| `08_pendiente.md` | Backlog y trabajo a medias | cada sesión |
| `09_historial_sesiones.md` | Bitácora de sesiones | **cada sesión** |

## Reglas de escritura

1. **Con números.** "La cresta quedaba mal" no sirve. "El extremo bajo quedaba
   17.4 m colgado sobre el cauce; el original lo deja a +2.29 m" sí.
2. **Con la causa raíz**, no con el síntoma.
3. **Con la cita** cuando sea una ecuación o una constante del método.
4. Añadir arriba (lo más reciente primero) en `04` y `09`; en orden lógico en el
   resto.
5. Si algo deja de ser cierto, **táchalo y explica por qué**, no lo borres. La
   historia de por qué se probó algo y no funcionó vale tanto como la solución.
