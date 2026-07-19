import sys
import types

import numpy as np
from anndata import AnnData
from scipy import sparse

# The helpers under test do not call scVelo, which is an optional CI dependency.
_stubbed_scvelo = 'scvelo' not in sys.modules
if _stubbed_scvelo:
    sys.modules['scvelo'] = types.ModuleType('scvelo')
try:
    from omicverse.external.latentvelo.utils import (
        _normalize_layer_by_size_factor,
        _select_hvgs_from_log1p,
    )
finally:
    if _stubbed_scvelo:
        sys.modules.pop('scvelo', None)


def _counts():
    return sparse.csr_matrix(np.random.default_rng(864).poisson(2, size=(80, 120)))


def test_latentvelo_hvg_selection_preserves_input_and_subsets():
    counts = _counts()
    adata = AnnData(X=counts.copy())
    _select_hvgs_from_log1p(adata, n_top_genes=30)

    assert (adata.X != counts).nnz == 0
    assert 'highly_variable' in adata.var
    expected_n_vars = int(adata.var['highly_variable'].sum())

    subset_adata = AnnData(X=counts.copy())
    _select_hvgs_from_log1p(subset_adata, n_top_genes=30, subset=True)

    assert subset_adata.n_vars == expected_n_vars
    assert subset_adata.var['highly_variable'].all()


def test_latentvelo_sparse_size_normalization_stays_csr():
    counts = _counts()
    normalized = _normalize_layer_by_size_factor(counts, counts.sum(axis=1))

    assert sparse.isspmatrix_csr(normalized)
    np.testing.assert_allclose(normalized.sum(axis=1).A1, 1.0)
