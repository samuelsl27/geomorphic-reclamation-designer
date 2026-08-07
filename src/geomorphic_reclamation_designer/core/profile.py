# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Perfiles longitudinales cóncavos del método fluvio-geomórfico.

El perfil de un canal natural estable es cóncavo: más pendiente en cabecera y
menos hacia la boca (Dunne & Leopold, 1978). GeoFluv construye una curva
vertical entre las cotas de cabecera y boca usando las pendientes de cabecera
y boca especificadas; los tributarios empalman con la misma pendiente que el
canal receptor en la confluencia (transición hidráulica suave).

Convención de estacionado: s = 0 en la CABECERA y s = L en la BOCA
(el estacionado crece aguas abajo). Las pendientes se expresan como dz/ds,
por lo que son negativas (el terreno desciende aguas abajo).
"""

from dataclasses import dataclass, field
import bisect


@dataclass
class PerfilLongitudinal:
    """Perfil z(s) muestreado; permite consultar cota y pendiente en cualquier s."""
    estaciones: list = field(default_factory=list)  # s crecientes
    cotas: list = field(default_factory=list)
    L: float = 0.0
    z_cabecera: float = 0.0
    z_boca: float = 0.0
    s_cabecera: float = 0.0   # pendiente dz/ds en cabecera (negativa)
    s_boca: float = 0.0       # pendiente dz/ds en boca (negativa)
    ajustado: bool = False    # True si hubo que corregir pendientes para consistencia

    def z(self, s):
        """Cota interpolada en la estación s."""
        if not self.estaciones:
            return 0.0
        s = max(self.estaciones[0], min(s, self.estaciones[-1]))
        i = bisect.bisect_left(self.estaciones, s)
        if i == 0:
            return self.cotas[0]
        if i >= len(self.estaciones):
            return self.cotas[-1]
        s0, s1 = self.estaciones[i - 1], self.estaciones[i]
        z0, z1 = self.cotas[i - 1], self.cotas[i]
        t = (s - s0) / (s1 - s0) if s1 > s0 else 0.0
        return z0 + t * (z1 - z0)

    def pendiente(self, s, ds=1.0):
        """Pendiente dz/ds (negativa aguas abajo) en la estación s."""
        s0 = max(0.0, s - ds / 2)
        s1 = min(self.L, s + ds / 2)
        if s1 <= s0:
            return self.s_boca
        return (self.z(s1) - self.z(s0)) / (s1 - s0)


def disenar_perfil(L, z_cabecera, z_boca, pend_cabecera, pend_boca, n=200,
                   concavidad=1.0):
    """Curva vertical cúbica de Hermite que cumple cotas y pendientes en ambos
    extremos. Pendientes en tanto por uno, negativas (p. ej. -0.12 y -0.02).

    Si la pendiente media (z_boca - z_cabecera)/L no queda entre las pendientes
    de cabecera y boca, no existe una curva monótona cóncava que cumpla las
    cuatro condiciones; se ajusta la pendiente de cabecera para mantener una
    parábola cóncava consistente (y se marca 'ajustado' para avisar al usuario).
    """
    perfil = PerfilLongitudinal(L=L)
    if L <= 0:
        return perfil

    m = (z_boca - z_cabecera) / L  # pendiente media (negativa)
    s0, s1 = pend_cabecera, pend_boca
    ajustado = False

    if m >= 0 or abs(m) < 1e-9:
        # sin desnivel real: perfil plano-lineal
        s0 = s1 = m
        ajustado = True
    else:
        # 1) Concavidad exige s0 < m < s1 (todas negativas; s0 la más empinada).
        #    La pendiente de boca es "el valor más crítico" del método: se
        #    respeta y se ajusta la de cabecera si hace falta (parábola:
        #    pendiente media = (s0+s1)/2  =>  s0 = 2m - s1).
        if not (s0 < m < s1):
            s0_nuevo = 2.0 * m - s1
            if s0_nuevo < m < s1:
                s0 = s0_nuevo
            else:
                s0 = s1 = m       # ni siquiera así: perfil lineal
            ajustado = True
        # 2) Condición suficiente de monotonía de la cúbica de Hermite
        #    (Fritsch-Carlson): 0 <= s0/m, s1/m <= 3.
        if s0 / m > 3.0:
            s0 = 3.0 * m
            ajustado = True
        if s1 / m > 3.0:
            s1 = 3.0 * m
            ajustado = True

    perfil.z_cabecera, perfil.z_boca = z_cabecera, z_boca
    perfil.s_cabecera, perfil.s_boca = s0, s1
    perfil.ajustado = ajustado

    for i in range(n + 1):
        t = i / n
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1
        h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2
        h11 = t ** 3 - t ** 2
        z = h00 * z_cabecera + h10 * L * s0 + h01 * z_boca + h11 * L * s1
        # 'concavidad' mezcla la curva de Hermite con la recta cabecera-boca:
        # 0 = perfil recto, 1 = curva estándar, >1 exagera la concavidad. Es lo
        # que permite a la optimización redefinir la curva sin tocar las cotas
        # de los extremos.
        if abs(concavidad - 1.0) > 1e-6:
            z_recta = z_cabecera + (z_boca - z_cabecera) * t
            z = z_recta + concavidad * (z - z_recta)
        perfil.estaciones.append(t * L)
        perfil.cotas.append(z)
    # forzar monotonía numérica descendente (por seguridad frente a redondeos)
    for i in range(1, len(perfil.cotas)):
        if perfil.cotas[i] > perfil.cotas[i - 1]:
            perfil.cotas[i] = perfil.cotas[i - 1]
    return perfil


def estacion_transicion(perfil, umbral=0.04):
    """Estación donde |pendiente| cae por debajo del umbral (transición del
    tramo tipo A, empinado, al tramo de fondo de valle). Devuelve None si todo
    el perfil es más tendido que el umbral (no hay tramo A)."""
    if not perfil.estaciones:
        return None
    if abs(perfil.pendiente(0.0)) <= umbral:
        return None  # ya empieza tendido: sin tramo A
    for s in perfil.estaciones:
        if abs(perfil.pendiente(s)) <= umbral:
            return s
    return perfil.L  # todo el canal es tipo A
