# Comparación contra la salida del programa original

Toda la validación geométrica del proyecto se ha hecho **midiendo** contra la
salida del Natural Regrade original sobre el **mismo terreno y los mismos
ajustes**. Esta página es la tabla de referencia: si un cambio mueve alguno de
estos números en la dirección equivocada, es una regresión.

**Casos de prueba**: dos emplazamientos de referencia internos (no se publican
sus datos), cada uno con su carpeta `GRD_Files/` y su `GeoFluv_origen/`.

| | Ej_1 | Ej_2 |
|---|---|---|
| canales | 2 | **6** |
| área | 23.3 ha | 35.6 ha |
| líneas de canal del original | 17 | 39 |
| líneas de cresta/vaguada del original | 104 | **244** |
| proyecto nativo del original (`.geo`/`.ggs`) | no | **sí** |

**El Ej_2 es el que manda desde 2026-08-10**: tiene confluencias múltiples,
tributarios cortos y empinados y un tramo con el cauce por encima del perímetro,
y destapó cinco bugs (B-023…B-027) en código que llevaba meses «validado»
contra el Ej_1. El Ej_1 se conserva como **red de seguridad**: no puede
empeorar.

Solo el Ej_2 conserva el proyecto nativo del programa original, así que es el
único donde se puede comparar **ajuste a ajuste** (`scripts/leer_geo.py`) y no
solo geometría contra geometría.

---

## Línea base del Ej_2 ANTES de la ronda de correcciones (2026-08-10)

Medido con `scripts/comparar_original.py`. Es el punto de partida contra el que
hay que comparar cuando se remida en QGIS.

| Magnitud | Nuestro | Original |
|---|---|---|
| Peor pendiente de segmento (subcrestas) | **955.4 %** | 65.7 % |
| Líneas de relieve por encima del 100 % | **19** | 0 |
| Líneas por debajo del cauce más bajo | 1 (−6.56 m) | 0 |
| Meseta más larga (vértices a la misma cota) | **27** | 2 |
| Líneas de relieve, longitud total | 14 352 m | 19 705 m |
| Líneas de relieve, número | 218 | 244 |
| Espaciado a lo largo del cauce | 13.0 m | 11.5 m |
| Ángulo medio con el eje | 51.3° | 60.5° |
| Pendiente recta cresta-pie (p50 / media) | 17.4 % / 21.6 % | 19.0 % / 21.0 % |
| Pendiente de cabecera, main L1 | 23.67 % | 16.16 % |
| Pendiente de cabecera, main R4 | 32.72 % | 18.29 % |
| Pendiente de cabecera, main | 16.11 % | 17.57 % |
| Longitud del canal principal | 1068.1 m | 1076.0 m |
| Cota de boca del canal principal | 275.03 m | 275.03 m |

Y el Ej_1, que ya estaba sano y **no puede empeorar**:

| Magnitud | Nuestro | Original |
|---|---|---|
| Peor pendiente de segmento (subcrestas) | 87.2 % | 84.7 % |
| Líneas por encima del 100 % | 0 | 0 |
| Meseta más larga | 18 | 2 |
| Longitud del canal principal | 925.7 m | 935.2 m |

## ⏳ Pendiente de remedir en QGIS (v1.0.19)

Las correcciones B-023…B-027 y ADR-018 **están hechas, con 117 tests en verde,
pero NO se han medido todavía en QGIS real**. Hasta que se remidan, las tablas
de abajo siguen siendo las de v1.0.17 y la de arriba es el «antes».

Lo verificado sin QGIS, ejecutando el motor de perfiles directamente:

| Canal Ej_2 | pedida | antes | ahora | original |
|---|---|---|---|---|
| main L1 | −15.40 % | −26.91 % | **−15.40 %** | −16.16 % |
| main R4 | −17.44 % | −36.95 % | **−17.44 %** | −18.29 % |
| main | −18.00 % | −18.00 % | −18.00 % | −17.57 % |

Deciles de pendiente boca→cabecera de main L1:

```
original  6.5  9.8 12.6 14.9 16.5 17.6 18.1 18.1 17.4 16.2
antes     6.6  8.8 10.9 13.0 15.2 17.3 19.4 21.6 23.7 25.8
ahora     7.7 11.4 14.5 16.8 18.5 19.5 19.8 19.4 18.3 16.5
```

Y el reparto de una corrección de extremo, que era la causa de las mesetas:

```
antes: 284.8 … 302.9 303.2 303.2 303.2 303.2 303.2 303.2 303.2
ahora: 284.8 … 300.7 301.2 301.4 301.5 301.5 301.6 301.9 302.4 303.2
```

**Ojo con ADR-018**: la pendiente N-E baja las crestas orientadas al norte y al
este en la proporción 22/33, así que cambia el balance de tierras. Al remedir
hay que rehacer la tabla entera, no solo mirar los defectos de forma.

---

## Estado del Ej_1 (v1.0.17, pendiente de remedir)

| Magnitud | Nuestro | Original | Veredicto |
|---|---|---|---|
| Extremo bajo de la divisoria sobre el lecho | **+2.29 m** | +2.29 m | ✅ idéntico |
| Distancia de la divisoria al eje del cauce | 6.62 m | 7.12 m | ✅ −7 % |
| Pie de ladera → borde de inundación | 0.01 m | 0.33 m | ✅ |
| Subcresta idx 3 | 1079.72→1062.00, 15.3 % | (fid 699) 1079.08→1062.00, 12.4 % | ✅ |
| Subcresta idx 7 | 1073.42→1062.00, 13.3 % | (fid 726) 1072.47→1062.00, 14.2 % | ✅ |
| Δz en cruces curva de nivel / cauce (mediana) | 0.021 m | 0.001 m | 🟡 aceptable |
| Peor gradiente vértice a vértice | **92 %** | — | ✅ (era 2070 %) |
| Empalmes forzados con el límite | **1** (peor 0.09 m) | — | ✅ (eran 27, peor 19.68 m) |
| Errores del *Check Design* | **2** (67 avisos, 56 info) | — | 🟡 los 2 son de τ |

## Canales (medido en v1.0.13, sin cambios posteriores relevantes)

| Magnitud | Nuestro | Original | Δ |
|---|---|---|---|
| Longitud del canal principal | 924.2 m | 935.2 m | −1.2 % |
| Sinuosidad del canal principal | 1.254 | 1.269 | −1.2 % |
| Longitud del tributario | 471.3 m | 473.8 m | −0.5 % |

## Crestas y vaguadas (v1.0.13)

| Magnitud | Nuestro | Original | Nota |
|---|---|---|---|
| Líneas que arrancan del canal principal | 60 | 73 | |
| Longitud media | 101 m | 104 m | ✅ |
| Espaciado a lo largo del canal | 15.5 m | 12.5 m | 🟡 |
| Ángulo respecto al eje | 74° | 64° | 🟡 |

> **Palanca conocida**: para acercar el ángulo y el espaciado, subir *Angle from
> sub-ridge to channel's perpendicular* de 10° a ~25°. Es un **ajuste**, no un
> bug del motor.

## Divisorias — perfil longitudinal del original

Medido sobre las polilíneas del DXF original, porque es lo que justifica ADR-009:

| Magnitud | Valor |
|---|---|
| Pendiente media de descenso de la divisoria | **41 %** |
| Pendiente máxima | **73 %** |

Por eso **no** se le aplica `pendiente_max_pct` (el máximo de *ladera*, típico
33–46 %): la divisoria del original la supera con holgura y es correcto.

## Evolución del *Check Design*

| Versión / hito | Errores | Avisos | Info |
|---|---|---|---|
| Primera ejecución (v1.0.16) | 13 | — | — |
| Tras corregir empalmes y sellado | 9 | — | — |
| **v1.0.17 actual** | **2** | 67 | 56 |

Los 2 errores restantes son de **tensión tractiva** (invariante H1): hay
estaciones con `τ > τ_crit`. Está en el backlog decidir si es un problema del
motor, del `D50` introducido o un aviso legítimo de que el diseño necesita
protección local. Ver `context/08_pendiente.md`.

---

## Cómo repetir la comparación

```bash
python scripts/comparar_original.py RUTA_DEL_EJEMPLO
python scripts/comparar_original.py RUTA_DEL_EJEMPLO --json informe.json
```

`RUTA_DEL_EJEMPLO` es la carpeta con `GRD_Files/` (lo nuestro) y
`GeoFluv_origen/` (el GeoPackage importado del DXF del original). **No necesita
QGIS ni GDAL**: lee los GeoPackage con `scripts/lector_gpkg.py`, que es
`sqlite3` más un parser de WKB propio. Eso importa más de lo que parece: el DXF
del original llega con arcos, así que sus polilíneas son `CompoundCurve` (tipo
9) y no `LineString`; un lector que solo entienda el tipo 2 devuelve **cero**
entidades y la comparación sale vacía sin dar ningún error.

Emite cuatro bloques: inventario, canales (longitud, sinuosidad, cotas y perfil
longitudinal por deciles), líneas de relieve (espaciado, ángulo, longitud, cota
de coronación) y defectos de forma (peor pendiente de segmento, líneas por
encima del 100 %, líneas por debajo del cauce, meseta más larga y vaivén).

**Los canales se emparejan por COTA DE CABECERA, no por nombre.** En el Ej_2 los
parámetros de los tributarios estaban tecleados en orden invertido, así que
emparejar por nombre daba falsos negativos en todo. La cota de cabecera la fija
el DEM en el extremo del fondo de valle, es la misma en los dos programas y
coincide con menos de 0.1 m.

Y para comparar los AJUSTES, no la geometría, cuando el ejemplo conserve el
proyecto nativo del original (`.geo` / `.ggs`):

```bash
python scripts/leer_geo.py Ej_2_GeoFluv_File.geo --comparar GRD_x.grd.json
python scripts/leer_geo.py Ej_2_GeoFluv_File.geo --fusionar GRD_x.grd.json
```

## Reglas para interpretar una comparación

1. **Coincidir al 100 % no es el objetivo.** El original tiene factores
   aleatorios (`Random scale factors`); dos ejecuciones suyas tampoco coinciden.
   Lo que debe coincidir es el **orden de magnitud y la forma**.
2. **Las cotas de anclaje sí deben coincidir**: extremo bajo de la divisoria,
   pie de ladera, confluencias. Ahí no hay aleatoriedad.
3. **Una diferencia sistemática en un ajuste** (espaciado, ángulo) es una
   calibración, no un bug. Anótala como palanca.
4. **Una diferencia en la FORMA** (meseta, zanja, cola vertical, escalón) sí es
   un bug, siempre.
