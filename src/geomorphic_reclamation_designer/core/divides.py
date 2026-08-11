# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Divisorias de cuenca: recorte contra el cauce y cota DERIVADA de las laderas.

Dos ideas, y las dos salen de medir la salida del GeoFluv original.

**1. Ninguna línea de terreno entra en el corredor del cauce.**
En el original las crestas y vaguadas de ladera mueren sobre la línea de orilla
flood-prone (a 0.33 m de media), y las divisorias de cuenca se paran todavía
antes: a 7.1 y 6.9 m del eje, unos 4.5 m por fuera del borde flood-prone, unos
2.3 m por encima del lecho. Dentro del corredor el terreno ya lo definen las
siete líneas 3D del propio cauce; meter ahí más líneas de rotura, con cotas
parecidas pero no iguales, es lo que produce triángulos volteados, curvas
cerradas diminutas y las formas raras junto a la confluencia.

**2. La cota de una divisoria no es un dato: es una consecuencia.**
La cota de la cresta que separa dos cuencas la fijan las laderas que suben
hasta ella por los dos lados, y esas sí tienen su cota determinada —por el
perfil del cauce y por los parámetros de ladera—. Diseñar la divisoria con un
perfil propio y después forzar las laderas a encajar en él (o al revés) es un
tira y afloja que deja escalones de metros y crestas que suben y se hunden
antes de morir.

Así que el orden correcto es: la divisoria en PLANTA primero, después las
laderas con su física, y la cota de la divisoria como ENVOLVENTE de lo que las
laderas le piden.
"""

import bisect
import math

from qgis.core import QgsGeometry, QgsPointXY, QgsPoint, QgsSpatialIndex, QgsFeature

from .compat import attrs, indices_datos
from .ridges import convexo_cresta, convexo_subcresta


TOL_LLEGADA = 20.0     # m, distancia a la que la cabecera de una ladera se
                       # considera que llega a la divisoria. Tiene que ser
                       # MAYOR que topology.TOL_EMPALME (18 m): si no, hay
                       # espolones que el pase topológico prolonga hasta la
                       # divisoria y que aquí no se reajustan, y se quedan con
                       # la cola vertical que aquel les pegó.
MARGEN_LIMITE = 3.0    # m, una cabecera que muere en el límite GeoFluv no
                       # aporta cota a la divisoria
SUAVIZADO = 2          # pasadas del suavizado entre puntos de control
MEZCLA_CABECERA = 25.0 # m sobre los que se reparte el ajuste de una cabecera
MEZCLA_LIMITE = 45.0   # m para el empalme con el terreno en el límite: la
                       # corrección ahí puede ser de veinte metros y hay que
                       # repartirla por buena parte de la ladera


# ------------------------------------------------------------ utilidades
def _estaciones(pts):
    s = [0.0]
    for a, b in zip(pts[:-1], pts[1:]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return s


def _pts3(f):
    return [(v.x(), v.y(), v.z()) for v in f.geometry().vertices()]


def _mezcla_sin_meseta(dz, L, grad, m0):
    """Longitud de mezcla mínima para que el recorte de monotonía no aplaste la
    línea en una MESETA.

    Si la corrección se reparte solo sobre `mezcla` metros, los vértices que
    quedan fuera conservan su cota vieja; cuando esa cota contradice el nuevo
    extremo, el recorte de monotonía los arrastra a todos a la misma cota y sale
    una meseta seguida de una rampa. Medido en el Ej_2 (Rom_Pla): la subcresta
    fid 65 subía 284.8 → 303.2 m en siete vértices y después se quedaba **48 m
    completamente planos** a 303.2. Diez de sus 218 líneas de relieve tenían esa
    firma, con mesetas de hasta 27 vértices; el original no pasa de 2.

    La cura NO es quitar la monotonía —eso deja dientes, y ya se probó y se
    revirtió (B-018)— sino repartir la corrección sobre longitud suficiente.

    CUÁNTA. La corrección vale `dz·w(d)` con `w` el smoothstep `3u²−2u³`, cuya
    pendiente máxima es `1.5/m`. Para que no invierta el sentido de la línea
    hace falta que no supere el gradiente propio de la línea:

        |dz| · 1.5/m  ≤  grad      ⇒      m ≥ 1.5 · |dz| / grad

    Es una cota, no un valor exacto: si el gradiente no es uniforme puede
    quedarse corta, y por eso `ajustar_extremo` comprueba el resultado y
    alarga otra vez si hace falta.
    """
    if abs(dz) < 1e-9 or grad < 1e-6:
        return m0
    return min(L, max(m0, 1.5 * abs(dz) / grad))


def _mezclar(pts, s, L, k, dz, m, en_inicio):
    """Reparte `dz` sobre los `m` metros contiguos al vértice `k`."""
    salida = []
    for (x, y, z), si in zip(pts, s):
        dist = si if en_inicio else (L - si)
        w = max(0.0, 1.0 - dist / m)
        w = w * w * (3 - 2 * w)
        salida.append((x, y, z + dz * w))
    salida[k] = (pts[k][0], pts[k][1], pts[k][2] + dz)
    return salida


def _rompe_monotonia(salida, sube):
    """Cuánta cota habría que recortar para dejar la línea monótona."""
    peor = 0.0
    if sube:
        for i in range(len(salida) - 2, -1, -1):
            peor = max(peor, salida[i][2] - salida[i + 1][2])
    else:
        for i in range(1, len(salida)):
            peor = max(peor, salida[i][2] - salida[i - 1][2])
    return peor


def ajustar_extremo(pts, z_obj, en_inicio=False, mezcla=20.0, monotona=True):
    """Lleva un extremo de la línea a la cota `z_obj` repartiendo la corrección
    hacia el interior con smoothstep.

    `monotona=True` (por defecto) recorta además lo que contradiga el sentido
    de la línea, que es lo que se quiere cuando una subcresta sube del canal a
    la divisoria: ahí un diente no es relieve, es un defecto. La monotonía se
    mide en el sentido REAL de la línea, no suponiendo que sube hacia el final.

    `monotona=False` cuando la línea NO tiene por qué ser monótona: una ladera
    que arranca en el canal, sube a un filo y baja al límite GeoFluv tiene un
    máximo interior legítimo. Forzarla a monótona la aplasta contra el extremo
    más bajo y desaparece el relieve — medido en el caso real: las subcrestas
    del oeste quedaban con un 0.7 % de pendiente media frente al 10-14 % de las
    del GeoFluv original, que caen del filo (1072 m) al perímetro (1062 m).
    """
    if len(pts) < 2:
        return list(pts)
    s = _estaciones(pts)
    L = s[-1]
    if L <= 1e-6:
        return list(pts)
    k = 0 if en_inicio else len(pts) - 1
    dz = z_obj - pts[k][2]
    m = max(1e-6, min(mezcla, L))
    if not monotona:
        return _mezclar(pts, s, L, k, dz, m, en_inicio)

    # La mezcla se ALARGA lo que haga falta para que el recorte de monotonía
    # de más abajo no tenga nada que recortar y no deje una meseta. La cota de
    # `_mezcla_sin_meseta` supone gradiente uniforme, así que se comprueba el
    # resultado y se alarga otra vez si se ha quedado corta. Converge en dos o
    # tres vueltas; el tope está solo para que una línea patológica no gire
    # indefinidamente.
    sube = pts[-1][2] >= pts[0][2]
    grad = abs(pts[-1][2] - pts[0][2]) / L
    m = _mezcla_sin_meseta(dz, L, grad, m)
    salida = _mezclar(pts, s, L, k, dz, m, en_inicio)
    for _ in range(4):
        exceso = _rompe_monotonia(salida, sube)
        if exceso < 1e-6 or m >= L - 1e-9:
            break
        m = min(L, m * 1.8)
        salida = _mezclar(pts, s, L, k, dz, m, en_inicio)

    sube = salida[-1][2] >= salida[0][2]
    if sube:
        for i in range(len(salida) - 2, -1, -1):
            if salida[i][2] > salida[i + 1][2]:
                salida[i] = (salida[i][0], salida[i][1], salida[i + 1][2])
    else:
        for i in range(1, len(salida)):
            if salida[i][2] > salida[i - 1][2]:
                salida[i] = (salida[i][0], salida[i][1], salida[i - 1][2])
    salida[k] = (pts[k][0], pts[k][1], z_obj)
    return salida


def perfil_base(pts, z_alto, z_bajo, lc, lf=None, desde_inicio=False):
    """Cotas de la línea siguiendo la ECUACIÓN del método, no un recorte.

    El manual de Natural Regrade lo dice literalmente para cualquier perfil
    longitudinal, también el de una cresta: *«GeoFluv designs a longitudinal
    profile between the upper and lower elevations of the 3D polyline by
    constructing a vertical curve using the specified bottom and top slope
    percents»*, con la opción de mantener convexo el arranque una longitud
    dada antes de aplicar la curva.

    Eso es exactamente `perfil_trapezoidal`: cabeza convexa de longitud `lc`
    (la xc de Horton, el 'Maximum convex portion' medido en el área de
    referencia), tramo central recto y pie cóncavo. Reconstruir el perfil con
    la ecuación es lo correcto; limitar la pendiente segmento a segmento —que
    es lo que hacía la versión anterior— es un apaño que deja la forma a medio
    camino entre la de diseño y la que había.
    """
    from .ridges import perfil_trapezoidal
    s = _estaciones(pts)
    L = s[-1]
    if L <= 1e-6:
        return [z_alto] * len(pts)
    dz = z_alto - z_bajo
    zs = []
    for si in s:
        # distancia DESDE el extremo alto
        x = si if desde_inicio else (L - si)
        zs.append(z_alto - perfil_trapezoidal(x, L, dz, lc, lf))
    zs[0 if desde_inicio else -1] = z_alto
    zs[-1 if desde_inicio else 0] = z_bajo
    return zs


def _limpiar_vertices(pts, tol=0.30):
    """Quita vértices pegados al anterior. Un segmento de 20 cm con medio metro
    de desnivel da una pendiente absurda que después contamina cualquier
    control de pendiente; y además son los vértices duplicados que Check Design
    reporta."""
    if len(pts) < 3:
        return list(pts)
    salida = [pts[0]]
    for p in pts[1:-1]:
        if math.hypot(p[0] - salida[-1][0], p[1] - salida[-1][1]) >= tol:
            salida.append(p)
    salida.append(pts[-1])
    if math.hypot(salida[-1][0] - salida[-2][0],
                  salida[-1][1] - salida[-2][1]) < tol and len(salida) > 2:
        del salida[-2]
    return salida


TOL_TRAZA_CRESTA = 0.5     # m que se le permite recortar a una curva cerrada al
                           # remuestrear. Un orden de magnitud por debajo de la
                           # holgura con que la divisoria se para del cauce.


def remuestrear(pts, paso, tol=TOL_TRAZA_CRESTA):
    """Vértices a un paso uniforme sobre la MISMA traza, con los dos extremos.

    'm_fMaxDistOnRidges' del original, que en el Ej_2 vale 6.1 m. No es solo
    una densificación: el espaciado medido en su salida da p50 = 6.1, p90 =
    12.2, p99 = 24.4 y máx = 30.5, todos múltiplos exactos de 6.1, o sea que
    sus vértices están sobre una retícula de ese paso. Los nuestros iban de 0.7
    a 9.5 m dentro de una misma línea.

    Los puntos se toman SOBRE la polilínea, así que la traza no se desplaza; lo
    único que cambia es que entre muestra y muestra se sustituye el arco por su
    cuerda. En las divisorias del Ej_2 eso son 2.5 cm de mediana, pero en una
    curva cerrada llegaba a 1.8 m, y el ajuste dice distancia MÁXIMA entre
    vértices, no licencia para comerse la forma: los vértices originales que se
    desviarían más de `tol` se conservan."""
    if paso <= 0 or len(pts) < 3:
        return list(pts)
    s = _estaciones([(p[0], p[1]) for p in pts])
    L = s[-1]
    if paso >= L:
        return list(pts)

    def _en(si):
        i = bisect.bisect_left(s, si)
        if i <= 0:
            return 0.0, tuple(pts[0])
        if i >= len(s):
            return L, tuple(pts[-1])
        t = (si - s[i - 1]) / max(s[i] - s[i - 1], 1e-9)
        return si, tuple(a + t * (b - a) for a, b in zip(pts[i - 1], pts[i]))

    # es una distancia MAXIMA, así que se sube al entero siguiente: repartir en
    # partes iguales deja el paso entre `paso`/2 y `paso`, nunca por encima, y
    # sin el muñón que dejaría caminar a paso fijo desde un extremo
    n = max(2, int(math.ceil(L / paso - 1e-9)))
    muestras = dict(_en(L * k / n) for k in range(n + 1))
    if tol > 0:
        marcas = sorted(muestras)
        for si, p in zip(s, pts):
            j = bisect.bisect_left(marcas, si)
            a = marcas[max(0, j - 1)]
            b = marcas[min(j, len(marcas) - 1)]
            if _dist_a_segmento(p, muestras[a], muestras[b]) > tol:
                muestras[si] = tuple(p)
    return [muestras[k] for k in sorted(muestras)]


def _dist_a_segmento(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    den = dx * dx + dy * dy
    t = 0.0 if den < 1e-12 else max(0.0, min(1.0, ((p[0] - a[0]) * dx
                                                   + (p[1] - a[1]) * dy) / den))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def extremo_alto(pts, dist=None):
    """Índice del extremo ALTO —la cabecera— de una línea de ladera: 0 o −1.

    El criterio es la **distancia al cauce**, no la cota: la cabecera es el
    extremo LEJANO. Por cota falla donde el cauce va sobre relleno, porque
    entonces la ladera BAJA de él y el extremo más alto resulta ser el pie
    (B-018, B-027, ADR-010).

    `dist` es un invocable `(x, y) → distancia al cauce`; cada módulo inyecta el
    suyo (`Corredor._cerca`, los ejes de `GRD_Channels`, los diseños) sin crear
    dependencias nuevas. Sin él se cae a la cota, que es un **respaldo**, no un
    criterio: en cuanto se toca la cota de las divisorias, decidir por cota hace
    que estas funciones elijan el otro extremo y el síntoma es inexplicable.
    Ver P-19."""
    if len(pts) < 2:
        return 0
    if dist is not None:
        d0 = dist(pts[0][0], pts[0][1])
        d1 = dist(pts[-1][0], pts[-1][1])
        if d0 is not None and d1 is not None and abs(d0 - d1) > 1e-9:
            return 0 if d0 > d1 else len(pts) - 1
    return 0 if pts[0][2] > pts[-1][2] else len(pts) - 1


def _proyectar(pts, x, y):
    """(distancia, estación, z interpolada) del punto más próximo de la
    polilínea. La estación es la que hace falta para colocar el punto de
    control sobre el perfil de la divisoria."""
    mejor = (float("inf"), 0.0, None)
    acum = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy
        L = math.sqrt(L2)
        if L2 <= 1e-12:
            continue
        t = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / L2))
        px, py = a[0] + t * dx, a[1] + t * dy
        d2 = (px - x) ** 2 + (py - y) ** 2
        if d2 < mejor[0]:
            za = a[2] if len(a) > 2 else None
            zb = b[2] if len(b) > 2 else None
            z = None if za is None or zb is None else za + t * (zb - za)
            mejor = (d2, acum + t * L, z)
        acum += L
    return math.sqrt(mejor[0]), mejor[1], mejor[2]


# ============================================== 1. CORREDOR DEL CAUCE
class Corredor:
    """Franja alrededor de cada cauce en la que no entra ninguna otra línea.

    El radio en cada punto es la semianchura flood-prone de la sección más una
    holgura. Se resuelve punto a punto en vez de con un buffer porque la
    anchura varía a lo largo del canal y porque así vale igual con dos canales
    que con quinientos: cada consulta es una búsqueda sobre el índice espacial
    de los ejes."""

    def __init__(self, disenos, holgura=0.0):
        self.holgura = float(holgura)
        self.ejes = []          # [(nombre, QgsGeometry, L_geom, L_valle, secs)]
        self.idx = QgsSpatialIndex()
        iterable = disenos.values() if isinstance(disenos, dict) else disenos
        for i, d in enumerate(iterable):
            pts = getattr(d, "puntos", None)
            if not pts or len(pts) < 2:
                continue
            g = QgsGeometry.fromPolylineXY(
                [QgsPointXY(p[0], p[1]) for p in pts])
            secs = [(e["estacion"], e.get("ancho_flood", 0.0),
                     e.get("cota", 0.0), e.get("prof_flood", 0.0))
                    for e in (getattr(d, "secciones", []) or [])]
            secs.sort()
            self.ejes.append((d.nombre, g, g.length(),
                              getattr(d, "L_valle", g.length()) or g.length(),
                              secs))
            f = QgsFeature(len(self.ejes) - 1)
            f.setGeometry(g)
            self.idx.addFeature(f)

    @staticmethod
    def _interp(secs, s, campo):
        """Valor de un campo de la sección en la estación s (índice 1 =
        anchura flood-prone, 2 = cota del lecho, 3 = calado flood-prone)."""
        if not secs:
            return 0.0
        est = [e[0] for e in secs]
        i = bisect.bisect_left(est, s)
        if i <= 0:
            return secs[0][campo]
        if i >= len(secs):
            return secs[-1][campo]
        s0, s1 = secs[i - 1][0], secs[i][0]
        v0, v1 = secs[i - 1][campo], secs[i][campo]
        t = (s - s0) / max(s1 - s0, 1e-9)
        return v0 + t * (v1 - v0)

    def _cerca(self, x, y):
        """(índice del eje más próximo, distancia, estación de valle)."""
        if not self.ejes:
            return None, float("inf"), 0.0
        p = QgsPointXY(x, y)
        gp = QgsGeometry.fromPointXY(p)
        cand = self.idx.nearestNeighbor(p, min(4, len(self.ejes)))
        if not cand:
            cand = range(len(self.ejes))
        mejor = (None, float("inf"), 0.0)
        for k in cand:
            _, g, Lg, Lv, secs = self.ejes[k]
            d = g.distance(gp)
            if d < mejor[1]:
                s_geo = g.lineLocatePoint(gp)
                mejor = (k, d, s_geo * (Lv / Lg) if Lg > 0 else s_geo)
        return mejor

    def radio_y_distancia(self, x, y):
        """(radio del corredor ahí, distancia del punto al eje más próximo)."""
        k, d, s = self._cerca(x, y)
        if k is None:
            return 0.0, float("inf")
        return self._interp(self.ejes[k][4], s, 1) / 2.0 + self.holgura, d

    def dentro(self, x, y):
        r, d = self.radio_y_distancia(x, y)
        return d < r

    def techo_cresta(self, x, y, s_max, dem=None):
        """Cota MÁXIMA que puede tener una cresta en ese punto.

        Dos condiciones, y vale la más permisiva:

        * la geometría de ladera: desde el cauce más próximo, subir a la
          pendiente recta máxima de diseño da `z_lecho + s_max · d`. Una cresta
          por encima de eso exigiría una ladera más empinada que el ajuste
          `Maximum straight-line slopes`;
        * el terreno existente: si el suelo ya está más alto —un talud de
          corta, un cerro que no se toca— la cresta puede estar ahí sin que
          nadie tenga que excavar para conseguirlo.

        Sirve para dos cosas a la vez: fijar la cota del extremo truncado de
        una divisoria (a 6.6 m del cauce da 1062.8, y el original acaba en
        1062.97) y filtrar las cabeceras que piden una cota imposible, que es
        lo que pasa cuando un pase anterior le pegó a un espolón la cota de la
        propia divisoria y esta se la vuelve a preguntar a sí misma.
        """
        k, dist, s = self._cerca(x, y)
        if k is None:
            return None
        z = self._interp(self.ejes[k][4], s, 2) + s_max * dist
        if dem is not None:
            from . import setup_tools as st
            zt = st.cota_dem(dem, x, y)
            if zt is not None:
                z = max(z, zt)
        return z

    def cota_borde(self, x, y):
        """Cota del BORDE del corredor en el punto: lecho del cauce más el
        calado flood-prone, que es la coronación de la orilla exterior.

        Es la cota a la que tiene que llegar el pie de una ladera. Dejarla en
        la cota del lecho —que es lo que salía al recortar sin más— pone la
        línea de ladera medio metro por debajo de la línea de orilla que pasa
        por ese mismo sitio, y eso es un cruce de líneas de rotura a distinta
        cota, justo lo que se quiere evitar."""
        k, _, s = self._cerca(x, y)
        if k is None:
            return None
        secs = self.ejes[k][4]
        if not secs:
            return None
        return self._interp(secs, s, 2) + self._interp(secs, s, 3)


PASO_SONDEO = 1.5      # m, resolución con la que se busca el borde del corredor


def _lerp(a, b, t):
    return tuple(a[k] + (b[k] - a[k]) * t for k in range(len(a)))


def _bisecar(a, b, t0, t1, corredor, iters=14):
    """t del borde del corredor entre t0 (un estado) y t1 (el otro). El radio
    del corredor varía a lo largo del eje, así que no hay fórmula: se busca."""
    dentro0 = corredor.dentro(*_lerp(a, b, t0)[:2])
    lo, hi = t0, t1
    for _ in range(iters):
        m = (lo + hi) / 2.0
        if corredor.dentro(*_lerp(a, b, m)[:2]) == dentro0:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2.0


def _subtramos(a, b, corredor, paso=PASO_SONDEO):
    """[(t0, t1, dentro)] del segmento a→b, partido donde cruza el borde.

    Se sondea a intervalos de `paso` en vez de mirar solo los extremos: un
    segmento largo puede entrar y salir del corredor sin que ninguno de sus dos
    vértices esté dentro."""
    L = math.hypot(b[0] - a[0], b[1] - a[1])
    if L < 1e-9:
        return [(0.0, 1.0, corredor.dentro(a[0], a[1]))]
    n = max(1, int(math.ceil(L / paso)))
    ts = [i / n for i in range(n + 1)]
    marcas = [corredor.dentro(*_lerp(a, b, t)[:2]) for t in ts]
    tramos = []
    t_ini, estado = 0.0, marcas[0]
    for i in range(1, len(ts)):
        if marcas[i] != estado:
            tc = _bisecar(a, b, ts[i - 1], ts[i], corredor)
            tramos.append((t_ini, tc, estado))
            t_ini, estado = tc, marcas[i]
    tramos.append((t_ini, 1.0, estado))
    return tramos


def recortar_contra_corredor(pts, corredor, long_min=0.0, paso=PASO_SONDEO):
    """Trozos de la línea que quedan FUERA del corredor, con el corte exacto.

    Es una diferencia geométrica, no un mordisco en los extremos. Cubre todos
    los casos, que era la condición: la línea entra por un extremo, entra y
    sale por el medio (y entonces se parte en dos), roza el corredor sin que
    ningún vértice quede dentro, cruza varios cauces, o está entera dentro (y
    entonces desaparece).

    Devuelve (trozos, metros_quitados). Los trozos más cortos que `long_min` se
    descartan: un muñón de cuatro metros junto a la confluencia no es una
    divisoria, es basura que además vuelve a ensuciar la triangulación.
    """
    if len(pts) < 2:
        return [], 0.0
    L_ini = _estaciones(pts)[-1]
    piezas, actual = [], []
    for a, b in zip(pts[:-1], pts[1:]):
        for t0, t1, dentro in _subtramos(a, b, corredor, paso):
            if dentro:
                if len(actual) >= 2:
                    piezas.append(actual)
                actual = []
                continue
            p0, p1 = _lerp(a, b, t0), _lerp(a, b, t1)
            if not actual:
                actual.append(p0)
            if math.hypot(p1[0] - actual[-1][0], p1[1] - actual[-1][1]) > 1e-9:
                actual.append(p1)
    if len(actual) >= 2:
        piezas.append(actual)
    piezas = [p for p in piezas if _estaciones(p)[-1] >= long_min]
    quitado = L_ini - sum(_estaciones(p)[-1] for p in piezas)
    return piezas, max(quitado, 0.0)


# ================================ 2. COTA DERIVADA DE LAS LADERAS
SEPARACION_CONTROL = 6.1   # m, por debajo de esto dos cabeceras son el MISMO
                           # punto de llegada. Es el paso de vértices de la
                           # divisoria: por debajo de él, no tiene con qué
                           # distinguirlas. Quien la llama pasa el suyo.


def puntos_de_control(dens, cabeceras, tol=TOL_LLEGADA,
                      separacion=SEPARACION_CONTROL):
    """[(estación, cota)] que las crestas de ladera imponen a la divisoria.

    Solo las SUBCRESTAS aportan cota: son las que suben hasta la divisoria. Una
    vaguada muere por debajo, entre dos subcrestas, así que no levanta la
    divisoria — luego se comprueba que no sobresalga de ella.

    Dos cabeceras separadas menos de `separacion` metros se funden en una, y se
    queda la más alta. La divisoria no tiene resolución para distinguirlas: sus
    vértices están a 2-3 m, así que ambas caen sobre el mismo o sobre vértices
    contiguos, y obligar al perfil a pasar por las dos escribe un escalón donde
    debería haber una pendiente. Antes ni siquiera era determinista: las dos
    aterrizaban en el mismo índice y `_restaurar_control` dejaba la que llegara
    la última. La que se descarta no se pierde —el pase de encaje vuelve a
    pegar su cabecera a la cota que la divisoria tenga al final—; es justo la
    tolerancia que el original se permite."""
    ctrl = {}
    for (x, y, z) in cabeceras:
        d, s, _ = _proyectar(dens, x, y)
        if d > tol:
            continue
        k = round(s, 2)
        if k not in ctrl or z > ctrl[k]:
            ctrl[k] = z
    fundidos, s0 = [], None
    for s, z in sorted(ctrl.items()):
        # la ventana se mide contra el ARRANQUE del grupo, no contra el último
        # que entró: si no, una hilera de cabeceras separadas 4.9 m se iría
        # encadenando y acabaría fundiendo cincuenta metros de divisoria en un
        # solo punto de control
        if fundidos and s - s0 < separacion:
            if z > fundidos[-1][1]:
                fundidos[-1] = (s, z)
        else:
            fundidos.append((s, z))
            s0 = s
    return fundidos


DECAIMIENTO = 40.0     # m sobre los que se apaga la corrección de un espolón
MAX_PENDIENTE_FILO = 1.00   # 100 %: cortafuegos contra picos en el filo de una
                            # divisoria, no un objetivo de diseño


def perfil_desde_control(dens, base, control, s_max, z_top=None, z_bot=None,
                         monotona=True):
    """Perfil longitudinal de la divisoria: el perfil de diseño CORREGIDO para
    que pase exactamente por las cabeceras de las laderas que llegan a ella.

    No se interpola de cabecera a cabecera. Una divisoria puede recibir dos
    espolones en 180 m —es lo que pasa en un caso real, y en el original ni
    siquiera eso— y unir esos dos puntos con una recta daría un filo inventado
    que en el extremo truncado se queda trece metros por encima de donde debe.

    Lo que se hace es trabajar con RESIDUOS:

    * `base` es el perfil de diseño de la divisoria (cota del canal más la
      altura de ladera que le corresponde). Es físicamente correcto en todas
      partes; lo único que no sabe es dónde muere cada espolón.
    * en cada cabecera se mide el residuo r = z_cabecera − base(s).
    * ese residuo se interpola entre cabeceras y se apaga linealmente en
      `DECAIMIENTO` metros más allá de la primera y de la última.
    * el perfil final es `base + r(s)`.

    Así el espolón cae EXACTAMENTE sobre la divisoria (residuo aplicado
    íntegro en su estación) y, lejos de él, la divisoria conserva su perfil de
    diseño. Los extremos se anclan solo si se conoce su cota (empalme con el
    DEM en el límite GeoFluv).
    """
    s = _estaciones(dens)
    if not s or len(s) != len(base):
        return None
    L = s[-1]
    if not control:
        return None

    ns = [c[0] for c in control]
    def _base_en(si):
        i = bisect.bisect_left(s, si)
        if i <= 0:
            return base[0]
        if i >= len(s):
            return base[-1]
        t = (si - s[i - 1]) / max(s[i] - s[i - 1], 1e-9)
        return base[i - 1] + t * (base[i] - base[i - 1])

    nodos = [(sc, zc - _base_en(sc)) for sc, zc in control]
    nodos.sort()
    # apagado a los lados: fuera del alcance de cualquier espolón la divisoria
    # es la de diseño
    nodos = ([(max(0.0, nodos[0][0] - DECAIMIENTO), 0.0)] + nodos
             + [(min(L, nodos[-1][0] + DECAIMIENTO), 0.0)])
    rs = [n[0] for n in nodos]
    rv = [n[1] for n in nodos]

    zs = []
    for si, zb in zip(s, base):
        if si <= rs[0] or si >= rs[-1]:
            r = 0.0
        else:
            i = max(0, min(bisect.bisect_right(rs, si) - 1, len(rs) - 2))
            t = (si - rs[i]) / max(rs[i + 1] - rs[i], 1e-9)
            # smoothstep, no lineal: es el 'blend' del Edit Longitudinal
            # Profile del original. Con interpolación lineal la corrección
            # entra y sale con un quiebro y el filo queda facetado.
            t = t * t * (3 - 2 * t)
            r = rv[i] + t * (rv[i + 1] - rv[i])
        zs.append(zb + r)

    if z_bot is not None and (not ns or ns[0] > 2.0):
        zs[0] = z_bot
    if z_top is not None and (not ns or ns[-1] < L - 2.0):
        zs[-1] = z_top

    fijos = _indices_fijos(s, ns)
    anclas = set()
    if z_bot is not None:
        anclas.add(0)
    if z_top is not None:
        anclas.add(len(zs) - 1)
    zs = _restaurar_control(zs, s, control)
    if monotona:
        zs = _monotonizar(zs, fijos | anclas)
    # OJO: aquí NO se aplica la pendiente máxima de ladera. Ese ajuste habla de
    # la pendiente recta de cresta a canal, no del perfil longitudinal del filo
    # de una divisoria, que baja lo que tenga que bajar: la del original
    # desciende 73 m en 178 (41 % de media, con tramos al 73 %). Limitarla al
    # 33 % dejaba la divisoria 17 m colgada sobre el cauce. El límite que se
    # aplica aquí es solo un cortafuegos contra picos imposibles.
    # El cortafuegos de pendiente NO respeta las estaciones de los espolones:
    # si dos cabeceras contiguas piden un salto imposible, hay que recortarlo.
    # El empalme no se pierde por eso, porque el paso siguiente vuelve a pegar
    # cada cabecera a la cota que la divisoria tenga finalmente.
    # OJO con el orden: el suavizado va ANTES del cortafuegos. Al revés, junto
    # a un extremo anclado el promediado tira del vértice contiguo hacia la
    # cota del ancla y deja el segmento siguiente más empinado que antes —así
    # aparecía un 220 % justo bajo el límite GeoFluv—. El limitador tiene que
    # ser lo último que toca el perfil.
    zs = _suavizar_entre_control(zs, s, ns, SUAVIZADO)
    zs = _limitar_pendiente(zs, s, MAX_PENDIENTE_FILO, anclas)
    return zs


def _indices_fijos(s, s_control):
    """Estaciones intocables para el limitador de pendiente: SOLO donde muere
    un espolón. Los extremos se añaden aparte, y únicamente si están anclados a
    una cota conocida: fijarlos siempre obligaría al perfil a conservar la
    pendiente del extremo del perfil de diseño, por disparatada que fuese."""
    return {min(range(len(s)), key=lambda i: abs(s[i] - sc))
            for sc in s_control}


def _restaurar_control(zs, s, control):
    """Devuelve a su sitio las cotas de las estaciones de control, que la
    monotonía o el límite de pendiente hayan podido mover. Es la condición
    que hace que la subcresta muera sin escalón; si hay que sacrificar algo,
    se sacrifica el límite de pendiente, no el empalme."""
    salida = list(zs)
    for sc, zc in control:
        i = min(range(len(s)), key=lambda k: abs(s[k] - sc))
        salida[i] = zc
    return salida


def _monotonizar(zs, fijos=None):
    """Suprime los cambios de sentido ESPURIOS, tramo a tramo entre puntos fijos.

    El sentido NO se decide con los dos extremos de la divisoria entera. Una
    divisoria puede tener una loma legítima —sube desde una confluencia, corona
    y baja a otra—, y con un único sentido global el perfil se convierte en un
    trinquete: los puntos de control, que son intocables, quedan encaramados y
    todo lo que viene detrás se aplana contra ellos hasta que el extremo
    anclado obliga a soltar el desnivel de golpe. Ver B-036.

    Lo que sí es espurio es que el perfil se salga del intervalo que marcan los
    dos puntos fijos que lo encierran. Entre cabecera y cabecera se impone la
    monotonía en el sentido que ellas dos determinan, y nada más."""
    if len(zs) < 3:
        return list(zs)
    fijos = fijos or set()
    salida = list(zs)
    nodos = sorted({0, len(zs) - 1} | {i for i in fijos if 0 <= i < len(zs)})
    for a, b in zip(nodos, nodos[1:]):
        if b - a < 2:
            continue
        sube = salida[b] >= salida[a]
        lo, hi = min(salida[a], salida[b]), max(salida[a], salida[b])
        for i in range(a + 1, b):
            if i in fijos:
                continue
            z = min(max(salida[i], lo), hi)
            if (sube and z < salida[i - 1]) or (not sube and z > salida[i - 1]):
                z = salida[i - 1]
            salida[i] = z
    return salida


def _limitar_pendiente(zs, s, s_max, fijos=None, pasadas=6):
    """Ningún tramo por encima de la pendiente recta máxima de diseño.

    Se barre en los DOS sentidos. Con un solo barrido hacia delante, un tramo
    demasiado empinado al principio arrastra hacia abajo todo lo que viene
    después; barriendo también hacia atrás la corrección se reparte a los dos
    lados del tramo que la provoca. Los índices `fijos` —las estaciones donde
    muere un espolón y los extremos anclados— no se tocan: se ajusta el vecino.
    """
    if s_max <= 0 or len(zs) < 2:
        return list(zs)
    fijos = fijos or set()
    salida = list(zs)
    for _ in range(pasadas):
        cambio = False
        for i in range(1, len(salida)):
            ds = s[i] - s[i - 1]
            if ds <= 1e-6:
                continue
            lim = s_max * ds
            dz = salida[i] - salida[i - 1]
            if abs(dz) <= lim + 1e-9:
                continue
            objetivo = salida[i - 1] + (lim if dz > 0 else -lim)
            if i not in fijos:
                salida[i] = objetivo
                cambio = True
            elif (i - 1) not in fijos:
                salida[i - 1] = salida[i] - (lim if dz > 0 else -lim)
                cambio = True
        for i in range(len(salida) - 2, -1, -1):
            ds = s[i + 1] - s[i]
            if ds <= 1e-6:
                continue
            lim = s_max * ds
            dz = salida[i] - salida[i + 1]
            if abs(dz) <= lim + 1e-9:
                continue
            if i not in fijos:
                salida[i] = salida[i + 1] + (lim if dz > 0 else -lim)
                cambio = True
        if not cambio:
            break
    return salida


def _suavizar_entre_control(zs, s, s_control, pasadas=SUAVIZADO):
    """Redondea los quiebros SIN mover los puntos de control: las cabeceras de
    las laderas tienen que seguir cayendo exactamente sobre la divisoria."""
    if pasadas <= 0 or len(zs) < 5:
        return zs
    fijos = set()
    for sc in s_control:
        k = min(range(len(s)), key=lambda i: abs(s[i] - sc))
        fijos.add(k)
    fijos.add(0)
    fijos.add(len(zs) - 1)
    salida = list(zs)
    for _ in range(pasadas):
        nuevo = list(salida)
        for i in range(1, len(salida) - 1):
            if i in fijos:
                continue
            nuevo[i] = 0.25 * salida[i - 1] + 0.5 * salida[i] + 0.25 * salida[i + 1]
        salida = nuevo
    return salida


# ================================================== orquesta del pase
def ajustar_divisorias(lm, disenos, glob, dem=None, g_lim=None, log=None):
    """Pase completo, en el orden correcto.

    1. Recorta contra el corredor del cauce las crestas y vaguadas de ladera
       (holgura 0: mueren en el borde flood-prone) y las divisorias (holgura
       `holgura_divisoria_m`).
    2. Recalcula la cota de cada divisoria como envolvente de las cabeceras de
       subcresta que llegan a ella.
    3. Encaja las cabeceras: las subcrestas caen EXACTAMENTE sobre la nueva
       divisoria y las vaguadas quedan por debajo.

    Devuelve un dict con el recuento de cada cosa.
    """
    log = log or (lambda *_a: None)
    res = {"recortadas": 0, "recorte_m": 0.0, "borradas": 0, "partidas": 0,
           "divisorias": 0, "control": 0, "encajadas": 0,
           "vaguadas_bajadas": 0, "rehechas": 0, "cortadas_div": 0,
           "sillas": 0, "empalmes_limite": 0, "peor_escalon": 0.0}
    if not disenos:
        return res
    s_max = float(glob.pendiente_max_pct) / 100.0
    holgura = float(getattr(glob, "holgura_divisoria_m", 4.5))

    corr_ladera = Corredor(disenos, holgura=0.0)
    corr_div = Corredor(disenos, holgura=holgura)

    # ---------- 1. recorte contra el corredor ----------
    # Longitud mínima de un trozo superviviente. Una ladera puede ser corta, de
    # modo que su mínimo es pequeño; una divisoria de cuatro metros no es una
    # divisoria, es un muñón que vuelve a ensuciar la triangulación.
    min_ladera = 2.0
    min_divisoria = max(0.5 * float(getattr(glob, "max_dist_cresta_cabecera", 25.0)),
                        3.0 * holgura)
    for nombre, corr, pegar, long_min in (
            ("GRD_SubRidges", corr_ladera, True, min_ladera),
            ("GRD_Swales", corr_ladera, True, min_ladera),
            ("GRD_Ridges", corr_div, False, min_divisoria)):
        capa = lm.obtener_capa(nombre, crear=False)
        if capa is None:
            continue
        cambios, borrar, extra = {}, [], []
        idx_datos = None
        for f in capa.getFeatures():
            pts = _pts3(f)
            if len(pts) < 2:
                continue
            piezas, quitado = recortar_contra_corredor(pts, corr, long_min)
            if quitado <= 1e-6 and len(piezas) == 1:
                continue
            if not piezas:
                borrar.append(f.id())
                res["recorte_m"] += quitado
                continue
            if pegar and len(piezas) > 1:
                # una línea de ladera no debería partirse; si pasa, se queda la
                # de más entidad y se avisa
                piezas = [max(piezas, key=lambda p: _estaciones(p)[-1])]
                res["partidas"] += 1
            listas = []
            for pz in piezas:
                if pegar:
                    # El pie de la ladera se pega a la CORONACIÓN de la orilla
                    # exterior, que es la línea 3D que pasa por ahí. Cuál es el
                    # pie se decide por la DISTANCIA AL CAUCE, nunca por la
                    # cota: donde el cauce va sobre relleno, la ladera BAJA de
                    # él y su pie es el extremo más ALTO de la línea. Con el
                    # criterio de cota se pegaba el extremo del límite a la
                    # cota de la orilla y la ladera entera se venía abajo.
                    _k0, _d0, _s0 = corr._cerca(pz[0][0], pz[0][1])
                    _k1, _d1, _s1 = corr._cerca(pz[-1][0], pz[-1][1])
                    en_inicio = _d0 <= _d1
                    pie = pz[0] if en_inicio else pz[-1]
                    z_borde = corr.cota_borde(pie[0], pie[1])
                    if z_borde is not None:
                        pz = ajustar_extremo(pz, z_borde, en_inicio=en_inicio,
                                             mezcla=15.0)
                listas.append(pz)
            cambios[f.id()] = listas[0]
            for pz in listas[1:]:
                extra.append((list(f.attributes()), pz))
            res["recorte_m"] += quitado
        if cambios or borrar or extra:
            capa.startEditing()
            for fid, pts in cambios.items():
                capa.changeGeometry(fid, QgsGeometry.fromPolyline(
                    [QgsPoint(x, y, z) for x, y, z in pts]))
            if borrar:
                capa.deleteFeatures(borrar)
            capa.commitChanges()
            if extra:
                # los trozos sobrantes de una línea partida entran como
                # entidades nuevas, con los mismos atributos
                nuevas = []
                for atrib, pz in extra:
                    nf = QgsFeature(capa.fields())
                    nf.setGeometry(QgsGeometry.fromPolyline(
                        [QgsPoint(x, y, z) for x, y, z in pz]))
                    idx = indices_datos(capa)
                    vals = [atrib[i] for i in idx]
                    nf.setAttributes(attrs(capa, vals))
                    nuevas.append(nf)
                capa.dataProvider().addFeatures(nuevas)
                capa.updateExtents()
                res["partidas"] += len(nuevas)
            capa.triggerRepaint()
            res["recortadas"] += len(cambios) + len(borrar)
            res["borradas"] += len(borrar)
    if res["recortadas"]:
        log(f"   · {res['recortadas']} línea(s) recortada(s) contra el corredor "
            f"del cauce ({res['recorte_m']:.0f} m en total, {res['borradas']} "
            f"eliminada(s), {res['partidas']} partida(s) en dos); las "
            f"divisorias se paran {holgura:g} m por fuera del borde "
            f"flood-prone")

    # ---------- 2. cota de las divisorias ----------
    capa_div = lm.obtener_capa("GRD_Ridges", crear=False)
    capa_sr = lm.obtener_capa("GRD_SubRidges", crear=False)
    capa_vg = lm.obtener_capa("GRD_Swales", crear=False)
    if capa_div is None or capa_sr is None or capa_div.featureCount() == 0:
        return res

    contorno = None
    if g_lim is not None and not g_lim.isEmpty():
        anillo = (g_lim.asPolygon()[0] if not g_lim.isMultipart()
                  else g_lim.asMultiPolygon()[0][0])
        contorno = QgsGeometry.fromPolylineXY([QgsPointXY(p) for p in anillo])

    # Distancia al cauce, para decidir cuál es el extremo ALTO de una línea de
    # ladera. NUNCA por cota: donde el cauce va sobre relleno la ladera baja de
    # él y el extremo más alto es el pie. Ver `extremo_alto` y P-19.
    def d_cauce(x, y):
        return corr_ladera._cerca(x, y)[1]

    cabeceras = []          # [(x, y, z)] de las subcrestas
    for f in capa_sr.getFeatures():
        pts = _pts3(f)
        if len(pts) < 2:
            continue
        alto = pts[extremo_alto(pts, d_cauce)]
        if contorno is not None:
            dl = contorno.distance(
                QgsGeometry.fromPointXY(QgsPointXY(alto[0], alto[1])))
            if dl < MARGEN_LIMITE:
                continue        # muere en el límite, no en la divisoria
        # La cota que el espolón IMPONE es la de su propio filo, no la del
        # último vértice: si un pase anterior le pegó una cola descendente
        # hasta la divisoria vieja, tomar ese último valor sería preguntarle a
        # la divisoria por su propia cota anterior y no arreglar nada. Y se
        # acota por el techo de cresta, para que un valor heredado de una
        # pasada anterior no pueda pedir una cota imposible.
        z_cab = max(z for _, _, z in pts)
        techo = corr_div.techo_cresta(alto[0], alto[1], s_max, dem)
        if techo is not None:
            z_cab = min(z_cab, techo)
        cabeceras.append((alto[0], alto[1], z_cab))

    # Cabeceras de VAGUADA: no levantan la divisoria, la hunden un poco. Es la
    # 'silla' del libro, §9.11.2, p. 259 (NO 9.4, que es 'Reference area
    # observation'; la palabra 'saddle' aparece UNA sola vez en todo el libro):
    # «the head of the swale depressions on the valley walls in natural
    # landforms tend to form saddles between the sub-ridges to either side of
    # the depression. In the design, incorporating dips in the ridgeline at
    # these locations prevents runoff water from flowing down the ridgeline in
    # tire ruts. Instead, it allows it to flow off the ridge and down the
    # valley wall swales».
    # OJO: el libro dice POR QUE existen las sillas, pero NO da ninguna cifra
    # de profundidad, ni absoluta ni relativa, y lo describe como una edicion
    # manual del disenador. `prof_silla_pct` es decision NUESTRA (ADR-020).
    cab_vaguada = []
    if capa_vg is not None:
        for f in capa_vg.getFeatures():
            pts = _pts3(f)
            if len(pts) < 2:
                continue
            alto = pts[extremo_alto(pts, d_cauce)]
            if contorno is not None and contorno.distance(
                    QgsGeometry.fromPointXY(
                        QgsPointXY(alto[0], alto[1]))) < MARGEN_LIMITE:
                continue
            cab_vaguada.append(alto)

    cambios = {}
    for f in capa_div.getFeatures():
        pts = _limpiar_vertices(_pts3(f))
        if len(pts) < 3:
            continue
        # el paso de vértices se fija ANTES de calcular la cota, para que los
        # puntos de control y el perfil se resuelvan ya sobre la traza final
        paso_v = float(getattr(glob, "max_dist_vertices_cresta", 6.1))
        pts = remuestrear(pts, paso_v)
        dens = [(x, y) for x, y, _ in pts]
        ctrl = list(puntos_de_control(dens, cabeceras, separacion=paso_v))
        s = _estaciones(dens)
        L = s[-1]
        # --- cotas de los dos extremos ---
        # en el límite GeoFluv manda el DEM (empalme con el terreno existente);
        # en el extremo truncado contra un cauce, el techo de cresta.
        z_ext = [None, None]
        for j, extremo in enumerate((0, len(pts) - 1)):
            x, y, z = pts[extremo]
            gp = QgsGeometry.fromPointXY(QgsPointXY(x, y))
            if contorno is not None and contorno.distance(gp) < MARGEN_LIMITE:
                if dem is not None:
                    from . import setup_tools as st
                    zd = st.cota_dem(dem, x, y)
                    if zd is not None:
                        z = zd
            else:
                techo = corr_div.techo_cresta(x, y, s_max, dem)
                if techo is not None:
                    z = min(z, techo)
            z_ext[j] = z
        # --- perfil de partida: la ECUACIÓN, no un muestreo punto a punto ---
        # El manual describe el perfil de una cresta igual que el de un canal:
        # curva vertical entre las cotas de los dos extremos, con la cabeza
        # convexa de longitud xc. Muestrear `_z_ladera` vértice a vértice daba
        # un filo ondulado que no es la forma del método.
        desde_inicio = z_ext[0] >= z_ext[1]
        z_alto, z_bajo = max(z_ext), min(z_ext)
        # misma fuente que `ridges._perfil_cresta`: eran dos expresiones
        # distintas para la misma cosa y se iban a desincronizar
        lc_cresta = convexo_cresta(glob, L)
        base = perfil_base(pts, z_alto, z_bajo, lc_cresta,
                           desde_inicio=desde_inicio)
        # --- sillas: la divisoria se hunde donde muere una vaguada ---
        # El contador es LOCAL de esta divisoria. Era `res["sillas"]`, que se
        # acumula a lo largo del bucle, y se usaba abajo como
        # `monotona=(res["sillas"] == 0)`: en cuanto UNA divisoria generaba una
        # silla, TODAS las siguientes del mismo pase perdian la monotonia,
        # tuvieran sillas o no. Ver B-035.
        n_sillas = 0
        pct = max(0.0, min(0.9, float(getattr(glob, "prof_silla_pct", 25.0))
                           / 100.0))
        if pct > 0:
            for (xv, yv, zv) in cab_vaguada:
                dd, sv, _ = _proyectar(dens, xv, yv)
                if dd > TOL_LLEGADA:
                    continue
                # una subcresta pegada manda: ahí hay filo, no silla
                if any(abs(c[0] - sv) < 6.0 for c in ctrl):
                    continue
                i = min(range(len(s)), key=lambda k: abs(s[k] - sv))
                z_crest = base[i]
                if z_crest - zv <= 0.05:
                    continue
                ctrl.append((sv, z_crest - pct * (z_crest - zv)))
                n_sillas += 1
            ctrl.sort()
        res["sillas"] += n_sillas
        # Los dos extremos son anclajes de la curva base; solo se sueltan si
        # hay una cabecera de espolón pegada a ellos, porque entonces manda el
        # empalme.
        z_ini, z_fin = z_ext[0], z_ext[1]
        if ctrl and ctrl[0][0] < 2.0:
            z_ini = None
        if ctrl and ctrl[-1][0] > L - 2.0:
            z_fin = None
        if not ctrl:
            # sin espolones que la modifiquen, la curva base ES el perfil
            cambios[f.id()] = [(x, y, z) for (x, y), z in zip(dens, base)]
            res["divisorias"] += 1
            continue
        # con sillas el perfil YA NO es monótono por definición: una
        # divisoria natural sube a los espolones y baja a las vaguadas
        #
        # OJO (P-24): esto es un error de categoría latente —una silla en la
        # estación 88 suelta los 346 m de perfil enteros—, pero NO se ha tocado
        # porque medido en el Ej_2 apenas cambia nada: 95.37 → 94.30 m de vaivén
        # sobre las 13 divisorias, y a cambio deja una meseta de 5 vértices en
        # una de ellas. El vaivén no viene de aquí, viene de los propios puntos
        # de control y del residuo. Solo hay 4 sillas en todo el ejemplo.
        zs = perfil_desde_control(dens, base, ctrl, s_max,
                                  z_top=z_fin, z_bot=z_ini,
                                  monotona=(n_sillas == 0))
        if zs is None:
            continue
        cambios[f.id()] = [(x, y, z) for (x, y), z in zip(dens, zs)]
        res["control"] += len(ctrl)
        res["divisorias"] += 1
    if cambios:
        capa_div.startEditing()
        for fid, pts in cambios.items():
            capa_div.changeGeometry(fid, QgsGeometry.fromPolyline(
                [QgsPoint(x, y, z) for x, y, z in pts]))
        capa_div.commitChanges()
        capa_div.triggerRepaint()
        log(f"   · {res['divisorias']} divisoria(s) con la cota derivada de "
            f"{res['control']} cabecera(s) de subcresta y {res['sillas']} "
            f"silla(s) donde muere una vaguada")

    # ---------- 3a. ninguna ladera cruza la divisoria ----------
    res["cortadas_div"] = _cortar_en_divisorias(lm, d_cauce)
    if res["cortadas_div"]:
        log(f"   · {res['cortadas_div']} línea(s) de ladera cortada(s) en la "
            f"divisoria: una subcresta muere sobre ella, no la atraviesa")

    # ---------- 3b. encaje de las cabeceras ----------
    divs = [[(x, y, z) for x, y, z in _pts3(f)] for f in capa_div.getFeatures()]
    if not divs:
        return res
    for nombre, capa, subir in (("GRD_SubRidges", capa_sr, True),
                                ("GRD_Swales", capa_vg, False)):
        if capa is None:
            continue
        cambios = {}
        for f in capa.getFeatures():
            pts = _pts3(f)
            if len(pts) < 2:
                continue
            k_alto = extremo_alto(pts, d_cauce)     # por distancia, no por cota
            en_inicio = k_alto == 0
            alto = pts[k_alto]
            mejor = (float("inf"), None)
            for dpts in divs:
                dd, _, zz = _proyectar(dpts, alto[0], alto[1])
                if zz is not None and dd < mejor[0]:
                    mejor = (dd, zz)
            if mejor[1] is None or mejor[0] > TOL_LLEGADA:
                continue
            z_obj = mejor[1]
            if not subir:
                # una vaguada nunca sobresale de la divisoria, pero tampoco se
                # levanta hasta ella: se queda donde estaba si ya iba por debajo
                if alto[2] <= z_obj + 1e-3:
                    continue
                res["vaguadas_bajadas"] += 1
            # Se reajusta SIEMPRE, aunque la cabecera ya esté a la cota de la
            # divisoria: lo que hay que arreglar no es el valor del último
            # vértice sino la forma con la que llega. Un pase anterior pudo
            # pegarle una cola de dos metros con ocho de desnivel, y esa cola
            # está a la cota correcta pero es un muro.
            cambios[f.id()] = ajustar_extremo(pts, z_obj, en_inicio=en_inicio,
                                              mezcla=MEZCLA_CABECERA)
        if cambios:
            capa.startEditing()
            for fid, pts in cambios.items():
                capa.changeGeometry(fid, QgsGeometry.fromPolyline(
                    [QgsPoint(x, y, z) for x, y, z in pts]))
            capa.commitChanges()
            capa.triggerRepaint()
            res["encajadas"] += len(cambios)
    if res["encajadas"]:
        log(f"   · {res['encajadas']} cabecera(s) encajada(s) sobre la "
            f"divisoria ({res['vaguadas_bajadas']} vaguada(s) que sobresalían)")

    # ---------- 3c. empalme con el terreno en el límite GeoFluv ----------
    res["empalmes_limite"], res["peor_escalon"] = _empalmar_con_el_limite(
        lm, contorno, dem, corr_ladera)
    if res["empalmes_limite"]:
        log(f"   · {res['empalmes_limite']} línea(s) de ladera empalmada(s) "
            f"con el terreno existente en el límite (el peor escalón era de "
            f"{res['peor_escalon']:.1f} m)")

    # NO se vuelve a curvar el perfil después de recortar. El orden correcto
    # es el de siempre: el motor traza la ladera con su ecuación y DESPUÉS se
    # recorta y se ajustan los extremos repartiendo la corrección. Volver a
    # aplicar `perfil_trapezoidal` entre los dos extremos ya movidos tiraba a
    # la basura la forma calculada y la sustituía por otra ajustada a una
    # longitud y unas cotas que ya no son las de diseño: los cauces que
    # terminan antes del borde superior salían con formas raras.
    return res


def _puntos_de(g):
    """Puntos de una geometría de intersección, sea punto, multipunto o línea
    (dos líneas colineales se cortan en un tramo, no en un punto)."""
    if g is None or g.isEmpty():
        return []
    try:
        if g.isMultipart():
            ps = g.asMultiPoint()
            if ps:
                return [(p.x(), p.y()) for p in ps]
        else:
            p = g.asPoint()
            return [(p.x(), p.y())]
    except Exception:
        pass
    v = [(p.x(), p.y()) for p in g.vertices()]
    return v[:1] + v[-1:] if v else []


def _cortar_en_divisorias(lm, d_cauce=None):
    """Una subcresta muere SOBRE la divisoria; no la atraviesa.

    Es la definición del libro: *«sub-ridge … extends from the inside of a
    stream channel bend up to a main ridge at the top of the valley wall that
    makes the catchment divide»*. Si la cruza, está metiéndose en la cuenca de
    al lado y en planta se ve pasada de largo.

    Ocurre porque `topology.empalmar_en_divisorias` prolonga la subcresta hasta
    la divisoria y puede pasarse, y porque la divisoria se mueve después. Se
    corta en el primer cruce contando desde el pie y se conserva el trozo del
    pie, con el vértice final exactamente en el cruce.
    """
    capa_div = lm.obtener_capa("GRD_Ridges", crear=False)
    if capa_div is None or capa_div.featureCount() == 0:
        return 0
    divs = []
    idx = QgsSpatialIndex()
    for f in capa_div.getFeatures():
        g = f.geometry()
        if g is None or g.isEmpty():
            continue
        nf = QgsFeature(len(divs))
        nf.setGeometry(g)
        idx.addFeature(nf)
        divs.append(g)
    if not divs:
        return 0
    n = 0
    for nombre in ("GRD_SubRidges", "GRD_Swales"):
        capa = lm.obtener_capa(nombre, crear=False)
        if capa is None:
            continue
        cambios = {}
        for f in capa.getFeatures():
            g = f.geometry()
            cerca = [divs[k] for k in idx.intersects(g.boundingBox())]
            if not cerca or not any(g.crosses(dg) for dg in cerca):
                continue
            pts = _pts3(f)
            # recorrer desde el PIE hacia la cabecera. El pie es el extremo
            # CERCANO al cauce, no el más bajo: ver `extremo_alto` y P-19.
            invertida = extremo_alto(pts, d_cauce) == 0
            seq = list(reversed(pts)) if invertida else pts
            nuevos = [seq[0]]
            corte = None
            for a, b in zip(seq[:-1], seq[1:]):
                seg = QgsGeometry.fromPolylineXY(
                    [QgsPointXY(a[0], a[1]), QgsPointXY(b[0], b[1])])
                tocado = None
                for dg in cerca:
                    if seg.intersects(dg):
                        inter = seg.intersection(dg)
                        for (px, py) in _puntos_de(inter):
                            dd = math.hypot(px - a[0], py - a[1])
                            if tocado is None or dd < tocado[0]:
                                tocado = (dd, px, py)
                if tocado is not None:
                    Lseg = math.hypot(b[0] - a[0], b[1] - a[1])
                    t = min(1.0, tocado[0] / max(Lseg, 1e-9))
                    corte = (tocado[1], tocado[2], a[2] + t * (b[2] - a[2]))
                    break
                nuevos.append(b)
            if corte is None:
                continue
            if math.hypot(corte[0] - nuevos[-1][0],
                          corte[1] - nuevos[-1][1]) > 0.05:
                nuevos.append(corte)
            else:
                nuevos[-1] = corte
            if len(nuevos) < 3 or _estaciones(nuevos)[-1] < 2.0:
                continue
            cambios[f.id()] = list(reversed(nuevos)) if invertida else nuevos
        if cambios:
            capa.startEditing()
            for fid, pts in cambios.items():
                capa.changeGeometry(fid, QgsGeometry.fromPolyline(
                    [QgsPoint(x, y, z) for x, y, z in pts]))
            capa.commitChanges()
            capa.triggerRepaint()
            n += len(cambios)
    return n


TOL_BORDE = 2.0        # m, a esta distancia del límite la línea muere en él


def _empalmar_con_el_limite(lm, contorno, dem, corr, tol=TOL_BORDE):
    """Toda ladera que muere en el límite GeoFluv llega a la cota del TERRENO.

    Es la condición de contorno del método: el diseño tiene que integrarse con
    el paisaje que lo rodea y con el nivel de base local. Sin ella el diseño
    levanta un muro contra el perímetro —medido en el proyecto real: hasta
    **19.7 m** de relleno sobre el piso de corta, que ahí es plano a 1062—.

    `_trazar_ladera` ya hace esto cuando la marcha SALE del polígono
    (`toco_borde`), pero una línea puede pararse justo en el borde por la
    condición de Voronoi o al rozar otra línea, y entonces la cota se la pone
    `_z_ladera`, que mira el canal y la distancia pero no el suelo que hay.
    Aquí se corrige por geometría, sin depender de qué rama la generó: si el
    extremo está sobre el límite, su cota es la del terreno, y punto.

    Solo se toca el extremo. El perfil completo lo rehace después
    `_rehacer_laderas` con la ecuación, de modo que la línea baja al perímetro
    con su forma convexa-cóncava en vez de con un escalón. Cuando el cauce
    queda por encima del perímetro —el caso de este proyecto— el resultado es
    justamente una ladera que vierte hacia ese extremo.
    """
    if contorno is None or dem is None:
        return 0, 0.0
    from . import setup_tools as st
    n, peor = 0, 0.0
    for nombre in ("GRD_SubRidges", "GRD_Swales"):
        capa = lm.obtener_capa(nombre, crear=False)
        if capa is None:
            continue
        cambios = {}
        for f in capa.getFeatures():
            pts = _pts3(f)
            if len(pts) < 3:
                continue
            # Cuál es el PIE se decide por la DISTANCIA AL CAUCE, no por la
            # cota. Suponer que el pie es el extremo más alto es falso justo
            # en el caso que nos ocupa: al oeste el cauce va sobre relleno y la
            # ladera BAJA de él hacia el perímetro, así que el pie es el punto
            # más alto de la línea. Con el criterio de cota se agarraba el
            # extremo equivocado, se bajaba el arranque del cauce a la cota del
            # terreno y salían la meseta plana y la zanja de en medio.
            _k0, d0, _s0 = corr._cerca(pts[0][0], pts[0][1])
            _k1, d1, _s1 = corr._cerca(pts[-1][0], pts[-1][1])
            k = len(pts) - 1 if d0 <= d1 else 0
            x, y, z = pts[k]
            if contorno.distance(
                    QgsGeometry.fromPointXY(QgsPointXY(x, y))) > tol:
                continue
            zt = st.cota_dem(dem, x, y)
            if zt is None or abs(z - zt) < 0.05:
                continue
            # Se REPARTE la corrección hacia dentro conservando la forma que
            # el motor le dio a la ladera. Antes se movía solo este vértice y
            # se rehacía después todo el perfil con la ecuación: eso borraba
            # la geometría original y empeoraba el resultado.
            nuevos = ajustar_extremo(pts, zt, en_inicio=(k == 0),
                                     mezcla=MEZCLA_LIMITE)
            nuevos = _limpiar_vertices(nuevos)
            cambios[f.id()] = nuevos
            peor = max(peor, abs(z - zt))
        if cambios:
            capa.startEditing()
            for fid, pts in cambios.items():
                capa.changeGeometry(fid, QgsGeometry.fromPolyline(
                    [QgsPoint(px, py, pz) for px, py, pz in pts]))
            capa.commitChanges()
            capa.triggerRepaint()
            n += len(cambios)
    return n, peor


def _rehacer_laderas(lm, glob, disenos):
    """NO SE USA. Se conserva por si hiciera falta regenerar un perfil desde
    cero, pero NO debe llamarse después de recortar.

    Reconstruye el perfil de cada ladera con la ecuación, no a parches.

    ¡OJO! Llamarla tras el recorte fue un error (v1.0.17): rehacer el perfil
    entre los dos extremos ya movidos descarta la forma que el motor calculó y
    la sustituye por otra ajustada a una longitud y unas cotas que ya no son
    las de diseño. Los cauces que terminan antes del borde superior salían con
    formas raras. El orden correcto es trazar con la ecuación, recortar, y
    ajustar los extremos REPARTIENDO la corrección con `ajustar_extremo`.

    Después del recorte contra el corredor y del encaje de la cabecera, la
    línea tiene los dos extremos en su sitio pero el interior conserva el
    perfil que se calculó para OTRA longitud y otras cotas: de ahí las colas
    verticales y las mesetas. Se vuelve a aplicar `perfil_trapezoidal` entre
    los dos extremos actuales, con la longitud convexa xc que corresponda al
    canal, y la forma vuelve a ser la de diseño en toda la línea.
    """
    from .ridges import convexo_subcresta, convexo_vaguada
    canales = {}
    iterable = disenos.values() if isinstance(disenos, dict) else (disenos or [])
    for d in iterable:
        canales[d.nombre] = d.settings
    n = 0
    for nombre, es_vaguada in (("GRD_SubRidges", False), ("GRD_Swales", True)):
        capa = lm.obtener_capa(nombre, crear=False)
        if capa is None:
            continue
        cambios = {}
        for f in capa.getFeatures():
            pts = _pts3(f)
            if len(pts) < 3:
                continue
            L = _estaciones(pts)[-1]
            if L < 1e-6:
                continue
            desde_inicio = pts[0][2] > pts[-1][2]
            z_alto = pts[0][2] if desde_inicio else pts[-1][2]
            z_bajo = pts[-1][2] if desde_inicio else pts[0][2]
            try:
                canal = canales.get(f.attributes()[1])
            except Exception:
                canal = None
            lc = (convexo_vaguada(glob, canal) if es_vaguada
                  else convexo_subcresta(glob, canal, L))
            zs = perfil_base(pts, z_alto, z_bajo, lc,
                             desde_inicio=desde_inicio)
            if max(abs(a - b[2]) for a, b in zip(zs, pts)) < 0.02:
                continue
            cambios[f.id()] = [(p[0], p[1], z) for p, z in zip(pts, zs)]
        if cambios:
            capa.startEditing()
            for fid, pts in cambios.items():
                capa.changeGeometry(fid, QgsGeometry.fromPolyline(
                    [QgsPoint(x, y, z) for x, y, z in pts]))
            capa.commitChanges()
            capa.triggerRepaint()
            n += len(cambios)
    return n
