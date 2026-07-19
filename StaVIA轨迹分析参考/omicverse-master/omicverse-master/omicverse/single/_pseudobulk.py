"""Pseudobulk aggregation of single-cell data.

``ov.single.pseudobulk`` collapses a single-cell AnnData into per-sample
(optionally per-sample-per-celltype) pseudobulk profiles — the correct unit
for cohort-level differential expression with DESeq2 / edgeR / limma
(``ov.bulk.pyDEG``).

The API mirrors :func:`decoupler.pp.pseudobulk`
(https://decoupler.readthedocs.io/en/latest/api/generated/decoupler.pp.pseudobulk.html):
aggregate by ``sample_col`` and optionally ``groups_col``, with the same
QC fields written to the output (``obs['psbulk_n_cells']``,
``obs['psbulk_counts']``, ``layers['psbulk_props']``).
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import scipy.sparse as sp

from .._registry import register_function


def _get_matrix(adata, layer: Optional[str], raw: bool):
    """Resolve the cell × gene matrix to aggregate."""
    if raw:
        if adata.raw is None:
            raise ValueError("raw=True but adata.raw is None.")
        return adata.raw.X, list(adata.raw.var_names)
    if layer is not None:
        if layer not in adata.layers:
            raise KeyError(f"layer={layer!r} not in adata.layers.")
        return adata.layers[layer], list(adata.var_names)
    return adata.X, list(adata.var_names)


@register_function(
    aliases=["拟蛋白", "pseudobulk", "pseudo_bulk", "拟bulk", "伪bulk", "样本聚合"],
    category="single",
    description=(
        "Aggregate single-cell profiles into per-sample (optionally "
        "per-sample-per-celltype) pseudobulk profiles — the correct unit "
        "for cohort-level DE with DESeq2 / edgeR / limma. API mirrors "
        "decoupler.pp.pseudobulk."
    ),
    requires={
        "obs": [
            "sample_col — sample / donor / replicate label",
            "groups_col — optional cell-type / cluster label",
        ],
    },
    produces={
        "obs": ["psbulk_n_cells", "psbulk_counts"],
        "layers": ["psbulk_props"],
    },
    auto_fix="none",
    examples=[
        "# One pseudobulk profile per sample",
        "pb = ov.single.pseudobulk(adata, sample_col='donor')",
        "",
        "# Per-sample × per-celltype (the usual input for pyDEG)",
        "pb = ov.single.pseudobulk(adata, sample_col='donor',",
        "                          groups_col='celltype', layer='counts')",
        "",
        "# Mean instead of sum, drop tiny groups",
        "pb = ov.single.pseudobulk(adata, sample_col='donor',",
        "                          groups_col='celltype', mode='mean',",
        "                          min_cells=10)",
    ],
    related=["bulk.pyDEG", "single.get_obs_value", "single.MetaCell"],
)
def pseudobulk(
    adata,
    sample_col: str,
    groups_col: Optional[str] = None,
    layer: Optional[str] = None,
    raw: bool = False,
    mode: str = "sum",
    min_cells: int = 0,
    min_counts: int = 0,
    dtype=np.float32,
):
    """Summarise single-cell profiles into pseudobulk profiles.

    Parameters
    ----------
    adata : AnnData
        Single-cell AnnData. For DE downstream, point ``layer`` at raw counts.
    sample_col : str
        ``adata.obs`` column with the sample / donor / replicate label.
    groups_col : str or None, default=None
        ``adata.obs`` column with the cell-type / cluster label. When given,
        one pseudobulk profile is produced per ``(sample, group)`` pair;
        when ``None``, one per sample.
    layer : str or None, default=None
        Layer to aggregate. ``None`` uses ``adata.X``. For DESeq2 / edgeR
        this must be **raw counts**.
    raw : bool, default=False
        Aggregate ``adata.raw.X`` instead of ``adata.X`` / a layer.
    mode : str, default='sum'
        Aggregation: ``'sum'`` (counts — required by DESeq2 / edgeR),
        ``'mean'`` or ``'median'``.
    min_cells : int, default=0
        Drop pseudobulk profiles built from fewer than this many cells.
    min_counts : int, default=0
        Drop pseudobulk profiles whose total aggregated count is below this.
    dtype : numpy dtype, default=float32
        dtype of the output matrix.

    Returns
    -------
    AnnData
        Pseudobulk AnnData: rows = ``(sample, group)`` profiles, columns =
        genes. ``obs`` carries ``sample_col``, ``groups_col`` (if used),
        ``psbulk_n_cells`` (cells per profile), ``psbulk_counts`` (total
        aggregated count), plus any other ``obs`` column that is constant
        within every profile. ``layers['psbulk_props']`` holds, per gene,
        the fraction of cells in the profile with non-zero expression.
    """
    import anndata as ad

    if mode not in ("sum", "mean", "median"):
        raise ValueError(f"mode must be 'sum' / 'mean' / 'median', got {mode!r}")
    if sample_col not in adata.obs:
        raise KeyError(f"sample_col={sample_col!r} not in adata.obs.")
    if groups_col is not None and groups_col not in adata.obs:
        raise KeyError(f"groups_col={groups_col!r} not in adata.obs.")

    X, var_names = _get_matrix(adata, layer, raw)
    n_cells, n_genes = X.shape

    # ---- profile key: (sample) or (sample, group) ---------------------------
    sample = adata.obs[sample_col].astype(str).to_numpy()
    if groups_col is None:
        keys = pd.Index(sample)
        key_frame = pd.DataFrame({sample_col: sample})
    else:
        group = adata.obs[groups_col].astype(str).to_numpy()
        keys = pd.Index([f"{s}{chr(0)}{g}" for s, g in zip(sample, group)])
        key_frame = pd.DataFrame({sample_col: sample, groups_col: group})

    uniq, inv = np.unique(keys.to_numpy(), return_inverse=True)
    n_profiles = len(uniq)

    # ---- aggregate cell × gene → profile × gene -----------------------------
    # Sparse (n_profiles × n_cells) indicator P; P @ X aggregates.
    cells = np.arange(n_cells)
    counts_per_profile = np.bincount(inv, minlength=n_profiles).astype(float)

    if mode == "median":
        # Median needs a per-profile pass (no linear-algebra shortcut).
        Xd = X.toarray() if sp.issparse(X) else np.asarray(X)
        agg = np.vstack([
            np.median(Xd[inv == p], axis=0) for p in range(n_profiles)
        ]).astype(dtype)
    else:
        weight = np.ones(n_cells) if mode == "sum" else 1.0 / counts_per_profile[inv]
        P = sp.csr_matrix((weight, (inv, cells)), shape=(n_profiles, n_cells))
        agg = P @ X
        agg = np.asarray(agg.todense() if sp.issparse(agg) else agg, dtype=dtype)

    # ---- QC: expressed-gene proportion per profile --------------------------
    nz = (X != 0)
    if sp.issparse(nz):
        nz = nz.astype(float)
    else:
        nz = np.asarray(nz, dtype=float)
    Pcount = sp.csr_matrix((np.ones(n_cells), (inv, cells)), shape=(n_profiles, n_cells))
    props = Pcount @ nz
    props = np.asarray(props.todense() if sp.issparse(props) else props, dtype=dtype)
    props /= counts_per_profile[:, None]          # → fraction of cells expressing

    psbulk_counts = np.asarray(agg.sum(axis=1)).ravel()

    # ---- assemble output AnnData --------------------------------------------
    obs = pd.DataFrame(index=pd.Index(
        [u.replace(chr(0), " | ") for u in uniq], name="pseudobulk"
    ))
    # First cell index of each profile — used to read constant obs columns.
    first_idx = np.array([np.where(inv == p)[0][0] for p in range(n_profiles)])
    obs[sample_col] = key_frame[sample_col].to_numpy()[first_idx]
    if groups_col is not None:
        obs[groups_col] = key_frame[groups_col].to_numpy()[first_idx]
    obs["psbulk_n_cells"] = counts_per_profile.astype(int)
    obs["psbulk_counts"] = psbulk_counts

    # Carry over any other obs column that is constant within every profile.
    for col in adata.obs.columns:
        if col in (sample_col, groups_col):
            continue
        vals = adata.obs[col].astype(str).to_numpy()
        constant = np.ones(n_profiles, dtype=bool)
        rep = vals[first_idx]
        for p in range(n_profiles):
            if not (vals[inv == p] == rep[p]).all():
                constant[p] = False
        if constant.all():
            obs[col] = rep

    out = ad.AnnData(X=agg, obs=obs, var=adata.var.copy())
    out.layers["psbulk_props"] = props
    out.uns["pseudobulk"] = {
        "sample_col": sample_col,
        "groups_col": groups_col,
        "mode": mode,
        "layer": layer if layer is not None else ("raw" if raw else "X"),
        "n_source_cells": int(n_cells),
    }

    # ---- filter tiny / low-count profiles -----------------------------------
    keep = np.ones(n_profiles, dtype=bool)
    if min_cells > 0:
        keep &= out.obs["psbulk_n_cells"].to_numpy() >= min_cells
    if min_counts > 0:
        keep &= out.obs["psbulk_counts"].to_numpy() >= min_counts
    if not keep.all():
        dropped = int((~keep).sum())
        print(f"[pseudobulk] dropped {dropped}/{n_profiles} profiles "
              f"below min_cells={min_cells} / min_counts={min_counts}")
        out = out[keep].copy()

    print(f"[pseudobulk] {out.n_obs} profiles × {out.n_vars} genes "
          f"(mode={mode}, from {n_cells} cells)")
    return out
