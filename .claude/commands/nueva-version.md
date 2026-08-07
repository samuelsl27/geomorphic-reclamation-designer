---
description: Cerrar una versión (subir número, changelog, tests, zip, tag)
allowed-tools: Bash(python:*), Bash(pytest:*), Bash(ruff:*), Bash(git:*), Read, Edit, Write
---

Cierra una versión del complemento. Versión pedida: **$ARGUMENTS**
(si no te doy número, usa `patch`).

Haz esto en orden y **para en el primer fallo**:

1. `git status` — si hay cambios sin confirmar, dímelo y espera.
2. `python scripts/bump_version.py <version>` — toca los 4 sitios a la vez.
3. **`CHANGELOG.md`**: crea la sección de la versión nueva. Recorre
   `git log` desde la etiqueta anterior y redáctala en el estilo del fichero:
   secciones *Añadido / Cambiado / Corregido / Medido / Conocido*, con los
   códigos `B-0xx`, `ADR-0xx` y `P-xx` que correspondan, y **con las medidas**
   (antes → después, y el valor del original si es geométrico).
4. **`context/09_historial_sesiones.md`**: añade la entrada de esta versión
   arriba del todo, con la plantilla del final del fichero.
5. **`context/08_pendiente.md`**: mueve a «Terminado recientemente» lo que se
   haya cerrado y añade lo nuevo que haya aparecido.
6. `python scripts/genera_guia.py`
7. `ruff check .`
8. `pytest -q`
9. `python scripts/build_zip.py`
10. `git add -A && git commit -m "chore: versión <version>"`
11. `git tag -a v<version> -m "v<version>"`

Al terminar, muéstrame el resumen de la versión y recuérdame que falta
`git push && git push --tags` para que Actions publique la release.
