# -*- coding: utf-8 -*-
"""Tests puros (sin QGIS) del motor hidráulico v1.1.

Ejecutar:  python3 -m pytest tests/test_hidraulica.py -v
   (o simplemente  python3 tests/test_hidraulica.py)
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "geomorphic_reclamation_designer"))

from core.hydrology import (   # noqa: E402
    qpk_racional, dimensionar_seccion, calado_normal_manning,
    tension_critica_shields, geometria_meandro, ancho_bankfull,
    _area_trapecio, _perimetro_trapecio, GAMMA_W, Z_TALUD,
)


def casi(a, b, tol=1e-3):
    assert abs(a - b) <= tol * max(1.0, abs(b)), f"{a} != {b}"


def test_racional():
    # Q = C·i·A/360 : C=0.89, i=20 mm/h, A=26.99 ha -> 1.334 m3/s
    casi(qpk_racional(0.89, 20.0, 26.99), 0.89 * 20 * 26.99 / 360.0)
    assert qpk_racional(0.6, 0.0, 100.0) == 0.0


def test_seccion_libro_2024():
    """Ejemplo del libro Geomorphic Reclamation Design 2024 (cap. 9):
    W:D = 12.5, taludes 4:1, calado 1 m => W = 12.5 m, fondo = 4.5 m,
    A = 8.5 m2."""
    # elegimos Q y v para que salga d = 1 exacto: A = d²(12.5-4) = 8.5
    v = 1.0
    q = 8.5 * v
    s = dimensionar_seccion(q, 0.0, 12.5, v, -0.02)
    casi(s.prof_bankfull, 1.0)
    casi(s.ancho_bankfull, 12.5)
    casi(s.ancho_fondo, 4.5)
    casi(s.area_bankfull, 8.5)
    # perímetro = b + 2·d·sqrt(17)
    casi(s.perimetro_bkf, 4.5 + 2 * math.sqrt(17.0))
    casi(s.radio_hidr_bkf, 8.5 / (4.5 + 2 * math.sqrt(17.0)))


def test_flood_prone_envuelve():
    """La sección flood-prone comparte fondo, es más profunda y más ancha,
    y el ratio de atrincheramiento es > 1."""
    s = dimensionar_seccion(1.0, 4.5, 12.5, 1.4, -0.02)
    assert s.prof_flood > s.prof_bankfull
    assert s.ancho_flood > s.ancho_bankfull
    assert s.entrenchment > 1.0
    casi(s.area_flood, 4.5 / 1.4, 0.02)   # A_fp = Q_fp / v


def test_crecimiento_aguas_abajo():
    """Con más caudal, todas las dimensiones crecen (consistencia NR)."""
    s1 = dimensionar_seccion(0.5, 2.0, 12.5, 1.4, -0.02)
    s2 = dimensionar_seccion(2.0, 8.0, 12.5, 1.4, -0.02)
    for at in ("ancho_bankfull", "prof_bankfull", "area_bankfull",
               "ancho_flood", "prof_flood"):
        assert getattr(s2, at) > getattr(s1, at)


def test_tension_tractiva():
    """τ = γ·R·S con R del trapecio."""
    s = dimensionar_seccion(8.5, 0.0, 12.5, 1.0, -0.02)
    casi(s.tension_bankfull, GAMMA_W * s.radio_hidr_bkf * 0.02)


def test_shields():
    # τcrit = 0.045·(γs−γw)·D50 ; D50 = 8 mm -> ~5.83 N/m2
    t = tension_critica_shields(8.0)
    casi(t, 0.045 * (25996.5 - 9810.0) * 0.008)
    # pendiente fuerte y material fino => inestable
    s = dimensionar_seccion(2.0, 8.0, 10.0, 1.4, -0.10, d50_mm=2.0)
    assert s.estab_tractiva == "high" and s.ratio_tractivo > 1.0
    # pendiente suave y material grueso => estable
    s2 = dimensionar_seccion(0.3, 1.2, 12.5, 1.4, -0.005, d50_mm=60.0)
    assert s2.estab_tractiva == "ok"


def test_manning():
    """El calado normal reproduce el caudal por la fórmula de Manning."""
    b, z, n, S, q = 3.0, Z_TALUD, 0.033, 0.02, 2.0
    d = calado_normal_manning(q, n, S, b, z)
    a = _area_trapecio(b, z, d)
    r = a / _perimetro_trapecio(b, z, d)
    q_check = a * r ** (2 / 3) * math.sqrt(S) / n
    casi(q_check, q, 1e-3)
    # verificación integrada: en pendiente fuerte v_manning > v_max -> aviso
    s = dimensionar_seccion(2.0, 8.0, 10.0, 1.0, -0.08, n_manning=0.030)
    assert s.verif_manning == "v_high"


def test_meandros():
    """Regime equations (Williams 1986, libro 2024 §2.2):
    Rc = k·W (k=2.5 defecto), λ = 4.53·Rc, cinturón = 0.61·λ."""
    w = 5.0
    lm, belt, rc = geometria_meandro(w)
    casi(rc, 2.5 * w)
    casi(lm, 4.53 * rc)
    casi(belt, 0.61 * lm)
    # con k máximo
    lm2, belt2, rc2 = geometria_meandro(w, k=3.2)
    casi(rc2, 3.2 * w)
    assert lm2 > lm and belt2 > belt


def test_ancho_bankfull():
    # W = wd·d con d = sqrt((Q/v)/(wd−z))
    q, wd, v = 8.5, 12.5, 1.0
    casi(ancho_bankfull(q, wd, v), 12.5)


def test_casos_limite():
    s = dimensionar_seccion(0.0, 0.0, 12.5, 1.4, -0.02)
    assert s.ancho_bankfull == 0.0
    # W:D menor que el mínimo geométrico -> se corrige con aviso
    s2 = dimensionar_seccion(1.0, 0.0, 3.0, 1.4, -0.02)
    assert s2.ancho_bankfull > 0 and s2.avisos


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ok    {nombre}")
            except AssertionError as e:
                fallos += 1
                print(f"  FALLO {nombre}: {e}")
    print("TODOS LOS TESTS OK" if fallos == 0 else f"{fallos} fallos")
    sys.exit(1 if fallos else 0)
