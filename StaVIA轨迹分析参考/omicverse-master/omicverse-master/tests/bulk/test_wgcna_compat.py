import inspect

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import pdist


def test_float_ranks(monkeypatch):
    import omicverse.bulk._dynamicTree as dynamic_tree

    points = np.array(
        [[0.0], [0.01], [0.2], [0.21], [1.0], [1.01], [1.2], [1.21]]
    )
    distances = pdist(points)
    gene_tree = linkage(distances, method="average")
    rankdata = dynamic_tree.rankdata

    def float_rankdata(*args, **kwargs):
        return np.asarray(rankdata(*args, **kwargs), dtype=float)

    monkeypatch.setattr(dynamic_tree, "rankdata", float_rankdata)

    result = dynamic_tree.cutreeHybrid(
        gene_tree,
        distM=distances,
        minClusterSize=2,
        deepSplit=2,
        pamStage=False,
    )

    assert np.issubdtype(np.asarray(result["labels"]).dtype, np.integer)


def test_float_labels():
    from omicverse.external.PyWGCNA.wgcna import pyWGCNA

    labels = pd.DataFrame(
        {
            "Name": [0.0, 1.0, 2.0],
            "Value": [0.0, 1.0, 2.0],
        }
    )

    colors = pyWGCNA.labels2colors(
        labels,
        colorSeq=["grey", "blue", "brown"],
    )

    assert colors.tolist() == ["grey", "blue", "brown"]


def test_save_roundtrip(tmp_path):
    import omicverse as ov

    expression = pd.DataFrame(
        [[1.0, 2.0], [3.0, 4.0]],
        index=["sample-1", "sample-2"],
        columns=["gene-1", "gene-2"],
    )
    wgcna = ov.bulk.pyWGCNA(
        name="pickle-smoke",
        species="mus musculus",
        geneExp=expression,
        outputPath=f"{tmp_path}/",
        save=False,
    )

    wgcna.saveWGCNA()
    restored = ov.bulk.readWGCNA(tmp_path / "pickle-smoke.p")

    assert inspect.isclass(ov.bulk.pyWGCNA)
    assert type(restored) is type(wgcna)
