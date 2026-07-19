"""Smoke tests for ov.pl.plot1cell (circular UMAP + metadata tracks)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from anndata import AnnData

from omicverse.pl._plot1cell import (
    _run_length,
    _transform_coordinates,
    plot1cell,
)


def _make_adata(n_clusters=4, cells_per=50, seed=0):
    rng = np.random.default_rng(seed)
    n = n_clusters * cells_per
    cluster_ids = np.repeat([f"cl{i+1}" for i in range(n_clusters)], cells_per)
    angles = np.linspace(0, 2 * np.pi, n_clusters + 1)[:-1]
    centers = np.column_stack([np.cos(angles), np.sin(angles)]) * 4
    umap = np.vstack([
        centers[int(c[2:]) - 1] + rng.normal(0, 0.6, size=2)
        for c in cluster_ids
    ])
    obs = pd.DataFrame({
        "cluster": pd.Categorical(
            cluster_ids, categories=[f"cl{i+1}" for i in range(n_clusters)]
        ),
        "sample": pd.Categorical(rng.choice(list("AB"), size=n)),
    })
    adata = AnnData(
        X=rng.poisson(1, size=(n, 10)).astype(float),
        obs=obs,
    )
    adata.obs_names = [f"c{i}" for i in range(n)]
    adata.obsm["X_umap"] = umap
    return adata


# -------------------- helper-level tests ----------------------------
def test_transform_coordinates_fills_range():
    v = np.array([1.0, 5.0, 9.0])
    out = _transform_coordinates(v, zoom=0.8)
    assert np.isclose(out.min(), -0.8)
    assert np.isclose(out.max(), 0.8)


def test_transform_coordinates_zero_range():
    v = np.array([3.0, 3.0, 3.0])
    # All-same input should not divide by zero
    out = _transform_coordinates(v, zoom=0.5)
    assert np.all(out == 0.0)


def test_run_length_detects_segments():
    vals = np.array(["A", "A", "B", "B", "B", "A"])
    starts, lengths, values = _run_length(vals)
    assert starts.tolist() == [0, 2, 5]
    assert lengths.tolist() == [2, 3, 1]
    assert values.tolist() == ["A", "B", "A"]


# -------------------- top-level API tests ---------------------------
def test_plot1cell_returns_axes():
    adata = _make_adata()
    ax = plot1cell(adata, clusters="cluster", basis="X_umap", show=False)
    assert ax is not None
    plt.close(ax.figure)


def test_plot1cell_with_tracks():
    adata = _make_adata()
    ax = plot1cell(
        adata, clusters="cluster", basis="X_umap",
        tracks=["sample"], show=False,
    )
    # Expect cluster ring (4 wedges) + sample ring (>=4 wedges, one per run)
    wedges = [p for p in ax.patches if type(p).__name__ == "Wedge"]
    assert len(wedges) >= 4 + 4  # at least one sample-run per cluster
    plt.close(ax.figure)


def test_plot1cell_return_data():
    adata = _make_adata()
    ax, df = plot1cell(
        adata, clusters="cluster", basis="X_umap",
        tracks=["sample"], show=False, return_data=True,
    )
    assert {"cluster", "x", "y", "x_polar", "sample"} <= set(df.columns)
    assert df.shape[0] == adata.n_obs
    plt.close(ax.figure)


def test_plot1cell_missing_basis_raises():
    adata = _make_adata()
    with pytest.raises(KeyError):
        plot1cell(adata, clusters="cluster", basis="X_tsne", show=False)


def test_plot1cell_missing_track_raises():
    adata = _make_adata()
    with pytest.raises(KeyError):
        plot1cell(
            adata, clusters="cluster", basis="X_umap",
            tracks=["does_not_exist"], show=False,
        )


def test_plot1cell_rejects_oversized_gaps():
    adata = _make_adata(n_clusters=2)
    with pytest.raises(ValueError, match="gaps"):
        plot1cell(
            adata, clusters="cluster", basis="X_umap",
            gap_between_deg=200, gap_start_deg=200, show=False,
        )
