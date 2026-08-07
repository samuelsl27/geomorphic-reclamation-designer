# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Herramientas de la fase Setup.

- Validación y aceptación del límite GeoFluv (polígono cerrado) y cálculo de área.
- Aceptación del canal principal (fondo de valle): debe cruzar/terminar en el
  límite en su punto más bajo (nivel de base local).
- Punto de transición entre tramo de valle (<4 %) y tramo empinado tipo A (>4 %):
  seleccionado por el usuario o determinado automáticamente a partir del DEM.
- Cálculo de densidad de drenaje (long. de valle / área) y comprobación frente
  al objetivo ± varianza.
- Muestreo de cotas en el DEM (cabecera, boca, perfil del terreno).
"""


from qgis.core import (
    QgsGeometry, QgsPointXY,
)

from .params import UMBRAL_PENDIENTE
from .compat import tipo_geom, formato_identify_valor


# ---------------- DEM ----------------

def cota_dem(dem_layer, x, y):
    """Cota del DEM en (x, y) o None."""
    if dem_layer is None:
        return None
    res = dem_layer.dataProvider().identify(QgsPointXY(x, y),
                                            formato_identify_valor())
    if not res.isValid():
        return None
    vals = res.results()
    if not vals:
        return None
    v = list(vals.values())[0]
    return float(v) if v is not None else None


def perfil_terreno(dem_layer, geom_linea, paso=5.0):
    """Muestrea el DEM a lo largo de una línea. Devuelve [(dist, x, y, z), ...]."""
    puntos = []
    if geom_linea is None or geom_linea.isEmpty():
        return puntos
    L = geom_linea.length()
    d = 0.0
    while d <= L + 1e-9:
        p = geom_linea.interpolate(min(d, L)).asPoint()
        z = cota_dem(dem_layer, p.x(), p.y())
        puntos.append((min(d, L), p.x(), p.y(), z))
        d += paso
    return puntos


# ---------------- Límite ----------------

def validar_limite(geom):
    """El límite debe ser un polígono cerrado válido. Devuelve (ok, area_ha, msg)."""
    if geom is None or geom.isEmpty():
        return False, 0.0, "Empty geometry."
    if tipo_geom(geom) != 2:  # polígono
        return False, 0.0, "The design boundary must be a closed polygon."
    if not geom.isGeosValid():
        geom = geom.makeValid()
        if not geom.isGeosValid():
            return False, 0.0, "The boundary polygon is not valid."
    area_ha = geom.area() / 10000.0
    return True, area_ha, "GF_Boundary aceptado."


# ---------------- Canal principal ----------------

def validar_canal_principal(geom_canal, geom_limite, tol=1.0):
    """El canal principal no puede ser cerrado y debe salir del límite (o acabar
    a menos de 'tol' del borde). Devuelve (ok, msg)."""
    if geom_canal is None or geom_canal.isEmpty():
        return False, "Empty geometry."
    if tipo_geom(geom_canal) != 1:
        return False, "The main channel must be a polyline."
    if geom_canal.isMultipart():
        partes = geom_canal.asMultiPolyline()
        if len(partes) != 1:
            return False, "The main channel polyline must have a single part."
        pts = partes[0]
    else:
        pts = geom_canal.asPolyline()
    if len(pts) < 2:
        return False, "The polyline needs at least 2 vertices."
    if pts[0] == pts[-1]:
        return False, "The main channel cannot be a closed polyline."
    borde = QgsGeometry.fromPolygonXY(geom_limite.asPolygon()) if not geom_limite.isMultipart() else geom_limite
    cruza = geom_canal.crosses(borde) or geom_canal.intersects(borde.constGet().boundary() and borde)
    # criterio práctico: uno de los extremos fuera o a < tol del contorno
    contorno = QgsGeometry.fromPolylineXY(
        geom_limite.asPolygon()[0] if not geom_limite.isMultipart() else geom_limite.asMultiPolygon()[0][0]
    )
    d0 = contorno.distance(QgsGeometry.fromPointXY(QgsPointXY(pts[0])))
    d1 = contorno.distance(QgsGeometry.fromPointXY(QgsPointXY(pts[-1])))
    dentro0 = borde.contains(QgsGeometry.fromPointXY(QgsPointXY(pts[0])))
    dentro1 = borde.contains(QgsGeometry.fromPointXY(QgsPointXY(pts[-1])))
    if not (cruza or d0 <= tol or d1 <= tol or (not dentro0) or (not dentro1)):
        return False, "The main channel must cross the design boundary at the base level."
    return True, "Canal principal aceptado."


def orientar_aguas_abajo(pts, dem_layer):
    """Devuelve la lista de puntos ordenada de cabecera (alta) a boca (baja)."""
    if dem_layer is None or len(pts) < 2:
        return pts
    z0 = cota_dem(dem_layer, pts[0].x(), pts[0].y())
    z1 = cota_dem(dem_layer, pts[-1].x(), pts[-1].y())
    if z0 is not None and z1 is not None and z0 < z1:
        return list(reversed(pts))
    return pts


def transicion_automatica(dem_layer, geom_canal, paso=5.0):
    """Busca automáticamente el punto donde la pendiente del fondo de valle
    supera el 4 % hacia aguas arriba (transición A <-> valle).

    Recorre el perfil del terreno desde la boca hacia la cabecera y devuelve
    (x, y, dist_desde_cabecera) del primer punto donde la pendiente media
    (ventana de 3 tramos) supera UMBRAL_PENDIENTE. Si nunca la supera,
    devuelve None (todo el canal es de valle)."""
    perfil = perfil_terreno(dem_layer, geom_canal, paso)
    perfil = [p for p in perfil if p[3] is not None]
    if len(perfil) < 4:
        return None
    # asumimos perfil ordenado cabecera->boca si z decrece; si no, invertir
    if perfil[0][3] < perfil[-1][3]:
        perfil = list(reversed(perfil))
        L = perfil[0][0]
        perfil = [(L - d, x, y, z) for (d, x, y, z) in perfil]
    # desde la boca hacia arriba
    for i in range(len(perfil) - 2, 1, -1):
        d1, x1, y1, z1 = perfil[i - 1]
        d2, x2, y2, z2 = perfil[i + 1]
        if d2 == d1:
            continue
        s = abs((z2 - z1) / (d2 - d1))
        if s > UMBRAL_PENDIENTE:
            d, x, y, z = perfil[i]
            return (x, y, d)
    return None


# ---------------- Densidad de drenaje ----------------

def longitud_dentro(geom_linea, geom_limite):
    inter = geom_linea.intersection(geom_limite)
    return inter.length() if inter and not inter.isEmpty() else 0.0


def densidad_drenaje(long_valles_m, area_ha):
    """Densidad de drenaje en m/ha."""
    if area_ha <= 0:
        return 0.0
    return long_valles_m / area_ha


def evaluar_dd(dd, objetivo, varianza_pct):
    """Devuelve (estado, minimo, maximo) donde estado ∈ {'ok','baja','alta'}."""
    dmin = objetivo * (1 - varianza_pct / 100.0)
    dmax = objetivo * (1 + varianza_pct / 100.0)
    if dd < dmin:
        return "baja", dmin, dmax
    if dd > dmax:
        return "alta", dmin, dmax
    return "ok", dmin, dmax


# ---------------- Validación de tributarios ----------------

def validar_tributario(geom_trib, geom_limite, geoms_existentes, max_dist_conexion,
                       max_dist_cabecera=None):
    """Reglas del método para añadir un canal:
    - un extremo cerca (< max_dist) de otro fondo de valle ya añadido,
    - el otro extremo (cabecera) a menos de 'max_dist_cabecera' del límite
      GeoFluv (el ajuste 'distancia máx. de cresta a cabecera'): si queda más
      lejos se ACEPTA con aviso, como el pop-up del método original,
    - no cruza el límite, ni otros fondos de valle, ni a sí mismo, ni es cerrado.
    Devuelve (ok, msg, padre_idx, extremo_confluencia)."""
    if geom_trib is None or geom_trib.isEmpty() or tipo_geom(geom_trib) != 1:
        return False, "The tributary must be a polyline.", None, None
    pts = geom_trib.asPolyline() if not geom_trib.isMultipart() else geom_trib.asMultiPolyline()[0]
    if len(pts) < 2 or pts[0] == pts[-1]:
        return False, "The polyline cannot be closed.", None, None
    if not geom_trib.isSimple():
        return False, "The polyline cannot cross itself.", None, None

    contorno = QgsGeometry.fromPolylineXY(
        geom_limite.asPolygon()[0] if not geom_limite.isMultipart() else geom_limite.asMultiPolygon()[0][0]
    )
    if geom_trib.crosses(geom_limite) and not geom_limite.contains(geom_trib):
        return False, "The tributary cannot cross the design boundary.", None, None

    g0 = QgsGeometry.fromPointXY(QgsPointXY(pts[0]))
    g1 = QgsGeometry.fromPointXY(QgsPointXY(pts[-1]))

    padre_idx, extremo_conf = None, None
    for i, g in enumerate(geoms_existentes):
        if geom_trib.crosses(g):
            return False, "The tributary cannot cross another valley bottom.", None, None
        if g.distance(g0) <= max_dist_conexion:
            padre_idx, extremo_conf = i, 0
        elif g.distance(g1) <= max_dist_conexion:
            padre_idx, extremo_conf = i, -1
    if padre_idx is None:
        return False, ("One end of the tributary must be within "
                       f"{max_dist_conexion:g} m of an already added valley bottom."), None, None

    extremo_libre = g1 if extremo_conf == 0 else g0
    umbral = max_dist_cabecera if max_dist_cabecera else max(10 * max_dist_conexion, 25.0)
    d_cab = contorno.distance(extremo_libre)
    if d_cab > umbral:
        return True, (f"Warning: the head is {d_cab:.0f} m from the boundary, more than "
                      f"the 'Maximum distance from ridgeline to channel head' ({umbral:g} m). "
                      "Lengthen the channel or change the setting if the terrain allows."), \
            padre_idx, extremo_conf
    return True, "Tributary has been accepted.", padre_idx, extremo_conf
