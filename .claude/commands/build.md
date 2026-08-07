---
description: Generar el ZIP instalable, con todas las comprobaciones previas
allowed-tools: Bash(python:*), Bash(pytest:*), Bash(ruff:*), Read, Edit
---

Genera el ZIP instalable siguiendo el orden completo. **Para en el primer fallo**
y explica qué hay que arreglar; no sigas adelante «a ver si cuela».

1. `python scripts/genera_guia.py` — regenerar `help/guide.html`.
2. `ruff check .`
3. `pytest -q` — deben pasar todos.
4. `python scripts/build_zip.py` — comprueba versiones, compila todo el Python,
   empaqueta y verifica el zip resultante.

Al terminar, dime:

- la ruta del zip y su tamaño;
- la versión empaquetada;
- si `CHANGELOG.md` tiene una entrada para esa versión (si no, avísame);
- el recordatorio de instalación:
  *QGIS → Complementos → Administrar e instalar complementos → Instalar a partir de ZIP*.

$ARGUMENTS
