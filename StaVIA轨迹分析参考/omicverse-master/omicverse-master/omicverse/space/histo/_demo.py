r"""Convenience loaders for 10x Visium demo datasets used by HE-zoo.

Two adjacent sections from the same patient/block are pre-wired:

* **Section 1** (``load_breast(section=1)``, the default) — used as the
  reference / training slide across all HE-zoo tutorials.
* **Section 2** (``load_breast(section=2)``) — the *held-out* slide for
  cross-slide evaluation. Same patient, adjacent physical section, so
  it shares anatomy and staining batch but is a genuinely new H&E from
  the model's point of view.

Both ship the full-resolution H&E (~1.7 GB each), Space Ranger
``spatial/`` outputs, and the filtered count matrix. Everything caches
under ``$OV_HISTO_CACHE/he_zoo/{visium_breast,visium_breast_s2}`` and
only re-downloads missing assets.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from ..._registry import register_function

if TYPE_CHECKING:
    from anndata import AnnData
    from wsidata import WSIData


_BASE_TMPL = (
    "https://cf.10xgenomics.com/samples/spatial-exp/1.1.0/"
    "V1_Breast_Cancer_Block_A_Section_{section}/"
)
_FILE_TMPL = {
    "counts": "V1_Breast_Cancer_Block_A_Section_{section}_filtered_feature_bc_matrix.h5",
    "spatial": "V1_Breast_Cancer_Block_A_Section_{section}_spatial.tar.gz",
    "image": "V1_Breast_Cancer_Block_A_Section_{section}_image.tif",
}
_DIR_TMPL = {1: "visium_breast", 2: "visium_breast_s2"}


def _files_for(section: int) -> dict[str, str]:
    return {k: v.format(section=section) for k, v in _FILE_TMPL.items()}


def _base_for(section: int) -> str:
    return _BASE_TMPL.format(section=section)


def _default_dir(section: int = 1) -> Path:
    base = os.environ.get("OV_HISTO_CACHE", Path.home() / ".cache" / "omicverse" / "histo")
    return Path(base) / "he_zoo" / _DIR_TMPL[section]


def _download(target: Path, url: str) -> None:
    import urllib.request
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists() or target.stat().st_size < 1024:
        print(f"  downloading {target.name} …", flush=True)
        urllib.request.urlretrieve(url, target)


@register_function(
    aliases=["下载乳腺癌Demo", "download_breast", "Visium乳腺数据下载"],
    category="space",
    description="Download a Visium Breast Cancer Block A section (1 or 2) from 10x Genomics into the on-disk cache. Section 1 is the demo / training slide; Section 2 is the adjacent held-out slide used in HE-zoo cross-slide evaluation.",
    examples=[
        "ov.space.histo.download_breast(section=1)",
        "ov.space.histo.download_breast(section=2, cache_dir='/scratch/heatlas')",
    ],
    related=["space.histo.load_breast", "space.histo.read_visium_with_image"],
)
def download_breast(
    cache_dir: str | Path | None = None,
    *,
    section: int = 1,
    include_image: bool = True,
) -> Path:
    """Download a Visium Breast Cancer Block A section.

    Parameters
    ----------
    section
        ``1`` (default) or ``2``. Section 1 is the demo / training
        slide used across HE-zoo; Section 2 is the held-out slide.
    """
    if section not in (1, 2):
        raise ValueError(f"section must be 1 or 2, got {section!r}")
    dst = Path(cache_dir) if cache_dir is not None else _default_dir(section)
    dst.mkdir(parents=True, exist_ok=True)
    files = _files_for(section)
    base = _base_for(section)
    _download(dst / files["counts"], base + files["counts"])
    _download(dst / files["spatial"], base + files["spatial"])
    if not (dst / "spatial").is_dir():
        import tarfile
        with tarfile.open(dst / files["spatial"]) as tar:
            tar.extractall(dst)
    if include_image:
        _download(dst / files["image"], base + files["image"])
    return dst


@register_function(
    aliases=["加载乳腺癌Demo", "load_breast", "load_demo", "Visium乳腺数据"],
    category="space",
    description="Download a Visium Breast Cancer Block A section and return (adata, wsi) — the canonical demo dataset for HE-zoo tutorials. section=1 is the training slide; section=2 is the adjacent held-out slide for cross-slide evaluation.",
    examples=[
        "adata, wsi = ov.space.histo.load_breast()                # section 1",
        "adata2, wsi2 = ov.space.histo.load_breast(section=2)     # held-out",
    ],
    related=["space.histo.download_breast", "space.histo.read_visium_with_image", "space.histo.predict_expression"],
)
def load_breast(
    cache_dir: str | Path | None = None,
    *,
    section: int = 1,
    include_image: bool = True,
) -> "tuple[AnnData, WSIData | None]":
    """Download a Visium Breast Cancer Block A section and return ``(adata, wsi)``.

    Parameters
    ----------
    section
        ``1`` (default) or ``2``. Use Section 2 as the held-out slide
        for cross-slide evaluation across HE-zoo tutorials.

    Examples
    --------
    >>> import omicverse as ov
    >>> adata, wsi = ov.space.histo.load_breast()              # section 1
    >>> adata2, wsi2 = ov.space.histo.load_breast(section=2)   # held-out
    """
    from ._io import read_visium_with_image
    base = download_breast(cache_dir=cache_dir, section=section,
                           include_image=include_image)
    files = _files_for(section)
    return read_visium_with_image(
        base,
        image_path=(base / files["image"]) if include_image else None,
        count_file=files["counts"],
    )
