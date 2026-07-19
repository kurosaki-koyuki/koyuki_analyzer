"""Apple-Silicon (MLX/metal) edge-SGD for non-parametric UMAP.

Mirrors :func:`._sgd.optimize_layout_torch` but runs the gradient
computation on Apple's MLX (metal) backend — the same Apple path
omicverse already uses for PCA (``_pca_mlx.MLXPCA``) and Harmony, rather
than torch-MPS (MLX has the float64/sparse coverage MPS lacks here, and
metal's launch/sync overhead makes a literal torch-MPS port of this
many-small-kernel loop slower than CPU).

Design: the cheap O(edges) active-edge selection and the per-edge schedule
stay in NumPy on the host (host ``np.nonzero`` over the schedule is only a
few % of the runtime); the *expensive* per-epoch work — the gather →
gradient → scatter-add **and the negative-sample draw** — runs on metal.

The original version drew negatives on the host (``np.repeat`` of the
catch-up counts + ``np.random`` of millions of vertices, then transferred
to metal every epoch); profiling showed that single step was ~31% of the
runtime. Here each active edge instead draws a *fixed*
``round(negative_sample_rate)`` negatives directly on-device with
``mx.random`` — the standard GPU/cuML simplification (umap-learn's
catch-up schedule averages to the same rate). That removes the host RNG
and the per-epoch index transfer, the bulk of the speedup.

Why not process *all* edges every epoch under ``mx.compile``? On a real
fuzzy graph only ~30% of edges are active in a typical epoch, so an
all-edges static-shape loop does ~3× the necessary work — and ``mx.compile``
with ``shapeless=True`` can't trace the dynamic scatter anyway
(``Scatter Sum cannot infer output shapes``). Active-only + on-device
negatives, run eagerly, is the faster choice on real data.

Bit-equality with umap-learn is not the goal (different RNG + parallel
updates); the embedding is validated by trustworthiness. Spectral init is
done on the CPU (scipy) by the caller.
"""
from __future__ import annotations

import numpy as np

CLIP = 4.0


def mlx_available() -> bool:
    """True when MLX is importable and a metal device is present."""
    try:
        import mlx.core as mx

        return bool(mx.metal.is_available())
    except Exception:  # noqa: BLE001
        return False


def optimize_layout_mlx(
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
    move_other: bool = True,
    verbose: bool = False,
) -> np.ndarray:
    """Optimise ``embedding`` with the MLX (metal) edge-SGD.

    Same gradient formulas / clip(±4) / linear alpha decay as the torch and
    umap-learn paths. Active-edge selection stays on the host; the gradient
    and the (fixed-count, on-device) negative sampling run on metal. Returns
    the optimised ``(n, dim)`` float32 array.
    """
    import mlx.core as mx

    head = np.ascontiguousarray(np.asarray(head), dtype=np.int32)
    tail = np.ascontiguousarray(np.asarray(tail), dtype=np.int32)
    eps_sample = np.asarray(epochs_per_sample, dtype=np.float64)
    next_sample = eps_sample.copy()
    sampleable = eps_sample > 0  # epochs_per_sample <= 0 -> never sampled

    n_vertices = int(embedding.shape[0])
    n_neg = int(round(float(negative_sample_rate)))
    a_f, b_f, gamma_f = float(a), float(b), float(gamma)

    emb = mx.array(np.ascontiguousarray(embedding, dtype=np.float32))
    key = mx.random.key(int(seed) & 0x7FFFFFFF)

    def gradient_step(emb, jx, kx, negk, alpha):
        """One epoch's metal work for the active edges ``(jx, kx)`` with
        pre-drawn on-device negatives ``negk`` of shape ``(A, n_neg)``."""
        # ---- attractive (positive edges) ----
        diff = emb[jx] - emb[kx]
        d2 = mx.sum(diff * diff, axis=1)
        d2c = mx.maximum(d2, 1e-12)
        # pow(d2c, b) = pow(d2c, b-1) * d2c -> one fractional pow instead of two
        pb1 = mx.power(d2c, b_f - 1.0)
        gc = (-2.0 * a_f * b_f * pb1) / (a_f * pb1 * d2c + 1.0)
        gc = mx.where(d2 > 0.0, gc, 0.0)
        grad = mx.clip(mx.expand_dims(gc, 1) * diff, -CLIP, CLIP) * alpha
        emb = emb.at[jx].add(grad)
        if move_other:
            emb = emb.at[kx].add(-grad)

        # ---- repulsion: fixed n_neg negatives per active edge ----
        if negk is not None:
            dn = mx.expand_dims(emb[jx], 1) - emb[negk]      # (A, n_neg, 2)
            d2n = mx.sum(dn * dn, axis=2)
            d2nc = mx.maximum(d2n, 1e-12)
            gcn = (2.0 * gamma_f * b_f) / ((0.001 + d2nc) * (a_f * mx.power(d2nc, b_f) + 1.0))
            gcn = mx.where(d2n > 0.0, gcn, 0.0)
            gradn = mx.clip(mx.expand_dims(gcn, 2) * dn, -CLIP, CLIP) * alpha
            # All n_neg negatives of an anchor land on the *same* vertex, so
            # sum them first and scatter once per active edge -- n_neg-fold
            # fewer atomic scatter ops than expanding to (A*n_neg,) anchors,
            # the dominant cost when n_neg=5. (The negative vertices don't
            # move; only the anchor repels.)
            emb = emb.at[jx].add(mx.sum(gradn, axis=1))
        return emb

    rng_iter = range(n_epochs)
    if verbose:
        try:
            from tqdm.auto import tqdm

            rng_iter = tqdm(rng_iter, desc="UMAP(MLX)")
        except Exception:  # noqa: BLE001
            pass

    for n in rng_iter:
        alpha = mx.array(initial_alpha * (1.0 - (float(n) / float(n_epochs))))
        active = np.nonzero(sampleable & (next_sample <= n))[0]
        if active.size == 0:
            continue
        jx = mx.array(head[active])
        kx = mx.array(tail[active])
        negk = None
        if n_neg > 0:
            key, sub = mx.random.split(key)
            negk = mx.random.randint(0, n_vertices, (active.size, n_neg), key=sub)
        emb = gradient_step(emb, jx, kx, negk, alpha)
        next_sample[active] += eps_sample[active]
        mx.eval(emb)  # materialise; bounds the lazy graph per epoch

    return np.array(emb).astype(np.float32)
