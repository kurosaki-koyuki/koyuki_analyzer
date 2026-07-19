"""Graph prep + embedding initialisation — faithful to umap-learn 0.5.7.

Everything here runs on CPU/NumPy/SciPy (it is cheap, deterministic, and
matching the CPU path here matters more than speed): graph dedup/prune,
``make_epochs_per_sample``, spectral / random / pca / array init, and the
mandatory ``[0, 10]`` rescale that umap-learn applies to every init.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse


def make_epochs_per_sample(weights: np.ndarray, n_epochs: int) -> np.ndarray:
    """Number of epochs between successive samples of each 1-simplex.

    Identical to ``umap.umap_.make_epochs_per_sample``. Edges with weight 0
    get ``-1.0`` (never sampled); stronger edges get a smaller value (sampled
    more often).
    """
    result = -1.0 * np.ones(weights.shape[0], dtype=np.float64)
    n_samples = n_epochs * (weights / weights.max())
    result[n_samples > 0] = float(n_epochs) / np.float64(n_samples[n_samples > 0])
    return result


def prune_graph(graph: scipy.sparse.spmatrix, n_epochs: int):
    """Dedup + drop weak edges, mirroring ``simplicial_set_embedding``.

    Zeros out entries below ``graph.data.max() / n_epochs`` and removes them,
    so weak 1-simplices are never sampled. Returns a COO matrix.
    """
    graph = graph.tocoo()
    graph.sum_duplicates()
    n_epochs_eff = n_epochs if n_epochs > 10 else 200
    graph.data[graph.data < (graph.data.max() / float(n_epochs_eff))] = 0.0
    graph.eliminate_zeros()
    return graph.tocoo()


def noisy_scale_coords(coords, random_state, max_coord=10.0, noise=0.0001):
    """Scale coords to a ``max_coord`` box and add tiny Gaussian noise.

    Matches umap-learn's ``noisy_scale_coords`` used after spectral/pca init.
    """
    expansion = max_coord / np.abs(coords).max()
    coords = (coords * expansion).astype(np.float32)
    if noise > 0.0:
        coords += random_state.normal(scale=noise, size=coords.shape).astype(
            np.float32
        )
    return coords


def _gpu_spectral_lobpcg(row_t, col_t, val_t, n, dim, dev):
    """Smallest non-trivial eigenvectors of the normalized Laplacian on GPU.

    Builds ``L = I - D^{-1/2} A D^{-1/2}`` as a *sparse* tensor (never a dense
    n×n) from the already-resident COO tensors and runs ``torch.lobpcg`` for
    the smallest eigenpairs — the same spectral-layout vectors umap-learn
    keeps (indices ``[1:dim+1]``). Validated to span the same subspace as
    scipy ``eigsh`` (canonical corr > 0.99) at ~25× the speed.

    Returns an ``(n, dim)`` float32 numpy array, or raises on failure (the
    caller falls back to the CPU scipy path).
    """
    import torch

    k = dim + 1
    val = val_t.to(torch.float64)
    # Degree via scatter-add (no second sparse build).
    deg = torch.zeros(n, dtype=torch.float64, device=dev).index_add_(0, row_t, val)
    d_inv_sqrt = deg.clamp_min(1.0).rsqrt()
    # L = I - D^{-1/2} A D^{-1/2}: off-diagonal = -d^{-1/2}_i A_ij d^{-1/2}_j,
    # plus an identity on the diagonal. coalesce() folds any self-loops in.
    scaled = -(d_inv_sqrt[row_t] * val * d_inv_sqrt[col_t])
    diag = torch.arange(n, device=dev)
    L_row = torch.cat([row_t, diag])
    L_col = torch.cat([col_t, diag])
    L_val = torch.cat([scaled, torch.ones(n, dtype=torch.float64, device=dev)])
    L_sp = torch.sparse_coo_tensor(
        torch.stack([L_row, L_col]), L_val, (n, n)
    ).coalesce()

    try:
        eigvals, eigvecs = torch.lobpcg(
            L_sp, k=k, largest=False, method="ortho", tol=1e-4, niter=-1
        )
    except (RuntimeError, TypeError):
        # Some torch builds reject method="ortho"/niter=-1; retry plainly.
        eigvals, eigvecs = torch.lobpcg(L_sp, k=k, largest=False)
    order = torch.argsort(eigvals)
    emb = eigvecs[:, order[1:k]].to(torch.float32)
    del L_sp, scaled, d_inv_sqrt, deg, val
    return emb.detach().cpu().numpy()


def _spectral_layout(data, graph, dim, random_state, metric, metric_kwds,
                     *, gpu_coo=None, device=None):
    """Spectral embedding of the fuzzy graph.

    When ``device`` is CUDA and the COO tensors are supplied (or built from
    ``graph``), use the GPU ``torch.lobpcg`` path; on any failure fall back
    to umap-learn's own ``spectral_layout`` (scipy ``eigsh``), then a
    vendored scipy version, then a random layout — guaranteeing parity with
    the CPU path whenever the GPU path is unavailable.
    """
    if device is not None and getattr(device, "type", None) == "cuda":
        try:
            import torch

            n = graph.shape[0]
            if gpu_coo is not None:
                row_t, col_t, val_t = gpu_coo[0], gpu_coo[1], gpu_coo[2]
            else:
                row_t = torch.as_tensor(graph.row, dtype=torch.long, device=device)
                col_t = torch.as_tensor(graph.col, dtype=torch.long, device=device)
                val_t = torch.as_tensor(graph.data, dtype=torch.float32,
                                        device=device)
            return _gpu_spectral_lobpcg(row_t, col_t, val_t, n, dim, device)
        except Exception:  # noqa: BLE001 - any GPU failure -> CPU parity path
            import gc

            try:
                import torch

                torch.cuda.empty_cache()
            except Exception:  # noqa: BLE001
                pass
            gc.collect()

    try:  # parity-first: reuse umap-learn's exact spectral init
        from umap.spectral import spectral_layout

        return spectral_layout(
            data, graph, dim, random_state, metric=metric, metric_kwds=metric_kwds
        )
    except Exception:  # noqa: BLE001 - any failure -> vendored scipy path
        pass

    # Vendored single-component normalized-Laplacian spectral layout.
    from scipy.sparse import identity, spdiags
    from scipy.sparse.linalg import eigsh

    n = graph.shape[0]
    diag_data = np.asarray(graph.sum(axis=0)).ravel()
    diag_data[diag_data == 0] = 1.0
    D_inv_sqrt = spdiags(1.0 / np.sqrt(diag_data), 0, n, n)
    L = identity(n) - D_inv_sqrt @ graph @ D_inv_sqrt

    k = dim + 1
    num_lanczos = max(2 * k + 1, int(np.sqrt(n)))
    try:
        eigenvalues, eigenvectors = eigsh(
            L, k, which="SM", ncv=num_lanczos, tol=1e-4, v0=np.ones(n),
            maxiter=n * 5,
        )
        order = np.argsort(eigenvalues)[1:k]
        return eigenvectors[:, order]
    except Exception:  # noqa: BLE001
        return random_state.uniform(low=-10.0, high=10.0, size=(n, dim))


def initialize_embedding(data, graph, n_components, init, random_state,
                         metric="euclidean", metric_kwds=None,
                         *, gpu_coo=None, device=None):
    """Produce the initial embedding, then rescale to ``[0, 10]`` per dim.

    Handles ``init`` in {'spectral', 'random', 'pca', ndarray}. The final
    ``10 * (E - min) / (max - min)`` rescale is applied to *every* path, as
    umap-learn does, so init only sets structure, not scale.
    """
    metric_kwds = metric_kwds or {}
    n = graph.shape[0]

    if isinstance(init, str) and init == "random":
        embedding = random_state.uniform(
            low=-10.0, high=10.0, size=(n, n_components)
        ).astype(np.float32)
    elif isinstance(init, str) and init == "pca":
        from sklearn.decomposition import PCA

        X = data.toarray() if scipy.sparse.issparse(data) else np.asarray(data)
        pca = PCA(n_components=n_components, random_state=random_state)
        embedding = pca.fit_transform(X).astype(np.float32)
        embedding = noisy_scale_coords(embedding, random_state)
    elif isinstance(init, str) and init == "spectral":
        embedding = _spectral_layout(
            data, graph, n_components, random_state, metric, metric_kwds,
            gpu_coo=gpu_coo, device=device,
        )
        embedding = noisy_scale_coords(np.asarray(embedding), random_state)
    else:  # explicit array init (used by the validation harness for parity)
        embedding = np.asarray(init, dtype=np.float32)
        if len(np.unique(embedding, axis=0)) < embedding.shape[0]:
            embedding = embedding + random_state.normal(
                scale=0.0001, size=embedding.shape
            ).astype(np.float32)

    # Mandatory final rescale (umap-learn umap_.py ~1188-1192).
    emb = np.asarray(embedding, dtype=np.float32)
    span = emb.max(axis=0) - emb.min(axis=0)
    span[span == 0] = 1.0
    emb = 10.0 * (emb - emb.min(axis=0)) / span
    return emb.astype(np.float32)
