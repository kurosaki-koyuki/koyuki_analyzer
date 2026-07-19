# Vendored from `decoupler` (https://github.com/scverse/decoupler) by
# omicverse for in-tree GPU acceleration work. Original copyright by
# the decoupler authors, redistributed under decoupler's GPL-3.0
# license. Cross-module imports rewritten from `decoupler.*` to
# `omicverse.es.*` (see scripts/vendor_decoupler.py).

import numpy as np
from tqdm.auto import tqdm

from .._monitor import monitor
from .._registry import register_function

from ._net import _resolve_net
from ._run import _run
from ._odeps import _check_import, xgboost

def _xgbr(
    x: np.ndarray,
    y: np.ndarray,
    **kwargs,
) -> np.ndarray:
    # Init model
    reg = xgboost.XGBRegressor(**kwargs)
    # Fit
    y = y.reshape(-1, 1)
    reg = reg.fit(x, y)
    # Get R score
    es = reg.feature_importances_
    return es

def _func_mdt(
    mat: np.ndarray,
    adj: np.ndarray,
    verbose: bool = False,
    **kwargs,
) -> tuple[np.ndarray, None]:
    r"""
    Multivariate Decision Trees (MDT) :cite:`decoupler`.

    This approach uses the molecular features from one observation as the population of samples
    and it fits a gradient boosted decision trees model with multiple covariates,
    which are the weights of all feature sets :math:`F`. It uses the implementation provided by ``xgboost`` :cite:`xgboost`.

    The enrichment score :math:`ES` for each :math:`F` is then calculated as the importance of each covariate in the model.

    Parameters
    ----------

    kwargs
        All other keyword arguments are passed to ``xgboost.XGBRegressor``.
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
        ov.es.mdt(adata, net, tmin=3)
    """
    _check_import(xgboost, "xgboost")
    nobs = mat.shape[0]
    nvar, nsrc = adj.shape
    es = np.zeros(shape=(nobs, nsrc))
    for i in tqdm(range(nobs), disable=not verbose):
        obs = mat[i]
        es[i, :] = _xgbr(x=adj, y=obs, **kwargs)
    return (es, None)

def _func_mdt_torch(
    mat,
    adj,
    verbose: bool = False,
    n_estimators: int = 100,
    max_depth: int = 6,
    learning_rate: float = 0.3,
    reg_lambda: float = 1.0,
    **_kwargs,
):
    r"""GPU (torch) port of :func:`_func_mdt`.

    Replaces the per-cell ``xgboost.XGBRegressor`` fit with a fully
    batched pure-torch GBDT (see ``gbdt_squared_loss_torch`` in
    ``_engine.py``). All ``nobs`` regressions share the same feature
    matrix ``adj``, so they can be fit in parallel — one ``B``-axis
    sweep over the boosting loop instead of ``nobs`` sequential xgboost
    fits.

    Algorithmic fidelity matches XGBoost on default squared-loss
    parameters; numerical agreement is approximate (importance Pearson
    r ≈ 0.99 mean, prediction r ≈ 0.998 mean against xgboost). See the
    ``# Pure-torch gradient boosted decision trees`` section in
    ``_engine.py`` for the precise list of differences.
    """
    import torch
    from ._engine import torch_device, to_gpu_dense, gbdt_squared_loss_torch

    device = torch_device()
    nobs, nvar = mat.shape
    nvar_a, nsrc = adj.shape
    assert nvar == nvar_a, "adj rows must equal mat columns"

    Mat = to_gpu_dense(mat, device, dtype=torch.float32)               # (nobs, nvar)
    Adj = torch.as_tensor(np.asarray(adj), dtype=torch.float32, device=device)  # (nvar, nsrc)
    # Per-cell regression: X = adj, Y[:, c] = mat[c, :]
    Y = Mat.t().contiguous()                                            # (nvar, nobs)

    res = gbdt_squared_loss_torch(
        Adj, Y,
        n_estimators=n_estimators, max_depth=max_depth,
        learning_rate=learning_rate, reg_lambda=reg_lambda,
        return_importances=True, return_predictions=False,
    )
    importances = res['importances']                                    # (nsrc, nobs)
    es = importances.t().cpu().numpy().astype(np.float64)               # (nobs, nsrc)
    return es, None


_func_mdt_torch._accepts_sparse = True


@monitor
@register_function(
    aliases=['mdt', 'MDT', 'multivariate_decision_tree'],
    category="enrichment",
    description=(
        "Multivariate Decision Tree (MDT). Per-cell gradient-boosted tree fit with all signatures as covariates; ES is the normalised feature-importance gain."
    ),
    prerequisites={"optional_functions": ["preprocess"]},
    requires={"var": ["gene symbols matching signature keys"]},
    produces={"obsm": ["score_mdt"]},
    auto_fix="none",
    examples=[
        "ov.es.mdt(adata, signatures=sigs)",
        "ov.es.mdt(adata, signatures=pathway_dict, engine='gpu', tmin=3)",
    ],
    related=["aucell", "gsea", "gsva", "ora", "ulm", "mlm", "waggr", "zscore", "viper", "udt"],
)
def mdt(
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
    n_estimators: int = 100,
    max_depth: int = 6,
    learning_rate: float = 0.3,
    reg_lambda: float = 1.0,
):
    r"""Per-cell gradient-boosted-tree feature importance per signature.

    .. math::

        ES_j = \frac{\sum_{\text{splits on } j} g_s}{\sum_{j'} \sum_{\text{splits on } j'} g_s}

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
        n_estimators: Number of boosting rounds (CPU XGBoost / torch GBDT).
        max_depth: Maximum tree depth.
        learning_rate: Boosting learning rate (a.k.a. eta).
        reg_lambda: L2 regularisation on leaf weights.

    Returns:
        None. Writes ``adata.obsm['score_mdt']``.

    Examples:
        >>> import omicverse as ov
        >>> ov.es.mdt(adata, signatures=sigs)
    """
    from ._engine import resolve_engine

    eng = resolve_engine(engine, has_torch_kernel=True)
    func = _func_mdt_torch if eng == "gpu" else _func_mdt
    resolved_net = _resolve_net(signatures, net)
    return _run(
        name="mdt",
        func=func,
        adj=True,
        test=False,
        data=data,
        net=resolved_net,
        tmin=tmin,
        raw=raw,
        empty=empty,
        bsize=bsize,
        verbose=verbose,
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        reg_lambda=reg_lambda,
    )
