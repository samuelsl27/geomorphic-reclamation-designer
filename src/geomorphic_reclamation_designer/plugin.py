# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Punto de entrada del complemento.

Añade el menú 'Geomorphic Reclamation' y un botón de barra que muestra u oculta
el panel acoplable. El orden de los comandos sigue la secuencia de trabajo del
método publicado.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon

from .core.compat import QAction

MENU_TITLE = "Geomorphic &Reclamation"


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
        self.action = QAction(icono, "Geomorphic Reclamation Designer",
                              self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.triggered.connect(self.toggle_dock)
        self.iface.addToolBarIcon(self.action)

        # --- menú 'Geomorphic Reclamation' (orden de la secuencia de trabajo) ---
        self._menu_add("Design Regrade", lambda: self.toggle_dock(True))
        self._menu_add("Draw Design Contours",
                       lambda: self._dock_cmd("_recontornear"))
        self._menu_add("3D Contour Viewer",
                       lambda: self._ensure_dock()._viewer_3d(False))
        self._menu_add("3D Surface Viewer",
                       lambda: self._ensure_dock()._viewer_3d(True))
        self._menu_add("Calculate Design Volume",
                       lambda: self._dock_cmd("_corte_relleno"))
        self._menu_add("Cut/Fill Centroids",
                       lambda: self._dock_cmd("_centroides"))
        self._menu_add("Channel Cross-Section Report",
                       lambda: self._dock_cmd("_ver_informe"))
        self._menu_add("Project Inspector Definitions",
                       lambda: self._dock_cmd("_def_inspector"))
        self._menu_add("Project Inspector",
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
