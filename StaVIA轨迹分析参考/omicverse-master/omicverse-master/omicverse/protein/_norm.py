"""Per-sample normalization for proteomics AnnData.

``ov.protein.normalize(adata, method=...)`` is the unified dispatcher
that picks between median centering, quantile normalization, and a
``log2-only`` no-op (for already-normalised inputs like Olink NPX).
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from .._registry import register_function


@register_function(
    aliases=["protein_normalize", "normalize", "蛋白归一化"],
    category="preprocessing",
    description=(
        "Per-sample normalize a proteomics intensity matrix. ``method`` "
        "selects one of: ``'median'`` (subtract sample-median from each "
        "column after log2 — the standard LFQ default), "
        "``'equalize_medians'`` (DEqMS/MSstats column-median equalisation "
        "via the pydeqms backend), ``'quantile'`` (rank-based quantile "
        "equalisation), or ``'log2'`` (log2-only, no centering). NaN-safe "
        "in every case. Mutates ``adata.X``; stashes the pre-normalised "
        "copy in ``adata.layers['raw']``."
    ),
    requires={},
    produces={"layers": ["raw", "log2"]},
    auto_fix="none",
    examples=[
        "ov.protein.normalize(adata, method='median', log2=True)",
        "ov.protein.normalize(adata, method='quantile', log2=True)",
    ],
)
def normalize(
    adata,
    *,
    method: str = "median",
    log2: bool = True,
    stash_raw: bool = True,
) -> None:
    """Per-sample normalize ``adata.X`` in place.

    Parameters
    ----------
    method
        ``'median'`` | ``'quantile'`` | ``'log2'``.
    log2
        Apply ``log2(X + 1)`` before normalization. Set ``False`` if the
        matrix is already on log scale (Olink NPX, post-VSN).
    stash_raw
        Save the unmodified ``X`` to ``adata.layers['raw']``. Default ``True``.
    """
    method = method.lower().strip()
    valid = {"median", "equalize_medians", "quantile", "log2"}
    if method not in valid:
        raise ValueError(f"method must be one of {sorted(valid)}, got {method!r}")
    X = adata.X.astype(float, copy=True)

    if stash_raw and "raw" not in adata.layers:
        adata.layers["raw"] = X.copy()

    if log2:
        # log2(X+1) preserves zero / missing semantics (0 → 0).
        with np.errstate(invalid="ignore", divide="ignore"):
            X = np.log2(X + 1.0)
            # Negative inputs (Olink NPX is already log) become NaN here —
            # callers should pass log2=False for NPX.
        adata.layers["log2"] = X.copy()

    if method == "log2":
        # log2-only — no centering / quantile.
        adata.X = X
        return

    if method == "median":
        sample_medians = np.nanmedian(X, axis=1, keepdims=True)
        # Reference: overall median across samples.
        overall = np.nanmedian(sample_medians)
        X = X - sample_medians + overall
    elif method == "equalize_medians":
        try:
            from pydeqms import equal_median_normalization
        except ImportError as exc:
            raise ImportError(
                "method='equalize_medians' requires pydeqms: "
                "`pip install pydeqms`."
            ) from exc
        # pydeqms works on proteins × samples — transpose in and back.
        X = np.asarray(equal_median_normalization(X.T)).T
    elif method == "quantile":
        X = _quantile_normalize(X)

    adata.X = X


def _quantile_normalize(X: np.ndarray) -> np.ndarray:
    """Rank-based quantile normalization, NaN-tolerant.

    Mirrors ``limma::normalizeBetweenArrays(method='quantile')``: each
    sample's distribution is mapped to the average across samples after
    ranking. NaNs preserve their position (do not contribute to the rank
    average).
    """
    Y = X.copy()
    n_samples, n_proteins = Y.shape
    ranks = np.full_like(Y, np.nan, dtype=float)
    sorted_vals = []
    for i in range(n_samples):
        row = Y[i]
        finite = ~np.isnan(row)
        if not finite.any():
            sorted_vals.append(np.array([]))
            continue
        idx = np.where(finite)[0]
        order = idx[np.argsort(row[idx])]
        ranks_row = np.empty(idx.size)
        ranks_row[np.argsort(row[idx])] = np.linspace(0.0, 1.0, idx.size)
        ranks[i, idx] = ranks_row
        sorted_vals.append(np.sort(row[idx]))

    # Average reference distribution at fractional ranks 0..1.
    common_grid = np.linspace(0.0, 1.0, n_proteins)
    ref = np.zeros(n_proteins)
    cnt = np.zeros(n_proteins)
    for arr in sorted_vals:
        if arr.size == 0:
            continue
        # Interpolate each sample to the common grid.
        sample_grid = np.linspace(0.0, 1.0, arr.size)
        interp = np.interp(common_grid, sample_grid, arr)
        ref += interp
        cnt += 1.0
    ref = ref / np.maximum(cnt, 1.0)

    # Map each sample's NaN-aware ranks back to ref values.
    out = np.full_like(Y, np.nan, dtype=float)
    for i in range(n_samples):
        finite = ~np.isnan(Y[i])
        if not finite.any():
            continue
        r = ranks[i, finite]
        out[i, finite] = np.interp(r, common_grid, ref)
    return out
