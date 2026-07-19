from __future__ import annotations

import warnings
from types import SimpleNamespace

from omicverse.pl import cell_fate, cellrank_macrostates


class _FakeCellRankEstimator:
    def __init__(self):
        self.calls = []

    def plot_macrostates(self, **kwargs):
        self.calls.append(kwargs)
        warnings.warn(
            "No data for colormapping provided via 'c'. Parameters 'cmap' will be ignored",
            UserWarning,
        )
        return "axis"


def test_cell_fate_accepts_estimator_and_suppresses_cmap_warning():
    estimator = _FakeCellRankEstimator()

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        result = cell_fate(estimator, which="terminal", basis="umap")

    assert result == "axis"
    assert estimator.calls == [
        {"which": "terminal", "basis": "umap", "legend_loc": "right", "s": 100}
    ]
    assert not any(
        "No data for colormapping provided via 'c'" in str(warning.message)
        for warning in captured
    )


def test_cell_fate_accepts_fitted_wrapper():
    estimator = _FakeCellRankEstimator()
    wrapper = type("Wrapper", (), {"cellrank_estimator": estimator})()

    result = cell_fate(
        wrapper,
        which="all",
        basis="X_umap",
        legend_loc="none",
        s=20,
    )

    assert result == "axis"
    assert estimator.calls == [
        {"which": "all", "basis": "X_umap", "legend_loc": "none", "s": 20}
    ]


def test_cell_fate_accepts_adata_with_stored_estimator():
    estimator = _FakeCellRankEstimator()
    adata_like = SimpleNamespace(uns={"velocity_cellrank": {"estimator": estimator}})

    result = cell_fate(adata_like, which="terminal")

    assert result == "axis"
    assert estimator.calls == [
        {"which": "terminal", "basis": "umap", "legend_loc": "right", "s": 100}
    ]


def test_cellrank_macrostates_alias_remains_available():
    estimator = _FakeCellRankEstimator()

    result = cellrank_macrostates(estimator, which="terminal")

    assert result == "axis"
    assert estimator.calls == [
        {"which": "terminal", "basis": "umap", "legend_loc": "right", "s": 100}
    ]
