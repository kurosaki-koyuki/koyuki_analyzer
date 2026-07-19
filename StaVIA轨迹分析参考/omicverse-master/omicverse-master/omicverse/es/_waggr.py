# Vendored from `decoupler` (https://github.com/scverse/decoupler) by
# omicverse for in-tree GPU acceleration work. Original copyright by
# the decoupler authors, redistributed under decoupler's GPL-3.0
# license. Cross-module imports rewritten from `decoupler.*` to
# `omicverse.es.*` (see scripts/vendor_decoupler.py).

import inspect
from collections.abc import Callable

import numba as nb
import numpy as np

from .._monitor import monitor
from .._registry import register_function

from ._net import _resolve_net
from ._run import _run
from ._gsea import _ridx, _std

@nb.njit(cache=True)
def _wsum(
    x: np.ndarray,
    w: np.ndarray,
) -> float:
    return np.sum(x * w)

@nb.njit(cache=True)
def _wmean(
    x: np.ndarray,
    w: np.ndarray,
) -> float:
    agg = _wsum(x, w)
    div: float = np.sum(np.abs(w))
    return agg / div

def _fun(
    f: Callable,
    verbose: bool = False,
):
    @nb.njit(parallel=True, cache=True)
    def _f(mat, adj):
        nobs, nvar = mat.shape
        nvar, nsrc = adj.shape
        es = np.zeros((nobs, nsrc))
        for i in nb.prange(nobs):
            x = mat[i]
            for j in range(nsrc):
                w = adj[:, j]
                es[i, j] = f(x, w)
        return es

    _f.__name__ = f.__name__
    if _f.__name__ not in _cfuncs:
        _cfuncs[f.__name__] = _f

_fun_dict = {
    "wsum": _wsum,
    "wmean": _wmean,
}

_cfuncs: dict = {}

def _validate_args(
    fun: Callable,
    verbose: bool,
) -> Callable:
    args = inspect.signature(fun).parameters
    required_args = ["x", "w"]
    for arg in required_args:
        if arg not in args:
            assert AssertionError(), f"fun={fun.__name__} must contain arguments x and w"
    # Check if any additional arguments have default values
    for param in args.values():
        if param.name not in required_args and param.default == inspect.Parameter.empty:
            assert AssertionError(), f"fun={fun.__name__} has an argument {param.name} without a default value"
    if not hasattr(fun, "func_code"):
        fun = nb.njit(fun)
    return fun

def _validate_func(
    fun: Callable,
    verbose: bool,
) -> None:
    fun = _validate_args(fun=fun, verbose=verbose)
    x = np.array([1.0, 2.0, 3.0])
    w = np.array([-1.0, 0.0, 2.0])
    try:
        res = fun(x=x, w=w)
        assert isinstance(res, int | float), "output of fun must be a single numerical value"
    except Exception as err:
        raise ValueError(f"fun failed to run with test data: fun(x={x}), w={w}") from err
    _fun(f=fun, verbose=verbose)

@nb.njit(parallel=True, cache=True)
def _perm(
    fun: Callable,
    es: np.ndarray,
    mat: np.ndarray,
    adj: np.ndarray,
    idx: np.ndarray,
):
    # Init
    nobs, nvar = mat.shape
    nvar, nsrc = adj.shape
    times, nvar = idx.shape
    null_dst = np.zeros((nobs, nsrc, times))
    pvals = np.zeros((nobs, nsrc))
    # Permute
    for i in nb.prange(times):
        null_dst[:, :, i] = fun(mat[:, idx[i]], adj)
        pvals += np.abs(null_dst[:, :, i]) > np.abs(es)
    # Compute z-score
    nes = np.zeros(es.shape)
    for i in nb.prange(nobs):
        for j in range(nsrc):
            e = es[i, j]
            d = _std(null_dst[i, j, :], 1)
            if d != 0.0:
                n = (e - np.mean(null_dst[i, j, :])) / d
            else:
                if e != 0.0:
                    n = np.inf
                else:
                    n = 0.0
            nes[i, j] = n
    # Compute empirical p-value
    pvals = np.where(pvals == 0.0, 1.0, pvals)
    pvals = np.where(pvals == times, times - 1, pvals)
    pvals = pvals / times
    pvals = np.where(pvals >= 0.5, 1 - (pvals), pvals)
    pvals = pvals * 2
    return nes, pvals

def _func_waggr(
    mat: np.ndarray,
    adj: np.ndarray,
    fun: str | Callable = "wmean",
    times: int | float = 1000,
    seed: int | float = 42,
    verbose: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    r"""
    Weighted Aggregate (WAGGR) :cite:`decoupler`.

    This approach aggregates the molecular features :math:`x_i` from one observation :math:`i` with
    the feature weights :math:`w` of a given feature set :math:`j` into an enrichment score :math:`ES`.

    This method can use any aggregation function, which by default is the weighted mean.

    .. math::

        ES = \frac{\sum_{i=1}^{n} w_i x_i}{\sum_{i=1}^{n} w_i}

    Another simpler option is the weighted sum.

    .. math::

        ES = \sum_{i=1}^{n} w_i x_i

    Alternatively, this method can also take any defined function :math:`f` as long at it aggregates :math:`x_i` and
    :math:`w` into a single :math:`ES`.

    .. math::

        ES = f(w_i, x_i)

    This functionality makes it relatively easy to implement and try new enrichment methods.

    When multiple random permutations are done (``times > 1``), statistical significance is assessed via empirical testing.

    .. math::

        p_{value}=\frac{ES_{rand} \geq ES}{P}

    Where:

    - :math:`ES_{rand}` are the enrichment scores of the random permutations
    - :math:`P` is the total number of permutations

    Additionaly, :math:`ES` is updated to a normalized enrichment score :math:`NES`.

    .. math::

        NES = \frac{ES - \mu(ES_{rand})}{\sigma(ES_{rand})}

    Where:

    - :math:`\mu` is the mean
    - :math:`\sigma` is the standard deviation

    Parameters
    ----------

    fun
        Function to compute enrichment statistic from omics readouts (``x``) and feature weights (``w``).
        Provided function must contain ``x`` and ``w`` arguments and ouput a single float.
        By default, 'wmean' and 'wsum' are implemented.
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
        ov.es.waggr(adata, net, tmin=3)
    """
    assert isinstance(fun, str) or callable(fun), "fun must be str or callable"
    if isinstance(fun, str):
        assert fun in _fun_dict, "when fun is str, it must be wmean or wsum"
        f_fun = _fun_dict[fun]
    else:
        f_fun = fun
    _validate_func(f_fun, verbose=verbose)
    vfun = _cfuncs[f_fun.__name__]
    assert isinstance(times, int | float) and times >= 0, "times must be numeric and >= 0"
    assert isinstance(seed, int | float) and seed >= 0, "seed must be numeric and >= 0"
    times, seed = int(times), int(seed)
    nobs, nvar = mat.shape
    nvar, nsrc = adj.shape
    es = vfun(mat, adj)
    if times > 1:
        idx = _ridx(times=times, nvar=nvar, seed=seed)
        es, pv = _perm(fun=vfun, es=es, mat=mat, adj=adj, idx=idx)
    else:
        pv = np.ones(es.shape)
    return es, pv

def _func_waggr_torch(
    mat,
    adj,
    fun: "str | Callable" = "wmean",
    times: "int | float" = 1000,
    seed: "int | float" = 42,
    verbose: bool = False,
):
    r"""Torch (GPU) port of :func:`_func_waggr` for the deterministic
    aggregation (``wmean`` / ``wsum``).

    The aggregation reduces to a single matmul + per-column
    normalisation:

    - ``wsum``:  :math:`es = \mathrm{mat} @ \mathrm{adj}`
    - ``wmean``: :math:`es = (\mathrm{mat} @ \mathrm{adj}) / \sum |w|`

    Both are trivially vectorised on the GPU. The permutation path
    (``times > 1``) requires a numba-only random-shuffle kernel and is
    not yet ported — when permutations are requested we fall back to
    the CPU kernel transparently.
    """
    if not isinstance(fun, str) or fun not in ("wsum", "wmean") or int(times) > 1:
        # Custom ``fun`` callables and permutation-based p-values stay
        # on the CPU path until a torch equivalent is written. Densify
        # here because the dispatcher passes sparse straight through
        # (we advertise ``_accepts_sparse = True`` for the fast path)
        # and the numba CPU kernel only takes dense arrays.
        import scipy.sparse as _sps
        if _sps.issparse(mat):
            mat = mat.toarray()
        return _func_waggr(mat, adj, fun=fun, times=times, seed=seed, verbose=verbose)

    import torch
    from ._engine import torch_device, to_gpu_dense

    device = torch_device()
    M = to_gpu_dense(mat, device, dtype=torch.float64)
    A = to_gpu_dense(adj, device, dtype=torch.float64)

    es = M @ A
    if fun == "wmean":
        es = es / A.abs().sum(dim=0)

    es_np = es.cpu().numpy()
    pv = np.ones_like(es_np)
    return es_np, pv


_func_waggr_torch._accepts_sparse = True


@monitor
@register_function(
    aliases=['waggr', 'WAGGR', 'weighted_aggregate', '加权聚合'],
    category="enrichment",
    description=(
        "Weighted Aggregate (WAGGR). Weighted mean or weighted sum of signature genes; the simplest enrichment scorer."
    ),
    prerequisites={"optional_functions": ["preprocess"]},
    requires={"var": ["gene symbols matching signature keys"]},
    produces={"obsm": ["score_waggr", "padj_waggr"]},
    auto_fix="none",
    examples=[
        "ov.es.waggr(adata, signatures=sigs)",
        "ov.es.waggr(adata, signatures=pathway_dict, engine='gpu', tmin=3)",
    ],
    related=["aucell", "gsea", "gsva", "ora", "ulm", "mlm", "zscore", "viper", "mdt", "udt"],
)
def waggr(
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
    fun: 'str | Callable' = 'wmean',
    times: int | float = 1000,
    seed: int | float = 42,
):
    r"""Per-cell weighted aggregate of signature-gene expression.

    .. math::

        ES = \frac{\sum_i w_i x_i}{\sum_i w_i}\ (\text{wmean})\quad\text{or}\quad ES = \sum_i w_i x_i\ (\text{wsum})

    Reference: `Badia-i-Mompel et al., Bioinformatics Advances (2022) <https://doi.org/10.1093/bioadv/vbac016>`_.

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
        fun: Aggregation: ``'wmean'`` (default), ``'wsum'``, or a callable ``f(w, x) -> ES``.
        times: Permutations for empirical p-values. ``1`` skips permutations and keeps the GPU on-device.
        seed: RNG seed for the permutation block.

    Returns:
        None. Writes ``adata.obsm['score_waggr']`` and ``adata.obsm['padj_waggr']``.

    Examples:
        >>> import omicverse as ov
        >>> ov.es.waggr(adata, signatures=sigs)
    """
    from ._engine import resolve_engine

    eng = resolve_engine(engine, has_torch_kernel=True)
    func = _func_waggr_torch if eng == "gpu" else _func_waggr
    resolved_net = _resolve_net(signatures, net)
    return _run(
        name="waggr",
        func=func,
        adj=True,
        test=True,
        data=data,
        net=resolved_net,
        tmin=tmin,
        raw=raw,
        empty=empty,
        bsize=bsize,
        verbose=verbose,
        fun=fun,
        times=times,
        seed=seed,
    )
