# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Estructuras auxiliares del diseño GeoFluv:

- VANES: deflectores de flujo dentro del cauce (tipo Rosgen: vanes de un solo
  brazo anclados en la orilla, apuntando aguas arriba hacia el centro del
  canal). Natural Regrade los usa para proteger la orilla exterior en
  transiciones forzadas y curvas cerradas. Aquí se colocan a partir del punto
  de transición A→valle del canal (o de su cabecera si no hay transición),
  espaciados en múltiplos de la anchura bankfull y alternando márgenes.

- ESCENA DE VEGETACIÓN: puntos aleatorios de vegetación (árboles/arbustos)
  dentro del límite, alejados del corredor del canal, con cota tomada de la
  superficie de diseño (o DEM), para visualizar en la vista 3D de QGIS.
"""

import math
import random

from qgis.core import QgsFeature, QgsGeometry, QgsPoint, QgsPointXY

from . import setup_tools as st
from .compat import attrs
from .builder import hidraulica_estacion


# ------------------------------------------------------------------ vanes
def generar_vanes(d, glob, lm, n_vanes=3, espaciado_w=4.0, longitud_w=0.75,
                  angulo_deg=25.0):
    """Coloca 'n_vanes' deflectores en el canal d aguas abajo del punto de
    transición (o desde ~1/4 del canal si no la hay), espaciados
    'espaciado_w'·W_bkf, alternando márgenes. Cada vane es una línea 3D desde
    la orilla bankfull hacia el centro, girada 'angulo_deg' aguas arriba.
    Devuelve el número de vanes creados."""
    if not d.puntos or d.L_valle <= 0:
        return 0
    capa = lm.obtener_capa("GF_Vanes")
    # borrar los vanes previos de este canal
    ids = [f.id() for f in capa.getFeatures() if f["channel"] == d.nombre]
    if ids:
        capa.dataProvider().deleteFeatures(ids)

    s0 = d.s_transicion if d.s_transicion is not None else 0.25 * d.L_valle
    ang = math.radians(angulo_deg)
    feats = []
    s = s0
    for i in range(n_vanes):
        est = hidraulica_estacion(d, s, glob)
        w = max(est["ancho_bankfull"], 0.5)
        # punto del eje y tangente local (aguas abajo)
        idx = min(range(len(d.puntos)), key=lambda k: abs(d.puntos[k][3] - s))
        x, y, z, _ = d.puntos[idx]
        i0, i1 = max(0, idx - 2), min(len(d.puntos) - 1, idx + 2)
        tx = d.puntos[i1][0] - d.puntos[i0][0]
        ty = d.puntos[i1][1] - d.puntos[i0][1]
        L = math.hypot(tx, ty) or 1.0
        tx, ty = tx / L, ty / L
        signo = 1.0 if i % 2 == 0 else -1.0          # márgenes alternas
        nx, ny = -ty * signo, tx * signo
        # anclaje en la orilla bankfull
        bx, by = x + nx * w / 2.0, y + ny * w / 2.0
        # brazo hacia el centro, girado aguas arriba
        vx = -nx * math.cos(ang) - tx * math.sin(ang)
        vy = -ny * math.cos(ang) - ty * math.sin(ang)
        Lv = longitud_w * w
        ex, ey = bx + vx * Lv, by + vy * Lv
        # el extremo del brazo baja hasta el lecho (~20 % del calado bkf)
        dz = 0.2 * max(est["prof_bankfull"], 0.05)
        f = QgsFeature(capa.fields())
        f.setGeometry(QgsGeometry.fromPolyline(
            [QgsPoint(bx, by, z + est["prof_bankfull"]),
             QgsPoint(ex, ey, z + dz)]))
        f.setAttributes(attrs(capa, [d.nombre, i, round(s, 1),
                         "R" if signo > 0 else "L"]))
        feats.append(f)
        s += espaciado_w * w
        if s > d.L_valle:
            break
    capa.dataProvider().addFeatures(feats)
    capa.updateExtents(); capa.triggerRepaint()
    return len(feats)


# ---------------------------------------------------------- vegetation scene
def generar_vegetacion(g_lim, disenos, lm, dem=None, capa_superficie=None,
                       arboles_ha=25.0, arbustos_ha=80.0, dist_min_canal=None,
                       semilla=1234):
    """Genera GF_Vegetation: puntos aleatorios (árboles y arbustos) dentro del
    límite, fuera del corredor de los canales, con cota de la superficie de
    diseño (o del DEM). Devuelve (n_arboles, n_arbustos)."""
    capa = lm.obtener_capa("GF_Vegetation")
    capa.dataProvider().truncate()
    rng = random.Random(semilla)
    bb = g_lim.boundingBox()
    area_ha = g_lim.area() / 10000.0
    geoms_ejes = [QgsGeometry.fromPolylineXY(
        [QgsPointXY(p[0], p[1]) for p in d.puntos])
        for d in disenos.values() if d.puntos]

    def z_en(x, y):
        if capa_superficie is not None:
            z = st.cota_dem(capa_superficie, x, y)
            if z is not None:
                return z
        if dem is not None:
            z = st.cota_dem(dem, x, y)
            if z is not None:
                return z
        return 0.0

    def puntos(n_obj, tipo, h_min, h_max, d_canal):
        feats, intentos = [], 0
        while len(feats) < n_obj and intentos < n_obj * 30:
            intentos += 1
            x = bb.xMinimum() + rng.random() * bb.width()
            y = bb.yMinimum() + rng.random() * bb.height()
            g = QgsGeometry.fromPointXY(QgsPointXY(x, y))
            if not g_lim.contains(g):
                continue
            if any(ge.distance(g) < d_canal for ge in geoms_ejes):
                continue
            f = QgsFeature(capa.fields())
            f.setGeometry(QgsGeometry(QgsPoint(x, y, z_en(x, y))))
            f.setAttributes(attrs(capa, [tipo, round(rng.uniform(h_min, h_max), 2)]))
            feats.append(f)
        return feats

    d_arb = dist_min_canal if dist_min_canal is not None else 8.0
    fa = puntos(int(area_ha * arboles_ha), "tree", 3.0, 9.0, d_arb)
    fb = puntos(int(area_ha * arbustos_ha), "shrub", 0.5, 2.0, max(d_arb * 0.5, 3.0))
    capa.dataProvider().addFeatures(fa + fb)
    capa.updateExtents(); capa.triggerRepaint()
    return len(fa), len(fb)
