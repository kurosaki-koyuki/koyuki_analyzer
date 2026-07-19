"""MetaCell-2 (tanaylab/metacells) backend.

The upstream ``metacells`` package is large (~50 modules + C extensions)
and is **not** vendored.  Users who want this backend should
``pip install metacells`` separately — the backend raises a clear
ImportError otherwise.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from .base import FitResult, MetaCellBackend


_INSTALL_HINT = (
    "MC2 backend requires the upstream `metacells` package "
    "(`pip install metacells`).  It is intentionally NOT vendored "
    "(>50 modules + C extensions)."
)


class MC2Backend(MetaCellBackend):
    name = "mc2"
    capabilities = {"streaming"}

    def __init__(
        self,
        adata,
        n_metacells: Optional[int] = None,
        target_metacell_size: int = 100,
        random_state: int = 0,
        verbose: bool = False,
        **kwargs,
    ):
        self.adata = adata
        self.n_metacells = n_metacells or (adata.n_obs // 75)
        self.target_metacell_size = target_metacell_size
        self.random_state = random_state
        self.verbose = verbose
        self._extra = kwargs
        self.assignments = None

    def fit(self, n_metacells: Optional[int] = None, **kwargs) -> FitResult:
        try:
            import metacells as mc
        except ImportError as exc:
            raise ImportError(_INSTALL_HINT) from exc

        if n_metacells is not None:
            self.n_metacells = n_metacells

        # MC2 default pipeline: clean → group → metacell → outlier sweep.
        ad = self.adata
        t0 = time.time()
        mc.tl.divide_and_conquer_pipeline(
            ad,
            target_metacell_size=self.target_metacell_size,
            random_seed=self.random_state,
            **kwargs,
        )
        runtime = time.time() - t0

        if "metacell" in ad.obs:
            labels = ad.obs["metacell"].to_numpy()
        else:
            raise RuntimeError("metacells pipeline did not populate obs['metacell'].")

        # MC2 uses -1 for outliers — map to its own bucket id at the end.
        labels = labels.astype(int)
        if (labels < 0).any():
            outlier_id = int(labels.max()) + 1
            labels = np.where(labels < 0, outlier_id, labels)

        self.assignments = labels
        return FitResult(
            assignments=labels,
            n_iter=1,
            converged=True,
            runtime_s=float(runtime),
            backend_meta={"target_size": self.target_metacell_size},
        )

    def save(self, path: str) -> None:
        import pickle
        with open(path, "wb") as f:
            pickle.dump({"assignments": self.assignments}, f)

    def load(self, path: str) -> None:
        import pickle
        with open(path, "rb") as f:
            self.assignments = pickle.load(f)["assignments"]
