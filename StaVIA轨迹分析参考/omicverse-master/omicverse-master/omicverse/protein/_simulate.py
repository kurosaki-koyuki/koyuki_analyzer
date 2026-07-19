"""Synthetic bulk-proteomics data generator for ``ov.protein`` tutorials
and tests. Produces a realistic MaxQuant-style AnnData with planted
differential proteins, count-correlated variance, and MNAR dropouts.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from .._registry import register_function


@register_function(
    aliases=["protein_simulate_lfq", "simulate_lfq", "蛋白模拟数据"],
    category="datasets",
    description=(
        "Simulate a bulk label-free proteomics dataset as an AnnData "
        "(samples × proteins, raw intensities in ``X``). Plants a known "
        "set of differential proteins, gives each protein a peptide "
        "count with count-correlated variance (so DEqMS has signal to "
        "exploit), and injects MNAR left-censored dropouts. The "
        "ground-truth DE flag is stored in ``adata.var['is_de_true']``."
    ),
    produces={"obs": ["group"], "var": ["peptides", "is_de_true"]},
    auto_fix="none",
    examples=[
        "adata = ov.protein.simulate_lfq(seed=0)",
        "adata = ov.protein.simulate_lfq(n_proteins=3000, n_per_group=8)",
    ],
)
def simulate_lfq(
    *,
    n_proteins: int = 2000,
    n_per_group: int = 6,
    n_groups: int = 2,
    prop_de: float = 0.12,
    effect_size: float = 1.0,
    missing_frac: float = 0.12,
    platform: str = "lfq",
    peptide_level: bool = False,
    n_peptides_per_protein: int = 4,
    seed: Optional[int] = 0,
):
    """Simulate a bulk proteomics AnnData.

    Parameters
    ----------
    n_proteins
        Number of proteins (``var``).
    n_per_group
        Biological replicates per group.
    n_groups
        Number of groups (the first two are the test contrast).
    prop_de
        Fraction of proteins that are truly differential.
    effect_size
        Log2 fold-change magnitude for the planted DE proteins.
    missing_frac
        Target overall fraction of MNAR (left-censored) missing values.
        Ignored when ``platform='olink'`` (NPX has negligible dropout).
    platform
        ``'lfq'`` (default) — raw linear intensities, MNAR dropout, a
        per-protein peptide count. ``'olink'`` — NPX-style values
        (already log2 scale, no dropout, no peptide count).
    peptide_level
        If ``True``, return a **peptide-level** AnnData
        (samples × peptides) with a ``var['Protein']`` column mapping
        each peptide to its parent protein — feed this to
        :func:`omicverse.protein.summarize`.
    n_peptides_per_protein
        Peptides per protein when ``peptide_level=True``.
    seed
        RNG seed.

    Returns
    -------
    AnnData
        ``obs['group']`` = group labels; ``var['is_de_true']`` =
        ground-truth DE flag. For ``platform='lfq'`` protein-level,
        ``var['peptides']`` holds the peptide count; ``X`` is raw
        intensities (NaN = missing). For ``platform='olink'`` ``X`` is
        NPX (log2). For ``peptide_level=True`` ``var['Protein']`` maps
        peptides → proteins.
    """
    from anndata import AnnData

    rng = np.random.default_rng(seed)
    n_samples = n_per_group * n_groups
    is_olink = platform.lower() == "olink"

    base_mean, base_sd = (0.0, 2.0) if is_olink else (20.0, 1.6)
    base = rng.normal(base_mean, base_sd, n_proteins)
    count = rng.integers(1, 25, n_proteins).astype(float)
    sigma = (0.3 + 0.4 * rng.uniform(size=n_proteins)) if is_olink \
        else (0.35 + 0.9 / np.sqrt(count))

    is_de = rng.uniform(size=n_proteins) < prop_de
    delta = np.zeros(n_proteins)
    delta[is_de] = rng.choice([-1, 1], size=int(is_de.sum())) * effect_size

    group_labels = np.repeat([f"group{g}" for g in range(n_groups)], n_per_group)

    def _draw_block(means_per_protein):
        """Draw an (n_samples × n_proteins) block from the group means."""
        block = np.zeros((n_samples, n_proteins))
        for g in range(n_groups):
            mean_g = base + means_per_protein + (delta if g == 1 else 0.0)
            block[g * n_per_group:(g + 1) * n_per_group, :] = rng.normal(
                mean_g[None, :], sigma[None, :], (n_per_group, n_proteins),
            )
        return block

    obs = pd.DataFrame({"group": group_labels},
                       index=[f"S{i:02d}" for i in range(n_samples)])

    if peptide_level:
        # Each peptide is its parent protein's signal + a peptide offset.
        # Per-protein peptide count varies in [1, n_peptides_per_protein]
        # so a count-aware DE method (DEqMS) has real signal to model.
        per_protein_n = rng.integers(
            1, max(n_peptides_per_protein, 2) + 1, n_proteins,
        )
        cols, proteins, pep_de = [], [], []
        for p in range(n_proteins):
            for k in range(int(per_protein_n[p])):
                offset = rng.normal(0.0, 0.5)
                pep_signal = _draw_block(np.full(n_proteins, 0.0))[:, p] + offset
                cols.append(pep_signal)
                proteins.append(f"prot_{p:04d}")
                pep_de.append(bool(is_de[p]))
        Xp = np.column_stack(cols)
        if not is_olink:
            Xp = 2.0 ** Xp
        var = pd.DataFrame(
            {"Protein": proteins, "is_de_true": pep_de},
            index=[f"pep_{i:05d}" for i in range(Xp.shape[1])],
        )
        adata = AnnData(X=Xp, obs=obs, var=var)
        adata.uns["source"] = f"simulate_lfq[{platform},peptide]"
        return adata

    X = _draw_block(np.zeros(n_proteins))
    if not is_olink:
        X = 2.0 ** X
        if missing_frac > 0:
            thr = np.quantile(X, min(missing_frac * 1.6, 0.5))
            p_miss = np.clip(np.exp(-(X / thr) ** 2), 0.0, 1.0)
            X[rng.uniform(size=X.shape) < p_miss] = np.nan

    var_cols = {
        "Gene_names": [f"GENE{i:04d}" for i in range(n_proteins)],
        "is_de_true": is_de,
    }
    if not is_olink:
        var_cols["peptides"] = count.astype(int)
    var = pd.DataFrame(var_cols,
                       index=[f"prot_{i:04d}" for i in range(n_proteins)])
    adata = AnnData(X=X, obs=obs, var=var)
    adata.uns["source"] = f"simulate_lfq[{platform}]"
    return adata
