# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas de la PLANTA de las divisorias de cuenca (core/ridges.py).

B-045. La divisoria de cuenca es equidistante de las POLILINEAS DE FONDO DE
VALLE, no de los ejes meandriformes que se dibujan alrededor de ellas:

    «The main ridgelines are shown between the tributary channels and are
    sub-parallel to the channels» (Natural Regrade Module, p. 36-37)

    El Preview muestra «main ridgelines (yellow) and valley centerlines (more
    linear blue)», y los ejes zigzag o sinuosos «will be designed around the
    more linear valley input lines» (LIBRO p. 242, pie de la figura 9-13).

Medido en la salida original del Ej_2, |d1 - d2| de cada vertice de las seis
divisorias respecto a las dos lineas mas proximas: 0.02-0.73 m contra las
lineas de valle y 1.0-2.9 m contra los ejes. Hasta la v1.0.24 nosotros
haciamos lo contrario (0.14-1.78 m contra los ejes, 1.77-4.52 m contra los
valles) y la divisoria heredaba la ondulacion del meandro: 70 grados/100 m de
giro acumulado frente a los 6.5-31.3 del original.

Se ejecuta el modulo REAL con QGIS simulado, no una copia de sus funciones:
una copia se desincroniza y deja de probar lo que se cree que prueba.
"""
import math
import os
import sys
import types

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

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src",
                    "geomorphic_reclamation_designer", "core")

if "gfq_params" not in sys.modules:
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "gfq_params", os.path.join(_DIR, "params.py"))
    _mod = importlib.util.module_from_spec(_spec)
    _mod.__package__ = ""
    sys.modules["gfq_params"] = _mod
    _spec.loader.exec_module(_mod)

_ruta = os.path.join(_DIR, "ridges.py")
_src = open(_ruta, encoding="utf-8").read().replace(
    "from . import setup_tools as st", "st = None").replace(
    "from .compat import tipo_geom, CAMPO_STR, attrs",
    "tipo_geom = CAMPO_STR = None\nattrs = lambda capa, v: v").replace(
    "from .params import pendiente_max_ladera, rumbo_de_ladera",
    "from gfq_params import pendiente_max_ladera, rumbo_de_ladera")
rg = types.ModuleType("grd_ridges_planta")
exec(compile(_src, _ruta, "exec"), rg.__dict__)


class _Diseno:
    """Lo minimo de builder.Diseno que mira la particion de subcuencas."""

    def __init__(self, nombre="main", dens=None, puntos=None):
        self.nombre = nombre
        self.dens = list(dens or [])        # [(s, x, y)] fondo de valle
        self.puntos = list(puntos or [])    # [(x, y, z, s)] eje meandriforme


def _valle_recto(largo=100.0, paso=1.0, y=0.0):
    n = int(largo / paso)
    return [(i * paso, i * paso, y) for i in range(n + 1)]


def _eje_con_meandros(dens, amplitud=6.0, lam=40.0):
    """El eje se traza DESPLAZANDO la linea de valle sobre su normal."""
    return [(x, y + amplitud * math.sin(2 * math.pi * s / lam), 0.0, s)
            for s, x, y in dens]


# ------------------------------------------------- fuente de la particion
def test_la_particion_muestrea_la_linea_de_valle_y_no_el_eje():
    """B-045. La divisoria es equidistante del FONDO DE VALLE."""
    dens = _valle_recto()
    d = _Diseno(dens=dens, puntos=_eje_con_meandros(dens))
    xy = rg._muestras_de_valle(d)
    assert len(xy) == len(dens)
    # todas las muestras estan sobre el valle (y = 0), ninguna sobre el eje
    assert max(abs(p[1]) for p in xy) < 1e-9
    assert xy[0] == (0.0, 0.0)


def test_sin_linea_de_valle_se_cae_al_eje_en_vez_de_quedarse_sin_puntos():
    """Una cuenca sin puntos desaparece del Voronoi y se lleva por delante las
    divisorias de sus vecinas, que es peor que muestrear la fuente equivocada."""
    dens = _valle_recto()
    d = _Diseno(dens=[], puntos=_eje_con_meandros(dens))
    xy = rg._muestras_de_valle(d)
    assert len(xy) == len(dens)
    assert max(abs(p[1]) for p in xy) > 1.0     # son los del eje, ondulados


def test_un_diseno_vacio_no_revienta():
    assert rg._muestras_de_valle(_Diseno(dens=[], puntos=[])) == []


# --------------------------------------------- por que importa la fuente
def _equidistante(a, b, xs):
    """Ordenada de la curva |d_a| = |d_b| entre dos polilineas, muestreada en
    xs. Devuelve la y de la curva en cada x (busqueda por biseccion)."""
    def dist(poly, px, py):
        mejor = float("inf")
        for i in range(len(poly) - 1):
            ax, ay = poly[i]
            bx, by = poly[i + 1]
            dx, dy = bx - ax, by - ay
            dd = dx * dx + dy * dy
            t = 0.0 if dd < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / dd))
            mejor = min(mejor, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
        return mejor

    ys = []
    for x in xs:
        lo, hi = 0.0, 60.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if dist(a, x, mid) - dist(b, x, mid) < 0:
                lo = mid
            else:
                hi = mid
        ys.append((lo + hi) / 2)
    return ys


def test_la_curva_equidistante_de_los_ejes_ondula_y_la_del_valle_no():
    """Este es el motivo del cambio, sobre geometria sintetica: dos valles
    paralelos separados 60 m, y sobre cada uno un eje con meandros de 6 m de
    amplitud y 40 m de longitud de onda. La equidistante de los VALLES es la
    recta central; la de los EJES ondula, y esa onda es la que aparecia en
    nuestras divisorias.

    Los dos ejes van con la MISMA fase, que es el caso que mas ondulacion
    produce y el que hay que evitar. Con fases opuestas la simetria cancela la
    onda y la equidistante vuelve a salir recta, asi que la magnitud real
    depende del desfase entre cauces vecinos: entre 0 y el doble de la
    amplitud. Ese es justo el problema, que la divisoria dependa de algo que no
    la deberia gobernar."""
    xs = [float(x) for x in range(10, 91)]
    valle_a = [(float(x), 0.0) for x in range(0, 101)]
    valle_b = [(float(x), 60.0) for x in range(0, 101)]
    onda = [6.0 * math.sin(2 * math.pi * x / 40.0) for x in range(0, 101)]
    eje_a = [(float(x), onda[x]) for x in range(0, 101)]
    eje_b = [(float(x), 60.0 + onda[x]) for x in range(0, 101)]

    y_valle = _equidistante(valle_a, valle_b, xs)
    y_eje = _equidistante(eje_a, eje_b, xs)

    amp_valle = max(y_valle) - min(y_valle)
    amp_eje = max(y_eje) - min(y_eje)
    assert amp_valle < 0.05          # la equidistante del valle es recta
    # medido: 6.28 m de pico a pico, la mitad de los 12 que dan los dos ejes,
    # porque la distancia a una senoide no es el desplazamiento vertical
    assert amp_eje > 4.0


# ------------------------------- B-046: no partir en confluencias ajenas
class _GeomFalsa:
    """Lo justo de QgsGeometry para `_separa`: distancia punto-polilinea."""

    def __init__(self, pts):
        self.pts = list(pts)

    @staticmethod
    def fromPointXY(p):
        return _GeomFalsa([(p[0], p[1])])

    def distance(self, otra):
        if len(self.pts) == 1 and len(otra.pts) > 1:
            return otra.distance(self)
        px, py = otra.pts[0]
        mejor = float("inf")
        for a, b in zip(self.pts[:-1], self.pts[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            dd = dx * dx + dy * dy
            t = 0.0 if dd < 1e-12 else max(0.0, min(1.0, ((px - a[0]) * dx + (py - a[1]) * dy) / dd))
            mejor = min(mejor, math.hypot(px - (a[0] + t * dx), py - (a[1] + t * dy)))
        return mejor


def _con_geoms_falsas(fn):
    """Sustituye QgsGeometry/QgsPointXY del modulo mientras dura la llamada."""
    g0, p0 = rg.QgsGeometry, rg.QgsPointXY
    rg.QgsGeometry, rg.QgsPointXY = _GeomFalsa, (lambda x, y: (x, y))
    try:
        return fn()
    finally:
        rg.QgsGeometry, rg.QgsPointXY = g0, p0


def _escenario():
    """Divisoria recta y tres cauces a distancias claramente distintas: en el
    vertice del corte los dos mas proximos son A (30 m) y B (45 m), y C esta a
    90. La confluencia de C con B cae a 38 m de la divisoria, que es el orden
    de magnitud del caso medido en el Ej_2 (33-38 m con `tol` de 50)."""
    dens = [(float(i) * 10.0, 0.0) for i in range(21)]      # divisoria, y = 0
    geoms = {"A": _GeomFalsa([(-50.0, 30.0), (250.0, 30.0)]),
             "B": _GeomFalsa([(-50.0, -45.0), (250.0, -45.0)]),
             "C": _GeomFalsa([(-50.0, -90.0), (250.0, -90.0)])}
    return dens, geoms


def test_separa_reconoce_la_pareja_que_la_divisoria_separa_de_verdad():
    """Los dos cauces mas proximos a un punto de una divisoria de Voronoi son,
    por definicion, las dos cuencas que ahi separa."""
    dens, geoms = _escenario()
    assert _con_geoms_falsas(
        lambda: rg._separa(dens, 10, frozenset(("A", "B")), geoms)) is True
    assert _con_geoms_falsas(
        lambda: rg._separa(dens, 10, frozenset(("C", "B")), geoms)) is False


def test_en_un_nudo_triple_no_se_puede_decir_que_separa():
    """B-050. Si el tercer cauce esta tan cerca como el segundo, «los dos que
    separa» es una moneda al aire. Medido en el Ej_2: el corte que quedaba caia
    en un punto a 42.61 / 42.76 / 42.78 m de tres cauces —dos centimetros entre
    el segundo y el tercero— y ahi partia la cadena por una confluencia que
    estaba a 49 m. El original no parte ninguna a mas de 20.1 m de la suya."""
    dens = [(float(i) * 10.0, 0.0) for i in range(21)]
    nudo = {"A": _GeomFalsa([(-50.0, 42.61), (250.0, 42.61)]),
            "B": _GeomFalsa([(-50.0, -42.76), (250.0, -42.76)]),
            "C": _GeomFalsa([(-50.0, -42.78), (250.0, -42.78)])}
    assert _con_geoms_falsas(
        lambda: rg._separa(dens, 10, frozenset(("A", "B")), nudo)) is False


def test_separa_deja_pasar_lo_que_no_puede_comprobar():
    """Sin ejes no hay comprobacion posible; y `pareja=None` es un cruce con un
    cauce, que parte siempre."""
    dens, geoms = _escenario()
    assert rg._separa(dens, 10, frozenset(("C", "B")), None) is True
    assert rg._separa(dens, 10, None, geoms) is True


def test_una_confluencia_ajena_ya_no_parte_la_cadena():
    """B-046, el cableado: la divisoria separa A|B y la confluencia es de C con
    B. Aunque caiga dentro de la tolerancia, no es suya y no la parte."""
    dens, geoms = _escenario()
    conf = [(100.0, -38.0, 55.0, frozenset(("C", "B")))]
    ramas = _con_geoms_falsas(
        lambda: rg._partir_en_confluencias(dens, conf, tol=50.0, geoms=geoms))
    assert len(ramas) == 1 and ramas[0][1] is None


def test_la_confluencia_propia_si_parte_la_cadena():
    """La misma geometria, con la pareja correcta."""
    dens, geoms = _escenario()
    conf = [(100.0, -38.0, 55.0, frozenset(("A", "B")))]
    ramas = _con_geoms_falsas(
        lambda: rg._partir_en_confluencias(dens, conf, tol=50.0, geoms=geoms))
    assert len(ramas) == 2
    assert [a[0] for _r, a in ramas] == ["fin", "ini"]


def test_un_cruce_con_un_cauce_parte_siempre():
    """`pareja = None` es lo que devuelve `cortes_con_cauces`: agua en medio,
    la divisoria se ha acabado, no hay nada que comprobar."""
    dens, geoms = _escenario()
    ramas = _con_geoms_falsas(
        lambda: rg._partir_en_confluencias(dens, [(100.0, 2.0, 55.0, None)],
                                           tol=50.0, geoms=geoms))
    assert len(ramas) == 2


def test_sin_geoms_se_comporta_como_antes():
    """Quien llame sin los ejes no puede comprobar nada, y no debe romperse."""
    dens, _geoms = _escenario()
    conf = [(100.0, -38.0, 55.0, frozenset(("C", "B")))]
    ramas = rg._partir_en_confluencias(dens, conf, tol=50.0)
    assert len(ramas) == 2


# --------------------- B-046: una divisoria llega al limite del proyecto
def _contorno(lado=1000.0):
    return _GeomFalsa([(0.0, 0.0), (lado, 0.0), (lado, lado), (0.0, lado),
                       (0.0, 0.0)])


def test_una_cadena_con_un_extremo_en_el_limite_es_divisoria():
    """Las 7 divisorias del original tienen un extremo a 0.00 m del limite y el
    otro a 70-135 m. Las cadenas nacen a 0.5 m porque `banda_limite` es
    `contorno.buffer(0.5)`."""
    rama = [(0.5, 500.0), (100.0, 500.0), (300.0, 500.0)]
    assert _con_geoms_falsas(lambda: rg.toca_el_limite(rama, _contorno())) is True
    assert _con_geoms_falsas(
        lambda: rg.toca_el_limite(rama[::-1], _contorno())) is True


def test_una_cadena_interior_por_los_dos_extremos_no_lo_es():
    """El brazo sobrante de un nudo triple: `encadenar_arcos` cose la pareja mas
    enfrentada y deja el tercero suelto, con los DOS extremos dentro."""
    rama = [(300.0, 400.0), (350.0, 450.0), (400.0, 500.0)]
    assert _con_geoms_falsas(lambda: rg.toca_el_limite(rama, _contorno())) is False


def test_el_criterio_no_es_de_longitud():
    """La divisoria legitima mas corta del original mide 25.0 m, asi que un
    umbral que matara los brazos de 40 m mataria divisorias buenas."""
    corta = [(0.5, 500.0), (12.0, 505.0), (25.0, 510.0)]      # 25 m, al limite
    larga = [(300.0, 300.0), (400.0, 400.0), (500.0, 500.0)]  # 283 m, interior
    assert _con_geoms_falsas(lambda: rg.toca_el_limite(corta, _contorno())) is True
    assert _con_geoms_falsas(lambda: rg.toca_el_limite(larga, _contorno())) is False


# ------------------------------------------------------------ invariante
def test_los_ejes_siguen_siendo_la_referencia_de_distancia_de_ladera():
    """La particion cambia de fuente, pero la DISTANCIA cauce-divisoria que
    gobierna la cota de ladera se mide al agua de verdad, no a la linea de
    valle. Si alguien 'simetriza' _geoms_ejes por analogia con la particion,
    el desnivel de ladera se calcula contra una linea por la que no corre el
    agua. Esta prueba existe para que ese cambio rompa algo."""
    fuente = open(_ruta, encoding="utf-8").read()
    i = fuente.index("def _geoms_ejes(")
    cuerpo = fuente[i:i + 400]
    assert "d.puntos" in cuerpo
    assert "d.dens" not in cuerpo
