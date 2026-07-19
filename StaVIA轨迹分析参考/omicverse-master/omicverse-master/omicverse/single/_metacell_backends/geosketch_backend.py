"""GeoSketch baseline (Hie et al., Cell Systems 2019).

GeoSketch is *not* a metacell aggregator — it picks ``n_metacells``
density-aware sketch cells.  To produce a partition we then assign every
non-sketch cell to its nearest sketch cell (cosine), so each sketch cell
becomes the prototype of a 1-or-more-cell "metacell".

This is provided as an *honest baseline*: in many tasks
(UMAP / Leiden / visualisation) sketching ≈ a real metacell at a tiny
fraction of the cost, and metacells only outperform it on tasks that
need aggregated counts (DE, ligand–receptor, GRNs).
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .base import FitResult, MetaCellBackend


class GeoSketchBackend(MetaCellBackend):
    name = "geosketch"
    capabilities = {"out_of_sample"}

    def __init__(
        self,
        adata,
        use_rep: str = "X_pca",
        n_metacells: Optional[int] = None,
        random_state: int = 0,
        **kwargs,
    ):
        self.adata = adata
        self.use_rep = use_rep
        self.n_metacells = n_metacells or (adata.n_obs // 75)
        self.random_state = int(random_state)
        self._extra = kwargs
        self._sketch_idx = None      # indices in the original adata
        self._sketch_x = None        # (n_metacells, d) — the prototype embeddings

    def _x(self) -> np.ndarray:
        if self.use_rep not in self.adata.obsm:
            raise KeyError(
                f"use_rep={self.use_rep!r} missing from adata.obsm; "
                "run a dimensionality reduction first (e.g. ov.pp.pca)."
            )
        return np.asarray(self.adata.obsm[self.use_rep])

    def fit(self, n_metacells: Optional[int] = None, **kwargs) -> FitResult:
        from ...external.geosketch import gs
        from sklearn.neighbors import NearestNeighbors

        if n_metacells is not None:
            self.n_metacells = n_metacells

        X = self._x()
        t0 = time.time()
        np.random.seed(self.random_state)
        idx = gs(X, self.n_metacells, replace=False)
        idx = np.asarray(sorted(idx), dtype=np.int64)

        # Assign every cell to nearest sketch cell (cosine).
        sketch_x = X[idx]
        nn = NearestNeighbors(n_neighbors=1, metric="cosine").fit(sketch_x)
        _, neighbor = nn.kneighbors(X)
        labels = neighbor.ravel().astype(np.int64)
        runtime = time.time() - t0

        self._sketch_idx = idx
        self._sketch_x = sketch_x

        return FitResult(
            assignments=labels,
            latent=X,
            codebook=sketch_x,
            n_iter=1,
            converged=True,
            runtime_s=float(runtime),
            backend_meta={"sketch_idx": idx.tolist()},
        )

    def codebook(self) -> np.ndarray:
        if self._sketch_x is None:
            raise RuntimeError("Call .fit() first.")
        return self._sketch_x

    def assign_new_cells(self, adata_query) -> dict:
        if self._sketch_x is None:
            raise RuntimeError("Call .fit() first.")
        from sklearn.neighbors import NearestNeighbors
        Xq = np.asarray(adata_query.obsm[self.use_rep])
        nn = NearestNeighbors(n_neighbors=1, metric="cosine").fit(self._sketch_x)
        d, neighbor = nn.kneighbors(Xq)
        return {
            "metacell_id": neighbor.ravel().astype(np.int64),
            "confidence": 1.0 / (1.0 + d.ravel()),
            "embedding": Xq,
        }

    def save(self, path: str) -> None:
        import pickle
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "sketch_idx": self._sketch_idx,
                    "sketch_x": self._sketch_x,
                    "n_metacells": self.n_metacells,
                    "use_rep": self.use_rep,
                },
                f,
            )

    def load(self, path: str) -> None:
        import pickle
        with open(path, "rb") as f:
            state = pickle.load(f)
        self._sketch_idx = state["sketch_idx"]
        self._sketch_x = state["sketch_x"]
        self.n_metacells = state["n_metacells"]
        self.use_rep = state["use_rep"]
