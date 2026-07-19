# Vendored from `decoupler` (https://github.com/scverse/decoupler) by
# omicverse for in-tree GPU acceleration work. Original copyright by
# the decoupler authors, redistributed under decoupler's GPL-3.0
# license. Cross-module imports rewritten from `decoupler.*` to
# `omicverse.es.*` (see scripts/vendor_decoupler.py).

from collections.abc import Callable

import numpy as np
import pandas as pd
import scipy.sparse as sps
from anndata import AnnData
from tqdm.auto import tqdm

from ._datatype import DataType
from ._pv import _fdr_bh_axis1_numba
from ._data import extract
from ._net import adjmat, idxmat, prune

def _return(
    name: str,
    data: DataType,
    es: pd.DataFrame,
    pv: pd.DataFrame,
    verbose: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame] | AnnData | None:
    if isinstance(data, AnnData):
        if data.obs_names.size != es.index.size:
            data = data[es.index, :].copy()
            data.obsm[f"score_{name}"] = es
            if pv is not None:
                data.obsm[f"padj_{name}"] = pv
            return data
        else:
            data.obsm[f"score_{name}"] = es
            if pv is not None:
                data.obsm[f"padj_{name}"] = pv
            return None
    else:
        return es, pv

def _run(
    name: str,
    func: Callable,
    adj: bool,
    test: bool,
    data: DataType,
    net: pd.DataFrame,
    tmin: int | float = 5,
    layer: str | None = None,
    raw: bool = False,
    empty: bool = True,
    bsize: int | float = 250_000,
    verbose: bool = False,
    **kwargs,
) -> tuple[pd.DataFrame, pd.DataFrame] | AnnData | None:
    # Process data
    mat, obs, var = extract(data, layer=layer, raw=raw, empty=empty, shuffle=True, verbose=verbose, bsize=bsize)
    issparse = sps.issparse(mat)
    isbacked = isinstance(mat, tuple)
    # Process net
    net = prune(features=var, net=net, tmin=tmin, verbose=verbose)
    # Handle stat type
    if adj:
        sources, targets, adjm = adjmat(features=var, net=net, verbose=verbose)
        # When the kernel signals it can ingest sparse input itself
        # (set via ``func._accepts_sparse = True`` on the torch kernels),
        # we skip the per-batch ``.toarray()`` and pass the sparse slice
        # straight through. Saves the dominant ~50 ms / call on dense-by-
        # density scRNA-seq matrices; see ``omicverse.es._engine.to_gpu_dense``.
        func_accepts_sparse = bool(getattr(func, '_accepts_sparse', False))
        # Handle batches
        if issparse or isbacked:
            nbatch = int(np.ceil(obs.size / bsize))
            es, pv = [], []
            for i in tqdm(range(nbatch), disable=not verbose):
                if i == 0 and verbose:
                    batch_verbose = True
                else:
                    batch_verbose = False
                srt, end = i * bsize, i * bsize + bsize
                if sps.issparse(mat):
                    sliced = mat[srt:end]
                    bmat = sliced if func_accepts_sparse else sliced.toarray()
                else:
                    bmat, msk_col = mat
                    bmat = bmat[srt:end, :]
                    if sps.issparse(bmat) and not func_accepts_sparse:
                        bmat = bmat.toarray()
                    if not sps.issparse(bmat):
                        bmat = bmat[:, msk_col]
                bes, bpv = func(bmat, adjm, verbose=batch_verbose, **kwargs)
                es.append(bes)
                pv.append(bpv)
            es = np.vstack(es)
            es = pd.DataFrame(es, index=obs, columns=sources)
        else:
            es, pv = func(mat, adjm, verbose=verbose, **kwargs)
            es = pd.DataFrame(es, index=obs, columns=sources)
    else:
        sources, cnct, starts, offsets = idxmat(features=var, net=net, verbose=verbose)
        if isbacked:
            nbatch = int(np.ceil(obs.size / bsize))
            es, pv = [], []
            for i in tqdm(range(nbatch), disable=not verbose):
                if i == 0 and verbose:
                    batch_verbose = True
                else:
                    batch_verbose = False
                srt, end = i * bsize, i * bsize + bsize
                bmat, msk_col = mat
                bmat = bmat[srt:end, msk_col]
                bes, bpv = func(bmat, cnct, starts, offsets, verbose=batch_verbose, **kwargs)
                es.append(bes)
                pv.append(bpv)
            es = np.vstack(es)
        else:
            es, pv = func(mat, cnct, starts, offsets, verbose=verbose, **kwargs)
        es = pd.DataFrame(es, index=obs, columns=sources)
    # Handle pvals and FDR correction
    if test:
        pv = np.vstack(pv)
        pv = pd.DataFrame(pv, index=obs, columns=sources)
        if name != "mlm":
            pv.loc[:, :] = _fdr_bh_axis1_numba(pv.values)
    else:
        pv = None
    return _return(name, data, es, pv, verbose=verbose)
