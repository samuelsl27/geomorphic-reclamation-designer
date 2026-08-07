# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Informe en forma de tabla con filas ENLAZADAS a entidades del proyecto.

Lo usa 'Check Ridgeline Slope' (y cualquier otro informe que señale
elementos concretos): al pulsar una fila se selecciona la entidad en su capa,
se hace zoom sobre ella y se marca como capa activa, de modo que el diseñador
puede editarla al momento (Edit Longitudinal Profile, mover vértices, etc.).
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QDialogButtonBox, QPushButton, QAbstractItemView, QCheckBox,
)
from qgis.core import QgsProject


class FeatureListDialog(QDialog):
    """titulo, cabecera (str), columnas (list[str]), filas: list de dicts
    {'valores': [...], 'capa': QgsVectorLayer|str, 'fid': int}."""

    def __init__(self, titulo, cabecera, columnas, filas, iface, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.iface = iface
        self.filas = filas
        v = QVBoxLayout(self)
        if cabecera:
            lb = QLabel(cabecera)
            lb.setWordWrap(True)
            v.addWidget(lb)
        self.tabla = QTableWidget(len(filas), len(columnas))
        self.tabla.setHorizontalHeaderLabels(columnas)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSortingEnabled(True)
        for r, fila in enumerate(filas):
            for c, val in enumerate(fila["valores"]):
                it = QTableWidgetItem()
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    it.setData(Qt.ItemDataRole.DisplayRole, val)
                else:
                    it.setText(str(val))
                self.tabla.setItem(r, c, it)
        self.tabla.resizeColumnsToContents()
        self.tabla.itemSelectionChanged.connect(self._fila_elegida)
        v.addWidget(self.tabla)

        h = QHBoxLayout()
        self.chk_zoom = QCheckBox("Zoom to the selected feature")
        self.chk_zoom.setChecked(True)
        h.addWidget(self.chk_zoom)
        b_todo = QPushButton("Select all listed features")
        b_todo.clicked.connect(self._seleccionar_todo)
        h.addWidget(b_todo)
        b_none = QPushButton("Clear selection")
        b_none.clicked.connect(self._limpiar)
        h.addWidget(b_none)
        h.addStretch(1)
        v.addLayout(h)
        v.addWidget(QLabel("Click a row to select that feature on the map."))

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.reject)
        bb.accepted.connect(self.accept)
        v.addWidget(bb)
        self.resize(720, 460)

    # ---------------- utilidades ----------------
    def _capa(self, ref):
        if isinstance(ref, str):
            for l in QgsProject.instance().mapLayers().values():
                if l.name() == ref:
                    return l
            return None
        return ref

    def _fila_elegida(self):
        filas = {i.row() for i in self.tabla.selectedIndexes()}
        if not filas:
            return
        # con la tabla ordenable hay que leer el fid guardado en la fila
        # original: se localiza por coincidencia de la primera columna
        self._limpiar()
        por_capa = {}
        for r in filas:
            datos = self._datos_de_fila(r)
            if datos is None:
                continue
            capa = self._capa(datos["capa"])
            if capa is None:
                continue
            por_capa.setdefault(capa, []).append(datos["fid"])
        for capa, fids in por_capa.items():
            capa.selectByIds(fids)
            self.iface.setActiveLayer(capa)
            if self.chk_zoom.isChecked():
                try:
                    self.iface.mapCanvas().zoomToSelected(capa)
                    self.iface.mapCanvas().zoomOut()
                except Exception:
                    pass
        self.iface.mapCanvas().refresh()

    def _datos_de_fila(self, r):
        """Recupera la fila original comparando todas sus celdas."""
        vals = []
        for c in range(self.tabla.columnCount()):
            it = self.tabla.item(r, c)
            vals.append(it.text() if it else "")
        for fila in self.filas:
            if [str(v) for v in fila["valores"]] == vals:
                return fila
        # fallback: por índice si no hay reordenación
        return self.filas[r] if r < len(self.filas) else None

    def _seleccionar_todo(self):
        self._limpiar()
        por_capa = {}
        for fila in self.filas:
            capa = self._capa(fila["capa"])
            if capa is not None:
                por_capa.setdefault(capa, []).append(fila["fid"])
        for capa, fids in por_capa.items():
            capa.selectByIds(fids)
        self.iface.mapCanvas().refresh()

    def _limpiar(self):
        for fila in self.filas:
            capa = self._capa(fila["capa"])
            if capa is not None:
                capa.removeSelection()
