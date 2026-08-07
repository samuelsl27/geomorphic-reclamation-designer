# Tests

```bash
pytest -q                        # todo
pytest tests/test_libro.py -v    # solo las ecuaciones del libro
pytest -q -k divisorias          # un area
pytest -q --cov=geomorphic_reclamation_designer   # con cobertura
```

## Qué hay

| Fichero | Tests | Qué cubre | ¿QGIS? |
|---|---|---|---|
| `test_libro.py` | 17 | **Cada ecuación contra su cita del libro.** El docstring de cada test *es* la cita | no |
| `test_hidraulica.py` | 10 | Método racional, Manning, Shields, geometría de meandro | no |
| `test_divisorias.py` | 31 | Recorte contra el corredor, perfiles desde control, monotonía, empalmes | no |
| `test_checks.py` | 17 | Las 22 comprobaciones C02–C52 | no |
| `test_optimizador.py` | 9 | Rangos, candidatos, puntuación | no |
| `test_integracion.py` | 15 pasos | Flujo completo *headless* | **sí** |
| `test_gui.py` | 7 pasos | Construcción de la interfaz | **sí** |

Los dos últimos **se saltan solos** si no encuentran `qgis.core` (ver
`conftest.py`). En CI corren los cinco primeros.

## `test_libro.py` es especial

Es la red de seguridad contra el peor tipo de bug de este proyecto: que alguien
—persona o IA— "corrija" una constante del método hacia un valor equivocado.

**Regla: el docstring de cada test es la cita textual que verifica.**

```python
def test_longitud_de_onda_del_meandro():
    """Williams (1986), recogido en el libro §2.2.8: lambda = 4.53 * Rc."""
    assert hydrology.LAMBDA_POR_RC == pytest.approx(4.53)
```

Así, cuando el test falla, no dice solo *«esperaba 4.53»*: dice **de dónde sale
el 4.53**. Nació del bug B-016, en el que la documentación tenía ecuaciones
inventadas mientras el código estaba bien.

Si añades una ecuación o una constante al motor:

1. documéntala en `context/01_metodo_geofluv.md` con su fuente;
2. escribe aquí el test, con la cita en el docstring.

## Correr los que necesitan QGIS

Hace falta que `qgis.core` sea importable. En Windows, con el Python de QGIS:

```bat
"C:\Program Files\QGIS 4.2\bin\python-qgis.bat" -m pytest -q tests
```

En Linux, con `python3-qgis` instalado, basta `pytest -q`.

## Añadir un test

- Uno por comportamiento, con nombre que diga **qué** se comprueba, no cómo.
- Si verifica una ecuación → `test_libro.py`, con la cita.
- Si es una regresión de un bug → cita el código `B-0xx` en el docstring, para
  que se pueda seguir el rastro hasta `context/04_bugs_resueltos.md`.
- Si necesita QGIS, ponlo en `test_integracion.py` o `test_gui.py`, que ya se
  saltan solos.
