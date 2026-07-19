"""Ro/e — ratio of observed to expected cell numbers (tissue/condition preference).

The Ro/e statistic quantifies whether a cell cluster is *enriched* or *depleted*
in a given tissue / sample / condition relative to a random distribution.  It was
introduced by Zhang et al. 2018 (*Nature*, colorectal-cancer T cells) and Guo
et al. 2018 (*Nature Medicine*, NSCLC T cells), and is implemented in the
``Startrac`` R package (Zemin Zhang lab, ``calTissueDist(method='chisq')``).

Definition
----------
Build the cluster × sample contingency table of cell counts.  For cluster *i*
in sample *j*::

    expected(i, j) = rowsum(i) * colsum(j) / total          # χ² independence model
    Ro/e(i, j)     = observed(i, j) / expected(i, j)

``Ro/e > 1`` → the cluster is over-represented (enriched) in that sample;
``Ro/e < 1`` → under-represented (depleted); ``Ro/e ≈ 1`` → no preference.

The χ² test on the whole table yields one global p-value testing overall
cluster–sample dependence.  It is a global QC flag only — the individual Ro/e
ratios are descriptive statistics and remain interpretable regardless of the
p-value, so this implementation **always returns the full Ro/e matrix**.

Symbolic categories
-------------------
For heat-map annotation Ro/e values are bucketed into 5 symbols.  The default
``scheme='anchored'`` puts the breakpoints at the meaningful value ``Ro/e = 1``
(the neutral expectation), cleanly separating depletion from enrichment::

    '−'    Ro/e == 0
    '+/−'  0   < Ro/e < 0.2
    '+'    0.2 ≤ Ro/e ≤ 1      (depleted → neutral)
    '++'   1   < Ro/e ≤ 3      (moderately enriched)
    '+++'  Ro/e > 3            (strongly enriched)

``scheme='legacy'`` reproduces the older omicverse cutoffs (breakpoints at
0.2 / 0.8 / 1) for backwards compatibility.
"""

import pandas as pd
from scipy.stats import chi2_contingency, fisher_exact
from anndata import AnnData

from .._registry import register_function


# ---------------------------------------------------------------------------
# Symbolic enrichment categories
# ---------------------------------------------------------------------------

_ROE_SCHEMES = ("anchored", "legacy")


def _categorize_roe(x, scheme: str) -> str:
    """Map one Ro/e value to its 5-level symbol under the chosen scheme."""
    if pd.isna(x):
        return ""
    if x <= 0:
        return "−"
    if scheme == "anchored":
        # Breakpoints anchored at Ro/e = 1 (the neutral expectation).
        if x < 0.2:
            return "+/−"      # 0   < x < 0.2
        if x <= 1.0:
            return "+"        # 0.2 ≤ x ≤ 1   (depleted → neutral)
        if x <= 3.0:
            return "++"       # 1   < x ≤ 3   (moderately enriched)
        return "+++"          # x   > 3       (strongly enriched)
    # Legacy omicverse cutoffs (breakpoints 0.2 / 0.8 / 1).
    if x < 0.2:
        return "+/−"          # 0   < x < 0.2
    if x <= 0.8:
        return "+"            # 0.2 ≤ x ≤ 0.8
    if x <= 1.0:
        return "++"           # 0.8 < x ≤ 1
    return "+++"              # x   > 1


def transform_roe_values(roe: pd.DataFrame, scheme: str = "anchored") -> pd.DataFrame:
    """Convert numeric Ro/e values to symbolic enrichment categories.

    Parameters
    ----------
    roe : pandas.DataFrame
        Numeric Ro/e matrix.
    scheme : str, default='anchored'
        ``'anchored'`` — breakpoints at Ro/e = 0.2 / 1 / 3 (recommended;
        the bins are anchored at the neutral value Ro/e = 1).
        ``'legacy'`` — older omicverse breakpoints at 0.2 / 0.8 / 1.

    Returns
    -------
    pandas.DataFrame
        String matrix with symbols ``−``, ``+/−``, ``+``, ``++``, ``+++``.
    """
    if scheme not in _ROE_SCHEMES:
        raise ValueError(f"scheme must be one of {_ROE_SCHEMES}, got {scheme!r}")
    return roe.apply(lambda col: col.map(lambda x: _categorize_roe(x, scheme)))


# ---------------------------------------------------------------------------
# Core Ro/e computation
# ---------------------------------------------------------------------------


@register_function(
    aliases=["观察预期比", "roe", "observed_expected_ratio", "细胞富集分析", "组织偏好性"],
    category="utils",
    description="Ratio of observed to expected cell numbers (Ro/e) for tissue/condition preference analysis",
    examples=[
        "# Ro/e of each cell type across samples",
        "roe = ov.utils.roe(adata, sample_key='tissue', cell_type_key='celltype')",
        "# Symbolic heatmap (anchored scheme: breakpoints at 0.2 / 1 / 3)",
        "ov.utils.roe_plot_heatmap(adata, display_numbers=False)",
        "# Fix the sample (column) order",
        "roe = ov.utils.roe(adata, sample_key='tissue', cell_type_key='celltype',",
        "                   order=['Normal', 'Adjacent', 'Tumor'])",
    ],
    related=["utils.roe_plot_heatmap", "single.pySCSA", "utils.plot_cellproportion"],
)
def roe(
    adata: AnnData,
    sample_key: str,
    cell_type_key: str,
    pval_threshold: float = 0.05,
    expected_value_threshold: float = 5,
    order=None,
) -> pd.DataFrame:
    """Compute the Ro/e (observed/expected) cell-type enrichment matrix.

    Parameters
    ----------
    adata : AnnData
        Object with sample and cell-type annotations in ``.obs``.
    sample_key : str
        ``adata.obs`` column with the sample / tissue / condition labels
        (these become the Ro/e columns).
    cell_type_key : str
        ``adata.obs`` column with the cell-type / cluster labels
        (these become the Ro/e rows).
    pval_threshold : float, default=0.05
        Significance level for the *global* χ² test of cluster–sample
        independence.  Recorded as a QC flag; it does **not** gate the
        returned matrix.
    expected_value_threshold : float, default=5
        Minimum expected count below which the χ² approximation is considered
        unreliable.  For a 2×2 table the global p-value then falls back to
        Fisher's exact test; for larger tables a warning is emitted.
    order : list of str or None, default=None
        Explicit column (sample) order.  A comma-separated string is also
        accepted for backwards compatibility.  ``None`` keeps the natural
        order.  (The legacy sentinel ``'F'`` is still accepted = ``None``.)

    Returns
    -------
    pandas.DataFrame
        Ro/e matrix, cell types (rows) × samples (columns).  Also stored,
        together with the observed / expected tables and the χ² result, in
        ``adata.uns['roe']``; ``adata.uns['roe_results']`` and
        ``adata.uns['expected_values']`` are kept for backwards compatibility.
    """
    # --- contingency table: rows = cell type, cols = sample --------------------
    observed = pd.crosstab(
        index=adata.obs[cell_type_key], columns=adata.obs[sample_key]
    )
    observed.index.name = "cluster"

    # Drop all-zero rows / columns (stale categorical levels) — chi2_contingency
    # raises on a zero marginal, and Ro/e is undefined there anyway.
    nonzero_rows = observed.sum(axis=1) > 0
    nonzero_cols = observed.sum(axis=0) > 0
    if not nonzero_rows.all() or not nonzero_cols.all():
        dropped = list(observed.index[~nonzero_rows]) + list(observed.columns[~nonzero_cols])
        print(f"[Ro/e] dropping empty cell types / samples: {dropped}")
        observed = observed.loc[nonzero_rows, nonzero_cols]

    if observed.shape[0] < 2 or observed.shape[1] < 2:
        raise ValueError(
            f"Ro/e needs at least 2 cell types and 2 samples; got "
            f"{observed.shape[0]} × {observed.shape[1]} after dropping empties."
        )

    # --- optional column ordering --------------------------------------------
    if order is not None and not (isinstance(order, str) and order == "F"):
        col_order = order.split(",") if isinstance(order, str) else list(order)
        missing = [c for c in col_order if c not in observed.columns]
        if missing:
            raise ValueError(f"order contains unknown samples: {missing}")
        observed = observed[col_order]

    # --- chi-square independence model ---------------------------------------
    chi2, p, dof, expected_arr = chi2_contingency(observed)
    expected = pd.DataFrame(expected_arr, index=observed.index, columns=observed.columns)

    low_expected = bool((expected_arr < expected_value_threshold).any())
    test_used = "chi2"
    if low_expected:
        if observed.shape == (2, 2):
            _, p = fisher_exact(observed.values)
            test_used = "fisher"
            print(
                f"[Ro/e] some expected counts < {expected_value_threshold}; "
                f"global p-value from Fisher's exact test = {p:.3g}"
            )
        else:
            print(
                f"[Ro/e] some expected counts < {expected_value_threshold}; the "
                f"global χ² p-value is unreliable for this {observed.shape[0]}×"
                f"{observed.shape[1]} table. Ro/e ratios are still reported."
            )

    # --- Ro/e ratio ----------------------------------------------------------
    roe_df = observed / expected
    significant = bool(p <= pval_threshold)

    print(
        f"[Ro/e] chi2={chi2:.3f}, dof={dof}, p={p:.3g} "
        f"({'significant' if significant else 'not significant'} "
        f"at {pval_threshold}; test={test_used})"
    )

    # --- persist -------------------------------------------------------------
    adata.uns["roe"] = {
        "roe": roe_df,
        "observed": observed,
        "expected": expected,
        "chi2": float(chi2),
        "dof": int(dof),
        "pvalue": float(p),
        "test": test_used,
        "significant": significant,
        "low_expected": low_expected,
        "pval_threshold": float(pval_threshold),
    }
    # Backwards-compatible keys.
    adata.uns["roe_results"] = roe_df
    adata.uns["expected_values"] = expected

    return roe_df


# ---------------------------------------------------------------------------
# Heat-map
# ---------------------------------------------------------------------------


@register_function(
    aliases=["roe热图", "roe_plot_heatmap", "roe_heatmap", "组织偏好热图"],
    category="utils",
    description="Plot the Ro/e enrichment heatmap computed by ov.utils.roe",
    examples=[
        "ov.utils.roe(adata, sample_key='tissue', cell_type_key='celltype')",
        "ov.utils.roe_plot_heatmap(adata, display_numbers=True)",
        "ov.utils.roe_plot_heatmap(adata, display_numbers=False, scheme='anchored')",
    ],
    related=["utils.roe", "utils.transform_roe_values"],
)
def roe_plot_heatmap(
    adata: AnnData,
    display_numbers: bool = False,
    scheme: str = "anchored",
    center_value: float = 1.0,
    vmax=None,
    color_scheme: str = "cool",
    custom_colors: list = None,
    save_path: str = None,
    batch_order: list = None,
):
    """Plot the Ro/e heat-map stored in ``adata.uns`` by :func:`roe`.

    Parameters
    ----------
    adata : AnnData
        Object carrying the output of :func:`roe`.
    display_numbers : bool, default=False
        Annotate cells with the numeric Ro/e value; otherwise use the symbolic
        categories from :func:`transform_roe_values`.
    scheme : str, default='anchored'
        Symbol scheme passed to :func:`transform_roe_values` when
        ``display_numbers=False``.
    center_value : float, default=1.0
        Value the diverging colormap is centered on (Ro/e = 1 = no preference).
    vmax : float or None, default=None
        Upper colour-scale cap.  Ro/e is unbounded above; capping (e.g. at 3,
        or the 95th percentile) keeps the colour scale readable.  ``None``
        uses the data maximum.
    color_scheme : str, default='cool'
        Preset palette: ``'default'``, ``'cool'`` or ``'warm'``.
    custom_colors : list or None
        Explicit colour list overriding ``color_scheme``.
    save_path : str or None
        If given, save the figure instead of showing it.
    batch_order : list or None
        Optional row order for the displayed cell types.

    Returns
    -------
    matplotlib.axes.Axes
        The heat-map axis.
    """
    import seaborn as sns
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    if "roe" in adata.uns and isinstance(adata.uns["roe"], dict):
        roe_df = adata.uns["roe"]["roe"]
        meta = adata.uns["roe"]
        if meta["significant"]:
            title_suffix = ""
        elif meta["low_expected"]:
            title_suffix = " (global test unreliable — low expected counts)"
        else:
            title_suffix = " (global test not significant)"
    elif "roe_results" in adata.uns:           # legacy fallback
        roe_df = adata.uns["roe_results"]
        title_suffix = ""
    else:
        raise KeyError("No Ro/e results found — run ov.utils.roe(adata, ...) first.")

    if batch_order:
        roe_df = roe_df.loc[batch_order]

    color_schemes = {
        "default": ["#D73027", "#FFFFFF", "#1E682A"],
        "cool": ["#440154", "#FFFFFF", "#fde725"],
        "warm": ["#3B4CC0", "#FFFFFF", "#B40426"],
    }
    colors = custom_colors if custom_colors else color_schemes[color_scheme]
    custom_cmap = LinearSegmentedColormap.from_list("roe_cmap", colors, N=256)
    custom_cmap.set_bad(color="white")

    fig, ax = plt.subplots(figsize=(10, 7))
    if display_numbers:
        sns.heatmap(
            roe_df, annot=roe_df.round(2), cmap=custom_cmap,
            center=center_value, vmax=vmax, fmt="", ax=ax,
            cbar_kws={"label": "Ro/e"},
        )
    else:
        symbols = transform_roe_values(roe_df, scheme=scheme)
        sns.heatmap(
            roe_df, annot=symbols, cmap=custom_cmap,
            center=center_value, vmax=vmax, fmt="", ax=ax,
            cbar_kws={"label": "Ro/e"},
        )

    ax.set_title(f"Ro/e{title_suffix}")
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
    else:
        plt.show()
    return ax
