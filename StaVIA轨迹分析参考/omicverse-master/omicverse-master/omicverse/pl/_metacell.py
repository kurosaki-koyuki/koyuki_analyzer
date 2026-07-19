"""Plotting helpers for ``ov.single.MetaCell``.

Each function takes a fitted :class:`~omicverse.single.MetaCell` (or a
mcRigor :class:`~omicverse.external.mcRigor.RigorReport`) so the tutorials
stay tiny — one call per figure, no inline matplotlib snippets — except
for the centroid overlay, which is plain ``ov.pl.embedding`` + ``ax.scatter``
in three lines and not worth abstracting.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .._registry import register_function


# ----------------------------------------------------------------------------
# Three benchmarking metrics: purity / separation / compactness
# ----------------------------------------------------------------------------


@register_function(
    aliases=["metacell_metrics", "元细胞指标", "metacell度量"],
    category="pl",
    description="Compute and plot the three SEACells-style benchmarking metrics (purity, separation, compactness) as side-by-side histograms.",
    examples=[
        "purity, separation, compactness = ov.pl.metacell_metrics(mc, label_key='clusters')",
    ],
    related=["single.MetaCell", "pl.metacell_centroids", "pl.metacell_purity_box"],
)
def metacell_metrics(
    mc,
    label_key: str = "clusters",
    use_rep: str = "X_pca",
    bins: int = 20,
    figsize=(11, 3),
    show: bool = True,
):
    """Compute purity / separation / compactness and plot 3 histograms.

    Returns
    -------
    (purity, separation, compactness)
        Three ``pd.DataFrame`` objects (per-metacell rows) used for the plot.
        Useful if you want to inspect the raw distributions.
    """
    import matplotlib.pyplot as plt
    import seaborn as sns

    purity = mc.compute_purity(label_key)
    separation = mc.compute_separation(use_rep=use_rep)
    compactness = mc.compute_compactness(use_rep=use_rep)

    fig, axes = plt.subplots(1, 3, figsize=figsize)
    sns.histplot(purity["purity"], bins=bins, ax=axes[0], color="#1f77b4")
    sns.histplot(separation["frac_1nn_same_metacell"], bins=bins, ax=axes[1], color="#2ca02c")
    sns.histplot(compactness["mean_centroid_dist"], bins=bins, ax=axes[2], color="#d62728")
    axes[0].set_xlabel("purity")
    axes[0].set_title("per-metacell purity")
    axes[1].set_xlabel("frac 1NN same MC")
    axes[1].set_title("separation")
    axes[2].set_xlabel("mean centroid dist")
    axes[2].set_title("compactness")

    if show:
        plt.tight_layout()
        plt.show()
    return purity, separation, compactness


# ----------------------------------------------------------------------------
# Per-celltype purity boxplot
# ----------------------------------------------------------------------------


@register_function(
    aliases=["metacell_purity_box", "元细胞纯度箱线图"],
    category="pl",
    description="Per-celltype boxplot of metacell purity. Reveals which celltypes get split most by the chosen backend.",
    examples=[
        "ov.pl.metacell_purity_box(mc, label_key='clusters')",
    ],
    related=["single.MetaCell", "pl.metacell_metrics"],
)
def metacell_purity_box(
    mc,
    label_key: str = "clusters",
    ax=None,
    figsize=(6, 3.5),
    show: bool = True,
):
    """Box plot of per-metacell purity, split by majority celltype."""
    import matplotlib.pyplot as plt
    import seaborn as sns

    df = mc.compute_purity(label_key).dropna(subset=["majority"])
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    sns.boxplot(
        data=df, x="majority", y="purity", ax=ax,
        order=sorted(df["majority"].unique()), color="#1f77b4",
    )
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("majority celltype")
    ax.set_ylabel("purity")
    ax.tick_params(axis="x", rotation=30)

    if show:
        plt.tight_layout()
        plt.show()
    return ax


# ----------------------------------------------------------------------------
# mcRigor: per-metacell mcDiv vs size scatter with threshold
# ----------------------------------------------------------------------------


@register_function(
    aliases=["rigor_scatter", "mcRigor_scatter", "元细胞rigor散点"],
    category="pl",
    description="Per-metacell mcDiv vs size scatter, overlaid with the size-stratified mcRigor threshold. Dubious metacells are highlighted in red.",
    examples=[
        "rep = mc.check_rigor()",
        "ov.pl.rigor_scatter(rep)",
    ],
    related=["single.MetaCell", "pl.metacell_metrics"],
)
def rigor_scatter(
    rep,
    ax=None,
    figsize=(5, 3.5),
    trustworthy_color: str = "#2ca02c",
    dubious_color: str = "#d62728",
    threshold_color: str = "red",
    show: bool = True,
):
    """Scatter plot of mcDiv vs metacell size, with the rigor threshold."""
    import matplotlib.pyplot as plt

    tab = rep.per_metacell
    colors = tab["label"].map({"trustworthy": trustworthy_color, "dubious": dubious_color})

    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    ax.scatter(
        tab["size"], tab["mcDiv"], c=colors, s=18, alpha=0.7,
        edgecolors="white", linewidths=0.4,
    )
    if len(rep.threshold):
        ax.plot(
            rep.threshold["size"], rep.threshold["thre"],
            color=threshold_color, linewidth=1.5,
            label="size-stratified threshold",
        )
        ax.legend(loc="best")
    ax.set_xlabel("metacell size")
    ax.set_ylabel("mcDiv  (T_org / T_colperm)")

    if show:
        plt.tight_layout()
        plt.show()
    return ax


# ----------------------------------------------------------------------------
# MetaQ-specific: codebook UMAP coloured by majority celltype
# ----------------------------------------------------------------------------


@register_function(
    aliases=["metacell_codebook_umap", "metaq_codebook_umap", "码本UMAP"],
    category="pl",
    description="UMAP of MetaQ's learned codebook (one dot per metacell prototype), coloured by majority cell-level annotation.",
    examples=[
        "ov.pl.metacell_codebook_umap(mc, label_key='clusters')",
    ],
    related=["single.MetaCell"],
)
def metacell_codebook_umap(
    mc,
    label_key: str = "clusters",
    n_neighbors: int = 15,
    min_dist: float = 0.3,
    random_state: int = 0,
    figsize=(5, 4),
    show: bool = True,
):
    """Project MetaQ's codebook to 2D and colour each entry by majority cell label."""
    import matplotlib.pyplot as plt
    import umap as _umap
    from sklearn.preprocessing import normalize

    if "codebook" not in mc.capabilities:
        raise NotImplementedError(
            f"Backend {mc.method!r} has no codebook capability. "
            "Codebook UMAP only available for 'metaq' / 'kmeans'."
        )

    cb = mc.codebook()
    cb_l2 = normalize(cb, norm="l2", axis=1)
    xy = _umap.UMAP(
        n_neighbors=min(n_neighbors, cb.shape[0] - 1),
        min_dist=min_dist, random_state=random_state,
    ).fit_transform(cb_l2)

    labels = mc._fit_result.assignments
    majority = []
    for u in range(cb.shape[0]):
        ix = np.where(labels == u)[0]
        if len(ix) == 0:
            majority.append("empty")
        else:
            vc = mc.adata.obs[label_key].iloc[ix].value_counts()
            majority.append(vc.index[0])
    majority = np.array(majority)

    fig, ax = plt.subplots(figsize=figsize)
    for ct in sorted(set(majority)):
        m = majority == ct
        ax.scatter(
            xy[m, 0], xy[m, 1], s=50, label=ct, alpha=0.85,
            edgecolors="white", linewidths=0.5,
        )
    ax.set_xlabel("codebook UMAP1")
    ax.set_ylabel("codebook UMAP2")
    ax.legend(loc="best", fontsize=7, frameon=False)
    ax.set_title(f"{mc.method} codebook UMAP (each dot = 1 metacell)")

    if show:
        plt.tight_layout()
        plt.show()
    return ax


# ----------------------------------------------------------------------------
# SEACells-specific: soft membership heatmap
# ----------------------------------------------------------------------------


@register_function(
    aliases=["metacell_soft_heatmap", "软分配热图"],
    category="pl",
    description="Heatmap of soft metacell membership for a random subset of cells × metacells.",
    examples=[
        "ov.pl.metacell_soft_heatmap(mc, n_cells=80, n_mc=40)",
    ],
    related=["single.MetaCell"],
)
def metacell_soft_heatmap(
    mc,
    n_cells: int = 80,
    n_mc: int = 40,
    random_state: int = 0,
    figsize=(7, 4),
    cmap: str = "viridis",
    show: bool = True,
):
    """Heatmap of a random subset of the soft membership matrix."""
    import matplotlib.pyplot as plt
    import seaborn as sns

    if "soft" not in mc.capabilities:
        raise NotImplementedError(
            f"Backend {mc.method!r} has no soft capability. "
            "Soft heatmap only available for 'seacells' / 'metaq'."
        )

    soft = mc.soft_membership().tocsr()
    rng = np.random.default_rng(random_state)
    sub_cells = rng.choice(soft.shape[0], min(n_cells, soft.shape[0]), replace=False)
    sub_mc = np.unique(soft[sub_cells].nonzero()[1])[: min(n_mc, soft.shape[1])]
    M = soft[np.ix_(sub_cells, sub_mc)].toarray()

    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(M, ax=ax, cmap=cmap, cbar_kws={"label": "membership weight"})
    ax.set_xlabel("metacell (subset)")
    ax.set_ylabel("cell (subset)")
    ax.set_title(
        f"soft membership for {len(sub_cells)} random cells × {len(sub_mc)} metacells"
    )

    if show:
        plt.tight_layout()
        plt.show()
    return ax
