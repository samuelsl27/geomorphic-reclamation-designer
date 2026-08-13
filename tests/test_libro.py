# -*- coding: utf-8 -*-
"""Verificacion del motor contra 'Geomorphic Reclamation Design' (2024).

Cada prueba fija UNA afirmacion del libro, citada en su docstring, y comprueba
que el codigo la cumple numericamente. Si alguien cambia una constante del
motor, aqui salta.

Ejecutar:  python3 -m pytest tests/test_libro.py -v
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "geomorphic_reclamation_designer"))

from core.hydrology import (   # noqa: E402
    geometria_meandro, ancho_bankfull, qpk_racional,
    tension_critica_shields, calado_normal_manning, dimensionar_seccion,
    RC_MIN, RC_MAX, LAMBDA_POR_RC, BELT_POR_LAMBDA, THETA_CRIT,
    GAMMA_W, GAMMA_S, Z_TALUD, _area_trapecio, _perimetro_trapecio,
)
from core.params import GlobalSettings, ChannelSettings, UMBRAL_PENDIENTE  # noqa: E402


# ===================================================== 2.2.9 regime equations
def test_radio_de_curvatura_entre_2_5_y_3_2_veces_la_anchura():
    """Libro, cap. 2, 'Channel plan view geometry':

    «Williams (1986) determined that the radius of curvature falls within a
    range of approximately 2.5 to 3.2 times the bankfull width».
    """
    assert (RC_MIN, RC_MAX) == (2.5, 3.2)
    W = 4.0
    for k, esperado in ((2.5, 10.0), (3.2, 12.8)):
        _lam, _belt, rc = geometria_meandro(W, k)
        assert abs(rc - esperado) < 1e-9, (k, rc)
    # fuera del rango se acota, no se extrapola
    assert abs(geometria_meandro(W, 1.0)[2] - 2.5 * W) < 1e-9
    assert abs(geometria_meandro(W, 9.0)[2] - 3.2 * W) < 1e-9
    # sin k explicito, el minimo estable
    assert abs(geometria_meandro(W)[2] - 2.5 * W) < 1e-9


def test_longitud_de_meandro_453_veces_el_radio():
    """«He found that channel meander length is a function of bankfull width
    that is 4.53 times the radius of curvature».
    """
    assert LAMBDA_POR_RC == 4.53
    W = 3.0
    lam, _belt, rc = geometria_meandro(W, 2.8)
    assert abs(lam - 4.53 * rc) < 1e-9
    assert abs(lam / rc - 4.53) < 1e-12


def test_cinturon_061_veces_la_longitud_de_meandro():
    """«He also determined that the meander belt width is a function of
    bankfull width as 0.61 times the meander length».
    """
    assert BELT_POR_LAMBDA == 0.61
    lam, belt, _rc = geometria_meandro(5.0, 3.0)
    assert abs(belt - 0.61 * lam) < 1e-9


def test_las_tres_ecuaciones_encadenadas():
    """Comprobacion de la cadena completa W -> Rc -> lambda -> B con un caso
    numerico cerrado a mano."""
    W = 2.0
    lam, belt, rc = geometria_meandro(W, 2.5)
    assert abs(rc - 5.0) < 1e-9                    # 2.5 x 2.0
    assert abs(lam - 22.65) < 1e-9                 # 4.53 x 5.0
    assert abs(belt - 13.8165) < 1e-9              # 0.61 x 22.65
    # y todas crecen linealmente con W: al doblar W se doblan las tres
    lam2, belt2, rc2 = geometria_meandro(2 * W, 2.5)
    for a, b in ((rc, rc2), (lam, lam2), (belt, belt2)):
        assert abs(b - 2 * a) < 1e-9


# ===================================================== 2.2.10 'A' reach
def test_el_reach_de_canal_A_es_media_longitud_de_meandro():
    """Libro, 2.2.10: «The "A-channel" reach length is one-half of a "meander
    length" for the steeper channels».

    En `planform.trazar_canal` la onda del tramo A usa `lam_A = 2.0 * reach_A`,
    que es exactamente esa relacion despejada. La misma relacion fija la ventana
    de mezcla entre las dos ondas (`largo_mezcla = 2.0 * reach_A`, B-047): una
    longitud de meandro del canal A.
    """
    ruta = os.path.join(os.path.dirname(__file__), "..", "src", "geomorphic_reclamation_designer", "core", "planform.py")
    src = open(ruta, encoding="utf-8").read()
    assert "lam_A = 2.0 * reach_A" in src, \
        "el tramo A ya no usa reach = media longitud de meandro"
    assert "largo_mezcla = 2.0 * reach_A" in src, \
        "la ventana de mezcla ya no es una longitud de meandro del canal A"


# ===================================================== 2.2.9 tipos de canal
def test_umbral_del_4_por_ciento_separa_los_dos_tipos():
    """«Rosgen's (1996) classification separates the many different channel
    types into two broad categories: the steeper channel types (>4%) and the
    lower gradient valley-bottom channel types (<4%)».
    """
    assert UMBRAL_PENDIENTE == 0.04


def test_relacion_anchura_profundidad_por_tipo():
    """«Channels steeper than 4% have: width to depth (W:D) <10:1 ...
    Channels less than 4% have: W:D >10:1».

    Los valores por defecto tienen que caer del lado correcto del 10.
    """
    c = ChannelSettings()
    assert c.wd_pend_mayor_004 <= 10.0, c.wd_pend_mayor_004
    assert c.wd_pend_menor_004 > 10.0, c.wd_pend_menor_004


def test_sinuosidad_por_tipo():
    """«Sinuosity < 1.2, expressed as a "zig-zag" pattern» para >4 % y
    «Sinuosity > 1.2 (1.4 to 1.9 is not unusual...)» para <4 %.
    """
    g, c = GlobalSettings(), ChannelSettings()
    assert g.sinuosidad_canal_A < 1.2
    assert c.sinuosidad_mayor_004 < 1.2
    assert c.sinuosidad_menor_004 > 1.2
    assert 1.4 <= c.sinuosidad_menor_004 <= 1.9


# ===================================================== metodo racional
def test_metodo_racional_en_unidades_metricas():
    """Libro, 4.3.2 / 7.5: metodo racional Q = C·i·A. En unidades metricas
    (i en mm/h, A en ha) el factor de conversion es 1/360.

    Comprobacion dimensional: 1 mm/h sobre 1 ha = 10 m3/h = 0.002778 m3/s,
    que es exactamente 1/360.
    """
    assert abs(qpk_racional(1.0, 1.0, 1.0) - 1.0 / 360.0) < 1e-12
    assert abs(qpk_racional(1.0, 1.0, 1.0) - 0.0027778) < 1e-6
    # lineal en los tres factores
    assert abs(qpk_racional(0.6, 15.0, 23.3) - 0.6 * 15.0 * 23.3 / 360.0) < 1e-12
    # sin escorrentia no hay caudal
    assert qpk_racional(0.0, 50.0, 100.0) == 0.0


# ===================================================== Shields
def test_tension_critica_de_shields():
    """tau_c = theta·(gamma_s - gamma_w)·D50, con theta = 0.045 para lecho
    turbulento rugoso y gamma_s de un sedimento de 2650 kg/m3.
    """
    assert THETA_CRIT == 0.045
    assert abs(GAMMA_S - 2650.0 * 9.81) < 1.0
    assert abs(GAMMA_W - 1000.0 * 9.81) < 1.0
    d50 = 8.0                                   # mm
    esperado = 0.045 * (GAMMA_S - GAMMA_W) * (d50 / 1000.0)
    assert abs(tension_critica_shields(d50) - esperado) < 1e-9
    assert abs(tension_critica_shields(8.0) - 5.83) < 0.05   # N/m2
    # lineal con D50 y nula si no hay dato
    assert abs(tension_critica_shields(16.0)
               - 2 * tension_critica_shields(8.0)) < 1e-9
    assert tension_critica_shields(0.0) == 0.0
    assert tension_critica_shields(None) == 0.0


# ===================================================== Manning
def test_manning_reproduce_el_caudal_que_se_le_pide():
    """Q = (1/n)·A·R^(2/3)·sqrt(S). El calado normal devuelto tiene que
    reproducir el caudal de entrada al sustituirlo en la formula."""
    q, n, s, b = 1.25, 0.033, 0.02, 1.0
    d = calado_normal_manning(q, n, s, b)
    a = _area_trapecio(b, Z_TALUD, d)
    r = a / _perimetro_trapecio(b, Z_TALUD, d)
    q_rec = a * (r ** (2.0 / 3.0)) * math.sqrt(s) / n
    assert abs(q_rec - q) / q < 1e-3, (q_rec, q)


def test_manning_es_monotono_con_el_caudal_y_la_pendiente():
    d1 = calado_normal_manning(0.5, 0.033, 0.02, 1.0)
    d2 = calado_normal_manning(2.0, 0.033, 0.02, 1.0)
    assert d2 > d1                                  # mas caudal, mas calado
    d3 = calado_normal_manning(1.0, 0.033, 0.005, 1.0)
    d4 = calado_normal_manning(1.0, 0.033, 0.05, 1.0)
    assert d3 > d4                                  # mas pendiente, menos calado
    # sin pendiente no hay flujo uniforme
    assert calado_normal_manning(1.0, 0.033, 0.0, 1.0) == 0.0


# ===================================================== seccion de diseno
def test_la_seccion_se_dimensiona_con_la_velocidad_maxima():
    """El metodo dimensiona por continuidad A = Q/v con la 'Maximum Water
    Velocity' del canal, y despues reparte esa area segun W:D."""
    q, wd, v = 1.0, 12.5, 1.4
    w = ancho_bankfull(q, wd, v)
    d = w / wd
    a = _area_trapecio(w - 2 * Z_TALUD * d if w - 2 * Z_TALUD * d > 0 else 0.0,
                       Z_TALUD, d)
    # el area del trapecio equivalente reproduce Q/v
    assert abs(d * (wd - Z_TALUD) * d - q / v) < 1e-9
    # y W:D se respeta
    assert abs(w / d - wd) < 1e-9


def test_el_flood_prone_es_mas_ancho_que_el_bankfull():
    """El area flood-prone esta POR ENCIMA del nivel bankfull y disipa la
    energia de las crecidas raras (cap. 2)."""
    sec = dimensionar_seccion(q_bankfull=0.5, q_flood=5.0, wd_ratio=12.5,
                              vel_max=1.4, pendiente=-0.02, d50_mm=8.0)
    assert sec.ancho_flood > sec.ancho_bankfull
    assert sec.prof_flood > sec.prof_bankfull
    assert sec.entrenchment > 1.0


def test_el_encajamiento_es_la_relacion_flood_bankfull():
    sec = dimensionar_seccion(q_bankfull=0.5, q_flood=5.0, wd_ratio=12.5,
                              vel_max=1.4, pendiente=-0.02, d50_mm=8.0)
    assert abs(sec.entrenchment - sec.ancho_flood / sec.ancho_bankfull) < 1e-6


def test_la_estabilidad_tractiva_compara_con_shields():
    """'Highlight Tractive Force Zones': una estacion es inestable cuando la
    tension tractiva supera la critica del material del lecho."""
    fino = dimensionar_seccion(2.0, 8.0, 12.5, 1.4, -0.09, d50_mm=0.5)
    grueso = dimensionar_seccion(2.0, 8.0, 12.5, 1.4, -0.09, d50_mm=64.0)
    # a igualdad de todo lo demas, el material mas grueso aguanta mas
    assert fino.tension_critica < grueso.tension_critica
    assert fino.ratio_tractivo > grueso.ratio_tractivo
    assert fino.estab_tractiva == "high"
    # y la misma seccion en pendiente suave con material grueso si es estable
    suave = dimensionar_seccion(2.0, 8.0, 12.5, 1.4, -0.005, d50_mm=64.0)
    assert suave.ratio_tractivo < 1.0
    assert suave.estab_tractiva != "high"


def test_la_seccion_crece_aguas_abajo_con_el_caudal():
    """Cap. 2: «the channel dimensions will continually increase in the
    downstream direction to accommodate greater discharges as a function of
    increased watershed area»."""
    arriba = dimensionar_seccion(0.2, 1.0, 12.5, 1.4, -0.02, d50_mm=8.0)
    abajo = dimensionar_seccion(2.0, 10.0, 12.5, 1.4, -0.02, d50_mm=8.0)
    assert abajo.ancho_bankfull > arriba.ancho_bankfull
    assert abajo.prof_bankfull > arriba.prof_bankfull
    # y con ella toda la geometria de planta
    assert (geometria_meandro(abajo.ancho_bankfull)[0]
            > geometria_meandro(arriba.ancho_bankfull)[0])
