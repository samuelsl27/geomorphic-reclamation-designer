---
description: Volcar a context/ lo aprendido antes de cerrar la sesión
allowed-tools: Read, Edit, Write, Bash(git:*)
---

Cierra la sesión de trabajo dejando la memoria del proyecto al día. Esto es lo
que hace que la siguiente sesión no empiece de cero: **hazlo bien, no lo
despaches**.

1. `git log --oneline` desde el principio de la sesión, y `git diff --stat`, para
   recordar qué se ha tocado.

2. **`context/09_historial_sesiones.md`** — entrada nueva arriba del todo, con la
   plantilla del final del fichero: qué se hizo, bugs (`B-0xx`), decisiones
   (`ADR-0xx`), **las medidas** (antes → después, y el original si aplica),
   **los intentos fallidos** (qué se probó y por qué no funcionó — esto vale
   tanto como la solución) y lo que queda pendiente.

3. **`context/04_bugs_resueltos.md`** — si se ha corregido algún bug, entrada
   nueva arriba, con el número siguiente: síntoma, **causa raíz**, corrección
   (con el fragmento de código si es sutil) y la medida que lo demuestra. Si
   encaja en alguno de los patrones recurrentes del final del fichero, dilo.

4. **`context/03_decisiones.md`** — si se ha tomado alguna decisión de diseño:
   contexto → decisión → consecuencias → alternativas descartadas.

5. **`context/08_pendiente.md`** — mueve lo terminado a «Terminado
   recientemente» y añade lo nuevo con su código `P-xx`.

6. **`context/01_metodo_geofluv.md`** — si se ha añadido o cambiado alguna
   ecuación o constante, con su cita.

7. **`AGENTS.md`** — si hemos aprendido una regla nueva que habría evitado el
   problema de hoy, propónmela como regla de oro. **No la añadas sin
   preguntar.**

8. **`CHANGELOG.md`** — bajo `[No publicado]`.

Al terminar, resume en 5 líneas qué queda pendiente y cuál sería el siguiente
paso lógico.

$ARGUMENTS
