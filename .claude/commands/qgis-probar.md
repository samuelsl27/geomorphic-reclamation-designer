---
description: Instalar en QGIS y verificar un cambio geométrico midiendo, no mirando
---

Verifica en QGIS **de verdad** el cambio que acabamos de hacer.
Qué hay que comprobar: **$ARGUMENTS**

Lee antes `context/07_entorno_qgis_mcp.md`. Recuerda las trampas:

- el perfil activo es **QGIS4**, no QGIS3;
- `execute_code` devuelve la salida de la llamada **anterior** → termina cada
  llamada con un `print("MARCA-n")` distinto y comprueba que lees la tuya;
- si has tocado `core/params.py`, **reinicia QGIS**, no recargues en caliente.

Pasos:

1. `python scripts/deploy_local.py`
2. Comprueba con la herramienta `ping` del MCP que QGIS responde. Si no, dime que
   lo abra y active `qgis_mcp_plugin`, y para ahí.
3. Recarga el complemento (o pídeme que reinicie QGIS si tocamos `params.py`).
4. Regenera el diseño.
5. **Mide.** Usa las recetas de `context/07_entorno_qgis_mcp.md`: cotas de los
   extremos, pendiente máxima vértice a vértice, distancia al eje del cauce,
   Δz en los cruces con las curvas de nivel, y `checks.resumen()`.
6. Compara con la tabla de `context/06_comparacion_original.md`.

Preséntame el resultado como una tabla **antes / después / original**, y di
claramente si el cambio **mejora, empeora o no cambia nada**. Si no puedes
medirlo, dilo: «parece que está bien» no es un resultado.
