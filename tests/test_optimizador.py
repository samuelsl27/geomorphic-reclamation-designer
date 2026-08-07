# -*- coding: utf-8 -*-
"""Pruebas puras (sin QGIS) de la lógica de optimización IA."""
import sys, types, importlib.util, os

_q = types.ModuleType("qgis"); _c = types.ModuleType("qgis.core")
for _n in ("QgsProject", "QgsRasterLayer", "QgsGeometry", "QgsPointXY"):
    setattr(_c, _n, type(_n, (), {}))
_q.core = _c
sys.modules.setdefault("qgis", _q); sys.modules.setdefault("qgis.core", _c)
_ruta = os.path.join(os.path.dirname(__file__), "..", "src", "geomorphic_reclamation_designer", "core", "ai_optimizer.py")
_spec = importlib.util.spec_from_file_location("aiopt", _ruta)
opt = importlib.util.module_from_spec(_spec)
opt.__package__ = ""
_spec.loader.exec_module(opt)

BASE = {"cut_m3": 100000.0, "fill_m3": 100000.0, "net_m3": 0.0,
        "ratio_pct": 100.0, "dozer_idx": 0.30, "lineas_total": 80,
        "lineas_fuera_pendiente": 0, "secciones": 100,
        "secciones_tau_alto": 0, "dd_media": 80, "dd_objetivo": 80}


def test_rango_respeta_limites_fisicos():
    lo, hi = opt.rango_de(-2.0, 25.0, -10.0, -0.3)
    assert (round(lo, 3), round(hi, 3)) == (-2.5, -1.5)
    lo, hi = opt.rango_de(-2.0, 900.0, -10.0, -0.3)
    assert lo >= -10.0 and hi <= -0.3


def test_equilibrio_perfecto_puntua_uno():
    s, det = opt.puntuar(BASE, {"equilibrio": True}, 5.0)
    assert s == 1.0 and det["equilibrio"] == 1.0


def test_desequilibrio_penaliza():
    """Penaliza, pero de forma GRADUAL: acercarse tiene que notarse."""
    peor = dict(BASE); peor["net_m3"] = -50000.0
    medio = dict(BASE); medio["net_m3"] = -20000.0
    cerca = dict(BASE); cerca["net_m3"] = -4000.0
    s_peor, _ = opt.puntuar(peor, {"equilibrio": True}, 5.0)
    s_medio, _ = opt.puntuar(medio, {"equilibrio": True}, 5.0)
    s_cerca, _ = opt.puntuar(cerca, {"equilibrio": True}, 5.0)
    assert 0.0 < s_peor < s_medio < s_cerca == 1.0


def test_objetivo_lejano_no_se_anula():
    """Dos diseños malos no pueden puntuar igual: si no, la búsqueda es ciega
    y no sabe que se está acercando (fallo detectado en la prueba real)."""
    lejos = dict(BASE); lejos["fill_m3"] = 3546471.0
    cerca = dict(BASE); cerca["fill_m3"] = 3385272.0
    s1, _ = opt.puntuar(lejos, {"fill_objetivo": 3250000.0}, 3.0)
    s2, _ = opt.puntuar(cerca, {"fill_objetivo": 3250000.0}, 3.0)
    assert 0.0 < s1 < s2 < 1.0


def test_indice_dozer():
    bueno = dict(BASE); bueno["dozer_idx"] = 0.4
    malo = dict(BASE); malo["dozer_idx"] = -0.4
    s1, _ = opt.puntuar(bueno, {"cut_alto_fill_bajo": True}, 5.0)
    s2, _ = opt.puntuar(malo, {"cut_alto_fill_bajo": True}, 5.0)
    assert s1 == 1.0 and s2 == 0.0


def test_objetivo_volumen_dentro_de_tolerancia():
    s, _ = opt.puntuar(BASE, {"fill_objetivo": 102000.0}, 5.0)
    assert s == 1.0
    s, _ = opt.puntuar(BASE, {"fill_objetivo": 200000.0}, 5.0)
    assert s < 0.5


def test_pendientes_fuera_reducen_la_nota():
    m = dict(BASE); m["lineas_fuera_pendiente"] = 40
    s, _ = opt.puntuar(m, {"pendientes_ok": True}, 5.0)
    assert abs(s - 0.5) < 1e-9


def test_desplazamiento_conserva_los_extremos():
    pts = [(0, 0), (10, 0), (20, 0), (30, 0), (40, 0)]
    out = opt.Evaluador._desplazar(pts, [0, 5, 10, 5, 0])
    assert out[0] == (0.0, 0.0) and out[-1] == (40.0, 0.0)
    assert abs(out[2][1] - 10.0) < 1e-6


def test_json_del_modelo_con_texto_alrededor():
    from importlib.util import spec_from_file_location, module_from_spec
    r = os.path.join(os.path.dirname(__file__), "..", "src", "geomorphic_reclamation_designer", "core", "ai_client.py")
    sp = spec_from_file_location("aicli", r)
    cli = module_from_spec(sp); cli.__package__ = ""
    sp.loader.exec_module(cli)
    d = cli.extraer_json('Claro, aquí tienes:\n```json\n{"global": {"a": 1}}\n```\nEso es todo.')
    assert d == {"global": {"a": 1}}
    d = cli.extraer_json('blah {"reasoning": "x", "global": {}} fin')
    assert d["reasoning"] == "x"
