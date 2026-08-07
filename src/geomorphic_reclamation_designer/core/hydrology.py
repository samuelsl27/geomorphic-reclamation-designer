# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Hidrología e hidráulica del método fluvio-geomórfico (GeoFluv / Natural Regrade).

Cadena de cálculo por estación de canal (ver especificación en docs):

1.  Caudal punta por método racional:  Qpk = C · i · A / 360   [m3/s]
    - bankfull:    i = P(2 años, 1 h) en mm/h (evento formador del cauce).
    - flood-prone: i = P(50 años, 6 h) introducida ÍNTEGRA como intensidad
      horaria (criterio conservador de Natural Regrade: "coloca todo el
      volumen de la tormenta de 6 h en el canal instantáneamente").

2.  Sección bankfull (Dunne & Leopold 1978; Rosgen 1996): A = Q / v_max con
    trapecio simétrico de taludes interiores 4H:1V y ratio anchura:profundidad
    W:D fijado por el usuario según el tipo de canal (|s| >/< 4 %):
        W = wd · d ;  b = W − 2·z·d ;  A = d · (W − z·d)
    ⇒   d = sqrt(A / (wd − z)) , con z = 4.

3.  Sección flood-prone: mismo fondo b y mismos taludes z que la bankfull,
    resuelta para el área A_fp = Q_fp / v_max:
        z·d² + b·d − A_fp = 0  ⇒  d_fp = (−b + sqrt(b² + 4·z·A_fp)) / (2·z)
        W_fp = b + 2·z·d_fp
    El ratio de atrincheramiento (entrenchment ratio, Rosgen) = W_fp / W_bkf.

4.  Hidráulica de la sección (por estación):
        P = b + 2·d·sqrt(1+z²)   (perímetro mojado)
        R = A / P                (radio hidráulico)
        τ = γw · R · S           (tensión tractiva, N/m²)
    Estabilidad tractiva (Shields): τ_crit = θc · (γs − γw) · D50, θc = 0.045
    (régimen turbulento rugoso), D50 del conteo Wolman del área de referencia.

5.  Verificación con Manning (no altera el dimensionado NR):
        Q = (1/n) · A(d) · R(d)^(2/3) · S^(1/2)  → calado normal d_n (bisección)
        v_n = Q / A(d_n) ;  Froude F = v_n / sqrt(g · A/T)
    Avisos si v_n > v_max (sección se queda corta para esa pendiente) o si
    v_n < 0.4·v_max (posible sedimentación / v_max optimista).

6.  Geometría de meandro ligada a la anchura bankfull — ecuaciones de
    régimen de Williams (1986) tal y como las enuncia el libro (Geomorphic
    Reclamation Design 2024, cap. 2, 'Channel plan view geometry'):
        Rc = k · W        radio de curvatura, con k en [2.5, 3.2] («the radius
                          of curvature falls within a range of approximately
                          2.5 to 3.2 times the bankfull width»). Aleatorio por
                          curva con 'Random scale factors', o 2.5 fijo.
        λ  = 4.53 · Rc    longitud de meandro («meander length ... is 4.53
                          times the radius of curvature»).
        B  = 0.61 · λ     cinturón de meandro («the meander belt width ... as
                          0.61 times the meander length»).
    El reach de canal A es MEDIA longitud de meandro (§2.2.10).

    OJO: hasta la v1.0.16 esta cabecera describía unas leyes potenciales
    (λ = 10.9·W^1.01, Rc = 2.4·W^1.04) y colocaba el rango 2.5-3.2 sobre el
    CINTURÓN en vez de sobre Rc. El código nunca hizo eso —siempre implementó
    las tres ecuaciones de arriba—, pero la documentación contradecía al
    módulo. `tests/test_libro.py` fija ahora cada relación con su cita.

Este módulo es Python puro (sin QGIS) para poder testearse aislado.
"""

import math
from dataclasses import dataclass, field

# ---------------- constantes físicas ----------------
GAMMA_W = 9810.0          # peso específico del agua, N/m3
GAMMA_S = 25996.5         # peso específico del sedimento (ρs=2650 kg/m3), N/m3
G = 9.81                  # m/s2
Z_TALUD = 4.0             # taludes interiores del cauce 4H:1V (NR por defecto)
THETA_CRIT = 0.045        # parámetro de Shields crítico (turbulento rugoso)
# Ecuaciones de régimen (Williams 1986, según Geomorphic Reclamation Design
# 2024 §2.2): Rc = k·W con k ∈ [2.5, 3.2]; λ = 4.53·Rc; cinturón = 0.61·λ
RC_MIN = 2.5              # radio de curvatura mínimo, × W bankfull
RC_MAX = 3.2              # radio de curvatura máximo, × W bankfull
LAMBDA_POR_RC = 4.53      # longitud de meandro / radio de curvatura
BELT_POR_LAMBDA = 0.61    # cinturón de meandro / longitud de meandro


# ---------------- caudales ----------------

def qpk_racional(c: float, i_mm_h: float, area_ha: float) -> float:
    """Caudal punta (m3/s) por método racional. i en mm/h, A en ha.

    Q [m3/s] = C · i [mm/h] · A [ha] / 360
    """
    return c * i_mm_h * area_ha / 360.0


def intensidad_2a1h(p_mm: float) -> float:
    """Intensidad (mm/h) de la tormenta de 2 años y 1 hora."""
    return p_mm / 1.0


def intensidad_50a6h_instantanea(p_mm: float) -> float:
    """Toda la lluvia de la tormenta de 50 años y 6 horas se introduce
    'instantáneamente' en el canal (criterio conservador del método):
    se usa la precipitación total como intensidad horaria equivalente."""
    return p_mm


# ---------------- geometría del trapecio ----------------

def _area_trapecio(b: float, z: float, d: float) -> float:
    return d * (b + z * d)


def _perimetro_trapecio(b: float, z: float, d: float) -> float:
    return b + 2.0 * d * math.sqrt(1.0 + z * z)


def _ancho_sup_trapecio(b: float, z: float, d: float) -> float:
    return b + 2.0 * z * d


@dataclass
class SeccionCanal:
    """Dimensiones y propiedades hidráulicas de una sección transversal."""
    # caudales
    q_bankfull: float = 0.0        # m3/s
    q_flood: float = 0.0           # m3/s
    # bankfull
    ancho_bankfull: float = 0.0    # m (anchura en lámina de agua)
    prof_bankfull: float = 0.0     # m (calado)
    area_bankfull: float = 0.0     # m2
    ancho_fondo: float = 0.0       # m
    perimetro_bkf: float = 0.0     # m (perímetro mojado)
    radio_hidr_bkf: float = 0.0    # m
    # flood-prone
    ancho_flood: float = 0.0       # m
    prof_flood: float = 0.0        # m
    area_flood: float = 0.0        # m2
    entrenchment: float = 0.0      # W_fp / W_bkf (ratio de atrincheramiento)
    # taludes
    talud_izq_pct: float = 25.0    # 4H:1V = 25 %
    talud_der_pct: float = 25.0
    # tensión tractiva
    tension_bankfull: float = 0.0  # N/m2 (τ = γ·R·S)
    tension_flood: float = 0.0     # N/m2
    tension_critica: float = 0.0   # N/m2 (Shields con D50)
    ratio_tractivo: float = 0.0    # τ_bkf / τ_crit
    estab_tractiva: str = "ok"     # 'ok' | 'high' (τ_bkf > τ_crit)
    # verificación Manning
    calado_manning: float = 0.0    # m (calado normal para Q_bkf)
    vel_manning: float = 0.0       # m/s
    froude: float = 0.0
    verif_manning: str = "ok"      # 'ok' | 'v_high' | 'v_low'
    avisos: list = field(default_factory=list)


def ancho_bankfull(q: float, wd_ratio: float, vel_max: float,
                   z: float = Z_TALUD) -> float:
    """Anchura bankfull (m) del trapecio de diseño para un caudal dado.

    A = Q/v ;  A = d²(wd − z)  ⇒  d = sqrt(A/(wd−z)) ;  W = wd·d
    """
    if q <= 0 or vel_max <= 0:
        return 0.0
    wd_ef = max(wd_ratio, z + 1.0)
    a = q / vel_max
    d = math.sqrt(a / (wd_ef - z))
    return wd_ef * d


def calado_normal_manning(q: float, n: float, s: float, b: float,
                          z: float = Z_TALUD, d_max: float = 25.0) -> float:
    """Calado normal (m) por Manning en trapecio (bisección).

    Q = (1/n)·A·R^(2/3)·√S  con A(d), R(d) del trapecio (b, z).
    """
    s = abs(s)
    if q <= 0 or n <= 0 or s < 1e-6:
        return 0.0

    def q_de(d):
        if d <= 0:
            return 0.0
        a = _area_trapecio(b, z, d)
        r = a / _perimetro_trapecio(b, z, d)
        return a * (r ** (2.0 / 3.0)) * math.sqrt(s) / n

    lo, hi = 0.0, 0.5
    while q_de(hi) < q and hi < d_max:
        hi *= 2.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if q_de(mid) < q:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def tension_critica_shields(d50_mm: float, theta: float = THETA_CRIT) -> float:
    """Tensión tractiva crítica de Shields (N/m²) para un D50 en mm."""
    if d50_mm is None or d50_mm <= 0:
        return 0.0
    return theta * (GAMMA_S - GAMMA_W) * (d50_mm / 1000.0)


def dimensionar_seccion(q_bankfull: float, q_flood: float, wd_ratio: float,
                        vel_max: float, pendiente: float,
                        n_manning: float = 0.033,
                        d50_mm: float = None) -> SeccionCanal:
    """Dimensiona la sección de una estación y calcula toda su hidráulica.

    Ver el esquema de cálculo en la cabecera del módulo. 'pendiente' es la
    pendiente local del perfil (adimensional, negativa aguas abajo).
    """
    s = SeccionCanal(q_bankfull=q_bankfull, q_flood=q_flood)
    z = Z_TALUD
    s_abs = max(abs(pendiente), 1e-5)

    if q_bankfull <= 0 or vel_max <= 0:
        return s

    # --- bankfull: A = Q/v con W:D y taludes 4H:1V ---
    wd_ef = max(wd_ratio, z + 1.0)
    if wd_ef != wd_ratio:
        s.avisos.append(
            f"W:D={wd_ratio:g} inferior al mínimo geométrico con taludes 4:1; "
            f"se usa {wd_ef:g}.")
    a_bkf = q_bankfull / vel_max
    d = math.sqrt(a_bkf / (wd_ef - z))
    w = wd_ef * d
    b = w - 2.0 * z * d
    if b < 0.05 * w:        # W:D < 8 deja fondo casi nulo: trapecio → triángulo
        b = 0.05 * w
    s.prof_bankfull = d
    s.ancho_bankfull = w
    s.ancho_fondo = b
    s.area_bankfull = _area_trapecio(b, z, d)
    s.perimetro_bkf = _perimetro_trapecio(b, z, d)
    s.radio_hidr_bkf = s.area_bankfull / s.perimetro_bkf if s.perimetro_bkf else 0.0

    # --- flood-prone: mismo fondo y taludes, área para Q_flood ---
    if q_flood > 0:
        a_fp = max(q_flood / vel_max, s.area_bankfull * 1.05)
        d_fp = (-b + math.sqrt(b * b + 4.0 * z * a_fp)) / (2.0 * z)
        s.prof_flood = d_fp
        s.ancho_flood = _ancho_sup_trapecio(b, z, d_fp)
        s.area_flood = _area_trapecio(b, z, d_fp)
        s.entrenchment = s.ancho_flood / w if w > 0 else 0.0

    # --- tensión tractiva τ = γ·R·S ---
    s.tension_bankfull = GAMMA_W * s.radio_hidr_bkf * s_abs
    if q_flood > 0:
        a_f = s.area_flood
        p_f = _perimetro_trapecio(b, z, s.prof_flood)
        s.tension_flood = GAMMA_W * (a_f / p_f if p_f else 0.0) * s_abs

    # --- estabilidad de Shields ---
    s.tension_critica = tension_critica_shields(d50_mm)
    if s.tension_critica > 0:
        s.ratio_tractivo = s.tension_bankfull / s.tension_critica
        s.estab_tractiva = "high" if s.ratio_tractivo > 1.0 else "ok"

    # --- verificación con Manning (no altera el dimensionado) ---
    if n_manning and n_manning > 0:
        dn = calado_normal_manning(q_bankfull, n_manning, s_abs, b, z)
        if dn > 0:
            a_n = _area_trapecio(b, z, dn)
            t_n = _ancho_sup_trapecio(b, z, dn)
            s.calado_manning = dn
            s.vel_manning = q_bankfull / a_n if a_n else 0.0
            dh = a_n / t_n if t_n else 0.0
            s.froude = s.vel_manning / math.sqrt(G * dh) if dh > 0 else 0.0
            if s.vel_manning > vel_max * 1.05:
                s.verif_manning = "v_high"
                s.avisos.append(
                    f"Manning: v={s.vel_manning:.2f} m/s > v_max={vel_max:g} "
                    "(la pendiente local impone más velocidad que la de diseño).")
            elif s.vel_manning < vel_max * 0.4:
                s.verif_manning = "v_low"
    return s


# ---------------- geometría de meandro ----------------

def geometria_meandro(w_bankfull: float, k: float = None):
    """Geometría de meandro a partir de la anchura bankfull W (m), según las
    ecuaciones de régimen de Williams 1986 (Geomorphic Reclamation Design
    2024, §2.2 'Channel plan view geometry'):

      Rc = k·W          con k en el rango estable [2.5, 3.2] (aleatorio por
                        curva con 'Random scale factors', o 2.5 fijo)
      λ  = 4.53·Rc      (longitud de meandro: ápice a ápice del mismo lado)
      B  = 0.61·λ       (cinturón de meandro: tangentes a los ápices de
                        lados opuestos)

    Devuelve (longitud_meandro λ, cinturón B, radio_curvatura Rc).
    """
    w = max(w_bankfull, 1e-3)
    k = RC_MIN if k is None else max(RC_MIN, min(k, RC_MAX))
    rc = k * w
    lm = LAMBDA_POR_RC * rc
    belt = BELT_POR_LAMBDA * lm
    return lm, belt, rc


def geometria_meandro_q(q_bankfull: float, wd_ratio: float = 12.5,
                        vel_max: float = 1.4, k: float = None):
    """Como geometria_meandro pero partiendo del caudal bankfull (m3/s)."""
    w = ancho_bankfull(max(q_bankfull, 1e-6), wd_ratio, vel_max)
    return geometria_meandro(w, k)
