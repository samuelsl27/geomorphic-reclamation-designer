---
description: Contrastar una parte del motor contra el libro y las citas
---

Revisa contra la literatura esta parte del motor: **$ARGUMENTS**

Método:

1. Lee `context/01_metodo_geofluv.md` y localiza las ecuaciones y constantes que
   afectan a esa parte, con su clave de fuente (`[LIBRO]`, `[W86]`, `[ROS]`…).
2. Lee el código correspondiente en `src/geomorphic_reclamation_designer/core/`.
3. Para **cada** ecuación y **cada** constante, dime:
   - qué dice la fuente,
   - qué hace el código,
   - si coinciden.
4. Comprueba que hay un test en `tests/test_libro.py` que la fija, y que **su
   docstring es la cita**. Si falta, escríbelo.

Ten presente el bug **B-016**: hubo un periodo en que la *documentación* tenía
ecuaciones inventadas y el *código* estaba bien. Si encuentras una discrepancia,
**no supongas que el código es el que está mal**: mira el histórico
(`git log -p`), busca el test, y si sigue sin estar claro, **pregúntame antes de
tocar nada**.

Al final, una tabla: `ecuación · fuente · código · test · veredicto`.
