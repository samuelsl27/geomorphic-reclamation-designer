# -*- coding: utf-8 -*-
"""Test de integración headless de GeoFluvQ sobre QGIS real.

Ejecuta el flujo completo: DEM sintético → límite → red de canales →
builder (perfiles, planta, secciones, capas) → subcuencas → crestas →
subcrestas/vaguadas → superficie TIN → curvas de nivel → corte/relleno →
centroides. Cualquier error de API o de lógica revienta aquí.
"""
import os, sys, math, traceback

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "/usr/share/qgis/python/plugins")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from qgis.core import (
    QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer, QgsFeature,
    QgsGeometry, QgsPointXY, QgsCoordinateReferenceSystem,
)

QgsApplication.setPrefixPath("/usr", True)
qgs = QgsApplication([], False)
qgs.initQgis()
import processing
from processing.core.Processing import Processing
Processing.initialize()

PASOS_OK = []

def paso(nombre):
    def deco(fn):
        def wrap(*a, **k):
            try:
                r = fn(*a, **k)
                PASOS_OK.append(nombre)
                print(f"  ✔ {nombre}")
                return r
            except Exception:
                print(f"  ✘ {nombre}")
                traceback.print_exc()
                sys.exit(1)
        return wrap
    return deco

# ---------------------------------------------------------------- DEM sintético
@paso("DEM sintético (GeoTIFF)")
def crear_dem():
    from osgeo import gdal, osr
    ruta = "/tmp/dem_test.tif"
    nx = ny = 400
    cell = 2.0
    drv = gdal.GetDriverByName("GTiff")
    ds = drv.Create(ruta, nx, ny, 1, gdal.GDT_Float32)
    ds.SetGeoTransform([0, cell, 0, 800, 0, -cell])
    srs = osr.SpatialReference(); srs.ImportFromEPSG(25830)
    ds.SetProjection(srs.ExportToWkt())
    import struct
    banda = ds.GetRasterBand(1)
    for fila in range(ny):
        y = 800 - (fila + 0.5) * cell
        vals = []
        for col in range(nx):
            x = (col + 0.5) * cell
            vals.append(100.0 - 0.07 * x + 0.015 * abs(y - 400.0))
        banda.WriteRaster(0, fila, nx, 1, struct.pack(f"{nx}f", *vals),
                          buf_type=6)  # GDT_Float32
    ds.FlushCache(); ds = None
    return ruta

# ---------------------------------------------------------------- proyecto
class IfaceMock:
    def __getattr__(self, n):
        raise AttributeError(n)

@paso("Proyecto, CRS y árbol de capas")
def preparar(ruta_dem):
    QgsProject.instance().setCrs(QgsCoordinateReferenceSystem("EPSG:25830"))
    from geomorphic_reclamation_designer.core.layer_manager import LayerManager
    lm = LayerManager(None, "test")
    lm.crear_arbol()
    dem = QgsRasterLayer(ruta_dem, "DEM test")
    assert dem.isValid()
    QgsProject.instance().addMapLayer(dem, False)
    lm.subgrupo("01 Inputs").addLayer(dem)
    return lm, dem

@paso("Límite y fondos de valle (entidades)")
def entradas(lm):
    capa_l = lm.obtener_capa("GF_Boundary")
    f = QgsFeature(capa_l.fields())
    anillo = [QgsPointXY(60, 160), QgsPointXY(740, 160), QgsPointXY(740, 640),
              QgsPointXY(60, 640), QgsPointXY(60, 160)]
    f.setGeometry(QgsGeometry.fromPolygonXY([anillo]))
    f.setAttributes(["limite", 0.0])
    capa_l.dataProvider().addFeatures([f])
    fid_lim = next(capa_l.getFeatures()).id()

    capa_v = lm.obtener_capa("GF_ValleyBottoms")
    valles = [
        [(120, 420), (400, 405), (750, 400)],                 # principal (sale por el E)
        [(300, 600), (305, 500), (310, 412)],                 # tributario N
        [(500, 200), (503, 300), (505, 398)],                 # tributario S
        [(310, 500), (420, 470), (430, 415)],                 # trib del trib N
    ]
    fids = []
    for pts in valles:
        f = QgsFeature(capa_v.fields())
        f.setGeometry(QgsGeometry.fromPolylineXY([QgsPointXY(*p) for p in pts]))
        f.setAttributes(["", False])
        capa_v.dataProvider().addFeatures([f])
    fids = [ft.id() for ft in capa_v.getFeatures()]
    return fid_lim, fids

@paso("Validaciones de Setup (límite, principal, tributarios, transición)")
def validaciones(lm, dem, fid_lim, fids):
    from geomorphic_reclamation_designer.core import setup_tools as st
    capa_l = lm.obtener_capa("GF_Boundary")
    capa_v = lm.obtener_capa("GF_ValleyBottoms")
    g_lim = capa_l.getFeature(fid_lim).geometry()
    ok, area_ha, msg = st.validar_limite(g_lim)
    assert ok and 30 < area_ha < 40, (ok, area_ha)
    g_main = capa_v.getFeature(fids[0]).geometry()
    ok, msg = st.validar_canal_principal(g_main, g_lim)
    assert ok, msg
    geoms = [g_main]
    for fid in fids[1:]:
        g = capa_v.getFeature(fid).geometry()
        ok, msg, p_idx, ext = st.validar_tributario(g, g_lim, geoms, 25.0, 25.0)
        assert ok, msg
        geoms.append(g)
    t = st.transicion_automatica(dem, g_main)
    z = st.cota_dem(dem, 400, 400)
    assert abs(z - (100 - 0.07 * 400)) < 1.5, z
    return g_lim

@paso("Builder: diseño completo de la red")
def construir(lm, dem, fid_lim, fids):
    from geomorphic_reclamation_designer.core.project import GeoFluvProject
    from geomorphic_reclamation_designer.core.params import ChannelSettings
    from geomorphic_reclamation_designer.core.builder import GeoFluvBuilder
    p = GeoFluvProject()
    p.fid_limite = fid_lim
    p.nombre_canal_principal = "arroyo"
    for i, fid in enumerate(fids):
        c = ChannelSettings(nombre=f"c{i}")
        c.fid_fondo_valle = fid
        p.canales.append(c)
    b = GeoFluvBuilder(p, lm, dem)
    disenos = b.construir()
    assert len(disenos) == 4, list(disenos)
    nombres = set(disenos)
    assert "arroyo" in nombres, nombres
    # convención R/L: trib N (desde +y con flujo +x) = L1; trib S = R1
    assert any(n.endswith("L1") and "R" not in n.split()[-1] for n in nombres), nombres
    assert any(n.endswith("R1") and "L" not in n.split()[-1] for n in nombres), nombres
    # empalme en confluencia: cota del hijo = cota del padre
    principal = disenos["arroyo"]
    for n, d in disenos.items():
        if d.padre == "arroyo":
            z_p = principal.perfil.z(d.s_confluencia)
            assert abs(d.perfil.z_boca - z_p) < 1e-6, (n, d.perfil.z_boca, z_p)
    # capas escritas
    assert lm.obtener_capa("GF_Channels").featureCount() == 4
    assert lm.obtener_capa("GF_ChannelBanks").featureCount() == 24   # 6 por canal
    assert lm.obtener_capa("GF_XSections").featureCount() > 40
    # geometrías con Z
    g = next(lm.obtener_capa("GF_Channels").getFeatures()).geometry()
    assert g.constGet().is3D()
    print(f"      canales: {sorted(nombres)}  avisos: {len(b.avisos)}")
    return p, disenos

@paso("Subcuencas (Voronoi + dissolve)")
def subcuencas(disenos, g_lim, lm):
    from geomorphic_reclamation_designer.core import ridges
    crs = QgsProject.instance().crs().authid()
    sub = ridges.generar_subcuencas(disenos, g_lim, lm, crs)
    assert len(sub) == 4, list(sub)
    a_tot = sum(g.area() for g in sub.values()) / 10000.0
    assert abs(a_tot - g_lim.area() / 10000.0) < 0.5, a_tot   # cubren el límite
    return sub

@paso("GF_Ridges")
def crestas(disenos, sub, g_lim, dem, lm):
    from geomorphic_reclamation_designer.core import ridges
    from geomorphic_reclamation_designer.core.params import GlobalSettings
    glob = GlobalSettings()
    n = ridges.generar_crestas(disenos, sub, g_lim, glob, dem, lm)
    assert n >= 3, n
    g = next(lm.obtener_capa("GF_Ridges").getFeatures()).geometry()
    assert g.constGet().is3D()
    return glob

@paso("Subcrestas y vaguadas")
def subcrestas(disenos, g_lim, glob, lm):
    from geomorphic_reclamation_designer.core import ridges
    ns, nv = ridges.generar_subcrestas(disenos, g_lim, glob, lm)
    assert ns > 4 and nv > 2, (ns, nv)
    print(f"      {ns} subcrestas, {nv} vaguadas")

@paso("GF_DesignSurface (TIN)")
def superficie(lm, g_lim, dem, disenos, glob):
    from geomorphic_reclamation_designer.core import surface
    capa, ruta = surface.interpolar_superficie(lm, g_lim, dem, disenos, glob)
    assert capa.isValid() and os.path.exists(ruta)
    lm.anadir_raster_a_grupo(capa, "03 Output")
    # cota del diseño en la boca ≈ cota de boca del principal
    from geomorphic_reclamation_designer.core import setup_tools as st
    z = st.cota_dem(capa, 700, 400)
    z_esp = disenos["arroyo"].perfil.z(disenos["arroyo"].L_valle * 0.93)
    assert z is not None and abs(z - z_esp) < 5.0, (z, z_esp)
    return capa, ruta

@paso("GF_Contours")
def curvas(ruta, lm, glob):
    from geomorphic_reclamation_designer.core import surface
    n = surface.generar_contornos(ruta, lm, glob)
    assert n > 20, n
    maestras = sum(1 for f in lm.obtener_capa("GF_Contours").getFeatures()
                   if f["maestra"])
    assert maestras > 0
    print(f"      {n} curvas ({maestras} maestras)")

@paso("Corte/relleno + ráster de diferencias")
def cortefill(capa_dis, ruta, dem, g_lim, glob, lm):
    from geomorphic_reclamation_designer.core import surface
    cf = surface.corte_relleno(capa_dis, dem, g_lim, glob, lm)
    assert cf["corte_m3"] > 0 and cf["relleno_m3"] > 0
    assert 0 < cf["pct"] < 10000
    r = surface.raster_diferencia(ruta, dem, lm)
    assert r is not None and r.isValid()
    print(f"      corte={cf['corte_m3']:,.0f} m³ relleno={cf['relleno_m3']:,.0f} m³ "
          f"C/R={cf['pct']:.1f} %")
    return cf

@paso("Centroides y plan de acarreo")
def centr(cf, lm, glob):
    from geomorphic_reclamation_designer.core import surface
    reg, plan = surface.centroides(cf, 500.0, lm)
    assert reg, "sin regiones"
    txt = surface.informe_centroides(reg, plan, cf, glob)
    assert "Plan de movimiento" in txt
    print(f"      {len(reg)} regiones, {len(plan)} movimientos")

@paso("Informes de canal y resumen")
def informes(disenos, glob, g_lim):
    from geomorphic_reclamation_designer.gui.report_dialog import informe_canal, informe_resumen
    t1 = informe_canal(disenos["arroyo"])
    assert "estación" in t1 and "bankfull" in t1
    from geomorphic_reclamation_designer.core import setup_tools as st
    area = g_lim.area() / 10000.0
    dd = st.densidad_drenaje(sum(d.L_valle for d in disenos.values()), area)
    t2 = informe_resumen(disenos, glob, area, dd)
    assert "arroyo" in t2

@paso("Regeneración tras editar geometría (Releer)")
def releer(lm, dem, p):
    from geomorphic_reclamation_designer.core.builder import GeoFluvBuilder
    capa_v = lm.obtener_capa("GF_ValleyBottoms")
    c3 = p.canales[3]
    f = capa_v.getFeature(c3.fid_fondo_valle)
    g = f.geometry()
    pts = g.asPolyline()
    pts[0] = QgsPointXY(pts[0].x() + 30, pts[0].y() + 40)   # el usuario mueve la cabecera
    capa_v.dataProvider().changeGeometryValues(
        {f.id(): QgsGeometry.fromPolylineXY(pts)})
    b2 = GeoFluvBuilder(p, lm, dem)
    d2 = b2.construir()
    assert len(d2) == 4
    print(f"      regenerado: {sorted(d2)}")

@paso("Auto-perfil sobre selección")
def autoperfil(lm):
    from geomorphic_reclamation_designer.gui.auto_profile_dialog import aplicar_auto_perfil
    capa = lm.obtener_capa("GF_Ridges")
    ids = [f.id() for f in capa.getFeatures()][:1]
    capa.selectByIds(ids)
    n = aplicar_auto_perfil(capa, -10.0, -2.0, convexo_m=0.0)
    assert n == 1, n

# ---------------------------------------------------------------- ejecución
print("== TEST DE INTEGRACIÓN GEOFLUVQ (QGIS %s) ==" %
      __import__("qgis.core", fromlist=["Qgis"]).Qgis.QGIS_VERSION)
ruta_dem = crear_dem()
lm, dem = preparar(ruta_dem)
fid_lim, fids = entradas(lm)
g_lim = validaciones(lm, dem, fid_lim, fids)
p, disenos = construir(lm, dem, fid_lim, fids)
sub = subcuencas(disenos, g_lim, lm)
glob = crestas(disenos, sub, g_lim, dem, lm)
subcrestas(disenos, g_lim, glob, lm)
capa_dis, ruta_sup = superficie(lm, g_lim, dem, disenos, glob)
curvas(ruta_sup, lm, glob)
cf = cortefill(capa_dis, ruta_sup, dem, g_lim, glob, lm)
centr(cf, lm, glob)
informes(disenos, glob, g_lim)
releer(lm, dem, p)
autoperfil(lm)
print(f"\n== {len(PASOS_OK)}/15 PASOS SUPERADOS ==")
qgs.exitQgis()
