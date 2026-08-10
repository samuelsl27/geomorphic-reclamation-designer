# -*- coding: utf-8 -*-
"""Pruebas de core/checks.py que NO necesitan QGIS.

Se prueban las funciones de geometría y de criterio (las que deciden si algo
está bien o mal); las que recorren capas se prueban en QGIS sobre el caso real.
"""

import math
import os
import sys
import types

import importlib.util

# --- QGIS falso: las funciones que se prueban aquí no llegan a usarlo (solo
# lo tocan las que recorren capas, que se prueban en QGIS sobre el caso real),
# así que basta con que el import del módulo no reviente.
_q = types.ModuleType("qgis")
_c = types.ModuleType("qgis.core")


def _cualquier_clase(nombre):
    """Cualquier Qgs* que pidan los módulos importados sale como una clase
    vacía. Así este doble sirve también para los demás ficheros de prueba,
    que se lo encuentran ya registrado."""
    if nombre.startswith("_"):
        raise AttributeError(nombre)
    cls = type(nombre, (), {})
    setattr(_c, nombre, cls)
    return cls


_c.__getattr__ = _cualquier_clase
_q.core = _c
sys.modules.setdefault("qgis", _q)
sys.modules.setdefault("qgis.core", _c)

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "geomorphic_reclamation_designer", "core")


def _cargar(nombre, fichero):
    ruta = os.path.join(_DIR, fichero)
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = ""
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


_params = _cargar("gfq_params", "params.py")
# checks.py importa 'from .params import ...' y 'from . import setup_tools':
# se le dan los dos ya resueltos para no arrastrar compat.py (que sí necesita
# un QGIS real).
_st = types.ModuleType("gfq_setup_tools")
_st.evaluar_dd = lambda dd, obj, var: (
    "baja" if dd < obj * (1 - var / 100.0)
    else "alta" if dd > obj * (1 + var / 100.0) else "ok",
    obj * (1 - var / 100.0), obj * (1 + var / 100.0))
_st.cota_dem = lambda *a, **k: None

_ruta = os.path.join(_DIR, "checks.py")
_fuente = open(_ruta, encoding="utf-8").read()
# params.py no importa QGIS, asi que aqui se usa el de verdad: la definicion de
# "ladera norte o este" tiene que ser LA MISMA que usa el trazado.
_fuente = _fuente.replace(
    "from .params import (UMBRAL_PENDIENTE, es_orientacion_NE,\n"
    "                     rumbo_de_ladera)",
    "from gfq_params import (UMBRAL_PENDIENTE, es_orientacion_NE,\n"
    "                        rumbo_de_ladera)")
_fuente = _fuente.replace("from . import setup_tools as st", "")
ck = types.ModuleType("gfq_checks")
ck.st = _st
exec(compile(_fuente, _ruta, "exec"), ck.__dict__)

GlobalSettings = _params.GlobalSettings


# ------------------------------------------------------------------ geometría
def test_z_interpolada_en_el_cruce():
    """La cota en un punto del segmento se interpola linealmente: es lo que
    permite comparar dos líneas de rotura en su cruce."""
    pts = [(0.0, 0.0, 100.0), (10.0, 0.0, 110.0)]
    assert abs(ck._z_en(pts, 5.0, 0.0) - 105.0) < 1e-9
    assert abs(ck._z_en(pts, 0.0, 0.0) - 100.0) < 1e-9
    assert abs(ck._z_en(pts, 10.0, 0.0) - 110.0) < 1e-9
    # fuera del segmento se proyecta al extremo, no se extrapola
    assert abs(ck._z_en(pts, 20.0, 0.0) - 110.0) < 1e-9


def test_pendiente_recta_cresta_pie():
    pts = [(0.0, 0.0, 110.0), (0.0, 100.0, 100.0)]
    assert abs(ck._pendiente_recta_pct(pts) - 10.0) < 1e-9
    # sin Z no se puede calcular
    assert ck._pendiente_recta_pct([(0, 0, None), (0, 10, 5)]) is None


def test_rumbo_y_orientacion_NE():
    """El ajuste 'North or East straight-line slopes' cubre de 315° a 135°."""
    assert abs(ck._rumbo([(0, 0, 0), (0, 10, 0)]) - 0.0) < 1e-9      # norte
    assert abs(ck._rumbo([(0, 0, 0), (10, 0, 0)]) - 90.0) < 1e-9     # este
    assert abs(ck._rumbo([(0, 0, 0), (0, -10, 0)]) - 180.0) < 1e-9   # sur
    assert ck._es_NE(0.0) and ck._es_NE(90.0) and ck._es_NE(320.0)
    assert not ck._es_NE(180.0) and not ck._es_NE(200.0)


# -------------------------------------------------------------------- Rosgen
def test_clasificacion_rosgen_por_pendiente():
    assert ck.clasificar_rosgen(0.15, 8, 1.2) == "Aa+"
    assert ck.clasificar_rosgen(0.06, 8, 1.2) == "A"
    assert ck.clasificar_rosgen(0.03, 15, 1.8) == "B"
    assert ck.clasificar_rosgen(0.01, 15, 3.0) == "C"


class _Perfil:
    def __init__(self, s_cab, s_boca, z0, z1, L, ajustado=True):
        self.s_cabecera, self.s_boca = s_cab, s_boca
        self.ajustado = ajustado
        self._z0, self._z1, self._L = z0, z1, L

    def z(self, s):
        return self._z0 + (self._z1 - self._z0) * (s / self._L)

    def pendiente(self, s):
        return self.s_cabecera


class _Ajustes:
    def __init__(self, **kw):
        self.pendiente_cabecera_pct = kw.get("pend_cab", -12.0)
        self.vel_max_agua = kw.get("vel", 1.4)
        self.sinuosidad_mayor_004 = kw.get("sinA", 1.15)
        self.espaciado_subcrestas = kw.get("esp", 3)
        self.nombre = kw.get("nombre", "main")
        self.cota_boca = kw.get("cota_boca", 1000.0)


class _Diseno:
    def __init__(self, nombre="main", secciones=None, perfil=None,
                 settings=None, dd=75.0, L=400.0):
        self.nombre = nombre
        self.secciones = secciones or []
        self.perfil = perfil
        self.settings = settings or _Ajustes()
        self.dd_m_ha = dd
        self.L_valle = L
        self.puntos = []


def _seccion(s, pend_pct, wd, entr, vel=1.0, tau="ok", ratio=0.5):
    return {"estacion": s, "pendiente": pend_pct, "wd_usado": wd,
            "entrench": entr, "vel_man": vel, "estab_tau": tau,
            "ratio_tau": ratio, "x": 0.0, "y": 0.0}


def test_seccion_fuera_del_rango_rosgen():
    """Un tramo de pendiente 6 % es tipo A: su W:D debe estar por debajo de
    12. Con 20 el diseño se sale del tipo y hay que avisar."""
    d = _Diseno(secciones=[_seccion(0, -6.0, 20.0, 1.2),
                           _seccion(10, -6.0, 20.0, 1.2)])
    h = ck.secciones_fuera_de_rango([d])
    assert len(h) == 1 and h[0].codigo == "C33"
    assert "width:depth" in h[0].titulo
    # dentro de rango no avisa
    d2 = _Diseno(secciones=[_seccion(0, -6.0, 10.0, 1.2)])
    assert ck.secciones_fuera_de_rango([d2]) == []


def test_velocidad_por_encima_del_maximo():
    d = _Diseno(secciones=[_seccion(0, -2.0, 12.5, 3.0, vel=1.0),
                           _seccion(10, -2.0, 12.5, 3.0, vel=2.1)],
                settings=_Ajustes(vel=1.4))
    h = ck.velocidad_excedida([d])
    assert len(h) == 1 and h[0].codigo == "C31"
    assert abs(h[0].valor - 2.1) < 1e-9


def test_tension_tractiva_resume_el_peor_tramo():
    d = _Diseno(secciones=[_seccion(0, -2.0, 12.5, 3.0, tau="high", ratio=1.4),
                           _seccion(10, -2.0, 12.5, 3.0, tau="high", ratio=2.2),
                           _seccion(20, -2.0, 12.5, 3.0)])
    h = ck.tension_tractiva([d])
    assert len(h) == 1 and h[0].gravedad == "error"
    assert abs(h[0].valor - 2.2) < 1e-9


def test_sinuosidad_de_canal_A():
    g = GlobalSettings()
    g.sinuosidad_canal_A = 1.30
    d = _Diseno(settings=_Ajustes(sinA=1.25))
    h = ck.sinuosidad_canal_A([d], g)
    assert len(h) == 2 and all(x.codigo == "C32" for x in h)
    g.sinuosidad_canal_A = 1.15
    assert ck.sinuosidad_canal_A([_Diseno(settings=_Ajustes(sinA=1.15))], g) == []


def test_densidad_de_drenaje_global_y_por_subcuenca():
    g = GlobalSettings()
    g.dd_objetivo, g.dd_varianza_pct = 75.0, 20.0     # rango 60-90
    d_ok = _Diseno("a", dd=80.0)
    d_baja = _Diseno("b", dd=40.0)
    h = ck.densidad_de_drenaje([d_ok, d_baja], g, dd_global=78.0)
    codigos = [x.codigo for x in h]
    assert "C34" in codigos                 # la subcuenca baja
    assert not any(x.codigo == "C34" and "'a'" in x.detalle for x in h)
    # global fuera de rango
    h2 = ck.densidad_de_drenaje([], g, dd_global=120.0)
    assert len(h2) == 1 and h2[0].codigo == "C34"


def test_uniformidad_de_densidad():
    """Las dos subcuencas están dentro del objetivo, pero muy desiguales
    entre sí: eso es lo que el módulo pide comprobar aparte."""
    g = GlobalSettings()
    g.dd_objetivo, g.dd_varianza_pct = 75.0, 20.0
    h = ck.densidad_de_drenaje([_Diseno("a", dd=61.0)], g, dd_global=89.0)
    assert [x.codigo for x in h] == ["C35"]


def test_espaciado_par_de_subcrestas():
    p = types.SimpleNamespace(canales=[_Ajustes(esp=4, nombre="main")])
    h = ck.ajustes_incoherentes(p, GlobalSettings())
    assert any(x.codigo == "C04" and x.limite == 5 for x in h)
    p2 = types.SimpleNamespace(canales=[_Ajustes(esp=3, nombre="main")])
    assert not any(x.codigo == "C04"
                   for x in ck.ajustes_incoherentes(p2, GlobalSettings()))


def test_cota_de_boca_sin_especificar():
    p = types.SimpleNamespace(canales=[_Ajustes(esp=3, cota_boca=None)])
    h = ck.ajustes_incoherentes(p, GlobalSettings())
    assert any(x.codigo == "C05" for x in h)


def test_perfil_ajustado_sugiere_la_cota_que_lo_resuelve():
    """El original no solo avisa: propone el valor que haría compatible la
    entrada. Aquí se comprueba que la cota sugerida es la que sale de la
    parábola con la pendiente pedida."""
    g = GlobalSettings()
    g.tol_pendiente_cabecera_pct = 0.5
    L, z_boca = 400.0, 1000.0
    perfil = _Perfil(-0.08, -0.02, 1030.0, z_boca, L)   # real 8 %, pedida 12 %
    d = _Diseno(perfil=perfil, settings=_Ajustes(pend_cab=-12.0), L=L)
    h = ck.perfil_ajustado([d], g)
    assert len(h) == 1 and h[0].codigo == "C02"
    z_sug = z_boca - L * (-0.12 + -0.02) / 2.0
    assert f"{z_sug:.2f}" in h[0].sugerencia
    # dentro de tolerancia no avisa
    perfil2 = _Perfil(-0.12, -0.02, 1030.0, z_boca, L)
    d2 = _Diseno(perfil=perfil2, settings=_Ajustes(pend_cab=-12.0), L=L)
    assert ck.perfil_ajustado([d2], g) == []


def test_balance_de_tierras():
    g = GlobalSettings()
    g.var_min_corte_relleno_pct, g.var_max_corte_relleno_pct = 80.0, 125.0
    dentro = ck.balance_de_tierras({"pct": 100.0, "corte_ajustado_m3": 1000,
                                    "relleno_ajustado_m3": 1000}, g)
    assert dentro[0].gravedad == "info"
    fuera = ck.balance_de_tierras({"pct": 60.0, "corte_ajustado_m3": 600,
                                   "relleno_ajustado_m3": 1000}, g)
    assert fuera[0].gravedad == "warning"
    assert "400 m3 of fill are missing" in fuera[0].detalle


def test_resumen_y_orden():
    hs = [ck.Hallazgo("Z", "info", ck.G_HIDRA, "i"),
          ck.Hallazgo("A", "error", ck.G_ROTURA, "e"),
          ck.Hallazgo("M", "warning", ck.G_LADERA, "w")]
    assert ck.resumen(hs) == (1, 1, 1)
    hs.sort(key=lambda h: ck.ORDEN_GRAVEDAD[h.gravedad])
    assert [h.gravedad for h in hs] == ["error", "warning", "info"]


# ------------------------------------------------- sellado de laderas
# `topology._sellar_extremo` delega el reparto de la correccion en
# `divides.ajustar_extremo`: las dos hacian lo mismo y tenerlo duplicado ya
# costo que la mezcla adaptativa se anadiera a una copia y no a la otra. Para
# que el test siga probando el codigo REAL y no un doble, se carga tambien
# divides.py con sus importaciones relativas neutralizadas y se enchufa por el
# mismo sitio.
_fdiv = os.path.join(_DIR, "divides.py")
_srcd = open(_fdiv, encoding="utf-8").read().replace(
    "from .compat import attrs, indices_datos",
    "attrs = lambda capa, v: v\nindices_datos = lambda capa: []").replace(
    "from .ridges import convexo_subcresta", "convexo_subcresta = None")
_div = types.ModuleType("grd_divides_para_topology")
exec(compile(_srcd, _fdiv, "exec"), _div.__dict__)
sys.modules["grd_divides_para_topology"] = _div

_ftopo = os.path.join(_DIR, "topology.py")
_src = open(_ftopo, encoding="utf-8").read().replace(
    "from .compat import attrs", "attrs = lambda capa, v: v").replace(
    "from .divides import ajustar_extremo",
    "from grd_divides_para_topology import ajustar_extremo")
topo = types.ModuleType("gfq_topology")
exec(compile(_src, _ftopo, "exec"), topo.__dict__)


def test_sellado_reparte_la_correccion_y_deja_la_ladera_monotona():
    """Bajar solo el ultimo vertice dejaba el penultimo por encima: en una
    ladera corta eso es un pico de varios metros en dos metros de recorrido,
    que es el diente que luego sale en el TIN. Lo detecto Check Design (C12)
    sobre el caso real."""
    pts = [(0.0, 0.0, 1060.0), (0.0, 2.0, 1086.0), (0.0, 4.0, 1090.0)]
    out = topo._sellar_extremo(pts, 1070.0)
    assert abs(out[-1][2] - 1070.0) < 1e-9
    zs = [p[2] for p in out]
    assert zs == sorted(zs), f"la ladera no es monotona: {zs}"
    assert max(zs) <= 1070.0 + 1e-9
    # el pie no se mueve cuando la linea es mas larga que la mezcla
    largos = [(0.0, float(i), 1000.0 + i) for i in range(0, 60, 2)]
    out2 = topo._sellar_extremo(largos, largos[-1][2] - 3.0, mezcla=20.0)
    assert abs(out2[0][2] - largos[0][2]) < 1e-9
    assert abs(out2[-1][2] - (largos[-1][2] - 3.0)) < 1e-9
    zs2 = [p[2] for p in out2]
    assert zs2 == sorted(zs2)


def test_sellado_hacia_arriba_no_rompe_la_monotonia():
    pts = [(0.0, 0.0, 1000.0), (0.0, 10.0, 1005.0), (0.0, 20.0, 1008.0)]
    out = topo._sellar_extremo(pts, 1012.0)
    zs = [p[2] for p in out]
    assert zs == sorted(zs) and abs(zs[-1] - 1012.0) < 1e-9


# ------------------------- empalme de subcrestas con su divisoria
def test_el_extremo_que_muere_en_la_divisoria_se_mide_no_se_supone():
    """Hasta la v1.0.18 se suponia que era `pts[-1]`, con el comentario
    'arranca siempre en el cauce'. Deja de ser cierto en cuanto `divides`
    parte o invierte una linea, y no lo es NUNCA para las lineas de encuentro
    (channel = 'junction'), que van de alto a bajo. Cuando falla, el sellado
    sube el PIE a la cota de la divisoria y fuerza monotonia despues: la linea
    entera queda del reves."""
    divisorias = {1: [(100.0, -50.0, 320.0), (100.0, 50.0, 320.0)]}
    #     pie en x=0 (lejos de la divisoria), cabecera en x=98 (a 2 m de ella)
    normal = [(0.0, 0.0, 280.0), (50.0, 0.0, 300.0), (98.0, 0.0, 319.0)]
    pt, en_inicio, proy = topo._extremo_hacia_divisoria(normal, None, divisorias)
    assert pt == normal[-1] and en_inicio is False
    assert proy is not None and proy[0] < 2.5
    # la MISMA linea al reves tiene que dar el MISMO extremo
    pt2, en_inicio2, _ = topo._extremo_hacia_divisoria(
        list(reversed(normal)), None, divisorias)
    assert pt2 == normal[-1] and en_inicio2 is True


def test_sin_divisorias_no_se_inventa_un_extremo():
    pt, en_inicio, proy = topo._extremo_hacia_divisoria(
        [(0.0, 0.0, 1.0), (1.0, 0.0, 2.0)], None, {})
    assert pt == (1.0, 0.0, 2.0) and en_inicio is False and proy is None


def test_las_proyecciones_vienen_ordenadas_por_distancia():
    """`empalmar_en_divisorias` necesita poder descartar la divisoria mas
    proxima en planta —si esta a una cota imposible— y probar la siguiente."""
    geoms = {1: [(10.0, -5.0, 300.0), (10.0, 5.0, 300.0)],
             2: [(30.0, -5.0, 310.0), (30.0, 5.0, 310.0)],
             3: [(60.0, -5.0, 330.0), (60.0, 5.0, 330.0)]}
    cand = topo._proyecciones(None, geoms, (0.0, 0.0, 295.0))
    assert [c[1] for c in cand] == [1, 2, 3]
    assert [round(c[0]) for c in cand] == [10, 30, 60]


def test_no_se_empalma_contra_una_divisoria_a_cota_imposible():
    """La comprobacion que evita el muro vertical. Medido en el Ej_2: una
    subcresta subia de 300.7 a 336.0 m en 3.69 m de recorrido, un 955 %. El
    original no pasa de 65.7 % en ninguna de sus 244 lineas de cresta."""
    alto = (0.0, 0.0, 300.7)
    geoms = {1: [(3.69, -5.0, 336.0), (3.69, 5.0, 336.0)],   # 955 %: se rechaza
             2: [(40.0, -5.0, 305.0), (40.0, 5.0, 305.0)]}   # 10.8 %: vale
    elegida = None
    for d_xy, fid, punto in topo._proyecciones(None, geoms, alto):
        if d_xy < 0.5 or d_xy > topo.TOL_EMPALME:
            continue
        if abs(punto[2] - alto[2]) > topo.MAX_PENDIENTE_EMPALME * d_xy:
            continue
        elegida = fid
        break
    # la segunda queda fuera de TOL_EMPALME (18 m), asi que NO se empalma:
    # mejor un hueco en planta, que el TIN resuelve, que un muro de 35 m
    assert elegida is None
