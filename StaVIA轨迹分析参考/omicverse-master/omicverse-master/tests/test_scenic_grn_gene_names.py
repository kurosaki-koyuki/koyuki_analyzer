"""Regression test for issue #681.

``scenic_obj.cal_grn(method='grnboost2', layer='counts_RNA',
tf_names=tf_list)`` blew up with::

    File "arboreto/algo.py", line 218, in _prepare_input
        assert expression_matrix.shape[1] == len(gene_names)
    TypeError: object of type 'NoneType' has no len()

because the expression matrix arrives at arboreto as a bare
``ndarray`` (no column names) and the omicverse wrapper never
forwarded ``gene_names``. arboreto's contract requires it whenever
``expression_data`` isn't a pandas DataFrame.

These tests pin both the grnboost2 and genie3 paths so the bug
can't return.

We don't run the real arboreto algorithms (they spin up a Dask
cluster and take minutes on real data, and the dask/distributed
versions in CI may not match the omicverse-bundled arboreto). We
mock the imported callables and check the wrapper passed
``gene_names`` through.
"""
from __future__ import annotations

import sys
import types
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp
from anndata import AnnData


@pytest.fixture
def fake_arboreto_module(monkeypatch):
    """Install a stand-in for ``omicverse.external.single.arboreto.algo``
    in ``sys.modules`` BEFORE ``cal_grn`` does
    ``from ..external.single.arboreto.algo import grnboost2``.

    The real arboreto module imports ``distributed.client`` which
    transitively requires ``dask._expr`` — that's a known dask /
    distributed version-skew problem in this environment but
    irrelevant to the bug we're testing. The fake module lets
    cal_grn's import succeed without touching dask at all and
    captures the kwargs that would have gone to the real algorithms.
    """
    captured: dict[str, dict] = {"grnboost2": {}, "genie3": {}}

    def make_recorder(name: str):
        def _stub(*, expression_data, gene_names=None,
                  tf_names=None, **rest):
            captured[name].update(
                expression_data_shape=expression_data.shape,
                gene_names=gene_names,
                tf_names=tf_names,
            )
            return pd.DataFrame({
                "TF":         [f"TF{i}" for i in range(5)],
                "target":     [f"Gene{i:03d}" for i in range(5)],
                "importance": np.arange(5, dtype=np.float32),
            })
        return _stub

    fake = types.ModuleType("omicverse.external.single.arboreto.algo")
    fake.grnboost2 = make_recorder("grnboost2")
    fake.genie3    = make_recorder("genie3")
    monkeypatch.setitem(
        sys.modules,
        "omicverse.external.single.arboreto.algo",
        fake,
    )

    fake_distributed = types.ModuleType("distributed")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def close(self):
            pass

        def compute(self, *args, **kwargs):
            return None

    class FakeLocalCluster:
        def __init__(self, *args, **kwargs):
            pass

        def close(self):
            pass

    fake_distributed.Client = FakeClient
    fake_distributed.LocalCluster = FakeLocalCluster
    monkeypatch.setitem(sys.modules, "distributed", fake_distributed)
    return captured


def _make_scenic_adata(n: int = 40, n_genes: int = 12, seed: int = 0) -> AnnData:
    """An AnnData with a ``counts_RNA`` sparse layer and integer counts.

    cal_grn rejects log-normalised layers (``layer.max() < log(1e4)``),
    so the synthetic counts need at least one entry above ~9.2 to look
    like raw UMI counts. We seed in a guaranteed high count.
    """
    rng = np.random.default_rng(seed)
    counts = rng.poisson(lam=2.0, size=(n, n_genes)).astype(np.float32)
    counts[0, 0] = 25.0  # guarantee max > log(1e4) ≈ 9.21
    adata = AnnData(X=counts.copy())
    adata.var_names = [f"Gene{i:03d}" for i in range(n_genes)]
    adata.layers["counts_RNA"] = sp.csr_matrix(counts)
    return adata


def _make_scenic_obj(adata: AnnData):
    """SCENIC.__init__ wants a glob of ranking-database files +
    motif annotations on disk; cal_grn touches neither. Build the
    object via ``__new__`` so we can exercise cal_grn in isolation.

    The public ``omicverse.single.SCENIC`` is a ``@register_function``-
    decorated wrapper around the class — unwrap it to get the
    underlying ``type`` so ``__new__`` works."""
    from omicverse.single import SCENIC as wrapped
    cls = getattr(wrapped, "__wrapped__", wrapped)

    obj = cls.__new__(cls)
    obj.adata = adata
    obj.n_jobs = 1
    return obj


def _stub_edgelist(n_pairs: int = 5) -> pd.DataFrame:
    """Mimics arboreto's grnboost2 / genie3 return shape so cal_grn's
    downstream `.astype` etc. succeeds."""
    return pd.DataFrame({
        "TF":         [f"TF{i}" for i in range(n_pairs)],
        "target":     [f"Gene{i:03d}" for i in range(n_pairs)],
        "importance": np.arange(n_pairs, dtype=np.float32),
    })


def _patch_ranking_database(monkeypatch):
    from omicverse.external.ctxcore import rnkdb

    class FakeRankingDatabase:
        def __init__(self, fname, name):
            self.fname = fname
            self.name = name

    monkeypatch.setattr(rnkdb, "FeatherRankingDatabase", FakeRankingDatabase)
    return FakeRankingDatabase


# --------------------------------------------------------------------------- #
# grnboost2 path — the one in the bug report
# --------------------------------------------------------------------------- #

def test_cal_grn_grnboost2_passes_gene_names(fake_arboreto_module) -> None:
    adata = _make_scenic_adata()
    obj = _make_scenic_obj(adata)

    obj.cal_grn(method="grnboost2", layer="counts_RNA",
                tf_names=["Gene000", "Gene001", "Gene002"])

    captured = fake_arboreto_module["grnboost2"]
    assert captured["gene_names"] is not None, (
        "cal_grn must forward gene_names to grnboost2 when expression_data "
        "is a bare ndarray (issue #681)."
    )
    assert captured["gene_names"] == list(adata.var_names)
    # The whole point: arboreto's `_prepare_input` asserts
    # ``expression_matrix.shape[1] == len(gene_names)``.
    assert captured["expression_data_shape"][1] == len(captured["gene_names"])
    assert captured["tf_names"] == ["Gene000", "Gene001", "Gene002"]


# --------------------------------------------------------------------------- #
# genie3 path — same bug, same fix
# --------------------------------------------------------------------------- #

def test_cal_grn_genie3_passes_gene_names(fake_arboreto_module) -> None:
    adata = _make_scenic_adata()
    obj = _make_scenic_obj(adata)

    obj.cal_grn(method="genie3", layer="counts_RNA",
                tf_names=["Gene005", "Gene006"])

    captured = fake_arboreto_module["genie3"]
    assert captured["gene_names"] is not None
    assert captured["gene_names"] == list(adata.var_names)
    assert captured["expression_data_shape"][1] == len(captured["gene_names"])
    assert captured["tf_names"] == ["Gene005", "Gene006"]


def test_scenic_species_uses_cached_resources(tmp_path, monkeypatch) -> None:
    from omicverse.single import SCENIC as wrapped

    _patch_ranking_database(monkeypatch)
    cls = getattr(wrapped, "__wrapped__", wrapped)

    resource_dir = tmp_path / "mouse_mm10"
    resource_dir.mkdir()
    db_path = resource_dir / (
        "mm10_500bp_up_100bp_down_full_tx_v10_clust."
        "genes_vs_motifs.rankings.feather"
    )
    motif_path = resource_dir / "motifs-v10nr_clust-nr.mgi-m0.001-o0.0.tbl"
    db_path.touch()
    motif_path.touch()

    obj = cls(
        _make_scenic_adata(),
        species="mm10",
        data_dir=tmp_path,
        db_names="500bp",
        download=False,
        n_jobs=1,
    )

    assert obj.species == "mouse"
    assert obj.db_glob == [str(db_path)]
    assert obj.motif_path == str(motif_path)
    assert obj.scenic_resource_dir == str(resource_dir)
    assert len(obj.dbs) == 1


def test_scenic_species_downloads_missing_resources(tmp_path, monkeypatch) -> None:
    import omicverse.datasets as datasets
    from omicverse.single import SCENIC as wrapped

    _patch_ranking_database(monkeypatch)
    cls = getattr(wrapped, "__wrapped__", wrapped)
    downloads = []

    def fake_download(url, file_path=None, dir="./data"):
        downloads.append((url, file_path, dir))
        path = tmp_path / "human_hg38" / file_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return str(path)

    monkeypatch.setattr(datasets, "download_data_requests", fake_download)

    obj = cls(
        _make_scenic_adata(),
        species="human",
        data_dir=tmp_path,
        db_names="500bp",
        download=True,
        n_jobs=1,
    )

    assert obj.species == "human"
    assert len(downloads) == 2
    assert obj.db_glob[0].endswith(".genes_vs_motifs.rankings.feather")
    assert obj.motif_path.endswith(".tbl")
