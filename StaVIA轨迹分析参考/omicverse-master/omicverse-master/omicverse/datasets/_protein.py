"""Real published proteomics datasets for the ``ov.protein`` tutorials.

Each loader downloads a dataset asset from the ``omicverse-data`` GitHub
release (``proteomics-v1``) on first use, caches it under ``dir``, and
returns it ready for the ``ov.protein`` workflow.

| Loader | Returns | Source |
|---|---|---|
| :func:`protein_pxd000022` | AnnData (samples × proteins) | ProteomeXchange PXD000022 |
| :func:`protein_pxd000279` | AnnData (samples × proteins) | ProteomeXchange PXD000279 (MaxQuant) |
| :func:`protein_pxd000438` | AnnData (samples × proteins) | ProteomeXchange PXD000438 |
| :func:`protein_dda_spikein` | DataFrame (MSstats long) | MSstats ``DDARawData`` |
| :func:`protein_dia` | DataFrame (MSstats long) | MSstats ``DIARawData`` |
| :func:`protein_olink` | DataFrame (long NPX) | OlinkAnalyze ``npx_data1`` |

All datasets are real, published proteomics data redistributed from the
open-source Bioconductor / CRAN packages imputeLCMD, MSstats and
OlinkAnalyze.
"""
from __future__ import annotations

import gzip
import os
from typing import TYPE_CHECKING

import pandas as pd

from .._registry import register_function
from ._datasets import download_data

if TYPE_CHECKING:  # pragma: no cover
    from anndata import AnnData

_RELEASE = (
    "https://github.com/omicverse/omicverse-data/releases/download/proteomics-v1"
)


def _fetch(asset: str, dir: str) -> str:
    """Download ``asset`` from the proteomics-v1 release; return local path."""
    return download_data(f"{_RELEASE}/{asset}", file_path=asset, dir=dir)


@register_function(
    aliases=["protein_pxd000022", "pxd000022", "蛋白组数据PXD000022"],
    category="datasets",
    description=(
        "Real label-free LC-MS/MS proteomics dataset ProteomeXchange "
        "PXD000022 — 660 proteins × 6 samples, two groups (MB vs MT, "
        "3 replicates each), ~40% left-censored (MNAR) missing values. "
        "Returned as an AnnData (samples × proteins, raw intensities, "
        "NaN = missing) ready for the ``ov.protein`` bulk-LFQ pipeline."
    ),
    examples=["adata = ov.datasets.protein_pxd000022()"],
)
def protein_pxd000022(dir: str = "./data") -> "AnnData":
    """Load the PXD000022 label-free proteomics dataset (real, 2-group)."""
    import anndata as ad
    return ad.read_h5ad(_fetch("protein_pxd000022.h5ad", dir))


@register_function(
    aliases=["protein_pxd000279", "pxd000279", "蛋白组benchmark数据"],
    category="datasets",
    description=(
        "Real label-free MaxQuant proteomics benchmark ProteomeXchange "
        "PXD000279 — the spike-in dataset used by the DEqMS vignette. "
        "6507 proteins × 6 samples, two groups H vs L (HeLa background "
        "constant, E. coli spiked at a 3:1 ratio, 3 replicates each). "
        "``var['peptides']`` holds the real per-protein peptide count "
        "(needed by DEqMS); ``var['species']`` / ``var['is_spikein']`` "
        "give the ground truth — E. coli proteins are truly "
        "differential, human proteins are not. Returned as an AnnData "
        "(samples × proteins, raw LFQ intensities, NaN = missing)."
    ),
    examples=["adata = ov.datasets.protein_pxd000279()"],
)
def protein_pxd000279(dir: str = "./data") -> "AnnData":
    """Load the PXD000279 MaxQuant label-free benchmark (real, spike-in truth)."""
    import anndata as ad
    return ad.read_h5ad(_fetch("protein_pxd000279.h5ad", dir))


@register_function(
    aliases=["protein_pxd000438", "pxd000438", "蛋白组数据PXD000438"],
    category="datasets",
    description=(
        "Real label-free LC-MS/MS proteomics dataset ProteomeXchange "
        "PXD000438 — 3709 proteins × 12 samples, four groups (3 "
        "replicates each), ~41% left-censored missing values. A larger, "
        "missingness-rich dataset for the imputation deep-dive. Returned "
        "as an AnnData (samples × proteins, raw intensities, NaN = "
        "missing)."
    ),
    examples=["adata = ov.datasets.protein_pxd000438()"],
)
def protein_pxd000438(dir: str = "./data") -> "AnnData":
    """Load the PXD000438 label-free proteomics dataset (real, 4-group)."""
    import anndata as ad
    return ad.read_h5ad(_fetch("protein_pxd000438.h5ad", dir))


@register_function(
    aliases=["protein_dda_spikein", "msstats_dda", "蛋白组DDA数据"],
    category="datasets",
    description=(
        "Real controlled spike-in label-free DDA dataset (MSstats "
        "``DDARawData``) — feature/peptide-level intensities in MSstats "
        "long format (ProteinName / PeptideSequence / Run / Condition / "
        "Intensity …). Returned as a pandas DataFrame; feed to "
        "``ov.protein`` peptide→protein summarization or ``pymsstats``."
    ),
    examples=["df = ov.datasets.protein_dda_spikein()"],
)
def protein_dda_spikein(dir: str = "./data") -> pd.DataFrame:
    """Load the MSstats DDA spike-in dataset (real, MSstats long format)."""
    return pd.read_csv(_fetch("protein_msstats_dda.csv.gz", dir))


@register_function(
    aliases=["protein_dia", "msstats_dia", "蛋白组DIA数据"],
    category="datasets",
    description=(
        "Real label-free DIA dataset (MSstats ``DIARawData``) — a "
        "S. Pyogenes group comparison (Strep 0% vs 10%), feature-level "
        "MSstats long format. Returned as a pandas DataFrame."
    ),
    examples=["df = ov.datasets.protein_dia()"],
)
def protein_dia(dir: str = "./data") -> pd.DataFrame:
    """Load the MSstats DIA dataset (real, MSstats long format)."""
    return pd.read_csv(_fetch("protein_msstats_dia.csv.gz", dir))


@register_function(
    aliases=["protein_olink", "olink_npx_data", "蛋白组Olink数据"],
    category="datasets",
    description=(
        "Real Olink Explore NPX dataset (OlinkAnalyze ``npx_data1``) — "
        "long-format NPX with SampleID / OlinkID / Assay / NPX / "
        "Treatment / Site / Subject, a real bridging study. Returned as "
        "a pandas DataFrame; load into an AnnData with "
        "``ov.protein.read_olink_npx`` or analyse with ``pyolinkanalyze``."
    ),
    examples=["df = ov.datasets.protein_olink()"],
)
def protein_olink(dir: str = "./data") -> pd.DataFrame:
    """Load the OlinkAnalyze NPX dataset (real Olink Explore data)."""
    return pd.read_csv(_fetch("protein_olink_npx.csv.gz", dir))
