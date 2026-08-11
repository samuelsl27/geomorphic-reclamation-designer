#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Mide el diseno generado contra la salida del programa original.

    python scripts/comparar_original.py RUTA_DEL_EJEMPLO
    python scripts/comparar_original.py RUTA --json informe.json

RUTA es la carpeta del ejemplo, con `GRD_Files/` (lo nuestro) y
`GeoFluv_origen/` (el GeoPackage importado del DXF del original).

POR QUE. "Parece que ya esta bien" no vale (AGENTS.md §4, paso 6). Cada
correccion de geometria tiene que medirse, y medirse SIEMPRE IGUAL, o no hay
forma de saber si un cambio ha arreglado una cosa y roto otra. Este guion es la
regla de medir: se ejecuta antes y despues de cada cambio y se comparan los
numeros, no las impresiones.

No necesita QGIS ni GDAL: lee los GeoPackage con `scripts/lector_gpkg.py`.

QUE MIDE, y por que cada cosa:

  1. Inventario           entidades y longitud por capa. Un cambio que mueve
                          mucho la longitud total esta cambiando el relieve.
  2. Canales              longitud, sinuosidad, cotas de cabecera y boca, y el
                          perfil longitudinal por deciles. El perfil del cauce
                          es el cimiento: de su cota cuelga todo lo demas.
  3. Lineas de relieve    subcrestas y vaguadas contra las del original:
                          espaciado, angulo, longitud, cota de coronacion.
  4. Defectos de forma    escalones, mesetas, vaiven y lineas por debajo del
                          cauce. Una diferencia de FORMA siempre es un bug
                          (context/06, regla 4); una diferencia sistematica en
                          un ajuste es calibracion.

EMPAREJAMIENTO DE CANALES. Por COTA DE CABECERA, no por nombre. En el Ej_2 los
parametros de los tributarios estaban tecleados en orden invertido, asi que
emparejar por nombre habria dado falsos negativos en todo. La cota de cabecera
la fija el DEM en el extremo del fondo de valle, es la misma en los dos
programas, y coincide con menos de 0.1 m.
"""

import argparse
import json
import math
import os
import sys

# Hay que tocar sys.path antes de importar el lector: este guion se ejecuta
# desde la raiz del repositorio, no como parte de un paquete.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lector_gpkg

# Capas del original dentro del GeoPackage importado del DXF. El importador de
# QGIS mete todo en una tabla `polylines` con el nombre de capa del DXF en el
# campo `layer`.
CAPA_CANALES_ORIG = "GF_Channels"
CAPA_RELIEVE_ORIG = "GF_Ridges"

# El original mete divisorias y lineas de ladera en la MISMA capa `GF_Ridges`, y
# hay que separarlas para comparar como con como: nosotros las tenemos en capas
# distintas y compararlas en bloque enmascara el defecto que este guion busca.
#
# No sirve mirar los extremos. Una divisoria muere en la CONFLUENCIA de los dos
# cauces que separa, asi que su extremo bajo tambien esta pegado a un cauce: con
# una tolerancia de 10 m, las 244 lineas del Ej_2 salen clasificadas como
# ladera. Lo que si las distingue es la EQUIDISTANCIA — una divisoria corre por
# el medio entre dos cauces; una ladera esta mucho mas cerca del suyo.
#
# Los dos umbrales estan calibrados contra la verdad conocida: se aplica el
# clasificador a la union de nuestras tres capas, donde ya se sabe cual es cual.
# Con 0.75/0.5 la precision es del 65 %, y ese fue el error que inflo la cuenta
# de divisorias del original de 7 a 17. Con 0.80/0.8 acierta las 13 de 13 sin
# ningun falso positivo entre las 219 lineas de ladera.
NUESTRAS_RELIEVE = ("GRD_SubRidges", "GRD_Swales")

TOL_CABECERA = 1.0     # m, para emparejar un canal nuestro con el del original
CERCA_CAUCE = 8.0      # m, "este extremo arranca en el cauce"
EQUIDIST = 0.80        # d(cauce mas cercano) / d(segundo) por encima de esto...
EQUIDIST_FRAC = 0.8    # ...en esta fraccion de los vertices muestreados


# ------------------------------------------------------------------ geometria
def largo(pts):
    return sum(math.dist(pts[i][:2], pts[i + 1][:2]) for i in range(len(pts) - 1))


def resumen(v, fmt="%.2f"):
    if not v:
        return "sin datos"
    v = sorted(v)
    n = len(v)

    def q(k):
        return fmt % v[min(n - 1, int(n * k))]

    return ("n=%d min=%s p50=%s p90=%s max=%s media=%s"
            % (n, fmt % v[0], q(.5), q(.9), fmt % v[-1], fmt % (sum(v) / n)))


class Rejilla:
    """Indice de puntos por celdas, para no hacer O(n*m) al buscar el vecino."""

    def __init__(self, puntos, lado=25.0):
        self.lado = lado
        self.celdas = {}
        for p in puntos:
            self.celdas.setdefault(
                (int(p[0] // lado), int(p[1] // lado)), []).append(p)

    def cercano(self, pt):
        """(distancia, punto) al vertice mas proximo en planta."""
        cx, cy = int(pt[0] // self.lado), int(pt[1] // self.lado)
        r = 1
        while True:
            cand = [q for i in range(cx - r, cx + r + 1)
                    for j in range(cy - r, cy + r + 1)
                    for q in self.celdas.get((i, j), ())]
            if cand:
                mejor = min(cand, key=lambda q: math.dist(pt[:2], q[:2]))
                d = math.dist(pt[:2], mejor[:2])
                # Solo es seguro si cabe dentro del anillo ya explorado.
                if d <= (r - 0.5) * self.lado or r > 40:
                    return d, mejor
            r += 1
            if r > 40:
                return float("inf"), None


def extremos(pts):
    """(extremo alto, extremo bajo) por cota."""
    return ((pts[0], pts[-1]) if pts[0][2] >= pts[-1][2] else (pts[-1], pts[0]))


def perfil(pts):
    """(estaciones, cotas) orientado de boca (s=0) a cabecera."""
    s, acc = [0.0], 0.0
    for i in range(len(pts) - 1):
        acc += math.dist(pts[i][:2], pts[i + 1][:2])
        s.append(acc)
    z = [p[2] for p in pts]
    if z[0] > z[-1]:
        s, z = [acc - x for x in s][::-1], z[::-1]
    return s, z


def _interp(s, z, x):
    for i in range(len(s) - 1):
        if s[i] <= x <= s[i + 1]:
            t = (x - s[i]) / (s[i + 1] - s[i]) if s[i + 1] > s[i] else 0.0
            return z[i] + t * (z[i + 1] - z[i])
    return z[-1] if x > s[-1] else z[0]


def deciles(s, z, n=10):
    L = s[-1]
    return [(_interp(s, z, L * (k + 1) / n) - _interp(s, z, L * k / n))
            / (L / n) * 100.0 for k in range(n)]


def pend_segmentos(pts, minimo=0.05):
    out = []
    for i in range(len(pts) - 1):
        dl = math.dist(pts[i][:2], pts[i + 1][:2])
        if dl > minimo:
            out.append((abs(pts[i + 1][2] - pts[i][2]) / dl * 100.0, dl, i))
    return out


def meseta(pts, tol=0.01):
    """Vertices consecutivos a la misma cota: la firma de un aplastamiento."""
    peor, run = 1, 1
    for i in range(1, len(pts)):
        run = run + 1 if abs(pts[i][2] - pts[i - 1][2]) <= tol else 1
        peor = max(peor, run)
    return peor


def vaiven(pts):
    """Cuanto sube y baja de mas respecto del desnivel util."""
    z = [p[2] for p in pts]
    sube = sum(max(0.0, z[i + 1] - z[i]) for i in range(len(z) - 1))
    baja = sum(max(0.0, z[i] - z[i + 1]) for i in range(len(z) - 1))
    return sube + baja - abs(z[0] - z[-1])


def giro_extremo(pts, largo=20.0):
    """Giro acumulado (grados) en los `largo` metros finales de cada extremo.

    Es la medida de P-27, el 'gancho': nuestras divisorias giran sobre si mismas
    al morir junto a una confluencia (hasta 104 grados) y las del original
    llegan rectas (33 como maximo). Devuelve el peor de los dos extremos."""
    def _giro(tramo):
        g = 0.0
        for i in range(1, len(tramo) - 1):
            a = math.atan2(tramo[i][1] - tramo[i - 1][1],
                           tramo[i][0] - tramo[i - 1][0])
            b = math.atan2(tramo[i + 1][1] - tramo[i][1],
                           tramo[i + 1][0] - tramo[i][0])
            d = abs(math.degrees(b - a))
            g += min(d, 360.0 - d)
        return g

    def _corte(seq):
        acc, out = 0.0, [seq[0]]
        for i in range(1, len(seq)):
            acc += math.dist(seq[i - 1][:2], seq[i][:2])
            out.append(seq[i])
            if acc >= largo:
                break
        return out

    if len(pts) < 3:
        return 0.0
    return max(_giro(_corte(pts)), _giro(_corte(pts[::-1])))


def pendiente_de_ladera(pts, ejes, n=2):
    """[(pendiente %, lado)] desde cada vertice a los `n` cauces mas proximos.

    Es la pendiente que el ajuste `Maximum straight-line slopes` acota, medida
    donde de verdad se produce: de la divisoria al cauce, no a lo largo del
    filo. El original no pasa de 48 % con objetivo 33; nosotros llegamos a 124."""
    out = []
    for q in pts:
        lados = []
        for e in ejes:
            mejor = (float("inf"), None)
            for i in range(len(e) - 1):
                ax, ay, az = e[i]
                bx, by, bz = e[i + 1]
                dx, dy = bx - ax, by - ay
                den = dx * dx + dy * dy
                t = 0.0 if den < 1e-12 else max(0.0, min(
                    1.0, ((q[0] - ax) * dx + (q[1] - ay) * dy) / den))
                d = math.hypot(q[0] - (ax + t * dx), q[1] - (ay + t * dy))
                if d < mejor[0]:
                    mejor = (d, az + t * (bz - az))
            lados.append(mejor)
        lados.sort()
        for k, (d, z) in enumerate(lados[:n]):
            if d > 2.0 and z is not None:
                out.append(((q[2] - z) / d * 100.0, k))
    return out


def angulo(pts, ejes_rejilla, ejes):
    """Angulo (grados) entre el arranque de la linea y el eje del cauce."""
    _, q = ejes_rejilla.cercano(pts[0])
    if q is None:
        return None
    mejor = None
    for e in ejes:
        for i in range(len(e) - 1):
            if e[i][:2] == q[:2]:
                mejor = (e, i)
                break
    if mejor is None:
        return None
    e, i = mejor
    j = i + 1 if i + 1 < len(e) else i - 1
    tx, ty = e[j][0] - e[i][0], e[j][1] - e[i][1]
    k = min(3, len(pts) - 1)
    lx, ly = pts[k][0] - pts[0][0], pts[k][1] - pts[0][1]
    nt, nl = math.hypot(tx, ty), math.hypot(lx, ly)
    if nt < 1e-9 or nl < 1e-9:
        return None
    a = math.degrees(math.acos(max(-1.0, min(1.0, (tx * lx + ty * ly) / (nt * nl)))))
    return min(a, 180.0 - a)


# --------------------------------------------------------------------- carga
def localizar(carpeta):
    grd = os.path.join(carpeta, "GRD_Files")
    orig_dir = os.path.join(carpeta, "GeoFluv_origen")
    if not os.path.isdir(grd):
        raise SystemExit("No encuentro %s" % grd)
    orig = None
    if os.path.isdir(orig_dir):
        for f in sorted(os.listdir(orig_dir)):
            if f.lower().endswith(".gpkg"):
                orig = os.path.join(orig_dir, f)
                break
    return grd, orig


def capa_nuestra(grd, nombre):
    ruta = os.path.join(grd, nombre + ".gpkg")
    if not os.path.exists(ruta):
        return []
    return lector_gpkg.lineas(ruta, nombre)


def capa_original(ruta, nombre):
    if not ruta:
        return []
    return lector_gpkg.lineas(ruta, "polylines", "layer='%s'" % nombre)


def ejes_del_original(canales_grd, lineas_orig):
    """Empareja cada canal nuestro con su eje en el original, por cota de
    cabecera. Devuelve (dict nombre -> pts, lista de no emparejados)."""
    usados, salida = set(), {}
    for at, pts in canales_grd:
        cab = max(p[2] for p in pts)
        cand = [(i, p) for i, (_, p) in enumerate(lineas_orig)
                if i not in usados
                and abs(max(q[2] for q in p) - cab) <= TOL_CABECERA]
        if not cand:
            continue
        i, p = max(cand, key=lambda t: largo(t[1]))
        usados.add(i)
        salida[at["name"]] = p
    sobran = [p for i, (_, p) in enumerate(lineas_orig) if i not in usados]
    return salida, sobran


def es_divisoria(pts, ejes, umbral=EQUIDIST, frac=EQUIDIST_FRAC):
    """True si la linea corre por el medio entre dos cauces. Ver la nota de
    arriba: los umbrales estan calibrados, no elegidos a ojo."""
    if len(ejes) < 2:
        return False
    muestra = pts[::max(1, len(pts) // 12)]
    razones = []
    for q in muestra:
        ds = sorted(min(math.dist(q[:2], w[:2]) for w in e) for e in ejes)
        if ds[1] > 0:
            razones.append(ds[0] / ds[1])
    if not razones:
        return False
    return sum(1 for x in razones if x > umbral) / len(razones) > frac


def separar_relieve(lineas, ejes):
    """(divisorias, laderas) a partir de una capa que mezcla las dos."""
    div, lad = [], []
    for at, p in lineas:
        (div if es_divisoria(p, ejes) else lad).append((at, p))
    return div, lad


# ------------------------------------------------------------------- informe
def informe(carpeta, salida_json=None):
    grd, orig = localizar(carpeta)
    print("=" * 78)
    print("COMPARACION CONTRA EL ORIGINAL — %s" % os.path.basename(
        os.path.normpath(carpeta)))
    print("  nuestro : %s" % grd)
    print("  original: %s" % (orig or "NO ENCONTRADO"))
    print("=" * 78)

    n_canales = capa_nuestra(grd, "GRD_Channels")
    n_relieve = [(at, p) for capa in NUESTRAS_RELIEVE
                 for at, p in capa_nuestra(grd, capa)]
    n_divisorias = capa_nuestra(grd, "GRD_Ridges")
    o_canales = capa_original(orig, CAPA_CANALES_ORIG)
    o_relieve = capa_original(orig, CAPA_RELIEVE_ORIG)

    res = {"carpeta": carpeta}

    # ---------------------------------------------------------- 1 inventario
    print("\n1) INVENTARIO")
    for nom, lst in (("GRD_Channels", n_canales),
                     ("GRD_SubRidges+GRD_Swales", n_relieve),
                     ("GRD_Ridges (las del original van en %s)"
                      % CAPA_RELIEVE_ORIG, n_divisorias),
                     ("ORIG " + CAPA_CANALES_ORIG, o_canales),
                     ("ORIG " + CAPA_RELIEVE_ORIG, o_relieve)):
        print("   %-44s %4d lineas  %10.1f m"
              % (nom, len(lst), sum(largo(p) for _, p in lst)))

    ejes_o, sobran = ejes_del_original(n_canales, o_canales)
    print("   ejes del original emparejados por cota de cabecera: %d de %d "
          "canales (%d lineas del original sin emparejar: orillas y tramos)"
          % (len(ejes_o), len(n_canales), len(sobran)))

    # ------------------------------------------------------------ 2 canales
    print("\n2) CANALES")
    cab = ("   %-10s %-8s %8s %8s %7s %9s %9s %8s %8s"
           % ("canal", "cual", "L", "valle", "sinuo", "cabecera", "boca",
              "p.boca", "p.cab"))
    print(cab)
    res["canales"] = {}
    for at, pts in n_canales:
        nombre = at["name"]
        for cual, p in (("nuestro", pts), ("original", ejes_o.get(nombre))):
            if p is None:
                print("   %-10s %-8s  (no emparejado)" % (nombre, cual))
                continue
            s, z = perfil(p)
            pb = (_interp(s, z, min(20.0, s[-1])) - z[0]) / min(20.0, s[-1]) * 100
            pc = (z[-1] - _interp(s, z, s[-1] - min(20.0, s[-1]))) \
                / min(20.0, s[-1]) * 100
            valle = at["valley_length"] if cual == "nuestro" else float("nan")
            sin_ = at["sinuosity"] if cual == "nuestro" else float("nan")
            print("   %-10s %-8s %8.1f %8.1f %7.3f %9.2f %9.2f %8.2f %8.2f"
                  % (nombre, cual, s[-1], valle, sin_, z[-1], z[0], pb, pc))
            res["canales"].setdefault(nombre, {})[cual] = {
                "longitud": s[-1], "cabecera": z[-1], "boca": z[0],
                "pend_boca": pb, "pend_cabecera": pc,
                "deciles": deciles(s, z)}

    print("\n   PERFIL LONGITUDINAL, pendiente media (%) por deciles boca->cabecera")
    print("   (concavo = creciente hacia la cabecera; si decrece al final, hay")
    print("    tramo convexo de cabecera, que es como el original evita")
    print("    sobrepasar la pendiente pedida)")
    for nombre, d in res["canales"].items():
        for cual in ("nuestro", "original"):
            if cual in d:
                print("   %-10s %-8s %s" % (nombre, cual, " ".join(
                    "%5.1f" % x for x in d[cual]["deciles"])))

    # ------------------------------------------------------------ 3 relieve
    print("\n3) LINEAS DE RELIEVE (subcrestas y vaguadas)")
    pts_ejes_n = [q for _, p in n_canales for q in p]
    pts_ejes_o = [q for p in ejes_o.values() for q in p]
    rej_n, rej_o = Rejilla(pts_ejes_n), Rejilla(pts_ejes_o or [(0, 0, 0)])
    ejes_n_geom = [p for _, p in n_canales]
    ejes_o_geom = list(ejes_o.values())

    L_ejes_n = sum(largo(p) for p in ejes_n_geom)
    L_ejes_o = sum(largo(p) for p in ejes_o_geom)

    # El original mezcla divisorias y laderas en GF_Ridges. Aqui se comparan
    # LADERAS con laderas: meterle sus divisorias al monton inflaba su longitud
    # total y su linea mas larga (454 m es una divisoria, no una ladera), y era
    # de donde salia el falso "nos falta un 20 % de relieve".
    o_div, o_lad = (separar_relieve(o_relieve, ejes_o_geom) if ejes_o_geom
                    else ([], list(o_relieve)))

    res["relieve"] = {}
    for cual, lst, rej, ejes, L_ejes in (
            ("nuestro", n_relieve, rej_n, ejes_n_geom, L_ejes_n),
            ("original (solo laderas)", o_lad, rej_o, ejes_o_geom, L_ejes_o)):
        if not lst or not ejes:
            continue
        sobre, dist, largos, angs = [], [], [], []
        for _at, p in lst:
            alto, bajo = extremos(p)
            d_bajo, q = rej.cercano(bajo)
            if q is not None:
                sobre.append(alto[2] - q[2])
            dist.append(rej.cercano(alto)[0])
            largos.append(largo(p))
            a = angulo(p, rej, ejes)
            if a is not None:
                angs.append(a)
        d = {"n": len(lst),
             "longitud_total": sum(largos),
             "espaciado_m": L_ejes / max(1, len(lst)),
             "angulo_medio": (sum(angs) / len(angs)) if angs else None}
        res["relieve"][cual] = d
        print("   --- %s ---" % cual)
        print("     lineas                              %d" % d["n"])
        print("     longitud total                      %.1f m" % d["longitud_total"])
        print("     1 linea cada                        %.1f m de cauce"
              % d["espaciado_m"])
        print("     angulo medio con el eje             %.1f grados"
              % (d["angulo_medio"] or float("nan")))
        print("     longitud de cada linea              %s" % resumen(largos))
        print("     cota del extremo alto sobre el cauce %s" % resumen(sobre))
        print("     distancia en planta alto -> cauce   %s" % resumen(dist))

    # --------------------------------------------------------- 3b divisorias
    # El original las mezcla con las laderas en `GF_Ridges`; hay que sacarlas
    # para comparar como con como. Nuestras 13 sirven de patron de calibracion:
    # el clasificador tiene que reconocerlas TODAS y no llamar divisoria a
    # ninguna de nuestras laderas.
    print("\n3b) DIVISORIAS DE CUENCA (el original las mezcla en %s)"
          % CAPA_RELIEVE_ORIG)
    res["divisorias"] = {}
    if ejes_o_geom:
        falsos = sum(1 for _at, p in n_relieve if es_divisoria(p, ejes_n_geom))
        aciertos = sum(1 for _at, p in n_divisorias
                       if es_divisoria(p, ejes_n_geom))
        print("   calibracion sobre lo NUESTRO, donde se sabe la respuesta: "
              "reconoce %d de %d divisorias y llama divisoria a %d de %d "
              "laderas" % (aciertos, len(n_divisorias), falsos, len(n_relieve)))
        if aciertos < len(n_divisorias) or falsos:
            print("   AVISO: el clasificador falla sobre nuestros propios "
                  "datos; las cifras del original que siguen NO son fiables")
        o_div, o_lad = separar_relieve(o_relieve, ejes_o_geom)
        for cual, lst, ejes in (("nuestro", n_divisorias, ejes_n_geom),
                                ("original", o_div, ejes_o_geom)):
            if not lst:
                continue
            largos = [largo(p) for _at, p in lst]
            ps = [x[0] for _at, p in lst for x in pend_segmentos(p)]
            ps.sort()
            seg = [math.dist(p[i][:2], p[i + 1][:2])
                   for _at, p in lst for i in range(len(p) - 1)]
            vv = sorted(vaiven(p) for _at, p in lst)
            gir = sorted(giro_extremo(p) for _at, p in lst)
            lad = pendiente_de_ladera([q for _at, p in lst for q in p], ejes)
            la = sorted(x for x, k in lad if k == 0)
            lb = sorted(x for x, k in lad if k == 1)
            d = {"n": len(lst), "longitud_total": sum(largos),
                 "pend_p50": ps[len(ps) // 2] if ps else None,
                 "pend_p90": ps[int(len(ps) * .9)] if ps else None,
                 "pend_max": ps[-1] if ps else None,
                 "pct_sobre_33": (100.0 * sum(1 for x in ps if x > 33) / len(ps)
                                  if ps else None),
                 "espaciado_vertices": resumen(seg),
                 "meseta_max": max(meseta(p) for _at, p in lst),
                 "vaiven_total": sum(vv), "vaiven_p50": vv[len(vv) // 2],
                 "vaiven_max": vv[-1],
                 "giro_p50": gir[len(gir) // 2], "giro_max": gir[-1],
                 "ladera_A_max": la[-1] if la else None,
                 "ladera_B_max": lb[-1] if lb else None,
                 "ladera_A_p90": la[int(len(la) * .9)] if la else None,
                 "ladera_B_p90": lb[int(len(lb) * .9)] if lb else None}
            res["divisorias"][cual] = d
            print("   --- %s ---" % cual)
            print("     lineas / longitud total             %d / %.0f m"
                  % (d["n"], d["longitud_total"]))
            print("     longitud de cada una                %s" % resumen(largos))
            print("     pendiente vertice a vertice (%%)     p50=%.1f p90=%.1f "
                  "MAX=%.1f" % (d["pend_p50"], d["pend_p90"], d["pend_max"]))
            print("     tramos por encima del 33 %%          %.2f %%"
                  % d["pct_sobre_33"])
            print("     meseta mas larga                    %d vert."
                  % d["meseta_max"])
            print("     VAIVEN total / p50 / max            %.1f / %.1f / %.1f m"
                  % (d["vaiven_total"], d["vaiven_p50"], d["vaiven_max"]))
            print("     GIRO en los ultimos 20 m  p50/max   %.1f / %.1f grados"
                  % (d["giro_p50"], d["giro_max"]))
            if la and lb:
                print("     PENDIENTE DE LADERA a los dos lados p90=%.1f/%.1f "
                      "MAX=%.1f/%.1f %%" % (d["ladera_A_p90"], d["ladera_B_p90"],
                                            d["ladera_A_max"], d["ladera_B_max"]))
            print("     espaciado entre vertices            %s"
                  % d["espaciado_vertices"])
        print("   resto del original (lineas de ladera): %d, %.0f m"
              % (len(o_lad), sum(largo(p) for _at, p in o_lad)))
    else:
        print("   sin ejes del original emparejados: no se puede separar")

    # --------------------------------------------------- 4 defectos de forma
    print("\n4) DEFECTOS DE FORMA (una diferencia de FORMA siempre es un bug)")
    z_min_n = min((q[2] for _, p in n_canales for q in p), default=None)
    z_min_o = min((q[2] for p in ejes_o.values() for q in p), default=None)
    res["defectos"] = {}
    for cual, grupos, z_min in (
            ("nuestro", [("GRD_SubRidges", capa_nuestra(grd, "GRD_SubRidges")),
                         ("GRD_Swales", capa_nuestra(grd, "GRD_Swales")),
                         ("GRD_Ridges", n_divisorias)], z_min_n),
            ("original", [(CAPA_RELIEVE_ORIG, o_relieve)], z_min_o)):
        for nom, lst in grupos:
            if not lst:
                continue
            peor, n_cien, n_bajo, peor_meseta, n_vaiven = 0.0, 0, 0, 1, 0
            detalle = []
            for at, p in lst:
                ps = pend_segmentos(p)
                pmax = max((x[0] for x in ps), default=0.0)
                peor = max(peor, pmax)
                if pmax > 100.0:
                    n_cien += 1
                    detalle.append((pmax, at.get("fid"), at.get("channel"),
                                    at.get("index")))
                if z_min is not None and min(q[2] for q in p) < z_min - 0.01:
                    n_bajo += 1
                peor_meseta = max(peor_meseta, meseta(p))
                if vaiven(p) > 0.5:
                    n_vaiven += 1
            clave = "%s/%s" % (cual, nom)
            res["defectos"][clave] = {
                "peor_pendiente_pct": peor, "lineas_sobre_100pct": n_cien,
                "lineas_bajo_el_cauce": n_bajo,
                "meseta_max_vertices": peor_meseta, "lineas_con_vaiven": n_vaiven}
            print("   %-9s %-16s peor=%7.1f%%  >100%%=%-3d  bajo el cauce=%-3d"
                  "  meseta=%-3d vert.  vaiven=%d"
                  % (cual, nom, peor, n_cien, n_bajo, peor_meseta, n_vaiven))
            for x in sorted(detalle, reverse=True)[:6]:
                print("        %8.1f%%  fid=%-5s canal=%-10s idx=%s" % x)

    if salida_json:
        with open(salida_json, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2, ensure_ascii=False)
        print("\nInforme en %s" % salida_json)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("carpeta", help="carpeta del ejemplo")
    ap.add_argument("--json", dest="salida", help="guarda el informe en JSON")
    args = ap.parse_args()
    informe(args.carpeta, args.salida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
