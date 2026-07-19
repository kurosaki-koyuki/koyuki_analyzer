"""Imputation dispatcher for ``ov.protein``.

Wraps the full :mod:`pyimputelcmd` imputer suite (MinDet / MinProb /
QRILC / ZERO / MLE / KNN / SVD / MAR / MAR-MNAR) plus the two
commonest non-LCMD fallbacks (``half_min`` and ``min``). The single
:func:`impute` function takes ``method=...`` and writes the imputed
matrix to ``adata.X``, stashing the pre-imputation copy in
``adata.layers['pre_impute']``.

The ``'auto'`` method runs :func:`pyimputelcmd.model_selector` to
classify each protein as MCAR or MNAR, then applies an MAR imputer
(KNN) to the MCAR proteins and an MNAR imputer (QRILC) to the rest —
the recommended strategy from Lazar 2016.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from .._registry import register_function


_VALID_METHODS = {
    "mindet", "minprob", "qrilc",       # imputeLCMD left-censored
    "zero", "mle", "knn", "svd",        # imputeLCMD MAR-family
    "mar", "mar_mnar", "auto",          # imputeLCMD model-selector driven
    "half_min", "min",                  # non-LCMD fallbacks
}


@register_function(
    aliases=["protein_impute", "impute", "蛋白缺失值填补"],
    category="preprocessing",
    description=(
        "Impute missing values in a proteomics AnnData. ``method`` "
        "dispatches to the full imputeLCMD suite (via ``pyimputelcmd``): "
        "left-censored MNAR imputers ``'mindet'`` / ``'minprob'`` / "
        "``'qrilc'``; MAR-family ``'zero'`` / ``'mle'`` / ``'knn'`` / "
        "``'svd'``; model-selector-driven ``'mar'`` / ``'mar_mnar'`` / "
        "``'auto'`` (classify each protein MCAR vs MNAR then route); plus "
        "the non-LCMD fallbacks ``'half_min'`` and ``'min'``. All methods "
        "are NaN-aware and operate per-sample (column) on the proteins × "
        "samples layout that R uses; the wrapper transposes ``adata.X`` "
        "internally and back."
    ),
    requires={},
    produces={"layers": ["pre_impute"]},
    auto_fix="none",
    examples=[
        "ov.protein.impute(adata, method='qrilc', seed=0)",
        "ov.protein.impute(adata, method='mindet')",
        "ov.protein.impute(adata, method='knn', n_neighbors=5)",
        "ov.protein.impute(adata, method='auto')  # MCAR/MNAR-aware",
    ],
)
def impute(
    adata,
    *,
    method: str = "qrilc",
    seed: Optional[int] = 0,
    stash: bool = True,
    **kwargs,
) -> None:
    """Impute ``adata.X`` in place using the requested ``method``.

    Parameters
    ----------
    adata
        AnnData with ``X`` = samples × proteins (omicverse layout). NaN
        marks missing.
    method
        Selector — see the function description.
    seed
        Optional seed for stochastic imputers (``minprob`` / ``qrilc``).
    stash
        Save the pre-imputation matrix to ``adata.layers['pre_impute']``
        (default ``True``).
    **kwargs
        Forwarded to the chosen imputer (e.g. ``q=0.01``,
        ``tune_sigma=1.0``, ``n_neighbors=5``).
    """
    key = method.lower().strip()
    if key not in _VALID_METHODS:
        raise ValueError(
            f"method must be one of {sorted(_VALID_METHODS)}, got {method!r}"
        )
    X = adata.X.astype(float, copy=True)  # samples × proteins
    if stash and "pre_impute" not in adata.layers:
        adata.layers["pre_impute"] = X.copy()

    # Transpose to proteins × samples for the R-convention imputers.
    XT = X.T

    if key in ("half_min", "min"):
        imputed = XT.copy()
        # Per-sample (column) minimum.
        col_min = np.nanmin(imputed, axis=0, keepdims=True)
        fill = col_min if key == "min" else col_min / 2.0
        # Where col_min itself is NaN (all-NaN column), fall back to global min.
        global_min = np.nanmin(imputed)
        fill = np.where(np.isnan(fill), global_min, fill)
        mask = np.isnan(imputed)
        imputed[mask] = np.broadcast_to(fill, imputed.shape)[mask]
    else:
        # Everything else is a pyimputelcmd backend.
        try:
            import pyimputelcmd as pyi
        except ImportError as exc:
            raise ImportError(
                f"method={key!r} requires ``pyimputelcmd``: "
                "`pip install pyimputelcmd`."
            ) from exc
        if key in ("minprob", "qrilc", "minprob"):
            kwargs.setdefault("seed", seed)
        if key in ("mar", "mar_mnar", "auto"):
            # Model-selector-driven imputation: classify MCAR vs MNAR,
            # then route each protein to the appropriate imputer.
            mcar_mask, _thr = pyi.model_selector(XT)
            if key == "mar":
                imputed = pyi.impute_mar(
                    XT, mcar_mask, method=kwargs.pop("mar_method", "mle"),
                )
            else:  # 'mar_mnar' / 'auto'
                imputed = pyi.impute_mar_mnar(
                    XT, mcar_mask,
                    method_mar=kwargs.pop("method_mar", "knn"),
                    method_mnar=kwargs.pop("method_mnar", "qrilc"),
                    **kwargs,
                )
        else:
            # Single-method imputers — dispatch through pyimputelcmd.impute.
            imputed = pyi.impute(XT, method=key, **kwargs)

    adata.X = np.asarray(imputed).T  # back to samples × proteins
    adata.uns.setdefault("protein", {})["impute_method"] = key
