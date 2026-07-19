"""Backend Protocol + return container for metacell algorithms."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Protocol, runtime_checkable

import numpy as np
from scipy import sparse


class UnsupportedCapability(NotImplementedError):
    """Raised when a backend method is missing a required capability flag."""


@dataclass
class FitResult:
    """Unified return type for :meth:`MetaCellBackend.fit`.

    Only ``assignments`` is required; everything else is optional and
    capability-gated by the backend.
    """

    assignments: np.ndarray                                  # (n_cells,) int — hard
    soft: Optional[sparse.csr_matrix] = None                 # (n_cells, n_mc)
    latent: Optional[np.ndarray] = None                      # (n_cells, d)
    codebook: Optional[np.ndarray] = None                    # (n_mc, d)
    n_iter: int = 0
    converged: bool = False
    runtime_s: float = 0.0
    backend_meta: dict = field(default_factory=dict)         # debug bag


@runtime_checkable
class MetaCellBackend(Protocol):
    """Minimal contract for a metacell backend.

    Subclasses should also set:

    - ``capabilities``: ``set[str]`` from
      ``{'soft', 'latent', 'codebook', 'out_of_sample', 'multimodal',
        'hierarchical', 'streaming'}``.
    - ``name``: short string used in error messages.
    """

    name: str
    capabilities: set[str]

    def fit(self, adata, n_metacells: int, **kwargs) -> FitResult: ...

    # Optional methods — only implemented when the capability flag is set.
    def soft_membership(self) -> sparse.csr_matrix: ...
    def latent(self) -> np.ndarray: ...
    def codebook(self) -> np.ndarray: ...
    def assign_new_cells(self, adata_query) -> dict: ...
    def fit_multi_gamma(self, gammas: list[float]) -> dict[float, FitResult]: ...
    def save(self, path: str) -> None: ...
    def load(self, path: str) -> None: ...


def require(backend: MetaCellBackend, capability: str, alternatives: list[str] = None):
    """Raise UnsupportedCapability with a helpful message if missing."""
    if capability not in backend.capabilities:
        msg = (
            f"Backend {backend.name!r} does not support {capability!r} "
            f"(capabilities: {sorted(backend.capabilities) or 'none'})."
        )
        if alternatives:
            msg += f" Backends with {capability!r}: {', '.join(alternatives)}."
        msg += " See ov.single.MetaCell.capability_matrix() for the full table."
        raise UnsupportedCapability(msg)
