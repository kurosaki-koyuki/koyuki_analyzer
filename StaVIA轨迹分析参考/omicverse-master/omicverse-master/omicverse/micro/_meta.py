"""Multi-cohort 16S meta-analysis utilities.

Two APIs:

- :func:`combine_studies` — stitch a list of AnnDatas (one per study) into a
  single AnnData with a shared feature axis, an ``obs['study']`` label, and
  zero-filled cells for taxa absent from a given study. This is the
  "mega-analysis" input — run regular DA on it with ``study`` as a batch
  covariate.

- :func:`meta_da` — run per-study DA (``wilcoxon`` / ``deseq2`` / ``ancombc``)
  first, then combine the per-study effect estimates by inverse-variance
  weighted random-effects meta-analysis (DerSimonian-Laird). Produces a
  single-table verdict with combined log-fold-change, z-statistic, p,
  Benjamini-Hochberg FDR, plus Cochran's Q / I² heterogeneity diagnostics.

Why both? Nearing *et al.* 2022 (*Nat. Commun.* 13, 342) showed that
*single-cohort* 16S DA methods disagree noticeably across datasets;
pooling effect sizes from ≥3 independent cohorts is the pragmatic cure
and is the standard operating procedure for published 16S meta-analyses
(Thomas *et al.* 2019, Wirbel *et al.* 2019).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd
from scipy import sparse

try:
    import anndata as ad
except ImportError as exc:  # pragma: no cover
    raise ImportError("anndata is required for ov.micro._meta") from exc

from .._registry import register_function
from ._da import DA, _bh_fdr
from ._pp import collapse_taxa


# ---------------------------------------------------------------------------
# combine_studies
# ---------------------------------------------------------------------------


@register_function(
    aliases=["combine_studies", "concat_studies", "meta_combine"],
    category="microbiome",
    description="Concatenate a list of 16S AnnDatas into one cross-cohort table with a shared feature axis (union of taxa), an obs['study'] label, and zero-fill for absent taxa.",
    examples=[
        "adata_all = ov.micro.combine_studies([adata_A, adata_B, adata_C], study_names=['A','B','C'], rank='genus')",
    ],
    related=["micro.meta_da", "micro.collapse_taxa"],
)
def combine_studies(
    studies: Sequence["ad.AnnData"],
    study_names: Optional[Sequence[str]] = None,
    rank: Optional[str] = "genus",
    study_key: str = "study",
    min_prevalence: float = 0.0,
) -> "ad.AnnData":
    """Stitch a list of per-study AnnDatas into a single cross-cohort table.

    Parameters
    ----------
    studies
        List of per-study AnnData objects (samples × ASVs or pre-collapsed
        genera). Each must already carry taxonomy columns in ``var`` if a
        ``rank`` other than None is requested.
    study_names
        Optional list aligned with ``studies`` to label each cohort. Default:
        ``['study_0', 'study_1', …]``.
    rank
        Collapse each study to this taxonomic rank before concatenating
        (so feature labels align across studies). Pass ``None`` to skip
        collapsing — only sensible when all studies already share the
        same ASV ids.
    study_key
        Column name to write the per-sample study label into.
    min_prevalence
        Optional per-study prevalence filter applied *before* union. A
        taxon has to appear in >= this fraction of samples in at least
        one study to survive.

    Returns
    -------
    AnnData
        Shape ``(Σn_samples, n_union_features)``. The ``obs`` carries the
        original per-study metadata (inner join on columns shared by all
        studies) plus ``obs[study_key]``. ``var`` carries the union of
        feature names (no taxonomy column — the rank collapse already
        flattened that). ``X`` is a sparse CSR of ``int64`` counts;
        features absent from a given study are zero.
    """
    if not studies:
        raise ValueError("`studies` is empty.")

    if study_names is None:
        study_names = [f"study_{i}" for i in range(len(studies))]
    if len(study_names) != len(studies):
        raise ValueError(
            f"study_names length {len(study_names)} != "
            f"studies length {len(studies)}."
        )

    # Per-study collapse to shared rank.
    per_study: List["ad.AnnData"] = []
    for a, name in zip(studies, study_names):
        if rank is not None:
            a_c = collapse_taxa(a, rank=rank)
        else:
            a_c = a.copy()
        if min_prevalence > 0:
            X = _dense(a_c.X)
            prev = (X > 0).sum(axis=0) / X.shape[0]
            keep = prev >= min_prevalence
            a_c = a_c[:, keep].copy()
        a_c.obs = a_c.obs.copy()
        a_c.obs[study_key] = str(name)
        per_study.append(a_c)

    # Union of feature names (preserve first-seen order for stable layout).
    seen: Dict[str, int] = {}
    for a in per_study:
        for f in a.var_names:
            if f not in seen:
                seen[f] = len(seen)
    features = np.asarray(list(seen.keys()))
    n_feat = len(features)

    # Build the concatenated count matrix by re-indexing each study onto the
    # union feature axis.
    blocks: List[sparse.csr_matrix] = []
    obs_blocks: List[pd.DataFrame] = []
    for a in per_study:
        X = _dense(a.X).astype(np.int64)
        idx = np.array([seen[f] for f in a.var_names], dtype=np.int64)
        # Scatter the original columns into the union grid.
        aligned = np.zeros((X.shape[0], n_feat), dtype=np.int64)
        aligned[:, idx] = X
        blocks.append(sparse.csr_matrix(aligned))
        obs_blocks.append(a.obs.copy())

    X_full = sparse.vstack(blocks, format="csr")
    obs_full = pd.concat(obs_blocks, axis=0, join="inner")
    obs_full.index = pd.Index([f"{s}__{i}" for s, i in zip(
        obs_full[study_key].astype(str), obs_full.index.astype(str)
    )], name="sample")

    var_full = pd.DataFrame(index=pd.Index(features, name="feature"))

    adata_all = ad.AnnData(X=X_full, obs=obs_full, var=var_full)
    adata_all.uns["micro"] = {
        "meta": {
            "n_studies": len(studies),
            "study_names": list(map(str, study_names)),
            "rank": rank,
            "min_prevalence": min_prevalence,
        }
    }
    return adata_all


def _dense(X) -> np.ndarray:
    if sparse.issparse(X):
        return np.asarray(X.toarray())
    return np.asarray(X)


# ---------------------------------------------------------------------------
# meta_da — per-study DA + random-effects combine
# ---------------------------------------------------------------------------


_METHOD_EFFECT_COL = {
    # DA method → (effect column, SE column). Missing SE forces wilcoxon's
    # "normalise by the observed variance among studies" fallback.
    "wilcoxon": ("log2FC", None),
    "deseq2":   ("log2FC", "log2FC_se"),
    "ancombc":  ("lfc",    "se"),
}


@register_function(
    aliases=["meta_da", "meta_analysis_da", "meta_differential_abundance"],
    category="microbiome",
    description="Cross-cohort random-effects meta-analysis of differential abundance — run DA on each study, then combine per-feature effect sizes by inverse-variance weighting (DerSimonian-Laird) with Cochran's Q / I² heterogeneity.",
    examples=[
        "ov.micro.meta_da([adata_A, adata_B, adata_C], group_key='disease', method='deseq2')",
    ],
    related=["micro.DA", "micro.combine_studies"],
)
def meta_da(
    studies: Sequence["ad.AnnData"],
    group_key: str,
    group_a: Optional[str] = None,
    group_b: Optional[str] = None,
    method: str = "deseq2",
    rank: Optional[str] = "genus",
    min_prevalence: float = 0.1,
    combine: str = "random_effects",
    study_names: Optional[Sequence[str]] = None,
    **method_kwargs,
) -> pd.DataFrame:
    """Per-study DA + inverse-variance meta-analysis.

    Parameters
    ----------
    studies
        List of per-study AnnData objects.
    group_key, group_a, group_b
        Same semantics as :meth:`ov.micro.DA.wilcoxon` /
        :meth:`DA.deseq2` / :meth:`DA.ancombc`. If ``group_a`` / ``group_b``
        are omitted, the two sorted unique values of ``group_key`` in the
        *first* study are used (and re-used for every study).
    method
        ``'wilcoxon'``, ``'deseq2'``, or ``'ancombc'``. The per-study
        effect sizes must be on a log-fold-change scale; Wilcoxon is
        supported but its reported log2FC has no standard-error, so
        Wilcoxon meta-DA uses the *empirical* between-study SE to weight
        (i.e. every study gets unit weight pre-τ² — still useful as a
        sanity check).
    rank
        Collapse to this taxonomic rank in every study before DA, so
        features align across cohorts. ``None`` assumes the studies
        already share the same feature ids.
    min_prevalence
        Passed through to each per-study DA call.
    combine
        ``'random_effects'`` (default; DerSimonian-Laird τ²) or
        ``'fixed_effects'``.
    study_names
        Labels for the per-study result columns; defaults to
        ``['study_0', 'study_1', …]``.
    **method_kwargs
        Extra kwargs forwarded to the underlying DA call (e.g.
        ``pseudocount=0.5`` for ancombc).

    Returns
    -------
    DataFrame indexed by feature with columns:

    - ``combined_lfc`` — meta-analytic log2 fold-change estimate
    - ``combined_se`` — standard error of the combined estimate
    - ``z`` — Wald z-score (``combined_lfc / combined_se``)
    - ``p_value`` / ``fdr_bh`` — two-sided p + BH-FDR
    - ``n_studies`` — number of cohorts in which the feature was tested
    - ``Q`` — Cochran's Q statistic of between-study heterogeneity
    - ``I2`` — I² heterogeneity (0 → homogeneous, > 75% → high)
    - ``tau2`` — between-study variance (random-effects only)
    - per-study columns ``lfc_<study>`` and ``se_<study>`` for traceability
    """
    if not studies:
        raise ValueError("`studies` is empty.")
    if method not in _METHOD_EFFECT_COL:
        raise ValueError(
            f"method={method!r} not one of {sorted(_METHOD_EFFECT_COL)}"
        )
    if combine not in ("random_effects", "fixed_effects"):
        raise ValueError(
            f"combine={combine!r} must be 'random_effects' or 'fixed_effects'"
        )

    if study_names is None:
        study_names = [f"study_{i}" for i in range(len(studies))]

    # Resolve group_a / group_b from the first study if unspecified.
    if group_a is None or group_b is None:
        vals = sorted(studies[0].obs[group_key].dropna().unique().tolist())
        group_a = group_a or vals[0]
        group_b = group_b or vals[1]

    effect_col, se_col_name = _METHOD_EFFECT_COL[method]

    # Per-study DA — collect (study_name, lfc Series, se Series).
    per_study_lfc: Dict[str, pd.Series] = {}
    per_study_se:  Dict[str, pd.Series] = {}
    for study, name in zip(studies, study_names):
        a = collapse_taxa(study, rank=rank) if rank is not None else study
        da = DA(a)
        if method == "wilcoxon":
            res = da.wilcoxon(
                group_key=group_key, group_a=group_a, group_b=group_b,
                min_prevalence=min_prevalence, **method_kwargs,
            )
            lfc_col = f"log2FC({group_b}/{group_a})"
            lfc = res.set_index("feature")[lfc_col]
            # No SE — use a flat unit SE; random-effects τ² will dominate.
            se = pd.Series(1.0, index=lfc.index)
        elif method == "deseq2":
            res = da.deseq2(
                group_key=group_key, group_a=group_a, group_b=group_b,
                min_prevalence=min_prevalence, **method_kwargs,
            )
            lfc_col = f"log2FC({group_b}/{group_a})"
            lfc = res.set_index("feature")[lfc_col]
            se = res.set_index("feature")["log2FC_se"]
        elif method == "ancombc":
            res = da.ancombc(
                group_key=group_key,
                min_prevalence=min_prevalence, **method_kwargs,
            )
            lfc = res.set_index("feature")["lfc"]
            se = res.set_index("feature")["se"]
        per_study_lfc[name] = lfc
        per_study_se[name]  = se

    # Align on feature union.
    feats: List[str] = []
    seen: set = set()
    for s in per_study_lfc.values():
        for f in s.index:
            if f not in seen:
                seen.add(f)
                feats.append(f)

    lfc_mat = pd.DataFrame(
        {name: per_study_lfc[name].reindex(feats) for name in study_names},
        index=feats,
    )
    se_mat = pd.DataFrame(
        {name: per_study_se[name].reindex(feats) for name in study_names},
        index=feats,
    )

    # Meta-analytic combine — per-row.
    out_rows: List[dict] = []
    for f in feats:
        theta = lfc_mat.loc[f].values.astype(float)
        se    = se_mat.loc[f].values.astype(float)
        mask = np.isfinite(theta) & np.isfinite(se) & (se > 0)
        k = int(mask.sum())
        if k < 2:
            combined_lfc = float(theta[mask].mean()) if k == 1 else np.nan
            combined_se  = float(se[mask].mean())    if k == 1 else np.nan
            Q, I2, tau2 = np.nan, np.nan, np.nan
        else:
            t = theta[mask]
            s = se[mask]
            w_fe = 1.0 / (s ** 2)
            theta_fe = (w_fe * t).sum() / w_fe.sum()
            Q = float(((t - theta_fe) ** 2 * w_fe).sum())
            df = k - 1
            c = w_fe.sum() - (w_fe ** 2).sum() / w_fe.sum()
            tau2 = max(0.0, (Q - df) / c) if c > 0 else 0.0
            I2 = max(0.0, (Q - df) / Q) if Q > 0 else 0.0

            if combine == "fixed_effects" or tau2 == 0.0:
                w = w_fe
            else:
                w = 1.0 / (s ** 2 + tau2)
            combined_lfc = float((w * t).sum() / w.sum())
            combined_se  = float(np.sqrt(1.0 / w.sum()))
        row = {
            "feature": f,
            "combined_lfc": combined_lfc,
            "combined_se":  combined_se,
            "n_studies":    k,
            "Q":            Q,
            "I2":           I2,
            "tau2":         tau2,
        }
        # Copy per-study columns for traceability.
        for name in study_names:
            row[f"lfc_{name}"] = lfc_mat.at[f, name]
            row[f"se_{name}"]  = se_mat.at[f, name]
        out_rows.append(row)

    out = pd.DataFrame(out_rows)
    # Wald z + two-sided p + BH.
    from scipy.stats import norm
    valid = np.isfinite(out["combined_se"]) & (out["combined_se"] > 0)
    z = np.full(len(out), np.nan)
    z[valid] = out.loc[valid, "combined_lfc"] / out.loc[valid, "combined_se"]
    out["z"] = z
    p = np.full(len(out), np.nan)
    p[valid] = 2.0 * (1.0 - norm.cdf(np.abs(z[valid])))
    out["p_value"] = p
    out["fdr_bh"]  = np.nan
    if valid.any():
        out.loc[valid, "fdr_bh"] = _bh_fdr(out.loc[valid, "p_value"].values)
    return out.sort_values("p_value").reset_index(drop=True)
