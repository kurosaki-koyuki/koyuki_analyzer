"""K-means backend — trivial baseline.

Each k-means cluster is treated as one metacell; the cluster centroid is
the codebook entry, which gives free out-of-sample assignment via
``predict()``.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .base import FitResult, MetaCellBackend


class KMeansBackend(MetaCellBackend):
    name = "kmeans"
    capabilities = {"latent", "codebook", "out_of_sample"}

    def __init__(
        self,
        adata,
        use_rep: str = "X_pca",
        n_metacells: Optional[int] = None,
        random_state: int = 0,
        n_init: int = 10,
        **kwargs,
    ):
        self.adata = adata
        self.use_rep = use_rep
        self.n_metacells = n_metacells or (adata.n_obs // 75)
        self.random_state = int(random_state)
        self.n_init = int(n_init)
        self._extra = kwargs
        self.model = None

    def _x(self) -> np.ndarray:
        if self.use_rep not in self.adata.obsm:
            raise KeyError(
                f"use_rep={self.use_rep!r} missing from adata.obsm; "
                "run a dimensionality reduction first (e.g. ov.pp.pca)."
            )
        return np.asarray(self.adata.obsm[self.use_rep])

    def fit(self, n_metacells: Optional[int] = None, **kwargs) -> FitResult:
        from sklearn.cluster import KMeans

        if n_metacells is not None:
            self.n_metacells = n_metacells

        X = self._x()
        t0 = time.time()
        self.model = KMeans(
            n_clusters=self.n_metacells,
            random_state=self.random_state,
            n_init=self.n_init,
            **kwargs,
        ).fit(X)
        runtime = time.time() - t0

        return FitResult(
            assignments=self.model.labels_.astype(np.int64),
            latent=X,
            codebook=self.model.cluster_centers_,
            n_iter=int(self.model.n_iter_),
            converged=True,
            runtime_s=float(runtime),
            backend_meta={"inertia": float(self.model.inertia_)},
        )

    def latent(self) -> np.ndarray:
        return self._x()

    def codebook(self) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Call .fit() first.")
        return self.model.cluster_centers_

    def assign_new_cells(self, adata_query) -> dict:
        if self.model is None:
            raise RuntimeError("Call .fit() first.")
        Xq = np.asarray(adata_query.obsm[self.use_rep])
        labels = self.model.predict(Xq).astype(np.int64)
        # "Confidence" = 1 / (1 + distance to nearest centroid)
        d = self.model.transform(Xq).min(axis=1)
        return {
            "metacell_id": labels,
            "confidence": 1.0 / (1.0 + d),
            "embedding": Xq,
        }

    def save(self, path: str) -> None:
        import pickle
        with open(path, "wb") as f:
            pickle.dump({"model": self.model, "use_rep": self.use_rep,
                         "n_metacells": self.n_metacells}, f)

    def load(self, path: str) -> None:
        import pickle
        with open(path, "rb") as f:
            state = pickle.load(f)
        self.model = state["model"]
        self.use_rep = state["use_rep"]
        self.n_metacells = state["n_metacells"]
