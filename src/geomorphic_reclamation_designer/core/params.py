# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Parámetros del proyecto.

Todos los ajustes globales y por canal del método fluvio-geomórfico.
Unidades: métricas (m, m/s, mm de lluvia, m/ha para densidad de drenaje).
El usuario puede trabajar también en pies/acres cambiando 'unidades', pero
internamente todo se maneja en las unidades del CRS del proyecto (se asume
CRS proyectado en metros).
"""

# OBLIGATORIO en este módulo: las anotaciones `float | None` de las dataclass
# son PEP 604, que no existe hasta Python 3.10, y QGIS 3.22 trae **Python 3.9**.
# Sin esta línea el módulo revienta al importarse con
# `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`, y con
# él todo el complemento, en el rango de QGIS que declara metadata.txt.
# Con ella las anotaciones quedan como cadenas y no se evalúan; las dataclass
# funcionan igual porque no llaman a get_type_hints().
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class GlobalSettings:
    """Equivalente a 'Global Settings'."""
    # Dibujo / snapping
    max_dist_conexion_canales: float = 3.0        # m, separación máx. para reconocer conexión de polilíneas
    tol_cota_cabecera_m: float = 0.5              # tolerancia de cota en cabecera (aviso)
    tol_pendiente_cabecera_pct: float = 0.5       # tolerancia de pendiente en cabecera (aviso)
    lineas_por_canal: int = 7                     # nº de líneas por canal: 3 (eje+bankfull), 5 (+fondo), 7 (+flood)
    # Variables locales esenciales
    max_dist_cresta_cabecera: float = 25.0        # m, distancia máx. de la divisoria a la cabecera de canal estable (default 80 ft)
    # Porción convexa máxima de subcresta: modo 'factor' (1.5 × dist. cresta-cabecera)
    # o 'pct' (% de la longitud total de la subcresta) — como el original
    convexo_modo: str = "factor"                  # 'factor' | 'pct'
    convexo_pct: float = 20.0                     # % si convexo_modo == 'pct'
    convexo_swale_activo: bool = False            # porción convexa máx. de vaguada (swale)
    convexo_swale_m: float = 12.0                 # m
    pendiente_desembocadura: float = -2.0         # %, pendiente en la boca del canal principal (crítico)
    sinuosidad_canal_A: float = 1.15              # canales con pendiente > 4% (tipo A), sinuosidad < 1.2
    reach_canal_A: float = 15.0                   # m, media longitud de meandro en canales A (default 50 ft)
    # Precipitación de diseño
    p_2a_1h_mm: float = 15.0                      # lluvia 2 años, 1 hora (dimensiona bankfull)
    p_50a_6h_mm: float = 50.0                     # lluvia 50 años, 6 horas (dimensiona flood-prone)
    # Densidad de drenaje
    dd_objetivo: float = 75.0                     # m/ha (≈ densidad objetivo; 100 ft/ac ≈ 75 m/ha)
    dd_varianza_pct: float = 20.0                 # % de varianza admisible
    forzar_crestas_bajo_limite: bool = False
    # Subcrestas y laderas
    angulo_subcresta_deg: float = 10.0            # ángulo de subcresta respecto a la perpendicular del canal, aguas arriba
    pendiente_NE_pct: float = 20.0                # objetivo laderas N/E (315°-135°)
    pendiente_max_pct: float = 33.0               # objetivo máximo cresta-pie
    # Hidráulica / material
    d50_mm: float = 8.0                           # D50 del conteo Wolman en el área de referencia (mm)
    # Balance de tierras
    var_max_corte_relleno_pct: float = 125.0
    var_min_corte_relleno_pct: float = 80.0
    factor_esponjamiento: float = 1.0             # cut swell
    factor_compactacion: float = 1.0              # fill shrink
    # Salida
    intervalo_curvas: float = 1.0                 # m
    intervalo_curvas_maestras: float = 5.0        # m
    intervalo_estaciones: float = 10.0            # m, para informes de sección transversal
    # --- 'Triangulate and Contour From TIN' (ventana de Draw Design Surface) ---
    resolucion_dem: float = 1.0                   # m, tamaño de celda de GF_DesignSurface
    naturalidad: int = 3                          # 0-10, pasadas del filtro de redondeo
    radio_suavizado: int = 1                      # celdas del filtro de redondeo
    recortar_superficie: bool = True              # NoData fuera del límite GeoFluv
    densificar_breaklines: bool = True            # 'Minimize Flat Triangles'
    intervalo_breaklines: float = 5.0             # m
    long_min_curva: float = 0.2                   # m, 'Min Contour Length'
    bezier_curvas: bool = True                    # 'Bezier Smoothing'
    factor_bezier: int = 5                        # 'Bezier Smoothing Factor'
    dibujar_curvas: bool = True                   # 'Draw Contours'
    # --- tolerancias de revisión del diseño ('Check Design') ---
    # Equivalen a los 'design warning tolerance settings' del original y a los
    # umbrales del Error Log de Carlson al contornear.
    # Holgura con la que una divisoria de cuenca se para por FUERA del borde
    # flood-prone del cauce. Medido en la salida del original: 7.1 y 6.9 m del
    # eje con una semianchura flood-prone de ~2.5 m, es decir ~4.5 m de holgura.
    # Las crestas y vaguadas de ladera mueren en el propio borde (holgura 0).
    holgura_divisoria_m: float = 4.5
    # Profundidad de la 'silla' que la divisoria forma donde muere una vaguada,
    # en % del desnivel entre el filo y la cabecera de la vaguada. Libro 9.4:
    # las sillas evitan que el agua corra por el filo de la cresta y la
    # encauzan hacia las vaguadas. 0 = sin sillas (filo continuo).
    prof_silla_pct: float = 25.0
    tol_cruce_breaklines_m: float = 0.10          # dif. de cota admisible donde se cruzan dos líneas de rotura
    tol_cruce_canal_m: float = 1.00               # ídem dentro del corredor del cauce (orillas y eje)
    long_max_lado_tin_m: float = 50.0             # 'maximum triangle mesh line length'
    pend_max_linea_pct: float = 300.0             # pico de cota entre dos vértices contiguos
    ang_max_valle_ladera_deg: float = 60.0        # valle trazado a media ladera en vez de ladera abajo
    # --- almacenamiento de capas (Create Design Layers) ---
    modo_almacenamiento: str = "memory"           # 'memory' | 'ruta' | 'proyecto'
    carpeta_capas: str = ""                       # carpeta destino cuando no es memoria

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        obj = cls()
        for k, v in (d or {}).items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        return obj


@dataclass
class ChannelSettings:
    """Ajustes por canal (pestaña Canales > 'Current Channel Settings')."""
    nombre: str = "main"
    # Geometría
    vel_max_agua: float = 1.4                     # m/s (≈4.5 ft/s)
    pendiente_cabecera_pct: float = -12.0
    pendiente_boca_pct: float | None = None       # solo canal principal
    wd_pend_mayor_004: float = 10.0               # ratio ancho:profundidad si |s| > 0.04
    wd_pend_menor_004: float = 12.5               # si |s| < 0.04
    sinuosidad_mayor_004: float = 1.15
    sinuosidad_menor_004: float = 1.48
    factores_aleatorios: bool = True              # variación aleatoria de la geometría sinusoidal
    espaciado_subcrestas: int = 3                 # nº impar de meandros entre subcrestas
    # Longitud convexa de subcresta/vaguada específica del canal (sobrescribe la global)
    especificar_convexo: bool = False
    dist_cresta_swale_m: float = 24.0             # 'Maximum distance from ridgeline to swale head'
    convexo_modo_canal: str = "factor"            # 'factor' (1.5 × dist) | 'pct'
    convexo_pct_canal: float = 20.0
    concavidad_perfil: float = 1.0                # 0 = recto, 1 = curva Hermite estándar, >1 más cóncavo
    cota_cabecera: float | None = None            # None => se toma del DEM
    cota_boca: float | None = None                # None => se toma del DEM (¡especificar en diseño final!)
    transicion_xy: tuple | None = None            # punto (x, y) de transición A <-> valle
    # Hidráulica
    n_manning: float = 0.033                      # n de Manning (verificación, no dimensionado)
    d50_mm: float | None = None                   # sobrescribe el D50 global (mm)
    # Hidrología
    usar_metodo_racional: bool = True
    coef_escorrentia: float = 0.6
    qpk_manual_bankfull: float | None = None      # m3/s
    qpk_manual_flood: float | None = None         # m3/s
    area_adicional_ha: float = 0.0
    area_adicional_en_cabecera: bool = True       # False => repartida a lo largo
    usar_racional_adicional: bool = True          # método racional para el área adicional
    coef_escorrentia_adicional: float = 0.6
    qpk_adic_bankfull: float | None = None        # Qpk manual del área adicional (m3/s)
    qpk_adic_flood: float | None = None
    # Identificador de la geometría (fid de la polilínea de fondo de valle)
    fid_fondo_valle: int | None = None

    def to_dict(self):
        d = asdict(self)
        d["transicion_xy"] = list(self.transicion_xy) if self.transicion_xy else None
        return d

    @classmethod
    def from_dict(cls, d):
        obj = cls()
        for k, v in (d or {}).items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        if obj.transicion_xy:
            obj.transicion_xy = tuple(obj.transicion_xy)
        return obj


# Umbral de pendiente que separa canales tipo A (zigzag, empinados) de los
# canales de fondo de valle sinusoidales (tipo Bc/C), según el método.
UMBRAL_PENDIENTE = 0.04
