# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del empalme de una ladera con su divisoria (core/topology.py).

B-048. `revisar()` repite el pase topologico hasta punto fijo, con tope de 30
pasadas, asi que una decision NO IDEMPOTENTE se multiplica por treinta.

El primer filtro de `empalmar_en_divisorias` era

    if d_xy < 0.5 or d_xy > tol: continue

dentro del bucle de candidatas. Cuando el extremo de la ladera ya estaba sobre
una divisoria, eso no paraba nada: descartaba ESA candidata y se iba a la
siguiente, hasta 18 m mas alla, y volvia a prolongar la linea. En la pasada
siguiente la mas proxima era la que acababa de alcanzar —descartada otra vez— y
volvia a la primera. Ping-pong, una cola por pasada.

Medido en el Ej_2: `GRD_SubRidges` fid 86 (canal "main R2", indice 15) salia con
66 vertices oscilando entre TRES puntos, 260.6 m de longitud, sinuosidad 8.318 y
28 giros de mas de 60 grados, con maximo de 180.00. En el GeoFluv original las
117 vaguadas tienen sinuosidad 1.000 y angulo de giro maximo 0.00 grados, y el
94 % de las 120 subcrestas son rectas perfectas.

La causa se reprodujo aparte con la logica anterior y una ladera de 6 vertices
que ya moria sobre una divisoria, con otra a 8 m: 30 pasadas sin converger,
**66 vertices, 260.0 m y giro maximo de 180.0 grados**, o sea la linea real
clavada. De paso explica P-05: el bucle nunca llegaba a punto fijo.
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
_ruta = os.path.join(_DIR, "topology.py")
_src = open(_ruta, encoding="utf-8").read().replace(
    "from .compat import attrs", "attrs = lambda capa, v: v")
tp = types.ModuleType("grd_topology")
exec(compile(_src, _ruta, "exec"), tp.__dict__)


def _ladera(n=6, paso=4.0):
    """Ladera recta que sube hacia el este, del cauce (x=0) a la divisoria."""
    return [(i * paso, 0.0, 280.0 + i * 1.0) for i in range(n)]


def _cand(*items):
    """[(distancia, fid, punto)] ordenado, como lo da `_proyecciones`."""
    return sorted([(d, fid, p) for fid, (d, p) in enumerate(items)],
                  key=lambda t: t[0])


# --------------------------------------------------------- el caso de B-048
def test_si_ya_muere_sobre_la_divisoria_no_se_prolonga_a_otra():
    """El nucleo de B-048. La ladera ya toca su divisoria (0.1 m) y hay otra a
    8 m: no se toca. Antes se prolongaba hasta la segunda, y a la pasada
    siguiente volvia a la primera."""
    pts = _ladera()
    alto = pts[-1]
    cand = _cand((0.1, (alto[0] + 0.1, alto[1], alto[2])),
                 (8.0, (alto[0] + 8.0, alto[1], alto[2] + 1.0)))
    assert tp.destino_de_empalme(pts, alto, False, cand) is None


def test_el_empalme_es_idempotente():
    """Aplicar la regla dos veces seguidas tiene que dar lo mismo que aplicarla
    una: es lo que `revisar()` da por supuesto al repetir el pase."""
    pts = _ladera()
    alto = pts[-1]
    cand = _cand((8.0, (alto[0] + 8.0, alto[1], alto[2] + 1.0)))
    destino = tp.destino_de_empalme(pts, alto, False, cand)
    assert destino is not None
    # segunda pasada: la linea ya llega, y la divisoria queda a 0
    pts2 = pts + [destino]
    cand2 = _cand((0.0, destino))
    assert tp.destino_de_empalme(pts2, destino, False, cand2) is None


# ------------------------------------------------------ segunda defensa
def test_no_se_admite_una_cola_que_se_dobla_hacia_atras():
    """Una subcresta es RECTA en planta (sinuosidad 1.000 en el original), asi
    que una prolongacion hacia atras no es una prolongacion, es un pliegue."""
    pts = _ladera()
    alto = pts[-1]
    detras = (alto[0] - 8.0, alto[1], alto[2] + 1.0)
    assert tp.destino_de_empalme(pts, alto, False, _cand((8.0, detras))) is None


def test_la_cola_hacia_delante_si_se_admite():
    pts = _ladera()
    alto = pts[-1]
    delante = (alto[0] + 8.0, alto[1], alto[2] + 1.0)
    assert tp.destino_de_empalme(pts, alto, False, _cand((8.0, delante))) == delante


def test_el_pliegue_se_mide_tambien_cuando_la_linea_viene_invertida():
    """Si el extremo alto es el PRIMER vertice, la referencia de direccion es
    pts[1], no pts[-2]."""
    pts = list(reversed(_ladera()))
    alto = pts[0]
    delante = (alto[0] + 8.0, alto[1], alto[2] + 1.0)
    detras = (alto[0] - 8.0, alto[1], alto[2] + 1.0)
    assert tp.destino_de_empalme(pts, alto, True, _cand((8.0, delante))) == delante
    assert tp.destino_de_empalme(pts, alto, True, _cand((8.0, detras))) is None


# ------------------------------------------------------- guardas que ya habia
def test_no_se_empalma_con_una_divisoria_a_cota_imposible():
    """Sin esto se pegaba la diferencia entera en un solo segmento: medido en el
    Ej_2, una subcresta subia de 300.7 a 336.0 m en 3.69 m, un 955 %."""
    pts = _ladera()
    alto = pts[-1]
    imposible = (alto[0] + 4.0, alto[1], alto[2] + 40.0)   # 1000 %
    assert tp.destino_de_empalme(pts, alto, False, _cand((4.0, imposible))) is None


def test_no_se_empalma_con_una_divisoria_demasiado_lejos():
    pts = _ladera()
    alto = pts[-1]
    lejos = (alto[0] + 40.0, alto[1], alto[2] + 1.0)
    assert tp.destino_de_empalme(pts, alto, False, _cand((40.0, lejos))) is None


def test_sin_candidatas_no_hay_empalme():
    pts = _ladera()
    assert tp.destino_de_empalme(pts, pts[-1], False, []) is None
