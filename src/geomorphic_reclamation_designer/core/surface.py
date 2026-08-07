# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""GF_DesignSurface y análisis de tierras.

- SUPERFICIE DE DISEÑO: interpolación TIN (QgsTinInterpolator, qgis.analysis)
  usando como líneas de rotura los ejes y bordes 3D de los canales, las
  crestas principales, las subcrestas y las vaguadas, más puntos del límite
  con la cota del terreno original (para que el diseño empalme con el
  entorno). Si el usuario edita cualquiera de esas capas, basta volver a
  ejecutar la interpolación ('Dibujar curvas de nivel GeoFluv') para
  regenerar la superficie: mismo flujo que el DWG tab del original.
- CURVAS DE NIVEL: gdal:contour sobre el ráster de diseño, con marcado de
  curvas maestras.
- CORTE/RELLENO: diferencia diseño − superficie de comparación, integrada
  SOLO dentro del límite GeoFluv (máscara por barrido de líneas), con
  factores de esponjamiento/compactación y semáforo frente a la varianza
  admisible.
- CENTROIDES: regiones conexas de corte y de relleno mayores que un volumen
  mínimo, con centroides ponderados por volumen e informe de movimiento de
  tierras optimizado (asignación voraz corte→relleno por distancia).
"""

import math
import os
import tempfile

from qgis.core import (
    QgsProject, QgsRasterLayer, QgsFeature, QgsGeometry, QgsPoint, QgsPointXY,
    QgsRectangle,
)

from . import setup_tools as st
from .compat import tipo_geom, attrs


# ------------------------------------------------------------------ TIN
def _capas_diseno(lm):
    nombres = ["GF_Channels", "GF_ChannelBanks", "GF_Ridges",
               "GF_SubRidges", "GF_Swales"]
    return [lm.obtener_capa(n, crear=False) for n in nombres]


def _puntos_limite(g_lim, dem, lm, disenos, glob, paso=15.0):
    """Capa temporal de puntos 3D sobre el límite con la cota del terreno
    (o, sin DEM, la cota de ladera de diseño)."""
    from qgis.core import QgsVectorLayer
    from .ridges import _geoms_ejes, _z_ladera
    crs = QgsProject.instance().crs().authid()
    lyr = QgsVectorLayer(f"PointZ?crs={crs}", "tmp_limite_z", "memory")
    anillo = g_lim.asPolygon()[0] if not g_lim.isMultipart() \
        else g_lim.asMultiPolygon()[0][0]
    geoms = _geoms_ejes(disenos) if disenos else {}
    s_max = glob.pendiente_max_pct / 100.0
    feats = []
    for a, b in zip(anillo[:-1], anillo[1:]):
        d = math.hypot(b.x() - a.x(), b.y() - a.y())
        n = max(1, int(d // paso))
        for k in range(n):
            t = k / n
            x = a.x() + t * (b.x() - a.x())
            y = a.y() + t * (b.y() - a.y())
            z = st.cota_dem(dem, x, y) if dem is not None else None
            if z is None and geoms:
                z = _z_ladera((x, y), disenos, geoms, s_max)
            if z is None:
                continue
            f = QgsFeature()
            f.setGeometry(QgsGeometry(QgsPoint(x, y, z)))
            feats.append(f)
    lyr.dataProvider().addFeatures(feats)
    lyr.updateExtents()
    return lyr


def _densificar_capa(capa, paso):
    """Copia en memoria de una capa de líneas 3D con vértices cada 'paso' m
    (interpolando la Z linealmente). Si algo falla devuelve la capa original."""
    try:
        from qgis.core import QgsVectorLayer, QgsLineString
        crs = capa.crs().authid() or QgsProject.instance().crs().authid()
        nueva = QgsVectorLayer(f"LineStringZ?crs={crs}",
                               capa.name() + "_dens", "memory")
        feats = []
        for f in capa.getFeatures():
            g = f.geometry()
            partes = []
            for v in ([g] if not g.isMultipart() else g.asGeometryCollection()):
                pts = [(p.x(), p.y(), p.z()) for p in v.vertices()]
                if len(pts) < 2:
                    continue
                out = [pts[0]]
                for a, b in zip(pts[:-1], pts[1:]):
                    d = math.hypot(b[0] - a[0], b[1] - a[1])
                    n = max(1, int(d // paso))
                    for k in range(1, n + 1):
                        t = k / n
                        out.append((a[0] + t * (b[0] - a[0]),
                                    a[1] + t * (b[1] - a[1]),
                                    a[2] + t * (b[2] - a[2])))
                partes.append(out)
            for out in partes:
                nf = QgsFeature()
                nf.setGeometry(QgsGeometry(QgsLineString(
                    [QgsPoint(x, y, z) for x, y, z in out])))
                feats.append(nf)
        if not feats:
            return capa
        nueva.dataProvider().addFeatures(feats)
        nueva.updateExtents()
        return nueva
    except Exception:
        return capa


def _capa_mascara(g_lim):
    """Capa de polígono en memoria con el límite GeoFluv (para recortes)."""
    from qgis.core import QgsVectorLayer
    crs = QgsProject.instance().crs().authid()
    lyr = QgsVectorLayer(f"Polygon?crs={crs}", "tmp_limite", "memory")
    f = QgsFeature()
    f.setGeometry(g_lim)
    lyr.dataProvider().addFeatures([f])
    lyr.updateExtents()
    return lyr


def mascara_corredor(ruta, disenos, margen=1.5):
    """Celdas del ráster que caen dentro del corredor de los cauces.

    El filtro de naturalidad NO debe tocarlas. El canal bankfull mide en este
    proyecto entre 0.4 y 2.8 m de ancho, del orden del tamaño de celda: unas
    pocas pasadas de media móvil lo emborronan, la incisión se pierde y las
    curvas de nivel acaban cruzándolo a una cota que no es la suya. Medido
    sobre el caso real, esa discrepancia llegaba a **2.37 m**, mientras que en
    la salida del GeoFluv original las curvas cruzan el cauce con una
    diferencia mediana de **0.001 m**.
    """
    try:
        import numpy as np
        from osgeo import gdal
    except Exception:
        return None
    if not disenos:
        return None
    ds = gdal.Open(ruta)
    if ds is None:
        return None
    gt = ds.GetGeoTransform()
    ny, nx = ds.RasterYSize, ds.RasterXSize
    ds = None
    if not gt or gt[1] == 0 or gt[5] == 0:
        return None
    m = np.zeros((ny, nx), dtype=bool)
    iterable = disenos.values() if isinstance(disenos, dict) else disenos
    for d in iterable:
        pts = getattr(d, "puntos", None)
        if not pts:
            continue
        secs = [(e["estacion"], e.get("ancho_flood", 0.0))
                for e in (getattr(d, "secciones", []) or [])]
        for (x, y, _z, s) in pts:
            semi = 0.0
            if secs:
                k = min(range(len(secs)), key=lambda i: abs(secs[i][0] - s))
                semi = secs[k][1] / 2.0
            r = semi + margen
            c0 = int((x - r - gt[0]) / gt[1]); c1 = int((x + r - gt[0]) / gt[1])
            f0 = int((y + r - gt[3]) / gt[5]); f1 = int((y - r - gt[3]) / gt[5])
            for fy in range(max(0, min(f0, f1)), min(ny - 1, max(f0, f1)) + 1):
                for cx in range(max(0, min(c0, c1)),
                                min(nx - 1, max(c0, c1)) + 1):
                    px = gt[0] + (cx + 0.5) * gt[1]
                    py = gt[3] + (fy + 0.5) * gt[5]
                    if (px - x) ** 2 + (py - y) ** 2 <= r * r:
                        m[fy, cx] = True
    return m


CELDAS_POR_CAUCE = 3.0     # celdas a lo ancho del canal bankfull, mínimo
CELDAS_MAX = 12_000_000    # tope del ráster, para no ahogar la máquina


def _celda_para_el_cauce(celda, bb, disenos, minimo=0.15):
    """Afina el tamaño de celda hasta que el cauce quepa en la malla.

    Una malla no puede representar un canal más estrecho que su celda. En el
    proyecto real el bankfull mide entre 0.4 y 2.8 m frente a una celda de
    1 m: la incisión se pierde y las curvas de nivel cruzan el cauce a una cota
    que no es la suya. Medido: con celda de 1 m la discrepancia entre la cota
    de la curva y la del eje en los cruces tenía mediana 0.078 m y máximo
    1.63 m; **con celda de 0.40 m baja a 0.009 m de mediana y 0.18 m de
    máximo**, que es el nivel de la salida del GeoFluv original (0.001 y
    0.101 m).

    Se pide `CELDAS_POR_CAUCE` celdas a lo ancho del canal más estrecho, con un
    tope de celdas totales para que un proyecto grande no genere un ráster
    inmanejable.
    """
    if not disenos:
        return celda
    anchos = []
    iterable = disenos.values() if isinstance(disenos, dict) else disenos
    for d in iterable:
        for e in (getattr(d, "secciones", []) or []):
            a = e.get("ancho_bankfull") or 0.0
            if a > 0:
                anchos.append(a)
    if not anchos:
        return celda
    # la MEDIANA, no el mínimo: afinar hasta el canal más estrecho del
    # proyecto multiplicaba por siete el número de celdas sin mejorar el
    # resultado (medido: celda 0.166 m -> mediana 0.010 m en 10.6 s, frente a
    # celda 0.40 m -> 0.009 m en 3.0 s).
    anchos.sort()
    tipico = anchos[len(anchos) // 2]
    deseada = max(minimo, tipico / CELDAS_POR_CAUCE)
    if deseada >= celda:
        return celda
    # ¿cabe el ráster?
    n = (bb.width() / deseada) * (bb.height() / deseada)
    if n > CELDAS_MAX:
        deseada = math.sqrt(bb.width() * bb.height() / CELDAS_MAX)
        if deseada >= celda:
            return celda
    return deseada


def suavizar_raster(ruta, pasadas=0, radio=1, ruta_salida=None,
                    mascara_fija=None):
    """Suaviza el ráster con una media móvil (filtro paso bajo) respetando los
    NoData: es el 'grado de naturalidad' del terreno.

    Un TIN construido con líneas de rotura da laderas facetadas y crestas en
    arista viva; en la naturaleza las divisorias y los interfluvios están
    redondeados por la difusión de ladera (creep). Aplicar n pasadas de una
    media móvil de radio r es exactamente un esquema explícito de la ecuación
    de difusión ∂z/∂t = K·∇²z, que es el modelo físico estándar de evolución de
    laderas: por eso el resultado se parece a un relieve maduro y no deforma la
    posición de canales ni divisorias (solo redondea las aristas).
    """
    if pasadas <= 0:
        return ruta
    try:
        import numpy as np
        from osgeo import gdal
    except Exception:
        return ruta
    ds = gdal.Open(ruta)
    if ds is None:
        return ruta
    banda = ds.GetRasterBand(1)
    nodata = banda.GetNoDataValue()
    a = banda.ReadAsArray().astype("float64")
    valido = np.isfinite(a)
    if nodata is not None:
        valido &= (a != nodata)
    a = np.where(valido, a, 0.0)
    original = a.copy()
    fija = None
    if mascara_fija is not None:
        try:
            fija = np.asarray(mascara_fija, dtype=bool)
            if fija.shape != a.shape:
                fija = None
        except Exception:
            fija = None
    w = valido.astype("float64")
    r = max(1, int(radio))

    def media(m):
        acum = np.zeros_like(m)
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                acum += np.roll(np.roll(m, dy, axis=0), dx, axis=1)
        return acum

    for _ in range(int(pasadas)):
        sa = media(a)
        sw = media(w)
        con = sw > 0
        a = np.where(con, sa / np.where(con, sw, 1.0), a)
        # el corredor del cauce se restaura tras cada pasada: su sección la
        # define el cálculo hidráulico y no puede emborronarse
        if fija is not None:
            a = np.where(fija, original, a)
        a = np.where(valido, a, 0.0)
    salida = ruta_salida or os.path.join(tempfile.gettempdir(),
                                         "geofluv_superficie_suave.tif")
    drv = gdal.GetDriverByName("GTiff")
    nd = nodata if nodata is not None else -9999.0
    out = drv.Create(salida, ds.RasterXSize, ds.RasterYSize, 1, gdal.GDT_Float32)
    out.SetGeoTransform(ds.GetGeoTransform())
    out.SetProjection(ds.GetProjection())
    ob = out.GetRasterBand(1)
    ob.SetNoDataValue(nd)
    ob.WriteArray(np.where(valido, a, nd).astype("float32"))
    ob.FlushCache()
    out = None
    ds = None
    return salida


def recortar_al_limite(ruta, g_lim, ruta_salida=None):
    """Recorta el ráster al polígono límite: fuera del perímetro GeoFluv no
    debe existir superficie de diseño (queda NoData)."""
    from qgis import processing
    salida = ruta_salida or os.path.join(tempfile.gettempdir(),
                                         "geofluv_superficie_rec.tif")
    try:
        processing.run("gdal:cliprasterbymasklayer", {
            "INPUT": ruta, "MASK": _capa_mascara(g_lim),
            "SOURCE_CRS": None, "TARGET_CRS": None,
            "NODATA": -9999.0, "ALPHA_BAND": False, "CROP_TO_CUTLINE": True,
            "KEEP_RESOLUTION": True, "SET_RESOLUTION": False,
            "DATA_TYPE": 6, "OUTPUT": salida})
        return salida
    except Exception:
        return ruta


def interpolar_superficie(lm, g_lim, dem, disenos, glob, ruta_salida=None,
                          celda=None, suavizado=0, radio_suavizado=1,
                          recortar=True):
    """TIN → ráster GeoTIFF de la superficie de diseño. Devuelve (capa, ruta).

    celda: tamaño de píxel (m). suavizado: nº de pasadas del filtro de
    naturalidad. recortar: NoData fuera del límite GeoFluv."""
    from qgis.analysis import QgsTinInterpolator, QgsInterpolator, QgsGridFileWriter

    capas = [c for c in _capas_diseno(lm) if c is not None and c.featureCount() > 0]
    if not capas:
        raise RuntimeError("No hay líneas de diseño. Genera antes el diseño y las crestas.")

    def _enum(base, contenedor, nombre):
        """Enum compatible entre versiones: QgsInterpolator.ValueZ o
        QgsInterpolator.ValueSource.ValueZ, etc."""
        cont = getattr(base, contenedor, None)
        if cont is not None and hasattr(cont, nombre):
            return getattr(cont, nombre)
        return getattr(base, nombre)

    v_z = _enum(QgsInterpolator, "ValueSource", "ValueZ")
    t_lineas = _enum(QgsInterpolator, "SourceType", "SourceBreakLines")
    t_puntos = _enum(QgsInterpolator, "SourceType", "SourcePoints")

    # 'Minimize Flat Triangles': densificar las líneas de rotura reduce los
    # triángulos planos largos entre vértices lejanos (crestas y vaguadas con
    # pocos vértices), que son los que producen terrazas artificiales.
    if getattr(glob, "densificar_breaklines", False):
        paso = max(float(getattr(glob, "intervalo_breaklines", 5.0) or 5.0), 0.5)
        capas = [_densificar_capa(c, paso) for c in capas]

    datos = []
    for c in capas:
        ld = QgsInterpolator.LayerData()
        ld.source = c
        ld.valueSource = v_z
        ld.interpolationAttribute = -1
        ld.sourceType = t_lineas
        try:
            ld.transformContext = QgsProject.instance().transformContext()
        except Exception:
            pass
        datos.append(ld)
    # puntos del límite (empalme con el terreno)
    lim_pts = _puntos_limite(g_lim, dem, lm, disenos, glob)
    if lim_pts.featureCount() > 0:
        ld = QgsInterpolator.LayerData()
        ld.source = lim_pts
        ld.valueSource = v_z
        ld.interpolationAttribute = -1
        ld.sourceType = t_puntos
        try:
            ld.transformContext = QgsProject.instance().transformContext()
        except Exception:
            pass
        datos.append(ld)

    metodo = _enum(QgsTinInterpolator, "TinInterpolation", "Linear")
    interp = QgsTinInterpolator(datos, metodo)
    bb = g_lim.boundingBox()
    bb.grow(10.0)
    if celda is None:
        celda = max(0.5, min(5.0, math.sqrt(g_lim.area()) / 800.0))
    celda = _celda_para_el_cauce(celda, bb, disenos)
    cols = max(10, int(bb.width() / celda))
    filas = max(10, int(bb.height() / celda))
    ruta_tin = os.path.join(tempfile.gettempdir(), "geofluv_superficie_tin.tif")
    escritor = QgsGridFileWriter(interp, ruta_tin, bb, cols, filas)
    res = escritor.writeFile()
    if res != 0:
        raise RuntimeError(f"La interpolación TIN falló (código {res}).")

    ruta = ruta_tin
    if suavizado and suavizado > 0:
        ruta = suavizar_raster(ruta, pasadas=suavizado, radio=radio_suavizado,
                               mascara_fija=mascara_corredor(ruta, disenos))
    if recortar:
        ruta = recortar_al_limite(ruta, g_lim)
    if ruta_salida and ruta != ruta_salida:
        try:
            import shutil
            shutil.copyfile(ruta, ruta_salida)
            ruta = ruta_salida
        except Exception:
            pass
    capa = QgsRasterLayer(ruta, "GF_DesignSurface")
    if not capa.isValid():
        raise RuntimeError("No se pudo cargar el ráster de la superficie de diseño.")
    return capa, ruta


# ------------------------------------------------------------------ contornos
def _a_3d(g, z):
    """Convierte una geometría de línea 2D en LineStringZ / MultiLineStringZ
    con la cota z en todos los vértices (curvas de nivel 3D)."""
    from qgis.core import QgsLineString, QgsMultiLineString
    try:
        partes = []
        for v in ([g] if not g.isMultipart() else g.asGeometryCollection()):
            pts = [QgsPoint(p.x(), p.y(), z) for p in v.vertices()]
            if len(pts) >= 2:
                partes.append(QgsLineString(pts))
        if not partes:
            return g
        if len(partes) == 1:
            return QgsGeometry(partes[0])
        ml = QgsMultiLineString()
        for pa in partes:
            ml.addGeometry(pa)
        return QgsGeometry(ml)
    except Exception:
        return g


def generar_contornos(ruta_raster, lm, glob, intervalo=None, indice=None,
                      long_min=0.0, bezier=True, factor_bezier=5):
    """GF_Contours gdal:contour → capa 'GF_Contours' con maestras.

    intervalo / indice: intervalos de curva y de curva maestra (m).
    long_min: descarta curvas más cortas (limpia el ruido de curvas cerradas).
    bezier / factor_bezier: suavizado de las curvas (Chaikin, equivalente al
    'Bezier Smoothing Factor' del original)."""
    from qgis import processing
    intervalo = float(intervalo or glob.intervalo_curvas)
    indice = float(indice or glob.intervalo_curvas_maestras)
    res = processing.run("gdal:contour", {
        "INPUT": ruta_raster, "BAND": 1, "INTERVAL": intervalo,
        "FIELD_NAME": "ELEV", "OUTPUT": "TEMPORARY_OUTPUT"})
    from qgis.core import QgsVectorLayer
    src = res["OUTPUT"]
    vc = src if isinstance(src, QgsVectorLayer) else QgsVectorLayer(src, "tmp", "ogr")
    capa = lm.obtener_capa("GF_Contours")
    capa.dataProvider().truncate()
    im = max(indice, intervalo)
    # 'Bezier Smoothing Factor' 1-10 → iteraciones y desplazamiento de Chaikin
    iters = max(1, min(5, 1 + int(factor_bezier) // 3))
    offset = max(0.10, min(0.45, 0.15 + 0.03 * float(factor_bezier)))
    feats = []
    for f in vc.getFeatures():
        z = f["ELEV"]
        g = f.geometry()
        if long_min > 0 and g.length() < long_min:
            continue
        if bezier and factor_bezier > 0:
            try:
                gs = g.smooth(iters, offset)
                if gs is not None and not gs.isEmpty():
                    g = gs
            except Exception:
                pass
        # curvas 3D: la cota de la curva se lleva a la geometría (LineStringZ)
        g = _a_3d(g, float(z))
        nf = QgsFeature(capa.fields())
        nf.setGeometry(g)
        maestra = abs((z / im) - round(z / im)) < 1e-6
        nf.setAttributes(attrs(capa, [float(z), bool(maestra)]))
        feats.append(nf)
    capa.dataProvider().addFeatures(feats)
    capa.updateExtents()
    _estilo_curvas(capa)
    capa.triggerRepaint()
    return len(feats)


def _estilo_curvas(capa):
    try:
        from qgis.core import (QgsRuleBasedRenderer, QgsLineSymbol)
        raiz = QgsRuleBasedRenderer.Rule(None)
        r1 = QgsRuleBasedRenderer.Rule(
            QgsLineSymbol.createSimple({"line_color": "#cc2200", "line_width": "0.45"}),
            0, 0, '"is_index" = true', "index contours")
        r2 = QgsRuleBasedRenderer.Rule(
            QgsLineSymbol.createSimple({"line_color": "#00b0c8", "line_width": "0.18"}),
            0, 0, '"is_index" = false', "contours")
        raiz.appendChild(r1); raiz.appendChild(r2)
        capa.setRenderer(QgsRuleBasedRenderer(raiz))
    except Exception:
        pass


# ------------------------------------------------------------------ corte/relleno
def _leer_bloque(capa_r, bb, cols, filas):
    prov = capa_r.dataProvider()
    bloque = prov.block(1, bb, cols, filas)
    return bloque


def _mascara_scanline(g_lim, bb, cols, filas):
    """Para cada fila del ráster, lista de rangos de columnas dentro del límite."""
    rangos = []
    dy = bb.height() / filas
    dx = bb.width() / cols
    for r in range(filas):
        y = bb.yMaximum() - (r + 0.5) * dy
        linea = QgsGeometry.fromPolylineXY([QgsPointXY(bb.xMinimum() - 1, y),
                                            QgsPointXY(bb.xMaximum() + 1, y)])
        inter = linea.intersection(g_lim)
        fila = []
        if inter and not inter.isEmpty():
            if tipo_geom(inter) == 1:
                partes = inter.asMultiPolyline() if inter.isMultipart() \
                    else [inter.asPolyline()]
            else:
                # colección con posibles puntos de tangencia: solo las líneas
                try:
                    partes = [g.asPolyline() for g in inter.asGeometryCollection()
                              if tipo_geom(g) == 1]
                except Exception:
                    partes = []
            for p in partes:
                if len(p) < 2:
                    continue
                x0 = min(p[0].x(), p[-1].x()); x1 = max(p[0].x(), p[-1].x())
                c0 = max(0, int((x0 - bb.xMinimum()) / dx))
                c1 = min(cols - 1, int((x1 - bb.xMinimum()) / dx))
                if c1 >= c0:
                    fila.append((c0, c1))
        rangos.append(fila)
    return rangos, dx, dy


def corte_relleno(capa_diseno, capa_comp, g_lim, glob, lm, cols_max=600):
    """Diferencia diseño − comparación dentro del límite.
    Devuelve dict con volúmenes, %, y la malla de diferencias para centroides."""
    bb = g_lim.boundingBox()
    celda = max(bb.width(), bb.height()) / cols_max
    cols = max(10, int(bb.width() / celda))
    filas = max(10, int(bb.height() / celda))
    b_d = _leer_bloque(capa_diseno, bb, cols, filas)
    b_c = _leer_bloque(capa_comp, bb, cols, filas)
    rangos, dx, dy = _mascara_scanline(g_lim, bb, cols, filas)
    area_celda = dx * dy

    corte = relleno = 0.0
    malla = [[None] * cols for _ in range(filas)]
    for r in range(filas):
        for (c0, c1) in rangos[r]:
            for c in range(c0, c1 + 1):
                if b_d.isNoData(r, c) or b_c.isNoData(r, c):
                    continue
                dif = b_d.value(r, c) - b_c.value(r, c)   # + relleno, − corte
                malla[r][c] = dif
                if dif > 0:
                    relleno += dif * area_celda
                else:
                    corte += -dif * area_celda
    corte_aj = corte * glob.factor_esponjamiento
    relleno_aj = relleno / max(glob.factor_compactacion, 1e-9)
    pct = (corte_aj / relleno_aj * 100.0) if relleno_aj > 0 else float("inf")
    ok = glob.var_min_corte_relleno_pct <= pct <= glob.var_max_corte_relleno_pct
    return {
        "corte_m3": corte, "relleno_m3": relleno,
        "corte_ajustado_m3": corte_aj, "relleno_ajustado_m3": relleno_aj,
        "pct": pct, "ok": ok, "malla": malla, "bb": bb,
        "dx": dx, "dy": dy, "cols": cols, "filas": filas,
    }


def raster_diferencia(ruta_diseno, capa_comp, lm, g_lim=None):
    """Ráster diseño − comparación (corte/relleno) con la calculadora ráster.

    Se recorta al límite GeoFluv: fuera del perímetro no hay diseño y por
    tanto tampoco corte ni relleno."""
    from qgis.analysis import QgsRasterCalculator, QgsRasterCalculatorEntry
    capa_d = QgsRasterLayer(ruta_diseno, "d")
    e1 = QgsRasterCalculatorEntry(); e1.ref = "d@1"; e1.raster = capa_d; e1.bandNumber = 1
    e2 = QgsRasterCalculatorEntry(); e2.ref = "c@1"; e2.raster = capa_comp; e2.bandNumber = 1
    salida = os.path.join(tempfile.gettempdir(), "geofluv_corte_relleno.tif")
    try:
        calc = QgsRasterCalculator(
            '"d@1" - "c@1"', salida, "GTiff", capa_d.extent(), capa_d.crs(),
            capa_d.width(), capa_d.height(), [e1, e2],
            QgsProject.instance().transformContext())
    except TypeError:
        calc = QgsRasterCalculator('"d@1" - "c@1"', salida, "GTiff",
                                   capa_d.extent(), capa_d.width(),
                                   capa_d.height(), [e1, e2])
    if calc.processCalculation() != 0:
        return None
    if g_lim is not None:
        salida = recortar_al_limite(
            salida, g_lim,
            os.path.join(tempfile.gettempdir(), "geofluv_corte_relleno_rec.tif"))
    capa = QgsRasterLayer(salida, "GF_CutFill (m)")
    if capa.isValid():
        _estilo_cutfill(capa)
        lm.anadir_raster_a_grupo(capa, "04 Analysis")
        return capa
    return None


def _estilo_cutfill(capa):
    """Rampa divergente: rojo = corte (diseño por debajo), azul = relleno."""
    try:
        from qgis.core import (QgsColorRampShader, QgsRasterShader,
                               QgsSingleBandPseudoColorRenderer)
        est = capa.dataProvider().bandStatistics(1)
        m = max(abs(est.minimumValue), abs(est.maximumValue), 0.5)
        items = [
            QgsColorRampShader.ColorRampItem(-m, _c(178, 24, 43), f"cut {-m:.1f} m"),
            QgsColorRampShader.ColorRampItem(-0.25, _c(244, 165, 130), "cut 0.25 m"),
            QgsColorRampShader.ColorRampItem(0.0, _c(247, 247, 247), "balance"),
            QgsColorRampShader.ColorRampItem(0.25, _c(146, 197, 222), "fill 0.25 m"),
            QgsColorRampShader.ColorRampItem(m, _c(33, 102, 172), f"fill {m:.1f} m"),
        ]
        ramp = QgsColorRampShader()
        try:
            ramp.setColorRampType(QgsColorRampShader.Type.Interpolated)
        except Exception:
            ramp.setColorRampType(QgsColorRampShader.Interpolated)
        ramp.setColorRampItemList(items)
        sh = QgsRasterShader()
        sh.setRasterShaderFunction(ramp)
        capa.setRenderer(QgsSingleBandPseudoColorRenderer(
            capa.dataProvider(), 1, sh))
        capa.triggerRepaint()
    except Exception:
        pass


def _c(r, g, b):
    from qgis.PyQt.QtGui import QColor
    return QColor(r, g, b)


# ------------------------------------------------------------------ centroides
def _poligono_region(celdas, bb, dx, dy):
    """Polígono de una región de corte/relleno a partir de sus celdas.

    Las celdas de cada fila se agrupan en tramos contiguos (un rectángulo por
    tramo) antes de unir, para que la unión sea rápida aunque la región tenga
    decenas de miles de píxeles."""
    porfila = {}
    for r, c in celdas:
        porfila.setdefault(r, []).append(c)
    rects = []
    for r, cs in porfila.items():
        cs.sort()
        ini = prev = cs[0]
        for c in cs[1:] + [None]:
            if c is not None and c == prev + 1:
                prev = c
                continue
            x0 = bb.xMinimum() + ini * dx
            x1 = bb.xMinimum() + (prev + 1) * dx
            y1 = bb.yMaximum() - r * dy
            y0 = bb.yMaximum() - (r + 1) * dy
            rects.append(QgsGeometry.fromRect(QgsRectangle(x0, y0, x1, y1)))
            if c is None:
                break
            ini = prev = c
    if not rects:
        return None
    try:
        g = QgsGeometry.unaryUnion(rects)
    except Exception:
        g = rects[0]
        for r in rects[1:]:
            g = g.combine(r)
    if g is None or g.isEmpty():
        return None
    try:
        g = g.buffer(0.0, 1)
    except Exception:
        pass
    return g


def centroides(cf, vol_min, lm, dibujar_areas=True):
    """Regiones conexas de corte/relleno ≥ vol_min, centroides ponderados,
    POLÍGONOS de cada área y plan de acarreo optimizado (asignación voraz por
    distancia). Escribe GF_Centroids, GF_HaulRegions y GF_HaulRoutes."""
    malla, filas, cols = cf["malla"], cf["filas"], cf["cols"]
    bb, dx, dy = cf["bb"], cf["dx"], cf["dy"]
    area = dx * dy
    visit = [[False] * cols for _ in range(filas)]
    regiones = []
    for r0 in range(filas):
        for c0 in range(cols):
            if visit[r0][c0] or malla[r0][c0] is None or abs(malla[r0][c0]) < 1e-6:
                continue
            signo = 1 if malla[r0][c0] > 0 else -1
            pila = [(r0, c0)]
            visit[r0][c0] = True
            vol = sx = sy = 0.0
            celdas = []
            while pila:
                r, c = pila.pop()
                celdas.append((r, c))
                v = malla[r][c] * area
                w = abs(v)
                vol += v
                x = bb.xMinimum() + (c + 0.5) * dx
                y = bb.yMaximum() - (r + 0.5) * dy
                sx += x * w; sy += y * w
                for rr, cc in ((r+1,c),(r-1,c),(r,c+1),(r,c-1)):
                    if 0 <= rr < filas and 0 <= cc < cols and not visit[rr][cc] \
                       and malla[rr][cc] is not None \
                       and (1 if malla[rr][cc] > 0 else -1) == signo \
                       and abs(malla[rr][cc]) >= 1e-6:
                        visit[rr][cc] = True
                        pila.append((rr, cc))
            w_tot = abs(vol)
            if w_tot >= vol_min:
                regiones.append({"tipo": "fill" if signo > 0 else "cut",
                                 "volumen": w_tot,
                                 "x": sx / w_tot if w_tot else 0,
                                 "y": sy / w_tot if w_tot else 0,
                                 "area_m2": len(celdas) * area,
                                 "celdas": celdas})
    regiones.sort(key=lambda R: -R["volumen"])
    for i, R in enumerate(regiones):
        R["id"] = i + 1
        R["prof_media"] = (R["volumen"] / R["area_m2"]) if R["area_m2"] else 0.0

    # capa de puntos (centroides)
    capa = lm.obtener_capa("GF_Centroids")
    capa.dataProvider().truncate()
    feats = []
    for R in regiones:
        f = QgsFeature(capa.fields())
        f.setGeometry(QgsGeometry(QgsPoint(R["x"], R["y"], 0)))
        f.setAttributes(attrs(capa, [R["id"], R["tipo"], round(R["volumen"], 1)]))
        feats.append(f)
    capa.dataProvider().addFeatures(feats)
    capa.updateExtents(); capa.triggerRepaint()

    # --- capa de ÁREAS (polígonos) con toda la información ---
    if dibujar_areas:
        capa_a = lm.obtener_capa("GF_HaulRegions")
        if capa_a is not None:
            capa_a.dataProvider().truncate()
            fa = []
            for R in regiones:
                g = _poligono_region(R["celdas"], bb, dx, dy)
                if g is None:
                    continue
                f = QgsFeature(capa_a.fields())
                f.setGeometry(g)
                f.setAttributes(attrs(capa_a, [R["id"], R["tipo"], round(R["volumen"], 1),
                                 round(R["area_m2"], 1), round(R["prof_media"], 3),
                                 round(R["x"], 2), round(R["y"], 2)]))
                fa.append(f)
            capa_a.dataProvider().addFeatures(fa)
            capa_a.updateExtents(); capa_a.triggerRepaint()

    # plan de acarreo voraz: mover de cada corte al relleno más próximo
    cortes = [dict(R) for R in regiones if R["tipo"] == "cut"]
    rellenos = [dict(R) for R in regiones if R["tipo"] == "fill"]
    plan = []
    for cta in sorted(cortes, key=lambda R: -R["volumen"]):
        rem = cta["volumen"]
        while rem > 1.0 and rellenos:
            rellenos = [R for R in rellenos if R["volumen"] > 1.0]
            if not rellenos:
                break
            dest = min(rellenos, key=lambda R: math.hypot(R["x"] - cta["x"],
                                                          R["y"] - cta["y"]))
            mov = min(rem, dest["volumen"])
            plan.append({"de": cta["id"], "a": dest["id"], "volumen": mov,
                         "distancia": math.hypot(dest["x"] - cta["x"],
                                                 dest["y"] - cta["y"]),
                         "x0": cta["x"], "y0": cta["y"],
                         "x1": dest["x"], "y1": dest["y"]})
            rem -= mov
            dest["volumen"] -= mov

    # --- capa de RUTAS de acarreo ---
    capa_r = lm.obtener_capa("GF_HaulRoutes")
    if capa_r is not None:
        capa_r.dataProvider().truncate()
        fr = []
        for p in plan:
            f = QgsFeature(capa_r.fields())
            f.setGeometry(QgsGeometry.fromPolylineXY(
                [QgsPointXY(p["x0"], p["y0"]), QgsPointXY(p["x1"], p["y1"])]))
            f.setAttributes(attrs(capa_r, [p["de"], p["a"], round(p["volumen"], 1),
                             round(p["distancia"], 1),
                             round(p["volumen"] * p["distancia"], 1)]))
            fr.append(f)
        capa_r.dataProvider().addFeatures(fr)
        capa_r.updateExtents(); capa_r.triggerRepaint()

    for R in regiones:
        R.pop("celdas", None)
    return regiones, plan


def informe_centroides(regiones, plan, cf, glob):
    ln = ["Cut & Fill Centroid Report", "=" * 60]
    ln.append(f"Total cut:      {cf['corte_m3']:,.0f} m³  "
              f"(swelled: {cf['corte_ajustado_m3']:,.0f} m³)")
    ln.append(f"Total fill:     {cf['relleno_m3']:,.0f} m³  "
              f"(compacted: {cf['relleno_ajustado_m3']:,.0f} m³)")
    ln.append(f"Cut / Fill:     {cf['pct']:,.1f} %   "
              f"(allowed {glob.var_min_corte_relleno_pct:g}-"
              f"{glob.var_max_corte_relleno_pct:g} %) -> "
              + ("WITHIN range" if cf["ok"] else "OUT of range"))
    ln.append("")
    ln.append(f"{'region':>7s} {'type':>8s} {'volume (m³)':>14s} {'area (m²)':>12s} "
              f"{'mean d (m)':>11s} {'X':>12s} {'Y':>12s}")
    ln.append("-" * 82)
    for R in regiones:
        ln.append(f"{R['id']:>7d} {R['tipo']:>8s} {R['volumen']:>14,.0f} "
                  f"{R.get('area_m2', 0):>12,.0f} {R.get('prof_media', 0):>11,.2f} "
                  f"{R['x']:>12,.1f} {R['y']:>12,.1f}")
    ln.append("")
    ln.append("Areas drawn in layer 'GF_HaulRegions' (cut red / fill blue) and "
              "haul lines in 'GF_HaulRoutes'.")
    ln.append("")
    ln.append("Earth Movement Report (minimum-distance assignment):")
    ln.append(f"{'from':>5s} {'to':>5s} {'volume (m³)':>14s} {'dist. (m)':>10s}")
    ln.append("-" * 40)
    vd = 0.0
    for p in plan:
        ln.append(f"{p['de']:>5d} {p['a']:>5d} {p['volumen']:>14,.0f} "
                  f"{p['distancia']:>10,.0f}")
        vd += p["volumen"] * p["distancia"]
    ln.append("")
    ln.append(f"Total internal volume x distance: {vd:,.0f} m³·m")
    exceso = cf["corte_ajustado_m3"] - cf["relleno_ajustado_m3"]
    if abs(exceso) > 1:
        ln.append(("Excess material (to external stockpile): " if exceso > 0
                   else "Borrow material required: ") + f"{abs(exceso):,.0f} m³")
    return "\n".join(ln)
