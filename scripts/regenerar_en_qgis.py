#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regenera un ejemplo entero DENTRO de QGIS, sin tocar la interfaz.

ESTE GUION SE EJECUTA EN LA CONSOLA DE PYTHON DE QGIS, no desde una terminal:
necesita el complemento cargado y un proyecto de QGIS abierto con las capas de
entrada (limite, fondos de valle, DEM).

    exec(open(r"...\\scripts\\regenerar_en_qgis.py", encoding="utf-8").read())

o, si se quiere otro ejemplo:

    PROYECTO = r"...\\Ej_1_Potoya_v5_Samu_3\\GRD_Files\\GRD_Potoya_file.grd.json"
    exec(open(r"...\\scripts\\regenerar_en_qgis.py", encoding="utf-8").read())

POR QUE EXISTE. Medir una correccion de geometria obliga a regenerar el diseno
completo, y hacerlo a mano (abrir proyecto, cargar el .grd.json, Preview, Draw
Design Surface) son cuatro pasos que se olvidan a medias o se hacen en otro
orden. Reproduce EXACTAMENTE lo que hace `dock._menu_proyecto` en su rama
"open" seguido de `_preview` y `_dibujar_superficie`, que es el camino que
recorre el usuario: si se llamara directamente a las funciones del motor se
estaria probando otra cosa (ver B-021, y el caso de `ai_optimizer`, que se
saltaba `divides.ajustar_divisorias` y puntuaba una superficie distinta).

DESPUES, desde una terminal normal:

    python scripts/comparar_original.py <carpeta del ejemplo>

RECUERDA: si se ha tocado `core/params.py`, hay que REINICIAR QGIS antes. La
recarga en caliente deja `GlobalSettings` viejo en memoria y salta un
`AttributeError` confuso al leer un ajuste nuevo (context/07, trampa 3).
"""

import os

# Ruta del proyecto a regenerar. Se puede fijar ANTES de hacer el exec() para
# usar otro ejemplo; si no, se toma la de por defecto.
PROYECTO = globals().get("PROYECTO") or (
    r"C:\Samuel\Software_en_desarrollo\IMGA_Geofluv\Ejemplos"
    r"\Ej_2_Rom_Pla\GRD_Files\GRD_Rom_Pla_File.grd.json")

SUPERFICIE = globals().get("SUPERFICIE", True)   # tambien TIN y curvas


def regenerar(ruta, superficie=True):
    from qgis import utils
    from geomorphic_reclamation_designer.core.project import GeoFluvProject
    from geomorphic_reclamation_designer.core.layer_manager import LayerManager

    p = utils.plugins.get("geomorphic_reclamation_designer")
    if p is None:
        raise RuntimeError("el complemento no esta cargado en este perfil de QGIS")
    d = p._ensure_dock()
    print("complemento ver.", getattr(d, "VERSION", "?"))

    # --- misma secuencia que dock._menu_proyecto, rama "open" ---
    d.proyecto = GeoFluvProject.cargar(ruta)
    d.ruta_proyecto = ruta
    d.lm = LayerManager(d.iface, d.proyecto.nombre)
    d.lm.configurar_almacenamiento(
        getattr(d.proyecto.settings, "modo_almacenamiento", "memory"),
        getattr(d.proyecto.settings, "carpeta_capas", ""))
    d.lb_proyecto.setText(os.path.basename(ruta))
    if d.proyecto.ruta_dem and os.path.exists(d.proyecto.ruta_dem):
        d._cargar_dem(d.proyecto.ruta_dem)
    d._refrescar_canales()
    d._releer_valles()
    d._actualizar_estado_botones()
    print("proyecto:", d.proyecto.nombre,
          "| canales:", [c.nombre for c in d.proyecto.canales])

    d._preview()
    print("preview hecho | canales generados:", len(d.diseno))
    if superficie:
        d._dibujar_superficie()
        print("superficie y curvas hechas")

    # --- recuento de lo escrito, para saber si ha ido bien sin abrir nada ---
    for nombre in ("GRD_Channels", "GRD_Ridges", "GRD_SubRidges",
                   "GRD_Swales", "GRD_XSections", "GRD_Contours"):
        capa = d.lm.obtener_capa(nombre, crear=False)
        print("   %-16s %s" % (
            nombre, capa.featureCount() if capa is not None else "(no existe)"))
    return d


def comprobar(d):
    """Check Design sobre el diseno recien generado: (errores, avisos, info).

    Mismos argumentos que le pasa `dock._revisar_diseno`, para que el recuento
    sea el que ve el usuario en el Error Log y no uno parecido."""
    from geomorphic_reclamation_designer.core import checks
    hallazgos = checks.revisar(
        d.lm, d.proyecto.settings, proyecto=d.proyecto, disenos=d.diseno,
        g_lim=d._geom_limite(), dem=d.dem_layer,
        ruta_superficie=getattr(d, "ruta_superficie", None),
        resultado_cf=getattr(d, "_ultimo_cf", None))
    n_e, n_w, n_i = checks.resumen(hallazgos)
    print("Check Design: %d error(es), %d aviso(s), %d nota(s)" % (n_e, n_w, n_i))
    for h in hallazgos:
        if h.gravedad == "error":
            print("   ERROR", h.codigo, h.titulo, "|", h.detalle)
    return hallazgos


_d = regenerar(PROYECTO, SUPERFICIE)
comprobar(_d)
print("HECHO")
