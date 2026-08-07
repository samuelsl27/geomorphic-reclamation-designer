#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera el .zip instalable en QGIS.

    python scripts/build_zip.py                # -> dist/geomorphic_reclamation_designer_v1.0.17.zip
    python scripts/build_zip.py --deploy       # ademas lo instala en el perfil
    python scripts/build_zip.py --guia         # regenera la guia antes de empaquetar
    python scripts/build_zip.py --salida C:\\x  # otra carpeta de salida

El zip contiene UNA sola carpeta raiz, `geomorphic_reclamation_designer/`, que es lo que QGIS
espera en "Instalar a partir de ZIP". Se excluye todo lo que no es del
complemento (tests, cache, ficheros de desarrollo).

Antes de empaquetar comprueba que la version coincide en todos los sitios: un
zip con metadata.txt y __init__.py descoordinados es una tarde perdida buscando
por que QGIS no ve la version nueva.
"""

import argparse
import os
import re
import subprocess
import sys
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAQUETE = "geomorphic_reclamation_designer"
ORIGEN = os.path.join(RAIZ, "src", PAQUETE)

# Nada de esto viaja dentro del complemento
EXCLUIR_DIR = {"__pycache__", ".git", ".pytest_cache", ".ruff_cache",
               ".mypy_cache", "tests", ".idea", ".vscode"}
EXCLUIR_EXT = {".pyc", ".pyo", ".pyd", ".bak", ".orig", ".rej", ".log",
               ".swp", ".swo"}
EXCLUIR_NOMBRE = {".DS_Store", "Thumbs.db", "desktop.ini", ".gitignore",
                  ".gitkeep"}


# ------------------------------------------------------------------ versiones

def version_metadata():
    ruta = os.path.join(ORIGEN, "metadata.txt")
    with open(ruta, encoding="utf-8") as fh:
        m = re.search(r"^version\s*=\s*(.+)$", fh.read(), re.M)
    if not m:
        raise SystemExit("ERROR: no encuentro 'version=' en metadata.txt")
    return m.group(1).strip()


def version_init():
    ruta = os.path.join(ORIGEN, "__init__.py")
    with open(ruta, encoding="utf-8") as fh:
        m = re.search(r'__version__\s*=\s*["\'](.+?)["\']', fh.read())
    return m.group(1).strip() if m else None


def version_dock():
    ruta = os.path.join(ORIGEN, "gui", "dock.py")
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as fh:
        m = re.search(r'^VERSION\s*=\s*["\'](.+?)["\']', fh.read(), re.M)
    return m.group(1).strip() if m else None


def version_guia():
    ruta = os.path.join(RAIZ, "scripts", "genera_guia.py")
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as fh:
        m = re.search(r'^VER\s*=\s*["\'](.+?)["\']', fh.read(), re.M)
    return m.group(1).strip() if m else None


def comprobar_versiones():
    """Falla si la version no es la misma en todos los sitios."""
    ref = version_metadata()
    otras = {"__init__.py": version_init(),
             "gui/dock.py": version_dock(),
             "scripts/genera_guia.py": version_guia()}
    malas = {k: v for k, v in otras.items() if v is not None and v != ref}
    if malas:
        print(f"ERROR: metadata.txt dice {ref}, pero:")
        for k, v in malas.items():
            print(f"       {k} dice {v}")
        print("\n       Ejecuta:  python scripts/bump_version.py " + ref)
        raise SystemExit(1)
    return ref


# ------------------------------------------------------------------ empaquetar

def se_excluye(ruta_rel, nombre):
    partes = ruta_rel.replace("\\", "/").split("/")
    if any(p in EXCLUIR_DIR for p in partes):
        return True
    if nombre in EXCLUIR_NOMBRE:
        return True
    return os.path.splitext(nombre)[1].lower() in EXCLUIR_EXT


def ficheros():
    for base, dirs, files in os.walk(ORIGEN):
        dirs[:] = [d for d in dirs if d not in EXCLUIR_DIR]
        for f in sorted(files):
            completa = os.path.join(base, f)
            rel = os.path.relpath(completa, ORIGEN)
            if not se_excluye(rel, f):
                yield completa, rel


def comprobar_esenciales():
    faltan = [f for f in ("__init__.py", "metadata.txt", "plugin.py", "icon.png")
              if not os.path.exists(os.path.join(ORIGEN, f))]
    if faltan:
        raise SystemExit("ERROR: faltan ficheros esenciales: " + ", ".join(faltan))
    guia = os.path.join(ORIGEN, "help", "guide.html")
    if not os.path.exists(guia):
        print("AVISO: no existe help/guide.html. Ejecuta scripts/genera_guia.py")


def compila(rutas):
    """Comprueba que todo el Python del complemento al menos compila.

    Se compila en memoria y no a disco: asi no ensucia el arbol de fuentes con
    .pyc ni depende de que se pueda escribir en ningun sitio.
    """
    fallos = []
    for completa, rel in rutas:
        if completa.endswith(".py"):
            try:
                with open(completa, encoding="utf-8") as fh:
                    compile(fh.read(), completa, "exec")
            except SyntaxError as e:
                fallos.append(f"{rel}:{e.lineno}: {e.msg}")
    if fallos:
        print("ERROR: hay ficheros que no compilan:")
        for f in fallos:
            print("  " + f)
        raise SystemExit(1)


def construir(destino, version):
    os.makedirs(destino, exist_ok=True)
    zip_ruta = os.path.join(destino, f"{PAQUETE}_v{version}.zip")
    rutas = list(ficheros())
    compila(rutas)
    if os.path.exists(zip_ruta):
        os.remove(zip_ruta)
    with zipfile.ZipFile(zip_ruta, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for completa, rel in rutas:
            z.write(completa, os.path.join(PAQUETE, rel).replace("\\", "/"))
    return zip_ruta, len(rutas)


def verificar(zip_ruta):
    """Un zip que QGIS rechaza es peor que no tener zip."""
    with zipfile.ZipFile(zip_ruta) as z:
        malo = z.testzip()
        if malo:
            raise SystemExit(f"ERROR: el zip esta corrupto en {malo}")
        nombres = z.namelist()
        raices = {n.split("/")[0] for n in nombres}
        if raices != {PAQUETE}:
            raise SystemExit(f"ERROR: el zip debe tener UNA sola carpeta raiz "
                             f"'{PAQUETE}/', tiene {sorted(raices)}")
        for imprescindible in (f"{PAQUETE}/__init__.py", f"{PAQUETE}/metadata.txt"):
            if imprescindible not in nombres:
                raise SystemExit(f"ERROR: falta {imprescindible} en el zip")
        if any("__pycache__" in n or n.endswith(".pyc") for n in nombres):
            raise SystemExit("ERROR: se ha colado __pycache__ en el zip")


# ------------------------------------------------------------------ principal

def main():
    ap = argparse.ArgumentParser(description="Genera el zip instalable en QGIS.")
    ap.add_argument("--salida", default=os.path.join(RAIZ, "dist"),
                    help="carpeta de salida (por defecto dist/)")
    ap.add_argument("--deploy", action="store_true",
                    help="ademas instala en el perfil de QGIS")
    ap.add_argument("--guia", action="store_true",
                    help="regenera help/guide.html antes de empaquetar")
    args = ap.parse_args()

    version = comprobar_versiones()
    comprobar_esenciales()

    if args.guia:
        print("Regenerando la guia...")
        subprocess.run([sys.executable,
                        os.path.join(RAIZ, "scripts", "genera_guia.py")],
                       check=True)

    zip_ruta, n = construir(args.salida, version)
    verificar(zip_ruta)

    mb = os.path.getsize(zip_ruta) / (1024 * 1024)
    print(f"\n  OK  {zip_ruta}")
    print(f"      version {version} · {n} ficheros · {mb:.2f} MB")
    print("\n      QGIS -> Complementos -> Administrar e instalar complementos")
    print("           -> Instalar a partir de ZIP")

    if args.deploy:
        print()
        sys.path.insert(0, os.path.join(RAIZ, "scripts"))
        import deploy_local
        deploy_local.instalar()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
