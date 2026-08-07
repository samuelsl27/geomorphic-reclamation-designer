# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cliente de modelos de IA que corren EN LOCAL (Ollama / LM Studio).

Todo va por HTTP con la biblioteca estándar (urllib): el complemento no añade
ninguna dependencia y funciona igual si el usuario no tiene ningún servidor
levantado (en ese caso la pestaña de optimización se queda deshabilitada).

Servidores soportados
---------------------
- **Ollama**   http://127.0.0.1:11434   → /api/tags (modelos), /api/chat
- **LM Studio** http://127.0.0.1:1234   → /v1/models, /v1/chat/completions
  (API compatible con OpenAI; también sirve para llama.cpp server, Jan, etc.)

Ambos aceptan imágenes en base64 si el modelo tiene visión (Qwen3-VL, Llama
3.2-Vision, Gemma 3…), que es lo que aprovecha el optimizador para enseñarle
el mapa de corte/relleno y la planta del diseño.
"""

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request


PUERTOS_OLLAMA = [11434]
PUERTOS_OPENAI = [1234, 1235, 8080, 5000, 8000]   # LM Studio, llama.cpp, Jan…
TIMEOUT_CORTO = 1.2
TIMEOUT_SONDEO = 0.12     # s, sondeo de puerto antes de hablar HTTP


def _puerto_abierto(host, puerto, timeout=TIMEOUT_SONDEO):
    """¿Hay algo escuchando? Un socket se cierra en microsegundos si el
    puerto está libre, mientras que una petición HTTP a un puerto muerto puede
    tardar segundos (resolución de nombre, reintentos IPv6/IPv4). Esto es lo
    que hacía que el panel tardase varios segundos en abrirse."""
    import socket
    try:
        with socket.create_connection((host, puerto), timeout=timeout):
            return True
    except Exception:
        return False


def _get(url, timeout=TIMEOUT_CORTO):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _post(url, payload, timeout=600.0, cabeceras=None):
    datos = json.dumps(payload).encode("utf-8")
    cab = {"Content-Type": "application/json"}
    cab.update(cabeceras or {})
    req = urllib.request.Request(url, data=datos, headers=cab)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def imagen_b64(ruta):
    """PNG/JPG → base64 (sin prefijo data:)."""
    with open(ruta, "rb") as fh:
        return base64.b64encode(fh.read()).decode("ascii")


# ------------------------------------------------------------------ descubrir
def detectar_servidores(hosts=("127.0.0.1",)):
    """Escanea los puertos habituales y devuelve la lista de servidores vivos:
    [{'tipo': 'ollama'|'openai', 'url': ..., 'modelos': [...]}].

    Se sondea solo 127.0.0.1 por defecto: 'localhost' es la misma máquina pero
    resuelve primero a ::1, y cada sondeo a un puerto cerrado por IPv6 se come
    el timeout completo (eran ~4 s de espera para nada). Si un host responde en
    un puerto, los siguientes ya no lo prueban, para no listar el mismo
    servidor dos veces."""
    encontrados = []
    vistos = set()
    puertos_ok = set()
    for host in hosts:
        for puerto in PUERTOS_OLLAMA:
            url = f"http://{host}:{puerto}"
            if url in vistos or puerto in puertos_ok:
                continue
            if not _puerto_abierto(host, puerto):
                continue
            try:
                d = _get(url + "/api/tags")
                modelos = [m.get("name") or m.get("model")
                           for m in d.get("models", [])]
                encontrados.append({"tipo": "ollama", "url": url,
                                    "modelos": [m for m in modelos if m]})
                vistos.add(url); puertos_ok.add(puerto)
            except Exception:
                pass
        for puerto in PUERTOS_OPENAI:
            url = f"http://{host}:{puerto}"
            if url in vistos or puerto in puertos_ok:
                continue
            if not _puerto_abierto(host, puerto):
                continue
            try:
                d = _get(url + "/v1/models")
                modelos = [m.get("id") for m in d.get("data", [])]
                encontrados.append({"tipo": "openai", "url": url,
                                    "modelos": [m for m in modelos if m]})
                vistos.add(url); puertos_ok.add(puerto)
            except Exception:
                pass
    return encontrados


def info_modelo(servidor, modelo):
    """Datos del modelo (parámetros, contexto, capacidades) si el servidor los
    expone. Se usa para avisar de si tiene visión y de la ventana de contexto."""
    try:
        if servidor["tipo"] == "ollama":
            d = _post(servidor["url"] + "/api/show", {"model": modelo},
                      timeout=15.0)
            det = d.get("details", {})
            fam = " ".join(filter(None, [det.get("family", "")] +
                                  (det.get("families") or [])))
            info = d.get("model_info", {}) or {}
            ctx = None
            for k, v in info.items():
                if k.endswith(".context_length"):
                    ctx = v
            cap = [str(c).lower() for c in (d.get("capabilities") or [])]
            vis = ("vision" in cap or "clip" in fam.lower()
                   or "vision" in fam.lower() or "mllama" in fam.lower()
                   or "-vl" in (modelo or "").lower())
            return {"parametros": det.get("parameter_size"),
                    "cuantizacion": det.get("quantization_level"),
                    "contexto": ctx, "vision": vis, "vision_seguro": True}
    except Exception:
        pass
    return {"parametros": None, "cuantizacion": None, "contexto": None,
            "vision_seguro": False,
            "vision": any(t in (modelo or "").lower()
                          for t in ("-vl", "vision", "llava"))}


# ------------------------------------------------------------------ conversar
class ClienteIA:
    """Conversación con un modelo local, con imágenes y respuesta en JSON."""

    def __init__(self, servidor, modelo, temperatura=0.2, contexto=16384,
                 timeout=900.0, pensar=False):
        self.servidor = servidor
        self.modelo = modelo
        self.temperatura = temperatura
        self.contexto = contexto
        self.timeout = timeout
        # 'pensar': activa el razonamiento explícito de los modelos que lo
        # soportan (Qwen3, DeepSeek-R1…). El texto del razonamiento se guarda
        # aparte y se muestra en el registro, sin romper el JSON de salida.
        self.pensar = pensar
        self.ultimo_razonamiento = None
        self.ultimo_error = None

    # ---- construcción de mensajes ----
    def _mensaje_ollama(self, texto, imagenes):
        m = {"role": "user", "content": texto}
        if imagenes:
            m["images"] = [imagen_b64(r) for r in imagenes if os.path.exists(r)]
        return m

    def _mensaje_openai(self, texto, imagenes):
        partes = [{"type": "text", "text": texto}]
        for r in imagenes or []:
            if os.path.exists(r):
                partes.append({"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + imagen_b64(r)}})
        return {"role": "user", "content": partes}

    def preguntar(self, texto, imagenes=None, sistema=None, json_estricto=True):
        """Devuelve el texto de la respuesta (str) o None si falla."""
        self.ultimo_error = None
        try:
            if self.servidor["tipo"] == "ollama":
                msgs = []
                if sistema:
                    msgs.append({"role": "system", "content": sistema})
                msgs.append(self._mensaje_ollama(texto, imagenes))
                payload = {"model": self.modelo, "messages": msgs,
                           "stream": False,
                           "options": {"temperature": self.temperatura,
                                       "num_ctx": int(self.contexto)}}
                if json_estricto:
                    payload["format"] = "json"
                if self.pensar:
                    payload["think"] = True
                try:
                    d = _post(self.servidor["url"] + "/api/chat", payload,
                              timeout=self.timeout)
                except Exception:
                    # algunos modelos no admiten 'think': se reintenta sin él
                    payload.pop("think", None)
                    d = _post(self.servidor["url"] + "/api/chat", payload,
                              timeout=self.timeout)
                msg = d.get("message") or {}
                self.ultimo_razonamiento = msg.get("thinking")
                return msg.get("content")
            msgs = []
            if sistema:
                msgs.append({"role": "system", "content": sistema})
            msgs.append(self._mensaje_openai(texto, imagenes))
            payload = {"model": self.modelo, "messages": msgs,
                       "temperature": self.temperatura, "stream": False}
            if json_estricto:
                payload["response_format"] = {"type": "json_object"}
            d = _post(self.servidor["url"] + "/v1/chat/completions", payload,
                      timeout=self.timeout)
            return d["choices"][0]["message"]["content"]
        except Exception as e:
            self.ultimo_error = str(e)
            return None

    def preguntar_json(self, texto, imagenes=None, sistema=None):
        """Como preguntar() pero devolviendo un dict; tolera que el modelo
        envuelva el JSON en texto o en un bloque ```json."""
        bruto = self.preguntar(texto, imagenes, sistema, json_estricto=True)
        if not bruto:
            return None, None
        d = extraer_json(bruto)
        if d is not None and self.ultimo_razonamiento:
            d["_thinking"] = self.ultimo_razonamiento
        return d, bruto


def extraer_json(txt):
    """Primer objeto JSON válido dentro de un texto (los modelos pequeños
    suelen añadir explicación antes o después, o usar ```json)."""
    if not txt:
        return None
    t = txt.strip()
    if "```" in t:
        trozos = t.split("```")
        for tr in trozos:
            tr = tr.strip()
            if tr.startswith("json"):
                tr = tr[4:].strip()
            if tr.startswith("{"):
                t = tr
                break
    try:
        return json.loads(t)
    except Exception:
        pass
    ini = t.find("{")
    while ini >= 0:
        prof = 0
        for i in range(ini, len(t)):
            if t[i] == "{":
                prof += 1
            elif t[i] == "}":
                prof -= 1
                if prof == 0:
                    try:
                        return json.loads(t[ini:i + 1])
                    except Exception:
                        break
        ini = t.find("{", ini + 1)
    return None


# ------------------------------------------------------------------ web
def buscar_web(consulta, n=5, timeout=15.0):
    """Búsqueda web sencilla (DuckDuckGo HTML) para dar contexto externo al
    modelo. Es OPCIONAL: si no hay salida a internet devuelve lista vacía y el
    optimizador sigue funcionando igual."""
    try:
        url = "https://duckduckgo.com/html/?q=" + urllib.parse.quote(consulta)
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (QGIS Geomorphic Reclamation Designer plugin)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            html = r.read().decode("utf-8", "replace")
    except Exception:
        return []
    import re
    res = []
    for m in re.finditer(
            r'result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
            r'result__snippet"[^>]*>(.*?)</a>', html, re.S):
        enlace, titulo, frag = m.groups()
        limpio = lambda s: re.sub(r"<[^>]+>", "", s).strip()
        res.append({"titulo": limpio(titulo), "url": enlace,
                    "resumen": limpio(frag)[:400]})
        if len(res) >= n:
            break
    return res
