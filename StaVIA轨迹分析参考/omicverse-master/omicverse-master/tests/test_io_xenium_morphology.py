"""Regression test for the V2 / Prime Xenium morphology loader (issue #708).

Real Xenium Prime ``outs.zip`` is many tens of GB, so this test builds a tiny
synthetic ``outs/`` directory that mirrors the V2 layout — including the
``morphology_focus/`` directory of per-channel OME-TIFF pyramids — and exercises
the loader end-to-end with ``load_image=True``.

What it covers:

- ``morphology_focus/morphology_focus_NNNN.ome.tif`` discovery (V2 / Prime
  layout). Pre-fix this case silently produced
  ``[Xenium] No morphology image loaded`` because tifffile's default
  ``_multifile=True`` followed the OME-XML cross-references between the four
  per-channel files and broke the pyramid-level walk.
- ``image_key='morphology_focus_0000'`` selecting the requested channel.
- Pyramid-level selection: reader picks the highest-resolution level whose
  largest dimension fits under ``image_max_dim`` and reports the correct
  downsample factor.
- Fallback when the requested channel is missing: the loader still returns
  another available channel rather than ``None``.
"""
from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp


N_CELLS = 12
N_GENES = 6
PIXEL_SIZE_UM = 0.2125
FULL_H, FULL_W = 800, 600  # full-res morphology image size
PYRAMID_DOWNSAMPLES = (1, 2, 4)  # → (800,600), (400,300), (200,150)


def _write_cell_feature_matrix_h5(path: Path) -> tuple[list[str], list[str]]:
    rng = np.random.default_rng(0)
    mat = sp.random(
        N_GENES, N_CELLS, density=0.6, format="csc",
        random_state=0,
        data_rvs=lambda size: rng.integers(1, 10, size=size),
    ).astype(np.int32)

    cell_ids = [f"cell{i:03d}" for i in range(N_CELLS)]
    gene_ids = [f"GENE{i:03d}" for i in range(N_GENES)]

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
                             data=np.array([s.encode() for s in gene_ids], dtype="|S20"))
        feats.create_dataset("name",
                             data=np.array([s.encode() for s in gene_ids], dtype="|S20"))
        feats.create_dataset("feature_type",
                             data=np.array([b"Gene Expression"] * N_GENES, dtype="|S30"))
        feats.create_dataset("genome",
                             data=np.array([b"GRCh38"] * N_GENES, dtype="|S10"))
        feats.create_dataset("_all_tag_keys", data=np.array([b"genome"], dtype="|S10"))
    return cell_ids, gene_ids


def _write_cells_parquet(path: Path, cell_ids: list[str]) -> None:
    rng = np.random.default_rng(1)
    df = pd.DataFrame({
        "cell_id": cell_ids,
        "x_centroid": rng.uniform(0, 100, size=N_CELLS).astype(np.float64),
        "y_centroid": rng.uniform(0, 100, size=N_CELLS).astype(np.float64),
        "transcript_counts": rng.integers(50, 500, size=N_CELLS),
        "cell_area": rng.uniform(20, 100, size=N_CELLS),
        "nucleus_area": rng.uniform(10, 50, size=N_CELLS),
    })
    df.to_parquet(path, index=False)


def _write_experiment_xenium(path: Path) -> dict:
    meta = {
        "major_version": 7,
        "minor_version": 0,
        "run_name": "Synthetic Xenium Prime",
        "region_name": "synthetic_v2",
        "panel_name": "Synthetic Prime Panel",
        "pixel_size": PIXEL_SIZE_UM,
    }
    path.write_text(json.dumps(meta, indent=2))
    return meta


def _write_v2_morphology_pyramid(out_path: Path, channel_idx: int) -> None:
    """Write a multi-resolution OME-TIFF with cross-file UUID refs (V2 layout).

    The four per-channel files reference one another in OME-XML — that is the
    key thing the fix needed to handle, because tifffile's default ``_multifile``
    behaviour follows those refs and merges the files into one logical 4-channel
    series, breaking the pyramid walk.
    """
    import tifffile

    rng = np.random.default_rng(100 + channel_idx)
    base = rng.integers(0, 255, size=(FULL_H, FULL_W), dtype=np.uint8)

    # Build pyramid (level 0 = full-res; subsequent levels halved).
    levels = [base]
    for ds in PYRAMID_DOWNSAMPLES[1:]:
        levels.append(base[::ds, ::ds].copy())

    # OME-XML can be omitted; tifffile generates a sensible default. The
    # default *does* include UUID-based references that link sibling files in
    # the same directory under the OME spec — exactly what triggers the bug.
    with tifffile.TiffWriter(out_path, ome=True, bigtiff=True) as tif:
        tif.write(
            levels[0],
            subifds=len(levels) - 1,
            tile=(256, 256),
            metadata={"axes": "YX"},
        )
        for lvl in levels[1:]:
            tif.write(lvl, subfiletype=1, tile=(256, 256))


@pytest.fixture
def xenium_v2_bundle(tmp_path: Path) -> dict:
    pytest.importorskip("tifffile")

    root = tmp_path / "outs"
    root.mkdir()
    cell_ids, gene_ids = _write_cell_feature_matrix_h5(root / "cell_feature_matrix.h5")
    _write_cells_parquet(root / "cells.parquet", cell_ids)
    meta = _write_experiment_xenium(root / "experiment.xenium")

    focus_dir = root / "morphology_focus"
    focus_dir.mkdir()
    channel_files = []
    for ci in range(4):
        cand = focus_dir / f"morphology_focus_{ci:04d}.ome.tif"
        _write_v2_morphology_pyramid(cand, ci)
        channel_files.append(cand)

    return {
        "root": root,
        "cell_ids": cell_ids,
        "gene_ids": gene_ids,
        "meta": meta,
        "channel_files": channel_files,
    }


def test_v2_default_image_key_loads_first_channel(xenium_v2_bundle) -> None:
    """``image_key='morphology_focus'`` (default) should pick up the V2 dir."""
    from omicverse.io.spatial import read_xenium

    adata = read_xenium(
        xenium_v2_bundle["root"],
        load_image=True,
        image_max_dim=512,  # forces selection of a downsampled level
        load_boundaries=False,
    )
    library_id = next(iter(adata.uns["spatial"]))
    img = adata.uns["spatial"][library_id]["images"].get("hires")
    assert img is not None, (
        "Pre-fix regression: V2 layout produced 'No morphology image loaded'."
    )
    # max_dim=512 should pick level-1 (downsample 1/2): (400, 300)
    assert max(img.shape) <= 512
    assert img.ndim == 2

    # tissue_hires_scalef must be rescaled by the chosen pyramid downsample.
    sf = adata.uns["spatial"][library_id]["scalefactors"]["tissue_hires_scalef"]
    expected = (1.0 / PIXEL_SIZE_UM) * (img.shape[0] / FULL_H)
    assert sf == pytest.approx(expected, rel=1e-6)


def test_v2_specific_channel_key_selects_that_channel(xenium_v2_bundle) -> None:
    """Issue #708 path: ``image_key='morphology_focus_0001'`` finds channel 1."""
    from omicverse.io.spatial._xenium import (
        _load_morphology_image,
        _morphology_candidates,
    )

    cands = _morphology_candidates(
        xenium_v2_bundle["root"], "morphology_focus_0001"
    )
    # The requested channel must be tried *first*.
    assert cands[0].name == "morphology_focus_0001.ome.tif"
    # All four V2 channels appear as fallbacks.
    assert {c.name for c in cands if c.name.startswith("morphology_focus_")} >= {
        f"morphology_focus_{i:04d}.ome.tif" for i in range(4)
    }

    loaded = _load_morphology_image(
        xenium_v2_bundle["root"], "morphology_focus_0001", max_dim=512
    )
    assert loaded is not None
    arr, downsample, src = loaded
    assert src.name == "morphology_focus_0001.ome.tif"
    assert arr.ndim == 2
    assert 0 < downsample <= 1.0


def test_v2_missing_specific_channel_falls_back(xenium_v2_bundle) -> None:
    """Asking for a non-existent channel must fall back to a sibling."""
    from omicverse.io.spatial._xenium import _load_morphology_image

    # Remove channel 2 to force fallback.
    (xenium_v2_bundle["root"] / "morphology_focus" /
     "morphology_focus_0002.ome.tif").unlink()

    loaded = _load_morphology_image(
        xenium_v2_bundle["root"], "morphology_focus_0002", max_dim=512
    )
    assert loaded is not None
    _, _, src = loaded
    assert src.name in {
        "morphology_focus_0000.ome.tif",
        "morphology_focus_0001.ome.tif",
        "morphology_focus_0003.ome.tif",
    }


def test_v1_layout_still_works(tmp_path: Path) -> None:
    """V1 ``morphology_focus.ome.tif`` at outs root must still load."""
    pytest.importorskip("tifffile")

    root = tmp_path / "outs"
    root.mkdir()
    cell_ids, _ = _write_cell_feature_matrix_h5(root / "cell_feature_matrix.h5")
    _write_cells_parquet(root / "cells.parquet", cell_ids)
    _write_experiment_xenium(root / "experiment.xenium")
    _write_v2_morphology_pyramid(root / "morphology_focus.ome.tif", 0)

    from omicverse.io.spatial import read_xenium

    adata = read_xenium(
        root, load_image=True, image_max_dim=512, load_boundaries=False
    )
    library_id = next(iter(adata.uns["spatial"]))
    assert adata.uns["spatial"][library_id]["images"].get("hires") is not None
