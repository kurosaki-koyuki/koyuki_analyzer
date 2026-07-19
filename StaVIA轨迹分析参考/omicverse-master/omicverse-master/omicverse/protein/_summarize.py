"""Peptide → protein summarization for ``ov.protein``.

Bulk LC-MS/MS search engines often report **peptide / PSM-level**
intensities; the downstream DE machinery (DEqMS, proDA, MSstats) works
on **protein-level** matrices. :func:`summarize` collapses a
peptide-level AnnData into a protein-level one, dispatching to the
canonical summarization algorithms from the standalone backends:

* ``'median'``          — per-protein median across peptides (``pydeqms.median_summary``)
* ``'median_sweeping'`` — TMT median sweeping (``pydeqms.median_sweeping``)
* ``'medpolish'``       — Tukey median polish (``pydeqms.medpolish_summary``)
* ``'tmp'``             — MSstats Tukey-median-polish (``pymsstats.msstats_summarize``)
* ``'linear'``          — MSstats linear-model summarization (``pymsstats.linear_summarize``)
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .._registry import register_function


_VALID_METHODS = {"median", "median_sweeping", "medpolish", "tmp", "linear"}


@register_function(
    aliases=["protein_summarize", "summarize", "肽段汇总", "蛋白汇总"],
    category="preprocessing",
    description=(
        "Collapse a peptide / PSM-level proteomics AnnData into a "
        "protein-level AnnData. ``method`` selects the summarization "
        "algorithm: ``'median'`` / ``'median_sweeping'`` / ``'medpolish'`` "
        "(DEqMS ports via pydeqms) or ``'tmp'`` / ``'linear'`` (MSstats "
        "ports via pymsstats). The peptide→protein map is read from "
        "``adata.var[protein_col]``."
    ),
    requires={"var": ["protein_col"]},
    produces={"uns": ["protein_summarize"]},
    auto_fix="none",
    examples=[
        "prot_adata = ov.protein.summarize(pep_adata, protein_col='Protein', method='medpolish')",
        "prot_adata = ov.protein.summarize(pep_adata, protein_col='Protein', method='tmp')",
    ],
)
def summarize(
    adata,
    *,
    protein_col: str = "Protein",
    method: str = "medpolish",
    log2: bool = True,
    **kwargs,
):
    """Summarize a peptide-level AnnData to protein level.

    Parameters
    ----------
    adata
        Peptide-level AnnData — ``X`` = samples × peptides, with a
        ``adata.var[protein_col]`` column mapping each peptide to its
        parent protein.
    protein_col
        Column in ``adata.var`` holding the parent-protein ID.
    method
        Summarization algorithm — see the function description.
    log2
        If ``True`` (default) the input is raw linear intensity and is
        log2-transformed before summarization — all summarizers (DEqMS
        and MSstats) collapse on the log scale. Set ``False`` when the
        matrix is already on log scale (e.g. Olink NPX).
    **kwargs
        Forwarded to the backend summarizer.

    Returns
    -------
    AnnData
        Protein-level AnnData — ``X`` = samples × proteins. ``obs`` is
        copied from the input; ``var`` is the unique protein index.
    """
    from anndata import AnnData

    key = method.lower().strip()
    if key not in _VALID_METHODS:
        raise ValueError(
            f"method must be one of {sorted(_VALID_METHODS)}, got {method!r}"
        )
    if protein_col not in adata.var.columns:
        raise KeyError(
            f"protein_col {protein_col!r} not in adata.var columns: "
            f"{list(adata.var.columns)}"
        )

    # peptide × sample matrix (R convention for the backends).
    pep_by_sample = pd.DataFrame(
        adata.X.T.astype(float),
        index=adata.var_names.astype(str),
        columns=adata.obs_names.astype(str),
    )
    # All summarizers (DEqMS and MSstats) collapse on the LOG2 scale —
    # summarising raw linear intensities inflates the protein-level
    # variance by orders of magnitude. ``log2=True`` (default) means the
    # input is raw intensity and should be logged first; ``log2=False``
    # means the matrix is already on log scale (e.g. Olink NPX).
    if log2:
        with np.errstate(invalid="ignore", divide="ignore"):
            pep_by_sample = np.log2(pep_by_sample)
    proteins = adata.var[protein_col].astype(str).to_numpy()

    if key in ("median", "median_sweeping", "medpolish"):
        try:
            import pydeqms
        except ImportError as exc:
            raise ImportError(
                f"method={key!r} requires pydeqms: `pip install pydeqms`."
            ) from exc
        # pydeqms summarizers take a peptide DataFrame with a protein
        # column + sample columns.
        pep_df = pep_by_sample.copy()
        pep_df.insert(0, protein_col, proteins)
        fn = {
            "median":          pydeqms.median_summary,
            "median_sweeping": pydeqms.median_sweeping,
            "medpolish":       pydeqms.medpolish_summary,
        }[key]
        prot_df = fn(pep_df, protein_col=protein_col,
                     sample_cols=list(pep_by_sample.columns), **kwargs)
        # ``medpolish`` / ``median_sweeping`` collapse to *column effects*
        # — for a single-peptide protein those effects are identically
        # zero (faithful to R DEqMS, which assumes ≥2-peptide filtering
        # upstream). Replace such degenerate rows with the plain median
        # summary so they carry real signal instead of a zero vector.
        if key in ("medpolish", "median_sweeping"):
            pep_per_protein = pd.Series(proteins).value_counts()
            singletons = pep_per_protein[pep_per_protein < 2].index
            singletons = [p for p in singletons if p in prot_df.index]
            if singletons:
                med = pydeqms.median_summary(
                    pep_df, protein_col=protein_col,
                    sample_cols=list(pep_by_sample.columns),
                )
                prot_df.loc[singletons, :] = med.reindex(
                    index=singletons, columns=prot_df.columns,
                )
    elif key in ("tmp", "linear"):
        try:
            import pymsstats
        except ImportError as exc:
            raise ImportError(
                f"method={key!r} requires pymsstats: `pip install pymsstats`."
            ) from exc
        # pymsstats summarizers consume a long-format DataFrame:
        # PROTEIN / RUN / FEATURE / ABUNDANCE.
        long_rows = pep_by_sample.copy()
        long_rows.insert(0, "FEATURE", long_rows.index.astype(str))
        long_rows.insert(0, "PROTEIN", proteins)
        # pep_by_sample is already log2 (handled at the top).
        long_df = long_rows.melt(
            id_vars=["PROTEIN", "FEATURE"],
            var_name="RUN", value_name="ABUNDANCE",
        )
        fn = (pymsstats.msstats_summarize if key == "tmp"
              else pymsstats.linear_summarize)
        summ = fn(long_df, **kwargs)
        # pymsstats returns long Protein / RUN / LogIntensities — pivot wide.
        prot_key = next(
            (c for c in ("Protein", "PROTEIN", "ProteinName")
             if c in summ.columns),
            summ.columns[0],
        )
        run_key = next(
            (c for c in ("RUN", "Run", "run") if c in summ.columns), "RUN",
        )
        val_col = next(
            (c for c in ("LogIntensities", "ABUNDANCE", "Abundance")
             if c in summ.columns),
            summ.columns[2],
        )
        prot_df = summ.pivot_table(
            index=prot_key, columns=run_key, values=val_col, aggfunc="first",
        )
    else:  # pragma: no cover
        raise ValueError(key)

    # prot_df is proteins × samples. Back to samples × proteins for AnnData.
    prot_df = prot_df.reindex(columns=pep_by_sample.columns)
    X = prot_df.to_numpy(dtype=float).T
    out = AnnData(
        X=X,
        obs=adata.obs.copy(),
        var=pd.DataFrame(index=pd.Index(prot_df.index.astype(str), name="protein")),
    )
    out.uns["protein_summarize"] = {"method": key, "n_peptides_in": adata.n_vars}
    out.uns["source"] = adata.uns.get("source", "unknown")
    return out
