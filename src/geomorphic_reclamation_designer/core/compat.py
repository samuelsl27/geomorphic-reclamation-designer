# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Compatibilidad QGIS 3.22+ y QGIS 4.x (Qt5/PyQt5 y Qt6/PyQt6).

Reglas de la migración a QGIS 4 que cubre este módulo:
- PyQt6 exige enums con ámbito (Qt.CursorShape.WaitCursor); PyQt5 acepta
  ambos estilos, así que el código usa SIEMPRE el estilo con ámbito y este
  módulo resuelve los enums de la API de QGIS que cambian de sitio.
- QgsField con QVariant está deprecado desde 3.38 y desaparece en 4:
  se usa QMetaType a partir de 3.38 y QVariant por debajo.
- QAction vive en QtGui en Qt6 y en QtWidgets en Qt5.
- exec_() no existe en PyQt6: el código usa exec() (presente en ambos).
- Los tipos de geometría se comparan a través de tipo_geom() porque en
  PyQt6 los enums no son comparables con int implícitamente.
"""

from qgis.core import Qgis

VERSION_QGIS = Qgis.QGIS_VERSION_INT

# ---------------------------------------------------------------- QAction
try:                                    # Qt6
    from qgis.PyQt.QtGui import QAction
except ImportError:                     # Qt5
    from qgis.PyQt.QtWidgets import QAction


# ---------------------------------------------------------------- enums genérico
def E(base, grupo, nombre):
    """Devuelve base.grupo.nombre si existe (estilo con ámbito) y si no
    base.nombre (estilo antiguo). Para enums de la API de QGIS."""
    g = getattr(base, grupo, None)
    if g is not None:
        v = getattr(g, nombre, None)
        if v is not None:
            return v
    return getattr(base, nombre)


# ---------------------------------------------------------------- tipos de campo
def _tipos_campo():
    """(str, double, int, bool) para construir QgsField según la versión."""
    if VERSION_QGIS >= 33800:
        from qgis.PyQt.QtCore import QMetaType
        T = QMetaType.Type
        return T.QString, T.Double, T.Int, T.Bool
    from qgis.PyQt.QtCore import QVariant
    return QVariant.String, QVariant.Double, QVariant.Int, QVariant.Bool


CAMPO_STR, CAMPO_DOUBLE, CAMPO_INT, CAMPO_BOOL = _tipos_campo()


# ---------------------------------------------------------------- geometría
def tipo_geom(geom):
    """Tipo de geometría como entero estable: 0 punto, 1 línea, 2 polígono.
    (En PyQt6 los enums no se comparan con int implícitamente.)"""
    t = geom.type()
    v = getattr(t, "value", t)
    try:
        return int(v)
    except (TypeError, ValueError):
        return v


# ---------------------------------------------------------------- ráster
def _fn_borrado():
    """`sip.isdeleted` en la ubicación que le toque según el enlace de Qt, o
    None si esta instalación no lo expone."""
    try:                                    # lo normal en QGIS 3 y 4
        from qgis.PyQt import sip
        return sip.isdeleted
    except ImportError:
        pass
    try:                                    # instalaciones antiguas
        import sip
        return sip.isdeleted
    except ImportError:
        return None


def capa_viva(capa):
    """True si `capa` existe y su objeto C++ NO ha sido destruido.

    QGIS destruye el objeto C++ en cuanto la capa sale del proyecto —el usuario
    la quita del árbol, se lee otro proyecto, `removeMapLayer`— pero el
    envoltorio de Python sobrevive, y la siguiente llamada revienta con
    «wrapped C/C++ object of type ... has been deleted». Quien guarde el objeto
    de una capa en vez de re-resolverla tiene que comprobar esto antes de
    tocarla (B-042)."""
    if capa is None:
        return False
    borrado = _fn_borrado()
    if borrado is not None:
        try:
            return not borrado(capa)
        except TypeError:       # no es un objeto de sip (dobles de los tests)
            pass
    try:                        # sin sip: tocarla y ver si protesta
        capa.id()
        return True
    except RuntimeError:
        return False


def formato_identify_valor():
    """Formato 'Value' para dataProvider().identify(), en su ubicación
    correcta según versión."""
    from qgis.core import QgsRaster
    try:
        return E(QgsRaster, "IdentifyFormat", "IdentifyFormatValue")
    except AttributeError:
        return E(Qgis, "RasterIdentifyFormat", "Value")


# ---------------------------------------------------------------- filtros de capa
def filtro_capas_raster():
    """Filtro 'RasterLayer' para QgsMapLayerComboBox.setFilters()."""
    try:
        return Qgis.LayerFilter.RasterLayer
    except AttributeError:
        from qgis.core import QgsMapLayerProxyModel
        return QgsMapLayerProxyModel.RasterLayer


def filtro_capas_poligono():
    """Filtro 'PolygonLayer' para QgsMapLayerComboBox.setFilters()."""
    try:
        return Qgis.LayerFilter.PolygonLayer
    except AttributeError:
        from qgis.core import QgsMapLayerProxyModel
        return QgsMapLayerProxyModel.PolygonLayer


def filtro_capas_linea():
    """Filtro 'LineLayer' para QgsMapLayerComboBox.setFilters()."""
    try:
        return Qgis.LayerFilter.LineLayer
    except AttributeError:
        from qgis.core import QgsMapLayerProxyModel
        return QgsMapLayerProxyModel.LineLayer


# ---------------------------------------------------------------- mensajes
def nivel_msg(indice):
    """Niveles de messageBar: 0 Info, 1 Warning, 2 Critical, 3 Success."""
    nombres = ["Info", "Warning", "Critical", "Success"]
    try:
        return getattr(Qgis.MessageLevel, nombres[indice])
    except AttributeError:
        return getattr(Qgis, nombres[indice])


# ------------------------------------------------ features y clave primaria
def indices_datos(capa):
    """Índices de los campos de DATOS de una capa, saltando la clave primaria
    automática que añaden algunos formatos.

    Un GeoPackage siempre añade un campo 'fid' de clave primaria al principio;
    si se rellenan los atributos por posición (setAttributes) sin tenerlo en
    cuenta, todos los valores se desplazan una columna y la escritura falla o
    guarda basura. Con capas en memoria no hay pk y la lista es la completa.
    """
    campos = capa.fields()
    n = campos.count()
    try:
        pk = set(capa.primaryKeyAttributes() or [])
    except Exception:
        pk = set()
    idx = [i for i in range(n) if i not in pk]
    if not idx:
        idx = list(range(n))
    return idx


def nueva_feature(capa, valores, geometria=None):
    """QgsFeature de 'capa' con 'valores' asignados a sus campos de datos
    (respetando la clave primaria automática) y, opcionalmente, geometría."""
    from qgis.core import QgsFeature
    f = QgsFeature(capa.fields())
    idx = indices_datos(capa)
    if len(idx) > len(valores):
        idx = idx[:len(valores)]
    for i, v in zip(idx, valores):
        f.setAttribute(i, v)
    if geometria is not None:
        f.setGeometry(geometria)
    return f


def attrs(capa, valores):
    """Lista de atributos ALINEADA con los campos de 'capa'.

    Rellena los campos de datos en orden y deja a None la clave primaria
    automática (el 'fid' que GeoPackage añade al principio). Sin esto, guardar
    las capas en disco desplazaba todos los valores una columna y las capas
    salían vacías o con los atributos corridos."""
    n = capa.fields().count()
    idx = indices_datos(capa)
    salida = [None] * n
    for i, v in zip(idx, valores):
        salida[i] = v
    return salida
