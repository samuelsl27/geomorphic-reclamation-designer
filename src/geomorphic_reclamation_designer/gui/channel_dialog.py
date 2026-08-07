# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""'Channel 'xxx' Settings' dialog — mirrors the original Geometry / Watershed
tabs, field by field. The 'Pick' buttons sample the elevation from the DEM at
the channel head/mouth."""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QFormLayout,
    QDoubleSpinBox, QCheckBox, QSpinBox, QDialogButtonBox, QLabel, QPushButton,
    QRadioButton, QGroupBox,
)


def _spin(minv, maxv, val, dec=2, suf=""):
    s = QDoubleSpinBox()
    s.setRange(minv, maxv)
    s.setDecimals(dec)
    s.setValue(val if val is not None else 0.0)
    if suf:
        s.setSuffix(" " + suf)
    return s


def _par(w1, w2):
    """Dos widgets en una fila (para los pares slope > -0.04 / < -0.04)."""
    w = QWidget(); h = QHBoxLayout(w); h.setContentsMargins(0, 0, 0, 0)
    h.addWidget(QLabel("slope > -0.04:")); h.addWidget(w1)
    h.addWidget(QLabel("< -0.04:")); h.addWidget(w2)
    h.addStretch()
    return w


class ChannelSettingsDialog(QDialog):
    def __init__(self, canal, es_principal, parent=None,
                 z_cab_dem=None, z_boca_dem=None):
        """z_cab_dem / z_boca_dem: cotas del DEM en cabecera y boca del canal
        (para los botones 'Pick')."""
        super().__init__(parent)
        self.c = canal
        self._z_cab_dem = z_cab_dem
        self._z_boca_dem = z_boca_dem
        self.setWindowTitle(f"Channel '{canal.nombre}' Settings")
        lay = QVBoxLayout(self)
        tabs = QTabWidget(); lay.addWidget(tabs)

        # ==================== Geometry ====================
        w1 = QWidget(); f1 = QFormLayout(w1)
        self.sp_vel = _spin(0.1, 10, self.c.vel_max_agua, 2, "m/s")
        f1.addRow("Maximum Water Velocity (m/s):", self.sp_vel)
        self.sp_pcab = _spin(-60, 0, self.c.pendiente_cabecera_pct, 2, "%")
        f1.addRow("Upstream Slope %:", self.sp_pcab)
        self.sp_pboca = _spin(-60, 0, self.c.pendiente_boca_pct or -2.0, 2, "%")
        self.sp_pboca.setEnabled(es_principal)
        f1.addRow("Downstream slope % (Only adjustable on main):",
                  self.sp_pboca if es_principal else QLabel("n/a"))
        self.sp_wd1 = _spin(2, 60, self.c.wd_pend_mayor_004, 2)
        self.sp_wd2 = _spin(2, 60, self.c.wd_pend_menor_004, 2)
        f1.addRow("Width-to-Depth:", _par(self.sp_wd1, self.sp_wd2))
        self.sp_s1 = _spin(1.0, 1.2, self.c.sinuosidad_mayor_004, 3)
        self.sp_s2 = _spin(1.0, 3.0, self.c.sinuosidad_menor_004, 3)
        f1.addRow("Sinuosity:", _par(self.sp_s1, self.sp_s2))
        self.sp_sub = QSpinBox(); self.sp_sub.setRange(1, 15)
        self.sp_sub.setSingleStep(2)
        self.sp_sub.setValue(self.c.espaciado_subcrestas)
        f1.addRow("Sub-ridge spacing on sinusoidal channel:", self.sp_sub)

        # --- Specify head elevation ---
        self.chk_zcab = QCheckBox("Specify head elevation.")
        self.chk_zcab.setChecked(self.c.cota_cabecera is not None)
        f1.addRow(self.chk_zcab)
        self.sp_zcab = _spin(-500, 9000, self.c.cota_cabecera
                             if self.c.cota_cabecera is not None
                             else (z_cab_dem or 0.0), 2, "m")
        btn_pick_cab = QPushButton("Pick")
        btn_pick_cab.setToolTip("Sample the DEM elevation at the channel head")
        btn_pick_cab.clicked.connect(self._pick_cab)
        wz = QWidget(); hz = QHBoxLayout(wz); hz.setContentsMargins(20, 0, 0, 0)
        hz.addWidget(QLabel("Head elevation (m)")); hz.addWidget(btn_pick_cab)
        hz.addWidget(self.sp_zcab); hz.addStretch()
        f1.addRow(wz)
        self.sp_zcab.setEnabled(self.chk_zcab.isChecked())
        self.chk_zcab.toggled.connect(self.sp_zcab.setEnabled)

        # --- Specify mouth elevation ---
        self.chk_zboca = QCheckBox("Specify mouth elevation. Only adjustable on main channel.")
        self.chk_zboca.setChecked(self.c.cota_boca is not None)
        self.chk_zboca.setEnabled(es_principal)
        f1.addRow(self.chk_zboca)
        self.sp_zboca = _spin(-500, 9000, self.c.cota_boca
                              if self.c.cota_boca is not None
                              else (z_boca_dem or 0.0), 2, "m")
        btn_pick_boca = QPushButton("Pick")
        btn_pick_boca.setToolTip("Sample the DEM elevation at the channel mouth")
        btn_pick_boca.clicked.connect(self._pick_boca)
        wz2 = QWidget(); hz2 = QHBoxLayout(wz2); hz2.setContentsMargins(20, 0, 0, 0)
        hz2.addWidget(QLabel("Mouth elevation (m)")); hz2.addWidget(btn_pick_boca)
        hz2.addWidget(self.sp_zboca); hz2.addStretch()
        f1.addRow(wz2)
        self.sp_zboca.setEnabled(es_principal and self.chk_zboca.isChecked())
        self.chk_zboca.toggled.connect(
            lambda v: self.sp_zboca.setEnabled(es_principal and v))

        # --- Specify sub-ridge/swale convex length ---
        self.chk_conv = QCheckBox("Specify sub-ridge/swale convex length")
        self.chk_conv.setChecked(getattr(self.c, "especificar_convexo", False))
        f1.addRow(self.chk_conv)
        self.sp_dist_swale = _spin(0.5, 1000,
                                   getattr(self.c, "dist_cresta_swale_m", 24.0), 1, "m")
        wd1 = QWidget(); hd1 = QHBoxLayout(wd1); hd1.setContentsMargins(20, 0, 0, 0)
        hd1.addWidget(QLabel("Maximum distance from ridgeline to swale head (m)"))
        hd1.addWidget(self.sp_dist_swale); hd1.addStretch()
        f1.addRow(wd1)
        f1.addRow(QLabel("Maximum convex portion of sub-ridge:"))
        self.chk_c_factor = QCheckBox("1.5 x distance (m)")
        self.lb_c_factor = QLabel("")
        wf = QWidget(); hf = QHBoxLayout(wf); hf.setContentsMargins(40, 0, 0, 0)
        hf.addWidget(self.chk_c_factor); hf.addWidget(self.lb_c_factor); hf.addStretch()
        f1.addRow(wf)
        self.chk_c_pct = QCheckBox("Percent of overall length (%)")
        self.sp_c_pct = _spin(0, 100, getattr(self.c, "convexo_pct_canal", 20.0), 1)
        wp = QWidget(); hp = QHBoxLayout(wp); hp.setContentsMargins(40, 0, 0, 0)
        hp.addWidget(self.chk_c_pct); hp.addWidget(self.sp_c_pct); hp.addStretch()
        f1.addRow(wp)
        modo = getattr(self.c, "convexo_modo_canal", "factor")
        self.chk_c_factor.setChecked(modo == "factor")
        self.chk_c_pct.setChecked(modo == "pct")
        self.chk_c_factor.toggled.connect(lambda v: self.chk_c_pct.setChecked(not v))
        self.chk_c_pct.toggled.connect(lambda v: self.chk_c_factor.setChecked(not v))
        self.sp_dist_swale.valueChanged.connect(self._act_c_factor)
        self._act_c_factor()

        def _tog_conv(v):
            for wdg in (self.sp_dist_swale, self.chk_c_factor, self.chk_c_pct,
                        self.sp_c_pct):
                wdg.setEnabled(v)
        self.chk_conv.toggled.connect(_tog_conv)
        _tog_conv(self.chk_conv.isChecked())

        self.chk_rand = QCheckBox("Random scale factors on sinusoidal channel.")
        self.chk_rand.setChecked(self.c.factores_aleatorios)
        f1.addRow(self.chk_rand)

        # --- Additional settings ---
        f1.addRow(QLabel("<i>Additional settings:</i>"))
        self.sp_n = _spin(0.010, 0.200, self.c.n_manning, 3)
        f1.addRow("Manning's n (hydraulic verification):", self.sp_n)
        self.chk_d50 = QCheckBox("Override global D50 for this channel")
        self.sp_d50 = _spin(0.0, 500.0, self.c.d50_mm or 0.0, 1, "mm")
        self.chk_d50.setChecked(self.c.d50_mm is not None)
        self.sp_d50.setEnabled(self.chk_d50.isChecked())
        self.chk_d50.toggled.connect(self.sp_d50.setEnabled)
        f1.addRow(self.chk_d50); f1.addRow("Channel D50:", self.sp_d50)
        tabs.addTab(w1, "Geometry")

        # ==================== Watershed ====================
        w2 = QWidget(); f2 = QFormLayout(w2)
        self.chk_rac = QCheckBox("Use Rational Runoff Method.")
        self.chk_rac.setChecked(self.c.usar_metodo_racional)
        f2.addRow(self.chk_rac)
        self.sp_c = _spin(0.05, 1.0, self.c.coef_escorrentia, 2)
        f2.addRow("Runoff Coefficient:", self.sp_c)
        self.chk_qman = QCheckBox("Use manual Qpk.")
        self.chk_qman.setChecked(self.c.qpk_manual_bankfull is not None)
        f2.addRow(self.chk_qman)
        self.sp_qb = _spin(0, 10000, self.c.qpk_manual_bankfull or 0, 3, "m³/s")
        f2.addRow("Manual Qpk, 2-yr, 1-hr storm (m^3/s):", self.sp_qb)
        self.sp_qf = _spin(0, 10000, self.c.qpk_manual_flood or 0, 3, "m³/s")
        f2.addRow("Manual Qpk, 50-yr, 6-hr storm (m^3/s):", self.sp_qf)

        self.chk_aad = QCheckBox("Additional watershed area.(ha)")
        self.chk_aad.setChecked(self.c.area_adicional_ha > 0)
        self.sp_aad = _spin(0, 100000, self.c.area_adicional_ha, 2, "ha")
        wa = QWidget(); ha = QHBoxLayout(wa); ha.setContentsMargins(0, 0, 0, 0)
        ha.addWidget(self.chk_aad); ha.addWidget(self.sp_aad); ha.addStretch()
        f2.addRow(wa)

        g_how = QGroupBox("How to add additional area?")
        hh = QHBoxLayout(g_how)
        self.rb_head = QRadioButton("At head of channel.")
        self.rb_even = QRadioButton("Evenly along length.")
        self.rb_head.setChecked(self.c.area_adicional_en_cabecera)
        self.rb_even.setChecked(not self.c.area_adicional_en_cabecera)
        hh.addWidget(self.rb_head); hh.addWidget(self.rb_even)
        f2.addRow(g_how)

        self.chk_rac_ad = QCheckBox("Use Rational Runoff Method for additional area.")
        self.chk_rac_ad.setChecked(getattr(self.c, "usar_racional_adicional", True))
        f2.addRow(self.chk_rac_ad)
        self.sp_cad = _spin(0.05, 1.0, self.c.coef_escorrentia_adicional, 2)
        f2.addRow("Runoff Coefficient:", self.sp_cad)
        self.chk_qman_ad = QCheckBox("Use manual Qpk for additional area.")
        self.chk_qman_ad.setChecked(getattr(self.c, "qpk_adic_bankfull", None) is not None)
        f2.addRow(self.chk_qman_ad)
        self.sp_qb_ad = _spin(0, 10000, getattr(self.c, "qpk_adic_bankfull", None) or 0,
                              3, "m³/s")
        f2.addRow("Manual Qpk, 2-yr, 1-hr storm (m^3/s):", self.sp_qb_ad)
        self.sp_qf_ad = _spin(0, 10000, getattr(self.c, "qpk_adic_flood", None) or 0,
                              3, "m³/s")
        f2.addRow("Manual Qpk, 50-yr, 6-hr storm (m^3/s):", self.sp_qf_ad)
        f2.addRow(QLabel("<i>Method note: raising discharges above the real event does NOT\n"
                         "add a safety factor — it produces a channel unable to move its\n"
                         "sediment in frequent flows (it silts up).</i>"))
        tabs.addTab(w2, "Watershed")

        # habilitaciones cruzadas
        def _tog_qman(v):
            self.sp_qb.setEnabled(v); self.sp_qf.setEnabled(v)
            self.sp_c.setEnabled(not v)
        self.chk_qman.toggled.connect(_tog_qman); _tog_qman(self.chk_qman.isChecked())

        def _tog_aad(v):
            for wdg in (self.sp_aad, self.rb_head, self.rb_even, self.chk_rac_ad,
                        self.sp_cad, self.chk_qman_ad, self.sp_qb_ad, self.sp_qf_ad):
                wdg.setEnabled(v)
            if v:
                _tog_qman_ad(self.chk_qman_ad.isChecked())
        def _tog_qman_ad(v):
            self.sp_qb_ad.setEnabled(v); self.sp_qf_ad.setEnabled(v)
            self.sp_cad.setEnabled(not v)
            self.chk_rac_ad.setChecked(not v)
        self.chk_aad.toggled.connect(_tog_aad)
        self.chk_qman_ad.toggled.connect(_tog_qman_ad)
        _tog_aad(self.chk_aad.isChecked())

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel
                              | QDialogButtonBox.StandardButton.Help)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        bb.helpRequested.connect(self._help)
        lay.addWidget(bb)

    # ---------- Pick (muestrear DEM) ----------
    def _pick_cab(self):
        if self._z_cab_dem is not None:
            self.sp_zcab.setValue(self._z_cab_dem)

    def _pick_boca(self):
        if self._z_boca_dem is not None:
            self.sp_zboca.setValue(self._z_boca_dem)

    def _act_c_factor(self):
        # mostrar con 2 decimales (el cálculo usa siempre el valor completo)
        self.lb_c_factor.setText(f"= {1.5 * self.sp_dist_swale.value():.2f} m")

    def _help(self):
        from qgis.PyQt.QtWidgets import QMessageBox
        QMessageBox.information(
            self, "Help — Channel Settings",
            "Geometry: velocity is inversely related to channel cross-sectional "
            "area for a given discharge (Q/a = v). Width-to-depth and sinuosity "
            "are set separately for reaches steeper (A/Aa+ types) and milder "
            "(Bc/C types) than 4 %. The mouth elevation of the MAIN channel and "
            "the slope immediately downstream may be the most critical values "
            "of the whole design.\n\n"
            "Watershed: the Rational Runoff Method (Qpk = C·i·A) computes the "
            "bankfull (2-yr, 1-hr) and flood-prone (50-yr, 6-hr) discharges "
            "with the watershed area accumulating downstream. Additional "
            "watershed area lets run-on water from outside the design "
            "boundary enter this channel at its head or evenly along it.")

    # ---------- aplicar ----------
    def aplicar(self):
        c = self.c
        c.vel_max_agua = self.sp_vel.value()
        c.pendiente_cabecera_pct = self.sp_pcab.value()
        if self.sp_pboca.isEnabled():
            c.pendiente_boca_pct = self.sp_pboca.value()
        c.wd_pend_mayor_004 = self.sp_wd1.value()
        c.wd_pend_menor_004 = self.sp_wd2.value()
        c.sinuosidad_mayor_004 = self.sp_s1.value()
        c.sinuosidad_menor_004 = self.sp_s2.value()
        n = self.sp_sub.value()
        c.espaciado_subcrestas = n if n % 2 == 1 else n + 1  # must be odd
        c.cota_cabecera = self.sp_zcab.value() if self.chk_zcab.isChecked() else None
        c.cota_boca = self.sp_zboca.value() if self.chk_zboca.isChecked() else None
        c.especificar_convexo = self.chk_conv.isChecked()
        c.dist_cresta_swale_m = self.sp_dist_swale.value()
        c.convexo_modo_canal = "pct" if self.chk_c_pct.isChecked() else "factor"
        c.convexo_pct_canal = self.sp_c_pct.value()
        c.factores_aleatorios = self.chk_rand.isChecked()
        c.n_manning = self.sp_n.value()
        c.d50_mm = self.sp_d50.value() if self.chk_d50.isChecked() else None
        c.usar_metodo_racional = self.chk_rac.isChecked()
        c.coef_escorrentia = self.sp_c.value()
        if self.chk_qman.isChecked():
            c.qpk_manual_bankfull = self.sp_qb.value()
            c.qpk_manual_flood = self.sp_qf.value()
        else:
            c.qpk_manual_bankfull = None
            c.qpk_manual_flood = None
        c.area_adicional_ha = self.sp_aad.value() if self.chk_aad.isChecked() else 0.0
        c.area_adicional_en_cabecera = self.rb_head.isChecked()
        c.usar_racional_adicional = not self.chk_qman_ad.isChecked()
        c.coef_escorrentia_adicional = self.sp_cad.value()
        if self.chk_aad.isChecked() and self.chk_qman_ad.isChecked():
            c.qpk_adic_bankfull = self.sp_qb_ad.value()
            c.qpk_adic_flood = self.sp_qf_ad.value()
        else:
            c.qpk_adic_bankfull = None
            c.qpk_adic_flood = None
