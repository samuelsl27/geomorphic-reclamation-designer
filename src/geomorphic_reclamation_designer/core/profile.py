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
    cabecera_convexa: bool = False   # True si el tramo alto es convexo (ver abajo)

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

    LAS DOS PENDIENTES DEL USUARIO SE RESPETAN. Lo único que se impone encima
    es la monotonía (el cauce no puede remontar): la condición suficiente de
    Fritsch-Carlson para la cúbica de Hermite, `0 <= s0/m, s1/m <= 3`. Si actúa,
    se marca `ajustado` para que el motor avise (invariante H7).

    CUANDO LA CABECERA ES MÁS TENDIDA QUE LA MEDIA (`|s0| < |m|`) el perfil no
    puede ser cóncavo en todo su recorrido: para bajar el desnivel que hay que
    bajar, algún tramo intermedio tiene que ser más empinado que la cabecera. La
    curva de Hermite lo resuelve sola, con la pendiente creciendo desde la boca,
    alcanzando su máximo en torno al 70-80 % del recorrido y **decreciendo hacia
    la cabecera**: un TRAMO CONVEXO DE CABECERA. Eso se marca en
    `cabecera_convexa` y es exactamente lo que hace el programa original.

    Medido en el Ej_2 (Rom_Pla), pendiente media por deciles boca -> cabecera:

        main L1, cabecera pedida -15.4 %
          original  6.5  9.8 12.6 14.9 16.5 17.6 18.1 18.1 17.4 16.2  -> 16.2 %
          nuestro   7.7 11.4 14.5 16.8 18.5 19.5 19.8 19.4 18.3 16.5  -> 16.5 %

    Hasta la v1.0.18 el código exigía `s0 < m < s1` (concavidad estricta) y,
    cuando no se cumplía, **re-empinaba la cabecera** con `s0 = 2m - s1` para
    forzar una parábola cóncava. Eso sacrificaba el dato del usuario: main L1
    salía al 25.8 % con -15.4 % pedido y main R4 al 35.2 % con -17.44 %. Y como
    de la cota del cauce cuelgan las crestas, las laderas y la superficie, el
    error se propagaba a todo el diseño. La concavidad estricta no es una regla
    del método: el método pide un perfil cóncavo *en su conjunto*, y el propio
    original produce cabeceras convexas cuando el desnivel lo exige.
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
        # Ambas pendientes tienen que descender aguas abajo.
        if s0 > 0:
            s0, ajustado = 0.0, True
        if s1 > 0:
            s1, ajustado = 0.0, True
        # Condición suficiente de monotonía de la cúbica de Hermite
        # (Fritsch-Carlson): 0 <= s0/m, s1/m <= 3. Es lo ÚNICO que se impone.
        if s0 / m > 3.0:
            s0 = 3.0 * m
            ajustado = True
        if s1 / m > 3.0:
            s1 = 3.0 * m
            ajustado = True

    perfil.z_cabecera, perfil.z_boca = z_cabecera, z_boca
    perfil.s_cabecera, perfil.s_boca = s0, s1
    perfil.ajustado = ajustado
    # |s0| < |m| con las dos negativas <=> s0 > m: la cabecera es más tendida
    # que la media, así que hay tramo intermedio más empinado que ella.
    perfil.cabecera_convexa = bool(m < 0 and s0 > m)

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
