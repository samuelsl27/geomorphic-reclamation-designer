#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Lee el proyecto NATIVO del programa original (.geo / .ggs) y lo traduce a
nuestras claves, para poder comparar ajuste a ajuste en vez de solo geometria.

    python scripts/leer_geo.py Ej_2_GeoFluv_File.geo
    python scripts/leer_geo.py Ej_2_GeoFluv_File.geo --comparar GRD_x.grd.json
    python scripts/leer_geo.py Ej_2_GeoFluv_File.geo --fusionar GRD_x.grd.json

POR QUE EXISTE. Al depurar el Ej_2 se vio que buena parte de la diferencia
geometrica no venia del motor sino de que los parametros de los tributarios se
habian tecleado en orden invertido (los de R1 en R4 y los de R2 en R3). Sin un
lector del fichero original eso solo se descubre a mano, canal a canal, y en el
siguiente ejemplo vuelve a pasar.

FORMATOS. Los dos son texto plano, una clave y un valor por linea:

- `.ggs`: solo los ajustes globales.
- `.geo`: `BEGIN PROJECT` con los globales y luego un bloque
  `BEGIN CHANNEL` ... `END CHANNEL` por canal.

UNIDADES, que es donde estan las trampas:

- En el `.geo` tres globales van en FRACCION y en el `.ggs` en TANTO POR CIENTO:
  `m_fMainMouthSlope` (-0.022 / -2.2), `m_fTargetDensityVar` (0.2 / 20) y
  `m_fCutFillMax|Min` (0.5 / 50). Se distingue por el formato, no por el valor.
  Ojo: `m_fUpstreamSlope`, dentro de los bloques de canal, va en % en ambos.
- La lluvia va en CENTIMETROS en los proyectos metricos (2.5 y 7.2 en el Ej_2,
  o sea 25 mm en 1 h con periodo de retorno 2 anos y 72 mm en 6 h con 50 anos,
  que es lo que corresponde al sureste peninsular). Con `--pulgadas` se aplica
  25.4 en lugar de 10, para proyectos hechos en unidades imperiales.
- La cabecera del `.geo` rotula el area como "square feet" aunque el proyecto
  sea metrico: es una etiqueta fija del programa, no un dato. No te fies de ella.
"""

import argparse
import json
import os
import shutil
import sys

MM_POR_CM = 10.0
MM_POR_PULGADA = 25.4

# clave del original -> (clave nuestra, factor si el fichero es .geo)
GLOBALES = {
    "m_fMaxDistToConnect": ("max_dist_conexion_canales", 1.0),
    "m_fMaxDistFromRidge": ("max_dist_cresta_cabecera", 1.0),
    "m_fMainMouthSlope": ("pendiente_desembocadura", 100.0),
    "m_fAChannelReach": ("reach_canal_A", 1.0),
    "m_fTargetDensity": ("dd_objetivo", 1.0),
    "m_fTargetDensityVar": ("dd_varianza_pct", 100.0),
    "m_fRidgeAngleBack": ("angulo_subcresta_deg", 1.0),
    "m_fNESlope": ("pendiente_NE_pct", 1.0),
    "m_fMaxSlope": ("pendiente_max_pct", 1.0),
    "m_fCutFillMax": ("var_max_corte_relleno_pct", 100.0),
    "m_fCutFillMin": ("var_min_corte_relleno_pct", 100.0),
    "m_fCutSwell": ("factor_esponjamiento", 1.0),
    "m_fFillShrink": ("factor_compactacion", 1.0),
    "m_fHeadElevTole": ("tol_cota_cabecera_m", 1.0),
    "m_fHeadSlopePertTole": ("tol_pendiente_cabecera_pct", 1.0),
}

# Estos dos van acompanados de un booleano y el original DEJA BASURA en el
# valor cuando el booleano esta a 0 (en el Ej_2, convexo_pct = 0 y
# convexo_swale_m = 50 con las dos casillas desmarcadas). Traducirlos sin mirar
# el booleano llena el informe de diferencias que no existen, y un comparador
# que da falsos positivos se deja de leer.
GLOBALES_CONDICIONADOS = {
    "m_fMaxDistPercentFromRidgeForSubridge": (
        "convexo_pct", "m_bMaxDistPercentFromRidgeForSubridge"),
    "m_fMaxDistFromRidgeForSubvalley": (
        "convexo_swale_m", "m_bMaxDistFromRidgeForSubvalley"),
}

CANAL = {
    "m_strDisplayName": ("nombre", None),
    "m_fUpstreamSlope": ("pendiente_cabecera_pct", 1.0),
    "m_fMaxVel": ("vel_max_agua", 1.0),
    "m_fW2DRatio": ("wd_pend_menor_004", 1.0),
    "m_fW2DRatio_A": ("wd_pend_mayor_004", 1.0),
    "m_fSinuosity_S": ("sinuosidad_menor_004", 1.0),
    "m_fSinuosity_A": ("sinuosidad_mayor_004", 1.0),
    "m_fRunoffCoef": ("coef_escorrentia", 1.0),
    "m_fAdditionalRunoffCoef": ("coef_escorrentia_adicional", 1.0),
    "m_fMaxDistFromRidge": ("dist_cresta_swale_m", 1.0),
    "m_fMaxDistPercentFromRidgeForSubridge": ("convexo_pct_canal", 1.0),
    "m_iSinusoidRidgeSpacing": ("espaciado_subcrestas", 1.0),
    "m_fAdditionalArea": ("area_adicional_ha", 1.0),
}


def _num(txt):
    try:
        return float(txt)
    except ValueError:
        return txt


def _lineas(ruta):
    with open(ruta, encoding="latin-1") as fh:
        for cruda in fh:
            linea = cruda.strip()
            if not linea or linea.startswith("##"):
                continue
            partes = linea.split(None, 1)
            yield partes[0], (partes[1].strip() if len(partes) > 1 else "")


def leer(ruta, pulgadas=False):
    """(ajustes globales, [canales]) con NUESTRAS claves."""
    es_geo = os.path.splitext(ruta)[1].lower() == ".geo"
    factor_lluvia = MM_POR_PULGADA if pulgadas else MM_POR_CM
    glob_crudo, canales_crudos, actual = {}, [], None

    for clave, valor in _lineas(ruta):
        if clave == "BEGIN":
            if valor.upper() == "CHANNEL":
                actual = {}
            continue
        if clave == "END":
            if valor.upper() == "CHANNEL" and actual is not None:
                canales_crudos.append(actual)
                actual = None
            continue
        (actual if actual is not None else glob_crudo)[clave] = _num(valor)

    ajustes = {}
    for clave, (nuestra, factor) in GLOBALES.items():
        if clave in glob_crudo:
            v = glob_crudo[clave]
            ajustes[nuestra] = v * factor if es_geo else v
    for clave, (nuestra, bandera) in GLOBALES_CONDICIONADOS.items():
        if clave in glob_crudo and glob_crudo.get(bandera):
            ajustes[nuestra] = glob_crudo[clave]
    if "m_f2y1h" in glob_crudo:
        ajustes["p_2a_1h_mm"] = glob_crudo["m_f2y1h"] * factor_lluvia
    if "m_f50y6h" in glob_crudo:
        ajustes["p_50a_6h_mm"] = glob_crudo["m_f50y6h"] * factor_lluvia
    if "m_bNoPeaksOnRidges" in glob_crudo:
        ajustes["forzar_crestas_bajo_limite"] = bool(glob_crudo["m_bNoPeaksOnRidges"])
    if "m_bMaxDistFromRidgeForSubvalley" in glob_crudo:
        ajustes["convexo_swale_activo"] = bool(
            glob_crudo["m_bMaxDistFromRidgeForSubvalley"])
    if "m_bMaxDistPercentFromRidgeForSubridge" in glob_crudo:
        ajustes["convexo_modo"] = ("pct" if glob_crudo[
            "m_bMaxDistPercentFromRidgeForSubridge"] else "factor")

    canales = []
    for crudo in canales_crudos:
        c = {}
        for clave, (nuestra, factor) in CANAL.items():
            if clave in crudo:
                v = crudo[clave]
                c[nuestra] = v * factor if isinstance(v, float) and factor else v
        if "espaciado_subcrestas" in c:
            c["espaciado_subcrestas"] = int(c["espaciado_subcrestas"])
        c["usar_metodo_racional"] = bool(crudo.get("m_bUseRationalRunoff", 1))
        c["usar_racional_adicional"] = bool(crudo.get("m_bAdditionalCustomQpk", 0)) is False
        c["factores_aleatorios"] = bool(crudo.get("m_bRandomScales", 0))
        c["especificar_convexo"] = bool(
            crudo.get("m_bMaxDistPercentFromRidgeForSubridge", 0))
        c["convexo_modo_canal"] = "pct" if c["especificar_convexo"] else "factor"
        c["area_adicional_en_cabecera"] = not bool(crudo.get("m_iAdditionalAreaMethod", 0))
        # Las cotas solo valen si el usuario las FIJO a mano: si no, el fichero
        # guarda las que calculo el programa y meterlas seria clavar el
        # resultado en vez de calcularlo.
        c["cota_cabecera"] = (crudo.get("m_fManualHeadElev")
                              if crudo.get("m_bManualHeadElev") else None)
        c["cota_boca"] = (crudo.get("m_fManualMouthElev")
                          if crudo.get("m_bManualMouthElev") else None)
        if crudo.get("m_bCustomQpk"):
            c["qpk_manual_bankfull"] = crudo.get("m_fQpk2y1h")
            c["qpk_manual_flood"] = crudo.get("m_fQpk50y6h")
        canales.append(c)
    return ajustes, canales


# ------------------------------------------------------------------ comparar
def _dif(a, b, tol=1e-6):
    if isinstance(a, float) and isinstance(b, (int, float)):
        return abs(a - float(b)) > tol
    return a != b


def comparar(ajustes, canales, ruta_json):
    """Imprime las diferencias. Devuelve cuantas ha encontrado."""
    with open(ruta_json, encoding="utf-8") as fh:
        proy = json.load(fh)
    mios_g = proy.get("settings", proy)
    n = 0

    print("--- ajustes globales ---")
    for clave, valor in sorted(ajustes.items()):
        if clave not in mios_g:
            print("  %-34s original=%-12s (no existe en el nuestro)"
                  % (clave, valor))
            continue
        if _dif(valor, mios_g[clave]):
            print("  %-34s original=%-12s nuestro=%s"
                  % (clave, valor, mios_g[clave]))
            n += 1

    print("--- canales (emparejados por nombre) ---")
    mios_c = {c.get("nombre"): c for c in proy.get("canales", [])}
    for orig in canales:
        nombre = orig.get("nombre")
        mio = mios_c.get(nombre)
        if mio is None:
            print("  canal '%s' del original no esta en el proyecto" % nombre)
            n += 1
            continue
        for clave, valor in sorted(orig.items()):
            if clave == "nombre" or clave not in mio:
                continue
            if _dif(valor, mio[clave]):
                print("  %-10s %-30s original=%-10s nuestro=%s"
                      % (nombre, clave, valor, mio[clave]))
                n += 1
    sobra = set(mios_c) - {c.get("nombre") for c in canales}
    for nombre in sorted(sobra):
        print("  canal '%s' del proyecto no esta en el original" % nombre)
        n += 1
    return n


def fusionar(ajustes, canales, ruta_json):
    """Escribe en el .grd.json los valores del original. Deja copia .bak."""
    with open(ruta_json, encoding="utf-8") as fh:
        proy = json.load(fh)
    shutil.copy2(ruta_json, ruta_json + ".bak")

    destino = proy.get("settings", proy)
    for clave, valor in ajustes.items():
        if clave in destino:
            destino[clave] = valor
    mios = {c.get("nombre"): c for c in proy.get("canales", [])}
    for orig in canales:
        mio = mios.get(orig.get("nombre"))
        if mio is None:
            continue
        for clave, valor in orig.items():
            if clave != "nombre" and clave in mio:
                mio[clave] = valor
    with open(ruta_json, "w", encoding="utf-8") as fh:
        json.dump(proy, fh, indent=2, ensure_ascii=False)
    print("Escrito %s (copia previa en %s.bak)" % (ruta_json, ruta_json))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("origen", help="fichero .geo o .ggs del programa original")
    ap.add_argument("--comparar", metavar="GRD.json",
                    help="muestra las diferencias con un proyecto nuestro")
    ap.add_argument("--fusionar", metavar="GRD.json",
                    help="escribe los valores del original en el proyecto")
    ap.add_argument("--pulgadas", action="store_true",
                    help="la lluvia del original esta en pulgadas, no en cm")
    args = ap.parse_args()

    ajustes, canales = leer(args.origen, pulgadas=args.pulgadas)
    if args.comparar:
        n = comparar(ajustes, canales, args.comparar)
        print("\n%d diferencia(s)" % n)
        return 0
    if args.fusionar:
        fusionar(ajustes, canales, args.fusionar)
        return 0
    print(json.dumps({"settings": ajustes, "canales": canales},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
