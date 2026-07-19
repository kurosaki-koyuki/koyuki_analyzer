"""Fast NMF for single-cell gene-program identification.

Wraps :pypi:`nmf-rs` (a Rust port of R's `NMF` package + 2024 SOTA algorithms)
for the factorisation, then provides cNMF-style helpers for visualisation
and module identification.

Use-cases:

- **Exploratory single-cell analysis** — gene programs that align with
  cell-type biology. Recipe: ``method='lee', init='nndsvd', max_iter=25``
  reaches ARI ≈ 0.89 vs ``predicted_celltype`` on PBMC 8k (still bit-eq R).
- **Speed at atlas scale** — ``method='dnmf', init='nndsvd'``
  (DeBruine 2024 RcppML-style) for a few hundred thousand cells.
- **Reproduce a published R `NMF` analysis** — ``method='lee'`` /
  ``'brunet'`` / ``'snmf/r'`` / ``'snmf/l'`` are bitwise-identical
  to R within f64 round-off.

Imports of ``nmf-rs`` are lazy / in-function so this module loads even
when the optional dependency is missing — call any method to trigger
the import (with a clear error message if not installed).
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union
import warnings

import numpy as np
import pandas as pd
from anndata import AnnData


__all__ = ["NMF"]


# -- internal helpers --------------------------------------------------------

_NMF_RS_INSTALL_HINT = (
    "`omicverse.single.NMF` requires `nmf-rs` (pip install nmf-rs). "
    "See https://github.com/omicverse/rust-NMF for build-from-source instructions."
)


def _import_nmf_rs():
    try:
        import nmf_rs  # type: ignore
    except ImportError as e:
        raise ImportError(_NMF_RS_INSTALL_HINT) from e
    return nmf_rs


def _to_dense_genes_x_cells(adata: AnnData, layer: Optional[str]) -> np.ndarray:
    """Extract a dense (genes × cells) float64 matrix from `adata`.

    The R `NMF` / single-cell convention is genes-as-rows; rust-NMF accepts
    either orientation but factor interpretation is cleaner with this layout.
    """
    if layer is None or layer == "X":
        X = adata.X
    elif layer in adata.layers:
        X = adata.layers[layer]
    else:
        raise KeyError(
            f"layer '{layer}' not found in adata.layers ({list(adata.layers)})"
        )
    if hasattr(X, "toarray"):
        X = X.toarray()
    X = np.asarray(X, dtype=np.float64)
    if (X < 0).any():
        # NMF requires V ≥ 0. Common failure mode: scaled or PCA-projected matrices.
        n_neg = int((X < 0).sum())
        warnings.warn(
            f"adata.{layer or 'X'} has {n_neg} negative entries; clamping to 0. "
            "NMF requires non-negative input — typical input is a log-normalised "
            "or raw counts matrix, NOT scaled / PCA / Z-scored data.",
            stacklevel=3,
        )
        X = np.clip(X, 0.0, None)
    # (n_obs × n_vars) → (genes × cells) by transposing.
    V = np.ascontiguousarray(X.T)
    return V


def _normalise_columns(arr: np.ndarray) -> np.ndarray:
    """Column-stochastic normalise (each column sums to 1)."""
    sums = arr.sum(axis=0, keepdims=True)
    sums = np.where(sums > 0, sums, 1.0)
    return arr / sums


def _normalise_rows(arr: np.ndarray) -> np.ndarray:
    """Row-stochastic normalise (each row sums to 1) — cNMF convention for cell usages."""
    sums = arr.sum(axis=1, keepdims=True)
    sums = np.where(sums > 0, sums, 1.0)
    return arr / sums


# -- public API --------------------------------------------------------------

class NMF:
    """Fast non-negative matrix factorisation for gene-program discovery.

    Parameters
    ----------
    adata : AnnData
        Input single-cell object. Use a non-negative matrix (raw counts or
        log-normalised counts in ``layer=`` / ``X``) — NOT scaled / PCA data.
    rank : int
        Number of factors / programs (``K``).
    layer : str, default ``'X'``
        Where to read the gene-by-cell matrix. ``'X'`` → ``adata.X``;
        otherwise looked up in ``adata.layers``.
    use_hvg : bool, default True
        If True and ``adata.var['highly_variable']`` exists, restrict to HVGs.
    num_threads : int, optional
        Per-call rayon thread count for the underlying rust-NMF kernel.
        Defaults to all available cores.

    Notes
    -----
    The fitted factors are stored on the object as ``self.W`` (genes × rank)
    and ``self.H`` (rank × cells). Use :meth:`get_results` to push them into
    ``adata.obsm`` / ``adata.varm`` in a layout compatible with
    ``ov.pl.embedding`` and ``ov.pl.dotplot``.
    """

    def __init__(
        self,
        adata: AnnData,
        rank: int,
        *,
        layer: Optional[str] = "X",
        use_hvg: bool = True,
        num_threads: Optional[int] = None,
    ) -> None:
        if not isinstance(rank, int) or rank < 2:
            raise ValueError(f"rank must be an int >= 2, got {rank!r}")
        if use_hvg and "highly_variable" in adata.var.columns:
            adata = adata[:, adata.var["highly_variable"]].copy()
        self._adata_view: AnnData = adata
        self.var_names: pd.Index = pd.Index(adata.var_names)
        self.obs_names: pd.Index = pd.Index(adata.obs_names)
        self.rank: int = int(rank)
        self.layer: Optional[str] = layer
        self.num_threads: Optional[int] = num_threads
        self.method: Optional[str] = None
        self.init: Optional[str] = None
        self.W: Optional[np.ndarray] = None     # (n_genes × rank)
        self.H: Optional[np.ndarray] = None     # (rank × n_cells)
        self.deviances: Optional[np.ndarray] = None
        self.n_iter: Optional[int] = None
        # Cached after fit.
        self._V: Optional[np.ndarray] = None     # (genes × cells)
        # Set by select_k().
        self._k_selection: Optional[pd.DataFrame] = None

    # ------ Fit ------------------------------------------------------------

    def fit(
        self,
        *,
        method: str = "lee",
        init: str = "nndsvd",
        max_iter: int = 25,
        sparsity: float = 0.0,
        smoothness: float = 0.0,
        seed: int = 0,
        nndsvd_fill: str = "mean",
    ) -> "NMF":
        """Run the factorisation.

        Recommended defaults (``method='lee', init='nndsvd', max_iter=25``)
        are the configuration that reaches the highest ARI vs cell-type labels
        on PBMC 8k in our benchmarks. For an even faster (modern) recipe use
        ``method='dnmf'`` (RcppML-style; non-bit-eq with R but ARI ≈ 0.85).

        Parameters
        ----------
        method : str
            One of ``brunet``, ``lee``, ``offset``, ``nsNMF``, ``hals``,
            ``ehals``, ``dnmf``, ``snmf/r``, ``snmf/l``, ``ls-nmf``.
            Aliases follow rust-NMF (``KL``, ``Frobenius``, ``rcppml``, ...).
        init : {'nndsvd', 'random'}
            Initialisation strategy. NNDSVD (Boutsidis-Gallopoulos 2008) is
            deterministic and yields ~30-60% higher cell-type ARI in our
            benchmarks vs random init.
        max_iter : int
            Iteration cap. With NNDSVD init, 25 typically suffices.
        sparsity / smoothness : float
            L1 / L2 coefficients (only used by ``snmf/r``, ``snmf/l``, ``dnmf``).
        seed : int
            Reproducibility seed for ``random`` init.
        nndsvd_fill : {'mean', 'eps', 'zero'}
            Zero-replacement strategy for NNDSVD; ``'mean'`` (NNDSVDa) is
            the canonical choice for multiplicative-update solvers.
        """
        nmf_rs = _import_nmf_rs()

        V = _to_dense_genes_x_cells(self._adata_view, self.layer)
        n_genes, n_cells = V.shape

        if init == "nndsvd":
            W0, H0 = nmf_rs.nndsvd_init(V, self.rank, fill=nndsvd_fill, seed=seed)
        elif init == "random":
            W0, H0 = nmf_rs.random_init(V, self.rank, seed=seed)
        else:
            raise ValueError(f"unknown init '{init}'; use 'nndsvd' or 'random'")

        kw = dict(
            W0=W0, H0=H0,
            max_iter=int(max_iter),
            num_threads=self.num_threads,
            seed=seed,
        )
        # Pass sparsity/smoothness only when the algorithm uses them
        # (avoid spurious params on lee/brunet/etc).
        if method in {"snmf/r", "snmf_r", "snmfr", "snmf/l", "snmf_l", "snmfl",
                       "dnmf", "rcppml", "diag_nmf"}:
            kw["sparsity"] = float(sparsity)
            kw["smoothness"] = float(smoothness)

        res = nmf_rs.nmf(V, rank=self.rank, method=method, **kw)
        self.method = method
        self.init = init
        self.W = np.asarray(res.W)            # (n_genes, rank)
        self.H = np.asarray(res.H)            # (rank, n_cells)
        self.deviances = np.asarray(res.deviances) if res.deviances is not None else None
        self.n_iter = int(res.n_iter)
        self._V = V
        return self

    # ------ Rank selection -------------------------------------------------

    def select_k(
        self,
        k_range: Iterable[int],
        *,
        method: str = "lee",
        init: str = "nndsvd",
        max_iter: int = 25,
        n_folds: int = 2,
        mask_frac: float = 0.05,
        seed: int = 0,
    ) -> pd.DataFrame:
        """Cross-validated rank selection.

        Holds out ``mask_frac`` of V's entries per fold, fits NMF via
        ``ls-nmf`` with the held-out cells masked from the loss, then
        reports test-MSE on the held-out entries.

        Returns
        -------
        DataFrame with columns ``rank, fold, train_loss, test_mse``.
        Test-MSE plateau identifies the right rank.
        """
        nmf_rs = _import_nmf_rs()
        V = _to_dense_genes_x_cells(self._adata_view, self.layer)
        df = nmf_rs.cv_rank(
            V, ranks=list(k_range),
            method=method, init=init, max_iter=max_iter,
            n_folds=n_folds, mask_frac=mask_frac, seed=seed,
            num_threads=self.num_threads,
        )
        self._k_selection = df
        self._k_selection_mode = "cv"
        return df

    def select_k_brunet(
        self,
        k_range: Iterable[int],
        *,
        method: Optional[str] = None,
        n_runs: int = 50,
        max_iter: int = 50,
        sparsity: float = 0.0,
        smoothness: float = 0.0,
        seed: int = 0,
    ) -> pd.DataFrame:
        """cNMF-style rank selection — silhouette of spectra k-means clusters.

        For each ``K`` in ``k_range``:

        1. Run NMF ``n_runs`` times with different random seeds.
        2. Stack all ``n_runs·K`` factor vectors (each length-`n_genes`,
           L2-normalised) and compute pair-wise Euclidean distances.
        3. K-means cluster the spectra into K groups.
        4. **Silhouette** of that K-clustering (tighter clusters → factors
           reproduce reliably across runs → higher silhouette).
        5. **Mean reconstruction loss** across runs.

        This is the canonical cNMF / Kotliar 2019 approach (and matches
        ``cnmf_obj.k_selection_plot``). The recommended K is at the
        silhouette elbow before reconstruction plateaus.

        Defaults are tuned to actually produce a clean elbow:
        ``n_runs=50, max_iter=50``. cNMF uses 200 / 500 — increase if your
        K curves still look noisy.

        Returns
        -------
        DataFrame with columns ``rank, mean_loss, silhouette``.
        Use :meth:`k_selection_plot` to visualise.
        """
        nmf_rs = _import_nmf_rs()
        if self._V is None:
            self._V = _to_dense_genes_x_cells(self._adata_view, self.layer)
        method = method or "dnmf"
        rng = np.random.default_rng(seed)

        kw_extras = {}
        if method.lower() in {"snmf/r", "snmf_r", "snmfr", "snmf/l", "snmf_l",
                               "snmfl", "dnmf", "rcppml", "diag_nmf"}:
            kw_extras["sparsity"] = float(sparsity)
            kw_extras["smoothness"] = float(smoothness)

        try:
            from scipy.spatial.distance import pdist, squareform
            from sklearn.cluster import KMeans
            from sklearn.metrics import silhouette_score
        except ImportError as e:
            raise ImportError(
                "select_k_brunet() requires scikit-learn + scipy"
            ) from e

        rows = []
        for k in k_range:
            spectra_cols: List[np.ndarray] = []
            losses: List[float] = []
            for _ in range(int(n_runs)):
                run_seed = int(rng.integers(0, 2**31 - 1))
                W0, H0 = nmf_rs.random_init(self._V, int(k), seed=run_seed)
                res = nmf_rs.nmf(
                    self._V, rank=int(k), method=method,
                    W0=W0, H0=H0, max_iter=int(max_iter),
                    num_threads=self.num_threads,
                    **kw_extras,
                )
                losses.append(0.5 * float(np.linalg.norm(self._V - res.fitted()) ** 2))
                W = res.W
                norms = np.linalg.norm(W, axis=0, keepdims=True)
                norms = np.where(norms > 0, norms, 1.0)
                spectra_cols.append(W / norms)
            spectra = np.hstack(spectra_cols).T          # (n_runs·k, n_genes)
            # Pair-wise distance + silhouette of k-means clustering.
            dist = squareform(pdist(spectra, metric="euclidean"))
            km = KMeans(n_clusters=int(k), n_init=10, random_state=int(seed))
            labels = km.fit_predict(spectra)
            if len(set(labels)) < 2:
                sil = float("nan")
            else:
                sil = float(silhouette_score(dist, labels, metric="precomputed"))
            rows.append({
                "rank": int(k),
                "mean_loss": float(np.mean(losses)),
                "silhouette": sil,
            })

        df = pd.DataFrame(rows)
        self._k_selection = df
        self._k_selection_mode = "brunet"
        self._auto_k = self._stability_drop_k(df["rank"].to_numpy(),
                                               df["silhouette"].to_numpy())
        return df

    @staticmethod
    def _stability_drop_k(ranks: np.ndarray, sil: np.ndarray,
                           plateau_tol: float = -0.01) -> int:
        """Auto-pick K via the **stability-drop heuristic**.

        Combines two well-cited NMF rank-selection ideas:

        - Brunet et al. PNAS 2004: pick K just before consensus stability
          drops sharply (originally on cophenetic correlation; we use the
          factor silhouette as a closely related but more robust statistic).
        - Kim-Park 2007: prefer K at a *local maximum* of the stability
          profile, not just the global peak.

        Algorithm: for each interior K, score it by the size of the silhouette
        drop from K to K+1, gated by the requirement that the silhouette
        held flat (or rose) coming into K — i.e. K is the end of a plateau
        right before a sharp drop. Return the K with maximum score.
        Falls back to the largest local peak if no plateau-drop pattern is
        detected (e.g. monotonic curves).
        """
        ranks = np.asarray(ranks); sil = np.asarray(sil, dtype=float)
        if len(ranks) < 3:
            return int(ranks[int(np.argmax(sil))])
        # First differences: dy[i] = sil[i+1] - sil[i].
        dy = np.diff(sil)
        # Score interior points where (left ≥ tol) and (right < 0).
        score = np.zeros(len(ranks))
        for i in range(1, len(ranks) - 1):
            left = dy[i - 1]    # change INTO ranks[i]
            right = dy[i]        # change AFTER ranks[i]
            if left >= plateau_tol and right < 0:
                score[i] = abs(right)
        if score.max() > 0:
            return int(ranks[int(np.argmax(score))])
        # Fallback: largest local peak (handles monotonic curves).
        local = []
        for i in range(len(ranks)):
            ok_left = (i == 0) or sil[i] >= sil[i - 1]
            ok_right = (i == len(ranks) - 1) or sil[i] >= sil[i + 1]
            if ok_left and ok_right:
                local.append(int(ranks[i]))
        if local:
            return max(local)
        return int(ranks[int(np.argmax(sil))])

    @property
    def auto_k(self) -> int:
        """K auto-selected by the most recent ``select_k_brunet`` run."""
        if not hasattr(self, "_auto_k"):
            raise RuntimeError("call select_k_brunet() first")
        return self._auto_k

    def k_selection_plot(
        self,
        ax=None,
        *,
        figsize: Tuple[int, int] = (6, 3),
    ):
        """Plot rank-selection curves from the most recent ``select_k*`` run.

        - ``select_k`` (CV mode): single-axis plot of test-MSE vs K.
        - ``select_k_brunet`` (consensus mode): twin-axis plot of stability
          (dispersion coefficient, left) and reconstruction error (right) vs K,
          mirroring cNMF's ``k_selection_plot``. Recommended K is where the
          stability curve has its kink and the error curve has flattened.
        """
        if getattr(self, "_k_selection", None) is None:
            raise RuntimeError("call select_k() or select_k_brunet() first")
        import matplotlib.pyplot as plt
        df = self._k_selection
        mode = getattr(self, "_k_selection_mode", "cv")
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.figure

        if mode == "cv":
            agg = df.groupby("rank")["test_mse"].agg(["mean", "std"])
            ax.errorbar(agg.index, agg["mean"], yerr=agg["std"], fmt="-o",
                        capsize=3, lw=1.5, color="#cc6677")
            ax.set_xlabel("rank (number of factors)")
            ax.set_ylabel("held-out test MSE")
            ax.set_title("CV rank selection — test-MSE plateau picks K")
            ax.grid(alpha=0.3)
        else:
            # Brunet/cNMF mode: silhouette (left axis) + reconstruction (right).
            agg = df.set_index("rank").sort_index()
            ax.plot(agg.index, agg["silhouette"], "o-", lw=2.0,
                    color="#cc6677", label="silhouette (factor stability)")
            sil_vals = agg["silhouette"].to_numpy()
            ranks_arr = agg.index.to_numpy()

            # Auto-K via the stability-drop heuristic (Brunet 2004 +
            # Kim-Park 2007). This is the same K our ``auto_k`` property
            # returns; it picks the K right before the biggest stability
            # drop, gated by a plateau / rise into K.
            auto_k = NMF._stability_drop_k(ranks_arr, sil_vals)
            ax.axvline(auto_k, color="#882255", lw=1.2, ls="--", alpha=0.85)
            ax.text(
                auto_k, agg.loc[auto_k, "silhouette"],
                f"  auto K = {auto_k}",
                color="#882255", fontsize=10, va="bottom", ha="left",
                fontweight="bold",
            )
            ax.set_xlabel("rank (K)")
            ax.set_ylabel("silhouette (higher = better)", color="#cc6677")
            ax.tick_params(axis='y', labelcolor="#cc6677")
            ax.set_ylim(0, 1.0)
            ax.grid(alpha=0.3)
            ax2 = ax.twinx()
            ax2.plot(agg.index, agg["mean_loss"], "^-", lw=1.8,
                     color="#4477aa", label="mean reconstruction loss")
            ax2.set_ylabel("reconstruction loss (lower = better)", color="#4477aa")
            ax2.tick_params(axis='y', labelcolor="#4477aa")
            lines1, labels1 = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2,
                      loc="lower center", bbox_to_anchor=(0.5, -0.42),
                      ncol=2, fontsize=8)
            ax.set_title(
                "cNMF-style K selection — pick the K with peak silhouette",
                fontsize=10,
            )
        fig.tight_layout()
        return ax

    # ------ Push results back into AnnData ---------------------------------

    def get_results(
        self,
        adata: AnnData,
        *,
        key_added: str = "NMF",
        n_top_genes: int = 30,
    ) -> Dict[str, Union[pd.DataFrame, pd.Index]]:
        """Push NMF outputs into ``adata`` and return a result dict.

        Adds:

        - ``adata.obsm[f'{key_added}_usage']`` — column-normalised
          ``H.T`` (cells × rank). Each row sums to 1 over factors.
        - ``adata.varm[f'{key_added}_genes']`` — column-normalised ``W``
          (HVG genes × rank).
        - ``adata.obs[f'{key_added}_module']`` — argmax-over-factors
          module assignment per cell.
        - ``adata.uns[f'{key_added}_params']`` — fit metadata.
        - ``adata.uns[f'{key_added}_top_genes']`` — DataFrame of the
          top-``n_top_genes`` per factor.

        The return-value dict mirrors the cNMF API:
        ``{'usage_norm', 'gep_scores', 'top_genes'}``.
        """
        if self.W is None:
            raise RuntimeError("call fit() first")
        rank = self.W.shape[1]
        cols = [f"factor_{k+1}" for k in range(rank)]

        # Cell usages: row-normalised so each cell's usages sum to 1 across
        # factors — matches the cNMF convention so the ARI / RFC threshold
        # logic transfers without surprise.
        H_T = self.H.T                                    # (n_cells × rank)
        usage_norm = pd.DataFrame(
            _normalise_rows(H_T.copy()), index=self.obs_names, columns=cols,
        )
        # Gene loadings: keep raw W values (each column is one factor's
        # gene-program; absolute values matter for top-gene ranking).
        gep_scores = pd.DataFrame(
            self.W.copy(), index=self.var_names, columns=cols,
        )

        # Top-n_top_genes per factor (descending W loading).
        top_idx = np.argsort(-self.W, axis=0)[:n_top_genes]
        top_genes_df = pd.DataFrame(
            self.var_names.values[top_idx], columns=cols,
        )

        # Wire into adata.
        # NB: usage uses ALL cells in self.obs_names (must match adata.obs_names).
        common_obs = self.obs_names.intersection(adata.obs_names)
        if len(common_obs) != adata.n_obs:
            warnings.warn(
                f"{adata.n_obs - len(common_obs)} of adata cells were not in the "
                "fit; their factor usages will be NaN.",
                stacklevel=2,
            )
        usage_full = usage_norm.reindex(adata.obs_names)
        adata.obsm[f"{key_added}_usage"] = usage_full.to_numpy(dtype=np.float64)
        # Also expose each factor as a per-cell column in adata.obs so
        # `ov.pl.embedding(adata, color=result_dict['usage_norm'].columns)`
        # works without extra plumbing — same as cNMF's behaviour.
        for col in cols:
            adata.obs[col] = usage_full[col].astype(np.float64).values
        # varm: store on shared genes only.
        common_var = self.var_names.intersection(adata.var_names)
        gene_full = pd.DataFrame(
            np.zeros((adata.n_vars, rank), dtype=np.float64),
            index=adata.var_names, columns=cols,
        )
        gene_full.loc[common_var, :] = gep_scores.loc[common_var, :].values
        adata.varm[f"{key_added}_genes"] = gene_full.to_numpy()

        # Argmax-over-factors module per cell.
        argmax_mod = np.full(adata.n_obs, -1, dtype=np.int64)
        usage_arr = usage_full.to_numpy()
        valid = ~np.isnan(usage_arr).any(axis=1)
        if valid.any():
            argmax_mod[valid] = np.argmax(usage_arr[valid], axis=1) + 1
        labels_mod = [f"M{m}" if m > 0 else "NA" for m in argmax_mod]
        seen_mod = sorted(set(labels_mod), key=lambda s: (s == "NA", int(s[1:]) if s != "NA" else 0))
        adata.obs[f"{key_added}_module"] = pd.Categorical(labels_mod, categories=seen_mod)

        adata.uns[f"{key_added}_params"] = {
            "rank": int(self.rank),
            "method": self.method,
            "init": self.init,
            "max_iter": int(self.n_iter or 0),
            "n_genes": int(self.W.shape[0]),
            "n_cells": int(self.H.shape[1]),
        }
        adata.uns[f"{key_added}_top_genes"] = top_genes_df

        return {
            "usage_norm": usage_norm,
            "gep_scores": gep_scores,
            "top_genes": top_genes_df,
        }

    def get_results_rfc(
        self,
        adata: AnnData,
        result_dict: Optional[dict] = None,
        *,
        threshold: float = 0.5,
        use_rep: str = "scaled|original|X_pca",
        key_added: str = "NMF_module_rfc",
        n_estimators: int = 100,
        random_state: int = 0,
    ):
        """Random-forest-classifier module assignment (cNMF-style).

        Cells with a single dominant factor (max usage > ``threshold``) are
        used as primary training examples. A random forest is trained to
        predict module membership from cell embeddings (``adata.obsm[use_rep]``);
        the trained model is then applied to all cells, including the
        ambiguous ones.

        Adds ``adata.obs[key_added]`` (categorical module assignment).
        """
        try:
            from sklearn.ensemble import RandomForestClassifier
        except ImportError as e:
            raise ImportError("get_results_rfc requires scikit-learn") from e
        if self.W is None:
            raise RuntimeError("call fit() first")
        if result_dict is None:
            result_dict = self.get_results(adata)
        usage = result_dict["usage_norm"].reindex(adata.obs_names)
        max_use = usage.max(axis=1)
        pseudo_label = np.argmax(usage.to_numpy(), axis=1) + 1
        pseudo_label[max_use < threshold] = 0  # ambiguous → 0, exclude from train

        if use_rep not in adata.obsm:
            raise KeyError(
                f"use_rep '{use_rep}' not in adata.obsm; pick one of {list(adata.obsm)}"
            )
        X = np.asarray(adata.obsm[use_rep])
        train_mask = pseudo_label > 0
        if train_mask.sum() < 10:
            raise RuntimeError(
                "Fewer than 10 cells pass `threshold` — try lowering it"
            )
        clf = RandomForestClassifier(
            n_estimators=n_estimators, random_state=random_state, n_jobs=-1
        )
        clf.fit(X[train_mask], pseudo_label[train_mask])
        pred = clf.predict(X)
        labels = [f"M{m}" for m in pred]
        # Only include categories the RFC actually predicted, otherwise
        # downstream `ov.pl.dotplot(..., standard_scale='var')` divides by
        # zero on empty groups.
        seen = sorted(
            {f"M{m}" for m in pred},
            key=lambda s: int(s[1:]),
        )
        adata.obs[key_added] = pd.Categorical(labels, categories=seen)
        return clf

    # ------ Visualisation --------------------------------------------------

    def plot_top_genes(
        self,
        n_top: int = 10,
        *,
        figsize: Tuple[int, int] = (10, 6),
        cmap: str = "Reds",
    ):
        """Heatmap of top genes per factor (genes × factors)."""
        if self.W is None:
            raise RuntimeError("call fit() first")
        import matplotlib.pyplot as plt
        rank = self.W.shape[1]
        # Pick the union of top-n genes per factor (with tie-break on max W).
        top_per = [np.argsort(-self.W[:, k])[:n_top] for k in range(rank)]
        chosen = []
        seen = set()
        for col_top in top_per:
            for idx in col_top:
                if idx not in seen:
                    seen.add(idx); chosen.append(idx)
        chosen = np.array(chosen)
        sub = self.W[chosen, :]
        sub = sub / np.maximum(sub.max(axis=0, keepdims=True), 1e-12)  # column-scale to [0,1]

        fig, ax = plt.subplots(figsize=figsize)
        im = ax.imshow(sub, aspect="auto", cmap=cmap)
        ax.set_xticks(np.arange(rank))
        ax.set_xticklabels([f"F{k+1}" for k in range(rank)])
        ax.set_yticks(np.arange(len(chosen)))
        ax.set_yticklabels(self.var_names[chosen], fontsize=7)
        ax.set_xlabel("factor")
        ax.set_title(f"Top {n_top} genes per factor (W loadings, column-scaled)")
        fig.colorbar(im, ax=ax, label="loading")
        fig.tight_layout()
        return ax

    def consensus(
        self,
        *,
        n_runs: int = 50,
        method: Optional[str] = None,
        max_iter: int = 50,
        sparsity: float = 0.0,
        smoothness: float = 0.0,
        seed: int = 0,
    ) -> np.ndarray:
        """Compute the cNMF-style spectra consensus.

        Following the canonical Brunet 2003 / cNMF (Kotliar 2019) recipe:
        run NMF ``n_runs`` times with different random seeds → collect all
        ``n_runs · K`` factor vectors (each one length-`n_genes`) →
        compute the pair-wise Euclidean distance matrix between them →
        cluster the spectra into K groups via k-means → reorder by cluster.

        A perfectly stable factorisation produces K tight clusters of
        spectra and the distance matrix renders as **K dark blocks on the
        diagonal against a bright background** — the canonical figure from
        the Brunet PNAS 2003 paper that cNMF reproduces.

        Parameters
        ----------
        n_runs : int, default 50
            Number of independent NMF runs. cNMF uses 200; 30-50 is
            usually enough to see the block structure.
        method : str, optional
            Algorithm to run; falls back to ``self.method``.
        max_iter : int
            Iterations per run.

        Returns
        -------
        spectra_dist : (n_runs·K, n_runs·K) np.ndarray of pair-wise distances.

        Side effects
        ------------
        Sets ``self._spectra_dist``, ``self._spectra_labels`` (k-means
        cluster IDs, length n_runs·K), and ``self._spectra_order`` (the
        sort order to use when plotting). Use :meth:`plot_consensus_heatmap`
        to render.
        """
        nmf_rs = _import_nmf_rs()
        if self._V is None:
            self._V = _to_dense_genes_x_cells(self._adata_view, self.layer)
        method = method or self.method or "dnmf"
        K = self.rank
        rng = np.random.default_rng(seed)

        kw_extras = {}
        if method.lower() in {"snmf/r", "snmf_r", "snmfr", "snmf/l", "snmf_l",
                               "snmfl", "dnmf", "rcppml", "diag_nmf"}:
            kw_extras["sparsity"] = float(sparsity)
            kw_extras["smoothness"] = float(smoothness)

        # Stack all factors from all runs as columns of a (n_genes × n_runs·K) matrix.
        spectra_cols: List[np.ndarray] = []
        for run in range(n_runs):
            run_seed = int(rng.integers(0, 2**31 - 1))
            W0, H0 = nmf_rs.random_init(self._V, K, seed=run_seed)
            res = nmf_rs.nmf(
                self._V, rank=K, method=method,
                W0=W0, H0=H0, max_iter=int(max_iter),
                num_threads=self.num_threads,
                **kw_extras,
            )
            # L2-normalise each factor column so the distance is direction-only.
            W = res.W
            norms = np.linalg.norm(W, axis=0, keepdims=True)
            norms = np.where(norms > 0, norms, 1.0)
            spectra_cols.append(W / norms)
        spectra = np.hstack(spectra_cols)             # (n_genes, n_runs * K)

        # Pair-wise distance (Euclidean on L2-normalised vectors ≈ angular distance).
        from scipy.spatial.distance import pdist, squareform
        dist = squareform(pdist(spectra.T, metric="euclidean"))

        # K-means cluster the n_runs·K spectra into K groups, using the
        # raw direction vectors. This is what cNMF does at consensus stage.
        try:
            from sklearn.cluster import KMeans
        except ImportError as e:
            raise ImportError(
                "consensus() requires scikit-learn (pip install scikit-learn)"
            ) from e
        km = KMeans(n_clusters=K, n_init=10, random_state=int(seed))
        labels = km.fit_predict(spectra.T)

        # Sort: cluster id, then by intra-cluster distance to the centroid
        # (more representative spectra come first within each block).
        centroid_dist = np.array([
            np.linalg.norm(spectra[:, i] - km.cluster_centers_[labels[i]])
            for i in range(spectra.shape[1])
        ])
        order = np.lexsort((centroid_dist, labels))

        self._spectra_dist = dist
        self._spectra_labels = labels
        self._spectra_order = order
        return dist

    def plot_consensus_heatmap(
        self,
        *,
        figsize: Tuple[int, int] = (6.5, 5.5),
        cmap: str = "viridis",
        cluster_cmap: str = "Spectral",
    ):
        """Render the cNMF-style consensus heatmap.

        Layout matches the cNMF tutorial:

        - **Top + left tracks**: K-means cluster colour assignment of the
          spectra (Spectral palette).
        - **Main panel**: pair-wise Euclidean distance between spectra,
          re-ordered so cells in the same cluster are adjacent. Tight
          clusters → small intra-block distance → dark diagonal blocks.
        - **Right colourbar**: distance scale.

        A perfectly stable factorisation produces K dark blocks on the
        diagonal; instability shows as bright crossings.
        """
        if not hasattr(self, "_spectra_dist"):
            raise RuntimeError("call .consensus() first")
        import matplotlib.pyplot as plt
        from matplotlib import gridspec

        D = self._spectra_dist[self._spectra_order, :][:, self._spectra_order]
        cluster_track = self._spectra_labels[self._spectra_order].reshape(-1, 1)

        # Layout — width_ratios mirror the cNMF tutorial: thin track + main +
        # gap + colourbar slot. height_ratios: thin track + main.
        width_ratios = [0.18, 4.0, 0.4, 0.18]
        height_ratios = [0.18, 4.0]
        fig = plt.figure(
            figsize=(sum(width_ratios) / 4.0 * figsize[0],
                     sum(height_ratios) / 4.0 * figsize[1])
        )
        gs = gridspec.GridSpec(
            2, 4, figure=fig,
            left=0.04, bottom=0.05, right=0.97, top=0.92,
            width_ratios=width_ratios, height_ratios=height_ratios,
            wspace=0.0, hspace=0.0,
        )
        # Top cluster track.
        ax_top = fig.add_subplot(gs[0, 1], frameon=True)
        ax_top.imshow(cluster_track.T, aspect="auto",
                      cmap=cluster_cmap, interpolation="nearest", rasterized=True)
        ax_top.set_xticks([]); ax_top.set_yticks([])
        # Left cluster track.
        ax_left = fig.add_subplot(gs[1, 0], frameon=True)
        ax_left.imshow(cluster_track, aspect="auto",
                       cmap=cluster_cmap, interpolation="nearest", rasterized=True)
        ax_left.set_xticks([]); ax_left.set_yticks([])
        # Main distance heatmap.
        ax_main = fig.add_subplot(gs[1, 1], frameon=True)
        im = ax_main.imshow(
            D, aspect="auto", cmap=cmap,
            interpolation="nearest", rasterized=True,
        )
        ax_main.set_xticks([]); ax_main.set_yticks([])
        # Colourbar — sit it in a smaller cell next to the main panel.
        ax_cb = fig.add_subplot(gs[1, 3])
        cb = fig.colorbar(im, cax=ax_cb)
        cb.ax.tick_params(labelsize=8)
        cb.set_label("Euclidean distance", fontsize=9)
        # Title — placed centred via a separate axes so it doesn't push the
        # main panel down.
        fig.suptitle(
            f"cNMF-style spectra consensus  (method={self.method}, "
            f"K={self.rank}, n_runs={D.shape[0] // self.rank})",
            fontsize=10,
        )
        return ax_main

    def plot_loss(self, ax=None, *, figsize: Tuple[int, int] = (5, 3)):
        """Plot the ``deviances`` trace (only available when ``stop='stationary'``)."""
        if self.deviances is None or len(self.deviances) == 0:
            raise RuntimeError(
                "no deviance trace available — fit with stop='stationary' to record one"
            )
        import matplotlib.pyplot as plt
        if ax is None:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.figure
        ax.plot(self.deviances, lw=1.5, color="#4477aa")
        ax.set_xlabel("iteration check")
        ax.set_ylabel("loss")
        ax.set_title(f"NMF loss trajectory ({self.method})")
        ax.grid(alpha=0.3)
        ax.set_yscale("log")
        fig.tight_layout()
        return ax

    def __repr__(self) -> str:
        s = (
            f"<omicverse.single.NMF rank={self.rank} method={self.method} "
            f"init={self.init} fitted={self.W is not None}>"
        )
        return s
