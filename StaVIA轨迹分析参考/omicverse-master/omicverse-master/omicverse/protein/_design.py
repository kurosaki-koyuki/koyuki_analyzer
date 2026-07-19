"""Study-design helpers for ``ov.protein`` — sample-size / power
calculation and contrast-matrix construction, wrapping :mod:`pymsstats`.
"""
from __future__ import annotations

from typing import Optional, Sequence, Union

import numpy as np
import pandas as pd

from .._registry import register_function


@register_function(
    aliases=["protein_sample_size", "sample_size", "样本量计算", "功效分析"],
    category="analysis",
    description=(
        "Sample-size / statistical-power calculation for a proteomics "
        "experiment, wrapping ``pymsstats.design_sample_size`` "
        "(MSstats ``designSampleSize``). Given a processed protein-level "
        "AnnData (post-summarization), returns the minimum number of "
        "biological replicates per group needed to detect a panel of "
        "desired fold-changes at the requested FDR and power."
    ),
    requires={},
    produces={"uns": ["protein_sample_size"]},
    auto_fix="none",
    examples=[
        "tbl = ov.protein.sample_size(adata, group='treatment', desired_fc=(1.25, 2.0))",
    ],
)
def sample_size(
    adata,
    group: Union[str, np.ndarray],
    *,
    desired_fc: Sequence[float] = (1.25, 1.5, 1.75, 2.0),
    fdr: float = 0.05,
    power: float = 0.8,
    **kwargs,
) -> pd.DataFrame:
    """Minimum replicates per group for a target fold-change panel.

    Parameters
    ----------
    adata
        Protein-level AnnData (post-``summarize`` / log2-normalized).
    group
        Sample-group column in ``adata.obs`` (or a labels array).
    desired_fc
        Fold-changes to power for. R default range is ``(1.25, …, 2.0)``.
    fdr
        Target false-discovery rate.
    power
        Target statistical power.
    **kwargs
        Forwarded to ``pymsstats.design_sample_size``.

    Returns
    -------
    pandas.DataFrame
        One row per desired fold-change with the minimum N.
    """
    try:
        import pymsstats
    except ImportError as exc:
        raise ImportError(
            "ov.protein.sample_size requires pymsstats: `pip install pymsstats`."
        ) from exc

    if isinstance(group, str):
        labels = adata.obs[group].astype(str).to_numpy()
    else:
        labels = np.asarray(group)

    # Build the MSstats-style processed long table the function expects.
    long_rows = pd.DataFrame(
        adata.X.astype(float),
        index=adata.obs_names.astype(str),
        columns=adata.var_names.astype(str),
    )
    long_rows["__group__"] = labels
    melted = long_rows.melt(
        id_vars="__group__", var_name="PROTEIN", value_name="LogIntensities",
        ignore_index=False,
    ).rename(columns={"__group__": "GROUP"})
    melted["RUN"] = melted.index.astype(str)
    melted["SUBJECT"] = melted.index.astype(str)

    result = pymsstats.design_sample_size(
        melted, desired_fc=tuple(desired_fc), fdr=fdr, power=power,
        protein_col="PROTEIN", group_col="GROUP",
        abundance_col="LogIntensities", subject_col="SUBJECT",
        **kwargs,
    )
    adata.uns.setdefault("protein", {})["sample_size"] = result
    return result


@register_function(
    aliases=["protein_contrast_matrix", "contrast_matrix"],
    category="analysis",
    description=(
        "Build a contrast matrix for a multi-group proteomics design, "
        "wrapping ``pymsstats.msstats_contrast_matrix`` "
        "(MSstats ``MSstatsContrastMatrix``). Accepts a string spec "
        "(``'groupB-groupA'``), ``'pairwise'``, a list of pairs, or a "
        "ready-made ndarray."
    ),
    examples=[
        "C = ov.protein.contrast_matrix('treated-control', ['control','treated'])",
        "C = ov.protein.contrast_matrix('pairwise', ['A','B','C'])",
    ],
)
def contrast_matrix(
    contrasts: Union[str, Sequence, np.ndarray],
    conditions: Sequence[str],
) -> pd.DataFrame:
    """Construct an MSstats-style contrast matrix.

    Parameters
    ----------
    contrasts
        Contrast spec — ``'groupB-groupA'``, ``'pairwise'``, a list of
        ``(a, b)`` pairs, or an ndarray (returned as-is).
    conditions
        Ordered list of condition / group names (the columns of the
        contrast matrix).

    Returns
    -------
    pandas.DataFrame
        Contrast matrix, rows = contrasts, columns = conditions.
    """
    try:
        import pymsstats
    except ImportError as exc:
        raise ImportError(
            "ov.protein.contrast_matrix requires pymsstats: "
            "`pip install pymsstats`."
        ) from exc
    return pymsstats.msstats_contrast_matrix(contrasts, list(conditions))
