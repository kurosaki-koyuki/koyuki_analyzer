"""Regression test for ``omicverse.io.spatial.read_atera``.

The real Atera FFPE Breast Cancer ``outs.zip`` is 55 GB and the H&E TIFF
companion is 17 GB — too big to ship through CI. This test builds a tiny
synthetic Atera bundle on disk (matching schema, ~30 cells, ~20 genes) and
runs the reader end-to-end with ``load_image=False``. It covers:

- the 10x ``cell_feature_matrix.h5`` schema (CSC, byte-string ids/features),
- ``Gene Expression`` filtering (control probes / codewords are dropped),
- ``cells.parquet`` centroid columns ``x_centroid`` / ``y_centroid``,
- ``experiment.xenium`` JSON → ``uns['spatial'][library]['metadata']``,
- ``cell_boundaries.parquet`` → ``obs['geometry']`` (WKT POLYGON),
- ``nucleus_boundaries.parquet`` → ``obs['nucleus_geometry']`` (Atera-only),
- optional ``cell_groups.csv`` merge → ``obs['cell_group']`` /
  ``obs['cell_group_color']`` (incl. NaN handling for cells absent
  from the CSV — the bug that broke the tutorial scatter),
- optional H&E ``alignment.csv`` → ``scalefactors['he_affine']``,
- the channel-name selector (``image_key='dapi'`` / ``'boundary'`` /
  ``'rna'`` / ``'stroma'`` / ``'2'`` / ``'cd45'``) against synthetic
  ``morphology_focus/ch####_<tag>.ome.tif`` filenames.
"""
from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp


N_CELLS = 32
N_GENES = 18
N_CONTROLS = 4   # control probes / codewords that must be dropped
PIXEL_SIZE_UM = 0.2125


# --------------------------------------------------------------------------- #
# Synthetic Atera bundle factory
# --------------------------------------------------------------------------- #


def _write_cell_feature_matrix_h5(path: Path) -> tuple[list[str], list[str]]:
    """Write a 10x-style HDF5 matrix with control probes mixed in.

    Returns ``(cell_ids, gene_names_only)`` so the rest of the bundle can
    be aligned with what the matrix says is in row 0..N_CELLS-1.
    """
    rng = np.random.default_rng(0)
    n_total = N_GENES + N_CONTROLS
    # 5% density, integer counts
    mat = sp.random(n_total, N_CELLS, density=0.5, format="csc",
                    random_state=0,
                    data_rvs=lambda size: rng.integers(1, 10, size=size)).astype(np.int32)

    cell_ids = [f"cell{i:03d}" for i in range(N_CELLS)]
    gene_ids = [f"GENE{i:03d}" for i in range(N_GENES)]
    ctrl_ids = [f"CTRL{i:03d}" for i in range(N_CONTROLS)]
    feature_ids = gene_ids + ctrl_ids
    feature_names = list(feature_ids)
    feature_types = (["Gene Expression"] * N_GENES
                     + ["Negative Control Probe"] * N_CONTROLS)

    with h5py.File(path, "w") as f:
        m = f.create_group("matrix")
        m.create_dataset("barcodes",
                         data=np.array([s.encode() for s in cell_ids], dtype="|S20"))
        m.create_dataset("data", data=mat.data)
        m.create_dataset("indices", data=mat.indices.astype(np.int64))
        m.create_dataset("indptr", data=mat.indptr.astype(np.int64))
        m.create_dataset("shape", data=np.array(mat.shape, dtype=np.int32))
        feats = m.create_group("features")
        feats.create_dataset("id",
                             data=np.array([s.encode() for s in feature_ids], dtype="|S20"))
        feats.create_dataset("name",
                             data=np.array([s.encode() for s in feature_names], dtype="|S20"))
        feats.create_dataset("feature_type",
                             data=np.array([s.encode() for s in feature_types], dtype="|S30"))
        feats.create_dataset("genome",
                             data=np.array([b"GRCh38"] * len(feature_ids), dtype="|S10"))
        feats.create_dataset("_all_tag_keys", data=np.array([b"genome"], dtype="|S10"))
    return cell_ids, gene_ids


def _write_cells_parquet(path: Path, cell_ids: list[str]) -> None:
    rng = np.random.default_rng(1)
    df = pd.DataFrame({
        "cell_id": cell_ids,
        "x_centroid": rng.uniform(0, 1000, size=N_CELLS).astype(np.float64),
        "y_centroid": rng.uniform(0, 1000, size=N_CELLS).astype(np.float64),
        "transcript_counts": rng.integers(50, 500, size=N_CELLS),
        "control_probe_counts": rng.integers(0, 5, size=N_CELLS),
        "genomic_control_counts": np.zeros(N_CELLS, dtype=np.int64),
        "control_codeword_counts": np.zeros(N_CELLS, dtype=np.int64),
        "unassigned_codeword_counts": np.zeros(N_CELLS, dtype=np.int64),
        "deprecated_codeword_counts": np.zeros(N_CELLS, dtype=np.int64),
        "total_counts": rng.integers(50, 500, size=N_CELLS),
        "cell_area": rng.uniform(20, 100, size=N_CELLS),
        "nucleus_area": rng.uniform(10, 50, size=N_CELLS),
        "nucleus_count": np.ones(N_CELLS, dtype=np.int64),
        "segmentation_method": ["Segmented by boundary stain"] * N_CELLS,
    })
    df.to_parquet(path, index=False)


def _write_polygon_parquet(path: Path, cell_ids: list[str], offset: float = 0.0) -> None:
    """Triangle polygons for cell_boundaries / nucleus_boundaries.

    The arboreto-style long-table schema: one row per vertex, columns
    ``cell_id``, ``vertex_x``, ``vertex_y``, ``label_id``. Each cell gets
    a 4-vertex closed triangle (the WKT-builder closes rings if needed,
    but Atera also ships them already closed).
    """
    rows = []
    for i, cid in enumerate(cell_ids):
        cx, cy = float(i * 10 + offset), float(i * 5 + offset)
        verts = [
            (cx,         cy),
            (cx + 5,     cy),
            (cx + 2.5,   cy + 5),
            (cx,         cy),
        ]
        for x, y in verts:
            rows.append((cid, np.float32(x), np.float32(y), 1))
    df = pd.DataFrame(rows, columns=["cell_id", "vertex_x", "vertex_y", "label_id"])
    df.to_parquet(path, index=False)


def _write_experiment_xenium(path: Path) -> dict:
    meta = {
        "major_version": 6,
        "minor_version": 1,
        "patch_version": 0,
        "run_name": "WTA Preview Test",
        "region_name": "Synthetic Atera Bundle",
        "preservation_method": "FFPE",
        "num_cells": N_CELLS,
        "transcripts_per_cell": 100,
        "panel_name": "Human WTA (synthetic)",
        "panel_organism": "Human",
        "chemistry_version": "Atera v1",
        "pixel_size": PIXEL_SIZE_UM,
        "instrument_sn": "test-instrument",
        "analysis_sw_version": "test-9.9.9",
        "experiment_uuid": "00000000-0000-0000-0000-000000000000",
    }
    path.write_text(json.dumps(meta, indent=2))
    return meta


def _write_morphology_channel_stubs(focus_dir: Path) -> list[str]:
    """Atera-named morphology channels. Empty TIFF stubs are fine — the
    test sets ``load_image=False`` so the loader never actually reads them.
    Their *filenames* are what the channel-key resolver matches against.
    """
    focus_dir.mkdir(parents=True, exist_ok=True)
    names = [
        "ch0000_dapi.ome.tif",
        "ch0001_atp1a1_cd45_e-cadherin.ome.tif",
        "ch0002_18s.ome.tif",
        "ch0003_alphasma_vimentin.ome.tif",
    ]
    for n in names:
        (focus_dir / n).write_bytes(b"")
    return names


@pytest.fixture
def atera_bundle(tmp_path: Path) -> dict:
    """A ``tmp_path / outs/`` directory that mirrors the real Atera schema
    and a sibling cell-groups CSV.
    """
    root = tmp_path / "outs"
    root.mkdir()
    cell_ids, gene_ids = _write_cell_feature_matrix_h5(root / "cell_feature_matrix.h5")
    _write_cells_parquet(root / "cells.parquet", cell_ids)
    _write_polygon_parquet(root / "cell_boundaries.parquet", cell_ids)
    # Nucleus polygons cover only the first 30 cells — exercises the
    # "fewer nuclei than cells" path that the reader handles with reindex.
    _write_polygon_parquet(root / "nucleus_boundaries.parquet",
                           cell_ids[:30], offset=0.5)
    meta = _write_experiment_xenium(root / "experiment.xenium")
    channels = _write_morphology_channel_stubs(root / "morphology_focus")

    # Sibling cell-groups CSV (some cells deliberately absent → NaN merge path).
    cg_path = tmp_path / "cell_groups.csv"
    rng = np.random.default_rng(2)
    n_labelled = N_CELLS - 3      # leave 3 unlabelled to exercise NaN handling
    groups = rng.choice(["TumorA", "TumorB", "Stroma", "Immune"], size=n_labelled)
    palette = {"TumorA": "#F943D2", "TumorB": "#9C27B0",
               "Stroma": "#FFC107", "Immune": "#1976D2"}
    pd.DataFrame({
        "cell_id": cell_ids[:n_labelled],
        "group": groups,
        "color": [palette[g] for g in groups],
    }).to_csv(cg_path, index=False)

    # H&E alignment matrix (3×3 affine, no header).
    affine_path = tmp_path / "he_alignment.csv"
    pd.DataFrame([[0.5, 0, 100.0],
                  [0, 0.5, 200.0],
                  [0, 0, 1]]).to_csv(affine_path, index=False, header=False)

    return {
        "root": root,
        "cell_groups_csv": cg_path,
        "he_alignment_csv": affine_path,
        "cell_ids": cell_ids,
        "gene_ids": gene_ids,
        "meta": meta,
        "channels": channels,
    }


# --------------------------------------------------------------------------- #
# read_atera: matrix / metadata / centroids / control filtering
# --------------------------------------------------------------------------- #

def test_read_atera_basic(atera_bundle) -> None:
    from omicverse.io.spatial import read_atera

    adata = read_atera(
        atera_bundle["root"],
        load_image=False,
        load_boundaries=True,
        load_nucleus_boundaries=True,
    )

    assert adata.n_obs == N_CELLS
    # Control probes (4) must be dropped — only Gene Expression survives.
    assert adata.n_vars == N_GENES, (
        f"control probes / codewords were not filtered: n_vars={adata.n_vars}"
    )
    assert all(v.startswith("GENE") for v in adata.var_names)

    # Centroids → obsm['spatial']
    assert "spatial" in adata.obsm
    assert adata.obsm["spatial"].shape == (N_CELLS, 2)
    assert adata.obsm["spatial"].dtype == np.float32

    # The centroid columns are *moved* out of obs into obsm.
    assert "x_centroid" not in adata.obs.columns
    assert "y_centroid" not in adata.obs.columns

    # Per-cell metadata from cells.parquet survives in obs.
    for col in ("transcript_counts", "cell_area", "nucleus_area",
                "nucleus_count", "segmentation_method"):
        assert col in adata.obs.columns

    # experiment.xenium → uns['spatial'][library]['metadata']
    library = "Synthetic Atera Bundle"  # = experiment.xenium["region_name"]
    assert library in adata.uns["spatial"]
    block = adata.uns["spatial"][library]
    assert block["metadata"]["pixel_size"] == PIXEL_SIZE_UM
    assert block["metadata"]["chemistry_version"] == "Atera v1"

    # Pixel-size driven scalefactor
    assert block["scalefactors"]["tissue_hires_scalef"] == pytest.approx(
        1.0 / PIXEL_SIZE_UM
    )

    # Without an image loaded, no 'hires' should be set.
    assert "hires" not in block["images"]

    # Discovered channel filenames are recorded even when load_image=False.
    assert block["metadata"]["morphology_channels"] == atera_bundle["channels"]

    # Reader stamps its type tag for downstream tools (geometry was loaded
    # successfully so it's the segmented variant).
    assert adata.uns["omicverse_io"]["type"] == "atera_seg"
    assert adata.uns["omicverse_io"]["library_id"] == library


# --------------------------------------------------------------------------- #
# Cell + nucleus polygons → WKT
# --------------------------------------------------------------------------- #

def test_read_atera_polygons(atera_bundle) -> None:
    from omicverse.io.spatial import read_atera

    adata = read_atera(
        atera_bundle["root"],
        load_image=False,
        load_boundaries=True,
        load_nucleus_boundaries=True,
    )

    # Every cell gets a cell polygon.
    assert "geometry" in adata.obs.columns
    geom = adata.obs["geometry"].astype(str)
    assert (geom != "").all()
    assert geom.iloc[0].startswith("POLYGON ((")

    # Nucleus polygons covered only first 30 cells; the remaining 2 are
    # left as empty strings by the reindex.
    assert "nucleus_geometry" in adata.obs.columns
    nuc = adata.obs["nucleus_geometry"].astype(str)
    assert (nuc != "").sum() == 30
    assert (nuc == "").sum() == N_CELLS - 30


def test_read_atera_disable_polygons(atera_bundle) -> None:
    from omicverse.io.spatial import read_atera

    adata = read_atera(
        atera_bundle["root"],
        load_image=False,
        load_boundaries=False,
        load_nucleus_boundaries=False,
    )
    assert "geometry" not in adata.obs.columns
    assert "nucleus_geometry" not in adata.obs.columns
    # When no segmentation is loaded the type tag drops the _seg suffix.
    assert adata.uns["omicverse_io"]["type"] == "atera"


# --------------------------------------------------------------------------- #
# cell_groups.csv merge — including the NaN-handling bug from the tutorial
# --------------------------------------------------------------------------- #

def test_read_atera_cell_groups_merge(atera_bundle) -> None:
    from omicverse.io.spatial import read_atera

    adata = read_atera(
        atera_bundle["root"],
        load_image=False,
        load_boundaries=False,
        load_nucleus_boundaries=False,
        cell_groups_csv=atera_bundle["cell_groups_csv"],
    )

    assert "cell_group" in adata.obs.columns
    assert "cell_group_color" in adata.obs.columns

    # 3 cells were left out of the CSV — they must arrive as NaN, not as
    # the string 'nan' (the latter broke the tutorial's `scatter(c=...)`).
    n_labelled = N_CELLS - 3
    assert adata.obs["cell_group"].notna().sum() == n_labelled
    assert adata.obs["cell_group_color"].isna().sum() == 3

    # Vendor colours are preserved verbatim, not e.g. coerced to ints.
    valid_colors = adata.obs["cell_group_color"].dropna().astype(str).unique()
    for c in valid_colors:
        assert c.startswith("#") and len(c) == 7


# --------------------------------------------------------------------------- #
# Channel-key resolver — semantic / substring / index
# --------------------------------------------------------------------------- #

def test_read_atera_channel_key_resolver_records_choice(atera_bundle, monkeypatch) -> None:
    """Every supported ``image_key`` form should select the right file.

    We intercept ``_load_pyramid_tiff`` so the test doesn't actually need
    a real pyramid TIFF — we just want to verify which file was picked.
    The reader records the chosen filename under
    ``scalefactors['morphology_channel']`` after a successful load.
    """
    from omicverse.io.spatial import _atera

    seen: list[Path] = []

    def fake_loader(path, max_dim=4096):
        seen.append(path)
        return np.zeros((4, 4), dtype=np.uint16), 1.0

    monkeypatch.setattr(_atera, "_load_pyramid_tiff", fake_loader)

    cases = {
        "dapi":     "ch0000_dapi.ome.tif",
        "boundary": "ch0001_atp1a1_cd45_e-cadherin.ome.tif",
        "rna":      "ch0002_18s.ome.tif",
        "stroma":   "ch0003_alphasma_vimentin.ome.tif",
        "cd45":     "ch0001_atp1a1_cd45_e-cadherin.ome.tif",  # substring
        "18s":      "ch0002_18s.ome.tif",                      # substring
        "2":        "ch0002_18s.ome.tif",                      # index-as-string
        "0":        "ch0000_dapi.ome.tif",
    }
    for key, expected_filename in cases.items():
        seen.clear()
        adata = _atera.read_atera(
            atera_bundle["root"],
            load_image=True,
            image_key=key,
            load_boundaries=False,
            load_nucleus_boundaries=False,
        )
        assert len(seen) == 1, f"image_key={key!r} did not trigger loader"
        assert seen[0].name == expected_filename, (
            f"image_key={key!r} picked {seen[0].name}, expected {expected_filename}"
        )
        sf = adata.uns["spatial"]["Synthetic Atera Bundle"]["scalefactors"]
        assert sf["morphology_channel"] == expected_filename


# --------------------------------------------------------------------------- #
# H&E alignment CSV → 3×3 affine
# --------------------------------------------------------------------------- #

def test_read_atera_he_alignment_loaded(atera_bundle, tmp_path, monkeypatch) -> None:
    """The H&E-image loader uses tifffile under the hood — the test stubs
    it so we don't need a real OME-TIFF, but we *do* exercise the
    alignment-CSV parsing and storage."""
    from omicverse.io.spatial import _atera

    monkeypatch.setattr(
        _atera, "_load_pyramid_tiff",
        lambda path, max_dim=4096: (np.zeros((4, 4), dtype=np.uint8), 1.0),
    )

    he_path = tmp_path / "he.ome.tif"
    he_path.write_bytes(b"")

    adata = _atera.read_atera(
        atera_bundle["root"],
        load_image=False,        # don't load morphology channel
        load_boundaries=False,
        load_nucleus_boundaries=False,
        he_image=he_path,
        he_alignment_csv=atera_bundle["he_alignment_csv"],
    )
    sf = adata.uns["spatial"]["Synthetic Atera Bundle"]["scalefactors"]
    assert "he_affine" in sf
    affine = sf["he_affine"]
    assert affine.shape == (3, 3)
    np.testing.assert_allclose(
        affine,
        np.array([[0.5, 0, 100.0],
                  [0, 0.5, 200.0],
                  [0, 0, 1]]),
    )
    assert sf["he_downsample"] == pytest.approx(1.0)
    assert "he" in adata.uns["spatial"]["Synthetic Atera Bundle"]["images"]
