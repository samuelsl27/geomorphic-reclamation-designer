#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Copia el complemento al perfil de QGIS, para iterar rapido sin hacer el zip.

    python scripts/deploy_local.py            # copia una vez
    python scripts/deploy_local.py --watch    # recopia cada vez que guardas
    python scripts/deploy_local.py --perfil QGIS4/profiles/otro
    python scripts/deploy_local.py --listar   # solo dice que perfiles encuentra

OJO CON EL PERFIL. En esta maquina conviven QGIS3 y QGIS4 y el activo es
**QGIS4**. Instalar en el equivocado significa editar codigo que nadie ejecuta.
Por eso, si hay mas de uno, este guion prefiere QGIS4 y AVISA de lo que ha
elegido.

Despues de copiar, en QGIS:

    from qgis import utils; utils.reloadPlugin("geomorphic_reclamation_designer")

y si has tocado core/params.py, **reinicia QGIS**: la recarga en caliente deja
GlobalSettings viejo en memoria (ver context/07_entorno_qgis_mcp.md).
"""

import argparse
import os
import shutil
import sys
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAQUETE = "geomorphic_reclamation_designer"
ORIGEN = os.path.join(RAIZ, "src", PAQUETE)

EXCLUIR = shutil.ignore_patterns(
    "__pycache__", "*.pyc", "*.pyo", ".pytest_cache", ".ruff_cache",
    "tests", ".git", "*.bak", "*.orig", ".DS_Store", "Thumbs.db")


def raiz_qgis():
    """Carpeta de configuracion de QGIS segun el sistema operativo."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
        return os.path.join(base, "QGIS")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/QGIS")
    return os.path.expanduser("~/.local/share/QGIS")


def perfiles():
    """Todas las carpetas de complementos que encuentre, QGIS4 primero."""
    base = raiz_qgis()
    encontrados = []
    if os.path.isdir(base):
        for mayor in sorted(os.listdir(base), reverse=True):   # QGIS4 antes que QGIS3
            praiz = os.path.join(base, mayor, "profiles")
            if not os.path.isdir(praiz):
                continue
            for perfil in sorted(os.listdir(praiz)):
                ruta = os.path.join(praiz, perfil, "python", "plugins")
                if os.path.isdir(os.path.dirname(os.path.dirname(ruta))):
                    encontrados.append((f"{mayor}/profiles/{perfil}", ruta))
    return encontrados


def elegir(preferido=None):
    encontrados = perfiles()
    if not encontrados:
        raise SystemExit(
            "ERROR: no encuentro ninguna instalacion de QGIS en\n"
            f"       {raiz_qgis()}\n"
            "       Usa --destino para dar la ruta a mano.")
    if preferido:
        for etiqueta, ruta in encontrados:
            if preferido.replace("\\", "/") in etiqueta:
                return etiqueta, ruta
        raise SystemExit(f"ERROR: no encuentro el perfil '{preferido}'.\n"
                         "       Perfiles disponibles:\n         " +
                         "\n         ".join(e for e, _ in encontrados))
    # sin preferencia: el primero (QGIS mayor mas alto, perfil 'default' antes)
    encontrados.sort(key=lambda x: (x[0].split("/")[0], "default" not in x[0]),
                     reverse=True)
    return encontrados[0]


def copiar(destino_plugins):
    destino = os.path.join(destino_plugins, PAQUETE)
    os.makedirs(destino_plugins, exist_ok=True)
    if os.path.exists(destino):
        shutil.rmtree(destino)
    shutil.copytree(ORIGEN, destino, ignore=EXCLUIR)
    n = sum(len(f) for _, _, f in os.walk(destino))
    return destino, n


def instalar(preferido=None, destino_manual=None, silencioso=False):
    if destino_manual:
        etiqueta, plugins = "(manual)", destino_manual
    else:
        etiqueta, plugins = elegir(preferido)
    destino, n = copiar(plugins)
    if not silencioso:
        print(f"  OK  instalado en {etiqueta}")
        print(f"      {destino}")
        print(f"      {n} ficheros")
        otros = [e for e, _ in perfiles() if e != etiqueta]
        if otros and not destino_manual:
            print(f"\n      AVISO: hay mas perfiles ({', '.join(otros)}).")
            print("             Si QGIS no ve el cambio, comprueba cual usas:")
            print("             from qgis.core import QgsApplication")
            print("             print(QgsApplication.qgisSettingsDirPath())")
        print('\n      En QGIS:  from qgis import utils'
              '; utils.reloadPlugin("geomorphic_reclamation_designer")')
        print("      Si tocaste core/params.py: REINICIA QGIS.")
    return destino


def firma():
    """Marca de tiempo del arbol de fuentes, para el modo --watch."""
    ultima = 0.0
    for base, dirs, files in os.walk(ORIGEN):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                continue
            try:
                ultima = max(ultima, os.path.getmtime(os.path.join(base, f)))
            except OSError:
                pass
    return ultima


def main():
    ap = argparse.ArgumentParser(
        description="Copia el complemento al perfil de QGIS.")
    ap.add_argument("--perfil", help="p.ej. QGIS4/profiles/default")
    ap.add_argument("--destino", help="ruta completa a la carpeta plugins")
    ap.add_argument("--watch", action="store_true",
                    help="recopiar cada vez que cambie algo")
    ap.add_argument("--listar", action="store_true",
                    help="solo listar los perfiles encontrados")
    args = ap.parse_args()

    if args.listar:
        for etiqueta, ruta in perfiles():
            print(f"  {etiqueta:32s} {ruta}")
        return 0

    instalar(args.perfil, args.destino)

    if args.watch:
        print("\n  Vigilando cambios (Ctrl+C para salir)...")
        anterior = firma()
        try:
            while True:
                time.sleep(1.0)
                actual = firma()
                if actual > anterior:
                    anterior = actual
                    instalar(args.perfil, args.destino, silencioso=True)
                    print(f"  {time.strftime('%H:%M:%S')}  recopiado")
        except KeyboardInterrupt:
            print("\n  Fin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
