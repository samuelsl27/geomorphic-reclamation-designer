# Comparación contra la salida del programa original

Toda la validación geométrica del proyecto se ha hecho **midiendo** contra la
salida del Natural Regrade original sobre el **mismo terreno y los mismos
ajustes**. Esta página es la tabla de referencia: si un cambio mueve alguno de
estos números en la dirección equivocada, es una regresión.

**Caso de prueba**: emplazamiento de referencia interno (no se publican sus
datos). El grupo de capas de referencia lleva `origen` en el nombre, que es lo
que buscan los guiones de comparación. Importadas del DXF de la salida
original: 17 polilíneas de canal, 106 de cresta/vaguada y 147 curvas de nivel.

---

## Estado actual (v1.0.17)

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
