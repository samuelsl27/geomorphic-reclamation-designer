# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Configuracion de pytest.

Los tests del motor puro (libro, hidraulica, divisorias, checks, optimizador) no
necesitan QGIS y corren en cualquier sitio, incluida la CI. Los de integracion y
los de interfaz si lo necesitan: se saltan solos con un mensaje claro en vez de
romper la ejecucion entera.
"""

import os
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(RAIZ, "src")
PAQUETE = os.path.join(SRC, "geomorphic_reclamation_designer")

# Dos entradas a proposito:
#   src/                    -> permite  import geomorphic_reclamation_designer.core.x   (integracion)
#   src/geomorphic_reclamation_designer/     -> permite  from core.x import y           (motor puro)
# Los tests del motor se escribieron para importar el modulo aislado, sin pasar
# por el __init__ del complemento, que arrastraria QGIS.
for _p in (PAQUETE, SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def hay_qgis():
    try:
        import qgis.core  # noqa: F401
    except Exception:
        return False
    return True


HAY_QGIS = hay_qgis()

necesita_qgis = pytest.mark.skipif(
    not HAY_QGIS,
    reason="necesita una instalacion de QGIS con python3-qgis en el PYTHONPATH")


# Estos dos arrancan una QgsApplication de verdad en el propio import, asi que
# no basta con marcarlos para saltar: hay que NO recolectarlos. Ademas, los
# tests del motor puro registran un `qgis` falso en sys.modules, con lo que sin
# QGIS real estos se encontrarian el doble y reventarian con un error confuso.
NECESITAN_QGIS = ("test_integracion.py", "test_gui.py")

collect_ignore = [] if HAY_QGIS else list(NECESITAN_QGIS)


def pytest_report_header(config):
    estado = ("disponible" if HAY_QGIS else
              "NO disponible (se saltan integracion e interfaz)")
    return f"QGIS: {estado}"
