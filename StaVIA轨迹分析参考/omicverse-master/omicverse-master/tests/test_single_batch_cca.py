"""Tests for the ``methods='cca'`` branch of ``ov.single.batch_correction``.

Gated on ``pyccasc`` availability; skipped when the package isn't
installed so CI that doesn't pull the optional dep stays green.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import anndata as ad

pyccasc = pytest.importorskip("cca_py")


def _toy_adata(n_per_batch=60, n_genes=150, n_batches=3, seed=0):
    """Synthetic AnnData with a planted per-batch mean shift + a shared
    cell-type signal. Downstream CCA integration should pull the
    shared signal up while removing the per-batch mean shift from the
    first component."""
    rng = np.random.default_rng(seed)
    Xs, batches, cell_types = [], [], []
    for bi in range(n_batches):
        X = rng.standard_normal((n_per_batch, n_genes)).astype(np.float64)
        # Per-batch additive offset on the first 20 genes
        X[:, :20] += bi * 3.0
        # Shared cell-type 1 (first half) on genes 20:40
        X[: n_per_batch // 2, 20:40] += 2.5
        # Shared cell-type 2 (second half) on genes 40:60
        X[n_per_batch // 2:, 40:60] += 2.5
        Xs.append(X)
        batches.extend([f"b{bi}"] * n_per_batch)
        cell_types.extend(
            ["A"] * (n_per_batch // 2) + ["B"] * (n_per_batch - n_per_batch // 2)
        )
    X = np.vstack(Xs)
    obs = pd.DataFrame(
        {"batch": batches, "cell_type": cell_types},
        index=[f"s{i}" for i in range(X.shape[0])],
    )
    var = pd.DataFrame(index=[f"g{j}" for j in range(n_genes)])
    return ad.AnnData(X=X, obs=obs, var=var)


class TestBatchCorrectionCCA:
    def test_two_batch_writes_x_cca(self):
        import omicverse as ov

        adata = _toy_adata(n_batches=2)
        ov.single.batch_correction(
            adata, batch_key="batch", methods="cca", n_pcs=10,
        )
        assert "X_cca" in adata.obsm
        assert adata.obsm["X_cca"].shape == (adata.n_obs, 10)

    def test_three_batch_writes_x_cca(self):
        import omicverse as ov

        adata = _toy_adata(n_batches=3)
        ov.single.batch_correction(
            adata, batch_key="batch", methods="cca", n_pcs=12,
        )
        assert adata.obsm["X_cca"].shape == (adata.n_obs, 12)
        meta = adata.uns["cca"]["X_cca"]
        assert meta["n_batches"] == 3
        assert meta["num_cc"] == 12
        assert set(meta["batches"]) == {"b0", "b1", "b2"}

    def test_seurat_cca_alias(self):
        import omicverse as ov

        adata = _toy_adata(n_batches=2)
        ov.single.batch_correction(
            adata, batch_key="batch", methods="seurat_cca", n_pcs=10,
        )
        assert "X_cca" in adata.obsm

    def test_returns_adata_for_chaining(self):
        """batch_correction(methods='cca') must return adata so the
        ``adata = batch_correction(adata, methods='cca')`` pattern
        works — matches scanorama / OOM branches."""
        import omicverse as ov

        adata = _toy_adata(n_batches=2)
        out = ov.single.batch_correction(
            adata, batch_key="batch", methods="cca", n_pcs=6,
        )
        assert out is adata
        assert "X_cca" in out.obsm

    def test_unknown_kwargs_warn_not_raise(self):
        """Unknown kwargs (e.g. typos) should warn and continue rather
        than raising TypeError — matches the loose-kwarg contract of
        the other backends."""
        import warnings
        import omicverse as ov

        adata = _toy_adata(n_batches=2)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ov.single.batch_correction(
                adata, batch_key="batch", methods="cca", n_pcs=6,
                n_layer=2,  # deliberate typo-like extra kwarg
            )
        msgs = [str(w.message) for w in caught]
        assert any("ignored unknown kwargs" in m and "n_layer" in m
                   for m in msgs), msgs
        assert "X_cca" in adata.obsm

    def test_single_batch_raises(self):
        import omicverse as ov

        adata = _toy_adata(n_batches=1)
        with pytest.raises(ValueError, match="requires ≥2 batches"):
            ov.single.batch_correction(
                adata, batch_key="batch", methods="cca", n_pcs=5,
            )

    def test_unknown_reference_raises(self):
        import omicverse as ov

        adata = _toy_adata(n_batches=3)
        with pytest.raises(KeyError, match="reference"):
            ov.single.batch_correction(
                adata, batch_key="batch", methods="cca", n_pcs=5,
                reference="bogus",
            )

    def test_reference_batch_selection(self):
        import omicverse as ov

        adata = _toy_adata(n_batches=3)
        ov.single.batch_correction(
            adata, batch_key="batch", methods="cca", n_pcs=8,
            reference="b1",
        )
        assert adata.obsm["X_cca"].shape == (adata.n_obs, 8)

    def test_integration_brings_same_celltype_closer(self):
        """After CCA, within-celltype distances (cross-batch) should be
        smaller than within-batch cross-celltype distances."""
        from sklearn.metrics import pairwise_distances
        import omicverse as ov

        adata = _toy_adata(n_batches=2, n_per_batch=40)
        ov.single.batch_correction(
            adata, batch_key="batch", methods="cca", n_pcs=10,
        )
        E = adata.obsm["X_cca"]
        D = pairwise_distances(E)
        bt = adata.obs["batch"].to_numpy()
        ct = adata.obs["cell_type"].to_numpy()
        # cross-batch, same celltype
        m_within_ct = (ct[:, None] == ct[None, :]) & (bt[:, None] != bt[None, :])
        np.fill_diagonal(m_within_ct, False)
        d_cross_same_ct = D[m_within_ct].mean()
        # same batch, different celltype
        m_within_bt_diff_ct = (bt[:, None] == bt[None, :]) & (ct[:, None] != ct[None, :])
        d_same_bt_diff_ct = D[m_within_bt_diff_ct].mean()
        assert d_cross_same_ct < d_same_bt_diff_ct, (
            f"CCA failed to integrate: cross-batch same-ct={d_cross_same_ct:.3f}"
            f" vs same-batch diff-ct={d_same_bt_diff_ct:.3f}"
        )
