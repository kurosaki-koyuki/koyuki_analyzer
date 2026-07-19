r"""Tile-level pathology foundation-model embedding.

Thin convenience wrapper around :func:`lazyslide.tl.feature_extraction`.
LazySlide already registers UNI/UNI2/CONCH/Virchow/Virchow2/GigaPath/
H-Optimus/Phikon/CTransPath/Hibou/Midnight; this layer adds:

* an ``available_backbones`` helper that filters the LazySlide registry
  down to backbones useful for HE→ST prediction;
* a default ``key_added`` convention that matches what the prediction
  backends (STPath, HEST-FM) expect.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..._registry import register_function

if TYPE_CHECKING:
    from wsidata import WSIData

# Pathology FMs that we recommend for HE→ST prediction. Models that only
# do segmentation/QC/zero-shot classification are filtered out.
_RECOMMENDED_BACKBONES = (
    "gigapath",       # STPath / STFlow default
    "uni2", "uni",    # HEST-Bench standard
    "virchow2", "virchow",
    "conch_vision", "conch_v1.5",
    "h-optimus-1", "h-optimus-0", "h0-mini",
    "phikonv2", "phikon",
    "ctranspath",
    "hibou-l", "hibou-b",
    "midnight",
    "chief",
)


@register_function(
    aliases=["FM列表", "available_backbones", "backbones"],
    category="space",
    description="Return the curated list of pathology foundation models supported by ov.space.histo.embed (filtered from LazySlide's model registry to those useful for HE→ST prediction).",
    examples=[
        "ov.space.histo.available_backbones()",
    ],
    related=["space.histo.embed"],
)
def available_backbones() -> list[str]:
    """Return the curated list of pathology FMs recommended for HE→ST."""
    try:
        from lazyslide.models import list_models
        registered = set(list_models())
    except ImportError:
        return list(_RECOMMENDED_BACKBONES)
    return [name for name in _RECOMMENDED_BACKBONES if name in registered]


@register_function(
    aliases=["提取特征", "embed", "FM提特征", "wsi_embed", "病理特征"],
    category="space",
    description="Extract per-tile pathology FM embeddings on a WSIData (wraps lazyslide.tl.feature_extraction). Writes features as wsi.tables[{model}_{tile_key}] (AnnData with one row per tile). Supports UNI/UNI2/CONCH/Virchow/GigaPath/CTransPath/Hibou/etc.",
    examples=[
        "ov.space.histo.embed(wsi, model='ctranspath', batch_size=16)",
        "ov.space.histo.embed(wsi, model='gigapath', token='hf_...')",
        "ov.space.histo.embed(wsi, model='uni2', model_path='/path/to/uni2.pth')",
    ],
    related=["space.histo.tile", "space.histo.available_backbones", "space.histo.predict_expression"],
)
def embed(
    wsi: "WSIData",
    model: str = "gigapath",
    *,
    tile_key: str = "tiles",
    key_added: str | None = None,
    model_path: str | None = None,
    batch_size: int = 32,
    num_workers: int = 0,
    device: str | None = None,
    amp: bool = True,
    token: str | None = None,
    pbar: bool = True,
    **kwargs,
) -> "WSIData":
    """Extract per-tile foundation-model embeddings.

    Writes the embedding AnnData into
    ``wsi.tables['{key_added}_{tile_key}']`` (default ``'<model>_tiles'``)
    where ``X`` is the (N_tiles × D) feature matrix and ``obs`` carries
    tile barcodes matching ``wsi.shapes[tile_key]``.

    Parameters
    ----------
    model
        Backbone name; one of :func:`available_backbones`.
    model_path
        Path to a pre-staged backbone weight file (e.g. CTransPath
        ``.pth``, GigaPath ``pytorch_model.bin``). Forwarded to LazySlide
        as ``model_path`` to skip the HuggingFace download.
    token
        HuggingFace token for gated models (UNI2/CONCH/Virchow2/GigaPath).
        Falls back to ``HUGGING_FACE_HUB_TOKEN`` env var or the cached
        ``~/.cache/huggingface/token``.
    """
    import lazyslide as zs
    import os
    from pathlib import Path
    import anndata as ad

    # NOTE: LazySlide only applies its `{name}_{tile_key}` naming when
    # ``key_added`` is ``None``. If the caller hands us a short name we
    # expand it ourselves to keep the table-naming contract.
    if key_added is None:
        lazyslide_key = None
        effective_table_key = f"{model}_{tile_key}"
    else:
        lazyslide_key = key_added if key_added.endswith(f"_{tile_key}") else f"{key_added}_{tile_key}"
        effective_table_key = lazyslide_key

    # Disk cache so notebook re-runs and parameter sweeps don't pay for
    # the embed twice. Keyed by slide stem + tile count + FM name so
    # different tile grids on the same WSI live alongside each other.
    cache_root = Path(os.environ.get("OV_HISTO_CACHE",
                                     Path.home() / ".cache" / "omicverse" / "histo")) / "tile_features"
    cache_root.mkdir(parents=True, exist_ok=True)
    slide_stem = Path(getattr(wsi.reader, "file", "wsi")).stem
    n_tiles = len(wsi.shapes[tile_key])
    cache_path = cache_root / f"{model}_{slide_stem}_{tile_key}_n{n_tiles}.h5ad"
    if cache_path.exists():
        wsi.tables[effective_table_key] = ad.read_h5ad(cache_path)
        return wsi

    zs.tl.feature_extraction(
        wsi,
        model=model,
        model_path=model_path,
        tile_key=tile_key,
        key_added=lazyslide_key,
        batch_size=batch_size,
        num_workers=num_workers,
        device=device,
        amp=amp,
        token=token,
        pbar=pbar,
        **kwargs,
    )
    try:
        wsi.tables[effective_table_key].write_h5ad(cache_path)
    except Exception:
        pass
    return wsi
