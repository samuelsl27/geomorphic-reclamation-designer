#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detecta el servidor MCP de QGIS instalado y escribe .mcp.json / .vscode/mcp.json.

    python scripts/configurar_mcp.py             # busca y escribe
    python scripts/configurar_mcp.py --seco      # solo dice que encontraria
    python scripts/configurar_mcp.py --ruta C:\\...\\qgis_mcp\\src\\qgis_mcp

El complemento `qgis_mcp_plugin` vive dentro del perfil de QGIS y abre un socket;
el SERVIDOR MCP es un proceso aparte que habla con ese socket y que arranca el
editor. Este guion busca los dos y deja la configuracion coherente.
"""

import argparse
import json
import os
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUERTO = "9876"


def raiz_qgis():
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
        return os.path.join(base, "QGIS")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/QGIS")
    return os.path.expanduser("~/.local/share/QGIS")


def buscar_complemento():
    """La parte que corre DENTRO de QGIS."""
    base = raiz_qgis()
    hallazgos = []
    if os.path.isdir(base):
        for mayor in sorted(os.listdir(base), reverse=True):
            praiz = os.path.join(base, mayor, "profiles")
            if not os.path.isdir(praiz):
                continue
            for perfil in sorted(os.listdir(praiz)):
                p = os.path.join(praiz, perfil, "python", "plugins",
                                 "qgis_mcp_plugin")
                if os.path.isdir(p):
                    hallazgos.append((f"{mayor}/profiles/{perfil}", p))
    return hallazgos


def buscar_servidor():
    """La parte que corre FUERA de QGIS: qgis_mcp_server.py."""
    candidatos = []
    inicios = [os.path.expanduser("~"), RAIZ, os.path.dirname(RAIZ)]
    if sys.platform.startswith("win"):
        inicios += ["C:/", "<ruta de trabajo>", "<ruta de trabajo>"]
    vistos = set()
    for inicio in inicios:
        if not os.path.isdir(inicio):
            continue
        for base, dirs, files in os.walk(inicio):
            # no bajar por sitios donde no va a estar y que tardan una eternidad
            dirs[:] = [d for d in dirs
                       if not d.startswith(".")
                       and d not in ("node_modules", "__pycache__", "Windows",
                                     "Program Files", "Program Files (x86)",
                                     "site-packages", "AppData")]
            if base.count(os.sep) - inicio.count(os.sep) > 5:
                dirs[:] = []
                continue
            if "qgis_mcp_server.py" in files and base not in vistos:
                vistos.add(base)
                candidatos.append(base)
    return candidatos


def config(directorio):
    tiene_uv = shutil.which("uv") is not None
    if tiene_uv:
        cmd, args = "uv", ["--directory", directorio.replace("\\", "/"),
                           "run", "qgis_mcp_server.py"]
    else:
        cmd = sys.executable.replace("\\", "/")
        args = [os.path.join(directorio, "qgis_mcp_server.py").replace("\\", "/")]
    return {"mcpServers": {"qgis": {
        "command": cmd, "args": args,
        "env": {"QGIS_MCP_HOST": "127.0.0.1", "QGIS_MCP_PORT": PUERTO}}}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ruta", help="carpeta que contiene qgis_mcp_server.py")
    ap.add_argument("--seco", action="store_true")
    args = ap.parse_args()

    print("Complemento qgis_mcp_plugin (dentro de QGIS):")
    comp = buscar_complemento()
    if comp:
        for etiqueta, ruta in comp:
            print(f"  OK  {etiqueta}\n      {ruta}")
    else:
        print("  !!  no encontrado. Instalalo en el perfil de QGIS que uses:")
        print("      https://github.com/jjsantos01/qgis_mcp")

    print("\nServidor MCP (fuera de QGIS):")
    if args.ruta:
        dirs = [args.ruta]
    else:
        print("  buscando qgis_mcp_server.py, esto tarda un poco...")
        dirs = buscar_servidor()
    if not dirs:
        print("  !!  no encontrado. Clona el repositorio y vuelve a ejecutar:")
        print("      git clone https://github.com/jjsantos01/qgis_mcp")
        print("      python scripts/configurar_mcp.py "
              "--ruta <...>/qgis_mcp/src/qgis_mcp")
        return 1
    for d in dirs:
        print(f"  OK  {d}")
    elegido = dirs[0]
    if len(dirs) > 1:
        print(f"\n  (hay varios; uso el primero: {elegido})")

    cfg = config(elegido)
    texto = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
    print("\nConfiguracion:\n" + texto)

    if args.seco:
        print("(modo seco: no se ha escrito nada)")
        return 0

    for destino in (os.path.join(RAIZ, ".mcp.json"),
                    os.path.join(RAIZ, ".vscode", "mcp.json")):
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as fh:
            fh.write(texto)
        print(f"  escrito {os.path.relpath(destino, RAIZ)}")

    print("\nAhora: abre QGIS, activa el complemento qgis_mcp_plugin y pulsa")
    print("'Start server'. Despues, en el editor, comprueba con la herramienta")
    print("'ping' del servidor qgis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
