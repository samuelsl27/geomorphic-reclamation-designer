# Generar el ZIP instalable en QGIS

## Lo corto

```bash
python scripts/build_zip.py
```

→ `dist/geomorphic_reclamation_designer_v1.0.17.zip`

En QGIS: *Complementos → Administrar e instalar complementos → **Instalar a
partir de ZIP*** → elegir el fichero → *Instalar complemento*.

## Opciones

```bash
python scripts/build_zip.py                    # solo el zip
python scripts/build_zip.py --guia             # regenera la guía antes
python scripts/build_zip.py --deploy           # además lo instala en el perfil
python scripts/build_zip.py --salida D:\entregas
```

---

## Qué hace exactamente

1. **Comprueba que la versión coincide en los cuatro sitios.** Si no, **falla** y
   te dice cuál está descoordinado. La versión vive en:

   | Fichero | Para qué |
   |---|---|
   | `src/geomorphic_reclamation_designer/metadata.txt` | lo que lee QGIS |
   | `src/geomorphic_reclamation_designer/__init__.py` | `__version__` |
   | `src/geomorphic_reclamation_designer/gui/dock.py` | lo que muestra el panel |
   | `scripts/genera_guia.py` | lo que imprime la guía |

   Los cuatro a la vez: `python scripts/bump_version.py 1.0.18`.

2. **Comprueba que están los ficheros esenciales**: `__init__.py`,
   `metadata.txt`, `plugin.py`, `icon.png`. Avisa si falta `help/guide.html`.

3. **Compila todo el Python** (en memoria, sin escribir `.pyc`). Un error de
   sintaxis se descubre aquí y no cuando QGIS se niega a cargar el complemento
   con un mensaje que no ayuda.

4. **Empaqueta** con una única carpeta raíz `geomorphic_reclamation_designer/`, excluyendo
   `__pycache__`, `*.pyc`, `tests/`, `.git`, ficheros de editor y temporales.

5. **Verifica el zip resultante**: que no esté corrupto, que tenga **una sola**
   carpeta raíz, que contenga `__init__.py` y `metadata.txt`, y que no se haya
   colado ningún `__pycache__`.

Ese paso 5 existe porque un zip con dos carpetas raíz QGIS lo instala mal y el
mensaje de error no dice por qué.

---

## La estructura que QGIS espera

```
geomorphic_reclamation_designer_v1.0.17.zip
└── geomorphic_reclamation_designer/          ← UNA sola carpeta raíz, y su nombre importa:
    ├── __init__.py          ←  es el nombre del módulo Python del complemento
    ├── metadata.txt
    ├── plugin.py
    ├── icon.png
    ├── core/
    ├── gui/
    └── help/guide.html
```

QGIS descomprime en
`…/QGIS4/profiles/default/python/plugins/geomorphic_reclamation_designer/` e importa
`geomorphic_reclamation_designer`, que debe exponer `classFactory(iface)`.

---

## Instalación manual (sin zip)

Para desarrollo es más cómodo copiar directamente:

```bash
python scripts/deploy_local.py            # detecta el perfil y copia
python scripts/deploy_local.py --watch    # recopia cada vez que guardas
python scripts/deploy_local.py --listar   # qué perfiles encuentra
```

Después, en QGIS:

```python
from qgis import utils
utils.reloadPlugin("geomorphic_reclamation_designer")
```

> Si has tocado `core/params.py`, **reinicia QGIS**: la recarga en caliente deja
> `GlobalSettings` viejo en memoria.

### El perfil correcto

Si conviven QGIS3 y QGIS4, asegúrate de instalar en el perfil activo:

```
%APPDATA%\QGIS\QGIS4\profiles\default\python\plugins
```

`deploy_local.py` prefiere QGIS4 y avisa si hay más. Para salir de dudas, en la
consola de QGIS:

```python
from qgis.core import QgsApplication
print(QgsApplication.qgisSettingsDirPath())
```

---

## Regenerar la guía

`src/geomorphic_reclamation_designer/help/guide.html` es **generado**. No lo edites: se
sobrescribe.

```bash
# edita el TEXTO en scripts/guia_datos.py
python scripts/genera_guia.py
```

`guia_datos.py` contiene `PESTANAS`, con las mismas pestañas del programa; cada
entrada es `(nombre_del_ajuste, texto_en, texto_es)`. Los bloques cuyo nombre
empieza por `__` salen como nota destacada en vez de como ficha de ajuste.

La CI comprueba que el HTML confirmado coincide con lo que produce el generador;
si no, falla y te pide que lo regeneres.

---

## Publicar una release

```bash
python scripts/bump_version.py patch
# redactar CHANGELOG.md y actualizar context/
python scripts/genera_guia.py
ruff check . && pytest -q
python scripts/build_zip.py
git add -A && git commit -m "chore: versión 1.0.19"
git tag -a v1.0.19 -m "v1.0.19"
git push && git push --tags
```

`.github/workflows/release.yml` se dispara con la etiqueta: pasa los tests,
comprueba que la etiqueta coincide con `metadata.txt`, construye el zip y
**publica la release con el zip adjunto** y las notas extraídas del CHANGELOG.

> **Numeración**: el proyecto va por **1.0.x** (`bump_version.py patch`)
> mientras no haya nada definitivo. No uses `minor` sin decidirlo antes: una vez
> publicada una 1.1.0, cualquier 1.0.x posterior deja de ofrecerse como
> actualización en el gestor de complementos de QGIS, porque es una versión
> *anterior*.

> **Etiquetas**: `git push --tags` sube **todas** las etiquetas locales, así que
> dispara el workflow también para las antiguas que aún no estuvieran en el
> remoto —y crea una release por cada una—. Si solo quieres publicar la nueva,
> usa `git push origin v1.0.19`. Comprueba después cuál quedó marcada como
> *Latest*: GitHub marca la última creada, no la de número más alto.

---

## Publicar en el repositorio oficial de QGIS

Cuando el complemento salga de `experimental`:

1. En `metadata.txt`: quitar `experimental=True` y comprobar que `homepage`,
   `tracker` y `repository` apuntan al GitHub real.
2. Probar en **3.22**, **3.34 LTR**, **3.40** y **4.2**.
3. Crear cuenta en [plugins.qgis.org](https://plugins.qgis.org/) y subir el zip.
4. Las versiones siguientes se pueden subir por API con
   [`qgis-plugin-ci`](https://github.com/opengisch/qgis-plugin-ci) desde el
   workflow de release.

---

## Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `build_zip.py` falla por versiones | descoordinadas | `python scripts/bump_version.py <version>` |
| QGIS: *"El complemento no es válido"* | falta `__init__.py` con `classFactory`, o el zip tiene dos carpetas raíz | reconstruir con `build_zip.py`, que lo verifica |
| El complemento no aparece tras instalar | `qgisMinimumVersion` mayor que tu QGIS | mirar `metadata.txt` |
| Los cambios no se ven | copiado al perfil equivocado | `QgsApplication.qgisSettingsDirPath()` |
| `AttributeError` en un ajuste nuevo | recarga en caliente tras tocar `params.py` | reiniciar QGIS |
| La guía sale en inglés y no cambia | HTML antiguo en caché | regenerar y recargar; ver bug B-008 |
| El zip pesa de más | se coló `__pycache__` | `build_zip.py` lo detecta y falla |
