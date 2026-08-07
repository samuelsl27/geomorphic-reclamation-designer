#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprueba las dos mitades del MCP de QGIS y escribe la configuracion.

    python scripts/configurar_mcp.py             # comprueba y escribe
    python scripts/configurar_mcp.py --seco      # solo informa, no escribe
    python scripts/configurar_mcp.py --version 0.10.0   # fijar a mano

El MCP son DOS piezas y la causa mas comun de que "no funcione" es que solo
este una:

  * el complemento `QGIS MCP` (nkarasiak/qgis-mcp), que vive DENTRO de QGIS y
    abre un socket en el 9876;
  * el servidor `qgis-mcp-server`, un proceso FUERA de QGIS que arranca el
    editor y traduce entre MCP y ese socket.

Las dos tienen numero de version y el complemento avisa si no coinciden, asi
que este guion lee la version del complemento instalado y fija esa misma
etiqueta en la configuracion, en vez de apuntar a `main` y quedar a merced de
lo que se publique manana.

El servidor NO se clona: `uvx` lo descarga y lo cachea desde la etiqueta de
GitHub, asi que la configuracion no lleva rutas de una maquina concreta y vale
igual para cualquiera que clone el repositorio.
"""

import argparse
import json
import os
import re
import shutil
import socket
import struct
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = "127.0.0.1"
PUERTO = 9876
PLANTILLA_ZIP = ("https://github.com/nkarasiak/qgis-mcp"
                 "/archive/refs/tags/v{ver}.zip")
CABECERA = struct.Struct(">I")


def raiz_qgis():
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~/AppData/Roaming")
        return os.path.join(base, "QGIS")
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/QGIS")
    return os.path.expanduser("~/.local/share/QGIS")


def buscar_complemento():
    """Devuelve [(etiqueta_perfil, ruta, version)] de la parte que va en QGIS.

    Se recorren los perfiles en orden inverso para que QGIS4 salga antes que
    QGIS3: el perfil activo de esta maquina es el 4 y instalar en el 3 es
    editar codigo que nadie ejecuta (ver context/07_entorno_qgis_mcp.md).
    """
    base = raiz_qgis()
    hallazgos = []
    if not os.path.isdir(base):
        return hallazgos
    for mayor in sorted(os.listdir(base), reverse=True):
        praiz = os.path.join(base, mayor, "profiles")
        if not os.path.isdir(praiz):
            continue
        for perfil in sorted(os.listdir(praiz)):
            p = os.path.join(praiz, perfil, "python", "plugins", "qgis_mcp_plugin")
            if os.path.isdir(p):
                hallazgos.append((f"{mayor}/profiles/{perfil}", p, version_de(p)))
    return hallazgos


def version_de(ruta_complemento):
    """Lee `version=` de metadata.txt. None si no se puede."""
    meta = os.path.join(ruta_complemento, "metadata.txt")
    try:
        with open(meta, encoding="utf-8") as fh:
            m = re.search(r"^version=(.+)$", fh.read(), re.MULTILINE)
        return m.group(1).strip() if m else None
    except OSError:
        return None


def socket_vivo():
    """True si el complemento responde `ping` en el socket.

    No basta con que el puerto acepte la conexion: se hace el ping completo
    (cabecera de 4 bytes big-endian + JSON) porque un puerto ocupado por otra
    cosa tambien acepta.
    """
    try:
        cuerpo = json.dumps({"type": "ping", "params": {}}).encode("utf-8")
        with socket.create_connection((HOST, PUERTO), timeout=3.0) as s:
            s.sendall(CABECERA.pack(len(cuerpo)) + cuerpo)
            cab = s.recv(4)
            if len(cab) < 4:
                return False
            n = CABECERA.unpack(cab)[0]
            datos = b""
            while len(datos) < n:
                trozo = s.recv(n - len(datos))
                if not trozo:
                    return False
                datos += trozo
        return json.loads(datos.decode("utf-8")).get("status") == "success"
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def entrada(version):
    """La entrada del servidor, comun a los dos formatos de configuracion."""
    return {
        "command": "uvx",
        "args": ["--from", PLANTILLA_ZIP.format(ver=version), "qgis-mcp-server"],
        "env": {"QGIS_MCP_HOST": HOST, "QGIS_MCP_PORT": str(PUERTO)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", help="version del servidor (por defecto, la "
                                      "del complemento instalado)")
    ap.add_argument("--seco", action="store_true", help="no escribir nada")
    args = ap.parse_args()

    fallos = []

    print("1. Complemento 'QGIS MCP' (dentro de QGIS)")
    comp = buscar_complemento()
    for etiqueta, ruta, ver in comp:
        print(f"   OK  {etiqueta}  v{ver or '?'}")
        print(f"       {ruta}")
    if not comp:
        print("   !!  no encontrado")
        print("       QGIS > Complementos > Administrar e instalar > 'QGIS MCP'")
        fallos.append("complemento")

    print("\n2. uvx (arranca el servidor, fuera de QGIS)")
    if shutil.which("uvx"):
        print(f"   OK  {shutil.which('uvx')}")
    else:
        print("   !!  no esta en el PATH. Instala uv:")
        print("       https://docs.astral.sh/uv/getting-started/installation/")
        fallos.append("uvx")

    print(f"\n3. Socket del complemento ({HOST}:{PUERTO})")
    if socket_vivo():
        print("   OK  responde ping")
    else:
        print("   --  sin respuesta. Abre QGIS y pulsa 'Start Server' en el")
        print("       complemento. No hace falta para escribir la configuracion.")

    version = args.version or next((v for _, _, v in comp if v), None)
    if not version:
        print("\n!! No se puede fijar la version: ni complemento ni --version.")
        return 1

    print(f"\n4. Version fijada: v{version}", end="")
    print(" (del complemento instalado)" if not args.version else " (--version)")

    if len({v for _, _, v in comp if v}) > 1:
        print("   AVISO: hay perfiles con versiones distintas del complemento.")
        print("   El servidor solo puede casar con una; revisa cual usas.")

    aviso = ("GENERADO por scripts/configurar_mcp.py; no lo edites a mano. La "
             f"version v{version} debe coincidir con la del complemento 'QGIS "
             "MCP' instalado en QGIS. Ver docs/MCP_QGIS.md.")

    destinos = {
        os.path.join(RAIZ, ".mcp.json"): {
            "$comment": aviso,
            "mcpServers": {"qgis": entrada(version)},
        },
        os.path.join(RAIZ, ".vscode", "mcp.json"): {
            "$comment": aviso,
            "servers": {"qgis": dict(type="stdio", **entrada(version))},
        },
    }

    print("\n5. Configuracion")
    for destino, cfg in destinos.items():
        rel = os.path.relpath(destino, RAIZ)
        texto = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
        if args.seco:
            print(f"   (seco) {rel}:\n{texto}")
            continue
        os.makedirs(os.path.dirname(destino), exist_ok=True)
        with open(destino, "w", encoding="utf-8") as fh:
            fh.write(texto)
        print(f"   escrito {rel}")

    if args.seco:
        print("   (modo seco: no se ha escrito nada)")
    else:
        print("\nRecarga la ventana de VSCode para que tome el servidor nuevo.")

    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())
