---
description: Medir el diseño generado contra la salida del GeoFluv original
---

Compara nuestro diseño con el del programa original sobre el mismo terreno.
Foco de la comparación: **$ARGUMENTS** (si no digo nada, compara todo).

En QGIS están cargados los dos: nuestras capas `GRD_*` y el grupo de referencia
importado del DXF original (busca «origen» en el nombre del grupo).

Mide, para cada elemento comparable:

| Magnitud | Cómo |
|---|---|
| Longitud y sinuosidad de cada canal | `geometry().length()` sobre eje y sobre valle |
| Cotas de cabecera y boca | primer y último vértice |
| Nº de crestas/vaguadas que arrancan del canal | conteo con índice espacial |
| Longitud media y pendiente media de esas líneas | |
| Espaciado a lo largo del canal y ángulo respecto al eje | |
| Extremo bajo de la divisoria sobre el lecho | diferencia de Z en la confluencia |
| Distancia de la divisoria al eje | `distance()` a la unión de ejes |
| Δz en los cruces curva de nivel / cauce | intersecciones e interpolación de Z |
| Peor gradiente vértice a vértice | |

Preséntalo como la tabla de `context/06_comparacion_original.md`, con la columna
del original al lado.

**Cómo interpretarlo** (está en ese fichero, respétalo):

- coincidir al 100 % **no** es el objetivo: el original tiene factores aleatorios;
- las **cotas de anclaje** sí deben coincidir (divisoria, pie de ladera, confluencias);
- una diferencia sistemática en un ajuste es **calibración**, no bug;
- una diferencia en la **forma** (meseta, zanja, cola vertical, escalón) **sí** es bug.

Si los números cambian respecto a la tabla guardada, actualízala.
