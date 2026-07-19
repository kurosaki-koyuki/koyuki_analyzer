"""Thin wrapper around :mod:`pyfunkyheatmap` for ``omicverse.pl``.

Re-exports the upstream :func:`pyfunkyheatmap.funky_heatmap` entry point and
helpers so users can call them via ``ov.pl.funky_heatmap(...)`` without
importing the third-party package explicitly. The dependency is loaded
lazily so that importing :mod:`omicverse.pl` doesn't fail if
``pyfunkyheatmap`` isn't installed.

Example::

    import omicverse as ov
    ov.style(font_path='Arial')

    import pandas as pd
    df = pd.DataFrame({
        'id':  ['A', 'B', 'C', 'D'],
        'x':   [0.1, 0.55, 0.8, 0.95],
        'y':   [0.5, 0.25, 0.75, 0.6],
        'tag': ['alpha', 'beta', 'gamma', 'delta'],
    })
    fh = ov.pl.funky_heatmap(df)
    fh.save('out.png', dpi=150)

Upstream: https://github.com/omicverse/py-funkyheatmap
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .._registry import register_function


_MISSING_MSG = (
    "ov.pl.funky_heatmap requires the `pyfunkyheatmap` package.\n"
    "Install with: pip install pyfunkyheatmap"
)


def _load():
    try:
        return import_module("pyfunkyheatmap")
    except ImportError as exc:  # pragma: no cover - exercised at call time
        raise ImportError(_MISSING_MSG) from exc


@register_function(
    aliases=[
        "funkyheatmap", "funky_heatmap", "funky 热图", "花式热图",
        "基准热图", "benchmark heatmap", "dynbenchmark heatmap",
        "scIB heatmap", "多指标表可视化",
    ],
    category="pl",
    description=(
        "Publication-ready dynbenchmark-style heatmap for benchmark / "
        "multi-metric tables, with funky rectangles, circles, bars, pies, "
        "text and image glyphs. Thin wrapper over pyfunkyheatmap — pure "
        "Python port of the R funkyheatmap package."
    ),
    examples=[
        "# Default heatmap from a DataFrame",
        "import omicverse as ov",
        "import pandas as pd",
        "ov.style(font_path='Arial')",
        "df = pd.DataFrame({",
        "    'id':   ['UMAP','t-SNE','PHATE','PCA','Diffusion','Slingshot'],",
        "    'accuracy': [0.83, 0.71, 0.94, 0.62, 0.88, 0.79],",
        "    'speed':    [0.42, 0.30, 0.20, 0.91, 0.55, 0.68],",
        "    'memory':   [0.60, 0.55, 0.85, 0.30, 0.70, 0.50],",
        "})",
        "fh = ov.pl.funky_heatmap(df)",
        "fh.save('benchmark.png', dpi=150)",
        "",
        "# Custom geoms per column",
        "column_info = pd.DataFrame({",
        "    'id':   ['id','accuracy','speed','memory'],",
        "    'name': ['Method','Accuracy','Speed','Memory'],",
        "    'geom': ['text','funkyrect','circle','bar'],",
        "})",
        "ov.pl.funky_heatmap(df, column_info=column_info)",
        "",
        "# Grouped columns + custom palettes + legends + row groups",
        "column_groups = pd.DataFrame({",
        "    'group': ['perf','resources'],",
        "    'level1':['Perf','Resources'],",
        "})",
        "palettes = {'perf_pal':'Blues','res_pal':'Reds'}",
        "legends = [dict(palette='perf_pal', geom='rect',",
        "                title='Overall', labels=['0','','0.5','','1'])]",
        "ov.pl.funky_heatmap(df, column_info=column_info,",
        "                    column_groups=column_groups,",
        "                    palettes=palettes, legends=legends)",
    ],
    related=["heatmap", "marsilea_heatmap", "dotplot"],
)
def funky_heatmap(*args: Any, **kwargs: Any):
    """Generate a funky heatmap from a :class:`pandas.DataFrame`.

    Thin wrapper around :func:`pyfunkyheatmap.funky_heatmap`. Supports the
    full upstream parameter list: ``column_info``, ``row_info``,
    ``column_groups``, ``row_groups``, ``palettes``, ``legends``,
    ``position_args``, ``scale_column``, ``add_abc``, and rendering
    knobs ``fig``, ``ax``, ``fig_scale``, ``dpi``.

    Returns a :class:`pyfunkyheatmap.FunkyHeatmap` object wrapping the
    matplotlib figure (``fh.figure``) and the underlying geometry tables
    (``fh.geom_positions``). Call ``fh.save(path)`` to write the figure.

    See :mod:`pyfunkyheatmap` for the full reference, and the
    `t_funkyheatmap.ipynb tutorial
    <https://omicverse.readthedocs.io/en/latest/Tutorials-plotting/t_funkyheatmap.html>`__.
    """
    return _load().funky_heatmap(*args, **kwargs)


def position_arguments(**kwargs: Any):
    """Build a layout-args container.

    Thin wrapper around :func:`pyfunkyheatmap.position_arguments`.
    """
    return _load().position_arguments(**kwargs)


def scale_minmax(x):
    """Min-max scale a vector to ``[0, 1]``.

    Thin wrapper around :func:`pyfunkyheatmap.scale_minmax`.
    """
    return _load().scale_minmax(x)


__all__ = ["funky_heatmap", "position_arguments", "scale_minmax"]
