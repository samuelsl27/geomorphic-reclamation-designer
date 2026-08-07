# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Optimización asistida por IA del diseño GeoFluv.

Esquema (elegido con el usuario):

  · El BUCLE lo lleva el complemento. El volumen de corte/relleno se calcula
    aquí, en local, con la malla que fije el usuario: es exacto y rápido, y
    garantiza que la búsqueda converge aunque el modelo se equivoque.
  · La IA actúa como GUÍA: en cada iteración recibe el estado (números,
    imágenes del diseño y del mapa de corte/relleno, historial) y devuelve
    QUÉ variables mover y en qué sentido, más una explicación. El complemento
    valida la propuesta contra los rangos permitidos, la aplica, regenera el
    diseño con su propio motor y mide el resultado.
  · El modelo NUNCA escribe geometría directamente: solo parámetros y deltas
    acotados. Así toda solución es geométricamente válida y reproducible.

Si no hay modelo disponible el mismo bucle funciona con propuestas numéricas
(descenso por coordenadas con paso adaptativo), de modo que la pestaña sigue
siendo útil sin IA.
"""

import copy
import json
import math
import os
import random
import time
from datetime import datetime

from qgis.core import QgsProject, QgsRasterLayer


# ===================================================================== espacio
# Registro de variables ajustables: clave -> (etiqueta, mínimo, máximo, tipo)
# El rango efectivo de cada una lo fija el usuario como % de desviación sobre
# el valor de partida, siempre recortado a estos límites físicos.
VARIABLES_GLOBALES = {
    "max_dist_cresta_cabecera": ("Max. distance ridgeline to channel head (m)", 5.0, 120.0, float),
    "pendiente_desembocadura": ("Slope at the mouth (%)", -8.0, -0.3, float),
    "sinuosidad_canal_A": ("Sinuosity of 'A' channels", 1.02, 1.20, float),
    "reach_canal_A": ("'A' channel reach (m)", 5.0, 80.0, float),
    "dd_objetivo": ("Target drainage density (m/ha)", 20.0, 200.0, float),
    "angulo_subcresta_deg": ("Angle sub-ridge to perpendicular (deg)", 0.0, 45.0, float),
    "pendiente_NE_pct": ("North/East straight-line slopes (%)", 10.0, 50.0, float),
    "pendiente_max_pct": ("Maximum straight-line slopes (%)", 10.0, 60.0, float),
    "convexo_pct": ("Convex portion of sub-ridge (%)", 5.0, 60.0, float),
    "convexo_swale_m": ("Max. convex portion of swale (m)", 1.0, 60.0, float),
    "naturalidad": ("Surface rounding / naturalness", 0, 10, int),
}

VARIABLES_CANAL = {
    "vel_max_agua": ("Maximum water velocity (m/s)", 0.5, 3.0, float),
    "pendiente_cabecera_pct": ("Upstream slope (%)", -40.0, -1.0, float),
    "pendiente_boca_pct": ("Downstream slope (%)", -10.0, -0.3, float),
    "wd_pend_mayor_004": ("Width-to-depth, slope > 4 %", 6.0, 30.0, float),
    "wd_pend_menor_004": ("Width-to-depth, slope < 4 %", 6.0, 40.0, float),
    "sinuosidad_mayor_004": ("Sinuosity, slope > 4 %", 1.02, 1.25, float),
    "sinuosidad_menor_004": ("Sinuosity, slope < 4 %", 1.05, 2.00, float),
    "espaciado_subcrestas": ("Sub-ridge spacing on sinusoidal channel", 1, 9, int),
    "dist_cresta_swale_m": ("Max. distance ridgeline to swale head (m)", 2.0, 100.0, float),
    "coef_escorrentia": ("Runoff coefficient", 0.05, 0.95, float),
    "concavidad_perfil": ("Vertical curve shape (0 straight … 1 standard … 2 very concave)", 0.0, 2.0, float),
}

# Variables geométricas propias del optimizador (no son ajustes del diálogo)
VARIABLES_GEOMETRIA = {
    "xy": ("Channel plan shift (m)", "Desplazamiento lateral del fondo de valle "
           "en puntos de control, dentro del margen indicado."),
    "z": ("Channel profile (%)", "Variación de las pendientes de cabecera y "
          "boca, que redefine la curva del perfil longitudinal."),
    "perfiles": ("Ridge / swale profiles (%)", "Variación de la convexidad y "
                 "de la altura de crestas y vaguadas."),
    "limite": ("Boundary overrun (m)", "Ampliación del límite de diseño por la "
               "zona alta o baja."),
}

OBJETIVOS = {
    "fill_objetivo": "Reach a target FILL volume (m³)",
    "cut_objetivo": "Reach a target CUT volume (m³)",
    "equilibrio": "Balance cut and fill (net ≈ 0)",
    "cut_alto_fill_bajo": "Cut on the high ground, fill on the low ground "
                          "(dozer-workable regrade)",
    "minimo_acarreo": "Minimise haul work (volume × distance)",
    "pendientes_ok": "Keep every ridge/swale slope below the maximum",
    "dd_objetivo": "Keep the drainage density within its target range",
    "tractiva_ok": "Keep the tractive force below the Shields critical value",
}


# ===================================================================== ayudas
def _recortar(v, lo, hi):
    return max(lo, min(hi, v))


def rango_de(valor_base, pct, lo, hi):
    """Rango permitido de una variable: valor ± pct %, recortado a [lo, hi]."""
    if valor_base is None:
        return lo, hi
    d = abs(valor_base) * pct / 100.0
    if d == 0:
        d = (hi - lo) * pct / 100.0
    return _recortar(valor_base - d, lo, hi), _recortar(valor_base + d, lo, hi)


# ===================================================================== estado
class Candidato:
    """Un juego completo de valores de las variables activas."""

    def __init__(self, globales=None, canales=None, geom=None):
        self.globales = dict(globales or {})
        self.canales = {k: dict(v) for k, v in (canales or {}).items()}
        self.geom = dict(geom or {})       # {'xy': {canal: [off...]}, 'z':..., ...}
        self.metricas = None
        self.puntuacion = None
        self.iteracion = None

    def copia(self):
        c = Candidato(self.globales, self.canales,
                      json.loads(json.dumps(self.geom)))
        return c

    def como_dict(self):
        return {"global": self.globales, "channels": self.canales,
                "geometry": self.geom}


# ===================================================================== motor
class Evaluador:
    """Aplica un candidato, regenera el diseño y mide sus métricas."""

    def __init__(self, proyecto, layer_manager, dem, iface, paso_malla=2.0,
                 log=None):
        self.p0 = proyecto
        self.lm = layer_manager
        self.dem = dem
        self.iface = iface
        self.paso_malla = paso_malla
        self.log = log or (lambda *_a, **_k: None)
        self._valles_base = None

    # ---------- geometría base de los fondos de valle ----------
    def _leer_valles(self):
        if self._valles_base is not None:
            return self._valles_base
        capa = self.lm.obtener_capa(self.p0.capa_valles, crear=False)
        base = {}
        if capa is not None:
            for c in self.p0.canales:
                if c.fid_fondo_valle is None:
                    continue
                f = capa.getFeature(c.fid_fondo_valle)
                if f.isValid():
                    base[c.nombre] = [(v.x(), v.y())
                                      for v in f.geometry().vertices()]
        self._valles_base = base
        return base

    @staticmethod
    def _desplazar(pts, offsets):
        """Aplica desplazamientos NORMALES a la polilínea en puntos de control
        equiespaciados, interpolando linealmente entre ellos. Conserva los
        extremos (cabecera y boca) si su offset es 0."""
        if not offsets or len(pts) < 3:
            return list(pts)
        n = len(pts)
        m = len(offsets)
        out = []
        for i, (x, y) in enumerate(pts):
            t = i / (n - 1)
            u = t * (m - 1)
            k = min(int(u), m - 2)
            fr = u - k
            off = offsets[k] * (1 - fr) + offsets[k + 1] * fr
            i0, i1 = max(0, i - 1), min(n - 1, i + 1)
            dx, dy = pts[i1][0] - pts[i0][0], pts[i1][1] - pts[i0][1]
            L = math.hypot(dx, dy) or 1.0
            out.append((x - dy / L * off, y + dx / L * off))
        return out

    # ---------- construir ----------
    def construir(self, cand):
        """Regenera diseño + crestas + superficie con el candidato dado.
        Devuelve (disenos, ruta_superficie, g_lim) o lanza excepción."""
        from .builder import GeoFluvBuilder
        from . import ridges, surface

        proyecto = copy.deepcopy(self.p0)
        for k, v in cand.globales.items():
            if hasattr(proyecto.settings, k):
                setattr(proyecto.settings, k, v)
        for c in proyecto.canales:
            for k, v in (cand.canales.get(c.nombre) or {}).items():
                if hasattr(c, k):
                    setattr(c, k, v)

        capa_lim = self.lm.obtener_capa(proyecto.capa_limite, crear=False)
        g_lim = capa_lim.getFeature(proyecto.fid_limite).geometry()
        # ampliación del límite (extralimitación permitida)
        extra = (cand.geom.get("limite") or {}).get("m", 0.0)
        if extra and abs(extra) > 0.01:
            g_lim = self._ampliar_limite(g_lim, extra,
                                         (cand.geom.get("limite") or {}).get("zona", "low"))

        b = GeoFluvBuilder(proyecto, self.lm, self.dem)
        # inyectar los fondos de valle desplazados
        offs = cand.geom.get("xy") or {}
        if offs:
            base = self._leer_valles()
            b._valles_forzados = {n: self._desplazar(base[n], o)
                                  for n, o in offs.items() if n in base}
        disenos = b.construir(g_lim_forzado=g_lim)
        crs = QgsProject.instance().crs().authid()
        sub = ridges.generar_subcuencas(disenos, g_lim, self.lm, crs)
        _, cr3 = ridges.generar_crestas(disenos, sub, g_lim,
                                        proyecto.settings, self.dem, self.lm)
        ridges.generar_subcrestas(disenos, g_lim, proyecto.settings, self.lm,
                                  dem=self.dem, crestas=cr3,
                                  ajustes_perfil=cand.geom.get("perfiles"))
        from . import topology as _top, builder as _b
        _top.revisar(self.lm, proyecto.settings)
        _b.recalcular_por_aportes(disenos, self.lm, proyecto.settings)
        s = proyecto.settings
        capa, ruta = surface.interpolar_superficie(
            self.lm, g_lim, self.dem, disenos, s,
            celda=max(s.resolucion_dem, self.paso_malla / 2.0),
            suavizado=int(s.naturalidad or 0),
            radio_suavizado=int(s.radio_suavizado or 1),
            recortar=True)
        return disenos, ruta, g_lim, proyecto

    def _ampliar_limite(self, g_lim, metros, zona="low"):
        """Amplía el límite 'metros' SOLO por la mitad alta o baja del recinto
        (según la cota del terreno), que es como se permite extralimitarse."""
        try:
            bufer = g_lim.buffer(abs(metros), 8)
            anillo = bufer.difference(g_lim)
            if anillo is None or anillo.isEmpty():
                return g_lim
            bb = g_lim.boundingBox()
            # separar por cota media del DEM en cada trozo
            partes = anillo.asGeometryCollection() if anillo.isMultipart() else [anillo]
            from . import setup_tools as st
            buenos = []
            zs = []
            for pa in partes:
                c = pa.centroid().asPoint()
                z = st.cota_dem(self.dem, c.x(), c.y()) if self.dem else None
                zs.append((z if z is not None else 0.0, pa))
            if not zs:
                return g_lim
            medio = sorted(z for z, _ in zs)[len(zs) // 2]
            for z, pa in zs:
                if (zona == "low" and z <= medio) or (zona == "high" and z >= medio):
                    buenos.append(pa)
            if not buenos:
                return g_lim
            g = g_lim
            for pa in buenos:
                g = g.combine(pa)
            return g
        except Exception:
            return g_lim

    # ---------- medir ----------
    def medir(self, cand):
        """Construye y devuelve el diccionario de métricas del candidato."""
        from . import surface
        t0 = time.time()
        disenos, ruta, g_lim, proyecto = self.construir(cand)
        s = proyecto.settings
        cols = max(60, int(math.sqrt(g_lim.area()) / max(self.paso_malla, 0.5)))
        cf = surface.corte_relleno(QgsRasterLayer(ruta, "d"), self.dem, g_lim,
                                   s, self.lm, cols_max=cols)
        m = {
            "cut_m3": cf["corte_m3"], "fill_m3": cf["relleno_m3"],
            "net_m3": cf["corte_m3"] - cf["relleno_m3"],
            "ratio_pct": cf["pct"],
            "cut_adj_m3": cf["corte_ajustado_m3"],
            "fill_adj_m3": cf["relleno_ajustado_m3"],
            "area_ha": g_lim.area() / 1e4,
            "segundos": round(time.time() - t0, 1),
        }
        m.update(self._reparto_altura(cf))
        m.update(self._metricas_lineas(s))
        m.update(self._metricas_canales(disenos, s))
        m.update(self._anomalias(ruta, g_lim))
        m.update(self._regiones(cf, s))
        m["_cf"] = cf
        m["_ruta"] = ruta
        m["_g_lim"] = g_lim
        m["_disenos"] = disenos
        return m

    def _anomalias(self, ruta, g_lim):
        """Busca INCOHERENCIAS de la superficie: hoyos cerrados (conos
        invertidos) y picos aislados que la triangulación deja donde las líneas
        de rotura no encajan — típicamente alrededor de las confluencias.

        Un hoyo cerrado es una celda cuyas 8 vecinas están MÁS ALTAS: el agua
        no puede salir de ahí, así que es un defecto de diseño, no relieve
        natural. Se cuentan y se localizan los peores para avisar al usuario y
        al modelo."""
        try:
            import numpy as np
            from osgeo import gdal
        except Exception:
            return {"hoyos": 0, "picos": 0, "anomalias": []}
        try:
            ds = gdal.Open(ruta)
            b = ds.GetRasterBand(1)
            nd = b.GetNoDataValue()
            a = b.ReadAsArray().astype("float64")
            gt = ds.GetGeoTransform()
            val = np.isfinite(a)
            if nd is not None:
                val &= (a != nd)
            a = np.where(val, a, np.nan)
            centro = a[1:-1, 1:-1]
            vecinas = []
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dy == 0 and dx == 0:
                        continue
                    vecinas.append(a[1 + dy: a.shape[0] - 1 + dy,
                                     1 + dx: a.shape[1] - 1 + dx])
            vmin = np.nanmin(np.stack(vecinas), axis=0)
            vmax = np.nanmax(np.stack(vecinas), axis=0)
            UMBRAL = 0.20      # m: por debajo es ruido de interpolación
            hoyos = (centro < vmin - UMBRAL)
            picos = (centro > vmax + UMBRAL)
            prof = np.where(hoyos, vmin - centro, 0.0)
            lista = []
            n_h = int(np.nansum(hoyos))
            n_p = int(np.nansum(picos))
            if n_h:
                idx = np.dstack(np.unravel_index(
                    np.argsort(-np.nan_to_num(prof).ravel())[:6], prof.shape))[0]
                for r, c in idx:
                    d = float(prof[r, c])
                    if d <= UMBRAL:
                        continue
                    x = gt[0] + (c + 1.5) * gt[1]
                    y = gt[3] + (r + 1.5) * gt[5]
                    lista.append({"tipo": "hoyo cerrado", "prof_m": round(d, 2),
                                  "x": round(x, 1), "y": round(y, 1)})
            ds = None
            return {"hoyos": n_h, "picos": n_p, "anomalias": lista}
        except Exception:
            return {"hoyos": 0, "picos": 0, "anomalias": []}

    def _regiones(self, cf, s):
        """Regiones conexas de corte y relleno + acarreo total, que es lo que
        el modelo necesita para razonar sobre la DISTRIBUCIÓN del movimiento
        de tierras (y no solo sobre los totales)."""
        from . import surface
        try:
            vol_min = max(50.0, (cf["corte_m3"] + cf["relleno_m3"]) / 500.0)
            regs, plan = surface.centroides(cf, vol_min, self.lm)
        except Exception:
            return {"regiones": [], "acarreo_m3m": None, "n_regiones": 0}
        acarreo = sum(p["volumen"] * p["distancia"] for p in plan)
        tabla = [{"id": R["id"], "tipo": R["tipo"],
                  "volumen_m3": round(R["volumen"], 1),
                  "area_m2": round(R.get("area_m2", 0), 1),
                  "prof_media_m": round(R.get("prof_media", 0), 2),
                  "x": round(R["x"], 1), "y": round(R["y"], 1)}
                 for R in regs[:20]]
        return {"regiones": tabla, "n_regiones": len(regs),
                "acarreo_m3m": round(acarreo, 1),
                "rutas": [{"de": p["de"], "a": p["a"],
                           "volumen_m3": round(p["volumen"], 1),
                           "distancia_m": round(p["distancia"], 1)}
                          for p in plan[:15]]}

    def _reparto_altura(self, cf):
        """¿El corte cae en las zonas altas y el relleno en las bajas?

        Se compara la cota ORIGINAL de las celdas de corte con la de las de
        relleno. Un remodelado ejecutable con bulldozer empuja material cuesta
        abajo: cota media de corte > cota media de relleno."""
        from . import setup_tools as st
        malla, filas, cols = cf["malla"], cf["filas"], cf["cols"]
        bb, dx, dy = cf["bb"], cf["dx"], cf["dy"]
        if self.dem is None:
            return {"z_cut_med": None, "z_fill_med": None, "dozer_idx": None,
                    "cut_en_alto_pct": None}
        # muestreo (no hace falta leer todas las celdas)
        paso = max(1, int(max(filas, cols) / 120))
        zc = zf = 0.0
        vc = vf = 0.0
        muestras = []
        for r in range(0, filas, paso):
            for c in range(0, cols, paso):
                v = malla[r][c]
                if v is None or abs(v) < 1e-6:
                    continue
                x = bb.xMinimum() + (c + 0.5) * dx
                y = bb.yMaximum() - (r + 0.5) * dy
                z = st.cota_dem(self.dem, x, y)
                if z is None:
                    continue
                muestras.append((z, v))
                if v < 0:
                    zc += z * (-v); vc += (-v)
                else:
                    zf += z * v; vf += v
        if not muestras or vc <= 0 or vf <= 0:
            return {"z_cut_med": None, "z_fill_med": None, "dozer_idx": None,
                    "cut_en_alto_pct": None}
        z_cut = zc / vc
        z_fill = zf / vf
        zz = sorted(z for z, _ in muestras)
        z_med = zz[len(zz) // 2]
        rango = (zz[-1] - zz[0]) or 1.0
        alto = sum(-v for z, v in muestras if v < 0 and z >= z_med)
        return {"z_cut_med": round(z_cut, 2), "z_fill_med": round(z_fill, 2),
                # +1 = todo el corte arriba y el relleno abajo; −1 = al revés
                "dozer_idx": round((z_cut - z_fill) / rango, 3),
                "cut_en_alto_pct": round(100.0 * alto / vc, 1)}

    def _metricas_lineas(self, s):
        """Pendientes de crestas/vaguadas frente al máximo admisible."""
        peor, fuera, total = 0.0, 0, 0
        for nom in ("GRD_Ridges", "GRD_SubRidges", "GRD_Swales"):
            capa = self.lm.obtener_capa(nom, crear=False)
            if capa is None:
                continue
            for f in capa.getFeatures():
                total += 1
                vs = list(f.geometry().vertices())
                pmax = 0.0
                for a, b in zip(vs[:-1], vs[1:]):
                    d = math.hypot(b.x() - a.x(), b.y() - a.y())
                    if d < 0.5:
                        continue
                    pmax = max(pmax, abs(b.z() - a.z()) / d * 100.0)
                peor = max(peor, pmax)
                if pmax > s.pendiente_max_pct:
                    fuera += 1
        return {"lineas_total": total, "lineas_fuera_pendiente": fuera,
                "pendiente_peor_pct": round(peor, 1)}

    def _metricas_canales(self, disenos, s):
        dd = [d.dd_m_ha for d in disenos.values() if d.dd_m_ha]
        tau_alto = 0
        capa = self.lm.obtener_capa("GRD_XSections", crear=False)
        n_sec = 0
        if capa is not None:
            for f in capa.getFeatures():
                n_sec += 1
                if (f["tau_ratio"] or 0) > 1.0:
                    tau_alto += 1
        # pendientes EFECTIVAS: el motor recorta las pendientes pedidas para
        # que el perfil siga siendo monótono y cóncavo. Si no se le devuelven
        # al modelo, éste pide una y otra vez valores que no tienen efecto.
        perfiles = {}
        for n, d in disenos.items():
            if d.perfil is None:
                continue
            m_media = ((d.perfil.z_boca - d.perfil.z_cabecera) / d.L_valle * 100.0) \
                if d.L_valle else 0.0
            perfiles[n] = {
                "pendiente_cabecera_efectiva_pct": round(d.perfil.s_cabecera * 100, 2),
                "pendiente_boca_efectiva_pct": round(d.perfil.s_boca * 100, 2),
                "pendiente_media_pct": round(m_media, 2),
                "recortado": bool(d.perfil.ajustado)}
        return {"perfiles_efectivos": perfiles,
                "dd_media": round(sum(dd) / len(dd), 1) if dd else None,
                "dd_objetivo": s.dd_objetivo,
                "secciones": n_sec, "secciones_tau_alto": tau_alto,
                "canales": {n: {"sinuosidad": round(d.sinuosidad_real, 3),
                                "longitud_m": round(d.long_canal, 1),
                                "dd_m_ha": round(d.dd_m_ha, 1)}
                            for n, d in disenos.items()}}


# ===================================================================== score
def puntuar(m, objetivos, tolerancia_pct):
    """Puntuación 0..1 (1 = todos los objetivos cumplidos) + detalle por
    objetivo. Cada término es un 'grado de cumplimiento' entre 0 y 1."""
    det = {}
    if not m:
        return 0.0, det
    tol = max(tolerancia_pct, 0.1) / 100.0

    def cerca(valor, objetivo):
        """Grado de cumplimiento de un objetivo numérico, 0..1.

        Dentro de la tolerancia vale 1. Fuera, decae de forma SUAVE y nunca
        llega a cero: antes se anulaba en cuanto el error doblaba la tolerancia,
        de modo que dos diseños malos —uno al 4 % y otro al 40 %— puntuaban
        igual (0.000) y la búsqueda se quedaba ciega, sin saber que se estaba
        acercando. Con la curva 1/(1+e) siempre hay pendiente que seguir."""
        if objetivo in (None, 0):
            return None
        err = abs(valor - objetivo) / abs(objetivo)
        if err <= tol:
            return 1.0
        exceso = (err - tol) / max(tol, 1e-6)
        return 1.0 / (1.0 + exceso)

    if objetivos.get("fill_objetivo") is not None:
        det["fill_objetivo"] = cerca(m["fill_m3"], objetivos["fill_objetivo"])
    if objetivos.get("cut_objetivo") is not None:
        det["cut_objetivo"] = cerca(m["cut_m3"], objetivos["cut_objetivo"])
    if objetivos.get("equilibrio"):
        base = max(m["cut_m3"], m["fill_m3"], 1.0)
        err = abs(m["net_m3"]) / base
        if err <= tol:
            det["equilibrio"] = 1.0
        else:
            det["equilibrio"] = 1.0 / (1.0 + (err - tol) / max(tol, 1e-6))
    if objetivos.get("cut_alto_fill_bajo"):
        idx = m.get("dozer_idx")
        det["cut_alto_fill_bajo"] = None if idx is None else \
            _recortar((idx + 0.1) / 0.5, 0.0, 1.0)
    if objetivos.get("minimo_acarreo"):
        ac = m.get("acarreo_m3m")
        ref = objetivos.get("_acarreo_ref")
        det["minimo_acarreo"] = None if (ac is None or not ref) else \
            _recortar(ref / max(ac, 1.0), 0.0, 1.0)
    if objetivos.get("pendientes_ok"):
        t = m.get("lineas_total") or 1
        det["pendientes_ok"] = 1.0 - _recortar(
            (m.get("lineas_fuera_pendiente") or 0) / t, 0.0, 1.0)
    if objetivos.get("dd_objetivo"):
        ddm, ddo = m.get("dd_media"), m.get("dd_objetivo")
        if ddm and ddo:
            err = abs(ddm - ddo) / ddo
            det["dd_objetivo"] = _recortar(1.0 - err / 0.25, 0.0, 1.0)
    if objetivos.get("tractiva_ok"):
        n = m.get("secciones") or 1
        det["tractiva_ok"] = 1.0 - _recortar(
            (m.get("secciones_tau_alto") or 0) / n, 0.0, 1.0)
    vals = [v for v in det.values() if v is not None]
    return (sum(vals) / len(vals) if vals else 0.0), det


# ===================================================================== bucle
class Optimizador:
    """Bucle de optimización: propone, evalúa, guarda y explica."""

    def __init__(self, evaluador, espacio, objetivos, carpeta, cliente=None,
                 iteraciones=10, tolerancia_pct=5.0, log=None, contexto=None,
                 semilla=12345, cancelado=None):
        self.ev = evaluador
        self.espacio = espacio          # {'globales':{k:(lo,hi)}, 'canales':{c:{k:(lo,hi)}}, 'geom':{...}}
        self.objetivos = objetivos
        self.carpeta = carpeta
        self.cli = cliente
        self.n_iter = max(1, int(iteraciones))
        self.tol = tolerancia_pct
        self.log = log or (lambda *_a, **_k: None)
        self.ctx = contexto
        self.rng = random.Random(semilla)
        self.cancelado = cancelado or (lambda: False)
        self.historial = []
        self.mejor = None
        self._sin_efecto = []

    # ---------- propuestas ----------
    def _propuesta_numerica(self, base, amplitud):
        """Descenso por coordenadas estocástico: mueve 1-3 variables activas."""
        c = base.copia()
        activas = []
        for k, (lo, hi) in self.espacio.get("globales", {}).items():
            activas.append(("g", None, k, lo, hi))
        for canal, vs in self.espacio.get("canales", {}).items():
            for k, (lo, hi) in vs.items():
                activas.append(("c", canal, k, lo, hi))
        if not activas:
            return c
        for _ in range(self.rng.randint(1, min(3, len(activas)))):
            tipo, canal, k, lo, hi = self.rng.choice(activas)
            actual = (c.globales.get(k) if tipo == "g"
                      else c.canales.setdefault(canal, {}).get(k))
            if actual is None:
                actual = (lo + hi) / 2.0
            paso = (hi - lo) * amplitud
            nuevo = _recortar(actual + self.rng.uniform(-paso, paso), lo, hi)
            reg = VARIABLES_GLOBALES if tipo == "g" else VARIABLES_CANAL
            if reg.get(k) and reg[k][3] is int:
                nuevo = int(round(nuevo))
            if tipo == "g":
                c.globales[k] = nuevo
            else:
                c.canales.setdefault(canal, {})[k] = nuevo
        # geometría
        gx = self.espacio.get("geom", {})
        if gx.get("xy"):
            maxm = gx["xy"]
            for canal in (self.espacio.get("canales") or {"main": {}}):
                offs = (c.geom.setdefault("xy", {})
                        .setdefault(canal, [0.0] * 5))
                i = self.rng.randrange(1, len(offs) - 1)
                offs[i] = _recortar(offs[i] + self.rng.uniform(-maxm, maxm) * amplitud,
                                    -maxm, maxm)
        if gx.get("perfiles"):
            pf = c.geom.setdefault("perfiles", {"crestas_pct": 0.0, "vaguadas_pct": 0.0})
            cual = self.rng.choice(("crestas_pct", "vaguadas_pct"))
            pf[cual] = _recortar(pf.get(cual, 0.0)
                                 + self.rng.uniform(-1, 1) * gx["perfiles"] * amplitud,
                                 -gx["perfiles"], gx["perfiles"])
        if gx.get("limite"):
            lim = c.geom.setdefault("limite", {"m": 0.0, "zona": gx.get("limite_zona", "low")})
            lim["m"] = _recortar(lim["m"] + self.rng.uniform(-1, 1) * gx["limite"] * amplitud,
                                 0.0, gx["limite"])
        return c

    def _propuesta_ia(self, base, iteracion, imagenes):
        """Pide al modelo qué variables mover. Devuelve (candidato, texto)."""
        if self.cli is None or self.ctx is None:
            return None, None
        self.ctx.sin_efecto = list(self._sin_efecto)
        prompt = self.ctx.prompt_iteracion(iteracion, self.historial, self.mejor,
                                           self.espacio, self.objetivos)
        datos, bruto = self.cli.preguntar_json(
            prompt, imagenes=imagenes, sistema=self.ctx.sistema())
        try:
            with open(os.path.join(self.carpeta, f"respuesta_{iteracion:02d}.txt"),
                      "w", encoding="utf-8") as fh:
                if getattr(self.cli, "ultimo_razonamiento", None):
                    fh.write("=== RAZONAMIENTO ===\n"
                             + str(self.cli.ultimo_razonamiento) + "\n\n")
                fh.write("=== RESPUESTA ===\n" + (bruto or ""))
        except Exception:
            pass
        if not datos:
            self.log("   · el modelo no ha devuelto un JSON válido"
                     + (f" ({self.cli.ultimo_error})" if self.cli.ultimo_error else "")
                     + "; se usa la propuesta numérica.")
            return None, bruto
        c = base.copia()
        cambios = []
        for k, v in (datos.get("global") or {}).items():
            rango = self.espacio.get("globales", {}).get(k)
            if rango is None:
                cambios.append(f"[ignorado, no permitido] {k}")
                continue
            try:
                nv = _recortar(float(v), *rango)
            except Exception:
                continue
            if VARIABLES_GLOBALES.get(k) and VARIABLES_GLOBALES[k][3] is int:
                nv = int(round(nv))
            c.globales[k] = nv
            cambios.append(f"global.{k} = {nv:g}")
        for canal, vs in (datos.get("channels") or {}).items():
            perm = self.espacio.get("canales", {}).get(canal, {})
            for k, v in (vs or {}).items():
                if k not in perm:
                    cambios.append(f"[ignorado] {canal}.{k}")
                    continue
                try:
                    nv = _recortar(float(v), *perm[k])
                except Exception:
                    continue
                if VARIABLES_CANAL.get(k) and VARIABLES_CANAL[k][3] is int:
                    nv = int(round(nv))
                c.canales.setdefault(canal, {})[k] = nv
                cambios.append(f"{canal}.{k} = {nv:g}")
        geo = datos.get("geometry") or {}
        maxm = self.espacio.get("geom", {}).get("xy")
        if maxm and geo.get("xy"):
            for canal, offs in geo["xy"].items():
                try:
                    lista = [_recortar(float(o), -maxm, maxm) for o in offs][:9]
                except Exception:
                    continue
                if lista:
                    c.geom.setdefault("xy", {})[canal] = lista
                    cambios.append(f"{canal}.xy = {[round(o,1) for o in lista]}")
        maxp = self.espacio.get("geom", {}).get("perfiles")
        if maxp and geo.get("profiles"):
            pf = geo["profiles"] or {}
            dest = c.geom.setdefault("perfiles", {})
            for k_in, k_out in (("ridges_pct", "crestas_pct"),
                                ("swales_pct", "vaguadas_pct")):
                if k_in in pf:
                    try:
                        dest[k_out] = _recortar(float(pf[k_in]), -maxp, maxp)
                        cambios.append(f"profiles.{k_in} = {dest[k_out]:+.1f} %")
                    except Exception:
                        pass
            porl = pf.get("per_line") or {}
            if isinstance(porl, dict) and porl:
                dl = dest.setdefault("por_linea", {})
                for clave, val in list(porl.items())[:60]:
                    try:
                        dl[str(clave)] = _recortar(float(val), -maxp, maxp)
                    except Exception:
                        pass
                cambios.append(f"profiles.per_line = {len(dl)} línea(s)")
        maxl = self.espacio.get("geom", {}).get("limite")
        if maxl and geo.get("boundary_m") is not None:
            try:
                c.geom["limite"] = {
                    "m": _recortar(float(geo["boundary_m"]), 0.0, maxl),
                    "zona": geo.get("boundary_zone",
                                    self.espacio["geom"].get("limite_zona", "low"))}
                cambios.append(f"boundary = +{c.geom['limite']['m']:.1f} m "
                               f"({c.geom['limite']['zona']})")
            except Exception:
                pass
        # búsqueda web pedida por el modelo
        consulta = datos.get("web_search")
        if consulta and self.ctx is not None and self.ctx.permitir_web:
            self.log(f"   · el modelo pide buscar en internet: \"{consulta}\"")
            res = self.ctx.buscar(str(consulta)[:200])
            self.log(f"   · {len(res)} resultado(s); se le pasarán en la "
                     "siguiente iteración")
        razon = datos.get("reasoning") or datos.get("razonamiento") or ""
        self.log(f"   · el modelo propone: {'; '.join(cambios) or 'nada'}")
        if razon:
            self.log(f"   · motivo: {str(razon)[:900]}")
        for av in (datos.get("warnings") or datos.get("avisos") or []):
            self.log(f"   · AVISO DEL MODELO: {str(av)[:400]}")
        efecto = datos.get("expected_effect") or datos.get("efecto_esperado")
        if efecto:
            self.log(f"   · efecto que espera: {str(efecto)[:500]}")
        pensado = datos.get("_thinking")
        if pensado:
            self.log(f"   · razonamiento interno: {str(pensado)[:900]}")
        if not cambios:
            return None, bruto
        return c, bruto

    # ---------- ejecución ----------
    def ejecutar(self, candidato_inicial):
        self.log("=" * 72)
        self.log(f"Optimización del diseño — {self.n_iter} iteraciones, "
                 f"tolerancia {self.tol:g} %, malla {self.ev.paso_malla:g} m")
        self.log(f"Carpeta de trabajo: {self.carpeta}")
        self.log("=" * 72)
        self.log("Iteración 0 (diseño de partida): calculando volúmenes…")
        try:
            m = self.ev.medir(candidato_inicial)
        except Exception as e:
            self.log(f"ERROR al evaluar el diseño de partida: {e}")
            return None
        self.objetivos.setdefault("_acarreo_ref", None)
        s, det = puntuar(m, self.objetivos, self.tol)
        candidato_inicial.metricas = m
        candidato_inicial.puntuacion = s
        candidato_inicial.iteracion = 0
        self.mejor = candidato_inicial
        self._avisar_anomalias(m)
        self._registrar(candidato_inicial, det,
                        imagenes=self._exportar(candidato_inicial, 0))
        amplitud = 0.35
        sin_mejora = 0
        for it in range(1, self.n_iter + 1):
            if self.cancelado():
                self.log("Cancelado por el usuario.")
                break
            self.log(f"--- Iteración {it}/{self.n_iter} "
                     f"(mejor puntuación hasta ahora: {self.mejor.puntuacion:.3f})")
            base = self.mejor
            cand, _bruto = self._propuesta_ia(base, it, base.metricas.get("_imagenes"))
            origen = "IA"
            if cand is None:
                cand = self._propuesta_numerica(base, amplitud)
                origen = "numérica"
                self.log("   · propuesta numérica (descenso por coordenadas)")
            try:
                m = self.ev.medir(cand)
            except Exception as e:
                self.log(f"   · fallo al construir el candidato: {e}")
                sin_mejora += 1
                continue
            s, det = puntuar(m, self.objetivos, self.tol)
            cand.metricas = m
            cand.puntuacion = s
            cand.iteracion = it
            # ¿la propuesta ha tenido algún efecto real?
            mb = base.metricas or {}
            if (abs(m["cut_m3"] - mb.get("cut_m3", -1)) < 1.0 and
                    abs(m["fill_m3"] - mb.get("fill_m3", -1)) < 1.0):
                self._sin_efecto.append(it)
                self.log("   · AVISO: el resultado es idéntico al anterior; ese "
                         "cambio NO tiene efecto sobre la geometría (el motor lo "
                         "ha recortado). Se avisará al modelo.")
                for n, pe in (m.get("perfiles_efectivos") or {}).items():
                    if pe.get("recortado"):
                        self.log(f"     - '{n}': pendientes efectivas "
                                 f"{pe['pendiente_cabecera_efectiva_pct']:g} % → "
                                 f"{pe['pendiente_boca_efectiva_pct']:g} % "
                                 f"(media {pe['pendiente_media_pct']:g} %); "
                                 "el perfil se ha recortado para seguir siendo "
                                 "monótono y cóncavo")
            imgs = self._exportar(cand, it)
            self._registrar(cand, det, imagenes=imgs, origen=origen)
            self._avisar_anomalias(m)
            self.log(f"   · calculado con malla de {self.ev.paso_malla:g} m sobre "
                     f"{m.get('area_ha', 0):,.1f} ha; "
                     f"{m.get('n_regiones', 0)} regiones de movimiento de tierras")
            self.log(f"   · resultado: cut {m['cut_m3']:,.0f} m³ · "
                     f"fill {m['fill_m3']:,.0f} m³ · neto {m['net_m3']:,.0f} m³ · "
                     f"dozer {m.get('dozer_idx')} · puntuación {s:.3f}")
            if s > self.mejor.puntuacion + 1e-6:
                self.mejor = cand
                sin_mejora = 0
                amplitud = max(0.08, amplitud * 0.85)
                self.log("   · MEJORA aceptada")
            else:
                sin_mejora += 1
                amplitud = min(0.6, amplitud * 1.15)
                self.log("   · sin mejora; se amplía el paso de búsqueda")
            if self.mejor.puntuacion >= 0.999:
                self.log("Todos los objetivos cumplidos dentro de la tolerancia.")
                break
            if sin_mejora >= max(4, self.n_iter // 2):
                self.log("Sin mejoras en varias iteraciones consecutivas: "
                         "la búsqueda parece estancada.")
        self._informe_final()
        return self.mejor

    def _avisar_anomalias(self, m):
        """Avisa al usuario de incoherencias geométricas del diseño."""
        n_h, n_p = m.get("hoyos", 0), m.get("picos", 0)
        if n_h:
            self.log(f"   · ATENCIÓN: {n_h} celda(s) en HOYO CERRADO — el agua "
                     "no puede salir de ahí, así que es un defecto de diseño. "
                     "Suele indicar líneas de rotura que no encajan en cota o "
                     "una cresta divisoria que falta (típico en las "
                     "confluencias).")
        if n_p:
            self.log(f"   · {n_p} pico(s) aislado(s) en la superficie. En este "
                     "método muchos son legítimos (la punta convexa de cada "
                     "subcresta es un alto local); solo hay que revisarlos si "
                     "aparecen lejos de una cresta.")
        if not (n_h or n_p):
            return
        for an in (m.get("anomalias") or [])[:4]:
            self.log(f"     - {an['tipo']} de {an['prof_m']:.2f} m en "
                     f"({an['x']:,.0f}, {an['y']:,.0f})")

    # ---------- salidas ----------
    def _exportar(self, cand, it):
        if self.ctx is None:
            return []
        try:
            imgs = self.ctx.exportar_iteracion(cand, it)
            cand.metricas["_imagenes"] = imgs
            return imgs
        except Exception as e:
            self.log(f"   · no se han podido exportar las imágenes: {e}")
            return []

    def _registrar(self, cand, detalle, imagenes=None, origen="base"):
        m = dict(cand.metricas)
        for k in list(m):
            if k.startswith("_"):
                m.pop(k)
        reg = {"iteracion": cand.iteracion, "origen": origen,
               "puntuacion": round(cand.puntuacion, 4),
               "objetivos": {k: (round(v, 3) if v is not None else None)
                             for k, v in detalle.items()},
               "variables": cand.como_dict(), "metricas": m,
               "imagenes": [os.path.basename(i) for i in (imagenes or [])]}
        self.historial.append(reg)
        try:
            with open(os.path.join(self.carpeta, "historial.json"), "w",
                      encoding="utf-8") as fh:
                json.dump(self.historial, fh, indent=1, ensure_ascii=False)
        except Exception:
            pass

    def _informe_final(self):
        mej = self.mejor
        ln = ["", "=" * 72, "RESULTADO DE LA OPTIMIZACIÓN", "=" * 72]
        if mej is None:
            ln.append("No se ha podido evaluar ningún diseño.")
            self.log("\n".join(ln))
            return
        m = mej.metricas
        ln.append(f"Mejor iteración: {mej.iteracion}   puntuación "
                  f"{mej.puntuacion:.3f} / 1.000")
        ln.append(f"  cut  = {m['cut_m3']:,.0f} m³")
        ln.append(f"  fill = {m['fill_m3']:,.0f} m³")
        ln.append(f"  neto = {m['net_m3']:,.0f} m³   (cut/fill "
                  f"{m['ratio_pct']:,.1f} %)")
        if m.get("dozer_idx") is not None:
            ln.append(f"  reparto en altura: cota media de corte "
                      f"{m['z_cut_med']} m vs relleno {m['z_fill_med']} m "
                      f"(índice {m['dozer_idx']:+.3f}; "
                      f"{m['cut_en_alto_pct']:.0f} % del corte en la mitad alta)")
        if m.get("hoyos"):
            ln.append(f"  DEFECTO: {m['hoyos']} celda(s) en hoyo cerrado (el "
                      "agua no drena): revisar las líneas de rotura de esas "
                      "zonas y que no falte ninguna cresta divisoria")
        elif m.get("picos"):
            ln.append(f"  {m['picos']} pico(s) aislado(s) — normalmente puntas "
                      "de subcresta, relieve legítimo del método")
        ln.append(f"  líneas fuera de pendiente máxima: "
                  f"{m.get('lineas_fuera_pendiente')} de {m.get('lineas_total')}")
        if mej.puntuacion < 0.999:
            ln.append("")
            ln.append("NO se han cumplido todos los objetivos dentro de la "
                      "tolerancia pedida. Se conserva el mejor diseño obtenido.")
            ln.append("Qué puedes hacer:")
            ln.append("  · ampliar los rangos de desviación de las variables,")
            ln.append("  · relajar la tolerancia o revisar si los objetivos son "
                      "compatibles entre sí (p. ej. un fill objetivo muy alto y "
                      "a la vez equilibrio cut/fill),")
            ln.append("  · permitir extralimitarse del límite o activar más "
                      "variables (perfiles de crestas, geometría en planta),")
            ln.append("  · aumentar el número de iteraciones.")
        ln.append("")
        ln.append(f"Todo el material de la sesión está en: {self.carpeta}")
        self.log("\n".join(ln))
        try:
            with open(os.path.join(self.carpeta, "resultado.json"), "w",
                      encoding="utf-8") as fh:
                json.dump({"mejor_iteracion": mej.iteracion,
                           "puntuacion": mej.puntuacion,
                           "variables": mej.como_dict(),
                           "metricas": {k: v for k, v in mej.metricas.items()
                                        if not k.startswith("_")}},
                          fh, indent=1, ensure_ascii=False)
        except Exception:
            pass


def carpeta_optimizacion(proyecto_nombre, ruta_json=None):
    """<carpeta del .grd.json>/<nombre>_optimization_<fecha>_<hora>."""
    base = None
    if ruta_json:
        base = os.path.dirname(ruta_json)
    if not base:
        f = QgsProject.instance().fileName()
        base = os.path.dirname(f) if f else os.path.expanduser("~")
    sello = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(base, f"{proyecto_nombre}_optimization_{sello}")
    os.makedirs(destino, exist_ok=True)
    for sub in ("images", "rasters", "data"):
        os.makedirs(os.path.join(destino, sub), exist_ok=True)
    return destino
