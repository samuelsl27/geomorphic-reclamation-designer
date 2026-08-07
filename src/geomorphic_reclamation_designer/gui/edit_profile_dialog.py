# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""'Edit Longitudinal Profile -- Double Click to Adjust Profile'.

Interactive profile editor, like the original: the profile of the selected 3D
polyline is shown; double-clicking raises/lowers the profile to the clicked
elevation at that chainage, blending the change over 'Blend %' of the line
length on each side. OK writes the new Z values back to the feature's
vertices (editing must then be followed by 'Draw Design Contours' to rebuild
the surface)."""

import math

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPainter, QPen, QColor, QFont
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QSlider, QPushButton, QWidget,
)
from qgis.core import QgsPoint, QgsGeometry


def _suavizado(w):
    """Peso suave (smoothstep) para repartir el ajuste."""
    w = max(0.0, min(1.0, w))
    return w * w * (3.0 - 2.0 * w)


class _LienzoEdicion(QWidget):
    """Profile canvas: draws original + edited profile; double click edits."""

    def __init__(self, dialogo, parent=None):
        super().__init__(parent)
        self.d = dialogo
        self.setMouseTracking(True)
        self.setMinimumSize(560, 260)
        self._cursor = None

    # ---------- coordenadas ----------
    def _rangos(self):
        s0, s1 = 0.0, max(self.d.ss[-1], 1e-6)
        zs = self.d.zs + self.d.zs_orig
        z0, z1 = min(zs), max(zs)
        if z1 - z0 < 1e-6:
            z1 = z0 + 1.0
        # exageración: se aplica dibujando el rango z sin proporción con x
        margen = 0.08 * (z1 - z0)
        return s0, s1, z0 - margen, z1 + margen

    def _a_pantalla(self, s, z):
        s0, s1, z0, z1 = self._rangos()
        W, H = self.width() - 70, self.height() - 40
        x = 55 + (s - s0) / (s1 - s0) * W
        y = 10 + (1.0 - (z - z0) / (z1 - z0)) * H
        return x, y

    def _de_pantalla(self, x, y):
        s0, s1, z0, z1 = self._rangos()
        W, H = self.width() - 70, self.height() - 40
        s = s0 + (x - 55) / max(W, 1) * (s1 - s0)
        z = z0 + (1.0 - (y - 10) / max(H, 1)) * (z1 - z0)
        return s, z

    # ---------- eventos ----------
    def mouseMoveEvent(self, e):
        pos = e.position() if hasattr(e, "position") else e.pos()
        s, z = self._de_pantalla(pos.x(), pos.y())
        self._cursor = (s, z)
        self.d.actualizar_info(s)
        self.update()

    def mouseDoubleClickEvent(self, e):
        pos = e.position() if hasattr(e, "position") else e.pos()
        s_c, z_c = self._de_pantalla(pos.x(), pos.y())
        self.d.editar(s_c, z_c)
        self.update()

    # ---------- pintura ----------
    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#000000"))
        f = QFont(); f.setPointSize(7); p.setFont(f)
        s0, s1, z0, z1 = self._rangos()

        # rejilla / ticks
        p.setPen(QPen(QColor("#00c8c8"), 1))
        n_t = 6
        for i in range(n_t + 1):
            s = s0 + i / n_t * (s1 - s0)
            x, y = self._a_pantalla(s, z0)
            p.drawLine(int(x), self.height() - 30, int(x), self.height() - 26)
            p.drawText(int(x) - 12, self.height() - 14, f"{s:.0f}")
        for i in range(4 + 1):
            z = z0 + i / 4 * (z1 - z0)
            x, y = self._a_pantalla(s0, z)
            p.drawLine(50, int(y), 55, int(y))
            p.drawText(2, int(y) + 3, f"{z:.1f}")

        # perfil original (si toggled)
        if self.d.chk_orig.isChecked():
            p.setPen(QPen(QColor("#666666"), 1, Qt.PenStyle.DashLine
                          if hasattr(Qt, "PenStyle") else Qt.DashLine))
            pts = [self._a_pantalla(s, z)
                   for s, z in zip(self.d.ss, self.d.zs_orig)]
            for a, b in zip(pts[:-1], pts[1:]):
                p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))

        # perfil editado
        p.setPen(QPen(QColor("#ffffff"), 2))
        pts = [self._a_pantalla(s, z) for s, z in zip(self.d.ss, self.d.zs)]
        for a, b in zip(pts[:-1], pts[1:]):
            p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))

        # cursor
        if self._cursor is not None:
            x, _ = self._a_pantalla(self._cursor[0], z0)
            p.setPen(QPen(QColor("#3060ff"), 1))
            p.drawLine(int(x), 10, int(x), self.height() - 30)
        p.end()


class EditProfileDialog(QDialog):
    """Edits the Z profile of one 3D polyline feature."""

    def __init__(self, nombre, vertices, parent=None):
        """vertices: [(x, y, z)] of the feature (3D)."""
        super().__init__(parent)
        self.setWindowTitle(f"Edit Longitudinal Profile -- Double Click to "
                            f"Adjust Profile   {nombre}")
        self.verts = vertices
        # chainage 2D
        self.ss = [0.0]
        for a, b in zip(vertices[:-1], vertices[1:]):
            self.ss.append(self.ss[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        self.zs_orig = [v[2] for v in vertices]
        self.zs = list(self.zs_orig)

        lay = QVBoxLayout(self)
        self.lienzo = _LienzoEdicion(self)
        lay.addWidget(self.lienzo, 1)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("Vertical Exaggeration: Fit"))
        self.chk_orig = QCheckBox("Original Line"); self.chk_orig.setChecked(True)
        self.chk_orig.toggled.connect(self.lienzo.update)
        fila.addWidget(self.chk_orig)
        fila.addWidget(QLabel("Blend %:"))
        self.sl_blend = QSlider(Qt.Orientation.Horizontal
                                if hasattr(Qt, "Orientation") else Qt.Horizontal)
        self.sl_blend.setRange(1, 50); self.sl_blend.setValue(5)
        self.sl_blend.setMaximumWidth(140)
        fila.addWidget(self.sl_blend)
        self.lb_blend = QLabel("5 %")
        self.sl_blend.valueChanged.connect(
            lambda v: self.lb_blend.setText(f"{v} %"))
        fila.addWidget(self.lb_blend)
        fila.addStretch()
        lay.addLayout(fila)

        fila2 = QHBoxLayout()
        self.lb_info = QLabel("Chainage: -    Elevation: -    Slope: -")
        fila2.addWidget(self.lb_info)
        fila2.addStretch()
        b_reset = QPushButton("Reset"); b_reset.clicked.connect(self._reset)
        b_ok = QPushButton("OK"); b_ok.clicked.connect(self.accept)
        b_cancel = QPushButton("Cancel"); b_cancel.clicked.connect(self.reject)
        for b in (b_reset, b_ok, b_cancel):
            fila2.addWidget(b)
        lay.addLayout(fila2)
        self.resize(720, 380)

    # ---------- edición ----------
    def editar(self, s_c, z_c):
        """Double click: move the profile to z_c at chainage s_c, blending
        over Blend % of the total length to each side."""
        L = max(self.ss[-1], 1e-6)
        Lb = max(self.sl_blend.value() / 100.0 * L, 1e-6)
        # z actual en s_c (interpolado)
        z_act = self._z_en(s_c)
        delta = z_c - z_act
        for i, s in enumerate(self.ss):
            w = 1.0 - abs(s - s_c) / Lb
            if w > 0:
                self.zs[i] += _suavizado(w) * delta

    def _z_en(self, s):
        import bisect
        i = min(max(bisect.bisect_left(self.ss, s), 1), len(self.ss) - 1)
        s0, s1 = self.ss[i - 1], self.ss[i]
        t = (s - s0) / (s1 - s0) if s1 > s0 else 0.0
        return self.zs[i - 1] + t * (self.zs[i] - self.zs[i - 1])

    def _reset(self):
        self.zs = list(self.zs_orig)
        self.lienzo.update()

    def actualizar_info(self, s):
        z = self._z_en(s)
        ds = max(self.ss[-1] / 100.0, 0.5)
        pend = (self._z_en(min(s + ds, self.ss[-1])) -
                self._z_en(max(s - ds, 0.0))) / (2 * ds) * 100.0
        self.lb_info.setText(f"Chainage: {s:,.1f} m    Elevation: {z:,.2f} m    "
                             f"Slope: {pend:,.2f} %")

    # ---------- aplicar ----------
    def aplicar_a_capa(self, capa, fid):
        """Writes the edited Z back to the feature's vertices."""
        f = capa.getFeature(fid)
        if not f.isValid():
            return False
        nuevos = [QgsPoint(v[0], v[1], z) for v, z in zip(self.verts, self.zs)]
        capa.startEditing()
        capa.changeGeometry(fid, QgsGeometry.fromPolyline(nuevos))
        capa.commitChanges()
        capa.triggerRepaint()
        return True
