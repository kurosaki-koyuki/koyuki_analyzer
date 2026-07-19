"""Enrichment dispatcher for ``ov.protein`` — thin wrapper over ``ov.es``.

For protein-level analysis the canonical input to ``ov.es`` is either:

* the AnnData itself (per-sample scoring), or
* a ranked statistic vector from ``ov.protein.de`` (one-shot GSEA / ORA).

This module re-exposes the relevant ``ov.es`` functions under a single
``ov.protein.enrich`` entry point with the same ``method=`` selector
the user is familiar with from imputation / DE.
"""
from __future__ import annotations

from typing import Optional, Union

import numpy as np
import pandas as pd

from .._registry import register_function


@register_function(
    aliases=["protein_enrich", "enrich", "蛋白富集"],
    category="enrichment",
    description=(
        "Run an ``ov.es`` enrichment kernel on a proteomics AnnData "
        "(per-sample scoring) or on a DE result table (one-shot ORA / "
        "GSEA). ``method`` is forwarded to ``ov.es.decoupler`` — one "
        "of ``aucell``, ``gsea``, ``gsva``, ``ora``, ``ulm``, ``mlm``, "
        "``waggr``, ``zscore``, ``viper``, ``mdt``, ``udt``."
    ),
    requires={},
    produces={"obsm": ["score_<method>"]},
    auto_fix="none",
    examples=[
        "ov.protein.enrich(adata, signatures=msigdb, method='ulm')",
        "ov.protein.enrich(de_table, signatures=msigdb, method='gsea')",
    ],
)
def enrich(
    data: Union["AnnData", pd.DataFrame],
    signatures: Optional[dict] = None,
    *,
    net: Optional[pd.DataFrame] = None,
    method: str = "ulm",
    engine: str = "auto",
    **kwargs,
):
    """Enrichment on protein-level data (AnnData) or DE result (DataFrame).

    Parameters
    ----------
    data
        ``AnnData`` (samples × proteins) or a DE result ``DataFrame``
        with at least ``gene`` and one of ``t``, ``logFC``, ``P.Value``.
    signatures
        Dict mapping ``signature_name → list[gene] | dict[gene, weight]``
        (omicverse convention). Mutually exclusive with ``net``.
    net
        Long-format ``source / target / weight`` DataFrame (decoupler
        convention). Power-user escape hatch.
    method
        Which kernel to run (forwarded to ``ov.es.decoupler``).
    engine
        ``'auto'`` | ``'cpu'`` | ``'gpu'``.
    **kwargs
        Forwarded to the chosen kernel.

    Returns
    -------
    AnnData | (DataFrame, DataFrame)
        Same return shape as the underlying ``ov.es`` function.
    """
    from .. import es as _es

    # If user passes a DE table, transpose into a 1-row "pseudo-sample"
    # for the t-statistic ranking. ``ov.es.gsea`` etc. consume this fine.
    if isinstance(data, pd.DataFrame) and "gene" in data.columns:
        rank_col = next(
            (c for c in ("t", "logFC", "stat", "log2FoldChange") if c in data.columns),
            None,
        )
        if rank_col is None:
            raise ValueError(
                "DE-table input must contain a rank column (one of t, "
                "logFC, stat, log2FoldChange)."
            )
        # Build a 1-row AnnData-like DataFrame.
        score = (
            data[["gene", rank_col]]
            .dropna()
            .set_index("gene")
            .T
        )
        score.index = ["de_query"]
        data = score
    return _es.decoupler(
        data, signatures=signatures, net=net,
        method=method, engine=engine, **kwargs,
    )
