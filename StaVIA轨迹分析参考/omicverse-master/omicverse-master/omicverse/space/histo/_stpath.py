r"""STPath backend — generative foundation model (npj Digital Medicine 2025).

Loads weights from HuggingFace ``tlhuang/STPath`` and runs zero-shot
inference on GigaPath features extracted from the WSI tiles. Predicts
log1p expression for up to 38,984 genes across 17 organs.

Reference
---------
Huang et al., STPath: a generative foundation model for integrating spatial
transcriptomics and whole-slide images, npj Digital Medicine, 2025.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

import numpy as np

if TYPE_CHECKING:
    from anndata import AnnData
    from wsidata import WSIData


STPATH_HF_REPO = "tlhuang/STPath"
# Upstream HF naming: README still says `stpath.pkl`, repo actually
# ships `stfm.pth` (the original training script's filename).
STPATH_WEIGHT_FILE = "stfm.pth"
STPATH_GENE_VOCAB_URL = (
    "https://raw.githubusercontent.com/"
    "Graph-and-Geometric-Learning/STPath/main/utils_data/symbol2ensembl.json"
)
STPATH_GITHUB_URL = "https://github.com/Graph-and-Geometric-Learning/STPath.git"


def _default_cache_dir() -> Path:
    return Path(
        os.environ.get(
            "OV_HISTO_CACHE",
            Path.home() / ".cache" / "omicverse" / "histo",
        )
    )


def _ensure_stpath_repo(cache_dir: Path) -> Path:
    """Auto-clone the STPath python package into ``cache_dir`` and return it."""
    repo_dir = cache_dir / "STPath"
    if not repo_dir.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        import subprocess
        subprocess.check_call(
            ["git", "clone", "--depth", "1", STPATH_GITHUB_URL, str(repo_dir)],
        )
    if str(repo_dir) not in sys.path:
        sys.path.insert(0, str(repo_dir))
    return repo_dir


def _download_stpath_weight(cache_dir: Path, token: str | None = None) -> Path:
    from huggingface_hub import hf_hub_download
    path = hf_hub_download(
        repo_id=STPATH_HF_REPO,
        filename=STPATH_WEIGHT_FILE,
        cache_dir=str(cache_dir / "hf"),
        token=token,
    )
    return Path(path)


def _gene_vocab(cache_dir: Path) -> Path:
    p = cache_dir / "STPath" / "utils_data" / "symbol2ensembl.json"
    if not p.exists():
        import urllib.request
        p.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(STPATH_GENE_VOCAB_URL, p)
    return p


def predict_stpath(
    wsi: "WSIData",
    *,
    tile_key: str = "tiles",
    key_added: str | None = None,
    genes: Sequence[str] | None = None,
    organ: str | None = None,
    tech: str | None = "Visium",
    feature_key: str | None = None,
    fm_backbone: str = "gigapath",
    weight_path: str | Path | None = None,
    fm_weight_path: str | Path | None = None,
    hf_token: str | None = None,
    device: str | None = None,
    cache_dir: str | Path | None = None,
) -> "AnnData":
    """Run STPath zero-shot inference on a tiled WSI.

    Parameters
    ----------
    organ
        One of the 17 STPath organ tokens (e.g. ``'Breast'``, ``'Kidney'``,
        ``'Lung'``, ``'Colon'``, ``'Liver'``…). ``None`` falls back to
        ``'Others'`` — works but loses the organ prior.
    tech
        Sequencing platform token. Default ``'Visium'``.
    """
    import anndata as ad
    import torch

    cache = Path(cache_dir) if cache_dir is not None else _default_cache_dir()
    cache.mkdir(parents=True, exist_ok=True)

    # 1. Resolve / extract GigaPath features for tiles.
    feat_table_key = f"{feature_key or fm_backbone}_{tile_key}"
    if feat_table_key not in wsi.tables:
        from ._embed import embed
        embed(wsi, model=fm_backbone, tile_key=tile_key, key_added=fm_backbone,
              model_path=fm_weight_path, token=hf_token, device=device)
        feat_table_key = f"{fm_backbone}_{tile_key}"
    feat_adata = wsi.tables[feat_table_key]
    img_features = np.asarray(feat_adata.X, dtype=np.float32)
    if img_features.shape[1] != 1536:
        raise ValueError(
            f"STPath expects 1536-d GigaPath features; got "
            f"{img_features.shape[1]}-d from '{feat_table_key}'. "
            f"Run ov.space.histo.embed(wsi, model='gigapath') first."
        )

    # Tile centroids — pull from the tile GeoDataFrame.
    tiles_gdf = wsi.shapes[tile_key]
    centroids = np.stack(
        [tiles_gdf.geometry.centroid.x.to_numpy(),
         tiles_gdf.geometry.centroid.y.to_numpy()],
        axis=1,
    ).astype(np.float32)

    # 2. Bring STPath into scope and load weights.
    _ensure_stpath_repo(cache)
    from stpath.app.pipeline.inference import STPathInference

    if weight_path is None:
        weight_path = _download_stpath_weight(cache, token=hf_token)
    else:
        weight_path = Path(weight_path)
    vocab_path = _gene_vocab(cache)
    dev = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
    agent = STPathInference(
        gene_voc_path=str(vocab_path),
        model_weight_path=str(weight_path),
        device=dev,
    )

    # 3. Inference.
    pred = agent.inference(
        coords=centroids,
        img_features=img_features,
        organ_type=organ,
        tech_type=tech,
        save_gene_names=list(genes) if genes is not None else None,
    )

    # 4. Repackage into a WSIData-friendly table.
    out = ad.AnnData(
        X=np.asarray(pred.X, dtype=np.float32),
        var=pred.var.copy(),
        obs=feat_adata.obs.copy(),
    )
    out.obsm["spatial"] = centroids
    out.uns["histo"] = {
        "method": "stpath",
        "fm_backbone": fm_backbone,
        "organ": organ,
        "tech": tech,
    }

    out_key = f"{key_added or 'stpath'}_{tile_key}"
    wsi.tables[out_key] = out
    return out
