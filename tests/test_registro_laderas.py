# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del registro de lineas de ladera ya trazadas (core/hillslopes.py).

Es lo que decide cuando una marcha se detiene contra otra linea y de cual
hereda la cota. Hasta la v1.0.19 recorria un dict POR CANAL y se quedaba con la
PRIMERA linea dentro del radio en orden de insercion; ahora mira las de todos
los canales, con indice espacial, y se queda con la MAS CERCANA (B-034).
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

# hillslopes importa de ridges; se le da el modulo real ya cargado.
if "grd_ridges_hs" not in sys.modules:
    _src_r = open(os.path.join(_DIR, "ridges.py"), encoding="utf-8").read()
    _src_r = _src_r.replace("from . import setup_tools as st", "st = None")
    _src_r = _src_r.replace(
        "from .compat import tipo_geom, CAMPO_STR, attrs",
        "tipo_geom = CAMPO_STR = None\nattrs = lambda capa, v: v")
    _src_r = _src_r.replace(
        "from .params import pendiente_max_ladera, rumbo_de_ladera",
        "pendiente_max_ladera = rumbo_de_ladera = None")
    _rg = types.ModuleType("grd_ridges_hs")
    exec(compile(_src_r, "ridges.py", "exec"), _rg.__dict__)
    sys.modules["grd_ridges_hs"] = _rg

_ruta = os.path.join(_DIR, "hillslopes.py")
_src = open(_ruta, encoding="utf-8").read()
_src = _src.replace("from . import setup_tools as st", "st = None")
_src = _src.replace("from .compat import attrs", "attrs = lambda capa, v: v")
_src = _src.replace(
    "from .ridges import (\n"
    "    PASO_CRESTA, PASO_MARCHA, perfil_trapezoidal, convexo_subcresta,\n"
    "    convexo_vaguada, _geoms_ejes, _z_ladera,\n"
    ")",
    "from grd_ridges_hs import (\n"
    "    PASO_CRESTA, PASO_MARCHA, perfil_trapezoidal, convexo_subcresta,\n"
    "    convexo_vaguada, _geoms_ejes, _z_ladera,\n"
    ")")
hs = types.ModuleType("grd_hillslopes")
exec(compile(_src, _ruta, "exec"), hs.__dict__)


# ------------------------------------------------------- geometria falsa
class _PtXY:
    def __init__(self, x, y):
        self._x, self._y = float(x), float(y)

    def x(self):
        return self._x

    def y(self):
        return self._y


class _Pt3(_PtXY):
    def __init__(self, x, y, z=0.0):
        _PtXY.__init__(self, x, y)
        self._z = float(z)

    def z(self):
        return self._z


class _Rect:
    def __init__(self, pts):
        self.x0 = min(p[0] for p in pts)
        self.x1 = max(p[0] for p in pts)
        self.y0 = min(p[1] for p in pts)
        self.y1 = max(p[1] for p in pts)

    def grow(self, r):
        self.x0 -= r
        self.x1 += r
        self.y0 -= r
        self.y1 += r


def _dist_pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


class _Geom:
    def __init__(self, pts):
        self.pts = [(p.x(), p.y()) if hasattr(p, "x") else (p[0], p[1])
                    for p in pts]

    @staticmethod
    def fromPointXY(p):
        return _Geom([p])

    @staticmethod
    def fromPolylineXY(ps):
        return _Geom(ps)

    def boundingBox(self):
        return _Rect(self.pts)

    def distance(self, otra):
        mejor = float("inf")
        for p in otra.pts:
            if len(self.pts) == 1:
                mejor = min(mejor, math.dist(p, self.pts[0]))
            for a, b in zip(self.pts[:-1], self.pts[1:]):
                mejor = min(mejor, _dist_pt_seg(p, a, b))
        return mejor


class _Feature:
    def __init__(self, fid):
        self._id = fid
        self._g = None

    def setGeometry(self, g):
        self._g = g


class _Indice:
    """Sin poda: devuelve todo. Lo que se prueba es la ELECCION, no el indice."""

    def __init__(self):
        self.fids = []

    def addFeature(self, f):
        self.fids.append(f._id)

    def intersects(self, _rect):
        return list(self.fids)


def _monta():
    hs.QgsGeometry = _Geom
    hs.QgsPointXY = _PtXY
    hs.QgsPoint = _Pt3
    hs.QgsFeature = _Feature
    hs.QgsSpatialIndex = _Indice


def _linea(pts):
    return [_Pt3(x, y, z) for x, y, z in pts]


# --------------------------------------------------------------- pruebas
def test_se_queda_con_la_linea_MAS_CERCANA_no_con_la_primera():
    """Antes se rompia el bucle en la primera dentro del radio, en orden de
    insercion, asi que la cota se heredaba de una linea que podia no ser la de
    al lado."""
    _monta()
    r = hs._RegistroLaderas()
    r.anadir(_linea([(0.0, 2.5, 100.0), (100.0, 2.5, 100.0)]))   # a 2.5 m
    r.anadir(_linea([(0.0, 0.5, 200.0), (100.0, 0.5, 200.0)]))   # a 0.5 m
    cerca = r.mas_cercana(_Geom([(50.0, 0.0)]), hs.TOL_TOQUE)
    assert cerca is not None
    d, _geom, zs = cerca
    assert abs(d - 0.5) < 1e-9
    assert zs[0] == 200.0, "ha heredado la cota de la linea equivocada"


def test_fuera_del_radio_no_engancha():
    _monta()
    r = hs._RegistroLaderas()
    r.anadir(_linea([(0.0, 50.0, 100.0), (100.0, 50.0, 100.0)]))
    assert r.mas_cercana(_Geom([(50.0, 0.0)]), hs.TOL_TOQUE) is None


def test_el_registro_no_distingue_de_que_canal_es_cada_linea():
    """Las lineas de canales distintos tambien tienen que verse: antes no, y
    dos laderas de canales opuestos podian cruzarse sin que nada lo impidiera.
    El registro es uno solo y no guarda el canal."""
    _monta()
    r = hs._RegistroLaderas()
    r.anadir(_linea([(0.0, 1.0, 100.0), (100.0, 1.0, 100.0)]))
    assert r.mas_cercana(_Geom([(50.0, 0.0)]), hs.TOL_TOQUE) is not None
    assert not hasattr(r, "por_canal")


def test_el_tope_de_toque_no_es_mayor_que_el_paso_de_marcha():
    """Si `TOL_TOQUE` superara el paso, la marcha engancharia antes de haberse
    movido y ninguna linea llegaria a ninguna parte."""
    assert 0 < hs.TOL_TOQUE < hs.PASO_MARCHA


# ------------------------------------------------- angulo de subcresta
def test_el_angulo_se_mide_desde_la_PERPENDICULAR_al_cauce():
    """[LIBRO glosario p. xxxiv] 'the angle of a sub-ridge from a PERPENDICULAR
    axis to the channel measured in the UPSTREAM direction', y el rotulo del
    ajuste (p. 190): 'angle from sub-ridge to channel's perpendicular,
    upstream'. Con ang = 0 la linea sale perpendicular al cauce."""
    tx, ty = 1.0, 0.0                       # valle hacia el este (aguas abajo)
    for signo in (1.0, -1.0):
        dx, dy = hs.direccion_de_ladera(tx, ty, signo, 0.0)
        assert abs(dx) < 1e-12               # sin componente a lo largo del eje
        assert abs(abs(dy) - 1.0) < 1e-12    # perpendicular pura
        # margenes opuestas
        assert (dy > 0) == (signo > 0)


def test_el_giro_va_hacia_AGUAS_ARRIBA_en_las_dos_margenes():
    tx, ty = 1.0, 0.0
    ang = math.radians(20.0)
    for signo in (1.0, -1.0):
        dx, dy = hs.direccion_de_ladera(tx, ty, signo, ang)
        assert dx < 0, "deberia apuntar aguas arriba"
        # y el angulo con el eje del cauce es 90 - 20 = 70 grados
        cos = abs(dx * tx + dy * ty) / math.hypot(dx, dy)
        assert abs(math.degrees(math.acos(cos)) - 70.0) < 1e-9


def test_la_direccion_es_unitaria():
    for ang in (0.0, math.radians(10.0), math.radians(45.0)):
        dx, dy = hs.direccion_de_ladera(0.6, 0.8, 1.0, ang)
        assert abs(math.hypot(dx, dy) - 1.0) < 1e-12
