# -*- coding: utf-8 -*-
"""
carga.py
========
Lectura del parquet crudo y de sus metadatos fisicos.

No modifica el archivo de origen. El sha256 se calcula para que el reporte
pueda afirmar sobre que bytes exactos se corrio el perfilado.
"""
from __future__ import annotations

import hashlib
import sys

import numpy as np
import pandas as pd

from .config import PARQUET_CRUDO, PARQUET_LIMPIO
from .utiles import log


def cargar_crudo(ruta=None):
    """Lee el parquet sin transformarlo. Devuelve (df, meta)."""
    import pyarrow.parquet as pq

    ruta = ruta or PARQUET_CRUDO
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encuentra {ruta}.\n"
            "El repositorio incluye el dataset en data/raw/. Si falta, "
            "copielo desde el enunciado del taller."
        )

    log(f"leyendo {ruta.name} ...")
    sha = hashlib.sha256(ruta.read_bytes()).hexdigest()
    pf = pq.ParquetFile(ruta)
    md = pf.metadata
    df = pd.read_parquet(ruta)
    meta = {
        "archivo": ruta.name,
        "ruta": str(ruta),
        "sha256": sha,
        "bytes": ruta.stat().st_size,
        "filas": int(md.num_rows),
        "columnas": int(md.num_columns),
        "row_groups": int(md.num_row_groups),
        "creado_por": md.created_by,
        "memoria_mb": round(df.memory_usage(deep=True).sum() / 1024 ** 2, 1),
        "generado": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "versiones": {
            "python": sys.version.split()[0],
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
    }
    log(f"cargado: {meta['filas']:,} filas x {meta['columnas']} columnas "
        f"({meta['memoria_mb']} MB en memoria)")
    return df, meta


def cargar_limpio(ruta=None):
    """Lee el parquet ya tratado que produce el notebook 01."""
    ruta = ruta or PARQUET_LIMPIO
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encuentra {ruta}.\n"
            "Ejecute primero notebooks/01_entendimiento_datos.ipynb, que es "
            "el que genera este archivo."
        )
    df = pd.read_parquet(ruta)
    log(f"dataset limpio: {len(df):,} filas x {df.shape[1]} columnas")
    return df
