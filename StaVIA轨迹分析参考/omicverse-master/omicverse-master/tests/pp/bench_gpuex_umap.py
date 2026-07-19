"""Speed benchmark: gpuex UMAP MLX (metal) vs CPU on synthetic cells.

Run as a script (not collected by pytest — name isn't ``test_*``):

    python tests/pp/bench_gpuex_umap.py [n_cells]

Loads the ``gpuex.umap`` subpackage standalone (numpy/scipy/scanpy/sklearn/
anndata/torch/mlx only), builds a fuzzy graph on synthetic blobs, and times
the non-parametric UMAP edge-SGD on the MLX (metal) backend vs the torch CPU
backend, printing wall-clock and speedup. Used by the macOS CI job to report
a real Apple-Silicon number; on a box without metal it prints CPU-only.
"""
import importlib.util
import pathlib
import sys
import time

import numpy as np

_UMAP_DIR = (
    pathlib.Path(__file__).resolve().parents[2]
    / "omicverse" / "utils" / "gpuex" / "umap"
)


def _load():
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


def main(n=30000):
    import anndata as ad
    import scanpy as sc
    from sklearn.datasets import make_blobs
    from sklearn.manifold import trustworthiness

    g = _load()
    print(f"=== gpuex UMAP speed benchmark: {n} cells, 200 epochs ===")
    X, _ = make_blobs(n_samples=n, centers=20, n_features=50, random_state=0)
    X = X.astype(np.float32)
    adata = ad.AnnData(X)
    t = time.time()
    sc.pp.neighbors(adata, n_neighbors=15, use_rep="X", random_state=0)
    graph = adata.obsp["connectivities"]
    print(f"  neighbors graph: {graph.nnz} edges ({time.time()-t:.1f}s, shared cost)")
    a, b = g.find_ab_params(1.0, 0.5)

    def run(backend, **kw):
        t = time.time()
        emb, _ = g.simplicial_set_embedding_torch(
            X, graph, 2, 1.0, a, b, 1.0, 5, 200, "spectral", 0,
            "euclidean", {}, backend=backend, **kw)
        return emb, time.time() - t

    emb_cpu, t_cpu = run("torch", device="cpu")
    tw_cpu = trustworthiness(X[:8000], emb_cpu[:8000], n_neighbors=15)
    print(f"  CPU (torch) : {t_cpu:6.1f}s   trustworthiness={tw_cpu:.4f}")

    if g.mlx_available():
        emb_mlx, t_mlx = run("mlx")
        tw_mlx = trustworthiness(X[:8000], emb_mlx[:8000], n_neighbors=15)
        print(f"  MLX (metal) : {t_mlx:6.1f}s   trustworthiness={tw_mlx:.4f}")
        print(f"  >>> MLX speedup vs CPU: {t_cpu / max(t_mlx, 1e-9):.1f}x")
    else:
        print("  MLX (metal) : not available on this host (CPU-only run)")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30000)
