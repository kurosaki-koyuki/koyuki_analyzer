# Vendored from `decoupler` (https://github.com/scverse/decoupler) by
# omicverse for in-tree GPU acceleration work. Original copyright by
# the decoupler authors, redistributed under decoupler's GPL-3.0
# license. Cross-module imports rewritten from `decoupler.*` to
# `omicverse.es.*` (see scripts/vendor_decoupler.py).

import numba as nb
import numpy as np
import scipy.stats as sts
from tqdm.auto import tqdm

from .._monitor import monitor
from .._registry import register_function

from ._net import _resolve_net
from ._run import _run

@nb.njit(cache=True)
def _get_wts_posidxs(
    wts: np.ndarray,
    idxs: np.ndarray,
    pval1: np.ndarray,
    table: np.ndarray,
    penalty: int,
) -> tuple[np.ndarray, np.ndarray]:
    pos_idxs = np.zeros(idxs.shape[0], dtype=np.int_)
    for j in range(idxs.shape[0]):
        p = pval1[j]
        if p > 0:
            x_idx, y_idx = idxs[j]
        else:
            y_idx, x_idx = idxs[j]
        pos_idxs[j] = x_idx
        x = wts[:, x_idx]
        y = wts[:, y_idx]
        x_msk, y_msk = x != 0, y != 0
        msk = x_msk * y_msk
        x[msk] = x[msk] / (1 + np.abs(p)) ** (penalty / table[x_idx])
        wts[:, x_idx] = x
    return wts, pos_idxs

@nb.njit(cache=True)
def _get_tmp_idxs(
    pval: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    size = int(np.sum(~np.isnan(pval)) / 2)
    tmp = np.zeros((size, 2))
    idxs = np.zeros((size, 2), dtype=np.int_)
    k = 0
    for i in range(pval.shape[0]):
        for j in range(pval.shape[1]):
            if i <= j:
                x = pval[i, j]
                if not np.isnan(x):
                    y = pval[j, i]
                    if not np.isnan(y):
                        tmp[k, 0] = x
                        tmp[k, 1] = y
                        idxs[k, 0] = i
                        idxs[k, 1] = j
                        k += 1
    return tmp, idxs

@nb.njit(cache=True)
def _fill_pval_mat(
    j: int,
    reg: np.ndarray,
    n_targets: int,
    s1: np.ndarray,
    s2: np.ndarray,
) -> np.ndarray:
    n_fsets = reg.shape[1]
    col = np.full(n_fsets, np.nan)
    for k in nb.prange(n_fsets):
        if k != j:
            k_msk = reg[:, k] != 0
            nhits = k_msk.sum()
            if nhits > n_targets:
                sum1: float = np.sum(reg[:, k] * s2)
                ss = np.sign(sum1)
                if ss == 0:
                    ss = 1
                sum2: float = np.sum((1 - np.abs(reg[k_msk, k])) * s1[k_msk])
                ww = np.ones(nhits)
                col[k] = (np.abs(sum1) + sum2 * (sum2 > 0)) / ww.size * ss * np.sqrt(ww.size)
    return col

def _get_inter_pvals(
    nes_i: np.ndarray,
    ss_i: np.ndarray,
    sub_net: np.ndarray,
    n_targets: int,
) -> np.ndarray:
    pval = np.full((sub_net.shape[1], sub_net.shape[1]), np.nan)
    for j in range(sub_net.shape[1]):
        trgt_msk = sub_net[:, j] != 0
        reg = (sub_net[trgt_msk] != 0) * sub_net[trgt_msk, j].reshape(-1, 1)
        s2 = ss_i[trgt_msk]
        s2 = sts.rankdata(s2, method="average") / (s2.shape[0] + 1) * 2 - 1
        s1 = np.abs(s2) * 2 - 1
        s1 = s1 + (1 - np.max(s1)) / 2
        s1 = sts.norm.ppf(s1 / 2 + 0.5)
        tmp = np.sign(nes_i[j])
        if tmp == 0:
            tmp = 1
        s2 = sts.norm.ppf(s2 / 2 + 0.5) * tmp
        pval[j] = _fill_pval_mat(j=j, reg=reg, n_targets=n_targets, s1=s1, s2=s2)
    pval = 1 - sts.norm.cdf(pval)
    return pval

def _shadow_regulon(
    nes_i: np.ndarray,
    ss_i: np.ndarray,
    net: np.ndarray,
    reg_sign: float = 1.96,
    n_targets: int = 10,
    penalty: int | float = 20,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    # Find significant activities
    msk_sign = np.abs(nes_i) > reg_sign
    # Filter by significance
    nes_i = nes_i[msk_sign]
    sub_net = net[:, msk_sign]
    # Init likelihood mat
    wts = np.zeros(sub_net.shape)
    wts[sub_net != 0] = 1.0
    if wts.shape[1] < 2:
        return None
    # Get significant interatcions between regulators
    pval = _get_inter_pvals(nes_i, ss_i, sub_net, n_targets=n_targets)
    # Get pairs of regulators
    tmp, idxs = _get_tmp_idxs(pval)
    if tmp.size == 0:
        return None
    pval1 = np.log10(tmp[:, 1]) - np.log10(tmp[:, 0])
    unique, counts = np.unique(idxs.flatten(), return_counts=True)
    table = np.zeros(int(unique.max()) + 1, dtype=np.int_)
    table[unique.astype(np.int_)] = counts
    # Modify interactions based on sign of pval1
    wts, pos_idxs = _get_wts_posidxs(wts, idxs, pval1, table, penalty)
    # Select only regulators with positive pval1
    pos_idxs = np.unique(pos_idxs)
    sub_net = sub_net[:, pos_idxs]
    wts = wts[:, pos_idxs]
    idxs = np.where(msk_sign)[0][pos_idxs]
    return sub_net, wts, idxs

def _aREA(mat: np.ndarray, net: np.ndarray, wts: None | np.ndarray = None) -> np.ndarray:
    if wts is None:
        wts = np.zeros(net.shape)
        wts[net != 0] = 1
    wts = wts / np.max(wts, axis=0)
    nes = np.sqrt(np.sum(wts**2, axis=0))
    wts = wts / np.sum(wts, axis=0)
    mat = sts.rankdata(mat, method="average", axis=1) / (mat.shape[1] + 1)
    t1 = np.abs(mat - 0.5) * 2
    t1 = t1 + (1 - np.max(t1)) / 2
    msk = np.sum(net != 0, axis=1) >= 1
    t1, mat = t1[:, msk], mat[:, msk]
    net, wts = net[msk], wts[msk]
    t1 = sts.norm.ppf(t1)
    mat = sts.norm.ppf(mat)
    sum1 = mat.dot(wts * net)
    sum2 = t1.dot((1 - np.abs(net)) * wts)
    tmp = (np.abs(sum1) + sum2 * (sum2 > 0)) * np.sign(sum1)
    nes = tmp * nes
    return nes

def _func_viper(
    mat: np.ndarray,
    adj: np.ndarray,
    pleiotropy: bool = True,
    reg_sign: float = 0.05,
    n_targets: int = 10,
    penalty: int | float = 20,
    verbose: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    r"""
    Virtual Inference of Protein-activity by Enriched Regulon analysis (VIPER) :cite:`viper`.

    This approach first ranks features based on their absolute values and computes a one-tail score.

    .. math::

        \begin{align}
        w &= \frac{w}{max(|w|)} \\
        l_{orig} &= 1_{w \neq 0} \\
        l &= \frac{l_{orig}}{\sum_{i=1}^{k} \frac{l_i}{max(l_{orig})}max(l_{orig})} \\
        q^{norm} &= \Phi^{-1}(2|q-0.5| + (1 + max(|q-0.5|))) \\
        S_1 &= \sum_{i=1}^{k}q_i^{norm}l_i(1-|w_i|) \\
        \end{align}

    Where:

    - :math:`w \in [-1, +1]` is a vector of interaction weights across features
    - :math:`l \in [0, 1]` is a vector of interaction likelihoods across features
    - :math:`q \in [0, 1]` is a vector of quantiles based on the molecular readouts across features
    - :math:`k` is the number of features in :math:`q`
    - :math:`\Phi^{-1}` is is the inverse of the cumulative distribution function of the standard normal distribution
    - :math:`q^{norm} \in [-\infty,+\infty]` are the z-scores of the deviation of quantiles from 0.5

    :math:`S_1` encodes for the magnitude of the enrichment score, irrespective of the interaction signs in ``net``.

    Then, :math:`q` are z-transformed and weighted by their interaction strength and likelihood.

    .. math::

        S_2 = \sum_{i=1}^{k}w_il_i(\Phi^{-1}(q_i))

    In this case, :math:`S_2` takes the direction (sign) of interactions into consideration.

    Afterwards, a summary score :math:`S_3` is obtained.

    .. math::

        S_3 =
        \begin{cases}
        (|S_2| + S_1)  \times \mathrm{sgn}(S_2) & \text{if } S_1 > 0 \\
        S_2 & \text{if } S_1 < 0
        \end{cases}

    An enrichment score :math:`ES` is obtained by comparing :math:`S_3` to a
    null model generated through an analytical approach that shuffles features.

    .. math::

        ES = S_3\sqrt{\sum_{i=1}^{k}l_{orig,i}^{2}}

    Together with a :math:`p_{value}`

    .. math::

        p_{value} = \Phi(ES)

    Additionaly, computing multiple sources simultaneously, a pleiotropic correction is employed.

    In brief, all possible pairs of sources AB are generated under two conditions:

    1. both A and B are significantly enriched (p < ``reg_sign=0.05``)
    2. they share at least ``n_targets=10`` features

    Subsequently, a :math:`ES` and its associated :math:`p_{value}` is computed for
    both A (:math:`pA`) and B (:math:`pB`) based only on the shared features.
    Then the pleiotropy score (:math:`PS`) is computed.

    .. math::

        PS =
        \begin{cases}
        \frac{1}{(1+|\log_{10}(pB) - \log_{10}(pA)|)^{\frac{20}{n_a}}} \text{ if } pA < pB \\
        \frac{1}{(1+|\log_{10}(pA) - \log_{10}(pB)|)^{\frac{20}{n_b}}} \text{ if } pA > pB
        \end{cases}

    Where:

    - :math:`n_a` is the number of test pairs involving the source A
    - :math:`n_b` is the number of test pairs involving the source B

    This score is used to update :math:`l_{orig}`.

    .. math::

        l_{orig, i} =
        \begin{cases}
        PS \times 1_{\{i \in A\}} \text{ if } pA < pB \\
        PS \times 1_{\{i \in B\}} \text{ if } pA > pB
        \end{cases}

    A new :math:`ES` and :math:`p_{value}` are calculated following all
    the previous steps but using the updated :math:`l_{orig}`

    Parameters
    ----------

    pleiotropy
        Whether correction for pleiotropic regulation should be performed.
    reg_sign
        If ``pleiotropy``, p-value threshold for considering significant regulators.
    n_targets
        If ``pleiotropy``, integer indicating the minimal number of overlaping targets to consider for analysis.
    penalty
        If ``pleiotropy``, number higher than 1 indicating the penalty for the pleiotropic interactions. 1 = no penalty.

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
        ov.es.viper(adata, net, tmin=3)
    """
    # Get number of batches
    n_samples = mat.shape[0]
    n_features, n_fsets = adj.shape
    # Compute score
    nes = _aREA(mat, adj)
    if pleiotropy:
        reg_sign = sts.norm.ppf(1 - (reg_sign / 2))
        for i in tqdm(range(nes.shape[0]), disable=not verbose):
            # Extract per sample
            ss_i = mat[i]
            nes_i = nes[i]
            # Shadow regulons
            shadow = _shadow_regulon(nes_i, ss_i, adj, reg_sign=reg_sign, n_targets=n_targets, penalty=penalty)
            if shadow is None:
                continue
            else:
                sub_net, wts, idxs = shadow
            # Recompute activity with shadow regulons and update nes
            tmp = _aREA(ss_i.reshape(1, -1), sub_net, wts=wts)[0]
            nes[i, idxs] = tmp
    # Get pvalues
    pvals = 2 * sts.norm.sf(np.abs(nes))
    return nes, pvals

def _aREA_torch(Mat, Net, Wts=None):
    r"""Analytical Rank-based Enrichment Analysis on torch tensors.

    Vectorised across all observations. Mirrors :func:`_aREA`:

    1. Per-observation rank → quantile :math:`q = r / (G+1)`.
    2. :math:`t_1 = |q - 0.5| \cdot 2 + (1 - \max t_1)/2`.
    3. ``norm.ppf`` on :math:`t_1` and :math:`q` via ``erfinv``.
    4. Two matmuls (sign + magnitude paths) + ``S_1 / S_2`` combine.
    5. Multiply by per-regulon ``nes`` factor.

    The CPU kernel guards a per-column ``msk`` (drop features with no
    network membership) before the matmul. We keep the full feature
    matrix on GPU and zero out the masked columns of ``Net`` / ``Wts``
    — same matmul result, no fancy index slicing.
    """
    import torch
    device = Mat.device
    dtype = Mat.dtype
    nobs, nvar = Mat.shape
    _, nsrc = Net.shape

    if Wts is None:
        Wts = (Net != 0).to(dtype)

    # Normalise weights per regulon (column).
    wts_max = Wts.abs().amax(dim=0, keepdim=True).clamp(min=1e-30)
    Wts = Wts / wts_max
    nes_factor = torch.sqrt((Wts * Wts).sum(dim=0))                    # (nsrc,)
    wts_sum = Wts.sum(dim=0, keepdim=True).clamp(min=1e-30)
    Wts = Wts / wts_sum

    # Rank per row (cell), average ties → quantile q in (0, 1).
    # torch has no built-in average-rank, but `argsort(stable)` + average
    # over tied groups is straightforward. For sparse expression the
    # number of distinct values is small; this matches sts.rankdata(method='average').
    rank = _avg_rank_per_row(Mat)
    q = rank / (nvar + 1.0)
    t1 = (q - 0.5).abs() * 2.0
    t1 = t1 + (1.0 - t1.amax()) / 2.0

    # Mask features absent from network.
    msk = (Net != 0).any(dim=1)                                        # (nvar,)
    if not msk.all():
        keep = msk.to(dtype).unsqueeze(0)                              # (1, nvar)
        Net = Net * keep.t()
        Wts = Wts * keep.t()
        # t1/q masked features contribute 0 after the matmul because the
        # corresponding rows of Net/Wts are zero — no need to slice.

    # ppf via erfinv: Φ⁻¹(p) = √2 · erfinv(2p − 1).
    t1_z = _norm_ppf_torch(t1.clamp(min=1e-12, max=1.0 - 1e-12))
    q_z = _norm_ppf_torch(q.clamp(min=1e-12, max=1.0 - 1e-12))

    # Matmuls: shapes (nobs, nvar) @ (nvar, nsrc) → (nobs, nsrc).
    weighted_net = Wts * Net                                            # (nvar, nsrc)
    mag = (1.0 - Net.abs()) * Wts                                       # (nvar, nsrc)
    sum1 = q_z @ weighted_net
    sum2 = t1_z @ mag

    tmp = (sum1.abs() + sum2 * (sum2 > 0)) * torch.sign(sum1)
    nes = tmp * nes_factor.unsqueeze(0)
    return nes

def _avg_rank_per_row(X):
    """Per-row average-rank, matching ``scipy.stats.rankdata(method='average', axis=1)``.

    Stable argsort gives the assigned position of each entry; for runs
    of tied values the average of their positions becomes their rank.
    Implemented with a cumulative-position trick: sort positions per
    row, identify tie groups, replace each tied element's rank with the
    mean rank within its group.
    """
    import torch
    nobs, nvar = X.shape
    device = X.device
    order = torch.argsort(X, dim=1, stable=True)                       # (nobs, nvar)
    pos = torch.arange(1, nvar + 1, device=device, dtype=X.dtype).unsqueeze(0).expand(nobs, -1)
    rank = torch.empty_like(X)
    rank.scatter_(1, order, pos)                                        # (nobs, nvar)

    sorted_X = torch.gather(X, 1, order)                                # (nobs, nvar)
    # Tied groups: identify run boundaries
    boundary = torch.ones_like(sorted_X, dtype=torch.bool)
    boundary[:, 1:] = sorted_X[:, 1:] != sorted_X[:, :-1]
    group_id = boundary.to(torch.long).cumsum(dim=1) - 1                # (nobs, nvar)

    # Average rank within group: sum(rank in group) / count(group)
    n_groups_max = nvar
    sum_rank = torch.zeros(nobs, n_groups_max, device=device, dtype=X.dtype)
    count = torch.zeros(nobs, n_groups_max, device=device, dtype=X.dtype)
    sum_rank.scatter_add_(1, group_id, pos)
    count.scatter_add_(1, group_id, torch.ones_like(pos))
    avg_rank_per_group = sum_rank / count.clamp(min=1)

    # Gather per-element average rank, then scatter to original positions
    sorted_avg = torch.gather(avg_rank_per_group, 1, group_id)          # (nobs, nvar) — sorted order
    out = torch.empty_like(X)
    out.scatter_(1, order, sorted_avg)
    return out

def _norm_ppf_torch(p):
    """Φ⁻¹(p) = √2 · erfinv(2p − 1)."""
    import torch
    return torch.special.erfinv(2.0 * p - 1.0) * (2.0 ** 0.5)

def _func_viper_torch(
    mat,
    adj,
    pleiotropy: bool = True,
    reg_sign: float = 0.05,
    n_targets: int = 10,
    penalty: int | float = 20,
    verbose: bool = False,
):
    r"""GPU port of :func:`_func_viper`.

    Initial ``_aREA`` (the dominant matmul + rank + norm-ppf stage)
    runs on torch via :func:`_aREA_torch`. When ``pleiotropy=True``,
    the per-cell shadow-regulon refinement falls back to the numba CPU
    path — that loop has cell-dependent sub-network shapes and isn't a
    good GPU target, but the post-stage runs against the GPU-computed
    ``nes`` so we still pay the matmul on the GPU.

    Final ``pvals`` use ``erfc`` (``2 * Φ̄(|nes|)``) so the survival
    function never round-trips through scipy.
    """
    import torch
    import scipy.stats as _sts
    from ._engine import torch_device, to_gpu_dense

    device = torch_device()
    Mat = to_gpu_dense(mat, device, dtype=torch.float32)
    Adj = torch.as_tensor(np.asarray(adj), dtype=torch.float32, device=device)

    nes_t = _aREA_torch(Mat, Adj)                                       # (nobs, nsrc) fp32
    nes = nes_t.cpu().numpy().astype(np.float64)

    if pleiotropy:
        # Refine on CPU. The per-cell pleiotropy loop produces variable-
        # size sub-networks; vectorising it would be a separate project.
        # The CPU path here is fast (~1 s on PBMC3k) because it skips
        # cells with <2 significant regulators.
        adj_np = np.asarray(adj)
        mat_np = mat.toarray() if hasattr(mat, 'toarray') else np.asarray(mat)
        rsg = _sts.norm.ppf(1.0 - (reg_sign / 2.0))
        for i in range(nes.shape[0]):
            ss_i = mat_np[i]
            nes_i = nes[i]
            shadow = _shadow_regulon(
                nes_i, ss_i, adj_np,
                reg_sign=rsg, n_targets=n_targets, penalty=penalty,
            )
            if shadow is None:
                continue
            sub_net, wts, idxs = shadow
            tmp = _aREA(ss_i.reshape(1, -1), sub_net, wts=wts)[0]
            nes[i, idxs] = tmp

    # p-values via torch erfc — 2 * Φ̄(|nes|) = erfc(|nes| / √2).
    nes_t_final = torch.as_tensor(nes, device=device)
    pvals_t = torch.special.erfc(nes_t_final.abs() / (2.0 ** 0.5))
    pvals = pvals_t.cpu().numpy()
    return nes, pvals


_func_viper_torch._accepts_sparse = True


@monitor
@register_function(
    aliases=['viper', 'VIPER', 'aREA', 'regulon_activity'],
    category="enrichment",
    description=(
        "Virtual Inference of Protein-activity by Enriched Regulon analysis (VIPER). Analytical rank-based enrichment (aREA) with optional pleiotropy correction."
    ),
    prerequisites={"optional_functions": ["preprocess"]},
    requires={"var": ["gene symbols matching signature keys"]},
    produces={"obsm": ["score_viper", "padj_viper"]},
    auto_fix="none",
    examples=[
        "ov.es.viper(adata, signatures=sigs)",
        "ov.es.viper(adata, signatures=pathway_dict, engine='gpu', tmin=3)",
    ],
    related=["aucell", "gsea", "gsva", "ora", "ulm", "mlm", "waggr", "zscore", "mdt", "udt"],
)
def viper(
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
    pleiotropy: bool = True,
    reg_sign: float = 0.05,
    n_targets: int = 10,
    penalty: int | float = 20,
):
    r"""Per-cell regulon activity via the aREA score with pleiotropy correction.

    .. math::

        ES = S_3 \sqrt{\sum_i l_i^2},\quad S_3 = (|S_2| + S_1)\,\mathrm{sgn}(S_2)\text{ if } S_1 > 0\text{ else }S_2

    Reference: `Alvarez et al., Nat Genet (2016) <https://doi.org/10.1038/ng.3593>`_.

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
        pleiotropy: Apply the pairwise pleiotropy correction (down-weights overlapping regulators).
        reg_sign: P-value threshold for considering a regulator 'significant' before pleiotropy correction.
        n_targets: Minimum number of shared targets required for a pairwise pleiotropy comparison.
        penalty: Pleiotropy penalty exponent (higher = harsher down-weight).

    Returns:
        None. Writes ``adata.obsm['score_viper']`` and ``adata.obsm['padj_viper']``.

    Examples:
        >>> import omicverse as ov
        >>> ov.es.viper(adata, signatures=sigs)
    """
    from ._engine import resolve_engine

    eng = resolve_engine(engine, has_torch_kernel=True)
    func = _func_viper_torch if eng == "gpu" else _func_viper
    resolved_net = _resolve_net(signatures, net)
    return _run(
        name="viper",
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
        pleiotropy=pleiotropy,
        reg_sign=reg_sign,
        n_targets=n_targets,
        penalty=penalty,
    )
