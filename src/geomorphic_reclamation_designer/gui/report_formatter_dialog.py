# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""'Report Formatter' — like the original: pick the fields to report from the
Available list, order them in the Used list, and output the per-channel table
as an on-screen table (Display), an HTML Report or a CSV file (opens directly
in Excel — equivalent to the MS Excel tab). Named formats are stored with
Save As / Delete (QgsSettings), the 'GEOFLUV' format being the default."""

import json

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton,
    QComboBox, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QInputDialog, QAbstractItemView,
)
from qgis.core import QgsSettings

CLAVE_SETTINGS = "GeoFluvQ/report_formats"


# ---------------------------------------------------------------- campos
def _rango(vals, dec=2):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "-"
    lo, hi = min(vals), max(vals)
    if abs(hi - lo) < 10 ** (-dec):
        return f"{lo:.{dec}f}"
    return f"{lo:.{dec}f} - {hi:.{dec}f}"


def _sec(d, clave):
    return [s.get(clave) for s in d.secciones] if d.secciones else []


# (label exactamente como el Report Formatter original, función de cálculo)
CAMPOS_REPORT = [
    ("name", lambda d, g: d.nombre),
    ("watershed area (ha)", lambda d, g: f"{d.area_propia_ha:.2f}"),
    ("add'l watershed area (ha)", lambda d, g: f"{d.settings.area_adicional_ha:.2f}"),
    ("valley length (m)", lambda d, g: f"{d.L_valle:.1f}"),
    ("drainage density (m/ha)", lambda d, g: f"{d.dd_m_ha:.1f}"),
    ("head elev (m)", lambda d, g: f"{d.perfil.z_cabecera:.2f}"),
    ("base elev (m)", lambda d, g: f"{d.perfil.z_boca:.2f}"),
    ("relief (m)", lambda d, g: f"{d.perfil.z_cabecera - d.perfil.z_boca:.2f}"),
    ("head slope", lambda d, g: f"{d.perfil.s_cabecera * 100:.2f}%"),
    ("base slope", lambda d, g: f"{d.perfil.s_boca * 100:.2f}%"),
    ("meander belt width range (m)", lambda d, g: _rango(_sec(d, "cinturon"), 1)),
    ("bankfull width range (m)", lambda d, g: _rango(_sec(d, "ancho_bankfull"))),
    ("bankfull depth range (m)", lambda d, g: _rango(_sec(d, "prof_bankfull"))),
    ("width to depth ratio, when slope < -0.04",
     lambda d, g: f"{d.settings.wd_pend_menor_004:g}"),
    ("flood prone width range (m)", lambda d, g: _rango(_sec(d, "ancho_flood"))),
    ("flood prone depth range (m)", lambda d, g: _rango(_sec(d, "prof_flood"))),
    ("Tractive force, bankfull width (kg/m^2)",
     lambda d, g: _rango([t / 9.81 for t in _sec(d, "tension_bkf") if t is not None])),
    ("Tractive force, flood prone width (kg/m^2)",
     lambda d, g: _rango([t / 9.81 for t in _sec(d, "tension_fld") if t is not None])),
    ("manual Qpk?",
     lambda d, g: "yes" if d.settings.qpk_manual_bankfull is not None else "no"),
    ("bankfull Qpk (m^3/s)", lambda d, g: f"{d.q_bankfull_boca:.3f}"),
    ("flood prone Qpk (m^3/s)", lambda d, g: f"{d.q_flood_boca:.3f}"),
    ("entrenchment ratio", lambda d, g: _rango(_sec(d, "entrench"))),
    ("radius of curvature range (m)", lambda d, g: _rango(_sec(d, "radio_curv"), 1)),
    ("meander length range (m)", lambda d, g: _rango(_sec(d, "long_meandro"), 1)),
    ("meander width ratio",
     lambda d, g: _rango([c / w for c, w in zip(_sec(d, "cinturon"),
                                                _sec(d, "ancho_bankfull"))
                          if c is not None and w])),
    ("slope range", lambda d, g: _rango(_sec(d, "pendiente")) + "%"),
    ("sinuosity (channel average)", lambda d, g: f"{d.sinuosidad_real:.3f}"),
    ("maximum design velocity (m/s)", lambda d, g: f"{d.settings.vel_max_agua:g}"),
    ("runoff coefficient", lambda d, g: f"{d.settings.coef_escorrentia:g}"),
]
_FUNC = dict(CAMPOS_REPORT)
FORMATO_DEFECTO = [c for c, _ in CAMPOS_REPORT]


class ReportFormatterDialog(QDialog):
    def __init__(self, disenos, glob, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Report Formatter")
        self.disenos = disenos
        self.glob = glob
        lay = QVBoxLayout(self)

        # ---------- formato ----------
        fila_f = QHBoxLayout()
        fila_f.addWidget(QLabel("Format"))
        self.cb_formato = QComboBox()
        fila_f.addWidget(self.cb_formato, 1)
        for txt, fn in (("Save As", self._save_as), ("Delete", self._delete)):
            b = QPushButton(txt); b.clicked.connect(fn); fila_f.addWidget(b)
        lay.addLayout(fila_f)

        # ---------- listas ----------
        fila = QHBoxLayout()
        col_a = QVBoxLayout()
        col_a.addWidget(QLabel("Available"))
        self.lst_disp = QListWidget()
        self.lst_disp.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        col_a.addWidget(self.lst_disp)
        fila.addLayout(col_a, 1)

        col_b = QVBoxLayout()
        col_b.addStretch()
        for txt, fn in (("Add >", self._add), ("Remove <", self._remove),
                        ("Up ↑", self._up), ("Down ↓", self._down)):
            b = QPushButton(txt); b.clicked.connect(fn); col_b.addWidget(b)
        col_b.addStretch()
        fila.addLayout(col_b)

        col_c = QVBoxLayout()
        col_c.addWidget(QLabel("Used"))
        self.lst_usado = QListWidget()
        self.lst_usado.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        col_c.addWidget(self.lst_usado)
        fila.addLayout(col_c, 1)
        lay.addLayout(fila, 1)

        # ---------- salida ----------
        fila_o = QHBoxLayout()
        for txt, fn in (("Display", self._display),
                        ("HTML Report", self._html),
                        ("Export CSV (Excel)", self._csv),
                        ("Exit", self.accept)):
            b = QPushButton(txt); b.clicked.connect(fn); fila_o.addWidget(b)
        lay.addLayout(fila_o)
        self.resize(760, 480)

        # cargar formatos guardados
        self._formatos = self._leer_formatos()
        self.cb_formato.addItems(list(self._formatos.keys()))
        self.cb_formato.currentTextChanged.connect(self._cargar_formato)
        self.cb_formato.setCurrentText("GEOFLUV")
        self._cargar_formato("GEOFLUV")

    # ---------- formatos guardados ----------
    def _leer_formatos(self):
        try:
            d = json.loads(QgsSettings().value(CLAVE_SETTINGS, "") or "{}")
        except Exception:
            d = {}
        if "GEOFLUV" not in d:
            d["GEOFLUV"] = list(FORMATO_DEFECTO)
        return d

    def _guardar_formatos(self):
        QgsSettings().setValue(CLAVE_SETTINGS, json.dumps(self._formatos))

    def _cargar_formato(self, nombre):
        campos = self._formatos.get(nombre, FORMATO_DEFECTO)
        self.lst_usado.clear()
        self.lst_disp.clear()
        for c in campos:
            if c in _FUNC:
                self.lst_usado.addItem(c)
        usados = set(campos)
        for c, _ in CAMPOS_REPORT:
            if c not in usados:
                self.lst_disp.addItem(c)

    def _save_as(self):
        nombre, ok = QInputDialog.getText(self, "Save Format As", "Format name:")
        if not ok or not nombre:
            return
        self._formatos[nombre] = self._campos_usados()
        self._guardar_formatos()
        if self.cb_formato.findText(nombre) < 0:
            self.cb_formato.addItem(nombre)
        self.cb_formato.setCurrentText(nombre)

    def _delete(self):
        nombre = self.cb_formato.currentText()
        if nombre == "GEOFLUV":
            QMessageBox.information(self, "Report Formatter",
                                    "The default GEOFLUV format cannot be deleted.")
            return
        self._formatos.pop(nombre, None)
        self._guardar_formatos()
        self.cb_formato.removeItem(self.cb_formato.currentIndex())

    # ---------- listas ----------
    def _campos_usados(self):
        return [self.lst_usado.item(i).text()
                for i in range(self.lst_usado.count())]

    def _add(self):
        for it in self.lst_disp.selectedItems():
            self.lst_usado.addItem(it.text())
            self.lst_disp.takeItem(self.lst_disp.row(it))

    def _remove(self):
        for it in self.lst_usado.selectedItems():
            self.lst_disp.addItem(it.text())
            self.lst_usado.takeItem(self.lst_usado.row(it))

    def _mover(self, delta):
        fila = self.lst_usado.currentRow()
        if fila < 0:
            return
        nueva = fila + delta
        if 0 <= nueva < self.lst_usado.count():
            it = self.lst_usado.takeItem(fila)
            self.lst_usado.insertItem(nueva, it)
            self.lst_usado.setCurrentRow(nueva)

    def _up(self):
        self._mover(-1)

    def _down(self):
        self._mover(1)

    # ---------- datos ----------
    def _tabla(self):
        campos = self._campos_usados()
        filas = []
        for d in self.disenos.values():
            filas.append([_FUNC[c](d, self.glob) for c in campos])
        return campos, filas

    # ---------- salidas ----------
    def _display(self):
        campos, filas = self._tabla()
        if not campos:
            QMessageBox.information(self, "Report Formatter",
                                    "Add at least one field to the Used list.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("GeoFluv Report")
        v = QVBoxLayout(dlg)
        t = QTableWidget(len(filas), len(campos))
        t.setHorizontalHeaderLabels(campos)
        for i, fila in enumerate(filas):
            for j, val in enumerate(fila):
                t.setItem(i, j, QTableWidgetItem(str(val)))
        t.resizeColumnsToContents()
        v.addWidget(t)
        b = QPushButton("Close"); b.clicked.connect(dlg.accept); v.addWidget(b)
        dlg.resize(860, 380)
        dlg.exec()

    def _csv(self):
        campos, filas = self._tabla()
        if not campos:
            return
        ruta, _ = QFileDialog.getSaveFileName(self, "Export CSV", "",
                                              "CSV (*.csv)")
        if not ruta:
            return
        if not ruta.endswith(".csv"):
            ruta += ".csv"
        import csv
        with open(ruta, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(campos)
            w.writerows(filas)
        QMessageBox.information(self, "Report Formatter",
                                f"CSV saved (opens in Excel):\n{ruta}")

    def _html(self):
        campos, filas = self._tabla()
        if not campos:
            return
        ruta, _ = QFileDialog.getSaveFileName(self, "HTML Report", "",
                                              "HTML (*.html)")
        if not ruta:
            return
        if not ruta.endswith(".html"):
            ruta += ".html"
        th = "".join(f"<th>{c}</th>" for c in campos)
        trs = "".join("<tr>" + "".join(f"<td>{v}</td>" for v in fila) + "</tr>"
                      for fila in filas)
        html = (f"<html><head><meta charset='utf-8'><title>GeoFluv Report</title>"
                f"<style>body{{font-family:sans-serif;font-size:12px}}"
                f"table{{border-collapse:collapse}}"
                f"td,th{{border:1px solid #999;padding:3px 7px}}"
                f"th{{background:#e8e8e8}}</style></head><body>"
                f"<h2>GeoFluv Report</h2><table><tr>{th}</tr>{trs}</table>"
                f"</body></html>")
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(html)
        QMessageBox.information(self, "Report Formatter",
                                f"HTML report saved:\n{ruta}")
