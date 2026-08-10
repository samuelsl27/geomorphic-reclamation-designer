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
_ruta = os.path.join(_DIR, "ridges.py")
_src = open(_ruta, encoding="utf-8").read().replace(
    "from . import setup_tools as st", "st = None").replace(
    "from .compat import tipo_geom, CAMPO_STR, attrs",
    "tipo_geom = CAMPO_STR = None\nattrs = lambda capa, v: v")
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
