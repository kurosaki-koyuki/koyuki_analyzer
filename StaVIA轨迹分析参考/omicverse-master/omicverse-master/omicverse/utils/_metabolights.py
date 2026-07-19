r"""Metabolights public-study loader.

Turn a Metabolights accession (e.g. ``"MTBLS1"``) into a
``samples × metabolites`` AnnData in one call, without having to
hand-merge the sample sheet with the MAF (Metabolite Assignment File)
every time.

The EBI-hosted ISA-Tab layout per study is:

- ``s_<ID>.txt`` — sample sheet (samples × factor-value columns)
- ``a_<ID>_*.txt`` — assay sheet (samples × instrument metadata)
- ``m_<ID>_*_maf.tsv`` — MAF: rows = metabolites, columns = sample
  intensities + annotation columns (``metabolite_identification``,
  ``chemical_formula``, ``smiles``, ``chemical_shift``, ``taxid``, ...)

``load_metabolights`` fetches ``s_*.txt`` and ``m_*.tsv`` from the
public FTP, caches them under a user-chosen directory, and returns
the transposed AnnData with obs merged from the sample sheet.
"""
from __future__ import annotations

import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from anndata import AnnData

from .._registry import register_function


_BASE = "https://ftp.ebi.ac.uk/pub/databases/metabolights/studies/public"


class _FileLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.files: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href":
                    self.files.append(v)


def _list_study_files(study_id: str, timeout: float = 20.0) -> list[str]:
    """Parse the FTP directory index to list every file in the study."""
    url = f"{_BASE}/{study_id}/"
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        html = resp.read().decode("utf-8", errors="replace")
    parser = _FileLinks()
    parser.feed(html)
    return parser.files


def _pick_maf(files: list[str]) -> str:
    """Pick the MAF filename from a study directory listing.

    Most studies ship exactly one ``m_<ID>_*_maf.tsv``; if there are
    multiple (rare) we take the first one to preserve determinism and
    leave the choice to the caller via ``maf_name=``.
    """
    mafs = [f for f in files if f.startswith("m_") and f.endswith("_maf.tsv")]
    if not mafs:
        raise FileNotFoundError(
            "No MAF (m_*_maf.tsv) found in the study directory."
        )
    return sorted(mafs)[0]


def _pick_sample_sheet(files: list[str], study_id: str) -> str:
    """Pick the sample-sheet filename (``s_<ID>.txt``)."""
    # Case-insensitive match: Metabolights studies are inconsistent
    # (MTBLS1 uses `s_MTBLS1.txt` but some use lowercase).
    target = f"s_{study_id}.txt"
    for f in files:
        if f.lower() == target.lower():
            return f
    # Fall back to any `s_*.txt` if the study has a non-standard name.
    candidates = [f for f in files if f.lower().startswith("s_")
                  and f.lower().endswith(".txt")]
    if not candidates:
        raise FileNotFoundError("No sample sheet (s_*.txt) found.")
    return candidates[0]


def _download(url: str, path: Path, timeout: float = 60.0) -> None:
    req = urllib.request.Request(
        url, headers={"User-Agent": "omicverse/utils.load_metabolights"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    path.write_bytes(data)


@register_function(
    aliases=[
        "load_metabolights",
        "metabolights_loader",
        "读取metabolights",
    ],
    category="utils",
    description=(
        "Download a public Metabolights study (sample sheet + MAF) from "
        "ftp.ebi.ac.uk and return a samples × metabolites AnnData ready "
        "for ov.metabol. Handles the ISA-Tab layout, NaN metabolite "
        "names (falls back on chemical_shift), and optional factor "
        "column renaming to 'group'."
    ),
    examples=[
        "adata = ov.utils.load_metabolights('MTBLS1', "
        "group_col='Factor Value[Metabolic syndrome]')",
    ],
    related=[
        "metabol.read_metaboanalyst",
        "datasets.download_data",
    ],
)
def load_metabolights(
    study_id: str,
    *,
    group_col: Optional[str] = None,
    cache_dir: str | Path = "metabolights_cache",
    maf_name: Optional[str] = None,
    sample_name_col: str = "Sample Name",
    refresh: bool = False,
) -> AnnData:
    """Load a Metabolights study into a samples × metabolites AnnData.

    Parameters
    ----------
    study_id
        Metabolights accession, e.g. ``"MTBLS1"``. The study must be
        under the public mirror at ``ftp.ebi.ac.uk/pub/databases/
        metabolights/studies/public``.
    group_col
        Column in the sample sheet to use as the primary phenotype
        label. When given, the column is renamed to ``"group"`` in
        ``adata.obs`` to match the convention the rest of
        ``ov.metabol`` expects (``differential(group_col="group")``,
        ``roc_feature(group_col="group")``, ...). Common choices:
        ``"Factor Value[<name>]"``.
    cache_dir
        Directory to cache downloaded files. Default
        ``./metabolights_cache/``. Re-runs reuse cached files unless
        ``refresh=True``.
    maf_name
        Explicit MAF filename. Default: first alphabetical
        ``m_*_maf.tsv`` in the directory listing. Override when a
        study ships multiple MAFs (e.g. positive vs. negative mode).
    sample_name_col
        Column in the sample sheet carrying the assay-side sample
        identifiers. Default ``"Sample Name"`` — works for every
        study that follows the ISA-Tab standard.
    refresh
        Force re-download even if the cached file exists. Use when
        Metabolights updates a study version in place.

    Returns
    -------
    AnnData
        ``obs`` carries every column of the sample sheet plus a
        derived ``group`` column (if ``group_col`` was supplied).
        ``var`` carries ``metabolite_identification`` (filled with
        ``unknown_shift_<ppm>`` for NMR rows that lack a named
        identification) plus ``chemical_formula`` and ``smiles`` when
        available.
        ``uns['metabolights'] = {'study_id', 'maf_name',
        'sample_sheet'}`` records provenance.
    """
    cache = Path(cache_dir).expanduser()
    cache.mkdir(parents=True, exist_ok=True)

    listing: Optional[list[str]] = None
    if maf_name is None:
        listing = _list_study_files(study_id)
        maf_name = _pick_maf(listing)
    sample_sheet_name = _pick_sample_sheet(
        listing if listing is not None else _list_study_files(study_id),
        study_id,
    )

    for fname in (sample_sheet_name, maf_name):
        dest = cache / fname
        if dest.exists() and not refresh:
            continue
        _download(f"{_BASE}/{study_id}/{fname}", dest)

    sample_path = cache / sample_sheet_name
    maf_path = cache / maf_name
    s_df = pd.read_csv(sample_path, sep="\t")
    m_df = pd.read_csv(maf_path, sep="\t")

    if sample_name_col not in s_df.columns:
        raise KeyError(
            f"{sample_name_col!r} not in sample sheet. "
            f"Available: {list(s_df.columns)[:10]}..."
        )
    # The MAF carries one column per sample. Sample column names are
    # exactly the values in ``s_df[sample_name_col]`` — intersect the
    # two to filter out annotation columns (like "database_identifier").
    sample_id_set = set(s_df[sample_name_col].astype(str))
    sample_cols = [c for c in m_df.columns
                   if isinstance(c, str) and c in sample_id_set]
    if not sample_cols:
        raise ValueError(
            f"No columns in the MAF matched sample IDs from the sample "
            f"sheet. First 5 MAF columns: {list(m_df.columns)[:5]}; "
            f"first 5 sample IDs: {list(s_df[sample_name_col])[:5]}."
        )

    # Metabolite names: prefer metabolite_identification, fall back on
    # chemical_shift (NMR), then on the row index.
    mid = m_df.get(
        "metabolite_identification", pd.Series(index=m_df.index, dtype=object)
    )
    shift = m_df.get(
        "chemical_shift", pd.Series(index=m_df.index, dtype=object)
    )
    var_names = []
    for i, (name, sh) in enumerate(zip(mid.fillna(""), shift.fillna(""))):
        if isinstance(name, str) and name:
            var_names.append(name)
        elif sh != "":
            var_names.append(f"unknown_shift_{sh}")
        else:
            var_names.append(f"feature_{i}")

    # obs: sample-sheet rows indexed by sample ID
    obs = s_df.set_index(sample_name_col).loc[sample_cols].copy()
    if group_col is not None:
        if group_col not in obs.columns:
            raise KeyError(
                f"group_col={group_col!r} not in sample sheet. "
                f"Available Factor Value columns: "
                f"{[c for c in obs.columns if 'Factor' in c]}"
            )
        obs = obs.rename(columns={group_col: "group"})
        obs["group"] = obs["group"].astype(str)

    var = pd.DataFrame(
        {
            "metabolite_identification": var_names,
        },
        index=[f"m{i}" for i in range(len(m_df))],
    )
    for col in ("chemical_formula", "smiles"):
        if col in m_df.columns:
            var[col] = m_df[col].values

    X = m_df[sample_cols].T.astype(float).values
    adata = AnnData(X=X, obs=obs, var=var)
    adata.uns["metabolights"] = {
        "study_id": str(study_id),
        "maf_name": str(maf_name),
        "sample_sheet": str(sample_sheet_name),
        "cache_dir": str(cache),
    }
    return adata
