# -*- coding: utf-8 -*-
"""
viz.py
======
Estilo compartido de figuras y helper de guardado.

Un solo estilo para todo el proyecto: los notebooks no configuran matplotlib
por su cuenta, de modo que las figuras del informe se ven como una familia.
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

from .config import FIGURAS

# Paleta sobria, apta para impresion en escala de grises y para daltonismo.
AZUL = "#2b5d8a"
AZUL_CLARO = "#7ba7c7"
NARANJA = "#c1651a"
GRIS = "#8a8a8a"
ROJO = "#a63446"
VERDE = "#3f7d5c"

# Severidad de hallazgos de calidad, para barras y tablas.
# El perfilado emite las etiquetas en femenino y sin tilde ("Critica", "Alta",
# "Media", "Baja"), porque califican a "regla". Se incluyen tambien las
# variantes masculinas y acentuadas para que el mapeo no dependa de la grafia.
AMBAR = "#c9a227"
COLOR_SEVERIDAD = {
    "Critica": ROJO, "Crítica": ROJO, "Critico": ROJO, "Crítico": ROJO,
    "Alta": NARANJA, "Alto": NARANJA,
    "Media": AMBAR, "Medio": AMBAR,
    "Baja": GRIS, "Bajo": GRIS,
}

# Orden de severidad de mayor a menor, para leyendas y ordenamientos.
ORDEN_SEVERIDAD = ["Critica", "Alta", "Media", "Baja"]

CICLO = [AZUL, NARANJA, VERDE, ROJO, AZUL_CLARO, GRIS]


def aplicar_estilo() -> None:
    """Configura matplotlib para todo el notebook. Idempotente."""
    mpl.rcParams.update({
        "figure.figsize": (9, 5),
        "figure.dpi": 110,
        "savefig.dpi": 150,
        "savefig.bbox": "tight",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#dddddd",
        "grid.linewidth": 0.6,
        "legend.frameon": False,
        "axes.prop_cycle": mpl.cycler(color=CICLO),
    })


def guardar(fig, nombre: str) -> str:
    """Guarda la figura en reports/figures/ y devuelve la ruta relativa.

    El nombre no lleva extension; se escribe siempre PNG para que el informe
    en Markdown pueda enlazarla sin depender del visor.
    """
    FIGURAS.mkdir(parents=True, exist_ok=True)
    destino = FIGURAS / f"{nombre}.png"
    fig.savefig(destino)
    return f"reports/figures/{destino.name}"


def miles(x, pos=None) -> str:
    """Formateador de eje con separador de miles a la colombiana."""
    return f"{x:,.0f}".replace(",", ".")


def pesos_cortos(x, pos=None) -> str:
    """Formatea pesos colombianos en magnitudes legibles."""
    for umbral, sufijo in ((1e12, " B"), (1e9, " mM"), (1e6, " M"), (1e3, " k")):
        if abs(x) >= umbral:
            return f"{x / umbral:,.1f}{sufijo}".replace(",", ".")
    return f"{x:,.0f}".replace(",", ".")
