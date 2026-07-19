from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import scanpy as sc
import scipy as sp

from ._config import CauchyCombinationConfig
from ._style import Colors, EMOJI

logger = logging.getLogger(__name__)


def acat_test(pvalues, weights=None):
    """Aggregate p-values with the ACAT/Cauchy test."""

    if any(np.isnan(pvalues)):
        raise ValueError("Cannot have NAs in the p-values.")
    if any((i > 1) or (i < 0) for i in pvalues):
        raise ValueError("P-values must be between 0 and 1.")
    if any(i == 1 for i in pvalues) and any(i == 0 for i in pvalues):
        raise ValueError("Cannot have both 0 and 1 p-values.")
    if any(i == 0 for i in pvalues):
        return 0.0
    if any(i == 1 for i in pvalues):
        return 1.0

    if weights is None:
        weights = [1 / len(pvalues) for _ in pvalues]
    elif len(weights) != len(pvalues):
        raise ValueError("Length of weights and p-values differs.")
    elif any(i < 0 for i in weights):
        raise ValueError("All weights must be positive.")
    else:
        weights = [i / np.sum(weights) for i in weights]

    pvalues = np.array(pvalues)
    weights = np.array(weights)

    if not any(i < 1e-15 for i in pvalues):
        cct_stat = sum(weights * np.tan((0.5 - pvalues) * np.pi))
    else:
        is_small = [i < 1e-15 for i in pvalues]
        is_large = [i >= 1e-15 for i in pvalues]
        cct_stat = sum((weights[is_small] / pvalues[is_small]) / np.pi)
        cct_stat += sum(weights[is_large] * np.tan((0.5 - pvalues[is_large]) * np.pi))

    if cct_stat > 1e15:
        return (1 / cct_stat) / np.pi
    return 1 - sp.stats.cauchy.cdf(cct_stat)


def run_cauchy_combination(config: CauchyCombinationConfig):
    """Run cauchy combination over spot-level spatial-LDSC p-values."""

    ldsc_list = []

    for sample_name in config.sample_name_list:
        config.sample_name = sample_name

        ldsc_input_file = config.get_ldsc_result_file(trait_name=config.trait_name)
        if not Path(ldsc_input_file).exists():
            raise FileNotFoundError(f"{ldsc_input_file} does not exist.")
        ldsc = pd.read_csv(ldsc_input_file, compression="gzip")
        ldsc["spot"] = ldsc["spot"].astype(str)
        ldsc.index = ldsc["spot"]

        h5ad_file = config.hdf5_with_latent_path
        if not Path(h5ad_file).exists():
            raise FileNotFoundError(f"{h5ad_file} does not exist.")
        adata = sc.read_h5ad(h5ad_file)

        common_cells = np.intersect1d(ldsc.index, adata.obs_names)
        adata = adata[common_cells]
        ldsc = ldsc.loc[common_cells]
        ldsc["annotation"] = adata.obs.loc[ldsc.spot, config.annotation].to_list()
        ldsc_list.append(ldsc)

    ldsc_all = pd.concat(ldsc_list)

    p_cauchy = []
    p_median = []
    annotations = ldsc_all["annotation"].unique()

    for annotation in annotations:
        p_values = ldsc_all.loc[ldsc_all["annotation"] == annotation, "p"]
        p_values_log = -np.log10(p_values)
        median_log = np.median(p_values_log)
        iqr_log = np.percentile(p_values_log, 75) - np.percentile(p_values_log, 25)
        p_values_filtered = p_values[p_values_log < median_log + 3 * iqr_log]
        n_removed = len(p_values) - len(p_values_filtered)

        if 0 < n_removed < max(len(p_values) * 0.01, 20):
            p_cauchy_temp = acat_test(p_values_filtered)
        else:
            p_cauchy_temp = acat_test(p_values)

        p_cauchy.append(p_cauchy_temp)
        p_median.append(np.median(p_values))

    results = pd.DataFrame(
        {"annotation": annotations, "p_cauchy": p_cauchy, "p_median": p_median}
    )
    results.sort_values(by="p_cauchy", inplace=True)

    Path(config.output_file).parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    results.to_csv(Path(config.output_file), compression="gzip", index=False)
    print(
        f"{EMOJI['done']} {Colors.GREEN}Cauchy combination results saved at {config.output_file}.{Colors.ENDC}"
    )
    return results
