# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Perfil longitudinal automático sobre entidades seleccionadas.

Equivalente al 'Auto Longitudinal Profile': aplica una curva vertical cóncava
(pendientes de cabeza y pie especificadas) a las polilíneas 3D seleccionadas
en la capa activa (crestas, subcrestas, vaguadas...), opcionalmente dejando
una longitud convexa en cabeza para alojar material sobrante ('joroba').
Tras editar, vuelve a ejecutar 'Dibujar curvas de nivel GeoFluv' para
regenerar la superficie con las líneas modificadas.
"""

import math

from qgis.PyQt.QtWidgets import (
    QDialog, QFormLayout, QDoubleSpinBox, QCheckBox, QDialogButtonBox, QLabel,
)
from qgis.core import QgsGeometry, QgsPoint

from ..core.profile import disenar_perfil


class AutoPerfilDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Auto Longitudinal Profile")
        f = QFormLayout(self)
        self.sp_cab = QDoubleSpinBox(); self.sp_cab.setRange(-60, 0)
        self.sp_cab.setValue(-12.0); self.sp_cab.setSuffix(" %")
        self.sp_pie = QDoubleSpinBox(); self.sp_pie.setRange(-60, 0)
        self.sp_pie.setValue(-2.0); self.sp_pie.setSuffix(" %")
        self.chk_convexo = QCheckBox("Connect to Ridge: convex curve at top (to place extra material)")
        self.sp_convexo = QDoubleSpinBox(); self.sp_convexo.setRange(0, 1000)
        self.sp_convexo.setValue(25.0); self.sp_convexo.setSuffix(" m")
        self.sp_convexo.setEnabled(False)
        self.chk_convexo.toggled.connect(self.sp_convexo.setEnabled)
        f.addRow(QLabel("Applies to the SELECTED features of the active layer.\n"
                        "The highest end is taken as the top."))
        f.addRow("Top Slope:", self.sp_cab)
        f.addRow("Bottom Slope:", self.sp_pie)
        f.addRow(self.chk_convexo)
        f.addRow("Convex Curve Length:", self.sp_convexo)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        f.addRow(bb)


def aplicar_auto_perfil(capa, s_cab_pct, s_pie_pct, convexo_m=0.0):
    """Aplica la curva vertical a las entidades seleccionadas. Devuelve nº editadas."""
    n_ed = 0
    capa.startEditing()
    for feat in capa.selectedFeatures():
        g = feat.geometry()
        try:
            pts = [QgsPoint(v.x(), v.y(),
                            v.z() if v.z() == v.z() else 0.0)  # NaN → 0
                   for v in g.vertices()]
        except Exception:
            continue
        if len(pts) < 2:
            continue
        # orientar: cabeza = extremo más alto
        if pts[0].z() < pts[-1].z():
            pts = list(reversed(pts))
        L = sum(math.hypot(b.x() - a.x(), b.y() - a.y())
                for a, b in zip(pts[:-1], pts[1:]))
        if L <= 0:
            continue
        z0, z1 = pts[0].z(), pts[-1].z()
        perfil = disenar_perfil(max(L - convexo_m, 1.0), z0, z1,
                                s_cab_pct / 100.0, s_pie_pct / 100.0)
        nuevos, acum = [], 0.0
        for i, p in enumerate(pts):
            if i > 0:
                acum += math.hypot(p.x() - pts[i - 1].x(), p.y() - pts[i - 1].y())
            if acum <= convexo_m:
                z = z0                      # meseta convexa en cabeza
            else:
                z = perfil.z(acum - convexo_m)
            nuevos.append(QgsPoint(p.x(), p.y(), z))
        capa.changeGeometry(feat.id(), QgsGeometry.fromPolyline(nuevos))
        n_ed += 1
    capa.commitChanges()
    capa.triggerRepaint()
    return n_ed
