"""SuperCell backend (Bilous et al., BMC Bioinformatics 2022).

Uses the in-tree pure-Python re-implementation at
``omicverse.external.supercell`` (kNN + walktrap on a chosen embedding).
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .base import FitResult, MetaCellBackend


class SuperCellBackend(MetaCellBackend):
    name = "supercell"
    capabilities = {"hierarchical"}

    def __init__(
        self,
        adata,
        use_rep: str = "X_pca",
        n_metacells: Optional[int] = None,
        k_knn: int = 5,
        metric: str = "cosine",
        walktrap_steps: int = 4,
        random_state: int = 0,
        **kwargs,
    ):
        self.adata = adata
        self.use_rep = use_rep
        self.n_metacells = n_metacells or (adata.n_obs // 75)
        self.k_knn = int(k_knn)
        self.metric = metric
        self.walktrap_steps = int(walktrap_steps)
        self.random_state = int(random_state)
        self._extra = kwargs
        self._sc_obj = None

    def _x(self) -> np.ndarray:
        if self.use_rep not in self.adata.obsm:
            raise KeyError(
                f"use_rep={self.use_rep!r} missing from adata.obsm; "
                "run a dimensionality reduction first (e.g. ov.pp.pca)."
            )
        return np.asarray(self.adata.obsm[self.use_rep])

    def fit(self, n_metacells: Optional[int] = None, **kwargs) -> FitResult:
        from ...external.supercell import SuperCell

        if n_metacells is not None:
            self.n_metacells = n_metacells

        t0 = time.time()
        self._sc_obj = SuperCell(
            self._x(),
            n_metacells=self.n_metacells,
            k_knn=self.k_knn,
            metric=self.metric,
            walktrap_steps=self.walktrap_steps,
            seed=self.random_state,
        ).fit()
        runtime = time.time() - t0

        return FitResult(
            assignments=self._sc_obj.membership.astype(np.int64),
            latent=self._x(),
            n_iter=1,
            converged=True,
            runtime_s=float(runtime),
        )

    # capability methods ----------------------------------------------------

    def fit_multi_gamma(self, gammas: list[float]) -> dict[float, FitResult]:
        """Cut the cached walktrap dendrogram at multiple γ values."""
        if self._sc_obj is None or self._sc_obj._dendro is None:
            raise RuntimeError("Call .fit() first.")
        out = {}
        n_cells = self.adata.n_obs
        for g in gammas:
            n_mc = max(1, int(round(n_cells / g)))
            self._sc_obj.refit(n_mc)
            out[float(g)] = FitResult(
                assignments=self._sc_obj.membership.astype(np.int64),
                n_iter=1,
                converged=True,
                runtime_s=0.0,
                backend_meta={"gamma": float(g), "n_metacells": n_mc},
            )
        return out

    # persistence -----------------------------------------------------------

    def save(self, path: str) -> None:
        import pickle
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "membership": None if self._sc_obj is None else self._sc_obj.membership,
                    "n_metacells": self.n_metacells,
                    "config": dict(
                        use_rep=self.use_rep,
                        k_knn=self.k_knn,
                        metric=self.metric,
                        walktrap_steps=self.walktrap_steps,
                    ),
                },
                f,
            )

    def load(self, path: str) -> None:
        import pickle
        with open(path, "rb") as f:
            state = pickle.load(f)
        # Membership is replayable but dendrogram isn't pickle-safe; re-fit on load.
        self._sc_obj = None
        if state["membership"] is not None:
            self.n_metacells = state["n_metacells"]
