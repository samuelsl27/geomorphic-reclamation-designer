#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sube el numero de version en TODOS los sitios a la vez.

    python scripts/bump_version.py 1.0.18
    python scripts/bump_version.py patch      # 1.0.17 -> 1.0.18
    python scripts/bump_version.py minor      # 1.0.17 -> 1.1.0
    python scripts/bump_version.py major      # 1.0.17 -> 2.0.0
    python scripts/bump_version.py 1.0.18 --seco   # solo dice que haria

La version vive en CINCO ficheros. Que se descoordinen es una de esas cosas
que cuestan media tarde: QGIS lee metadata.txt, el panel muestra dock.VERSION y
la guia imprime la suya. build_zip.py se niega a empaquetar si no coinciden.

pyproject.toml se anadio despues: se habia quedado en 1.0.17 mientras el resto
subia, porque no lo tocaba nadie y build_zip.py no lo comprueba (no viaja en el
zip). No rompe la instalacion, pero es el numero que ven las herramientas de
empaquetado y quien lee el repositorio.
"""

import argparse
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAQ = os.path.join(RAIZ, "src", "geomorphic_reclamation_designer")

# (ruta, patron con un grupo para la version, plantilla de sustitucion)
SITIOS = [
    (os.path.join(PAQ, "metadata.txt"),
     r"^(version\s*=\s*)(.+)$", r"\g<1>{v}", re.M),
    (os.path.join(PAQ, "__init__.py"),
     r'^(__version__\s*=\s*")([^"]+)(")', r"\g<1>{v}\g<3>", re.M),
    (os.path.join(PAQ, "gui", "dock.py"),
     r'^(VERSION\s*=\s*")([^"]+)(")', r"\g<1>{v}\g<3>", re.M),
    (os.path.join(RAIZ, "scripts", "genera_guia.py"),
     r'^(VER\s*=\s*")([^"]+)(")', r"\g<1>{v}\g<3>", re.M),
    (os.path.join(RAIZ, "pyproject.toml"),
     r'^(version\s*=\s*")([^"]+)(")', r"\g<1>{v}\g<3>", re.M),
]


def actual():
    with open(SITIOS[0][0], encoding="utf-8") as fh:
        m = re.search(r"^version\s*=\s*(.+)$", fh.read(), re.M)
    return m.group(1).strip()


def siguiente(ver, parte):
    try:
        may, men, par = (int(x) for x in ver.split("."))
    except ValueError:
        raise SystemExit(f"ERROR: no se puede incrementar '{ver}' "
                         "(no es X.Y.Z). Da la version completa.")
    return {"major": f"{may + 1}.0.0",
            "minor": f"{may}.{men + 1}.0",
            "patch": f"{may}.{men}.{par + 1}"}[parte]


def main():
    ap = argparse.ArgumentParser(description="Sube la version del complemento.")
    ap.add_argument("version", help="X.Y.Z, o 'major' / 'minor' / 'patch'")
    ap.add_argument("--seco", action="store_true", help="no escribir nada")
    args = ap.parse_args()

    vieja = actual()
    nueva = (siguiente(vieja, args.version)
             if args.version in ("major", "minor", "patch") else args.version)

    if not re.fullmatch(r"\d+\.\d+\.\d+", nueva):
        raise SystemExit(f"ERROR: '{nueva}' no tiene la forma X.Y.Z")
    if nueva == vieja:
        raise SystemExit(f"La version ya es {nueva}. Nada que hacer.")

    print(f"  {vieja}  ->  {nueva}\n")
    tocados = 0
    for ruta, patron, plantilla, banderas in SITIOS:
        if not os.path.exists(ruta):
            print(f"  --  {os.path.relpath(ruta, RAIZ)} (no existe)")
            continue
        with open(ruta, encoding="utf-8") as fh:
            texto = fh.read()
        nuevo, n = re.subn(patron, plantilla.format(v=nueva), texto,
                           count=1, flags=banderas)
        if n:
            if not args.seco:
                with open(ruta, "w", encoding="utf-8") as fh:
                    fh.write(nuevo)
            print(f"  OK  {os.path.relpath(ruta, RAIZ)}")
            tocados += 1
        else:
            print(f"  !!  {os.path.relpath(ruta, RAIZ)}: no encontre la version")

    if args.seco:
        print("\n  (modo seco: no se ha escrito nada)")
        return 0

    print(f"\n  {tocados} ficheros actualizados.\n")
    print("  Siguiente:")
    print(f"    1. anota los cambios en CHANGELOG.md bajo [{nueva}]")
    print("    2. python scripts/genera_guia.py")
    print("    3. pytest -q")
    print("    4. python scripts/build_zip.py")
    print(f'    5. git commit -am "chore: version {nueva}"'
          f' && git tag -a v{nueva} -m "v{nueva}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
