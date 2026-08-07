# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""GeoFluvQ plugin entry point.

Adds the 'Natural Regrade' top menu (same commands as the original module's
pulldown menu) plus a toolbar button that toggles the GeoFluv dockable dialog.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon

from .core.compat import QAction

MENU_TITLE = "Natural &Regrade"


class GeoFluvQPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dock = None
        self.action = None
        self.menu_actions = []

    # ---------- helpers ----------
    def _ensure_dock(self, mostrar=True):
        from .gui.dock import GeoFluvDock
        if self.dock is None:
            self.dock = GeoFluvDock(self.iface, self.iface.mainWindow())
            self.iface.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea
                                     if hasattr(Qt, "DockWidgetArea")
                                     else Qt.LeftDockWidgetArea, self.dock)
            # el panel se usa FLOTANTE: addDockWidget lo acopla, así que se
            # suelta inmediatamente (el dock lo reafirma en su showEvent)
            self.dock.setFloating(True)
            self.dock.visibilityChanged.connect(
                lambda vis: self.action.setChecked(vis) if self.action else None)
        if mostrar:
            self.dock.show()
            self.dock.raise_()
        return self.dock

    def _dock_cmd(self, nombre_metodo):
        """Run a dock method from the menu, creating the dock if needed."""
        d = self._ensure_dock()
        getattr(d, nombre_metodo)()

    def _menu_add(self, texto, slot):
        a = QAction(texto, self.iface.mainWindow())
        a.triggered.connect(slot)
        self.iface.addPluginToMenu(MENU_TITLE, a)
        self.menu_actions.append(a)
        return a

    # ---------- QGIS hooks ----------
    def initGui(self):
        icono = QIcon(os.path.join(os.path.dirname(__file__), "icon.png"))
        self.action = QAction(icono, "Design GeoFluv Regrade", self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self.toggle_dock)
        self.iface.addToolBarIcon(self.action)

        # --- 'Natural Regrade' menu (same order as the original pulldown) ---
        self._menu_add("Design GeoFluv Regrade", lambda: self.toggle_dock(True))
        self._menu_add("Draw GeoFluv Contours",
                       lambda: self._dock_cmd("_recontornear"))
        self._menu_add("3D GeoFluv Contour Viewer",
                       lambda: self._ensure_dock()._viewer_3d(False))
        self._menu_add("3D GeoFluv Surface Viewer",
                       lambda: self._ensure_dock()._viewer_3d(True))
        self._menu_add("Calculate GeoFluv Volume",
                       lambda: self._dock_cmd("_corte_relleno"))
        self._menu_add("Cut/Fill Centroids",
                       lambda: self._dock_cmd("_centroides"))
        self._menu_add("GeoFluv Channel Cross-Section Report",
                       lambda: self._dock_cmd("_ver_informe"))
        self._menu_add("Project Inspector Definitions",
                       lambda: self._dock_cmd("_def_inspector"))
        self._menu_add("GeoFluv Project Inspector",
                       lambda: self._ensure_dock().btn_inspector.setChecked(True))
        self._menu_add("View Longitudinal Profile",
                       lambda: self._dock_cmd("_ver_perfil"))
        self._menu_add("Edit Longitudinal Profile",
                       lambda: self._dock_cmd("_edit_profile"))
        self._menu_add("Auto Longitudinal Profile",
                       lambda: self._dock_cmd("_auto_perfil"))
        self._menu_add("Create Vegetation Scene",
                       lambda: self._dock_cmd("_crear_vegetacion"))

    def toggle_dock(self, checked=None):
        d = self._ensure_dock(mostrar=False)
        visible = d.isVisible()
        if checked is True or not visible:
            d.show(); d.raise_()
            if self.action:
                self.action.setChecked(True)
        else:
            d.hide()
            if self.action:
                self.action.setChecked(False)

    def unload(self):
        for a in self.menu_actions:
            self.iface.removePluginMenu(MENU_TITLE, a)
        self.menu_actions = []
        if self.action is not None:
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if self.dock is not None:
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
