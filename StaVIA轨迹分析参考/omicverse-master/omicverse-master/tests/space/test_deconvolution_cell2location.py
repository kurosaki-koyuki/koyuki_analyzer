from __future__ import annotations

import sys
import types

import numpy as np
import pandas as pd
from anndata import AnnData


def _synthetic_pair():
    ad_sc = AnnData(X=np.array([[1, 0], [0, 2], [3, 1]], dtype=np.float32))
    ad_sc.var_names = ["g0", "g1"]
    ad_sc.obs["cell_type"] = ["A", "B", "A"]
    ad_sc.layers["counts"] = ad_sc.X.copy()

    ad_sp = AnnData(X=np.array([[2, 1], [1, 3]], dtype=np.float32))
    ad_sp.var_names = ["g0", "g1"]
    ad_sp.obs["sample"] = ["s0", "s0"]
    ad_sp.layers["counts"] = ad_sp.X.copy()
    return ad_sp, ad_sc


def _install_fake_cell2location(monkeypatch, seen: dict):
    fake_root = types.ModuleType("omicverse.external.space.cell2location")
    fake_root.__path__ = []

    fake_models = types.ModuleType("omicverse.external.space.cell2location.models")
    fake_plt = types.ModuleType("omicverse.external.space.cell2location.plt")
    fake_utils = types.ModuleType("omicverse.external.space.cell2location.utils")
    fake_filtering = types.ModuleType("omicverse.external.space.cell2location.utils.filtering")

    factors = ["A", "B"]

    class FakeRegressionModel:
        @classmethod
        def setup_anndata(cls, **kwargs):
            seen["regression_setup"] = kwargs

        def __init__(self, adata):
            seen["regression_init_adata"] = adata

        def train(self, **kwargs):
            seen["regression_train"] = kwargs

        def export_posterior(self, adata, sample_kwargs=None):
            seen["regression_sample_kwargs"] = sample_kwargs
            adata = adata.copy()
            adata.uns["mod"] = {"factor_names": factors}
            for factor in factors:
                adata.var[f"means_per_cluster_mu_fg_{factor}"] = [1.0, 2.0]
            return adata

    class FakeCell2location:
        @classmethod
        def setup_anndata(cls, **kwargs):
            seen["spatial_setup"] = kwargs

        def __init__(self, adata, **kwargs):
            seen["spatial_init_adata"] = adata
            seen["spatial_init_kwargs"] = kwargs

        def train(self, **kwargs):
            seen["spatial_train"] = kwargs

        def export_posterior(self, adata, sample_kwargs=None):
            seen["spatial_sample_kwargs"] = sample_kwargs
            adata = adata.copy()
            adata.uns["mod"] = {"factor_names": factors}
            adata.obsm["q05_cell_abundance_w_sf"] = pd.DataFrame(
                [[2.0, 1.0], [1.0, 3.0]],
                index=adata.obs_names,
                columns=factors,
            )
            return adata

    fake_models.RegressionModel = FakeRegressionModel
    fake_models.Cell2location = FakeCell2location
    fake_plt.plot_spatial = lambda *args, **kwargs: None
    fake_utils.select_slide = lambda *args, **kwargs: None
    fake_filtering.filter_genes = lambda adata, **kwargs: np.ones(adata.n_vars, dtype=bool)

    monkeypatch.setitem(sys.modules, "omicverse.external.space.cell2location", fake_root)
    monkeypatch.setitem(sys.modules, "omicverse.external.space.cell2location.models", fake_models)
    monkeypatch.setitem(sys.modules, "omicverse.external.space.cell2location.plt", fake_plt)
    monkeypatch.setitem(sys.modules, "omicverse.external.space.cell2location.utils", fake_utils)
    monkeypatch.setitem(
        sys.modules,
        "omicverse.external.space.cell2location.utils.filtering",
        fake_filtering,
    )


def test_cell2location_uses_cuda_defaults(monkeypatch):
    import torch
    import omicverse as ov

    seen: dict = {}
    _install_fake_cell2location(monkeypatch, seen)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)

    ad_sp, ad_sc = _synthetic_pair()
    decov = ov.space.Deconvolution(adata_sp=ad_sp, adata_sc=ad_sc)
    decov.deconvolution(
        method="cell2location",
        celltype_key_sc="cell_type",
        batch_key_sp="sample",
        cell2location_scrna_kwargs={"max_epochs": 1, "batch_size": 2, "train_size": 1},
        cell2location_spatial_kwargs={"max_epochs": 2, "batch_size": None, "train_size": 1},
        sample_kwargs={"num_samples": 1, "batch_size": 2},
    )

    assert seen["regression_train"]["accelerator"] == "gpu"
    assert seen["regression_train"]["device"] == 1
    assert seen["spatial_train"]["accelerator"] == "gpu"
    assert seen["spatial_train"]["device"] == 1


def test_cell2location_keeps_explicit_device(monkeypatch):
    import torch
    import omicverse as ov

    seen: dict = {}
    _install_fake_cell2location(monkeypatch, seen)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)

    ad_sp, ad_sc = _synthetic_pair()
    decov = ov.space.Deconvolution(adata_sp=ad_sp, adata_sc=ad_sc)
    decov.deconvolution(
        method="cell2location",
        celltype_key_sc="cell_type",
        cell2location_scrna_kwargs={
            "max_epochs": 1,
            "batch_size": 2,
            "train_size": 1,
            "accelerator": "cpu",
            "device": "auto",
        },
        cell2location_spatial_kwargs={
            "max_epochs": 2,
            "batch_size": None,
            "train_size": 1,
            "accelerator": "cpu",
            "device": "auto",
        },
        sample_kwargs={"num_samples": 1, "batch_size": 2},
    )

    assert seen["regression_train"]["accelerator"] == "cpu"
    assert seen["regression_train"]["device"] == "auto"
    assert seen["spatial_train"]["accelerator"] == "cpu"
    assert seen["spatial_train"]["device"] == "auto"
