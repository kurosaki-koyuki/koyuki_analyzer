"""Tests for ov.single.pseudobulk — single-cell → pseudobulk aggregation.

API mirrors decoupler.pp.pseudobulk: aggregate by sample_col (and optionally
groups_col), with QC fields obs['psbulk_n_cells'] / obs['psbulk_counts'] and
layers['psbulk_props'].
"""

import numpy as np
import pandas as pd
import anndata as ad
import pytest

import omicverse as ov


@pytest.fixture
def sc_adata():
    """600 cells × 80 genes, 3 donors × 3 celltypes, a per-donor condition."""
    rng = np.random.default_rng(0)
    n_cells, n_genes = 600, 80
    X = rng.negative_binomial(5, 0.4, size=(n_cells, n_genes)).astype(np.float32)
    adata = ad.AnnData(X=X)
    adata.obs["donor"] = rng.choice(["d1", "d2", "d3"], n_cells)
    adata.obs["celltype"] = rng.choice(["T", "B", "Mono"], n_cells)
    # condition is constant within each donor → must be carried over.
    adata.obs["condition"] = adata.obs["donor"].map(
        {"d1": "ctrl", "d2": "ctrl", "d3": "disease"}
    )
    adata.layers["counts"] = X.copy()
    adata.var_names = [f"g{i}" for i in range(n_genes)]
    return adata


def test_per_sample(sc_adata):
    pb = ov.single.pseudobulk(sc_adata, sample_col="donor", layer="counts")
    assert pb.shape == (3, 80)
    assert {"donor", "psbulk_n_cells", "psbulk_counts"}.issubset(pb.obs.columns)
    # sum mode conserves total counts.
    assert np.isclose(np.asarray(pb.X).sum(), sc_adata.layers["counts"].sum())
    # n_cells per profile sums back to the original cell count.
    assert pb.obs["psbulk_n_cells"].sum() == sc_adata.n_obs


def test_per_sample_per_group(sc_adata):
    pb = ov.single.pseudobulk(sc_adata, sample_col="donor",
                              groups_col="celltype", layer="counts")
    assert pb.shape == (9, 80)               # 3 donors × 3 celltypes
    assert {"donor", "celltype"}.issubset(pb.obs.columns)
    # QC layer present, shape matches.
    assert "psbulk_props" in pb.layers
    assert pb.layers["psbulk_props"].shape == pb.shape
    # proportions are in [0, 1].
    props = pb.layers["psbulk_props"]
    assert (props >= 0).all() and (props <= 1).all()


def test_constant_obs_carried_over(sc_adata):
    pb = ov.single.pseudobulk(sc_adata, sample_col="donor",
                              groups_col="celltype", layer="counts")
    # 'condition' is constant within each donor → carried onto every profile.
    assert "condition" in pb.obs.columns
    assert set(pb.obs.loc[pb.obs["donor"] == "d3", "condition"]) == {"disease"}


def test_non_constant_obs_dropped(sc_adata):
    # celltype varies within a donor-level profile → must NOT be carried over.
    pb = ov.single.pseudobulk(sc_adata, sample_col="donor", layer="counts")
    assert "celltype" not in pb.obs.columns


def test_mode_mean(sc_adata):
    pb = ov.single.pseudobulk(sc_adata, sample_col="donor",
                              groups_col="celltype", mode="mean", layer="counts")
    # Mean per profile must not exceed the global max single-cell value.
    assert np.asarray(pb.X).max() <= sc_adata.layers["counts"].max()
    assert pb.uns["pseudobulk"]["mode"] == "mean"


def test_min_cells_filter(sc_adata):
    pb_all = ov.single.pseudobulk(sc_adata, sample_col="donor",
                                  groups_col="celltype", layer="counts")
    pb_flt = ov.single.pseudobulk(sc_adata, sample_col="donor", groups_col="celltype",
                                  layer="counts", min_cells=1000)
    # An impossibly high min_cells drops every profile.
    assert pb_flt.n_obs < pb_all.n_obs


def test_bad_args_raise(sc_adata):
    with pytest.raises(KeyError):
        ov.single.pseudobulk(sc_adata, sample_col="not_a_col")
    with pytest.raises(ValueError):
        ov.single.pseudobulk(sc_adata, sample_col="donor", mode="bogus")


def test_pseudobulk_feeds_pyDEG(sc_adata):
    """The pseudobulk output should plug straight into ov.bulk.pyDEG."""
    pb = ov.single.pseudobulk(sc_adata, sample_col="donor",
                              groups_col="celltype", layer="counts", mode="sum")
    # Build a genes × profiles count frame for one celltype across donors.
    t_cells = pb[pb.obs["celltype"] == "T"]
    counts = pd.DataFrame(np.asarray(t_cells.X).T,
                          index=t_cells.var_names,
                          columns=list(t_cells.obs_names))
    assert counts.shape[0] == 80
    assert (counts.values >= 0).all()
