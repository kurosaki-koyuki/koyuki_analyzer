import numpy as np
import pandas as pd
import pytest
import matplotlib.pyplot as plt
import sys
from types import ModuleType
from anndata import AnnData

import omicverse.pl._ccc as ccc_mod
import omicverse.pl._cpdbviz_plus as cpdbviz_plus_mod


class _StubAnnotation:
    def __init__(self, kind, *args, **kwargs):
        self.kind = kind
        self.args = args
        self.kwargs = kwargs


class _StubSizedHeatmap:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def add_left(self, *args, **kwargs):
        return None

    def add_right(self, *args, **kwargs):
        return None

    def add_top(self, *args, **kwargs):
        return None

    def add_bottom(self, *args, **kwargs):
        return None

    def add_layer(self, *args, **kwargs):
        return None

    def add_dendrogram(self, *args, **kwargs):
        return None

    def add_legends(self, *args, **kwargs):
        return None

    def add_title(self, *args, **kwargs):
        return None

    def render(self, *args, **kwargs):
        return object()


class _StubMA:
    __version__ = "0.5.6"
    SizedHeatmap = _StubSizedHeatmap


class _StubMP:
    @staticmethod
    def Numbers(*args, **kwargs):
        return _StubAnnotation("Numbers", *args, **kwargs)

    @staticmethod
    def Colors(*args, **kwargs):
        return _StubAnnotation("Colors", *args, **kwargs)

    @staticmethod
    def MarkerMesh(*args, **kwargs):
        return _StubAnnotation("MarkerMesh", *args, **kwargs)


def test_dot_matrix_plot_warns_for_broken_marsilea_056(monkeypatch):
    monkeypatch.setattr(ccc_mod, "_import_marsilea", lambda: (_StubMA, _StubMP))
    def _fake_render_plot(plotter):
        fig, _ax = plt.subplots()
        return fig

    monkeypatch.setattr(ccc_mod, "_render_plot", _fake_render_plot)

    matrix = pd.DataFrame([[1.0, 2.0], [0.5, 1.5]], index=["r1", "r2"], columns=["c1", "c2"])
    size_matrix = pd.DataFrame([[1.0, 0.0], [0.5, 1.0]], index=matrix.index, columns=matrix.columns)

    with pytest.warns(UserWarning, match="marsilea 0.5.6"):
        ccc_mod._dot_matrix_plot(
            matrix,
            size_matrix,
            color_label="Communication score",
            title="Bubble",
            cmap="Reds",
            figsize=(6, 4),
            border=False,
            add_text=False,
        )


def test_netvisual_bubble_marsilea_warns_for_broken_marsilea_056(monkeypatch):
    monkeypatch.setattr(cpdbviz_plus_mod, "MARSILEA_AVAILABLE", True)
    calls = []
    monkeypatch.setattr(
        cpdbviz_plus_mod,
        "_warn_if_broken_marsilea_version",
        lambda ma: calls.append(getattr(ma, "__version__", "")),
    )

    marsilea_mod = ModuleType("marsilea")
    marsilea_mod.__version__ = "0.5.6"
    marsilea_mod.SizedHeatmap = _StubSizedHeatmap
    marsilea_mod.__path__ = []
    plotter_mod = ModuleType("marsilea.plotter")
    plotter_mod.Numbers = _StubMP.Numbers
    plotter_mod.Colors = _StubMP.Colors
    plotter_mod.MarkerMesh = _StubMP.MarkerMesh
    marsilea_mod.plotter = plotter_mod

    sklearn_mod = ModuleType("sklearn")
    sklearn_mod.__path__ = []
    preprocessing_mod = ModuleType("sklearn.preprocessing")
    preprocessing_mod.normalize = lambda x, axis=0: np.asarray(x, dtype=float)
    sklearn_mod.preprocessing = preprocessing_mod

    monkeypatch.setitem(sys.modules, "marsilea", marsilea_mod)
    monkeypatch.setitem(sys.modules, "marsilea.plotter", plotter_mod)
    monkeypatch.setitem(sys.modules, "sklearn", sklearn_mod)
    monkeypatch.setitem(sys.modules, "sklearn.preprocessing", preprocessing_mod)

    viz = cpdbviz_plus_mod.CellChatVizPlus.__new__(cpdbviz_plus_mod.CellChatVizPlus)
    viz.cell_types = ["A", "B"]
    viz._get_cell_type_colors = lambda: {"A": "#111111", "B": "#222222"}

    adata = AnnData(np.zeros((2, 2)))
    adata.obs = pd.DataFrame({"sender": ["A", "B"], "receiver": ["B", "A"]}, index=["p1", "p2"])
    adata.var = pd.DataFrame(
        {
            "classification": ["Pathway1", "Pathway2"],
            "gene_a": ["Lig1", "Lig2"],
            "gene_b": ["Rec1", "Rec2"],
        },
        index=["f1", "f2"],
    )
    adata.layers["pvalues"] = np.array([[0.01, 0.2], [0.03, 0.04]])
    adata.layers["means"] = np.array([[0.5, 0.0], [0.6, 0.7]])
    viz.adata = adata

    with pytest.raises(Exception):
        viz.netVisual_bubble_marsilea(
            signaling=["Pathway1"],
            top_interactions=None,
            figsize=(6, 4),
        )

    assert calls == ["0.5.6"]
