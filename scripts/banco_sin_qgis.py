# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Carga los modulos de core/ FUERA de QGIS, con las importaciones relativas
funcionando, para poder reproducir el motor sobre los .gpkg ya escritos.

Para que sirve: probar un cambio de geometria y MEDIRLO sobre el caso real sin
tener que reinstalar el complemento y regenerar en QGIS. Se uso para descartar
tres candidatos de arreglo del perfil de divisoria en la v1.0.21 (ver P-25) sin
gastar una vuelta de QGIS en cada uno.

    import banco_sin_qgis as banco
    zs = banco.divides.perfil_desde_control(dens, base, ctrl, 0.33)

OJO: el doble de `compat` devuelve None para todo, asi que SOLO valen las
funciones de geometria pura. Nada que toque una capa de QGIS funciona aqui.
"""
import os
import sys
import types

RAIZ = ("c:/Samuel/Software_en_desarrollo/IMGA_Geofluv/"
        "geomorphic-reclamation-designer")
CORE = os.path.join(RAIZ, "src", "geomorphic_reclamation_designer", "core")

# --- qgis de mentira ---
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

# --- paquete de mentira para que los `from .x import y` funcionen ---
PKG = "gfq_core"
pkg = types.ModuleType(PKG)
pkg.__path__ = [CORE]
sys.modules[PKG] = pkg


def _carga(nombre, sustituciones=()):
    ruta = os.path.join(CORE, nombre + ".py")
    src = open(ruta, encoding="utf-8").read()
    for a, b in sustituciones:
        src = src.replace(a, b)
    mod = types.ModuleType(PKG + "." + nombre)
    mod.__package__ = PKG
    mod.__file__ = ruta
    sys.modules[PKG + "." + nombre] = mod
    exec(compile(src, ruta, "exec"), mod.__dict__)
    setattr(pkg, nombre, mod)
    return mod


class _Compat(types.ModuleType):
    """Cualquier ayudante de compat.py se resuelve a un no-operativo: aqui no se
    toca ninguna capa, solo se llaman las funciones de geometria pura."""

    def __getattr__(self, nombre):
        if nombre.startswith("_"):
            raise AttributeError(nombre)
        return lambda *a, **k: None


compat = _Compat(PKG + ".compat")
compat.attrs = lambda capa, v: v
compat.indices_datos = lambda capa: []
sys.modules[PKG + ".compat"] = compat
pkg.compat = compat

params = _carga("params")
ridges = _carga("ridges")
divides = _carga("divides")

__all__ = ["divides", "params", "ridges"]

if __name__ == "__main__":
    print("cargado: divides=%s ridges=%s" % (bool(divides), bool(ridges)))
    print("perfil_trapezoidal(30,100,20,15) =",
          ridges.perfil_trapezoidal(30.0, 100.0, 20.0, 15.0))
    print("MAX_PENDIENTE_FILO =", divides.MAX_PENDIENTE_FILO)
    print("SEPARACION_CONTROL =", divides.SEPARACION_CONTROL)
