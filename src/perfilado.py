# -*- coding: utf-8 -*-
"""
perfilado.py
============
Diagnostico de calidad, completitud y relevancia del dataset.

Todas las funciones son puras: reciben el DataFrame crudo y devuelven
diccionarios serializables. Ninguna escribe en disco ni muta el DataFrame,
de modo que el notebook puede recomponer el perfil en cualquier orden.

Secciones, en el orden en que las consume el notebook 01:
    perfilar_columnas    estructura y completitud real vs aparente
    analizar_unicidad    duplicados de clave y de fila
    analizar_validez     dominios, formatos, binarias, capitalizacion
    evaluar_reglas       21 reglas de negocio
    analizar_outliers    exactitud y concentracion monetaria
    parsear_duracion     duracion textual -> dias
    analizar_temporal    cobertura, estacionalidad, censura
    evaluar_relevancia   veredicto por variable y fuga de informacion
    analizar_texto       objeto_del_contrato
    calcular_indice      indice de calidad agregado
    preparar_graficos    series precalculadas para las figuras
"""
from __future__ import annotations

import re
from collections import Counter

import numpy as np
import pandas as pd

from .config import (
    ANIO_MAX_PLAUSIBLE,
    ANIO_MIN_PLAUSIBLE,
    COLS_ALTA_CARD,
    COLS_BINARIAS,
    COLS_FECHA,
    COLS_NUMERICAS,
    HOY,
    PIB_COL,
    RENOMBRES,
    SENTINELAS,
    TOPE_CONTRATO_PLAUSIBLE,
)
from .diccionario import DICCIONARIO
from .utiles import entropia_normalizada, f, log, norm_txt


def perfilar_columnas(df: pd.DataFrame) -> list[dict]:
    N = len(df)
    filas = []
    for i, col in enumerate(df.columns, start=1):
        s = df[col]
        dic = DICCIONARIO.get(col, {})
        es_fecha = col in COLS_FECHA
        es_num = col in COLS_NUMERICAS

        n_null = int(s.isna().sum())
        n_vacio = n_sent = n_fecha_mala = 0
        muestras_sent: dict[str, int] = {}

        if es_fecha:
            anios = s.dt.year
            mala = (anios < ANIO_MIN_PLAUSIBLE) | (anios > ANIO_MAX_PLAUSIBLE)
            n_fecha_mala = int(mala.fillna(False).sum())
        elif not es_num:
            txt = s.astype("string")
            n_vacio = int(txt.str.strip().eq("").fillna(False).sum())
            normal = txt.map(norm_txt)
            marca = normal.isin(SENTINELAS)
            n_sent = int(marca.sum())
            if n_sent:
                muestras_sent = (s[marca].astype(str).value_counts()
                                 .head(6).to_dict())

        faltante_efectivo = n_null + n_vacio + n_sent + n_fecha_mala
        comp_aparente = 100.0 * (N - n_null) / N
        comp_efectiva = 100.0 * (N - faltante_efectivo) / N

        # cardinalidad y concentración sobre valores presentes y no centinela
        if es_fecha:
            validos = s[~((s.dt.year < ANIO_MIN_PLAUSIBLE) |
                          (s.dt.year > ANIO_MAX_PLAUSIBLE)).fillna(False)].dropna()
        elif es_num:
            validos = s.dropna()
        else:
            txt = s.astype("string")
            validos = s[~(txt.map(norm_txt).isin(SENTINELAS) |
                          txt.str.strip().eq("").fillna(False) | s.isna())]

        card = int(validos.nunique())
        if len(validos):
            vc = validos.value_counts()
            moda = vc.index[0]
            p_moda = 100.0 * vc.iloc[0] / len(validos)
            entrop = entropia_normalizada(vc.values.astype(float))
            top5 = [{"valor": str(k)[:90], "n": int(v),
                     "pct": round(100.0 * v / len(validos), 3)}
                    for k, v in vc.head(5).items()]
        else:
            moda, p_moda, entrop, top5 = None, 0.0, 0.0, []

        fila = {
            "id": f"V{i:02d}",
            "columna": col,
            "columna_normalizada": RENOMBRES.get(col, col),
            "bloque": dic.get("bloque", "-"),
            "definicion": dic.get("definicion", "-"),
            "dominio_esperado": dic.get("dominio", "-"),
            "rol": dic.get("rol", "-"),
            "dtype": str(s.dtype),
            "cardinalidad": card,
            "n_null": n_null,
            "n_vacio": n_vacio,
            "n_sentinela": n_sent,
            "n_fecha_implausible": n_fecha_mala,
            "faltante_efectivo": faltante_efectivo,
            "completitud_aparente": round(comp_aparente, 4),
            "completitud_efectiva": round(comp_efectiva, 4),
            "brecha_completitud": round(comp_aparente - comp_efectiva, 4),
            "moda": str(moda)[:90] if moda is not None else None,
            "pct_moda": round(p_moda, 3),
            "entropia_norm": round(entrop, 4),
            "top5": top5,
            "muestras_sentinela": {str(k)[:60]: int(v) for k, v in muestras_sent.items()},
        }

        if es_num:
            v = s.dropna().astype(float)
            qs = v.quantile([.01, .05, .25, .5, .75, .95, .99, .999])
            fila["stats"] = {
                "min": f(v.min()), "max": f(v.max()), "media": f(v.mean()),
                "std": f(v.std()), "p01": f(qs[.01]), "p05": f(qs[.05]),
                "p25": f(qs[.25]), "p50": f(qs[.5]), "p75": f(qs[.75]),
                "p95": f(qs[.95]), "p99": f(qs[.99]), "p999": f(qs[.999]),
                "suma": f(v.sum()),
                "n_cero": int((v == 0).sum()),
                "n_negativo": int((v < 0).sum()),
            }
        if es_fecha:
            v = s.dropna()
            fila["stats"] = {
                "min": str(v.min()), "max": str(v.max()),
                "n_implausible": n_fecha_mala,
            }
        filas.append(fila)
    return filas


# ==========================================================================
# 5. SECCION C - UNICIDAD Y DUPLICADOS
# ==========================================================================
def analizar_unicidad(df: pd.DataFrame) -> dict:
    N = len(df)
    pk_dup = int(df["id_contrato"].duplicated().sum())
    filas_dup = int(df.duplicated().sum())
    clave_negocio = ["nombre_entidad", "proveedor_adjudicado", "objeto_del_contrato",
                     "fecha_de_firma", "valor_del_contrato"]
    neg_dup = int(df.duplicated(subset=clave_negocio).sum())

    nit_a_nombre = df.groupby("documento_proveedor")["proveedor_adjudicado"].nunique()
    nombre_a_nit = df.groupby("proveedor_adjudicado")["documento_proveedor"].nunique()
    ejemplos = []
    for nit in nit_a_nombre[nit_a_nombre > 1].sort_values(ascending=False).head(5).index:
        nombres = sorted(df.loc[df["documento_proveedor"] == nit,
                                "proveedor_adjudicado"].unique())[:3]
        ejemplos.append({"documento": str(nit), "razones_sociales": [str(x)[:70] for x in nombres]})

    return {
        "pk_duplicados": pk_dup,
        "pk_unica": pk_dup == 0,
        "filas_identicas_duplicadas": filas_dup,
        "clave_negocio": clave_negocio,
        "duplicados_clave_negocio": neg_dup,
        "pct_duplicados_clave_negocio": round(100.0 * neg_dup / N, 4),
        "nit_con_varias_razones": int((nit_a_nombre > 1).sum()),
        "razon_con_varios_nit": int((nombre_a_nit > 1).sum()),
        "ejemplos_nit_multiples": ejemplos,
        "n_proveedores_por_nombre": int(df["proveedor_adjudicado"].nunique()),
        "n_proveedores_por_nit": int(df["documento_proveedor"].nunique()),
    }


# ==========================================================================
# 6. SECCION D - VALIDEZ Y DOMINIOS
# ==========================================================================
def analizar_validez(df: pd.DataFrame) -> dict:
    N = len(df)
    out = {}

    # --- 6.1 dominios de las categóricas de baja/media cardinalidad
    cats = [c for c in df.columns
            if c not in COLS_NUMERICAS + COLS_FECHA + COLS_ALTA_CARD
            and df[c].nunique() <= 40]
    dominios = {}
    for c in cats:
        vc = df[c].value_counts(dropna=False)
        dominios[c] = [{"valor": str(k), "n": int(v), "pct": round(100.0 * v / N, 3)}
                       for k, v in vc.items()]
    out["dominios"] = dominios

    # --- 6.2 inconsistencia de capitalización / tildes: valores que colapsan
    colapsos = {}
    for c in cats + ["ciudad", "nombre_entidad", "proveedor_adjudicado"]:
        s = df[c].dropna().astype(str)
        grupos = {}
        for val, n in s.value_counts().items():
            grupos.setdefault(norm_txt(val), []).append((val, int(n)))
        problemas = [{"forma_canonica": k,
                      "variantes": [{"valor": v, "n": n} for v, n in sorted(vs, key=lambda t: -t[1])]}
                     for k, vs in grupos.items() if len(vs) > 1]
        if problemas:
            afectados = sum(sum(x["n"] for x in p["variantes"][1:]) for p in problemas)
            colapsos[c] = {
                "n_grupos_afectados": len(problemas),
                "n_registros_en_variante_no_dominante": afectados,
                "pct": round(100.0 * afectados / N, 3),
                "ejemplos": sorted(problemas,
                                   key=lambda p: -sum(x["n"] for x in p["variantes"]))[:6],
            }
    out["colapsos_normalizacion"] = colapsos

    # --- 6.2b convencion de capitalización inconsistente.
    # Distinto de 6.2: aqui NO hay dos grafías del mismo valor (un group_by no se
    # parte), sino valores que rompen la convencion dominante de la columna.
    # Importa al cruzar con catálogos oficiales, no al contar.
    convencion = {}
    for c in cats:
        vc = df[c].value_counts()
        vals = [str(v) for v in vc.index]
        minus = [v for v in vals if v[:1].islower()]
        if minus and len(minus) < len(vals):
            n_reg = int(vc[minus].sum())
            convencion[c] = {
                "valores_totales": len(vals),
                "valores_en_minuscula": len(minus),
                "registros_afectados": n_reg,
                "pct": round(100.0 * n_reg / N, 3),
                "ejemplos": sorted(minus, key=lambda v: -int(vc[v]))[:6],
            }
    out["convencion_capitalizacion"] = convencion

    # --- 6.3 binarias fuera de {Si, No}
    binarias = {}
    for c in COLS_BINARIAS:
        vc = df[c].value_counts(dropna=False)
        fuera = {str(k): int(v) for k, v in vc.items() if str(k) not in ("Si", "No")}
        binarias[c] = {"valores": {str(k): int(v) for k, v in vc.items()},
                       "fuera_de_dominio": fuera,
                       "n_fuera": int(sum(fuera.values()))}
    out["binarias"] = binarias

    # --- 6.4 UNSPSC
    cc = df["codigo_de_categoria_principal"].astype(str)
    ok = cc.str.fullmatch(r"V1\.\d{8}")
    seg = cc.where(ok).str.slice(3, 5)
    out["unspsc"] = {
        "validos": int(ok.sum()),
        "unspecified": int((cc == "UNSPECIFIED").sum()),
        "otros_formatos": int((~ok & (cc != "UNSPECIFIED")).sum()),
        "pct_validos": round(100.0 * ok.sum() / N, 3),
        "n_codigos_distintos": int(cc[ok].nunique()),
        "n_segmentos": int(seg.dropna().nunique()),
        "top_segmentos": [{"segmento": str(k), "n": int(v)}
                          for k, v in seg.value_counts().head(10).items()],
    }

    # --- 6.5 documento del proveedor
    dp = df["documento_proveedor"].astype("string")
    solo_dig = dp.str.fullmatch(r"\d+", na=False)
    longs = dp.str.len()
    out["documento_proveedor"] = {
        "no_numericos": int((~solo_dig & dp.notna()).sum()),
        "nulos": int(dp.isna().sum()),
        "con_guion_dv": int(dp.str.contains(r"^\d+-\d$", na=False, regex=True).sum()),
        "longitud_min": int(longs.min()) if longs.notna().any() else None,
        "longitud_max": int(longs.max()) if longs.notna().any() else None,
        "distribucion_longitud": {str(int(k)): int(v) for k, v in
                                  longs.value_counts().sort_index().items()},
        "fuera_rango_6_11": int(((longs < 6) | (longs > 11)).fillna(False).sum()),
        "ejemplos_no_numericos": {str(k)[:40]: int(v) for k, v in
                                  dp[~solo_dig].value_counts().head(8).items()},
    }

    # --- 6.6 urlproceso
    u = df["urlproceso"].astype(str)
    out["urlproceso"] = {
        "parseables": int(u.str.startswith("{'url': '").sum()),
        "con_noticeUID": int(u.str.contains("noticeUID", na=False).sum()),
        "genericas_login": int(u.str.contains("Page=login", na=False).sum()),
        "urls_distintas": int(u.nunique()),
        "urls_repetidas": int(N - u.nunique()),
        "max_repeticiones": int(u.value_counts().iloc[0]),
    }

    # --- 6.7 códigos crudos de sistema en condiciones_de_entrega
    ce = df["condiciones_de_entrega"].astype(str)
    cod_crudo = ce.str.match(r"^NXTWY\.")
    out["codigos_crudos"] = {
        "columna": "condiciones_de_entrega",
        "n": int(cod_crudo.sum()),
        "pct": round(100.0 * cod_crudo.sum() / N, 3),
        "variantes": int(ce[cod_crudo].nunique()),
    }

    # --- 6.8 jerarquía geográfica
    g = df.groupby("ciudad")["departamento"].nunique()
    ambiguas = g[g > 1]
    sin_sent = df[(df["ciudad"] != "No Definido") & (df["departamento"] != "No Definido")]
    g2 = sin_sent.groupby("ciudad")["departamento"].nunique()
    out["geografia"] = {
        "ciudades_distintas": int(g.size),
        "ciudades_en_varios_departamentos": int((g > 1).sum()),
        "ciudades_ambiguas_sin_centinela": int((g2 > 1).sum()),
        "ejemplos": {str(k): int(v) for k, v in ambiguas.sort_values(ascending=False).head(8).items()},
    }
    return out


# ==========================================================================
# 7. SECCION E - REGLAS DE NEGOCIO
# ==========================================================================
def evaluar_reglas(df: pd.DataFrame, dur: pd.DataFrame) -> list[dict]:
    N = len(df)
    v = df["valor_del_contrato"]
    pg = df["valor_pagado"]
    fa = df["valor_facturado"]
    pe = df["valor_pendiente_de_pago"]
    ff = df["fecha_de_firma"]
    fi = df["fecha_de_inicio_del_contrato"]
    fn = df["fecha_de_fin_del_contrato"]
    hoy = pd.Timestamp(HOY)
    estado_norm = df["estado_contrato"].map(norm_txt)

    dur_dias = dur["dias_declarados"]
    dur_efectiva = (fn - fi).dt.days

    # Una fecha nula NO es una fecha implausible: el faltante ya se contabiliza en
    # la dimensión de completitud. Solo se marca lo que existe y está fuera de rango.
    def anio_malo(s):
        a = s.dt.year
        return s.notna() & ((a < ANIO_MIN_PLAUSIBLE) | (a > ANIO_MAX_PLAUSIBLE))

    fechas_malas = anio_malo(ff) | anio_malo(fi) | anio_malo(fn)

    defs = [
        ("R01", "valor_del_contrato >= 0", "Critica", v < 0),
        ("R02", "valor_pagado, valor_facturado y valor_pendiente_de_pago >= 0", "Critica",
         (pg < 0) | (fa < 0) | (pe < 0)),
        ("R03", "valor_pagado <= valor_del_contrato", "Alta", pg > v),
        ("R04", "valor_facturado <= valor_del_contrato", "Alta", fa > v),
        ("R05", "valor_pagado <= valor_facturado", "Media", pg > fa),
        ("R06", "valor_del_contrato ~= valor_pagado + valor_pendiente_de_pago (tol. 1%)", "Alta",
         (v - (pg + pe)).abs() > 0.01 * np.maximum(v.abs(), 1)),
        ("R07", "fecha_de_firma <= fecha_de_inicio_del_contrato", "Alta", ff > fi),
        ("R08", "fecha_de_inicio_del_contrato <= fecha_de_fin_del_contrato", "Critica", fi > fn),
        ("R09", f"todas las fechas dentro de [{ANIO_MIN_PLAUSIBLE}, {ANIO_MAX_PLAUSIBLE}]",
         "Critica", fechas_malas),
        ("R10", "duración declarada ~= fecha_fin - fecha_inicio (tol. 10% o 7 días)", "Media",
         (dur_dias.notna() & dur_efectiva.notna() &
          ((dur_dias - dur_efectiva).abs() > np.maximum(0.10 * dur_dias, 7)))),
        ("R11", "dias_adicionados dentro de un rango plausible (<= 1.095 días)", "Media",
         df["dias_adicionados"] > 1095),
        ("R12", "estado 'terminado' o 'cerrado' implica fecha_de_fin <= hoy", "Media",
         estado_norm.isin(["terminado", "cerrado"]) & (fn > hoy)),
        ("R13", "estado 'cerrado' implica valor_pendiente_de_pago == 0", "Media",
         (estado_norm == "cerrado") & (pe != 0)),
        ("R14", "dias_adicionados > 0 implica el_contrato_puede_ser_prorrogado = 'Si'", "Baja",
         (df["dias_adicionados"] > 0) & (df["el_contrato_puede_ser_prorrogado"] != "Si")),
        ("R15", "id_contrato es único", "Critica", df["id_contrato"].duplicated()),
        # R16 excluye los registros centinela: un 'No Definido' que aparece en 31
        # departamentos no es una inconsistencia real, es un faltante ya
        # contabilizado en la dimensión de completitud.
        ("R16", "documento_proveedor y proveedor_adjudicado son consistentes 1:1 "
                "(excluye centinelas)", "Media",
         (df["documento_proveedor"].map(
             df.groupby("documento_proveedor")["proveedor_adjudicado"].nunique()) > 1)
         & ~df["documento_proveedor"].map(norm_txt).isin(SENTINELAS)),
        # R17 (ciudad pertenece a un unico departamento) se RETIRO: marcaba 35
        # ciudades y 7.342 filas que resultaron ser homonimos legitimos —Armenia
        # esta en Quindio y en Antioquia, La Union en cuatro departamentos—, asi
        # que penalizaba consistencia sin que hubiera error de dato. El hecho de
        # fondo que si es cierto (ciudad no es llave: sin contar centinelas, 675
        # nombres cubren 716 pares departamento-ciudad) queda registrado como
        # dependencia funcional en `evaluar_relevancia`, que lo describe sin
        # castigarlo. Los ids R18-R22 no
        # se renumeran para no romper la trazabilidad con los informes ya emitidos.
        ("R18", "codigo_de_categoria_principal cumple el patrón V1.<8 dígitos>", "Media",
         ~df["codigo_de_categoria_principal"].astype(str).str.fullmatch(r"V1\.\d{8}")),
        ("R19", "urlproceso apunta a un proceso real (contiene noticeUID)", "Baja",
         ~df["urlproceso"].astype(str).str.contains("noticeUID", na=False)),
        ("R20", "valor_del_contrato > 0", "Alta", v == 0),
        ("R21", "valor_del_contrato <= 1 billon COP (plausibilidad macro)", "Critica",
         v > TOPE_CONTRATO_PLAUSIBLE),
        ("R22", "duración del contrato es parseable a un número de días", "Alta",
         dur_dias.isna()),
    ]

    reglas = []
    masks: dict[str, pd.Series] = {}
    for rid, desc, sev, mask in defs:
        mask = mask.fillna(False) if hasattr(mask, "fillna") else mask
        mask = mask.astype(bool)
        masks[rid] = mask
        n = int(mask.sum())
        ejemplos = []
        if n:
            sub = df.loc[mask, ["id_contrato", "nombre_entidad", "valor_del_contrato",
                                "fecha_de_firma", "estado_contrato"]].head(3)
            ejemplos = [{"id_contrato": str(r.id_contrato),
                         "entidad": str(r.nombre_entidad)[:55],
                         "valor": f(r.valor_del_contrato),
                         "firma": str(r.fecha_de_firma)[:10],
                         "estado": str(r.estado_contrato)}
                        for r in sub.itertuples()]
        reglas.append({
            "id": rid, "regla": desc, "severidad": sev,
            "violaciones": n, "pct": round(100.0 * n / N, 4),
            "cumple": n == 0, "ejemplos": ejemplos,
        })
    return reglas, pd.DataFrame(masks)


# ==========================================================================
# 8. SECCION F - OUTLIERS Y EXACTITUD
# ==========================================================================
def analizar_outliers(df: pd.DataFrame) -> dict:
    N = len(df)
    res = {}
    for c in COLS_NUMERICAS:
        v = df[c].dropna().astype(float)
        q1, q3 = v.quantile(.25), v.quantile(.75)
        iqr = q3 - q1
        lo15, hi15 = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        lo30, hi30 = q1 - 3.0 * iqr, q3 + 3.0 * iqr
        med = v.median()
        mad = (v - med).abs().median()
        z = (0.6745 * (v - med) / mad) if mad > 0 else pd.Series(0.0, index=v.index)
        total = v.sum()
        top1 = v.nlargest(max(N // 100, 1)).sum()
        res[c] = {
            "iqr": f(iqr), "lim_inf_1_5": f(lo15), "lim_sup_1_5": f(hi15),
            "n_outliers_1_5": int(((v < lo15) | (v > hi15)).sum()),
            "n_outliers_3_0": int(((v < lo30) | (v > hi30)).sum()),
            "pct_outliers_1_5": round(100.0 * ((v < lo15) | (v > hi15)).sum() / N, 3),
            "mad": f(mad),
            "n_z_robusto_mayor_10": int((z.abs() > 10).sum()),
            "n_z_robusto_mayor_50": int((z.abs() > 50).sum()),
            "asimetria": f(v.skew()),
            "curtosis": f(v.kurtosis()),
            "suma": f(total),
            "pct_valor_en_top1pct": round(100.0 * top1 / total, 3) if total else None,
            "max_sobre_p99": f(v.max() / v.quantile(.99)) if v.quantile(.99) else None,
        }
    # el contrato dominante
    vmax = df["valor_del_contrato"].max()
    idx = df["valor_del_contrato"].idxmax()
    total = df["valor_del_contrato"].sum()
    res["_dominante"] = {
        "id_contrato": str(df.at[idx, "id_contrato"]),
        "entidad": str(df.at[idx, "nombre_entidad"]),
        "valor": f(vmax),
        "pct_del_total": round(100.0 * vmax / total, 3),
        "veces_el_pib": round(vmax / PIB_COL, 2),
        "fecha_firma": str(df.at[idx, "fecha_de_firma"])[:10],
        "estado": str(df.at[idx, "estado_contrato"]),
    }
    res["_suma_total"] = f(total)
    res["_implausibles"] = int((df["valor_del_contrato"] > TOPE_CONTRATO_PLAUSIBLE).sum())
    top10 = df.nlargest(10, "valor_del_contrato")[
        ["id_contrato", "nombre_entidad", "valor_del_contrato", "valor_pagado", "fecha_de_firma"]]
    res["_top10_valor"] = [{"id_contrato": str(r.id_contrato),
                            "entidad": str(r.nombre_entidad)[:60],
                            "valor": f(r.valor_del_contrato),
                            "pagado": f(r.valor_pagado),
                            "firma": str(r.fecha_de_firma)[:10]} for r in top10.itertuples()]
    return res


# ==========================================================================
# 9. SECCION G - TEMPORALIDAD Y DURACION
# ==========================================================================
def parsear_duracion(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte 'duraci_n_del_contrato' (texto) a días. Devuelve DataFrame auxiliar."""
    s = df["duraci_n_del_contrato"].astype(str)
    ext = s.str.extract(
        r"^\s*(?P<num>-?\d+)?\s*(?P<uni>Dia\(s\)|Mes\(es\)|A\w*o\(s\)|Semana\(s\)|Hora\(s\)|Minuto\(s\))?\s*$")
    factor = {"Dia(s)": 1.0, "Mes(es)": 30.0, "Semana(s)": 7.0,
              "Hora(s)": 1 / 24, "Minuto(s)": 1 / 1440}
    fac = ext["uni"].map(lambda u: 365.0 if isinstance(u, str) and u.endswith("o(s)")
                         and "Semana" not in u and "Dia" not in u and "Mes" not in u
                         and "Hora" not in u and "Minuto" not in u
                         else factor.get(u, np.nan))
    num = pd.to_numeric(ext["num"], errors="coerce")
    return pd.DataFrame({
        "num": num, "unidad": ext["uni"], "factor": fac,
        "dias_declarados": num * fac,
    }, index=df.index)


def analizar_temporal(df: pd.DataFrame, dur: pd.DataFrame) -> dict:
    N = len(df)
    ff = df["fecha_de_firma"]
    fi = df["fecha_de_inicio_del_contrato"]
    fn = df["fecha_de_fin_del_contrato"]

    por_anio = ff.dt.year.value_counts().sort_index()
    mensual = ff.dt.to_period("M").value_counts().sort_index()
    por_mes = ff.dt.month.value_counts().sort_index()

    lag = (fi - ff).dt.days
    dur_efectiva = (fn - fi).dt.days
    unidades = dur["unidad"].value_counts(dropna=False)

    return {
        "rango_firma": {"min": str(ff.min())[:10], "max": str(ff.max())[:10]},
        "rango_inicio": {"min": str(fi.min())[:10], "max": str(fi.max())[:10],
                         "nulos": int(fi.isna().sum())},
        "rango_fin": {"min": str(fn.min())[:10], "max": str(fn.max())[:10]},
        "firmas_por_anio": {str(k): int(v) for k, v in por_anio.items()},
        "firmas_por_mes_calendario": {str(k): int(v) for k, v in por_mes.items()},
        "serie_mensual": [{"periodo": str(k), "n": int(v)} for k, v in mensual.items()],
        "crecimiento_2019_2025": round(100.0 * (por_anio.iloc[-1] / por_anio.iloc[0] - 1), 1),
        "pct_firmas_diciembre": round(100.0 * por_mes.get(12, 0) / N, 2),
        "pct_firmas_ultimo_trimestre": round(
            100.0 * por_mes.reindex([10, 11, 12]).fillna(0).sum() / N, 2),
        "lag_firma_inicio": {
            "p50": f(lag.median()), "p95": f(lag.quantile(.95)),
            "negativos": int((lag < 0).sum()),
            "pct_negativos": round(100.0 * (lag < 0).sum() / N, 3),
            "max": f(lag.max()), "min": f(lag.min()),
        },
        "duracion_efectiva_dias": {
            "p05": f(dur_efectiva.quantile(.05)), "p50": f(dur_efectiva.median()),
            "p95": f(dur_efectiva.quantile(.95)),
            "negativa": int((dur_efectiva < 0).sum()),
            "cero": int((dur_efectiva == 0).sum()),
        },
        "duracion_texto": {
            "unidades": {("SIN_UNIDAD" if pd.isna(k) else str(k)): int(v)
                         for k, v in unidades.items()},
            "no_parseable": int(dur["dias_declarados"].isna().sum()),
            "pct_no_parseable": round(100.0 * dur["dias_declarados"].isna().sum() / N, 3),
            "unidad_sin_numero": int((dur["num"].isna() & dur["unidad"].notna()).sum()),
            "valor_cero": int((dur["num"] == 0).sum()),
            "cardinalidad_texto": int(df["duraci_n_del_contrato"].nunique()),
        },
        "cobertura_completa": bool(str(ff.max())[:10] >= f"{ff.dt.year.max()}-12-01"),
    }


# ==========================================================================
# 10. SECCION H - RELEVANCIA DE VARIABLES
# ==========================================================================
def evaluar_relevancia(df: pd.DataFrame, cols: list[dict]) -> dict:
    # correlaciones entre monetarias (Spearman: robusta a la escala rota)
    corr = df[COLS_NUMERICAS].corr(method="spearman").round(3)
    corr_dict = {a: {b: f(corr.loc[a, b]) for b in COLS_NUMERICAS} for a in COLS_NUMERICAS}

    # dependencias funcionales A -> B (que tan determinada queda B por A)
    def dependencia(a, b):
        g = df.groupby(a)[b].nunique()
        return round(100.0 * (g <= 1).sum() / len(g), 2)

    dependencias = [
        {"de": "nombre_entidad", "a": "sector", "pct_determinado": dependencia("nombre_entidad", "sector")},
        {"de": "nombre_entidad", "a": "departamento", "pct_determinado": dependencia("nombre_entidad", "departamento")},
        {"de": "nombre_entidad", "a": "rama", "pct_determinado": dependencia("nombre_entidad", "rama")},
        {"de": "nombre_entidad", "a": "orden", "pct_determinado": dependencia("nombre_entidad", "orden")},
        {"de": "nombre_entidad", "a": "entidad_centralizada", "pct_determinado": dependencia("nombre_entidad", "entidad_centralizada")},
        {"de": "ciudad", "a": "departamento", "pct_determinado": dependencia("ciudad", "departamento")},
        {"de": "documento_proveedor", "a": "proveedor_adjudicado", "pct_determinado": dependencia("documento_proveedor", "proveedor_adjudicado")},
        {"de": "documento_proveedor", "a": "es_pyme", "pct_determinado": dependencia("documento_proveedor", "es_pyme")},
    ]

    # variables con fuga de información si el objetivo es un resultado del contrato
    leakage = ["valor_pagado", "valor_facturado", "valor_pendiente_de_pago",
               "dias_adicionados", "estado_contrato", "liquidaci_n",
               "fecha_de_fin_del_contrato"]

    OVERRIDES = {
        "id_contrato": ("Nucleo", "Clave primaria íntegra: 100% única y sin nulos. No es predictor, es el ancla del dataset."),
        "urlproceso": ("Contextual", "Valor de trazabilidad, no analitico. Requiere extraer la URL del diccionario serializado."),
        "objeto_del_contrato": ("Util con limpieza", "Unica fuente de senal semántica del bien contratado; exige NLP y limpieza de ruido."),
        "condiciones_de_entrega": ("Descartar", "25% centinela y ~37% códigos crudos de sistema sin traducir: menos de 40% del campo es interpretable."),
        "duraci_n_del_contrato": ("Util con limpieza", "Informativa pero almacenada como texto; hay que normalizarla a días antes de usarla."),
        "nacionalidad_representante_legal": ("Descartar", "99,05% concentrado en 'CO': prácticamente constante, sin poder discriminante."),
        "tipo_de_contrato": ("Contextual", "Solo dos valores por el pre-filtrado del dataset; util para segmentar, no para explicar."),
        "valor_del_contrato": ("Nucleo", "Métrica central del análisis, pero inutilizable sin winsorizar o filtrar los outliers macro-imposibles."),
    }

    filas = []
    for c in cols:
        col = c["columna"]
        comp = c["completitud_efectiva"]
        poder = 100.0 - c["pct_moda"]                 # 1 - proporcion modal
        if c["rol"] == "Identificador":
            poder = 100.0
        redundante = any(d["pct_determinado"] > 95 and d["a"] == col for d in dependencias)
        pena_red = 20.0 if redundante else 0.0
        score = 0.45 * comp + 0.40 * min(poder, 100.0) + 0.15 * (100.0 - pena_red)
        score = round(max(0.0, min(100.0, score)), 1)

        if col in OVERRIDES:
            veredicto, motivo = OVERRIDES[col]
        elif comp < 60:
            veredicto, motivo = "Descartar", f"Completitud efectiva de solo {comp:.1f}%."
        elif c["pct_moda"] > 99.0:
            veredicto, motivo = "Descartar", f"El {c['pct_moda']:.2f}% de los registros comparte un único valor."
        elif comp < 85:
            veredicto, motivo = "Util con limpieza", f"Completitud efectiva {comp:.1f}%: exige imputar o marcar los faltantes."
        elif redundante:
            veredicto, motivo = "Contextual", "Redundante: queda determinada por otra variable del dataset."
        elif score >= 75:
            veredicto, motivo = "Nucleo", "Alta completitud efectiva y buen poder discriminante."
        else:
            veredicto, motivo = "Contextual", "Utilizable, con poder discriminante moderado."

        filas.append({
            "id": c["id"], "columna": col, "rol": c["rol"],
            "completitud_efectiva": comp,
            "poder_discriminante": round(min(poder, 100.0), 2),
            "entropia_norm": c["entropia_norm"],
            "cardinalidad": c["cardinalidad"],
            "redundante": redundante,
            "leakage": col in leakage,
            "score": score,
            "veredicto": veredicto,
            "motivo": motivo,
        })

    filas.sort(key=lambda r: -r["score"])
    resumen = Counter(r["veredicto"] for r in filas)
    return {
        "correlacion_spearman": corr_dict,
        "dependencias_funcionales": dependencias,
        "variables_con_leakage": leakage,
        "ranking": filas,
        "resumen_veredictos": dict(resumen),
    }


# ==========================================================================
# 11. SECCION I - TEXTO LIBRE
# ==========================================================================
def analizar_texto(df: pd.DataFrame) -> dict:
    N = len(df)
    ob = df["objeto_del_contrato"].astype(str)
    longs = ob.str.len()
    STOP = {"de", "la", "el", "los", "las", "para", "del", "y", "en", "con", "a",
            "por", "al", "un", "una", "se", "que", "su", "sus", "o", "e", "como",
            "no", "lo", "es", "sin", "sobre", "the", "of"}
    palabras = Counter()
    for t in ob.sample(min(40000, N), random_state=7):
        for w in re.findall(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ]{4,}", t.lower()):
            if w not in STOP:
                palabras[w] += 1

    return {
        "longitud": {"min": int(longs.min()), "p05": int(longs.quantile(.05)),
                     "p50": int(longs.median()), "p95": int(longs.quantile(.95)),
                     "max": int(longs.max())},
        "n_en_limite_500": int((longs == 500).sum()),
        "pct_en_limite_500": round(100.0 * (longs == 500).sum() / N, 3),
        "duplicados_exactos": int(ob.duplicated().sum()),
        "pct_duplicados": round(100.0 * ob.duplicated().sum() / N, 3),
        "con_salto_de_linea": int(ob.str.contains("\n", regex=False).sum()),
        "con_punto_y_coma": int(ob.str.contains(";", regex=False).sum()),
        "con_signo_peso": int(ob.str.contains(r"\$", regex=True).sum()),
        "muy_cortos_menos_15": int((longs < 15).sum()),
        "centinela_no_definido": int(ob.map(norm_txt).isin(SENTINELAS).sum()),
        "top_objetos_repetidos": [{"texto": str(k)[:110], "n": int(v)}
                                  for k, v in ob.value_counts().head(8).items()],
        "top_terminos": [{"termino": k, "n": int(v)} for k, v in palabras.most_common(25)],
    }


# ==========================================================================
# 12. SECCION J - INDICE DE CALIDAD DE DATOS
# ==========================================================================
def calcular_indice(df, cols, uniq, val, reglas, masks, out, temp, texto) -> dict:
    """
    Cada dimensión se puntua como el porcentaje de registros LIMPIOS en ese eje.

    Las reglas se solapan (un mismo contrato puede violar varias), así que la
    penalizacion se calcula sobre la UNION de registros afectados, no sumando
    porcentajes: sumar sobrepenaliza y puede pasar de 100.
    """
    N = len(df)

    def pct_union(ids, extra_masks=()):
        """% de registros que violan al menos una de las condiciones dadas."""
        presentes = [masks[i] for i in ids if i in masks.columns]
        presentes += list(extra_masks)
        if not presentes:
            return 0.0
        union = presentes[0].copy()
        for m in presentes[1:]:
            union |= m
        return 100.0 * float(union.sum()) / N

    completitud = float(np.mean([c["completitud_efectiva"] for c in cols]))

    dup = uniq["pk_duplicados"] + uniq["filas_identicas_duplicadas"] + \
        uniq["duplicados_clave_negocio"]
    unicidad = 100.0 - 100.0 * dup / N

    # Validez: formato y conformidad de dominio del propio registro.
    cod_crudo = df["condiciones_de_entrega"].astype(str).str.match(r"^NXTWY\.")
    validez = 100.0 - pct_union(["R18", "R19", "R21", "R22"], extra_masks=[cod_crudo])

    # Consistencia: coherencia entre campos del mismo registro y contra el resto.
    consistencia = 100.0 - pct_union(
        ["R03", "R04", "R05", "R06", "R07", "R08", "R10", "R12", "R13", "R16"])

    # Exactitud: plausibilidad del valor medido.
    outlier_extremo = df["valor_del_contrato"] > out["valor_del_contrato"]["lim_sup_1_5"]
    exactitud = 100.0 - pct_union(["R01", "R02", "R09", "R11", "R20"],
                                  extra_masks=[outlier_extremo])

    anio_max = max(int(a) for a in temp["firmas_por_anio"])
    actualidad = 100.0 if anio_max >= HOY.year - 1 else max(0.0, 100.0 - 20 * (HOY.year - anio_max))

    # interpretabilidad: penalizaciones estructurales fijas y explicitas
    penas_interp = [
        ("4 nombres de columna con mojibake (tildes convertidas en '_')", 8),
        ("duración del contrato almacenada como texto en vez de número", 10),
        ("urlproceso almacenado como diccionario Python serializado", 6),
        ("códigos internos NXTWY.DLVY.* sin traducir en condiciones_de_entrega", 12),
        ("magnitudes monetarias con tipos mixtos (float64 vs int64)", 4),
        ("faltantes codificados como texto en vez de nulos", 15),
    ]
    interpretabilidad = max(0.0, 100.0 - sum(p for _, p in penas_interp))

    dims = {
        "Completitud": round(completitud, 2),
        "Unicidad": round(max(0.0, unicidad), 2),
        "Validez": round(validez, 2),
        "Consistencia": round(consistencia, 2),
        "Exactitud": round(max(0.0, exactitud), 2),
        "Actualidad": round(actualidad, 2),
        "Interpretabilidad": round(interpretabilidad, 2),
    }
    pesos = {"Completitud": .25, "Unicidad": .10, "Validez": .15, "Consistencia": .20,
             "Exactitud": .15, "Actualidad": .05, "Interpretabilidad": .10}
    global_ = round(sum(dims[k] * pesos[k] for k in dims), 2)

    if global_ >= 85:
        nivel = "Bueno"
    elif global_ >= 70:
        nivel = "Aceptable con reservas"
    elif global_ >= 55:
        nivel = "Deficiente"
    else:
        nivel = "Critico"

    return {
        "dimensiones": dims, "pesos": pesos, "global": global_, "nivel": nivel,
        "penalizaciones_interpretabilidad": [{"motivo": m, "puntos": p} for m, p in penas_interp],
        "formula": ("Cada dimensión = 100 - porcentaje de registros afectados por al menos una "
                    "de sus condiciones (union, no suma, para no doble-contar registros que "
                    "violan varias reglas). El índice global es el promedio ponderado."),
        "reglas_por_dimension": {
            "Validez": ["R18", "R19", "R21", "R22", "códigos crudos NXTWY.*"],
            "Consistencia": ["R03", "R04", "R05", "R06", "R07", "R08", "R10", "R12", "R13",
                             "R16"],
            "Exactitud": ["R01", "R02", "R09", "R11", "R20", "outliers IQR 1.5x"],
            "Completitud": ["completitud efectiva promedio de las 36 columnas"],
            "Unicidad": ["R15", "filas idénticas", "duplicados por clave de negocio"],
            "Actualidad": ["distancia entre la última firma y hoy"],
            "Interpretabilidad": ["penalizaciones estructurales fijas"],
        },
    }


# ==========================================================================
# 13. GRAFICOS (datos precalculados para los SVG del HTML)
# ==========================================================================
def preparar_graficos(df, cols, reglas, temp, indice) -> dict:
    N = len(df)
    comp = sorted([{"col": c["columna"], "efectiva": c["completitud_efectiva"],
                    "aparente": c["completitud_aparente"]} for c in cols],
                  key=lambda d: d["efectiva"])
    v = df["valor_del_contrato"]
    pos = v[v > 0]
    lg = np.log10(pos)
    hist, edges = np.histogram(lg, bins=28)

    top_ent = df["nombre_entidad"].value_counts().head(12)
    top_prov = df["proveedor_adjudicado"].value_counts().head(12)
    estados = df["estado_contrato"].value_counts()
    modal = df["modalidad_de_contratacion"].value_counts()
    deptos = df["departamento"].value_counts().head(12)

    return {
        "completitud": comp,
        "brecha_top": sorted([c for c in comp if c["aparente"] - c["efectiva"] > 0.01],
                             key=lambda d: -(d["aparente"] - d["efectiva"]))[:15],
        "serie_mensual": temp["serie_mensual"],
        "firmas_por_mes": temp["firmas_por_mes_calendario"],
        "hist_valor_log": {"conteos": hist.tolist(),
                           "bordes": [round(float(e), 3) for e in edges]},
        "top_entidades": [{"k": str(k)[:48], "n": int(x)} for k, x in top_ent.items()],
        "top_proveedores": [{"k": str(k)[:48], "n": int(x)} for k, x in top_prov.items()],
        "estados": [{"k": str(k), "n": int(x)} for k, x in estados.items()],
        "modalidades": [{"k": str(k)[:48], "n": int(x)} for k, x in modal.items()],
        "departamentos": [{"k": str(k)[:30], "n": int(x)} for k, x in deptos.items()],
        "reglas": [{"id": r["id"], "pct": r["pct"], "n": r["violaciones"],
                    "sev": r["severidad"]} for r in reglas],
        "dimensiones": indice["dimensiones"],
    }



# ==========================================================================
# 15. ORQUESTADOR
# ==========================================================================
def perfil_completo(df: pd.DataFrame, meta: dict | None = None) -> dict:
    """Corre el perfilado entero y devuelve el diccionario de resultados.

    Replica el pipeline del script original `perfilado_secop.py`, sin escribir
    en disco. El orden importa: `parsear_duracion` alimenta tanto el analisis
    temporal como las reglas de negocio, y `calcular_indice` consume las
    mascaras de violacion que produce `evaluar_reglas`.
    """
    from .config import (
        ANIO_MAX_PLAUSIBLE,
        ANIO_MIN_PLAUSIBLE,
        RENOMBRES,
        SENTINELAS,
        TOPE_CONTRATO_PLAUSIBLE,
    )

    log("A/B  estructura y completitud real vs aparente ...")
    cols = perfilar_columnas(df)

    log("C    unicidad y duplicados ...")
    uniq = analizar_unicidad(df)

    log("D    validez y dominios ...")
    val = analizar_validez(df)

    log("G    temporalidad y parseo de duracion ...")
    dur = parsear_duracion(df)
    temp = analizar_temporal(df, dur)

    log("E    reglas de negocio ...")
    reglas, masks = evaluar_reglas(df, dur)

    log("F    outliers y exactitud ...")
    out = analizar_outliers(df)

    log("I    texto libre ...")
    texto = analizar_texto(df)

    log("H    relevancia de variables ...")
    rel = evaluar_relevancia(df, cols)

    log("J    indice de calidad ...")
    indice = calcular_indice(df, cols, uniq, val, reglas, masks, out, temp, texto)

    log("     preparando datos de graficos ...")
    graf = preparar_graficos(df, cols, reglas, temp, indice)

    return {
        "meta": meta or {},
        "columnas": cols,
        "unicidad": uniq,
        "validez": val,
        "reglas": reglas,
        "outliers": out,
        "temporal": temp,
        "texto": texto,
        "relevancia": rel,
        "indice": indice,
        "graficos": graf,
        "_masks": masks,
        "config": {
            "sentinelas": sorted(SENTINELAS),
            "anio_min_plausible": ANIO_MIN_PLAUSIBLE,
            "anio_max_plausible": ANIO_MAX_PLAUSIBLE,
            "tope_contrato_plausible": TOPE_CONTRATO_PLAUSIBLE,
            "renombres_sugeridos": RENOMBRES,
        },
    }


def resumen_perfil(perfil: dict) -> pd.DataFrame:
    """Tabla de una fila con los indicadores de cabecera del perfilado."""
    cols = perfil["columnas"]
    reglas = perfil["reglas"]
    return pd.DataFrame([{
        "filas": perfil["meta"].get("filas"),
        "columnas": perfil["meta"].get("columnas"),
        "indice_calidad": perfil["indice"]["global"],
        "nivel": perfil["indice"]["nivel"],
        "completitud_aparente_media": round(
            float(np.mean([c["completitud_aparente"] for c in cols])), 2),
        "completitud_efectiva_media": round(
            float(np.mean([c["completitud_efectiva"] for c in cols])), 2),
        "reglas_evaluadas": len(reglas),
        "reglas_incumplidas": sum(1 for r in reglas if not r["cumple"]),
    }])
