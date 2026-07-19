import importlib
import sys
import types

import numpy as np
from anndata import AnnData


def test_umap_filters_unsupported_rapids_options(monkeypatch):
    import omicverse.pp._preprocess as preprocess

    captured = {}

    def fake_umap(adata, **kwargs):
        del adata
        captured.update(kwargs)

    fake_rsc = types.SimpleNamespace(tl=types.SimpleNamespace(umap=fake_umap))
    monkeypatch.setitem(sys.modules, "rapids_singlecell", fake_rsc)
    monkeypatch.setattr(preprocess.settings, "mode", "gpu")
    monkeypatch.setattr(preprocess, "add_reference", lambda *args, **kwargs: None)
    monkeypatch.setattr(preprocess, "note", lambda **kwargs: None)
    monkeypatch.setattr(preprocess, "pick_color_key", lambda adata: None)

    preprocess.umap(AnnData(np.ones((2, 2))), method="rapids", gamma=2.0)

    assert "gamma" not in captured
    assert "method" not in captured
    assert captured["min_dist"] == 0.5


def test_umap_falls_back_from_rapids(monkeypatch):
    preprocess = importlib.import_module("omicverse.pp._preprocess")
    umap_backend = importlib.import_module("omicverse.pp._umap")
    captured = {}

    def fail_rapids(adata, **kwargs):
        del adata, kwargs
        raise RuntimeError("RAPIDS unavailable")

    def fake_fallback(adata, **kwargs):
        del adata
        captured.update(kwargs)

    fake_rsc = types.SimpleNamespace(tl=types.SimpleNamespace(umap=fail_rapids))
    monkeypatch.setitem(sys.modules, "rapids_singlecell", fake_rsc)
    monkeypatch.setattr(umap_backend, "umap", fake_fallback)
    monkeypatch.setattr(preprocess.settings, "mode", "gpu")
    monkeypatch.setattr(preprocess, "note", lambda **kwargs: None)
    monkeypatch.setattr(preprocess, "pick_color_key", lambda adata: None)

    preprocess.umap(
        AnnData(np.ones((2, 2))), method="rapids", gamma=2.0, min_dist=0.2
    )

    assert captured["method"] == "umap-gpu"
    assert captured["gamma"] == 2.0
    assert captured["min_dist"] == 0.2


def test_umap_mixed_mode_overrides_dispatcher_method(monkeypatch):
    preprocess = importlib.import_module("omicverse.pp._preprocess")
    umap_backend = importlib.import_module("omicverse.pp._umap")
    captured = {}

    def fake_backend(adata, **kwargs):
        del adata
        captured.update(kwargs)

    monkeypatch.setattr(umap_backend, "umap", fake_backend)
    monkeypatch.setattr(preprocess.settings, "mode", "cpu-gpu-mixed")
    monkeypatch.setattr(preprocess, "print_gpu_usage_color", lambda: None)
    monkeypatch.setattr(preprocess, "add_reference", lambda *args, **kwargs: None)
    monkeypatch.setattr(preprocess, "note", lambda **kwargs: None)
    monkeypatch.setattr(preprocess, "pick_color_key", lambda adata: None)

    preprocess.umap(
        AnnData(np.ones((2, 2))), method="rapids", gamma=2.0, min_dist=0.2
    )

    assert captured["method"] == "umap-gpu"
    assert captured["gamma"] == 2.0
    assert captured["min_dist"] == 0.2
