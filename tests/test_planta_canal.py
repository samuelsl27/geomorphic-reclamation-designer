# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del enlace entre el tramo A (zigzag) y el tramo de fondo de valle
(senoide) en la planta del canal — core/planform.py.

B-047. Hasta la v1.0.24 la forma de onda se ELEGIA en cada vertice: zigzag si el
vertice estaba aguas arriba de la transicion y la pendiente pasaba del 4 %,
senoide en caso contrario. Las dos ondas tienen amplitud y longitud de onda
distintas y compartian una sola fase acumulada, asi que cuando le tocaba el
relevo la onda triangular podia estar en cualquier punto de su ciclo y el
desplazamiento respecto al fondo de valle daba un salto.

Medido en el eje `main` del Ej_2, entre los vertices 548 y 549 (estaciones
628.8 y 634.1 m): el desplazamiento pasaba de +0.10 m a -5.11 m en un solo paso
de densificado de 1 m, con giros de 108.7 y 98.1 grados. El GeoFluv original, en
esa misma transicion, no pasa de 66.6 grados; y los vertices de su zigzag giran
59.2, que es el valor teorico del apice para k = 1.15 y reach = 20 m:

    A = (lam/4)*sqrt(k^2 - 1)  ->  giro del apice = 2*atan(4A/lam)

Ademas se comprobaba `abs(pendiente(s)) > UMBRAL` vertice a vertice, asi que con
la pendiente rondando el 4 % la condicion parpadeaba.
"""
import math
import os
import sys
import types

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src",
                    "geomorphic_reclamation_designer", "core")


def _carga(nombre, sustituciones=()):
    ruta = os.path.join(_DIR, nombre + ".py")
    src = open(ruta, encoding="utf-8").read()
    for viejo, nuevo in sustituciones:
        src = src.replace(viejo, nuevo)
    clave = "grd_" + nombre
    mod = types.ModuleType(clave)
    mod.__file__ = ruta
    # registrado ANTES de ejecutarlo: `dataclasses` resuelve el modulo de la
    # clase por `sys.modules[cls.__module__]` y sin esto revienta
    sys.modules[clave] = mod
    exec(compile(src, ruta, "exec"), mod.__dict__)
    return mod


_carga("params")
_carga("hydrology")
pf = _carga("planform", (
    ("from .hydrology import geometria_meandro, ancho_bankfull",
     "from grd_hydrology import geometria_meandro, ancho_bankfull"),
    ("from .params import UMBRAL_PENDIENTE",
     "from grd_params import UMBRAL_PENDIENTE"),
))
pr = sys.modules["grd_params"]


class _Perfil:
    """Perfil concavo de juguete: la pendiente cae de 18 % en cabecera a 2 % en
    la boca siguiendo una parabola, asi que cruza el 4 % en un unico punto."""

    def __init__(self, L=900.0, p_cab=0.18, p_boca=0.02):
        self.L = L
        self._a, self._b = p_boca, p_cab - p_boca

    def pendiente(self, s):
        u = max(0.0, min(1.0, s / self.L))
        return -(self._a + self._b * (1.0 - u) ** 2)     # negativa: desciende

    def z(self, s):
        # no la usa la planta mas que para el atributo z de cada punto
        return 300.0 + self.pendiente(s) * s

    @property
    def s_cruce(self):
        return self.L * (1.0 - math.sqrt((0.04 - self._a) / self._b))


def _caso(reach=20.0, k_A=1.15, k_valle=1.24, L=900.0, paso=1.0):
    perfil = _Perfil(L)
    dens = [(i * paso, i * paso, 0.0) for i in range(int(L / paso) + 1)]
    glob = pr.GlobalSettings()
    glob.sinuosidad_canal_A = k_A
    glob.reach_canal_A = reach
    canal = pr.ChannelSettings()
    canal.vel_max_agua = 1.37
    canal.wd_pend_mayor_004 = 10.0
    canal.wd_pend_menor_004 = 12.5
    canal.sinuosidad_mayor_004 = k_A
    canal.sinuosidad_menor_004 = k_valle
    canal.factores_aleatorios = False

    def q_en(s):
        # caudal bankfull creciente aguas abajo, del orden del Ej_2 (1.4 m3/s en
        # la boca -> lambda ~ 49 m, que es la escala de meandro que se mide alli)
        return 0.2 + 1.2 * s / L

    return dens, perfil, q_en, canal, glob


def _traza(s_transicion=None, **kw):
    dens, perfil, q_en, canal, glob = _caso(**kw)
    if s_transicion is None:
        s_transicion = perfil.s_cruce
    pts, sinu = pf.trazar_canal(dens, perfil, s_transicion, q_en, canal, glob,
                                semilla=1)
    # el fondo de valle es el eje X, asi que el desplazamiento es la propia y
    off = [p[1] for p in pts]
    return pts, off, sinu, perfil


def _giros(pts):
    out = []
    for i in range(1, len(pts) - 1):
        ax, ay = pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]
        bx, by = pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]
        na, nb = math.hypot(ax, ay), math.hypot(bx, by)
        if na < 1e-9 or nb < 1e-9:
            continue
        c = max(-1.0, min(1.0, (ax * bx + ay * by) / (na * nb)))
        out.append(math.degrees(math.acos(c)))
    return out


def _giro_apice_teorico(k, lam):
    """Giro en el vertice de una onda triangular de sinuosidad k."""
    a = pf.amplitud_triangular(k, lam)
    return 2.0 * math.degrees(math.atan(4.0 * a / lam))


# ------------------------------------------------------- continuidad
def _ventana(valores, s_t, largo, dentro=True):
    """Reparte una serie indexada por estacion (paso 1 m) en 'la ventana de la
    transicion' y 'el resto'. La comparacion se hace entre las dos, no contra un
    numero absoluto: asi la prueba no depende de la escala del caso."""
    r = 1.5 * largo
    return [v for i, v in enumerate(valores) if (abs(i - s_t) <= r) == dentro]


def test_el_desplazamiento_no_da_saltos_en_la_transicion():
    """B-047. El defecto era un salto LOCALIZADO en la transicion: +0.10 m a
    -5.11 m en un paso de 1 m, cuando el resto del canal se mueve decimetros.
    La ventana de la transicion no puede ser mas brusca que el resto."""
    _pts, off, _s, perfil = _traza()
    saltos = [abs(off[i + 1] - off[i]) for i in range(len(off) - 1)]
    largo = 2.0 * 20.0
    dentro = _ventana(saltos, perfil.s_cruce, largo, True)
    fuera = _ventana(saltos, perfil.s_cruce, largo, False)
    assert max(dentro) <= 1.2 * max(fuera), (
        f"salto de {max(dentro):.2f} m en la transicion frente a "
        f"{max(fuera):.2f} m en el resto del canal")


def test_ningun_giro_supera_el_apice_del_zigzag():
    """El vertice mas cerrado que el metodo admite es el apice del zigzag del
    canal A. Cualquier giro mayor es un artefacto del trazado, no geometria.

    Medido sobre este mismo caso: con el codigo anterior el giro maximo salia
    69.1 grados y caia DENTRO de la ventana de la transicion; ahora sale 59.2,
    que es exactamente el apice teorico, y el peor giro de la transicion es el
    mismo que el del resto del canal."""
    pts, _off, _s, _p = _traza()
    tope = _giro_apice_teorico(1.15, 2.0 * 20.0) + 3.0     # 59.2 + margen
    peor = max(_giros(pts))
    assert peor <= tope, f"giro de {peor:.1f} grados, tope {tope:.1f}"


def test_la_transicion_no_clava_el_desplazamiento_a_cero():
    """La rampa vieja `min(1, |s-s_t|/(lam/8))` forzaba offset = 0 justo en la
    transicion y lo soltaba cinco metros despues: un pinchazo, no un enlace.
    Ahora la mezcla es suave y el canal sigue meandreando al pasar."""
    _pts, off, _s, perfil = _traza()
    s_t = perfil.s_cruce
    ventana = [off[i] for i in range(len(off)) if abs(i - s_t) <= 40.0]
    assert max(abs(o) for o in ventana) > 1.0


# --------------------------------------------------- las dos formas siguen
def test_aguas_arriba_sigue_siendo_zigzag_y_aguas_abajo_senoide():
    """La mezcla no puede comerse las dos formas: lejos de la transicion cada
    una tiene que ser la suya. Se distinguen por la curvatura: la triangular
    tiene todo el giro concentrado en los apices y cero en el resto."""
    pts, _off, _s, perfil = _traza()
    s_t = perfil.s_cruce
    arriba = _giros(pts[20:int(s_t) - 60])
    abajo = _giros(pts[int(s_t) + 60:-20])
    # zigzag: casi todos los vertices rectos y unos pocos muy cerrados
    assert sum(1 for g in arriba if g < 1.0) / len(arriba) > 0.85
    assert max(arriba) > 30.0
    # senoide: giro repartido, ninguno cerrado
    assert max(abajo) < 15.0


def test_sin_transicion_el_canal_es_todo_meandros():
    """Sin punto de transicion no hay tramo A: la onda triangular no aparece por
    ningun lado. Se distingue por la firma de la curvatura, no por el angulo:
    el zigzag deja la mayoria de los vertices RECTOS y concentra el giro en los
    apices; la senoide lo reparte."""
    dens, perfil, q_en, canal, glob = _caso()
    pts, _sinu = pf.trazar_canal(dens, perfil, None, q_en, canal, glob, semilla=1)
    g = _giros(pts)
    rectos = sum(1 for x in g if x < 1.0) / len(g)
    assert rectos < 0.30, "hay tramos rectos de zigzag donde no deberia"


# ------------------------------------------------------------ sinuosidad
def test_la_sinuosidad_no_se_desploma_con_la_mezcla():
    """La mezcla rebaja la amplitud en la ventana de transicion, asi que la
    sinuosidad real baja un poco. Lo que no puede es desplomarse: el original
    del Ej_2 sale a 1.214 con 1.24 pedido, y nosotros a 1.202."""
    _pts, _off, sinu, _p = _traza()
    assert 1.10 < sinu < 1.30
