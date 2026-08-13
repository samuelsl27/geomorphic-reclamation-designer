# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Crestas, subcrestas, vaguadas y subcuencas del diseño GeoFluv.

- SUBCUENCAS: partición del área del límite por proximidad a cada canal
  (polígonos de Voronoi de los puntos de las LÍNEAS DE VALLE, disueltos por
  canal y recortados al límite). Es la divisoria natural "equidistante" que
  el método materializa como crestas entre canales adyacentes. Equidistante de
  la línea de valle, **no del eje meandriforme**: ver `_capa_puntos_valle` y
  B-045.
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
from .params import pendiente_max_ladera, rumbo_de_ladera

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


def convexo_vaguada(glob, canal=None):
    """Longitud convexa (m) de una VAGUADA — su xc de Horton.

    Es el ajuste *'maximum distance from ridgeline to swale head'*
    [LIBRO p. 191]: «option 1 — **specify swale convex length** based on
    reference area observations». Se mide DESDE LA DIVISORIA, y es lo que sitúa
    la cabecera de la vaguada; **no es un retranqueo** que acorte la línea.

    De ella cuelga todo el relieve de ladera [LIBRO fig. 8-11, p. 204]:

        «A depression is formed by the SHORTER SWALE CONVEX LENGTH between the
         LONGER ADJACENT SUB-RIDGE CONVEX LENGTHS and runoff water is directed
         into the swale bottom.»

    Es decir: la vaguada es una depresión **porque su tramo convexo es más
    corto** que el de las subcrestas vecinas, no porque sea más corta ni acabe
    más abajo. Las dos salen del cauce y las dos mueren en la divisoria.

    Orden de preferencia:
      1. `dist_cresta_swale_m` del canal (el ajuste por cuenca del *Geometry
         tab*);
      2. `convexo_swale_m` global, si `convexo_swale_activo` (*maximum swale
         convexity* de Global Settings, [LIBRO p. 189]);
      3. `max_dist_cresta_cabecera` (xrh) — [LIBRO p. 236]: «the convex swale
         length, xc, was **similar to the xrh value** in the three stable
         reference areas».
    """
    if canal is not None:
        v = getattr(canal, "dist_cresta_swale_m", None)
        if v:
            return float(v)
    if getattr(glob, "convexo_swale_activo", False) and \
            getattr(glob, "convexo_swale_m", 0):
        return float(glob.convexo_swale_m)
    return float(glob.max_dist_cresta_cabecera)


def convexo_subcresta(glob, canal=None, D=None):
    """Longitud convexa (m) de subcresta según ajustes: por canal si
    'especificar_convexo', si no la global. Modo 'factor' = 1.5 × distancia
    cresta-cabecera(-swale); modo 'pct' = % de la longitud de la ladera.

    El factor 1.5 es del método [LIBRO p. 191]: «maximum convex length of a
    sub-ridge – **1.5 x** 'xx' — sub-ridge convex length calculated as 1.5 x
    the specified swale convex length», y en Global Settings [LIBRO p. 189]
    «1.5 x '25' — 1.5 times the ridge-to-head of channel distance». La
    subcresta tiene SIEMPRE tramo convexo más largo que la vaguada: de esa
    diferencia sale la depresión (`convexo_vaguada`)."""
    if canal is not None and getattr(canal, "especificar_convexo", False):
        if getattr(canal, "convexo_modo_canal", "factor") == "pct" and D:
            return canal.convexo_pct_canal / 100.0 * D
        return 1.5 * getattr(canal, "dist_cresta_swale_m", 24.0)
    if glob.convexo_modo == "pct" and D:
        return glob.convexo_pct / 100.0 * D
    return 1.5 * glob.max_dist_cresta_cabecera


def traza_y_cotas(linea):
    """`(traza 2D, cotas)` de una polilínea 3D, para consumo de `hillslopes`.

    Existe para que la geometría y el array de cotas salgan SIEMPRE del mismo
    objeto. `_perfil_cresta` invierte su copia de los puntos cuando el perfil
    viene al revés (`dens = dens[::-1]`, reasignación local que no toca la
    lista del llamante), así que `zs` puede quedar en orden inverso al de los
    puntos que se le pasaron. Emparejarlos con esos puntos daba a la mitad de
    las divisorias **las cotas del revés**, y las laderas que toman de aquí su
    cota de coronación heredaban la del OTRO extremo de la divisoria (B-028).

    Pasar por esta función quita de en medio la posibilidad de equivocarse: no
    hay dos fuentes entre las que elegir.
    """
    return (QgsGeometry.fromPolylineXY([QgsPointXY(p.x(), p.y()) for p in linea]),
            [p.z() for p in linea])


def _muestras_de_valle(d):
    """Puntos (x, y) de la LÍNEA DE VALLE de un diseño.

    Es el punto de corte de todo el cambio de B-045, así que vive en su propia
    función y tiene su propia prueba: `d.dens` es `[(s, x, y)]` del fondo de
    valle, ya densificado a `builder.PASO_DENSIFICADO` = 1 m; `d.puntos` es
    `[(x, y, z, s)]` del eje meandriforme. La partición de subcuencas se hace
    con la primera.

    El respaldo al eje es para diseños que no traigan `dens` (bancos de prueba
    antiguos, o un `Diseno` construido a mano): mejor una cuenca con la fuente
    equivocada que una cuenca sin puntos, que desaparecería del Voronoi y se
    llevaría por delante las divisorias de sus vecinas."""
    pts = [(x, y) for _s, x, y in getattr(d, "dens", None) or ()]
    if not pts:
        pts = [(p[0], p[1]) for p in getattr(d, "puntos", None) or ()]
    return pts


def _capa_puntos_valle(disenos, crs):
    """Capa temporal de puntos de las LÍNEAS DE VALLE, con atributo 'canal'.

    **La fuente es la línea de valle (`d.dens`), NO el eje meandriforme
    (`d.puntos`)**, y esa es la corrección de B-045. La divisoria de cuenca del
    método es equidistante de las *polilíneas de fondo de valle* —las que dibuja
    el usuario—, no de los ejes sinuosos que se trazan alrededor de ellas:

    > «The main ridgelines are shown between the tributary channels and are
    > **sub-parallel to the channels**» (Natural Regrade Module p. 36-37), y el
    > Preview muestra «main ridgelines (yellow) and **valley centerlines (more
    > linear blue)**», con los ejes zigzag o sinuosos dibujados «**around** the
    > more linear valley input lines» (LIBRO p. 242, pie de la fig. 9-13).

    Medido en la salida original del Ej_2, `|d₁ − d₂|` de cada vértice de las
    siete divisorias respecto a las dos líneas más próximas:

    | | a las líneas de VALLE | a los EJES meandriformes |
    |---|---|---|
    | original | **0.02 – 0.73 m** | 1.0 – 2.9 m (máx 15.5) |
    | nuestro (v1.0.24) | 1.77 – 4.52 m | **0.14 – 1.78 m** |

    O sea, hacíamos exactamente lo contrario, y por eso la divisoria heredaba la
    ondulación del meandro: giro acumulado de 70 °/100 m de media frente a los
    6.5 – 31.3 del original, con giros de hasta 42.9° frente a 17.3°.

    **El paso de muestreo da igual.** Repitiendo la medida contra las *muestras*
    de las líneas de valle a 0.5, 1 y 5 m sale lo mismo (0.02 – 0.85 m): el error
    de aproximar la bisectriz de dos curvas por la de dos nubes de puntos vale
    ~h²/8d, o sea 0.05 m con h = 5 m y d = 65 m. Lo único que importa es **de qué
    línea se muestrea**. Por eso se usa `d.dens` tal cual, que ya viene
    densificado a `builder.PASO_DENSIFICADO` = 1 m.

    Ojo: `_geoms_ejes()` sigue devolviendo el **eje meandriforme**, y tiene que
    seguir haciéndolo. La distancia cauce-divisoria que gobierna la cota de
    ladera es al agua de verdad, no a la línea de valle.
    """
    lyr = QgsVectorLayer(f"Point?crs={crs}", "tmp_pts_valle", "memory")
    lyr.dataProvider().addAttributes([QgsField("canal", CAMPO_STR)])
    lyr.updateFields()
    feats = []
    for d in disenos.values():
        for x, y in _muestras_de_valle(d):
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


def convexo_cresta(glob, L):
    """Longitud convexa de una DIVISORIA. Fuente única para `ridges` y
    `divides`: eran dos expresiones distintas y se iban a desincronizar, que es
    el patrón nº 10 del catálogo de bugs."""
    return min(convexo_subcresta(glob, None, L), 0.5 * max(L, 1e-6))


def suelo_de_cresta(lados, resguardo=0.25):
    """Cota MÍNIMA de un filo: por encima del lecho de TODOS sus cauces.

    Una divisoria por debajo de un lecho no separa nada, drena al revés y deja
    charcos en el TIN.

    **OJO, y aquí me equivoqué en la v1.0.22**: este docstring decía que era
    «`max` de funciones continuas, así que es continuo y no escribe escalones».
    Es falso. Lo que cambia no son las funciones, es **el CONJUNTO**: `lados`
    son los dos cauces más próximos, y esa pareja cambia de miembros a lo largo
    de la divisoria. `techo_de_ladera` se salva de eso porque usa `min` y el
    cauce que entra y sale es el lejano, cuyo término es el mayor; el `max` de
    aquí está dominado **justo por él**, así que hereda el salto entero.

    Medido en el Ej_2 con la v1.0.22: el suelo mandaba en el **40.9 %** de los
    vértices de divisoria y él mismo saltaba hasta **15.80 m** entre vértices
    consecutivos. Por eso ya **no se aplica punto a punto**: acota el extremo
    libre (ver `resolver_extremo_libre`), que es donde no puede escribir
    escalones. Ver B-038."""
    if not lados:
        return None
    return max(z for _D, z, _s, _lc in lados) + resguardo


PESO_MIN_EXTREMO = 0.50   # peso mínimo con el que un punto puede opinar sobre
                          # la cota del extremo libre; acota la amplificación
                          # del despeje a 1/PESO = 2


def resolver_extremo_libre(f, techo, z_fijo, libre_es_alto, suelo=None,
                           peso_min=PESO_MIN_EXTREMO):
    """Cota del extremo LIBRE: la más alta que respeta el techo y el suelo.

    `perfil_trapezoidal` es exactamente **lineal en `dz`** (está comprobado en
    `test_el_perfil_es_lineal_en_el_desnivel`), así que con
    `f(x) = perfil_trapezoidal(x, L, 1, lc)` la curva es la combinación convexa

        z(x) = z_alto·(1 − f(x)) + z_bajo·f(x),   f monótona de 0 a 1

    y las dos condiciones se despejan de una vez, sin iterar:

        z_alto ≤ min_x [ (techo(x) − z_bajo·f(x)) / (1 − f(x)) ]      (techo)
        z_alto ≥ max_x [ (suelo(x) − z_bajo·f(x)) / (1 − f(x)) ]      (suelo)

    Se coge la mayor de las dos, o sea **el suelo manda sobre el techo**: una
    divisoria por debajo del lecho de su cauce es un error duro, y quedarse
    corto de pendiente de ladera es solo un objetivo incumplido (el manual la
    llama *«a best-fit slope adjustment toward the specified target value»*,
    NRM p. 1718).

    **`peso_min` es la corrección de B-038**, y es lo que hace que el despeje sea
    estable. El factor de amplificación del cociente es `1/peso`, así que un
    punto con `peso` pequeño convierte centímetros de restricción en decenas de
    metros de cota. Y los pesos pequeños están precisamente **junto al extremo
    fijo**, que es donde la divisoria muere: ahí la distancia al cauce tiende a
    cero, el techo tiende al propio lecho y el suelo también, o sea que ese
    tramo **no aporta ninguna información** sobre la cota del otro extremo — su
    cota ya la fija el ancla.

    Sin la guarda, en el Ej_2: siete de trece divisorias salían con menos de 7 m
    de desnivel (una con 2.4 m en 117 m) cuando la más pequeña del original
    tiene 11.5; y al añadir el suelo, dos se disparaban a 240 y 100 m de
    desnivel. Con `peso_min = 0.5` la amplificación queda acotada a ×2 y el
    desnivel máximo en 68.2 m, contra los 64.1 del original."""
    alto, bajo = None, None
    for k, fk in enumerate(f):
        peso = (1.0 - fk) if libre_es_alto else fk
        if peso < max(peso_min, 1e-9):
            continue
        otro = (z_fijo * fk) if libre_es_alto else (z_fijo * (1.0 - fk))
        tk = techo[k] if techo else None
        if tk is not None:
            cand = (tk - otro) / peso
            if alto is None or cand < alto:
                alto = cand
        sk = suelo[k] if suelo else None
        if sk is not None:
            cand = (sk - otro) / peso
            if bajo is None or cand > bajo:
                bajo = cand
    if alto is None:
        return bajo
    if bajo is None:
        return alto
    return max(alto, bajo)


def proyectar_en_eje(puntos, x, y):
    """(distancia, cota) del punto más próximo del eje, INTERPOLANDO.

    La versión anterior tomaba el vértice más próximo muestreando uno de cada
    dos (`range(0, len(puntos), 2)`): la distancia salía exacta y la cota no,
    que son dos criterios distintos sobre el mismo punto y una fuente de
    escalones de por sí."""
    mejor = (float("inf"), None)
    for i in range(len(puntos) - 1):
        ax, ay, az = puntos[i][0], puntos[i][1], puntos[i][2]
        bx, by, bz = puntos[i + 1][0], puntos[i + 1][1], puntos[i + 1][2]
        dx, dy = bx - ax, by - ay
        den = dx * dx + dy * dy
        t = 0.0 if den < 1e-12 else max(0.0, min(
            1.0, ((x - ax) * dx + (y - ay) * dy) / den))
        d = math.hypot(x - (ax + t * dx), y - (ay + t * dy))
        if d < mejor[0]:
            mejor = (d, az + t * (bz - az))
    if mejor[1] is None and puntos:
        p = puntos[0]
        return math.hypot(x - p[0], y - p[1]), p[2]
    return mejor


def techo_de_ladera(lados, lf=None, resguardo=0.25):
    """Cota MÁXIMA de un filo, evaluada con TODOS los cauces que lo flanquean.

    `lados` = [(D, z_lecho, s, lc), …]. Devuelve
    `min(z_lecho + desnivel_de_ladera(D, s, lc))`.

    **Es un techo, no un suelo**, y ese es el sentido del método: el ajuste se
    llama *Maximum straight-line slopes* y el manual dice que las crestas se
    colocan *«at elevations that create side slopes **less than** a default 5:1
    gradient»* (p. 1706); el ejercicio del libro (pp. 270 y 272) **baja** la
    cresta de 120 a 80 ft para suavizar la ladera del 40 % al 20 %. Despejado
    del propio perfil que dibujamos: la pendiente del tramo recto vale
    `dz/(D − lc/2 − lf/2)`, así que exigirle `≤ s` es exactamente
    `dz ≤ desnivel_de_ladera(D, s, lc)`.

    **Y con TODOS los lados, no con el más próximo.** Una divisoria de Voronoi
    es equidistante de dos ejes, así que «el más próximo» se alterna por
    milímetros: medido en el Ej_2, cambia en el **21.2 %** de los pasos de
    vértice a vértice, y con él la cota de lecho de referencia salta 4.15 m de
    mediana y hasta **29.96 m**. El `min` de dos funciones continuas es
    continuo: donde antes se alternaba el ganador ahora `D_A = D_B` y los dos
    candidatos coinciden, así que el salto desaparece por construcción y no por
    promediado. Es además lo que dice el libro (p. 180): el ajuste sirve para
    que *«as one side of the ridge reaches its slope steepness target, the
    other side of the ridge does not become over-steepened»* — mira los dos
    lados a la vez.

    Lejos de una divisoria degrada solo: el cauce lejano tiene `D` grande, así
    que su término es el mayor y el `min` se queda con el cercano."""
    if not lados:
        return None
    return min(z + max(desnivel_de_ladera(D, s, lc, lf), resguardo)
               for D, z, s, lc in lados)


def lados_de_un_punto(pt, disenos, geoms, s_max, glob=None, convexo=None, n=2):
    """[(D, z_lecho, s, lc)] de los `n` cauces más próximos a `pt`.

    Todo se calcula **por lado**, y a propósito: `s` porque la ladera de cada
    lado tiene su propia orientación y puede caerle `pendiente_NE_pct`
    (ADR-018), y `lc` porque sale de los ajustes de SU canal. Tomar el `lc` del
    lado más próximo volvería a meter un salto cada vez que cambia el ganador,
    que es justo lo que se viene a quitar."""
    g = QgsGeometry.fromPointXY(QgsPointXY(pt[0], pt[1]))
    cand = sorted((ge.distance(g), nombre) for nombre, ge in geoms.items())
    salida = []
    for _d, nombre in cand[:max(1, n)]:
        d = disenos[nombre]
        dist, z_ch = proyectar_en_eje(d.puntos, pt[0], pt[1])
        if convexo is not None:
            lc = convexo(dist) if callable(convexo) else convexo
        elif glob is not None:
            lc = convexo_subcresta(glob, getattr(d, "settings", None), dist)
        else:
            lc = 0.5
        s = s_max
        if glob is not None:
            # la ladera desciende de `pt` hacia el cauce: ese es su rumbo
            i = min(range(len(d.puntos)),
                    key=lambda k, _p=pt: (d.puntos[k][0] - _p[0]) ** 2
                    + (d.puntos[k][1] - _p[1]) ** 2)
            s = pendiente_max_ladera(
                glob, rumbo_de_ladera([(pt[0], pt[1], z_ch + 1.0),
                                       (d.puntos[i][0], d.puntos[i][1], z_ch)]))
        salida.append((dist, z_ch, s, lc))
    return salida


def _z_ladera(pt, disenos, geoms, s_max, dem=None, cap_dem=False,
              contorno=None, banda_mezcla=0.0, convexo=None, glob=None,
              n_lados=2):
    """Cota TECHO en un punto de ladera/cresta, con los `n_lados` cauces que lo
    flanquean: `min(z_lecho + Δz)`. Ver `techo_de_ladera`.

    Hasta la v1.0.21 esto devolvía la cota del **canal más próximo** y se usaba
    como **suelo** (`max(z, z_env)` en `_perfil_cresta`). Las dos cosas estaban
    mal: el ajuste es un máximo de pendiente, así que acota por arriba; y «el
    más próximo» se alterna sobre una divisoria equidistante y metía saltos de
    hasta 29.96 m. Ver B-0xx y la ADR de la v1.0.22.

    `glob` activa el segundo objetivo de pendiente del método ('North or East
    straight-line slopes'): la ladera que sube desde el cauce hasta `pt`
    desciende hacia su cauce, así que su orientación se conoce aquí sin
    necesidad de haberla trazado, y si mira al norte o al este se usa
    `pendiente_NE_pct` en lugar de `pendiente_max_pct`. Se evalúa **por lado**.

    La porción convexa que se usa para despejar el Δz es **siempre la de la
    SUBCRESTA**, se lo pregunte quien se lo pregunte. La cota de coronación es
    una propiedad del FILO, no de la línea que consulta: si cada línea usara la
    suya, la vaguada —que tiene el tramo convexo más corto— pediría una cota
    MÁS ALTA que la subcresta de al lado (`Δz = s_max·(D − lc/2 − lf/2)` crece
    al menguar `lc`), justo lo contrario de lo que tiene que pasar. Medido con
    los ajustes del Ej_2 y D = 70 m: subcresta 12.71 m, vaguada 15.68 m.

    La depresión de la vaguada NO sale de coronar más abajo: sale de que su
    perfil, con el MISMO desnivel y los mismos extremos, cae más deprisa
    [LIBRO fig. 8-11, p. 204]. Con esos números, hasta 1.28 m más a media
    ladera.

    `convexo` permite forzar esa longitud (una función de la distancia o un
    número); si no se pasa, se calcula con `convexo_subcresta` a partir de los
    ajustes del canal más próximo, que es lo correcto por defecto.

    Continuidad con el relieve existente: dentro de la banda de mezcla junto
    al límite GeoFluv la cota de diseño se funde progresivamente con la del
    DEM, de modo que en el propio límite la cresta coincide con el terreno
    (sin escalones entre lo diseñado y lo existente)."""
    # El resguardo mínimo de 0.25 m es porque donde las divisorias mueren en
    # las confluencias la distancia tiende a 0, y sin él la cresta puede quedar
    # por debajo del lecho y crear charcos espurios en el TIN.
    lados = lados_de_un_punto(pt, disenos, geoms, s_max, glob=glob,
                              convexo=convexo, n=n_lados)
    z = techo_de_ladera(lados)
    if z is None:
        return None
    g = QgsGeometry.fromPointXY(QgsPointXY(pt[0], pt[1]))
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
    """Voronoi de las LÍNEAS DE VALLE → disolución por canal → recorte al límite.
    Devuelve dict nombre → QgsGeometry (polígono de subcuenca).

    La fuente de puntos es `_capa_puntos_valle` y no el eje sinuoso; el porqué,
    con las medidas, está en su docstring (B-045). El cambio de partición mueve
    el área de cada cuenca entre −1.21 % y +1.97 % en el Ej_2 (rejilla de 2 m
    dentro del límite), y como `Qpk` es proporcional al área, el efecto
    hidráulico es de ese orden: despreciable.

    `drainage_density` se calcula con `d.L_valle`, que es lo que pide el método
    —«valley length **without meanders**», NRM p. 22— y ya era así."""
    from qgis import processing
    pts = _capa_puntos_valle(disenos, crs)
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
def _xy(p):
    """Las coordenadas de un punto, venga como venga.

    En este módulo conviven dos representaciones: `QgsPointXY`, que es lo que
    devuelven `asPolyline()`/`asMultiPolyline()` y se lee con `.x()`/`.y()`, y
    la tupla plana `(x, y)` que usan el resto de funciones. Se parecen lo
    bastante para engañar —ambas admiten `p[0]` y `p[1]`, `len(p)` y el
    desempaquetado `x, y = p`— pero **el QgsPointXY no admite rebanadas**:
    `p[:2]` lanza TypeError. Ver B-044.

    Este es el único sitio donde vive esa diferencia."""
    x = getattr(p, "x", None)
    if callable(x):
        return (p.x(), p.y())
    return (p[0], p[1])


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
    divisoria.

    **Se ha revisado al cambiar la fuente a la línea de valle (B-045) y se deja
    como está, a propósito.** Con muestras a 1 m y cauces separados ~65 m, la
    amplitud de la escalera vale ~h²/8d ≈ 0.002 m, así que ya casi no hay nada
    que quitar; pero el filtro tampoco estorba: la cadena que llega aquí tiene
    los vértices a ~1 m, o sea que la ventana ±2 son ±2 m y tres pasadas
    equivalen a ±3.5 m. El sesgo hacia el interior de una curva es d²/8R, o sea
    0.32 m en el radio más cerrado que tiene el original (19 m) y 0.02 m en el
    típico (200 m). Bajar las pasadas es una decisión que hay que tomar
    **midiendo en QGIS**, no a ojo: es exactamente el error de P-22."""
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
    """Anclas `(x, y, z, pareja)` donde cada tributario se une a su receptor.

    La divisoria entre dos cuencas contiguas MUERE justo ahí: aguas abajo de
    la confluencia ya no hay dos cuencas que separar. Por eso la cresta tiene
    que terminar en ese punto exacto, en planta y en cota.

    **`pareja` es la corrección de B-046**, y es lo único que faltaba. Esto
    devolvía `(x, y, z)` a secas, así que `_partir_en_confluencias` no tenía
    forma de saber **de qué dos cauces** era cada confluencia y partía la cadena
    en la primera que le cayera dentro de la tolerancia — 50 m en el Ej_2.
    Resultado: cadenas cortadas por confluencias **ajenas**. La prueba es que la
    cota del corte coincidía a seis decimales con el lecho de una confluencia
    situada a 33–38 m que no era de los dos cauces que esa divisoria separa:

        cresta 5.fin ≡ cresta 6.ini = (719670.09, 4408225.34, 289.091453)
            confluencia de main L1 a 38.28 m, z de lecho = 289.091453
            …pero esa cadena separa main | main R1

    Con la pareja, una confluencia solo parte la cadena donde la cadena separa
    **precisamente esos dos** cauces."""
    out = []
    for d in disenos.values():
        padre = getattr(d, "padre", "")
        if padre and d.puntos:
            x, y, z, _ = d.puntos[-1]
            out.append((x, y, z, frozenset((d.nombre, padre))))
    return out


def cortes_con_cauces(dens, disenos, geoms):
    """Anclas `(x, y, z, None)` donde la cadena de divisoria CRUZA un cauce.

    Una divisoria no puede atravesar un canal: al llegar al cauce la divisoria
    se ha acabado, porque al otro lado del agua empieza otra ladera de otra
    cuenca. La frontera de Voronoi sí puede cruzarlo (es un lugar geométrico,
    no una forma del terreno), y cuando lo hacía salía una cresta que pasaba
    por encima del canal principal. Aquí se localizan esos cruces para partir
    la cadena en ellos, con la cota del cauce en el punto de cruce.

    La `pareja` va a `None` **a propósito**: un cruce con un cauce parte la
    cadena siempre, sin comprobar nada. No es una confluencia entre dos cuencas,
    es agua en medio (ver B-046 y `puntos_confluencia`)."""
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
            cortes.append((pt.x(), pt.y(), d.puntos[i][2], None))
    return cortes


LARGO_TANGENTE = 5.0 * PASO_CRESTA   # m sobre los que se mide la dirección de
                                     # salida de un arco. Atado al paso de
                                     # vértices y no a un número de metros: lo
                                     # que hay que promediar es el ruido del
                                     # densificado, que `_densificar_xy` deja
                                     # entre PASO_CRESTA y 2·PASO_CRESTA, y
                                     # `_suavizar_xy` mueve sobre ±2 vértices.
TOL_NUDO = 0.4 * PASO_CRESTA         # m para dar dos extremos por coincidentes.
                                     # En un nudo son literalmente el mismo
                                     # vértice de Voronoi, así que basta con
                                     # absorber el ruido de las operaciones
                                     # geométricas intermedias.


MARGEN_CONFLUENCIA = 4.0 * PASO_CRESTA   # m desde un extremo por debajo de los
                                         # cuales una confluencia no parte la
                                         # cadena, solo la recorta


def _indice_a(pts, largo):
    """Primer índice que queda a `largo` metros de ARCO del inicio."""
    acc = 0.0
    for k in range(1, len(pts)):
        acc += math.hypot(pts[k][0] - pts[k - 1][0], pts[k][1] - pts[k - 1][1])
        if acc >= largo:
            return k
    return max(1, len(pts) - 1)


def _tangente(pts, desde_el_final, largo=LARGO_TANGENTE):
    """Dirección con la que un arco SALE de uno de sus extremos.

    Se mide sobre `largo` metros de arco, no sobre un número de vértices: el
    espaciado real de una frontera de Voronoi va de `PASO_CRESTA` a el doble, y
    contar vértices da direcciones que dependen de dónde cayeron."""
    seq = pts[::-1] if desde_el_final else pts
    acc = 0.0
    j = len(seq) - 1
    for k in range(1, len(seq)):
        acc += math.hypot(seq[k][0] - seq[k - 1][0], seq[k][1] - seq[k - 1][1])
        if acc >= largo:
            j = k
            break
    dx, dy = seq[j][0] - seq[0][0], seq[j][1] - seq[0][1]
    L = math.hypot(dx, dy) or 1.0
    return dx / L, dy / L


def encadenar_arcos(arcos, tol=TOL_NUDO, largo_tangente=LARGO_TANGENTE):
    """Cose los arcos de frontera que comparten extremo en CADENAS continuas.

    Las subcuencas se comparan por parejas, así que un punto donde se tocan tres
    de ellas —un vértice del diagrama de Voronoi— produce **tres arcos sueltos**
    que terminan exactamente ahí, calculados en tres iteraciones distintas y sin
    ninguna comunicación entre ellas. Eso deja extremos que mueren en el aire,
    que no existen en la salida del original: sus divisorias van siempre de
    borde a confluencia. Ver B-040.

    En un nudo de grado 3 hay que elegir cuáles dos continúan, y el criterio es
    el **giro**: sigue la pareja cuyas tangentes de salida están más enfrentadas,
    porque una divisoria real no gira 120° en un nudo. Es el mismo criterio de
    coseno que ya usa `_salir_por_bisectriz`. Medido sobre el Ej_2, los cuatro
    nudos se resuelven con desviaciones de la recta de 5°, 13°, 25° y 25°, y las
    trece piezas salen como las **siete cadenas** del original, con sus
    longitudes: 461/454, 399/397, 389/384, 325/325, 234/238, 197/188, 116/118.

    `QgsGeometry.mergeLines()` no sirve para esto: solo funde nodos de grado 2 y
    en un punto triple deja los tres arcos.

    Acepta arcos de `QgsPointXY` (lo que da `_cadenas_continuas`) o de tuplas, y
    devuelve SIEMPRE listas de (x, y): normaliza en la entrada. Esta función se
    intercaló entre la fuente de puntos y `_densificar_xy`, que era el único
    normalizador del camino, y se escribió contra el tipo que circula DESPUÉS de
    normalizar; por eso reventaba en QGIS y no en los tests (B-044).

    No filtra por longitud: eso va después, sobre la cadena, porque descartar un
    arco corto ANTES partiría la cadena por el medio y crearía dos extremos
    nuevos en el aire."""
    arcos = [[_xy(p) for p in arco] for arco in arcos]
    ext = []          # (indice de arco, 0=inicio | 1=final)
    for k in range(len(arcos)):
        ext.append((k, 0))
        ext.append((k, 1))

    def pto(e):
        return arcos[e[0]][0] if e[1] == 0 else arcos[e[0]][-1]

    # nudos: extremos que caen en el mismo sitio
    nudos = []
    visto = set()
    for a in range(len(ext)):
        if a in visto:
            continue
        grupo = [a]
        for b in range(a + 1, len(ext)):
            if b in visto:
                continue
            if math.dist(pto(ext[a]), pto(ext[b])) <= tol:
                grupo.append(b)
                visto.add(b)
        visto.add(a)
        if len(grupo) > 1:
            nudos.append([ext[g] for g in grupo])

    # en cada nudo, la pareja MÁS ENFRENTADA continúa; el resto queda suelto
    sigue = {}
    for grupo in nudos:
        mejor = None
        for a in range(len(grupo)):
            for b in range(a + 1, len(grupo)):
                ta = _tangente(arcos[grupo[a][0]], grupo[a][1] == 1,
                               largo_tangente)
                tb = _tangente(arcos[grupo[b][0]], grupo[b][1] == 1,
                               largo_tangente)
                # enfrentadas = coseno -1; se mide lo que se desvía de eso
                cos = ta[0] * tb[0] + ta[1] * tb[1]
                if mejor is None or cos < mejor[0]:
                    mejor = (cos, grupo[a], grupo[b])
        if mejor is not None:
            sigue[mejor[1]] = mejor[2]
            sigue[mejor[2]] = mejor[1]

    cadenas, usados = [], set()
    for k in range(len(arcos)):
        if k in usados:
            continue
        # se arranca por un extremo LIBRE si lo hay; si no, es un ciclo
        arranque = None
        for e in ((k, 0), (k, 1)):
            if e not in sigue:
                arranque = (k, 1 - e[1])
                break
        if arranque is None:
            arranque = (k, 1)
        pts, ki, salida = [], k, arranque[1]
        while True:
            if ki in usados:
                break
            usados.add(ki)
            tramo = arcos[ki] if salida == 1 else arcos[ki][::-1]
            pts.extend(tramo if not pts else tramo[1:])
            sig = sigue.get((ki, salida))
            if sig is None or sig[0] in usados:
                break
            ki, salida = sig[0], 1 - sig[1]
        if len(pts) >= 2:
            cadenas.append(pts)
    return cadenas


MARGEN_TERCER_CAUCE = 1.0    # m; por debajo de esta diferencia entre el segundo
                             # y el tercer cauce más próximos, el punto es un
                             # NUDO TRIPLE y no se puede decir qué dos cuencas
                             # separa. Ver `_separa` y B-050.
TOL_LIMITE_DIVISORIA = 3.0   # m; las cadenas nacen a 0.5 m del contorno porque
                             # `banda_limite` es `contorno.buffer(0.5)`, así que
                             # basta con absorber ese medio metro y el ruido de
                             # las operaciones geométricas


def toca_el_limite(rama, contorno, tol=TOL_LIMITE_DIVISORIA):
    """¿Tiene esta cadena UN EXTREMO sobre el límite del proyecto?

    Es el criterio que distingue una divisoria principal de un brazo suelto, y
    es **topológico, no de longitud** (B-046, segunda mitad).

    Una divisoria separa dos subcuencas: nace en la confluencia donde sus dos
    aguas se juntan y se aleja de ella hasta salirse del área de diseño. El
    extremo de dentro puede morir en una confluencia, en un cruce con un cauce o
    contra otra divisoria; el de fuera **siempre** llega al límite. Lo que no
    existe es una divisoria con los dos extremos en el interior: eso es el brazo
    sobrante de un nudo triple, donde `encadenar_arcos` cose la pareja más
    enfrentada y deja el tercero suelto.

    **Verificado sobre la salida del original, Ej_2**: sus **siete** divisorias
    tienen un extremo a 0.00 m del límite y el otro a 70-135 m. Y aplicado a
    nuestras diez, se queda con siete y tira las tres que no lo son (97.1, 42.1
    y 40.4 m), cuyos extremos equidistan de **tres** cauces — la definición de
    vértice de Voronoi.

    **Por qué no un umbral de longitud**: la divisoria legítima más corta del
    original mide **25.0 m**, que es justo el valor de `divides.min_divisoria`.
    Cualquier umbral que matara los brazos de 40 m mataría también divisorias
    buenas, y ya se intentó una vez (P-22).
    """
    if len(rama) < 2:
        return False
    for x, y in (rama[0], rama[-1]):
        if contorno.distance(QgsGeometry.fromPointXY(QgsPointXY(x, y))) <= tol:
            return True
    return False


def _separa(dens, i, pareja, geoms):
    """¿La cadena separa, en su vértice `i`, exactamente los cauces de `pareja`?

    `geoms` son los ejes por nombre. Los dos cauces más próximos a un punto de
    una divisoria de Voronoi son, por definición, las dos cuencas que esa
    divisoria separa ahí. Si no coinciden con la pareja de la confluencia, esa
    confluencia es de otros dos cauces y no tiene por qué partir esta cadena.

    Sin `geoms` no se puede comprobar y se deja pasar: es el comportamiento
    anterior, que es el que hay que conservar para quien llame sin ellos."""
    if not geoms or pareja is None:
        return True
    x, y = dens[i][0], dens[i][1]
    g = QgsGeometry.fromPointXY(QgsPointXY(x, y))
    d = sorted(((ge.distance(g), n) for n, ge in geoms.items()))
    if len(d) > 2 and d[2][0] - d[1][0] < MARGEN_TERCER_CAUCE:
        # NUDO TRIPLE: el tercer cauce está tan cerca como el segundo, así que
        # «los dos que separa» es una moneda al aire y la respuesta no significa
        # nada. Medido en el Ej_2, el corte que quedaba caía en un punto a
        # 42.61 / 42.76 / 42.78 m de main, main R2 y main R3 —dos centímetros de
        # diferencia entre el segundo y el tercero— y ahí partía la cadena por
        # una confluencia que estaba a 49 m. El original no parte ninguna de sus
        # siete a más de 20.1 m de la suya. Ver B-050.
        return False
    return frozenset(n for _d, n in d[:2]) == pareja


def _partir_en_confluencias(dens, confluencias, tol, geoms=None):
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
    for cx, cy, cz, pareja in confluencias:
        for i, (x, y) in enumerate(dens):
            dd = math.hypot(x - cx, y - cy)
            if dd >= tol or (mejor is not None and dd >= mejor[0]):
                continue
            # B-046: una confluencia solo parte la cadena si la cadena separa
            # PRECISAMENTE esos dos cauces en ese punto. Sin esto, con `tol` de
            # 50 m, una confluencia ajena a 33-38 m partía la divisoria por el
            # medio: medido en el Ej_2, dos de las siete cadenas salían en dos
            # trozos, y la cota del corte era la del lecho de una confluencia
            # que no era la suya. `pareja is None` = cruce con un cauce, que
            # parte siempre (ver `cortes_con_cauces`).
            if pareja is not None and not _separa(dens, i, pareja, geoms):
                continue
            mejor = (dd, i, (cx, cy, cz, pareja))
    if mejor is None:
        return [(dens, None)]
    _, i, (cx, cy, cz, _pareja) = mejor
    # Margen para decidir si la confluencia cae «en el interior» —y entonces se
    # PARTE en dos crestas— o «junto a un extremo» —y entonces se recorta—.
    # Era `max(2, int(0.08 * len(dens)))`, una fracción del NÚMERO DE VÉRTICES:
    # con los arcos sueltos de antes eran dos vértices, o sea 10-20 m, pero al
    # emitir cadenas enteras (B-040) las líneas son cuatro veces más largas y
    # ese 8 % pasaba a valer 40-80 m, con lo que una confluencia legítima cerca
    # del arranque hacía descartar decenas de metros de divisoria buena. En
    # longitud de arco no crece con la cadena.
    margen = _indice_a(dens, MARGEN_CONFLUENCIA)
    margen = max(2, min(margen, (len(dens) - 1) // 2))
    # --- la confluencia cae en el INTERIOR: la cadena se PARTE en dos crestas
    if margen <= i <= len(dens) - 1 - margen:
        # OJO: la confluencia NO se inserta en la planta. Aquí se hacía
        # `dens[:i] + [(cx, cy)]`, y como `i` es el vértice de MÍNIMA DISTANCIA
        # —o sea el pie de la perpendicular—, el segmento nuevo salía
        # perpendicular a la traza y podía medir hasta `tol` = 50 m. Eso es el
        # gancho de P-27: medido en el Ej_2, nuestras divisorias giraban hasta
        # 104° en sus últimos 20 m y las del original no pasan de 33°.
        # Lo que da las DOS crestas de ADR-003 es el CORTE, no el punto
        # insertado; la confluencia se conserva como ancla de COTA, que es para
        # lo que hace falta. Y esos metros los recorta después
        # `divides.recortar_contra_corredor` de todas formas.
        rama_a = list(dens[:i + 1])
        rama_b = list(dens[i:])
        salida = []
        # cada rama se vuelve a examinar por si hay más puntos de anclaje
        # (una cadena larga puede cruzar varios cauces)
        restantes = [c for c in confluencias
                     if math.hypot(c[0] - cx, c[1] - cy) > tol]
        for rama, extremo in ((rama_a, "fin"), (rama_b, "ini")):
            if len(rama) < 3:
                continue
            sub = _partir_en_confluencias(rama, restantes, tol, geoms)
            if len(sub) == 1 and sub[0][1] is None:
                salida.append((rama, (extremo, cz)))
            else:
                salida.extend(sub)
        return salida or [(dens, None)]
    # --- la confluencia cae junto a un extremo: solo se ancla la COTA de ese
    # extremo, y tampoco aquí se inserta el punto en la planta (mismo motivo)
    if i <= len(dens) / 2:
        nueva = list(dens[i:])
        return [(nueva if len(nueva) >= 3 else dens, ("ini", cz))]
    nueva = list(dens[:i + 1])
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


def _salir_por_bisectriz(dens, anclaje, bisectrices, largo=None, radio=None):
    """Rehace el arranque de una cresta anclada en una confluencia para que
    salga por la bisectriz, y lo funde con el resto de la cadena.

    La frontera de Voronoi da bien el recorrido lejano, pero junto a la unión
    de los cauces se retuerce; el original sale recto por la bisectriz y luego
    se curva. Se sustituyen los primeros 'largo' metros por el segmento de la
    bisectriz más próxima y se mezcla con la traza original."""
    if not anclaje or not bisectrices or len(dens) < 4:
        return dens
    # `largo` y `radio` eran 30.0 y 3.0*PASO_CRESTA, dos constantes sin cita.
    # Se atan a la distancia cresta-cabecera de canal (xrh), que es el ajuste
    # del método que gobierna esta escala [LIBRO p. 189] y que el llamante ya
    # usa para `tol_conf` y `long_min`.
    if largo is None:
        largo = 30.0
    if radio is None:
        radio = 3.0 * PASO_CRESTA
    extremo, _z = anclaje
    puntos = list(dens) if extremo == "ini" else list(dens)[::-1]
    ini = puntos[0]
    # bisectriz de la confluencia más próxima y con la dirección más parecida
    ref = None
    for b in bisectrices:
        if math.hypot(b["xy"][0] - ini[0], b["xy"][1] - ini[1]) > radio:
            continue
        # hacia dónde va la cadena en sus primeros metros. Por LONGITUD DE ARCO,
        # no por índice: `int(largo / PASO_CRESTA)` suponía un espaciado de 5 m
        # exactos que `_densificar_xy` no garantiza —deja entre 5 y 10— y que
        # `_suavizar_xy` altera además de forma desigual. La dirección de prueba
        # salía medida a una distancia que podía ser el doble de la pedida.
        vx, vy = _tangente(puntos, False, largo)
        for dx, dy in b["dirs"]:
            cos = vx * dx + vy * dy
            if ref is None or cos > ref[0]:
                ref = (cos, (dx, dy))
    # `ref[0]` es el coseno entre la traza y la bisectriz. La guarda era
    # `< 0.2`, y cos(90°) = 0 < 0.2: descartaba EXACTAMENTE los arranques a
    # noventa grados que esta función existe para enderezar. Ahora solo se
    # rinde si la cadena va en sentido CONTRARIO a la bisectriz, que es el caso
    # legítimo de haber elegido la bisectriz o la confluencia equivocada.
    if ref is None or ref[0] <= 0.0:
        return dens
    # La mezcla también va por LONGITUD DE ARCO. Aquí estaba el defecto de
    # fondo: el rayo avanzaba `PASO_CRESTA` exactos por índice y la cadena entre
    # 5 y 10 m, así que al mezclarlos por el mismo índice se restaban dos
    # parametrizaciones distintas. Sus dos firmas son las que se midieron: el
    # espaciado colapsaba a fracciones de metro en el centro del smoothstep, y
    # con la cadena corriendo más que el rayo el avance se invertía. Con la
    # estación real de cada vértice, el rayo y la traza hablan del mismo punto.
    dx, dy = ref[1]
    s = [0.0]
    for a, b in zip(puntos[:-1], puntos[1:]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    nuevos = []
    for si, pt in zip(s, puntos):
        if si > largo:
            nuevos.append(pt)
            continue
        w = si / largo              # 0 en la confluencia, 1 al final del tramo
        w = w * w * (3 - 2 * w)
        rx = ini[0] + dx * si
        ry = ini[1] + dy * si
        nuevos.append((rx * (1 - w) + pt[0] * w, ry * (1 - w) + pt[1] * w))
    return nuevos if extremo == "ini" else nuevos[::-1]


def generar_crestas(disenos, subcuencas, g_lim, glob, dem, lm):
    """GRD_Ridges = CRESTAS DIVISORIAS entre subcuencas.

    Dos cuencas contiguas solo pueden estar separadas por una CRESTA: lo que
    cae en una ladera va a un canal y lo que cae en la otra al otro. Por eso
    esta línea no se adapta al terreno original: es una divisoria de DISEÑO,
    continua desde la confluencia hasta el límite GeoFluv.

    Su cota es una curva vertical entre las cotas de sus dos extremos, acotada
    por arriba por la pendiente de ladera que dejan sus DOS cauces y por abajo
    por sus lechos. Hasta la v1.0.21 era al revés —la cota «nunca bajaba» de la
    de cresta de diseño, o sea un SUELO—, y eso convertía el perfil en la
    envolvente superior de una función a trozos. Ver `_perfil_cresta`.

    Devuelve `(n, crestas_3d, peor_exceso)`, donde `peor_exceso` es cuánto
    rebasa el techo de ladera la peor cresta: con los dos extremos anclados la
    curva está determinada y el exceso se INFORMA, no se recorta.
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
    peor_exceso = 0.0       # cuánto rebasa el techo de ladera la peor cresta
    confluencias = puntos_confluencia(disenos)
    bisectrices = bisectrices_confluencia(disenos)
    tol_conf = max(3.0 * PASO_CRESTA, glob.max_dist_cresta_cabecera)

    capa = lm.obtener_capa("GRD_Ridges")
    capa.dataProvider().truncate()
    feats = []
    crestas_3d = []      # [(QgsGeometry 2D, [z por vértice])] para subcrestas
    arcos = []           # fronteras de cada pareja, ANTES de encadenar
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
            # Solo se RECOGEN. Encadenar exige ver todas las fronteras a la vez:
            # un punto donde se tocan tres subcuencas se calcula en tres
            # iteraciones distintas de este bucle, y desde dentro no hay forma
            # de saber que son el mismo nudo. Ver B-040.
            for pts in _cadenas_continuas(inter):
                if len(pts) >= 2:
                    arcos.append(pts)

    # --- de arcos de pareja a CADENAS de borde a confluencia ---
    for dens in encadenar_arcos(arcos):
        dens = _densificar_xy(dens, PASO_CRESTA)
        largo = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                    for a, b in zip(dens[:-1], dens[1:]))
        # El filtro va sobre la CADENA, no sobre el arco: descartar un arco
        # corto antes de encadenar partiría la cadena por el medio y dejaría dos
        # extremos nuevos en el aire. Y aplicado aquí cae solo el brazo sobrante
        # de cada nudo triple, que es lo que el original tampoco tiene.
        if largo < long_min:
            continue            # esquirla de Voronoi, no es una divisoria
        dens = _suavizar_xy(dens)
        # La divisoria PASA por la confluencia (se parte en dos crestas)
        # y NUNCA puede atravesar un cauce: los cruces con cualquier eje
        # de canal son también puntos de corte.
        anclas = list(confluencias) + cortes_con_cauces(dens, disenos, geoms)
        for rama, anclaje in _partir_en_confluencias(
                dens, anclas, tol_conf, geoms):
            largo_r = sum(math.hypot(b[0] - a[0], b[1] - a[1])
                          for a, b in zip(rama[:-1], rama[1:]))
            if largo_r < 0.5 * long_min:
                continue
            if not toca_el_limite(rama, contorno):
                continue            # brazo interior de un nudo triple
            rama = _salir_por_bisectriz(
                rama, anclaje, bisectrices,
                largo=glob.max_dist_cresta_cabecera,
                radio=tol_conf)
            linea, _zs, diag = _perfil_cresta(
                rama, disenos, geoms, s_max, dem, glob, contorno,
                anclaje=anclaje)
            if diag["exceso_techo"] > peor_exceso:
                peor_exceso = diag["exceso_techo"]
            f = QgsFeature(capa.fields())
            f.setGeometry(QgsGeometry.fromPolyline(linea))
            # Una cadena atraviesa varios nudos y separa cuencas distintas en
            # tramos distintos, así que «cresta A | B» ya no la describe. Se
            # numeran, que además arregla que hasta ahora dos entidades podían
            # salir con el MISMO nombre.
            f.setAttributes(attrs(capa, ["cresta %d" % (len(feats) + 1)]))
            feats.append(f)
            crestas_3d.append(traza_y_cotas(linea))
    capa.dataProvider().addFeatures(feats)
    capa.updateExtents(); capa.triggerRepaint()
    return len(feats), crestas_3d, peor_exceso


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
    def alza_de_pie(pt):
        """Cuánto sube la divisoria sobre la RASANTE en su pie (B-051).

        El pie de una divisoria no está en el agua: en el original arranca a
        **2.5–7.2 m del eje** del cauce, o sea ya subido por la ladera, y su cota
        va de **+0.60 a +2.63 m** sobre la rasante (mediana +1.68). Nosotros
        anclábamos ese extremo a la cota del lecho en el punto de confluencia y
        salía entre −0.47 y +0.50, con **cinco de siete por debajo del lecho**:
        una divisoria por debajo del agua que separa no separa nada.

        La cota que le corresponde es la misma ecuación que rige todo el relieve
        de ladera, `desnivel_de_ladera`, evaluada a la distancia real del pie al
        cauce. No es una constante nueva ni un resguardo: es la cota de cresta
        que toca a ese punto. El 0.25 de antes se queda como suelo."""
        lados = lados_de_un_punto((pt[0], pt[1]), disenos, geoms, s_max,
                                  glob=glob)
        if not lados:
            return 0.25
        D_pie, _z, s_pie, lc_pie = min(lados, key=lambda t: t[0])
        return max(desnivel_de_ladera(D_pie, s_pie, lc_pie), 0.25)

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
            return d.puntos[i][2] + alza_de_pie(pt), "confluencia"
        return (_z_ladera(pt, disenos, geoms, s_max, dem, False,
                          glob=glob), "cresta")

    zA, tipoA = z_extremo(dens[0])
    zB, tipoB = z_extremo(dens[-1])
    # extremo anclado a una confluencia: manda la cota del cauce en ese punto,
    # SUBIDA lo que sube la ladera desde el agua hasta donde muere la divisoria
    if anclaje:
        donde, z_conf = anclaje
        if donde == "ini":
            zA, tipoA = z_conf + alza_de_pie(dens[0]), "confluencia"
        else:
            zB, tipoB = z_conf + alza_de_pie(dens[-1]), "confluencia"
    # orientar del extremo ALTO al bajo para el perfil
    if zB > zA:
        dens = dens[::-1]
        zA, zB = zB, zA
        tipoA, tipoB = tipoB, tipoA
    s = [0.0]
    for a, b in zip(dens[:-1], dens[1:]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    D = max(s[-1], 1e-6)
    lc = convexo_cresta(glob, D)

    # --- techo y suelo de ladera, continuos, con los DOS cauces de cada punto
    lados = [lados_de_un_punto((pt[0], pt[1]), disenos, geoms, s_max,
                               glob=glob)
             for pt in dens]
    techo = [techo_de_ladera(ld) for ld in lados]
    suelo = [suelo_de_cresta(ld) for ld in lados]

    # --- forma: UNA curva vertical, `f` de 0 a 1 del extremo alto al bajo
    # (LIBRO p. 156 «any yellow MAIN- or sub-ridge polylines… complex slopes»;
    # MANUAL p. 1752 «constructing a vertical curve»). `perfil_trapezoidal` es
    # lineal en el desnivel, así que la curva es la combinación convexa de las
    # dos cotas extremas y el extremo libre se despeja de una vez.
    # `lf = 0`: la divisoria NO lleva pie cóncavo. Ese tramo existe donde una
    # ladera se tumba al llegar al fondo del valle, y una divisoria no llega al
    # fondo: muere sobre el filo, por encima del agua. Ajustado sobre las siete
    # del original, `lf/L` sale **0.000**; `tramos_de_ladera` lo acota a 0.5 m,
    # que es lo que se quiere, no cero exacto.
    # Con el `lf = min(lc, 0.30·D)` por defecto salía un pie cóncavo de **75 m**
    # en una divisoria de 436, y eso es lo que aplanaba el arranque: al 10 % del
    # recorrido habíamos ganado 0.055 del desnivel y el original 0.119.
    # OJO: esto vale para la DIVISORIA, no para subcrestas ni vaguadas, que sí
    # tienen pie cóncavo medido (57 perfiles del DXF de referencia).
    f = [perfil_trapezoidal(si, D, 1.0, lc, lf=0.0) for si in s]

    # --- un extremo LIBRE se resuelve contra el techo Y el suelo; uno anclado
    # manda. Los dos entran como COTAS DEL EXTREMO, nunca punto a punto: ese
    # era el fallo de la v1.0.22 (B-038).
    if tipoA == "cresta" and tipoB != "cresta":
        cand = resolver_extremo_libre(f, techo, zB, True, suelo=suelo)
        if cand is not None:
            zA = cand
    elif tipoB == "cresta" and tipoA != "cresta":
        cand = resolver_extremo_libre(f, techo, zA, False, suelo=suelo)
        if cand is not None:
            zB = cand
    elif tipoA == "cresta" and tipoB == "cresta":
        for k, z in ((0, zA), (-1, zB)):
            v = z
            if techo[k] is not None:
                v = min(v, techo[k])
            if suelo[k] is not None:
                v = max(v, suelo[k])
            if k == 0:
                zA = v
            else:
                zB = v
    if zB > zA:                       # la resolución puede invertir el sentido
        zA, zB = zB, zA
        dens, f, techo, suelo = dens[::-1], [1.0 - x for x in f[::-1]], \
            techo[::-1], suelo[::-1]

    zs = [zA * (1.0 - fk) + zB * fk for fk in f]

    # Ni el techo ni el suelo se aplican punto a punto: los dos se INFORMAN.
    # El suelo lo hacía hasta la v1.0.22, y era el deformador dominante — con
    # `max` sobre una pareja de cauces que cambia de miembros, escribía saltos
    # de hasta 15.80 m y mandaba en el 40.9 % de los vértices. Ahora acota el
    # extremo libre, que es donde no puede escribir escalones (B-038).
    # Y con los dos extremos anclados la curva está DETERMINADA: el mando del
    # método para un exceso es mover la divisoria en planta (LIBRO p. 180
    # §7.4.3), no retocarle la cota.
    peor = peor_suelo = 0.0
    for z, tk, su in zip(zs, techo, suelo):
        if tk is not None and z - tk > peor:
            peor = z - tk
        if su is not None and su - z > peor_suelo:
            peor_suelo = su - z
    diag = {"exceso_techo": peor, "bajo_suelo": peor_suelo,
            "anclas": (tipoA, tipoB), "L": D}
    linea = [QgsPoint(pt[0], pt[1], z) for pt, z in zip(dens, zs)]
    return linea, zs, diag


def _densificar_xy(pts, paso):
    """Vértices cada `paso` metros. Acepta QgsPointXY o tuplas (ver `_xy`)."""
    pts = [_xy(p) for p in pts]
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(d // paso))
        for k in range(1, n + 1):
            t = k / n
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
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
