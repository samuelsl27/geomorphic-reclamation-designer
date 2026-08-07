# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""GeoFluv Project Inspector — equivalent to the original 'GeoFluv Channel
Inspector'. With the tool active, moving the cursor over the map finds the
nearest designed channel, projects the cursor on its centerline and shows the
CONTINUOUS hydraulic information at that station in a floating panel (not just
at the stored cross-section stations): station, elevation, slope, watershed
area, discharges, bankfull and flood-prone sections, hydraulic radius,
tractive force vs Shields critical, Manning verification and meander geometry.

Everything is computed on the fly with builder.hidraulica_estacion(), so it
always reflects the current settings and design. The data groups shown are
configured in 'Project Inspector Definitions'.
"""

import math

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialog, QLabel, QVBoxLayout
from qgis.PyQt.QtGui import QColor
from qgis.core import QgsGeometry, QgsPointXY
from qgis.gui import QgsMapTool, QgsVertexMarker

from ..core.builder import hidraulica_estacion

DIST_MAX_FACTOR = 0.15   # snap distance: 15 % of the view width


class InspectorPanel(QDialog):
    """Floating panel with the hydraulic data sheet under the cursor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GeoFluv Project Inspector")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint
                            if hasattr(Qt, "WindowType")
                            else self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(260)
        lay = QVBoxLayout(self)
        self.lbl = QLabel("Move the cursor over a designed channel...")
        self.lbl.setTextFormat(Qt.TextFormat.RichText if hasattr(Qt, "TextFormat")
                               else Qt.RichText)
        self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)

    def mostrar(self, est, grupos=None):
        if est is None:
            self.lbl.setText("<i>No channel near the cursor.</i>")
            return
        g = grupos if grupos is not None else {"watershed", "bankfull", "flood",
                                               "tractive", "manning", "meander"}
        colores = {"ok": "#2e9e46", "high": "#d40000",
                   "v_high": "#d40000", "v_low": "#ff9900"}
        c_tau = colores.get(est["estab_tau"], "#2e9e46")
        c_man = colores.get(est["verif_man"], "#2e9e46")
        filas = []

        def fila(a, va, b="", vb=""):
            filas.append(f'<tr><td>{a}</td><td align="right">{va}</td>'
                         f'<td>&nbsp;&nbsp;{b}</td><td align="right">{vb}</td></tr>')

        fila("Elevation", f"<b>{est['cota']:.2f} m</b>",
             "Slope", f"<b>{est['pendiente']:.2f} %</b>")
        if "watershed" in g:
            fila("Watershed area", f"{est['area_ha']:.2f} ha",
                 "W:D used", f"{est['wd_usado']:g}")
            filas.append('<tr><td colspan="4"><hr/></td></tr>')
            fila("Bankfull Qpk (2yr-1hr)", f"<b>{est['q_bankfull']:.3f} m³/s</b>",
                 "Flood Qpk (50yr-6hr)", f"<b>{est['q_flood']:.3f} m³/s</b>")
        if "bankfull" in g:
            fila("Bankfull width", f"{est['ancho_bankfull']:.2f} m",
                 "Bankfull depth", f"{est['prof_bankfull']:.2f} m")
            fila("Bankfull area", f"{est['area_bankfull']:.2f} m²",
                 "Bottom width", f"{est['ancho_fondo']:.2f} m")
            fila("Wetted perimeter", f"{est['perim_bkf']:.2f} m",
                 "Hydraulic radius", f"{est['radio_hidr']:.2f} m")
        if "flood" in g:
            fila("Flood prone width", f"{est['ancho_flood']:.2f} m",
                 "Flood prone depth", f"{est['prof_flood']:.2f} m")
            fila("Entrenchment ratio", f"{est['entrench']:.2f}",
                 "Side slopes", "4H:1V (25 %)")
        if "tractive" in g:
            filas.append('<tr><td colspan="4"><hr/></td></tr>')
            fila("Tractive force bankfull", f"{est['tension_bkf']:.1f} N/m²",
                 "flood prone", f"{est['tension_fld']:.1f} N/m²")
            fila("τ critical (Shields)", f"{est['tau_crit']:.1f} N/m²",
                 "τ/τcrit",
                 f'<b style="color:{c_tau}">{est["ratio_tau"]:.2f} '
                 f'({est["estab_tau"]})</b>')
        if "manning" in g:
            fila("Manning depth", f"{est['calado_man']:.2f} m",
                 "velocity",
                 f'<b style="color:{c_man}">{est["vel_man"]:.2f} m/s '
                 f'({est["verif_man"]})</b>')
            fila("Froude number", f"{est['froude']:.2f}")
        if "meander" in g:
            filas.append('<tr><td colspan="4"><hr/></td></tr>')
            fila("Meander length λ", f"{est['long_meandro']:.1f} m",
                 "Radius of curvature", f"{est['radio_curv']:.1f} m")
            fila("Belt width (2.5-3.2·W)",
                 f"{est['cinturon']:.1f}-{est['cinturon'] / 2.5 * 3.2:.1f} m")
        html = (f'<b style="font-size:11pt">{est["canal"]}</b> — '
                f'station <b>{est["estacion"]:.1f} m</b> (type {est["tipo"]})<br/>'
                f'<table cellspacing="0" cellpadding="1" style="font-size:9pt">'
                + "".join(filas) + "</table>")
        self.lbl.setText(html)


class InspectorTool(QgsMapTool):
    """Map tool: tracks the cursor and queries the design."""

    def __init__(self, canvas, obtener_disenos, obtener_settings,
                 obtener_grupos=None):
        """obtener_disenos(): dict name->ChannelDesign of the last design.
        obtener_settings(): current GlobalSettings.
        obtener_grupos(): set of data groups to display (Inspector Definitions)."""
        super().__init__(canvas)
        self.canvas = canvas
        self._disenos = obtener_disenos
        self._glob = obtener_settings
        self._grupos = obtener_grupos or (lambda: None)
        self.panel = None
        self.marker = None
        self._geoms = {}      # name -> (2D QgsGeometry of axis, [station per vertex])

    # ---------- lifecycle ----------
    def activate(self):
        super().activate()
        self._geoms = {}
        if self.panel is None:
            self.panel = InspectorPanel(self.canvas.window())
        self.panel.show()
        if self.marker is None:
            self.marker = QgsVertexMarker(self.canvas)
            self.marker.setColor(QColor(255, 0, 120))
            self.marker.setIconType(QgsVertexMarker.ICON_CIRCLE)
            self.marker.setIconSize(12)
            self.marker.setPenWidth(2)
        self.marker.hide()

    def deactivate(self):
        if self.panel is not None:
            self.panel.hide()
        if self.marker is not None:
            self.marker.hide()
        super().deactivate()

    # ---------- cached geometries ----------
    def _geometrias(self):
        disenos = self._disenos() or {}
        for nombre, d in disenos.items():
            if nombre not in self._geoms and d.puntos:
                pts = [QgsPointXY(p[0], p[1]) for p in d.puntos]
                self._geoms[nombre] = (QgsGeometry.fromPolylineXY(pts),
                                       [p[3] for p in d.puntos])
        for nombre in list(self._geoms.keys()):
            if nombre not in disenos:
                del self._geoms[nombre]
        return disenos

    # ---------- main event ----------
    def canvasMoveEvent(self, e):
        disenos = self._geometrias()
        if not disenos or self.panel is None:
            return
        pt = self.toMapCoordinates(e.pos())
        mejor = None      # (dist, name, projected point, valley station)
        for nombre, (geom, s_list) in self._geoms.items():
            d = disenos.get(nombre)
            if d is None or geom.isEmpty():
                continue
            res = geom.closestSegmentWithContext(QgsPointXY(pt))
            try:
                sqr_dist, p_min, after, _ = res
            except Exception:
                continue
            dist = math.sqrt(max(sqr_dist, 0.0))
            if mejor is None or dist < mejor[0]:
                i1 = max(1, min(after, len(s_list) - 1))
                i0 = i1 - 1
                v0 = geom.vertexAt(i0)
                d_seg = math.hypot(p_min.x() - v0.x(), p_min.y() - v0.y())
                s_v = s_list[i0] + min(d_seg, abs(s_list[i1] - s_list[i0]))
                mejor = (dist, nombre, p_min, s_v)

        umbral = self.canvas.extent().width() * DIST_MAX_FACTOR
        if mejor is None or mejor[0] > umbral:
            self.panel.mostrar(None)
            if self.marker:
                self.marker.hide()
            return
        _, nombre, p_min, s_v = mejor
        d = disenos[nombre]
        est = hidraulica_estacion(d, s_v, self._glob())
        self.panel.mostrar(est, self._grupos())
        if self.marker:
            self.marker.setCenter(QgsPointXY(p_min.x(), p_min.y()))
            self.marker.show()

    def keyPressEvent(self, e):
        try:
            if e.key() == Qt.Key.Key_Escape:
                self.canvas.unsetMapTool(self)
        except Exception:
            pass
