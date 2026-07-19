"""Regression tests for ``ov.pp.tsne`` (issue #683).

The original bug: ``ov.pp.tsne`` forwarded ``n_components=2`` to
``scanpy.tl.tsne`` which doesn't accept it and raised TypeError on
scanpy ≥ 1.10.

The fix went one step further: the cpu code path was rewritten to
talk directly to ``sklearn.manifold.TSNE`` via a small in-tree wrapper
(``omicverse.pp._tsne_cpu.tsne_cpu``), removing the dependency on
``scanpy.tl.tsne`` altogether. CPU users now get full k-D t-SNE the
same as the torch / RAPIDS backends.

These tests pin:

1. ``ov.pp.tsne(adata, use_rep='X_pca')`` (the literal user repro)
   succeeds on cpu mode and produces a 2-D embedding.
2. ``ov.pp.tsne(adata, n_components=3, ...)`` succeeds on cpu mode
   and produces a 3-D embedding.
3. ``scanpy.tl.tsne`` is not called on the cpu code path — the bug
   would re-appear if a regression accidentally re-introduced it.
4. The ``cpu-gpu-mixed`` (torch) backend still receives
   ``n_components`` so its k-D support survives the refactor.
5. The standalone helper ``omicverse.pp._tsne_cpu.tsne_cpu`` is a
   real function that writes ``adata.obsm['X_tsne']`` /
   ``adata.uns['tsne']`` in the canonical scanpy layout.
"""
from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pytest
from anndata import AnnData


def _make_pca_adata(n: int = 60, n_pcs: int = 10, seed: int = 0) -> AnnData:
    """Minimal AnnData with X_pca already populated."""
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, 12)).astype(np.float32)
    adata = AnnData(X=X)
    adata.obsm["X_pca"] = rng.standard_normal((n, n_pcs)).astype(np.float32)
    return adata


# --------------------------------------------------------------------------- #
# 1. CPU mode no longer goes through scanpy at all
# --------------------------------------------------------------------------- #

def test_cpu_tsne_does_not_call_scanpy() -> None:
    import omicverse as ov
    from omicverse import settings

    adata = _make_pca_adata()

    prev_mode = settings.mode
    settings.mode = "cpu"
    try:
        with patch("scanpy.tl.tsne") as patched_scanpy:
            ov.pp.tsne(adata, use_rep="X_pca")
        assert not patched_scanpy.called, (
            "ov.pp.tsne(cpu mode) must not delegate to scanpy.tl.tsne anymore "
            "(issue #683 follow-up: cpu path goes direct to sklearn)."
        )
    finally:
        settings.mode = prev_mode


# --------------------------------------------------------------------------- #
# 2. CPU mode: 2-D end-to-end smoke (the literal user repro)
# --------------------------------------------------------------------------- #

def test_cpu_tsne_2d_end_to_end() -> None:
    import omicverse as ov
    from omicverse import settings

    adata = _make_pca_adata()

    prev_mode = settings.mode
    settings.mode = "cpu"
    try:
        ov.pp.tsne(adata, use_rep="X_pca")
    finally:
        settings.mode = prev_mode

    assert "X_tsne" in adata.obsm
    assert adata.obsm["X_tsne"].shape == (adata.n_obs, 2)
    # The canonical params dict that downstream plot helpers consult.
    assert "tsne" in adata.uns
    assert "params" in adata.uns["tsne"]


# --------------------------------------------------------------------------- #
# 3. CPU mode: 3-D produces the requested dimensionality
# --------------------------------------------------------------------------- #

def test_cpu_tsne_3d_end_to_end() -> None:
    import omicverse as ov
    from omicverse import settings

    adata = _make_pca_adata()

    prev_mode = settings.mode
    settings.mode = "cpu"
    try:
        ov.pp.tsne(adata, n_components=3, use_rep="X_pca")
    finally:
        settings.mode = prev_mode

    assert adata.obsm["X_tsne"].shape == (adata.n_obs, 3), (
        f"Expected 3-D embedding (n_components=3); got "
        f"{adata.obsm['X_tsne'].shape}"
    )


# --------------------------------------------------------------------------- #
# 4. CPU-GPU-MIXED still routes n_components to the torch backend
# --------------------------------------------------------------------------- #

def test_cpu_gpu_mixed_tsne_does_forward_n_components() -> None:
    import omicverse as ov
    from omicverse import settings

    adata = _make_pca_adata()
    captured: dict = {}

    def fake_torch_tsne(adata, **kw):
        captured["kw"] = kw

    prev_mode = settings.mode
    settings.mode = "cpu-gpu-mixed"
    try:
        with patch("omicverse.pp._tsne.tsne", side_effect=fake_torch_tsne):
            ov.pp.tsne(adata, n_components=3, use_rep="X_pca")
    finally:
        settings.mode = prev_mode

    assert captured["kw"].get("n_components") == 3, (
        "ov.pp.tsne(cpu-gpu-mixed) must forward n_components to the "
        f"torch backend; got: {captured['kw']}"
    )


# --------------------------------------------------------------------------- #
# 5. The in-tree sklearn wrapper itself
# --------------------------------------------------------------------------- #

def test_tsne_cpu_helper_writes_canonical_layout() -> None:
    """``ov.pp._tsne_cpu.tsne_cpu`` must write the canonical scanpy
    storage layout (``obsm['X_tsne']`` + ``uns['tsne']['params']``)."""
    from omicverse.pp._tsne_cpu import tsne_cpu

    adata = _make_pca_adata()
    tsne_cpu(adata, use_rep="X_pca", n_components=2)

    assert "X_tsne" in adata.obsm
    assert adata.obsm["X_tsne"].shape == (adata.n_obs, 2)
    params = adata.uns["tsne"]["params"]
    assert params["n_components"] == 2
    assert params["use_rep"] == "X_pca"


def test_tsne_cpu_helper_supports_3d() -> None:
    from omicverse.pp._tsne_cpu import tsne_cpu

    adata = _make_pca_adata()
    tsne_cpu(adata, use_rep="X_pca", n_components=3)
    assert adata.obsm["X_tsne"].shape == (adata.n_obs, 3)
    assert adata.uns["tsne"]["params"]["n_components"] == 3
