"""Readers for the four bulk-proteomics file formats omicverse supports
out of the box: MaxQuant ``proteinGroups.txt``, DIA-NN
``report.pg_matrix.tsv``, FragPipe ``combined_protein.tsv``, and Olink
long NPX TSV/CSV.

Every reader returns an ``AnnData`` with the omicverse convention:
``obs = samples`` (rows), ``var = proteins`` (columns), and ``X``
populated with **raw intensities** (NOT log-transformed). Downstream
``ov.protein.normalize(..., log2=True)`` is responsible for the
transform.

Per-protein metadata (peptide count, sequence coverage, gene names,
UniProt IDs, …) lands in ``adata.var`` so DEqMS / proDA / MSstats can
read it directly via ``count_var=`` etc.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

import numpy as np
import pandas as pd

try:
    from anndata import AnnData
except ImportError:  # pragma: no cover
    AnnData = None  # type: ignore

from .._registry import register_function


PathLike = Union[str, Path]


def _require_anndata() -> None:
    if AnnData is None:
        raise ImportError(
            "anndata is required for omicverse.protein.io — "
            "`pip install anndata`."
        )


def _intensity_columns(
    df: pd.DataFrame,
    pattern: str,
) -> tuple[list[str], list[str]]:
    """Return (column names, sample names) where columns match ``pattern``.

    The sample name is captured by group(1) of the regex.
    """
    cre = re.compile(pattern)
    keep_cols, sample_names = [], []
    for col in df.columns:
        m = cre.fullmatch(str(col))
        if m is not None:
            keep_cols.append(col)
            sample_names.append(m.group(1) if m.groups() else str(col))
    return keep_cols, sample_names


# --------------------------------------------------------------------------- #
# MaxQuant                                                                    #
# --------------------------------------------------------------------------- #

@register_function(
    aliases=["read_maxquant", "maxquant", "蛋白组maxquant", "蛋白MaxQuant"],
    category="io",
    description=(
        "Read a MaxQuant ``proteinGroups.txt`` file into an AnnData "
        "(samples × proteins). ``sample_pattern`` selects which intensity "
        "columns become samples (default = ``LFQ intensity <sample>``). "
        "Reverse / contaminant / only-identified-by-site rows are dropped. "
        "Per-protein metadata (peptides, sequence coverage, gene names, "
        "Majority protein IDs) lands in ``adata.var``."
    ),
    produces={"obs": ["sample"], "var": ["peptides", "Gene_names", "Protein_IDs"]},
    auto_fix="none",
    examples=[
        "adata = ov.protein.read_maxquant('proteinGroups.txt')",
        "adata = ov.protein.read_maxquant('pG.txt', sample_pattern=r'Intensity (.+)')",
    ],
)
def read_maxquant(
    path: PathLike,
    *,
    sample_pattern: str = r"LFQ intensity (.+)",
    protein_id_col: str = "Majority protein IDs",
    drop_contaminants: bool = True,
    drop_reverse: bool = True,
    drop_only_by_site: bool = True,
    peptides_col: str = "Peptides",
    gene_names_col: str = "Gene names",
) -> "AnnData":
    """Load MaxQuant ``proteinGroups.txt`` into AnnData."""
    _require_anndata()
    df = pd.read_csv(path, sep="\t", low_memory=False)

    # Standard MaxQuant junk-row filters.
    mask = pd.Series(True, index=df.index)
    if drop_reverse and "Reverse" in df.columns:
        mask &= df["Reverse"].fillna("") != "+"
    if drop_contaminants:
        col = "Potential contaminant" if "Potential contaminant" in df.columns else "Contaminant"
        if col in df.columns:
            mask &= df[col].fillna("") != "+"
    if drop_only_by_site and "Only identified by site" in df.columns:
        mask &= df["Only identified by site"].fillna("") != "+"
    df = df[mask].reset_index(drop=True)

    cols, sample_names = _intensity_columns(df, sample_pattern)
    if not cols:
        raise ValueError(
            f"No columns match {sample_pattern!r}. Available columns: "
            f"{list(df.columns)[:20]}…"
        )
    # X is samples × proteins.
    X = df[cols].to_numpy(dtype=float).T
    # 0 → NaN: MaxQuant uses 0 for missing in LFQ intensities.
    X[X == 0] = np.nan

    var_cols = {}
    if protein_id_col in df.columns:
        var_cols["Protein_IDs"] = df[protein_id_col].astype(str).values
    if peptides_col in df.columns:
        var_cols["peptides"] = pd.to_numeric(df[peptides_col], errors="coerce").values
    if gene_names_col in df.columns:
        var_cols["Gene_names"] = df[gene_names_col].astype(str).values
    if "Sequence coverage [%]" in df.columns:
        var_cols["seq_coverage"] = pd.to_numeric(
            df["Sequence coverage [%]"], errors="coerce",
        ).values
    if "id" in df.columns:
        var_cols["mq_id"] = df["id"].astype(str).values

    var_index = (
        var_cols["Gene_names"] if "Gene_names" in var_cols else df.index.astype(str).values
    )
    # Disambiguate duplicate gene names.
    var_index = pd.Index(var_index).astype(str)
    if var_index.duplicated().any():
        seen: dict[str, int] = {}
        new = []
        for v in var_index:
            seen[v] = seen.get(v, 0) + 1
            new.append(f"{v}_{seen[v]}" if seen[v] > 1 else v)
        var_index = pd.Index(new)
    var = pd.DataFrame(var_cols, index=var_index)

    obs = pd.DataFrame(index=pd.Index(sample_names, name="sample"))
    adata = AnnData(X=X, obs=obs, var=var)
    adata.uns["source"] = "MaxQuant"
    adata.uns["source_path"] = str(path)
    return adata


# --------------------------------------------------------------------------- #
# DIA-NN                                                                      #
# --------------------------------------------------------------------------- #

@register_function(
    aliases=["read_diann", "diann", "DIA-NN"],
    category="io",
    description=(
        "Read a DIA-NN ``report.pg_matrix.tsv`` (or main ``report.tsv``) "
        "into an AnnData (samples × proteins). For pg_matrix the wide "
        "format is parsed directly; for the long ``report.tsv`` the "
        "matrix is pivoted on ``Protein.Group`` × ``File.Name`` using "
        "``PG.MaxLFQ``."
    ),
    produces={"obs": ["sample"], "var": ["Protein_Group", "Gene_names"]},
    auto_fix="none",
    examples=[
        "adata = ov.protein.read_diann('report.pg_matrix.tsv')",
        "adata = ov.protein.read_diann('report.tsv', quant_col='PG.MaxLFQ')",
    ],
)
def read_diann(
    path: PathLike,
    *,
    quant_col: str = "PG.MaxLFQ",
    protein_col: str = "Protein.Group",
    sample_col: str = "File.Name",
) -> "AnnData":
    """Load a DIA-NN report into AnnData."""
    _require_anndata()
    df = pd.read_csv(path, sep="\t", low_memory=False)

    # Long vs wide detection: pg_matrix is wide (one column per sample).
    if {protein_col, quant_col, sample_col}.issubset(df.columns):
        wide = df.pivot_table(
            index=protein_col, columns=sample_col, values=quant_col,
            aggfunc="first",
        )
        protein_ids = wide.index.astype(str)
        sample_names = wide.columns.astype(str)
        X = wide.to_numpy(dtype=float).T
        var_cols = {"Protein_Group": protein_ids.values}
    else:
        # Wide pg_matrix: protein ID(s) in first ~5 columns, then sample columns.
        meta_cols = [c for c in df.columns
                     if c in ("Protein.Group", "Protein.Ids", "Protein.Names",
                              "Genes", "First.Protein.Description")]
        sample_cols = [c for c in df.columns if c not in meta_cols]
        if not sample_cols:
            raise ValueError(
                f"Could not determine sample columns in {path}; "
                f"columns={list(df.columns)[:10]}…"
            )
        protein_ids = df.get("Protein.Group", df[meta_cols[0]]).astype(str).values
        X = df[sample_cols].to_numpy(dtype=float).T
        sample_names = sample_cols
        var_cols = {"Protein_Group": protein_ids}
        if "Genes" in df.columns:
            var_cols["Gene_names"] = df["Genes"].astype(str).values
        if "First.Protein.Description" in df.columns:
            var_cols["protein_desc"] = df["First.Protein.Description"].astype(str).values

    # DIA-NN already drops 0s but emit NaN-safe just in case.
    X[X == 0] = np.nan

    var_index = (
        var_cols.get("Gene_names")
        if "Gene_names" in var_cols
        else var_cols["Protein_Group"]
    )
    var_index = pd.Index(pd.Series(var_index).astype(str))
    if var_index.duplicated().any():
        seen: dict[str, int] = {}
        new = []
        for v in var_index:
            seen[v] = seen.get(v, 0) + 1
            new.append(f"{v}_{seen[v]}" if seen[v] > 1 else v)
        var_index = pd.Index(new)
    var = pd.DataFrame(var_cols, index=var_index)
    obs = pd.DataFrame(index=pd.Index([str(s) for s in sample_names], name="sample"))
    adata = AnnData(X=X, obs=obs, var=var)
    adata.uns["source"] = "DIA-NN"
    adata.uns["source_path"] = str(path)
    return adata


# --------------------------------------------------------------------------- #
# FragPipe                                                                    #
# --------------------------------------------------------------------------- #

@register_function(
    aliases=["read_fragpipe", "fragpipe", "MSFragger"],
    category="io",
    description=(
        "Read a FragPipe ``combined_protein.tsv`` into an AnnData "
        "(samples × proteins). Intensity columns are taken from "
        "``<sample> Intensity`` by default."
    ),
    produces={"obs": ["sample"], "var": ["Protein", "Gene", "Combined.Total.Peptides"]},
    auto_fix="none",
    examples=["adata = ov.protein.read_fragpipe('combined_protein.tsv')"],
)
def read_fragpipe(
    path: PathLike,
    *,
    sample_pattern: str = r"(.+) Intensity",
) -> "AnnData":
    """Load FragPipe ``combined_protein.tsv`` into AnnData."""
    _require_anndata()
    df = pd.read_csv(path, sep="\t", low_memory=False)
    cols, sample_names = _intensity_columns(df, sample_pattern)
    if not cols:
        raise ValueError(
            f"No FragPipe Intensity columns match {sample_pattern!r}."
        )
    X = df[cols].to_numpy(dtype=float).T
    X[X == 0] = np.nan
    var_cols: dict[str, np.ndarray] = {}
    for key in ("Protein", "Protein ID", "Entry Name", "Gene",
                "Combined Total Peptides", "Description"):
        if key in df.columns:
            var_cols[key.replace(" ", "_")] = df[key].astype(str).values
    var_index = (
        var_cols.get("Gene") if "Gene" in var_cols else df.index.astype(str).values
    )
    var_index = pd.Index(pd.Series(var_index).astype(str))
    var = pd.DataFrame(var_cols, index=var_index)
    obs = pd.DataFrame(index=pd.Index(sample_names, name="sample"))
    adata = AnnData(X=X, obs=obs, var=var)
    adata.uns["source"] = "FragPipe"
    adata.uns["source_path"] = str(path)
    return adata


# --------------------------------------------------------------------------- #
# Olink NPX (long-format TSV / CSV)                                           #
# --------------------------------------------------------------------------- #

@register_function(
    aliases=["read_olink_npx", "olink", "NPX"],
    category="io",
    description=(
        "Read an Olink NPX TSV / CSV (long-format with columns "
        "``SampleID``, ``OlinkID`` (or ``Assay``), ``NPX``) into an "
        "AnnData (samples × proteins). NPX values are kept on the "
        "original log2 scale; no further transform needed."
    ),
    produces={"obs": ["sample"], "var": ["OlinkID", "Assay", "Panel", "UniProt"]},
    auto_fix="none",
    examples=[
        "adata = ov.protein.read_olink_npx('olink_npx.csv')",
    ],
)
def read_olink_npx(
    path: PathLike,
    *,
    sample_col: str = "SampleID",
    protein_col: str = "OlinkID",
    value_col: str = "NPX",
    sep: Optional[str] = None,
) -> "AnnData":
    """Load Olink long-format NPX file into AnnData."""
    _require_anndata()
    sep = sep or ("\t" if str(path).lower().endswith(".tsv") else ",")
    df = pd.read_csv(path, sep=sep, low_memory=False)

    if protein_col not in df.columns and "Assay" in df.columns:
        protein_col = "Assay"
    for c in (sample_col, protein_col, value_col):
        if c not in df.columns:
            raise ValueError(
                f"Column {c!r} missing from {path}. Found: {list(df.columns)[:10]}…"
            )

    wide = df.pivot_table(
        index=sample_col, columns=protein_col, values=value_col,
        aggfunc="mean",
    )
    X = wide.to_numpy(dtype=float)

    # Per-protein metadata: take the first non-null row per protein.
    var_keys = [c for c in ("Assay", "UniProt", "Panel", "LOD", "OlinkID")
                if c in df.columns]
    var = (
        df.drop_duplicates(subset=protein_col)
          .set_index(protein_col)[var_keys]
          .reindex(wide.columns)
    )
    var.index = pd.Index(var.index.astype(str), name="protein")
    obs = pd.DataFrame(index=pd.Index(wide.index.astype(str), name="sample"))
    adata = AnnData(X=X, obs=obs, var=var)
    adata.uns["source"] = "Olink_NPX"
    adata.uns["source_path"] = str(path)
    return adata


# --------------------------------------------------------------------------- #
# Generic wide-table reader                                                   #
# --------------------------------------------------------------------------- #

@register_function(
    aliases=["read_wide", "protein_read_wide"],
    category="io",
    description=(
        "Read a generic wide protein × sample TSV / CSV into AnnData. "
        "Use this for already-processed matrices (e.g. supplementary "
        "tables) that don't come from a known vendor format."
    ),
    auto_fix="none",
    examples=["adata = ov.protein.read_wide('matrix.tsv', protein_col='gene')"],
)
def read_wide(
    path: PathLike,
    *,
    protein_col: Optional[str] = None,
    sep: Optional[str] = None,
    na_values: Optional[list[str]] = None,
) -> "AnnData":
    """Generic protein × sample table → AnnData (samples × proteins)."""
    _require_anndata()
    sep = sep or ("\t" if str(path).lower().endswith((".tsv", ".txt")) else ",")
    df = pd.read_csv(path, sep=sep, na_values=na_values or ["NA", ""])
    if protein_col is None:
        # Assume first column holds protein IDs.
        protein_col = df.columns[0]
    df = df.set_index(protein_col)
    X = df.to_numpy(dtype=float).T  # samples × proteins
    obs = pd.DataFrame(index=pd.Index(df.columns.astype(str), name="sample"))
    var = pd.DataFrame(index=pd.Index(df.index.astype(str), name="protein"))
    adata = AnnData(X=X, obs=obs, var=var)
    adata.uns["source"] = "wide_table"
    adata.uns["source_path"] = str(path)
    return adata
