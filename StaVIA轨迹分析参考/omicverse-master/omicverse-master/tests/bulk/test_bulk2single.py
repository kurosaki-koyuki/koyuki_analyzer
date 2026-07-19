import numpy as np
import pandas as pd
from anndata import AnnData


def _bulk2single_model():
    from omicverse.bulk2single._bulk2single import Bulk2Single

    bulk_data = pd.DataFrame([[1.0]], index=["g1"], columns=["sample"])
    single_data = AnnData(
        np.array([[1.0]]),
        obs=pd.DataFrame({"celltype": ["A"]}, index=["cell"]),
        var=pd.DataFrame(index=["g1"]),
    )
    return Bulk2Single(bulk_data, single_data, celltype_key="celltype")


def _prediction(index):
    return pd.DataFrame({"A": [1.0]}, index=index)


def test_predicted_fraction_forwards_scaden_options(monkeypatch):
    from omicverse.external import tape

    captured = {}

    def fake_scaden(reference, bulk, **kwargs):
        del reference
        captured.update(kwargs)
        return _prediction(bulk.index)

    monkeypatch.setattr(tape, "ScadenDeconvolution", fake_scaden)

    result = _bulk2single_model().predicted_fraction(
        method="scaden",
        scaler="mms",
        scale=False,
        pseudobulk_size=7,
        epochs=1,
    )

    assert list(result.columns) == ["A"]
    assert captured["scale"] is False
    assert captured["pseudobulk_size"] == 7
    assert "scaler" not in captured


def test_predicted_fraction_forwards_tape_options(monkeypatch):
    from omicverse.external import tape

    captured = {}

    def fake_tape(reference, bulk, **kwargs):
        del reference
        captured.update(kwargs)
        return None, _prediction(bulk.index)

    monkeypatch.setattr(tape, "Deconvolution", fake_tape)

    _bulk2single_model().predicted_fraction(
        method="tape",
        scaler="ss",
        scale=False,
        pseudobulk_size=7,
        epochs=1,
    )

    assert captured["scaler"] == "ss"
    assert captured["scale"] is False
    assert captured["pseudobulk_size"] == 7


def _marker_stub(adata, groupby, method):
    del groupby, method
    adata.uns["rank_genes_groups"] = {
        "names": {"A": ["g1"], "B": ["g2"]},
    }


def _mapping_data():
    expression = pd.DataFrame(
        [[1.0, 2.0, 3.0, 4.0], [2.0, 2.0, 1.0, 3.0]],
        index=["g1", "g2"],
        columns=["c1", "c2", "c3", "c4"],
    )
    metadata = pd.DataFrame(
        {
            "Cell": ["c1", "c2", "c3", "c4"],
            "Cell_type": ["A", "A", "B", "B"],
        }
    )
    return expression, metadata


def test_create_st_selects_markers(monkeypatch):
    import scanpy as sc

    from omicverse.bulk2single._map_utils import create_st

    monkeypatch.setattr(sc.tl, "rank_genes_groups", _marker_stub)
    expression, metadata = _mapping_data()

    selected, _, spots, _ = create_st(
        expression,
        metadata,
        spot_num=1,
        cell_num=2,
        gene_num=1,
        marker_used=True,
    )

    assert list(selected.index) == ["g1", "g2"]
    assert list(spots.index) == ["g1", "g2"]


def test_dfrunner_selects_markers(monkeypatch):
    import scanpy as sc

    from omicverse.bulk2single._map_utils import DFRunner

    monkeypatch.setattr(sc.tl, "rank_genes_groups", _marker_stub)
    expression, metadata = _mapping_data()
    spatial = pd.DataFrame([[1.0], [2.0]], index=["g1", "g2"], columns=["s1"])

    runner = DFRunner(
        expression,
        metadata,
        spatial,
        pd.DataFrame(index=["s1"]),
        marker_used=True,
        top_marker_num=1,
    )

    assert list(runner.sc_test.index) == ["g1", "g2"]
    assert list(runner.st_test.index) == ["g1", "g2"]
