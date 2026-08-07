# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Visor de perfil longitudinal (equivalente al 'View Longitudinal Profile').

Dibuja el perfil de diseño (azul) y, si hay DEM, el perfil del terreno
original (gris) sobre la misma traza de valle. Al mover el cursor se muestran
estación, cota y pendiente. Combo de exageración vertical: Ajustar, x1, x2,
x5, x10.
"""

from qgis.PyQt.QtCore import Qt, QPointF
from qgis.PyQt.QtGui import QPainter, QPen, QColor, QPolygonF, QFont
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QWidget,
    QDialogButtonBox,
)


class _LienzoPerfil(QWidget):
    MARGEN = 45

    def __init__(self, perfil, terreno=None, parent=None):
        super().__init__(parent)
        self.perfil = perfil          # PerfilLongitudinal
        self.terreno = terreno or []  # [(s, z)]
        self.exag = 0.0               # 0 = ajustar
        self.cursor_s = None
        self.setMouseTracking(True)
        self.setMinimumSize(560, 300)
        self.lb_info = None

    # ---------- transformación ----------
    def _rangos(self):
        ss = self.perfil.estaciones
        zz = list(self.perfil.cotas) + [z for _, z in self.terreno if z is not None]
        s0, s1 = 0.0, (ss[-1] if ss else 1.0)
        z0, z1 = (min(zz), max(zz)) if zz else (0.0, 1.0)
        if z1 - z0 < 1e-6:
            z1 = z0 + 1.0
        return s0, s1, z0, z1

    def _map(self, s, z):
        s0, s1, z0, z1 = self._rangos()
        w = self.width() - 2 * self.MARGEN
        h = self.height() - 2 * self.MARGEN
        px = self.MARGEN + (s - s0) / (s1 - s0) * w
        if self.exag <= 0:                       # ajustar
            py = self.height() - self.MARGEN - (z - z0) / (z1 - z0) * h
        else:                                    # misma escala x, exagerada
            esc_x = w / (s1 - s0)
            py = self.height() - self.MARGEN - (z - z0) * esc_x * self.exag
        return QPointF(px, py)

    def _s_desde_px(self, px):
        s0, s1, _, _ = self._rangos()
        w = self.width() - 2 * self.MARGEN
        t = (px - self.MARGEN) / w if w > 0 else 0
        return max(s0, min(s1, s0 + t * (s1 - s0)))

    # ---------- eventos ----------
    def mouseMoveEvent(self, ev):
        px = ev.position().x() if hasattr(ev, "position") else ev.pos().x()
        self.cursor_s = self._s_desde_px(px)
        if self.lb_info is not None and self.perfil.estaciones:
            s = self.cursor_s
            z = self.perfil.z(s)
            p = self.perfil.pendiente(s) * 100.0
            self.lb_info.setText(f"Chainage: {s:,.1f} m    Elevation: {z:,.2f} m    "
                                 f"Slope: {p:,.2f} %")
        self.update()

    def paintEvent(self, ev):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.fillRect(self.rect(), QColor("#ffffff"))
        if not self.perfil.estaciones:
            return
        s0, s1, z0, z1 = self._rangos()

        # rejilla y ejes
        qp.setPen(QPen(QColor("#dddddd"), 1))
        n_t = 8
        f = QFont(); f.setPointSize(8); qp.setFont(f)
        for i in range(n_t + 1):
            s = s0 + i * (s1 - s0) / n_t
            p = self._map(s, z0)
            qp.drawLine(int(p.x()), self.MARGEN, int(p.x()), self.height() - self.MARGEN)
            qp.setPen(QPen(QColor("#555555")))
            qp.drawText(int(p.x()) - 18, self.height() - self.MARGEN + 15, f"{s:,.0f}")
            qp.setPen(QPen(QColor("#dddddd"), 1))
        for i in range(5):
            z = z0 + i * (z1 - z0) / 4
            p = self._map(s0, z)
            qp.drawLine(self.MARGEN, int(p.y()), self.width() - self.MARGEN, int(p.y()))
            qp.setPen(QPen(QColor("#555555")))
            qp.drawText(2, int(p.y()) + 4, f"{z:,.1f}")
            qp.setPen(QPen(QColor("#dddddd"), 1))

        # terreno original
        if self.terreno:
            qp.setPen(QPen(QColor("#999999"), 1, Qt.PenStyle.DashLine))
            poly = QPolygonF([self._map(s, z) for s, z in self.terreno if z is not None])
            qp.drawPolyline(poly)

        # perfil de diseño
        qp.setPen(QPen(QColor("#0055cc"), 2))
        poly = QPolygonF([self._map(s, z) for s, z in
                          zip(self.perfil.estaciones, self.perfil.cotas)])
        qp.drawPolyline(poly)

        # cursor
        if self.cursor_s is not None:
            z = self.perfil.z(self.cursor_s)
            p = self._map(self.cursor_s, z)
            qp.setPen(QPen(QColor("#cc0000"), 1))
            qp.drawLine(int(p.x()), self.MARGEN, int(p.x()), self.height() - self.MARGEN)
            qp.setBrush(QColor("#cc0000"))
            qp.drawEllipse(p, 3, 3)


class ProfileDialog(QDialog):
    def __init__(self, nombre_canal, perfil, terreno=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"View Longitudinal Profile   {nombre_canal}")
        lay = QVBoxLayout(self)

        fila = QHBoxLayout()
        fila.addWidget(QLabel("Vertical Exaggeration:"))
        self.cb = QComboBox()
        self.cb.addItems(["Fit", "x1", "x2", "x5", "x10"])
        fila.addWidget(self.cb)
        fila.addStretch()
        lay.addLayout(fila)

        self.lienzo = _LienzoPerfil(perfil, terreno)
        lay.addWidget(self.lienzo, 1)

        self.lb_info = QLabel("Move the cursor over the profile...")
        self.lienzo.lb_info = self.lb_info
        lay.addWidget(self.lb_info)
        if terreno:
            lay.addWidget(QLabel("<span style='color:#888'>- - original ground&nbsp;&nbsp;"
                                 "<span style='color:#05c'>——</span> perfil de diseño</span>"))

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)

        def _exag(idx):
            self.lienzo.exag = [0.0, 1.0, 2.0, 5.0, 10.0][idx]
            self.lienzo.update()
        self.cb.currentIndexChanged.connect(_exag)
        self.resize(760, 460)
