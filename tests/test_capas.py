# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pruebas del ciclo de vida de las capas (core/compat.py, core/setup_tools.py).

B-042 y B-043. El panel guardaba el objeto de la capa del DEM en vez de
re-resolverla; cuando QGIS destruia esa capa, el envoltorio de Python quedaba
colgando y la primera lectura reventaba con «wrapped C/C++ object of type
QgsRasterLayer has been deleted». Y lo que la destruia era el propio
complemento: al abrir un proyecto sobre un QGIS que ya tenia el terreno
cargado, lo anadia DUPLICADO, y el usuario borraba la copia.

Se ejecutan los modulos REALES con QGIS simulado, no copias de sus funciones:
una copia se desincroniza y deja de probar lo que se cree que prueba.
"""
import os
import sys
import types

import pytest

# --------------------------------------------------------------- QGIS falso
_q = types.ModuleType("qgis")
_c = types.ModuleType("qgis.core")


class _Qgis:
    # compat.py lo lee en el import; 3.38+ para que use QMetaType
    QGIS_VERSION_INT = 34200


_c.Qgis = _Qgis


def _cualquier_clase(nombre):
    if nombre.startswith("_"):
        raise AttributeError(nombre)
    cls = type(nombre, (), {})
    setattr(_c, nombre, cls)
    return cls


_c.__getattr__ = _cualquier_clase
_q.core = _c

_pyqt = types.ModuleType("qgis.PyQt")
_qtgui = types.ModuleType("qgis.PyQt.QtGui")
_qtgui.QAction = type("QAction", (), {})
_qtcore = types.ModuleType("qgis.PyQt.QtCore")
_qtcore.QMetaType = type("QMetaType", (), {
    "Type": type("Type", (), {"QString": "str", "Double": "double",
                              "Int": "int", "Bool": "bool"})})
_q.PyQt = _pyqt
_pyqt.QtGui = _qtgui
_pyqt.QtCore = _qtcore

for _n, _m in (("qgis", _q), ("qgis.core", _c), ("qgis.PyQt", _pyqt),
               ("qgis.PyQt.QtGui", _qtgui), ("qgis.PyQt.QtCore", _qtcore)):
    sys.modules.setdefault(_n, _m)

# ------------------------------------------------- modulos reales bajo prueba
_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src",
                    "geomorphic_reclamation_designer", "core")


def _cargar(fichero, reemplazos=()):
    ruta = os.path.join(_DIR, fichero)
    with open(ruta, encoding="utf-8") as fh:
        src = fh.read()
    for viejo, nuevo in reemplazos:
        # si el import cambia, que el test lo diga en vez de probar otra cosa
        assert viejo in src, f"{fichero}: ya no contiene {viejo!r}"
        src = src.replace(viejo, nuevo)
    mod = types.ModuleType("gfq_" + fichero[:-3])
    # registrar ANTES de ejecutar: @dataclass busca su propio modulo en
    # sys.modules mientras se construye la clase
    sys.modules[mod.__name__] = mod
    exec(compile(src, ruta, "exec"), mod.__dict__)
    return mod


compat = _cargar("compat.py")
_cargar("params.py")
st = _cargar("setup_tools.py", [
    ("from .params import UMBRAL_PENDIENTE",
     "from gfq_params import UMBRAL_PENDIENTE"),
    ("from .compat import tipo_geom, formato_identify_valor, capa_viva",
     "from gfq_compat import tipo_geom, formato_identify_valor, capa_viva"),
])

MSG_MUERTA = "wrapped C/C++ object of type QgsRasterLayer has been deleted"


# ------------------------------------------------------------------ dobles
class RasterFalso(st.QgsRasterLayer):
    """Capa rastera de mentira. `viva=False` imita el envoltorio huerfano:
    cualquier metodo lanza el RuntimeError de sip."""

    def __init__(self, ruta, viva=True):
        self._ruta = ruta
        self._viva = viva

    def source(self):
        if not self._viva:
            raise RuntimeError(MSG_MUERTA)
        return self._ruta

    def id(self):
        if not self._viva:
            raise RuntimeError(MSG_MUERTA)
        return "id:" + self._ruta

    def dataProvider(self):
        raise AssertionError("no se debe llegar al proveedor de una capa muerta")


class VectorFalso:
    """Cualquier capa que NO sea rastera. Deliberadamente no hereda de
    QgsRasterLayer: es lo unico que la distingue del terreno."""

    def __init__(self, ruta):
        self._ruta = ruta

    def source(self):
        return self._ruta

    def id(self):
        return "id:" + self._ruta


# ------------------------------------------------------------- capa_viva()
def test_capa_viva_dice_que_no_a_none():
    assert compat.capa_viva(None) is False


def test_capa_viva_distingue_la_viva_de_la_muerta():
    assert compat.capa_viva(RasterFalso("C:/dem/topo.tif")) is True
    assert compat.capa_viva(RasterFalso("C:/dem/topo.tif", viva=False)) is False


def test_capa_viva_manda_sip_cuando_esta_disponible():
    """En QGIS real la unica fuente fiable es sip.isdeleted: un objeto borrado
    puede seguir contestando a metodos triviales."""
    falso = types.ModuleType("qgis.PyQt.sip")
    falso.isdeleted = lambda obj: getattr(obj, "_borrada", False)
    _pyqt.sip = falso
    sys.modules["qgis.PyQt.sip"] = falso
    try:
        capa = RasterFalso("C:/dem/topo.tif")     # su .id() responde siempre
        capa._borrada = True
        assert compat.capa_viva(capa) is False    # y aun asi manda sip
        capa._borrada = False
        assert compat.capa_viva(capa) is True
    finally:
        del _pyqt.sip
        sys.modules.pop("qgis.PyQt.sip", None)


# --------------------------------------------------------- raster_por_ruta()
def test_encuentra_la_misma_ruta_escrita_de_otra_forma():
    capas = [RasterFalso("C:/dem/topo.tif")]
    assert st.raster_por_ruta("C:/dem/./topo.tif", capas) is capas[0]


@pytest.mark.skipif(sys.platform != "win32",
                    reason="mayusculas y barras invertidas solo en Windows")
def test_en_windows_da_igual_mayusculas_y_barras():
    """El caso real: el proyecto guarda 'C:/…/Topo.tif' y QGIS devuelve
    'C:\\…\\topo.tif'. Comparadas en crudo parecen ficheros distintos y el
    raster se duplicaba (B-043)."""
    capas = [RasterFalso(r"C:\DEM\Topo.tif")]
    assert st.raster_por_ruta("C:/dem/topo.tif", capas) is capas[0]


def test_no_devuelve_una_capa_muerta():
    """Recuperar el DEM entregando el cadaver no arregla nada: es justo el
    objeto que revienta al tocarlo (B-042)."""
    capas = [RasterFalso("C:/dem/topo.tif", viva=False)]
    assert st.raster_por_ruta("C:/dem/topo.tif", capas) is None


def test_no_confunde_una_vectorial_con_el_terreno():
    capas = [VectorFalso("C:/dem/topo.tif")]
    assert st.raster_por_ruta("C:/dem/topo.tif", capas) is None


def test_sin_ruta_no_hay_nada_que_buscar():
    capas = [RasterFalso("C:/dem/topo.tif")]
    assert st.raster_por_ruta("", capas) is None
    assert st.raster_por_ruta(None, capas) is None


def test_otra_ruta_no_vale():
    capas = [RasterFalso("C:/dem/topo.tif")]
    assert st.raster_por_ruta("C:/dem/otro.tif", capas) is None


def test_se_queda_con_la_primera_viva_habiendo_muertas():
    viva = RasterFalso("C:/dem/topo.tif")
    capas = [RasterFalso("C:/dem/topo.tif", viva=False), viva]
    assert st.raster_por_ruta("C:/dem/topo.tif", capas) is viva


# ----------------------------------------------------------------- cota_dem()
def test_sin_dem_la_cota_es_none():
    assert st.cota_dem(None, 0.0, 0.0) is None


def test_con_el_dem_muerto_para_en_seco_y_lo_explica():
    """Y NO devuelve None: eso haria caer las cotas al calculo de reserva y
    saldria un diseno silenciosamente equivocado (B-042)."""
    capa = RasterFalso("C:/dem/topo.tif", viva=False)
    with pytest.raises(RuntimeError) as exc:
        st.cota_dem(capa, 10.0, 20.0)
    assert str(exc.value) == st.MSG_DEM_MUERTO
    assert "wrapped C/C++" not in str(exc.value)
