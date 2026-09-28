# Correspondencia con el inventario de pruebas del curso

**Propósito:** documentar qué prueba estadística se aplicó a cada hipótesis, por qué esa y no
otra, y cómo se validó su supuesto. Toda prueba reportada como contraste pertenece al inventario
de la presentación *Estadística inferencial* del curso.

**Reproducible en:** [`notebooks/03_desarrollo_estrategia.ipynb`](../notebooks/03_desarrollo_estrategia.ipynb)
· tablas de respaldo en [`reports/tablas/pruebas_hipotesis.csv`](../reports/tablas/pruebas_hipotesis.csv),
[`pruebas_robustez.csv`](../reports/tablas/pruebas_robustez.csv) y
[`validacion_supuestos.csv`](../reports/tablas/validacion_supuestos.csv)

---

## 1. El árbol de decisión y dónde se usa cada rama

La prueba no se elige por conveniencia: la determina el tipo de las dos variables que se cruzan.

| Rama del árbol | Prueba | Dónde se usa | Contrastes |
|---|---|---|---|
| Numérica vs. numérica | **Correlation Test** | H2 (decil de valor × tasa de desviación) | 1 |
| Numérica vs. categórica, ≤ 2 grupos, muestras **grandes** | **Z Test** | H2b (log₁₀ del valor, con y sin desviación) | 1 |
| Numérica vs. categórica, ≤ 2 grupos, muestras **pequeñas** | **T Test** | *no aplica* | 0 |
| Numérica vs. categórica, > 2 grupos | **ANOVA** | H6 (días adicionados por sector) | 1 |
| Categórica vs. categórica | **Chi-cuadrado** | H1, H3, H4 (×2), H5 (×2), H7, H8 (×2) | 9 |
| | | **Total** | **12** |

**Por qué no aparece el T Test.** Su condición es la muestra pequeña. En este dataset el grupo
más pequeño de cualquier comparación de dos medias tiene 26.603 contratos, así que el árbol
manda al Z Test. Declararlo es parte de justificar la elección.

**Por qué domina el chi-cuadrado.** Los datos son abrumadoramente categóricos: solo 5 de las 36
variables son numéricas, y de esas cinco, cuatro no pueden usarse como criterios por fuga de
información (§2.1 de [`01_hallazgos_datos.md`](01_hallazgos_datos.md)). No es una preferencia
metodológica, es la estructura del dataset.

---

## 2. Los doce contrastes

| # | Hipótesis | Tipo de cruce | Prueba | n | Efecto | Utilizable |
|---|---|---|---|---|---|---|
| H1 | Adición por modalidad | cat × cat | χ² | 196.391 | V = 0,144 | **Sí** |
| H2 | Tasa por nivel de valor | num × num | Correlación de Pearson | 10 deciles | r = 0,954 [0,81; 0,99] | **Sí** |
| H2b | Valor de los que se desvían | num × cat (2) | Z test | 196.391 | factor 2,81× [2,74; 2,88] | **Sí** |
| H3 | Subejecución por destino | cat × cat | χ² | 88.142 | 4,29 pp [3,88; 4,69] | No¹ |
| H4-orden | Adición por orden | cat × cat | χ² | 196.382 | V = 0,015 | No |
| H4-sector | Adición por sector | cat × cat | χ² | 171.917 | V = 0,089 | No |
| H5-prorrogable | Adición por prorrogabilidad | cat × cat | χ² | 196.391 | V = 0,057 | No |
| H5-pago adelantado | Adición por pago adelantado | cat × cat | χ² | 167.884 | V = 0,003 | **No significativo** |
| H6 | Magnitud de la adición por sector | num × cat (23) | ANOVA de Welch | 16.678 | η² = 0,032 | No |
| H7 | **Control:** género del representante | cat × cat | χ² | 160.569 | V = 0,0094 | No |
| H8-orden | Zona ciega por orden | cat × cat | χ² | 196.382 | V = 0,037 | No |
| H8-sector | Zona ciega por sector | cat × cat | χ² | 171.917 | V = 0,222 | **Sí**² |

¹ Supera el umbral de 2 pp sobre la subejecución, pero sobre la desviación el efecto propio del
destino del gasto es pequeño: cerca de la mitad de su diferencia bruta es composición y, dentro de
cada rango de valor, la V de Cramér no pasa de 0,045 (notebook 03, §12). No es un criterio de
focalización.
² Es el mayor efecto del análisis, pero describe el registro y no la ejecución: requiere un
frente de acción propio.

---

## 3. Criterios de decisión, fijados antes de ver los datos

Están declarados en [`src/config.py`](../src/config.py) y los consumen los notebooks 02 a 04, de
modo que ningún contraste puede ajustar su propio umbral en función del resultado.

| Criterio | Constante | Valor | Se aplica a |
|---|---|---|---|
| Nivel de significancia | `ALFA` | 0,05 | todas las pruebas primarias |
| Relevancia práctica | `V_MINIMA_UTIL` | 0,10 | los nueve contrastes χ² |
| Relevancia práctica | `DIF_MINIMA_PP` | 2,0 pp | H3, diferencia de proporciones |
| Relevancia práctica | `RHO_MINIMO_UTIL` | 0,30 | H2, correlación |
| Relevancia práctica | `FACTOR_MINIMO_UTIL` | 1,5× | H2b, Z test sobre log₁₀(valor) |
| Relevancia práctica | `ETA2_MINIMO_UTIL` | 0,06 | H6, ANOVA |

Los cinco umbrales de efecto siguen las referencias de Cohen para su estadístico respectivo. El
de H2b se expresa como factor multiplicativo porque es la forma en que el resultado le habla al
negocio: un contrato tiene que ser al menos una vez y media más caro para que el criterio sirva
de algo operativamente.

---

## 4. Validación de supuestos

El paso 3 del procedimiento no termina al elegir la prueba: exige validar sus supuestos. **Los
doce contrastes cumplen el suyo.** Tabla completa en
[`validacion_supuestos.csv`](../reports/tablas/validacion_supuestos.csv); dos casos merecen
comentario.

**H6 — varianzas muy desiguales.** La razón entre la varianza mayor y la menor entre sectores es
de **12,6×**, y la asimetría máxima dentro de un grupo llega a **6,0**. El ANOVA clásico asume
varianzas iguales, así que usarlo aquí sería elegir la prueba sin validar su supuesto. Se usa la
variante de **Welch**, que no lo exige, y que es además la misma elección conservadora que hace
el ejemplo trabajado del curso al preferir Welch sobre el t clásico. La normalidad la cubre el
teorema central del límite: 34 observaciones en el grupo más pequeño, 16.678 en total.

**H2b — distribución no normal.** `log₁₀(valor)` no es normal (asimetría −0,78 en el grupo sin
desviación). Pero el Z test no exige normalidad de los datos sino de la **distribución de la
diferencia de medias**, que el TCL garantiza con 26.603 y 169.788 observaciones por grupo. Se usa
la variante de varianzas desiguales, coherente con la elección de Welch en H6.

**Los nueve contrastes χ²** cumplen el supuesto de frecuencia esperada ≥ 5 con holgura: la
mínima observada es 22,4 (H1). Para conseguirlo se agrupan en «Otros» las categorías con menos
del 1 % de los registros, que era necesario porque `modalidad_de_contratacion` tiene una
categoría de solo 236 registros (0,12 %).

---

## 5. Verificaciones de robustez

En las tres hipótesis donde la asimetría de los datos podría hacer dudar de una prueba
paramétrica, se añade la alternativa no paramétrica. **No se reportan como el contraste**: su
función es comprobar que la conclusión no depende de esa asimetría, que es lo que da contenido
real a la validación de supuestos.

| Hipótesis | Prueba primaria | Verificación | Resultado |
|---|---|---|---|
| H2 | Correlación de Pearson, r = 0,954 | Spearman entre deciles | ρ = 1,000 — monotonía sin una sola excepción |
| H2 | *(ídem)* | Spearman fila a fila | ρ = 0,184 — ver nota |
| H2b | Z test, factor 2,81× | Mann-Whitney + delta de Cliff | p < 10⁻³⁰⁰, δ = 0,316 — coincide |
| H6 | ANOVA de Welch, η² = 0,032 | Kruskal-Wallis + ε² | p = 1,5 × 10⁻¹¹³, ε² = 0,035 — coincide |

**Nota sobre la brecha de H2.** La correlación a nivel de decil (r = 0,95) y la correlación fila
a fila (ρ = 0,18) no se contradicen: miden cosas distintas. La tendencia *agregada* es
prácticamente perfecta —la tasa sube en los diez deciles sin excepción— mientras que la
capacidad de discriminar un contrato *individual* es débil. Esa brecha explica por qué la tabla
de riesgo del notebook 04 detecta el 48 % de las desviaciones revisando el 30 % de los contratos,
y no mucho más; conviene tenerla presente antes de prometer más de lo que los datos pueden dar.

---

## 6. Qué acompaña a las pruebas sin ser una prueba del inventario

Ninguna conclusión del taller depende de técnicas ajenas a la presentación *Estadística
inferencial*: no se usan modelos predictivos. Cuatro elementos acompañan a las pruebas sin ser
pruebas del inventario, y se declaran.

**El control por composición** (notebook 03, §12). No es una prueba nueva: repite el
chi-cuadrado dentro de cada rango de valor y compara la tasa observada de un grupo con la que
anticipa su mezcla de valor y modalidad, que es un promedio de tasas. Responde lo que ninguna
prueba bivariada responde sola —cuánto de una diferencia es del atributo y cuánto de los
contratos que lo acompañan— y su resultado principal es **negativo**: el destino del gasto no
llega al umbral de relevancia dentro de ningún rango de valor.

**La tabla de riesgo** (notebook 04). La tasa de desviación de cada combinación de valor y
modalidad, con su intervalo de confianza del 95 % calculado con la fórmula de clase: estimación
± Z × error estándar, con el error estándar de una proporción.

**Las verificaciones de robustez** (Mann-Whitney con delta de Cliff y Kruskal-Wallis). Son las
alternativas no paramétricas del Z test y del ANOVA; sirven para validar supuestos, el paso 3
del procedimiento (§5), y ninguna conclusión depende de ellas.

**Los tamaños de efecto** (V de Cramér, delta de Cliff, ε², η²). No son pruebas sino la forma de
cumplir el requisito de separar la significancia estadística de la relevancia práctica. La V de
Cramér es el acompañante estándar del chi-cuadrado, y sin una medida de este tipo el criterio de
decisión se reduciría al valor p, que es precisamente lo que el curso advierte que no debe
hacerse.
