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
    kwargs.setdefault("n_estimators", 10)
    # Init model
    reg = xgboost.XGBRegressor(**kwargs)
    # Fit
    x, y = x.reshape(-1, 1), y.reshape(-1, 1)
    reg = reg.fit(x, y)
    # Get R score
    es = reg.score(x, y)
    # Clip to [0, 1]
    es = np.clip(es, 0, 1)
    return es

def _func_udt(
    mat: np.ndarray,
    adj: np.ndarray,
    verbose: bool = False,
    **kwargs,
) -> tuple[np.ndarray, None]:
    """
    Univariate Decision Tree (UDT) :cite:`decoupler`.

    This approach uses the molecular features from one observation as the population of samples
    and it fits a gradient boosted decision trees model with a single covariate,
    which is the feature weights of a set :math:`F`.
    It uses the implementation provided by ``xgboost`` :cite:`xgboost`.

    The enrichment score :math:`ES` is then calculated as the coefficient of determination :math:`R^2`.

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
        ov.es.udt(adata, net, tmin=3)
    """
    _check_import(xgboost, "xgboost")
    nobs = mat.shape[0]
    nvar, nsrc = adj.shape
    es = np.zeros(shape=(nobs, nsrc))
    for i in tqdm(range(nobs), disable=not verbose):
        obs = mat[i]
        for j in range(adj.shape[1]):
            es[i, j] = _xgbr(x=adj[:, j], y=obs, **kwargs)
    return es, None

def _func_udt_torch(
    mat,
    adj,
    verbose: bool = False,
    n_estimators: int = 10,
    max_depth: int = 6,
    learning_rate: float = 0.3,
    reg_lambda: float = 1.0,
    **_kwargs,
):
    r"""GPU (torch) port of :func:`_func_udt`.

    UDT fits ``nobs × nsrc`` univariate gradient-boosted trees (one per
    cell-signature pair), each on the single feature ``adj[:, j]``. The
    CPU version's double Python loop dominates wall time (≈ 128 k tiny
    xgboost fits on PBMC3k). On GPU we batch across cells per signature
    — for each signature ``j`` we run a single ``gbdt_squared_loss_torch``
    call with ``X = adj[:, j:j+1]`` and ``Y = mat.T`` (all ``nobs``
    targets at once) and read off :math:`R^2` from the final
    predictions.

    Same algorithmic notes as ``_func_mdt_torch`` apply; see the
    GBDT section in ``_engine.py`` for the differences from xgboost.
    """
    import torch
    from ._engine import torch_device, to_gpu_dense, gbdt_squared_loss_torch

    device = torch_device()
    nobs, nvar = mat.shape
    nvar_a, nsrc = adj.shape
    assert nvar == nvar_a, "adj rows must equal mat columns"

    Mat = to_gpu_dense(mat, device, dtype=torch.float32)               # (nobs, nvar)
    Adj = torch.as_tensor(np.asarray(adj), dtype=torch.float32, device=device)  # (nvar, nsrc)
    Y = Mat.t().contiguous()                                            # (nvar, nobs)

    # Per-cell totals — denominator of R² = 1 - SS_res / SS_tot is shared
    # across signatures.
    y_mean = Y.mean(dim=0, keepdim=True)                                # (1, nobs)
    ss_tot = ((Y - y_mean) ** 2).sum(dim=0)                             # (nobs,)
    ss_tot_safe = ss_tot.clamp(min=1e-30)

    es = torch.zeros(nobs, nsrc, dtype=torch.float32, device=device)
    for j in range(nsrc):
        X_j = Adj[:, j:j + 1].contiguous()                              # (nvar, 1)
        res = gbdt_squared_loss_torch(
            X_j, Y,
            n_estimators=n_estimators, max_depth=max_depth,
            learning_rate=learning_rate, reg_lambda=reg_lambda,
            return_importances=False, return_predictions=True,
        )
        pred = res['predictions']                                       # (nvar, nobs)
        ss_res = ((Y - pred) ** 2).sum(dim=0)                           # (nobs,)
        r2 = 1.0 - ss_res / ss_tot_safe
        es[:, j] = r2.clamp(0.0, 1.0)

    return es.cpu().numpy().astype(np.float64), None


_func_udt_torch._accepts_sparse = True


@monitor
@register_function(
    aliases=['udt', 'UDT', 'univariate_decision_tree'],
    category="enrichment",
    description=(
        "Univariate Decision Tree (UDT). Per (cell × signature), fits a univariate GBDT on that signature's weights; ES is the model's R²."
    ),
    prerequisites={"optional_functions": ["preprocess"]},
    requires={"var": ["gene symbols matching signature keys"]},
    produces={"obsm": ["score_udt"]},
    auto_fix="none",
    examples=[
        "ov.es.udt(adata, signatures=sigs)",
        "ov.es.udt(adata, signatures=pathway_dict, engine='gpu', tmin=3)",
    ],
    related=["aucell", "gsea", "gsva", "ora", "ulm", "mlm", "waggr", "zscore", "viper", "mdt"],
)
def udt(
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
    n_estimators: int = 10,
    max_depth: int = 6,
    learning_rate: float = 0.3,
    reg_lambda: float = 1.0,
):
    r"""Per (cell, signature) univariate gradient-boosted-tree R² score.

    .. math::

        ES = R^2 = 1 - \frac{\sum_g (y_g - \hat{y}_g)^2}{\sum_g (y_g - \bar{y})^2}

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
        n_estimators: Number of boosting rounds per univariate fit.
        max_depth: Maximum tree depth.
        learning_rate: Boosting learning rate.
        reg_lambda: L2 regularisation on leaf weights.

    Returns:
        None. Writes ``adata.obsm['score_udt']``.

    Examples:
        >>> import omicverse as ov
        >>> ov.es.udt(adata, signatures=sigs)
    """
    from ._engine import resolve_engine

    eng = resolve_engine(engine, has_torch_kernel=True)
    func = _func_udt_torch if eng == "gpu" else _func_udt
    resolved_net = _resolve_net(signatures, net)
    return _run(
        name="udt",
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
