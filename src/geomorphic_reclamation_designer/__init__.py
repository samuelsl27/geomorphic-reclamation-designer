# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Geomorphic Reclamation Designer — diseño de restauración geomorfológica en QGIS.

Copyright (C) 2026 Samuel Saez Lopez y colaboradores.
Licencia AGPL-3.0-or-later. Ver LICENSE en la raíz del repositorio.

El método de referencia es el fluvio-geomórfico publicado por Bugosh (Natural
Regrade® con GeoFluv™, marcas de sus titulares), citado como fuente y nada
más: esto es una implementación independiente y libre del método publicado, sin
relación con Carlson Software.

Nada de cara al usuario lleva la marca (ADR-016): las capas van con el prefijo
`GRD_` y el proyecto se guarda como `.grd.json`. Sobreviven algunos
identificadores internos históricos (`GeoFluvBuilder`, `GeoFluvProject`,
`GeoFluvQPlugin`) que no se muestran en ninguna parte.
"""

__version__ = "1.0.23"
__author__ = "Samuel Saez Lopez"
__license__ = "AGPL-3.0-or-later"


def classFactory(iface):
    from .plugin import GeoFluvQPlugin
    return GeoFluvQPlugin(iface)
