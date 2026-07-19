# Vendored from `decoupler` (https://github.com/scverse/decoupler) by
# omicverse for in-tree GPU acceleration work. Original copyright by
# the decoupler authors, redistributed under decoupler's GPL-3.0
# license. Cross-module imports rewritten from `decoupler.*` to
# `omicverse.es.*` (see scripts/vendor_decoupler.py).

import numba as nb
import numpy as np
import scipy.sparse as sps
from tqdm.auto import tqdm

from .._monitor import monitor
from .._registry import register_function

from ._net import _resolve_net
from ._run import _run
from ._net import _getset

@nb.njit(cache=True)
def _std(
    arr: np.ndarray,
    ddof: int,
) -> float:
    N = arr.shape[0]
    m = np.mean(arr)
    var = np.sum((arr - m) ** 2) / (N - ddof)
    sd = np.sqrt(var)
    return sd

def _ridx(
    times: int,
    nvar: int,
    seed: int | None,
):
    idx = np.tile(np.arange(nvar), (times, 1))
    if seed:
        rng = np.random.default_rng(seed=seed)
        for i in idx:
            rng.shuffle(i)
    return idx

@nb.njit(cache=True)
def _esrank(
    row: np.ndarray,
    rnks: np.ndarray,
    set_msk: np.ndarray,
    dec: float,
) -> tuple[float, int, np.ndarray]:
    # Init empty
    mx_value = 0.0
    cum_sum = 0.0
    mx_pos = 0.0
    mx_neg = 0.0
    j_pos = 0
    j_neg = 0
    es = np.zeros(rnks.size)
    # Compute norm
    sum_set: float = np.sum(np.abs(row[set_msk]))
    if sum_set == 0.0:
        return 0.0, 0, np.zeros(rnks.size)
    # Compute ES
    for i in rnks:
        if set_msk[i]:
            cum_sum += np.abs(row[i]) / sum_set
            es[i] = cum_sum
        else:
            cum_sum -= dec
            es[i] = cum_sum
        # Update max scores and idx
        if cum_sum > mx_pos:
            mx_pos = cum_sum
            j_pos = i
        if cum_sum < mx_neg:
            mx_neg = cum_sum
            j_neg = i
    # Determine if pos or neg are more enriched
    if mx_pos > -mx_neg:
        mx_value = mx_pos
        j = j_pos
    else:
        mx_value = mx_neg
        j = j_neg
    return mx_value, j, es

@nb.njit(cache=True)
def _nesrank(
    ridx: np.ndarray,
    row: np.ndarray,
    rnks: np.ndarray,
    set_msk: np.ndarray,
    dec: float,
    es: float,
) -> tuple[float, float]:
    # Keep old set_msk upstream
    set_msk = set_msk.copy()
    # Compute null
    times, nvar = ridx.shape
    if times == 0:
        return 0.0, 1.0
    null = np.zeros(times)
    for i in range(times):
        null[i], _, _ = _esrank(row=row, rnks=rnks, set_msk=set_msk[ridx[i]], dec=dec)
    # Compute NES
    pos_null_msk = null >= 0.0
    neg_null_msk = null < 0.0
    pos_null_sum = pos_null_msk.sum()
    neg_null_sum = neg_null_msk.sum()
    if (es >= 0) and (pos_null_sum > 0):
        pval = (null[pos_null_msk] >= es).sum() / pos_null_sum
        pos_null_mean = null[pos_null_msk].mean()
        nes = es / pos_null_mean
    elif (es < 0) and (neg_null_sum > 0):
        pval = (null[neg_null_msk] <= es).sum() / neg_null_sum
        neg_null_mean = null[neg_null_msk].mean()
        nes = -es / neg_null_mean
    else:
        nes = 0.0
        pval = 1.0
    return nes, pval

@nb.njit(parallel=True, cache=True)
def _stsgsea(
    row: np.ndarray,
    cnct: np.ndarray,
    starts: np.ndarray,
    offsets: np.ndarray,
    ridx: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Sort features
    idx = np.argsort(-row)
    row = row[idx]
    # Init empty
    nvar = row.size
    nsrc = starts.size
    rnks = np.arange(nvar)
    es = np.zeros(nsrc)
    nes = np.zeros(nsrc)
    pv = np.ones(nsrc)
    for j in nb.prange(nsrc):
        # Extract fset
        fset = _getset(cnct, starts, offsets, j)
        # Get decending penalty
        dec = 1.0 / (nvar - fset.size)
        # Get msk
        set_msk = np.zeros(nvar, dtype=np.bool_)
        set_msk[fset] = True
        set_msk = set_msk[idx]
        # Compute es per feature
        es[j], _, _ = _esrank(row=row, rnks=rnks, set_msk=set_msk, dec=dec)
        nes[j], pv[j] = _nesrank(ridx=ridx, row=row, rnks=rnks, set_msk=set_msk, dec=dec, es=es[j])
    return es, nes, pv

def _func_gsea(
    mat: np.ndarray,
    cnct: np.ndarray,
    starts: np.ndarray,
    offsets: np.ndarray,
    times: int | float = 1000,
    seed: int | float = 42,
    verbose: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    r"""
    Gene Set Enrichment Analysis (GSEA) :cite:`gsea`.

    Features are ranked based on a continuous statistic (e.g., expression, score, or correlation).
    The enrichment score (ES) for a feature set is computed by walking down the ranked list and increasing a running-sum
    statistic when a feature is in the set, and decreasing it when it is not.

    .. math::

       \delta(F, i) =
       \begin{cases}
       \frac{|r_i|}{\sum\limits_{j \in F} |r_j|} & \text{if feature } i \in F \\
       -\frac{1}{l} & \text{if feature } i \notin F
       \end{cases}

    Where:

    - :math:`F` is a feature set
    - :math:`r` is the ranking of the feature statistics in descending order
    - :math:`r_i` is the value for feature :math:`i`
    - :math:`r_j` is the value for feature :math:`j` in :math:`F`
    - :math:`k` is the number of features in :math:`F`
    - :math:`N` is the total number of features in :math:`r`
    - :math:`l=N-k` is the number of features not in :math:`F` but present in :math:`r`

    For each feature, the function :math:`\delta(F,i)` is applied and stored as a sequence :math:`L`.

    .. math::

        L = \delta(F, i)\text{ for i} = \text{1, 2, ... , N}

    The enrichment score :math:`ES` corresponds to the maximum deviation from zero of this running sum.

    .. math::

        ES = L_{arg max |L|}

    When multiple random permutations are done (``times > 1``), statistical significance is assessed via empirical testing.

    .. math::

        p_{value}=\frac{ES_{rand} \geq ES}{P}

    Where:

    - :math:`ES_{rand}` are the enrichment scores of the random permutations
    - :math:`P` is the total number of permutations

    Additionaly, :math:`ES` is updated to a normalized enrichment score :math:`NES`.

    .. math::

        NES = \begin{cases} \frac{ES}{\mu_{+}} & \text{if } ES > 0 \\ \frac{ES}{\mu_{-}} & \text{if } ES < 0  \end{cases}

    Where:

    - :math:`\mu{+}` is the mean of positive values in :math:`ES_{rand}`
    - :math:`\mu{-}` is the mean of negative values in :math:`ES_{rand}`

    Parameters
    ----------
    %(times)s
    %(seed)s

    Returns
    -------
    es : np.ndarray
        Enrichment score matrix (observations × signatures).
    pv : np.ndarray or None
        P-value matrix; ``None`` for kernels without a statistical test.

    Example
    -------
    .. code-block:: python

        import omicverse as ov
        adata, net = ov.es.toy_data()  # or your own (adata, net)
        ov.es.gsea(adata, net, tmin=3)
    """
    nobs, nvar = mat.shape
    assert isinstance(times, int | float) and times >= 0, "times must be numeric and >= 0"
    assert isinstance(seed, int | float) and seed >= 0, "seed must be numeric and >= 0"
    times, seed = int(times), int(seed)
    # Compute
    nsrc = starts.size
    if times > 1:
        ridx = _ridx(times=times, nvar=nvar, seed=seed)
    else:
        ridx = _ridx(times=times, nvar=nvar, seed=None)
    es = np.zeros(shape=(nobs, nsrc))
    nes = np.zeros(shape=(nobs, nsrc))
    pv = np.zeros(shape=(nobs, nsrc))
    for i in tqdm(range(nobs), disable=not verbose):
        if isinstance(mat, sps.csr_matrix):
            row = mat[i].toarray()[0]
        else:
            row = mat[i]
        es[i, :], nes[i, :], pv[i, :] = _stsgsea(
            row=row,
            cnct=cnct,
            starts=starts,
            offsets=offsets,
            ridx=ridx,
        )
    if times > 1:
        es = nes
    return es, pv

def _func_gsea_torch(
    mat,
    cnct,
    starts,
    offsets,
    times: int | float = 1000,
    seed: int | float = 42,
    verbose: bool = False,
):
    r"""Torch (GPU) port of GSEA — deterministic ES via batched
    running-max-deviation on the rank axis.

    Algorithm (per cell, vectorised over all signatures)
    ---------------------------------------------------
    1. Sort row descending (``argsort(-row, stable=True)``) once,
       giving ``sort_idx`` and ``row_abs_sorted``.
    2. Build a binary ``membership[gene, sig]`` matrix once.
       Reorder along the rank axis: ``mem_sorted = membership[sort_idx]``,
       shape ``(B, nvar, nsrc)`` per cell-batch.
    3. Per-cell-per-signature step:
         delta_in_set  = |row_sorted| / sum_set
         delta_out_set = -1 / (nvar - k)
       Combine via ``where(mem_sorted, in_set, out_set)`` → step values.
    4. ``cumsum`` along rank axis = running enrichment ``L(r)``.
    5. ``es = sign(L_pos > -L_neg) * max(|L_pos|, |L_neg|)`` where
       ``L_pos = max_r L(r)``, ``L_neg = min_r L(r)``.

    No permutation path (NES + p-value) here — when ``times > 1`` we
    fall back to the numba CPU kernel. Permutation requires a
    pseudo-random batched-shuffle kernel that's a substantial
    follow-up; GSEA without permutation (``times=1``) still gives the
    canonical ES which is what most callers chart.

    Memory model
    ------------
    Working tensor ``(B, nvar, nsrc)`` in fp32. Cell-batch size
    chosen by :func:`chunk_size_for` to stay around 32 MB.
    """
    import torch
    from ._engine import torch_device, chunk_size_for, to_gpu_dense

    if int(times) > 1:
        # Permutation-based p-value path stays on the numba kernel.
        return _func_gsea(
            mat, cnct, starts, offsets, times=times, seed=seed, verbose=verbose,
        )

    device = torch_device()
    M = to_gpu_dense(mat, device, dtype=torch.float64)
    nobs, nvar = M.shape
    nsrc = starts.size

    # Build dense (gene → signature) membership once.
    membership = torch.zeros(nvar, nsrc, dtype=torch.float32, device=device)
    cnct_t = torch.as_tensor(cnct, dtype=torch.long, device=device)
    sig_id = torch.as_tensor(
        np.repeat(np.arange(nsrc, dtype=np.int64), offsets), device=device,
    )
    membership[cnct_t, sig_id] = 1.0
    k = membership.sum(dim=0).to(torch.float64)                    # (nsrc,) signature sizes
    dec = 1.0 / (nvar - k)                                          # (nsrc,) out-of-set decrement

    # Cell-batch loop — same target-element budget as aucell.
    cells_per_batch = chunk_size_for(nvar * nsrc, max_units=nobs)
    es_out = torch.zeros(nobs, nsrc, dtype=torch.float64, device=device)
    for b0 in range(0, nobs, cells_per_batch):
        b1 = min(b0 + cells_per_batch, nobs)
        Mb = M[b0:b1]                                              # (B, nvar)
        sort_idx = torch.argsort(-Mb, dim=1, stable=True)          # (B, nvar)
        row_abs_sorted = Mb.abs().gather(1, sort_idx)              # (B, nvar)

        # sum_set[i, j] = Σ |row_i[g]| for g ∈ signature j
        sum_set = Mb.abs() @ membership.to(torch.float64)           # (B, nsrc)

        # mem_sorted[i, r, j] = membership[sort_idx[i, r], j]
        mem_sorted = membership[sort_idx]                          # (B, nvar, nsrc) fp32

        # Avoid 0/0 when sum_set == 0 (signature contributes nothing).
        safe_sum = torch.where(sum_set == 0, torch.ones_like(sum_set), sum_set)

        # Step values: numerator = |row_sorted| (B, nvar, 1), denom = sum_set (B, 1, nsrc).
        in_step = row_abs_sorted.unsqueeze(2) / safe_sum.unsqueeze(1)   # (B, nvar, nsrc)
        # (mem * in_step) + ((1 - mem) * -dec)
        delta = mem_sorted * in_step.to(torch.float32) + \
                (1.0 - mem_sorted) * (-dec.to(torch.float32))
        # Zero out columns whose sum_set is 0 to match the CPU kernel's
        # early-return ``return 0.0, 0, np.zeros(rnks.size)``.
        zero_mask = (sum_set == 0)
        if zero_mask.any():
            delta[:, :, :] = torch.where(
                zero_mask.unsqueeze(1).expand_as(delta),
                torch.zeros_like(delta),
                delta,
            )

        running = delta.cumsum(dim=1)                              # (B, nvar, nsrc)
        # max+ and max- along rank axis
        max_pos = running.amax(dim=1)                              # (B, nsrc)
        max_neg = running.amin(dim=1)                              # (B, nsrc)
        # ES = max_pos if |max_pos| > |max_neg| else max_neg
        es_out[b0:b1] = torch.where(
            max_pos > -max_neg, max_pos, max_neg,
        ).to(torch.float64)

    # No permutation → pv is all ones (matches CPU ``np.ones(nsrc)``).
    pv = np.ones((nobs, nsrc), dtype=np.float64)
    return es_out.cpu().numpy(), pv


_func_gsea_torch._accepts_sparse = True


@monitor
@register_function(
    aliases=['gsea', 'GSEA', 'enrichment_score', '通路富集'],
    category="enrichment",
    description=(
        "Gene Set Enrichment Analysis (GSEA). Walks a per-cell ranked feature list and tracks the running deviation from a uniform null."
    ),
    prerequisites={"optional_functions": ["preprocess"]},
    requires={"var": ["gene symbols matching signature keys"]},
    produces={"obsm": ["score_gsea", "padj_gsea"]},
    auto_fix="none",
    examples=[
        "ov.es.gsea(adata, signatures=sigs)",
        "ov.es.gsea(adata, signatures=pathway_dict, engine='gpu', tmin=3)",
    ],
    related=["aucell", "gsva", "ora", "ulm", "mlm", "waggr", "zscore", "viper", "mdt", "udt"],
)
def gsea(
    data,
    signatures=None,
    *,
    net=None,
    tmin: int | float = 5,
    raw: bool = False,
    empty: bool = True,
    bsize: int | float = 250_000,
    verbose: bool = False,
    engine: str = "auto",
    times: int | float = 1000,
    seed: int | float = 42,
):
    r"""Per-cell pathway enrichment via the GSEA running-sum statistic.

    .. math::

        ES = L_{\arg\max_i |L_i|},\quad L_i = \sum_{j \le i} \delta(F, j)

    Reference: `Subramanian et al., PNAS (2005) <https://doi.org/10.1073/pnas.0506580102>`_.

    Args:
        data: AnnData (or DataFrame) containing the expression matrix.
        signatures: Mapping ``{name → [gene, ...]}`` (binary) or
            ``{name → {gene: weight}}`` (weighted / signed). Mutually
            exclusive with ``net``.
        net: Long-format ``source / target / weight`` DataFrame (decoupler
            convention). Power-user escape hatch; ``signatures`` is the default.
        tmin: Minimum number of targets per signature; sets below this are
            silently dropped. Default 5.
        raw: Score against ``adata.raw.X`` instead of ``adata.X``. Default False.
        empty: Whether to write all-zero rows for signatures filtered out by
            ``tmin``. Default True.
        bsize: Cells per processing chunk (controls peak memory for sparse
            inputs). Default 250 000.
        verbose: Show per-cell tqdm progress bars. Default False.
        engine: ``"auto"`` (default) picks GPU when available, ``"cpu"`` forces
            the numba kernel, ``"gpu"`` forces the torch kernel.
        times: Permutations for empirical p-values. ``1`` skips permutations and keeps the GPU on-device.
        seed: RNG seed for the permutation block.

    Returns:
        None. Writes ``adata.obsm['score_gsea']`` and ``adata.obsm['padj_gsea']``.

    Examples:
        >>> import omicverse as ov
        >>> ov.es.gsea(adata, signatures=sigs)
    """
    from ._engine import resolve_engine

    eng = resolve_engine(engine, has_torch_kernel=True)
    func = _func_gsea_torch if eng == "gpu" else _func_gsea
    resolved_net = _resolve_net(signatures, net)
    return _run(
        name="gsea",
        func=func,
        adj=False,
        test=True,
        data=data,
        net=resolved_net,
        tmin=tmin,
        raw=raw,
        empty=empty,
        bsize=bsize,
        verbose=verbose,
        times=times,
        seed=seed,
    )
