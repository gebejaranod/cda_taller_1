# -*- coding: utf-8 -*-
"""
config.py
=========
Rutas del proyecto y constantes de perfilado compartidas por los notebooks.

Toda ruta se deriva de la posicion de este archivo, de modo que el repositorio
funciona sin importar donde se clone y sin variables de entorno.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

# --------------------------------------------------------------------------
# Rutas
# --------------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent

DATA_RAW = RAIZ / "data" / "raw"
DATA_PROC = RAIZ / "data" / "processed"
PARQUET_CRUDO = DATA_RAW / "secop_bienes.parquet"
PARQUET_LIMPIO = DATA_PROC / "contratos_limpio.parquet"

DOCS = RAIZ / "docs"
REPORTS = RAIZ / "reports"
FIGURAS = REPORTS / "figures"
TABLAS = REPORTS / "tablas"


def asegurar_directorios() -> None:
    """Crea las carpetas de salida si no existen. Idempotente."""
    for d in (DATA_PROC, FIGURAS, TABLAS):
        d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------
# Ventana de plausibilidad temporal
# --------------------------------------------------------------------------
# El dataset declara firmas entre 2019 y 2025, pero fecha_de_fin_del_contrato
# contiene valores imposibles (desde el anio 202 d.C. hasta 2065). Se considera
# plausible [2010, hoy+5]: holgado hacia atras para no descartar prorrogas
# heredadas, y hacia adelante para admitir contratos plurianuales.
# Fecha de observacion del dataset. Se congela a proposito: la regla de negocio
# R12 ("estado terminado implica fecha_de_fin <= hoy") y la dimension
# "Actualidad" del indice de calidad se miden contra ella. Con date.today() el
# reporte cambiaria solo por el paso del calendario y dos corridas del notebook
# en fechas distintas darian cifras distintas. Subirla es una decision
# deliberada, no un efecto secundario.
FECHA_CORTE = date(2026, 9, 23)
HOY = FECHA_CORTE

ANIO_MIN_PLAUSIBLE = 2010
ANIO_MAX_PLAUSIBLE = HOY.year + 5

# --------------------------------------------------------------------------
# Centinelas: texto que ocupa el lugar de un dato ausente
# --------------------------------------------------------------------------
# 34 de 36 columnas reportan cero nulos, pero 15 codifican los faltantes como
# texto. Sin este catalogo, isna() da una completitud aparente del 99,97 %
# frente a una completitud efectiva real del 97,04 %.
# Se comparan normalizados (minusculas, sin tildes, sin espacios extremos).
SENTINELAS = {
    "no definido", "no definida", "nodefinido", "no aplica",
    "no aplica/no pertenece", "noaplica", "unspecified", "unknown",
    "sin dato", "sin informacion", "sin definir", "n/a", "na", "n.a.",
    "null", "none", "nulo", "ninguno", "xxxx", "xxxxx", "xxx",
    "-", "--", "---", ".",
}

# --------------------------------------------------------------------------
# Nombres de columna
# --------------------------------------------------------------------------
# Mojibake heredado de la API Socrata: la tilde se perdio y quedo "_".
# El perfilado opera sobre los nombres crudos; el renombrado se aplica en la
# etapa de limpieza para no romper la trazabilidad con el reporte original.
RENOMBRES = {
    "duraci_n_del_contrato": "duracion_del_contrato",
    "g_nero_representante_legal": "genero_representante_legal",
    "liquidaci_n": "liquidacion",
    "obligaci_n_ambiental": "obligacion_ambiental",
}

COLS_NUMERICAS = [
    "valor_del_contrato", "valor_pagado", "valor_facturado",
    "valor_pendiente_de_pago", "dias_adicionados",
]
COLS_FECHA = [
    "fecha_de_firma", "fecha_de_inicio_del_contrato", "fecha_de_fin_del_contrato",
]
COLS_BINARIAS = [
    "es_pyme", "es_grupo", "habilita_pago_adelantado",
    "el_contrato_puede_ser_prorrogado", "liquidaci_n", "obligaci_n_ambiental",
]
COLS_ALTA_CARD = [
    "id_contrato", "nombre_entidad", "ciudad", "codigo_de_categoria_principal",
    "proveedor_adjudicado", "documento_proveedor", "objeto_del_contrato", "urlproceso",
]

# --------------------------------------------------------------------------
# Escalas de plausibilidad monetaria
# --------------------------------------------------------------------------
# PIB de Colombia a precios corrientes, orden de magnitud. Se usa solo como
# escala para senalar valores macro-imposibles: el contrato mayor del dataset
# equivale a 8 veces el PIB anual del pais.
PIB_COL = 1_600_000_000_000_000            # ~1.600 billones COP
TOPE_CONTRATO_PLAUSIBLE = 1_000_000_000_000  # 1 billon COP para un contrato de bienes

# Semilla unica para todo muestreo del proyecto.
SEMILLA = 42

# --------------------------------------------------------------------------
# Criterios de decision del contraste de hipotesis
# --------------------------------------------------------------------------
# El procedimiento de contraste exige fijar el nivel de significancia en el
# paso 2, *antes* de ver los datos, y no moverlo despues en funcion de lo que
# salga. Se declara aqui, en el modulo de configuracion que importan los cuatro
# notebooks, para que sea una constante del proyecto y no un argumento que se
# pueda ajustar contraste a contraste.
ALFA = 0.05

# La significancia estadistica no es el criterio de decision. Con n cercano a
# 196.000 una diferencia de 0,4 puntos porcentuales alcanza p < 0,001, asi que
# hace falta un umbral de relevancia practica, y ese umbral tambien se fija
# antes de ver los resultados.
V_MINIMA_UTIL = 0.10    # V de Cramer: por debajo de 0,10 el efecto es despreciable (Cohen)
DIF_MINIMA_PP = 2.0     # diferencia de proporciones en puntos porcentuales
RHO_MINIMO_UTIL = 0.30  # coeficiente de correlacion
ETA2_MINIMO_UTIL = 0.06  # eta cuadrado en ANOVA (efecto mediano segun Cohen)
# Para el Z test sobre log10(valor), la relevancia practica se expresa como el
# factor multiplicativo entre los grupos: un contrato del grupo con desviacion
# tiene que ser al menos 1,5 veces mas caro para que el criterio sirva de algo.
FACTOR_MINIMO_UTIL = 1.5
