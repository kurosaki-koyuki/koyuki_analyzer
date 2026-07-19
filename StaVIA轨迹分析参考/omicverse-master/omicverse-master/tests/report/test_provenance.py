"""Tests for ``omicverse.report`` — provenance, ``@tracked`` nesting guard,
h5ad round-trip, and end-to-end HTML rendering on synthetic data.

These tests don't run any real omicverse pipeline; they invoke the
provenance primitives directly on small in-memory AnnData objects so
they finish fast and have no optional-dependency surface.
"""
from __future__ import annotations

import os
import tempfile

import anndata as ad
import numpy as np
import pandas as pd
import pytest

from omicverse.report._provenance import (
    PROVENANCE_KEY,
    clear_provenance,
    get_provenance,
    note,
    record_step,
    tracked,
)


def _toy_adata(n_obs: int = 40, n_vars: int = 20) -> ad.AnnData:
    rng = np.random.default_rng(0)
    X = rng.poisson(1.0, size=(n_obs, n_vars)).astype(np.float32)
    obs = pd.DataFrame({"cluster": rng.integers(0, 3, n_obs).astype(str)},
                        index=[f"c{i}" for i in range(n_obs)])
    var = pd.DataFrame(index=[f"g{i}" for i in range(n_vars)])
    return ad.AnnData(X=X, obs=obs, var=var)


# ─────────────────────────── record_step primitive ────────────────────────────


def test_record_step_roundtrip():
    adata = _toy_adata()
    record_step(adata, "umap", function="ov.pp.umap",
                params={"min_dist": 0.3}, backend="omicverse(cpu) · scanpy",
                duration_s=0.5, viz=[{"function": "ov.pl.embedding",
                                       "kwargs": {"basis": "X_umap"}}])
    prov = get_provenance(adata)
    assert len(prov) == 1
    e = prov[0]
    assert e["name"] == "umap"
    assert e["function"] == "ov.pp.umap"
    assert e["params"] == {"min_dist": 0.3}
    assert e["backend"] == "omicverse(cpu) · scanpy"
    assert e["duration_s"] == pytest.approx(0.5)
    assert e["viz"] == [{"function": "ov.pl.embedding",
                          "kwargs": {"basis": "X_umap"}}]


def test_record_step_preserves_order():
    adata = _toy_adata()
    for name in ("qc", "pca", "umap"):
        record_step(adata, name, function=f"ov.pp.{name}")
    names = [e["name"] for e in get_provenance(adata)]
    assert names == ["qc", "pca", "umap"]


def test_clear_provenance():
    adata = _toy_adata()
    record_step(adata, "umap", function="ov.pp.umap")
    assert len(get_provenance(adata)) == 1
    clear_provenance(adata)
    assert get_provenance(adata) == []


def test_record_step_never_raises_on_bad_adata():
    # Best-effort contract: a broken adata must not crash the caller.
    record_step(None, "umap", function="ov.pp.umap")
    class _NoUns: pass
    record_step(_NoUns(), "umap", function="ov.pp.umap")


# ─────────────────────────── h5ad round-trip ──────────────────────────────────


def test_h5ad_roundtrip_preserves_provenance(tmp_path):
    adata = _toy_adata()
    viz = [{"function": "ov.pl.embedding",
             "kwargs": {"basis": "X_umap", "color": "cluster"}}]
    record_step(adata, "qc", function="ov.pp.qc",
                params={"tresh": {"mito_perc": 0.2}},
                backend="omicverse(cpu)", duration_s=1.1, viz=viz,
                n_obs_before=50, n_obs_after=40)
    record_step(adata, "umap", function="ov.pp.umap",
                params={"min_dist": 0.3}, backend="omicverse(cpu) · scanpy",
                duration_s=2.3, viz=viz)

    path = tmp_path / "toy.h5ad"
    adata.write_h5ad(path, compression="gzip")
    loaded = ad.read_h5ad(path)
    prov = get_provenance(loaded)
    assert [e["name"] for e in prov] == ["qc", "umap"]
    # viz round-trips as a live list-of-dicts despite JSON-encoded storage.
    assert prov[0]["viz"] == viz
    assert prov[0]["n_obs_before"] == 50
    assert prov[0]["n_obs_after"] == 40
    assert prov[0]["params"] == {"tresh": {"mito_perc": 0.2}}


# ───────────────────────── @tracked decorator ─────────────────────────────────


def test_tracked_records_a_single_entry():
    @tracked("umap", "ov.pp.umap")
    def umap(adata, *, min_dist=0.5, **kwargs):
        note(backend="omicverse(cpu) · scanpy")

    adata = _toy_adata()
    umap(adata, min_dist=0.3)
    prov = get_provenance(adata)
    assert len(prov) == 1
    e = prov[0]
    assert e["name"] == "umap"
    assert e["function"] == "ov.pp.umap"
    assert e["backend"] == "omicverse(cpu) · scanpy"
    # Only the user-passed kwarg, not the default.
    assert e["params"] == {"min_dist": 0.3}
    # @tracked populates timing and n_obs automatically.
    assert e["duration_s"] is not None
    assert e["n_obs_before"] == adata.n_obs
    assert e["n_obs_after"] == adata.n_obs


def test_tracked_nested_call_produces_one_entry():
    """Outer @tracked dispatcher invoking an inner @tracked one must
    leave exactly one entry — the outer — so the report reflects what
    the user literally wrote, not the internal call graph."""

    @tracked("scrublet", "ov.pp.scrublet")
    def scrublet(adata, **kwargs):
        note(backend="scrublet")

    @tracked("qc", "ov.pp.qc")
    def qc(adata, *, doublets_method=None, **kwargs):
        if doublets_method == "scrublet":
            scrublet(adata)                  # nested tracked call
        note(backend="omicverse(cpu) · mode=seurat")

    adata = _toy_adata()
    qc(adata, doublets_method="scrublet")
    prov = get_provenance(adata)
    assert len(prov) == 1
    assert prov[0]["name"] == "qc"
    assert prov[0]["backend"] == "omicverse(cpu) · mode=seurat"


def test_tracked_skips_record_on_exception():
    @tracked("umap", "ov.pp.umap")
    def umap_fails(adata, **kwargs):
        raise RuntimeError("boom")

    adata = _toy_adata()
    with pytest.raises(RuntimeError, match="boom"):
        umap_fails(adata)
    assert get_provenance(adata) == []


def test_tracked_direct_scrublet_call_still_records():
    """When the user calls the decorated dispatcher DIRECTLY (not nested),
    the entry is emitted — the nesting guard only silences INTERNAL hops."""

    @tracked("scrublet", "ov.pp.scrublet")
    def scrublet(adata, **kwargs):
        note(backend="scrublet")

    adata = _toy_adata()
    scrublet(adata)
    prov = get_provenance(adata)
    assert len(prov) == 1
    assert prov[0]["name"] == "scrublet"


def test_note_viz_is_additive():
    """Multiple note(viz=[...]) calls in the same body append, not overwrite."""

    @tracked("leiden", "ov.pp.leiden")
    def leiden(adata, **kwargs):
        note(viz=[{"function": "ov.pl.cluster_sizes_bar",
                    "kwargs": {"groupby": "leiden"}}])
        note(viz=[{"function": "ov.pl.embedding",
                    "kwargs": {"basis": "X_umap", "color": "leiden"}}])

    adata = _toy_adata()
    leiden(adata)
    prov = get_provenance(adata)
    assert len(prov) == 1
    viz = prov[0]["viz"]
    assert len(viz) == 2
    assert viz[0]["function"] == "ov.pl.cluster_sizes_bar"
    assert viz[1]["function"] == "ov.pl.embedding"


def test_tracked_captures_n_obs_change():
    """n_obs_before reflects the adata AT ENTRY, not post-filter."""

    @tracked("qc", "ov.pp.qc")
    def qc(adata, **kwargs):
        # Simulate filter-style mutation: drop two cells in place.
        import anndata as _ad
        adata._inplace_subset_obs(np.arange(adata.n_obs - 2))

    adata = _toy_adata(n_obs=10)
    qc(adata)
    prov = get_provenance(adata)
    assert len(prov) == 1
    assert prov[0]["n_obs_before"] == 10
    assert prov[0]["n_obs_after"] == 8


# ─────────────── @tracked on class methods (adata_attr) ──────────────────────


def test_tracked_method_pulls_adata_from_self():
    """``@tracked(adata_attr='adata')`` records on the AnnData held by
    ``self``, not on ``args[0]`` (which is ``self`` itself)."""

    class Annotator:
        def __init__(self, adata):
            self.adata = adata

        @tracked("Annotator.annotate", "ov.x.Annotator.annotate",
                 adata_attr="adata")
        def annotate(self, *, method="celltypist"):
            note(backend=f"omicverse · method={method}")

    adata = _toy_adata()
    Annotator(adata).annotate(method="celltypist")
    prov = get_provenance(adata)
    assert len(prov) == 1
    e = prov[0]
    assert e["name"] == "Annotator.annotate"
    assert e["function"] == "ov.x.Annotator.annotate"
    assert e["params"] == {"method": "celltypist"}
    assert e["backend"] == "omicverse · method=celltypist"
    assert e["n_obs_before"] == adata.n_obs
    assert e["n_obs_after"] == adata.n_obs


def test_tracked_method_uses_custom_adata_attr():
    """``adata_attr`` can name any attribute (e.g. ``adata_query`` for
    reference-based annotators)."""

    class RefAnnotator:
        def __init__(self, adata_query, adata_ref):
            self.adata_query = adata_query
            self.adata_ref = adata_ref

        @tracked("RefAnnotator.predict", "ov.x.RefAnnotator.predict",
                 adata_attr="adata_query")
        def predict(self, *, method="harmony"):
            note(backend=f"RefAnnotator · {method}")

    query = _toy_adata()
    reference = _toy_adata()
    RefAnnotator(query, reference).predict(method="harmony")
    # Entry lands on the query, not the reference.
    assert len(get_provenance(query)) == 1
    assert get_provenance(reference) == []


def test_tracked_method_nested_inside_tracked_function_silent():
    """A tracked free function calling a tracked class method (or vice
    versa) still produces exactly one entry — outermost wins regardless
    of which kind of dispatcher is on the stack."""

    class _Inner:
        def __init__(self, adata):
            self.adata = adata

        @tracked("inner.run", "ov.x.inner.run", adata_attr="adata")
        def run(self):
            note(backend="inner")

    @tracked("outer", "ov.x.outer")
    def outer(adata):
        _Inner(adata).run()  # nested tracked method
        note(backend="outer")

    adata = _toy_adata()
    outer(adata)
    prov = get_provenance(adata)
    assert len(prov) == 1
    assert prov[0]["name"] == "outer"
    assert prov[0]["backend"] == "outer"


# ─────────────────────────── HTML rendering ───────────────────────────────────


def test_from_anndata_renders_html(tmp_path, monkeypatch):
    """End-to-end: synthetic provenance → self-contained HTML file."""
    # Avoid the ov.style() import side-effect during the test — we only
    # want to verify that render() completes and the file is valid.
    monkeypatch.setenv("OMICVERSE_DISABLE_LLM", "1")

    import omicverse as ov  # lazy, respects env

    adata = _toy_adata()
    record_step(adata, "qc", function="ov.pp.qc",
                params={"mode": "seurat"},
                backend="omicverse(cpu)", duration_s=0.1,
                n_obs_before=50, n_obs_after=adata.n_obs,
                viz=[])   # no viz → renders placeholder, never crashes

    out = tmp_path / "report.html"
    ov.report.from_anndata(adata, output=out, title="toy")
    assert out.exists()
    html = out.read_text()
    # Must be a well-formed single-file HTML doc.
    assert html.startswith("<!DOCTYPE html>") or html.startswith("<html")
    # The qc section must appear.
    assert "Quality Control" in html
    # Self-contained: no external image references (everything inline).
    assert "src=\"http" not in html and "src='http" not in html


def test_from_anndata_empty_provenance(tmp_path, monkeypatch):
    """AnnData with no provenance still produces a (mostly empty) report."""
    monkeypatch.setenv("OMICVERSE_DISABLE_LLM", "1")
    import omicverse as ov
    adata = _toy_adata()
    out = tmp_path / "empty.html"
    ov.report.from_anndata(adata, output=out)
    assert out.exists()
    assert "No omicverse pipeline steps detected" in out.read_text()
