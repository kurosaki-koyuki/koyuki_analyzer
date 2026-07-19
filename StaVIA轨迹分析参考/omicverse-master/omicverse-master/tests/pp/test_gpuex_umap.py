"""Tests for the GPU non-parametric UMAP backend (omicverse.utils.gpuex.umap).

The torch CPU path runs everywhere (incl. the Ubuntu CI). The MLX (metal)
path is exercised only when MLX + a metal device are present — i.e. on the
macOS CI runner (.github/workflows/gpuex-umap-mac.yml) — and skipped
otherwise.

The ``gpuex.umap`` subpackage is loaded standalone via importlib so this test
needs only numpy/scipy/scanpy/sklearn/anndata/torch(/mlx) — not a full
omicverse install (``omicverse.utils.__init__`` eagerly imports the heavy
plotting stack). That keeps the macOS MLX job lightweight.
"""
import importlib.util
import pathlib
import sys

import numpy as np
import pytest

_UMAP_DIR = (
    pathlib.Path(__file__).resolve().parents[2]
    / "omicverse" / "utils" / "gpuex" / "umap"
)


def _load_gpuex_umap():
    name = "gpuex_umap_standalone"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, _UMAP_DIR / "__init__.py",
        submodule_search_locations=[str(_UMAP_DIR)],
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gpuex_umap = _load_gpuex_umap()


def _toy_graph(n=1500, centers=6, seed=0):
    """A small blob dataset + its scanpy fuzzy connectivities graph."""
    import anndata as ad
    import scanpy as sc
    from sklearn.datasets import make_blobs

    X, _ = make_blobs(n_samples=n, centers=centers, n_features=20,
                      random_state=seed)
    X = X.astype(np.float32)
    adata = ad.AnnData(X)
    sc.pp.neighbors(adata, n_neighbors=15, use_rep="X", random_state=seed)
    return X, adata.obsp["connectivities"]


def _trustworthiness(X, emb, k=15):
    from sklearn.manifold import trustworthiness

    return trustworthiness(X, emb, n_neighbors=k)


def test_find_ab_params_matches_umap_learn():
    a, b = gpuex_umap.find_ab_params(spread=1.0, min_dist=0.5)
    assert abs(a - 0.583) < 0.05 and abs(b - 1.334) < 0.05


def test_torch_cpu_embedding_preserves_structure():
    """Non-parametric UMAP on CPU should preserve neighborhood structure."""
    X, graph = _toy_graph()
    a, b = gpuex_umap.find_ab_params(1.0, 0.5)
    emb, _ = gpuex_umap.simplicial_set_embedding_torch(
        X, graph, 2, 1.0, a, b, 1.0, 5, 500, "spectral", 0, "euclidean", {},
        device="cpu", backend="torch",
    )
    assert emb.shape == (X.shape[0], 2)
    assert np.isfinite(emb).all()
    assert _trustworthiness(X, emb) > 0.85


def test_backend_validation():
    X, graph = _toy_graph(n=300)
    a, b = gpuex_umap.find_ab_params(1.0, 0.5)
    with pytest.raises(ValueError):
        gpuex_umap.simplicial_set_embedding_torch(
            X, graph, 2, 1.0, a, b, 1.0, 5, 50, "spectral", 0, "euclidean", {},
            backend="not-a-backend",
        )


@pytest.mark.skipif(
    not _load_gpuex_umap().mlx_available(),
    reason="MLX/metal not available (Apple Silicon only)",
)
def test_mlx_embedding_preserves_structure():
    """MLX (metal) edge-SGD should match the CPU path's structure quality."""
    X, graph = _toy_graph()
    a, b = gpuex_umap.find_ab_params(1.0, 0.5)
    emb_mlx, _ = gpuex_umap.simplicial_set_embedding_torch(
        X, graph, 2, 1.0, a, b, 1.0, 5, 500, "spectral", 0, "euclidean", {},
        backend="mlx",
    )
    emb_cpu, _ = gpuex_umap.simplicial_set_embedding_torch(
        X, graph, 2, 1.0, a, b, 1.0, 5, 500, "spectral", 0, "euclidean", {},
        device="cpu", backend="torch",
    )
    assert emb_mlx.shape == (X.shape[0], 2)
    assert np.isfinite(emb_mlx).all()
    tw_mlx = _trustworthiness(X, emb_mlx)
    tw_cpu = _trustworthiness(X, emb_cpu)
    assert tw_mlx > 0.85, f"MLX trustworthiness too low: {tw_mlx}"
    assert abs(tw_mlx - tw_cpu) < 0.05, f"MLX {tw_mlx} vs CPU {tw_cpu}"
