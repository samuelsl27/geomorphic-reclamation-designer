# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 Samuel Saez Lopez y colaboradores
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Todo lo que se le entrega al modelo de IA en cada sesión de optimización.

En la carpeta de trabajo (una por sesión, con fecha y hora) queda:

    prompt_base.md        prompt de sistema + memoria del complemento
    memoria_metodo.md     qué es el método, qué hace el plugin, qué significa
                          cada variable y cada métrica (redactado para que lo
                          consuma un modelo local, no una persona)
    iteracion_XX.md       prompt exacto enviado en esa iteración
    respuesta_XX.txt      respuesta cruda del modelo
    historial.json        variables, métricas y puntuación de cada iteración
    resultado.json        mejor solución
    images/               planta del diseño y mapa de corte/relleno con leyenda
    rasters/              superficie de diseño y ráster corte/relleno
    data/                 tablas de regiones de corte/relleno y de canales

Las imágenes se generan con el propio motor de render de QGIS, con una leyenda
quemada en el pie para que un modelo con visión pueda leer los rangos.
"""

import json
import os
import shutil

from qgis.core import (
    QgsProject, QgsMapSettings, QgsMapRendererParallelJob, QgsRectangle,
)
from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtGui import QColor, QImage, QPainter, QFont, QPen


MEMORIA = """# Memoria del método para el modelo de optimización

## 1. Qué estás optimizando
Geomorphic Reclamation Designer es un complemento de QGIS que implementa el
**método fluvio-geomórfico** de restauración geomorfológica de minas publicado
por N. Bugosh (*Natural Regrade® / GeoFluv™*, marcas de sus titulares, citadas
aquí solo para identificar el método de referencia). En vez de taludes y bermas
rectos, construye la red de drenaje que se formaría de forma natural en ese
sitio y la superficie estable asociada. El diseño se compone de:

- **Canales** (`GRD_Channels`): eje 3D de cada cauce. El principal y sus
  tributarios (`main`, `main R1`, `main L1`…). Perfil longitudinal cóncavo.
  Donde la pendiente supera el 4 % el trazado es en **zigzag** (canal tipo A);
  por debajo del 4 % es **sinusoidal** (meandros).
- **Crestas divisorias** (`GRD_Ridges`): separan las cuencas de dos canales
  contiguos y mueren en la confluencia de ambos cauces.
- **Subcrestas** (`GRD_SubRidges`) y **vaguadas** (`GRD_Swales`): del ápice de
  cada meandro nace una subcresta hacia el interior de la curva y una vaguada
  hacia la margen opuesta; son las que dan el relieve ondulado de ladera.
- **Superficie de diseño** (`GRD_DesignSurface`): TIN sobre todas esas líneas
  de rotura, recortado al límite del proyecto.
- **Corte y relleno**: diferencia entre la superficie de diseño y el terreno
  original, SOLO dentro del límite.

## 2. Reglas físicas que NO puedes romper
- El agua va cuesta abajo: el perfil de cada canal desciende de forma monótona
  de la cabecera a la boca, y es cóncavo (más pendiente arriba).
- Dos cuencas contiguas están separadas por una cresta; una ladera drena a su
  canal.
- Las pendientes recta máximas de crestas y laderas no deben superar el valor
  `pendiente_max_pct` de los ajustes.
- La sinuosidad de un canal tipo A (>4 %) es baja (1.02–1.20); la de un canal
  de fondo de valle puede llegar a ~1.5.
- La longitud de onda del meandro sale de la anchura bankfull:
  Rc = 2.5–3.2·W, λ = 4.53·Rc, cinturón = 0.61·λ (ecuaciones de régimen de
  Williams 1986). La anchura bankfull sale del caudal por el método racional
  Qpk = C·i·A/360.
- Aumentar el coeficiente de escorrentía o la lluvia agranda el canal, alarga
  la longitud de onda del meandro y separa las crestas.

## 3. Qué significa cada métrica que recibes
- `cut_m3` / `fill_m3`: volumen de excavación y de relleno dentro del límite.
- `net_m3` = cut − fill. Positivo = sobra tierra; negativo = falta tierra.
- `ratio_pct` = cut/fill en %.
- `dozer_idx`: índice de reparto en altura. **+1 = todo el corte en la parte
  alta y todo el relleno en la baja** (remodelado ejecutable empujando material
  cuesta abajo con bulldozer). Valores negativos significan que estás
  excavando abajo y rellenando arriba, que es lo que hay que evitar.
- `cut_en_alto_pct`: % del volumen de corte situado por encima de la cota
  mediana del recinto.
- `lineas_fuera_pendiente`: nº de crestas/vaguadas que superan la pendiente
  máxima admisible.
- `dd_media` frente a `dd_objetivo`: densidad de drenaje (m de canal por ha).
- `secciones_tau_alto`: nº de secciones donde la tensión tractiva supera la
  crítica de Shields (riesgo de erosión del lecho).

## 3bis. LÍMITE que te va a frenar con las pendientes del canal
El perfil debe ser monótono y cóncavo, así que la **pendiente de boca tiene que
ser MENOS empinada que la pendiente media del valle** (que es
(z_boca − z_cabecera)/longitud y te la doy en `perfiles_efectivos`), y la de
cabecera MÁS empinada que esa media. Si pides una pendiente de boca más
empinada que la media, el motor la recorta y el perfil colapsa a una RECTA: el
resultado sale idéntico y habrás perdido la iteración. En ese caso
`concavidad_perfil` tampoco hace nada, porque la curva ya es la recta.
Comprueba siempre `perfiles_efectivos` para ver qué se ha aplicado de verdad.

## 4. Cómo influye cada variable (efecto dominante)
- `pendiente_cabecera_pct` (más negativa) → el canal baja antes → más corte
  arriba y menos relleno abajo.
- `pendiente_boca_pct` (más negativa) → baja la cota de todo el tramo final →
  MÁS corte / MENOS relleno en toda la cuenca. Es la palanca más potente sobre
  el volumen.
- `pendiente_max_pct` (mayor) → laderas más altas respecto al canal → crestas
  más altas → más relleno.
- `max_dist_cresta_cabecera` (mayor) → laderas más largas y crestas más altas.
- `vel_max_agua` (mayor) → sección más pequeña → canal más estrecho.
- `wd_pend_menor_004` (mayor) → canal más ancho y menos profundo.
- `sinuosidad_menor_004` (mayor) → canal más largo y sinuoso, más longitud de
  excavación de cauce.
- `espaciado_subcrestas` (menor) → más crestas y vaguadas → relieve más
  troceado, más movimiento de tierras.
- `naturalidad` (mayor) → superficie más redondeada; suaviza picos y hoyos,
  reduce ligeramente los volúmenes extremos.
- `geometry.xy` → desplazamiento lateral del fondo de valle en metros, en
  puntos de control equiespaciados de cabecera a boca. Sirve para llevar el
  cauce hacia zonas donde interesa cortar o rellenar.
- `geometry.boundary_m` → cuántos metros te extralimitas del límite de diseño
  (solo por la zona permitida).
- `concavidad_perfil` (por canal) → forma de la curva vertical del canal SIN
  tocar las cotas de cabecera ni de boca: 0 = perfil recto, 1 = curva cóncava
  estándar, 2 = muy cóncavo. Más cóncavo hunde el tramo medio → más corte en el
  centro de la cuenca.
- `geometry.profiles` → es el equivalente a 'Edit Longitudinal Profile' sobre
  las crestas y las vaguadas: `ridges_pct` y `swales_pct` suben (+) o bajan (−)
  ese porcentaje el extremo alto de TODAS las subcrestas o de todas las
  vaguadas, y `per_line` permite hacerlo línea a línea con la clave
  `"canal|indice"` (el índice es el campo `index` de las capas GRD_SubRidges y
  GRD_Swales). Subir las crestas añade relleno; bajar las vaguadas añade corte,
  y ambas cosas cambian el reparto por regiones sin tocar los canales.

## 4bis. Recetario del libro (Bugosh & Martín Duque, 2024)

Esto no son reglas mías: son las ediciones que el libro y el manual de Natural
Regrade recomiendan para cada problema, con las cifras de sus propios ejemplos.
Úsalas como primera opción antes de inventar combinaciones.

### Balance corte/relleno [6.9.1, 9.10.1]
Falta corte (relleno > corte, % por debajo del mínimo):
1. **Empinar la pendiente de cabecera** del canal principal. El perfil cóncavo
   se hunde más y hay que excavar más. En el tutorial, pasar de −12 % a −16 %
   llevó el balance de **70.2 % a 94.3 %**. Efecto secundario: el punto de
   transición del tramo A se acerca a la cabecera.
2. **Bajar la cota de cabecera**. Baja todo el perfil, y de forma NO uniforme
   porque la curva es cóncava. Bajar ~1 m en el tutorial dejó el balance dentro
   de tolerancia.
3. **Bajar la cota de boca** (nivel de base local). Es la palanca más potente:
   afecta a toda la cuenca y a todos los tributarios. En el ejemplo del cap. 9,
   1.5 m menos llevaron el balance de **65.6 % a 110.9 %**.
4. Ajuste fino con los **tributarios**: en el tutorial, bajar 0.2 ft la cota de
   cabecera y subir 0.2 % la pendiente de un tributario dejó el déficit en 1 %.

Sobra corte (% por encima del máximo): las mismas palancas al revés. Subir la
cota de cabecera del principal 0.6 m llevó el balance de **110.9 % a 104.4 %**.

Otra vía, con efecto sobre la forma: **bajar las crestas** genera corte
(en el cap. 9 bajar una cresta local generó ~2.051 m3) y **subirlas** genera
relleno.

### El agua no entra en el cauce, corre paralela a él [8.1.3]
Síntoma: las líneas de escorrentía bajan por la vaguada pero, antes de entrar,
las arrastra ladera abajo pasando la nariz de la subcresta.
1. **Bajar la cota del canal** (empinar la cabecera o bajar la cota de
   cabecera) → laderas de valle más empinadas → el agua entra.
2. **Alargar la porción convexa de la subcresta** (xc). En el ejemplo del libro
   la llevaron al **90 % de la longitud total de la subcresta**: la subcresta
   queda más alta junto al canal y hace de tope.

### Laderas sobreempinadas [9.4]
NO se recorta la pendiente: se **baja la línea de cresta**. En el ejemplo, un
tramo pasó de **46 % a 33 %**. Al bajarla hay que vigilar el propio perfil
longitudinal de la cresta, que se puede sobreempinar: se corrige subiendo el
**blend percent** de la edición. Genera corte, que hay que colocar en otro
sitio.

### Tensión tractiva por encima del umbral [8.3.5]
Editar el perfil del canal en el tramo afectado y su cota en la confluencia.
Es iterativo: corregir un tramo suele mover el problema aguas abajo. El libro
llegó a 1.90 lb/ft2 frente a un umbral de 2 tras varias iteraciones.

### Sillas en la línea de cresta [9.11.2, p. 259]
La cabecera de una vaguada forma una **silla** en la divisoria. Sin ella el
agua corre por el filo de la cresta, hace roderas y acaba en cárcava. Aquí lo
controla `prof_silla_pct`.

### Aviso del propio libro [8.4, 9.6]
> «editing one element of an integrated landform to address a problem can
> affect other design elements»

Bajar un canal para mejorar la conducción sobreempina las laderas; cualquier
cambio mueve el balance de tierras y el coste. Cambia POCAS cosas por
iteración y comprueba el efecto cruzado antes de seguir.

## 5. Qué tienes que devolver
SIEMPRE un único objeto JSON, sin texto alrededor, con esta forma:

```json
{
  "reasoning": "en 2-4 frases: qué has leído en los datos y en las imágenes, y por qué mueves esas variables",
  "global": {"pendiente_max_pct": 30.0},
  "channels": {"main": {"pendiente_boca_pct": -2.4}},
  "geometry": {
    "xy": {"main": [0, 4.0, 6.0, 2.0, 0]},
    "profiles": {"ridges_pct": 5.0, "swales_pct": -3.0, "per_line": {"main|7": -12.0}},
    "boundary_m": 0.0
  },
  "expected_effect": "qué esperas que pase con cut, fill y dozer_idx",
  "web_search": "(opcional) consulta si necesitas un dato externo",
  "warnings": ["(opcional) incoherencias o errores del diseño que detectes y que el usuario deba revisar"]
}
```

Reglas de la respuesta:
- Solo puedes usar las variables que aparecen en la lista de VARIABLES
  PERMITIDAS de este turno, y siempre dentro de su rango `[min, max]`.
  Cualquier otra se ignora.
- Mueve pocas variables a la vez (1–3) y con cambios apreciables pero no
  extremos: así se puede atribuir el efecto y la búsqueda converge.
- Mira el historial: si un movimiento empeoró la puntuación, prueba el sentido
  contrario o cambia de variable.
- Si crees que los objetivos son incompatibles entre sí, dilo en `reasoning`.
- Usa la tabla de REGIONES y la imagen `regions_*` para decidir DÓNDE actuar:
  si una región de relleno enorme está en la parte baja y el `dozer_idx` es
  negativo, mueve el canal en planta hacia ella o baja la pendiente de boca.
- Si en las MÉTRICAS aparecen hoyos cerrados o picos aislados, o si al mirar
  las imágenes ves un cono, una depresión cerrada o curvas de nivel que se
  cierran donde no debería (típicamente junto a la confluencia de dos cauces),
  DILO en `warnings`: eso se muestra al usuario. Suele significar que falta una
  cresta divisoria o que dos líneas de rotura no encajan en cota.
- `expected_effect` sirve para comprobarte a ti mismo: en la siguiente
  iteración verás si acertaste, y eso te dice si el sentido del movimiento era
  el correcto.
"""


class ContextoIA:
    """Genera prompts, exporta imágenes/datos y guarda todo en la carpeta."""

    def __init__(self, carpeta, proyecto, iface, permitir_web=False,
                 max_imagenes=3, log=None, dem=None):
        self.sin_efecto = []
        self.dem = dem
        self.carpeta = carpeta
        self.p = proyecto
        self.iface = iface
        self.permitir_web = permitir_web
        self.max_imagenes = max_imagenes
        self.log = log or (lambda *_a, **_k: None)
        self.notas_web = []
        self._escribir_memoria()

    # ---------------------------------------------------------- memoria
    def _escribir_memoria(self):
        try:
            with open(os.path.join(self.carpeta, "memoria_metodo.md"), "w",
                      encoding="utf-8") as fh:
                fh.write(MEMORIA)
        except Exception:
            pass

    def sistema(self):
        return ("Eres un ingeniero de restauración geomorfológica que optimiza "
                "un diseño fluvio-geomórfico dentro de QGIS. Piensa paso a paso "
                "antes de "
                "responder, pero responde ÚNICAMENTE con un objeto JSON válido "
                "con las claves reasoning, global, channels, geometry y "
                "expected_effect.\n\n" + MEMORIA)

    # ---------------------------------------------------------- prompts
    def _bloque_variables(self, espacio):
        ln = ["## VARIABLES PERMITIDAS EN ESTE TURNO"]
        from .ai_optimizer import VARIABLES_GLOBALES, VARIABLES_CANAL
        g = espacio.get("globales") or {}
        if g:
            ln.append("### global")
            for k, (lo, hi) in g.items():
                et = VARIABLES_GLOBALES.get(k, (k,))[0]
                ln.append(f"- `{k}` — {et} — rango [{lo:.4g}, {hi:.4g}]")
        for canal, vs in (espacio.get("canales") or {}).items():
            if not vs:
                continue
            ln.append(f"### channels.{canal}")
            for k, (lo, hi) in vs.items():
                et = VARIABLES_CANAL.get(k, (k,))[0]
                ln.append(f"- `{k}` — {et} — rango [{lo:.4g}, {hi:.4g}]")
        geo = espacio.get("geom") or {}
        if geo.get("xy"):
            ln.append(f"### geometry.xy — desplazamiento lateral máximo "
                      f"±{geo['xy']:.4g} m, lista de 5 valores por canal "
                      "(cabecera → boca; el primero y el último deben ser 0)")
            ln.append("  **CONVENIO DE SIGNO**: el desplazamiento se aplica "
                      "sobre la NORMAL IZQUIERDA del sentido de avance del "
                      "cauce (de cabecera a boca). Un valor POSITIVO mueve el "
                      "cauce hacia su margen izquierda mirando aguas abajo; uno "
                      "NEGATIVO hacia la derecha. Si no estás seguro del "
                      "sentido, mira las coordenadas del eje que te doy más "
                      "abajo: van de cabecera a boca.")
            ln.append("  **QUÉ CONSIGUE**: llevar el cauce hacia una zona de "
                      "RELLENO la convierte en corte (el fondo del canal baja "
                      "hasta la cota de diseño), y alejarlo de ella deja más "
                      "relleno. Es la palanca MÁS DIRECTA sobre el reparto de "
                      "volúmenes, mucho más que cualquier parámetro, porque "
                      "cambia DÓNDE está el diseño y no solo su forma.")
            if not (espacio.get("globales") or
                    any(espacio.get("canales", {}).values())):
                ln.append("  **ESTE TURNO NO PUEDES TOCAR NINGÚN PARÁMETRO**: "
                          "la ÚNICA variable habilitada es geometry.xy. "
                          "Cualquier clave dentro de `global` o `channels` se "
                          "descarta. Responde con `geometry.xy` y nada más; si "
                          "devuelves solo parámetros, la iteración se pierde.")
            ln.append(self._pista_direccion())
        if geo.get("limite"):
            ln.append(f"### geometry.boundary_m — extralimitación máxima "
                      f"{geo['limite']:.4g} m por la zona "
                      f"'{geo.get('limite_zona', 'low')}'")
        if not g and not (espacio.get("canales") or {}) and not geo:
            ln.append("(ninguna: el usuario no ha habilitado variables)")
        return "\n".join(ln)

    def _pista_direccion(self):
        """Dónde está el grueso del relleno respecto al cauce.

        Sin esto el modelo sabe que puede mover el canal pero no hacia dónde:
        se le da el centroide de la mayor región de relleno y el punto del eje
        más próximo, para que deduzca el sentido del desplazamiento."""
        m = getattr(self, "_ultimas_metricas", None) or {}
        regs = [r for r in (m.get("regiones") or []) if r["tipo"] == "fill"]
        if not regs:
            return ""
        r = max(regs, key=lambda x: x["volumen_m3"])
        from qgis.core import QgsProject as _P
        capa = None
        for l in _P.instance().mapLayers().values():
            if l.name() == "GRD_Channels":
                capa = l
        if capa is None:
            return ""
        mejor = None
        for f in capa.getFeatures():
            for v in f.geometry().vertices():
                d2 = (v.x() - r["x"]) ** 2 + (v.y() - r["y"]) ** 2
                if mejor is None or d2 < mejor[0]:
                    mejor = (d2, f["name"], v.x(), v.y())
        if mejor is None:
            return ""
        _, nombre, cx, cy = mejor
        dx, dy = r["x"] - cx, r["y"] - cy
        import math as _m
        dist = _m.hypot(dx, dy)
        rumbo = ("este" if dx > abs(dy) else "oeste" if -dx > abs(dy)
                 else "norte" if dy > 0 else "sur")
        return ("  **PISTA**: el grueso del relleno "
                f"({r['volumen_m3']:,.0f} m3, espesor medio "
                f"{r['prof_media_m']:.1f} m) tiene su centro en "
                f"({r['x']:,.0f}, {r['y']:,.0f}), a {dist:,.0f} m al {rumbo} del "
                f"punto más próximo del canal '{nombre}' "
                f"({cx:,.0f}, {cy:,.0f}). Acercar el cauce a esa zona reduce el "
                "relleno; alejarlo lo aumenta.")

    def _bloque_objetivos(self, objetivos):
        from .ai_optimizer import OBJETIVOS
        ln = ["## OBJETIVOS"]
        for k, v in objetivos.items():
            if k.startswith("_") or v in (None, False):
                continue
            et = OBJETIVOS.get(k, k)
            if isinstance(v, bool):
                ln.append(f"- {et}")
            else:
                ln.append(f"- {et}: objetivo = {v:,.0f}")
        return "\n".join(ln)

    @staticmethod
    def _bloque_metricas(m, titulo="MÉTRICAS"):
        if not m:
            return ""
        ln = [f"## {titulo}"]
        for k in ("cut_m3", "fill_m3", "net_m3", "ratio_pct", "dozer_idx",
                  "cut_en_alto_pct", "z_cut_med", "z_fill_med", "dd_media",
                  "dd_objetivo", "lineas_fuera_pendiente", "lineas_total",
                  "secciones_tau_alto", "secciones", "area_ha"):
            if k in m and m[k] is not None:
                v = m[k]
                ln.append(f"- {k} = {v:,.2f}" if isinstance(v, float)
                          else f"- {k} = {v}")
        if m.get("acarreo_m3m") is not None:
            ln.append(f"- acarreo_m3m (volumen x distancia) = {m['acarreo_m3m']:,.0f}")
        if m.get("hoyos") or m.get("picos"):
            ln.append(f"- INCOHERENCIAS DE LA SUPERFICIE: {m.get('hoyos', 0)} "
                      f"celda(s) en hoyo cerrado y {m.get('picos', 0)} pico(s) "
                      "aislado(s); el agua no drena ahí. Localizaciones:")
            for an in (m.get("anomalias") or [])[:6]:
                ln.append(f"  · {an['tipo']} de {an['prof_m']:.2f} m en "
                          f"({an['x']:,.0f}, {an['y']:,.0f})")
        pe = m.get("perfiles_efectivos") or {}
        if pe:
            ln.append("- perfiles EFECTIVOS (lo que el motor ha podido aplicar):")
            for n, v in pe.items():
                ln.append(
                    f"  · {n}: cabecera {v['pendiente_cabecera_efectiva_pct']:g} % → "
                    f"boca {v['pendiente_boca_efectiva_pct']:g} % "
                    f"(pendiente media del valle {v['pendiente_media_pct']:g} %)"
                    + ("  ← RECORTADO: lo pedido no era realizable"
                       if v.get("recortado") else ""))
        can = m.get("canales") or {}
        if can:
            ln.append("- canales: " + json.dumps(can, ensure_ascii=False))
        regs = m.get("regiones") or []
        if regs:
            ln.append("")
            ln.append("### DISTRIBUCIÓN DEL MOVIMIENTO DE TIERRAS POR REGIONES")
            ln.append("(las mismas que ves en la imagen `regions_*`: ROJO = corte, "
                      "AZUL = relleno; 'prof_media_m' es el espesor medio)")
            ln.append("| id | tipo | volumen (m3) | area (m2) | prof. media (m) | X | Y |")
            ln.append("|---:|:-----|-------------:|----------:|----------------:|---:|---:|")
            for R in regs:
                ln.append("| %d | %s | %s | %s | %s | %s | %s |" % (
                    R["id"], R["tipo"], f"{R['volumen_m3']:,.0f}",
                    f"{R['area_m2']:,.0f}", f"{R['prof_media_m']:.2f}",
                    f"{R['x']:,.0f}", f"{R['y']:,.0f}"))
            if m.get("n_regiones", 0) > len(regs):
                ln.append(f"(se listan las {len(regs)} mayores de "
                          f"{m['n_regiones']} regiones)")
        rutas = m.get("rutas") or []
        if rutas:
            ln.append("")
            ln.append("### ACARREOS PREVISTOS (de la region de corte a la de relleno)")
            for r in rutas:
                ln.append(f"- {r['de']} -> {r['a']}: {r['volumen_m3']:,.0f} m3 "
                          f"a {r['distancia_m']:,.0f} m")
        return "\n".join(ln)

    def _bloque_historial(self, historial, n=6):
        if not historial:
            return ""
        ln = ["## HISTORIAL DE ITERACIONES (lo que ya se ha probado)"]
        for reg in historial[-n:]:
            m = reg["metricas"]
            ln.append(
                f"- it {reg['iteracion']} ({reg['origen']}): puntuación "
                f"{reg['puntuacion']:.3f} · cut {m.get('cut_m3', 0):,.0f} · "
                f"fill {m.get('fill_m3', 0):,.0f} · neto {m.get('net_m3', 0):,.0f} · "
                f"dozer {m.get('dozer_idx')} · variables "
                + json.dumps(reg["variables"], ensure_ascii=False)[:500])
        return "\n".join(ln)

    def _bloque_ajustes(self):
        """Los ajustes que están en vigor en este momento, para que el modelo
        sepa de qué valores parte y no proponga los que ya están puestos."""
        s = getattr(self.p, "settings", None)
        if s is None:
            return ""
        ln = ["## AJUSTES EN VIGOR AHORA MISMO",
              "### global"]
        for k in ("max_dist_cresta_cabecera", "pendiente_desembocadura",
                  "sinuosidad_canal_A", "reach_canal_A", "p_2a_1h_mm",
                  "p_50a_6h_mm", "dd_objetivo", "angulo_subcresta_deg",
                  "pendiente_NE_pct", "pendiente_max_pct", "d50_mm",
                  "convexo_pct", "convexo_swale_m", "naturalidad",
                  "resolucion_dem", "factor_esponjamiento",
                  "factor_compactacion"):
            v = getattr(s, k, None)
            if v is not None:
                ln.append(f"- `{k}` = {v}")
        for c in getattr(self.p, "canales", []) or []:
            ln.append(f"### channels.{c.nombre}")
            for k in ("vel_max_agua", "pendiente_cabecera_pct",
                      "pendiente_boca_pct", "wd_pend_mayor_004",
                      "wd_pend_menor_004", "sinuosidad_mayor_004",
                      "sinuosidad_menor_004", "espaciado_subcrestas",
                      "dist_cresta_swale_m", "coef_escorrentia",
                      "concavidad_perfil"):
                v = getattr(c, k, None)
                if v is not None:
                    ln.append(f"- `{k}` = {v}")
        return "\n".join(ln)

    def _bloque_canales(self):
        """Trazado de los canales en coordenadas, para que el modelo sepa por
        dónde discurren y pueda relacionarlo con las imágenes."""
        from qgis.core import QgsProject as _P
        capa = None
        for l in _P.instance().mapLayers().values():
            if l.name() == "GRD_Channels":
                capa = l
        if capa is None:
            return ""
        ln = ["## TRAZADO DE LOS CANALES (coordenadas del eje, cabecera → boca)"]
        for f in capa.getFeatures():
            vs = list(f.geometry().vertices())
            if len(vs) < 2:
                continue
            paso = max(1, len(vs) // 8)
            pts = [f"({v.x():,.0f}, {v.y():,.0f}, {v.z():.1f})"
                   for v in vs[::paso]]
            if pts and vs[-1] is not None:
                pts.append(f"({vs[-1].x():,.0f}, {vs[-1].y():,.0f}, "
                           f"{vs[-1].z():.1f})")
            ln.append(f"- **{f['name']}** (recibe: {f['receiving'] or '—'}, "
                      f"margen {f['side'] or '—'}): longitud "
                      f"{f['channel_length']:,.0f} m, sinuosidad "
                      f"{f['sinuosity']}, cabecera {f['head_elev']:.1f} m → "
                      f"boca {f['base_elev']:.1f} m")
            ln.append("  eje: " + " → ".join(pts))
        ln.append("El fichero data/canales_NN.csv tiene el eje completo cada "
                  "25 m (canal, estación, X, Y, Z).")
        return "\n".join(ln)

    def _bloque_lineas(self):
        """Tabla de crestas y vaguadas: cada una con su clave, su posición y su
        geometría, para poder modificar UNA sola con
        geometry.profiles.per_line."""
        filas = getattr(self, "tabla_lineas", None)
        if not filas:
            return ""
        ln = ["## CRESTAS Y VAGUADAS, UNA A UNA",
              "(`key` es lo que se usa en `geometry.profiles.per_line`; "
              "x/y_channel es el arranque en el cauce y x/y_top el extremo "
              "alto; dz_m es el desnivel que se gana)",
              "| capa | key | arranque (X,Y,Z) | extremo alto (X,Y,Z) | L (m) | dz (m) | pend (%) |",
              "|:-----|:----|:-----------------|:---------------------|------:|-------:|---------:|"]
        for r in filas[:70]:
            ln.append("| %s | %s | (%s, %s, %s) | (%s, %s, %s) | %s | %s | %s |"
                      % (r[0].replace("GRD_", ""), r[1],
                         f"{r[4]:,.0f}", f"{r[5]:,.0f}", f"{r[6]:.1f}",
                         f"{r[7]:,.0f}", f"{r[8]:,.0f}", f"{r[9]:.1f}",
                         f"{r[10]:.0f}", f"{r[11]:+.1f}", f"{r[12]:.0f}"))
        if len(filas) > 70:
            ln.append(f"(se listan 70 de {len(filas)}; la tabla completa está "
                      "en data/lineas_NN.csv)")
        return "\n".join(ln)

    def prompt_iteracion(self, it, historial, mejor, espacio, objetivos):
        self._ultimas_metricas = (mejor.metricas if mejor else None)
        partes = [
            f"# ITERACIÓN {it}",
            "Tienes el estado actual de un diseño fluvio-geomórfico y debes "
            "proponer el "
            "siguiente movimiento de variables para acercarte a los objetivos.",
            self._bloque_objetivos(objetivos),
            self._bloque_metricas(mejor.metricas if mejor else None,
                                  "MÉTRICAS DEL MEJOR DISEÑO ACTUAL"),
            self._bloque_variables(espacio),
            self._bloque_historial(historial),
        ]
        imgs = (mejor.metricas or {}).get("_imagenes") if mejor else None
        if imgs:
            partes.append(
                "## IMÁGENES ADJUNTAS\n"
                + "\n".join(f"{i+1}. {os.path.basename(r)}"
                            for i, r in enumerate(imgs))
                + "\n\nLa imagen `plan_*` es la planta del diseño: azul = "
                  "canales, rojo = crestas divisorias, amarillo = subcrestas, "
                  "punteado azul = vaguadas, línea gruesa azul = límite.\n"
                  "La imagen `cutfill_*` es el mapa de corte y relleno: ROJO = "
                  "corte (hay que excavar), AZUL = relleno (hay que aportar "
                  "tierra), blanco = equilibrio. La intensidad crece con el "
                  "espesor; la leyenda del pie indica el rango en metros.\n"
                  "La imagen `regions_*` muestra las regiones de movimiento de "
                  "tierras con su número y volumen.")
        if self.permitir_web:
            partes.append(
                "## BÚSQUEDA WEB\nPuedes pedir una búsqueda añadiendo al JSON "
                '`"web_search": "tu consulta"`. Los resultados te llegarán en '
                "la siguiente iteración. Úsala solo si necesitas un dato externo "
                "(p. ej. valores típicos de coeficiente de escorrentía o de D50 "
                "para un material concreto).")
        if self.permitir_web and self.notas_web:
            partes.append("## NOTAS DE BÚSQUEDA WEB\n"
                          + "\n".join(f"- {n}" for n in self.notas_web[-5:]))
        if getattr(self, "sin_efecto", None):
            partes.append(
                "## AVISO IMPORTANTE\nLas iteraciones "
                + ", ".join(str(i) for i in self.sin_efecto)
                + " NO cambiaron nada: los valores que pediste fueron recortados "
                  "por el motor y el diseño resultante fue idéntico. NO repitas "
                  "ese tipo de movimiento; usa OTRAS variables (por ejemplo los "
                  "perfiles de crestas y vaguadas, la geometría en planta, la "
                  "pendiente máxima de ladera o la distancia cresta-cabecera).")
        partes.append(self._bloque_ajustes())
        partes.append(self._bloque_canales())
        partes.append(self._bloque_lineas())
        partes.append(
            "Responde SOLO con el JSON descrito en la memoria "
            "(reasoning, global, channels, geometry, expected_effect).")
        texto = "\n\n".join(p for p in partes if p)
        try:
            with open(os.path.join(self.carpeta, f"iteracion_{it:02d}.md"),
                      "w", encoding="utf-8") as fh:
                fh.write(texto)
        except Exception:
            pass
        return texto

    # ---------------------------------------------------------- exportación
    def exportar_iteracion(self, cand, it):
        """Renderiza las imágenes y copia los rásteres y tablas."""
        m = cand.metricas or {}
        g_lim = m.get("_g_lim")
        salidas = []
        if g_lim is None:
            return salidas
        ext = g_lim.boundingBox()
        ext.grow(max(ext.width(), ext.height()) * 0.05)
        salidas.append(self._render(
            ext, ["GRD_Boundary", "GRD_Swales", "GRD_SubRidges", "GRD_Ridges",
                  "GRD_Channels"],
            os.path.join(self.carpeta, "images", f"plan_{it:02d}.png"),
            "Design — blue: channels · red: divide ridges · "
            "yellow: sub-ridges · dotted: swales"))
        # MAPA DE CALOR del corte/relleno: se re-simboliza el ráster con una
        # rampa divergente y sus rangos numéricos ANTES de renderizar, para que
        # la imagen sea de verdad un mapa de calor legible y no la simbología
        # que tuviera la capa en ese momento.
        rango = self._simbolizar_cutfill()
        salidas.append(self._render(
            ext, ["GRD_CutFill (m)", "GRD_Boundary", "GRD_Channels"],
            os.path.join(self.carpeta, "images", f"cutfill_{it:02d}.png"),
            self._leyenda_cutfill(m, rango)))
        # TERRENO ORIGINAL: contexto de lo que hay dentro y fuera del área
        salidas.append(self._render(
            self._ext_ampliada(ext, 0.6),
            ["_DEM_", "GRD_Boundary", "GRD_Channels"],
            os.path.join(self.carpeta, "images", f"terrain_{it:02d}.png"),
            "ORIGINAL GROUND (hillshade + elevation) before any reclamation, "
            "with the design boundary in blue. The view is deliberately wider "
            "than the project area so you can see what the design has to tie "
            "into: where the ground falls away, where it rises, and where the "
            "outlet has to discharge."))
        # CURVAS DE NIVEL del diseño
        salidas.append(self._render(
            ext, ["GRD_Contours", "GRD_Channels", "GRD_Boundary"],
            os.path.join(self.carpeta, "images", f"contours_{it:02d}.png"),
            "DESIGN CONTOURS. Contours that close in small rings mark a peak or "
            "a hollow: a closed hollow is a defect (water cannot get out). "
            "Contours bending upstream mark a valley, bending downstream a "
            "ridge; their spacing is the slope (closer = steeper)."))
        salidas.append(self._render(
            ext, ["GRD_HaulRegions", "GRD_HaulRoutes", "GRD_Boundary",
                  "GRD_Channels"],
            os.path.join(self.carpeta, "images", f"regions_{it:02d}.png"),
            self._leyenda_regiones(m)))
        # planta de crestas y vaguadas con sus etiquetas, para poder actuar
        # sobre una línea concreta
        salidas.append(self._render(
            ext, ["GRD_Swales", "GRD_SubRidges", "GRD_Ridges", "GRD_Channels",
                  "GRD_Boundary"],
            os.path.join(self.carpeta, "images", f"lines_{it:02d}.png"),
            "Ridge and swale layout — yellow: sub-ridges · dotted blue: swales "
            "· thick red: divide ridges. Their numeric table (per line: index, "
            "start/end coordinates, elevations, length and slope) is in the "
            "prompt and in data/lineas_NN.csv"))
        # orden por importancia: si el tope de imágenes recorta, que se
        # queden las que más deciden
        orden = ("cutfill_", "terrain_", "plan_", "regions_", "contours_",
                 "lines_")
        salidas = [s for s in salidas if s]
        salidas.sort(key=lambda r: next(
            (i for i, p_ in enumerate(orden) if os.path.basename(r).startswith(p_)),
            99))
        self._tablas_geometria(m, it)
        # rásteres y tablas
        try:
            if m.get("_ruta") and os.path.exists(m["_ruta"]):
                shutil.copyfile(m["_ruta"], os.path.join(
                    self.carpeta, "rasters", f"design_surface_{it:02d}.tif"))
        except Exception:
            pass
        try:
            datos = {k: v for k, v in m.items() if not k.startswith("_")}
            with open(os.path.join(self.carpeta, "data",
                                   f"metricas_{it:02d}.json"),
                      "w", encoding="utf-8") as fh:
                json.dump(datos, fh, indent=1, ensure_ascii=False)
        except Exception:
            pass
        return salidas[:self.max_imagenes]

    def _ext_ampliada(self, ext, factor):
        from qgis.core import QgsRectangle
        e = QgsRectangle(ext)
        e.grow(max(e.width(), e.height()) * factor)
        return e

    def _simbolizar_cutfill(self):
        """Rampa divergente con rangos numéricos sobre GRD_CutFill.

        Devuelve (min, max) en metros para poder escribirlos en la leyenda."""
        try:
            from qgis.core import (QgsProject as _P, QgsColorRampShader,
                                   QgsRasterShader,
                                   QgsSingleBandPseudoColorRenderer)
            capa = None
            for l in _P.instance().mapLayers().values():
                if l.name() == "GRD_CutFill (m)":
                    capa = l
            if capa is None:
                return None
            est = capa.dataProvider().bandStatistics(1)
            m = max(abs(est.minimumValue), abs(est.maximumValue), 0.5)
            pasos = [(-m, (103, 0, 31)), (-0.6 * m, (178, 24, 43)),
                     (-0.25 * m, (214, 96, 77)), (-0.05 * m, (244, 165, 130)),
                     (0.0, (247, 247, 247)), (0.05 * m, (146, 197, 222)),
                     (0.25 * m, (67, 147, 195)), (0.6 * m, (33, 102, 172)),
                     (m, (5, 48, 97))]
            items = []
            for v, (r, g, b) in pasos:
                etiqueta = (f"cut {abs(v):.1f} m" if v < 0
                            else ("balance" if v == 0 else f"fill {v:.1f} m"))
                # QColor viene del import de cabecera del modulo. Aqui habia un
                # `_c(r, g, b)` que no existia en ninguna parte: como todo el
                # bloque va dentro de un try/except que devuelve None, el
                # NameError se tragaba en silencio y GRD_CutFill se quedaba SIN
                # simbolizar, con lo que la imagen que recibe el modelo de IA no
                # llevaba la rampa de corte/relleno. Detectado por ruff (F821).
                items.append(QgsColorRampShader.ColorRampItem(
                    v, QColor(r, g, b), etiqueta))
            ramp = QgsColorRampShader()
            try:
                ramp.setColorRampType(QgsColorRampShader.Type.Interpolated)
            except Exception:
                ramp.setColorRampType(QgsColorRampShader.Interpolated)
            ramp.setColorRampItemList(items)
            sh = QgsRasterShader(); sh.setRasterShaderFunction(ramp)
            capa.setRenderer(QgsSingleBandPseudoColorRenderer(
                capa.dataProvider(), 1, sh))
            capa.triggerRepaint()
            return (est.minimumValue, est.maximumValue)
        except Exception:
            return None

    def _leyenda_regiones(self, m):
        n = m.get("n_regiones", 0)
        ac = m.get("acarreo_m3m")
        return ("Earthwork regions — RED = cut area, BLUE = fill area, black "
                "lines = haul routes from a cut region to a fill region. "
                f"{n} region(s)"
                + (f" · total haul {ac:,.0f} m3*m." if ac else "."))

    def _tablas_geometria(self, m, it):
        """CSV con los ejes de los canales y con cada cresta/vaguada.

        Es lo que permite al modelo SITUAR el diseño y actuar sobre una línea
        concreta: cada fila lleva la clave `canal|indice` que se usa en
        `geometry.profiles.per_line`."""
        import csv
        from qgis.core import QgsProject as _P
        def capa(nombre):
            for l in _P.instance().mapLayers().values():
                if l.name() == nombre:
                    return l
            return None
        # ejes de los canales, cada 25 m
        try:
            ruta = os.path.join(self.carpeta, "data", f"canales_{it:02d}.csv")
            with open(ruta, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["channel", "station_m", "x", "y", "z"])
                c = capa("GRD_Channels")
                if c is not None:
                    for f in c.getFeatures():
                        vs = list(f.geometry().vertices())
                        s = 0.0
                        ant = None
                        prox = 0.0
                        for v in vs:
                            if ant is not None:
                                s += ((v.x() - ant[0]) ** 2
                                      + (v.y() - ant[1]) ** 2) ** 0.5
                            ant = (v.x(), v.y())
                            if s >= prox or v is vs[-1]:
                                w.writerow([f["name"], round(s, 1),
                                            round(v.x(), 2), round(v.y(), 2),
                                            round(v.z(), 2)])
                                prox = s + 25.0
        except Exception:
            pass
        # crestas, subcrestas y vaguadas
        self.tabla_lineas = []
        try:
            ruta = os.path.join(self.carpeta, "data", f"lineas_{it:02d}.csv")
            with open(ruta, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["layer", "key", "channel", "index", "x_channel",
                            "y_channel", "z_channel", "x_top", "y_top", "z_top",
                            "length_m", "dz_m", "mean_slope_pct"])
                for nombre in ("GRD_SubRidges", "GRD_Swales", "GRD_Ridges"):
                    c = capa(nombre)
                    if c is None:
                        continue
                    for f in c.getFeatures():
                        vs = list(f.geometry().vertices())
                        if len(vs) < 2:
                            continue
                        L = f.geometry().length()
                        a, b = vs[0], vs[-1]
                        dz = b.z() - a.z()
                        pend = (dz / L * 100.0) if L else 0.0
                        canal = f["channel"] if "channel" in \
                            [fl.name() for fl in c.fields()] else ""
                        idx = f["index"] if "index" in \
                            [fl.name() for fl in c.fields()] else ""
                        clave = f"{canal}|{idx}" if canal != "" else str(f.id())
                        fila = [nombre, clave, canal, idx,
                                round(a.x(), 1), round(a.y(), 1), round(a.z(), 2),
                                round(b.x(), 1), round(b.y(), 1), round(b.z(), 2),
                                round(L, 1), round(dz, 2), round(pend, 1)]
                        w.writerow(fila)
                        self.tabla_lineas.append(fila)
        except Exception:
            pass

    def _leyenda_cutfill(self, m, rango=None):
        c = m.get("cut_m3", 0) or 0
        f = m.get("fill_m3", 0) or 0
        esc = ""
        if rango:
            esc = (f"  Colour scale: dark red = {abs(rango[0]):.1f} m of CUT, "
                   f"white = no change, dark blue = {rango[1]:.1f} m of FILL; "
                   "the intensity is the thickness.")
        return ("CUT/FILL HEAT MAP (design surface minus original ground). "
                "RED = cut (excavate), BLUE = fill (place soil), white = "
                f"balance.{esc}  Totals: cut {c:,.0f} m3 · fill {f:,.0f} m3 · "
                f"net {c - f:,.0f} m3 · dozer index {m.get('dozer_idx')}")

    @staticmethod
    def _pie_georref(extent, ancho, alto):
        """Texto que permite al modelo pasar de píxel a coordenada."""
        try:
            esc_x = extent.width() / max(ancho, 1)
            esc_y = extent.height() / max(alto, 1)
            return (f"GEOREF: image {ancho}x{alto} px covers X "
                    f"{extent.xMinimum():,.0f}..{extent.xMaximum():,.0f} and Y "
                    f"{extent.yMinimum():,.0f}..{extent.yMaximum():,.0f} m "
                    f"({esc_x:.2f} m/px in X, {esc_y:.2f} m/px in Y). "
                    f"X grows to the RIGHT, Y grows UPWARDS: "
                    f"X = {extent.xMinimum():,.0f} + col*{esc_x:.3f}, "
                    f"Y = {extent.yMaximum():,.0f} - row*{esc_y:.3f}.")
        except Exception:
            return ""

    def _render(self, extent, nombres, ruta, pie, ancho=900, alto=900):
        """Render de un subconjunto de capas a PNG con leyenda y georreferencia
        en el pie, para que el modelo pueda situar lo que ve en coordenadas."""
        try:
            proj = QgsProject.instance()
            capas = []
            for n in nombres:
                if n == "_DEM_":
                    if getattr(self, "dem", None) is not None:
                        capas.append(self.dem)
                    continue
                for l in proj.mapLayers().values():
                    if l.name() == n:
                        capas.append(l)
                        break
            if not capas:
                return None
            ms = QgsMapSettings()
            ms.setLayers(capas)
            ms.setBackgroundColor(QColor(255, 255, 255))
            ms.setOutputSize(QSize(ancho, alto))
            ms.setDestinationCrs(proj.crs())
            ms.setExtent(QgsRectangle(extent))
            job = QgsMapRendererParallelJob(ms)
            job.start()
            job.waitForFinished()
            img = job.renderedImage()
            # pie con la leyenda, para que el modelo con visión pueda leerla
            final = QImage(ancho, alto + 62, QImage.Format.Format_ARGB32)
            final.fill(QColor(255, 255, 255))
            qp = QPainter(final)
            qp.drawImage(0, 0, img)
            qp.setPen(QPen(QColor(0, 0, 0)))
            fnt = QFont()
            fnt.setPointSize(9)
            qp.setFont(fnt)
            qp.drawLine(0, alto + 1, ancho, alto + 1)
            texto = pie + "  " + self._pie_georref(QgsRectangle(extent),
                                                   ancho, alto)
            qp.drawText(6, alto + 4, ancho - 12, 56,
                        int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                            | Qt.TextFlag.TextWordWrap), texto)
            qp.end()
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            final.save(ruta, "PNG")
            return ruta if os.path.exists(ruta) else None
        except Exception as e:
            self.log(f"   · render fallido ({os.path.basename(ruta)}): {e}")
            return None

    # ---------------------------------------------------------- web
    def buscar(self, consulta):
        if not self.permitir_web:
            return []
        from .ai_client import buscar_web
        res = buscar_web(consulta)
        for r in res:
            self.notas_web.append(f"{r['titulo']} — {r['resumen']} ({r['url']})")
        return res

    def guardar_prompt_base(self, sistema):
        try:
            with open(os.path.join(self.carpeta, "prompt_base.md"), "w",
                      encoding="utf-8") as fh:
                fh.write(sistema)
        except Exception:
            pass
