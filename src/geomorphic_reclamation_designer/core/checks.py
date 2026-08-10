# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Revisión del diseño: el equivalente al 'Error Log' y a las comprobaciones
que el Natural Regrade original va haciendo por su cuenta.

El original reparte sus comprobaciones por toda la interfaz:

* al añadir un canal            → reglas de la polilínea tributaria,
* al fijar cotas y pendientes   → avisos de tolerancia con valor sugerido,
* en las pestañas Setup/Output  → densidad de drenaje en verde o rojo,
* al calcular volúmenes         → balance corte/relleno en verde o rojo,
* al contornear                 → 'Error Log' de Carlson con las líneas de
                                  rotura que se cruzan a distinta cota,
* en el libro (capítulo 8)      → la inspección del borrador: laderas
                                  sobreempinadas, valles trazados a media
                                  ladera, laderas que no vierten al cauce,
                                  tensión tractiva por encima del umbral.

Aquí están TODAS reunidas en un solo comando, cada una con su código, su
gravedad, la entidad concreta a la que se refiere y —cuando tiene sentido— el
valor que habría que poner para resolverla.

El módulo no depende de la interfaz: devuelve una lista de `Hallazgo` que el
panel muestra en una tabla enlazada a las entidades.
"""

import math

from qgis.core import (
    QgsGeometry, QgsPointXY, QgsSpatialIndex, QgsFeature, QgsWkbTypes,
)

from .params import (UMBRAL_PENDIENTE, es_orientacion_NE,
                     rumbo_de_ladera)
from . import setup_tools as st


# --------------------------------------------------------------- estructura
class Hallazgo:
    """Un problema detectado en el diseño.

    gravedad: 'error'   → el diseño no es válido / no funciona como se espera
              'warning' → funciona, pero se aparta del método o de los ajustes
              'info'    → dato de control, no hay nada que corregir
    """

    __slots__ = (
        "capa",
        "codigo",
        "detalle",
        "fid",
        "gravedad",
        "grupo",
        "limite",
        "sugerencia",
        "titulo",
        "valor",
        "x",
        "y",
    )

    def __init__(self, codigo, gravedad, grupo, titulo, detalle="", capa="",
                 fid=-1, x=None, y=None, valor=None, limite=None,
                 sugerencia=""):
        self.codigo = codigo
        self.gravedad = gravedad
        self.grupo = grupo
        self.titulo = titulo
        self.detalle = detalle
        self.capa = capa
        self.fid = fid
        self.x = x
        self.y = y
        self.valor = valor
        self.limite = limite
        self.sugerencia = sugerencia

    def __repr__(self):                                     # pragma: no cover
        return f"<{self.codigo} {self.gravedad}: {self.titulo}>"

    def to_dict(self):
        return {k: getattr(self, k) for k in self.__slots__}


ORDEN_GRAVEDAD = {"error": 0, "warning": 1, "info": 2}

# Grupos, en el orden en que se presentan
G_ENTRADA = "Inputs"
G_ROTURA = "Breaklines / TIN"
G_LADERA = "Slopes"
G_HIDRA = "Hydraulics"
G_TRAZADO = "Layout"
G_SUPERF = "Surface / volumes"


# ------------------------------------------------------------- utilidades
def _pts3(geom):
    """Vértices (x, y, z) de una geometría de línea. Si no tiene Z, z=None."""
    if geom is None or geom.isEmpty():
        return []
    salida = []
    try:
        for v in geom.vertices():
            z = v.z()
            if z != z:                       # NaN
                z = None
            salida.append((v.x(), v.y(), z))
    except Exception:
        return []
    return salida


def _long2d(pts):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1])
               for a, b in zip(pts[:-1], pts[1:]))


def _z_en(pts, x, y):
    """Cota interpolada sobre la polilínea en el punto (x, y) más próximo.

    No se usa QgsGeometry.interpolate porque no todos los proveedores
    conservan la Z al interpolar; aquí se hace a mano sobre los vértices, que
    es exacto para una polilínea."""
    mejor_d2, mejor_z = float("inf"), None
    for (x0, y0, z0), (x1, y1, z1) in zip(pts[:-1], pts[1:]):
        dx, dy = x1 - x0, y1 - y0
        L2 = dx * dx + dy * dy
        if L2 <= 1e-12:
            continue
        t = ((x - x0) * dx + (y - y0) * dy) / L2
        t = max(0.0, min(1.0, t))
        px, py = x0 + t * dx, y0 + t * dy
        d2 = (px - x) ** 2 + (py - y) ** 2
        if d2 < mejor_d2:
            mejor_d2 = d2
            if z0 is None or z1 is None:
                mejor_z = z0 if z1 is None else z1
            else:
                mejor_z = z0 + t * (z1 - z0)
    return mejor_z


# La definición de «ladera norte o este» y el rumbo de una ladera viven en
# `params.py` porque los usa también el TRAZADO (`ridges`, `hillslopes`), no
# solo esta comprobación: tenerlos dos veces era garantizar que el motor y el
# Error Log acabaran discrepando sobre qué ladera es cuál.
_es_NE = es_orientacion_NE
_rumbo = rumbo_de_ladera


def _pendiente_recta_pct(pts):
    """Pendiente en línea recta cresta-pie: desnivel entre distancia
    horizontal, en %. Positiva si baja del primer al último vértice."""
    if len(pts) < 2 or pts[0][2] is None or pts[-1][2] is None:
        return None
    d = math.hypot(pts[-1][0] - pts[0][0], pts[-1][1] - pts[0][1])
    if d < 1e-6:
        return None
    return (pts[0][2] - pts[-1][2]) / d * 100.0


def _capas(lm, nombres):
    salida = []
    for n in nombres:
        try:
            c = lm.obtener_capa(n, crear=False)
        except Exception:
            c = None
        if c is not None and c.isValid():
            salida.append((n, c))
    return salida


def _entidades(capas):
    """[(nombre_capa, fid, geom, pts3)] de todas las líneas de varias capas."""
    salida = []
    for nombre, capa in capas:
        for f in capa.getFeatures():
            g = f.geometry()
            if g is None or g.isEmpty():
                continue
            pts = _pts3(g)
            if len(pts) >= 2:
                salida.append((nombre, f.id(), g, pts))
    return salida


def _indice(lineas):
    """Índice espacial sobre la lista de _entidades(), con id = posición."""
    idx = QgsSpatialIndex()
    for i, (_, _, g, _) in enumerate(lineas):
        f = QgsFeature(i)
        f.setGeometry(g)
        idx.addFeature(f)
    return idx


def _puntos_interseccion(g):
    """Puntos de una geometría de intersección, sea punto, multipunto o
    línea (dos líneas colineales se cortan en un tramo)."""
    if g is None or g.isEmpty():
        return []
    t = QgsWkbTypes.geometryType(g.wkbType())
    if t == QgsWkbTypes.PointGeometry:
        if g.isMultipart():
            return [(p.x(), p.y()) for p in g.asMultiPoint()]
        p = g.asPoint()
        return [(p.x(), p.y())]
    # colineales: basta con muestrear los extremos y el centro del solape
    v = [(p.x(), p.y()) for p in g.vertices()]
    if not v:
        return []
    return [v[0], v[len(v) // 2], v[-1]]


# =========================================================== 1. LÍNEAS DE
#                                                               ROTURA / TIN
CAPAS_ROTURA = ["GRD_Channels", "GRD_ChannelBanks", "GRD_Ridges",
                "GRD_SubRidges", "GRD_Swales"]

# Las líneas del propio cauce (eje, orillas bankfull y flood-prone) son
# desplazamientos paralelos de la MISMA sección: en los meandros se cortan
# entre sí por construcción, y una ladera que muere en la orilla la cruza
# necesariamente a la cota del cajero, no a la del terreno. Esos cruces los
# reporta también el Error Log del original, que en el tutorial avisa de que
# "los cruces que aparecen suelen ser intersecciones de líneas de canal y de
# valle" y de que normalmente son incidentales. Por eso se separan: el defecto
# de verdad es el cruce entre líneas de TERRENO.
CAPAS_CANAL = {"GRD_Channels", "GRD_ChannelBanks"}


def cruces_de_rotura(lm, tol_z=0.10, tol_canal=1.0, max_hallazgos=400):
    """El 'Error Log' de Carlson: líneas de rotura que se cruzan en planta
    con DISTINTA cota en el punto de cruce.

    Es el defecto que más ensucia la triangulación: en el cruce el TIN tiene
    que elegir una cota y el resultado son triángulos volteados, curvas de
    nivel cerradas diminutas y, en el peor caso, un hoyo o un pico.

    Un cruce con la misma cota (una subcresta muriendo sobre la divisoria, un
    tributario entrando en el cauce principal) es correcto y no se avisa: por
    eso el criterio no es 'se cruzan' sino 'se cruzan y no coinciden en Z'."""
    lineas = _entidades(_capas(lm, CAPAS_ROTURA))
    if not lineas:
        return []
    idx = _indice(lineas)
    vistos = set()
    salida = []
    for i, (cap_i, fid_i, g_i, pts_i) in enumerate(lineas):
        for j in idx.intersects(g_i.boundingBox()):
            if j <= i:
                continue
            par = (i, j)
            if par in vistos:
                continue
            vistos.add(par)
            cap_j, fid_j, g_j, pts_j = lineas[j]
            if not g_i.intersects(g_j):
                continue
            n_canal = (cap_i in CAPAS_CANAL) + (cap_j in CAPAS_CANAL)
            for (x, y) in _puntos_interseccion(g_i.intersection(g_j)):
                zi = _z_en(pts_i, x, y)
                zj = _z_en(pts_j, x, y)
                if zi is None or zj is None:
                    continue
                dz = abs(zi - zj)
                if dz <= tol_z:
                    continue
                if n_canal == 0:
                    cod, grav, lim = "C10", "error", tol_z
                    nota = ("Two terrain breaklines cross at different "
                            "elevations: this is a real design defect.")
                elif dz <= tol_canal:
                    cod, grav, lim = "C14", "info", tol_canal
                    nota = ("The crossing is inside the channel corridor and "
                            "the difference is of the order of the bank "
                            "depth, so it is the expected geometry.")
                else:
                    cod = "C14"
                    grav = "warning" if n_canal == 2 else "error"
                    lim = tol_canal
                    nota = ("The crossing is inside the channel corridor but "
                            "the difference is far larger than the bank "
                            "depth.")
                salida.append(Hallazgo(
                    cod, grav, G_ROTURA,
                    "Crossing breaklines at different elevations"
                    if n_canal == 0 else
                    "Crossing inside the channel corridor",
                    f"'{cap_i}' fid {fid_i} (z = {zi:.2f} m) crosses "
                    f"'{cap_j}' fid {fid_j} (z = {zj:.2f} m); "
                    f"the difference is {dz:.2f} m. " + nota,
                    capa=cap_i, fid=fid_i, x=x, y=y, valor=dz, limite=lim,
                    sugerencia="Move one of the two lines, or make them share "
                               "the elevation at the crossing point."))
                if len(salida) >= max_hallazgos:
                    return salida
    return salida


def vertices_defectuosos(lm, tol_xy=0.001, pend_max_pct=300.0):
    """Vértices duplicados / segmentos de longitud cero y picos de cota.

    Son los otros dos campos habituales del Error Log. Un segmento de longitud
    cero rompe el cálculo del acimut, y un salto vertical desproporcionado
    entre dos vértices contiguos es casi siempre un error de edición."""
    salida = []
    for nombre, capa in _capas(lm, CAPAS_ROTURA):
        for f in capa.getFeatures():
            pts = _pts3(f.geometry())
            for k, (a, b) in enumerate(zip(pts[:-1], pts[1:])):
                d = math.hypot(b[0] - a[0], b[1] - a[1])
                if d <= tol_xy:
                    salida.append(Hallazgo(
                        "C11", "warning", G_ROTURA,
                        "Duplicate vertex / zero-length segment",
                        f"'{nombre}' fid {f.id()}: vertices {k} and {k + 1} "
                        f"are {d * 100:.2f} cm apart.",
                        capa=nombre, fid=f.id(), x=a[0], y=a[1],
                        valor=d, limite=tol_xy,
                        sugerencia="Delete the repeated vertex."))
                    continue
                if a[2] is None or b[2] is None:
                    continue
                p = abs(b[2] - a[2]) / d * 100.0
                if p > pend_max_pct:
                    salida.append(Hallazgo(
                        "C12", "warning", G_ROTURA,
                        "Elevation spike on a breakline",
                        f"'{nombre}' fid {f.id()}: {p:.0f} % between vertices "
                        f"{k} and {k + 1} ({abs(b[2] - a[2]):.2f} m over "
                        f"{d:.2f} m).",
                        capa=nombre, fid=f.id(), x=b[0], y=b[1],
                        valor=p, limite=pend_max_pct,
                        sugerencia="Check the elevation of that vertex; a "
                                   "natural slope does not reach this "
                                   "gradient between two contiguous points."))
    return salida


def huecos_sin_rotura(lm, g_lim, largo_max=50.0, paso=10.0):
    """Zonas del área de diseño sin ninguna línea de rotura cerca.

    Es el equivalente al aviso del original 'Ignored xxx triangulation lines
    that exceeded maximum tmesh line length': donde no hay líneas, el TIN
    tiene que unir puntos muy lejanos y la superficie sale plana y facetada,
    sin el relieve que el método pretende crear.

    Se muestrea en malla, pero se AGRUPA: un hueco grande daría decenas de
    puntos con el mismo diagnóstico, y una lista de decenas de avisos idénticos
    no informa mejor que uno solo que diga dónde está el peor y cuánta
    superficie afecta."""
    if g_lim is None or g_lim.isEmpty():
        return []
    lineas = _entidades(_capas(lm, CAPAS_ROTURA))
    if not lineas:
        return []
    idx = _indice(lineas)
    bb = g_lim.boundingBox()
    umbral = largo_max / 2.0
    peor = (0.0, None, None)
    n_fuera = n_dentro = 0
    y = bb.yMinimum()
    while y <= bb.yMaximum():
        x = bb.xMinimum()
        while x <= bb.xMaximum():
            p = QgsGeometry.fromPointXY(QgsPointXY(x, y))
            if g_lim.contains(p):
                n_dentro += 1
                vecinos = idx.nearestNeighbor(QgsPointXY(x, y), 1)
                if vecinos:
                    d = lineas[vecinos[0]][2].distance(p)
                    if d > peor[0]:
                        peor = (d, x, y)
                    if d > umbral:
                        n_fuera += 1
            x += paso
        y += paso
    if not n_dentro:
        return []
    if not n_fuera:
        return [Hallazgo(
            "C13", "info", G_ROTURA, "Breakline coverage is complete",
            f"The point furthest from any design line is {peor[0]:.0f} m away, "
            f"under the {umbral:g} m limit derived from the maximum TIN edge "
            f"length ({largo_max:g} m).",
            x=peor[1], y=peor[2], valor=peor[0], limite=umbral)]
    pct = n_fuera / n_dentro * 100.0
    sup = n_fuera * paso * paso / 10000.0
    return [Hallazgo(
        "C13", "warning", G_ROTURA, "Area without nearby breaklines",
        f"{pct:.0f} % of the design area (about {sup:.1f} ha) is further than "
        f"{umbral:g} m from any design line; the worst point is {peor[0]:.0f} m "
        "away. The surface there will be a flat facet with no relief.",
        x=peor[1], y=peor[2], valor=peor[0], limite=umbral,
        sugerencia="Add a channel in that area, or reduce 'Sub-ridge spacing' "
                   "so more ridges and swales are created.")]


# ================================================================ 2. LADERAS
def pendientes_de_ladera(lm, glob):
    """Pendiente cresta-pie en línea recta frente a los dos objetivos del
    original: 'Maximum straight-line slopes' y 'North or East straight-line
    slopes'.

    El original las trata como un objetivo de mejor ajuste, no como un límite
    duro (no puede controlar cada punto del diseño), así que aquí también son
    avisos: dicen dónde se ha pasado y cuánto."""
    salida = []
    lim = float(glob.pendiente_max_pct)
    lim_ne = float(glob.pendiente_NE_pct)
    for nombre, capa in _capas(lm, ["GRD_SubRidges", "GRD_Swales", "GRD_Ridges"]):
        for f in capa.getFeatures():
            pts = _pts3(f.geometry())
            p = _pendiente_recta_pct(pts)
            if p is None:
                continue
            ac = _rumbo(pts)
            ne = _es_NE(ac)
            objetivo = min(lim, lim_ne) if ne else lim
            if abs(p) > objetivo:
                salida.append(Hallazgo(
                    "C21" if ne else "C20", "warning", G_LADERA,
                    "North/East-facing slope above target" if ne
                    else "Straight-line slope above target",
                    f"'{nombre}' fid {f.id()}: {abs(p):.1f} % over "
                    f"{_long2d(pts):.0f} m"
                    + (f", aspect {ac:.0f}°" if ac is not None else "")
                    + f". Target {objetivo:g} %.",
                    capa=nombre, fid=f.id(), x=pts[0][0], y=pts[0][1],
                    valor=abs(p), limite=objetivo,
                    sugerencia="Lower the ridge, move the channel away from "
                               "it, or raise the channel profile."))
    return salida


def laderas_que_no_vierten(lm, disenos, margen_pct=1.0):
    """Ladera que no lleva el agua al cauce.

    Regla del libro (cap. 8): la ladera del valle tiene que ser MÁS
    empinada que el cauce al que vierte; si no, el agua corre paralela al
    cauce en vez de entrar en él, que es justo lo que el original enseña a
    detectar con 'Runoff Tracking'."""
    if not disenos:
        return []
    salida = []
    ejes = []
    for d in disenos.values() if isinstance(disenos, dict) else disenos:
        if getattr(d, "puntos", None):
            ejes.append(d)
    if not ejes:
        return []
    for nombre, capa in _capas(lm, ["GRD_SubRidges", "GRD_Swales"]):
        for f in capa.getFeatures():
            pts = _pts3(f.geometry())
            p = _pendiente_recta_pct(pts)
            if p is None:
                continue
            # el pie de la ladera es el extremo más bajo
            pie = pts[-1] if (pts[-1][2] or 0) <= (pts[0][2] or 0) else pts[0]
            mejor, mejor_d = None, float("inf")
            for d in ejes:
                for (x, y, z, s) in d.puntos:
                    dd = (x - pie[0]) ** 2 + (y - pie[1]) ** 2
                    if dd < mejor_d:
                        mejor_d, mejor = dd, (d, s)
            if mejor is None or math.sqrt(mejor_d) > 30.0:
                continue
            d, s = mejor
            try:
                p_canal = abs(d.perfil.pendiente(s)) * 100.0
            except Exception:
                continue
            if abs(p) < p_canal + margen_pct:
                salida.append(Hallazgo(
                    "C22", "warning", G_LADERA,
                    "Valley wall not steeper than its channel",
                    f"'{nombre}' fid {f.id()}: the hillslope falls at "
                    f"{abs(p):.1f} % while '{d.nombre}' falls at "
                    f"{p_canal:.1f} % at station {s:.0f} m. Runoff will tend "
                    "to run parallel to the channel instead of into it.",
                    capa=nombre, fid=f.id(), x=pie[0], y=pie[1],
                    valor=abs(p), limite=p_canal + margen_pct,
                    sugerencia="Raise the ridge, or lower the channel head "
                               "elevation / steepen its head slope."))
    return salida


def crestas_sobre_el_limite(lm, g_lim, dem, glob, tol=0.05):
    """'Force ridges to be lower than the design boundary'.

    Cuando el ajuste está activo, ningún punto de una cresta principal puede
    quedar por encima de la cota del límite donde la cresta lo corta: el
    diseño tiene que quedar dentro del cuenco."""
    if not getattr(glob, "forzar_crestas_bajo_limite", False):
        return []
    if g_lim is None or g_lim.isEmpty():
        return []
    anillo = g_lim.asPolygon()[0] if not g_lim.isMultipart() \
        else g_lim.asMultiPolygon()[0][0]
    contorno = QgsGeometry.fromPolylineXY([QgsPointXY(p) for p in anillo])
    salida = []
    for nombre, capa in _capas(lm, ["GRD_Ridges"]):
        for f in capa.getFeatures():
            pts = _pts3(f.geometry())
            if not pts:
                continue
            # cota del límite en el punto por el que la cresta lo alcanza
            extremo = pts[-1]
            pc = contorno.nearestPoint(
                QgsGeometry.fromPointXY(QgsPointXY(extremo[0], extremo[1])))
            z_lim = None
            if dem is not None:
                p = pc.asPoint()
                z_lim = st.cota_dem(dem, p.x(), p.y())
            if z_lim is None:
                z_lim = extremo[2]
            if z_lim is None:
                continue
            alto = max(((z or -1e9), x, y) for x, y, z in pts)
            if alto[0] > z_lim + tol:
                salida.append(Hallazgo(
                    "C23", "warning", G_LADERA,
                    "Ridge above the design boundary elevation",
                    f"'{nombre}' fid {f.id()} reaches {alto[0]:.2f} m while "
                    f"the boundary at its foot is at {z_lim:.2f} m "
                    f"({alto[0] - z_lim:.2f} m higher). "
                    "'Force ridges to be lower than the design boundary' is on.",
                    capa=nombre, fid=f.id(), x=alto[1], y=alto[2],
                    valor=alto[0], limite=z_lim,
                    sugerencia="Lower the ridge profile, or turn the setting "
                               "off if a knob is wanted there."))
    return salida


# ============================================================= 3. HIDRÁULICA
# Rangos de Rosgen usados por el método. Cada tipo se define por pendiente,
# relación anchura:profundidad, encajamiento (entrenchment) y sinuosidad.
ROSGEN = {
    "Aa+": {"pend": (0.10, 9.99), "wd": (0.0, 12.0),
            "entr": (0.0, 1.4), "sin": (1.0, 1.1)},
    "A":   {"pend": (0.04, 0.10), "wd": (0.0, 12.0),
            "entr": (0.0, 1.4), "sin": (1.0, 1.2)},
    "B":   {"pend": (0.02, 0.04), "wd": (12.0, 99.0),
            "entr": (1.4, 2.2), "sin": (1.2, 99.0)},
    "C":   {"pend": (0.0, 0.02), "wd": (12.0, 99.0),
            "entr": (2.2, 99.0), "sin": (1.2, 99.0)},
}


def clasificar_rosgen(pend_abs, wd, entr):
    """Tipo de Rosgen más plausible para una sección, por pendiente y forma."""
    if pend_abs >= 0.10:
        return "Aa+"
    if pend_abs >= UMBRAL_PENDIENTE:
        return "A"
    if entr is not None and entr < 2.2 and wd is not None and wd >= 12.0:
        return "B"
    return "C"


def secciones_fuera_de_rango(disenos):
    """Comprueba cada estación contra el rango del tipo de Rosgen que le
    corresponde por pendiente, que es lo que el Summary Report del original
    pone al lado de los valores de diseño para que el usuario compare.

    Se avisa una vez por canal y por parámetro, con el tramo afectado: repetir
    el mismo aviso en 90 estaciones no ayuda a nadie."""
    if not disenos:
        return []
    salida = []
    iterable = disenos.values() if isinstance(disenos, dict) else disenos
    for d in iterable:
        fallos = {}
        for est in getattr(d, "secciones", []) or []:
            pend = abs(est.get("pendiente", 0.0)) / 100.0
            wd = est.get("wd_usado")
            entr = est.get("entrench")
            tipo = clasificar_rosgen(pend, wd, entr)
            r = ROSGEN[tipo]
            for clave, valor, rango, etiq in (
                    ("wd", wd, r["wd"], "width:depth"),
                    ("entr", entr, r["entr"], "entrenchment")):
                if valor is None:
                    continue
                if valor < rango[0] or valor > rango[1]:
                    k = (tipo, clave)
                    if k not in fallos:
                        fallos[k] = [est["estacion"], est["estacion"],
                                     valor, rango, etiq]
                    else:
                        fallos[k][1] = est["estacion"]
                        fallos[k][2] = valor
        for (tipo, _), (s0, s1, valor, rango, etiq) in fallos.items():
            salida.append(Hallazgo(
                "C33", "warning", G_HIDRA,
                f"{etiq} outside the Rosgen type {tipo} range",
                f"'{d.nombre}': stations {s0:.0f}-{s1:.0f} m are classified "
                f"as type {tipo} by their slope, but their {etiq} is "
                f"{valor:.1f} (stable range {rango[0]:g}-{rango[1]:g}).",
                valor=valor, limite=rango[1],
                sugerencia=f"Adjust 'Width-to-Depth' for this channel, or "
                           f"change the profile so the reach is no longer "
                           f"type {tipo}."))
    return salida


def velocidad_excedida(disenos):
    """La velocidad de Manning por encima de la 'Maximum Water Velocity' del
    canal. El original dimensiona con Q/a = v; si al verificar con Manning la
    velocidad se dispara, la sección no es la que el usuario pidió."""
    if not disenos:
        return []
    salida = []
    iterable = disenos.values() if isinstance(disenos, dict) else disenos
    for d in iterable:
        lim = float(getattr(d.settings, "vel_max_agua", 0) or 0)
        if lim <= 0:
            continue
        peor, s_peor = 0.0, 0.0
        n = 0
        for est in getattr(d, "secciones", []) or []:
            v = est.get("vel_man")
            if v is None:
                continue
            if v > lim:
                n += 1
                if v > peor:
                    peor, s_peor = v, est["estacion"]
        if n:
            salida.append(Hallazgo(
                "C31", "warning", G_HIDRA, "Velocity above the channel limit",
                f"'{d.nombre}': {n} station(s) above "
                f"{lim:.2f} m/s; the worst is {peor:.2f} m/s at station "
                f"{s_peor:.0f} m (Manning verification).",
                valor=peor, limite=lim,
                sugerencia="Increase 'Width-to-Depth', raise Manning's n, or "
                           "flatten the profile in that reach."))
    return salida


def tension_tractiva(disenos):
    """Estaciones con tensión tractiva por encima de la crítica de Shields:
    el mismo criterio que 'Highlight Tractive Force Zones', aquí resumido por
    canal para que aparezca en la revisión completa."""
    if not disenos:
        return []
    salida = []
    iterable = disenos.values() if isinstance(disenos, dict) else disenos
    for d in iterable:
        malas = [e for e in (getattr(d, "secciones", []) or [])
                 if e.get("estab_tau") == "high"]
        if not malas:
            continue
        peor = max(malas, key=lambda e: e.get("ratio_tau") or 0)
        salida.append(Hallazgo(
            "C30", "error", G_HIDRA, "Tractive force above the critical value",
            f"'{d.nombre}': {len(malas)} station(s) exceed the Shields "
            f"critical shear; the worst is station {peor['estacion']:.0f} m "
            f"with tau/tau_crit = {peor.get('ratio_tau', 0):.2f}.",
            x=peor.get("x"), y=peor.get("y"),
            valor=peor.get("ratio_tau"), limite=1.0,
            sugerencia="Lower the profile in that reach (less slope), raise "
                       "D50, or widen the section."))
    return salida


def sinuosidad_canal_A(disenos, glob):
    """Los tramos de tipo A tienen sinuosidad < 1.2 por definición. Si el
    usuario pone más, el original ya no está diseñando un canal A."""
    salida = []
    if glob.sinuosidad_canal_A >= 1.2:
        salida.append(Hallazgo(
            "C32", "warning", G_HIDRA, "'A' channel sinuosity out of range",
            f"'Sinuosity of A channels' is {glob.sinuosidad_canal_A:.2f}; "
            "type A and Aa+ reaches (slope over 4 %) have sinuosity below "
            "1.20 in stable landforms.",
            valor=glob.sinuosidad_canal_A, limite=1.2,
            sugerencia="Set it to 1.15 or lower."))
    iterable = (disenos.values() if isinstance(disenos, dict)
                else (disenos or []))
    for d in iterable:
        v = getattr(d.settings, "sinuosidad_mayor_004", None)
        if v is not None and v >= 1.2:
            salida.append(Hallazgo(
                "C32", "warning", G_HIDRA, "'A' channel sinuosity out of range",
                f"'{d.nombre}': sinuosity for slopes over 4 % is {v:.2f}, "
                "above the 1.20 limit for type A channels.",
                valor=v, limite=1.2, sugerencia="Set it to 1.15 or lower."))
    return salida


def densidad_de_drenaje(disenos, glob, dd_global=None):
    """Densidad de drenaje del conjunto y de cada subcuenca frente al objetivo
    ± varianza (el verde/rojo del original), y además la UNIFORMIDAD: el
    módulo pide comparar la densidad de cada subcuenca con la del conjunto
    para verificar que la red está repartida de forma pareja."""
    salida = []
    obj, var = glob.dd_objetivo, glob.dd_varianza_pct
    if dd_global is not None:
        estado, lo, hi = st.evaluar_dd(dd_global, obj, var)
        if estado != "ok":
            salida.append(Hallazgo(
                "C34", "warning", G_HIDRA,
                "Overall drainage density outside the target range",
                f"{dd_global:.1f} m/ha against a target of {obj:g} "
                f"± {var:g} % ({lo:.1f}-{hi:.1f} m/ha).",
                valor=dd_global, limite=hi if dd_global > hi else lo,
                sugerencia=("Shorten or remove channels, or enlarge the "
                            "boundary." if dd_global > hi else
                            "Lengthen the main channel or add tributaries.")))
    iterable = (disenos.values() if isinstance(disenos, dict)
                else (disenos or []))
    for d in iterable:
        dd = getattr(d, "dd_m_ha", 0.0)
        if dd <= 0:
            continue
        estado, lo, hi = st.evaluar_dd(dd, obj, var)
        if estado != "ok":
            salida.append(Hallazgo(
                "C34", "warning", G_HIDRA,
                "Sub-watershed drainage density outside the target range",
                f"'{d.nombre}': {dd:.1f} m/ha against {obj:g} ± {var:g} % "
                f"({lo:.1f}-{hi:.1f} m/ha).",
                valor=dd, limite=hi if dd > hi else lo,
                sugerencia=("Shorten this channel or enlarge its "
                            "sub-watershed." if dd > hi else
                            "Lengthen it or add a tributary inside its "
                            "sub-watershed.")))
        elif dd_global and abs(dd - dd_global) / max(dd_global, 1e-6) * 100.0 > var:
            salida.append(Hallazgo(
                "C35", "info", G_HIDRA, "Drainage density is not uniform",
                f"'{d.nombre}': {dd:.1f} m/ha against {dd_global:.1f} m/ha "
                f"for the whole area — a difference of "
                f"{abs(dd - dd_global) / dd_global * 100:.0f} %, more than "
                f"the {var:g} % variance. Both values are inside the target "
                "range, but the network is unevenly distributed.",
                valor=dd, limite=dd_global,
                sugerencia="Redistribute the channels so the sub-watersheds "
                           "have a similar size."))
    return salida


# =============================================================== 4. TRAZADO
def valles_a_media_ladera(lm, dem, ang_max=60.0, n_muestras=9):
    """Valle trazado a media ladera en vez de ladera abajo (figura 8-4 del
    libro): la ladera de un lado vierte al cauce y la del otro se aleja de él.

    Se compara la dirección de la línea de fondo de valle con la dirección de
    máxima pendiente del TERRENO en varios puntos. Si el ángulo medio entre
    ambas es grande, el valle va atravesando la ladera."""
    if dem is None:
        return []
    salida = []
    for nombre, capa in _capas(lm, ["GRD_ValleyBottoms"]):
        for f in capa.getFeatures():
            g = f.geometry()
            L = g.length()
            if L < 20.0:
                continue
            angs = []
            for k in range(n_muestras):
                s = L * (k + 0.5) / n_muestras
                p0 = g.interpolate(max(s - 5.0, 0.0)).asPoint()
                p1 = g.interpolate(min(s + 5.0, L)).asPoint()
                vx, vy = p1.x() - p0.x(), p1.y() - p0.y()
                if math.hypot(vx, vy) < 1e-6:
                    continue
                gx, gy = _gradiente(dem, (p0.x() + p1.x()) / 2,
                                    (p0.y() + p1.y()) / 2)
                if gx is None:
                    continue
                n1 = math.hypot(vx, vy)
                n2 = math.hypot(gx, gy)
                if n2 < 1e-9:
                    continue
                cos = (vx * gx + vy * gy) / (n1 * n2)
                cos = max(-1.0, min(1.0, cos))
                a = math.degrees(math.acos(abs(cos)))   # sin importar sentido
                angs.append(a)
            if len(angs) < 3:
                continue
            medio = sum(angs) / len(angs)
            if medio > ang_max:
                p = g.interpolate(L / 2).asPoint()
                salida.append(Hallazgo(
                    "C40", "warning", G_TRAZADO,
                    "Valley drawn across the slope",
                    f"'{nombre}' fid {f.id()}: the valley line runs at "
                    f"{medio:.0f}° on average to the terrain's downslope "
                    f"direction (over {ang_max:g}°). One valley wall will "
                    "slope away from the channel and will not drain into it.",
                    capa=nombre, fid=f.id(), x=p.x(), y=p.y(),
                    valor=medio, limite=ang_max,
                    sugerencia="Redraw the valley line following the "
                               "downslope direction of the terrain."))
    return salida


def _gradiente(dem, x, y, h=None):
    """Vector de máxima pendiente (hacia abajo) del DEM en (x, y)."""
    if h is None:
        try:
            h = max(abs(dem.rasterUnitsPerPixelX()), 1.0)
        except Exception:
            h = 1.0
        h *= 2.0
    z0 = st.cota_dem(dem, x - h, y)
    z1 = st.cota_dem(dem, x + h, y)
    z2 = st.cota_dem(dem, x, y - h)
    z3 = st.cota_dem(dem, x, y + h)
    if None in (z0, z1, z2, z3):
        return None, None
    # gradiente descendente = -grad(z)
    return -(z1 - z0) / (2 * h), -(z3 - z2) / (2 * h)


def canales_junto_a_zonas_altas(lm, disenos, dem, glob, paso=25.0,
                                alcance=60.0):
    """Cauce trazado muy cerca de una zona mucho más alta (figura 8-2) o dos
    cauces demasiado juntos (figura 8-3).

    Los dos errores producen el mismo síntoma medible: la ladera que tiene que
    unir el punto más alto de al lado con la orilla del cauce sale
    sobreempinada. Se mira a ambos lados del eje, perpendicularmente, hasta
    'alcance' metros, se busca la cota máxima del terreno y se calcula la
    pendiente en línea recta hasta el cauce.

    El resultado se agrupa por TRAMOS: el problema es continuo a lo largo de
    un trecho del canal, y lo útil es saber de qué estación a qué estación,
    no recibir un aviso por cada punto de muestreo."""
    if dem is None or not disenos:
        return []
    lim = float(glob.pendiente_max_pct)
    salida = []
    iterable = disenos.values() if isinstance(disenos, dict) else disenos
    for d in iterable:
        pts = getattr(d, "puntos", None)
        if not pts or len(pts) < 3:
            continue
        for signo, etiq in ((1.0, "left"), (-1.0, "right")):
            malos = []
            s_ultimo = -1e9
            for i in range(1, len(pts) - 1):
                x, y, z, s = pts[i]
                if s - s_ultimo < paso:
                    continue
                s_ultimo = s
                dx = pts[i + 1][0] - pts[i - 1][0]
                dy = pts[i + 1][1] - pts[i - 1][1]
                n = math.hypot(dx, dy)
                if n < 1e-6:
                    continue
                nx, ny = -dy / n, dx / n
                peor_p, peor_xy, peor_d = 0.0, None, 0.0
                dist = 10.0
                while dist <= alcance:
                    px = x + nx * signo * dist
                    py = y + ny * signo * dist
                    zt = st.cota_dem(dem, px, py)
                    if zt is not None and zt > z:
                        p = (zt - z) / dist * 100.0
                        if p > peor_p:
                            peor_p, peor_xy, peor_d = p, (px, py), dist
                    dist += 10.0
                if peor_p > lim and peor_xy:
                    malos.append((s, peor_p, peor_xy, peor_d, z))
            # agrupar estaciones consecutivas en tramos
            for tramo in _tramos(malos, paso * 2.5):
                s0, s1 = tramo[0][0], tramo[-1][0]
                peor = max(tramo, key=lambda t: t[1])
                salida.append(Hallazgo(
                    "C41", "warning", G_TRAZADO,
                    "Channel too close to high ground",
                    f"'{d.nombre}', {etiq} bank, stations {s0:.0f}-{s1:.0f} m: "
                    f"the valley wall connecting the channel with the high "
                    f"ground beside it would fall at up to {peor[1]:.0f} % "
                    f"({peor[4]:.1f} m up to the top over {peor[3]:.0f} m), "
                    f"over the {lim:g} % target.",
                    x=peor[2][0], y=peor[2][1], valor=peor[1], limite=lim,
                    sugerencia="Move the valley line away from the high "
                               "ground, or lower that area in the "
                               "comparison surface."))
    return salida


def _tramos(muestras, hueco_max):
    """Agrupa muestras ordenadas por estación en tramos contiguos."""
    grupos, actual = [], []
    for m in muestras:
        if actual and m[0] - actual[-1][0] > hueco_max:
            grupos.append(actual)
            actual = []
        actual.append(m)
    if actual:
        grupos.append(actual)
    return grupos


# ============================================================ 5. ENTRADAS
def ajustes_incoherentes(proyecto, glob):
    """Ajustes que el original vigila en su propia interfaz."""
    salida = []
    canales = list(getattr(proyecto, "canales", []) or [])
    for i, c in enumerate(canales):
        n = int(getattr(c, "espaciado_subcrestas", 3) or 3)
        if n % 2 == 0:
            salida.append(Hallazgo(
                "C04", "warning", G_ENTRADA,
                "Sub-ridge spacing must be an odd number",
                f"'{c.nombre}': the spacing is {n}. With an even number every "
                "sub-ridge and its swale end up on the same side of the "
                "valley instead of alternating.",
                valor=n, limite=n + 1,
                sugerencia=f"Use {n + 1} (or {max(n - 1, 1)})."))
        # solo el canal principal: la boca de un tributario la fija el perfil
        # del canal receptor en la confluencia, no el usuario
        if i == 0 and getattr(c, "cota_boca", None) is None:
            salida.append(Hallazgo(
                "C05", "warning", G_ENTRADA,
                "Main channel mouth elevation not specified",
                f"'{c.nombre}': the mouth elevation is being interpolated from "
                "the surface. It is the single most critical value of the "
                "design and a map interpolation can be off by metres.",
                sugerencia="Enter the field-surveyed base-level elevation in "
                           "'Current Channel Settings'."))
    if glob.dd_varianza_pct <= 0:
        salida.append(Hallazgo(
            "C06", "info", G_ENTRADA, "Drainage density variance is zero",
            "With 0 % variance any value other than the exact target will be "
            "flagged.", valor=glob.dd_varianza_pct,
            sugerencia="Use the range measured in the reference areas, "
                       "typically 15-25 %."))
    return salida


def perfil_ajustado(disenos, glob):
    """Cuando las cotas y pendientes pedidas no admiten un perfil cóncavo
    monótono, el motor las recorta. El original avisa además con el VALOR que
    resolvería el conflicto; aquí se calcula igual."""
    salida = []
    iterable = (disenos.values() if isinstance(disenos, dict)
                else (disenos or []))
    for d in iterable:
        perfil = getattr(d, "perfil", None)
        if perfil is None or not getattr(perfil, "ajustado", False):
            continue
        pedida = d.settings.pendiente_cabecera_pct
        real = perfil.s_cabecera * 100.0
        if abs(real - pedida) <= glob.tol_pendiente_cabecera_pct:
            continue
        # cota de cabecera que HARÍA compatible la pendiente pedida:
        # z_cab = z_boca - L·(s_cab + s_boca)/2 con las pendientes deseadas
        z_boca = perfil.z(d.L_valle)
        s_cab = pedida / 100.0
        s_boca = perfil.s_boca
        z_sug = z_boca - d.L_valle * (s_cab + s_boca) / 2.0
        z_act = perfil.z(0.0)
        salida.append(Hallazgo(
            "C02", "warning", G_ENTRADA,
            "Head slope had to be adjusted",
            f"'{d.nombre}': the requested head slope is {pedida:.1f} % but "
            f"the profile can only be kept concave and monotonic at "
            f"{real:.1f} % with a head elevation of {z_act:.2f} m.",
            valor=real, limite=pedida,
            sugerencia=(f"Raise the head elevation to {z_sug:.2f} m "
                        f"({z_sug - z_act:+.2f} m) to keep "
                        f"{pedida:.1f} %, or accept {real:.1f} %.")))
    return salida


# ============================================================== 6. SUPERFICIE
def anomalias_superficie(ruta_raster, umbral=0.20, max_hallazgos=20):
    """Hoyos cerrados y picos aislados en la superficie de diseño.

    Un hoyo cerrado —una celda con las ocho vecinas más altas— es agua que no
    sale: no es relieve natural sino un defecto de la triangulación, casi
    siempre donde dos líneas de rotura no encajan."""
    if not ruta_raster:
        return []
    try:
        import numpy as np
        from osgeo import gdal
    except Exception:
        return []
    try:
        ds = gdal.Open(ruta_raster)
        if ds is None:
            return []
        b = ds.GetRasterBand(1)
        nd = b.GetNoDataValue()
        a = b.ReadAsArray().astype("float64")
        gt = ds.GetGeoTransform()
        val = np.isfinite(a)
        if nd is not None:
            val &= (a != nd)
        a = np.where(val, a, np.nan)
        centro = a[1:-1, 1:-1]
        vecinas = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy == 0 and dx == 0:
                    continue
                vecinas.append(a[1 + dy: a.shape[0] - 1 + dy,
                                 1 + dx: a.shape[1] - 1 + dx])
        pila = np.stack(vecinas)
        vmin = np.nanmin(pila, axis=0)
        vmax = np.nanmax(pila, axis=0)
        hoyos = centro < vmin - umbral
        picos = centro > vmax + umbral
        prof = np.where(hoyos, vmin - centro, 0.0)
        alt = np.where(picos, centro - vmax, 0.0)
        salida = []
        for mat, mask, cod, etiq, texto in (
                (prof, hoyos, "C50", "Closed depression in the design surface",
                 "water cannot leave this cell: all eight neighbours are "
                 "higher"),
                (alt, picos, "C51", "Isolated peak in the design surface",
                 "all eight neighbours are lower: a spike left by the "
                 "triangulation")):
            n = int(np.nansum(mask))
            if not n:
                continue
            plano = np.nan_to_num(mat).ravel()
            for k in np.argsort(-plano)[:max_hallazgos // 2]:
                d = float(plano[k])
                if d <= umbral:
                    break
                r, c = np.unravel_index(k, mat.shape)
                x = gt[0] + (c + 1.5) * gt[1]
                y = gt[3] + (r + 1.5) * gt[5]
                salida.append(Hallazgo(
                    cod, "error" if cod == "C50" else "warning", G_SUPERF,
                    etiq, f"{d:.2f} m deep — {texto}. Total found: {n}.",
                    x=float(x), y=float(y), valor=d, limite=umbral,
                    sugerencia="Increase 'Naturalness' when contouring, or "
                               "fix the breaklines that meet at that point "
                               "(see the Breaklines group)."))
        ds = None
        return salida
    except Exception:
        return []


def balance_de_tierras(resultado_cf, glob):
    """Balance corte/relleno frente a los límites del original."""
    if not resultado_cf:
        return []
    pct = resultado_cf.get("pct")
    if pct is None:
        return []
    lo = glob.var_min_corte_relleno_pct
    hi = glob.var_max_corte_relleno_pct
    if lo <= pct <= hi:
        return [Hallazgo("C52", "info", G_SUPERF, "Cut/fill balance is inside "
                         "the allowed range",
                         f"{pct:.1f} % (allowed {lo:g}-{hi:g} %).",
                         valor=pct, limite=hi)]
    falta = (resultado_cf.get("relleno_ajustado_m3", 0)
             - resultado_cf.get("corte_ajustado_m3", 0))
    return [Hallazgo(
        "C52", "warning", G_SUPERF, "Cut/fill balance outside the allowed range",
        f"{pct:.1f} % (allowed {lo:g}-{hi:g} %). "
        + (f"{abs(falta):,.0f} m3 of fill are missing."
           if falta > 0 else
           f"{abs(falta):,.0f} m3 of cut are left over."),
        valor=pct, limite=hi if pct > hi else lo,
        sugerencia=("Lower the ridges or raise the channel profiles."
                    if pct > hi else
                    "Raise the ridges or lower the channel profiles."))]


# ================================================================ ORQUESTA
def revisar(lm, glob, proyecto=None, disenos=None, g_lim=None, dem=None,
            ruta_superficie=None, resultado_cf=None, dd_global=None,
            grupos=None, log=None):
    """Ejecuta todas las comprobaciones y devuelve la lista de hallazgos
    ordenada por gravedad y grupo.

    'grupos' permite pedir solo algunos (los nombres G_*); por defecto van
    todos. Cada bloque va protegido: que una comprobación falle —porque falta
    una capa, porque el DEM no cubre el área— no debe impedir que se ejecuten
    las demás."""
    pedidos = set(grupos) if grupos else None
    salida = []

    def _corre(grupo, etiqueta, fn, *a, **kw):
        if pedidos is not None and grupo not in pedidos:
            return
        try:
            r = fn(*a, **kw) or []
            salida.extend(r)
            if log:
                log(f"  · {etiqueta}: {len(r)}")
        except Exception as e:                              # pragma: no cover
            if log:
                log(f"  · {etiqueta}: could not be run ({e})")

    tol_z = float(getattr(glob, "tol_cruce_breaklines_m", 0.10))
    tol_canal = float(getattr(glob, "tol_cruce_canal_m", 1.00))
    largo_max = float(getattr(glob, "long_max_lado_tin_m", 50.0))
    pend_pico = float(getattr(glob, "pend_max_linea_pct", 300.0))
    ang_valle = float(getattr(glob, "ang_max_valle_ladera_deg", 60.0))

    if proyecto is not None:
        _corre(G_ENTRADA, "settings", ajustes_incoherentes, proyecto, glob)
    _corre(G_ENTRADA, "adjusted profiles", perfil_ajustado, disenos, glob)

    _corre(G_ROTURA, "crossing breaklines", cruces_de_rotura, lm, tol_z,
           tol_canal)
    _corre(G_ROTURA, "vertices", vertices_defectuosos, lm, 0.001, pend_pico)
    _corre(G_ROTURA, "breakline coverage", huecos_sin_rotura, lm, g_lim,
           largo_max)

    _corre(G_LADERA, "straight-line slopes", pendientes_de_ladera, lm, glob)
    _corre(G_LADERA, "walls draining to the channel", laderas_que_no_vierten,
           lm, disenos)
    _corre(G_LADERA, "ridges under the boundary", crestas_sobre_el_limite,
           lm, g_lim, dem, glob)

    _corre(G_HIDRA, "tractive force", tension_tractiva, disenos)
    _corre(G_HIDRA, "velocity", velocidad_excedida, disenos)
    _corre(G_HIDRA, "Rosgen ranges", secciones_fuera_de_rango, disenos)
    _corre(G_HIDRA, "'A' sinuosity", sinuosidad_canal_A, disenos, glob)
    _corre(G_HIDRA, "drainage density", densidad_de_drenaje, disenos, glob,
           dd_global)

    _corre(G_TRAZADO, "valleys across the slope", valles_a_media_ladera,
           lm, dem, ang_valle)
    _corre(G_TRAZADO, "channels beside high ground",
           canales_junto_a_zonas_altas, lm, disenos, dem, glob)

    _corre(G_SUPERF, "surface anomalies", anomalias_superficie,
           ruta_superficie)
    _corre(G_SUPERF, "cut/fill balance", balance_de_tierras, resultado_cf,
           glob)

    orden_grupo = {g: i for i, g in enumerate(
        [G_ENTRADA, G_TRAZADO, G_ROTURA, G_LADERA, G_HIDRA, G_SUPERF])}
    salida.sort(key=lambda h: (ORDEN_GRAVEDAD.get(h.gravedad, 3),
                               orden_grupo.get(h.grupo, 9), h.codigo))
    return salida


def resumen(hallazgos):
    """(n_errores, n_avisos, n_info) para el mensaje de una línea."""
    n = {"error": 0, "warning": 0, "info": 0}
    for h in hallazgos:
        n[h.gravedad] = n.get(h.gravedad, 0) + 1
    return n["error"], n["warning"], n["info"]
