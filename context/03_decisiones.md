# Registro de decisiones (ADR)

Formato: **contexto → decisión → consecuencias → alternativas descartadas**.
Lo más reciente arriba. No borres una decisión superada: márcala y explica qué
la sustituyó.

---

## ADR-014 · Nombre público «Geomorphic Reclamation Designer»

**Fecha**: 2026-07 · **Estado**: aceptada

**Contexto.** El proyecto se ha llamado internamente `geofluv_q` / *GeoFluvQ*.
*GeoFluv™* y *Natural Regrade®* son **marcas registradas** de sus titulares
(N. Bugosh / Carlson Software). Publicar en GitHub un complemento libre con ese
nombre es un riesgo legal innecesario y además induce a pensar que es el
producto original o un derivado suyo.

**Decisión.**
- Nombre público del complemento: **Geomorphic Reclamation Designer**.
- Paquete Python / carpeta del complemento: `geomorphic_reclamation_designer`.
- Repositorio: `geomorphic-reclamation-designer`.
- **Se conservan** por compatibilidad técnica: prefijo de capa `GF_`, extensión
  `.geofluv.json`, clases `GeoFluvBuilder`, `GeoFluvDock`, `GeoFluvProject`.
- El método se cita siempre como *"método fluvio-geomórfico (tipo Natural
  Regrade)"*, con la referencia bibliográfica.

**Por qué este nombre.** *«Geomorphic reclamation»* es el **término estándar y
descriptivo** del campo, no la marca de nadie: se usa así en la literatura
revisada por pares (Martín Duque et al. 2017; Bugosh & Epp 2019). Un nombre
descriptivo es exactamente lo que interesa aquí: nadie puede reclamar derechos
exclusivos sobre él, y dice qué hace el programa sin apoyarse en la marca ajena.

**Ojo con una confusión posible.** *Geomorphic Reclamation Design* (2024) es
además el **título del libro** de Bugosh & Martín Duque, que es nuestra
referencia principal. El nombre del complemento se le parece mucho. Para que no
parezca el software oficial del libro:

- el `NOTICE` lo dice explícitamente;
- el README cita el libro **como fuente**, con sus autores, no como respaldo;
- nunca se usa la formulación *«el software del libro»* ni equivalentes.

Si algún día llegara una objeción de los autores, el cambio es barato (§«Por qué
el renombrado fue barato»).

**Consecuencias.** Los usuarios que tenían `geofluv_q` instalado verán un
complemento nuevo en la lista; deben desinstalar el viejo. **Los proyectos
`.geofluv.json` y las capas `GF_*` siguen funcionando sin tocar nada.**

**Por qué el renombrado fue barato.** Todo el código usa **importaciones
relativas** (`from .core.compat import …`), así que renombrar la carpeta raíz
solo obligó a tocar el nombre de la carpeta, `metadata.txt` y `__init__.py`.
Merece la pena conservar esa propiedad: **no metas importaciones absolutas del
paquete** en `src/`.

**Alternativas descartadas.**
- *Seguir con GeoFluvQ*: riesgo de marca al publicar.
- *Mine Geomorphological Rehabilitation*: correcto pero largo y algo genérico;
  «rehabilitation» es menos usado que «reclamation» en la literatura del campo.
- *OpenRegrade / GeoRegrade*: cortos y con buena resonancia, pero *«regrade»*
  evoca directamente *Natural Regrade®*, que es justo lo que se quería evitar.
- *Renombrar también `GF_` y `.geofluv.json`*: rompería todos los proyectos ya
  hechos por el autor a cambio de nada.

---

## ADR-013 · Licencia AGPL-3.0-or-later + CLA

**Fecha**: 2026-07 · **Estado**: aceptada

**Contexto.** El autor quiere: (a) que el código sea **siempre libre**, (b) que
cualquiera pueda usarlo **gratis, personal y profesionalmente**, y (c)
reservarse la posibilidad de **cobrar en el futuro por un servicio web / en
servidor**.

**Decisión.** **AGPL-3.0-or-later** para el código, más un **CLA** que otorga a
Samuel Sáez López los derechos necesarios para relicenciar (modelo *open core /
doble licencia*).

**Por qué AGPL y no GPL o MIT.** La AGPL es la única de las tres que cubre el
caso *"alguien monta un SaaS con esto y no devuelve nada"*: su §13 obliga a
publicar el código fuente **también a los usuarios que interactúan por red**.
Eso es exactamente lo que preserva la opción comercial del autor: un tercero que
quiera ofrecerlo como servicio sin liberar su código tendrá que negociar una
licencia comercial.

**Por qué el CLA es imprescindible.** Sin él, el autor **no podría** ofrecer una
licencia comercial, porque el copyright de las contribuciones sería de cada
contribuyente y la AGPL no permite relicenciar código ajeno.

**Consecuencias.**
- Todo contribuyente firma el CLA antes de que se acepte su PR.
- Cada fichero fuente lleva cabecera de copyright y licencia.
- Nunca se integra código de terceros sin CLA ni código de origen propietario.

**Alternativas descartadas.**
- *MIT/Apache*: no cumple (c) — cualquiera monta el SaaS y no devuelve nada.
- *GPL-3.0*: no cubre el uso por red, que es justo el caso que preocupa.
- *AGPL sin CLA*: bloquearía al propio autor para relicenciar.
- *Fuente disponible no libre (BSL)*: incumple (a).

---

## ADR-012 · `context/` como memoria explícita del proyecto

**Fecha**: 2026-07 · **Estado**: aceptada

**Contexto.** El desarrollo se ha hecho en sesiones largas con asistentes de IA
que pierden el contexto al terminar. Se han repetido errores ya resueltos y se
ha perdido tiempo redescubriendo por qué una constante vale lo que vale.

**Decisión.** Carpeta `context/` versionada con el conocimiento condensado
(método con citas, bugs con causa raíz, decisiones, invariantes, métricas
medidas, trampas del entorno, backlog y bitácora), y obligación en `AGENTS.md`
de leerla antes de tocar y de actualizarla al terminar.

**Consecuencias.** Cuesta unos minutos por sesión. A cambio, cualquier agente
arranca con el estado real del proyecto en lugar de deducirlo del código.

**Alternativas descartadas.** *Comentarios en el código* (no cuentan la historia
transversal); *issues de GitHub* (no los lee un agente por defecto);
*documentación de usuario* (público distinto, objetivo distinto).

---

## ADR-011 · Primero curvar, después recortar; nunca volver a curvar

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-017

**Decisión.** El perfil de una línea de ladera se calcula **una sola vez**, con
la geometría completa, y **después** se recorta contra el corredor del cauce.
`divides._rehacer_laderas()` se conserva pero **no se llama**, con aviso en el
docstring.

**Consecuencias.** Una línea recortada conserva la forma de la curva original en
el tramo que sobrevive — que es lo que hace el original y lo que el usuario
identificó como el resultado bueno.

---

## ADR-010 · El pie de ladera se identifica por distancia, no por cota

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-018

**Decisión.** `Corredor._cerca(x, y) → (índice, distancia, estación)` es el
criterio único para saber qué extremo de una línea es el pie.

**Razón física.** Donde el cauce va **en relleno**, la ladera desciende *desde*
el cauce: el pie es el punto **más alto**. Cualquier criterio basado en Z falla
en ese caso, que es frecuente en el margen alto del perímetro.

---

## ADR-009 · La divisoria no tiene límite de pendiente de ladera

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-012

**Decisión.** Al perfil longitudinal de una divisoria **no** se le aplica
`pendiente_max_pct`. Solo actúa `MAX_PENDIENTE_FILO = 100 %` como cortapicos.

**Evidencia.** La divisoria del original desciende al **41 % de media y 73 % de
máximo**. Aplicarle el máximo de ladera la dejaba 17 m colgada sobre el cauce.

---

## ADR-008 · Correcciones de extremo mezcladas con *smoothstep*

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-009

**Decisión.** Ninguna corrección de cota se aplica a un solo vértice.
`ajustar_extremo()` y `_sellar_extremo()` reparten la corrección sobre una
longitud de mezcla (`MEZCLA_*`) con `3u² − 2u³` y después imponen monotonía
direccional.

---

## ADR-007 · Orden fijo dentro de `perfil_desde_control()`

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-014

**Decisión.**
`_restaurar_control → _monotonizar → _suavizar_entre_control → _limitar_pendiente`.
**El limitador de pendiente va SIEMPRE el último.**

---

## ADR-006 · Recorte por diferencia geométrica, no recorriendo desde los extremos

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-010

**Decisión.** `recortar_contra_corredor()` calcula la diferencia geométrica real
y devuelve **todos** los trozos exteriores al corredor.

**Principio general.** *"Las implementaciones deben funcionar en todos los
escenarios, no solo en el ejemplo con el que depuramos."* Recorrer desde los
extremos es un atajo que solo funciona en la topología del caso de prueba.

---

## ADR-005 · La máscara del corredor protege el cauce del suavizado

**Fecha**: 2026-07 · **Estado**: aceptada · **Origen**: bug B-015

**Decisión.** `surface.mascara_corredor(...)` genera una máscara fija que
`suavizar_raster()` respeta, y la celda del ráster se dimensiona con
`CELDAS_POR_CAUCE = 3.0` sobre la anchura **mediana** del bankfull.

**Por qué la mediana y no la mínima.** Con la mínima, un solo tramo estrecho
disparaba el número de celdas por encima de `CELDAS_MAX = 12 000 000`.

---

## ADR-004 · La IA es guía, no motor

**Fecha**: 2026-06 · **Estado**: aceptada

**Decisión.** El bucle de optimización lo lleva el complemento. El modelo local
recibe números, historial e imágenes y devuelve **en JSON qué variables mover y
por qué**. El complemento valida cada propuesta contra rangos y regenera la
geometría con el motor.

**Consecuencia clave.** **Toda solución es geométricamente válida por
construcción.** El modelo no puede producir un diseño imposible; como mucho,
propone un cambio que se ignora por salirse de rango (y queda anotado).

**Además.** El modelo corre **en local** (Ollama / LM Studio): sin servidor, el
resto del complemento funciona igual y el mismo bucle sigue en modo numérico.
No sale ningún dato del proyecto a Internet.

---

## ADR-003 · La divisoria es una V que pasa por la confluencia

**Fecha**: 2026-06 · **Estado**: aceptada · **Origen**: bug B-007

**Decisión.** `ridges._partir_en_confluencias()` parte la cadena Voronoi en la
confluencia y genera **dos** crestas, ancladas ahí en X, Y y Z.

**Razón geométrica.** Aguas arriba de la unión hay divisoria por los **dos**
lados del tributario.

---

## ADR-002 · Atributos por nombre de campo

**Fecha**: 2026-05 · **Estado**: aceptada · **Origen**: bug B-006

**Decisión.** `compat.attrs()` es el único camino para rellenar atributos.
GeoPackage añade un campo `fid` al principio y desplaza todo lo demás.

---

## ADR-001 · `hydrology.py` sin QGIS

**Fecha**: 2026-04 · **Estado**: aceptada

**Decisión.** El módulo hidráulico es **Python puro**, sin importar `qgis.*`.

**Razón.** Es la parte que hay que poder verificar contra el libro sin arrancar
un SIG. Permite `pytest` en CI sin instalar QGIS, y hace `test_libro.py` posible.

**Consecuencia.** Cualquier cosa que necesite capas va en `builder` o en
`surface`, no en `hydrology`.
