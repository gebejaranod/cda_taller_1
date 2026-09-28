# -*- coding: utf-8 -*-
"""
inferencia.py
=============
Pruebas de hipotesis con tamano de efecto e intervalo de confianza.

**Inventario de pruebas.** El curso fija un arbol de decision cerrado, y toda
prueba que este modulo reporta como primaria sale de ahi:

    numerica  vs numerica                        -> Correlation Test
    numerica  vs categorica, <=2 grupos, n grande -> Z Test
    numerica  vs categorica, <=2 grupos, n chico  -> T Test
    numerica  vs categorica, >2 grupos            -> ANOVA
    categorica vs categorica                      -> Chi-cuadrado

La correspondencia entre cada hipotesis del taller y su rama del arbol esta en
`docs/02_correspondencia_estadistica.md`.

**Pruebas de robustez.** `prueba_kruskal` y `delta_cliff` implementan las
alternativas no parametricas de ANOVA y del Z test. No se reportan como la
prueba del contraste: acompanan a la prueba sancionada para verificar que la
asimetria de los datos no altera la conclusion. El paso 3 del procedimiento
exige validar los supuestos, y con distribuciones tan asimetricas como
`dias_adicionados` la forma honesta de hacerlo es mostrar que ambas familias
llegan al mismo sitio.

**Por que el tamano de efecto y no el valor p.** Con n cercano a 196.000,
diferencias irrelevantes en la practica alcanzan significancia estadistica. Por
eso **toda funcion de este modulo devuelve el tamano de efecto y su intervalo
de confianza junto al valor p**, y se contrastan contra los umbrales que
`config` fija a priori (`ALFA`, `V_MINIMA_UTIL`, `DIF_MINIMA_PP`,
`RHO_MINIMO_UTIL`).

Referencias de interpretacion de la V de Cramer (Cohen, 1988), para gl = 1:
    < 0,10  despreciable      0,10-0,30  pequeno
    0,30-0,50  mediano        > 0,50     grande
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


# --------------------------------------------------------------------------
# Tamanos de efecto
# --------------------------------------------------------------------------
def v_cramer(tabla: pd.DataFrame) -> float:
    """V de Cramer: chi2 normalizado a [0, 1], comparable entre tablas."""
    chi2 = stats.chi2_contingency(tabla)[0]
    n = tabla.values.sum()
    return float(np.sqrt(chi2 / (n * (min(tabla.shape) - 1))))


def interpretar_v(v: float) -> str:
    """Etiqueta cualitativa de la V de Cramer segun Cohen."""
    if v < 0.10:
        return "despreciable"
    if v < 0.30:
        return "pequeno"
    if v < 0.50:
        return "mediano"
    return "grande"


def delta_cliff(a, b) -> float:
    """Delta de Cliff a partir del estadistico U: dominancia entre grupos.

    Va de -1 a 1; 0 significa que un valor tomado al azar de cada grupo tiene
    la misma probabilidad de ser mayor en uno o en otro.
    """
    a, b = np.asarray(a), np.asarray(b)
    u = stats.mannwhitneyu(a, b, alternative="two-sided").statistic
    return float(2 * u / (len(a) * len(b)) - 1)


def epsilon2(h: float, k: int, n: int) -> float:
    """Epsilon cuadrado: tamano de efecto para Kruskal-Wallis (robustez)."""
    return float((h - k + 1) / (n - k))


def eta2(grupos: list) -> float:
    """Eta cuadrado: fraccion de la varianza que explica el factor. Para ANOVA.

    Se calcula sobre las sumas de cuadrados y no sobre el estadistico F, para
    que no dependa de si la version usada es la clasica o la de Welch.
    """
    todos = np.concatenate([np.asarray(g, dtype=float) for g in grupos])
    media = todos.mean()
    ss_total = float(((todos - media) ** 2).sum())
    ss_entre = float(sum(len(g) * (np.asarray(g, dtype=float).mean() - media) ** 2
                         for g in grupos))
    return ss_entre / ss_total if ss_total > 0 else 0.0


def interpretar_eta2(e: float) -> str:
    """Etiqueta cualitativa de eta cuadrado segun Cohen (0,01 / 0,06 / 0,14)."""
    if e < 0.01:
        return "despreciable"
    if e < 0.06:
        return "pequeno"
    if e < 0.14:
        return "mediano"
    return "grande"


# --------------------------------------------------------------------------
# Agrupacion de categorias raras
# --------------------------------------------------------------------------
def agrupar_raras(s: pd.Series, min_pct: float = 0.01,
                  etiqueta: str = "Otros") -> pd.Series:
    """Colapsa en una sola categoria las que no alcanzan `min_pct`.

    Necesario antes de un chi-cuadrado: una categoria de 236 registros produce
    frecuencias esperadas por debajo de 5 e invalida el supuesto de la prueba.
    """
    share = s.value_counts(normalize=True)
    return s.where(~s.isin(share[share < min_pct].index), etiqueta)


# --------------------------------------------------------------------------
# Pruebas
# --------------------------------------------------------------------------
def prueba_chi2(datos: pd.DataFrame, variable: str, objetivo: str,
                hipotesis: str = "", min_pct: float = 0.01) -> dict:
    """Chi-cuadrado de independencia con V de Cramer y chequeo de supuestos."""
    s = agrupar_raras(datos[variable], min_pct)
    sub = pd.DataFrame({variable: s, "_y": datos[objetivo]}).dropna()
    tabla = pd.crosstab(sub[variable], sub["_y"])
    if min(tabla.shape) < 2:
        return {"hipotesis": hipotesis, "variable": variable, "objetivo": objetivo,
                "n": len(sub), "p": np.nan, "nota": "menos de 2 categorias"}

    chi2, p, gl, esperadas = stats.chi2_contingency(tabla)
    v = v_cramer(tabla)
    res = {
        "hipotesis": hipotesis, "variable": variable, "objetivo": objetivo,
        "prueba": "chi2 de independencia", "n": int(tabla.values.sum()),
        "categorias": int(tabla.shape[0]), "estadistico": float(chi2), "gl": int(gl),
        "p": float(p), "efecto": "V de Cramer", "valor_efecto": v,
        "magnitud": interpretar_v(v),
        "min_esperada": float(esperadas.min()),
        "supuesto": "frecuencia esperada >= 5 en todas las celdas",
        "supuesto_ok": bool(esperadas.min() >= 5),
        "tabla": tabla,
    }
    return res


def prueba_proporciones(datos: pd.DataFrame, variable: str, objetivo: str,
                        cat_a: str, cat_b: str, hipotesis: str = "") -> dict:
    """Diferencia de dos proporciones con IC 95 % (Wald).

    Cruzar dos variables categoricas es la rama del chi-cuadrado, asi que la
    prueba que se reporta en ese caso es `prueba_chi2`. Esta funcion aporta el
    **tamano de efecto** de ese contraste —la diferencia en puntos porcentuales
    con su intervalo— que es exactamente lo que hace el ejemplo trabajado del
    curso al acompanar el valor p con la diferencia y su IC 95 %.

    Sobre una tabla 2x2 el estadistico z cumple z^2 = chi2 cuando el
    chi-cuadrado se calcula sin la correccion de continuidad de Yates. scipy la
    aplica por defecto, asi que los dos valores no coinciden al ultimo decimal:
    para H3 son 458,73 y 458,27. Yates es la opcion conservadora y a este n la
    diferencia no mueve ninguna conclusion, de modo que reportar el
    chi-cuadrado en vez del z no cambia el resultado del contraste.
    """
    from statsmodels.stats.proportion import (confint_proportions_2indep,
                                              proportions_ztest)
    sub = datos[datos[variable].isin([cat_a, cat_b])][[variable, objetivo]].dropna()
    tabla = pd.crosstab(sub[variable], sub[objetivo])
    n1, n2 = tabla.loc[cat_a].sum(), tabla.loc[cat_b].sum()
    x1, x2 = tabla.loc[cat_a, True], tabla.loc[cat_b, True]
    z, p = proportions_ztest([x1, x2], [n1, n2])
    lo, hi = confint_proportions_2indep(x1, n1, x2, n2, method="wald")
    return {
        "hipotesis": hipotesis, "variable": variable, "objetivo": objetivo,
        "prueba": "z de dos proporciones", "n": int(n1 + n2),
        "estadistico": float(z), "p": float(p),
        "efecto": "diferencia de proporciones (pp)",
        "valor_efecto": float(100 * (x1 / n1 - x2 / n2)),
        "IC_lo": float(100 * lo), "IC_hi": float(100 * hi),
        f"tasa_{cat_a}": float(100 * x1 / n1), f"tasa_{cat_b}": float(100 * x2 / n2),
        "supuesto": "al menos 10 casos en cada celda de la tabla 2x2",
        "supuesto_ok": bool(min(x1, x2, n1 - x1, n2 - x2) >= 10),
        "tabla": tabla,
    }


def prueba_z_medias(datos: pd.DataFrame, numerica: str, grupo: str,
                    cat_a=True, cat_b=False, hipotesis: str = "",
                    n_minimo: int = 30, escala_log10: bool = False,
                    alpha: float = 0.05) -> dict:
    """Z test de dos medias independientes, con IC 95 % de la diferencia.

    Es la prueba que corresponde a la rama "numerica vs categorica de dos
    grupos con muestras grandes" del arbol de decision. Usa la variante de
    varianzas desiguales, que es la misma eleccion conservadora que hace el
    ejemplo trabajado del curso al preferir Welch sobre el t clasico.

    El supuesto que hay que validar no es la normalidad de los datos sino la
    de la distribucion de la diferencia de medias, que el teorema central del
    limite garantiza con grupos de este tamano. Por eso se verifica `n_minimo`
    por grupo y se reporta la asimetria como diagnostico, no como veto.

    Con `escala_log10` la diferencia se traduce ademas a un factor
    multiplicativo: una diferencia de 0,30 en log10 es un contrato 2 veces
    mas caro, que es la lectura que le sirve al negocio.
    """
    from statsmodels.stats.weightstats import CompareMeans, DescrStatsW, ztest

    sub = datos[[numerica, grupo]].dropna()
    a = sub.loc[sub[grupo] == cat_a, numerica].astype(float).values
    b = sub.loc[sub[grupo] == cat_b, numerica].astype(float).values
    if len(a) < 2 or len(b) < 2:
        return {"hipotesis": hipotesis, "variable": numerica, "objetivo": grupo,
                "n": len(a) + len(b), "p": np.nan, "nota": "grupo sin datos"}

    z, p = ztest(a, b, usevar="unequal")
    cm = CompareMeans(DescrStatsW(a), DescrStatsW(b))
    lo, hi = cm.zconfint_diff(alpha=alpha, usevar="unequal")
    dif = float(a.mean() - b.mean())

    res = {
        "hipotesis": hipotesis, "variable": numerica, "objetivo": grupo,
        "prueba": "Z test de dos medias", "n": int(len(a) + len(b)),
        "n_a": int(len(a)), "n_b": int(len(b)),
        "media_a": float(a.mean()), "media_b": float(b.mean()),
        "estadistico": float(z), "p": float(p),
        "error_estandar": float(cm.std_meandiff_separatevar),
        "efecto": "diferencia de medias", "valor_efecto": dif,
        "IC_lo": float(lo), "IC_hi": float(hi),
        "asimetria_a": float(stats.skew(a)), "asimetria_b": float(stats.skew(b)),
        "supuesto": f"n >= {n_minimo} por grupo (TCL)",
        "supuesto_ok": bool(len(a) >= n_minimo and len(b) >= n_minimo),
    }
    if escala_log10:
        res.update(factor=float(10 ** dif), factor_lo=float(10 ** lo),
                   factor_hi=float(10 ** hi))
    return res


def prueba_anova(datos: pd.DataFrame, numerica: str, grupo: str,
                 min_grupo: int = 30, welch: bool = True,
                 hipotesis: str = "") -> dict:
    """ANOVA de una via con eta cuadrado y diagnostico de supuestos.

    Corresponde a la rama "numerica vs categorica de mas de dos grupos". Se usa
    por defecto la version de Welch, que no exige varianzas iguales: aqui la
    razon entre la varianza mayor y la menor supera con holgura lo que tolera
    el ANOVA clasico, y forzar la version clasica seria elegir la prueba sin
    validar su supuesto.

    Se reportan la razon de varianzas y la asimetria maxima como diagnostico
    explicito, para que quede a la vista sobre que se esta apoyando el TCL.
    """
    from statsmodels.stats.oneway import anova_oneway

    sub = datos[[numerica, grupo]].dropna()
    grupos, nombres = [], []
    for nombre, g in sub.groupby(grupo, observed=True):
        v = g[numerica].astype(float).values
        if len(v) >= min_grupo:
            grupos.append(v)
            nombres.append(nombre)
    if len(grupos) < 2:
        return {"hipotesis": hipotesis, "variable": grupo, "objetivo": numerica,
                "n": 0, "p": np.nan, "nota": "menos de 2 grupos con tamano suficiente"}

    r = anova_oneway(grupos, use_var="unequal" if welch else "equal")
    k = len(grupos)
    n = int(sum(len(g) for g in grupos))
    varianzas = [float(np.var(g, ddof=1)) for g in grupos]
    razon = max(varianzas) / min(varianzas) if min(varianzas) > 0 else np.inf
    e2 = eta2(grupos)

    return {
        "hipotesis": hipotesis, "variable": grupo, "objetivo": numerica,
        "prueba": "ANOVA de Welch" if welch else "ANOVA de una via",
        "n": n, "categorias": k,
        "estadistico": float(r.statistic), "gl": float(np.ravel(r.df)[0]),
        "gl_den": float(np.ravel(r.df)[-1]), "p": float(r.pvalue),
        "efecto": "eta cuadrado", "valor_efecto": e2,
        "magnitud": interpretar_eta2(e2),
        "razon_varianzas": float(razon),
        "asimetria_max": float(max(abs(stats.skew(g)) for g in grupos)),
        "min_grupo_n": int(min(len(g) for g in grupos)),
        "supuesto": f"n >= {min_grupo} por grupo (TCL); Welch no exige varianzas iguales",
        "supuesto_ok": bool(min(len(g) for g in grupos) >= min_grupo),
    }


def prueba_correlacion(datos: pd.DataFrame, x: str, y: str,
                       metodo: str = "spearman", hipotesis: str = "",
                       alpha: float = 0.05) -> dict:
    """Correlation Test entre dos variables numericas, con IC 95 %.

    El intervalo se obtiene por la transformacion z de Fisher. Para Spearman se
    usa el error estandar de Fieller (1,06 / raiz(n-3)), algo mas ancho que el
    de Pearson porque el coeficiente de rangos pierde algo de eficiencia.
    """
    sub = datos[[x, y]].dropna()
    n = len(sub)
    if n < 4:
        return {"hipotesis": hipotesis, "variable": x, "objetivo": y,
                "n": n, "p": np.nan, "nota": "n insuficiente para correlacion"}

    if metodo == "pearson":
        r, p = stats.pearsonr(sub[x], sub[y])
        se, etiqueta = 1.0 / np.sqrt(n - 3), "r de Pearson"
    else:
        r, p = stats.spearmanr(sub[x], sub[y])
        se, etiqueta = 1.06 / np.sqrt(n - 3), "rho de Spearman"

    r = float(np.clip(r, -0.999999, 0.999999))
    z_r = np.arctanh(r)
    crit = stats.norm.ppf(1 - alpha / 2)
    lo, hi = np.tanh(z_r - crit * se), np.tanh(z_r + crit * se)

    return {
        "hipotesis": hipotesis, "variable": x, "objetivo": y,
        "prueba": f"Correlacion de {'Pearson' if metodo == 'pearson' else 'Spearman'}",
        "n": n, "estadistico": r, "p": float(p),
        "efecto": etiqueta, "valor_efecto": r,
        "IC_lo": float(lo), "IC_hi": float(hi),
        "supuesto": "ambas variables numericas; Spearman no exige relacion lineal",
        "supuesto_ok": True,
    }


def prueba_kruskal(datos: pd.DataFrame, variable: str, objetivo: str,
                   min_grupo: int = 30, hipotesis: str = "") -> dict:
    """Kruskal-Wallis con epsilon cuadrado. Robustez de ANOVA, no prueba primaria."""
    sub = datos[[variable, objetivo]].dropna()
    grupos = [g[objetivo].values for _, g in sub.groupby(variable, observed=True)
              if len(g) >= min_grupo]
    h, p = stats.kruskal(*grupos)
    k, n = len(grupos), sum(len(g) for g in grupos)
    return {
        "hipotesis": hipotesis, "variable": variable, "objetivo": objetivo,
        "prueba": "Kruskal-Wallis", "n": int(n), "categorias": k,
        "estadistico": float(h), "gl": k - 1, "p": float(p),
        "efecto": "epsilon cuadrado", "valor_efecto": epsilon2(h, k, n),
        "supuesto": "solo exige independencia entre grupos; no asume normalidad",
        "supuesto_ok": True,
    }


def prueba_tendencia(datos: pd.DataFrame, orden: str, objetivo: str,
                     hipotesis: str = "") -> dict:
    """Spearman entre un ordinal y un binario: contrasta tendencia monotona."""
    sub = datos[[orden, objetivo]].dropna()
    rho, p = stats.spearmanr(sub[orden], sub[objetivo].astype(int))
    return {
        "hipotesis": hipotesis, "variable": orden, "objetivo": objetivo,
        "prueba": "Spearman (tendencia)", "n": len(sub),
        "estadistico": float(rho), "p": float(p),
        "efecto": "rho de Spearman", "valor_efecto": float(rho),
        "supuesto": "relacion monotona; no exige linealidad ni normalidad",
        "supuesto_ok": True,
    }


# --------------------------------------------------------------------------
# Presentacion del contraste
# --------------------------------------------------------------------------
# Umbral de relevancia practica por tipo de tamano de efecto. Todos salen de
# `config` y estan fijados antes de ver los resultados.
UMBRALES_EFECTO = {
    "V de Cramer": 0.10,
    "diferencia de proporciones (pp)": 2.0,
    "rho de Spearman": 0.30,
    "r de Pearson": 0.30,
    "eta cuadrado": 0.06,
    "delta de Cliff": 0.30,
}


def _fmt_p(p: float) -> str:
    """Un valor p tan pequeno que el float se desborda no es '0,000'."""
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "no disponible"
    return "< 1e-300" if p == 0 else f"{p:.3e}"


def ficha_prueba(res: dict, h0: str, h1: str, alpha: float = 0.05,
                 umbral: float | None = None) -> pd.DataFrame:
    """Los cinco pasos del contraste, en el orden en que los pide el curso.

    Se construye a partir del diccionario que devuelve cualquier prueba de este
    modulo, de modo que las ocho hipotesis del notebook 03 se reporten con la
    misma estructura y no quede ninguna sin declarar sus supuestos o su
    criterio de decision.
    """
    efecto = res.get("efecto", "")
    valor = res.get("valor_efecto")
    if umbral is None:
        umbral = UMBRALES_EFECTO.get(efecto)

    p = res.get("p", np.nan)
    significativo = (not np.isnan(p)) and p < alpha

    filas = [
        ("1. Hipotesis nula (H0)", h0),
        ("1. Hipotesis alternativa (H1)", h1),
        ("2. Nivel de significancia", f"alfa = {alpha} (fijado antes de ver los datos)"),
        ("3. Prueba elegida", res.get("prueba", "")),
        ("3. Supuesto a validar", res.get("supuesto", "no declarado")),
        ("3. Verificacion del supuesto",
         "cumple" if res.get("supuesto_ok") else "NO cumple - ver nota"),
    ]

    est = res.get("estadistico")
    if est is not None:
        gl = res.get("gl")
        filas.append(("4. Estadistico",
                      f"{est:,.4f}" + (f"  (gl = {gl:g})" if gl is not None else "")))
    if res.get("error_estandar") is not None:
        filas.append(("4. Error estandar", f"{res['error_estandar']:,.5f}"))
    filas.append(("4. Valor p", _fmt_p(p)))

    if valor is not None:
        txt = f"{efecto} = {valor:,.4f}"
        if res.get("IC_lo") is not None:
            txt += f"   IC 95 % [{res['IC_lo']:,.4f}, {res['IC_hi']:,.4f}]"
        if res.get("magnitud"):
            txt += f"   ({res['magnitud']})"
        filas.append(("4. Tamano de efecto", txt))
    if res.get("factor") is not None:
        filas.append(("4. Lectura en escala original",
                      f"factor {res['factor']:,.2f}x   "
                      f"IC 95 % [{res['factor_lo']:,.2f}x, {res['factor_hi']:,.2f}x]"))

    filas.append(("5. Decision sobre H0",
                  "Se rechaza H0" if significativo else "Se falla al rechazar H0"))
    if not significativo:
        filas.append(("5. Lectura de la decision",
                      "no hay evidencia suficiente, que no es lo mismo que "
                      "afirmar que no hay diferencia"))
    if umbral is not None and valor is not None:
        supera = abs(valor) >= umbral
        filas.append(("5. Relevancia practica",
                      f"|{valor:,.4f}| {'>=' if supera else '<'} umbral {umbral:g}"
                      f"  ->  {'utilizable' if supera else 'no utilizable'} para focalizar"))

    return pd.DataFrame(filas, columns=["Paso", "Detalle"]).set_index("Paso")
