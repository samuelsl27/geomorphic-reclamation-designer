# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""'Natural Regrade Global Settings' dialog — mirrors the original layout:
GeoFluv Inputs + Drawing Settings groups, with OK / Cancel / Load / Save As /
Help buttons. Storm depths are shown in cm (as in the original) but stored
internally in mm."""

import json

from qgis.PyQt.QtWidgets import (
    QDialog, QFormLayout, QDoubleSpinBox, QCheckBox, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QGroupBox, QPushButton, QFileDialog,
    QMessageBox, QScrollArea,
)


def _spin(minv, maxv, val, dec=2, suf=""):
    s = QDoubleSpinBox()
    s.setRange(minv, maxv)
    s.setDecimals(dec)
    s.setValue(val)
    if suf:
        s.setSuffix(" " + suf)
    return s


class SettingsDialog(QDialog):
    """Natural Regrade Global Settings."""

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Natural Regrade Global Settings")
        self.s = settings
        self._loaded = False   # True si se cargó un archivo de settings
        outer = QVBoxLayout(self)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        cont = QWidget(); scroll.setWidget(cont)
        outer.addWidget(scroll)
        lay = QVBoxLayout(cont)

        # ================= GeoFluv Inputs =================
        g1 = QGroupBox("GeoFluv Inputs")
        f1 = QFormLayout(g1)

        self.sp_cresta = _spin(1, 1000, self.s.max_dist_cresta_cabecera, 1, "m")
        f1.addRow("Maximum distance from ridgeline to channel's head (m):",
                  self.sp_cresta)

        f1.addRow(QLabel("Maximum convex portion of sub-ridge:"))
        self.chk_conv_factor = QCheckBox("1.5 x ridge-to-head distance (m)")
        self.lb_conv_factor = QLabel("")
        fila = QHBoxLayout(); w_f = QWidget(); w_f.setLayout(fila)
        fila.setContentsMargins(20, 0, 0, 0)
        fila.addWidget(self.chk_conv_factor); fila.addWidget(self.lb_conv_factor)
        fila.addStretch()
        f1.addRow(w_f)
        self.chk_conv_pct = QCheckBox("Percent of overall length (%)")
        self.sp_conv_pct = _spin(0, 100, self.s.convexo_pct, 1)
        fila2 = QHBoxLayout(); w_p = QWidget(); w_p.setLayout(fila2)
        fila2.setContentsMargins(20, 0, 0, 0)
        fila2.addWidget(self.chk_conv_pct); fila2.addWidget(self.sp_conv_pct)
        fila2.addStretch()
        f1.addRow(w_p)
        self.chk_conv_factor.setChecked(self.s.convexo_modo == "factor")
        self.chk_conv_pct.setChecked(self.s.convexo_modo == "pct")
        self.chk_conv_factor.toggled.connect(
            lambda v: self.chk_conv_pct.setChecked(not v))
        self.chk_conv_pct.toggled.connect(
            lambda v: self.chk_conv_factor.setChecked(not v))
        self.sp_cresta.valueChanged.connect(self._act_factor)
        self._act_factor()

        self.chk_swale = QCheckBox("Maximum convex portion of swale (m)")
        self.chk_swale.setChecked(self.s.convexo_swale_activo)
        self.sp_swale = _spin(0.5, 500, self.s.convexo_swale_m, 1, "m")
        self.sp_swale.setEnabled(self.chk_swale.isChecked())
        self.chk_swale.toggled.connect(self.sp_swale.setEnabled)
        fila3 = QHBoxLayout(); w_s = QWidget(); w_s.setLayout(fila3)
        fila3.setContentsMargins(0, 0, 0, 0)
        fila3.addWidget(self.chk_swale); fila3.addWidget(self.sp_swale)
        fila3.addStretch()
        f1.addRow(w_s)

        self.sp_pboca = _spin(-50, 0, self.s.pendiente_desembocadura, 2, "%")
        f1.addRow("Slope at the mouth of the main valley bottom channel (%):",
                  self.sp_pboca)
        self.sp_reachA = _spin(1, 500, self.s.reach_canal_A, 2, "m")
        f1.addRow("'A' channel reach (m):", self.sp_reachA)
        self.sp_p2 = _spin(0.01, 50, self.s.p_2a_1h_mm / 10.0, 2, "cm")
        f1.addRow("2-yr, 1-hr (cm) (see documentation):", self.sp_p2)
        self.sp_p50 = _spin(0.01, 100, self.s.p_50a_6h_mm / 10.0, 2, "cm")
        f1.addRow("50-yr, 6-hr (cm) (see documentation):", self.sp_p50)
        f1.addRow(QLabel("<i>The 2-yr, 1-hr storm sizes the bankfull channel and meander\n"
                         "geometry; the 50-yr, 6-hr storm (introduced instantaneously)\n"
                         "sizes the flood-prone area.</i>"))
        self.sp_dd = _spin(1, 1000, self.s.dd_objetivo, 2, "m/ha")
        f1.addRow("Target drainage density (m/ha):", self.sp_dd)
        self.sp_ddv = _spin(0, 100, self.s.dd_varianza_pct, 2, "%")
        f1.addRow("Target drainage density variance (%):", self.sp_ddv)
        self.chk_crestas = QCheckBox("Force ridges to be lower than GeoFluv boundary")
        self.chk_crestas.setChecked(self.s.forzar_crestas_bajo_limite)
        f1.addRow(self.chk_crestas)
        self.sp_ang = _spin(0, 60, self.s.angulo_subcresta_deg, 2, "deg")
        f1.addRow("Angle from sub-ridge to channel's perpendicular, upstream:",
                  self.sp_ang)
        self.sp_ne = _spin(1, 100, self.s.pendiente_NE_pct, 2, "%")
        f1.addRow("North or East straight-line slopes (%):", self.sp_ne)
        self.sp_max = _spin(1, 100, self.s.pendiente_max_pct, 2, "%")
        f1.addRow("Maximum straight-line slopes (%):", self.sp_max)
        lay.addWidget(g1)

        # ================= Drawing Settings =================
        g2 = QGroupBox("Drawing Settings")
        f2 = QFormLayout(g2)
        self.sp_vmax = _spin(50, 300, self.s.var_max_corte_relleno_pct, 2, "%")
        f2.addRow("Maximum cut / fill (%):", self.sp_vmax)
        self.sp_vmin = _spin(10, 150, self.s.var_min_corte_relleno_pct, 2, "%")
        f2.addRow("Minimum cut / fill (%):", self.sp_vmin)
        self.sp_esp = _spin(0.5, 2.0, self.s.factor_esponjamiento, 3)
        f2.addRow("Cut swell factor:", self.sp_esp)
        self.sp_comp = _spin(0.5, 2.0, self.s.factor_compactacion, 3)
        f2.addRow("Fill shrink factor:", self.sp_comp)
        self.sp_dist_con = _spin(0.1, 100, self.s.max_dist_conexion_canales, 2, "m")
        f2.addRow("Maximum distance between connecting channels (m):", self.sp_dist_con)
        self.sp_tol_z = _spin(0.01, 50, self.s.tol_cota_cabecera_m, 3, "m")
        f2.addRow("Channel: head elevation tolerance (m):", self.sp_tol_z)
        self.sp_tol_s = _spin(0.01, 50, self.s.tol_pendiente_cabecera_pct, 3, "%")
        f2.addRow("Channel: head slope tolerance (%):", self.sp_tol_s)
        self.sp_holg = _spin(0.0, 40.0, self.s.holgura_divisoria_m, 2, "m")
        self.sp_holg.setToolTip(
            "How far outside the flood-prone edge a basin divide stops. Inside "
            "the channel corridor the ground is already defined by the "
            "channel's own 3D lines; a divide running in there fights them and "
            "produces flipped triangles. Ridges and swales stop at the edge "
            "itself (clearance 0).")
        f2.addRow("Basin divide clearance from the channel (m):", self.sp_holg)
        self.sp_silla = _spin(0.0, 90.0, self.s.prof_silla_pct, 1, "%")
        self.sp_silla.setToolTip(
            "Depth of the saddle the ridgeline forms where a swale head "
            "reaches it, as a percentage of the drop from the crest to the "
            "swale head. Natural ridgelines dip at swale heads; without the "
            "dip, runoff travels along the ridge crest, cuts ruts and ends up "
            "gullying. 0 disables the saddles.")
        f2.addRow("Ridgeline saddle depth at swale heads (%):", self.sp_silla)
        self.sp_tol_x = _spin(0.001, 5.0, self.s.tol_cruce_breaklines_m, 3, "m")
        self.sp_tol_x.setToolTip(
            "Two design lines that cross in plan should meet at the same "
            "elevation. Above this difference the crossing is reported by "
            "Check Design, as the Error Log does when contouring.")
        f2.addRow("Crossing breaklines: elevation tolerance (m):", self.sp_tol_x)
        self.sp_tol_xc = _spin(0.01, 20.0, self.s.tol_cruce_canal_m, 2, "m")
        self.sp_tol_xc.setToolTip(
            "Same tolerance inside the channel corridor. The bank lines are "
            "parallel offsets of the same section, so they cross each other "
            "and the hillslope lines by construction, at the bank depth. "
            "Only differences above this value are reported as a defect.")
        f2.addRow("Crossing inside the channel: tolerance (m):", self.sp_tol_xc)
        self.sp_tin = _spin(5.0, 500.0, self.s.long_max_lado_tin_m, 1, "m")
        self.sp_tin.setToolTip(
            "Maximum triangle mesh line length. Areas further than half this "
            "distance from any design line are reported: the surface there "
            "will be a flat facet with no relief.")
        f2.addRow("Maximum triangle mesh line length (m):", self.sp_tin)
        self.sp_pico = _spin(50.0, 2000.0, self.s.pend_max_linea_pct, 0, "%")
        self.sp_pico.setToolTip(
            "Slope between two contiguous vertices of a design line above "
            "which Check Design reports an elevation spike.")
        f2.addRow("Breakline elevation spike above (%):", self.sp_pico)
        self.sp_ang_v = _spin(10.0, 89.0, self.s.ang_max_valle_ladera_deg, 0, "deg")
        self.sp_ang_v.setToolTip(
            "A valley input line making a larger angle with the terrain's "
            "downslope direction is running across the slope: one valley wall "
            "will not drain into the channel.")
        f2.addRow("Valley across the slope above (deg):", self.sp_ang_v)
        lay.addWidget(g2)

        # ================= GeoFluvQ additional settings =================
        g3 = QGroupBox("GeoFluvQ additional settings (not in the original)")
        f3 = QFormLayout(g3)
        self.sp_sinA = _spin(1.0, 1.2, self.s.sinuosidad_canal_A, 3)
        f3.addRow("'A' channel sinuosity (<1.2):", self.sp_sinA)
        self.sp_d50 = _spin(0.0, 500.0, self.s.d50_mm, 1, "mm")
        f3.addRow("Bed material D50, Wolman count (mm):", self.sp_d50)
        f3.addRow(QLabel("<i>τcrit = 0.045·(γs−γw)·D50 (Shields). With D50 = 0 tractive\n"
                         "stability is not evaluated. Can be overridden per channel.</i>"))
        self.sp_ci = _spin(0.1, 50, self.s.intervalo_curvas, 2, "m")
        f3.addRow("Contour interval (m):", self.sp_ci)
        self.sp_cm = _spin(0.5, 200, self.s.intervalo_curvas_maestras, 1, "m")
        f3.addRow("Index contour interval (m):", self.sp_cm)
        self.sp_est = _spin(1, 200, self.s.intervalo_estaciones, 1, "m")
        f3.addRow("Cross-section station interval (m):", self.sp_est)
        lay.addWidget(g3)
        lay.addStretch()

        # ================= botones =================
        fila_b = QHBoxLayout()
        for txt, fn in (("OK", self._ok), ("Cancel", self.reject),
                        ("Load", self._load), ("Save As", self._save_as),
                        ("Help", self._help)):
            b = QPushButton(txt); b.clicked.connect(fn); fila_b.addWidget(b)
        outer.addLayout(fila_b)
        self.resize(560, 640)

    # ---------- lógica ----------
    def _act_factor(self):
        # mostrar con 2 decimales (el cálculo usa siempre el valor completo)
        self.lb_conv_factor.setText(
            f"= {1.5 * self.sp_cresta.value():.2f} m")

    def _ok(self):
        self.accept()

    def aplicar(self):
        if self._loaded:      # los valores ya vienen del archivo cargado
            return
        s = self.s
        s.max_dist_cresta_cabecera = self.sp_cresta.value()
        s.convexo_modo = "pct" if self.chk_conv_pct.isChecked() else "factor"
        s.convexo_pct = self.sp_conv_pct.value()
        s.convexo_swale_activo = self.chk_swale.isChecked()
        s.convexo_swale_m = self.sp_swale.value()
        s.pendiente_desembocadura = self.sp_pboca.value()
        s.reach_canal_A = self.sp_reachA.value()
        s.p_2a_1h_mm = self.sp_p2.value() * 10.0     # cm -> mm
        s.p_50a_6h_mm = self.sp_p50.value() * 10.0   # cm -> mm
        s.dd_objetivo = self.sp_dd.value()
        s.dd_varianza_pct = self.sp_ddv.value()
        s.forzar_crestas_bajo_limite = self.chk_crestas.isChecked()
        s.angulo_subcresta_deg = self.sp_ang.value()
        s.pendiente_NE_pct = self.sp_ne.value()
        s.pendiente_max_pct = self.sp_max.value()
        s.var_max_corte_relleno_pct = self.sp_vmax.value()
        s.var_min_corte_relleno_pct = self.sp_vmin.value()
        s.factor_esponjamiento = self.sp_esp.value()
        s.factor_compactacion = self.sp_comp.value()
        s.max_dist_conexion_canales = self.sp_dist_con.value()
        s.tol_cota_cabecera_m = self.sp_tol_z.value()
        s.tol_pendiente_cabecera_pct = self.sp_tol_s.value()
        s.holgura_divisoria_m = self.sp_holg.value()
        s.prof_silla_pct = self.sp_silla.value()
        s.tol_cruce_breaklines_m = self.sp_tol_x.value()
        s.tol_cruce_canal_m = self.sp_tol_xc.value()
        s.long_max_lado_tin_m = self.sp_tin.value()
        s.pend_max_linea_pct = self.sp_pico.value()
        s.ang_max_valle_ladera_deg = self.sp_ang_v.value()
        s.sinuosidad_canal_A = self.sp_sinA.value()
        s.d50_mm = self.sp_d50.value()
        s.intervalo_curvas = self.sp_ci.value()
        s.intervalo_curvas_maestras = self.sp_cm.value()
        s.intervalo_estaciones = self.sp_est.value()

    # ---------- Load / Save As (settings file, like the original) ----------
    def _save_as(self):
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Save Settings As", "", "GeoFluv settings (*.geofluv-settings.json)")
        if not ruta:
            return
        if not ruta.endswith(".geofluv-settings.json"):
            ruta += ".geofluv-settings.json"
        self.aplicar()
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(self.s.to_dict(), fh, indent=2, ensure_ascii=False)
        QMessageBox.information(self, "Settings", f"Settings saved to:\n{ruta}")

    def _load(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Load Settings", "", "GeoFluv settings (*.geofluv-settings.json)")
        if not ruta:
            return
        try:
            with open(ruta, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception as e:
            QMessageBox.warning(self, "Settings", f"Could not load settings:\n{e}")
            return
        from ..core.params import GlobalSettings
        nuevo = GlobalSettings.from_dict(d)
        for k, v in nuevo.to_dict().items():
            setattr(self.s, k, v)
        self._loaded = True
        self.accept()

    def _help(self):
        QMessageBox.information(
            self, "Help — Global Settings",
            "These settings hold the essential local variables of the GeoFluv "
            "method, measured at stable reference sites with earth materials "
            "similar to the project area:\n\n"
            "· Ridgeline-to-channel-head distance, 'A' channel reach, target "
            "drainage density (± variance) — measured in the field.\n"
            "· 2-yr 1-hr and 50-yr 6-hr storms — from rainfall records.\n"
            "· Slope at the mouth of the main channel — measured downstream "
            "of the local base level (the most critical value of the design).\n"
            "· Cut/fill range and swell/shrink factors control the earthwork "
            "balance validation.\n\n"
            "Load / Save As store these settings in an independent file so "
            "they can be reused across design alternatives.")
