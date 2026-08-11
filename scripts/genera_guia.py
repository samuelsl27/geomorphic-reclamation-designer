# -*- coding: utf-8 -*-
"""Genera help/guide.html: guía bilingüe con las mismas pestañas del programa."""
import sys
import html
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guia_datos import PESTANAS

VER = "1.0.24"

CSS = """
:root{--tinta:#1d2b36;--suave:#5a6b78;--linea:#dfe6ec;--acento:#0b6ea8;
       --fondo:#ffffff;--caja:#f5f8fa;--codigo:#eef3f7}
*{box-sizing:border-box}
body{margin:0;font:15px/1.62 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
     color:var(--tinta);background:var(--fondo)}
header{position:sticky;top:0;z-index:10;background:#fff;border-bottom:1px solid var(--linea);
       padding:14px 26px 0}
.fila{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
h1{font-size:19px;margin:0 0 2px;font-weight:650}
.ver{color:var(--suave);font-size:13px}
.idioma{margin-left:auto;display:flex;gap:6px}
.idioma button{font:600 12px/1 inherit;padding:7px 13px;border:1px solid var(--linea);
       background:#fff;color:var(--suave);border-radius:14px;cursor:pointer}
/* El botón del idioma ACTIVO se resalta con el atributo de <html>: sin
   JavaScript de por medio, así que no puede volver a ocurrir que el
   conmutador se quede sin uno de los dos botones. */
html[data-idioma="en"] .idioma button[data-idioma="en"],
html[data-idioma="es"] .idioma button[data-idioma="es"]{
       background:var(--acento);border-color:var(--acento);color:#fff}
nav{display:flex;gap:2px;margin-top:12px;overflow-x:auto}
nav button{font:600 13px/1 inherit;padding:11px 16px;border:none;background:none;
       color:var(--suave);cursor:pointer;border-bottom:3px solid transparent;white-space:nowrap}
nav button.on{color:var(--acento);border-bottom-color:var(--acento)}
main{max-width:920px;margin:0 auto;padding:26px 26px 90px}
section{display:none} section.on{display:block}
h2{font-size:22px;margin:0 0 6px;font-weight:650}
h2 + p.lead{color:var(--suave);margin:0 0 26px}
h3{font-size:16px;margin:30px 0 14px;font-weight:650;color:var(--acento)}
hr{border:none;border-top:1px solid var(--linea);margin:32px 0 0}
.item{padding:16px 0;border-bottom:1px solid var(--linea)}
.item:last-child{border-bottom:none}
.nom{font-weight:650;font-size:14.5px;margin-bottom:5px}
.nom code{background:none;padding:0;font-size:14.5px}
.txt p{margin:0 0 9px} .txt p:last-child{margin-bottom:0}
.nota{background:var(--caja);border-left:3px solid var(--acento);padding:14px 18px;
      border-radius:0 5px 5px 0;margin:0 0 22px}
code{background:var(--codigo);padding:1px 5px;border-radius:3px;
     font:13px/1.45 ui-monospace,Consolas,monospace}
.sub{color:var(--suave);font-weight:400;font-size:13px}
/* El idioma se decide con UN atributo en <html>, no marcando cada elemento.
   Los bloques de texto llevan data-l="en" | "es" y se oculta el que no toca.
   Los botones del conmutador llevan data-idioma, un atributo DISTINTO: si
   compartiesen data-l con el contenido, la regla de abajo ocultaría el botón
   del idioma inactivo y no habría forma de volver a cambiarlo — que es
   justamente lo que pasaba. */
html[data-idioma="es"] [data-l="en"]{display:none}
html[data-idioma="en"] [data-l="es"]{display:none}
footer{max-width:920px;margin:0 auto;padding:0 26px 50px;color:var(--suave);font-size:13px}
@media print{nav,.idioma{display:none}section{display:block!important}}
"""

JS = """
function idioma(l){
  if(l!=='en' && l!=='es'){l='es';}
  document.documentElement.setAttribute('data-idioma', l);
  try{localStorage.setItem('gfq_lang_v2', l);}catch(e){}
}
function pestana(id){
  document.querySelectorAll('main section').forEach(function(s){
    s.classList.toggle('on', s.id===id);});
  document.querySelectorAll('nav button').forEach(function(b){
    b.classList.toggle('on', b.dataset.t===id);});
  window.scrollTo(0,0);
}
function arranque(){
  /* Orden de preferencia:
       1. lo último que eligió el usuario en la guía,
       2. #lang=xx, que es el idioma de QGIS y lo pone el botón Help,
       3. el idioma del navegador,
       4. español.
     localStorage falla en file:// en algunos navegadores, por eso va dentro
     de try: sin él la guía sigue funcionando, solo que no recuerda. */
  var l=null;
  try{l=localStorage.getItem('gfq_lang_v2');}catch(e){}
  if(l!=='en' && l!=='es'){
    var m=/lang=(en|es)/.exec(location.hash||'');
    l = m ? m[1] : null;
  }
  if(l!=='en' && l!=='es'){
    var nav=(navigator.language||navigator.userLanguage||'es').toLowerCase();
    l = nav.indexOf('en')===0 ? 'en' : 'es';
  }
  document.documentElement.setAttribute('data-idioma', l);
  pestana('general');
}
/* Si el documento ya está cargado cuando se ejecuta este script (pasa en
   algunos visores incrustados), DOMContentLoaded no vuelve a dispararse. */
if(document.readyState==='loading'){
  document.addEventListener('DOMContentLoaded', arranque);
}else{ arranque(); }
"""

TITULOS = {
 "general": ("Overview, method and project files",
             "Visión general, metodología y ficheros de proyecto",
             "What the plugin does, how a design is built and how projects and layers are stored.",
             "Qué hace el complemento, cómo se construye un diseño y cómo se guardan proyectos y capas."),
 "setup":   ("Setup tab and Global Settings",
             "Pestaña Setup y ajustes globales",
             "The three inputs the design needs, and the local variables of the method.",
             "Las tres entradas que el diseño necesita y las variables locales del método."),
 "channels":("Channels tab",
             "Pestaña Channels",
             "Growing the network and giving each channel its geometry and hydrology.",
             "Hacer crecer la red y dar a cada canal su geometría y su hidrología."),
 "output":  ("Output tab",
             "Pestaña Output",
             "From the network to the design surface, the contours and the earthwork balance.",
             "De la red a la superficie de diseño, las curvas de nivel y el balance de tierras."),
 "dwg":     ("DWG tab",
             "Pestaña DWG",
             "Analysis, checks, volumes, profiles and hand editing of what has been generated.",
             "Análisis, comprobaciones, volúmenes, perfiles y edición manual de lo generado."),
 "ai":      ("AI Optimization tab",
             "Pestaña AI Optimization",
             "Optional refinement of a finished design with a language model running on your own machine.",
             "Refinamiento opcional de un diseño terminado con un modelo de lenguaje que corre en tu máquina."),
}

def item(nombre, en, es):
    if nombre.startswith("__"):
        return ('<div class="nota">'
                f'<div class="txt" data-l="en">{en}</div>'
                f'<div class="txt" data-l="es">{es}</div></div>')
    return ('<div class="item">'
            f'<div class="nom"><code>{nombre}</code></div>'
            f'<div class="txt" data-l="en">{en}</div>'
            f'<div class="txt" data-l="es">{es}</div></div>')

partes = []
# data-idioma va YA en el HTML: si el JavaScript no llegase a ejecutarse, la
# guía se ve igual en español en vez de quedarse en blanco.
partes.append('<!DOCTYPE html><html lang="es" data-idioma="es">'
              '<head><meta charset="utf-8">'
              '<meta name="viewport" content="width=device-width,initial-scale=1">'
              '<title>Geomorphic Reclamation Designer — Guide / Guía</title>'
              f'<style>{CSS}</style></head><body>')
partes.append('<header><div class="fila"><div>'
              '<h1>Geomorphic Reclamation Designer</h1>'
              f'<div class="ver">Parameter guide · Guía de parámetros · v{VER}</div></div>'
              '<div class="idioma">'
              '<button type="button" data-idioma="en" '
              'onclick="idioma(\'en\')">English</button>'
              '<button type="button" data-idioma="es" '
              'onclick="idioma(\'es\')">Español</button>'
              '</div></div><nav>')
for i, (cid, etq, _) in enumerate(PESTANAS):
    # la primera pestaña nace marcada, por lo mismo: sin JS sigue leyéndose
    cls = ' class="on"' if i == 0 else ''
    partes.append(f'<button type="button" data-t="{cid}"{cls} '
                  f'onclick="pestana(\'{cid}\')">{html.escape(etq)}</button>')
partes.append('</nav></header><main>')
for i, (cid, etq, bloques) in enumerate(PESTANAS):
    t_en, t_es, l_en, l_es = TITULOS[cid]
    cls_sec = ' class="on"' if i == 0 else ''
    partes.append(f'<section id="{cid}"{cls_sec}>')
    partes.append(f'<h2><span data-l="en">{t_en}</span><span data-l="es">{t_es}</span></h2>')
    partes.append(f'<p class="lead"><span data-l="en">{l_en}</span>'
                  f'<span data-l="es">{l_es}</span></p>')
    for nombre, en, es in bloques:
        partes.append(item(nombre, en, es))
    partes.append('</section>')
partes.append('</main><footer>'
              '<p data-l="en">Setting names are kept in English in both languages so '
              'they match the interface exactly. Slopes are negative downstream. '
              'This guide is generic: calibrate the local variables against a '
              'natural reference area with the same material and climate as your '
              'site.</p>'
              '<p data-l="es">Los nombres de los ajustes se mantienen en inglés en '
              'los dos idiomas para que coincidan exactamente con la interfaz. Las '
              'pendientes son negativas aguas abajo. Esta guía es genérica: '
              'calibra las variables locales contra un área natural de referencia '
              'con el mismo material y clima que tu emplazamiento.</p>'
              f'</footer><script>{JS}</script></body></html>')

ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "src", "geomorphic_reclamation_designer", "help", "guide.html")
with open(ruta, "w", encoding="utf-8") as fh:
    fh.write("\n".join(partes))
print("escrito:", os.path.normpath(ruta))
