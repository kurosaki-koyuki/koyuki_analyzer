"""Plotting for ``ov.protein``.

Diagnostic + result plots for the bulk-proteomics workflow:

* :func:`volcano` — log2FC × -log10(adj.P) scatter for a DE result.
* :func:`missing_pattern_plot` — heatmap of per-protein × per-sample
  missingness (white = observed, dark = missing).
* :func:`abundance_rank_plot` — per-sample rank-vs-intensity diagnostic
  (mirrors the MaxQuant ``QC_plot``).
* :func:`pca_plot` — sample PCA scatter, coloured by a metadata column.
* :func:`heatmap` — z-scored expression heatmap of the top DE proteins.
* :func:`boxplot` — per-sample intensity boxplots (normalization QC).
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

from .._registry import register_function


@register_function(
    aliases=["protein_volcano", "volcano", "蛋白火山图"],
    category="visualization",
    description=(
        "Volcano plot for a DE result table from ``ov.protein.de``. "
        "Highlights proteins passing ``adj_p_threshold`` (FDR) and "
        "``logfc_threshold`` (absolute log2FC). Returns the matplotlib "
        "axes for further annotation."
    ),
    examples=[
        "ov.protein.volcano(res, fc_col='logFC', p_col='adj.P.Val')",
    ],
)
def volcano(
    de_table: pd.DataFrame,
    *,
    fc_col: str = "logFC",
    p_col: str = "adj.P.Val",
    raw_p_col: str = "P.Value",
    logfc_threshold: float = 1.0,
    adj_p_threshold: float = 0.05,
    label_top: int = 10,
    gene_col: str = "gene",
    ax: Optional["matplotlib.axes.Axes"] = None,
    figsize: tuple[float, float] = (5.0, 4.5),
    s: float = 8.0,
    up_color: str = "#d62728",
    down_color: str = "#1f77b4",
    nochange_color: str = "#cccccc",
    title: Optional[str] = None,
):
    """Standard volcano: x = logFC, y = -log10(p). Highlights significant proteins."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)

    df = de_table.copy()
    pcol_used = p_col if p_col in df.columns else raw_p_col
    p = df[pcol_used].to_numpy(dtype=float)
    fc = df[fc_col].to_numpy(dtype=float)
    valid = np.isfinite(p) & np.isfinite(fc)
    df = df.loc[valid].reset_index(drop=True)
    p = p[valid]; fc = fc[valid]
    nlogp = -np.log10(np.clip(p, 1e-300, 1.0))

    up_mask = (fc >= logfc_threshold) & (p <= adj_p_threshold)
    down_mask = (fc <= -logfc_threshold) & (p <= adj_p_threshold)
    other_mask = ~(up_mask | down_mask)

    ax.scatter(fc[other_mask], nlogp[other_mask], s=s, c=nochange_color,
               edgecolor="none", alpha=0.7, label=None)
    ax.scatter(fc[up_mask], nlogp[up_mask], s=s, c=up_color,
               edgecolor="none", alpha=0.9,
               label=f"Up ({int(up_mask.sum())})")
    ax.scatter(fc[down_mask], nlogp[down_mask], s=s, c=down_color,
               edgecolor="none", alpha=0.9,
               label=f"Down ({int(down_mask.sum())})")

    ax.axhline(-np.log10(adj_p_threshold), color="black", lw=0.6, ls="--")
    ax.axvline(logfc_threshold, color="black", lw=0.6, ls="--")
    ax.axvline(-logfc_threshold, color="black", lw=0.6, ls="--")

    ax.set_xlabel(fc_col)
    ax.set_ylabel(f"-log10({pcol_used})")
    ax.legend(loc="best", fontsize=8, frameon=False)
    if title:
        ax.set_title(title)

    if label_top and gene_col in df.columns:
        # Label top-N most-significant proteins among the highlighted set.
        sig_idx = np.where(up_mask | down_mask)[0]
        if sig_idx.size:
            top = sig_idx[np.argsort(p[sig_idx])][:label_top]
            for i in top:
                ax.annotate(
                    str(df[gene_col].iloc[i]),
                    (fc[i], nlogp[i]),
                    fontsize=7, alpha=0.85,
                    xytext=(3, 3), textcoords="offset points",
                )

    return ax


@register_function(
    aliases=["protein_missing_pattern_plot", "missing_pattern_plot"],
    category="visualization",
    description=(
        "Heatmap of the proteomics missingness pattern. Rows are "
        "proteins (sorted by overall missingness), columns are samples. "
        "Useful for diagnosing MNAR vs MCAR before imputation."
    ),
    examples=["ov.protein.missing_pattern_plot(adata)"],
)
def missing_pattern_plot(
    adata,
    *,
    ax: Optional["matplotlib.axes.Axes"] = None,
    figsize: tuple[float, float] = (8.0, 5.0),
    cmap: str = "Greys",
    max_proteins: int = 1000,
):
    """Heatmap of per-protein × per-sample missingness — diagnose MNAR vs MCAR."""
    import matplotlib.pyplot as plt
    miss = np.isnan(adata.X).T.astype(float)  # proteins × samples
    order = np.argsort(-miss.mean(axis=1))
    miss = miss[order][:max_proteins]
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(miss, aspect="auto", cmap=cmap, interpolation="nearest")
    ax.set_xlabel("samples"); ax.set_ylabel(f"proteins (top {max_proteins} missing)")
    ax.set_xticks(np.arange(adata.n_obs))
    ax.set_xticklabels(adata.obs_names, rotation=90, fontsize=6)
    ax.set_yticks([])
    plt.colorbar(im, ax=ax, label="missing")
    return ax


@register_function(
    aliases=["protein_abundance_rank_plot", "abundance_rank_plot"],
    category="visualization",
    description=(
        "Per-sample rank-vs-log-intensity diagnostic — one line per "
        "sample, sorted by descending abundance. Use to spot under-/"
        "over-loaded samples before normalization."
    ),
    examples=["ov.protein.abundance_rank_plot(adata)"],
)
def abundance_rank_plot(
    adata,
    *,
    ax: Optional["matplotlib.axes.Axes"] = None,
    figsize: tuple[float, float] = (6.0, 4.0),
    log: bool = True,
    color_by: Optional[str] = None,
):
    """Per-sample rank-vs-log-intensity diagnostic; spots under/over-loaded samples."""
    import matplotlib.pyplot as plt
    X = adata.X.astype(float)
    if log:
        X = np.log2(np.where(X > 0, X, np.nan))
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    palette = None
    if color_by and color_by in adata.obs.columns:
        groups = adata.obs[color_by].astype(str)
        unique = pd.unique(groups)
        palette = {g: c for g, c in zip(
            unique, plt.cm.tab10.colors[: len(unique)]  # type: ignore[attr-defined]
        )}
    for i, sample in enumerate(adata.obs_names):
        row = X[i]
        row = row[~np.isnan(row)]
        row = np.sort(row)[::-1]
        if row.size == 0:
            continue
        color = palette[str(adata.obs[color_by].iloc[i])] if palette else None
        ax.plot(np.arange(row.size), row, lw=0.6, alpha=0.7,
                color=color, label=sample if not palette else None)
    ax.set_xlabel("rank (sorted high → low)")
    ax.set_ylabel("log2 intensity" if log else "intensity")
    if not palette and adata.n_obs <= 20:
        ax.legend(fontsize=6, ncol=2)
    return ax


@register_function(
    aliases=["protein_pca_plot", "pca_plot", "蛋白PCA图"],
    category="visualization",
    description=(
        "Sample-level PCA scatter for a proteomics AnnData — points are "
        "samples, coloured by an ``adata.obs`` column. Use it as a QC "
        "step after normalization / imputation to spot batch effects "
        "and outlier samples and to confirm the groups separate."
    ),
    examples=["ov.protein.pca_plot(adata, color='group')"],
)
def pca_plot(
    adata,
    *,
    color: Optional[str] = None,
    n_comps: int = 2,
    ax: Optional["matplotlib.axes.Axes"] = None,
    figsize: tuple[float, float] = (4.8, 4.2),
    s: float = 60.0,
    label_samples: bool = False,
):
    """PCA of samples (rows of ``adata.X``); colour by ``adata.obs[color]``."""
    import matplotlib.pyplot as plt
    from sklearn.decomposition import PCA

    X = adata.X.astype(float)
    # PCA needs complete data — mean-impute any residual NaNs for the projection.
    if np.isnan(X).any():
        col_mean = np.nanmean(X, axis=0, keepdims=True)
        X = np.where(np.isnan(X), col_mean, X)
    X = X - X.mean(axis=0, keepdims=True)
    pca = PCA(n_components=min(n_comps, *X.shape))
    scores = pca.fit_transform(X)
    var = pca.explained_variance_ratio_ * 100.0

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    if color and color in adata.obs.columns:
        groups = adata.obs[color].astype(str)
        for g in pd.unique(groups):
            m = (groups == g).to_numpy()
            ax.scatter(scores[m, 0], scores[m, 1], s=s, label=str(g),
                       edgecolor="white", linewidth=0.5, alpha=0.9)
        ax.legend(title=color, fontsize=8, frameon=False)
    else:
        ax.scatter(scores[:, 0], scores[:, 1], s=s,
                   edgecolor="white", linewidth=0.5, alpha=0.9)
    if label_samples:
        for i, name in enumerate(adata.obs_names):
            ax.annotate(str(name), (scores[i, 0], scores[i, 1]),
                        fontsize=6, xytext=(3, 3), textcoords="offset points")
    ax.set_xlabel(f"PC1 ({var[0]:.1f}%)")
    ax.set_ylabel(f"PC2 ({var[1]:.1f}%)" if var.size > 1 else "PC2")
    ax.set_title("Sample PCA")
    ax.axhline(0, color="grey", lw=0.5, ls="--")
    ax.axvline(0, color="grey", lw=0.5, ls="--")
    return ax


@register_function(
    aliases=["protein_heatmap", "heatmap", "蛋白热图"],
    category="visualization",
    description=(
        "Z-scored expression heatmap of the top differentially-expressed "
        "proteins. Rows = proteins (top ``n_top`` by ascending p-value "
        "from an ``ov.protein.de`` result), columns = samples grouped / "
        "annotated by ``group``. Each row is z-scored across samples."
    ),
    examples=[
        "ov.protein.heatmap(adata, de_table=res, group='group', n_top=40)",
    ],
)
def heatmap(
    adata,
    de_table: pd.DataFrame,
    *,
    group: Optional[str] = None,
    n_top: int = 40,
    gene_col: str = "gene",
    p_col: str = "adj.P.Val",
    ax: Optional["matplotlib.axes.Axes"] = None,
    figsize: tuple[float, float] = (7.0, 8.0),
    cmap: str = "RdBu_r",
):
    """Z-scored heatmap of the top-``n_top`` DE proteins across samples."""
    import matplotlib.pyplot as plt

    ranked = de_table.sort_values(p_col) if p_col in de_table.columns else de_table
    top_genes = [g for g in ranked[gene_col].astype(str).tolist()
                 if g in set(adata.var_names.astype(str))][:n_top]
    if not top_genes:
        raise ValueError("none of the DE-table genes are in adata.var_names")

    sub = adata[:, top_genes]
    M = sub.X.astype(float).T  # proteins × samples
    # Per-protein z-score across samples.
    mu = np.nanmean(M, axis=1, keepdims=True)
    sd = np.nanstd(M, axis=1, keepdims=True)
    Z = (M - mu) / np.where(sd == 0, 1.0, sd)

    # Order samples by group for a block-structured heatmap.
    sample_order = np.arange(adata.n_obs)
    col_labels = list(adata.obs_names.astype(str))
    if group and group in adata.obs.columns:
        g = adata.obs[group].astype(str).to_numpy()
        sample_order = np.argsort(g, kind="stable")
        Z = Z[:, sample_order]
        col_labels = [f"{adata.obs_names[i]}" for i in sample_order]
        group_sorted = g[sample_order]
    else:
        group_sorted = None

    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    vmax = float(np.nanpercentile(np.abs(Z), 98)) or 1.0
    im = ax.imshow(Z, aspect="auto", cmap=cmap, vmin=-vmax, vmax=vmax,
                   interpolation="nearest")
    ax.set_yticks(np.arange(len(top_genes)))
    ax.set_yticklabels(top_genes, fontsize=6)
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_xticklabels(col_labels, rotation=90, fontsize=6)
    # Group separators.
    if group_sorted is not None:
        bounds = np.where(group_sorted[:-1] != group_sorted[1:])[0] + 0.5
        for b in bounds:
            ax.axvline(b, color="black", lw=1.0)
    ax.set_title(f"Top {len(top_genes)} DE proteins (z-scored)")
    plt.colorbar(im, ax=ax, label="z-score", fraction=0.03, pad=0.02)
    return ax


@register_function(
    aliases=["protein_boxplot", "boxplot"],
    category="visualization",
    description=(
        "Per-sample intensity boxplots — a normalization QC plot. Run it "
        "before and after ``ov.protein.normalize`` to confirm the "
        "sample medians have been equalised."
    ),
    examples=["ov.protein.boxplot(adata, color_by='group')"],
)
def boxplot(
    adata,
    *,
    color_by: Optional[str] = None,
    ax: Optional["matplotlib.axes.Axes"] = None,
    figsize: tuple[float, float] = (7.0, 3.6),
):
    """Per-sample intensity boxplots (normalization QC)."""
    import matplotlib.pyplot as plt

    X = adata.X.astype(float)
    data = [row[~np.isnan(row)] for row in X]
    if ax is None:
        _, ax = plt.subplots(figsize=figsize)
    bp = ax.boxplot(data, showfliers=False, patch_artist=True,
                    medianprops=dict(color="black"))
    if color_by and color_by in adata.obs.columns:
        groups = adata.obs[color_by].astype(str)
        uniq = list(pd.unique(groups))
        palette = {g: c for g, c in zip(uniq, plt.cm.tab10.colors)}  # type: ignore[attr-defined]
        for patch, samp in zip(bp["boxes"], adata.obs_names):
            patch.set_facecolor(palette[str(adata.obs[color_by].loc[samp])])
            patch.set_alpha(0.7)
    ax.set_xticks(np.arange(1, adata.n_obs + 1))
    ax.set_xticklabels(adata.obs_names, rotation=90, fontsize=6)
    ax.set_ylabel("intensity")
    ax.set_title("Per-sample intensity distribution")
    return ax
