# -*- coding: utf-8 -*-
"""
utiles.py
=========
Utilidades transversales: normalizacion de texto para comparar centinelas,
serializacion segura a JSON y entropia normalizada.
"""
from __future__ import annotations

import unicodedata
from datetime import date

import numpy as np
import pandas as pd


def log(msg: str) -> None:
    print(f"  {msg}", flush=True)


def norm_txt(s) -> str:
    """Minusculas, sin tildes, sin espacios extremos. Para comparar centinelas."""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()


def jdefault(o):
    """Serializador para tipos numpy/pandas."""
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        v = float(o)
        return v if np.isfinite(v) else None
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (np.ndarray,)):
        return o.tolist()
    if isinstance(o, (pd.Timestamp, date)):
        return str(o)
    if o is pd.NaT:
        return None
    return str(o)


def f(x):
    """Float seguro para JSON."""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def entropia_normalizada(counts: np.ndarray) -> float:
    """Entropía de Shannon dividida por log(k). 0 = constante, 1 = uniforme."""
    counts = counts[counts > 0]
    k = len(counts)
    if k <= 1:
        return 0.0
    p = counts / counts.sum()
    h = -(p * np.log(p)).sum()
    return float(h / np.log(k))
