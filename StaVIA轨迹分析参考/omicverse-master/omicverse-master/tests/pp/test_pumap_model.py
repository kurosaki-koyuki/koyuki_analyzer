"""ov.pp.umap(method='pumap') returns a reusable model that projects new data."""
import numpy as np
import pytest


def _ref_query():
    import scanpy as sc
    import omicverse as ov

    ad = sc.datasets.pbmc3k()
    sc.pp.filter_genes(ad, min_cells=3)
    sc.pp.normalize_total(ad, target_sum=1e4)
    sc.pp.log1p(ad)
    sc.pp.highly_variable_genes(ad, n_top_genes=2000)
    ad = ad[:, ad.var.highly_variable].copy()
    ov.pp.scale(ad)
    ov.pp.pca(ad, n_pcs=50, layer="scaled")
    import scanpy as sc
    sc.pp.neighbors(ad, use_rep="scaled|original|X_pca", random_state=0)
    return ad[:2000].copy(), ad[2000:].copy()


@pytest.mark.skipif(
    not __import__("torch").cuda.is_available(),
    reason="parametric UMAP (pumap) needs a GPU",
)
def test_pumap_returns_model_and_projects_new_data():
    import contextlib
    import io

    import omicverse as ov

    ref, qry = _ref_query()
    ov.settings.mode = "cpu-gpu-mixed"
    with contextlib.redirect_stdout(io.StringIO()):
        model = ov.pp.umap(ref, method="pumap")

    # model returned, reference embedding written
    assert model is not None and hasattr(model, "transform")
    assert ref.obsm["X_umap"].shape == (ref.n_obs, 2)

    # project NEW data through the learned mapping (same PCA space)
    qx = np.ascontiguousarray(qry.obsm["scaled|original|X_pca"], dtype=np.float32)
    emb = model.transform(qx)
    assert emb.shape == (qry.n_obs, 2) and np.isfinite(emb).all()
    # deterministic for the same fitted model + input
    assert np.allclose(emb, model.transform(qx))


@pytest.mark.skipif(
    not __import__("torch").cuda.is_available(),
    reason="parametric UMAP (pumap) needs a GPU",
)
def test_pumap_save_load(tmp_path):
    import contextlib
    import io

    import omicverse as ov

    ref, qry = _ref_query()
    ov.settings.mode = "cpu-gpu-mixed"
    with contextlib.redirect_stdout(io.StringIO()):
        model = ov.pp.umap(ref, method="pumap")
    qx = np.ascontiguousarray(qry.obsm["scaled|original|X_pca"], dtype=np.float32)
    emb = model.transform(qx)

    p = str(tmp_path / "pumap.pkl")
    model.save(p)
    m2 = ov.pp.load_pumap(p)
    assert np.allclose(m2.transform(qx), emb)
