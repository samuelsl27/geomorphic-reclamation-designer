# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas de la ecuacion del perfil de ladera y de la cota de cresta
(core/ridges.py).

Lo que se prueba aqui es la CONSISTENCIA entre las dos: la cota que se le pone
a la cresta tiene que ser exactamente la que produce el perfil que luego se
dibuja. Hasta la v1.0.18 no lo era —el docstring del modulo decia
Dz = (2/3)*s_max*D y el codigo usaba 0.5*s_max*D—, que es el patron de B-016
(documentacion que contradice al codigo) aplicado a una constante del metodo.

Se ejecuta el modulo REAL con QGIS simulado, en vez de copiar las funciones al
test: una copia vuelve a desincronizarse, que es justo el fallo que se corrige.
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

# params.py no importa QGIS, asi que se carga el de verdad: la definicion de
# "ladera norte o este" tiene que ser LA MISMA en el motor y en las
# comprobaciones. Se registra aqui y no se da por hecho que ya este: un test
# que solo pasa segun el orden en que se ejecuten los ficheros es una trampa.
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
rg = types.ModuleType("grd_ridges")
exec(compile(_src, _ruta, "exec"), rg.__dict__)


class _Ajustes:
    """Lo minimo de GlobalSettings que mira convexo_subcresta."""

    def __init__(self, modo="factor", pct=20.0, dist=25.0):
        self.convexo_modo = modo
        self.convexo_pct = pct
        self.max_dist_cresta_cabecera = dist


def pendiente_maxima(D, dz, lc, n=400):
    """Peor pendiente local del perfil trapezoidal, muestreado fino."""
    paso = D / n
    peor = 0.0
    for i in range(n):
        a = rg.perfil_trapezoidal(i * paso, D, dz, lc)
        b = rg.perfil_trapezoidal((i + 1) * paso, D, dz, lc)
        peor = max(peor, abs(b - a) / paso)
    return peor


# ------------------------------------------------- la relacion que se despeja
def test_el_desnivel_agota_la_pendiente_maxima_sin_superarla():
    """`desnivel_de_ladera` se despeja igualando la pendiente del tramo recto
    de `perfil_trapezoidal` a s_max. Si las dos ecuaciones estan sincronizadas,
    el perfil resultante toca s_max y no lo pasa."""
    s_max = 0.33
    for D in (20.0, 40.0, 60.0, 100.0, 150.0, 240.0):
        for lc in (12.0, 24.0, 36.0, 75.0):
            dz = rg.desnivel_de_ladera(D, s_max, lc)
            peor = pendiente_maxima(D, dz, lc)
            assert peor <= s_max + 1e-6, (D, lc, peor)
            assert peor > s_max - 0.02, (D, lc, peor)


def test_el_desnivel_no_es_un_multiplo_fijo_de_smax_por_D():
    """El factor depende de cuanta ladera se lleven los tramos curvos:
    0.55 con lc y lf saturados en sus topes (0.6*D y 0.3*D), 2/3 con
    lc = 0.3667*D, y tiende a 1 con una cabeza convexa pequena (ladera recta).
    Nunca 0.5, que es lo que hacia el codigo hasta la v1.0.18.

    Esta prueba existe porque al escribirla se descubrio que el rango que se
    habia supuesto (0.55 a 2/3) era falso: con lc = 12 m en una ladera de 60 m
    el factor es 0.80. Cualquier constante vale para un caso y falla en otro,
    que es exactamente por que hay que despejarlo."""
    s_max = 0.33
    for D in (30.0, 60.0, 100.0, 200.0):
        for lc in (12.0, 24.0, 36.0, 75.0):
            f = rg.desnivel_de_ladera(D, s_max, lc) / (s_max * D)
            assert 0.549 <= f < 1.0, (D, lc, f)
    # los dos extremos analiticos
    assert abs(rg.desnivel_de_ladera(100.0, s_max, 500.0)
               / (s_max * 100.0) - 0.55) < 1e-9        # lc y lf saturados
    # lc + lf = 2D/3 con lf saturado en 0.3*D  =>  lc = 0.36667*D
    assert abs(rg.desnivel_de_ladera(90.0, s_max, 33.0)
               / (s_max * 90.0) - 2.0 / 3.0) < 1e-9


def test_el_desnivel_crece_con_la_distancia_al_canal():
    s_max = 0.33
    v = [rg.desnivel_de_ladera(D, s_max, 36.0) for D in range(10, 200, 10)]
    assert v == sorted(v)
    assert all(b > a for a, b in zip(v[:-1], v[1:]))


def test_una_ladera_sin_longitud_no_tiene_desnivel():
    assert rg.desnivel_de_ladera(0.0, 0.33, 24.0) == 0.0
    assert rg.desnivel_de_ladera(-5.0, 0.33, 24.0) == 0.0


# ------------------------------------------------------------- tramos acotados
def test_los_tramos_se_acotan_y_dejan_sitio_al_tramo_recto():
    for D in (5.0, 20.0, 60.0, 200.0):
        lc, lf = rg.tramos_de_ladera(D, 500.0)      # lc absurdo a proposito
        assert 0.5 <= lc <= 0.6 * D + 1e-9
        assert lf >= 0.5
        assert lc + lf <= 0.9 * D + 1e-9
        assert D - lc / 2.0 - lf / 2.0 > 0


def test_perfil_trapezoidal_y_tramos_usan_el_mismo_acotado():
    """Si `perfil_trapezoidal` acotara distinto que `tramos_de_ladera`, la cota
    de cresta y el perfil dibujado volverian a discrepar."""
    D, dz, lc = 60.0, 12.0, 75.0
    lc_ac, lf_ac = rg.tramos_de_ladera(D, lc)
    s_m = dz / (D - lc_ac / 2.0 - lf_ac / 2.0)
    # en el tramo central la pendiente vale exactamente s_m
    x = (lc_ac + (D - lf_ac)) / 2.0
    h = 0.01
    local = (rg.perfil_trapezoidal(x + h, D, dz, lc)
             - rg.perfil_trapezoidal(x - h, D, dz, lc)) / (2 * h)
    assert abs(local - s_m) < 1e-6


# ------------------------------------------------------- forma del perfil
def test_el_perfil_arranca_y_acaba_tendido():
    """Cabeza convexa junto a la cresta y pie concavo junto al canal: la
    pendiente maxima esta en el interior, no en los extremos."""
    D, lc = 100.0, 25.0
    dz = rg.desnivel_de_ladera(D, 0.33, lc)
    h = 0.05
    p_ini = (rg.perfil_trapezoidal(h, D, dz, lc)
             - rg.perfil_trapezoidal(0.0, D, dz, lc)) / h
    p_fin = (rg.perfil_trapezoidal(D, D, dz, lc)
             - rg.perfil_trapezoidal(D - h, D, dz, lc)) / h
    assert p_ini < pendiente_maxima(D, dz, lc)
    assert p_fin < pendiente_maxima(D, dz, lc)


def test_el_perfil_reparte_todo_el_desnivel():
    D, lc, dz = 80.0, 30.0, 20.0
    assert abs(rg.perfil_trapezoidal(0.0, D, dz, lc)) < 1e-9
    assert abs(rg.perfil_trapezoidal(D, D, dz, lc) - dz) < 1e-6


def test_un_desnivel_negativo_no_rompe_la_ecuacion():
    """Una linea que DESCIENDE hacia su empalme: dz negativo."""
    D, lc, dz = 80.0, 30.0, -15.0
    assert abs(rg.perfil_trapezoidal(D, D, dz, lc) - dz) < 1e-6


# ------------------------------------------------------ porcion convexa
def test_convexo_por_factor_y_por_porcentaje():
    """Modo 'factor' = 1.5 x la distancia cresta-cabecera; modo 'pct' = % de
    la longitud de la ladera."""
    g = _Ajustes(modo="factor", dist=25.0)
    assert rg.convexo_subcresta(g, None, 100.0) == 1.5 * 25.0
    g = _Ajustes(modo="pct", pct=20.0)
    assert rg.convexo_subcresta(g, None, 100.0) == 20.0


# ------------------------------------------------- orientacion de la ladera
class _AjustesNE:
    """Los del proyecto original del Ej_2: 33 % general, 22 % al norte/este."""
    convexo_modo = "factor"
    convexo_pct = 20.0
    max_dist_cresta_cabecera = 50.0
    pendiente_max_pct = 33.0
    pendiente_NE_pct = 22.0


def test_el_rumbo_es_el_de_DESCENSO_no_el_del_orden_de_los_vertices():
    """Las subcrestas y las vaguadas se trazan del cauce hacia arriba, asi que
    su primer vertice es el PIE. Tomar el rumbo de pts[0] a pts[-1] daba la
    direccion contraria y clasificaba como norte lo que mira al sur."""
    par = sys.modules["gfq_params"]
    # cresta al norte (y=100, alta), pie al sur (y=0, bajo): mira al SUR
    del_pie_a_la_cresta = [(0.0, 0.0, 100.0), (0.0, 100.0, 130.0)]
    assert abs(par.rumbo_de_ladera(del_pie_a_la_cresta) - 180.0) < 1e-9
    # la misma ladera guardada al reves tiene que dar el MISMO rumbo
    assert abs(par.rumbo_de_ladera(list(reversed(del_pie_a_la_cresta)))
               - 180.0) < 1e-9
    assert not par.es_orientacion_NE(180.0)


def test_una_ladera_al_norte_usa_la_pendiente_NE():
    """'North or East straight-line slopes' (m_fNESlope en el original) es un
    objetivo de DISENO, no solo una comprobacion: hasta la v1.0.18 el motor
    trazaba todas las laderas con la pendiente general (P-09)."""
    par = sys.modules["gfq_params"]
    g = _AjustesNE()
    # pie al norte (y=100), cresta al sur (y=0): la ladera mira al NORTE
    al_norte = par.rumbo_de_ladera([(0.0, 0.0, 130.0), (0.0, 100.0, 100.0)])
    assert abs(al_norte - 0.0) < 1e-9
    assert par.es_orientacion_NE(al_norte)
    assert abs(par.pendiente_max_ladera(g, al_norte) - 0.22) < 1e-12
    al_sur = par.rumbo_de_ladera([(0.0, 100.0, 130.0), (0.0, 0.0, 100.0)])
    assert abs(par.pendiente_max_ladera(g, al_sur) - 0.33) < 1e-12


def test_la_cresta_de_una_ladera_al_norte_queda_mas_baja():
    """Consecuencia geometrica: con 22 % en vez de 33 %, la misma ladera
    corona un tercio mas abajo."""
    g = _AjustesNE()
    par = sys.modules["gfq_params"]
    lc = rg.convexo_subcresta(g, None, 60.0)
    dz_general = rg.desnivel_de_ladera(60.0, par.pendiente_max_ladera(g, 200.0), lc)
    dz_ne = rg.desnivel_de_ladera(60.0, par.pendiente_max_ladera(g, 45.0), lc)
    assert dz_ne < dz_general
    assert abs(dz_ne / dz_general - 22.0 / 33.0) < 1e-9


def test_una_ladera_sin_rumbo_no_se_clasifica_como_NE():
    par = sys.modules["gfq_params"]
    assert par.rumbo_de_ladera([(0.0, 0.0, 10.0), (0.0, 0.0, 5.0)]) is None
    assert not par.es_orientacion_NE(None)
    assert abs(par.pendiente_max_ladera(_AjustesNE(), None) - 0.33) < 1e-12


# ================================================ perfil de la cresta divisoria
# `_perfil_cresta` invierte su copia de los puntos cuando el perfil viene al
# reves. Para poder ejecutarlo de verdad hace falta un poco mas de QGIS que la
# clase vacia del doble global: se inyectan geometrias falsas con la distancia
# euclidea, que es lo unico que la funcion usa.
class _PtXY:
    """Doble FIEL de QgsPointXY. Comprobado contra QGIS 3.44:

        p[0], p[1]  -> float          len(p) -> 2
        x, y = p    -> OK             math.dist(p, q) -> OK
        p[-1]       -> IndexError
        p[:2]       -> TypeError ('slice')

    Lo que este doble tenia de menos —el acceso por indice— es justo lo que hizo
    que B-044 pasara desapercibido: un doble MAS PERMISIVO que el objeto real no
    prueba nada, y uno mas restrictivo tampoco, porque nadie le pasa puntos.
    """

    def __init__(self, x, y):
        self._x, self._y = float(x), float(y)

    def x(self):
        return self._x

    def y(self):
        return self._y

    def __len__(self):
        return 2

    def __getitem__(self, i):
        if isinstance(i, slice):
            raise TypeError("QgsPointXY.__getitem__(): argument 1 has "
                            "unexpected type 'slice'")
        if i not in (0, 1):
            raise IndexError("Bad index: %s" % i)
        return self._x if i == 0 else self._y


class _Pt3(_PtXY):
    def __init__(self, x, y, z=0.0):
        _PtXY.__init__(self, x, y)
        self._z = float(z)

    def z(self):
        return self._z


def _dist_pt_seg(p, a, b):
    import math
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


class _Geom:
    """Punto o polilinea 2D con `distance()`; es todo lo que se usa aqui."""

    def __init__(self, pts):
        self.pts = [(p.x(), p.y()) if hasattr(p, "x") else (p[0], p[1])
                    for p in pts]

    @staticmethod
    def fromPointXY(p):
        return _Geom([p])

    @staticmethod
    def fromPolylineXY(ps):
        return _Geom(ps)

    @staticmethod
    def fromPolyline(ps):
        return _Geom(ps)

    def distance(self, otra):
        mejor = float("inf")
        for p in otra.pts:
            if len(self.pts) == 1:
                import math
                mejor = min(mejor, math.dist(p, self.pts[0]))
            for a, b in zip(self.pts[:-1], self.pts[1:]):
                mejor = min(mejor, _dist_pt_seg(p, a, b))
        return mejor


class _Canal:
    """Eje que sube de oeste a este: z crece con x."""

    def __init__(self):
        self.puntos = [(float(i) * 5.0, 0.0, 200.0 + i * 2.0, float(i) * 5.0)
                       for i in range(41)]          # 0..200 m, z 200..280


class _AjustesCresta(_AjustesNE):
    pass


def _monta_qgis_falso():
    rg.QgsGeometry = _Geom
    rg.QgsPointXY = _PtXY
    rg.QgsPoint = _Pt3


def test_la_traza_y_las_cotas_salen_del_MISMO_objeto():
    """B-028. `_perfil_cresta` hace `dens = dens[::-1]` cuando el perfil viene
    al reves, y esa reasignacion es LOCAL: no toca la lista del llamante. Asi
    que `zs` puede quedar en orden inverso al de los puntos que le pasaste.

    `generar_crestas` emparejaba `zs` con esos puntos (`rama`) y le daba a la
    mitad de las divisorias LAS COTAS DEL REVES. Las laderas que toman de ahi
    su cota de coronacion (`hillslopes._trazar_ladera`, radio 24 m) heredaban
    la del OTRO extremo de la divisoria.

    La cura no es acordarse de emparejar bien: es que solo haya UNA fuente.
    `traza_y_cotas` deriva las dos cosas de la misma polilinea 3D.
    """
    _monta_qgis_falso()
    disenos = {"main": _Canal()}
    geoms = {"main": _Geom([(x, y) for x, y, _z, _s in disenos["main"].puntos])}
    contorno = _Geom([(-500.0, -500.0), (500.0, -500.0),
                      (500.0, 500.0), (-500.0, 500.0), (-500.0, -500.0)])
    # divisoria paralela al cauce, a 50 m: su extremo ESTE es el mas alto,
    # asi que `_perfil_cresta` tiene que invertir (zB > zA)
    rama = [(float(i) * 10.0, 50.0) for i in range(16)]     # x 0..150, y 50

    linea, zs, _diag = rg._perfil_cresta(rama, disenos, geoms, 0.33, None,
                                  _AjustesCresta(), contorno)

    # el caso discrimina: ha invertido y las dos cotas extremas son distintas
    assert abs(linea[0].x() - rama[-1][0]) < 1e-9, "no ha invertido: revisa el caso"
    assert abs(zs[0] - zs[-1]) > 1.0, "el caso no discrimina: cotas casi iguales"

    geom, cotas = rg.traza_y_cotas(linea)
    assert len(geom.pts) == len(cotas) == len(linea)
    for i, (xy, z) in enumerate(zip(geom.pts, cotas)):
        assert abs(xy[0] - linea[i].x()) < 1e-9
        assert abs(z - linea[i].z()) < 1e-9, (i, z, linea[i].z())
    # la traza empieza donde empieza `linea`, NO donde empezaba `rama`
    assert abs(geom.pts[0][0] - rama[-1][0]) < 1e-9
    # y por tanto la cota del primer punto es la del extremo ALTO
    assert cotas[0] == max(cotas)


def test_el_perfil_de_cresta_desciende_de_un_extremo_al_otro():
    _monta_qgis_falso()
    disenos = {"main": _Canal()}
    geoms = {"main": _Geom([(x, y) for x, y, _z, _s in disenos["main"].puntos])}
    contorno = _Geom([(-500.0, -500.0), (500.0, -500.0),
                      (500.0, 500.0), (-500.0, 500.0), (-500.0, -500.0)])
    dens = [(float(i) * 10.0, 50.0) for i in range(16)]
    _linea, zs, _diag = rg._perfil_cresta(dens, disenos, geoms, 0.33, None,
                                   _AjustesCresta(), contorno)
    assert zs[0] > zs[-1], zs          # orientada de ALTO a bajo


# =========================== longitud convexa de vaguada y de subcresta
class _AjustesXC:
    """Los ajustes del Ej_2: xrh = 50 m, vaguada por canal 24 m."""
    convexo_modo = "factor"
    convexo_pct = 20.0
    max_dist_cresta_cabecera = 50.0
    convexo_swale_activo = False
    convexo_swale_m = 12.0
    pendiente_max_pct = 33.0
    pendiente_NE_pct = 22.0


class _Canal24:
    dist_cresta_swale_m = 24.0
    especificar_convexo = False
    convexo_modo_canal = "factor"
    convexo_pct_canal = 20.0


def test_la_longitud_convexa_de_la_vaguada_es_el_ajuste_de_cabecera():
    """[LIBRO p. 191] 'maximum distance from ridgeline to swale head — option 1
    — SPECIFY SWALE CONVEX LENGTH based on reference area observations'.

    Es una longitud convexa, no un retranqueo. Hasta la v1.0.19 se usaba para
    AMPUTAR 24 m del final de cada vaguada (B-032)."""
    g = _AjustesXC()
    assert rg.convexo_vaguada(g, _Canal24()) == 24.0
    # sin canal: la casilla global, si esta marcada
    g.convexo_swale_activo = True
    assert rg.convexo_vaguada(g, None) == 12.0
    # y si no, xc ~ xrh [LIBRO p. 236]
    g.convexo_swale_activo = False
    assert rg.convexo_vaguada(g, None) == 50.0


def test_la_subcresta_tiene_el_tramo_convexo_MAS_LARGO_que_la_vaguada():
    """[LIBRO p. 191] 'maximum convex length of a sub-ridge – 1.5 x ...'.
    De esa diferencia sale la depresion, asi que el orden importa."""
    g = _AjustesXC()
    c = _Canal24()
    assert rg.convexo_subcresta(g, c, 70.0) > rg.convexo_vaguada(g, c)


def test_la_vaguada_queda_por_DEBAJO_de_la_subcresta_con_los_mismos_extremos():
    """[LIBRO fig. 8-11, p. 204] 'A depression is formed by the SHORTER SWALE
    CONVEX LENGTH between the LONGER ADJACENT SUB-RIDGE CONVEX LENGTHS and
    runoff water is directed into the swale bottom.'

    La depresion NO se hace acortando la vaguada ni bajandole la cabecera: con
    el MISMO desnivel y los MISMOS dos extremos, el perfil de menor longitud
    convexa cae mas deprisa y queda por debajo en todo el interior."""
    g, c = _AjustesXC(), _Canal24()
    D, s_max = 70.0, 0.33
    lc_s = rg.convexo_subcresta(g, c, D)
    lc_v = rg.convexo_vaguada(g, c)
    dz = rg.desnivel_de_ladera(D, s_max, lc_s)      # la cota la fija el FILO
    for x in range(1, int(D)):
        caida_s = rg.perfil_trapezoidal(x, D, dz, lc_s)
        caida_v = rg.perfil_trapezoidal(x, D, dz, lc_v)
        assert caida_v >= caida_s - 1e-9, (x, caida_v, caida_s)
    # y estrictamente por debajo a media ladera
    x = D / 2.0
    assert (rg.perfil_trapezoidal(x, D, dz, lc_v)
            - rg.perfil_trapezoidal(x, D, dz, lc_s)) > 0.5
    # los dos extremos, en cambio, coinciden: las dos mueren en la divisoria
    assert abs(rg.perfil_trapezoidal(0.0, D, dz, lc_v)
               - rg.perfil_trapezoidal(0.0, D, dz, lc_s)) < 1e-9
    assert abs(rg.perfil_trapezoidal(D, D, dz, lc_v)
               - rg.perfil_trapezoidal(D, D, dz, lc_s)) < 1e-6


def test_la_cota_de_coronacion_la_fija_la_SUBCRESTA_no_quien_pregunta():
    """Si cada linea usara su propia longitud convexa, la vaguada pediria una
    cota MAS ALTA que la subcresta vecina: `dz = s_max*(D - lc/2 - lf/2)` crece
    al menguar `lc`. Medido con los ajustes del Ej_2 y D = 70 m: subcresta
    12.71 m, vaguada 15.68 m. Por eso `_z_ladera` calcula la longitud convexa
    por su cuenta, con `convexo_subcresta`, y ya no acepta la de la linea."""
    g, c = _AjustesXC(), _Canal24()
    D, s_max = 70.0, 0.33
    dz_sub = rg.desnivel_de_ladera(D, s_max, rg.convexo_subcresta(g, c, D))
    dz_vag = rg.desnivel_de_ladera(D, s_max, rg.convexo_vaguada(g, c))
    assert dz_vag > dz_sub, (dz_vag, dz_sub)     # la trampa que se evita


# ------------------------------------ el TECHO de ladera (v1.0.22, fase 1)
def test_proyectar_en_eje_interpola_la_cota():
    """Antes se tomaba el vertice mas proximo muestreando uno de cada dos: la
    distancia salia exacta y la cota no, que son dos criterios distintos sobre
    el mismo punto y una fuente de escalones de por si."""
    eje = [(0.0, 0.0, 100.0), (10.0, 0.0, 110.0)]
    d, z = rg.proyectar_en_eje(eje, 3.0, 4.0)
    assert abs(d - 4.0) < 1e-9
    assert abs(z - 103.0) < 1e-9


def test_el_techo_manda_el_lado_mas_restrictivo():
    """`min`, no `max`: la cresta tiene que cumplir la pendiente por LOS DOS
    lados, asi que la ata el lado que menos permite."""
    lados = [(100.0, 200.0, 0.33, 30.0), (100.0, 180.0, 0.33, 30.0)]
    t = rg.techo_de_ladera(lados)
    assert abs(t - (180.0 + rg.desnivel_de_ladera(100.0, 0.33, 30.0))) < 1e-9
    assert rg.techo_de_ladera([]) is None


def test_el_techo_es_CONTINUO_donde_se_alterna_el_canal_mas_proximo():
    """El corazon de la fase 1. Sobre una divisoria equidistante, «el canal mas
    proximo» cambia por milimetros y con el saltaba la cota de referencia: 21.2 %
    de los pasos en el Ej_2, con saltos de hasta 29.96 m. El `min` de dos
    funciones continuas es continuo, asi que el salto desaparece por
    construccion."""
    zA, zB, lc, s = 200.0, 230.0, 30.0, 0.33

    def techo(d_a):                       # el punto se desplaza de A hacia B
        return rg.techo_de_ladera([(d_a, zA, s, lc), (200.0 - d_a, zB, s, lc)])

    def solo_el_mas_proximo(d_a):
        D, z = ((d_a, zA) if d_a <= 200.0 - d_a else (200.0 - d_a, zB))
        return z + max(rg.desnivel_de_ladera(D, s, lc), 0.25)

    # justo a los dos lados de la equidistancia (d_a = 100)
    salto_nuevo = abs(techo(100.5) - techo(99.5))
    salto_viejo = abs(solo_el_mas_proximo(100.5) - solo_el_mas_proximo(99.5))
    # el techo nuevo cambia a la VELOCIDAD SUAVE de la propia ladera, s por
    # metro recorrido: eso es continuidad, no un salto
    assert abs(salto_nuevo - s * 1.0) < 0.05, salto_nuevo
    # el viejo salta la diferencia de cota entre los dos lechos, de golpe
    assert salto_viejo > 25.0, salto_viejo
    assert salto_viejo > 50 * salto_nuevo


# =============== el perfil de la divisoria es UNA curva (v1.0.22, fase 2)
def test_el_perfil_es_lineal_en_el_desnivel():
    """Es lo que permite despejar el extremo libre en FORMA CERRADA, sin
    iterar: `perfil_trapezoidal(x, L, dz, lc) / dz` no depende de dz."""
    L, lc = 346.0, 75.0
    for x in (0.0, 12.0, 87.0, 173.0, 300.0, 346.0):
        base = rg.perfil_trapezoidal(x, L, 1.0, lc)
        for dz in (1.0, 5.0, 20.0, -13.0):
            assert abs(rg.perfil_trapezoidal(x, L, dz, lc) - dz * base) < 1e-9


def test_el_extremo_libre_se_resuelve_para_no_rebasar_el_techo():
    L, lc = 300.0, 60.0
    s = [L * k / 60.0 for k in range(61)]
    f = [rg.perfil_trapezoidal(x, L, 1.0, lc) for x in s]
    z_bajo = 100.0
    # techo IRREGULAR a proposito, con un diente de 30 m en medio
    techo = [160.0 + 0.05 * x for x in s]
    techo[30] = 118.0
    z_alto = rg.resolver_extremo_libre(f, techo, z_bajo, libre_es_alto=True)
    zs = [z_alto * (1.0 - fk) + z_bajo * fk for fk in f]
    for z, t in zip(zs, techo):
        assert z <= t + 1e-6, (z, t)
    # y toca el techo en algun punto: no se queda corta por si acaso
    assert min(t - z for z, t in zip(zs, techo)) < 1e-6


def test_un_diente_de_30_m_en_el_techo_no_escribe_un_escalon():
    """La prueba que fija la doctrina nueva. Antes el techo era un SUELO
    aplicado vertice a vertice y REIMPUESTO despues de suavizar, asi que cada
    salto de la envolvente quedaba clavado en el perfil. Ahora el techo entra
    por un `min` sobre la linea entera, y un salto en el techo no puede
    escribir un salto en la cresta."""
    L, lc = 300.0, 60.0
    s = [L * k / 60.0 for k in range(61)]
    f = [rg.perfil_trapezoidal(x, L, 1.0, lc) for x in s]
    techo = [160.0 + 0.05 * x for x in s]
    techo[30] = 118.0                       # diente de 30 m
    z_alto = rg.resolver_extremo_libre(f, techo, 100.0, libre_es_alto=True)
    zs = [z_alto * (1.0 - fk) + 100.0 * fk for fk in f]
    saltos = [abs(zs[i + 1] - zs[i]) for i in range(len(zs) - 1)]
    assert max(saltos) < 1.0, max(saltos)
    # y el perfil sigue siendo MONOTONO: vaiven exactamente cero
    sube = sum(max(0.0, zs[i + 1] - zs[i]) for i in range(len(zs) - 1))
    baja = sum(max(0.0, zs[i] - zs[i + 1]) for i in range(len(zs) - 1))
    assert abs(sube + baja - abs(zs[0] - zs[-1])) < 1e-9


def test_el_suelo_de_cresta_es_el_lecho_mas_alto():
    lados = [(80.0, 200.0, 0.33, 30.0), (60.0, 213.0, 0.33, 30.0)]
    assert abs(rg.suelo_de_cresta(lados, 0.25) - 213.25) < 1e-9
    assert rg.suelo_de_cresta([]) is None


# =============== el gancho de la confluencia (v1.0.22, fase 4)
def test_la_confluencia_no_se_inserta_en_la_planta():
    """P-27. Se sustituia el vertice de MINIMA DISTANCIA por el punto de
    confluencia; como ese vertice es el pie de la perpendicular, el segmento
    nuevo salia perpendicular a la traza y podia medir hasta `tol`. Ahora la
    cadena se PARTE ahi —que es lo que da las dos crestas de ADR-003— y la
    confluencia se conserva solo como ancla de cota."""
    dens = [(float(i) * 10.0, 0.0) for i in range(21)]      # recta de 200 m
    # ancla = (x, y, z, pareja); `pareja=None` = sin comprobacion de cauces
    conf = [(100.0, 40.0, 55.0, None)]                      # a 40 m DE LADO
    ramas = rg._partir_en_confluencias(dens, conf, tol=50.0)
    assert len(ramas) == 2, ramas
    for rama, anclaje in ramas:
        assert anclaje is not None and abs(anclaje[1] - 55.0) < 1e-9
        # ni un solo vertice fuera de la recta original: no se ha metido el
        # punto de confluencia, que esta a y = 40
        assert all(abs(y) < 1e-9 for _x, y in rama), rama


def test_las_dos_ramas_siguen_saliendo_de_la_confluencia():
    """ADR-003 intacto: lo que da las DOS crestas es el corte, no el punto."""
    dens = [(float(i) * 10.0, 0.0) for i in range(21)]
    ramas = rg._partir_en_confluencias(dens, [(100.0, 2.0, 55.0, None)],
                                       tol=50.0)
    assert [a[0] for _r, a in ramas] == ["fin", "ini"]
    # y las dos comparten el vertice del corte
    assert ramas[0][0][-1] == ramas[1][0][0]


# ============ el extremo libre no lo tumba un punto del pie (v1.0.23, B-038)
def _caso_divisoria_que_muere_en_confluencia(n=40, L=120.0, lc=60.0):
    """Un extremo anclado ABAJO (la confluencia) y otro libre. El techo es bajo
    junto al anclado —ahi la distancia al cauce tiende a cero— y alto en el
    resto. Es el caso real de la fid=1 del Ej_2."""
    s = [L * k / (n - 1) for k in range(n)]
    f = [rg.perfil_trapezoidal(x, L, 1.0, lc) for x in s]   # 0 en el libre
    z_anc = 280.0
    # El extremo ANCLADO esta en x = L (f = 1), muriendo en la confluencia:
    # alli la distancia al cauce tiende a cero, asi que el techo tiende al
    # PROPIO anclaje. El LIBRE esta en x = 0, lejos del cauce, y alli el techo
    # permite subir de sobra. Es la geometria de la fid=1 del Ej_2.
    techo = [max(z_anc + 0.05, 316.0 - 0.30 * x) if x < 0.85 * L
             else z_anc + 0.05 for x in s]
    suelo = [z_anc - 0.20] * len(s)
    return f, techo, suelo, z_anc


def test_el_extremo_libre_no_lo_tumba_un_punto_del_pie():
    """B-038. `resolver_extremo_libre` tomaba el `min` sobre TODA la linea, y
    junto al extremo anclado el peso (1-f) tiende a cero: un solo punto de ahi
    convertia la divisoria en una linea tumbada. Medido en el Ej_2: siete de
    trece con menos de 7 m de desnivel, una con 2.4 m en 117 m."""
    f, techo, suelo, z_anc = _caso_divisoria_que_muere_en_confluencia()
    z_lib = rg.resolver_extremo_libre(f, techo, z_anc, True, suelo=suelo)
    assert z_lib is not None
    assert z_lib - z_anc > 8.0, "la divisoria sale tumbada: %.2f m" % (z_lib - z_anc)

    # sin la guarda (peso_min = 0) se reproduce el defecto
    z_malo = rg.resolver_extremo_libre(f, techo, z_anc, True, suelo=suelo,
                                       peso_min=0.0)
    assert z_malo - z_anc < z_lib - z_anc


def test_el_suelo_tambien_acota_el_extremo_libre_pero_sin_dispararlo():
    """El suelo manda sobre el techo —una divisoria bajo el lecho es un error
    duro y quedarse corto de pendiente solo es un objetivo incumplido— pero con
    la misma guarda de amplificacion: sin ella, dos divisorias del Ej_2 se
    disparaban a 240 y 100 m de desnivel."""
    f, techo, _su, z_anc = _caso_divisoria_que_muere_en_confluencia()
    suelo_alto = [z_anc + 40.0] * len(f)          # un suelo exigente
    z = rg.resolver_extremo_libre(f, techo, z_anc, True, suelo=suelo_alto)
    assert z >= z_anc + 40.0 - 1e-6, "el suelo tiene que mandar sobre el techo"
    # y la amplificacion queda acotada: con peso_min = 0.5, a lo sumo x2
    assert z - z_anc < 2.0 * 40.0 + 1e-6


def test_ni_el_techo_ni_el_suelo_se_aplican_punto_a_punto():
    """El suelo se aplicaba con `max(z, suelo)` vertice a vertice, y `suelo` NO
    es continuo: es `max` sobre los dos cauces mas proximos, y esa pareja cambia
    de miembros. Escribia saltos de hasta 15.80 m y mandaba en el 40.9 % de los
    vertices del Ej_2.

    Se comprueba por el COMPORTAMIENTO: con un suelo escalonado, la curva que
    sale no puede tener ese escalon."""
    f, techo, _su, z_anc = _caso_divisoria_que_muere_en_confluencia()
    z_lib = rg.resolver_extremo_libre(f, techo, z_anc, True)
    zs = [z_lib * (1.0 - fk) + z_anc * fk for fk in f]
    saltos = [abs(zs[i + 1] - zs[i]) for i in range(len(zs) - 1)]
    assert max(saltos) < 2.0, max(saltos)


# ================= encadenar la red de divisorias (v1.0.24, B-040)
def test_encadenar_cose_dos_arcos_que_comparten_extremo():
    a = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
    b = [(20.0, 0.0), (30.0, 0.0), (40.0, 0.0)]
    cad = rg.encadenar_arcos([a, b])
    assert len(cad) == 1
    assert cad[0][0] == (0.0, 0.0) and cad[0][-1] == (40.0, 0.0)
    assert len(cad[0]) == 5, cad[0]        # el vertice compartido no se duplica


def test_encadenar_respeta_el_sentido_de_cada_arco():
    """Un arco puede venir al reves; encadenar tiene que invertirlo, no unir
    cabeza con cabeza."""
    a = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
    b = [(40.0, 0.0), (30.0, 0.0), (20.0, 0.0)]     # llega al nudo por su FINAL
    cad = rg.encadenar_arcos([a, b])
    assert len(cad) == 1
    xs = [p[0] for p in cad[0]]
    assert xs == sorted(xs) or xs == sorted(xs, reverse=True), xs


def test_en_un_nudo_TRIPLE_continua_la_pareja_mas_enfrentada():
    """Es el caso real: tres subcuencas que se tocan en un vertice de Voronoi
    dan tres arcos. Sigue la pareja que menos gira —una divisoria no gira 120
    grados en un nudo— y el tercero queda como cadena aparte."""
    izq = [(-40.0, 0.0), (-20.0, 0.0), (0.0, 0.0)]        # llega por el este
    der = [(0.0, 0.0), (20.0, 0.0), (40.0, 0.0)]          # sigue al este: recto
    ramal = [(0.0, 0.0), (10.0, 20.0), (20.0, 40.0)]      # se va a 63 grados
    cad = rg.encadenar_arcos([izq, der, ramal])
    assert len(cad) == 2, [len(c) for c in cad]
    larga = max(cad, key=len)
    assert (-40.0, 0.0) in larga and (40.0, 0.0) in larga, larga
    assert (20.0, 40.0) not in larga


def test_encadenar_no_se_cuelga_con_un_ciclo():
    a = [(0.0, 0.0), (10.0, 10.0), (20.0, 0.0)]
    b = [(20.0, 0.0), (10.0, -10.0), (0.0, 0.0)]
    cad = rg.encadenar_arcos([a, b])
    assert 1 <= len(cad) <= 2
    assert sum(len(c) for c in cad) < 20        # no ha entrado en bucle


def test_la_tangente_se_mide_por_LONGITUD_no_por_vertices():
    """El espaciado real de una frontera de Voronoi va de 5 a 10 m, asi que
    contar vertices da direcciones que dependen de donde cayeron."""
    # primeros vertices muy juntos y girados, el resto recto hacia el este
    pts = [(0.0, 0.0), (0.5, 0.5), (1.0, 0.0)] + [(float(x), 0.0)
                                                  for x in range(10, 60, 10)]
    tx, ty = rg._tangente(pts, False, largo=25.0)
    assert tx > 0.99 and abs(ty) < 0.05, (tx, ty)


def test_la_mezcla_de_la_bisectriz_acaba_donde_se_le_pide():
    """B-041. El rayo avanzaba PASO_CRESTA exactos por INDICE y la cadena entre
    5 y 10 m, asi que la mezcla acababa en una estacion arbitraria —el indice 10
    podia caer entre 50 y 100 m— y ahi se pegaba la traza cruda de golpe. En el
    Ej_2 se midio un giro de 109 y 131 grados justo pasado ese punto."""
    import random
    random.seed(3)
    pts = [(0.0, 0.0)]
    for _ in range(30):                       # espaciado irregular, 5 a 10 m
        pts.append((pts[-1][0] + random.uniform(5.0, 10.0),
                    pts[-1][1] + random.uniform(-1.0, 1.0)))
    bis = [{"xy": pts[0], "z": 100.0, "dirs": [(1.0, 0.0)],
            "canal": "a", "padre": "b"}]
    largo = 50.0
    out = rg._salir_por_bisectriz(pts, ("ini", 100.0), bis,
                                  largo=largo, radio=50.0)
    # mas alla de `largo` metros de ARCO la traza queda intacta
    s = 0.0
    for i in range(1, len(pts)):
        s += math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
        if s > largo + 1e-6:
            assert out[i] == pts[i], (i, s, out[i], pts[i])
    # y dentro del tramo si se ha movido hacia la bisectriz
    assert out[1] != pts[1]


# ============ B-044: el encadenado con los puntos QUE DE VERDAD LE LLEGAN
def _qgis(arco):
    """El mismo arco, pero con puntos como los que trae QGIS."""
    return [_PtXY(x, y) for x, y in arco]


def test_encadenar_con_puntos_de_QGIS_no_revienta():
    """B-044. En QGIS los arcos llegan como QgsPointXY, no como tuplas: salen de
    `_cadenas_continuas` -> `asPolyline()`. `encadenar_arcos` se intercalo entre
    esa fuente y `_densificar_xy`, que era el unico normalizador del camino, y
    hacia `pto(...)[:2]`: TypeError, y con el se caia la red de divisorias, la
    superficie y las curvas. Los tests no lo vieron porque le pasan tuplas."""
    a = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)]
    b = [(20.0, 0.0), (30.0, 0.0), (40.0, 0.0)]
    cad = rg.encadenar_arcos([_qgis(a), _qgis(b)])
    assert len(cad) == 1
    assert cad[0][0] == (0.0, 0.0) and cad[0][-1] == (40.0, 0.0)
    assert len(cad[0]) == 5, cad[0]


def test_el_encadenado_da_LO_MISMO_con_tuplas_que_con_puntos_de_QGIS():
    """Y ademas normaliza: devuelve tuplas siempre, que es lo que promete su
    docstring y lo que `_densificar_xy` espera."""
    casos = [
        [[(0., 0.), (10., 0.), (20., 0.)], [(20., 0.), (30., 0.), (40., 0.)]],
        [[(0., 0.), (10., 0.), (20., 0.)], [(40., 0.), (30., 0.), (20., 0.)]],
        [[(-40., 0.), (-20., 0.), (0., 0.)], [(0., 0.), (20., 0.), (40., 0.)],
         [(0., 0.), (10., 20.), (20., 40.)]],
        [[(0., 0.), (10., 10.), (20., 0.)], [(20., 0.), (10., -10.), (0., 0.)]],
    ]
    for arcos in casos:
        con_tuplas = rg.encadenar_arcos(arcos)
        con_qgis = rg.encadenar_arcos([_qgis(a) for a in arcos])
        assert con_qgis == con_tuplas, arcos
        for cadena in con_qgis:
            assert all(isinstance(p, tuple) for p in cadena), cadena


def test_densificar_acepta_las_dos_formas_de_punto():
    pts = [(0.0, 0.0), (30.0, 0.0)]
    assert rg._densificar_xy(_qgis(pts), 10.0) == rg._densificar_xy(pts, 10.0)


def test_el_doble_de_punto_rechaza_la_rebanada_como_el_de_verdad():
    """Si este test se cae es que el doble ha dejado de ser fiel, y entonces los
    de arriba no prueban lo que dicen probar."""
    import math as _m
    p = _PtXY(3.0, 4.0)
    assert (p[0], p[1], len(p)) == (3.0, 4.0, 2)
    assert tuple(p) == (3.0, 4.0)               # desempaquetado x, y = p
    assert _m.dist(p, _PtXY(0.0, 0.0)) == 5.0   # math.dist SI funciona
    for mal in (lambda: p[:2], lambda: p[::-1]):
        try:
            mal()
        except TypeError:
            pass
        else:
            raise AssertionError("la rebanada tenia que fallar")


# ============ generalidad del encadenado: regla de oro nº 2 (AGENTS.md)
def test_encadenar_aguanta_los_casos_limite():
    """Tiene que funcionar en TODOS los escenarios, no solo en el ejemplo con el
    que se depura: un solo canal (sin arcos), dos canales (sin nudos), un nudo de
    grado 4, un ciclo cerrado y arcos degenerados."""
    casos = {
        "sin arcos": [],
        "un solo arco": [[(0., 0.), (10., 0.), (20., 0.)]],
        "dos que no se tocan": [[(0., 0.), (10., 0.)],
                                [(100., 100.), (110., 100.)]],
        "arco degenerado": [[(0., 0.)], [(0., 0.), (10., 0.)]],
        "nudo de grado 4": [[(-20., 0.), (0., 0.)], [(0., 0.), (20., 0.)],
                            [(0., 0.), (0., 20.)], [(0., 0.), (0., -20.)]],
        "ciclo puro": [[(0., 0.), (10., 17.)], [(10., 17.), (20., 0.)],
                       [(20., 0.), (0., 0.)]],
    }
    for nombre, arcos in casos.items():
        cad = rg.encadenar_arcos(arcos)
        assert isinstance(cad, list), nombre
        # ni bucle infinito ni vertices inventados
        assert sum(len(c) for c in cad) <= sum(len(a) for a in arcos) + 2, nombre


def test_encadenar_no_pierde_ni_duplica_ningun_arco():
    """El invariante que de verdad importa: cada arco de entrada aparece una vez
    y solo una en el resultado. Se comprueba sobre 200 redes aleatorias."""
    import random
    random.seed(5)
    for _ in range(200):
        n = random.randint(1, 7)
        arcos = []
        for _k in range(n):
            x0, y0 = random.choice([(0., 0.), (50., 0.), (0., 50.), (25., 25.)])
            arcos.append([(x0, y0), (x0 + random.uniform(-40, 40),
                                     y0 + random.uniform(-40, 40))])
        cad = rg.encadenar_arcos(arcos)
        assert sum(len(c) - 1 for c in cad) == n


def test_el_encadenado_no_depende_de_afinar_sus_constantes():
    """Si el resultado cambiara al mover `tol` o `largo_tangente`, estarian
    ajustadas al ejemplo con el que se depuro."""
    izq = [(-60., 0.), (-30., 0.), (0., 0.)]
    der = [(0., 0.), (30., 0.), (60., 0.)]
    ramal = [(0., 0.), (15., 30.), (30., 60.)]
    base = len(rg.encadenar_arcos([izq, der, ramal]))
    for lt in (10.0, 25.0, 50.0, 100.0):
        for tl in (0.5, 2.0, 5.0):
            assert len(rg.encadenar_arcos([izq, der, ramal], tol=tl,
                                          largo_tangente=lt)) == base, (lt, tl)


def test_el_margen_de_confluencia_no_crece_con_la_cadena():
    """Era `0.08 * numero de vertices`. Con los arcos sueltos eran 10-20 m, pero
    al emitir CADENAS enteras (B-040) pasaba a 40-80 m, y ese margen decide si
    una confluencia parte la linea o le recorta el brazo corto: podia tirar
    decenas de metros de divisoria buena."""
    anchos = []
    for L in (100.0, 350.0, 800.0):
        n = int(L / 6) + 1
        pts = [(L * k / (n - 1), 0.0) for k in range(n)]
        i = rg._indice_a(pts, rg.MARGEN_CONFLUENCIA)
        anchos.append(i * L / (n - 1))
    assert max(anchos) - min(anchos) < 3.0, anchos
    assert all(abs(a - rg.MARGEN_CONFLUENCIA) < 6.0 for a in anchos), anchos
