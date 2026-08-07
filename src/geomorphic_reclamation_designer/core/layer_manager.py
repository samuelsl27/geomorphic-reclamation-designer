# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Gestión del árbol de capas del proyecto GeoFluvQ.

Estructura de grupos creada en el panel de capas de QGIS:

GeoFluv <nombre_proyecto>
├── 01 Entradas
│   ├── GF_Boundary           (polígono)
│   ├── GF_ValleyBottoms          (línea 2D dibujada por el usuario)
│   └── (DEM de elevaciones — capa ráster del usuario, se referencia)
├── 02 Diseño
│   ├── GF_Channels         (LineStringZ, uno por canal, con atributos)
│   ├── GF_ChannelBanks          (LineStringZ: bankfull y flood-prone)
│   ├── Secciones                (PointZ por estación con propiedades hidráulicas)
│   ├── GF_Ridges      (LineStringZ)
│   ├── Subcrestas               (LineStringZ)
│   └── GF_Swales    (LineStringZ)
├── 03 Salida
│   ├── GF_DesignSurface     (ráster interpolado)
│   ├── GF_Contours          (línea)
│   └── Subcuencas               (polígono)
└── 04 Análisis
    ├── Corte-Relleno            (ráster diferencia)
    └── GF_Centroids           (punto)

Todas las capas vectoriales de diseño son capas 'memory' que se pueden
exportar/guardar en GPKG desde el propio panel del plugin. El usuario puede
editar las geometrías (p. ej. mover un fondo de valle) y regenerar el diseño.
"""

from qgis.core import (
    QgsProject, QgsVectorLayer, QgsField, QgsWkbTypes, QgsCoordinateReferenceSystem,
)
from .compat import CAMPO_STR, CAMPO_DOUBLE, CAMPO_INT, CAMPO_BOOL

GRUPO_RAIZ = "Geomorphic Reclamation"
SUBGRUPOS = ["01 Inputs", "02 Design", "03 Output", "04 Analysis"]

# Definición de capas: nombre -> (tipo geometría, subgrupo, campos)
# Field names follow the GeoFluv report nomenclature (Report Formatter)
CAMPOS_CANAL = [
    ("name", CAMPO_STR), ("receiving", CAMPO_STR), ("side", CAMPO_STR),
    ("valley_length", CAMPO_DOUBLE), ("channel_length", CAMPO_DOUBLE),
    ("sinuosity", CAMPO_DOUBLE), ("watershed_area_ha", CAMPO_DOUBLE),
    ("addl_area_ha", CAMPO_DOUBLE), ("drainage_density", CAMPO_DOUBLE),
    ("head_elev", CAMPO_DOUBLE), ("base_elev", CAMPO_DOUBLE),
    ("head_slope", CAMPO_DOUBLE), ("base_slope", CAMPO_DOUBLE),
    ("bankfull_qpk", CAMPO_DOUBLE), ("flood_prone_qpk", CAMPO_DOUBLE),
    ("runoff_coeff", CAMPO_DOUBLE), ("max_velocity", CAMPO_DOUBLE),
    ("wd_steep", CAMPO_DOUBLE), ("wd_mild", CAMPO_DOUBLE),
    ("status", CAMPO_STR),
]

CAMPOS_SECCION = [
    ("channel", CAMPO_STR), ("station", CAMPO_DOUBLE),
    ("elev", CAMPO_DOUBLE), ("slope_pct", CAMPO_DOUBLE),
    ("type", CAMPO_STR),  # 'A' | 'valley'
    ("bankfull_width", CAMPO_DOUBLE), ("bankfull_depth", CAMPO_DOUBLE),
    ("bankfull_area", CAMPO_DOUBLE), ("flood_prone_width", CAMPO_DOUBLE),
    ("flood_prone_depth", CAMPO_DOUBLE), ("flood_prone_area", CAMPO_DOUBLE),
    ("bottom_width", CAMPO_DOUBLE),
    ("tractive_force_bkf", CAMPO_DOUBLE), ("tractive_force_fp", CAMPO_DOUBLE),
    ("bankfull_qpk", CAMPO_DOUBLE), ("flood_prone_qpk", CAMPO_DOUBLE),
    # --- extended hydraulics ---
    ("watershed_area_ha", CAMPO_DOUBLE),   # accumulated drainage area at station
    ("wetted_perimeter", CAMPO_DOUBLE),    # bankfull wetted perimeter
    ("hydraulic_radius", CAMPO_DOUBLE),    # bankfull hydraulic radius
    ("entrenchment_ratio", CAMPO_DOUBLE),  # W_fp / W_bkf (Rosgen)
    ("tau_critical", CAMPO_DOUBLE),        # Shields critical shear (N/m2)
    ("tau_ratio", CAMPO_DOUBLE),           # τ_bkf / τ_crit
    ("tau_status", CAMPO_STR),             # 'ok' | 'high'
    ("manning_depth", CAMPO_DOUBLE),       # Manning normal depth (m)
    ("manning_vel", CAMPO_DOUBLE),         # Manning velocity (m/s)
    ("froude", CAMPO_DOUBLE),
    ("manning_check", CAMPO_STR),          # 'ok' | 'v_high' | 'v_low'
    ("meander_length", CAMPO_DOUBLE),      # λ (m)
    ("belt_width", CAMPO_DOUBLE),          # stable min belt 2.5·W (m)
    ("radius_curvature", CAMPO_DOUBLE),    # Rc (m)
]

# Map tip HTML for GF_XSections: with QGIS 'Show Map Tips' enabled, hovering
# over a cross-section shows its hydraulic data sheet.
MAPTIP_SECCION = """
<div style="font-family:sans-serif; font-size:9pt; background:#ffffff;">
<b>[% "channel" %] — sta. [% format_number("station",1) %] m</b> (type [% "type" %])<br/>
Elev [% format_number("elev",2) %] m · slope [% format_number("slope_pct",2) %] %
 · watershed [% format_number("watershed_area_ha",2) %] ha<br/>
<b>Qpk</b> bankfull [% format_number("bankfull_qpk",3) %] m³/s ·
 flood-prone [% format_number("flood_prone_qpk",3) %] m³/s<br/>
<b>Bankfull</b>: W [% format_number("bankfull_width",2) %] ·
 d [% format_number("bankfull_depth",2) %] ·
 A [% format_number("bankfull_area",2) %] m² ·
 bottom [% format_number("bottom_width",2) %] m ·
 R [% format_number("hydraulic_radius",2) %] m<br/>
<b>Flood-prone</b>: W [% format_number("flood_prone_width",2) %] ·
 d [% format_number("flood_prone_depth",2) %] m ·
 entrench. [% format_number("entrenchment_ratio",2) %]<br/>
<b>τ</b> [% format_number("tractive_force_bkf",1) %] /
 τcrit [% format_number("tau_critical",1) %] N/m² →
 <b>[% "tau_status" %]</b> ·
 Manning v [% format_number("manning_vel",2) %] m/s ·
 F [% format_number("froude",2) %] ([% "manning_check" %])
</div>
"""

DEF_CAPAS = {
    "GF_Boundary":        ("Polygon",      "01 Inputs", [("name", CAMPO_STR), ("area_ha", CAMPO_DOUBLE)]),
    "GF_ValleyBottoms":       ("LineString",   "01 Inputs", [("name", CAMPO_STR), ("is_main", CAMPO_BOOL)]),
    "GF_Channels":      ("LineStringZ",  "02 Design",   CAMPOS_CANAL),
    "GF_ChannelBanks":       ("LineStringZ",  "02 Design",   [("channel", CAMPO_STR), ("type", CAMPO_STR)]),
    "GF_XSections":             ("PointZ",       "02 Design",   CAMPOS_SECCION),
    "GF_Ridges":   ("LineStringZ",  "02 Design",   [("name", CAMPO_STR)]),
    "GF_SubRidges":            ("LineStringZ",  "02 Design",   [("channel", CAMPO_STR), ("index", CAMPO_INT)]),
    "GF_Swales": ("LineStringZ",  "02 Design",   [("channel", CAMPO_STR), ("index", CAMPO_INT)]),
    "GF_Contours":       ("LineStringZ",  "03 Output",   [("elev", CAMPO_DOUBLE), ("is_index", CAMPO_BOOL)]),
    "GF_SubWatershed":            ("Polygon",      "03 Output",   [("channel", CAMPO_STR), ("area_ha", CAMPO_DOUBLE), ("drainage_density", CAMPO_DOUBLE)]),
    "GF_Centroids":        ("PointZ",       "04 Analysis", [("region", CAMPO_INT), ("type", CAMPO_STR), ("volume_m3", CAMPO_DOUBLE)]),
    "GF_HaulRegions":      ("Polygon",      "04 Analysis", [("region", CAMPO_INT), ("type", CAMPO_STR), ("volume_m3", CAMPO_DOUBLE), ("area_m2", CAMPO_DOUBLE), ("mean_depth_m", CAMPO_DOUBLE), ("centroid_x", CAMPO_DOUBLE), ("centroid_y", CAMPO_DOUBLE)]),
    "GF_HaulRoutes":       ("LineString",   "04 Analysis", [("from_region", CAMPO_INT), ("to_region", CAMPO_INT), ("volume_m3", CAMPO_DOUBLE), ("distance_m", CAMPO_DOUBLE), ("vol_x_dist", CAMPO_DOUBLE)]),
    "GF_Vanes":            ("LineStringZ",  "02 Design",   [("channel", CAMPO_STR), ("index", CAMPO_INT), ("station", CAMPO_DOUBLE), ("bank", CAMPO_STR)]),
    "GF_Vegetation":       ("PointZ",       "03 Output",   [("type", CAMPO_STR), ("height_m", CAMPO_DOUBLE)]),
}


def carpeta_unica_proyecto(nombre_proyecto="Design"):
    """Carpeta única para las capas: junto al .qgz guardado, con el nombre del
    proyecto QGIS + fecha y hora (así cada generación queda separada)."""
    import os
    from datetime import datetime
    ruta_qgz = QgsProject.instance().fileName()
    if ruta_qgz:
        base = os.path.dirname(ruta_qgz)
        nombre = os.path.splitext(os.path.basename(ruta_qgz))[0]
    else:
        base = os.path.expanduser("~")
        nombre = nombre_proyecto or "Design"
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(base, f"{nombre}_{sello}")
    os.makedirs(destino, exist_ok=True)
    return destino


class LayerManager:
    def __init__(self, iface, nombre_proyecto="proyecto"):
        self.iface = iface
        self.nombre_proyecto = nombre_proyecto
        # almacenamiento: 'memory' (capas virtuales) o una carpeta de destino
        # en la que cada capa se guarda como GeoPackage
        self.modo_almacenamiento = "memory"
        self.carpeta = ""

    def configurar_almacenamiento(self, modo="memory", carpeta=""):
        self.modo_almacenamiento = modo or "memory"
        self.carpeta = carpeta or ""
        return self.carpeta

    # ---------- grupos ----------
    def grupo_raiz(self, crear=True):
        root = QgsProject.instance().layerTreeRoot()
        nombre = f"{GRUPO_RAIZ} {self.nombre_proyecto}"
        g = root.findGroup(nombre)
        if g is None and crear:
            g = root.insertGroup(0, nombre)
        return g

    def subgrupo(self, nombre_sub, crear=True):
        g = self.grupo_raiz(crear)
        if g is None:
            return None
        sg = g.findGroup(nombre_sub)
        if sg is None and crear:
            # mantener el orden definido en SUBGRUPOS
            idx = SUBGRUPOS.index(nombre_sub) if nombre_sub in SUBGRUPOS else -1
            sg = g.insertGroup(idx if idx >= 0 else -1, nombre_sub)
        return sg

    def crear_arbol(self):
        for s in SUBGRUPOS:
            self.subgrupo(s)

    # ---------- capas ----------
    def _crs(self):
        crs = QgsProject.instance().crs()
        if not crs.isValid():
            crs = QgsCoordinateReferenceSystem("EPSG:25830")
        return crs

    @staticmethod
    def _tipo_compatible(lyr, geom_def):
        """True si el tipo de geometría de la capa existente sirve para lo que
        la versión actual va a escribir (sobre todo: si necesita Z, que la
        tenga). Al actualizar de versión pueden quedar capas antiguas 2D en el
        proyecto —p. ej. GF_Contours— y ahí se perderían las cotas."""
        try:
            necesita_z = geom_def.endswith("Z")
            tiene_z = QgsWkbTypes.hasZ(lyr.wkbType())
            if necesita_z and not tiene_z:
                return False
            base_def = geom_def[:-1] if geom_def.endswith("Z") else geom_def
            esperado = {"Point": 0, "LineString": 1, "Polygon": 2}.get(base_def)
            return esperado is None or lyr.geometryType() == esperado
        except Exception:
            return True

    def obtener_capa(self, nombre, crear=True):
        """Devuelve la capa vectorial del proyecto por nombre; la crea si no existe."""
        for lyr in QgsProject.instance().mapLayers().values():
            if lyr.name() == nombre and isinstance(lyr, QgsVectorLayer):
                if nombre in DEF_CAPAS and crear and \
                        not self._tipo_compatible(lyr, DEF_CAPAS[nombre][0]):
                    # capa de una versión anterior con geometría incompatible
                    # (típicamente sin Z): se sustituye por una nueva
                    QgsProject.instance().removeMapLayer(lyr.id())
                    break
                return lyr
        if not crear or nombre not in DEF_CAPAS:
            return None
        geom, sub, campos = DEF_CAPAS[nombre]
        uri = f"{geom}?crs={self._crs().authid()}"
        lyr = QgsVectorLayer(uri, nombre, "memory")
        lyr.dataProvider().addAttributes([QgsField(n, t) for n, t in campos])
        lyr.updateFields()
        if self.modo_almacenamiento != "memory" and self.carpeta:
            en_disco = self._guardar_en_disco(lyr, nombre)
            if en_disco is not None:
                lyr = en_disco
        QgsProject.instance().addMapLayer(lyr, False)
        sg = self.subgrupo(sub)
        sg.addLayer(lyr)
        self._aplicar_estilo(lyr, nombre)
        if nombre == "GF_XSections":
            try:
                lyr.setMapTipTemplate(MAPTIP_SECCION)
            except Exception:
                pass
        return lyr

    def _guardar_en_disco(self, lyr_mem, nombre):
        """Escribe la capa vacía como GeoPackage en la carpeta configurada y
        devuelve la capa cargada desde el fichero (editable y persistente)."""
        import os
        try:
            from qgis.core import QgsVectorFileWriter, QgsCoordinateTransformContext
            os.makedirs(self.carpeta, exist_ok=True)
            ruta = os.path.join(self.carpeta, f"{nombre}.gpkg")
            opciones = QgsVectorFileWriter.SaveVectorOptions()
            opciones.driverName = "GPKG"
            opciones.layerName = nombre
            opciones.fileEncoding = "UTF-8"
            try:
                opciones.actionOnExistingFile = \
                    QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile
            except Exception:
                pass
            try:
                res = QgsVectorFileWriter.writeAsVectorFormatV3(
                    lyr_mem, ruta, QgsCoordinateTransformContext(), opciones)
            except Exception:
                res = QgsVectorFileWriter.writeAsVectorFormatV2(
                    lyr_mem, ruta, QgsCoordinateTransformContext(), opciones)
            err = res[0] if isinstance(res, (tuple, list)) else res
            if err not in (0, QgsVectorFileWriter.NoError):
                return None
            nueva = QgsVectorLayer(f"{ruta}|layername={nombre}", nombre, "ogr")
            return nueva if nueva.isValid() else None
        except Exception:
            return None

    def resaltar_fuerza_tractiva(self, activar=True):
        """Estilo de la capa Secciones por estabilidad tractiva (equivalente a
        'Highlight Tractive Force Zones'): verde τ≤0.8·τcrit, ámbar 0.8–1,
        rojo τ>τcrit. Con activar=False restaura el símbolo simple."""
        lyr = self.obtener_capa("GF_XSections", crear=False)
        if lyr is None:
            return None
        try:
            from qgis.core import (QgsMarkerSymbol, QgsRuleBasedRenderer,
                                   QgsSingleSymbolRenderer)
            if not activar:
                sym = QgsMarkerSymbol.createSimple(
                    {"name": "circle", "color": "#ff8800", "size": "1.2"})
                lyr.setRenderer(QgsSingleSymbolRenderer(sym))
                lyr.triggerRepaint()
                return lyr
            reglas = [
                ('"tau_ratio" > 1', "#d40000", "τ > τcrit (erosion risk)", "2.4"),
                ('"tau_ratio" > 0.8 AND "tau_ratio" <= 1', "#ff9900",
                 "τ 80–100 % of τcrit", "1.8"),
                ('"tau_ratio" <= 0.8 AND "tau_critical" > 0', "#2e9e46",
                 "τ ≤ 80 % τcrit", "1.2"),
                ('"tau_critical" = 0 OR "tau_critical" IS NULL', "#888888",
                 "no D50 (τcrit unknown)", "1.2"),
            ]
            raiz = QgsRuleBasedRenderer.Rule(None)
            for expr, color, etiqueta, tam in reglas:
                sym = QgsMarkerSymbol.createSimple(
                    {"name": "circle", "color": color, "size": tam})
                regla = QgsRuleBasedRenderer.Rule(sym, 0, 0, expr, etiqueta)
                raiz.appendChild(regla)
            lyr.setRenderer(QgsRuleBasedRenderer(raiz))
            lyr.triggerRepaint()
            return lyr
        except Exception:
            return None

    def limpiar_capa(self, nombre):
        lyr = self.obtener_capa(nombre, crear=False)
        if lyr:
            lyr.dataProvider().truncate()
            lyr.triggerRepaint()
        return lyr

    def anadir_raster_a_grupo(self, raster_layer, subgrupo):
        QgsProject.instance().addMapLayer(raster_layer, False)
        self.subgrupo(subgrupo).addLayer(raster_layer)

    # ---------- estilos básicos ----------
    def _aplicar_estilo(self, lyr, nombre):
        try:
            from qgis.core import QgsLineSymbol, QgsFillSymbol, QgsMarkerSymbol
            sym = None
            if nombre == "GF_Boundary":
                sym = QgsFillSymbol.createSimple({"color": "0,0,0,0", "outline_color": "#0055aa",
                                                  "outline_width": "0.6"})
            elif nombre == "GF_ValleyBottoms":
                sym = QgsLineSymbol.createSimple({"line_color": "#00aa66", "line_width": "0.5",
                                                  "line_style": "dash"})
            elif nombre == "GF_Channels":
                sym = QgsLineSymbol.createSimple({"line_color": "#0077ff", "line_width": "0.7"})
            elif nombre == "GF_ChannelBanks":
                sym = QgsLineSymbol.createSimple({"line_color": "#00c8ff", "line_width": "0.3"})
            elif nombre == "GF_Ridges":
                sym = QgsLineSymbol.createSimple({"line_color": "#cc0000", "line_width": "0.6"})
            elif nombre == "GF_SubRidges":
                sym = QgsLineSymbol.createSimple({"line_color": "#e6b800", "line_width": "0.4"})
            elif nombre == "GF_Swales":
                sym = QgsLineSymbol.createSimple({"line_color": "#3366cc", "line_width": "0.3",
                                                  "line_style": "dot"})
            elif nombre == "GF_XSections":
                sym = QgsMarkerSymbol.createSimple({"name": "circle", "color": "#ff8800", "size": "1.2"})
            elif nombre == "GF_Vanes":
                sym = QgsLineSymbol.createSimple({"line_color": "#8000c0",
                                                  "line_width": "0.8"})
            elif nombre == "GF_Vegetation":
                sym = QgsMarkerSymbol.createSimple({"name": "triangle",
                                                    "color": "#1d7a1d",
                                                    "size": "1.6"})
            elif nombre == "GF_Centroids":
                sym = QgsMarkerSymbol.createSimple({"name": "cross2", "color": "#000000", "size": "3"})
            elif nombre == "GF_HaulRoutes":
                sym = QgsLineSymbol.createSimple({"line_color": "#000000",
                                                  "line_width": "0.5"})
            if nombre == "GF_HaulRegions":
                self._estilo_haul_regions(lyr)
                return
            if sym is not None:
                lyr.renderer().setSymbol(sym)
                lyr.triggerRepaint()
        except Exception:
            pass

    def _estilo_haul_regions(self, lyr):
        """Corte en rojo, relleno en azul (Mass Haul areas)."""
        try:
            from qgis.core import (QgsFillSymbol, QgsRuleBasedRenderer)
            raiz = QgsRuleBasedRenderer.Rule(None)
            for expr, color, etiqueta in (
                    ("\"type\" = 'cut'", "178,24,43,110", "cut area"),
                    ("\"type\" = 'fill'", "33,102,172,110", "fill area")):
                sym = QgsFillSymbol.createSimple(
                    {"color": color, "outline_color": color.rsplit(",", 1)[0] + ",255",
                     "outline_width": "0.35"})
                raiz.appendChild(QgsRuleBasedRenderer.Rule(sym, 0, 0, expr, etiqueta))
            lyr.setRenderer(QgsRuleBasedRenderer(raiz))
            lyr.setOpacity(0.75)
            lyr.triggerRepaint()
        except Exception:
            pass
