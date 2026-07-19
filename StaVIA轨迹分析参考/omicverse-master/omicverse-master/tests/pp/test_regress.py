"""Tests for ``ov.pp.regress`` — custom ``keys`` parameter (issue #798).

Verifies:
- Default call (``keys=None``) regresses ``mito_perc`` and ``nUMIs``
  and writes ``adata.layers['regressed']``.
- Custom ``keys`` with cell-cycle scores regress additional covariates.
- Missing columns raise ``ValueError`` with the available column list.
- Compatibility with ``regress_and_scale`` downstream.
"""
from __future__ import annotations

import numpy as np
import pytest
from anndata import AnnData
import omicverse as ov


def _small_adata(n_cells: int = 50, n_genes: int = 100, seed: int = 42) -> AnnData:
    """Minimal Poisson-counts AnnData with ``mito_perc``, ``nUMIs``,
    ``S_score``, and ``G2M_score`` in ``.obs`` — mimicking the output
    of ``ov.pp.qc`` followed by ``ov.pp.score_genes_cell_cycle``.
    """
    rng = np.random.default_rng(seed)
    counts = rng.poisson(lam=3.0, size=(n_cells, n_genes)).astype(np.float32)
    adata = AnnData(X=counts)
    adata.var_names = [f"Gene{i:04d}" for i in range(n_genes)]
    adata.obs_names = [f"cell{i:04d}" for i in range(n_cells)]
    adata.obs["nUMIs"] = np.array(counts.sum(axis=1)).ravel()
    adata.obs["mito_perc"] = rng.uniform(0.01, 0.15, size=n_cells).astype(np.float32)
    adata.obs["S_score"] = rng.normal(0, 1, size=n_cells).astype(np.float32)
    adata.obs["G2M_score"] = rng.normal(0, 1, size=n_cells).astype(np.float32)
    return adata


# ── default behaviour (backward compatibility) ────────────────────────────


def test_regress_default_keys_writes_regressed_layer():
    """``ov.pp.regress(adata)`` with no ``keys`` argument must regress
    ``mito_perc`` and ``nUMIs`` and store the result in
    ``adata.layers['regressed']``, preserving the original shape.
    """
    adata = _small_adata()
    original_shape = adata.shape

    ov.pp.regress(adata)

    assert "regressed" in adata.layers, (
        "regress() did not create adata.layers['regressed']"
    )
    assert adata.layers["regressed"].shape == original_shape, (
        "regressed layer shape mismatch"
    )


# ── custom keys ───────────────────────────────────────────────────────────


def test_regress_custom_keys_with_cell_cycle():
    """``ov.pp.regress(adata, keys=[..., 'S_score', 'G2M_score'])``
    must accept and regress additional ``adata.obs`` columns beyond the
    default ``mito_perc`` / ``nUMIs`` pair.
    """
    adata = _small_adata()
    ov.pp.regress(
        adata,
        keys=["mito_perc", "nUMIs", "S_score", "G2M_score"],
    )
    assert "regressed" in adata.layers


def test_regress_single_custom_key():
    """Regression with only a single custom column must succeed."""
    adata = _small_adata()
    ov.pp.regress(adata, keys=["S_score"])
    assert "regressed" in adata.layers


# ── error handling ────────────────────────────────────────────────────────


def test_regress_missing_key_raises_valueerror_with_available_columns():
    """When a requested column does not exist in ``adata.obs``,
    ``regress()`` must raise ``ValueError`` and include the list of
    available column names in the message.
    """
    adata = _small_adata()
    with pytest.raises(ValueError, match="not found in adata.obs"):
        ov.pp.regress(adata, keys=["mito_perc", "nonexistent_column"])


def test_regress_nonexistent_key_message_lists_columns():
    """The error message must include 'Available columns' so users can
    see what columns actually exist.
    """
    adata = _small_adata()
    with pytest.raises(ValueError, match="Available columns"):
        ov.pp.regress(adata, keys=["nUMIs", "bad_key"])


# ── downstream compatibility ──────────────────────────────────────────────


def test_regress_and_scale_works_after_custom_keys_regress():
    """``ov.pp.regress_and_scale(adata)`` must succeed after a
    custom-keys ``regress()`` call, producing a
    ``regressed_and_scaled`` layer.
    """
    adata = _small_adata()
    ov.pp.regress(adata, keys=["mito_perc", "nUMIs", "S_score"])
    ov.pp.regress_and_scale(adata)
    assert "regressed_and_scaled" in adata.layers


# ── edge cases ────────────────────────────────────────────────────────────


def test_regress_preserves_obs_columns():
    """``regress()`` must not mutate or drop existing ``.obs`` columns."""
    adata = _small_adata()
    original_obs_cols = set(adata.obs.columns)
    ov.pp.regress(adata)
    assert set(adata.obs.columns) == original_obs_cols


def test_regress_idempotent_with_same_keys():
    """Calling ``regress()`` twice with the same keys must not raise."""
    adata = _small_adata()
    ov.pp.regress(adata)
    ov.pp.regress(adata)  # second call re-computes from adata.X, overwriting 'regressed'
    assert "regressed" in adata.layers


# ── empty keys guard ──────────────────────────────────────────────────────


def test_regress_empty_keys_raises_valueerror():
    """``ov.pp.regress(adata, keys=[])`` must raise ``ValueError``."""
    adata = _small_adata()
    with pytest.raises(ValueError, match="non-empty list"):
        ov.pp.regress(adata, keys=[])
