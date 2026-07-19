"""Random-partition baseline.

Uniformly assigns each cell to one of ``n_metacells`` buckets, optionally
stratified by an ``obs`` column (e.g. cluster) so that within-stratum
random sampling is what gets compared against principled metacells.

This is the **honest baseline** users should sanity-check against —
see Bilous et al. 2022 and the SuperCell paper for the case that
metacells beat random groupings on DE/velocity.  It is provided so the
maintainer's "is metacell even worth it?" question can be answered on
the user's own data via ``ov.single.compare_metacell_backends``.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .base import FitResult, MetaCellBackend


class RandomBackend(MetaCellBackend):
    name = "random"
    capabilities: set[str] = set()

    def __init__(
        self,
        adata,
        n_metacells: Optional[int] = None,
        stratify_key: Optional[str] = None,
        random_state: int = 0,
        **kwargs,
    ):
        self.adata = adata
        self.n_metacells = n_metacells or (adata.n_obs // 75)
        self.stratify_key = stratify_key
        self.random_state = int(random_state)
        self._extra = kwargs
        self.assignments = None

    def fit(self, n_metacells: Optional[int] = None, **kwargs) -> FitResult:
        if n_metacells is not None:
            self.n_metacells = n_metacells

        rng = np.random.default_rng(self.random_state)
        n = self.adata.n_obs
        t0 = time.time()

        if self.stratify_key is not None:
            if self.stratify_key not in self.adata.obs:
                raise KeyError(f"stratify_key={self.stratify_key!r} not in adata.obs")
            strata = self.adata.obs[self.stratify_key].astype(str).to_numpy()
            uniq = np.unique(strata)
            # Distribute n_metacells across strata in proportion to stratum size.
            labels = np.zeros(n, dtype=np.int64)
            offset = 0
            for s in uniq:
                idx = np.where(strata == s)[0]
                k_s = max(1, int(round(self.n_metacells * idx.size / n)))
                local = rng.integers(0, k_s, size=idx.size)
                labels[idx] = local + offset
                offset += k_s
        else:
            labels = rng.integers(0, self.n_metacells, size=n).astype(np.int64)

        runtime = time.time() - t0
        self.assignments = labels
        return FitResult(
            assignments=labels,
            n_iter=1,
            converged=True,
            runtime_s=float(runtime),
            backend_meta={"stratify_key": self.stratify_key},
        )

    def save(self, path: str) -> None:
        import pickle
        with open(path, "wb") as f:
            pickle.dump({"assignments": self.assignments,
                         "n_metacells": self.n_metacells,
                         "stratify_key": self.stratify_key,
                         "random_state": self.random_state}, f)

    def load(self, path: str) -> None:
        import pickle
        with open(path, "rb") as f:
            state = pickle.load(f)
        self.assignments = state["assignments"]
        self.n_metacells = state["n_metacells"]
        self.stratify_key = state["stratify_key"]
        self.random_state = state["random_state"]
