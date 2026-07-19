"""UMAP a/b curve-parameter fitting — bit-faithful to umap-learn 0.5.7.

``find_ab_params`` fits the smooth low-dimensional membership curve
``1 / (1 + a * x^(2b))`` to an offset exponential decay parameterised by
``spread`` and ``min_dist``. We reproduce umap-learn's exact ``curve_fit``
so the attractive/repulsive gradients downstream match the CPU path.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import curve_fit


def find_ab_params(spread: float, min_dist: float) -> tuple[float, float]:
    """Fit ``(a, b)`` for the UMAP low-dim membership curve.

    Identical to ``umap.umap_.find_ab_params``: fit
    ``1/(1 + a*x**(2b))`` against ``y=1`` for ``x < min_dist`` and
    ``y=exp(-(x-min_dist)/spread)`` otherwise, over ``x in [0, 3*spread]``.

    Parameters
    ----------
    spread
        Effective scale of embedded points.
    min_dist
        Minimum distance between embedded points.

    Returns
    -------
    tuple of float
        The fitted ``(a, b)`` parameters.
    """

    def curve(x, a, b):
        return 1.0 / (1.0 + a * x ** (2 * b))

    xv = np.linspace(0, spread * 3, 300)
    yv = np.zeros(xv.shape)
    yv[xv < min_dist] = 1.0
    yv[xv >= min_dist] = np.exp(-(xv[xv >= min_dist] - min_dist) / spread)
    params, _ = curve_fit(curve, xv, yv)
    return float(params[0]), float(params[1])
