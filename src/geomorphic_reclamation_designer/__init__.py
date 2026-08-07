# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Geomorphic Reclamation Designer — diseño de restauración geomorfológica en QGIS.

Copyright (C) 2026 Samuel Saez Lopez y colaboradores.
Licencia AGPL-3.0-or-later. Ver LICENSE en la raíz del repositorio.

El código histórico usa el prefijo interno `GeoFluv`/`GF_` porque el método de
referencia es el fluvio-geomórfico publicado por Bugosh (Natural Regrade con
GeoFluv™, marca de su titular). Se mantiene por compatibilidad con los
proyectos ya creados; no implica relación con Carlson Software.
"""

__version__ = "1.1.0"
__author__ = "Samuel Saez Lopez"
__license__ = "AGPL-3.0-or-later"


def classFactory(iface):
    from .plugin import GeoFluvQPlugin
    return GeoFluvQPlugin(iface)
