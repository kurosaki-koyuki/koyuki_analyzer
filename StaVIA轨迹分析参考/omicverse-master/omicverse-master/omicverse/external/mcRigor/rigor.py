"""Pure-Python port of mcRigor's double-permutation rigor test.

The R/Rcpp source ``src/mc_test_stats.cpp`` defines:

    mc_indpd_stats_cpp(dat) = ||Σ̂ - I||_F / sqrt(p * (p - 0.5))
        where dat is (cells × genes), centered & scaled per gene, and
        Σ̂ = dat.T @ dat / (n - 1).

For each metacell we:

1. Filter genes with non-zero count in > ``gene_filter`` fraction of cells.
2. Centre/scale gene columns.
3. Compute T_org on the cell-by-gene block.
4. T_colperm: column-wise shuffle of cells within each gene (breaks
   cell-cell dependence, preserves marginals).  Computed once.
5. For i = 1..Nrep:
   - row-permute (within-cell shuffle of genes; destroys all structure).
   - T_rowperm[i] = T(rowperm(dat)).
   - T_bothperm[i] = T(colperm(rowperm(dat))).
6. mcDiv = T_org / T_colperm.

Threshold for size s: ``(1 - test_cutoff)`` quantile of
``T_rowperm / T_bothperm`` pooled across all metacells of that size, with
optional LOWESS smoothing across sizes (bandwidth ``thre_bw``).

A metacell is *dubious* iff ``size > 1 and mcDiv > threshold[size]``.

For γ-sweeps we additionally track:
- ``DubRate(γ)`` = Σ size(dubious mc) / Σ size(all mc)   (LOWESS-smoothed)
- ``ZeroRate(γ)`` = mean (1 − nFeature_above_thr / n_genes) per metacell
- ``Score(γ)``  = 1 − (weight · DubRate + (1 − weight) · ZeroRate)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy import sparse


# ----------------------------------------------------------------------------
# Core statistic + permutations
# ----------------------------------------------------------------------------


def _scale_cols(M: np.ndarray) -> np.ndarray:
    """Center each column to zero mean, scale to unit SD.  Cols with sd=0 stay 0."""
    M = M.astype(np.float64, copy=False)
    mean = M.mean(axis=0)
    centered = M - mean
    sd = np.sqrt((centered**2).sum(axis=0) / max(M.shape[0] - 1, 1))
    out = np.zeros_like(centered)
    nz = sd > 0
    out[:, nz] = centered[:, nz] / sd[nz]
    return out


def mc_indpd_stats(dat: np.ndarray) -> float:
    """Modified Frobenius norm of (sample covariance − I).

    Matches ``mc_indpd_stats_cpp`` in mcRigor src.
    """
    if dat.shape[0] < 2 or dat.shape[1] < 2:
        return np.nan
    centered = dat - dat.mean(axis=0)
    cov = (centered.T @ centered) / (dat.shape[0] - 1.0)
    # Subtract identity from diagonal.
    np.fill_diagonal(cov, np.diag(cov) - 1.0)
    p = float(dat.shape[1])
    return float(np.linalg.norm(cov, ord="fro") / np.sqrt(p * (p - 0.5)))


def _colwise_perm(dat: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Independently shuffle each column (within-gene shuffle of cells)."""
    out = dat.copy()
    n = dat.shape[0]
    for j in range(dat.shape[1]):
        out[:, j] = out[rng.permutation(n), j]
    return out


def _rowwise_perm(dat: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Independently shuffle each row (within-cell shuffle of genes)."""
    out = dat.copy()
    p = dat.shape[1]
    for i in range(dat.shape[0]):
        out[i, :] = out[i, rng.permutation(p)]
    return out


# ----------------------------------------------------------------------------
# Per-metacell test
# ----------------------------------------------------------------------------


def _mc_test_stats(
    counts: np.ndarray,
    gene_filter: float,
    n_rep: int,
    rng: np.random.Generator,
) -> dict:
    """Run the double-permutation test on one metacell's (cells × genes) block.

    Parameters
    ----------
    counts : (n_cells, n_genes)
        Log-normalised expression block for the cells in one metacell.
    gene_filter : float
        Drop genes with non-zero count in <= this fraction of cells.
    n_rep : int
        Number of row-permutation replicates.
    rng : numpy Generator
    """
    n, p_full = counts.shape

    # Gene filter: keep genes present in > gene_filter fraction of cells.
    keep = (counts > 0).sum(axis=0) > p_full * gene_filter  # NOTE: matches R src
    # The R cpp uses `nonZeroCount > counts.cols() * gene_select_thre` but counts
    # is genes × cells there → for our cells × genes layout the equivalent
    # condition is `(counts > 0).sum(0) > n_cells * gene_filter`.
    keep = (counts > 0).sum(axis=0) > n * gene_filter

    counts_var = counts[:, keep]
    p = counts_var.shape[1]
    n_feature_kept = int(keep.sum())

    if n < 2 or p < 2:
        return dict(
            T_org=np.nan,
            T_colperm=np.nan,
            T_rowperm=np.full(n_rep, np.nan),
            T_bothperm=np.full(n_rep, np.nan),
            n_feature=n_feature_kept,
        )

    dat = _scale_cols(counts_var)  # cells × kept-genes, column-centered/scaled

    T_org = mc_indpd_stats(dat)
    T_colperm = mc_indpd_stats(_colwise_perm(dat, rng))

    T_rowperm = np.empty(n_rep)
    T_bothperm = np.empty(n_rep)
    for i in range(n_rep):
        x = _rowwise_perm(dat, rng)
        T_rowperm[i] = mc_indpd_stats(x)
        T_bothperm[i] = mc_indpd_stats(_colwise_perm(x, rng))

    return dict(
        T_org=T_org,
        T_colperm=T_colperm,
        T_rowperm=T_rowperm,
        T_bothperm=T_bothperm,
        n_feature=n_feature_kept,
    )


def _threshold_by_size(
    tabmc: pd.DataFrame,
    test_cutoff: float,
    thre_smooth: bool,
    thre_bw: float,
) -> pd.DataFrame:
    """Compute size-stratified rigor threshold, optionally LOWESS-smoothed."""
    rows = []
    for size, sub in tabmc.groupby("size"):
        if size == 1:
            continue
        ratios = np.concatenate(
            [r / b for r, b in zip(sub["T_rowperm"].values, sub["T_bothperm"].values)]
        )
        ratios = ratios[~np.isnan(ratios)]
        if ratios.size == 0:
            continue
        rows.append((int(size), float(np.quantile(ratios, 1 - test_cutoff))))

    if not rows:
        return pd.DataFrame(columns=["size", "thre"])

    thre = pd.DataFrame(rows, columns=["size", "thre"]).sort_values("size").reset_index(drop=True)

    if thre_smooth and len(thre) >= 4:
        try:
            from statsmodels.nonparametric.smoothers_lowess import lowess
            smoothed = lowess(
                endog=thre["thre"].values,
                exog=thre["size"].values,
                frac=thre_bw,
                return_sorted=True,
            )
            thre = pd.DataFrame({"size": smoothed[:, 0], "thre": smoothed[:, 1]})
        except ImportError:
            pass  # statsmodels not installed → fall back to raw quantiles

    return thre


def _label_dubious(tabmc: pd.DataFrame, thre: pd.DataFrame) -> pd.Series:
    """Assign 'trustworthy' | 'dubious' per metacell using size-stratified threshold."""
    thre_lookup = dict(zip(thre["size"].round().astype(int), thre["thre"]))
    sizes = list(thre_lookup.keys())

    def _label(row):
        if row["size"] <= 1:
            return "trustworthy"
        size = int(row["size"])
        if size in thre_lookup:
            t = thre_lookup[size]
        elif sizes:
            # Nearest neighbour on size if exact match missing post-smoothing.
            t = thre_lookup[min(sizes, key=lambda s: abs(s - size))]
        else:
            return "trustworthy"
        return "dubious" if row["mcDiv"] > t else "trustworthy"

    return tabmc.apply(_label, axis=1)


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------


@dataclass
class RigorReport:
    """Return container for :func:`rigor_detect` / :func:`rigor_optimize`."""

    per_metacell: pd.DataFrame   # one row per metacell
    threshold: pd.DataFrame      # (size, thre)
    dubious_rate: float          # Σ size(dubious) / Σ size(all)
    zero_rate: float             # mean per-metacell sparsity
    score: float                 # 1 − (weight·DubRate + (1−weight)·ZeroRate)
    null_table: pd.DataFrame     # Nrep × n_metacells (T_rowperm, T_bothperm)
    n_metacells: int = 0
    sweep: Optional[pd.DataFrame] = None        # set by rigor_optimize only
    best_n_metacells: Optional[int] = None      # set by rigor_optimize only


def _logical_to_index(membership: np.ndarray) -> dict[int, np.ndarray]:
    """Return {metacell_id: array of cell indices}."""
    out: dict[int, np.ndarray] = {}
    uniq, inv = np.unique(membership, return_inverse=True)
    for k, mc_id in enumerate(uniq):
        out[int(mc_id)] = np.where(inv == k)[0]
    return out


def rigor_detect(
    X_lognorm,
    membership: np.ndarray,
    *,
    feature_use: int = 2000,
    gene_filter: float = 0.1,
    n_rep: int = 50,
    test_cutoff: float = 0.01,
    thre_smooth: bool = True,
    thre_bw: float = 1 / 6,
    weight: float = 0.5,
    random_state: int = 0,
) -> RigorReport:
    """Score the rigor of one fixed metacell partition.

    Parameters
    ----------
    X_lognorm
        ``(n_cells, n_genes)`` log-normalised expression matrix
        (numpy array or scipy sparse).  Counts will be densified per
        metacell internally.
    membership
        ``(n_cells,)`` integer array assigning each cell to a metacell id.
    feature_use
        Pre-select this many high-variance genes globally (matches
        ``feature_use=2000`` in upstream).  Use 0 to disable.
    gene_filter
        Within each metacell, drop genes detected in <= this fraction of
        cells (upstream default 0.1).
    n_rep
        Number of row-permutation replicates (upstream default 50).
    test_cutoff
        Threshold quantile = ``1 - test_cutoff`` (upstream default 0.01 → 99%).
    thre_smooth, thre_bw
        LOWESS smoothing of the size-vs-threshold curve (R defaults).
    weight
        Score weight on DubRate vs ZeroRate (R default 0.5).
    random_state
        Seed for numpy Generator.
    """
    membership = np.asarray(membership).astype(int)
    rng = np.random.default_rng(random_state)

    # Optional global HVG pre-selection (Seurat-style: top by variance after sparse → dense).
    if feature_use and feature_use > 0 and X_lognorm.shape[1] > feature_use:
        if sparse.issparse(X_lognorm):
            mean = np.asarray(X_lognorm.mean(axis=0)).ravel()
            sq_mean = np.asarray(X_lognorm.multiply(X_lognorm).mean(axis=0)).ravel()
            var = sq_mean - mean**2
        else:
            var = np.asarray(X_lognorm).var(axis=0)
        top = np.argsort(var)[::-1][:feature_use]
        X_lognorm = X_lognorm[:, top]

    mc_index = _logical_to_index(membership)
    n_metacells_total = len(mc_index)
    rows = []
    null_rows = []
    for mc_id, cell_ix in mc_index.items():
        if sparse.issparse(X_lognorm):
            block = np.asarray(X_lognorm[cell_ix].todense())
        else:
            block = X_lognorm[cell_ix]
        size = block.shape[0]
        out = _mc_test_stats(block, gene_filter=gene_filter, n_rep=n_rep, rng=rng)

        mcDiv = (
            out["T_org"] / out["T_colperm"]
            if out["T_colperm"] and not np.isnan(out["T_colperm"])
            else 1.0
        )
        if np.isnan(mcDiv):
            mcDiv = 1.0

        rows.append(
            dict(
                metacell_id=int(mc_id),
                size=int(size),
                T_org=out["T_org"],
                T_colperm=out["T_colperm"],
                mcDiv=mcDiv,
                n_feature=out["n_feature"],
                T_rowperm=out["T_rowperm"],
                T_bothperm=out["T_bothperm"],
            )
        )
        null_rows.append(
            dict(metacell_id=int(mc_id), T_rowperm=out["T_rowperm"], T_bothperm=out["T_bothperm"])
        )

    tabmc = pd.DataFrame(rows)

    # Threshold (size-stratified, LOWESS-smoothed).
    thre = _threshold_by_size(
        tabmc, test_cutoff=test_cutoff, thre_smooth=thre_smooth, thre_bw=thre_bw
    )

    # Label dubious / trustworthy.
    tabmc["label"] = _label_dubious(tabmc, thre)

    # Aggregate scores.
    dub_size = tabmc.loc[tabmc["label"] == "dubious", "size"].sum()
    all_size = tabmc["size"].sum()
    dub_rate = float(dub_size) / float(all_size) if all_size else 0.0

    n_genes = X_lognorm.shape[1] if X_lognorm.shape[1] else 1
    zero_rate = float((1 - tabmc["n_feature"] / n_genes).mean())

    score = 1.0 - (weight * dub_rate + (1 - weight) * zero_rate)

    return RigorReport(
        per_metacell=tabmc.drop(columns=["T_rowperm", "T_bothperm"]).reset_index(drop=True),
        threshold=thre.reset_index(drop=True),
        dubious_rate=dub_rate,
        zero_rate=zero_rate,
        score=score,
        null_table=pd.DataFrame(null_rows),
        n_metacells=n_metacells_total,
    )


def rigor_optimize(
    X_lognorm,
    memberships_by_n: dict[int, np.ndarray],
    *,
    optim_method: str = "tradeoff",
    dub_rate: float = 0.1,
    weight: float = 0.5,
    smooth_dub_rate: bool = True,
    D_bw: int = 10,
    **detect_kwargs,
) -> RigorReport:
    """Sweep ``n_metacells`` values and pick the best.

    Parameters
    ----------
    X_lognorm
        ``(n_cells, n_genes)`` log-normalised expression.
    memberships_by_n
        Mapping from ``n_metacells`` (int) → membership vector ``(n_cells,)``.
    optim_method
        ``'tradeoff'``      — argmax Score = 1 − (½·DubRate + ½·ZeroRate)
        ``'dub_rate_large'`` — largest n_metacells with DubRate < ``dub_rate``
        ``'dub_rate_small'`` — first n_metacells with DubRate ≥ ``dub_rate``,
                               minus 1
    dub_rate
        Threshold used by the non-tradeoff modes (default 0.1).
    weight
        Score weight on DubRate (default 0.5).
    smooth_dub_rate
        LOWESS-smooth DubRate across n_metacells if range > 5.
    D_bw
        LOWESS bandwidth for DubRate smoothing (R default 10).
    **detect_kwargs
        Forwarded to :func:`rigor_detect` for each γ.
    """
    if optim_method not in {"tradeoff", "dub_rate_large", "dub_rate_small"}:
        raise ValueError(f"unknown optim_method: {optim_method!r}")

    sweep_rows = []
    reports: dict[int, RigorReport] = {}
    for n_mc, membership in sorted(memberships_by_n.items()):
        rep = rigor_detect(X_lognorm, membership, weight=weight, **detect_kwargs)
        reports[n_mc] = rep
        sweep_rows.append(
            dict(
                n_metacells=n_mc,
                dubious_rate=rep.dubious_rate,
                zero_rate=rep.zero_rate,
                score=rep.score,
            )
        )

    sweep = pd.DataFrame(sweep_rows).sort_values("n_metacells").reset_index(drop=True)

    if smooth_dub_rate and len(sweep) > 1:
        rng_span = sweep["n_metacells"].max() - sweep["n_metacells"].min()
        if rng_span > 5:
            try:
                from statsmodels.nonparametric.smoothers_lowess import lowess
                sweep["dubious_rate"] = lowess(
                    endog=sweep["dubious_rate"].values,
                    exog=sweep["n_metacells"].values,
                    frac=min(1.0, D_bw / rng_span),
                    return_sorted=False,
                )
            except ImportError:
                pass

    # Recompute score from possibly-smoothed dubious_rate (matches R behaviour).
    sweep["score"] = 1 - (weight * sweep["dubious_rate"] + (1 - weight) * sweep["zero_rate"])

    if optim_method == "tradeoff":
        best_n = int(sweep.loc[sweep["score"].idxmax(), "n_metacells"])
    elif optim_method == "dub_rate_large":
        candidates = sweep[sweep["dubious_rate"] < dub_rate]
        best_n = int(candidates["n_metacells"].max()) if not candidates.empty else int(sweep["n_metacells"].iloc[0])
    else:  # dub_rate_small
        above = sweep[sweep["dubious_rate"] >= dub_rate]
        if above.empty:
            best_n = int(sweep["n_metacells"].iloc[-1])
        else:
            idx = above.index[0]
            best_n = int(sweep.loc[max(idx - 1, 0), "n_metacells"])

    best_rep = reports[best_n]
    best_rep.sweep = sweep
    best_rep.best_n_metacells = best_n
    return best_rep
