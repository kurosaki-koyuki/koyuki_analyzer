# Vendored from `decoupler` (https://github.com/scverse/decoupler) by
# omicverse for in-tree GPU acceleration work. Original copyright by
# the decoupler authors, redistributed under decoupler's GPL-3.0
# license. Cross-module imports rewritten from `decoupler.*` to
# `omicverse.es.*` (see scripts/vendor_decoupler.py).

import math

import numba as nb
import numpy as np
import scipy.sparse as sps
import scipy.stats as sts
from tqdm.auto import tqdm

from .._monitor import monitor
from .._registry import register_function

from ._net import _resolve_net
from ._run import _run
from ._net import _getset

def _maxn() -> int:
    l = 1
    n = 2
    h = float("inf")
    while l < n:
        if abs(math.lgamma(n + 1) - math.lgamma(n) - math.log(n)) >= 1:
            h = n
        else:
            l = n
        n = int((l + min(h, l * 3)) / 2)
    return n

MAXN = _maxn()

@nb.njit(cache=True)
def _mlnTest2t(
    a: int,
    ab: int,
    ac: int,
    abcd: int,
):
    if 0 > a or a > ab or a > ac or ab + ac > abcd + a:
        raise ValueError("invalid contingency table")
    if abcd > MAXN:
        raise OverflowError("the grand total of contingency table is too large")
    a_min = max(0, ab + ac - abcd)
    a_max = min(ab, ac)
    if a_min == a_max:
        return 0.0
    p0 = (
        math.lgamma(ab + 1)
        + math.lgamma(ac + 1)
        + math.lgamma(abcd - ac + 1)
        + math.lgamma(abcd - ab + 1)
        - math.lgamma(abcd + 1)
    )
    pa = math.lgamma(a + 1) + math.lgamma(ab - a + 1) + math.lgamma(ac - a + 1) + math.lgamma(abcd - ab - ac + a + 1)
    st = 1.0
    if ab * ac < a * abcd:
        for i in range(min(a - 1, int(round(ab * ac / abcd))), a_min - 1, -1):
            pi = (
                math.lgamma(i + 1)
                + math.lgamma(ab - i + 1)
                + math.lgamma(ac - i + 1)
                + math.lgamma(abcd - ab - ac + i + 1)
            )
            if pi < pa:
                continue
            st_new = st + math.exp(pa - pi)
            if st_new == st:
                break
            st = st_new
        for i in range(a + 1, a_max + 1):
            pi = (
                math.lgamma(i + 1)
                + math.lgamma(ab - i + 1)
                + math.lgamma(ac - i + 1)
                + math.lgamma(abcd - ab - ac + i + 1)
            )
            st_new = st + math.exp(pa - pi)
            if st_new == st:
                break
            st = st_new
    else:
        for i in range(a - 1, a_min - 1, -1):
            pi = (
                math.lgamma(i + 1)
                + math.lgamma(ab - i + 1)
                + math.lgamma(ac - i + 1)
                + math.lgamma(abcd - ab - ac + i + 1)
            )
            st_new = st + math.exp(pa - pi)
            if st_new == st:
                break
            st = st_new
        for i in range(max(a + 1, int(round(ab * ac / abcd))), a_max + 1):
            pi = (
                math.lgamma(i + 1)
                + math.lgamma(ab - i + 1)
                + math.lgamma(ac - i + 1)
                + math.lgamma(abcd - ab - ac + i + 1)
            )
            if pi < pa:
                continue
            st_new = st + math.exp(pa - pi)
            if st_new == st:
                break
            st = st_new
    return max(0, pa - p0 - math.log(st))

@nb.njit(cache=True)
def _test1t(
    a: int,
    b: int,
    c: int,
    d: int,
) -> float:
    # https://github.com/painyeph/FishersExactTest/blob/master/fisher.py
    return math.exp(-_mlnTest2t(a, a + b, a + c, a + b + c + d))

@nb.njit(cache=True)
def _oddsr(
    a: int | float,
    b: int | float,
    c: int | float,
    d: int | float,
    ha_corr: int | float = 0.5,
    log: bool = True,
) -> float:
    # Haldane-Anscombe correction
    a += ha_corr
    b += ha_corr
    c += ha_corr
    d += ha_corr
    r = (a * d) / (b * c)
    if log and r != 0.0:
        r = math.log(r)
    return r

@nb.njit(parallel=True, cache=True)
def _runora(
    row: set,
    ranks: set,
    cnct: np.ndarray,
    starts: np.ndarray,
    offsets: np.ndarray,
    n_bg: int | None,
    ha_corr: int | float = 0.5,
) -> tuple[float, float]:
    nsrc = starts.size
    # Transform to set
    es = np.zeros(nsrc)
    pv = np.zeros(nsrc)
    for j in nb.prange(nsrc):
        # Extract feature set
        fset = _getset(cnct=cnct, starts=starts, offsets=offsets, j=j)
        fset = set(fset)
        # Build table
        set_a = row.intersection(fset)
        set_b = fset.difference(row)
        set_c = row.difference(fset)
        a = len(set_a)
        b = len(set_b)
        c = len(set_c)
        if n_bg == 0:
            set_u = set_a.union(set_b).union(set_c)
            set_d = ranks.difference(set_u)
            d = len(set_d)
        else:
            d = n_bg - a - b - c
        es[j] = _oddsr(a=a, b=b, c=c, d=d, ha_corr=ha_corr, log=True)
        pv[j] = _test1t(a=a, b=b, c=c, d=d)
    return es, pv

def _func_ora(
    mat: np.ndarray,
    cnct: np.ndarray,
    starts: np.ndarray,
    offsets: np.ndarray,
    n_up: int | float | None = None,
    n_bm: int | float = 0,
    n_bg: int | float | None = 20_000,
    ha_corr: int | float = 0.5,
    verbose: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    r"""
    Over Representation Analysis (ORA) :cite:`ora`.

    This approach first creates a contingency table.

    .. list-table:: 2×2 Contingency Table
       :header-rows: 1
       :widths: 20 20 20

       * -
         - :math:`\in F`
         - :math:`\notin F`
       * - :math:`\in Sign. features`
         - :math:`a`
         - :math:`b`
       * - :math:`\notin Sign. features`
         - :math:`c`
         - :math:`d`

    Where:

    - :math:`a` is the number of features that are both significant and in :math:`F`
    - :math:`b` is the number of features that are signficiant but not in :math:`F`
    - :math:`c` is the number of features that are not signficiant but in :math:`F`
    - :math:`d` is the number of features that are not signficiant and not in :math:`F`

    .. figure:: /_static/images/ora.png
       :alt: Over Representation Analysis (ORA) schematic.
       :align: center
       :width: 100%

       Over Representation Analysis (ORA) scheme.

    The statistic is calculated as the Odds Ratio :math:`OR` with Haldane-Anscombe correction.

    .. math::

        \text{OR} = \log{\frac{\frac{a + 0.5}{b + 0.5}}{\frac{c + 0.5}{d + 0.5}}}

    And the :math:`p_{value}` is obtained afer computing a two-tailed Fisher’s exact test with the same table.

    Parameters
    ----------

    n_up
        Number of top-ranked features, based on their magnitude, to select as observed features.
        If ``None``, the top 5% of positive features are selected.
    n_bm
        Number of bottom-ranked features, based on their magnitude, to select as observed features.
    %(n_bg)s
    %(ha_corr)s

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
        ov.es.ora(adata, net, tmin=3)
    """
    nobs, nvar = mat.shape
    nsrc = starts.size
    if n_up is None:
        n_up = int(np.max([np.ceil(0.05 * nvar), 2]))
    if n_bg is None:
        n_bg = 0
    assert isinstance(n_up, int | float) and n_up > 0, "n_up must be numeric and > 0"
    assert isinstance(n_bm, int | float) and n_bm >= 0, "n_bm must be numeric and positive"
    assert isinstance(n_bg, int | float) and n_bg >= 0, "n_bg must be numeric and positive"
    es = np.zeros((nobs, nsrc))
    pv = np.zeros((nobs, nsrc))
    ranks = np.arange(nvar, dtype=np.int_)
    for i in tqdm(range(nobs), disable=not verbose):
        if isinstance(mat, sps.csr_matrix):
            row = mat[i].toarray()[0]
        else:
            row = mat[i]
        # Find ranks
        row = sts.rankdata(row, method="ordinal")
        row = ranks[(row > n_up) | (row < n_bm)]
        es[i], pv[i] = _runora(
            row=set(row), ranks=set(ranks), cnct=cnct, starts=starts, offsets=offsets, n_bg=n_bg, ha_corr=ha_corr
        )
    return es, pv

def _func_ora_torch(
    mat,
    cnct,
    starts,
    offsets,
    n_up=None,
    n_bm: int | float = 0,
    n_bg: int | float | None = 20_000,
    ha_corr: int | float = 0.5,
    verbose: bool = False,
):
    r"""Torch (GPU) port of ORA.

    Algorithm
    ---------
    For each cell we form the "significant" gene set as ranks > n_up
    (top of the distribution) **or** rank < n_bm (bottom). Then for
    each (cell, signature) we tabulate

        a = |significant ∩ signature|
        b = |signature \\ significant| = |signature| − a
        c = |significant \\ signature| = |significant| − a
        d = n_bg − a − b − c   (or total - a-b-c when n_bg == 0)

    and compute

        log-OR(a,b,c,d)        — Haldane-Anscombe-corrected log odds
        Fisher one-tail p      — hypergeometric ≥ a in (N, K, n) urn

    Vectorisation: build a binary ``significant[nobs, nvar]`` mask via
    ``argsort + scatter`` (top-N pattern), build the standard
    ``membership[nvar, nsrc]``, then ``a = significant @ membership``
    in one batched matmul. Per-cell + per-sig totals fall out of
    bool reductions.

    The Fisher exact test stays on scipy — ``scipy.stats.hypergeom.sf``
    is vectorised in C and runs in a few ms for a (nobs, nsrc) batch,
    which beats hand-rolling a torch betainc for typical workloads
    (same finding as for ulm/mlm earlier in this PR).
    """
    import torch
    import scipy.stats as _sts
    from ._engine import torch_device, to_gpu_dense

    device = torch_device()
    M = to_gpu_dense(mat, device, dtype=torch.float64)
    nobs, nvar = M.shape
    nsrc = starts.size

    if n_up is None:
        n_up = int(np.max([np.ceil(0.05 * nvar), 2]))
    if n_bg is None:
        n_bg_use = 0  # signal: use significant-gene-specific background later
    else:
        n_bg_use = int(n_bg)
    n_up_int = int(n_up)
    n_bm_int = int(n_bm)

    # ``rankdata(..., method='ordinal')`` ⇔ ``argsort(stable=True)`` then
    # invert the permutation to get 1..nvar ranks per cell.
    sort_idx = torch.argsort(M, dim=1, stable=True)                 # ascending
    ranks = torch.empty_like(sort_idx, dtype=torch.long)
    seq = torch.arange(1, nvar + 1, dtype=torch.long, device=device).unsqueeze(0)
    ranks.scatter_(1, sort_idx, seq.expand(nobs, -1))               # 1..nvar
    significant = (ranks > n_up_int) | (ranks < n_bm_int)            # (nobs, nvar) bool

    # Build the (nvar × nsrc) signature-membership matrix on GPU.
    membership = torch.zeros(nvar, nsrc, dtype=torch.float32, device=device)
    cnct_t = torch.as_tensor(cnct, dtype=torch.long, device=device)
    sig_id = torch.as_tensor(
        np.repeat(np.arange(nsrc, dtype=np.int64), offsets), device=device,
    )
    membership[cnct_t, sig_id] = 1.0

    # a[i, j] = |significant_i ∩ fset_j|
    a = significant.to(torch.float32) @ membership                  # (nobs, nsrc)
    fset_size = membership.sum(dim=0)                               # (nsrc,)
    sig_size = significant.sum(dim=1, dtype=torch.float32)           # (nobs,)
    b = fset_size.unsqueeze(0) - a                                  # (nobs, nsrc)
    c = sig_size.unsqueeze(1) - a                                   # (nobs, nsrc)
    if n_bg_use == 0:
        # Background = full panel size minus union of (a, b, c) — but
        # since a+b is |fset| and a+c is |significant|, |union| =
        # a + b + c (genes in either group). So d = nvar − a − b − c.
        d = float(nvar) - a - b - c
    else:
        d = float(n_bg_use) - a - b - c

    # Haldane-Anscombe corrected log odds ratio (GPU).
    a_c = a + ha_corr
    b_c = b + ha_corr
    c_c = c + ha_corr
    d_c = d + ha_corr
    es = torch.log((a_c * d_c) / (b_c * c_c))                       # (nobs, nsrc)

    # Hypergeometric survival on GPU via lgamma-based PMF sum
    # (``hypergeom_sf_torch``). Replaces ``scipy.stats.hypergeom.sf``
    # which loops per element in C and was ~700× slower than the
    # batched torch path at the (nobs, nsrc) shapes ora produces.
    from ._engine import hypergeom_sf_torch
    pv_t = hypergeom_sf_torch(
        a.to(torch.long), b.to(torch.long),
        c.to(torch.long), d.to(torch.long),
    )

    return es.cpu().numpy(), pv_t.cpu().numpy()


_func_ora_torch._accepts_sparse = True


@monitor
@register_function(
    aliases=['ora', 'ORA', 'over_representation', '超几何富集'],
    category="enrichment",
    description=(
        "Over-Representation Analysis (ORA). Builds a per-cell 2×2 contingency table and reports the log odds ratio + Fisher exact tail."
    ),
    prerequisites={"optional_functions": ["preprocess"]},
    requires={"var": ["gene symbols matching signature keys"]},
    produces={"obsm": ["score_ora", "padj_ora"]},
    auto_fix="none",
    examples=[
        "ov.es.ora(adata, signatures=sigs)",
        "ov.es.ora(adata, signatures=pathway_dict, engine='gpu', tmin=3)",
    ],
    related=["aucell", "gsea", "gsva", "ulm", "mlm", "waggr", "zscore", "viper", "mdt", "udt"],
)
def ora(
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
    n_up: int | float | None = None,
    n_bm: int | float = 0,
    n_bg: int | float = 20000,
    ha_corr: float = 0.5,
):
    r"""Per-cell hypergeometric over-representation test for a signature.

    .. math::

        OR = \log\!\left(\frac{(a+0.5)(d+0.5)}{(b+0.5)(c+0.5)}\right),\quad p = P(X \ge a)\text{ under hypergeometric}

    Reference: `Fisher, J R Stat Soc (1922) <https://doi.org/10.2307/2340521>`_.

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
        n_up: Top-ranked features used as the 'significant' set per cell. ``None`` picks the top 5 %.
        n_bm: Bottom-ranked features used as the 'background'. ``0`` means use all non-significant features.
        n_bg: Total background population size for the hypergeometric tail.
        ha_corr: Haldane–Anscombe continuity correction added to each cell of the 2×2 table.

    Returns:
        None. Writes ``adata.obsm['score_ora']`` and ``adata.obsm['padj_ora']``.

    Examples:
        >>> import omicverse as ov
        >>> ov.es.ora(adata, signatures=sigs)
    """
    from ._engine import resolve_engine

    eng = resolve_engine(engine, has_torch_kernel=True)
    func = _func_ora_torch if eng == "gpu" else _func_ora
    resolved_net = _resolve_net(signatures, net)
    return _run(
        name="ora",
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
        n_up=n_up,
        n_bm=n_bm,
        n_bg=n_bg,
        ha_corr=ha_corr,
    )
