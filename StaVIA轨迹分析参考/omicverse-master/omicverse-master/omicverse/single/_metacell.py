"""Unified MetaCell dispatcher for omicverse.

A single :class:`MetaCell` class wraps 7 backends behind a common
interface:

- ``seacells``    — kernel archetypal analysis (Persad et al., Nat Biotech 2023)
- ``metaq``       — VQ-VAE codebook (Li et al., Nat Commun 2025)
- ``mc2``         — MetaCell-2 divide-and-conquer (Ben-Kiki et al., Genome Biology 2022)
- ``supercell``   — kNN + walktrap (Bilous et al., BMC Bioinformatics 2022)
- ``kmeans``      — trivial baseline
- ``random``      — honest random baseline (Bilous et al. lower bound)
- ``geosketch``   — density-aware sketching (Hie et al., Cell Systems 2019)

Backward compatibility: the legacy SEACells-only signature
``MetaCell(adata, use_rep, n_metacells, use_gpu=...)`` is preserved; if
``method`` is omitted it defaults to ``'seacells'`` and
``adata.obs['SEACell']`` is still written (alongside the new unified
``adata.obs['metacell_id']``).
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import scipy.sparse as sp

from .._registry import register_function
from .._settings import add_reference
from ._metacell_backends import (
    BACKEND_REGISTRY,
    FitResult,
    MetaCellBackend,
    UnsupportedCapability,
)
from ._metacell_backends.base import require


# ----------------------------------------------------------------------------
# Unified AnnData schema (written by .fit())
# ----------------------------------------------------------------------------
#  obs['metacell_id']  : Categorical (str)                        — universal
#  obs['SEACell']      : Categorical (str)                        — backward-compat, seacells only
#  obs['metacell_conf']: float in [0, 1]                          — universal
#  obsm['X_metacell']  : (n_cells, d)                             — if capability 'latent'
#  obsm['metacell_soft']: sparse (n_cells, n_metacells)           — if capability 'soft'
#  uns['metacell']     : dict(method, n_metacells, n_iter, ...)   — universal
# ----------------------------------------------------------------------------


def _legacy_seacells_kwargs(kwargs: dict) -> dict:
    """Strip legacy SEACells-only kwargs from a generic kwargs bag."""
    seacells_keys = {
        "use_gpu", "verbose", "n_waypoint_eigs", "n_neighbors",
        "convergence_epsilon", "l2_penalty", "max_franke_wolfe_iters",
        "use_sparse",
    }
    return {k: v for k, v in kwargs.items() if k in seacells_keys}


@register_function(
    aliases=["元细胞", "MetaCell", "metacell", "元细胞构建", "SEA细胞"],
    category="single",
    description=(
        "Construct metacells from single-cell data. 7 backends: seacells, "
        "metaq, mc2, supercell, kmeans, random, geosketch. Writes a unified "
        "schema (obs['metacell_id'], uns['metacell']) consumed by all "
        "downstream tools."
    ),
    requires={
        "obsm": [
            "low-dim embedding via use_rep, e.g. X_pca "
            "(graph backends: seacells / supercell / kmeans / geosketch)",
        ],
        "layers": [
            "raw counts via layer, e.g. counts "
            "(deep backends: metaq / mc2)",
        ],
    },
    produces={
        "obs": ["metacell_id", "metacell_conf"],
        "obsm": ["X_metacell", "metacell_soft"],
        "uns": ["metacell"],
    },
    auto_fix="none",
    examples=[
        "# SEACells (legacy default)",
        "mc = ov.single.MetaCell(adata, use_rep='X_pca', n_metacells=200).fit()",
        "ad_mc = mc.predicted(method='soft')",
        "",
        "# MetaQ (VQ-VAE, 100x faster, supports out-of-sample)",
        "mc = ov.single.MetaCell(adata, method='metaq', n_metacells=500,",
        "                         device='cuda').fit()",
        "ad_mc = mc.predicted()",
        "mc.assign_new_cells(adata_query)",
        "",
        "# Honest baseline: random + geosketch",
        "mc_rand = ov.single.MetaCell(adata, method='random', n_metacells=200).fit()",
        "mc_sk   = ov.single.MetaCell(adata, method='geosketch', n_metacells=200).fit()",
        "",
        "# Validate any partition",
        "rep = mc.check_rigor(n_rep=50)",
        "print(rep.dubious_rate, rep.score)",
    ],
    related=["single.optimize_granularity", "single.compare_metacell_backends",
             "single.get_obs_value", "single.plot_metacells"],
)
class MetaCell(object):
    """Unified metacell wrapper with dispatchable backends.

    Parameters
    ----------
    adata
        Input single-cell AnnData.
    method
        Backend key.  One of ``'seacells'`` (default, backward-compatible),
        ``'metaq'``, ``'mc2'``, ``'supercell'``, ``'kmeans'``, ``'random'``,
        ``'geosketch'``.
    use_rep
        Embedding key in ``adata.obsm``.  Used by graph-based backends
        (``seacells``/``supercell``/``kmeans``/``geosketch``).  MetaQ and
        MC2 derive their own representations and ignore this.
    n_metacells
        Target number of metacells.  Default ``adata.n_obs // 75``.
    layer
        Counts layer for backends that need raw counts (MetaQ, MC2).
    device
        ``'cpu'``, ``'cuda'``, or ``'mps'`` for GPU-capable backends.
    random_state
        Seed forwarded to all backends.
    **kwargs
        Forwarded to the backend constructor.  See each backend's
        docstring for valid kwargs.
    """

    def __init__(
        self,
        adata,
        method: str = "seacells",
        use_rep: str = "X_pca",
        n_metacells: Optional[int] = None,
        layer: Optional[str] = None,
        device: str = "cpu",
        random_state: int = 0,
        **kwargs,
    ):
        if method not in BACKEND_REGISTRY:
            raise ValueError(
                f"Unknown backend method={method!r}. "
                f"Available: {sorted(BACKEND_REGISTRY)}"
            )

        self.adata = adata
        self.method = method
        self.use_rep = use_rep
        self.n_metacells = n_metacells or (adata.n_obs // 75)
        self.layer = layer
        self.device = device
        self.random_state = random_state

        # Backward-compat: SEACells uses 'use_gpu' instead of 'device'.
        if method == "seacells" and "use_gpu" not in kwargs:
            kwargs["use_gpu"] = device != "cpu"

        # Per-backend kwarg construction (some accept use_rep, some don't).
        bcls = BACKEND_REGISTRY[method]
        common = dict(
            adata=adata,
            n_metacells=self.n_metacells,
            random_state=random_state,
        )
        if method in {"seacells", "supercell", "kmeans", "geosketch"}:
            common["use_rep"] = use_rep
        if method in {"seacells", "metaq"}:
            common["device"] = device
        if method == "metaq":
            common["layer"] = layer
        if method == "mc2":
            # n_metacells → target_metacell_size mapping if user only passed one.
            kwargs.setdefault("target_metacell_size",
                              max(1, adata.n_obs // self.n_metacells))

        self.backend: MetaCellBackend = bcls(**common, **kwargs)
        self._fit_result: Optional[FitResult] = None
        self._predicted_ad = None
        self._init_kwargs = kwargs

    # ------------------------------------------------------------------
    # Universal: fit / predicted / metrics / save / load
    # ------------------------------------------------------------------

    def fit(self, **kwargs) -> "MetaCell":
        """Train the chosen backend; write unified schema into ``adata``.

        Returns ``self`` so the call chains: ``mc = MetaCell(...).fit()``.
        """
        self._fit_result = self.backend.fit(**kwargs)
        self._write_schema()
        add_reference(
            self.adata,
            f"MetaCell ({self.method})",
            f"metacell construction with {self.method}",
        )
        return self

    def _write_schema(self):
        """Write the universal schema into ``self.adata`` based on FitResult."""
        if self._fit_result is None:
            return
        r = self._fit_result
        labels = pd.Categorical([f"mc-{i}" for i in r.assignments])
        self.adata.obs["metacell_id"] = labels

        if self.method == "seacells":
            # Keep backward-compat column populated alongside the new one.
            if "SEACell" not in self.adata.obs:
                self.adata.obs["SEACell"] = labels.astype(str)

        # Confidence: per-cell.  Backends that have soft can derive it.
        if r.soft is not None and sp.issparse(r.soft):
            conf = np.asarray(r.soft.max(axis=1).todense()).ravel()
        else:
            conf = np.ones(r.assignments.shape[0], dtype=np.float32)
        self.adata.obs["metacell_conf"] = conf

        if r.latent is not None:
            self.adata.obsm["X_metacell"] = np.asarray(r.latent)

        if r.soft is not None:
            self.adata.obsm["metacell_soft"] = r.soft

        self.adata.uns["metacell"] = {
            "method": self.method,
            "n_metacells": int(np.unique(r.assignments).size),
            "n_iter": int(r.n_iter),
            "converged": bool(r.converged),
            "runtime_s": float(r.runtime_s),
            "random_state": int(self.random_state),
            "capabilities": sorted(self.capabilities),
        }

    def predicted(
        self,
        method: str = "hard",
        layer: Optional[str] = "raw",
        summary: str = "sum",
        celltype_label: Optional[str] = None,
        minimum_weight: float = 0.05,
        **kwargs,
    ):
        """Aggregate single cells into a metacell-level AnnData.

        Parameters
        ----------
        method
            ``'hard'`` (argmax) or ``'soft'`` (weighted by membership; needs
            capability ``'soft'``).
        layer
            Layer to aggregate.  ``'raw'`` uses ``adata.X``; otherwise
            ``adata.layers[layer]``.
        summary
            ``'sum'`` (default — preserves count totals; downstream-friendly
            for SCENIC/CellPhoneDB/pseudobulk-DE) or ``'mean'``.
        celltype_label
            ``adata.obs`` column to propagate via majority vote.  Adds
            ``ad_mc.obs['<celltype_label>']`` and
            ``ad_mc.obs['<celltype_label>_purity']``.
        minimum_weight
            Drop soft contributions below this weight (soft method only).
        """
        if self._fit_result is None:
            raise RuntimeError("Call .fit() before .predicted().")

        import anndata as ad

        # Universal soft path uses any FitResult.soft (no SEACells dep needed),
        # so it works for metaq too.
        if method == "soft":
            require(self.backend, "soft")
            return self._predicted_soft(
                layer=layer, summary=summary,
                celltype_label=celltype_label, minimum_weight=minimum_weight,
            )

        return self._predicted_hard(
            layer=layer, summary=summary, celltype_label=celltype_label,
        )

    def _get_counts(self, layer: Optional[str]):
        if layer in (None, "raw"):
            X = self.adata.X
        elif layer in self.adata.layers:
            X = self.adata.layers[layer]
        else:
            raise KeyError(f"layer={layer!r} not in adata.layers (or not 'raw').")
        return X

    def _predicted_hard(self, layer, summary, celltype_label):
        import anndata as ad
        X = self._get_counts(layer)
        labels = self._fit_result.assignments
        uniq = np.unique(labels)
        n_mc = len(uniq)

        # Per-metacell row sum/mean by sparse matrix multiplication.
        n_cells = self.adata.n_obs
        rows = np.arange(n_cells)
        cols = np.searchsorted(uniq, labels)
        if summary == "sum":
            data = np.ones(n_cells)
        elif summary == "mean":
            counts = np.bincount(cols, minlength=n_mc)
            data = 1.0 / np.maximum(counts[cols], 1)
        else:
            raise ValueError(f"summary must be 'sum' or 'mean', got {summary!r}")
        P = sp.csr_matrix((data, (cols, rows)), shape=(n_mc, n_cells))
        X_mc = P @ X
        if sp.issparse(X_mc):
            X_mc = X_mc.tocsr()

        out = ad.AnnData(X=X_mc, var=self.adata.var.copy())
        out.obs.index = [f"mc-{u}" for u in uniq]
        out.obs["n_cells"] = np.bincount(cols, minlength=n_mc)
        if celltype_label and celltype_label in self.adata.obs:
            self._add_majority(out, labels, uniq, celltype_label)
        out.uns["source"] = {
            "method": self.method,
            "n_source_cells": int(n_cells),
            "aggregation": f"{summary} (hard)",
            "layer": layer or "X",
        }
        self._predicted_ad = out
        return out

    def _predicted_soft(self, layer, summary, celltype_label, minimum_weight):
        """Soft aggregation, matching SEACells.summarize_by_soft_SEACell.

        For metacell ``m`` with per-cell soft weights ``w_cm``:

        - ``summary='mean'`` → weighted mean  ``Σ_c w_cm · X_c / Σ_c w_cm``
          (this is exactly what the upstream SEACells soft summary does).
        - ``summary='sum'``  → weighted sum   ``Σ_c w_cm · X_c``.
          Because each cell's weights sum to 1 across metacells, the weighted
          sum conserves total counts (``Σ_m X_mc == Σ_c X_c``) — the right
          "pseudo-raw count" semantics for SCENIC / pseudobulk DE.
        """
        import anndata as ad
        soft = self._fit_result.soft.copy().tocsr()
        if minimum_weight > 0:
            soft.data[soft.data < minimum_weight] = 0
            soft.eliminate_zeros()
        # Re-normalise rows so each cell's weights sum to 1 across metacells.
        row_sum = np.asarray(soft.sum(axis=1)).ravel()
        row_sum[row_sum == 0] = 1
        soft = sp.diags(1.0 / row_sum) @ soft

        X = self._get_counts(layer)
        # Weighted sum: X_mc[m, g] = Σ_c soft[c, m] * X[c, g].
        X_mc = soft.T @ X
        if summary == "mean":
            # Divide by per-metacell weight sum → weighted mean (SEACells parity).
            eff = np.asarray(soft.sum(axis=0)).ravel()
            eff[eff == 0] = 1.0
            X_mc = sp.diags(1.0 / eff) @ X_mc
        elif summary != "sum":
            raise ValueError(f"summary must be 'sum' or 'mean', got {summary!r}")
        # summary == 'sum': X_mc is already the weighted sum — no rescaling.
        if sp.issparse(X_mc):
            X_mc = X_mc.tocsr()

        n_mc = soft.shape[1]
        out = ad.AnnData(X=X_mc, var=self.adata.var.copy())
        out.obs.index = [f"mc-{i}" for i in range(n_mc)]
        out.obs["n_cells"] = np.asarray((soft > 0).sum(axis=0)).ravel().astype(int)

        if celltype_label and celltype_label in self.adata.obs:
            hard = self._fit_result.assignments
            uniq = np.arange(n_mc)
            self._add_majority(out, hard, uniq, celltype_label)

        out.uns["source"] = {
            "method": self.method,
            "n_source_cells": int(self.adata.n_obs),
            "aggregation": f"{summary} (soft, top-k from {self.method})",
            "layer": layer or "X",
        }
        self._predicted_ad = out
        return out

    def _add_majority(self, out_ad, labels, uniq, key):
        col = self.adata.obs[key].astype(str)
        majority = []
        purity = []
        for u in uniq:
            sub = col.iloc[np.where(labels == u)[0]]
            if len(sub) == 0:
                majority.append("")
                purity.append(np.nan)
                continue
            vc = sub.value_counts()
            majority.append(vc.index[0])
            purity.append(vc.iloc[0] / len(sub))
        out_ad.obs[key] = majority
        out_ad.obs[f"{key}_purity"] = purity

    # ----------------------- universal metrics -------------------------

    def compute_purity(self, label_key: str = "celltype") -> pd.DataFrame:
        """Per-metacell majority-label purity."""
        if self._fit_result is None:
            raise RuntimeError("Call .fit() first.")
        labels = self._fit_result.assignments
        col = self.adata.obs[label_key].astype(str)
        rows = []
        for u in np.unique(labels):
            sub = col.iloc[np.where(labels == u)[0]]
            vc = sub.value_counts()
            rows.append((int(u), int(len(sub)), vc.index[0] if len(vc) else "",
                         float(vc.iloc[0] / len(sub)) if len(vc) else np.nan))
        return pd.DataFrame(rows, columns=["metacell_id", "size", "majority", "purity"])

    def compute_separation(self, use_rep: Optional[str] = None,
                           label_key: Optional[str] = None) -> pd.DataFrame:
        """Mean intra/inter-metacell distance ratio per metacell (lower = more separated)."""
        from sklearn.neighbors import NearestNeighbors
        if self._fit_result is None:
            raise RuntimeError("Call .fit() first.")
        rep = use_rep or self.use_rep
        if rep not in self.adata.obsm:
            raise KeyError(f"use_rep={rep!r} missing from adata.obsm.")
        X = np.asarray(self.adata.obsm[rep])
        labels = self._fit_result.assignments
        nn = NearestNeighbors(n_neighbors=2).fit(X)
        d, idx = nn.kneighbors(X)
        same = labels[idx[:, 1]] == labels
        rows = []
        for u in np.unique(labels):
            mask = labels == u
            rows.append((int(u), int(mask.sum()),
                         float(d[mask, 1].mean()),
                         float(same[mask].mean())))
        return pd.DataFrame(rows, columns=["metacell_id", "size", "mean_1nn_dist",
                                           "frac_1nn_same_metacell"])

    def compute_compactness(self, use_rep: Optional[str] = None) -> pd.DataFrame:
        """Per-metacell mean pairwise distance in ``use_rep`` (lower = more compact)."""
        if self._fit_result is None:
            raise RuntimeError("Call .fit() first.")
        rep = use_rep or self.use_rep
        if rep not in self.adata.obsm:
            raise KeyError(f"use_rep={rep!r} missing from adata.obsm.")
        X = np.asarray(self.adata.obsm[rep])
        labels = self._fit_result.assignments
        rows = []
        for u in np.unique(labels):
            ix = np.where(labels == u)[0]
            if ix.size < 2:
                rows.append((int(u), int(ix.size), 0.0))
                continue
            sub = X[ix]
            centroid = sub.mean(axis=0)
            rows.append((int(u), int(ix.size),
                         float(np.linalg.norm(sub - centroid, axis=1).mean())))
        return pd.DataFrame(rows, columns=["metacell_id", "size", "mean_centroid_dist"])

    # ----------------------- capability-gated --------------------------

    @property
    def capabilities(self) -> set:
        return set(self.backend.capabilities)

    @classmethod
    def capability_matrix(cls) -> pd.DataFrame:
        all_caps = sorted({c for b in BACKEND_REGISTRY.values() for c in getattr(b, "capabilities", set())})
        rows = []
        for name, b in BACKEND_REGISTRY.items():
            caps = set(getattr(b, "capabilities", set()))
            rows.append({"backend": name, **{c: c in caps for c in all_caps}})
        return pd.DataFrame(rows).set_index("backend")

    def soft_membership(self) -> sp.csr_matrix:
        require(self.backend, "soft",
                alternatives=[k for k, b in BACKEND_REGISTRY.items()
                              if "soft" in getattr(b, "capabilities", set())])
        return self.backend.soft_membership()

    def latent(self) -> np.ndarray:
        require(self.backend, "latent",
                alternatives=[k for k, b in BACKEND_REGISTRY.items()
                              if "latent" in getattr(b, "capabilities", set())])
        return self.backend.latent()

    def codebook(self) -> np.ndarray:
        require(self.backend, "codebook",
                alternatives=[k for k, b in BACKEND_REGISTRY.items()
                              if "codebook" in getattr(b, "capabilities", set())])
        return self.backend.codebook()

    def assign_new_cells(self, adata_query) -> dict:
        require(self.backend, "out_of_sample",
                alternatives=[k for k, b in BACKEND_REGISTRY.items()
                              if "out_of_sample" in getattr(b, "capabilities", set())])
        return self.backend.assign_new_cells(adata_query)

    def fit_multi_gamma(self, gammas: list) -> dict:
        require(self.backend, "hierarchical",
                alternatives=[k for k, b in BACKEND_REGISTRY.items()
                              if "hierarchical" in getattr(b, "capabilities", set())])
        return self.backend.fit_multi_gamma(gammas)

    # ----------------------- rigor (orthogonal) ------------------------

    def check_rigor(
        self,
        layer_lognorm: Optional[str] = None,
        feature_use: int = 2000,
        gene_filter: float = 0.1,
        n_rep: int = 50,
        test_cutoff: float = 0.01,
        thre_smooth: bool = True,
        thre_bw: float = 1 / 6,
        weight: float = 0.5,
        random_state: Optional[int] = None,
    ):
        """Score the rigor of the current partition (mcRigor port).

        Works on any backend.  Uses log-normalised expression: if
        ``layer_lognorm`` is None, expects ``adata.X`` to be already
        log-normalised (e.g. after ``ov.pp.preprocess``); otherwise reads
        ``adata.layers[layer_lognorm]``.
        """
        from ..external.mcRigor import rigor_detect

        if self._fit_result is None:
            raise RuntimeError("Call .fit() first.")

        X = self.adata.layers[layer_lognorm] if layer_lognorm else self.adata.X
        return rigor_detect(
            X,
            self._fit_result.assignments,
            feature_use=feature_use,
            gene_filter=gene_filter,
            n_rep=n_rep,
            test_cutoff=test_cutoff,
            thre_smooth=thre_smooth,
            thre_bw=thre_bw,
            weight=weight,
            random_state=self.random_state if random_state is None else random_state,
        )

    # ----------------------- save / load -------------------------------

    def save(self, path: str) -> None:
        self.backend.save(path)

    def load(self, path: str) -> None:
        self.backend.load(path)
        # Replay write_schema from backend assignments if available.
        if hasattr(self.backend, "assignments") and self.backend.assignments is not None:
            self._fit_result = FitResult(assignments=self.backend.assignments,
                                         n_iter=1, converged=True, runtime_s=0.0)
            self._write_schema()

    # ----------------------- legacy API shims --------------------------

    def initialize_archetypes(self, **kwargs):
        """Legacy SEACells shim.  Folded into ``.fit()`` for all backends."""
        if self.method != "seacells":
            warnings.warn(
                "initialize_archetypes() is a SEACells legacy hook; ignored "
                f"for backend {self.method!r}.  Call .fit() instead.",
                DeprecationWarning,
            )
            return
        from ..external.SEACells.core import SEACells
        # Lazy-init the model so .train() can run.
        if self.backend.model is None:
            self.backend.model = SEACells(
                self.adata,
                build_kernel_on=self.use_rep,
                n_SEACells=self.n_metacells,
                use_gpu=(self.device != "cpu"),
                **self.backend._init_kwargs,
            )
        self.backend.model.construct_kernel_matrix()
        self.backend.M = self.backend.model.kernel_matrix
        self.backend.model.initialize_archetypes(**kwargs)

    def train(self, min_iter=10, max_iter=50, **kwargs):
        """Legacy SEACells shim → ``.fit()``."""
        if self.method == "seacells":
            kwargs["min_iter"] = min_iter
            kwargs["max_iter"] = max_iter
        else:
            warnings.warn(
                f"train(min_iter, max_iter) is SEACells-specific; for backend "
                f"{self.method!r} use .fit(**backend_kwargs).",
                DeprecationWarning,
            )
        return self.fit(**kwargs)

    def step(self, n_steps: int = 5):
        """Legacy SEACells shim — only meaningful for the seacells backend."""
        if self.method != "seacells":
            warnings.warn(
                f".step() is SEACells-specific; ignored for {self.method!r}.",
                DeprecationWarning,
            )
            return
        m = self.backend.model
        for _ in range(n_steps):
            m.step()

    def compute_celltype_purity(self, celltype_label: str = "celltype"):
        """Legacy alias → ``compute_purity``."""
        return self.compute_purity(celltype_label)

    def separation(self, use_rep: str = "X_pca", nth_nbr: int = 1, **kwargs):
        """Legacy alias → ``compute_separation``."""
        return self.compute_separation(use_rep=use_rep)

    def compactness(self, use_rep: str = "X_pca", **kwargs):
        """Legacy alias → ``compute_compactness``."""
        return self.compute_compactness(use_rep=use_rep)


# ----------------------------------------------------------------------------
# Top-level helpers
# ----------------------------------------------------------------------------


@register_function(
    aliases=["选择最优粒度", "optimize_metacell_granularity", "γ优化", "granularity_optimize"],
    category="single",
    description=(
        "Sweep n_metacells values and pick the best granularity via mcRigor's "
        "Score (dubious-rate / zero-rate trade-off). Returns (best_n, sweep)."
    ),
    requires={
        "obsm": ["low-dim embedding via use_rep, e.g. X_pca"],
        "layers": ["log-normalised expression via layer_lognorm (optional; "
                   "defaults to adata.X)"],
    },
    produces={},
    auto_fix="none",
    examples=[
        "best_n, sweep = ov.single.optimize_granularity(adata, method='metaq',",
        "    n_metacells_grid=[50, 100, 200, 500, 1000], weight=0.5)",
    ],
    related=["single.MetaCell", "single.compare_metacell_backends"],
)
def optimize_granularity(
    adata,
    method: str = "seacells",
    n_metacells_grid: Optional[List[int]] = None,
    weight: float = 0.5,
    optim_method: str = "tradeoff",
    use_rep: str = "X_pca",
    layer_lognorm: Optional[str] = None,
    random_state: int = 0,
    **backend_kwargs,
):
    """Sweep ``n_metacells`` and return the optimal value per mcRigor.

    Returns
    -------
    (best_n, sweep)
        ``best_n``: int — optimal ``n_metacells``.
        ``sweep``: ``pd.DataFrame`` with columns
        ``[n_metacells, dubious_rate, zero_rate, score]``.
    """
    from ..external.mcRigor import rigor_optimize

    if n_metacells_grid is None:
        n_metacells_grid = [50, 100, 200, 500, 1000]

    memberships = {}
    for n_mc in n_metacells_grid:
        mc = MetaCell(adata, method=method, use_rep=use_rep,
                      n_metacells=n_mc, random_state=random_state,
                      **backend_kwargs).fit()
        memberships[n_mc] = mc._fit_result.assignments

    X = adata.layers[layer_lognorm] if layer_lognorm else adata.X
    rep = rigor_optimize(
        X, memberships,
        optim_method=optim_method,
        weight=weight,
        random_state=random_state,
    )
    return rep.best_n_metacells, rep.sweep


@register_function(
    aliases=["对比元细胞方法", "compare_metacell", "benchmark_metacell", "元细胞benchmark"],
    category="single",
    description=(
        "Honest baseline comparison: run multiple metacell backends on the "
        "same adata and report runtime + rigor + purity side-by-side. "
        "Returns a per-backend benchmark DataFrame (adata is not modified)."
    ),
    requires={
        "obsm": ["low-dim embedding via use_rep, e.g. X_pca"],
        "layers": ["raw counts via layer (e.g. counts)",
                   "log-normalised expression via layer_lognorm"],
    },
    produces={},
    auto_fix="none",
    examples=[
        "df = ov.single.compare_metacell_backends(",
        "    adata, backends=['seacells', 'metaq', 'kmeans', 'random', 'geosketch'],",
        "    n_metacells=200, use_rep='X_pca', eval_label='celltype')",
    ],
    related=["single.MetaCell", "single.optimize_granularity"],
)
def compare_metacell_backends(
    adata,
    backends: Optional[List[str]] = None,
    n_metacells: int = 200,
    use_rep: str = "X_pca",
    layer: Optional[str] = None,
    layer_lognorm: Optional[str] = None,
    eval_label: Optional[str] = "celltype",
    device: str = "cpu",
    random_state: int = 0,
    n_rigor_rep: int = 30,
    **backend_kwargs,
):
    """Side-by-side benchmark for the user's own data.

    For each backend, fits a metacell partition with the same
    ``n_metacells``, runs mcRigor, and computes purity / separation /
    compactness on a single result table.

    Returns
    -------
    ``pd.DataFrame`` indexed by backend name with columns
    ``[runtime_s, dubious_rate, rigor_score, mean_purity, mean_compactness, n_metacells]``.
    """
    if backends is None:
        backends = ["seacells", "metaq", "supercell", "kmeans", "random", "geosketch"]

    rows = []
    for name in backends:
        try:
            mc = MetaCell(
                adata.copy(),
                method=name,
                use_rep=use_rep,
                n_metacells=n_metacells,
                layer=layer,
                device=device,
                random_state=random_state,
                **{k: v for k, v in backend_kwargs.items()},
            ).fit()
        except Exception as exc:
            rows.append({
                "backend": name, "runtime_s": np.nan, "dubious_rate": np.nan,
                "rigor_score": np.nan, "mean_purity": np.nan,
                "mean_compactness": np.nan,
                "n_metacells": np.nan, "error": str(exc),
            })
            continue

        rep = mc.check_rigor(layer_lognorm=layer_lognorm, n_rep=n_rigor_rep)
        purity = np.nan
        if eval_label and eval_label in adata.obs:
            p = mc.compute_purity(eval_label)
            purity = float(p["purity"].mean())
        compactness = float(mc.compute_compactness(use_rep=use_rep)["mean_centroid_dist"].mean())

        rows.append({
            "backend": name,
            "runtime_s": float(mc._fit_result.runtime_s),
            "dubious_rate": float(rep.dubious_rate),
            "rigor_score": float(rep.score),
            "mean_purity": purity,
            "mean_compactness": compactness,
            "n_metacells": int(rep.n_metacells),
            "error": "",
        })

    return pd.DataFrame(rows).set_index("backend")


# ----------------------------------------------------------------------------
# Legacy helpers (plot + obs transfer) — unchanged
# ----------------------------------------------------------------------------


@register_function(
    aliases=["绘制元细胞", "plot_metacells", "metacell_plot", "元细胞绘图", "可视化元细胞"],
    category="single",
    description="Plot metacells on existing axis with customizable visualization parameters",
    examples=[
        "import matplotlib.pyplot as plt",
        "fig, ax = plt.subplots(figsize=(6, 6))",
        "ov.single.plot_metacells(ax, metacells_ad, use_rep='X_umap')",
    ],
    related=["single.MetaCell", "utils.embedding", "pl.embedding"],
)
def plot_metacells(ax, metacells_ad, use_rep="X_umap", color="#1f77b4",
                   size=15, edgecolors="b", linewidths=0.6, alpha=1, **kwargs):
    r"""Plot metacell centroids on a given embedding axis."""
    label_col = "metacell_id" if "metacell_id" in metacells_ad.obs else "SEACell"
    umap = (
        pd.DataFrame(metacells_ad.obsm[use_rep])
        .set_index(metacells_ad.obs_names)
        .join(metacells_ad.obs[label_col])
    )
    umap[label_col] = umap[label_col].astype("category")
    mcs = umap.groupby(label_col).mean().reset_index()

    ax.scatter(mcs[0], mcs[1], s=size, c=color,
               edgecolors=edgecolors, linewidths=linewidths,
               alpha=alpha, **kwargs)
    return ax


@register_function(
    aliases=["获取观测值", "get_obs_value", "transfer_obs", "观测值转移", "元细胞注释转移"],
    category="single",
    description="Transfer observation values from single-cell to metacell data",
    examples=[
        "ov.single.get_obs_value(metacell_adata, original_adata, 'celltype', type='str')",
    ],
    related=["single.MetaCell", "single.plot_metacells", "utils.transfer_obs"],
)
def get_obs_value(ad, adata, groupby, type="int"):
    r"""Transfer per-cell annotations/statistics to metacells.

    Looks at ``adata.obs['metacell_id']`` (new schema) or ``'SEACell'``
    (legacy) for the cell → metacell mapping.
    """
    label_col = "metacell_id" if "metacell_id" in adata.obs else "SEACell"
    if type == "str":
        grouped = adata.obs.groupby(label_col)[groupby]
        labels = []
        for k in grouped.idxmax().index:
            labels.append(grouped.get_group(k).value_counts().index[0])
        ad.obs[groupby] = pd.Series(labels, index=grouped.idxmax().index).loc[ad.obs.index].values
    else:
        ad.obs[groupby] = (
            adata.obs.groupby(label_col)
            .agg({groupby: type})
            .loc[ad.obs.index][groupby]
            .tolist()
        )
    print(f"... {groupby} added to ad.obs[{groupby}]")
