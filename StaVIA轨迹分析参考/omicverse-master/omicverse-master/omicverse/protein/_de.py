"""Differential-expression dispatcher for ``ov.protein``.

Exposes ``ov.protein.de(adata, group, method=...)`` with one of six
backends:

* ``'deqms'`` — peptide-count-aware moderated t (via :mod:`pydeqms`)
* ``'limma'`` — Smyth 2004 empirical-Bayes moderated t
  (:func:`pydeqms.ebayes`, no count adjustment)
* ``'proda'`` — MNAR probabilistic DE (via :mod:`pyproda`, optional)
* ``'wilcoxon'`` — Mann-Whitney U (NaN-tolerant per-protein)
* ``'welch_t'`` — Welch t-test (unequal variances, NaN-tolerant)
* ``'olink_lmer'`` — Olink-style per-protein LMM via statsmodels
  (optional)

Returns a tidy ``pandas.DataFrame`` with columns
``gene``, ``logFC``, ``AveExpr``, ``t``, ``P.Value``, ``adj.P.Val``
(plus ``count``, ``sca.*`` for DEqMS; ``rho``, ``zeta`` for proDA).
"""
from __future__ import annotations

from typing import Optional, Union

import numpy as np
import pandas as pd

from .._registry import register_function


_VALID_METHODS = {
    "deqms", "limma", "proda",
    "wilcoxon", "welch_t", "ttest", "t-test",
    "olink_lmer",
    "anova", "kruskal",        # multi-group (>2)
}
_MULTIGROUP_METHODS = {"anova", "kruskal"}


@register_function(
    aliases=["protein_de", "de", "蛋白差异分析", "蛋白DE"],
    category="analysis",
    description=(
        "Differential-expression dispatcher for proteomics AnnData. "
        "``method`` selects: ``'deqms'`` (peptide-count moderated t, "
        "via pydeqms), ``'limma'`` (Smyth 2004 moderated t, no count), "
        "``'proda'`` (MNAR probabilistic DE, via pyproda), "
        "``'wilcoxon'`` / ``'welch_t'`` (per-protein non-parametric / "
        "parametric two-group test), ``'olink_lmer'`` (per-protein "
        "linear mixed model via statsmodels), or the multi-group omnibus "
        "tests ``'anova'`` / ``'kruskal'`` (>2 groups). The first "
        "argument after ``adata`` is ``group`` — either a column in "
        "``adata.obs`` (string) or an explicit (n_samples,) labels array."
    ),
    requires={"obs": ["group"]},
    produces={"uns": ["protein_de"]},
    auto_fix="none",
    examples=[
        "ov.protein.de(adata, group='treatment', method='deqms', count_var='peptides')",
        "ov.protein.de(adata, group='treatment', method='limma')",
        "ov.protein.de(adata, group='treatment', method='wilcoxon')",
        "ov.protein.de(adata, group='treatment', method='proda')",
    ],
)
def de(
    adata,
    group: Union[str, np.ndarray, pd.Series],
    *,
    method: str = "deqms",
    reference: Optional[str] = None,
    count_var: str = "peptides",
    fit_method: str = "loess",
    **kwargs,
) -> pd.DataFrame:
    """Differential-expression dispatch.

    Parameters
    ----------
    adata
        ``ov.protein`` AnnData (samples × proteins). ``X`` should be on
        log2 scale (call ``ov.protein.normalize(adata, log2=True)`` first).
    group
        Sample-group assignment. Either a column name in ``adata.obs`` or
        an explicit (n_samples,) array of labels.
    method
        Algorithm selector — one of the seven above. ``'ttest'`` and
        ``'t-test'`` are aliases for ``'welch_t'``.
    reference
        Optional reference group name; the test reports ``other - reference``
        log2 fold-change. Defaults to the first sorted unique group.
    count_var
        For ``method='deqms'``: the column in ``adata.var`` holding the
        per-protein peptide / PSM count. Falls back to 1 (no count
        weighting) if the column is missing.
    fit_method
        For ``method='deqms'``: ``'loess'`` | ``'nls'`` | ``'spline'``.
    **kwargs
        Forwarded to the backend.

    Returns
    -------
    pandas.DataFrame
        Result table, columns vary by ``method``; always includes
        ``gene``, ``logFC``, ``P.Value``, ``adj.P.Val``.
    """
    key = method.lower().strip()
    if key in ("t-test", "ttest"):
        key = "welch_t"
    if key not in _VALID_METHODS:
        raise ValueError(
            f"method must be one of {sorted(_VALID_METHODS)}, got {method!r}"
        )

    labels, groups = _resolve_groups(adata, group, reference)

    X = adata.X.astype(float)
    n_samples, n_proteins = X.shape
    gene_names = list(adata.var_names.astype(str))

    if key in _MULTIGROUP_METHODS:
        res = _de_multigroup(X, gene_names, labels, groups, key)
        adata.uns.setdefault("protein", {})["de_method"] = key
        adata.uns["protein_de"] = res
        return res

    # Pairwise tests below need exactly two groups.
    if len(groups) != 2:
        raise ValueError(
            f"method={key!r} is a two-group test but got {len(groups)} "
            f"groups: {groups}. Use method='anova' or 'kruskal' for "
            f"multi-group designs, or pass reference= to pick a baseline."
        )

    if key == "deqms":
        res = _de_deqms(adata, labels, groups, count_var, fit_method, **kwargs)
    elif key == "limma":
        res = _de_limma(adata, labels, groups, **kwargs)
    elif key == "proda":
        res = _de_proda(adata, labels, groups, **kwargs)
    elif key == "wilcoxon":
        res = _de_wilcoxon(X, gene_names, labels, groups, **kwargs)
    elif key == "welch_t":
        res = _de_welch_t(X, gene_names, labels, groups, **kwargs)
    elif key == "olink_lmer":
        res = _de_olink_lmer(adata, labels, groups, **kwargs)
    else:  # pragma: no cover
        raise ValueError(key)

    adata.uns.setdefault("protein", {})["de_method"] = key
    adata.uns["protein_de"] = res
    return res


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _resolve_groups(adata, group, reference):
    if isinstance(group, str):
        if group not in adata.obs.columns:
            raise KeyError(f"group {group!r} not in adata.obs columns: "
                           f"{list(adata.obs.columns)}")
        labels = adata.obs[group].astype(str).to_numpy()
    else:
        labels = np.asarray(group)
        if labels.size != adata.n_obs:
            raise ValueError(f"group array has length {labels.size}, expected {adata.n_obs}")
    groups = list(pd.unique(labels))
    if reference is not None:
        if reference not in groups:
            raise ValueError(f"reference {reference!r} not among groups {groups}")
        groups = [reference] + [g for g in groups if g != reference]
    else:
        groups = sorted(groups)
    return labels, groups


def _build_design(labels, groups):
    n = labels.size
    design = np.zeros((n, len(groups)), dtype=float)
    for j, g in enumerate(groups):
        design[labels == g, j] = 1.0
    return design


def _bh_adjust(p: np.ndarray) -> np.ndarray:
    from scipy import stats as _st
    return _st.false_discovery_control(np.clip(p, 0.0, 1.0), method="bh")


# --------------------------------------------------------------------------- #
# DEqMS                                                                       #
# --------------------------------------------------------------------------- #
def _de_deqms(adata, labels, groups, count_var, fit_method, **kwargs):
    try:
        from pydeqms import deqms as _deqms_fn
    except ImportError as exc:
        raise ImportError(
            "method='deqms' requires pydeqms: `pip install pydeqms`. "
            "Fall back to method='limma' for no-count moderated t."
        ) from exc

    X = adata.X.astype(float)
    # pydeqms expects proteins × samples.
    M = pd.DataFrame(
        X.T, index=adata.var_names.astype(str), columns=adata.obs_names.astype(str),
    )
    design = pd.DataFrame(
        _build_design(labels, groups),
        index=adata.obs_names.astype(str),
        columns=[f"group_{g}" for g in groups],
    )
    if count_var in adata.var.columns:
        count = (
            pd.to_numeric(adata.var[count_var], errors="coerce")
              .fillna(1.0).astype(float).to_numpy()
        )
    else:
        count = np.ones(adata.n_vars, dtype=float)
    # Contrast: group1 - group0 (matches sorted groups ordering).
    contrast = np.array([-1.0, 1.0], dtype=float)
    # The DEqMS variance prior regresses log(s^2) on log2(count) — when
    # the peptide count has few distinct values the loess local fits go
    # singular ("svddc failed in l2fit"). Fall back loess → nls → spline
    # so ``method='deqms'`` is robust regardless of the count spread.
    fit_methods = [fit_method] + [
        m for m in ("nls", "spline") if m != fit_method
    ]
    result = None
    last_exc: Exception | None = None
    for fm in fit_methods:
        try:
            result = _deqms_fn(
                M, design, count=count,
                contrast=contrast, fit_method=fm, **kwargs,
            )
            break
        except (ValueError, np.linalg.LinAlgError, RuntimeError) as exc:
            last_exc = exc
            continue
    if result is None:
        raise RuntimeError(
            "DEqMS variance fit failed for every fit_method "
            f"({fit_methods}); the peptide count column may be degenerate. "
            "Use method='limma' for a count-free moderated t."
        ) from last_exc
    # Drop the limma P.Value/adj columns to avoid duplicate column names
    # after the sca.* rename — the DEqMS-adjusted statistics are the
    # ``ov.protein.de(method='deqms')`` answer; limma's are available via
    # ``method='limma'``.
    result = result.drop(columns=["P.Value", "adj.P.Val"], errors="ignore")
    result = result.rename(columns={
        "sca.P.Value": "P.Value",
        "sca.adj.pval": "adj.P.Val",
    })
    # Keep the limma t around but rename to sca.t to mark it's the
    # DEqMS-adjusted statistic.
    if "sca.t" in result.columns:
        result = result.drop(columns=["t"], errors="ignore")
        result = result.rename(columns={"sca.t": "t"})
    return result


# --------------------------------------------------------------------------- #
# limma (Smyth 2004 moderated t, no count weighting)                          #
# --------------------------------------------------------------------------- #
def _de_limma(adata, labels, groups, **kwargs):
    try:
        from pydeqms import lm_fit, ebayes
        from pydeqms.pipeline import _resolve_contrast
    except ImportError as exc:
        raise ImportError(
            "method='limma' requires pydeqms (vendored limma.eBayes): "
            "`pip install pydeqms`."
        ) from exc

    X = adata.X.astype(float)
    M = pd.DataFrame(
        X.T, index=adata.var_names.astype(str), columns=adata.obs_names.astype(str),
    )
    design = pd.DataFrame(
        _build_design(labels, groups),
        index=adata.obs_names.astype(str),
        columns=[f"group_{g}" for g in groups],
    )
    fit = lm_fit(M, design)
    fit, _ = _resolve_contrast(fit, np.array([-1.0, 1.0]))
    ebayes(fit)
    res = pd.DataFrame({
        "gene":      fit.protein_names,
        "logFC":     fit.coefficients[:, 0],
        "AveExpr":   fit.Amean,
        "t":         fit.t[:, 0],
        "P.Value":   fit.p_value[:, 0],
        "adj.P.Val": _bh_adjust(fit.p_value[:, 0]),
    }).sort_values("P.Value").reset_index(drop=True)
    return res


# --------------------------------------------------------------------------- #
# proDA (optional)                                                            #
# --------------------------------------------------------------------------- #
def _de_proda(adata, labels, groups, **kwargs):
    try:
        from pyproda import proda as _proda_fn, test_diff as _test_diff
    except ImportError as exc:
        raise ImportError(
            "method='proda' requires pyproda: `pip install pyproda`."
        ) from exc

    M = pd.DataFrame(
        adata.X.astype(float).T,
        index=adata.var_names.astype(str),
        columns=adata.obs_names.astype(str),
    )
    design = pd.DataFrame(
        _build_design(labels, groups),
        index=adata.obs_names.astype(str),
        columns=[f"group_{g}" for g in groups],
    )
    fit = _proda_fn(M, design=design, **kwargs)
    result = _test_diff(fit, contrast=np.array([-1.0, 1.0]))
    # Canonicalise pyproda's column names to the ov.protein DE schema.
    rename = {
        "name": "gene", "protein": "gene", "feature": "gene",
        "pval": "P.Value", "p.value": "P.Value", "pvalue": "P.Value",
        "adj.pval": "adj.P.Val", "adj_pval": "adj.P.Val",
        "padj": "adj.P.Val", "qvalue": "adj.P.Val",
        "estimate": "logFC", "diff": "logFC",
        "t_statistic": "t", "t.statistic": "t",
        "avg_abundance": "AveExpr",
    }
    result = result.rename(columns={k: v for k, v in rename.items() if k in result.columns})
    if "gene" not in result.columns:
        # Fall back to the index if no explicit name column survived.
        result = result.reset_index().rename(columns={"index": "gene"})
    if "adj.P.Val" not in result.columns and "P.Value" in result.columns:
        result["adj.P.Val"] = _bh_adjust(result["P.Value"].to_numpy())
    if "P.Value" in result.columns:
        result = result.sort_values("P.Value").reset_index(drop=True)
    return result


# --------------------------------------------------------------------------- #
# Wilcoxon                                                                    #
# --------------------------------------------------------------------------- #
def _de_wilcoxon(X, gene_names, labels, groups, **kwargs):
    from scipy import stats
    g0, g1 = groups
    idx0 = labels == g0
    idx1 = labels == g1
    n = X.shape[1]
    logfc = np.full(n, np.nan)
    pv = np.full(n, np.nan)
    for j in range(n):
        a = X[idx0, j]; b = X[idx1, j]
        a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
        if a.size < 2 or b.size < 2:
            continue
        logfc[j] = float(np.mean(b) - np.mean(a))
        try:
            res = stats.mannwhitneyu(a, b, alternative="two-sided",
                                      use_continuity=True)
            pv[j] = float(res.pvalue)
        except ValueError:
            continue
    return pd.DataFrame({
        "gene":      gene_names,
        "logFC":     logfc,
        "AveExpr":   np.nanmean(X, axis=0),
        "P.Value":   pv,
        "adj.P.Val": _bh_adjust(pv),
    }).sort_values("P.Value").reset_index(drop=True)


def _de_welch_t(X, gene_names, labels, groups, **kwargs):
    from scipy import stats
    g0, g1 = groups
    idx0 = labels == g0
    idx1 = labels == g1
    n = X.shape[1]
    logfc = np.full(n, np.nan)
    tval = np.full(n, np.nan)
    pv = np.full(n, np.nan)
    for j in range(n):
        a = X[idx0, j]; b = X[idx1, j]
        a = a[~np.isnan(a)]; b = b[~np.isnan(b)]
        if a.size < 2 or b.size < 2:
            continue
        logfc[j] = float(np.mean(b) - np.mean(a))
        try:
            res = stats.ttest_ind(b, a, equal_var=False, nan_policy="omit")
            tval[j] = float(res.statistic)
            pv[j] = float(res.pvalue)
        except ValueError:
            continue
    return pd.DataFrame({
        "gene":      gene_names,
        "logFC":     logfc,
        "AveExpr":   np.nanmean(X, axis=0),
        "t":         tval,
        "P.Value":   pv,
        "adj.P.Val": _bh_adjust(pv),
    }).sort_values("P.Value").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Multi-group: one-way ANOVA / Kruskal-Wallis                                 #
# --------------------------------------------------------------------------- #
def _de_multigroup(X, gene_names, labels, groups, key):
    """Per-protein omnibus test across >=2 groups (ANOVA or Kruskal-Wallis)."""
    from scipy import stats
    group_idx = [labels == g for g in groups]
    n = X.shape[1]
    stat = np.full(n, np.nan)
    pv = np.full(n, np.nan)
    for j in range(n):
        samples = []
        for idx in group_idx:
            v = X[idx, j]
            v = v[~np.isnan(v)]
            if v.size >= 2:
                samples.append(v)
        if len(samples) < 2:
            continue
        try:
            if key == "anova":
                res = stats.f_oneway(*samples)
            else:  # kruskal
                res = stats.kruskal(*samples)
            stat[j] = float(res.statistic)
            pv[j] = float(res.pvalue)
        except ValueError:
            continue
    stat_name = "F" if key == "anova" else "H"
    return pd.DataFrame({
        "gene":      gene_names,
        stat_name:   stat,
        "AveExpr":   np.nanmean(X, axis=0),
        "P.Value":   pv,
        "adj.P.Val": _bh_adjust(pv),
    }).sort_values("P.Value").reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Olink-style per-protein LMM                                                 #
# --------------------------------------------------------------------------- #
def _de_olink_lmer(adata, labels, groups, **kwargs):
    """Per-protein LMM ``NPX ~ group + (1|subject)`` via statsmodels.

    Used for paired / repeated-measures Olink designs. Falls back to
    fixed-effects OLS when ``subject_var`` is not supplied.
    """
    try:
        import statsmodels.formula.api as smf
    except ImportError as exc:
        raise ImportError(
            "method='olink_lmer' requires statsmodels: "
            "`pip install statsmodels`."
        ) from exc
    subject_var = kwargs.get("subject_var")

    rows = []
    for j, gene in enumerate(adata.var_names.astype(str)):
        y = adata.X[:, j].astype(float)
        keep = ~np.isnan(y)
        if keep.sum() < 4:
            rows.append({"gene": gene, "logFC": np.nan, "P.Value": np.nan})
            continue
        df = pd.DataFrame({
            "y": y[keep],
            "group": pd.Categorical(labels[keep], categories=groups),
        })
        if subject_var is not None:
            df["subject"] = adata.obs[subject_var].to_numpy()[keep]
            try:
                m = smf.mixedlm("y ~ group", df, groups=df["subject"]).fit(disp=False)
            except Exception:
                rows.append({"gene": gene, "logFC": np.nan, "P.Value": np.nan})
                continue
        else:
            try:
                m = smf.ols("y ~ group", df).fit()
            except Exception:
                rows.append({"gene": gene, "logFC": np.nan, "P.Value": np.nan})
                continue
        # Pick the group1 coefficient.
        target = next((k for k in m.params.index if k.startswith("group[T.")), None)
        if target is None:
            rows.append({"gene": gene, "logFC": np.nan, "P.Value": np.nan})
            continue
        rows.append({
            "gene":    gene,
            "logFC":   float(m.params[target]),
            "P.Value": float(m.pvalues[target]),
        })
    out = pd.DataFrame(rows)
    out["adj.P.Val"] = _bh_adjust(out["P.Value"].to_numpy())
    return out.sort_values("P.Value").reset_index(drop=True)
