# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pestaña 'AI Optimization' — OPCIONAL.

Se conecta a un modelo que corra EN LOCAL (Ollama o LM Studio). Si no hay
servidor, la pestaña queda deshabilitada con un aviso y un botón de reintento:
el resto del complemento funciona exactamente igual.

Estructura:
  1. Modelo local: escanear, elegir servidor y modelo, temperatura, contexto.
  2. Objetivos: qué se quiere conseguir (varios a la vez).
  3. Variables que la IA puede alterar, con rango de desviación.
  4. Botones de ajustes: uno para los globales y uno por canal, donde se marca
     variable a variable si puede cambiar y con qué % de desviación.
  5. Ejecución: iteraciones, tolerancia, paso de malla, registro en vivo.
"""

import os

from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal, QTimer
from qgis.PyQt.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QDoubleSpinBox, QSpinBox, QGroupBox, QPlainTextEdit,
    QDialog, QDialogButtonBox, QScrollArea, QProgressBar,
    QMessageBox, QFileDialog, QSplitter,
)

from ..core import ai_client
from ..core.ai_optimizer import (
    VARIABLES_GLOBALES, VARIABLES_CANAL, OBJETIVOS, rango_de, Candidato,
    Evaluador, Optimizador, carpeta_optimizacion,
)
from ..core.ai_context import ContextoIA


# ------------------------------------------------------------------ diálogos
class VariablesDialog(QDialog):
    """Marca qué ajustes puede alterar la IA y con qué % de desviación."""

    def __init__(self, titulo, registro, objeto, estado, parent=None):
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.registro = registro
        self.objeto = objeto
        self.estado = estado          # {clave: {'on': bool, 'pct': float}}
        self.filas = {}
        v = QVBoxLayout(self)
        v.addWidget(QLabel(
            "Marca los ajustes que la optimización puede modificar y el "
            "porcentaje de desviación permitido sobre el valor actual.\n"
            "El rango efectivo se recorta además a los límites físicos de cada "
            "variable."))
        sc = QScrollArea(); sc.setWidgetResizable(True)
        inner = QWidget(); g = QGridLayout(inner)
        g.addWidget(QLabel("<b>Setting</b>"), 0, 0)
        g.addWidget(QLabel("<b>Current</b>"), 0, 1)
        g.addWidget(QLabel("<b>Can change</b>"), 0, 2)
        g.addWidget(QLabel("<b>Deviation ±%</b>"), 0, 3)
        g.addWidget(QLabel("<b>Resulting range</b>"), 0, 4)
        for i, (clave, (etiqueta, lo, hi, tipo)) in enumerate(registro.items(), 1):
            actual = getattr(objeto, clave, None)
            st = estado.get(clave, {})
            chk = QCheckBox(); chk.setChecked(bool(st.get("on", False)))
            sp = QDoubleSpinBox(); sp.setRange(1.0, 300.0); sp.setSuffix(" %")
            sp.setValue(float(st.get("pct", 20.0)))
            lb_rango = QLabel("")
            g.addWidget(QLabel(etiqueta), i, 0)
            g.addWidget(QLabel("—" if actual is None else f"{actual:g}"), i, 1)
            g.addWidget(chk, i, 2)
            g.addWidget(sp, i, 3)
            g.addWidget(lb_rango, i, 4)
            self.filas[clave] = (chk, sp, lb_rango, actual, lo, hi)

            def act(_=None, c=clave):
                ch, s, lbr, a, l, h = self.filas[c]
                r = rango_de(a if a is not None else (l + h) / 2, s.value(), l, h)
                lbr.setText(f"[{r[0]:.4g} … {r[1]:.4g}]")
            sp.valueChanged.connect(act)
            act()
        sc.setWidget(inner)
        v.addWidget(sc)
        h = QHBoxLayout()
        b1 = QPushButton("Select all"); b1.clicked.connect(
            lambda: [f[0].setChecked(True) for f in self.filas.values()])
        b2 = QPushButton("Select none"); b2.clicked.connect(
            lambda: [f[0].setChecked(False) for f in self.filas.values()])
        h.addWidget(b1); h.addWidget(b2); h.addStretch(1)
        v.addLayout(h)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        v.addWidget(bb)
        self.resize(860, 560)

    def resultado(self):
        return {k: {"on": f[0].isChecked(), "pct": f[1].value()}
                for k, f in self.filas.items()}


class VentanaRegistro(QDialog):
    """Copia del registro en una ventana propia, redimensionable a pantalla
    completa. Se abre con 'Open log in a window' y sigue recibiendo los
    mensajes en directo mientras la optimización avanza."""

    def __init__(self, texto_inicial="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Optimization — log")
        self.setWindowFlags(self.windowFlags()
                            | Qt.WindowType.WindowMaximizeButtonHint
                            | Qt.WindowType.WindowMinimizeButtonHint)
        self.setModal(False)
        self.setSizeGripEnabled(True)
        v = QVBoxLayout(self)
        self.txt = QPlainTextEdit()
        self.txt.setReadOnly(True)
        self.txt.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.txt.setPlainText(texto_inicial)
        v.addWidget(self.txt, 1)
        h = QHBoxLayout()
        b_copiar = QPushButton("Copy all")
        b_copiar.clicked.connect(self._copiar)
        b_guardar = QPushButton("Save to file...")
        b_guardar.clicked.connect(self._guardar)
        self.chk_wrap = QCheckBox("Wrap long lines")
        self.chk_wrap.toggled.connect(
            lambda on: self.txt.setLineWrapMode(
                QPlainTextEdit.LineWrapMode.WidgetWidth if on
                else QPlainTextEdit.LineWrapMode.NoWrap))
        h.addWidget(b_copiar); h.addWidget(b_guardar)
        h.addWidget(self.chk_wrap); h.addStretch(1)
        v.addLayout(h)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.close)
        v.addWidget(bb)
        self.resize(900, 620)

    def anadir(self, txt):
        self.txt.appendPlainText(txt)
        self.txt.verticalScrollBar().setValue(
            self.txt.verticalScrollBar().maximum())

    def _copiar(self):
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.clipboard().setText(self.txt.toPlainText())

    def _guardar(self):
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Save log", "geofluv_optimization_log.txt", "Text (*.txt)")
        if ruta:
            try:
                with open(ruta, "w", encoding="utf-8") as fh:
                    fh.write(self.txt.toPlainText())
            except Exception:
                pass


class HiloEscaneo(QThread):
    """Escaneo de servidores de IA en segundo plano: aunque los sondeos de
    puerto sean cortos, sumados bloquearían la interfaz un par de segundos."""
    listo = pyqtSignal(object)

    def run(self):
        try:
            from ..core import ai_client as _c
            self.listo.emit(_c.detectar_servidores())
        except Exception:
            self.listo.emit([])


# ------------------------------------------------------------------ hilo
class HiloOptimizacion(QThread):
    mensaje = pyqtSignal(str)
    terminado = pyqtSignal(object)

    def __init__(self, optimizador, candidato):
        super().__init__()
        self.opt = optimizador
        self.cand = candidato
        self._cancelar = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        self.opt.log = lambda t: self.mensaje.emit(str(t))
        self.opt.ev.log = self.opt.log
        self.opt.cancelado = lambda: self._cancelar
        try:
            mejor = self.opt.ejecutar(self.cand)
        except Exception as e:
            import traceback
            self.mensaje.emit("ERROR: " + str(e))
            self.mensaje.emit(traceback.format_exc())
            mejor = None
        self.terminado.emit(mejor)


# ------------------------------------------------------------------ pestaña
class AITab(QWidget):

    def __init__(self, dock, parent=None):
        super().__init__(parent)
        self.dock = dock
        self.servidores = []
        self.estado_global = {}
        self.estado_canales = {}
        self.hilo = None
        self._escaneado = False
        self.ventana_log = None
        self._construir()
        # NO se escanea la red aquí: abrir el panel debe ser instantáneo. El
        # escaneo se hace la primera vez que se muestra la pestaña (o con el
        # botón), y en diferido para no bloquear el dibujado.

    def showEvent(self, ev):
        super().showEvent(ev)
        if not self._escaneado:
            self._escaneado = True
            QTimer.singleShot(50, lambda: self.buscar_modelos(True))

    # ---------------- interfaz ----------------
    def _construir(self):
        v = QVBoxLayout(self)

        # --- 1. modelo ---
        g1 = QGroupBox("1 · Local AI model  (optional — the plugin works without it)")
        f1 = QGridLayout(g1)
        self.btn_scan = QPushButton("Scan for local models")
        self.btn_scan.clicked.connect(lambda: self.buscar_modelos(False))
        f1.addWidget(self.btn_scan, 0, 0)
        self.lb_estado = QLabel("Not scanned yet.")
        f1.addWidget(self.lb_estado, 0, 1, 1, 3)
        f1.addWidget(QLabel("Server:"), 1, 0)
        self.cb_srv = QComboBox(); self.cb_srv.currentIndexChanged.connect(self._srv_cambiado)
        f1.addWidget(self.cb_srv, 1, 1)
        f1.addWidget(QLabel("Model:"), 1, 2)
        self.cb_mod = QComboBox()
        self.cb_mod.currentTextChanged.connect(self._mod_cambiado)
        f1.addWidget(self.cb_mod, 1, 3)
        f1.addWidget(QLabel("Temperature:"), 2, 0)
        self.sp_temp = QDoubleSpinBox(); self.sp_temp.setRange(0.0, 1.5)
        self.sp_temp.setSingleStep(0.05); self.sp_temp.setValue(0.2)
        f1.addWidget(self.sp_temp, 2, 1)
        f1.addWidget(QLabel("Context (tokens):"), 2, 2)
        self.sp_ctx = QSpinBox(); self.sp_ctx.setRange(2048, 262144)
        self.sp_ctx.setSingleStep(2048); self.sp_ctx.setValue(32768)
        f1.addWidget(self.sp_ctx, 2, 3)
        self.chk_img = QCheckBox("Send design and cut/fill images to the model "
                                 "(needs a vision model)")
        self.chk_img.setChecked(True)
        f1.addWidget(self.chk_img, 3, 0, 1, 3)
        self.chk_web = QCheckBox("Allow web search for reference data")
        f1.addWidget(self.chk_web, 3, 3)
        self.chk_think = QCheckBox("Enable model reasoning / thinking "
                                   "(Qwen3, DeepSeek-R1…): slower but better "
                                   "decisions; the reasoning is logged")
        self.chk_think.setChecked(True)
        f1.addWidget(self.chk_think, 5, 0, 1, 4)
        self.lb_modelo = QLabel("")
        f1.addWidget(self.lb_modelo, 4, 0, 1, 4)
        # g1 se añade al divisor al final

        # --- 2. objetivos ---
        g2 = QGroupBox("2 · Goals  (several can be active at the same time)")
        f2 = QGridLayout(g2)
        self.chk_fill = QCheckBox(OBJETIVOS["fill_objetivo"])
        self.sp_fill = QDoubleSpinBox(); self.sp_fill.setRange(0, 1e9)
        self.sp_fill.setSuffix(" m3"); self.sp_fill.setDecimals(0)
        self.sp_fill.setSingleStep(1000)
        f2.addWidget(self.chk_fill, 0, 0); f2.addWidget(self.sp_fill, 0, 1)
        self.chk_cut = QCheckBox(OBJETIVOS["cut_objetivo"])
        self.sp_cut = QDoubleSpinBox(); self.sp_cut.setRange(0, 1e9)
        self.sp_cut.setSuffix(" m3"); self.sp_cut.setDecimals(0)
        self.sp_cut.setSingleStep(1000)
        f2.addWidget(self.chk_cut, 1, 0); f2.addWidget(self.sp_cut, 1, 1)
        self.chk_eq = QCheckBox(OBJETIVOS["equilibrio"]); self.chk_eq.setChecked(True)
        f2.addWidget(self.chk_eq, 2, 0, 1, 2)
        self.chk_dozer = QCheckBox(OBJETIVOS["cut_alto_fill_bajo"])
        self.chk_dozer.setChecked(True)
        f2.addWidget(self.chk_dozer, 3, 0, 1, 2)
        self.chk_haul = QCheckBox(OBJETIVOS["minimo_acarreo"])
        f2.addWidget(self.chk_haul, 4, 0, 1, 2)
        self.chk_slope = QCheckBox(OBJETIVOS["pendientes_ok"])
        self.chk_slope.setChecked(True)
        f2.addWidget(self.chk_slope, 0, 2, 1, 2)
        self.chk_dd = QCheckBox(OBJETIVOS["dd_objetivo"])
        f2.addWidget(self.chk_dd, 1, 2, 1, 2)
        self.chk_tau = QCheckBox(OBJETIVOS["tractiva_ok"])
        f2.addWidget(self.chk_tau, 2, 2, 1, 2)
        # g2 se añade al divisor al final

        # --- 3. variables ---
        g3 = QGroupBox("3 · What the optimisation may change")
        f3 = QGridLayout(g3)
        self.chk_xy = QCheckBox("Channel plan geometry (X, Y)")
        self.sp_xy = QDoubleSpinBox(); self.sp_xy.setRange(0.5, 200.0)
        self.sp_xy.setValue(10.0); self.sp_xy.setSuffix(" m max. shift")
        f3.addWidget(self.chk_xy, 0, 0); f3.addWidget(self.sp_xy, 0, 1)
        self.chk_z = QCheckBox("Channel profile: slopes and vertical curve")
        self.sp_z = QDoubleSpinBox(); self.sp_z.setRange(1.0, 200.0)
        self.sp_z.setValue(25.0); self.sp_z.setSuffix(" % deviation")
        f3.addWidget(self.chk_z, 1, 0); f3.addWidget(self.sp_z, 1, 1)
        self.chk_perf = QCheckBox("Ridge and swale longitudinal profiles")
        self.sp_perf = QDoubleSpinBox(); self.sp_perf.setRange(1.0, 200.0)
        self.sp_perf.setValue(25.0); self.sp_perf.setSuffix(" % deviation")
        f3.addWidget(self.chk_perf, 2, 0); f3.addWidget(self.sp_perf, 2, 1)
        self.chk_lim = QCheckBox("May go beyond the design boundary")
        self.sp_lim = QDoubleSpinBox(); self.sp_lim.setRange(1.0, 500.0)
        self.sp_lim.setValue(15.0); self.sp_lim.setSuffix(" m")
        self.cb_lim = QComboBox(); self.cb_lim.addItems(["lower part", "upper part"])
        f3.addWidget(self.chk_lim, 3, 0); f3.addWidget(self.sp_lim, 3, 1)
        f3.addWidget(self.cb_lim, 3, 2)
        self.btn_glob = QPushButton("Global Settings the AI may change...")
        self.btn_glob.clicked.connect(self._editar_globales)
        f3.addWidget(self.btn_glob, 4, 0, 1, 2)
        self.cont_canales = QHBoxLayout()
        f3.addLayout(self.cont_canales, 5, 0, 1, 3)
        # g3 se añade al divisor al final

        # --- 4. ejecución ---
        g4 = QGroupBox("4 · Run")
        f4 = QGridLayout(g4)
        f4.addWidget(QLabel("Iterations:"), 0, 0)
        self.sp_iter = QSpinBox(); self.sp_iter.setRange(1, 500)
        self.sp_iter.setValue(10)
        f4.addWidget(self.sp_iter, 0, 1)
        f4.addWidget(QLabel("Allowed error (tolerance):"), 0, 2)
        self.sp_tol = QDoubleSpinBox(); self.sp_tol.setRange(0.1, 50.0)
        self.sp_tol.setValue(5.0); self.sp_tol.setSuffix(" %")
        f4.addWidget(self.sp_tol, 0, 3)
        f4.addWidget(QLabel("Volume mesh step:"), 1, 0)
        self.sp_malla = QDoubleSpinBox(); self.sp_malla.setRange(0.25, 20.0)
        self.sp_malla.setValue(2.0); self.sp_malla.setSuffix(" m")
        self.sp_malla.setToolTip("Bigger step = faster iterations, less precise "
                                 "volumes. 2-5 m is a good compromise.")
        f4.addWidget(self.sp_malla, 1, 1)
        self.btn_run = QPushButton("Run optimisation")
        self.btn_run.clicked.connect(self._ejecutar)
        f4.addWidget(self.btn_run, 1, 2)
        self.btn_stop = QPushButton("Stop"); self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._parar)
        f4.addWidget(self.btn_stop, 1, 3)
        self.barra = QProgressBar(); self.barra.setTextVisible(False)
        f4.addWidget(self.barra, 2, 0, 1, 4)
        # g4 se añade al divisor al final

        # El registro va en un DIVISOR: se puede arrastrar el separador para
        # darle toda la altura que se quiera, y además se puede abrir en una
        # ventana aparte redimensionable.
        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setMinimumHeight(70)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        cab = QHBoxLayout()
        cab.addWidget(QLabel("<b>Progress log</b>  (drag the separator above to "
                             "make it taller)"))
        cab.addStretch(1)
        self.btn_log = QPushButton("Open log in a window")
        self.btn_log.setToolTip("Opens a separate resizable window that keeps "
                                "receiving the messages live.")
        self.btn_log.clicked.connect(self._abrir_ventana_log)
        cab.addWidget(self.btn_log)
        b_limpiar = QPushButton("Clear")
        b_limpiar.clicked.connect(self.log.clear)
        cab.addWidget(b_limpiar)
        caja_log = QWidget(); vlog = QVBoxLayout(caja_log)
        vlog.setContentsMargins(0, 0, 0, 0)
        vlog.addLayout(cab)
        vlog.addWidget(self.log, 1)
        self._divisor = QSplitter(Qt.Orientation.Vertical)
        arriba = QWidget(); varr = QVBoxLayout(arriba)
        varr.setContentsMargins(0, 0, 0, 0)
        for gb in (g1, g2, g3, g4):
            varr.addWidget(gb)
        self._divisor.addWidget(arriba)
        self._divisor.addWidget(caja_log)
        self._divisor.setStretchFactor(0, 3)
        self._divisor.setStretchFactor(1, 2)
        self._divisor.setChildrenCollapsible(False)
        v.addWidget(self._divisor, 1)
        h = QHBoxLayout()
        self.btn_carpeta = QPushButton("Open working folder")
        self.btn_carpeta.setEnabled(False)
        self.btn_carpeta.clicked.connect(self._abrir_carpeta)
        h.addWidget(self.btn_carpeta)
        self.btn_aplicar = QPushButton("Apply best solution to the project")
        self.btn_aplicar.setEnabled(False)
        self.btn_aplicar.clicked.connect(self._aplicar_mejor)
        h.addWidget(self.btn_aplicar)
        h.addStretch(1)
        v.addLayout(h)
        self._habilitar(False)

    # ---------------- modelos ----------------
    def _habilitar(self, on):
        for w in (self.cb_srv, self.cb_mod, self.sp_temp, self.sp_ctx,
                  self.chk_img, self.chk_web):
            w.setEnabled(on)
        # los objetivos y variables se pueden preparar aunque no haya modelo
        self.btn_run.setEnabled(True)

    def buscar_modelos(self, silencioso=True):
        """Lanza el escaneo en segundo plano; la interfaz no se bloquea."""
        self.escribir("Scanning for local AI servers (Ollama, LM Studio)…")
        self.btn_scan.setEnabled(False)
        self.lb_estado.setText("Scanning…")
        self._hilo_scan = HiloEscaneo()
        self._hilo_scan.listo.connect(
            lambda srv: self._fin_escaneo(srv, silencioso))
        self._hilo_scan.start()

    def _fin_escaneo(self, servidores, silencioso=True):
        self.btn_scan.setEnabled(True)
        self.servidores = servidores or []
        self.cb_srv.clear()
        if not self.servidores:
            self.lb_estado.setText(
                "No local AI server found. Start Ollama or LM Studio and press "
                "'Scan for local models'. The optimisation can still run in "
                "numeric mode.")
            self._habilitar(False)
            if not silencioso:
                self.escribir("No server answered on the usual ports "
                              "(11434 Ollama, 1234 LM Studio, 8080, 5000, 8000).")
            return
        for s in self.servidores:
            self.cb_srv.addItem(f"{s['tipo']} — {s['url']} "
                                f"({len(s['modelos'])} models)")
        self.lb_estado.setText(f"{len(self.servidores)} server(s) found.")
        self._habilitar(True)
        self._srv_cambiado(0)

    def _srv_cambiado(self, i):
        # al rellenar la lista no se consulta el servidor modelo a modelo
        # (cada /api/show costaba su tiempo y multiplicaba la espera)
        self.cb_mod.blockSignals(True)
        self.cb_mod.clear()
        if 0 <= i < len(self.servidores):
            for m in self.servidores[i]["modelos"]:
                self.cb_mod.addItem(m)
        self.cb_mod.blockSignals(False)
        if self.cb_mod.count():
            self._mod_cambiado(self.cb_mod.currentText())

    def _mod_cambiado(self, nombre):
        i = self.cb_srv.currentIndex()
        if not nombre or not (0 <= i < len(self.servidores)):
            self.lb_modelo.setText("")
            return
        info = ai_client.info_modelo(self.servidores[i], nombre)
        partes = []
        if info.get("parametros"):
            partes.append(str(info["parametros"]))
        if info.get("cuantizacion"):
            partes.append(str(info["cuantizacion"]))
        if info.get("contexto"):
            partes.append(f"max context {info['contexto']:,}")
            # no se sube el contexto al máximo del modelo: con 200k tokens la
            # memoria de vídeo se dispara y el servidor puede no arrancar
            self.sp_ctx.setValue(min(int(info["contexto"]), 65536))
        if info.get("vision"):
            partes.append("vision: yes")
        elif info.get("vision_seguro"):
            partes.append("vision: NO (images will not be sent)")
        else:
            partes.append("vision: unknown")
        self.chk_img.setEnabled(bool(info.get("vision")) or
                                not info.get("vision_seguro"))
        if info.get("vision_seguro") and not info.get("vision"):
            self.chk_img.setChecked(False)
        self.lb_modelo.setText("Model: " + " · ".join(partes))

    # ---------------- variables ----------------
    def refrescar_canales(self):
        while self.cont_canales.count():
            it = self.cont_canales.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for c in self.dock.proyecto.canales:
            b = QPushButton(f"Channel '{c.nombre}' settings...")
            b.clicked.connect(lambda _=False, n=c.nombre: self._editar_canal(n))
            self.cont_canales.addWidget(b)
        self.cont_canales.addStretch(1)

    def _editar_globales(self):
        dlg = VariablesDialog("Global Settings the AI may change",
                              VARIABLES_GLOBALES, self.dock.proyecto.settings,
                              self.estado_global, self)
        if dlg.exec():
            self.estado_global = dlg.resultado()
            n = sum(1 for v in self.estado_global.values() if v["on"])
            self.escribir(f"{n} global setting(s) enabled for optimisation.")

    def _editar_canal(self, nombre):
        canal = next((c for c in self.dock.proyecto.canales
                      if c.nombre == nombre), None)
        if canal is None:
            return
        dlg = VariablesDialog(f"Channel '{nombre}' settings the AI may change",
                              VARIABLES_CANAL, canal,
                              self.estado_canales.get(nombre, {}), self)
        if dlg.exec():
            self.estado_canales[nombre] = dlg.resultado()
            n = sum(1 for v in self.estado_canales[nombre].values() if v["on"])
            self.escribir(f"{n} setting(s) of channel '{nombre}' enabled.")

    def _espacio(self):
        """Construye el espacio de búsqueda a partir de lo marcado."""
        esp = {"globales": {}, "canales": {}, "geom": {}}
        s = self.dock.proyecto.settings
        for k, st in self.estado_global.items():
            if not st.get("on"):
                continue
            et, lo, hi, _t = VARIABLES_GLOBALES[k]
            esp["globales"][k] = rango_de(getattr(s, k, None), st["pct"], lo, hi)
        for c in self.dock.proyecto.canales:
            marcados = self.estado_canales.get(c.nombre, {})
            d = {}
            for k, st in marcados.items():
                if not st.get("on"):
                    continue
                et, lo, hi, _t = VARIABLES_CANAL[k]
                d[k] = rango_de(getattr(c, k, None), st["pct"], lo, hi)
            if self.chk_z.isChecked():
                for k in ("pendiente_cabecera_pct", "pendiente_boca_pct"):
                    et, lo, hi, _t = VARIABLES_CANAL[k]
                    base = getattr(c, k, None)
                    if base is None and k == "pendiente_boca_pct":
                        base = s.pendiente_desembocadura
                    d.setdefault(k, rango_de(base, self.sp_z.value(), lo, hi))
            if self.chk_perf.isChecked():
                for k in ("dist_cresta_swale_m",):
                    et, lo, hi, _t = VARIABLES_CANAL[k]
                    d.setdefault(k, rango_de(getattr(c, k, None),
                                             self.sp_perf.value(), lo, hi))
            esp["canales"][c.nombre] = d
        if self.chk_perf.isChecked():
            for k in ("pendiente_max_pct", "convexo_pct", "max_dist_cresta_cabecera"):
                et, lo, hi, _t = VARIABLES_GLOBALES[k]
                esp["globales"].setdefault(
                    k, rango_de(getattr(s, k, None), self.sp_perf.value(), lo, hi))
        if self.chk_perf.isChecked():
            # equivale a 'Edit Longitudinal Profile' de cada cresta y vaguada
            esp["geom"]["perfiles"] = self.sp_perf.value()
        if self.chk_z.isChecked():
            for c in self.dock.proyecto.canales:
                et, lo, hi, _t = VARIABLES_CANAL["concavidad_perfil"]
                esp["canales"].setdefault(c.nombre, {}).setdefault(
                    "concavidad_perfil",
                    rango_de(getattr(c, "concavidad_perfil", 1.0),
                             self.sp_z.value(), lo, hi))
        if self.chk_xy.isChecked():
            esp["geom"]["xy"] = self.sp_xy.value()
        if self.chk_lim.isChecked():
            esp["geom"]["limite"] = self.sp_lim.value()
            esp["geom"]["limite_zona"] = "low" if self.cb_lim.currentIndex() == 0 else "high"
        return esp

    def _objetivos(self):
        o = {}
        if self.chk_fill.isChecked():
            o["fill_objetivo"] = self.sp_fill.value()
        if self.chk_cut.isChecked():
            o["cut_objetivo"] = self.sp_cut.value()
        for chk, k in ((self.chk_eq, "equilibrio"),
                       (self.chk_dozer, "cut_alto_fill_bajo"),
                       (self.chk_haul, "minimo_acarreo"),
                       (self.chk_slope, "pendientes_ok"),
                       (self.chk_dd, "dd_objetivo"),
                       (self.chk_tau, "tractiva_ok")):
            if chk.isChecked():
                o[k] = True
        return o

    # ---------------- ejecución ----------------
    def escribir(self, txt):
        self.log.appendPlainText(str(txt))
        self.log.verticalScrollBar().setValue(
            self.log.verticalScrollBar().maximum())
        if self.ventana_log is not None and self.ventana_log.isVisible():
            self.ventana_log.anadir(str(txt))

    def _abrir_ventana_log(self):
        if self.ventana_log is None:
            self.ventana_log = VentanaRegistro(self.log.toPlainText(), self)
        else:
            self.ventana_log.txt.setPlainText(self.log.toPlainText())
        self.ventana_log.show()
        self.ventana_log.raise_()

    def _ejecutar(self):
        d = self.dock
        if d.dem_layer is None:
            QMessageBox.warning(self, "AI Optimization",
                                "Load the original surface (DEM) first: the "
                                "cut/fill volumes are measured against it.")
            return
        if not d.proyecto.canales:
            QMessageBox.warning(self, "AI Optimization",
                                "Define the boundary and the channels first.")
            return
        esp = self._espacio()
        if not (esp["globales"] or any(esp["canales"].values()) or esp["geom"]):
            QMessageBox.warning(self, "AI Optimization",
                                "Nothing is allowed to change: enable at least "
                                "one setting or geometry option in section 3.")
            return
        objetivos = self._objetivos()
        if not objetivos:
            QMessageBox.warning(self, "AI Optimization",
                                "Select at least one goal in section 2.")
            return
        self.carpeta = carpeta_optimizacion(
            d.proyecto.nombre or "GeoFluv", getattr(d, "ruta_proyecto", None))
        self.btn_carpeta.setEnabled(True)
        cliente = None
        i = self.cb_srv.currentIndex()
        if 0 <= i < len(self.servidores) and self.cb_mod.currentText():
            cliente = ai_client.ClienteIA(
                self.servidores[i], self.cb_mod.currentText(),
                temperatura=self.sp_temp.value(), contexto=self.sp_ctx.value(),
                pensar=self.chk_think.isChecked())
            self.escribir(f"Using model '{self.cb_mod.currentText()}' on "
                          f"{self.servidores[i]['url']}.")
        else:
            self.escribir("No model selected: running in numeric mode "
                          "(no AI guidance).")
        ctx = ContextoIA(self.carpeta, d.proyecto, d.iface,
                         permitir_web=self.chk_web.isChecked(),
                         max_imagenes=6 if self.chk_img.isChecked() else 0,
                         log=self.escribir, dem=d.dem_layer)
        if cliente:
            ctx.guardar_prompt_base(ctx.sistema())
        ev = Evaluador(d.proyecto, d.lm, d.dem_layer, d.iface,
                       paso_malla=self.sp_malla.value(), log=self.escribir)
        opt = Optimizador(ev, esp, objetivos, self.carpeta, cliente=cliente,
                          iteraciones=self.sp_iter.value(),
                          tolerancia_pct=self.sp_tol.value(),
                          log=self.escribir, contexto=ctx)
        self.hilo = HiloOptimizacion(opt, Candidato())
        self.hilo.mensaje.connect(self.escribir)
        self.hilo.terminado.connect(self._fin)
        self.btn_run.setEnabled(False); self.btn_stop.setEnabled(True)
        self.barra.setRange(0, 0)
        self.hilo.start()

    def _parar(self):
        if self.hilo:
            self.hilo.cancelar()
            self.escribir("Stop requested; finishing the current iteration…")

    def _fin(self, mejor):
        self.barra.setRange(0, 1); self.barra.setValue(1)
        self.btn_run.setEnabled(True); self.btn_stop.setEnabled(False)
        self.mejor = mejor
        self.btn_aplicar.setEnabled(mejor is not None)
        self.dock.iface.mapCanvas().refreshAllLayers()

    def _aplicar_mejor(self):
        mejor = getattr(self, "mejor", None)
        if mejor is None:
            return
        s = self.dock.proyecto.settings
        for k, v in mejor.globales.items():
            if hasattr(s, k):
                setattr(s, k, v)
        for c in self.dock.proyecto.canales:
            for k, v in (mejor.canales.get(c.nombre) or {}).items():
                if hasattr(c, k):
                    setattr(c, k, v)
        self.escribir("Best solution written into the project settings.")
        if mejor.geom.get("xy"):
            r = QMessageBox.question(
                self, "AI Optimization",
                "The best solution also shifts the valley bottom lines.\n"
                "Write those shifted lines into the GF_ValleyBottoms layer?\n"
                "(the original geometry will be replaced)")
            if r == QMessageBox.StandardButton.Yes:
                n = self._aplicar_valles(mejor.geom["xy"])
                self.escribir(f"{n} valley bottom line(s) updated.")
            else:
                self.escribir("Valley bottom offsets kept only in "
                              "resultado.json.")
        if mejor.geom.get("perfiles"):
            self.escribir("Ridge/swale profile adjustments of the best "
                          "solution: "
                          + str(mejor.geom["perfiles"])
                          + "  — they are re-applied automatically the next "
                            "time the design surface is drawn from this tab.")
        self.escribir("Press 'Draw Design Surface' to rebuild the design at "
                      "full resolution.")

    def _aplicar_valles(self, offsets):
        """Escribe en GF_ValleyBottoms los fondos de valle desplazados."""
        from qgis.core import QgsGeometry, QgsPointXY
        from ..core.ai_optimizer import Evaluador
        d = self.dock
        capa = d.lm.obtener_capa(d.proyecto.capa_valles, crear=False)
        if capa is None:
            return 0
        n = 0
        capa.startEditing()
        for c in d.proyecto.canales:
            offs = offsets.get(c.nombre)
            if not offs or c.fid_fondo_valle is None:
                continue
            f = capa.getFeature(c.fid_fondo_valle)
            if not f.isValid():
                continue
            base = [(v.x(), v.y()) for v in f.geometry().vertices()]
            nuevos = Evaluador._desplazar(base, offs)
            capa.changeGeometry(c.fid_fondo_valle, QgsGeometry.fromPolylineXY(
                [QgsPointXY(x, y) for x, y in nuevos]))
            n += 1
        capa.commitChanges()
        capa.triggerRepaint()
        return n

    def _abrir_carpeta(self):
        ruta = getattr(self, "carpeta", None)
        if ruta and os.path.isdir(ruta):
            try:
                os.startfile(ruta)               # Windows
            except Exception:
                import webbrowser
                webbrowser.open("file://" + ruta)
