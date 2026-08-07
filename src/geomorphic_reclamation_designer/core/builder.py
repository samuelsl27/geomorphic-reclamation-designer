# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Constructor del diseño GeoFluv: orquesta todo el motor de canales.

Pasos (equivalentes a lo que Natural Regrade hace al Añadir canales y
Previsualizar):

1. Lee las geometrías de fondo de valle y el límite; orienta cada canal de
   cabecera a boca y lo recorta al límite.
2. Construye la topología de la red: canal padre de cada tributario, estación
   de confluencia y margen (R/L mirando aguas abajo) → nombres R1/L1/R1L1.
3. Reparte el área del límite en subcuencas aproximadas (partición por
   proximidad al canal más cercano) y acumula áreas aguas abajo.
4. Diseña los perfiles longitudinales cóncavos: primero el principal (cota y
   pendiente de boca fijadas por el usuario/ajustes), después cada tributario
   empalmando con la cota Y la pendiente del receptor en la confluencia.
5. Calcula el caudal bankfull (2a-1h) y de área inundable (50a-6h) en cada
   estación (método racional con área acumulada creciente aguas abajo).
6. Traza la planta (zigzag tipo A / meandros sinusoidales) y los bordes
   paralelos de fondo, bankfull y flood-prone.
7. Genera la capa de Secciones con las propiedades hidráulicas por estación
   y escribe todas las capas en el grupo '02 Diseño'.
"""

import math
from dataclasses import dataclass, field

from qgis.core import QgsFeature, QgsGeometry, QgsPoint, QgsPointXY

from . import setup_tools as st
from .compat import attrs
from .params import UMBRAL_PENDIENTE
from .profile import disenar_perfil, estacion_transicion, PerfilLongitudinal
from .planform import densificar, trazar_canal, bordes_canal
from .hydrology import (qpk_racional, dimensionar_seccion, geometria_meandro)
from .naming import lado_confluencia, renombrar_red


# Paso de densificado del eje. El GeoFluv original entrega los canales con
# ~0.9 m entre vértices; con 2 m los meandros cortos quedaban "recortados" y
# la sinuosidad dibujada era menor que la de diseño.
PASO_DENSIFICADO = 1.0  # m


def hidraulica_estacion(d, sv, glob):
    """Hidráulica completa de la estación de valle sv del canal d.

    Devuelve un dict con todos los valores por estación (los mismos que se
    guardan en la capa Secciones). Lo usan el builder, los informes y el
    Inspector GeoFluv (que interpola en continuo al mover el cursor).
    """
    c = d.settings
    sv = max(0.0, min(sv, d.L_valle))
    pend = d.perfil.pendiente(sv)
    tipo = "A" if d.es_tramo_A(sv) else "valley"
    wd = c.wd_pend_mayor_004 if abs(pend) > UMBRAL_PENDIENTE else c.wd_pend_menor_004
    qb = d.q_bankfull(sv, glob)
    qf = d.q_flood(sv, glob)
    d50 = c.d50_mm if (c.d50_mm and c.d50_mm > 0) else glob.d50_mm
    sec = dimensionar_seccion(qb, qf, wd, c.vel_max_agua, pend,
                              n_manning=c.n_manning, d50_mm=d50)
    lm, b_min, rc = geometria_meandro(sec.ancho_bankfull)
    return {
        "canal": d.nombre, "estacion": sv, "cota": d.perfil.z(sv),
        "pendiente": pend * 100.0, "tipo": tipo,
        "area_ha": d.area_en(sv),
        "q_bankfull": qb, "q_flood": qf,
        "ancho_bankfull": sec.ancho_bankfull, "prof_bankfull": sec.prof_bankfull,
        "area_bankfull": sec.area_bankfull, "ancho_fondo": sec.ancho_fondo,
        "perim_bkf": sec.perimetro_bkf, "radio_hidr": sec.radio_hidr_bkf,
        "ancho_flood": sec.ancho_flood, "prof_flood": sec.prof_flood,
        "area_flood": sec.area_flood, "entrench": sec.entrenchment,
        "tension_bkf": sec.tension_bankfull, "tension_fld": sec.tension_flood,
        "tau_crit": sec.tension_critica, "ratio_tau": sec.ratio_tractivo,
        "estab_tau": sec.estab_tractiva,
        "calado_man": sec.calado_manning, "vel_man": sec.vel_manning,
        "froude": sec.froude, "verif_man": sec.verif_manning,
        "long_meandro": lm, "cinturon": b_min, "radio_curv": rc,
        "wd_usado": wd, "seccion": sec,
    }


@dataclass
class ChannelDesign:
    """Resultado del diseño de un canal."""
    settings: object = None
    nombre: str = ""
    padre: str = ""
    lado: str = ""
    dens: list = field(default_factory=list)        # [(s, x, y)] valle
    L_valle: float = 0.0
    perfil: PerfilLongitudinal = None
    s_transicion: float = None
    s_confluencia: float = 0.0                       # estación en el PADRE
    area_propia_ha: float = 0.0
    area_acumulada_ha: float = 0.0
    hijos: list = field(default_factory=list)        # [(s_conf, ChannelDesign)]
    puntos: list = field(default_factory=list)       # eje [(x, y, z, s)]
    sinuosidad_real: float = 1.0
    long_canal: float = 0.0
    q_bankfull_boca: float = 0.0
    q_flood_boca: float = 0.0
    dd_m_ha: float = 0.0
    secciones: list = field(default_factory=list)    # dicts por estación
    avisos: list = field(default_factory=list)

    # --- caudales en función de la estación de valle ---
    L0: float = 0.0   # ladera contribuyente aguas arriba de la cabecera (m)
    # Aportes DISCRETOS de las laderas: [(estacion, area_ha)]. Cada vaguada
    # entrega en su confluencia con el cauce el agua de la franja de ladera que
    # drena, igual que un tributario entrega la de su cuenca. Mientras está
    # vacío, el área se reparte de forma continua (primera pasada, antes de que
    # existan las vaguadas).
    aportes: list = field(default_factory=list)

    def es_tramo_A(self, s):
        """True si la estación s pertenece a un tramo tipo A (zigzag).

        Criterio del método: canal A = |pendiente| > 4 %. El punto de
        transición marcado por el usuario ('Pick') solo puede ADELANTAR el
        final del tramo A, nunca convertir en zigzag un tramo tendido."""
        if self.s_transicion is None or self.perfil is None:
            return False
        return (s <= self.s_transicion
                and abs(self.perfil.pendiente(s)) > UMBRAL_PENDIENTE)

    def area_en(self, s):
        c = self.settings
        if self.aportes:
            # --- modelo ESCALONADO (el del método): el área crece a saltos,
            # uno por cada vaguada que entra, más la ladera de cabecera. Entre
            # dos aportes la sección no cambia, que es lo que hace que el canal
            # se pueda dividir en tramos hidráulicamente homogéneos.
            a = self.area_cabecera_ha
            for est, inc in self.aportes:
                if est <= s + 1e-9:
                    a += inc
        else:
            # --- primera pasada: reparto continuo (aún no hay vaguadas) ---
            # la cabecera ya recibe escorrentía de la ladera situada entre la
            # divisoria y el inicio del canal (distancia cresta-cabecera), por
            # lo que las dimensiones en la estación 0 son pequeñas pero no nulas
            if self.L_valle > 0:
                frac = (s + self.L0) / (self.L_valle + self.L0)
            else:
                frac = 1.0
            a = self.area_propia_ha * frac
        if c.area_adicional_ha > 0 and getattr(c, "usar_racional_adicional", True):
            a += c.area_adicional_ha if c.area_adicional_en_cabecera \
                else c.area_adicional_ha * (s / self.L_valle if self.L_valle > 0 else 1.0)
        for s_conf, hijo in self.hijos:
            if s_conf <= s:
                a += hijo.area_acumulada_ha
        return a

    # área que entra por la cabecera cuando el modelo es escalonado
    area_cabecera_ha: float = 0.0

    def fijar_aportes(self, estaciones):
        """Reparte el área propia del canal en aportes DISCRETOS.

        'estaciones' son las estaciones de valle donde una vaguada entrega su
        agua al cauce. A cada una le corresponde la franja de ladera que hay
        entre la mitad del hueco anterior y la mitad del siguiente, de modo que
        la suma de los aportes es exactamente el área propia del canal: no se
        inventa ni se pierde superficie, solo se concentra donde de verdad
        entra.
        """
        est = sorted(set(round(float(e), 2) for e in estaciones
                         if 0.0 <= e <= self.L_valle))
        if not est or self.L_valle <= 0:
            self.aportes = []
            self.area_cabecera_ha = 0.0
            return
        cortes = [0.0]
        for a, b in zip(est[:-1], est[1:]):
            cortes.append((a + b) / 2.0)
        cortes.append(self.L_valle)
        total = self.area_propia_ha
        # la ladera de cabecera (entre la divisoria y el arranque del canal)
        # entra por la estación 0 y es proporcional a L0
        frac_cab = self.L0 / (self.L_valle + self.L0) if self.L_valle > 0 else 0.0
        self.area_cabecera_ha = total * frac_cab
        resto = total - self.area_cabecera_ha
        self.aportes = []
        for i, e in enumerate(est):
            ancho = max(cortes[i + 1] - cortes[i], 1e-6)
            self.aportes.append((e, resto * ancho / self.L_valle))

    def _q_adicional(self, s, q_manual):
        """Qpk manual del área adicional: entra entero por cabecera o crece
        linealmente si se reparte a lo largo del canal."""
        c = self.settings
        if q_manual is None or getattr(c, "usar_racional_adicional", True):
            return 0.0
        if c.area_adicional_en_cabecera or self.L_valle <= 0:
            return q_manual
        return q_manual * (s / self.L_valle)

    def q_bankfull(self, s, glob):
        c = self.settings
        if c.qpk_manual_bankfull is not None:
            return c.qpk_manual_bankfull
        return qpk_racional(c.coef_escorrentia, glob.p_2a_1h_mm, self.area_en(s)) \
            + self._q_adicional(s, getattr(c, "qpk_adic_bankfull", None))

    def q_flood(self, s, glob):
        c = self.settings
        if c.qpk_manual_flood is not None:
            return c.qpk_manual_flood
        return qpk_racional(c.coef_escorrentia, glob.p_50a_6h_mm, self.area_en(s)) \
            + self._q_adicional(s, getattr(c, "qpk_adic_flood", None))


class GeoFluvBuilder:
    def __init__(self, proyecto, layer_manager, dem_layer):
        self.p = proyecto
        self.lm = layer_manager
        self.dem = dem_layer
        self.avisos = []
        self.disenos = {}          # nombre -> ChannelDesign

    # ================= entrada =================
    def _geom_limite(self):
        capa = self.lm.obtener_capa(getattr(self.p, "capa_limite", "GF_Boundary"),
                                    crear=False)
        if capa is None or self.p.fid_limite is None:
            return None
        f = capa.getFeature(self.p.fid_limite)
        return f.geometry() if f.isValid() else None

    def _geom_valle(self, canal, g_lim):
        forzados = getattr(self, "_valles_forzados", None) or {}
        if canal.nombre in forzados:
            pts = forzados[canal.nombre]
            g = QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in pts])
        else:
            capa = self.lm.obtener_capa(
                getattr(self.p, "capa_valles", "GF_ValleyBottoms"), crear=False)
            if capa is None or canal.fid_fondo_valle is None:
                return None
            f = capa.getFeature(canal.fid_fondo_valle)
            if not f.isValid():
                return None
            g = f.geometry()
        gi = g.intersection(g_lim)
        if gi is None or gi.isEmpty():
            gi = g
        # quedarse con la parte más larga si el recorte fragmenta
        if gi.isMultipart():
            partes = gi.asMultiPolyline()
            partes.sort(key=lambda p: -sum(
                math.hypot(p[i + 1].x() - p[i].x(), p[i + 1].y() - p[i].y())
                for i in range(len(p) - 1)))
            pts = partes[0] if partes else []
        else:
            pts = gi.asPolyline()
        return [(pt.x(), pt.y()) for pt in pts]

    # ================= construcción =================
    def construir(self, g_lim_forzado=None):
        """g_lim_forzado: límite alternativo (lo usa el optimizador cuando se
        permite extralimitarse del límite de diseño). Si además se ha fijado
        self._valles_forzados = {canal: [(x, y), ...]}, esas polilíneas
        sustituyen a las de la capa de fondos de valle (desplazamiento en
        planta propuesto por la optimización)."""
        g_lim = g_lim_forzado if g_lim_forzado is not None else self._geom_limite()
        if g_lim is None:
            raise RuntimeError("No accepted design boundary.")
        if not self.p.canales or self.p.canales[0].fid_fondo_valle is None:
            raise RuntimeError("No accepted main channel.")

        glob = self.p.settings
        area_total_ha = g_lim.area() / 10000.0

        # --- 1. leer y orientar geometrías ---
        disenos = []
        for c in self.p.canales:
            pts = self._geom_valle(c, g_lim)
            if not pts or len(pts) < 2:
                self.avisos.append(f"Channel '{c.nombre}': invalid geometry, skipped.")
                continue
            d = ChannelDesign(settings=c, nombre=c.nombre)
            d.pts_2d = pts
            disenos.append(d)
        if not disenos:
            raise RuntimeError("No channel with valid geometry.")

        principal = disenos[0]
        principal._padre_obj = None
        self._todos = disenos
        self._orientar(principal, None)

        # --- 2. topología (padres, confluencias, lados) ---
        for d in disenos[1:]:
            self._asignar_padre(d, disenos)
        # orientar tributarios: la boca es el extremo de confluencia
        for d in disenos[1:]:
            self._orientar(d, d._padre_obj)
        # densificar y longitudes
        for d in disenos:
            d.dens = densificar(d.pts_2d, PASO_DENSIFICADO)
            d.L_valle = d.dens[-1][0] if d.dens else 0.0
        # estación de confluencia sobre el padre y margen R/L
        for d in disenos[1:]:
            self._confluencia(d)

        # --- 3. nombres R/L ---
        lista = []
        for i, d in enumerate(disenos):
            lista.append({"id": i,
                          "padre_id": disenos.index(d._padre_obj) if d._padre_obj else None,
                          "lado": d.lado or "R",
                          "estacion_confluencia": d.s_confluencia})
        nombres = renombrar_red(lista, self.p.nombre_canal_principal)
        for i, d in enumerate(disenos):
            d.nombre = nombres.get(i, d.nombre)
            d.settings.nombre = d.nombre
            if d._padre_obj is not None:
                d.padre = d._padre_obj.nombre

        # --- 4. subcuencas por proximidad y acumulación ---
        self._particion_areas(disenos, g_lim, area_total_ha)
        for d in disenos:
            d.hijos = [(h.s_confluencia, h) for h in disenos if h._padre_obj is d]

        def acumular(d):
            d.area_acumulada_ha = d.area_propia_ha + d.settings.area_adicional_ha + \
                sum(acumular(h) for _, h in d.hijos)
            return d.area_acumulada_ha
        acumular(principal)

        # --- 5. perfiles (principal → tributarios, recursivo) ---
        self._perfil_canal(principal, None, glob)

        # --- 6. planta, bordes y secciones ---
        for k, d in enumerate(disenos):
            d.L0 = glob.max_dist_cresta_cabecera
            q_en = (lambda dd: (lambda s: dd.q_bankfull(s, glob)))(d)
            d.puntos, d.sinuosidad_real = trazar_canal(
                d.dens, d.perfil, d.s_transicion, q_en, d.settings, glob, semilla=k * 7919)
            d.long_canal = d.L_valle * d.sinuosidad_real
            d.q_bankfull_boca = d.q_bankfull(d.L_valle, glob)
            d.q_flood_boca = d.q_flood(d.L_valle, glob)
            d.dd_m_ha = (d.L_valle / d.area_propia_ha) if d.area_propia_ha > 0 else 0.0
            self._secciones(d, glob)
            if d.perfil.ajustado and \
                    abs(d.perfil.s_cabecera * 100 - d.settings.pendiente_cabecera_pct) \
                    > glob.tol_pendiente_cabecera_pct:
                d.avisos.append(
                    f"'{d.nombre}': head/mouth elevations and slopes were not fully "
                    "compatible; slopes were minimally adjusted to keep a "
                    f"monotonic concave profile (result: {d.perfil.s_cabecera*100:.1f} % -> "
                    f"{d.perfil.s_boca*100:.1f} %).")
            # regla del método: la cabecera debe quedar a menos de la
            # 'distancia máx. de cresta a cabecera' del límite/divisoria
            if d.dens:
                g_cab = QgsGeometry.fromPointXY(QgsPointXY(d.dens[0][1], d.dens[0][2]))
                contorno = QgsGeometry.fromPolylineXY(
                    g_lim.asPolygon()[0] if not g_lim.isMultipart()
                    else g_lim.asMultiPolygon()[0][0])
                d_cab = contorno.distance(g_cab)
                if d_cab > glob.max_dist_cresta_cabecera:
                    d.avisos.append(
                        f"'{d.nombre}': the head is {d_cab:.0f} m from the boundary, more "
                        f"than the ridgeline-to-head distance ({glob.max_dist_cresta_cabecera:g} m): "
                        "the upslope hillside could erode and incise a channel.")
            self.avisos.extend(d.avisos)

        self._conectar_tributarios(disenos)
        self.disenos = {d.nombre: d for d in disenos}
        self._escribir_capas(disenos, glob)
        return self.disenos

    # ---------- continuidad del agua en las confluencias ----------
    def _conectar_tributarios(self, disenos, mezcla=18.0):
        """Pega la boca de cada tributario al EJE de su canal receptor.

        El fondo de valle del tributario acaba sobre el fondo de valle del
        principal, pero después los dos ejes se separan de su valle al meandrear
        —cada uno con su longitud de onda—, así que las bocas quedaban a unos
        metros del cauce receptor y el agua no tenía continuidad: dos líneas de
        rotura sueltas que además dejaban un escalón en el TIN.

        Se lleva el último punto del tributario EXACTAMENTE sobre el punto más
        próximo del eje receptor (en X, Y y Z) y se reparte esa corrección
        hacia aguas arriba a lo largo de 'mezcla' metros, con peso creciente,
        para que el empalme no haga un quiebro."""
        for d in disenos:
            padre = getattr(d, "_padre_obj", None)
            if padre is None or not d.puntos or not padre.puntos:
                continue
            bx, by = d.puntos[-1][0], d.puntos[-1][1]
            k = min(range(len(padre.puntos)),
                    key=lambda i: (padre.puntos[i][0] - bx) ** 2
                    + (padre.puntos[i][1] - by) ** 2)
            px, py, pz, _ = padre.puntos[k]
            dx, dy = px - bx, py - by
            dz = pz - d.puntos[-1][2]
            sep = math.hypot(dx, dy)
            if sep < 1e-6:
                continue
            L = d.puntos[-1][3]
            nuevos = []
            for x, y, z, s in d.puntos:
                w = max(0.0, 1.0 - (L - s) / max(mezcla, 1e-6))
                w = w * w * (3 - 2 * w)          # smoothstep: sin quiebro
                nuevos.append((x + dx * w, y + dy * w, z + dz * w, s))
            nuevos[-1] = (px, py, pz, L)
            d.puntos = nuevos
            if sep > 0.5:
                d.avisos.append(
                    f"'{d.nombre}': the mouth was {sep:.1f} m away from the "
                    f"'{padre.nombre}' centreline after meandering; it has been "
                    "tied to it so the water is continuous.")

    # ---------- orientación cabecera→boca ----------
    def _orientar(self, d, padre):
        pts = d.pts_2d
        if padre is None:
            # canal principal: orientar con el DEM (cabecera más alta)
            if self.dem is not None:
                z0 = st.cota_dem(self.dem, *pts[0])
                z1 = st.cota_dem(self.dem, *pts[-1])
                if z0 is not None and z1 is not None and z0 < z1:
                    d.pts_2d = list(reversed(pts))
        else:
            # tributario: la boca es el extremo más próximo al padre
            gp = QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in padre.pts_2d])
            d0 = gp.distance(QgsGeometry.fromPointXY(QgsPointXY(*pts[0])))
            d1 = gp.distance(QgsGeometry.fromPointXY(QgsPointXY(*pts[-1])))
            if d0 < d1:          # la confluencia está en el inicio → invertir
                d.pts_2d = list(reversed(pts))

    def _asignar_padre(self, d, disenos):
        """Padre = canal más próximo a alguno de los extremos, de entre los
        añadidos ANTES (regla del método: se conecta a un canal ya existente,
        lo que garantiza una red dendrítica sin ciclos)."""
        mejor, dist_min = None, float("inf")
        candidatos = disenos[:disenos.index(d)]
        for otro in candidatos:
            if otro is d:
                continue
            gp = QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in otro.pts_2d])
            for extremo in (d.pts_2d[0], d.pts_2d[-1]):
                dd = gp.distance(QgsGeometry.fromPointXY(QgsPointXY(*extremo)))
                if dd < dist_min:
                    dist_min, mejor = dd, otro
        d._padre_obj = mejor
        if dist_min > max(self.p.settings.max_dist_conexion_canales * 3, 10.0):
            self.avisos.append(f"'{d.nombre}': the confluence is {dist_min:.1f} m away "
                               "from the receiving channel; check the geometry.")

    def _confluencia(self, d):
        """Estación en el padre y margen R/L del tributario."""
        padre = d._padre_obj
        boca = d.pts_2d[-1]
        mejor_s, mejor_d, mejor_i = 0.0, float("inf"), 0
        for i, (s, x, y) in enumerate(padre.dens):
            dd = math.hypot(x - boca[0], y - boca[1])
            if dd < mejor_d:
                mejor_d, mejor_s, mejor_i = dd, s, i
        d.s_confluencia = mejor_s
        # dirección aguas abajo del padre en la confluencia
        i0 = max(0, mejor_i - 3)
        i1 = min(len(padre.dens) - 1, mejor_i + 3)
        dir_p = (padre.dens[i1][1] - padre.dens[i0][1],
                 padre.dens[i1][2] - padre.dens[i0][2])
        # vector desde la confluencia hacia el interior del tributario
        ref = d.pts_2d[-2] if len(d.pts_2d) >= 2 else d.pts_2d[0]
        v_in = (ref[0] - boca[0], ref[1] - boca[1])
        d.lado = lado_confluencia(dir_p, v_in)

    def _padre_de(self, d):
        return getattr(d, "_padre_obj", None)

    # ---------- subcuencas ----------
    def _particion_areas(self, disenos, g_lim, area_total_ha):
        """Partición del área del límite por proximidad al canal más cercano
        (aproximación de subcuencas hasta que existan las crestas en la Parte 3)."""
        bb = g_lim.boundingBox()
        paso = max(2.0, min(50.0, math.sqrt(area_total_ha * 10000.0 / 3000.0)))
        geoms = [QgsGeometry.fromPolylineXY(
            [QgsPointXY(x, y) for _, x, y in d.dens]) for d in disenos]
        cuenta = [0] * len(disenos)
        total = 0
        y = bb.yMinimum() + paso / 2
        while y < bb.yMaximum():
            x = bb.xMinimum() + paso / 2
            while x < bb.xMaximum():
                pt = QgsGeometry.fromPointXY(QgsPointXY(x, y))
                if g_lim.contains(pt):
                    total += 1
                    dmin, imin = float("inf"), 0
                    for i, g in enumerate(geoms):
                        dd = g.distance(pt)
                        if dd < dmin:
                            dmin, imin = dd, i
                    cuenta[imin] += 1
                x += paso
            y += paso
        for i, d in enumerate(disenos):
            d.area_propia_ha = area_total_ha * (cuenta[i] / total if total else 0.0)

    # ---------- perfiles ----------
    def _perfil_canal(self, d, padre, glob):
        c = d.settings
        # cota y pendiente de boca
        if padre is None:
            z_boca = c.cota_boca
            if z_boca is None and self.dem is not None:
                z_boca = st.cota_dem(self.dem, d.dens[-1][1], d.dens[-1][2])
            if z_boca is None:
                z_boca = 0.0
                d.avisos.append(f"'{d.nombre}': no DEM and no mouth elevation; using 0.")
            s_boca = (c.pendiente_boca_pct if c.pendiente_boca_pct is not None
                      else glob.pendiente_desembocadura) / 100.0
        else:
            z_boca = padre.perfil.z(d.s_confluencia)
            s_boca = padre.perfil.pendiente(d.s_confluencia)

        # cota de cabecera
        z_cab = c.cota_cabecera
        if z_cab is not None and self.dem is not None:
            z_dem = st.cota_dem(self.dem, d.dens[0][1], d.dens[0][2])
            if z_dem is not None and abs(z_cab - z_dem) > glob.tol_cota_cabecera_m:
                d.avisos.append(
                    f"'{d.nombre}': the specified head elevation ({z_cab:.2f} m) "
                    f"differs {abs(z_cab - z_dem):.2f} m from the terrain "
                    f"(tolerance {glob.tol_cota_cabecera_m:g} m).")
        if z_cab is None and self.dem is not None:
            z_cab = st.cota_dem(self.dem, d.dens[0][1], d.dens[0][2])
        if z_cab is None or z_cab <= z_boca:
            # sin dato o incoherente: derivar de las pendientes (parábola)
            s_cab_tmp = c.pendiente_cabecera_pct / 100.0
            z_cab = z_boca - d.L_valle * (s_cab_tmp + s_boca) / 2.0
            d.avisos.append(f"'{d.nombre}': head elevation derived from the profile "
                            f"({z_cab:.2f} m).")

        s_cab = c.pendiente_cabecera_pct / 100.0
        d.perfil = disenar_perfil(d.L_valle, z_cab, z_boca, s_cab, s_boca,
                                  concavidad=getattr(c, 'concavidad_perfil', 1.0))

        # transición A→valle
        s_nat = estacion_transicion(d.perfil, UMBRAL_PENDIENTE)
        if c.transicion_xy is not None:
            d.s_transicion = self._proyectar_estacion(d, c.transicion_xy)
            if s_nat is not None and d.s_transicion > s_nat + 5.0:
                d.avisos.append(
                    f"'{d.nombre}': the picked A-reach transition is at station "
                    f"{d.s_transicion:.0f} m but the profile already drops below "
                    f"4 % at {s_nat:.0f} m. The zig-zag ('A' channel) pattern is "
                    "applied only where the slope really exceeds 4 %; the rest "
                    "is drawn with sinusoidal meanders.")
        else:
            d.s_transicion = s_nat

        for hijo in sorted(self._hijos_de(d), key=lambda h: h.s_confluencia):
            self._perfil_canal(hijo, d, glob)

    def _hijos_de(self, d):
        return [x for x in self._todos if getattr(x, "_padre_obj", None) is d]

    def _proyectar_estacion(self, d, xy):
        mejor_s, mejor_d = 0.0, float("inf")
        for s, x, y in d.dens:
            dd = math.hypot(x - xy[0], y - xy[1])
            if dd < mejor_d:
                mejor_d, mejor_s = dd, s
        return mejor_s

    # ---------- secciones ----------
    def _secciones(self, d, glob):
        paso = max(glob.intervalo_estaciones, 1.0)
        s = 0.0
        d.secciones = []
        alertas_tau = 0
        while s <= d.L_valle + 1e-6:
            sv = min(s, d.L_valle)
            est = hidraulica_estacion(d, sv, glob)
            # posición sobre el eje (punto del eje más próximo en s de valle)
            idx = min(range(len(d.puntos)), key=lambda i: abs(d.puntos[i][3] - sv)) \
                if d.puntos else 0
            x, y, z, _ = d.puntos[idx] if d.puntos else (0, 0, est["cota"], sv)
            est["x"], est["y"], est["cota"] = x, y, z
            if est["estab_tau"] == "high":
                alertas_tau += 1
            d.secciones.append(est)
            s += paso
        if alertas_tau:
            d.avisos.append(
                f"'{d.nombre}': {alertas_tau} station(s) with tractive force above "
                "the Shields critical value (check D50, slopes or W:D; use "
                "'Highlight Tractive Force Zones').")

    # ---------- escritura de capas ----------
    def _escribir_capas(self, disenos, glob):


        # --- ejes 3D ---
        capa = self.lm.obtener_capa("GF_Channels")
        capa.dataProvider().truncate()
        feats = []
        for d in disenos:
            f = QgsFeature(capa.fields())
            f.setGeometry(QgsGeometry.fromPolyline(
                [QgsPoint(x, y, z) for x, y, z, _ in d.puntos]))
            estado, _, _ = st.evaluar_dd(d.dd_m_ha, glob.dd_objetivo, glob.dd_varianza_pct)
            f.setAttributes(attrs(capa, [
                d.nombre, d.padre, d.lado,
                round(d.L_valle, 2), round(d.long_canal, 2),
                round(d.sinuosidad_real, 3), round(d.area_propia_ha, 3),
                round(d.settings.area_adicional_ha, 3), round(d.dd_m_ha, 2),
                round(d.perfil.z_cabecera, 2), round(d.perfil.z_boca, 2),
                round(d.perfil.s_cabecera * 100, 2), round(d.perfil.s_boca * 100, 2),
                round(d.q_bankfull_boca, 4), round(d.q_flood_boca, 4),
                d.settings.coef_escorrentia, d.settings.vel_max_agua,
                d.settings.wd_pend_mayor_004, d.settings.wd_pend_menor_004,
                {"ok": "dd_ok", "baja": "dd_baja", "alta": "dd_alta"}[estado],
            ]))
            feats.append(f)
        capa.dataProvider().addFeatures(feats)
        capa.updateExtents(); capa.triggerRepaint()

        # --- bordes ---
        capa_b = self.lm.obtener_capa("GF_ChannelBanks")
        capa_b.dataProvider().truncate()
        feats = []
        for d in disenos:
            def sec_en(s):
                pend = d.perfil.pendiente(s)
                wd = d.settings.wd_pend_mayor_004 if abs(pend) > UMBRAL_PENDIENTE \
                    else d.settings.wd_pend_menor_004
                return dimensionar_seccion(d.q_bankfull(s, glob), d.q_flood(s, glob),
                                           wd, d.settings.vel_max_agua, pend)
            juegos = [
                ("bankfull", lambda s: sec_en(s).ancho_bankfull,
                 lambda s: sec_en(s).prof_bankfull),
                ("fondo", lambda s: sec_en(s).ancho_fondo, lambda s: 0.0),
                ("flood", lambda s: sec_en(s).ancho_flood, lambda s: sec_en(s).prof_flood),
            ]
            # 'Number of lines in a channel': 3 = eje+bankfull, 5 = +fondo, 7 = +flood
            n_lineas = int(getattr(glob, "lineas_por_canal", 7) or 7)
            juegos = juegos[:max(1, (n_lineas - 1) // 2)]
            for tipo, w_fn, dz_fn in juegos:
                izq, der = bordes_canal(d.puntos, w_fn, dz_fn)
                for sufijo, linea in (("izq", izq), ("der", der)):
                    f = QgsFeature(capa_b.fields())
                    f.setGeometry(QgsGeometry.fromPolyline(
                        [QgsPoint(x, y, z) for x, y, z in linea]))
                    f.setAttributes(attrs(capa_b, [d.nombre, f"{tipo}_{sufijo}"]))
                    feats.append(f)
        capa_b.dataProvider().addFeatures(feats)
        capa_b.updateExtents(); capa_b.triggerRepaint()

        # --- secciones ---
        capa_s = self.lm.obtener_capa("GF_XSections")
        capa_s.dataProvider().truncate()
        feats = []
        for d in disenos:
            for sc in d.secciones:
                f = QgsFeature(capa_s.fields())
                f.setGeometry(QgsGeometry(QgsPoint(sc["x"], sc["y"], sc["cota"])))
                f.setAttributes(attrs(capa_s, [
                    sc["canal"], round(sc["estacion"], 1), round(sc["cota"], 3),
                    round(sc["pendiente"], 3), sc["tipo"],
                    round(sc["ancho_bankfull"], 3), round(sc["prof_bankfull"], 3),
                    round(sc["area_bankfull"], 3), round(sc["ancho_flood"], 3),
                    round(sc["prof_flood"], 3), round(sc["area_flood"], 3),
                    round(sc["ancho_fondo"], 3),
                    round(sc["tension_bkf"], 2), round(sc["tension_fld"], 2),
                    round(sc["q_bankfull"], 4), round(sc["q_flood"], 4),
                    round(sc["area_ha"], 3), round(sc["perim_bkf"], 3),
                    round(sc["radio_hidr"], 3), round(sc["entrench"], 3),
                    round(sc["tau_crit"], 2), round(sc["ratio_tau"], 3),
                    sc["estab_tau"],
                    round(sc["calado_man"], 3), round(sc["vel_man"], 3),
                    round(sc["froude"], 3), sc["verif_man"],
                    round(sc["long_meandro"], 2), round(sc["cinturon"], 2),
                    round(sc["radio_curv"], 2),
                ]))
                feats.append(f)
        capa_s.dataProvider().addFeatures(feats)
        capa_s.updateExtents(); capa_s.triggerRepaint()


def recalcular_por_aportes(disenos, layer_manager, glob, log=None):
    """Segunda pasada hidráulica: pasa del área continua a la ESCALONADA.

    Una vez existen las vaguadas se sabe DÓNDE entra el agua de cada ladera.
    Cada vaguada entrega en su confluencia con el cauce la franja de ladera que
    drena, igual que un tributario entrega la de su cuenca, de modo que el área
    acumulada —y con ella el caudal, la sección, la velocidad y la tensión—
    crece a saltos y el canal queda dividido en tramos hidráulicamente
    homogéneos entre aporte y aporte. Es lo que describe el método: la sección
    solo cambia donde de verdad cambia el caudal.

    Devuelve el nº de canales recalculados."""
    log = log or (lambda *_a: None)
    capa = layer_manager.obtener_capa("GF_Swales", crear=False)
    if capa is None or capa.featureCount() == 0:
        return 0
    porcanal = {}
    for f in capa.getFeatures():
        nombre = f["channel"]
        d = disenos.get(nombre)
        if d is None or not d.puntos:
            continue
        vs = list(f.geometry().vertices())
        if not vs:
            continue
        # la vaguada arranca en el cauce: su primer vértice da la estación
        x0, y0 = vs[0].x(), vs[0].y()
        k = min(range(len(d.puntos)),
                key=lambda i: (d.puntos[i][0] - x0) ** 2 + (d.puntos[i][1] - y0) ** 2)
        porcanal.setdefault(nombre, []).append(d.puntos[k][3])
    n = 0
    for nombre, estaciones in porcanal.items():
        d = disenos[nombre]
        d.fijar_aportes(estaciones)
        if d.aportes:
            n += 1
    if not n:
        return 0
    # recalcular de aguas arriba hacia abajo para que los tributarios entreguen
    # su área acumulada ya actualizada
    def acumular(d):
        d.area_acumulada_ha = d.area_en(d.L_valle)
        for _, h in d.hijos:
            acumular(h)
        return d.area_acumulada_ha
    raices = [d for d in disenos.values() if not d.padre]
    for r in raices:
        for _, h in r.hijos:
            acumular(h)
        acumular(r)
    for d in disenos.values():
        d.q_bankfull_boca = d.q_bankfull(d.L_valle, glob)
        d.q_flood_boca = d.q_flood(d.L_valle, glob)
    # reescribir la capa de secciones con la hidráulica nueva
    try:
        from .compat import attrs as _attrs
        capa_s = layer_manager.obtener_capa("GF_XSections", crear=False)
        if capa_s is not None:
            capa_s.dataProvider().truncate()
            feats = []
            for d in disenos.values():
                paso = max(glob.intervalo_estaciones, 1.0)
                sv = 0.0
                d.secciones = []
                while sv <= d.L_valle + 1e-6:
                    est = hidraulica_estacion(d, min(sv, d.L_valle), glob)
                    idx = min(range(len(d.puntos)),
                              key=lambda i: abs(d.puntos[i][3] - est["estacion"])) \
                        if d.puntos else 0
                    x, y, z, _ = d.puntos[idx] if d.puntos else (0, 0, est["cota"], 0)
                    est["x"], est["y"], est["cota"] = x, y, z
                    d.secciones.append(est)
                    sv += paso
                for sc in d.secciones:
                    f = QgsFeature(capa_s.fields())
                    f.setGeometry(QgsGeometry(QgsPoint(sc["x"], sc["y"], sc["cota"])))
                    f.setAttributes(_attrs(capa_s, [
                        sc["canal"], round(sc["estacion"], 1), round(sc["cota"], 3),
                        round(sc["pendiente"], 3), sc["tipo"],
                        round(sc["ancho_bankfull"], 3), round(sc["prof_bankfull"], 3),
                        round(sc["area_bankfull"], 3), round(sc["ancho_flood"], 3),
                        round(sc["prof_flood"], 3), round(sc["area_flood"], 3),
                        round(sc["ancho_fondo"], 3),
                        round(sc["tension_bkf"], 2), round(sc["tension_fld"], 2),
                        round(sc["q_bankfull"], 4), round(sc["q_flood"], 4),
                        round(sc["area_ha"], 3), round(sc["perim_bkf"], 3),
                        round(sc["radio_hidr"], 3), round(sc["entrench"], 3),
                        round(sc["tau_crit"], 2), round(sc["ratio_tau"], 3),
                        sc["estab_tau"],
                        round(sc["calado_man"], 3), round(sc["vel_man"], 3),
                        round(sc["froude"], 3), sc["verif_man"],
                        round(sc["long_meandro"], 2), round(sc["cinturon"], 2),
                        round(sc["radio_curv"], 2)]))
                    feats.append(f)
            capa_s.dataProvider().addFeatures(feats)
            capa_s.updateExtents(); capa_s.triggerRepaint()
    except Exception as e:
        log(f"   · no se han podido reescribir las secciones: {e}")
    log(f"   · hidráulica recalculada por tramos: {n} canal(es) con "
        f"{sum(len(disenos[k].aportes) for k in porcanal)} aportes discretos "
        "de ladera")
    return n
