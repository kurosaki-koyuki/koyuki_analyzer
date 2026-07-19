"""Lightweight diagnostic plots used by :mod:`omicverse.report`.

These helpers produce simple, publication-ready figures that cover a few
gaps in ``omicverse.pl``: a cluster-size bar chart, a doublet-score
histogram with the call threshold overlaid, and a neighbor-graph degree
distribution. They are intentionally generic so you can call them
directly as ``ov.pl.cluster_sizes_bar(adata, 'leiden')`` etc.
"""
from __future__ import annotations

from typing import Optional

import matplotlib.pyplot as plt
import numpy as np

from ._palette import palette_28, sc_color


def _resolve_palette(n: int) -> list[str]:
    """Return at least ``n`` distinct hex colours from omicverse palettes."""
    base = list(palette_28) if n > len(sc_color) else list(sc_color)
    if n <= len(base):
        return base[:n]
    return [base[i % len(base)] for i in range(n)]


def auto_resolution_curve(
    adata=None,
    *,
    scores=None,
    best: Optional[float] = None,
    show_real: bool = True,
    show_null: bool = True,
    show_excess: bool = True,
    title: str = "Resolution-stability curve (Lange et al. 2004)",
    figsize: tuple[float, float] = (6.4, 4.0),
    ax: Optional[plt.Axes] = None,
    show: Optional[bool] = None,
    return_fig: bool = False,
):
    """Line-plot of bootstrap-stability scores from
    :func:`omicverse.single.auto_resolution`.

    Without arguments, reads the scores stored at
    ``adata.uns['autoResolution']``::

        ov.single.auto_resolution(adata)
        ov.pl.auto_resolution_curve(adata)

    Or pass an explicit ``scores`` table — either the DataFrame returned
    by ``auto_resolution`` or the dict form
    ``adata.uns['autoResolution']['scores']`` (round-trips through h5ad).

    Parameters
    ----------
    adata
        AnnData on which ``auto_resolution`` was run. If ``scores`` is
        not given, it is pulled from
        ``adata.uns['autoResolution']['scores']``.
    scores
        Optional explicit override (DataFrame or scores dict).
    best
        Resolution to highlight with a vertical line. If ``None``, the
        function uses ``adata.uns['autoResolution']['best_resolution']``
        (or, failing that, the argmax of ``excess_stability``).
    show_real, show_null, show_excess
        Toggle individual lines.
    """
    import pandas as pd

    if scores is None:
        if adata is None or "autoResolution" not in adata.uns:
            raise ValueError(
                "auto_resolution_curve needs either `scores` or an "
                "AnnData with `adata.uns['autoResolution']` populated "
                "by ov.single.auto_resolution(adata)."
            )
        scores = adata.uns["autoResolution"]["scores"]
        if best is None:
            best = adata.uns["autoResolution"].get("best_resolution")

    if isinstance(scores, dict):
        df = pd.DataFrame(scores).set_index("resolution").sort_index()
    else:
        df = scores.sort_index() if hasattr(scores, "sort_index") \
              else pd.DataFrame(scores)

    have_null = ("stability_null" in df.columns
                  and df["stability_null"].abs().sum() > 0)
    have_excess = "excess_stability" in df.columns and have_null
    if best is None:
        best = float(
            df["excess_stability"].idxmax() if have_excess
            else df["stability_real"].idxmax()
        )

    created = ax is None
    fig = ax.figure if ax is not None else plt.figure(figsize=figsize)
    if ax is None:
        ax = fig.add_subplot(111)

    x = df.index.astype(float).values
    if show_real and "stability_real" in df.columns:
        ax.plot(x, df["stability_real"].values, "o-",
                color=sc_color[0], lw=1.6, ms=5,
                label="real (bootstrap mean ARI)")
    if show_null and have_null:
        ax.plot(x, df["stability_null"].values, "s--",
                color="#B7B1A4", lw=1.2, ms=4,
                label="null (per-gene permutation)")
    if show_excess and have_excess:
        ax.plot(x, df["excess_stability"].values, "D-",
                color=sc_color[10], lw=2.0, ms=6,
                label="excess = real − null")

    ax.axvline(best, color=sc_color[10], lw=1.0, ls=":", alpha=0.7)
    n_cl = (int(df.loc[best, "n_clusters"])
            if "n_clusters" in df.columns and best in df.index else None)
    label_y = ax.get_ylim()[1] if ax.get_ylim()[1] > 0 else 1.0
    ax.text(best, label_y, f" chosen r={best}"
                              + (f"\n {n_cl} clusters" if n_cl is not None else ""),
            va="top", ha="left", fontsize=10,
            color=sc_color[10], alpha=0.95)

    ax.set_xlabel("Leiden resolution")
    ax.set_ylabel("stability (mean bootstrap ARI)")
    ax.set_title(title)
    ax.axhline(0, color="#888", lw=0.5, alpha=0.5)
    ax.legend(loc="lower right", frameon=False, fontsize=9)

    if show:
        plt.show()
    if created and return_fig:
        return fig
    return ax


def cluster_sizes_bar(
    adata,
    groupby: str,
    *,
    ax: Optional[plt.Axes] = None,
    figsize: tuple[float, float] = (7.6, 3.2),
    title: Optional[str] = None,
    xlabel: Optional[str] = None,
    ylabel: str = "# cells",
    show: Optional[bool] = None,
    return_fig: bool = False,
):
    """Bar chart of cell counts per cluster.

    Parameters
    ----------
    adata
        AnnData with ``groupby`` in ``adata.obs``.
    groupby
        Categorical column in ``adata.obs`` (e.g. ``"leiden"``).
    ax
        Matplotlib axes to draw into. A new figure is created if omitted.
    figsize
        Size of the created figure when ``ax`` is ``None``.
    title, xlabel, ylabel
        Text overrides.
    show
        If ``None`` (default), returns the ``Figure``/``Axes`` following
        omicverse's convention; if ``False``, returns silently; if
        ``True``, calls ``plt.show()``.
    return_fig
        If True and a new figure was created, return the ``Figure`` rather
        than the ``Axes``.
    """
    if groupby not in adata.obs.columns:
        raise ValueError(f"{groupby!r} not in adata.obs")
    sizes = adata.obs[groupby].astype("category").value_counts().sort_index()
    n = len(sizes)
    colors = _resolve_palette(n)

    created = ax is None
    fig = ax.figure if ax is not None else plt.figure(figsize=figsize)
    if ax is None:
        ax = fig.add_subplot(111)

    ax.bar(range(n), sizes.values, color=colors,
           edgecolor="white", linewidth=0.4, width=0.85)
    ax.set_xlabel(xlabel if xlabel is not None else f"{groupby} cluster")
    ax.set_ylabel(ylabel)
    ax.set_title(title if title is not None
                 else f"{groupby} cluster sizes  ·  total {n}")
    if n <= 30:
        ax.set_xticks(range(n))
        ax.set_xticklabels([str(s) for s in sizes.index], rotation=0)

    if show:
        plt.show()
    if created and return_fig:
        return fig
    return ax


def doublet_score_histogram(
    adata,
    *,
    score_key: str = "doublet_score",
    call_key: str = "predicted_doublet",
    bins: int = 60,
    color: Optional[str] = None,
    threshold_color: Optional[str] = None,
    ax: Optional[plt.Axes] = None,
    figsize: tuple[float, float] = (7.6, 3.0),
    title: str = "Doublet score distribution",
    show: Optional[bool] = None,
    return_fig: bool = False,
):
    """Histogram of doublet scores with the call threshold marked.

    Expects ``adata.obs[score_key]`` (e.g. from ``ov.pp.scdblfinder`` or
    ``ov.pp.scrublet``). If ``adata.obs[call_key]`` is present the
    smallest score among called doublets is drawn as a dashed threshold.
    """
    if score_key not in adata.obs.columns:
        raise ValueError(f"{score_key!r} not in adata.obs — has doublet "
                          "detection been run?")
    s = adata.obs[score_key].dropna().astype(float).values
    color = color or sc_color[7]
    threshold_color = threshold_color or sc_color[10]

    created = ax is None
    fig = ax.figure if ax is not None else plt.figure(figsize=figsize)
    if ax is None:
        ax = fig.add_subplot(111)

    ax.hist(s, bins=bins, color=color, alpha=0.85,
            edgecolor="white", linewidth=0.3)
    ax.set_xlabel(score_key)
    ax.set_ylabel("# cells")
    ax.set_title(title)
    if call_key in adata.obs.columns and bool(adata.obs[call_key].sum()):
        thr = float(adata.obs.loc[adata.obs[call_key], score_key].min())
        ax.axvline(thr, color=threshold_color, linewidth=1.4, linestyle="--",
                    label=f"call threshold = {thr:.2f}")
        ax.legend(loc="upper right")

    if show:
        plt.show()
    if created and return_fig:
        return fig
    return ax


def highly_variable_genes_scatter(
    adata,
    *,
    hv_col: str = "highly_variable",
    mean_col: Optional[str] = None,
    disp_col: Optional[str] = None,
    ax: Optional[plt.Axes] = None,
    figsize: tuple[float, float] = (6.0, 4.0),
    title: str = "Highly variable genes",
    show: Optional[bool] = None,
    return_fig: bool = False,
):
    """Mean-vs-dispersion scatter with HVG highlighted.

    Reads the per-gene stats produced by omicverse / scanpy HVG
    selection. ``mean_col`` defaults to ``"means"`` (scanpy) or
    ``"mean"`` (fallback); ``disp_col`` defaults to
    ``"residual_variances"`` (omicverse pearson-residual flavour),
    falling back to ``"dispersions_norm"`` or ``"variances"``.
    """
    var = adata.var
    if hv_col not in var.columns:
        raise ValueError(f"{hv_col!r} not in adata.var — run HVG selection first.")

    if mean_col is None:
        mean_col = next((c for c in ("means", "mean") if c in var.columns), None)
    if disp_col is None:
        disp_col = next(
            (c for c in ("residual_variances", "dispersions_norm",
                         "dispersions", "variances") if c in var.columns),
            None,
        )
    if mean_col is None or disp_col is None:
        raise ValueError("could not locate mean/dispersion columns in adata.var")

    x = var[mean_col].astype(float).values
    y = var[disp_col].astype(float).values
    hv = var[hv_col].astype(bool).values

    created = ax is None
    fig = ax.figure if ax is not None else plt.figure(figsize=figsize)
    if ax is None:
        ax = fig.add_subplot(111)

    ax.scatter(x[~hv], y[~hv], s=6, alpha=0.45, c="#B7B1A4",
                linewidths=0, label="other")
    ax.scatter(x[hv], y[hv], s=8, alpha=0.85, c=sc_color[10],
                linewidths=0, label=f"HVG (n={int(hv.sum())})")
    ax.set_xscale("log")
    ax.set_xlabel(mean_col)
    ax.set_ylabel(disp_col)
    ax.set_title(title)
    ax.legend(loc="upper right", frameon=False, markerscale=1.8)

    if show:
        plt.show()
    if created and return_fig:
        return fig
    return ax


def champ_landscape(
    adata=None,
    *,
    partitions=None,
    best: Optional[float] = None,
    ax: Optional[plt.Axes] = None,
    figsize: tuple[float, float] = (6.4, 4.5),
    title: str = "CHAMP: modularity landscape (b, a)",
    show: Optional[bool] = None,
    return_fig: bool = False,
):
    """Scatter of CHAMP's ``(b, a)`` modularity-landscape points.

    For any fixed partition :math:`P`, Newman modularity is linear in
    the resolution parameter: :math:`Q(\\gamma; P) = a_P - \\gamma b_P`.
    CHAMP picks the partition whose line lies on the upper envelope of
    all candidates across the widest :math:`\\gamma`-range. Geometrically
    in the :math:`(b, a)` plane that is the upper convex hull; this
    plot shows all candidate partitions, marks the hull points, and
    highlights the chosen one.

    Without arguments, reads the partitions DataFrame stored at
    ``adata.uns['<champ-key>']['partitions']`` (default uns key is
    ``'champ'``; see :func:`omicverse.pp.champ`'s ``key_added``)::

        ov.pp.champ(adata)
        ov.pl.champ_landscape(adata)

    Parameters
    ----------
    adata
        AnnData on which :func:`omicverse.pp.champ` has been run.
    partitions
        Optional explicit partitions table — either the DataFrame
        returned as the third element of ``champ``'s return tuple, or
        the ``adata.uns['champ']['partitions']`` dict. Overrides the
        ``uns`` lookup.
    best
        Resolution value to highlight. If ``None``, the row in
        ``partitions`` with the largest ``gamma_range`` on the hull is
        used.
    """
    import pandas as pd

    if partitions is None:
        if adata is None:
            raise ValueError(
                "champ_landscape needs either an AnnData with "
                "`adata.uns['champ']` (produced by ov.pp.champ) or an "
                "explicit `partitions` table."
            )
        # Search uns for a champ-style payload.
        payload = None
        for key, v in (adata.uns or {}).items():
            if (isinstance(v, dict) and "partitions" in v
                    and "method" in v and "CHAMP" in str(v["method"])):
                payload = v
                break
        if payload is None:
            raise ValueError(
                "No CHAMP result found in adata.uns — run ov.pp.champ "
                "first, or pass `partitions` explicitly."
            )
        partitions = payload["partitions"]

    df = (pd.DataFrame(partitions) if isinstance(partitions, dict)
          else partitions.copy() if hasattr(partitions, "copy")
          else pd.DataFrame(partitions))

    created = ax is None
    fig = ax.figure if ax is not None else plt.figure(figsize=figsize)
    if ax is None:
        ax = fig.add_subplot(111)

    non_hull = df[~df["on_hull"]] if "on_hull" in df.columns else df.iloc[:0]
    hull = (df[df["on_hull"]].sort_values("b")
             if "on_hull" in df.columns else df.sort_values("b"))
    ax.scatter(non_hull["b"], non_hull["a"], s=18, c="#B7B1A4",
                alpha=0.6, linewidths=0, label="dominated")
    ax.plot(hull["b"], hull["a"], "-o", color=sc_color[0],
            lw=1.4, markersize=6, label="hull (admissible)")
    # Star the chosen one.
    chosen_idx = None
    if "gamma_range" in df.columns and "on_hull" in df.columns:
        hull_only = df[df["on_hull"]]
        if len(hull_only) > 0:
            chosen_idx = hull_only["gamma_range"].idxmax()
    if chosen_idx is not None:
        row = df.loc[chosen_idx]
        ax.scatter(row["b"], row["a"], s=220, marker="*",
                    color=sc_color[10], zorder=5,
                    label=f"chosen ({int(row['n_clusters'])} clusters)")

    ax.set_xlabel("b  (within-cluster degree² / (2m)²)")
    ax.set_ylabel("a  (within-cluster edge weight / 2m)")
    ax.set_title(title)
    ax.legend(loc="best", frameon=False, fontsize=9)

    if show:
        plt.show()
    if created and return_fig:
        return fig
    return ax


def neighbor_degree_histogram(
    adata,
    *,
    key: str = "connectivities",
    bins: int = 60,
    color: Optional[str] = None,
    ax: Optional[plt.Axes] = None,
    figsize: tuple[float, float] = (7.6, 3.0),
    title: Optional[str] = None,
    show: Optional[bool] = None,
    return_fig: bool = False,
):
    """Per-cell sum of connectivities from the neighbor graph.

    Reads ``adata.obsp[key]`` (default ``"connectivities"``, the standard
    key used by ``ov.pp.neighbors``).
    """
    if not hasattr(adata, "obsp") or key not in adata.obsp:
        raise ValueError(f"{key!r} not in adata.obsp — run ov.pp.neighbors first.")
    G = adata.obsp[key]
    deg = np.asarray(G.sum(axis=1)).ravel()
    color = color or sc_color[5]

    created = ax is None
    fig = ax.figure if ax is not None else plt.figure(figsize=figsize)
    if ax is None:
        ax = fig.add_subplot(111)

    ax.hist(deg, bins=bins, color=color, alpha=0.85,
            edgecolor="white", linewidth=0.3)
    ax.set_xlabel("Per-cell connectivity sum")
    ax.set_ylabel("# cells")
    nnz = getattr(G, "nnz", None)
    if title is None:
        title = (f"Neighbor-graph density  ·  nnz = {nnz:,}"
                 if nnz is not None else "Neighbor-graph density")
    ax.set_title(title)

    if show:
        plt.show()
    if created and return_fig:
        return fig
    return ax
