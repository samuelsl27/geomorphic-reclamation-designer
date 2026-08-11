# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Panel acoplable principal. La disposición sigue el orden de trabajo descrito
para el método publicado:

    [File...]  [Settings...]
    Setup | Channels | Output | DWG
    [Exit] [Help]

Commands are arranged in the input and operational sequence the user would
normally follow (left-to-right, top-to-bottom); prerequisite commands/inputs
are inactive until the prerequisite step is performed, as in the original.
"""

import os
import shutil
import time

from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTabWidget,
    QLabel, QComboBox, QFileDialog, QMessageBox, QFormLayout, QGroupBox,
    QDialog, QCheckBox, QRadioButton, QDialogButtonBox, QLineEdit,
    QDoubleSpinBox, QSpinBox, QSlider, QButtonGroup, QScrollArea, QFrame,
    QApplication,
)
from qgis.core import QgsProject, QgsRasterLayer, QgsGeometry, QgsVectorLayer
from qgis.gui import QgsMapLayerComboBox, QgsMapToolIdentifyFeature

from ..core.project import (GeoFluvProject, EXT_PROYECTO, FILTRO_PROYECTO,
                            nombre_desde_ruta)
from ..core.params import ChannelSettings
from ..core.layer_manager import LayerManager
from ..core import setup_tools as st
from ..core.compat import (filtro_capas_raster, filtro_capas_poligono,
                           filtro_capas_linea, nivel_msg)
from .settings_dialog import SettingsDialog

VERSION = "1.0.23"

# Ancho mínimo del CONTENIDO del panel (no del panel): por debajo de esto
# los controles se solaparían, así que aparece la barra horizontal.
ANCHO_CONTENIDO = 430


def _etiqueta_valor(txt="-"):
    lb = QLabel(txt)
    lb.setStyleSheet("QLabel{background:#f0f0f0;padding:2px;border:1px solid #ccc;}")
    return lb


# ============================================================ small dialogs
class FileDialogGF(QDialog):
    """'Open And Save Projects' dialog (File...)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open And Save Projects")
        self.opcion = None
        v = QVBoxLayout(self)
        for txt, key in (("New...", "new"), ("Open...", "open"),
                         ("Save As...", "save")):
            b = QPushButton(txt)
            b.clicked.connect(lambda _, k=key: self._elegir(k))
            v.addWidget(b)
        b_c = QPushButton("Cancel"); b_c.clicked.connect(self.reject)
        v.addWidget(b_c)
        self.setMinimumWidth(260)

    def _elegir(self, k):
        self.opcion = k
        self.accept()


class PickLayerDialog(QDialog):
    """Choose which layer to pick the boundary / valley bottoms from: the
    design layers by default, but any user layer can be selected instead
    (this is QGIS: inputs may live in any polygon/line layer)."""

    def __init__(self, titulo, filtro, defecto, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Layer to select the feature from:"))
        self.cb = QgsMapLayerComboBox()
        self.cb.setFilters(filtro)
        v.addWidget(self.cb)
        # preseleccionar la capa por defecto (GRD_*) si existe
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.name() == defecto:
                self.cb.setLayer(lyr)
                break
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)


class SurfaceElevDialog(QDialog):
    """'Surface for Elevations' — QGIS works with raster DEMs instead of the
    original TIN files: pick a loaded raster or browse for a file."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Surface for Elevations")
        self.ruta = None
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Use an existing raster DEM or load a new one\n"
                           "(equivalent to the original TIN surface file):"))
        self.cb = QgsMapLayerComboBox()
        self.cb.setFilters(filtro_capas_raster())
        v.addWidget(self.cb)
        b_file = QPushButton("Browse for raster file...")
        b_file.clicked.connect(self._browse)
        v.addWidget(b_file)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _browse(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Surface for Elevations (DEM)", "",
            "Raster (*.tif *.tiff *.asc *.vrt *.img)")
        if ruta:
            self.ruta = ruta
            self.accept()


class DrawSurfaceDialog(QDialog):
    """'Draw Design Surface' options dialog."""

    def __init__(self, glob, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Draw Design Surface")
        v = QVBoxLayout(self)
        v.addWidget(QLabel(
            "Draws the draft design surface using as inputs the 2D valley\n"
            "bottom polylines, the Design Boundary, the Pre-Disturbed\n"
            "Surface, and the various settings.  Press OK to continue."))
        f = QFormLayout()
        f.addRow("Channel Layer:", QLabel("GRD_Channels"))
        f.addRow("Ridge Layer:", QLabel("GRD_Ridges"))
        self.chk_sub = QCheckBox("Sub-Watershed Layer:  GRD_SubWatershed")
        self.chk_sub.setChecked(True)
        f.addRow(self.chk_sub)
        self.chk_trim = QCheckBox("Trim intersecting channels")
        self.chk_trim.setChecked(True); self.chk_trim.setEnabled(False)
        f.addRow(self.chk_trim)
        self.chk_contour = QCheckBox("Triangulate and Contour")
        self.chk_contour.setChecked(True)
        f.addRow(self.chk_contour)
        self.cb_lineas = QComboBox()
        for n in ("3", "5", "7"):
            self.cb_lineas.addItem(n)
        self.cb_lineas.setCurrentText(str(getattr(glob, "lineas_por_canal", 7)))
        f.addRow("Number of lines in a channel:", self.cb_lineas)
        v.addLayout(f)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)


class LayerStorageDialog(QDialog):
    """'Create Design Layers' — dónde se guardan las capas del diseño."""

    def __init__(self, glob, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Design Layers")
        self.carpeta = ""
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Where should the design layers be stored?"))
        g = QGroupBox("Layer storage")
        vg = QVBoxLayout(g)
        self.rb_mem = QRadioButton(
            "Virtual (memory) layers — fast, lost when QGIS closes")
        self.rb_ruta = QRadioButton("Save layers to a folder I choose...")
        self.rb_proy = QRadioButton(
            "Save layers in the project folder (new dated sub-folder)")
        grp = QButtonGroup(self)
        for rb in (self.rb_mem, self.rb_ruta, self.rb_proy):
            grp.addButton(rb); vg.addWidget(rb)
        modo = getattr(glob, "modo_almacenamiento", "memory")
        {"memory": self.rb_mem, "ruta": self.rb_ruta,
         "proyecto": self.rb_proy}.get(modo, self.rb_mem).setChecked(True)
        h = QHBoxLayout()
        self.ed_ruta = QLineEdit(getattr(glob, "carpeta_capas", "") or "")
        b = QPushButton("Browse...")
        b.clicked.connect(self._browse)
        h.addWidget(self.ed_ruta); h.addWidget(b)
        vg.addLayout(h)
        vg.addWidget(QLabel(
            "The project-folder option creates <project name>_<date>_<time>\n"
            "next to the saved .qgz, so every run keeps its own layer set."))
        v.addWidget(g)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Folder for the design layers")
        if d:
            self.ed_ruta.setText(d)
            self.rb_ruta.setChecked(True)

    def resultado(self):
        """Devuelve (modo, carpeta)."""
        if self.rb_mem.isChecked():
            return "memory", ""
        if self.rb_ruta.isChecked():
            return "ruta", self.ed_ruta.text().strip()
        return "proyecto", ""


class TriangulateContourDialog(QDialog):
    """'Triangulate and Contour From TIN' — ventana emergente del original.

    Pestañas Triangulate | Contour, con los ajustes que en QGIS tienen
    sentido: resolución del ráster de salida, redondeo/naturalidad de la
    superficie, recorte al límite, intervalo y suavizado Bezier de las curvas.
    """

    def __init__(self, glob, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Triangulate and Contour From Design TIN")
        self.glob = glob
        v = QVBoxLayout(self)
        tabs = QTabWidget()
        v.addWidget(tabs)

        # ---------------- Triangulate ----------------
        w1 = QWidget(); f1 = QFormLayout(w1)
        self.sp_celda = QDoubleSpinBox()
        self.sp_celda.setRange(0.10, 25.0); self.sp_celda.setDecimals(2)
        self.sp_celda.setSingleStep(0.25); self.sp_celda.setSuffix(" m")
        self.sp_celda.setValue(float(getattr(glob, "resolucion_dem", 1.0)))
        f1.addRow("Output surface resolution (cell size):", self.sp_celda)

        self.chk_ridval = QCheckBox("Interpolate Ridges and Valleys")
        self.chk_ridval.setChecked(True)
        self.chk_ridval.setToolTip(
            "Uses ridges, sub-ridges and swales as breaklines of the TIN.")
        f1.addRow(self.chk_ridval)

        self.chk_flat = QCheckBox("Minimize Flat Triangles (densify breaklines)")
        self.chk_flat.setChecked(bool(getattr(glob, "densificar_breaklines", True)))
        f1.addRow(self.chk_flat)
        self.sp_dens = QDoubleSpinBox()
        self.sp_dens.setRange(0.5, 100.0); self.sp_dens.setValue(
            float(getattr(glob, "intervalo_breaklines", 5.0)))
        self.sp_dens.setSuffix(" m")
        f1.addRow("    Densify interval:", self.sp_dens)

        self.chk_clip = QCheckBox("Clip surface to the Design Boundary "
                                  "(no data outside)")
        self.chk_clip.setChecked(bool(getattr(glob, "recortar_superficie", True)))
        f1.addRow(self.chk_clip)

        g_nat = QGroupBox("Surface rounding / naturalness")
        vn = QVBoxLayout(g_nat)
        vn.addWidget(QLabel(
            "A raw TIN of ridges and valleys is faceted and sharp-crested.\n"
            "Rounding applies a hillslope-diffusion (creep) low-pass filter so\n"
            "divides and interfluves look like a mature natural landscape."))
        hn = QHBoxLayout()
        self.sl_nat = QSlider(Qt.Orientation.Horizontal)
        self.sl_nat.setRange(0, 10)
        self.sl_nat.setValue(int(getattr(glob, "naturalidad", 3)))
        self.lb_nat = QLabel(str(self.sl_nat.value()))
        self.sl_nat.valueChanged.connect(lambda x: self.lb_nat.setText(str(x)))
        hn.addWidget(QLabel("Smoothing degree (0 = raw TIN):"))
        hn.addWidget(self.sl_nat); hn.addWidget(self.lb_nat)
        vn.addLayout(hn)
        hr = QHBoxLayout()
        self.sp_radio = QSpinBox(); self.sp_radio.setRange(1, 8)
        self.sp_radio.setValue(int(getattr(glob, "radio_suavizado", 1)))
        hr.addWidget(QLabel("Filter radius (cells):")); hr.addWidget(self.sp_radio)
        hr.addStretch(1)
        vn.addLayout(hr)
        f1.addRow(g_nat)
        tabs.addTab(w1, "Triangulate")

        # ---------------- Contour ----------------
        w2 = QWidget(); f2 = QFormLayout(w2)
        self.chk_draw = QCheckBox("Draw Contours")
        self.chk_draw.setChecked(True)
        f2.addRow(self.chk_draw)
        self.sp_int = QDoubleSpinBox()
        self.sp_int.setRange(0.05, 100.0); self.sp_int.setDecimals(2)
        self.sp_int.setValue(float(glob.intervalo_curvas)); self.sp_int.setSuffix(" m")
        f2.addRow("Contour Interval:", self.sp_int)
        self.chk_idx = QCheckBox("Draw Index Contours")
        self.chk_idx.setChecked(True)
        f2.addRow(self.chk_idx)
        self.sp_idx = QDoubleSpinBox()
        self.sp_idx.setRange(0.1, 500.0); self.sp_idx.setDecimals(2)
        self.sp_idx.setValue(float(glob.intervalo_curvas_maestras))
        self.sp_idx.setSuffix(" m")
        f2.addRow("    Index Interval:", self.sp_idx)
        self.sp_lmin = QDoubleSpinBox()
        self.sp_lmin.setRange(0.0, 500.0); self.sp_lmin.setDecimals(2)
        self.sp_lmin.setValue(float(getattr(glob, "long_min_curva", 0.2)))
        self.sp_lmin.setSuffix(" m")
        f2.addRow("Min Contour Length:", self.sp_lmin)

        g_sm = QGroupBox("Contour Smoothing Method")
        vs = QVBoxLayout(g_sm)
        self.rb_nosm = QRadioButton("No Smoothing")
        self.rb_bez = QRadioButton("Bezier Smoothing")
        grp = QButtonGroup(self); grp.addButton(self.rb_nosm); grp.addButton(self.rb_bez)
        self.rb_bez.setChecked(bool(getattr(glob, "bezier_curvas", True)))
        self.rb_nosm.setChecked(not self.rb_bez.isChecked())
        vs.addWidget(self.rb_nosm); vs.addWidget(self.rb_bez)
        hb = QHBoxLayout()
        self.sl_bez = QSlider(Qt.Orientation.Horizontal)
        self.sl_bez.setRange(1, 10)
        self.sl_bez.setValue(int(getattr(glob, "factor_bezier", 5)))
        self.lb_bez = QLabel(f"Bezier Smoothing Factor = {self.sl_bez.value()}")
        self.sl_bez.valueChanged.connect(
            lambda x: self.lb_bez.setText(f"Bezier Smoothing Factor = {x}"))
        hb.addWidget(self.sl_bez); hb.addWidget(self.lb_bez)
        vs.addLayout(hb)
        f2.addRow(g_sm)
        tabs.addTab(w2, "Contour")

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def aplicar(self):
        """Vuelca los valores elegidos en los ajustes globales del proyecto."""
        g = self.glob
        g.resolucion_dem = self.sp_celda.value()
        g.naturalidad = self.sl_nat.value()
        g.radio_suavizado = self.sp_radio.value()
        g.recortar_superficie = self.chk_clip.isChecked()
        g.densificar_breaklines = self.chk_flat.isChecked()
        g.intervalo_breaklines = self.sp_dens.value()
        g.intervalo_curvas = self.sp_int.value()
        g.intervalo_curvas_maestras = self.sp_idx.value() if self.chk_idx.isChecked() \
            else self.sp_int.value()
        g.long_min_curva = self.sp_lmin.value()
        g.bezier_curvas = self.rb_bez.isChecked()
        g.factor_bezier = self.sl_bez.value()
        g.dibujar_curvas = self.chk_draw.isChecked()
        return g


class SummaryOptionsDialog(QDialog):
    """'Design Summary Report' options."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Design Summary Report")
        v = QVBoxLayout(self)
        self.chk_fmt = QCheckBox("Use report formatter.")
        self.chk_rosgen = QCheckBox("Show Rosgen example channels.")
        self.chk_rosgen.setChecked(True)
        v.addWidget(self.chk_fmt); v.addWidget(self.chk_rosgen)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)


class ChangeNameDialog(QDialog):
    """'Change Channel Name' dialog."""

    def __init__(self, nombre, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Channel Name")
        f = QFormLayout(self)
        self.ed = QLineEdit(nombre)
        f.addRow("Channel name", self.ed)
        self.chk = QCheckBox("Update tributary channel names.")
        self.chk.setChecked(True)
        f.addRow(self.chk)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        f.addRow(bb)


class InspectorDefsDialog(QDialog):
    """'Project Inspector Definitions' — choose what the Inspector shows."""

    GRUPOS = [("watershed", "Watershed / discharges"),
              ("bankfull", "Bankfull cross-section"),
              ("flood", "Flood-prone cross-section"),
              ("tractive", "Tractive force (Shields)"),
              ("manning", "Manning verification"),
              ("meander", "Meander geometry")]

    def __init__(self, activos, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Project Inspector Definitions")
        v = QVBoxLayout(self)
        v.addWidget(QLabel("Data groups shown by the Project Inspector:"))
        self.chks = {}
        for clave, texto in self.GRUPOS:
            c = QCheckBox(texto); c.setChecked(clave in activos)
            self.chks[clave] = c
            v.addWidget(c)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def activos(self):
        return {k for k, c in self.chks.items() if c.isChecked()}


# ============================================================ main dock
class GeoFluvDock(QDockWidget):
    def __init__(self, iface, parent=None):
        super().__init__("Geomorphic Reclamation Designer", parent)
        self.iface = iface
        self.proyecto = GeoFluvProject()
        self.ruta_proyecto = None
        self.lm = LayerManager(iface, self.proyecto.nombre)
        self.dem_layer = None
        self._map_tool = None
        self._inspector_tool = None
        self.inspector_groups = {k for k, _ in InspectorDefsDialog.GRUPOS}
        self.diseno = {}   # name -> ChannelDesign (last generated design)

        # El panel se abre FLOTANTE y todo su contenido vive dentro de un área
        # con barras de desplazamiento. Así se puede reducir a cualquier altura
        # y anchura y lo que no quepa se recorre con la barra; antes el propio
        # contenido imponía una altura mínima y el panel no se podía achicar.
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetClosable
                         | QDockWidget.DockWidgetFeature.DockWidgetMovable
                         | QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setWidget(self._scroll)
        w = QWidget()
        self._scroll.setWidget(w)
        self._contenido = w
        lay = QVBoxLayout(w)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(4)

        # --- header ---
        lb_t = QLabel(f"Geomorphic Reclamation Designer  ver.{VERSION}")
        lb_t.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(lb_t)
        self.lb_proyecto = QLabel("<not yet saved>")
        self.lb_proyecto.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.lb_proyecto.setStyleSheet("QLabel{font-family:monospace;color:#800;}")
        lay.addWidget(self.lb_proyecto)
        fila = QHBoxLayout()
        btn_file = QPushButton("File...")
        btn_file.clicked.connect(self._menu_proyecto)
        btn_set = QPushButton("Settings...")
        btn_set.clicked.connect(self._abrir_ajustes)
        fila.addWidget(btn_file); fila.addWidget(btn_set)
        lay.addLayout(fila)

        # --- tabs ---
        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)
        self._tab_setup()
        self._tab_channels()
        self._tab_output()
        self._tab_dwg()
        self._tab_ia()
        # el conjunto de pestañas no impone altura al panel: lo que no quepa se
        # recorre con la barra de desplazamiento general
        self.tabs.setMinimumHeight(0)

        # --- footer ---
        fila2 = QHBoxLayout()
        b_exit = QPushButton("Exit"); b_exit.clicked.connect(self.close)
        b_help = QPushButton("Help"); b_help.clicked.connect(self._help)
        fila2.addWidget(b_exit); fila2.addWidget(b_help)
        lay.addLayout(fila2)

        # --- dimensiones del panel ---
        # Ni el panel ni su contenido fijan una altura mínima: el usuario puede
        # dejarlo tan pequeño como quiera y desplazarse con la barra. Solo se
        # conserva un ancho mínimo de CONTENIDO para que los controles no se
        # solapen; si el panel se estrecha más, aparece la barra horizontal.
        self.setMinimumSize(QSize(0, 0))
        self._contenido.setMinimumWidth(ANCHO_CONTENIDO)
        self._actualizar_estado_botones()

    # ---------- comportamiento de la ventana ----------
    def _geometria_inicial(self):
        """Coloca el panel flotante con un tamaño manejable y siempre visible.

        El alto es el 80 % de la pantalla disponible (con topes), de modo que
        en pantallas pequeñas o con escalado alto de Windows el panel entra
        completo; lo que no quepa se recorre con la barra de desplazamiento."""
        try:
            pantalla = None
            vent = self.iface.mainWindow() if self.iface else None
            if vent is not None and hasattr(vent, "screen"):
                pantalla = vent.screen()
            if pantalla is None:
                pantalla = QApplication.primaryScreen()
            disp = pantalla.availableGeometry()
            ancho = max(ANCHO_CONTENIDO + 34, min(int(disp.width() * 0.30), 640))
            alto = max(340, min(int(disp.height() * 0.80), 920))
            x, y = disp.x() + 40, disp.y() + 40
            if vent is not None:
                g = vent.geometry()
                x = max(disp.x(), g.x() + 60)
                y = max(disp.y(), g.y() + 90)
            x = min(x, max(disp.x(), disp.right() - ancho - 10))
            y = min(y, max(disp.y(), disp.bottom() - alto - 10))
            self.setGeometry(x, y, ancho, alto)
        except Exception:
            self.resize(520, 700)

    def showEvent(self, ev):
        """El panel se abre SIEMPRE flotante, no acoplado a un lado.

        QGIS recuerda el estado de los paneles entre sesiones y lo volvía a
        acoplar; aquí se fuerza el modo flotante la primera vez que se muestra.
        Después el usuario puede acoplarlo a mano si lo prefiere."""
        if not getattr(self, "_ya_flotante", False):
            self._ya_flotante = True
            try:
                self.setFloating(True)
                self._geometria_inicial()
            except Exception:
                pass
        super().showEvent(ev)

    # ==================== SETUP TAB ====================
    def _tab_setup(self):
        w = QWidget(); v = QVBoxLayout(w)

        self.btn_capas = QPushButton("Create Design Layers")
        self.btn_capas.setToolTip(
            "Creates the design layer tree (01 Inputs ... 04 Analysis) with "
            "GRD_Boundary and GRD_ValleyBottoms ready to draw on. Optional: you "
            "can also pick the boundary/valley bottoms from any of your own "
            "layers.")
        self.btn_capas.clicked.connect(self._crear_arbol)
        v.addWidget(self.btn_capas)

        self.btn_limite = QPushButton("Design Boundary")
        self.btn_limite.clicked.connect(self._sel_limite)
        v.addWidget(self.btn_limite)
        f0 = QFormLayout()
        self.lb_area = _etiqueta_valor("0.00")
        f0.addRow("Area (ha)", self.lb_area)
        v.addLayout(f0)

        self.btn_canal = QPushButton("Select Main Channel")
        self.btn_canal.clicked.connect(self._sel_canal_principal)
        v.addWidget(self.btn_canal)
        v.addWidget(QLabel("Data for main channel:"))
        f2 = QFormLayout()
        self.lb_cab = _etiqueta_valor(); self.lb_boca = _etiqueta_valor()
        self.lb_lval = _etiqueta_valor(); self.lb_dd = _etiqueta_valor()
        f2.addRow("Head Elev. (m)", self.lb_cab)
        f2.addRow("Base Elev. (m)", self.lb_boca)
        f2.addRow("Valley Length (m)", self.lb_lval)
        f2.addRow("Drainage Density(m/ha):", self.lb_dd)
        v.addLayout(f2)

        self.btn_surface = QPushButton("Surface for Elevations")
        self.btn_surface.clicked.connect(self._surface_for_elevations)
        v.addWidget(self.btn_surface)

        v.addWidget(QLabel("<i>Draw the boundary (polygon) in GRD_Boundary and the\n"
                           "valley bottoms (2D polylines) in GRD_ValleyBottoms.\n"
                           "Buttons activate as each prerequisite is completed.</i>"))
        v.addStretch()
        self.tabs.addTab(w, "Setup")

    # ==================== CHANNELS TAB ====================
    def _tab_channels(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.cb_canal = QComboBox()
        v.addWidget(self.cb_canal)

        fila = QHBoxLayout()
        self.btn_add = QPushButton("Add"); self.btn_del = QPushButton("Delete")
        fila.addWidget(self.btn_add); fila.addWidget(self.btn_del)
        v.addLayout(fila)
        fila_b = QHBoxLayout()
        self.btn_ren = QPushButton("Name"); self.btn_tr2 = QPushButton("Transition")
        fila_b.addWidget(self.btn_ren); fila_b.addWidget(self.btn_tr2)
        v.addLayout(fila_b)
        self.btn_vanes = QPushButton("Vanes")
        v.addWidget(self.btn_vanes)
        self.btn_add.clicked.connect(self._add_tributario)
        self.btn_del.clicked.connect(self._del_canal)
        self.btn_ren.clicked.connect(self._ren_canal)
        self.btn_tr2.clicked.connect(self._sel_transicion)
        self.btn_vanes.clicked.connect(self._vanes)

        self.btn_cfg_canal = QPushButton("Current Channel Settings...")
        self.btn_cfg_canal.clicked.connect(self._cfg_canal)
        v.addWidget(self.btn_cfg_canal)

        v.addWidget(QLabel("Settings for current channel:"))
        fs = QFormLayout()
        self.lb_s_slope = _etiqueta_valor(); self.lb_s_vel = _etiqueta_valor()
        self.lb_s_wd_menor = _etiqueta_valor(); self.lb_s_wd_mayor = _etiqueta_valor()
        fs.addRow("Upstream Slope %", self.lb_s_slope)
        fs.addRow("Max Water Vel.(m/s)", self.lb_s_vel)
        fs.addRow("W:D,slope < -0.04", self.lb_s_wd_menor)
        fs.addRow("W:D,slope > -0.04", self.lb_s_wd_mayor)
        v.addLayout(fs)

        v.addWidget(QLabel("Data for current channel:"))
        fg = QFormLayout()
        self.lb_c_lval = _etiqueta_valor()
        self.lb_c_area = _etiqueta_valor()
        self.lb_c_aad = _etiqueta_valor()
        self.lb_c_dd = _etiqueta_valor()
        fg.addRow("Valley Length(m):", self.lb_c_lval)
        fg.addRow("Reach Area(ha):", self.lb_c_area)
        fg.addRow("Add'l Area (ha)", self.lb_c_aad)
        fg.addRow("Drainage Density(m/ha):", self.lb_c_dd)
        v.addLayout(fg)

        fila2 = QHBoxLayout()
        self.btn_perfil = QPushButton("Profile")
        self.btn_informe = QPushButton("Report")
        fila2.addWidget(self.btn_perfil); fila2.addWidget(self.btn_informe)
        v.addLayout(fila2)
        self.btn_perfil.clicked.connect(self._ver_perfil)
        self.btn_informe.clicked.connect(self._ver_informe)
        self.cb_canal.currentTextChanged.connect(self._datos_canal_actual)
        v.addStretch()
        self.tabs.addTab(w, "Channels")

    # ==================== OUTPUT TAB ====================
    def _tab_output(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.btn_prev = QPushButton("Preview")
        self.btn_releer = QPushButton("Reread Valley Bottoms")
        self.btn_draw = QPushButton("Draw Design Surface...")
        for b in (self.btn_prev, self.btn_releer, self.btn_draw):
            v.addWidget(b)

        v.addWidget(QLabel("Data for design work area:"))
        fg = QFormLayout()
        self.lb_o_lval = _etiqueta_valor(); self.lb_o_area = _etiqueta_valor()
        self.lb_o_dd = _etiqueta_valor()
        fg.addRow("Valleys (m)", self.lb_o_lval)
        fg.addRow("Area (ha):", self.lb_o_area)
        fg.addRow("Drainage Density(m/ha):", self.lb_o_dd)
        v.addLayout(fg)

        self.btn_comp = QPushButton("Comparison Surface")
        v.addWidget(self.btn_comp)
        self.btn_cf = QPushButton("Update Cut / Fill")
        v.addWidget(self.btn_cf)
        fcf = QFormLayout()
        self.lb_o_cut = _etiqueta_valor(); self.lb_o_fill = _etiqueta_valor()
        self.lb_o_cf = _etiqueta_valor()
        fcf.addRow("Cut (c.m.):", self.lb_o_cut)
        fcf.addRow("Fill (c.m.):", self.lb_o_fill)
        fcf.addRow("Cut / Fill (%):", self.lb_o_cf)
        v.addLayout(fcf)

        self.btn_rep = QPushButton("Summary Report...")
        v.addWidget(self.btn_rep)
        v.addStretch()

        self.btn_prev.clicked.connect(self._preview)
        self.btn_releer.clicked.connect(self._releer_valles)
        self.btn_draw.clicked.connect(self._dibujar_superficie)
        self.btn_comp.clicked.connect(self._sel_comparacion)
        self.btn_cf.clicked.connect(self._corte_relleno)
        self.btn_rep.clicked.connect(self._ver_resumen)
        self.tabs.addTab(w, "Output")

    # ==================== DWG TAB ====================
    def _tab_dwg(self):
        w = QWidget(); v = QVBoxLayout(w)
        g = QGroupBox("Editing Mode")
        gv = QVBoxLayout(g)
        self.rb_inputs = QRadioButton("Edit design inputs.")
        self.rb_surface = QRadioButton("Edit design surface in drawing.")
        self.rb_inputs.setChecked(True)
        gv.addWidget(self.rb_inputs); gv.addWidget(self.rb_surface)
        v.addWidget(g)
        self.rb_inputs.toggled.connect(self._modo_edicion)

        self.btn_contours = QPushButton("Draw Design Contours")
        self.btn_v3d_c = QPushButton("3D Contour Viewer")
        self.btn_v3d_s = QPushButton("3D Surface Viewer")
        self.btn_vol = QPushButton("Calculate Design Volume")
        self.btn_haul = QPushButton("Mass Haul")
        self.btn_xsec = QPushButton("Channel Cross-Section Report")
        self.btn_tractiva = QPushButton("Highlight Tractive Force Zones")
        self.btn_tractiva.setCheckable(True)
        self.btn_ridge_chk = QPushButton("Check Ridgeline Slope")
        self.btn_check = QPushButton("Check Design (Error Log)")
        self.btn_check.setToolTip(
            "Runs every design check at once: crossing breaklines, slopes "
            "above target, valley walls that do not drain to their channel, "
            "tractive force, Rosgen ranges, drainage density, closed "
            "depressions and the cut/fill balance.")
        self.btn_view_prof = QPushButton("View Longitudinal Profile")
        self.btn_edit_prof = QPushButton("Edit Longitudinal Profile")
        self.btn_auto_prof = QPushButton("Auto Longitudinal Profile")
        self.btn_save_tin = QPushButton("Save Design Surface TIN")
        self.btn_sum2 = QPushButton("Summary Report...")
        self.btn_inspector = QPushButton("Project Inspector")
        self.btn_inspector.setCheckable(True)
        for b in (self.btn_contours, self.btn_v3d_c, self.btn_v3d_s, self.btn_vol,
                  self.btn_haul, self.btn_xsec, self.btn_tractiva,
                  self.btn_ridge_chk, self.btn_check, self.btn_view_prof,
                  self.btn_edit_prof, self.btn_auto_prof, self.btn_save_tin,
                  self.btn_sum2, self.btn_inspector):
            v.addWidget(b)
        v.addStretch()

        self.btn_contours.clicked.connect(self._recontornear)
        self.btn_v3d_c.clicked.connect(lambda: self._viewer_3d(False))
        self.btn_v3d_s.clicked.connect(lambda: self._viewer_3d(True))
        self.btn_vol.clicked.connect(self._corte_relleno)
        self.btn_haul.clicked.connect(self._centroides)
        self.btn_xsec.clicked.connect(self._ver_informe)
        self.btn_tractiva.toggled.connect(self._toggle_tractiva)
        self.btn_ridge_chk.clicked.connect(self._check_ridgeline)
        self.btn_check.clicked.connect(self._revisar_diseno)
        self.btn_view_prof.clicked.connect(self._ver_perfil)
        self.btn_edit_prof.clicked.connect(self._edit_profile)
        self.btn_auto_prof.clicked.connect(self._auto_perfil)
        self.btn_save_tin.clicked.connect(self._save_tin)
        self.btn_sum2.clicked.connect(self._ver_resumen)
        self.btn_inspector.toggled.connect(self._toggle_inspector)
        self.tabs.addTab(w, "DWG")

    def _tab_ia(self):
        """'AI Optimization' — pestaña OPCIONAL. Si algo falla al construirla
        (falta un módulo, versión de Qt distinta…) el resto del complemento
        sigue funcionando exactamente igual."""
        self.tab_ia = None
        try:
            from .ai_tab import AITab
            self.tab_ia = AITab(self)
            # la pestaña es larga: se le da su propio desplazamiento para que no
            # imponga altura al panel
            sc = QScrollArea()
            sc.setWidgetResizable(True)
            sc.setFrameShape(QFrame.Shape.NoFrame)
            sc.setWidget(self.tab_ia)
            self.tabs.addTab(sc, "AI Optimization")
            self.tab_ia.refrescar_canales()
        except Exception as e:
            w = QWidget()
            v = QVBoxLayout(w)
            lb = QLabel("The AI Optimization tab could not be loaded:\n"
                        f"{e}\n\nThe rest of the plugin is unaffected.")
            lb.setWordWrap(True)
            v.addWidget(lb); v.addStretch(1)
            self.tabs.addTab(w, "AI Optimization")

    # ---------- editing mode ----------
    def _modo_edicion(self, inputs_on):
        """'Edit design surface in drawing' locks the other tabs; going back
        to 'Edit design inputs' unlocks them (surface edits will be replaced
        when the design is regenerated)."""
        for i in range(3):     # Setup, Channels, Output
            self.tabs.setTabEnabled(i, inputs_on)
        if inputs_on:
            self._actualizar_estado_botones()
            if getattr(self, "ruta_superficie", None):
                self._msg("Editing design inputs again: regenerating the design "
                          "will replace manual edits of the design surface.", 1)

    # ---------- inspector ----------
    def _toggle_inspector(self, activo):
        from .inspector_tool import InspectorTool
        if activo:
            if not self.diseno:
                self._msg("Generate the channel design first (Output > Preview).", 1)
                self.btn_inspector.setChecked(False)
                return
            if self._inspector_tool is None:
                self._inspector_tool = InspectorTool(
                    self.iface.mapCanvas(),
                    lambda: self.diseno,
                    lambda: self.proyecto.settings,
                    lambda: self.inspector_groups)
                self._inspector_tool.deactivated.connect(
                    lambda: self.btn_inspector.setChecked(False))
            self.iface.mapCanvas().setMapTool(self._inspector_tool)
        else:
            if self._inspector_tool is not None and \
                    self.iface.mapCanvas().mapTool() is self._inspector_tool:
                self.iface.mapCanvas().unsetMapTool(self._inspector_tool)

    def _def_inspector(self):
        dlg = InspectorDefsDialog(self.inspector_groups, self)
        if dlg.exec():
            self.inspector_groups = dlg.activos()
            self._msg("Project Inspector definitions updated.", 3)

    def _toggle_tractiva(self, activo):
        capa = self.lm.resaltar_fuerza_tractiva(activo)
        if capa is None and activo:
            self._msg("No GRD_XSections layer yet; generate the design first.", 1)
            self.btn_tractiva.setChecked(False)
            return
        if not activo:
            return
        if capa.featureCount() == 0:
            self._msg("GRD_XSections is empty: run 'Preview'/'Draw Design Surface' "
                      "first so the cross-sections are computed.", 1)
            self.btn_tractiva.setChecked(False)
            return
        # resumen para que se vea que ha hecho algo aunque no haya zonas rojas
        alto = medio = ok = sin = 0
        for f in capa.getFeatures():
            tc, tr = f["tau_critical"], f["tau_ratio"]
            if tc is None or tc == 0:
                sin += 1
            elif tr is not None and tr > 1:
                alto += 1
            elif tr is not None and tr > 0.8:
                medio += 1
            else:
                ok += 1
        if sin == capa.featureCount():
            self._msg("No D50 set (Settings > D50 of the reference reach): the "
                      "critical shear cannot be computed, so nothing is "
                      "highlighted.", 1)
            return
        self.iface.setActiveLayer(capa)
        self.iface.mapCanvas().refreshAllLayers()
        self._msg(f"Tractive force: {alto} station(s) above τcrit (red), "
                  f"{medio} at 80-100 % (amber), {ok} safe (green)"
                  + (f", {sin} without D50 (grey)." if sin else "."),
                  1 if alto else 3)

    # ==================== logic ====================
    def _msg(self, txt, nivel=0):
        self.iface.messageBar().pushMessage("Geomorphic Reclamation", txt,
                                            level=nivel_msg(nivel), duration=6)

    def _help(self):
        """Opens the bilingual HTML parameter guide in the browser."""
        ruta = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            "help", "guide.html")
        if os.path.exists(ruta):
            from qgis.PyQt.QtCore import QUrl, QSettings, QLocale
            from qgis.PyQt.QtGui import QDesktopServices
            # idioma inicial = el de QGIS (o el del sistema). Solo es el valor
            # de partida: si el usuario ya ha elegido idioma en la guía, esa
            # elección manda y se conserva entre sesiones.
            try:
                loc = QSettings().value("locale/userLocale", "") \
                    or QLocale.system().name()
            except Exception:
                loc = ""
            lang = "es" if str(loc).lower().startswith("es") else "en"
            url = QUrl.fromLocalFile(ruta)
            url.setFragment(f"lang={lang}")
            QDesktopServices.openUrl(url)
            return
        QMessageBox.information(
            self, "Geomorphic Reclamation Designer — Help",
            "Work sequence (left-to-right, top-to-bottom):\n\n"
            "1. Setup: select the Design Boundary polygon, the Main Channel "
            "valley bottom polyline and the Surface for Elevations (DEM).\n"
            "2. Channels: Add tributary valley bottoms, set Current Channel "
            "Settings, watch the drainage density traffic-light.\n"
            "3. Output: Preview the channels and ridges, Draw Design "
            "Surface, set a Comparison Surface and Update Cut / Fill.\n"
            "4. DWG: contours, 3D viewers, volumes, mass haul, cross-section "
            "report, tractive force zones, longitudinal profiles, Project "
            "Inspector.\n\n"
            "File... saves the project (.grd.json): settings, channels and "
            "references to the input polylines. Layers are regenerable from "
            "those inputs at any time.")

    # ---------- project ----------
    def _menu_proyecto(self):
        dlg = FileDialogGF(self)
        if not dlg.exec():
            return
        if dlg.opcion == "new":
            self.proyecto = GeoFluvProject()
            self.lm = LayerManager(self.iface, self.proyecto.nombre)
            self.lb_proyecto.setText("<not yet saved>")
            self.diseno = {}
            self._refrescar_canales()
        elif dlg.opcion == "open":
            ruta, _ = QFileDialog.getOpenFileName(self, "Open Project", "",
                                                  FILTRO_PROYECTO)
            if ruta:
                self.proyecto = GeoFluvProject.cargar(ruta)
                self.ruta_proyecto = ruta
                self.lm = LayerManager(self.iface, self.proyecto.nombre)
                self.lm.configurar_almacenamiento(
                    getattr(self.proyecto.settings, "modo_almacenamiento", "memory"),
                    getattr(self.proyecto.settings, "carpeta_capas", ""))
                self.lb_proyecto.setText(os.path.basename(ruta))
                if self.proyecto.ruta_dem and os.path.exists(self.proyecto.ruta_dem):
                    self._cargar_dem(self.proyecto.ruta_dem)
                self._refrescar_canales()
                self._releer_valles()
        elif dlg.opcion == "save":
            ruta, _ = QFileDialog.getSaveFileName(self, "Save Project As", "",
                                                  FILTRO_PROYECTO)
            if ruta:
                if not ruta.endswith(EXT_PROYECTO):
                    ruta += EXT_PROYECTO
                self.ruta_proyecto = ruta
                self.proyecto.nombre = nombre_desde_ruta(ruta)
                self.proyecto.guardar(ruta)
                self.lb_proyecto.setText(os.path.basename(ruta))
                self._msg("Project saved.", 3)
        self._actualizar_estado_botones()

    def _abrir_ajustes(self):
        dlg = SettingsDialog(self.proyecto.settings, self)
        if dlg.exec():
            dlg.aplicar()
            if self.proyecto.ruta:
                self.proyecto.guardar()
            self._recalcular_dd()
            self._msg("Global settings updated.", 3)

    # ---------- map selection ----------
    def _herramienta_identificar(self, capa, callback):
        if capa is None:
            self._msg("Layer not found.", 1)
            return
        self.iface.setActiveLayer(capa)
        tool = QgsMapToolIdentifyFeature(self.iface.mapCanvas(), capa)
        tool.featureIdentified.connect(callback)
        self.iface.mapCanvas().setMapTool(tool)
        self._map_tool = tool
        self._msg(f"Click the feature on layer '{capa.name()}'.")

    def _crear_arbol(self):
        """Create Design Layers: builds the group tree and the default input
        layers. The user can draw there or use their own layers instead."""
        from ..core.layer_manager import carpeta_unica_proyecto
        s = self.proyecto.settings
        dlg = LayerStorageDialog(s, self)
        if not dlg.exec():
            return
        modo, carpeta = dlg.resultado()
        if modo == "proyecto":
            carpeta = carpeta_unica_proyecto(self.proyecto.nombre)
        elif modo == "ruta" and not carpeta:
            self._msg("No folder chosen; using virtual (memory) layers.", 1)
            modo = "memory"
        s.modo_almacenamiento = modo
        s.carpeta_capas = carpeta
        self.lm.configurar_almacenamiento(modo, carpeta)
        self.lm.crear_arbol()
        self.lm.obtener_capa("GRD_Boundary")
        self.lm.obtener_capa("GRD_ValleyBottoms")
        destino = "virtual (memory)" if modo == "memory" else carpeta
        self._msg(f"Design layer tree created — storage: {destino}. "
                  "Draw the boundary in GRD_Boundary and the valley bottoms in "
                  "GRD_ValleyBottoms (or use your own layers when selecting).", 3)
        self._actualizar_estado_botones()

    def _sel_limite(self):
        dlg = PickLayerDialog("Design Boundary", filtro_capas_poligono(),
                              self.proyecto.capa_limite, self)
        if not dlg.exec():
            return
        capa = dlg.cb.currentLayer()
        if capa is None:
            self._msg("No polygon layer available. Use 'Create Design Layers' "
                      "and draw the boundary in GRD_Boundary.", 1)
            return
        if capa.featureCount() == 0:
            self._msg(f"Layer '{capa.name()}' has no features: draw the boundary "
                      "polygon first (toggle editing).", 1)
            return
        self.proyecto.capa_limite = capa.name()
        self._herramienta_identificar(capa, self._limite_elegido)

    def _limite_elegido(self, feat):
        ok, area_ha, msg = st.validar_limite(feat.geometry())
        if not ok:
            self._msg(msg, 2)
            return
        self.proyecto.fid_limite = feat.id()
        self.lb_area.setText(f"{area_ha:,.2f}")
        self._msg("New design boundary has been accepted.", 3)
        self.iface.mapCanvas().unsetMapTool(self._map_tool)
        self._recalcular_dd()
        self._actualizar_estado_botones()

    def _geom_limite(self):
        capa = self.lm.obtener_capa(self.proyecto.capa_limite, crear=False)
        if capa is None or self.proyecto.fid_limite is None:
            return None
        f = capa.getFeature(self.proyecto.fid_limite)
        return f.geometry() if f.isValid() else None

    def _sel_canal_principal(self):
        dlg = PickLayerDialog("Select Main Channel", filtro_capas_linea(),
                              self.proyecto.capa_valles, self)
        if not dlg.exec():
            return
        capa = dlg.cb.currentLayer()
        if capa is None or capa.featureCount() == 0:
            self._msg("Draw the main valley bottom polyline first (default "
                      "layer: GRD_ValleyBottoms).", 1)
            return
        self.proyecto.capa_valles = capa.name()
        self._herramienta_identificar(capa, self._canal_elegido)

    def _canal_elegido(self, feat):
        gl = self._geom_limite()
        if gl is None:
            self._msg("Select the Design Boundary first.", 1)
            return
        ok, msg = st.validar_canal_principal(feat.geometry(), gl)
        if not ok:
            self._msg(msg, 2)
            return
        if not self.proyecto.canales:
            self.proyecto.canales.append(ChannelSettings(nombre="main"))
        cp = self.proyecto.canales[0]
        cp.fid_fondo_valle = feat.id()
        self._msg("Main channel has been accepted.", 3)
        self.iface.mapCanvas().unsetMapTool(self._map_tool)
        if self.dem_layer is not None:
            t = st.transicion_automatica(self.dem_layer, feat.geometry())
            if t:
                cp.transicion_xy = (t[0], t[1])
                self._msg(f"Automatic transition point at {t[2]:.0f} m from the head "
                          "(press Transition to override).", 0)
        self._actualizar_datos_principal()
        self._refrescar_canales()
        self._actualizar_estado_botones()

    def _sel_transicion(self):
        from qgis.gui import QgsMapToolEmitPoint
        cp = self._canal_actual()
        if cp is None:
            self._msg("No channel selected.", 1)
            return
        tool = QgsMapToolEmitPoint(self.iface.mapCanvas())

        def punto(p, btn):
            cp.transicion_xy = (p.x(), p.y())
            self.iface.mapCanvas().unsetMapTool(tool)
            self._msg("Forced transition point set.", 3)
        tool.canvasClicked.connect(punto)
        self.iface.mapCanvas().setMapTool(tool)
        self._map_tool = tool
        self._msg("Choose the forced transition point between channel types "
                  "(> -0.04 to < -0.04 slope).")

    def _vanes(self):
        """Vanes: in-channel flow-deflection structures (Rosgen-type single-arm
        vanes) placed downstream of the forced transition, alternating banks."""
        from ..core import structures
        d = self._diseno_actual()
        if d is None:
            self._generar_diseno()
            d = self._diseno_actual()
            if d is None:
                return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Vanes — channel '{d.nombre}'")
        f = QFormLayout(dlg)
        from qgis.PyQt.QtWidgets import QSpinBox, QDoubleSpinBox
        sp_n = QSpinBox(); sp_n.setRange(1, 50); sp_n.setValue(3)
        sp_esp = QDoubleSpinBox(); sp_esp.setRange(1, 20); sp_esp.setValue(4.0)
        sp_len = QDoubleSpinBox(); sp_len.setRange(0.2, 1.0); sp_len.setValue(0.75)
        sp_ang = QDoubleSpinBox(); sp_ang.setRange(5, 45); sp_ang.setValue(25.0)
        f.addRow("Number of vanes:", sp_n)
        f.addRow("Spacing (x bankfull width):", sp_esp)
        f.addRow("Arm length (x bankfull width):", sp_len)
        f.addRow("Angle upstream from bank (deg):", sp_ang)
        f.addRow(QLabel("<i>Single-arm vanes anchored at the bankfull bank,\n"
                        "pointing upstream, alternating banks, starting at the\n"
                        "forced transition point (protects the outer bank).</i>"))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if not dlg.exec():
            return
        n = structures.generar_vanes(d, self.proyecto.settings, self.lm,
                                     n_vanes=sp_n.value(),
                                     espaciado_w=sp_esp.value(),
                                     longitud_w=sp_len.value(),
                                     angulo_deg=sp_ang.value())
        self._msg(f"{n} vanes placed on '{d.nombre}' (layer GRD_Vanes).", 3)
        self.iface.mapCanvas().refreshAllLayers()

    def _crear_vegetacion(self):
        """Create Vegetation Scene: random trees/shrubs inside the boundary,
        away from the channel corridors, draped on the design surface."""
        from ..core import structures
        gl = self._geom_limite()
        if gl is None:
            self._msg("No design boundary.", 1)
            return
        if not self.diseno:
            self._generar_diseno()
        dlg = QDialog(self)
        dlg.setWindowTitle("Create Vegetation Scene")
        f = QFormLayout(dlg)
        from qgis.PyQt.QtWidgets import QSpinBox
        sp_arb = QSpinBox(); sp_arb.setRange(0, 2000); sp_arb.setValue(25)
        sp_shr = QSpinBox(); sp_shr.setRange(0, 5000); sp_shr.setValue(80)
        sp_sem = QSpinBox(); sp_sem.setRange(1, 99999); sp_sem.setValue(1234)
        f.addRow("Trees per ha:", sp_arb)
        f.addRow("Shrubs per ha:", sp_shr)
        f.addRow("Random seed:", sp_sem)
        f.addRow(QLabel("<i>Creates GRD_Vegetation (3D points with height_m).\n"
                        "In the QGIS 3D view use rule/height-based symbols or\n"
                        "billboards over GRD_DesignSurface.</i>"))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept); bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if not dlg.exec():
            return
        capa_sup = None
        if getattr(self, "ruta_superficie", None):
            capa_sup = QgsRasterLayer(self.ruta_superficie, "surf")
            if not capa_sup.isValid():
                capa_sup = None
        n_a, n_s = structures.generar_vegetacion(
            gl, self.diseno, self.lm, dem=self.dem_layer,
            capa_superficie=capa_sup, arboles_ha=sp_arb.value(),
            arbustos_ha=sp_shr.value(), semilla=sp_sem.value())
        self._msg(f"Vegetation scene: {n_a} trees + {n_s} shrubs "
                  "(layer GRD_Vegetation).", 3)
        self.iface.mapCanvas().refreshAllLayers()

    # ---------- DEM ----------
    def _surface_for_elevations(self):
        dlg = SurfaceElevDialog(self)
        if not dlg.exec():
            return
        if dlg.ruta:
            self._cargar_dem(dlg.ruta)
        else:
            lyr = dlg.cb.currentLayer()
            if lyr is not None:
                self.dem_layer = lyr
                self.proyecto.ruta_dem = lyr.source()
        if self.dem_layer is not None:
            self._msg(f"Surface for Elevations: {self.dem_layer.name()}", 3)
            self._actualizar_datos_principal()
        self._actualizar_estado_botones()

    def _cargar_dem(self, ruta):
        lyr = QgsRasterLayer(ruta, os.path.basename(ruta))
        if lyr.isValid():
            self.lm.anadir_raster_a_grupo(lyr, "01 Inputs")
            self.dem_layer = lyr
            self.proyecto.ruta_dem = ruta

    def _sel_comparacion(self):
        ruta, _ = QFileDialog.getOpenFileName(self, "Comparison Surface (DEM)", "",
                                              "Raster (*.tif *.tiff *.asc *.vrt)")
        if ruta:
            self.proyecto.ruta_dem_comparacion = ruta
            self._cargar_dem(ruta)
            self._msg("Comparison surface set. Press Update Cut / Fill.", 3)

    # ---------- data / drainage density ----------
    def _capa_valles(self):
        return self.lm.obtener_capa(self.proyecto.capa_valles, crear=False)

    def _canal_actual(self):
        nombre = self.cb_canal.currentText()
        return self.proyecto.canal_por_nombre(nombre) or self.proyecto.canal_principal()

    def _actualizar_datos_principal(self):
        cp = self.proyecto.canal_principal()
        capa = self._capa_valles()
        gl = self._geom_limite()
        if not (cp and capa and gl and cp.fid_fondo_valle is not None):
            return
        f = capa.getFeature(cp.fid_fondo_valle)
        if not f.isValid():
            return
        g = f.geometry()
        lval = st.longitud_dentro(g, gl)
        self.lb_lval.setText(f"{lval:,.1f}")
        if self.dem_layer is not None:
            pts = g.asPolyline() if not g.isMultipart() else g.asMultiPolyline()[0]
            pts = st.orientar_aguas_abajo(pts, self.dem_layer)
            zc = st.cota_dem(self.dem_layer, pts[0].x(), pts[0].y())
            zb = st.cota_dem(self.dem_layer, pts[-1].x(), pts[-1].y())
            self.lb_cab.setText(f"{zc:.2f}" if zc is not None else "-")
            self.lb_boca.setText(f"{zb:.2f}" if zb is not None else "-")
        self._recalcular_dd()

    def _recalcular_dd(self):
        gl = self._geom_limite()
        capa = self._capa_valles()
        if gl is None or capa is None:
            return
        area_ha = gl.area() / 10000.0
        ltot = 0.0
        fids = [c.fid_fondo_valle for c in self.proyecto.canales
                if c.fid_fondo_valle is not None]
        for fid in fids:
            f = capa.getFeature(fid)
            if f.isValid():
                ltot += st.longitud_dentro(f.geometry(), gl)
        dd = st.densidad_drenaje(ltot, area_ha)
        estado, dmin, dmax = st.evaluar_dd(dd, self.proyecto.settings.dd_objetivo,
                                           self.proyecto.settings.dd_varianza_pct)
        color = {"ok": "#7CFC00", "baja": "#ff6666", "alta": "#ff6666"}[estado]
        for lb in (self.lb_dd, self.lb_o_dd):
            lb.setText(f"{dd:,.1f}  (range {dmin:.0f}-{dmax:.0f})")
            lb.setStyleSheet(f"QLabel{{background:{color};padding:2px;border:1px solid #888;}}")
        self.lb_o_lval.setText(f"{ltot:,.1f}")
        self.lb_o_area.setText(f"{area_ha:,.2f}")
        if estado == "baja":
            self._msg("Drainage density LOW: lengthen or add channels "
                      "(Channels > Add).", 1)
        elif estado == "alta":
            self._msg("Drainage density HIGH: shorten or delete channels.", 1)

    def _releer_valles(self):
        self._actualizar_datos_principal()
        self._recalcular_dd()
        if self.diseno:
            self._generar_diseno()
            self._msg("Valley bottoms reread: design regenerated.", 3)
        else:
            self._msg("Valley bottoms reread: data updated.", 3)

    # ---------- design engine ----------
    def _preview(self):
        """Preview = generate channels + main ridgelines (no surface yet)."""
        self._generar_diseno()
        if not self.diseno:
            return
        gl = self._geom_limite()
        if gl is None:
            return
        from ..core import ridges
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            crs = QgsProject.instance().crs().authid()
            sub = ridges.generar_subcuencas(self.diseno, gl, self.lm, crs)
            n_cr, crestas3d, exc_cr = ridges.generar_crestas(
                self.diseno, sub, gl, self.proyecto.settings, self.dem_layer,
                self.lm)
            n_sc, n_vg, avisos_l = ridges.generar_subcrestas(
                self.diseno, gl, self.proyecto.settings, self.lm,
                dem=self.dem_layer, crestas=crestas3d)
            # --- pase topológico: las crestas de ladera mueren sobre la
            # divisoria, y del encuentro de dos nace una cresta de orden
            # superior con su valle entre medias
            from ..core import topology, divides, builder as _b
            res_top = topology.revisar(self.lm, self.proyecto.settings,
                                       log=lambda m: self._msg(m.strip(), 0))
            # --- divisorias: recorte contra el corredor del cauce y cota
            # DERIVADA de las cabeceras de ladera que llegan a ellas
            divides.ajustar_divisorias(
                self.lm, self.diseno, self.proyecto.settings,
                dem=self.dem_layer, g_lim=gl,
                log=lambda m: self._msg(m.strip(), 0))
            # --- hidráulica escalonada: cada vaguada aporta en su confluencia
            _b.recalcular_por_aportes(self.diseno, self.lm,
                                      self.proyecto.settings,
                                      log=lambda m: self._msg(m.strip(), 0))
            self._msg(f"Preview: {len(self.diseno)} channels, {n_cr} ridges, "
                      f"{n_sc} sub-ridges, {n_vg} swales.", 3)
            if exc_cr > 0.5:
                self._msg(
                    f"A ridgeline sits {exc_cr:.1f} m above the elevation its "
                    f"valley-wall slope target allows. The design lever for "
                    f"this is to move the ridgeline in plan towards the "
                    f"opposite valley, or to lower the slope target.", 1)
            for a in avisos_l:
                self._msg(a, 1)
        except Exception as e:
            self._msg(f"Preview error: {e}", 2)
        finally:
            QApplication.restoreOverrideCursor()
        self.iface.mapCanvas().refreshAllLayers()

    def _generar_diseno(self):
        from ..core.builder import GeoFluvBuilder
        if self.proyecto.fid_limite is None or not self.proyecto.canales:
            self._msg("Complete the Setup tab first (boundary and main channel).", 1)
            return
        from qgis.PyQt.QtWidgets import QApplication
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            b = GeoFluvBuilder(self.proyecto, self.lm, self.dem_layer)
            self.diseno = b.construir()
        except Exception as e:
            self.diseno = {}
            self._msg(f"Design error: {e}", 2)
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._refrescar_canales()
        self._datos_canal_actual()
        self._recalcular_dd()
        if self.proyecto.ruta:
            self.proyecto.guardar()
        n_avisos = len(b.avisos)
        self._msg(f"Design generated: {len(self.diseno)} channels."
                  + (f" {n_avisos} warnings (see Summary Report)." if n_avisos else ""), 3)
        self._actualizar_estado_botones()
        self.iface.mapCanvas().refreshAllLayers()

    def _diseno_actual(self):
        nombre = self.cb_canal.currentText()
        if nombre in self.diseno:
            return self.diseno[nombre]
        return next(iter(self.diseno.values()), None)

    def _datos_canal_actual(self, *args):
        c = self._canal_actual()
        if c is not None:
            self.lb_s_slope.setText(f"{c.pendiente_cabecera_pct:.2f}")
            self.lb_s_vel.setText(f"{c.vel_max_agua:.2f}")
            self.lb_s_wd_menor.setText(f"{c.wd_pend_menor_004:.2f}")
            self.lb_s_wd_mayor.setText(f"{c.wd_pend_mayor_004:.2f}")
            self.lb_c_aad.setText(f"{c.area_adicional_ha:,.2f}")
        d = self._diseno_actual()
        if d is None:
            return
        self.lb_c_lval.setText(f"{d.L_valle:,.1f}")
        self.lb_c_area.setText(f"{d.area_propia_ha:,.2f}")
        estado, dmin, dmax = st.evaluar_dd(d.dd_m_ha, self.proyecto.settings.dd_objetivo,
                                           self.proyecto.settings.dd_varianza_pct)
        color = {"ok": "#7CFC00", "baja": "#ff6666", "alta": "#ff6666"}[estado]
        self.lb_c_dd.setText(f"{d.dd_m_ha:,.1f}  (range {dmin:.0f}-{dmax:.0f})")
        self.lb_c_dd.setStyleSheet(
            f"QLabel{{background:{color};padding:2px;border:1px solid #888;}}")

    def _entidades_seleccionadas(self):
        """[(capa, feature)] de TODAS las capas vectoriales con selección."""
        out = []
        for l in QgsProject.instance().mapLayers().values():
            if not isinstance(l, QgsVectorLayer):
                continue
            try:
                sel = l.selectedFeatures()
            except Exception:
                continue
            for f in sel:
                out.append((l, f))
        return out

    def _ver_perfil(self):
        """View Longitudinal Profile.

        Si hay entidades seleccionadas en el proyecto (de cualquier capa), se
        dibuja el perfil longitudinal de TODAS ellas superpuestas,
        identificadas por capa y fid. Si no hay ninguna selección se muestra
        el perfil de diseño del canal activo, como hasta ahora."""
        from .profile_dialog import ProfileDialog
        from .multi_profile_dialog import (MultiProfileDialog, serie_de_geometria,
                                           traza_de_geometria)
        sel = self._entidades_seleccionadas()
        if sel:
            series = []
            for capa, f in sel[:40]:
                g = f.geometry()
                if g is None or g.isEmpty():
                    continue
                pts = serie_de_geometria(g)
                if len(pts) < 2:
                    continue
                # ¿la geometría tiene Z real?
                if all(abs(z) < 1e-9 for _, z in pts):
                    self._msg(f"'{capa.name()}' fid {f.id()} has no Z values; "
                              "the terrain profile is shown instead.", 1)
                    pts = []
                terreno = []
                if self.dem_layer is not None:
                    for s, x, y in traza_de_geometria(g, 5.0):
                        z = st.cota_dem(self.dem_layer, x, y)
                        if z is not None:
                            terreno.append((s, z))
                if not pts and terreno:
                    pts = list(terreno)
                    terreno = []
                if len(pts) < 2:
                    continue
                series.append({"etiqueta": f"{capa.name()} [fid {f.id()}]",
                               "puntos": pts, "terreno": terreno,
                               # traza en planta: al deslizar por el perfil se
                               # marca con un círculo rojo dónde estás
                               "traza": traza_de_geometria(g, 2.0)})
            if series:
                if len(sel) > 40:
                    self._msg(f"{len(sel)} features selected; only the first 40 "
                              "profiles are drawn.", 1)
                MultiProfileDialog(
                    f"View Longitudinal Profile — {len(series)} selected feature(s)",
                    series, self, iface=self.iface).exec()
                return
            self._msg("The selected features have no usable geometry for a "
                      "longitudinal profile.", 1)
            return
        d = self._diseno_actual()
        if d is None:
            self._generar_diseno()
            d = self._diseno_actual()
            if d is None:
                return
        terreno = []
        if self.dem_layer is not None:
            for s, x, y in d.dens[::5]:
                z = st.cota_dem(self.dem_layer, x, y)
                if z is not None:
                    terreno.append((s, z))
        ProfileDialog(d.nombre, d.perfil, terreno, self).exec()

    def _ver_informe(self):
        from .report_dialog import ReportDialog, informe_canal
        d = self._diseno_actual()
        if d is None:
            self._generar_diseno()
            d = self._diseno_actual()
            if d is None:
                return
        ReportDialog(f"Channel '{d.nombre}' Report", informe_canal(d), self).exec()

    def _ver_resumen(self):
        from .report_dialog import ReportDialog, informe_resumen
        if not self.diseno:
            self._generar_diseno()
            if not self.diseno:
                return
        dlg = SummaryOptionsDialog(self)
        if not dlg.exec():
            return
        if dlg.chk_fmt.isChecked():
            from .report_formatter_dialog import ReportFormatterDialog
            ReportFormatterDialog(self.diseno, self.proyecto.settings, self).exec()
            return
        gl = self._geom_limite()
        area_ha = gl.area() / 10000.0 if gl else 0.0
        ltot = sum(d.L_valle for d in self.diseno.values())
        dd = st.densidad_drenaje(ltot, area_ha)
        ReportDialog("Design Summary Report",
                     informe_resumen(self.diseno, self.proyecto.settings, area_ha,
                                     dd, rosgen=dlg.chk_rosgen.isChecked()),
                     self).exec()

    # ---------- surface & analysis ----------
    def _dibujar_superficie(self):
        from ..core import ridges
        if not self.diseno:
            self._generar_diseno()
            if not self.diseno:
                return
        gl = self._geom_limite()
        if gl is None:
            self._msg("No design boundary.", 1)
            return
        dlg = DrawSurfaceDialog(self.proyecto.settings, self)
        if not dlg.exec():
            return
        self.proyecto.settings.lineas_por_canal = int(dlg.cb_lineas.currentText())
        # ventana de triangulación/curvas, como en el original
        contornear = dlg.chk_contour.isChecked()
        if contornear:
            dlg2 = TriangulateContourDialog(self.proyecto.settings, self)
            if not dlg2.exec():
                return
            dlg2.aplicar()
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._generar_diseno()          # re-write banks with chosen line count
            crs = QgsProject.instance().crs().authid()
            sub = ridges.generar_subcuencas(self.diseno, gl, self.lm, crs)
            n_cr, crestas3d, exc_cr = ridges.generar_crestas(
                self.diseno, sub, gl, self.proyecto.settings, self.dem_layer,
                self.lm)
            n_sc, n_vg, avisos_l = ridges.generar_subcrestas(
                self.diseno, gl, self.proyecto.settings, self.lm,
                dem=self.dem_layer, crestas=crestas3d)
            # --- pase topológico: las crestas de ladera mueren sobre la
            # divisoria, y del encuentro de dos nace una cresta de orden
            # superior con su valle entre medias
            from ..core import topology, divides, builder as _b
            res_top = topology.revisar(self.lm, self.proyecto.settings,
                                       log=lambda m: self._msg(m.strip(), 0))
            # --- divisorias: recorte contra el corredor del cauce y cota
            # DERIVADA de las cabeceras de ladera que llegan a ellas
            divides.ajustar_divisorias(
                self.lm, self.diseno, self.proyecto.settings,
                dem=self.dem_layer, g_lim=gl,
                log=lambda m: self._msg(m.strip(), 0))
            # --- hidráulica escalonada: cada vaguada aporta en su confluencia
            _b.recalcular_por_aportes(self.diseno, self.lm,
                                      self.proyecto.settings,
                                      log=lambda m: self._msg(m.strip(), 0))
            self._msg(f"Design lines: {n_cr} ridges, {n_sc} sub-ridges, "
                      f"{n_vg} swales, {len(sub)} sub-watersheds.", 0)
            if exc_cr > 0.5:
                self._msg(
                    f"A ridgeline sits {exc_cr:.1f} m above the elevation its "
                    f"valley-wall slope target allows. The design lever for "
                    f"this is to move the ridgeline in plan towards the "
                    f"opposite valley, or to lower the slope target.", 1)
            for a in avisos_l:
                self._msg(a, 1)
            if contornear:
                self._interpolar_y_contornear(gl)
            self.rb_surface.setChecked(True)   # switch to surface editing mode
        except Exception as e:
            self._msg(f"Draw Design Surface error: {e}", 2)
        finally:
            QApplication.restoreOverrideCursor()

    def _recontornear(self):
        gl = self._geom_limite()
        if gl is None:
            self._msg("No design boundary.", 1)
            return
        dlg = TriangulateContourDialog(self.proyecto.settings, self)
        if not dlg.exec():
            return
        dlg.aplicar()
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._interpolar_y_contornear(gl)
        except Exception as e:
            self._msg(f"Contouring error: {e}", 2)
        finally:
            QApplication.restoreOverrideCursor()

    def _interpolar_y_contornear(self, gl):
        from ..core import surface
        for lyr in list(QgsProject.instance().mapLayers().values()):
            if lyr.name() == "GRD_DesignSurface":
                QgsProject.instance().removeMapLayer(lyr.id())
        s = self.proyecto.settings
        capa, ruta = surface.interpolar_superficie(
            self.lm, gl, self.dem_layer, self.diseno, s,
            celda=getattr(s, "resolucion_dem", None) or None,
            suavizado=int(getattr(s, "naturalidad", 0) or 0),
            radio_suavizado=int(getattr(s, "radio_suavizado", 1) or 1),
            recortar=bool(getattr(s, "recortar_superficie", True)))
        self.ruta_superficie = ruta
        self.lm.anadir_raster_a_grupo(capa, "03 Output")
        n = 0
        if bool(getattr(s, "dibujar_curvas", True)):
            n = surface.generar_contornos(
                ruta, self.lm, s,
                intervalo=s.intervalo_curvas,
                indice=s.intervalo_curvas_maestras,
                long_min=float(getattr(s, "long_min_curva", 0.0) or 0.0),
                bezier=bool(getattr(s, "bezier_curvas", True)),
                factor_bezier=int(getattr(s, "factor_bezier", 5) or 5))
        self._msg(f"Design surface interpolated ({getattr(s,'resolucion_dem',1):g} m "
                  f"cell, smoothing {getattr(s,'naturalidad',0)}); "
                  f"{n} contours drawn.", 3)
        self.iface.mapCanvas().refreshAllLayers()

    def _capa_comparacion(self):
        ruta = self.proyecto.ruta_dem_comparacion
        if ruta and os.path.exists(ruta):
            for lyr in QgsProject.instance().mapLayers().values():
                if isinstance(lyr, QgsRasterLayer) and lyr.source() == ruta:
                    return lyr
            lyr = QgsRasterLayer(ruta, os.path.basename(ruta))
            if lyr.isValid():
                self.lm.anadir_raster_a_grupo(lyr, "01 Inputs")
                return lyr
        return self.dem_layer

    def _corte_relleno(self):
        from ..core import surface
        gl = self._geom_limite()
        comp = self._capa_comparacion()
        if gl is None or comp is None:
            self._msg("Missing boundary or comparison surface (or DEM).", 1)
            return
        if not getattr(self, "ruta_superficie", None):
            self._msg("Draw the design surface first (Output tab).", 1)
            return
        capa_d = QgsRasterLayer(self.ruta_superficie, "d")
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            cf = surface.corte_relleno(capa_d, comp, gl, self.proyecto.settings, self.lm)
            self._ultimo_cf = cf
            for lyr in list(QgsProject.instance().mapLayers().values()):
                if lyr.name() == "GRD_CutFill (m)":
                    QgsProject.instance().removeMapLayer(lyr.id())
            surface.raster_diferencia(self.ruta_superficie, comp, self.lm, gl)
        except Exception as e:
            self._msg(f"Cut/Fill error: {e}", 2)
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._informe_volumen(cf)
        color = "#7CFC00" if cf["ok"] else "#ff6666"
        self.lb_o_cut.setText(f"{cf['corte_m3']:,.0f}")
        self.lb_o_fill.setText(f"{cf['relleno_m3']:,.0f}")
        self.lb_o_cf.setText(f"{cf['pct']:,.1f}")
        self.lb_o_cf.setStyleSheet(
            f"QLabel{{background:{color};padding:2px;border:1px solid #888;}}")
        s = self.proyecto.settings
        self._msg(f"Cut/Fill = {cf['pct']:,.1f} % "
                  f"(allowed {s.var_min_corte_relleno_pct:g}-"
                  f"{s.var_max_corte_relleno_pct:g} %). "
                  + ("Within range." if cf["ok"] else
                     "OUT of range: edit ridges or elevations and regenerate."),
                  3 if cf["ok"] else 1)

    def _informe_volumen(self, cf):
        """'Calculate Design Volume': cifras de corte y relleno dentro del
        límite GeoFluv + ráster GRD_CutFill con las zonas."""
        from .report_dialog import ReportDialog
        s = self.proyecto.settings
        neto = cf["corte_ajustado_m3"] - cf["relleno_ajustado_m3"]
        area = cf["bb"] and None
        ln = [
            "Design Volume  (design surface − original surface, inside the "
            "Design Boundary only)",
            "=" * 78, "",
            f"  CUT   (excavation, design below original) : "
            f"{cf['corte_m3']:>16,.0f} m³",
            f"  FILL  (embankment, design above original) : "
            f"{cf['relleno_m3']:>16,.0f} m³",
            f"  NET   (cut − fill)                        : "
            f"{cf['corte_m3'] - cf['relleno_m3']:>16,.0f} m³",
            "",
            f"  Swell factor {s.factor_esponjamiento:g} → adjusted cut  : "
            f"{cf['corte_ajustado_m3']:>16,.0f} m³",
            f"  Shrink factor {s.factor_compactacion:g} → adjusted fill: "
            f"{cf['relleno_ajustado_m3']:>16,.0f} m³",
            f"  Adjusted net                              : {neto:>16,.0f} m³  "
            + ("(surplus to haul off site)" if neto > 0 else "(borrow required)"),
            "",
            f"  Cut / Fill ratio: {cf['pct']:,.1f} %   (allowed "
            f"{s.var_min_corte_relleno_pct:g}–{s.var_max_corte_relleno_pct:g} %) → "
            + ("WITHIN range" if cf["ok"] else "OUT of range"),
            "",
            "  Cell size used: %.2f x %.2f m" % (cf["dx"], cf["dy"]),
            "  Raster 'GRD_CutFill (m)' added to 04 Analysis: negative = cut, "
            "positive = fill (clipped to the boundary).",
        ]
        ReportDialog("Calculate Design Volume", "\n".join(ln), self).exec()

    def _centroides(self):
        """Cut & Fill Centroids + haul plan (Mass Haul)."""
        from ..core import surface
        from .report_dialog import ReportDialog
        from qgis.PyQt.QtWidgets import QInputDialog
        if not getattr(self, "_ultimo_cf", None):
            self._corte_relleno()
            if not getattr(self, "_ultimo_cf", None):
                return
        vol_min, ok = QInputDialog.getDouble(
            self, "Cut & Fill Centroid Locator",
            "Minimum Region Volume (m³)\n(match it to your earthmoving equipment):",
            100.0, 0.0, 1e9, 1)
        if not ok:
            return
        regiones, plan = surface.centroides(self._ultimo_cf, vol_min, self.lm)
        txt = surface.informe_centroides(regiones, plan, self._ultimo_cf,
                                         self.proyecto.settings)
        ReportDialog("Cut & Fill Centroid Report", txt, self).exec()
        self.iface.mapCanvas().refreshAllLayers()

    def _auto_perfil(self):
        from .auto_profile_dialog import AutoPerfilDialog, aplicar_auto_perfil
        capa = self.iface.activeLayer()
        if not isinstance(capa, QgsVectorLayer) or capa.selectedFeatureCount() == 0:
            self._msg("Activate a design line layer and select the features "
                      "to edit first.", 1)
            return
        dlg = AutoPerfilDialog(self)
        if not dlg.exec():
            return
        n = aplicar_auto_perfil(capa, dlg.sp_cab.value(), dlg.sp_pie.value(),
                                dlg.sp_convexo.value() if dlg.chk_convexo.isChecked() else 0.0)
        self._msg(f"{n} profiles updated. Run 'Draw Design Contours' to "
                  "rebuild the surface.", 3)

    def _edit_profile(self):
        """Edit Longitudinal Profile: interactive editor of the selected 3D
        polyline (double click to adjust, Blend % controls the transition)."""
        from .edit_profile_dialog import EditProfileDialog
        capa = self.iface.activeLayer()
        if not isinstance(capa, QgsVectorLayer) or capa.selectedFeatureCount() != 1:
            self._msg("Select exactly ONE 3D line feature on the active layer "
                      "(e.g. GRD_Ridges, GRD_SubRidges, GRD_Channels).", 1)
            return
        feat = capa.selectedFeatures()[0]
        g = feat.geometry()
        try:
            verts = [(v.x(), v.y(), v.z() if v.z() == v.z() else 0.0)
                     for v in g.vertices()]
        except Exception:
            verts = []
        if len(verts) < 2:
            self._msg("The selected feature has no 3D vertices.", 1)
            return
        dlg = EditProfileDialog(f"{capa.name()} fid {feat.id()}", verts, self)
        if dlg.exec():
            dlg.aplicar_a_capa(capa, feat.id())
            self._msg("Profile applied. Run 'Draw Design Contours' to rebuild "
                      "the surface.", 3)

    def _viewer_3d(self, superficie):
        capas = "GRD_DesignSurface (raster)" if superficie else "GRD_Contours"
        QMessageBox.information(
            self, "3D Viewer",
            f"QGIS includes a native 3D viewer.\n\n"
            f"1. Menu View > 3D Map Views > New 3D Map View.\n"
            f"2. In the 3D configuration set Terrain = GRD_DesignSurface "
            f"(DEM type: raster layer).\n"
            f"3. Make {capas} visible to inspect the design"
            + (" surface shaded in 3D." if superficie else " contours in 3D.")
            + "\n\nVertical exaggeration and camera controls are in the 3D "
              "panel toolbar.")

    def _check_ridgeline(self):
        """Check Ridgeline Slope: flags ridge/sub-ridge segments steeper than
        'Maximum straight-line slopes'."""
        from .feature_list_dialog import FeatureListDialog
        s_max = self.proyecto.settings.pendiente_max_pct
        total_seg, malos = 0, []
        for nombre_capa in ("GRD_Ridges", "GRD_SubRidges", "GRD_Swales"):
            capa = self.lm.obtener_capa(nombre_capa, crear=False)
            if capa is None:
                continue
            for f in capa.getFeatures():
                g = f.geometry()
                try:
                    verts = list(g.vertices())
                except Exception:
                    continue
                peor, s_media, largo = 0.0, 0.0, 0.0
                for a, b in zip(verts[:-1], verts[1:]):
                    dx = ((b.x() - a.x()) ** 2 + (b.y() - a.y()) ** 2) ** 0.5
                    if dx < 0.5:
                        continue
                    total_seg += 1
                    largo += dx
                    s = abs(b.z() - a.z()) / dx * 100.0
                    peor = max(peor, s)
                if largo > 0 and len(verts) >= 2:
                    s_media = abs(verts[-1].z() - verts[0].z()) / largo * 100.0
                if peor > s_max:
                    malos.append({
                        "valores": [nombre_capa, f.id(), round(peor, 1),
                                    round(s_media, 1), round(largo, 1)],
                        "capa": capa, "fid": f.id()})
        cabecera = (f"Maximum straight-line slope allowed: {s_max:g} %  ·  "
                    f"segments checked: {total_seg}  ·  "
                    f"lines exceeding the maximum: {len(malos)}")
        if not malos:
            cabecera += "\nAll ridgeline slopes are within the allowed maximum."
        FeatureListDialog(
            "Check Ridgeline Slope", cabecera,
            ["layer", "fid", "worst slope (%)", "mean slope (%)", "length (m)"],
            malos, self.iface, self).exec()

    def _revisar_diseno(self):
        """'Check Design': lanza de una vez todas las comprobaciones que el
        original reparte por su interfaz y por su Error Log, y las presenta en
        una tabla enlazada a las entidades."""
        from ..core import checks
        from .check_dialog import CheckDialog
        from qgis.PyQt.QtWidgets import QApplication
        if not self.diseno:
            self._msg("Generate the design first (Output > Preview or "
                      "Draw Design Surface).", 1)
            return
        gl = self._geom_limite()
        # densidad de drenaje del conjunto, la misma que muestran las pestañas
        dd_global = None
        capa_v = self._capa_valles()
        if gl is not None and capa_v is not None:
            ltot = 0.0
            for c in self.proyecto.canales:
                if c.fid_fondo_valle is None:
                    continue
                f = capa_v.getFeature(c.fid_fondo_valle)
                if f.isValid():
                    ltot += st.longitud_dentro(f.geometry(), gl)
            dd_global = st.densidad_drenaje(ltot, gl.area() / 10000.0)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            t0 = time.time()
            hallazgos = checks.revisar(
                self.lm, self.proyecto.settings, proyecto=self.proyecto,
                disenos=self.diseno, g_lim=gl, dem=self.dem_layer,
                ruta_superficie=getattr(self, "ruta_superficie", None),
                resultado_cf=getattr(self, "_ultimo_cf", None),
                dd_global=dd_global,
                log=lambda m: self._msg(m.strip(), 0))
            dt = time.time() - t0
        except Exception as e:
            self._msg(f"Check Design error: {e}", 2)
            return
        finally:
            QApplication.restoreOverrideCursor()
        n_e, n_w, n_i = checks.resumen(hallazgos)
        self._msg(f"Design check finished in {dt:.1f} s: {n_e} error(s), "
                  f"{n_w} warning(s), {n_i} note(s).",
                  2 if n_e else (1 if n_w else 3))
        if not hallazgos:
            self._msg("No problems found in the design.", 3)
            return
        CheckDialog(hallazgos, self.iface, self).exec()

    def _save_tin(self):
        if not getattr(self, "ruta_superficie", None):
            self._msg("No design surface yet (Output > Draw Design Surface).", 1)
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Save Design Surface", "", "GeoTIFF (*.tif)")
        if not ruta:
            return
        if not ruta.endswith(".tif"):
            ruta += ".tif"
        shutil.copyfile(self.ruta_superficie, ruta)
        self._msg(f"Design surface saved to {ruta}", 3)

    # ---------- channels ----------
    def _refrescar_canales(self):
        self.cb_canal.blockSignals(True)
        self.cb_canal.clear()
        for c in self.proyecto.canales:
            self.cb_canal.addItem(c.nombre)
        self.cb_canal.blockSignals(False)
        self._datos_canal_actual()
        # un botón de ajustes por canal en la pestaña de optimización
        if getattr(self, "tab_ia", None) is not None:
            try:
                self.tab_ia.refrescar_canales()
            except Exception:
                pass

    def _add_tributario(self):
        capa = self._capa_valles()
        self._herramienta_identificar(capa, self._tributario_elegido)

    def _tributario_elegido(self, feat):
        gl = self._geom_limite()
        capa = self._capa_valles()
        if gl is None or capa is None:
            return
        geoms = []
        for c in self.proyecto.canales:
            if c.fid_fondo_valle is not None:
                f = capa.getFeature(c.fid_fondo_valle)
                if f.isValid():
                    geoms.append(f.geometry())
        ok, msg, padre_idx, extremo = st.validar_tributario(
            feat.geometry(), gl, geoms, self.proyecto.settings.max_dist_conexion_canales,
            self.proyecto.settings.max_dist_cresta_cabecera)
        if not ok:
            self._msg(msg, 2)
            return
        n = len(self.proyecto.canales)
        c = ChannelSettings(nombre=f"channel_{n}")
        c.fid_fondo_valle = feat.id()
        prev = self.proyecto.canales[-1]
        c.coef_escorrentia = prev.coef_escorrentia
        c.vel_max_agua = prev.vel_max_agua
        self.proyecto.canales.append(c)
        self.iface.mapCanvas().unsetMapTool(self._map_tool)
        self._refrescar_canales()
        self.cb_canal.setCurrentText(c.nombre)
        self._recalcular_dd()
        self._msg(f"{msg} Channel '{c.nombre}' added (final R/L name is assigned "
                  "when the design is generated).", 3)

    def _del_canal(self):
        nombre = self.cb_canal.currentText()
        if not nombre or not self.proyecto.canales:
            return
        if nombre == self.proyecto.canales[0].nombre:
            self._msg("The main valley bottom channel cannot be deleted.", 1)
            return
        capa = self._capa_valles()
        geoms = {}
        if capa is not None:
            for c in self.proyecto.canales:
                if c.fid_fondo_valle is not None:
                    f = capa.getFeature(c.fid_fondo_valle)
                    if f.isValid():
                        geoms[c.nombre] = f.geometry()

        def padre_de(c):
            idx = self.proyecto.canales.index(c)
            g = geoms.get(c.nombre)
            if g is None or idx == 0:
                return None
            pts = g.asPolyline() if not g.isMultipart() else g.asMultiPolyline()[0]
            mejor, dist = None, float("inf")
            for prev in self.proyecto.canales[:idx]:
                gp = geoms.get(prev.nombre)
                if gp is None:
                    continue
                for extremo in (pts[0], pts[-1]):
                    d = gp.distance(QgsGeometry.fromPointXY(extremo))
                    if d < dist:
                        dist, mejor = d, prev
            return mejor

        a_borrar = {nombre}
        cambio = True
        while cambio:            # transitive closure of tributaries
            cambio = False
            for c in self.proyecto.canales[1:]:
                if c.nombre in a_borrar:
                    continue
                p = padre_de(c)
                if p is not None and p.nombre in a_borrar:
                    a_borrar.add(c.nombre)
                    cambio = True
        n_trib = len(a_borrar) - 1
        self.proyecto.canales = [c for c in self.proyecto.canales
                                 if c.nombre not in a_borrar]
        self._refrescar_canales()
        self._recalcular_dd()
        self.diseno = {}
        self._msg(f"Channel '{nombre}' deleted"
                  + (f" along with {n_trib} tributary(ies)." if n_trib else ".")
                  + " Regenerate the design.", 3)
        self._actualizar_estado_botones()

    def _ren_canal(self):
        c = self._canal_actual()
        if c is None:
            return
        dlg = ChangeNameDialog(c.nombre, self)
        if dlg.exec() and dlg.ed.text():
            c.nombre = dlg.ed.text()
            if c is self.proyecto.canal_principal():
                self.proyecto.nombre_canal_principal = c.nombre
            if not dlg.chk.isChecked():
                self._msg("Note: tributary names always follow the hydrologic "
                          "R/L convention when the design regenerates.", 0)
            self._refrescar_canales()
            self.cb_canal.setCurrentText(c.nombre)

    def _cfg_canal(self):
        from .channel_dialog import ChannelSettingsDialog
        c = self._canal_actual()
        if c is None:
            self._msg("No channel selected.", 1)
            return
        es_principal = (c is self.proyecto.canal_principal())
        # DEM elevations at head/mouth for the Pick buttons
        z_cab = z_boca = None
        capa = self._capa_valles()
        if capa is not None and c.fid_fondo_valle is not None and self.dem_layer:
            f = capa.getFeature(c.fid_fondo_valle)
            if f.isValid():
                g = f.geometry()
                pts = g.asPolyline() if not g.isMultipart() else g.asMultiPolyline()[0]
                pts = st.orientar_aguas_abajo(pts, self.dem_layer)
                z_cab = st.cota_dem(self.dem_layer, pts[0].x(), pts[0].y())
                z_boca = st.cota_dem(self.dem_layer, pts[-1].x(), pts[-1].y())
        dlg = ChannelSettingsDialog(c, es_principal, self,
                                    z_cab_dem=z_cab, z_boca_dem=z_boca)
        if dlg.exec():
            dlg.aplicar()
            self._datos_canal_actual()
            self._msg(f"Channel '{c.nombre}' settings updated.", 3)

    # ---------- sequential enabling ----------
    def _actualizar_estado_botones(self):
        hay_limite = self.proyecto.fid_limite is not None
        hay_principal = bool(self.proyecto.canales) and \
            self.proyecto.canales[0].fid_fondo_valle is not None
        hay_diseno = bool(self.diseno)
        self.btn_canal.setEnabled(hay_limite)
        self.btn_surface.setEnabled(hay_principal)
        if self.rb_inputs.isChecked():
            self.tabs.setTabEnabled(1, hay_principal)      # Channels
            self.tabs.setTabEnabled(2, hay_principal)      # Output
        self.btn_prev.setEnabled(hay_principal)
        self.btn_draw.setEnabled(hay_principal)
        self.btn_releer.setEnabled(hay_principal)
        for b in (self.btn_perfil, self.btn_informe, self.btn_rep, self.btn_cf):
            b.setEnabled(hay_diseno or hay_principal)
