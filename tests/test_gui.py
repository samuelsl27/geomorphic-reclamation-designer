# -*- coding: utf-8 -*-
"""Smoke test de la GUI de GeoFluvQ (offscreen)."""
import os, sys, traceback
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, "/usr/share/qgis/python/plugins")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from qgis.core import QgsApplication
QgsApplication.setPrefixPath("/usr", True)
qgs = QgsApplication([], True)          # GUI=True para poder crear widgets
qgs.initQgis()

from unittest.mock import MagicMock

ok = 0
try:
    from geomorphic_reclamation_designer.gui.dock import GeoFluvDock
    iface = MagicMock()
    iface.mainWindow.return_value = None
    dock = GeoFluvDock(iface)
    # Setup · Channels · Output · DWG · AI Optimization. Eran 4 hasta que se
    # añadió la pestaña de optimización; el test se quedó atrás.
    rotulos = [dock.tabs.tabText(i) for i in range(dock.tabs.count())]
    assert rotulos == ["Setup", "Channels", "Output", "DWG",
                       "AI Optimization"], rotulos
    # ningún rótulo puede llevar la marca ajena (ADR-015 / ADR-016)
    assert not any("geofluv" in r.lower() for r in rotulos), rotulos
    # Estado inicial: flujo secuencial bloqueado. Sin límite no se puede elegir
    # canal principal; sin canal principal no hay Preview ni superficie.
    # (El antiguo btn_generar ya no existe: son btn_prev y btn_draw.)
    assert not dock.btn_canal.isEnabled(), "btn_canal sin límite"
    assert not dock.btn_prev.isEnabled(), "btn_prev sin canal principal"
    assert not dock.btn_draw.isEnabled(), "btn_draw sin canal principal"
    print("  ✔ Dock (%d pestañas, botones secuenciales)" % len(rotulos)); ok += 1

    from geomorphic_reclamation_designer.gui.settings_dialog import SettingsDialog
    from geomorphic_reclamation_designer.core.params import GlobalSettings, ChannelSettings
    s = GlobalSettings()
    dlg = SettingsDialog(s)
    dlg.sp_dd.setValue(88.0); dlg.aplicar()
    assert s.dd_objetivo == 88.0
    print("  ✔ SettingsDialog (round-trip de valores)"); ok += 1

    from geomorphic_reclamation_designer.gui.channel_dialog import ChannelSettingsDialog
    c = ChannelSettings()
    d2 = ChannelSettingsDialog(c, es_principal=True)
    d2.sp_sub.setValue(4)               # par → debe forzarse a impar
    d2.aplicar()
    assert c.espaciado_subcrestas % 2 == 1, c.espaciado_subcrestas
    print("  ✔ ChannelSettingsDialog (espaciado forzado a impar)"); ok += 1

    from geomorphic_reclamation_designer.gui.profile_dialog import ProfileDialog
    from geomorphic_reclamation_designer.core.profile import disenar_perfil
    p = disenar_perfil(300, 50, 30, -0.1, -0.02)
    d3 = ProfileDialog("test", p, [(0, 51), (300, 29)])
    d3.lienzo.exag = 2.0
    d3.lienzo.repaint()
    print("  ✔ ProfileDialog (render offscreen)"); ok += 1

    from geomorphic_reclamation_designer.gui.report_dialog import ReportDialog
    d4 = ReportDialog("t", "contenido")
    print("  ✔ ReportDialog"); ok += 1

    from geomorphic_reclamation_designer.gui.auto_profile_dialog import AutoPerfilDialog
    d5 = AutoPerfilDialog()
    print("  ✔ AutoPerfilDialog"); ok += 1

    from geomorphic_reclamation_designer.plugin import GeoFluvQPlugin
    pl = GeoFluvQPlugin(iface)
    pl.initGui()
    pl.unload()
    print("  ✔ Plugin initGui/unload"); ok += 1
except Exception:
    traceback.print_exc()
    sys.exit(1)
print(f"== GUI: {ok}/7 OK ==")
qgs.exitQgis()
