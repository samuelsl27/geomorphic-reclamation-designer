# Qué cambia

<!-- Una frase. Si son varias cosas, probablemente deban ser varios PR. -->

Cierra #

## Por qué

<!-- El problema real. Si es un bug, la CAUSA RAÍZ, no el síntoma. -->

## La medida

<!-- Obligatorio si el cambio es geométrico o hidráulico.
     Antes → después, y el valor del programa original si aplica.
     Ver context/06_comparacion_original.md -->

| Magnitud | Antes | Después | Original |
|---|---|---|---|
|  |  |  |  |

## Escenarios comprobados

<!-- Regla de la casa: la corrección debe valer en TODOS los escenarios, no
     solo en el caso con el que depuraste. Marca los que hayas comprobado. -->

- [ ] El caso que motivó el cambio
- [ ] El cauce por encima del perímetro (ladera que desciende *desde* el cauce)
- [ ] Ladera prácticamente plana
- [ ] Línea que entra y sale del corredor varias veces
- [ ] Un solo canal, sin tributarios
- [ ] Otro: <!-- cuál -->

## Lista de comprobación

- [ ] He leído `AGENTS.md` y `context/04_bugs_resueltos.md`
- [ ] `pytest -q` en verde
- [ ] `ruff check .` en verde
- [ ] Hay un test que falla antes y pasa después
- [ ] Si toco una ecuación o constante: está en `context/01_metodo_geofluv.md` **con su cita** y fijada en `tests/test_libro.py`
- [ ] No he añadido dependencias pip
- [ ] Compatible con Qt5 **y** Qt6 (enums con ámbito, `exec()`, `compat.*`)
- [ ] Atributos por nombre de campo (`compat.attrs`), no por posición
- [ ] No he editado `help/guide.html` a mano (he editado `scripts/guia_datos.py`)
- [ ] `CHANGELOG.md` actualizado
- [ ] `context/` actualizado (bug → `04`, decisión → `03`, tarea → `08`, siempre `09`)
- [ ] Acepto el [CLA](../blob/main/CLA.md) (`git commit -s`, o línea en `AUTHORS.md`)

## Capturas

<!-- Si el cambio es geométrico, antes y después. -->
