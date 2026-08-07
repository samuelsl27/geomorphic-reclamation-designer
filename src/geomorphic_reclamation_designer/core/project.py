# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Proyecto GeoFluvQ: estado del diseño y guardado/carga en JSON.

Igual que el 'File...' de Natural Regrade: el proyecto guarda referencias a
las geometrías (fids de las polilíneas de fondo de valle y del límite) en vez
de copiar las coordenadas, de forma que si el usuario edita las capas y pulsa
'Releer fondos de valle' / regenerar, el diseño refleja los cambios.
"""

import json
import os

from .params import GlobalSettings, ChannelSettings


class GeoFluvProject:
    def __init__(self):
        self.ruta = None                    # ruta del .geofluv.json
        self.nombre = "proyecto"
        self.settings = GlobalSettings()
        self.canales = []                   # lista de ChannelSettings (índice 0 = principal)
        self.fid_limite = None              # fid del polígono del límite
        self.ruta_dem = None                # DEM 'Superficie de elevaciones'
        self.ruta_dem_comparacion = None    # superficie de comparación para corte/relleno
        self.nombre_canal_principal = "main"
        # Capas de entrada: por defecto las del plugin, pero el usuario puede
        # seleccionar cualquier capa de polígonos/líneas propia
        self.capa_limite = "GF_Boundary"
        self.capa_valles = "GF_ValleyBottoms"

    # ---------- canales ----------
    def canal_principal(self):
        return self.canales[0] if self.canales else None

    def canal_por_nombre(self, nombre):
        for c in self.canales:
            if c.nombre == nombre:
                return c
        return None

    # ---------- serialización ----------
    def to_dict(self):
        return {
            "version": 1,
            "nombre": self.nombre,
            "settings": self.settings.to_dict(),
            "canales": [c.to_dict() for c in self.canales],
            "fid_limite": self.fid_limite,
            "ruta_dem": self.ruta_dem,
            "ruta_dem_comparacion": self.ruta_dem_comparacion,
            "nombre_canal_principal": self.nombre_canal_principal,
            "capa_limite": self.capa_limite,
            "capa_valles": self.capa_valles,
        }

    def guardar(self, ruta=None):
        if ruta:
            self.ruta = ruta
        if not self.ruta:
            raise ValueError("No hay ruta de proyecto definida")
        with open(self.ruta, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def cargar(cls, ruta):
        with open(ruta, encoding="utf-8") as f:
            d = json.load(f)
        p = cls()
        p.ruta = ruta
        p.nombre = d.get("nombre", os.path.splitext(os.path.basename(ruta))[0])
        p.settings = GlobalSettings.from_dict(d.get("settings"))
        p.canales = [ChannelSettings.from_dict(c) for c in d.get("canales", [])]
        p.fid_limite = d.get("fid_limite")
        p.ruta_dem = d.get("ruta_dem")
        p.ruta_dem_comparacion = d.get("ruta_dem_comparacion")
        p.nombre_canal_principal = d.get("nombre_canal_principal", "main")
        p.capa_limite = d.get("capa_limite", "GF_Boundary")
        p.capa_valles = d.get("capa_valles", "GF_ValleyBottoms")
        return p
