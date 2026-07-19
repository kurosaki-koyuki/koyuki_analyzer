r"""iStar backend — super-resolve a paired (Visium, H&E) sample.

Vendored copy lives at ``omicverse.external.istar``. iStar's
``run.sh``-style pipeline is wrapped here as a single Python call:

1. stage ``cnts.tsv``, ``locs-raw.tsv``, ``he-raw.jpg``,
   ``pixel-size-raw.txt`` and ``radius-raw.txt`` into a working directory
   using the same on-disk format the original scripts expect;
2. extract HIPT features (``extract_features.py``);
3. infer tissue mask (``get_mask.py``);
4. train per-slide head and predict at sub-spot resolution
   (``impute.py``);
5. read ``imputed.tsv`` back into an ``AnnData`` indexed by sub-spot
   pixels and gene symbols.

Reference
---------
Zhang et al., Inferring super-resolution tissue architecture by
integrating spatial transcriptomics with histology, Nature Biotechnology,
2024. https://doi.org/10.1038/s41587-023-02019-9
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from anndata import AnnData
    from wsidata import WSIData


# The upstream Box mirror has rotted; fetch HIPT checkpoints from the
# mahmoodlab/HIPT GitHub LFS media endpoint instead.
ISTAR_HIPT_SRC_256 = (
    "https://media.githubusercontent.com/media/mahmoodlab/HIPT/master/"
    "HIPT_4K/Checkpoints/vit256_small_dino.pth"
)
ISTAR_HIPT_SRC_4K = (
    "https://media.githubusercontent.com/media/mahmoodlab/HIPT/master/"
    "HIPT_4K/Checkpoints/vit4k_xs_dino.pth"
)


def _vendored_istar_dir() -> Path:
    here = Path(__file__).resolve().parents[2]
    p = here / "external" / "istar"
    if not p.exists():
        raise FileNotFoundError(
            f"vendored iStar source not found at {p}. "
            "Re-install omicverse or contact the maintainers."
        )
    return p


def _default_cache_dir() -> Path:
    return Path(
        os.environ.get(
            "OV_HISTO_CACHE",
            Path.home() / ".cache" / "omicverse" / "histo",
        )
    )


def _ensure_hipt_checkpoints(
    istar_dir: Path,
    cache_dir: Path | None = None,
    *,
    hipt256_path: str | Path | None = None,
    hipt4k_path: str | Path | None = None,
) -> None:
    """Make sure HIPT checkpoints exist next to iStar.

    Looks for ``vit256_small_dino.pth`` / ``vit4k_xs_dino.pth`` in:
    (1) the explicit ``hipt256_path`` / ``hipt4k_path`` overrides;
    (2) ``cache_dir/istar_checkpoints``;
    (3) downloads them from the mahmoodlab/HIPT LFS endpoint when missing.

    Symlinks the final files into ``istar_dir/checkpoints/`` so the
    vendored scripts can find them by their hard-coded relative path.
    """
    ck = istar_dir / "checkpoints"
    ck.mkdir(exist_ok=True)
    user_cache = (cache_dir or _default_cache_dir()) / "istar_checkpoints"
    user_cache.mkdir(parents=True, exist_ok=True)
    overrides = {
        "vit256_small_dino.pth": hipt256_path,
        "vit4k_xs_dino.pth": hipt4k_path,
    }
    sources = {
        "vit256_small_dino.pth": ISTAR_HIPT_SRC_256,
        "vit4k_xs_dino.pth": ISTAR_HIPT_SRC_4K,
    }
    import urllib.request
    for name, url in sources.items():
        if overrides[name] is not None:
            resolved = Path(overrides[name]).resolve()
        else:
            cached = user_cache / name
            if not cached.exists() or cached.stat().st_size < 1_000_000:
                urllib.request.urlretrieve(url, cached)
            resolved = cached.resolve()
        dst = ck / name
        if dst.is_symlink() or dst.exists():
            dst.unlink()
        dst.symlink_to(resolved)


def _stage_inputs(
    adata: "AnnData",
    he_image_path: Path,
    work_dir: Path,
    *,
    spot_diameter_fullres: float,
) -> None:
    """Write iStar-format inputs into ``work_dir``."""
    work_dir.mkdir(parents=True, exist_ok=True)

    # cnts.tsv — rows are spots, columns are genes
    X = adata.X
    if hasattr(X, "toarray"):
        X = X.toarray()
    cnts = pd.DataFrame(X, index=adata.obs_names, columns=adata.var_names)
    cnts.index.name = ""
    cnts.to_csv(work_dir / "cnts.tsv", sep="\t")

    # locs-raw.tsv — spot pixel coordinates at full resolution
    if "spatial" not in adata.obsm:
        raise KeyError("adata.obsm['spatial'] missing — must be Visium.")
    coords = np.asarray(adata.obsm["spatial"], dtype=float)
    locs = pd.DataFrame({"x": coords[:, 0], "y": coords[:, 1]}, index=adata.obs_names)
    locs.index.name = ""
    locs.to_csv(work_dir / "locs-raw.tsv", sep="\t")

    # radius and pixel size for raw image
    radius_px = float(spot_diameter_fullres) / 2.0
    (work_dir / "radius-raw.txt").write_text(f"{radius_px}\n")

    library_id = next(iter(adata.uns["spatial"]))
    sf = adata.uns["spatial"][library_id]["scalefactors"]
    # Visium spots are 55 µm in diameter; convert px to µm/px
    mpp = 55.0 / float(sf.get("spot_diameter_fullres", 100.0))
    (work_dir / "pixel-size-raw.txt").write_text(f"{mpp}\n")

    # Symlink the H&E image
    he_dst = work_dir / "he-raw.jpg"
    if not he_dst.exists():
        try:
            he_dst.symlink_to(he_image_path.resolve())
        except OSError:
            shutil.copy2(he_image_path, he_dst)


def _run_step(script: str, args: list[str], cwd: Path) -> None:
    cmd = [sys.executable, str(cwd / script), *args]
    subprocess.run(cmd, cwd=str(cwd), check=True)


def super_resolve_istar(
    adata: "AnnData",
    *,
    wsi: "WSIData | None" = None,
    he_image: str | Path | None = None,
    factor: int = 8,
    pixel_size: float = 0.5,
    n_top_genes: int = 1000,
    genes: Sequence[str] | None = None,
    epochs: int = 400,
    device: str | None = None,
    cache_dir: str | Path | None = None,
    hipt256_path: str | Path | None = None,
    hipt4k_path: str | Path | None = None,
    keep_workdir: bool = True,
) -> "AnnData":
    """Run iStar end-to-end on a paired Visium + H&E sample.

    Parameters
    ----------
    pixel_size
        Target microns-per-pixel for the super-resolved grid. ``0.5`` is
        the iStar default (~near-single-cell on a 0.5 µm Visium image).
        ``factor`` is currently used only to derive ``pixel_size`` when
        the caller does not pass one explicitly.
    n_top_genes
        Number of highly variable genes to impute. Ignored when ``genes``
        is provided.
    genes
        Specific gene panel to impute. Written to ``gene-names.txt`` so
        iStar uses it instead of the HVG fallback.
    epochs
        Training epochs for iStar's per-slide head.
    """
    import anndata as ad
    import torch

    if he_image is None and wsi is not None:
        he_image = wsi.reader.file
    if he_image is None:
        he_image = (
            (adata.uns.get("histo") or {}).get("wsi_path") if adata.uns else None
        )
    if he_image is None:
        raise ValueError(
            "iStar needs a full-resolution H&E image. Pass `he_image=` or "
            "wrap the Visium output with ov.space.histo.read_visium_with_image."
        )
    he_image = Path(he_image)

    library_id = next(iter(adata.uns["spatial"]))
    sf = adata.uns["spatial"][library_id]["scalefactors"]
    spot_diameter = float(sf.get("spot_diameter_fullres", 100.0))

    dev = device or ("cuda" if torch.cuda.is_available() else "cpu")

    cache = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
    work_dir = cache / "istar_runs" / f"{he_image.stem}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # If a prior run already imputed the same gene panel, return the
    # cached result without retraining.
    super_dir = work_dir / "cnts-super"
    cached_genes = sorted(p.stem for p in super_dir.glob("*.pickle")) if super_dir.exists() else []
    requested = list(genes) if genes is not None else None
    if cached_genes and (requested is None or set(requested).issubset(cached_genes)):
        out = _gather_istar_pickles(work_dir)
        out.uns["histo"] = {
            "method": "istar",
            "pixel_size": pixel_size,
            "factor": factor,
            "work_dir": str(work_dir),
            "cache_hit": True,
        }
        return out

    istar_dir = _vendored_istar_dir()
    _ensure_hipt_checkpoints(
        istar_dir, cache_dir=cache,
        hipt256_path=hipt256_path, hipt4k_path=hipt4k_path,
    )
    _stage_inputs(
        adata, he_image, work_dir,
        spot_diameter_fullres=spot_diameter,
    )
    (work_dir / "pixel-size.txt").write_text(f"{pixel_size}\n")

    if genes is not None:
        (work_dir / "gene-names.txt").write_text("\n".join(genes) + "\n")

    prefix_arg = str(work_dir) + "/"

    # Run the iStar pipeline. Each script is silent on success.
    _run_step("rescale.py",     [prefix_arg, "--image"],            istar_dir)
    _run_step("preprocess.py",  [prefix_arg, "--image"],            istar_dir)
    _run_step("extract_features.py", [prefix_arg, f"--device={dev}"], istar_dir)
    _run_step(
        "get_mask.py",
        [str(work_dir / "embeddings-hist.pickle"),
         str(work_dir / "mask-small.png")],
        istar_dir,
    )
    if genes is None:
        _run_step(
            "select_genes.py",
            [f"--n-top={n_top_genes}",
             str(work_dir / "cnts.tsv"),
             str(work_dir / "gene-names.txt")],
            istar_dir,
        )
    _run_step("rescale.py", [prefix_arg, "--locs", "--radius"], istar_dir)
    _run_step(
        "impute.py",
        [prefix_arg, f"--epochs={epochs}", f"--device={dev}"],
        istar_dir,
    )
    # iStar writes one ``cnts-super/<gene>.pickle`` per gene — a 2D float32
    # array of imputed log1p expression at the super-resolution grid.
    # We skip aggregate_imputed.py / reorganize_imputed.py because those
    # depend on a separate clustering step and are not core to the
    # super-resolution output.
    out = _gather_istar_pickles(work_dir)
    out.uns["histo"] = {
        "method": "istar",
        "pixel_size": pixel_size,
        "factor": factor,
        "work_dir": str(work_dir),
    }
    return out


def _gather_istar_pickles(work_dir: Path) -> "AnnData":
    """Stack per-gene iStar pickles into a tissue-masked AnnData."""
    import anndata as ad
    import pickle
    from PIL import Image

    super_dir = work_dir / "cnts-super"
    files = sorted(super_dir.glob("*.pickle"))
    if not files:
        raise FileNotFoundError(f"iStar produced no super-resolved tables in {super_dir}.")

    genes = [f.stem for f in files]
    arrays = []
    for f in files:
        with open(f, "rb") as fh:
            arrays.append(pickle.load(fh))
    stack = np.stack(arrays, axis=-1).astype(np.float32)   # [H, W, G]

    mask_path = work_dir / "mask-small.png"
    if mask_path.exists():
        mask_img = np.asarray(Image.open(mask_path).convert("L")) > 0
        # The mask resolution may differ from the super-res grid; resize.
        if mask_img.shape != stack.shape[:2]:
            mask_img = np.asarray(
                Image.fromarray(mask_img.astype(np.uint8) * 255)
                .resize((stack.shape[1], stack.shape[0]), Image.NEAREST)
            ) > 0
    else:
        mask_img = np.any(stack != 0, axis=-1)

    yy, xx = np.nonzero(mask_img)
    X = stack[yy, xx]
    obs = pd.DataFrame(
        {"x": xx, "y": yy},
        index=[f"px_{y}_{x}" for y, x in zip(yy, xx)],
    )
    var = pd.DataFrame(index=pd.Index(genes, name="gene"))
    out = ad.AnnData(X=X, obs=obs, var=var)
    out.obsm["spatial"] = np.stack([xx, yy], axis=1).astype(np.float32)
    return out
