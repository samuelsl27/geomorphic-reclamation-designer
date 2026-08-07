# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Convención de nombres de canales (margen derecha/izquierda mirando aguas abajo).

El canal principal recibe el nombre base (p. ej. "Arroyo"). El primer tributario
que entra por la margen derecha aguas abajo es "Arroyo R1", el primero por la
izquierda "Arroyo L1"; los tributarios de estos añaden su propio sufijo:
"Arroyo R1L1", etc.
"""


def lado_confluencia(pt_dir_padre, pt_entrada):
    """Determina si un tributario entra por la derecha (R) o izquierda (L).

    pt_dir_padre: vector (dx, dy) de la dirección aguas abajo del canal padre
                  en el punto de confluencia.
    pt_entrada:   vector (dx, dy) desde la confluencia hacia el tributario.
    Producto cruzado z > 0 => el tributario queda a la izquierda.
    """
    cross = pt_dir_padre[0] * pt_entrada[1] - pt_dir_padre[1] * pt_entrada[0]
    return "L" if cross > 0 else "R"


def renombrar_red(canales, nombre_base):
    """Reasigna nombres a toda la red según la convención.

    canales: lista de dicts con claves:
        'id', 'padre_id' (None para el principal), 'lado' ('R'/'L'),
        'estacion_confluencia' (distancia desde cabecera del padre).
    Devuelve dict id -> nombre.
    """
    nombres = {}
    principal = [c for c in canales if c.get("padre_id") is None]
    if not principal:
        return nombres
    nombres[principal[0]["id"]] = nombre_base

    def hijos_de(pid):
        hs = [c for c in canales if c.get("padre_id") == pid]
        hs.sort(key=lambda c: c.get("estacion_confluencia", 0.0))
        return hs

    def asignar(pid):
        contador = {"R": 0, "L": 0}
        for h in hijos_de(pid):
            lado = h.get("lado", "R")
            contador[lado] += 1
            base_padre = nombres[pid]
            # El sufijo se concatena al nombre del padre (sin duplicar el base)
            nombres[h["id"]] = f"{base_padre}{lado}{contador[lado]}" \
                if base_padre != nombre_base else f"{nombre_base} {lado}{contador[lado]}"
            asignar(h["id"])

    asignar(principal[0]["id"])
    return nombres
