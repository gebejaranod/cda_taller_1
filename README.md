# Taller 1 — Supervisión de contratación pública de bienes

**MINE-4101 · Ciencia de Datos Aplicada** · Universidad de los Andes · Semestre 2026-20

Análisis de 196.391 contratos de compraventa y suministros firmados por entidades públicas
colombianas entre 2019 y 2025 (SECOP II), orientado a **focalizar la supervisión** de la
oficina de control interno: identificar qué características de un contrato, conocidas desde
el momento de la firma, se asocian con desviaciones en su ejecución.

## Integrante

| Nombre | Correo | Código |
|---|---|---|
| Gabriel Esteban Bejarano Delgado | gabriel.ebd3@gmail.com | 202626558 |

## Declaración de uso de inteligencia artificial

Este trabajo se desarrolló con asistencia de **Claude Code** (Anthropic). Declaro de forma
explícita el alcance de ese uso:

**Lo que hizo la herramienta.** Escribió la totalidad del código del repositorio: los nueve
módulos de `src/`, los cuatro notebooks y los scripts de perfilado. Asistió también en la
redacción de los documentos —este README, `docs/01_hallazgos_datos.md` y
`docs/informe_ejecutivo.md`— y en la producción de las figuras y tablas de `reports/`.

**Lo que fue decisión mía.** Todas las decisiones de fondo del análisis se tomaron bajo mi
criterio y con mi aprobación explícita en cada bifurcación. En particular:

- La estructura del proyecto en **dos iteraciones** con un punto de control intermedio, para no
  comprometer el diseño analítico antes de entender la calidad de los datos.
- La **redefinición de la variable objetivo** tras comprobar que las tres desviaciones del
  enunciado no son medibles en su forma literal, y la elección de `desviacion` como objetivo
  principal frente a las alternativas evaluadas.
- El tratamiento de la **zona ciega** de pagos: analizarla como pregunta propia en lugar de
  excluirla del análisis.
- La decisión de **no usar una serie de IPC externa**: se declara la limitación y la tabla de
  riesgo se recalcula cada año.
- La exclusión de la **duración declarada** de los criterios pese a su gradiente fuerte, por
  riesgo de fuga de información.
- El uso exclusivo de **herramientas vistas en clase**: la focalización se construye con la
  tabla de riesgo valor × modalidad.
- La exclusión de los **atributos del representante legal** de todo criterio de focalización.
- El criterio metodológico de exigir **tamaño de efecto** y no solo significancia estadística,
  y el de **marcar en lugar de eliminar** registros problemáticos.

**Verificación.** Revisé el código, los supuestos estadísticos y los resultados. Los cuatro
notebooks se ejecutan secuencialmente sin errores desde un estado limpio, y toda cifra citada en
los documentos es reproducible a partir de ellos. Asumo la responsabilidad por el contenido, las
conclusiones y las limitaciones declaradas en este trabajo.

## Objetivo

Entregar a la oficina de control interno un conjunto de **criterios de focalización basados en
datos** que le permitan priorizar, con un equipo de supervisión pequeño, los contratos con
mayor probabilidad de desviarse de su plan inicial.

## Alcance

- **Universo:** contratos de bienes (compraventa y suministros), firmas entre 2019-01-01 y
  2025-12-31, extraídos de SECOP II. 196.391 registros × 36 atributos.
- **Definición de desviación:** adición de plazo, o subejecución presupuestal parcial real.
  Ver [`docs/01_hallazgos_datos.md`](docs/01_hallazgos_datos.md) §1 para la justificación de
  por qué las tres definiciones literales del enunciado no son directamente utilizables.
- **Fuera de alcance:** servicios, obra y consultoría (el dataset está prefiltrado a bienes);
  sobrecostos frente a precios de mercado (no hay cantidades ni precios unitarios); calidad o
  cumplimiento de la entrega (no existe variable de resultado).

## Estado del proyecto

El taller se desarrolla en dos iteraciones, con un punto de control entre ellas.

| Iteración | Contenido | Estado |
|---|---|---|
| 1 | Entendimiento y calidad de datos (punto 1) | **Completa** |
| 2 | Estrategia, desarrollo de hipótesis y resultados (puntos 2–4) | **Completa** |

**Entregable principal:** [`docs/informe_ejecutivo.md`](docs/informe_ejecutivo.md)

## Hallazgos principales

### De la Iteración 1 (calidad de datos)

1. **Ninguna de las tres desviaciones del enunciado es medible en su forma literal.** El
   compuesto literal se activa en el **83,77 %** de los contratos, lo que no permite focalizar
   nada. `valor_pagado` resultó ser una bandera de reporte casi binaria (54,77 % exactamente en
   cero, 26,11 % exactamente en 100 %) y `liquidación = No` es la norma administrativa (60,30 %),
   no una anomalía.
   El objetivo se redefinió como adición de plazo **o** subejecución parcial real:
   **13,55 % de prevalencia**. La subejecución solo se evalúa donde el plazo ya venció —
   un contrato en curso que lleva pagado el 40 % no está subejecutado, no ha terminado.

   **Por qué se descartaron dos de las tres:** la frecuencia es el diagnóstico. Una señal que
   se activa en 6 de cada 10 contratos no describe un contrato que se desvía, describe cómo se
   opera el sistema. El cero en `valor_pagado` no dice que no se pagó: dice que no se registró
   el pago, y no hay forma de separar una cosa de la otra. `liquidación = No` no marca un
   cierre irregular: marca el trámite que la mayoría de las entidades no completa. Las dos
   miden el **uso del sistema de registro**, no la ejecución del contrato, y tomarlas al pie de
   la letra convertiría un fallo administrativo en un hallazgo de supervisión. El fallo de
   registro no se perdió como hallazgo: se reubicó como frente de acción propio (hallazgo 11).

2. **La completitud del dataset es falsa.** 34 de 36 columnas declaran cero nulos, pero
   **206.821 celdas** son centinelas de texto (`No Definido`, `No aplica`, `UNSPECIFIED`,
   `xxxx`). La completitud efectiva es 97,04 %, no 99,97 %. Un `df.info()` no lo detecta.

3. **Un solo contrato concentra el 99,47 % del valor monetario total** — 8 veces el PIB anual
   de Colombia. Toda media o suma cruda del valor es inservible.

4. **`estado_contrato` no es confiable.** 51.238 contratos siguen marcados «En ejecución»
   aunque su plazo ya venció, y su composición cambia radicalmente entre años. La
   observabilidad del desenlace se determina por fecha, no por estado.

5. **Primera señal de focalización:** la tasa de desviación va del 10,46 % en régimen especial
   al **34,25 % en licitación pública**, más de tres veces. La Iteración 2 confirmó que la
   diferencia es significativa y que la modalidad tiene el mayor efecto de las pruebas primarias
   sobre la adición de plazo (V = 0,144).

6. **Restricción de diseño:** `dias_adicionados > 0` es casi sinónimo de
   `estado = Modificado` (91,8 % de las adiciones), así que el estado no puede usarse para
   anticiparla. Y como el negocio decide a quién supervisar desde la firma, los criterios solo
   pueden usar variables conocidas en ese momento.

### De la Iteración 2 (contrastes y focalización)

7. **Solo dos atributos discriminan de verdad: el valor del contrato y la modalidad.** Se
   acumulan entre sí. Licitación pública por encima de 1.000 millones se desvía en el **41,5 %**
   de los casos; contratación directa por debajo de 10 millones, en el **3,2 %**. Un rango de
   más de 12 veces.

8. **La tabla de riesgo mejora de verdad a una revisión al azar, pero de forma moderada.**
   Revisando el **30 %** de los contratos de mayor riesgo se detecta el **48 %** de las
   desviaciones, 1,6 veces lo que daría el azar; en el nivel 1, el 5 % de los contratos, la
   ganancia llega a 2,5 veces. Es una mejora real y medida, no un cambio de paradigma.

9. **Con n ≈ 196.000 el valor p deja de informar.** De doce pruebas, once resultaron
   significativas y solo cinco superan el umbral de efecto que se fijó antes de ver los datos; de
   esas cinco, una tiene un efecto propio pequeño una vez descontados el valor y la modalidad, y
   otra describe el registro, no la ejecución. El género del
   representante legal salió «significativo» (p = 0,0009) con una diferencia de 0,43 puntos
   porcentuales: se incluyó como control precisamente para hacer visible ese problema, y queda
   excluido de todo criterio.

10. **El destino del gasto, que el enunciado sugería como criterio, no sirve para focalizar.**
    Cerca de la mitad de su diferencia bruta es composición —la inversión firma contratos más
    caros— y, dentro de cada rango de valor, lo que queda no llega al umbral de relevancia
    (V ≤ 0,045).

11. **Entre las pruebas primarias, el hallazgo de mayor tamaño de efecto es sobre el
    registro, no sobre la ejecución**
    (V = 0,222): la zona ciega de pagos se concentra por sector, y algunos de los sectores que
    peor reportan, como Transporte, se desvían menos de lo que anticipa su mezcla de valor y
    modalidad. Requiere un frente de acción propio.

Detalle completo de la Iteración 1 en **[`docs/01_hallazgos_datos.md`](docs/01_hallazgos_datos.md)**;
resultados y recomendaciones en **[`docs/informe_ejecutivo.md`](docs/informe_ejecutivo.md)**.

## Organización del repositorio

```
cda_taller_1/
├── notebooks/                           Ejecutar en orden numérico
│   ├── 01_entendimiento_datos.ipynb     Punto 1 (20 %): entendimiento y calidad
│   ├── 02_estrategia_analisis.ipynb     Punto 2 (15 %): estrategia y hipótesis
│   ├── 03_desarrollo_estrategia.ipynb   Punto 3 (40 %): contrastes y control por composición
│   └── 04_resultados_focalizacion.ipynb Punto 4 (25 %): tabla de riesgo y niveles
├── src/                                 Código reutilizable que importan los notebooks
│   ├── config.py                        Rutas, centinelas, umbrales de plausibilidad
│   ├── carga.py                         Lectura del parquet y sus metadatos
│   ├── utiles.py                        Normalización de texto, entropía, JSON seguro
│   ├── diccionario.py                   Diccionario semántico de las 36 variables
│   ├── perfilado.py                     Perfilado de calidad y 21 reglas de integridad
│   ├── limpieza.py                      Pipeline de tratamiento y señales objetivo
│   ├── inferencia.py                    Pruebas del curso con tamaño de efecto e IC
│   └── viz.py                           Estilo compartido de figuras
├── data/
│   ├── raw/secop_bienes.parquet         Dataset original (se versiona)
│   └── processed/                        Generado por el notebook 01 (no se versiona)
├── docs/
│   ├── informe_ejecutivo.md             ENTREGABLE del punto 4
│   ├── informe_ejecutivo.pdf            El mismo informe, listo para imprimir
│   ├── presentacion_ejecutiva.html      Presentación ejecutiva (abre sin servidor)
│   ├── 01_hallazgos_datos.md            Hallazgos y decisiones de la Iteración 1
│   ├── 02_correspondencia_estadistica.md  Cada prueba y su rama del árbol de decisión
│   └── enunciado_taller_1.pdf           Enunciado del taller
└── reports/
    ├── figures/                          Figuras en PNG
    └── tablas/                           Tablas de perfilado, reglas y bitácora
```

## Instrucciones de ejecución

### Requisitos

- **Python 3.12** (probado en 3.12.10)
- Windows, macOS o Linux. Los comandos siguientes son para **PowerShell en Windows**.

### Preparar el entorno

```powershell
cd cda_taller_1
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

En macOS o Linux, sustituir `.\.venv\Scripts\` por `./.venv/bin/`.

### Ejecutar los notebooks

Deben correrse **en orden numérico**. El notebook 01 genera
`data/processed/contratos_limpio.parquet`, del que dependen los siguientes.

```powershell
.\.venv\Scripts\jupyter.exe nbconvert --to notebook --execute --inplace notebooks\01_entendimiento_datos.ipynb
```

O de forma interactiva:

```powershell
.\.venv\Scripts\jupyter.exe lab
```

Cada notebook corre de principio a fin sin errores partiendo de un `data/processed/` vacío.

### Dependencias

Fijadas en [`requirements.txt`](requirements.txt): pandas 2.2.3, numpy 2.1.3, pyarrow 18.1.0,
scipy 1.14.1, statsmodels 0.14.4, matplotlib 3.9.3, seaborn 0.13.2,
jupyter 1.1.1, nbconvert 7.16.4, tabulate 0.9.0.

## Reproducibilidad

- La **fecha de observación está congelada** en `src/config.py` (`FECHA_CORTE = 2026-09-23`).
  Dos resultados dependen de ella —la regla R12 y la dimensión «Actualidad» del índice de
  calidad—, así que dejarla en `date.today()` haría que el reporte cambiara con el calendario.
- El `sha256` del parquet se registra en la salida del notebook 01, de modo que los resultados
  quedan atados a unos bytes de entrada concretos.
- Toda operación de muestreo usa la semilla `config.SEMILLA = 42`.
- `data/processed/` no se versiona: es un artefacto derivado que el notebook 01 regenera.