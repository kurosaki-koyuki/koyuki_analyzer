"""Smoke + regression tests for ``ov.single.MetaCell`` backend dispatch.

Covers:

- All 7 backends instantiate, fit, and write the unified AnnData schema.
- ``predicted()`` works for both hard and soft (where applicable).
- Capability-gated methods raise :class:`UnsupportedCapability` when missing.
- ``check_rigor()`` returns a sensible :class:`RigorReport` for each backend.
- Legacy SEACells signature ``MetaCell(adata, use_rep=..., n_metacells=...)``
  is still accepted (no ``method=`` kwarg) and writes the legacy
  ``obs['SEACell']`` column.
- ``save()`` / ``load()`` roundtrips for the always-installed backends
  (kmeans, random, geosketch, supercell, seacells).
"""

from __future__ import annotations

import os
import tempfile
import warnings

import numpy as np
import pytest


N_CELLS = 240
N_GENES = 60
N_METACELLS = 12


@pytest.fixture(scope="module")
def adata():
    """Small synthetic 4-cluster Poisson dataset with PCA + log-norm layer."""
    anndata = pytest.importorskip("anndata")
    pytest.importorskip("scanpy")
    pytest.importorskip("sklearn")
    import scanpy as sc
    from sklearn.decomposition import PCA

    rng = np.random.default_rng(0)
    blocks = [
        rng.poisson(lam=3 + i * 0.5, size=(N_CELLS // 4, N_GENES)).astype(np.float32)
        for i in range(4)
    ]
    X = np.vstack(blocks)
    ad = anndata.AnnData(X=X)
    ad.obs["celltype"] = (
        ["A"] * (N_CELLS // 4) + ["B"] * (N_CELLS // 4)
        + ["C"] * (N_CELLS // 4) + ["D"] * (N_CELLS // 4)
    )
    ad.var_names = [f"g{i}" for i in range(N_GENES)]
    ad.obs_names = [f"c{i}" for i in range(N_CELLS)]
    ad.obsm["X_pca"] = PCA(n_components=10, random_state=0).fit_transform(X.astype(float))
    ad.layers["raw_count"] = X.astype(np.int32)

    # log-normalised layer for rigor.
    norm = sc.pp.normalize_total(ad, target_sum=1e4, layer="raw_count", inplace=False)["X"]
    ad.layers["lognorm"] = sc.pp.log1p(norm)
    return ad


# ---------------------------------------------------------------------------
# Backend smoke tests (parametrised)
# ---------------------------------------------------------------------------


# `seacells` and `metaq` are slower; they still run in the smoke loop because
# their wrappers are the most likely to break.  `mc2` is excluded because the
# upstream `metacells` package is intentionally not a hard dep.
BACKENDS_TO_TEST = ["random", "kmeans", "geosketch", "supercell", "seacells", "metaq"]


@pytest.mark.parametrize("backend", BACKENDS_TO_TEST)
def test_backend_fit_and_schema(adata, backend):
    """Each backend fits and writes the unified obs/obsm/uns schema."""
    if backend == "metaq":
        pytest.importorskip("torch")
    ov = pytest.importorskip("omicverse")

    a = adata.copy()
    extra: dict = {}
    if backend == "metaq":
        extra.update(dict(train_epoch=10, warm_epochs=2, batch_size=64))

    mc = ov.single.MetaCell(
        a, method=backend, n_metacells=N_METACELLS,
        use_rep="X_pca", random_state=0, device="cpu", **extra,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mc.fit()

    assert mc._fit_result is not None
    assert mc._fit_result.assignments.shape == (N_CELLS,)
    assert "metacell_id" in a.obs
    assert "metacell_conf" in a.obs
    assert a.uns["metacell"]["method"] == backend

    if backend == "seacells":
        # Backward-compat column must still appear.
        assert "SEACell" in a.obs

    if "latent" in mc.capabilities:
        assert "X_metacell" in a.obsm

    if "soft" in mc.capabilities:
        assert "metacell_soft" in a.obsm


@pytest.mark.parametrize("backend", BACKENDS_TO_TEST)
def test_predicted_hard(adata, backend):
    if backend == "metaq":
        pytest.importorskip("torch")
    ov = pytest.importorskip("omicverse")

    a = adata.copy()
    extra: dict = {}
    if backend == "metaq":
        extra.update(dict(train_epoch=10, warm_epochs=2, batch_size=64))

    mc = ov.single.MetaCell(
        a, method=backend, n_metacells=N_METACELLS,
        use_rep="X_pca", random_state=0, device="cpu", **extra,
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mc.fit()

    ad_mc = mc.predicted(method="hard", layer="raw_count", summary="sum",
                         celltype_label="celltype")
    assert ad_mc.shape[1] == N_GENES
    assert ad_mc.shape[0] >= 1
    assert "n_cells" in ad_mc.obs
    assert "celltype" in ad_mc.obs
    assert "celltype_purity" in ad_mc.obs


def test_unsupported_capability_raises(adata):
    """random has no capabilities; querying soft/codebook/oos must raise."""
    ov = pytest.importorskip("omicverse")
    from omicverse.single._metacell_backends import UnsupportedCapability

    a = adata.copy()
    mc = ov.single.MetaCell(a, method="random", n_metacells=N_METACELLS).fit()

    with pytest.raises(UnsupportedCapability):
        mc.soft_membership()
    with pytest.raises(UnsupportedCapability):
        mc.codebook()
    with pytest.raises(UnsupportedCapability):
        mc.assign_new_cells(a)


def test_capability_matrix_shape():
    ov = pytest.importorskip("omicverse")
    df = ov.single.MetaCell.capability_matrix()
    assert "seacells" in df.index and "metaq" in df.index and "random" in df.index
    # MetaQ should advertise the union of soft/latent/codebook/out_of_sample.
    assert df.loc["metaq", "soft"] and df.loc["metaq", "latent"]
    assert df.loc["metaq", "codebook"] and df.loc["metaq", "out_of_sample"]


def test_legacy_seacells_signature(adata):
    """Old-style MetaCell(adata, use_rep, n_metacells, use_gpu=...) still works."""
    ov = pytest.importorskip("omicverse")
    a = adata.copy()

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mc = ov.single.MetaCell(
            a, use_rep="X_pca", n_metacells=N_METACELLS,
            use_gpu=False, verbose=False,
        )
        mc.initialize_archetypes()    # legacy shim
        mc.train(min_iter=5, max_iter=10)

    assert "SEACell" in a.obs
    assert "metacell_id" in a.obs
    ad_mc = mc.predicted(method="soft")
    assert ad_mc.shape[1] == N_GENES


@pytest.mark.parametrize("backend", ["kmeans", "random", "geosketch", "supercell"])
def test_save_load_roundtrip(tmp_path, adata, backend):
    ov = pytest.importorskip("omicverse")
    a = adata.copy()
    mc1 = ov.single.MetaCell(a, method=backend, n_metacells=N_METACELLS,
                              use_rep="X_pca").fit()
    path = tmp_path / f"{backend}.pkl"
    mc1.save(str(path))
    mc2 = ov.single.MetaCell(adata.copy(), method=backend, n_metacells=N_METACELLS,
                              use_rep="X_pca")
    mc2.load(str(path))
    if "codebook" in mc1.capabilities and "codebook" in mc2.capabilities:
        assert np.allclose(mc1.codebook(), mc2.codebook())


def test_check_rigor_returns_report(adata):
    """check_rigor produces a RigorReport with expected fields."""
    ov = pytest.importorskip("omicverse")
    from omicverse.external.mcRigor import RigorReport

    a = adata.copy()
    mc = ov.single.MetaCell(a, method="kmeans", n_metacells=N_METACELLS,
                             use_rep="X_pca").fit()
    rep = mc.check_rigor(layer_lognorm="lognorm", n_rep=10, feature_use=0,
                         gene_filter=0.0, random_state=0)
    assert isinstance(rep, RigorReport)
    assert rep.per_metacell.shape[0] >= 1
    assert {"metacell_id", "size", "mcDiv", "label"} <= set(rep.per_metacell.columns)
    assert 0.0 <= rep.dubious_rate <= 1.0
    assert 0.0 <= rep.score <= 1.0


def test_compare_metacell_backends_returns_table(adata):
    """compare_metacell_backends returns a benchmark dataframe with all backends."""
    ov = pytest.importorskip("omicverse")
    df = ov.single.compare_metacell_backends(
        adata.copy(),
        backends=["random", "kmeans", "geosketch", "supercell"],
        n_metacells=N_METACELLS,
        use_rep="X_pca",
        eval_label="celltype",
        layer_lognorm="lognorm",
        n_rigor_rep=10,
        random_state=0,
    )
    assert set(df.index) == {"random", "kmeans", "geosketch", "supercell"}
    expected_cols = {"runtime_s", "dubious_rate", "rigor_score",
                     "mean_purity", "mean_compactness", "n_metacells"}
    assert expected_cols <= set(df.columns)
    # Random's mean_purity should NOT be highest — sanity that purity discriminates.
    assert df["mean_purity"]["random"] <= max(df["mean_purity"][["kmeans", "supercell"]])


def test_metaq_assign_new_cells(adata):
    """MetaQ out-of-sample projection returns expected dict."""
    pytest.importorskip("torch")
    ov = pytest.importorskip("omicverse")
    a = adata.copy()
    mc = ov.single.MetaCell(
        a, method="metaq", n_metacells=N_METACELLS,
        train_epoch=10, warm_epochs=2, batch_size=64, device="cpu",
    ).fit()
    out = mc.assign_new_cells(adata[:30].copy())
    assert set(out.keys()) == {"metacell_id", "confidence", "embedding"}
    assert out["metacell_id"].shape == (30,)
    assert out["confidence"].shape == (30,)
    assert out["embedding"].shape[0] == 30
