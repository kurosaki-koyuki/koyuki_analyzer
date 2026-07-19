"""``ov.utils.gpuex`` — GPU-accelerated re-implementations of common
NumPy / SciPy primitives.

Each submodule mirrors the upstream namespace and tries to keep the
public-function signatures byte-compatible so a one-line import-swap
moves a hot loop onto CUDA.

Today
-----
* ``ov.utils.gpuex.scipy.rankdata`` — vectorised, batched, average-tie
  ranking for 2-D arrays. Drop-in for ``scipy.stats.rankdata(..., axis=1,
  method='average')``.
* ``ov.utils.gpuex.umap`` — non-parametric UMAP embedding (umap-learn /
  scanpy parity) on the GPU via PyTorch (lobpcg spectral + edge-SGD).
  Drop-in for ``umap.umap_.simplicial_set_embedding``.
"""

from __future__ import annotations

from . import scipy  # noqa: F401  (re-export submodule)
from . import umap  # noqa: F401  (re-export submodule)

__all__ = ["scipy", "umap"]
