#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detecta la instalacion de QGIS y ajusta .vscode/settings.json.

    python scripts/configurar_vscode.py            # detecta y escribe
    python scripts/configurar_vscode.py --seco     # solo dice que haria
    python scripts/configurar_vscode.py --listar   # que instalaciones encuentra
    python scripts/configurar_vscode.py --qgis "C:\\Program Files\\QGIS 3.44.6"

Sin esto, Pylance subraya en rojo todos los `from qgis.core import ...`. Es
cosmetico —no impide ejecutar nada— pero convierte el editor en un arbol de
Navidad y acabas ignorando los avisos de verdad.

OJO: en esta maquina conviven varias versiones de QGIS. Este guion elige la
MAS ALTA por defecto y te dice cual ha elegido. Comprueba que es la misma con
la que trabajas: instalar o depurar contra la version equivocada es la forma
mas eficiente de perder una tarde (ver context/07_entorno_qgis_mcp.md).
"""

import argparse
import glob
import json
import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AJUSTES = os.path.join(RAIZ, ".vscode", "settings.json")


def _clave_version(nombre):
    """'QGIS 4.2.0' -> (4, 2, 0), para poder ordenar de mayor a menor."""
    nums = re.findall(r"\d+", nombre)
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def instalaciones():
    """Todas las instalaciones de QGIS que encuentre, la mas nueva primero."""
    patrones = []
    if sys.platform.startswith("win"):
        # En Windows las variables de entorno no distinguen mayusculas, asi que
        # PROGRAMFILES es lo mismo que ProgramFiles y ademas contenta al linter.
        for pf in (os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                   os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"),
                   r"C:\OSGeo4W", r"C:\OSGeo4W64"):
            patrones += [os.path.join(pf, "QGIS*"), pf]
    elif sys.platform == "darwin":
        patrones += ["/Applications/QGIS*.app/Contents/MacOS"]
    else:
        patrones += ["/usr", "/usr/local"]

    vistas, salida = set(), []
    for patron in patrones:
        for ruta in glob.glob(patron):
            if not os.path.isdir(ruta):
                continue
            # lo que confirma que es una instalacion: la carpeta python de qgis
            for cand in (os.path.join(ruta, "apps", "qgis", "python"),
                         os.path.join(ruta, "apps", "qgis-ltr", "python"),
                         os.path.join(ruta, "share", "qgis", "python"),
                         os.path.join(ruta, "Resources", "python")):
                if os.path.isdir(cand) and ruta not in vistas:
                    vistas.add(ruta)
                    salida.append(ruta)
                    break
    salida.sort(key=lambda r: _clave_version(os.path.basename(r)), reverse=True)
    return salida


def rutas_de(base):
    """Las rutas que Pylance necesita, y el interprete de QGIS."""
    res = {"base": base, "extra": [], "interprete": None}

    for sub in ("apps/qgis/python", "apps/qgis-ltr/python",
                "share/qgis/python", "Resources/python"):
        p = os.path.join(base, *sub.split("/"))
        if os.path.isdir(p):
            res["extra"].append(p)
            if os.path.isdir(os.path.join(p, "plugins")):
                res["extra"].append(os.path.join(p, "plugins"))

    # site-packages de la version de Python que traiga esa instalacion
    for patron in ("apps/Python*/Lib/site-packages",
                   "apps/Python*/lib/python*/site-packages",
                   "lib/python*/site-packages"):
        for p in glob.glob(os.path.join(base, *patron.split("/"))):
            if os.path.isdir(p):
                res["extra"].append(p)

    for cand in ("bin/python-qgis.bat", "bin/python-qgis-ltr.bat",
                 "bin/python3.exe", "bin/python3", "bin/python"):
        p = os.path.join(base, *cand.split("/"))
        if os.path.exists(p):
            res["interprete"] = p
            break

    return res


def _sin_comentarios(texto):
    """settings.json lleva claves-comentario ('// Tests': '...'), que son JSON
    valido, pero por si alguien mete // de verdad, se limpian antes de parsear."""
    return re.sub(r'^\s*//.*$', '', texto, flags=re.M)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--qgis", help="ruta de la instalacion a usar")
    ap.add_argument("--seco", action="store_true")
    ap.add_argument("--listar", action="store_true")
    args = ap.parse_args()

    encontradas = instalaciones()
    if not encontradas:
        print("No encuentro ninguna instalacion de QGIS.")
        print("Pasa la ruta a mano:  --qgis \"C:\\Program Files\\QGIS 4.2.0\"")
        return 1

    print("Instalaciones de QGIS encontradas (la mas nueva primero):")
    for i, r in enumerate(encontradas):
        print(f"  {'->' if i == 0 else '  '} {r}")
    if args.listar:
        return 0

    base = args.qgis or encontradas[0]
    if not os.path.isdir(base):
        print(f"\nERROR: no existe {base}")
        return 1

    r = rutas_de(base)
    print(f"\nUsando: {base}")
    if len(encontradas) > 1 and not args.qgis:
        print("  AVISO: hay mas de una instalacion. Si trabajas con otra,")
        print("         vuelve a ejecutar con --qgis \"<ruta>\".")
    print(f"\nInterprete: {r['interprete'] or '(no encontrado)'}")
    print("extraPaths:")
    for p in r["extra"]:
        print(f"  {p}")

    if not os.path.exists(AJUSTES):
        print(f"\nERROR: no existe {AJUSTES}")
        return 1

    with open(AJUSTES, encoding="utf-8") as fh:
        texto = fh.read()
    cfg = json.loads(_sin_comentarios(texto))

    if r["interprete"]:
        cfg["python.defaultInterpreterPath"] = r["interprete"].replace("/", os.sep)
    cfg["python.analysis.extraPaths"] = ["./src"] + [
        p.replace("/", os.sep) for p in r["extra"]]

    if args.seco:
        print("\n(modo seco: no se ha escrito nada)")
        return 0

    with open(AJUSTES, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"\n  OK  {os.path.relpath(AJUSTES, RAIZ)} actualizado.")
    print("      Recarga la ventana de VSCode:")
    print("      Ctrl+Shift+P -> 'Developer: Reload Window'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
