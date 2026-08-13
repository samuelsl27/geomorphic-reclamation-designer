# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Revisión TOPOLÓGICA del relieve de ladera (segundo nivel jerárquico).

Las subcrestas y las vaguadas que salen de `hillslopes.py` son el primer nivel:
cada una nace en el cauce y sube hacia la divisoria. Pero un relieve natural no
se queda ahí — tiene una jerarquía:

1. Una cresta de ladera **muere sobre la cresta que delimita la cuenca**, no en
   el aire. Si su extremo alto se queda a unos metros de la divisoria, en el
   TIN aparece un escalón y, a menudo, una depresión cerrada.
2. Cuando **dos crestas de ladera convergen** aguas arriba, no se cruzan: se
   funden y de ese encuentro **nace una cresta nueva**, de orden superior, que
   sigue subiendo hasta la divisoria (o hasta otra cresta de orden aún mayor).
3. **Entre dos crestas nuevas hay un valle nuevo**: la vaguada que separa las
   dos laderas que acaban de unirse, y que baja desde el punto de encuentro.

Este módulo hace ese pase después de generar las laderas:

    empalmar_en_divisorias()  → regla 1
    crestas_de_encuentro()    → reglas 2 y 3

Trabaja sobre las capas ya escritas (GRD_SubRidges, GRD_Swales, GRD_Ridges), de
modo que es un post-proceso: si falla, el diseño de primer nivel sigue siendo
válido.
"""

import math

from qgis.core import (QgsFeature, QgsGeometry, QgsPoint, QgsPointXY,
                       QgsSpatialIndex)

from .compat import attrs

TOL_EMPALME = 18.0      # m, distancia máx. para considerar que una cresta
                        # muere sobre una divisoria
TOL_ENCUENTRO = 22.0    # m, distancia máx. entre dos extremos altos para
                        # considerar que las crestas se funden
LARGO_MAX_ENCUENTRO = 60.0   # m, longitud máxima de una cresta de encuentro:
                        # si la divisoria queda más lejos, ese encuentro no da
                        # lugar a una cresta de orden superior (antes salía una
                        # línea de 441 m atravesando media cuenca)
MAX_PENDIENTE_EMPALME = 1.00   # 100 %, cortapicos del tramo que se añade para
                        # empalmar una subcresta con su divisoria. NO es un
                        # objetivo de diseño: es el listón por debajo del cual
                        # el empalme deja de ser una cresta y pasa a ser un
                        # muro. Referencia medida en el DXF del original: sus
                        # 244 líneas de cresta no pasan de 65.7 %. Mismo valor
                        # que `divides.MAX_PENDIENTE_FILO`, por coherencia.
PASO = 4.0              # m, densificado de las líneas nuevas
TOL_PEGADO = 0.5        # m por debajo de los cuales el extremo de una ladera YA
                        # está sobre la divisoria y no hay nada que empalmar.
                        # Ver `empalmar_en_divisorias` y B-048.
MAX_ORDEN = 10          # órdenes de cresta como máximo. Una cresta nacida de
                        # un encuentro es de orden 2, la que nazca del
                        # encuentro de dos de esas es de orden 3… Igual que en
                        # una red de drenaje (Strahler). Diez órdenes cubren
                        # cuencas muy ramificadas con holgura; el tope solo
                        # está para que una geometría patológica no genere
                        # niveles indefinidamente.


# ------------------------------------------------------------------ utilidades
def _pts3(f):
    return [(v.x(), v.y(), v.z()) for v in f.geometry().vertices()]


def _extremo_hacia_divisoria(pts, idx=None, divisorias=None):
    """Extremo de una línea de ladera que muere contra la divisoria.

    Se MIDE, no se supone: de los dos extremos, el que se proyecta más cerca de
    la red de divisorias. Devuelve `(punto, en_inicio, proyección)`.

    Hasta la v1.0.18 esto era `return pts[-1]`, con el comentario «arranca
    siempre en el cauce». Deja de ser cierto en cuanto `divides` parte una
    línea contra el corredor o la invierte, y no lo es NUNCA para las líneas de
    encuentro (`channel = "junction"`), que van de alto a bajo. Cuando falla,
    `sellar_contra_divisorias` sube el PIE a la cota de la divisoria y luego
    fuerza monotonía ascendente: la línea entera queda invertida.

    Tampoco se identifica por cota — regla de oro nº 3: donde el cauce va en
    relleno la ladera desciende DESDE el cauce y el extremo que muere en la
    divisoria es el más bajo. Por construcción las divisorias están lejos del
    cauce (`Corredor` las recorta), así que el pie no puede ganar esta
    comparación.
    """
    # `idx` puede ser None (si QgsSpatialIndex falla): `_cercanas` lo absorbe
    # probando contra todas las divisorias. Lo único que impide medir es que no
    # haya ninguna divisoria contra la que proyectar.
    if not divisorias:
        return pts[-1], False, None
    r_ini = _mejor_proyeccion(idx, divisorias, pts[0])
    r_fin = _mejor_proyeccion(idx, divisorias, pts[-1])
    if r_ini is None:
        return pts[-1], False, r_fin
    if r_fin is None or r_ini[0] < r_fin[0]:
        return pts[0], True, r_ini
    return pts[-1], False, r_fin


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _proyectar_en(linea_xyz, pt):
    """(distancia, punto más próximo con su z) de pt sobre una polilínea 3D."""
    mejor = None
    for a, b in zip(linea_xyz[:-1], linea_xyz[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        if L2 < 1e-12:
            continue
        t = max(0.0, min(1.0, ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / L2))
        px, py = a[0] + t * dx, a[1] + t * dy
        pz = a[2] + t * (b[2] - a[2])
        d = math.hypot(pt[0] - px, pt[1] - py)
        if mejor is None or d < mejor[0]:
            mejor = (d, (px, py, pz))
    return mejor


def _indice(capa):
    """Índice espacial + geometrías 3D de una capa de líneas.

    Sin índice, cada extremo de ladera se proyectaría contra TODAS las
    divisorias y todos sus vértices: con dos canales da igual, pero con una red
    de cientos de cauces el coste crece como (nº de laderas × nº de divisorias
    × vértices) y el pase se vuelve inviable. Con el índice solo se prueban las
    pocas divisorias que caen cerca."""
    try:
        idx = QgsSpatialIndex(capa.getFeatures())
    except Exception:
        idx = None
    return idx, {f.id(): _pts3(f) for f in capa.getFeatures()
                 if f.geometry() and len(_pts3(f)) >= 2}


def _cercanas(idx, geoms, pt, k=6):
    """fids de las k divisorias más próximas a un punto (todas si no hay
    índice)."""
    if idx is None:
        return list(geoms.keys())
    try:
        return idx.nearestNeighbor(QgsPointXY(pt[0], pt[1]), k)
    except Exception:
        return list(geoms.keys())


def _proyecciones(idx, geoms, pt, k=6):
    """[(distancia, fid, punto sobre la línea)] ordenadas de más cerca a más
    lejos. En lista, y no solo la mejor, porque la divisoria más próxima EN
    PLANTA puede estar a una cota imposible: hay que poder descartarla y
    probar la siguiente."""
    salida = []
    for fid in _cercanas(idx, geoms, pt, k):
        d = geoms.get(fid)
        if not d:
            continue
        r = _proyectar_en(d, pt)
        if r:
            salida.append((r[0], fid, r[1]))
    salida.sort(key=lambda t: t[0])
    return salida


def _mejor_proyeccion(idx, geoms, pt, k=6):
    """(distancia, fid, punto sobre la línea) de la divisoria más próxima."""
    cand = _proyecciones(idx, geoms, pt, k)
    return cand[0] if cand else None


def _geoms2d(geoms):
    """Polilíneas 2D de un dict {fid: [(x, y, z)]}, construidas UNA vez."""
    salida = []
    for pts in geoms.values():
        if len(pts) >= 2:
            salida.append(QgsGeometry.fromPolylineXY(
                [QgsPointXY(x, y) for x, y, _z in pts]))
    return salida


def _cruza_alguna(p_a, p_b, geoms2d):
    """¿El segmento p_a-p_b corta alguna de las polilíneas de `geoms2d`?

    Se usa para no emparejar dos encuentros que tienen un cauce en medio: el
    valle que naciera entre ellos cruzaría el canal.
    """
    seg = QgsGeometry.fromPolylineXY([QgsPointXY(p_a[0], p_a[1]),
                                      QgsPointXY(p_b[0], p_b[1])])
    return any(seg.intersects(g) for g in geoms2d)


def _se_dobla(pts, alto, en_inicio, destino):
    """¿La cola que se va a añadir se dobla sobre la propia línea?

    Una subcresta o una vaguada son RECTAS en planta —lo son en el original: las
    117 vaguadas del Ej_2 tienen sinuosidad 1.000 y ángulo de giro máximo 0.00°—
    así que una prolongación que salga hacia atrás no es una prolongación, es un
    pliegue. Segunda línea de defensa de B-048: aunque alguien vuelva a abrir la
    puerta a extender dos veces la misma línea, un pliegue no puede entrar."""
    vecino = pts[1] if en_inicio else pts[-2]
    ax, ay = alto[0] - vecino[0], alto[1] - vecino[1]
    bx, by = destino[0] - alto[0], destino[1] - alto[1]
    na, nb = math.hypot(ax, ay), math.hypot(bx, by)
    if na < 1e-9 or nb < 1e-9:
        return False
    return (ax * bx + ay * by) / (na * nb) < 0.0


def _densificar3(p0, p1, paso=PASO):
    """Segmento 3D densificado, con la z interpolada linealmente."""
    d = _dist(p0, p1)
    n = max(1, int(d // paso))
    out = []
    for k in range(n + 1):
        t = k / n
        out.append((p0[0] + t * (p1[0] - p0[0]),
                    p0[1] + t * (p1[1] - p0[1]),
                    p0[2] + t * (p1[2] - p0[2])))
    return out


def destino_de_empalme(pts, alto, en_inicio, cand, tol=TOL_EMPALME):
    """Punto de divisoria hasta el que prolongar una ladera, o None.

    `cand` es `[(distancia, fid, punto)]` ordenado, tal y como lo devuelve
    `_proyecciones`. Es la decisión entera del empalme, y vive fuera de
    `empalmar_en_divisorias` porque necesita prueba propia: `revisar()` repite
    ese pase hasta punto fijo y una decisión no idempotente se multiplica por
    treinta.

    **B-048.** El primer filtro era `if d_xy < 0.5 or d_xy > tol: continue`
    dentro del bucle de candidatas, así que cuando el extremo ya estaba sobre
    una divisoria no paraba: descartaba **esa** candidata y se iba a la
    SIGUIENTE, hasta 18 m más allá, y volvía a prolongar. En la pasada siguiente
    la más próxima era la que acababa de alcanzar —descartada otra vez— y volvía
    a la primera: ping-pong, una cola por pasada.

    Medido en el Ej_2: `GRD_SubRidges` fid 86, canal "main R2", índice 15, con
    **66 vértices oscilando entre tres puntos**, 260.6 m de longitud, sinuosidad
    **8.318** y 28 giros de más de 60°, con máximo de **180.00°**. Otras quince
    subcrestas con anomalías menores del mismo origen. Y de paso el bucle no
    convergía nunca, así que se comía las 30 pasadas de `MAX_PASADAS` (P-05).
    """
    if cand and cand[0][0] < TOL_PEGADO:
        return None                     # ya muere sobre la divisoria: no se toca
    for d_xy, _fid, punto in cand:
        if d_xy > tol:
            continue
        # La divisoria más próxima EN PLANTA puede estar a una cota imposible.
        # Sin esta comprobación se pegaba la diferencia entera en un solo
        # segmento: medido en el Ej_2, una subcresta subía de 300.7 a 336.0 m en
        # 3.69 m de recorrido, un 955 %. El original no pasa de 65.7 % en
        # ninguna de sus 244 líneas.
        if abs(punto[2] - alto[2]) > MAX_PENDIENTE_EMPALME * d_xy:
            continue
        if _se_dobla(pts, alto, en_inicio, punto):
            continue
        return punto
    return None


# ------------------------------------------------------- regla 1: empalmes
def empalmar_en_divisorias(lm, tol=TOL_EMPALME, log=None):
    """Prolonga hasta la divisoria las crestas de ladera que se quedan cerca.

    El extremo alto se lleva EXACTAMENTE sobre la línea de la cresta divisoria,
    en planta y en cota. Devuelve cuántas se han empalmado."""
    log = log or (lambda *_a: None)
    capa_div = lm.obtener_capa("GRD_Ridges", crear=False)
    capa_sr = lm.obtener_capa("GRD_SubRidges", crear=False)
    if capa_div is None or capa_sr is None or capa_div.featureCount() == 0:
        return 0
    idx, divisorias = _indice(capa_div)
    if not divisorias:
        return 0
    cambios, descartados, ya_estaban = {}, 0, 0
    for f in capa_sr.getFeatures():
        pts = _pts3(f)
        if len(pts) < 2:
            continue
        alto, en_inicio, _ = _extremo_hacia_divisoria(pts, idx, divisorias)
        cand = _proyecciones(idx, divisorias, alto)
        # «Ya muere sobre la divisoria» y «no se puede empalmar» son cosas
        # distintas y se cuentan aparte: la primera es el caso sano y desde
        # B-048 es mayoría, así que meterlas en el mismo saco convertía el aviso
        # del registro en una alarma falsa de casi cien líneas.
        if cand and cand[0][0] < TOL_PEGADO:
            ya_estaban += 1
            continue
        destino = destino_de_empalme(pts, alto, en_inicio, cand, tol)
        if destino is None:
            descartados += 1
            continue
        cola = _densificar3(alto, destino)[1:]
        if not cola:
            continue
        # La cola se añade por el extremo que corresponda: si la línea viene
        # invertida, `pts + cola` la dejaría con un pico en medio.
        nuevos = (list(reversed(cola)) + pts) if en_inicio else (pts + cola)
        cambios[f.id()] = QgsGeometry.fromPolyline(
            [QgsPoint(x, y, z) for x, y, z in nuevos])
    if cambios:
        capa_sr.startEditing()
        for fid, g in cambios.items():
            capa_sr.changeGeometry(fid, g)
        capa_sr.commitChanges()
        capa_sr.triggerRepaint()
    log(f"   · {len(cambios)} subcresta(s) prolongada(s) hasta morir sobre la "
        f"cresta divisoria ({ya_estaban} ya morían sobre ella)")
    if descartados:
        # No se calla: una subcresta que no empalma deja un hueco en planta, y
        # el hueco tiene que poder verse en el registro. La cota la resuelve
        # despues `divides`, que baja la divisoria a la cota de la cabecera.
        log(f"   · {descartados} subcresta(s) sin empalmar: la divisoria mas "
            "proxima quedaba a una cota inalcanzable")
    return len(cambios)


# --------------------------------------- reglas 2 y 3: encuentros y valles
def _agrupar_extremos(items, tol):
    """Agrupa extremos altos próximos. items = [(pt3, clave)]."""
    grupos = []
    usados = set()
    for i, (p, k) in enumerate(items):
        if i in usados:
            continue
        grupo = [(p, k)]
        usados.add(i)
        for j in range(i + 1, len(items)):
            if j in usados:
                continue
            if _dist(p, items[j][0]) <= tol:
                grupo.append(items[j])
                usados.add(j)
        if len(grupo) >= 2:
            grupos.append(grupo)
    return grupos


def crestas_de_encuentro(lm, glob, log=None, tol=TOL_ENCUENTRO):
    """Donde dos crestas de ladera se funden nace una cresta NUEVA, y entre dos
    crestas nuevas nace un valle NUEVO.

    - Se buscan grupos de extremos altos de subcrestas que caen a menos de
      'tol' entre sí y que NO están ya sobre una divisoria.
    - Del punto de encuentro sale una cresta de orden superior hasta la
      divisoria más próxima, subiendo desde la cota del encuentro hasta la de
      la divisoria.
    - Entre dos crestas nuevas consecutivas se traza la vaguada que las separa,
      que baja desde el punto de encuentro hacia el canal.

    Devuelve (n_crestas_nuevas, n_vaguadas_nuevas)."""
    log = log or (lambda *_a: None)
    capa_div = lm.obtener_capa("GRD_Ridges", crear=False)
    capa_sr = lm.obtener_capa("GRD_SubRidges", crear=False)
    capa_sw = lm.obtener_capa("GRD_Swales", crear=False)
    if capa_div is None or capa_sr is None:
        return 0, 0
    idx, divisorias = _indice(capa_div)
    if not divisorias:
        return 0, 0

    items = []
    for f in capa_sr.getFeatures():
        pts = _pts3(f)
        if len(pts) < 2:
            continue
        alto, _en_inicio, _proy = _extremo_hacia_divisoria(pts, idx, divisorias)
        # una cresta ya de orden alto no vuelve a engendrar otro nivel
        try:
            orden = -int(f["index"]) if str(f["channel"]) == "junction" else 1
        except Exception:
            orden = 1
        if orden >= MAX_ORDEN:
            continue
        # si ya está sobre una divisoria no es un encuentro: es un empalme
        r0 = _mejor_proyeccion(idx, divisorias, alto)
        if r0 is not None and r0[0] < 2.0:
            continue
        items.append((alto, (f["channel"], f["index"], pts, orden)))

    grupos = _agrupar_extremos(items, tol)
    if not grupos:
        log("   · no hay encuentros de crestas que generen un nivel superior")
        return 0, 0

    nuevas_crestas = []
    nuevas_vaguadas = []
    for grupo in grupos:
        # punto de encuentro: media en planta, la cota MÁS ALTA de las que
        # llegan (la nueva cresta arranca en el punto alto de la unión)
        xs = sum(p[0] for p, _ in grupo) / len(grupo)
        ys = sum(p[1] for p, _ in grupo) / len(grupo)
        zs = max(p[2] for p, _ in grupo)
        encuentro = (xs, ys, zs)
        # divisoria más próxima
        mejor = _mejor_proyeccion(idx, divisorias, encuentro)
        if mejor is None or mejor[0] < PASO or mejor[0] > LARGO_MAX_ENCUENTRO:
            continue
        destino = mejor[2]
        if destino[2] <= encuentro[2] + 0.1:
            # la divisoria no está por encima: no hay cresta nueva que subir
            continue
        orden_nuevo = min(MAX_ORDEN,
                          max(g[1][3] for g in grupo) + 1)
        nuevas_crestas.append((_densificar3(encuentro, destino), orden_nuevo))

    # --- valles nuevos entre crestas nuevas ---
    #
    # Antes esto tenía dos fallos de bulto, ninguno visible en los ejemplos de
    # referencia (que no generan ni una sola línea 'junction'), pero que
    # aparecerán en cuanto una cuenca los genere:
    #
    # 1. Se emparejaban ordenando por COORDENADA X. Dos encuentros de laderas
    #    opuestas del mismo valle —o de cuencas distintas— quedaban
    #    "consecutivos" y el valle resultante cruzaba el cauce.
    # 2. El extremo bajo era una EXTRAPOLACIÓN a ciegas: dirección la
    #    bisectriz, longitud 0.6 × la distancia al punto medio de los destinos
    #    y cota `med.z − 0.35·s_max·largo`, un gradiente que no sale de
    #    `perfil_trapezoidal` ni de ningún ajuste. La línea terminaba donde
    #    terminaba, en mitad de la ladera, y nada la recogía después: las cuatro
    #    reglas de `topology` tocan extremos altos, y `divides` también.
    #    Resultado: un escalón directo en el TIN.
    #
    # Ahora se empareja por PROXIMIDAD REAL, se descartan las parejas separadas
    # por un cauce, y el valle MUERE EN EL CAUCE, con su cota — igual que
    # cualquier otra vaguada. A partir de ahí `divides.ajustar_divisorias` lo
    # trata como a las demás: lo recorta contra el corredor y le pega el pie a
    # la coronación de la orilla.
    capa_ch = lm.obtener_capa("GRD_Channels", crear=False)
    idx_ch, canales = _indice(capa_ch) if capa_ch is not None else (None, {})
    if len(nuevas_crestas) >= 2 and capa_sw is not None and canales:
        ejes2d = _geoms2d(canales)
        pendientes = list(nuevas_crestas)
        usados = set()
        for i, ca in enumerate(pendientes):
            if i in usados:
                continue
            p_a = ca[0][0]
            mejor_j, mejor_d = None, None
            for j, cb in enumerate(pendientes):
                if j == i or j in usados:
                    continue
                d = _dist(p_a, cb[0][0])
                if d > 6.0 * tol or (mejor_d is not None and d >= mejor_d):
                    continue
                if _cruza_alguna(p_a, cb[0][0], ejes2d):
                    continue      # hay un cauce en medio: no son vecinas
                mejor_j, mejor_d = j, d
            if mejor_j is None:
                continue
            p_b = pendientes[mejor_j][0][0]
            usados.add(i)
            usados.add(mejor_j)
            # arranque del valle: punto medio entre los dos encuentros, a la
            # cota MENOR de los dos (un valle nace en el punto bajo del collado)
            med = ((p_a[0] + p_b[0]) / 2.0, (p_a[1] + p_b[1]) / 2.0,
                   min(p_a[2], p_b[2]) - 0.25)
            r = _mejor_proyeccion(idx_ch, canales, med)
            if r is None or r[0] < PASO:
                continue
            destino = r[2]
            if destino[2] >= med[2] - 0.1:
                continue          # el cauce no queda por debajo: no hay valle
            nuevas_vaguadas.append(_densificar3(med, destino))

    # --- escritura ---
    feats = []
    for linea, orden_nuevo in nuevas_crestas:
        f = QgsFeature(capa_sr.fields())
        f.setGeometry(QgsGeometry.fromPolyline(
            [QgsPoint(x, y, z) for x, y, z in linea]))
        # el índice negativo guarda el ORDEN de la cresta nueva
        f.setAttributes(attrs(capa_sr, ["junction", -orden_nuevo]))
        feats.append(f)
    if feats:
        capa_sr.dataProvider().addFeatures(feats)
        capa_sr.updateExtents(); capa_sr.triggerRepaint()
    fv = []
    for linea in nuevas_vaguadas:
        f = QgsFeature(capa_sw.fields())
        f.setGeometry(QgsGeometry.fromPolyline(
            [QgsPoint(x, y, z) for x, y, z in linea]))
        f.setAttributes(attrs(capa_sw, ["junction", -1]))
        fv.append(f)
    if fv:
        capa_sw.dataProvider().addFeatures(fv)
        capa_sw.updateExtents(); capa_sw.triggerRepaint()

    log(f"   · {len(feats)} cresta(s) de orden superior nacidas del encuentro "
        f"de crestas de ladera y {len(fv)} valle(s) nuevo(s) entre ellas")
    return len(feats), len(fv)


MEZCLA_SELLADO = 25.0    # m sobre los que se reparte la corrección del sellado


def _sellar_extremo(pts, z_nuevo, en_inicio=False, mezcla=MEZCLA_SELLADO):
    """Lleva a 'z_nuevo' el extremo de una línea de ladera que muere sobre la
    divisoria, REPARTIENDO la corrección hacia dentro.

    Mover solo el último vértice era un error: cuando la corrección es grande
    y hacia abajo, el penúltimo vértice se queda por encima del último y la
    línea deja de ser monótona. En una ladera corta —las que salen recortadas
    junto a una confluencia— eso produce un pico de varios metros en dos
    metros de recorrido, que es exactamente el diente que luego aparece en el
    TIN.

    Es exactamente lo que hace `divides.ajustar_extremo`, así que se delega en
    ella en vez de mantener dos veces el mismo reparto con smoothstep. Tenerlo
    duplicado ya salió caro: la mezcla adaptativa que evita las mesetas se
    añadió a una de las dos copias y la otra se habría quedado atrás.
    """
    from .divides import ajustar_extremo
    return ajustar_extremo(pts, z_nuevo, en_inicio=en_inicio, mezcla=mezcla)


def sellar_contra_divisorias(lm, log=None, tol=2.5):
    """Pasada final: ninguna línea de ladera puede sobresalir de la divisoria.

    Al fundir, la divisoria se levanta; una cresta que ya estaba apoyada en
    ella antes del levantamiento podría quedar por encima o por debajo por unos
    centímetros, y ese desajuste es justo el que la triangulación convierte en
    un diente o en una depresión cerrada. Aquí se iguala la cota del extremo a
    la de la divisoria en ese punto y se reparte la corrección hacia abajo."""
    log = log or (lambda *_a: None)
    capa_div = lm.obtener_capa("GRD_Ridges", crear=False)
    if capa_div is None or capa_div.featureCount() == 0:
        return 0
    idx, divs = _indice(capa_div)
    n = 0
    for nombre in ("GRD_SubRidges", "GRD_Swales"):
        capa = lm.obtener_capa(nombre, crear=False)
        if capa is None:
            continue
        cambios = {}
        for f in capa.getFeatures():
            pts = _pts3(f)
            if len(pts) < 2:
                continue
            # El extremo que muere en la divisoria se MIDE. Suponiendo que era
            # `pts[-1]` bastaba con que `divides` hubiera partido o invertido
            # la linea para acabar subiendo el PIE a la cota de la divisoria y
            # forzando monotonia despues: la linea entera quedaba del reves.
            alto, en_inicio, mejor = _extremo_hacia_divisoria(pts, idx, divs)
            if mejor is None or mejor[0] > tol:
                continue
            if abs(alto[2] - mejor[2][2]) < 0.02:
                continue
            cambios[f.id()] = _sellar_extremo(pts, mejor[2][2],
                                              en_inicio=en_inicio)
        if cambios:
            capa.startEditing()
            for fid, pts in cambios.items():
                capa.changeGeometry(fid, QgsGeometry.fromPolyline(
                    [QgsPoint(x, y, z) for x, y, z in pts]))
            capa.commitChanges()
            capa.triggerRepaint()
            n += len(cambios)
    if n:
        log(f"   · {n} extremo(s) de ladera igualado(s) a la cota exacta de la "
            "divisoria")
    return n


# ------------------------------------------- regla 2: fusión de crestas
TOL_FUSION = 16.0        # m, distancia a la que una cresta de ladera se
                         # considera que llega a la divisoria y se funde
DESVIO_MAX = 8.0         # m, desplazamiento máximo en planta de la divisoria
EPS_Z = 0.03             # m, por debajo de esto una fusión ya está resuelta
EPS_XY = 0.05            # m, ídem para el desvío en planta
MEZCLA_FUSION = 35.0     # m, longitud sobre la que se reparte el desvío


def _estaciones(pts):
    s = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        s.append(s[-1] + _dist(a, b))
    return s


def _peso(pts):
    """Orden de una cresta: se usa su longitud como aproximación (una cresta
    larga separa cuencas mayores que una corta de ladera). Es el mismo criterio
    que ordena una red de drenaje: manda la de mayor cuenca."""
    return max(_estaciones(pts)[-1], 1e-6)


def fundir_con_divisorias(lm, log=None, tol=TOL_FUSION):
    """Funde las crestas de ladera que llegan a una divisoria de cuenca.

    Cuando una cresta nacida de un meandro alcanza la cresta que delimita la
    cuenca no se cruzan ni se superponen: se **funden en una sola** y la
    divisoria sigue a partir de ahí una dirección resultante. Dos consecuencias
    que hay que respetar, y que son la razón de que no baste con mover la
    cresta pequeña:

    1. **La cota del encuentro la impone la cresta de ladera.** Su z está
       determinada por sus propios parámetros (longitud de ladera, pendiente
       máxima, porción convexa): no es libre. Y un collado no puede quedar por
       debajo de ninguna de las dos crestas que lo forman, porque entonces el
       agua cruzaría la divisoria. Así que en la unión la divisoria toma la
       cota MAYOR de las dos y su perfil se rehace pasando por esos puntos,
       monótono entre ellos: es la divisoria la que se mueve en Z.

    2. **En planta manda la de mayor orden.** La divisoria se desvía hacia el
       punto de llegada solo la fracción peso_ladera/(peso_ladera+peso_divisoria)
       del desvío necesario, repartida a lo largo de MEZCLA_FUSION metros para
       que no haga quiebro y con los extremos (confluencia y límite) fijos.
    """
    log = log or (lambda *_a: None)
    capa_div = lm.obtener_capa("GRD_Ridges", crear=False)
    capa_sr = lm.obtener_capa("GRD_SubRidges", crear=False)
    if capa_div is None or capa_sr is None or capa_div.featureCount() == 0:
        return 0
    idx, divisorias = _indice(capa_div)
    divisorias = {k: v for k, v in divisorias.items() if len(v) >= 3}
    if not divisorias:
        return 0

    encuentros = {}
    ajustes_sub = {}
    for f in capa_sr.getFeatures():
        pts = _pts3(f)
        if len(pts) < 2:
            continue
        alto, en_inicio, mejor = _extremo_hacia_divisoria(pts, idx, divisorias)
        if mejor is None or mejor[0] > tol:
            continue
        _, fid, sobre = mejor
        div = divisorias[fid]
        s_div = _estaciones(div)
        k = min(range(len(div)), key=lambda i: _dist(div[i], sobre))
        # Manda la DIVISORIA: la ladera cuelga de ella. Era
        # `max(alto[2], sobre[2])`, y ese `max` es el eslabón que cerraba el
        # bucle — la cabecera se quedaba con la cota de la divisoria cuando
        # esta era más alta, y `divides` la leía después como si fuera un dato
        # independiente para volver a derivar la divisoria de ella.
        z_req = sobre[2]
        # --- IDEMPOTENCIA ---
        # Una fusión ya resuelta no debe volver a "aplicarse": si no, fusión y
        # sellado se realimentan (la fusión levanta la divisoria, el sellado
        # iguala la ladera, la fusión vuelve a detectar el encuentro…) y el
        # bucle de convergencia no termina nunca. Solo cuenta como cambio si
        # queda algo REAL que corregir, por encima de la tolerancia numérica.
        peso_l = _peso(pts)
        sep = _dist((alto[0], alto[1], 0), (sobre[0], sobre[1], 0))
        w = peso_l / (peso_l + _peso(div))
        desvio_previsto = min(sep * w, DESVIO_MAX)
        # La divisoria ya no se mueve en cota, así que lo único que puede
        # quedar por corregir es el desvío en planta o la cota de la ladera.
        if desvio_previsto <= EPS_XY and abs(z_req - alto[2]) <= EPS_Z:
            continue
        encuentros.setdefault(fid, []).append(
            (s_div[k], z_req, (alto[0], alto[1]), peso_l))
        # La corrección de cota se REPARTE, no se pega. Hasta la v1.0.19 esto
        # era `pts[:-1] + [(sobre[0], sobre[1], z_req)]`, con dos fallos a la
        # vez: movía SIEMPRE el último vértice —aunque la cabecera fuese el
        # primero, que es lo que pasa en cuanto `divides` parte o invierte la
        # línea— y le clavaba la cota nueva sin mezclar nada. Con `sobre` hasta
        # a `TOL_FUSION` = 16 m en planta, eso deja una línea entera plana y un
        # salto de veinte metros en el último segmento: es la firma que se
        # midió en el Ej_2 (peor caso, 1017 %). Regla de oro nº 5. Ver B-033.
        movido = _sellar_extremo(pts, z_req, en_inicio=en_inicio)
        k_ext = 0 if en_inicio else len(movido) - 1
        # el extremo se lleva además a la traza de la divisoria, en planta
        movido[k_ext] = (sobre[0], sobre[1], z_req)
        ajustes_sub[f.id()] = movido

    if not encuentros:
        return 0

    n_fus = 0
    cambios_div = {}
    for fid, lista in encuentros.items():
        div = divisorias[fid]
        s = _estaciones(div)
        peso_div = _peso(div)
        lista.sort(key=lambda t_: t_[0])
        xs = [p[0] for p in div]
        ys = [p[1] for p in div]
        zs = [p[2] for p in div]
        # --- planta: desvío ponderado por el orden de cada cresta ---
        for est, _zr, pt, peso in lista:
            k = min(range(len(s)), key=lambda i: abs(s[i] - est))
            dx, dy = pt[0] - xs[k], pt[1] - ys[k]
            sep = math.hypot(dx, dy)
            if sep < 1e-6:
                continue
            w = peso / (peso + peso_div)
            desvio = min(sep * w, DESVIO_MAX)
            ux, uy = dx / sep, dy / sep
            for i in range(len(s)):
                d = abs(s[i] - est)
                if d > MEZCLA_FUSION:
                    continue
                g = 1.0 - d / MEZCLA_FUSION
                g = g * g * (3 - 2 * g)
                borde = min(s[i], s[-1] - s[i]) / max(MEZCLA_FUSION, 1e-6)
                g *= max(0.0, min(1.0, borde))
                xs[i] += ux * desvio * g
                ys[i] += uy * desvio * g
            n_fus += 1
        # --- la COTA de la divisoria no se toca ---
        # Aquí había un `nuevos_z.append(max(z_lin, z0))`: un trinquete que
        # solo permitía SUBIR la divisoria, repetido en cada una de las hasta
        # 30 pasadas de `revisar`. Junto con el `z_req = max(...)` de arriba y
        # con `divides.py`, cerraba el bucle en el que la divisoria acababa
        # preguntándose su propia cota anterior. La divisoria tiene su curva
        # (`ridges._perfil_cresta`) y es la ladera la que se ajusta a ella.
        cambios_div[fid] = list(zip(xs, ys, zs))

    if cambios_div:
        capa_div.startEditing()
        for fid, pts in cambios_div.items():
            capa_div.changeGeometry(fid, QgsGeometry.fromPolyline(
                [QgsPoint(x, y, z) for x, y, z in pts]))
        capa_div.commitChanges()
        capa_div.triggerRepaint()
    if ajustes_sub:
        capa_sr.startEditing()
        for fid, pts in ajustes_sub.items():
            capa_sr.changeGeometry(fid, QgsGeometry.fromPolyline(
                [QgsPoint(x, y, z) for x, y, z in pts]))
        capa_sr.commitChanges()
        capa_sr.triggerRepaint()
    log(f"   · {n_fus} cresta(s) de ladera fundida(s) con la divisoria: la "
        "ladera se ha llevado a la cota de la divisoria y la divisoria se ha "
        "desviado en planta según el orden de cada una")
    return n_fus


MAX_PASADAS = 30         # tope de seguridad del bucle de convergencia. Un
                         # diseño normal converge en 2-3 pasadas; el margen
                         # está para redes muy ramificadas, donde cada orden
                         # de cresta necesita al menos una pasada para nacer y
                         # otra para fundirse aguas arriba.


def _una_pasada(lm, glob, log=None):
    """Una aplicación de las cuatro reglas. Devuelve el recuento de cambios."""
    n_emp = empalmar_en_divisorias(lm, log=log)
    n_fus = fundir_con_divisorias(lm, log=log)
    n_cr, n_vg = crestas_de_encuentro(lm, glob, log=log)
    n_sel = sellar_contra_divisorias(lm, log=log)
    return {"empalmadas": n_emp, "fusiones": n_fus, "crestas_nuevas": n_cr,
            "valles_nuevos": n_vg, "selladas": n_sel}


def revisar(lm, glob, log=None, max_pasadas=MAX_PASADAS):
    """Pase topológico ITERADO hasta que el relieve deja de cambiar.

    Las cuatro reglas se aplican en el orden en que se construye el relieve:

    1. las crestas de ladera mueren sobre la divisoria de cuenca;
    2. divisoria y cresta de ladera se FUNDEN donde se encuentran (la divisoria
       se levanta a la cota del collado y se desvía en planta según el orden de
       cada una);
    3. del encuentro de dos crestas de ladera nace una de ORDEN SUPERIOR, y
       entre dos de ellas un valle nuevo;
    4. sellado: ningún extremo de ladera desajustado respecto a la divisoria.

    Pero la regla 3 CREA crestas nuevas, y esas crestas nuevas pueden a su vez
    encontrarse con otras aguas arriba y generar un tercer orden, y así
    sucesivamente: es exactamente la jerarquía de una red de drenaje. Por eso
    una sola pasada solo resuelve el primer nivel. Aquí se repite el ciclo
    hasta que una pasada completa no produce ningún cambio — el punto fijo del
    proceso — con un tope de seguridad por si una configuración patológica
    hiciera oscilar el resultado.

    El coste no se dispara con el tamaño de la red: las búsquedas van por
    índice espacial, así que cada extremo solo se compara con las divisorias
    que tiene cerca, y el número de pasadas depende de la PROFUNDIDAD de la
    jerarquía (cuántos órdenes de cresta hay), no del número de cauces. Una red
    de cientos de tributarios converge en las mismas pocas pasadas que una de
    dos, porque todos los órdenes de un mismo nivel se resuelven a la vez.
    """
    log = log or (lambda *_a: None)
    total = {"empalmadas": 0, "fusiones": 0, "crestas_nuevas": 0,
             "valles_nuevos": 0, "selladas": 0, "pasadas": 0}
    for k in range(1, max(1, int(max_pasadas)) + 1):
        if k > 1:
            log(f"   · pasada topológica {k} (hay crestas nuevas que pueden "
                "volver a fundirse aguas arriba)")
        r = _una_pasada(lm, glob, log=log if k == 1 else None)
        total["pasadas"] = k
        for clave in ("empalmadas", "fusiones", "crestas_nuevas",
                      "valles_nuevos", "selladas"):
            total[clave] += r[clave]
        if sum(r.values()) == 0:
            break
    else:
        log(f"   · AVISO: la topología no se ha estabilizado en {max_pasadas} "
            "pasadas; se conserva el último estado. Revisa si hay crestas "
            "solapadas en alguna confluencia.")
    if total["pasadas"] > 1:
        log(f"   · topología estabilizada en {total['pasadas']} pasada(s): "
            f"{total['empalmadas']} empalmes, {total['fusiones']} fusiones, "
            f"{total['crestas_nuevas']} crestas de orden superior, "
            f"{total['valles_nuevos']} valles nuevos")
    return total
