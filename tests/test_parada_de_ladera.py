# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""La marcha de ladera para en la divisoria de VALLE (core/hillslopes.py).

B-049, y es una regresion que creo B-045. Desde que la particion de subcuencas
se hace con las LINEAS DE VALLE, la divisoria es el eje medial de esas lineas.
Pero `_trazar_ladera` seguia parando en la equidistancia de los EJES
meandriformes, que es otra curva.

Medido reconstruyendo el eje medial de los valles del Ej_2 desde los 378
vertices de `GRD_Ridges`: la separacion entre las dos curvas tiene mediana
1.12 m, p90 4.83 y p99 7.52. Con eso, el 32.9 % de los vertices caeria fuera de
la tolerancia de 2.0 m con la que `topology` da una cabecera por «llegada» a la
divisoria. Volveria B-034 por un lado (el 38 % de los extremos altos en el aire)
y `divides._cortar_en_divisorias` amputaria por el otro.

La distincion que hay que mantener:

    geoms_div (lineas de valle) -> DONDE esta la divisoria -> donde se para
    geoms     (ejes sinuosos)   -> distancia al AGUA        -> cota de ladera
"""
import math
import os
import sys
import types

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src",
                    "geomorphic_reclamation_designer", "core")

_q = types.ModuleType("qgis")
_c = types.ModuleType("qgis.core")


def _cualquier_clase(nombre):
    if nombre.startswith("_"):
        raise AttributeError(nombre)
    cls = type(nombre, (), {})
    setattr(_c, nombre, cls)
    return cls


_c.__getattr__ = _cualquier_clase
_q.core = _c
sys.modules.setdefault("qgis", _q)
sys.modules.setdefault("qgis.core", _c)

if "grd_ridges_pl" not in sys.modules:
    _src_r = open(os.path.join(_DIR, "ridges.py"), encoding="utf-8").read()
    _src_r = _src_r.replace("from . import setup_tools as st", "st = None")
    _src_r = _src_r.replace(
        "from .compat import tipo_geom, CAMPO_STR, attrs",
        "tipo_geom = CAMPO_STR = None\nattrs = lambda capa, v: v")
    _src_r = _src_r.replace(
        "from .params import pendiente_max_ladera, rumbo_de_ladera",
        "pendiente_max_ladera = rumbo_de_ladera = None")
    _rg = types.ModuleType("grd_ridges_pl")
    exec(compile(_src_r, "ridges.py", "exec"), _rg.__dict__)
    sys.modules["grd_ridges_pl"] = _rg

_ruta = os.path.join(_DIR, "hillslopes.py")
_src = open(_ruta, encoding="utf-8").read()
_src = _src.replace("from . import setup_tools as st", "st = None")
_src = _src.replace("from .compat import attrs", "attrs = lambda capa, v: v")
_src = _src.replace(
    "from .ridges import (\n"
    "    PASO_CRESTA, PASO_MARCHA, perfil_trapezoidal, convexo_subcresta,\n"
    "    convexo_vaguada, _geoms_ejes, _z_ladera,\n"
    ")",
    "from grd_ridges_pl import (\n"
    "    PASO_CRESTA, PASO_MARCHA, perfil_trapezoidal, convexo_subcresta,\n"
    "    convexo_vaguada, _geoms_ejes, _z_ladera,\n"
    ")")
hs = types.ModuleType("grd_hillslopes_pl")
exec(compile(_src, _ruta, "exec"), hs.__dict__)


# ------------------------------------------------------- geometria falsa
def _d_pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


class _Geom:
    def __init__(self, pts):
        self.pts = [(p[0], p[1]) for p in pts]

    @staticmethod
    def fromPointXY(p):
        return _Geom([(p[0], p[1])])

    def distance(self, otra):
        mejor = float("inf")
        for p in otra.pts:
            if len(self.pts) == 1:
                mejor = min(mejor, math.dist(p, self.pts[0]))
            for a, b in zip(self.pts[:-1], self.pts[1:]):
                mejor = min(mejor, _d_pt_seg(p, a, b))
        return mejor

    def contains(self, _g):
        return True                 # el limite no interviene en esta prueba


class _P3:
    def __init__(self, x, y, z):
        self.xyz = (x, y, z)


class _Pt:
    def __init__(self, x, y):
        self._x, self._y = x, y

    def __getitem__(self, i):
        return (self._x, self._y)[i]


def _linea(y, x0=-500.0, x1=500.0):
    return _Geom([(x0, y), (x1, y)])


def _marcha(geoms, geoms_div):
    """Traza una ladera recta hacia el norte desde (0, 0) y devuelve su
    longitud, que es donde ha parado."""
    hs.QgsGeometry = _Geom
    hs.QgsPointXY = _Pt
    hs.QgsPoint = _P3
    hs._z_ladera = lambda *a, **k: 320.0
    linea = hs._trazar_ladera(
        (0.0, 0.0), (0.0, 1.0), "propio", geoms, _Geom([(0, 0)]),
        {}, 0.33, 20.0, 280.0, geoms_div=geoms_div)
    assert linea is not None
    return max(p.xyz[1] for p in linea)


# ------------------------------------------------------------- la prueba
def test_para_en_la_equidistancia_de_los_valles_y_no_en_la_de_los_ejes():
    """Dos valles paralelos a 0 y 60 (divisoria en y = 30) y dos ejes a 0 y 100
    (equidistancia en y = 50). La ladera tiene que morir en 30."""
    valles = {"propio": _linea(0.0), "otro": _linea(60.0)}
    ejes = {"propio": _linea(0.0), "otro": _linea(100.0)}

    con_valles = _marcha(ejes, valles)
    con_ejes = _marcha(ejes, None)      # comportamiento anterior a B-049

    assert 28.0 <= con_valles <= 34.0, con_valles
    assert 48.0 <= con_ejes <= 54.0, con_ejes
    assert con_ejes - con_valles > 15.0


def test_sin_lineas_de_valle_se_cae_a_los_ejes_y_no_revienta():
    """Un diseno sin `dens` no puede dejar la ladera sin criterio de parada."""
    ejes = {"propio": _linea(0.0), "otro": _linea(60.0)}
    assert 28.0 <= _marcha(ejes, None) <= 34.0


def test_la_cota_sigue_midiendose_contra_los_ejes():
    """`geoms` (los ejes) es lo que va a `_z_ladera`: la cota de ladera depende
    de la distancia al AGUA, no a la linea de valle. Si alguien 'simetriza'
    esto, el desnivel se calcula contra una linea por la que no corre nada."""
    fuente = open(_ruta, encoding="utf-8").read()
    i = fuente.index("z_div = _z_ladera(")
    llamada = fuente[i:i + 200]
    assert "geoms" in llamada and "geoms_div" not in llamada and "gd" not in llamada
