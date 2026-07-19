"""GPU edge-sampling SGD — the torch core of non-parametric UMAP.

This reproduces umap-learn 0.5.7's ``optimize_layout_euclidean`` analytic
gradient updates (NOT autograd, NOT a parametric MLP) on the GPU. Each
epoch the whole *active* edge set is updated simultaneously with atomic
``index_add_`` scatter — the standard parallel relaxation of umap-learn's
sequential per-edge loop (same approach cuML uses). Output is structurally
equivalent to the CPU embedding (bit-exactness is impossible: different RNG
family + parallel vs sequential updates).

Gradient formulas, the ``clip(±4)`` bound, the linear ``alpha`` decay, and
the negative-sample-count schedule are all taken verbatim from
``umap/layouts.py``.
"""
from __future__ import annotations

import numpy as np

CLIP = 4.0


def optimize_layout_torch(
    embedding: np.ndarray,
    head: np.ndarray,
    tail: np.ndarray,
    n_epochs: int,
    epochs_per_sample: np.ndarray,
    a: float,
    b: float,
    *,
    gamma: float = 1.0,
    initial_alpha: float = 1.0,
    negative_sample_rate: float = 5.0,
    seed: int = 0,
    device: str | None = None,
    move_other: bool = True,
    verbose: bool = False,
) -> np.ndarray:
    """Optimise ``embedding`` with GPU edge-SGD (umap-learn semantics).

    Parameters
    ----------
    embedding
        Initial ``(n, dim)`` float32 layout (already ``[0, 10]`` rescaled).
    head, tail
        Int arrays of the COO 1-simplex endpoints (post-prune).
    n_epochs
        Total optimisation epochs.
    epochs_per_sample
        Per-edge sampling period from ``make_epochs_per_sample`` (``-1`` =
        never sampled).
    a, b
        Low-dim membership curve params from ``find_ab_params``.
    gamma
        Repulsion weight.
    initial_alpha
        Initial learning rate; decays linearly to ~0.
    negative_sample_rate
        Negative samples per positive sample.
    seed
        Seed for the torch generator (negative-vertex draws).
    device
        ``'cuda'`` / ``'cpu'``; auto-detected when ``None``.
    move_other
        Whether tail vertices of positive edges also move (True for the
        standard single-embedding case).

    Returns
    -------
    numpy.ndarray
        The optimised ``(n, dim)`` float32 embedding.
    """
    import torch

    if isinstance(device, torch.device):
        dev = device
    elif device is None:
        dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        dev = torch.device(device)
    # MPS lacks float64 (used by the edge schedules) — fall back to CPU.
    if dev.type == "mps":
        dev = torch.device("cpu")

    n_vertices = embedding.shape[0]

    # Accept already-on-device tensors (single-transfer path: the graph COO
    # was uploaded once by the caller and is reused here) or numpy (standalone
    # / CPU-fallback path). Avoid re-uploading the big edge arrays.
    def _to_dev(arr, dtype):
        if isinstance(arr, torch.Tensor):
            return arr.to(device=dev, dtype=dtype)
        return torch.as_tensor(np.asarray(arr), dtype=dtype, device=dev)

    if isinstance(embedding, torch.Tensor):
        emb = embedding.to(device=dev, dtype=torch.float32).contiguous()
    else:
        emb = torch.as_tensor(np.ascontiguousarray(embedding),
                              dtype=torch.float32, device=dev)
    head_t = _to_dev(head, torch.long)
    tail_t = _to_dev(tail, torch.long)

    eps_sample = torch.as_tensor(np.asarray(epochs_per_sample),
                                 dtype=torch.float64, device=dev)
    eps_neg_sample = eps_sample / negative_sample_rate
    next_sample = eps_sample.clone()
    next_neg_sample = eps_neg_sample.clone()

    # Edges with epochs_per_sample < 0 are never sampled (weight was 0).
    sampleable = eps_sample > 0

    gen = torch.Generator(device=dev)
    gen.manual_seed(int(seed) & 0x7FFFFFFF)

    rng = range(n_epochs)
    if verbose:
        try:
            from tqdm.auto import tqdm

            rng = tqdm(rng, desc="UMAP(GPU)")
        except Exception:  # noqa: BLE001
            pass

    for n in rng:
        alpha = initial_alpha * (1.0 - (float(n) / float(n_epochs)))

        active = sampleable & (next_sample <= n)
        if not bool(active.any()):
            continue
        idx = active.nonzero(as_tuple=False).squeeze(1)
        j = head_t[idx]
        k = tail_t[idx]

        # ---- attractive gradient (positive edges) ----
        yj = emb[j]
        yk = emb[k]
        diff = yj - yk
        d2 = (diff * diff).sum(dim=1)
        pos = d2 > 0.0
        d2c = d2.clamp_min(1e-12)  # masked out below; avoids 0**(b-1) blowup
        grad_coeff = (-2.0 * a * b * d2c.pow(b - 1.0)) / (a * d2c.pow(b) + 1.0)
        grad_coeff = torch.where(pos, grad_coeff, torch.zeros_like(grad_coeff))
        grad = (grad_coeff.unsqueeze(1) * diff).clamp(-CLIP, CLIP) * alpha
        emb.index_add_(0, j, grad)
        if move_other:
            emb.index_add_(0, k, -grad)

        # ---- negative sampling (repulsion) ----
        n_neg = ((n - next_neg_sample[idx]) / eps_neg_sample[idx]).floor()
        n_neg = n_neg.clamp_min(0).to(torch.long)
        total_neg = int(n_neg.sum().item())
        if total_neg > 0:
            anchor = torch.repeat_interleave(j, n_neg)
            neg_k = torch.randint(0, n_vertices, (total_neg,), generator=gen,
                                  device=dev)
            ya = emb[anchor]
            yn = emb[neg_k]
            dn = ya - yn
            d2n = (dn * dn).sum(dim=1)
            posn = d2n > 0.0
            d2nc = d2n.clamp_min(1e-12)
            gc = (2.0 * gamma * b) / ((0.001 + d2nc) * (a * d2nc.pow(b) + 1.0))
            gc = torch.where(posn, gc, torch.zeros_like(gc))
            gradn = (gc.unsqueeze(1) * dn).clamp(-CLIP, CLIP) * alpha
            emb.index_add_(0, anchor, gradn)
            next_neg_sample[idx] += n_neg.to(torch.float64) * eps_neg_sample[idx]

        # ---- advance positive-edge schedule ----
        next_sample[idx] += eps_sample[idx]

    return emb.detach().cpu().numpy().astype(np.float32)
