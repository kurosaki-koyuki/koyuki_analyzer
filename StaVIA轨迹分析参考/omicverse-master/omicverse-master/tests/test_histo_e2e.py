"""End-to-end smoke script for ov.space.histo on the Visium Breast Cancer slide.

This is a **manual integration script**, not a unit test. It downloads
~1.7 GB of public Visium data on first use and exercises each backend
end-to-end on a real H&E. Run from a host with at least one CUDA GPU,
the omicdev env active, and an HF token with GigaPath access:

    OV_HISTO_CACHE=/scratch/path/to/cache \\
        python tests/test_histo_e2e.py [backend]

Pass a backend name to run only one of: ``embed``, ``hest_fm``, ``stpath``,
``stflow``, ``istar``. Default is to run them all in sequence.

The module top auto-skips pytest collection so CI doesn't try to import
it (it depends on hardcoded paths + gated HF weights).
"""
from __future__ import annotations

import os
import sys
import time
import warnings
from pathlib import Path

# Make sure `pytest` skips this file — it's a manual integration
# script, not a unit test. The collect_ignore hook below is honoured by
# pytest when set as a module-level attribute.
import pytest
collect_ignore_glob = ["*"]
pytestmark = pytest.mark.skip(reason="manual integration script; not a unit test")

warnings.filterwarnings("ignore")

DATA_DIR = Path(os.environ.get(
    "OV_HISTO_DEMO_DIR",
    "/scratch/users/steorra/cache/he_zoo/visium_breast",
))
VISIUM_PATH = DATA_DIR  # Spaceranger 1.1.0 layout: filtered_feature_bc_matrix.h5 + spatial/
HE_IMAGE = DATA_DIR / "V1_Breast_Cancer_Block_A_Section_1_image.tif"
CACHE = Path(os.environ.get("OV_HISTO_CACHE", Path.home() / ".cache" / "omicverse" / "histo"))
SCRATCH = Path(os.environ.get(
    "OV_HISTO_SCRATCH",
    str(CACHE / "he_zoo" / "runs"),
))


def load_inputs():
    import omicverse as ov
    print("[step] read_visium_with_image", flush=True)
    adata, wsi = ov.space.histo.read_visium_with_image(
        VISIUM_PATH,
        image_path=HE_IMAGE,
        count_file="V1_Breast_Cancer_Block_A_Section_1_filtered_feature_bc_matrix.h5",
    )
    print(f"  adata: {adata.shape}, wsi.shape: {wsi.properties.shape}, mpp: {wsi.properties.mpp}", flush=True)
    return adata, wsi


def stage_tiles(wsi, mpp=0.5, tile_px=224):
    import omicverse as ov
    if "tiles" not in wsi.shapes:
        print("[step] tile (find_tissues + tile_tissues)", flush=True)
        ov.space.histo.tile(wsi, tile_px=tile_px, mpp=mpp)
    print(f"  tiles: {len(wsi.shapes['tiles'])}", flush=True)


def stage_embed(wsi, backbone):
    import omicverse as ov
    key = f"{backbone}_tiles"
    if key in wsi.tables:
        return
    print(f"[step] embed model={backbone}", flush=True)
    ov.space.histo.embed(wsi, model=backbone, batch_size=16, num_workers=0)


def run_hest_fm(adata, wsi, genes=("EPCAM", "CDH1", "KRT8", "ESR1", "ERBB2")):
    import omicverse as ov
    print("\n=== HEST-FM ===", flush=True)
    t0 = time.time()
    pred = ov.space.histo.predict_expression(
        wsi, method="hest_fm",
        reference=adata,
        genes=list(genes),
        fm_backbone="ctranspath",
    )
    dt = time.time() - t0
    print(f"  pred: {pred.shape} in {dt:.1f}s", flush=True)
    print(f"  pred head: {pred.X[:3, :3]}", flush=True)
    return pred


def run_stpath(adata, wsi, genes=("EPCAM", "CDH1", "KRT8", "ESR1", "ERBB2", "ACTA2", "VIM")):
    import omicverse as ov
    print("\n=== STPath (zero-shot) ===", flush=True)
    t0 = time.time()
    pred = ov.space.histo.predict_expression(
        wsi, method="stpath",
        organ="Breast",
        tech="Visium",
        genes=list(genes),
        fm_backbone="gigapath",
    )
    dt = time.time() - t0
    print(f"  pred: {pred.shape} in {dt:.1f}s", flush=True)
    print(f"  genes: {list(pred.var_names)}", flush=True)
    return pred


def run_stflow(adata, wsi):
    import omicverse as ov
    print("\n=== STFlow (fine-tune on reference) ===", flush=True)
    t0 = time.time()
    pred = ov.space.histo.predict_expression(
        wsi, method="stflow",
        reference=adata,
        n_epochs=80,
        fm_backbone="gigapath",
    )
    dt = time.time() - t0
    print(f"  pred: {pred.shape} in {dt:.1f}s", flush=True)
    return pred


def run_istar(adata, wsi):
    import omicverse as ov
    print("\n=== iStar (super-resolve) ===", flush=True)
    t0 = time.time()
    pred = ov.space.histo.super_resolve(
        adata, wsi=wsi, method="istar",
        epochs=80, n_top_genes=50,
        cache_dir=CACHE,
    )
    dt = time.time() - t0
    print(f"  pred: {pred.shape} in {dt:.1f}s", flush=True)
    return pred


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    adata, wsi = load_inputs()
    stage_tiles(wsi)

    if target in ("embed", "all", "hest_fm", "stpath", "stflow"):
        # CTransPath for HEST-FM; GigaPath for STPath / STFlow.
        if target in ("embed", "all", "hest_fm"):
            stage_embed(wsi, "ctranspath")
        if target in ("embed", "all", "stpath", "stflow"):
            stage_embed(wsi, "gigapath")

    if target in ("hest_fm", "all"):
        run_hest_fm(adata, wsi)
    if target in ("stpath", "all"):
        run_stpath(adata, wsi)
    if target in ("stflow", "all"):
        run_stflow(adata, wsi)
    if target in ("istar", "all"):
        run_istar(adata, wsi)

    print("\n[OK]", flush=True)


if __name__ == "__main__":
    SCRATCH.mkdir(parents=True, exist_ok=True)
    main()
