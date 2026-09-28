# -*- coding: utf-8 -*-
"""
limpieza.py
===========
Pipeline de tratamiento del dataset y construccion de las senales objetivo.

Implementa, en orden, las diez decisiones de tratamiento que sustenta el
perfilado (ver docs/01_hallazgos_datos.md). Dos principios gobiernan el modulo:

1. **Marcar antes que borrar.** Ninguna funcion elimina filas. Los registros
   problematicos quedan senalados con banderas (`calidad_sospechosa`,
   `documento_valido`) y las columnas originales se conservan intactas junto a
   las derivadas. Quien analiza decide que excluir, y lo hace explicito.

2. **Bitacora auditable.** Cada paso registra que problema atendio, que decidio
   y cuantas filas afecto. `limpiar()` devuelve esa bitacora como DataFrame:
   es la tabla "problema -> decision -> justificacion -> filas afectadas" que
   exige el punto 1 del taller.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    ANIO_MAX_PLAUSIBLE,
    ANIO_MIN_PLAUSIBLE,
    COLS_FECHA,
    FECHA_CORTE,
    RENOMBRES,
    SENTINELAS,
    TOPE_CONTRATO_PLAUSIBLE,
)
from .utiles import log, norm_txt

# Categoricas que se normalizan en grafia: las que el reporte senala con
# capitalizacion inconsistente o con espacios extremos.
CATEGORICAS_A_NORMALIZAR = [
    "sector", "estado_contrato", "modalidad_de_contratacion", "ciudad",
    "departamento", "orden", "rama", "tipo_de_contrato", "destino_gasto",
    "origen_de_los_recursos", "entidad_centralizada", "condiciones_de_entrega",
]

# Estados que implican que la ejecucion ya concluyo. Solo en ellos el desenlace
# (pago, liquidacion) es observable.
ESTADOS_CERRADOS = {"terminado", "cerrado", "liquidado"}


class Bitacora:
    """Acumula las decisiones de tratamiento para reportarlas al final."""

    def __init__(self) -> None:
        self._filas: list[dict] = []

    def anotar(self, paso: str, problema: str, decision: str,
               justificacion: str, filas: int, total: int) -> None:
        self._filas.append({
            "paso": paso,
            "problema": problema,
            "decision": decision,
            "justificacion": justificacion,
            "filas_afectadas": int(filas),
            "pct_filas": round(100.0 * filas / total, 4) if total else 0.0,
        })

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self._filas)


# ==========================================================================
# 1-4. Normalizacion estructural
# ==========================================================================
def renombrar_columnas(df: pd.DataFrame, bit: Bitacora) -> pd.DataFrame:
    """Paso 1. Repara el mojibake heredado de la API Socrata."""
    presentes = {k: v for k, v in RENOMBRES.items() if k in df.columns}
    df = df.rename(columns=presentes)
    bit.anotar(
        "1. Nombres de columna",
        "Cuatro columnas perdieron la tilde en la extraccion y quedaron con "
        "un guion bajo en su lugar (duraci_n_del_contrato, g_nero_..., "
        "liquidaci_n, obligaci_n_ambiental).",
        f"Renombrar las {len(presentes)} columnas afectadas a su forma sin tilde.",
        "Un nombre con guion bajo en mitad de la palabra es ilegible y propenso "
        "a errores de tipeo. No afecta ningun dato, solo la cabecera.",
        len(presentes), len(df.columns))
    return df


def sentinelas_a_nan(df: pd.DataFrame, bit: Bitacora) -> pd.DataFrame:
    """Paso 2. Convierte los centinelas de texto en NaN reales."""
    df = df.copy()
    total_celdas = 0
    cols_afectadas = []
    for col in df.columns:
        if df[col].dtype != object:
            continue
        marca = df[col].map(norm_txt).isin(SENTINELAS)
        n = int(marca.sum())
        if n:
            df.loc[marca, col] = np.nan
            total_celdas += n
            cols_afectadas.append(col)
    bit.anotar(
        "2. Centinelas de nulo",
        "34 de 36 columnas reportaban cero nulos, pero los faltantes venian "
        "codificados como texto: No Definido, No aplica, UNSPECIFIED, xxxx.",
        f"Sustituir por NaN el catalogo de {len(SENTINELAS)} centinelas en "
        f"{len(cols_afectadas)} columnas ({total_celdas:,} celdas).",
        "Sin esto isna() reporta una completitud aparente del 99,97 % frente a "
        "una efectiva del 97,04 %: todo conteo de faltantes o imputacion "
        "posterior partiria de una premisa falsa.",
        total_celdas, df.size)
    return df


def normalizar_categoricas(df: pd.DataFrame, bit: Bitacora) -> pd.DataFrame:
    """Paso 3. Unifica espacios y capitalizacion en las categoricas clave.

    Importante: el perfilado verifico que al normalizar mayusculas y tildes en
    todo el dataset solo colapsan 46 registros. Es decir, 'terminado' y
    'Terminado' son valores distintos del catalogo, no dos grafias del mismo
    valor. Esta normalizacion corrige la presentacion y evita fallos al unir
    con catalogos externos; no reagrupa conteos de forma significativa.
    """
    df = df.copy()
    cambios = 0
    for col in CATEGORICAS_A_NORMALIZAR:
        if col not in df.columns:
            continue
        s = df[col]
        nuevo = s.where(s.isna(), s.astype(str).str.strip().str.capitalize())
        cambios += int((nuevo.fillna("") != s.fillna("")).sum())
        df[col] = nuevo
    bit.anotar(
        "3. Grafia de categoricas",
        "estado_contrato tenia 2 de 9 valores en minuscula (27,64 % de los "
        "registros) y sector 4 de 26 (20,18 %); habia ademas espacios extremos.",
        f"Quitar espacios y unificar capitalizacion en "
        f"{len(CATEGORICAS_A_NORMALIZAR)} columnas ({cambios:,} celdas reescritas).",
        "Homogeneiza etiquetas para tablas y graficos. No reagrupa categorias: "
        "el perfilado confirmo que solo 46 registros colapsan al normalizar.",
        cambios, df.size)
    return df


def anular_fechas_implausibles(df: pd.DataFrame, bit: Bitacora) -> pd.DataFrame:
    """Paso 4. Nulifica fechas con anio fuera de la ventana plausible."""
    df = df.copy()
    n_total = 0
    for col in COLS_FECHA:
        if col not in df.columns:
            continue
        anios = df[col].dt.year
        mala = df[col].notna() & (
            (anios < ANIO_MIN_PLAUSIBLE) | (anios > ANIO_MAX_PLAUSIBLE))
        n = int(mala.sum())
        if n:
            df.loc[mala, col] = pd.NaT
            n_total += n
    bit.anotar(
        "4. Fechas imposibles",
        "fecha_de_fin_del_contrato iba del anio 202 d.C. hasta 2065, sin declarar "
        "un solo nulo.",
        f"Convertir a NaT las fechas con anio fuera de [{ANIO_MIN_PLAUSIBLE}, "
        f"{ANIO_MAX_PLAUSIBLE}]: {n_total} celdas.",
        "Una fecha del anio 202 no es un dato con ruido, es un error de captura. "
        "Arrastrarla contamina cualquier duracion o serie temporal que la use.",
        n_total, len(df))
    return df


# ==========================================================================
# 5-9. Variables derivadas
# ==========================================================================
def derivar_duracion(df: pd.DataFrame, bit: Bitacora) -> pd.DataFrame:
    """Paso 5. Parsea la duracion textual a dias y la contrasta con las fechas."""
    df = df.copy()
    patron = (r"^\s*(?P<num>-?\d+)?\s*"
              r"(?P<uni>Dia\(s\)|Mes\(es\)|A\w*o\(s\)|Semana\(s\)|Hora\(s\)"
              r"|Minuto\(s\))?\s*$")
    ext = df["duracion_del_contrato"].astype(str).str.extract(patron)
    factor = {"Dia(s)": 1.0, "Mes(es)": 30.0, "Semana(s)": 7.0,
              "Hora(s)": 1 / 24, "Minuto(s)": 1 / 1440}

    def _factor(u):
        if not isinstance(u, str):
            return np.nan
        if u in factor:
            return factor[u]
        return 365.0 if u.endswith("o(s)") else np.nan   # Anio(s) con tilde perdida

    fac = ext["uni"].map(_factor)
    num = pd.to_numeric(ext["num"], errors="coerce")

    df["duracion_unidad"] = ext["uni"]
    df["duracion_dias"] = num * fac

    # Un subconjunto de registros trae una FECHA escrita dentro del campo de
    # duracion: "30092025 Mes(es)" es el 30/09/2025 y "31122021 Dia(s)" el
    # 31/12/2021. Al parsearlos salen plazos de hasta 2,5 millones de anios.
    patron_fecha = num.notna() & num.astype("Float64").apply(
        lambda x: bool(x) and 1_000_000 <= x <= 99_999_999)
    n_fecha_en_campo = int(patron_fecha.fillna(False).sum())

    # Techo de plausibilidad: 5 anios para un contrato de bienes.
    TOPE_DIAS = 1825
    implausible = df["duracion_dias"] > TOPE_DIAS
    n_implausible = int(implausible.sum())
    df["duracion_implausible"] = implausible.fillna(False)
    df.loc[implausible, "duracion_dias"] = np.nan

    df["duracion_dias_efectiva"] = (
        df["fecha_de_fin_del_contrato"] - df["fecha_de_inicio_del_contrato"]).dt.days
    df["duracion_discrepancia"] = df["duracion_dias_efectiva"] - df["duracion_dias"]

    no_parseable = int(df["duracion_dias"].isna().sum())
    bit.anotar(
        "5. Duracion textual",
        f"duracion_del_contrato es texto con 835 variantes que mezclan cantidad y "
        f"unidad ('30 Dia(s)', '1 Mes(es)'); 11.329 traen unidad sin cantidad. Peor: "
        f"{n_fecha_en_campo} registros traen una FECHA en el campo "
        f"('30092025 Mes(es)' = 30/09/2025), que al parsearse produce plazos de "
        f"hasta 2,5 millones de anios.",
        f"Derivar duracion_dias normalizando la unidad a dias, anular los "
        f"{n_implausible} plazos por encima de {TOPE_DIAS} dias (5 anios) y marcarlos "
        "en duracion_implausible. Se anaden duracion_dias_efectiva (fin menos "
        "inicio) y su discrepancia.",
        f"Sin el techo, la media de duracion es de 7.850 dias con desviacion de 2,3 "
        f"millones: un solo registro mal capturado destruye el estadistico. Quedan "
        f"{no_parseable:,} registros sin plazo utilizable, que se dejan en NaN en vez "
        "de imputar un valor inventado.",
        no_parseable, len(df))
    return df


def normalizar_proveedor(df: pd.DataFrame, bit: Bitacora) -> pd.DataFrame:
    """Paso 6. Documento a solo digitos y razon social canonica por documento.

    No se elimina el digito de verificacion: un NIT de 9 digitos mas DV es
    indistinguible de una cedula de 10 digitos sin aplicar el checksum, y
    recortar a ciegas fusionaria proveedores distintos. Se deja el documento
    normalizado como llave y se marca su validez por longitud.
    """
    df = df.copy()
    doc = (df["documento_proveedor"].astype(str)
           .str.replace(r"\D", "", regex=True).replace("", np.nan))
    df["documento_norm"] = doc
    df["documento_valido"] = doc.str.len().between(6, 11)

    canon = (df.dropna(subset=["documento_norm", "proveedor_adjudicado"])
               .groupby("documento_norm")["proveedor_adjudicado"]
               .agg(lambda s: s.value_counts().idxmax()))
    df["proveedor_canonico"] = df["documento_norm"].map(canon)
    df["n_contratos_proveedor"] = (
        df.groupby("documento_norm")["id_contrato"].transform("count"))

    invalidos = int((~df["documento_valido"].fillna(False)).sum())
    bit.anotar(
        "6. Identidad del proveedor",
        "documento_proveedor tenia longitudes de 1 a 54 caracteres, 2.076 valores "
        "no numericos y 200 documentos asociados a mas de una razon social.",
        "Derivar documento_norm (solo digitos), documento_valido (6 a 11 "
        "digitos), proveedor_canonico (razon social mas frecuente por documento) "
        "y n_contratos_proveedor.",
        f"Permite contar proveedores sin inflar el conteo por variantes de la "
        f"razon social. Quedan {invalidos:,} filas con documento fuera de rango, "
        "marcadas y no borradas. El digito de verificacion se conserva a "
        "proposito: recortarlo a ciegas fusionaria proveedores distintos.",
        invalidos, len(df))
    return df


def extraer_url(df: pd.DataFrame, bit: Bitacora) -> pd.DataFrame:
    """Paso 7. Saca la URL y el noticeUID del diccionario serializado."""
    df = df.copy()
    s = df["urlproceso"].astype(str)
    df["url_proceso"] = s.str.extract(r"'url':\s*'([^']*)'")[0]
    df["notice_uid"] = df["url_proceso"].str.extract(r"noticeUID=([^&]+)")[0]
    sin_uid = int(df["notice_uid"].isna().sum())
    bit.anotar(
        "7. URL del proceso",
        "urlproceso venia como un diccionario de Python serializado en texto, "
        "no como una URL utilizable.",
        "Extraer url_proceso y notice_uid a columnas propias.",
        f"notice_uid permite agrupar contratos del mismo proceso (lotes). Quedan "
        f"{sin_uid} registros sin identificador porque apuntan a URLs genericas "
        "de login.",
        sin_uid, len(df))
    return df


def descomponer_unspsc(df: pd.DataFrame, bit: Bitacora) -> pd.DataFrame:
    """Paso 8. Corta el clasificador UNSPSC en sus niveles jerarquicos."""
    df = df.copy()
    cod = (df["codigo_de_categoria_principal"].astype(str)
           .str.extract(r"V1\.(\d{8})")[0])
    df["unspsc_segmento"] = cod.str[:2]
    df["unspsc_familia"] = cod.str[:4]
    df["unspsc_clase"] = cod.str[:6]
    sin_cod = int(cod.isna().sum())
    bit.anotar(
        "8. Clasificador UNSPSC",
        "El codigo tiene 10.930 valores distintos: demasiado granular para "
        "agrupar o cruzar.",
        "Descomponer en segmento (2 digitos), familia (4) y clase (6).",
        f"El segmento reduce 10.930 codigos a 56 grupos manejables, que si "
        f"admiten comparacion estadistica. {sin_cod:,} registros no traen codigo "
        "valido y quedan en NaN.",
        sin_cod, len(df))
    return df


def derivar_temporales_y_monetarias(df: pd.DataFrame, bit: Bitacora) -> pd.DataFrame:
    """Paso 9. Derivadas de calendario y de magnitud monetaria."""
    df = df.copy()
    ff = df["fecha_de_firma"]
    df["anio_firma"] = ff.dt.year
    df["mes_firma"] = ff.dt.month
    df["trimestre_firma"] = ff.dt.quarter
    df["periodo_firma"] = ff.dt.to_period("M").astype(str)
    df["lag_firma_inicio"] = (df["fecha_de_inicio_del_contrato"] - ff).dt.days

    v = df["valor_del_contrato"]
    df["log_valor"] = np.log10(v.clip(lower=0) + 1)
    p999 = v.quantile(0.999)
    df["valor_contrato_w"] = v.clip(upper=p999)
    df["pct_ejecucion_financiera"] = np.where(v > 0, df["valor_pagado"] / v, np.nan)

    n_w = int((v > p999).sum())
    bit.anotar(
        "9. Concentracion monetaria",
        "Un solo contrato (CO1.PCCNTR.3102623) concentra el 99,47 % de la suma "
        "de valor_del_contrato: 8 veces el PIB de Colombia. Hay 4 contratos por "
        "encima del billon de pesos.",
        f"Conservar valor_del_contrato intacto y anadir valor_contrato_w "
        f"winsorizado al percentil 99,9 ({p999:,.0f} COP), mas log_valor y "
        "pct_ejecucion_financiera.",
        f"Toda media o suma cruda del valor original es basura estadistica. Se "
        f"winsoriza en una columna aparte ({n_w:,} filas topadas) para que el "
        "analisis use la version robusta sin perder el dato de origen.",
        n_w, len(df))
    return df


# ==========================================================================
# 10. Bandera de calidad
# ==========================================================================
def marcar_calidad_sospechosa(df: pd.DataFrame, bit: Bitacora) -> pd.DataFrame:
    """Marca los registros que violan alguna regla critica. No los elimina."""
    df = df.copy()
    v = df["valor_del_contrato"]
    cond = {
        "valor_no_positivo": v.isna() | (v <= 0),
        "valor_implausible": v > TOPE_CONTRATO_PLAUSIBLE,
        "monto_negativo": ((df["valor_pagado"] < 0)
                           | (df["valor_facturado"] < 0)
                           | (df["valor_pendiente_de_pago"] < 0)),
        "pagado_mayor_contrato": df["valor_pagado"] > v,
        "inicio_antes_de_firma": df["lag_firma_inicio"] < 0,
        "fin_antes_de_inicio": df["duracion_dias_efectiva"] < 0,
        "duracion_implausible": df["duracion_implausible"],
    }
    marco = pd.DataFrame(cond).fillna(False)
    df["calidad_sospechosa"] = marco.any(axis=1)
    df["n_problemas_calidad"] = marco.sum(axis=1)

    n = int(df["calidad_sospechosa"].sum())
    detalle = ", ".join(f"{k}={int(m.fillna(False).sum()):,}" for k, m in cond.items())
    bit.anotar(
        "10. Bandera de calidad",
        f"Registros que violan al menos una regla critica: {detalle}.",
        "Anadir las banderas calidad_sospechosa y n_problemas_calidad.",
        f"Marcar en vez de borrar deja la decision de exclusion al analisis y "
        f"permite medir si los {n:,} registros sospechosos "
        f"({100 * n / len(df):.2f} %) sesgan algun resultado.",
        n, len(df))
    return df


# ==========================================================================
# 11. Senales objetivo
# ==========================================================================
def construir_senales(df: pd.DataFrame, bit: Bitacora,
                      umbral_subejecucion: float = 0.90) -> pd.DataFrame:
    """Construye las senales de desviacion y el indicador compuesto.

    Tres hallazgos del perfilado gobiernan estas definiciones, y ninguno es
    evidente a primera vista:

    1. **La observabilidad no se decide por `estado_contrato`.** 51.238
       contratos siguen marcados 'En ejecucion' aunque su plazo ya vencio: el
       estado esta rancio. El criterio limpio es temporal, `fecha_de_fin <
       FECHA_CORTE`, que cubre el 99,52 % del dataset. Ese criterio **condiciona
       la senal financiera**: la subejecucion solo se evalua donde el desenlace
       ya ocurrio. La adicion de plazo no lo necesita, porque un dia anadido es
       un hecho consumado se haya cerrado el contrato o no.

    2. **`valor_pagado` es casi binario, no continuo.** El 54,77 % marca
       exactamente 0 y el 26,11 % exactamente 100 %: es una bandera de reporte,
       no una medida de avance. Solo el 4,93 % del universo muestra ejecucion
       parcial real (0 < pct < 90 %), y al exigir ademas que el plazo haya
       vencido la senal queda en 4,76 %. Tratar el cero como subejecucion
       convertiria un fallo de reporte en un hallazgo de supervision.

    3. **`sin_liquidar` es la norma, no la anomalia** (60,30 %). Se conserva
       como variable descriptiva, pero se excluye del compuesto: un indicador
       que se activa en 6 de cada 10 contratos no focaliza nada.

    De ahi que `desviacion` = adicion de plazo O subejecucion parcial, y que
    la version de tres senales quede disponible como `n_senales` para medir
    severidad sin contaminar el objetivo principal.
    """
    df = df.copy()
    corte = pd.Timestamp(FECHA_CORTE)

    # --- Observabilidad del desenlace: criterio temporal, no de estado -----
    df["contrato_cerrado"] = df["estado_contrato"].map(norm_txt).isin(ESTADOS_CERRADOS)
    fn = df["fecha_de_fin_del_contrato"]
    df["plazo_vencido"] = fn.notna() & (fn < corte)
    df["desenlace_observable"] = df["plazo_vencido"]

    # --- Senal 1: adicion de plazo -----------------------------------------
    df["tiene_adicion"] = df["dias_adicionados"] > 0

    # --- Senales financieras ------------------------------------------------
    # La subejecucion solo es interpretable una vez vencido el plazo: un
    # contrato en curso que lleva pagado el 40 % no esta subejecutado,
    # simplemente no ha terminado. Para los que siguen vigentes la senal queda
    # en NaN -desconocida-, no en False, porque el desenlace aun no ocurrio;
    # los compuestos de abajo ya tratan el NaN como ausente.
    pct = df["pct_ejecucion_financiera"]
    df["pago_cero"] = (pct == 0)
    df["subejecucion_parcial"] = (
        (pct > 0) & (pct < umbral_subejecucion)
    ).where(df["desenlace_observable"])

    # --- Senal 3: cierre sin liquidar (descriptiva) -------------------------
    df["sin_liquidar"] = df["liquidacion"].map(norm_txt).eq("no")

    # --- Compuestos ---------------------------------------------------------
    # Objetivo principal: las dos senales con prevalencia utilizable.
    df["desviacion"] = df["tiene_adicion"] | df["subejecucion_parcial"].fillna(False)

    # Severidad, con las tres senales del enunciado.
    tres = pd.DataFrame({
        "adicion": df["tiene_adicion"],
        "subejecucion_parcial": df["subejecucion_parcial"].fillna(False),
        "sin_liquidar": df["sin_liquidar"],
    })
    df["n_senales"] = tres.sum(axis=1)
    df["desviacion_severa"] = df["n_senales"] >= 2

    n_venc = int(df["plazo_vencido"].sum())
    n_adic = int(df["tiene_adicion"].sum())
    n_sub = int(df["subejecucion_parcial"].fillna(False).sum())
    n_liq = int(df["sin_liquidar"].sum())
    n_desv = int(df["desviacion"].sum())
    # Las cifras del texto se calculan aqui: escritas a mano, quedaban
    # desfasadas cada vez que cambiaba una definicion.
    n_eval = int(pct.notna().sum())
    pct_cero = 100 * int((pct == 0).sum()) / n_eval
    pct_cien = 100 * int((pct == 1).sum()) / n_eval
    n_rancio = int((df["estado_contrato"].map(norm_txt).eq("en ejecucion")
                    & df["plazo_vencido"]).sum())
    amplia = (df["tiene_adicion"] | (pct < umbral_subejecucion).fillna(False)
              | df["sin_liquidar"])
    bit.anotar(
        "11. Senales objetivo",
        "El enunciado define tres desviaciones, pero ninguna es directamente "
        f"utilizable: valor_pagado es una bandera casi binaria ({pct_cero:.2f} % en "
        f"cero, {pct_cien:.2f} % en 100 %), sin_liquidar se activa en "
        f"{100 * n_liq / len(df):.1f} % de los contratos, y estado_contrato esta "
        f"rancio en {n_rancio:,} registros cuyo plazo ya vencio.",
        f"Observabilidad por criterio temporal (plazo_vencido, {n_venc:,} filas). "
        f"desviacion = adicion de plazo ({n_adic:,}) O subejecucion parcial "
        f"({n_sub:,}) = {n_desv:,} casos ({100 * n_desv / len(df):.2f} %). "
        "sin_liquidar se conserva como descriptiva y entra solo en n_senales.",
        f"Un objetivo que se activa en el {100 * amplia.mean():.0f} % de los contratos "
        "(version amplia de las tres senales) no permite focalizar supervision. "
        "Restringir la senal "
        "financiera a la ejecucion parcial real separa el incumplimiento del "
        "simple fallo de reporte, y excluir sin_liquidar del compuesto evita que "
        "la norma administrativa se confunda con una anomalia.",
        n_desv, len(df))
    return df


# ==========================================================================
# Orquestador
# ==========================================================================
def limpiar(df: pd.DataFrame, umbral_subejecucion: float = 0.90):
    """Corre el pipeline completo. Devuelve (df_limpio, bitacora)."""
    bit = Bitacora()
    n0, c0 = df.shape

    pasos = [
        ("1  renombrando columnas", renombrar_columnas),
        ("2  centinelas a NaN", sentinelas_a_nan),
        ("3  normalizando categoricas", normalizar_categoricas),
        ("4  anulando fechas implausibles", anular_fechas_implausibles),
        ("5  derivando duracion", derivar_duracion),
        ("6  normalizando proveedor", normalizar_proveedor),
        ("7  extrayendo url", extraer_url),
        ("8  descomponiendo UNSPSC", descomponer_unspsc),
        ("9  derivadas temporales y monetarias", derivar_temporales_y_monetarias),
        ("10 marcando calidad", marcar_calidad_sospechosa),
    ]
    for etiqueta, fn in pasos:
        log(f"{etiqueta} ...")
        df = fn(df, bit)

    log("11 construyendo senales objetivo ...")
    df = construir_senales(df, bit, umbral_subejecucion)

    log(f"limpieza lista: {n0:,} x {c0}  ->  {df.shape[0]:,} x {df.shape[1]} "
        f"(+{df.shape[1] - c0} derivadas, 0 filas eliminadas)")
    return df, bit.to_frame()
