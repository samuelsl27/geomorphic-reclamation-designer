# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Laderas del diseño GeoFluv: SUBCRESTAS y VAGUADAS.

Del ápice de cada meandro elegido nacen dos líneas desde el MISMO punto del
cauce: una SUBCRESTA hacia el interior de la curva y una VAGUADA hacia la
margen opuesta (patrón de espina de pez del libro de referencia, §2.2). Ambas
avanzan con un ángulo fijo respecto a la línea de valle —por eso salen
sub-paralelas y no se cruzan— y mueren en la divisoria con otro canal o en el
límite del proyecto.

Este módulo se separó de `ridges.py` (que se ocupa de las subcuencas y de las
crestas divisorias) para que cada fichero tenga una responsabilidad: aquí está
todo el trazado de ladera, allí la partición de cuencas. `ridges` reexporta lo
público de este módulo, de modo que el código que llamaba a
`ridges.generar_subcrestas(...)` sigue funcionando igual.
"""

import math

from qgis.core import (
    QgsFeature, QgsGeometry, QgsPoint, QgsPointXY, QgsSpatialIndex,
)

from . import setup_tools as st
from .compat import attrs
from .ridges import (
    PASO_CRESTA, PASO_MARCHA, perfil_trapezoidal, convexo_subcresta,
    convexo_vaguada, _geoms_ejes, _z_ladera,
)

# ------------------------------------------------------- subcrestas y vaguadas
def _apices(d):
    """Ápices de meandro: extremos locales del desplazamiento lateral del eje
    respecto a la línea de valle. Devuelve [(idx_punto, signo)]."""
    if len(d.puntos) < 5 or len(d.dens) < 2:
        return []
    # offset firmado de cada punto del eje respecto al valle
    import bisect
    est_valle = [p[0] for p in d.dens]
    offs = []
    for k, (x, y, _, s) in enumerate(d.puntos):
        i = min(max(bisect.bisect_left(est_valle, s) - 1, 0), len(d.dens) - 2)
        _, vx, vy = d.dens[i]
        _, vx1, vy1 = d.dens[i + 1]
        tx, ty = vx1 - vx, vy1 - vy
        L = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / L, tx / L
        offs.append((x - vx) * nx + (y - vy) * ny)
    # ápice = punto de máximo |offset| entre cruces por cero consecutivos
    # (garantiza la alternancia de márgenes por construcción)
    apices = []
    i0 = 0
    for k in range(1, len(offs)):
        if offs[k] * offs[k - 1] < 0 or k == len(offs) - 1:   # cruce o final
            km = max(range(i0, k + 1), key=lambda i: abs(offs[i]))
            if abs(offs[km]) > 0.3:
                apices.append((km, 1.0 if offs[km] > 0 else -1.0))
            i0 = k
    # depurar: si dos ápices consecutivos caen en la misma margen (micro-
    # oscilaciones filtradas), conservar solo el de mayor amplitud
    depurados = []
    for ap in apices:
        if depurados and depurados[-1][1] == ap[1]:
            if abs(offs[ap[0]]) > abs(offs[depurados[-1][0]]):
                depurados[-1] = ap
        else:
            depurados.append(ap)
    return depurados


def _cruce_con_borde(p_in, p_out, g_lim, iters=10):
    """Punto de corte del segmento p_in(dentro)→p_out(fuera) con el límite
    (bisección sobre el segmento)."""
    x0, y0 = p_in
    x1, y1 = p_out
    for _ in range(iters):
        xm, ym = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        if g_lim.contains(QgsGeometry.fromPointXY(QgsPointXY(xm, ym))):
            x0, y0 = xm, ym
        else:
            x1, y1 = xm, ym
    return (x0, y0)


def _recortar_cola(pts_xy, retranqueo):
    """NO SE USA. Recorta metros del final de una polilínea, en planta.

    Se conserva desconectada, como `divides._rehacer_laderas()`, porque el bug
    que provocó es fácil de reintroducir: se usaba para "retranquear" la
    cabecera de las vaguadas `dist_cresta_swale_m` metros por debajo de la
    divisoria. Ese ajuste NO es un retranqueo, es la longitud convexa de la
    vaguada [LIBRO p. 191], y amputarla dejaba las vaguadas 19 m por debajo del
    alcance de las subcrestas y demasiado tendidas (ver B-032 y ADR-019).

    Si vuelves a necesitar recortar una cola, que no sea para esto.
    """
    if retranqueo <= 0 or len(pts_xy) < 3:
        return list(pts_xy), 0.0
    largos = [math.hypot(b[0] - a[0], b[1] - a[1])
              for a, b in zip(pts_xy[:-1], pts_xy[1:])]
    total = sum(largos)
    if retranqueo >= total - PASO_MARCHA:
        retranqueo = max(0.0, total - PASO_MARCHA)
    restante = retranqueo
    out = list(pts_xy)
    while restante > 1e-9 and len(out) > 2:
        d = math.hypot(out[-1][0] - out[-2][0], out[-1][1] - out[-2][1])
        if d <= restante + 1e-9:
            out.pop()
            restante -= d
        else:
            t = (d - restante) / d
            out[-1] = (out[-2][0] + t * (out[-1][0] - out[-2][0]),
                       out[-2][1] + t * (out[-1][1] - out[-2][1]))
            restante = 0.0
    return out, retranqueo


TOL_TOQUE = 0.7 * PASO_MARCHA   # m (2.8), a partir de aquí se considera que la
                        # marcha ha alcanzado una línea de ladera ya trazada.
                        # Solo decide CUÁNDO se engancha, no dónde: el vértice
                        # final se pone sobre la otra línea, así que ya no deja
                        # una separación sistemática (ver B-034).


class _RegistroLaderas:
    """Líneas de ladera ya trazadas, con índice espacial.

    Antes era un dict por canal recorrido entero en CADA uno de los hasta 600
    pasos de cada marcha, y solo miraba las del PROPIO canal. Dos problemas:

    1. Dos laderas de canales distintos podían cruzarse sin que nada lo
       impidiera, y ninguna comprobación posterior lo arregla.
    2. Coste O(nº de líneas) por paso, sin índice, a diferencia de
       `topology._indice` y `divides.Corredor`, que sí lo usan.
    """

    def __init__(self):
        self.idx = QgsSpatialIndex()
        self.datos = {}
        self._n = 0

    def anadir(self, linea):
        geom = QgsGeometry.fromPolylineXY(
            [QgsPointXY(p.x(), p.y()) for p in linea])
        self._n += 1
        f = QgsFeature(self._n)
        f.setGeometry(geom)
        try:
            self.idx.addFeature(f)
        except Exception:
            pass
        self.datos[self._n] = (geom, [p.z() for p in linea])

    def mas_cercana(self, g, radio):
        """`(distancia, geom, zs)` de la línea más próxima dentro del radio.

        La MÁS PRÓXIMA, no la primera que aparezca: antes se rompía el bucle en
        la primera dentro del radio, en orden de inserción, así que la cota se
        heredaba de una línea que podía no ser la de al lado."""
        rect = g.boundingBox()
        rect.grow(radio)
        try:
            candidatas = self.idx.intersects(rect)
        except Exception:
            candidatas = list(self.datos.keys())
        mejor = None
        for fid in candidatas:
            par = self.datos.get(fid)
            if not par:
                continue
            d = par[0].distance(g)
            if d < radio and (mejor is None or d < mejor[0]):
                mejor = (d, par[0], par[1])
        return mejor


def _z_en_linea(geom_xy, zs, pt):
    """Cota de la polilínea (geom_xy, zs) en el vértice más próximo a pt."""
    try:
        res = geom_xy.closestSegmentWithContext(QgsPointXY(pt[0], pt[1]))
        after = res[2]
        idx = max(0, min(after - 1, len(zs) - 1))
        return zs[idx]
    except Exception:
        return zs[0] if zs else None


def _trazar_ladera(origen, direccion, propio, geoms, g_lim, disenos, s_max,
                   convexo_m, z0, dem=None, lineas_previas=None,
                   factor_fin=1.0, contorno=None, banda_mezcla=0.0,
                   forzar_bajo=False, crestas=None,
                   factor_dz=1.0, glob=None):
    """Marcha desde el borde del canal hacia la divisoria con dirección FIJA
    (todas las subcrestas/vaguadas del canal comparten el mismo ángulo con la
    perpendicular del valle, por lo que resultan sub-paralelas/equidistantes).

    Termina al: (a) cruzar la equidistancia con otro canal (divisoria),
    (b) llegar al límite GeoFluv (el extremo se recorta al límite), o
    (c) acercarse a una línea de ladera ya trazada (evita cruces).

    PERFIL 3D (corregido según Geomorphic Reclamation Design 2024, §2.2.4):
    la línea reparte el DESNIVEL REAL Δz entre el canal (z0) y su extremo:
      · extremo en el límite GeoFluv  → z_fin = cota del DEM (continuidad
        exacta con el relieve existente; nunca queda por debajo);
      · extremo en una divisoria interior → z_fin = cota de cresta de diseño
        (_z_ladera, la misma regla que las crestas principales, con mezcla
        DEM junto al borde) — así ambos lados de la divisoria empalman.
    La forma es el perfil de Horton (fig. 2-9): tramo llano CONVEXO junto a
    la cresta en la longitud xc ('Maximum convex portion'), tramo CÓNCAVO
    hacia el canal, llano en el pie. La pendiente máxima resulta
    s_j = 2·Δz/D — si el desnivel es pequeño, la ladera es suave (ya no se
    impone la pendiente máxima). 'factor_fin' (<1 en vaguadas) rebaja la cota
    del extremo interior para que la vaguada quede bajo las subcrestas."""
    pts_xy = [origen]
    x, y = origen
    dx, dy = direccion
    toco_borde = False
    linea_tocada = None       # (geom2d, zs) de la línea que ha detenido la marcha
    for _ in range(600):
        xn, yn = x + dx * PASO_MARCHA, y + dy * PASO_MARCHA
        g = QgsGeometry.fromPointXY(QgsPointXY(xn, yn))
        if not g_lim.contains(g):
            # recortar el extremo exactamente al límite
            xb, yb = _cruce_con_borde((x, y), (xn, yn), g_lim)
            if math.hypot(xb - x, yb - y) > 0.3:
                pts_xy.append((xb, yb))
            toco_borde = True
            break
        # No cruzar líneas de ladera ya trazadas. Si se alcanza una, la marcha
        # TERMINA SOBRE ELLA: se añade como último vértice el punto de esa
        # línea más próximo, y de ahí se hereda la cota. Hasta la v1.0.19 se
        # rompía el bucle SIN añadir nada, así que la línea quedaba entre 2.8 y
        # 6.8 m corta y el extremo alto se quedaba en el aire — medido en el
        # Ej_2: el 38 % de los extremos altos sin nada cerca, con un hueco
        # mediano de 10.1 m, frente al 13 % y 2.3 m del original. Ver B-034.
        #
        # Los tres primeros pasos no cuentan: la subcresta y la vaguada de un
        # mismo ápice nacen en el MISMO punto del cauce y se separarían al
        # instante por su propio arranque.
        if lineas_previas is not None and len(pts_xy) >= 3:
            cerca = lineas_previas.mas_cercana(g, TOL_TOQUE)
            if cerca is not None:
                _d, geom_lp, zs_lp = cerca
                linea_tocada = (geom_lp, zs_lp)
                try:
                    p_toque = geom_lp.nearestPoint(g).asPoint()
                    if math.hypot(p_toque.x() - x, p_toque.y() - y) > 0.3:
                        pts_xy.append((p_toque.x(), p_toque.y()))
                except Exception:
                    pass
                break
        d_propio = geoms[propio].distance(g)
        d_otro = min((ge.distance(g) for n, ge in geoms.items() if n != propio),
                     default=d_propio + 1)
        x, y = xn, yn
        pts_xy.append((x, y))
        if d_otro <= d_propio:      # divisoria alcanzada
            break
    if len(pts_xy) < 3:
        return None
    D = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts_xy[:-1], pts_xy[1:]))
    if D < PASO_MARCHA:
        return None
    if callable(convexo_m):
        conv_total = convexo_m(D)
    else:
        conv_total = convexo_m

    # --- cota del EXTREMO ALTO alcanzado (condición de contorno) ---
    fin = pts_xy[-1]
    z_div = None
    if toco_borde and dem is not None:
        # empalme EXACTO con el terreno del límite, aunque quede por debajo
        # del canal (comportamiento verificado en el DXF del original)
        z_div = st.cota_dem(dem, fin[0], fin[1])
    if z_div is None and linea_tocada is not None and linea_tocada[1]:
        # nace sobre una cresta ya trazada: hereda SU cota en ese punto
        z_div = _z_en_linea(linea_tocada[0], linea_tocada[1], fin)
    # --- cota de la CRESTA DIVISORIA en el extremo, si hay una cerca ---
    # Solo como RESPALDO, cuando esta ladera no tiene otra forma de saber a qué
    # cota muere. Hasta la v1.0.16 la cota de la divisoria actuaba además como
    # SUELO, y eso era un error de orden: la divisoria tenía un perfil propio,
    # empujaba a las laderas hacia arriba, y después `topology` volvía a
    # empujarla a ella hacia las laderas. De ese tira y afloja salían espolones
    # que suben y se hunden antes de morir, y divisorias con escalones de
    # metros. Ahora la ladera manda —su cota la fijan el perfil del cauce y los
    # parámetros de ladera, que es la física— y la divisoria se calcula después
    # como envolvente de las cabeceras que llegan a ella (`core/divides.py`).
    z_divisoria = None
    if crestas and z_div is None:
        g_fin = QgsGeometry.fromPointXY(QgsPointXY(fin[0], fin[1]))
        mejor = None
        radio = 6.0 * PASO_MARCHA
        for geom_cr, zs_cr in crestas:
            dcr = geom_cr.distance(g_fin)
            if dcr < radio and (mejor is None or dcr < mejor[0]):
                mejor = (dcr, _z_en_linea(geom_cr, zs_cr, fin))
        if mejor is not None and mejor[1] is not None:
            z_divisoria = mejor[1]
            z_div = z_divisoria
    if z_div is None:
        # sin `convexo`: la cota de coronacion la fija SIEMPRE la longitud
        # convexa de la SUBCRESTA, no la de la linea que pregunta (si no, la
        # vaguada coronaria mas alta que la subcresta vecina)
        z_div = _z_ladera(fin, disenos, geoms, s_max, dem, forzar_bajo,
                          contorno=contorno, banda_mezcla=banda_mezcla,
                          glob=glob)
    if not toco_borde:
        z_div = max(z_div, z0 + 0.25)   # drenaje interior siempre hacia el canal

    # NO se retranquea la cabecera. 'Maximum distance from ridgeline to swale
    # head' NO es un retranqueo: es la LONGITUD CONVEXA de la vaguada
    # [LIBRO p. 191], y ya está aplicada arriba, en `conv_total`. La vaguada
    # muere en la divisoria igual que la subcresta [LIBRO p. 211]; lo que la
    # hunde es que su tramo convexo es MÁS CORTO que el de las subcrestas
    # vecinas [LIBRO fig. 8-11, p. 204], no que sea más corta.
    # Amputarle esos metros la dejaba 19 m por debajo del alcance de las
    # subcrestas (44.0 m frente a 63.4) y demasiado tendida (10.8 % frente al
    # 24.0 % del original). Ver B-032 y ADR-019.
    z_fin = z_div
    if factor_fin < 1.0 and not toco_borde:
        z_fin = max(z0 + factor_fin * (z_fin - z0), z0 + 0.25)
    dz_total = (z_fin - z0) * float(factor_dz)

    # --- perfil medido en el original: convexo lc / recto / cóncavo al pie ---
    zs, acum = [], 0.0
    for i, (px, py) in enumerate(pts_xy):
        if i > 0:
            acum += math.hypot(px - pts_xy[i - 1][0], py - pts_xy[i - 1][1])
        drop = perfil_trapezoidal(D - acum, D, dz_total, conv_total)
        zs.append(z0 + (dz_total - drop))
    zs[-1] = z0 + dz_total
    return [QgsPoint(px, py, z) for (px, py), z in zip(pts_xy, zs)]


def _tangente_valle(d, s, ventana=4):
    """Tangente unitaria de la LÍNEA DE VALLE (no del eje sinuoso) en la
    estación s. Usar la tangente del valle hace que todas las subcrestas y
    vaguadas de un canal compartan la misma referencia angular — el ángulo en
    planta respecto al canal es igual para todas y las líneas resultan
    sub-paralelas (equidistantes), como en GeoFluv."""
    import bisect
    est = [p[0] for p in d.dens]
    i = min(max(bisect.bisect_left(est, s), 1), len(d.dens) - 1)
    i0 = max(0, i - ventana)
    i1 = min(len(d.dens) - 1, i + ventana)
    tx = d.dens[i1][1] - d.dens[i0][1]
    ty = d.dens[i1][2] - d.dens[i0][2]
    L = math.hypot(tx, ty) or 1.0
    return tx / L, ty / L


def generar_subcrestas(disenos, g_lim, glob, lm, dem=None, crestas=None,
                       ajustes_perfil=None):
    """Subcrestas y vaguadas por canal, según el patrón del método (libro
    2024, §2.2: 'A ridge on the inside of the apex of each bend and a swale
    on the wall of the opposite side of the valley'):

    - En cada ápice de meandro elegido (según 'Sub-ridge spacing'), del MISMO
      punto del canal nacen DOS líneas: la SUBCRESTA hacia el interior de la
      curva (lado del centro de curvatura) y la VAGUADA hacia la margen
      opuesta. Con espaciado impar los lados van alternando y ambas laderas
      quedan cubiertas por el patrón alterno cresta/vaguada (espina de pez).
    - Dirección: perpendicular a la LÍNEA DE VALLE girada 'Angle from
      sub-ridge to channel's perpendicular, upstream' — igual para todas ⇒
      líneas sub-paralelas y equidistantes en planta.
    - Una línea nunca cruza otra ya trazada (se detiene antes) y termina en
      la divisoria con otro canal o en el límite GeoFluv (con la cota del
      DEM: continuidad con el relieve existente).
    """
    s_max = glob.pendiente_max_pct / 100.0
    ang = math.radians(glob.angulo_subcresta_deg)
    geoms = _geoms_ejes(disenos)
    contorno = QgsGeometry.fromPolylineXY(
        g_lim.asPolygon()[0] if not g_lim.isMultipart()
        else g_lim.asMultiPolygon()[0][0])
    banda_mezcla = max(glob.max_dist_cresta_cabecera, 4.0 * PASO_CRESTA)

    capa_s = lm.obtener_capa("GRD_SubRidges")
    capa_v = lm.obtener_capa("GRD_Swales")
    capa_s.dataProvider().truncate()
    capa_v.dataProvider().truncate()
    fs, fv = [], []
    # Anti-cruce contra TODAS las líneas ya trazadas, de cualquier canal.
    # Antes se miraban solo las del propio canal, con el argumento de que las
    # de canales opuestos debían poder llegar las dos a la cresta de encuentro.
    # Pero llegar a la divisoria ya lo garantiza la condición de equidistancia
    # de Voronoi; lo único que conseguía la excepción era permitir que dos
    # laderas de canales distintos se cruzaran, sin que ninguna comprobación
    # posterior lo arreglara.
    registro = _RegistroLaderas()

    # 'Edit Longitudinal Profile' aplicado por la optimización: cada línea
    # puede subir o bajar su extremo alto un % del desnivel, en conjunto
    # (crestas_pct / vaguadas_pct) o línea a línea ('canal|indice').
    aj = ajustes_perfil or {}
    por_linea = aj.get("por_linea") or {}

    def _factor(tipo, canal, idx):
        clave = f"{canal}|{idx}"
        if clave in por_linea:
            return 1.0 + float(por_linea[clave]) / 100.0
        base = aj.get("crestas_pct" if tipo == "cresta" else "vaguadas_pct", 0.0)
        return 1.0 + float(base or 0.0) / 100.0

    def _traza(d, k, lado, convexo, factor_dz=1.0):
        return _linea_ladera_en(d, k, lado, ang, geoms, g_lim, disenos,
                                s_max, convexo=convexo, dem=dem,
                                lineas_previas=registro,
                                contorno=contorno,
                                banda_mezcla=banda_mezcla,
                                forzar_bajo=glob.forzar_crestas_bajo_limite,
                                crestas=crestas,
                                factor_dz=factor_dz, glob=glob)

    def _registrar(_d, linea):
        registro.anadir(linea)

    for d in disenos.values():
        aps = _apices(d)
        paso = max(1, d.settings.espaciado_subcrestas)
        # 'Sub-ridge spacing on sinusoidal channel' SOLO aplica al tramo
        # sinuoso (|s| < 4 %). En los tramos A en zigzag (> 4 %) el método
        # crea cresta/vaguada en CADA zigzag ("a ridge on the inside of the
        # apex of EACH zig-zag...", libro 2024 §2.2); su frecuencia la regula
        # el 'A' channel reach (longitud del zigzag), no este espaciado.
        elegidos = []
        n_valle = 0
        for k, signo in aps:
            en_tramo_A = d.es_tramo_A(d.puntos[k][3]) \
                if hasattr(d, "es_tramo_A") else False
            if en_tramo_A:
                elegidos.append((k, signo))          # todos los zigzags
            else:
                if n_valle % paso == 0:              # espaciado solo sinuoso
                    elegidos.append((k, signo))
                n_valle += 1
        # longitud convexa de subcresta (por canal o global; en modo 'pct'
        # depende de la longitud D de cada ladera → se pasa como función)
        conv_sub = lambda D, c=d.settings: convexo_subcresta(glob, c, D)
        # VAGUADAS. 'Maximum distance from ridgeline to swale head' es la
        # LONGITUD CONVEXA de la vaguada, no un retranqueo: ver
        # `ridges.convexo_vaguada` y [LIBRO p. 191 y fig. 8-11 p. 204]. La
        # depresión sale de que ese tramo convexo es MÁS CORTO que el de las
        # subcrestas vecinas, no de acortar la línea.
        _cv = convexo_vaguada(glob, d.settings)
        conv_vag = lambda D, v=_cv: min(v, 0.9 * D)

        # 1) TODAS las subcrestas del canal primero: así cada vaguada nace
        #    donde encuentra una cresta ya trazada y hereda su cota (el punto
        #    de encuentro de dos crestas es la cabecera del vallecillo).
        for idx, (k, signo) in enumerate(elegidos):
            # SUBCRESTA hacia el interior de la curva (lado opuesto al
            # abombamiento del ápice: el 'nose' de la cresta apunta al ápice)
            linea = _traza(d, k, -signo, conv_sub,
                           factor_dz=_factor('cresta', d.nombre, idx))
            if linea:
                f = QgsFeature(capa_s.fields())
                f.setGeometry(QgsGeometry.fromPolyline(linea))
                f.setAttributes(attrs(capa_s, [d.nombre, idx]))
                fs.append(f)
                _registrar(d, linea)
        # 2) VAGUADAS hacia la margen opuesta, desde el MISMO punto del canal
        for idx, (k, signo) in enumerate(elegidos):
            linea_v = _traza(d, k, signo, conv_vag,
                             factor_dz=_factor('vaguada', d.nombre, idx))
            if linea_v:
                f = QgsFeature(capa_v.fields())
                f.setGeometry(QgsGeometry.fromPolyline(linea_v))
                f.setAttributes(attrs(capa_v, [d.nombre, idx]))
                fv.append(f)
                _registrar(d, linea_v)
    capa_s.dataProvider().addFeatures(fs)
    capa_v.dataProvider().addFeatures(fv)
    for c in (capa_s, capa_v):
        c.updateExtents(); c.triggerRepaint()

    # --- salvaguarda de lógica general (libro): las laderas drenan AL canal.
    # Un extremo en el límite por debajo del arranque en el canal es un caso
    # legítimo de empalme (p. ej. fondo de corta más bajo), pero invierte el
    # drenaje local → se avisa para que el diseñador lo revise.
    avisos = []
    invertidas = 0
    for f in fs + fv:
        try:
            vs = list(f.geometry().vertices())
            if len(vs) >= 2 and vs[-1].z() < vs[0].z() - 0.05:
                invertidas += 1
        except Exception:
            pass
    if invertidas:
        avisos.append(
            f"{invertidas} sub-ridge/swale line(s) end BELOW their channel "
            "start (they tie into lower terrain at the boundary). Legitimate "
            "where the boundary is lower (e.g. pit floor), but local runoff "
            "there drains OUTWARD, not to the channel — review those areas.")
    return len(fs), len(fv), avisos


def _linea_ladera_en(d, k, signo, ang, geoms, g_lim, disenos, s_max,
                     convexo=None, dem=None, lineas_previas=None,
                     factor_fin=1.0, contorno=None, banda_mezcla=0.0,
                     forzar_bajo=False, crestas=None,
                     factor_dz=1.0, glob=None):
    """Construye la línea de ladera (subcresta o vaguada) que arranca del
    punto k del eje del canal d, hacia la margen 'signo', girada 'ang' hacia
    aguas arriba. La referencia angular es la tangente de la LÍNEA DE VALLE
    en esa estación (no la del eje sinuoso), de modo que el ángulo en planta
    respecto al cauce es el mismo para todas las líneas."""
    x, y, z, s_valle = d.puntos[k]
    tx, ty = _tangente_valle(d, s_valle)
    nx, ny = -ty * signo, tx * signo            # normal hacia la margen 'signo'
    # giro hacia aguas arriba: componente -t
    dx = nx * math.cos(ang) - tx * math.sin(ang)
    dy = ny * math.cos(ang) - ty * math.sin(ang)
    linea = _trazar_ladera((x, y), (dx, dy), d.nombre, geoms, g_lim, disenos,
                           s_max, convexo, z, dem=dem,
                           lineas_previas=lineas_previas,
                           factor_fin=factor_fin, contorno=contorno,
                           banda_mezcla=banda_mezcla, forzar_bajo=forzar_bajo,
                           crestas=crestas,
                           factor_dz=factor_dz, glob=glob)
    return linea
