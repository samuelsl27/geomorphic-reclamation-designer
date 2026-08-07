# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Design reports (equivalent to the original 'Report', 'Channel Cross-Section
Report' and 'Summary Report'). Station-based layout mirrors the original:
stations are measured along the centerline, starting from the headwaters;
left and right are from the point of view of looking downstream."""

from qgis.PyQt.QtGui import QFont
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QPlainTextEdit, QDialogButtonBox, QPushButton,
    QFileDialog,
)


def informe_canal(d):
    """Detailed by-station report of a ChannelDesign (Cross-Section Report)."""
    ln = []
    ln.append(f"Report on Channel '{d.nombre}'")
    ln.append("=" * 64)
    ln.append(f"Receiving channel:         {d.padre or '(main channel)'}"
              + (f"   {d.lado} bank" if d.lado else ""))
    ln.append(f"Subwatershed area:         {d.area_propia_ha:,.2f} ha")
    ln.append(f"Accumulated area at mouth: {d.area_acumulada_ha:,.2f} ha")
    ln.append(f"Valley length:             {d.L_valle:,.1f} m")
    ln.append(f"Channel length:            {d.long_canal:,.1f} m")
    ln.append(f"Sinuosity (average):       {d.sinuosidad_real:,.3f}")
    ln.append(f"Drainage density:          {d.dd_m_ha:,.1f} m/ha")
    ln.append(f"Head / base elevation:     {d.perfil.z_cabecera:,.2f} / "
              f"{d.perfil.z_boca:,.2f} m   (relief {d.perfil.z_cabecera - d.perfil.z_boca:,.2f} m)")
    ln.append(f"Head / base slope:         {d.perfil.s_cabecera*100:,.2f} % / "
              f"{d.perfil.s_boca*100:,.2f} %")
    if d.s_transicion is not None:
        ln.append(f"A -> valley transition:    station {d.s_transicion:,.1f} m")
    else:
        ln.append("A -> valley transition:    (no A-type reach)")
    ln.append(f"Bankfull Qpk at mouth:     {d.q_bankfull_boca:,.3f} m³/s")
    ln.append(f"Flood-prone Qpk at mouth:  {d.q_flood_boca:,.3f} m³/s")
    ln.append("")
    ln.append("Stations are measured along the centerline, starting at the")
    ln.append("headwaters (station 0). Stationing increases downstream.")
    ln.append("-" * 64)
    for s in d.secciones:
        ln.append("")
        ln.append(f"station (m):               {s['estacion']:.1f}   [{s['tipo']}]")
        ln.append(f"  slope at station:        {s['pendiente']:.2f} %")
        ln.append(f"  centerline elev:         {s['cota']:.2f} m")
        ln.append(f"  watershed area:          {s['area_ha']:.2f} ha")
        ln.append(f"  bankfull / flood Qpk:    {s['q_bankfull']:.3f} / {s['q_flood']:.3f} m³/s")
        ln.append(f"  bankfull width (m):      {s['ancho_bankfull']:.2f}")
        ln.append(f"  bankfull depth (m):      {s['prof_bankfull']:.2f}")
        ln.append(f"  bankfull area (sq.m.):   {s['area_bankfull']:.2f}")
        ln.append(f"  wetted perim. / R (m):   {s['perim_bkf']:.2f} / {s['radio_hidr']:.2f}")
        ln.append(f"  flood prone width (m):   {s['ancho_flood']:.2f}")
        ln.append(f"  flood prone depth (m):   {s['prof_flood']:.2f}")
        ln.append(f"  flood prone area (sq.m.):{s['area_flood']:.2f}")
        ln.append(f"  entrenchment ratio:      {s['entrench']:.2f}")
        ln.append(f"  bottom width (m):        {s['ancho_fondo']:.2f}")
        ln.append("  right side slope (%):    25.00")
        ln.append("  left side slope (%):     25.00")
        ln.append(f"  tractive force, bankfull / flood prone (N/m²): "
                  f"{s['tension_bkf']:.1f} / {s['tension_fld']:.1f}")
        if s['tau_crit'] > 0:
            ln.append(f"  Shields critical τ:      {s['tau_crit']:.1f} N/m²  ->  "
                      f"τ/τcrit = {s['ratio_tau']:.2f}  [{s['estab_tau']}]")
        ln.append(f"  Manning: normal depth    {s['calado_man']:.2f} m · "
                  f"v {s['vel_man']:.2f} m/s · F {s['froude']:.2f}  [{s['verif_man']}]")
        ln.append(f"  meander: λ {s['long_meandro']:.1f} m · belt >= "
                  f"{s['cinturon']:.1f} m · Rc {s['radio_curv']:.1f} m")
    return "\n".join(ln)


def informe_resumen(disenos, glob, area_total_ha, dd_global, rosgen=True):
    """Summary report of all channels (Summary Report)."""
    ln = []
    ln.append("Design Summary Report")
    ln.append("=" * 72)
    ln.append(f"Total area within design boundary:  {area_total_ha:,.2f} ha")
    ln.append(f"Overall drainage density:            {dd_global:,.1f} m/ha "
              f"(target {glob.dd_objetivo:,.0f} ± {glob.dd_varianza_pct:,.0f} %)")
    ln.append(f"Design storms:                       {glob.p_2a_1h_mm/10:g} cm (2-yr,1-hr) / "
              f"{glob.p_50a_6h_mm/10:g} cm (50-yr,6-hr)")
    ln.append("")
    cab = (f"{'channel':22s}{'area(ha)':>10s}{'valley(m)':>11s}{'sinuos.':>8s}"
           f"{'dd(m/ha)':>9s}{'headZ':>8s}{'baseZ':>8s}{'Qbkf(m³/s)':>11s}")
    ln.append(cab)
    ln.append("-" * len(cab))
    for d in disenos.values():
        ln.append(f"{d.nombre[:22]:22s}{d.area_propia_ha:>10.2f}{d.L_valle:>11.1f}"
                  f"{d.sinuosidad_real:>8.3f}{d.dd_m_ha:>9.1f}"
                  f"{d.perfil.z_cabecera:>8.2f}{d.perfil.z_boca:>8.2f}"
                  f"{d.q_bankfull_boca:>11.3f}")
    if rosgen:
        ln.append("")
        ln.append("Rosgen example channel types (reference values):")
        ln.append("  A/Aa+ : slope > 4 %, sinuosity < 1.2, W:D < 12")
        ln.append("  Bc    : slope 2-4 %, sinuosity ~1.2-1.4")
        ln.append("  C     : slope < 2 %, sinuosity > 1.2, W:D > 12")
        ln.append("  E     : slope < 2 %, sinuosity > 1.5, W:D < 12")
    ln.append("")
    avisos = []
    for d in disenos.values():
        avisos.extend(d.avisos)
    if avisos:
        ln.append("WARNINGS:")
        for a in avisos:
            ln.append(f"  · {a}")
    return "\n".join(ln)


class ReportDialog(QDialog):
    def __init__(self, titulo, texto, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        lay = QVBoxLayout(self)
        ed = QPlainTextEdit()
        ed.setPlainText(texto)
        ed.setReadOnly(True)
        f = QFont("Monospace"); f.setStyleHint(QFont.StyleHint.TypeWriter); f.setPointSize(9)
        ed.setFont(f)
        lay.addWidget(ed)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn = QPushButton("Save...")

        def guardar():
            ruta, _ = QFileDialog.getSaveFileName(self, "Save report", "",
                                                  "Text (*.txt)")
            if ruta:
                with open(ruta, "w", encoding="utf-8") as fh:
                    fh.write(texto)
        btn.clicked.connect(guardar)
        bb.addButton(btn, QDialogButtonBox.ButtonRole.ActionRole)
        bb.accepted.connect(self.accept)
        lay.addWidget(bb)
        self.resize(720, 560)
