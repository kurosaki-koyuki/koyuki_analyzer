from __future__ import annotations

import glob
import logging
import os

import pandas as pd

logger = logging.getLogger(__name__)


def _read_sumstats(fh, alleles=False, dropna=False):
    """Parse GWAS summary statistics."""

    compression = None
    if str(fh).endswith("gz"):
        compression = "gzip"
    elif str(fh).endswith("bz2"):
        compression = "bz2"

    dtype_dict = {"SNP": str, "Z": float, "N": float, "A1": str, "A2": str}
    usecols = ["SNP", "Z", "N"]
    if alleles:
        usecols += ["A1", "A2"]

    sumstats = pd.read_csv(
        fh,
        sep=r"\s+",
        na_values=".",
        usecols=usecols,
        dtype=dtype_dict,
        compression=compression,
    )
    if dropna:
        sumstats = sumstats.dropna(how="any")
    return sumstats.drop_duplicates(subset="SNP")


def _read_chr_files(base_path, suffix, expected_count=22):
    """Read chromosome files using glob pattern matching."""

    file_pattern = f"{base_path}[1-9]*{suffix}*"
    all_files = glob.glob(file_pattern)
    chr_files = []
    for file_path in all_files:
        try:
            file_name = os.path.basename(file_path)
            base_name = os.path.basename(str(base_path))
            chr_part = file_name.replace(base_name, "").split(suffix)[0]
            chr_num = int(chr_part)
            if 1 <= chr_num <= expected_count:
                chr_files.append((chr_num, file_path))
        except (ValueError, IndexError):
            continue

    chr_files.sort()
    return [file_path for _, file_path in chr_files]


def _read_file(file_path):
    """Read a file based on its extension."""

    if file_path.endswith(".feather"):
        return pd.read_feather(file_path)
    if file_path.endswith(".parquet"):
        return pd.read_parquet(file_path)
    if file_path.endswith(".gz"):
        return pd.read_csv(file_path, compression="gzip", sep="\t")
    if file_path.endswith(".bz2"):
        return pd.read_csv(file_path, compression="bz2", sep="\t")
    return pd.read_csv(file_path, sep="\t")


def _read_ref_ld_v2(ld_file):
    """Read reference LD scores for all chromosomes."""

    suffix = ".l2.ldscore"
    chr_files = _read_chr_files(ld_file, suffix)
    df_list = [_read_file(file_path) for file_path in chr_files]
    if not df_list:
        raise FileNotFoundError(f"No LD score files found matching pattern: {ld_file}*{suffix}*")

    ref_ld = pd.concat(df_list, axis=0)
    if "index" in ref_ld.columns:
        ref_ld.rename(columns={"index": "SNP"}, inplace=True)
    if "SNP" in ref_ld.columns:
        ref_ld.set_index("SNP", inplace=True)
    return ref_ld


def _read_w_ld(w_file):
    """Read LD weights for all chromosomes."""

    suffix = ".l2.ldscore"
    chr_files = _read_chr_files(w_file, suffix)
    if not chr_files:
        raise FileNotFoundError(f"No LD score files found matching pattern: {w_file}*{suffix}*")

    w_array = []
    for file_path in chr_files:
        frame = _read_file(file_path)
        if "CHR" in frame.columns and "BP" in frame.columns:
            frame = frame.sort_values(by=["CHR", "BP"])

        columns_to_drop = ["MAF", "CM", "Gene", "TSS", "CHR", "BP"]
        columns_to_drop = [col for col in columns_to_drop if col in frame.columns]
        if columns_to_drop:
            frame = frame.drop(columns=columns_to_drop, axis=1)
        w_array.append(frame)

    w_ld = pd.concat(w_array, axis=0)
    w_ld.columns = (
        ["SNP", "LD_weights"] + list(w_ld.columns[2:])
        if len(w_ld.columns) > 2
        else ["SNP", "LD_weights"]
    )
    return w_ld
