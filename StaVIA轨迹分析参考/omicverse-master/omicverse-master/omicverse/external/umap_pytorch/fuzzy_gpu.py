"""GPU port of umap-learn's ``fuzzy_simplicial_set`` (smooth_knn_dist +
membership strengths + fuzzy set union). All ops run in torch on the device
of the input KNN tensors; nothing leaves GPU.

Algorithm reference: McInnes et al. UMAP §3 + the ``umap.umap_`` source.
We track the same defaults as umap-learn: ``local_connectivity=1.0``,
``set_op_mix_ratio=1.0``, ``n_iter=64``, ``SMOOTH_K_TOLERANCE=1e-5``,
``MIN_K_DIST_SCALE=1e-3``.
"""
from __future__ import annotations

import math

import torch


_SMOOTH_K_TOLERANCE = 1e-5
_MIN_K_DIST_SCALE = 1e-3


def smooth_knn_dist(
    distances: torch.Tensor,
    k: int,
    n_iter: int = 64,
    local_connectivity: float = 1.0,
    bandwidth: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Vectorized binary search for sigma_i, rho_i per row.

    Mirrors ``umap.umap_.smooth_knn_dist`` for ``local_connectivity=1.0``
    (the only value the parametric path exercises). For non-default values
    we fall through to the simple "first nonzero distance" rho — that's a
    minor approximation that doesn't matter for typical pumap usage.
    """
    if local_connectivity != 1.0:
        # The full umap-learn formula with floor()/interpolation is rarely
        # used; we keep a clear error rather than silently diverging.
        raise NotImplementedError(
            "smooth_knn_dist on GPU only implements local_connectivity=1.0; "
            f"got {local_connectivity}"
        )

    device = distances.device
    N, K = distances.shape
    target = torch.tensor(math.log2(float(k)) * bandwidth, device=device, dtype=torch.float32)

    # rho_i = smallest positive distance in row i (== 0 if none).
    INF = torch.tensor(float("inf"), device=device, dtype=distances.dtype)
    masked = torch.where(distances > 0, distances, INF.expand_as(distances))
    rho = masked.min(dim=1).values
    rho = torch.where(torch.isinf(rho), torch.zeros_like(rho), rho)

    # Skip column 0 (typically self / d=0) when computing psum, matching umap-learn.
    d_minus_rho = distances[:, 1:] - rho.unsqueeze(1)
    pos_mask = d_minus_rho > 0

    lo = torch.zeros(N, device=device, dtype=torch.float32)
    hi = torch.full((N,), float("inf"), device=device, dtype=torch.float32)
    mid = torch.ones(N, device=device, dtype=torch.float32)

    for _ in range(n_iter):
        # psum_i = sum_j (1 if (d-rho)_ij <= 0 else exp(-(d-rho)_ij / mid_i))
        contrib = torch.where(
            pos_mask,
            torch.exp(-d_minus_rho / mid.unsqueeze(1)),
            torch.ones_like(d_minus_rho),
        )
        psum = contrib.sum(dim=1)
        diff = psum - target
        if diff.abs().max().item() < _SMOOTH_K_TOLERANCE:
            break

        too_high = psum > target
        new_hi = torch.where(too_high, mid, hi)
        new_lo = torch.where(too_high, lo, mid)
        hi_finite = torch.isfinite(new_hi)
        new_mid = torch.where(
            hi_finite,
            (new_lo + new_hi) * 0.5,
            torch.where(too_high, mid, mid * 2.0),
        )
        # Don't update rows that already converged this iteration.
        converged = diff.abs() < _SMOOTH_K_TOLERANCE
        lo = torch.where(converged, lo, new_lo)
        hi = torch.where(converged, hi, new_hi)
        mid = torch.where(converged, mid, new_mid)

    sigmas = mid

    # Floor sigma to MIN_K_DIST_SCALE * mean distance, matching umap-learn.
    mean_per_row = distances.mean(dim=1)
    mean_global = distances.mean()
    floor = torch.where(rho > 0, _MIN_K_DIST_SCALE * mean_per_row, _MIN_K_DIST_SCALE * mean_global)
    sigmas = torch.maximum(sigmas, floor)

    return sigmas, rho


def compute_membership_strengths(
    knn_indices: torch.Tensor,
    knn_dists: torch.Tensor,
    sigmas: torch.Tensor,
    rhos: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Build COO arrays (rows, cols, vals) of fuzzy memberships.

    Mirrors ``umap.umap_.compute_membership_strengths`` exactly:
        val(i, knn[i, j]) = 0                if knn[i, j] == i
                          = 1                if d <= rho_i
                          = exp(-(d - rho_i) / sigma_i)   otherwise
    Entries with ``knn_indices == -1`` (umap-learn's "missing neighbor"
    sentinel) are dropped.
    """
    device = knn_indices.device
    N, K = knn_indices.shape

    rows = torch.arange(N, device=device, dtype=torch.long).unsqueeze(1).expand(N, K).reshape(-1)
    cols = knn_indices.reshape(-1).to(torch.long)

    rho_b = rhos.unsqueeze(1).expand(N, K)
    sigma_b = sigmas.unsqueeze(1).expand(N, K)
    diff = knn_dists - rho_b
    vals = torch.where(
        diff <= 0,
        torch.ones_like(knn_dists),
        torch.exp(-diff / sigma_b),
    )
    # Self-loops -> 0 (eliminate during set union).
    self_mask = knn_indices == torch.arange(N, device=device, dtype=knn_indices.dtype).unsqueeze(1)
    vals = torch.where(self_mask, torch.zeros_like(vals), vals).reshape(-1)

    valid = (cols >= 0) & (vals > 0)
    return rows[valid], cols[valid], vals[valid]


def fuzzy_set_union(
    rows: torch.Tensor,
    cols: torch.Tensor,
    vals: torch.Tensor,
    n_vertices: int,
    set_op_mix_ratio: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Symmetrize fuzzy memberships via probabilistic set operations.

    For each undirected pair (i, j):
        union(a, b) = a + b - a*b   (size 2: both A[i,j] and A[j,i] exist)
        union(a)    = a              (size 1: only one direction exists)

    With ``set_op_mix_ratio=1.0`` (default) the result is pure union; lower
    values blend with intersection ``a*b`` per umap-learn's formula.

    All arithmetic stays on the device of the inputs.
    """
    device = rows.device
    if rows.numel() == 0:
        return rows, cols, vals

    # Stack forward and reverse edges so each unique unordered pair (i, j)
    # appears once or twice in this combined COO list.
    all_rows = torch.cat([rows, cols])
    all_cols = torch.cat([cols, rows])
    all_vals = torch.cat([vals, vals])

    # Encode (row, col) as a single int64 key for sort/dedup. Safe up to
    # n_vertices ~ 3e9 in int64.
    n = int(n_vertices)
    key = all_rows.to(torch.long) * n + all_cols.to(torch.long)

    sorted_key, perm = torch.sort(key)
    sorted_vals = all_vals[perm]

    unique_keys, inverse = torch.unique_consecutive(sorted_key, return_inverse=True)
    M = unique_keys.numel()

    counts = torch.zeros(M, device=device, dtype=torch.long)
    counts.scatter_add_(0, inverse, torch.ones_like(inverse))
    # Group start indices in the sorted arrays.
    starts = torch.cumsum(counts, dim=0) - counts

    # First and (optional) second value per group. Each group has size 1 or 2
    # because each unordered pair contributes at most twice to the stack.
    val_first = sorted_vals[starts]
    has_second = counts > 1
    second_idx = torch.where(has_second, starts + 1, torch.zeros_like(starts))
    val_second = torch.where(has_second, sorted_vals[second_idx], torch.zeros_like(val_first))

    union = val_first + val_second - val_first * val_second
    if set_op_mix_ratio != 1.0:
        prod = val_first * val_second
        union = set_op_mix_ratio * union + (1.0 - set_op_mix_ratio) * prod

    out_rows = unique_keys // n
    out_cols = unique_keys % n
    keep = union > 0
    return out_rows[keep], out_cols[keep], union[keep]


def fuzzy_simplicial_set_gpu(
    knn_indices: torch.Tensor,
    knn_dists: torch.Tensor,
    n_neighbors: int,
    set_op_mix_ratio: float = 1.0,
    local_connectivity: float = 1.0,
    bandwidth: float = 1.0,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """GPU drop-in for ``umap.umap_.fuzzy_simplicial_set``.

    Returns ``(rows, cols, vals)`` of the symmetrized fuzzy graph as torch
    tensors on the same device as the inputs. Use these directly with
    :class:`StreamingUMAPDataset` to avoid the CPU/scipy round-trip.

    Compared to the umap-learn version we omit the densmap parameters and
    only support ``local_connectivity=1.0`` (sufficient for the parametric
    pipeline; assert the rest match upstream defaults).
    """
    n_vertices = int(knn_indices.shape[0])
    sigmas, rhos = smooth_knn_dist(
        knn_dists,
        k=n_neighbors,
        local_connectivity=local_connectivity,
        bandwidth=bandwidth,
    )
    rows, cols, vals = compute_membership_strengths(knn_indices, knn_dists, sigmas, rhos)
    return fuzzy_set_union(rows, cols, vals, n_vertices, set_op_mix_ratio=set_op_mix_ratio)
