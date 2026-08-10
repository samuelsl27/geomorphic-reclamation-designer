# Glosario ES / EN

El código está en español; los **nombres de ajustes y de capas están en inglés**
para que coincidan letra por letra con la interfaz del programa de referencia.
Esta tabla traduce entre los dos mundos.

## Elementos del diseño

| Español (código) | English (UI / literatura) | Qué es |
|---|---|---|
| límite de diseño | Design Boundary | Polígono del área a rehabilitar. `GRD_Boundary`. En el programa original y en los comentarios antiguos aparece como *GeoFluv boundary* |
| fondo de valle | valley bottom | Polilínea 2D aproximada del eje del futuro valle. Entrada del usuario. `GRD_ValleyBottoms` |
| canal / cauce | channel | Eje 3D generado. `GRD_Channels` |
| canal principal | main channel | El que desagua fuera del límite |
| tributario | tributary | Canal que entra en otro |
| boca / desembocadura | mouth / outlet | Extremo aguas abajo. Su pendiente es **el dato más crítico** |
| cabecera | headwater / head | Extremo aguas arriba |
| confluencia | confluence / junction | Donde un tributario entra en su receptor |
| transición | transition point | Estación donde el canal deja de ser tipo A |
| cresta / divisoria | ridge / ridgeline / divide | Línea de máxima cota entre dos cuencas. `GRD_Ridges` |
| subcresta | sub-ridge | Cresta secundaria en un ápice de meandro. `GRD_SubRidges` |
| vaguada | swale | Línea de vaguada entre dos subcrestas. `GRD_Swales` |
| silla | saddle | Rebaje de la cresta entre dos culminaciones (libro §9.11.2, p. 259; el libro NO da su profundidad) |
| ladera | hillslope | Superficie entre el cauce y la divisoria |
| pie de ladera | hillslope toe | Arranque de la ladera **junto al cauce** (¡no el punto bajo!) |
| espolón | spur | Arranque de una subcresta sobre el cauce |
| corredor | corridor | Banda alrededor del eje del cauce donde no puede haber cresta |
| borde | bank / edge | Líneas paralelas de fondo, bankfull y flood-prone. `GRD_Banks` |
| sección | cross-section | Punto de cálculo con toda la hidráulica. `GRD_XSections` |
| subcuenca | sub-watershed | Área que drena a un canal. Partición Voronoi |
| superficie de diseño | design surface | Ráster TIN del terreno propuesto. `GRD_DesignSurface` |
| curvas de nivel | contours | `GRD_Contours` (LineStringZ) |
| corte / relleno | cut / fill | `GRD_CutFill (m)`, `GRD_HaulRegions`, `GRD_HaulRoutes` |
| acarreo | haul | Transporte de tierras, volumen × distancia |
| densidad de drenaje | drainage density | Longitud de canal por unidad de área (m/ha) |
| esponjamiento | swell | Aumento de volumen al excavar |
| compactación | compaction / shrink | Reducción al compactar en relleno |

## Hidráulica

| Español | English | Símbolo | Unidad |
|---|---|---|---|
| caudal punta | peak flow | Qpk | m³/s |
| caudal formador | bankfull discharge | Q_bkf | m³/s |
| caudal de avenida | flood-prone discharge | Q_fp | m³/s |
| coeficiente de escorrentía | runoff coefficient | C | – |
| intensidad | rainfall intensity | i | mm/h |
| anchura formadora | bankfull width | W | m |
| calado formador | bankfull depth | d | m |
| relación anchura:profundidad | width:depth ratio | W:D | – |
| ancho de fondo | bottom width | b | m |
| talud | side slope | z | H:V |
| radio hidráulico | hydraulic radius | R | m |
| perímetro mojado | wetted perimeter | P | m |
| tensión tractiva | tractive force / shear stress | τ | N/m² |
| tensión crítica | critical shear stress | τ_crit | N/m² |
| rugosidad | roughness | n (Manning) | – |
| sinuosidad | sinuosity | k | – |
| radio de curvatura | radius of curvature | Rc | m |
| longitud de meandro | meander length | λ | m |
| cinturón de meandro | meander belt width | B | m |
| ratio de atrincheramiento | entrenchment ratio | W_fp / W | – |
| número de Froude | Froude number | F | – |

## Términos del código que conviene reconocer

| Nombre | Significa |
|---|---|
| `Corredor` | Clase de `divides.py`: banda alrededor del eje del cauce. Sabe si un punto está dentro, a qué distancia y a qué estación |
| `perfil_trapezoidal` | La curva de ladera del libro: convexa arriba (longitud `xc`), recta en medio, cóncava al pie |
| `smoothstep` | `3u² − 2u³`. Reparte una corrección sin escalones |
| `Hermite monótono` | Curva vertical del perfil longitudinal, con la condición de Fritsch–Carlson que impide que se ondule |
| `ajustar_extremo` | Mezcla una corrección de cota sobre una longitud de mezcla, no la pega en el vértice |
| `_sellar_extremo` | Lo mismo, para el sellado contra divisorias |
| `perfil_desde_control` | Método residual: recalcula el perfil respetando puntos de control |
| `MEZCLA_*` | Longitud (m) sobre la que se reparte una corrección |
| `TOL_*` | Tolerancia geométrica (m) |
| `Hallazgo` | Un resultado del *Check Design* (código, severidad, grupo, geometría) |
| `Candidato` | Una propuesta del optimizador de IA, con sus variables y métricas |

## Siglas

| Sigla | Significa |
|---|---|
| **DEM** | Modelo digital de elevaciones (terreno de partida) |
| **TIN** | Red de triángulos irregulares |
| **DD** | Densidad de drenaje |
| **NR** | Natural Regrade (el método de referencia) |
| **IMGA** | Instituto de Minería y Geología Aplicada / equipo de opengeorock.org |
| **UPCT** | Universidad Politécnica de Cartagena |
| **CRS / SRC** | Sistema de referencia de coordenadas |
| **ADR** | Architecture Decision Record |
