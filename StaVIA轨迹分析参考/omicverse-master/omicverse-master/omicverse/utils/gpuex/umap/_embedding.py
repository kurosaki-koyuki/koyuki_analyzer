"""Orchestrator: a drop-in GPU twin of umap-learn ``simplicial_set_embedding``.

Takes the *same* fuzzy ``connectivities`` graph scanpy already built and
returns a structurally-equivalent embedding, computed with the torch GPU
edge-SGD. Argument order/names mirror ``umap.umap_.simplicial_set_embedding``
so the omicverse CPU UMAP branch can swap backends by changing one call.
"""
from __future__ import annotations

import numpy as np
from sklearn.utils import check_random_state

from ._init import initialize_embedding, make_epochs_per_sample, prune_graph
from ._sgd import optimize_layout_torch


def _default_n_epochs(n_obs: int) -> int:
    """umap-learn's rule: 500 epochs for small data, 200 for large."""
    return 500 if n_obs <= 10_000 else 200


def simplicial_set_embedding_torch(
    data,
    graph,
    n_components,
    initial_alpha,
    a,
    b,
    gamma,
    negative_sample_rate,
    n_epochs,
    init,
    random_state,
    metric,
    metric_kwds,
    densmap=False,
    densmap_kwds=None,
    output_dens=False,
    *,
    device=None,
    backend="auto",
    verbose=False,
):
    """GPU non-parametric UMAP embedding of a fuzzy simplicial set.

    Parameters
    ----------
    data
        ``(n, d)`` matrix; only used to seed spectral init. May be sparse.
    graph
        ``(n, n)`` scipy sparse fuzzy ``connectivities`` (e.g.
        ``adata.obsp['connectivities']``).
    n_components
        Output dimensionality (usually 2).
    initial_alpha
        Initial SGD learning rate (1.0 in standard UMAP).
    a, b
        Low-dim membership curve params (``find_ab_params``).
    gamma
        Repulsion weight.
    negative_sample_rate
        Negative samples per positive sample.
    n_epochs
        Epoch count, or ``None`` to use umap-learn's 500/200 rule.
    init
        ``'spectral'`` / ``'random'`` / ``'pca'`` or an ``(n, n_components)``
        array (an explicit array gives bit-identical init to a CPU run).
    random_state
        Seed or ``RandomState`` instance.
    metric, metric_kwds
        Forwarded to spectral init only.
    densmap
        Must be ``False`` (densMAP is not implemented on this path).
    device
        ``'cuda'`` / ``'cpu'``; auto-detected when ``None``.

    Returns
    -------
    tuple
        ``(embedding, aux_data)`` — float32 ``(n, n_components)`` array and an
        (empty) aux dict, matching the umap-learn return signature.
    """
    if densmap:
        raise NotImplementedError(
            "densMAP is not supported by the GPU UMAP backend; use method='umap'."
        )

    random_state = check_random_state(random_state)
    n_obs = graph.shape[0]

    if n_epochs is None:
        n_epochs = _default_n_epochs(n_obs)
    n_epochs_max = max(n_epochs) if isinstance(n_epochs, (list, tuple)) else n_epochs

    # 1. dedup + prune weak edges (umap-learn semantics)
    graph = prune_graph(graph, n_epochs_max)

    # Pick the compute backend. 'auto': torch+CUDA when present, else MLX on
    # Apple Silicon (metal), else torch CPU. CUDA is the only path that also
    # GPU-accelerates the spectral init (lobpcg); MLX/CPU do spectral on CPU.
    use_mlx = False
    gpu_coo = None
    dev = None
    if backend in ("auto", "mlx", "torch"):
        cuda_ok = False
        try:
            import torch

            cuda_ok = torch.cuda.is_available()
        except Exception:  # noqa: BLE001
            cuda_ok = False
        if backend == "mlx":
            use_mlx = True
        elif backend == "auto" and not cuda_ok:
            from ._sgd_mlx import mlx_available

            use_mlx = mlx_available()
    else:
        raise ValueError(f"backend must be 'auto'|'torch'|'mlx', got {backend!r}")

    if not use_mlx:
        # torch path: resolve device once, upload the pruned COO a SINGLE time
        # so the spectral eigensolve and edge-SGD share resident tensors.
        try:
            import torch

            if isinstance(device, torch.device):
                dev = device
            elif device is None:
                dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            else:
                dev = torch.device(device)
            # MPS (Apple) unsupported here (torch float64/sparse gaps) -> CPU.
            if dev.type == "mps":
                dev = torch.device("cpu")
            if dev.type == "cuda":
                row_t = torch.as_tensor(graph.row, dtype=torch.long, device=dev)
                col_t = torch.as_tensor(graph.col, dtype=torch.long, device=dev)
                val_t = torch.as_tensor(graph.data, dtype=torch.float32, device=dev)
                gpu_coo = (row_t, col_t, val_t, graph.shape[0])
        except Exception:  # noqa: BLE001 - fall back to host arrays
            gpu_coo, dev = None, device

    # 2. initial layout (GPU spectral via lobpcg on CUDA; CPU scipy for MLX/CPU)
    embedding = initialize_embedding(
        data, graph, n_components, init, random_state,
        metric=metric, metric_kwds=metric_kwds,
        gpu_coo=gpu_coo, device=dev,
    )

    # 3. per-edge sampling schedule
    epochs_per_sample = make_epochs_per_sample(graph.data, n_epochs_max)

    # 4. edge-SGD
    seed = int(random_state.randint(np.iinfo(np.int32).max))
    if use_mlx:
        from ._sgd_mlx import optimize_layout_mlx

        embedding = optimize_layout_mlx(
            np.asarray(embedding), graph.row, graph.col, n_epochs_max,
            epochs_per_sample, a, b, gamma=gamma, initial_alpha=initial_alpha,
            negative_sample_rate=negative_sample_rate, seed=seed,
            move_other=True, verbose=verbose,
        )
    else:
        # reuse the resident COO endpoints (head=row, tail=col) on CUDA
        head = gpu_coo[0] if gpu_coo is not None else graph.row
        tail = gpu_coo[1] if gpu_coo is not None else graph.col
        embedding = optimize_layout_torch(
            embedding, head, tail, n_epochs_max, epochs_per_sample, a, b,
            gamma=gamma, initial_alpha=initial_alpha,
            negative_sample_rate=negative_sample_rate, seed=seed, device=dev,
            move_other=True, verbose=verbose,
        )

    aux_data: dict = {}
    if output_dens:
        aux_data["rad_orig"] = None
        aux_data["rad_emb"] = None
    return embedding, aux_data
