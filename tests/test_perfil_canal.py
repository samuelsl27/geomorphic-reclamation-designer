# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del perfil longitudinal del cauce (core/profile.py).

El perfil del cauce es el cimiento del diseno: de su cota cuelgan las crestas,
las laderas y la superficie. Un error aqui se propaga a todo lo demas, asi que
va con sus propias pruebas.

Las cifras de referencia estan medidas sobre el DXF del programa original en el
ejemplo Rom_Pla (6 canales), con `scripts/comparar_original.py`.
"""
import math

from core.profile import PerfilLongitudinal, disenar_perfil, estacion_transicion


def pendiente_media(perfil, a, b):
    """Pendiente media (%) entre dos estaciones, positiva si desciende."""
    return (perfil.z(a) - perfil.z(b)) / (b - a) * 100.0


def deciles(perfil, n=10):
    """Pendiente media (%) por deciles, de BOCA a CABECERA."""
    L = perfil.L
    return [pendiente_media(perfil, L * (1 - (k + 1) / n), L * (1 - k / n))
            for k in range(n)]


def es_monotono(perfil):
    return all(perfil.cotas[i] <= perfil.cotas[i - 1] + 1e-9
               for i in range(1, len(perfil.cotas)))


# ------------------------------------------------- lo basico se sigue cumpliendo
def test_el_perfil_pasa_por_las_dos_cotas():
    p = disenar_perfil(300.0, 50.0, 30.0, -0.12, -0.02)
    assert math.isclose(p.z(0.0), 50.0, abs_tol=1e-6)
    assert math.isclose(p.z(300.0), 30.0, abs_tol=1e-6)


def test_el_perfil_siempre_desciende_aguas_abajo():
    """Invariante G4: el perfil longitudinal es monotono descendente."""
    for L, zc, zb, s0, s1 in ((300, 50, 30, -0.12, -0.02),
                              (190.46, 320.00, 289.09, -0.154, -0.0555),
                              (284.86, 332.36, 276.71, -0.1744, -0.0212),
                              (903.68, 338.64, 275.03, -0.18, -0.022),
                              (200, 100, 99, -0.50, -0.001)):
        assert es_monotono(disenar_perfil(L, zc, zb, s0, s1)), (L, zc, zb)


def test_perfil_concavo_cuando_la_cabecera_es_mas_empinada_que_la_media():
    """Caso normal: |s_cabecera| > |media| -> la pendiente crece sin parar
    hacia la cabecera. Medido en el canal principal del Ej_2."""
    p = disenar_perfil(903.68, 338.64, 275.03, -0.18, -0.022)
    d = deciles(p)
    assert not p.cabecera_convexa
    assert all(d[i] <= d[i + 1] + 1e-6 for i in range(len(d) - 1)), d


# ------------------------------------------------------- tramo convexo de cabecera
def test_la_pendiente_de_cabecera_pedida_se_respeta():
    """La cabecera del Ej_2 main L1 se pide al 15.4 % y el original la da al
    16.2 %. Hasta la v1.0.18 el motor la re-empinaba al 25.8 % para forzar un
    perfil concavo, sacrificando el dato del usuario."""
    p = disenar_perfil(190.46, 320.00, 289.09, -0.154, -0.0555)
    assert math.isclose(p.s_cabecera, -0.154, abs_tol=1e-9)
    assert not p.ajustado
    assert pendiente_media(p, 0.0, 20.0) < 17.0


def test_cabecera_mas_tendida_que_la_media_da_tramo_convexo():
    """Si |s_cabecera| < |media| no cabe un perfil concavo: algun tramo
    intermedio tiene que ser mas empinado que la cabecera. El original lo
    resuelve con una cabecera CONVEXA (la pendiente crece desde la boca, hace
    maximo en torno al 70-80 % del recorrido y decrece hacia la cabecera).

    Ej_2 main L1, original: 6.5 9.8 12.6 14.9 16.5 17.6 18.1 18.1 17.4 16.2
    """
    p = disenar_perfil(190.46, 320.00, 289.09, -0.154, -0.0555)
    assert p.cabecera_convexa
    d = deciles(p)
    cumbre = d.index(max(d))
    assert 5 <= cumbre <= 8, d          # el maximo NO esta en la cabecera
    assert d[-1] < max(d)               # y decrece hacia ella
    assert es_monotono(p)


def test_el_tramo_convexo_aparece_tambien_en_un_tributario_corto():
    """Ej_2 main R4: pedida -17.44 %, media -19.5 %. El original da 18.29 % en
    la cabecera; el motor viejo daba 36.95 %."""
    p = disenar_perfil(284.86, 332.36, 276.71, -0.1744, -0.0212)
    assert p.cabecera_convexa
    assert math.isclose(p.s_cabecera, -0.1744, abs_tol=1e-9)
    assert pendiente_media(p, 0.0, 20.0) < 21.0
    assert es_monotono(p)


# ------------------------------------------------------------- monotonia forzada
def test_fritsch_carlson_recorta_una_pendiente_imposible_y_avisa():
    """Unica correccion que se sigue imponiendo: la condicion suficiente de
    monotonia de la cubica de Hermite, 0 <= s/m <= 3."""
    p = disenar_perfil(200.0, 100.0, 99.0, -0.50, -0.001)
    m = (99.0 - 100.0) / 200.0
    assert p.ajustado
    assert math.isclose(p.s_cabecera, 3.0 * m, rel_tol=1e-9)
    assert es_monotono(p)


def test_una_pendiente_que_remonta_se_lleva_a_cero():
    p = disenar_perfil(300.0, 50.0, 30.0, +0.05, -0.02)
    assert p.ajustado
    assert p.s_cabecera == 0.0
    assert es_monotono(p)


def test_sin_desnivel_el_perfil_es_plano():
    p = disenar_perfil(300.0, 40.0, 40.0, -0.12, -0.02)
    assert p.ajustado
    assert max(p.cotas) - min(p.cotas) < 1e-6


# --------------------------------------------------------------- transicion tipo A
def test_la_transicion_marca_donde_se_baja_del_4_por_ciento():
    """[LIBRO cap. 2] y [ROS]: por encima del 4 % el canal es tipo A."""
    p = disenar_perfil(500.0, 100.0, 50.0, -0.20, -0.01)
    s = estacion_transicion(p, umbral=0.04)
    assert s is not None
    assert abs(p.pendiente(s)) <= 0.04 + 1e-6
    assert abs(p.pendiente(max(0.0, s - 20.0))) > 0.04


def test_un_canal_tendido_no_tiene_tramo_A():
    p = disenar_perfil(500.0, 100.0, 95.0, -0.02, -0.005)
    assert estacion_transicion(p, umbral=0.04) is None


def test_perfil_vacio_no_revienta():
    p = disenar_perfil(0.0, 10.0, 5.0, -0.1, -0.02)
    assert isinstance(p, PerfilLongitudinal)
    assert estacion_transicion(p) is None
