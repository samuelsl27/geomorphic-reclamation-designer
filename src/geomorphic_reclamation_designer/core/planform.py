# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Geometría en planta de los canales.

- Tramos de fondo de valle (|s| < 4 %): trazado sinusoidal (meandros) alrededor
  de la polilínea de fondo de valle, con longitud de meandro y cinturón ligados
  al caudal bankfull (relaciones de Williams, 1986) y amplitud resuelta para
  alcanzar la sinuosidad objetivo. Las dimensiones crecen aguas abajo con el
  caudal. Con 'factores aleatorios' se varían ligeramente para un aspecto
  más natural.
- Tramos empinados tipo A (|s| > 4 %): trazado en zigzag de baja sinuosidad
  (< 1.2) con media longitud de meandro igual al 'reach' de canal A.

Todo se calcula sobre la polilínea 2D del fondo de valle parametrizada por
longitud de arco; el desplazamiento se aplica sobre la normal local suavizada.
"""

import math
import random


# ---------------- utilidades de polilínea ----------------

def densificar(pts, paso):
    """Densifica [(x,y),...] cada 'paso' m. Devuelve [(s, x, y)]."""
    out = []
    if len(pts) < 2:
        return out
    s_acum = 0.0
    out.append((0.0, pts[0][0], pts[0][1]))
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        dx, dy = x1 - x0, y1 - y0
        d = math.hypot(dx, dy)
        if d < 1e-9:
            continue
        n = max(1, int(d // paso))
        for j in range(1, n + 1):
            t = j / n
            out.append((s_acum + t * d, x0 + t * dx, y0 + t * dy))
        s_acum += d
    return out


def tangentes_suaves(dens, ventana=5):
    """Tangente unitaria suavizada en cada punto densificado (media móvil)."""
    n = len(dens)
    tg = []
    for i in range(n):
        i0 = max(0, i - ventana)
        i1 = min(n - 1, i + ventana)
        dx = dens[i1][1] - dens[i0][1]
        dy = dens[i1][2] - dens[i0][2]
        d = math.hypot(dx, dy) or 1.0
        tg.append((dx / d, dy / d))
    return tg


def _sinuosidad_de_a(a):
    """Sinuosidad de y = A·sin(2πx/λ) con a = 2πA/λ (integración numérica)."""
    n = 200
    tot = 0.0
    for i in range(n):
        u = (i + 0.5) * 2 * math.pi / n
        tot += math.sqrt(1 + a * a * math.cos(u) ** 2)
    return tot / n


def amplitud_para_sinuosidad(k, lam):
    """Amplitud A tal que la senoide de longitud de onda 'lam' tiene sinuosidad k."""
    if k <= 1.001:
        return 0.0
    lo, hi = 0.0, 12.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if _sinuosidad_de_a(mid) < k:
            lo = mid
        else:
            hi = mid
    a = (lo + hi) / 2
    return a * lam / (2 * math.pi)


def amplitud_triangular(k, lam):
    """Amplitud A de una onda TRIANGULAR (zigzag de los tramos A) de longitud
    de onda 'lam' con sinuosidad EXACTA k.

    En un cuarto de periodo la onda avanza lam/4 en planta y sube A, por lo que
    recorre sqrt((lam/4)² + A²) y la sinuosidad resulta

        k = sqrt(1 + (4A/lam)²)   ⇒   A = (lam/4)·sqrt(k² − 1)

    Hasta la v1.0.9 el zigzag usaba la amplitud de la SENOIDE, con lo que la
    sinuosidad real quedaba por debajo de la pedida (k=1.15 → 1.128 medido).
    """
    if k <= 1.0:
        return 0.0
    return (lam / 4.0) * math.sqrt(max(k * k - 1.0, 0.0))


# ---------------- trazado del canal ----------------

def trazar_canal(dens, perfil, s_transicion, q_en, settings_canal, settings_glob,
                 semilla=None):
    """Genera el eje del canal desplazando la línea de valle.

    dens: [(s, x, y)] del fondo de valle (s = 0 en cabecera).
    perfil: PerfilLongitudinal (cotas por estación de valle).
    s_transicion: estación de transición A→valle (None si no hay tramo A).
    q_en(s): función que devuelve el caudal bankfull (m3/s) en la estación s.
    Devuelve (puntos, sinuosidad_real) con puntos = [(x, y, z, s_valle)].
    """
    from .hydrology import geometria_meandro, ancho_bankfull
    from .params import UMBRAL_PENDIENTE

    if len(dens) < 2:
        return [], 1.0
    tg = tangentes_suaves(dens)
    rng = random.Random(semilla)
    usar_rand = settings_canal.factores_aleatorios

    k_A = min(settings_glob.sinuosidad_canal_A, settings_canal.sinuosidad_mayor_004)
    k_valle = settings_canal.sinuosidad_menor_004
    reach_A = max(settings_glob.reach_canal_A, 1.0)

    paso_dens = max((dens[1][0] - dens[0][0]) if len(dens) > 1 else 1.0, 0.25)

    # fase acumulada y factores aleatorios por meandro
    puntos = []
    fase = 0.0
    k_rc = 2.5            # radio de curvatura fijo 2.5·W (sin factores aleatorios)
    ciclo_previo = -1
    long_canal = 0.0
    px_prev = None

    for i, (s, x, y) in enumerate(dens):
        # variación aleatoria por ciclo de meandro: el radio de curvatura de
        # cada curva varía en el rango estable Rc = 2.5–3.2 × W bankfull
        # (Williams 1986); λ y el cinturón se derivan de Rc (regime equations)
        ciclo = int(fase / (2 * math.pi))
        if usar_rand and ciclo != ciclo_previo:
            k_rc = rng.uniform(2.5, 3.2)
            ciclo_previo = ciclo

        # Un tramo es de tipo A (zigzag) solo si está aguas arriba de la
        # transición Y la pendiente local supera realmente el 4 % (definición
        # del método: los canales A son los de |s| > 4 %). Antes bastaba con
        # estar aguas arriba del punto de transición, de modo que si el usuario
        # marcaba la transición con 'Pick' cerca de la boca TODO el canal se
        # dibujaba en zigzag y desaparecían los meandros (bug de la v1.0.9).
        pend_local = perfil.pendiente(s)
        en_tramo_A = (s_transicion is not None and s <= s_transicion
                      and abs(pend_local) > UMBRAL_PENDIENTE)
        if en_tramo_A:
            lam = 2.0 * reach_A                       # reach = ½ longitud de meandro
            amp = amplitud_triangular(k_A, lam)
        else:
            q = max(q_en(s), 1e-4)
            pend = perfil.pendiente(s)
            wd = settings_canal.wd_pend_mayor_004 if abs(pend) > UMBRAL_PENDIENTE \
                else settings_canal.wd_pend_menor_004
            w_bkf = ancho_bankfull(q, wd, settings_canal.vel_max_agua)
            lm, belt, _rc = geometria_meandro(w_bkf, k_rc)
            # la longitud de onda nunca por debajo de 6 pasos de densificado:
            # con menos vértices por meandro la polilínea "recorta" las curvas
            # y la sinuosidad dibujada queda muy por debajo de la calculada
            lam = max(lm, 6.0 * paso_dens, 4.0)
            amp = min(amplitud_para_sinuosidad(k_valle, lam),
                      max(belt - w_bkf, w_bkf) / 2.0)

        # avance de fase
        if i > 0:
            ds = s - dens[i - 1][0]
            fase += 2 * math.pi * ds / lam

        if en_tramo_A:
            # zigzag triangular: onda triangular de la fase
            tri = 2.0 * abs(2.0 * ((fase / (2 * math.pi)) % 1.0) - 1.0) - 1.0
            offset = amp * tri
        else:
            offset = amp * math.sin(fase)

        # Amortiguar el offset SOLO lo justo en los extremos (cabecera y boca)
        # y en el propio punto de transición, para no perder sinuosidad: antes
        # se amortiguaba media longitud de onda en cada extremo y un cuarto a
        # cada lado de la transición, lo que rebajaba visiblemente la
        # sinuosidad real del canal frente a la pedida.
        margen = min(s, perfil.L - s)
        rampa = min(1.0, margen / max(lam / 4.0, 1e-6))
        if s_transicion is not None:
            rampa = min(rampa, min(1.0, abs(s - s_transicion) / max(lam / 8.0, 1e-6)))
        offset *= max(rampa, 0.0)

        nx, ny = -tg[i][1], tg[i][0]   # normal (izquierda del avance)
        cx, cy = x + nx * offset, y + ny * offset
        z = perfil.z(s)
        if px_prev is not None:
            long_canal += math.hypot(cx - px_prev[0], cy - px_prev[1])
        px_prev = (cx, cy)
        puntos.append((cx, cy, z, s))

    L_valle = dens[-1][0] or 1.0
    return puntos, (long_canal / L_valle if L_valle > 0 else 1.0)


def bordes_canal(puntos, ancho_en, dz_en):
    """Genera dos polilíneas paralelas al eje a ±ancho/2 con Δz sobre el eje.

    puntos: [(x, y, z, s)] del eje. ancho_en(s), dz_en(s): funciones.
    Devuelve (izquierda, derecha) como listas [(x, y, z)].
    """
    izq, der = [], []
    n = len(puntos)
    for i in range(n):
        i0, i1 = max(0, i - 1), min(n - 1, i + 1)
        dx = puntos[i1][0] - puntos[i0][0]
        dy = puntos[i1][1] - puntos[i0][1]
        d = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / d, dx / d
        x, y, z, s = puntos[i]
        w2 = max(ancho_en(s), 0.05) / 2.0
        dz = dz_en(s)
        izq.append((x + nx * w2, y + ny * w2, z + dz))
        der.append((x - nx * w2, y - ny * w2, z + dz))
    return izq, der
