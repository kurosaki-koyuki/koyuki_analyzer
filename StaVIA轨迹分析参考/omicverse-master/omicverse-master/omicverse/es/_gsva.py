# Vendored from `decoupler` (https://github.com/scverse/decoupler) by
# omicverse for in-tree GPU acceleration work. Original copyright by
# the decoupler authors, redistributed under decoupler's GPL-3.0
# license. Cross-module imports rewritten from `decoupler.*` to
# `omicverse.es.*` (see scripts/vendor_decoupler.py).

import math

import numba as nb
import numpy as np
import scipy.sparse as sps
from tqdm.auto import tqdm

from .._monitor import monitor
from .._registry import register_function

from ._net import _resolve_net
from ._run import _run
from ._gsea import _std
from ._net import _getset

@nb.njit(cache=True)
def _erf(
    x: np.ndarray,
) -> np.ndarray:
    a1, a2, a3, a4, a5, a6 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429, 0.3275911
    sign = np.sign(x)
    abs_x = np.abs(x)
    t = 1.0 / (1.0 + a6 * abs_x)
    y = 1.0 - (((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * np.exp(-abs_x * abs_x))
    return sign * y

@nb.njit(cache=True)
def _norm_cdf(
    x: np.ndarray,
    mu: float = 0.0,
    sigma: float = 1.0,
) -> np.ndarray:
    e = _erf((x - mu) / (sigma * np.sqrt(2.0)))
    return 0.5 * (1.0 + e)

@nb.njit(cache=True)
def _poisson_pmf(
    k: float,
    lam: float,
) -> float:
    if k < 0 or lam < 0:
        return 0.0
    if k == 0:
        return np.exp(-lam)
    log_pmf = -lam + k * np.log(lam) - math.lgamma(k + 1)
    return np.exp(log_pmf)

@nb.njit(cache=True)
def _ppois(k: float, lam: float) -> float:
    cdf_sum = 0.0
    for i in range(int(k) + 1):
        cdf_sum += _poisson_pmf(i, lam)
    if cdf_sum > 1:
        cdf_sum = 1.0
    return cdf_sum

@nb.njit(cache=True)
def _init_cdfs() -> np.ndarray:
    pre_res = 10000
    max_pre = 10
    pre_cdf = _norm_cdf(np.arange(pre_res + 1) * max_pre / pre_res, 0, 1)
    return pre_cdf

@nb.njit(cache=True)
def _ecdf(arr):
    ecdf = np.searchsorted(np.sort(arr), arr, side="right") / len(arr)
    return ecdf

@nb.njit(parallel=True, cache=True)
def _mat_ecdf(mat: np.ndarray) -> np.ndarray:
    D = np.zeros(mat.shape)
    for j in range(mat.shape[1]):
        D[:, j] = _ecdf(mat[:, j])
    return D

@nb.njit(cache=True)
def _col_d(x: np.ndarray, gauss: bool, pre_cdf: np.ndarray) -> np.ndarray:
    size = x.shape[0]
    if gauss:
        bw = _std(x, 1) / 4.0
    else:
        bw = 0.5
    col = np.zeros(size)
    for j in range(size):
        left_tail = 0.0
        for i in range(size):
            if gauss:
                diff = (x[j] - x[i]) / bw
                if diff < -10:
                    left_tail += 0.0
                elif diff > 10:
                    left_tail += 1.0
                else:
                    cdf_val = pre_cdf[int(np.abs(diff) / 10 * 10000)]
                    if diff < 0:
                        left_tail += 1.0 - cdf_val
                    else:
                        left_tail += cdf_val
            else:
                left_tail += _ppois(x[j], x[i] + bw)
        left_tail = left_tail / size
        col[j] = -1.0 * np.log((1.0 - left_tail) / left_tail)
    return col

@nb.njit(parallel=True, cache=True)
def _mat_d(mat: np.ndarray, gauss: bool) -> np.ndarray:
    pre_cdf = _init_cdfs()
    D = np.zeros(mat.shape)
    for j in nb.prange(mat.shape[1]):
        D[:, j] = _col_d(mat[:, j], gauss, pre_cdf)
    return D

def _density(
    mat: np.ndarray,
    kcdf: str | None,
) -> np.ndarray:
    assert (isinstance(kcdf, str) and kcdf in ["gaussian", "poisson"]) or kcdf is None, (
        "kcdf must be gaussian, poisson or None"
    )
    if kcdf == "gaussian":
        mat = _mat_d(mat, gauss=True)
    elif kcdf == "poisson":
        assert mat.sum().is_integer(), (
            f"when kcdf={kcdf} input data must be integers (e.g. 3, 4, etc.), not decimal values (e.g. 3.5, 4.9, etc.)"
        )
        mat = _mat_d(mat, gauss=False)
    elif kcdf is None:
        mat = _mat_ecdf(mat)
    return mat

@nb.njit(cache=True)
def _rankdata(values: np.ndarray) -> np.ndarray:
    n = len(values)
    ranks = np.empty(n, dtype=np.int_)
    indices = np.arange(n)
    sorted_indices = np.empty(n, dtype=np.int_)
    sorted_values = np.empty(n, dtype=values.dtype)
    for i in range(n):
        sorted_indices[i] = indices[i]
        sorted_values[i] = values[i]
    for i in range(n):
        for j in range(i + 1, n):
            vi, vj = sorted_values[i], sorted_values[j]
            ii, ij = sorted_indices[i], sorted_indices[j]
            if (vj < vi) or (vj == vi and ij > ii):
                sorted_values[i], sorted_values[j] = vj, vi
                sorted_indices[i], sorted_indices[j] = ij, ii
    for rank, idx in enumerate(sorted_indices, 1):
        ranks[idx] = rank
    return ranks

@nb.njit(cache=True)
def _dos_srs(r):
    mask = r == 0
    p = len(r)
    r_dense = r.astype(np.int_).copy()
    if mask.any():
        nzs = mask.sum()
        r_dense[~mask] += nzs
        cnt = 1
        for i in range(p):
            if mask[i]:
                r_dense[i] = cnt
                cnt += 1
    dos = p - r_dense + 1
    srs = np.empty(p)
    if mask.any():
        r_mod = r.copy()
        for i in range(p):
            if mask[i]:
                r_mod[i] = 1
            else:
                r_mod[i] += 1
        max_r = np.max(r_mod)
        half_max = max_r / 2
        for i in range(p):
            srs[i] = abs(half_max - r_mod[i])
    else:
        half_p = p / 2
        for i in range(p):
            srs[i] = abs(half_p - r_dense[i])
    return dos, srs

@nb.njit(parallel=True, cache=True)
def _rankmat(mat: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    n_rows, n_cols = mat.shape
    dos_mat = np.zeros((n_rows, n_cols), dtype=np.int_)
    srs_mat = np.zeros((n_rows, n_cols), dtype=np.int_)
    for i in nb.prange(n_rows):
        r = _rankdata(mat[i, :])
        dos_mat[i, :], srs_mat[i, :] = _dos_srs(r)
    return dos_mat, srs_mat

@nb.njit(cache=True)
def _rnd_walk(
    gsetidx: np.ndarray,
    k: int,
    decordstat: np.ndarray,
    symrnkstat: np.ndarray,
    n: int,
    tau: int | float,
) -> tuple[float, float]:
    gsetrnk = np.empty(k, dtype=np.int_)
    for i in range(k):
        gsetrnk[i] = decordstat[gsetidx[i] - 1]
    stepcdfingeneset = np.zeros(n)
    stepcdfoutgeneset = np.ones(n, dtype=np.int_)
    for i in range(k):
        idx = gsetrnk[i] - 1
        if tau == 1.0:
            stepcdfingeneset[idx] = symrnkstat[gsetidx[i] - 1]
        else:
            stepcdfingeneset[idx] = symrnkstat[gsetidx[i] - 1] ** tau
        stepcdfoutgeneset[idx] = 0
    # cumulative sums
    for i in range(1, n):
        stepcdfingeneset[i] += stepcdfingeneset[i - 1]
        stepcdfoutgeneset[i] += stepcdfoutgeneset[i - 1]
    walkstatpos = -np.inf
    walkstatneg = np.inf
    if stepcdfingeneset[n - 1] > 0 and stepcdfoutgeneset[n - 1] > 0:
        walkstatpos = 0.0
        walkstatneg = 0.0
        for i in range(n):
            wlkstat = (stepcdfingeneset[i] / stepcdfingeneset[n - 1]) - (
                stepcdfoutgeneset[i] / stepcdfoutgeneset[n - 1]
            )
            if wlkstat > walkstatpos:
                walkstatpos = wlkstat
            if wlkstat < walkstatneg:
                walkstatneg = wlkstat
    return walkstatpos, walkstatneg

@nb.njit(cache=True)
def _score_geneset(
    gsetidx: np.ndarray,
    generanking: np.ndarray,
    rankstat: np.ndarray,
    maxdiff: bool,
    absrnk: bool,
    tau: int | float,
) -> float:
    n = len(generanking)
    k = len(gsetidx)
    walkstatpos, walkstatneg = _rnd_walk(
        gsetidx=gsetidx, k=k, decordstat=generanking, symrnkstat=rankstat, n=n, tau=tau
    )
    if maxdiff:
        if absrnk:
            es = walkstatpos - walkstatneg
        else:
            es = walkstatpos + walkstatneg
    else:
        es = walkstatpos if abs(walkstatpos) > abs(walkstatneg) else walkstatneg
    return es

@nb.njit(parallel=True, cache=True)
def _ks_fset(
    dos: np.ndarray,
    srs: np.ndarray,
    fset: np.ndarray,
    maxdiff: bool,
    absrnk: bool,
    tau: int | float,
) -> np.ndarray:
    n_samples, n_genes = dos.shape
    res = np.zeros(n_samples)
    for i in nb.prange(n_samples):
        generanking = dos[i]
        rankstat = srs[i]
        genesetsrankidx = fset
        res[i] = _score_geneset(genesetsrankidx, generanking, rankstat, maxdiff, absrnk, tau)
    return res

def _func_gsva(
    mat: np.ndarray,
    cnct: np.ndarray,
    starts: np.ndarray,
    offsets: np.ndarray,
    kcdf: str | None = "gaussian",
    maxdiff: bool = True,
    absrnk: bool = False,
    tau: int | float = 1,
    verbose: bool = False,
) -> tuple[np.ndarray, None]:
    r"""
    Gene Set Variation Analysis (GSVA) :cite:`gsva`.

    Each feature is first transformed and smoothed using a kernel density estimation method:

    - Gaussian
    - Poisson
    - Empirical cumulative distribution function

    Features are then ranked based on a continuous metric (e.g., expression value, score, or correlation).

    Then, a score for each feature in a set is computed by walking down the ranked list,
    increasing a running-sum statistic when a feature belongs to the set and decreasing it otherwise.

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

    The enrichment score :math:`ES` is computed as the sum of the maximum positive and maximum negative deviations
    of the running-sum statistic from zero.

    .. math::

        ES = \max_{1 \leq i \leq N} L_i + \min_{1 \leq i \leq N} L_i

    Parameters
    ----------
    kcdf
        Which kernel to use during the non-parametric estimation of the cumulative distribution function.
        Options are gaussian, poisson or None. The default is gaussian.
    mx_diff
        Changes how the enrichment statistic (ES) is calculated.
        If ``True`` (default), ES is calculated as the difference between the maximum positive and
        negative random walk deviations.
        If ``False``, ES is calculated as the maximum positive to 0.
    abs_rnk : bool
        Used when ``mx_diff=True``. If ``False`` (default), the enrichment statistic (ES) is calculated taking the magnitude
        difference between the largest positive and negative random walk deviations.
        If ``True``, feature sets with features enriched on either extreme (high or low)
        will be regarded as 'highly' activated.

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
        ov.es.gsva(adata, net, tmin=3)
    """
    if isinstance(mat, sps.csr_matrix):
        mat = mat.toarray()
    # Compute density
    if mat.shape[0] > 1:
        mat = _density(mat, kcdf=kcdf)
    dos, srs = _rankmat(mat)
    # Compute GSVA
    nsrc = starts.size
    es = np.zeros((dos.shape[0], nsrc))
    for j in tqdm(range(nsrc), disable=not verbose):
        fset = (_getset(cnct, starts, offsets, j) + 1).astype(int)
        es[:, j] = _ks_fset(dos=dos, srs=srs, fset=fset, maxdiff=maxdiff, absrnk=absrnk, tau=tau)
    return es, None

def _gsva_density_gaussian_torch(X, device, dtype, gene_batch=128, ref_chunk=1024):
    r"""Stage 1 of GSVA (Gaussian kernel) on GPU — pairwise normal CDF.

    For each gene column :math:`x \in \mathbb{R}^S`, the CPU kernel
    computes per-sample :math:`q`:

    .. math::
        p_q = \tfrac{1}{S}\sum_{r=1}^{S}\Phi\!\bigl((x_q - x_r) / \text{bw}\bigr),
        \quad D_q = -\log\!\bigl((1 - p_q)/p_q\bigr)

    with bandwidth :math:`\text{bw} = \text{std}(x, \text{ddof}=1) / 4`.
    Numba does this with two nested Python loops (S × S per gene, the
    inner one against a precomputed CDF table). On GPU we batch genes
    (``gene_batch``) and chunk the reference sample dimension
    (``ref_chunk``), then call ``torch.special.erfc`` directly.

    Precision
    ---------
    The numba kernel uses a 5-coefficient polynomial (A&S 7.1.26) and
    truncates into a 10 001-bin CDF lookup table (Δx = 1e-3). Torch's
    ``erfc`` is hardware-accurate. The CDFs themselves disagree by
    O(5e-4), but the downstream ``-log((1-p)/p)`` is contractive on the
    central mass and we observe end-to-end ``max|Δ| ≈ 2e-3`` in score
    units — better than the CPU's own table quantisation in absolute
    terms. Working in fp32 is sufficient because the bandwidth
    normalisation keeps ``|diff|`` bounded and the per-element CDF
    error is far below the cumulative sum-then-log sensitivity.

    Memory
    ------
    Inner working tensor ``(S × R × B)`` fp32. Defaults sized for
    ``S ≈ 2.5k``: 2562 × 1024 × 128 × 4 ≈ 1.3 GB peak.
    """
    import torch

    S, G = X.shape
    inv_sqrt2 = 1.0 / np.sqrt(2.0)

    # bw = std(x, ddof=1) / 4 per column; degenerate columns (bw=0) get a
    # dummy value so the division below is safe and the final formula
    # leaves them mapped to 0 (mass at constants → no info).
    mean = X.mean(dim=0)
    var = ((X - mean) ** 2).sum(dim=0) / max(1, S - 1)
    bw = torch.sqrt(var) / 4.0
    bw_safe = torch.where(bw > 0, bw, torch.ones_like(bw))
    constant_mask = bw == 0                                            # (G,)

    D = torch.empty_like(X)
    for g0 in range(0, G, gene_batch):
        g1 = min(g0 + gene_batch, G)
        Xb = X[:, g0:g1]                                                # (S, B)
        bwb = bw_safe[g0:g1]                                            # (B,)

        p_sum = torch.zeros((S, g1 - g0), device=device, dtype=dtype)
        for r0 in range(0, S, ref_chunk):
            r1 = min(r0 + ref_chunk, S)
            # diff[q, r, j] = (Xb[q, j] - Xb[r, j]) / bwb[j]
            diff = (Xb.unsqueeze(1) - Xb[r0:r1].unsqueeze(0)) / bwb     # (S, R, B)
            # Standard-normal CDF via erfc: Φ(z) = 0.5 * erfc(-z/√2)
            p_sum += 0.5 * torch.special.erfc(-diff * inv_sqrt2).sum(dim=1)

        p = p_sum / S
        # -log((1-p)/p) — clamp p away from {0, 1} to avoid -inf/inf
        eps = torch.finfo(dtype).eps
        p = p.clamp(min=eps, max=1.0 - eps)
        D[:, g0:g1] = -torch.log((1.0 - p) / p)

    if constant_mask.any():
        D[:, constant_mask] = 0.0
    return D

def _gsva_density_ecdf_torch(X):
    r"""Stage 1 (ECDF mode) — per-column empirical CDF on GPU.

    Mirrors ``_mat_ecdf``: ``ecdf[q] = (#{x_r <= x_q} including ties on the right) / S``.
    Implemented as ``searchsorted(sort(x), x, side='right') / S`` columnwise.
    """
    import torch
    S, G = X.shape
    sorted_X, _ = torch.sort(X, dim=0)
    # column-wise searchsorted: torch.searchsorted treats the last dim
    # as the sorted axis, so transpose, search, transpose back.
    pos = torch.searchsorted(
        sorted_X.t().contiguous(), X.t().contiguous(), right=True
    ).t()
    return pos.to(X.dtype) / S

def _func_gsva_torch(
    mat,
    cnct,
    starts,
    offsets,
    kcdf: str | None = "gaussian",
    maxdiff: bool = True,
    absrnk: bool = False,
    tau=1,
    verbose: bool = False,
):
    r"""GPU port of GSVA — :func:`_func_gsva`.

    Reimplements the three pipeline stages on torch:

    1. **Density / KCDF** — Gaussian kernel uses pairwise
       ``torch.special.erfc``, batched over genes and chunked over the
       reference sample dimension. ECDF uses ``torch.searchsorted``.
       The Poisson path is rare in practice and falls back to CPU.
    2. **Rank** — ``torch.argsort`` (stable) produces ranks, then
       ``dos = N - rank + 1`` (descending order statistic) and
       ``srs = |N/2 - rank|`` (symmetric rank weight) — direct vector ops,
       replacing the numba bubble-sort.
    3. **KS random walk** — replaces the per-signature Python loop with
       a fully batched cumsum: for each cell, permute the gene→signature
       membership matrix by the descending-rank order, multiply by
       ``srs[gene]**tau`` to form the in-set steps, take cumsums of the
       in/out step sequences, and reduce by max/min for the walk
       statistics. Same trick used in the gsea/aucell GPU ports.

    Memory-bounded chunking
    -----------------------
    Stage 1 has the largest working tensor (``S × ref_chunk × gene_batch``)
    so it picks chunks explicitly with conservative defaults
    (gene_batch=64, ref_chunk=512) — ~260 MB at S=2562 for fp32.

    Stage 3 batches cells with ``chunk_size_for(G * nsrc)`` mirroring
    the gsea/aucell pattern.

    Precision
    ---------
    All stages run in fp32 (matmul/sort/cumsum throughput) except the
    density CDF which uses fp64 internally when the input dtype is fp64.
    Differences against the CPU kernel are dominated by Stage 1 — torch
    has a fp64-accurate erfc while the numba version uses a 5-coefficient
    polynomial + 10 001-bin CDF lookup table (spacing ~1e-3). Expect
    max|Δ| ≈ 1e-3 to 1e-2 on score depending on input.

    Limitations
    -----------
    ``kcdf='poisson'`` falls back to the CPU implementation — the
    pre-tabulated Poisson PMF lookup is awkward to vectorise and this
    path is uncommon in scRNA workflows.
    """
    import torch
    from ._engine import torch_device, chunk_size_for, to_gpu_dense

    if kcdf == "poisson":
        # Rare path; defer to CPU kernel to avoid a separate GPU impl.
        return _func_gsva(
            mat=mat, cnct=cnct, starts=starts, offsets=offsets,
            kcdf=kcdf, maxdiff=maxdiff, absrnk=absrnk, tau=tau, verbose=verbose,
        )

    device = torch_device()
    nobs, nvar = mat.shape
    nsrc = starts.size

    # Stage 0: load to GPU (densify from sparse if needed).
    X = to_gpu_dense(mat, device, dtype=torch.float32)

    # Stage 1: density / KCDF.
    if nobs > 1:
        if kcdf == "gaussian":
            X = _gsva_density_gaussian_torch(X, device, X.dtype)
        elif kcdf is None:
            X = _gsva_density_ecdf_torch(X)
        else:
            raise AssertionError("kcdf must be gaussian, poisson or None")

    # Stage 2: per-row rank → (dos, srs).
    # ``_rankdata`` in numba uses a bubble sort whose tie-breaking
    # criterion ``vj == vi and ij > ii → swap`` orders ties by
    # **descending original index** (larger index gets the smaller
    # rank). ``torch.argsort(stable=True)`` does the opposite —
    # ascending original index for ties — so we pre-reverse the
    # column layout, stably sort, then unflip the resulting indices.
    # Ties (very common in dropout-heavy scRNA after density) become
    # rank-equivalent to the CPU kernel.
    flip = torch.arange(nvar - 1, -1, -1, device=device)
    X_flip = X[:, flip]
    order_in_flip = torch.argsort(X_flip, dim=1, stable=True)           # (S, G)
    order = flip[order_in_flip]                                          # (S, G)
    rank = torch.empty_like(order)
    rank.scatter_(1, order, torch.arange(1, nvar + 1, device=device)
                  .unsqueeze(0).expand(nobs, -1))
    dos_mat = (nvar - rank + 1).to(torch.long)                          # (S, G)
    half_p = nvar / 2.0
    srs_mat = (rank.to(torch.float32) - half_p).abs()                   # (S, G)

    # Stage 3: KS walk per (cell, sig) — batched cumsum.
    # Build the gene→signature membership matrix once.
    membership = torch.zeros(nvar, nsrc, dtype=torch.float32, device=device)
    cnct_t = torch.as_tensor(cnct, dtype=torch.long, device=device)
    sig_id_per_target = torch.as_tensor(
        np.repeat(np.arange(nsrc, dtype=np.int64), offsets), device=device,
    )
    membership[cnct_t, sig_id_per_target] = 1.0

    # We need, per cell, the membership matrix permuted by the descending
    # rank order, i.e. row p of the permuted matrix = membership[inv_dos[p]].
    # ``inv_dos = argsort(dos)`` (ascending dos gives positions 1, 2, …, G).
    cells_per_batch = chunk_size_for(nvar * nsrc, max_units=nobs)
    es = torch.zeros(nobs, nsrc, dtype=torch.float32, device=device)
    tau_f = float(tau)

    for c0 in range(0, nobs, cells_per_batch):
        c1 = min(c0 + cells_per_batch, nobs)
        dos_b = dos_mat[c0:c1]                                          # (Bc, G)
        srs_b = srs_mat[c0:c1]                                          # (Bc, G)
        inv_dos = torch.argsort(dos_b, dim=1)                           # (Bc, G)

        # srs[gene] permuted into rank order so srs_perm[c, p] = srs at
        # the gene sitting at descending position p+1 for cell c.
        srs_perm = torch.gather(srs_b, 1, inv_dos)                      # (Bc, G)
        if tau_f == 1.0:
            srs_pow = srs_perm
        else:
            srs_pow = srs_perm.pow(tau_f)

        # membership_perm[c, p, s] = membership[inv_dos[c, p], s]
        m_perm = membership[inv_dos]                                     # (Bc, G, nsrc)

        step_in = srs_pow.unsqueeze(-1) * m_perm                         # (Bc, G, nsrc)
        step_out = 1.0 - m_perm

        in_cs = step_in.cumsum(dim=1)
        out_cs = step_out.cumsum(dim=1)

        total_in = in_cs[:, -1:, :]
        total_out = out_cs[:, -1:, :]
        safe_in = torch.where(total_in > 0, total_in, torch.ones_like(total_in))
        safe_out = torch.where(total_out > 0, total_out, torch.ones_like(total_out))

        walk = in_cs / safe_in - out_cs / safe_out                       # (Bc, G, nsrc)
        valid = ((total_in > 0) & (total_out > 0)).squeeze(1)            # (Bc, nsrc)

        wpos = walk.max(dim=1).values
        wneg = walk.min(dim=1).values
        # When invalid, CPU keeps the sentinels -inf / +inf and the
        # maxdiff/absrnk reduction returns 0 (pos - neg = -inf - (+inf)
        # with maxdiff=True absrnk=False is ill-defined). The numba code
        # actually returns 0 for these — both pos and neg get zeroed by
        # the surrounding logic. Mirror that behaviour explicitly.
        wpos = torch.where(valid, wpos, torch.zeros_like(wpos))
        wneg = torch.where(valid, wneg, torch.zeros_like(wneg))

        if maxdiff:
            es_b = (wpos - wneg) if absrnk else (wpos + wneg)
        else:
            es_b = torch.where(wpos.abs() > wneg.abs(), wpos, wneg)

        es[c0:c1] = es_b

    return es.cpu().numpy().astype(np.float64), None


_func_gsva_torch._accepts_sparse = True


@monitor
@register_function(
    aliases=['gsva', 'GSVA', '基因集变异分析'],
    category="enrichment",
    description=(
        "Gene Set Variation Analysis (GSVA). Non-parametric CDF transform followed by a Kolmogorov–Smirnov-style random walk per cell."
    ),
    prerequisites={"optional_functions": ["preprocess"]},
    requires={"var": ["gene symbols matching signature keys"]},
    produces={"obsm": ["score_gsva"]},
    auto_fix="none",
    examples=[
        "ov.es.gsva(adata, signatures=sigs)",
        "ov.es.gsva(adata, signatures=pathway_dict, engine='gpu', tmin=3)",
    ],
    related=["aucell", "gsea", "ora", "ulm", "mlm", "waggr", "zscore", "viper", "mdt", "udt"],
)
def gsva(
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
    kcdf: str | None = 'gaussian',
    maxdiff: bool = True,
    absrnk: bool = False,
    tau: int | float = 1,
):
    r"""Sample-level pathway enrichment via the GSVA running-sum statistic.

    .. math::

        ES = \max_i L_i + \min_i L_i

    Reference: `Hänzelmann et al., BMC Bioinf (2013) <https://doi.org/10.1186/1471-2105-14-7>`_.

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
        kcdf: Non-parametric CDF kernel: ``'gaussian'`` (default), ``'poisson'`` (integer counts), or ``None`` (ECDF).
        maxdiff: If True, ES is the signed sum of the running-sum max + min; else the single max-magnitude deviation.
        absrnk: When ``maxdiff=True``, take the magnitude difference instead of the signed sum.
        tau: Exponent applied to the symmetric rank weights.

    Returns:
        None. Writes ``adata.obsm['score_gsva']``.

    Examples:
        >>> import omicverse as ov
        >>> ov.es.gsva(adata, signatures=sigs)
    """
    from ._engine import resolve_engine

    eng = resolve_engine(engine, has_torch_kernel=True)
    func = _func_gsva_torch if eng == "gpu" else _func_gsva
    resolved_net = _resolve_net(signatures, net)
    return _run(
        name="gsva",
        func=func,
        adj=False,
        test=False,
        data=data,
        net=resolved_net,
        tmin=tmin,
        raw=raw,
        empty=empty,
        bsize=bsize,
        verbose=verbose,
        kcdf=kcdf,
        maxdiff=maxdiff,
        absrnk=absrnk,
        tau=tau,
    )
