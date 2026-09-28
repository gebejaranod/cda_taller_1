# Hallazgos del entendimiento de datos — punto de control Iteración 1

**Dataset:** `secop_bienes.parquet` · 196.391 contratos × 36 columnas · 31,7 MB
**SHA-256:** `3eb495b1d7fda28e28863ed57f18e59a4aa611b565c77df6b9790951e1bcb0d2`
**Ventana de firmas:** 2019-01-01 a 2025-12-31
**Fecha de observación (congelada):** 2026-09-23
**Reproducible en:** [`notebooks/01_entendimiento_datos.ipynb`](../notebooks/01_entendimiento_datos.ipynb)

Este documento cierra la Iteración 1 y fija las decisiones que condicionan la Iteración 2.

---

## 1. Veredicto sobre las señales objetivo

El enunciado define la desviación de tres formas. **Ninguna es utilizable en su forma
literal.** Este es el hallazgo que más afecta al diseño del resto del taller.

| Señal del enunciado | Definición literal | Prevalencia | Veredicto |
|---|---|---|---|
| Adición de plazo | `dias_adicionados > 0` | 9,51 % | **Usable** |
| Presupuesto no ejecutado | `pagado / valor < 90 %` | 59,64 % | **No usable** |
| Presupuesto no ejecutado (estricta) | `0 < pagado / valor < 90 %` | 4,93 % | **Usable** |
| Presupuesto no ejecutado (estricta, observable) | la anterior **y** plazo vencido | 4,76 % | **Adoptada** |
| Cierre sin liquidar | `liquidación = No` | 60,30 % | **No usable como objetivo** |
| Compuesto literal de las tres | al menos una | **83,77 %** | **No usable** |

### Por qué falla cada una

**`valor_pagado` es una bandera de reporte, no una medida de avance.** La distribución del
ratio de ejecución es bimodal en los extremos: **54,77 % marca exactamente 0** y **26,11 %
exactamente 100 %**, con otro 14,10 % entre el 90 % y el 100 %. Solo el 4,93 % muestra ejecución
parcial real. El 54,77 % de ceros mezcla
dos cosas indistinguibles entre sí: contratos genuinamente no ejecutados y contratos cuyo pago
nunca se reportó en la plataforma. Contar ese cero como subejecución convertiría un fallo
administrativo de reporte en un hallazgo de supervisión.

**Y la subejecución solo es interpretable una vez vencido el plazo.** Un contrato en curso que
lleva pagado el 40 % no está subejecutado: no ha terminado. La señal se evalúa únicamente donde
`fecha_de_fin < fecha de corte` —el 99,52 % del dataset— y queda en NaN, no en `False`, para los
948 cuyo desenlace no es observable: 928 con el plazo aún vigente y 20 cuya fecha de fin se anuló
por imposible. Eso baja la señal de 4,93 % a **4,76 %**. La
adición de plazo no necesita esa condición, porque un día añadido es un hecho consumado se haya
cerrado el contrato o no.

**`sin_liquidar` es la norma, no la anomalía.** Se activa en 6 de cada 10 contratos. Un
indicador con esa prevalencia no focaliza nada: señalaría más de la mitad del universo.

**El compuesto literal se activa en el 83,77 % de los contratos.** Recomendar supervisar al
84 % del universo es equivalente a no recomendar nada.

### Decisión adoptada

```
desviacion = (dias_adicionados > 0)
             OR (0 < valor_pagado / valor_del_contrato < 0,90  Y  plazo vencido)
```

**Prevalencia: 13,55 %** (26.603 contratos). Es una tasa que sí permite priorizar.

Complementos disponibles en el dataset tratado:

- `n_senales` (0–3): severidad con las tres señales del enunciado, para no perder la lectura
  literal. Distribución: 0 → 33,60 %, 1 → 58,56 %, 2 → 7,52 %, 3 → 0,32 %.
- `desviacion_severa` (`n_senales >= 2`): 7,84 %, objetivo alternativo más exigente.
- `sin_liquidar` y `pago_cero` se conservan como variables descriptivas.

Las tres señales están **débilmente asociadas entre sí** (φ de Matthews < 0,1 en los tres
pares), lo que confirma que miden fenómenos distintos y justifica analizarlas por separado en
lugar de colapsarlas en un único índice.

---

## 2. Restricciones metodológicas que hereda la Iteración 2

### 2.1 Fuga de información: qué NO puede ser criterio

Estas variables solo se conocen **después** del hecho:

`valor_pagado` · `valor_facturado` · `valor_pendiente_de_pago` · `dias_adicionados` ·
`estado_contrato` · `liquidacion` · `fecha_de_fin_del_contrato`

El negocio necesita decidir a quién supervisar **desde el momento de la firma**, así que los
criterios de focalización deben usar exclusivamente variables disponibles en ese momento: valor
del contrato, modalidad, sector, orden, destino del gasto, tipo de contrato, categoría UNSPSC,
departamento y atributos del proveedor.

### 2.2 `estado_contrato` no puede usarse para anticipar la adición

De las 18.671 adiciones de plazo, **17.147 (91,8 %) están en estado `Modificado`**, donde la
tasa es del 49,76 % frente al 0,04 % en `En ejecución`. `dias_adicionados > 0` es casi un
sinónimo de `estado = Modificado`. Usar uno para anticipar el otro sería circular.

### 2.3 `estado_contrato` tampoco define la observabilidad

**51.238 contratos siguen marcados «En ejecución» aunque su plazo ya venció.** El estado está
rancio. La observabilidad del desenlace se decide por criterio temporal:
`fecha_de_fin_del_contrato < 2026-09-23`, que cubre el **99,52 %** del dataset.

Corolario útil: la censura por contratos en curso **no** es el problema que cabría esperar de
una ventana que llega a 2025. Solo 928 contratos tienen plazo vigente.

### 2.4 Categorías de baja frecuencia

`modalidad_de_contratacion` tiene 9 categorías, una de ellas con 236 registros (0,12 %):
«Seleccion Abreviada Menor Cuantia Sin Manifestacion Interes». Produce frecuencias esperadas
bajas en tablas de contingencia y puede invalidar el supuesto de la prueba χ². Hay que
agruparla o excluirla, declarándolo.

*(Nota: no hay etiquetas duplicadas en el catálogo. Se verificó que ninguna colapsa al
normalizar tildes, mayúsculas y palabras de enlace; las 9 son modalidades distintas.)*

---

## 3. Problemas de calidad y su tratamiento

**Índice global de calidad: 75,99 / 100** («Aceptable con reservas»).
**21 reglas de integridad evaluadas, 18 incumplidas** (4 críticas, 6 altas, 6 medias, 2 bajas).

### 3.1 Los cuatro problemas que más condicionan el análisis

**H01 · Concentración monetaria extrema (crítico).** El contrato `CO1.PCCNTR.3102623`
(Instituto Municipal del Deporte y la Recreación de Yumbo) registra 1,29 × 10¹⁶ COP: el
**99,47 % de la suma total** y **8 veces el PIB anual de Colombia**. Hay 4 contratos por encima
del billón de pesos. → Se conserva `valor_del_contrato` intacto y se añade
`valor_contrato_w` winsorizado al p99,9 (197 filas topadas) más `log_valor`. Toda media o suma
cruda del valor original es inservible; se reporta siempre la mediana.

**H02 · La completitud aparente es falsa (crítico).** 34 de 36 columnas declaran cero nulos,
pero 15 codifican los faltantes como texto: `No Definido`, `No aplica`, `UNSPECIFIED`, `xxxx`.
**206.821 celdas** son centinelas. Completitud aparente 99,97 % frente a efectiva 97,04 %.
→ Se sustituye el catálogo de 25 centinelas por `NaN` antes de perfilar.

Las cinco columnas menos completas de verdad:

| Columna | Aparente | Efectiva | Centinelas |
|---|---|---|---|
| `condiciones_de_entrega` | 100,0 % | 74,56 % | 49.971 |
| `ciudad` | 100,0 % | 78,78 % | 41.672 |
| `genero_representante_legal` | 100,0 % | 81,76 % | 35.822 |
| `habilita_pago_adelantado` | 100,0 % | 85,48 % | 28.507 |
| `sector` | 100,0 % | 87,54 % | 24.474 |

**H03 · Fechas imposibles (crítico).** `fecha_de_fin_del_contrato` va del **año 202 d.C.**
hasta **2065**, sin declarar un solo nulo. → Se anulan las fechas con año fuera de
[2010, 2031]: 20 celdas. `fecha_de_firma` es el único eje temporal sin nulos ni valores
imposibles, y se usa como ancla.

**H04 · `estado_contrato` rancio e inconsistente en el tiempo.** Además de los 51.238
registros ya mencionados, la composición por año cambia drásticamente: 2019 no tiene ni un
contrato «En ejecución» y concentra el 32 % en «Aprobado»; 2025 invierte el patrón con 37,5 %
«En ejecución». La semántica del campo no es estable entre años.

### 3.2 Reglas más incumplidas

| Regla | Sev. | Violaciones | % |
|---|---|---|---|
| R10 · duración declarada ≈ fin − inicio (tol. 10 % o 7 días) | Media | 50.535 | 25,73 % |
| R13 · estado «cerrado» implica pendiente de pago = 0 | Media | 25.782 | 13,13 % |
| R22 · duración parseable a número de días | Alta | 20.819 | 10,60 % |
| R14 · adición > 0 implica contrato prorrogable | Baja | 13.726 | 6,99 % |
| R07 · fecha de firma ≤ fecha de inicio | Alta | 13.047 | 6,64 % |
| R16 · documento y nombre del proveedor consistentes 1:1 | Media | 5.332 | 2,72 % |

R14 es interesante por sí misma: **13.726 contratos registran adición de plazo pese a estar
marcados como no prorrogables.** Es una inconsistencia administrativa que el informe final
puede señalar como criterio de alerta.

### 3.2.1 Una regla que se retiró

La versión anterior de este perfilado incluía una regla **R17 · «ciudad pertenece a un único
departamento»**, que marcaba 7.342 filas (3,74 %). Al revisar las 35 ciudades que la violaban
resultó que **ninguna era un error de dato**: son homónimos legítimos de la geografía
colombiana. Armenia es la capital del Quindío y también un municipio de Antioquia; La Unión
existe en Valle, Antioquia, Nariño y Sucre; Granada en Meta, Antioquia y Cundinamarca; Sucre
es municipio del Cauca, de Santander y del propio departamento de Sucre. La regla tenía una
tasa de falsos positivos del 100 % y penalizaba la dimensión de Consistencia sin que hubiera
suciedad detrás, así que **se eliminó**; sin ella, el índice global queda en 75,99. El bloque C del
notebook 01 reproduce lo que la regla marcaba.

Lo que sí queda registrado —como dependencia funcional, no como defecto— es que **`ciudad` no
es una llave**: sin contar los centinelas, 675 nombres de ciudad cubren 716 pares
`(departamento, ciudad)` distintos, y el dataset no trae código DANE. Cualquier agregación geográfica debe usar el par, nunca la ciudad
sola. El análisis de este taller no agrupa por ciudad en ningún punto.

*(Los identificadores R18–R22 conservan su numeración original: renumerarlos rompería la
trazabilidad con los artefactos ya emitidos.)*

### 3.3 Bitácora de tratamiento

Once pasos, **ninguna fila eliminada**, 34 columnas derivadas. Criterio general: marcar y
documentar antes que borrar, para que la decisión de exclusión quede en manos del análisis y
sea medible.

| Paso | Filas / celdas afectadas |
|---|---|
| 1. Nombres de columna (mojibake) | 4 columnas |
| 2. Centinelas de nulo → `NaN` | 206.821 celdas |
| 3. Grafía de categóricas | 442.619 celdas |
| 4. Fechas imposibles → `NaT` | 20 celdas |
| 5. Duración textual → días | 20.918 sin plazo utilizable (10,65 %): 20.819 no parseables y 99 implausibles |
| 6. Identidad del proveedor | 1.671 documentos fuera de rango |
| 7. URL del proceso | 29 sin `noticeUID` |
| 8. Clasificador UNSPSC | 4.779 sin código válido |
| 9. Winsorización al p99,9 | 197 filas topadas |
| 10. Bandera `calidad_sospechosa` | 13.595 filas (6,92 %) |
| 11. Señales objetivo | 26.603 con desviación (13,55 %) |

Detalle completo con justificación por paso en
[`reports/tablas/bitacora_tratamiento.csv`](../reports/tablas/bitacora_tratamiento.csv).

Dos decisiones de tratamiento que se apartaron de la recomendación automática, y por qué:

- **No se eliminó el dígito de verificación del NIT.** Un NIT de 9 dígitos más DV es
  indistinguible de una cédula de 10 dígitos sin aplicar el checksum, y recortar a ciegas
  fusionaría proveedores distintos. Se conserva el documento normalizado como llave y se marca
  su validez por longitud.
- **La normalización de grafía no reagrupa categorías.** El perfilado verificó que normalizar
  mayúsculas y tildes en todo el dataset solo colapsa 46 registros: `terminado` y `Terminado`
  son valores distintos del catálogo, no dos grafías del mismo valor.

---

## 4. Sobre la selección del periodo

El enunciado pide justificar qué periodo es apropiado. La evidencia recogida:

- **La censura no es el riesgo principal:** el 99,52 % de los contratos ya tiene plazo vencido.
- **El volumen crece 144 %** entre 2019 (16.425 firmas) y 2025 (40.113). El 37,19 % de los
  contratos se firma en el último trimestre del año, un patrón de cierre fiscal.
- **La composición de `estado_contrato` cambia radicalmente por año** (§3.1 H04), así que
  cualquier variable derivada del estado no es comparable entre años.
- **Los valores están en pesos corrientes sin deflactar.** Comparar el valor de 2019 con el de
  2025 sin ajustar por IPC sobreestima el crecimiento real.
- **La tasa de adición sube del 4,2 % (2019) al 17,3 % (2025)**, y dentro de cada año crece
  con el mes de firma. El salto de 2025 es general (la nacional pasa del 11,0 % al 23,1 % y
  suben todas las modalidades con volumen) y no se concentra en pocas entidades. Como los
  contratos de 2025 son los que menos tiempo han tenido para recibir una adición, no es un
  efecto del tiempo de exposición: es un cambio en el registro de las modificaciones o en el
  comportamiento, y los datos no permiten separarlos.
- **2019 es otro registro.** El 60,2 % de sus contratos empieza antes de la fecha de firma
  (desde 2021, menos del 0,3 %), 1.515 terminan antes de ella, y desde abril casi desaparecen
  la contratación directa y el régimen especial.
- **Dos cambios de modalidad responden a la ley, no a errores.** La contratación directa salta
  al 43,1 % de las firmas en enero de 2022 y cae al 1,4 % entre el 29 de enero y el 19 de junio,
  la ventana de restricción de la Ley de Garantías. Con la emergencia del COVID-19 sube al
  25,8 % en abril de 2020.

**Decisión:** no se recorta la ventana a priori. Se conservan los siete años y el **año de
firma entra como control** en los contrastes de la Iteración 2, que es lo que permite separar
el efecto de las características del contrato del efecto de la cobertura creciente de la
plataforma. Cuando una prueba resulte sensible al año, se reporta el resultado por cohorte.

**Verificación posterior (bloque E del notebook 01).** Repetida sin 2019, la matriz de
asociación del notebook 03 no cambia: el cambio máximo de V es 0,018 y ningún par cruza el
umbral de 0,10. Sin 2025, el valor y la modalidad pierden fuerza frente a la adición (de 0,190
a 0,156 y de 0,144 a 0,126), pero siguen siendo las únicas características por encima de 0,10
en la adición y en la desviación. La decisión de conservar los siete años se mantiene.

---

## 5. Decisiones abiertas para la Iteración 2

1. **Objetivo principal:** ¿`desviacion` (13,55 %) o `desviacion_severa` (7,84 %)? La primera
   es el objetivo por defecto; la segunda focaliza más pero reduce los casos positivos.
2. **Tratamiento de la zona ciega:** los 107.452 contratos con pago cero (54,71 %). ¿Se
   excluyen del análisis financiero, o se modelan aparte como «riesgo de no reporte»?
3. **Agrupación de categorías raras** en modalidad y sector para cumplir los supuestos de χ².
4. **Deflactación por IPC:** requiere una serie externa que el repositorio no incluye. De no
   incorporarse, queda como limitación declarada del informe.

---

## 6. Limitación de fondo que debe constar en el informe final

El 54,71 % de contratos con pago cero es una **zona ciega**: puede contener incumplimiento real
que este análisis no detecta, porque los datos no permiten distinguir entre «no se ejecutó» y
«no se reportó». Cualquier tasa de desviación calculada aquí es por tanto un **piso**, no una
estimación puntual del incumplimiento real.
