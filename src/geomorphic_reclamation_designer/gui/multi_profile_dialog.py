# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""'View Longitudinal Profile' de CUALQUIER conjunto de entidades seleccionadas.

Cada entidad 3D seleccionada (canal, cresta, subcresta, vaguada, curva, borde
de canal…) se convierte en una serie (estación, cota) recorriendo su geometría,
y todas se dibujan superpuestas con un color por serie. La leyenda identifica
cada elemento por CAPA y FID, tal y como aparece en la tabla de atributos.

Si hay un DEM disponible se añade, en gris discontinuo, el perfil del terreno
original bajo la traza de la primera serie (o de la serie resaltada), para
comparar diseño y terreno.
"""

import math

from qgis.PyQt.QtCore import Qt, QPointF
from qgis.PyQt.QtGui import QPainter, QPen, QColor, QPolygonF, QFont
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QWidget,
    QDialogButtonBox, QListWidget, QListWidgetItem, QSplitter,
)

COLORES = ["#0077ff", "#cc0000", "#e6a800", "#2e9e46", "#8000c0", "#00a0a0",
           "#ff6600", "#666666", "#b3007a", "#336699"]


def serie_de_geometria(geom):
    """[(s, z)] recorriendo la geometría 3D: s = distancia acumulada en planta."""
    pts = []
    try:
        vs = list(geom.vertices())
    except Exception:
        return pts
    s = 0.0
    ant = None
    for v in vs:
        z = v.z()
        if z != z:            # NaN
            z = None
        if ant is not None:
            s += math.hypot(v.x() - ant[0], v.y() - ant[1])
        ant = (v.x(), v.y())
        if z is not None:
            pts.append((s, z))
    return pts


def traza_de_geometria(geom, paso=5.0):
    """[(s, x, y)] muestreada cada 'paso' m, para consultar el DEM."""
    out = []
    try:
        vs = [(v.x(), v.y()) for v in geom.vertices()]
    except Exception:
        return out
    if len(vs) < 2:
        return out
    s = 0.0
    out.append((0.0, vs[0][0], vs[0][1]))
    for a, b in zip(vs[:-1], vs[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(d // paso))
        for k in range(1, n + 1):
            t = k / n
            out.append((s + t * d, a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
        s += d
    return out


class _Lienzo(QWidget):
    MARGEN = 55

    def __init__(self, series, parent=None):
        super().__init__(parent)
        self.series = series        # [{'etiqueta','puntos','color','visible','terreno'}]
        self.exag = 0.0
        self.cursor_s = None
        self.al_mover = None        # callback(estacion) -> marcador en planta
        self.setMouseTracking(True)
        self.setMinimumSize(640, 340)
        self.lb_info = None

    def _visibles(self):
        return [s for s in self.series if s.get("visible", True) and s["puntos"]]

    def _rangos(self):
        ss, zz = [], []
        for s in self._visibles():
            ss += [p[0] for p in s["puntos"]]
            zz += [p[1] for p in s["puntos"]]
            for p in (s.get("terreno") or []):
                zz.append(p[1]); ss.append(p[0])
        if not ss:
            return 0.0, 1.0, 0.0, 1.0
        s0, s1 = 0.0, max(ss)
        z0, z1 = min(zz), max(zz)
        if s1 - s0 < 1e-6:
            s1 = s0 + 1.0
        if z1 - z0 < 1e-6:
            z1 = z0 + 1.0
        return s0, s1, z0, z1

    def _map(self, s, z):
        s0, s1, z0, z1 = self._rangos()
        w = self.width() - 2 * self.MARGEN
        h = self.height() - 2 * self.MARGEN
        px = self.MARGEN + (s - s0) / (s1 - s0) * w
        if self.exag <= 0:
            py = self.height() - self.MARGEN - (z - z0) / (z1 - z0) * h
        else:
            esc_x = w / (s1 - s0)
            py = self.height() - self.MARGEN - (z - z0) * esc_x * self.exag
        return QPointF(px, py)

    def mouseMoveEvent(self, ev):
        s0, s1, _, _ = self._rangos()
        w = self.width() - 2 * self.MARGEN
        t = (ev.position().x() if hasattr(ev, "position") else ev.x())
        frac = (t - self.MARGEN) / w if w > 0 else 0
        self.cursor_s = max(s0, min(s1, s0 + frac * (s1 - s0)))
        if self.lb_info is not None:
            txt = f"station {self.cursor_s:,.1f} m"
            for se in self._visibles()[:4]:
                z = self._z_en(se["puntos"], self.cursor_s)
                if z is not None:
                    txt += f"   |   {se['etiqueta']}: {z:,.2f} m"
            self.lb_info.setText(txt)
        if self.al_mover is not None:
            try:
                self.al_mover(self.cursor_s)
            except Exception:
                pass
        self.update()

    @staticmethod
    def _z_en(puntos, s):
        if not puntos:
            return None
        if s <= puntos[0][0]:
            return puntos[0][1]
        if s >= puntos[-1][0]:
            return puntos[-1][1]
        for a, b in zip(puntos[:-1], puntos[1:]):
            if a[0] <= s <= b[0]:
                t = (s - a[0]) / (b[0] - a[0]) if b[0] > a[0] else 0
                return a[1] + t * (b[1] - a[1])
        return None

    def paintEvent(self, _ev):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.fillRect(self.rect(), QColor("#ffffff"))
        s0, s1, z0, z1 = self._rangos()
        # marco y rejilla
        qp.setPen(QPen(QColor("#cccccc"), 1))
        f = QFont(); f.setPointSize(7); qp.setFont(f)
        for i in range(6):
            z = z0 + (z1 - z0) * i / 5.0
            p = self._map(s0, z)
            qp.drawLine(QPointF(self.MARGEN, p.y()),
                        QPointF(self.width() - self.MARGEN, p.y()))
            qp.setPen(QPen(QColor("#666666")))
            qp.drawText(QPointF(4, p.y() + 3), f"{z:,.1f}")
            qp.setPen(QPen(QColor("#cccccc"), 1))
        for i in range(6):
            s = s0 + (s1 - s0) * i / 5.0
            p = self._map(s, z0)
            qp.drawLine(QPointF(p.x(), self.MARGEN),
                        QPointF(p.x(), self.height() - self.MARGEN))
            qp.setPen(QPen(QColor("#666666")))
            qp.drawText(QPointF(p.x() - 14, self.height() - self.MARGEN + 14),
                        f"{s:,.0f}")
            qp.setPen(QPen(QColor("#cccccc"), 1))
        # series
        for se in self._visibles():
            terreno = se.get("terreno") or []
            if terreno:
                qp.setPen(QPen(QColor("#999999"), 1, Qt.PenStyle.DashLine))
                qp.drawPolyline(QPolygonF([self._map(s, z) for s, z in terreno]))
            qp.setPen(QPen(QColor(se["color"]), 2))
            qp.drawPolyline(QPolygonF([self._map(s, z) for s, z in se["puntos"]]))
        # cursor
        if self.cursor_s is not None:
            qp.setPen(QPen(QColor("#ff8800"), 1, Qt.PenStyle.DashLine))
            p = self._map(self.cursor_s, z0)
            qp.drawLine(QPointF(p.x(), self.MARGEN),
                        QPointF(p.x(), self.height() - self.MARGEN))
        qp.end()


class MultiProfileDialog(QDialog):
    """series: [{'etiqueta', 'puntos':[(s,z)], 'terreno':[(s,z)]|None}]"""

    def __init__(self, titulo, series, parent=None, iface=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.iface = iface
        self._marcador = None
        for i, se in enumerate(series):
            se.setdefault("color", COLORES[i % len(COLORES)])
            se.setdefault("visible", True)
        v = QVBoxLayout(self)
        h = QHBoxLayout()
        h.addWidget(QLabel("Vertical exaggeration:"))
        self.cb = QComboBox()
        for t in ("Fit", "x1", "x2", "x5", "x10"):
            self.cb.addItem(t)
        h.addWidget(self.cb); h.addStretch(1)
        v.addLayout(h)

        sp = QSplitter(Qt.Orientation.Horizontal)
        self.lienzo = _Lienzo(series)
        sp.addWidget(self.lienzo)
        self.lista = QListWidget()
        self.lista.setMaximumWidth(260)
        for se in series:
            it = QListWidgetItem(se["etiqueta"])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            it.setForeground(QColor(se["color"]))
            self.lista.addItem(it)
        self.lista.itemChanged.connect(self._visibilidad)
        sp.addWidget(self.lista)
        v.addWidget(sp)

        self.lb = QLabel("Move the cursor over the profile.")
        self.lienzo.lb_info = self.lb
        v.addWidget(self.lb)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject); bb.accepted.connect(self.accept)
        v.addWidget(bb)
        self.cb.currentTextChanged.connect(self._exag)
        self.lienzo.al_mover = self._marcar_en_planta
        self.resize(960, 560)

    # ---------------- marcador en planta ----------------
    def _crear_marcador(self):
        """Círculo rojo sobre el lienzo del mapa. Se crea a la primera, para no
        tocar el canvas si el usuario nunca pasa el cursor por el perfil."""
        if self._marcador is not None or self.iface is None:
            return
        try:
            from qgis.gui import QgsRubberBand
            from qgis.core import QgsWkbTypes
            rb = QgsRubberBand(self.iface.mapCanvas(),
                               QgsWkbTypes.PointGeometry)
            rb.setColor(QColor(255, 0, 0))
            rb.setFillColor(QColor(255, 0, 0, 0))
            rb.setWidth(3)
            rb.setIcon(QgsRubberBand.ICON_CIRCLE)
            rb.setIconSize(12)
            self._marcador = rb
        except Exception:
            self._marcador = None

    @staticmethod
    def _xy_en(traza, s):
        """(x, y) de la traza en la estación s, interpolando entre muestras."""
        if not traza:
            return None
        if s <= traza[0][0]:
            return traza[0][1], traza[0][2]
        for (s0, x0, y0), (s1, x1, y1) in zip(traza[:-1], traza[1:]):
            if s0 <= s <= s1:
                t = (s - s0) / max(s1 - s0, 1e-9)
                return x0 + t * (x1 - x0), y0 + t * (y1 - y0)
        return traza[-1][1], traza[-1][2]

    def _marcar_en_planta(self, s):
        """Un círculo rojo sobre el punto de la línea en el que está el cursor
        del perfil: al deslizar por el perfil se ve en planta qué zona es."""
        if self.iface is None:
            return
        self._crear_marcador()
        if self._marcador is None:
            return
        from qgis.core import QgsGeometry, QgsPointXY
        xy = None
        for se in self.lienzo.series:
            if se.get("visible", True) and se.get("traza"):
                xy = self._xy_en(se["traza"], s)
                break
        self._marcador.reset(self._marcador.geometryType())
        if xy is not None:
            self._marcador.addGeometry(
                QgsGeometry.fromPointXY(QgsPointXY(xy[0], xy[1])), None)
            self._marcador.show()

    def _limpiar_marcador(self):
        if self._marcador is not None:
            try:
                self.iface.mapCanvas().scene().removeItem(self._marcador)
            except Exception:
                pass
            self._marcador = None

    def closeEvent(self, ev):
        self._limpiar_marcador()
        super().closeEvent(ev)

    def done(self, r):
        self._limpiar_marcador()
        super().done(r)

    def _exag(self, txt):
        self.lienzo.exag = 0.0 if txt == "Fit" else float(txt[1:])
        self.lienzo.update()

    def _visibilidad(self, item):
        i = self.lista.row(item)
        self.lienzo.series[i]["visible"] = \
            item.checkState() == Qt.CheckState.Checked
        self.lienzo.update()
