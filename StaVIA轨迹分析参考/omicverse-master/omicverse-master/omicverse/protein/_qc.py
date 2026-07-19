"""QC for proteomics AnnData: peptide-count / valid-value filtering and
missing-pattern statistics. ``ov.protein`` follows the omicverse
convention of mutating ``adata`` in place — same as ``ov.metabol.cv_filter``."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .._registry import register_function


@register_function(
    aliases=["protein_qc_filter", "qc_filter", "蛋白质控"],
    category="preprocessing",
    description=(
        "Drop low-quality proteins from a proteomics AnnData. Two filters: "
        "(1) peptide-count threshold (``min_peptides``) on a per-protein "
        "metadata column; (2) per-protein minimum number of valid (non-NaN) "
        "samples (``min_valid``). Both default to keeping proteins with "
        "≥2 peptides and ≥50% valid samples — the MaxQuant default."
    ),
    requires={"var": []},
    produces={"obs": ["n_valid_proteins"], "var": ["n_valid_samples"]},
    auto_fix="none",
    examples=[
        "ov.protein.qc_filter(adata, min_peptides=2, min_valid=0.5)",
        "ov.protein.qc_filter(adata, min_peptides=2, peptides_col='Combined.Total.Peptides')",
    ],
)
def qc_filter(
    adata,
    *,
    min_peptides: int = 2,
    peptides_col: str = "peptides",
    min_valid: float = 0.5,
    inplace: bool = True,
) -> "AnnData | None":
    """Subset ``adata`` to proteins passing peptide-count and missingness QC.

    Parameters
    ----------
    adata
        ``AnnData`` from ``ov.protein.read_*``.
    min_peptides
        Minimum count in ``adata.var[peptides_col]``. Set to 0 to skip.
        Silently skipped if the column does not exist.
    peptides_col
        Column in ``adata.var`` holding the peptide count.
    min_valid
        Per-protein minimum fraction of samples with a valid (non-NaN)
        intensity. If ≥1, treated as an integer count instead of a
        fraction.
    inplace
        Modify ``adata`` in place (default) or return a new object.

    Returns
    -------
    None | AnnData
        ``None`` when ``inplace=True``; the filtered ``AnnData`` otherwise.
    """
    X = adata.X
    n_samples = X.shape[0]
    n_valid_per_var = np.sum(~np.isnan(X), axis=0)

    keep = np.ones(adata.n_vars, dtype=bool)

    if min_peptides > 0 and peptides_col in adata.var.columns:
        peptides = pd.to_numeric(adata.var[peptides_col], errors="coerce")
        keep &= (peptides.fillna(0).to_numpy() >= min_peptides)

    if min_valid > 0:
        thresh = (min_valid if min_valid >= 1 else min_valid * n_samples)
        keep &= n_valid_per_var >= thresh

    # Persist QC metrics.
    adata.var["n_valid_samples"] = n_valid_per_var
    if inplace:
        kept_idx = np.flatnonzero(keep)
        # AnnData's slice copies. Replace contents.
        new = adata[:, kept_idx].copy()
        adata._init_as_actual(
            X=new.X, obs=new.obs, var=new.var,
            obsm=dict(new.obsm), varm=dict(new.varm),
            uns=dict(new.uns), layers=dict(new.layers),
        )
        # Per-sample valid-protein count (after filtering).
        adata.obs["n_valid_proteins"] = np.sum(~np.isnan(adata.X), axis=1)
        return None
    out = adata[:, keep].copy()
    out.obs["n_valid_proteins"] = np.sum(~np.isnan(out.X), axis=1)
    return out


@register_function(
    aliases=["protein_model_selector", "model_selector", "缺失机制分类"],
    category="preprocessing",
    description=(
        "Classify each protein's missingness as MCAR (missing completely "
        "at random) or MNAR (missing not at random, i.e. left-censored) "
        "using the imputeLCMD ``model.Selector`` algorithm (via "
        "``pyimputelcmd``). Writes a boolean ``adata.var['is_mcar']`` "
        "column (True = MCAR/MAR) and returns the per-protein mask plus "
        "the estimated censoring threshold. Use it to decide between "
        "MAR imputers (KNN/MLE) and MNAR imputers (QRILC)."
    ),
    requires={},
    produces={"var": ["is_mcar"]},
    auto_fix="none",
    examples=["mask, thr = ov.protein.model_selector(adata)"],
)
def model_selector(adata):
    """Classify proteins as MCAR vs MNAR (imputeLCMD model.Selector).

    Returns
    -------
    (np.ndarray[bool], float)
        Per-protein MCAR mask (True = MCAR/MAR) and the estimated
        censoring threshold. Also written to ``adata.var['is_mcar']``.
    """
    try:
        import pyimputelcmd as pyi
    except ImportError as exc:
        raise ImportError(
            "model_selector requires pyimputelcmd: `pip install pyimputelcmd`."
        ) from exc
    # pyimputelcmd works on proteins × samples.
    mask, threshold = pyi.model_selector(adata.X.T.astype(float))
    adata.var["is_mcar"] = np.asarray(mask, dtype=bool)
    adata.uns.setdefault("protein", {})["mnar_threshold"] = float(threshold)
    return mask, float(threshold)


@register_function(
    aliases=["protein_missing_pattern", "missing_pattern"],
    category="preprocessing",
    description=(
        "Tabulate the per-protein and per-sample missingness pattern. "
        "Returns a dict with ``protein_missing_frac`` (Series), "
        "``sample_missing_frac`` (Series), and ``overall`` (float)."
    ),
    examples=["stats = ov.protein.missing_pattern(adata)"],
)
def missing_pattern(adata) -> dict:
    """Per-protein / per-sample / overall missing fraction for a proteomics AnnData."""
    X = adata.X
    miss = np.isnan(X)
    return {
        "protein_missing_frac": pd.Series(
            miss.mean(axis=0), index=adata.var_names, name="missing_frac",
        ),
        "sample_missing_frac": pd.Series(
            miss.mean(axis=1), index=adata.obs_names, name="missing_frac",
        ),
        "overall": float(miss.mean()),
    }
