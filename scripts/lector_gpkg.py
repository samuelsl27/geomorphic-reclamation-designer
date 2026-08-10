#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lector minimo de GeoPackage: sqlite3 + un parser de WKB propio.

POR QUE ESTO Y NO GDAL. Este guion es de MEDIDA, y la medida tiene que poder
ejecutarse desde una consola normal, sin arrancar QGIS y sin depender de que
osgeo/GDAL este en el PYTHONPATH del interprete de turno. Un GeoPackage es un
SQLite con la geometria en BLOB, asi que con la biblioteca estandar basta.

QUE HAY QUE SABER DEL FORMATO:

- El BLOB de GeoPackage es una cabecera propia ('GP', version, banderas,
  srs_id, envelope opcional) seguida del WKB estandar. La longitud del envelope
  la dicen tres bits de las banderas.
- El DXF que exporta el programa original llega a QGIS con **arcos**, asi que
  sus polilineas no son LineString (tipo 2) sino **CompoundCurve (tipo 9)** con
  tramos CircularString (tipo 8) dentro. Un parser que solo entienda el tipo 2
  devuelve cero entidades y la comparacion sale vacia sin dar ningun error:
  exactamente el fallo silencioso que mas caro sale en este proyecto.
- Los CircularString se toman por sus vertices, sin linealizar el arco. Para lo
  que se mide aqui (cotas de extremo, pendientes vertice a vertice, longitudes)
  la diferencia es despreciable y no merece la complicacion.

Uso como biblioteca:

    from lector_gpkg import leer, tablas, campos
    for f in leer("GRD_Ridges.gpkg", "GRD_Ridges"):
        print(f["attrs"], f["geom"])     # geom = lista de partes; parte = [(x,y,z)]
"""

import os
import shutil
import sqlite3
import struct
import tempfile

# Tipos WKB que son "una lista de subgeometrias" y se recorren igual.
_CONTENEDORES = (4, 5, 6, 7, 9, 10, 11, 12)


def _punto(buf, off, fmt, hay_z, hay_m):
    n = 2 + (1 if hay_z else 0) + (1 if hay_m else 0)
    vals = struct.unpack_from(fmt + "d" * n, buf, off)
    return (vals[0], vals[1], vals[2] if hay_z else None), off + 8 * n


def _lista_de_puntos(buf, off, fmt, hay_z, hay_m):
    (n,) = struct.unpack_from(fmt + "I", buf, off)
    off += 4
    pts = []
    for _ in range(n):
        p, off = _punto(buf, off, fmt, hay_z, hay_m)
        pts.append(p)
    return pts, off


def _geom(buf, off):
    """Devuelve (lista de partes, offset). Cada parte es una lista de (x,y,z)."""
    endian = buf[off]
    off += 1
    fmt = "<" if endian == 1 else ">"
    (gtype,) = struct.unpack_from(fmt + "I", buf, off)
    off += 4
    if gtype & 0x80000000:          # EWKB de PostGIS
        hay_z, hay_m, base = True, bool(gtype & 0x40000000), gtype & 0xFF
    else:                            # ISO WKB: 1000 -> Z, 2000 -> M, 3000 -> ZM
        alto, base = gtype // 1000, gtype % 1000
        hay_z, hay_m = alto in (1, 3), alto in (2, 3)

    partes = []
    if base == 1:                                    # Point
        p, off = _punto(buf, off, fmt, hay_z, hay_m)
        partes.append([p])
    elif base in (2, 8):                             # LineString, CircularString
        pts, off = _lista_de_puntos(buf, off, fmt, hay_z, hay_m)
        partes.append(pts)
    elif base == 3:                                  # Polygon
        (nanillos,) = struct.unpack_from(fmt + "I", buf, off)
        off += 4
        for _ in range(nanillos):
            pts, off = _lista_de_puntos(buf, off, fmt, hay_z, hay_m)
            partes.append(pts)
    elif base in _CONTENEDORES:
        (nsub,) = struct.unpack_from(fmt + "I", buf, off)
        off += 4
        for _ in range(nsub):
            sub, off = _geom(buf, off)
            partes.extend(sub)
        if base == 9:
            partes = [_unir(partes)]   # CompoundCurve: sus tramos son continuos
    else:
        raise ValueError("tipo WKB no soportado: %d (gtype=%d)" % (base, gtype))
    return partes, off


def _unir(partes):
    """Encadena los tramos de un CompoundCurve en una sola polilinea."""
    salida = []
    for p in partes:
        if salida and p and salida[-1][:2] == p[0][:2]:
            salida.extend(p[1:])
        else:
            salida.extend(p)
    return salida


def parse_blob(blob):
    """Geometria de un BLOB de GeoPackage -> lista de partes."""
    if not blob:
        return []
    if blob[:2] == b"GP":
        env = (blob[3] >> 1) & 0x07
        off = 8 + {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}.get(env, 0)
    else:
        off = 0                       # WKB pelado
    return _geom(blob, off)[0]


# --------------------------------------------------------------- acceso SQLite
class _Abierto:
    """Abre el .gpkg para lectura sin tocar el original.

    Si hay un WAL sin consolidar (QGIS deja .gpkg-wal cuando la sesion no ha
    cerrado la capa), abrir en solo lectura no lo veria y faltarian entidades.
    Se copia el trio .gpkg/-wal/-shm a un temporal y se lee de ahi: se ve todo
    y no se modifica nada de lo del usuario.
    """

    def __init__(self, ruta):
        self.tmp = None
        if os.path.exists(ruta + "-wal"):
            self.tmp = tempfile.mkdtemp(prefix="grd_cmp_")
            destino = os.path.join(self.tmp, os.path.basename(ruta))
            for suf in ("", "-wal", "-shm"):
                if os.path.exists(ruta + suf):
                    shutil.copy2(ruta + suf, destino + suf)
            ruta = destino
        self.con = sqlite3.connect(ruta)

    def __enter__(self):
        return self.con

    def __exit__(self, *_exc):
        self.con.close()
        if self.tmp:
            shutil.rmtree(self.tmp, ignore_errors=True)


def tablas(ruta):
    """[(nombre, tipo, srs_id)] de las tablas registradas en el GeoPackage."""
    with _Abierto(ruta) as con:
        return con.execute(
            "SELECT table_name, data_type, srs_id FROM gpkg_contents").fetchall()


def campos(ruta, tabla):
    with _Abierto(ruta) as con:
        return [(c[1], c[2]) for c in con.execute('PRAGMA table_info("%s")' % tabla)]


def leer(ruta, tabla, where=None):
    """[{'attrs': {...}, 'geom': [[(x,y,z), ...], ...]}] de una tabla."""
    with _Abierto(ruta) as con:
        fila = con.execute(
            "SELECT column_name FROM gpkg_geometry_columns WHERE table_name=?",
            (tabla,)).fetchone()
        col_geom = fila[0] if fila else None
        cols = [c[1] for c in con.execute('PRAGMA table_info("%s")' % tabla)]
        sql = 'SELECT %s FROM "%s"' % (",".join('"%s"' % c for c in cols), tabla)
        if where:
            sql += " WHERE " + where
        salida = []
        for fila in con.execute(sql):
            d = dict(zip(cols, fila))
            blob = d.pop(col_geom, None) if col_geom else None
            try:
                geom = parse_blob(blob)
            except Exception as e:
                geom, d["_error_geom"] = [], str(e)
            salida.append({"attrs": d, "geom": geom})
        return salida


def lineas(ruta, tabla, where=None):
    """[(attrs, [(x,y,z), ...])] descartando partes de menos de 2 vertices."""
    return [(f["attrs"], parte)
            for f in leer(ruta, tabla, where)
            for parte in f["geom"] if len(parte) >= 2]
