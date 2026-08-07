# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Ventana de resultados de 'Check Design' — el Error Log del complemento.

Muestra los hallazgos en una tabla ordenada por gravedad, con filtros por
gravedad y por grupo. Al pulsar una fila se selecciona la entidad implicada en
su capa y se hace zoom sobre ella (o sobre el punto, cuando el hallazgo no
apunta a una entidad concreta sino a una coordenada, como un cruce de líneas o
un hoyo cerrado), igual que el Zoom del Error Log del original.

El panel inferior explica el hallazgo seleccionado y la corrección sugerida.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QBrush
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QDialogButtonBox, QPushButton, QAbstractItemView, QCheckBox, QComboBox,
    QTextEdit, QSplitter, QWidget, QFileDialog,
)
from qgis.core import QgsProject, QgsRectangle


COLOR = {
    "error":   QColor(255, 220, 220),
    "warning": QColor(255, 244, 205),
    "info":    QColor(224, 240, 224),
}
ETIQUETA = {"error": "Error", "warning": "Warning", "info": "Info"}


class CheckDialog(QDialog):
    """hallazgos: lista de core.checks.Hallazgo."""

    def __init__(self, hallazgos, iface, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GeoFluv Design Check")
        self.iface = iface
        self.todos = list(hallazgos)
        self.filas = []
        self.resize(940, 560)

        v = QVBoxLayout(self)
        n_e = sum(1 for h in self.todos if h.gravedad == "error")
        n_w = sum(1 for h in self.todos if h.gravedad == "warning")
        n_i = len(self.todos) - n_e - n_w
        self.lb = QLabel(
            f"<b>{n_e} error(s), {n_w} warning(s), {n_i} note(s).</b>  "
            "Errors break the design or the triangulation; warnings mean the "
            "design departs from the method or from your own settings. "
            "Click a row to select and zoom to the feature involved.")
        self.lb.setWordWrap(True)
        v.addWidget(self.lb)

        h = QHBoxLayout()
        h.addWidget(QLabel("Severity:"))
        self.cb_grav = QComboBox()
        self.cb_grav.addItems(["All", "Errors only", "Errors and warnings"])
        self.cb_grav.setCurrentIndex(2)
        self.cb_grav.currentIndexChanged.connect(self._refiltrar)
        h.addWidget(self.cb_grav)
        h.addWidget(QLabel("Group:"))
        self.cb_grupo = QComboBox()
        self.cb_grupo.addItem("All")
        for g in sorted({x.grupo for x in self.todos}):
            self.cb_grupo.addItem(g)
        self.cb_grupo.currentIndexChanged.connect(self._refiltrar)
        h.addWidget(self.cb_grupo)
        self.chk_zoom = QCheckBox("Zoom to the selected item")
        self.chk_zoom.setChecked(True)
        h.addWidget(self.chk_zoom)
        h.addStretch(1)
        v.addLayout(h)

        sp = QSplitter(Qt.Orientation.Vertical)
        self.tabla = QTableWidget(0, 5)
        self.tabla.setHorizontalHeaderLabels(
            ["Severity", "Code", "Group", "Issue", "Where"])
        self.tabla.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSortingEnabled(True)
        self.tabla.itemSelectionChanged.connect(self._fila_elegida)
        sp.addWidget(self.tabla)

        caja = QWidget()
        vb = QVBoxLayout(caja)
        vb.setContentsMargins(0, 0, 0, 0)
        self.txt = QTextEdit()
        self.txt.setReadOnly(True)
        vb.addWidget(self.txt)
        sp.addWidget(caja)
        sp.setSizes([380, 160])
        v.addWidget(sp, 1)

        hb = QHBoxLayout()
        b_csv = QPushButton("Export to CSV...")
        b_csv.clicked.connect(self._exportar)
        hb.addWidget(b_csv)
        b_sel = QPushButton("Select all listed features")
        b_sel.clicked.connect(self._seleccionar_todo)
        hb.addWidget(b_sel)
        b_lim = QPushButton("Clear selection")
        b_lim.clicked.connect(self._limpiar)
        hb.addWidget(b_lim)
        hb.addStretch(1)
        v.addLayout(hb)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        v.addWidget(bb)

        self._refiltrar()

    # ------------------------------------------------------------ tabla
    def _visibles(self):
        i = self.cb_grav.currentIndex()
        permitidas = ({"error", "warning", "info"} if i == 0
                      else {"error"} if i == 1 else {"error", "warning"})
        grupo = self.cb_grupo.currentText()
        return [h for h in self.todos
                if h.gravedad in permitidas
                and (grupo == "All" or h.grupo == grupo)]

    def _refiltrar(self):
        self.filas = self._visibles()
        self.tabla.setSortingEnabled(False)
        self.tabla.setRowCount(len(self.filas))
        for r, h in enumerate(self.filas):
            donde = ""
            if h.capa and h.fid is not None and h.fid >= 0:
                donde = f"{h.capa} fid {h.fid}"
            elif h.x is not None:
                donde = f"{h.x:,.0f}, {h.y:,.0f}"
            for c, val in enumerate([ETIQUETA.get(h.gravedad, h.gravedad),
                                     h.codigo, h.grupo, h.titulo, donde]):
                it = QTableWidgetItem(str(val))
                it.setBackground(QBrush(COLOR.get(h.gravedad,
                                                  QColor(255, 255, 255))))
                it.setData(Qt.ItemDataRole.UserRole, r)
                self.tabla.setItem(r, c, it)
        self.tabla.resizeColumnsToContents()
        self.tabla.setSortingEnabled(True)
        self.txt.clear()

    def _hallazgo_actual(self):
        f = self.tabla.currentRow()
        if f < 0:
            return None
        it = self.tabla.item(f, 0)
        if it is None:
            return None
        i = it.data(Qt.ItemDataRole.UserRole)
        if i is None or i >= len(self.filas):
            return None
        return self.filas[i]

    def _fila_elegida(self):
        h = self._hallazgo_actual()
        if h is None:
            return
        html = [f"<b>{h.codigo} — {h.titulo}</b>", f"<p>{h.detalle}</p>"]
        if h.valor is not None and h.limite is not None:
            html.append(f"<p>Value <b>{h.valor:,.2f}</b> against a limit of "
                        f"<b>{h.limite:,.2f}</b>.</p>")
        if h.sugerencia:
            html.append(f"<p><i>Suggested fix:</i> {h.sugerencia}</p>")
        self.txt.setHtml("".join(html))
        if self.chk_zoom.isChecked():
            self._ir_a(h)

    # ------------------------------------------------------------- zoom
    def _capa(self, nombre):
        for l in QgsProject.instance().mapLayers().values():
            if l.name() == nombre:
                return l
        return None

    def _ir_a(self, h):
        canvas = self.iface.mapCanvas()
        capa = self._capa(h.capa) if h.capa else None
        if capa is not None and h.fid is not None and h.fid >= 0:
            capa.removeSelection()
            capa.selectByIds([h.fid])
            self.iface.setActiveLayer(capa)
            f = capa.getFeature(h.fid)
            if f.isValid() and f.geometry() is not None:
                bb = f.geometry().boundingBox()
                bb.grow(max(bb.width(), bb.height(), 20.0) * 0.25)
                canvas.setExtent(bb)
                canvas.refresh()
                if h.x is None:
                    return
        if h.x is not None and h.y is not None:
            r = QgsRectangle(h.x - 40, h.y - 40, h.x + 40, h.y + 40)
            canvas.setExtent(r)
            canvas.refresh()

    def _seleccionar_todo(self):
        porcapa = {}
        for h in self.filas:
            if h.capa and h.fid is not None and h.fid >= 0:
                porcapa.setdefault(h.capa, []).append(h.fid)
        for nombre, fids in porcapa.items():
            capa = self._capa(nombre)
            if capa is not None:
                capa.selectByIds(fids)

    def _limpiar(self):
        for h in self.filas:
            capa = self._capa(h.capa) if h.capa else None
            if capa is not None:
                capa.removeSelection()

    # ------------------------------------------------------------- CSV
    def _exportar(self):
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Export design check", "geofluv_check.csv", "CSV (*.csv)")
        if not ruta:
            return
        import csv
        with open(ruta, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["severity", "code", "group", "issue", "detail",
                        "layer", "fid", "x", "y", "value", "limit",
                        "suggested_fix"])
            for h in self.filas:
                w.writerow([h.gravedad, h.codigo, h.grupo, h.titulo, h.detalle,
                            h.capa, h.fid if h.fid is not None and h.fid >= 0
                            else "", "" if h.x is None else round(h.x, 2),
                            "" if h.y is None else round(h.y, 2),
                            "" if h.valor is None else round(h.valor, 3),
                            "" if h.limite is None else round(h.limite, 3),
                            h.sugerencia])
        self.lb.setText(f"Exported to {ruta}")
