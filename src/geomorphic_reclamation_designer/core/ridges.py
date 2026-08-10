# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Crestas, subcrestas, vaguadas y subcuencas del diseño GeoFluv.

- SUBCUENCAS: partición del área del límite por proximidad a cada canal
  (polígonos de Voronoi de los puntos densificados de los ejes, disueltos por
  canal y recortados al límite). Es la divisoria natural "equidistante" que
  el método materializa como crestas entre canales adyacentes.
- CRESTAS PRINCIPALES: fronteras compartidas entre subcuencas (excluyendo el
  propio límite GeoFluv). Cota de cresta: z del canal más próximo + el desnivel
  de ladera que da `desnivel_de_ladera()`, que NO es una constante: se despeja
  de la propia ecuación del perfil que se va a dibujar (`perfil_trapezoidal`),
  igualando la pendiente de su tramo recto a la pendiente máxima de Ajustes:

      Δz = s_max · (D − lc/2 − lf/2)

  con D la distancia al canal, lc la porción convexa de cabeza y lf la cóncava
  del pie. Con los ajustes de los ejemplos de referencia eso queda entre
  0.55·s_max·D y 0.75·s_max·D. Se despeja en vez de fijarse porque una
  constante y una ecuación acaban desincronizándose: hasta la v1.0.18 este
  docstring decía (2/3)·s_max·D y el código usaba 0.5·s_max·D (ver B-024).
- SUBCRESTAS: en cada N-ésimo ápice de meandro (espaciado impar ⇒ márgenes
  alternas) nace una subcresta que sube desde el borde del canal hasta la
  divisoria, girada 'angulo_subcresta' hacia aguas arriba, con perfil de
  ladera convexo en cabeza y cóncavo al pie (smoothstep).
- VAGUADAS: entre subcrestas consecutivas, líneas de vaguada con perfil más
  cóncavo (u²) que drenan hacia el canal: crean el relieve ondulado de
  ladera característico del método.
"""

import math

from qgis.core import (
    QgsFeature, QgsGeometry, QgsPoint, QgsPointXY, QgsVectorLayer, QgsField,
)

from . import setup_tools as st
from .compat import tipo_geom, CAMPO_STR, attrs

PASO_CRESTA = 5.0     # m, densificado de crestas
PASO_MARCHA = 4.0     # m, paso de avance al trazar subcrestas


# ---------------------------------------------------------------- utilidades
def _smoothstep(u):
    u = max(0.0, min(1.0, u))
    return 3 * u * u - 2 * u ** 3


def tramos_de_ladera(D, lc, lf=None):
    """Longitudes (convexa de cabeza, cóncava de pie) ya acotadas.

    Existe para que `perfil_trapezoidal` y `desnivel_de_ladera` no puedan
    desincronizarse: la cota que se le pone a la cresta tiene que ser la que
    produce el perfil que luego se dibuja, no una parecida.
    """
    if lf is None:
        lf = min(lc, 0.30 * D)
    lc = max(0.5, min(lc, 0.6 * D))
    lf = max(0.5, min(lf, 0.9 * D - lc))
    return lc, lf


def desnivel_de_ladera(D, s_max, lc, lf=None):
    """Desnivel de una ladera de longitud D cuya pendiente MÁXIMA es s_max.

    En `perfil_trapezoidal` la pendiente del tramo central —que es la máxima de
    todo el perfil— vale `s_m = dz / (D − lc/2 − lf/2)`. Igualarla a s_max y
    despejar dz da el desnivel que agota justo la pendiente máxima de Ajustes
    ('Maximum straight-line slopes') sin superarla:

        Δz = s_max · (D − lc/2 − lf/2)

    NO es un múltiplo fijo de s_max·D: depende de cuánta ladera se lleven los
    tramos curvos. Con lc y lf saturados en sus topes (0.6·D y 0.3·D) sale
    0.55·s_max·D; con lc = 0.367·D sale (2/3)·s_max·D; y con una cabeza convexa
    pequeña frente a la ladera tiende a s_max·D, que es la ladera recta. Por
    eso se despeja y no se tabula: cualquier constante vale para un caso y
    falla en el resto.
    """
    if D <= 0:
        return 0.0
    lc, lf = tramos_de_ladera(D, lc, lf)
    return s_max * max(0.0, D - lc / 2.0 - lf / 2.0)


def perfil_trapezoidal(x_desde_cresta, D, dz, lc, lf=None):
    """Desnivel BAJO el extremo alto a distancia x de él, repartiendo el
    desnivel REAL dz (con signo) con la forma medida en el GeoFluv original
    (análisis del DXF de referencia, 57 perfiles):

    - cabeza CONVEXA de longitud lc junto al extremo alto (parábola,
      pendiente 0 en el extremo) — 'Maximum convex portion';
    - tramo CENTRAL casi recto de pendiente s_m;
    - pie CÓNCAVO de longitud lf junto al canal (parábola, pendiente 0).

    s_m = dz / (D − lc/2 − lf/2); la relación pendiente máx/media resulta
    ≈ 1.2–1.5 como en el original (la doble parábola anterior daba 2.0).
    dz puede ser negativo (línea que desciende hacia su empalme)."""
    lc, lf = tramos_de_ladera(D, lc, lf)
    s_m = dz / (D - lc / 2.0 - lf / 2.0)
    x = max(0.0, min(x_desde_cresta, D))
    if x <= lc:
        drop = s_m * x * x / (2.0 * lc)
    elif x <= D - lf:
        drop = s_m * (lc / 2.0 + (x - lc))
    else:
        y = x - (D - lf)
        drop = s_m * (lc / 2.0 + (D - lf - lc) + y - y * y / (2.0 * lf))
    return drop


def convexo_subcresta(glob, canal=None, D=None):
    """Longitud convexa (m) de subcresta según ajustes: por canal si
    'especificar_convexo', si no la global. Modo 'factor' = 1.5 × distancia
    cresta-cabecera(-swale); modo 'pct' = % de la longitud de la ladera."""
    if canal is not None and getattr(canal, "especificar_convexo", False):
        if getattr(canal, "convexo_modo_canal", "factor") == "pct" and D:
            return canal.convexo_pct_canal / 100.0 * D
        return 1.5 * getattr(canal, "dist_cresta_swale_m", 24.0)
    if glob.convexo_modo == "pct" and D:
        return glob.convexo_pct / 100.0 * D
    return 1.5 * glob.max_dist_cresta_cabecera


def _capa_puntos_canales(disenos, crs):
    """Capa temporal de puntos densificados de los ejes, con atributo 'canal'.
    Muestreo denso (todos los puntos del eje) para que la divisoria Voronoi
    entre subcuencas sea fiel a la equidistancia real entre canales."""
    lyr = QgsVectorLayer(f"Point?crs={crs}", "tmp_pts_canales", "memory")
    lyr.dataProvider().addAttributes([QgsField("canal", CAMPO_STR)])
    lyr.updateFields()
    feats = []
    for d in disenos.values():
        for i in range(0, len(d.puntos), 1):
            x, y, _, _ = d.puntos[i]
            f = QgsFeature(lyr.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            f.setAttributes(attrs(lyr, [d.nombre]))
            feats.append(f)
    lyr.dataProvider().addFeatures(feats)
    lyr.updateExtents()
    return lyr


def _geoms_ejes(disenos):
    return {n: QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y, _, _ in d.puntos])
            for n, d in disenos.items()}


def _z_ladera(pt, disenos, geoms, s_max, dem=None, cap_dem=False,
              contorno=None, banda_mezcla=0.0, convexo=None):
    """Cota de diseño en un punto de ladera/cresta: canal más próximo + Δz.

    `convexo` es la porción convexa de cabeza (m), o una función de la
    distancia que la devuelva; sale de `convexo_subcresta()`. Con ella se
    despeja el Δz de la ecuación del perfil (`desnivel_de_ladera`). Si no se
    pasa, se supone ladera recta sin cabeza convexa (Δz ≈ s_max·D).

    Continuidad con el relieve existente: dentro de la banda de mezcla junto
    al límite GeoFluv la cota de diseño se funde progresivamente con la del
    DEM, de modo que en el propio límite la cresta coincide con el terreno
    (sin escalones entre lo diseñado y lo existente)."""
    g = QgsGeometry.fromPointXY(QgsPointXY(*pt))
    mejor = None
    for n, ge in geoms.items():
        dist = ge.distance(g)
        if mejor is None or dist < mejor[0]:
            mejor = (dist, n)
    dist, n = mejor
    d = disenos[n]
    # z del canal en el punto más próximo
    i = min(range(0, len(d.puntos), 2),
            key=lambda k: (d.puntos[k][0] - pt[0]) ** 2 + (d.puntos[k][1] - pt[1]) ** 2)
    z_ch = d.puntos[i][2]
    # resguardo mínimo: donde las divisorias mueren en las confluencias la
    # distancia tiende a 0; sin resguardo el muestreo puede dejar la cresta
    # por debajo del lecho y crear charcos espurios en el TIN.
    lc = convexo(dist) if callable(convexo) else (0.5 if convexo is None
                                                  else convexo)
    z = z_ch + max(desnivel_de_ladera(dist, s_max, lc), 0.25)
    # --- mezcla con el DEM junto al límite (continuidad de relieve) ---
    if dem is not None and contorno is not None and banda_mezcla > 0:
        d_borde = contorno.distance(g)
        if d_borde < banda_mezcla:
            z_t = st.cota_dem(dem, pt[0], pt[1])
            if z_t is not None:
                w = (1.0 - d_borde / banda_mezcla) ** 2
                z = (1.0 - w) * z + w * z_t
    if cap_dem and dem is not None:
        z_t = st.cota_dem(dem, pt[0], pt[1])
        if z_t is not None:
            z = min(z, z_t)
    return z


# ------------------------------------------------------------- subcuencas
def generar_subcuencas(disenos, g_lim, lm, crs):
    """Voronoi de los ejes → recorte al límite → disolución por canal.
    Devuelve dict nombre → QgsGeometry (polígono de subcuenca)."""
    from qgis import processing
    pts = _capa_puntos_canales(disenos, crs)
    try:
        vor = processing.run("native:voronoipolygons",
                             {"INPUT": pts, "BUFFER": 100, "OUTPUT": "memory:"})["OUTPUT"]
    except Exception:
        vor = processing.run("qgis:voronoipolygons",
                             {"INPUT": pts, "BUFFER": 100, "OUTPUT": "memory:"})["OUTPUT"]
    dis = processing.run("native:dissolve",
                         {"INPUT": vor, "FIELD": ["canal"], "OUTPUT": "memory:"})["OUTPUT"]
    sub = {}
    for f in dis.getFeatures():
        g = f.geometry().intersection(g_lim)
        if g and not g.isEmpty():
            sub[f["canal"]] = g

    capa = lm.obtener_capa("GRD_SubWatershed")
    capa.dataProvider().truncate()
    feats = []
    for n, g in sub.items():
        d = disenos.get(n)
        area_ha = g.area() / 10000.0
        dd = (d.L_valle / area_ha) if (d and area_ha > 0) else 0.0
        f = QgsFeature(capa.fields())
        f.setGeometry(g)
        f.setAttributes(attrs(capa, [n, round(area_ha, 3), round(dd, 2)]))
        feats.append(f)
    capa.dataProvider().addFeatures(feats)
    capa.updateExtents(); capa.triggerRepaint()
    return sub


# ------------------------------------------------------------- crestas
def _cadenas_continuas(inter):
    """Convierte la intersección de dos subcuencas en CADENAS CONTINUAS.

    La frontera Voronoi entre dos subcuencas sale como una nube de micro-
    segmentos (en la v1.0.9 la divisoria main|main R1 salía partida en 48
    trozos de ~7 m). Se unen con mergeLines() y se ordenan por longitud.
    """
    if inter is None or inter.isEmpty():
        return []
    try:
        unida = inter.mergeLines()
        if unida is not None and not unida.isEmpty():
            inter = unida
    except Exception:
        pass
    partes = inter.asMultiPolyline() if inter.isMultipart() else [inter.asPolyline()]
    partes = [p for p in partes if len(p) >= 2]
    partes.sort(key=lambda p: -sum(
        math.hypot(p[i + 1].x() - p[i].x(), p[i + 1].y() - p[i].y())
        for i in range(len(p) - 1)))
    return partes


def _suavizar_xy(pts, pasadas=3, ventana=2):
    """Suaviza en planta una polilínea (media móvil) conservando los extremos.

    La divisoria de Voronoi es una escalera de bisectrices; una cresta real es
    una línea suave. Sin esto el TIN genera dientes de sierra sobre la
    divisoria."""
    if len(pts) < 5:
        return list(pts)
    out = list(pts)
    for _ in range(max(1, pasadas)):
        nuevo = [out[0]]
        for i in range(1, len(out) - 1):
            i0, i1 = max(0, i - ventana), min(len(out) - 1, i + ventana)
            n = i1 - i0 + 1
            nuevo.append((sum(p[0] for p in out[i0:i1 + 1]) / n,
                          sum(p[1] for p in out[i0:i1 + 1]) / n))
        nuevo.append(out[-1])
        out = nuevo
    return out


def puntos_confluencia(disenos):
    """Puntos (x, y, z) donde cada tributario se une a su receptor.

    La divisoria entre dos cuencas contiguas MUERE justo ahí: aguas abajo de
    la confluencia ya no hay dos cuencas que separar. Por eso la cresta tiene
    que terminar en ese punto exacto, en planta y en cota."""
    out = []
    for d in disenos.values():
        if getattr(d, "padre", "") and d.puntos:
            x, y, z, _ = d.puntos[-1]
            out.append((x, y, z))
    return out


def cortes_con_cauces(dens, disenos, geoms):
    """Puntos (x, y, z) donde la cadena de divisoria CRUZA el eje de un cauce.

    Una divisoria no puede atravesar un canal: al llegar al cauce la divisoria
    se ha acabado, porque al otro lado del agua empieza otra ladera de otra
    cuenca. La frontera de Voronoi sí puede cruzarlo (es un lugar geométrico,
    no una forma del terreno), y cuando lo hacía salía una cresta que pasaba
    por encima del canal principal. Aquí se localizan esos cruces para partir
    la cadena en ellos, con la cota del cauce en el punto de cruce."""
    if len(dens) < 2:
        return []
    linea = QgsGeometry.fromPolylineXY([QgsPointXY(x, y) for x, y in dens])
    cortes = []
    for nombre, ge in geoms.items():
        inter = linea.intersection(ge)
        if inter is None or inter.isEmpty():
            continue
        try:
            partes = inter.asGeometryCollection() if inter.isMultipart() else [inter]
        except Exception:
            partes = [inter]
        d = disenos[nombre]
        for pa in partes:
            try:
                pt = pa.centroid().asPoint()
            except Exception:
                continue
            i = min(range(len(d.puntos)),
                    key=lambda k: (d.puntos[k][0] - pt.x()) ** 2
                    + (d.puntos[k][1] - pt.y()) ** 2)
            cortes.append((pt.x(), pt.y(), d.puntos[i][2]))
    return cortes


def _partir_en_confluencias(dens, confluencias, tol):
    """Parte la cadena de divisoria EN la confluencia de cauces.

    La frontera Voronoi entre dos cuencas contiguas no es una línea que muere
    en la confluencia: es una **V que PASA por ella**. Aguas arriba del punto
    de unión hay divisoria por los dos lados del tributario, así que de ese
    punto salen DOS crestas, una hacia cada lado.

    Hasta la v1.0.13 se buscaba el vértice más próximo a la confluencia y se
    conservaba solo una de las dos mitades: la otra cresta desaparecía y esa
    ladera se quedaba sin divisoria (de ahí las cotas incoherentes y el cono de
    triangulación alrededor de la unión de los cauces).

    Devuelve una lista de (cadena, anclaje) donde anclaje = (extremo, z) indica
    qué extremo se ha pegado a la confluencia y con qué cota del cauce.
    """
    if not confluencias or len(dens) < 3:
        return [(dens, None)]
    # vértice de acercamiento máximo a cada confluencia
    mejor = None
    for cx, cy, cz in confluencias:
        for i, (x, y) in enumerate(dens):
            dd = math.hypot(x - cx, y - cy)
            if dd < tol and (mejor is None or dd < mejor[0]):
                mejor = (dd, i, (cx, cy, cz))
    if mejor is None:
        return [(dens, None)]
    _, i, (cx, cy, cz) = mejor
    margen = max(2, int(0.08 * len(dens)))
    # --- la confluencia cae en el INTERIOR: la cadena se PARTE en dos crestas
    if margen <= i <= len(dens) - 1 - margen:
        rama_a = list(dens[:i]) + [(cx, cy)]
        rama_b = [(cx, cy)] + list(dens[i + 1:])
        salida = []
        # cada rama se vuelve a examinar por si hay más puntos de anclaje
        # (una cadena larga puede cruzar varios cauces)
        restantes = [c for c in confluencias
                     if math.hypot(c[0] - cx, c[1] - cy) > tol]
        for rama, extremo in ((rama_a, "fin"), (rama_b, "ini")):
            if len(rama) < 3:
                continue
            sub = _partir_en_confluencias(rama, restantes, tol)
            if len(sub) == 1 and sub[0][1] is None:
                salida.append((rama, (extremo, cz)))
            else:
                salida.extend(sub)
        return salida or [(dens, None)]
    # --- la confluencia cae junto a un extremo: solo se engancha ese extremo
    if i <= len(dens) / 2:
        nueva = [(cx, cy)] + list(dens[i + 1:])
        return [(nueva if len(nueva) >= 3 else dens, ("ini", cz))]
    nueva = list(dens[:i]) + [(cx, cy)]
    return [(nueva if len(nueva) >= 3 else dens, ("fin", cz))]


def bisectrices_confluencia(disenos, radio=6.0):
    """Direcciones de salida de las crestas en cada confluencia de cauces.

    En la unión de un canal con su tributario nacen DOS crestas, una a cada
    lado del tributario, y cada una sale por la BISECTRIZ del ángulo que forman
    los dos cauces en ese lado. Es la dirección en la que los dos cauces son
    equidistantes, que es la definición misma de divisoria.

    Verificado contra el DXF del GeoFluv original en una confluencia real:
    con el eje principal entrando a 287.6 grados y el tributario a 6.4, las
    bisectrices predicen 327 y 57 grados y el original dibuja sus dos crestas a
    315 y 54.9 — 12 y 2 grados de diferencia.

    Devuelve [{'xy', 'z', 'dirs': [(dx, dy), (dx, dy)]}] por confluencia.
    """
    salida = []
    for d in disenos.values():
        padre = None
        for o in disenos.values():
            if o.nombre == getattr(d, "padre", ""):
                padre = o
        if padre is None or not d.puntos or not padre.puntos:
            continue
        bx, by, bz, _ = d.puntos[-1]
        # dirección del TRIBUTARIO hacia aguas arriba
        k = min(range(len(d.puntos)),
                key=lambda i: abs(math.hypot(d.puntos[i][0] - bx,
                                             d.puntos[i][1] - by) - radio))
        t_dx, t_dy = d.puntos[k][0] - bx, d.puntos[k][1] - by
        # punto del receptor más próximo y sus dos direcciones
        j = min(range(len(padre.puntos)),
                key=lambda i: (padre.puntos[i][0] - bx) ** 2
                + (padre.puntos[i][1] - by) ** 2)
        ja = max(0, j - max(1, int(radio)))
        jb = min(len(padre.puntos) - 1, j + max(1, int(radio)))
        p_arriba = (padre.puntos[ja][0] - bx, padre.puntos[ja][1] - by)
        p_abajo = (padre.puntos[jb][0] - bx, padre.puntos[jb][1] - by)

        def unit(v):
            L = math.hypot(*v) or 1.0
            return (v[0] / L, v[1] / L)

        tu, au, bu = unit((t_dx, t_dy)), unit(p_arriba), unit(p_abajo)
        # bisectriz entre el tributario y cada rama del receptor
        dirs = []
        for otra in (au, bu):
            bxr, byr = tu[0] + otra[0], tu[1] + otra[1]
            if math.hypot(bxr, byr) < 1e-6:      # cauces opuestos: perpendicular
                bxr, byr = -tu[1], tu[0]
            dirs.append(unit((bxr, byr)))
        salida.append({"xy": (bx, by), "z": bz, "dirs": dirs,
                       "canal": d.nombre, "padre": padre.nombre})
    return salida


def _salir_por_bisectriz(dens, anclaje, bisectrices, largo=30.0):
    """Rehace el arranque de una cresta anclada en una confluencia para que
    salga por la bisectriz, y lo funde con el resto de la cadena.

    La frontera de Voronoi da bien el recorrido lejano, pero junto a la unión
    de los cauces se retuerce; el original sale recto por la bisectriz y luego
    se curva. Se sustituyen los primeros 'largo' metros por el segmento de la
    bisectriz más próxima y se mezcla con la traza original."""
    if not anclaje or not bisectrices or len(dens) < 4:
        return dens
    extremo, _z = anclaje
    puntos = list(dens) if extremo == "ini" else list(dens)[::-1]
    ini = puntos[0]
    # bisectriz de la confluencia más próxima y con la dirección más parecida
    ref = None
    for b in bisectrices:
        if math.hypot(b["xy"][0] - ini[0], b["xy"][1] - ini[1]) > 3.0 * PASO_CRESTA:
            continue
        # hacia dónde va la cadena en sus primeros metros
        j = min(len(puntos) - 1, max(1, int(largo / PASO_CRESTA)))
        vx, vy = puntos[j][0] - ini[0], puntos[j][1] - ini[1]
        L = math.hypot(vx, vy) or 1.0
        for dx, dy in b["dirs"]:
            cos = (vx / L) * dx + (vy / L) * dy
            if ref is None or cos > ref[0]:
                ref = (cos, (dx, dy))
    if ref is None or ref[0] < 0.2:
        return dens
    dx, dy = ref[1]
    n = max(2, int(largo / PASO_CRESTA))
    nuevos = []
    for i, pt in enumerate(puntos):
        if i > n:
            nuevos.append(pt)
            continue
        w = i / n                       # 0 en la confluencia, 1 al final del tramo
        w = w * w * (3 - 2 * w)
        rx = ini[0] + dx * PASO_CRESTA * i
        ry = ini[1] + dy * PASO_CRESTA * i
        nuevos.append((rx * (1 - w) + pt[0] * w, ry * (1 - w) + pt[1] * w))
    return nuevos if extremo == "ini" else nuevos[::-1]


def generar_crestas(disenos, subcuencas, g_lim, glob, dem, lm):
    """GRD_Ridges = CRESTAS DIVISORIAS entre subcuencas.

    Dos cuencas contiguas solo pueden estar separadas por una CRESTA: lo que
    cae en una ladera va a un canal y lo que cae en la otra al otro. Por eso
    esta línea no se adapta al terreno original: es una divisoria de diseño,
    continua desde la confluencia hasta el límite GeoFluv, cuya cota nunca baja
    de la cota de cresta de diseño (canal + altura de ladera). Solo el extremo
    que muere en el límite empalma exactamente con el DEM, para que no haya
    escalón con el relieve existente.
    """
    s_max = glob.pendiente_max_pct / 100.0
    geoms = _geoms_ejes(disenos)
    contorno = QgsGeometry.fromPolylineXY(
        g_lim.asPolygon()[0] if not g_lim.isMultipart() else g_lim.asMultiPolygon()[0][0])
    # franja mínima para excluir SOLO los tramos de divisoria que discurren
    # pegados sobre el propio límite (la cresta debe llegar al borde, no
    # recorrerlo)
    banda_limite = contorno.buffer(0.5, 4)
    # longitud mínima de una divisoria con sentido físico
    long_min = max(4.0 * PASO_CRESTA, glob.max_dist_cresta_cabecera)
    confluencias = puntos_confluencia(disenos)
    bisectrices = bisectrices_confluencia(disenos)
    tol_conf = max(3.0 * PASO_CRESTA, glob.max_dist_cresta_cabecera)

    capa = lm.obtener_capa("GRD_Ridges")
    capa.dataProvider().truncate()
    feats = []
    crestas_3d = []      # [(QgsGeometry 2D, [z por vértice])] para subcrestas
    nombres = list(subcuencas.keys())
    for i in range(len(nombres)):
        for j in range(i + 1, len(nombres)):
            inter = subcuencas[nombres[i]].intersection(subcuencas[nombres[j]])
            if inter is None or inter.isEmpty():
                continue
            if tipo_geom(inter) != 1:
                # colección: quedarnos solo con las partes lineales
                try:
                    lineas = [g for g in inter.asGeometryCollection() if tipo_geom(g) == 1]
                except Exception:
                    lineas = []
                if not lineas:
                    continue
                inter = QgsGeometry.collectGeometry(lineas)
            inter = inter.difference(banda_limite)  # excluir tramos sobre el límite
            partes = _cadenas_continuas(inter)
            for pts in partes:
                dens = _densificar_xy(pts, PASO_CRESTA)
                largo = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                            for a, b in zip(dens[:-1], dens[1:]))
                if largo < long_min:
                    continue        # esquirla de Voronoi, no es una divisoria
                dens = _suavizar_xy(dens)
                # La divisoria PASA por la confluencia (se parte en dos crestas)
                # y NUNCA puede atravesar un cauce: los cruces con cualquier eje
                # de canal son también puntos de corte.
                anclas = list(confluencias) + cortes_con_cauces(dens, disenos, geoms)
                for k_r, (rama, anclaje) in enumerate(
                        _partir_en_confluencias(dens, anclas, tol_conf)):
                    largo_r = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                                  for a, b in zip(rama[:-1], rama[1:]))
                    if largo_r < 0.5 * long_min:
                        continue
                    rama = _salir_por_bisectriz(rama, anclaje, bisectrices)
                    linea, zs = _perfil_cresta(rama, disenos, geoms, s_max, dem,
                                               glob, contorno, anclaje=anclaje)
                    f = QgsFeature(capa.fields())
                    f.setGeometry(QgsGeometry.fromPolyline(linea))
                    f.setAttributes(attrs(capa, [
                        f"cresta {nombres[i]} | {nombres[j]}"
                        + (f" ({k_r + 1})" if k_r else "")]))
                    feats.append(f)
                    crestas_3d.append((QgsGeometry.fromPolylineXY(
                        [QgsPointXY(x, y) for x, y in rama]), zs))
    capa.dataProvider().addFeatures(feats)
    capa.updateExtents(); capa.triggerRepaint()
    return len(feats), crestas_3d


def _perfil_cresta(dens, disenos, geoms, s_max, dem, glob, contorno, anclaje=None):
    """Perfil longitudinal de una CRESTA DIVISORIA entre cuencas.

    Es una cresta de DISEÑO, no una copia del terreno: su cota en cada punto
    es, como mínimo, la cota de cresta que corresponde a la ladera (canal más
    próximo + `desnivel_de_ladera`, despejado del perfil). Sobre esa
    envolvente se traza un perfil longitudinal monótono, con la forma
    convexo/recto/cóncavo de las laderas, entre las cotas de los dos extremos:

      · extremo que muere en el LÍMITE GeoFluv → cota del DEM allí (empalme
        exacto con el relieve existente, sin escalón);
      · extremo que muere en una CONFLUENCIA (a <15 m de un canal) → cota del
        canal + 0.25 m (la divisoria se extingue en el punto donde se juntan
        los dos cauces);
      · cualquier otro extremo → cota mínima de cresta de diseño.

    A diferencia de la v1.0.9 el interior de la divisoria NO se funde con el
    DEM: fundirlo hacía que la "cresta" copiase la topografía original y en
    muchos tramos no separase realmente las dos cuencas.
    """
    # Porción convexa de la LADERA que sube hasta esta cresta (no la de la
    # cresta misma): es la que hay que meter en `desnivel_de_ladera` para que
    # la cota de coronación case con el perfil que dibujan las subcrestas.
    def _conv_ladera(D_ladera):
        return convexo_subcresta(glob, None, D_ladera)

    def z_extremo(pt):
        g = QgsGeometry.fromPointXY(QgsPointXY(*pt))
        if contorno is not None and contorno.distance(g) < 3.0 and dem is not None:
            z = st.cota_dem(dem, pt[0], pt[1])
            if z is not None:
                return z, "limite"
        # ¿muere en un canal (confluencia)?
        dmin, n_min = None, None
        for n, ge in geoms.items():
            dd = ge.distance(g)
            if dmin is None or dd < dmin:
                dmin, n_min = dd, n
        if dmin is not None and dmin < 15.0:
            d = disenos[n_min]
            i = min(range(len(d.puntos)),
                    key=lambda k: (d.puntos[k][0] - pt[0]) ** 2 +
                                  (d.puntos[k][1] - pt[1]) ** 2)
            return d.puntos[i][2] + 0.25, "confluencia"
        return (_z_ladera(pt, disenos, geoms, s_max, dem, False,
                          convexo=_conv_ladera), "cresta")

    zA, _ = z_extremo(dens[0])
    zB, _ = z_extremo(dens[-1])
    # extremo anclado a una confluencia: manda la cota del cauce en ese punto
    if anclaje:
        donde, z_conf = anclaje
        if donde == "ini":
            zA = z_conf
        else:
            zB = z_conf
    # orientar del extremo ALTO al bajo para el perfil
    if zB > zA:
        dens = dens[::-1]
        zA, zB = zB, zA
    s = [0.0]
    for a, b in zip(dens[:-1], dens[1:]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    D = max(s[-1], 1e-6)
    lc = min(1.5 * glob.max_dist_cresta_cabecera, 0.5 * D)
    # envolvente de cresta de diseño (sin mezcla con el DEM)
    z_env = [_z_ladera((pt[0], pt[1]), disenos, geoms, s_max, dem, False,
                       convexo=_conv_ladera)
             for pt in dens]
    zs = []
    n = len(dens)
    for k, si in enumerate(s):
        z = zA - perfil_trapezoidal(si, D, zA - zB, lc)
        if k == 0:
            z = zA
        elif k == n - 1:
            z = zB
        else:
            z = max(z, z_env[k])
        zs.append(z)
    # suavizado del perfil (media móvil) conservando extremos: evita que los
    # saltos de la envolvente dejen dientes en la cresta
    for _ in range(2):
        nuevo = [zs[0]]
        for k in range(1, n - 1):
            nuevo.append((zs[k - 1] + 2.0 * zs[k] + zs[k + 1]) / 4.0)
        nuevo.append(zs[-1])
        zs = [max(z, z_env[k]) if 0 < k < n - 1 else z
              for k, z in enumerate(nuevo)]
    linea = [QgsPoint(pt[0], pt[1], z) for pt, z in zip(dens, zs)]
    return linea, zs


def _densificar_xy(pts, paso):
    out = [(pts[0].x(), pts[0].y())]
    for a, b in zip(pts[:-1], pts[1:]):
        d = math.hypot(b.x() - a.x(), b.y() - a.y())
        n = max(1, int(d // paso))
        for k in range(1, n + 1):
            t = k / n
            out.append((a.x() + t * (b.x() - a.x()), a.y() + t * (b.y() - a.y())))
    return out



# ------------------------------------------------------------------ laderas
# Las subcrestas y las vaguadas viven en `hillslopes.py`. Se reexportan aquí
# para no romper el código que ya llamaba a ridges.generar_subcrestas(...).
# La importación es diferida (dentro de la función) porque hillslopes importa
# de este módulo y una importación circular a nivel de módulo fallaría.
def generar_subcrestas(*args, **kwargs):
    """Ver hillslopes.generar_subcrestas (reexportado por compatibilidad)."""
    from .hillslopes import generar_subcrestas as _g
    return _g(*args, **kwargs)


def _apices(*args, **kwargs):
    from .hillslopes import _apices as _g
    return _g(*args, **kwargs)


def _trazar_ladera(*args, **kwargs):
    from .hillslopes import _trazar_ladera as _g
    return _g(*args, **kwargs)


def _tangente_valle(*args, **kwargs):
    from .hillslopes import _tangente_valle as _g
    return _g(*args, **kwargs)
