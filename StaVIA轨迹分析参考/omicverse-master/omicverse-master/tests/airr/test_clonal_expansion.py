"""Tests for ov.airr.clonal_expansion — int clip_at + custom bins (issue #810)."""
import numpy as np
import pytest


def _toy_adata():
    import anndata as ad

    # clones of sizes 1, 3, 7, 30, 80, 150 — one per target bin
    clone_ids = []
    for cid, size in [("c1", 1), ("c3", 3), ("c7", 7),
                      ("c30", 30), ("c80", 80), ("c150", 150)]:
        clone_ids += [cid] * size
    rng = np.random.default_rng(0)
    adata = ad.AnnData(rng.random((len(clone_ids), 5)).astype(np.float32))
    adata.obs["clone_id"] = clone_ids
    return adata


def _first_per_clone(adata, key="clonal_expansion"):
    s = adata.obs.groupby("clone_id", observed=True)[key].first()
    return {k: str(v) for k, v in s.to_dict().items()}


def test_int_clip_at_backward_compatible():
    from omicverse.airr import clonal_expansion

    adata = _toy_adata()
    clonal_expansion(adata, clip_at=4)
    cats = list(adata.obs["clonal_expansion"].cat.categories)
    assert cats == ["1 (single)", "2", "3", ">= 4"]
    assert adata.obs["clonal_expansion"].cat.ordered
    m = _first_per_clone(adata)
    assert m["c1"] == "1 (single)"
    assert m["c3"] == "3"
    assert m["c7"] == ">= 4" and m["c150"] == ">= 4"


def test_custom_bins_match_issue_spec():
    from omicverse.airr import clonal_expansion

    adata = _toy_adata()
    clonal_expansion(adata, clip_at=[1, 5, 10, 50, 100])
    cats = list(adata.obs["clonal_expansion"].cat.categories)
    assert cats == ["1 (single)", "2-5", "6-10", "11-50", "51-100", ">100"]
    assert adata.obs["clonal_expansion"].cat.ordered
    m = _first_per_clone(adata)
    assert m == {
        "c1": "1 (single)", "c3": "2-5", "c7": "6-10",
        "c30": "11-50", "c80": "51-100", "c150": ">100",
    }


def test_custom_bins_without_singleton_edge():
    """First edge need not be 1; range labels still come out right."""
    from omicverse.airr import clonal_expansion

    adata = _toy_adata()
    clonal_expansion(adata, clip_at=[10, 100])
    cats = list(adata.obs["clonal_expansion"].cat.categories)
    assert cats == ["1-10", "11-100", ">100"]
    m = _first_per_clone(adata)
    assert m["c1"] == "1-10" and m["c7"] == "1-10"
    assert m["c30"] == "11-100" and m["c150"] == ">100"


@pytest.mark.parametrize("bad", [[5, 2, 10], [0, 5], [3, 3], []])
def test_invalid_bins_raise(bad):
    from omicverse.airr import clonal_expansion

    adata = _toy_adata()
    with pytest.raises(ValueError):
        clonal_expansion(adata, clip_at=bad)


def test_missing_clone_column_raises():
    import anndata as ad
    from omicverse.airr import clonal_expansion

    adata = ad.AnnData(np.zeros((4, 3), dtype=np.float32))
    with pytest.raises(KeyError):
        clonal_expansion(adata, clip_at=[1, 5])
