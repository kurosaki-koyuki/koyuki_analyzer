"""Pure-Python SuperCell implementation.

The original R SuperCell (Bilous et al. 2022) reduces a single-cell dataset
to ``N / gamma`` "metacells" by:

1. Building a ``k_knn``-nearest-neighbour graph on a low-dimensional
   embedding (default ``X_pca``).
2. Running **walktrap** community detection with walk length 1 — short
   random walks merge tightly connected cells before they have a chance
   to escape a local neighbourhood.
3. Cutting the resulting hierarchical dendrogram at the level that
   yields ``N / gamma`` communities; each community = one metacell.

The aggregation step (sum/mean of counts per community) is left to the
omicverse wrapper so it can re-use a single AnnData schema across
backends.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


def _build_knn_graph(X: np.ndarray, k: int, mode: str = "cosine"):
    """Build a kNN igraph.Graph in embedding space ``X``."""
    import igraph as ig
    from sklearn.neighbors import NearestNeighbors

    metric = "cosine" if mode == "cosine" else "euclidean"
    nn = NearestNeighbors(n_neighbors=k + 1, metric=metric).fit(X)
    distances, indices = nn.kneighbors(X)

    # Drop self-loops (first column).
    indices = indices[:, 1:]
    distances = distances[:, 1:]

    n = X.shape[0]
    src = np.repeat(np.arange(n), k)
    dst = indices.reshape(-1)
    # Walktrap likes positive edge weights; convert distance → similarity.
    weights = 1.0 / (distances.reshape(-1) + 1e-12)

    g = ig.Graph(n=n, edges=list(zip(src.tolist(), dst.tolist())), directed=False)
    g.es["weight"] = weights.tolist()
    # Undirected → coalesce duplicate edges, summing weights.
    g.simplify(combine_edges={"weight": "sum"})
    return g


@dataclass
class SuperCellResult:
    """Return container for :func:`supercell_partition`."""

    membership: np.ndarray            # (n_cells,) int — metacell id per cell
    n_metacells: int                  # number of distinct metacells
    dendrogram: object                # igraph.clustering.VertexDendrogram


def supercell_partition(
    X: np.ndarray,
    n_metacells: Optional[int] = None,
    gamma: Optional[float] = None,
    k_knn: int = 5,
    metric: str = "cosine",
    walktrap_steps: int = 4,
    seed: int = 0,
) -> SuperCellResult:
    """Partition cells into SuperCell metacells.

    Parameters
    ----------
    X
        Cell × feature embedding (e.g. PCA coordinates), shape ``(n_cells, d)``.
    n_metacells
        Target number of metacells.  Either this or ``gamma`` must be set.
    gamma
        Graining factor (n_cells / n_metacells).  Ignored if ``n_metacells``
        is given.
    k_knn
        Neighbours per cell in the kNN graph (R default: 5).
    metric
        ``'cosine'`` (default, R behaviour) or ``'euclidean'``.
    walktrap_steps
        Random-walk length for walktrap (R default: 4).
    seed
        Random seed.
    """
    import igraph as ig  # noqa: F401  (ensure igraph import error surfaces here)

    n_cells = X.shape[0]
    if n_metacells is None and gamma is None:
        raise ValueError("Must specify n_metacells or gamma.")
    if n_metacells is None:
        n_metacells = max(1, int(round(n_cells / gamma)))

    np.random.seed(seed)
    g = _build_knn_graph(X, k=k_knn, mode=metric)
    dendro = g.community_walktrap(weights="weight", steps=walktrap_steps)

    # Walktrap returns a hierarchical clustering; cut at requested n.
    optimal_n = min(n_metacells, n_cells)
    clustering = dendro.as_clustering(n=optimal_n)
    membership = np.asarray(clustering.membership, dtype=np.int64)

    return SuperCellResult(
        membership=membership,
        n_metacells=int(membership.max()) + 1,
        dendrogram=dendro,
    )


class SuperCell:
    """Object-style wrapper mirroring the upstream R API.

    Examples
    --------
    >>> sc_obj = SuperCell(X_pca, n_metacells=200, k_knn=5)
    >>> sc_obj.fit()
    >>> sc_obj.membership          # (n_cells,) int
    >>> sc_obj.refit(n_metacells=500)   # re-cut without rerunning walktrap
    """

    def __init__(
        self,
        X: np.ndarray,
        n_metacells: Optional[int] = None,
        gamma: Optional[float] = None,
        k_knn: int = 5,
        metric: str = "cosine",
        walktrap_steps: int = 4,
        seed: int = 0,
    ):
        self.X = np.asarray(X)
        self.n_metacells = n_metacells
        self.gamma = gamma
        self.k_knn = k_knn
        self.metric = metric
        self.walktrap_steps = walktrap_steps
        self.seed = seed
        self._dendro = None
        self.membership = None

    def fit(self):
        """Build kNN graph and run walktrap."""
        res = supercell_partition(
            self.X,
            n_metacells=self.n_metacells,
            gamma=self.gamma,
            k_knn=self.k_knn,
            metric=self.metric,
            walktrap_steps=self.walktrap_steps,
            seed=self.seed,
        )
        self._dendro = res.dendrogram
        self.membership = res.membership
        self.n_metacells = res.n_metacells
        return self

    def refit(self, n_metacells: int):
        """Re-cut the cached dendrogram at a different graining (no rebuild)."""
        if self._dendro is None:
            raise RuntimeError("Call .fit() before .refit().")
        clustering = self._dendro.as_clustering(n=min(n_metacells, self.X.shape[0]))
        self.membership = np.asarray(clustering.membership, dtype=np.int64)
        self.n_metacells = int(self.membership.max()) + 1
        return self
