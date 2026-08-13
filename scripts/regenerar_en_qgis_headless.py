# -*- coding: utf-8 -*-
"""Regenera el Ej_2 con QGIS EN MODO HEADLESS y exporta las capas a una carpeta
de trabajo, SIN tocar los GeoPackage del usuario.

    "C:\\Program Files\\QGIS 4.2.0\\bin\\python-qgis.bat" regenerar_ej2.py <salida>

Reproduce la secuencia de `gui.dock._preview`:
    builder.construir -> ridges.generar_subcuencas -> generar_crestas
    -> generar_subcrestas -> topology.revisar -> divides.ajustar_divisorias
    -> builder.recalcular_por_aportes

Las capas de salida se crean EN MEMORIA (modo_almacenamiento='memory') y al
final se vuelcan a GeoPackage en la carpeta que se pase por argumento. Los
ficheros de `Ejemplos/Ej_2_Rom_Pla/GRD_Files` se leen, nunca se escriben.
"""
import os
import sys
import traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Carpeta del ejemplo: se puede pasar por argumento para correr cualquier
# proyecto, no solo el que se usa para depurar.
EJ_POR_DEFECTO = r"C:\Samuel\Software_en_desarrollo\IMGA_Geofluv\Ejemplos\Ej_2_Rom_Pla"

sys.path.insert(0, os.path.join(RAIZ, "src"))

from qgis.core import (
    QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer,
    QgsCoordinateReferenceSystem, QgsVectorFileWriter,
    QgsCoordinateTransformContext,
)

_PREFIJO = os.path.dirname(os.path.dirname(sys.executable))
QgsApplication.setPrefixPath(_PREFIJO, True)
qgs = QgsApplication([], False)
qgs.initQgis()

# processing vive en los plugins de la instalacion, no en el PYTHONPATH normal
for _p in (os.path.join(_PREFIJO, "python", "plugins"),
           os.path.join(_PREFIJO, "apps", "qgis", "python", "plugins"),
           os.path.join(os.path.dirname(_PREFIJO), "apps", "qgis", "python",
                        "plugins")):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
import processing  # noqa: F401  (registra los algoritmos nativos)
from processing.core.Processing import Processing
Processing.initialize()

from geomorphic_reclamation_designer.core.project import GeoFluvProject as Proyecto
from geomorphic_reclamation_designer.core.layer_manager import LayerManager
from geomorphic_reclamation_designer.core.builder import GeoFluvBuilder
from geomorphic_reclamation_designer.core import ridges, topology, divides
from geomorphic_reclamation_designer.core import builder as _b


def log(msg):
    print(msg, flush=True)


def main(salida, ejemplo=EJ_POR_DEFECTO):
    global GRD
    GRD = os.path.join(ejemplo, "GRD_Files")
    proys = [f for f in os.listdir(GRD) if f.endswith(".grd.json")]
    if not proys:
        raise RuntimeError(f"no hay ningun .grd.json en {GRD}")
    proy = os.path.join(GRD, proys[0])
    os.makedirs(salida, exist_ok=True)
    QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:25830"))

    p = Proyecto.cargar(proy)
    # NO escribir en la carpeta del usuario: todo en memoria
    p.settings.modo_almacenamiento = "memory"
    p.settings.carpeta_capas = ""
    log(f"proyecto '{p.nombre}': {len(p.canales)} canales, "
        f"fid_limite={p.fid_limite}")

    # --- capas de ENTRADA, leidas del disco ---
    for nombre, gpkg in (("GRD_Boundary", "GRD_Boundary.gpkg"),
                         ("GRD_ValleyBottoms", "GRD_ValleyBottoms.gpkg")):
        uri = f"{os.path.join(GRD, gpkg)}|layername={nombre}"
        lyr = QgsVectorLayer(uri, nombre, "ogr")
        if not lyr.isValid():
            raise RuntimeError(f"no se pudo abrir {uri}")
        QgsProject.instance().addMapLayer(lyr, False)
        log(f"  entrada {nombre}: {lyr.featureCount()} entidades")

    dem = QgsRasterLayer(p.ruta_dem, "DEM")
    if not dem.isValid():
        raise RuntimeError(f"DEM invalido: {p.ruta_dem}")
    QgsProject.instance().addMapLayer(dem, False)

    lm = LayerManager(None, p.nombre)
    lm.configurar_almacenamiento("memory", "")

    # --- 1. canales ---
    b = GeoFluvBuilder(p, lm, dem)
    diseno = b.construir()
    log(f"1. builder: {len(diseno)} canales, {len(b.avisos)} avisos")
    for a in b.avisos:
        log(f"     aviso: {a}")

    gl = b._geom_limite()
    crs = QgsProject.instance().crs().authid()

    # --- 2. subcuencas ---
    sub = ridges.generar_subcuencas(diseno, gl, lm, crs)
    log(f"2. subcuencas: {len(sub)}")

    # --- 3. crestas divisorias ---
    n_cr, crestas3d, exc = ridges.generar_crestas(diseno, sub, gl, p.settings,
                                                  dem, lm)
    log(f"3. crestas: {n_cr}  (exceso de techo peor: {exc:.2f} m)")

    # --- 4. subcrestas y vaguadas ---
    n_sc, n_vg, avisos = ridges.generar_subcrestas(diseno, gl, p.settings, lm,
                                                   dem=dem, crestas=crestas3d)
    log(f"4. subcrestas: {n_sc}, vaguadas: {n_vg}")
    for a in avisos:
        log(f"     aviso: {a}")

    # --- 5. pase topologico ---
    res = topology.revisar(lm, p.settings, log=lambda m: log("     " + m.strip()))
    log(f"5. topology.revisar: {res}")

    # --- 6. divisorias: recorte y cota ---
    divides.ajustar_divisorias(lm, diseno, p.settings, dem=dem, g_lim=gl,
                               log=lambda m: log("     " + m.strip()))
    log("6. divides.ajustar_divisorias hecho")

    # --- 7. hidraulica escalonada ---
    _b.recalcular_por_aportes(diseno, lm, p.settings,
                              log=lambda m: log("     " + m.strip()))
    log("7. recalcular_por_aportes hecho")

    # --- volcado ---
    ctx = QgsCoordinateTransformContext()
    for nombre in ("GRD_Ridges", "GRD_SubRidges", "GRD_Swales", "GRD_Channels",
                   "GRD_SubWatershed", "GRD_ValleyBottoms", "GRD_ChannelBanks",
                   "GRD_XSections"):
        lyr = lm.obtener_capa(nombre, crear=False)
        if lyr is None:
            log(f"  (sin capa {nombre})")
            continue
        op = QgsVectorFileWriter.SaveVectorOptions()
        op.driverName = "GPKG"
        op.layerName = nombre
        op.fileEncoding = "UTF-8"
        destino = os.path.join(salida, nombre + ".gpkg")
        if os.path.exists(destino):
            os.remove(destino)
        err = QgsVectorFileWriter.writeAsVectorFormatV3(lyr, destino, ctx, op)
        log(f"  volcado {nombre}: {lyr.featureCount()} entidades  err={err[0]}")
    log("LISTO")


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(
                 os.path.dirname(os.path.abspath(__file__)), "salida"),
             sys.argv[2] if len(sys.argv) > 2 else EJ_POR_DEFECTO)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    finally:
        qgs.exitQgis()
